"""Risk overlay: the "risk dial".

Risk is applied on top of whatever the strategy wants, instead of being a choice of strategy.
That keeps the two questions separate: "which assets does this strategy like?" and
"how much of my money should be exposed to them?".
"""

from __future__ import annotations

import math

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class RiskSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_position_weight: float = Field(
        1.0, gt=0, le=1, description="Cap on any single symbol's share of equity."
    )
    target_volatility: float | None = Field(
        None,
        gt=0,
        le=1,
        description="Annualized volatility target. Exposure is scaled down (never levered up) "
        "when the proposed portfolio's recent volatility exceeds it. Null disables.",
    )
    vol_lookback_days: int = Field(63, ge=10, le=252)
    cash_buffer: float = Field(0.0, ge=0, lt=1, description="Fraction always held in cash.")


RISK_PRESETS: dict[int, tuple[str, RiskSettings]] = {
    1: (
        "Preservation",
        RiskSettings(max_position_weight=0.25, target_volatility=0.06, cash_buffer=0.05),
    ),
    2: ("Conservative", RiskSettings(max_position_weight=0.35, target_volatility=0.10)),
    3: ("Moderate", RiskSettings(max_position_weight=0.50, target_volatility=0.15)),
    4: ("Growth", RiskSettings(max_position_weight=1.0, target_volatility=0.22)),
    5: ("Unconstrained", RiskSettings()),
}


def apply_risk(weights: pd.Series, close: pd.DataFrame, risk: RiskSettings) -> pd.Series:
    """Return risk-adjusted weights. Freed-up weight goes to cash, never to other symbols."""
    w = weights.astype(float).fillna(0.0).clip(lower=0.0)
    w = w[w > 0]
    if w.empty:
        return w
    total = w.sum()
    if total > 1.0:
        w = w / total
    w = w.clip(upper=risk.max_position_weight)

    if risk.target_volatility is not None:
        returns = close[w.index].pct_change().iloc[-risk.vol_lookback_days :]
        returns = returns.dropna(how="any")
        if len(returns) >= 10:
            portfolio = returns.to_numpy() @ w.to_numpy()
            vol = float(portfolio.std(ddof=1)) * math.sqrt(252)
            if vol > risk.target_volatility:
                w = w * (risk.target_volatility / vol)

    return w * (1.0 - risk.cash_buffer)
