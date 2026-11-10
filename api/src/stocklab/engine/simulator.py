"""Daily-bar portfolio simulator.

Timing model (the part most home-made backtesters get wrong):
  1. At the close of day t the strategy sees closes up to and including t.
  2. Orders execute at the open of day t+1, with slippage and fees.
  3. The portfolio is marked to market at every close.
So the strategy never trades at a price it has already seen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .data import Bars
from .risk import RiskSettings, apply_risk
from .strategies import Rebalance, Strategy


class Costs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_bps: float = Field(0.0, ge=0, le=500, description="Commission per trade, in basis points.")
    slippage_bps: float = Field(
        5.0, ge=0, le=500, description="Price moved against you per trade, in basis points."
    )


@dataclass(frozen=True)
class Trade:
    date: date
    symbol: str
    side: str  # "buy" | "sell"
    shares: float
    price: float  # execution price after slippage
    notional: float
    fee: float
    reason: str = "rebalance"  # "rebalance" | "delisted"


@dataclass
class SimulationResult:
    equity: pd.Series
    exposure: pd.Series  # fraction of equity invested at each close
    trades: list[Trade] = field(default_factory=list)
    final_shares: dict[str, float] = field(default_factory=dict)
    final_cash: float = 0.0
    total_fees: float = 0.0
    total_slippage: float = 0.0
    traded_notional: float = 0.0


def _period_keys(dates: pd.DatetimeIndex, rebalance: Rebalance) -> np.ndarray | None:
    if rebalance == "weekly":
        iso = dates.isocalendar()
        return (iso["year"].to_numpy() * 100 + iso["week"].to_numpy()).astype(int)
    if rebalance == "monthly":
        return dates.year.to_numpy() * 12 + dates.month.to_numpy()
    if rebalance == "quarterly":
        return dates.year.to_numpy() * 4 + (dates.month.to_numpy() - 1) // 3
    return None


def decision_days(dates: pd.DatetimeIndex, start_idx: int, rebalance: Rebalance) -> np.ndarray:
    """Boolean mask of days whose close triggers a rebalance decision.

    Always decides on the first day. Periodic schedules decide on the last trading day of
    each period. Knowing a period ends tomorrow is calendar knowledge, not price lookahead.
    The final day never decides, since there is no next open to trade at.
    """
    n = len(dates)
    mask = np.zeros(n, dtype=bool)
    mask[start_idx] = True
    if rebalance == "daily":
        mask[start_idx:] = True
    elif rebalance != "never":
        keys = _period_keys(dates, rebalance)
        assert keys is not None
        period_ends = np.append(keys[:-1] != keys[1:], False)
        mask[start_idx:] |= period_ends[start_idx:]
    mask[n - 1] = False
    return mask


def simulate(
    bars: Bars,
    strategy: Strategy,
    *,
    start: date,
    starting_cash: float,
    rebalance: Rebalance,
    risk: RiskSettings | None = None,
    costs: Costs | None = None,
    rebalance_threshold: float = 0.0,
) -> SimulationResult:
    if starting_cash <= 0:
        raise ValueError("starting_cash must be positive")
    risk = risk or RiskSettings()
    costs = costs or Costs()
    fee_rate = costs.fee_bps / 10_000
    slip = costs.slippage_bps / 10_000

    dates = bars.dates
    symbols = bars.symbols
    start_idx = int(dates.searchsorted(pd.Timestamp(start)))
    if start_idx >= len(dates) - 1:
        raise ValueError("not enough trading days after the start date")

    opens = bars.open.to_numpy(dtype=float)
    closes = bars.close.to_numpy(dtype=float)
    closes_ff = bars.close.ffill().to_numpy(dtype=float)
    valid_close = ~np.isnan(closes)
    last_valid = np.where(
        valid_close.any(axis=0),
        len(dates) - 1 - np.argmax(valid_close[::-1], axis=0),
        -1,
    )
    decide = decision_days(dates, start_idx, rebalance)

    n_sym = len(symbols)
    shares = np.zeros(n_sym)
    cash = float(starting_cash)
    pending: np.ndarray | None = None
    equity = np.empty(len(dates) - start_idx)
    exposure = np.empty(len(dates) - start_idx)
    trades: list[Trade] = []
    total_fees = total_slippage = traded = 0.0

    for i in range(start_idx, len(dates)):
        day = dates[i].date()

        if pending is not None:
            px = opens[i]
            tradable = ~np.isnan(px) & (px > 0)
            mark = np.where(tradable, px, closes_ff[i - 1])
            held_value = np.nansum(shares * mark)
            pre_equity = cash + held_value
            current = np.nan_to_num(shares * mark)
            target = np.where(tradable, pending * pre_equity, current)
            delta = target - current
            small = (np.abs(delta) < rebalance_threshold * pre_equity) & (target > 0)
            delta[small] = 0.0

            for j in np.flatnonzero(delta < 0):
                qty = min(-delta[j] / px[j], shares[j])
                if target[j] == 0:
                    qty = shares[j]  # close the position completely, no dust
                if qty <= 0:
                    continue
                exec_px = px[j] * (1 - slip)
                proceeds = qty * exec_px
                fee = proceeds * fee_rate
                cash += proceeds - fee
                shares[j] -= qty
                total_fees += fee
                total_slippage += qty * px[j] * slip
                traded += proceeds
                trades.append(Trade(day, symbols[j], "sell", qty, exec_px, proceeds, fee))

            buys = np.flatnonzero(delta > 0)
            if buys.size:
                gross_needed = float(np.sum(delta[buys])) * (1 + slip) * (1 + fee_rate)
                scale = min(1.0, cash / gross_needed) if gross_needed > 0 else 0.0
                for j in buys:
                    exec_px = px[j] * (1 + slip)
                    qty = delta[j] * scale / px[j]
                    if qty <= 0:
                        continue
                    spend = qty * exec_px
                    fee = spend * fee_rate
                    cash -= spend + fee
                    shares[j] += qty
                    total_fees += fee
                    total_slippage += qty * px[j] * slip
                    traded += spend
                    trades.append(Trade(day, symbols[j], "buy", qty, exec_px, spend, fee))
            cash = max(cash, 0.0)  # guard against float dust
            pending = None

        # Symbols whose data ends here (delisted, merged, renamed) are sold at the last close
        # so the backtest doesn't carry a frozen position forever.
        if i < len(dates) - 1:
            for j in np.flatnonzero((last_valid == i) & (shares > 0)):
                exec_px = closes[i, j] * (1 - slip)
                proceeds = shares[j] * exec_px
                fee = proceeds * fee_rate
                cash += proceeds - fee
                total_fees += fee
                total_slippage += shares[j] * closes[i, j] * slip
                traded += proceeds
                trades.append(
                    Trade(day, symbols[j], "sell", shares[j], exec_px, proceeds, fee, "delisted")
                )
                shares[j] = 0.0

        held = float(np.nansum(shares * closes_ff[i]))
        equity[i - start_idx] = cash + held
        exposure[i - start_idx] = held / (cash + held) if cash + held > 0 else 0.0

        if decide[i]:
            history = bars.close.iloc[: i + 1]
            raw = strategy.target_weights(history)
            adjusted = apply_risk(raw, history, risk)
            pending = adjusted.reindex(symbols).fillna(0.0).to_numpy(dtype=float)

    index = dates[start_idx:]
    return SimulationResult(
        equity=pd.Series(equity, index=index, name="equity"),
        exposure=pd.Series(exposure, index=index, name="exposure"),
        trades=trades,
        final_shares={s: float(q) for s, q in zip(symbols, shares, strict=True) if q > 1e-12},
        final_cash=cash,
        total_fees=total_fees,
        total_slippage=total_slippage,
        traded_notional=traded,
    )
