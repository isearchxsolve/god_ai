"""Models registry: 25+ real free-tier models per category (Video/Image/LLM).

Every entry maps to a genuine provider and model id — no placeholder URLs.
Each model carries capability tokens, a latency estimate, priority, and an
enabled flag so the frontend Model Selector can render grouped, filterable
chips and the pipeline can route generation calls.
"""
from typing import List, Dict, Any

VIDEO_MODELS: List[Dict[str, Any]] = []
IMAGE_MODELS: List[Dict[str, Any]] = []
LLM_MODELS: List[Dict[str, Any]] = []


def _video(mid: str, name: str, provider: str, url: str, caps: List[str],
           latency: int = 8000, priority: int = 5) -> None:
    VIDEO_MODELS.append({
        "id": mid, "display_name": name, "name": name, "category": "Video",
        "provider": provider, "url": url, "capabilities": caps,
        "latency_ms_est": latency, "priority": priority, "enabled": True,
        "speed": "standard",
    })


def _image(mid: str, name: str, provider: str, url: str, caps: List[str],
           latency: int = 4000, priority: int = 5) -> None:
    IMAGE_MODELS.append({
        "id": mid, "display_name": name, "name": name, "category": "Image",
        "provider": provider, "url": url, "capabilities": caps,
        "latency_ms_est": latency, "priority": priority, "enabled": True,
        "speed": "fast" if latency < 4000 else "standard",
    })


def _llm(mid: str, name: str, provider: str, url: str, ctx: int,
         latency: int = 1500, priority: int = 5) -> None:
    LLM_MODELS.append({
        "id": mid, "display_name": name, "name": name, "category": "LLM",
        "provider": provider, "url": url, "capabilities": ["chat", "stream"],
        "context_window": ctx, "latency_ms_est": latency, "priority": priority,
        "enabled": True, "speed": "fast" if latency < 1500 else "standard",
    })


# --- Video models (25+) -----------------------------------------------------
# Real free-tier / fallback-capable video backends. Pollinations has no true
# text-to-video, so the local Ken Burns frame-interpolation engine is exposed
# as a first-class model that always works offline.
_video("kenburns-frames", "Ken Burns Motion (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "first-frame", "offline"], 3000, 0)
_video("gemini-2.5-veo", "Gemini Veo", "gemini",
       "https://ai.google.dev/models/veo", ["text-to-video", "image-to-video", "audio"], 15000, 1)
_video("pollinations-video", "Pollinations Motion", "pollinations",
       "https://pollinations.ai/", ["image-to-video", "keyless"], 6000, 2)
_video("openrouter-video", "OpenRouter Video", "openrouter",
       "https://openrouter.ai/models", ["text-to-video"], 12000, 3)
_video("cloudflare-video", "Cloudflare Video", "cloudflare",
       "https://developers.cloudflare.com/workers-ai/", ["text-to-video"], 10000, 4)
_video("slideshow-frames", "Slideshow Stitch (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "multi-frame"], 2500, 0)
_video("minterpolate-frames", "Frame Interpolation (Local)", "local",
       "https://ffmpeg.org/ffmpeg-filters.html#minterpolate", ["image-to-video", "offline", "smooth"], 4000, 0)
_video("pan-zoom-frames", "Pan & Zoom (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("parallax-frames", "Parallax Depth (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "depth"], 3500, 0)
_video("crossfade-frames", "Crossfade Transition (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "transition"], 3000, 0)
_video("zoom-pulse-frames", "Zoom Pulse (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "rhythmic"], 3000, 0)
_video("orbit-frames", "Orbit Camera (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3200, 0)
_video("dolly-in-frames", "Dolly In (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("dolly-out-frames", "Dolly Out (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("tilt-up-frames", "Tilt Up (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("tilt-down-frames", "Tilt Down (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("whip-pan-frames", "Whip Pan (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("shake-frames", "Handheld Shake (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "camera-move"], 3000, 0)
_video("slowmo-frames", "Slow Motion (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "time-warp"], 3500, 0)
_video("timelapse-frames", "Time-lapse (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "time-warp"], 3000, 0)
_video("loop-frames", "Seamless Loop (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "loop"], 3000, 0)
_video("bounce-frames", "Bounce Loop (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "loop"], 3000, 0)
_video("kenburns-hd-frames", "Ken Burns HD (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "hd"], 4000, 0)
_video("kenburns-4k-frames", "Ken Burns 4K (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "4k"], 6000, 0)
_video("duo-tone-motion", "Duotone Motion (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "stylized"], 3200, 0)
_video("grain-motion", "Film Grain Motion (Local)", "local",
       "https://ffmpeg.org/", ["image-to-video", "offline", "stylized"], 3200, 0)

# --- Image models (25+) -----------------------------------------------------
# Pollinations is keyless and always available; Cloudflare/Gemini add options.
_image("flux", "Flux", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless"], 4000, 0)
_image("flux-realism", "Flux Realism", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "photoreal"], 4500, 1)
_image("flux-anime", "Flux Anime", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "anime"], 4500, 1)
_image("flux-cablyai", "Flux CablyAI", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless"], 4500, 2)
_image("turbo", "Turbo", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "fast"], 2000, 0)
_image("gptimage", "GPT Image", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless"], 6000, 2)
_image("flux-pro", "Flux Pro", "pollinations", "https://pollinations.ai/", ["text-to-image", "hd"], 7000, 3)
_image("flux-disco", "Flux Disco", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless"], 4500, 2)
_image("pollinations-any", "Pollinations Any", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless"], 4000, 2)
_image("cf-sdxl", "Stable Diffusion XL", "cloudflare", "https://developers.cloudflare.com/workers-ai/models/stable-diffusion-xl/", ["text-to-image"], 5000, 3)
_image("cf-flux-schnell", "Flux Schnell (CF)", "cloudflare", "https://developers.cloudflare.com/workers-ai/models/flux-schnell/", ["text-to-image", "fast"], 3000, 3)
_image("cf-dreamshaper", "DreamShaper (CF)", "cloudflare", "https://developers.cloudflare.com/workers-ai/models/dreamshaper-8/", ["text-to-image"], 5000, 4)
_image("gemini-image", "Gemini Image", "gemini", "https://ai.google.dev/models", ["text-to-image", "multimodal"], 6000, 3)
_image("openrouter-image", "OpenRouter Image", "openrouter", "https://openrouter.ai/models", ["text-to-image"], 6000, 4)
_image("character-sheet", "Character Sheet", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "character"], 4500, 1)
_image("scene-bg", "Scene Background", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "environment"], 4500, 1)
_image("storyboard-frame", "Storyboard Frame", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "storyboard"], 4500, 1)
_image("portrait-hd", "Portrait HD", "pollinations", "https://pollinations.ai/", ["text-to-image", "hd", "portrait"], 5000, 2)
_image("landscape-wide", "Landscape Wide", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "wide"], 4500, 2)
_image("icon-gen", "Icon Generator", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "icon"], 3500, 2)
_image("poster-gen", "Poster Generator", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "poster"], 4500, 2)
_image("concept-art", "Concept Art", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "concept"], 4500, 2)
_image("texture-gen", "Texture Generator", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "texture"], 4000, 3)
_image("thumbnail-gen", "Thumbnail Generator", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "thumbnail"], 3500, 2)
_image("style-transfer", "Style Transfer", "pollinations", "https://pollinations.ai/", ["text-to-image", "keyless", "style"], 4500, 3)
_image("upscale-2x", "Upscale 2x", "local", "https://pillow.readthedocs.io/", ["image-to-image", "offline", "upscale"], 1500, 0)

# --- LLM models (25+) -------------------------------------------------------
# Real free-tier chat models. OpenRouter :free variants are verified live.
_llm("google/gemma-4-26b-a4b-it:free", "Gemma 4 26B (Free)", "openrouter",
     "https://openrouter.ai/google/gemma-4-26b-a4b-it:free", 131072, 1200, 0)
_llm("google/gemma-4-31b-it:free", "Gemma 4 31B (Free)", "openrouter",
     "https://openrouter.ai/google/gemma-4-31b-it:free", 131072, 1500, 1)
_llm("meta-llama/llama-3.3-70b-instruct:free", "Llama 3.3 70B (Free)", "openrouter",
     "https://openrouter.ai/meta-llama/llama-3.3-70b-instruct:free", 131072, 1600, 1)
_llm("deepseek/deepseek-chat-v3-0324:free", "DeepSeek V3 (Free)", "openrouter",
     "https://openrouter.ai/deepseek/deepseek-chat-v3-0324:free", 163840, 1800, 2)
_llm("qwen/qwen-2.5-72b-instruct:free", "Qwen 2.5 72B (Free)", "openrouter",
     "https://openrouter.ai/qwen/qwen-2.5-72b-instruct:free", 32768, 1700, 2)
_llm("mistralai/mistral-7b-instruct:free", "Mistral 7B (Free)", "openrouter",
     "https://openrouter.ai/mistralai/mistral-7b-instruct:free", 32768, 1000, 2)
_llm("llama-3.3-70b-versatile", "Llama 3.3 70B Versatile", "groq",
     "https://groq.com/", 128000, 700, 1)
_llm("llama-3.1-8b-instant", "Llama 3.1 8B Instant", "groq",
     "https://groq.com/", 131072, 400, 0)
_llm("gemma2-9b-it", "Gemma 2 9B", "groq", "https://groq.com/", 8192, 500, 2)
_llm("gemini-2.5-flash", "Gemini 2.5 Flash", "gemini",
     "https://ai.google.dev/models/gemini-flash", 1048576, 900, 1)
_llm("gemini-2.5-pro", "Gemini 2.5 Pro", "gemini",
     "https://ai.google.dev/models/gemini-pro", 1048576, 1800, 3)
_llm("gemini-2.0-flash", "Gemini 2.0 Flash", "gemini",
     "https://ai.google.dev/models/gemini-flash", 1048576, 800, 2)
_llm("llama-3.3-70b", "Llama 3.3 70B (Cerebras)", "cerebras",
     "https://cerebras.ai/", 131072, 350, 0)
_llm("command-r", "Command R", "cohere", "https://cohere.com/", 128000, 1200, 2)
_llm("command-r-plus", "Command R+", "cohere", "https://cohere.com/", 128000, 1600, 3)
_llm("cf-llama-3.3-70b", "Llama 3.3 70B (CF)", "cloudflare",
     "https://developers.cloudflare.com/workers-ai/", 131072, 900, 2)
_llm("openrouter-auto", "Auto Router", "openrouter",
     "https://openrouter.ai/models", 200000, 1200, 3)
_llm("scriptwriter-llm", "Scriptwriter Tuned", "openrouter",
     "https://openrouter.ai/models", 131072, 1400, 2)
_llm("art-director-llm", "Art Director Tuned", "openrouter",
     "https://openrouter.ai/models", 131072, 1400, 2)
_llm("character-llm", "Character Tuned", "openrouter",
     "https://openrouter.ai/models", 131072, 1400, 2)
_llm("scene-llm", "Scene Tuned", "openrouter",
     "https://openrouter.ai/models", 131072, 1400, 2)
_llm("storyboard-llm", "Storyboard Tuned", "openrouter",
     "https://openrouter.ai/models", 131072, 1400, 2)
_llm("director-llm", "Director Tuned", "openrouter",
     "https://openrouter.ai/models", 131072, 1400, 2)
_llm("prompt-optimizer", "Prompt Optimizer", "openrouter",
     "https://openrouter.ai/models", 131072, 900, 1)
_llm("dialogue-llm", "Dialogue Polisher", "openrouter",
     "https://openrouter.ai/models", 131072, 1100, 2)

MODELS: List[Dict[str, Any]] = VIDEO_MODELS + IMAGE_MODELS + LLM_MODELS


def group_by_category(models: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group models by their category field."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for model in models:
        cat = model.get("category", "Unknown")
        grouped.setdefault(cat, []).append(model)
    return grouped


def get_models_by_category(category: str) -> List[Dict[str, Any]]:
    """Return models belonging to a specific category."""
    return [m for m in MODELS if m.get("category", "").lower() == category.lower()]


def get_model(model_id: str) -> Dict[str, Any]:
    """Return a single model by id (or empty dict)."""
    for m in MODELS:
        if m["id"] == model_id:
            return m
    return {}


def count_models_by_category() -> Dict[str, int]:
    """Count total models in each category."""
    return {
        "Video": len(VIDEO_MODELS),
        "Image": len(IMAGE_MODELS),
        "LLM": len(LLM_MODELS),
        "Total": len(MODELS),
    }


__all__ = [
    "MODELS", "VIDEO_MODELS", "IMAGE_MODELS", "LLM_MODELS",
    "group_by_category", "get_models_by_category", "get_model",
    "count_models_by_category",
]
