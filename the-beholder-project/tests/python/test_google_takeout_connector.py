"""Google Takeout connector behavior: extraction, service fan-out, and
provenance/idempotency regression tests (AGENTS.md: connector, schema
validation, and provenance/immutability regression tests)."""

import asyncio
import zipfile
from pathlib import Path

from life_archive.connectors.google_takeout import GoogleTakeoutConnector
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus, ForensicStatus


def _make_takeout_zip(incoming_dir: Path, name: str = "takeout-20260101T000000Z-001.zip") -> Path:
    """Build a synthetic fake Takeout export zip (no real user data)."""
    zip_path = incoming_dir / name
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(
            "Takeout/Mail/All mail Including Spam and Trash.mbox",
            "From someone@example.com\nSubject: Test\n\nHello world\n",
        )
        zf.writestr("Takeout/Drive/some_doc.txt", "This is a fake drive document.\n")
        zf.writestr("Takeout/archive_browser.html", "<html><body>fake browser</body></html>")
    return zip_path


def _make_archive(tmp_path: Path) -> tuple[Path, Path]:
    archive_root = tmp_path / "LIFE_ARCHIVE"
    incoming_dir = archive_root / "00_RAW" / "google" / "takeout" / "incoming"
    incoming_dir.mkdir(parents=True)
    return archive_root, incoming_dir


def test_pipeline_extracts_and_fans_out_services(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    _make_takeout_zip(incoming_dir)

    connector = GoogleTakeoutConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1
    assert result.items_failed == 0
    assert result.errors == []

    gmail_dir = archive_root / "00_RAW" / "google" / "gmail"
    drive_dir = archive_root / "00_RAW" / "google" / "drive"
    assert gmail_dir.exists()
    assert drive_dir.exists()

    mbox_file = gmail_dir / "All mail Including Spam and Trash.mbox"
    doc_file = drive_dir / "some_doc.txt"
    assert mbox_file.exists()
    assert doc_file.exists()
    assert "Hello world" in mbox_file.read_text()
    assert doc_file.read_text() == "This is a fake drive document.\n"

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.connector == "google-takeout"
    assert entry.source == "google-takeout"
    assert entry.dedupe_status == DedupeStatus.UNIQUE
    assert entry.processing_status.value == "STORED"


def test_services_detected_recorded_in_acquisition_log(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    _make_takeout_zip(incoming_dir)

    connector = GoogleTakeoutConnector(archive_root=archive_root)
    asyncio.run(connector.run())

    reader = ManifestReader(archive_root / "01_MANIFEST")
    logs = list(reader.read_acquisition_log())
    assert len(logs) == 1
    services = logs[0]["details"]["services_detected"]
    assert "Mail" in services
    assert "Drive" in services


def test_rerun_is_idempotent_and_does_not_duplicate(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    _make_takeout_zip(incoming_dir)

    connector = GoogleTakeoutConnector(archive_root=archive_root)
    asyncio.run(connector.run())
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_failed == 0

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.DUPLICATE_OF


def test_export_without_takeout_folder_fails_gracefully(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)

    bad_zip = incoming_dir / "not-a-takeout.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("readme.txt", "this is not a takeout export")

    connector = GoogleTakeoutConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.items_discovered == 1
    assert result.items_failed == 1
    assert result.items_processed == 0
    assert len(result.errors) == 1
    assert "not-a-takeout.zip" in result.errors[0]
