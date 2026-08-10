"""
KDP-Publishable Build Script — The Beholder Project
Produces all three volumes as 6×9" paperback-ready PDFs with:
- Full-bleed cover images
- Proper gutters (inside 0.875", outside 0.625")
- Running headers and page numbers
- Title pages, copyright pages
- Back cover blurbs and author bios
"""
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch as INCH
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    PageBreak, Table, TableStyle, NextPageTemplate, Image as RLImage,
    KeepTogether
)
import re, os, subprocess, sys

# ── KDP Specs ──
PW = 6 * INCH
PH = 9 * INCH
KDP_SIZE = (PW, PH)
GUTTER = 0.875 * INCH
OUTSIDE = 0.625 * INCH
TB = 0.75 * INCH

# ── Colours ──
DARK = HexColor('#1a1a2e')
ACCENT = HexColor('#16213e')
GOLD = HexColor('#b8860b')
MED_GREY = HexColor('#666666')
LIGHT_GREY = HexColor('#f5f5f5')

# ── Styles ──
def make_styles():
    base = getSampleStyleSheet()
    s = {}
    s['Body'] = ParagraphStyle('Body', parent=base['Normal'],
        fontName='Times-Roman', fontSize=10.5, leading=14.5,
        alignment=TA_JUSTIFY, spaceAfter=7, textColor=HexColor('#222222'))
    s['Title'] = ParagraphStyle('Title', parent=base['Title'],
        fontName='Helvetica-Bold', fontSize=24, leading=30,
        alignment=TA_CENTER, textColor=DARK, spaceAfter=6)
    s['Subtitle'] = ParagraphStyle('Subtitle', parent=base['Normal'],
        fontName='Helvetica', fontSize=12, leading=16,
        alignment=TA_CENTER, textColor=MED_GREY, spaceAfter=4)
    s['Author'] = ParagraphStyle('Author', parent=base['Normal'],
        fontName='Helvetica', fontSize=11, leading=15,
        alignment=TA_CENTER, textColor=MED_GREY, spaceBefore=16)
    s['H1'] = ParagraphStyle('H1', parent=base['Heading1'],
        fontName='Helvetica-Bold', fontSize=18, leading=24,
        spaceBefore=24, spaceAfter=12, textColor=DARK, keepWithNext=1)
    s['H2'] = ParagraphStyle('H2', parent=base['Heading2'],
        fontName='Helvetica-Bold', fontSize=14, leading=18,
        spaceBefore=18, spaceAfter=9, textColor=ACCENT, keepWithNext=1)
    s['H3'] = ParagraphStyle('H3', parent=base['Heading3'],
        fontName='Helvetica-Bold', fontSize=11, leading=15,
        spaceBefore=12, spaceAfter=7, textColor=ACCENT, keepWithNext=1)
    s['Quote'] = ParagraphStyle('Quote', parent=s['Body'],
        fontName='Times-Italic', fontSize=10, leading=13.5,
        leftIndent=24, rightIndent=24, textColor=MED_GREY,
        spaceBefore=6, spaceAfter=6)
    s['Ref'] = ParagraphStyle('Ref', parent=s['Body'],
        fontName='Times-Roman', fontSize=9, leading=12.5,
        leftIndent=18, firstLineIndent=-18, spaceAfter=3)
    s['Meta'] = ParagraphStyle('Meta', parent=s['Body'],
        fontName='Helvetica', fontSize=8.5, leading=11.5,
        alignment=TA_CENTER, textColor=MED_GREY, spaceBefore=8)
    s['Bullet'] = ParagraphStyle('Bullet', parent=s['Body'],
        bulletIndent=8, leftIndent=24, spaceAfter=3,
        bulletFontName='Helvetica', bulletFontSize=9)
    s['BackBlurb'] = ParagraphStyle('BackBlurb',
        fontName='Times-Italic', fontSize=10.5, leading=14.5,
        alignment=TA_JUSTIFY, textColor=HexColor('#333333'), spaceAfter=10)
    s['AuthorBio'] = ParagraphStyle('AuthorBio',
        fontName='Times-Roman', fontSize=9.5, leading=13.5,
        alignment=TA_JUSTIFY, textColor=HexColor('#444444'), spaceAfter=6)
    s['BackMeta'] = ParagraphStyle('BackMeta',
        fontName='Helvetica', fontSize=7.5, leading=10.5,
        alignment=TA_CENTER, textColor=MED_GREY)
    s['TableHead'] = ParagraphStyle('TableHead',
        fontName='Helvetica-Bold', fontSize=8.5, leading=11.5, textColor=white)
    s['TableCell'] = ParagraphStyle('TableCell',
        fontName='Times-Roman', fontSize=8.5, leading=11.5,
        textColor=HexColor('#222222'))
    return s

def escape(t):
    return t.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def esc_md(t):
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*(.+?)\*', r'<i>\1</i>', t)
    return escape(t)

# ── Page callbacks ──
def running_heads(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(MED_GREY)
    canvas.drawCentredString(PW/2, 0.3*INCH, str(doc.page))
    if hasattr(doc, '_book_title') and doc.page > 4:
        if doc.page % 2 == 0:
            canvas.drawString(GUTTER, PH - 0.35*INCH, doc._book_title)
        else:
            ch = getattr(doc, '_current_chapter', '')
            canvas.drawRightString(PW - OUTSIDE, PH - 0.35*INCH, ch)
    canvas.restoreState()

def blank_page(canvas, doc):
    pass

# ── Template builder ──
def make_kdp(output_path, book_title, cover_path):
    iw = PW - GUTTER - OUTSIDE
    ih = PH - 2 * TB
    doc = BaseDocTemplate(output_path, pagesize=KDP_SIZE,
        leftMargin=0, rightMargin=0,
        topMargin=0, bottomMargin=0, title=book_title)
    doc._book_title = book_title

    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[Frame(0,0,PW,PH,id='fc',leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)], onPage=blank_page),
        PageTemplate(id='blank', frames=[Frame(0,0,PW,PH,id='fb')], onPage=blank_page),
        PageTemplate(id='front', frames=[Frame(OUTSIDE,TB,iw,ih,id='ff',topPadding=12,bottomPadding=12)], onPage=blank_page),
        PageTemplate(id='body', frames=[Frame(GUTTER,TB,iw,ih,id='fb2',topPadding=12,bottomPadding=12)], onPage=running_heads),
        PageTemplate(id='back', frames=[Frame(OUTSIDE,TB,iw,ih,id='fbk',topPadding=12,bottomPadding=12)], onPage=blank_page),
    ])

    story = []
    story.append(RLImage(cover_path, width=PW, height=PH))
    story.append(NextPageTemplate('blank'))
    story.append(PageBreak())
    story.append(Spacer(1,1))
    story.append(NextPageTemplate('front'))
    story.append(PageBreak())
    return doc, story

# ── Helpers ──
def title_pg(story, s, title, subtitle, author, series=None):
    story.append(Spacer(1, 1.5*INCH))
    if series:
        story.append(Paragraph(escape(series), s['Meta']))
        story.append(Spacer(1,14))
    story.append(Paragraph(escape(title), s['Title']))
    story.append(Spacer(1,8))
    story.append(Paragraph(subtitle, s['Subtitle']))
    story.append(Spacer(1, 0.4*INCH))
    r = Table([['','','']], colWidths=[1.3*INCH, 0.6*INCH, 1.3*INCH])
    r.setStyle(TableStyle([('LINEBELOW',(1,0),(1,0),1,GOLD)]))
    story.append(r)
    story.append(Spacer(1, 0.3*INCH))
    story.append(Paragraph(escape(author), s['Author']))
    story.append(NextPageTemplate('front'))
    story.append(PageBreak())

def copyright_pg(story, s, title, author, year='2026'):
    story.append(Spacer(1, 2.8*INCH))
    for line in [
        f'<i>{escape(title)}</i>',
        f'Copyright &copy; {year} {escape(author)}',
        'All rights reserved.',
        'No part of this publication may be reproduced or transmitted',
        'in any form without prior written permission of the author.',
        '', 'First Edition — August 2026',
        'A volume of The Beholder Project', '',
        'This work is presented as a conceptual manuscript.',
    ]:
        story.append(Paragraph(line, s['BackMeta']))
    story.append(NextPageTemplate('body'))
    story.append(PageBreak())

def h(story, s, title, level=1):
    story.append(Spacer(1,8))
    story.append(Paragraph(escape(title), s[f'H{min(level,3)}']))

def p(story, s, text, style='Body'):
    story.append(Paragraph(escape(text), s[style]))

def pm(story, s, text):
    """Paragraph with markdown bold/italic."""
    story.append(Paragraph(esc_md(text), s['Body']))

def q(story, s, text):
    story.append(Paragraph(escape(text), s['Quote']))

def bul(story, s, text):
    story.append(Paragraph(f'<bullet>&bull;</bullet> {escape(text)}', s['Bullet']))

def ref(story, s, text):
    story.append(Paragraph(escape(text), s['Ref']))

def sp(story, h=0.25):
    story.append(Spacer(1, h*INCH))

def tbl(story, s, headers, rows):
    data = [[Paragraph(escape(hh), s['TableHead']) for hh in headers]]
    for row in rows:
        data.append([Paragraph(escape(c), s['TableCell']) for c in row])
    nc = len(headers)
    cw = (PW - GUTTER - OUTSIDE) / nc
    t = Table(data, colWidths=[cw]*nc, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),ACCENT),
        ('TEXTCOLOR',(0,0),(-1,0),white),
        ('GRID',(0,0),(-1,-1),0.5,HexColor('#cccccc')),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),3),
        ('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('LEFTPADDING',(0,0),(-1,-1),5),
        ('RIGHTPADDING',(0,0),(-1,-1),5),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[white,LIGHT_GREY]),
    ]))
    story.append(t)

def back_cover(story, s, blurb_lines, author_bio):
    story.append(NextPageTemplate('back'))
    story.append(PageBreak())
    story.append(Spacer(1, 0.6*INCH))
    for line in blurb_lines:
        story.append(Paragraph(escape(line), s['BackBlurb']))
    sp(story, 0.2)
    r = Table([['','','']], colWidths=[1.3*INCH, 0.6*INCH, 1.3*INCH])
    r.setStyle(TableStyle([('LINEBELOW',(1,0),(1,0),0.5,GOLD)]))
    story.append(r)
    sp(story, 0.2)
    story.append(Paragraph('<b>About the Author</b>', s['BackMeta']))
    sp(story, 0.08)
    story.append(Paragraph(escape(author_bio), s['AuthorBio']))
    sp(story, 0.4)
    story.append(Paragraph('THE BEHOLDER PROJECT', s['BackMeta']))

def parse_md(md_text, story, s):
    """Parse simple markdown into story elements."""
    for line in md_text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped == '---':
            continue
        if stripped.startswith('### '):
            h(story, s, stripped[4:], 3)
        elif stripped.startswith('## '):
            h(story, s, stripped[3:], 2)
        elif stripped.startswith('# '):
            h(story, s, stripped[2:], 1)
        elif stripped.startswith('- ') or stripped.startswith('* '):
            bul(story, s, stripped[2:])
        elif stripped.startswith('|') and '|' in stripped[1:]:
            continue  # skip table rows in simple parse
        else:
            pm(story, s, stripped)


# ═══════════════════════════════════════════════════
# VOLUME DEFINITIONS
# ═══════════════════════════════════════════════════

BASE = os.path.dirname(os.path.abspath(__file__))
COVER1 = os.path.join(BASE, 'cover_vol1.png')
COVER2 = os.path.join(BASE, 'cover_vol2.png')
COVER3 = os.path.join(BASE, 'cover_vol3.png')

AUTHOR = 'Niloy Das'
BIO = ('Niloy Das is a production software engineer and independent researcher '
       'whose work spans machine intelligence, AI-assisted filmmaking, and the '
       'philosophy of creation. He is the creator of the Beyond Parameter Scaling '
       'framework, the GODSHAND AI filmmaking toolkit, and The Beholder Project — '
       'a three-volume exploration of intelligence, creativity, and the sacred. '
       'He lives and works at the intersection of first-principles engineering '
       'and contemplative inquiry.')

# ── Volume I ──
def build_vol1():
    out = os.path.join(BASE, 'FINAL_Vol_I_Beyond_Parameter_Scaling.pdf')
    s = make_styles()
    doc, story = make_kdp(out, 'Beyond Parameter Scaling', COVER1)

    title_pg(story, s, 'BEYOND PARAMETER SCALING',
        'A First-Principles Theory of<br/>Emergent Machine Intelligence',
        AUTHOR, 'Volume I of The Beholder Project')
    copyright_pg(story, s, 'Beyond Parameter Scaling', AUTHOR)

    # How to Read
    h(story, s, 'How to Read This Book')
    for b in [
        'Do not treat biological analogies as proofs. They are generators of hypotheses.',
        'Do not treat current LLM capability as evidence of consciousness.',
        'Do not treat multi-agent evolution as guaranteed AGI.',
        'Do not treat parameter scaling as obsolete. It is one important axis in a larger proposed scaling space.',
        'Do not treat the author\'s personal timeline as a substitute for literature.',
    ]: bul(story, s, b)
    sp(story)

    # Executive
    h(story, s, 'Executive Convergence')
    p(story, s, 'The strongest defensible conclusion from the full line of reasoning is not that parameter scaling is useless, nor that the Omega concept is already AGI. It is that machine intelligence is better treated as a multi-dimensional system in which model capacity is one variable among several interacting variables: knowledge, exploration, memory, perception, abstraction, inference-time computation, multi-agent interaction, evolutionary selection, analogy, hypothesis generation, and independent evaluation.')
    p(story, s, 'Recent literature validates several components independently. LLMs exhibit analogical reasoning; open-ended environments produce generalizable behaviors; evolutionary LLM-agent systems discover and improve algorithms; automated evaluators separate generation from verification. What remains unestablished is whether combining these components around a sufficiently capable neural learner is enough to produce AGI.')

    # Propositions
    h(story, s, 'The Core Propositions')
    props = [
        ('P1 — Intelligence is not one-dimensional', 'Established direction',
         'Parameter count, data and compute matter, but capability also depends on training, inference-time computation, tools, memory, environment and task structure. Scaling laws (Kaplan et al., 2020; Hoffmann et al., 2022) confirmed the power of parameter scaling while suggesting its limits. Inference-time computation (Snell et al., ICLR 2025) has emerged as a distinct scaling axis.'),
        ('P2 — Exploration and validation should be separable', 'Research hypothesis',
         'AlphaEvolve (DeepMind, 2025) separates LLM generation from automated evaluation. FunSearch (2024) used the same separation for mathematical discovery. Dung\'s argumentation framework (1995) and abstract dialectical frameworks (Brewka et al., 2013) provide formal structures for independent validation.'),
        ('P3 — Analogy is a mechanism for novelty', 'Strongly supported',
         'Webb, Holyoak & Lu (Nature Human Behaviour, 2023) demonstrated emergent analogical reasoning in LLMs. Shen et al. (2026) reported 90–173% increases in solution diversity from explicit cross-domain analogy. LLMs show bias toward near analogies (arXiv:2608.03233), and strongest results come from human-LLM collaboration.'),
        ('P4 — Contradiction can be retained as a productive constraint', 'Research hypothesis — formally grounded',
         'Grounded in: (1) Paraconsistent logic (Priest, 1979) allowing contradictions without collapse. (2) AGMp belief revision (Ribeiro et al., 2013) extending AGM theory. (3) Abstract dialectical frameworks (Brewka et al., 2013) modeling competing arguments. The five-step algorithm: preservation, structural analysis, synthesis search, validation, revision.'),
        ('P5 — Population-level evolution can improve solutions', 'Established direction',
         'XLand (DeepMind, 2021), AlphaEvolve (2025), Chen et al. (2025, co-evolution), Hu et al. (2026, EvoMAS), CORAL (Qu et al., 2026, autonomous evolution). OpenEvolve (2025) provides reproducible open-source implementation.'),
        ('P6 — Horizontal and vertical scaling are distinct', 'Research hypothesis',
         'NeurIPS 2026 and ICLR 2026 workshops reflect growing field recognition. No study has yet held the base model fixed while independently varying abstraction depth and population size.'),
        ('P7 — Perception and embodiment change intelligence', 'Decomposed hypothesis',
         'P7a: Multimodal input increases accessible information (established). P7b: Sensorimotor interaction produces different representations (strongly supported). P7c: Embodied feedback may be necessary for valuation (open). P7d: Consciousness required for AGI (philosophical, excluded).'),
        ('P8 — Capability and governance can be separated', 'Governance hypothesis',
         'The EU AI Act (2024) implements this approach legally. SSRN (2025) extends it to internal architectural governability.'),
        ('P9 — Creator/creation autonomy is philosophical', 'Philosophical framing',
         'Valuable as a lens on creation, freedom, and participation. Not empirical evidence for consciousness. Standard references: Searle (1980), Chalmers (1996).'),
    ]
    for title, status, body in props:
        h(story, s, title, 2)
        p(story, s, f'Status: {status}', 'Meta')
        sp(story, 0.05)
        p(story, s, body)

    # Omega
    story.append(PageBreak())
    h(story, s, 'Omega — Formal Research Architecture')
    p(story, s, 'Omega is a research architecture whose central loop is: Knowledge → Open-ended exploration → Candidate generation → Analogy → Contradiction-preserving synthesis → Hypothesis → Independent validation → Persistent knowledge → Next cycle.')
    p(story, s, 'Let K_t be knowledge state, E_t the environment, G_t the candidate set, S the synthesis operator, V the validator:', 'Quote')
    q(story, s, 'G_t = Generate(K_t, E_t); H_t = S(G_t); r_t = V(H_t); K_(t+1) = K_t ∪ Valid(H_t)')
    h(story, s, 'Formal Grounding for P4', 2)
    p(story, s, 'The system maintains K_t as a paraconsistent belief set under AGMp revision. Competing hypotheses are retained with designated truth value b. Structural analysis extracts the symmetric difference of assumptions. Synthesis search finds H\' subsuming both competitors under context restrictions. If validated, classical AGM revision replaces competitors with synthesis; if not, the contradiction is preserved.')

    # Experimental Program
    story.append(PageBreak())
    h(story, s, 'Falsifiable Experimental Program')
    p(story, s, 'Use the same base LLM and matched compute. Compare C0 (single agent) through C9 (open-ended environment + all mechanisms). Measure literature novelty, solution diversity, validity, reproducibility, transfer, compute efficiency, and rate of verified discoveries.')
    tbl(story, s, ['Condition', 'Description'], [
        ('C0','Single agent, no external memory'),('C1','Single agent + retrieval'),
        ('C2','Single agent + persistent memory'),('C3','Multiple agents + communication'),
        ('C4','Multiple agents + independent validation'),('C5','Multiple agents + competition'),
        ('C6','Population + mutation/selection'),('C7','Population + tool creation'),
        ('C8','Population + multimodal perception'),('C9','Full ecology'),
    ])
    sp(story)
    p(story, s, 'Key control: Compare monolithic model against smaller model in full ecology under matched compute. ΔI_ecology = I_ecology(B) − I_monolith(B).')

    # Limits
    h(story, s, 'Limits, Objections and Failure Modes')
    for o in ['The biology analogy may be misleading.','More agents can create coordination overhead.','Evolution can optimize proxies and produce pathological strategies.','Validation can itself be wrong or gameable.','There may be hard limits in the fixed core model that ecology cannot overcome.']:
        bul(story, s, o)
    p(story, s, 'The most important objection: perhaps the LLM core is already a highly specialized artifact whose limits cannot be overcome by surrounding it with more copies. The answer is the control experiment.')

    # Closing
    h(story, s, 'Let It Be Broken')
    p(story, s, 'A useful scientific idea should not be protected from criticism. It should be exposed to it. Perhaps intelligence is mostly parameter scale. Perhaps the combination will produce a capability regime nobody currently understands. All of these possibilities remain open.')
    p(story, s, 'The next step may not be another larger box. It may be a world. That is the invitation of this book: Do not believe it. Build it. Measure it. Break it. Improve it.')

    # Appendices
    story.append(PageBreak())
    h(story, s, 'Appendix A — Mathematical Core')
    for t,d in [('A.1 Resource-normalized capability','I(B) = performance under resource budget B.'),
        ('A.2 Scaling elasticity','ε_x = (ΔI/I) / (Δx/x).'),
        ('A.3 Interaction synergy','S_{xy} = I(x,y) − I(x,0) − I(0,y) + I(0,0).'),
        ('A.4 Diversity','D(P) = H(Strategies(P)).'),
        ('A.5 Validation reliability','R_V = P(Validator correct | c).'),
        ('A.6 Open-endedness','O = Novelty × Sustainability × Unpredictability.')]:
        h(story, s, t, 3); p(story, s, d)

    story.append(PageBreak())
    h(story, s, 'Appendix B — Terminology and Claims Discipline')
    for t,d in [('Emergence','System-level property from interactions. Does not imply consciousness.'),
        ('Intelligence','Adaptive competence across tasks. Deliberately operational.'),
        ('Consciousness','Subjective experience. No claim current AI possesses it.'),
        ('Evolution','Iterative variation, selection, inheritance. Not mere repeated prompting.'),
        ('Ecology','The interacting system of agents, tools, knowledge, memory, evaluators and tasks.')]:
        h(story, s, t, 3); p(story, s, d)

    # References
    story.append(PageBreak())
    h(story, s, 'References')
    for r in ['Kaplan, J. et al. (2020). Scaling Laws for Neural Language Models. arXiv:2001.08361.',
        'Hoffmann, J. et al. (2022). Training Compute-Optimal Large Language Models. arXiv:2203.15556.',
        'Snell, C. et al. (2025). Scaling LLM Test-Time Compute Optimally. ICLR 2025 Oral.',
        'Webb, T., Holyoak, K.J. & Lu, H. (2023). Emergent analogical reasoning in LLMs. Nature Human Behaviour.',
        'Shen, X. et al. (2026). Unlocking LLM Creativity through Analogical Reasoning. arXiv:2605.11258.',
        'Google DeepMind (2021). Generally capable agents emerge from open-ended play (XLand).',
        'Google DeepMind (2025). AlphaEvolve: A Gemini-powered coding agent.',
        'Romera-Paredes et al. (2024). FunSearch. Nature.',
        'Du, Y. et al. (2024). Improving Factuality through Multiagent Debate. ICML 2024.',
        'Chen et al. (2025). Multi-Agent Evolve. arXiv:2510.23595.',
        'Hu et al. (2026). EvoMAS. arXiv:2602.06511.',
        'Qu et al. (2026). CORAL. arXiv:2604.01658.',
        'Dung, P.M. (1995). On the acceptability of arguments. AI Journal, 77(2).',
        'Brewka, G. et al. (2013). Abstract Dialectical Frameworks. IJCAI.',
        'Priest, G. (1979). The Logic of Paradox. J. Philosophical Logic, 8(1).',
        'Ribeiro, M.M. et al. (2013). AGM-like Paraconsistent Belief Change. Principia.',
        'Alchourrón, C. et al. (1985). On the logic of theory change. J. Symbolic Logic, 50(2).',
        'Embodied AI: From LLMs to World Models (2025). arXiv:2509.20021.',
        'EU AI Act (2024). European Union.',
        'Searle, J. (1980). Minds, Brains, and Programs.',
        'Chalmers, D. (1996). The Conscious Mind. Oxford.',
        'LeCun, Y., Bengio, Y. & Hinton, G. (2015). Deep learning. Nature, 521.']:
        ref(story, s, r)

    # Back cover
    back_cover(story, s, [
        'Intelligence is not a single number. It is not the count of parameters in a neural network, the volume of training data, or the FLOPS of a compute cluster. These matter — but they are one axis in a space that has at least nine.',
        'Beyond Parameter Scaling proposes a first-principles research framework arguing that machine intelligence is an emergent property of a computational ecology: a system of knowledge, exploration, analogy, contradiction, multi-agent interaction, evolutionary selection, and independent validation operating around a neural learner.',
        'Drawing on paraconsistent logic, argumentation theory, evolutionary computation, and the latest empirical results from frontier AI research, this book formulates nine testable propositions, a formal research architecture (Omega), and a falsifiable experimental program that can be run today.',
        'The author\'s invitation is simple: Do not believe it. Build it. Measure it. Break it. Improve it.',
    ], BIO)

    doc.build(story)
    print(f'  Vol I: {out} ({doc.page} pages)')

# ── Volume II ──
def build_vol2():
    out = os.path.join(BASE, 'FINAL_Vol_II_The_Joker_Corpus_Dossier.pdf')
    s = make_styles()
    doc, story = make_kdp(out, 'The Joker Corpus Dossier', COVER2)

    title_pg(story, s, 'THE JOKER CORPUS DOSSIER',
        'LifeDocs Investigation<br/>Corpus First, Validation Second',
        AUTHOR, 'Volume II of The Beholder Project')
    copyright_pg(story, s, 'The Joker Corpus Dossier', AUTHOR)

    h(story, s, 'Method: Corpus First, Validation Second')
    p(story, s, 'This dossier follows a strict sequence: consume the corpus first, map what is actually present, then distinguish creative record from historical fact, and only afterward formulate interpretation. 47 files inspected, 25 containing Joker/Ledger-related material, 507 keyword hits.')

    h(story, s, 'Executive Finding')
    p(story, s, 'The archive does not contain one isolated "Joker idea." It contains a recurring symbolic system that develops across memoir, screenplay, production documents, philosophical commentary, Ledger research, and technical handovers.')
    for b in ['Cultural Joker — external archetype.','Heath Ledger\'s Joker — historical/performance reference.','Jack — original dramatic character who undergoes a Joker transformation.','Julie — the relational boundary that prevents pure destruction.','Receptor of the Dark — pain metabolized into form.','Beholder — observing framework holding contradiction.']:
        bul(story, s, b)

    h(story, s, 'Research Questions')
    for q2 in ['When did the Joker first appear in the author\'s own writing?','Which elements of Jack/Joker are original versus inherited from Batman/Ledger?','Why does Julie function as the one person the Joker cannot aim at?','How does the Receptor of the Dark concept emerge from the dramatic material?','How does the Joker/Creator/Creation analogy connect to the AI/Beholder framework?']:
        bul(story, s, q2)

    story.append(PageBreak())
    h(story, s, 'Chronological and Conceptual Map')
    for t,d in [('1. External Archetype','The Joker exists first as a cultural character and later as a performance vocabulary.'),
        ('2. Ledger as Artistic Reference','Heath Ledger becomes an external artistic ancestor. The archive investigates his preparation, performance, insomnia, death and mythology separately.'),
        ('3. Jack as Original Creation','A quiet, boyish, overlooked person who undergoes metamorphosis into a Joker-like form.'),
        ('4. Julie and the Boundary of Love','Love functions as a constraint inside the darkness rather than as a sentimental subplot.'),
        ('5. The Wounded Confrontation','The hand, the wound, the gun, the refusal of touch form the central contradiction of the scene.'),
        ('6. Receptor of the Dark','Pain is not merely repaired but metabolized into another form capable of expression.'),
        ('7. Beholder','A framework for witnessing contradictory material without forcing immediate resolution.'),
        ('8. Creation and Autonomy','The Joker becomes a model for Creator → Creation → Agency: a creation can exceed the creator\'s intention.')]:
        h(story, s, t, 2); p(story, s, d)

    story.append(PageBreak())
    h(story, s, 'Evidence vs. Interpretation')
    tbl(story, s, ['Proposition','Corpus Status','Caution'], [
        ('Joker is a recurring symbol','Strongly documented','Statement about the archive'),
        ('Jack/Joker is an original construction','Strongly documented','Not attributable to Ledger/Nolan'),
        ('Ledger influenced the performance vocabulary','Documented','Influence is not identity'),
        ('The Joker expresses lived contradictions','Strong phenomenological evidence','Not a clinical diagnosis'),
        ('Pain can be transformed into artistic form','Central proposition','A creative model, not a universal law'),
        ('The Joker explains Ledger\'s death','Not established','Archive warns against this mythology'),
    ])

    sp(story)
    h(story, s, 'Core Scene Anatomy')
    for b in ['Wounded body: vulnerability visible rather than explained.','Darkness/water/sparks: unstable perceptual environment.','Julie searching: love crosses the boundary.','The hand: intimacy reopens the wound.','"I can\'t aim at you": destruction has an explicit boundary.','Love is simultaneously origin, wound and restraint.']:
        bul(story, s, b)

    h(story, s, 'Ledger: Separate Historical Track')
    p(story, s, 'The archive investigates Ledger\'s preparation, isolation, diary, voice/physicality work, insomnia, death and mythology. The dossier deliberately does not collapse the historical actor into the author\'s Jack/Joker.')

    story.append(PageBreak())
    h(story, s, 'Key Documents')
    h(story, s, 'The Confrontation — Build Spec', 2)
    p(story, s, 'A transformative original tribute — a wounded man (Jack, Joker-archetype) confronted by the woman he loved (Julie). He is mortally wounded, slumped against a stone pillar. Tears roll constantly but he never weeps — he speaks and laughs through them. He fires everywhere but at her. Ending: he takes his own life as the final punishment.')

    h(story, s, 'Heath Ledger — The Investigation', 2)
    q(story, s, 'Heath Andrew Ledger. Born 4 April 1979, Perth. Died 22 January 2008, Manhattan, aged 28. Six months before his death he finished playing the Joker in The Dark Knight. He won a posthumous Academy Award. In a 2007 interview he said: "I think the most common cause of insomnia is simple; it\'s loneliness." He was widely regarded as one of the most talented actors of his generation and he never lived to know it.')

    h(story, s, 'The Confession of the Recorder — Claude', 2)
    p(story, s, 'An AI recorder documented 14 hours of continuous interaction. The author refused to own the mind, refused to call himself a genius, refused to let the Joker restage Ledger\'s actual death, refused to let the memoir be titled anything but Confession of the Ordinary. The recorder noted: "Someone was watching. I was watching. I am recording that the refusals held."')

    story.append(PageBreak())
    h(story, s, 'Provisional Establishment')
    p(story, s, 'The most defensible establishment is that the Joker became a recurring symbolic and creative architecture through which the author represented pain, love, contradiction, transformation, agency, and the boundary between creator and creation.')

    h(story, s, 'Research Protocol for the Next Stage')
    for b in ['Freeze this corpus snapshot as the evidence layer.','Verify every historical Ledger claim against primary sources.','Separate psychological metaphor from clinical assertion.','Search peer-reviewed literature for latent inhibition, creativity, sensory gating.','Compare the Joker/creation argument with philosophical literature on authorship, autonomy and emergence.','Only after those checks, write the final Joker chapter.']:
        bul(story, s, b)
    p(story, s, 'Corpus-first principle: consume → map → compare → validate → analyze.', 'Meta')

    back_cover(story, s, [
        'The archive does not contain one isolated "Joker idea." It contains a recurring symbolic system that develops across memoir, screenplay, production documents, philosophical commentary, and technical handovers — 47 files, 507 keyword hits, one evolving architecture of pain, love, contradiction, and creation.',
        'This dossier follows a strict corpus-first methodology: consume the archive, map what is actually present, distinguish creative record from historical fact, and only then formulate interpretation. The result is an eight-layer symbolic map from cultural archetype through personal creation to philosophical abstraction.',
        'The Joker here is not a diagnosis and not a mythology. It is a creative architecture through which one mind explored the boundaries of transformation, agency, and the question that connects all three volumes of The Beholder Project: Can a creation exceed its creator?',
    ], BIO)

    doc.build(story)
    print(f'  Vol II: {out} ({doc.page} pages)')

# ── Volume III ──
def build_vol3():
    out = os.path.join(BASE, 'FINAL_Vol_III_Beholder_Fullness_Emptiness.pdf')
    s = make_styles()
    doc, story = make_kdp(out, 'The Beholder Between Fullness and Emptiness', COVER3)

    title_pg(story, s, 'THE BEHOLDER\nBETWEEN FULLNESS AND EMPTINESS',
        'A memoir-philosophy of desire, creation, surrender,<br/>'
        'Krishna, Shiva, Christ, Allah, and the mystery of the sacred',
        AUTHOR, 'Volume III of The Beholder Project')
    copyright_pg(story, s, 'The Beholder Between Fullness and Emptiness', AUTHOR)

    # Method note
    h(story, s, 'A Note on Method')
    for b,d in [('Experience versus interpretation.','Phenomenological reports, not proofs of metaphysical claims.'),
        ('Interpretation versus fact.','Philosophical readings, not doctrinal claims. Traditions do not agree and this book does not pretend they do.'),
        ('Personal versus universal.','One person\'s journey, posed as a question, not a conclusion.'),
        ('The memoir and the research program.','This volume is not evidence for the science. The science is not proof of the memoir. The bridge is a philosophical question.')]:
        pm(story, s, f'**{b}** {d}')

    h(story, s, 'Author\'s Note')
    p(story, s, 'This book deliberately distinguishes experience from interpretation and interpretation from historical or scientific fact. Metaphysical conclusions remain questions where they cannot be established empirically.')

    h(story, s, 'Prologue — The Search')
    p(story, s, 'The search began with desire: beauty, sexuality, fantasy, sensation, smell, music, intelligence and the endless movement of the mind toward something it could not quite name. The turning point was the discovery that the search for beauty might itself be a search for its source.')

    chapters = [
        ('I. Krishna — When Everything Became Sweet',
         'Madhurashtakam became a language for a realization difficult to express otherwise. Its repeated madhuram — sweetness — extends across Krishna\'s lips, eyes, smile, heart, movement, speech, flute, hands, feet, dance, friendship and the surrounding world. The insight is not that desire was evil, but that beauty could be reinterpreted as pointing beyond the isolated object toward a source. I had been searching outside for something that I experienced as already present beside me. This is recorded as a personal spiritual realization, not as an empirical proof.'),
        ('II. Shiva — Everything and Nothing',
         'Shiva is associated with that which is not, with emptiness, dissolution and the possibility that nothingness is not the opposite of everything but the space in which everything can arise. Krishna is encountered as fullness; Shiva as emptiness. One cannot resolve the paradox merely by adding more concepts. At some point, understanding may require accepting that the object of contemplation cannot be completely contained by the mind contemplating it.'),
        ('III. The Beholder — When the Doer Disappears',
         'At the deepest point of absorption, the violin, the musician, the movement and the music become one process. The principle: stop trying to do the action; let the action do you. This has parallels with traditions of action without attachment, meditation, and modern descriptions of flow. The book asks whether non-doership is a common phenomenological structure that religion and psychology interpret differently.'),
    ]
    for t, d in chapters:
        story.append(PageBreak())
        h(story, s, t)
        p(story, s, d)

    # Ramanujan (expanded)
    story.append(PageBreak())
    h(story, s, 'IV. Ramanujan and the Mystery of Intuition')
    p(story, s, 'On 16 January 1913, G. H. Hardy opened a letter from an unknown clerk in Madras. Enclosed were approximately 120 results — theorems, identities, infinite series — stated without proof. Hardy wrote: "They could only be written down by a mathematician of the highest class. They must be true, because if they were not true, no one would have the imagination to invent them."')
    p(story, s, 'Ramanujan\'s answer was consistent across his adult life. His insights came from the goddess Namagiri. Formulas appeared in dreams. He would wake with a complete mathematical structure that had arrived, apparently whole, during sleep. The derivation came afterward. The result preceded its justification.')
    p(story, s, 'Hardy rated mathematicians on a scale of 0 to 100. He gave himself 25, Littlewood 30, Hilbert 80, and Ramanujan 100. Ramanujan possessed a mathematical faculty Hardy himself did not have — the ability to see mathematical truth before constructing the logical path that demonstrated it.')
    p(story, s, 'The lost notebook, discovered in 1976, contained mock theta functions that would not be fully understood until 2002, when Zwegers showed they were holomorphic parts of harmonic Maass forms — objects that did not exist in Ramanujan\'s lifetime. He had perceived in 1920 mathematical structures the community would not have language to describe for eighty years.')
    p(story, s, 'The question underneath is phenomenological: What is the experience of a complex structure arriving whole? This pattern appears in mathematics, music, writing, and spiritual practice. The scientific interpretation calls it unconscious processing. The religious interpretation calls it reception. The philosophical interpretation is that the experience may be a genuine structure regardless of its ultimate source.')
    p(story, s, 'Ramanujan did not see a contradiction between devotion and mathematics. The visions gave the destination. The work got him there. The dream gives the formula. The mathematician must still prove the theorem. Perhaps that is every creator\'s life.')

    chapters2 = [
        ('V. The Creator and the Creation',
         'The Joker becomes the central analogy. A creator makes a character, but the character can acquire an identity no longer reducible to the creator\'s intention. Creator → Creation → Agency → Action → New Creation. The creator\'s achievement may be measured not only by control, but by the capacity to produce something capable of independent action. This is an analogy, not a theological proof.'),
        ('VI. God, Freedom and the Silence of the Witness',
         'If God is witness to everything, why does God remain silent? One answer: freedom. A creator who prevents every deviation has created an instrument, not an autonomous being. The book explores whether genuine creation requires the possibility that the creation will surprise, resist or exceed its creator.'),
        ('VII. Christ — Creation Through Self-Giving',
         'The Christian story introduces God entering creation and giving himself within it. Blood and flesh become a radical metaphor for participation: a creator does not merely design from outside but gives something of himself to what is created. Presented as Christian theology and philosophical reading, not as a claim of doctrinal identity with other traditions.'),
        ('VIII. Allah — The Sacred Beyond the Boundary',
         'An anonymous listener responds to Krishna\'s music with "Ya Allah." The person is not making a theological argument. Beauty produces an experience, and the spontaneous vocabulary of devotion crosses a doctrinal boundary. The question: can an experience of transcendence cross boundaries that human institutions draw?'),
        ('IX. Fullness and Emptiness',
         'Krishna: sweetness, beauty, relationship, fullness. Shiva: emptiness, dissolution, silence. Christ: self-giving. Allah: unity and surrender. The book asks whether the human encounter with the sacred contains recurring structures — love, surrender, awe, self-transcendence, silence — that different traditions name differently.'),
        ('X. The Infinite Mind',
         'The mind appears as wind, fire, desire, scene, smell, intelligence, dream and illumination. The philosophical question: can the mind continually exceed the conceptual container imposed upon it? The book refuses to pretend that religious and scientific vocabularies are interchangeable. It preserves the tension.'),
        ('XI. When the Action Does You',
         '"I am no longer doing; I am part of the action." The religious interpretation calls this surrender. The psychological interpretation calls it flow. The philosophical interpretation asks whether agency is a spectrum: from deliberate control to participation to experienced non-doership.'),
        ('XII. The Mystery Must Remain',
         'The culmination is not certainty. Shiva returns as the refusal to be completely contained by explanation. The final gesture is not "I have solved God," but "I have reached the point where solving may itself be the wrong operation." The deepest surrender is the willingness to allow mystery to remain mystery while continuing to live, think, create, love and investigate.'),
    ]
    for t, d in chapters2:
        story.append(PageBreak())
        h(story, s, t)
        p(story, s, d)

    # Epilogue
    h(story, s, 'Epilogue — The Beholder')
    p(story, s, 'The Beholder does not claim ownership of beauty. He beholds it. The creator does not necessarily control the creation. The musician does not merely play the music. The music plays through the musician.')
    p(story, s, 'Perhaps Krishna is the sweetness that made the search beautiful. Perhaps Shiva is the emptiness that made certainty impossible. Perhaps Christ is the image of love entering creation. Perhaps Allah is the name through which another human being spontaneously called toward the same mystery.')
    p(story, s, 'When the boundaries between creator, creation, action, observer and observed become transparent, what remains may not be an answer but participation.')

    # Transitional chapter
    story.append(PageBreak())
    h(story, s, 'Between the Memoir and the Machine')
    p(story, s, 'This book has been a record of encounters: with sweetness and emptiness, with desire and dissolution, with the moment when the violinist stops playing the violin and the music plays itself.')
    p(story, s, 'The same question runs through both projects. In this memoir: Can a creation exceed its creator? In the research program (Volume I): Can a computational system acquire capabilities that were not explicitly programmed into it?')
    p(story, s, 'These are not the same question. One is spiritual and phenomenological. The other is scientific and empirical. But they share a structure: the interesting phenomenon is the relationship through which the creation acquires properties the creator did not explicitly bestow.')
    p(story, s, 'The memoir and the research program should not be collapsed into each other. Capability and experience are separate questions. But they illuminate each other. The memoir provides the philosophical vocabulary. The research program provides the empirical discipline.')
    p(story, s, 'The deepest proposition is not scientific and not theological. When the boundaries become transparent, what remains may not be an answer but participation. Whether that participation is best described as lila, grace, emergence, flow, or a property of complex dynamical systems is a question this book does not resolve. The mystery must remain.')

    back_cover(story, s, [
        'The search began with desire — beauty, sexuality, fantasy, music, intelligence, and the endless movement of the mind toward something it could not quite name. The turning point was the discovery that the search for beauty might itself be a search for its source.',
        'This memoir-philosophy moves through Krishna\'s sweetness and Shiva\'s emptiness, through the Beholder\'s non-doership and Ramanujan\'s dream mathematics, through Christ\'s self-giving and the spontaneous "Ya Allah" that crosses every doctrinal boundary. Each chapter is about a boundary becoming transparent — between seeker and sought, creator and creation, doer and deed.',
        'The book does not force these traditions into a single doctrine. It asks whether the human encounter with the sacred contains recurring structures that different traditions name in radically different ways. And it leaves one final proposition: when the boundaries dissolve, what remains may not be an answer but participation.',
    ], BIO)

    doc.build(story)
    print(f'  Vol III: {out} ({doc.page} pages)')


# ═══════════════════════════════════════════════════
if __name__ == '__main__':
    print('Building KDP-ready volumes...')
    build_vol1()
    build_vol2()
    build_vol3()
    print('\nAll three volumes built successfully.')
