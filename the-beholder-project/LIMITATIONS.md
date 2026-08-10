# Known Limitations — Phase 1

**Date:** 2026-08-09
**Scope:** Honest accounting of what is and is not done after this session's work,
per Task 1.7.4 of `06_IMPLEMENTATION_PLAN.md`.

---

## What works today (verified by automated tests)

All of the following are covered by `tests/python/` (32/32 passing as of this
writing):

| Connector | What it does | Credentials | Test file |
|-----------|--------------|-------------|-----------|
| `local-files` | Discovers, hashes, and stores arbitrary files from `00_RAW/` | None | `test_local_files_connector.py` |
| `git` | Bundles local Git repos (`git bundle create --all`), extracts commit metadata | None | `test_git_connector.py` |
| `github` | Fetches issues/PRs/releases via GitHub REST API, with pagination + rate-limit backoff | `GITHUB_PAT` env var | `test_github_connector.py` |
| `google-takeout` | Extracts a manually-downloaded Takeout `.zip`, fans services out to `00_RAW/google/{service}/` | None (manual export) | `test_google_takeout_connector.py` |
| `whatsapp` | Parses WhatsApp "Export Chat" `.txt`/`.zip` into structured JSONL + media | None (manual export) | `test_whatsapp_connector.py` |
| `linkedin` | Extracts LinkedIn "Download your data" CSV/JSON export by category | None (manual export) | `test_linkedin_connector.py` |

`github` is the only connector requiring a credential, and it was implemented
using a dependency-injected HTTP client so its tests run fully mocked
(`httpx.MockTransport`) — no real PAT or network access was used to validate
it. **It has not been run against the real GitHub API.** Set `GITHUB_PAT` in
`.env` (scopes: `repo`, `read:user`, `read:org`, `user:email`, `read:project`,
`read:packages` — see `04_CREDENTIAL_REQUIREMENTS.md`) and run
`life-archive ingest github` to validate against your real account before
relying on it.

Each connector: discovers input, hashes it, writes an immutable copy under
`00_RAW/`, records a full-provenance `ManifestEntry` in
`01_MANIFEST/source_manifest.jsonl`, and is idempotent (re-running does not
duplicate raw storage; repeats are marked `DUPLICATE_OF`).

All connectors are wired into the CLI: `life-archive ingest <source>` and
`life-archive sources`.

## What is explicitly NOT done, and why

### 1. Not tested against real user data
The four manual-export/local connectors (`google-takeout`, `whatsapp`, `linkedin`,
and indirectly `git`) were tested against **synthetic fixtures** built in the
test suite (fake emails, fake chat transcripts, fake CSV rows, throwaway git repos).
`github` was tested against a fully mocked HTTP transport. None have been run
against a real Google Takeout export, real WhatsApp chat, or real LinkedIn data
export, because none have been provided. Real exports may use formats, encodings,
or edge cases (locale-specific date formats, unusual folder names, corrupted
archives) not covered by the synthetic fixtures. **Action needed:** drop a real
export into the connector's `incoming/` folder and re-run before relying on this
for actual archival use.

### 2. No infrastructure is deployed
`docker-compose.yml` and `.env.example` were written per spec Section 2.1, but
**Docker Desktop cannot currently start** on this machine (WSL2 is blocked by a
BIOS virtualization setting per `01_ARCHITECTURE_ASSESSMENT.md`). Consequently:
- No PostgreSQL — the SQLAlchemy models in `db/__init__.py` exist but are only
  exercised against a temporary SQLite database in this environment, not the
  production Postgres schema.
- No Meilisearch/Qdrant — every connector's `index()` method is a stub (`# TODO`).
  Search and semantic embeddings do not exist yet.
- No Neo4j — every connector's `normalize()` method is a stub. There is no
  knowledge graph; `Person`/`Organization`/`GitCommit`/`Conversation` canonical
  schemas are not yet emitted anywhere.
- No n8n/Traefik — no orchestration or scheduled/recurring ingestion exists.
  All ingestion is manual (`life-archive ingest <source>`).

### 3. `github` connector implemented but unverified against the live API
The connector (`python/life_archive/connectors/github.py`) fetches issues, pull
requests, and releases with pagination and rate-limit backoff, but a GitHub
Personal Access Token has not been provided (`04_CREDENTIAL_REQUIREMENTS.md`),
so **no live API calls have been made**. All 6 tests use `httpx.MockTransport`.
Comments, stars, and workflow runs (mentioned in `03_CONNECTOR_INVENTORY.md`
section 1.6) are not yet fetched — only issues/PRs/releases, left as `# TODO`
for a future iteration.

### 4. Phase 2 (Google OAuth: Gmail, Drive, Photos, YouTube, Calendar, Contacts)
Not started. Requires a Google Cloud OAuth 2.0 client that only the user can
create and authorize — this is explicitly gated behind pilot success per
`04_CREDENTIAL_REQUIREMENTS.md`'s progressive-credential-request principle.

### 5. Phase 3+ (LMS, social exports, research/validation/discovery engines,
knowledge graph, publishing pipeline)
Not started — these depend on Phase 2 data and the infrastructure in item 2 above.

### 6. Hashing caveats
- `google-takeout` and `linkedin`: when the input is a single `.zip` file, the
  original zip is hashed directly (SHA-256) for provenance. When the input is
  an already-extracted directory (no single canonical byte-stream), a
  deterministic `(relative_path, size)` manifest is hashed instead — this is
  weaker provenance than a true content hash and is documented in each
  connector's `hash()` docstring.
- `whatsapp`: the manifest-level hash covers the parsed message list
  (sender+timestamp+text), not the raw `_chat.txt` bytes, so re-exporting the
  same conversation with different WhatsApp app formatting could produce a
  different hash even if the conversation content is unchanged. This is a
  known trade-off, not a bug.
- xxHash64 is only populated for `local-files` and `git` (whole-file streaming
  hashes); the other three connectors leave it `None` since there's no single
  file to stream-hash the same way.

### 7. TypeScript implementation (`src/`) does not exist
By agreement with the user, only the Python implementation
(`python/life_archive/`) was built out this session. `package.json` still lists
the intended TS dependencies, but `src/cli/`, `src/connectors/`, etc. remain
empty.

---

## Recommended next steps, in priority order

1. Fix the BIOS/WSL2 blocker and run `docker compose up -d` to bring up
   Postgres/Neo4j/Qdrant/MinIO/Redis/Meilisearch/n8n.
2. Drop real Google Takeout / WhatsApp / LinkedIn exports into their
   respective `incoming/` folders and re-run the connectors to validate
   against real data.
3. Implement `index()` (Meilisearch + Qdrant) and `normalize()` (Neo4j +
   canonical schemas) for each connector once infra is up.
4. Obtain a GitHub PAT and implement the `github` connector.
5. Only after the above: begin Phase 2 (Google OAuth connectors).
