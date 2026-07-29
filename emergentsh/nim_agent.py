#!/usr/bin/env python3
"""
NIM Agent v2.5 — Indestructible, Fast, Auto-Nudging
- Token-bucket RPM enforcement (default 40, configurable)
- Dynamic profiles (any number, user-defined)
- Concurrency cap + jitter + Retry-After respect
- Stream telemetry to prevent "silent hang" illusions
- Lean Input / Fat Output optimization for fast TTFT (10% compaction, 32k output)
- Mid-stream overload protection and auto-retry
- Silent Stream Truncation detection
- Chatty-Stop Auto-Nudge (prevents LLM from pausing without executing tools)
- Auto-Correction Interceptor for XML hallucinations
"""

import json
import os
import random
import re
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.rule import Rule
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.padding import Padding
    from rich.theme import Theme
    from rich.box import ROUNDED, SQUARE
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Windows ANSI color support
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

LEGACY_WIN_CONSOLE = (
    sys.platform == "win32"
    and not os.environ.get("WT_SESSION")
    and not os.environ.get("ANSICON")
    and os.environ.get("ConEmuANSI") != "ON"
    and not os.environ.get("TERM_PROGRAM")
)

# ───────────────────────────────────────────
# THEME 
# ───────────────────────────────────────────
if HAS_RICH:
    THEME = Theme({
        "accent":     "bold #7aa2f7",
        "accent.dim": "#7aa2f7",
        "ok":         "bold #9ece6a",
        "warn":       "bold #e0af68",
        "err":        "bold #f7768e",
        "muted":      "#565f89",
        "label":      "bold #c0caf5",
        "value":      "#a9b1d6",
        "think":      "italic #bb9af7",
        "tool":       "bold #e0af68",
        "assistant":  "#c0caf5",
        "border":     "#3b4261",
        "title":      "bold #7aa2f7",
    })
    console = Console(theme=THEME, highlight=False)
else:
    console = None

# ───────────────────────────────────────────
# ANSI COLORS & ICONS
# ───────────────────────────────────────────
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; MAGENTA = "\033[35m"; CYAN = "\033[36m"
    WHITE = "\033[37m"
    BRED = "\033[91m"; BGREEN = "\033[92m"; BYELLOW = "\033[93m"
    BBLUE = "\033[94m"; BMAGENTA = "\033[95m"; BCYAN = "\033[96m"
    BWHITE = "\033[97m"

I = {
    "bot": "»", "brain": "◆", "code": "▸", "bug": "×", "rocket": "»", "check": "✓",
    "cross": "✗", "warn": "!", "info": "i", "sparkle": "*", "gear": "⚙", "file": "▤",
    "folder": "▸", "search": "?", "git": "±", "test": "✓", "run": "▶", "save": "↓",
    "key": "•", "star": "*", "clock": "~", "target": "◎", "bulb": "*", "tools": "⚙"
}
if LEGACY_WIN_CONSOLE:
    for k in I:
        I[k] = {"check": "[OK]", "cross": "[X]", "warn": "[!]"}.get(k, I[k])

# ───────────────────────────────────────────
# UI HELPERS
# ───────────────────────────────────────────
def ok(msg: str):
    if HAS_RICH:
        console.print(f"  [ok]✓[/ok] [value]{esc(msg)}[/value]")
    else:
        print(f"  {C.BGREEN}{C.BOLD}✓{C.RESET} {msg}")

def err(msg: str):
    if HAS_RICH:
        console.print(f"  [err]✗[/err] [value]{esc(msg)}[/value]")
    else:
        print(f"  {C.BRED}{C.BOLD}✗{C.RESET} {msg}")

def warn(msg: str):
    if HAS_RICH:
        console.print(f"  [warn]![/warn] [value]{esc(msg)}[/value]")
    else:
        print(f"  {C.BYELLOW}{C.BOLD}!{C.RESET} {msg}")

def info(msg: str):
    if HAS_RICH:
        console.print(f"  [accent]i[/accent] [value]{esc(msg)}[/value]")
    else:
        print(f"  {C.BCYAN}{C.BOLD}ℹ{C.RESET} {msg}")

def sep(title: str = ""):
    # UI FIX: Using simple hyphens "-" instead of box characters to fix the cmd.exe □□□ bug
    if HAS_RICH:
        console.print(Rule(title, style="border", characters="-") if title else Rule(style="border", characters="-"))
    else:
        print(f"{C.DIM}------------------------------------------------------------{C.RESET}")

def esc(s: str) -> str:
    return s.replace("[", "\\[") if HAS_RICH else s

def banner(subtitle: str = ""):
    if HAS_RICH:
        title = Text("NIM AGENT", style="title")
        title.append("  v2.5", style="muted")
        body = Group(title, Text(subtitle, style="muted")) if subtitle else title
        console.print(Panel(body, box=ROUNDED, border_style="border", padding=(0, 2)))
    else:
        print(f"{C.BMAGENTA}{C.BOLD}NIM AGENT v2.5{C.RESET}")
        if subtitle:
            print(f"{C.DIM}{subtitle}{C.RESET}")

# ───────────────────────────────────────────
# PATHS & CONFIG
# ───────────────────────────────────────────
CONFIG_FILE = Path.home() / ".nim_agent_config.json"
SESSIONS_FILE = Path.home() / ".nim_agent_sessions.json"
NIM_BASE = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
OPENROUTER_FREE_MODELS = [
    ("OR-Nemotron", "nvidia/nemotron-3-ultra-550b-a55b:free"),
    ("OR-Qwen3", "qwen/qwen3-coder:free"),
]

# ───────────────────────────────────────────
# TOKEN BUCKET RATE LIMITER
# ───────────────────────────────────────────
class TokenBucket:
    def __init__(self, rpm: float = 20.0, burst: int = 1, min_gap: float = 1.0, safety_margin: float = 0.8):
        self.ceiling_rpm = max(1.0, rpm)
        self.rpm = self.ceiling_rpm * safety_margin
        self.burst = burst
        self.base_min_gap = min_gap
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self.last_request_time = 0.0
        self.lock = threading.Lock()
        self.history = deque()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * (self.rpm / 60.0))
        self.last_update = now

    def _prune(self):
        cutoff = time.monotonic() - 60.0
        while self.history and self.history[0] < cutoff:
            self.history.popleft()

    def _wait_time(self) -> float:
        self._refill()
        self._prune()
        waits = []
        if self.tokens < 1.0:
            waits.append((1.0 - self.tokens) / (self.rpm / 60.0))
        if len(self.history) >= max(1, int(self.rpm)):
            if self.history:
                waits.append(60.0 - (time.monotonic() - self.history[0]) + 0.5)
        since_last = time.monotonic() - self.last_request_time
        if since_last < self.base_min_gap:
            waits.append(self.base_min_gap - since_last)
        return max(waits) if waits else 0.0

    def reserve(self, timeout: float = 60.0) -> bool:
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            with self.lock:
                wait = self._wait_time()
                if wait <= 0.01:
                    self.tokens -= 1.0
                    self.last_request_time = time.monotonic()
                    return True
            time.sleep(wait)
        return False

    def commit(self):
        with self.lock:
            self.history.append(time.monotonic())

class TokenMeter:
    def __init__(self):
        self.total_prompt = 0
        self.total_completion = 0
        self.lock = threading.Lock()

    def record(self, p: int, c: int):
        with self.lock:
            self.total_prompt += max(0, p)
            self.total_completion += max(0, c)

# ───────────────────────────────────────────
# PROVIDER POOL
# ───────────────────────────────────────────
class Provider:
    def __init__(self, name: str, base_url: str, api_key: str, model_id: str, rpm: float):
        self.name = name
        self.model_id = model_id
        self.bucket = TokenBucket(rpm=rpm, min_gap=1.0)
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=300) if HAS_OPENAI else None
        self.cooldown_until = 0.0

    def is_available(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def record_success(self):
        self.bucket.commit()

    def record_rejection(self):
        self.cooldown_until = time.monotonic() + 60.0

class ProviderPool:
    def __init__(self, providers: List[Provider]):
        self.providers = providers
        self.idx = 0

    def current(self) -> Provider: 
        return self.providers[self.idx]
        
    def rotate(self): 
        self.idx = (self.idx + 1) % len(self.providers)
    
    def next_available(self) -> Optional[Provider]:
        for _ in range(len(self.providers)):
            if self.current().is_available(): return self.current()
            self.rotate()
        return None

    def wait_time(self) -> float:
        waits = [max(0.0, p.cooldown_until - time.monotonic()) for p in self.providers]
        return min(waits) if waits else 5.0

def build_provider_pool(profile: Dict) -> ProviderPool:
    m = profile["models"][profile["default_model"]]
    providers = [Provider("NVIDIA NIM", NIM_BASE, profile["key"], m["id"], profile.get("rpm", 20.0))]
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if or_key:
        for name, mid in OPENROUTER_FREE_MODELS:
            providers.append(Provider(name, OPENROUTER_BASE, or_key, mid, 18.0))
    return ProviderPool(providers)

# ───────────────────────────────────────────
# TOOLS
# ───────────────────────────────────────────
class FileTools:
    def __init__(self, base: str):
        self.base = Path(base).resolve()

    def _safe(self, p: str) -> Path:
        t = (self.base / p).resolve()
        try:
            t.relative_to(self.base)
        except ValueError:
            raise PermissionError(f"Path '{p}' escapes project directory ({self.base})")
        return t

    def read(self, path: str) -> str:
        try:
            t = self._safe(path)
            if not t.exists(): return f"[ERR] File not found: {path}"
            with open(t, "r", encoding="utf-8", errors="replace") as f: return f.read()
        except Exception as e: return f"[ERR] {e}"

    def write(self, path: str, content: str) -> str:
        try:
            t = self._safe(path)
            t.parent.mkdir(parents=True, exist_ok=True)
            with open(t, "w", encoding="utf-8") as f: f.write(content)
            return f"[OK] Written {len(content)} chars to {path}"
        except Exception as e: return f"[ERR] {e}"

    def search(self, pattern: str, path: str = ".") -> str:
        try:
            t = self._safe(path)
            rx = re.compile(pattern, re.IGNORECASE)
            matches = []
            for root, dirs, files in os.walk(t):
                dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".venv", "node_modules")]
                for fn in files:
                    if fn.endswith((".pyc", ".exe", ".dll", ".png", ".jpg", ".zip", ".tar")): continue
                    fp = Path(root) / fn
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as f:
                            for i, line in enumerate(f, 1):
                                if rx.search(line):
                                    matches.append(f"{fp.relative_to(self.base)}:{i} {line.strip()}")
                                    if len(matches) >= 50: break
                    except Exception: pass
                    if len(matches) >= 50: break
            return "\n".join(matches) if matches else f"No matches for '{pattern}'"
        except Exception as e: return f"[ERR] {e}"

    def run_cmd(self, cmd: str) -> str:
        try:
            if HAS_RICH: console.print(f"  [accent]▶ Executing Live:[/accent] {esc(cmd)}")
            else: print(f"  {C.BCYAN}▶ Executing Live:{C.RESET} {cmd}")
            p = subprocess.Popen(cmd, cwd=self.base, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
            out = []
            for line in p.stdout:
                out.append(line)
                if HAS_RICH: console.print(f"    [muted]│[/muted] {esc(line.rstrip(chr(10)))}")
                else: print(f"    {C.DIM}│{C.RESET} {line}", end="")
            try:
                p.wait(timeout=120)
                return "".join(out) + f"\n[EXIT CODE: {p.returncode}]"
            except subprocess.TimeoutExpired:
                p.kill()
                return "\n[ERR: command exceeded 120s timeout and was killed]"
        except Exception as e: return f"[ERR] {e}"

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create/overwrite file.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "search_files", "description": "Regex search in project.", "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string", "default": "."}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "run_command", "description": "Run shell command/tests.", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
]

def execute_tool(tools: FileTools, name: str, args: Dict) -> str:
    if name == "read_file": return tools.read(args.get("path", ""))
    if name == "write_file": return tools.write(args.get("path", ""), args.get("content", ""))
    if name == "search_files": return tools.search(args.get("pattern", ""), args.get("path", "."))
    if name == "run_command": return tools.run_cmd(args.get("command", ""))
    return f"[ERR] Unknown tool: {name}"

# ───────────────────────────────────────────
# AGENT CORE
# ───────────────────────────────────────────
class NIMAgent:
    def __init__(self, profile: Dict, pdir: str):
        self.profile = profile
        self.pdir = pdir
        self.tools = FileTools(pdir)
        self.pool = build_provider_pool(profile)
        self.messages = []
        self.goal = None
        self.meter = TokenMeter()
        self.compact_threshold = 0.10
        self.compaction_summary = None

        s = self._load_session(profile["name"], pdir)
        if s:
            try: resume = input(f"  Resume saved session? [Y/n]: ").strip().lower()
            except KeyboardInterrupt: resume = "n"; print()
            if resume != 'n':
                self.messages = s.get("messages", [])
                self.goal = s.get("goal")
                self.compaction_summary = s.get("compaction_summary")
                ok("Session restored.")
        self._rebuild_system()

    def _load_session(self, pk: str, pdir: str) -> Optional[Dict]:
        k = f"{pk}::{pdir}"
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r") as f: return json.load(f).get(k)
            except Exception: pass
        return None

    def save(self):
        k = f"{self.profile['name']}::{self.pdir}"
        s = {}
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, "r") as f: s = json.load(f)
            except Exception: pass
        s[k] = {"messages": self.messages, "goal": self.goal, "compaction_summary": self.compaction_summary}
        with open(SESSIONS_FILE, "w") as f: json.dump(s, f)

    def _rebuild_system(self):
        p = ["You are an expert autonomous developer. Use tools proactively to achieve the goal."]
        p.append("CRITICAL: You MUST use the native JSON function calling API to execute tools.")
        # NEW FIX: Explicitly forbid announcing and pausing
        p.append("CRITICAL: If you intend to use a tool, you MUST use it immediately in the exact same response. "
                 "DO NOT announce your intentions and stop. DO NOT wait for user permission.")
        p.append("NEVER output raw XML or markdown blocks (like <tool_call>) under any circumstances.")
        
        if self.goal: p.append(f"CURRENT GOAL: {self.goal}")
        p.append(f"Working Directory: {self.pdir}")
        self.messages = [m for m in self.messages if m.get("role") != "system"]
        self.messages.insert(0, {"role": "system", "content": "\n".join(p)})
        if self.compaction_summary:
            if not any(self.compaction_summary in (m.get("content") or "") for m in self.messages):
                # NEW FIX: Jedi mind-trick the LLM into continuing after compaction
                self.messages.insert(1, {"role": "user", "content": f"[PRIOR CONTEXT SUMMARY]\n{self.compaction_summary}\n\nYou are mid-task. Do not ask for permission. Execute the next required tool immediately."})
                self.messages.insert(2, {"role": "assistant", "content": "Context acknowledged. I will execute the next tool directly."})

    def est_tokens(self) -> int:
        return sum(max(1, len(str(m.get("content", ""))) // 4) for m in self.messages)

    def maybe_compact(self):
        ctx_size = self.est_tokens()
        if ctx_size < 128000 * self.compact_threshold: return
        sys_msgs = [m for m in self.messages if m.get("role") == "system"]
        rest = [m for m in self.messages if m.get("role") != "system"]
        if len(rest) <= 8: return

        old, recent = rest[:-8], rest[-8:]
        lines = []
        for m in old:
            c = str(m.get("content", ""))[:150].replace("\n", " ")
            lines.append(f"- {m.get('role')}: {c}")

        self.compaction_summary = f"Folded {len(old)} messages.\n" + "\n".join(lines[-40:])
        self.messages = sys_msgs + recent
        self._rebuild_system()
        info(f"Context compacted: ~{ctx_size} -> ~{self.est_tokens()} tokens")

    def run(self, prompt: str):
        if prompt:
            self.messages.append({"role": "user", "content": prompt})

        rnd = 0
        retries = 0
        nudges = 0
        
        while rnd < 100:
            self.maybe_compact()
            ctx = self.est_tokens()
            
            if HAS_RICH:
                t = Table.grid(padding=(0, 2))
                t.add_column(justify="left"); t.add_column(justify="right")
                t.add_row(Text.from_markup(f"[label]Round {rnd + 1}[/label][muted]/100[/muted]"), Text.from_markup(f"[muted]context ~{ctx} tok[/muted]"))
                console.print(Rule(style="border", characters="-")); console.print(t)
            else:
                sep(); print(f"{C.BCYAN}{C.BOLD}Round {rnd+1}/100{C.RESET} {C.DIM}| Context: ~{ctx} tokens{C.RESET}")

            payload = {
                "messages": [{k: v for k, v in m.items() if not k.startswith('_')} for m in self.messages],
                "max_tokens": 32768, "temperature": 0.2, "stream": True,
                "tools": TOOLS_SCHEMA, "tool_choice": "auto"
            }

            full_content = ""; full_reason = ""; tcalls = []
            provider = None; overloaded = False

            try:
                for _ in range(5):
                    provider = self.pool.next_available()
                    if not provider:
                        warn(f"Waiting {self.pool.wait_time():.1f}s for rate limits..."); time.sleep(self.pool.wait_time()); continue

                    with provider.bucket.lock: wt = provider.bucket._wait_time()
                    if wt > 0.5:
                        if HAS_RICH: console.print(f"  [muted]pacing rate limit (~{wt:.1f}s)...[/muted]")
                        else: print(f"  {C.DIM}⏳ Pacing API rate limit (~{wt:.1f}s)...{C.RESET}")
                    if not provider.bucket.reserve(60):
                        self.pool.rotate(); continue

                    if HAS_RICH: console.print(f"  [muted]awaiting {esc(provider.name)} (TTFT)...[/muted]", end="\r")
                    else: print(f"  {C.DIM}📡 Awaiting {provider.name}...{C.RESET}", end="\r")

                    payload["model"] = provider.model_id
                    if "glm" in provider.model_id: payload["extra_body"] = {"chat_template_kwargs": {"enable_thinking": True, "thinking_effort": "medium"}}

                    resp = provider.client.chat.completions.create(**payload)
                    in_think = False; print(" " * 60, end="\r")
                    
                    finish_reason = None

                    for chunk in resp:
                        if chunk.choices and len(chunk.choices) > 0:
                            if chunk.choices[0].finish_reason is not None:
                                finish_reason = chunk.choices[0].finish_reason
                                
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            if not in_think:
                                if HAS_RICH: console.print("  [think]◆ thinking[/think]")
                                else: print(f"  {C.BMAGENTA}🧠 Thinking:{C.RESET}")
                                in_think = True
                            if HAS_RICH: console.print(Text(delta.reasoning_content, style="think"), end="")
                            else: print(f"{C.DIM}{delta.reasoning_content}{C.RESET}", end="", flush=True)
                            full_reason += delta.reasoning_content

                        if delta.content:
                            if in_think: print(); in_think = False
                            if HAS_RICH: console.print(Text(delta.content, style="assistant"), end="")
                            else: print(f"{C.BWHITE}{delta.content}{C.RESET}", end="", flush=True)
                            full_content += delta.content

                        if delta.tool_calls:
                            if in_think: print(); in_think = False
                            for tc in delta.tool_calls:
                                idx = tc.index
                                while len(tcalls) <= idx: tcalls.append({"id": "", "name": "", "args": ""})
                                if tc.id: tcalls[idx]["id"] += tc.id
                                if tc.function:
                                    if tc.function.name:
                                        tcalls[idx]["name"] += tc.function.name
                                        if HAS_RICH: console.print(f"\n  [tool]▸ preparing tool:[/tool] {esc(tcalls[idx]['name'])}...")
                                        else: print(f"\n  {C.BYELLOW}🛠 Preparing:{C.RESET} {tcalls[idx]['name']}...", flush=True)
                                    if tc.function.arguments:
                                        tcalls[idx]["args"] += tc.function.arguments

                    if finish_reason is None:
                        raise Exception("502 Server Overload: Connection silently dropped by provider before completion.")
                        
                    break
                
                if provider: provider.record_success()

            except Exception as e:
                err_str = str(e).lower().replace(" ", "")
                if any(x in err_str for x in ["429", "toomanyrequests", "ratelimit", "resourceexhausted", "workerlocaltotalrequestlimit", "overloaded", "503", "502", "500", "504"]):
                    print()
                    warn("Server overload — connection dropped mid-stream.")
                    if HAS_RICH: console.print("  [muted]Retrying round...[/muted]\n")
                    else: print(f"  {C.DIM}Retrying round...{C.RESET}\n")
                    if provider: provider.record_rejection()
                    self.pool.rotate(); time.sleep(3.0); overloaded = True
                else:
                    print(); err(f"API error: {e}"); return

            if overloaded:
                retries += 1
                if retries > 20: err("Too many overload retries — aborting."); return
                continue
            retries = 0

            print("\n", flush=True)
            self.meter.record(ctx, len(full_content) // 4)

            # ─── AUTO-CORRECTION INTERCEPTOR ───
            if not tcalls and re.search(r"<(tool_call|function|parameter)", full_content):
                warn("Detected raw XML hallucination. Auto-correcting memory...")
                self.messages.append({"role": "assistant", "content": full_content})
                self.messages.append({
                    "role": "user", 
                    "content": "SYSTEM ERROR: You just output raw XML tags for a tool call. "
                               "This is strictly forbidden. You MUST use the native JSON function calling API to execute tools. "
                               "Please re-issue your command correctly."
                })
                self.save()
                time.sleep(2.0)
                continue

            # ─── TOOL EXECUTION ───
            if tcalls:
                nudges = 0 # reset nudges if successful
                self.messages.append({
                    "role": "assistant", "content": full_content or None,
                    "tool_calls": [{"id": t["id"], "type": "function", "function": {"name": t["name"], "arguments": t["args"]}} for t in tcalls]
                })

                for t in tcalls:
                    name = t["name"]
                    try: args = json.loads(t["args"])
                    except Exception: args = {}

                    args_str = json.dumps(args, ensure_ascii=False)
                    args_preview = args_str[:150] + "...}" if len(args_str) > 150 else args_str

                    if HAS_RICH: console.print(f"  [tool]⚙ executing:[/tool] {esc(name)} [muted]{esc(args_preview)}[/muted]")
                    else: print(f"  {C.BYELLOW}⚙ Executing:{C.RESET} {name} {C.DIM}{args_preview}{C.RESET}")
                    
                    res = execute_tool(self.tools, name, args)
                    ui_res = res[:1500] + f"\n\n  ... [Terminal preview truncated. Agent received full {len(res)} chars.] ..." if len(res) > 1500 else res

                    for line in ui_res.split("\n"):
                        if HAS_RICH: console.print(f"    [muted]│[/muted] {esc(line)}")
                        else: print(f"    {C.DIM}│{C.RESET} {line}")

                    self.messages.append({"role": "tool", "tool_call_id": t["id"], "name": name, "content": res[:max(2000, 128000 - ctx) * 4]})

                self.save()
                time.sleep(3.0)
                rnd += 1
            else:
                self.messages.append({"role": "assistant", "content": full_content})
                
                # NEW FIX: Chatty-Stop Auto-Nudge
                action_phrases = ["let me", "i will", "i need to", "i'm going to", "allow me to", "i should", "here is the plan"]
                is_chatty_promise = len(full_content) < 800 and any(p in full_content.lower() for p in action_phrases)
                
                if is_chatty_promise and nudges < 3:
                    warn("Agent paused without calling a tool. Auto-nudging...")
                    self.messages.append({"role": "user", "content": "Please proceed and execute the tool you just mentioned."})
                    nudges += 1
                    time.sleep(2.0)
                    continue # immediately run next round without stopping
                
                self.save()
                break

# ───────────────────────────────────────────
# UI RUNNER
# ───────────────────────────────────────────
def load_config() -> Dict:
    c = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f: c = json.load(f)
        except Exception: pass
    if "profiles" not in c:
        c["profiles"] = {}
    return c

def create_profile(c: Dict) -> str:
    sep("New Profile Setup")
    name = input("Profile name: ").strip() or f"PROFILE_{len(c['profiles'])+1}"
    key = input("NVIDIA API key: ").strip()
    
    new_id = str(max([int(k) for k in c["profiles"].keys() if k.isdigit()] + [0]) + 1)
    
    c["profiles"][new_id] = {
        "name": name, 
        "key": key, 
        "default_model": "glm", 
        "rpm": 40.0, 
        "models": {
            "glm": {
              "name": "ases-GLM",
              "id": "z-ai/glm-5.2"
            },
            "nemotron": {
              "name": "ases-Nemotron",
              "id": "nvidia/nemotron-3-ultra-550b-a55b"
            }
        }
    }
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f: json.dump(c, f, indent=2)
    ok(f"Profile '{name}' created successfully!")
    return new_id

def main():
    try:
        os.system('cls' if os.name == 'nt' else 'clear'); banner()
        cfg = load_config()
        
        if not cfg["profiles"]:
            warn("No profiles found. Let's create one.")
            create_profile(cfg)
            
        profiles = cfg["profiles"]
        
        if HAS_RICH: console.print("\n[label]Available Profiles[/label]")
        else: print(f"\n{C.BOLD}Available Profiles{C.RESET}")
        
        for pid, p in profiles.items(): 
            try:
                model_id = p["models"][p["default_model"]]["id"]
            except KeyError:
                model_id = "unknown"
            print(f" [{pid}] {p.get('name', 'Unknown')} ({model_id})")
        
        choice = input(f"\nSelect profile or type 'new' [default: 1]: ").strip().lower() or "1"
        
        if choice == "new":
            choice = create_profile(cfg)
            profiles = cfg["profiles"]
        elif choice not in profiles:
            warn(f"Invalid profile '{choice}'. Defaulting to first available.")
            choice = list(profiles.keys())[0]

        p = profiles[choice]
        agent = NIMAgent(p, os.getcwd())
        
        os.system('cls' if os.name == 'nt' else 'clear')
        banner(f"{p['name']}  ·  {agent.pool.current().model_id}")
        
        while True:
            try: cmd = console.input("[accent]❯[/accent] ").strip() if HAS_RICH else input(f"{C.BCYAN}❯{C.RESET} ").strip()
            except KeyboardInterrupt: break
            
            # NEW FIX: Empty Enter to Proceed 
            if not cmd: 
                cmd = "Please proceed."
                
            if cmd == "/exit": break
            if cmd == "/clear":
                agent.messages = []; agent._rebuild_system(); ok("Context cleared.")
                continue
            
            agent.run(cmd)
    except KeyboardInterrupt: print("\nExiting...")

if __name__ == "__main__":
    main()