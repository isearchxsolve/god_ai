"""Provider service — wires configured free-tier providers into the registry.

This replaces the old `nim_client` singleton. It reads API keys from
`app.core.config.settings`, constructs adapters lazily, and registers them
with the `ProviderRegistry` in priority order. NVIDIA NIM is a TOTAL NO-GO
(AC-10) and is never registered.
"""
from __future__ import annotations

from typing import Optional

from app.core.config import settings
from providers import ProviderRegistry, get_registry, reset_registry


async def _make_gemini():
    from providers.gemini import GeminiAdapter
    return GeminiAdapter(
        api_key=settings.GEMINI_API_KEY,
        base_url=settings.GEMINI_API_BASE_URL,
    )


async def _make_pollinations():
    from providers.pollinations import PollinationsAdapter
    return PollinationsAdapter(
        base_url=settings.POLLINATIONS_API_BASE_URL,
    )


async def _make_openrouter():
    from openrouter_adapter import OpenRouterAdapter
    return OpenRouterAdapter(
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_API_BASE_URL,
    )


async def _make_groq():
    from groq_adapter import GroqAdapter
    return GroqAdapter(
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_API_BASE_URL,
    )


async def _make_cerebras():
    from providers.cerebras import CerebrasAdapter
    return CerebrasAdapter(
        api_key=settings.CEREBRAS_API_KEY,
        base_url=settings.CEREBRAS_API_BASE_URL,
    )


async def _make_cohere():
    from providers.cohere import CohereAdapter
    return CohereAdapter(
        api_key=settings.COHERE_API_KEY,
        base_url=settings.COHERE_API_BASE_URL,
    )


async def _make_cloudflare():
    from providers.cloudflare import CloudflareAdapter
    return CloudflareAdapter(
        api_key=settings.CLOUDFLARE_API_KEY,
        account_id=settings.CLOUDFLARE_ACCOUNT_ID,
        base_url=settings.CLOUDFLARE_API_BASE_URL,
    )


_FACTORIES = {
    "gemini": (_make_gemini, ("chat", "image", "video", "audio")),
    "pollinations": (_make_pollinations, ("image",)),
    "openrouter": (_make_openrouter, ("chat", "image", "video", "embedding")),
    "groq": (_make_groq, ("chat", "embedding")),
    "cerebras": (_make_cerebras, ("chat",)),  # AC-11: embedding raises NotImplementedError
    "cohere": (_make_cohere, ("chat", "embedding")),
    "cloudflare": (_make_cloudflare, ("chat", "image", "embedding")),
}


def _has_key(name: str) -> bool:
    if name == "pollinations":
        return True  # Pollinations is keyless
    keys = {
        "gemini": settings.GEMINI_API_KEY,
        "openrouter": settings.OPENROUTER_API_KEY,
        "groq": settings.GROQ_API_KEY,
        "cerebras": settings.CEREBRAS_API_KEY,
        "cohere": settings.COHERE_API_KEY,
        "cloudflare": settings.CLOUDFLARE_API_KEY,
    }
    return bool(keys.get(name))


async def init_registry() -> ProviderRegistry:
    """Build and populate the provider registry from configuration.

    Only providers whose API key is configured (or keyless like Pollinations)
    are registered. Providers are ordered by `settings.PROVIDER_PRIORITY`.
    NVIDIA NIM is never registered.
    """
    registry = get_registry()
    for idx, name in enumerate(settings.PROVIDER_PRIORITY):
        if name not in _FACTORIES or not _has_key(name):
            continue
        factory, caps = _FACTORIES[name]
        registry.register_factory(name, factory, priority=idx, capabilities=caps)
    return registry


async def get_provider_registry() -> ProviderRegistry:
    return await init_registry()


async def shutdown_registry() -> None:
    reset_registry()
