"""
Build Volume III — The Beholder Between Fullness and Emptiness
A memoir-philosophy of desire, creation, surrender, Krishna, Shiva, Christ, Allah,
and the mystery of the sacred
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from book_builder import *

def build():
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, 'Vol_III_The_Beholder_Fullness_Emptiness.pdf')
    styles = make_styles()
    doc = make_doc_template(out, 'The Beholder Between Fullness and Emptiness')

    story = []

    # ── Title Page ──
    title_page(story, styles,
        'THE BEHOLDER<br/>BETWEEN FULLNESS AND EMPTINESS',
        'A memoir-philosophy of desire, creation, surrender,<br/>'
        'Krishna, Shiva, Christ, Allah, and the mystery of the sacred',
        ['Version 3.0 — Converged Edition',
         'Volume III of The Beholder Project'],
        series=None)

    spacer(story, 1.5)
    para(story, styles, 'Volume III — The Beholder Between Fullness and Emptiness', 'Meta')
    para(story, styles, 'Converged Edition — August 2026', 'Meta')
    story.append(PageBreak())

    # ── Methodological Note (moved to front) ──
    chapter(story, styles, 'A Note on Method')
    note_paragraphs = [
        ('Experience versus interpretation.',
         'The experiences described here — moments of sweetness, dissolution, non-doership, surrender, '
         'illumination — are preserved as experiences. They are phenomenological reports: this is what '
         'happened, this is how it felt, this is what it seemed to mean at the time. They are not offered '
         'as proof of the metaphysical claims that various traditions attach to such experiences.'),
        ('Interpretation versus fact.',
         'Theological traditions — Vaishnavism, Shaivism, Christianity, Islam — are represented as '
         'traditions with their own internal logic, history and authority. Where this book interprets '
         'across traditions, it is offering a philosophical reading, not a historical or doctrinal claim. '
         'The traditions themselves do not agree with each other, and this book does not pretend that they do.'),
        ('Personal versus universal.',
         'The author\'s journey is one person\'s journey. The recurring question — whether the human '
         'encounter with the sacred contains structures that different traditions name differently — is '
         'posed as a question, not answered as a conclusion.'),
        ('Scientific claims.',
         'Where this book references scientific literature — on flow states, absorption, consciousness, '
         'emotion, neural mechanisms, mathematical creativity — those claims should be evaluated against '
         'peer-reviewed sources. The book uses science as a conversational partner, not as a validator '
         'of spiritual experience or a refutation of it.'),
        ('The memoir\'s relationship to the research program.',
         'This book is one volume of a three-volume project. Volume I (Beyond Parameter Scaling) contains '
         'the scientific research program on machine intelligence. Volume II (The Joker Corpus Dossier) '
         'contains the creative-archive evidence base. The memoir is not evidence for the science, and '
         'the science is not a proof of the memoir\'s spiritual claims.'),
    ]
    for bold_part, rest in note_paragraphs:
        text = f'<b>{escape(bold_part)}</b> {escape(rest)}'
        story.append(Paragraph(text, styles['Body']))
    story.append(PageBreak())

    # ── Author's Note ──
    chapter(story, styles, 'Author\'s Note')
    para(story, styles,
        'This book is a record of a lived spiritual and philosophical journey. It deliberately '
        'distinguishes experience from interpretation and interpretation from historical or scientific '
        'fact. The experiences described here are preserved as experiences; theological traditions are '
        'represented as traditions; metaphysical conclusions remain questions where they cannot be '
        'established empirically.')

    # ── Prologue ──
    chapter(story, styles, 'Prologue — The Search')
    para(story, styles,
        'The search began with desire: beauty, sexuality, fantasy, sensation, smell, music, intelligence '
        'and the endless movement of the mind toward something it could not quite name. The turning point '
        'was the discovery that the search for beauty might itself be a search for its source.')

    # ── Chapter I: Krishna ──
    chapter(story, styles, 'I. Krishna — When Everything Became Sweet')
    para(story, styles,
        'Madhurashtakam became a language for a realization that was difficult to express otherwise. '
        'Its repeated madhuram — sweetness — extends across Krishna\'s lips, eyes, smile, heart, '
        'movement, speech, flute, hands, feet, dance, friendship and the surrounding world. The spiritual '
        'insight recorded here is not that desire was simply evil, but that beauty could be reinterpreted '
        'as pointing beyond the isolated object toward a source.')
    para(story, styles,
        'The memoir\'s formulation is simple: I had been searching outside for something that I experienced '
        'as already present beside me. This is recorded as a personal spiritual realization, not as an '
        'empirical proof of Krishna\'s metaphysical existence.')

    # ── Chapter II: Shiva ──
    chapter(story, styles, 'II. Shiva — Everything and Nothing')
    para(story, styles,
        'Shiva introduces the opposite pole. In the yogic interpretation used in this book, Shiva is not '
        'merely a person among other persons. Shiva is associated with that which is not, with emptiness, '
        'dissolution and the possibility that nothingness is not the opposite of everything but the space '
        'in which everything can arise.')
    para(story, styles,
        'This creates the paradox at the heart of the book: Krishna is encountered as fullness and '
        'sweetness; Shiva as emptiness and mystery. One cannot resolve the paradox merely by adding '
        'more concepts. At some point, understanding may require accepting that the object of contemplation '
        'cannot be completely contained by the mind contemplating it.')
    para(story, styles,
        'The author\'s account of an intense period of Shiva study, including loss of consciousness and '
        'the belief that Shiva restored him, is preserved as lived experience. The supernatural interpretation '
        'is explicitly separated from what can be independently established.')

    # ── Chapter III: The Beholder ──
    chapter(story, styles, 'III. The Beholder — When the Doer Disappears')
    para(story, styles,
        'The Beholder memoir supplies the bridge between spirituality and creative action. The violinist '
        'is not merely a person manipulating an instrument. At the deepest point of absorption, the violin, '
        'the musician, the movement and the music become one process.')
    para(story, styles,
        'The principle is: stop trying to do the action; let the action do you. The mathematician no '
        'longer experiences every calculation as a deliberate act of control. The musician no longer '
        'stands outside the music. The creator becomes part of creation.')
    para(story, styles,
        'This has parallels with traditions of action without attachment, meditation and absorption, and '
        'with modern psychological descriptions of flow. The book does not claim that these scientific '
        'descriptions prove divine agency. Instead, it asks whether the experience of non-doership is a '
        'common phenomenological structure that religion and psychology interpret differently.')

    # ── Chapter IV: Ramanujan (EXPANDED) ──
    story.append(PageBreak())
    ramanujan_path = os.path.join(base, 'Supplement_E_Ramanujan_Expansion.md')
    if os.path.exists(ramanujan_path):
        with open(ramanujan_path, 'r', encoding='utf-8') as f:
            ram_md = f.read()
        # Find the main content after the header
        lines = ram_md.split('\n')
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('### IV. Ramanujan'):
                start = i
                break
        parse_markdown('\n'.join(lines[start:]), story, styles)
    else:
        chapter(story, styles, 'IV. Ramanujan and the Mystery of Intuition')
        para(story, styles,
            'Ramanujan\'s accounts of mathematical inspiration and his devotion to Namagiri provide a '
            'historical example of a creative person describing mathematical insight in religious and '
            'dream language. The recurring question is: why can a human being experience a complex '
            'structure as arriving whole, before conscious derivation has reconstructed it?')

    # ── Chapter V: Creator and Creation ──
    story.append(PageBreak())
    chapter(story, styles, 'V. The Creator and the Creation')
    para(story, styles,
        'The Joker becomes the central analogy. A creator makes a character, but the character can acquire '
        'an identity that is no longer reducible to the creator\'s immediate intention. The creation becomes '
        'an autonomous participant.')
    para(story, styles,
        'The philosophical progression is: Creator → Creation → Agency → Action → New Creation.')
    para(story, styles,
        'The creator\'s achievement may therefore be measured not only by control, but by the capacity '
        'to produce something capable of independent action and further creation. This is an analogy, '
        'not a theological proof.')

    # ── Chapter VI ──
    chapter(story, styles, 'VI. God, Freedom and the Silence of the Witness')
    para(story, styles,
        'The book records the question: if God is witness to everything, including desire, sexuality, '
        'fantasy and action, why does God remain silent? One answer explored here is freedom. A creator '
        'who prevents every deviation has created an instrument, not an autonomous being.')
    para(story, styles,
        'The religious traditions examined contain different accounts of divine omniscience, providence, '
        'freedom and responsibility. The book does not collapse those differences. It uses them to explore '
        'one philosophical problem: whether genuine creation requires the possibility that the creation '
        'will surprise, resist or exceed its creator.')

    # ── Chapter VII ──
    chapter(story, styles, 'VII. Christ — Creation Through Self-Giving')
    para(story, styles,
        'The Christian story introduces a different image of creation: God entering creation and giving '
        'himself within it. The image of blood and flesh becomes, in the author\'s interpretation, a '
        'radical metaphor for participation: a creator does not merely design from outside but gives '
        'something of himself to what is created.')
    para(story, styles,
        'This is presented as Christian theology and as the author\'s philosophical reading of it, not '
        'as a claim that Christianity and other traditions are doctrinally identical.')

    # ── Chapter VIII ──
    chapter(story, styles, 'VIII. Allah — The Sacred Beyond the Boundary')
    para(story, styles,
        'The book records an anonymous YouTube comment remembered by the author in response to Krishna\'s '
        'music, approximately: "Agar meri Krishna ki bansuri bajegi, ya Allah, saara jag jhoomega." The '
        'exact comment has not been independently recovered, so it is treated as a remembered anonymous '
        'response rather than a verified quotation.')
    para(story, styles,
        'Its philosophical importance lies elsewhere. The person does not appear to be making a theological '
        'argument. Krishna\'s flute produces an experience of beauty, and the spontaneous vocabulary of '
        'devotion is "Ya Allah." The event becomes an image of a human response to transcendence that '
        'precedes doctrinal comparison.')
    para(story, styles,
        'This does not establish that Islam and Vaishnavism are theologically identical. They are not. '
        'It illustrates instead a deeper question: can an experience of beauty, surrender or transcendence '
        'cross boundaries that human institutions and theological systems draw?')

    # ── Chapter IX ──
    chapter(story, styles, 'IX. Fullness and Emptiness')
    para(story, styles,
        'Krishna and Shiva now form two poles of the same spiritual investigation. Krishna: sweetness, '
        'beauty, relationship, fullness. Shiva: emptiness, dissolution, silence, mystery. Christ: '
        'self-giving. Allah: unity and surrender in Islamic theological language.')
    para(story, styles,
        'The book does not force these traditions into a single doctrine. Instead it asks whether the '
        'human encounter with the sacred contains recurring structures — love, surrender, awe, self-'
        'transcendence, compassion, silence and the dissolution of isolated ego — that different '
        'traditions name in radically different ways.')

    # ── Chapter X ──
    chapter(story, styles, 'X. The Infinite Mind')
    para(story, styles,
        'The mind appears in the memoir as wind, fire, desire, scene, smell, intelligence, dream and '
        'illumination. The philosophical question is whether the mind can continually exceed the conceptual '
        'container imposed upon it. Religious traditions often describe this in terms of spiritual expansion; '
        'neuroscience and psychology describe different aspects through attention, memory, emotion, '
        'prediction, absorption and altered states.')
    para(story, styles,
        'The book refuses to pretend that these vocabularies are interchangeable. It preserves the tension.')

    # ── Chapter XI ──
    chapter(story, styles, 'XI. When the Action Does You')
    para(story, styles,
        'The central practical principle becomes: "I am no longer doing; I am part of the action." In '
        'calculus, music, writing, research, devotion or creation, there may be states in which deliberate '
        'self-monitoring recedes and skilled action unfolds with unusual fluency.')
    para(story, styles,
        'The religious interpretation calls this surrender. The psychological interpretation may call it '
        'flow or absorption. The philosophical interpretation asks whether agency is a spectrum rather '
        'than a binary: from deliberate control to participation to experienced non-doership.')

    # ── Chapter XII ──
    chapter(story, styles, 'XII. The Mystery Must Remain')
    para(story, styles,
        'The culmination is not certainty. Shiva returns as the refusal to be completely contained by '
        'explanation. The final spiritual gesture is therefore not "I have solved God," but "I have '
        'reached the point where solving may itself be the wrong operation."')
    para(story, styles,
        'The deepest form of surrender in this book is not intellectual surrender to an authority. It '
        'is the willingness to allow mystery to remain mystery while continuing to live, think, create, '
        'love and investigate.')

    # ── Epilogue ──
    story.append(PageBreak())
    chapter(story, styles, 'Epilogue — The Beholder')
    para(story, styles,
        'The Beholder does not claim ownership of beauty. He beholds it. The creator does not necessarily '
        'control the creation. The creation may become a participant. The musician does not merely play '
        'the music. The music plays through the musician. The seeker does not necessarily find God as an '
        'object. The seeker may discover that the search itself has become the encounter.')
    para(story, styles,
        'Perhaps Krishna is the sweetness that made the search beautiful. Perhaps Shiva is the emptiness '
        'that made certainty impossible. Perhaps Christ is the image of love entering creation. Perhaps '
        'Allah is the name through which another human being spontaneously called toward the same mystery. '
        'The book does not decide these questions for the reader.')
    para(story, styles,
        'It leaves one final proposition: when the boundaries between creator, creation, action, observer '
        'and observed become transparent, what remains may not be an answer but participation.')

    # ── Transitional Chapter ──
    story.append(PageBreak())
    trans_path = os.path.join(base, 'Supplement_C_Book_III_Transitional_Chapter.md')
    if os.path.exists(trans_path):
        with open(trans_path, 'r', encoding='utf-8') as f:
            trans_md = f.read()
        lines = trans_md.split('\n')
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('### Between the Memoir'):
                start = i
                break
        # Add chapter heading
        chapter(story, styles, 'Between the Memoir and the Machine')
        parse_markdown('\n'.join(lines[start:]), story, styles)

    # Build
    doc.build(story)
    print(f'Volume III built: {out} ({doc.page} pages)')

if __name__ == '__main__':
    build()
