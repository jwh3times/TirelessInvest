from __future__ import annotations

import time
from functools import lru_cache
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Jsonb
from pydantic import Field

from ..access import flags_for, permissions_for, require_permission
from ..auth import CurrentUser, current_user
from ..config import get_settings
from ..db import connection
from ..engine.backtest import BacktestError, BacktestRequest, run_backtest
from ..engine.data import PriceStore, SyntheticPriceStore
from ..engine.strategies import STRATEGIES
from ..market.alpaca import AlpacaClient, AlpacaError
from ..market.store import PostgresPriceStore

router = APIRouter(prefix="/backtests", tags=["backtests"])

SUMMARY_KEYS = ("total_return", "cagr", "volatility", "sharpe", "max_drawdown", "end_value")


class CreateBacktest(BacktestRequest):
    name: str | None = Field(None, max_length=120)


@lru_cache
def get_price_store() -> PriceStore:
    s = get_settings()
    if s.price_source == "synthetic":
        return SyntheticPriceStore()
    alpaca = None
    if s.alpaca_configured and s.backfill_on_demand:
        alpaca = AlpacaClient(
            s.alpaca_key_id, s.alpaca_secret_key, base_url=s.alpaca_data_url, feed=s.alpaca_feed
        )
    return PostgresPriceStore(alpaca, s.backfill_floor)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_backtest(
    body: CreateBacktest,
    user: CurrentUser = Depends(require_permission("backtest:run")),
    store: PriceStore = Depends(get_price_store),
) -> dict:
    # Plain `def` endpoint: FastAPI runs it in a worker thread, so a slow backtest
    # doesn't block the event loop.
    strategy_cls = STRATEGIES.get(body.strategy)
    if strategy_cls is None:
        raise HTTPException(422, "unknown strategy")
    if strategy_cls.feature_flag and not flags_for(user).get(strategy_cls.feature_flag, False):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this strategy is not enabled for you")
    if body.universe.symbols is not None and "backtest:custom_universe" not in permissions_for(
        user
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "custom symbol lists need permission")

    request = BacktestRequest.model_validate(body.model_dump(exclude={"name"}))
    started = time.perf_counter()
    try:
        report = run_backtest(request, store)
    except AlpacaError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"market data error: {exc}") from exc
    except (BacktestError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    duration_ms = int((time.perf_counter() - started) * 1000)

    summary = {k: report["summary"].get(k) for k in SUMMARY_KEYS}
    summary["benchmark_cagr"] = report["benchmark"]["summary"].get("cagr")
    with connection() as conn:
        row = conn.execute(
            """
            insert into public.backtests
              (user_id, name, strategy, request, summary, report, duration_ms)
            values (%s, %s, %s, %s, %s, %s, %s)
            returning id, created_at
            """,
            (
                user.id,
                body.name,
                body.strategy,
                Jsonb(request.model_dump(mode="json")),
                Jsonb(summary),
                Jsonb(report),
                duration_ms,
            ),
        ).fetchone()
    return {
        "id": str(row["id"]),
        "name": body.name,
        "created_at": row["created_at"],
        "duration_ms": duration_ms,
        "report": report,
    }


@router.get("")
def list_backtests(
    user: CurrentUser = Depends(current_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """
            select id, name, strategy, summary, created_at, duration_ms,
                   request -> 'universe' as universe,
                   request ->> 'start_date' as start_date,
                   request ->> 'end_date' as end_date,
                   request ->> 'starting_cash' as starting_cash
            from public.backtests where user_id = %s
            order by created_at desc limit %s offset %s
            """,
            (user.id, limit, offset),
        ).fetchall()
    return [{**r, "id": str(r["id"])} for r in rows]


def _owned(conn, backtest_id: UUID, user: CurrentUser) -> dict:
    row = conn.execute("select * from public.backtests where id = %s", (backtest_id,)).fetchone()
    # 404 (not 403) for other people's backtests so IDs can't be probed.
    if row is None or (row["user_id"] != user.id and not user.is_admin):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "backtest not found")
    return row


@router.get("/{backtest_id}")
def get_backtest(backtest_id: UUID, user: CurrentUser = Depends(current_user)) -> dict:
    with connection() as conn:
        row = _owned(conn, backtest_id, user)
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "created_at": row["created_at"],
        "duration_ms": row["duration_ms"],
        "report": row["report"],
    }


@router.delete("/{backtest_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backtest(backtest_id: UUID, user: CurrentUser = Depends(current_user)) -> None:
    with connection() as conn:
        row = _owned(conn, backtest_id, user)
        conn.execute("delete from public.backtests where id = %s", (row["id"],))
