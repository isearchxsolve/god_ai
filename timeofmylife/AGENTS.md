# 🚨 TOP PRIORITY AGENT RULES 🚨

1. **DETAILED WORKLOG SUMMARIES:** The `MASTER_WORKLOG.md` entry MUST NEVER be a simple one-line summary. Each and every action, observation, and step must be detailed extensively in the worklog. Make it a habit. This is the absolute top priority.
2. **INCREMENTAL COMMITS:** Incremental commits should be done continuously. This is the second highest priority. Make it a habit.

### THREE ARCHITECTURAL PILLARS (MANDATORY FOR ALL AGENTS)
1. **Business Vision Compliance:** This is the highest priority. All actions must align with the end goal of a production-ready, monetizable product.
2. **Open-Ended & Deep-Dive Audits:** Do not perform shallow or baseline audits. Look for hidden gaps and perform deep open-ended investigations.
3. **Extreme Priority on UI Polish & Research:** The UI is the FIRST priority. It must be highly polished, pixel-perfect, and feature a "wow" effect (glassmorphism, 2026 state-of-the-art design). Furthermore, the UI MUST be well-researched. When given a target (e.g., "build an OiiOii clone"), the agent MUST search the internet to study the actual look and feel of the target UI before proceeding, ensuring a well-grounded visual replication. A businessman will forgive backend glitches if the UI is breathtaking.

---

# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains numbered Markdown assessment and planning documents for the Life Archive platform. Keep those files in sequence (`01_...md`, `02_...md`, etc.) so readers can follow the audit trail.

The planned implementation structure is described in `06_IMPLEMENTATION_PLAN.md`. When adding code, use the proposed layout: `LIFE_ARCHIVE/` for local archive data, `lib/` for core TypeScript/Python libraries, `schemas/` for shared contracts, connector code under paths such as `connectors/local-files/`, and tests colocated or under `tests/`.

## Build, Test, and Development Commands

There is no package manifest or runnable app yet. Until `package.json`, `pyproject.toml`, or `docker-compose.yml` exists, use documentation checks only:

```powershell
rg --files
git diff --check
```

Expected future commands include:

```powershell
bun install              # install TypeScript dependencies
bun test                 # run Bun tests
python -m pytest         # run Python tests
docker compose up -d     # start local platform services
docker compose ps        # verify service health
```

Update this section when tooling lands.

## Coding Style & Naming Conventions

Use Markdown for repository documentation, with concise headings, dated status notes, and tables where comparisons beat prose. Preserve the numbered-document naming pattern for major reports.

For future code, prefer TypeScript for orchestration-facing libraries and Python for data processing or ML-heavy work. Use descriptive module names such as `manifest`, `hash`, `provenance`, and connector names like `local-files`. Keep secrets out of committed files; document required variables in `.env.example`.

## Testing Guidelines

No automated tests exist yet. For documentation-only changes, run `git diff --check` and review Markdown formatting manually.

When code is introduced, add unit tests for manifest writing/reading, hashing, schema validation, and connector behavior. Name tests after behavior, for example `manifest_write_read.test.ts` or `test_hash_streaming.py`. Include regression tests for provenance and immutability guarantees.

## Commit & Pull Request Guidelines

Existing commit messages are short and informal. New commits should be clearer and action-oriented, for example `Add phase 1 contributor guide` or `Document connector credential requirements`.

Pull requests should include a summary, affected documents or modules, verification performed, and follow-up tasks. For infrastructure or UI changes, include relevant screenshots, logs, or `docker compose ps` output. Link issues or planning sections when available.

## Security & Configuration Tips

This project is expected to handle personal archive data and credentials. Never commit `.env`, raw exports, API keys, access tokens, or generated archive contents. Use `.env.example` for placeholders and document credential requirements in `04_CREDENTIAL_REQUIREMENTS.md`.
