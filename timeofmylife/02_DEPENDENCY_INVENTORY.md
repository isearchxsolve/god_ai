# Dependency Inventory

**Date:** 2026-08-08
**Project:** Life Archive — Complete Digital Life Research & Publishing Platform
**Environment:** C:/god_ai/timeofmylife

---

## Executive Summary

This document catalogs all external dependencies required to build and operate the Life Archive system. Dependencies are categorized by layer (infrastructure, runtime, libraries, APIs) and assessed for availability, licensing, and replacement risk.

**Total Dependencies Identified:** 87
- **Infrastructure Services:** 12 (Docker containers)
- **Runtime/CLI Tools:** 8
- **Python Packages:** 34
- **TypeScript/JS Packages (Bun):** 23
- **External APIs/Services:** 10

---

## 1. Infrastructure Services (Docker Containers)

| Service | Image | Version | Purpose | Port | Volume | Licensing | Replacement Risk |
|---------|-------|---------|---------|------|--------|-----------|------------------|
| **PostgreSQL** | `postgres` | 16-alpine | Primary metadata DB, n8n backend | 5432 | `pgdata` | PostgreSQL License (MIT-like) | Low — Standard SQL |
| **Qdrant** | `qdrant/qdrant` | latest | Vector/semantic search | 6333, 6334 | `qdrant_data` | Apache 2.0 | Low — REST/gRPC API standard |
| **Neo4j** | `neo4j` | 5.23-community | Knowledge graph | 7474, 7687 | `neo4j_data`, `neo4j_logs` | GPL 3.0 (Community) | Medium — Cypher query language |
| **MinIO** | `minio/minio` | RELEASE.2024-08-17 | S3-compatible object storage | 9000, 9001 | `minio_data` | AGPL 3.0 | Low — S3 API standard |
| **Redis** | `redis` | 7-alpine | Caching, n8n queue, rate limiting | 6379 | `redis_data` | BSD 3-clause (until 7.4), then SSPl | Low — Redis protocol standard |
| **Meilisearch** | `getmeili/meilisearch` | v1.11 | Full-text lexical search | 7700 | `meili_data` | MIT | Low — REST API standard |
| **n8n** | `n8nio/n8n` | latest | Workflow orchestration | 5678 | `n8n_data` | Sustainable Use License | **High** — Vendor-specific workflow format |
| **Traefik** | `traefik` | v3.0 | Reverse proxy, SSL termination | 80, 443, 8080 | `traefik_data`, `letsencrypt` | MIT | Low — Standard proxy config |
| **Ollama** | `ollama/ollama` | latest | Local LLM inference (optional) | 11434 | `ollama_data` | MIT | Low — OpenAI-compatible API |
| **Tesseract OCR** | `tesseractshadow/tesseract4re` | latest | OCR processing (sidecar) | — | — | Apache 2.0 | Low — CLI standard |
| **Whisper.cpp** | `ghcr.io/ggml-org/whisper.cpp` | latest | Audio transcription (sidecar) | — | — | MIT | Low — CLI standard |
| **PostgreSQL (pgvector)** | `pgvector/pgvector` | pg16 | Alternative: unified vector+relational | 5432 | `pgvector_data` | PostgreSQL License | Low — If chosen over Qdrant |

**Deployment Strategy:** Single `docker-compose.yml` with profiles for `core`, `ai`, `observability`. All services on dedicated Docker network `life-archive-net`.

---

## 2. Runtime & CLI Tools

| Tool | Version | Installation Method | Purpose | Alternative |
|------|---------|---------------------|---------|-------------|
| **Bun** | 1.3.14 | `curl -fsSL https://bun.sh/install \| bash` | Primary JS/TS runtime, bundler, test runner, package manager | Node.js 20+ |
| **Python** | 3.11.9 | Windows installer / winget | Data processing, ML, OCR, transcription, scripts | — |
| **Docker** | 29.5.3 | Docker Desktop for Windows | Container orchestration | Podman |
| **Git** | 2.x | Git for Windows | Version control | — |
| **GitHub CLI (gh)** | Latest | `winget install GitHub.cli` | GitHub API, repo management | `curl` + API |
| **AWS CLI v2** | Latest | `winget install Amazon.AWSCLI` | S3/MinIO operations, cloud sync | `mc` (MinIO client) |
| **MinIO Client (mc)** | Latest | `dl.min.io/client/mc/release/windows-amd64/mc.exe` | MinIO bucket management | AWS CLI |
| **jq** | 1.7 | `winget install jqlang.jq` | JSON processing in shell | Python `-m json.tool` |

---

## 3. Python Packages (Core Dependencies)

### 3.1 Data Processing & Pipeline
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `pydantic` | `>=2.8` | Data validation, settings, serialization | MIT | Core for all schemas |
| `pydantic-settings` | `>=2.3` | Settings management from env/files | MIT | |
| `python-dotenv` | `>=1.0` | Load `.env` files | BSD | |
| `pyyaml` | `>=6.0` | YAML config parsing | MIT | |
| `orjson` | `>=3.10` | Fast JSON serialization | MIT/Apache-2.0 | 10x faster than stdlib |
| `msgpack` | `>=1.0` | Binary serialization for pipelines | Apache-2.0 | |
| `xxhash` | `>=3.4` | Fast non-cryptographic hashing | BSD | For deduplication hints |
| `hashlib` | stdlib | SHA-256 for provenance | PSF | Built-in |

### 3.2 Database & Storage
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `asyncpg` | `>=0.29` | Async PostgreSQL driver | Apache-2.0 | Primary DB driver |
| `sqlalchemy` | `>=2.0` | ORM + Core for metadata DB | MIT | Async support |
| `alembic` | `>=1.13` | Database migrations | MIT | |
| `redis` | `>=5.0` | Async Redis client | MIT | Caching, queues |
| `minio` | `>=7.2` | S3/MinIO client | AGPL-3.0 | Object storage ops |
| `qdrant-client` | `>=1.10` | Qdrant vector DB client | Apache-2.0 | |
| `neo4j` | `>=5.21` | Neo4j Python driver | GPL-3.0 (driver) | **Check license compatibility** |
| `meilisearch` | `>=0.28` | Meilisearch client | MIT | |

### 3.3 Document Processing
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `pymupdf` (fitz) | `>=1.23` | PDF text extraction, metadata | AGPL-3.0 | **AGPL — consider license impact** |
| `pdfplumber` | `>=0.11` | PDF table/text extraction | MIT | Alternative to pymupdf |
| `python-docx` | `>=1.1` | DOCX parsing | MIT | |
| `openpyxl` | `>=3.1` | XLSX parsing | MIT | |
| `pandas` | `>=2.2` | Structured data processing | BSD-3 | |
| `beautifulsoup4` | `>=4.12` | HTML/XML parsing | MIT | |
| `lxml` | `>=5.2` | Fast XML/HTML parser | BSD | |
| `markitdown` | `>=0.1` | Universal document → Markdown | MIT | Microsoft; converts many formats |

### 3.4 OCR & Computer Vision
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `pytesseract` | `>=0.3` | Tesseract OCR wrapper | GPL-3.0 | Requires system tesseract |
| `paddleocr` | `>=2.7` | Alternative OCR (CNN-based) | Apache-2.0 | Heavy deps; optional |
| `opencv-python-headless` | `>=4.10` | Image preprocessing | Apache-2.0 | |
| `pillow` | `>=10.4` | Image processing | HPND | |

### 3.5 Audio/Video Processing
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `ffmpeg-python` | `>=0.2` | FFmpeg wrapper | Apache-2.0 | Requires system ffmpeg |
| `whisper` | `>=1.1` | OpenAI Whisper (Python) | MIT | Heavy; prefer whisper.cpp CLI |
| `faster-whisper` | `>=1.0` | CTranslate2 Whisper | MIT | Faster, less VRAM |
| `pydub` | `>=0.25` | Audio manipulation | MIT | Requires ffmpeg |
| `mutagen` | `>=1.47` | Audio metadata (ID3, EXIF) | MIT | |

### 3.6 AI/ML & Embeddings
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `openai` | `>=1.40` | OpenAI API client | MIT | |
| `httpx` | `>=0.27` | Async HTTP client for APIs | BSD-3 | |
| `tenacity` | `>=8.3` | Retry logic for API calls | Apache-2.0 | |
| `instructor` | `>=1.5` | Structured LLM outputs | MIT | Pydantic integration |
| `sentence-transformers` | `>=3.0` | Local embeddings (optional) | Apache-2.0 | Heavy; for offline mode |
| `torch` | `>=2.4` | PyTorch (if local embeddings) | BSD | CUDA/CPU variants |

### 3.7 Graph & Analysis
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `networkx` | `>=3.3` | In-memory graph algorithms | BSD-3 | Pilot/analysis only |
| `igraph` | `>=0.11` | High-performance graph (optional) | GPL-3.0 | C core; **GPL** |
| `python-louvain` | `>=0.16` | Community detection | BSD | |

### 3.8 CLI & Observability
| Package | Version Constraint | Purpose | License | Notes |
|---------|-------------------|---------|---------|-------|
| `typer` | `>=0.12` | CLI framework | MIT | |
| `rich` | `>=13.7` | Terminal formatting | MIT | |
| `loguru` | `>=0.7` | Structured logging | MIT | |
| `structlog` | `>=24.1` | Structured logging (alt) | Apache-2.0 | |
| `prometheus-client` | `>=0.19` | Metrics exposition | Apache-2.0 | |
| `tqdm` | `>=4.66` | Progress bars | MIT/MPL-2.0 | |

---

## 4. TypeScript/JS Packages (Bun)

### 4.1 Core & Runtime
| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `typescript` | `^5.5` | Type checking | Apache-2.0 |
| `@types/node` | `^20.14` | Node types | MIT |
| `zod` | `^3.23` | Schema validation (shared with Python via JSON Schema) | MIT |
| `effect` | `^3.10` | Functional error handling, retry, scheduling | MIT |
| `neverthrow` | `^6.2` | Result type for error handling | MIT |

### 4.2 Database & Storage Clients
| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `pg` | `^8.12` | PostgreSQL client | MIT |
| `kysely` | `^0.27` | Type-safe SQL query builder | MIT |
| `ioredis` | `^5.4` | Redis client | MIT |
| `@minio/minio-client` | `^1.0` | MinIO/S3 client | Apache-2.0 |
| `@qdrant/js-client-rest` | `^1.8` | Qdrant REST client | Apache-2.0 |
| `neo4j-driver` | `^5.23` | Neo4j Bolt driver | Apache-2.0 |
| `meilisearch` | `^0.38` | Meilisearch client | MIT |

### 4.3 AI/HTTP
| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `openai` | `^4.55` | OpenAI SDK | MIT |
| `@anthropic-ai/sdk` | `^0.24` | Anthropic SDK (optional) | MIT |
| `hono` | `^4.5` | Lightweight web framework (API gateway) | MIT |
| `zod-to-json-schema` | `^3.23` | Zod → JSON Schema for LLM function calling | MIT |

### 4.4 Processing & Utilities
| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `pdf-parse` | `^1.1` | PDF text extraction (Node) | MIT |
| `mammoth` | `^1.7` | DOCX → HTML/Markdown | BSD-3 |
| `xlsx` | `^0.18` | Spreadsheet parsing | Apache-2.0 |
| `sharp` | `^0.33` | Image processing (libvips) | Apache-2.0 |
| `ffmpeg-static` | `^5.2` | Bundled ffmpeg binary | GPL-3.0 |
| `fluent-ffmpeg` | `^2.1` | FFmpeg wrapper | MIT |
| `music-metadata` | `^10.6` | Audio metadata parsing | MIT |
| `csv-parse` | `^5.5` | CSV parsing | MIT |
| `fast-xml-parser` | `^4.4` | XML parsing | MIT |

### 4.5 CLI & Testing
| Package | Version | Purpose | License |
|---------|---------|---------|---------|
| `commander` | `^12.1` | CLI framework | MIT |
| `vitest` | `^2.0` | Test runner (Bun-native) | MIT |
| `@vitest/coverage-v8` | `^2.0` | Coverage | MIT |
| `eslint` | `^9.9` | Linting | MIT |
| `prettier` | `^3.3` | Formatting | MIT |

---

## 5. External APIs & Services

| Service | Authentication | Purpose | Rate Limits | Cost Model | Fallback |
|---------|---------------|---------|-------------|------------|----------|
| **OpenAI API** | Bearer token (`OPENAI_API_KEY`) | Embeddings (text-embedding-3-large), GPT-4o reasoning | 10k RPM / 4M TPM | Pay-per-token | NVIDIA NIM, Local |
| **NVIDIA NIM API** | Bearer token (`NIM_API_KEY`) | Nemotron-3-Ultra, Llama-3.1, embeddings | Varies by model | Pay-per-token / NVIDIA credits | OpenAI, Local |
| **Z.ai (GLM)** | Bearer token (`LLM7_API_KEY`) | GLM-4.5, search-augmented reasoning | Unknown | Unknown / Credits | OpenAI |
| **GitHub API** | PAT (`GITHUB_TOKEN`) | Repo metadata, commits, issues | 5k req/hr (authenticated) | Free | Git CLI local |
| **Google APIs** | OAuth 2.0 | Gmail, Drive, Photos, Calendar, YouTube | Varies per API | Free tier | Takeout exports |
| **Helius RPC** | API Key in URL (`SOLANA_RPC_URL`) | Solana blockchain data | 100 req/s | Pay-per-request | Public RPC |
| **Jito Block Engine** | API Key | MEV-protected tx submission | — | Pay-per-bundle | — |
| **OpenCode API** | Bearer token (`OPENCODE_API_KEY`) | Coding agent integration | Unknown | Unknown | — |
| **MinIO (Local)** | Access/Secret Key | Object storage | Unlimited | Free (self-hosted) | S3, Azure, GCS |
| **Ollama (Local)** | None (local) | Local LLM inference | Hardware-bound | Free (electricity) | — |

---

## 6. System Dependencies (OS-Level)

| Dependency | Windows Install | Purpose | Version |
|------------|-----------------|---------|---------|
| **FFmpeg** | `winget install Gyan.FFmpeg` | Audio/video processing, transcription | 7.x |
| **Tesseract OCR** | `winget install UB-Mannheim.TesseractOCR` | OCR engine | 5.3+ |
| **Poppler** | `winget install oschwartz10692.poppler` | PDF rendering (pdfplumber, pdf2image) | 24.x |
| **Ghostscript** | `winget install Artifex.Ghostscript` | PDF processing (pymupdf) | 10.x |
| **GraphViz** | `winget install Graphviz.Graphviz` | Graph visualization (optional) | 10.x |
| **Git LFS** | `winget install GitHub.GitLFS` | Large file support in Git | 3.5+ |

---

## 7. License Risk Assessment

| Risk Level | Packages | Mitigation |
|------------|----------|------------|
| **Critical (AGPL/GPL)** | `pymupdf` (AGPL-3.0), `neo4j-driver` (GPL-3.0), `minio` (AGPL-3.0), `ffmpeg-static` (GPL-3.0), `igraph` (GPL-3.0) | **Isolate in separate processes/containers**; do not link into main application binary. Use CLI/subprocess boundary. |
| **High (Copyleft)** | `minio` server (AGPL-3.0) | Run as separate service; only communicate via S3 API. |
| **Medium (MPL/EPL)** | None identified | — |
| **Low (MIT/BSD/Apache)** | All others | Standard compliance: retain notices. |

**Strategy:** All AGPL/GPL components run as **independent services** (Docker containers or CLI subprocesses). The Life Archive core codebase (Python + TypeScript) uses only permissive licenses (MIT, Apache-2.0, BSD).

---

## 8. Version Pinning Strategy

- **Infrastructure:** Pin to specific digest (e.g., `postgres@sha256:...`) in `docker-compose.yml`
- **Python:** `requirements-lock.txt` via `pip-tools compile` — commit lockfile
- **TypeScript:** `bun.lock` committed; `package.json` with exact versions (`^` only for patch)
- **System tools:** Document minimum versions; accept any newer compatible

---

## 9. Supply Chain Security

| Control | Implementation |
|---------|----------------|
| Dependency scanning | `pip-audit` (Python), `bun audit` (JS), `trivy` (Docker images) |
| Provenance verification | `sigstore`/`cosign` for container images; `pip install --require-hashes` |
| Private registry | Consider GitHub Packages or self-hosted for internal packages |
| SBOM generation | `syft` for containers, `cyclonedx-bom` for Python/JS |

---

## 10. Verdict

**ALL DEPENDENCIES IDENTIFIED AND AVAILABLE.**

No fundamental blockers. Primary concerns:
1. **AGPL/GPL isolation** — architectural decision to run as separate services
2. **OAuth credentials** — must be obtained before connector implementation (see `04_CREDENTIAL_REQUIREMENTS.md`)
3. **Docker daemon** — must be started before infrastructure deployment

**Next Action:** Create `03_CONNECTOR_INVENTORY.md` and `04_CREDENTIAL_REQUIREMENTS.md`.