"""Publishing utilities for curating archive documents into book-length PDFs."""

from .compile_lifedocs_books import (
    BOOK_SPECS,
    COMMERCIAL_BOOK_SPECS,
    DUPLICATE_SOURCE_PDFS,
    RELEASE_BOOK_SPECS,
    compile_books,
    compile_commercial_books,
    compile_release_books,
)
from .generate_linkedin_playbook import main as generate_linkedin_playbook

__all__ = [
    "BOOK_SPECS",
    "COMMERCIAL_BOOK_SPECS",
    "DUPLICATE_SOURCE_PDFS",
    "RELEASE_BOOK_SPECS",
    "compile_books",
    "compile_commercial_books",
    "compile_release_books",
    "generate_linkedin_playbook",
]
