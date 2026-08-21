"""TDD tests for the /v1/generate smart-flow endpoint.

These tests exercise the real HTTP surface exposed by backend/app/api/v1/generate.py
and assert behavior tied to PLAN.md acceptance criteria for the Smart one-click
orchestrator: it must enqueue a job, return a job_id, and the job must progress
through the 7-agent pipeline stages.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.agents.pipeline import AgentRole


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)


def _post_smart(client: TestClient, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    resp = client.post("/api/v1/generate/smart", json=payload)
    return resp.status_code, resp.json()


def test_smart_generate_accepts_valid_request_and_returns_job_id(client: TestClient) -> None:
    status, body = _post_smart(client, {
        "idea": "A lone astronaut discovers a garden growing inside a derelict station.",
        "style_id": "anime-cinematic",
        "model_ids": ["pollinations/flux"],
    })
    assert status == 202, body
    assert "job_id" in body
    assert isinstance(body["job_id"], str) and len(body["job_id"]) > 0
    assert body["status"] in {"queued", "running", "completed"}


def test_smart_generate_rejects_empty_idea(client: TestClient) -> None:
    status, body = _post_smart(client, {
        "idea": "   ",
        "style_id": "anime-cinematic",
        "model_ids": ["pollinations/flux"],
    })
    assert status == 422, body
    assert "idea" in str(body).lower()


def test_smart_generate_rejects_missing_model_ids(client: TestClient) -> None:
    status, body = _post_smart(client, {
        "idea": "A cat learns to play piano.",
        "style_id": "anime-cinematic",
    })
    assert status == 422, body


def test_smart_generate_rejects_empty_model_ids_list(client: TestClient) -> None:
    status, body = _post_smart(client, {
        "idea": "A cat learns to play piano.",
        "style_id": "anime-cinematic",
        "model_ids": [],
    })
    assert status == 422, body


def test_job_status_endpoint_returns_pipeline_progress(client: TestClient) -> None:
    _, body = _post_smart(client, {
        "idea": "Rain falls upward on a neon-lit Tokyo street.",
        "style_id": "cyberpunk-neon",
        "model_ids": ["pollinations/flux"],
    })
    job_id = body["job_id"]

    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200, resp.text
    status_body = resp.json()
    assert status_body["job_id"] == job_id
    assert "status" in status_body
    assert "stages" in status_body
    # The pipeline must expose all 7 production agents plus the director.
    expected_roles = {r.value for r in AgentRole}
    stage_roles = {s["agent"] for s in status_body["stages"]}
    assert expected_roles.issubset(stage_roles), (
        f"missing roles: {expected_roles - stage_roles}"
    )


def test_job_status_404_for_unknown_job(client: TestClient) -> None:
    resp = client.get("/api/v1/jobs/does-not-exist-12345")
    assert resp.status_code == 404


def test_smart_generate_persists_job_across_requests(client: TestClient) -> None:
    _, body = _post_smart(client, {
        "idea": "A paper boat sails across an endless ocean of stars.",
        "style_id": "illustrated-dreamy",
        "model_ids": ["pollinations/flux"],
    })
    job_id = body["job_id"]

    # A second GET on a fresh client must still find the job (persistence).
    fresh = TestClient(app)
    resp = fresh.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["job_id"] == job_id


def test_smart_generate_records_idea_and_style_on_job(client: TestClient) -> None:
    idea = "A hummingbird frozen in mid-air as the world blurs past it."
    style_id = "photographic-macro"
    _, body = _post_smart(client, {
        "idea": idea,
        "style_id": style_id,
        "model_ids": ["pollinations/flux"],
    })
    job_id = body["job_id"]

    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["idea"] == idea
    assert detail["style_id"] == style_id
    assert detail["model_ids"] == ["pollinations/flux"]


def test_smart_generate_job_eventually_reaches_terminal_state(client: TestClient) -> None:
    _, body = _post_smart(client, {
        "idea": "Two children build a sandcastle that becomes a real kingdom.",
        "style_id": "anime-cinematic",
        "model_ids": ["pollinations/flux"],
    })
    job_id = body["job_id"]

    # The synchronous test pipeline runs to completion within the request lifecycle,
    # so a follow-up GET must show a terminal status (completed or failed).
    resp = client.get(f"/api/v1/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] in {"completed", "failed"}


def test_list_jobs_returns_all_submitted_jobs(client: TestClient) -> None:
    _, b1 = _post_smart(client, {
        "idea": "A candle flame that refuses to go out in a storm.",
        "style_id": "painting-oil",
        "model_ids": ["pollinations/flux"],
    })
    _, b2 = _post_smart(client, {
        "idea": "A robot tends a garden of clockwork flowers.",
        "style_id": "3d-pixar",
        "model_ids": ["pollinations/flux"],
    })

    resp = client.get("/api/v1/jobs")
    assert resp.status_code == 200
    data = resp.json()
    items = data["items"] if isinstance(data, dict) and "items" in data else data
    ids = {item["job_id"] for item in items}
    assert b1["job_id"] in ids
    assert b2["job_id"] in ids
