"""OpenRouter adapter — free-tier AI provider (OpenAI-compatible API).

Base URL: https://openrouter.ai/api/v1
Implements the AIProviderAdapter interface. NVIDIA NIM is NOT used.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Shared request/response contracts (also used by other adapters)
# ---------------------------------------------------------------------------
class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Dict[str, Any]]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Dict[str, Any]


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[Dict[str, Any]]


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str
    n: int = 1
    size: str = "1024x1024"
    response_format: str = "url"


class ImageGenerationResponse(BaseModel):
    created: int
    data: List[Dict[str, Any]]


class VideoGenerationRequest(BaseModel):
    prompt: str
    model: str
    first_frame: Optional[str] = None
    last_frame: Optional[str] = None


class VideoGenerationResponse(BaseModel):
    created: int
    data: List[Dict[str, Any]]


class EmbeddingRequest(BaseModel):
    input: Any
    model: str


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[Dict[str, Any]]
    model: str
    usage: Dict[str, Any]


class Model(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = ""


# ---------------------------------------------------------------------------
# Unified adapter interface
# ---------------------------------------------------------------------------
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRIES = 5


def backoff(attempt: int) -> float:
    """Exponential backoff with jitter, capped at 30s."""
    return min(30.0, 0.5 * (2 ** attempt))


class AIProviderAdapter(ABC):
    """Unified interface every free-tier provider must implement."""

    @abstractmethod
    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        ...

    @abstractmethod
    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        ...

    @abstractmethod
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        ...

    @abstractmethod
    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        ...

    @abstractmethod
    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...

    @abstractmethod
    async def list_models(self) -> List[Model]:
        ...

    @abstractmethod
    def get_provider_name(self) -> str:
        ...


# ---------------------------------------------------------------------------
# OpenRouter implementation
# ---------------------------------------------------------------------------
class OpenRouterAdapter(AIProviderAdapter):
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": "https://oioii.ai",
                "X-Title": "OiiOii.ai Clone",
            },
        )

    async def _request_with_retry(self, method: str, path: str, json: Optional[dict] = None) -> httpx.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = await self.client.request(method, path, json=json)
                if resp.status_code in RETRY_STATUS and attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff(attempt))
                    continue
                resp.raise_for_status()
                return resp
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(backoff(attempt))
                    continue
                raise
        raise last_exc  # type: ignore[misc]

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        resp = await self._request_with_retry("POST", "/chat/completions", request.model_dump())
        return ChatCompletionResponse(**resp.json())

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        async with self.client.stream(
            "POST", "/chat/completions", json=request.model_dump()
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    yield ChatCompletionChunk.model_validate_json(data)

    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        resp = await self._request_with_retry("POST", "/images/generations", request.model_dump())
        return ImageGenerationResponse(**resp.json())

    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        resp = await self._request_with_retry("POST", "/videos/generations", request.model_dump())
        return VideoGenerationResponse(**resp.json())

    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        resp = await self._request_with_retry("POST", "/embeddings", request.model_dump())
        return EmbeddingResponse(**resp.json())

    async def list_models(self) -> List[Model]:
        resp = await self._request_with_retry("GET", "/models")
        data = resp.json()
        return [Model(**m) for m in data.get("data", [])]

    def get_provider_name(self) -> str:
        return "openrouter"
