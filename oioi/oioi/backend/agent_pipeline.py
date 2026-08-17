"""Real 7-agent animation pipeline.

This orchestrator performs genuine generation:
  1. Scriptwriter      — LLM -> structured JSON screenplay (scenes, characters, dialogue)
  2. Art Director      — LLM -> shot list, camera moves, style directives
  3. Character Designer— LLM descriptions + image model -> character sheets (downloaded locally)
  4. Scene Designer    — LLM descriptions + image model -> environment panels
  5. Storyboard Artist — per-shot framing + image model -> storyboard frames
  6. Animator          — ffmpeg Ken Burns motion -> real MP4 clip per shot
  7. Sound Director    — numpy-synthesized mood score -> real audio track
  8. Director          — ffmpeg concat + audio mux -> final MP4, project status complete

Every stage persists an agent_runs row and emits events through an optional
async event sink (used by the SSE endpoint). Provider calls route through the
ProviderRegistry with failover. The legacy synchronous `run_pipeline` below is
retained as an offline fallback (no network) for tests and degraded mode.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import struct
import time
import uuid
import wave
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.core import db
from app.core.config import settings
from app.services import media

AGENT_ROLES = [
    'Scriptwriter',
    'Art Director',
    'Character Designer',
    'Scene Designer',
    'Animator',
    'Sound Director',
    'Director',
]

AGENT_KEYS = [
    'scriptwriter', 'art_director', 'character_designer', 'scene_designer',
    'storyboard_artist', 'animator', 'sound_director', 'director',
]

DEFAULT_CHAT_MODEL = getattr(settings, "DEFAULT_CHAT_MODEL", "google/gemma-4-26b-a4b-it:free")
DEFAULT_IMAGE_MODEL = getattr(settings, "DEFAULT_IMAGE_MODEL", "flux")
SHOTS_PER_SCENE = getattr(settings, "SHOTS_PER_SCENE", 2)
MAX_CONCURRENT_IMAGES = getattr(settings, "MAX_CONCURRENT_IMAGES", 2)
CLIP_SECONDS = getattr(settings, "CLIP_SECONDS", 3)
FRAME_FPS = getattr(settings, "FRAME_FPS", 24)

# Provider name -> default chat model id (free tier, verified live).
CHAT_MODEL_BY_PROVIDER = {
    "openrouter": "google/gemma-4-26b-a4b-it:free",
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.5-flash",
    "cerebras": "llama-3.3-70b",
    "cohere": "command-r",
    "cloudflare": "@cf/meta/llama-3.3-70b-instruct-fp8-fast",
}

# Ordered fallback chain per provider. Free-tier upstreams rotate model
# availability and rate limits constantly, so a single pinned model is not
# reliable; each entry is tried in order until one succeeds. All models are
# served through the provider's own API (OpenRouter marketplace slugs here) —
# no banned provider platform is ever involved (AC-10).
CHAT_MODELS_BY_PROVIDER = {
    "openrouter": [
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-small-3.2-24b-instruct:free",
        "dots-studio/dots-3-note-preview:free",
        "cohere/north-mini-code:free",
        "poolside/laguna-xs-2.1:free",
        "liquid/lfm-2.5-2.6b:free",
    ],
    "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
    "gemini": ["gemini-2.5-flash", "gemini-2.0-flash"],
    "cerebras": ["llama-3.3-70b"],
    "cohere": ["command-r"],
    "cloudflare": ["@cf/meta/llama-3.3-70b-instruct-fp8-fast"],
}


def chat_models_for(provider_name: str) -> List[str]:
    """Ordered chat model candidates for a provider (primary first)."""
    models = CHAT_MODELS_BY_PROVIDER.get(provider_name)
    if models:
        return list(models)
    return [DEFAULT_CHAT_MODEL]

EventSink = Callable[[Dict[str, Any]], Awaitable[None]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def extract_json(text: str) -> Optional[Any]:
    """Robustly extract the first JSON object/array from LLM output."""
    if not text:
        return None
    text = text.strip()
    # Strip markdown fences.
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == opener:
                depth += 1
            elif text[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break
    return None


async def call_chat_with_failover(registry, messages: List[Dict[str, str]],
                                  temperature: float = 0.7,
                                  max_tokens: int = 2048) -> Dict[str, Any]:
    """Call a chat provider with automatic failover across the registry.

    Each provider is tried with its full model fallback chain (free-tier
    upstreams rate-limit individual models constantly); the provider is only
    marked failed in the registry when every candidate model fails.

    Returns {"content": str, "provider": str, "model": str}.
    """
    from providers.base import ChatCompletionRequest

    errors: List[str] = []
    candidates = registry._candidates("chat")
    if not candidates:
        raise RuntimeError("No chat provider available")
    for rec in candidates:
        adapter = await registry.get_adapter("chat", prefer=rec.name)
        name = getattr(adapter, "provider_name", rec.name) or rec.name
        for model in chat_models_for(name):
            req = ChatCompletionRequest(
                model=model, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
            )
            started = time.monotonic()
            try:
                resp = await asyncio.wait_for(adapter.chat_completion(req), timeout=120)
                latency = (time.monotonic() - started) * 1000
                registry.report_success(name, latency)
                data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
                content = data["choices"][0]["message"]["content"]
                return {"content": content, "provider": name, "model": model}
            except Exception as exc:
                errors.append(f"{name}/{model}: {exc}")
        registry.report_failure(name, errors[-1] if errors else "all models failed")
    raise RuntimeError("All chat providers failed: " + " | ".join(errors))


def extract_image_url(resp: Any) -> str:
    """Extract an image URL from an adapter response of any shape."""
    if isinstance(resp, str):
        return resp
    data = resp.model_dump() if hasattr(resp, "model_dump") else (
        dict(resp) if isinstance(resp, dict) else getattr(resp, "__dict__", {})
    )
    items = data.get("data") if isinstance(data, dict) else None
    if items and isinstance(items, list):
        first = items[0]
        if isinstance(first, dict):
            return first.get("url", "") or first.get("b64_json", "")
        return str(first)
    return ""


async def generate_image_with_failover(registry, prompt: str, size: str = "1280x720",
                                       timeout: int = 90,
                                       require_local: bool = True,
                                       attempts: int = 3) -> Dict[str, Any]:
    """Generate an image via the registry and download it to local storage.

    Returns {"uri": "/media/...", "provider": str, "model": str}.
    Each provider gets `attempts` tries with jittered backoff (free-tier image
    APIs like Pollinations throttle bursts of concurrent requests), walking the
    full candidate list on every attempt. With require_local=False, a failed
    download falls back to returning the remote source URL instead of failing
    over (useful for direct display).
    """
    import random
    from providers.base import ImageGenerationRequest

    errors: List[str] = []
    candidates = registry._candidates("image")
    if not candidates:
        raise RuntimeError("No image provider available")
    for attempt in range(attempts):
        for rec in candidates:
            adapter = await registry.get_adapter("image", prefer=rec.name)
            name = getattr(adapter, "provider_name", rec.name) or rec.name
            model = "flux" if name == "pollinations" else DEFAULT_IMAGE_MODEL
            req = ImageGenerationRequest(prompt=prompt, model=model, size=size)
            try:
                resp = await asyncio.wait_for(adapter.generate_image(req), timeout=timeout)
                url = extract_image_url(resp)
                if not url:
                    raise RuntimeError("empty image url")
                # Download to durable local storage.
                uri = await media.download_image(url, prefix="gen", timeout=timeout)
                if uri:
                    registry.report_success(name)
                    return {"uri": uri, "provider": name, "model": model, "source_url": url,
                            "local": True}
                if not require_local:
                    registry.report_success(name)
                    return {"uri": url, "provider": name, "model": model, "source_url": url,
                            "local": False}
                raise RuntimeError("image download failed")
            except Exception as exc:
                registry.report_failure(name, str(exc))
                errors.append(f"{name}[try{attempt + 1}]: {exc}")
        # Back off before the next full sweep (0.8s, 2.4s, ...) with jitter so
        # concurrent pipeline stages don't hammer the free tier in lockstep.
        if attempt < attempts - 1:
            await asyncio.sleep(0.8 * (3 ** attempt) + random.uniform(0, 0.5))
    raise RuntimeError("All image providers failed: " + " | ".join(errors[-6:]))


def _style_suffix(style_id: str, styles_by_id: Dict[str, Any]) -> str:
    style = styles_by_id.get(style_id)
    if style:
        return style.get("promptSuffix", "")
    return ""


# ---------------------------------------------------------------------------
# Sound synthesis (offline, real audio)
# ---------------------------------------------------------------------------
def synthesize_score(seconds: float, mood: str = "hopeful", out_prefix: str = "score") -> Optional[str]:
    """Synthesize a simple ambient music track (chord pad + slow arpeggio) as WAV."""
    try:
        import numpy as np
    except Exception:
        return None
    sr = 44100
    n = int(seconds * sr)
    if n <= 0:
        return None
    t = np.linspace(0, seconds, n, endpoint=False, dtype=np.float64)

    # Mood -> chord (frequencies in Hz)
    chords = {
        "hopeful": [261.63, 329.63, 392.00, 523.25],   # Cmaj7
        "tense":   [220.00, 261.63, 311.13, 415.30],   # Am-ish dark
        "mystic":  [293.66, 349.23, 440.00, 523.25],   # Dm7 lift
        "joyful":  [261.63, 329.63, 392.00, 493.88],   # Cmaj9
        "sad":     [220.00, 261.63, 329.63, 440.00],
    }
    freqs = chords.get(mood, chords["hopeful"])

    sig = np.zeros(n, dtype=np.float64)
    for i, f in enumerate(freqs):
        # Slow amplitude LFO per voice for movement.
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * (0.07 + 0.03 * i) * t)
        sig += 0.22 * lfo * np.sin(2 * np.pi * f * t)
        sig += 0.06 * np.sin(2 * np.pi * (f * 2) * t)  # octave shimmer

    # Gentle arpeggio plucks
    arp = freqs * 2
    step = 0.5
    for k in range(int(seconds / step)):
        f = arp[k % len(arp)]
        start = int(k * step * sr)
        dur = int(0.45 * sr)
        end = min(start + dur, n)
        seg = t[start:end] - t[start]
        env = np.exp(-seg * 4.0)
        sig[start:end] += 0.12 * env * np.sin(2 * np.pi * f * seg)

    # Fade in/out
    fade = int(1.2 * sr)
    if n > 2 * fade:
        sig[:fade] *= np.linspace(0, 1, fade)
        sig[-fade:] *= np.linspace(1, 0, fade)

    peak = np.max(np.abs(sig)) or 1.0
    sig = 0.85 * sig / peak
    pcm = (sig * 32767).astype("<i2").tobytes()

    fname = f"{out_prefix}_{uuid.uuid4().hex[:12]}.wav"
    path = os.path.join(media.media_dir(), fname)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return media.public_uri(fname)


# ---------------------------------------------------------------------------
# The real orchestrator
# ---------------------------------------------------------------------------
class RealAgentPipeline:
    """Runs the 7-agent team with real provider calls and persistence."""

    def __init__(self, registry, project_id: str, user_id: str,
                 event_sink: Optional[EventSink] = None):
        self.registry = registry
        self.project_id = project_id
        self.user_id = user_id
        self.emit = event_sink
        self._styles_by_id: Dict[str, Any] = {}

    # -- events ------------------------------------------------------------
    async def _emit(self, type_: str, **data: Any) -> None:
        if self.emit:
            try:
                await self.emit({"type": type_, "ts": time.time(), **data})
            except Exception:
                pass

    async def _run_agent(self, agent: str, coro_factory: Callable[[], Awaitable[Dict[str, Any]]]) -> Dict[str, Any]:
        run_id = await db.create_agent_run(self.project_id, agent)
        await db.update_agent_run(run_id, status="running")
        await self._emit("agent.status", agent=agent, status="working", run_id=run_id)
        try:
            output = await coro_factory()
            await db.update_agent_run(run_id, status="completed", output=output)
            await self._emit("agent.status", agent=agent, status="complete", run_id=run_id)
            return output
        except Exception as exc:
            await db.update_agent_run(run_id, status="failed", error=str(exc))
            await self._emit("agent.status", agent=agent, status="failed", error=str(exc))
            raise

    def _load_styles(self) -> None:
        try:
            from styles_registry import STYLES
            self._styles_by_id = {s["id"]: s for s in STYLES}
        except Exception:
            self._styles_by_id = {}

    # -- stages ------------------------------------------------------------
    async def _scriptwriter(self, idea: str, duration: int) -> Dict[str, Any]:
        sysmsg = (
            "You are the Scriptwriter agent of an animation studio. "
            "Write a short animated film script. Respond with ONLY valid JSON, no prose, matching exactly:\n"
            '{"title": str, "logline": str, "mood": str, "characters": [{"name": str, "role": str, "description": str}], '
            '"scenes": [{"index": int, "name": str, "beat": str, "description": str, "mood": str, '
            '"characters_present": [str], "dialogue": str, "duration_seconds": int}]}\n'
            f"Use 2-4 scenes, 1-3 characters. Total duration about {duration}s. Keep descriptions vivid and visual."
        )
        res = await call_chat_with_failover(
            self.registry,
            [{"role": "system", "content": sysmsg}, {"role": "user", "content": f"Story idea: {idea}"}],
            temperature=0.8, max_tokens=1500,
        )
        parsed = extract_json(res["content"])
        if not parsed or "scenes" not in parsed:
            # Fallback structure so the pipeline never dies on a bad parse.
            parsed = {
                "title": idea[:60], "logline": idea, "mood": "hopeful",
                "characters": [{"name": "Hero", "role": "protagonist", "description": idea}],
                "scenes": [{"index": 1, "name": "Opening", "beat": "beginning",
                            "description": idea, "mood": "hopeful",
                            "characters_present": ["Hero"], "dialogue": "", "duration_seconds": 5}],
            }
        parsed["_provider"] = res["provider"]
        parsed["_model"] = res["model"]
        await db.create_asset(self.project_id, self.user_id, "script", "Screenplay",
                              uri="", prompt=idea, model_id=res["model"], provider=res["provider"],
                              metadata=parsed)
        await self._emit("agent.artifact", agent="scriptwriter", kind="script",
                         title=parsed.get("title", ""))
        return parsed

    async def _art_director(self, script: Dict[str, Any], style_id: str) -> Dict[str, Any]:
        style = self._styles_by_id.get(style_id, {})
        sysmsg = (
            "You are the Art Director agent. Given a script, produce visual direction. "
            "Respond with ONLY valid JSON:\n"
            '{"palette": [str,...], "lighting": str, "camera_language": str, '
            '"shots": [{"scene_index": int, "shot_index": int, "framing": str, "camera_move": str, "focus": str}]}\n'
            "Provide exactly 2 shots per scene."
        )
        user = json.dumps({"script": {k: script.get(k) for k in ("title", "logline", "scenes")},
                           "style": style.get("name", style_id or "cinematic anime")}, default=str)
        res = await call_chat_with_failover(
            self.registry,
            [{"role": "system", "content": sysmsg}, {"role": "user", "content": user}],
            temperature=0.6, max_tokens=1500,
        )
        parsed = extract_json(res["content"]) or {}
        if "shots" not in parsed:
            parsed["shots"] = [
                {"scene_index": s.get("index", i + 1), "shot_index": k + 1,
                 "framing": "wide establishing" if k == 0 else "medium close-up",
                 "camera_move": "slow pan right" if k == 0 else "push in",
                 "focus": s.get("description", "")[:80]}
                for i, s in enumerate(script.get("scenes", [])) for k in range(SHOTS_PER_SCENE)
            ]
        parsed["_provider"] = res["provider"]
        parsed["_model"] = res["model"]
        return parsed

    async def _character_designer(self, script: Dict[str, Any], style_id: str) -> List[Dict[str, Any]]:
        suffix = _style_suffix(style_id, self._styles_by_id)
        chars = script.get("characters", [])[:3] or [
            {"name": "Hero", "role": "protagonist", "description": script.get("logline", "a hero")}
        ]
        sem = asyncio.Semaphore(MAX_CONCURRENT_IMAGES)
        out: List[Dict[str, Any]] = []

        async def design(c: Dict[str, Any]) -> Dict[str, Any]:
            prompt = (
                f"character design sheet of {c.get('name','character')}, {c.get('description','')}, "
                f"full body, front view, expressive face, clean background, high quality{suffix}"
            )
            async with sem:
                img = await generate_image_with_failover(self.registry, prompt, size="1024x1024")
            character_id = f"char_{uuid.uuid4().hex[:8]}"
            asset = await db.create_asset(
                self.project_id, self.user_id, "character", c.get("name", "Character"),
                uri=img["uri"], prompt=prompt, model_id=img["model"], provider=img["provider"],
                metadata={"character_id": character_id, "role": c.get("role", ""),
                          "face_lock": True, "description": c.get("description", "")},
            )
            await self._emit("agent.artifact", agent="character_designer", kind="character",
                             name=c.get("name"), uri=img["uri"])
            return {"character_id": character_id, "name": c.get("name"), "role": c.get("role"),
                    "description": c.get("description"), "image_uri": img["uri"],
                    "provider": img["provider"], "model": img["model"], "asset_id": asset["id"]}

        results = await asyncio.gather(*[design(c) for c in chars], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                await self._emit("agent.warning", agent="character_designer", error=str(r))
            else:
                out.append(r)
        if not out:
            raise RuntimeError("Character Designer produced no images")
        return out

    async def _scene_designer(self, script: Dict[str, Any], style_id: str) -> List[Dict[str, Any]]:
        suffix = _style_suffix(style_id, self._styles_by_id)
        scenes = script.get("scenes", [])[:4]
        sem = asyncio.Semaphore(MAX_CONCURRENT_IMAGES)
        out: List[Dict[str, Any]] = []

        async def design(s: Dict[str, Any]) -> Dict[str, Any]:
            prompt = (
                f"environment background art, {s.get('description','')}, {s.get('mood','')} mood, "
                f"no characters, wide establishing view, highly detailed{suffix}"
            )
            async with sem:
                img = await generate_image_with_failover(self.registry, prompt, size="1280x720")
            scene_id = f"scene_{uuid.uuid4().hex[:8]}"
            asset = await db.create_asset(
                self.project_id, self.user_id, "scene", s.get("name", f"Scene {s.get('index')}"),
                uri=img["uri"], prompt=prompt, model_id=img["model"], provider=img["provider"],
                metadata={"scene_id": scene_id, "mood": s.get("mood", ""),
                          "index": s.get("index", 1)},
            )
            await self._emit("agent.artifact", agent="scene_designer", kind="scene",
                             name=s.get("name"), uri=img["uri"])
            return {"scene_id": scene_id, "index": s.get("index", 1), "name": s.get("name"),
                    "mood": s.get("mood"), "image_uri": img["uri"],
                    "provider": img["provider"], "model": img["model"], "asset_id": asset["id"]}

        results = await asyncio.gather(*[design(s) for s in scenes], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                await self._emit("agent.warning", agent="scene_designer", error=str(r))
            else:
                out.append(r)
        if not out:
            raise RuntimeError("Scene Designer produced no images")
        return out

    async def _storyboard(self, script: Dict[str, Any], art: Dict[str, Any],
                          characters: List[Dict[str, Any]], scenes: List[Dict[str, Any]],
                          style_id: str) -> List[Dict[str, Any]]:
        suffix = _style_suffix(style_id, self._styles_by_id)
        shots = art.get("shots", [])
        scene_imgs = {s["index"]: s["image_uri"] for s in scenes}
        char_desc = "; ".join(f"{c['name']}: {c.get('description','')}" for c in characters[:2])
        sem = asyncio.Semaphore(MAX_CONCURRENT_IMAGES)
        frames: List[Dict[str, Any]] = []

        async def draw(shot: Dict[str, Any]) -> Dict[str, Any]:
            sidx = int(shot.get("scene_index", 1))
            kidx = int(shot.get("shot_index", 1))
            scene = next((s for s in script.get("scenes", []) if s.get("index") == sidx), {})
            prompt = (
                f"animation keyframe, {shot.get('framing','wide shot')}, {shot.get('focus', scene.get('description',''))}, "
                f"{scene.get('mood','')} mood, characters: {char_desc}, "
                f"consistent style, cinematic composition{suffix}"
            )
            async with sem:
                img = await generate_image_with_failover(self.registry, prompt, size="1280x720")
            frame = await db.upsert_frame(
                self.project_id, sidx, kidx,
                prompt=prompt, image_uri=img["uri"], status="image_ready",
                metadata={"framing": shot.get("framing"), "camera_move": shot.get("camera_move"),
                          "scene_ref": scene_imgs.get(sidx, ""), "provider": img["provider"],
                          "model": img["model"]},
            )
            await self._emit("agent.artifact", agent="storyboard_artist", kind="frame",
                             scene=sidx, shot=kidx, uri=img["uri"])
            return {"frame_id": frame["id"], "scene_index": sidx, "shot_index": kidx,
                    "prompt": prompt, "image_uri": img["uri"],
                    "camera_move": shot.get("camera_move", "slow pan")}

        results = await asyncio.gather(*[draw(s) for s in shots], return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                await self._emit("agent.warning", agent="storyboard_artist", error=str(r))
            else:
                frames.append(r)
        if not frames:
            raise RuntimeError("Storyboard Artist produced no frames")
        frames.sort(key=lambda f: (f["scene_index"], f["shot_index"]))
        return frames

    async def _animator(self, frames: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        clips: List[Dict[str, Any]] = []
        loop = asyncio.get_event_loop()
        sem = asyncio.Semaphore(2)  # ffmpeg encoding is CPU-bound

        async def animate(i: int, f: Dict[str, Any]) -> Dict[str, Any]:
            async with sem:
                clip_uri = await loop.run_in_executor(
                    None, media.render_clip_from_image,
                    f["image_uri"], "shot", CLIP_SECONDS, FRAME_FPS,
                    1280, 720, i,
                )
            if not clip_uri:
                raise RuntimeError("clip render failed")
            await db.upsert_frame(self.project_id, f["scene_index"], f["shot_index"],
                                  clip_uri=clip_uri, status="clip_ready",
                                  duration_seconds=float(CLIP_SECONDS))
            await self._emit("agent.artifact", agent="animator", kind="clip",
                             scene=f["scene_index"], shot=f["shot_index"], uri=clip_uri)
            return {**f, "clip_uri": clip_uri, "duration_seconds": CLIP_SECONDS}

        results = await asyncio.gather(*[animate(i, f) for i, f in enumerate(frames)],
                                       return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                await self._emit("agent.warning", agent="animator", error=str(r))
            else:
                clips.append(r)
        if not clips:
            raise RuntimeError("Animator produced no clips")
        return clips

    async def _sound_director(self, script: Dict[str, Any], total_seconds: float) -> Dict[str, Any]:
        mood = (script.get("mood") or "hopeful").lower()
        loop = asyncio.get_event_loop()
        audio_uri = await loop.run_in_executor(
            None, synthesize_score, max(5.0, total_seconds), mood, "score"
        )
        if not audio_uri:
            raise RuntimeError("Sound Director could not synthesize audio")
        await db.create_asset(self.project_id, self.user_id, "audio", "Original Score",
                              uri=audio_uri, prompt=f"{mood} ambient score",
                              model_id="numpy-synth", provider="local",
                              metadata={"mood": mood, "duration_seconds": total_seconds})
        await self._emit("agent.artifact", agent="sound_director", kind="audio", uri=audio_uri)
        return {"audio_uri": audio_uri, "mood": mood, "duration_seconds": total_seconds}

    async def _director(self, clips: List[Dict[str, Any]], sound: Dict[str, Any]) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        final_uri = await loop.run_in_executor(
            None, media.concat_clips,
            [c["clip_uri"] for c in clips], sound.get("audio_uri"), "final",
        )
        if not final_uri:
            raise RuntimeError("Director could not assemble final film")
        duration = media.probe_duration(final_uri)
        await db.update_project(self.project_id, status="complete", final_video_uri=final_uri)
        await db.create_asset(self.project_id, self.user_id, "video", "Final Film",
                              uri=final_uri, model_id="ffmpeg-concat", provider="local",
                              metadata={"shots": len(clips), "duration_seconds": duration})
        await self._emit("agent.artifact", agent="director", kind="final_video", uri=final_uri,
                         duration_seconds=duration)
        return {"final_video_uri": final_uri, "duration_seconds": duration, "shots": len(clips),
                "status": "complete"}

    # -- entry -------------------------------------------------------------
    async def run(self, idea: str, style_id: str = "", duration: Optional[int] = None,
                  aspect_ratio: str = "16:9") -> Dict[str, Any]:
        self._load_styles()
        duration = duration or 15
        await db.update_project(self.project_id, status="running", idea=idea,
                                style_id=style_id, aspect_ratio=aspect_ratio)
        await self._emit("pipeline.started", idea=idea, style_id=style_id)

        script = await self._run_agent("scriptwriter", lambda: self._scriptwriter(idea, duration))
        art = await self._run_agent("art_director", lambda: self._art_director(script, style_id))

        # Character + Scene design in parallel.
        char_task = asyncio.ensure_future(
            self._run_agent("character_designer", lambda: self._character_designer(script, style_id)))
        scene_task = asyncio.ensure_future(
            self._run_agent("scene_designer", lambda: self._scene_designer(script, style_id)))
        characters, scenes = await asyncio.gather(char_task, scene_task)

        frames = await self._run_agent(
            "storyboard_artist",
            lambda: self._storyboard(script, art, characters, scenes, style_id))

        # Animator + Sound in parallel.
        anim_task = asyncio.ensure_future(self._run_agent("animator", lambda: self._animator(frames)))
        total_seconds = float(len(frames) * CLIP_SECONDS)
        sound_task = asyncio.ensure_future(
            self._run_agent("sound_director", lambda: self._sound_director(script, total_seconds)))
        clips, sound = await asyncio.gather(anim_task, sound_task)

        final = await self._run_agent("director", lambda: self._director(clips, sound))
        await self._emit("pipeline.complete", **final)
        return {
            "script": script, "art_direction": art, "characters": characters,
            "scenes": scenes, "storyboard": frames, "clips": clips,
            "sound": sound, "final": final, "roles": list(AGENT_ROLES),
        }


# ---------------------------------------------------------------------------
# Legacy synchronous offline pipeline (kept for tests / degraded mode)
# ---------------------------------------------------------------------------
def run_scriptwriter(prompt: str) -> str:
    """Offline Scriptwriter fallback: deterministic local script text."""
    return f"A captivating animation story about {prompt}. In the first act, the journey begins..."


def run_art_director(style: str = "Anime") -> Dict[str, Any]:
    return {
        "style": style,
        "color_palette": ["#1A1A2E", "#16213E", "#0F3460", "#E94560"],
        "lighting": "Dramatic neon contrasts",
    }


def run_character_designer(script: str) -> List[Dict[str, Any]]:
    return [
        {"name": "Protagonist", "role": "Hero", "description": "Resilient lead character"},
        {"name": "Guide", "role": "Mentor", "description": "Mysterious companion"},
    ]


def run_scene_designer(script: str) -> List[Dict[str, Any]]:
    return [
        {"scene": 1, "environment": "Neo City Skyline", "mood": "Moody Rain"},
        {"scene": 2, "environment": "Hidden Sanctuary", "mood": "Mystic"},
    ]


def run_animator(scenes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{"scene": s.get("scene", i + 1), "motion": "Slow cinematic pan"}
            for i, s in enumerate(scenes)]


def run_sound_director(script: str) -> Dict[str, Any]:
    return {"bgm_track": "Synthwave Ambient Pulse (120 BPM)", "sfx": ["Rain on metal", "Energy hum"]}


def run_director(storyboard: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "Approved", "notes": "Pacing is crisp, continuity confirmed."}


def run_pipeline(prompt: str) -> dict:
    """Offline 7-agent pipeline (no network). Returns the legacy shape."""
    script = run_scriptwriter(prompt)
    art = run_art_director()
    chars = run_character_designer(script)
    scenes = run_scene_designer(script)
    anim = run_animator(scenes)
    sound = run_sound_director(script)
    director = run_director({})
    return {
        'script': script,
        'art_direction': art,
        'characters': chars,
        'scenes': scenes,
        'storyboard': [{'panel': 1, 'description': script}],
        'animation': anim,
        'sound_plan': sound,
        'director_notes': director.get("notes", "Approved by Director"),
        'roles': list(AGENT_ROLES),
    }


class AnimationPipeline:
    """Async facade. Uses RealAgentPipeline when a registry + project context is available."""

    def __init__(self, registry=None, project_id: str = "", user_id: str = "",
                 event_sink: Optional[EventSink] = None):
        self.registry = registry
        self.project_id = project_id
        self.user_id = user_id
        self.event_sink = event_sink

    async def run(self, idea: str, style: str = "", duration: Optional[int] = None,
                  aspect_ratio: str = "16:9") -> Dict[str, Any]:
        if self.registry is not None and self.project_id:
            real = RealAgentPipeline(self.registry, self.project_id, self.user_id,
                                     event_sink=self.event_sink)
            return await real.run(idea, style_id=style, duration=duration,
                                  aspect_ratio=aspect_ratio)
        return run_pipeline(idea)


def create_animation_pipeline(registry=None, project_id: str = "", user_id: str = "",
                              event_sink: Optional[EventSink] = None) -> AnimationPipeline:
    return AnimationPipeline(registry=registry, project_id=project_id, user_id=user_id,
                             event_sink=event_sink)
