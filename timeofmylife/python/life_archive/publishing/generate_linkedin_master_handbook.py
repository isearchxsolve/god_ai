from __future__ import annotations

from pathlib import Path

import fitz

SOURCE_PDFS = (
    Path("PUBLISHING_DELIVERABLES/PUBLISHING_DELIVERABLES_INDEX.pdf"),
    Path("PUBLISHING_DELIVERABLES/books/commercial/linkedin/LinkedIn_Monetization_Complete_Tutorial.pdf"),
    Path("PUBLISHING_DELIVERABLES/LINKEDIN_POSTS_AND_DM_SCRIPTS.pdf"),
    Path("PUBLISHING_DELIVERABLES/LINKEDIN_LAUNCH_CHECKLIST.pdf"),
)
OUTPUT_PDF = Path("PUBLISHING_DELIVERABLES/LINKEDIN_MONETIZATION_MASTER_HANDBOOK.pdf")
TITLE = "LinkedIn Monetization Master Handbook"
SUBTITLE = "Index, tutorial, scripts, and checklist in one PDF"

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 56


def _draw_cover(doc: fitz.Document) -> None:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    accent = (0.17, 0.17, 0.17)
    page.draw_rect(fitz.Rect(36, 36, PAGE_WIDTH - 36, PAGE_HEIGHT - 36), color=accent, width=1.2)
    page.draw_rect(fitz.Rect(48, 48, PAGE_WIDTH - 48, 78), color=accent, fill=accent)
    page.draw_rect(
        fitz.Rect(48, PAGE_HEIGHT - 78, PAGE_WIDTH - 48, PAGE_HEIGHT - 48),
        color=accent,
        fill=accent,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN, 56, PAGE_WIDTH - MARGIN, 74),
        "LifeDocs Press",
        fontname="Helvetica",
        fontsize=11,
        color=(1, 1, 1),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 10, 170, PAGE_WIDTH - MARGIN - 10, 300),
        TITLE,
        fontname="Helvetica-Bold",
        fontsize=28,
        color=(0.08, 0.08, 0.08),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 20, 300, PAGE_WIDTH - MARGIN - 20, 350),
        SUBTITLE,
        fontname="Times-Italic",
        fontsize=16,
        color=(0.22, 0.22, 0.22),
        align=1,
    )
    page.draw_line(
        fitz.Point(MARGIN + 50, 390),
        fitz.Point(PAGE_WIDTH - MARGIN - 50, 390),
        color=accent,
        width=1.0,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 10, 430, PAGE_WIDTH - MARGIN - 10, 570),
        "This handbook combines the deliverables index, the complete LinkedIn monetization tutorial, the copy-paste posts and DM scripts, and the launch checklist into one operating manual.",
        fontname="Times-Roman",
        fontsize=13,
        color=(0.1, 0.1, 0.1),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN, PAGE_HEIGHT - 70, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 54),
        "Open this file if you want the entire LinkedIn system in one place.",
        fontname="Helvetica",
        fontsize=10,
        color=(1, 1, 1),
        align=1,
    )


def _draw_page_number(page: fitz.Page, page_number: int) -> None:
    page.insert_text(
        fitz.Point(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 24),
        str(page_number),
        fontname="Helvetica",
        fontsize=10,
        color=(0.35, 0.35, 0.35),
    )


def main() -> None:
    doc = fitz.open()
    toc: list[list[int | str]] = []

    _draw_cover(doc)
    toc.append([1, TITLE, 1])

    page_cursor = 2
    for source in SOURCE_PDFS:
        source_doc = fitz.open(source)
        try:
            toc.append([1, source.stem.replace("_", " "), page_cursor])
            doc.insert_pdf(source_doc)
            page_cursor += source_doc.page_count
        finally:
            source_doc.close()

    for page_number, page in enumerate(doc, start=1):
        if page_number > 1:
            _draw_page_number(page, page_number)

    doc.set_toc(toc)
    doc.set_metadata(
        {
            "title": TITLE,
            "author": "LifeDocs Press",
            "subject": SUBTITLE,
            "creator": "life_archive.publishing.generate_linkedin_master_handbook",
            "producer": "PyMuPDF",
        }
    )
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT_PDF, garbage=4, deflate=True)
    doc.close()
    print(OUTPUT_PDF)


if __name__ == "__main__":
    main()
