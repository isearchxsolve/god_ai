"""JWT authentication for the OiiOii Studio API.

Issues HS256-signed tokens carrying `sub` (user id) and `email`.
`get_current_user` resolves the Bearer token to a user row, optionally
auto-provisioning a demo user when AUTO_PROVISION_DEMO is enabled so the
studio is instantly usable without a signup flow.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core import db

_bearer = HTTPBearer(auto_error=False)


def create_access_token(user_id: str, email: str = "") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Resolve the current user from the Authorization header.

    Falls back to the `token` query param (needed for SSE/EventSource which
    cannot set headers). With AUTO_PROVISION_DEMO, a missing token yields a
    shared demo user instead of a 401 so the studio works out of the box.
    """
    token: Optional[str] = credentials.credentials if credentials else None
    if not token:
        token = request.query_params.get("token")

    if token:
        payload = decode_token(token)
        user = await db.get_user(payload.get("sub", ""))
        if user:
            return user
        raise HTTPException(status_code=401, detail="User not found for token")

    if settings.AUTO_PROVISION_DEMO:
        user = await db.get_user_by_email("demo@oioi.studio")
        if not user:
            user = await db.create_user("demo@oioi.studio", name="Demo Director", credits=300)
        return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Strict variant: always demands a valid token (no auto-provision)."""
    token: Optional[str] = credentials.credentials if credentials else None
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    user = await db.get_user(payload.get("sub", ""))
    if not user:
        raise HTTPException(status_code=401, detail="User not found for token")
    return user
