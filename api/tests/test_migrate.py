"""The migration runner Railway calls before each deploy (ADR 0001)."""

from __future__ import annotations

import threading

import psycopg
import pytest
from conftest import MIGRATIONS

from tirelessinvest.jobs.migrate import MIGRATION_LOCK, apply_migrations


def recorded(url: str) -> list[tuple[str, str]]:
    """What `supabase migration list` reads: the CLI's own history table."""
    with psycopg.connect(url) as conn:
        return conn.execute(
            "select version, name from supabase_migrations.schema_migrations order by version"
        ).fetchall()


def test_fresh_database_gets_every_migration_recorded(empty_database_url):
    run = apply_migrations(empty_database_url, MIGRATIONS)

    assert run.applied == ["20261110000000"]
    assert recorded(empty_database_url) == [("20261110000000", "init")]
    with psycopg.connect(empty_database_url) as conn:
        assert conn.execute("select to_regclass('public.backtests')").fetchone()[0] == "backtests"


def test_second_run_applies_nothing(empty_database_url):
    apply_migrations(empty_database_url, MIGRATIONS)

    run = apply_migrations(empty_database_url, MIGRATIONS)

    assert run.applied == []
    assert recorded(empty_database_url) == [("20261110000000", "init")]


def write_migrations(folder, files: dict[str, str]):
    folder.mkdir(parents=True, exist_ok=True)
    for name, sql in files.items():
        (folder / name).write_text(sql, encoding="utf-8")
    return folder


def test_failing_migration_stops_the_run_at_the_last_good_one(empty_database_url, tmp_path):
    folder = write_migrations(
        tmp_path,
        {
            "1_good.sql": "create table public.one (id int);",
            "2_bad.sql": "create table public.two (id int); select * from public.missing;",
            "3_later.sql": "create table public.three (id int);",
        },
    )

    with pytest.raises(psycopg.Error):
        apply_migrations(empty_database_url, folder)

    assert recorded(empty_database_url) == [("1", "good")]
    with psycopg.connect(empty_database_url) as conn:
        tables = conn.execute(
            "select to_regclass('public.one'), to_regclass('public.two'),"
            " to_regclass('public.three')"
        ).fetchone()
    assert tables == ("one", None, None)


def test_migration_newer_than_the_image_is_reported_and_tolerated(empty_database_url, tmp_path):
    newer = write_migrations(
        tmp_path / "newer",
        {"1_one.sql": "create table public.one (id int);", "2_two.sql": "select 1;"},
    )
    apply_migrations(empty_database_url, newer)
    older = write_migrations(tmp_path / "older", {"1_one.sql": "create table public.one (id int);"})

    run = apply_migrations(empty_database_url, older)

    assert run.applied == []
    assert run.unknown == ["2"]


def test_dry_run_reports_pending_and_changes_nothing(empty_database_url):
    run = apply_migrations(empty_database_url, MIGRATIONS, dry_run=True)

    assert run.applied == ["20261110000000"]
    with psycopg.connect(empty_database_url) as conn:
        assert conn.execute(
            "select to_regclass('public.backtests'),"
            " to_regclass('supabase_migrations.schema_migrations')"
        ).fetchone() == (None, None)


def test_run_waits_while_another_run_holds_the_lock(empty_database_url):
    result = {}
    with psycopg.connect(empty_database_url, autocommit=True) as holder:
        holder.execute("select pg_advisory_lock(%s)", (MIGRATION_LOCK,))
        runner = threading.Thread(
            target=lambda: result.update(run=apply_migrations(empty_database_url, MIGRATIONS))
        )
        runner.start()
        runner.join(timeout=1)
        assert runner.is_alive(), "the run went ahead while the lock was held"
        holder.execute("select pg_advisory_unlock(%s)", (MIGRATION_LOCK,))
    runner.join(timeout=30)

    assert result["run"].applied == ["20261110000000"]
