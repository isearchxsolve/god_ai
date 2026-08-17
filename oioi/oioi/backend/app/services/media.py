"""Media service: local storage, image download, and video assembly.

- Downloads generated images (e.g. from Pollinations) into ./storage/media so
  artifacts are durable and served locally rather than hot-linked.
- Assembles real MP4 clips from still frames using the ffmpeg binary bundled
  with imageio-ffmpeg (Ken Burns pan/zoom motion applied per frame).
- Concatenates clips into a final film with an optional audio track.
"""
from __future__ import annotations

import asyncio
import math
import os
import shutil
import subprocess
import uuid
from typing import List, Optional

import httpx

from app.core.config import settings

try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:  # pragma: no cover - ffmpeg optional at import time
    FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

try:
    from PIL import Image
    HAS_PIL = True
except Exception:  # pragma: no cover
    HAS_PIL = False


def media_dir() -> str:
    d = os.path.join(settings.STORAGE_PATH, "media")
    os.makedirs(d, exist_ok=True)
    return d


def public_uri(filename: str) -> str:
    """Return the app-relative URI used to serve a stored file."""
    return f"/media/{filename}"


async def download_image(url: str, prefix: str = "img", timeout: int = 90) -> Optional[str]:
    """Fetch an image from a remote URL and store it locally. Returns public URI."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0 OiiOiiStudio/1.0"})
            resp.raise_for_status()
            data = resp.content
        if not data or len(data) < 100:
            return None
        ext = ".jpg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            ext = ".png"
        elif data[:3] == b"\xff\xd8\xff":
            ext = ".jpg"
        elif data[:4] == b"RIFF":
            ext = ".webp"
        fname = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
        path = os.path.join(media_dir(), fname)
        with open(path, "wb") as f:
            f.write(data)
        return public_uri(fname)
    except Exception:
        return None


def save_bytes(data: bytes, prefix: str, ext: str) -> str:
    fname = f"{prefix}_{uuid.uuid4().hex[:12]}{ext}"
    path = os.path.join(media_dir(), fname)
    with open(path, "wb") as f:
        f.write(data)
    return public_uri(fname)


def _local_path(uri: str) -> str:
    if uri.startswith("/media/"):
        return os.path.join(media_dir(), uri[len("/media/"):])
    return uri


def _kenburns_frame(src: Image.Image, t: float, width: int, height: int,
                    direction: int = 0) -> Image.Image:
    """Crop/zoom a source image to produce a pan/zoom frame at progress t in [0,1]."""
    sw, sh = src.size
    # Zoom from 1.0 -> 1.18 across the clip, plus a small pan.
    zoom = 1.0 + 0.18 * t
    cw, ch = int(sw / zoom), int(sh / zoom)
    max_dx = max(0, sw - cw)
    max_dy = max(0, sh - ch)
    if direction % 4 == 0:      # pan left -> right
        x, y = int(max_dx * t), int(max_dy * 0.5)
    elif direction % 4 == 1:    # pan right -> left
        x, y = int(max_dx * (1 - t)), int(max_dy * 0.5)
    elif direction % 4 == 2:    # pan top -> bottom
        x, y = int(max_dx * 0.5), int(max_dy * t)
    else:                       # center zoom
        x, y = int(max_dx * 0.5), int(max_dy * 0.5)
    crop = src.crop((x, y, x + cw, y + ch))
    return crop.resize((width, height), Image.LANCZOS)


def render_clip_from_image(image_uri: str, out_prefix: str = "clip",
                           seconds: Optional[int] = None, fps: Optional[int] = None,
                           width: int = 1280, height: int = 720,
                           direction: int = 0) -> Optional[str]:
    """Create a real MP4 clip from a single still via Ken Burns motion.

    Uses the bundled ffmpeg binary. Returns the public URI of the clip.
    """
    if not HAS_PIL or not FFMPEG:
        return None
    seconds = seconds or settings.CLIP_SECONDS
    fps = fps or settings.FRAME_FPS
    src_path = _local_path(image_uri)
    if not os.path.exists(src_path):
        return None
    try:
        src = Image.open(src_path).convert("RGB")
    except Exception:
        return None

    n_frames = max(2, int(seconds * fps))
    frame_dir = os.path.join(media_dir(), f"frames_{uuid.uuid4().hex[:10]}")
    os.makedirs(frame_dir, exist_ok=True)
    try:
        for i in range(n_frames):
            t = i / max(1, n_frames - 1)
            frame = _kenburns_frame(src, t, width, height, direction)
            frame.save(os.path.join(frame_dir, f"f{i:05d}.jpg"), quality=88)

        fname = f"{out_prefix}_{uuid.uuid4().hex[:12]}.mp4"
        out_path = os.path.join(media_dir(), fname)
        cmd = [
            FFMPEG, "-y", "-loglevel", "error",
            "-framerate", str(fps),
            "-i", os.path.join(frame_dir, "f%05d.jpg"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast", "-crf", "23",
            "-movflags", "+faststart",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        return public_uri(fname)
    except Exception:
        return None
    finally:
        shutil.rmtree(frame_dir, ignore_errors=True)


def concat_clips(clip_uris: List[str], audio_uri: Optional[str] = None,
                 out_prefix: str = "final") -> Optional[str]:
    """Concatenate MP4 clips (re-encoding for uniformity) and mux optional audio."""
    if not FFMPEG or not clip_uris:
        return None
    paths = [_local_path(u) for u in clip_uris]
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return None
    list_file = os.path.join(media_dir(), f"concat_{uuid.uuid4().hex[:8]}.txt")
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for p in paths:
                f.write(f"file '{p}'\n")
        fname = f"{out_prefix}_{uuid.uuid4().hex[:12]}.mp4"
        out_path = os.path.join(media_dir(), fname)
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
               "-i", list_file, "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-preset", "veryfast", "-crf", "23", "-movflags", "+faststart"]
        if audio_uri:
            audio_path = _local_path(audio_uri)
            if os.path.exists(audio_path):
                cmd += ["-i", audio_path, "-c:a", "aac", "-shortest"]
        cmd.append(out_path)
        subprocess.run(cmd, check=True, capture_output=True, timeout=600)
        return public_uri(fname)
    except Exception:
        return None
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def probe_duration(uri: str) -> float:
    """Return media duration in seconds (0 if unknown)."""
    path = _local_path(uri)
    if not os.path.exists(path):
        return 0.0
    try:
        gen = None
        import imageio_ffmpeg
        reader = imageio_ffmpeg.read_frames(path)
        meta = next(reader)
        reader.close()
        return float(meta.get("duration", 0.0))
    except Exception:
        return 0.0
