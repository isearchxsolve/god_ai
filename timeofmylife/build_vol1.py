"""
Build Volume I — Beyond Parameter Scaling
A First-Principles Theory of Emergent Machine Intelligence
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from book_builder import *

def build():
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, 'Vol_I_Beyond_Parameter_Scaling.pdf')
    styles = make_styles()
    doc = make_doc_template(out, 'Beyond Parameter Scaling')

    story = []

    # ── Title Page ──
    title_page(story, styles,
        'BEYOND PARAMETER SCALING',
        'A First-Principles Theory of<br/>Emergent Machine Intelligence',
        ['Converged Propositions, Evidence Status,<br/>Mathematical Research Program, and Philosophical Extensions',
         'Volume I of The Beholder Project'],
        series=None)

    # ── Half Title / Imprint ──
    spacer(story, 1.5)
    para(story, styles, 'Volume I — Beyond Parameter Scaling', 'Meta')
    para(story, styles, 'Converged Edition — August 2026', 'Meta')
    spacer(story, 0.3)
    para(story, styles,
        'This work is presented as a conceptual research manuscript. '
        'It should be cited as a hypothesis to be tested, extended, or broken — '
        'not as a peer-reviewed scientific result. The scientific community is '
        'invited to reproduce, criticize, formalize, extend and falsify.', 'Meta')
    story.append(PageBreak())

    # ── How to Read This Book ──
    chapter(story, styles, 'How to Read This Book')
    for line in [
        'Do not treat biological analogies as proofs. They are generators of hypotheses.',
        'Do not treat current LLM capability as evidence of consciousness. Capability and experience are separate questions.',
        'Do not treat multi-agent evolution as guaranteed AGI. It is an experimentally supported mechanism for producing new capability in bounded settings.',
        'Do not treat parameter scaling as obsolete. It is one important axis in a larger proposed scaling space.',
        'Do not treat the author\'s personal timeline as a substitute for literature. It is a historical record of questions, not a scientific validation.',
    ]:
        bullet(story, styles, line)
    spacer(story)

    # ── Executive Convergence ──
    chapter(story, styles, 'Executive Convergence')
    para(story, styles,
        'The strongest defensible conclusion from the full line of reasoning is not that parameter scaling is useless, '
        'nor that the Omega concept is already AGI. It is that machine intelligence is better treated as a multi-dimensional '
        'system in which model capacity is one variable among several interacting variables: knowledge, exploration, memory, '
        'perception, abstraction, inference-time computation, multi-agent interaction, evolutionary selection, analogy, '
        'hypothesis generation, and independent evaluation.')
    para(story, styles,
        'Recent literature validates several components of this picture independently. LLMs exhibit analogical reasoning; '
        'open-ended environments can produce generalizable behaviors; evolutionary LLM-agent systems can discover and '
        'improve algorithms; and automated evaluators can separate generation from verification. What remains unestablished '
        'is whether combining these components around a sufficiently capable neural learner is enough to produce AGI.')

    # ── The Core Propositions ──
    chapter(story, styles, 'The Core Propositions')

    props = [
        ('P1 — Intelligence is not one-dimensional', 'Established direction',
         'Parameter count, data and compute matter, but capability also depends on training, inference-time computation, '
         'tools, memory, environment and task structure. Parameter count is therefore not a complete theory of intelligence. '
         'Scaling laws (Kaplan et al., 2020; Hoffmann et al., 2022) confirmed the power of parameter scaling while '
         'simultaneously suggesting its limits. Inference-time computation has emerged as a distinct scaling axis: '
         'Snell et al. (ICLR 2025) demonstrated that scaling test-time compute can be more effective than scaling '
         'model parameters for certain reasoning tasks.'),
        ('P2 — Exploration and validation should be separable', 'Research hypothesis',
         'A discovery system should be allowed to generate a broad candidate set before an independent evaluator '
         'aggressively filters it. AlphaEvolve (DeepMind, 2025) explicitly separates LLM-based code generation from '
         'automated evaluation. FunSearch (2024) used the same separation to discover new mathematical results. '
         'Dung\'s abstract argumentation framework (1995) and abstract dialectical frameworks (Brewka et al., 2013) '
         'provide formal structures for independent validation.'),
        ('P3 — Analogy is a mechanism for novelty', 'Strongly supported',
         'Webb, Holyoak & Lu (Nature Human Behaviour, 2023) demonstrated emergent analogical reasoning in LLMs. '
         'Shen, Druckmann & Zou (2026) reported that explicit cross-domain analogical reasoning increased solution '
         'diversity by 90-173%. However, LLMs show a bias toward near analogies (arXiv:2608.03233, 2026), and the '
         'strongest results come from human-LLM collaboration rather than autonomous analogy generation.'),
        ('P4 — Contradiction can be retained as a productive constraint', 'Research hypothesis — now formally grounded',
         'Instead of immediately resolving conflicting theories, a system can preserve competing hypotheses, identify '
         'their hidden assumptions, and search for a third synthesis. This is now formally grounded in three bodies of '
         'work: (1) Paraconsistent logic (Priest, 1979; da Costa, 1974), which allows systems to contain contradictions '
         'without collapse. (2) AGMp belief revision (Ribeiro et al., 2013), which extends AGM theory to allow '
         'revision that preserves contradictions. (3) Abstract dialectical frameworks (Brewka et al., 2013), which '
         'model competing arguments with general acceptance conditions. The integrated formal statement is: '
         'the system maintains K_t as a paraconsistent belief set under AGMp revision, preserving contradictions '
         'with designated truth value b, performing structural analysis of competing assumptions, and searching for '
         'a synthesis H\' that subsumes both competitors under context restrictions.'),
        ('P5 — Population-level evolution can improve solutions', 'Established direction',
         'XLand (DeepMind, 2021) trained agents across millions of tasks in a dynamically changing multiplayer '
         'environment. AlphaEvolve (DeepMind, 2025) combines LLMs, automated evaluators, and evolutionary selection. '
         'Chen et al. (2025) demonstrated multi-agent co-evolution. Hu et al. (2026, EvoMAS) showed evolutionary '
         'generation of multi-agent systems. CORAL (Qu et al., 2026) demonstrated autonomous multi-agent evolution '
         'for open-ended discovery.'),
        ('P6 — Horizontal and vertical scaling are distinct', 'Research hypothesis',
         'Increasing population/compute/model width and increasing abstraction depth should be treated as separate '
         'interventions and measured independently. The NeurIPS 2026 Workshop on Scaling Environments for Agents '
         'and the ICLR 2026 Workshop on Multi-Agent Learning reflect growing field recognition of this distinction. '
         'No cited study has yet performed the exact experiment: holding the base model fixed while independently '
         'varying abstraction depth and population size.'),
        ('P7 — Perception and embodiment change the information available to intelligence', 'Decomposed research hypothesis',
         'Decomposed into four sub-propositions: (P7a) Multimodal input increases accessible information — established. '
         '(P7b) Sensorimotor interaction produces qualitatively different representations than passive observation — '
         'strongly supported (Embodied AI survey, arXiv:2509.20021). (P7c) Embodied feedback signals may be necessary '
         'for certain kinds of valuation and temporal reasoning — open hypothesis. (P7d) Whether subjective experience '
         'is required for general intelligence — philosophical question, excluded from the research program.'),
        ('P8 — Capability and governance can be separated', 'Governance hypothesis',
         'It may be possible to preserve broad reasoning capability while restricting consequential real-world '
         'execution externally. The EU AI Act (2024) represents the first comprehensive legal implementation of '
         'this approach. Recent work on internal architectural governability (SSRN, 2025) extends the hypothesis '
         'beyond external regulation.'),
        ('P9 — Creator/creation autonomy is philosophical, not empirical evidence', 'Philosophical framing',
         'The religious material in the project is valuable as a philosophical lens on creation, freedom, '
         'participation, love and the possibility that a creation exceeds its creator. It should not be presented '
         'as scientific evidence for consciousness or AGI. Standard references: Searle (1980, Chinese Room), '
         'Chalmers (1996, hard problem of consciousness).'),
    ]

    for title, status, body in props:
        chapter(story, styles, title, level=2)
        para(story, styles, f'Status: {status}', 'Meta')
        spacer(story, 0.1)
        para(story, styles, body)

    # ── Omega Research Architecture ──
    story.append(PageBreak())
    chapter(story, styles, 'Omega — Formal Research Architecture')
    para(story, styles,
        'Omega is best stated as a research architecture rather than a claim of an already-solved AGI design. '
        'Its central loop is: Knowledge → Open-ended exploration → Candidate generation → Analogy → '
        'Contradiction-preserving synthesis → Hypothesis → Independent validation → Persistent knowledge → Next cycle.')
    para(story, styles,
        'Let K_t be the accessible knowledge state, E_t the environment, G_t the generated candidate set, '
        'S the synthesis operator, and V an independent validator:')
    para(story, styles,
        'G_t = Generate(K_t, E_t);  H_t = S(G_t);  r_t = V(H_t);  K_(t+1) = K_t ∪ Valid(H_t)', 'Quote')
    para(story, styles,
        'The central experimental question is whether separating generation from validation and iterating '
        'the validated knowledge produces broader and more reliable discovery than forcing one model to '
        'perform every role simultaneously.')

    chapter(story, styles, 'Contradiction, Analogy and Synthesis', level=2)
    para(story, styles,
        'A productive discovery process can be modeled as: Existing theories → preserve competing hypotheses → '
        'search for structural analogies → identify hidden assumptions → synthesize a candidate theory → validate '
        'it → add the surviving result to the literature. This provides a stronger definition of machine novelty: '
        'novelty need not mean information appearing from nothing; it can mean discovering a previously unrecognized '
        'relationship, transformation or synthesis among existing structures.')

    # ── P4 Formal Grounding ──
    chapter(story, styles, 'Formal Grounding for Contradiction-Preserving Synthesis', level=2)
    para(story, styles,
        'The formal grounding for P4 draws on three bodies of work. Paraconsistent logic (Priest, 1979) '
        'assigns truth values from {t, b, f} where b means "both true and false," allowing a system to '
        'contain contradictions without collapse. AGMp belief revision (Ribeiro et al., 2013) extends '
        'the AGM framework to allow revision that produces belief sets containing contradictions: '
        'K_{t+1} = K_t *_{AGMp} E_t. Abstract dialectical frameworks (Brewka et al., 2013) model '
        'competing hypotheses as nodes in a graph with general acceptance conditions, enabling the '
        'synthesis operator to search for a hypothesis that subsumes both competitors.')
    para(story, styles,
        'The five-step algorithm is: (1) Preservation — both hypotheses retained with value b. '
        '(2) Structural analysis — extract assumptions and identify the symmetric difference. '
        '(3) Synthesis search — find H\' consistent with the knowledge base minus the competitors, '
        'subsuming each under context restrictions. (4) Validation — evaluate by independent validator V. '
        '(5) Revision — if validated, replace competitors with synthesis via classical AGM revision; '
        'if not, preserve contradiction for next cycle.')

    # ── Experimental Program ──
    story.append(PageBreak())
    chapter(story, styles, 'Falsifiable Experimental Program')
    para(story, styles,
        'Use the same base LLM and matched compute across conditions. Compare single-pass prompting, '
        'retrieval-plus-reasoning, retrieval-generation-validation, multi-agent populations, evolutionary '
        'selection, cross-domain analogy, and contradiction-preserving hypothesis management. Add sensory '
        'environments as a separate experimental factor rather than mixing perception into model scale.')
    para(story, styles,
        'Measure literature novelty, solution diversity, validity, reproducibility, transfer to unseen tasks, '
        'compute efficiency, and rate of independently verified discoveries. Record failures as carefully as '
        'successes. A theory that predicts no measurable improvement should be rejected or revised.')

    chapter(story, styles, 'Experimental Conditions', level=2)
    conditions = [
        ('C0', 'Single agent, no external memory'),
        ('C1', 'Single agent + retrieval/search'),
        ('C2', 'Single agent + persistent memory'),
        ('C3', 'Multiple agents + communication'),
        ('C4', 'Multiple agents + independent validation'),
        ('C5', 'Multiple agents + competition/self-play'),
        ('C6', 'Population + mutation/selection'),
        ('C7', 'Population + autonomous tool creation'),
        ('C8', 'Population + multimodal perception/action'),
        ('C9', 'Open-ended environment + all preceding mechanisms'),
    ]
    add_simple_table(story, styles, ['Condition', 'Description'],
                     [(c, d) for c, d in conditions])

    spacer(story)
    chapter(story, styles, 'The Key Control Experiment', level=2)
    para(story, styles,
        'Compare a large monolithic model against a smaller fixed model embedded in the full ecology '
        'under matched compute budgets. The question is not whether the ecology always wins. The question '
        'is whether there are regimes in which ecological organization produces capabilities that parameter '
        'scaling alone cannot reproduce economically.')
    para(story, styles,
        'ΔI_ecology = I_ecology(B) − I_monolith(B), where B is a matched resource budget.', 'Quote')

    # ── Limits ──
    story.append(PageBreak())
    chapter(story, styles, 'Limits, Objections and Failure Modes')
    objections = [
        'The biology analogy may be misleading. Artificial systems and organisms have different substrates.',
        'More agents can create coordination overhead rather than intelligence.',
        'Evolution can optimize proxies and produce pathological strategies.',
        'A population can converge prematurely and lose diversity.',
        'Validation can itself be wrong or gameable.',
        'Open-ended exploration can become computationally unbounded.',
        'Memory can accumulate noise and stale beliefs.',
        'Competition can produce adversarial equilibria instead of useful intelligence.',
        'Multimodality may require specialized architectures.',
        'Consciousness is not implied by capability, emergence or self-reference.',
        'There may be hard limits in the fixed core model that ecology cannot overcome.',
    ]
    for o in objections:
        bullet(story, styles, o)
    spacer(story)
    para(story, styles,
        'The most important objection is: perhaps the LLM core is not a primitive like a biological cell. '
        'Perhaps it is already a highly specialized statistical artifact whose limits cannot be overcome '
        'by surrounding it with more copies. The answer is not rhetoric. It is the control experiment.')

    # ── Final Establishment ──
    chapter(story, styles, 'Final Establishment')
    para(story, styles,
        'The work does not establish that Omega is AGI. It establishes a coherent and testable research thesis: '
        'increasingly capable neural learners may acquire qualitatively broader intelligence through interaction '
        'with open-ended knowledge, environments, memory, abstraction, analogy, competing hypotheses, populations '
        'of agents, evolutionary selection and independent validation.')
    para(story, styles,
        'The key scientific question is whether these components produce emergent capabilities that cannot be '
        'obtained efficiently by scaling a single model alone. The project should therefore be presented as a '
        'research program and hypothesis, not as a completed discovery.')

    # ── Closing ──
    chapter(story, styles, 'Let It Be Broken')
    para(story, styles,
        'A useful scientific idea should not be protected from criticism. It should be exposed to it. '
        'The central proposal of this book is therefore intentionally unfinished.')
    para(story, styles,
        'Perhaps intelligence is mostly parameter scale. Perhaps vertical abstraction is the decisive variable. '
        'Perhaps horizontal populations matter only for specialized tasks. Perhaps evolutionary systems will '
        'plateau. Perhaps a new core architecture will eventually be necessary. Perhaps the combination will '
        'produce a capability regime nobody currently understands. All of these possibilities remain open.')
    para(story, styles,
        'The next step may not be another larger box. It may be a world — a world in which models perceive, '
        'remember, explore, compete, cooperate, validate, create tools, teach one another and evolve.')
    para(story, styles,
        'That is the invitation of this book: Do not believe it. Build it. Measure it. Break it. Improve it.')

    # ── Appendix: Mathematical Core ──
    story.append(PageBreak())
    chapter(story, styles, 'Appendix A — Mathematical Core')
    math_items = [
        ('A.1 Resource-normalized capability', 'I(B) = performance achieved under resource budget B.'),
        ('A.2 Scaling elasticity', 'ε_x = (ΔI/I) / (Δx/x). Percentage change in capability per percentage change in scaling variable.'),
        ('A.3 Interaction synergy', 'S_{xy} = I(x,y) − I(x,0) − I(0,y) + I(0,0). Positive S_xy indicates super-additive interaction.'),
        ('A.4 Diversity', 'D(P) = H(Strategies(P)). Entropy over strategy classes.'),
        ('A.5 Evolutionary progress', 'ΔF_t = F(P_{t+1}) − F(P_t), where F is population fitness distribution.'),
        ('A.6 Knowledge growth', 'K_{t+1} = K_t ∪ ΔK_t. The rate of useful information discovered, validated and reused.'),
        ('A.7 Validation reliability', 'R_V = P(Validator(c)=correct | c). Validators must themselves be calibrated.'),
        ('A.8 Open-endedness', 'O = Novelty × Sustainability × Unpredictability_of_future_tasks.'),
    ]
    for title, desc in math_items:
        chapter(story, styles, title, level=3)
        para(story, styles, desc)

    # ── Appendix: Provenance ──
    story.append(PageBreak())
    chapter(story, styles, 'Appendix B — Origin of the Framework')
    prov_path = os.path.join(base, 'Supplement_D_Provenance_Appendix.md')
    if os.path.exists(prov_path):
        with open(prov_path, 'r', encoding='utf-8') as f:
            prov_md = f.read()
        # Skip the header lines
        lines = prov_md.split('\n')
        start = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('## APPENDIX B'):
                start = i
                break
        parse_markdown('\n'.join(lines[start:]), story, styles)

    # ── Appendix: Terminology ──
    story.append(PageBreak())
    chapter(story, styles, 'Appendix C — Terminology and Claims Discipline')
    terms = [
        ('Emergence', 'A system-level property arising from interactions among components. It does not imply magic, irreducibility or consciousness.'),
        ('Intelligence', 'Adaptive competence across tasks and environments. Deliberately operational rather than metaphysical.'),
        ('Consciousness', 'Subjective experience or phenomenal awareness. No claim that current AI systems possess it.'),
        ('Emotion', 'A family of biological processes involving valuation, bodily state, motivation, learning and action. Transformer attention should not be equated with emotion.'),
        ('Evolution', 'Iterative variation, selection and inheritance. Mere repeated prompting is not necessarily evolution.'),
        ('Validation', 'An independent mechanism that evaluates a candidate against evidence, constraints or consequences.'),
        ('Exploration', 'Deliberate search through possibilities or environments without a fully specified final answer.'),
        ('Abstraction', 'Representation that compresses or organizes information so that relationships can be reused across contexts.'),
        ('Ecology', 'The interacting computational environment consisting of agents, tools, knowledge, memory, evaluators and tasks.'),
    ]
    for term, defn in terms:
        chapter(story, styles, term, level=3)
        para(story, styles, defn)

    # ── References ──
    story.append(PageBreak())
    chapter(story, styles, 'References')
    refs = [
        'Kaplan, J. et al. (2020). Scaling Laws for Neural Language Models. arXiv:2001.08361.',
        'Hoffmann, J. et al. (2022). Training Compute-Optimal Large Language Models. arXiv:2203.15556.',
        'Snell, C. et al. (2025). Scaling LLM Test-Time Compute Optimally. ICLR 2025 Oral.',
        'OpenAI (2024). Learning to Reason with LLMs (o1 technical report).',
        'Webb, T., Holyoak, K.J. & Lu, H. (2023). Emergent analogical reasoning in LLMs. Nature Human Behaviour.',
        'Shen, X., Druckmann, S. & Zou, J. (2026). Unlocking LLM Creativity through Analogical Reasoning. arXiv:2605.11258.',
        'Google DeepMind (2021). Generally capable agents emerge from open-ended play / XLand.',
        'Google DeepMind (2025). AlphaEvolve: A Gemini-powered coding agent for advanced algorithms.',
        'Romera-Paredes, D. et al. (2024). Mathematical discoveries from program search with LLMs (FunSearch). Nature.',
        'Du, Y. et al. (2024). Improving Factuality and Reasoning through Multiagent Debate. ICML 2024.',
        'Li et al. (2025). Can LLM Agents Really Debate? arXiv:2511.07784.',
        'Chen et al. (2025). Multi-Agent Evolve: LLM Self-Improve through Co-evolution. arXiv:2510.23595.',
        'Hu et al. (2026). Evolutionary Generation of Multi-Agent Systems (EvoMAS). arXiv:2602.06511.',
        'Qu et al. (2026). CORAL: Autonomous Multi-Agent Evolution for Open-Ended Discovery. arXiv:2604.01658.',
        'Jaderberg, M. et al. (2017). Population Based Training of Neural Networks. DeepMind.',
        'Dung, P.M. (1995). On the acceptability of arguments. Artificial Intelligence, 77(2), 321–357.',
        'Brewka, G. et al. (2013). Abstract Dialectical Frameworks. IJCAI 2013.',
        'Priest, G. (1979). The Logic of Paradox. Journal of Philosophical Logic, 8(1), 219–241.',
        'da Costa, N.C.A. (1974). On the theory of inconsistent formal systems. Notre Dame J. Formal Logic, 15(4).',
        'Ribeiro, M.M. et al. (2013). AGM-like Paraconsistent Belief Change. Principia.',
        'Alchourrón, C., Gärdenfors, P. & Makinson, D. (1985). On the logic of theory change. J. Symbolic Logic, 50(2).',
        'Coniglio, M.E. & Ferens, R. (2022). Paraconsistent Belief Revision. Erkenntnis.',
        'Embodied AI: From LLMs to World Models (2025). arXiv:2509.20021.',
        'EU AI Act (2024). European Union Artificial Intelligence Act.',
        'Searle, J. (1980). Minds, Brains, and Programs. Behavioral and Brain Sciences.',
        'Chalmers, D. (1996). The Conscious Mind. Oxford University Press.',
        'LeCun, Y., Bengio, Y. & Hinton, G. (2015). Deep learning. Nature, 521, 436–444.',
        'Nature Scientific Reports (2025). Divergent creativity in humans and LLMs.',
        'Baker et al. (2019). Emergent Tool Use from Multi-Agent Interaction. OpenAI.',
        'Zheng et al. (2023). Large Language Models for Scientific Synthesis, Inference and Explanation.',
    ]
    for r in refs:
        ref_entry(story, styles, r)

    # Build
    doc.build(story)
    print(f'Volume I built: {out} ({doc.page} pages)')

if __name__ == '__main__':
    build()
