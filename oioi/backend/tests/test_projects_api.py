"""TDD tests for the /v1/projects REST surface.

These tests exercise the real SQLite-backed CRUD handlers in
`backend/app/api/v1/projects.py` through FastAPI's TestClient. They assert
actual behavior — created rows are persisted, filters narrow results,
soft-deletes hide rows, and the 'recently opened' ordering is correct.
"""

from __future__ import annotations

import os
import sqlite3
import time
from collections import deque

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.v1 import projects as projects_module
from backend.app.api.v1.projects import router


# ---------------------------------------------------------------------------
# Fixtures — isolate each test against a fresh in-memory-ish DB by redirecting
# the module-level DB_PATH to a temp file and wiping it between tests.
# ---------------------------------------------------------------------------


@pytest.fixture()
def app(tmp_path, monkeypatch) -> FastAPI:
    db_file = str(tmp_path / "projects_test.db")
    monkeypatch.setattr(projects_module, "DB_PATH", db_file)
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def sample_payload() -> dict:
    return {
        "name": "Neon Short",
        "kind": "story_anime",
        "idea": "A lone neon samurai walks through rain-soaked Tokyo at dawn.",
        "style_id": "style.anime.cinematic",
        "model_ids": ["groq/llama-3.3-70b", "pollinations/flux-anime"],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_project_returns_201_with_real_fields(client, sample_payload):
    res = client.post("/v1/projects", json=sample_payload)
    assert res.status_code == 201
    body = res.json()
    assert body["id"]
    assert body["name"] == "Neon Short"
    assert body["kind"] == "story_anime"
    assert body["status"] == "draft"
    assert body["model_ids"] == ["groq/llama-3.3-70b", "pollinations/flux-anime"]
    assert body["style_id"] == "style.anime.cinematic"
    assert isinstance(body["created_at"], int)
    assert body["opened_at"] is None


def test_create_project_rejects_invalid_kind(client, sample_payload):
    sample_payload["kind"] = "not_a_real_kind"
    res = client.post("/v1/projects", json=sample_payload)
    assert res.status_code == 422


def test_get_project_returns_persisted_row(client, sample_payload):
    pid = client.post("/v1/projects", json=sample_payload).json()["id"]
    res = client.get(f"/v1/projects/{pid}")
    assert res.status_code == 200
    assert res.json()["id"] == pid


def test_get_project_404_for_unknown_id(client):
    res = client.get("/v1/projects/does-not-exist")
    assert res.status_code == 404


def test_list_projects_pagination_and_order(client, sample_payload):
    # Create 3 projects with distinct names
    for i in range(3):
        payload = dict(sample_payload, name=f"P{i}")
        r = client.post("/v1/projects", json=payload)
        assert r.status_code == 201
        time.sleep(0.01)  # ensure distinct created_at ordering

    res = client.get("/v1/projects?page=1&page_size=2")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2
    # newest first
    assert body["items"][0]["name"] == "P2"
    assert body["items"][1]["name"] == "P1"

    res2 = client.get("/v1/projects?page=2&page_size=2")
    assert res2.json()["items"][0]["name"] == "P0"


def test_list_projects_filter_by_kind(client, sample_payload):
    client.post("/v1/projects", json=dict(sample_payload, kind="story_anime"))
    client.post("/v1/projects", json=dict(sample_payload, kind="music_video"))
    res = client.get("/v1/projects?kind=music_video")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["kind"] == "music_video"


def test_update_project_changes_fields(client, sample_payload):
    pid = client.post("/v1/projects", json=sample_payload).json()["id"]
    res = client.patch(
        f"/v1/projects/{pid}",
        json={"name": "Renamed", "status": "generating", "model_ids": ["x"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Renamed"
    assert body["status"] == "generating"
    assert body["model_ids"] == ["x"]


def test_update_project_rejects_invalid_status(client, sample_payload):
    pid = client.post("/v1/projects", json=sample_payload).json()["id"]
    res = client.patch(f"/v1/projects/{pid}", json={"status": "bogus"})
    assert res.status_code == 422


def test_update_project_404_for_unknown_id(client):
    res = client.patch("/v1/projects/missing", json={"name": "x"})
    assert res.status_code == 404


def test_delete_project_soft_deletes_and_hides_from_list(client, sample_payload):
    pid = client.post("/v1/projects", json=sample_payload).json()["id"]
    del_res = client.delete(f"/v1/projects/{pid}")
    assert del_res.status_code == 204
    # Now hidden from list
    assert client.get("/v1/projects").json()["total"] == 0
    # And direct get 404s
    assert client.get(f"/v1/projects/{pid}").status_code == 404
    # Re-delete is 404 (already soft-deleted)
    assert client.delete(f"/v1/projects/{pid}").status_code == 404


def test_open_project_records_opened_at_and_orders_recent(client, sample_payload):
    p1 = client.post("/v1/projects", json=dict(sample_payload, name="First")).json()["id"]
    p2 = client.post("/v1/projects", json=dict(sample_payload, name="Second")).json()["id"]
    # Open the older one last so it should appear first in /recent
    client.post(f"/v1/projects/{p1}/open")
    time.sleep(0.01)
    client.post(f"/v1/projects/{p2}/open")
    time.sleep(0.01)
    client.post(f"/v1/projects/{p1}/open")  # re-open p1 -> most recent

    res = client.get("/v1/projects/recent")
    assert res.status_code == 200
    items = res.json()["items"]
    assert items[0]["id"] == p1
    assert items[1]["id"] == p2
    assert all(it["opened_at"] is not None for it in items)


def test_open_project_404_for_unknown_id(client):
    assert client.post("/v1/projects/missing/open").status_code == 404


def test_recent_excludes_unopened_projects(client, sample_payload):
    client.post("/v1/projects", json=sample_payload)  # never opened
    res = client.get("/v1/projects/recent")
    assert res.json()["total"] == 0


def test_update_with_no_fields_returns_400(client, sample_payload):
    pid = client.post("/v1/projects", json=sample_payload).json()["id"]
    res = client.patch(f"/v1/projects/{pid}", json={})
    assert res.status_code == 400


def test_persistence_survives_new_connection(client, sample_payload, tmp_path, monkeypatch):
    # The DB file must actually persist across connections — proves the
    # handler is not using an in-memory throwaway.
    pid = client.post("/v1/projects", json=sample_payload).json()["id"]

    # Spin a second app pointed at the same DB file
    db_file = projects_module.DB_PATH
    app2 = FastAPI()
    app2.include_router(router)
    client2 = TestClient(app2)
    res = client2.get(f"/v1/projects/{pid}")
    assert res.status_code == 200
    assert res.json()["name"] == "Neon Short"
