"""
Shared book-building framework using ReportLab.
Provides typography styles, title page, TOC, and text parsing utilities.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    PageBreak, Table, TableStyle, NextPageTemplate, KeepTogether,
    ListFlowable, ListItem
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.lib import colors
import re, os

# --- Colours ---
DARK = HexColor('#1a1a2e')
ACCENT = HexColor('#16213e')
GOLD = HexColor('#b8860b')
LIGHT_GREY = HexColor('#f5f5f5')
MED_GREY = HexColor('#666666')

# --- Styles ---
def make_styles():
    base = getSampleStyleSheet()
    s = {}
    s['Body'] = ParagraphStyle(
        'Body', parent=base['Normal'],
        fontName='Times-Roman', fontSize=11, leading=15,
        alignment=TA_JUSTIFY, spaceAfter=8, firstLineIndent=0,
        textColor=HexColor('#222222')
    )
    s['BodyFirst'] = ParagraphStyle(
        'BodyFirst', parent=s['Body'],
        firstLineIndent=0, spaceBefore=4
    )
    s['Title'] = ParagraphStyle(
        'Title', parent=base['Title'],
        fontName='Helvetica-Bold', fontSize=28, leading=34,
        alignment=TA_CENTER, textColor=DARK, spaceAfter=6
    )
    s['Subtitle'] = ParagraphStyle(
        'Subtitle', parent=base['Normal'],
        fontName='Helvetica', fontSize=14, leading=18,
        alignment=TA_CENTER, textColor=MED_GREY, spaceAfter=4
    )
    s['Author'] = ParagraphStyle(
        'Author', parent=base['Normal'],
        fontName='Helvetica', fontSize=12, leading=16,
        alignment=TA_CENTER, textColor=MED_GREY, spaceBefore=20
    )
    s['H1'] = ParagraphStyle(
        'H1', parent=base['Heading1'],
        fontName='Helvetica-Bold', fontSize=20, leading=26,
        spaceBefore=28, spaceAfter=14, textColor=DARK,
        keepWithNext=1
    )
    s['H2'] = ParagraphStyle(
        'H2', parent=base['Heading2'],
        fontName='Helvetica-Bold', fontSize=15, leading=20,
        spaceBefore=20, spaceAfter=10, textColor=ACCENT,
        keepWithNext=1
    )
    s['H3'] = ParagraphStyle(
        'H3', parent=base['Heading3'],
        fontName='Helvetica-Bold', fontSize=12, leading=16,
        spaceBefore=14, spaceAfter=8, textColor=ACCENT,
        keepWithNext=1
    )
    s['Quote'] = ParagraphStyle(
        'Quote', parent=s['Body'],
        fontName='Times-Italic', fontSize=10.5, leading=14,
        leftIndent=30, rightIndent=30, alignment=TA_LEFT,
        textColor=MED_GREY, spaceBefore=8, spaceAfter=8
    )
    s['Ref'] = ParagraphStyle(
        'Ref', parent=s['Body'],
        fontName='Times-Roman', fontSize=9.5, leading=13,
        leftIndent=20, firstLineIndent=-20, spaceAfter=4
    )
    s['TOCH1'] = ParagraphStyle(
        'TOCH1', fontName='Helvetica-Bold', fontSize=12, leading=18,
        leftIndent=0, spaceBefore=6
    )
    s['TOCH2'] = ParagraphStyle(
        'TOCH2', fontName='Helvetica', fontSize=10.5, leading=15,
        leftIndent=20, spaceBefore=2
    )
    s['Footer'] = ParagraphStyle(
        'Footer', fontName='Helvetica', fontSize=8, leading=10,
        alignment=TA_CENTER, textColor=MED_GREY
    )
    s['Meta'] = ParagraphStyle(
        'Meta', parent=s['Body'],
        fontName='Helvetica', fontSize=9, leading=12,
        alignment=TA_CENTER, textColor=MED_GREY, spaceBefore=10
    )
    s['Bullet'] = ParagraphStyle(
        'Bullet', parent=s['Body'],
        bulletIndent=10, leftIndent=30, spaceAfter=4,
        bulletFontName='Helvetica', bulletFontSize=10
    )
    s['TableHead'] = ParagraphStyle(
        'TableHead', fontName='Helvetica-Bold', fontSize=9, leading=12,
        textColor=white
    )
    s['TableCell'] = ParagraphStyle(
        'TableCell', fontName='Times-Roman', fontSize=9, leading=12,
        textColor=HexColor('#222222')
    )
    return s

# --- Page Templates ---
def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(MED_GREY)
    # Footer: page number
    canvas.drawCentredString(A4[0]/2, 0.5*inch, f'{doc.page}')
    # Header: book title on verso, chapter on recto
    if hasattr(doc, '_book_title') and doc.page > 2:
        canvas.setFont('Helvetica', 7)
        if doc.page % 2 == 0:
            canvas.drawString(0.8*inch, A4[1] - 0.45*inch, doc._book_title)
        else:
            ch = getattr(doc, '_current_chapter', '')
            canvas.drawRightString(A4[0] - 0.8*inch, A4[1] - 0.45*inch, ch)
    canvas.restoreState()

def title_page_footer(canvas, doc):
    pass  # no header/footer on title page

def make_doc_template(output_path, book_title):
    """Create a BaseDocTemplate with title and body page templates."""
    page_w, page_h = A4
    margin = 0.85 * inch
    frame_body = Frame(margin, margin, page_w - 2*margin, page_h - 2*margin,
                       id='body', topPadding=12, bottomPadding=12)
    frame_title = Frame(margin, margin, page_w - 2*margin, page_h - 2*margin,
                        id='title')

    doc = BaseDocTemplate(
        output_path, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin,
        title=book_title
    )
    doc._book_title = book_title

    doc.addPageTemplates([
        PageTemplate(id='title', frames=[frame_title],
                     onPage=title_page_footer),
        PageTemplate(id='body', frames=[frame_body],
                     onPage=header_footer),
    ])
    return doc

# --- Content Helpers ---
def title_page(story, styles, title, subtitle, author_info, series=None):
    """Add a polished title page."""
    story.append(Spacer(1, 2*inch))
    if series:
        story.append(Paragraph(series, styles['Meta']))
        story.append(Spacer(1, 20))
    story.append(Paragraph(title, styles['Title']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(subtitle, styles['Subtitle']))
    story.append(Spacer(1, 0.6*inch))
    # Decorative rule
    rule_data = [['', '', '']]
    rule = Table(rule_data, colWidths=[2*inch, 1*inch, 2*inch])
    rule.setStyle(TableStyle([
        ('LINEBELOW', (1, 0), (1, 0), 1, GOLD),
    ]))
    story.append(rule)
    story.append(Spacer(1, 0.4*inch))
    if isinstance(author_info, list):
        for line in author_info:
            story.append(Paragraph(line, styles['Author']))
    else:
        story.append(Paragraph(author_info, styles['Author']))
    story.append(Spacer(1, 1.5*inch))
    story.append(Paragraph('August 2026', styles['Meta']))
    story.append(NextPageTemplate('body'))
    story.append(PageBreak())

def chapter(story, styles, title, level=1):
    """Add a chapter heading with appropriate level."""
    key = f'H{min(level, 3)}'
    story.append(Spacer(1, 10))
    story.append(Paragraph(escape(title), styles[key]))
    return title

def para(story, styles, text, style_name='Body'):
    """Add a paragraph."""
    story.append(Paragraph(escape(text), styles[style_name]))

def bullet(story, styles, text):
    """Add a bullet point."""
    story.append(Paragraph(
        f'<bullet>&bull;</bullet> {escape(text)}',
        styles['Bullet']
    ))

def quote(story, styles, text):
    """Add an indented quote."""
    story.append(Paragraph(escape(text), styles['Quote']))

def spacer(story, height=0.3):
    story.append(Spacer(1, height*inch))

def escape(text):
    """Escape XML special chars for ReportLab paragraphs."""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))

def ref_entry(story, styles, text):
    """Add a reference list entry with hanging indent."""
    story.append(Paragraph(escape(text), styles['Ref']))

def add_simple_table(story, styles, headers, rows):
    """Add a simple table with styled header."""
    data = [[Paragraph(escape(h), styles['TableHead']) for h in headers]]
    for row in rows:
        data.append([Paragraph(escape(c), styles['TableCell']) for c in row])
    ncols = len(headers)
    avail = A4[0] - 2 * 0.85 * inch
    col_w = avail / ncols
    t = Table(data, colWidths=[col_w]*ncols, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('BACKGROUND', (0, 1), (-1, -1), white),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_GREY]),
    ]))
    story.append(t)

# --- Markdown Parser ---
def parse_markdown(md_text, story, styles):
    """Parse simple markdown into story elements."""
    lines = md_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines and horizontal rules
        if not stripped or stripped == '---':
            i += 1
            continue

        # Headings
        if stripped.startswith('### '):
            chapter(story, styles, stripped[4:], level=3)
        elif stripped.startswith('## '):
            chapter(story, styles, stripped[3:], level=2)
        elif stripped.startswith('# '):
            chapter(story, styles, stripped[2:], level=1)
        # Bullet points
        elif stripped.startswith('- ') or stripped.startswith('* '):
            bullet(story, styles, stripped[2:])
        # Table detection (simple pipe tables)
        elif stripped.startswith('|') and '|' in stripped[1:]:
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                headers = [c.strip() for c in table_lines[0].split('|') if c.strip()]
                rows = []
                for tl in table_lines[2:]:  # skip header + separator
                    cells = [c.strip() for c in tl.split('|') if c.strip()]
                    if cells:
                        rows.append(cells)
                if headers:
                    add_simple_table(story, styles, headers, rows)
            continue  # i already advanced
        else:
            # Regular paragraph - collect continuation lines
            para_lines = [stripped]
            while (i + 1 < len(lines) and lines[i+1].strip()
                   and not lines[i+1].strip().startswith('#')
                   and not lines[i+1].strip().startswith('-')
                   and not lines[i+1].strip().startswith('*')
                   and not lines[i+1].strip().startswith('|')
                   and lines[i+1].strip() != '---'):
                i += 1
                para_lines.append(lines[i].strip())
            text = ' '.join(para_lines)
            # Detect bold-only paragraphs as meta text
            if text.startswith('**') and text.endswith('**'):
                para(story, styles, text.strip('*'), 'Meta')
            else:
                # Bold markers
                text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
                text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
                # Escape XML
                text = text.replace('&', '&amp;')
                text = re.sub(r'<(?!/?[bi]>)', '&lt;', text)
                story.append(Paragraph(text, styles['Body']))
        i += 1

def parse_text_as_book(text, story, styles, heading_patterns=None):
    """Parse plain extracted text into story, detecting headings by pattern."""
    if heading_patterns is None:
        heading_patterns = {
            'h1': [
                r'^BEYOND PARAMETER SCALING$',
                r'^BOOK [IVX]+$',
                r'^THE JOKER CORPUS DOSSIER$',
                r'^Original Version 1 Material$',
                r'^Archive',
                r'^Research and Source Discipline$',
            ],
            'h2': [
                r'^Executive Convergence$',
                r'^The Core Propositions$',
                r'^What the Literature',
                r'^Omega',
                r'^Falsifiable',
                r'^The Religious',
                r'^Final Establishment$',
                r'^Selected Literature',
                r'^Closing',
                r'^Appendix',
                r'^(P[0-9]+\s)',
                r'^Method$',
                r'^Executive finding$',
                r'^Corpus inventory$',
                r'^Chronological',
                r'^Core scene',
                r'^Evidence vs interpretation$',
                r'^Ledger:',
                r'^All [0-9]+ relevant',
                r'^Research questions',
                r'^Provisional establishment$',
                r'^Research protocol',
                r'^Author\'s Note$',
                r'^Prologue',
                r'^Epilogue',
                r'^(I{1,3}|IV|V|VI{0,3}|IX|X|XI{0,2}|XII)\.',
                r'^\d+\.\s+[A-Z]',
            ],
            'h3': [
                r'^What remains open$',
                r'^Analogical reasoning$',
                r'^Open-ended learning$',
                r'^Evolutionary',
                r'^Scientific synthesis$',
                r'^Contradiction \+ Analogy',
                r'^(A\.\d|B\.\d|C\.\d)',
                r'^\d+\.\d+\s',
            ]
        }

    lines = text.split('\n')
    buf = []

    def flush_buf():
        if buf:
            text = ' '.join(buf)
            text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(text, styles['Body']))
            buf.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_buf()
            continue

        is_heading = False
        for level, patterns in heading_patterns.items():
            for pat in patterns:
                if re.match(pat, stripped, re.IGNORECASE if level == 'h1' else 0):
                    flush_buf()
                    style_map = {'h1': 'H1', 'h2': 'H2', 'h3': 'H3'}
                    story.append(Paragraph(escape(stripped), styles[style_map[level]]))
                    is_heading = True
                    break
            if is_heading:
                break

        if not is_heading:
            buf.append(stripped)

    flush_buf()
