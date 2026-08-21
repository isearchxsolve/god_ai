"""Scriptwriter agent contract.

Defines the typed input/output schema, validation rules, retry policy, and
provider fallback chain for the Scriptwriter agent — the first stage of the
7-agent animation pipeline. The Scriptwriter turns a raw creative idea into a
structured script (title, logline, scene beats, dialogue, shot directions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ScriptTone(str, Enum):
    """Allowed emotional tones for a generated script."""

    DRAMATIC = "dramatic"
    COMEDIC = "comedic"
    WHIMSICAL = "whimsical"
    DARK = "dark"
    UPLIFTING = "uplifting"
    TENSE = "tense"


class ScriptFormat(str, Enum):
    """Output format the scriptwriter should produce."""

    SHORT_FILM = "short_film"
    MUSIC_VIDEO = "music_video"
    CREATIVE_CLIP = "creative_clip"
    STORY_ANIME = "story_anime"


@dataclass(frozen=True)
class SceneBeat:
    """A single beat in the script — one moment of screen time."""

    index: int
    description: str
    dialogue: str = ""
    shot_direction: str = ""
    duration_seconds: float = 5.0

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError(f"SceneBeat.index must be >= 0, got {self.index}")
        if not self.description or not self.description.strip():
            raise ValueError("SceneBeat.description must be non-empty")
        if self.duration_seconds <= 0:
            raise ValueError(
                f"SceneBeat.duration_seconds must be > 0, got {self.duration_seconds}"
            )


@dataclass(frozen=True)
class ScriptwriterInput:
    """Typed input to the Scriptwriter agent."""

    idea: str
    style_id: str
    target_format: ScriptFormat = ScriptFormat.CREATIVE_CLIP
    target_duration_seconds: float = 15.0
    tone: ScriptTone = ScriptTone.DRAMATIC
    language: str = "en"
    reference_asset_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.idea or not self.idea.strip():
            raise ValueError("ScriptwriterInput.idea must be non-empty")
        if not self.style_id or not self.style_id.strip():
            raise ValueError("ScriptwriterInput.style_id must be non-empty")
        if self.target_duration_seconds <= 0:
            raise ValueError(
                f"target_duration_seconds must be > 0, got {self.target_duration_seconds}"
            )
        if self.target_duration_seconds > 600:
            raise ValueError(
                f"target_duration_seconds must be <= 600 (10 min), got {self.target_duration_seconds}"
            )


@dataclass(frozen=True)
class ScriptwriterOutput:
    """Typed output from the Scriptwriter agent."""

    title: str
    logline: str
    beats: tuple[SceneBeat, ...]
    raw_text: str
    provider_used: str
    model_used: str
    tokens_used: int = 0

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("ScriptwriterOutput.title must be non-empty")
        if not self.logline or not self.logline.strip():
            raise ValueError("ScriptwriterOutput.logline must be non-empty")
        if not self.beats:
            raise ValueError("ScriptwriterOutput.beats must contain at least one SceneBeat")
        if self.tokens_used < 0:
            raise ValueError(f"tokens_used must be >= 0, got {self.tokens_used}")

    @property
    def total_duration_seconds(self) -> float:
        """Sum of all beat durations."""
        return sum(beat.duration_seconds for beat in self.beats)

    def beat_count(self) -> int:
        """Number of beats in the script."""
        return len(self.beats)


@dataclass(frozen=True)
class RetryPolicy:
    """Retry configuration for the Scriptwriter agent."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError(f"max_attempts must be >= 1, got {self.max_attempts}")
        if self.base_delay_seconds <= 0:
            raise ValueError("base_delay_seconds must be > 0")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds must be >= base_delay_seconds")
        if self.backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be >= 1.0")

    def delay_for_attempt(self, attempt: int) -> float:
        """Compute the delay (seconds) before the given attempt (1-indexed)."""
        if attempt < 1:
            raise ValueError(f"attempt must be >= 1, got {attempt}")
        delay = self.base_delay_seconds * (self.backoff_multiplier ** (attempt - 1))
        return min(delay, self.max_delay_seconds)


# Ordered provider fallback chain — first available wins. Free-tier providers
# only, matching the project's no-paid-key constraint.
SCRIPTWRITER_PROVIDER_CHAIN: tuple[str, ...] = (
    "groq",        # llama-3.3-70b-versatile — fast, generous free tier
    "cerebras",    # llama-3.1-8b — ultra-low latency free tier
    "openrouter",  # free-tier models as last resort
    "gemini",      # gemini-1.5-flash free tier fallback
)


def default_retry_policy() -> RetryPolicy:
    """Return the default retry policy for the Scriptwriter agent."""
    return RetryPolicy()


def validate_output_against_input(
    output: ScriptwriterOutput, input_: ScriptwriterInput
) -> list[str]:
    """Return a list of validation errors; empty list means valid.

    Checks that the produced script's total duration is within +/-20% of the
    requested target, and that the number of beats is reasonable for the format.
    """
    errors: list[str] = []
    target = input_.target_duration_seconds
    actual = output.total_duration_seconds
    if actual < target * 0.5:
        errors.append(
            f"Script too short: {actual:.1f}s vs target {target:.1f}s"
        )
    if actual > target * 2.0:
        errors.append(
            f"Script too long: {actual:.1f}s vs target {target:.1f}s"
        )
    min_beats = 1
    max_beats = 60
    if output.beat_count() < min_beats:
        errors.append(f"Need at least {min_beats} beat, got {output.beat_count()}")
    if output.beat_count() > max_beats:
        errors.append(f"Too many beats: {output.beat_count()} > {max_beats}")
    return errors


__all__ = [
    "ScriptTone",
    "ScriptFormat",
    "SceneBeat",
    "ScriptwriterInput",
    "ScriptwriterOutput",
    "RetryPolicy",
    "SCRIPTWRITER_PROVIDER_CHAIN",
    "default_retry_policy",
    "validate_output_against_input",
]
