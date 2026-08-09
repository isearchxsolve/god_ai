"""Build the LinkedIn Monetization Playbook as a polished PDF."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from book_builder import *

def build():
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, 'LinkedIn_Monetization_Playbook.pdf')
    styles = make_styles()
    doc = make_doc_template(out, 'LinkedIn Monetization Playbook')

    story = []

    # ── Title Page ──
    title_page(story, styles,
        'LINKEDIN MONETIZATION<br/>PLAYBOOK',
        'For The Beholder Project',
        ['A 90-day launch plan for revenue<br/>from AI research, filmmaking tools, and philosophical thought leadership'],
        series=None)

    spacer(story, 1.5)
    para(story, styles, 'August 2026', 'Meta')
    para(story, styles, 'Companion document to The Beholder Project (Volumes I–III)', 'Meta')
    story.append(PageBreak())

    # ── Read the playbook markdown ──
    pb_path = os.path.join(base, 'LinkedIn_Monetization_Playbook.md')
    with open(pb_path, 'r', encoding='utf-8') as f:
        md = f.read()

    # Parse the markdown using our framework
    parse_markdown(md, story, styles)

    # Build
    doc.build(story)
    print(f'Playbook PDF built: {out} ({doc.page} pages)')

if __name__ == '__main__':
    build()
