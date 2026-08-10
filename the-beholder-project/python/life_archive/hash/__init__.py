"""Hashing module for Life Archive.

Provides cryptographic and non-cryptographic hashing for:
- SHA-256: Provenance verification, immutable storage (RULE 2: Never destroy source data)
- xxHash64: Fast deduplication hints (not for provenance)

All hashing is streaming to handle large files (videos, archives) without
loading entire file into memory.
"""

import hashlib
from pathlib import Path
from typing import BinaryIO, Union

try:
    import xxhash
except ImportError:
    xxhash = None  # xxhash is optional for fast dedup


# Default chunk size for streaming (8 MB)
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024


def hash_file_sha256(
    file_path: Union[str, Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Compute SHA-256 hash of a file using streaming reads.

    This is the primary provenance hash. Per RULE 2, raw source material must
    be immutable. The SHA-256 hash provides cryptographic verification that
    the stored object has not been modified since ingestion.

    Args:
        file_path: Path to the file to hash
        chunk_size: Size of chunks to read at a time (default 8 MB)

    Returns:
        Hex-encoded SHA-256 hash string

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If file cannot be read
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)

    return sha256.hexdigest()


def hash_file_xxhash64(
    file_path: Union[str, Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str | None:
    """Compute xxHash64 of a file for fast deduplication hints.

    xxHash64 is NOT for provenance - it's a non-cryptographic hash used for
    quick duplicate detection. The primary dedup check is SHA-256; xxHash64
    is used as a fast pre-filter.

    Args:
        file_path: Path to the file to hash
        chunk_size: Size of chunks to read at a time (default 8 MB)

    Returns:
        Hex-encoded xxHash64 string, or None if xxhash not installed
    """
    if xxhash is None:
        return None

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    xxh = xxhash.xxh64()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            xxh.update(chunk)

    return xxh.hexdigest()


def hash_stream_sha256(stream: BinaryIO) -> str:
    """Compute SHA-256 hash from a binary stream.

    Useful for hashing data that's already in memory or from a network stream.

    Args:
        stream: Binary IO stream to read from

    Returns:
        Hex-encoded SHA-256 hash string
    """
    sha256 = hashlib.sha256()

    while True:
        chunk = stream.read(DEFAULT_CHUNK_SIZE)
        if not chunk:
            break
        sha256.update(chunk)

    return sha256.hexdigest()


def hash_bytes_sha256(data: bytes) -> str:
    """Compute SHA-256 hash of bytes in memory.

    Args:
        data: Bytes to hash

    Returns:
        Hex-encoded SHA-256 hash string
    """
    return hashlib.sha256(data).hexdigest()


def hash_bytes_xxhash64(data: bytes) -> str | None:
    """Compute xxHash64 of bytes in memory.

    Args:
        data: Bytes to hash

    Returns:
        Hex-encoded xxHash64 string, or None if xxhash not installed
    """
    if xxhash is None:
        return None
    return xxhash.xxh64(data).hexdigest()


def verify_file_hash(
    file_path: Union[str, Path],
    expected_sha256: str,
    expected_xxhash64: str | None = None,
) -> tuple[bool, str, str | None]:
    """Verify a file's hash matches expected values.

    Args:
        file_path: Path to the file to verify
        expected_sha256: Expected SHA-256 hash
        expected_xxhash64: Expected xxHash64 hash (optional)

    Returns:
        Tuple of (sha256_match, actual_sha256, actual_xxhash64)
    """
    actual_sha256 = hash_file_sha256(file_path)
    actual_xxhash64 = hash_file_xxhash64(file_path)

    sha256_match = actual_sha256.lower() == expected_sha256.lower()
    xxhash_match = (
        expected_xxhash64 is None
        or actual_xxhash64 is None
        or actual_xxhash64.lower() == expected_xxhash64.lower()
    )

    return sha256_match and xxhash_match, actual_sha256, actual_xxhash64


def compute_file_hashes(
    file_path: Union[str, Path],
) -> tuple[str, str | None]:
    """Compute both SHA-256 and xxHash64 for a file in a single pass.

    More efficient than calling hash_file_sha256 and hash_file_xxhash64
    separately as it only reads the file once.

    Args:
        file_path: Path to the file to hash

    Returns:
        Tuple of (sha256_hex, xxhash64_hex)
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256 = hashlib.sha256()
    xxh = xxhash.xxh64() if xxhash else None

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(DEFAULT_CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
            if xxh:
                xxh.update(chunk)

    return sha256.hexdigest(), xxh.hexdigest() if xxh else None
