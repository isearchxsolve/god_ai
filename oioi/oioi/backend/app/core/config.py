import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "OiiOii Studio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
    ]

    # --- Auth (JWT) ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", "oioi-dev-secret-change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    # When True, requests without a token are auto-provisioned a demo user.
    # Set False in production to enforce strict auth.
    AUTO_PROVISION_DEMO: bool = os.getenv("AUTO_PROVISION_DEMO", "true").lower() == "true"

    # --- Persistence (SQLite via aiosqlite) ---
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "")  # filled in __init__ if empty
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "")    # filled in __init__ if empty

    # --- OpenRouter (free-tier LLM/image/video) ---
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    OPENROUTER_API_BASE_URL: str = "https://openrouter.ai/api/v1"

    # --- Groq (free-tier LLM) ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_BASE_URL: str = "https://api.groq.com/openai/v1"

    # --- Cerebras (free-tier LLM) ---
    CEREBRAS_API_KEY: str = os.getenv("CEREBRAS_API_KEY", "")
    CEREBRAS_API_BASE_URL: str = "https://api.cerebras.ai/v1"

    # --- Cohere (free-tier LLM + embeddings) ---
    COHERE_API_KEY: str = os.getenv("COHERE_API_KEY", "")
    COHERE_API_BASE_URL: str = "https://api.cohere.ai/v1"

    # --- Cloudflare Workers AI ---
    CLOUDFLARE_API_KEY: str = os.getenv("CLOUDFLARE_API_KEY", "")
    CLOUDFLARE_ACCOUNT_ID: str = os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
    CLOUDFLARE_API_BASE_URL: str = "https://api.cloudflare.com/client/v4/accounts"

    # --- Google Gemini (free-tier multimodal) ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    # --- Pollinations (free keyless text-to-image) ---
    POLLINATIONS_API_BASE_URL: str = "https://image.pollinations.ai"

    # Provider priority (lower index = higher priority). Only providers with
    # configured keys are registered at runtime. Pollinations is keyless.
    PROVIDER_PRIORITY: list[str] = [
        "openrouter", "groq", "gemini", "cerebras", "cohere", "cloudflare", "pollinations",
    ]

    # Default models per capability (free-tier friendly, verified live).
    DEFAULT_CHAT_MODEL: str = os.getenv("DEFAULT_CHAT_MODEL", "google/gemma-4-26b-a4b-it:free")
    DEFAULT_IMAGE_MODEL: str = "flux"
    DEFAULT_VIDEO_MODEL: str = "kenburns-frames"
    DEFAULT_EMBEDDING_MODEL: str = "cohere/embed-english-v3.0"

    # Pipeline behaviour
    SHOTS_PER_SCENE: int = int(os.getenv("SHOTS_PER_SCENE", "2"))
    MAX_CONCURRENT_IMAGES: int = int(os.getenv("MAX_CONCURRENT_IMAGES", "3"))
    IMAGE_TIMEOUT_SECONDS: int = int(os.getenv("IMAGE_TIMEOUT_SECONDS", "60"))
    FRAME_FPS: int = int(os.getenv("FRAME_FPS", "12"))
    CLIP_SECONDS: int = int(os.getenv("CLIP_SECONDS", "5"))

    class Config:
        env_file = ".env"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Resolve default paths relative to the backend directory.
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not self.DATABASE_PATH:
            self.DATABASE_PATH = os.getenv("DATABASE_PATH", os.path.join(backend_dir, "oioi.db"))
        if not self.STORAGE_PATH:
            self.STORAGE_PATH = os.getenv("STORAGE_PATH", os.path.join(backend_dir, "storage"))


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
