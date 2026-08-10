"""WhatsApp export connector for Life Archive.

WhatsApp's "Export Chat" feature produces either a bare `_chat.txt` file or a
`.zip` containing `_chat.txt` plus referenced media attachments. This
connector parses the chat transcript into structured messages and stores
media alongside them.

No credentials are required — the user manually exports a chat from the
WhatsApp app and drops the file into the scan directory.
"""

import re
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import AsyncIterator

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

CONNECTOR_ID = "whatsapp"

# Matches lines like:
#   "1/15/24, 9:41 AM - Alice: Hey, how are you?"
#   "15/01/2024, 09:41 - Alice: Hey, how are you?"
# Group 1: date, Group 2: time, Group 3: sender, Group 4: message
_MESSAGE_LINE_RE = re.compile(
    r"^(\d{1,4}[/.\-]\d{1,2}[/.\-]\d{1,4}),\s*"
    r"(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s*-\s*"
    r"([^:]+):\s?(.*)$"
)

_MEDIA_ATTACHMENT_RE = re.compile(
    r"<attached:\s*([^>]+)>|\(file attached\)\s*([^\s]+)?"
)

_SYSTEM_MESSAGE_MARKERS = (
    "Messages and calls are end-to-end encrypted",
    "created group",
    "changed the subject",
    "changed this group's icon",
)


def _parse_messages(text: str) -> list[dict]:
    """Parse WhatsApp chat export text into structured messages.

    Lines that don't match the message pattern are treated as continuations
    of the previous message (e.g. multi-line messages).
    """
    messages: list[dict] = []

    # Strip a leading BOM/invisible LRM character WhatsApp sometimes emits.
    lines = text.replace("\u200e", "").splitlines()

    for line in lines:
        match = _MESSAGE_LINE_RE.match(line.strip())
        if match:
            date, time, sender, message = match.groups()
            messages.append(
                {
                    "date": date.strip(),
                    "time": time.strip(),
                    "sender": sender.strip(),
                    "message": message.strip(),
                }
            )
        elif messages and line.strip():
            # Continuation of the previous message (embedded newline).
            messages[-1]["message"] += "\n" + line.strip()

    return messages


def _is_system_message(sender: str) -> bool:
    return any(marker.lower() in sender.lower() for marker in _SYSTEM_MESSAGE_MARKERS)


def _find_media_references(messages: list[dict]) -> set[str]:
    """Find filenames referenced via `<attached: ...>` or `(file attached) ...`."""
    filenames = set()
    for msg in messages:
        for match in _MEDIA_ATTACHMENT_RE.finditer(msg["message"]):
            name = match.group(1) or match.group(2)
            if name:
                filenames.add(name.strip())
    return filenames


def _sanitize_chat_name(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe.strip() or "chat"


class WhatsAppConnector:
    """Connector for ingesting WhatsApp chat exports."""

    def __init__(
        self,
        archive_root: Path,
        scan_paths: list[Path] | None = None,
    ):
        """Initialize the WhatsApp connector.

        Args:
            archive_root: Path to LIFE_ARCHIVE/ directory
            scan_paths: Directories to search for exports (default:
                [00_RAW/whatsapp/incoming])
        """
        self.archive_root = Path(archive_root)
        self.scan_paths = scan_paths or [
            self.archive_root / "00_RAW" / "whatsapp" / "incoming"
        ]

        self.raw_storage = LocalFilesystemStorage(self.archive_root / "00_RAW")
        self.manifest_writer = ManifestWriter(self.archive_root / "01_MANIFEST")
        self.manifest_reader = ManifestReader(self.archive_root / "01_MANIFEST")

    async def discover(self) -> AsyncIterator[DiscoveredItem]:
        """Discover WhatsApp export zips and bare chat text files."""
        for scan_path in self.scan_paths:
            if not scan_path.exists():
                continue

            for entry in sorted(scan_path.iterdir()):
                if not entry.is_file():
                    continue

                suffix = entry.suffix.lower()
                if suffix not in (".zip", ".txt"):
                    continue

                stat = entry.stat()
                mime_type = "application/zip" if suffix == ".zip" else "text/plain"

                yield DiscoveredItem(
                    source_identifier=entry.name,
                    source_path=str(entry),
                    relative_path=entry.name,
                    size_bytes=stat.st_size,
                    mtime=datetime.fromtimestamp(stat.st_mtime),
                    mime_type=mime_type,
                    metadata={
                        "kind": "zip" if suffix == ".zip" else "text",
                        "chat_name": _sanitize_chat_name(entry.stem),
                    },
                )

    async def acquire(self, item: DiscoveredItem) -> AcquiredItem:
        """Extract zip exports, or reference bare .txt files directly."""
        metadata = dict(item.metadata)

        if metadata["kind"] == "zip":
            staging_dir = Path(mkdtemp(prefix="life_archive_whatsapp_"))
            with zipfile.ZipFile(item.source_path) as zf:
                zf.extractall(staging_dir)
            metadata["staging_dir"] = str(staging_dir)
        else:
            metadata["staging_dir"] = str(Path(item.source_path).parent)
            metadata["chat_txt_path"] = item.source_path

        return AcquiredItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=metadata["staging_dir"],
        )

    async def verify(self, item: AcquiredItem) -> VerifiedItem:
        """Locate and parse the chat transcript.

        Raises:
            ValueError: If no chat text file is found, or no messages can be
                parsed from it.
        """
        metadata = dict(item.metadata)

        if metadata["kind"] == "zip":
            staging_dir = Path(metadata["staging_dir"])
            chat_txt = None
            for candidate in staging_dir.rglob("*.txt"):
                if "chat" in candidate.name.lower():
                    chat_txt = candidate
                    break
            if chat_txt is None:
                txt_files = list(staging_dir.rglob("*.txt"))
                chat_txt = txt_files[0] if txt_files else None
            if chat_txt is None:
                raise ValueError(
                    f"No chat transcript (_chat.txt) found in {item.source_identifier}"
                )
        else:
            chat_txt = Path(metadata["chat_txt_path"])

        text = chat_txt.read_text(encoding="utf-8", errors="replace")
        messages = _parse_messages(text)

        if not messages:
            raise ValueError(
                f"Unable to parse any WhatsApp messages from export: {item.source_identifier}"
            )

        participants = sorted(
            {m["sender"] for m in messages if not _is_system_message(m["sender"])}
        )
        media_filenames = _find_media_references(messages)

        metadata["chat_txt_path"] = str(chat_txt)
        metadata["messages"] = messages
        metadata["message_count"] = len(messages)
        metadata["participants"] = participants
        metadata["media_filenames"] = sorted(media_filenames)

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
                "message_count": len(messages),
                "participants": participants,
            },
        )

    def hash(self, item: VerifiedItem) -> HashedItem:
        """Hash the parsed conversation for provenance.

        Per spec, individual messages are conceptually hashed by
        (content + timestamp + sender); we combine that into a single
        deterministic connector-level hash for the manifest entry by joining
        each message's stable fields in original order and hashing the
        resulting UTF-8 bytes. This keeps one manifest entry per
        conversation/export while still being sensitive to any change in
        any message.
        """
        messages = item.metadata["messages"]
        serialized = "\n".join(
            f"{m['date']}|{m['time']}|{m['sender']}|{m['message']}" for m in messages
        )
        sha256 = hash_bytes_sha256(serialized.encode("utf-8"))

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
        """Store parsed messages as JSONL and copy referenced media.

        Args:
            item: Hashed item
            run_id: Ingestion run ID

        Returns:
            StoredItem with archive path
        """
        chat_name = item.metadata["chat_name"]

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
            original_filename=f"{chat_name}/messages.jsonl",
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

        archive_path = f"00_RAW/whatsapp/{chat_name}/messages.jsonl"
        media_count = 0

        if dedupe_status != DedupeStatus.DUPLICATE_OF:
            import orjson

            messages = item.metadata["messages"]
            lines = b"".join(orjson.dumps(m) + b"\n" for m in messages)
            self.raw_storage.put(f"whatsapp/{chat_name}/messages.jsonl", lines)

            # Copy any referenced media found alongside the chat transcript.
            chat_txt_path = Path(item.metadata["chat_txt_path"])
            media_dir = chat_txt_path.parent
            media_filenames = item.metadata.get("media_filenames", [])
            for filename in media_filenames:
                src = media_dir / filename
                if src.exists() and src.is_file():
                    self.raw_storage.put(
                        f"whatsapp/{chat_name}/media/{filename}",
                        src,
                    )
                    media_count += 1
        else:
            assert existing is not None
            archive_path = f"00_RAW/whatsapp/{chat_name}/messages.jsonl"

        item.metadata["media_count"] = media_count

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
        """Index messages for search. Stub pending Meilisearch/Qdrant.

        TODO: Full-text index messages; embeddings per conversation chunk;
        entity extraction (people, places, dates).
        """
        return item

    async def normalize(self, item: StoredItem) -> StoredItem:
        """Map to Conversation/Message/Person/MediaAttachment schemas.

        TODO: Emit normalized records once schemas are finalized. Group
        chats should produce multiple Person nodes; media should be
        deduplicated across chats via content hash.
        """
        return item

    def log(self, item: StoredItem, run_id: str) -> None:
        """Write manifest entries for the stored conversation."""
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
                "message_count": item.metadata.get("message_count", 0),
                "participants": item.metadata.get("participants", []),
                "media_count": item.metadata.get("media_count", 0),
            },
        )

    async def run(self, max_items: int | None = None) -> ConnectorResult:
        """Execute the full ingestion pipeline across all discovered exports."""
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
                    bytes_processed += discovered_item.size_bytes

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
                config_hash="whatsapp_config_v1",
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
