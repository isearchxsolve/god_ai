"""TDD tests for the typed PipelineRunner facade in backend.app.agents.pipeline.

These exercise the public, stage-oriented API (PipelineContext, AgentRole,
PipelineRunner, build_default_pipeline, create_*_stage) that the FastAPI v1
surface imports. They complement the standalone agent_pipeline tests by
verifying the facade correctly threads state through every stage.
"""

from __future__ import annotations

import os
import sys

import pytest

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.agents.pipeline import (  # noqa: E402
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
    reset_orchestrator,
)


@pytest.fixture(autouse=True)
def _fresh_orchestrator():
    reset_orchestrator()
    yield
    reset_orchestrator()


def test_agent_role_enum_has_eight_roles():
    roles = list(AgentRole)
    assert len(roles) == 8
    assert roles[0] is AgentRole.SCRIPTWRITER
    assert roles[-1] is AgentRole.DIRECTOR


def test_build_default_pipeline_returns_eight_stages():
    stages = build_default_pipeline()
    assert len(stages) == 8
    assert all(callable(s) for s in stages)


def test_create_agent_stage_returns_callable_for_each_role():
    for role in AgentRole:
        stage = create_agent_stage(role)
        assert callable(stage)


def test_create_agent_stage_raises_for_unknown_role():
    with pytest.raises(ValueError):
        create_agent_stage("not-a-role")  # type: ignore[arg-type]


def test_pipeline_runner_seeds_context_with_full_production():
    runner = PipelineRunner()
    ctx = runner.run(idea="a lantern drifts through a foggy harbour")
    assert ctx.status == "approved"
    assert ctx.script
    assert ctx.art_direction
    assert ctx.characters
    assert ctx.scenes
    assert ctx.storyboard
    assert ctx.animation
    assert ctx.sound_plan
    assert ctx.director_notes


def test_pipeline_runner_records_all_eight_roles():
    runner = PipelineRunner()
    ctx = runner.run(idea="a fox races the sunrise")
    expected = [r.value for r in AgentRole]
    assert ctx.roles == expected


def test_pipeline_runner_accepts_prebuilt_context():
    ctx = PipelineContext(idea="a kite escapes into a thundercloud")
    runner = PipelineRunner()
    out = runner.run(ctx)
    assert out is ctx
    assert ctx.status == "approved"
    assert ctx.director_notes


def test_pipeline_runner_requires_idea_when_no_ctx():
    runner = PipelineRunner()
    with pytest.raises(ValueError):
        runner.run()


def test_pipeline_context_with_role_is_idempotent():
    ctx = PipelineContext(idea="x")
    ctx.with_role(AgentRole.ANIMATOR)
    ctx.with_role(AgentRole.ANIMATOR)
    assert ctx.roles.count(AgentRole.ANIMATOR.value) == 1


def test_individual_stages_populate_their_slice():
    ctx = PipelineContext(idea="a hummingbird visits a cyberpunk garden")
    create_scriptwriter_stage()(ctx)
    assert ctx.script
    assert AgentRole.SCRIPTWRITER.value in ctx.roles

    create_art_director_stage()(ctx)
    assert ctx.art_direction
    assert AgentRole.ART_DIRECTOR.value in ctx.roles

    create_character_designer_stage()(ctx)
    assert ctx.characters
    assert AgentRole.CHARACTER_DESIGNER.value in ctx.roles

    create_scene_designer_stage()(ctx)
    assert ctx.scenes
    assert AgentRole.SCENE_DESIGNER.value in ctx.roles

    create_storyboard_artist_stage()(ctx)
    assert ctx.storyboard
    assert AgentRole.STORYBOARD_ARTIST.value in ctx.roles

    create_animator_stage()(ctx)
    assert ctx.animation
    assert AgentRole.ANIMATOR.value in ctx.roles

    create_sound_director_stage()(ctx)
    assert ctx.sound_plan
    assert AgentRole.SOUND_DIRECTOR.value in ctx.roles

    create_director_stage()(ctx)
    assert ctx.director_notes
    assert ctx.status == "approved"
    assert AgentRole.DIRECTOR.value in ctx.roles


def test_facade_run_pipeline_matches_orchestrator_output():
    result = run_pipeline("a paper boat sails down a neon river")
    assert set(result["roles"]) == {
        AgentRole.SCRIPTWRITER.value,
        AgentRole.ART_DIRECTOR.value,
        AgentRole.CHARACTER_DESIGNER.value,
        AgentRole.SCENE_DESIGNER.value,
        AgentRole.STORYBOARD_ARTIST.value,
        AgentRole.ANIMATOR.value,
        AgentRole.SOUND_DIRECTOR.value,
    }
    assert AgentRole.DIRECTOR.value not in result["roles"]


def test_runner_custom_stage_can_observe_context():
    observed: list = []

    def spy(ctx: PipelineContext) -> PipelineContext:
        observed.append(ctx.script)
        return ctx

    runner = PipelineRunner(stages=[create_scriptwriter_stage(), spy])
    runner.run(idea="a robot learns to dream")
    assert observed and observed[0]
