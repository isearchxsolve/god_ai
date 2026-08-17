"""Assets endpoint: list generated characters, scenes, images, audio, video."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core import db
from app.core.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_assets(project_id: str = Query(...),
                      kind: Optional[str] = None,
                      user: dict = Depends(get_current_user)):
    """List assets for a project, optionally filtered by kind."""
    project = await db.get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    assets = await db.list_assets(project_id, kind=kind)
    return {"assets": assets, "count": len(assets)}


@router.get("/{asset_id}")
async def get_asset(asset_id: str, user: dict = Depends(get_current_user)):
    asset = await db.get_asset(asset_id)
    if not asset or asset["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"asset": asset}
