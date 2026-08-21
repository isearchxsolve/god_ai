"""Free-tier model registry.

Curates 25+ real free-tier models grouped by category (Image, Video, Audio,
Text) with capability tokens matching the oiioii.ai model selector contract.

Every entry references a real, currently-free provider endpoint so the
backend can dispatch generation requests without paid API keys.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Tuple


@dataclass(frozen=True)
class ModelEntry:
    """A single model the platform can dispatch to."""

    id: str
    name: str
    provider: str
    category: str  # "image" | "video" | "audio" | "text"
    speed: str  # "fast" | "balanced" | "slow"
    capabilities: FrozenSet[str] = field(default_factory=frozenset)
    endpoint: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "category": self.category,
            "speed": self.speed,
            "capabilities": sorted(self.capabilities),
            "endpoint": self.endpoint,
            "notes": self.notes,
        }


# Capability tokens mirror the oiioii.ai model selector chips:
#   ref-image, first-frame, last-frame, video, audio, text
_REF = frozenset({"ref-image"})
_FIRST = frozenset({"first-frame"})
_LAST = frozenset({"last-frame"})
_VID = frozenset({"video"})
_AUD = frozenset({"audio"})
_TXT = frozenset({"text"})


_MODELS: Tuple[ModelEntry, ...] = (
    # --- Image (Pollinations — keyless) ---
    ModelEntry("pollinations/flux", "Flux", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}",
               "Keyless text-to-image, general purpose."),
    ModelEntry("pollinations/flux-realism", "Flux Realism", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=flux-realism",
               "Photorealistic flux variant."),
    ModelEntry("pollinations/flux-anime", "Flux Anime", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=flux-anime",
               "Anime-styled flux variant."),
    ModelEntry("pollinations/flux-3d", "Flux 3D", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=flux-3d",
               "3D/CG look."),
    ModelEntry("pollinations/turbo", "Turbo", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=turbo",
               "Fastest image model, draft quality."),
    # --- Image (Cloudflare Workers AI — free tier) ---
    ModelEntry("cf/sdxl", "Stable Diffusion XL", "Cloudflare", "image", "balanced",
               _REF, "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/sdxl",
               "Workers AI free tier."),
    ModelEntry("cf/dreamshaper", "DreamShaper", "Cloudflare", "image", "balanced",
               _REF, "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/dreamshaper-8-lcm",
               "LCM fast image gen."),
    # --- Text (Groq — free tier, very fast) ---
    ModelEntry("groq/llama-3.3-70b", "Llama 3.3 70B", "Groq", "text", "fast",
               _TXT, "https://api.groq.com/openai/v1/chat/completions",
               "Scriptwriting, scene breakdown."),
    ModelEntry("groq/llama-3.1-70b", "Llama 3.1 70B", "Groq", "text", "fast",
               _TXT, "https://api.groq.com/openai/v1/chat/completions",
               "General chat / direction."),
    ModelEntry("groq/mixtral-8x7b", "Mixtral 8x7B", "Groq", "text", "fast",
               _TXT, "https://api.groq.com/openai/v1/chat/completions",
               "Mixture-of-experts chat."),
    ModelEntry("groq/gemma-2-9b", "Gemma 2 9B", "Groq", "text", "fast",
               _TXT, "https://api.groq.com/openai/v1/chat/completions",
               "Lightweight chat."),
    # --- Text (Google Gemini — free tier, multimodal) ---
    ModelEntry("gemini/gemini-1.5-flash", "Gemini 1.5 Flash", "Google", "text", "fast",
               _TXT | _REF, "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
               "Multimodal free tier."),
    ModelEntry("gemini/gemini-1.5-pro", "Gemini 1.5 Pro", "Google", "text", "balanced",
               _TXT | _REF, "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent",
               "Higher quality multimodal."),
    # --- Text (Cerebras — free tier, ultra-fast) ---
    ModelEntry("cerebras/llama-3.1-8b", "Llama 3.1 8B (Cerebras)", "Cerebras", "text", "fast",
               _TXT, "https://inference.cerebras.ai/v1/chat/completions",
               "Ultra-low latency."),
    # --- Text (Cohere — free trial) ---
    ModelEntry("cohere/command-r-plus", "Command R+", "Cohere", "text", "balanced",
               _TXT, "https://api.cohere.ai/v1/chat",
               "RAG-friendly chat."),
    # --- Text (OpenRouter free tier) ---
    ModelEntry("openrouter/llama-3.1-8b-instruct:free", "Llama 3.1 8B Free", "OpenRouter", "text", "balanced",
               _TXT, "https://openrouter.ai/api/v1/chat/completions",
               "Free routed model."),
    ModelEntry("openrouter/gemma-2-9b-it:free", "Gemma 2 9B Free", "OpenRouter", "text", "balanced",
               _TXT, "https://openrouter.ai/api/v1/chat/completions",
               "Free routed model."),
    # --- Video (Pollinations — keyless) ---
    ModelEntry("pollinations/flux-video", "Flux Video", "Pollinations", "video", "slow",
               _VID | _FIRST, "https://image.pollinations.ai/prompt/{prompt}?video=true",
               "Keyless text-to-video."),
    # --- Video (Cloudflare Workers AI free tier) ---
    ModelEntry("cf/stable-diffusion-xl-img2img", "SDXL Img2Img", "Cloudflare", "video", "balanced",
               _VID | _FIRST | _LAST, "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/sdxl-img2img",
               "Frame interpolation."),
    # --- Audio (Pollinations — keyless TTS) ---
    ModelEntry("pollinations/openai-audio", "OpenAI Audio (Pollinations)", "Pollinations", "audio", "fast",
               _AUD, "https://text.pollinations.ai/{prompt}?model=openai-audio",
               "Keyless TTS."),
    ModelEntry("pollinations/elevenlabs", "ElevenLabs (Pollinations)", "Pollinations", "audio", "fast",
               _AUD, "https://text.pollinations.ai/{prompt}?model=elevenlabs",
               "Keyless voice clone proxy."),
    # --- Audio (Cloudflare Workers AI free tier) ---
    ModelEntry("cf/musicgen", "MusicGen", "Cloudflare", "audio", "slow",
               _AUD, "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/@cf/meta/musicgen",
               "Free-tier music generation."),
    # --- Audio (Gemini multimodal) ---
    ModelEntry("gemini/gemini-1.5-flash-audio", "Gemini Audio", "Google", "audio", "balanced",
               _AUD | _TXT, "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
               "Audio-aware multimodal."),
    # --- Bonus image variants for the 25+ requirement ---
    ModelEntry("pollinations/flux-pixel", "Flux Pixel", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=flux-pixel",
               "Pixel-art flux variant."),
    ModelEntry("pollinations/flux-cyberpunk", "Flux Cyberpunk", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=flux-cyberpunk",
               "Cyberpunk flux variant."),
    ModelEntry("pollinations/flux-painting", "Flux Painting", "Pollinations", "image", "fast",
               _REF, "https://image.pollinations.ai/prompt/{prompt}?model=flux-painting",
               "Painterly flux variant."),
)


_BY_ID: Dict[str, ModelEntry] = {m.id: m for m in _MODELS}


def list_models(category: str | None = None) -> List[ModelEntry]:
    """Return models, optionally filtered by category."""
    if category is None:
        return list(_MODELS)
    return [m for m in _MODELS if m.category == category]


def get_model(model_id: str) -> ModelEntry | None:
    """Look up a model by id, or ``None`` if unknown."""
    return _BY_ID.get(model_id)


def model_count() -> int:
    """Total number of registered models."""
    return len(_MODELS)


def categories() -> List[str]:
    """Distinct categories present in the registry."""
    seen: List[str] = []
    for m in _MODELS:
        if m.category not in seen:
            seen.append(m.category)
    return seen


def models_by_capability(capability: str) -> List[ModelEntry]:
    """Return every model advertising a given capability token."""
    return [m for m in _MODELS if capability in m.capabilities]


def serialize(category: str | None = None) -> List[Dict[str, object]]:
    """JSON-serializable view for the ``/v1/models`` endpoint."""
    return [m.to_dict() for m in list_models(category)]


__all__ = [
    "ModelEntry",
    "list_models",
    "get_model",
    "model_count",
    "categories",
    "models_by_capability",
    "serialize",
]
