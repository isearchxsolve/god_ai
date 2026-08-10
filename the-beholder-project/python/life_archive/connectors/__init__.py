"""Connectors package for Life Archive.

Connectors ingest data from external sources through the standard pipeline:
discover -> acquire -> verify -> hash -> store -> index -> normalize -> log.
"""

from life_archive.connectors.git import GitConnector
from life_archive.connectors.github import GitHubConnector
from life_archive.connectors.google_takeout import GoogleTakeoutConnector
from life_archive.connectors.linkedin import LinkedInConnector
from life_archive.connectors.local_files import LocalFilesConnector
from life_archive.connectors.whatsapp import WhatsAppConnector

__all__ = [
    "LocalFilesConnector",
    "GitConnector",
    "GitHubConnector",
    "GoogleTakeoutConnector",
    "WhatsAppConnector",
    "LinkedInConnector",
]
