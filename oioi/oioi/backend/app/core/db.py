"""Async SQLite persistence layer (aiosqlite).

Tables:
  users             — auth principals with credit balance
  projects          — a film/animation project per user
  assets            — generated artifacts (image/video/audio/script) tied to a project
  storyboard_frames — per-shot frames on the canvas
  agent_runs        — execution log for each of the 7 agents
  jobs              — background generation job queue

All timestamps are stored as ISO-8601 UTC strings. IDs are uuid4 hex.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from app.core.config import settings

_DB_PATH: Optional[str] = None
_init_lock = asyncio.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def db_path() -> str:
    return _DB_PATH or settings.DATABASE_PATH


def set_db_path(path: str) -> None:
    """Override the database path (used by tests)."""
    global _DB_PATH
    _DB_PATH = path


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    name TEXT,
    credits INTEGER NOT NULL DEFAULT 300,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    idea TEXT,
    style_id TEXT,
    aspect_ratio TEXT DEFAULT '16:9',
    status TEXT NOT NULL DEFAULT 'draft',
    final_video_uri TEXT,
    thumbnail_uri TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    uri TEXT,
    prompt TEXT,
    model_id TEXT,
    provider TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id);
CREATE INDEX IF NOT EXISTS idx_assets_kind ON assets(kind);

CREATE TABLE IF NOT EXISTS storyboard_frames (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    scene_index INTEGER NOT NULL,
    shot_index INTEGER NOT NULL,
    prompt TEXT,
    image_uri TEXT,
    clip_uri TEXT,
    audio_uri TEXT,
    duration_seconds REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_frames_project ON storyboard_frames(project_id);

CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    agent TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    input_json TEXT,
    output_json TEXT,
    error TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_project ON agent_runs(project_id);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    project_id TEXT,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    provider TEXT,
    model TEXT,
    priority INTEGER NOT NULL DEFAULT 5,
    retry_count INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
"""


async def connect() -> aiosqlite.Connection:
    path = db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = await aiosqlite.connect(path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


from contextlib import asynccontextmanager

_schema_ready = False


@asynccontextmanager
async def get_conn():
    """Async context manager yielding a configured connection.

    Guarantees the schema exists on first use so callers never need to invoke
    init_db() explicitly (important for tests that skip the app lifespan).
    """
    global _schema_ready
    conn = await connect()
    try:
        if not _schema_ready:
            await conn.executescript(SCHEMA)
            await conn.commit()
            _schema_ready = True
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    """Create schema if missing. Safe to call repeatedly."""
    async with _init_lock:
        async with get_conn() as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()


def _row_to_dict(row: aiosqlite.Row) -> Dict[str, Any]:
    d = dict(row)
    # Decode JSON columns for convenience.
    for key in ("metadata_json", "input_json", "output_json", "payload_json", "result_json"):
        if key in d and isinstance(d[key], str) and d[key]:
            try:
                d[key.replace("_json", "")] = json.loads(d[key])
            except Exception:
                pass
    return d


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def create_user(email: str, name: str = "", credits: int = 300) -> Dict[str, Any]:
    await init_db()
    uid = new_id()
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO users (id, email, name, credits, created_at) VALUES (?,?,?,?,?)",
            (uid, email, name, credits, _now()),
        )
        await conn.commit()
    return await get_user(uid)


async def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM users WHERE email=?", (email,))
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def adjust_credits(user_id: str, delta: int) -> Optional[int]:
    async with get_conn() as conn:
        await conn.execute("UPDATE users SET credits = credits + ? WHERE id=?", (delta, user_id))
        await conn.commit()
        cur = await conn.execute("SELECT credits FROM users WHERE id=?", (user_id,))
        row = await cur.fetchone()
        return row["credits"] if row else None


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
async def create_project(user_id: str, name: str, idea: str = "", style_id: str = "",
                         aspect_ratio: str = "16:9") -> Dict[str, Any]:
    await init_db()
    pid = new_id()
    now = _now()
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO projects (id,user_id,name,idea,style_id,aspect_ratio,status,created_at,updated_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, user_id, name, idea, style_id, aspect_ratio, "draft", now, now),
        )
        await conn.commit()
    return await get_project(pid)


async def get_project(project_id: str) -> Optional[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM projects WHERE id=?", (project_id,))
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def list_projects(user_id: str) -> List[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM projects WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
        )
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


async def update_project(project_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    if not fields:
        return await get_project(project_id)
    fields["updated_at"] = _now()
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [project_id]
    async with get_conn() as conn:
        await conn.execute(f"UPDATE projects SET {sets} WHERE id=?", vals)
        await conn.commit()
    return await get_project(project_id)


async def delete_project(project_id: str) -> None:
    async with get_conn() as conn:
        for table in ("storyboard_frames", "agent_runs", "assets", "jobs"):
            await conn.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
        await conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        await conn.commit()


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
async def create_asset(project_id: str, user_id: str, kind: str, name: str,
                       uri: str = "", prompt: str = "", model_id: str = "",
                       provider: str = "", metadata: Optional[Dict] = None) -> Dict[str, Any]:
    await init_db()
    aid = new_id()
    async with get_conn() as conn:
        # version = existing count for this project+kind+name + 1
        cur = await conn.execute(
            "SELECT COUNT(*) AS c FROM assets WHERE project_id=? AND kind=? AND name=?",
            (project_id, kind, name),
        )
        row = await cur.fetchone()
        version = (row["c"] if row else 0) + 1
        await conn.execute(
            "INSERT INTO assets (id,project_id,user_id,kind,name,uri,prompt,model_id,provider,version,metadata_json,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, project_id, user_id, kind, name, uri, prompt, model_id, provider,
             version, json.dumps(metadata or {}), _now()),
        )
        await conn.commit()
    return await get_asset(aid)


async def get_asset(asset_id: str) -> Optional[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,))
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def list_assets(project_id: str, kind: Optional[str] = None) -> List[Dict[str, Any]]:
    async with get_conn() as conn:
        if kind:
            cur = await conn.execute(
                "SELECT * FROM assets WHERE project_id=? AND kind=? ORDER BY created_at", (project_id, kind)
            )
        else:
            cur = await conn.execute(
                "SELECT * FROM assets WHERE project_id=? ORDER BY created_at", (project_id,)
            )
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Storyboard frames
# ---------------------------------------------------------------------------
async def upsert_frame(project_id: str, scene_index: int, shot_index: int, **fields: Any) -> Dict[str, Any]:
    await init_db()
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT id FROM storyboard_frames WHERE project_id=? AND scene_index=? AND shot_index=?",
            (project_id, scene_index, shot_index),
        )
        row = await cur.fetchone()
        if row:
            fid = row["id"]
            if fields:
                sets = ", ".join(f"{k}=?" for k in fields)
                vals = list(fields.values()) + [fid]
                await conn.execute(f"UPDATE storyboard_frames SET {sets} WHERE id=?", vals)
        else:
            fid = new_id()
            await conn.execute(
                "INSERT INTO storyboard_frames (id,project_id,scene_index,shot_index,prompt,image_uri,clip_uri,audio_uri,duration_seconds,status,metadata_json,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (fid, project_id, scene_index, shot_index,
                 fields.get("prompt", ""), fields.get("image_uri", ""), fields.get("clip_uri", ""),
                 fields.get("audio_uri", ""), fields.get("duration_seconds"),
                 fields.get("status", "pending"), json.dumps(fields.get("metadata", {})), _now()),
            )
        await conn.commit()
        cur2 = await conn.execute("SELECT * FROM storyboard_frames WHERE id=?", (fid,))
        r = await cur2.fetchone()
        return _row_to_dict(r)


async def list_frames(project_id: str) -> List[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM storyboard_frames WHERE project_id=? ORDER BY scene_index, shot_index",
            (project_id,),
        )
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Agent runs
# ---------------------------------------------------------------------------
async def create_agent_run(project_id: str, agent: str, input_data: Optional[Dict] = None) -> str:
    await init_db()
    rid = new_id()
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO agent_runs (id,project_id,agent,status,input_json,created_at)"
            " VALUES (?,?,?,?,?,?)",
            (rid, project_id, agent, "pending", json.dumps(input_data or {}), _now()),
        )
        await conn.commit()
    return rid


async def update_agent_run(run_id: str, status: Optional[str] = None,
                           output: Optional[Dict] = None, error: str = "") -> None:
    async with get_conn() as conn:
        if status in ("running",):
            await conn.execute(
                "UPDATE agent_runs SET status=?, started_at=? WHERE id=?", (status, _now(), run_id)
            )
        elif status in ("completed", "failed"):
            await conn.execute(
                "UPDATE agent_runs SET status=?, output_json=?, error=?, finished_at=? WHERE id=?",
                (status, json.dumps(output or {}), error, _now(), run_id),
            )
        elif status:
            await conn.execute("UPDATE agent_runs SET status=? WHERE id=?", (status, run_id))
        await conn.commit()


async def list_agent_runs(project_id: str) -> List[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT * FROM agent_runs WHERE project_id=? ORDER BY created_at", (project_id,)
        )
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------
async def create_job(kind: str, payload: Dict[str, Any], user_id: str = "",
                     project_id: str = "", provider: str = "", model: str = "",
                     priority: int = 5) -> Dict[str, Any]:
    await init_db()
    jid = new_id()
    async with get_conn() as conn:
        await conn.execute(
            "INSERT INTO jobs (id,user_id,project_id,kind,status,provider,model,priority,payload_json,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (jid, user_id, project_id, kind, "queued", provider, model, priority,
             json.dumps(payload), _now()),
        )
        await conn.commit()
    return await get_job(jid)


async def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,))
        row = await cur.fetchone()
        return _row_to_dict(row) if row else None


async def list_jobs(project_id: Optional[str] = None, status: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
    async with get_conn() as conn:
        q = "SELECT * FROM jobs"
        clauses, vals = [], []
        if project_id:
            clauses.append("project_id=?")
            vals.append(project_id)
        if status:
            clauses.append("status=?")
            vals.append(status)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY created_at DESC LIMIT ?"
        vals.append(limit)
        cur = await conn.execute(q, vals)
        rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]


async def update_job(job_id: str, status: Optional[str] = None,
                     result: Optional[Dict] = None, error: str = "",
                     retry_count: Optional[int] = None) -> None:
    async with get_conn() as conn:
        if status == "processing":
            await conn.execute(
                "UPDATE jobs SET status=?, started_at=? WHERE id=?", (status, _now(), job_id)
            )
        elif status in ("complete", "failed"):
            await conn.execute(
                "UPDATE jobs SET status=?, result_json=?, error=?, finished_at=? WHERE id=?",
                (status, json.dumps(result or {}), error, _now(), job_id),
            )
        elif status:
            await conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        if retry_count is not None:
            await conn.execute("UPDATE jobs SET retry_count=? WHERE id=?", (retry_count, job_id))
        await conn.commit()
