"""Project CRUD backed by SQLite with JWT auth.

Accepts both `title` (legacy) and `name` on create/update, and returns the
project at the top level with both `id` and `title` so existing clients and
the new frontend work interchangeably.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core import db
from app.core.auth import get_current_user

router = APIRouter()


class ProjectCreateRequest(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    idea: Optional[str] = ""
    description: Optional[str] = ""
    style_id: Optional[str] = ""
    aspect_ratio: Optional[str] = "16:9"


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = None
    title: Optional[str] = None
    idea: Optional[str] = None
    description: Optional[str] = None
    style_id: Optional[str] = None
    aspect_ratio: Optional[str] = None
    status: Optional[str] = None


def _with_title(project: dict) -> dict:
    """Ensure both `name` and `title` are present for client compatibility."""
    out = dict(project)
    out["title"] = out.get("name", "")
    return out


@router.post("/")
async def create_project(request: ProjectCreateRequest, user: dict = Depends(get_current_user)):
    name = request.name or request.title or "Untitled Film"
    idea = request.idea or request.description or ""
    project = await db.create_project(
        user["id"], name, idea=idea,
        style_id=request.style_id or "", aspect_ratio=request.aspect_ratio or "16:9",
    )
    return _with_title(project)


@router.get("/")
async def list_projects(user: dict = Depends(get_current_user)):
    projects = await db.list_projects(user["id"])
    return {"projects": [_with_title(p) for p in projects]}


@router.get("/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    project = await db.get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    frames = await db.list_frames(project_id)
    assets = await db.list_assets(project_id)
    runs = await db.list_agent_runs(project_id)
    return {
        **_with_title(project),
        "frames": frames,
        "assets": assets,
        "agent_runs": runs,
    }


@router.patch("/{project_id}")
@router.put("/{project_id}")
async def update_project(project_id: str, request: ProjectUpdateRequest,
                         user: dict = Depends(get_current_user)):
    project = await db.get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    data = request.model_dump(exclude_none=True)
    if "title" in data:
        data["name"] = data.pop("title")
    if "description" in data:
        data["idea"] = data.pop("description")
    updated = await db.update_project(project_id, **data)
    return _with_title(updated)


@router.delete("/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    project = await db.get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete_project(project_id)
    return {"deleted": True}
