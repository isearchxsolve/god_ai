"""Image generation endpoint with provider failover and local persistence."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent_pipeline import generate_image_with_failover
from app.core import db
from app.core.auth import get_current_user
from app.services.provider_service import get_provider_registry

router = APIRouter()


class ImageGenerationRequest(BaseModel):
    prompt: str
    model: Optional[str] = "flux"
    size: Optional[str] = "1024x1024"
    n: Optional[int] = 1
    style: Optional[str] = None
    style_id: Optional[str] = None
    project_id: Optional[str] = None


@router.post("/generations")
async def generate_images(request: ImageGenerationRequest,
                          user: dict = Depends(get_current_user)):
    """Generate an image via the provider registry.

    Applies the selected style's prompt template, routes through the registry
    with automatic failover, downloads the result into durable local storage
    when possible, and (optionally) records it as a project asset.
    """
    registry = await get_provider_registry()

    # Apply style template if provided.
    suffix = ""
    if request.style_id or request.style:
        from styles_registry import get_style
        style = get_style(request.style_id or request.style or "")
        suffix = style.get("promptSuffix", "")
    full_prompt = request.prompt + suffix

    try:
        result = await generate_image_with_failover(
            registry, full_prompt, size=request.size or "1024x1024",
            require_local=False,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Image generation failed: {exc}")

    asset = None
    if request.project_id:
        asset = await db.create_asset(
            request.project_id, user["id"], "image", request.prompt[:60],
            uri=result["uri"], prompt=full_prompt, model_id=result["model"],
            provider=result["provider"],
        )

    return {
        "data": [{"url": result["uri"], "source_url": result.get("source_url", "")}],
        "provider": result["provider"],
        "model": result["model"],
        "prompt": full_prompt,
        "local": result.get("local", False),
        "asset": asset,
    }
