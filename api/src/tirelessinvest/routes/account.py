"""The signed-in user's own account: who they are, and deleting it."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..access import flags_for, permissions_for
from ..auth import CurrentUser, current_user
from ..db import connection
from .admin import forget_user_in_audit

router = APIRouter(tags=["account"])


@router.get("/me")
def me(user: CurrentUser = Depends(current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "is_admin": user.is_admin,
        "permissions": sorted(permissions_for(user)),
        "flags": flags_for(user),
    }


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
        # lower() matches the web page's toLowerCase(), which enables the button.
        email = row["email"] or ""
        if not email or body.confirm_email.strip().lower() != email.lower():
            raise HTTPException(422, "the confirmation doesn't match your account's email address")
        # Admin audit entries about the user stay, but no longer say whose account it was.
        forget_user_in_audit(conn, user.id)
        conn.execute("delete from auth.users where id = %s", (user.id,))
