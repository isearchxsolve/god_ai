"""Git connector for Life Archive.

Discovers local Git repositories, bundles their full history, and records
commit metadata. This connector requires only the `git` CLI on PATH — no
credentials or network access are needed (unlike the GitHub connector, which
talks to the GitHub API).

Pipeline: discover -> acquire -> verify -> hash -> store -> index ->
normalize -> log, matching the pattern established by LocalFilesConnector.
"""

import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

import orjson

from life_archive.hash import compute_file_hashes
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
from life_archive.storage import LocalFilesystemStorage, StoragePathBuilder

CONNECTOR_ID = "git"


class GitCommandError(RuntimeError):
    """Raised when a `git` subprocess invocation fails."""


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout, raising on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitCommandError(
            f"git {' '.join(args)} failed in {cwd}: {result.stderr.strip()}"
        )
    return result.stdout


class GitConnector:
    """Connector for ingesting local Git repository history.

    For each discovered repository, this connector:
    - Creates a full `git bundle` (all branches/tags/history) as the
      immutable raw artifact (RULE 2).
    - Extracts commit metadata (SHA, author, committer, date, message) for
      normalization into `03_NORMALIZED/git_commits/`.
    - Records remotes and branch names for provenance.

    Incremental behavior: because the bundle's SHA-256 changes whenever the
    repository's history changes, re-running the connector on an unchanged
    repository naturally dedupes via the same content-addressed mechanism
    used by LocalFilesConnector, without needing a separate checkpoint file.
    """

    def __init__(
        self,
        archive_root: Path,
        scan_paths: list[Path] | None = None,
    ):
        """Initialize the Git connector.

        Args:
            archive_root: Path to LIFE_ARCHIVE/ directory
            scan_paths: Roots to search for `.git` directories (default:
                [00_RAW/git/repos] so that placed/cloned repos are picked up
                without also re-scanning connector output)
        """
        self.archive_root = Path(archive_root)
        self.scan_paths = scan_paths or [self.archive_root / "00_RAW" / "git" / "repos"]

        self.raw_storage = LocalFilesystemStorage(self.archive_root / "00_RAW")
        self.normalized_storage = LocalFilesystemStorage(self.archive_root / "03_NORMALIZED")

        self.manifest_writer = ManifestWriter(self.archive_root / "01_MANIFEST")
        self.manifest_reader = ManifestReader(self.archive_root / "01_MANIFEST")

        self.path_builder = StoragePathBuilder()

    async def discover(self) -> AsyncIterator[DiscoveredItem]:
        """Discover Git repositories under the configured scan paths.

        Yields one DiscoveredItem per repository root (identified by the
        presence of a `.git` directory).
        """
        for scan_path in self.scan_paths:
            if not scan_path.exists():
                continue

            for git_dir in scan_path.rglob(".git"):
                if not git_dir.is_dir():
                    continue

                repo_root = git_dir.parent

                try:
                    relative_path = repo_root.relative_to(scan_path)
                except ValueError:
                    relative_path = repo_root.name

                stat = git_dir.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)

                yield DiscoveredItem(
                    source_identifier=str(relative_path),
                    source_path=str(repo_root),
                    relative_path=str(relative_path),
                    size_bytes=0,  # Unknown until bundled
                    mtime=mtime,
                    mime_type="application/x-git-bundle",
                    metadata={
                        "repo_name": repo_root.name,
                        "repo_root": str(repo_root),
                    },
                )

    async def acquire(self, item: DiscoveredItem) -> AcquiredItem:
        """Bundle the repository's full history and extract commit metadata.

        Args:
            item: Discovered repository item

        Returns:
            AcquiredItem with staging_path pointing at the created bundle

        Raises:
            GitCommandError: If the repository has no commits, or any git
                command fails.
        """
        repo_root = Path(item.metadata["repo_root"])
        repo_name = item.metadata["repo_name"]

        # NOTE: intentionally not cleaned up here; store() consumes the
        # bundle from this path, and OS temp cleanup reclaims it later.
        staging_dir = Path(tempfile.mkdtemp(prefix="life_archive_git_"))
        bundle_path = staging_dir / f"{repo_name}.bundle"

        # `git bundle create` requires at least one commit.
        _run_git(["bundle", "create", str(bundle_path), "--all"], cwd=repo_root)

        commits = self._extract_commits(repo_root)
        remotes = self._extract_remotes(repo_root)
        branches = self._extract_branches(repo_root)

        metadata = dict(item.metadata)
        metadata.update(
            {
                "commit_count": len(commits),
                "commits": commits,
                "remotes": remotes,
                "branches": branches,
                "head_sha": commits[0]["sha"] if commits else None,
            }
        )

        return AcquiredItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=bundle_path.stat().st_size,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=str(bundle_path),
        )

    async def verify(self, item: AcquiredItem) -> VerifiedItem:
        """Verify the created bundle is structurally valid.

        Args:
            item: Acquired item with bundle at staging_path

        Returns:
            VerifiedItem

        Raises:
            GitCommandError: If `git bundle verify` fails
        """
        bundle_path = Path(item.staging_path)
        repo_root = Path(item.metadata["repo_root"])

        # `git bundle verify` must be run against a repo that can resolve
        # the bundle's prerequisite commits; the source repo always can.
        _run_git(["bundle", "verify", str(bundle_path)], cwd=repo_root)

        metadata = dict(item.metadata)
        metadata["verified"] = True
        metadata["verified_at"] = datetime.utcnow().isoformat()

        return VerifiedItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=item.staging_path,
            extracted_metadata={
                "commit_count": metadata.get("commit_count", 0),
                "branches": metadata.get("branches", []),
                "remotes": metadata.get("remotes", []),
            },
        )

    def hash(self, item: VerifiedItem) -> HashedItem:
        """Compute SHA-256/xxHash64 of the bundle file.

        Args:
            item: Verified item

        Returns:
            HashedItem
        """
        bundle_path = Path(item.staging_path)
        sha256, xxhash64 = compute_file_hashes(bundle_path)

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
            xxhash64=xxhash64,
        )

    async def store(self, item: HashedItem, run_id: str) -> StoredItem:
        """Store the bundle under 00_RAW/git/ and commit metadata under
        03_NORMALIZED/git_commits/.

        Args:
            item: Hashed item
            run_id: Ingestion run ID

        Returns:
            StoredItem with archive path
        """
        repo_name = item.metadata["repo_name"]

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
            original_filename=f"{repo_name}.bundle",
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

        archive_path = self.path_builder.raw_object_path(
            connector=CONNECTOR_ID,
            date=item.mtime,
            sha256=item.sha256,
            original_filename=f"{repo_name}.bundle",
        )
        storage_key = archive_path[len("00_RAW/") :]

        if dedupe_status == DedupeStatus.DUPLICATE_OF:
            assert existing is not None
            archive_path = self.path_builder.raw_object_path(
                connector=existing.connector,
                date=existing.original_timestamp,
                sha256=item.sha256,
                original_filename=existing.original_filename,
            )
        else:
            self.raw_storage.put(
                storage_key,
                Path(item.staging_path),
                metadata={
                    "source_identifier": item.source_identifier,
                    "mime_type": item.mime_type,
                    "sha256": item.sha256,
                    "xxhash64": item.xxhash64,
                    "commit_count": item.metadata.get("commit_count", 0),
                    "branches": item.metadata.get("branches", []),
                    "remotes": item.metadata.get("remotes", []),
                },
            )

            # Write normalized commit metadata (spec 1.5: commit metadata
            # lands in 03_NORMALIZED/git_commits/ during the STORE stage).
            commits = item.metadata.get("commits", [])
            if commits:
                lines = b"".join(
                    orjson.dumps(
                        {
                            "repo_name": repo_name,
                            "archive_id": manifest_entry.archive_id,
                            **commit,
                        }
                    )
                    + b"\n"
                    for commit in commits
                )
                self.normalized_storage.put(
                    f"git_commits/{repo_name}.jsonl",
                    lines,
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
        """Index commit messages for search. Stub pending Meilisearch/Qdrant."""
        # TODO: Full-text index commit messages; optional code embeddings.
        return item

    async def normalize(self, item: StoredItem) -> StoredItem:
        """Map to GitRepository/GitCommit canonical schemas. Stub pending
        schema finalization; commit-level data is already persisted in
        store()."""
        # TODO: Emit GitRepository/GitCommit/GitBranch/GitTag/Person records.
        return item

    def log(self, item: StoredItem, run_id: str) -> None:
        """Write manifest entries for the stored repository bundle."""
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
                "commit_count": item.metadata.get("commit_count", 0),
                "branches": item.metadata.get("branches", []),
                "remotes": item.metadata.get("remotes", []),
            },
        )

    async def run(self, max_items: int | None = None) -> ConnectorResult:
        """Execute the full ingestion pipeline across all discovered repos.

        Args:
            max_items: Maximum number of repositories to process

        Returns:
            ConnectorResult with statistics and status
        """
        run_id = str(uuid.uuid4())
        start_time = datetime.utcnow()

        items_discovered = 0
        items_processed = 0
        items_failed = 0
        items_skipped = 0
        bytes_processed = 0
        errors: list[str] = []

        try:
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
                    bytes_processed += hashed.size_bytes

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
                config_hash="git_config_v1",
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

    @staticmethod
    def _extract_commits(repo_root: Path) -> list[dict]:
        """Extract commit metadata via `git log --all`."""
        sep = "\x1f"  # unit separator, unlikely to appear in commit fields
        fmt = sep.join(["%H", "%an", "%ae", "%cn", "%ce", "%aI", "%s"])
        output = _run_git(["log", "--all", f"--format={fmt}"], cwd=repo_root)

        commits = []
        for line in output.splitlines():
            if not line.strip():
                continue
            parts = line.split(sep)
            if len(parts) != 7:
                continue
            sha, author_name, author_email, committer_name, committer_email, date, subject = parts
            commits.append(
                {
                    "sha": sha,
                    "author_name": author_name,
                    "author_email": author_email,
                    "committer_name": committer_name,
                    "committer_email": committer_email,
                    "date": date,
                    "message": subject,
                }
            )
        return commits

    @staticmethod
    def _extract_remotes(repo_root: Path) -> list[dict]:
        """Extract remote name/URL pairs via `git remote -v`."""
        try:
            output = _run_git(["remote", "-v"], cwd=repo_root)
        except GitCommandError:
            return []

        remotes = {}
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                remotes[parts[0]] = parts[1]
        return [{"name": name, "url": url} for name, url in remotes.items()]

    @staticmethod
    def _extract_branches(repo_root: Path) -> list[str]:
        """Extract local branch names via `git branch --format`."""
        try:
            output = _run_git(
                ["branch", "--format=%(refname:short)"], cwd=repo_root
            )
        except GitCommandError:
            return []
        return [line.strip() for line in output.splitlines() if line.strip()]
