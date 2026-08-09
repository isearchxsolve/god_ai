"""Local-files connector behavior (AGENTS.md: connector, schema validation,
and provenance/immutability regression tests)."""

import asyncio
import hashlib
from pathlib import Path

from life_archive.connectors.local_files import LocalFilesConnector
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus, ForensicStatus, PrivacyClassification

CONTENT = b"immutable source material"
SHA256 = hashlib.sha256(CONTENT).hexdigest()


def _make_archive(tmp_path: Path) -> Path:
    archive_root = tmp_path / "LIFE_ARCHIVE"
    source_dir = archive_root / "00_RAW" / "test"
    source_dir.mkdir(parents=True)
    (source_dir / "doc.txt").write_bytes(CONTENT)
    return archive_root


def test_pipeline_stores_exact_copy_with_provenance(tmp_path):
    """RULE 2 regression: stored bytes must equal source bytes, and the
    manifest entry must trace back to the source (provenance)."""
    archive_root = _make_archive(tmp_path)
    connector = LocalFilesConnector(archive_root=archive_root)

    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1
    assert result.items_failed == 0
    assert result.errors == []

    # Stored copy exists at the content-addressed path and is byte-identical
    stored = archive_root / "00_RAW" / "local-files"
    stored_files = [p for p in stored.rglob("*") if p.is_file() and not p.name.endswith(".meta.json")]
    assert len(stored_files) == 1
    assert stored_files[0].read_bytes() == CONTENT

    # Manifest entry carries full provenance
    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.archive_id == f"sha256:{SHA256}"
    assert entry.sha256 == SHA256
    assert entry.original_filename == "doc.txt"
    assert entry.connector == "local-files"
    assert entry.dedupe_status == DedupeStatus.UNIQUE
    assert entry.privacy_classification == PrivacyClassification.PRIVATE  # RULE 9 default
    assert entry.processing_status.value == "STORED"


def test_rerun_is_idempotent_and_does_not_duplicate_raw(tmp_path):
    """Re-ingesting the same source must link as DUPLICATE_OF and must not
    write a second raw copy (RAW stays append-only, dedup only marks)."""
    archive_root = _make_archive(tmp_path)
    connector = LocalFilesConnector(archive_root=archive_root)

    asyncio.run(connector.run())
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_failed == 0

    stored = archive_root / "00_RAW" / "local-files"
    stored_files = [p for p in stored.rglob("*") if p.is_file() and not p.name.endswith(".meta.json")]
    assert len(stored_files) == 1  # no second copy

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.DUPLICATE_OF
    assert entries[1].dedupe_of == f"sha256:{SHA256}"


def test_stored_copies_are_not_rescanned(tmp_path):
    """Discovery must skip the connector's own storage output."""
    archive_root = _make_archive(tmp_path)
    connector = LocalFilesConnector(archive_root=archive_root)
    asyncio.run(connector.run())

    discovered = asyncio.run(_collect(connector))
    # Only the original source file; the stored copy under
    # 00_RAW/local-files/ must not be rediscovered.
    assert len(discovered) == 1
    assert discovered[0].source_identifier.endswith("doc.txt")
    assert "local-files" not in discovered[0].source_path.split("00_RAW")[-1].split("test")[0]


async def _collect(connector):
    return [item async for item in connector.discover()]
