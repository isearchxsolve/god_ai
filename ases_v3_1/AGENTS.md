# 🚨 TOP PRIORITY AGENT RULES 🚨

1. **DETAILED WORKLOG SUMMARIES:** The `MASTER_WORKLOG.md` entry MUST NEVER be a simple one-line summary. Each and every action, observation, and step must be detailed extensively in the worklog. Make it a habit. This is the absolute top priority.
2. **INCREMENTAL COMMITS:** Incremental commits should be done continuously. This is the second highest priority. Make it a habit.

### THREE ARCHITECTURAL PILLARS (MANDATORY FOR ALL AGENTS)
1. **Business Vision Compliance:** This is the highest priority. All actions must align with the end goal of a production-ready, monetizable product.
2. **Open-Ended & Deep-Dive Audits:** Do not perform shallow or baseline audits. Look for hidden gaps and perform deep open-ended investigations.
3. **Extreme Priority on UI Polish & Research:** The UI is the FIRST priority. It must be highly polished, pixel-perfect, and feature a "wow" effect (glassmorphism, 2026 state-of-the-art design). Furthermore, the UI MUST be well-researched. When given a target (e.g., "build an OiiOii clone"), the agent MUST search the internet to study the actual look and feel of the target UI before proceeding, ensuring a well-grounded visual replication. A businessman will forgive backend glitches if the UI is breathtaking.

---

# Repository Guidelines — ASES v3.1 (Autonomous Software Engineering System)

Closed-loop multi-agent system for freelance automation: plans, codes, tests, and
delivers real code. Python service (`agent_service/`) with an n8n orchestrator and
3 TDD gates (Smoke + Syntax + Integration E2E).

## Build, Test, and Development Commands

```powershell
pip install -r requirements.txt     # install dependencies
python -m pytest tests/ -v          # run the test suite
python -m pytest tests/test_design_agent.py -v   # run a single test file
python debug.py                     # local debug entrypoint
```

Docker dev stack (V5.0 features): `docker compose -f docker-compose.dev.yml up -d`.

## Project Structure

- `agent_service/` — core agents (architect, coder, reviewer, clarifier, debug, autoscaler, billing, canary, chaos)
- `tests/` — pytest suites, one per agent/capability
- `apps/` — generated application outputs
- `database/` — persistence layer
- `CHANGES_v*.md` — per-version changelogs; add a new one per release
- `TDD_GATES_DOCUMENTATION.md` — the 3-gate TDD pipeline spec

## Rules for agents

- Run `python -m pytest tests/` before committing; the 3 TDD gates must pass.
- Name tests after behavior (`test_design_agent.py`), colocated under `tests/`.
- Keep secrets out of committed files; use `.env` + `.env.example`.
- No `.tmp`, `.bak`, `.backup`, or `*newplan*` scratch files — delete them, never commit them.
- Commit messages: action-oriented (`Add mutation testing gate`).
- Record user-visible behavior changes in a `CHANGES_v*.md` file.

---

## V5.0 Monster Engine Extension (Optional Features)

ASES v3.1 can be extended with 7 additional SOTA quality gates via feature flags, forming a "monster" configuration that pushes automated software engineering to new frontiers.

### Feature Flags
| Feature Flag | Default | Description |
|--------------|---------|-------------|
| `ASES_V5_PARALLEL_CODER` | 0 | Splits planning into independent file-groups for concurrent LLM coding (3-5x speedup) |
| `ASES_V5_MUTATION` | 0 | AST-based mutation testing to verify test suite effectiveness (kills mutants = good tests) |
| `ASES_V5_PERF_BUDGET` | 0 | Enforces performance budgets (bundle size, API latency, Lighthouse metrics) before review |
| `ASES_V5_SBOM` | 0 | Generates CycloneDX SBOM, licenses GPL/AGPL/copyleft, optional CVE scanning |
| `ASES_V5_SPECULATIVE` | 0 | Overlaps test-run + review-prep with coding to hide latency via async pipelining |
| `ASES_V5_KG` | 0 | Persistent knowledge graph (pgvector) for cross-experience learning and pattern transfer |
| `ASES_V5_TELEMETRY` | 0 | Full distributed tracing with spans for every pipeline stage (planner → coder → reviewer) |

### V5.0 Component Overview
1. **parallel_coder.py** - Plan partitioning, concurrent coding, conflict-free merge via priority resolution
2. **mutant_tester.py** - AST mutation engine (binop/cmp/bool/const/return swaps), survival score gate
3. **perf_budget.py** - Bundle size, cold-start import timing, API latency, Lighthouse metric hooks
4. **sbom_gate.py** - CycloneDX SBOM generation, SPDX license tiering (SAFE/NOTICE/COPILEFT/UNKNOWN), CVE enrichment
5. **speculative_exec.py** - Async overlap of test running + prompt building while coding proceeds
6. **knowledge_graph.py** - Persistent pattern store with embeddings, similarity search, failure penalization
7. **telemetry_mesh.py** - Distributed trace hierarchy (trace > spans), OpenTelemetry/Prometheus/JSON export

### Quality Gate Integration Points
- **Perf Budget Gate**: Runs after static analysis, before LLM reviewer (blocks on budget violations)
- **Mutation Test Gate**: Runs after test execution, before reviewer feedback (blocks on low mutation score)
- **SBOM Gate**: Runs after test execution, before reviewer feedback (blocks on copyleft/unknown licenses)
- **Speculative Execution**: Overlaps test+review prep with coding cycle (zero behavioral change if speculatively valid)
- **Knowledge Graph**: Queries pre-planner for similar past solutions; stores post-success patterns
- **Telemetry Mesh**: Wraps every pipeline stage with spans, exports traces for observability
- **Parallel Coder**: Replaces serial coder_agent call when fan-out yields >1 independent groups

### Configuration
All v5.0 features degrade gracefully to v3.1 behavior when disabled:
- Set any `ASES_V5_*=1` to enable
- Optional `ASES_V5_CVE_DB` path for SBOM CVE enrichment
- Optional `ASES_KG_EMBEDDING` model (default: text-embedding-3-small)
- Optional `ASES_EMBED_ENDPOINT` override (default: OpenAPI)

### Example Usage
```bash
# Enable all v5.0 features for maximum throughput and quality
ASES_V5_PARALLEL_CODER=1 \
ASES_V5_MUTATION=1 \
ASES_V5_PERF_BUDGET=1 \
ASES_V5_SBOM=1 \
ASES_V5_SPECULATIVE=1 \
ASES_V5_KG=1 \
ASES_V5_TELEMETRY=1 \
docker compose -f docker-compose.dev.yml up -d
```
