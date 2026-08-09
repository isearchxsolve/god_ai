"""Provenance and core data model schemas for Life Archive.

This module defines the foundational types for tracking data through the entire
pipeline from ingestion through publication. Every schema includes provenance
fields to maintain traceability back to source evidence.
"""

from datetime import datetime
from enum import StrEnum
from typing import Optional
from pydantic import BaseModel, Field


class PrivacyClassification(StrEnum):
    """Privacy classification for all data objects.

    RULE 9: Everything is PRIVATE by default.
    """

    PUBLIC = "PUBLIC"  # Cleared for publication
    PRIVATE = "PRIVATE"  # Default for all ingested data
    SENSITIVE = "SENSITIVE"  # Health, financial, biometric data
    THIRD_PARTY_PRIVATE = "THIRD_PARTY_PRIVATE"  # Other people's PII
    RESTRICTED = "RESTRICTED"  # Credentials, keys, secrets - NEVER in archive


class ProcessingStatus(StrEnum):
    """Processing status through the pipeline stages."""

    DISCOVERED = "DISCOVERED"
    ACQUIRED = "ACQUIRED"
    VERIFIED = "VERIFIED"
    HASHED = "HASHED"
    STORED = "STORED"
    INDEXED = "INDEXED"
    NORMALIZED = "NORMALIZED"
    LOGGED = "LOGGED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class DedupeStatus(StrEnum):
    """Deduplication status - NEVER delete from RAW, only mark relationships."""

    UNIQUE = "UNIQUE"
    DUPLICATE_OF = "DUPLICATE_OF"
    NEAR_DUPLICATE_OF = "NEAR_DUPLICATE_OF"
    VERSION_OF = "VERSION_OF"


class EvidenceClassification(StrEnum):
    """Classification of claims/findings per RULE 4.

    Never silently convert one category into another.
    """

    FACT = "FACT"  # Directly supported by evidence
    INFERENCE = "INFERENCE"  # Reasonable conclusion from evidence
    HYPOTHESIS = "HYPOTHESIS"  # Potential explanation requiring investigation
    INTERPRETATION = "INTERPRETATION"  # Higher-order intellectual interpretation
    UNPROVEN = "UNPROVEN"  # No evidence exists
    BLOCKED = "BLOCKED"  # Source cannot be accessed
    CONTRADICTION = "CONTRADICTION"  # Evidence conflicts
    UNVALIDATED = "UNVALIDATED"  # Cannot be validated


class ForensicStatus(StrEnum):
    """Forensic checkpoint status per RULE 11."""

    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    UNPROVEN = "UNPROVEN"
    CONTRADICTION = "CONTRADICTION"


class ManifestEntry(BaseModel):
    """Entry in the source manifest (one line per object in source_manifest.jsonl).

    Per spec Section 6: Every source object must be recorded with full provenance.
    """

    archive_id: str = Field(..., description="Format: sha256:<hash>")
    source: str = Field(..., description="Connector ID (e.g., 'gmail', 'google-drive')")
    source_identifier: str = Field(..., description="Source-specific ID")
    original_filename: str = Field(..., description="Original filename at source")
    mime_type: str = Field(..., description="MIME type of the object")
    size_bytes: int = Field(..., ge=0, description="Size in bytes")
    original_timestamp: datetime = Field(..., description="Timestamp from source")
    acquisition_timestamp: datetime = Field(
        ..., description="When we acquired the object"
    )
    sha256: str = Field(..., description="SHA-256 hash of object content")
    xxhash64: Optional[str] = Field(None, description="xxHash64 for fast dedup")
    connector: str = Field(..., description="Connector that ingested this")
    ingestion_run_id: str = Field(..., description="UUID v7 of ingestion run")
    privacy_classification: PrivacyClassification = Field(
        default=PrivacyClassification.PRIVATE
    )
    processing_status: ProcessingStatus = Field(default=ProcessingStatus.DISCOVERED)
    dedupe_status: DedupeStatus = Field(default=DedupeStatus.UNIQUE)
    dedupe_of: Optional[str] = Field(
        None, description="archive_id of canonical if duplicate"
    )
    error: Optional[str] = Field(None, description="Error message if failed")


class IngestionRun(BaseModel):
    """Record of a single ingestion run (one line per run in ingestion_runs.jsonl)."""

    run_id: str = Field(..., description="UUID (timestamp-ordered)")
    connector: str = Field(..., description="Connector ID")
    start_time: datetime = Field(...)
    end_time: Optional[datetime] = Field(None)
    status: str = Field(..., description="Ingestion run status")
    items_discovered: int = Field(default=0, ge=0)
    items_processed: int = Field(default=0, ge=0)
    items_failed: int = Field(default=0, ge=0)
    items_skipped: int = Field(default=0, ge=0)
    bytes_processed: int = Field(default=0, ge=0)
    config_hash: str = Field(default="", description="SHA-256 of connector config")
    error: Optional[str] = Field(None)


class DiscoveredItem(BaseModel):
    """Item discovered during connector discovery phase."""

    source_path: str = Field(..., description="Absolute path at source")
    relative_path: str = Field(..., description="Relative path within source")
    size_bytes: int = Field(..., ge=0)
    mtime: datetime = Field(..., description="Last modification time")
    mime_type: str = Field(..., description="Detected MIME type")
    source_identifier: str = Field(..., description="Source-specific ID")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


class AcquiredItem(DiscoveredItem):
    """Item after acquisition phase - copied to staging."""

    staging_path: str = Field(..., description="Path in staging area")


class VerifiedItem(AcquiredItem):
    """Item after verification phase - readability confirmed, metadata extracted."""

    verified: bool = Field(default=True)
    extracted_metadata: dict = Field(
        default_factory=dict, description="EXIF, ID3, PDF info, etc."
    )


class HashedItem(VerifiedItem):
    """Item after hashing phase - SHA-256 and xxHash64 computed."""

    sha256: str = Field(..., description="SHA-256 hash")
    xxhash64: Optional[str] = Field(None, description="xxHash64 for fast dedup (optional)")


class StoredItem(HashedItem):
    """Item after storage phase - written to 00_RAW with manifest entry."""

    archive_path: str = Field(..., description="Relative path in 00_RAW/")
    manifest_entry: ManifestEntry = Field(...)


class IndexedItem(StoredItem):
    """Item after indexing phase - text extracted, embeddings computed, entities found."""

    text_content: Optional[str] = Field(None, description="Extracted text")
    embedding_id: Optional[str] = Field(None, description="Qdrant point ID")
    search_doc_id: Optional[str] = Field(None, description="Meilisearch document ID")
    entities: list[dict] = Field(default_factory=list, description="Extracted entities")


class NormalizedItem(IndexedItem):
    """Item after normalization phase - mapped to canonical schema."""

    normalized_type: str = Field(..., description="Type: Document, Image, Person, etc.")
    normalized_data: dict = Field(..., description="Canonical schema data")


class ConnectorResult(BaseModel):
    """Final result of a connector run."""

    run_id: str
    connector: str
    status: ForensicStatus
    items_discovered: int
    items_processed: int
    items_failed: int
    items_skipped: int
    bytes_processed: int
    duration_seconds: float
    errors: list[str] = Field(default_factory=list)
    forensic_evidence: dict = Field(default_factory=dict)
