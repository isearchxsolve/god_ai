"""Streaming hash behavior (AGENTS.md: hashing tests)."""

import hashlib

from life_archive.hash import (
    compute_file_hashes,
    hash_bytes_sha256,
    hash_file_sha256,
    verify_file_hash,
)

KNOWN_SHA256_EMPTY = hashlib.sha256(b"").hexdigest()
KNOWN_SHA256_ABC = hashlib.sha256(b"abc").hexdigest()


def test_hash_bytes_matches_hashlib():
    assert hash_bytes_sha256(b"") == KNOWN_SHA256_EMPTY
    assert hash_bytes_sha256(b"abc") == KNOWN_SHA256_ABC


def test_hash_file_streaming_matches_chunked_reference(tmp_path):
    """Streaming file hash must equal the reference digest for any chunk size."""
    data = b"provenance-check-" * 1000
    file_path = tmp_path / "payload.bin"
    file_path.write_bytes(data)

    expected = hashlib.sha256(data).hexdigest()
    assert hash_file_sha256(file_path) == expected
    # Chunk smaller than file: still identical (streaming correctness)
    assert hash_file_sha256(file_path, chunk_size=7) == expected


def test_compute_file_hashes_single_pass_consistent(tmp_path):
    data = b"single-pass"
    file_path = tmp_path / "one_pass.bin"
    file_path.write_bytes(data)

    sha256, xxhash64 = compute_file_hashes(file_path)
    assert sha256 == hashlib.sha256(data).hexdigest()
    # xxhash64 is None only when the optional dependency is absent
    if xxhash64 is not None:
        second_sha, second_xx = compute_file_hashes(file_path)
        assert (sha256, xxhash64) == (second_sha, second_xx)


def test_verify_file_hash_detects_mismatch(tmp_path):
    file_path = tmp_path / "check.bin"
    file_path.write_bytes(b"original")

    ok, actual_sha, _ = verify_file_hash(file_path, hashlib.sha256(b"original").hexdigest())
    assert ok is True
    assert actual_sha == hashlib.sha256(b"original").hexdigest()

    ok, _, _ = verify_file_hash(file_path, "0" * 64)
    assert ok is False
