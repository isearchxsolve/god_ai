"""Startup configuration validation contracts."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

from config import Settings  # noqa: E402


def _settings(**overrides):
    values = {
        "SANDBOX_BASE_DIR": "/tmp/ases-sandboxes",
        "ENVIRONMENT": "test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("ENVIRONMENT", "internet", "ENVIRONMENT"),
        ("SANDBOX_MAX_AGE_MINUTES", 0, "MAX_AGE"),
        ("SANDBOX_COMMAND_TIMEOUT_SECONDS", 0, "TIMEOUT"),
        ("SANDBOX_MAX_OUTPUT_BYTES", 100, "OUTPUT"),
        ("SANDBOX_BASE_DIR", "relative/path", "absolute"),
    ],
)
def test_startup_validation_rejects_unsafe_settings(field, value, error):
    with pytest.raises(RuntimeError, match=error):
        _settings(**{field: value}).validate_startup()


@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "DATABASE_URL", "REDIS_URL"])
def test_production_requires_runtime_dependencies(missing):
    values = {
        "ENVIRONMENT": "production",
        "OPENAI_API_KEY": "key",
        "DATABASE_URL": "postgresql://example/ases",
        "REDIS_URL": "redis://example/0",
    }
    values[missing] = None
    with pytest.raises(RuntimeError, match=missing):
        _settings(**values).validate_startup()


def test_valid_production_configuration_passes():
    _settings(
        ENVIRONMENT="production",
        OPENAI_API_KEY="key",
        DATABASE_URL="postgresql://example/ases",
        REDIS_URL="redis://example/0",
    ).validate_startup()
