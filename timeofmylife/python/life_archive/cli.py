"""Command-line interface for Life Archive.

Provides commands for:
- Ingesting data from various sources
- Querying the archive
- Managing the pipeline
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from life_archive.connectors.git import GitConnector
from life_archive.connectors.github import GitHubConnector
from life_archive.connectors.google_takeout import GoogleTakeoutConnector
from life_archive.connectors.linkedin import LinkedInConnector
from life_archive.connectors.local_files import LocalFilesConnector
from life_archive.connectors.whatsapp import WhatsAppConnector
from life_archive.hash import hash_file_sha256
from life_archive.manifest import ManifestReader
from life_archive.schemas.provenance import DedupeStatus
from life_archive.storage import StoragePathBuilder

app = typer.Typer(
    name="life-archive",
    help="Complete digital life research and publishing platform",
    add_completion=False,
)
console = Console()

CONNECTORS = {
    "local-files": LocalFilesConnector,
    "git": GitConnector,
    "github": GitHubConnector,
    "google-takeout": GoogleTakeoutConnector,
    "whatsapp": WhatsAppConnector,
    "linkedin": LinkedInConnector,
}


@app.command()
def ingest(
    source: str = typer.Argument(..., help="Source connector (e.g., 'local-files')"),
    archive_root: Path = typer.Option(
        Path("LIFE_ARCHIVE"),
        help="Path to LIFE_ARCHIVE directory",
    ),
    max_items: Optional[int] = typer.Option(
        None,
        help="Maximum number of items to process",
    ),
):
    """Ingest data from a source connector.

    Examples:
        life-archive ingest local-files
        life-archive ingest local-files --max-items 10
        life-archive ingest git
        life-archive ingest github
        life-archive ingest google-takeout
        life-archive ingest whatsapp
        life-archive ingest linkedin
    """
    console.print(f"[bold blue]Starting ingestion from:[/bold blue] {source}")
    console.print(f"[bold blue]Archive root:[/bold blue] {archive_root}")

    connector_cls = CONNECTORS.get(source)
    if connector_cls is None:
        console.print(f"[bold red]Unknown source:[/bold red] {source}")
        console.print(f"Available sources: {', '.join(sorted(CONNECTORS))}")
        raise typer.Exit(1)

    connector = connector_cls(archive_root=archive_root)
    result = asyncio.run(connector.run(max_items=max_items))

    # Display results
    console.print("\n[bold]Ingestion Results[/bold]")
    console.print(f"Run ID: {result.run_id}")
    console.print(f"Status: {result.status.value}")
    console.print(f"Duration: {result.duration_seconds:.2f}s")

    table = Table(title="Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")

    table.add_row("Items Discovered", str(result.items_discovered))
    table.add_row("Items Processed", str(result.items_processed))
    table.add_row("Items Failed", str(result.items_failed))
    table.add_row("Items Skipped", str(result.items_skipped))

    console.print(table)

    if result.errors:
        console.print(f"\n[bold red]Errors ({len(result.errors)}):[/bold red]")
        for error in result.errors[:10]:  # Show first 10
            console.print(f"  - {error}")
        if len(result.errors) > 10:
            console.print(f"  ... and {len(result.errors) - 10} more")

    console.print("\n[bold green]Manifest files updated:[/bold green]")
    console.print("  - 01_MANIFEST/source_manifest.jsonl")
    console.print("  - 01_MANIFEST/hashes.jsonl")
    console.print("  - 01_MANIFEST/acquisition_log.jsonl")
    console.print("  - 01_MANIFEST/ingestion_runs.jsonl")


@app.command()
def sources():
    """List available source connectors."""
    table = Table(title="Available Connectors")
    table.add_column("Source", style="cyan")
    table.add_column("Credentials Required", style="magenta")

    credential_notes = {
        "local-files": "None",
        "git": "None (local git CLI)",
        "github": "GITHUB_PAT env var required",
        "google-takeout": "None (manual export)",
        "whatsapp": "None (manual export)",
        "linkedin": "None (manual export)",
    }
    for name in sorted(CONNECTORS):
        table.add_row(name, credential_notes.get(name, "Unknown"))

    console.print(table)


@app.command()
def status(
    archive_root: Path = typer.Option(
        Path("LIFE_ARCHIVE"),
        help="Path to LIFE_ARCHIVE directory",
    ),
):
    """Show archive status and statistics.

    Displays:
    - Total objects ingested
    - Objects by source
    - Objects by status
    - Recent ingestion runs
    """
    console.print(f"[bold blue]Archive root:[/bold blue] {archive_root}")

    reader = ManifestReader(archive_root / "01_MANIFEST")

    # Count entries by source
    source_counts = {}
    status_counts = {}
    total_size = 0

    for entry in reader.read_manifest_entries():
        source_counts[entry.source] = source_counts.get(entry.source, 0) + 1
        status_counts[entry.processing_status] = (
            status_counts.get(entry.processing_status, 0) + 1
        )
        total_size += entry.size_bytes

    # Display summary
    console.print("\n[bold]Archive Summary[/bold]")

    table = Table(title="By Source")
    table.add_column("Source", style="cyan")
    table.add_column("Count", style="magenta", justify="right")

    for source, count in sorted(source_counts.items()):
        table.add_row(source, str(count))

    console.print(table)

    # Status breakdown
    table2 = Table(title="By Status")
    table2.add_column("Status", style="cyan")
    table2.add_column("Count", style="magenta", justify="right")

    for status, count in sorted(status_counts.items()):
        table2.add_row(status.value, str(count))

    console.print(table2)

    # Total size
    size_mb = total_size / (1024 * 1024)
    console.print(f"\n[bold]Total size:[/bold] {size_mb:.2f} MB")

    # Recent runs
    runs = list(reader.read_ingestion_runs())
    if runs:
        console.print("\n[bold]Recent Ingestion Runs[/bold]")
        table3 = Table()
        table3.add_column("Run ID", style="cyan")
        table3.add_column("Connector", style="magenta")
        table3.add_column("Status", style="green")
        table3.add_column("Items", style="blue", justify="right")
        table3.add_column("Time", style="yellow")

        for run in runs[-10:]:  # Last 10 runs
            table3.add_row(
                run.run_id[:8] + "...",
                run.connector,
                run.status,
                str(run.items_processed),
                run.start_time.strftime("%Y-%m-%d %H:%M"),
            )

        console.print(table3)


@app.command()
def verify(
    archive_root: Path = typer.Option(
        Path("LIFE_ARCHIVE"),
        help="Path to LIFE_ARCHIVE directory",
    ),
    source: Optional[str] = typer.Option(
        None,
        help="Filter by source connector",
    ),
):
    """Verify archive integrity.

    Checks that:
    - All manifest entries have corresponding files in 00_RAW/
    - File hashes match manifest records
    """
    console.print(f"[bold blue]Verifying archive integrity[/bold blue]")
    console.print(f"[bold blue]Archive root:[/bold blue] {archive_root}")

    reader = ManifestReader(archive_root / "01_MANIFEST")
    path_builder = StoragePathBuilder()

    verified = 0
    missing = 0
    hash_mismatch = 0

    for entry in reader.read_manifest_entries():
        if source and entry.source != source:
            continue

        # Duplicate entries reference the canonical copy; the canonical
        # entry is what gets checked.
        if entry.dedupe_status == DedupeStatus.DUPLICATE_OF:
            continue

        # Rebuild the content-addressed path used by store()
        rel_path = path_builder.raw_object_path(
            connector=entry.connector,
            date=entry.original_timestamp,
            sha256=entry.sha256,
            original_filename=entry.original_filename,
        )
        file_path = archive_root / rel_path

        console.print(f"  Checking {entry.archive_id[:20]}... ", end="")

        if not file_path.exists():
            missing += 1
            console.print(f"[red]MISSING[/red] ({rel_path})")
            continue

        actual_sha256 = hash_file_sha256(file_path)
        if actual_sha256.lower() != entry.sha256.lower():
            hash_mismatch += 1
            console.print(f"[red]HASH MISMATCH[/red]")
        else:
            verified += 1
            console.print("[green]OK[/green]")

    console.print(f"\n[bold]Verification Results[/bold]")
    console.print(f"  Verified: {verified}")
    console.print(f"  Missing: {missing}")
    console.print(f"  Hash mismatch: {hash_mismatch}")

    if verified == 0 and missing == 0 and hash_mismatch == 0:
        console.print("\n[bold yellow][WARN] No entries checked (manifest empty or fully filtered)[/bold yellow]")
        raise typer.Exit(1)

    if missing == 0 and hash_mismatch == 0:
        console.print("\n[bold green][OK] Archive integrity verified[/bold green]")
    else:
        console.print("\n[bold red][FAIL] Archive integrity check failed[/bold red]")
        raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    archive_root: Path = typer.Option(
        Path("LIFE_ARCHIVE"),
        help="Path to LIFE_ARCHIVE directory",
    ),
    limit: int = typer.Option(10, help="Maximum results"),
):
    """Search the archive.

    Currently searches manifest entries by filename or MIME type.
    Will integrate with Meilisearch/Qdrant when deployed.
    """
    console.print(f"[bold blue]Searching for:[/bold blue] {query}")

    reader = ManifestReader(archive_root / "01_MANIFEST")
    results = []

    for entry in reader.read_manifest_entries():
        # Simple text search in filename and MIME type
        if (
            query.lower() in entry.original_filename.lower()
            or query.lower() in entry.mime_type.lower()
        ):
            results.append(entry)
            if len(results) >= limit:
                break

    if not results:
        console.print("[yellow]No results found[/yellow]")
        return

    console.print(f"\n[bold]Results ({len(results)})[/bold]")

    table = Table()
    table.add_column("Filename", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("MIME Type", style="blue")
    table.add_column("Size", style="green", justify="right")
    table.add_column("Date", style="yellow")

    for entry in results:
        size_kb = entry.size_bytes / 1024
        table.add_row(
            entry.original_filename[:40],
            entry.source,
            entry.mime_type,
            f"{size_kb:.1f} KB",
            entry.original_timestamp.strftime("%Y-%m-%d"),
        )

    console.print(table)


if __name__ == "__main__":
    app()
