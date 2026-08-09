"""Manifest module for Life Archive.

Handles reading and writing JSONL manifest files that track all ingested objects
through the pipeline. Per spec Section 6, every source object must be recorded
with full provenance.

Manifest files (all JSONL format):
- source_manifest.jsonl: One entry per ingested object
- acquisition_log.jsonl: Log of acquisition events
- hashes.jsonl: Hash records for deduplication
- ingestion_runs.jsonl: Log of ingestion runs
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Generator, Union

import orjson

from life_archive.schemas.provenance import (
    IngestionRun,
    ManifestEntry,
    ProcessingStatus,
)


class ManifestWriter:
    """Writes entries to JSONL manifest files.

    Each manifest file is append-only to maintain an immutable audit trail.
    """

    def __init__(self, manifest_dir: Union[str, Path]):
        """Initialize manifest writer.

        Args:
            manifest_dir: Path to 01_MANIFEST/ directory
        """
        self.manifest_dir = Path(manifest_dir)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

        self.source_manifest_path = self.manifest_dir / "source_manifest.jsonl"
        self.acquisition_log_path = self.manifest_dir / "acquisition_log.jsonl"
        self.hashes_path = self.manifest_dir / "hashes.jsonl"
        self.ingestion_runs_path = self.manifest_dir / "ingestion_runs.jsonl"

    def write_manifest_entry(self, entry: ManifestEntry) -> None:
        """Write a manifest entry to source_manifest.jsonl.

        Args:
            entry: Manifest entry to write
        """
        self._append_jsonl(self.source_manifest_path, entry)

    def write_acquisition_log(
        self,
        archive_id: str,
        source: str,
        action: str,
        details: dict | None = None,
    ) -> None:
        """Write an acquisition log entry.

        Args:
            archive_id: Archive ID of the object
            source: Source connector
            action: Action performed (e.g., "acquired", "verified", "stored")
            details: Additional details
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "archive_id": archive_id,
            "source": source,
            "action": action,
            "details": details or {},
        }
        self._append_jsonl(self.acquisition_log_path, log_entry)

    def write_hash_record(
        self,
        archive_id: str,
        sha256: str,
        xxhash64: str | None = None,
    ) -> None:
        """Write a hash record for deduplication.

        Args:
            archive_id: Archive ID (sha256:<hash>)
            sha256: SHA-256 hash
            xxhash64: xxHash64 hash (optional)
        """
        hash_record = {
            "archive_id": archive_id,
            "sha256": sha256,
            "xxhash64": xxhash64,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._append_jsonl(self.hashes_path, hash_record)

    def write_ingestion_run(self, run: IngestionRun) -> None:
        """Write an ingestion run record.

        Args:
            run: Ingestion run to write
        """
        self._append_jsonl(self.ingestion_runs_path, run)

    def _append_jsonl(self, path: Path, obj: Union[dict, object]) -> None:
        """Append an object as JSON to a JSONL file.

        Args:
            path: Path to JSONL file
            obj: Object to serialize (dict or Pydantic model)
        """
        # Convert Pydantic models to dict
        if hasattr(obj, "model_dump"):
            data = obj.model_dump(mode="json")
        else:
            data = obj

        # Use orjson for fast serialization
        line = orjson.dumps(data) + b"\n"

        with open(path, "ab") as f:
            f.write(line)


class ManifestReader:
    """Reads entries from JSONL manifest files."""

    def __init__(self, manifest_dir: Union[str, Path]):
        """Initialize manifest reader.

        Args:
            manifest_dir: Path to 01_MANIFEST/ directory
        """
        self.manifest_dir = Path(manifest_dir)
        self.source_manifest_path = self.manifest_dir / "source_manifest.jsonl"
        self.acquisition_log_path = self.manifest_dir / "acquisition_log.jsonl"
        self.hashes_path = self.manifest_dir / "hashes.jsonl"
        self.ingestion_runs_path = self.manifest_dir / "ingestion_runs.jsonl"

    def read_manifest_entries(self) -> Generator[ManifestEntry, None, None]:
        """Read all manifest entries.

        Yields:
            ManifestEntry objects
        """
        yield from self._read_jsonl(self.source_manifest_path, ManifestEntry)

    def read_acquisition_log(self) -> Generator[dict, None, None]:
        """Read all acquisition log entries.

        Yields:
            Dict objects
        """
        yield from self._read_jsonl(self.acquisition_log_path, dict)

    def read_hash_records(self) -> Generator[dict, None, None]:
        """Read all hash records.

        Yields:
            Dict objects with archive_id, sha256, xxhash64
        """
        yield from self._read_jsonl(self.hashes_path, dict)

    def read_ingestion_runs(self) -> Generator[IngestionRun, None, None]:
        """Read all ingestion runs.

        Yields:
            IngestionRun objects
        """
        yield from self._read_jsonl(self.ingestion_runs_path, IngestionRun)

    def get_entry_by_archive_id(self, archive_id: str) -> ManifestEntry | None:
        """Get a manifest entry by archive ID.

        Args:
            archive_id: Archive ID to search for

        Returns:
            ManifestEntry or None if not found
        """
        for entry in self.read_manifest_entries():
            if entry.archive_id == archive_id:
                return entry
        return None

    def get_entry_by_sha256(self, sha256: str) -> ManifestEntry | None:
        """Get a manifest entry by SHA-256 hash.

        Args:
            sha256: SHA-256 hash to search for

        Returns:
            ManifestEntry or None if not found
        """
        for entry in self.read_manifest_entries():
            if entry.sha256 == sha256:
                return entry
        return None

    def get_latest_run(self, connector: str) -> IngestionRun | None:
        """Get the latest ingestion run for a connector.

        Args:
            connector: Connector ID

        Returns:
            IngestionRun or None if no runs found
        """
        runs = [
            run for run in self.read_ingestion_runs() if run.connector == connector
        ]
        return max(runs, key=lambda r: r.start_time) if runs else None

    def count_entries(self, status: ProcessingStatus | None = None) -> int:
        """Count manifest entries, optionally filtered by status.

        Args:
            status: Optional status filter

        Returns:
            Count of entries
        """
        count = 0
        for entry in self.read_manifest_entries():
            if status is None or entry.processing_status == status:
                count += 1
        return count

    def _read_jsonl(self, path: Path, model_class: type) -> Generator:
        """Read JSONL file and yield objects.

        Args:
            path: Path to JSONL file
            model_class: Class to instantiate (dict or Pydantic model)

        Yields:
            Objects of model_class
        """
        if not path.exists():
            return

        with open(path, "rb") as f:
            for line in f:
                if not line.strip():
                    continue
                data = orjson.loads(line)
                if model_class == dict:
                    yield data
                else:
                    yield model_class.model_validate(data)


def create_archive_id(sha256: str) -> str:
    """Create an archive ID from a SHA-256 hash.

    Format: sha256:<hash>

    Args:
        sha256: SHA-256 hash

    Returns:
        Archive ID string
    """
    return f"sha256:{sha256}"


def parse_archive_id(archive_id: str) -> str:
    """Parse a SHA-256 hash from an archive ID.

    Args:
        archive_id: Archive ID (sha256:<hash>)

    Returns:
        SHA-256 hash string

    Raises:
        ValueError: If archive_id format is invalid
    """
    if not archive_id.startswith("sha256:"):
        raise ValueError(f"Invalid archive_id format: {archive_id}")
    return archive_id[7:]
