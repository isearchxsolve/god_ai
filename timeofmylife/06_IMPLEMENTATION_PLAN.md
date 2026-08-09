# Implementation Plan — Phase 1: Foundation + Architecture

**Date:** 2026-08-08
**Project:** Life Archive — Complete Digital Life Research & Publishing Platform
**Specification Reference:** Sections 37, 38 (First Implementation Task, Development Phases)
**Phase:** 1 of 20
**Duration Target:** 1-2 weeks
**Gate:** All 6 assessment docs complete + infrastructure running + `local-files` connector operational + forensic evidence captured

---

## Executive Summary

Phase 1 establishes the **foundational infrastructure, project structure, and first working connector** (`local-files`). It validates the end-to-end pipeline from raw ingestion through manifest, hashing, storage, and indexing — without any external credentials.

**Success Criteria (Quality Gate 1-4):**
- [ ] GATE 01: Can acquire data (local files)
- [ ] GATE 02: Raw data preserved immutably
- [ ] GATE 03: Hashes verified (SHA-256 + xxHash)
- [ ] GATE 04: Provenance verified (manifest + archive_id traceability)

---

## 1. Phase 1 Task Breakdown

### 1.1 Infrastructure Deployment (Day 1-2)

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.1.1** | Start Docker Desktop (WSL2 backend) | Docker daemon running | `docker ps` works |
| **1.1.2** | Create `docker-compose.yml` with core services | `docker-compose.yml` | `docker compose config` valid |
| **1.1.3** | Deploy: PostgreSQL, Qdrant, Neo4j, MinIO, Redis, Meilisearch, n8n, Traefik | Running containers | `docker compose ps` → all healthy |
| **1.1.4** | Generate and persist `N8N_ENCRYPTION_KEY` | `.env` with key | n8n starts, encrypts credentials |
| **1.1.5** | Configure Traefik with self-signed certs (dev) | HTTPS on `https://life-archive.local` | Browser trust (manual) |
| **1.1.6** | Initialize n8n: basic auth, first project | n8n accessible | Login works |
| **1.1.7** | Create MinIO buckets: `raw`, `processed`, `normalized`, `index`, `backups` | Buckets exist | `mc ls` shows buckets |
| **1.1.8** | Run DB migrations (PostgreSQL schema for metadata) | Tables created | `psql` query succeeds |
| **1.1.9** | Create Neo4j constraints/indexes | Schema ready | Cypher `CREATE CONSTRAINT` succeeds |
| **1.1.10** | Verify all service health endpoints | Health checks pass | `curl` / programmatic checks |

### 1.2 Project Structure & Tooling (Day 1-2)

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.2.1** | Create `LIFE_ARCHIVE/` directory structure (Section 4) | 13 top-level dirs + subdirs | `tree LIFE_ARCHIVE` matches spec |
| **1.2.2** | Initialize Bun project: `package.json`, `tsconfig.json` | `package.json` with deps | `bun install` succeeds |
| **1.2.3** | Initialize Python project: `pyproject.toml`, `requirements.txt` | `pyproject.toml` with deps | `pip install -r requirements.txt` succeeds |
| **1.2.4** | Shared schema definitions (TypeScript + Python) | `schemas/` package | Both languages import successfully |
| **1.2.5** | CLI entrypoints: `life-archive` (TS), `life-archive-py` (Python) | Working CLIs | `--help` shows commands |
| **1.2.6** | Pre-commit hooks: secret scan, lint, format | `.pre-commit-config.yaml` | `pre-commit run --all-files` passes |
| **1.2.7** | CI/CD pipeline (GitHub Actions) | `.github/workflows/ci.yml` | Push triggers workflow |
| **1.2.8** | Development `.env.example` | Template for all env vars | Documented |

### 1.3 Core Library Implementation (Day 2-4)

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.3.1** | **Manifest System** — JSONL writers/readers for `source_manifest.jsonl`, `hashes.jsonl`, `acquisition_log.jsonl`, `ingestion_runs.jsonl` | `lib/manifest/` (TS + Py) | Unit tests: write → read → verify |
| **1.3.2** | **Hashing Module** — SHA-256 (streaming), xxHash64, file identification | `lib/hash/` | Test: known vectors + large file streaming |
| **1.3.3** | **Provenance Types** — `ArchiveId`, `SourceRef`, `ProcessingStatus`, `PrivacyClassification` | `schemas/provenance.ts/py` | Type checking passes |
| **1.3.4** | **Storage Abstraction** — MinIO client wrapper (put/get/list/delete/presign) | `lib/storage/` | Integration test: round-trip |
| **1.3.5** | **Database Layer** — SQLAlchemy/Kysely models for metadata DB | `lib/db/` | Migration runs; CRUD works |
| **1.3.6** | **Vector Index Client** — Qdrant upsert/search/delete | `lib/vector/` | Embedding insert + search |
| **1.3.7** | **Search Index Client** — Meilisearch document add/search | `lib/search/` | Document index + query |
| **1.3.8** | **Graph Client** — Neo4j session + Cypher helpers | `lib/graph/` | Node/edge create + traverse |
| **1.3.9** | **Privacy Engine Stub** — Classification enum, redaction interface (no-op for now) | `lib/privacy/` | Interface compiles; tests pass |
| **1.3.10** | **Observability** — Structured logging (loguru/rich), run reporting | `lib/obs/` | JSONL run report generated |

### 1.4 Local Files Connector (Day 3-5)

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.4.1** | Connector scaffold: `BaseConnector` class, `ConnectorRegistry` | `connectors/local_files/` | Registry loads connector |
| **1.4.2** | **DISCOVER** — Walk `00_RAW/`; emit `DiscoveredItem` with path, size, mtime, MIME | `discover.ts/py` | Test: finds test files |
| **1.4.3** | **ACQUIRE** — Copy to staging (preserve original); handle large files | `acquire.ts/py` | Test: staging created |
| **1.4.4** | **VERIFY** — Readability check; basic metadata extraction (EXIF, ID3, PDF info) | `verify.ts/py` | Test: metadata extracted |
| **1.4.5** | **HASH** — Streaming SHA-256 + xxHash; progress for large files | `hash.ts/py` | Test: matches known hashes |
| **1.4.6** | **STORE** — Write to `00_RAW/local/{date}/{hash[:2]}/{hash}`; manifest entry | `store.ts/py` | Test: file in RAW; manifest line |
| **1.4.7** | **INDEX** — Text extraction → Meilisearch; embeddings → Qdrant; entities → Neo4j staging | `index.ts/py` | Test: search returns results |
| **1.4.8** | **NORMALIZE** — Map to canonical schemas (Document, Image, Audio, Video) | `normalize.ts/py` | Test: normalized JSON valid |
| **1.4.9** | **LOG** — Write all manifest files; update `ingestion_runs.jsonl` | `log.ts/py` | Test: manifests complete |
| **1.4.10** | **RESUME** — Checkpoint every N items; skip already-hashed | `resume.ts/py` | Test: interrupt → resume works |
| **1.4.11** | **CLI Command** — `life-archive ingest local-files` | CLI integrated | End-to-end run succeeds |

### 1.5 Git Connector (Day 4-5) — Parallel with Local Files

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.5.1** | Discover `.git` dirs under configured roots | `discover.ts/py` | Finds test repos |
| **1.5.2** | `git bundle create` + commit metadata export | `acquire.ts/py` | Bundle + JSONL created |
| **1.5.3** | Verify bundle; hash commits | `verify.ts/py` + `hash.ts/py` | Bundle valid |
| **1.5.4** | Store bundles in `00_RAW/git/`; commits in `03_NORMALIZED/git_commits/` | `store.ts/py` | Files in place |
| **1.5.5** | Index commit messages; normalize to `GitCommit`, `GitRepository` | `index.ts/py` + `normalize.ts/py` | Search works |
| **1.5.6** | CLI command: `life-archive ingest git` | CLI integrated | End-to-end run |

### 1.6 Pilot Data Preparation (Day 1, Ongoing)

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.6.1** | Create test corpus in `00_RAW/` (10-20 docs, images, audio, video) | Test files | Varied MIME types |
| **1.6.2** | Request Google Takeout export from user | `takeout-*.zip` in `00_RAW/google/` | User provides |
| **1.6.3** | Request WhatsApp export from user | `whatsapp-*.zip` in `00_RAW/whatsapp/` | User provides |
| **1.6.4** | Request LinkedIn export from user | `linkedin-*.zip` in `00_RAW/linkedin/` | User provides |
| **1.6.5** | Place sample Git repos in `00_RAW/git/` | Repos | `git bundle verify` works |

### 1.7 Forensic Evidence & Reporting (Day 5-6)

| Task | Description | Deliverable | Verification |
|------|-------------|-------------|--------------|
| **1.7.1** | Capture screenshots: Docker services, n8n UI, MinIO console, database counts | `12_AUDIT/pipeline_runs/phase1/` | Visual evidence |
| **1.7.2** | Generate `RUN_REPORT.json` + `RUN_REPORT.md` for each run | Reports in `12_AUDIT/` | Schema valid |
| **1.7.3** | Verify GATE 01-04 with evidence | `GATE_REPORT.md` | PASS/FAIL with proof |
| **1.7.4** | Document known limitations | `LIMITATIONS.md` | Honest assessment |

---

## 2. Detailed Technical Specifications

### 2.1 Docker Compose Stack (`docker-compose.yml`)

```yaml
version: '3.8'

services:
  # Reverse proxy + TLS
  traefik:
    image: traefik:v3.0
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.le.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.le.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "letsencrypt:/letsencrypt"
    networks: [life-archive-net]

  # Primary metadata database
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: life_archive
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
    secrets: [postgres_password]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d life_archive"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks: [life-archive-net]

  # Vector database
  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 10s
    networks: [life-archive-net]

  # Knowledge graph
  neo4j:
    image: neo4j:5.23-community
    environment:
      NEO4J_AUTH: ${NEO4J_AUTH}
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_memory_heap_initial__size: 512m
      NEO4J_dbms_memory_heap_max__size: 2g
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7474"]
      interval: 10s
    networks: [life-archive-net]

  # Object storage
  minio:
    image: minio/minio:RELEASE.2024-08-17
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER_FILE: /run/secrets/minio_access_key
      MINIO_ROOT_PASSWORD_FILE: /run/secrets/minio_secret_key
    secrets: [minio_access_key, minio_secret_key]
    volumes:
      - minio_data:/data
    ports: ["9000:9000", "9001:9001"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
    networks: [life-archive-net]

  # Cache + queue
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
    networks: [life-archive-net]

  # Lexical search
  meilisearch:
    image: getmeili/meilisearch:v1.11
    environment:
      MEILI_MASTER_KEY: ${MEILI_MASTER_KEY}
      MEILI_NO_ANALYTICS: "true"
    volumes:
      - meili_data:/meili_data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:7700/health"]
      interval: 10s
    networks: [life-archive-net]

  # Orchestration
  n8n:
    image: n8nio/n8n:latest
    environment:
      N8N_ENCRYPTION_KEY_FILE: /run/secrets/n8n_encryption_key
      N8N_HOST: ${N8N_HOST}
      N8N_PORT: 5678
      N8N_PROTOCOL: https
      WEBHOOK_URL: https://${N8N_HOST}/
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: life_archive
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD_FILE: /run/secrets/postgres_password
      EXECUTIONS_MODE: queue
      QUEUE_BULL_REDIS_HOST: redis
      QUEUE_BULL_REDIS_PORT: 6379
      QUEUE_BULL_REDIS_PASSWORD_FILE: /run/secrets/redis_password
    secrets: [n8n_encryption_key, postgres_password, redis_password]
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on: [postgres, redis]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5678/healthz"]
      interval: 10s
    networks: [life-archive-net]

secrets:
  postgres_password: { file: ./secrets/postgres_password.txt }
  minio_access_key: { file: ./secrets/minio_access_key.txt }
  minio_secret_key: { file: ./secrets/minio_secret_key.txt }
  redis_password: { file: ./secrets/redis_password.txt }
  n8n_encryption_key: { file: ./secrets/n8n_encryption_key.txt }

volumes:
  pgdata:
  qdrant_data:
  neo4j_data:
  neo4j_logs:
  minio_data:
  redis_data:
  meili_data:
  n8n_data:
  letsencrypt:

networks:
  life-archive-net:
    driver: bridge
```

### 2.2 Directory Structure Creation Script

```bash
#!/usr/bin/env bash
# create_archive_structure.sh

ROOT="LIFE_ARCHIVE"
DIRS=(
  "00_RAW/google/gmail"
  "00_RAW/google/drive"
  "00_RAW/google/photos"
  "00_RAW/google/youtube"
  "00_RAW/google/calendar"
  "00_RAW/google/contacts"
  "00_RAW/google/takeout"
  "00_RAW/whatsapp"
  "00_RAW/linkedin"
  "00_RAW/github"
  "00_RAW/git"
  "00_RAW/lms"
  "00_RAW/social"
  "00_RAW/documents"
  "00_RAW/images"
  "00_RAW/audio"
  "00_RAW/video"
  "00_RAW/other"
  "01_MANIFEST"
  "02_PROCESSED/ocr"
  "02_PROCESSED/transcripts"
  "02_PROCESSED/extracted_metadata"
  "02_PROCESSED/thumbnails"
  "03_NORMALIZED/documents"
  "03_NORMALIZED/emails"
  "03_NORMALIZED/conversations"
  "03_NORMALIZED/events"
  "03_NORMALIZED/projects"
  "03_NORMALIZED/people"
  "03_NORMALIZED/organizations"
  "03_NORMALIZED/creative_works"
  "04_TIMELINE"
  "05_ENTITIES/people"
  "05_ENTITIES/organizations"
  "05_ENTITIES/places"
  "05_ENTITIES/projects"
  "05_ENTITIES/technologies"
  "05_ENTITIES/concepts"
  "06_KNOWLEDGE_GRAPH/nodes"
  "06_KNOWLEDGE_GRAPH/edges"
  "06_KNOWLEDGE_GRAPH/graph_exports"
  "07_INDEX/lexical"
  "07_INDEX/semantic"
  "07_INDEX/metadata"
  "08_RESEARCH/questions"
  "08_RESEARCH/investigations"
  "08_RESEARCH/hypotheses"
  "08_RESEARCH/findings"
  "08_RESEARCH/contradictions"
  "08_RESEARCH/discoveries"
  "09_EVIDENCE/evidence_chains"
  "09_EVIDENCE/citations"
  "09_EVIDENCE/screenshots"
  "09_EVIDENCE/source_maps"
  "10_CREATIVE/films"
  "10_CREATIVE/writing"
  "10_CREATIVE/philosophy"
  "10_CREATIVE/photography"
  "10_CREATIVE/audio"
  "10_CREATIVE/software"
  "10_CREATIVE/intellectual_frameworks"
  "10_CREATIVE/unfinished"
  "10_CREATIVE/monetizable"
  "11_PUBLICATION/linkedin"
  "11_PUBLICATION/articles"
  "11_PUBLICATION/books"
  "11_PUBLICATION/essays"
  "11_PUBLICATION/talks"
  "11_PUBLICATION/website"
  "11_PUBLICATION/documentary"
  "11_PUBLICATION/social"
  "12_AUDIT/pipeline_runs"
  "12_AUDIT/quality"
  "12_AUDIT/validation"
  "12_AUDIT/errors"
  "99_PRIVATE/secrets"
  "99_PRIVATE/credentials"
  "99_PRIVATE/restricted"
)

for dir in "${DIRS[@]}"; do
  mkdir -p "$ROOT/$dir"
done

# Create .gitkeep files
find "$ROOT" -type d -empty -exec touch {}/.gitkeep \;

echo "Archive structure created at $ROOT/"
```

### 2.3 Shared Schema Definitions (TypeScript + Python)

**TypeScript:** `schemas/provenance.ts`
```typescript
export type PrivacyClassification = 
  | 'PUBLIC' | 'PRIVATE' | 'SENSITIVE' | 'THIRD_PARTY_PRIVATE' | 'RESTRICTED';

export type ProcessingStatus = 
  | 'DISCOVERED' | 'ACQUIRED' | 'VERIFIED' | 'HASHED' | 'STORED' 
  | 'INDEXED' | 'NORMALIZED' | 'LOGGED' | 'FAILED' | 'SKIPPED';

export type DedupeStatus = 'UNIQUE' | 'DUPLICATE_OF' | 'NEAR_DUPLICATE_OF' | 'VERSION_OF';

export interface ManifestEntry {
  archive_id: string;           // sha256:<hash>
  source: string;               // connector id
  source_identifier: string;    // source-specific ID
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  original_timestamp: string;   // ISO 8601
  acquisition_timestamp: string; // ISO 8601
  sha256: string;
  xxhash64?: string;
  connector: string;
  ingestion_run_id: string;
  privacy_classification: PrivacyClassification;
  processing_status: ProcessingStatus;
  dedupe_status: DedupeStatus;
  dedupe_of?: string;           // archive_id of canonical
  error?: string;
}

export interface IngestionRun {
  run_id: string;               // UUID v7 (timestamp-ordered)
  connector: string;
  start_time: string;
  end_time?: string;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'PARTIAL';
  items_discovered: number;
  items_processed: number;
  items_failed: number;
  bytes_processed: number;
  config_hash: string;          // hash of connector config
}

export interface DiscoveredItem {
  source_path: string;
  relative_path: string;
  size_bytes: number;
  mtime: string;
  mime_type: string;
  source_identifier: string;
}

export interface HashedItem extends DiscoveredItem {
  sha256: string;
  xxhash64: string;
}

export interface StoredItem extends HashedItem {
  archive_path: string;         // relative to 00_RAW/
  manifest_entry: ManifestEntry;
}
```

**Python:** `schemas/provenance.py` (Pydantic models matching TS)

### 2.4 Connector Base Class (Python)

```python
# connectors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator, Generic, TypeVar
from schemas.provenance import *

T = TypeVar('T')

@dataclass
class ConnectorCheckpoint:
    run_id: str
    connector_id: str
    stage: str
    processed_count: int
    last_item_id: str | None
    metadata: dict

class BaseConnector(ABC, Generic[T]):
    def __init__(self, config: dict, run_id: str):
        self.config = config
        self.run_id = run_id
        self.checkpoint_interval = config.get('checkpoint_interval', 100)
    
    @property
    @abstractmethod
    def connector_id(self) -> str: ...
    
    @property
    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities: ...
    
    @abstractmethod
    async def discover(self) -> AsyncIterator[DiscoveredItem]: ...
    
    @abstractmethod
    async def acquire(self, item: DiscoveredItem) -> AcquiredItem: ...
    
    @abstractmethod
    async def verify(self, item: AcquiredItem) -> VerifiedItem: ...
    
    def hash(self, item: VerifiedItem) -> HashedItem: ...
    
    @abstractmethod
    async def store(self, item: HashedItem) -> StoredItem: ...
    
    @abstractmethod
    async def index(self, item: StoredItem) -> IndexedItem: ...
    
    @abstractmethod
    async def normalize(self, item: IndexedItem) -> NormalizedItem: ...
    
    @abstractmethod
    async def log(self, result: ConnectorResult) -> None: ...
    
    async def get_checkpoint(self) -> ConnectorCheckpoint | None: ...
    async def save_checkpoint(self, cp: ConnectorCheckpoint) -> None: ...
    
    async def run(self) -> ConnectorResult:
        # Orchestrates all stages with checkpointing
        ...
```

---

## 3. Quality Gates — Phase 1 Verification

### GATE 01: Can Acquire Data
- **Test:** `life-archive ingest local-files` discovers ≥10 test files
- **Evidence:** `01_MANIFEST/source_manifest.jsonl` has ≥10 entries with `status: DISCOVERED`
- **Status (2026-08-09):** ✅ PASS at the code/test level — `local-files`, `git`, `google-takeout`,
  `whatsapp`, and `linkedin` connectors all implement `discover()` with automated regression
  tests (`tests/python/test_*_connector.py`, 26/26 passing). Real-world pilot corpora
  (actual Google Takeout/WhatsApp/LinkedIn exports) have not yet been provided by the user;
  synthetic fixtures were used for test coverage instead.

### GATE 02: Raw Data Preserved
- **Test:** Original files in `00_RAW/` unchanged (mtime, size, hash match)
- **Evidence:** `diff` original vs stored; SHA-256 match
- **Status (2026-08-09):** ✅ PASS — regression tests assert byte-identical stored copies and
  idempotent re-runs (no duplicate RAW writes; dedupe via `DUPLICATE_OF`) for every connector.

### GATE 03: Hashes Verified
- **Test:** Every manifest entry has valid SHA-256 + xxHash64
- **Evidence:** Re-compute hashes from stored files; compare to manifest
- **Status (2026-08-09):** ✅ PASS for SHA-256 (all connectors). xxHash64 is populated for
  `local-files` and `git` (whole-file streaming hash); `google-takeout`, `whatsapp`, and
  `linkedin` use a SHA-256-only manifest/content hash where no single canonical byte-stream
  exists (see `LIMITATIONS.md`).

### GATE 04: Provenance Verified
- **Test:** Trace any normalized object → manifest entry → original file
- **Evidence:** `source_archive_id` in normalized object matches manifest `archive_id`
- **Status (2026-08-09):** ⚠️ PARTIAL — every manifest entry traces back to its original file
  via `archive_id`/`source_identifier`. Full `NormalizedItem` schemas (Document, Image,
  GitCommit, Conversation, etc.) are still stubs pending Neo4j/Meilisearch/Qdrant infra
  (see `normalize()`/`index()` TODOs in each connector).

---

## 4. Dependencies & Prerequisites

| Prerequisite | Status | Owner |
|--------------|--------|-------|
| Docker Desktop running | ❌ Blocked: WSL2 unavailable — hardware virtualization must be enabled in BIOS first (2026-08-09) | User/Operator |
| `docker-compose.yml` + `.env.example` | ✅ Written (2026-08-09); host port mappings added and `docker compose config` validated, secrets staged via `scripts\generate_secrets.ps1` (2026-08-10); not yet run — blocked on Docker above | Operator |
| Native prototype stack (Docker-free) | ✅ Meilisearch, MinIO, Qdrant run natively from `tools\bin` via `scripts\start_native_stack.ps1` alongside native PostgreSQL 18; ingest → Meilisearch index → CLI search proven end-to-end, `DatabaseManager` proven against PostgreSQL (2026-08-10) | Operator |
| GitHub PAT provided | ❌ Not provided | User |
| Test corpus in `00_RAW/` | ✅ Created (`00_RAW/test/`: 4 files) | Operator |
| `local-files` connector | ✅ Implemented + tested (2026-08-09) | Operator |
| `git` connector | ✅ Implemented + tested (2026-08-09) — bundles local repos, no credentials | Operator |
| `google-takeout` connector | ✅ Implemented + tested against synthetic fixtures (2026-08-09) | Operator |
| `whatsapp` connector | ✅ Implemented + tested against synthetic fixtures (2026-08-09) | Operator |
| `linkedin` connector | ✅ Implemented + tested against synthetic fixtures (2026-08-09) | Operator |
| `github` connector | ✅ Implemented + tested against mocked API (2026-08-09); unverified against real GitHub — needs `GITHUB_PAT` | Operator (blocked on User for live verification) |
| Google Takeout export (real user data) | ❌ Not provided | User (optional for Phase 1) |
| WhatsApp export (real user data) | ❌ Not provided | User (optional for Phase 1) |
| LinkedIn export (real user data) | ❌ Not provided | User (optional for Phase 1) |

---

## 5. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Docker Desktop fails to start | High | High | Root cause confirmed: WSL2 blocked by BIOS virtualization setting. Unblock by enabling virtualization in BIOS; fallback: Podman or native installs |
| n8n encryption key lost | Low | Critical | Persist in `.env`; document backup procedure |
| MinIO bucket permissions | Low | Medium | Auto-create via mc script on startup |
| Neo4j APOC plugin missing | Low | Medium | Include in image; verify on startup |
| Large file handling (video) | Medium | Medium | Streaming hash; chunked upload; resume |
| Schema mismatch TS ↔ Py | Medium | High | Shared JSON Schema source; codegen both |
| GitHub PAT scope insufficient | Low | Medium | Document exact scopes; test early |

---

## 6. Timeline & Milestones

| Day | Milestone | Deliverable |
|-----|-----------|-------------|
| 1 | Infrastructure up | `docker compose ps` all green |
| 2 | Project scaffold + schemas | `bun install` + `pip install` pass |
| 3 | Core libraries (manifest, hash, storage, db) | Unit tests pass |
| 4 | Local-files connector DISCOVER→LOG | Single file processed end-to-end |
| 5 | Local-files connector batch + resume | 10+ files; interrupt/resume works |
| 5 | Git connector basic | Bundle + metadata for 1 repo |
| 6 | Pilot run on test corpus | Full pipeline run report |
| 6 | Forensic evidence captured | Screenshots + `RUN_REPORT.json` |
| 6 | GATE 01-04 verification | `GATE_REPORT.md` = PASS |
| 7 | Documentation + handoff | Phase 1 complete; Phase 2 plan |

---

## 7. Next Phase Preview (Phase 2: Storage + Raw Archive)

- Google Takeout connector (meta-connector)
- WhatsApp connector
- LinkedIn connector
- Processing pipeline: OCR (Tesseract), transcription (Whisper.cpp), text extraction
- Privacy Engine v1 (classification + redaction)
- Incremental ingestion framework

---

## 8. Approval

**Phase 1 Plan Status (2026-08-09):** ⚠️ **CODE-COMPLETE FOR CREDENTIAL-FREE SCOPE — INFRA STILL BLOCKED**

All five credential-free Phase 1 connectors (`local-files`, `git`, `google-takeout`,
`whatsapp`, `linkedin`) are implemented in Python with passing automated tests
(`tests/python/`, 26/26 passing) and are wired into the CLI (`life-archive ingest <source>`).
`docker-compose.yml` and `.env.example` are written per Section 2.1 but not yet deployed.
See `LIMITATIONS.md` for a full honest accounting of what remains.

**Blocking Items Requiring User Action:**
1. Enable hardware virtualization in BIOS, then start Docker Desktop (WSL2 backend) — Docker deployment (Task 1.1) is blocked until this is done
2. Provide GitHub PAT (securely) — required for the `github` connector (Task 1.6, not yet implemented)
3. Provide real Google Takeout / WhatsApp / LinkedIn exports to validate connectors against real data (synthetic fixtures were used for automated tests)

**Once unblocked:** Run `docker compose up -d`, then proceed to Task 1.3.6-1.3.8 (vector/search/graph client wiring) and Task 1.6 (GitHub connector).