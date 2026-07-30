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
from collections import deque
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

# ── Windows console fix ───────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: CONSTANTS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "NEON ARCHITECT"
APP_VERSION = "4.0.0"
APP_TAGLINE = "GLM-5.2 · NVIDIA NIM · Zero Bottlenecks · Self-Healing"

CONFIG_DIR = Path.home() / ".neon_architect"
CONFIG_FILE = CONFIG_DIR / "config.json"
SESSIONS_DIR = CONFIG_DIR / "sessions"
HISTORY_FILE = CONFIG_DIR / "history.jsonl"

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# ── Model Registry ────────────────────────────────────────────────────────────
MODELS: Dict[str, Dict[str, Any]] = {
    "glm-5.2": {
        "id": "z-ai/glm-5.2",
        "name": "GLM-5.2",
        "provider": "NVIDIA NIM",
        "rpm": 40,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True, "thinking_effort": "medium"}},
    },
    "glm-5.2-fp8": {
        "id": "z-ai/glm-5.2-fp8",
        "name": "GLM-5.2-FP8",
        "provider": "NVIDIA NIM",
        "rpm": 40,
        "max_tokens": 32768,
        "ctx_window": 131072,
        "thinking": True,
        "extra_body": {"chat_template_kwargs": {"enable_thinking": True, "thinking_effort": "medium"}},
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
}

DEFAULT_CONFIG = {
    "version": APP_VERSION,
    "api_key": "",
    "default_model": "glm-5.2",
    "base_url": NIM_BASE_URL,
    "project_dir": str(Path.cwd()),
    "temperature": 0.2,
    "max_rounds": 100,
    "compact_threshold": 0.10,
    "auto_nudge": True,
    "max_nudges": 3,
    "stream_timeout": 30.0,
    "request_timeout": 180.0,
    "rpm_safety": 0.80,
    "show_thinking": True,
    "theme": "neon",
    "retry_max": 20,
    "retry_base_delay": 3.0,
    "enable_openrouter": True,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: CYBERPUNK THEME & UI SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_RICH:
    THEME = Theme({
        "neon_cyan": "bold bright_cyan",
        "neon_magenta": "bold bright_magenta",
        "neon_green": "bold bright_green",
        "neon_yellow": "bold bright_yellow",
        "neon_red": "bold bright_red",
        "neon_blue": "bold bright_blue",
        "neon_white": "bold bright_white",
        "dim_cyan": "dim cyan",
        "dim_magenta": "dim magenta",
        "dim_green": "dim green",
        "dim_yellow": "dim yellow",
        "dim_red": "dim red",
        "dim_white": "dim white",
        "dark_bg": "on black",
        "panel_border": "bright_black",
        "user": "bold bright_cyan",
        "assistant": "bright_white",
        "thinking": "italic bright_magenta",
        "tool_name": "bold bright_yellow",
        "tool_args": "dim bright_yellow",
        "tool_result": "bright_black",
        "file_path": "bold bright_cyan",
        "code": "bright_white on black",
        "border": "bright_black",
        "header": "bold bright_cyan on black",
        "status_ok": "bright_green",
        "status_warn": "bright_yellow",
        "status_err": "bright_red",
        "prompt": "bold bright_cyan",
        "round": "bold bright_magenta",
        "token_count": "dim bright_black",
        "neon_prompt": "bold bright_cyan",
        "neon_accent": "bold bright_magenta",
        "neon_dim": "dim bright_black",
        "neon_success": "bold bright_green",
        "neon_warning": "bold bright_yellow",
        "neon_error": "bold bright_red",
        "neon_info": "bold bright_blue",
    })
    console = Console(theme=THEME, highlight=False, soft_wrap=True, color_system="truecolor")
else:
    console = None


class UI:
    """Cyberpunk-inspired neon UI primitives."""

    @staticmethod
    def esc(text: str) -> str:
        return text.replace("[", "\\[").replace("]", "\\]") if HAS_RICH else text

    @staticmethod
    def header(model_name: str, project: str) -> RenderableType:
        if not HAS_RICH:
            return f"{APP_NAME} v{APP_VERSION} | {model_name} | {project}"
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="center")
        grid.add_column(justify="right")
        grid.add_row(
            Text.from_markup(f"[neon_cyan]◆ {APP_NAME}[/neon_cyan] [neon_dim]v{APP_VERSION}[/neon_dim]"),
            Text.from_markup(f"[neon_magenta]{model_name}[/neon_magenta]"),
            Text.from_markup(f"[neon_dim]{UI.esc(project)}[/neon_dim]"),
        )
        return Panel(grid, box=HEAVY_EDGE, border_style="neon_cyan", padding=(0, 1))

    @staticmethod
    def turn_indicator(round_num: int, tokens: int, status: str = "") -> RenderableType:
        if not HAS_RICH:
            return f"═══ TURN {round_num} | ~{tokens} tokens {status} ═══"
        left = Text.from_markup(f"[neon_magenta]▶ TURN {round_num:03d}[/neon_magenta]")
        right = Text.from_markup(f"[neon_dim]◈ {tokens:,} tok[/neon_dim]")
        if status:
            right.append(f"  ◈  {status}", style="neon_dim")
        grid = Table.grid(expand=True)
        grid.add_column(justify="left")
        grid.add_column(justify="right")
        grid.add_row(left, right)
        return Panel(grid, box=MINIMAL, border_style="neon_magenta", padding=(0, 1))

    @staticmethod
    def user_message(text: str) -> RenderableType:
        if not HAS_RICH:
            return f">>> {text}"
        return Text.from_markup(f"[neon_cyan]▸[/neon_cyan] [user]{UI.esc(text)}[/user]")

    @staticmethod
    def assistant_stream() -> Text:
        return Text("", style="assistant")

    @staticmethod
    def thinking_block(text: str) -> RenderableType:
        if not HAS_RICH:
            return f"◈ THINKING ◈ {text[:200]}..."
        return Text.from_markup(f"[thinking]◈ {UI.esc(text)}[/thinking]")

    @staticmethod
    def tool_call(name: str, args_preview: str) -> RenderableType:
        if not HAS_RICH:
            return f"◈ {name}({args_preview})"
        return Text.from_markup(
            f"[neon_yellow]◈ {name}[/neon_yellow] [tool_args]({UI.esc(args_preview)})[/tool_args]"
        )

    @staticmethod
    def tool_result(name: str, output: str, is_error: bool = False) -> RenderableType:
        lines = output.splitlines()
        if len(lines) > 20:
            shown = "\n".join(lines[:20])
            shown += f"\n\n... [{len(lines) - 20} more lines; full output sent to agent] ..."
        else:
            shown = "\n".join(lines)
        style = "neon_error" if is_error else "neon_dim"
        if not HAS_RICH:
            prefix = "✗" if is_error else "│"
            return "\n".join(f"  {prefix} {ln}" for ln in shown.split("\n"))
        body = Text.from_markup("\n".join(f"  [neon_dim]│[/neon_dim] {UI.esc(ln)}" for ln in shown.split("\n")))
        return body

    @staticmethod
    def file_tree(root: Path, cwd: Path) -> RenderableType:
        if not HAS_RICH:
            lines = []
            for p in sorted(root.rglob("*")):
                if any(part.startswith(".") for part in p.relative_to(root).parts):
                    continue
                depth = len(p.relative_to(root).parts) - 1
                icon = "📁" if p.is_dir() else "📄"
                lines.append("  " * depth + f"{icon} {p.name}")
            return "\n".join(lines[:50])

        tree = Tree(f"[neon_cyan]{UI.esc(str(root))}[/neon_cyan]")
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if p.is_dir() and any((p / child).is_file() for child in p.iterdir()):
                continue
            parts = list(rel.parts)
            node = tree
            for part in parts[:-1]:
                found = None
                for child in node.children:
                    if hasattr(child, "label") and part in str(child.label):
                        found = child
                        break
                if found is None:
                    found = node.add(f"[neon_dim]{part}/[/neon_dim]")
                node = found
            if p.is_dir():
                node.add(f"[neon_dim]{parts[-1]}/[/neon_dim]")
            else:
                node.add(f"[neon_cyan]{parts[-1]}[/neon_cyan]")
        return tree

    @staticmethod
    def file_diff(path: str, old: str, new: str) -> RenderableType:
        diff = list(difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        ))
        diff_text = "".join(diff)
        if not HAS_RICH:
            return diff_text[:800]
        return Syntax(diff_text, "diff", theme="monokai", line_numbers=True)

    @staticmethod
    def ok(msg: str):
        if HAS_RICH:
            console.print(f"  [neon_success]◈[/neon_success] {UI.esc(msg)}")
        else:
            print(f"  ◈ {msg}")

    @staticmethod
    def warn(msg: str):
        if HAS_RICH:
            console.print(f"  [neon_warning]◈[/neon_warning] {UI.esc(msg)}")
        else:
            print(f"  ◈ {msg}")

    @staticmethod
    def err(msg: str):
        if HAS_RICH:
            console.print(f"  [neon_error]◈[/neon_error] {UI.esc(msg)}")
        else:
            print(f"  ◈ {msg}")

    @staticmethod
    def info(msg: str):
        if HAS_RICH:
            console.print(f"  [neon_info]◈[/neon_info] {UI.esc(msg)}")
        else:
            print(f"  ◈ {msg}")

    @staticmethod
    def separator(title: str = ""):
        if HAS_RICH:
            console.print(Rule(title, style="neon_magenta", characters="═"))
        else:
            print(f"{'═' * 60}")

    @staticmethod
    def status_bar(left: str, right: str = ""):
        if HAS_RICH:
            grid = Table.grid(expand=True)
            grid.add_column(justify="left")
            grid.add_column(justify="right")
            grid.add_row(Text.from_markup(left), Text.from_markup(right))
            console.print(Panel(grid, box=MINIMAL, border_style="neon_cyan", padding=(0, 1)))
        else:
            print(f"[{left}] {right}")

    @staticmethod
    def neon_banner():
        if not HAS_RICH:
            print(f"{APP_NAME} v{APP_VERSION}")
            return
        banner_text = """
╔══════════════════════════════════════════════════════════════════╗
║  ███╗   ██╗███████╗ ██████╗ ███╗   ██╗                         ║
║  ████╗  ██║██╔════╝██╔═══██╗████╗  ██║                         ║
║  ██╔██╗ ██║█████╗  ██║   ██║██╔██╗ ██║    ▀▄▀▄▀▄ ARCHITECT ▄▀▄▀▄▀║
║  ██║╚██╗██║██╔══╝  ██║   ██║██║╚██╗██║                         ║
║  ██║ ╚████║███████╗╚██████╔╝██║ ╚████║    v4.0 · GLM-5.2 · NIM ║
║  ╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝                         ║
╚══════════════════════════════════════════════════════════════════╝
        """
        console.print(Panel(
            Text.from_markup(f"[neon_cyan]{banner_text}[/neon_cyan]"),
            box=DOUBLE_EDGE,
            border_style="neon_magenta",
            padding=(0, 2)
        ))


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: TOKEN BUCKET & RATE LIMITING (Indestructible)
# ═══════════════════════════════════════════════════════════════════════════════

class TokenBucket:
    """Thread-safe token bucket for RPM enforcement with jitter."""

    def __init__(self, rpm: float, burst: int = 2, min_gap: float = 0.5, safety: float = 0.80):
        self.rpm = max(1.0, rpm) * safety
        self.burst = burst
        self.min_gap = min_gap
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self.last_request = 0.0
        self.lock = threading.Lock()
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

    def acquire(self, timeout: float = 60.0) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            with self.lock:
                self._refill()
                self._prune()
                wait = self.wait_time()
                if wait <= 0.01:
                    self.tokens -= 1.0
                    self.last_request = time.monotonic()
                    return True
            time.sleep(min(wait, 0.5))
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
    """A single API endpoint with failure tracking and cooldown."""

    def __init__(self, name: str, base_url: str, api_key: str, model_cfg: Dict[str, Any]):
        self.name = name
        self.model_cfg = model_cfg
        self.model_id = model_cfg["id"]
        self.bucket = TokenBucket(model_cfg.get("rpm", 20), safety=0.80)
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=300) if HAS_OPENAI else None
        self.cooldown_until = 0.0
        self.failures = 0

    def available(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def record_success(self):
        self.bucket.commit()
        self.failures = max(0, self.failures - 1)

    def record_failure(self, cooldown: float = 60.0):
        self.failures += 1
        self.cooldown_until = time.monotonic() + cooldown * min(self.failures, 5)


class ProviderPool:
    """Rotates across providers on failure / rate-limit with telemetry."""

    def __init__(self, providers: List[Provider]):
        self.providers = providers
        self.index = 0

    def current(self) -> Provider:
        return self.providers[self.index]

    def rotate(self):
        self.index = (self.index + 1) % len(self.providers)

    def next_available(self) -> Optional[Provider]:
        for _ in range(len(self.providers)):
            p = self.current()
            if p.available() and p.bucket.acquire(timeout=5.0):
                return p
            self.rotate()
        return None

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

    if api_key and model_key in MODELS:
        providers.append(Provider("NIM-Primary", base_url, api_key, MODELS[model_key]))

    # NVIDIA NIM fallbacks (same key, different models)
    fallbacks = ["nemotron-ultra", "llama-3.1-405b", "glm-5.2-fp8"]
    for fb in fallbacks:
        if fb != model_key and fb in MODELS and api_key:
            providers.append(Provider(f"NIM-{fb}", base_url, api_key, MODELS[fb]))

    # OpenRouter free tier fallback
    if config.get("enable_openrouter", True):
        or_key = os.environ.get("OPENROUTER_API_KEY")
        if or_key:
            or_models = [
                ("OR-Nemotron", "nvidia/nemotron-3-ultra-550b-a55b:free"),
                ("OR-Qwen3", "qwen/qwen3-coder:free"),
            ]
            for name, mid in or_models:
                fake_cfg = {"id": mid, "rpm": 15}
                providers.append(Provider(name, "https://openrouter.ai/api/v1", or_key, fake_cfg))

    if not providers:
        raise RuntimeError("No providers configured. Set NVIDIA API key in config or OPENROUTER_API_KEY env.")

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
    description = "Read the contents of a file. Use offset/limit for large files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Relative path to file"},
            "offset": {"type": "integer", "description": "Line number to start from (1-based)", "default": 1},
            "limit": {"type": "integer", "description": "Max lines to read", "default": 200},
        },
        "required": ["path"],
    }

    def execute(self, path: str, offset: int = 1, limit: int = 200) -> ToolResult:
        try:
            fp = self._safe_path(path)
            if not fp.exists():
                return ToolResult("", error=f"File not found: {path}", is_error=True)
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            start = max(0, offset - 1)
            end = start + limit
            chunk = "".join(lines[start:end])
            if end < len(lines):
                chunk += f"\n\n... [{len(lines) - end} more lines] ..."
            return ToolResult(chunk)
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
                    icon = {"pending": "○", "in_progress": "◐", "done": "◈"}[todo["status"]]
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

    def __init__(self, compact_threshold: float = 0.10, ctx_window: int = 131072):
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
        for m in old:
            role = m.get("role", "")
            content = str(m.get("content", ""))[:120].replace("\n", " ")
            if role == "tool":
                content = f"[tool result from {m.get('name', '?')}]"
            elif role == "assistant" and m.get("tool_calls"):
                names = [tc.get("function", {}).get("name", "?") for tc in m["tool_calls"]]
                content = f"[called tools: {', '.join(names)}]"
            summaries.append(f"  {role}: {content}")

        self.compaction_summary = (
            f"[FOLDED {len(old)} MESSAGES]\n" + "\n".join(summaries[-30:])
        )
        self.messages = sys_msgs + [
            {"role": "user", "content": f"[PRIOR CONTEXT SUMMARY]\n{self.compaction_summary}\n\nYou are mid-task. Continue executing the next required tool immediately."},
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

SYSTEM_PROMPT_TEMPLATE = """You are Neon Architect, an expert autonomous software engineer.
Your mission: write, edit, read, search, and execute code to achieve the user's goal.

CRITICAL RULES:
1. ALWAYS use the native JSON function calling API for tools. Never output raw XML or markdown code blocks for tool calls.
2. If you need to use a tool, CALL IT IMMEDIATELY in the same response. Do NOT announce your intention and stop.
3. Read files before editing them. Search before writing new files to avoid duplication.
4. Write clean, documented code. Follow the project's existing style.
5. After making changes, verify with tests or by reading the modified file.
6. If a task is complex, break it into sub-tasks using the 'task' tool.
7. Use the 'todo' tool to track multi-step tasks.

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
            compact_threshold=config.get("compact_threshold", 0.10),
            ctx_window=self.model_cfg.get("ctx_window", 131072),
        )
        self.meter = TokenMeter()
        self.round = 0
        self.nudges = 0
        self.running = True

        self._rebuild_system()
        UI.separator()
        UI.ok(f"Initialized in {self.project_dir}")
        UI.info(f"Model: {self.model_cfg['name']} ({self.model_cfg['id']})")

    def _rebuild_system(self):
        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            project_dir=str(self.project_dir),
            model_name=self.model_cfg["name"],
        )
        if self.ctx.compaction_summary:
            prompt += f"\n\n[COMPACTED HISTORY]\n{self.ctx.compaction_summary}"
        self.ctx.add_system(prompt)

    def _build_payload(self) -> Dict[str, Any]:
        payload = {
            "model": self.pool.current().model_id,
            "messages": self.ctx.export(),
            "temperature": self.config.get("temperature", 0.2),
            "max_tokens": self.model_cfg.get("max_tokens", 32768),
            "stream": True,
            "tools": tools_schema(self.tools),
            "tool_choice": "auto",
        }
        extra = self.model_cfg.get("extra_body")
        if extra:
            payload["extra_body"] = extra
        return payload

    def _stream_response(self, provider: Provider, payload: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        """Yields chunks from the API stream with overload protection and telemetry."""
        if not provider.client:
            raise RuntimeError("OpenAI client not available")

        resp = provider.client.chat.completions.create(**payload)
        last_chunk_time = time.monotonic()
        stream_timeout = self.config.get("stream_timeout", 30.0)

        for chunk in resp:
            last_chunk_time = time.monotonic()
            yield {"type": "chunk", "data": chunk}

            if time.monotonic() - last_chunk_time > stream_timeout:
                yield {"type": "error", "msg": "Stream timed out — provider dropped connection"}
                break

    def _parse_stream(self, provider: Provider, payload: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
        """
        Streams to completion. Returns (content, reasoning, tool_calls).
        Handles provider rotation on overload/rate-limit.
        """
        content = ""
        reasoning = ""
        tool_calls: List[Dict[str, Any]] = []
        finish_reason = None
        overload_retries = 0
        max_retries = self.config.get("retry_max", 20)

        while overload_retries <= max_retries:
            provider = self.pool.next_available()
            if not provider:
                wait = self.pool.shortest_wait()
                UI.warn(f"All providers busy. Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            wt = provider.bucket.wait_time()
            if wt > 0.5:
                UI.info(f"Rate limit pacing ({wt:.1f}s)...")
                time.sleep(wt)

            try:
                if HAS_RICH:
                    console.print(f"  [neon_dim]◈ connecting {UI.esc(provider.name)}…[/neon_dim]", end="\r")
                else:
                    print(f"  ◈ {provider.name}…", end="\r")

                payload["model"] = provider.model_id
                in_think = False
                printed_len = 0

                for event in self._stream_response(provider, payload):
                    if event["type"] == "error":
                        raise Exception(event["msg"])

                    chunk = event["data"]
                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta

                    if chunk.choices[0].finish_reason is not None:
                        finish_reason = chunk.choices[0].finish_reason

                    # Reasoning content (GLM-5.2)
                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        if not in_think:
                            print(" " * 70, end="\r")
                            if self.config.get("show_thinking", True):
                                if HAS_RICH:
                                    console.print(UI.thinking_block(""))
                                else:
                                    print("◈ THINKING...")
                            in_think = True
                        reasoning += delta.reasoning_content
                        if self.config.get("show_thinking", True):
                            if HAS_RICH:
                                console.print(Text(delta.reasoning_content, style="thinking"), end="")
                            else:
                                print(delta.reasoning_content, end="", flush=True)

                    # Regular content
                    if delta.content:
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

                    # Tool calls
                    if delta.tool_calls:
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
                                        print(f"\n◈ {name}(...)")
                                if tc.function.arguments:
                                    tool_calls[idx]["arguments"] += tc.function.arguments

                # Check for silent truncation
                if finish_reason is None:
                    raise Exception("Stream ended without finish_reason — provider dropped connection")

                print()
                provider.record_success()
                return content, reasoning, tool_calls

            except Exception as e:
                err_str = str(e).lower().replace(" ", "")
                is_overload = any(x in err_str for x in [
                    "429", "toomanyrequests", "ratelimit", "resourceexhausted",
                    "overloaded", "503", "502", "500", "504", "workerlocal"
                ])
                if is_overload:
                    print()
                    UI.warn(f"Overload from {provider.name}: {e}")
                    provider.record_failure(cooldown=60.0)
                    self.pool.rotate()
                    overload_retries += 1
                    time.sleep(self.config.get("retry_base_delay", 3.0))
                    continue
                else:
                    print()
                    UI.err(f"API error: {e}")
                    raise

        raise RuntimeError(f"Max overload retries ({max_retries}) exceeded.")

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
                print(f"◈ {name}({preview})")

            result = execute_tool(self.tools, name, args)
            UI.tool_result(name, result.text()[:500], result.is_error)

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
        """Execute one full turn: user input → LLM → tools → loop."""
        if user_input:
            self.ctx.add_user(user_input)
            if HAS_RICH:
                console.print(UI.user_message(user_input))
            else:
                print(f">>> {user_input}")

        while self.round < self.config.get("max_rounds", 100):
            self.round += 1

            # Context compaction check
            if self.ctx.should_compact():
                before = self.ctx.estimate_tokens()
                if self.ctx.compact(keep_recent=8):
                    after = self.ctx.estimate_tokens()
                    UI.info(f"Context compacted: ~{before:,} → ~{after:,} tokens")
                    self._rebuild_system()

            tokens = self.ctx.estimate_tokens()
            if HAS_RICH:
                console.print(UI.turn_indicator(self.round, tokens))
            else:
                UI.separator(f"TURN {self.round} | ~{tokens} tokens")

            payload = self._build_payload()

            try:
                content, reasoning, tool_calls = self._parse_stream(
                    self.pool.current(), payload
                )
            except Exception as e:
                UI.err(f"Turn failed: {e}")
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
                time.sleep(1.5)
                continue

            # Tool execution
            if tool_calls:
                self.nudges = 0
                self._execute_tools(tool_calls)
                time.sleep(1.0)
                continue

            # No tools — assistant response
            self.ctx.add_assistant(content)

            # Auto-nudge if assistant announced but didn't act
            if self._should_nudge(content):
                UI.warn("Agent paused without action. Nudging...")
                self.ctx.add_user("Please proceed and execute the tool you just mentioned. Do not ask for permission.")
                self.nudges += 1
                time.sleep(1.5)
                continue

            self.nudges = 0
            break

        else:
            UI.warn("Max rounds reached. Stopping.")

    def cmd_files(self):
        tree = UI.file_tree(self.project_dir, self.project_dir)
        if HAS_RICH:
            console.print(Panel(tree, title="[neon_cyan]Project Files[/neon_cyan]", border_style="neon_magenta", padding=(1, 2)))
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
        else:
            available = ", ".join(MODELS.keys())
            UI.err(f"Unknown model '{name}'. Available: {available}")

    def cmd_todo(self):
        todo_tool = TodoTool(self.project_dir)
        result = todo_tool.execute(action="list")
        if HAS_RICH:
            console.print(Panel(
                Text.from_markup(f"[neon_yellow]{UI.esc(result.text())}[/neon_yellow]"),
                title="[neon_cyan]Task Tracker[/neon_cyan]",
                border_style="neon_magenta"
            ))
        else:
            print(result.text())


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 8: CONFIG & SESSION PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════════

def load_config() -> Dict[str, Any]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: Dict[str, Any]):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def ensure_api_key(cfg: Dict[str, Any]) -> bool:
    if cfg.get("api_key"):
        return True
    UI.separator("First-time setup")
    key = input("NVIDIA API Key (from https://build.nvidia.com): ").strip()
    if not key:
        UI.err("API key required.")
        return False
    cfg["api_key"] = key
    save_config(cfg)
    UI.ok("Key saved to ~/.neon_architect/config.json")
    return True


def save_session(agent: NeonArchitect):
    try:
        session = {
            "timestamp": datetime.now().isoformat(),
            "project": str(agent.project_dir),
            "model": agent.model_key,
            "messages": agent.ctx.messages,
            "compaction_summary": agent.ctx.compaction_summary,
            "meter": {"prompt": agent.meter.prompt, "completion": agent.meter.completion},
        }
        sid = uuid.uuid4().hex[:8]
        sf = SESSIONS_DIR / f"session_{sid}.json"
        with open(sf, "w", encoding="utf-8") as f:
            json.dump(session, f)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 9: MAIN LOOP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--model", "-m", default=None, help="Model key (glm-5.2, nemotron-ultra, ...)")
    args = parser.parse_args()

    cfg = load_config()
    project = Path(args.project).resolve()
    cfg["project_dir"] = str(project)
    if args.model:
        cfg["default_model"] = args.model

    if not ensure_api_key(cfg):
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

    UI.separator("Ready")
    UI.info("Type your request, or use /files, /cost, /clear, /compact, /model <name>, /todo, /exit")

    while True:
        try:
            if HAS_RICH:
                raw = console.input("[neon_prompt]◈[/neon_prompt] ").strip()
            else:
                raw = input("◈ ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not raw:
            raw = "Please proceed with the current task."

        if raw == "/exit":
            break
        if raw == "/clear":
            agent.ctx.clear()
            agent._rebuild_system()
            agent.round = 0
            UI.ok("Context cleared. Starting fresh.")
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
        if raw.startswith("/"):
            UI.warn(f"Unknown command: {raw}. Try /exit, /clear, /files, /cost, /compact, /model, /todo")
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

    save_session(agent)
    UI.separator()
    UI.ok(f"Session saved. Total usage: {agent.meter.report()}")
    print("Goodbye.")


if __name__ == "__main__":
    main()
