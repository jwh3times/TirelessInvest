"""Integration-test fixtures. Set TEST_DATABASE_URL to a Postgres server you can create
databases on (e.g. postgresql://postgres@127.0.0.1:5432/postgres); otherwise the
integration tests are skipped and only the pure engine tests run."""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path

import jwt
import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[2]
JWT_SECRET = "test-secret-at-least-32-characters-long!!"
SUPABASE_URL = "http://supabase.test"


MIGRATIONS = ROOT / "supabase" / "migrations"


def _admin_url() -> str:
    admin_url = os.environ.get("TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("TEST_DATABASE_URL not set")
    return admin_url


def _create_stubbed_database(admin_url: str) -> tuple[str, str]:
    """Create an empty database holding only the Supabase stand-ins; return (name, url)."""
    name = f"tirelessinvest_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'create database "{name}"')
    url = admin_url.rsplit("/", 1)[0] + f"/{name}"
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute((Path(__file__).parent / "supabase_stub.sql").read_text())
    return name, url


def _drop_database(admin_url: str, name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'drop database "{name}" with (force)')


@pytest.fixture(scope="session")
def database_url():
    admin_url = _admin_url()
    name, url = _create_stubbed_database(admin_url)
    # The same runner Railway's pre-deploy step uses, so every integration test exercises it.
    from tirelessinvest.jobs.migrate import apply_migrations

    apply_migrations(url, MIGRATIONS)
    yield url
    from tirelessinvest.db import close_pool

    close_pool()
    _drop_database(admin_url, name)


@pytest.fixture
def empty_database_url():
    """A database with the Supabase stand-ins and no migrations applied, dropped afterwards."""
    admin_url = _admin_url()
    name, url = _create_stubbed_database(admin_url)
    yield url
    _drop_database(admin_url, name)


@pytest.fixture(scope="session")
def client(database_url):
    os.environ.update(
        DATABASE_URL=database_url,
        SUPABASE_URL=SUPABASE_URL,
        SUPABASE_JWT_SECRET=JWT_SECRET,
        PRICE_SOURCE="synthetic",
    )
    from fastapi.testclient import TestClient

    from tirelessinvest.auth import get_verifier
    from tirelessinvest.config import get_settings
    from tirelessinvest.routes.backtests import get_price_store

    get_settings.cache_clear()
    get_verifier.cache_clear()
    get_price_store.cache_clear()
    from tirelessinvest.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def db(database_url):
    with psycopg.connect(database_url, autocommit=True) as conn:
        yield conn


def make_user(conn: psycopg.Connection, *, admin: bool = False) -> tuple[str, str]:
    """Insert a user (firing the sign-up trigger) and return (user_id, bearer token)."""
    email = f"user-{uuid.uuid4().hex[:8]}@example.test"
    meta = '{"role": "admin"}' if admin else "{}"
    user_id = conn.execute(
        "insert into auth.users (email, raw_app_meta_data) values (%s, %s::jsonb) returning id",
        (email, meta),
    ).fetchone()[0]
    return str(user_id), token_for(
        str(user_id), email, app_metadata={"role": "admin"} if admin else {}
    )


def token_for(
    user_id: str,
    email: str,
    *,
    app_metadata: dict,
    user_metadata: dict | None = None,
    secret: str = JWT_SECRET,
    expires_in: int = 3600,
) -> str:
    now = int(time.time())
    claims = {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "iss": f"{SUPABASE_URL}/auth/v1",
        "iat": now,
        "exp": now + expires_in,
        "app_metadata": app_metadata,
        "user_metadata": user_metadata or {},
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
