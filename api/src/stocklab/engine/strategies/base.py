from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

Rebalance = Literal["never", "daily", "weekly", "monthly", "quarterly"]


class StrategyParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Strategy(ABC):
    """A strategy turns price history into target portfolio weights.

    Contract:
      * `target_weights` receives closes up to and including the decision day only.
        The simulator executes the result at the next day's open, so a strategy
        cannot see the price it trades at.
      * Returned weights are long-only fractions of equity. They may sum to less than 1
        (the rest is cash). Symbols missing from the result are treated as 0.
    """

    key: ClassVar[str]
    label: ClassVar[str]
    description: ClassVar[str]
    params_model: ClassVar[type[StrategyParams]]
    default_rebalance: ClassVar[Rebalance] = "monthly"
    # Feature flag that must be enabled for users to run this strategy, if any.
    feature_flag: ClassVar[str | None] = None

    def __init__(self, params: StrategyParams) -> None:
        self.params = params

    @abstractmethod
    def warmup_days(self) -> int:
        """Trading days of history needed before the first meaningful decision."""

    @abstractmethod
    def target_weights(self, close: pd.DataFrame) -> pd.Series:
        """Return target weights indexed by symbol."""


def equal_weight(symbols: list[str] | pd.Index) -> pd.Series:
    symbols = list(symbols)
    if not symbols:
        return pd.Series(dtype=float)
    return pd.Series(1.0 / len(symbols), index=symbols)


def tradable_symbols(close: pd.DataFrame, min_history: int) -> list[str]:
    """Symbols with a price today and a price `min_history` rows ago.

    Checks two rows instead of counting the whole history, so a daily-rebalanced backtest
    stays linear in its length. Assumes no long gaps inside a symbol's history, which holds
    for adjusted daily bars."""
    if len(close) <= min_history:
        return []
    ok = close.iloc[-1].notna() & close.iloc[-1 - min_history].notna()
    return list(close.columns[ok.to_numpy()])
