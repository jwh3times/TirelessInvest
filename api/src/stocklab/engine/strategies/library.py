"""Built-in strategies. Each one is deliberately simple and well known, so results are
easy to sanity-check against published research before trusting anything fancier."""

from __future__ import annotations

import pandas as pd
from pydantic import Field, field_validator

from .base import Strategy, StrategyParams, equal_weight, tradable_symbols


class FixedWeightsParams(StrategyParams):
    weights: dict[str, float] | None = Field(
        default=None,
        description="Target weight per symbol (fractions of equity). Omit for equal weight.",
    )

    @field_validator("weights")
    @classmethod
    def _valid(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return v
        if any(w < 0 for w in v.values()):
            raise ValueError("weights must be non-negative")
        if sum(v.values()) > 1.0 + 1e-9:
            raise ValueError("weights must sum to at most 1")
        return {k.upper(): w for k, w in v.items()}


class FixedWeights(Strategy):
    key = "fixed_weights"
    label = "Buy and hold / fixed allocation"
    description = (
        "Hold a fixed mix (e.g. 100% SPY, or 60/40 stocks/bonds). With rebalancing set to "
        "'never' this is pure buy-and-hold; otherwise it periodically resets to the target mix."
    )
    params_model = FixedWeightsParams
    default_rebalance = "never"

    def warmup_days(self) -> int:
        return 0

    def target_weights(self, close: pd.DataFrame) -> pd.Series:
        params: FixedWeightsParams = self.params  # type: ignore[assignment]
        available = tradable_symbols(close, 0)
        if params.weights is None:
            return equal_weight(available)
        return pd.Series({s: w for s, w in params.weights.items() if s in available}, dtype=float)


class MomentumParams(StrategyParams):
    lookback_days: int = Field(252, ge=20, le=756, description="Return measurement window.")
    skip_days: int = Field(
        21, ge=0, le=63, description="Ignore the most recent days (short-term reversal effect)."
    )
    top_n: int = Field(3, ge=1, le=50, description="Number of top-ranked symbols to hold.")
    absolute_filter: bool = Field(
        True, description="Only hold a symbol if its own momentum is positive; otherwise cash."
    )


class Momentum(Strategy):
    key = "momentum"
    label = "Momentum rotation"
    description = (
        "Rank symbols by trailing return and hold the strongest few in equal weight. "
        "The absolute filter moves to cash when even the leaders are falling."
    )
    params_model = MomentumParams
    default_rebalance = "monthly"

    def warmup_days(self) -> int:
        p: MomentumParams = self.params  # type: ignore[assignment]
        return p.lookback_days + p.skip_days

    def target_weights(self, close: pd.DataFrame) -> pd.Series:
        p: MomentumParams = self.params  # type: ignore[assignment]
        need = p.lookback_days + p.skip_days
        symbols = tradable_symbols(close, need)
        if not symbols:
            return pd.Series(dtype=float)
        window = close[symbols]
        end = window.iloc[-1 - p.skip_days]
        begin = window.iloc[-1 - p.skip_days - p.lookback_days]
        momentum = (end / begin - 1).dropna().sort_values(ascending=False)
        if p.absolute_filter:
            momentum = momentum[momentum > 0]
        picks = momentum.index[: p.top_n]
        if len(picks) == 0:
            return pd.Series(dtype=float)
        # Each pick gets 1/top_n; unfilled slots stay in cash.
        return pd.Series(1.0 / p.top_n, index=picks)


class SmaTrendParams(StrategyParams):
    sma_days: int = Field(200, ge=10, le=400, description="Moving-average length.")
    concentrate: bool = Field(
        False,
        description="If true, split equity among symbols in an uptrend. If false, each symbol "
        "keeps a fixed 1/N slot and its slot sits in cash while it is below trend.",
    )


class SmaTrend(Strategy):
    key = "sma_trend"
    label = "Trend following (moving average)"
    description = (
        "Hold a symbol only while its price is above its moving average. Designed to sidestep "
        "long bear markets at the cost of whipsaws in choppy ones."
    )
    params_model = SmaTrendParams
    default_rebalance = "monthly"

    def warmup_days(self) -> int:
        return self.params.sma_days  # type: ignore[attr-defined]

    def target_weights(self, close: pd.DataFrame) -> pd.Series:
        p: SmaTrendParams = self.params  # type: ignore[assignment]
        universe = tradable_symbols(close, 0)
        symbols = tradable_symbols(close, p.sma_days)
        if not universe:
            return pd.Series(dtype=float)
        tail = close[symbols].iloc[-p.sma_days :]
        is_above = tail.iloc[-1] > tail.mean()
        above = list(is_above.index[is_above.to_numpy()])
        if not above:
            return pd.Series(dtype=float)
        if p.concentrate:
            return equal_weight(above)
        return pd.Series(1.0 / len(universe), index=above)


class MeanReversionParams(StrategyParams):
    lookback_days: int = Field(5, ge=2, le=30, description="Short-term pullback window.")
    trend_sma_days: int = Field(
        200, ge=20, le=400, description="Only buy pullbacks in symbols above this average."
    )
    hold_n: int = Field(3, ge=1, le=50, description="Number of symbols to hold.")


class MeanReversion(Strategy):
    key = "mean_reversion"
    label = "Short-term mean reversion"
    description = (
        "Buy the symbols that fell the most over the last few days, but only within a "
        "long-term uptrend. High turnover, so it is very sensitive to fees and slippage."
    )
    params_model = MeanReversionParams
    default_rebalance = "weekly"
    feature_flag = "strategy.mean_reversion"

    def warmup_days(self) -> int:
        p: MeanReversionParams = self.params  # type: ignore[assignment]
        return max(p.trend_sma_days, p.lookback_days)

    def target_weights(self, close: pd.DataFrame) -> pd.Series:
        p: MeanReversionParams = self.params  # type: ignore[assignment]
        symbols = tradable_symbols(close, self.warmup_days())
        if not symbols:
            return pd.Series(dtype=float)
        window = close[symbols]
        sma = window.iloc[-p.trend_sma_days :].mean()
        last = window.iloc[-1]
        in_uptrend = last[last > sma].index
        if len(in_uptrend) == 0:
            return pd.Series(dtype=float)
        pullback = last[in_uptrend] / window[in_uptrend].iloc[-1 - p.lookback_days] - 1
        picks = pullback.sort_values().index[: p.hold_n]
        return pd.Series(1.0 / p.hold_n, index=picks)
