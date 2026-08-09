"""GitHub connector behavior: mocked API pagination, rate-limit backoff, and
provenance/idempotency regression tests. No real network access or PAT is
used — the HTTP client is fully mocked via httpx.MockTransport."""

import asyncio
from pathlib import Path

import httpx
import orjson
import pytest

from life_archive.connectors.github import GitHubAuthError, GitHubConnector
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus, ForensicStatus

REPO = {
    "full_name": "octocat/hello-world",
    "html_url": "https://github.com/octocat/hello-world",
    "updated_at": "2026-01-01T00:00:00Z",
}

ISSUE = {"id": 1, "title": "A bug", "body": "Something is broken"}
PULL_AS_ISSUE = {"id": 2, "title": "A fix", "pull_request": {"url": "https://api.github.com/x"}}
RELEASE = {"id": 10, "tag_name": "v1.0.0", "name": "First release"}


def _make_archive(tmp_path: Path) -> Path:
    return tmp_path / "LIFE_ARCHIVE"


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/user/repos":
        return httpx.Response(200, json=[REPO], headers={})
    if path == "/repos/octocat/hello-world/issues":
        return httpx.Response(200, json=[ISSUE, PULL_AS_ISSUE])
    if path == "/repos/octocat/hello-world/releases":
        return httpx.Response(200, json=[RELEASE])
    return httpx.Response(404, json={"message": "not found"})


def _make_connector(archive_root: Path, repos=None) -> GitHubConnector:
    transport = httpx.MockTransport(_mock_handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    return GitHubConnector(archive_root=archive_root, http_client=client, repos=repos)


def test_pipeline_fetches_and_splits_issues_and_pulls(tmp_path):
    archive_root = _make_archive(tmp_path)
    connector = _make_connector(archive_root)

    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1
    assert result.items_failed == 0

    base = archive_root / "00_RAW" / "github" / "octocat" / "hello-world"
    issues = orjson.loads((base / "issues.json").read_bytes())
    pulls = orjson.loads((base / "pulls.json").read_bytes())
    releases = orjson.loads((base / "releases.json").read_bytes())

    assert len(issues) == 1
    assert issues[0]["id"] == 1
    assert len(pulls) == 1
    assert pulls[0]["id"] == 2
    assert len(releases) == 1
    assert releases[0]["id"] == 10

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.connector == "github"
    assert entry.source == "github"
    assert entry.dedupe_status == DedupeStatus.UNIQUE


def test_explicit_repos_list_skips_discovery_call(tmp_path):
    archive_root = _make_archive(tmp_path)
    connector = _make_connector(archive_root, repos=["octocat/hello-world"])

    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1


def test_rerun_is_idempotent_and_does_not_duplicate(tmp_path):
    archive_root = _make_archive(tmp_path)
    connector1 = _make_connector(archive_root)
    asyncio.run(connector1.run())

    connector2 = _make_connector(archive_root)
    result = asyncio.run(connector2.run())

    assert result.status == ForensicStatus.PASS
    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.DUPLICATE_OF


def test_pagination_follows_link_header(tmp_path):
    archive_root = _make_archive(tmp_path)
    page2_repo = {**REPO, "full_name": "octocat/second-repo"}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/repos" and "page=2" not in str(request.url):
            return httpx.Response(
                200,
                json=[REPO],
                headers={"Link": '<https://api.github.com/user/repos?page=2>; rel="next"'},
            )
        if request.url.path == "/user/repos":
            return httpx.Response(200, json=[page2_repo])
        if "issues" in request.url.path:
            return httpx.Response(200, json=[])
        if "releases" in request.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    connector = GitHubConnector(archive_root=archive_root, http_client=client)

    result = asyncio.run(connector.run())

    assert result.items_discovered == 2


def test_missing_token_fails_gracefully_without_injected_client(tmp_path):
    archive_root = _make_archive(tmp_path)
    connector = GitHubConnector(archive_root=archive_root, token=None)

    # Ensure no ambient GITHUB_PAT leaks into the test from the environment.
    import os

    original = os.environ.pop("GITHUB_PAT", None)
    try:
        result = asyncio.run(connector.run())
    finally:
        if original is not None:
            os.environ["GITHUB_PAT"] = original

    assert result.status == ForensicStatus.FAIL
    assert result.items_discovered == 0
    assert any("GitHub PAT" in e for e in result.errors)


def test_rate_limit_triggers_backoff_then_succeeds(tmp_path):
    archive_root = _make_archive(tmp_path)
    call_count = {"n": 0}
    sleep_calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/repos":
            call_count["n"] += 1
            if call_count["n"] == 1:
                return httpx.Response(
                    403,
                    json={"message": "rate limited"},
                    headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "0"},
                )
            return httpx.Response(200, json=[REPO])
        if "issues" in request.url.path:
            return httpx.Response(200, json=[])
        if "releases" in request.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    connector = GitHubConnector(
        archive_root=archive_root,
        http_client=client,
        sleep_fn=lambda s: sleep_calls.append(s),
    )

    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert len(sleep_calls) == 1  # backed off exactly once before succeeding
