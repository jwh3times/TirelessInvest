from datetime import date

import numpy as np
import pandas as pd
import pytest

from tirelessinvest.engine.backtest import BacktestError, BacktestRequest, run_backtest
from tirelessinvest.engine.data import Bars, SyntheticPriceStore, synthetic_bars
from tirelessinvest.engine.metrics import performance
from tirelessinvest.engine.risk import RiskSettings, apply_risk
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
