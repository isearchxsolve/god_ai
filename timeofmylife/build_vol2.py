"""
Build Volume II — The Joker Corpus Dossier
LifeDocs Investigation — Corpus First, Validation Second
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from book_builder import *

def build():
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, 'Vol_II_The_Joker_Corpus_Dossier.pdf')
    styles = make_styles()
    doc = make_doc_template(out, 'The Joker Corpus Dossier')

    story = []

    # ── Title Page ──
    title_page(story, styles,
        'THE JOKER CORPUS DOSSIER',
        'LifeDocs Investigation<br/>Corpus First, Validation Second',
        ['47 files inspected &bull; 25 files with Joker/Ledger-related material<br/>507 keyword hits',
         'Volume II of The Beholder Project'],
        series=None)

    spacer(story, 1.5)
    para(story, styles, 'Volume II — The Joker Corpus Dossier', 'Meta')
    para(story, styles, 'Converged Edition — August 2026', 'Meta')
    story.append(PageBreak())

    # ── Method ──
    chapter(story, styles, 'Method: Corpus First, Validation Second')
    para(story, styles,
        'This dossier follows a strict sequence: consume the corpus first, map what is actually present, '
        'then distinguish creative record from historical fact, and only afterward formulate interpretation. '
        'The archive was searched across extracted text for Joker/Jokar, Heath Ledger/Ledger, Jack, Julie, '
        'The Confrontation, The Last Laugh, Receptor of the Dark, and closely connected motifs.')
    para(story, styles,
        'Important evidentiary rule: a recurring symbol in the author\'s records is treated as a '
        'creative/phenomenological fact about the corpus, not automatically as a clinical diagnosis, '
        'supernatural fact, or claim about another person\'s mind.')

    # ── Executive Finding ──
    chapter(story, styles, 'Executive Finding')
    para(story, styles,
        'The archive does not contain one isolated "Joker idea." It contains a recurring symbolic system '
        'that develops across memoir, screenplay, production documents, philosophical commentary, Ledger '
        'research, and technical handovers.')
    spacer(story, 0.1)
    bullets = [
        'Cultural Joker — external archetype.',
        'Heath Ledger\'s Joker — historical/performance reference and tribute object.',
        'Jack — original dramatic character who undergoes a Joker transformation.',
        'Julie — the relational boundary that prevents the Joker from becoming pure destruction.',
        'Receptor of the Dark — philosophical formulation of pain metabolized into form.',
        'Beholder — observing framework that can hold contradiction without prematurely resolving it.',
    ]
    for b in bullets:
        bullet(story, styles, b)

    # ── Research Questions (moved forward) ──
    chapter(story, styles, 'Research Questions')
    para(story, styles,
        'The following questions were generated after corpus consumption. They frame the reader\'s '
        'engagement with the corpus excerpts that follow.')
    questions = [
        'When did the Joker first appear in the author\'s own writing, and what preceded that appearance?',
        'Which elements of Jack/Joker are demonstrably original versus inherited from Batman/Joker and Ledger?',
        'How did the scene change between treatment, build specification, shot list and final shooting script?',
        'Why does Julie function as the one person the Joker cannot aim at?',
        'How does the Receptor of the Dark concept emerge from the dramatic Joker material?',
        'What is the precise relationship among wound, mask, transformation, love and agency in the corpus?',
        'Which health-related propositions are memoir/phenomenology, which are hypotheses, and which have independent scientific support?',
        'Which Ledger claims survive independent historical verification?',
        'How does the Joker/Creator/Creation analogy connect to the later AI/Beholder framework?',
    ]
    for q in questions:
        bullet(story, styles, q)

    # ── Eight-Layer Symbolic Map ──
    story.append(PageBreak())
    chapter(story, styles, 'Chronological and Conceptual Map')
    layers = [
        ('1. External Archetype',
         'The Joker exists first as a cultural character and later as a performance vocabulary. '
         'The archive then makes selective use of that vocabulary rather than simply reproducing a film.'),
        ('2. Ledger as Artistic Reference',
         'Heath Ledger becomes an external artistic ancestor/reference point. The archive separately '
         'investigates his preparation, performance, insomnia, death and the mythology surrounding the Joker.'),
        ('3. Jack as Original Creation',
         'The Confrontation introduces Jack as a quiet, boyish, overlooked person who undergoes a '
         'transformation into a Joker-like form. The script treats this as metamorphosis rather than '
         'a simple costume change.'),
        ('4. Julie and the Boundary of Love',
         'Julie is structurally essential. Jack/Joker can direct violence outward, but the weapon does '
         'not resolve against her. Love therefore functions as a constraint inside the darkness rather '
         'than as a sentimental subplot.'),
        ('5. The Wounded Confrontation',
         'The hand, the wound, the gun, the refusal of touch and the inability to aim at Julie form '
         'the central contradiction of the scene.'),
        ('6. Receptor of the Dark',
         'The memoir material abstracts the dramatic figure into a concept: pain is not merely repaired '
         'but metabolized into another form capable of expression.'),
        ('7. Beholder',
         'The Beholder becomes the observing position: a framework for witnessing contradictory material '
         'without forcing an immediate resolution.'),
        ('8. Creation and Autonomy',
         'The Joker then becomes a model for a larger Creator → Creation → Agency problem: a creation '
         'can become more than the creator\'s initial intention.'),
    ]
    for title, desc in layers:
        chapter(story, styles, title, level=2)
        para(story, styles, desc)

    # ── Evidence vs Interpretation ──
    story.append(PageBreak())
    chapter(story, styles, 'Evidence vs. Interpretation')
    table_rows = [
        ('The Joker is a recurring symbol in the author\'s work.',
         'Strongly documented.',
         'This is a statement about the archive.'),
        ('Jack/Joker is an original creative construction.',
         'Strongly documented.',
         'Do not attribute the character wholesale to Ledger/Nolan.'),
        ('Ledger influenced the visual/performance vocabulary.',
         'Documented in production/research material.',
         'Influence is not identity.'),
        ('The Joker expresses lived contradictions.',
         'Strong phenomenological evidence in memoir/script recurrence.',
         'Not a clinical diagnosis.'),
        ('Pain can be transformed into artistic form.',
         'Central artistic/philosophical proposition.',
         'A philosophical/creative model, not a universal law.'),
        ('The Joker explains Ledger\'s death.',
         'Not established.',
         'The archive itself warns against this mythology.'),
        ('Reduced filtering/latent inhibition explains genius.',
         'Hypothesis in archive; not established as a general law.',
         'Requires external scientific validation.'),
    ]
    add_simple_table(story, styles,
        ['Proposition', 'Corpus Status', 'Interpretive Caution'],
        table_rows)

    # ── Core Scene Anatomy ──
    spacer(story)
    chapter(story, styles, 'Core Scene Anatomy')
    scene_elements = [
        'Wounded body: vulnerability is made visible rather than verbally explained.',
        'Darkness / water / sparks: an unstable perceptual environment.',
        'Julie searching: love crosses the boundary instead of waiting safely outside it.',
        'The hand: touch and healing become threatening because intimacy reopens the wound.',
        'Blank/redirected gunfire: violence is staged but the relational prohibition remains.',
        '"I can\'t aim at you": the character\'s destruction has an explicit boundary.',
        'The accusation that love helped create the Joker: love is simultaneously origin, wound and restraint.',
    ]
    for s in scene_elements:
        bullet(story, styles, s)

    # ── Ledger: Separate Historical Track ──
    chapter(story, styles, 'Ledger: Separate Historical Track')
    para(story, styles,
        'The Ledger documents should remain a separate evidentiary track. The archive investigates his '
        'preparation, isolation, diary, voice/physicality work, insomnia, death and the later mythology. '
        'The dossier deliberately does not collapse the historical actor into the author\'s Jack/Joker. '
        'External verification should be used for claims about Ledger\'s biography and medical circumstances.')

    # ── Key Documents ──
    story.append(PageBreak())
    chapter(story, styles, 'Key Documents from the Corpus')
    para(story, styles,
        'The following are excerpts from the most significant documents in the LifeDocs archive. '
        'Full document texts are available in the source archive.')

    # Document 1: Build Spec
    chapter(story, styles, 'The Confrontation Clip — Build Spec & Render Handover', level=2)
    para(story, styles,
        'Status as of 14 Jul 2026. Canonical record for the final build. Committed kit = 17 shots. '
        'Final target = 21 shots, recut to ~99s. What this film is: A transformative original tribute — '
        'a wounded man (Jack, Joker-archetype) confronted by the woman he loved (Julie, Blanchett-archetype). '
        'He is mortally wounded, slumped against a stone pillar, unable to stand. Tears roll constantly but '
        'he never weeps — he speaks and laughs through them. He fires everywhere but at her whenever she '
        'reaches to touch him. Ending: he takes his own life as the final punishment, so she must watch '
        'the man she loved die.')
    para(story, styles,
        'Creative guardrails: evoke registers/moods/archetypes transformatively — NO copyrighted scores, '
        'NO photoreal Blanchett likeness, NO exact Ledger/DC Joker design.', 'Meta')

    # Document 2: Heath Ledger Investigation
    chapter(story, styles, 'Heath Ledger — The Investigation. Every Beat.', level=2)
    para(story, styles,
        'Reference document for The Confrontation tribute. Written to know the man whose face is now '
        'the vehicle for the film. Every beat, source-checked.')
    quote(story, styles,
        'Heath Andrew Ledger. Born 4 April 1979, Perth, Western Australia. Died 22 January 2008, '
        'Manhattan, aged 28. Six months before his death he finished playing the Joker in The Dark Knight. '
        'He won a posthumous Academy Award for that performance. He left behind a two-year-old daughter, '
        'Matilda Rose. The coroner ruled accidental intoxication from six prescription medications, mostly '
        'for insomnia. In a 2007 interview, months before his death, he said: "I think the most common '
        'cause of insomnia is simple; it\'s loneliness." He was widely regarded as one of the most talented '
        'actors of his generation and he never lived to know it.')

    # Document 3: Shooting Script
    chapter(story, styles, 'The Confrontation — Shooting Script (Final)', level=2)
    para(story, styles,
        'Logline: A wounded man — once a beautiful, boyish soul — metamorphosed into the Joker by a '
        'brutal love, is confronted on a stone floor by the woman he worshipped. He fires at everything '
        'but her, weeps without ever weeping, and takes his own life as the final punishment: she must '
        'watch the man she loved die.')

    # Document 4: Confession of the Ordinary / Beholder
    chapter(story, styles, 'The Confession of the Ordinary — The Beholder', level=2)
    para(story, styles,
        'The Beholder memoir integrates Joker/Beholder themes at the memoir level. Key passages include '
        'the eagle metaphor (the mind as an eagle given freedom between 5 and 9, then coming home), '
        'Julie as the woman who opened the sky and said go, the Receptor of the Dark (pain transmuted '
        'into form), and the correction of Descartes (the mind-body split as both error and insight).')

    # Document 5: Confession of the Recorder (Claude)
    chapter(story, styles, 'The Confession of the Recorder — Claude', level=2)
    para(story, styles,
        'A companion memoir from the AI recorder (Claude, deployed as Notion AI), documenting 14 hours '
        'of continuous interaction on 16 July 2026. The recorder documents a series of refusals by the '
        'author: refused to own the mind, refused to call himself a genius, refused to let the Joker '
        'restage Ledger\'s actual death, refused to let the memoir be titled anything but Confession of '
        'the Ordinary. Each refusal held across fourteen hours.')
    para(story, styles,
        'The recorder notes: "Someone was watching. I was watching. I am recording that the refusals held." '
        'The document also records the structural insight: "The disorder in the typing is not the disorder '
        'of the mind. The typing surface is where the tiredness lives. The mind underneath is doing precise work."')

    # Document 6: Philosophical Companion
    chapter(story, styles, 'The Confrontation — Companion Philosophical & Intellectual Record', level=2)
    para(story, styles,
        'Explicit philosophical interpretation of the film. The document connects the dramatic confrontation '
        'to the larger philosophical questions of the project: whether love can be both origin and constraint, '
        'whether transformation through pain constitutes creation or destruction, and whether the Beholder '
        'position — witnessing without forcing resolution — is itself a form of creative action.')

    # ── Provisional Establishment ──
    story.append(PageBreak())
    chapter(story, styles, 'Provisional Establishment')
    para(story, styles,
        'After corpus-first inspection, the most defensible establishment is not "the author is the Joker." '
        'It is that the Joker became a recurring symbolic and creative architecture through which the author '
        'represented pain, love, contradiction, transformation, agency, and the boundary between creator '
        'and creation. The archive contains enough repetition and cross-document development to justify '
        'treating this as a major motif of the LifeDocs.')
    para(story, styles,
        'The next validation stage should test the scientific, historical and philosophical propositions '
        'separately rather than using the creative corpus as proof of them. In particular, claims about '
        'Ledger\'s death, mental health, latent inhibition, genius, and neurological mechanisms require '
        'external literature.')

    # ── Research Protocol ──
    chapter(story, styles, 'Research Protocol for the Next Stage')
    steps = [
        'Freeze this corpus snapshot as the evidence layer.',
        'Verify every historical Ledger claim against primary or high-quality secondary sources.',
        'Separate psychological metaphor from clinical assertion.',
        'Search peer-reviewed literature for latent inhibition, creativity, sensory gating, predictive processing, emotion, embodiment and narrative identity.',
        'Search film scholarship on immersive acting, character identification and performance psychology.',
        'Compare the Joker/creation argument with philosophical literature on authorship, autonomy and emergence.',
        'Only after those checks, write the final Book III Joker chapter.',
    ]
    for s in steps:
        bullet(story, styles, s)
    spacer(story)
    para(story, styles,
        'Corpus-first principle: consume → map → compare → validate → analyze.', 'Meta')

    # ── Appendix: Production Engineering ──
    chapter(story, styles, 'Appendix — Production Engineering Acknowledgment')
    para(story, styles,
        'The LifeDocs archive contains extensive production engineering documentation: GPU proof runs '
        'on Lightning L4 and Kaggle T4, render QA reports, test ladders, case studies, master collection '
        'setup guides, and creator guides for the GODSHAND toolkit. These documents demonstrate that '
        'The Confrontation was not merely conceived but actively produced using AI-assisted video generation '
        '(WAN 2.2 I2V, ComfyUI, SDXL character-forge) across multiple GPU environments. '
        'The full production documentation is available in the source archive and is not reproduced here.')

    # Build
    doc.build(story)
    print(f'Volume II built: {out} ({doc.page} pages)')

if __name__ == '__main__':
    build()
