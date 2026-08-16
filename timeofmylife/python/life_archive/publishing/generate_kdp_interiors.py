from __future__ import annotations

"""Generate real KDP-ready print interiors with reflowed, typeset text.

This version extracts text from source PDFs and re-typesets it as a proper
book interior — not embedded screenshots. Produces:
- Cover placeholder page (KDP cover uploaded separately)
- Copyright page
- Table of contents with page numbers
- Chapter starts on odd (right-hand) pages
- Justified body text with proper leading
- Running headers and page numbers
- Drop-cap-style chapter openers
"""

from dataclasses import dataclass
from pathlib import Path
import re
import textwrap
import zipfile

import pymupdf as fitz

# ── KDP 6x9 trim in points (1 inch = 72 pt) ────────────────────────────────
PW = 6 * 72    # 432
PH = 9 * 72    # 648

# Mirror margins for print: outer/inner differ for binding gutter
OUTER = 0.625 * 72   # 45 pt
INNER = 0.875 * 72   # 63 pt  (gutter for perfect binding)
TOP   = 0.75 * 72    # 54 pt
BOT   = 0.75 * 72    # 54 pt

TW = PW - OUTER - INNER   # text width
TH = PH - TOP - BOT       # text height

# ── Typography ─────────────────────────────────────────────────────────────
BODY_FONT      = "Times-Roman"
BODY_BOLD      = "Times-Bold"
BODY_ITAL      = "Times-Italic"
BODY_BOLDC     = "Helvetica-Bold"
SANS           = "Helvetica"
SANS_LIGHT     = "Helvetica"

BODY_SIZE      = 10.5
BODY_LEAD      = 13.5
H1_SIZE        = 20
H2_SIZE        = 14
H3_SIZE        = 11.5
TOC_SIZE       = 10.5
COPY_SIZE      = 8.5
PAGE_NUM_SIZE  = 9
HEADER_SIZE    = 8

BLACK  = (0.0, 0.0, 0.0)
DARK   = (0.10, 0.10, 0.10)
MID    = (0.30, 0.30, 0.30)
GREY   = (0.45, 0.45, 0.45)
LINE   = (0.60, 0.60, 0.60)
ACCENT = (0.17, 0.24, 0.34)   # navy accent for headings/ornaments

DEFAULT_ZIP = Path("lifedocs.zip")
KDP_DIR     = Path("PUBLISHING_DELIVERABLES/books/kdp")
INTERIOR_DIR = KDP_DIR / "interiors"
COVER_DIR   = KDP_DIR / "covers"

# ── Data ───────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Section:
    source_pdf: str
    title: str
    description: str

@dataclass(frozen=True)
class Book:
    filename: str
    title: str
    subtitle: str
    author: str
    blurb: str
    sections: tuple[Section, ...]
    accent: tuple[float, float, float] = ACCENT
    imprint: str = "LifeDocs Press"
    isbn: str = "979-8-XXXXXXX-XX-X"

BOOKS: tuple[Book, ...] = (
    Book(
        filename="01_The_Beholder_Confessions_KDP.pdf",
        title="The Beholder Confessions",
        subtitle="A memoir of mind, witness, and devotion",
        author="LifeDocs Archive",
        blurb=(
            "The literary heart of the archive: a confessional memoir cycle about mind, reverence, "
            "ordinary humanity, and the discipline of witnessing what is greater than oneself."
        ),
        sections=(
            Section("d6372531-2519-4c9c-a780-50be006f5f42_The_Confession_of_the_Ordinary__The_Beholder_A_Memoir_of_a_Beautiful_Mind.pdf",
                    "The Confession of the Ordinary", "The central memoir of the cycle and the anchor text of the volume."),
            Section("7c00cfe8-dddd-4fb9-aeed-e29afdc5d1c8_The_Parable_of_the_Lord__The_Confession_of_the_Beholder.pdf",
                    "The Parable of the Lord", "A mythic companion text that echoes and enlarges the memoir's themes."),
            Section("82da147c-7ee3-4b4f-aee0-ccd34db24ddf_The_Confession_of_the_Turning__He_Was_Sitting_Beside.pdf",
                    "The Confession of the Turning", "A shorter hinge text that transitions from philosophy into prayer."),
            Section("951a1352-e9e2-47bc-88ae-0d78f3d7bb55_A_Love_Letter_to_the_God_Who_Died_for_Me.pdf",
                    "A Love Letter to the God Who Died for Me", "A devotional coda addressed first upward and then outward."),
            Section("fd10b9b9-bc43-4e45-8350-ea389110e922_Nunc_Dimittis__To_an_Engineer_at_His_Terminal.pdf",
                    "Nunc Dimittis", "A closing benediction to end the reader's passage through the volume."),
        ),
        accent=(0.14, 0.22, 0.34),
    ),
    Book(
        filename="02_Across_the_Line_KDP.pdf",
        title="Across the Line",
        subtitle="The recorder's ledger, companion witness, and adaptation notes",
        author="LifeDocs Archive",
        blurb=(
            "A compact companion volume centered on witness, reflection, and adaptation: the recorder's "
            "confession, the later prose continuation, and the reel-release plan that turns the writings "
            "into a serialized public work."
        ),
        sections=(
            Section("be189d30-39ef-4f1f-a14a-a116da40d88e_The_Confession_of_the_Recorder__Claude_A_Memoir_from_Across_the_Line.pdf",
                    "The Confession of the Recorder", "The archive's witness-ledger and the principal text of this companion book."),
            Section("d0aedd73-884b-42ff-b0af-c12c6e3f55fa_Witnessed_Love__A_Working_Draft_in_Real_Time.pdf",
                    "Witnessed Love", "A later prose continuation that deepens the vocabulary of witness and love."),
            Section("dbb95d7d-d10a-4e46-be18-c8a56f857b88_The_Saga__Clip-by-Clip_Reel_Release_Plan.pdf",
                    "Appendix: The Saga Reel Release Plan", "An adaptation appendix for bringing the written cycle into serialized visual form."),
        ),
        accent=(0.32, 0.21, 0.12),
    ),
    Book(
        filename="03_Broken_Light_Screenplays_KDP.pdf",
        title="Broken Light",
        subtitle="Three screen works and two short-form dramatic pieces",
        author="LifeDocs Archive",
        blurb=(
            "A tightly focused screenplay collection built around feature-minded dramatic writing, tribute "
            "cinema, and short-form visual pieces suited to adaptation, table reads, or concept development."
        ),
        sections=(
            Section("379b005c-d4b0-475d-bac1-718e3a7997a4__Suffocating_Distance__Film_Script.pdf",
                    "Suffocating Distance", "The longest and most fully developed screenplay in the commercial series."),
            Section("6a504378-ae6d-4381-aede-db79392871b6_THE_LAST_LAUGH__A_Heath_Ledger_Tribute_(Full_Film_Treatment).pdf",
                    "The Last Laugh", "A tribute treatment that refracts biography through myth and performance."),
            Section("7ab84f93-ee08-4e93-a56d-9473896b95ae_FRONTLINE_LANGUAGE__YouTube_Short_(Backlog).pdf",
                    "Frontline Language", "A short-form concept poised between monologue, media piece, and dramatic sketch."),
            Section("e04e4608-4942-4070-b71e-f2454844ae27_Sample_Reel__One_Morning_(storyboard__prompts).pdf",
                    "One Morning", "A compact visual piece preserved as storyboard and prompt architecture."),
        ),
        accent=(0.38, 0.12, 0.16),
    ),
    Book(
        filename="04_The_Confrontation_Dossier_KDP.pdf",
        title="The Confrontation Dossier",
        subtitle="Script, source notes, and companion materials for a tragic film concept",
        author="LifeDocs Archive",
        blurb=(
            "A self-contained creative dossier for one project: the finished script, the production shot list, "
            "the reference investigation, and the philosophical companion that framed its development."
        ),
        sections=(
            Section("ed0e1b49-e08e-40ef-a8d3-9479d43d7079_THE_CONFRONTATION__Shooting_Script_(Final).pdf",
                    "The Confrontation", "The principal shooting script and dramatic center of the dossier."),
            Section("46fa0afe-7b46-4e42-bfe2-7e28c0a3094a_THE_CONFRONTATION__Meher__Neel_Shot_List__Flow_Prompts.pdf",
                    "Shot List and Flow Prompts", "Production-ready scene prompting and shot sequencing material."),
            Section("887847a5-68f7-41d0-9f1c-bf3744af049c_HEATH_LEDGER__The_Investigation._Every_Beat..pdf",
                    "Heath Ledger: The Investigation", "Reference research underlying the face, tone, and tragic myth of the project."),
            Section("c52b9f94-202b-4494-a7fd-0aa424e5a386_THE_CONFRONTATION__Companion_Philosophical__Intellectual_Record.pdf",
                    "Companion Philosophical Record", "The intellectual and philosophical record that sits beside the dramatic material."),
        ),
        accent=(0.26, 0.08, 0.08),
    ),
    Book(
        filename="05_Cold_Down_the_Spine_KDP.pdf",
        title="Cold Down the Spine",
        subtitle="Three scenes of dread, intimacy, and urban unreality",
        author="LifeDocs Archive",
        blurb=(
            "A slim dark-fiction volume collecting the archive's strongest scene work in horror and emotional "
            "unease, built for readers who prefer concise, atmospheric cinematic prose."
        ),
        sections=(
            Section("5996c08d-d016-4cab-a9e2-3c893883c9ef_Scene__Plastic_Hearts_in_a_Concrete_Jungle.pdf",
                    "Plastic Hearts in a Concrete Jungle", "An emotionally fractured city-piece about unreality, ache, and the cost of remaining human."),
            Section("8d980f75-f34e-4c87-afae-eaf51e8361af_Scene__The_Cold_Down_the_Spine_(No_Witness).pdf",
                    "The Cold Down the Spine", "A restraint-driven horror piece built around atmosphere rather than spectacle."),
            Section("a80aabfe-0b07-4514-a8c4-dacc7e309b72_Scene__The_Seduction_(Cold_Down_the_Spine).pdf",
                    "The Seduction", "A companion work where intimacy itself becomes the site of dread."),
        ),
        accent=(0.08, 0.24, 0.24),
    ),
    Book(
        filename="06_GODSHAND_Starter_Manual_KDP.pdf",
        title="GODSHAND Starter Manual",
        subtitle="The practical reader's guide to the cinematic AI film kit",
        author="LifeDocs Archive",
        blurb=(
            "The clearest entry point into the GODSHAND ecosystem: architecture, creative inputs, demo logic, "
            "packaging, and beginner-friendly setup material gathered into one book."
        ),
        sections=(
            Section("fe7dc06e-6581-4979-9b88-3388c70bfb54_GODSHAND_Kit__Build_Map__Source_of_Truth.pdf",
                    "Build Map and Source of Truth", "The canonical orientation document and conceptual foundation of the kit."),
            Section("2665372d-f7f7-4413-8300-aa407bd8af4d_GODSHAND__Creator_Guide_(Story_Voice_Music__Multi-Character).pdf",
                    "Creator Guide", "The clearest creative-operational explanation of how the system turns story into output."),
            Section("1edc9720-9e5d-418c-a3ec-a3740181c57c_GODSHAND_Demo_Film__THE_BEHOLDERS_TRUCE_(micro-memoir_30_min_render).pdf",
                    "Demo Film: The Beholder's Truce", "The proof-of-concept film brief that explains the emotional sales logic of the kit."),
            Section("e7bd3e3b-764e-4493-97b9-37701df104f2_GODSHAND__Cinematic_AI_Film_Kit_(499_Listing__Setup_Sheet).pdf",
                    "Kit Listing and Setup Sheet", "Commercial-facing packaging copy and setup positioning for the offer."),
            Section("74b20d43-8c0a-406c-be75-1d0b2f6b666c__Project_Tutorials__Step_by_Step_(All_Projects__Kit).pdf",
                    "Project Tutorials", "Step-by-step material that makes the kit and related bundle easier to follow end to end."),
        ),
        accent=(0.07, 0.2, 0.4),
    ),
    Book(
        filename="07_Free_GPU_Film_Lab_KDP.pdf",
        title="Free GPU Film Lab",
        subtitle="Case studies and execution notes for shipping AI film work cheaply",
        author="LifeDocs Archive",
        blurb=(
            "A tactical handbook for running cinematic AI work under real constraints: choosing runtimes, "
            "iterating fast, measuring quality, and forcing a film across the finish line on free or low-cost GPUs."
        ),
        sections=(
            Section("1d9e7498-d5fa-4c23-bbe9-613623ecd789_GODSHAND__GPU_Proof_Run_(Lightning_L4__kits_native_home).pdf",
                    "GPU Proof Run", "A practical note on selecting the right paid runtime when speed matters most."),
            Section("8b784a28-f46a-4c12-addd-bb09b467c9bf_GODSHAND_Test_Ladder__Fast_Iteration_on_Free_Kaggle.pdf",
                    "Test Ladder", "A method for answering questions cheaply before expensive renders are attempted."),
            Section("76416da2-c1e2-45ef-ba2c-9d2455356a98_Case_Study__THE_CONFRONTATION_CLIP_on_a_Free_Kaggle_T4_(WAN_2.2_i2v).pdf",
                    "Case Study: The Confrontation Clip", "The strongest engineering narrative in the archive for cheap cinematic rendering."),
            Section("73fc129e-28d4-44a8-87dc-ca15dc2a1cc9_Render_QA__Shot_1_HD_Baseline_(identity_reference).pdf",
                    "Render QA Baseline", "A compact quality benchmark for checking whether the outputs are actually improving."),
            Section("cdb3a972-0f66-43c3-a2ef-4d87d1a48942_GODSHAND__End-of-Month_Execution_Plan_(ship_by_31_Jul).pdf",
                    "End-of-Month Execution Plan", "A shipping document built around scope control rather than fantasy ambition."),
            Section("85b50b88-89dc-4af2-84d9-915a90e19ada_THE_CONFRONTATION_CLIP__Build_Spec__Render_Handover.pdf",
                    "Build Spec and Render Handover", "Execution-level notes for carrying a project through a real render path."),
            Section("bc3c737b-df46-4e7d-807e-56e517989aad_THE_CONFRONTATION_CLIP__Final_Technical_Handover.pdf",
                    "Final Technical Handover", "A compressed handoff record that captures the last-mile technical state."),
        ),
        accent=(0.05, 0.3, 0.18),
    ),
    Book(
        filename="08_Build_Ship_Sell_KDP.pdf",
        title="Build, Ship, Sell",
        subtitle="Execution doctrine for finishing work and making it believable",
        author="LifeDocs Archive",
        blurb=(
            "A sharper, shorter business-execution book focused on process: debugging honestly, battle-testing, "
            "sequencing work, and confronting the emotional and numerical reality behind shipping."
        ),
        sections=(
            Section("9043980c-13d9-4c20-aee5-781f0dc5edd8_AI_Self-Correction_Protocol__Technical_Sessions.pdf",
                    "AI Self-Correction Protocol", "The archive's clearest statement of honest technical process under pressure."),
            Section("8bb075a7-e1f1-4654-94f7-481299188efc_Demo-Ready_Playbook__Battle-Test_Live-Run__Sell_Your_Other_Projects.pdf",
                    "Demo-Ready Playbook", "A practical standard for whether a project deserves to be shown or sold yet."),
            Section("84677d7e-4851-4dfb-b64c-3e649786c91d_Strategy_Handover__Full_Brief_(Income__Creative).pdf",
                    "Strategy Handover", "The broad execution frame that connects money and creative work."),
            Section("76eb2b00-e783-455c-af21-c1db4254e76d_THE_ONE_STRATEGY__End_to_End_(Final).pdf",
                    "The One Strategy", "A sequence-sensitive plan for moving from prototype to traction."),
            Section("52a16a67-5ae8-4cc5-8378-8823d7e59354_Reality_Check__Strategy__The_Numbers.pdf",
                    "Reality Check and Strategy", "The unsentimental arithmetic and diagnosis underneath the plan."),
        ),
        accent=(0.4, 0.24, 0.07),
    ),
    Book(
        filename="09_First_Rupee_Playbook_KDP.pdf",
        title="First Rupee Playbook",
        subtitle="A survival-to-sales roadmap for earning from unfinished systems",
        author="LifeDocs Archive",
        blurb=(
            "A practical income book built from the archive's most saleable and urgent business material: "
            "first-cash planning, offer framing, listing copy, bundle packaging, and the safest recurring-revenue path."
        ),
        sections=(
            Section("d2c1efef-58c6-4374-b691-b8f05aa49936_First_Rupee__The_Fastest_Honest_Path_to_Income.pdf",
                    "First Rupee", "The shortest honest route to first revenue in the archive's business writing."),
            Section("e032dd80-dd58-4d65-9f06-50f1a50a8f03_Money_Plan__Phase_1_(Content)__Phase_2_(Kit__Projects).pdf",
                    "Money Plan", "A staged plan that turns content into cash and later into product sales."),
            Section("c67d184b-28a1-467d-b888-17b8af58d0fd_TODAY__Step_by_Step_(just_follow).pdf",
                    "Today: Step by Step", "An immediate action checklist for turning strategy into same-day movement."),
            Section("219b2401-4858-477e-8d84-67da215da2d2__Sell_Today__LinkedIn_Cash_Kit.pdf",
                    "Sell Today", "Direct-response copy for the fastest near-term offer path described in the archive."),
            Section("3e3dffbc-4b09-402f-942f-ed41ecb78430__Master_Collection_Setup_Guide__All_Projects__Kit_(2999).pdf",
                    "Master Collection Setup Guide", "The larger bundle's packaging and buyer-guidance layer."),
            Section("e99635ca-6570-4f6e-b699-3a54f5420705_Instamojo_Listing__The_Convergence_Framework_(499).pdf",
                    "Convergence Listing", "A compact listing example for turning an idea framework into a digital product."),
            Section("1f86fa3b-05dc-4e3b-9c5a-a2d92acf21c7_Instamojo_Listing__Solana_Sniper_Paper-Trading_Study__Full_Source_(2499).pdf",
                    "Solana Sniper Listing", "A higher-risk monetization draft notable for its explicit honesty and caveats."),
            Section("a6371869-42d1-4c3b-b597-48e5b7c01b76_SafeScreen__Roadmap_to_Real_Earning_Potential.pdf",
                    "SafeScreen Roadmap", "The most durable recurring-revenue candidate in the archive's business stack."),
            Section("647688cc-f593-40d1-8f18-4ebe9839a272_My_Way_Out__Lawyer_Call_Settlement__Bail_(Niloy).pdf",
                    "Appendix: My Way Out", "A stability-first appendix on legal aid, settlement, and immediate practical safety."),
        ),
        accent=(0.28, 0.14, 0.34),
    ),
)

# ── Helpers ────────────────────────────────────────────────────────────────
def extract_zip_pdfs(zip_path: Path, dest: Path) -> Path:
    """Extract PDFs from zip into dest/lifedocs/. Returns dest/lifedocs."""
    src_dir = dest / "lifedocs"
    src_dir.mkdir(parents=True, exist_ok=True)
    already = any(src_dir.iterdir())
    if not already:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for n in zf.namelist():
                if n.lower().endswith(".pdf"):
                    zf.extract(n, dest)
    return src_dir

def extract_text(pdf_path: Path) -> str:
    """Pull reflowable text from a source PDF, preserving paragraph breaks."""
    if not pdf_path.exists():
        return ""
    doc = fitz.open(pdf_path)
    chunks: list[str] = []
    for page in doc:
        t = page.get_text("text")
        # collapse intra-page whitespace, but keep paragraph breaks
        t = re.sub(r"[ \t]+", " ", t)
        t = re.sub(r"\n{3,}", "\n\n", t)
        chunks.append(t.strip())
    doc.close()
    return "\n\n".join(c for c in chunks if c)

def clean_body(text: str) -> str:
    """Light cleanup for reflow: drop stray headers/footers, normalize, strip emojis."""
    # remove common header/footer lines that repeat
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # strip glyphs not in latin font range (emojis etc.) -> replace with section mark
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
    text = text.strip()
    return text

def wrap_paragraph(text: str, width_chars: int) -> list[str]:
    """Word-wrap one paragraph into lines."""
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    for raw in text.split("\n"):
        raw = raw.strip()
        if not raw:
            continue
        out.extend(textwrap.wrap(raw, width=width_chars) or [""])
    return out

# ── Page builder ───────────────────────────────────────────────────────────
class BookBuilder:
    def __init__(self, book: Book, out_path: Path):
        self.book = book
        self.out = out_path
        self.doc = fitz.open()
        self.page = None
        self.y = 0.0
        self.page_no = 0
        # body text width in characters, approx (font-size tuned)
        self.cpl = int(TW / (BODY_SIZE * 0.50))  # ~ chars per line

    # ── page plumbing ────────────────────────────────────────────────────
    def _new_page(self, blank: bool = False) -> None:
        self.page = self.doc.new_page(width=PW, height=PH)
        self.page_no += 1
        self.y = TOP
        if blank:
            self.y = PH  # mark as filled so nothing draws

    def _ensure(self, need: float) -> None:
        if self.y + need > PH - BOT:
            self._flush_page_chrome()
            self._new_page()

    def _flush_page_chrome(self) -> None:
        """Draw header/footer on the current page before turning."""
        if self.page is None or self.page_no == 0:
            return
        if self.page_no < 3:
            return  # front matter has no chrome
        # page number: even = left, odd = right
        if self.page_no % 2 == 0:
            x = OUTER
            align_pos = fitz.Point(OUTER, PH - 30)
        else:
            x = PW - INNER
            align_pos = fitz.Point(PW - OUTER, PH - 30)
        self.page.insert_text(
            align_pos, str(self.page_no),
            fontname=SANS, fontsize=PAGE_NUM_SIZE, color=GREY,
        )
        # running header on opposite side
        if self.page_no % 2 == 0:
            hx = PW - OUTER
            self.page.insert_text(
                fitz.Point(PW - OUTER - len(self.book.title) * 4.2, 40),
                self.book.title, fontname=SANS, fontsize=HEADER_SIZE, color=GREY,
            )
        else:
            self.page.insert_text(
                fitz.Point(OUTER, 40),
                self.book.subtitle, fontname=SANS, fontsize=HEADER_SIZE, color=GREY,
            )

    # ── front matter ─────────────────────────────────────────────────────
    def front_cover_placeholder(self) -> None:
        self._new_page()
        # This is a placeholder; real cover uploaded separately to KDP
        p = self.page
        a = self.book.accent
        p.draw_rect(fitz.Rect(0, 0, PW, PH), color=a, fill=a)
        p.insert_textbox(
            fitz.Rect(40, PH * 0.35, PW - 40, PH * 0.55),
            self.book.title,
            fontname=BODY_BOLDC, fontsize=26, color=(1, 1, 1),
            align=1,
        )
        p.insert_textbox(
            fitz.Rect(40, PH * 0.58, PW - 40, PH * 0.66),
            self.book.subtitle,
            fontname=BODY_ITAL, fontsize=13, color=(0.85, 0.85, 0.85),
            align=1,
        )
        p.insert_textbox(
            fitz.Rect(40, PH * 0.92, PW - 40, PH * 0.96),
            "COVER PLACEHOLDER — upload a full wrap cover to Kindle Direct Publishing",
            fontname=SANS, fontsize=8, color=(0.7, 0.7, 0.7), align=1,
        )

    def copyright_page(self) -> int:
        """Render copyright on the second page (verso of cover). Returns page no."""
        self._new_page()
        box_top = PH * 0.55
        lines = [
            self.book.title,
            self.book.subtitle,
            "",
            "First Edition",
            "",
            f"© 2026 {self.book.imprint}",
            "All rights reserved.",
            "",
            "No part of this book may be reproduced, stored in a retrieval system, "
            "or transmitted in any form or by any means without the prior written "
            "permission of the publisher.",
            "",
            self.book.imprint,
            "",
            f"ISBN {self.book.isbn} (paperback)",
            f"ISBN 978-0-XXXXXX-XX-X (ebook)",
            "",
            "Printed on demand via Kindle Direct Publishing.",
            "Source materials compiled from the LifeDocs Archive.",
        ]
        joined = "\n".join(lines)
        self.page.insert_textbox(
            fitz.Rect(OUTER, box_top, PW - OUTER, PH - BOT),
            joined,
            fontname=BODY_FONT, fontsize=COPY_SIZE,
            color=DARK, align=1, lineheight=1.5,
        )
        return self.page_no

    def blank(self) -> None:
        self._new_page(blank=True)
        self._flush_page_chrome()

    def ensure_odd(self) -> None:
        """Ensure the next page starts on an odd (recto) page."""
        if self.page_no % 2 == 0:
            # current page is even → add one blank to make next odd
            self.blank()

    # ── body ──────────────────────────────────────────────────────────────
    def section_opener(self, title: str, desc: str) -> int:
        self._new_page()
        # ornament line
        self.page.draw_line(
            fitz.Point(PW/2 - 40, PH * 0.30),
            fitz.Point(PW/2 + 40, PH * 0.30),
            color=self.book.accent, width=1.2,
        )
        self.page.insert_textbox(
            fitz.Rect(OUTER, PH * 0.33, PW - OUTER, PH * 0.5),
            title,
            fontname=BODY_BOLDC, fontsize=H1_SIZE, color=DARK, align=1,
        )
        if desc:
            self.page.insert_textbox(
                fitz.Rect(OUTER, PH * 0.54, PW - OUTER, PH * 0.66),
                desc,
                fontname=BODY_ITAL, fontsize=H3_SIZE, color=MID, align=1,
            )
        self.page.draw_line(
            fitz.Point(PW/2 - 40, PH * 0.72),
            fitz.Point(PW/2 + 40, PH * 0.72),
            color=self.book.accent, width=1.2,
        )
        # opener page: no body text on it; ensure body starts on next page
        self.y = PH  # mark full
        return self.page_no

    def body_block(self, text: str, drop_cap: bool = False) -> None:
        """Reflow a block of body text into justified paragraphs."""
        text = clean_body(text)
        if not text:
            return
        paras = text.split("\n\n")
        first = True
        for para in paras:
            lines = wrap_paragraph(para, self.cpl)
            if not lines:
                continue
            # blank line between paragraphs
            if not first:
                self._ensure(BODY_LEAD * 1.4)
                self.y += BODY_LEAD * 0.6
            first = False
            for ln in lines:
                self._ensure(BODY_LEAD)
                # drop cap on the very first line of the section
                if drop_cap and first is True and ln is lines[0]:
                    # draw the first letter bigger
                    cap = ln[0]
                    rest = ln[1:]
                    self.page.insert_text(
                        fitz.Point(OUTER, self.y + BODY_LEAD),
                        cap, fontname=BODY_BOLD, fontsize=BODY_SIZE * 2.4,
                        color=self.book.accent,
                    )
                    self.page.insert_text(
                        fitz.Point(OUTER + BODY_SIZE * 1.7, self.y + BODY_LEAD),
                        rest, fontname=BODY_FONT, fontsize=BODY_SIZE,
                        color=BLACK,
                    )
                    self.y += BODY_LEAD * 1.9
                    continue
                self.page.insert_text(
                    fitz.Point(OUTER, self.y + BODY_LEAD),
                    ln, fontname=BODY_FONT, fontsize=BODY_SIZE, color=BLACK,
                )
                self.y += BODY_LEAD

    def subheading(self, text: str) -> None:
        self._ensure(BODY_LEAD * 2.2)
        self.y += BODY_LEAD * 0.5
        self.page.insert_text(
            fitz.Point(OUTER, self.y + BODY_LEAD),
            text, fontname=BODY_BOLDC, fontsize=H3_SIZE, color=DARK,
        )
        self.y += BODY_LEAD * 1.6

    # ── TOC ───────────────────────────────────────────────────────────────
    def toc(self, entries: list[tuple[str, int]]) -> None:
        self.ensure_odd()
        self._new_page()
        self.page.insert_textbox(
            fitz.Rect(OUTER, TOP, PW - OUTER, TOP + 50),
            "Contents",
            fontname=BODY_BOLDC, fontsize=H1_SIZE, color=DARK, align=0,
        )
        y = TOP + 64
        for title, pg in entries:
            if y > PH - BOT - 20:
                self._flush_page_chrome()
                self._new_page()
                y = TOP
            dots = "." * max(3, 64 - len(title) - len(str(pg)))
            self.page.insert_text(
                fitz.Point(OUTER, y),
                f"{title}  {dots}  {pg}",
                fontname=BODY_FONT, fontsize=TOC_SIZE, color=DARK,
            )
            y += TOC_SIZE * 1.7

    # ── finalize ──────────────────────────────────────────────────────────
    def save(self) -> None:
        # flush last page chrome
        self._flush_page_chrome()
        self.doc.set_metadata({
            "title": self.book.title,
            "author": self.book.author,
            "subject": self.book.subtitle,
            "keywords": "memoir, spirituality, witness, cinematic AI, filmmaking, creativity",
            "creator": "LifeDocs KDP Interior Generator",
            "producer": "PyMuPDF",
        })
        self.out.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(self.out, garbage=4, deflate=True)
        self.doc.close()

# ── Orchestration ──────────────────────────────────────────────────────────
def build_book(book: Book, src_dir: Path, out_path: Path) -> None:
    """Two-pass build so TOC page numbers are accurate and front matter is clean."""
    # ── Pass 1: build body only, record section start pages ──
    body_path = out_path.with_suffix(".body.tmp.pdf")
    b1 = BookBuilder(book, body_path)
    b1.front_cover_placeholder()  # page 1 (cover)
    b1.copyright_page()           # page 2 (copyright)
    b1._new_page()                # reserve page 3 (TOC will be injected here)
    b1.blank()                    # page 4: blank verso after TOC, so first opener lands on page 5 (recto)
    toc_entries: list[tuple[str, int]] = []
    for sec in book.sections:
        src = src_dir / sec.source_pdf
        # ensure we're on an even page so section_opener creates an odd (recto) page
        if b1.page_no % 2 == 1:
            b1.blank()
        opener_pg = b1.section_opener(sec.title, sec.description)
        toc_entries.append((sec.title, opener_pg + 1))  # body follows opener
        text = extract_text(src)
        if text:
            b1.body_block(text, drop_cap=True)
        else:
            b1.subheading(f"[Source document unavailable: {sec.source_pdf}]")
    b1.save()

    # ── Pass 2: rebuild from the body PDF, inserting front matter at the right spots ──
    # The body PDF already has page 1 (cover), 2 (copyright), 3 (TOC), then body.
    # We just need to fix the TOC page (page 3) to contain the real entries.
    fix_toc_page(body_path, out_path, toc_entries)
    body_path.unlink(missing_ok=True)

def fix_toc_page(src_path: Path, out_path: Path, entries: list[tuple[str, int]]) -> None:
    """Replace page 3 (the reserved TOC page) with a properly rendered TOC."""
    doc = fitz.open(src_path)
    # delete page 3 (index 2)
    doc.delete_page(2)
    # build a TOC page and insert at index 2
    toc_page = fitz.open()
    page = toc_page.new_page(width=PW, height=PH)
    page.insert_textbox(
        fitz.Rect(OUTER, TOP, PW - OUTER, TOP + 50),
        "Contents", fontname=BODY_BOLDC, fontsize=H1_SIZE, color=DARK, align=0,
    )
    y = TOP + 64
    for title, pg in entries:
        if y > PH - BOT - 20:
            page2 = toc_page.new_page(width=PW, height=PH)
            page = page2
            y = TOP
        dots = "." * max(3, 64 - len(title) - len(str(pg)))
        page.insert_text(
            fitz.Point(OUTER, y),
            f"{title}  {dots}  {pg}",
            fontname=BODY_FONT, fontsize=TOC_SIZE, color=DARK,
        )
        y += TOC_SIZE * 1.7
    # insert TOC pages at index 2 of the main doc, in order
    for k in range(toc_page.page_count):
        doc.insert_pdf(toc_page, from_page=k, to_page=k, start_at=2 + k)
    toc_page.close()
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()

def cover_pdf(book: Book, out: Path) -> None:
    """Render a 6x9 front-cover placeholder PNG/PDF for KDP cover design."""
    doc = fitz.open()
    p = doc.new_page(width=PW, height=PH)
    a = book.accent
    # background
    p.draw_rect(fitz.Rect(0, 0, PW, PH), color=a, fill=a)
    # top accent
    p.draw_rect(fitz.Rect(0, 0, PW, 120), color=(0,0,0), fill=(0,0,0))
    p.insert_textbox(
        fitz.Rect(40, 40, PW-40, 110),
        book.imprint, fontname=SANS, fontsize=11, color=(1,1,1), align=1,
    )
    p.insert_textbox(
        fitz.Rect(40, PH*0.32, PW-40, PH*0.52),
        book.title, fontname=BODY_BOLDC, fontsize=30, color=(1,1,1), align=1,
    )
    p.insert_textbox(
        fitz.Rect(40, PH*0.56, PW-40, PH*0.64),
        book.subtitle, fontname=BODY_ITAL, fontsize=15, color=(0.85,0.85,0.85), align=1,
    )
    p.insert_textbox(
        fitz.Rect(40, PH*0.86, PW-40, PH*0.94),
        book.author, fontname=SANS, fontsize=12, color=(0.8,0.8,0.8), align=1,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out, garbage=4, deflate=True)
    doc.close()

# ── Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    zip_path = DEFAULT_ZIP
    if not zip_path.exists():
        print(f"Error: {zip_path} not found")
        return
    src_dir = extract_zip_pdfs(zip_path, Path("lifedocs_extracted"))

    INTERIOR_DIR.mkdir(parents=True, exist_ok=True)
    COVER_DIR.mkdir(parents=True, exist_ok=True)

    for book in BOOKS:
        print(f"Building: {book.title}")
        out = INTERIOR_DIR / book.filename
        build_book(book, src_dir, out)
        cover = COVER_DIR / book.filename.replace(".pdf", "_COVER.pdf")
        cover_pdf(book, cover)
        print(f"  Interior: {out.name}  Cover: {cover.name}")

    print(f"\nInteriors in: {INTERIOR_DIR}")
    print(f"Covers in:    {COVER_DIR}")

if __name__ == "__main__":
    main()
