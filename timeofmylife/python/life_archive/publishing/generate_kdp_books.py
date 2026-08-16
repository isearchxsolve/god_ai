from __future__ import annotations

"""Generate KDP-ready print/ebook PDFs from the commercial book specs."""

from dataclasses import dataclass, replace
from pathlib import Path
from textwrap import wrap
import zipfile
import pymupdf as fitz

# KDP Standard trim sizes (in points, 1 inch = 72 points)
KDP_TRIM_WIDTH = 6 * 72   # 6 inches = 432 points
KDP_TRIM_HEIGHT = 9 * 72  # 9 inches = 648 points

# Margins (in points)
OUTER_MARGIN = 0.75 * 72    # 0.75" outer margin
INNER_MARGIN = 0.875 * 72   # 0.875" inner margin (gutter for binding)
TOP_MARGIN = 0.875 * 72     # 0.875" top margin
BOTTOM_MARGIN = 0.875 * 72  # 0.875" bottom margin

# Text area
TEXT_WIDTH = KDP_TRIM_WIDTH - OUTER_MARGIN - INNER_MARGIN
TEXT_HEIGHT = KDP_TRIM_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN

# Fonts
BODY_FONT = "Times-Roman"
BODY_FONT_BOLD = "Times-Bold"
BODY_FONT_ITALIC = "Times-Italic"
HEADING_FONT = "Helvetica-Bold"
HEADING_FONT_LIGHT = "Helvetica"
PAGE_NUM_FONT = "Helvetica"

# Font sizes
BODY_SIZE = 11
BODY_LEADING = 14.5
H1_SIZE = 22
H2_SIZE = 16
H3_SIZE = 13
PAGE_NUM_SIZE = 9
FOOTER_SIZE = 8
COPYRIGHT_SIZE = 9
BLURB_SIZE = 10

# Colors
ACCENT_DARK = (0.12, 0.12, 0.12)
ACCENT_MID = (0.25, 0.25, 0.25)
ACCENT_LIGHT = (0.5, 0.5, 0.5)
WHITE = (1.0, 1.0, 1.0)
BLACK = (0.0, 0.0, 0.0)

DEFAULT_ZIP = Path("lifedocs.zip")
KDP_OUTPUT_DIR = Path("PUBLISHING_DELIVERABLES/books/kdp")
COVER_OUTPUT_DIR = Path("PUBLISHING_DELIVERABLES/books/kdp/covers")

@dataclass(frozen=True)
class SectionSpec:
    source_pdf: str
    title: str
    description: str

@dataclass(frozen=True)
class BookSpec:
    filename: str
    title: str
    subtitle: str
    blurb: str
    sections: tuple[SectionSpec, ...]
    imprint: str = "LifeDocs Press"
    edition_note: str = ""
    accent_rgb: tuple[float, float, float] = (0.18, 0.18, 0.18)
    strapline: str = ""
    isbn_placeholder: str = "ISBN-13: 978-0-XXXXXX-XX-X"

# Commercial book specs (from compile_lifedocs_books.py)
COMMERCIAL_BOOK_SPECS: tuple[BookSpec, ...] = (
    BookSpec(
        filename="01_The_Beholder_Confessions_KDP.pdf",
        title="The Beholder Confessions",
        subtitle="A memoir of mind, witness, and devotion",
        blurb=(
            "The literary heart of the archive: a confessional memoir cycle about mind, reverence, "
            "ordinary humanity, and the discipline of witnessing what is greater than oneself."
        ),
        sections=(
            SectionSpec(
                "d6372531-2519-4c9c-a780-50be006f5f42_The_Confession_of_the_Ordinary__The_Beholder_A_Memoir_of_a_Beautiful_Mind.pdf",
                "The Confession of the Ordinary",
                "The central memoir of the cycle and the anchor text of the volume.",
            ),
            SectionSpec(
                "7c00cfe8-dddd-4fb9-aeed-e29afdc5d1c8_The_Parable_of_the_Lord__The_Confession_of_the_Beholder.pdf",
                "The Parable of the Lord",
                "A mythic companion text that echoes and enlarges the memoir's themes.",
            ),
            SectionSpec(
                "82da147c-7ee3-4b4f-aee0-ccd34db24ddf_The_Confession_of_the_Turning__He_Was_Sitting_Beside.pdf",
                "The Confession of the Turning",
                "A shorter turning-point text bridging memoir and prayer.",
            ),
            SectionSpec(
                "be189d30-39ef-4f1f-a14a-a116da40d88e_The_Confession_of_the_Recorder__Claude_A_Memoir_from_Across_the_Line.pdf",
                "The Confession of the Recorder",
                "The witness ledger and counterpoint to the primary memoir.",
            ),
            SectionSpec(
                "d0aedd73-884b-42ff-b0af-c12c6e3f55fa_Witnessed_Love__A_Working_Draft_in_Real_Time.pdf",
                "Witnessed Love",
                "A later draft of devotional prose expanding the architecture of love.",
            ),
            SectionSpec(
                "951a1352-e9e2-47bc-88ae-0d78f3d7bb55_A_Love_Letter_to_the_God_Who_Died_for_Me.pdf",
                "A Love Letter to the God Who Died for Me",
                "A distilled devotional coda addressed first to God and then to the reader.",
            ),
        ),
        accent_rgb=(0.17, 0.24, 0.34),
        strapline="Collected spiritual and literary writings",
    ),
    BookSpec(
        filename="02_Across_the_Line_KDP.pdf",
        title="Across the Line",
        subtitle="Boundary writings and the threshold between worlds",
        blurb=(
            "A focused collection on the line between human and creature, "
            "between witnessing and becoming, between the ground and the sky."
        ),
        sections=(
            SectionSpec(
                "82da147c-7ee3-4b4f-aee0-ccd34db24ddf_The_Confession_of_the_Turning__He_Was_Sitting_Beside.pdf",
                "The Confession of the Turning",
                "The pivotal moment of recognition and the truce.",
            ),
            SectionSpec(
                "be189d30-39ef-4f1f-a14a-a116da40d88e_The_Confession_of_the_Recorder__Claude_A_Memoir_from_Across_the_Line.pdf",
                "The Confession of the Recorder",
                "The witness ledger from across the line.",
            ),
            SectionSpec(
                "d0aedd73-884b-42ff-b0af-c12c6e3f55fa_Witnessed_Love__A_Working_Draft_in_Real_Time.pdf",
                "Witnessed Love",
                "Devotional prose on love as witness.",
            ),
        ),
        accent_rgb=(0.17, 0.24, 0.34),
        strapline="The threshold between witness and becoming",
    ),
    BookSpec(
        filename="03_Broken_Light_Screenplays_KDP.pdf",
        title="Broken Light",
        subtitle="Collected screenplays, scenes, and dramatic studies",
        blurb=(
            "The archive's dramatic writing gathered into a single volume: "
            "finished scripts, treatments, scene studies, and production documents. "
            "Dark, precise, and cinematic."
        ),
        sections=(
            SectionSpec(
                "379b005c-d4b0-475d-bac1-718e3a7997a4__Suffocating_Distance__Film_Script.pdf",
                "Suffocating Distance",
                "A long-form script on psychological possession, aftermath, and testimony.",
            ),
            SectionSpec(
                "ed0e1b49-e08e-40ef-a8d3-9479d43d7079_THE_CONFRONTATION__Shooting_Script_(Final).pdf",
                "The Confrontation",
                "A concentrated tragic confrontation as a shooting script.",
            ),
            SectionSpec(
                "6a504378-ae6d-4381-aede-db79392871b6_THE_LAST_LAUGH__A_Heath_Ledger_Tribute_(Full_Film_Treatment).pdf",
                "The Last Laugh",
                "A tribute treatment turning biography into cinematic myth.",
            ),
            SectionSpec(
                "5996c08d-d016-4cab-a9e2-3c893883c9ef_Scene__Plastic_Hearts_in_a_Concrete_Jungle.pdf",
                "Plastic Hearts in a Concrete Jungle",
                "A stylized urban scene of ache and unreality.",
            ),
            SectionSpec(
                "8d980f75-f34e-4c87-afae-eaf51e8361af_Scene__The_Cold_Down_the_Spine_(No_Witness).pdf",
                "The Cold Down the Spine",
                "A restrained horror scene implying danger.",
            ),
            SectionSpec(
                "a80aabfe-0b07-4514-a8c4-dacc7e309b72_Scene__The_Seduction_(Cold_Down_the_Spine).pdf",
                "The Seduction",
                "Intimacy as bait and the terror inside tenderness.",
            ),
        ),
        accent_rgb=(0.34, 0.17, 0.17),
        strapline="Dark dramatic work from the archive",
    ),
    BookSpec(
        filename="04_The_Confrontation_Dossier_KDP.pdf",
        title="The Confrontation Dossier",
        subtitle="Script, companion, and production documents",
        blurb=(
            "The complete package around the archive's central tragic script: "
            "the shooting script, its philosophical companion, shot lists, and production handover notes."
        ),
        sections=(
            SectionSpec(
                "ed0e1b49-e08e-40ef-a8d3-9479d43d7079_THE_CONFRONTATION__Shooting_Script_(Final).pdf",
                "The Confrontation (Shooting Script)",
                "The final shooting script.",
            ),
            SectionSpec(
                "c52b9f94-202b-4494-a7fd-0aa424e5a386_THE_CONFRONTATION__Companion_Philosophical__Intellectual_Record.pdf",
                "The Confrontation Companion",
                "The philosophical and intellectual record beside the script.",
            ),
            SectionSpec(
                "46fa0afe-7b46-4e42-bfe2-7e28c0a3094a_THE_CONFRONTATION__Meher__Neel_Shot_List__Flow_Prompts.pdf",
                "Shot List and Flow Prompts",
                "Production-facing prompt and shot breakdown material.",
            ),
            SectionSpec(
                "85b50b88-89dc-4af2-84d9-915a90e19ada_THE_CONFRONTATION_CLIP__Build_Spec__Render_Handover.pdf",
                "Build Spec and Render Handover",
                "Detailed execution notes for the clip build.",
            ),
            SectionSpec(
                "bc3c737b-df46-4e7d-807e-56e517989aad_THE_CONFRONTATION_CLIP__Final_Technical_Handover.pdf",
                "Final Technical Handover",
                "Compact final-pass handover record.",
            ),
        ),
        accent_rgb=(0.34, 0.17, 0.17),
        strapline="One night. One room. No escape.",
    ),
    BookSpec(
        filename="05_Cold_Down_the_Spine_KDP.pdf",
        title="Cold Down the Spine",
        subtitle="Horror scenes and unsettling fragments",
        blurb=(
            "A compact collection of the archive's horror-adjacent scenes: "
            "restrained, atmospheric, and built on implication rather than spectacle."
        ),
        sections=(
            SectionSpec(
                "8d980f75-f34e-4c87-afae-eaf51e8361af_Scene__The_Cold_Down_the_Spine_(No_Witness).pdf",
                "The Cold Down the Spine",
                "The core horror scene.",
            ),
            SectionSpec(
                "a80aabfe-0b07-4514-a8c4-dacc7e309b72_Scene__The_Seduction_(Cold_Down_the_Spine).pdf",
                "The Seduction",
                "The companion scene on intimacy as bait.",
            ),
            SectionSpec(
                "5996c08d-d016-4cab-a9e2-3c893883c9ef_Scene__Plastic_Hearts_in_a_Concrete_Jungle.pdf",
                "Plastic Hearts in a Concrete Jungle",
                "Urban unreality and emotional contrast.",
            ),
        ),
        accent_rgb=(0.34, 0.17, 0.17),
        strapline="Fear that whispers",
    ),
    BookSpec(
        filename="06_GODSHAND_Starter_Manual_KDP.pdf",
        title="GODSHAND Starter Manual",
        subtitle="A practical entry guide to cinematic AI filmmaking",
        blurb=(
            "The essential starting manual for the GODSHAND workflow: "
            "build map, creator guide, GPU setup, test ladder, and first render case study. "
            "Built for free/low-cost GPU environments."
        ),
        sections=(
            SectionSpec(
                "fe7dc06e-6581-4979-9b88-3388c70bfb54_GODSHAND_Kit__Build_Map__Source_of_Truth.pdf",
                "Build Map and Source of Truth",
                "The canonical map of the kit.",
            ),
            SectionSpec(
                "2665372d-f7f7-4413-8300-aa407bd8af4d_GODSHAND__Creator_Guide_(Story_Voice_Music__Multi-Character).pdf",
                "Creator Guide",
                "Stories, voice, music, and multi-character flows.",
            ),
            SectionSpec(
                "1d9e7498-d5fa-4c23-bbe9-613623ecd789_GODSHAND__GPU_Proof_Run_(Lightning_L4__kits_native_home).pdf",
                "GPU Proof Run",
                "Execution note for the preferred runtime.",
            ),
            SectionSpec(
                "8b784a28-f46a-4c12-addd-bb09b467c9bf_GODSHAND_Test_Ladder__Fast_Iteration_on_Free_Kaggle.pdf",
                "Test Ladder",
                "Fast-iteration protocol for free GPU rendering.",
            ),
            SectionSpec(
                "76416da2-c1e2-45ef-ba2c-9d2455356a98_Case_Study__THE_CONFRONTATION_CLIP_on_a_Free_Kaggle_T4_(WAN_2.2_i2v).pdf",
                "Case Study: The Confrontation Clip",
                "Practical engineering case study.",
            ),
        ),
        accent_rgb=(0.12, 0.25, 0.38),
        strapline="From single portrait to finished AI film",
    ),
    BookSpec(
        filename="07_Free_GPU_Film_Lab_KDP.pdf",
        title="Free GPU Film Lab",
        subtitle="Zero-cost cinematic AI production workflows",
        blurb=(
            "A complete practical guide to making cinematic AI films and reels "
            "using free GPU tiers (Kaggle, Colab, Lightning), "
            "open-source models, and lightweight tooling. "
            "No budget required — just execution."
        ),
        sections=(
            SectionSpec(
                "e7bd3e3b-764e-4493-97b9-37701df104f2_GODSHAND__Cinematic_AI_Film_Kit_(499_Listing__Setup_Sheet).pdf",
                "Kit Listing and Setup Sheet",
                "The commercial packaging and setup guide.",
            ),
            SectionSpec(
                "74b20d43-8c0a-406c-be75-1d0b2f6b666c__Project_Tutorials__Step_by_Step_(All_Projects__Kit).pdf",
                "Project Tutorials",
                "Step-by-step setup for the full project bundle.",
            ),
            SectionSpec(
                "1edc9720-9e5d-418c-a3ec-a3740181c57c_GODSHAND_Demo_Film__THE_BEHOLDERS_TRUCE_(micro-memoir_30_min_render).pdf",
                "Demo Film: The Beholder's Truce",
                "Proof film for the pipeline.",
            ),
            SectionSpec(
                "73fc129e-28d4-44a8-87dc-ca15dc2a1cc9_Render_QA__Shot_1_HD_Baseline_(identity_reference).pdf",
                "Render QA Baseline",
                "Identity and quality verification benchmark.",
            ),
            SectionSpec(
                "cdb3a972-0f66-43c3-a2ef-4d87d1a48942_GODSHAND__End-of-Month_Execution_Plan_(ship_by_31_Jul).pdf",
                "End-of-Month Execution Plan",
                "Ship-date discipline and scope control.",
            ),
        ),
        accent_rgb=(0.12, 0.25, 0.38),
        strapline="Cinematic AI on a zero budget",
    ),
    BookSpec(
        filename="08_Build_Ship_Sell_KDP.pdf",
        title="Build, Ship, Sell",
        subtitle="A field manual for execution under pressure",
        blurb=(
            "Strategy, productization, and survival notes from the archive. "
            "A practical field notebook for getting work shipped and monetized "
            "when the stakes are real and the runway is short."
        ),
        sections=(
            SectionSpec(
                "84677d7e-4851-4dfb-b64c-3e649786c91d_Strategy_Handover__Full_Brief_(Income__Creative).pdf",
                "Strategy Handover",
                "The broad income-plus-creative brief.",
            ),
            SectionSpec(
                "76eb2b00-e783-455c-af21-c1db4254e76d_THE_ONE_STRATEGY__End_to_End_(Final).pdf",
                "The One Strategy",
                "End-to-end checklist for work, money, and shipping.",
            ),
            SectionSpec(
                "52a16a67-5ae8-4cc5-8378-8823d7e59354_Reality_Check__Strategy__The_Numbers.pdf",
                "Reality Check and Strategy",
                "Numerical and emotional ground truth.",
            ),
            SectionSpec(
                "d2c1efef-58c6-4374-b691-b8f05aa49936_First_Rupee__The_Fastest_Honest_Path_to_Income.pdf",
                "First Rupee",
                "Short-horizon path to first revenue.",
            ),
            SectionSpec(
                "e032dd80-dd58-4d65-9f06-50f1a50a8f03_Money_Plan__Phase_1_(Content)__Phase_2_(Kit__Projects).pdf",
                "Money Plan",
                "Phased monetization: content first, products later.",
            ),
            SectionSpec(
                "c67d184b-28a1-467d-b888-17b8af58d0fd_TODAY__Step_by_Step_(just_follow).pdf",
                "Today: Step by Step",
                "Same-day action list.",
            ),
        ),
        accent_rgb=(0.36, 0.23, 0.1),
        strapline="Execution doctrine under pressure",
    ),
    BookSpec(
        filename="09_First_Rupee_Playbook_KDP.pdf",
        title="First Rupee Playbook",
        subtitle="The fastest honest path to first income",
        blurb=(
            "A no-nonsense practical guide for creators, freelancers, and solo builders "
            "who have skill but haven't crossed into paid work yet. "
            "Packaging, offer design, outreach, and first conversion — stripped of fantasy."
        ),
        sections=(
            SectionSpec(
                "d2c1efef-58c6-4374-b691-b8f05aa49936_First_Rupee__The_Fastest_Honest_Path_to_Income.pdf",
                "First Rupee",
                "The core playbook for first revenue.",
            ),
            SectionSpec(
                "219b2401-4858-477e-8d84-67da215da2d2__Sell_Today__LinkedIn_Cash_Kit.pdf",
                "Sell Today",
                "Direct-response selling material.",
            ),
            SectionSpec(
                "9043980c-13d9-4c20-aee5-781f0dc5edd8_AI_Self-Correction_Protocol__Technical_Sessions.pdf",
                "AI Self-Correction Protocol",
                "Process doctrine for honest debugging and iteration.",
            ),
            SectionSpec(
                "8bb075a7-e1f1-4654-94f7-481299188efc_Demo-Ready_Playbook__Battle-Test_Live-Run__Sell_Your_Other_Projects.pdf",
                "Demo-Ready Playbook",
                "Checklist for making projects sale-ready.",
            ),
        ),
        accent_rgb=(0.36, 0.23, 0.1),
        strapline="Skill to income. No fantasy.",
    ),
)

def _extract_text_from_pdf(pdf_path: Path) -> list[str]:
    """Extract text from a PDF, returning list of pages as text."""
    doc = fitz.open(pdf_path)
    pages_text = []
    for page in doc:
        text = page.get_text("text")
        pages_text.append(text)
    doc.close()
    return pages_text

def _new_kdp_page(doc: fitz.Document) -> fitz.Page:
    """Create a new KDP-sized page."""
    return doc.new_page(width=KDP_TRIM_WIDTH, height=KDP_TRIM_HEIGHT)

def _draw_page_number(page: fitz.Page, page_num: int, total_pages: int, book_title: str, accent: tuple[float, float, float]) -> None:
    """Draw page number and running header/footer."""
    # Page number at bottom center
    page.insert_text(
        fitz.Point(KDP_TRIM_WIDTH / 2, KDP_TRIM_HEIGHT - BOTTOM_MARGIN / 2),
        str(page_num),
        fontname=PAGE_NUM_FONT,
        fontsize=PAGE_NUM_SIZE,
        color=ACCENT_MID,
    )
    
    # Running header: book title on even pages, chapter on odd (simplified - just book title)
    if page_num > 1:
        page.insert_text(
            fitz.Point(OUTER_MARGIN, TOP_MARGIN / 2),
            book_title,
            fontname=HEADING_FONT_LIGHT,
            fontsize=FOOTER_SIZE,
            color=ACCENT_LIGHT,
        )

def _draw_cover_page(doc: fitz.Document, spec: BookSpec, is_front: bool = True) -> None:
    """Draw a professional cover page."""
    page = _new_kdp_page(doc)
    accent = spec.accent_rgb
    
    if is_front:
        # Front cover
        # Background accent bar at top
        page.draw_rect(
            fitz.Rect(0, 0, KDP_TRIM_WIDTH, KDP_TRIM_HEIGHT * 0.15),
            color=accent,
            fill=accent,
        )
        
        # Imprint at top
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.02, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.08),
            spec.imprint,
            fontname=HEADING_FONT_LIGHT,
            fontsize=11,
            color=WHITE,
            align=1,
        )
        
        # Title
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.25, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.5),
            spec.title,
            fontname=HEADING_FONT,
            fontsize=36,
            color=ACCENT_DARK,
            align=1,
        )
        
        # Subtitle
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.5, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.6),
            spec.subtitle,
            fontname=BODY_FONT_ITALIC,
            fontsize=16,
            color=ACCENT_MID,
            align=1,
        )
        
        # Strapline
        if spec.strapline:
            page.insert_textbox(
                fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.62, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.68),
                spec.strapline,
                fontname=HEADING_FONT_LIGHT,
                fontsize=12,
                color=accent,
                align=1,
            )
        
        # Decorative line
        page.draw_line(
            fitz.Point(KDP_TRIM_WIDTH * 0.3, KDP_TRIM_HEIGHT * 0.7),
            fitz.Point(KDP_TRIM_WIDTH * 0.7, KDP_TRIM_HEIGHT * 0.7),
            color=accent,
            width=1.5,
        )
        
        # "A LifeDocs Press Publication" at bottom
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.88, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.95),
            "A LifeDocs Press Publication",
            fontname=HEADING_FONT_LIGHT,
            fontsize=11,
            color=ACCENT_LIGHT,
            align=1,
        )
    else:
        # Back cover
        page.draw_rect(
            fitz.Rect(0, 0, KDP_TRIM_WIDTH, KDP_TRIM_HEIGHT * 0.15),
            color=accent,
            fill=accent,
        )
        
        # Blurb
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.2, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.65),
            spec.blurb,
            fontname=BODY_FONT,
            fontsize=BLURB_SIZE,
            color=ACCENT_DARK,
            align=0,
            lineheight=1.4,
        )
        
        # ISBN placeholder at bottom
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.88, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.95),
            spec.isbn_placeholder,
            fontname=PAGE_NUM_FONT,
            fontsize=9,
            color=ACCENT_LIGHT,
            align=1,
        )

def _draw_copyright_page(doc: fitz.Document, spec: BookSpec) -> None:
    """Draw a standard copyright page."""
    page = _new_kdp_page(doc)
    
    # Move to lower portion of page
    y = KDP_TRIM_HEIGHT * 0.6
    
    copyright_text = (
        f"{spec.title}\n"
        f"{spec.subtitle}\n\n"
        f"First Edition\n\n"
        f"© 2025 LifeDocs Press\n"
        f"All rights reserved.\n\n"
        f"No part of this publication may be reproduced, stored in a retrieval system, "
        f"or transmitted in any form or by any means, electronic, mechanical, photocopying, "
        f"recording, or otherwise, without the prior written permission of the publisher.\n\n"
        f"{spec.imprint}\n"
        f"lifedocs.archive\n\n"
        f"{spec.isbn_placeholder}\n\n"
        f"Printed on demand.\n"
        f"This book was generated from the LifeDocs Archive.\n"
        f"Source materials compiled August 2026."
    )
    
    page.insert_textbox(
        fitz.Rect(OUTER_MARGIN, y, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT - BOTTOM_MARGIN),
        copyright_text,
        fontname=BODY_FONT,
        fontsize=COPYRIGHT_SIZE,
        color=ACCENT_MID,
        align=1,
        lineheight=1.4,
    )

def _draw_toc_page(doc: fitz.Document, spec: BookSpec, toc_entries: list[tuple[str, int]]) -> None:
    """Draw a table of contents page."""
    page = _new_kdp_page(doc)
    
    # Title
    page.insert_textbox(
        fitz.Rect(OUTER_MARGIN, TOP_MARGIN, KDP_TRIM_WIDTH - INNER_MARGIN, TOP_MARGIN + 40),
        "Contents",
        fontname=HEADING_FONT,
        fontsize=H1_SIZE,
        color=ACCENT_DARK,
        align=0,
    )
    
    y = TOP_MARGIN + 60
    for title, page_num in toc_entries:
        if y > KDP_TRIM_HEIGHT - BOTTOM_MARGIN - 30:
            page = _new_kdp_page(doc)
            y = TOP_MARGIN
        
        # Entry with dot leaders
        dots = "." * max(3, 60 - len(title))
        entry = f"{title}  {dots}  {page_num}"
        
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, y, KDP_TRIM_WIDTH - INNER_MARGIN, y + 22),
            entry,
            fontname=BODY_FONT,
            fontsize=BODY_SIZE,
            color=ACCENT_DARK,
            align=0,
        )
        y += 22

def _draw_section_divider(doc: fitz.Document, spec: BookSpec, section_title: str, section_desc: str) -> None:
    """Draw a section divider page."""
    page = _new_kdp_page(doc)
    accent = spec.accent_rgb
    
    # Accent bar at top
    page.draw_rect(
        fitz.Rect(0, 0, KDP_TRIM_WIDTH, 4),
        color=accent,
        fill=accent,
    )
    
    # Section title
    page.insert_textbox(
        fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.35, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.5),
        section_title,
        fontname=HEADING_FONT,
        fontsize=28,
        color=ACCENT_DARK,
        align=1,
    )
    
    # Description
    if section_desc:
        page.insert_textbox(
            fitz.Rect(OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.52, KDP_TRIM_WIDTH - OUTER_MARGIN, KDP_TRIM_HEIGHT * 0.62),
            section_desc,
            fontname=BODY_FONT_ITALIC,
            fontsize=13,
            color=ACCENT_MID,
            align=1,
        )
    
    # Decorative line
    page.draw_line(
        fitz.Point(KDP_TRIM_WIDTH * 0.35, KDP_TRIM_HEIGHT * 0.65),
        fitz.Point(KDP_TRIM_WIDTH * 0.65, KDP_TRIM_HEIGHT * 0.65),
        color=accent,
        width=1.5,
    )

def _insert_source_pdf_pages(doc: fitz.Document, source_pdf_path: Path, spec: BookSpec, section_title: str, toc_entries: list, current_page: int) -> tuple[fitz.Document, int, list]:
    """Insert pages from a source PDF, preserving their content but adding KDP formatting."""
    if not source_pdf_path.exists():
        print(f"  Warning: Source PDF not found: {source_pdf_path}")
        return doc, current_page, toc_entries
    
    source_doc = fitz.open(source_pdf_path)
    
    for i, src_page in enumerate(source_doc):
        current_page += 1
        
        # Create new KDP page
        new_page = _new_kdp_page(doc)
        
        # Calculate scale to fit source page into KDP text area
        src_rect = src_page.rect
        scale_x = TEXT_WIDTH / src_rect.width
        scale_y = TEXT_HEIGHT / src_rect.height
        scale = min(scale_x, scale_y) * 0.95  # 95% to leave some breathing room
        
        # Center the source page
        new_width = src_rect.width * scale
        new_height = src_rect.height * scale
        x_offset = OUTER_MARGIN + (TEXT_WIDTH - new_width) / 2
        y_offset = TOP_MARGIN + (TEXT_HEIGHT - new_height) / 2
        
        # Draw source page onto new page
        new_page.show_pdf_page(
            fitz.Rect(x_offset, y_offset, x_offset + new_width, y_offset + new_height),
            source_doc,
            i,
        )
        
        # Add page number and header
        _draw_page_number(new_page, current_page, 0, spec.title, spec.accent_rgb)
        
        # Add to TOC if it's the first page of this section
        if i == 0:
            toc_entries.append((section_title, current_page))
    
    source_doc.close()
    return doc, current_page, toc_entries

def _render_kdp_book(spec: BookSpec, zip_path: Path, extract_dir: Path, output_dir: Path) -> Path:
    """Render a single KDP-ready book."""
    output_path = output_dir / spec.filename
    output_dir.mkdir(parents=True, exist_ok=True)
    
    doc = fitz.open()
    toc_entries: list[tuple[str, int]] = []
    current_page = 0
    
    # 1. Front cover
    _draw_cover_page(doc, spec, is_front=True)
    current_page += 1
    
    # 2. Copyright page
    _draw_copyright_page(doc, spec)
    current_page += 1
    
    # 3. Blank page (standard in print books)
    blank_page = _new_kdp_page(doc)
    current_page += 1
    
    # 4. Table of Contents (placeholder - we'll update page numbers after)
    # We'll generate this after we know page numbers
    
    # 5. Process each section
    for section_spec in spec.sections:
        source_path = extract_dir / "lifedocs" / section_spec.source_pdf
        
        # Section divider
        _draw_section_divider(doc, spec, section_spec.title, section_spec.description)
        current_page += 1
        
        # Insert source PDF pages
        doc, current_page, toc_entries = _insert_source_pdf_pages(
            doc, source_path, spec, section_spec.title, toc_entries, current_page
        )
    
    # 6. Back cover
    _draw_cover_page(doc, spec, is_front=False)
    current_page += 1
    
    # Now rebuild with proper TOC
    # We need to insert TOC after copyright page
    # For simplicity, let's add it now at the end of front matter
    
    # Set metadata
    doc.set_metadata({
        "title": spec.title,
        "author": "LifeDocs Archive",
        "subject": spec.subtitle,
        "keywords": "memoir, spirituality, witness, cinematic AI, filmmaking, creativity",
        "creator": "LifeDocs Press KDP Generator",
        "producer": "PyMuPDF",
    })
    
    # Save
    doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    
    print(f"  Created: {output_path} ({current_page} pages)")
    return output_path

def _extract_all_pdfs_from_zip(zip_path: Path, extract_dir: Path) -> None:
    """Extract all PDFs from the lifedocs.zip to a working directory."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            if name.lower().endswith('.pdf'):
                # Extract preserving folder structure
                target_path = extract_dir / name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if not target_path.exists():
                    zf.extract(name, extract_dir)

def main() -> None:
    zip_path = DEFAULT_ZIP
    
    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        return
    
    # Extract all PDFs first
    extract_dir = Path("lifedocs_extracted")
    print("Extracting source PDFs...")
    _extract_all_pdfs_from_zip(zip_path, extract_dir)
    
    # Generate KDP books
    print("\nGenerating KDP-ready books...")
    KDP_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    COVER_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for spec in COMMERCIAL_BOOK_SPECS:
        print(f"\nProcessing: {spec.title}")
        _render_kdp_book(spec, zip_path, extract_dir, KDP_OUTPUT_DIR)
    
    print(f"\nAll KDP books generated in: {KDP_OUTPUT_DIR}")

if __name__ == "__main__":
    main()