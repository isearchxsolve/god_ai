from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from backend.app.core.database import init_db, close_db
from backend.app.api import projects, auth, credits


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="Emergent.sh Clone API",
    description="API for the Emergent.sh clone - AI-powered full-stack app builder",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(credits.router)


@app.get("/")
async def root():
    return {
        "name": "Emergent.sh Clone API",
        "version": "1.0.0",
        "description": "AI-powered full-stack app builder API",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}