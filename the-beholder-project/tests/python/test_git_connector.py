"""Git connector behavior: bundling, provenance, and idempotency regression
tests (AGENTS.md: connector, schema validation, and provenance/immutability
regression tests)."""

import asyncio
import subprocess
from pathlib import Path

import pytest

from life_archive.connectors.git import GitConnector
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus, ForensicStatus, PrivacyClassification


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _make_repo(repos_dir: Path, name: str = "sample-repo") -> Path:
    repo_root = repos_dir / name
    repo_root.mkdir(parents=True)
    _git(["init", "-q"], repo_root)
    _git(["config", "user.email", "test@example.com"], repo_root)
    _git(["config", "user.name", "Test User"], repo_root)
    (repo_root / "README.md").write_text("hello world\n")
    _git(["add", "."], repo_root)
    _git(["commit", "-q", "-m", "initial commit"], repo_root)
    return repo_root


def _make_archive(tmp_path: Path) -> tuple[Path, Path]:
    archive_root = tmp_path / "LIFE_ARCHIVE"
    repos_dir = archive_root / "00_RAW" / "git" / "repos"
    repos_dir.mkdir(parents=True)
    return archive_root, repos_dir


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git CLI not available",
)
def test_pipeline_bundles_repo_with_provenance(tmp_path):
    archive_root, repos_dir = _make_archive(tmp_path)
    _make_repo(repos_dir)

    connector = GitConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1
    assert result.items_failed == 0
    assert result.errors == []

    # Bundle stored under 00_RAW/git/
    bundles = list((archive_root / "00_RAW" / "git").rglob("*.bundle"))
    assert len(bundles) == 1

    # Commit metadata stored under 03_NORMALIZED/git_commits/
    commit_files = list((archive_root / "03_NORMALIZED" / "git_commits").glob("*.jsonl"))
    assert len(commit_files) == 1
    lines = commit_files[0].read_text().strip().splitlines()
    assert len(lines) == 1
    assert "initial commit" in lines[0]

    # Manifest entry carries full provenance
    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.connector == "git"
    assert entry.source == "git"
    assert entry.original_filename == "sample-repo.bundle"
    assert entry.dedupe_status == DedupeStatus.UNIQUE
    assert entry.privacy_classification == PrivacyClassification.PRIVATE
    assert entry.processing_status.value == "STORED"


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git CLI not available",
)
def test_rerun_is_idempotent_and_does_not_duplicate_raw(tmp_path):
    archive_root, repos_dir = _make_archive(tmp_path)
    _make_repo(repos_dir)

    connector = GitConnector(archive_root=archive_root)
    asyncio.run(connector.run())
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_failed == 0

    bundles = list((archive_root / "00_RAW" / "git").rglob("*.bundle"))
    assert len(bundles) == 1  # no second copy of unchanged repo

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.DUPLICATE_OF


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git CLI not available",
)
def test_new_commit_produces_new_bundle(tmp_path):
    archive_root, repos_dir = _make_archive(tmp_path)
    repo_root = _make_repo(repos_dir)

    connector = GitConnector(archive_root=archive_root)
    asyncio.run(connector.run())

    (repo_root / "NOTES.md").write_text("more content\n")
    _git(["add", "."], repo_root)
    _git(["commit", "-q", "-m", "second commit"], repo_root)

    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.UNIQUE  # history changed -> new bundle hash

    bundles = list((archive_root / "00_RAW" / "git").rglob("*.bundle"))
    assert len(bundles) == 2


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git CLI not available",
)
def test_multiple_repos_discovered_independently(tmp_path):
    archive_root, repos_dir = _make_archive(tmp_path)
    _make_repo(repos_dir, "repo-a")
    _make_repo(repos_dir, "repo-b")

    connector = GitConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.items_discovered == 2
    assert result.items_processed == 2

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    filenames = sorted(e.original_filename for e in entries)
    assert filenames == ["repo-a.bundle", "repo-b.bundle"]
