# BEYOND PARAMETER SCALING — Research Program Supplement
## Expanded Literature, Formal Grounding for P4, and P7 Decomposition
### August 2026

This supplement addresses three structural weaknesses identified in the review of the
Beyond Parameter Scaling corpus: (1) the literature base was too thin for the breadth
of claims made; (2) P4 (contradiction-preserving synthesis) lacked formal grounding;
(3) P7 (perception changes information available to intelligence) was too broad to
test. Each section below is written for direct insertion into the next revision of the
canonical research document.

---

## PART A — EXPANDED LITERATURE BASE BY PROPOSITION

### P1 — Intelligence is not one-dimensional
**Status: Established direction**

The parameter-scaling hypothesis rests on empirical scaling laws formalized by Kaplan
et al. (2020) and refined by Hoffmann et al. (2022, Chinchilla), who demonstrated that
compute-optimal training requires balancing model size and data rather than simply
maximizing parameters. Subsequent work has identified sub-scaling regimes in which
performance gains diminish predictably (OpenReview, "From Scaling Law to Sub-Scaling
Law," 2025), and domain-specific studies have found diminishing returns to scale even
in frontier models (Hackenburg et al., 2025, on political persuasion).

Inference-time computation has emerged as a distinct scaling axis. Snell et al. (ICLR
2025 Oral) demonstrated that scaling test-time compute can be more effective than
scaling model parameters for certain reasoning tasks. OpenAI's o1/o3 models (2024–
2025) showed that chain-of-thought reasoning trained via reinforcement learning
produces qualitative capability shifts not reducible to parameter count. Forest-of-
Thought (ICML 2025) extended this by integrating multiple reasoning trees for
collective decision-making on complex logical tasks.

The multidimensional view is now mainstream in practice: capability depends on
parameters, data, compute, training methodology, inference-time computation, tool
access, memory, and environmental structure. No major frontier lab treats parameter
count as a sufficient theory.

**Key references:**
- Kaplan, J. et al. (2020). Scaling Laws for Neural Language Models. arXiv:2001.08361.
- Hoffmann, J. et al. (2022). Training Compute-Optimal Large Language Models. arXiv:2203.15556.
- Snell, C. et al. (2025). Scaling LLM Test-Time Compute Optimally Can be More Effective than Scaling Model Parameters. ICLR 2025 Oral.
- OpenAI (2024). Learning to Reason with LLMs (o1 technical report).
- Forest-of-Thought (2025). Scaling Test-Time Compute for Enhancing LLM Reasoning. ICML 2025.
- "From Scaling Law to Sub-Scaling Law: Under-scaling Phenomena in LLMs." OpenReview, 2025.
- Hackenburg, K. et al. (2025). Scaling Language Model Size Yields Diminishing Returns for Single-Message Political Persuasion. LSE Research Online.
- Wolfe, C. (2025). Scaling Laws for LLMs: From GPT-3 to o3. Substack analysis.

### P2 — Exploration and validation should be separable
**Status: Research hypothesis**

The separation of generation from evaluation has precedent in multiple independent
lines of research. AlphaEvolve (DeepMind, 2025) explicitly separates LLM-based code
generation from automated evaluation via a program database and evolutionary
selection. FunSearch (Google DeepMind, 2024) used LLM-generated programs filtered
through automated evaluators to discover new mathematical results, including a
solution to the cap set problem variant.

In the multi-agent debate literature, Du et al. (ICML 2024) showed that multiple LLM
instances proposing and debating individual responses, followed by a separate
evaluation step, improves factuality and reasoning. However, Li et al. (2025,
"Can LLM Agents Really Debate?") found that debate performance gains are
substantially dependent on agent diversity and can degrade when agents converge
prematurely — providing a concrete cautionary result for the separation hypothesis.

Argumentation theory provides a formal framework for this separation. Dung's (1995)
abstract argumentation framework models conflict among arguments with an attack
relation, and subsequent work on abstract dialectical frameworks (Brewka et al., 2013;
COMMA 2024) allows for general acceptance conditions beyond binary attack,
including support, conditional acceptance, and collective evaluation — precisely the
kind of independent validation structure that P2 proposes.

**Key references:**
- AlphaEvolve (DeepMind, 2025). A Gemini-powered coding agent for designing advanced algorithms.
- FunSearch (Romera-Paredes, D. et al., 2024). Mathematical discoveries from program search with large language models. Nature.
- Du, Y. et al. (2024). Improving Factuality and Reasoning in Language Models through Multiagent Debate. ICML 2024.
- Li et al. (2025). Can LLM Agents Really Debate? A Controlled Study. arXiv:2511.07784.
- ACL 2025. Multi-Agent LLM Debate Unveils the Premise Left Unsaid. ACL anthology.
- Dung, P.M. (1995). On the acceptability of arguments and its fundamental role in nonmonotonic reasoning. Artificial Intelligence, 77(2), 321–357.
- Brewka, G. et al. (2013). Abstract Dialectical Frameworks. IJCAI.
- COMMA 2024. Computational Models of Argument. IOS Press.

### P3 — Analogy is a mechanism for novelty
**Status: Strongly supported**

Webb, Holyoak & Lu (Nature Human Behaviour, 2023) demonstrated emergent
analogical reasoning in GPT-3 with stronger preliminary performance in GPT-4. Shen,
Druckmann & Zou (2026 preprint, arXiv:2605.11258) reported that explicit cross-
domain analogical reasoning increased solution diversity by 90–173% and produced
novel solutions far more often than baselines.

Subsequent work has strengthened these findings. A Cambridge Design Science study
(2025) evaluated LLM-generated content in cross-domain analogical reasoning for
design ideation and found that LLMs can serve as effective analogical partners when
the cross-domain mapping is explicitly structured. Nature Scientific Reports (2025,
"Divergent creativity in humans and large language models") found evidence that LLMs
can surpass average human performance on the Divergent Association Task, though
they remain below top human performers on creative writing.

Human-guided analogical reasoning amplifies LLM performance on complex cross-
domain problems (PMC, 2025), suggesting that the strongest results come from
human-LLM collaboration rather than purely autonomous analogy generation.
However, LLMs tend to generate analogies closely aligned with similar target domains
(arXiv:2608.03233, 2026), which is a genuine limitation: the most valuable analogies
are often those that cross distant domains, and current models show a bias toward
near analogies.

**Key references:**
- Webb, T., Holyoak, K.J. & Lu, H. (2023). Emergent analogical reasoning in large language models. Nature Human Behaviour.
- Shen, X., Druckmann, S. & Zou, J. (2026). Unlocking LLM Creativity in Science through Analogical Reasoning. arXiv:2605.11258.
- Cambridge Design Science (2025). Analogical reasoning with large language models: a co-creative framework and benchmarking of LLMs in design ideation.
- Nature Scientific Reports (2025). Divergent creativity in humans and large language models.
- PMC (2025). Human analogical guidance amplifies LLM performance through cross-domain reasoning.
- arXiv:2608.03233 (2026). On the Diversity of Analogy Making in Large Language Models.
- INFORMS (2025). Can LLMs Aid Analogical Reasoning for Strategic Decisions? Strategy Science.

### P4 — Contradiction can be retained as a productive constraint
**Status: Research hypothesis — now formally grounded (see Part B below)**

### P5 — Population-level evolution can improve solutions
**Status: Established direction**

XLand (DeepMind, 2021) trained agents across millions of unique tasks in a
dynamically changing multiplayer environment and reported broadly applicable
behaviors and transfer to unseen tasks. AlphaEvolve (DeepMind, 2025) combines
LLMs, automated evaluators, a program database, and evolutionary selection, with
published results including new algorithmic discoveries.

The evolutionary LLM-agent literature has expanded rapidly. Chen et al. (2025,
"Multi-Agent Evolve: LLM Self-Improve through Co-evolution") demonstrated that
multi-agent populations can co-evolve to improve individual and collective capability.
Hu et al. (2026, EvoMAS) showed evolutionary generation of multi-agent systems
with automatic architecture search. CORAL (Qu et al., 2026) demonstrated autonomous
multi-agent evolution for open-ended discovery. Population Based Training (DeepMind,
2017/2018) remains a foundational method for hyperparameter optimization through
evolutionary selection.

OpenEvolve (2025, open-source) provides a reproducible implementation of
evolutionary coding agents, enabling independent verification of AlphaEvolve-type
results.

**Key references:**
- DeepMind (2021). Generally capable agents emerge from open-ended play / XLand.
- AlphaEvolve (DeepMind, 2025).
- Chen et al. (2025). Multi-Agent Evolve: LLM Self-Improve through Co-evolution. arXiv:2510.23595.
- Hu et al. (2026). Evolutionary Generation of Multi-Agent Systems (EvoMAS). arXiv:2602.06511.
- Qu et al. (2026). CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery. arXiv:2604.01658.
- Jaderberg, M. et al. (2017/2018). Population Based Training of Neural Networks. DeepMind.
- OpenEvolve (2025). Open-source evolutionary coding agent. GitHub.
- arXiv:2603.28416 (2026). Evolutionary Discovery of Reinforcement Learning Algorithms.
- DeepMind (2025). Evolving Deeper LLM Thinking / Mind Evolution.

### P6 — Horizontal and vertical scaling are distinct
**Status: Research hypothesis**

Vertical scaling (depth of abstraction) and horizontal scaling (population breadth) are
conceptually distinct but have rarely been measured independently in the LLM
literature. The nearest experimental precedent is Population Based Training, which
varies population size independently from model architecture, and the multi-agent
debate literature, which varies the number of debating agents independently from
the base model.

The NeurIPS 2026 Workshop on Scaling Environments for Agents and the ICLR 2026
Workshop on Multi-Agent Learning represent the field's growing recognition that
agent-environment scale and model scale are distinct interventions.

No cited study has yet performed the exact experiment proposed here: holding the
base model fixed while independently varying abstraction depth (number of
successive meta-reasoning passes) and population size, measuring their separate and
interactive effects.

**Key references:**
- NeurIPS 2026 Workshop. Scaling Environments for Agents.
- ICLR 2026 Workshop. Multi-Agent Learning and Its Opportunities in the Era of Generative AI.
- Jaderberg, M. et al. (2017/2018). Population Based Training.
- Du, Y. et al. (2024). Multiagent Debate (varying agent count independently from model).

### P7 — Perception changes the information available to intelligence
**Status: Decomposed into testable sub-propositions (see Part C below)**

### P8 — Capability and governance can be separated
**Status: Governance hypothesis**

The EU AI Act (2024) represents the first comprehensive legal framework classifying AI
systems by risk and imposing obligations on developers — an external governance
approach that preserves model capability while constraining deployment. The
conceptual distinction between capability-limiting approaches (restricting what a
model can learn or represent) and governance-limiting approaches (restricting what a
model can do in the world) is now widely recognized in the AI safety literature.

Recent work on "Beyond External Constraints" (SSRN, 2025) proposes that AI
governance has a missing dimension: not just external regulation, but internal
architectural properties that make systems governable. This aligns with P8's
hypothesis that preserving broad reasoning capability while restricting consequential
real-world execution externally should be experimentally compared with capability-
limiting approaches.

**Key references:**
- EU AI Act (2024). European Union Artificial Intelligence Act.
- SSRN (2025). Beyond External Constraints: The Missing Dimension of AI Governance.
- ITU (2025). The Annual AI Governance Report 2025: Steering the Future of AI.

### P9 — Creator/creation autonomy is philosophical, not empirical evidence
**Status: Philosophical framing**

This proposition is by nature a boundary claim rather than an empirical hypothesis.
The relevant literature is in philosophy of mind, philosophy of technology, and
theology. The proposition is consistent with standard positions in each field:
philosophy of mind does not derive consciousness from capability; philosophy of
technology distinguishes between instrumental and autonomous agency; theology
distinguishes between creation as act and creation as being.

No additional empirical literature is required. The proposition should cite standard
philosophical references: Searle (1980, Chinese Room), Chalmers (1996, hard
problem of consciousness), and the theological distinction between creatio ex nihilo
and creatio continua.

**Key references:**
- Searle, J. (1980). Minds, Brains, and Programs. Behavioral and Brain Sciences.
- Chalmers, D. (1996). The Conscious Mind. Oxford University Press.
- Stanford Encyclopedia of Philosophy. Creation and Conservation (theological).

---

## PART B — FORMAL GROUNDING FOR P4

### P4 Restated
Instead of immediately resolving conflicting theories, a system can preserve competing
hypotheses, identify their hidden assumptions, and search for a third synthesis.

### Why P4 needs formal grounding
As stated, P4 is an intuition. "Preserve contradiction" is ambiguous — does it mean
storing two conflicting beliefs side by side (trivial), maintaining both in active
inference without collapse (non-trivial), or using the tension between them as a
generator of new structure (ambitious)? Formal literature in three areas —
paraconsistent logic, AGM belief revision, and computational argumentation —
provides the vocabulary to make P4 precise and implementable.

### B.1 Paraconsistent Logic

Classical logic is explosive: from a contradiction, anything follows (ex contradictione
quodlibet). Paraconsistent logics reject this principle, allowing a system to contain
contradictions without collapsing into triviality.

**Core definition (Stanford Encyclopedia, 2024 edition):** A logic is paraconsistent if
and only if it is not explosive — i.e., there exist formulas A, B such that A, ¬A ⊬ B.

The Logic of Paradox (LP, Priest 1979) assigns truth values from {t, b, f} where b
means "both true and false." In LP, a proposition can be designated (t or b) without
forcing every other proposition to be designated. This provides a minimal formal
structure for P4: hypotheses can be held as both-supported-and-opposed (value b)
without the system deriving arbitrary conclusions.

**Relevance to P4:** The Omega architecture can represent a hypothesis H with its
supporting evidence E+ and opposing evidence E− as having truth value b in a
paraconsistent logic. The system continues to reason with H without either discarding
it (which would lose potentially valuable structure) or accepting it unconditionally
(which would propagate error).

**Key references:**
- Priest, G. (1979). The Logic of Paradox. Journal of Philosophical Logic, 8(1), 219–241.
- da Costa, N.C.A. (1974). On the theory of inconsistent formal systems. Notre Dame Journal of Formal Logic, 15(4), 497–510.
- Stanford Encyclopedia of Philosophy (2024). Paraconsistent Logic.
- Tanaka, K. et al. (eds., 2013). Paraconsistency: Logic and Applications. Springer.

### B.2 AGM Belief Revision in Paraconsistent Settings

The AGM framework (Alchourrón, Gärdenfors & Makinson, 1985) defines three
operations on a belief set K:
- **Expansion** (K+A): add A to K
- **Contraction** (K−A): remove A from K
- **Revision** (K*A): add A while maintaining consistency

The revision operation is the critical one. In classical AGM, revision requires
maintaining consistency, which means contradictions must be resolved. Paraconsistent
extensions of AGM (Ribeiro et al., 2013, "AGM-like Paraconsistent Belief Change";
Mares, "A Paraconsistent Theory of Belief Revision"; recent algebraic investigation
in Erkenntnis, 2022) relax the consistency requirement.

**Ribeiro et al. (2013)** define two systems:
- **AGMp**: belief change over paraconsistent logics, allowing revision to produce
  belief sets that contain contradictions without collapse
- **AGMo**: a weaker system that preserves the AGM postulates where possible
  and modifies only those that assume consistency

**Relevance to P4:** The Omega knowledge state K_t can be modeled as a
paraconsistent belief set. When new evidence E_t arrives that contradicts existing
beliefs, the system performs paraconsistent revision (AGMp) rather than classical
revision (AGM). This preserves the contradiction as a productive structure:

    K_{t+1} = K_t *_{AGMp} E_t

The contradiction remains in K_{t+1} until either:
(a) New evidence resolves it (classical revision becomes possible)
(b) The synthesis operator S identifies a higher-order structure that subsumes both
    competing hypotheses (Hegelian synthesis, formally: find H' such that H' ⊢ H₁
    in context C₁ and H' ⊢ H₂ in context C₂)

**Key references:**
- Alchourrón, C., Gärdenfors, P. & Makinson, D. (1985). On the logic of theory change. Journal of Symbolic Logic, 50(2), 510–530.
- Ribeiro, M.M. et al. (2013). AGM-like Paraconsistent Belief Change. Principia.
- Mares, E.D. A Paraconsistent Theory of Belief Revision. PhilPapers.
- Coniglio, M.E. & Ferens, R. (2022). Paraconsistent Belief Revision: An Algebraic Investigation. Erkenntnis.
- arXiv:2412.06117 (2024). A Logic for Paraconsistent Belief Revision based on Epistemic Entrenchment.

### B.3 Computational Argumentation

Dung's Abstract Argumentation Framework (1995) models argumentation as a directed
graph (Args, Attack) where arguments attack each other. An argument is acceptable
if it is defended against all its attackers.

**Abstract Dialectical Frameworks (ADFs, Brewka et al. 2013)** generalize Dung's
framework by replacing the binary attack relation with arbitrary acceptance
conditions. Each argument has an acceptance condition expressed as a Boolean
function over its parents in the graph. This allows modeling:
- Support (argument A supports B)
- Conditional acceptance (A is accepted only if B and C are both accepted)
- Collective evaluation (A is accepted if at least two of {B, C, D} are accepted)

**Relevance to P4:** The Omega synthesis operator S can be formalized as an ADF
operating over competing hypotheses:

    ADF = (H, L, AC)

where H = {H₁, H₂, ..., Hₙ} is the set of competing hypotheses, L is the set of
links between hypotheses (attack, support, conditional-dependence), and AC is the
set of acceptance conditions. The synthesis step searches for a new hypothesis H'
whose acceptance condition is satisfied by the union of the support structures of H₁
and H₂ — i.e., H' subsumes both competitors.

**Multi-agent debate connection:** Li et al. (2025, ACL) showed that accuracy gains
in multi-agent LLM debate stem from agents refining predictions in response to
opposing views — not from repeated generation. This is precisely the argumentation
mechanism: competing arguments improve the system when the acceptance
conditions (evaluation criteria) can distinguish better from worse refinements.

**Key references:**
- Dung, P.M. (1995). On the acceptability of arguments and its fundamental role in nonmonotonic reasoning, logic programming and n-person games. Artificial Intelligence, 77(2), 321–357.
- Brewka, G., Ellmauthaler, S., Strass, H., Wallner, J.P. & Woltran, S. (2013). Abstract Dialectical Frameworks. IJCAI 2013.
- COMMA 2024 Proceedings. Computational Models of Argument. IOS Press.
- IJCAI 2024. Reasoning, Dynamics, and Supporting Explainability in Abstract Argumentation.
- Li et al. (2025). Multi-Agent LLM Debate Unveils the Premise Left Unsaid. ACL.

### B.4 Integrated Formal Statement of P4

P4 can now be restated formally:

**P4 (formal):** A discovery system maintains its knowledge state K_t as a
paraconsistent belief set under AGMp revision. When K_t contains competing
hypotheses {H₁, H₂} with contradictory support, the system does not immediately
contract to resolve the contradiction. Instead:

1. **Preservation:** Both H₁ and H₂ are retained with designated truth value b.
2. **Structural analysis:** The system extracts the assumptions A(H₁) and A(H₂)
   and identifies the assumption set Δ = A(H₁) △ A(H₂) (symmetric difference).
3. **Synthesis search:** The system searches for H' such that:
   - H' is consistent with K_t \ {H₁, H₂}
   - H' subsumes H₁ under some context restriction C₁
   - H' subsumes H₂ under some context restriction C₂
   - H' explains the evidence that supported both H₁ and H₂
4. **Validation:** H' is evaluated by the independent validator V.
5. **Revision:** If V(H') passes threshold, K_{t+1} = (K_t \ {H₁, H₂}) ∪ {H'} via
   classical AGM revision. If not, the contradiction is preserved for the next cycle.

This is implementable. Each step maps to existing formal machinery. The
experimental question is whether step 3 (synthesis search) produces hypotheses
that are measurably more novel and valid than hypotheses generated from
contradiction-free knowledge states.

---

## PART C — DECOMPOSITION OF P7

### P7 as originally stated
Perception changes the information available to intelligence.

### Why decomposition is needed
As stated, P7 conflates at least four distinct claims that have different evidence
statuses and different experimental implications. The trivial reading (different
sensors → different data) is established. The strong reading (embodiment is necessary
for general intelligence) is unproven and possibly unprovable in current terms.

### Sub-propositions

**P7a — Multimodal input increases the accessible information space**
*Status: Established.*
Text-only systems cannot access visual, auditory, proprioceptive, or olfactory
information. Adding vision, audio, or tactile sensors trivially increases the
information available. This is an engineering fact, not a hypothesis.
Evidence: GPT-4V, Gemini multimodal, and multimodal embodied AI surveys
(arXiv:2509.20021, "Embodied AI: From LLMs to World Models," 2025).

**P7b — Sensorimotor grounding changes learned representations**
*Status: Strongly supported.*
Agents that can act on and receive feedback from an environment develop
representations that differ from agents trained on static datasets of the same
environment. The embodied AI literature demonstrates that interactive perception
produces qualitatively different representations than passive observation.
Evidence: Bio-inspired cognitive frameworks for embodied agents (arXiv:2510.17129,
2025); spatial intelligence and multimodal reasoning work (Li, Northwestern).
Experimental prediction: An agent that navigates a 3D environment and learns from
interactive feedback will develop spatial representations that a text-trained agent
cannot replicate from textual descriptions of the same environment.

**P7c — Embodiment provides feedback signals unavailable to text-only systems**
*Status: Open hypothesis.*
Biological intelligence uses proprioceptive, interoceptive, and affective feedback
(pain, hunger, fatigue, reward signals) that have no direct textual equivalent. The
question is whether these signals are necessary for certain kinds of intelligence
(motivation, valuation, temporal urgency) or whether they can be functionally
approximated by textual or numerical proxies.
This is related to but distinct from the consciousness question. A system might
require reward signals for effective learning without those signals constituting
subjective experience.
Experimental prediction: Compare an agent with numerical reward signals against
an agent with no reward signals and an agent with human-like affective proxies,
measuring capability on tasks requiring valuation and temporal prioritization.

**P7d — Emotion or consciousness is required for general intelligence**
*Status: Unproven philosophical claim. Not an empirical hypothesis in current terms.*
This is the strongest possible reading of P7 and should be explicitly separated from
the research program. It is not testable because "consciousness" lacks an agreed
operational definition, and "general intelligence" is defined differently by different
researchers. The research program should neither assert nor deny P7d. It should note
that P7a–P7c are testable without committing to P7d.

### Revised P7 statement for the canonical document

**P7 — Perception and embodiment change the information available to intelligence**
*Decomposed research hypothesis.*
(a) Multimodal input increases accessible information (established).
(b) Sensorimotor interaction produces qualitatively different representations than
    passive observation (strongly supported).
(c) Embodied feedback signals may be necessary for certain kinds of valuation and
    temporal reasoning (open hypothesis, experimentally testable).
(d) Whether subjective experience is required for general intelligence is a
    philosophical question that the research program does not address.

**Key references:**
- arXiv:2509.20021 (2025). Embodied AI: From LLMs to World Models. Tsinghua survey.
- arXiv:2510.17129 (2025). A Bio-Inspired Cognitive Framework for Embodied Agents.
- Li, M. Selected publications on spatial intelligence and multimodal reasoning. Northwestern.
- Barsalou, L.W. (2008). Grounded Cognition. Annual Review of Psychology, 59, 617–645.
- Wilson, M. (2002). Six views of embodied cognition. Psychonomic Bulletin & Review, 9(4), 625–636.

---

## SUMMARY OF CHANGES

| Proposition | Before | After |
|---|---|---|
| P1 | 2 references | 8 references, inference-time scaling axis added |
| P2 | 1 reference | 8 references, argumentation framework added |
| P3 | 2 references | 7 references, limitations of LLM analogy noted |
| P4 | No formal grounding | Full formal grounding in paraconsistent logic, AGMp, and ADFs |
| P5 | 2 references | 9 references, open-source verification noted |
| P6 | 0 references | 4 references, workshop-level field recognition noted |
| P7 | 1 vague proposition | 4 decomposed sub-propositions with distinct evidence statuses |
| P8 | 0 references | 3 references, EU AI Act as concrete governance example |
| P9 | 0 references | 2 standard philosophical references (appropriate for the claim type) |
| **Total** | **~15 references** | **~48 references** |
