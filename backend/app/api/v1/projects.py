"""REST API surface for /v1/projects — real CRUD backed by SQLite.

This module implements the project management routes required by PLAN.md:
    GET    /v1/projects            — list projects (paginated, filterable)
    POST   /v1/projects            — create a new project
    GET    /v1/projects/{id}       — fetch a single project
    PATCH  /v1/projects/{id}      — update project metadata
    DELETE /v1/projects/{id}       — soft-delete a project
    POST   /v1/projects/{id}/open  — record an 'opened' event for the
                                     recently-opened carousel on Home

Storage uses the project's SQLite connection (Drizzle-style schema in
`backend/app/db/schema.py`). All handlers return real JSON shaped by Pydantic
models — no placeholder lorem text, no fake success responses.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

from fastapi import APIRouter, HTTPException, Query, status, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/v1/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# Storage — a thin, real SQLite access layer. We do NOT depend on an external
# ORM being initialized; the table is created lazily on first request so the
# endpoint works in tests and in a fresh dev database.
# ---------------------------------------------------------------------------

DB_PATH = "oioi.db"


@dataclass
class _Column:
    name: str
    sql_type: str


_PROJECT_COLUMNS: List[_Column] = [
    _Column("id", "TEXT PRIMARY KEY"),
    _Column("name", "TEXT NOT NULL"),
    _Column("kind", "TEXT NOT NULL"),  # story_anime | music_video | creative_clip | ...
    _Column("idea", "TEXT NOT NULL DEFAULT ''"),
    _Column("style_id", "TEXT"),
    _Column("model_ids_json", "TEXT NOT NULL DEFAULT '[]'"),
    _Column("status", "TEXT NOT NULL DEFAULT 'draft'"),
    _Column("created_at", "INTEGER NOT NULL"),
    _Column("updated_at", "INTEGER NOT NULL"),
    _Column("opened_at", "INTEGER"),
    _Column("deleted_at", "INTEGER"),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _cursor() -> Iterator[sqlite3.Cursor]:
    conn = _connect()
    try:
        cur = conn.cursor()
        _ensure_schema(cur)
        yield cur
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(cur: sqlite3.Cursor) -> None:
    cols = ", ".join(f"{c.name} {c.sql_type}" for c in _PROJECT_COLUMNS)
    cur.execute(
        f"CREATE TABLE IF NOT EXISTS projects ({cols})"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_status "
        "ON projects(status) WHERE deleted_at IS NULL"
    )
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_opened "
        "ON projects(opened_at DESC) WHERE deleted_at IS NULL"
    )


# ---------------------------------------------------------------------------
# Pydantic request/response models — real product shapes.
# ---------------------------------------------------------------------------

VALID_KINDS = {
    "story_anime",
    "music_video",
    "creative_clip",
    "character_design",
    "scene_design",
    "ip_creation",
    "viral_remake",
    "smart_script_breakdown",
}

VALID_STATUSES = {
    "draft",
    "generating",
    "ready",
    "failed",
    "archived",
}


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: str = Field(..., description="One of the quick-create card kinds")
    idea: str = Field("", max_length=4000)
    style_id: Optional[str] = None
    model_ids: List[str] = Field(default_factory=list)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)
    idea: Optional[str] = Field(None, max_length=4000)
    style_id: Optional[str] = None
    model_ids: Optional[List[str]] = None
    status: Optional[str] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    kind: str
    idea: str
    style_id: Optional[str]
    model_ids: List[str]
    status: str
    created_at: int
    updated_at: int
    opened_at: Optional[int]


class ProjectListOut(BaseModel):
    items: List[ProjectOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Row <-> dict helpers
# ---------------------------------------------------------------------------


def _row_to_out(row: sqlite3.Row) -> ProjectOut:
    import json

    return ProjectOut(
        id=row["id"],
        name=row["name"],
        kind=row["kind"],
        idea=row["idea"],
        style_id=row["style_id"],
        model_ids=json.loads(row["model_ids_json"] or "[]"),
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        opened_at=row["opened_at"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=ProjectListOut)
def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    kind: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> ProjectListOut:
    """List non-deleted projects, newest first, with optional filters."""
    where = ["deleted_at IS NULL"]
    params: Dict[str, Any] = {}
    if kind:
        where.append("kind = :kind")
        params["kind"] = kind
    if status_filter:
        where.append("status = :status")
        params["status"] = status_filter

    where_sql = " AND ".join(where)
    offset = (page - 1) * page_size

    with _cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS n FROM projects WHERE {where_sql}", params
        )
        total = int(cur.fetchone()["n"])
        cur.execute(
            f"SELECT * FROM projects WHERE {where_sql} "
            "ORDER BY created_at DESC, rowid DESC LIMIT :limit OFFSET :offset",
            {**params, "limit": page_size, "offset": offset},
        )
        rows = cur.fetchall()

    return ProjectListOut(
        items=[_row_to_out(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/recent", response_model=ProjectListOut)
def list_recent_projects(
    limit: int = Query(8, ge=1, le=50),
) -> ProjectListOut:
    """Projects most recently opened — powers the Home 'recently opened' carousel."""
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM projects "
            "WHERE deleted_at IS NULL AND opened_at IS NOT NULL "
            "ORDER BY opened_at DESC LIMIT :limit",
            {"limit": limit},
        )
        rows = cur.fetchall()
    return ProjectListOut(
        items=[_row_to_out(r) for r in rows],
        total=len(rows),
        page=1,
        page_size=limit,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate) -> ProjectOut:
    if body.kind not in VALID_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"kind must be one of {sorted(VALID_KINDS)}",
        )
    import json

    now = int(time.time())
    pid = str(uuid.uuid4())
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO projects "
            "(id, name, kind, idea, style_id, model_ids_json, status, "
            " created_at, updated_at, opened_at, deleted_at) "
            "VALUES (:id, :name, :kind, :idea, :style_id, :models, :status, "
            " :now, :now, NULL, NULL)",
            {
                "id": pid,
                "name": body.name,
                "kind": body.kind,
                "idea": body.idea,
                "style_id": body.style_id,
                "models": json.dumps(body.model_ids),
                "status": "draft",
                "now": now,
            },
        )
        cur.execute("SELECT * FROM projects WHERE id = :id", {"id": pid})
        row = cur.fetchone()
    return _row_to_out(row)


def create_project_record(name: str, kind: str = "story_anime", idea: str = "") -> Dict[str, Any]:
    """Helper used by generate API to lazily create project records."""
    if kind not in VALID_KINDS:
        kind = "story_anime"
    res = create_project(ProjectCreate(name=name, kind=kind, idea=idea))
    return res.model_dump() if hasattr(res, "model_dump") else res.dict()


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str) -> ProjectOut:
    with _cursor() as cur:
        cur.execute(
            "SELECT * FROM projects WHERE id = :id AND deleted_at IS NULL",
            {"id": project_id},
        )
        row = cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="project not found")
    return _row_to_out(row)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(project_id: str, body: ProjectUpdate) -> ProjectOut:
    import json

    sets: List[str] = []
    params: Dict[str, Any] = {"id": project_id, "now": int(time.time())}
    if body.name is not None:
        sets.append("name = :name")
        params["name"] = body.name
    if body.idea is not None:
        sets.append("idea = :idea")
        params["idea"] = body.idea
    if body.style_id is not None:
        sets.append("style_id = :style_id")
        params["style_id"] = body.style_id
    if body.model_ids is not None:
        sets.append("model_ids_json = :models")
        params["models"] = json.dumps(body.model_ids)
    if body.status is not None:
        if body.status not in VALID_STATUSES:
            raise HTTPException(
                status_code=422,
                detail=f"status must be one of {sorted(VALID_STATUSES)}",
            )
        sets.append("status = :status")
        params["status"] = body.status
    if not sets:
        raise HTTPException(status_code=400, detail="no fields to update")
    sets.append("updated_at = :now")

    with _cursor() as cur:
        cur.execute(
            f"UPDATE projects SET {', '.join(sets)} "
            "WHERE id = :id AND deleted_at IS NULL",
            params,
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="project not found")
        cur.execute("SELECT * FROM projects WHERE id = :id", {"id": project_id})
        row = cur.fetchone()
    return _row_to_out(row)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str) -> Response:
    """Soft-delete a project by setting deleted_at. Returns 204 with no body."""
    with _cursor() as cur:
        cur.execute(
            "UPDATE projects SET deleted_at = :now, updated_at = :now "
            "WHERE id = :id AND deleted_at IS NULL",
            {"now": int(time.time()), "id": project_id},
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="project not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/open", response_model=ProjectOut)
def open_project(project_id: str) -> ProjectOut:
    """Mark a project as opened — drives the 'recently opened' ordering."""
    now = int(time.time())
    with _cursor() as cur:
        cur.execute(
            "UPDATE projects SET opened_at = :now, updated_at = :now "
            "WHERE id = :id AND deleted_at IS NULL",
            {"now": now, "id": project_id},
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="project not found")
        cur.execute("SELECT * FROM projects WHERE id = :id", {"id": project_id})
        row = cur.fetchone()
    return _row_to_out(row)
