#!/usr/bin/env python3
"""
Film Kit v1.0 — Free-Tier AI Filmmaking Pipeline
──────────────────────────────────────────────────
idea → script → storyboard images → narration → Ken-Burns clips → stitched film

Free-tier services used (bring your own free API key where noted):
  • NVIDIA NIM          (https://build.nvidia.com)  — free LLM for script/storyboard
    + optional OpenRouter free models as a fallback provider (same idea as nim_agent.py)
  • Pollinations.ai     (https://pollinations.ai)    — free, keyless text-to-image
  • Microsoft Edge TTS  (via the `edge-tts` package)  — free, keyless narration voices
  • ffmpeg              (local, open-source)          — Ken Burns clips + stitching

Install:
    pip install openai edge-tts
    # + a system install of ffmpeg (ffmpeg.org) available on PATH

First run will ask for a free NVIDIA NIM API key (build.nvidia.com → API Keys).
Everything else in the pipeline is keyless.

Extras:
  • A fixed per-project seed is reused across all scene images for a
    more consistent palette/style (Pollinations has no image-to-image
    reference, so recurring characters will still drift somewhat).
  • Optional ambient background music, synthesized locally with ffmpeg
    (no external "free music API" — those aren't reliable/licensed
    enough to depend on unattended). Toggle with /music on [mood].
  • Non-interactive batch mode for scripting, e.g.:
      python film_kit.py --idea "a lighthouse keeper meets a sea dragon" \\
          --scenes 8 --mode crossfade --music --project lighthouse
"""

import argparse
import asyncio
import json
import os
import random
import re
import shutil
import subprocess
import sys
import textwrap
import time
import urllib.parse
import urllib.request
from collections import deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False


# ───────────────────────────────────────────
# COLORS / UI HELPERS
# ───────────────────────────────────────────
class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    CYAN = "\033[36m"; MAGENTA = "\033[35m"
    BRED = "\033[91m"; BGREEN = "\033[92m"; BYELLOW = "\033[93m"
    BBLUE = "\033[94m"; BMAGENTA = "\033[95m"; BCYAN = "\033[96m"; BWHITE = "\033[97m"

H, V, TL, TR, BL, BR, ML, MR = "─", "│", "┌", "┐", "└", "┘", "├", "┤"
ARROW = "❯"

def ok(msg):   print(f"  {C.BGREEN}✓{C.RESET} {msg}")
def err(msg):  print(f"  {C.BRED}✗{C.RESET} {msg}")
def warn(msg): print(f"  {C.BYELLOW}!{C.RESET} {msg}")
def info(msg): print(f"  {C.BCYAN}i{C.RESET} {msg}")

def banner(title: str, subtitle: str = ""):
    w = 64
    print(f"{C.BMAGENTA}{TL}{H*(w-2)}{TR}{C.RESET}")
    print(f"{C.BMAGENTA}{V}{C.RESET} {C.BOLD}{C.BWHITE}{title:<{w-4}}{C.RESET}{C.BMAGENTA}{V}{C.RESET}")
    if subtitle:
        print(f"{C.BMAGENTA}{V}{C.RESET} {C.DIM}{subtitle:<{w-4}}{C.RESET}{C.BMAGENTA}{V}{C.RESET}")
    print(f"{C.BMAGENTA}{BL}{H*(w-2)}{BR}{C.RESET}")

def section(label: str):
    print(f"\n{C.BCYAN}{ML}{H*3} {C.BOLD}{label}{C.RESET} {C.BCYAN}{H*(56-len(label))}{C.RESET}")


# ───────────────────────────────────────────
# PATHS / CONFIG
# ───────────────────────────────────────────
CONFIG_FILE = Path.home() / ".film_kit_config.json"
PROJECTS_DIR = Path.home() / "film_kit_projects"
NIM_BASE = "https://integrate.api.nvidia.com/v1"
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_NIM_MODEL = "meta/llama-3.1-70b-instruct"

# A handful of OpenRouter's free-tier models, used only as fallback
# capacity if OPENROUTER_API_KEY is set — separate quota from NVIDIA,
# same idea as the fallback pool in nim_agent.py.
OPENROUTER_FREE_MODELS = [
    ("OpenRouter Llama-3.1-8B free", "meta-llama/llama-3.1-8b-instruct:free"),
    ("OpenRouter Gemma-2-9B free",   "google/gemma-2-9b-it:free"),
]

ASPECTS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1":  (1080, 1080),
}

# Curated free Edge-TTS voices (no key needed)
VOICES = {
    "aria":   "en-US-AriaNeural",
    "guy":    "en-US-GuyNeural",
    "jenny":  "en-US-JennyNeural",
    "sonia":  "en-GB-SoniaNeural",
    "ryan":   "en-GB-RyanNeural",
    "natasha":"en-AU-NatashaNeural",
}

def load_config() -> Dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg: Dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

def ensure_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None

def run(cmd: List[str], quiet: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=quiet, text=True)


# ───────────────────────────────────────────
# TOKEN BUCKET (lightweight RPM guard for the free LLM tier)
# ───────────────────────────────────────────
class TokenBucket:
    """Minimal adaptive RPM guard: targets 80% of the advertised
    ceiling and backs off hard on a 429, same spirit as the fuller
    version in nim_agent.py but trimmed to what a linear scripting
    pipeline (a handful of calls per film) actually needs."""
    def __init__(self, rpm: float = 20.0, min_gap: float = 2.0):
        self.rpm = max(1.0, rpm) * 0.8
        self.min_gap = min_gap
        self.last_call = 0.0

    def wait(self):
        gap = max(self.min_gap, 60.0 / self.rpm)
        elapsed = time.monotonic() - self.last_call
        if elapsed < gap:
            time.sleep(gap - elapsed)
        self.last_call = time.monotonic()

    def penalize(self):
        self.rpm = max(2.0, self.rpm * 0.5)


class TokenMeter:
    """Lightweight TPM/tok-s observer — no compaction logic needed
    here (this pipeline never accumulates a growing message history,
    each pool.chat() call is a fresh, short, fixed-size prompt), but
    it shares the same NVIDIA/OpenRouter quota as nim_agent.py, and a
    max_tokens=2000 call can still eat into a TPM cap even at low RPM.
    This just makes that visible."""
    def __init__(self):
        self.window = deque()  # (monotonic_ts, tokens) for the last 60s
        self.total_prompt = 0
        self.total_completion = 0

    def _prune(self):
        now = time.monotonic()
        while self.window and self.window[0][0] < now - 60.0:
            self.window.popleft()

    def record(self, prompt_tokens: int, completion_tokens: int):
        now = time.monotonic()
        self.window.append((now, prompt_tokens + completion_tokens))
        self.total_prompt += max(0, prompt_tokens)
        self.total_completion += max(0, completion_tokens)
        self._prune()

    def tpm(self) -> int:
        self._prune()
        return sum(t for _, t in self.window)

    def stats(self) -> str:
        return (f"{self.tpm()} TPM | lifetime: "
                f"{self.total_prompt}in/{self.total_completion}out tokens")


def estimate_tokens(text: Optional[str]) -> int:
    """Cheap ~4-chars/token estimate — the OpenAI-compatible endpoints
    used here don't reliably return usage counts, so this is close
    enough for pacing visibility."""
    if not text:
        return 0
    return max(1, len(text) // 4)


TOKEN_METER = TokenMeter()


class Provider:
    def __init__(self, name, base_url, api_key, model_id, rpm=20.0):
        self.name, self.base_url, self.model_id = name, base_url, model_id
        self.bucket = TokenBucket(rpm=rpm)
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=120) if HAS_OPENAI else None
        self.cooldown_until = 0.0

    def is_available(self) -> bool:
        return time.monotonic() >= self.cooldown_until

    def cooldown(self, secs=90.0):
        self.cooldown_until = time.monotonic() + secs


class ProviderPool:
    def __init__(self, providers: List[Provider]):
        if not providers:
            raise ValueError("Need at least one LLM provider (set a NIM API key).")
        self.providers = providers

    def next_available(self) -> Optional[Provider]:
        for p in self.providers:
            if p.is_available():
                return p
        return None

    def chat(self, messages, temperature=0.8, max_tokens=2000) -> str:
        last_exc = None
        for _ in range(len(self.providers) * 2):
            p = self.next_available()
            if p is None:
                time.sleep(5)
                continue
            p.bucket.wait()
            try:
                resp = p.client.chat.completions.create(
                    model=p.model_id, messages=messages,
                    temperature=temperature, max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content
                usage = getattr(resp, "usage", None)
                if usage:
                    TOKEN_METER.record(usage.prompt_tokens, usage.completion_tokens)
                else:
                    prompt_est = sum(estimate_tokens(m.get("content")) for m in messages)
                    TOKEN_METER.record(prompt_est, estimate_tokens(content))
                return content
            except Exception as e:
                last_exc = e
                msg = str(e).lower()
                if "429" in msg or "rate" in msg:
                    p.bucket.penalize()
                    p.cooldown(90.0)
                else:
                    p.cooldown(20.0)
        raise RuntimeError(f"All LLM providers failed. Last error: {last_exc}")


def build_provider_pool(cfg: Dict) -> ProviderPool:
    if not HAS_OPENAI:
        raise RuntimeError("Install the 'openai' package: pip install openai")
    providers = [Provider(
        name="NVIDIA NIM", base_url=NIM_BASE, api_key=cfg["nim_key"],
        model_id=cfg.get("model", DEFAULT_NIM_MODEL), rpm=cfg.get("rpm", 20.0),
    )]
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if or_key:
        for name, model_id in OPENROUTER_FREE_MODELS:
            providers.append(Provider(name, OPENROUTER_BASE, or_key, model_id, rpm=18.0))
    return ProviderPool(providers)


# ───────────────────────────────────────────
# SCENE / PROJECT MODEL
# ───────────────────────────────────────────
@dataclass
class Scene:
    index: int
    narration: str
    visual_prompt: str
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    clip_path: Optional[str] = None
    duration: Optional[float] = None


class Project:
    def __init__(self, name: str):
        self.name = name
        self.dir = PROJECTS_DIR / name
        for sub in ("images", "audio", "clips", "output"):
            (self.dir / sub).mkdir(parents=True, exist_ok=True)
        self.idea: str = ""
        self.style: str = "cinematic, warm lighting, detailed"
        self.aspect: str = "16:9"
        self.voice: str = "aria"
        self.seed: int = random.randint(0, 999_999)
        self.music: bool = False
        self.music_mood: str = "ambient"
        self.scenes: List[Scene] = []
        self.manifest_path = self.dir / "manifest.json"
        self.load()

    def save(self):
        data = {
            "idea": self.idea, "style": self.style, "aspect": self.aspect,
            "voice": self.voice, "seed": self.seed, "music": self.music,
            "music_mood": self.music_mood, "scenes": [asdict(s) for s in self.scenes],
        }
        self.manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self):
        if self.manifest_path.exists():
            try:
                data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                self.idea = data.get("idea", "")
                self.style = data.get("style", self.style)
                self.aspect = data.get("aspect", self.aspect)
                self.voice = data.get("voice", self.voice)
                self.seed = data.get("seed", self.seed)
                self.music = data.get("music", self.music)
                self.music_mood = data.get("music_mood", self.music_mood)
                self.scenes = [Scene(**s) for s in data.get("scenes", [])]
            except Exception:
                pass


# ───────────────────────────────────────────
# 1) SCRIPT / STORYBOARD  (free NIM LLM)
# ───────────────────────────────────────────
SCRIPT_SYSTEM_PROMPT = """You are a concise film storyboard writer.
Given a story idea, break it into a numbered sequence of short scenes.
Respond with ONLY a JSON array, no prose, no markdown fences. Each element:
{"narration": "1-2 sentence voiceover line for this scene",
 "visual_prompt": "a vivid, concrete text-to-image prompt describing exactly what is on screen"}
Keep narration lines short (under 25 words) since each is read aloud over one shot."""

def generate_script(pool: ProviderPool, idea: str, num_scenes: int, style: str) -> List[Scene]:
    user_prompt = (
        f"Story idea: {idea}\n"
        f"Visual style to weave into every visual_prompt: {style}\n"
        f"Produce exactly {num_scenes} scenes."
    )
    raw = pool.chat(
        [{"role": "system", "content": SCRIPT_SYSTEM_PROMPT},
         {"role": "user", "content": user_prompt}],
        temperature=0.85, max_tokens=1800,
    )
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"Could not find a JSON array in the model's response:\n{raw[:400]}")
    items = json.loads(match.group(0))
    scenes = []
    for i, item in enumerate(items):
        scenes.append(Scene(
            index=i,
            narration=item["narration"].strip(),
            visual_prompt=f"{item['visual_prompt'].strip()}, {style}",
        ))
    return scenes


# ───────────────────────────────────────────
# 2) IMAGES  (free, keyless — Pollinations.ai)
# ───────────────────────────────────────────
def generate_image(prompt: str, out_path: Path, width: int, height: int, seed: Optional[int] = None):
    q = urllib.parse.quote(prompt)
    seed = seed if seed is not None else random.randint(0, 999_999)
    url = (f"https://image.pollinations.ai/prompt/{q}"
           f"?width={width}&height={height}&nologo=true&seed={seed}")
    req = urllib.request.Request(url, headers={"User-Agent": "film-kit/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(out_path, "wb") as f:
        f.write(resp.read())


# ───────────────────────────────────────────
# 3) NARRATION  (free, keyless — edge-tts)
# ───────────────────────────────────────────
async def _synthesize(text: str, voice: str, out_path: Path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))

def synthesize_narration(text: str, voice_key: str, out_path: Path):
    if not HAS_EDGE_TTS:
        raise RuntimeError("Install narration support: pip install edge-tts")
    voice = VOICES.get(voice_key, voice_key)
    asyncio.run(_synthesize(text, voice, out_path))


# ───────────────────────────────────────────
# 4) KEN BURNS CLIPS + STITCHING  (ffmpeg)
# ───────────────────────────────────────────
def probe_duration(path: Path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
              "-of", "default=noprint_wrappers=1:nokey=1", str(path)])
    try:
        return max(0.5, float(p.stdout.strip()))
    except Exception:
        return 4.0

def build_ken_burns_clip(image_path: Path, duration: float, out_path: Path,
                          size, fps: int = 30, zoom_in: bool = True):
    w, h = size
    frames = max(1, int(duration * fps))
    z_expr = "min(zoom+0.0015,1.4)" if zoom_in else "if(eq(on,1),1.4,max(zoom-0.0015,1.0))"
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-vf", f"scale={w*3}:-1,zoompan=z='{z_expr}':d={frames}:s={w}x{h}:fps={fps},format=yuv420p",
        "-t", f"{duration:.2f}", "-pix_fmt", "yuv420p", str(out_path),
    ]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg (ken burns) failed for {image_path.name}:\n{p.stderr[-800:]}")

def mux_audio(video_path: Path, audio_path: Path, out_path: Path):
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(audio_path),
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_path)]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg (mux audio) failed:\n{p.stderr[-800:]}")

def stitch_concat(clip_paths: List[Path], out_path: Path):
    """Fast path: hard cuts, no re-encode (all clips share codec/res/fps)."""
    list_file = out_path.parent / "_concat_list.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in clip_paths), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)]
    p = run(cmd)
    list_file.unlink(missing_ok=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg (concat) failed:\n{p.stderr[-800:]}")

def stitch_crossfade(clip_paths: List[Path], out_path: Path, trans_dur: float = 0.75):
    """Slower path: xfade/acrossfade chain for smooth dissolve transitions."""
    durations = [probe_duration(p) for p in clip_paths]
    n = len(clip_paths)
    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]
    parts, prev_v, prev_a = [], "0:v", "0:a"
    cum = durations[0]
    for i in range(1, n):
        td = min(trans_dur, durations[i - 1] - 0.1, durations[i] - 0.1)
        td = max(0.2, td)
        offset = cum - td
        vlab, alab = f"v{i}", f"a{i}"
        parts.append(f"[{prev_v}][{i}:v]xfade=transition=fade:duration={td:.2f}:offset={offset:.2f}[{vlab}]")
        parts.append(f"[{prev_a}][{i}:a]acrossfade=d={td:.2f}[{alab}]")
        prev_v, prev_a = vlab, alab
        cum += durations[i] - td
    filter_complex = ";".join(parts)
    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", filter_complex,
           "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
           "-c:v", "libx264", "-preset", "medium", "-c:a", "aac", str(out_path)]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg (crossfade stitch) failed:\n{p.stderr[-1200:]}")

def write_srt(scenes: List[Scene], out_path: Path):
    lines, t = [], 0.0
    def fmt(sec):
        h_, rem = divmod(sec, 3600); m_, s_ = divmod(rem, 60)
        return f"{int(h_):02}:{int(m_):02}:{s_:06.3f}".replace(".", ",")
    for i, s in enumerate(scenes, 1):
        dur = s.duration or 4.0
        lines.append(str(i))
        lines.append(f"{fmt(t)} --> {fmt(t + dur)}")
        lines.append(s.narration)
        lines.append("")
        t += dur
    out_path.write_text("\n".join(lines), encoding="utf-8")


# Ambient music beds are synthesized locally with ffmpeg's own signal
# generators (detuned sine drones + filtered noise) rather than pulled
# from a "free music API" — no such API is reliable enough (rate
# limits, attribution terms, catalog gaps) to depend on unattended,
# and this sidesteps licensing risk entirely.
MUSIC_MOODS = ["ambient", "tense", "bright"]

def generate_ambient_bed(duration: float, out_path: Path, mood: str = "ambient"):
    """Two slow, detuned sine drones + a hint of filtered noise, faded
    in/out, mixed down to a quiet stereo pad `duration` seconds long."""
    freqs = {"ambient": (110, 165), "tense": (98, 104), "bright": (220, 330)}
    f1, f2 = freqs.get(mood, freqs["ambient"])
    filt = (
        f"sine=frequency={f1}:duration={duration:.2f}[a];"
        f"sine=frequency={f2}:duration={duration:.2f}[b];"
        f"anoisesrc=color=pink:duration={duration:.2f}:amplitude=0.05[n];"
        f"[a][b]amix=inputs=2:weights=1 0.6[ab];"
        f"[ab][n]amix=inputs=2:weights=1 0.3,"
        f"lowpass=f=600,"
        f"afade=t=in:d=2,afade=t=out:st={max(0,duration-2):.2f}:d=2,"
        f"volume=0.18[out]"
    )
    cmd = ["ffmpeg", "-y", "-filter_complex", filt, "-map", "[out]",
           "-t", f"{duration:.2f}", str(out_path)]
    p = run(cmd)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg (ambient bed) failed:\n{p.stderr[-800:]}")

def mix_music_under(video_path: Path, out_path: Path, mood: str = "ambient"):
    duration = probe_duration(video_path)
    bed = video_path.parent / "_music_bed.aac"
    generate_ambient_bed(duration, bed, mood)
    cmd = ["ffmpeg", "-y", "-i", str(video_path), "-i", str(bed),
           "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=1 1[a]",
           "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", str(out_path)]
    p = run(cmd)
    bed.unlink(missing_ok=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg (music mix) failed:\n{p.stderr[-800:]}")


# ───────────────────────────────────────────
# PIPELINE STEPS (CLI-facing)
# ───────────────────────────────────────────
def step_script(proj: Project, pool: ProviderPool, num_scenes: int):
    section("Writing script")
    if not proj.idea:
        err("No idea set. Use /idea <your story idea> first."); return
    info(f"Asking the free LLM for {num_scenes} scenes...")
    proj.scenes = generate_script(pool, proj.idea, num_scenes, proj.style)
    proj.save()
    ok(f"Got {len(proj.scenes)} scenes.")
    info(f"Tokens: {TOKEN_METER.stats()}")
    for s in proj.scenes:
        print(f"  {C.DIM}[{s.index}]{C.RESET} {C.BWHITE}{s.narration}{C.RESET}")

def step_images(proj: Project):
    section("Generating storyboard images (Pollinations.ai)")
    if not proj.scenes:
        err("No scenes yet. Run /script first."); return
    w, h = ASPECTS[proj.aspect]
    info(f"Using a fixed seed ({proj.seed}) across all scenes for a consistent look. "
         f"Note: Pollinations has no image-to-image reference, so recurring characters/props "
         f"may still drift — mention them explicitly in /style if they need to recur.")
    for s in proj.scenes:
        out = proj.dir / "images" / f"scene_{s.index:02}.jpg"
        try:
            generate_image(s.visual_prompt, out, w // 2, h // 2, seed=proj.seed)
            s.image_path = str(out)
            ok(f"scene {s.index}: {out.name}")
        except Exception as e:
            err(f"scene {s.index} image failed: {e}")
    proj.save()

def step_voice(proj: Project, voice_key: str):
    section(f"Synthesizing narration (edge-tts, voice={voice_key})")
    if not proj.scenes:
        err("No scenes yet. Run /script first."); return
    proj.voice = voice_key
    for s in proj.scenes:
        out = proj.dir / "audio" / f"scene_{s.index:02}.mp3"
        try:
            synthesize_narration(s.narration, voice_key, out)
            s.audio_path = str(out)
            s.duration = probe_duration(out) + 0.4  # small pad so Ken Burns isn't cut off
            ok(f"scene {s.index}: {s.duration:.1f}s")
        except Exception as e:
            err(f"scene {s.index} narration failed: {e}")
    proj.save()

def step_clips(proj: Project):
    section("Building Ken Burns clips (ffmpeg)")
    if not ensure_ffmpeg():
        err("ffmpeg/ffprobe not found on PATH. Install ffmpeg first."); return
    size = ASPECTS[proj.aspect]
    for s in proj.scenes:
        if not (s.image_path and s.audio_path):
            warn(f"scene {s.index} missing image or audio, skipping"); continue
        raw = proj.dir / "clips" / f"raw_{s.index:02}.mp4"
        final = proj.dir / "clips" / f"scene_{s.index:02}.mp4"
        try:
            build_ken_burns_clip(Path(s.image_path), s.duration, raw, size,
                                  zoom_in=(s.index % 2 == 0))
            mux_audio(raw, Path(s.audio_path), final)
            raw.unlink(missing_ok=True)
            s.clip_path = str(final)
            ok(f"scene {s.index}: {final.name}")
        except Exception as e:
            err(f"scene {s.index} clip failed: {e}")
    proj.save()

def step_stitch(proj: Project, mode: str):
    section(f"Stitching final film ({mode})")
    clips = [Path(s.clip_path) for s in proj.scenes if s.clip_path]
    if not clips:
        err("No clips built yet. Run /clips first."); return
    out = proj.dir / "output" / f"{proj.name}.mp4"
    try:
        if mode == "crossfade":
            stitch_crossfade(clips, out)
        else:
            stitch_concat(clips, out)
        if proj.music:
            info(f"Mixing in a synthesized '{proj.music_mood}' ambient bed...")
            with_music = proj.dir / "output" / f"{proj.name}_music.mp4"
            mix_music_under(out, with_music, proj.music_mood)
            with_music.replace(out)
            ok("Music mixed in (quiet, under the narration).")
        write_srt(proj.scenes, proj.dir / "output" / f"{proj.name}.srt")
        ok(f"Final film: {out}")
        ok(f"Subtitles:  {proj.dir / 'output' / (proj.name + '.srt')}")
    except Exception as e:
        err(f"Stitching failed: {e}")

def step_render_all(proj: Project, pool: ProviderPool, num_scenes: int, mode: str):
    step_script(proj, pool, num_scenes)
    if proj.scenes:
        step_images(proj)
        step_voice(proj, proj.voice)
        step_clips(proj)
        step_stitch(proj, mode)


# ───────────────────────────────────────────
# FIRST-RUN SETUP
# ───────────────────────────────────────────
def first_run_setup() -> Dict:
    cfg = load_config()
    if cfg.get("nim_key"):
        return cfg
    banner("Film Kit — first-time setup", "Free NVIDIA NIM key needed for script writing")
    print(f"  {C.DIM}Get a free key at https://build.nvidia.com → API Keys{C.RESET}")
    key = input(f"  {C.BYELLOW}Paste your NVIDIA NIM API key: {C.RESET}").strip()
    cfg = {"nim_key": key, "model": DEFAULT_NIM_MODEL, "rpm": 20.0}
    save_config(cfg)
    ok("Saved to ~/.film_kit_config.json")
    return cfg


# ───────────────────────────────────────────
# CLI
# ───────────────────────────────────────────
HELP = f"""
{C.BOLD}Pipeline commands{C.RESET}
  {C.BYELLOW}/project <name>{C.RESET}        create/open a project
  {C.BYELLOW}/idea <text>{C.RESET}           set the story idea
  {C.BYELLOW}/style <text>{C.RESET}          set the visual style (default: cinematic, warm lighting)
  {C.BYELLOW}/aspect <16:9|9:16|1:1>{C.RESET} set frame aspect ratio (default 16:9)
  {C.BYELLOW}/seed [reroll]{C.RESET}         show/reroll the image seed (kept fixed for style consistency)
  {C.BYELLOW}/music <on|off> [mood]{C.RESET}  toggle synthesized ambient music ({', '.join(MUSIC_MOODS)})
  {C.BYELLOW}/script [n]{C.RESET}            generate an n-scene script (default 6)
  {C.BYELLOW}/images{C.RESET}                generate a storyboard image per scene
  {C.BYELLOW}/voice [name]{C.RESET}          synthesize narration ({', '.join(VOICES)})
  {C.BYELLOW}/clips{C.RESET}                 render each scene into a Ken Burns video clip
  {C.BYELLOW}/stitch [cut|crossfade]{C.RESET} stitch clips into the final film (default cut)
  {C.BYELLOW}/render [n] [cut|crossfade]{C.RESET} run the whole pipeline end to end
  {C.BYELLOW}/status{C.RESET}                show project status
  {C.BYELLOW}/voices{C.RESET}                list narration voices
  {C.BYELLOW}/help{C.RESET}  {C.BYELLOW}/quit{C.RESET}
"""

def print_status(proj: Project):
    section("Project status")
    print(f"  {C.DIM}name:{C.RESET}   {proj.name}")
    print(f"  {C.DIM}idea:{C.RESET}   {proj.idea or '(not set)'}")
    print(f"  {C.DIM}style:{C.RESET}  {proj.style}")
    print(f"  {C.DIM}aspect:{C.RESET} {proj.aspect}")
    print(f"  {C.DIM}voice:{C.RESET}  {proj.voice}")
    print(f"  {C.DIM}scenes:{C.RESET} {len(proj.scenes)}")
    for s in proj.scenes:
        flags = "".join([
            "🖼" if s.image_path else "·",
            "🔊" if s.audio_path else "·",
            "🎬" if s.clip_path else "·",
        ])
        print(f"    [{s.index}] {flags}  {s.narration[:60]}")

def parse_args():
    p = argparse.ArgumentParser(
        description="Film Kit — free-tier AI filmmaking pipeline. "
                     "Run with no arguments for the interactive REPL, "
                     "or pass --idea for a scripted, non-interactive run of the full pipeline."
    )
    p.add_argument("--project", help="project name (default: my_film)")
    p.add_argument("--idea", help="story idea; if given, batch mode is used instead of the REPL")
    p.add_argument("--style", default="cinematic, warm lighting, detailed")
    p.add_argument("--aspect", choices=list(ASPECTS), default="16:9")
    p.add_argument("--voice", choices=list(VOICES), default="aria")
    p.add_argument("--scenes", type=int, default=6)
    p.add_argument("--mode", choices=["cut", "crossfade"], default="cut")
    p.add_argument("--music", action="store_true", help="mix in synthesized ambient music")
    p.add_argument("--music-mood", choices=MUSIC_MOODS, default="ambient")
    p.add_argument("--seed", type=int, help="fixed image seed (default: random per project)")
    p.add_argument("--key", help="NVIDIA NIM API key (skips the first-run prompt / overwrites saved key)")
    return p.parse_args()

def run_batch(args) -> int:
    """Non-interactive: build one project end to end from CLI flags and exit.
    Returns a process exit code."""
    banner("🎬 Film Kit — batch mode", "idea → script → images → narration → Ken Burns → stitched film")
    if not HAS_OPENAI:
        err("pip install openai   (needed for script writing)"); return 1
    if not HAS_EDGE_TTS:
        err("pip install edge-tts   (needed for narration)"); return 1
    if not ensure_ffmpeg():
        err("ffmpeg/ffprobe not found on PATH   (needed for clips + stitching)"); return 1

    cfg = load_config()
    if args.key:
        cfg["nim_key"] = args.key
        cfg.setdefault("model", DEFAULT_NIM_MODEL)
        cfg.setdefault("rpm", 20.0)
        save_config(cfg)
    if not cfg.get("nim_key"):
        err("No NIM API key found. Pass --key <key> or run once without --idea to set it up.")
        return 1

    try:
        pool = build_provider_pool(cfg)
    except Exception as e:
        err(f"LLM pool not ready: {e}"); return 1

    proj = Project(args.project or "my_film")
    proj.idea, proj.style, proj.aspect, proj.voice = args.idea, args.style, args.aspect, args.voice
    proj.music, proj.music_mood = args.music, args.music_mood
    if args.seed is not None:
        proj.seed = args.seed
    proj.save()
    ok(f"Project ready at {proj.dir}")

    step_render_all(proj, pool, args.scenes, args.mode)
    return 0 if proj.scenes and all(s.clip_path for s in proj.scenes) else 1


def main():
    args = parse_args()
    if args.idea:
        sys.exit(run_batch(args))

    banner("🎬 Film Kit", "idea → script → images → narration → Ken Burns → stitched film")
    if not HAS_OPENAI:
        warn("pip install openai   (needed for script writing)")
    if not HAS_EDGE_TTS:
        warn("pip install edge-tts   (needed for narration)")
    if not ensure_ffmpeg():
        warn("ffmpeg/ffprobe not found on PATH   (needed for clips + stitching)")

    cfg = first_run_setup()
    if args.key:
        cfg["nim_key"] = args.key
        save_config(cfg)
    pool = None
    try:
        pool = build_provider_pool(cfg)
    except Exception as e:
        warn(f"LLM pool not ready ({e}) — /script will fail until fixed.")

    proj_name = args.project or (input(f"\n  {C.BYELLOW}Project name [my_film]: {C.RESET}").strip() or "my_film")
    proj = Project(proj_name)
    ok(f"Project ready at {proj.dir}")
    print(HELP)

    while True:
        try:
            raw = input(f"{C.BMAGENTA}{ARROW}{C.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not raw:
            continue
        if raw in ("/quit", "/exit"):
            break
        elif raw == "/help":
            print(HELP)
        elif raw == "/status":
            print_status(proj)
        elif raw == "/voices":
            for k, v in VOICES.items():
                print(f"  {C.BYELLOW}{k:<10}{C.RESET} {C.DIM}{v}{C.RESET}")
        elif raw.startswith("/project "):
            proj = Project(raw[9:].strip())
            ok(f"Switched to project '{proj.name}'")
        elif raw.startswith("/idea "):
            proj.idea = raw[6:].strip(); proj.save(); ok("Idea set.")
        elif raw.startswith("/style "):
            proj.style = raw[7:].strip(); proj.save(); ok("Style set.")
        elif raw.startswith("/aspect "):
            a = raw[8:].strip()
            if a in ASPECTS:
                proj.aspect = a; proj.save(); ok(f"Aspect set to {a}")
            else:
                err(f"Choose one of: {', '.join(ASPECTS)}")
        elif raw.startswith("/seed"):
            parts = raw.split()
            if len(parts) > 1 and parts[1] == "reroll":
                proj.seed = random.randint(0, 999_999); proj.save()
                ok(f"New seed: {proj.seed} (re-run /images to apply)")
            else:
                info(f"Current seed: {proj.seed}")
        elif raw.startswith("/music"):
            parts = raw.split()
            if len(parts) > 1 and parts[1] in ("on", "off"):
                proj.music = (parts[1] == "on")
                if len(parts) > 2 and parts[2] in MUSIC_MOODS:
                    proj.music_mood = parts[2]
                proj.save()
                ok(f"Music {'on' if proj.music else 'off'} (mood: {proj.music_mood})")
            else:
                err(f"Usage: /music <on|off> [{'|'.join(MUSIC_MOODS)}]")
        elif raw.startswith("/script"):
            parts = raw.split()
            n = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 6
            if pool is None:
                err("LLM pool unavailable — check your NIM key.")
            else:
                step_script(proj, pool, n)
        elif raw == "/images":
            step_images(proj)
        elif raw.startswith("/voice"):
            parts = raw.split()
            vk = parts[1] if len(parts) > 1 else proj.voice
            step_voice(proj, vk)
        elif raw == "/clips":
            step_clips(proj)
        elif raw.startswith("/stitch"):
            parts = raw.split()
            mode = parts[1] if len(parts) > 1 else "cut"
            step_stitch(proj, mode)
        elif raw.startswith("/render"):
            parts = raw.split()
            n = 6; mode = "cut"
            for p in parts[1:]:
                if p.isdigit(): n = int(p)
                elif p in ("cut", "crossfade"): mode = p
            if pool is None:
                err("LLM pool unavailable — check your NIM key.")
            else:
                step_render_all(proj, pool, n, mode)
        else:
            warn("Unknown command. Type /help.")

    ok("Bye — project saved.")

if __name__ == "__main__":
    main()