"""Database layer for Life Archive.

Provides SQLAlchemy models and async session management for the PostgreSQL
metadata database. Stores all structured metadata that supports the pipeline:
- Manifest entries
- Ingestion runs
- Processing status
- Entity relationships
- Research findings
- Evidence chains
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    type_annotation_map = {
        dict: String,
        Dict[str, Any]: String,  # type: ignore
    }


class ManifestEntryModel(Base):
    """SQLAlchemy model for manifest entries (source_manifest.jsonl equivalent)."""

    __tablename__ = "manifest_entries"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Archive ID (sha256:<hash>) - indexed for fast lookups
    archive_id: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)

    # Source information
    source: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_identifier: Mapped[str] = mapped_column(String, nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Size and timestamps
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acquisition_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Cryptographic hashes
    sha256: Mapped[str] = mapped_column(String, nullable=False, index=True)
    xxhash64: Mapped[Optional[str]] = mapped_column(String, index=True)

    # Processing information
    connector: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ingestion_run_id: Mapped[str] = mapped_column(
        String, ForeignKey("ingestion_runs.run_id"), nullable=False, index=True
    )

    # Privacy and processing status
    privacy_classification: Mapped[str] = mapped_column(String, nullable=False, index=True)
    processing_status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dedupe_status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    dedupe_of: Mapped[Optional[str]] = mapped_column(String, index=True)

    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    ingestion_run: Mapped["IngestionRunModel"] = relationship(
        "IngestionRunModel", foreign_keys=[ingestion_run_id], viewonly=True
    )


class IngestionRunModel(Base):
    """SQLAlchemy model for ingestion runs (ingestion_runs.jsonl equivalent)."""

    __tablename__ = "ingestion_runs"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Run information
    run_id: Mapped[str] = mapped_column(String, nullable=False, index=True, unique=True)
    connector: Mapped[str] = mapped_column(String, nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Status and statistics
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    items_discovered: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_processed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Configuration and error tracking
    config_hash: Mapped[str] = mapped_column(String, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(String)

    # Relationships
    manifest_entries: Mapped[list["ManifestEntryModel"]] = relationship(
        "ManifestEntryModel",
        foreign_keys=[ManifestEntryModel.ingestion_run_id],
        viewonly=True,
    )


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self, database_url: str):
        """Initialize database manager.

        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url
        self.engine = create_async_engine(database_url)
        self.sessionmaker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_tables(self):
        """Create all database tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self) -> AsyncSession:
        """Get a new database session.

        Returns an AsyncSession, which supports use as an async context
        manager (``async with manager.get_session() as session: ...``).
        """
        return self.sessionmaker()

    async def close(self):
        """Close the database engine."""
        await self.engine.dispose()

    # Manifest entry operations
    async def get_manifest_entry_by_id(self, archive_id: str) -> Optional[ManifestEntryModel]:
        """Get a manifest entry by archive ID.

        Args:
            archive_id: Archive ID to search for

        Returns:
            ManifestEntryModel or None
        """
        async with self.get_session() as session:
            stmt = select(ManifestEntryModel).where(ManifestEntryModel.archive_id == archive_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_manifest_entries_by_connector(
        self, connector: str, limit: int = 100
    ) -> list[ManifestEntryModel]:
        """Get manifest entries by connector.

        Args:
            connector: Connector ID
            limit: Maximum number of entries to return

        Returns:
            List of ManifestEntryModel
        """
        async with self.get_session() as session:
            stmt = (
                select(ManifestEntryModel)
                .where(ManifestEntryModel.connector == connector)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def get_manifest_entries_by_status(
        self, status: str, limit: int = 100
    ) -> list[ManifestEntryModel]:
        """Get manifest entries by processing status.

        Args:
            status: Processing status
            limit: Maximum number of entries to return

        Returns:
            List of ManifestEntryModel
        """
        async with self.get_session() as session:
            stmt = (
                select(ManifestEntryModel)
                .where(ManifestEntryModel.processing_status == status)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def count_manifest_entries(self) -> int:
        """Count total manifest entries.

        Returns:
            Total count
        """
        async with self.get_session() as session:
            stmt = select(func.count(ManifestEntryModel.id))
            result = await session.execute(stmt)
            return result.scalar_one()

    async def count_manifest_entries_by_connector(self, connector: str) -> int:
        """Count manifest entries by connector.

        Args:
            connector: Connector ID

        Returns:
            Count for connector
        """
        async with self.get_session() as session:
            stmt = select(func.count(ManifestEntryModel.id)).where(
                ManifestEntryModel.connector == connector
            )
            result = await session.execute(stmt)
            return result.scalar_one()

    # Ingestion run operations
    async def get_ingestion_run(self, run_id: str) -> Optional[IngestionRunModel]:
        """Get an ingestion run by ID.

        Args:
            run_id: Run ID to search for

        Returns:
            IngestionRunModel or None
        """
        async with self.get_session() as session:
            stmt = select(IngestionRunModel).where(IngestionRunModel.run_id == run_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_latest_ingestion_run(self, connector: str) -> Optional[IngestionRunModel]:
        """Get the latest ingestion run for a connector.

        Args:
            connector: Connector ID

        Returns:
            Latest IngestionRunModel or None
        """
        async with self.get_session() as session:
            stmt = (
                select(IngestionRunModel)
                .where(IngestionRunModel.connector == connector)
                .order_by(IngestionRunModel.start_time.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def get_recent_ingestion_runs(
        self, limit: int = 10
    ) -> list[IngestionRunModel]:
        """Get recent ingestion runs.

        Args:
            limit: Maximum number of runs to return

        Returns:
            List of IngestionRunModel
        """
        async with self.get_session() as session:
            stmt = (
                select(IngestionRunModel)
                .order_by(IngestionRunModel.start_time.desc())
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()

    async def create_ingestion_run(self, run_data: dict) -> IngestionRunModel:
        """Create a new ingestion run record.

        Args:
            run_data: Dictionary with run information

        Returns:
            Created IngestionRunModel
        """
        async with self.get_session() as session:
            run = IngestionRunModel(**run_data)
            session.add(run)
            await session.commit()
            await session.refresh(run)
            return run

    async def update_ingestion_run(self, run_id: str, update_data: dict) -> bool:
        """Update an ingestion run record.

        Args:
            run_id: Run ID to update
            update_data: Dictionary with fields to update

        Returns:
            True if updated, False if not found
        """
        async with self.get_session() as session:
            stmt = select(IngestionRunModel).where(IngestionRunModel.run_id == run_id)
            result = await session.execute(stmt)
            run = result.scalar_one_or_none()

            if not run:
                return False

            for key, value in update_data.items():
                setattr(run, key, value)

            await session.commit()
            return True

    async def create_manifest_entry(self, entry_data: dict) -> ManifestEntryModel:
        """Create a new manifest entry.

        Args:
            entry_data: Dictionary with entry information

        Returns:
            Created ManifestEntryModel
        """
        async with self.get_session() as session:
            entry = ManifestEntryModel(**entry_data)
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry


# Async helper for testing
async def test_database():
    """Test the database functionality."""
    import tempfile
    import os

    # Create a temporary SQLite database for testing
    temp_db = tempfile.mktemp(suffix=".db")
    db_url = f"sqlite+aiosqlite:///{temp_db}"

    try:
        db = DatabaseManager(db_url)
        await db.create_tables()

        # Test creating an ingestion run
        run_data = {
            "run_id": "test-run-1",
            "connector": "local-files",
            "status": "COMPLETED",
            "config_hash": "test-hash",
        }
        run = await db.create_ingestion_run(run_data)
        print(f"Created run: {run.run_id}")

        # Test creating a manifest entry
        entry_data = {
            "archive_id": "sha256:test-hash",
            "source": "local-files",
            "source_identifier": "test/file.txt",
            "original_filename": "file.txt",
            "mime_type": "text/plain",
            "size_bytes": 1024,
            "original_timestamp": datetime.utcnow(),
            "sha256": "test-hash",
            "connector": "local-files",
            "ingestion_run_id": "test-run-1",
            "privacy_classification": "PRIVATE",
            "processing_status": "INGESTED",
            "dedupe_status": "UNIQUE",
        }
        entry = await db.create_manifest_entry(entry_data)
        print(f"Created entry: {entry.archive_id}")

        # Test queries
        retrieved_run = await db.get_ingestion_run("test-run-1")
        print(f"Retrieved run: {retrieved_run.run_id if retrieved_run else 'None'}")

        retrieved_entry = await db.get_manifest_entry_by_id("sha256:test-hash")
        print(f"Retrieved entry: {retrieved_entry.archive_id if retrieved_entry else 'None'}")

        count = await db.count_manifest_entries()
        print(f"Total entries: {count}")

    finally:
        await db.close()
        if os.path.exists(temp_db):
            os.unlink(temp_db)


if __name__ == "__main__":
    asyncio.run(test_database())
