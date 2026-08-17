"""Auth endpoints: token issuance and current-user info."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core import db
from app.core.auth import create_access_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = "demo@oioi.studio"
    name: Optional[str] = "Demo Director"


@router.post("/login")
async def login(request: LoginRequest):
    """Issue a JWT, auto-provisioning the user if they don't exist yet."""
    user = await db.get_user_by_email(request.email)
    if not user:
        user = await db.create_user(request.email, name=request.name or "Director", credits=300)
    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": user}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current user's profile and credit balance."""
    return {"user": user}
