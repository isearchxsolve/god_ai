"""Storage abstraction for Life Archive.

Provides a unified interface for object storage that can work with:
- Local filesystem (development/pilot)
- MinIO/S3 (production)
- Cloud storage (future)

Per RULE 2: Never destroy source data. Storage is append-only for raw objects.
"""

import shutil
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Union


class StorageBackend:
    """Abstract base for storage backends."""

    def put(
        self,
        key: str,
        data: Union[bytes, BinaryIO, Path],
        metadata: dict | None = None,
    ) -> str:
        """Store an object.

        Args:
            key: Object key/path
            data: Data to store (bytes, file object, or path)
            metadata: Optional metadata

        Returns:
            Storage path/URL
        """
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        """Retrieve an object.

        Args:
            key: Object key/path

        Returns:
            Object bytes
        """
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        """Check if an object exists.

        Args:
            key: Object key/path

        Returns:
            True if exists
        """
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """Delete an object (use with caution - raw storage should never delete).

        Args:
            key: Object key/path
        """
        raise NotImplementedError

    def list(self, prefix: str = "") -> list[str]:
        """List objects with a prefix.

        Args:
            prefix: Key prefix

        Returns:
            List of keys
        """
        raise NotImplementedError


class LocalFilesystemStorage(StorageBackend):
    """Local filesystem storage backend.

    Suitable for development, pilot, and single-machine deployments.
    Objects are stored in a directory structure under a root path.
    """

    def __init__(self, root_path: Union[str, Path]):
        """Initialize local filesystem storage.

        Args:
            root_path: Root directory for storage
        """
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)

    def put(
        self,
        key: str,
        data: Union[bytes, BinaryIO, Path],
        metadata: dict | None = None,
    ) -> str:
        """Store an object to local filesystem.

        Args:
            key: Relative path from root
            data: Data to store (bytes, file object, or path to copy)
            metadata: Optional metadata (stored as .meta.json)

        Returns:
            Absolute path to stored file
        """
        file_path = self.root_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(data, Path):
            # Copy from another path
            shutil.copy2(data, file_path)
        elif isinstance(data, bytes):
            # Write bytes directly
            file_path.write_bytes(data)
        else:
            # Write from file object
            with open(file_path, "wb") as f:
                shutil.copyfileobj(data, f)

        # Store metadata if provided
        if metadata:
            import json
            meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, default=str)  # default=str handles datetime objects

        return str(file_path)

    def get(self, key: str) -> bytes:
        """Retrieve an object from local filesystem.

        Args:
            key: Relative path from root

        Returns:
            Object bytes

        Raises:
            FileNotFoundError: If object doesn't exist
        """
        file_path = self.root_path / key
        if not file_path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return file_path.read_bytes()

    def get_path(self, key: str) -> Path:
        """Get the absolute path to an object.

        Args:
            key: Relative path from root

        Returns:
            Absolute Path object

        Raises:
            FileNotFoundError: If object doesn't exist
        """
        file_path = self.root_path / key
        if not file_path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return file_path

    def exists(self, key: str) -> bool:
        """Check if an object exists.

        Args:
            key: Relative path from root

        Returns:
            True if exists
        """
        return (self.root_path / key).exists()

    def delete(self, key: str) -> None:
        """Delete an object.

        WARNING: Per RULE 2, never delete from 00_RAW/. Use only for temp/staging.

        Args:
            key: Relative path from root
        """
        file_path = self.root_path / key
        if file_path.exists():
            file_path.unlink()

    def list(self, prefix: str = "") -> list[str]:
        """List objects with a prefix.

        Args:
            prefix: Key prefix (relative path)

        Returns:
            List of relative keys
        """
        search_path = self.root_path / prefix if prefix else self.root_path
        if not search_path.exists():
            return []

        keys = []
        for path in search_path.rglob("*"):
            if path.is_file() and not path.name.endswith(".meta.json"):
                keys.append(str(path.relative_to(self.root_path)))

        return sorted(keys)

    def get_metadata(self, key: str) -> dict | None:
        """Get metadata for an object.

        Args:
            key: Object key

        Returns:
            Metadata dict or None
        """
        import json
        file_path = self.root_path / key
        meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
        if meta_path.exists():
            return json.loads(meta_path.read_text())
        return None


class StoragePathBuilder:
    """Builds standardized storage paths for archive objects.

    Ensures consistent path structure across all connectors.
    """

    @staticmethod
    def raw_object_path(
        connector: str,
        date: datetime,
        sha256: str,
        original_filename: str,
    ) -> str:
        """Build path for raw object storage.

        Structure: 00_RAW/{connector}/{YYYY-MM-DD}/{sha256[:2]}/{sha256}_{filename}

        Args:
            connector: Connector ID
            date: Acquisition date
            sha256: SHA-256 hash
            original_filename: Original filename

        Returns:
            Relative path from LIFE_ARCHIVE root
        """
        date_str = date.strftime("%Y-%m-%d")
        prefix = sha256[:2]
        safe_filename = "".join(c if c.isalnum() or c in "._-" else "_" for c in original_filename)
        return f"00_RAW/{connector}/{date_str}/{prefix}/{sha256}_{safe_filename}"

    @staticmethod
    def processed_path(
        archive_id: str,
        processing_type: str,
        extension: str,
    ) -> str:
        """Build path for processed object storage.

        Structure: 02_PROCESSED/{processing_type}/{archive_id_prefix}/{archive_id}.{ext}

        Args:
            archive_id: Archive ID (sha256:<hash>)
            processing_type: Type (ocr, transcript, etc.)
            extension: File extension

        Returns:
            Relative path from LIFE_ARCHIVE root
        """
        prefix = archive_id.split(":")[-1][:2]
        return f"02_PROCESSED/{processing_type}/{prefix}/{archive_id.replace(':', '_')}.{extension}"

    @staticmethod
    def normalized_path(
        normalized_type: str,
        archive_id: str,
    ) -> str:
        """Build path for normalized object storage.

        Structure: 03_NORMALIZED/{type}/{archive_id_prefix}/{archive_id}.json

        Args:
            normalized_type: Type (document, image, person, etc.)
            archive_id: Archive ID

        Returns:
            Relative path from LIFE_ARCHIVE root
        """
        prefix = archive_id.split(":")[-1][:2]
        return f"03_NORMALIZED/{normalized_type}/{prefix}/{archive_id.replace(':', '_')}.json"
