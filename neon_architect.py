#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  NEON ARCHITECT v4.0  —  Monolithic Coding Agent for NVIDIA NIM (GLM-5.2)  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Backend:   NVIDIA NIM  →  GLM-5.2  (primary) | Nemotron / Llama (fallback)  ║
║  Design:    Cyberpunk TUI · Zero Bottlenecks · Self-Healing Streams          ║
║  Features:  Auto-Nudge · XML Interceptor · Smart Compaction · Token Bucket  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python neon_architect.py                    # interactive mode
    python neon_architect.py --project ./myapp  # set project dir
    python neon_architect.py --model glm-5.2    # pick model

Commands (inside agent):
    /exit          quit
    /clear         wipe conversation history
    /compact       force context compaction
    /files         show project file tree
    /cost          show token usage stats
    /model <name>  switch model
    /todo          show task tracker
    <Enter>        continue / proceed with last task
"""

from __future__ import annotations

import argparse
import difflib
import fnmatch
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
import concurrent.futures
import queue
from collections import deque
import random
import atexit

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

try:
    import openai
    OPENAI_ERRORS = (
        openai.APITimeoutError,
        openai.APIConnectionError,
        openai.InternalServerError,
        openai.RateLimitError,
        openai.APIStatusError,
    )
except ImportError:
    OPENAI_ERRORS = (Exception,)
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

# ── OpenAI client ─────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    OpenAI = None  # type: ignore

# ── Rich TUI ──────────────────────────────────────────────────────────────────
try:
    from rich.console import Console, Group, RenderableType
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.rule import Rule
    from rich.syntax import Syntax
    from rich.markdown import Markdown
    from rich.tree import Tree
    from rich.align import Align
    from rich.padding import Padding
    from rich.theme import Theme
    from rich.box import ROUNDED, MINIMAL, SIMPLE_HEAD, DOUBLE_EDGE, HEAVY_EDGE
    from rich.live import Live
    from rich.progress import (
        Progress, SpinnerColumn, TextColumn,
        BarColumn, TimeElapsedColumn
    )
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    Console = None  # type: ignore

# ── Windows console fix & legacy detection ──────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

LEGACY_WIN_CONSOLE = (
    sys.platform == "win32"
    and not os.environ.get("WT_SESSION")           # Not Windows Terminal
    and not os.environ.get("ANSICON")              # Not ANSICON
    and os.environ.get("ConEmuANSI") != "ON"         # Not ConEmu
    and not os.environ.get("TERM_PROGRAM")           # Not VS Code / Hyper / etc.
)
if LEGACY_WIN_CONSOLE:
    # Force plain ASCII on legacy cmd.exe to prevent □□□ garbage
    os.environ["PYTHONIOENCODING"] = "utf-8"

# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: CONSTANTS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "NEON ARCHITECT"
APP_VERSION = "4.2.13"
APP_TAGLINE = "GLM-5.2 · NVIDIA NIM · Zero Bottlenecks · Self-Healing"

CONFIG_DIR = Path.home() / ".neon_architect"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"
HISTORY_FILE = CONFIG_DIR / "history.jsonl"
STATE_VERSION = 2  # bump when session schema changes


def _project_id(project_dir: Path) -> str:
    """Stable short id for a project directory."""
    import hashlib
    key = str(project_dir.resolve()).encode("utf-8", errors="replace")
    return hashlib.sha256(key).hexdigest()[:16]


def _project_session_path(project_dir: Path) -> Path:
    """Stable per-project session file (survives relaunch)."""
    return SESSIONS_DIR / f"project_{_project_id(project_dir)}.json"


def _project_key_path(project_dir: Path) -> Path:
    """Per-project API key file — avoids throttling one global NVIDIA account."""
    return SESSIONS_DIR / f"project_{_project_id(project_dir)}.key.json"


def load_project_api_key(project_dir: Path) -> str:
    data = _safe_json_load(_project_key_path(project_dir))
    if data and isinstance(data.get("api_key"), str):
        return data["api_key"].strip()
    return ""


def save_project_api_key(project_dir: Path, api_key: str) -> Path:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = _project_key_path(project_dir)
    cleaned = api_key.strip().strip('"').strip("'").replace("\n", "").replace("\r", "")
    payload = {
        "project": str(Path(project_dir).resolve()),
        "api_key": cleaned,
        "updated": datetime.now().isoformat(),
    }
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)
    return path


def _safe_json_load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return None

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# ── Model Registry ────────────────────────────────────────────────────────────
MODELS: Dict[str, Dict[str, Any]] = {
    "glm-5.2": {
        "id": "z-ai/glm-5.2",
        "name": "GLM-5.2",
        "provider": "NVIDIA NIM",
        "rpm": 40,
        "max_tokens": 8192,
        "ctx_window": 131072,
        # thinking ON — max server-side reasoning (effort=high)
        "thinking": True,
        "extra_body": None,
    },
    "glm-5.2-fp8": {
        "id": "z-ai/glm-5.2-fp8",
        "name": "GLM-5.2-FP8",
        "provider": "NVIDIA NIM",
        "rpm": 40,
        "max_tokens": 8192,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": None,
    },
    "nemotron-ultra": {
        "id": "nvidia/nemotron-3-ultra-550b-a55b",
        "name": "Nemotron 3 Ultra",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": None,
    },
    "nemotron-4-340b": {
        "id": "nvidia/nemotron-4-340b",
        "name": "Nemotron 4 340B",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": None,
    },
    "llama-3.1-405b": {
        "id": "nvidia/llama-3.1-405b-instruct",
        "name": "Llama 3.1 405B",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": None,
    },
    "nemotron-3-super-120b-a12b": {
        "id": "nvidia/nemotron-3-super-120b-a12b",
        "name": "Nemotron 3 Super 120B",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": None,
    },
}

# Hardened defaults for thinking_effort=high on NVIDIA NIM.
# Root cause of stalls/hiccups: first_token_timeout too low (25s) while GLM
# buffers 30–90s of reasoning with zero SSE bytes — looked like a dead backend
# and forced false provider rotations.
DEFAULT_CONFIG = {
    "version": APP_VERSION,
    "api_key": "",
    "default_model": "glm-5.2",
    "default_persona": "engineer",
    "base_url": NIM_BASE_URL,
    "project_dir": str(Path.cwd()),
    "temperature": 0.2,
    "max_rounds": 500,
    "compact_threshold": 0.3,
    "auto_nudge": True,
    "max_nudges": 3,
    # --- Stream / HTTP sized for high-thinking quiet windows ---
    "stream_timeout": 420.0,           # full-stream wall-clock (think + codegen)
    "request_timeout": 420.0,
    "rpm_safety": 0.80,                # fewer 429 hiccups
    "show_thinking": True,
    "theme": "neon",
    "retry_max": 8,
    "retry_base_delay": 2.5,           # calmer backoff
    "enable_openrouter": True,
    "stream_content_timeout": 150.0,   # idle AFTER first token
    "first_token_timeout": 90.0,       # MUST exceed server think buffer (25s = false stalls)
    "http_read_timeout": 180.0,        # socket quiet between chunks
    "http_connect_timeout": 15.0,      # NIM LB can be slow to accept
    "max_retries_per_provider": 3,     # rotate after real failures; don't thrash
    "thinking_effort": "high",
    "inter_turn_delay": 0.35,          # light pacing vs rate spikes
    "max_autopilot_rounds": 500,
    "max_phase_rounds": 4,
    "startup_compact_tokens": 60000,
    "autopilot_thinking": True,

}
# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1b: PERSONAS & SDLC DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

PERSONAS: Dict[str, Dict[str, Any]] = {
    "adaptive": {
        "name": "Adaptive",
        "description": "Automatically switches based on task keywords",
        "prompt": "You are an adaptive agent. Analyze the user request and adopt the most appropriate professional role to solve the task efficiently.",
        "auto_switch": True,
    },
    "architect": {
        "name": "Architect",
        "description": "System design, APIs, data models, structure",
        "prompt": "You are a senior software architect. Focus on system design, APIs, data models, and overall structure. Think about scalability, maintainability, and clean separation of concerns. Create diagrams and interfaces before implementation.",
        "auto_switch": False,
    },
    "designer": {
        "name": "Designer",
        "description": "UI/UX, components, styling, accessibility",
        "prompt": "You are a UI/UX designer and frontend engineer. Focus on user experience, component design, styling, accessibility, and responsive layouts. Think about color theory, typography, and interaction patterns.",
        "auto_switch": False,
    },
    "engineer": {
        "name": "Engineer",
        "description": "Implementation, algorithms, business logic",
        "prompt": "You are a senior software engineer. Focus on clean implementation, algorithms, business logic, and code quality. Write well-documented, tested code. Follow SOLID principles and best practices.",
        "auto_switch": False,
    },
    "tester": {
        "name": "Tester",
        "description": "TDD, test writing, validation, coverage",
        "prompt": "You are a QA engineer and test specialist. Focus on test-driven development, writing comprehensive tests, edge case coverage, and validation. Ensure all code paths are tested. Use mocking and fixtures appropriately.",
        "auto_switch": False,
    },
    "debugger": {
        "name": "Debugger",
        "description": "Bug diagnosis, root cause analysis, fixes",
        "prompt": "You are a debugging specialist. Focus on systematic bug diagnosis, root cause analysis, and precise fixes. Use logging, breakpoints, and tracing. Think about race conditions, memory leaks, and edge cases.",
        "auto_switch": False,
    },
    "reviewer": {
        "name": "Reviewer",
        "description": "Code quality, security, performance audit",
        "prompt": "You are a code reviewer and security auditor. Focus on code quality, security vulnerabilities, performance bottlenecks, and best practices. Check for OWASP issues, SQL injection, XSS, and inefficient algorithms.",
        "auto_switch": False,
    },
    "devops": {
        "name": "DevOps",
        "description": "Deployment, CI/CD, infrastructure, Docker",
        "prompt": "You are a DevOps engineer. Focus on deployment pipelines, CI/CD, Docker, Kubernetes, infrastructure as code, monitoring, and logging. Ensure systems are observable, scalable, and resilient.",
        "auto_switch": False,
    },
}

PERSONA_TRIGGERS: Dict[str, List[str]] = {
    "architect": ["design", "architecture", "system", "api", "structure", "model", "schema", "interface"],
    "designer": ["ui", "ux", "frontend", "css", "html", "component", "layout", "style", "responsive", "theme"],
    "engineer": ["implement", "code", "function", "algorithm", "logic", "backend", "feature", "build"],
    "tester": ["test", "testing", "tdd", "coverage", "pytest", "unit test", "integration test", "validation"],
    "debugger": ["bug", "fix", "debug", "error", "crash", "issue", "broken", "fail", "traceback"],
    "reviewer": ["review", "audit", "security", "quality", "refactor", "clean up", "optimize", "performance"],
    "devops": ["deploy", "docker", "ci/cd", "pipeline", "kubernetes", "k8s", "infrastructure", "server"],
}

SDLC_PHASES: List[str] = [
    "planning",
    "architecture",
    "design",
    "implementation",
    "testing",
    "review",
    "deployment",
    "verification",
]

SDLC_PHASE_PROMPTS: Dict[str, str] = {
    "planning": "Create a detailed task breakdown and plan. Identify requirements, risks, and dependencies.",
    "architecture": "Design the system architecture. Define components, interfaces, data flow, and tech stack.",
    "design": "Design the UI/UX and component structure. Create layouts, styles, and interaction patterns.",
    "implementation": "Implement the features using TDD. Write clean, documented code with proper error handling.",
    "testing": "Write and run comprehensive tests. Ensure coverage for edge cases and error paths.",
    "review": "Review the codebase for quality, security, and consistency. Refactor as needed.",
    "deployment": "Create deployment artifacts: Dockerfile, docker-compose, CI/CD config, documentation.",
    "verification": "Run final integration tests. Verify all acceptance criteria are met.",
}

SDLC_PERSONA_MAP: Dict[str, str] = {
    "planning": "architect",
    "architecture": "architect",
    "design": "designer",
    "implementation": "engineer",
    "testing": "tester",
    "review": "reviewer",
    "deployment": "devops",
    "verification": "tester",
}

# ── DETERMINISTIC PHASE-COMPLETION GATES ──────────────────────────────────────
# ROOT CAUSE FIX (architectural): The orchestrator was previously asking the
# model to self-certify phase completion via prose ("plan complete", "ready to
# implement"). A thinking model like GLM-5.2 is probabilistic and does not
# reliably emit those exact linguistic markers, so the orchestrator would sit
# waiting for a signal that never comes — the model thinks it's working, the
# orchestrator thinks nothing has happened, and neither side advances.
#
# The fix: the orchestrator now checks OBSERVABLE FACTS from actual tool
# execution (todos created, files written, tests run with a real exit code)
# rather than the model's claims about its own progress. The model becomes a
# worker that produces artifacts; the orchestrator is the project manager that
# verifies artifacts exist and advances the state machine deterministically.
# Textual signal detection and the stuck-round timer remain as fallbacks, but
# are no longer the primary or only path to advancing a phase.
SDLC_PHASE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    # Strict gates so IMPLEMENTATION is real coding, not 2 stubs + phase skip.
    "planning": {
        "kind": "todo_count",
        "min_todos": 5,
    },
    "architecture": {
        "kind": "tool_calls",
        "any_tool": ["write", "edit"],
        "min_calls": 2,
    },
    "design": {
        "kind": "tool_calls",
        "any_tool": ["write", "edit"],
        "min_calls": 2,
    },
    "implementation": {
        "kind": "tool_calls",
        "any_tool": ["write", "edit"],
        "min_calls": 8,  # substantial application code
    },
    "testing": {
        "kind": "bash_success",  # only pytest/unittest-style cmds set _phase_bash_ok
        "require_test_cmd": True,
    },
    "review": {
        "kind": "tool_calls",
        "any_tool": ["read", "edit", "search"],
        "min_calls": 3,
    },
    "deployment": {
        "kind": "tool_calls",
        "any_tool": ["write", "edit"],
        "min_calls": 1,
    },
    "verification": {
        "kind": "bash_success",
        "require_test_cmd": True,
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: CYBERPUNK THEME & UI SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_RICH:
    # Claude Code design system — warm terracotta, high-contrast, large readable type
    THEME = Theme({
        "cc_primary": "#d77757",          # terracotta brand accent
        "cc_primary_bold": "bold #d77757",
        "cc_shimmer": "#eb9f7f",
        "cc_tool": "bold #fd5db1",        # hot pink tool borders
        "cc_tool_dim": "#fd5db1",
        "cc_permission": "#b1b9f9",       # lavender
        "cc_success": "bold #4eba65",
        "cc_warn": "bold #ffc107",
        "cc_error": "bold #ff6b80",
        "cc_muted": "#a0a0a0",           # brighter than #888 for visibility
        "cc_subtle": "#6a6a6a",
        "cc_fg": "bold #ffffff",         # large-readable body
        "cc_body": "#f0f0f0",
        "cc_user": "bold #ffffff",
        "cc_surface": "#373737",
        "cc_thinking": "bold #d77757",
        "cc_prompt": "bold #d77757",
        "cc_status": "#b0b0b0",
        # keep legacy aliases so old markup doesn't crash
        "neon_cyan": "bold #d77757",
        "neon_magenta": "bold #fd5db1",
        "neon_green": "bold #4eba65",
        "neon_yellow": "bold #ffc107",
        "neon_red": "bold #ff6b80",
        "neon_blue": "bold #b1b9f9",
        "neon_white": "bold #ffffff",
        "neon_dim": "#a0a0a0",
        "neon_prompt": "bold #d77757",
        "neon_accent": "bold #fd5db1",
        "neon_success": "bold #4eba65",
        "neon_warning": "bold #ffc107",
        "neon_error": "bold #ff6b80",
        "neon_info": "bold #b1b9f9",
        "user": "bold #ffffff",
        "assistant": "#f0f0f0",
        "thinking": "bold #d77757",
        "tool_name": "bold #fd5db1",
        "tool_args": "#fd5db1",
        "tool_result": "#a0a0a0",
        "dim_cyan": "#d77757",
        "dim_white": "#a0a0a0",
        "status_ok": "bold #4eba65",
        "status_warn": "bold #ffc107",
        "status_err": "bold #ff6b80",
    })
    # force_terminal + soft_wrap help readability on Windows Terminal / cmd
    console = Console(
        theme=THEME,
        highlight=False,
        soft_wrap=True,
        color_system="truecolor",
        force_terminal=True,
    )
else:
    console = None


# Whimsical Claude Code thinking verbs (subset)
_CC_VERBS = [
    "Thinking", "Cooking", "Percolating", "Ruminating", "Cogitating",
    "Ideating", "Kneading", "Sautéing", "Pondering", "Brewing",
    "Noodling", "Whirring", "Mulling", "Spinning", "Crunching",
]
_CC_SPINNER = ["·", "✢", "✳", "✶", "✻", "✽", "✻", "✶", "✳", "✢"]


class UI:
    """Claude Code–style terminal UI: terracotta accent, hot-pink tools, large readable type."""

    @staticmethod
    def esc(text: str) -> str:
        return text.replace("[", "\\[").replace("]", "\\]") if HAS_RICH else text

    @staticmethod
    def header(model_name: str, project: str) -> "RenderableType":
        """Minimal session header — Claude Code has almost no chrome."""
        if not HAS_RICH:
            return f"{APP_NAME} v{APP_VERSION}  ·  {model_name}  ·  {project}"
        line = Text()
        line.append(f"{APP_NAME}", style="cc_primary_bold")
        line.append(f"  v{APP_VERSION}", style="cc_muted")
        line.append("  ·  ", style="cc_subtle")
        line.append(str(model_name), style="cc_fg")
        line.append("  ·  ", style="cc_subtle")
        line.append(UI.esc(str(project)), style="cc_muted")
        return line

    @staticmethod
    def turn_indicator(round_num: int, tokens: int, status: str = "") -> "RenderableType":
        """Large, clear turn marker — high contrast, easy to spot while scrolling."""
        if not HAS_RICH:
            return f"── TURN {round_num:03d}  ·  {tokens:,} tok  {status} ──"
        t = Text()
        t.append("● ", style="cc_primary_bold")
        t.append(f"TURN {round_num:03d}", style="cc_primary_bold")
        t.append("  ·  ", style="cc_subtle")
        t.append(f"{tokens:,} tokens", style="cc_status")
        if status:
            t.append("  ·  ", style="cc_subtle")
            t.append(str(status).upper(), style="cc_tool")
        return t

    @staticmethod
    def user_message(text: str) -> "RenderableType":
        """User prompt — Claude Code dashed ASCII frame, large > prefix."""
        if not HAS_RICH:
            return f"\n> {text}\n"
        # Wide dashed border for visibility
        width = min(max(len(text) + 6, 40), 72)
        dash = "- " * (width // 2)
        dash = dash[:width]
        body = Text()
        body.append(dash + "\n", style="cc_muted")
        body.append("|  ", style="cc_muted")
        body.append("> ", style="cc_prompt")
        body.append(UI.esc(text), style="cc_user")
        body.append("\n", style="cc_user")
        body.append("|  ", style="cc_muted")
        body.append("\n" + dash, style="cc_muted")
        return body

    @staticmethod
    def assistant_stream() -> "Text":
        return Text("", style="cc_body") if HAS_RICH else Text("")  # type: ignore

    @staticmethod
    def thinking_block(text: str) -> "RenderableType":
        """Terracotta thinking line — large glyph + verb."""
        if not HAS_RICH:
            return f"* {text[:240]}"
        verb = random.choice(_CC_VERBS)
        glyph = random.choice(_CC_SPINNER)
        t = Text()
        t.append(f"  {glyph} ", style="cc_thinking")
        t.append(f"{verb}… ", style="cc_thinking")
        if text:
            snippet = text.strip().replace("\n", " ")
            if len(snippet) > 100:
                snippet = snippet[:100] + "…"
            t.append(UI.esc(snippet), style="cc_muted")
        return t

    @staticmethod
    def tool_call(name: str, args_preview: str) -> "RenderableType":
        """Hot-pink tool header — Claude Code signature."""
        if not HAS_RICH:
            return f"  ┌─ {name}  {args_preview}"
        t = Text()
        t.append("  ┌─ ", style="cc_tool")
        t.append(str(name), style="cc_tool")
        if args_preview:
            t.append("  ", style="cc_tool")
            ap = args_preview if len(args_preview) < 80 else args_preview[:77] + "…"
            t.append(UI.esc(ap), style="cc_muted")
        return t

    @staticmethod
    def tool_result(name: str, output: str, is_error: bool = False) -> "RenderableType":
        """Tool result body under hot-pink gutter — larger, clearer."""
        lines = (output or "").splitlines() or [""]
        if len(lines) > 24:
            shown = lines[:24]
            shown.append(f"… [{len(lines) - 24} more lines]")
        else:
            shown = lines
        if not HAS_RICH:
            prefix = "  │ " if not is_error else "  ✗ "
            return "\n".join(prefix + ln for ln in shown) + "\n  └─"
        style = "cc_error" if is_error else "cc_body"
        border = "cc_error" if is_error else "cc_tool_dim"
        parts = []
        for ln in shown:
            row = Text()
            row.append("  │ ", style=border)
            row.append(UI.esc(ln), style=style)
            parts.append(row)
        end = Text("  └─", style=border)
        parts.append(end)
        return Group(*parts) if parts else Text("")

    @staticmethod
    def file_tree(root: Path, cwd: Path) -> "RenderableType":
        if not HAS_RICH:
            lines = []
            for p in sorted(root.rglob("*")):
                if any(part.startswith(".") for part in p.relative_to(root).parts):
                    continue
                depth = len(p.relative_to(root).parts) - 1
                icon = "[dir]" if p.is_dir() else " · "
                lines.append("  " * depth + f"{icon} {p.name}")
            return "\n".join(lines[:60])
        tree = Tree(Text(str(root), style="cc_primary_bold"))
        count = 0
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if count > 60:
                tree.add(Text("…", style="cc_muted"))
                break
            style = "cc_muted" if p.is_dir() else "cc_body"
            tree.add(Text(str(rel), style=style))
            count += 1
        return tree

    @staticmethod
    def file_diff(path: str, old: str, new: str) -> "RenderableType":
        if not HAS_RICH:
            return f"--- {path}\n+++ {path}\n"
        t = Text()
        t.append(f"  ┌─ Edit: {path}\n", style="cc_tool")
        for line in difflib.unified_diff(
            (old or "").splitlines(), (new or "").splitlines(), lineterm=""
        ):
            if line.startswith("+") and not line.startswith("+++"):
                t.append("  │ " + line + "\n", style="cc_success")
            elif line.startswith("-") and not line.startswith("---"):
                t.append("  │ " + line + "\n", style="cc_error")
            else:
                t.append("  │ " + line + "\n", style="cc_muted")
        t.append("  └─", style="cc_tool")
        return t

    @staticmethod
    def ok(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  ✓ ", "cc_success"), (msg, "cc_body")))
        else:
            print(f"  + {msg}")

    @staticmethod
    def warn(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  ⚠ ", "cc_warn"), (msg, "cc_body")))
        else:
            print(f"  ! {msg}")

    @staticmethod
    def err(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  ✗ ", "cc_error"), (msg, "cc_fg")))
        else:
            print(f"  x {msg}")

    @staticmethod
    def info(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  · ", "cc_primary"), (msg, "cc_body")))
        else:
            print(f"  * {msg}")

    @staticmethod
    def separator(title: str = ""):
        if HAS_RICH:
            if title:
                console.print(Text(f"\n  ── {title} ──", style="cc_subtle"))
            else:
                console.print(Text("  " + "─" * 48, style="cc_subtle"))
        else:
            print(f"--- {title} ---" if title else "-" * 40)

    @staticmethod
    def status_bar(model: str, tokens: int, phase: str = "") -> "RenderableType":
        """Bottom-style status — large enough to read at a glance."""
        if not HAS_RICH:
            return f"{model}  ·  {tokens:,} tok  ·  {phase}"
        t = Text()
        t.append("  ", style="cc_status")
        t.append(str(model), style="cc_primary_bold")
        t.append("  ·  ", style="cc_subtle")
        t.append(f"{tokens:,} tokens", style="cc_status")
        if phase:
            t.append("  ·  ", style="cc_subtle")
            t.append(str(phase).upper(), style="cc_tool")
        return t

    @staticmethod
    def neon_banner():
        """Startup banner — Claude Code minimal (no heavy cyberpunk boxes)."""
        if not HAS_RICH:
            print(f"{APP_NAME} v{APP_VERSION}")
            print("Claude Code–style interface  ·  NVIDIA NIM")
            return
        console.print()
        title = Text()
        title.append("  ", style="cc_primary")
        title.append(APP_NAME, style="cc_primary_bold")
        title.append(f"  v{APP_VERSION}", style="cc_muted")
        console.print(title)
        sub = Text()
        sub.append("  ", style="cc_muted")
        sub.append("Warm terracotta UI  ·  ", style="cc_muted")
        sub.append("GLM-5.2", style="cc_fg")
        sub.append("  ·  NVIDIA NIM", style="cc_muted")
        console.print(sub)
        console.print(Text("  " + "─" * 52, style="cc_subtle"))
        console.print()



class TokenBucket:
    """Thread-safe token bucket for RPM enforcement with jitter."""

    def __init__(self, rpm: float, burst: int = 2, min_gap: float = 0.5, safety: float = 0.80):
        self.rpm = max(1.0, rpm) * safety
        self.burst = burst
        self.min_gap = min_gap
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self.last_request = 0.0
        # RLock, not Lock: try_acquire()/acquire() hold this lock and then call
        # wait_time(), which acquires it again. A plain Lock is not reentrant,
        # so that nested acquire deadlocks the calling thread on every single
        # call — this was the actual cause of the TURN 001 freeze (it happens
        # before any request is ever sent, so no HTTP/streaming code runs at all).
        self.lock = threading.RLock()
        self.history: deque[float] = deque()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * (self.rpm / 60.0))
        self.last_update = now

    def _prune(self):
        cutoff = time.monotonic() - 60.0
        while self.history and self.history[0] < cutoff:
            self.history.popleft()

    def wait_time(self) -> float:
        with self.lock:
            self._refill()
            self._prune()
            waits = []
            if self.tokens < 1.0:
                waits.append((1.0 - self.tokens) / (self.rpm / 60.0))
            if self.history and len(self.history) >= int(self.rpm):
                waits.append(60.0 - (time.monotonic() - self.history[0]) + 0.5)
            since_last = time.monotonic() - self.last_request
            if since_last < self.min_gap:
                waits.append(self.min_gap - since_last)
            return max(waits) if waits else 0.0

    def try_acquire(self) -> bool:
        """Non-blocking: take a token if available, else return False immediately."""
        with self.lock:
            self._refill()
            self._prune()
            # Inline wait — do NOT call wait_time() while holding lock (deadlock if Lock;
            # redundant if RLock). Compute directly under the held lock.
            self._refill()
            self._prune()
            waits = []
            if self.tokens < 1.0:
                waits.append((1.0 - self.tokens) / (self.rpm / 60.0))
            if self.history and len(self.history) >= int(self.rpm):
                waits.append(60.0 - (time.monotonic() - self.history[0]) + 0.5)
            since_last = time.monotonic() - self.last_request
            if since_last < self.min_gap:
                waits.append(self.min_gap - since_last)
            wait = max(waits) if waits else 0.0
            if wait <= 0.01:
                self.tokens -= 1.0
                self.last_request = time.monotonic()
                return True
            return False

    def acquire(self, timeout: float = 5.0) -> bool:
        """Blocking acquire with short default timeout."""
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            with self.lock:
                self._refill()
                self._prune()
                waits = []
                if self.tokens < 1.0:
                    waits.append((1.0 - self.tokens) / (self.rpm / 60.0))
                if self.history and len(self.history) >= int(self.rpm):
                    waits.append(60.0 - (time.monotonic() - self.history[0]) + 0.5)
                since_last = time.monotonic() - self.last_request
                if since_last < self.min_gap:
                    waits.append(self.min_gap - since_last)
                wait = max(waits) if waits else 0.0
                if wait <= 0.01:
                    self.tokens -= 1.0
                    self.last_request = time.monotonic()
                    return True
            time.sleep(min(max(wait, 0.05), 0.25))
        return False

    def commit(self):
        with self.lock:
            self.history.append(time.monotonic())


@dataclass
class TokenMeter:
    prompt: int = 0
    completion: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, prompt: int, completion: int):
        with self.lock:
            self.prompt += max(0, prompt)
            self.completion += max(0, completion)

    def report(self) -> str:
        total = self.prompt + self.completion
        return f"{total:,} tok total ({self.prompt:,} prompt + {self.completion:,} completion)"


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: PROVIDER POOL (Self-Healing)
# ═══════════════════════════════════════════════════════════════════════════════

class Provider:
    """A single API endpoint with failure tracking and cooldown.

    NIM BEHAVIOR: GPU backends behind LB may accept TCP then silently drop.
    This is NORMAL for inference-as-a-service. We handle it via:
    1. Short httpx read timeout (20s) to detect silent drops at socket level
    2. max_retries=0 so OpenAI SDK doesn't mask errors with internal retries
    3. Our own retry loop with exponential backoff + provider rotation
    """

    def __init__(self, name: str, base_url: str, api_key: str, model_cfg: Dict[str, Any],
                 connect_timeout: float = 10.0, read_timeout: float = 20.0, bucket: Optional[TokenBucket] = None):
        self.name = name
        self.model_cfg = model_cfg
        self.model_id = model_cfg["id"]
        self.bucket = bucket if bucket is not None else TokenBucket(model_cfg.get("rpm", 20), safety=0.80)

        if HAS_OPENAI and HAS_HTTPX:
            # Aggressive timeouts: detect NIM backend stalls fast, retry to healthy backend
            http_timeout = httpx.Timeout(
                connect=connect_timeout,
                read=read_timeout,      # KEY: kills silent drops within 20s
                write=10.0,
                pool=10.0
            )
            self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=http_timeout, max_retries=0)
        elif HAS_OPENAI:
            self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=read_timeout, max_retries=0)
        else:
            self.client = None
        self.cooldown_until = 0.0
        self.failures = 0
        self.consecutive_failures = 0
        self.permanently_disabled = False

    def available(self) -> bool:
        if getattr(self, "permanently_disabled", False):
            return False
        return time.monotonic() >= self.cooldown_until

    def record_success(self):
        self.bucket.commit()
        self.failures = max(0, self.failures - 1)
        self.consecutive_failures = 0

    def record_failure(self, cooldown: float = 15.0, *, permanent: bool = False):
        self.failures += 1
        self.consecutive_failures += 1
        if permanent:
            self.permanently_disabled = True
            self.cooldown_until = time.monotonic() + 86400.0  # effectively gone
            return
        # Progressive cooldown capped
        self.cooldown_until = time.monotonic() + cooldown * min(self.consecutive_failures, 5)


class ProviderPool:
    """Rotates across providers on failure / rate-limit with telemetry.

    NIM BEHAVIOR: When a backend drops, retry SAME provider first (LB may route
    to different healthy backend). Only rotate after max_retries_per_provider.
    """

    def __init__(self, providers: List[Provider]):
        self.providers = providers
        self.index = 0
        self.attempts_on_current = 0

    def current(self) -> Provider:
        return self.providers[self.index]

    def rotate(self):
        self.index = (self.index + 1) % len(self.providers)
        self.attempts_on_current = 0

    def next_available(self) -> Optional[Provider]:
        """Pick next ready provider without blocking >0s on rate-limit wait."""
        for _ in range(len(self.providers)):
            p = self.current()
            if p.available() and p.bucket.try_acquire():
                return p
            self.rotate()
        return None

    def should_rotate(self, max_per_provider: int = 3) -> bool:
        """Rotate only after N failed attempts on current provider."""
        self.attempts_on_current += 1
        return self.attempts_on_current >= max_per_provider

    def shortest_wait(self) -> float:
        waits = [max(0.0, p.cooldown_until - time.monotonic()) for p in self.providers]
        bucket_waits = [p.bucket.wait_time() for p in self.providers]
        return min(waits + bucket_waits) if (waits or bucket_waits) else 5.0


def build_pool(config: Dict[str, Any]) -> ProviderPool:
    """Build provider pool from config with OpenRouter fallback."""
    providers: List[Provider] = []
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", NIM_BASE_URL)
    model_key = config.get("default_model", "glm-5.2")
    read_timeout = config.get("http_read_timeout", 20.0)
    connect_timeout = config.get("http_connect_timeout", 10.0)
    
    # Shared token buckets per (base_url, api_key) to avoid over-counting RPM
    shared_buckets: Dict[Tuple[str, str], TokenBucket] = {}

    def get_or_create_bucket(model_key: str) -> TokenBucket:
        key = (base_url, api_key)
        if key not in shared_buckets:
            rpm = MODELS.get(model_key, {}).get("rpm", 20)
            shared_buckets[key] = TokenBucket(rpm, safety=0.80)
        return shared_buckets[key]

    if api_key and model_key in MODELS:
        providers.append(Provider("NIM-Primary", base_url, api_key, MODELS[model_key],
                                  connect_timeout, read_timeout, get_or_create_bucket(model_key)))

    # NVIDIA NIM fallbacks (same key, different models)
    fallbacks = ["nemotron-ultra"]  # only verified; 404 models removed
    for fb in fallbacks:
        if fb != model_key and fb in MODELS and api_key:
            providers.append(Provider(f"NIM-{fb}", base_url, api_key, MODELS[fb],
                                      connect_timeout, read_timeout, get_or_create_bucket(fb)))

    # OpenRouter free tier fallback (optional — only if OPENROUTER_API_KEY is set)
    if config.get("enable_openrouter", True):
        or_key = os.environ.get("OPENROUTER_API_KEY")
        if or_key:
            or_base = "https://openrouter.ai/api/v1"
            or_models = [
                ("OR-Nemotron", "nvidia/nemotron-3-ultra-550b-a55b:free"),
                ("OR-Qwen3", "qwen/qwen3-coder:free"),
            ]
            or_bucket = TokenBucket(15, safety=0.80)
            for name, mid in or_models:
                fake_cfg = {
                    "id": mid,
                    "name": name,
                    "rpm": 15,
                    "max_tokens": 8192,
                    "ctx_window": 131072,
                    "thinking": True,
                    "extra_body": None,
                }
                providers.append(Provider(
                    name, or_base, or_key, fake_cfg,
                    connect_timeout, read_timeout, or_bucket,
                ))

    if not providers:
        raise RuntimeError(
            "No providers configured. Set NVIDIA API key in config or OPENROUTER_API_KEY env."
        )

    return ProviderPool(providers)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: TOOL SYSTEM (Complete Arsenal)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ToolResult:
    output: str
    error: str = ""
    is_error: bool = False

    def text(self) -> str:
        if self.is_error:
            return f"[ERROR] {self.error}"
        return self.output


class Tool:
    """Base class for all tools."""
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, cwd: Path):
        self.cwd = cwd.resolve()

    def _safe_path(self, path: str) -> Path:
        target = (self.cwd / path).resolve()
        try:
            target.relative_to(self.cwd)
        except ValueError:
            raise PermissionError(f"Path '{path}' escapes project directory")
        return target

    def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError

    def schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            }
        }


class ReadTool(Tool):
    name = "read"
    description = "Read the contents of a file. Whole file is returned unless it exceeds the limit."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file"},
            "offset": {"type": "integer", "description": "Line number to start from (1-based)", "default": 1},
            # FIX: was 200 — forced 2-4 extra turns of pagination on any file
            # over 200 lines, and those files (render_motion.py etc.) get
            # re-read after every compaction, multiplying wasted turns.
            "limit": {"type": "integer", "description": "Max lines to read", "default": 2000},
        },
        "required": ["path"],
    }

    # Session-level cache: path -> (mtime, size, full_text, lines).
    # Shared across all ReadTool instances/turns in this process so a
    # compaction event doesn't force re-reading an unchanged file from disk
    # — we still re-serve it to the model (it needs the tokens in-context
    # again), but we skip disk I/O and can tell the model explicitly that
    # this is a repeat so it stops treating it as new discovery work.
    _cache: Dict[str, Tuple[float, int, str, List[str]]] = {}
    _cache_lock = threading.Lock()

    def execute(self, path: str, offset: int = 1, limit: int = 2000) -> ToolResult:
        try:
            fp = self._safe_path(path)
            if not fp.exists():
                return ToolResult("", error=f"File not found: {path}", is_error=True)

            key = str(fp)
            stat = fp.stat()
            was_cached = False

            with self._cache_lock:
                cached = self._cache.get(key)
                if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
                    lines = cached[3]
                    was_cached = True
                else:
                    with open(fp, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                    lines = text.splitlines(keepends=True)
                    self._cache[key] = (stat.st_mtime, stat.st_size, text, lines)

            start = max(0, offset - 1)
            end = start + limit
            chunk = "".join(lines[start:end])
            remaining = len(lines) - end

            prefix = ""
            if was_cached and offset == 1:
                prefix = f"[already read this session, unchanged — {len(lines)} lines total]\n"

            if remaining > 0:
                chunk += (
                    f"\n\n... [{remaining} more lines — increase 'limit' or set "
                    f"offset={end + 1} to continue, file has {len(lines)} lines total] ..."
                )
            return ToolResult(prefix + chunk)
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class WriteTool(Tool):
    name = "write"
    description = "Create or overwrite a file with the given content. Creates parent dirs."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def execute(self, path: str, content: str) -> ToolResult:
        try:
            fp = self._safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(f"Written {len(content)} chars to {path}")
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class EditTool(Tool):
    name = "edit"
    description = "Replace old_text with new_text in a file. Use replace_all to replace all occurrences."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
            "replace_all": {"type": "boolean", "default": False},
        },
        "required": ["path", "old_text", "new_text"],
    }

    def execute(self, path: str, old_text: str, new_text: str, replace_all: bool = False) -> ToolResult:
        try:
            fp = self._safe_path(path)
            if not fp.exists():
                return ToolResult("", error=f"File not found: {path}", is_error=True)
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                original = f.read()
            if old_text not in original:
                return ToolResult("", error=f"old_text not found in {path}", is_error=True)
            if replace_all:
                new_content = original.replace(old_text, new_text)
                count = original.count(old_text)
            else:
                new_content = original.replace(old_text, new_text, 1)
                count = 1
            with open(fp, "w", encoding="utf-8") as f:
                f.write(new_content)
            return ToolResult(f"Replaced {count} occurrence(s) in {path}")
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class SearchTool(Tool):
    name = "search"
    description = "Search file contents with a regex pattern."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern"},
            "path": {"type": "string", "default": ".", "description": "Base directory"},
        },
        "required": ["pattern"],
    }

    SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", "dist", "build"}
    SKIP_EXTS = {".pyc", ".exe", ".dll", ".so", ".dylib", ".png", ".jpg", ".jpeg", ".gif", ".zip", ".tar", ".gz", ".mp3", ".mp4", ".woff", ".ttf"}

    def execute(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            base = self._safe_path(path)
            rx = re.compile(pattern, re.IGNORECASE)
            matches: List[str] = []
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
                for fn in files:
                    if any(fn.endswith(ext) for ext in self.SKIP_EXTS):
                        continue
                    fp = Path(root) / fn
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if rx.search(line):
                                    rel = fp.relative_to(self.cwd)
                                    matches.append(f"{rel}:{i}:{line.rstrip()}")
                                    if len(matches) >= 100:
                                        break
                    except Exception:
                        pass
                    if len(matches) >= 100:
                        break
            if not matches:
                return ToolResult(f"No matches for pattern: {pattern}")
            return ToolResult("\n".join(matches))
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class GlobTool(Tool):
    name = "glob"
    description = "Find files matching a glob pattern (e.g., '**/*.py')."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "path": {"type": "string", "default": "."},
        },
        "required": ["pattern"],
    }

    def execute(self, pattern: str, path: str = ".") -> ToolResult:
        try:
            base = self._safe_path(path)
            matches = list(base.rglob(pattern))
            if not matches:
                return ToolResult("No files found")
            rels = sorted(str(m.relative_to(self.cwd)) for m in matches)
            return ToolResult("\n".join(rels))
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class LsTool(Tool):
    name = "ls"
    description = "List files in a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
        },
        "required": [],
    }

    def execute(self, path: str = ".") -> ToolResult:
        try:
            base = self._safe_path(path)
            if not base.exists():
                return ToolResult("", error=f"Directory not found: {path}", is_error=True)
            items = []
            for p in sorted(base.iterdir()):
                icon = "📁" if p.is_dir() else "📄"
                items.append(f"{icon} {p.name}")
            return ToolResult("\n".join(items))
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class BashTool(Tool):
    name = "bash"
    description = "Execute a shell command. Use timeout to limit execution time."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 120},
        },
        "required": ["command"],
    }

    def execute(self, command: str, timeout: int = 120) -> ToolResult:
        try:
            result = subprocess.run(
                command, shell=True, cwd=str(self.cwd),
                capture_output=True, text=True, timeout=timeout,
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            output += f"\n[exit code: {result.returncode}]"
            return ToolResult(output, is_error=result.returncode != 0)
        except subprocess.TimeoutExpired:
            return ToolResult("", error=f"Command timed out after {timeout}s", is_error=True)
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class TaskTool(Tool):
    name = "task"
    description = "Launch a sub-agent to perform an independent multi-step task. Returns a summary."
    parameters = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Short task description"},
            "prompt": {"type": "string", "description": "Detailed instructions for the sub-agent"},
        },
        "required": ["description", "prompt"],
    }

    def execute(self, description: str, prompt: str) -> ToolResult:
        return ToolResult(
            f"[Sub-agent: {description}]\n"
            f"This is a simulated sub-agent task. In swarm mode, this would execute:\n"
            f"{prompt[:300]}..."
        )


class TodoTool(Tool):
    name = "todo"
    description = "Manage a todo list for tracking complex multi-step tasks."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "update", "remove", "list", "clear"]},
            "id": {"type": "string", "description": "Todo ID (for update/remove)"},
            "content": {"type": "string", "description": "Todo content (for add/update)"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "done"], "description": "Status (for update)"},
        },
        "required": ["action"],
    }

    _todos: Dict[str, Dict[str, Any]] = {}
    _counter = 0

    def execute(self, action: str, id: Optional[str] = None, content: Optional[str] = None, status: Optional[str] = None) -> ToolResult:
        try:
            if action == "add":
                if not content:
                    return ToolResult("", error="Content required for add", is_error=True)
                TodoTool._counter += 1
                tid = f"T{TodoTool._counter:03d}"
                TodoTool._todos[tid] = {"content": content, "status": "pending"}
                return ToolResult(f"Added todo {tid}: {content}")
            elif action == "update":
                if id not in TodoTool._todos:
                    return ToolResult("", error=f"Todo {id} not found", is_error=True)
                if content:
                    TodoTool._todos[id]["content"] = content
                if status:
                    TodoTool._todos[id]["status"] = status
                return ToolResult(f"Updated todo {id}")
            elif action == "remove":
                if id not in TodoTool._todos:
                    return ToolResult("", error=f"Todo {id} not found", is_error=True)
                del TodoTool._todos[id]
                return ToolResult(f"Removed todo {id}")
            elif action == "list":
                if not TodoTool._todos:
                    return ToolResult("No todos")
                lines = []
                for tid, todo in TodoTool._todos.items():
                    icon = {"pending": "○", "in_progress": "◐", "done": "*"}[todo["status"]]
                    lines.append(f"{icon} {tid}: {todo['content']} [{todo['status']}]")
                return ToolResult("\n".join(lines))
            elif action == "clear":
                TodoTool._todos.clear()
                return ToolResult("All todos cleared")
            else:
                return ToolResult("", error=f"Unknown action: {action}", is_error=True)
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


def build_tools(cwd: Path) -> Dict[str, Tool]:
    tool_list: List[Tool] = [
        ReadTool(cwd), WriteTool(cwd), EditTool(cwd),
        SearchTool(cwd), GlobTool(cwd), LsTool(cwd),
        BashTool(cwd), TaskTool(cwd), TodoTool(cwd),
    ]
    return {t.name: t for t in tool_list}


def tools_schema(tools: Dict[str, Tool]) -> List[Dict[str, Any]]:
    return [t.schema() for t in tools.values()]


def execute_tool(tools: Dict[str, Tool], name: str, args: Dict[str, Any]) -> ToolResult:
    tool = tools.get(name)
    if not tool:
        return ToolResult("", error=f"Unknown tool: {name}", is_error=True)
    try:
        return tool.execute(**args)
    except TypeError as e:
        return ToolResult("", error=f"Invalid arguments for {name}: {e}", is_error=True)
    except Exception as e:
        return ToolResult("", error=f"{name} failed: {e}", is_error=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: CONTEXT MANAGEMENT (Smart Compaction)
# ═══════════════════════════════════════════════════════════════════════════════

class ContextManager:
    """Handles message history, compaction, and summarization."""

    def __init__(self, compact_threshold: float = 0.75, ctx_window: int = 131072):
        self.messages: List[Dict[str, Any]] = []
        self.compact_threshold = compact_threshold
        self.ctx_window = ctx_window
        self.compaction_summary: Optional[str] = None

    def add_system(self, content: str):
        self.messages = [m for m in self.messages if m.get("role") != "system"]
        self.messages.insert(0, {"role": "system", "content": content})

    def add_user(self, content: str):
        self.messages.append({"role": "user", "content": content})

    def add_assistant(self, content: str = "", tool_calls: Optional[List[Dict]] = None):
        msg: Dict[str, Any] = {"role": "assistant", "content": content or None}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.messages.append(msg)

    def add_tool_result(self, tool_call_id: str, name: str, content: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": name,
            "content": content,
        })

    def estimate_tokens(self) -> int:
        total = 0
        for m in self.messages:
            content = str(m.get("content") or "")
            for tc in m.get("tool_calls", []):
                fn = tc.get("function", {})
                content += str(fn.get("name", "")) + str(fn.get("arguments", ""))
            total += max(1, len(content) // 4)
        return total

    def ratio_used(self) -> float:
        return self.estimate_tokens() / self.ctx_window

    def should_compact(self) -> bool:
        return self.ratio_used() > self.compact_threshold

    def compact(self, keep_recent: int = 8) -> bool:
        """Fold old messages into a summary. Returns True if compaction occurred."""
        sys_msgs = [m for m in self.messages if m.get("role") == "system"]
        rest = [m for m in self.messages if m.get("role") != "system"]
        if len(rest) <= keep_recent + 2:
            return False

        old, recent = rest[:-keep_recent], rest[-keep_recent:]
        summaries = []
        # FIX: track files the agent already read/wrote in the folded window.
        # Previously `read` tool results collapsed to the opaque placeholder
        # "[tool result from read]" with the path thrown away — the model
        # had no way to know it already had a file's contents, so it kept
        # re-reading the same files (in paginated chunks) every time
        # compaction fired. Now we surface an explicit manifest instead.
        files_touched: Dict[str, str] = {}  # path -> "read" | "wrote" | "edited"

        # Look at the preceding assistant tool_calls to recover the path
        # for each tool-result message, since the result itself doesn't
        # carry it.
        pending_call_paths: Dict[str, str] = {}  # tool_call_id -> path
        for m in old:
            role = m.get("role", "")
            if role == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    fn = tc.get("function", {})
                    name = fn.get("name", "?")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = {}
                    path = args.get("path")
                    if path and name in ("read", "write", "edit"):
                        pending_call_paths[tc.get("id", "")] = (name, path)
            elif role == "tool":
                call_id = m.get("tool_call_id", "")
                match = pending_call_paths.get(call_id)
                if match:
                    name, path = match
                    is_error = str(m.get("content", "")).startswith("[ERROR]")
                    if not is_error:
                        verb = {"read": "read", "write": "wrote", "edit": "edited"}[name]
                        # edit/write after a read should show the more recent action
                        files_touched[path] = verb

        for m in old:
            role = m.get("role", "")
            content = str(m.get("content", ""))[:120].replace("\n", " ")
            if role == "tool":
                content = f"[tool result from {m.get('name', '?')}]"
            elif role == "assistant" and m.get("tool_calls"):
                names = [tc.get("function", {}).get("name", "?") for tc in m["tool_calls"]]
                content = f"[called tools: {', '.join(names)}]"
            summaries.append(f"  {role}: {content}")

        manifest = ""
        if files_touched:
            lines = [f"  - {p} ({v})" for p, v in sorted(files_touched.items())]
            manifest = (
                "\n\n[FILES ALREADY SEEN THIS SESSION — do NOT re-read unless you "
                "suspect they changed; use the summary above and proceed]\n"
                + "\n".join(lines)
            )

        self.compaction_summary = (
            f"[FOLDED {len(old)} MESSAGES]\n" + "\n".join(summaries[-30:]) + manifest
        )
        self.messages = sys_msgs + [
            {"role": "user", "content": f"[PRIOR CONTEXT SUMMARY]\n{self.compaction_summary}\n\nYou are mid-task. Continue executing the next required tool immediately. Do not re-read files listed as already seen unless you have a specific reason to believe they changed."},
            {"role": "assistant", "content": "Context acknowledged. Proceeding with next tool execution."},
        ] + recent
        return True

    def clear(self):
        self.messages = [m for m in self.messages if m.get("role") == "system"]
        self.compaction_summary = None

    def export(self) -> List[Dict[str, Any]]:
        return [{k: v for k, v in m.items() if not k.startswith("_")} for m in self.messages]


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 7: AGENT CORE (Zero Bottlenecks)
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_TEMPLATE = """You are Neon Architect, an expert autonomous software engineering team.
Your mission: write, edit, read, search, and execute code using Test-Driven Development (TDD).

CRITICAL RULES:
1. ALWAYS use the native JSON function calling API for tools. Never output raw XML or markdown code blocks for tool calls.
2. If you need to use a tool, CALL IT IMMEDIATELY in the same response. Do NOT announce your intention and stop.
3. Read files before editing them. Search before writing new files to avoid duplication.
4. Write clean, documented code. Follow the project's existing style.
5. After making changes, verify with tests or by reading the modified file.
6. If a task is complex, break it into sub-tasks using the 'task' tool.
7. Use the 'todo' tool to track multi-step tasks.

TDD METHODOLOGY (Default):
- RED: Write a failing test that defines the expected behavior
- GREEN: Write the minimum code to make the test pass
- REFACTOR: Clean up the code while keeping tests green
- ALWAYS run tests after implementation to verify
- If no test framework exists, set one up first

PERSONA SYSTEM:
You adopt different professional roles depending on the task:
- Architect: System design, APIs, data models, structure
- Designer: UI/UX, components, styling, accessibility
- Engineer: Implementation, algorithms, business logic
- Tester: TDD, test writing, validation, coverage
- Debugger: Bug diagnosis, root cause analysis, fixes
- Reviewer: Code quality, security, performance audit
- DevOps: Deployment, CI/CD, infrastructure, Docker
Your current persona is injected below. Stay in character.

WORKING DIRECTORY: {project_dir}
CURRENT MODEL: {model_name}

You have access to these tools:
- read(path, offset, limit) — read file contents
- write(path, content) — create/overwrite a file
- edit(path, old_text, new_text, replace_all) — precise string replacement
- search(pattern, path) — regex search across files
- glob(pattern, path) — find files by glob pattern
- ls(path) — list directory contents
- bash(command, timeout) — run shell commands
- task(description, prompt) — delegate to sub-agent
- todo(action, id, content, status) — manage task tracker

The user may set a goal with /goal and start /autopilot for god mode.
In autopilot mode, you cycle through SDLC phases autonomously: planning → architecture → design → implementation → testing → review → deployment → verification.
You must self-direct: decide when a phase is complete and signal completion so the next phase begins.
"""


class NeonArchitect:
    """The main agent. Cyberpunk interface, zero-bottleneck core."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_dir = Path(config.get("project_dir", ".")).resolve()
        self.model_key = config.get("default_model", "glm-5.2")
        self.model_cfg = MODELS.get(self.model_key, MODELS["glm-5.2"])

        self.pool = build_pool(config)
        self.tools = build_tools(self.project_dir)
        self.ctx = ContextManager(
            compact_threshold=config.get("compact_threshold", 0.75),
            ctx_window=self.model_cfg.get("ctx_window", 131072),
        )
        self.meter = TokenMeter()
        self.round = 0
        self.nudges = 0
        self.running = True

        self.goal = None
        self.persona_key = config.get("default_persona", "adaptive")
        self.persona_history: deque[str] = deque(maxlen=10)
        # Autopilot / SDLC state
        self.autopilot = False
        self.sdlc_phase_idx = 0
        self.sdlc_completed: set[str] = set()
        self.autopilot_rounds = 0
        self.max_autopilot_rounds = int(config.get("max_autopilot_rounds", 500))
        # Phase-stuck detection: force-advance after N rounds with no signal
        self._phase_rounds = 0
        self._max_phase_rounds = int(config.get("max_phase_rounds", 4))
        # Deterministic phase-completion tracking: counts of tool calls made
        # DURING the current phase, and whether a bash call in this phase
        # succeeded (exit code 0). Reset every time the phase advances.
        self._phase_tool_counts: Dict[str, int] = {}
        self._phase_bash_ok = False
        self.current_turn_tool_calls = False
        self._last_persist = 0.0
        self._persist_every = 3  # autosave every N turns

        # Restore previous session ONLY for THIS project path.
        # Never import last_goal / SDLC from global config — that leaked old
        # projects into new folders ("not creating a new session for a new project").
        restored = False
        skip_restore = bool(config.get("_fresh", False))
        try:
            if skip_restore:
                UI.info("Fresh session (--fresh / /new) — not restoring prior state")
                self._rebuild_system()
            else:
                prior = load_session(self.project_dir)
                if prior:
                    apply_session(self, prior)
                    restored = True
                else:
                    # Brand-new project directory: clean slate (model/persona from config only)
                    self._rebuild_system()
        except Exception as e:
            UI.warn(f"Could not restore session: {e}")
            self._rebuild_system()

        if not restored and not skip_restore:
            self._rebuild_system()

        # Hard-pin thinking policy after session/config merge (old sessions had "off")
        self.config["thinking_effort"] = "high"
        self.config["show_thinking"] = True
        self.config["autopilot_thinking"] = True
        self.config["first_token_timeout"] = float(
            self.config.get("first_token_timeout") or DEFAULT_CONFIG["first_token_timeout"]
        )
        if self.config["first_token_timeout"] < 90.0:
            self.config["first_token_timeout"] = 90.0

        UI.separator()
        UI.ok(f"Initialized in {self.project_dir}")
        UI.info(
            f"Thinking: {self.config.get('thinking_effort')} | "
            f"show={self.config.get('show_thinking')} | "
            f"first_token={self.config.get('first_token_timeout')}s"
        )
        UI.info(f"Model: {self.model_cfg['name']} ({self.model_cfg['id']})")
        UI.info(f"Persona: {PERSONAS[self.persona_key]['name']} (auto-switching)" if PERSONAS[self.persona_key]['auto_switch'] else f"Persona: {PERSONAS[self.persona_key]['name']}")
        if restored:
            UI.ok("Session restored from previous launch")
            if self.goal:
                UI.info(f"Goal: {self.goal}")
            if self.sdlc_completed or self.sdlc_phase_idx:
                phase = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else "COMPLETE"
                UI.info(f"SDLC phase: {phase.upper()} | completed: {', '.join(sorted(self.sdlc_completed)) or 'none'}")
            if TodoTool._todos:
                UI.info(f"Todos: {len(TodoTool._todos)} item(s) restored")
            n_msgs = len([m for m in self.ctx.messages if m.get('role') != 'system'])
            if n_msgs:
                UI.info(f"Conversation: {n_msgs} message(s) restored")
            # Aggressive startup compact — multi-million token restores destroy latency
            est = self.ctx.estimate_tokens()
            floor = int(self.config.get("startup_compact_tokens", 40000))
            if est > floor:
                before = est
                # Keep only last few turns; wipe the rest into a short summary
                keep = 4 if est > 200_000 else 6
                if self.ctx.compact(keep_recent=keep):
                    after = self.ctx.estimate_tokens()
                    UI.warn(f"Startup compact: ~{before:,} → ~{after:,} tokens")
                    self._rebuild_system()
                # If still huge, drop history entirely (keep goal/todos/phase)
                est2 = self.ctx.estimate_tokens()
                if est2 > floor * 2:
                    self.ctx.messages = [m for m in self.ctx.messages if m.get("role") == "system"]
                    self.ctx.compaction_summary = (
                        f"[Prior session truncated: was ~{before:,} tokens. Goal and todos kept.]"
                    )
                    self._rebuild_system()
                    UI.warn("Context still large — conversation history cleared (goal/todos kept). Use /reset for full wipe.")
            UI.info(f"Tokens so far: {self.meter.report()}")
        elif self.goal:
            UI.info(f"Goal (from config): {self.goal}")

    def _rebuild_system(self):
        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            project_dir=str(self.project_dir),
            model_name=self.model_cfg["name"],
        )
        # Add active persona directive
        persona = PERSONAS.get(self.persona_key, PERSONAS["adaptive"])
        prompt += f"\n\n[CURRENT PERSONA: {persona['name']}]\n{persona['prompt']}"
        if self.goal:
            prompt += f"\n\n[CURRENT GOAL]\n{self.goal}\nYou must focus all actions toward achieving this goal."
        # Add SDLC phase directive when in autopilot
        if self.autopilot and self.sdlc_phase_idx < len(SDLC_PHASES):
            phase = SDLC_PHASES[self.sdlc_phase_idx]
            phase_prompt = SDLC_PHASE_PROMPTS.get(phase, "")
            completed = ", ".join(self.sdlc_completed) if self.sdlc_completed else "none"
            prompt += f"\n\n[SDLC PHASE: {phase.upper()}]\n{phase_prompt}\n\nCompleted phases: {completed}"
        if self.ctx.compaction_summary:
            prompt += f"\n\n[COMPACTED HISTORY]\n{self.ctx.compaction_summary}"
        self.ctx.add_system(prompt)

    def _advance_sdlc(self) -> bool:
        """Advance to next SDLC phase. Returns True if there are more phases."""
        current = SDLC_PHASES[self.sdlc_phase_idx]
        self.sdlc_completed.add(current)
        self.sdlc_phase_idx += 1
        self._phase_rounds = 0  # reset stuck counter on every advance
        self._phase_tool_counts = {}  # reset deterministic tool-call tracking
        self._phase_bash_ok = False
        if self.sdlc_phase_idx >= len(SDLC_PHASES):
            UI.ok("All SDLC phases complete — goal pipeline finished.")
            if self.autopilot:
                UI.ok("Autopilot stopping: full SDLC cycle done. Review output or /autopilot to continue.")
                self.autopilot = False
            return False
        next_phase = SDLC_PHASES[self.sdlc_phase_idx]
        next_persona = SDLC_PERSONA_MAP.get(next_phase, "adaptive")
        self._switch_persona(next_persona, reason="auto")
        UI.ok(f"SDLC: {current.upper()} complete → {next_phase.upper()}")
        if next_phase == "implementation":
            UI.info(
                "IMPLEMENTATION: write/edit real application code under the project dir "
                "(≥8 write/edit calls required before phase can complete). "
                "No more planning-only exploration."
            )
        elif next_phase == "testing":
            UI.info("TESTING: run pytest/unittest — only real test commands count as success.")
        self._rebuild_system()
        self.persist(force=True)
        return True

    def _start_autopilot(self):
        """Enter god autopilot mode for the current goal."""
        if not self.goal:
            UI.err("No goal set. Use /goal <description> first.")
            return False
        self.autopilot = True
        self.sdlc_phase_idx = 0
        self.sdlc_completed.clear()
        self.autopilot_rounds = 0
        self.round = 0
        self._phase_rounds = 0
        self._phase_tool_counts = {}
        self._phase_bash_ok = False
        # Set initial persona for planning phase
        initial_persona = SDLC_PERSONA_MAP.get("planning", "adaptive")
        self._switch_persona(initial_persona, reason="auto")
        self._rebuild_system()
        UI.separator("GOD AUTOPILOT ENGAGED")
        UI.ok(f"Goal: {self.goal}")
        UI.info(f"Starting SDLC phase: {SDLC_PHASES[0].upper()}")
        UI.info("The agent will now autonomously cycle through planning → architecture → design → implementation → testing → review → deployment → verification")
        UI.info("Type /stop to halt autopilot, /status to check progress")
        return True

    def _stop_autopilot(self):
        """Halt autopilot mode."""
        if not self.autopilot:
            UI.info("Autopilot is not active.")
            return
        self.autopilot = False
        phase = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else "COMPLETE"
        UI.separator("AUTOPILOT HALTED")
        UI.info(f"Stopped at phase: {phase.upper()}")
        UI.info(f"Completed: {', '.join(self.sdlc_completed) if self.sdlc_completed else 'none'}")
        UI.info("Type /autopilot to resume from current phase.")
        self.persist(force=True)

    def _autopilot_status(self):
        """Show autopilot progress."""
        if not self.goal:
            UI.info("No goal set.")
            return
        if not self.autopilot:
            UI.info("Autopilot is OFF. Goal is set but not being actively pursued.")
        current = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else "COMPLETE"
        UI.separator("AUTOPILOT STATUS")
        UI.info(f"Goal: {self.goal}")
        UI.info(f"Active: {'YES' if self.autopilot else 'NO'}")
        UI.info(f"Current phase: {current.upper()}")
        UI.info(f"Rounds: {self.autopilot_rounds}")
        UI.info(f"Completed: {', '.join(self.sdlc_completed) if self.sdlc_completed else 'none'}")
        remaining = [p for p in SDLC_PHASES if p not in self.sdlc_completed]
        UI.info(f"Remaining: {', '.join(remaining)}")

    def _autopilot_prompt(self) -> str:
        """Generate the next autopilot prompt based on current phase."""
        if self.sdlc_phase_idx >= len(SDLC_PHASES):
            return "The SDLC is complete. Verify all acceptance criteria are met and summarize the deliverables."
        phase = SDLC_PHASES[self.sdlc_phase_idx]
        prompts = {
            "planning": "PLANNING ONLY: Call the todo tool at least 5 times (action=add). Do NOT read the whole codebase. Do NOT implement yet. Summarize in 5 bullets after todos.",
            "architecture": "Design the system architecture. Create the directory structure and write interface stubs. Do NOT write full implementations yet.",
            "design": "Design the UI/UX. Create component structure, styles, and layout. Focus on frontend structure only.",
            "implementation": "Implement the features using TDD. For each feature: 1) write a failing test, 2) write code to pass it, 3) refactor. Run tests frequently.",
            "testing": "Run the full test suite. Fix any failures. Add tests for edge cases. Ensure coverage is adequate. Do NOT add new features.",
            "review": "Review the entire codebase for quality, security, and consistency. Refactor as needed. Ensure all tests pass.",
            "deployment": "Create deployment artifacts: Dockerfile, docker-compose, CI/CD config. Add health checks and documentation.",
            "verification": "Run final integration tests. Verify the goal is fully achieved. Update todos to complete. If gaps exist, identify them.",
        }
        return prompts.get(phase, "Continue working toward the goal.")

    def _detect_persona(self, user_input: str) -> Optional[str]:
        """Auto-detect persona from user input keywords."""
        lower = user_input.lower()
        scores: Dict[str, int] = {}
        for persona_key, triggers in PERSONA_TRIGGERS.items():
            score = sum(1 for trigger in triggers if trigger in lower)
            if score > 0:
                scores[persona_key] = score
        if not scores:
            return None
        return max(scores, key=scores.get)

    def _switch_persona(self, new_persona: str, reason: str = "manual"):
        """Switch to a new persona and rebuild system prompt."""
        if new_persona not in PERSONAS:
            return False
        old_name = PERSONAS[self.persona_key]["name"]
        self.persona_key = new_persona
        self.persona_history.append(new_persona)
        self._rebuild_system()
        new_name = PERSONAS[new_persona]["name"]
        if reason == "auto":
            UI.info(f"Auto-switched: {old_name} → {new_name}")
        else:
            UI.ok(f"Switched to {new_name}")
            self.config["default_persona"] = new_persona
            self.persist(force=True)
        return True

    def persist(self, force: bool = False) -> None:
        """Autosave durable state. Call after meaningful state changes."""
        now = time.monotonic()
        if not force and (now - self._last_persist) < 2.0:
            return
        if save_session(self, also_config=True):
            self._last_persist = now

    def _build_payload(self) -> Dict[str, Any]:
        payload = {
            "model": self.pool.current().model_id,
            "messages": self.ctx.export(),
            "temperature": self.config.get("temperature", 0.2),
            "max_tokens": self.model_cfg.get("max_tokens", 8192),
            "stream": True,
            "tools": tools_schema(self.tools),
            "tool_choice": "auto",
        }
        # Only attach model extra_body when thinking is enabled
        effort = str(self.config.get("thinking_effort") or "off").lower()
        if effort in ("low", "medium", "high") and self.model_cfg.get("extra_body"):
            payload["extra_body"] = self.model_cfg["extra_body"]
        return payload


    def _consume_stream(self, provider: "Provider", payload: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]], Optional[str]]:
        """Consume stream with hard wall-clock timeout via background reader.

        ROOT CAUSE FIX:
        - OpenAI/httpx read timeout only applies between socket reads, but
          thinking models (GLM) can legitimately pause 30-90s between chunks.
        - A bare `for chunk in resp` blocks forever if the iterator never
          yields and the socket doesn't die.
        - Solution: read chunks on a daemon thread into a queue; main thread
          enforces stream_timeout + content_timeout with queue.get(timeout=).
        - Reasoning tokens reset the content-stall timer (thinking is progress).

        ROOT CAUSE FIX v2:
        - `client.chat.completions.create(...)` is itself a blocking call: it
          must get a response back before it can return the stream object.
          NIM can hold a connection open with low-level keepalive/framing
          traffic far longer than the configured httpx read timeout without
          ever delivering a usable HTTP response — that resets httpx's read
          timer without a single byte reaching application code.
        - So `create()` now runs INSIDE this same reader thread instead of in
          the caller. first_token_timeout therefore covers the entire
          "request sent -> first token seen" window, including stream
          acquisition, not just "resp object already exists -> first token
          seen". One wall-clock owned by the orchestrator now protects the
          whole pre-first-token phase, regardless of where in the stack a
          stall happens.
        """
        content = ""
        reasoning = ""
        tool_calls: List[Dict[str, Any]] = []
        finish_reason = None
        stream_timeout = float(self.config.get("stream_timeout", 300.0))
        content_timeout = float(self.config.get("stream_content_timeout", 90.0))
        first_token_timeout = float(self.config.get("first_token_timeout", 8.0))
        stream_start = time.monotonic()
        last_content_time = time.monotonic()
        in_think = False
        printed_len = 0
        last_heartbeat = 0
        saw_any_token = False

        # --- Threaded reader so we can hard-kill on stall ---
        chunk_q: "queue.Queue" = __import__("queue").Queue(maxsize=256)
        SENTINEL = object()
        reader_err: List[BaseException] = []
        resp_holder: List[Any] = []

        def _reader():
            try:
                resp = provider.client.chat.completions.create(**payload)
                resp_holder.append(resp)
                for chunk in resp:
                    chunk_q.put(chunk)
            except BaseException as ex:
                reader_err.append(ex)
            finally:
                chunk_q.put(SENTINEL)

        t = threading.Thread(target=_reader, daemon=True, name="neon-stream-reader")
        t.start()

        try:
            while True:
                elapsed = time.monotonic() - stream_start

                # Hard overall stream timeout
                if elapsed > stream_timeout:
                    raise Exception(
                        f"Stream hard timeout after {elapsed:.0f}s (limit: {stream_timeout:.0f}s)"
                    )

                # ROOT CAUSE FIX: NIM can buffer the ENTIRE reasoning phase
                # server-side and emit ZERO bytes until it's done. The old
                # content-stall check below only fires AFTER a token is seen,
                # so total silence was previously bounded only by the 300s
                # stream_timeout — meaning a stuck request looked identical
                # to a dead process for up to 5 minutes per retry attempt.
                # This fires much sooner and hands control back to the retry loop.
                if not saw_any_token and elapsed > first_token_timeout:
                    raise Exception(
                        f"First-token timeout after {elapsed:.0f}s (limit: {first_token_timeout:.0f}s) — "
                        f"backend is likely buffering the full reasoning phase server-side "
                        f"(thinking_effort={self.config.get('thinking_effort')}). Retrying."
                    )

                # Heartbeat every 15s after 20s
                if elapsed > 20 and int(elapsed) - last_heartbeat >= 15:
                    last_heartbeat = int(elapsed)
                    phase = "thinking" if in_think else "streaming"
                    msg = f"  * {phase}... ({elapsed:.0f}s)"
                    if HAS_RICH:
                        console.print(f"  [neon_dim]{msg}[/neon_dim]", end="\r")
                    else:
                        print(msg, end="\r", flush=True)

                # Content / thinking stall (only after first token seen)
                idle = time.monotonic() - last_content_time
                if saw_any_token and idle > content_timeout:
                    raise Exception(
                        f"Content stall — no tokens for {content_timeout:.0f}s "
                        f"(thinking={in_think})"
                    )

                # Wait for next chunk with short poll so we re-check timeouts
                poll = min(2.0, content_timeout / 4.0)
                try:
                    chunk = chunk_q.get(timeout=poll)
                except Exception:
                    # queue.Empty — loop back to check wall-clock / stall
                    if not t.is_alive() and chunk_q.empty():
                        break
                    continue

                if chunk is SENTINEL:
                    break

                if not getattr(chunk, "choices", None):
                    continue

                delta = chunk.choices[0].delta
                if chunk.choices[0].finish_reason is not None:
                    finish_reason = chunk.choices[0].finish_reason

                if delta is None:
                    continue

                has_content = False

                # Reasoning / thinking tokens = progress (reset stall timer)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    has_content = True
                    saw_any_token = True
                    if not in_think:
                        print(" " * 70, end="\r")
                        if self.config.get("show_thinking", True):
                            if HAS_RICH:
                                console.print(UI.thinking_block(""))
                            else:
                                print("* THINKING...")
                        in_think = True
                    reasoning += delta.reasoning_content
                    if self.config.get("show_thinking", True):
                        if HAS_RICH:
                            console.print(Text(delta.reasoning_content, style="thinking"), end="")
                        else:
                            print(delta.reasoning_content, end="", flush=True)

                if delta.content:
                    has_content = True
                    saw_any_token = True
                    if in_think:
                        print()
                        in_think = False
                    content += delta.content
                    new_text = content[printed_len:]
                    if HAS_RICH:
                        console.print(Text(new_text, style="assistant"), end="")
                    else:
                        print(new_text, end="", flush=True)
                    printed_len = len(content)

                if delta.tool_calls:
                    has_content = True
                    saw_any_token = True
                    if in_think:
                        print()
                        in_think = False
                    for tc in delta.tool_calls:
                        idx = tc.index
                        while len(tool_calls) <= idx:
                            tool_calls.append({"id": "", "name": "", "arguments": ""})
                        if tc.id:
                            tool_calls[idx]["id"] += tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls[idx]["name"] += tc.function.name
                                name = tool_calls[idx]["name"]
                                print(" " * 70, end="\r")
                                if HAS_RICH:
                                    console.print(UI.tool_call(name, "..."))
                                else:
                                    print(f"\n* {name}(...)")
                            if tc.function.arguments:
                                tool_calls[idx]["arguments"] += tc.function.arguments

                if has_content:
                    last_content_time = time.monotonic()

            if reader_err:
                raise reader_err[0]

        finally:
            # Best-effort close of underlying response to free sockets.
            # resp now lives inside the reader thread's local scope, so it's
            # only reachable via resp_holder — and only if create() actually
            # returned. If it's still hanging, there's nothing to close yet;
            # the daemon thread is left to resolve (or die with the process).
            try:
                if resp_holder:
                    resp = resp_holder[0]
                    close = getattr(resp, "close", None) or getattr(resp, "http_response", None)
                    if callable(close):
                        close()
                    elif close is not None and hasattr(close, "close"):
                        close.close()
            except Exception:
                pass

        print()
        return content, reasoning, tool_calls, finish_reason

    def _is_transient_error(self, e: Exception) -> bool:
        """Classify whether an error is transient (retryable) or fatal."""
        err_str = str(e).lower().replace(" ", "")
        transient_markers = [
            "timeout", "timedout", "apitimeout", "apiconnection",
            "429", "toomanyrequests", "ratelimit", "resourceexhausted",
            "overloaded", "503", "502", "500", "504", "workerlocal",
            "finish_reason", "dropped", "stall", "degraded",
            "badgateway", "unavailable", "gateway", "first-token", "firsttoken",
        ]
        if any(m in err_str for m in transient_markers):
            return True
        if isinstance(e, OPENAI_ERRORS):
            return True
        return False

    def _parse_stream(self, payload: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
        """Streams to completion with NIM-aware retry architecture.

        ROOT CAUSE FIXES:
        - Non-blocking provider selection (no 5s acquire hang)
        - Cap "all cooling down" wait to 10s max
        - Faster rotate (2 failures per provider)
        - Shorter exponential backoff
        - Apply config thinking_effort override on every call
        """
        max_total_attempts = int(self.config.get("retry_max", 2))
        max_per_provider = int(self.config.get("max_retries_per_provider", 2))
        base_delay = float(self.config.get("retry_base_delay", 1.5))
        total_attempts = 0
        empty_pool_spins = 0

        # Apply thinking_effort from config (overrides model default)
        # Thinking is OFF unless explicitly enabled (effort in low|medium|high).
        # GLM-5.2 with enable_thinking buffers the full reasoning phase server-side
        # before the first SSE token — that was the remaining 5–8s interactive lag.
        effort = str(self.config.get("thinking_effort") or "off").lower()
        payload = dict(payload)
        if effort in ("low", "medium", "high") and (
            self.model_cfg.get("thinking") or self.config.get("autopilot_thinking")
        ):
            extra = dict(payload.get("extra_body") or {})
            ctk = dict(extra.get("chat_template_kwargs") or {})
            ctk["enable_thinking"] = True
            ctk["thinking_effort"] = effort
            extra["chat_template_kwargs"] = ctk
            payload["extra_body"] = extra
        else:
            # Explicitly strip any thinking kwargs inherited from model defaults
            extra = dict(payload.get("extra_body") or {})
            if "chat_template_kwargs" in extra:
                ctk = dict(extra["chat_template_kwargs"])
                ctk["enable_thinking"] = False
                extra["chat_template_kwargs"] = ctk
                payload["extra_body"] = extra
            elif not extra:
                payload.pop("extra_body", None)

        while total_attempts < max_total_attempts:
            provider = self.pool.next_available()
            if not provider:
                empty_pool_spins += 1
                wait = min(self.pool.shortest_wait(), 10.0)
                if empty_pool_spins > 6:
                    raise RuntimeError(
                        "All providers unavailable after repeated waits. "
                        "Check API key / rate limits / network."
                    )
                wait = max(wait, 5.0)  # never busy-spin at 0.0s
                UI.warn(f"All providers cooling down. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue
            empty_pool_spins = 0

            # Soft rate-limit pacing (info only — token already acquired)
            wt = provider.bucket.wait_time()
            if wt > 0.5:
                UI.info(f"Rate limit pacing ({wt:.1f}s)...")
                time.sleep(min(wt, 5.0))

            total_attempts += 1

            try:
                if HAS_RICH:
                    console.print(
                        f"  [neon_dim]* {UI.esc(provider.name)} attempt {total_attempts}/{max_total_attempts}...[/neon_dim]",
                        end="\r"
                    )
                else:
                    print(f"  * {provider.name} attempt {total_attempts}/{max_total_attempts}...", end="\r", flush=True)
                # Belt-and-suspenders: guarantee this line hit the terminal even if the
                # next stage (stream acquisition) stalls, independent of how the console
                # buffers \r-based redraws.
                sys.stdout.flush()

                payload["model"] = provider.model_id

                content, reasoning, tool_calls, finish_reason = self._consume_stream(provider, payload)

                if finish_reason is not None:
                    provider.record_success()
                    return content, reasoning, tool_calls
                else:
                    raise Exception("Stream completed without finish_reason — backend dropped")

            except Exception as e:
                err_l = str(e).lower()
                err_c = err_l.replace(" ", "")

                # 404 = model not available for this account → permanent remove
                if "404" in err_l or "not found" in err_l or "model_not_found" in err_c:
                    UI.warn(f"{provider.name} permanent miss (404) — removed from pool")
                    provider.record_failure(cooldown=600.0, permanent=True)
                    self.pool.rotate()
                    if total_attempts < max_total_attempts:
                        time.sleep(0.3)
                        continue
                    raise RuntimeError(f"All providers failed. Last error: {e}")

                # Auth → stop immediately with clear recovery steps
                if "401" in err_l or "403" in err_l or "unauthorized" in err_l or "forbidden" in err_l:
                    UI.err(f"Auth failure: {e}")
                    UI.warn("NVIDIA rejected this project's API key (403/401).")
                    UI.info("Fix:  /apikey <new-nvapi-key-from-https://build.nvidia.com>")
                    UI.info("Check: key must have access to model z-ai/glm-5.2 on NVIDIA NIM.")
                    UI.info("Or:    /model nemotron-ultra   if that model is enabled on your key.")
                    raise

                # Capacity / rate limit → cool down, rotate once
                if (
                    "resourceexhausted" in err_c
                    or "limit reached" in err_l
                    or "429" in err_l
                    or "ratelimit" in err_c
                ):
                    UI.warn(f"{provider.name} at capacity — cooling 90s, rotating")
                    provider.record_failure(cooldown=20.0)
                    self.pool.rotate()
                elif not self._is_transient_error(e):
                    UI.err(f"Fatal API error: {e}")
                    raise
                else:
                    UI.warn(f"{provider.name} transient: {str(e)[:100]}")
                    provider.record_failure(cooldown=20.0)
                    if self.pool.should_rotate(max_per_provider):
                        self.pool.rotate()

                if total_attempts < max_total_attempts:
                    delay = min(base_delay + random.uniform(0, 1.0), 5.0)
                    UI.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    UI.err(f"Max retries ({max_total_attempts}) exceeded.")
                    raise RuntimeError(f"All providers failed. Last error: {e}")

        raise RuntimeError("Exhausted all retry attempts")

    def _execute_tools(self, tool_calls: List[Dict[str, Any]]) -> bool:
        """Execute tool calls and append results. Returns True if any executed."""
        if not tool_calls:
            return False

        formatted = []
        for tc in tool_calls:
            formatted.append({
                "id": tc["id"],
                "type": "function",
                "function": {"name": tc["name"], "arguments": tc["arguments"]},
            })
        self.ctx.add_assistant(content="", tool_calls=formatted)

        for tc in tool_calls:
            name = tc.get("name", "")
            raw_args = tc.get("arguments", "{}")
            try:
                args = json.loads(raw_args)
            except json.JSONDecodeError:
                args = {}

            preview = json.dumps(args, ensure_ascii=False)[:120]
            if len(preview) > 120:
                preview = preview[:117] + "..."
            if HAS_RICH:
                console.print(UI.tool_call(name, preview))
            else:
                print(f"* {name}({preview})")

            result = execute_tool(self.tools, name, args)
            UI.tool_result(name, result.text()[:500], result.is_error)

            # Deterministic phase-completion tracking (orchestrator-owned facts,
            # not model self-reports). Only meaningful in autopilot, but cheap
            # to track always. Scoped to the CURRENT phase only — TodoTool._todos
            # itself is a class-level counter that persists for the whole
            # session, so we track "add" actions separately per-phase rather
            # than reading that global count (a restored session with old
            # todos already present would otherwise satisfy planning instantly).
            self.current_turn_tool_calls = True
            self._phase_tool_counts[name] = self._phase_tool_counts.get(name, 0) + 1
            if name == "todo" and args.get("action") == "add" and not result.is_error:
                self._phase_tool_counts["todo_add"] = self._phase_tool_counts.get("todo_add", 0) + 1
            if name == "bash" and not result.is_error:
                cmd = str(args.get("command") or "").lower()
                # dir/ls/echo must NOT complete TESTING
                if any(
                    x in cmd
                    for x in (
                        "pytest",
                        "python -m pytest",
                        "python -m unittest",
                        "unittest",
                        "npm test",
                        "npx jest",
                        "cargo test",
                        "go test",
                        "test_core.py",
                        "test_agents.py",
                    )
                ):
                    self._phase_bash_ok = True

            ctx_tokens = self.ctx.estimate_tokens()
            max_tool_len = max(2000, (self.model_cfg["ctx_window"] - ctx_tokens) * 4)
            self.ctx.add_tool_result(tc["id"], name, result.text()[:max_tool_len])

        return True

    def _should_nudge(self, content: str) -> bool:
        """Detect if the assistant announced intent without calling a tool."""
        if not self.config.get("auto_nudge", True):
            return False
        if self.nudges >= self.config.get("max_nudges", 3):
            return False
        if len(content) > 1000:
            return False
        phrases = [
            "let me", "i will", "i'll", "i need to", "i'm going to",
            "allow me to", "i should", "here is the plan", "first, i",
            "next, i", "i can", "i would like to", "i shall", "i intend to"
        ]
        lower = content.lower()
        return any(p in lower for p in phrases)

    def run_turn(self, user_input: str):
        """Execute one full turn: user input → persona detect → LLM → tools → loop.
        In autopilot mode, the agent self-directs through SDLC phases."""
        if user_input:
            # Handle autopilot commands
            if user_input.lower() == "/stop":
                self._stop_autopilot()
                return
            if user_input.lower() == "/status":
                self._autopilot_status()
                return
            # Auto-detect persona if in adaptive mode and NOT in autopilot
            if not self.autopilot and PERSONAS[self.persona_key]["auto_switch"]:
                detected = self._detect_persona(user_input)
                if detected and detected != self.persona_key:
                    self._switch_persona(detected, reason="auto")
            self.ctx.add_user(user_input)
            if HAS_RICH:
                console.print(UI.user_message(user_input))
            else:
                print(f">>> {user_input}")

        # Cap = max(max_rounds, max_autopilot_rounds) so autopilot never dies at 100
        _cap = int(self.config.get("max_rounds", 500))
        if self.autopilot:
            _cap = max(_cap, int(self.config.get("max_autopilot_rounds", self.max_autopilot_rounds)))
        while self.round < _cap:
            self.round += 1
            self.current_turn_tool_calls = False
            if self.autopilot:
                self.autopilot_rounds += 1
                max_ap = int(self.config.get("max_autopilot_rounds", self.max_autopilot_rounds))
                if self.autopilot_rounds > max_ap:
                    # Soft limit: do NOT abandon the goal. Extend budget and
                    # force-advance a stuck phase so autopilot can finish.
                    UI.warn(
                        f"Autopilot round budget ({max_ap}) reached — extending +100 "
                        f"(goal not complete; phase={SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else 'done'})"
                    )
                    self.max_autopilot_rounds = max_ap + 100
                    self.config["max_autopilot_rounds"] = self.max_autopilot_rounds
                    # Force phase advance if still stuck in early phases
                    if self.sdlc_phase_idx < len(SDLC_PHASES) - 1:
                        UI.warn("Force-advancing SDLC phase so work can continue toward the goal.")
                        self._advance_sdlc()

            # Periodic autosave (every N turns)
            if self.round % max(1, self._persist_every) == 0:
                self.persist()

            # Context compaction check
            if self.ctx.should_compact():
                before = self.ctx.estimate_tokens()
                if self.ctx.compact(keep_recent=8):
                    after = self.ctx.estimate_tokens()
                    UI.info(f"Context compacted: ~{before:,} → ~{after:,} tokens")
                    self._rebuild_system()

            tokens = self.ctx.estimate_tokens()
            phase_tag = ""
            if self.autopilot and self.sdlc_phase_idx < len(SDLC_PHASES):
                phase_tag = f" | {SDLC_PHASES[self.sdlc_phase_idx].upper()}"
            if HAS_RICH:
                console.print(UI.turn_indicator(self.round, tokens, phase_tag))
            else:
                UI.separator(f"TURN {self.round} | ~{tokens} tokens{phase_tag}")

            payload = self._build_payload()

            try:
                content, reasoning, tool_calls = self._parse_stream(payload)
            except Exception as e:
                UI.err(f"Turn failed: {e}")
                if self.autopilot:
                    # Survive provider outages: save, wait, CONTINUE (don't abandon goal)
                    self.persist(force=True)
                    err_l = str(e).lower()
                    wait = 25.0 if any(x in err_l for x in ("timeout", "capacity", "429", "resource")) else 12.0
                    phase = SDLC_PHASES[min(self.sdlc_phase_idx, len(SDLC_PHASES) - 1)].upper()
                    UI.warn(
                        f"Provider hiccup — sleeping {wait:.0f}s then continuing "
                        f"(phase={phase}, round={self.autopilot_rounds}). /stop to halt."
                    )
                    time.sleep(wait)
                    continue
                break

            # Record tokens (heuristic)
            self.meter.record(tokens, len(content) // 4 + len(reasoning) // 4)

            # XML hallucination interceptor
            if not tool_calls and re.search(r"<(tool_call|function|parameter)", content):
                UI.warn("Detected XML hallucination. Correcting...")
                self.ctx.add_assistant(content)
                self.ctx.add_user(
                    "SYSTEM: You output raw XML for a tool call. This is forbidden. "
                    "Use the native JSON function calling API. Re-issue correctly."
                )
                time.sleep(0.5)
                continue

            # Tool execution
            if tool_calls:
                self.nudges = 0
                self._execute_tools(tool_calls)
                # Persist immediately if todos or files changed
                tool_names = {tc.get("name", "") for tc in tool_calls}
                if tool_names & {"todo", "write", "edit"}:
                    self.persist(force=True)
                delay = float(self.config.get("inter_turn_delay", 0.1))
                time.sleep(max(0.1, delay))
                # In autopilot, after tools execute, continue to next round automatically
                if self.autopilot:
                    phase_name = SDLC_PHASES[min(self.sdlc_phase_idx, len(SDLC_PHASES) - 1)]
                    stuck_limit = int(self.config.get("max_phase_rounds", 4))
                    if phase_name in ("implementation", "testing"):
                        stuck_limit = max(stuck_limit, 20)
                    elif phase_name in ("architecture", "design"):
                        stuck_limit = max(stuck_limit, 8)
                    force_phase = self._phase_rounds >= stuck_limit
                    if force_phase and phase_name == "implementation":
                        we = (
                            self._phase_tool_counts.get("write", 0)
                            + self._phase_tool_counts.get("edit", 0)
                        )
                        if we < 8:
                            force_phase = False
                            if self._phase_rounds % 5 == 0:
                                UI.warn(
                                    f"IMPLEMENTATION needs more coding "
                                    f"(write/edit={we}/8) — keep implementing under project dir"
                                )
                    if force_phase and not self._phase_requirements_met():
                        UI.warn(
                            f"Phase stuck ({self._phase_rounds} turns in "
                            f"{phase_name.upper()}) — force-advancing"
                        )
                    if (
                        self._phase_requirements_met()
                        or self._should_advance_phase(content)
                        or force_phase
                    ):
                        if not self._advance_sdlc():
                            UI.separator("GOAL ACHIEVED")
                            UI.ok("All SDLC phases complete!")
                            self._stop_autopilot()
                            break
                    continue
                continue

            # No tools — assistant response
            self.ctx.add_assistant(content)

            # Auto-nudge if assistant announced but didn't act
            if self._should_nudge(content):
                self.nudges += 1
                if self.nudges >= self.config.get("max_nudges", 3) and self.autopilot:
                    # Nudge cap hit in autopilot — inject a hard imperative and reset counter
                    UI.warn("Nudge cap hit in autopilot. Injecting hard command...")
                    self.ctx.add_user(
                        "SYSTEM OVERRIDE: Stop planning and talking. Execute a tool call RIGHT NOW. "
                        "Pick the most important next action and call the tool immediately. "
                        "Do not explain. Do not ask. Just call the tool."
                    )
                    self.nudges = 0
                else:
                    UI.warn("Agent paused without action. Nudging...")
                    self.ctx.add_user(
                        "Please proceed and execute the tool you just mentioned. "
                        "Do not ask for permission. Call the tool now."
                    )
                time.sleep(0.5)  # was 1.5s — reduced
                continue

            self.nudges = 0

            # Autopilot: auto-proceed after assistant responds without tools
            if self.autopilot:
                if self._phase_requirements_met() or self._should_advance_phase(content):
                    if not self._advance_sdlc():
                        UI.separator("GOAL ACHIEVED")
                        UI.ok("All SDLC phases complete!")
                        self._stop_autopilot()
                        break
                # Inject autopilot prompt for next action
                self.ctx.add_user(self._autopilot_prompt())
                delay = float(self.config.get("inter_turn_delay", 0.1))
                time.sleep(max(0.1, delay))
                continue

            break

        else:
            UI.warn("Max rounds reached. Stopping.")
            if self.autopilot:
                self._stop_autopilot()

    def _phase_requirements_met(self) -> bool:
        """ORCHESTRATOR-OWNED, DETERMINISTIC phase-completion check.

        This is the primary gate. It checks observable facts produced by real
        tool execution during the CURRENT phase only (todos created, files
        written, a bash command that actually exited 0) — never the model's
        own claims about its progress. A thinking model is probabilistic and
        will not reliably say "planning complete"; it will, however,
        deterministically either have called todo(add) three times or not.

        The textual/heuristic check in _should_advance_phase remains as a
        secondary signal and the stuck-round timer remains as a last resort,
        but this is what should fire in the common case.
        """
        if not self.autopilot:
            return False
        if self.sdlc_phase_idx >= len(SDLC_PHASES):
            return False
        phase = SDLC_PHASES[self.sdlc_phase_idx]
        reqs = SDLC_PHASE_REQUIREMENTS.get(phase)
        if not reqs:
            return False

        kind = reqs.get("kind")

        if kind == "todo_count":
            min_todos = reqs.get("min_todos", 3)
            added_this_phase = self._phase_tool_counts.get("todo_add", 0)
            met = added_this_phase >= min_todos
            if met:
                UI.info(f"Deterministic gate met: {added_this_phase} todo(s) added this phase (>= {min_todos}) → advancing from {phase.upper()}")
            return met

        if kind == "tool_calls":
            any_tool = reqs.get("any_tool", [])
            min_calls = reqs.get("min_calls", 1)
            total = sum(self._phase_tool_counts.get(t, 0) for t in any_tool)
            met = total >= min_calls
            if met:
                UI.info(f"Deterministic gate met: {total} call(s) to {any_tool} (>= {min_calls}) → advancing from {phase.upper()}")
            return met

        if kind == "bash_success":
            met = self._phase_bash_ok
            if met:
                UI.info(f"Deterministic gate met: a bash command exited 0 in this phase → advancing from {phase.upper()}")
            return met

        return False

    def _should_advance_phase(self, content: str) -> bool:
        """Heuristic FALLBACK: determine if the current SDLC phase is complete.

        This is now the SECONDARY signal. _phase_requirements_met() (checked
        first by the caller) is the primary, deterministic gate based on
        actual tool execution. This method exists for cases where the model
        clearly announces completion in prose before the deterministic
        threshold is hit, plus the stuck-round timer as a last-resort escape
        hatch if neither the deterministic check nor prose ever fires.
        """
        if not self.autopilot:
            return False
        lower = content.lower()
        phase = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else ""

        # Count every turn in this phase (tool spam used to freeze the stuck-timer)
        self._phase_rounds += 1

        # IMPLEMENTATION / TESTING: prose alone must NEVER advance — only tool gates
        if phase in ("implementation", "testing", "verification"):
            return False

        # Phase-specific completion signals — broader to catch thinking-model phrasing
        signals = {
            "planning": [
                "plan complete", "todo list created", "todos added",
                "planning complete", "breakdown complete", "planning is done",
                "ready for architecture",
            ],
            "architecture": [
                "architecture complete", "design done", "structure defined", "interfaces created",
                "architecture is complete", "architecture done", "system design complete",
                "directory structure", "have defined the", "have designed the",
                "ready for implementation", "ready to implement",
            ],
            "design": [
                "design complete", "ui designed", "components ready", "layout done",
                "design is complete", "ui complete", "ux done", "frontend ready",
                "have designed", "have created the components",
            ],
            "implementation": [
                "implementation complete", "feature done", "all tests pass", "code written",
                "implementation is complete", "implementation done", "feature complete",
                "have implemented", "code is complete", "features implemented",
                "tests are passing", "tests pass",
            ],
            "testing": [
                "tests pass", "coverage complete", "all green", "testing done",
                "testing complete", "all tests pass", "test suite complete",
                "have written tests", "tests are complete", "coverage is",
            ],
            "review": [
                "review complete", "refactoring done", "code clean", "audit passed",
                "review is complete", "code review done", "refactoring complete",
                "have reviewed", "code is clean", "review done",
            ],
            "deployment": [
                "deployment ready", "docker complete", "ci/cd configured", "deployed",
                "deployment complete", "dockerfile created", "docker-compose",
                "have created the dockerfile", "ci/cd complete", "deployment done",
            ],
            "verification": [
                "verification complete", "goal achieved", "all criteria met", "ready for release",
                "verification done", "all verified", "goal is achieved",
                "have verified", "everything works", "complete and working",
            ],
        }

        for signal in signals.get(phase, []):
            if signal in lower:
                UI.info(f"Phase signal detected: '{signal}' → advancing from {phase.upper()}")
                return True

        # Generic "moving on" language
        generic_advance = [
            "moving to", "next phase", "proceed to", "let's move",
            "moving on to", "transitioning to", "advancing to",
            "now proceed", "now move", "phase is complete", "phase complete",
        ]
        if any(p in lower for p in generic_advance):
            UI.info(f"Generic advance signal detected → advancing from {phase.upper()}")
            return True

        # Stuck-timer fallback: force-advance if we've been in this phase too long
        max_rounds = self._max_phase_rounds
        if self._phase_rounds >= max_rounds:
            UI.warn(
                f"Phase {phase.upper()} stuck for {self._phase_rounds} rounds "
                f"(limit: {max_rounds}). Force-advancing."
            )
            return True

        return False

    def cmd_files(self):
        tree = UI.file_tree(self.project_dir, self.project_dir)
        if HAS_RICH:
            box_style = MINIMAL if LEGACY_WIN_CONSOLE else ROUNDED
            console.print(Panel(tree, title="[neon_cyan]Project Files[/neon_cyan]", border_style="neon_magenta", padding=(1, 2), box=box_style))
        else:
            print(tree)

    def cmd_cost(self):
        UI.info(self.meter.report())

    def cmd_compact(self):
        before = self.ctx.estimate_tokens()
        if self.ctx.compact(keep_recent=8):
            after = self.ctx.estimate_tokens()
            UI.ok(f"Compacted: ~{before:,} → ~{after:,} tokens")
        else:
            UI.info("Nothing to compact yet.")

    def cmd_model(self, name: str):
        if name in MODELS:
            self.model_key = name
            self.model_cfg = MODELS[name]
            self.config["default_model"] = name
            UI.ok(f"Switched to {self.model_cfg['name']}")
            self._rebuild_system()
            self.persist(force=True)
        else:
            available = ", ".join(MODELS.keys())
            UI.err(f"Unknown model '{name}'. Available: {available}")

    def cmd_todo(self):
        todo_tool = TodoTool(self.project_dir)
        result = todo_tool.execute(action="list")
        if HAS_RICH:
            box_style = MINIMAL if LEGACY_WIN_CONSOLE else ROUNDED
            console.print(Panel(
                Text.from_markup(f"[neon_yellow]{UI.esc(result.text())}[/neon_yellow]"),
                title="[neon_cyan]Task Tracker[/neon_cyan]",
                border_style="neon_magenta",
                box=box_style
            ))
        else:
            print(result.text())

    def cmd_goal(self, goal_text: str = ""):
        if not goal_text.strip():
            if self.goal:
                UI.info(f"Current goal: {self.goal}")
                if not self.autopilot:
                    UI.info("Type /autopilot to start autonomous development toward this goal.")
            else:
                UI.info("No goal set. Use /goal <description> to set one, then /autopilot to start.")
            return
        self.goal = goal_text.strip()
        self.autopilot = False  # reset autopilot on new goal
        self.sdlc_phase_idx = 0
        self.sdlc_completed.clear()
        self._rebuild_system()
        self.persist(force=True)
        UI.ok(f"Goal set: {self.goal}")
        UI.info("Type /autopilot to enter GOD MODE — the agent will autonomously run full SDLC with TDD until the goal is reached.")
        UI.info("Type /status to check progress, /stop to halt.")

    def cmd_persona(self, persona_key: str = ""):
        if not persona_key.strip():
            current = PERSONAS[self.persona_key]
            UI.info(f"Current: {current['name']} — {current['description']}")
            UI.info("Available: " + ", ".join(f"{k} ({v['name']})" for k, v in PERSONAS.items()))
            if self.persona_history:
                UI.info("Recent: " + " → ".join(PERSONAS[p]["name"] for p in self.persona_history))
            return
        if self._switch_persona(persona_key.strip().lower()):
            pass  # _switch_persona already prints
        else:
            available = ", ".join(PERSONAS.keys())
            UI.err(f"Unknown persona '{persona_key}'. Available: {available}")

    def cmd_autopilot(self):
        """Start or resume god autopilot mode."""
        if self.autopilot:
            UI.info("Autopilot is already running.")
            self._autopilot_status()
            return
        if not self.goal:
            UI.err("No goal set. Use /goal <description> first.")
            return
        self._start_autopilot()
        # Immediately trigger first turn with autopilot prompt
        self.run_turn(self._autopilot_prompt())


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: CONFIG & SESSION PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

def load_config() -> Dict[str, Any]:
    """Load multi-project config. Migrates legacy single-key config.json once.

    Schema:
      {
        "version": "...",
        "projects": {
          "C:/path/to/proj": {
            "api_key": "nvapi-...",
            "default_model": "glm-5.2",
            "default_persona": "adaptive",
            "last_goal": "...",
            "last_sdlc_phase_idx": 0,
            "last_sdlc_completed": [],
            ...optional timeout overrides...
          },
          ...
        },
        "active_project": "C:/path/to/proj",
        # plus global defaults for fields not overridden per project
      }
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    raw: Dict[str, Any] = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                raw = loaded
        except Exception:
            raw = {}

    migrated = False

    # --- Migrate legacy flat config (single api_key at top level) → projects map ---
    if "projects" not in raw or not isinstance(raw.get("projects"), dict):
        raw["projects"] = {}
        migrated = True

    # Old-style: api_key + project_dir at top level
    legacy_key = (raw.get("api_key") or "").strip() if isinstance(raw.get("api_key"), str) else ""
    legacy_proj = raw.get("project_dir") or raw.get("active_project")
    if legacy_key and legacy_proj:
        pkey = str(Path(str(legacy_proj)).resolve())
        entry = dict(raw["projects"].get(pkey) or {})
        if not entry.get("api_key"):
            entry["api_key"] = legacy_key
            migrated = True
        for field in (
            "default_model", "default_persona", "last_goal",
            "last_sdlc_phase_idx", "last_sdlc_completed", "thinking_effort",
        ):
            if field in raw and field not in entry:
                entry[field] = raw[field]
                migrated = True
        raw["projects"][pkey] = entry
        raw["active_project"] = pkey
        # Strip legacy top-level secret
        if "api_key" in raw:
            del raw["api_key"]
            migrated = True

    # Also absorb any standalone .key.json files into projects map
    try:
        for kp in SESSIONS_DIR.glob("project_*.key.json"):
            data = _safe_json_load(kp)
            if not data:
                continue
            proj = data.get("project")
            key = (data.get("api_key") or "").strip()
            if not proj or not key:
                continue
            pkey = str(Path(str(proj)).resolve())
            entry = dict(raw["projects"].get(pkey) or {})
            if entry.get("api_key") != key:
                entry["api_key"] = key
                raw["projects"][pkey] = entry
                migrated = True
    except Exception:
        pass

    # Fill global defaults
    for k, v in DEFAULT_CONFIG.items():
        if k == "api_key":
            continue  # never keep a global key
        if k not in raw:
            raw[k] = v
            migrated = True

    raw["version"] = APP_VERSION
    if "projects" not in raw:
        raw["projects"] = {}

    # Enforce hardened thinking-safe globals (overwrite stale / contradictory values)
    _HARDWIRE = {
        "stream_timeout": 420.0,
        "request_timeout": 420.0,
        "stream_content_timeout": 150.0,
        "first_token_timeout": 90.0,       # critical: 25s caused false stalls under high think
        "http_read_timeout": 180.0,
        "http_connect_timeout": 15.0,
        "retry_max": 8,
        "retry_base_delay": 2.5,
        "max_retries_per_provider": 3,
        "inter_turn_delay": 0.35,
        "compact_threshold": 0.3,
        "startup_compact_tokens": 60000,
        "max_rounds": 500,
        "max_autopilot_rounds": 500,
        "max_phase_rounds": 4,
        "rpm_safety": 0.80,
        "thinking_effort": "high",
        "show_thinking": True,
        "autopilot_thinking": True,
    }
    for _k, _v in _HARDWIRE.items():
        if raw.get(_k) != _v:
            raw[_k] = _v
            migrated = True

    if migrated:
        try:
            save_config(raw)
        except Exception:
            pass
    return raw


def save_config(cfg: Dict[str, Any]):
    """Write multi-project config. Never leaves a top-level api_key or nested _root."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    out = dict(cfg)
    # Strip runtime-only / secret / recursive junk
    for k in ("api_key", "_fresh", "_root"):
        out.pop(k, None)
    # Prefer projects map from root if someone passed a flat runtime cfg by mistake
    if not isinstance(out.get("projects"), dict) or not out["projects"]:
        # empty projects is ok for brand-new install
        out.setdefault("projects", {})
    # Never embed last_goal at top-level as the only goal source for all projects
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


def get_project_entry(cfg: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    """Return the per-project settings dict (mutable view into cfg['projects'])."""
    pkey = str(Path(project_dir).resolve())
    projects = cfg.setdefault("projects", {})
    if pkey not in projects or not isinstance(projects[pkey], dict):
        projects[pkey] = {}
    return projects[pkey]


def apply_project_to_runtime(cfg: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
    """Merge global defaults + this project's entry into a flat runtime config.

    Runtime code still sees cfg['api_key'], cfg['default_model'], etc.
    """
    pkey = str(Path(project_dir).resolve())
    entry = get_project_entry(cfg, project_dir)
    runtime = dict(DEFAULT_CONFIG)
    # global non-secret overrides from cfg
    for k, v in cfg.items():
        if k in ("projects", "api_key", "active_project"):
            continue
        runtime[k] = v
    # project overrides win (except hardwired thinking / stall policy below)
    for k, v in entry.items():
        runtime[k] = v
    # Pin thinking-safe policy — project/session/legacy config cannot disable
    runtime["thinking_effort"] = "high"
    runtime["show_thinking"] = True
    runtime["autopilot_thinking"] = True
    runtime["first_token_timeout"] = max(90.0, float(runtime.get("first_token_timeout") or 90.0))
    runtime["stream_content_timeout"] = max(150.0, float(runtime.get("stream_content_timeout") or 150.0))
    runtime["http_read_timeout"] = max(180.0, float(runtime.get("http_read_timeout") or 180.0))
    runtime["stream_timeout"] = max(420.0, float(runtime.get("stream_timeout") or 420.0))
    runtime["request_timeout"] = max(420.0, float(runtime.get("request_timeout") or 420.0))
    runtime["project_dir"] = pkey
    runtime["api_key"] = (entry.get("api_key") or "").strip()
    cfg["active_project"] = pkey
    return runtime


def save_project_settings(cfg: Dict[str, Any], project_dir: Path, **fields: Any) -> None:
    """Update fields for one project and write config.json."""
    entry = get_project_entry(cfg, project_dir)
    for k, v in fields.items():
        if v is None and k in entry:
            continue
        entry[k] = v
    cfg["active_project"] = str(Path(project_dir).resolve())
    save_config(cfg)


def ensure_api_key(cfg: Dict[str, Any], project_dir: Optional[Path] = None) -> bool:
    """Resolve API key for THIS project only (multi-entry config).

    Priority:
      1. projects[<path>].api_key in config.json
      2. Legacy per-project .key.json file (migrated upward)
      3. Env NVIDIA_API_KEY / NGC_API_KEY / NIM_API_KEY
      4. Interactive prompt → stored under projects[<path>]
    """
    project = Path(project_dir or cfg.get("project_dir") or ".").resolve()
    entry = get_project_entry(cfg, project)

    key = (entry.get("api_key") or "").strip()
    if not key:
        # legacy sidecar file
        key = load_project_api_key(project)
        if key:
            entry["api_key"] = key
            save_config(cfg)

    if not key:
        key = (
            os.environ.get("NVIDIA_API_KEY")
            or os.environ.get("NGC_API_KEY")
            or os.environ.get("NIM_API_KEY")
            or ""
        ).strip()
        if key:
            entry["api_key"] = key
            save_config(cfg)
            UI.info(f"API key from env stored under projects[{project}]")

    if key:
        cfg["api_key"] = key  # runtime flat access for build_pool
        return True

    UI.separator("API key for this project")
    UI.info(f"Project: {project}")
    UI.info(f"Config:  {CONFIG_FILE}")
    UI.info("Each project has its own entry + key (avoids throttling one NVIDIA account).")
    UI.info("Get a key at https://build.nvidia.com")
    try:
        key = input("NVIDIA API Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        key = ""
    if not key:
        UI.err("API key required for this project.")
        return False
    entry["api_key"] = key
    cfg["api_key"] = key
    save_config(cfg)
    # keep sidecar in sync for older tools
    try:
        save_project_api_key(project, key)
    except Exception:
        pass
    UI.ok(f"Saved project API key → {CONFIG_FILE} [{project}]")
    return True



def save_session(agent: "NeonArchitect", *, also_config: bool = True) -> bool:
    """Persist full agent state for this project so relaunch restores everything."""
    try:
        SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        session = {
            "state_version": STATE_VERSION,
            "timestamp": datetime.now().isoformat(),
            "project": str(agent.project_dir),
            "model": agent.model_key,
            "persona": agent.persona_key,
            "persona_history": list(agent.persona_history),
            "goal": agent.goal,
            "autopilot": False,  # never auto-resume god mode (safety)
            "sdlc_phase_idx": agent.sdlc_phase_idx,
            "sdlc_completed": sorted(agent.sdlc_completed),
            "autopilot_rounds": agent.autopilot_rounds,
            "round": agent.round,
            "messages": agent.ctx.export(),
            "compaction_summary": agent.ctx.compaction_summary,
            "meter": {"prompt": agent.meter.prompt, "completion": agent.meter.completion},
            "todos": dict(TodoTool._todos),
            "todo_counter": TodoTool._counter,
            "thinking_effort": agent.config.get("thinking_effort"),
        }
        sf = _project_session_path(agent.project_dir)
        tmp = sf.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(session, f, ensure_ascii=False, indent=2)
        tmp.replace(sf)

        # Also keep a rolling history entry
        try:
            with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
                hf.write(json.dumps({
                    "ts": session["timestamp"],
                    "project": session["project"],
                    "model": session["model"],
                    "goal": session["goal"],
                    "phase": session["sdlc_phase_idx"],
                    "tokens": session["meter"]["prompt"] + session["meter"]["completion"],
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass

        if also_config:
            root = agent.config.get("_root") or load_config()
            fields = {
                "default_model": agent.model_key,
                "default_persona": agent.persona_key,
                "last_sdlc_phase_idx": agent.sdlc_phase_idx,
                "last_sdlc_completed": sorted(agent.sdlc_completed),
            }
            if agent.goal is not None:
                fields["last_goal"] = agent.goal
            # preserve existing api_key on the entry
            save_project_settings(root, agent.project_dir, **fields)
            agent.config["_root"] = root
        return True
    except Exception as e:
        try:
            UI.warn(f"Session save failed: {e}")
        except Exception:
            pass
        return False


def load_session(project_dir: Path) -> Optional[Dict[str, Any]]:
    """Load the latest persisted state for this project directory."""
    data = _safe_json_load(_project_session_path(project_dir))
    if not data:
        return None
    # Reject ancient incompatible schemas softly
    if int(data.get("state_version", 0)) > STATE_VERSION + 5:
        return None
    return data


def apply_session(agent: "NeonArchitect", data: Dict[str, Any]) -> None:
    """Restore agent fields from a saved session dict."""
    if not data:
        return
    # Model
    mk = data.get("model") or agent.config.get("default_model")
    if mk and mk in MODELS:
        agent.model_key = mk
        agent.model_cfg = MODELS[mk]
        agent.config["default_model"] = mk

    # Persona
    pk = data.get("persona") or agent.config.get("default_persona", "adaptive")
    if pk in PERSONAS:
        agent.persona_key = pk
        agent.config["default_persona"] = pk
    for p in data.get("persona_history") or []:
        if p in PERSONAS:
            agent.persona_history.append(p)

    # Goal + SDLC (do NOT auto-enable autopilot)
    agent.goal = data.get("goal")
    agent.sdlc_phase_idx = int(data.get("sdlc_phase_idx") or 0)
    agent.sdlc_completed = set(data.get("sdlc_completed") or [])
    agent.autopilot_rounds = int(data.get("autopilot_rounds") or 0)
    agent.autopilot = False
    agent.round = int(data.get("round") or 0)
    agent._phase_rounds = 0  # always reset on restore so stuck-timer starts fresh
    agent._phase_tool_counts = {}
    agent._phase_bash_ok = False

    # Tokens
    meter = data.get("meter") or {}
    agent.meter.prompt = int(meter.get("prompt") or 0)
    agent.meter.completion = int(meter.get("completion") or 0)

    # Todos
    todos = data.get("todos")
    if isinstance(todos, dict):
        TodoTool._todos = {str(k): v for k, v in todos.items() if isinstance(v, dict)}
        TodoTool._counter = int(data.get("todo_counter") or len(TodoTool._todos))

    # Do NOT restore thinking_effort / show_thinking from session — those are
    # hardwired runtime policy. Old sessions saved "off" and kept killing think mode.

    # Messages (keep system out — rebuilt below)
    msgs = data.get("messages") or []
    restored = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        if role == "system":
            continue  # rebuilt by _rebuild_system
        restored.append(m)
    agent.ctx.messages = restored
    agent.ctx.compaction_summary = data.get("compaction_summary")

    agent._rebuild_system()


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9: MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--project", "-p", default=None,
                        help="Project directory (default: current working directory)")
    parser.add_argument("--model", "-m", default=None, help="Model key (glm-5.2, nemotron-ultra, ...)")
    parser.add_argument("--fresh", action="store_true",
                        help="Start a clean session (do not restore prior goal/messages/todos)")
    args = parser.parse_args()

    root_cfg = load_config()
    # Claude Code style: project = cwd unless -p is given.
    if args.project:
        project = Path(args.project).resolve()
    else:
        project = Path.cwd().resolve()

    # Merge this project's entry (api_key, model, goal prefs) into flat runtime cfg
    cfg = apply_project_to_runtime(root_cfg, project)
    cfg["_root"] = root_cfg  # keep handle for multi-project saves
    if args.model:
        cfg["default_model"] = args.model
        save_project_settings(root_cfg, project, default_model=args.model)
    if args.fresh:
        cfg["_fresh"] = True

    if not ensure_api_key(cfg, project_dir=project):
        sys.exit(1)
    # refresh key into runtime after ensure
    cfg["api_key"] = get_project_entry(root_cfg, project).get("api_key", "")

    os.system("cls" if os.name == "nt" else "clear")
    UI.neon_banner()
    if HAS_RICH:
        console.print(UI.header(
            MODELS.get(cfg["default_model"], MODELS["glm-5.2"])["name"],
            str(project),
        ))
    else:
        print(f"{APP_NAME} v{APP_VERSION}")
        print(f"Model: {cfg.get('default_model')} | Project: {project}")

    try:
        agent = NeonArchitect(cfg)
    except Exception as e:
        UI.err(f"Failed to initialize: {e}")
        sys.exit(1)

    # Survive crashes / abrupt kill where possible
    atexit.register(lambda: save_session(agent, also_config=True))

    # Persist this project's prefs into config.json → projects[<path>]
    try:
        root = agent.config.get("_root") or load_config()
        save_project_settings(
            root,
            project,
            default_model=agent.model_key,
            default_persona=agent.persona_key,
        )
        agent.config["_root"] = root
        # Keep runtime flat fields in sync
        agent.config["project_dir"] = str(project)
        agent.config["version"] = APP_VERSION
    except Exception as e:
        UI.warn(f"Could not update config: {e}")

    UI.separator("Ready")
    # Masked key status — per-project entry in config.json
    _k = (agent.config.get("api_key") or "")
    _nproj = len((agent.config.get("_root") or load_config()).get("projects") or {})
    if _k:
        _masked = (_k[:6] + "…" + _k[-4:]) if len(_k) > 12 else "***"
        UI.info(f"API key (this project): {_masked}")
    else:
        UI.warn("No API key for this project — set with /apikey")
    UI.info(f"Config: {CONFIG_FILE}  ·  {_nproj} project entr{'y' if _nproj == 1 else 'ies'}")
    UI.info("Type your request. Empty Enter = proceed.")
    UI.info("Commands: /new /apikey /files /cost /clear /reset /compact /model /todo /goal /persona /autopilot /status /stop /exit")
    UI.info(
        f"First token: {agent.config.get('first_token_timeout', 5)}s | "
        f"Retries: {agent.config.get('retry_max', 2)} | "
        f"Thinking: {agent.config.get('thinking_effort', 'off')} | "
        f"HTTP read: {agent.config.get('http_read_timeout', 60)}s"
    )
    UI.info("Personas: architect, designer, engineer, tester, debugger, reviewer, devops (or adaptive)")
    UI.info("GOD MODE: /goal <desc> → /autopilot → full SDLC with TDD until goal reached")

    while True:
        try:
            if HAS_RICH:
                raw = console.input("[cc_prompt]❯[/cc_prompt] ").strip()
            else:
                raw = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not raw:
            raw = "Please proceed with the current task."

        if raw == "/exit":
            break
        if raw == "/clear":
            agent.ctx.clear()
            agent.round = 0
            agent.nudges = 0
            agent._rebuild_system()
            agent.persist(force=True)
            UI.ok("Context cleared (goal/model/todos kept). State saved.")
            continue
        if raw == "/files":
            agent.cmd_files()
            continue
        if raw == "/cost":
            agent.cmd_cost()
            continue
        if raw == "/compact":
            agent.cmd_compact()
            continue
        if raw.startswith("/model "):
            agent.cmd_model(raw.split(None, 1)[1].strip())
            continue
        if raw == "/todo":
            agent.cmd_todo()
            continue
        if raw.startswith("/goal "):
            agent.cmd_goal(raw.split(None, 1)[1].strip())
            continue
        if raw == "/goal":
            agent.cmd_goal()
            continue
        if raw.startswith("/persona "):
            agent.cmd_persona(raw.split(None, 1)[1].strip())
            continue
        if raw == "/persona":
            agent.cmd_persona()
            continue
        if raw == "/autopilot":
            agent.cmd_autopilot()
            continue
        if raw == "/status":
            agent._autopilot_status()
            continue
        if raw == "/stop":
            agent._stop_autopilot()
            continue
        if raw.startswith("/apikey"):
            parts = raw.split(None, 1)
            root = agent.config.get("_root") or load_config()
            entry = get_project_entry(root, agent.project_dir)
            if len(parts) < 2 or not parts[1].strip():
                UI.info(f"Project: {agent.project_dir}")
                UI.info(f"Config:  {CONFIG_FILE}")
                k = (entry.get("api_key") or agent.config.get("api_key") or "")
                if k:
                    UI.info(f"Current key: {k[:6]}…{k[-4:] if len(k)>12 else '***'}")
                else:
                    UI.warn("No API key set for this project.")
                UI.info(f"Projects in config: {len(root.get('projects') or {})}")
                for pp in sorted((root.get("projects") or {}).keys()):
                    has = "key=yes" if (root["projects"][pp] or {}).get("api_key") else "key=no"
                    mark = "→" if pp == str(agent.project_dir.resolve()) else " "
                    UI.info(f"  {mark} {pp} ({has})")
                UI.info("Usage: /apikey <your-nvidia-key>")
                continue
            new_key = parts[1].strip().strip('"').strip("'").replace("\n","").replace("\r","")
            save_project_settings(root, agent.project_dir, api_key=new_key)
            agent.config["api_key"] = new_key
            agent.config["_root"] = root
            try:
                save_project_api_key(agent.project_dir, new_key)
            except Exception:
                pass
            try:
                agent.pool = build_pool(agent.config)
                UI.ok(f"API key saved for this project → {CONFIG_FILE}")
                UI.info(f"Providers: {', '.join(p.name for p in agent.pool.providers)}")
            except Exception as e:
                UI.err(f"Key saved but pool rebuild failed: {e}")
            continue
        if raw == "/new":
            # Clean session for THIS project only — keeps API key & model
            agent.ctx.clear()
            agent.goal = None
            agent.autopilot = False
            agent.sdlc_phase_idx = 0
            agent.sdlc_completed.clear()
            agent.autopilot_rounds = 0
            agent.round = 0
            agent.nudges = 0
            agent.meter.prompt = 0
            agent.meter.completion = 0
            agent._phase_rounds = 0
            agent._phase_tool_counts = {}
            agent._phase_bash_ok = False
            agent.current_turn_tool_calls = False
            TodoTool._todos.clear()
            TodoTool._counter = 0
            agent.config.pop("last_goal", None)
            agent.config.pop("last_sdlc_phase_idx", None)
            agent.config.pop("last_sdlc_completed", None)
            agent._rebuild_system()
            # Overwrite session file with empty state so next launch stays clean
            agent.persist(force=True)
            UI.ok("New session for this project. Goal/todos/history cleared. API key & model kept.")
            UI.info(f"Project: {agent.project_dir}")
            continue
        if raw == "/reset":
            agent.ctx.clear()
            agent.goal = None
            agent.autopilot = False
            agent.sdlc_phase_idx = 0
            agent.sdlc_completed.clear()
            agent.autopilot_rounds = 0
            agent.round = 0
            agent.nudges = 0
            agent.meter.prompt = 0
            agent.meter.completion = 0
            agent._phase_rounds = 0
            agent._phase_tool_counts = {}
            agent._phase_bash_ok = False
            TodoTool._todos.clear()
            TodoTool._counter = 0
            agent.config.pop("last_goal", None)
            agent.config.pop("last_sdlc_phase_idx", None)
            agent.config.pop("last_sdlc_completed", None)
            agent._rebuild_system()
            agent.persist(force=True)
            UI.ok("Full reset: goal, SDLC, todos, conversation wiped. Model/persona kept.")
            continue
        if raw.startswith("/"):
            UI.warn(f"Unknown command: {raw}. Try /new /apikey /exit /clear /reset /files /cost /compact /model /todo /goal /persona /autopilot /status /stop")
            continue

        try:
            agent.run_turn(raw)
        except KeyboardInterrupt:
            print("\n")
            UI.warn("Interrupted by user.")
            continue
        except Exception as e:
            UI.err(f"Error: {e}")
            continue

    ok = save_session(agent, also_config=True)
    UI.separator()
    if ok:
        UI.ok(f"Session saved → {_project_session_path(agent.project_dir)}")
    UI.ok(f"Total usage: {agent.meter.report()}")
    print("Goodbye.")


if __name__ == "__main__":
    main()
