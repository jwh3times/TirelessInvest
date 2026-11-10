"""Price data containers and providers.

Prices are stored "wide": a DataFrame indexed by trading date with one column per symbol.
All prices are split- and dividend-adjusted, so a buy-and-hold return computed from them
is a total return.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Bars:
    """Daily open and close prices for a set of symbols over a shared date index."""

    open: pd.DataFrame
    close: pd.DataFrame

    def __post_init__(self) -> None:
        if not self.open.index.equals(self.close.index):
            raise ValueError("open and close must share the same date index")
        if list(self.open.columns) != list(self.close.columns):
            raise ValueError("open and close must share the same symbol columns")
        if not self.close.index.is_monotonic_increasing:
            raise ValueError("bars must be sorted by date ascending")

    @property
    def symbols(self) -> list[str]:
        return list(self.close.columns)

    @property
    def dates(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(self.close.index)

    def select(self, symbols: list[str]) -> Bars:
        return Bars(open=self.open[symbols], close=self.close[symbols])

    @classmethod
    def from_long(cls, rows: pd.DataFrame, symbols: list[str]) -> Bars:
        """Build from a long frame with columns: symbol, date, open, close.

        Every requested symbol gets a column; symbols without rows are all-NaN."""
        if rows.empty:
            empty = pd.DataFrame(columns=symbols, index=pd.DatetimeIndex([]), dtype=float)
            return cls(open=empty, close=empty.copy())
        rows = rows.copy()
        rows["date"] = pd.to_datetime(rows["date"])
        open_ = rows.pivot(index="date", columns="symbol", values="open").sort_index()
        close = rows.pivot(index="date", columns="symbol", values="close").sort_index()
        return cls(
            open=open_.reindex(columns=symbols).astype(float),
            close=close.reindex(columns=symbols).astype(float),
        )


class PriceStore(Protocol):
    """Anything that can load adjusted daily bars for a date range."""

    def load(self, symbols: list[str], start: date, end: date) -> Bars: ...


def synthetic_bars(
    symbols: list[str],
    start: date,
    end: date,
    *,
    seed: int = 7,
    annual_drift: float = 0.07,
    annual_vol: float = 0.18,
) -> Bars:
    """Deterministic random-walk prices on business days. For tests and offline demos only;
    results from synthetic data say nothing about real markets."""
    dates = pd.bdate_range(start, end)
    rng = np.random.default_rng(seed)
    n, k = len(dates), len(symbols)
    daily_mu = annual_drift / 252
    daily_sigma = annual_vol / np.sqrt(252)
    # Correlated assets: one shared market factor plus idiosyncratic noise.
    market = rng.normal(0, daily_sigma * 0.7, size=(n, 1))
    idio = rng.normal(0, daily_sigma * 0.7, size=(n, k))
    drifts = daily_mu + rng.normal(0, daily_mu, size=k)
    log_returns = drifts + market + idio
    close = 100 * np.exp(np.cumsum(log_returns, axis=0))
    gap = rng.normal(0, daily_sigma * 0.2, size=(n, k))
    prev_close = np.vstack([np.full((1, k), 100.0), close[:-1]])
    open_ = prev_close * np.exp(gap)
    return Bars(
        open=pd.DataFrame(open_, index=dates, columns=symbols),
        close=pd.DataFrame(close, index=dates, columns=symbols),
    )


class SyntheticPriceStore:
    """PriceStore backed by synthetic data (PRICE_SOURCE=synthetic)."""

    synthetic = True

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed

    def load(self, symbols: list[str], start: date, end: date) -> Bars:
        return synthetic_bars(symbols, start, end, seed=self.seed)
