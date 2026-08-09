from pathlib import Path
import zipfile

from life_archive.publishing.compile_lifedocs_books import (
    BOOK_SPECS,
    COMMERCIAL_BOOK_SPECS,
    DUPLICATE_SOURCE_PDFS,
    RELEASE_BOOK_SPECS,
)


def test_all_non_duplicate_pdfs_are_assigned_once() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    zip_path = repo_root / "lifedocs.zip"

    with zipfile.ZipFile(zip_path) as archive:
        actual = {
            Path(name).name
            for name in archive.namelist()
            if name.lower().endswith(".pdf")
        }

    assigned = [section.source_pdf for book in BOOK_SPECS for section in book.sections]

    assert len(assigned) == len(set(assigned))
    assert actual == set(assigned) | DUPLICATE_SOURCE_PDFS


def test_book_output_names_are_pdfs() -> None:
    assert all(book.filename.endswith(".pdf") for book in BOOK_SPECS)
    assert all(book.filename.endswith(".pdf") for book in RELEASE_BOOK_SPECS)
    assert all(book.filename.endswith(".pdf") for book in COMMERCIAL_BOOK_SPECS)


def test_release_books_cover_same_sources() -> None:
    assigned = {section.source_pdf for book in BOOK_SPECS for section in book.sections}
    release_assigned = {section.source_pdf for book in RELEASE_BOOK_SPECS for section in book.sections}

    assert assigned == release_assigned


def test_commercial_books_cover_same_sources() -> None:
    assigned = {section.source_pdf for book in BOOK_SPECS for section in book.sections}
    commercial_assigned = {
        section.source_pdf for book in COMMERCIAL_BOOK_SPECS for section in book.sections
    }

    assert assigned == commercial_assigned
