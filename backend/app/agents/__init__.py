"""Agent pipeline package.

Re-exports the public facade from :mod:`backend.app.agents.pipeline` so
upstream code can import everything from a single namespace::

    from backend.app.agents import AgentRole, PipelineContext, run_pipeline

Only names that actually exist on :mod:`pipeline` are re-exported here to
keep the package import surface honest and avoid ``ImportError`` at
collection time.
"""

from .pipeline import (
    AgentRole,
    PipelineContext,
    PipelineRunner,
    build_default_pipeline,
    create_agent_stage,
    create_director_stage,
    create_scriptwriter_stage,
    create_art_director_stage,
    create_character_designer_stage,
    create_scene_designer_stage,
    create_storyboard_artist_stage,
    create_animator_stage,
    create_sound_director_stage,
    run_pipeline,
    get_orchestrator,
    reset_orchestrator,
)

__all__ = [
    "AgentRole",
    "PipelineContext",
    "PipelineRunner",
    "build_default_pipeline",
    "create_agent_stage",
    "create_director_stage",
    "create_scriptwriter_stage",
    "create_art_director_stage",
    "create_character_designer_stage",
    "create_scene_designer_stage",
    "create_storyboard_artist_stage",
    "create_animator_stage",
    "create_sound_director_stage",
    "run_pipeline",
    "get_orchestrator",
    "reset_orchestrator",
]
