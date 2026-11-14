"""Verifies Supabase access tokens, checks their user still exists, and exposes the current user
to routes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import connection

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str | None
    is_admin: bool


class TokenVerifier:
    """Checks signature, expiry, audience and issuer of a Supabase access token.

    New Supabase projects sign tokens with asymmetric keys published at a JWKS URL, so the
    API never needs a shared secret. Projects on the legacy HS256 secret can set
    SUPABASE_JWT_SECRET instead.
    """

    def __init__(self, supabase_url: str, jwt_secret: str = "") -> None:
        self.issuer = f"{supabase_url.rstrip('/')}/auth/v1"
        self.secret = jwt_secret or None
        self.jwks = (
            None
            if self.secret
            else jwt.PyJWKClient(f"{self.issuer}/.well-known/jwks.json", lifespan=600)
        )

    def verify(self, token: str) -> dict:
        if self.secret:
            key, algorithms = self.secret, ["HS256"]
        else:
            assert self.jwks is not None
            key, algorithms = self.jwks.get_signing_key_from_jwt(token).key, ["ES256", "RS256"]
        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience="authenticated",
            issuer=self.issuer,
            options={"require": ["exp", "sub"]},
        )


@lru_cache
def get_verifier() -> TokenVerifier:
    s = get_settings()
    return TokenVerifier(s.supabase_url, s.supabase_jwt_secret)


_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    verifier: TokenVerifier = Depends(get_verifier),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    try:
        claims = verifier.verify(creds.credentials)
    except jwt.PyJWTError as exc:
        log.info("rejected token: %s", exc)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired token") from exc
    user_id = UUID(claims["sub"])
    # A token outlives its user: after an account is deleted, its access token stays valid
    # until it expires. Only a user who still exists is authenticated.
    with connection() as conn:
        if conn.execute("select 1 from auth.users where id = %s", (user_id,)).fetchone() is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown user")
    # Role comes from app_metadata, which only the service role can write.
    # Never read roles from user_metadata: users can edit that themselves.
    app_metadata = claims.get("app_metadata") or {}
    return CurrentUser(
        id=user_id,
        email=claims.get("email"),
        is_admin=app_metadata.get("role") == "admin",
    )


def require_admin(user: CurrentUser = Depends(current_user)) -> CurrentUser:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin only")
    return user
