"""LinkedIn connector behavior: extraction, category detection, and
provenance/idempotency regression tests (AGENTS.md: connector, schema
validation, and provenance/immutability regression tests)."""

import asyncio
import zipfile
from pathlib import Path

from life_archive.connectors.linkedin import LinkedInConnector
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus, ForensicStatus

CONNECTIONS_CSV = (
    "First Name,Last Name,Email Address,Company,Position,Connected On\n"
    "Jane,Doe,jane.doe@example.com,Acme Corp,Engineer,01 Jan 2024\n"
    "John,Smith,john.smith@example.com,Widget Inc,Manager,02 Feb 2024\n"
    "Amy,Lee,amy.lee@example.com,Gizmo LLC,Designer,03 Mar 2024\n"
)

PROFILE_CSV = "First Name,Last Name,Headline\n" "Fictional,Person,Software Engineer\n"


def _make_export_zip(incoming_dir: Path, name: str = "Complete_LinkedInDataExport.zip") -> Path:
    zip_path = incoming_dir / name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("Connections.csv", CONNECTIONS_CSV)
        zf.writestr("Profile.csv", PROFILE_CSV)
    return zip_path


def _make_archive(tmp_path: Path) -> tuple[Path, Path]:
    archive_root = tmp_path / "LIFE_ARCHIVE"
    incoming_dir = archive_root / "00_RAW" / "linkedin" / "incoming"
    incoming_dir.mkdir(parents=True)
    return archive_root, incoming_dir


def test_pipeline_extracts_recognized_files(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    _make_export_zip(incoming_dir)

    connector = LinkedInConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1
    assert result.items_failed == 0
    assert result.errors == []

    connections_file = archive_root / "00_RAW" / "linkedin" / "connections" / "Connections.csv"
    profile_file = archive_root / "00_RAW" / "linkedin" / "profile" / "Profile.csv"
    assert connections_file.exists()
    assert profile_file.exists()
    assert connections_file.read_text() == CONNECTIONS_CSV
    assert profile_file.read_text() == PROFILE_CSV

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.connector == "linkedin"
    assert entry.source == "linkedin"
    assert entry.dedupe_status == DedupeStatus.UNIQUE


def test_categories_detected_with_correct_record_counts(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    _make_export_zip(incoming_dir)

    connector = LinkedInConnector(archive_root=archive_root)
    asyncio.run(connector.run())

    reader = ManifestReader(archive_root / "01_MANIFEST")
    logs = list(reader.read_acquisition_log())
    assert len(logs) == 1
    categories = logs[0]["details"]["categories_detected"]
    assert categories["connections"] == 3
    assert categories["profile"] == 1


def test_rerun_is_idempotent_and_does_not_duplicate(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    _make_export_zip(incoming_dir)

    connector = LinkedInConnector(archive_root=archive_root)
    asyncio.run(connector.run())
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_failed == 0

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.DUPLICATE_OF


def test_unrecognized_export_fails_gracefully(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)

    bad_zip = incoming_dir / "not-linkedin.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("readme.txt", "this is not a linkedin export")

    connector = LinkedInConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.items_discovered == 1
    assert result.items_failed == 1
    assert result.items_processed == 0
    assert len(result.errors) == 1
    assert "not-linkedin.zip" in result.errors[0]
