"""TDD tests for the 7-agent animation pipeline.

These tests exercise :mod:`agent_pipeline` and :mod:`agent_contracts` without
requiring any network access. The local orchestrator is deterministic, so the
assertions check real structured artifacts produced by each agent stage.
"""

from __future__ import annotations

import os
import sys

import pytest

# Ensure the backend package root is importable when tests run from the
# backend directory or from the project root.
BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from agent_contracts import (  # noqa: E402
    AGENT_ORDER,
    AgentType,
    ArtDirectorOutput,
    CharacterDesignerOutput,
    SceneDesignerOutput,
    StoryboardArtistOutput,
    AnimatorOutput,
    SoundDirectorOutput,
    DirectorOutput,
)
from agent_pipeline import (  # noqa: E402
    AGENT_ROLES,
    LocalAgentOrchestrator,
    get_orchestrator,
    run_pipeline,
    run_scriptwriter,
)


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

def test_agent_order_has_seven_production_roles_plus_director():
    # Scriptwriter, Art Director, Character Designer, Scene Designer,
    # Storyboard Artist, Animator, Sound Director, Director.
    assert len(AGENT_ORDER) == 8
    assert AGENT_ORDER[0] is AgentType.SCRIPTWRITER
    assert AGENT_ORDER[-1] is AgentType.DIRECTOR
    assert AgentType.ANIMATOR in AGENT_ORDER
    assert AgentType.SOUND_DIRECTOR in AGENT_ORDER


def test_agent_roles_map_matches_order():
    expected_names = [
        "Scriptwriter",
        "Art Director",
        "Character Designer",
        "Scene Designer",
        "Storyboard Artist",
        "Animator",
        "Sound Director",
        "Director",
    ]
    assert list(AGENT_ROLES.keys()) == expected_names


# ---------------------------------------------------------------------------
# Scriptwriter
# ---------------------------------------------------------------------------

def test_scriptwriter_returns_non_empty_script():
    script = run_scriptwriter("a lonely robot finds a flower")
    assert isinstance(script, str)
    assert len(script) > 20
    assert "robot" in script.lower() or "flower" in script.lower()


def test_scriptwriter_handles_empty_idea_gracefully():
    script = run_scriptwriter("")
    assert isinstance(script, str)
    assert len(script) > 10  # falls back to a default story


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def test_pipeline_returns_all_seven_stages():
    result = run_pipeline("a girl chases a comet across the city")
    required_keys = {
        "script",
        "art_direction",
        "characters",
        "scenes",
        "storyboard",
        "animation",
        "sound_plan",
        "director_notes",
        "roles",
        "artifacts",
    }
    assert required_keys.issubset(result.keys())


def test_pipeline_roles_list_has_seven_entries():
    result = run_pipeline("a samurai meditates under neon rain")
    assert len(result["roles"]) == 7
    assert "Scriptwriter" in result["roles"]
    assert "Director" not in result["roles"]  # director is the reviewer, not a producer


def test_pipeline_artifacts_contain_structured_data():
    result = run_pipeline("a kite flies over a sleeping volcano")
    artifacts = result["artifacts"]
    assert isinstance(artifacts["palette"], list) and len(artifacts["palette"]) >= 2
    assert isinstance(artifacts["character_sheets"], list) and artifacts["character_sheets"]
    assert isinstance(artifacts["scene_designs"], list) and artifacts["scene_designs"]
    assert isinstance(artifacts["frames"], list) and artifacts["frames"]
    assert isinstance(artifacts["clips"], list) and artifacts["clips"]
    assert "music" in artifacts["sound"] and "sfx" in artifacts["sound"]


def test_pipeline_director_approves_production():
    result = run_pipeline("a paper boat sails down a neon river")
    assert result["director_notes"]
    assert "approved" in result["director_notes"].lower() or "ready" in result["director_notes"].lower()


def test_pipeline_storyboard_has_multiple_frames():
    result = run_pipeline("a cat explores an abandoned arcade")
    frames = result["artifacts"]["frames"]
    assert len(frames) >= 3
    assert all("index" in f and "shot" in f for f in frames)


def test_pipeline_animation_has_clips():
    result = run_pipeline("a dancer performs in zero gravity")
    clips = result["artifacts"]["clips"]
    assert len(clips) >= 1
    assert all("frame_index" in c and "duration_seconds" in c for c in clips)


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------

def test_get_orchestrator_returns_local_default():
    orch = get_orchestrator()
    assert isinstance(orch, LocalAgentOrchestrator)


def test_orchestrator_without_registry_still_runs():
    orch = LocalAgentOrchestrator(registry=None)
    result = orch.run_pipeline("a hummingbird visits a cyberpunk garden")
    assert result["script"]
    assert result["director_notes"]


@pytest.mark.parametrize("idea", ["a storm of glowing jellyfish", "a monk paints the sky", "a robot learns to dream"])
def test_pipeline_is_deterministic_for_same_idea(idea):
    a = run_pipeline(idea)
    b = run_pipeline(idea)
    assert a["script"] == b["script"]
    assert a["artifacts"]["frames"] == b["artifacts"]["frames"]
