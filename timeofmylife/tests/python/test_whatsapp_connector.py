"""WhatsApp connector behavior: parsing, media handling, and
provenance/idempotency regression tests (AGENTS.md: connector, schema
validation, and provenance/immutability regression tests)."""

import asyncio
import zipfile
from pathlib import Path

from life_archive.connectors.whatsapp import WhatsAppConnector
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus, ForensicStatus

CHAT_TEXT = (
    "1/15/24, 9:41 AM - Alice: Hey, how are you?\n"
    "1/15/24, 9:42 AM - Bob: I'm good! Just wanted to share something long:\n"
    "This is a second line of the same message\n"
    "and a third line too.\n"
    "1/15/24, 9:43 AM - Alice: Sounds great, talk soon.\n"
)

CHAT_TEXT_WITH_MEDIA = (
    "1/15/24, 9:41 AM - Alice: Check this out\n"
    "1/15/24, 9:42 AM - Alice: <attached: IMG-001.jpg>\n"
)


def _make_archive(tmp_path: Path) -> tuple[Path, Path]:
    archive_root = tmp_path / "LIFE_ARCHIVE"
    incoming_dir = archive_root / "00_RAW" / "whatsapp" / "incoming"
    incoming_dir.mkdir(parents=True)
    return archive_root, incoming_dir


def test_bare_chat_txt_parsed_with_multiline_message(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    (incoming_dir / "_chat.txt").write_text(CHAT_TEXT, encoding="utf-8")

    connector = WhatsAppConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_discovered == 1
    assert result.items_processed == 1
    assert result.items_failed == 0

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.connector == "whatsapp"

    messages_file = archive_root / "00_RAW" / "whatsapp" / "_chat" / "messages.jsonl"
    assert messages_file.exists()
    lines = messages_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3  # 3 messages: Alice, Bob (multi-line merged), Alice

    import orjson

    parsed = [orjson.loads(line) for line in lines]
    assert parsed[0]["sender"] == "Alice"
    assert parsed[1]["sender"] == "Bob"
    assert "second line" in parsed[1]["message"]
    assert "third line" in parsed[1]["message"]
    assert parsed[2]["sender"] == "Alice"


def test_zip_export_with_media_is_copied(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)

    zip_path = incoming_dir / "WhatsApp Chat - Friend.zip"
    media_bytes = b"\xff\xd8\xff\xe0fake-jpeg-bytes"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("_chat.txt", CHAT_TEXT_WITH_MEDIA)
        zf.writestr("IMG-001.jpg", media_bytes)

    connector = WhatsAppConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_processed == 1

    chat_name = "WhatsApp Chat - Friend"
    media_file = archive_root / "00_RAW" / "whatsapp" / chat_name / "media" / "IMG-001.jpg"
    assert media_file.exists()
    assert media_file.read_bytes() == media_bytes

    messages_file = archive_root / "00_RAW" / "whatsapp" / chat_name / "messages.jsonl"
    assert messages_file.exists()


def test_rerun_is_idempotent_and_does_not_duplicate(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    (incoming_dir / "_chat.txt").write_text(CHAT_TEXT, encoding="utf-8")

    connector = WhatsAppConnector(archive_root=archive_root)
    asyncio.run(connector.run())
    result = asyncio.run(connector.run())

    assert result.status == ForensicStatus.PASS
    assert result.items_failed == 0

    entries = list(ManifestReader(archive_root / "01_MANIFEST").read_manifest_entries())
    assert len(entries) == 2
    assert entries[1].dedupe_status == DedupeStatus.DUPLICATE_OF


def test_unparseable_text_fails_gracefully(tmp_path):
    archive_root, incoming_dir = _make_archive(tmp_path)
    (incoming_dir / "random.txt").write_text(
        "This is just some random prose with no timestamps at all.\n"
        "Nothing here looks like a chat export.\n",
        encoding="utf-8",
    )

    connector = WhatsAppConnector(archive_root=archive_root)
    result = asyncio.run(connector.run())

    assert result.items_discovered == 1
    assert result.items_failed == 1
    assert result.items_processed == 0
    assert len(result.errors) == 1
    assert "random.txt" in result.errors[0]
