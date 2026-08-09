"""Lexical search index for Life Archive (Meilisearch).

Prototype wiring for the index stage of the pipeline. Designed to be
optional: if the Meilisearch server is unreachable or not configured,
every operation degrades gracefully and the ingestion pipeline is
unaffected.

Configuration (environment variables, or a .env at the repo root):
- MEILI_URL: Meilisearch URL (default http://localhost:7700)
- MEILI_MASTER_KEY: master key (unset = dev server without auth)
"""

import os

from dotenv import load_dotenv

from life_archive.schemas.provenance import ManifestEntry

load_dotenv()

INDEX_UID = "archive_objects"

DEFAULT_URL = "http://localhost:7700"


def _doc_id(archive_id: str) -> str:
    """Meilisearch document IDs allow only [a-zA-Z0-9_-]; archive IDs
    contain a colon (e.g. sha256:...). Sanitize for use as the primary
    key; the original archive_id stays in the document body."""
    return archive_id.replace(":", "_")


class SearchIndex:
    """Thin wrapper around Meilisearch for manifest-object documents."""

    def __init__(self, url: str | None = None, master_key: str | None = None):
        self.url = url or os.environ.get("MEILI_URL", DEFAULT_URL)
        self.master_key = master_key or os.environ.get("MEILI_MASTER_KEY") or None
        self._client = None

    def _get_client(self):
        if self._client is None:
            import meilisearch

            self._client = meilisearch.Client(self.url, self.master_key)
        return self._client

    def available(self) -> bool:
        """True if the Meilisearch server responds."""
        try:
            return bool(self._get_client().health())
        except Exception:
            return False

    def ensure_index(self) -> bool:
        """Create the index and settings if missing. Returns success."""
        try:
            client = self._get_client()
            try:
                client.create_index(INDEX_UID, {"primaryKey": "doc_id"})
            except Exception:
                pass  # already exists
            client.index(INDEX_UID).update_searchable_attributes(
                ["original_filename", "mime_type", "source", "archive_path"]
            )
            return True
        except Exception:
            return False

    def index_entry(self, entry: ManifestEntry, archive_path: str) -> bool:
        """Index one manifest entry. Returns True on success."""
        try:
            doc = {
                "doc_id": _doc_id(entry.archive_id),
                "archive_id": entry.archive_id,
                "original_filename": entry.original_filename,
                "mime_type": entry.mime_type,
                "source": entry.source,
                "size_bytes": entry.size_bytes,
                "original_timestamp": entry.original_timestamp.isoformat(),
                "archive_path": archive_path,
            }
            self._get_client().index(INDEX_UID).add_documents([doc])
            return True
        except Exception:
            return False

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search indexed objects. Returns [] when unavailable."""
        try:
            result = self._get_client().index(INDEX_UID).search(
                query, {"limit": limit}
            )
            return result.get("hits", [])
        except Exception:
            return []
