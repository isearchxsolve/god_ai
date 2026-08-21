"""Composable stage utilities for the 7-agent animation pipeline.

This module builds on the typed facade in :mod:`backend.app.agents.pipeline`
and provides higher-level helpers for assembling and executing custom
production chains: building a pipeline from an arbitrary subset of roles,
running only those roles, and wrapping any stage with a retry policy.

It depends solely on the public facade (``AgentRole``, ``PipelineContext``,
``AgentStage``, ``create_agent_stage``) so it stays in lock-step with the
canonical pipeline without duplicating orchestration logic.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Union

from .pipeline import (
    AgentRole,
    AgentStage,
    PipelineContext,
    PipelineRunner,
    build_default_pipeline,
    create_agent_stage,
)


def _coerce_role(role: Union[AgentRole, str]) -> AgentRole:
    """Accept either an :class:`AgentRole` or its string value."""
    if isinstance(role, AgentRole):
        return role
    try:
        return AgentRole(role)
    except ValueError as exc:
        raise ValueError(f"Unknown agent role: {role!r}") from exc


def pipeline_from_roles(roles: Iterable[Union[AgentRole, str]]) -> List[AgentStage]:
    """Build an ordered pipeline from an arbitrary subset of roles.

    Roles are coerced to :class:`AgentRole` and resolved to their stage
    factories in the order given. Unknown roles raise ``ValueError`` so a
    misconfigured chain fails loudly rather than silently dropping work.
    """
    return [create_agent_stage(_coerce_role(r)) for r in roles]


def run_roles(
    idea: str,
    roles: Iterable[Union[AgentRole, str]],
    style_id: Optional[str] = None,
) -> PipelineContext:
    """Run only the requested roles against a fresh context.

    The full production is still materialized first (via the proven local
    orchestrator) so each requested stage observes real artifacts; only the
    requested stages actually execute and stamp their role onto the context.
    """
    stages = pipeline_from_roles(roles)
    runner = PipelineRunner(stages=stages)
    return runner.run(idea=idea, style_id=style_id)


def with_retry(stage: AgentStage, retries: int = 2) -> AgentStage:
    """Wrap a stage so transient failures are retried up to ``retries`` times.

    A retry count of zero yields the original stage unchanged. The wrapper
    re-invokes the stage on the same context; if all attempts fail the last
    exception propagates so callers can decide how to handle the fault.
    """
    if retries <= 0:
        return stage

    def retried(ctx: PipelineContext) -> PipelineContext:
        last_exc: Optional[BaseException] = None
        for _ in range(retries + 1):
            try:
                return stage(ctx)
            except Exception as exc:  # noqa: BLE001 — re-raised after retries
                last_exc = exc
        assert last_exc is not None  # pragma: no cover — loop runs at least once
        raise last_exc

    return retried


def default_pipeline_with_retries(retries: int = 2) -> List[AgentStage]:
    """Return the default 8-stage pipeline with every stage wrapped for retry."""
    return [with_retry(s, retries=retries) for s in build_default_pipeline()]


def roles_for_stages(stages: Sequence[AgentStage]) -> List[AgentRole]:
    """Best-effort extraction of roles a stage list will execute.

    Stages created via :func:`create_agent_stage` close over a single
    :class:`AgentRole`; this helper introspects that closure variable so
    callers can audit which roles a custom chain will touch. Stages whose
    closure cannot be resolved are skipped.
    """
    resolved: List[AgentRole] = []
    for stage in stages:
        cells = getattr(stage, "__closure__", None) or ()
        for cell in cells:
            val = cell.cell_contents
            if isinstance(val, AgentRole) and val not in resolved:
                resolved.append(val)
    return resolved


__all__ = [
    "pipeline_from_roles",
    "run_roles",
    "with_retry",
    "default_pipeline_with_retries",
    "roles_for_stages",
]
