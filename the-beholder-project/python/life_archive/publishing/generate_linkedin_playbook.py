from __future__ import annotations

from pathlib import Path
import sys

import fitz

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 56
LINE_HEIGHT = 16
TEXT_WIDTH = PAGE_WIDTH - (MARGIN * 2)


def _new_page(doc: fitz.Document) -> fitz.Page:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.draw_rect(
        fitz.Rect(36, 36, PAGE_WIDTH - 36, PAGE_HEIGHT - 36),
        color=(0.18, 0.18, 0.18),
        width=1,
    )
    page.draw_rect(
        fitz.Rect(48, 48, PAGE_WIDTH - 48, 78),
        color=(0.18, 0.18, 0.18),
        fill=(0.18, 0.18, 0.18),
    )
    page.insert_textbox(
        fitz.Rect(MARGIN, 56, PAGE_WIDTH - MARGIN, 74),
        "LifeDocs Press",
        fontname="Helvetica",
        fontsize=11,
        color=(1, 1, 1),
        align=1,
    )
    return page


def _draw_page_number(page: fitz.Page, page_number: int) -> None:
    page.insert_text(
        fitz.Point(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 24),
        str(page_number),
        fontname="Helvetica",
        fontsize=10,
        color=(0.35, 0.35, 0.35),
    )


def _render_markdown(
    markdown_path: Path,
    output_path: Path,
    title: str,
    subject: str,
) -> None:
    lines = markdown_path.read_text(encoding="utf-8").splitlines()
    doc = fitz.open()

    page = _new_page(doc)
    y = 110.0

    def ensure_space(height: float) -> tuple[fitz.Page, float]:
        nonlocal page, y
        if y + height > PAGE_HEIGHT - 70:
            page = _new_page(doc)
            y = 96.0
        return page, y

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            y += 8
            continue

        if line.startswith("# "):
            page, y = ensure_space(56)
            page.insert_textbox(
                fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 40),
                line[2:],
                fontname="Helvetica-Bold",
                fontsize=24,
                color=(0.12, 0.12, 0.12),
            )
            y += 36
            continue

        if line.startswith("## "):
            page, y = ensure_space(38)
            page.insert_textbox(
                fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 28),
                line[3:],
                fontname="Helvetica-Bold",
                fontsize=16,
                color=(0.18, 0.18, 0.18),
            )
            y += 24
            continue

        if line.startswith("### "):
            page, y = ensure_space(32)
            page.insert_textbox(
                fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 24),
                line[4:],
                fontname="Helvetica-Bold",
                fontsize=13,
                color=(0.22, 0.22, 0.22),
            )
            y += 20
            continue

        text = line
        if text.startswith("- ") or text.startswith("1. ") or text.startswith("2. ") or text.startswith("3. ") or text.startswith("4. ") or text.startswith("5. ") or text.startswith("6. ") or text.startswith("7. ") or text.startswith("8. ") or text.startswith("9. "):
            pass

        page, y = ensure_space(48)
        rect = fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 48)
        used = page.insert_textbox(
            rect,
            text,
            fontname="Times-Roman",
            fontsize=11.5,
            color=(0.08, 0.08, 0.08),
            lineheight=1.22,
            align=0,
        )
        if used < 0:
            page = _new_page(doc)
            y = 96.0
            rect = fitz.Rect(MARGIN, y, PAGE_WIDTH - MARGIN, y + 80)
            page.insert_textbox(
                rect,
                text,
                fontname="Times-Roman",
                fontsize=11.5,
                color=(0.08, 0.08, 0.08),
                lineheight=1.22,
                align=0,
            )
            y += 40
        else:
            y += 18 + max(0, used)

    for page_number, current_page in enumerate(doc, start=1):
        _draw_page_number(current_page, page_number)

    doc.set_metadata(
        {
            "title": title,
            "author": "LifeDocs Press",
            "subject": subject,
            "creator": "life_archive.publishing.generate_linkedin_playbook",
            "producer": "PyMuPDF",
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()


def main() -> None:
    args = sys.argv[1:]

    if args:
        if len(args) not in {2, 4}:
            raise SystemExit(
                "Usage: generate_linkedin_playbook.py <input_md> <output_pdf> [<title> <subject>]"
            )
        markdown_path = Path(args[0])
        output_path = Path(args[1])
        title = args[2] if len(args) == 4 else output_path.stem.replace("_", " ")
        subject = args[3] if len(args) == 4 else "Generated PDF from Markdown"
    else:
        markdown_path = Path("PUBLISHING_DELIVERABLES/books/commercial/linkedin/LINKEDIN_MONETIZATION_PLAYBOOK.md")
        output_path = Path("PUBLISHING_DELIVERABLES/books/commercial/linkedin/LinkedIn_Monetization_Playbook.pdf")
        title = "LinkedIn Monetization Playbook"
        subject = "LinkedIn monetization strategy and sales assets"

    _render_markdown(markdown_path, output_path, title, subject)
    print(output_path)


if __name__ == "__main__":
    main()
