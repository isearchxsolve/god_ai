"""Chat SSE streaming endpoint for the dual-mode creation shell.

Exposes ``POST /v1/chat/stream`` which consumes the 7-agent animation
pipeline and streams agent status bubbles + token deltas back to the
Expo frontend via Server-Sent Events.  Mirrors the contract described in
ARCHITECTURE.md (``ChatInterface.tsx`` subscribes to this stream).
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import AsyncIterator, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.pipeline import (
    AgentRole,
    PipelineContext,
    PipelineRunner,
    build_default_pipeline,
)

router = APIRouter(prefix="/v1/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., description="user | assistant | agent")
    content: str
    agent: Optional[str] = None


class ChatStreamRequest(BaseModel):
    session_id: Optional[str] = None
    idea: str = Field(..., min_length=1, max_length=4000)
    style_id: Optional[str] = None
    model_ids: Optional[List[str]] = None
    history: List[ChatMessage] = Field(default_factory=list)


def _sse_event(event: str, data: Dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


async def _stream_pipeline(req: ChatStreamRequest) -> AsyncIterator[str]:
    session_id = req.session_id or str(uuid.uuid4())
    yield _sse_event("session.start", {"session_id": session_id})

    ctx = PipelineContext(
        session_id=session_id,
        idea=req.idea,
        style_id=req.style_id,
        model_ids=req.model_ids or [],
    )
    runner = build_default_pipeline()

    for role in runner.order:
        agent = runner.factory.build(role)
        yield _sse_event(
            "agent.start",
            {"agent": role.value, "status": "running"},
        )
        try:
            output = await asyncio.to_thread(agent.run, ctx)
            ctx.history.append({"agent": role.value, "output": output.payload})
            yield _sse_event(
                "agent.token",
                {"agent": role.value, "token": output.payload[:120]},
            )
            yield _sse_event(
                "agent.done",
                {"agent": role.value, "status": output.status, "ms": output.elapsed_ms},
            )
        except Exception as exc:  # pragma: no cover - defensive
            yield _sse_event(
                "agent.error",
                {"agent": role.value, "error": str(exc)},
            )
            raise

    yield _sse_event("session.end", {"session_id": session_id, "ok": True})


@router.post("/stream", response_class=StreamingResponse)
async def chat_stream(req: ChatStreamRequest, request: Request) -> StreamingResponse:
    if not req.idea.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idea must not be empty",
        )
    return StreamingResponse(
        _stream_pipeline(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict:
    return {"session_id": session_id, "status": "ok", "ts": int(time.time())}
