from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _finite(x: float) -> float | None:
    return float(x) if x is not None and math.isfinite(x) else None


def performance(
    equity: pd.Series, *, benchmark: pd.Series | None = None, risk_free_rate: float = 0.0
) -> dict[str, float | None]:
    """Summary statistics for an equity curve. Returns None where a metric is undefined."""
    equity = equity.dropna()
    if len(equity) < 2:
        raise ValueError("need at least two equity points")
    returns = equity.pct_change().dropna()
    start_value, end_value = float(equity.iloc[0]), float(equity.iloc[-1])
    years = (equity.index[-1] - equity.index[0]).days / 365.25

    total_return = end_value / start_value - 1
    cagr = (end_value / start_value) ** (1 / years) - 1 if years > 0 and end_value > 0 else None
    std = float(returns.std(ddof=1)) if len(returns) > 1 else float("nan")
    volatility = std * math.sqrt(TRADING_DAYS)
    daily_rf = risk_free_rate / TRADING_DAYS
    sharpe = (returns.mean() - daily_rf) / std * math.sqrt(TRADING_DAYS) if std > 0 else None
    downside = math.sqrt(float(np.mean(np.minimum(returns.to_numpy() - daily_rf, 0.0) ** 2)))
    sortino = (
        (returns.mean() - daily_rf) / downside * math.sqrt(TRADING_DAYS) if downside > 0 else None
    )

    peak = equity.cummax()
    drawdown = equity / peak - 1
    max_drawdown = float(drawdown.min())
    underwater = drawdown < 0
    longest = current = 0
    prev_date = None
    for d, is_under in underwater.items():
        if is_under and prev_date is not None:
            current += (d - prev_date).days
            longest = max(longest, current)
        elif not is_under:
            current = 0
        prev_date = d
    calmar = cagr / abs(max_drawdown) if cagr is not None and max_drawdown < 0 else None

    out: dict[str, float | None] = {
        "start_value": start_value,
        "end_value": end_value,
        "total_return": total_return,
        "cagr": _finite(cagr) if cagr is not None else None,
        "volatility": _finite(volatility),
        "sharpe": _finite(sharpe) if sharpe is not None else None,
        "sortino": _finite(sortino) if sortino is not None else None,
        "max_drawdown": max_drawdown,
        "max_drawdown_days": float(longest),
        "calmar": _finite(calmar) if calmar is not None else None,
        "best_day": float(returns.max()),
        "worst_day": float(returns.min()),
        "positive_days": float((returns > 0).mean()),
    }

    if benchmark is not None:
        bench_returns = benchmark.reindex(equity.index).pct_change().dropna()
        aligned = pd.concat([returns, bench_returns], axis=1, join="inner").dropna()
        if len(aligned) > 2:
            r, b = aligned.iloc[:, 0], aligned.iloc[:, 1]
            var_b = float(b.var(ddof=1))
            beta = float(r.cov(b)) / var_b if var_b > 0 else None
            out["beta"] = _finite(beta) if beta is not None else None
            out["alpha"] = (
                _finite((r.mean() - beta * b.mean()) * TRADING_DAYS) if beta is not None else None
            )
            out["correlation"] = _finite(float(r.corr(b)))
    return out


def risk_adjusted_verdict(equity: pd.Series, benchmark: pd.Series) -> dict[str, Any]:
    """Judge a strategy against its benchmark by Sharpe ratio, over the dates both cover."""
    both = pd.concat([equity, benchmark], axis=1, join="inner").dropna()
    return verdict_from_summaries(performance(both.iloc[:, 0]), performance(both.iloc[:, 1]))


def verdict_from_summaries(
    strategy: Mapping[str, Any], benchmark: Mapping[str, Any]
) -> dict[str, Any]:
    """The verdict from two `performance` summaries already measured over the same dates.

    The strategy is better risk-adjusted when its Sharpe ratio is higher than the benchmark's.
    When either Sharpe ratio is undefined (no volatility) no comparison is possible, and
    `better_risk_adjusted` is None rather than a meaningless True or False.
    """
    sharpe, bench_sharpe = strategy.get("sharpe"), benchmark.get("sharpe")
    cagr, bench_cagr = strategy.get("cagr"), benchmark.get("cagr")
    comparable = sharpe is not None and bench_sharpe is not None
    return {
        "comparable": comparable,
        "better_risk_adjusted": sharpe > bench_sharpe if comparable else None,
        "sharpe": sharpe,
        "benchmark_sharpe": bench_sharpe,
        "cagr_difference": cagr - bench_cagr
        if cagr is not None and bench_cagr is not None
        else None,
    }


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1


def monthly_returns(equity: pd.Series) -> pd.Series:
    month_end = equity.resample("ME").last()
    first = pd.Series([equity.iloc[0]], index=[equity.index[0]])
    return pd.concat([first, month_end]).pct_change().dropna()
