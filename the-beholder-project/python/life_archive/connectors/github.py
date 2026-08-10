"""GitHub connector for Life Archive.

Fetches issues, pull requests, and releases for the authenticated user's
repositories via the GitHub REST API. Unlike the `git` connector (which
bundles local clones with no credentials), this connector requires a GitHub
Personal Access Token (PAT) with `repo`, `read:user`, `read:org`,
`user:email`, `read:project`, `read:packages` scopes
(see `04_CREDENTIAL_REQUIREMENTS.md`).

The HTTP client is dependency-injected so tests can run against a mocked
transport without a real token or network access.
"""

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Callable

import httpx
import orjson

from life_archive.hash import hash_bytes_sha256
from life_archive.manifest import ManifestReader, ManifestWriter, create_archive_id
from life_archive.schemas.provenance import (
    AcquiredItem,
    ConnectorResult,
    DedupeStatus,
    DiscoveredItem,
    ForensicStatus,
    HashedItem,
    IngestionRun,
    ManifestEntry,
    PrivacyClassification,
    ProcessingStatus,
    StoredItem,
    VerifiedItem,
)
from life_archive.storage import LocalFilesystemStorage

CONNECTOR_ID = "github"
GITHUB_API_BASE = "https://api.github.com"


class GitHubAuthError(RuntimeError):
    """Raised when no GitHub PAT is configured."""


def _parse_link_header(link_header: str | None) -> dict[str, str]:
    """Parse a GitHub `Link` header into {rel: url} pairs."""
    links: dict[str, str] = {}
    if not link_header:
        return links
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        rel = None
        for seg in segments[1:]:
            seg = seg.strip()
            if seg.startswith('rel="') and seg.endswith('"'):
                rel = seg[5:-1]
        if rel:
            links[rel] = url
    return links


class GitHubConnector:
    """Connector for ingesting GitHub repository activity via the REST API."""

    def __init__(
        self,
        archive_root: Path,
        token: str | None = None,
        http_client: httpx.Client | None = None,
        repos: list[str] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ):
        """Initialize the GitHub connector.

        Args:
            archive_root: Path to LIFE_ARCHIVE/ directory
            token: GitHub PAT. If not provided, falls back to the
                `GITHUB_PAT` environment variable at run() time.
            http_client: Pre-configured httpx.Client (for testing/mocking).
                If not provided, a real client is built against the GitHub
                API using the resolved token.
            repos: Optional explicit list of "owner/repo" strings to
                process, skipping the `/user/repos` discovery call (useful
                to scope a fine-grained PAT, or for tests).
            sleep_fn: Function used to wait out rate-limit windows
                (injectable for tests to avoid real delays).
        """
        self.archive_root = Path(archive_root)
        self._token = token
        self._injected_client = http_client
        self.repos = repos
        self.sleep_fn = sleep_fn

        self.raw_storage = LocalFilesystemStorage(self.archive_root / "00_RAW")
        self.manifest_writer = ManifestWriter(self.archive_root / "01_MANIFEST")
        self.manifest_reader = ManifestReader(self.archive_root / "01_MANIFEST")

    def _resolve_token(self) -> str | None:
        if self._token:
            return self._token
        import os

        return os.environ.get("GITHUB_PAT")

    def _build_client(self) -> httpx.Client:
        if self._injected_client is not None:
            return self._injected_client

        token = self._resolve_token()
        if not token:
            raise GitHubAuthError(
                "GitHub PAT not configured. Set the GITHUB_PAT environment "
                "variable or pass token= explicitly. See "
                "04_CREDENTIAL_REQUIREMENTS.md for required scopes."
            )

        return httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "life-archive-connector",
            },
            timeout=30.0,
        )

    def _get_paginated(self, client: httpx.Client, url: str, params: dict | None = None) -> list[dict]:
        """GET all pages of a paginated GitHub API endpoint, with basic
        rate-limit backoff."""
        results: list[dict] = []
        next_url: str | None = url
        next_params: dict | None = params

        while next_url:
            response = self._request_with_backoff(client, next_url, next_params)
            data = response.json()
            if isinstance(data, list):
                results.extend(data)
            links = _parse_link_header(response.headers.get("Link"))
            next_url = links.get("next")
            next_params = None  # `next` URL already includes query params

        return results

    def _request_with_backoff(
        self, client: httpx.Client, url: str, params: dict | None, max_retries: int = 3
    ) -> httpx.Response:
        response = client.get(url, params=params)

        for attempt in range(max_retries):
            remaining = response.headers.get("X-RateLimit-Remaining")
            if response.status_code != 403 or remaining != "0":
                break

            reset = response.headers.get("X-RateLimit-Reset")
            wait_seconds = 1.0
            if reset:
                try:
                    wait_seconds = max(0.0, float(reset) - time.time())
                except ValueError:
                    pass
            self.sleep_fn(min(wait_seconds, 60.0))
            response = client.get(url, params=params)

        response.raise_for_status()
        return response

    async def discover(self) -> AsyncIterator[DiscoveredItem]:
        """Discover repositories (owned + contributor) for the authenticated user.

        Raises:
            GitHubAuthError: If no PAT is configured.
        """
        client = self._build_client()

        if self.repos:
            repo_dicts = [{"full_name": name} for name in self.repos]
        else:
            repo_dicts = self._get_paginated(
                client,
                "/user/repos",
                params={"per_page": 100, "affiliation": "owner,collaborator,organization_member"},
            )

        for repo in repo_dicts:
            full_name = repo["full_name"]
            owner, _, repo_name = full_name.partition("/")
            updated_at = repo.get("updated_at")
            mtime = (
                datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                if updated_at
                else datetime.utcnow()
            )

            yield DiscoveredItem(
                source_identifier=full_name,
                source_path=repo.get("html_url", f"https://github.com/{full_name}"),
                relative_path=full_name,
                size_bytes=0,
                mtime=mtime.replace(tzinfo=None),
                mime_type="application/json",
                metadata={"owner": owner, "repo": repo_name, "full_name": full_name},
            )

    async def acquire(self, item: DiscoveredItem) -> AcquiredItem:
        """Fetch issues, pull requests, and releases for the repository."""
        client = self._build_client()
        owner = item.metadata["owner"]
        repo = item.metadata["repo"]

        all_issues = self._get_paginated(
            client,
            f"/repos/{owner}/{repo}/issues",
            params={"state": "all", "per_page": 100},
        )
        # GitHub's issues endpoint includes PRs (flagged via "pull_request").
        issues = [i for i in all_issues if "pull_request" not in i]
        pulls = [i for i in all_issues if "pull_request" in i]
        releases = self._get_paginated(
            client,
            f"/repos/{owner}/{repo}/releases",
            params={"per_page": 100},
        )

        metadata = dict(item.metadata)
        metadata["issues"] = issues
        metadata["pulls"] = pulls
        metadata["releases"] = releases

        return AcquiredItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=item.source_path,  # No local file; API-sourced data
        )

    async def verify(self, item: AcquiredItem) -> VerifiedItem:
        """Basic sanity check on fetched data."""
        metadata = dict(item.metadata)
        counts = {
            "issue_count": len(metadata.get("issues", [])),
            "pull_count": len(metadata.get("pulls", [])),
            "release_count": len(metadata.get("releases", [])),
        }
        metadata.update(counts)

        return VerifiedItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=item.staging_path,
            extracted_metadata=counts,
        )

    def hash(self, item: VerifiedItem) -> HashedItem:
        """Hash the canonical (sorted-key) JSON snapshot of fetched data.

        There is no single canonical byte-stream from a REST API response
        set, so — consistent with the Google Takeout/LinkedIn connectors'
        directory-hashing fallback — we hash a deterministic serialization
        of the fetched issues/pulls/releases.
        """
        snapshot = {
            "issues": item.metadata.get("issues", []),
            "pulls": item.metadata.get("pulls", []),
            "releases": item.metadata.get("releases", []),
        }
        canonical = orjson.dumps(snapshot, option=orjson.OPT_SORT_KEYS)
        sha256 = hash_bytes_sha256(canonical)

        return HashedItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=item.metadata,
            staging_path=item.staging_path,
            sha256=sha256,
            xxhash64=None,
        )

    async def store(self, item: HashedItem, run_id: str) -> StoredItem:
        """Store raw issues/pulls/releases JSON under 00_RAW/github/{owner}/{repo}/."""
        owner = item.metadata["owner"]
        repo = item.metadata["repo"]
        full_name = item.metadata["full_name"]

        dedupe_status = DedupeStatus.UNIQUE
        dedupe_of = None
        existing = self.manifest_reader.get_entry_by_sha256(item.sha256)
        if existing is not None:
            dedupe_status = DedupeStatus.DUPLICATE_OF
            dedupe_of = existing.archive_id

        manifest_entry = ManifestEntry(
            archive_id=create_archive_id(item.sha256),
            source=CONNECTOR_ID,
            source_identifier=item.source_identifier,
            original_filename=f"{owner}/{repo}/snapshot.json",
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            original_timestamp=item.mtime,
            acquisition_timestamp=datetime.utcnow(),
            sha256=item.sha256,
            xxhash64=item.xxhash64,
            connector=CONNECTOR_ID,
            ingestion_run_id=run_id,
            privacy_classification=PrivacyClassification.PRIVATE,
            processing_status=ProcessingStatus.STORED,
            dedupe_status=dedupe_status,
            dedupe_of=dedupe_of,
        )

        archive_path = f"00_RAW/github/{owner}/{repo}/snapshot.json"

        if dedupe_status != DedupeStatus.DUPLICATE_OF:
            for kind in ("issues", "pulls", "releases"):
                payload = item.metadata.get(kind, [])
                self.raw_storage.put(
                    f"github/{owner}/{repo}/{kind}.json",
                    orjson.dumps(payload, option=orjson.OPT_SORT_KEYS | orjson.OPT_INDENT_2),
                )
            self.raw_storage.put(
                f"github/{owner}/{repo}/snapshot.json",
                orjson.dumps(
                    {
                        "full_name": full_name,
                        "sha256": item.sha256,
                        "issue_count": item.metadata.get("issue_count", 0),
                        "pull_count": item.metadata.get("pull_count", 0),
                        "release_count": item.metadata.get("release_count", 0),
                    },
                    option=orjson.OPT_INDENT_2,
                ),
            )

        return StoredItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=item.metadata,
            staging_path=item.staging_path,
            sha256=item.sha256,
            xxhash64=item.xxhash64,
            archive_path=archive_path,
            manifest_entry=manifest_entry,
        )

    async def index(self, item: StoredItem) -> StoredItem:
        """Index issue/PR bodies for search. Stub pending Meilisearch/Qdrant.

        TODO: Full-text index issue/PR bodies + embeddings; code references
        as entities.
        """
        return item

    async def normalize(self, item: StoredItem) -> StoredItem:
        """Map to GitHubRepository/Issue/PullRequest/Release schemas.

        TODO: Emit GitHubRepository, GitHubIssue, GitHubPullRequest,
        GitHubComment, GitHubRelease, GitHubWorkflowRun records once
        schemas are finalized.
        """
        return item

    def log(self, item: StoredItem, run_id: str) -> None:
        """Write manifest entries for the stored repository snapshot."""
        entry = item.manifest_entry

        self.manifest_writer.write_manifest_entry(entry)
        self.manifest_writer.write_hash_record(
            archive_id=entry.archive_id,
            sha256=item.sha256,
            xxhash64=item.xxhash64,
        )
        self.manifest_writer.write_acquisition_log(
            archive_id=entry.archive_id,
            source=entry.source,
            action="stored",
            details={
                "archive_path": item.archive_path,
                "issue_count": item.metadata.get("issue_count", 0),
                "pull_count": item.metadata.get("pull_count", 0),
                "release_count": item.metadata.get("release_count", 0),
            },
        )

    async def run(self, max_items: int | None = None) -> ConnectorResult:
        """Execute the full ingestion pipeline across all discovered repos."""
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        items_discovered = 0
        items_processed = 0
        items_failed = 0
        items_skipped = 0
        bytes_processed = 0
        errors: list[str] = []

        try:
            # Fail fast (and clearly) if no credentials are configured,
            # rather than silently discovering zero items.
            self._build_client()

            async for discovered_item in self.discover():
                items_discovered += 1

                if max_items and items_processed >= max_items:
                    items_skipped += 1
                    continue

                try:
                    acquired = await self.acquire(discovered_item)
                    verified = await self.verify(acquired)
                    hashed = self.hash(verified)
                    stored = await self.store(hashed, run_id)
                    indexed = await self.index(stored)
                    normalized = await self.normalize(indexed)
                    self.log(normalized, run_id)
                    items_processed += 1

                except Exception as e:
                    items_failed += 1
                    errors.append(
                        f"{discovered_item.source_identifier}: {type(e).__name__}: {e}"
                    )

            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            if items_failed == 0:
                status = ForensicStatus.PASS
            elif items_processed > 0:
                status = ForensicStatus.PARTIAL
            else:
                status = ForensicStatus.FAIL

            run_record = IngestionRun(
                run_id=run_id,
                connector=CONNECTOR_ID,
                start_time=start_time,
                end_time=end_time,
                status=status.value,
                items_discovered=items_discovered,
                items_processed=items_processed,
                items_failed=items_failed,
                items_skipped=items_skipped,
                bytes_processed=bytes_processed,
                config_hash="github_config_v1",
            )
            self.manifest_writer.write_ingestion_run(run_record)

            return ConnectorResult(
                run_id=run_id,
                connector=CONNECTOR_ID,
                status=status,
                items_discovered=items_discovered,
                items_processed=items_processed,
                items_failed=items_failed,
                items_skipped=items_skipped,
                bytes_processed=bytes_processed,
                duration_seconds=duration,
                errors=errors,
                forensic_evidence={
                    "manifest_entries_written": items_processed,
                    "hash_records_written": items_processed,
                    "acquisition_logs_written": items_processed,
                },
            )

        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            run_record = IngestionRun(
                run_id=run_id,
                connector=CONNECTOR_ID,
                start_time=start_time,
                end_time=end_time,
                status=ForensicStatus.FAIL.value,
                items_discovered=items_discovered,
                items_processed=items_processed,
                items_failed=items_failed,
                items_skipped=items_skipped,
                error=str(e),
            )
            self.manifest_writer.write_ingestion_run(run_record)

            return ConnectorResult(
                run_id=run_id,
                connector=CONNECTOR_ID,
                status=ForensicStatus.FAIL,
                items_discovered=items_discovered,
                items_processed=items_processed,
                items_failed=items_failed,
                items_skipped=items_skipped,
                bytes_processed=0,
                duration_seconds=duration,
                errors=[f"Fatal error: {type(e).__name__}: {e}"] + errors,
                forensic_evidence={},
            )
