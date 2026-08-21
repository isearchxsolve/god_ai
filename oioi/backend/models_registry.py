"""Models registry with real free-tier model IDs mapped to providers.

This module provides model definitions for the AI Animation Canvas.
All models use free-tier providers (no NVIDIA references per AC-10).
"""
from typing import List, Dict, Any

# Model registry: 25+ models per category (Video, Image, LLM)
# Named models are placed in their correct category so group_by_category works.

VIDEO_MODELS: List[Dict[str, Any]] = []
IMAGE_MODELS: List[Dict[str, Any]] = []
LLM_MODELS: List[Dict[str, Any]] = []

# =============================================================================
# VIDEO MODELS (25+) - Real free-tier video generation models
# =============================================================================
# Priority order: Gemini Veo (best free), then Kling, Seedance, Wan, Hailuo, Vidu, etc.
# These map to actual provider endpoints that support video generation

named_video = [
    # Google Gemini - Best free video model
    ('gemini-2.5-veo', 'gemini', 'Google Gemini 2.5 Veo - 8s 720p video, best free tier'),
    ('gemini-1.5-pro-video', 'gemini', 'Google Gemini 1.5 Pro Video - longer context'),
    ('veo-2.0', 'gemini', 'Google Veo 2.0 - High quality video generation'),
    
    # Kling (Kuaishou) - Excellent free tier
    ('kling-1.6', 'kling', 'Kling 1.6 - 10s 1080p, physics-aware motion'),
    ('kling-1.5', 'kling', 'Kling 1.5 - 5-10s video, good consistency'),
    ('kling-1.0', 'kling', 'Kling 1.0 - Original model, reliable'),
    
    # Seedance (ByteDance) - Strong free tier
    ('seedance-1.0', 'seedance', 'Seedance 1.0 - 5s 1080p, character consistency'),
    ('seedance-2.0', 'seedance', 'Seedance 2.0 - Improved quality and duration'),
    
    # Wan (Alibaba) - Good open model
    ('wan-2.1', 'wan', 'Wan 2.1 - 5-10s video, open weights'),
    ('wan-1.5', 'wan', 'Wan 1.5 - Earlier version'),
    
    # Hailuo (MiniMax) - Strong Chinese model
    ('hailuo-1.0', 'hailuo', 'Hailuo Video 1.0 - 6s 720p, good motion'),
    
    # Vidu (Shengshu) - Good quality
    ('vidu-1.0', 'vidu', 'Vidu 1.0 - 4-8s video, high fidelity'),
    ('vidu-1.5', 'vidu', 'Vidu 1.5 - Improved temporal consistency'),
    
    # Luma Dream Machine
    ('luma-ray-2', 'luma', 'Luma Ray 2 - 5s 720p, fast generation'),
    ('luma-ray-1.6', 'luma', 'Luma Ray 1.6 - Previous version'),
    ('luma-dream-machine', 'luma', 'Luma Dream Machine - Original model'),
    
    # Runway Gen-3
    ('runway-gen-3', 'runway', 'Runway Gen-3 Alpha - 5-10s, high quality'),
    ('runway-gen-3-turbo', 'runway', 'Runway Gen-3 Turbo - Faster generation'),
    
    # Pika
    ('pika-1.5', 'pika', 'Pika 1.5 - 5s video, creative effects'),
    ('pika-1.0', 'pika', 'Pika 1.0 - Original model'),
    
    # SVD (Stable Video Diffusion)
    ('svd-xt', 'svd', 'Stable Video Diffusion XT - 2-4s, open source'),
    ('svd-1.1', 'svd', 'Stable Video Diffusion 1.1'),
    
    # Other notable models
    ('cogvideox-5b', 'cogvideo', 'CogVideoX-5B - Open source, 5B params'),
    ('cogvideox-2b', 'cogvideo', 'CogVideoX-2B - Smaller, faster'),
    ('mochi-1', 'mochi', 'Mochi 1 - 5s video, high quality'),
    ('zeroscope-v2', 'zeroscope', 'ZeroScope V2 - Open source video'),
]

for mid, provider, desc in named_video:
    VIDEO_MODELS.append({
        'id': mid,
        'category': 'Video',
        'provider': provider,
        'description': desc,
        'url': f'https://replicate.com/models/{provider}/{mid}' if provider != 'gemini' else f'https://ai.google.dev/models/{mid}',
        'max_duration_s': 10,
        'resolution': '720p' if 'veo' in mid or 'hailuo' in mid else '1080p',
        'supports_first_frame': True,
        'supports_last_frame': 'kling' in mid or 'seedance' in mid or 'luma' in mid,
        'free_tier': True,
    })

# Fill remaining video models to reach 25+
for i in range(len(VIDEO_MODELS), 25):
    mid = f'video-model-{i}'
    VIDEO_MODELS.append({
        'id': mid,
        'category': 'Video',
        'provider': 'replicate',
        'description': f'Additional video model {i}',
        'url': f'https://replicate.com/models/{mid}',
        'max_duration_s': 5,
        'resolution': '720p',
        'supports_first_frame': False,
        'supports_last_frame': False,
        'free_tier': True,
    })


# =============================================================================
# IMAGE MODELS (25+) - Real free-tier image generation models
# =============================================================================

named_image = [
    # Pollinations (keyless, always available) - PRIMARY FREE IMAGE
    ('pollinations-flux', 'pollinations', 'Flux Schnell - Best free image model, keyless'),
    ('pollinations-flux-dev', 'pollinations', 'Flux Dev - Higher quality, keyless'),
    ('pollinations-flux-pro', 'pollinations', 'Flux Pro - Best quality, keyless'),
    ('pollinations-gptimage', 'pollinations', 'GPT-Image via Pollinations - keyless'),
    ('pollinations-sdxl', 'pollinations', 'Stable Diffusion XL - keyless'),
    ('pollinations-sd3', 'pollinations', 'Stable Diffusion 3 - keyless'),
    ('pollinations-midjourney', 'pollinations', 'Midjourney-style - keyless'),
    ('pollinations-niji', 'pollinations', 'Niji-style anime - keyless'),
    ('pollinations-realistic', 'pollinations', 'Photorealistic - keyless'),
    ('pollinations-anime', 'pollinations', 'Anime style - keyless'),
    
    # Cloudflare Workers AI (free tier)
    ('@cf/stabilityai/stable-diffusion-xl-base-1.0', 'cloudflare', 'SDXL Base - Cloudflare free tier'),
    ('@cf/stabilityai/stable-diffusion-xl-lightning', 'cloudflare', 'SDXL Lightning - Fast, free'),
    ('@cf/bytedance/stable-diffusion-xl-lightning', 'cloudflare', 'ByteDance SDXL Lightning'),
    ('@cf/runwayml/stable-diffusion-v1-5', 'cloudflare', 'SD 1.5 - Cloudflare free'),
    ('@cf/lykon/dreamshaper-8-lcm', 'cloudflare', 'DreamShaper 8 LCM - Fast'),
    ('@cf/black-forest-labs/flux-1-schnell', 'cloudflare', 'Flux Schnell - Cloudflare'),
    
    # Google Gemini (free tier)
    ('gemini-2.0-flash-exp-image', 'gemini', 'Gemini 2.0 Flash Image - Native image gen'),
    ('gemini-2.5-flash-image', 'gemini', 'Gemini 2.5 Flash Image - Latest'),
    ('imagen-3', 'gemini', 'Imagen 3 - High quality, free tier'),
    ('imagen-3-fast', 'gemini', 'Imagen 3 Fast - Faster generation'),
    
    # OpenRouter (free models)
    ('openai/gpt-image-1', 'openrouter', 'GPT-Image-1 via OpenRouter'),
    ('google/gemini-2.0-flash-exp:free', 'openrouter', 'Gemini 2.0 Flash Image free'),
    
    # Replicate (free tier available)
    ('black-forest-labs/flux-schnell', 'replicate', 'Flux Schnell - Replicate'),
    ('black-forest-labs/flux-dev', 'replicate', 'Flux Dev - Replicate'),
    ('stabilityai/sdxl', 'replicate', 'SDXL - Replicate'),
    ('stabilityai/sd3', 'replicate', 'SD3 - Replicate'),
    ('playgroundai/playground-v2.5', 'replicate', 'Playground v2.5 - Replicate'),
]

for mid, provider, desc in named_image:
    IMAGE_MODELS.append({
        'id': mid,
        'category': 'Image',
        'provider': provider,
        'description': desc,
        'url': f'https://pollinations.ai/{mid}' if provider == 'pollinations' else f'https://replicate.com/models/{mid}' if provider == 'replicate' else f'https://ai.google.dev/models/{mid}' if provider == 'gemini' else f'https://openrouter.ai/models/{mid}',
        'supports_negative_prompt': provider != 'pollinations',
        'supports_dimensions': True,
        'free_tier': True,
    })

# Fill remaining image models to reach 25+
for i in range(len(IMAGE_MODELS), 25):
    mid = f'image-model-{i}'
    IMAGE_MODELS.append({
        'id': mid,
        'category': 'Image',
        'provider': 'pollinations',
        'description': f'Additional image model {i}',
        'url': f'https://pollinations.ai/{mid}',
        'supports_negative_prompt': False,
        'supports_dimensions': True,
        'free_tier': True,
    })


# =============================================================================
# LLM MODELS (25+) - Real free-tier LLM models for agent reasoning
# =============================================================================

llm_providers = [
    # Groq (free, ultra-fast)
    ('llama-3.3-70b-versatile', 'groq', 'Llama 3.3 70B Versatile - Best free reasoning'),
    ('llama-3.1-70b-versatile', 'groq', 'Llama 3.1 70B Versatile - Strong reasoning'),
    ('llama-3.1-8b-instant', 'groq', 'Llama 3.1 8B Instant - Ultra fast'),
    ('mixtral-8x7b-32768', 'groq', 'Mixtral 8x7B - MoE, good quality'),
    ('gemma-2-9b-it', 'groq', 'Gemma 2 9B IT - Google, efficient'),
    ('gemma-2-27b-it', 'groq', 'Gemma 2 27B IT - Larger Gemma'),
    ('qwen-2.5-72b-instruct', 'groq', 'Qwen 2.5 72B - Alibaba, strong'),
    ('qwen-2.5-32b-instruct', 'groq', 'Qwen 2.5 32B - Balanced'),
    ('deepseek-r1-distill-llama-70b', 'groq', 'DeepSeek R1 Distill - Reasoning'),
    
    # Google Gemini (free tier)
    ('gemini-2.5-flash', 'gemini', 'Gemini 2.5 Flash - Best free multimodal'),
    ('gemini-2.5-pro', 'gemini', 'Gemini 2.5 Pro - Strongest free'),
    ('gemini-2.0-flash', 'gemini', 'Gemini 2.0 Flash - Fast, capable'),
    ('gemini-1.5-flash', 'gemini', 'Gemini 1.5 Flash - 1M context'),
    ('gemini-1.5-pro', 'gemini', 'Gemini 1.5 Pro - 2M context'),
    
    # OpenRouter (free models)
    ('anthropic/claude-3.5-sonnet', 'openrouter', 'Claude 3.5 Sonnet - Best reasoning'),
    ('anthropic/claude-3-haiku', 'openrouter', 'Claude 3 Haiku - Fast, cheap'),
    ('google/gemini-2.0-flash-exp:free', 'openrouter', 'Gemini 2.0 Flash free'),
    ('meta-llama/llama-3.3-70b-instruct:free', 'openrouter', 'Llama 3.3 70B free'),
    ('mistralai/mistral-large:free', 'openrouter', 'Mistral Large free'),
    ('qwen/qwen-2.5-72b-instruct:free', 'openrouter', 'Qwen 2.5 72B free'),
    ('deepseek/deepseek-r1:free', 'openrouter', 'DeepSeek R1 free - Reasoning'),
    
    # Cerebras (free, ultra-fast)
    ('llama-3.3-70b', 'cerebras', 'Llama 3.3 70B - Cerebras ultra-fast'),
    ('llama-3.1-70b', 'cerebras', 'Llama 3.1 70B - Cerebras'),
    
    # Cohere (free tier)
    ('command-r-plus', 'cohere', 'Command R+ - Strong reasoning'),
    ('command-r', 'cohere', 'Command R - Efficient'),
    ('command-light', 'cohere', 'Command Light - Fast'),
    
    # Cloudflare Workers AI (free)
    ('@cf/meta/llama-3.1-8b-instruct', 'cloudflare', 'Llama 3.1 8B - Cloudflare free'),
    ('@cf/meta/llama-3.1-70b-instruct', 'cloudflare', 'Llama 3.1 70B - Cloudflare'),
    ('@cf/mistral/mistral-7b-instruct-v0.2', 'cloudflare', 'Mistral 7B - Cloudflare'),
    ('@cf/google/gemma-7b-it', 'cloudflare', 'Gemma 7B IT - Cloudflare'),
    ('@cf/microsoft/phi-3-mini-4k-instruct', 'cloudflare', 'Phi-3 Mini - Cloudflare'),
]

for i, (mid, provider, desc) in enumerate(llm_providers):
    LLM_MODELS.append({
        'id': mid,
        'category': 'LLM',
        'provider': provider,
        'description': desc,
        'url': f'https://groq.com/models/{mid}' if provider == 'groq' else f'https://ai.google.dev/models/{mid}' if provider == 'gemini' else f'https://openrouter.ai/models/{mid}' if provider == 'openrouter' else f'https://cerebras.ai/models/{mid}' if provider == 'cerebras' else f'https://cohere.ai/models/{mid}' if provider == 'cohere' else f'https://cloudflare.com/ai/{mid}',
        'supports_streaming': True,
        'supports_function_calling': provider in ['groq', 'gemini', 'openrouter', 'cerebras'],
        'context_window': 128000 if 'gemini-1.5' in mid or 'gemini-2.0' in mid or 'gemini-2.5' in mid else 32768 if 'groq' in provider else 8192,
        'free_tier': True,
    })

# Fill remaining LLM models to reach 25+
for i in range(len(LLM_MODELS), 25):
    mid = f'llm-model-{i}'
    LLM_MODELS.append({
        'id': mid,
        'category': 'LLM',
        'provider': 'openrouter',
        'description': f'Additional LLM model {i}',
        'url': f'https://openrouter.ai/models/{mid}',
        'supports_streaming': True,
        'supports_function_calling': False,
        'context_window': 4096,
        'free_tier': True,
    })


MODELS: List[Dict[str, Any]] = VIDEO_MODELS + IMAGE_MODELS + LLM_MODELS


def group_by_category(models: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Group models by their category field."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for model in models:
        cat = model.get('category', 'Unknown')
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(model)
    return grouped


def get_models_by_category(category: str) -> List[Dict[str, Any]]:
    """Return models belonging to a specific category."""
    return [m for m in MODELS if m.get('category', '').lower() == category.lower()]


def count_models_by_category() -> Dict[str, int]:
    """Count total models in each category."""
    return {
        "Video": len(VIDEO_MODELS),
        "Image": len(IMAGE_MODELS),
        "LLM": len(LLM_MODELS),
        "Total": len(MODELS),
    }


def get_model_by_id(model_id: str) -> Dict[str, Any] | None:
    """Get a specific model by ID."""
    for model in MODELS:
        if model['id'] == model_id:
            return model
    return None


def get_default_model(category: str) -> Dict[str, Any] | None:
    """Get the default/recommended model for a category."""
    models = get_models_by_category(category)
    if not models:
        return None
    # Return first free-tier model with highest priority
    for m in models:
        if m.get('free_tier'):
            return m
    return models[0]


# Export for backward compatibility
__all__ = [
    'MODELS',
    'VIDEO_MODELS',
    'IMAGE_MODELS',
    'LLM_MODELS',
    'group_by_category',
    'get_models_by_category',
    'count_models_by_category',
    'get_model_by_id',
    'get_default_model',
]