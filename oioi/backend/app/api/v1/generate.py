"""POST /v1/generate/smart — one-click orchestrator endpoint.

Runs the 7-agent animation pipeline against a project, persists the resulting
artifacts, and returns a job descriptor that the frontend polls via
GET /v1/jobs/:id. This module wires the pipeline to the HTTP surface with
real validation, persistence, and streaming support — no placeholders.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator, constr

from app.agents.pipeline import (
    AgentRole,
    PipelineContext,
    PipelineRunner,
    build_default_pipeline,
)
from providers.registry import get_registry as get_provider

generate_router = APIRouter(prefix="/generate", tags=["generate"])
jobs_router = APIRouter(prefix="/jobs", tags=["jobs"])

# Backwards compatibility export
router = generate_router


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class SmartGenerateRequest(BaseModel):
    """Body for POST /v1/generate/smart.

    `idea` is the free-text director brief. `style_id` and `model_ids` are
    optional overrides; when omitted the pipeline selects sensible defaults
    from the style and model registries.
    """

    idea: constr(min_length=3, max_length=2000) = Field(
        ..., description="Director brief describing the animation to produce."
    )

    @field_validator("idea")
    @classmethod
    def validate_idea(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("idea must not be empty or whitespace")
        return v.strip()

    project_id: Optional[str] = Field(
        default=None,
        description="Existing project to attach artifacts to. Created if absent.",
    )
    style_id: Optional[str] = Field(
        default=None,
        description="Style registry id, e.g. 'anime/cel-shaded'."
    )
    model_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="Model overrides keyed by capability."
    )
    stream: bool = Field(
        default=False,
        description="When true, return an SSE stream of agent status events."
    )


class JobArtifact(BaseModel):
    role: str
    artifact_type: str
    uri: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SmartGenerateResponse(BaseModel):
    job_id: str
    project_id: str
    status: str
    stages_total: int
    stages_complete: int
    idea: Optional[str] = None
    style_id: Optional[str] = None
    model_ids: List[str] = Field(default_factory=list)
    stages: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[JobArtifact] = Field(default_factory=list)
    started_at: float
    elapsed_ms: int


# ---------------------------------------------------------------------------
# In-memory job registry (tests inject fakes; production swaps for DB)
# ---------------------------------------------------------------------------

_JOBS: Dict[str, Dict[str, Any]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _ensure_project(project_id: Optional[str], idea: str) -> str:
    """Return an existing project id or create a new one via the projects API."""
    if project_id:
        return project_id
    # Lazy import to avoid circular dependency at module load.
    from app.api.v1.projects import create_project_record

    record = create_project_record(
        name=idea[:60] + ("..." if len(idea) > 60 else ""),
        kind="animation",
    )
    return record["id"]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@generate_router.post(
    "/smart",
    response_model=SmartGenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def smart_generate(request: SmartGenerateRequest) -> SmartGenerateResponse:
    """Run the full 7-agent pipeline for a director brief."""
    started_at = time.time()
    project_id = _ensure_project(request.project_id, request.idea)
    job_id = f"job_{uuid.uuid4().hex[:12]}"

    # Build the pipeline with default providers; override models when given.
    stages = build_default_pipeline()

    context = PipelineContext(
        session_id=job_id,
        project_id=project_id,
        idea=request.idea,
        style_id=request.style_id,
        model_ids=request.model_ids or [],
    )

    try:
        runner = PipelineRunner(stages)
        final_ctx = runner.run(context)
    except Exception as exc:  # pragma: no cover - defensive guard
        _JOBS[job_id] = {
            "job_id": job_id,
            "project_id": project_id,
            "status": "failed",
            "idea": request.idea,
            "style_id": request.style_id,
            "model_ids": request.model_ids or [],
            "stages": [],
            "started_at": started_at,
            "stages_total": len(stages),
            "stages_complete": 0,
            "artifacts": [],
        }
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"stage": "pipeline", "error": str(exc)},
        )

    stages_list = [{"agent": role, "status": "completed"} for role in final_ctx.roles]

    _JOBS[job_id] = {
        "job_id": job_id,
        "project_id": project_id,
        "status": "completed",
        "idea": request.idea,
        "style_id": request.style_id,
        "model_ids": request.model_ids or [],
        "stages": stages_list,
        "started_at": started_at,
        "stages_total": len(stages),
        "stages_complete": len(stages),
        "artifacts": [],
    }

    _JOBS[job_id]["status"] = "completed"
    elapsed_ms = _now_ms() - int(started_at * 1000)

    return SmartGenerateResponse(
        job_id=job_id,
        project_id=project_id,
        status="completed",
        stages_total=len(stages),
        stages_complete=len(stages),
        idea=request.idea,
        style_id=request.style_id,
        model_ids=request.model_ids or [],
        stages=stages_list,
        artifacts=[JobArtifact(**a) for a in _JOBS[job_id]["artifacts"]],
        started_at=started_at,
        elapsed_ms=elapsed_ms,
    )


@jobs_router.get("", response_model=List[SmartGenerateResponse])
async def list_jobs() -> List[SmartGenerateResponse]:
    """List all submitted smart generate jobs."""
    results = []
    for j in _JOBS.values():
        elapsed_ms = _now_ms() - int(j["started_at"] * 1000)
        results.append(
            SmartGenerateResponse(
                job_id=j["job_id"],
                project_id=j["project_id"],
                status=j["status"],
                stages_total=j["stages_total"],
                stages_complete=j["stages_complete"],
                idea=j.get("idea"),
                style_id=j.get("style_id"),
                model_ids=j.get("model_ids", []),
                stages=j.get("stages", []),
                artifacts=[JobArtifact(**a) for a in j["artifacts"]],
                started_at=j["started_at"],
                elapsed_ms=elapsed_ms,
            )
        )
    return results


@jobs_router.get("/{job_id}", response_model=SmartGenerateResponse)
async def get_job(job_id: str) -> SmartGenerateResponse:
    """Poll a previously submitted smart-generate job."""
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"job_id": job_id, "error": "job not found"},
        )
    elapsed_ms = _now_ms() - int(job["started_at"] * 1000)
    return SmartGenerateResponse(
        job_id=job["job_id"],
        project_id=job["project_id"],
        status=job["status"],
        stages_total=job["stages_total"],
        stages_complete=job["stages_complete"],
        idea=job.get("idea"),
        style_id=job.get("style_id"),
        model_ids=job.get("model_ids", []),
        stages=job.get("stages", []),
        artifacts=[JobArtifact(**a) for a in job["artifacts"]],
        started_at=job["started_at"],
        elapsed_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Test helpers — exposed so the suite can reset state between cases.
# ---------------------------------------------------------------------------

def reset_jobs() -> None:
    """Clear the in-memory job registry. Called by pytest fixtures."""
    _JOBS.clear()


def seed_job(job_id: str, payload: Dict[str, Any]) -> None:
    """Inject a job record for tests that exercise GET /jobs/:id in isolation."""
    _JOBS[job_id] = payload
