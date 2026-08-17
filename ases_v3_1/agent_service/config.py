"""
ASES - Configuration
"""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API
    APP_NAME: str = "ASES Agent Service"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None

    # GitHub
    GITHUB_TOKEN: Optional[str] = None

    # Vercel
    VERCEL_TOKEN: Optional[str] = None

    # Sandbox
    SANDBOX_BASE_DIR: str = "/tmp/ases-sandboxes"
    SANDBOX_MAX_AGE_MINUTES: int = 10

    # Database (for production)
    DATABASE_URL: Optional[str] = None
    REDIS_URL: Optional[str] = None

    SANDBOX_COMMAND_TIMEOUT_SECONDS: int = 120
    SANDBOX_MAX_OUTPUT_BYTES: int = 12000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_startup(self) -> None:
        """Reject invalid operational settings before serving traffic."""
        errors = []
        if self.ENVIRONMENT not in {"development", "test", "staging", "production"}:
            errors.append("ENVIRONMENT must be development, test, staging, or production")
        if self.SANDBOX_MAX_AGE_MINUTES < 1:
            errors.append("SANDBOX_MAX_AGE_MINUTES must be at least 1")
        if not 1 <= self.SANDBOX_COMMAND_TIMEOUT_SECONDS <= 300:
            errors.append("SANDBOX_COMMAND_TIMEOUT_SECONDS must be between 1 and 300")
        if not 1024 <= self.SANDBOX_MAX_OUTPUT_BYTES <= 1_000_000:
            errors.append("SANDBOX_MAX_OUTPUT_BYTES must be between 1024 and 1000000")
        if not (Path(self.SANDBOX_BASE_DIR).is_absolute() or self.SANDBOX_BASE_DIR.startswith("/")):
            errors.append("SANDBOX_BASE_DIR must be an absolute path")
        if self.ENVIRONMENT == "production":
            for name in ("OPENAI_API_KEY", "DATABASE_URL", "REDIS_URL"):
                if not getattr(self, name):
                    errors.append(f"{name} is required when ENVIRONMENT=production")
        if errors:
            raise RuntimeError("Invalid ASES configuration: " + "; ".join(errors))

settings = Settings()
