"""Local files connector for Life Archive.

Discovers, acquires, verifies, hashes, stores, indexes, normalizes and logs
files from the local filesystem (LIFE_ARCHIVE/00_RAW/).

This is the foundational connector that validates the entire pipeline without
requiring external credentials.
"""

import mimetypes
import shutil
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
import uuid

from life_archive.hash import compute_file_hashes
from life_archive.manifest import (
    ManifestReader,
    ManifestWriter,
    create_archive_id,
    parse_archive_id,
)
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


class LocalFilesConnector:
    """Connector for ingesting files from local filesystem.

    This connector is designed for:
    - Pilot testing with synthetic/test data
    - Ingesting manually downloaded exports (Google Takeout, WhatsApp, LinkedIn)
    - Processing files already present in 00_RAW/

    It does NOT require external credentials or APIs.
    """

    def __init__(
        self,
        archive_root: Path,
        scan_paths: list[Path] | None = None,
        supported_extensions: list[str] | None = None,
    ):
        """Initialize local files connector.

        Args:
            archive_root: Path to LIFE_ARCHIVE/ directory
            scan_paths: Paths to scan (default: [00_RAW/])
            supported_extensions: File extensions to process (default: all)
        """
        self.archive_root = Path(archive_root)
        self.scan_paths = scan_paths or [self.archive_root / "00_RAW"]
        self.supported_extensions = supported_extensions

        # Initialize storage and manifest handlers
        self.raw_storage = LocalFilesystemStorage(self.archive_root / "00_RAW")
        self.processed_storage = LocalFilesystemStorage(
            self.archive_root / "02_PROCESSED"
        )
        self.normalized_storage = LocalFilesystemStorage(
            self.archive_root / "03_NORMALIZED"
        )

        self.manifest_writer = ManifestWriter(self.archive_root / "01_MANIFEST")
        self.manifest_reader = ManifestReader(self.archive_root / "01_MANIFEST")

        self.path_builder = StoragePathBuilder()

    async def discover(self) -> AsyncIterator[DiscoveredItem]:
        """Discover files in scan paths.

        Yields DiscoveredItem for each file found.
        """
        for scan_path in self.scan_paths:
            if not scan_path.exists():
                continue

            for file_path in scan_path.rglob("*"):
                if not file_path.is_file():
                    continue

                # Skip metadata files
                if file_path.name.endswith(".meta.json"):
                    continue

                # Skip directory placeholders (not real content)
                if file_path.name == ".gitkeep":
                    continue

                # Skip this connector's own content-addressed storage
                # output; re-scanning it would re-ingest stored copies.
                try:
                    file_path.relative_to(self.archive_root / "00_RAW" / "local-files")
                    continue
                except ValueError:
                    pass

                # Skip if extension not supported
                if self.supported_extensions:
                    if file_path.suffix.lower() not in self.supported_extensions:
                        continue

                # Get file stats
                stat = file_path.stat()
                mtime = datetime.fromtimestamp(stat.st_mtime)

                # Detect MIME type
                mime_type, _ = mimetypes.guess_type(file_path)
                if mime_type is None:
                    mime_type = "application/octet-stream"

                # Create source identifier (relative path)
                try:
                    relative_path = file_path.relative_to(scan_path)
                except ValueError:
                    relative_path = file_path.name

                yield DiscoveredItem(
                    source_identifier=str(relative_path),
                    source_path=str(file_path),
                    relative_path=str(relative_path),
                    size_bytes=stat.st_size,
                    mtime=mtime,
                    mime_type=mime_type,
                    metadata={
                        "scan_path": str(scan_path),
                        "filename": file_path.name,
                        "extension": file_path.suffix,
                    },
                )

    async def acquire(self, item: DiscoveredItem) -> AcquiredItem:
        """Acquire file by copying to staging area.

        For local files, acquisition is simply recording the path.
        No copy is needed since we're already on the local filesystem.

        Args:
            item: Discovered item

        Returns:
            AcquiredItem with staging path
        """
        # For local files, staging = source (no copy needed)
        return AcquiredItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=item.metadata,
            staging_path=item.source_path,  # Same as source
        )

    async def verify(self, item: AcquiredItem) -> VerifiedItem:
        """Verify file is readable and extract basic metadata.

        Args:
            item: Acquired item

        Returns:
            VerifiedItem with extracted metadata

        Raises:
            Exception: If file cannot be read
        """
        file_path = Path(item.staging_path)

        # Verify file exists and is readable
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        # Try to read first few bytes to verify readability
        with open(file_path, "rb") as f:
            header = f.read(1024)

        # Extract basic metadata
        metadata = dict(item.metadata)
        metadata["verified"] = True
        metadata["verified_at"] = datetime.utcnow().isoformat()
        metadata["header_size"] = len(header)

        # Try to extract file-specific metadata
        try:
            if item.mime_type.startswith("image/"):
                metadata.update(self._extract_image_metadata(file_path))
            elif item.mime_type.startswith("audio/"):
                metadata.update(self._extract_audio_metadata(file_path))
            elif item.mime_type == "application/pdf":
                metadata.update(self._extract_pdf_metadata(file_path))
        except Exception as e:
            metadata["metadata_extraction_error"] = str(e)

        return VerifiedItem(
            source_identifier=item.source_identifier,
            source_path=item.source_path,
            relative_path=item.relative_path,
            size_bytes=item.size_bytes,
            mtime=item.mtime,
            mime_type=item.mime_type,
            metadata=metadata,
            staging_path=item.staging_path,
        )

    def hash(self, item: VerifiedItem) -> HashedItem:
        """Compute cryptographic hashes for the file.

        Args:
            item: Verified item

        Returns:
            HashedItem with SHA-256 and xxHash64
        """
        file_path = Path(item.staging_path)
        sha256, xxhash64 = compute_file_hashes(file_path)

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
        """Store file in immutable raw storage.

        Per RULE 2: Never destroy source data. Files are stored in a
        content-addressed structure under 00_RAW/.

        Args:
            item: Hashed item
            run_id: Ingestion run ID for the manifest entry

        Returns:
            StoredItem with archive path
        """
        # Detect duplicates against existing manifest entries (by SHA-256).
        # Files already under 00_RAW/ are skipped in discover(), so anything
        # found here is a genuinely new copy of previously ingested content.
        dedupe_status = DedupeStatus.UNIQUE
        dedupe_of = None
        existing = self.manifest_reader.get_entry_by_sha256(item.sha256)
        if existing is not None:
            dedupe_status = DedupeStatus.DUPLICATE_OF
            dedupe_of = existing.archive_id

        # Build the manifest entry before storage so StoredItem is complete.
        manifest_entry = ManifestEntry(
            archive_id=create_archive_id(item.sha256),
            source="local-files",
            source_identifier=item.source_identifier,
            original_filename=Path(item.source_path).name,
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            original_timestamp=item.mtime,
            acquisition_timestamp=datetime.utcnow(),
            sha256=item.sha256,
            xxhash64=item.xxhash64,
            connector="local-files",
            ingestion_run_id=run_id,
            privacy_classification=PrivacyClassification.PRIVATE,
            processing_status=ProcessingStatus.STORED,
            dedupe_status=dedupe_status,
            dedupe_of=dedupe_of,
        )

        # Build the connector-relative path. raw_object_path() includes the
        # 00_RAW/ prefix, and raw_storage is already rooted at 00_RAW/.
        archive_path = self.path_builder.raw_object_path(
            connector="local-files",
            date=item.mtime,
            sha256=item.sha256,
            original_filename=Path(item.source_path).name,
        )
        storage_key = archive_path[len("00_RAW/"):]

        if dedupe_status == DedupeStatus.DUPLICATE_OF:
            # Content already stored under the canonical archive_id; do not
            # write a second copy (RULE 2 keeps RAW append-only, dedup only
            # marks relationships). Point at the canonical stored path.
            assert existing is not None
            archive_path = self._archive_path_for(existing)
        else:
            # Store the file
            self.raw_storage.put(
                storage_key,
                Path(item.staging_path),
                metadata={
                    "source_identifier": item.source_identifier,
                    "mime_type": item.mime_type,
                    "original_mtime": item.mtime.isoformat(),
                    "sha256": item.sha256,
                    "xxhash64": item.xxhash64,
                },
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

    def _archive_path_for(self, entry: ManifestEntry) -> str:
        """Rebuild the canonical 00_RAW path for an existing manifest entry.

        Args:
            entry: Manifest entry of the canonical copy

        Returns:
            Relative path from LIFE_ARCHIVE root
        """
        return self.path_builder.raw_object_path(
            connector=entry.connector,
            date=entry.original_timestamp,
            sha256=parse_archive_id(entry.archive_id),
            original_filename=entry.original_filename,
        )

    async def index(
        self, item: StoredItem
    ) -> StoredItem:  # TODO: Return IndexedItem when search is implemented
        """Index file content for search.

        Currently a stub. Will integrate with Meilisearch/Qdrant when
        infrastructure is deployed.

        Args:
            item: Stored item

        Returns:
            IndexedItem (currently same as StoredItem)
        """
        # TODO: Extract text content
        # TODO: Generate embeddings
        # TODO: Index in Meilisearch (lexical) and Qdrant (semantic)
        return item

    async def normalize(
        self, item: StoredItem
    ) -> StoredItem:  # TODO: Return NormalizedItem
        """Normalize to canonical schema.

        Currently a stub. Will map to Document, Image, Person, etc. schemas.

        Args:
            item: Stored item

        Returns:
            NormalizedItem (currently same as StoredItem)
        """
        # TODO: Determine normalized type based on MIME type
        # TODO: Map to canonical schema
        # TODO: Store in 03_NORMALIZED/
        return item

    def log(self, item: StoredItem, run_id: str) -> None:
        """Write manifest entries for stored item.

        The manifest entry itself is built during store(); here we persist it
        and record the hash/acquisition audit trail.

        Args:
            item: Stored item
            run_id: Ingestion run ID
        """
        entry = item.manifest_entry

        # Write to manifests
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
            details={"archive_path": item.archive_path},
        )

    async def run(self, max_items: int | None = None) -> ConnectorResult:
        """Execute full ingestion pipeline.

        Args:
            max_items: Maximum number of items to process (for testing)

        Returns:
            ConnectorResult with statistics and status
        """
        run_id = str(uuid.uuid4())  # Using uuid4 instead of uuid7 (not available in Python 3.11)
        start_time = datetime.utcnow()

        items_discovered = 0
        items_processed = 0
        items_failed = 0
        items_skipped = 0
        bytes_processed = 0

        errors = []

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

            # Determine status
            if items_failed == 0:
                status = ForensicStatus.PASS
            elif items_processed > 0:
                status = ForensicStatus.PARTIAL
            else:
                status = ForensicStatus.FAIL

            # Write ingestion run record
            run_record = IngestionRun(
                run_id=run_id,
                connector="local-files",
                start_time=start_time,
                end_time=end_time,
                status=status.value,
                items_discovered=items_discovered,
                items_processed=items_processed,
                items_failed=items_failed,
                items_skipped=items_skipped,
                config_hash="local_files_config_v1",
            )
            self.manifest_writer.write_ingestion_run(run_record)

            return ConnectorResult(
                run_id=run_id,
                connector="local-files",
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
            # Record failed run
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            run_record = IngestionRun(
                run_id=run_id,
                connector="local-files",
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
                connector="local-files",
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

    def _extract_image_metadata(self, file_path: Path) -> dict:
        """Extract metadata from image files.

        Args:
            file_path: Path to image file

        Returns:
            Metadata dict
        """
        metadata = {}

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(file_path) as img:
                metadata["image_width"] = img.width
                metadata["image_height"] = img.height
                metadata["image_format"] = img.format

                # Extract EXIF data
                exif_data = img.getexif()
                if exif_data:
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        metadata[f"exif_{tag}"] = value

        except ImportError:
            metadata["image_metadata_error"] = "PIL not installed"
        except Exception as e:
            metadata["image_metadata_error"] = str(e)

        return metadata

    def _extract_audio_metadata(self, file_path: Path) -> dict:
        """Extract metadata from audio files.

        Args:
            file_path: Path to audio file

        Returns:
            Metadata dict
        """
        metadata = {}

        try:
            import mutagen

            audio = mutagen.File(file_path)
            if audio:
                metadata["audio_length"] = audio.info.length
                metadata["audio_bitrate"] = audio.info.bitrate
                metadata["audio_sample_rate"] = audio.info.sample_rate

                # Extract tags
                if audio.tags:
                    for key, value in audio.tags.items():
                        metadata[f"audio_tag_{key}"] = str(value)

        except ImportError:
            metadata["audio_metadata_error"] = "mutagen not installed"
        except Exception as e:
            metadata["audio_metadata_error"] = str(e)

        return metadata

    def _extract_pdf_metadata(self, file_path: Path) -> dict:
        """Extract metadata from PDF files.

        Args:
            file_path: Path to PDF file

        Returns:
            Metadata dict
        """
        metadata = {}

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            metadata["pdf_page_count"] = doc.page_count

            # Extract document metadata
            pdf_metadata = doc.metadata
            if pdf_metadata:
                for key, value in pdf_metadata.items():
                    if value:
                        metadata[f"pdf_{key}"] = value

            doc.close()

        except ImportError:
            metadata["pdf_metadata_error"] = "PyMuPDF not installed"
        except Exception as e:
            metadata["pdf_metadata_error"] = str(e)

        return metadata
