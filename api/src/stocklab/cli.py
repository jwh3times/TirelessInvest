"""Operator commands. Usage: python -m stocklab.cli make-admin you@example.com"""

from __future__ import annotations

import argparse
import sys

from .db import close_pool, connection


def make_admin(email: str, force: bool) -> int:
    with connection() as conn:
        existing = conn.execute(
            "select email from auth.users where raw_app_meta_data ->> 'role' = 'admin'"
        ).fetchall()
        others = [r["email"] for r in existing if r["email"] != email]
        if others and not force:
            print(f"refusing: admin already exists ({', '.join(others)}). Use --force.")
            return 1
        row = conn.execute(
            """
            update auth.users
            set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || '{"role": "admin"}'
            where email = %s returning id
            """,
            (email,),
        ).fetchone()
        if row is None:
            print(f"no user with email {email}; sign up in the app first")
            return 1
    print(f"{email} is now admin. Sign out and back in so your token picks up the role.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="stocklab")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("make-admin", help="grant the admin role to an existing user")
    p.add_argument("email")
    p.add_argument("--force", action="store_true", help="allow more than one admin")
    args = parser.parse_args()
    try:
        if args.command == "make-admin":
            return make_admin(args.email, args.force)
    finally:
        close_pool()
    return 2


if __name__ == "__main__":
    sys.exit(main())
