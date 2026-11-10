from .base import Rebalance, Strategy, StrategyParams
from .library import FixedWeights, MeanReversion, Momentum, SmaTrend

STRATEGIES: dict[str, type[Strategy]] = {
    cls.key: cls for cls in (FixedWeights, Momentum, SmaTrend, MeanReversion)
}


def build_strategy(key: str, params: dict | None = None) -> Strategy:
    try:
        cls = STRATEGIES[key]
    except KeyError as exc:
        raise ValueError(f"unknown strategy '{key}'") from exc
    return cls(cls.params_model.model_validate(params or {}))


__all__ = ["STRATEGIES", "Rebalance", "Strategy", "StrategyParams", "build_strategy"]
