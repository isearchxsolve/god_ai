from __future__ import annotations
import asyncio
from typing import Any, AsyncGenerator, List, Dict
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
import time
from providers.base import (
    AIProviderAdapter,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChunk,
    ImageGenerationRequest,
    ImageGenerationResponse,
    VideoGenerationRequest,
    VideoGenerationResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    Model,
    ProviderHealth,
    ProviderStatus,
)


class OpenRouterAdapter(AIProviderAdapter):
    def __init__(self, api_key: str, base_url: str = 'https://openrouter.ai/api/v1'):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.provider_name = 'openrouter'

    async def chat_completion(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        response = await self.client.chat.completions.create(**request.dict())
        return ChatCompletionResponse(**response.dict())

    async def chat_completion_stream(self, request: ChatCompletionRequest) -> AsyncGenerator[ChatCompletionChunk, None]:
        async for chunk in await self.client.chat.completions.create(stream=True, **request.dict()):
            yield ChatCompletionChunk(**chunk.dict())

    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        # OpenRouter uses OpenAI-compatible image generation via DALL-E or Stable Diffusion via model param
        # For simplicity, we assume a compatible endpoint; adjust as needed
        response = await self.client.images.generate(**request.dict())
        return ImageGenerationResponse(**response.dict())

    async def generate_video(self, request: VideoGenerationRequest) -> VideoGenerationResponse:
        # OpenRouter may not have video generation; we raise NotImplementedError or return empty
        raise NotImplementedError('Video generation not supported by OpenRouter adapter')

    async def create_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        response = await self.client.embeddings.create(**request.dict())
        return EmbeddingResponse(**response.dict())

    async def list_models(self) -> List[Model]:
        models = await self.client.models.list()
        return [Model(**m.dict()) for m in models.data]

    async def health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            await self.client.models.list()
            latency = (time.time() - start) * 1000
            return ProviderHealth(status=ProviderStatus.HEALTHY, latency_ms=latency, last_check=time.time(), error='')
        except Exception as e:
            return ProviderHealth(status=ProviderStatus.UNHEALTHY, latency_ms=0.0, last_check=time.time(), error=str(e))

    def get_provider_name(self) -> str:
        return self.provider_name