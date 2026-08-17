"""Jobs endpoint: inspect the background generation queue."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core import db
from app.core.auth import get_current_user

router = APIRouter()


@router.get("/")
async def list_jobs(project_id: Optional[str] = None,
                    status: Optional[str] = None,
                    limit: int = Query(100, le=500),
                    user: dict = Depends(get_current_user)):
    jobs = await db.list_jobs(project_id=project_id, status=status, limit=limit)
    return {"jobs": jobs, "count": len(jobs)}


@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.get_job(job_id)
    return {"job": job}
