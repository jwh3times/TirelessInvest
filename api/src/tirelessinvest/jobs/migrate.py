"""Apply pending schema migrations. Run with `python -m tirelessinvest.jobs.migrate`.

Railway runs this as the pre-deploy command of both services, so a release's migrations land
before its code takes traffic (docs/adr/0001-railway-applies-migrations-at-deploy.md). It records
each migration in the Supabase CLI's own history table, so `supabase migration list` agrees.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from ..config import get_settings

# The Supabase CLI's migration filename: `<digits>_<name>.sql`.
MIGRATION_FILE = re.compile(r"^([0-9]+)_(.*)\.sql$")

# The Postgres advisory lock a run holds, so the two services' pre-deploy runs take turns. Any
# fixed number would do; this one spells "TIMIGRAT" in ASCII.
MIGRATION_LOCK = 0x54494D4947524154

# The CLI's history table, created the way the CLI creates it.
CREATE_HISTORY = (
    "create schema if not exists supabase_migrations",
    "create table if not exists supabase_migrations.schema_migrations"
    " (version text not null primary key)",
    "alter table supabase_migrations.schema_migrations add column if not exists statements text[]",
    "alter table supabase_migrations.schema_migrations add column if not exists name text",
)


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path


@dataclass(frozen=True)
class MigrationRun:
    applied: list[str] = field(default_factory=list)
    # Recorded in the database but absent from the folder: an older image than the schema, as
    # in an emergency rollback. Migrations are additive, so the older code still works.
    unknown: list[str] = field(default_factory=list)


def find_migrations(folder: Path) -> list[Migration]:
    found = []
    for path in folder.iterdir():
        match = MIGRATION_FILE.match(path.name)
        if match:
            found.append(Migration(match[1], match[2], path))
    return sorted(found, key=lambda migration: migration.path.name)


def recorded_versions(conn: psycopg.Connection) -> set[str]:
    exists = conn.execute("select to_regclass('supabase_migrations.schema_migrations')").fetchone()
    if exists[0] is None:
        return set()
    rows = conn.execute("select version from supabase_migrations.schema_migrations")
    return {row[0] for row in rows}


def apply_migrations(database_url: str, folder: Path, *, dry_run: bool = False) -> MigrationRun:
    """Apply the folder's unrecorded migrations in filename order, each in its own transaction,
    stopping at the first failure. With `dry_run`, `applied` lists what would be applied and the
    database is left untouched."""
    applied = []
    with psycopg.connect(database_url, autocommit=True) as conn:
        if not dry_run:
            # Held until the connection closes, which releases it even if a migration fails.
            conn.execute("select pg_advisory_lock(%s)", (MIGRATION_LOCK,))
            for statement in CREATE_HISTORY:
                conn.execute(statement)
        done = recorded_versions(conn)
        migrations = find_migrations(folder)
        unknown = sorted(done - {migration.version for migration in migrations})
        for migration in migrations:
            if migration.version in done:
                continue
            if dry_run:
                applied.append(migration.version)
                continue
            sql = migration.path.read_text(encoding="utf-8")
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "insert into supabase_migrations.schema_migrations (version, name, statements)"
                    " values (%s, %s, %s)",
                    (migration.version, migration.name, [sql]),
                )
            applied.append(migration.version)
    return MigrationRun(applied=applied, unknown=unknown)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dir",
        type=Path,
        default=Path(os.environ.get("MIGRATIONS_DIR", "supabase/migrations")),
        help="folder of <digits>_<name>.sql files; default $MIGRATIONS_DIR or supabase/migrations",
    )
    parser.add_argument("--dry-run", action="store_true", help="list pending migrations only")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.dir.is_dir():
        logging.error("migrations folder %s does not exist", args.dir)
        return 1
    try:
        run = apply_migrations(get_settings().database_url, args.dir, dry_run=args.dry_run)
    except psycopg.Error as error:
        logging.error("migration failed: %s", error)
        return 1
    for version in run.unknown:
        logging.warning("database has migration %s, which this image does not; continuing", version)
    verb = "pending" if args.dry_run else "applied"
    logging.info("%s %d migration(s): %s", verb, len(run.applied), ", ".join(run.applied) or "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
