"""Turns a user's backtest request into a full report (strategy run + benchmark run)."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .data import Bars, PriceStore
from .metrics import drawdown_series, monthly_returns, performance, risk_adjusted_verdict
from .risk import DEFAULT_RISK_LEVEL, LEGACY_RISK_PRESETS, RISK_PRESETS, RiskSettings
from .simulator import Costs, SimulationResult, simulate
from .strategies import Rebalance, build_strategy
from .strategies.library import FixedWeights, FixedWeightsParams
from .universes import UNIVERSES

SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
MAX_SYMBOLS = 50
MAX_YEARS = 30
MAX_STORED_TRADES = 1000

# The two long bear markets the history gate (PRD P11) asks a strategy to be tested through,
# the PRD's 2000–02 and 2008–09, to the month from peak to trough.
LONG_BEAR_MARKETS = (
    (pd.Period("2000-03", freq="M"), pd.Period("2002-10", freq="M")),
    (pd.Period("2007-10", freq="M"), pd.Period("2009-03", freq="M")),
)


class BacktestError(ValueError):
    """A request that is well-formed but cannot be run (e.g. missing data)."""


def shift_years(d: date, years: int) -> date:
    """The same calendar day `years` later (earlier when negative); 29 February becomes the 28th."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def leaves_a_year_in_sample(first: date, holdout_start: date) -> bool:
    return holdout_start >= shift_years(first, 1)


def _too_short_in_sample(holdout_years: int, detail: str) -> str:
    return f"a {holdout_years}-year holdout needs at least one year in-sample: {detail}"


class UniverseSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preset: str | None = None
    symbols: list[str] | None = None

    @model_validator(mode="after")
    def _one_of(self) -> UniverseSpec:
        if (self.preset is None) == (self.symbols is None):
            raise ValueError("provide exactly one of 'preset' or 'symbols'")
        if self.preset is not None and self.preset not in UNIVERSES:
            raise ValueError(f"unknown universe preset '{self.preset}'")
        if self.symbols is not None:
            cleaned = list(dict.fromkeys(s.strip().upper() for s in self.symbols if s.strip()))
            bad = [s for s in cleaned if not SYMBOL_RE.match(s)]
            if bad:
                raise ValueError(f"invalid symbols: {', '.join(bad)}")
            if not 1 <= len(cleaned) <= MAX_SYMBOLS:
                raise ValueError(f"custom universes need 1 to {MAX_SYMBOLS} symbols")
            self.symbols = cleaned
        return self

    def resolve(self) -> list[str]:
        if self.preset is not None:
            return list(UNIVERSES[self.preset].symbols)
        assert self.symbols is not None
        return list(self.symbols)


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: str
    params: dict[str, Any] = Field(default_factory=dict)
    universe: UniverseSpec
    start_date: date
    end_date: date
    starting_cash: float = Field(10_000, ge=100, le=100_000_000)
    rebalance: Rebalance | None = Field(None, description="Defaults to the strategy's own.")
    risk_level: int = Field(
        DEFAULT_RISK_LEVEL,
        ge=min(RISK_PRESETS),
        le=max(RISK_PRESETS),
        description="Risk dial level, 1-10; 5 = Moderate.",
    )
    risk: RiskSettings | None = Field(None, description="Explicit settings; overrides risk_level.")
    legacy_risk_level: int | None = Field(
        None,
        ge=min(LEGACY_RISK_PRESETS),
        le=max(LEGACY_RISK_PRESETS),
        description="Set on requests saved on the old 1-5 dial; `risk` holds its settings.",
    )
    costs: Costs = Field(default_factory=Costs)
    rebalance_threshold: float = Field(
        0.005, ge=0, le=0.2, description="Skip trades smaller than this fraction of equity."
    )
    benchmark: str = "SPY"
    holdout_years: int | None = Field(
        None,
        ge=1,
        le=MAX_YEARS,
        description="Report the last N years separately from the rest, as a holdout.",
    )

    @model_validator(mode="after")
    def _dates(self) -> BacktestRequest:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        if self.end_date > date.today():
            raise ValueError("end_date cannot be in the future")
        if (self.end_date - self.start_date).days > MAX_YEARS * 366:
            raise ValueError(f"date range is limited to {MAX_YEARS} years")
        self.benchmark = self.benchmark.strip().upper()
        if not SYMBOL_RE.match(self.benchmark):
            raise ValueError("invalid benchmark symbol")
        # The marker labels a result "old 1-5 scale", so it must carry that level's settings.
        legacy = self.legacy_risk_level
        if legacy is not None and self.risk != LEGACY_RISK_PRESETS[legacy][1]:
            raise ValueError("legacy_risk_level needs the explicit risk settings it stands for")
        if self.holdout_years is not None and not leaves_a_year_in_sample(
            self.start_date, self.holdout_start()
        ):
            start_by = shift_years(self.holdout_start(), -1)
            raise ValueError(
                _too_short_in_sample(
                    self.holdout_years, f"start by {start_by}, or hold out fewer years"
                )
            )
        return self

    def holdout_start(self) -> date:
        """The first day of the holdout: the end date less `holdout_years`."""
        assert self.holdout_years is not None
        return shift_years(self.end_date, -self.holdout_years)

    def risk_settings(self) -> RiskSettings:
        return self.risk if self.risk is not None else RISK_PRESETS[self.risk_level][1]


def history_start(req: BacktestRequest, warmup_days: int) -> date:
    """Calendar date to load from so the strategy has its warmup history on day one."""
    return req.start_date - timedelta(days=math.ceil(warmup_days * 1.5) + 10)


def run_backtest(req: BacktestRequest, store: PriceStore) -> dict[str, Any]:
    strategy = build_strategy(req.strategy, req.params)
    symbols = req.universe.resolve()
    risk = req.risk_settings()
    rebalance: Rebalance = req.rebalance or strategy.default_rebalance

    if isinstance(strategy.params, FixedWeightsParams) and strategy.params.weights:
        unknown = sorted(set(strategy.params.weights) - set(symbols))
        if unknown:
            raise BacktestError(f"weights reference symbols outside the universe: {unknown}")

    warmup = max(strategy.warmup_days(), risk.vol_lookback_days if risk.target_volatility else 0)
    load_symbols = list(dict.fromkeys([*symbols, req.benchmark]))
    bars = store.load(load_symbols, history_start(req, warmup), req.end_date)

    missing = [s for s in load_symbols if s not in bars.symbols or bars.close[s].isna().all()]
    if missing:
        raise BacktestError(f"no price data for: {', '.join(missing)}")
    if bars.dates[-1] < pd.Timestamp(req.start_date):
        raise BacktestError("no price data on or after the start date")

    warnings = _data_warnings(req, bars, symbols, warmup)
    if getattr(store, "synthetic", False):
        warnings.insert(
            0,
            "SYNTHETIC DATA: these prices are random, not real market history. "
            "Use this mode only to try the app.",
        )

    try:
        result = simulate(
            bars.select(symbols),
            strategy,
            start=req.start_date,
            starting_cash=req.starting_cash,
            rebalance=rebalance,
            risk=risk,
            costs=req.costs,
            rebalance_threshold=req.rebalance_threshold,
        )
        bench = simulate(
            bars.select([req.benchmark]),
            FixedWeights(FixedWeightsParams(weights={req.benchmark: 1.0})),
            start=req.start_date,
            starting_cash=req.starting_cash,
            rebalance="never",
            costs=req.costs,
        )
    except ValueError as exc:
        raise BacktestError(str(exc)) from exc
    if req.holdout_years is not None:
        _check_holdout_has_data(req, result.equity.index)

    return _report(req, rebalance, risk, result, bench, bars, warnings)


def _data_warnings(req: BacktestRequest, bars: Bars, symbols: list[str], warmup: int) -> list[str]:
    warnings: list[str] = []
    if req.universe.preset and UNIVERSES[req.universe.preset].survivorship_biased:
        warnings.append(
            "This universe is survivorship-biased (only companies that are big today). "
            "Results will look better than a real investor could have achieved."
        )
    first_valid = bars.close.apply(lambda s: s.first_valid_index())
    start_ts = pd.Timestamp(req.start_date)
    late = [s for s in symbols if first_valid[s] > start_ts + pd.Timedelta(days=7)]
    if late:
        detail = ", ".join(f"{s} ({first_valid[s].date()})" for s in late)
        warnings.append(f"Some symbols have no data at the start date and join later: {detail}.")
    first_date = bars.dates[0]
    if first_date > start_ts:
        warnings.append(
            f"Price data begins on {first_date.date()}, after the requested start date; "
            "the backtest starts there instead."
        )
    elif warmup and (start_ts - first_date).days < warmup:
        warnings.append(
            "Not enough history before the start date for the strategy's lookback; "
            "it may sit in cash early on."
        )
    return warnings


def data_window(first: date, last: date) -> dict[str, Any]:
    """The period a backtest had data for, with a notice when it spans neither long bear market.

    It depends on the dates alone, so the notice goes away by itself once longer price history
    lets a backtest reach back through one of them.
    """
    start, end = pd.Period(first, freq="M"), pd.Period(last, freq="M")
    spans_a_bear_market = any(start <= peak and trough <= end for peak, trough in LONG_BEAR_MARKETS)
    notice = (
        None
        if spans_a_bear_market
        else f"Tested only from {first.isoformat()} to {last.isoformat()}: "
        "this period has no long bear market."
    )
    return {"first_date": first.isoformat(), "last_date": last.isoformat(), "notice": notice}


def _check_holdout_has_data(req: BacktestRequest, dates: pd.DatetimeIndex) -> None:
    """The request's dates leave a year in-sample, but its price data may begin later."""
    first, boundary = dates[0].date(), req.holdout_start()
    assert req.holdout_years is not None
    if not leaves_a_year_in_sample(first, boundary):
        raise BacktestError(
            _too_short_in_sample(
                req.holdout_years,
                f"price data begins on {first.isoformat()}, so hold out fewer years, or end later",
            )
        )
    if dates[-1].date() < boundary:
        raise BacktestError(f"no price data in the holdout, from {boundary.isoformat()}")


def _holdout_sections(
    req: BacktestRequest, equity: pd.Series, bench_equity: pd.Series
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The in-sample and holdout sections of one continuous run, or None without a holdout.

    The holdout is measured from the portfolio's value at the last in-sample close: where the
    run had got to, not a fresh start.
    """
    if req.holdout_years is None:
        return None, None
    in_holdout = equity.index >= pd.Timestamp(req.holdout_start())
    in_sample_dates, holdout_dates = equity.index[~in_holdout], equity.index[in_holdout]
    measured_from_last_close = in_sample_dates[-1:].append(holdout_dates)
    return (
        _holdout_section(equity, bench_equity, in_sample_dates, in_sample_dates),
        _holdout_section(equity, bench_equity, holdout_dates, measured_from_last_close),
    )


def _holdout_section(
    equity: pd.Series,
    bench_equity: pd.Series,
    dates: pd.DatetimeIndex,
    return_dates: pd.DatetimeIndex,
) -> dict[str, Any]:
    """A section labelled by `dates`, with its metrics measured over `return_dates`."""
    strategy, bench = equity.loc[return_dates], bench_equity.reindex(return_dates)
    return {
        "first_date": dates[0].date().isoformat(),
        "last_date": dates[-1].date().isoformat(),
        "summary": performance(strategy, benchmark=bench),
        "benchmark": {"summary": performance(bench)},
        "verdict": risk_adjusted_verdict(strategy, bench),
    }


def _round(values: pd.Series, digits: int) -> list[float | None]:
    return [None if pd.isna(v) else round(float(v), digits) for v in values]


def _report(
    req: BacktestRequest,
    rebalance: Rebalance,
    risk: RiskSettings,
    result: SimulationResult,
    bench: SimulationResult,
    bars: Bars,
    warnings: list[str],
) -> dict[str, Any]:
    equity, bench_equity = result.equity, bench.equity
    summary = performance(equity, benchmark=bench_equity)
    years = max((equity.index[-1] - equity.index[0]).days / 365.25, 1 / 365.25)
    summary.update(
        total_fees=round(result.total_fees, 2),
        total_slippage=round(result.total_slippage, 2),
        trade_count=len(result.trades),
        annual_turnover=result.traded_notional / float(equity.mean()) / years,
        average_exposure=float(result.exposure.mean()),
    )

    last_close = bars.close.ffill().iloc[-1]
    end_value = float(equity.iloc[-1])
    positions = [
        {
            "symbol": s,
            "shares": round(q, 6),
            "value": round(q * float(last_close[s]), 2),
            "weight": round(q * float(last_close[s]) / end_value, 6) if end_value else 0.0,
        }
        for s, q in sorted(result.final_shares.items())
    ]
    trades = result.trades[-MAX_STORED_TRADES:]
    in_sample, holdout = _holdout_sections(req, equity, bench_equity)

    return {
        "config": {
            **req.model_dump(mode="json"),
            "rebalance": rebalance,
            "risk": risk.model_dump(mode="json"),
            "symbols": req.universe.resolve(),
        },
        "summary": summary,
        "benchmark": {
            "symbol": req.benchmark,
            "summary": performance(bench_equity),
        },
        "verdict": risk_adjusted_verdict(equity, bench_equity),
        "data_window": data_window(equity.index[0].date(), equity.index[-1].date()),
        "in_sample": in_sample,
        "holdout": holdout,
        "series": {
            "dates": [d.date().isoformat() for d in equity.index],
            "equity": _round(equity, 2),
            "benchmark": _round(bench_equity.reindex(equity.index), 2),
            "drawdown": _round(drawdown_series(equity), 6),
            "benchmark_drawdown": _round(drawdown_series(bench_equity), 6),
            "exposure": _round(result.exposure, 4),
        },
        "monthly_returns": [
            {"month": d.strftime("%Y-%m"), "return": round(float(r), 6)}
            for d, r in monthly_returns(equity).items()
        ],
        "trades": [
            {
                "date": t.date.isoformat(),
                "symbol": t.symbol,
                "side": t.side,
                "shares": round(t.shares, 6),
                "price": round(t.price, 4),
                "notional": round(t.notional, 2),
                "fee": round(t.fee, 4),
                "reason": t.reason,
            }
            for t in trades
        ],
        "trades_truncated": len(result.trades) > len(trades),
        "final_positions": positions,
        "final_cash": round(result.final_cash, 2),
        "warnings": warnings,
    }
