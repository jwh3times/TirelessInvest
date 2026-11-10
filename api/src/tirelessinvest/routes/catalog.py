from __future__ import annotations

from fastapi import APIRouter, Depends

from ..access import flags_for, permissions_for
from ..auth import CurrentUser, current_user
from ..engine.risk import RISK_PRESETS
from ..engine.simulator import Costs
from ..engine.strategies import STRATEGIES
from ..engine.universes import UNIVERSES

router = APIRouter(tags=["catalog"])


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "is_admin": user.is_admin,
        "permissions": sorted(permissions_for(user)),
        "flags": flags_for(user),
    }


@router.get("/catalog")
def catalog(user: CurrentUser = Depends(current_user)) -> dict:
    """Everything the UI needs to build a backtest form."""
    flags = flags_for(user)
    return {
        "strategies": [
            {
                "key": cls.key,
                "label": cls.label,
                "description": cls.description,
                "default_rebalance": cls.default_rebalance,
                "params_schema": cls.params_model.model_json_schema(),
                "available": cls.feature_flag is None or flags.get(cls.feature_flag, False),
            }
            for cls in STRATEGIES.values()
        ],
        "universes": [
            {
                "key": u.key,
                "label": u.label,
                "description": u.description,
                "symbols": list(u.symbols),
                "survivorship_biased": u.survivorship_biased,
            }
            for u in UNIVERSES.values()
        ],
        "risk_levels": [
            {"level": level, "label": label, "settings": settings.model_dump()}
            for level, (label, settings) in RISK_PRESETS.items()
        ],
        "default_costs": Costs().model_dump(),
    }
