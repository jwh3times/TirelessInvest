"""Admin-only endpoints: users, permissions, feature flags, audit log.

There is deliberately no endpoint to grant the admin role: the project has a single admin,
set once with `python -m stocklab.cli make-admin`.
"""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field, field_validator

from ..auth import CurrentUser, require_admin
from ..db import connection

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

FLAG_KEY_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,63}$")


def _audit(conn, actor: CurrentUser, action: str, target: str, detail: dict) -> None:
    conn.execute(
        "insert into public.admin_audit_log (actor_id, action, target, detail) "
        "values (%s, %s, %s, %s)",
        (actor.id, action, target, Jsonb(detail)),
    )


# --- users & permissions ---------------------------------------------------------------


@router.get("/users")
def list_users() -> list[dict]:
    with connection() as conn:
        rows = conn.execute(
            """
            select u.id, u.email, u.created_at, u.last_sign_in_at,
                   coalesce(u.raw_app_meta_data ->> 'role', '') = 'admin' as is_admin,
                   coalesce(
                     array_agg(p.permission_key order by p.permission_key)
                       filter (where p.permission_key is not null),
                     '{}'
                   ) as permissions,
                   (select count(*) from public.backtests b where b.user_id = u.id)
                     as backtest_count
            from auth.users u
            left join public.user_permissions p on p.user_id = u.id
            group by u.id
            order by u.created_at
            """
        ).fetchall()
    return [{**r, "id": str(r["id"])} for r in rows]


@router.get("/permissions")
def list_permissions() -> list[dict]:
    with connection() as conn:
        return conn.execute("select * from public.permissions order by key").fetchall()


class SetPermissions(BaseModel):
    permissions: list[str]


@router.put("/users/{user_id}/permissions")
def set_permissions(
    user_id: UUID, body: SetPermissions, admin: CurrentUser = Depends(require_admin)
) -> dict:
    wanted = sorted(set(body.permissions))
    with connection() as conn:
        if conn.execute("select 1 from auth.users where id = %s", (user_id,)).fetchone() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        known = {r["key"] for r in conn.execute("select key from public.permissions")}
        unknown = set(wanted) - known
        if unknown:
            raise HTTPException(422, f"unknown permissions: {sorted(unknown)}")
        conn.execute("delete from public.user_permissions where user_id = %s", (user_id,))
        for key in wanted:
            conn.execute(
                "insert into public.user_permissions (user_id, permission_key) values (%s, %s)",
                (user_id, key),
            )
        _audit(conn, admin, "permissions.set", str(user_id), {"permissions": wanted})
    return {"user_id": str(user_id), "permissions": wanted}


# --- feature flags ------------------------------------------------------------------------


@router.get("/flags")
def list_flags() -> list[dict]:
    with connection() as conn:
        flags = conn.execute("select * from public.feature_flags order by key").fetchall()
        overrides = conn.execute(
            """
            select o.flag_key, o.user_id, o.enabled, u.email
            from public.feature_flag_overrides o join auth.users u on u.id = o.user_id
            order by u.email
            """
        ).fetchall()
    by_flag: dict[str, list[dict]] = {}
    for o in overrides:
        by_flag.setdefault(o["flag_key"], []).append(
            {"user_id": str(o["user_id"]), "email": o["email"], "enabled": o["enabled"]}
        )
    return [{**f, "overrides": by_flag.get(f["key"], [])} for f in flags]


class CreateFlag(BaseModel):
    key: str
    description: str = Field(min_length=1, max_length=300)
    enabled: bool = False

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        if not FLAG_KEY_RE.match(v):
            raise ValueError("flag keys are lowercase, e.g. 'strategy.my_idea'")
        return v


@router.post("/flags", status_code=status.HTTP_201_CREATED)
def create_flag(body: CreateFlag, admin: CurrentUser = Depends(require_admin)) -> dict:
    with connection() as conn:
        row = conn.execute(
            "insert into public.feature_flags (key, description, enabled) values (%s, %s, %s) "
            "on conflict (key) do nothing returning *",
            (body.key, body.description, body.enabled),
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "flag already exists")
        _audit(conn, admin, "flag.create", body.key, body.model_dump())
    return row


class UpdateFlag(BaseModel):
    enabled: bool | None = None
    description: str | None = Field(None, min_length=1, max_length=300)


@router.patch("/flags/{key}")
def update_flag(key: str, body: UpdateFlag, admin: CurrentUser = Depends(require_admin)) -> dict:
    with connection() as conn:
        row = conn.execute(
            """
            update public.feature_flags set
              enabled = coalesce(%s, enabled),
              description = coalesce(%s, description),
              updated_at = now()
            where key = %s returning *
            """,
            (body.enabled, body.description, key),
        ).fetchone()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "flag not found")
        _audit(conn, admin, "flag.update", key, body.model_dump(exclude_none=True))
    return row


@router.delete("/flags/{key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_flag(key: str, admin: CurrentUser = Depends(require_admin)) -> None:
    with connection() as conn:
        deleted = conn.execute(
            "delete from public.feature_flags where key = %s returning key", (key,)
        ).fetchone()
        if deleted is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "flag not found")
        _audit(conn, admin, "flag.delete", key, {})


class SetOverride(BaseModel):
    enabled: bool


@router.put("/flags/{key}/overrides/{user_id}")
def set_override(
    key: str, user_id: UUID, body: SetOverride, admin: CurrentUser = Depends(require_admin)
) -> dict:
    with connection() as conn:
        if (
            conn.execute("select 1 from public.feature_flags where key = %s", (key,)).fetchone()
            is None
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "flag not found")
        if conn.execute("select 1 from auth.users where id = %s", (user_id,)).fetchone() is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
        conn.execute(
            """
            insert into public.feature_flag_overrides (flag_key, user_id, enabled)
            values (%s, %s, %s)
            on conflict (flag_key, user_id) do update
              set enabled = excluded.enabled, updated_at = now()
            """,
            (key, user_id, body.enabled),
        )
        _audit(
            conn,
            admin,
            "flag.override.set",
            key,
            {"user_id": str(user_id), "enabled": body.enabled},
        )
    return {"flag_key": key, "user_id": str(user_id), "enabled": body.enabled}


@router.delete("/flags/{key}/overrides/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_override(key: str, user_id: UUID, admin: CurrentUser = Depends(require_admin)) -> None:
    with connection() as conn:
        conn.execute(
            "delete from public.feature_flag_overrides where flag_key = %s and user_id = %s",
            (key, user_id),
        )
        _audit(conn, admin, "flag.override.delete", key, {"user_id": str(user_id)})


# --- audit log ----------------------------------------------------------------------------


@router.get("/audit")
def audit_log(limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    with connection() as conn:
        return conn.execute(
            """
            select a.id, a.action, a.target, a.detail, a.created_at, u.email as actor_email
            from public.admin_audit_log a left join auth.users u on u.id = a.actor_id
            order by a.id desc limit %s
            """,
            (limit,),
        ).fetchall()
