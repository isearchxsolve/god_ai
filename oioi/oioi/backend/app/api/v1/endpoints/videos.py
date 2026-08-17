"""Video generation endpoint.

Strategy (free-tier friendly):
1. If a registry provider supports video (e.g. Gemini Veo), try it and
   download the result locally.
2. Otherwise render a real MP4 clip locally: generate a keyframe image from
   the prompt (or use the supplied first frame) and apply Ken Burns motion
   with the bundled ffmpeg.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent_pipeline import extract_image_url, generate_image_with_failover
from app.core import db
from app.core.auth import get_current_user
from app.core.config import settings
from app.services import media
from app.services.provider_service import get_provider_registry

router = APIRouter()


class VideoGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = "kenburns-frames"
    first_frame_url: Optional[str] = None
    last_frame_url: Optional[str] = None
    duration_seconds: Optional[int] = 5
    size: Optional[str] = "1280x720"
    project_id: Optional[str] = None


@router.post("/generations")
async def generate_video(request: VideoGenerationRequest,
                         user: dict = Depends(get_current_user)):
    """Generate a video clip. Returns a playable local MP4 whenever possible."""
    registry = await get_provider_registry()
    remote_candidate = ""

    # 1) Try a real video provider if one is registered.
    candidates = registry._candidates("video")
    for rec in candidates:
        try:
            adapter = await registry.get_adapter("video", prefer=rec.name)
            from providers.base import VideoGenerationRequest as AdapterReq
            resp = await asyncio.wait_for(
                adapter.generate_video(AdapterReq(
                    prompt=request.prompt, model=request.model or "",
                    first_frame=request.first_frame_url,
                    last_frame=request.last_frame_url,
                )),
                timeout=180,
            )
            if isinstance(resp, str):
                url = resp
            else:
                data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
                url = (data.get("data") or [{}])[0].get("url", "")
            if url:
                registry.report_success(rec.name)
                local = await media.download_image(url, prefix="vid", timeout=180)
                if local:
                    return await _finish(request, user, local, rec.name, request.model or "")
                remote_candidate = url
                break
        except NotImplementedError:
            continue
        except Exception as exc:
            registry.report_failure(rec.name, str(exc))

    # 2) Local Ken Burns render from a first frame or a generated keyframe.
    frame_uri = request.first_frame_url or ""
    if frame_uri and not frame_uri.startswith("/media/"):
        downloaded = await media.download_image(frame_uri, prefix="frame")
        frame_uri = downloaded or ""
    if not frame_uri:
        try:
            img = await generate_image_with_failover(
                registry, request.prompt, size=request.size or "1280x720",
                require_local=True,
            )
            frame_uri = img["uri"]
        except Exception:
            frame_uri = ""

    if frame_uri:
        loop = asyncio.get_event_loop()
        clip_uri = await loop.run_in_executor(
            None, media.render_clip_from_image,
            frame_uri, "clip", request.duration_seconds or settings.CLIP_SECONDS,
            settings.FRAME_FPS, 1280, 720, 0,
        )
        if clip_uri:
            return await _finish(request, user, clip_uri, "local-ffmpeg", "kenburns-frames")

    # 3) Last resort: return the remote candidate if we have one.
    if remote_candidate:
        return await _finish(request, user, remote_candidate, "remote", request.model or "")

    raise HTTPException(status_code=502, detail="Video generation failed: no provider or render path available")


async def _finish(request: VideoGenerationRequest, user: dict, uri: str,
                  provider: str, model: str) -> dict:
    duration = media.probe_duration(uri) if uri.startswith("/media/") else float(
        request.duration_seconds or settings.CLIP_SECONDS)
    asset = None
    if request.project_id:
        asset = await db.create_asset(
            request.project_id, user["id"], "video", request.prompt[:60],
            uri=uri, prompt=request.prompt, model_id=model, provider=provider,
            metadata={"duration_seconds": duration},
        )
    return {
        "status": "completed",
        "video_url": uri,
        "duration_seconds": duration,
        "provider": provider,
        "model": model,
        "prompt": request.prompt,
        "first_frame": request.first_frame_url,
        "last_frame": request.last_frame_url,
        "asset": asset,
    }
