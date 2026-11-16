from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import close_pool
from .routes import account, admin, backtests, catalog


def running_commit() -> str | None:
    """The commit Railway built this deploy from. The version is the tag on that commit: Railway
    builds before the tag exists, so the API cannot know its own version (ADR 0001)."""
    return os.environ.get("RAILWAY_GIT_COMMIT_SHA") or None


def _without_value_error_prefix(error: dict) -> dict:
    """Pydantic writes a validator's `ValueError` as "Value error, <text>"; the Lab shows `msg`
    as it comes, so give it the validator's own text."""
    cause = (error.get("ctx") or {}).get("error")
    if error.get("type") == "value_error" and isinstance(cause, ValueError):
        return {**error, "msg": str(cause)}
    return error


async def _request_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default handler, with the messages unprefixed.
    errors = [_without_value_error_prefix(e) for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    close_pool()


def create_app() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    app = FastAPI(title="TirelessInvest API", version=running_commit() or "dev", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_exception_handler(RequestValidationError, _request_validation_error)

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        return {"status": "ok", "commit": running_commit()}

    app.include_router(catalog.router)
    app.include_router(account.router)
    app.include_router(backtests.router)
    app.include_router(admin.router)
    return app


app = create_app()
