from fastapi import APIRouter

from app.api.v1.endpoints import (
    chat,
    images,
    videos,
    audio,
    projects,
    pipeline,
    models,
    styles,
    providers,
)
from app.api.v1.generate import generate_router, jobs_router

# AC-10: NVIDIA NIM router removed. Multi-provider free-tier endpoints connected.
api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(images.router, prefix="/images", tags=["Images"])
api_router.include_router(videos.router, prefix="/videos", tags=["Videos"])
api_router.include_router(audio.router, prefix="/audio", tags=["Audio"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(pipeline.router, prefix="/projects", tags=["Pipeline"])
api_router.include_router(models.router, prefix="/models", tags=["Models"])
api_router.include_router(styles.router, prefix="/styles", tags=["Styles"])
api_router.include_router(providers.router, prefix="/providers", tags=["Providers"])
api_router.include_router(generate_router)
api_router.include_router(jobs_router)