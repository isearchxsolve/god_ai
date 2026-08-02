from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json

from app.services.provider_service import get_provider_registry

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "gemini-2.5-flash"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 4096
    stream: Optional[bool] = False


@router.post("/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    """Chat completion routed through free-tier ProviderRegistry."""
    registry = await get_provider_registry()
    try:
        adapter = await registry.get_adapter("chat")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No available chat provider: {e}")

    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    try:
        resp = await adapter.chat_completion(
            messages=messages,
            model=request.model or "gemini-2.5-flash",
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 4096,
            stream=request.stream or False,
        )
        registry.report_success(adapter.provider_name)
        if isinstance(resp, dict):
            return resp
        return {"choices": [{"message": {"role": "assistant", "content": str(resp)}}]}
    except Exception as e:
        registry.report_failure(adapter.provider_name, error=e)
        raise HTTPException(status_code=502, detail=f"Provider {adapter.provider_name} error: {e}")


@router.get("/stream")
async def stream_chat(prompt: str, model: Optional[str] = "gemini-2.5-flash"):
    """SSE streaming chat response for real-time frontend canvas interaction."""
    registry = await get_provider_registry()
    try:
        adapter = await registry.get_adapter("chat")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No chat provider available: {e}")

    async def event_generator():
        messages = [{"role": "user", "content": prompt}]
        try:
            resp = await adapter.chat_completion(
                messages=messages,
                model=model or "gemini-2.5-flash",
                stream=False,
            )
            registry.report_success(adapter.provider_name)
            # Yield content tokens
            text = resp.get("choices", [{}])[0].get("message", {}).get("content", "") if isinstance(resp, dict) else str(resp)
            words = text.split(" ")
            for w in words:
                chunk = {"delta": {"content": w + " "}}
                yield f"data: {json.dumps(chunk)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            registry.report_failure(adapter.provider_name, error=e)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
