"""Manifest write/read round-trip (AGENTS.md: manifest writing/reading tests)."""

from datetime import datetime

import pytest

from life_archive.manifest import (
    ManifestReader,
    ManifestWriter,
    create_archive_id,
    parse_archive_id,
)
from life_archive.schemas.provenance import IngestionRun, ManifestEntry


def _make_entry(sha256: str) -> ManifestEntry:
    return ManifestEntry(
        archive_id=create_archive_id(sha256),
        source="local-files",
        source_identifier="test/file.txt",
        original_filename="file.txt",
        mime_type="text/plain",
        size_bytes=11,
        original_timestamp=datetime(2026, 8, 9, 10, 0, 0),
        acquisition_timestamp=datetime(2026, 8, 9, 11, 0, 0),
        sha256=sha256,
        connector="local-files",
        ingestion_run_id="run-1",
    )


def test_manifest_write_read_round_trip(tmp_path):
    writer = ManifestWriter(tmp_path)
    reader = ManifestReader(tmp_path)

    sha = "a" * 64
    writer.write_manifest_entry(_make_entry(sha))
    writer.write_hash_record(create_archive_id(sha), sha, xxhash64=None)
    writer.write_acquisition_log(create_archive_id(sha), "local-files", "stored")
    writer.write_ingestion_run(
        IngestionRun(
            run_id="run-1",
            connector="local-files",
            start_time=datetime(2026, 8, 9, 11, 0, 0),
            end_time=datetime(2026, 8, 9, 11, 0, 1),
            status="PASS",
            items_discovered=1,
            items_processed=1,
        )
    )

    entries = list(reader.read_manifest_entries())
    assert len(entries) == 1
    assert entries[0].archive_id == f"sha256:{sha}"
    assert entries[0].processing_status.value == "DISCOVERED"  # schema default

    hash_records = list(reader.read_hash_records())
    assert hash_records[0]["sha256"] == sha

    acquisitions = list(reader.read_acquisition_log())
    assert acquisitions[0]["action"] == "stored"

    runs = list(reader.read_ingestion_runs())
    assert runs[0].run_id == "run-1"
    assert runs[0].items_processed == 1

    assert reader.get_entry_by_sha256(sha) is not None
    assert reader.get_entry_by_sha256("b" * 64) is None
    assert reader.count_entries() == 1


def test_manifest_is_append_only(tmp_path):
    """Writing twice keeps both records (immutable audit trail)."""
    writer = ManifestWriter(tmp_path)
    writer.write_manifest_entry(_make_entry("a" * 64))
    writer.write_manifest_entry(_make_entry("b" * 64))

    entries = list(ManifestReader(tmp_path).read_manifest_entries())
    assert [e.sha256 for e in entries] == ["a" * 64, "b" * 64]


def test_archive_id_format_validation():
    assert parse_archive_id("sha256:abc") == "abc"
    with pytest.raises(ValueError):
        parse_archive_id("md5:abc")
