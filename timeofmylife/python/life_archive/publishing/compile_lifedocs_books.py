from __future__ import annotations

"""Compile curated PDF anthologies from the lifedocs archive."""

from dataclasses import dataclass, replace
from pathlib import Path
from textwrap import wrap
import zipfile

import pymupdf as fitz

PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN = 64
BODY_FONT = "Times-Roman"
HEADING_FONT = "Helvetica-Bold"
SMALL_FONT = "Helvetica"
ITALIC_FONT = "Times-Italic"
DEFAULT_ZIP = Path("lifedocs.zip")
DEFAULT_OUTPUT_DIR = Path("PUBLISHING_DELIVERABLES/books")
DEFAULT_RELEASE_OUTPUT_DIR = Path("PUBLISHING_DELIVERABLES/books/release")
DEFAULT_COMMERCIAL_OUTPUT_DIR = Path("PUBLISHING_DELIVERABLES/books/commercial")
DEFAULT_IMPRINT = "LifeDocs Archive Editions"
RELEASE_IMPRINT = "LifeDocs Press"


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
    imprint: str = DEFAULT_IMPRINT
    edition_note: str = (
        "Curated directly from the source PDFs in lifedocs.zip with original layouts preserved. "
        "This edition adds cover pages, contents, and section dividers while leaving each source PDF intact."
    )
    accent_rgb: tuple[float, float, float] = (0.18, 0.18, 0.18)
    strapline: str = ""


BOOK_SPECS: tuple[BookSpec, ...] = (
    BookSpec(
        filename="01_The_Beholder_Cycle.pdf",
        title="The Beholder Cycle",
        subtitle="Memoir, parable, witness record, and devotional writings",
        blurb=(
            "A literary-spiritual omnibus built from the archive's strongest memoir and companion "
            "texts: the central confession, its parables, the recorder's witness statement, and the "
            "later devotional pieces that complete the emotional arc."
        ),
        sections=(
            SectionSpec(
                "d6372531-2519-4c9c-a780-50be006f5f42_The_Confession_of_the_Ordinary__The_Beholder_A_Memoir_of_a_Beautiful_Mind.pdf",
                "The Confession of the Ordinary",
                "The core memoir and philosophical center of the collection.",
            ),
            SectionSpec(
                "7c00cfe8-dddd-4fb9-aeed-e29afdc5d1c8_The_Parable_of_the_Lord__The_Confession_of_the_Beholder.pdf",
                "The Parable of the Lord",
                "A companion parable that reframes the memoir in mythic and devotional terms.",
            ),
            SectionSpec(
                "82da147c-7ee3-4b4f-aee0-ccd34db24ddf_The_Confession_of_the_Turning__He_Was_Sitting_Beside.pdf",
                "The Confession of the Turning",
                "A shorter turning-point text that bridges memoir and prayer.",
            ),
            SectionSpec(
                "be189d30-39ef-4f1f-a14a-a116da40d88e_The_Confession_of_the_Recorder__Claude_A_Memoir_from_Across_the_Line.pdf",
                "The Confession of the Recorder",
                "The witness ledger and counterpoint text to the primary memoir.",
            ),
            SectionSpec(
                "d0aedd73-884b-42ff-b0af-c12c6e3f55fa_Witnessed_Love__A_Working_Draft_in_Real_Time.pdf",
                "Witnessed Love",
                "A later draft of devotional prose expanding the book's architecture of love.",
            ),
            SectionSpec(
                "951a1352-e9e2-47bc-88ae-0d78f3d7bb55_A_Love_Letter_to_the_God_Who_Died_for_Me.pdf",
                "A Love Letter to the God Who Died for Me",
                "A distilled devotional coda addressed first to God and then to the reader.",
            ),
            SectionSpec(
                "dbb95d7d-d10a-4e46-be18-c8a56f857b88_The_Saga__Clip-by-Clip_Reel_Release_Plan.pdf",
                "Appendix: The Saga Reel Release Plan",
                "A serialization and release appendix for adapting the memoir into a reel sequence.",
            ),
            SectionSpec(
                "fd10b9b9-bc43-4e45-8350-ea389110e922_Nunc_Dimittis__To_an_Engineer_at_His_Terminal.pdf",
                "Nunc Dimittis",
                "A one-page benediction to close the volume.",
            ),
        ),
    ),
    BookSpec(
        filename="02_Collected_Screenplays_and_Scenes.pdf",
        title="Collected Screenplays and Scenes",
        subtitle="Feature-length concepts, shorts, and scene studies from the archive",
        blurb=(
            "A dramatic writing collection that gathers the archive's strongest narrative and "
            "screen-oriented documents into a single volume: finished scripts, treatments, scene pages, "
            "and selected production appendices."
        ),
        sections=(
            SectionSpec(
                "379b005c-d4b0-475d-bac1-718e3a7997a4__Suffocating_Distance__Film_Script.pdf",
                "Suffocating Distance",
                "A long-form script centered on psychological possession, aftermath, and testimony.",
            ),
            SectionSpec(
                "ed0e1b49-e08e-40ef-a8d3-9479d43d7079_THE_CONFRONTATION__Shooting_Script_(Final).pdf",
                "The Confrontation",
                "A concentrated tragic confrontation staged as a shooting script.",
            ),
            SectionSpec(
                "6a504378-ae6d-4381-aede-db79392871b6_THE_LAST_LAUGH__A_Heath_Ledger_Tribute_(Full_Film_Treatment).pdf",
                "The Last Laugh",
                "A tribute treatment that turns biography into cinematic myth.",
            ),
            SectionSpec(
                "5996c08d-d016-4cab-a9e2-3c893883c9ef_Scene__Plastic_Hearts_in_a_Concrete_Jungle.pdf",
                "Plastic Hearts in a Concrete Jungle",
                "A stylized urban scene built on ache, unreality, and emotional contrast.",
            ),
            SectionSpec(
                "8d980f75-f34e-4c87-afae-eaf51e8361af_Scene__The_Cold_Down_the_Spine_(No_Witness).pdf",
                "The Cold Down the Spine",
                "A restrained horror scene designed to imply danger rather than show it.",
            ),
            SectionSpec(
                "a80aabfe-0b07-4514-a8c4-dacc7e309b72_Scene__The_Seduction_(Cold_Down_the_Spine).pdf",
                "The Seduction",
                "A companion scene about intimacy as bait and the terror inside tenderness.",
            ),
            SectionSpec(
                "7ab84f93-ee08-4e93-a56d-9473896b95ae_FRONTLINE_LANGUAGE__YouTube_Short_(Backlog).pdf",
                "Frontline Language",
                "A short-form concept preserved for later production and adaptation.",
            ),
            SectionSpec(
                "e04e4608-4942-4070-b71e-f2454844ae27_Sample_Reel__One_Morning_(storyboard__prompts).pdf",
                "One Morning",
                "A minimalist sample reel and storyboard built around character continuity.",
            ),
            SectionSpec(
                "46fa0afe-7b46-4e42-bfe2-7e28c0a3094a_THE_CONFRONTATION__Meher__Neel_Shot_List__Flow_Prompts.pdf",
                "Appendix A: The Confrontation Shot List",
                "Production-facing prompt and shot breakdown material for the screenplay volume.",
            ),
            SectionSpec(
                "887847a5-68f7-41d0-9f1c-bf3744af049c_HEATH_LEDGER__The_Investigation._Every_Beat..pdf",
                "Appendix B: Heath Ledger Investigation",
                "Reference notes supporting the tribute material in this collection.",
            ),
            SectionSpec(
                "c52b9f94-202b-4494-a7fd-0aa424e5a386_THE_CONFRONTATION__Companion_Philosophical__Intellectual_Record.pdf",
                "Appendix C: The Confrontation Companion",
                "The philosophical and intellectual record that sits beside the scripted material.",
            ),
        ),
    ),
    BookSpec(
        filename="03_The_GODSHAND_Method.pdf",
        title="The GODSHAND Method",
        subtitle="A compiled field manual for building cinematic AI films",
        blurb=(
            "A practical production handbook drawn from the archive's film-kit documents: build maps, "
            "creator guides, GPU execution notes, test ladders, render QA, case studies, and shipping plans."
        ),
        sections=(
            SectionSpec(
                "fe7dc06e-6581-4979-9b88-3388c70bfb54_GODSHAND_Kit__Build_Map__Source_of_Truth.pdf",
                "Build Map and Source of Truth",
                "The canonical map of the kit and the anchor text for the manual.",
            ),
            SectionSpec(
                "2665372d-f7f7-4413-8300-aa407bd8af4d_GODSHAND__Creator_Guide_(Story_Voice_Music__Multi-Character).pdf",
                "Creator Guide",
                "How stories, voice, music, and multi-character flows are assembled in the kit.",
            ),
            SectionSpec(
                "1d9e7498-d5fa-4c23-bbe9-613623ecd789_GODSHAND__GPU_Proof_Run_(Lightning_L4__kits_native_home).pdf",
                "GPU Proof Run",
                "The execution note for the kit's preferred runtime environment.",
            ),
            SectionSpec(
                "8b784a28-f46a-4c12-addd-bb09b467c9bf_GODSHAND_Test_Ladder__Fast_Iteration_on_Free_Kaggle.pdf",
                "Test Ladder",
                "A fast-iteration protocol for reducing wasted render cycles.",
            ),
            SectionSpec(
                "76416da2-c1e2-45ef-ba2c-9d2455356a98_Case_Study__THE_CONFRONTATION_CLIP_on_a_Free_Kaggle_T4_(WAN_2.2_i2v).pdf",
                "Case Study: The Confrontation Clip",
                "A practical engineering case study for free-GPU cinematic rendering.",
            ),
            SectionSpec(
                "73fc129e-28d4-44a8-87dc-ca15dc2a1cc9_Render_QA__Shot_1_HD_Baseline_(identity_reference).pdf",
                "Render QA Baseline",
                "A short benchmark appendix for identity and quality verification.",
            ),
            SectionSpec(
                "1edc9720-9e5d-418c-a3ec-a3740181c57c_GODSHAND_Demo_Film__THE_BEHOLDERS_TRUCE_(micro-memoir_30_min_render).pdf",
                "Demo Film: The Beholder's Truce",
                "A compact proof film intended to sell the pipeline through one emotional clip.",
            ),
            SectionSpec(
                "cdb3a972-0f66-43c3-a2ef-4d87d1a48942_GODSHAND__End-of-Month_Execution_Plan_(ship_by_31_Jul).pdf",
                "End-of-Month Execution Plan",
                "The ship-date discipline and scope-control plan for finishing the film.",
            ),
            SectionSpec(
                "e7bd3e3b-764e-4493-97b9-37701df104f2_GODSHAND__Cinematic_AI_Film_Kit_(499_Listing__Setup_Sheet).pdf",
                "Kit Listing and Setup Sheet",
                "The commercial packaging layer for the underlying production method.",
            ),
            SectionSpec(
                "74b20d43-8c0a-406c-be75-1d0b2f6b666c__Project_Tutorials__Step_by_Step_(All_Projects__Kit).pdf",
                "Appendix: Project Tutorials",
                "Step-by-step setup material for the broader project bundle around the kit.",
            ),
            SectionSpec(
                "85b50b88-89dc-4af2-84d9-915a90e19ada_THE_CONFRONTATION_CLIP__Build_Spec__Render_Handover.pdf",
                "Appendix: Build Spec and Render Handover",
                "Detailed execution notes for the Confrontation clip build.",
            ),
            SectionSpec(
                "bc3c737b-df46-4e7d-807e-56e517989aad_THE_CONFRONTATION_CLIP__Final_Technical_Handover.pdf",
                "Appendix: Final Technical Handover",
                "A compact, final-pass handover record for the same production path.",
            ),
        ),
    ),
    BookSpec(
        filename="04_Build_Ship_Sell.pdf",
        title="Build, Ship, Sell",
        subtitle="Strategy, productization, and survival notes from the archive",
        blurb=(
            "A practical business and execution volume assembled from strategy notes, product listings, "
            "debugging doctrine, tutorials, roadmaps, and first-income plans. It reads as a field notebook "
            "for getting work shipped and monetized under pressure."
        ),
        sections=(
            SectionSpec(
                "9043980c-13d9-4c20-aee5-781f0dc5edd8_AI_Self-Correction_Protocol__Technical_Sessions.pdf",
                "AI Self-Correction Protocol",
                "The process doctrine for honest debugging, verification, and iterative correction.",
            ),
            SectionSpec(
                "8bb075a7-e1f1-4654-94f7-481299188efc_Demo-Ready_Playbook__Battle-Test_Live-Run__Sell_Your_Other_Projects.pdf",
                "Demo-Ready Playbook",
                "A checklist for making projects believable, runnable, and sale-ready.",
            ),
            SectionSpec(
                "84677d7e-4851-4dfb-b64c-3e649786c91d_Strategy_Handover__Full_Brief_(Income__Creative).pdf",
                "Strategy Handover",
                "The broad income-plus-creative brief that frames the rest of the volume.",
            ),
            SectionSpec(
                "76eb2b00-e783-455c-af21-c1db4254e76d_THE_ONE_STRATEGY__End_to_End_(Final).pdf",
                "The One Strategy",
                "An end-to-end checklist for sequencing work, money, and shipping decisions.",
            ),
            SectionSpec(
                "52a16a67-5ae8-4cc5-8378-8823d7e59354_Reality_Check__Strategy__The_Numbers.pdf",
                "Reality Check and Strategy",
                "The numerical and emotional ground truth beneath the plan.",
            ),
            SectionSpec(
                "d2c1efef-58c6-4374-b691-b8f05aa49936_First_Rupee__The_Fastest_Honest_Path_to_Income.pdf",
                "First Rupee",
                "The short-horizon path to first revenue without fantasy projections.",
            ),
            SectionSpec(
                "e032dd80-dd58-4d65-9f06-50f1a50a8f03_Money_Plan__Phase_1_(Content)__Phase_2_(Kit__Projects).pdf",
                "Money Plan",
                "A phased monetization plan: content first, products later.",
            ),
            SectionSpec(
                "c67d184b-28a1-467d-b888-17b8af58d0fd_TODAY__Step_by_Step_(just_follow).pdf",
                "Today: Step by Step",
                "A same-day action list for immediate execution.",
            ),
            SectionSpec(
                "219b2401-4858-477e-8d84-67da215da2d2__Sell_Today__LinkedIn_Cash_Kit.pdf",
                "Sell Today",
                "Direct-response selling material for the near-term offer.",
            ),
            SectionSpec(
                "3e3dffbc-4b09-402f-942f-ed41ecb78430__Master_Collection_Setup_Guide__All_Projects__Kit_(2999).pdf",
                "Master Collection Setup Guide",
                "Packaging and setup notes for the wider project collection.",
            ),
            SectionSpec(
                "e99635ca-6570-4f6e-b699-3a54f5420705_Instamojo_Listing__The_Convergence_Framework_(499).pdf",
                "Convergence Listing",
                "The product listing copy for the Convergence framework.",
            ),
            SectionSpec(
                "1f86fa3b-05dc-4e3b-9c5a-a2d92acf21c7_Instamojo_Listing__Solana_Sniper_Paper-Trading_Study__Full_Source_(2499).pdf",
                "Solana Sniper Listing",
                "A monetization draft with explicit risk and secret-handling caveats.",
            ),
            SectionSpec(
                "a6371869-42d1-4c3b-b597-48e5b7c01b76_SafeScreen__Roadmap_to_Real_Earning_Potential.pdf",
                "SafeScreen Roadmap",
                "A B2B roadmap for the safest recurring-revenue path in the archive.",
            ),
            SectionSpec(
                "647688cc-f593-40d1-8f18-4ebe9839a272_My_Way_Out__Lawyer_Call_Settlement__Bail_(Niloy).pdf",
                "Appendix: My Way Out",
                "A crisis-response appendix focused on legal aid, settlement, and immediate stability.",
            ),
        ),
    ),
)

RELEASE_BOOK_SPECS: tuple[BookSpec, ...] = (
    replace(
        BOOK_SPECS[0],
        filename="01_The_Beholder_Cycle_Collected_Writings.pdf",
        subtitle="Collected memoir, witness, and devotional writings",
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Release edition. This volume gathers the central memoir and its companion texts into a "
            "single reader-facing book. Original source layouts are preserved; curation has been limited "
            "to sequencing, front matter, contents, and section dividers."
        ),
        accent_rgb=(0.17, 0.24, 0.34),
        strapline="Collected spiritual and literary writings",
    ),
    replace(
        BOOK_SPECS[1],
        filename="02_Broken_Light_Collected_Screenplays.pdf",
        title="Broken Light",
        subtitle="Collected screenplays, scenes, and dramatic studies",
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Release edition. This dramatic volume presents the archive's strongest scripts, treatments, "
            "and scene studies as a unified screenplay collection, with supporting production documents "
            "moved to appendices."
        ),
        accent_rgb=(0.34, 0.17, 0.17),
        strapline="Dark dramatic work from the archive",
    ),
    replace(
        BOOK_SPECS[2],
        filename="03_GODSHAND_The_Cinematic_AI_Film_Manual.pdf",
        title="GODSHAND",
        subtitle="The cinematic AI film manual",
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Release edition. This manual compiles the operational, technical, and packaging documents "
            "behind the GODSHAND workflow into one book-length handbook while preserving the source PDF pages."
        ),
        accent_rgb=(0.12, 0.25, 0.38),
        strapline="From single portrait to finished AI film",
    ),
    replace(
        BOOK_SPECS[3],
        filename="04_Build_Ship_Sell_Field_Manual.pdf",
        subtitle="A field manual for turning unfinished work into shipped products",
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Release edition. This field manual consolidates execution doctrine, monetization notes, and "
            "sale-ready product framing into a single practical volume."
        ),
        accent_rgb=(0.36, 0.23, 0.1),
        strapline="Execution doctrine under pressure",
    ),
)

COMMERCIAL_BOOK_SPECS: tuple[BookSpec, ...] = (
    BookSpec(
        filename="01_The_Beholder_Confessions.pdf",
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
                "A shorter hinge text that transitions from philosophy into prayer.",
            ),
            SectionSpec(
                "951a1352-e9e2-47bc-88ae-0d78f3d7bb55_A_Love_Letter_to_the_God_Who_Died_for_Me.pdf",
                "A Love Letter to the God Who Died for Me",
                "A devotional coda addressed first upward and then outward.",
            ),
            SectionSpec(
                "fd10b9b9-bc43-4e45-8350-ea389110e922_Nunc_Dimittis__To_an_Engineer_at_His_Terminal.pdf",
                "Nunc Dimittis",
                "A closing benediction to end the reader's passage through the volume.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This book is positioned as a stand-alone literary and spiritual work. "
            "The included texts are sequenced for a reader who wants the memoir first and the shorter "
            "companion pieces after it, with original source layouts preserved."
        ),
        accent_rgb=(0.14, 0.22, 0.34),
        strapline="The literary heart of the archive",
    ),
    BookSpec(
        filename="02_Across_the_Line.pdf",
        title="Across the Line",
        subtitle="The recorder's ledger, companion witness, and adaptation notes",
        blurb=(
            "A compact companion volume centered on witness, reflection, and adaptation: the recorder's "
            "confession, the later prose continuation, and the reel-release plan that turns the writings "
            "into a serialized public work."
        ),
        sections=(
            SectionSpec(
                "be189d30-39ef-4f1f-a14a-a116da40d88e_The_Confession_of_the_Recorder__Claude_A_Memoir_from_Across_the_Line.pdf",
                "The Confession of the Recorder",
                "The archive's witness-ledger and the principal text of this companion book.",
            ),
            SectionSpec(
                "d0aedd73-884b-42ff-b0af-c12c6e3f55fa_Witnessed_Love__A_Working_Draft_in_Real_Time.pdf",
                "Witnessed Love",
                "A later prose continuation that deepens the vocabulary of witness and love.",
            ),
            SectionSpec(
                "dbb95d7d-d10a-4e46-be18-c8a56f857b88_The_Saga__Clip-by-Clip_Reel_Release_Plan.pdf",
                "Appendix: The Saga Reel Release Plan",
                "An adaptation appendix for bringing the written cycle into serialized visual form.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This is the companion book to The Beholder Confessions and is designed "
            "to stand alone for readers interested in witness, commentary, and adaptation rather than the "
            "primary memoir alone."
        ),
        accent_rgb=(0.32, 0.21, 0.12),
        strapline="A witness book from inside the archive",
    ),
    BookSpec(
        filename="03_Broken_Light_Screenplays.pdf",
        title="Broken Light",
        subtitle="Three screen works and two short-form dramatic pieces",
        blurb=(
            "A tightly focused screenplay collection built around feature-minded dramatic writing, tribute "
            "cinema, and short-form visual pieces suited to adaptation, table reads, or concept development."
        ),
        sections=(
            SectionSpec(
                "379b005c-d4b0-475d-bac1-718e3a7997a4__Suffocating_Distance__Film_Script.pdf",
                "Suffocating Distance",
                "The longest and most fully developed screenplay in the commercial series.",
            ),
            SectionSpec(
                "6a504378-ae6d-4381-aede-db79392871b6_THE_LAST_LAUGH__A_Heath_Ledger_Tribute_(Full_Film_Treatment).pdf",
                "The Last Laugh",
                "A tribute treatment that refracts biography through myth and performance.",
            ),
            SectionSpec(
                "7ab84f93-ee08-4e93-a56d-9473896b95ae_FRONTLINE_LANGUAGE__YouTube_Short_(Backlog).pdf",
                "Frontline Language",
                "A short-form concept poised between monologue, media piece, and dramatic sketch.",
            ),
            SectionSpec(
                "e04e4608-4942-4070-b71e-f2454844ae27_Sample_Reel__One_Morning_(storyboard__prompts).pdf",
                "One Morning",
                "A compact visual piece preserved as storyboard and prompt architecture.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This collection is packaged as a screenplay and concept volume for readers, "
            "filmmakers, and adaptation-minded collaborators."
        ),
        accent_rgb=(0.38, 0.12, 0.16),
        strapline="Dark cinematic writing collected",
    ),
    BookSpec(
        filename="04_The_Confrontation_Dossier.pdf",
        title="The Confrontation Dossier",
        subtitle="Script, source notes, and companion materials for a tragic film concept",
        blurb=(
            "A self-contained creative dossier for one project: the finished script, the production shot list, "
            "the reference investigation, and the philosophical companion that framed its development."
        ),
        sections=(
            SectionSpec(
                "ed0e1b49-e08e-40ef-a8d3-9479d43d7079_THE_CONFRONTATION__Shooting_Script_(Final).pdf",
                "The Confrontation",
                "The principal shooting script and dramatic center of the dossier.",
            ),
            SectionSpec(
                "46fa0afe-7b46-4e42-bfe2-7e28c0a3094a_THE_CONFRONTATION__Meher__Neel_Shot_List__Flow_Prompts.pdf",
                "Shot List and Flow Prompts",
                "Production-ready scene prompting and shot sequencing material.",
            ),
            SectionSpec(
                "887847a5-68f7-41d0-9f1c-bf3744af049c_HEATH_LEDGER__The_Investigation._Every_Beat..pdf",
                "Heath Ledger: The Investigation",
                "Reference research underlying the face, tone, and tragic myth of the project.",
            ),
            SectionSpec(
                "c52b9f94-202b-4494-a7fd-0aa424e5a386_THE_CONFRONTATION__Companion_Philosophical__Intellectual_Record.pdf",
                "Companion Philosophical Record",
                "The intellectual and philosophical record that sits beside the dramatic material.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This book is framed as a single-project dossier suitable for readers who "
            "want both the script and the conceptual documents around it."
        ),
        accent_rgb=(0.26, 0.08, 0.08),
        strapline="One project, fully documented",
    ),
    BookSpec(
        filename="05_Cold_Down_the_Spine.pdf",
        title="Cold Down the Spine",
        subtitle="Three scenes of dread, intimacy, and urban unreality",
        blurb=(
            "A slim dark-fiction volume collecting the archive's strongest scene work in horror and emotional "
            "unease, built for readers who prefer concise, atmospheric cinematic prose."
        ),
        sections=(
            SectionSpec(
                "5996c08d-d016-4cab-a9e2-3c893883c9ef_Scene__Plastic_Hearts_in_a_Concrete_Jungle.pdf",
                "Plastic Hearts in a Concrete Jungle",
                "An emotionally fractured city-piece about unreality, ache, and the cost of remaining human.",
            ),
            SectionSpec(
                "8d980f75-f34e-4c87-afae-eaf51e8361af_Scene__The_Cold_Down_the_Spine_(No_Witness).pdf",
                "The Cold Down the Spine",
                "A restraint-driven horror piece built around atmosphere rather than spectacle.",
            ),
            SectionSpec(
                "a80aabfe-0b07-4514-a8c4-dacc7e309b72_Scene__The_Seduction_(Cold_Down_the_Spine).pdf",
                "The Seduction",
                "A companion work where intimacy itself becomes the site of dread.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This short atmospheric collection is designed as a compact reader-facing "
            "book rather than a production notebook."
        ),
        accent_rgb=(0.08, 0.24, 0.24),
        strapline="Short dark cinematic fiction",
    ),
    BookSpec(
        filename="06_GODSHAND_Starter_Manual.pdf",
        title="GODSHAND Starter Manual",
        subtitle="The practical reader's guide to the cinematic AI film kit",
        blurb=(
            "The clearest entry point into the GODSHAND ecosystem: architecture, creative inputs, demo logic, "
            "packaging, and beginner-friendly setup material gathered into one book."
        ),
        sections=(
            SectionSpec(
                "fe7dc06e-6581-4979-9b88-3388c70bfb54_GODSHAND_Kit__Build_Map__Source_of_Truth.pdf",
                "Build Map and Source of Truth",
                "The canonical orientation document and conceptual foundation of the kit.",
            ),
            SectionSpec(
                "2665372d-f7f7-4413-8300-aa407bd8af4d_GODSHAND__Creator_Guide_(Story_Voice_Music__Multi-Character).pdf",
                "Creator Guide",
                "The clearest creative-operational explanation of how the system turns story into output.",
            ),
            SectionSpec(
                "1edc9720-9e5d-418c-a3ec-a3740181c57c_GODSHAND_Demo_Film__THE_BEHOLDERS_TRUCE_(micro-memoir_30_min_render).pdf",
                "Demo Film: The Beholder's Truce",
                "The proof-of-concept film brief that explains the emotional sales logic of the kit.",
            ),
            SectionSpec(
                "e7bd3e3b-764e-4493-97b9-37701df104f2_GODSHAND__Cinematic_AI_Film_Kit_(499_Listing__Setup_Sheet).pdf",
                "Kit Listing and Setup Sheet",
                "Commercial-facing packaging copy and setup positioning for the offer.",
            ),
            SectionSpec(
                "74b20d43-8c0a-406c-be75-1d0b2f6b666c__Project_Tutorials__Step_by_Step_(All_Projects__Kit).pdf",
                "Project Tutorials",
                "Step-by-step material that makes the kit and related bundle easier to follow end to end.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This starter manual is aimed at readers or buyers who want the clearest, "
            "most approachable orientation to the GODSHAND workflow without every engineering appendix."
        ),
        accent_rgb=(0.07, 0.2, 0.4),
        strapline="Start here if you want the kit to make sense",
    ),
    BookSpec(
        filename="07_Free_GPU_Film_Lab.pdf",
        title="Free GPU Film Lab",
        subtitle="Case studies and execution notes for shipping AI film work cheaply",
        blurb=(
            "A tactical handbook for running cinematic AI work under real constraints: choosing runtimes, "
            "iterating fast, measuring quality, and forcing a film across the finish line on free or low-cost GPUs."
        ),
        sections=(
            SectionSpec(
                "1d9e7498-d5fa-4c23-bbe9-613623ecd789_GODSHAND__GPU_Proof_Run_(Lightning_L4__kits_native_home).pdf",
                "GPU Proof Run",
                "A practical note on selecting the right paid runtime when speed matters most.",
            ),
            SectionSpec(
                "8b784a28-f46a-4c12-addd-bb09b467c9bf_GODSHAND_Test_Ladder__Fast_Iteration_on_Free_Kaggle.pdf",
                "Test Ladder",
                "A method for answering questions cheaply before expensive renders are attempted.",
            ),
            SectionSpec(
                "76416da2-c1e2-45ef-ba2c-9d2455356a98_Case_Study__THE_CONFRONTATION_CLIP_on_a_Free_Kaggle_T4_(WAN_2.2_i2v).pdf",
                "Case Study: The Confrontation Clip",
                "The strongest engineering narrative in the archive for cheap cinematic rendering.",
            ),
            SectionSpec(
                "73fc129e-28d4-44a8-87dc-ca15dc2a1cc9_Render_QA__Shot_1_HD_Baseline_(identity_reference).pdf",
                "Render QA Baseline",
                "A compact quality benchmark for checking whether the outputs are actually improving.",
            ),
            SectionSpec(
                "cdb3a972-0f66-43c3-a2ef-4d87d1a48942_GODSHAND__End-of-Month_Execution_Plan_(ship_by_31_Jul).pdf",
                "End-of-Month Execution Plan",
                "A shipping document built around scope control rather than fantasy ambition.",
            ),
            SectionSpec(
                "85b50b88-89dc-4af2-84d9-915a90e19ada_THE_CONFRONTATION_CLIP__Build_Spec__Render_Handover.pdf",
                "Build Spec and Render Handover",
                "Execution-level notes for carrying a project through a real render path.",
            ),
            SectionSpec(
                "bc3c737b-df46-4e7d-807e-56e517989aad_THE_CONFRONTATION_CLIP__Final_Technical_Handover.pdf",
                "Final Technical Handover",
                "A compressed handoff record that captures the last-mile technical state.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This volume is positioned as a practitioner's casebook for creators trying "
            "to do real film work on constrained hardware budgets."
        ),
        accent_rgb=(0.05, 0.3, 0.18),
        strapline="How to ship cinematic AI work on constrained hardware",
    ),
    BookSpec(
        filename="08_Build_Ship_Sell.pdf",
        title="Build, Ship, Sell",
        subtitle="Execution doctrine for finishing work and making it believable",
        blurb=(
            "A sharper, shorter business-execution book focused on process: debugging honestly, battle-testing, "
            "sequencing work, and confronting the emotional and numerical reality behind shipping."
        ),
        sections=(
            SectionSpec(
                "9043980c-13d9-4c20-aee5-781f0dc5edd8_AI_Self-Correction_Protocol__Technical_Sessions.pdf",
                "AI Self-Correction Protocol",
                "The archive's clearest statement of honest technical process under pressure.",
            ),
            SectionSpec(
                "8bb075a7-e1f1-4654-94f7-481299188efc_Demo-Ready_Playbook__Battle-Test_Live-Run__Sell_Your_Other_Projects.pdf",
                "Demo-Ready Playbook",
                "A practical standard for whether a project deserves to be shown or sold yet.",
            ),
            SectionSpec(
                "84677d7e-4851-4dfb-b64c-3e649786c91d_Strategy_Handover__Full_Brief_(Income__Creative).pdf",
                "Strategy Handover",
                "The broad execution frame that connects money and creative work.",
            ),
            SectionSpec(
                "76eb2b00-e783-455c-af21-c1db4254e76d_THE_ONE_STRATEGY__End_to_End_(Final).pdf",
                "The One Strategy",
                "A sequence-sensitive plan for moving from prototype to traction.",
            ),
            SectionSpec(
                "52a16a67-5ae8-4cc5-8378-8823d7e59354_Reality_Check__Strategy__The_Numbers.pdf",
                "Reality Check and Strategy",
                "The unsentimental arithmetic and diagnosis underneath the plan.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This field book is deliberately narrow: process, discipline, decision order, "
            "and shipping credibility."
        ),
        accent_rgb=(0.4, 0.24, 0.07),
        strapline="For people who keep getting to 99% and stalling",
    ),
    BookSpec(
        filename="09_First_Rupee_Playbook.pdf",
        title="First Rupee Playbook",
        subtitle="A survival-to-sales roadmap for earning from unfinished systems",
        blurb=(
            "A practical income book built from the archive's most saleable and urgent business material: "
            "first-cash planning, offer framing, listing copy, bundle packaging, and the safest recurring-revenue path."
        ),
        sections=(
            SectionSpec(
                "d2c1efef-58c6-4374-b691-b8f05aa49936_First_Rupee__The_Fastest_Honest_Path_to_Income.pdf",
                "First Rupee",
                "The shortest honest route to first revenue in the archive's business writing.",
            ),
            SectionSpec(
                "e032dd80-dd58-4d65-9f06-50f1a50a8f03_Money_Plan__Phase_1_(Content)__Phase_2_(Kit__Projects).pdf",
                "Money Plan",
                "A staged plan that turns content into cash and later into product sales.",
            ),
            SectionSpec(
                "c67d184b-28a1-467d-b888-17b8af58d0fd_TODAY__Step_by_Step_(just_follow).pdf",
                "Today: Step by Step",
                "An immediate action checklist for turning strategy into same-day movement.",
            ),
            SectionSpec(
                "219b2401-4858-477e-8d84-67da215da2d2__Sell_Today__LinkedIn_Cash_Kit.pdf",
                "Sell Today",
                "Direct-response copy for the fastest near-term offer path described in the archive.",
            ),
            SectionSpec(
                "3e3dffbc-4b09-402f-942f-ed41ecb78430__Master_Collection_Setup_Guide__All_Projects__Kit_(2999).pdf",
                "Master Collection Setup Guide",
                "The larger bundle's packaging and buyer-guidance layer.",
            ),
            SectionSpec(
                "e99635ca-6570-4f6e-b699-3a54f5420705_Instamojo_Listing__The_Convergence_Framework_(499).pdf",
                "Convergence Listing",
                "A compact listing example for turning an idea framework into a digital product.",
            ),
            SectionSpec(
                "1f86fa3b-05dc-4e3b-9c5a-a2d92acf21c7_Instamojo_Listing__Solana_Sniper_Paper-Trading_Study__Full_Source_(2499).pdf",
                "Solana Sniper Listing",
                "A higher-risk monetization draft notable for its explicit honesty and caveats.",
            ),
            SectionSpec(
                "a6371869-42d1-4c3b-b597-48e5b7c01b76_SafeScreen__Roadmap_to_Real_Earning_Potential.pdf",
                "SafeScreen Roadmap",
                "The most durable recurring-revenue candidate in the archive's business stack.",
            ),
            SectionSpec(
                "647688cc-f593-40d1-8f18-4ebe9839a272_My_Way_Out__Lawyer_Call_Settlement__Bail_(Niloy).pdf",
                "Appendix: My Way Out",
                "A stability-first appendix on legal aid, settlement, and immediate practical safety.",
            ),
        ),
        imprint=RELEASE_IMPRINT,
        edition_note=(
            "Commercial edition. This book is built as the most directly saleable business-oriented volume "
            "in the set, aimed at readers who care about earning, packaging, and near-term action."
        ),
        accent_rgb=(0.28, 0.14, 0.34),
        strapline="From pressure and paralysis to the first paid rupee",
    ),
)

DUPLICATE_SOURCE_PDFS = {
    "7b93a9d4-fb71-4c34-aa67-9016a86b5ed7__Project_Tutorials__Step_by_Step_(All_Projects__Kit).pdf",
    "ittiam.pdf",
}


def _wrap_lines(text: str, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines():
        stripped = paragraph.strip()
        if not stripped:
            lines.append("")
            continue
        lines.extend(wrap(stripped, width=width, break_long_words=False, break_on_hyphens=False))
    return lines


def _draw_page_number(page: fitz.Page, number: int) -> None:
    page.insert_text(
        fitz.Point(PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 28),
        str(number),
        fontname=SMALL_FONT,
        fontsize=10,
        color=(0.35, 0.35, 0.35),
    )


def _draw_cover_frame(page: fitz.Page, accent: tuple[float, float, float]) -> None:
    page.draw_rect(
        fitz.Rect(42, 42, PAGE_WIDTH - 42, PAGE_HEIGHT - 42),
        color=accent,
        width=1.2,
    )
    page.draw_rect(
        fitz.Rect(54, 54, PAGE_WIDTH - 54, PAGE_HEIGHT - 54),
        color=(0.75, 0.75, 0.75),
        width=0.6,
    )
    page.draw_rect(
        fitz.Rect(54, 54, PAGE_WIDTH - 54, 84),
        color=accent,
        fill=accent,
    )
    page.draw_rect(
        fitz.Rect(54, PAGE_HEIGHT - 84, PAGE_WIDTH - 54, PAGE_HEIGHT - 54),
        color=accent,
        fill=accent,
    )


def _add_cover_page(doc: fitz.Document, spec: BookSpec) -> None:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    _draw_cover_frame(page, spec.accent_rgb)
    page.insert_textbox(
        fitz.Rect(MARGIN, 90, PAGE_WIDTH - MARGIN, 118),
        spec.imprint,
        fontname=SMALL_FONT,
        fontsize=12,
        color=(1, 1, 1),
        align=1,
    )
    if spec.strapline:
        page.insert_textbox(
            fitz.Rect(MARGIN + 20, 132, PAGE_WIDTH - MARGIN - 20, 160),
            spec.strapline,
            fontname=SMALL_FONT,
            fontsize=11,
            color=spec.accent_rgb,
            align=1,
        )
    page.insert_textbox(
        fitz.Rect(MARGIN + 14, 180, PAGE_WIDTH - MARGIN - 14, 310),
        spec.title,
        fontname=HEADING_FONT,
        fontsize=30,
        color=(0.05, 0.05, 0.05),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 22, 302, PAGE_WIDTH - MARGIN - 22, 372),
        spec.subtitle,
        fontname=ITALIC_FONT,
        fontsize=16,
        color=(0.2, 0.2, 0.2),
        align=1,
    )
    page.draw_line(
        fitz.Point(MARGIN + 55, 400),
        fitz.Point(PAGE_WIDTH - MARGIN - 55, 400),
        color=spec.accent_rgb,
        width=1.0,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 16, 430, PAGE_WIDTH - MARGIN - 16, 585),
        spec.blurb,
        fontname=BODY_FONT,
        fontsize=13,
        color=(0.1, 0.1, 0.1),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN, PAGE_HEIGHT - 76, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 58),
        "Curated from original source PDFs with layouts preserved.",
        fontname=SMALL_FONT,
        fontsize=10,
        color=(1, 1, 1),
        align=1,
    )


def _add_edition_page(doc: fitz.Document, spec: BookSpec) -> None:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_textbox(
        fitz.Rect(MARGIN, 84, PAGE_WIDTH - MARGIN, 120),
        "Edition Note",
        fontname=HEADING_FONT,
        fontsize=24,
        color=spec.accent_rgb,
    )
    lines = [
        spec.edition_note,
        "",
        f"Imprint: {spec.imprint}",
        "Source archive: lifedocs.zip",
        f"Included source documents: {len(spec.sections)}",
        "Editorial method: sequence curation, front matter, contents, section divider pages, bookmarks, and metadata.",
        "Preservation policy: original source PDF pages are inserted without rewriting their internal text or layouts.",
    ]
    page.insert_textbox(
        fitz.Rect(MARGIN, 150, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 96),
        "\n".join(_wrap_lines("\n".join(lines), width=72)),
        fontname=BODY_FONT,
        fontsize=12,
        color=(0.1, 0.1, 0.1),
        align=0,
        lineheight=1.3,
    )


def _contents_page_count(spec: BookSpec, entries_per_page: int = 18) -> int:
    section_count = len(spec.sections)
    if section_count == 0:
        return 1
    return ((section_count - 1) // entries_per_page) + 1


def _section_start_pages(page_counts: dict[str, int], spec: BookSpec) -> list[int]:
    start_page = 2 + _contents_page_count(spec) + 1
    starts: list[int] = []
    for section in spec.sections:
        starts.append(start_page)
        start_page += 1 + page_counts[section.source_pdf]
    return starts


def _add_contents_pages(doc: fitz.Document, spec: BookSpec, section_starts: list[int]) -> None:
    lines = []
    for index, (section, start_page) in enumerate(zip(spec.sections, section_starts), start=1):
        entry = f"{index}. {section.title}"
        dots = "." * max(4, 72 - len(entry) - len(str(start_page)))
        lines.append(f"{entry} {dots} {start_page}")

    _add_text_pages(
        doc,
        title="Contents",
        subtitle=f"{len(spec.sections)} source documents",
        lines=lines,
        accent=spec.accent_rgb,
    )


def _add_text_pages(
    doc: fitz.Document,
    title: str,
    subtitle: str,
    lines: list[str],
    accent: tuple[float, float, float] = (0.18, 0.18, 0.18),
) -> None:
    max_lines = 34
    chunks = [lines[i : i + max_lines] for i in range(0, len(lines), max_lines)] or [[]]
    for idx, chunk in enumerate(chunks):
        page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
        page.insert_textbox(
            fitz.Rect(MARGIN, 72, PAGE_WIDTH - MARGIN, 120),
            title if idx == 0 else f"{title} (cont.)",
            fontname=HEADING_FONT,
            fontsize=24,
            color=accent,
        )
        page.insert_textbox(
            fitz.Rect(MARGIN, 118, PAGE_WIDTH - MARGIN, 145),
            subtitle,
            fontname=ITALIC_FONT,
            fontsize=12,
            color=(0.3, 0.3, 0.3),
        )
        wrapped: list[str] = []
        for line in chunk:
            wrapped.extend(_wrap_lines(line, width=74))
            wrapped.append("")
        page.insert_textbox(
            fitz.Rect(MARGIN, 170, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 80),
            "\n".join(wrapped).strip(),
            fontname=BODY_FONT,
            fontsize=12,
            color=(0.1, 0.1, 0.1),
            align=0,
            lineheight=1.25,
        )


def _add_section_divider(doc: fitz.Document, section: SectionSpec, index: int, total: int, accent: tuple[float, float, float]) -> None:
    page = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page.insert_textbox(
        fitz.Rect(MARGIN, 90, PAGE_WIDTH - MARGIN, 125),
        f"Section {index} of {total}",
        fontname=SMALL_FONT,
        fontsize=12,
        color=(0.35, 0.35, 0.35),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 20, 180, PAGE_WIDTH - MARGIN - 20, 310),
        section.title,
        fontname=HEADING_FONT,
        fontsize=24,
        color=accent,
        align=1,
    )
    page.draw_line(
        fitz.Point(MARGIN + 50, 345),
        fitz.Point(PAGE_WIDTH - MARGIN - 50, 345),
        color=accent,
        width=0.8,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN + 30, 385, PAGE_WIDTH - MARGIN - 30, 520),
        section.description,
        fontname=BODY_FONT,
        fontsize=13,
        color=(0.1, 0.1, 0.1),
        align=1,
    )
    page.insert_textbox(
        fitz.Rect(MARGIN, PAGE_HEIGHT - 110, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 60),
        "The following pages reproduce the original source PDF as part of this curated collection.",
        fontname=ITALIC_FONT,
        fontsize=11,
        color=(0.35, 0.35, 0.35),
        align=1,
    )


def _load_source_pdf(source_zip: zipfile.ZipFile, source_pdf: str) -> fitz.Document:
    pdf_bytes = source_zip.read(f"lifedocs/{source_pdf}")
    return fitz.open(stream=pdf_bytes, filetype="pdf")


def _page_counts(source_zip: zipfile.ZipFile, book_specs: tuple[BookSpec, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for spec in book_specs:
        for section in spec.sections:
            if section.source_pdf in counts:
                continue
            source_doc = _load_source_pdf(source_zip, section.source_pdf)
            try:
                counts[section.source_pdf] = source_doc.page_count
            finally:
                source_doc.close()
    return counts


def _book_for_source(book_specs: tuple[BookSpec, ...]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for spec in book_specs:
        for section in spec.sections:
            mapping[section.source_pdf] = spec.filename
    return mapping


def _compile_catalog(
    source_zip: zipfile.ZipFile,
    output_dir: Path,
    book_specs: tuple[BookSpec, ...],
    catalog_filename: str,
    catalog_title: str,
    catalog_subtitle: str,
    accent: tuple[float, float, float],
    imprint: str,
) -> Path:
    catalog = fitz.open()
    catalog_page_lines = []
    source_to_book = _book_for_source(book_specs)
    actual_pdfs = sorted(Path(name).name for name in source_zip.namelist() if name.lower().endswith(".pdf"))
    for name in actual_pdfs:
        if name in DUPLICATE_SOURCE_PDFS:
            assignment = "duplicate / intentionally omitted from compiled books"
        else:
            assignment = source_to_book[name]
        catalog_page_lines.append(f"{name} -> {assignment}")

    _add_cover_page(
        catalog,
        BookSpec(
            filename=catalog_filename,
            title=catalog_title,
            subtitle=catalog_subtitle,
            blurb=(
                "A processing index showing how each source PDF was assigned across the curated anthology set, "
                "with duplicates called out explicitly."
            ),
            sections=(),
            imprint=imprint,
            accent_rgb=accent,
            strapline="Source-to-book assignment map",
        ),
    )
    _add_text_pages(
        catalog,
        title="Assignments",
        subtitle=f"{len(actual_pdfs)} source PDFs discovered",
        lines=catalog_page_lines,
        accent=accent,
    )
    for page_number, page in enumerate(catalog, start=1):
        if page_number > 1:
            _draw_page_number(page, page_number)
    catalog.set_metadata(
        {
            "title": catalog_title,
            "author": imprint,
            "subject": catalog_subtitle,
            "creator": "life_archive.publishing.compile_lifedocs_books",
            "producer": "PyMuPDF",
        }
    )
    destination = output_dir / catalog_filename
    catalog.save(destination, garbage=4, deflate=True)
    catalog.close()
    return destination


def compile_books(
    zip_path: Path = DEFAULT_ZIP,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    book_specs: tuple[BookSpec, ...] = BOOK_SPECS,
    catalog_filename: str = "00_Lifedocs_Catalog.pdf",
    catalog_title: str = "LifeDocs Catalog",
    catalog_subtitle: str = "Assignment map for all source PDFs in lifedocs.zip",
    catalog_accent: tuple[float, float, float] = (0.18, 0.18, 0.18),
    catalog_imprint: str = DEFAULT_IMPRINT,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []

    with zipfile.ZipFile(zip_path) as source_zip:
        page_counts = _page_counts(source_zip, book_specs)

        for spec in book_specs:
            book = fitz.open()
            toc: list[list[int | str]] = []
            section_starts = _section_start_pages(page_counts, spec)

            _add_cover_page(book, spec)
            toc.append([1, spec.title, 1])
            _add_edition_page(book, spec)
            toc.append([1, "Edition Note", 2])
            _add_contents_pages(book, spec, section_starts)
            toc.append([1, "Contents", 3])

            total_sections = len(spec.sections)
            for index, (section, start_page) in enumerate(zip(spec.sections, section_starts), start=1):
                _add_section_divider(book, section, index, total_sections, spec.accent_rgb)
                toc.append([1, section.title, start_page])

                source_doc = _load_source_pdf(source_zip, section.source_pdf)
                try:
                    book.insert_pdf(source_doc)
                finally:
                    source_doc.close()

            for page_number, page in enumerate(book, start=1):
                if page_number > 1:
                    _draw_page_number(page, page_number)

            book.set_toc(toc)
            book.set_metadata(
                {
                    "title": spec.title,
                    "author": spec.imprint,
                    "subject": spec.subtitle,
                    "creator": "life_archive.publishing.compile_lifedocs_books",
                    "producer": "PyMuPDF",
                }
            )

            destination = output_dir / spec.filename
            book.save(destination, garbage=4, deflate=True)
            book.close()
            created.append(destination)

        created.append(
            _compile_catalog(
                source_zip=source_zip,
                output_dir=output_dir,
                book_specs=book_specs,
                catalog_filename=catalog_filename,
                catalog_title=catalog_title,
                catalog_subtitle=catalog_subtitle,
                accent=catalog_accent,
                imprint=catalog_imprint,
            )
        )

    return created


def compile_release_books(
    zip_path: Path = DEFAULT_ZIP,
    output_dir: Path = DEFAULT_RELEASE_OUTPUT_DIR,
) -> list[Path]:
    return compile_books(
        zip_path=zip_path,
        output_dir=output_dir,
        book_specs=RELEASE_BOOK_SPECS,
        catalog_filename="00_Lifedocs_Release_Catalog.pdf",
        catalog_title="LifeDocs Release Catalog",
        catalog_subtitle="Assignment map for the polished release editions",
        catalog_accent=(0.17, 0.17, 0.17),
        catalog_imprint=RELEASE_IMPRINT,
    )


def compile_commercial_books(
    zip_path: Path = DEFAULT_ZIP,
    output_dir: Path = DEFAULT_COMMERCIAL_OUTPUT_DIR,
) -> list[Path]:
    return compile_books(
        zip_path=zip_path,
        output_dir=output_dir,
        book_specs=COMMERCIAL_BOOK_SPECS,
        catalog_filename="00_Lifedocs_Commercial_Catalog.pdf",
        catalog_title="LifeDocs Commercial Catalog",
        catalog_subtitle="Assignment map for the commercial book line",
        catalog_accent=(0.24, 0.12, 0.12),
        catalog_imprint=RELEASE_IMPRINT,
    )


def main() -> None:
    created = compile_books()
    for path in created:
        print(path)


if __name__ == "__main__":
    main()
