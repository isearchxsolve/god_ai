import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Film Kit Studio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # OpenRouter (free-tier LLM/image/video — NVIDIA NIM is a TOTAL NO-GO)
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Groq (free-tier LLM)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_BASE_URL: str = "https://api.groq.com/openai/v1"

    # Cerebras (free-tier LLM, ultra-fast inference)
    CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
    CEREBRAS_API_BASE_URL: str = "https://api.cerebras.ai/v1"

    # Cohere (free-tier LLM + embeddings)
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_API_BASE_URL: str = "https://api.cohere.ai/v1"

    # Cloudflare Workers AI (free-tier LLM/image/embeddings)
    CLOUDFLARE_API_KEY: str = os.getenv("CLOUDFLARE_API_KEY", "")
    CLOUDFLARE_ACCOUNT_ID: str = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    # Google Gemini (free-tier multimodal chat/image/video/audio)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    # Pollinations (free keyless text-to-image fallback)
    POLLINATIONS_API_BASE_URL: str = "https://image.pollinations.ai"

    # Provider priority (lower = higher priority). Only providers with keys
    # configured are actually registered at runtime. Pollinations is keyless and always available.
    PROVIDER_PRIORITY: list[str] = ["gemini", "groq", "openrouter", "cerebras", "cohere", "cloudflare", "pollinations"]

    # Default models per capability (free-tier friendly).
    DEFAULT_CHAT_MODEL: str = "gemini-2.5-flash"
    DEFAULT_IMAGE_MODEL: str = "pollinations/flux"
    DEFAULT_VIDEO_MODEL: str = "gemini-2.5-veo"
    DEFAULT_EMBEDDING_MODEL: str = "cohere/embed-english-v3.0"

    # Model-to-provider mapping (model id prefix -> provider name).
    MODEL_PROVIDER_MAP: dict[str, str] = {
        "llama": "groq",
        "mixtral": "groq",
        "gemma": "groq",
        "openai": "openrouter",
        "anthropic": "openrouter",
        "mistral": "openrouter",
        "command": "cohere",
        "embed-": "cohere",
        "@cf/": "cloudflare",
    }

    # Database (optional - for future use)
    DATABASE_URL: Optional[str] = None
    
    # Redis (optional - for caching/queue)
    REDIS_URL: Optional[str] = None
    
    # Storage (optional - for video storage)
    STORAGE_TYPE: str = "local"  # local, s3, gcs
    STORAGE_PATH: str = "./storage"
    
    # Celery (optional - for background tasks)
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
# We'll read the existing file and update it. Let's first read it.