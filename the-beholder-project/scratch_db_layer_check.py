"""Scratch: run the project DatabaseManager against native PostgreSQL."""

import asyncio
from datetime import datetime, timezone

from dotenv import dotenv_values

# A stale system-level DATABASE_URL (another project) shadows .env for
# os.environ reads; load the project value from .env explicitly.
DATABASE_URL = dotenv_values(".env")["DATABASE_URL"]

from life_archive.db import (  # noqa: E402
    DatabaseManager,
    IngestionRunModel,
    ManifestEntryModel,
)


async def main():
    db = DatabaseManager(DATABASE_URL)
    await db.create_tables()
    print("create_tables: OK")

    run_id = "run-proto-pg-smoke"
    async with db.get_session() as session:
        session.add(
            IngestionRunModel(
                run_id=run_id,
                connector="local-files",
                status="SUCCESS",
                items_discovered=1,
                items_processed=1,
                config_hash="proto",
            )
        )
        session.add(
            ManifestEntryModel(
                archive_id="sha256:proto_smoke_0001",
                source="local-files",
                source_identifier="proto/smoke.txt",
                original_filename="smoke.txt",
                mime_type="text/plain",
                size_bytes=12,
                original_timestamp=datetime.now(timezone.utc),
                sha256="proto_smoke_0001",
                connector="local-files",
                ingestion_run_id=run_id,
                privacy_classification="PRIVATE",
                processing_status="STORED",
                dedupe_status="UNIQUE",
            )
        )
        await session.commit()
    print("insert run + manifest entry: OK")

    entry = await db.get_manifest_entry_by_id("sha256:proto_smoke_0001")
    print("query by archive_id:", entry.original_filename, entry.processing_status)
    print("count:", await db.count_manifest_entries())
    run = await db.get_ingestion_run(run_id)
    print("run lookup:", run.status, "entries linked:", len(run.manifest_entries))
    await db.close()
    print("DatabaseManager vs PostgreSQL: ALL OK")


if __name__ == "__main__":
    asyncio.run(main())
