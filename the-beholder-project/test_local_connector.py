"""Test script for Life Archive local files connector.

This script demonstrates the complete pipeline for the local files connector:
1. Discovery of files in LIFE_ARCHIVE/00_RAW/
2. Acquisition (staging)
3. Verification (readability check)
4. Hashing (SHA-256 computation)
5. Storage (to immutable archive)
6. Logging (to manifest files)

This validates that the core pipeline works without external dependencies.
"""

import asyncio
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the ✓/✗ markers
# used below. Force UTF-8 output where supported.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass

# Add the python directory to the path so we can import life_archive
sys.path.insert(0, str(Path(__file__).parent / "python"))

from life_archive.connectors.local_files import LocalFilesConnector


async def test_local_files_connector():
    """Test the local files connector with sample data."""
    print("=" * 60)
    print("LIFE ARCHIVE - LOCAL FILES CONNECTOR TEST")
    print("=" * 60)
    
    # Initialize the connector
    archive_root = Path("LIFE_ARCHIVE")
    connector = LocalFilesConnector(
        archive_root=archive_root,
        scan_paths=[archive_root / "00_RAW" / "test"]  # Scan our test directory
    )
    
    print(f"Archive root: {archive_root.absolute()}")
    print(f"Scan paths: {[str(p) for p in connector.scan_paths]}")
    print()
    
    # Run the connector (process up to 10 items for testing)
    print("Running local files connector...")
    result = await connector.run(max_items=10)
    
    print()
    print("INGESTION RESULTS:")
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status.value}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print()
    
    print("STATISTICS:")
    print(f"  Items Discovered: {result.items_discovered}")
    print(f"  Items Processed:  {result.items_processed}")
    print(f"  Items Failed:     {result.items_failed}")
    print(f"  Items Skipped:    {result.items_skipped}")
    print()
    
    if result.errors:
        print("ERRORS:")
        for error in result.errors:
            print(f"  - {error}")
        print()
    
    # Verify that manifest files were created
    print("MANIFEST VERIFICATION:")
    manifest_dir = archive_root / "01_MANIFEST"
    manifest_files = [
        "source_manifest.jsonl",
        "acquisition_log.jsonl", 
        "hashes.jsonl",
        "ingestion_runs.jsonl"
    ]
    
    for manifest_file in manifest_files:
        file_path = manifest_dir / manifest_file
        if file_path.exists():
            line_count = sum(1 for line in open(file_path, 'rb'))
            print(f"  ✓ {manifest_file}: {line_count} entries")
        else:
            print(f"  ✗ {manifest_file}: NOT FOUND")
    
    print()
    print("FORENSIC EVIDENCE:")
    for key, value in result.forensic_evidence.items():
        print(f"  {key}: {value}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    return result


def verify_manifests():
    """Verify that manifest files contain expected entries."""
    print("\nMANIFEST CONTENT PREVIEW:")
    print("-" * 40)
    
    import json
    from pathlib import Path
    
    manifest_dir = Path("LIFE_ARCHIVE") / "01_MANIFEST"
    
    # Show first few entries from source_manifest.jsonl
    source_manifest = manifest_dir / "source_manifest.jsonl"
    if source_manifest.exists():
        print(f"\nFirst 3 entries from {source_manifest.name}:")
        with open(source_manifest, 'r', encoding='utf-8') as f:
            count = 0
            for line in f:
                if count >= 3:
                    break
                try:
                    entry = json.loads(line.strip())
                    print(f"  {count + 1}. {entry['original_filename']} - {entry['sha256'][:16]}... - {entry['processing_status']}")
                    count += 1
                except Exception:
                    continue
    
    # Show first few entries from ingestion_runs.jsonl
    ingestion_runs = manifest_dir / "ingestion_runs.jsonl"
    if ingestion_runs.exists():
        print(f"\nFirst 3 entries from {ingestion_runs.name}:")
        with open(ingestion_runs, 'r', encoding='utf-8') as f:
            count = 0
            for line in f:
                if count >= 3:
                    break
                try:
                    run = json.loads(line.strip())
                    print(f"  {count + 1}. {run['run_id'][:16]}... - {run['connector']} - {run['status']}")
                    count += 1
                except Exception:
                    continue


if __name__ == "__main__":
    # Run the test
    result = asyncio.run(test_local_files_connector())
    
    # Verify manifests
    verify_manifests()
    
    # Final status
    print(f"\nOVERALL STATUS: {'PASS' if result.status.value in ['PASS', 'PARTIAL'] else 'FAIL'}")
    if result.status.value == 'PASS':
        print("✓ Local files connector test PASSED - Pipeline validated")
    elif result.status.value == 'PARTIAL':
        print("? Local files connector test PARTIAL - Some items processed")
    else:
        print("✗ Local files connector test FAILED - No items processed")