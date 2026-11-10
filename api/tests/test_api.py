"""API + database integration tests (need TEST_DATABASE_URL; see conftest.py)."""

from __future__ import annotations

from datetime import date

import pandas as pd
import psycopg
import pytest
from conftest import auth, make_user, token_for

BACKTEST = {
    "strategy": "momentum",
    "universe": {"preset": "multi_asset"},
    "start_date": "2019-01-01",
    "end_date": "2023-12-31",
    "starting_cash": 25_000,
    "risk_level": 3,
}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_requests_without_valid_token_are_rejected(client, db):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers=auth("garbage")).status_code == 401
    user_id, _ = make_user(db)
    wrong_key = token_for(
        user_id,
        "x@example.test",
        app_metadata={},
        secret="another-secret-that-is-32-characters-long",
    )
    assert client.get("/me", headers=auth(wrong_key)).status_code == 401
    expired = token_for(user_id, "x@example.test", app_metadata={}, expires_in=-60)
    assert client.get("/me", headers=auth(expired)).status_code == 401


def test_user_metadata_cannot_grant_admin(client, db):
    """Users can edit their own user_metadata, so it must never confer the admin role."""
    user_id, _ = make_user(db)
    sneaky = token_for(user_id, "x@example.test", app_metadata={}, user_metadata={"role": "admin"})
    me = client.get("/me", headers=auth(sneaky)).json()
    assert me["is_admin"] is False
    assert client.get("/admin/users", headers=auth(sneaky)).status_code == 403


def test_signup_grants_default_permissions(client, db):
    _, token = make_user(db)
    me = client.get("/me", headers=auth(token)).json()
    assert me["permissions"] == ["backtest:run"]
    assert me["flags"] == {"live_trading": False, "strategy.mean_reversion": False}


def test_backtest_lifecycle_and_isolation(client, db):
    _, alice = make_user(db)
    _, bob = make_user(db)
    created = client.post("/backtests", json={**BACKTEST, "name": "first"}, headers=auth(alice))
    assert created.status_code == 201, created.text
    body = created.json()
    report = body["report"]
    assert report["summary"]["start_value"] == 25_000
    assert len(report["series"]["dates"]) == len(report["series"]["equity"])

    listed = client.get("/backtests", headers=auth(alice)).json()
    assert [b["id"] for b in listed] == [body["id"]]
    assert listed[0]["summary"]["cagr"] is not None

    # Bob can't see or delete Alice's backtest, and gets 404 rather than 403.
    assert client.get("/backtests", headers=auth(bob)).json() == []
    assert client.get(f"/backtests/{body['id']}", headers=auth(bob)).status_code == 404
    assert client.delete(f"/backtests/{body['id']}", headers=auth(bob)).status_code == 404

    assert client.delete(f"/backtests/{body['id']}", headers=auth(alice)).status_code == 204
    assert client.get("/backtests", headers=auth(alice)).json() == []


def test_invalid_backtest_is_422(client, db):
    _, token = make_user(db)
    bad = {**BACKTEST, "end_date": "2018-01-01"}
    assert client.post("/backtests", json=bad, headers=auth(token)).status_code == 422
    bad = {**BACKTEST, "strategy": "nope"}
    assert client.post("/backtests", json=bad, headers=auth(token)).status_code == 422


def test_custom_universe_needs_permission_granted_by_admin(client, db):
    user_id, token = make_user(db)
    _, admin = make_user(db, admin=True)
    custom = {**BACKTEST, "universe": {"symbols": ["aapl", "msft"]}}
    assert client.post("/backtests", json=custom, headers=auth(token)).status_code == 403

    r = client.put(
        f"/admin/users/{user_id}/permissions",
        headers=auth(admin),
        json={"permissions": ["backtest:run", "backtest:custom_universe"]},
    )
    assert r.status_code == 200, r.text
    assert client.post("/backtests", json=custom, headers=auth(token)).status_code == 201

    # Removing backtest:run locks the user out of running anything.
    client.put(f"/admin/users/{user_id}/permissions", headers=auth(admin), json={"permissions": []})
    assert client.post("/backtests", json=BACKTEST, headers=auth(token)).status_code == 403


def test_flagged_strategy_respects_global_flag_and_user_override(client, db):
    user_id, token = make_user(db)
    _, admin = make_user(db, admin=True)
    mr = {**BACKTEST, "strategy": "mean_reversion"}
    assert client.post("/backtests", json=mr, headers=auth(token)).status_code == 403

    catalog = client.get("/catalog", headers=auth(token)).json()
    assert {s["key"]: s["available"] for s in catalog["strategies"]}["mean_reversion"] is False

    r = client.put(
        f"/admin/flags/strategy.mean_reversion/overrides/{user_id}",
        json={"enabled": True},
        headers=auth(admin),
    )
    assert r.status_code == 200
    assert client.post("/backtests", json=mr, headers=auth(token)).status_code == 201

    flags = client.get("/admin/flags", headers=auth(admin)).json()
    mr_flag = next(f for f in flags if f["key"] == "strategy.mean_reversion")
    assert mr_flag["enabled"] is False and mr_flag["overrides"][0]["user_id"] == user_id

    client.delete(f"/admin/flags/strategy.mean_reversion/overrides/{user_id}", headers=auth(admin))
    assert client.post("/backtests", json=mr, headers=auth(token)).status_code == 403


def test_admin_endpoints(client, db):
    _, user = make_user(db)
    _, admin = make_user(db, admin=True)
    for path in ("/admin/users", "/admin/flags", "/admin/permissions", "/admin/audit"):
        assert client.get(path, headers=auth(user)).status_code == 403
        assert client.get(path, headers=auth(admin)).status_code == 200

    r = client.post(
        "/admin/flags",
        headers=auth(admin),
        json={"key": "ui.dark_charts", "description": "Try dark charts"},
    )
    assert r.status_code == 201
    assert (
        client.post(
            "/admin/flags",
            headers=auth(admin),
            json={"key": "ui.dark_charts", "description": "dup"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/admin/flags", headers=auth(admin), json={"key": "Bad Key", "description": "x"}
        ).status_code
        == 422
    )
    r = client.patch("/admin/flags/ui.dark_charts", headers=auth(admin), json={"enabled": True})
    assert r.json()["enabled"] is True
    assert client.get("/me", headers=auth(user)).json()["flags"]["ui.dark_charts"] is True
    assert client.delete("/admin/flags/ui.dark_charts", headers=auth(admin)).status_code == 204

    actions = [a["action"] for a in client.get("/admin/audit", headers=auth(admin)).json()]
    assert {"flag.create", "flag.update", "flag.delete"} <= set(actions)

    users = client.get("/admin/users", headers=auth(admin)).json()
    assert any(u["is_admin"] for u in users)


def test_client_roles_cannot_read_tables_directly(database_url):
    """RLS + revoked grants: Supabase's public REST API (anon/authenticated) sees nothing."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        for role in ("anon", "authenticated"):
            conn.execute(f"set role {role}")
            for table in ("backtests", "feature_flags", "user_permissions", "prices_daily"):
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(f"select * from public.{table}")
            conn.execute("reset role")


class FakeAlpaca:
    def __init__(self):
        self.calls = []

    def daily_bars(self, symbols, start, end):
        self.calls.append((tuple(symbols), start))
        dates = pd.bdate_range(start, end)[:30]
        known = [s for s in symbols if s != "TYPO"]
        return pd.DataFrame(
            [(s, d.date(), 10.0, 11.0, 9.0, 10.5, 1000) for s in known for d in dates],
            columns=["symbol", "date", "open", "high", "low", "close", "volume"],
        )


def test_price_store_backfills_once_and_skips_unknown_symbols(client, db):
    from stocklab.market.store import PostgresPriceStore

    alpaca = FakeAlpaca()
    store = PostgresPriceStore(alpaca, backfill_floor=date(2016, 1, 1))
    bars = store.load(["AAA", "TYPO"], date(2020, 1, 1), date(2020, 3, 1))
    assert bars.close["AAA"].notna().sum() == 30
    assert bars.close["TYPO"].isna().all()
    tracked = {r[0] for r in db.execute("select symbol from public.symbols")}
    assert "AAA" in tracked and "TYPO" not in tracked

    # Already backfilled from 2020-01-01: loading the same range again doesn't refetch AAA.
    store.load(["AAA"], date(2020, 1, 1), date(2020, 3, 1))
    assert all("AAA" not in call[0] for call in alpaca.calls[1:])
    # Reloading is idempotent (upsert, no duplicates).
    store.refresh_all()
    count = db.execute("select count(*) from public.prices_daily where symbol='AAA'").fetchone()
    assert count[0] == 30


def test_make_admin_refuses_second_admin(client, db, capsys):
    from stocklab.cli import make_admin

    make_user(db, admin=True)
    _, _ = make_user(db)
    email = db.execute(
        "select email from auth.users where raw_app_meta_data->>'role' is null limit 1"
    ).fetchone()[0]
    assert make_admin(email, force=False) == 1
    assert "refusing" in capsys.readouterr().out
