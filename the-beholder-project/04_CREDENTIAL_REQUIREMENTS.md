# Credential Requirements

**Date:** 2026-08-08
**Project:** Life Archive — Complete Digital Life Research & Publishing Platform
**Specification Reference:** Sections 5, 25, 26, 40 (Ingestion, Privacy, Security, Credential Discovery)
**Principle:** Never ask for a password if OAuth/export exists. Never ask for credentials not currently required. Request progressively.

---

## Executive Summary

This document specifies every credential required by each connector, the minimum necessary scope, where it will be stored, and the security risk. Credentials are requested **progressively by phase** — only Phase 1 credentials are requested now.

**Total Credential Sets Required:** 14
- **Phase 1 (Immediate):** 2 (GitHub PAT, MinIO keys) — *OAuth not required for pilot connectors*
- **Phase 2 (Core Google):** 6 OAuth 2.0 clients (Gmail, Drive, Photos, YouTube, Calendar, Contacts)
- **Phase 3 (Extended):** 0 new (uses manual exports)
- **AI Providers (Already Configured):** 4 (OpenAI, NVIDIA NIM, Z.ai, OpenCode)
- **Infrastructure (Auto-generated):** 2 (PostgreSQL, Neo4j, Redis, Qdrant, Meilisearch passwords)

---

## Credential Storage Strategy

| Credential Type | Storage Location | Encryption | Access Control |
|-----------------|------------------|------------|----------------|
| **OAuth 2.0 Client Secrets** | n8n credential store (encrypted at rest) | AES-256-GCM | n8n RBAC |
| **OAuth 2.0 Refresh Tokens** | n8n credential store | AES-256-GCM | n8n RBAC |
| **API Keys (AI providers)** | Environment variables (`.env`) → injected at runtime | OS keyring (Windows Credential Manager) | Process-only |
| **Database Passwords** | Docker secrets / `.env` (dev) | At-rest via Docker secrets | Service-only |
| **MinIO Access/Secret Keys** | `.env` → Docker secrets | At-rest via Docker secrets | Service-only |
| **GitHub PAT** | `.env` → n8n credential store | AES-256-GCM | n8n RBAC |
| **User-provided exports** | `00_RAW/` (filesystem) | Disk encryption (BitLocker) | File ACLs |

**No credentials in Git.** No credentials in LLM prompts. No credentials in logs.

---

## Phase 1 Credentials (Required Now)

### 1. GitHub Personal Access Token (PAT)

| Field | Value |
|-------|-------|
| **Service** | GitHub |
| **Credential Type** | Personal Access Token (Classic) or Fine-grained PAT |
| **Why Required** | Access to repos, issues, PRs, commits, stars beyond local clones |
| **Scope Required** | `repo` (full), `read:user`, `read:org`, `user:email`, `read:project`, `read:packages` |
| **Read/Write** | READ ONLY |
| **Where Stored** | n8n credential store (type: "GitHub Personal Access Token") |
| **OAuth Possible?** | Yes (GitHub App) — but PAT simpler for pilot |
| **Export Alternative?** | `git` connector covers local clones; PAT needed for GitHub-only data |
| **Security Risk** | **MEDIUM** — Token grants read access to all repos user can access. Rotate every 90 days. Use fine-grained PAT targeting specific repos if possible. |
| **Rotation** | Manual via GitHub Settings → Developer settings |
| **Status** | ❌ **NOT CONFIGURED — USER ACTION REQUIRED** |

**Action:** User creates PAT at https://github.com/settings/tokens with scopes above. Provides via secure channel (not chat).

---

### 2. MinIO Access Key / Secret Key

| Field | Value |
|-------|-------|
| **Service** | MinIO (self-hosted S3-compatible storage) |
| **Credential Type** | Access Key + Secret Key |
| **Why Required** | Object storage for `00_RAW/` archive, processed artifacts, backups |
| **Scope Required** | Full bucket access (read/write/list/delete) |
| **Read/Write** | READ + WRITE |
| **Where Stored** | Docker secrets (`minio_access_key`, `minio_secret_key`) + `.env` for dev |
| **OAuth Possible?** | N/A (self-hosted) |
| **Export Alternative?** | N/A |
| **Security Risk** | **LOW** — Local network only (Docker internal). Not exposed externally. |
| **Rotation** | Recreate via MinIO console; update Docker secrets |
| **Status** | ⚠️ **AUTO-GENERATED on first deploy** — User can override via `.env` |

**Note:** Generated automatically by Docker Compose on first run. No user action needed unless specific keys required.

---

## Phase 2 Credentials (Google OAuth 2.0 — Required After Pilot)

> **All Google connectors use the SAME OAuth 2.0 Client** (one per Google Cloud Project) with different scopes. User creates **one** OAuth client, grants all scopes.

### 3. Google Cloud OAuth 2.0 Client (Unified)

| Field | Value |
|-------|-------|
| **Service** | Google Cloud Platform (all Google APIs) |
| **Credential Type** | OAuth 2.0 Client ID + Client Secret |
| **Why Required** | Gmail, Drive, Photos, YouTube, Calendar, Contacts APIs |
| **Scopes Required** | See per-connector below |
| **Read/Write** | READ ONLY (all scopes) |
| **Where Stored** | n8n credential store (type: "Google OAuth2 API") |
| **OAuth Possible?** | **YES — THIS IS OAUTH** |
| **Export Alternative?** | **YES — Google Takeout** (manual, one-time). Use Takeout for pilot; OAuth for incremental. |
| **Security Risk** | **MEDIUM-HIGH** — Grants read access to user's entire Google account. Mitigations: <br>• Use dedicated Google Cloud Project (not personal)<br>• Restrict OAuth consent screen to "Internal" or single user<br>• Enable "Force re-authentication" for sensitive scopes<br>• Monitor OAuth token usage via GCP audit logs |
| **Rotation** | Rotate client secret in GCP Console; re-authorize in n8n |
| **Status** | ❌ **NOT CONFIGURED — USER ACTION REQUIRED (Phase 2)** |

---

### 3.1 Gmail Scopes (Subset of Unified Client)

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `https://www.googleapis.com/auth/gmail.readonly` | Read messages, threads, labels, attachments | **HIGH** — Full email content |
| `https://www.googleapis.com/auth/gmail.metadata` | Read headers only (faster, less sensitive) | MEDIUM |

**Recommendation:** Start with `gmail.metadata` for discovery; add `gmail.readonly` for full ingestion.

---

### 3.2 Google Drive Scopes

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `https://www.googleapis.com/auth/drive.readonly` | Read all files, metadata, revisions | **HIGH** — All Drive content |
| `https://www.googleapis.com/auth/drive.metadata.readonly` | Read metadata only (no content) | MEDIUM |

**Recommendation:** `drive.readonly` required for content extraction.

---

### 3.3 Google Photos Scopes

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `https://www.googleapis.com/auth/photoslibrary.readonly` | Read photos, videos, albums | **HIGH** — All media |
| `https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata` | Read only app-created items | LOW |

**Recommendation:** Full `photoslibrary.readonly` needed.

---

### 3.4 YouTube Scopes

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `https://www.googleapis.com/auth/youtube.readonly` | Read channel, videos, playlists, subscriptions | MEDIUM — Public + private videos |
| `https://www.googleapis.com/auth/yt-analytics.readonly` | Read analytics (views, revenue) | MEDIUM — Business data |

---

### 3.5 Google Calendar Scopes

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `https://www.googleapis.com/auth/calendar.readonly` | Read all calendars, events | **HIGH** — Schedule, attendees, locations |
| `https://www.googleapis.com/auth/calendar.events.readonly` | Read events only (no calendar list) | MEDIUM |

---

### 3.6 Google Contacts Scopes

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `https://www.googleapis.com/auth/contacts.readonly` | Read all contacts | **HIGH** — PII: names, emails, phones, addresses |

**Privacy Note:** Contacts are **THIRD_PARTY_PRIVATE** — never publish without consent.

---

## Phase 3 Credentials (Manual Exports — No OAuth)

| Connector | Credential | How Obtained |
|-----------|------------|--------------|
| `whatsapp` | Export ZIP file | User: WhatsApp → Settings → Chats → Export Chat |
| `linkedin` | Export ZIP file | User: LinkedIn → Settings → Data Privacy → Get copy |
| `social` (Twitter/X) | Export ZIP | User: Twitter → Settings → Your Account → Download archive |
| `social` (Facebook) | Export ZIP | User: Facebook → Settings → Your Information → Download |
| `lms` | Varies | Platform-specific export/API token |

**No credentials needed from user for Phase 3** — only file transfers.

---

## AI Provider Credentials (Already Configured in Environment)

| Provider | Env Var | Status | Used By |
|----------|---------|--------|---------|
| OpenAI | `OPENAI_API_KEY` | ✅ Set | Embeddings, GPT-4o reasoning |
| NVIDIA NIM | `NVIDIA_API_KEY` / `NIM_API_KEY` | ✅ Set | Nemotron, Llama, embeddings |
| Z.ai (GLM) | `ZAI_BUSINESS_BASE_URL` + `LLM7_API_KEY` | ✅ Set | GLM-4.5, search-augmented |
| OpenCode | `OPENCODE_API_KEY` | ✅ Set | Coding agent integration |

**Security Note:** These are in shell environment. For production, move to secret manager (Doppler, Vault, AWS Secrets Manager) and inject at runtime.

---

## Infrastructure Credentials (Auto-Generated)

| Service | Credentials | Generated By | User Override |
|---------|-------------|--------------|---------------|
| PostgreSQL | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Docker Compose (random) | Via `.env` |
| Neo4j | `NEO4J_AUTH` (neo4j/password) | Docker Compose (random) | Via `.env` |
| Redis | `REDIS_PASSWORD` | Docker Compose (random) | Via `.env` |
| Qdrant | API Key (optional) | Docker Compose (disabled by default) | Via `.env` |
| Meilisearch | `MEILI_MASTER_KEY` | Docker Compose (random) | Via `.env` |
| n8n | `N8N_ENCRYPTION_KEY` | Docker Compose (random) | **Must persist!** Via `.env` |
| Traefik | Let's Encrypt account email | User input | Via `.env` |

**Critical:** `N8N_ENCRYPTION_KEY` **must persist across restarts** or all stored credentials become undecryptable. Store in `.env` and back up.

---

## Credential Request Sequence (Progressive)

### ✅ NOW (Phase 1 Start)
1. **GitHub PAT** — User creates and provides securely
2. **MinIO keys** — Auto-generated (user can override)

### 🔄 AFTER PILOT SUCCESS (Phase 2 Start)
3. **Google OAuth Client** — User creates in GCP, provides Client ID + Secret
4. **User authorizes** via n8n OAuth flow (one-time per connector)

### 📦 AS NEEDED (Phase 3)
5. **Export files** — User provides WhatsApp, LinkedIn, Twitter, Facebook exports via secure transfer

---

## Security Checklist for Credential Handling

- [ ] No credentials in Git history (verify with `git log --all --full-history -- "**/*secret*" "**/*token*" "**/*key*"`)
- [ ] No credentials in Docker images (use build args / runtime injection)
- [ ] No credentials in LLM prompts (privacy engine strips before sending)
- [ ] No credentials in logs (structured logging excludes sensitive fields)
- [ ] OAuth refresh tokens encrypted at rest (n8n handles)
- [ ] `N8N_ENCRYPTION_KEY` backed up securely
- [ ] Rotation schedule documented for each credential
- [ ] Incident response: credential compromise → immediate revocation + rotation

---

## User Action Required (Summary)

| Priority | Credential | Action | Deadline |
|----------|------------|--------|----------|
| **P0** | GitHub PAT | Create at github.com/settings/tokens → Provide securely | Before Phase 1 implementation |
| **P0** | (Optional) MinIO keys | Override in `.env` if desired | Before Docker deploy |
| **P1** | Google OAuth Client | Create in Google Cloud Console → Provide Client ID + Secret | After pilot approval |
| **P2** | WhatsApp Export | Generate in WhatsApp → Transfer securely | Phase 1 pilot |
| **P2** | LinkedIn Export | Generate in LinkedIn → Transfer securely | Phase 1 pilot |

---

## Next Steps

1. **User provides GitHub PAT** → Configure in n8n / `.env`
2. **Deploy Docker Compose stack** (generates infrastructure credentials)
3. **Implement `local-files` + `git` connectors** (no external creds)
4. **Request Google Takeout export** from user (enables `google-takeout` pilot)
5. **Request WhatsApp + LinkedIn exports** from user
6. **After pilot:** Request Google OAuth setup

**See `06_IMPLEMENTATION_PLAN.md` for detailed Phase 1 tasks.**