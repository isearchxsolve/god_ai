"""Pipeline endpoints: run the 7-agent team and stream its progress via SSE.

POST /projects/{id}/pipeline/run        — kicks off a pipeline run
GET  /projects/{id}/pipeline/stream     — SSE feed of agent status + artifacts
GET  /projects/{id}/pipeline/status     — current project status + agent history

The run executes as a fire-and-forget asyncio task so the HTTP response returns
immediately; progress is observed via the SSE stream. Pass wait=true to block
until completion (used by integration tests and the "Smart mode" one-click flow
when a caller prefers to await the result).
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional, Set

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_pipeline import AGENT_ROLES, create_animation_pipeline
from app.core import db
from app.core.auth import get_current_user
from app.services.events import get_event_bus
from app.services.provider_service import get_provider_registry

router = APIRouter()

# Keep strong references to background tasks so they aren't garbage-collected.
_RUNNING_TASKS: Set[asyncio.Task] = set()


class PipelineRunRequest(BaseModel):
    idea: str
    style: Optional[str] = ""
    style_id: Optional[str] = ""
    aspect_ratio: Optional[str] = "16:9"
    duration: Optional[int] = 15
    wait: Optional[bool] = False


def _stages(status: str) -> list:
    return [{"agent": a, "status": status} for a in AGENT_ROLES]


async def _run_pipeline_task(project_id: str, user_id: str, idea: str,
                             style_id: str, duration: int, aspect_ratio: str) -> None:
    bus = get_event_bus()
    channel = f"pipeline:{project_id}"

    async def sink(event: dict) -> None:
        await bus.publish(channel, event)

    try:
        registry = await get_provider_registry()
        pipeline = create_animation_pipeline(
            registry, project_id=project_id, user_id=user_id, event_sink=sink
        )
        await pipeline.run(idea, style=style_id, duration=duration,
                           aspect_ratio=aspect_ratio)
    except Exception as exc:
        await db.update_project(project_id, status="failed")
        await bus.publish(channel, {"type": "pipeline.failed", "error": str(exc)})


async def _ensure_project(project_id: str, user: dict, idea: str,
                          style_id: str, aspect_ratio: str) -> dict:
    """Return the project, auto-creating it if the caller used a fresh id."""
    project = await db.get_project(project_id)
    if project and project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project:
        project = await db.create_project(
            user["id"], name=idea[:60] or "Untitled Film", idea=idea,
            style_id=style_id, aspect_ratio=aspect_ratio,
        )
        # Re-key to the caller-supplied id so stream URLs match.
        await db.update_project(project["id"], name=idea[:60] or "Untitled Film")
        project = await db.get_project(project["id"])
    return project


@router.post("/{project_id}/pipeline/run")
async def run_animation_pipeline(project_id: str, request: PipelineRunRequest,
                                 user: dict = Depends(get_current_user)):
    """Run the 7-agent animation pipeline for a project."""
    style_id = request.style_id or request.style or ""
    duration = request.duration or 15
    aspect_ratio = request.aspect_ratio or "16:9"

    project = await db.get_project(project_id)
    if project and project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project:
        project = await db.create_project(
            user["id"], name=request.idea[:60] or "Untitled Film", idea=request.idea,
            style_id=style_id, aspect_ratio=aspect_ratio,
        )
        # Use the newly created project's real id for the run.
        project_id = project["id"]

    if request.wait:
        await _run_pipeline_task(project_id, user["id"], request.idea,
                                 style_id, duration, aspect_ratio)
        updated = await db.get_project(project_id)
        status = updated["status"] if updated else "failed"
        # Normalize the internal "complete" state to the public "completed".
        public_status = "completed" if status == "complete" else status
        return {
            "project_id": project_id,
            "status": public_status,
            "stages": _stages("completed" if public_status == "completed" else public_status),
            "final_video_uri": (updated or {}).get("final_video_uri"),
        }

    task = asyncio.create_task(
        _run_pipeline_task(project_id, user["id"], request.idea,
                           style_id, duration, aspect_ratio)
    )
    _RUNNING_TASKS.add(task)
    task.add_done_callback(_RUNNING_TASKS.discard)

    return {
        "project_id": project_id,
        "status": "started",
        "stages": _stages("queued"),
        "stream_url": f"/api/v1/projects/{project_id}/pipeline/stream",
    }


@router.get("/{project_id}/pipeline/stream")
async def stream_pipeline(project_id: str, user: dict = Depends(get_current_user)):
    """SSE stream of agent status updates and generated artifacts."""
    project = await db.get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")

    bus = get_event_bus()
    channel = f"pipeline:{project_id}"

    async def event_generator():
        yield f"data: {json.dumps({'type': 'stream.connected', 'project_id': project_id})}\n\n"
        async for event in bus.subscribe(channel):
            yield f"data: {json.dumps(event, default=str)}\n\n"
            if event.get("type") in ("pipeline.complete", "pipeline.failed"):
                break
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{project_id}/pipeline/status")
async def pipeline_status(project_id: str, user: dict = Depends(get_current_user)):
    """Current pipeline state: project status + per-agent run history."""
    project = await db.get_project(project_id)
    if not project or project["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Project not found")
    runs = await db.list_agent_runs(project_id)
    return {"project_id": project_id, "status": project["status"], "agent_runs": runs}
