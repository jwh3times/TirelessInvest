"""The signed-in user's own account: deleting it."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import CurrentUser, current_user
from ..db import connection

router = APIRouter(tags=["account"])

# Stands in for a deleted user's id in the admin audit log, which keeps its entries but not
# whose account they were about.
DELETED_USER = "deleted user"


class DeleteAccount(BaseModel):
    confirm_email: str


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(body: DeleteAccount, user: CurrentUser = Depends(current_user)) -> None:
    """Deletes the caller's account at once and for good.

    The email and the admin role are read from the database, not the token, so a token issued
    before a change can't get past either check. Deleting the auth.users row cascades to the
    user's backtests, permissions and flag overrides, and to Supabase's own sessions and
    refresh tokens; the caller's still-unexpired access token then fails current_user's check
    that its user exists.
    """
    with connection() as conn:
        row = conn.execute(
            "select email, coalesce(raw_app_meta_data ->> 'role', '') = 'admin' as is_admin "
            "from auth.users where id = %s for update",
            (user.id,),
        ).fetchone()
        if row is None:  # deleted by a concurrent request since current_user looked
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
        if row["is_admin"]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "the admin account can't be deleted through the app"
            )
        email = row["email"] or ""
        if not email or body.confirm_email.strip().casefold() != email.casefold():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "the confirmation doesn't match your account's email address",
            )
        # Admin audit entries about the user stay, but no longer say whose account it was:
        # permissions.set names the user as its target, flag.override.* in detail.user_id.
        conn.execute(
            "update public.admin_audit_log set target = %s where target = %s",
            (DELETED_USER, str(user.id)),
        )
        conn.execute(
            """
            update public.admin_audit_log
            set detail = jsonb_set(detail, '{user_id}', to_jsonb(%s::text))
            where detail ->> 'user_id' = %s
            """,
            (DELETED_USER, str(user.id)),
        )
        conn.execute("delete from auth.users where id = %s", (user.id,))
