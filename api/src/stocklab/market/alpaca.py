"""Minimal client for Alpaca's market-data API (daily bars only)."""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta

import httpx
import pandas as pd

log = logging.getLogger(__name__)

BAR_COLUMNS = ["symbol", "date", "open", "high", "low", "close", "volume"]
MAX_SYMBOLS_PER_REQUEST = 50


class AlpacaError(RuntimeError):
    pass


class AlpacaClient:
    def __init__(
        self,
        key_id: str,
        secret_key: str,
        *,
        base_url: str = "https://data.alpaca.markets",
        feed: str = "sip",
        http: httpx.Client | None = None,
    ) -> None:
        self.feed = feed
        self._http = http or httpx.Client(timeout=30)
        self._base_url = base_url.rstrip("/")
        self._headers = {"APCA-API-KEY-ID": key_id, "APCA-API-SECRET-KEY": secret_key}

    def daily_bars(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        """Split- and dividend-adjusted daily bars as a long DataFrame (BAR_COLUMNS)."""
        frames = [
            self._fetch(symbols[i : i + MAX_SYMBOLS_PER_REQUEST], start, end)
            for i in range(0, len(symbols), MAX_SYMBOLS_PER_REQUEST)
        ]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame(columns=BAR_COLUMNS)
        return pd.concat(frames, ignore_index=True)

    def _fetch(self, symbols: list[str], start: date, end: date) -> pd.DataFrame:
        # Free plans may not query the most recent 15 minutes of consolidated data.
        end_dt = min(
            datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
            datetime.now(UTC) - timedelta(minutes=20),
        )
        params: dict[str, str | int] = {
            "symbols": ",".join(symbols),
            "timeframe": "1Day",
            "start": start.isoformat(),
            "end": end_dt.isoformat().replace("+00:00", "Z"),
            "adjustment": "all",
            "limit": 10_000,
            "sort": "asc",
        }
        rows: list[tuple] = []
        page_token: str | None = None
        while True:
            if page_token:
                params["page_token"] = page_token
            payload = self._get("/v2/stocks/bars", params)
            for symbol, bars in (payload.get("bars") or {}).items():
                for b in bars:
                    rows.append(
                        (symbol, _bar_date(b["t"]), b["o"], b["h"], b["l"], b["c"], b.get("v", 0))
                    )
            page_token = payload.get("next_page_token")
            if not page_token:
                break
        return pd.DataFrame(rows, columns=BAR_COLUMNS)

    def _get(self, path: str, params: dict) -> dict:
        for attempt in range(4):
            response = self._http.get(
                self._base_url + path,
                params={**params, "feed": self.feed},
                headers=self._headers,
            )
            if response.status_code == 403 and self.feed == "sip":
                log.warning("Alpaca rejected the SIP feed for this account; falling back to IEX")
                self.feed = "iex"
                continue
            if response.status_code == 429:
                wait = float(response.headers.get("retry-after", 2 ** (attempt + 1)))
                time.sleep(min(wait, 30))
                continue
            if response.status_code >= 400:
                raise AlpacaError(f"Alpaca {response.status_code}: {response.text[:300]}")
            return response.json()
        raise AlpacaError("Alpaca request failed after retries")


def _bar_date(timestamp: str) -> date:
    """Daily bars are stamped at midnight New York time, expressed in UTC."""
    return pd.Timestamp(timestamp).tz_convert("America/New_York").date()
