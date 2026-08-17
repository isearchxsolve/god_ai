"""Chat endpoints: OpenAI-compatible completions + SSE streaming."""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent_pipeline import chat_models_for, call_chat_with_failover
from app.core.auth import get_current_user
from app.services.provider_service import get_provider_registry

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    stream: Optional[bool] = False


@router.post("/completions")
async def create_chat_completion(request: ChatCompletionRequest,
                                 user: dict = Depends(get_current_user)):
    """Chat completion routed through the free-tier ProviderRegistry with failover."""
    registry = await get_provider_registry()
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        result = await call_chat_with_failover(
            registry, messages,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 4096,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Chat generation failed: {exc}")

    return {
        "id": "chatcmpl-oioi",
        "object": "chat.completion",
        "model": result["model"],
        "provider": result["provider"],
        "choices": [{"index": 0,
                     "message": {"role": "assistant", "content": result["content"]},
                     "finish_reason": "stop"}],
    }


@router.get("/stream")
async def stream_chat(prompt: str, model: Optional[str] = None,
                      user: dict = Depends(get_current_user)):
    """SSE streaming chat. Streams real tokens when the provider supports it,
    otherwise streams the completed response word-by-word."""
    registry = await get_provider_registry()

    async def event_generator():
        try:
            # Try true token streaming from the best chat adapter, walking each
            # provider's model fallback chain (free-tier models rotate in and
            # out of rate limits constantly).
            streamed = False
            candidates = registry._candidates("chat")
            for rec in candidates:
                adapter = await registry.get_adapter("chat", prefer=rec.name)
                name = getattr(adapter, "provider_name", rec.name) or rec.name
                model_chain = [model] if model else chat_models_for(name)
                provider_failed = False
                for chat_model in model_chain:
                    from providers.base import ChatCompletionRequest as AdapterReq
                    req = AdapterReq(model=chat_model,
                                     messages=[{"role": "user", "content": prompt}],
                                     stream=True)
                    try:
                        async for chunk in adapter.chat_completion_stream(req):
                            data = chunk.model_dump() if hasattr(chunk, "model_dump") else dict(chunk)
                            delta = (data.get("choices") or [{}])[0].get("delta", {})
                            content = delta.get("content")
                            if content is None:
                                msg = (data.get("choices") or [{}])[0].get("message", {})
                                content = msg.get("content")
                            if content:
                                yield f"data: {json.dumps({'delta': {'content': content}})}\n\n"
                        registry.report_success(name)
                        streamed = True
                        break
                    except NotImplementedError:
                        provider_failed = True
                        break
                    except Exception:
                        continue
                if streamed:
                    break
                if not provider_failed:
                    registry.report_failure(name, "all streaming models failed")

            if not streamed:
                result = await call_chat_with_failover(
                    registry, [{"role": "user", "content": prompt}])
                for word in result["content"].split(" "):
                    yield f"data: {json.dumps({'delta': {'content': word + ' '}})}\n\n"

            yield "data: [DONE]\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
