from fastapi import APIRouter
from typing import Dict, Any

from app.services.provider_service import get_provider_registry

router = APIRouter()


@router.get("/health")
async def provider_health_dashboard():
    """Live provider health dashboard (AC-1, AC-10). NVIDIA NIM is blocked and not reported."""
    registry = await get_provider_registry()
    snapshot = registry.snapshot()
    return {
        "status": "healthy",
        "active_providers": len(snapshot),
        "providers": snapshot,
    }
