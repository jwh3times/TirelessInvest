import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from tirelessinvest.engine.backtest import BacktestError, BacktestRequest, run_backtest
from tirelessinvest.engine.data import Bars, SyntheticPriceStore, synthetic_bars
from tirelessinvest.engine.metrics import performance, risk_adjusted_verdict
from tirelessinvest.engine.risk import (
    LEGACY_RISK_PRESETS,
    RISK_PRESETS,
    RiskSettings,
    apply_risk,
)
from tirelessinvest.engine.simulator import Costs, decision_days, simulate
from tirelessinvest.engine.strategies import STRATEGIES, Strategy, build_strategy
from tirelessinvest.engine.strategies.base import StrategyParams

NO_COSTS = Costs(fee_bps=0, slippage_bps=0)


def linear_bars(symbol: str = "AAA", days: int = 30, start_price: float = 100.0) -> Bars:
    dates = pd.bdate_range("2024-01-01", periods=days)
    close = pd.DataFrame({symbol: start_price + np.arange(days, dtype=float)}, index=dates)
    open_ = close.shift(1).fillna(start_price)  # opens at previous close
    return Bars(open=open_, close=close)


def test_buy_and_hold_matches_price_return_without_costs():
    bars = linear_bars()
    result = simulate(
        bars,
        build_strategy("fixed_weights", {"weights": {"AAA": 1.0}}),
        start=date(2024, 1, 1),
        starting_cash=1000,
        rebalance="never",
        costs=NO_COSTS,
    )
    # Decides at day-0 close (100), buys at day-1 open (= day-0 close = 100).
    expected = 1000 * bars.close["AAA"].iloc[-1] / 100.0
    assert result.equity.iloc[-1] == pytest.approx(expected)
    assert result.equity.iloc[0] == 1000  # first day is all cash
    assert len(result.trades) == 1


def test_costs_reduce_returns():
    bars = synthetic_bars(["A", "B", "C"], date(2020, 1, 1), date(2022, 12, 31))
    kwargs = dict(start=date(2020, 1, 1), starting_cash=10_000, rebalance="daily")
    strat = build_strategy("fixed_weights", {})
    free = simulate(bars, strat, costs=NO_COSTS, **kwargs)
    costly = simulate(bars, strat, costs=Costs(fee_bps=10, slippage_bps=10), **kwargs)
    assert costly.equity.iloc[-1] < free.equity.iloc[-1]
    assert costly.total_fees > 0 and costly.total_slippage > 0


class PeekingCheck(Strategy):
    """Records the last date it was shown, to prove the simulator never leaks the future."""

    key = "peek"
    label = description = "test"
    params_model = StrategyParams

    def __init__(self):
        super().__init__(StrategyParams())
        self.seen: list[pd.Timestamp] = []

    def warmup_days(self) -> int:
        return 0

    def target_weights(self, close):
        self.seen.append(close.index[-1])
        return pd.Series({close.columns[0]: 1.0})


def test_no_lookahead_and_next_open_execution():
    bars = synthetic_bars(["A"], date(2021, 1, 1), date(2021, 3, 31))
    strat = PeekingCheck()
    result = simulate(
        bars, strat, start=date(2021, 1, 4), starting_cash=1000, rebalance="weekly", costs=NO_COSTS
    )
    dates = list(bars.dates)
    for decision_date, trade in zip(strat.seen, result.trades, strict=False):
        # Trade happens strictly after the information it was based on.
        assert pd.Timestamp(trade.date) > decision_date
        next_day = dates[dates.index(decision_date) + 1]
        assert pd.Timestamp(trade.date) == next_day
        assert trade.price == pytest.approx(bars.open.loc[next_day, "A"])


def test_decision_days_monthly_uses_last_trading_day():
    dates = pd.bdate_range("2024-01-01", "2024-04-30")
    mask = decision_days(dates, 0, "monthly")
    decided = [d.date() for d in dates[mask]]
    assert decided == [date(2024, 1, 1), date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 29)]


def test_volatility_target_scales_exposure_down():
    bars = synthetic_bars(["A"], date(2020, 1, 1), date(2020, 12, 31), annual_vol=0.40)
    w = apply_risk(pd.Series({"A": 1.0}), bars.close, RiskSettings(target_volatility=0.10))
    assert 0 < w["A"] < 0.5


def test_position_cap_leaves_cash():
    w = apply_risk(
        pd.Series({"A": 0.8, "B": 0.2}), pd.DataFrame(), RiskSettings(max_position_weight=0.5)
    )
    assert w.to_dict() == {"A": 0.5, "B": 0.2}


def test_delisted_symbol_is_liquidated():
    bars = linear_bars("A", 20)
    close = bars.close.copy()
    close["B"] = 50.0
    close.loc[close.index[10] :, "B"] = np.nan  # B stops trading after day 9
    open_ = close.shift(1).fillna(close.iloc[0])
    bars = Bars(open=open_, close=close)
    result = simulate(
        bars,
        build_strategy("fixed_weights", {}),
        start=date(2024, 1, 1),
        starting_cash=1000,
        rebalance="never",
        costs=NO_COSTS,
    )
    assert any(t.reason == "delisted" and t.symbol == "B" for t in result.trades)
    assert "B" not in result.final_shares


def test_metrics_on_known_curve():
    idx = pd.bdate_range("2020-01-01", periods=4)
    m = performance(pd.Series([100.0, 110.0, 99.0, 121.0], index=idx))
    assert m["total_return"] == pytest.approx(0.21)
    assert m["max_drawdown"] == pytest.approx(-0.1)


def alternating_curve(up: float, down: float, days: int = 253, start: str = "2020-01-01"):
    """An equity curve whose daily returns alternate between `up` and `down`."""
    returns = np.where(np.arange(days - 1) % 2 == 0, up, down)
    values = 100.0 * np.cumprod(np.concatenate([[1.0], 1.0 + returns]))
    return pd.Series(values, index=pd.bdate_range(start, periods=days))


def alternating_sharpe(up: float, down: float, n: int = 252) -> float:
    """Sharpe (risk-free 0, annualised over 252 days) of n alternating daily returns, by hand."""
    mean, std = (up + down) / 2, abs(up - down) / 2 * (n / (n - 1)) ** 0.5
    return mean / std * 252**0.5


CALM = (0.001, 0.0)  # earns little, barely moves
WILD = (0.02, -0.016)  # earns more, swings hard


def test_verdict_prefers_higher_sharpe_even_with_lower_cagr():
    v = risk_adjusted_verdict(alternating_curve(*CALM), alternating_curve(*WILD))
    assert v["comparable"] is True
    assert v["better_risk_adjusted"] is True
    assert v["sharpe"] == pytest.approx(alternating_sharpe(*CALM))
    assert v["benchmark_sharpe"] == pytest.approx(alternating_sharpe(*WILD))
    assert v["cagr_difference"] < 0  # the CAGR shortfall is still reported


def test_verdict_reports_worse_when_sharpe_is_lower_despite_higher_cagr():
    v = risk_adjusted_verdict(alternating_curve(*WILD), alternating_curve(*CALM))
    assert v["comparable"] is True
    assert v["better_risk_adjusted"] is False
    assert v["cagr_difference"] > 0


def test_verdict_is_not_comparable_when_a_sharpe_is_undefined():
    flat = pd.Series(100.0, index=pd.bdate_range("2020-01-01", periods=5))
    v = risk_adjusted_verdict(alternating_curve(*CALM, days=5), flat)
    assert v["comparable"] is False
    assert v["better_risk_adjusted"] is None
    assert v["benchmark_sharpe"] is None
    assert v["cagr_difference"] is not None


def test_verdict_measures_the_benchmark_over_the_strategys_dates_only():
    # The benchmark's series starts 100 days earlier, with a crash the strategy never faced.
    crash = alternating_curve(-0.03, -0.01, days=101, start="2019-08-14")
    later = alternating_curve(*WILD, start=crash.index[-1].strftime("%Y-%m-%d"))
    bench = pd.concat([crash, later.iloc[1:] / 100.0 * crash.iloc[-1]])
    strategy = alternating_curve(*CALM, start=crash.index[-1].strftime("%Y-%m-%d"))
    v = risk_adjusted_verdict(strategy, bench)
    assert v["benchmark_sharpe"] == pytest.approx(alternating_sharpe(*WILD))


@pytest.mark.parametrize("key", sorted(STRATEGIES))
def test_every_strategy_runs_end_to_end(key):
    req = BacktestRequest(
        strategy=key,
        universe={"preset": "multi_asset"},
        start_date=date(2018, 1, 1),
        end_date=date(2023, 12, 31),
        risk_level=3,
    )
    report = run_backtest(req, SyntheticPriceStore())
    assert len(report["series"]["dates"]) == len(report["series"]["equity"])
    assert report["summary"]["end_value"] > 0
    assert report["benchmark"]["symbol"] == "SPY"


def test_missing_data_is_a_clear_error():
    class EmptyStore:
        def load(self, symbols, start, end):
            return synthetic_bars(["SPY"], start, end)

    req = BacktestRequest(
        strategy="fixed_weights",
        universe={"symbols": ["ZZZZ"]},
        start_date=date(2020, 1, 1),
        end_date=date(2021, 1, 1),
    )
    with pytest.raises(BacktestError, match="ZZZZ"):
        run_backtest(req, EmptyStore())


def test_request_validation():
    with pytest.raises(ValueError):
        BacktestRequest(
            strategy="momentum",
            universe={"symbols": ["bad symbol!"]},
            start_date=date(2020, 1, 1),
            end_date=date(2021, 1, 1),
        )
    with pytest.raises(ValueError):
        BacktestRequest(
            strategy="momentum",
            universe={"preset": "us_size"},
            start_date=date(2021, 1, 1),
            end_date=date(2020, 1, 1),
        )


# The ten-level dial (#22): label, max per symbol, volatility target, cash floor.
TEN_LEVELS = {
    1: ("Preservation", 0.20, 0.04, 0.10),
    2: ("Preservation", 0.25, 0.06, 0.05),
    3: ("Conservative", 0.30, 0.08, 0.0),
    4: ("Conservative", 0.35, 0.10, 0.0),
    5: ("Moderate", 0.40, 0.12, 0.0),
    6: ("Moderate", 0.50, 0.15, 0.0),
    7: ("Growth", 0.65, 0.18, 0.0),
    8: ("Growth", 0.80, 0.22, 0.0),
    9: ("Aggressive", 1.0, 0.28, 0.0),
    10: ("Unconstrained", 1.0, None, 0.0),
}


def realized_vol(close: pd.Series, lookback: int = 63) -> float:
    return float(close.pct_change().iloc[-lookback:].dropna().std(ddof=1)) * math.sqrt(252)


def test_the_dial_has_ten_levels():
    assert sorted(RISK_PRESETS) == list(range(1, 11))


@pytest.mark.parametrize("level", sorted(TEN_LEVELS))
def test_each_risk_level_applies_its_cap_volatility_target_and_cash_floor(level):
    label, cap, target, cash = TEN_LEVELS[level]
    name, settings = RISK_PRESETS[level]
    assert name == label
    wanted = pd.Series({"A": 1.0})

    # A calm symbol never reaches the volatility target: only the cap and the cash floor bind.
    calm = synthetic_bars(["A"], date(2020, 1, 1), date(2020, 12, 31), annual_vol=0.01).close
    assert apply_risk(wanted, calm, settings)["A"] == pytest.approx(cap * (1 - cash))

    # A wild one breaches every level's target, so exposure scales down to it.
    wild = synthetic_bars(["A"], date(2020, 1, 1), date(2020, 12, 31), annual_vol=0.60).close
    vol = realized_vol(wild["A"]) * cap
    scale = 1.0 if target is None else min(1.0, target / vol)
    assert target is None or scale < 1.0
    assert apply_risk(wanted, wild, settings)["A"] == pytest.approx(cap * scale * (1 - cash))


def test_old_five_level_presets_are_kept_for_saved_backtests():
    old = {level: (label, s.model_dump()) for level, (label, s) in LEGACY_RISK_PRESETS.items()}
    base = {"vol_lookback_days": 63}
    assert old == {
        1: (
            "Preservation",
            {**base, "max_position_weight": 0.25, "target_volatility": 0.06, "cash_buffer": 0.05},
        ),
        2: (
            "Conservative",
            {**base, "max_position_weight": 0.35, "target_volatility": 0.10, "cash_buffer": 0.0},
        ),
        3: (
            "Moderate",
            {**base, "max_position_weight": 0.50, "target_volatility": 0.15, "cash_buffer": 0.0},
        ),
        4: (
            "Growth",
            {**base, "max_position_weight": 1.0, "target_volatility": 0.22, "cash_buffer": 0.0},
        ),
        5: (
            "Unconstrained",
            {**base, "max_position_weight": 1.0, "target_volatility": None, "cash_buffer": 0.0},
        ),
    }


def make_request(**kwargs) -> BacktestRequest:
    return BacktestRequest(
        strategy="momentum",
        universe={"preset": "multi_asset"},
        start_date=date(2020, 1, 1),
        end_date=date(2021, 1, 1),
        **kwargs,
    )


def test_risk_level_defaults_to_moderate_and_accepts_one_to_ten():
    assert make_request().risk_level == 5
    assert make_request().risk_settings() == RISK_PRESETS[5][1]
    assert make_request(risk_level=10).risk_settings() == RISK_PRESETS[10][1]
    for bad in (0, 11):
        with pytest.raises(ValueError):
            make_request(risk_level=bad)


def test_explicit_risk_settings_override_the_level():
    explicit = RiskSettings(max_position_weight=0.33)
    assert make_request(risk_level=2, risk=explicit).risk_settings() == explicit


def test_legacy_risk_level_needs_the_explicit_settings_it_stands_for():
    old = LEGACY_RISK_PRESETS[3][1]
    marked = make_request(risk_level=3, risk=old, legacy_risk_level=3)
    assert marked.risk_settings() == old
    with pytest.raises(ValueError, match="legacy_risk_level"):
        make_request(risk_level=3, legacy_risk_level=3)
    with pytest.raises(ValueError, match="legacy_risk_level"):
        make_request(risk_level=3, risk=LEGACY_RISK_PRESETS[2][1], legacy_risk_level=3)
    with pytest.raises(ValueError):
        make_request(risk=old, legacy_risk_level=6)
