"""Google Takeout connector for Life Archive.

Google Takeout is a **meta-connector**: a single export (`takeout-*.zip`
downloaded from takeout.google.com) bundles multiple Google services (Mail,
Drive, Photos, Calendar, YouTube, Contacts, etc.) into one archive. This
connector extracts the export, fans each detected service out into its own
subtree under `00_RAW/google/{service}/`, and records one manifest entry for
the export as a whole (per-service/per-file processing is left to future
service-specific connectors, per `03_CONNECTOR_INVENTORY.md` section 1.2).

No credentials are required — the user manually downloads and drops the
export into the scan directory.
"""

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
from life_archive.storage import LocalFilesystemStorage, StoragePathBuilder

CONNECTOR_ID = "google-takeout"

# Maps Google Takeout's top-level service folder names to our internal
# storage slugs. Names are matched case-insensitively. Anything not listed
# falls back to a slugified version of the folder name itself.
SERVICE_SLUG_MAP = {
    "mail": "gmail",
    "drive": "drive",
    "google photos": "photos",
    "photos": "photos",
    "calendar": "calendar",
    "contacts": "contacts",
    "youtube and youtube music": "youtube",
    "youtube": "youtube",
    "maps": "maps",
    "maps (your places)": "maps",
    "chrome": "chrome",
    "keep": "keep",
    "tasks": "tasks",
    "fit": "fit",
    "voice": "voice",
    "hangouts": "hangouts",
}


def _slugify(name: str) -> str:
    """Fallback slugifier for unrecognized Takeout service folder names."""
    slug = "".join(c.lower() if c.isalnum() else "-" for c in name)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "other"


def _service_slug(folder_name: str) -> str:
    return SERVICE_SLUG_MAP.get(folder_name.strip().lower(), _slugify(folder_name))


class GoogleTakeoutConnector:
    """Connector for ingesting Google Takeout exports.

    Handles both a raw `takeout-*.zip` download and an already-extracted
    export directory (i.e. one containing a `Takeout/` subfolder).
    """

    def __init__(
        self,
        archive_root: Path,
        scan_paths: list[Path] | None = None,
    ):
        """Initialize the Google Takeout connector.

        Args:
            archive_root: Path to LIFE_ARCHIVE/ directory
            scan_paths: Directories to search for Takeout exports (default:
                [00_RAW/google/takeout/incoming])
        """
        self.archive_root = Path(archive_root)
        self.scan_paths = scan_paths or [
            self.archive_root / "00_RAW" / "google" / "takeout" / "incoming"
        ]

        self.raw_storage = LocalFilesystemStorage(self.archive_root / "00_RAW")
        self.manifest_writer = ManifestWriter(self.archive_root / "01_MANIFEST")
        self.manifest_reader = ManifestReader(self.archive_root / "01_MANIFEST")
        self.path_builder = StoragePathBuilder()

    async def discover(self) -> AsyncIterator[DiscoveredItem]:
        """Discover Takeout export zips and pre-extracted export directories."""
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
                elif entry.is_dir() and (entry / "Takeout").exists():
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
        """Extract the zip export (or reference an already-extracted one).

        Args:
            item: Discovered export item

        Returns:
            AcquiredItem with staging_path pointing at the directory
            containing the extracted `Takeout/` folder.
        """
        metadata = dict(item.metadata)

        if metadata["kind"] == "zip":
            staging_dir = Path(mkdtemp(prefix="life_archive_takeout_"))
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
        """Identify which Google services are present in the export.

        Args:
            item: Acquired item with extracted_root in metadata

        Returns:
            VerifiedItem with services_detected recorded

        Raises:
            ValueError: If no `Takeout/` folder or zero known services found
        """
        extracted_root = Path(item.metadata["extracted_root"])
        takeout_dir = extracted_root / "Takeout"

        if not takeout_dir.exists() or not takeout_dir.is_dir():
            raise ValueError(
                f"No recognizable Google Takeout services found in {item.source_identifier} "
                "(missing Takeout/ folder)"
            )

        services = sorted(
            p.name for p in takeout_dir.iterdir() if p.is_dir()
        )

        if not services:
            raise ValueError(
                f"No recognizable Google Takeout services found in {item.source_identifier} "
                "(Takeout/ folder is empty)"
            )

        metadata = dict(item.metadata)
        metadata["services_detected"] = services
        metadata["takeout_dir"] = str(takeout_dir)

        return VerifiedItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=item.staging_path,
            extracted_metadata={"services_detected": services},
        )

    def hash(self, item: VerifiedItem) -> HashedItem:
        """Hash the export for provenance.

        If the source was a single zip file, hash that file directly (it is
        the immutable artifact the user downloaded). If the source was
        already an extracted directory (no single canonical archive file),
        fall back to hashing a deterministic manifest of
        `(relative_path, size)` pairs for every file under `Takeout/`, since
        there is no single byte-stream to hash.

        Args:
            item: Verified item

        Returns:
            HashedItem
        """
        if item.metadata.get("kind") == "zip":
            sha256, xxhash64 = compute_file_hashes(item.metadata["original_zip"])
        else:
            takeout_dir = Path(item.metadata["takeout_dir"])
            entries = sorted(
                (str(p.relative_to(takeout_dir)), p.stat().st_size)
                for p in takeout_dir.rglob("*")
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
        """Store the export and fan out per-service files.

        Args:
            item: Hashed item
            run_id: Ingestion run ID

        Returns:
            StoredItem with archive path
        """
        original_filename = item.metadata.get("name", "takeout") + (
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
            privacy_classification=PrivacyClassification.PRIVATE,
            processing_status=ProcessingStatus.STORED,
            dedupe_status=dedupe_status,
            dedupe_of=dedupe_of,
        )

        archive_path = self.path_builder.raw_object_path(
            connector=CONNECTOR_ID,
            date=item.mtime,
            sha256=item.sha256,
            original_filename=original_filename,
        )

        if dedupe_status != DedupeStatus.DUPLICATE_OF:
            takeout_dir = Path(item.metadata["takeout_dir"])

            # Store the canonical export artifact (the zip itself, or a
            # small marker file describing the pre-extracted directory).
            storage_key = archive_path[len("00_RAW/") :]
            if item.metadata.get("kind") == "zip":
                self.raw_storage.put(
                    storage_key,
                    Path(item.metadata["original_zip"]),
                    metadata={
                        "source_identifier": item.source_identifier,
                        "sha256": item.sha256,
                        "services_detected": item.metadata.get("services_detected", []),
                    },
                )
            else:
                self.raw_storage.put(
                    storage_key,
                    f"Pre-extracted Takeout export: {item.source_path}\n".encode("utf-8"),
                    metadata={
                        "source_identifier": item.source_identifier,
                        "sha256": item.sha256,
                        "services_detected": item.metadata.get("services_detected", []),
                    },
                )

            # Fan out per-service directories (bulk copy; individual files
            # are re-hashed/deduped later by local-files or service-specific
            # connectors, per the Takeout meta-connector design).
            for service_dir in takeout_dir.iterdir():
                if not service_dir.is_dir():
                    continue
                slug = _service_slug(service_dir.name)
                dest = self.archive_root / "00_RAW" / "google" / slug
                dest.mkdir(parents=True, exist_ok=True)
                for src_path in service_dir.rglob("*"):
                    if not src_path.is_file():
                        continue
                    rel = src_path.relative_to(service_dir)
                    dest_path = dest / rel
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_path, dest_path)
        else:
            assert existing is not None
            archive_path = self.path_builder.raw_object_path(
                connector=existing.connector,
                date=existing.original_timestamp,
                sha256=item.sha256,
                original_filename=existing.original_filename,
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
        """Index extracted content for search. Stub pending Meilisearch/Qdrant.

        TODO: Delegate to service-specific sub-connectors (Gmail, Drive,
        Photos, Calendar, YouTube, Contacts) once Phase 2 OAuth connectors
        or offline parsers for these formats exist.
        """
        return item

    async def normalize(self, item: StoredItem) -> StoredItem:
        """Produce a unified GoogleTakeoutExport manifest. Stub pending
        schema finalization.

        TODO: Emit a GoogleTakeoutExport record linking all fanned-out
        services for this export.
        """
        return item

    def log(self, item: StoredItem, run_id: str) -> None:
        """Write manifest entries for the stored Takeout export."""
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
                "services_detected": item.metadata.get("services_detected", []),
            },
        )

    async def run(self, max_items: int | None = None) -> ConnectorResult:
        """Execute the full ingestion pipeline across all discovered exports.

        Args:
            max_items: Maximum number of exports to process

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
                config_hash="google_takeout_config_v1",
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
