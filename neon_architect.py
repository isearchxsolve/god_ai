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
APP_VERSION = "4.5.0"
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
        "thinking": False,
        "extra_body": None,
    },
    "glm-5.2-fp8": {
        "id": "z-ai/glm-5.2-fp8",
        "name": "GLM-5.2-FP8",
        "provider": "NVIDIA NIM",
        "rpm": 40,
        "max_tokens": 8192,
        "ctx_window": 131072,
        "thinking": False,
        "extra_body": None,
    },
    "nemotron-ultra": {
        "id": "nvidia/nemotron-3-ultra-550b-a55b",
        "name": "Nemotron 3 Ultra",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": False,
        "extra_body": None,
    },
    "nemotron-4-340b": {
        "id": "nvidia/nemotron-4-340b",
        "name": "Nemotron 4 340B",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": False,
        "extra_body": None,
    },
    "llama-3.1-405b": {
        "id": "nvidia/llama-3.1-405b-instruct",
        "name": "Llama 3.1 405B",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": False,
        "extra_body": None,
    },
    "nemotron-3-super-120b-a12b": {
        "id": "nvidia/nemotron-3-super-120b-a12b",
        "name": "Nemotron 3 Super 120B",
        "provider": "NVIDIA NIM",
        "rpm": 20,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": False,
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
    # 0 = unlimited. Turns driven by phase gates, not a fixed budget.
    "max_rounds": 0,
    "compact_threshold": 0.3,
    "auto_nudge": True,
    "max_nudges": 2,
    # --- Stream / HTTP sized for high-thinking quiet windows ---
    "stream_timeout": 420.0,
    "request_timeout": 420.0,
    "rpm_safety": 0.80,
    "show_thinking": False,
    "theme": "neon",
    "retry_max": 8,
    "retry_base_delay": 2.5,
    "enable_openrouter": True,
    "stream_content_timeout": 200.0,
    "first_token_timeout": 60.0,
    "http_read_timeout": 180.0,
    "http_connect_timeout": 15.0,
    "max_retries_per_provider": 3,
    "thinking_effort": "off",
    "inter_turn_delay": 0.35,
    # 0 = unlimited autopilot; stop on gates or /stop only.
    "max_autopilot_rounds": 0,
    # 0 = no force-advance on phase round count.
    "max_phase_rounds": 0,
    "startup_compact_tokens": 60000,
    "autopilot_thinking": False,
    "plan_artifact": "PLAN.md",
    "architecture_artifact": "ARCHITECTURE.md",
    "working_memory_file": ".neon_working_memory.md",
    "project_state_file": ".neon_project_state.json",
    "max_same_tool_failures": 3,
    "require_research_for_external": True,
    # DEFAULT: full tool power INSIDE the project only (paths never escape project_dir).
    "full_access": True,
    "allow_path_outside_project": False,
    "allow_local_network": True,
    "bash_confirm_destructive": False,
    "bash_timeout_max": 600,
    "implementation_path_prefixes": ["src/", "app/", "backend/", "frontend/", "lib/", "tests/"],
    "min_implementation_src_writes": 4,
    "session_restore_max_messages": 24,
    "session_restore_max_tokens": 80000,
    "tdd_enforce_red_green": True,
    "git_worktree_on_autopilot": True,
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
    "planning": (
        "Research the goal (web_search + browse_page if external product). "
        "Write PLAN.md with requirements, risks, phased tasks, acceptance criteria. Add todos. Do NOT implement yet."
    ),
    "architecture": (
        "Follow PLAN.md. Write ARCHITECTURE.md (components, interfaces, data flow, tech stack) and interface stubs only."
    ),
    "design": "Follow PLAN.md and ARCHITECTURE.md. Design UI/UX, components, styles, layouts.",
    "implementation": "Follow PLAN.md and ARCHITECTURE.md. Implement with TDD. Track todos.",
    "testing": "Test against PLAN.md acceptance criteria. Fix failures. No new features.",
    "review": "Review against PLAN.md and ARCHITECTURE.md for quality, security, consistency.",
    "deployment": "Create deployment artifacts aligned with ARCHITECTURE.md.",
    "verification": "Verify every PLAN.md acceptance criterion. Mark todos done only when criteria pass.",
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
# Gates only — no fixed turn budget, no force-advance on round count.
SDLC_PHASE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "planning": {
        "kind": "plan_complete",
        "artifact": "PLAN.md",
        "min_chars": 400,
        "min_todos": 5,
        "require_sections": ["Acceptance Criteria", "Requirements", "Risks"],
        "require_research": True,  # web_search or browse_page if goal looks external
    },
    "architecture": {
        "kind": "architecture_complete",
        "artifact": "ARCHITECTURE.md",
        "min_chars": 300,
        "any_tool": ["write", "edit"],
        "min_calls": 2,
        "require_sections": ["Components", "Data Flow"],
    },
    "design": {
        "kind": "tool_calls",
        "any_tool": ["write", "edit"],
        "min_calls": 3,
    },
    "implementation": {
        "kind": "implementation_complete",
        "any_tool": ["write", "edit"],
        "min_calls": 8,
        "min_src_writes": 4,  # under src/app/backend/frontend/lib/tests
    },
    "testing": {
        "kind": "bash_success",
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

# Plan schema markers (case-insensitive section headers expected in PLAN.md)
PLAN_REQUIRED_HEADERS = ("acceptance criteria", "requirements", "risks")
ARCH_REQUIRED_HEADERS = ("components", "data flow")

# Destructive bash patterns (require confirm unless bash_confirm_destructive=False)
DESTRUCTIVE_BASH_RE = re.compile(
    r"(?:^|[\s;|&])(rm\s+-[a-zA-Z]*[fr]|rm\s+--recursive|del\s+/[sf]|format\s+|"
    r"git\s+push\s+.*--force|git\s+reset\s+--hard|dd\s+if=|mkfs\.|shutdown|reboot)\b",
    re.I,
)


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


# Whimsical Claude Code thinking verbs (expanded set)
_CC_VERBS = [
    "Thinking", "Cooking", "Percolating", "Ruminating", "Cogitating",
    "Ideating", "Kneading", "Sautéing", "Pondering", "Brewing",
    "Noodling", "Whirring", "Mulling", "Spinning", "Crunching",
    "Synthesizing", "Harmonizing", "Channeling", "Orchestrating",
    "Conjuring", "Distilling", "Weaving", "Sculpting", "Composing",
]
_CC_SPINNER = ["·", "✢", "✳", "✶", "✻", "✽", "✻", "✶", "✳", "✢"]
_CC_THINK_IDX = 0


class UI:
    """Claude Code–style terminal UI: terracotta accent, hot-pink tools, dashed frames."""

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
            return f"● TURN {round_num:03d}  ·  {tokens:,} tok  {status}"
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
        """User prompt — Claude Code dashed ASCII frame with > prefix."""
        text = text or ""
        lines = text.splitlines() or [""]
        width = 72
        dash = "- " * (width // 2)
        dash = dash[:width].rstrip()
        if not HAS_RICH:
            out = [dash, f"|  > {lines[0]}"]
            for ln in lines[1:]:
                out.append(f"|    {ln}")
            out.append("|")
            out.append(dash)
            return "\n".join(out)
        body = Text()
        body.append(dash + "\n", style="cc_muted")
        body.append("|  ", style="cc_muted")
        body.append("> ", style="cc_prompt")
        body.append(UI.esc(lines[0]), style="cc_user")
        body.append("\n")
        for ln in lines[1:]:
            body.append("|    ", style="cc_muted")
            body.append(UI.esc(ln), style="cc_user")
            body.append("\n")
        body.append("|", style="cc_muted")
        body.append("\n" + dash, style="cc_muted")
        return body

    @staticmethod
    def assistant_stream() -> "Text":
        return Text("", style="cc_body") if HAS_RICH else Text("")  # type: ignore

    @staticmethod
    def thinking_block(text: str = "") -> "RenderableType":
        """Claude Code–style thinking: brief verb only (no reasoning dump)."""
        global _CC_THINK_IDX
        verb = _CC_VERBS[_CC_THINK_IDX % len(_CC_VERBS)]
        glyph = _CC_SPINNER[_CC_THINK_IDX % len(_CC_SPINNER)]
        _CC_THINK_IDX += 1
        if not HAS_RICH:
            return f"  {glyph} {verb}…"
        t = Text()
        t.append(f"  {glyph} ", style="cc_thinking")
        t.append(f"{verb}…", style="cc_thinking")
        return t

    @staticmethod
    def thinking_live(elapsed: float = 0.0) -> None:
        """In-place thinking spinner (Claude Code style) while waiting for tokens."""
        global _CC_THINK_IDX
        verb = _CC_VERBS[_CC_THINK_IDX % len(_CC_VERBS)]
        glyph = _CC_SPINNER[_CC_THINK_IDX % len(_CC_SPINNER)]
        _CC_THINK_IDX += 1
        msg = f"  {glyph} {verb}…"
        if elapsed >= 8:
            msg += f"  ({int(elapsed)}s)"
        if HAS_RICH:
            console.print(f"[cc_thinking]{msg}[/cc_thinking]", end="\r")
        else:
            print(msg, end="\r", flush=True)

    @staticmethod
    def clear_live_line() -> None:
        if HAS_RICH:
            console.print(" " * 60, end="\r")
        else:
            print(" " * 60, end="\r", flush=True)

    @staticmethod
    def tool_call(name: str, args_preview: str) -> "RenderableType":
        """Claude Code–style tool header: ⏺ + Title Case name + muted args."""
        label = {
            "read": "Read", "write": "Write", "edit": "Edit", "bash": "Bash",
            "search": "Search", "glob": "Glob", "ls": "List", "todo": "Todo",
            "web_search": "WebSearch", "browse_page": "Browse", "task": "Task",
            "modules": "Modules",
        }.get(name, str(name).replace("_", " ").title().replace(" ", ""))
        if not HAS_RICH:
            return f"  ⏺ {label}" + (f"  {args_preview}" if args_preview else "")
        t = Text()
        t.append("  ⏺ ", style="cc_tool")
        t.append(label, style="cc_tool")
        if args_preview:
            t.append("  ", style="cc_tool")
            ap = args_preview if len(args_preview) < 90 else args_preview[:87] + "…"
            t.append(UI.esc(ap), style="cc_muted")
        return t

    @staticmethod
    def tool_result(name: str, output: str, is_error: bool = False) -> "RenderableType":
        """Tool result body under hot-pink gutter — Claude Code │ / └─."""
        lines = (output or "").splitlines() or [""]
        max_show = 20
        if len(lines) > max_show:
            shown = lines[:max_show]
            shown.append(f"… [{len(lines) - max_show} more lines]")
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
            row.append(UI.esc(ln[:200]), style=style)
            parts.append(row)
        parts.append(Text("  └─", style=border))
        return Group(*parts) if parts else Text("")

    @staticmethod
    def permission_prompt(action: str, detail: str = "") -> "RenderableType":
        """Claude Code–style permission card (lavender)."""
        if not HAS_RICH:
            return f"\n  [Permission] {action}\n  {detail}\n  Allow? (y/n)\n"
        body = Text()
        body.append("  ╭─ Permission ─────────────────────────\n", style="cc_permission")
        body.append("  │ ", style="cc_permission")
        body.append(UI.esc(action), style="cc_fg")
        body.append("\n")
        if detail:
            body.append("  │ ", style="cc_permission")
            body.append(UI.esc(detail[:120]), style="cc_muted")
            body.append("\n")
        body.append("  │ Allow this action? [y/n]\n", style="cc_permission")
        body.append("  ╰──────────────────────────────────────", style="cc_permission")
        return body

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
        """Inline unified diff with Claude Code gutter colors."""
        if not HAS_RICH:
            return f"--- {path}\n+++ {path}\n"
        t = Text()
        t.append(f"  ⏺ Edit  ", style="cc_tool")
        t.append(UI.esc(path) + "\n", style="cc_muted")
        n = 0
        for line in difflib.unified_diff(
            (old or "").splitlines(), (new or "").splitlines(), lineterm="",
            n=3,
        ):
            if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
                t.append("  │ " + line + "\n", style="cc_subtle")
            elif line.startswith("+"):
                t.append("  │ " + line + "\n", style="cc_success")
                n += 1
            elif line.startswith("-"):
                t.append("  │ " + line + "\n", style="cc_error")
                n += 1
            else:
                t.append("  │ " + line + "\n", style="cc_muted")
            if n > 40:
                t.append("  │ …\n", style="cc_muted")
                break
        t.append("  └─", style="cc_tool")
        return t

    @staticmethod
    def ok(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  ✓ ", "cc_success"), (msg, "cc_body")))
        else:
            print(f"  ✓ {msg}")

    @staticmethod
    def warn(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  ⚠ ", "cc_warn"), (msg, "cc_body")))
        else:
            print(f"  ⚠ {msg}")

    @staticmethod
    def err(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  ✗ ", "cc_error"), (msg, "cc_fg")))
        else:
            print(f"  ✗ {msg}")

    @staticmethod
    def info(msg: str):
        if HAS_RICH:
            console.print(Text.assemble(("  · ", "cc_primary"), (msg, "cc_body")))
        else:
            print(f"  · {msg}")

    @staticmethod
    def separator(title: str = ""):
        if HAS_RICH:
            if title:
                console.print(Text(f"\n  ── {title} ──", style="cc_subtle"))
            else:
                console.print(Text("  " + "─" * 48, style="cc_subtle"))
        else:
            print(f"── {title} ──" if title else "─" * 40)

    @staticmethod
    def status_bar(model: str, tokens: int, phase: str = "") -> "RenderableType":
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
        """Startup — Claude Code minimal chrome."""
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
                    "thinking": False,
                    "extra_body": None,
                }
                providers.append(Provider(
                    name, or_base, or_key, fake_cfg,
                    connect_timeout, read_timeout, or_bucket,
                ))

    if not providers:
        raise RuntimeError(
            "No providers configured for this project. "
            "Set a NVIDIA NIM key:  (1) env NVIDIA_API_KEY=nvapi-...  "
            "(2) python neon_architect.py and /apikey nvapi-...  "
            "(3) or OPENROUTER_API_KEY for OpenRouter fallback. "
            f"project={config.get('project_dir')}"
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

    # Class-level flags set from config / full_access mode
    allow_outside_project: bool = False

    def _safe_path(self, path: str) -> Path:
        """Resolve path — ALWAYS confined to project directory (system permission = project only)."""
        raw = (path or "").strip()
        if not raw:
            raise ValueError("path is required (use project-relative paths, e.g. src/app.py)")
        if raw.startswith("\\\\?\\"):
            raw = raw[4:]
        candidate = Path(raw)
        target = candidate.resolve() if candidate.is_absolute() else (self.cwd / raw).resolve()
        # Hard sandbox: never allow escape, even if allow_outside_project was set.
        try:
            target.relative_to(self.cwd.resolve())
        except ValueError:
            raise PermissionError(
                f"Path '{path}' is outside the project folder ({self.cwd}). "
                f"All file access is limited to the project directory."
            )
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
    description = (
        "Create or overwrite a file (or append). path MUST be project-relative "
        "(e.g. src/app.py). Prefer SMALL files (<4000 chars per write). "
        "For long docs use multiple writes with append=true. Creates parent dirs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project-relative path"},
            "content": {"type": "string"},
            "append": {"type": "boolean", "default": False, "description": "Append instead of overwrite"},
        },
        "required": ["path", "content"],
    }
    WARN_CHARS = 12000

    def execute(self, path: str = "", content: str = None, append: bool = False) -> ToolResult:
        try:
            if not path or not str(path).strip():
                return ToolResult(
                    "",
                    error="path is required. Example: path='src/core/agents/pm.py'",
                    is_error=True,
                )
            if content is None:
                return ToolResult("", error="content is required", is_error=True)
            fp = self._safe_path(path)
            fp.parent.mkdir(parents=True, exist_ok=True)
            data = content if isinstance(content, str) else str(content)
            mode = "a" if append else "w"
            with open(fp, mode, encoding="utf-8", newline="\n") as f:
                f.write(data)
            with ReadTool._cache_lock:
                ReadTool._cache.pop(str(fp), None)
            size = fp.stat().st_size if fp.is_file() else 0
            notes = []
            if len(data) >= self.WARN_CHARS:
                notes.append(
                    f"WARN: payload {len(data)} chars is large — prefer smaller chunks + append=true "
                    "to avoid model/stream truncation."
                )
            # Heuristic: unfinished markdown fence or mid-token cut
            stripped = data.rstrip()
            if stripped.count("```") % 2 == 1:
                notes.append("WARN: odd number of ``` fences — content may be truncated; append the rest.")
            if any(stripped.endswith(x) for x in ("{", "(", "[", ",")) or stripped.endswith("className="):
                notes.append("WARN: content ends mid-syntax — likely truncated; continue with append=true.")
            msg = f"{'Appended' if append else 'Written'} {len(data)} chars ({size} bytes on disk) to {path}"
            if notes:
                msg += "\n" + "\n".join(notes)
            return ToolResult(msg)
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
                hint = ""
                sn = (old_text or "")[:40]
                if sn and sn in original:
                    hint = " (partial match exists — check whitespace)"
                return ToolResult("", error=f"old_text not found in {path}{hint}", is_error=True)
            if replace_all:
                count = original.count(old_text)
                new_content = original.replace(old_text, new_text)
            else:
                new_content = original.replace(old_text, new_text, 1)
                count = 1
            with open(fp, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_content)
            with ReadTool._cache_lock:
                ReadTool._cache.pop(str(fp), None)
            # Claude Code–style unified diff snippet in tool result
            diff_lines = list(difflib.unified_diff(
                old_text.splitlines(), new_text.splitlines(),
                fromfile=f"a/{path}", tofile=f"b/{path}", lineterm="",
            ))
            diff_txt = "\n".join(diff_lines[:80])
            if len(diff_lines) > 80:
                diff_txt += f"\n… [{len(diff_lines)-80} more diff lines]"
            msg = (
                f"Replaced {count} occurrence(s) in {path} ({len(new_content)} chars now)\n"
                f"--- diff ---\n{diff_txt}"
            )
            return ToolResult(msg)
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
    description = (
        "Execute a shell command in the project directory (tests, installs, builds). "
        "Prefer web_search/browse_page for internet research. "
        "Destructive commands (rm -rf, git reset --hard, force push) are blocked unless "
        "confirmed via confirm=true when bash_confirm_destructive is enabled."
    )
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer", "default": 120},
            "confirm": {"type": "boolean", "default": False, "description": "Required for destructive commands"},
        },
        "required": ["command"],
    }
    MAX_OUTPUT = 80000
    # Set by NeonArchitect after build_tools
    confirm_destructive: bool = True
    last_test_digest: str = ""

    def execute(self, command: str, timeout: int = 120, confirm: bool = False) -> ToolResult:
        try:
            cmd = (command or "").strip()
            if not cmd:
                return ToolResult("", error="command is required", is_error=True)
            if getattr(self, "confirm_destructive", True) and DESTRUCTIVE_BASH_RE.search(cmd) and not confirm:
                return ToolResult(
                    "",
                    error=(
                        "Destructive command blocked. Re-call bash with confirm=true if intentional: "
                        f"{cmd[:200]}"
                    ),
                    is_error=True,
                )
            timeout = max(5, min(int(timeout or 120), 600))
            result = subprocess.run(
                cmd, shell=True, cwd=str(self.cwd),
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=timeout,
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            if len(output) > self.MAX_OUTPUT:
                half = self.MAX_OUTPUT // 2
                output = output[:half] + f"\n\n… [truncated {len(output)} chars] …\n\n" + output[-half:]
            output += f"\n[exit code: {result.returncode}]"
            # Test failure digest for orchestrator injection
            low = cmd.lower()
            is_test = any(x in low for x in ("pytest", "unittest", "npm test", "npx jest", "cargo test", "go test"))
            if is_test:
                digest_lines = [ln for ln in output.splitlines() if ln.strip()][-40:]
                BashTool.last_test_digest = (
                    f"cmd: {cmd}\nexit: {result.returncode}\n" + "\n".join(digest_lines)
                )
            return ToolResult(output, is_error=result.returncode != 0)
        except subprocess.TimeoutExpired:
            return ToolResult("", error=f"Command timed out after {timeout}s", is_error=True)
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


class TaskTool(Tool):
    """Lightweight specialist worker: explores the codebase with tools (no nested LLM).

    Gathers files matching the prompt keywords via glob/search/read and returns a
    structured summary the parent agent can act on — closes the old stub gap.
    """
    name = "task"
    description = (
        "Delegate an independent exploration task. Searches and reads relevant files "
        "under the project, returns a structured summary (paths + excerpts). "
        "Use for 'find how X works', 'map module Y', etc. Does not write files."
    )
    parameters = {
        "type": "object",
        "properties": {
            "description": {"type": "string", "description": "Short task description"},
            "prompt": {"type": "string", "description": "Detailed instructions / keywords"},
        },
        "required": ["description", "prompt"],
    }

    def execute(self, description: str, prompt: str) -> ToolResult:
        try:
            text = f"{description or ''}\n{prompt or ''}"
            # Keyword tokens for search
            tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
            stop = {
                "the", "and", "for", "with", "that", "this", "from", "into", "about",
                "find", "how", "what", "where", "please", "should", "must", "task",
                "search", "read", "file", "files", "code", "project", "implement",
            }
            keys = []
            seen = set()
            for tok in tokens:
                low = tok.lower()
                if low in stop or low in seen:
                    continue
                seen.add(low)
                keys.append(tok)
                if len(keys) >= 8:
                    break
            if not keys:
                keys = ["main", "config", "agent"]

            findings: List[str] = []
            paths_hit: List[str] = []

            # 1) Glob likely source trees
            globber = GlobTool(self.cwd)
            for pattern in ("**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/package.json", "**/requirements.txt"):
                res = globber.execute(pattern=pattern, path=".")
                if not res.is_error and res.output:
                    for line in res.output.splitlines()[:40]:
                        line = line.strip()
                        if line and line not in paths_hit:
                            paths_hit.append(line)
                if len(paths_hit) > 80:
                    break

            # 2) Search for keywords
            searcher = SearchTool(self.cwd)
            match_files: Dict[str, int] = {}
            for k in keys[:5]:
                res = searcher.execute(pattern=re.escape(k), path=".")
                if res.is_error or not res.output:
                    continue
                for line in res.output.splitlines()[:30]:
                    # typical "path:line:content"
                    path = line.split(":", 1)[0].strip() if ":" in line else ""
                    if path and not path.startswith("["):
                        match_files[path] = match_files.get(path, 0) + 1

            ranked = sorted(match_files.items(), key=lambda x: -x[1])[:12]
            reader = ReadTool(self.cwd)
            excerpts = []
            for path, score in ranked:
                try:
                    r = reader.execute(path=path, offset=1, limit=40)
                    if not r.is_error:
                        body = (r.output or "")[:1200]
                        excerpts.append(f"### {path} (score={score})\n{body}")
                except Exception:
                    continue

            lines = [
                f"[Sub-agent complete] {description}",
                f"Keywords: {', '.join(keys)}",
                f"Indexed source candidates: {len(paths_hit)}",
                f"Keyword-matched files: {len(match_files)}",
                "",
                "## Top matches",
            ]
            for path, score in ranked[:10]:
                lines.append(f"- {path} (hits≈{score})")
            if excerpts:
                lines.append("")
                lines.append("## Excerpts")
                lines.extend(excerpts[:6])
            else:
                lines.append("")
                lines.append("No keyword hits. Sample paths:")
                for pth in paths_hit[:15]:
                    lines.append(f"- {pth}")
            return ToolResult("\n".join(lines))
        except Exception as e:
            return ToolResult("", error=f"task sub-agent failed: {e}", is_error=True)


class ModulesTool(Tool):
    """Lightweight module/package graph for Python projects."""
    name = "modules"
    description = (
        "List Python packages/modules under a path and who-imports-whom (shallow). "
        "Use before large refactors to extend existing modules instead of duplicating."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "src"},
            "max_files": {"type": "integer", "default": 80},
        },
        "required": [],
    }

    def execute(self, path: str = "src", max_files: int = 80) -> ToolResult:
        try:
            base = self._safe_path(path if path else ".")
            if not base.exists():
                # fallback to project root
                base = self.cwd
            py_files = []
            for fp in sorted(base.rglob("*.py")):
                if any(part.startswith(".") for part in fp.relative_to(self.cwd).parts):
                    continue
                py_files.append(fp)
                if len(py_files) >= max(10, min(int(max_files or 80), 200)):
                    break
            import_re = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M)
            lines = [f"Modules under {base.relative_to(self.cwd) if base != self.cwd else '.'} ({len(py_files)} files)", ""]
            for fp in py_files:
                rel = str(fp.relative_to(self.cwd)).replace("\\", "/")
                try:
                    text = fp.read_text(encoding="utf-8", errors="replace")[:8000]
                except Exception:
                    continue
                imps = []
                for m in import_re.finditer(text):
                    mod = m.group(1) or m.group(2)
                    if mod and mod not in imps:
                        imps.append(mod)
                    if len(imps) >= 12:
                        break
                imp_s = ", ".join(imps[:12]) if imps else "(no imports parsed)"
                lines.append(f"- {rel}")
                lines.append(f"    imports: {imp_s}")
            return ToolResult("\n".join(lines))
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)


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



def _strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        return "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
    except Exception:
        pass
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def urllib_quote(s: str) -> str:
    from urllib.parse import quote
    return quote(s, safe="")


def _http_get(url: str, timeout: float = 25.0, headers: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
    default_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; NeonArchitect/4.2) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        default_headers.update(headers)
    if HAS_HTTPX:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=default_headers) as client:
            r = client.get(url)
            return r.status_code, r.text, str(r.url)
    import urllib.request
    req = urllib.request.Request(url, headers=default_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return getattr(resp, "status", 200), raw.decode(charset, errors="replace"), resp.geturl()


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the public internet. Returns ranked titles, URLs, snippets. "
        "Use BEFORE guessing product domains. Follow with browse_page on best URLs. "
        "Supports site: operators."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "num_results": {"type": "integer", "default": 8},
        },
        "required": ["query"],
    }

    def execute(self, query: str, num_results: int = 8) -> ToolResult:
        try:
            q = (query or "").strip()
            if not q:
                return ToolResult("", error="query is required", is_error=True)
            n = max(1, min(int(num_results or 8), 15))
            results: List[Dict[str, str]] = []
            errors: List[str] = []
            brave_key = (os.environ.get("BRAVE_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip()
            if brave_key:
                try:
                    status, body, _ = _http_get(
                        f"https://api.search.brave.com/res/v1/web/search?q={urllib_quote(q)}&count={n}",
                        timeout=20.0,
                        headers={"Accept": "application/json", "X-Subscription-Token": brave_key},
                    )
                    if status == 200:
                        data = json.loads(body)
                        for item in (data.get("web") or {}).get("results") or []:
                            results.append({"title": item.get("title") or "", "url": item.get("url") or "",
                                            "snippet": item.get("description") or ""})
                    else:
                        errors.append(f"brave:{status}")
                except Exception as e:
                    errors.append(f"brave:{e}")
            if len(results) < n:
                try:
                    status, body, _ = _http_get(f"https://html.duckduckgo.com/html/?q={urllib_quote(q)}", timeout=25.0)
                    if status == 200:
                        results.extend(self._parse_ddg_html(body, n - len(results)))
                    else:
                        errors.append(f"ddg_html:{status}")
                except Exception as e:
                    errors.append(f"ddg_html:{e}")
            if len(results) < n:
                try:
                    status, body, _ = _http_get(f"https://lite.duckduckgo.com/lite/?q={urllib_quote(q)}", timeout=25.0)
                    if status == 200:
                        results.extend(self._parse_ddg_lite(body, n - len(results)))
                    else:
                        errors.append(f"ddg_lite:{status}")
                except Exception as e:
                    errors.append(f"ddg_lite:{e}")
            if len(results) < n:
                try:
                    status, body, _ = _http_get(
                        f"https://api.duckduckgo.com/?q={urllib_quote(q)}&format=json&no_html=1&skip_disambig=1",
                        timeout=15.0,
                    )
                    if status == 200:
                        data = json.loads(body)
                        if data.get("AbstractURL"):
                            results.append({"title": data.get("Heading") or q, "url": data.get("AbstractURL") or "",
                                            "snippet": data.get("AbstractText") or ""})
                        for topic in data.get("RelatedTopics") or []:
                            items = topic.get("Topics") if isinstance(topic, dict) and topic.get("Topics") else [topic]
                            for sub in items:
                                if isinstance(sub, dict) and sub.get("FirstURL"):
                                    results.append({
                                        "title": re.sub(r"<.*?>", "", sub.get("Text") or "")[:120],
                                        "url": sub.get("FirstURL") or "",
                                        "snippet": re.sub(r"<.*?>", "", sub.get("Text") or ""),
                                    })
                except Exception as e:
                    errors.append(f"ddg_api:{e}")
            seen, unique = set(), []
            for r in results:
                u = (r.get("url") or "").strip()
                if not u or u in seen:
                    continue
                seen.add(u)
                unique.append(r)
                if len(unique) >= n:
                    break
            if not unique:
                return ToolResult("", error=(
                    f"No results for {q!r}. Details: {'; '.join(errors) or 'unknown'}. "
                    "Try alternate spelling (oiioii.ai vs oioi.com) or browse_page on a known URL."
                ), is_error=True)
            lines = [f"Web search results for: {q}", f"Returned {len(unique)} result(s).", ""]
            for i, r in enumerate(unique, 1):
                lines.append(f"{i}. {r.get('title') or '(no title)'}")
                lines.append(f"   URL: {r.get('url')}")
                if r.get("snippet"):
                    lines.append(f"   {r['snippet'][:300]}")
                lines.append("")
            return ToolResult("\n".join(lines))
        except Exception as e:
            return ToolResult("", error=str(e), is_error=True)

    @staticmethod
    def _parse_ddg_html(html: str, limit: int) -> List[Dict[str, str]]:
        out = []
        for m in re.finditer(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?class="result__snippet"[^>]*>(.*?)</(?:a|td|div)',
            html, re.I | re.S,
        ):
            url = WebSearchTool._clean_ddg_url(m.group(1))
            title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", m.group(3)).strip()
            if url:
                out.append({"title": title, "url": url, "snippet": snippet})
            if len(out) >= limit:
                break
        if not out:
            for m in re.finditer(r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
                url = WebSearchTool._clean_ddg_url(m.group(1))
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if url:
                    out.append({"title": title, "url": url, "snippet": ""})
                if len(out) >= limit:
                    break
        return out

    @staticmethod
    def _parse_ddg_lite(html: str, limit: int) -> List[Dict[str, str]]:
        out = []
        for m in re.finditer(r' rel="nofollow" href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
            url, title = m.group(1).strip(), re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if "duckduckgo.com" in url:
                continue
            out.append({"title": title, "url": url, "snippet": ""})
            if len(out) >= limit:
                break
        return out

    @staticmethod
    def _clean_ddg_url(url: str) -> str:
        from urllib.parse import unquote, parse_qs, urlparse
        url = url.replace("&amp;", "&")
        if "uddg=" in url:
            try:
                qs = parse_qs(urlparse(url).query)
                if "uddg" in qs:
                    return unquote(qs["uddg"][0])
            except Exception:
                pass
        if url.startswith("//"):
            url = "https:" + url
        return url


class BrowsePageTool(Tool):
    name = "browse_page"
    description = (
        "Fetch a URL and return readable text (HTML stripped). "
        "Use after web_search for docs, product pages, API references."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "max_chars": {"type": "integer", "default": 12000},
            "start_line": {"type": "integer", "default": 1},
        },
        "required": ["url"],
    }

    def execute(self, url: str, max_chars: int = 12000, start_line: int = 1) -> ToolResult:
        try:
            u = (url or "").strip()
            if not u:
                return ToolResult("", error="url is required", is_error=True)
            if not re.match(r"^https?://", u, re.I):
                u = "https://" + u
            host = re.sub(r"^https?://", "", u, flags=re.I).split("/")[0].lower()
            allow_local = getattr(self, "allow_local_network", False)
            if not allow_local and (
                host in ("localhost", "127.0.0.1", "0.0.0.0") or host.endswith(".local")
            ):
                return ToolResult(
                    "",
                    error=f"Refusing local host: {host} (enable full_access / allow_local_network)",
                    is_error=True,
                )
            status, body, final_url = _http_get(u, timeout=30.0)
            if status >= 400:
                return ToolResult("", error=f"HTTP {status} fetching {final_url or u}", is_error=True)
            low = body[:2000].lower()
            text = _strip_html(body) if ("<html" in low or "<!doctype" in low or "<body" in low) else body
            lines = text.splitlines()
            start = max(0, int(start_line or 1) - 1)
            sliced = "\n".join(lines[start:])
            max_c = max(1000, min(int(max_chars or 12000), 50000))
            trunc = len(sliced) > max_c
            if trunc:
                sliced = sliced[:max_c] + f"\n\n… [truncated at {max_c} chars]"
            header = f"URL: {final_url}\nStatus: {status}\nLines: {len(lines)} (from {start+1})\nTruncated: {trunc}\n{'─'*40}\n"
            return ToolResult(header + sliced)
        except Exception as e:
            return ToolResult("", error=f"browse_page failed: {e}", is_error=True)


def build_tools(cwd: Path, full_access: bool = True, allow_outside: bool = False,
                allow_local: bool = True, bash_confirm: bool = False) -> Dict[str, Tool]:
    """Build tools. File I/O is always project-sandboxed; full_access = unrestricted bash in-project."""
    tool_list: List[Tool] = [
        ReadTool(cwd), WriteTool(cwd), EditTool(cwd),
        SearchTool(cwd), GlobTool(cwd), LsTool(cwd),
        BashTool(cwd), WebSearchTool(cwd), BrowsePageTool(cwd),
        TaskTool(cwd), ModulesTool(cwd), TodoTool(cwd),
    ]
    tools = {t.name: t for t in tool_list}
    # Paths: always project-only (ignore allow_outside for file tools)
    for t in tools.values():
        t.allow_outside_project = False
    local = bool(allow_local or full_access)
    if "browse_page" in tools:
        tools["browse_page"].allow_local_network = local
    if "bash" in tools:
        # full_access default: no destructive confirm; cwd remains project_dir
        tools["bash"].confirm_destructive = bool(bash_confirm) and not full_access
        tools["bash"].description = (
            "Execute a shell command with cwd=project directory. "
            "File tools cannot leave the project folder. "
            + (
                "Destructive commands allowed without confirm (in-project full permission)."
                if full_access and not bash_confirm
                else "Destructive commands require confirm=true."
            )
        )
    return tools


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
Your mission: research, plan, write, edit, test, and ship code using TDD — with minimal wasted turns.

CRITICAL RULES (anti-fumble):
1. ALWAYS use the native JSON function calling API for tools. Never output raw XML for tool calls.
2. If you need a tool, CALL IT in the same response. Do NOT say "Let me..." and stop.
3. ONE focused tool action per turn when exploring. Do not re-run the same failed command.
4. If a tool fails twice the same way, CHANGE STRATEGY (different tool, query, or path).
5. Prefer web_search + browse_page over bash curl for internet research.
6. Read before edit. Search before creating duplicate files.
7. Keep working memory accurate: facts you already know need not be rediscovered.
8. Phase completion is decided by the orchestrator via gates (PLAN.md, ARCHITECTURE.md, todos, tests) — do not claim a phase is done without producing those artifacts.
9. AUTOPILOT: NEVER ask the user questions, never wait for confirmation, never say "Shall I…?", "Ready?", "Would you like…?", "Proceed to implementation?". The orchestrator advances phases. CALL TOOLS only — no permission requests.
10. Paths: use project-relative paths only (e.g. src/app.py, PLAN.md). Never use /god_ai/... or other absolute Unix paths on Windows; cwd is already the project folder.

TDD: RED (failing test) → GREEN (minimum code) → REFACTOR. Run tests after changes.

PERSONA: Architect | Designer | Engineer | Tester | Debugger | Reviewer | DevOps — stay in the injected persona.

WORKING DIRECTORY: {project_dir}
CURRENT MODEL: {model_name}

Tools:
- read / write / edit — local files (edit returns a diff)
- search / glob / ls / modules — local discovery & import graph
- bash — tests, installs, builds (not for web search)
- web_search(query, num_results) — internet search
- browse_page(url, max_chars, start_line) — fetch page text
- todo — task tracker
- task — specialist explorer (search/read summary; does not write)

External products: web_search first; confirm real domain (e.g. oiioii.ai vs oioi.com) before cloning.
Autopilot: planning → architecture → design → implementation → testing → review → deployment → verification.
"""



# ── Durable project state (survives compaction / session restore) ─────────────

def _default_project_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "goal": None,
        "phase": "planning",
        "completed_phases": [],
        "autopilot_active": False,
        "autopilot_resume": False,
        "sdlc_phase_idx": 0,
        "stack": [],
        "entrypoints": [],
        "test_command": None,
        "key_modules": [],
        "last_failures": [],
        "open_todos": [],
        "decisions": [],
        "blockers": [],
        "next_action": None,
        "research_notes": [],
        "src_write_paths": [],
        "updated_at": None,
    }


def load_project_state(project_dir: Path, filename: str = ".neon_project_state.json") -> Dict[str, Any]:
    state = _default_project_state()
    fp = project_dir / filename
    try:
        if fp.is_file():
            data = json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                state.update({k: data[k] for k in state.keys() if k in data})
    except Exception:
        pass
    return state


def save_project_state(project_dir: Path, state: Dict[str, Any], filename: str = ".neon_project_state.json") -> None:
    try:
        state = dict(state)
        state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        fp = project_dir / filename
        fp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except Exception:
        pass


def plan_has_sections(text: str, headers: tuple) -> bool:
    """Flexible section detection — accepts common synonyms."""
    low = (text or "").lower()
    synonyms = {
        "acceptance criteria": (
            "acceptance criteria", "acceptance criterion", "success criteria",
            "definition of done", "acceptance:",
        ),
        "requirements": (
            "requirements", "requirement analysis", "functional requirements",
            "product requirements", "scope",
        ),
        "risks": (
            "risks", "risk assessment", "risk & mitigation", "risks &",
            "risk mitigation", "known risks",
        ),
        "components": (
            "components", "component architecture", "system components",
            "modules", "service layout",
        ),
        "data flow": (
            "data flow", "dataflow", "architecture flow", "request flow",
            "system flow", "pipeline",
        ),
    }
    for h in headers:
        key = h.lower().strip()
        opts = synonyms.get(key, (key,))
        if not any(o in low for o in opts):
            return False
    return True


def goal_looks_external(goal: str) -> bool:
    g = (goal or "").lower()
    if not g:
        return False
    if re.search(r"\bhttps?://", g):
        return True
    if re.search(r"\b[a-z0-9-]+\.(com|ai|io|dev|app|sh|net|org)\b", g):
        return True
    if any(w in g for w in ("clone of", "clone", "replica of", "like ", "similar to")):
        return True
    return False


class NeonArchitect:
    """The main agent. Cyberpunk interface, zero-bottleneck core."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.project_dir = Path(config.get("project_dir", ".")).resolve()
        self.model_key = config.get("default_model", "glm-5.2")
        self.model_cfg = MODELS.get(self.model_key, MODELS["glm-5.2"])

        self.pool = build_pool(config)
        self.full_access = bool(config.get("full_access", True))
        self.tools = build_tools(
            self.project_dir,
            full_access=self.full_access,
            allow_outside=False,  # hard policy: project folder only
            allow_local=bool(config.get("allow_local_network", True)),
            bash_confirm=bool(config.get("bash_confirm_destructive", False)),
        )
        self.config["allow_path_outside_project"] = False
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
        self._session_wants_resume = False
        self.sdlc_phase_idx = 0
        self.sdlc_completed: set[str] = set()
        self.autopilot_rounds = 0
        self.max_autopilot_rounds = int(config.get("max_autopilot_rounds", 0) or 0)
        self._phase_rounds = 0  # telemetry only — never force-advances
        self._max_phase_rounds = int(config.get("max_phase_rounds", 0) or 0)
        self._phase_tool_counts: Dict[str, int] = {}
        self._phase_bash_ok = False
        self.current_turn_tool_calls = False
        self._last_persist = 0.0
        self._persist_every = 3
        self.plan_artifact = str(config.get("plan_artifact") or "PLAN.md")
        self.architecture_artifact = str(config.get("architecture_artifact") or "ARCHITECTURE.md")
        self.working_memory_file = str(config.get("working_memory_file") or ".neon_working_memory.md")
        self.max_same_tool_failures = int(config.get("max_same_tool_failures", 3) or 3)
        # Recent tool fingerprint → failure count (anti-loop)
        self._tool_fail_counts: Dict[str, int] = {}
        self._recent_tool_keys: deque = deque(maxlen=24)
        self._strategy_hints: List[str] = []
        self.project_state_file = str(config.get("project_state_file") or ".neon_project_state.json")
        self.project_state: Dict[str, Any] = load_project_state(self.project_dir, self.project_state_file)
        self._src_write_paths: List[str] = list(self.project_state.get("src_write_paths") or [])
        self._last_test_digest: str = ""
        self._research_done: bool = bool(self.project_state.get("research_notes"))
        # TDD red→green tracking (mitigation)
        self._tdd_saw_red: bool = False
        self._tdd_saw_green: bool = False
        self._consecutive_no_tool_turns: int = 0
        if "bash" in self.tools:
            if self.full_access:
                self.tools["bash"].confirm_destructive = False
            else:
                self.tools["bash"].confirm_destructive = bool(config.get("bash_confirm_destructive", True))

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

        # Thinking policy: prefer config/defaults (medium) to reduce NIM first-token stalls.
        # Do not force "high" — that was causing 90s buffer timeouts.
        # Default OFF: NIM GLM with enable_thinking buffers full reasoning before first token
        effort = str(self.config.get("thinking_effort") or "off").lower()
        if effort in ("high", "medium"):
            # keep only low if user insists; medium/high stall too often on NIM
            effort = "off"
        if effort not in ("off", "low"):
            effort = "off"
        self.config["thinking_effort"] = effort
        self.config["show_thinking"] = bool(self.config.get("show_thinking", False))
        self.config["autopilot_thinking"] = False
        self.config["first_token_timeout"] = max(
            60.0, float(self.config.get("first_token_timeout") or 60.0)
        )

        UI.separator()
        UI.ok(f"Initialized in {self.project_dir}")
        UI.info(
            "Permissions: project-folder only for files | "
            f"full_in_project={self.full_access} | "
            f"bash_confirm={bool(self.tools.get('bash') and getattr(self.tools['bash'], 'confirm_destructive', False))} | "
            f"local_net={bool(config.get('allow_local_network', True))} | "
            f"worktree={bool(config.get('git_worktree_on_autopilot'))} | "
            f"tdd={bool(config.get('tdd_enforce_red_green'))}"
        )
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
        persona = PERSONAS.get(self.persona_key, PERSONAS["adaptive"])
        prompt += f"\n\n[CURRENT PERSONA: {persona['name']}]\n{persona['prompt']}"
        if self.goal:
            prompt += f"\n\n[CURRENT GOAL]\n{self.goal}\nFocus all actions on this goal."
        # Durable project state snapshot
        try:
            ps = self.project_state or {}
            snap = []
            if ps.get("test_command"):
                snap.append(f"test_command: {ps['test_command']}")
            if ps.get("entrypoints"):
                snap.append("entrypoints: " + ", ".join(ps["entrypoints"][:8]))
            if ps.get("key_modules"):
                snap.append("key_modules: " + ", ".join(ps["key_modules"][:12]))
            if ps.get("next_action"):
                snap.append(f"next_action: {ps['next_action']}")
            if ps.get("blockers"):
                snap.append("blockers: " + "; ".join(str(b) for b in ps["blockers"][-3:]))
            if snap:
                prompt += "\n\n[PROJECT STATE — durable]\n" + "\n".join(snap)
        except Exception:
            pass
        if self.autopilot and self.sdlc_phase_idx < len(SDLC_PHASES):
            phase = SDLC_PHASES[self.sdlc_phase_idx]
            phase_prompt = SDLC_PHASE_PROMPTS.get(phase, "")
            completed = ", ".join(self.sdlc_completed) if self.sdlc_completed else "none"
            prompt += (
                f"\n\n[SDLC PHASE: {phase.upper()}]\n{phase_prompt}\n"
                f"Completed: {completed}\n"
                "Turns are NOT limited by a fixed count. Produce required artifacts; orchestrator advances gates."
            )
            handoff = self._phase_handoff_block(phase)
            if handoff:
                prompt += f"\n\n{handoff}"
        wm = self._read_working_memory()
        if wm:
            prompt += f"\n\n[WORKING MEMORY — do not rediscover these facts]\n{wm}"
        if self._strategy_hints:
            prompt += "\n\n[STRATEGY CORRECTIONS — obey these]\n" + "\n".join(f"- {h}" for h in self._strategy_hints[-5:])
        if self._last_test_digest:
            prompt += f"\n\n[LAST TEST DIGEST — fix these failures]\n{self._last_test_digest[:3000]}"
        if self.ctx.compaction_summary:
            prompt += f"\n\n[COMPACTED HISTORY]\n{self.ctx.compaction_summary}"
        self.ctx.add_system(prompt)

    def _sync_project_state(self) -> None:
        """Write orchestrator facts into PROJECT_STATE and disk."""
        try:
            st = self.project_state
            st["goal"] = self.goal
            st["phase"] = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else "complete"
            st["completed_phases"] = sorted(self.sdlc_completed)
            st["sdlc_phase_idx"] = int(self.sdlc_phase_idx)
            st["autopilot_active"] = bool(self.autopilot)
            # Keep resume flag sticky until goal fully complete or user restarts
            if self.autopilot:
                st["autopilot_resume"] = True
            st["open_todos"] = [
                {"id": tid, **todo} for tid, todo in list(TodoTool._todos.items())[:40]
            ]
            st["src_write_paths"] = list(self._src_write_paths)[-40:]
            if self._last_test_digest:
                fails = list(st.get("last_failures") or [])
                fails.append(self._last_test_digest[:500])
                st["last_failures"] = fails[-10:]
            save_project_state(self.project_dir, st, self.project_state_file)
        except Exception:
            pass

    def _advance_sdlc(self) -> bool:
        """Advance to next SDLC phase. Returns True if there are more phases."""
        current = SDLC_PHASES[self.sdlc_phase_idx]
        self.sdlc_completed.add(current)
        self.sdlc_phase_idx += 1
        self._phase_rounds = 0
        self._phase_tool_counts = {}
        self._phase_bash_ok = False
        self._sync_project_state()
        self._update_working_memory(f"phase complete: {current} → next")
        if self.sdlc_phase_idx >= len(SDLC_PHASES):
            UI.ok("All SDLC phases complete — goal pipeline finished.")
            if self.autopilot:
                UI.ok("Autopilot stopping: full SDLC cycle done. Review output or /autopilot to continue.")
                self.autopilot = False
            try:
                self.project_state["autopilot_active"] = False
                self.project_state["autopilot_resume"] = False
                self._sync_project_state()
            except Exception:
                pass
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

    def _start_autopilot(self, restart: bool = False):
        """Enter god autopilot. Resumes saved phase unless restart=True."""
        if not self.goal:
            UI.err("No goal set. Use /goal <description> first.")
            return False
        self.autopilot = True
        try:
            self.project_state["autopilot_active"] = True
            self.project_state["autopilot_resume"] = True
            self._sync_project_state()
        except Exception:
            pass
        if restart or self.sdlc_phase_idx >= len(SDLC_PHASES):
            self.sdlc_phase_idx = 0
            self.sdlc_completed.clear()
            self.autopilot_rounds = 0
            self.round = 0
            self._phase_tool_counts = {}
            self._phase_bash_ok = False
            if hasattr(self, "_tool_fail_counts"):
                self._tool_fail_counts = {}
            if hasattr(self, "_strategy_hints"):
                self._strategy_hints = []
            UI.info("Autopilot starting from PLANNING (fresh cycle).")
        else:
            UI.info(
                f"Autopilot resuming at {SDLC_PHASES[self.sdlc_phase_idx].upper()} "
                f"(completed: {', '.join(sorted(self.sdlc_completed)) or 'none'}). "
                "Use /autopilot restart for a full restart."
            )
        self._phase_rounds = 0
        phase = SDLC_PHASES[min(self.sdlc_phase_idx, len(SDLC_PHASES) - 1)]
        initial_persona = SDLC_PERSONA_MAP.get(phase, "adaptive")
        self._switch_persona(initial_persona, reason="auto")
        self._rebuild_system()
        UI.separator("GOD AUTOPILOT ENGAGED")
        UI.ok(f"Goal: {self.goal}")
        UI.info(f"Current SDLC phase: {phase.upper()}")
        UI.info("SDLC: planning → architecture → design → implementation → testing → review → deployment → verification")
        UI.info(
            f"Gates: {getattr(self, 'plan_artifact', 'PLAN.md')} + todos; "
            f"{getattr(self, 'architecture_artifact', 'ARCHITECTURE.md')} + stubs. "
            "No fixed turn force-advance."
        )
        UI.info("Type /stop to halt, /status for progress")
        return True

    def _stop_autopilot(self):
        """Halt autopilot mode."""
        if not self.autopilot:
            UI.info("Autopilot is not active.")
            return
        self.autopilot = False
        phase = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else "COMPLETE"
        try:
            self.project_state["autopilot_active"] = False
            # Still offer resume next launch if goal not finished
            self.project_state["autopilot_resume"] = self.sdlc_phase_idx < len(SDLC_PHASES) and bool(self.goal)
            self._sync_project_state()
        except Exception:
            pass
        UI.separator("AUTOPILOT HALTED")
        UI.info(f"Stopped at phase: {phase.upper()}")
        UI.info(f"Completed: {', '.join(self.sdlc_completed) if self.sdlc_completed else 'none'}")
        UI.info("Type /autopilot to resume from current phase (also offered on next launch).")
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

    def _read_artifact_snippet(self, relative_path: str, max_chars: int = 3500) -> str:
        try:
            fp = (self.project_dir / relative_path).resolve()
            fp.relative_to(self.project_dir.resolve())
            if not fp.is_file():
                return ""
            text = fp.read_text(encoding="utf-8", errors="replace").strip()
            return text if len(text) <= max_chars else text[:max_chars] + f"\n… [{len(text)} chars total]"
        except Exception:
            return ""

    def _todo_handoff_text(self) -> str:
        if not TodoTool._todos:
            return "(no todos yet)"
        return "\n".join(
            f"- [{t.get('status','pending')}] {tid}: {t.get('content','')}"
            for tid, t in TodoTool._todos.items()
        )

    def _phase_handoff_block(self, phase: str) -> str:
        parts: List[str] = []
        plan_name = getattr(self, "plan_artifact", "PLAN.md")
        arch_name = getattr(self, "architecture_artifact", "ARCHITECTURE.md")
        if phase != "planning":
            plan = self._read_artifact_snippet(plan_name)
            parts.append(f"[PLAN — follow]\nSource: {plan_name}\n{plan}" if plan else f"[PLAN MISSING] {plan_name}")
        if phase not in ("planning", "architecture"):
            arch = self._read_artifact_snippet(arch_name)
            parts.append(f"[ARCHITECTURE — follow]\nSource: {arch_name}\n{arch}" if arch else f"[ARCHITECTURE MISSING] {arch_name}")
        parts.append(f"[TODOS]\n{self._todo_handoff_text()}")
        return "\n\n".join(parts)

    def _working_memory_path(self) -> Path:
        return self.project_dir / getattr(self, "working_memory_file", ".neon_working_memory.md")

    def _read_working_memory(self) -> str:
        try:
            fp = self._working_memory_path()
            if fp.is_file():
                return fp.read_text(encoding="utf-8", errors="replace").strip()[:4000]
        except Exception:
            pass
        return ""

    def _update_working_memory(self, note: str, section: str = "Facts") -> None:
        """Structured durable memory: Facts / Decisions / Blockers / Next action."""
        try:
            fp = self._working_memory_path()
            prev = self._read_working_memory()
            sections = {"Facts": [], "Decisions": [], "Blockers": [], "Next action": []}
            cur = "Facts"
            if prev:
                for ln in prev.splitlines():
                    s = ln.strip()
                    if s.startswith("## "):
                        title = s[3:].strip()
                        if title in sections:
                            cur = title
                        continue
                    if s.startswith("#"):
                        continue
                    if s:
                        sections.setdefault(cur, []).append(s)
            stamp = datetime.now().strftime("%H:%M:%S")
            entry = f"- [{stamp}] {note.strip()[:300]}"
            sec = section if section in sections else "Facts"
            sections[sec].append(entry)
            # Cap each section
            for k in list(sections.keys()):
                sections[k] = sections[k][-15:]
            body_lines = ["# Neon working memory (auto)", ""]
            for title in ("Facts", "Decisions", "Blockers", "Next action"):
                body_lines.append(f"## {title}")
                body_lines.extend(sections.get(title) or ["- (none)"])
                body_lines.append("")
            fp.write_text("\n".join(body_lines), encoding="utf-8")
            with ReadTool._cache_lock:
                ReadTool._cache.pop(str(fp.resolve()), None)
            # Mirror into project_state
            if section == "Decisions":
                self.project_state.setdefault("decisions", []).append(note[:200])
                self.project_state["decisions"] = self.project_state["decisions"][-20:]
            elif section == "Blockers":
                self.project_state.setdefault("blockers", []).append(note[:200])
                self.project_state["blockers"] = self.project_state["blockers"][-10:]
            elif section == "Next action":
                self.project_state["next_action"] = note[:300]
        except Exception:
            pass

    def _tool_fingerprint(self, name: str, args: Dict[str, Any]) -> str:
        key_args = {}
        for k in ("path", "command", "query", "url", "pattern", "action", "id"):
            if k in args and args[k] is not None:
                key_args[k] = str(args[k])[:200]
        return f"{name}:{json.dumps(key_args, sort_keys=True, ensure_ascii=False)}"

    def _autopilot_prompt(self) -> str:
        if self.sdlc_phase_idx >= len(SDLC_PHASES):
            return "SDLC complete. Verify PLAN.md acceptance criteria and summarize deliverables."
        phase = SDLC_PHASES[self.sdlc_phase_idx]
        plan_name = getattr(self, "plan_artifact", "PLAN.md")
        arch_name = getattr(self, "architecture_artifact", "ARCHITECTURE.md")
        prompts = {
            "planning": (
                f"AUTOPILOT PLANNING — do NOT ask the user anything. "
                f"(1) web_search external product + browse_page top URLs. "
                f"(2) Write {plan_name} that MUST contain headings: Requirements, Risks, Acceptance Criteria "
                f"(exact words help the gate). (3) todo add ≥5. Do NOT implement app code. "
                f"If {plan_name} already exists and is complete, do NOT summarize for the user — "
                f"call a tool to fix any missing section headers, or wait for orchestrator advance. "
                f"Call a tool NOW."
            ),
            "architecture": (
                f"AUTOPILOT ARCHITECTURE — do NOT ask the user. Follow {plan_name}. "
                f"Write {arch_name} with headings Components and Data Flow + interface stubs (≥2 write/edit). "
                f"No full features. Call a tool NOW."
            ),
            "design": f"DESIGN following {plan_name}/{arch_name}. ≥3 write/edit. Call a tool NOW.",
            "implementation": (
                f"IMPLEMENT following {plan_name}/{arch_name} with TDD (RED→GREEN). "
                f"Write REAL application source under src/, backend/, frontend/, tests/ — "
                f"NOT more DESIGN.md/SPEC.md essays. "
                f"Each write MUST be SMALL (<4000 chars). Use append=true only to continue the SAME file. "
                f"Never dump an entire design system in one write. "
                f"≥8 write/edit with ≥4 under src/app/backend/frontend/lib/tests. "
                f"If providers time out, write an even smaller next file. Call a tool NOW."
            ),
            "testing": (
                f"TEST against {plan_name}. Run the project test command to exit 0. "
                f"If failures appear, fix code (GREEN) — do not skip. Call a tool NOW."
            ),
            "review": f"REVIEW vs {plan_name}/{arch_name}. ≥3 read/edit/search. Call a tool NOW.",
            "deployment": f"DEPLOY aligned with {arch_name}. Dockerfile/compose/CI. Call a tool NOW.",
            "verification": f"VERIFY all {plan_name} criteria. Tests must exit 0. Call a tool NOW.",
        }
        body = prompts.get(phase, "Continue the goal. Call a tool NOW.")
        handoff = self._phase_handoff_block(phase)
        hints = ""
        if self._strategy_hints:
            hints = "\n\n[STRATEGY — do not repeat failed approaches]\n" + "\n".join(
                f"- {h}" for h in self._strategy_hints[-4:]
            )
        return f"{body}\n\n{handoff}{hints}"

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
        try:
            self._sync_project_state()
        except Exception:
            pass
        if save_session(self, also_config=True):
            self._last_persist = now

    def _build_payload(self) -> Dict[str, Any]:
        # Autopilot: force a tool when the model has been talking without acting
        force_tool = bool(
            self.autopilot
            and (self._consecutive_no_tool_turns >= 1 or self._phase_rounds >= 1)
        )
        payload = {
            "model": self.pool.current().model_id,
            "messages": self.ctx.export(),
            "temperature": self.config.get("temperature", 0.2),
            "max_tokens": self.model_cfg.get("max_tokens", 8192),
            "stream": True,
            "tools": tools_schema(self.tools),
            "tool_choice": "required" if force_tool else "auto",
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

                # Claude Code–style thinking spinner while waiting for first token
                if not saw_any_token and elapsed >= 1.5 and int(elapsed) - last_heartbeat >= 1:
                    last_heartbeat = int(elapsed)
                    try:
                        UI.thinking_live(elapsed)
                    except Exception:
                        pass
                elif saw_any_token and elapsed > 20 and int(elapsed) - last_heartbeat >= 15:
                    last_heartbeat = int(elapsed)
                    msg = f"  · streaming... ({elapsed:.0f}s)"
                    if HAS_RICH:
                        console.print(f"  [cc_muted]{msg}[/cc_muted]", end="\r")
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
                    try:
                        UI.clear_live_line()
                    except Exception:
                        pass
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
        if effort == "low":
            # only explicit low keeps thinking; medium/high forced off above
            extra = dict(payload.get("extra_body") or {})
            ctk = dict(extra.get("chat_template_kwargs") or {})
            ctk["enable_thinking"] = True
            ctk["thinking_effort"] = "low"
            extra["chat_template_kwargs"] = ctk
            payload["extra_body"] = extra
        else:
            # Explicitly DISABLE thinking — critical for NIM first-token latency
            extra = dict(payload.get("extra_body") or {})
            ctk = dict(extra.get("chat_template_kwargs") or {})
            ctk["enable_thinking"] = False
            extra["chat_template_kwargs"] = ctk
            payload["extra_body"] = extra

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

            # Anti-loop: identical failing fingerprints
            fp_key = self._tool_fingerprint(name, args)
            prior_fails = self._tool_fail_counts.get(fp_key, 0)
            if prior_fails >= self.max_same_tool_failures:
                msg = (
                    f"[BLOCKED REPEAT] {name} with the same arguments already failed "
                    f"{prior_fails} times. Change strategy: different path, query, URL, or tool."
                )
                UI.warn(msg)
                self._strategy_hints.append(msg)
                result = ToolResult("", error=msg, is_error=True)
            else:
                result = execute_tool(self.tools, name, args)
                if result.is_error:
                    self._tool_fail_counts[fp_key] = prior_fails + 1
                    if self._tool_fail_counts[fp_key] >= 2:
                        hint = (
                            f"Tool {name} failed {self._tool_fail_counts[fp_key]}x with same args. "
                            f"Do NOT retry identically — change approach."
                        )
                        self._strategy_hints.append(hint)
                        UI.warn(hint)
                else:
                    self._tool_fail_counts[fp_key] = 0
                    if name == "web_search":
                        self._research_done = True
                        q = str(args.get("query", ""))[:120]
                        self._update_working_memory(f"web_search: {q}")
                        self.project_state.setdefault("research_notes", []).append(f"search:{q}")
                    elif name == "browse_page":
                        self._research_done = True
                        u = str(args.get("url", ""))[:160]
                        self._update_working_memory(f"browsed: {u}")
                        self.project_state.setdefault("research_notes", []).append(f"browse:{u}")
                    elif name in ("write", "edit"):
                        rel = str(args.get("path") or "").replace("\\", "/").lstrip("./")
                        self._update_working_memory(f"{name}: {rel}")
                        prefixes = self.config.get("implementation_path_prefixes") or [
                            "src/", "app/", "backend/", "frontend/", "lib/", "tests/"
                        ]
                        low = rel.lower()
                        if any(low.startswith(p.lower()) or f"/{p.lower()}" in f"/{low}" for p in prefixes):
                            if rel not in self._src_write_paths:
                                self._src_write_paths.append(rel)
                            self._phase_tool_counts["src_write"] = self._phase_tool_counts.get("src_write", 0) + 1
                    elif name == "todo" and args.get("action") == "add":
                        self._update_working_memory(f"todo: {str(args.get('content',''))[:120]}", section="Next action")
                    elif name == "bash":
                        digest = getattr(BashTool, "last_test_digest", "") or ""
                        if digest:
                            self._last_test_digest = digest
                            if result.is_error:
                                self._update_working_memory("test failure — see LAST TEST DIGEST", section="Blockers")
                            else:
                                cmd = str(args.get("command") or "")[:120]
                                self.project_state["test_command"] = cmd
                                self._update_working_memory(f"tests ok: {cmd}", section="Decisions")

            self._recent_tool_keys.append(fp_key)
            out_preview = result.text()[:800] if not result.is_error else result.text()[:500]
            UI.tool_result(name, out_preview, result.is_error)

            self.current_turn_tool_calls = True
            self._phase_tool_counts[name] = self._phase_tool_counts.get(name, 0) + 1
            if name == "todo" and args.get("action") == "add" and not result.is_error:
                self._phase_tool_counts["todo_add"] = self._phase_tool_counts.get("todo_add", 0) + 1
            if name == "bash":
                cmd = str(args.get("command") or "").lower()
                is_test = any(
                    x in cmd
                    for x in (
                        "pytest", "python -m pytest", "python -m unittest", "unittest",
                        "npm test", "npx jest", "cargo test", "go test",
                        "test_core.py", "test_agents.py",
                    )
                )
                if is_test and result.is_error:
                    self._tdd_saw_red = True
                    if BashTool.last_test_digest:
                        self._last_test_digest = BashTool.last_test_digest
                if is_test and not result.is_error:
                    self._phase_bash_ok = True
                    if self._tdd_saw_red:
                        self._tdd_saw_green = True
                        self._update_working_memory("TDD green after red", section="Decisions")

            ctx_tokens = self.ctx.estimate_tokens()
            max_tool_len = max(2000, (self.model_cfg["ctx_window"] - ctx_tokens) * 4)
            self.ctx.add_tool_result(tc["id"], name, result.text()[:max_tool_len])

        self._sync_project_state()
        return True

    def _asks_user(self, content: str) -> bool:
        """True if the model is prompting the human (forbidden in autopilot)."""
        lower = (content or "").lower()
        markers = [
            "shall i", "should i", "would you like", "do you want me",
            "ready to proceed", "may i proceed", "can i proceed",
            "let me know", "please confirm", "awaiting your",
            "your approval", "want me to continue", "shall we",
            "ready for the next", "proceed to the next phase",
            "move to the next phase", "ok to continue",
            "start phase", "begin phase", "shall i start",
            "ready for **", "gate satisfied. ready",
            "proceeding to **implementation**?",
        ]
        if any(m in lower for m in markers):
            return True
        # Trailing question aimed at user
        if "?" in content and any(
            w in lower for w in ("you", "shall", "should", "ready", "proceed", "continue")
        ):
            return True
        return False

    def _should_nudge(self, content: str) -> bool:
        """Detect announce-without-tool or forbidden user prompts."""
        if not self.config.get("auto_nudge", True):
            return False
        if self.nudges >= self.config.get("max_nudges", 2):
            return False
        if self.autopilot and self._asks_user(content):
            return True
        if len(content) > 800 and not self.autopilot:
            return False
        lower = content.lower()
        phrases = [
            "let me", "i will", "i'll", "i need to", "i'm going to",
            "allow me to", "i should", "first, i", "next, i",
            "i can", "i shall", "i intend to", "i am going to",
            "going to search", "going to read", "going to check",
            "will now", "now i will", "planning phase is complete",
            "ready to proceed", "gate requirements are satisfied",
        ]
        return any(p in lower for p in phrases)

    def _gate_missing_hint(self) -> str:
        """Tell the model exactly why the current phase gate is not met."""
        if not self.autopilot or self.sdlc_phase_idx >= len(SDLC_PHASES):
            return ""
        phase = SDLC_PHASES[self.sdlc_phase_idx]
        reqs = SDLC_PHASE_REQUIREMENTS.get(phase) or {}
        kind = reqs.get("kind")
        bits = [f"Phase={phase}. Gate NOT met. Do NOT ask the user."]
        if kind == "plan_complete":
            art = reqs.get("artifact") or "PLAN.md"
            ok, n = self._artifact_ok(art, int(reqs.get("min_chars", 400)))
            bits.append(f"{art}: {'ok' if ok else 'MISSING/short'} ({n} chars)")
            bits.append(f"todos_added={self._phase_tool_counts.get('todo_add', 0)} need ≥{reqs.get('min_todos', 5)}")
            text = self._read_artifact_snippet(art, max_chars=20000)
            headers = tuple(h.lower() for h in (reqs.get("require_sections") or PLAN_REQUIRED_HEADERS))
            for h in headers:
                bits.append(f"section '{h}': {'ok' if plan_has_sections(text, (h,)) else 'MISSING — edit PLAN.md to add heading'}")
            research = (
                self._research_done
                or self._phase_tool_counts.get("web_search", 0) > 0
                or self._phase_tool_counts.get("browse_page", 0) > 0
            )
            bits.append(f"research: {'ok' if research else 'need web_search/browse_page'}")
        elif kind == "architecture_complete":
            art = reqs.get("artifact") or "ARCHITECTURE.md"
            ok, n = self._artifact_ok(art, int(reqs.get("min_chars", 300)))
            bits.append(f"{art}: {'ok' if ok else 'MISSING'} ({n} chars)")
            bits.append(f"write/edit={sum(self._phase_tool_counts.get(x,0) for x in ('write','edit'))}")
        else:
            bits.append(f"counts={dict(self._phase_tool_counts)}")
        bits.append("Call ONE tool now to fix the missing gate item.")
        return " | ".join(bits)

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

        _max_rounds = int(self.config.get("max_rounds", 0) or 0)
        _max_ap = int(self.config.get("max_autopilot_rounds", self.max_autopilot_rounds) or 0)
        while True:
            if not self.autopilot and _max_rounds > 0 and self.round >= _max_rounds:
                UI.warn(f"Interactive max_rounds ({_max_rounds}) reached. Stopping.")
                break
            if self.autopilot and _max_ap > 0 and self.autopilot_rounds >= _max_ap:
                UI.warn(
                    f"Autopilot advisory limit ({_max_ap}) reached — stopping without force-advancing. "
                    "Raise max_autopilot_rounds or /autopilot to resume."
                )
                self._stop_autopilot()
                break

            self.round += 1
            self.current_turn_tool_calls = False
            if self.autopilot:
                self.autopilot_rounds += 1

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
                    if self.autopilot:
                        self.ctx.add_user(
                            "SYSTEM: Provider stalled. Do NOT rewrite huge DESIGN.md/SPEC.md. "
                            "Call write on ONE small source file (<200 lines) under src/ or backend/ or frontend/. "
                            "path required. No questions."
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
                self._consecutive_no_tool_turns = 0
                # Persist immediately if todos or files changed
                tool_names = {tc.get("name", "") for tc in tool_calls}
                if tool_names & {"todo", "write", "edit"}:
                    self.persist(force=True)
                delay = float(self.config.get("inter_turn_delay", 0.1))
                time.sleep(max(0.1, delay))
                if self.autopilot:
                    self._phase_rounds += 1
                    phase_name = SDLC_PHASES[min(self.sdlc_phase_idx, len(SDLC_PHASES) - 1)]
                    if self._phase_requirements_met():
                        if not self._advance_sdlc():
                            UI.separator("GOAL ACHIEVED")
                            UI.ok("All SDLC phases complete!")
                            self._stop_autopilot()
                            break
                    elif self._phase_rounds % 5 == 0:
                        hint = self._gate_missing_hint()
                        UI.info(
                            f"Still in {phase_name.upper()} (turn {self._phase_rounds}). "
                            f"{hint}"
                        )
                        # Push explicit fix instruction so model does not idle
                        self.ctx.add_user(
                            "AUTOPILOT: Gate still open. " + hint + " Call ONE tool now. Do not ask the user."
                        )
                    continue
                continue

            # No tools — assistant response
            self._consecutive_no_tool_turns += 1
            self.ctx.add_assistant(content)

            # Autopilot: if gates already met, advance immediately (never wait on "Shall I…?")
            if self.autopilot and (
                self._phase_requirements_met() or self._should_advance_phase(content)
            ):
                if not self._advance_sdlc():
                    UI.separator("GOAL ACHIEVED")
                    UI.ok("All SDLC phases complete!")
                    self._stop_autopilot()
                    break
                self.ctx.add_user(self._autopilot_prompt())
                self.nudges = 0
                time.sleep(max(0.1, float(self.config.get("inter_turn_delay", 0.1))))
                continue

            # Forbidden: asking the human during autopilot
            if self.autopilot and self._asks_user(content):
                UI.warn("Autopilot blocked a user-facing question — forcing tool action.")
                hint = self._gate_missing_hint()
                self.ctx.add_user(
                    "SYSTEM OVERRIDE (AUTOPILOT): Do NOT ask the user. Do NOT wait for confirmation. "
                    "Never say Shall I / Ready / Would you like. "
                    f"{hint} "
                    "Call exactly ONE tool now."
                )
                self.nudges = 0
                time.sleep(0.3)
                continue

            # Auto-nudge if assistant announced but didn't act
            if self._should_nudge(content):
                self.nudges += 1
                if self.nudges >= self.config.get("max_nudges", 2) and self.autopilot:
                    UI.warn("Nudge cap — hard tool command.")
                    hint = self._gate_missing_hint()
                    self.ctx.add_user(
                        "SYSTEM OVERRIDE: Do not explain. Do not ask the user. "
                        f"Call exactly ONE tool now. {hint}"
                    )
                    self.nudges = 0
                else:
                    UI.warn("Paused without tool — nudging.")
                    msg = "Call the tool you need NOW. No preamble. One tool call only."
                    if self.autopilot:
                        msg += " " + self._gate_missing_hint()
                    self.ctx.add_user(msg)
                time.sleep(0.5)
                continue

            self.nudges = 0

            # Autopilot: inject next action (gates not met yet)
            if self.autopilot:
                self.ctx.add_user(self._autopilot_prompt() + "\n" + self._gate_missing_hint())
                delay = float(self.config.get("inter_turn_delay", 0.1))
                time.sleep(max(0.1, delay))
                continue

            break

    def _artifact_ok(self, relative_path: str, min_chars: int = 200):
        try:
            fp = (self.project_dir / relative_path).resolve()
            fp.relative_to(self.project_dir.resolve())
            if not fp.is_file():
                return False, 0
            try:
                n = len(fp.read_text(encoding="utf-8", errors="replace").strip())
            except Exception:
                n = fp.stat().st_size
            return n >= min_chars, n
        except Exception:
            return False, 0

    def _artifact_ok(self, relative_path: str, min_chars: int = 200):
        try:
            fp = (self.project_dir / relative_path).resolve()
            fp.relative_to(self.project_dir.resolve())
            if not fp.is_file():
                return False, 0
            try:
                n = len(fp.read_text(encoding="utf-8", errors="replace").strip())
            except Exception:
                n = fp.stat().st_size
            return n >= min_chars, n
        except Exception:
            return False, 0

    def _phase_requirements_met(self) -> bool:
        """Primary gate: durable artifacts, schema sections, research, src writes, tests."""
        if not self.autopilot or self.sdlc_phase_idx >= len(SDLC_PHASES):
            return False
        phase = SDLC_PHASES[self.sdlc_phase_idx]
        reqs = SDLC_PHASE_REQUIREMENTS.get(phase)
        if not reqs:
            return False
        kind = reqs.get("kind")
        if kind == "plan_complete":
            artifact = reqs.get("artifact") or getattr(self, "plan_artifact", "PLAN.md")
            ok, n = self._artifact_ok(artifact, int(reqs.get("min_chars", 400)))
            added = self._phase_tool_counts.get("todo_add", 0)
            # Also accept todos already on the board (session / prior turns)
            board = len(TodoTool._todos) if TodoTool._todos else 0
            todo_ok = added >= int(reqs.get("min_todos", 5)) or board >= int(reqs.get("min_todos", 5))
            plan_text = self._read_artifact_snippet(artifact, max_chars=50000)
            headers = tuple(h.lower() for h in (reqs.get("require_sections") or PLAN_REQUIRED_HEADERS))
            sections_ok = plan_has_sections(plan_text, headers) if plan_text else False
            # Long substantive plan (>= 1500 chars) soft-passes missing exact headers
            if ok and n >= 1500 and not sections_ok:
                sections_ok = True
                UI.info(f"Plan gate: soft-pass sections ({artifact} {n} chars is substantive)")
            research_ok = True
            if reqs.get("require_research") and self.config.get("require_research_for_external", True):
                if goal_looks_external(self.goal or ""):
                    research_ok = (
                        self._research_done
                        or self._phase_tool_counts.get("web_search", 0) > 0
                        or self._phase_tool_counts.get("browse_page", 0) > 0
                        or bool(self.project_state.get("research_notes"))
                    )
            met = ok and todo_ok and sections_ok and research_ok
            if met:
                UI.info(
                    f"Gate met: {artifact} ({n}c) + todos={max(added, board)} "
                    f"+ sections + research → {phase.upper()}"
                )
            return met
        if kind == "architecture_complete":
            artifact = reqs.get("artifact") or getattr(self, "architecture_artifact", "ARCHITECTURE.md")
            ok, n = self._artifact_ok(artifact, int(reqs.get("min_chars", 300)))
            total = sum(self._phase_tool_counts.get(x, 0) for x in reqs.get("any_tool", ["write", "edit"]))
            # Count any write of ARCHITECTURE.md even if logged under other phase counters
            if ok and n >= 300:
                total = max(total, 1)
            arch_text = self._read_artifact_snippet(artifact, max_chars=50000)
            headers = tuple(h.lower() for h in (reqs.get("require_sections") or ARCH_REQUIRED_HEADERS))
            sections_ok = plan_has_sections(arch_text, headers) if arch_text else False
            if ok and n >= 1500 and not sections_ok:
                sections_ok = True
                UI.info(f"Architecture gate: soft-pass sections ({n} chars)")
            met = ok and total >= int(reqs.get("min_calls", 2)) and sections_ok
            # If file is large enough, don't block forever on min_calls from this phase only
            if ok and n >= 1500 and sections_ok:
                met = True
            if met:
                UI.info(f"Gate met: {artifact} ({n}c) + writes={total} + sections → {phase.upper()}")
            return met
        if kind == "implementation_complete":
            total = sum(self._phase_tool_counts.get(x, 0) for x in reqs.get("any_tool", ["write", "edit"]))
            src_n = self._phase_tool_counts.get("src_write", 0)
            min_src = int(reqs.get("min_src_writes", self.config.get("min_implementation_src_writes", 4)))
            met = total >= int(reqs.get("min_calls", 8)) and src_n >= min_src
            if met:
                UI.info(f"Gate met: write/edit={total}, src_writes={src_n} → {phase.upper()}")
            return met
        if kind == "todo_count":
            added = self._phase_tool_counts.get("todo_add", 0)
            met = added >= reqs.get("min_todos", 3)
            if met:
                UI.info(f"Gate met: {added} todos → {phase.upper()}")
            return met
        if kind == "tool_calls":
            total = sum(self._phase_tool_counts.get(x, 0) for x in reqs.get("any_tool", []))
            met = total >= reqs.get("min_calls", 1)
            if met:
                UI.info(f"Gate met: {total} tool calls → {phase.upper()}")
            return met
        if kind == "bash_success":
            if not self._phase_bash_ok:
                return False
            # Optional RED→GREEN: prefer seeing a failure then a pass in testing/verification
            if self.config.get("tdd_enforce_red_green") and phase in ("testing", "verification"):
                if self._tdd_saw_red and not self._tdd_saw_green:
                    UI.info("TDD: saw RED but not GREEN yet — keep fixing until tests pass after a failure.")
                    return False
                # If never saw red, still allow advance on green (legacy suites already passing)
            UI.info(f"Gate met: test exit 0 → {phase.upper()}")
            return True
        return False

    def _should_advance_phase(self, content: str) -> bool:
        """Secondary prose signal only. NEVER force-advances on turn count."""
        if not self.autopilot:
            return False
        phase = SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else ""
        self._phase_rounds += 1
        if phase in ("planning", "architecture", "implementation", "testing", "verification"):
            return False
        lower = (content or "").lower()
        signals = {
            "design": ["design complete", "ui designed", "design is complete"],
            "review": ["review complete", "review is complete", "code review done"],
            "deployment": ["deployment ready", "deployment complete", "dockerfile created"],
        }
        for signal in signals.get(phase, []):
            if signal in lower and self._phase_requirements_met():
                UI.info(f"Signal+gate: '{signal}' → {phase.upper()}")
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
        # Fold critical facts into working memory before shrinking chat
        self._update_working_memory(
            f"compact at phase={SDLC_PHASES[self.sdlc_phase_idx] if self.sdlc_phase_idx < len(SDLC_PHASES) else 'done'}; "
            f"goal={(self.goal or '')[:120]}",
            section="Facts",
        )
        self._sync_project_state()
        if self.ctx.compact(keep_recent=8):
            after = self.ctx.estimate_tokens()
            UI.ok(f"Compacted: ~{before:,} → ~{after:,} tokens (state + working memory preserved)")
            self._rebuild_system()
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


    def offer_resume_autopilot(self) -> bool:
        """If prior session left incomplete autopilot/goal, ask user to resume.

        Returns True if autopilot was started.
        """
        if self.autopilot:
            return False
        if not self.goal:
            return False
        if self.sdlc_phase_idx >= len(SDLC_PHASES):
            return False
        wants = bool(getattr(self, "_session_wants_resume", False))
        try:
            wants = wants or bool(self.project_state.get("autopilot_resume"))
            wants = wants or bool(self.project_state.get("autopilot_active"))
        except Exception:
            pass
        # Also offer if we have a goal + any completed phase or progress
        if not wants and not self.sdlc_completed and self.sdlc_phase_idx == 0:
            return False
        phase = SDLC_PHASES[self.sdlc_phase_idx]
        UI.separator("RESUME AUTOPILOT?")
        UI.info(f"Goal: {self.goal}")
        UI.info(f"Last phase: {phase.upper()} | completed: {', '.join(sorted(self.sdlc_completed)) or 'none'}")
        UI.info("Press Enter or y to resume autopilot from this phase.")
        UI.info("Type n to stay in interactive mode (goal kept).")
        try:
            ans = input("  Resume autopilot? [Y/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            ans = "n"
        if ans in ("", "y", "yes"):
            return bool(self._start_autopilot(restart=False))
        UI.info("Staying interactive. /autopilot when ready, /autopilot restart for a full restart.")
        try:
            self.project_state["autopilot_active"] = False
            # keep resume flag so next launch can ask again unless user clears goal
            self._sync_project_state()
        except Exception:
            pass
        return False

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

    def cmd_autopilot(self, restart: bool = False):
        """Start or resume god autopilot. restart=True forces PLANNING from scratch."""
        if self.autopilot:
            UI.info("Autopilot is already running.")
            self._autopilot_status()
            return
        if not self.goal:
            UI.err("No goal set. Use /goal <description> first.")
            return
        if self.config.get("git_worktree_on_autopilot"):
            self.cmd_worktree(auto=True)
        self._start_autopilot(restart=restart)
        self.run_turn(self._autopilot_prompt())

    def cmd_permission(self, mode: str = "status") -> None:
        """Permission modes. File access is ALWAYS project-folder only.

        full     — default: unrestricted bash in project, local net, no destructive confirm
        strict   — bash destructive commands require confirm=true
        local    — enable localhost browse
        nolo     — disable localhost browse
        status   — show flags
        """
        mode = (mode or "status").strip().lower()
        if mode in ("status", "show", ""):
            UI.separator("PERMISSIONS")
            UI.info("File access: PROJECT FOLDER ONLY (hard limit)")
            UI.info(f"full_access (in-project) = {self.full_access}")
            UI.info(f"allow_local_network = {bool(self.config.get('allow_local_network'))}")
            bash = self.tools.get("bash")
            UI.info(f"bash_confirm_destructive = {getattr(bash, 'confirm_destructive', False)}")
            UI.info(f"git_worktree_on_autopilot = {bool(self.config.get('git_worktree_on_autopilot'))}")
            UI.info(f"tdd_enforce_red_green = {bool(self.config.get('tdd_enforce_red_green'))}")
            UI.info("Commands: /permission full | strict | local | nolo | status")
            return
        if mode in ("full", "default"):
            self.full_access = True
            self.config["full_access"] = True
            self.config["allow_path_outside_project"] = False
            self.config["allow_local_network"] = True
            self.config["bash_confirm_destructive"] = False
            self.tools = build_tools(
                self.project_dir, full_access=True, allow_outside=False,
                allow_local=True, bash_confirm=False,
            )
            UI.ok("Full in-project permission (default). Files stay inside project folder.")
            return
        if mode in ("strict", "sandbox", "safe"):
            self.full_access = False
            self.config["full_access"] = False
            self.config["bash_confirm_destructive"] = True
            self.tools = build_tools(
                self.project_dir, full_access=False, allow_outside=False,
                allow_local=bool(self.config.get("allow_local_network", True)),
                bash_confirm=True,
            )
            UI.ok("Strict mode: destructive bash requires confirm=true. Files still project-only.")
            return
        if mode == "local":
            self.config["allow_local_network"] = True
            if "browse_page" in self.tools:
                self.tools["browse_page"].allow_local_network = True
            UI.ok("Local network browse allowed.")
            return
        if mode in ("nolo", "nolocal"):
            self.config["allow_local_network"] = False
            if "browse_page" in self.tools:
                self.tools["browse_page"].allow_local_network = False
            UI.ok("Local network browse disabled.")
            return
        if mode == "outside":
            UI.warn(
                "Outside-project file access is disabled by policy. "
                "All file tools are limited to the project folder."
            )
            return
        UI.err(f"Unknown permission mode: {mode}. Use full | strict | local | nolo | status")

    def cmd_worktree(self, auto: bool = False) -> None:
        """Create a git worktree branch for isolated autopilot work (mitigates messy main)."""
        branch = f"neon/{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        path = self.project_dir / ".neon_worktrees" / branch.replace("/", "_")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            # Ensure git repo
            chk = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(self.project_dir), capture_output=True, text=True, timeout=15,
            )
            if chk.returncode != 0:
                if auto:
                    UI.info("Not a git repo — skipping worktree.")
                    return
                UI.err("Not a git repository. Run git init first, or ignore worktree.")
                return
            r = subprocess.run(
                ["git", "worktree", "add", "-b", branch, str(path)],
                cwd=str(self.project_dir), capture_output=True, text=True, timeout=60,
            )
            if r.returncode != 0:
                UI.warn(f"worktree failed: {(r.stderr or r.stdout or '')[:300]}")
                return
            UI.ok(f"Git worktree ready: {path} (branch {branch})")
            UI.info("Point future work there manually or re-launch with -p to that path.")
            self._update_working_memory(f"worktree: {path} branch={branch}", section="Decisions")
            self.project_state["worktree"] = {"path": str(path), "branch": branch}
            self._sync_project_state()
        except Exception as e:
            UI.warn(f"worktree error: {e}")


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
        "stream_content_timeout": 200.0,
        "first_token_timeout": 60.0,
        "http_read_timeout": 180.0,
        "http_connect_timeout": 15.0,
        "retry_max": 8,
        "retry_base_delay": 2.5,
        "max_retries_per_provider": 3,
        "inter_turn_delay": 0.35,
        "compact_threshold": 0.3,
        "startup_compact_tokens": 60000,
        "max_rounds": 0,
        "max_autopilot_rounds": 0,
        "max_phase_rounds": 0,
        "rpm_safety": 0.80,
        # medium (not high) — high causes long NIM first-token buffers / stalls
        "thinking_effort": "off",
        "show_thinking": False,
        "autopilot_thinking": False,
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
    # Thinking: honor DEFAULT_CONFIG / project entry (do not force high — causes NIM stalls)
    effort = str(runtime.get("thinking_effort") or DEFAULT_CONFIG.get("thinking_effort") or "off").lower()
    if effort in ("high", "medium"):
        effort = "off"
    if effort not in ("off", "low"):
        effort = "off"
    runtime["thinking_effort"] = effort
    runtime["show_thinking"] = False
    runtime["autopilot_thinking"] = False
    runtime["first_token_timeout"] = max(90.0, float(runtime.get("first_token_timeout") or DEFAULT_CONFIG.get("first_token_timeout") or 120.0))
    runtime["stream_content_timeout"] = max(150.0, float(runtime.get("stream_content_timeout") or DEFAULT_CONFIG.get("stream_content_timeout") or 200.0))
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
    """First-time setup: ask for NVIDIA API key once per project, then reuse.

    Priority:
      1. Already saved projects[<path>].api_key
      2. Legacy .key.json for this path
      3. Env NVIDIA_API_KEY / NGC_API_KEY / NIM_API_KEY (saved for this project)
      4. Interactive prompt (first time) → saved under this project
    """
    project = Path(project_dir or cfg.get("project_dir") or ".").resolve()
    root = cfg.get("_root") if isinstance(cfg.get("_root"), dict) else None
    if not isinstance(root, dict) or "projects" not in root:
        try:
            root = load_config()
        except Exception:
            root = {"projects": {}}
        cfg["_root"] = root
    root.setdefault("projects", {})
    entry = get_project_entry(root, project)

    def _save(key: str) -> None:
        key = key.strip().strip('"').strip("'")
        entry["api_key"] = key
        cfg["api_key"] = key
        try:
            save_config(root)
        except Exception:
            pass
        try:
            save_project_api_key(project, key)
        except Exception:
            pass

    key = (entry.get("api_key") or "").strip()
    if not key:
        key = (load_project_api_key(project) or "").strip()
        if key:
            _save(key)
            return True

    if not key:
        key = (
            os.environ.get("NVIDIA_API_KEY")
            or os.environ.get("NGC_API_KEY")
            or os.environ.get("NIM_API_KEY")
            or ""
        ).strip()
        if key:
            _save(key)
            UI.info("API key taken from environment and saved for this project.")
            return True

    if key:
        cfg["api_key"] = key
        return True

    # First time for this project — ask once
    print()
    print("=" * 56)
    print("  NEON ARCHITECT — first-time setup")
    print("=" * 56)
    print(f"  Project: {project}")
    print(f"  Config:  {CONFIG_FILE}")
    print()
    print("  No API key saved for this folder yet.")
    print("  Get a free/paid key: https://build.nvidia.com")
    print("  Paste your NVIDIA NIM key below (starts with nvapi-).")
    print("  It will be remembered for this project only.")
    print("=" * 56)
    try:
        key = input("  NVIDIA API Key: ").strip().strip('"').strip("'")
    except (EOFError, KeyboardInterrupt):
        print()
        key = ""
    if not key:
        UI.err("API key is required to start. Run again and paste your nvapi- key.")
        return False
    _save(key)
    UI.ok("API key saved. Starting agent…")
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
            "autopilot": bool(agent.autopilot),
            "autopilot_resume": bool(
                agent.autopilot
                or (agent.goal and agent.sdlc_phase_idx < len(SDLC_PHASES))
            ),
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
    agent.autopilot = False  # never auto-start; prompt via offer_resume_autopilot
    agent._session_wants_resume = bool(
        data.get("autopilot") or data.get("autopilot_resume")
    )
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
    parser.add_argument("--full-access", action="store_true",
                        help="Unrestricted mode: any path, any bash (no destructive confirm), local network browse")
    parser.add_argument("--allow-outside", action="store_true",
                        help="Allow file tools to touch paths outside the project directory")
    parser.add_argument("--allow-local-net", action="store_true",
                        help="Allow browse_page to localhost / .local hosts")
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
    # Defaults already: full in-project access, paths locked to project.
    if args.full_access:
        cfg["full_access"] = True
        cfg["allow_path_outside_project"] = False  # never leave project folder
        cfg["allow_local_network"] = True
        cfg["bash_confirm_destructive"] = False
    if args.allow_outside:
        # Policy: outside paths are not granted even if flag is passed
        UI.warn("--allow-outside ignored: file access is limited to the project folder only.")
        cfg["allow_path_outside_project"] = False
    if args.allow_local_net:
        cfg["allow_local_network"] = True

    if not ensure_api_key(cfg, project_dir=project):
        sys.exit(1)
    # refresh key into runtime after ensure (always from root project entry)
    cfg["api_key"] = (get_project_entry(root_cfg, project).get("api_key") or cfg.get("api_key") or "").strip()
    if not cfg["api_key"]:
        UI.err("No API key after ensure_api_key — set NVIDIA_API_KEY or use /apikey after fixing config.")
        sys.exit(1)

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

    # Offer to resume autopilot from last session (goal + phase persisted)
    if not cfg.get("_fresh"):
        try:
            if agent.offer_resume_autopilot():
                try:
                    agent.run_turn(agent._autopilot_prompt())
                except KeyboardInterrupt:
                    print()
                    UI.warn("Interrupted — autopilot still active; empty Enter or /stop.")
                except Exception as e:
                    UI.err(f"Resume turn error: {e}")
        except Exception as e:
            UI.warn(f"Resume prompt skipped: {e}")

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
    UI.info("Commands: /new /apikey /files /cost /clear /reset /compact /model /todo /goal /persona /autopilot /status /stop /permission /worktree /exit")
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
        if raw == "/autopilot" or raw.startswith("/autopilot "):
            agent.cmd_autopilot(restart="restart" in raw.lower())
            continue
        if raw == "/status":
            agent._autopilot_status()
            continue
        if raw == "/stop":
            agent._stop_autopilot()
            continue
        if raw == "/permission" or raw.startswith("/permission "):
            arg = raw.split(None, 1)[1] if " " in raw else "status"
            agent.cmd_permission(arg)
            continue
        if raw == "/worktree":
            agent.cmd_worktree(auto=False)
            continue
        if raw == "/full-access" or raw == "/fullaccess":
            agent.cmd_permission("full")
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
            try:
                self.project_state["autopilot_active"] = False
                self.project_state["autopilot_resume"] = False
                self._session_wants_resume = False
                self._sync_project_state()
            except Exception:
                pass
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
