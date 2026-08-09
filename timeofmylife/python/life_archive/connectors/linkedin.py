"""LinkedIn export connector for Life Archive.

LinkedIn's "Download your data" feature produces a `.zip` of mostly-CSV
files (Connections, Profile, Messages, Jobs, Education, Skills, Posts,
etc.). This connector extracts recognized files, counts records per
category, and stores them under `00_RAW/linkedin/{category}/`.

No credentials are required — the user manually requests and downloads the
export from LinkedIn and drops it into the scan directory.
"""

import csv
import json
import shutil
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import AsyncIterator

from life_archive.hash import compute_file_hashes, hash_bytes_sha256
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

CONNECTOR_ID = "linkedin"

# Maps known LinkedIn export file stems (case-insensitive, without
# extension) to our internal category slugs.
KNOWN_FILE_CATEGORIES = {
    "connections": "connections",
    "profile": "profile",
    "messages": "messages",
    "jobs": "jobs",
    "saved jobs": "jobs",
    "education": "education",
    "skills": "skills",
    "posts": "posts",
    "shares": "posts",
}


def _category_for_stem(stem: str) -> str | None:
    return KNOWN_FILE_CATEGORIES.get(stem.strip().lower())


def _count_records(path: Path) -> int:
    """Count data rows in a LinkedIn export file (CSV or JSON)."""
    if path.suffix.lower() == ".csv":
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # First row is the header; everything else is data.
        return max(len(rows) - 1, 0) if rows else 0
    elif path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return 0
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            return 1
        return 0
    return 0


def _find_export_files(root: Path) -> dict[str, Path]:
    """Find known LinkedIn export files under root, tolerant of one level
    of nesting. Returns category -> file path (first match wins)."""
    found: dict[str, Path] = {}

    candidates = list(root.glob("*")) + list(root.glob("*/*"))
    for candidate in candidates:
        if not candidate.is_file():
            continue
        if candidate.suffix.lower() not in (".csv", ".json"):
            continue
        category = _category_for_stem(candidate.stem)
        if category and category not in found:
            found[category] = candidate

    return found


class LinkedInConnector:
    """Connector for ingesting LinkedIn "Download your data" exports."""

    def __init__(
        self,
        archive_root: Path,
        scan_paths: list[Path] | None = None,
    ):
        """Initialize the LinkedIn connector.

        Args:
            archive_root: Path to LIFE_ARCHIVE/ directory
            scan_paths: Directories to search for exports (default:
                [00_RAW/linkedin/incoming])
        """
        self.archive_root = Path(archive_root)
        self.scan_paths = scan_paths or [
            self.archive_root / "00_RAW" / "linkedin" / "incoming"
        ]

        self.raw_storage = LocalFilesystemStorage(self.archive_root / "00_RAW")
        self.manifest_writer = ManifestWriter(self.archive_root / "01_MANIFEST")
        self.manifest_reader = ManifestReader(self.archive_root / "01_MANIFEST")

    async def discover(self) -> AsyncIterator[DiscoveredItem]:
        """Discover LinkedIn export zips and directories."""
        for scan_path in self.scan_paths:
            if not scan_path.exists():
                continue

            for entry in sorted(scan_path.iterdir()):
                if entry.is_file() and entry.suffix.lower() == ".zip":
                    stat = entry.stat()
                    yield DiscoveredItem(
                        source_identifier=entry.name,
                        source_path=str(entry),
                        relative_path=entry.name,
                        size_bytes=stat.st_size,
                        mtime=datetime.fromtimestamp(stat.st_mtime),
                        mime_type="application/zip",
                        metadata={"kind": "zip", "name": entry.stem},
                    )
                elif entry.is_dir():
                    found = _find_export_files(entry)
                    if found:
                        stat = entry.stat()
                        yield DiscoveredItem(
                            source_identifier=entry.name,
                            source_path=str(entry),
                            relative_path=entry.name,
                            size_bytes=0,
                            mtime=datetime.fromtimestamp(stat.st_mtime),
                            mime_type="inode/directory",
                            metadata={"kind": "directory", "name": entry.name},
                        )

    async def acquire(self, item: DiscoveredItem) -> AcquiredItem:
        """Extract the zip export (or reference an already-extracted one)."""
        metadata = dict(item.metadata)

        if metadata["kind"] == "zip":
            staging_dir = Path(mkdtemp(prefix="life_archive_linkedin_"))
            with zipfile.ZipFile(item.source_path) as zf:
                zf.extractall(staging_dir)
            metadata["original_zip"] = item.source_path
            extracted_root = staging_dir
        else:
            extracted_root = Path(item.source_path)

        metadata["extracted_root"] = str(extracted_root)

        return AcquiredItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=str(extracted_root),
        )

    async def verify(self, item: AcquiredItem) -> VerifiedItem:
        """Identify known LinkedIn export files and count records.

        Raises:
            ValueError: If no recognizable LinkedIn export files are found.
        """
        extracted_root = Path(item.metadata["extracted_root"])
        found = _find_export_files(extracted_root)

        if not found:
            raise ValueError(
                f"No recognizable LinkedIn export files found in {item.source_identifier}"
            )

        categories_detected = {
            category: _count_records(path) for category, path in found.items()
        }

        metadata = dict(item.metadata)
        metadata["files_by_category"] = {c: str(p) for c, p in found.items()}
        metadata["categories_detected"] = categories_detected

        return VerifiedItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=item.staging_path,
            extracted_metadata={"categories_detected": categories_detected},
        )

    def hash(self, item: VerifiedItem) -> HashedItem:
        """Hash the export for provenance.

        Prefers hashing the original zip file directly when available (the
        immutable artifact the user downloaded); falls back to a
        deterministic manifest of `(relative_path, size)` pairs for
        pre-extracted directories, matching the approach used by the
        Google Takeout connector.
        """
        if item.metadata.get("kind") == "zip":
            sha256, xxhash64 = compute_file_hashes(item.metadata["original_zip"])
        else:
            extracted_root = Path(item.metadata["extracted_root"])
            entries = sorted(
                (str(p.relative_to(extracted_root)), p.stat().st_size)
                for p in extracted_root.rglob("*")
                if p.is_file()
            )
            manifest_str = "\n".join(f"{path}:{size}" for path, size in entries)
            sha256 = hash_bytes_sha256(manifest_str.encode("utf-8"))
            xxhash64 = None

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
        """Store the export and copy recognized files by category.

        Args:
            item: Hashed item
            run_id: Ingestion run ID

        Returns:
            StoredItem with archive path
        """
        original_filename = item.metadata.get("name", "linkedin-export") + (
            ".zip" if item.metadata.get("kind") == "zip" else ""
        )

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
            original_filename=original_filename,
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            original_timestamp=item.mtime,
            acquisition_timestamp=datetime.utcnow(),
            sha256=item.sha256,
            xxhash64=item.xxhash64,
            connector=CONNECTOR_ID,
            ingestion_run_id=run_id,
            # TODO: Per-connection email addresses should eventually be
            # classified THIRD_PARTY_PRIVATE during normalize(); the
            # top-level export entry defaults to PRIVATE like other
            # connectors (RULE 9).
            privacy_classification=PrivacyClassification.PRIVATE,
            processing_status=ProcessingStatus.STORED,
            dedupe_status=dedupe_status,
            dedupe_of=dedupe_of,
        )

        archive_path = f"00_RAW/linkedin/_export/{original_filename}"

        if dedupe_status != DedupeStatus.DUPLICATE_OF:
            if item.metadata.get("kind") == "zip":
                self.raw_storage.put(
                    f"linkedin/_export/{original_filename}",
                    Path(item.metadata["original_zip"]),
                    metadata={
                        "source_identifier": item.source_identifier,
                        "sha256": item.sha256,
                        "categories_detected": item.metadata.get("categories_detected", {}),
                    },
                )
            else:
                self.raw_storage.put(
                    f"linkedin/_export/{original_filename}.marker.txt",
                    f"Pre-extracted LinkedIn export: {item.source_path}\n".encode("utf-8"),
                )

            for category, file_path_str in item.metadata["files_by_category"].items():
                file_path = Path(file_path_str)
                dest_dir = self.archive_root / "00_RAW" / "linkedin" / category
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_dir / file_path.name)
        else:
            assert existing is not None

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
        """Index posts/messages for search. Stub pending Meilisearch/Qdrant.

        TODO: Connections -> graph edges; Posts -> full-text + embeddings;
        Profile -> entity.
        """
        return item

    async def normalize(self, item: StoredItem) -> StoredItem:
        """Map to Person/Organization/Job/Education/Post/Skill schemas.

        TODO: Emit normalized records once schemas/Neo4j graph infra are
        available. Connections' email addresses should be classified
        THIRD_PARTY_PRIVATE at that point.
        """
        return item

    def log(self, item: StoredItem, run_id: str) -> None:
        """Write manifest entries for the stored LinkedIn export."""
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
                "categories_detected": item.metadata.get("categories_detected", {}),
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
                config_hash="linkedin_config_v1",
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
