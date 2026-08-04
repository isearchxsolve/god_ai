"""Typed contracts for the 7-agent animation pipeline.

This module defines the canonical agent types, per-agent input/output
records, and the abstract :class:`AgentOrchestrator` interface that the
production pipeline implements. It is intentionally free of I/O so it can be
imported and unit-tested in isolation.

The pipeline mirrors oiioii.ai's production chain:

    Scriptwriter -> Art Director -> Character Designer -> Scene Designer
    -> Storyboard Artist -> Animator -> Sound Director -> Director
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentType(str, Enum):
    """The eight production roles in the animation pipeline."""

    SCRIPTWRITER = "scriptwriter"
    ART_DIRECTOR = "art_director"
    CHARACTER_DESIGNER = "character_designer"
    SCENE_DESIGNER = "scene_designer"
    STORYBOARD_ARTIST = "storyboard_artist"
    ANIMATOR = "animator"
    SOUND_DIRECTOR = "sound_director"
    DIRECTOR = "director"


# Ordered execution sequence used by the orchestrator.
AGENT_ORDER: List[AgentType] = [
    AgentType.SCRIPTWRITER,
    AgentType.ART_DIRECTOR,
    AgentType.CHARACTER_DESIGNER,
    AgentType.SCENE_DESIGNER,
    AgentType.STORYBOARD_ARTIST,
    AgentType.ANIMATOR,
    AgentType.SOUND_DIRECTOR,
    AgentType.DIRECTOR,
]


# ---------------------------------------------------------------------------
# Shared input/output records
# ---------------------------------------------------------------------------

@dataclass
class PipelineRequest:
    """Top-level request that seeds the whole production chain."""

    idea: str
    style_id: Optional[str] = None
    model_ids: List[str] = field(default_factory=list)
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentArtifact:
    """A single typed artifact produced by an agent."""

    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Generic result envelope returned by every agent."""

    agent_type: AgentType
    content: str = ""
    artifacts: List[AgentArtifact] = field(default_factory=list)
    status: str = "approved"
    model_id: Optional[str] = None

    def is_approved(self) -> bool:
        return self.status == "approved"


# ---------------------------------------------------------------------------
# Per-agent input/output contracts
# ---------------------------------------------------------------------------

@dataclass
class ScriptwriterInput:
    idea: str
    style_id: Optional[str] = None
    length_beats: int = 3


@dataclass
class ScriptwriterOutput:
    title: str
    logline: str
    beats: List[str]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.SCRIPTWRITER,
            content=self.raw or self.logline,
            artifacts=[AgentArtifact(type="script", payload={
                "title": self.title,
                "logline": self.logline,
                "beats": self.beats,
            })],
        )


@dataclass
class ArtDirectorInput:
    script: str
    style_id: Optional[str] = None


@dataclass
class ArtDirectorOutput:
    palette: List[str]
    mood: str
    style_tokens: List[str]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.ART_DIRECTOR,
            content=self.raw or self.mood,
            artifacts=[AgentArtifact(type="art_direction", payload={
                "palette": self.palette,
                "mood": self.mood,
                "style_tokens": self.style_tokens,
            })],
        )


@dataclass
class CharacterDesignerInput:
    script: str
    art_direction: str


@dataclass
class CharacterSheet:
    name: str
    traits: List[str]
    visual_description: str


@dataclass
class CharacterDesignerOutput:
    characters: List[CharacterSheet]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.CHARACTER_DESIGNER,
            content=self.raw,
            artifacts=[AgentArtifact(type="character_sheet", payload={
                "characters": [c.__dict__ for c in self.characters],
            })],
        )


@dataclass
class SceneDesignerInput:
    script: str
    art_direction: str


@dataclass
class SceneDesign:
    name: str
    description: str
    lighting: str


@dataclass
class SceneDesignerOutput:
    scenes: List[SceneDesign]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.SCENE_DESIGNER,
            content=self.raw,
            artifacts=[AgentArtifact(type="scene_design", payload={
                "scenes": [s.__dict__ for s in self.scenes],
            })],
        )


@dataclass
class StoryboardArtistInput:
    script: str
    characters: str
    scenes: str
    frame_count: int = 6


@dataclass
class StoryboardFrame:
    index: int
    shot: str
    description: str


@dataclass
class StoryboardArtistOutput:
    frames: List[StoryboardFrame]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.STORYBOARD_ARTIST,
            content=self.raw,
            artifacts=[AgentArtifact(type="storyboard", payload={
                "frames": [f.__dict__ for f in self.frames],
            })],
        )


@dataclass
class AnimatorInput:
    storyboard: str
    style_id: Optional[str] = None


@dataclass
class AnimationClip:
    frame_index: int
    motion: str
    duration_seconds: float
    uri: str = ""


@dataclass
class AnimatorOutput:
    clips: List[AnimationClip]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.ANIMATOR,
            content=self.raw,
            artifacts=[AgentArtifact(type="video_clip", payload={
                "clips": [c.__dict__ for c in self.clips],
            })],
        )


@dataclass
class SoundDirectorInput:
    clip: str
    script: str


@dataclass
class SoundDirectorOutput:
    music: str
    sfx: List[str]
    dialogue_cues: List[str]
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.SOUND_DIRECTOR,
            content=self.raw or self.music,
            artifacts=[AgentArtifact(type="audio_track", payload={
                "music": self.music,
                "sfx": self.sfx,
                "dialogue_cues": self.dialogue_cues,
            })],
        )


@dataclass
class DirectorInput:
    production: Dict[str, Any]


@dataclass
class DirectorOutput:
    verdict: str
    notes: str
    raw: str = ""

    def to_result(self) -> AgentResult:
        return AgentResult(
            agent_type=AgentType.DIRECTOR,
            content=self.raw or self.notes,
            artifacts=[AgentArtifact(type="director_review", payload={
                "verdict": self.verdict,
                "notes": self.notes,
            })],
        )


# ---------------------------------------------------------------------------
# Orchestrator interface
# ---------------------------------------------------------------------------

class AgentOrchestrator(ABC):
    """Abstract contract for the 7-agent production orchestrator."""

    @abstractmethod
    def run_scriptwriter(self, idea: str, style_id: Optional[str] = None) -> str:
        """Produce a script from an idea; return the raw script text."""

    @abstractmethod
    def run_pipeline(self, idea: str, style_id: Optional[str] = None) -> Dict[str, Any]:
        """Run the full production chain and return the assembled result map."""


__all__ = [
    "AgentType",
    "AGENT_ORDER",
    "PipelineRequest",
    "AgentArtifact",
    "AgentResult",
    "ScriptwriterInput",
    "ScriptwriterOutput",
    "ArtDirectorInput",
    "ArtDirectorOutput",
    "CharacterDesignerInput",
    "CharacterDesignerOutput",
    "CharacterSheet",
    "SceneDesignerInput",
    "SceneDesignerOutput",
    "SceneDesign",
    "StoryboardArtistInput",
    "StoryboardArtistOutput",
    "StoryboardFrame",
    "AnimatorInput",
    "AnimatorOutput",
    "AnimationClip",
    "SoundDirectorInput",
    "SoundDirectorOutput",
    "DirectorInput",
    "DirectorOutput",
    "AgentOrchestrator",
]
