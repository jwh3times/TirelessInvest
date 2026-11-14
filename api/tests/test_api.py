"""API + database integration tests (need TEST_DATABASE_URL; see conftest.py)."""

from __future__ import annotations

import shutil
from datetime import date

import pandas as pd
import psycopg
import pytest
from conftest import MIGRATIONS, auth, make_user, token_for
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from tirelessinvest.engine.backtest import BacktestRequest, run_backtest
from tirelessinvest.engine.data import SyntheticPriceStore
from tirelessinvest.engine.risk import LEGACY_RISK_PRESETS
from tirelessinvest.jobs.migrate import apply_migrations

BACKTEST = {
    "strategy": "momentum",
    "universe": {"preset": "multi_asset"},
    "start_date": "2019-01-01",
    "end_date": "2023-12-31",
    "starting_cash": 25_000,
    "risk_level": 3,
}


def test_health_reports_the_running_commit(client, monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "fab06b3e1f")
    assert client.get("/health").json() == {"status": "ok", "commit": "fab06b3e1f"}


def test_health_reports_no_commit_outside_railway(client, monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    assert client.get("/health").json() == {"status": "ok", "commit": None}


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


@pytest.mark.parametrize("invited", [False, True], ids=["created", "invited"])
def test_new_user_receives_default_permissions(client, db, invited):
    """Sign-up is closed, so accounts come from Supabase invitations (or the dashboard). Either
    way the user is a new auth.users row, and gets the defaults."""
    _, token = make_user(db, invited=invited)
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


VERDICT_KEYS = {
    "comparable",
    "better_risk_adjusted",
    "sharpe",
    "benchmark_sharpe",
    "cagr_difference",
}


def assert_well_formed_verdict(verdict: dict, summary: dict, benchmark: dict) -> None:
    assert set(verdict) == VERDICT_KEYS
    assert verdict["comparable"] is True
    assert verdict["sharpe"] == pytest.approx(summary["sharpe"])
    assert verdict["benchmark_sharpe"] == pytest.approx(benchmark["sharpe"])
    assert verdict["better_risk_adjusted"] is (summary["sharpe"] > benchmark["sharpe"])
    assert verdict["cagr_difference"] == pytest.approx(summary["cagr"] - benchmark["cagr"])


def test_backtest_report_carries_a_risk_adjusted_verdict(client, db):
    _, token = make_user(db)
    created = client.post("/backtests", json=BACKTEST, headers=auth(token))
    assert created.status_code == 201, created.text
    report = created.json()["report"]
    assert_well_formed_verdict(report["verdict"], report["summary"], report["benchmark"]["summary"])

    listed = client.get("/backtests", headers=auth(token)).json()
    assert listed[0]["verdict"] == report["verdict"]


def test_backtest_saved_before_the_verdict_still_shows_one(client, db):
    _, token = make_user(db)
    backtest_id = client.post("/backtests", json=BACKTEST, headers=auth(token)).json()["id"]
    # Make the row look like one saved before verdicts existed.
    db.execute(
        """
        update public.backtests
        set report = report - 'verdict', summary = summary - 'verdict'
        where id = %s
        """,
        (backtest_id,),
    )

    report = client.get(f"/backtests/{backtest_id}", headers=auth(token)).json()["report"]
    assert_well_formed_verdict(report["verdict"], report["summary"], report["benchmark"]["summary"])
    listed = client.get("/backtests", headers=auth(token)).json()
    assert listed[0]["verdict"] == report["verdict"]


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
    from tirelessinvest.market.store import PostgresPriceStore

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
    from tirelessinvest.cli import make_admin

    make_user(db, admin=True)
    _, _ = make_user(db)
    email = db.execute(
        "select email from auth.users where raw_app_meta_data->>'role' is null limit 1"
    ).fetchone()[0]
    assert make_admin(email, force=False) == 1
    assert "refusing" in capsys.readouterr().out


LEGACY_MIGRATION = "20261113000000_legacy_risk_levels.sql"


def old_scale_save(conn, user_id: str, **request) -> str:
    """Save a backtest the way the five-level dial did: `risk_level` alone, no explicit `risk`
    and no `legacy_risk_level` key, with the result that dial's preset produced."""
    saved = BacktestRequest.model_validate({**BACKTEST, **request}).model_dump(mode="json")
    del saved["legacy_risk_level"]
    run = dict(saved)
    if run["risk"] is None:
        run["risk"] = LEGACY_RISK_PRESETS[run["risk_level"]][1].model_dump(mode="json")
    report = run_backtest(BacktestRequest.model_validate(run), SyntheticPriceStore())
    del report["config"]["legacy_risk_level"]
    return insert_backtest(conn, user_id, saved, report["summary"], report)


def insert_backtest(conn, user_id: str, request: dict, summary: dict, report: dict) -> str:
    return conn.execute(
        """
        insert into public.backtests (user_id, strategy, request, summary, report, duration_ms)
        values (%s, %s, %s, %s, %s, 1) returning id
        """,
        (user_id, request["strategy"], Jsonb(request), Jsonb(summary), Jsonb(report)),
    ).fetchone()[0]


@pytest.fixture
def old_scale_database(empty_database_url, tmp_path):
    """A database migrated up to, but not including, the legacy-risk-level migration."""
    before = tmp_path / "before"
    before.mkdir()
    for path in MIGRATIONS.glob("*.sql"):
        if path.name < LEGACY_MIGRATION:
            shutil.copy(path, before / path.name)
    apply_migrations(empty_database_url, before)
    with psycopg.connect(empty_database_url, autocommit=True) as conn:
        user_id = conn.execute(
            "insert into auth.users (email) values ('old@example.test') returning id"
        ).fetchone()[0]
    return empty_database_url, str(user_id)


def saved_rows(url: str) -> dict:
    with psycopg.connect(url, row_factory=dict_row) as conn:
        rows = conn.execute("select id, request, summary, report from public.backtests").fetchall()
    return {row["id"]: row for row in rows}


def test_migration_rewrites_old_scale_requests_to_explicit_old_settings(old_scale_database):
    url, user_id = old_scale_database
    explicit = {
        "max_position_weight": 0.3,
        "target_volatility": None,
        "vol_lookback_days": 63,
        "cash_buffer": 0.0,
    }
    with psycopg.connect(url, autocommit=True) as conn:
        by_level = {level: old_scale_save(conn, user_id, risk_level=level) for level in range(1, 6)}
        explicit_id = old_scale_save(conn, user_id, risk_level=2, risk=explicit)
    before = saved_rows(url)

    apply_migrations(url, MIGRATIONS)

    after = saved_rows(url)
    for level, backtest_id in by_level.items():
        old = LEGACY_RISK_PRESETS[level][1].model_dump(mode="json")
        assert after[backtest_id]["request"] == {
            **before[backtest_id]["request"],
            "risk": old,
            "legacy_risk_level": level,
        }
        assert after[backtest_id]["report"]["config"]["legacy_risk_level"] == level
        assert after[backtest_id]["summary"] == before[backtest_id]["summary"]
    assert after[explicit_id] == before[explicit_id]


def test_old_scale_backtest_reruns_identically_after_the_migration(client, db, old_scale_database):
    url, old_user = old_scale_database
    with psycopg.connect(url, autocommit=True) as conn:
        old_id = old_scale_save(conn, old_user, risk_level=3)
    apply_migrations(url, MIGRATIONS)
    migrated = saved_rows(url)[old_id]

    # The migrated row, served by the API, shows it used the old scale.
    user_id, token = make_user(db)
    backtest_id = insert_backtest(
        db, user_id, migrated["request"], migrated["summary"], migrated["report"]
    )
    shown = client.get(f"/backtests/{backtest_id}", headers=auth(token)).json()["report"]
    assert shown["config"]["legacy_risk_level"] == 3
    [listed] = client.get("/backtests", headers=auth(token)).json()
    assert (listed["risk_level"], listed["legacy_risk_level"]) == (3, 3)

    # Re-running its request reproduces the original result, still marked legacy.
    rerun = client.post("/backtests", json=migrated["request"], headers=auth(token))
    assert rerun.status_code == 201, rerun.text
    report = rerun.json()["report"]
    assert report["summary"] == migrated["report"]["summary"]
    assert report["config"]["legacy_risk_level"] == 3
    newest = client.get("/backtests", headers=auth(token)).json()[0]
    assert newest["legacy_risk_level"] == 3


def test_new_backtests_carry_no_legacy_marker(client, db):
    _, token = make_user(db)
    created = client.post("/backtests", json={**BACKTEST, "risk_level": 10}, headers=auth(token))
    assert created.status_code == 201, created.text
    assert created.json()["report"]["config"]["legacy_risk_level"] is None
    [listed] = client.get("/backtests", headers=auth(token)).json()
    assert (listed["risk_level"], listed["legacy_risk_level"]) == (10, None)


def test_catalog_serves_the_ten_level_dial(client, db):
    _, token = make_user(db)
    levels = client.get("/catalog", headers=auth(token)).json()["risk_levels"]
    assert [(r["level"], r["label"]) for r in levels] == [
        (1, "Preservation"),
        (2, "Preservation"),
        (3, "Conservative"),
        (4, "Conservative"),
        (5, "Moderate"),
        (6, "Moderate"),
        (7, "Growth"),
        (8, "Growth"),
        (9, "Aggressive"),
        (10, "Unconstrained"),
    ]
    assert levels[4]["settings"] == {
        "max_position_weight": 0.4,
        "target_volatility": 0.12,
        "vol_lookback_days": 63,
        "cash_buffer": 0.0,
    }
