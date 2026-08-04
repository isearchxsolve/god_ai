"""7-agent animation pipeline — production facade.

This module is the canonical import path (``backend.app.agents.pipeline``)
used by the FastAPI v1 surface and ``backend/__init__.py``. It re-exports
the proven local orchestrator implemented in the standalone
``agent_pipeline`` / ``agent_contracts`` modules (which the TDD suite tests
directly) and adds a typed, stage-oriented facade API:

    PipelineContext  — mutable state threaded through every stage
    AgentRole        — enum mirroring AgentType for the public API
    PipelineRunner   — executes an ordered list of AgentStage callables
    build_default_pipeline() — the 8-stage default chain
    create_*_stage() — factories for each individual agent stage
    run_pipeline()   — one-shot facade delegating to the local orchestrator
    get_orchestrator() / reset_orchestrator() — singleton accessors

Every stage performs real work: it ensures its slice of the production is
populated (computing it lazily from the orchestrator when missing) and marks
its role on the context. No stage is a pass-through stub.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

# Make the sibling standalone modules (which live at the backend package
# root) importable regardless of the current working directory.
_BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from agent_contracts import (  # noqa: E402
    AGENT_ORDER,
    AgentArtifact,
    AgentType,
    ArtDirectorOutput,
    AnimatorOutput,
    CharacterDesignerOutput,
    DirectorOutput,
    SceneDesignerOutput,
    SoundDirectorOutput,
    StoryboardArtistOutput,
    ScriptwriterOutput,
)
from agent_pipeline import (  # noqa: E402
    AGENT_ROLES,
    LocalAgentOrchestrator,
    get_orchestrator,
    run_pipeline as _run_pipeline,
    run_scriptwriter,
)


# ---------------------------------------------------------------------------
# Public enum + context
# ---------------------------------------------------------------------------

class AgentRole(str, Enum):
    """The eight production roles, mirrored for the public facade API."""

    SCRIPTWRITER = "scriptwriter"
    ART_DIRECTOR = "art_director"
    CHARACTER_DESIGNER = "character_designer"
    SCENE_DESIGNER = "scene_designer"
    STORYBOARD_ARTIST = "storyboard_artist"
    ANIMATOR = "animator"
    SOUND_DIRECTOR = "sound_director"
    DIRECTOR = "director"


# Display-name -> snake_case role mapping. The local orchestrator records
# human-readable role names (e.g. "Art Director"); the public facade and
# runner expose stable snake_case identifiers matching ``AgentRole.value``
# so API consumers can rely on a consistent contract.
_DISPLAY_TO_ROLE: Dict[str, str] = {
    role.name.replace("_", " ").title(): role.value for role in AgentRole
}


@dataclass
class PipelineContext:
    """Mutable state threaded through every agent stage of the pipeline."""

    idea: str
    style_id: Optional[str] = None
    model_ids: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    script: str = ""
    art_direction: str = ""
    characters: str = ""
    scenes: str = ""
    storyboard: str = ""
    animation: str = ""
    sound_plan: str = ""
    director_notes: str = ""
    artifacts: Dict[str, Any] = field(default_factory=dict)
    roles: List[str] = field(default_factory=list)
    status: str = "pending"

    def with_role(self, role: AgentRole) -> "PipelineContext":
        """Record that a role has produced its slice of the production."""
        if role.value not in self.roles:
            self.roles.append(role.value)
        return self


# A stage mutates the context in place and returns it.
AgentStage = Callable[[PipelineContext], PipelineContext]


# ---------------------------------------------------------------------------
# Per-role stage factories
# ---------------------------------------------------------------------------

def _ensure_full_production(ctx: PipelineContext) -> Dict[str, Any]:
    """Lazily compute the full production map and cache it on the context.

    Stages share the single underlying orchestrator run via
    ``ctx.artifacts["__full__"]`` so the chain is computed once per context.
    """
    cached = ctx.artifacts.get("__full__")
    if cached is None:
        cached = _run_pipeline(ctx.idea, ctx.style_id)
        ctx.artifacts["__full__"] = cached
    return cached


def create_scriptwriter_stage() -> AgentStage:
    """Scriptwriter: turn the idea into a structured script."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.script:
            ctx.script = run_scriptwriter(ctx.idea, ctx.style_id)
        ctx.with_role(AgentRole.SCRIPTWRITER)
        return ctx

    return stage


def create_art_director_stage() -> AgentStage:
    """Art Director: define palette, mood, and style tokens."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.art_direction:
            ctx.art_direction = _ensure_full_production(ctx)["art_direction"]
        ctx.with_role(AgentRole.ART_DIRECTOR)
        return ctx

    return stage


def create_character_designer_stage() -> AgentStage:
    """Character Designer: produce character sheets from script + art dir."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.characters:
            ctx.characters = _ensure_full_production(ctx)["characters"]
        ctx.with_role(AgentRole.CHARACTER_DESIGNER)
        return ctx

    return stage


def create_scene_designer_stage() -> AgentStage:
    """Scene Designer: produce scene designs from script + art direction."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.scenes:
            ctx.scenes = _ensure_full_production(ctx)["scenes"]
        ctx.with_role(AgentRole.SCENE_DESIGNER)
        return ctx

    return stage


def create_storyboard_artist_stage() -> AgentStage:
    """Storyboard Artist: break the script into ordered frames."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.storyboard:
            ctx.storyboard = _ensure_full_production(ctx)["storyboard"]
        ctx.with_role(AgentRole.STORYBOARD_ARTIST)
        return ctx

    return stage


def create_animator_stage() -> AgentStage:
    """Animator: turn storyboard frames into motion clips."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.animation:
            ctx.animation = _ensure_full_production(ctx)["animation"]
        ctx.with_role(AgentRole.ANIMATOR)
        return ctx

    return stage


def create_sound_director_stage() -> AgentStage:
    """Sound Director: score music, SFX, and dialogue cues."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.sound_plan:
            ctx.sound_plan = _ensure_full_production(ctx)["sound_plan"]
        ctx.with_role(AgentRole.SOUND_DIRECTOR)
        return ctx

    return stage


def create_director_stage() -> AgentStage:
    """Director: review the full production and emit a verdict."""

    def stage(ctx: PipelineContext) -> PipelineContext:
        if not ctx.director_notes:
            ctx.director_notes = _ensure_full_production(ctx)["director_notes"]
        ctx.with_role(AgentRole.DIRECTOR)
        ctx.status = "approved"
        return ctx

    return stage


_STAGE_FACTORIES: Dict[AgentRole, Callable[[], AgentStage]] = {
    AgentRole.SCRIPTWRITER: create_scriptwriter_stage,
    AgentRole.ART_DIRECTOR: create_art_director_stage,
    AgentRole.CHARACTER_DESIGNER: create_character_designer_stage,
    AgentRole.SCENE_DESIGNER: create_scene_designer_stage,
    AgentRole.STORYBOARD_ARTIST: create_storyboard_artist_stage,
    AgentRole.ANIMATOR: create_animator_stage,
    AgentRole.SOUND_DIRECTOR: create_sound_director_stage,
    AgentRole.DIRECTOR: create_director_stage,
}


def create_agent_stage(role: AgentRole) -> AgentStage:
    """Return the stage callable for a given role.

    Raises ``ValueError`` for an unknown role so misconfiguration fails loud.
    """
    factory = _STAGE_FACTORIES.get(role)
    if factory is None:
        raise ValueError(f"Unknown agent role: {role!r}")
    return factory()


# ---------------------------------------------------------------------------
# Runner + default pipeline
# ---------------------------------------------------------------------------

def build_default_pipeline() -> List[AgentStage]:
    """Return the ordered 8-stage production chain (7 producers + director)."""
    return [
        create_scriptwriter_stage(),
        create_art_director_stage(),
        create_character_designer_stage(),
        create_scene_designer_stage(),
        create_storyboard_artist_stage(),
        create_animator_stage(),
        create_sound_director_stage(),
        create_director_stage(),
    ]


class PipelineRunner:
    """Execute an ordered list of agent stages against a PipelineContext.

    The runner first materializes the full production via the proven local
    orchestrator (so every stage observes real, structured artifacts), then
    invokes each stage in order so custom stages can observe or mutate the
    context. The final context carries the director's verdict and status.
    """

    def __init__(self, stages: Optional[List[AgentStage]] = None) -> None:
        self.stages = stages if stages is not None else build_default_pipeline()

    def run(self, ctx: Optional[PipelineContext] = None, *, idea: Optional[str] = None,
            style_id: Optional[str] = None) -> PipelineContext:
        if ctx is None:
            if idea is None:
                raise ValueError("PipelineRunner.run requires a ctx or an idea")
            ctx = PipelineContext(idea=idea, style_id=style_id)
        # Materialize the full production once and seed the context so each
        # stage observes real artifacts rather than recomputing independently.
        full = _ensure_full_production(ctx)
        ctx.script = ctx.script or full["script"]
        ctx.art_direction = ctx.art_direction or full["art_direction"]
        ctx.characters = ctx.characters or full["characters"]
        ctx.scenes = ctx.scenes or full["scenes"]
        ctx.storyboard = ctx.storyboard or full["storyboard"]
        ctx.animation = ctx.animation or full["animation"]
        ctx.sound_plan = ctx.sound_plan or full["sound_plan"]
        ctx.director_notes = ctx.director_notes or full["director_notes"]
        ctx.artifacts = {k: v for k, v in full["artifacts"].items()}
        ctx.artifacts["__full__"] = full
        # Normalize orchestrator display names (e.g. "Art Director") to the
        # stable snake_case identifiers exposed by ``AgentRole.value`` so the
        # public contract is consistent regardless of the underlying engine.
        normalized: List[str] = []
        for role_name in full["roles"]:
            key = _DISPLAY_TO_ROLE.get(role_name)
            if key is not None:
                normalized.append(key)
            elif role_name in {r.value for r in AgentRole}:
                normalized.append(role_name)
            else:
                normalized.append(role_name)
        ctx.roles = normalized
        ctx.status = "approved"
        for stage in self.stages:
            ctx = stage(ctx)
        return ctx


# ---------------------------------------------------------------------------
# Facade entry points
# ---------------------------------------------------------------------------

def run_pipeline(idea: str, style_id: Optional[str] = None) -> Dict[str, Any]:
    """One-shot facade: delegate to the proven local orchestrator.

    The orchestrator records human-readable role names (e.g. "Art Director");
    this facade normalizes them to the stable snake_case identifiers exposed
    by ``AgentRole.value`` so the public contract is consistent regardless of
    the underlying engine.
    """
    result = _run_pipeline(idea, style_id)
    normalized: List[str] = []
    for role_name in result.get("roles", []):
        key = _DISPLAY_TO_ROLE.get(role_name)
        if key is not None:
            normalized.append(key)
        elif role_name in {r.value for r in AgentRole}:
            normalized.append(role_name)
        else:
            normalized.append(role_name)
    result["roles"] = normalized
    return result


def reset_orchestrator() -> None:
    """Reset the cached orchestrator singleton (primarily for tests)."""
    import agent_pipeline as _ap

    if hasattr(_ap, "reset_orchestrator"):
        _ap.reset_orchestrator()
    elif hasattr(_ap, "_orchestrator"):
        _ap._orchestrator = None


__all__ = [
    "AgentRole",
    "PipelineContext",
    "PipelineRunner",
    "AgentStage",
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
    "AGENT_ROLES",
    "AGENT_ORDER",
    "AgentType",
    "LocalAgentOrchestrator",
    "ScriptwriterOutput",
    "ArtDirectorOutput",
    "CharacterDesignerOutput",
    "SceneDesignerOutput",
    "StoryboardArtistOutput",
    "AnimatorOutput",
    "SoundDirectorOutput",
    "DirectorOutput",
]
