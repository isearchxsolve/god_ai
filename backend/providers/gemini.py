"""Gemini adapter — Google AI Studio (free-tier multimodal).

Google AI Studio offers free-tier access to:
- Chat completions (Gemini 2.5 Flash / Pro) via ``generateContent``
- Image generation (Gemini 2.0 Flash experimental / Imagen 3)
- Video generation (Veo 2 via Long-running Operation) - NOTE: Veo may not be available in free tier
- Text-to-speech (Gemini TTS / Gemini Live)
- Embeddings (``text-embedding-004``)

No proprietary cloud dependencies — pure Google AI Studio endpoints.
"""
from __future__ import annotations

from typing import AsyncGenerator, List
import time

import httpx

from .base import (
    AIProviderAdapter,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    ImageGenerationRequest,
    ImageGenerationResponse,
    Model,
    ProviderHealth,
    ProviderStatus,
    VideoGenerationRequest,
    VideoGenerationResponse,
)


class GeminiAdapter(AIProviderAdapter):
    """Adapter for Google Gemini (AI Studio) free-tier endpoints."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL) -> None:
        if not api_key:
            raise ValueError("GeminiAdapter requires a non-empty api_key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.provider_name = "gemini"
        self.client = httpx.AsyncClient(
            headers={"Content-Type": "application/json"},
            timeout=120.0,
        )

    def get_provider_name(self) -> str:
        return self.provider_name

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        url = f"{self.base_url}/models/{request.model}:generateContent?key={self.api_key}"
        contents = [
            {
                "role": m["role"] if m["role"] != "assistant" else "model",
                "parts": [{"text": m["content"]}],
            }
            for m in request.messages
        ]
        payload = {"contents": contents}
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        usage = data.get("usageMetadata", {})
        return ChatCompletionResponse(
            id=data.get("id", "gemini-completion"),
            model=request.model,
            choices=[{
                "message": {"role": "assistant", "content": text},
                "finish_reason": data["candidates"][0].get("finishReason", "stop"),
            }],
            usage={
                "prompt_tokens": usage.get("promptTokenCount", 0),
                "completion_tokens": usage.get("candidatesTokenCount", 0),
                "total_tokens": usage.get("totalTokenCount", 0),
            },
        )

    async def chat_completion_stream(
        self, request: ChatCompletionRequest
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Stream chat completion deltas from Gemini via SSE.

        Gemini's ``streamGenerateContent`` endpoint returns an SSE stream of
        JSON objects; each contains incremental ``text`` deltas. We convert
        those to ``ChatCompletionChunk`` for parity with OpenAI.
        """
        url = f"{self.base_url}/models/{request.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        contents = [
            {
                "role": m["role"] if m["role"] != "assistant" else "model",
                "parts": [{"text": m["content"]}],
            }
            for m in request.messages
        ]
        payload = {"contents": contents}
        async with self.client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                chunk_data = line[5:].strip()
                if not chunk_data or chunk_data == "[DONE]":
                    continue
                try:
                    import json as _json
                    data = _json.loads(chunk_data)
                except Exception:
                    continue
                text = ""
                for cand in data.get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        if "text" in part:
                            text += part["text"]
                yield ChatCompletionChunk(
                    id=data.get("id", "gemini-stream"),
                    model=request.model,
                    delta={"role": "assistant", "content": text},
                    finish_reason=data["candidates"][0].get("finishReason") if data.get("candidates") else None,
                )

    async def generate_image(
        self, request: ImageGenerationRequest
    ) -> ImageGenerationResponse:
        url = f"{self.base_url}/models/{request.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        image_url = next(
            (p.get("text") or p.get("fileData", {}).get("fileUri", "") for p in parts),
            "",
        )
        return ImageGenerationResponse(data=[{"url": image_url, "prompt": request.prompt}])

    async def generate_video(
        self, request: VideoGenerationRequest
    ) -> VideoGenerationResponse:
        """
        Video generation using Google's Veo models.
        
        NOTE: As of the current free-tier offering, Veo video generation may not be
        available without enabling billing or using Vertex AI. For the free tier,
        we fall back to generating a keyframe image and indicating that motion
        should be applied in post-production.
        """
        # For now, we'll generate a keyframe image and note that this is a placeholder
        # for actual video generation. In a production setting with billing enabled,
        # this would call the actual Veo API.
        
        from .base import ImageGenerationRequest
        
        # Create an image generation request for the first frame
        img_request = ImageGenerationRequest(
            prompt=request.prompt,
            model="gemini-2.0-flash-exp",  # Use a multimodal model for image generation
            n=1,
            size="1280x720",  # HD landscape
        )
        
        # Generate the keyframe image
        img_response = await self.generate_image(img_request)
        
        # Return a video response that points to the keyframe
        # In a real implementation with billing, this would be a real video URL
        video_url = img_response.data[0]["url"] if img_response.data else ""
        
        # Add a note that this is a keyframe - in production with Veo, this would be actual video
        return VideoGenerationResponse(
            data=[{
                "url": video_url,
                "prompt": request.prompt,
                "note": "Keyframe generated - for actual video generation, enable billing and use Veo API"
            }]
        )

    async def create_embedding(
        self, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        url = f"{self.base_url}/models/text-embedding-004:embedContent?key={self.api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": request.input}]},
        }
        resp = await self.client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        vector = data["embedding"]["values"]
        return EmbeddingResponse(data=[{"embedding": vector}])

    async def list_models(self) -> List[Model]:
        return [
            Model(id="gemini-2.5-flash", owned_by="google"),
            Model(id="gemini-2.5-pro", owned_by="google"),
            Model(id="gemini-2.0-flash-exp", owned_by="google"),
            Model(id="gemini-2.5-veo", owned_by="google"),
            Model(id="text-embedding-004", owned_by="google"),
        ]

    async def health_check(self) -> ProviderHealth:
        try:
            url = f"{self.base_url}/models?key={self.api_key}"
            resp = await self.client.get(url, timeout=10.0)
            resp.raise_for_status()
            return ProviderHealth(
                status=ProviderStatus.HEALTHY,
                latency_ms=0.0,
                last_check=time.time(),
                error=""
            )
        except Exception as exc:  # pragma: no cover
            return ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                latency_ms=0.0,
                last_check=time.time(),
                error=str(exc)
            )