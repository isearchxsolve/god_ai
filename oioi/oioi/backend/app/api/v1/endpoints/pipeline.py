from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from agent_pipeline import create_animation_pipeline
from app.services.provider_service import get_provider_registry

router = APIRouter()


class PipelineRunRequest(BaseModel):
    idea: str
    style: Optional[str] = "Anime"
    aspect_ratio: Optional[str] = "16:9"

class PipelineAnimateRequest(BaseModel):
    scenes: List[Dict[str, Any]]

# Store pipelines in memory for this demo, in a real app use DB
active_pipelines = {}

@router.post("/{project_id}/pipeline/scriptwriter")
async def run_pipeline_scriptwriter(project_id: str, request: PipelineRunRequest):
    """Run Agents 1-4 (Scriptwriter to Scene Designer) and pause for approval."""
    registry = await get_provider_registry()
    pipeline = create_animation_pipeline(registry)
    active_pipelines[project_id] = pipeline

    try:
        results = await pipeline.run_scriptwriter(idea=request.idea, style=request.style)
        return {
            "project_id": project_id,
            "status": "pending_approval",
            "stages": [
                {"agent": "Scriptwriter", "status": "completed", "output": f"Script based on: {request.idea}"},
                {"agent": "Art Director", "status": "completed", "output": f"Visual style: {request.style}"},
                {"agent": "Character Designer", "status": "completed", "output": "Characters generated"},
                {"agent": "Scene Designer", "status": "completed", "output": "Scene boards mapped"},
                {"agent": "Animator", "status": "pending", "output": "Waiting for approval"},
                {"agent": "Sound Director", "status": "pending", "output": "Waiting for approval"},
                {"agent": "Director", "status": "pending", "output": "Waiting for approval"},
            ],
            "result": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scriptwriter execution error: {e}")

@router.post("/{project_id}/pipeline/animate")
async def run_pipeline_animate(project_id: str, request: PipelineAnimateRequest):
    """Run Agents 5-7 (Animator to Director) after human approval."""
    pipeline = active_pipelines.get(project_id)
    if not pipeline:
        # Recreate if lost from memory
        registry = await get_provider_registry()
        pipeline = create_animation_pipeline(registry)

    try:
        results = await pipeline.run_animator(scenes_data=request.scenes)
        return {
            "project_id": project_id,
            "status": "completed",
            "stages": [
                {"agent": "Scriptwriter", "status": "completed", "output": "Approved"},
                {"agent": "Art Director", "status": "completed", "output": "Approved"},
                {"agent": "Character Designer", "status": "completed", "output": "Approved"},
                {"agent": "Scene Designer", "status": "completed", "output": "Approved"},
                {"agent": "Animator", "status": "completed", "output": "Animation frames rendered"},
                {"agent": "Sound Director", "status": "completed", "output": "Audio soundtrack synthesized"},
                {"agent": "Director", "status": "completed", "output": "Final film cut compiled"},
            ],
            "result": results,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Animator execution error: {e}")
