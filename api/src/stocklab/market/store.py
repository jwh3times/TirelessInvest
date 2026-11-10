"""Postgres-backed price store with on-demand backfill from Alpaca."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import psycopg

from ..db import connection
from ..engine.data import Bars
from .alpaca import AlpacaClient

log = logging.getLogger(__name__)


class PostgresPriceStore:
    def __init__(self, alpaca: AlpacaClient | None = None, backfill_floor: date | None = None):
        self.alpaca = alpaca
        self.backfill_floor = backfill_floor or date(2016, 1, 1)

    def load(self, symbols: list[str], start: date, end: date) -> Bars:
        if self.alpaca is not None:
            self.ensure_history(symbols, start)
        with connection() as conn:
            rows = conn.execute(
                """
                select symbol, date, open, close from public.prices_daily
                where symbol = any(%s) and date between %s and %s
                order by date
                """,
                (symbols, start, end),
            ).fetchall()
        return Bars.from_long(
            pd.DataFrame(rows, columns=["symbol", "date", "open", "close"]), symbols
        )

    def ensure_history(self, symbols: list[str], start: date) -> None:
        """Backfill any symbol we have never fetched, or not fetched back far enough."""
        assert self.alpaca is not None
        start = max(start, self.backfill_floor)
        with connection() as conn:
            known = {
                r["symbol"]: r["history_from"]
                for r in conn.execute(
                    "select symbol, history_from from public.symbols where symbol = any(%s)",
                    (symbols,),
                )
            }
        needed = [s for s in symbols if s not in known or (known[s] or date.max) > start]
        if not needed:
            return
        log.info("backfilling %s from %s", needed, start)
        bars = self.alpaca.daily_bars(needed, start, date.today())
        found = sorted(set(bars["symbol"])) if not bars.empty else []
        with connection() as conn:
            upsert_bars(conn, bars)
            # Only register symbols Alpaca actually knows, so typos don't get synced forever.
            for symbol in found:
                conn.execute(
                    """
                    insert into public.symbols (symbol, history_from, last_synced_at)
                    values (%s, %s, now())
                    on conflict (symbol) do update set
                      history_from = least(public.symbols.history_from, excluded.history_from),
                      last_synced_at = now()
                    """,
                    (symbol, start),
                )

    def refresh_all(self) -> dict[str, int]:
        """Re-download the full history of every tracked symbol. Idempotent.

        Why full history and not just the last few days: adjusted prices are rewritten
        backwards every time a symbol pays a dividend or splits. Appending only new days
        would mix two adjustment bases and create fake price jumps on those dates."""
        assert self.alpaca is not None
        with connection() as conn:
            tracked = conn.execute(
                "select symbol, coalesce(history_from, %s) as history_from from public.symbols",
                (self.backfill_floor,),
            ).fetchall()
        by_start: dict[date, list[str]] = {}
        for r in tracked:
            by_start.setdefault(r["history_from"], []).append(r["symbol"])
        rows = 0
        for start, symbols in by_start.items():
            bars = self.alpaca.daily_bars(symbols, start, date.today())
            rows += len(bars)
            with connection() as conn:
                upsert_bars(conn, bars)
                conn.execute(
                    "update public.symbols set last_synced_at = now() where symbol = any(%s)",
                    (symbols,),
                )
        return {"symbols": len(tracked), "rows": rows}


def upsert_bars(conn: psycopg.Connection, bars: pd.DataFrame) -> None:
    if bars.empty:
        return
    with conn.cursor() as cur:
        cur.execute(
            "insert into public.symbols (symbol) select unnest(%s::text[]) on conflict do nothing",
            (sorted(set(bars["symbol"])),),
        )
        cur.execute("create temp table _bars (like public.prices_daily) on commit drop")
        with cur.copy(
            "copy _bars (symbol, date, open, high, low, close, volume) from stdin"
        ) as copy:
            for row in bars.itertuples(index=False):
                copy.write_row(row)
        cur.execute(
            """
            insert into public.prices_daily (symbol, date, open, high, low, close, volume)
            select symbol, date, open, high, low, close, volume from _bars
            on conflict (symbol, date) do update set
              open = excluded.open, high = excluded.high, low = excluded.low,
              close = excluded.close, volume = excluded.volume
            """
        )
