"""Permissions and feature flags, evaluated server-side on every request."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status

from .auth import CurrentUser, current_user
from .db import connection


def permissions_for(user: CurrentUser) -> set[str]:
    with connection() as conn:
        if user.is_admin:  # the admin implicitly holds every permission
            rows = conn.execute("select key from public.permissions").fetchall()
        else:
            rows = conn.execute(
                "select permission_key as key from public.user_permissions where user_id = %s",
                (user.id,),
            ).fetchall()
    return {r["key"] for r in rows}


def flags_for(user: CurrentUser) -> dict[str, bool]:
    """Effective flags: a per-user override wins over the global value."""
    with connection() as conn:
        rows = conn.execute(
            """
            select f.key, coalesce(o.enabled, f.enabled) as enabled
            from public.feature_flags f
            left join public.feature_flag_overrides o
              on o.flag_key = f.key and o.user_id = %s
            """,
            (user.id,),
        ).fetchall()
    return {r["key"]: r["enabled"] for r in rows}


def require_permission(permission: str) -> Callable[..., CurrentUser]:
    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if permission not in permissions_for(user):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing permission '{permission}'")
        return user

    return dependency
