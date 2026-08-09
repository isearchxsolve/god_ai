# Connector Inventory

**Date:** 2026-08-08
**Project:** Life Archive — Complete Digital Life Research & Publishing Platform
**Specification Reference:** Sections 5, 6, 7, 27, 28 (Ingestion Framework, Manifest, Deduplication, Incremental Ingestion, Resumability)

---

## Executive Summary

This document catalogs all source system connectors required for the Life Archive ingestion pipeline. Each connector implements the 8-stage interface: **DISCOVER → ACQUIRE → VERIFY → HASH → STORE → INDEX → NORMALIZE → LOG** with **RESUME** capability.

**Total Connectors Specified:** 18
- **Phase 1 (Pilot):** 6 connectors (Local files, Google Takeout, WhatsApp, LinkedIn, Git, GitHub)
- **Phase 2 (Core Google):** 6 connectors (Gmail, Drive, Photos, YouTube, Calendar, Contacts)
- **Phase 3 (Extended):** 6 connectors (LMS, Social exports, Documents, Spreadsheets, Images, Audio/Video)

---

## Connector Architecture

### Base Interface (TypeScript/Python)

```typescript
// Shared contract — implemented in both languages
interface Connector {
  readonly id: string;                    // e.g., "gmail", "google-drive", "local-files"
  readonly name: string;                  // Human-readable
  readonly sourceType: SourceType;        // Enum: GOOGLE, GITHUB, LOCAL, WHATSAPP, LINKEDIN, etc.
  readonly capabilities: ConnectorCapabilities;
  
  // 8-stage pipeline
  discover(ctx: RunContext): Promise<DiscoverResult>;
  acquire(ctx: RunContext, items: DiscoveredItem[]): Promise<AcquireResult>;
  verify(ctx: RunContext, items: AcquiredItem[]): Promise<VerifyResult>;
  hash(items: VerifiedItem[]): HashedItem[];           // Sync, pure
  store(ctx: RunContext, items: HashedItem[]): Promise<StoreResult>;
  index(ctx: RunContext, items: StoredItem[]): Promise<IndexResult>;
  normalize(ctx: RunContext, items: IndexedItem[]): Promise<NormalizeResult>;
  log(ctx: RunContext, result: ConnectorResult): Promise<void>;
  
  // Resumability
  getCheckpoint(runId: string): Promise<ConnectorCheckpoint | null>;
  saveCheckpoint(runId: string, checkpoint: ConnectorCheckpoint): Promise<void>;
}
```

### Connector Capabilities

```typescript
interface ConnectorCapabilities {
  incremental: boolean;        // Supports cursor-based incremental sync
  batchSize: number;           // Max items per batch
  rateLimit: RateLimit;        // Requests per window
  authType: AuthType;          // OAUTH, API_KEY, BEARER, NONE, EXPORT_FILE
  supportsResume: boolean;     // Can resume from checkpoint
  supportsDedupe: boolean;     // Can detect duplicates during discover
  exportFormats: string[];     // For manual exports: ["zip", "json", "mbox", "csv"]
}
```

---

## 1. Phase 1 Connectors (Pilot — Implement First)

### 1.1 Local Files Connector (`local-files`)
**Priority:** CRITICAL — Foundation for all other connectors
**Source:** `LIFE_ARCHIVE/00_RAW/documents/`, `images/`, `audio/`, `video/`, `other/`
**Auth:** NONE (filesystem)

| Stage | Implementation |
|-------|----------------|
| **DISCOVER** | Recursive walk of `00_RAW/`; emit `DiscoveredItem` with relative path, size, mtime, MIME type (via `file-type`/`python-magic`) |
| **ACQUIRE** | No-op (already local); copy to staging with original preserved |
| **VERIFY** | Read file, verify readable, extract basic metadata (EXIF for images, ID3 for audio, PDF info) |
| **HASH** | SHA-256 stream (chunked for large files); also compute xxHash for fast dedupe hint |
| **STORE** | Write to `00_RAW/{source}/{date}/{hash[:2]}/{hash}`; create manifest entry |
| **INDEX** | Extract text content → Meilisearch; compute embeddings → Qdrant; extract entities → Neo4j staging |
| **NORMALIZE** | Map to canonical schemas (Document, Image, Audio, Video) with `source_archive_id` |
| **LOG** | Write to `01_MANIFEST/ingestion_runs.jsonl`, `source_manifest.jsonl`, `hashes.jsonl` |
| **RESUME** | Checkpoint: last processed file path + hash; skip already-hashed files |

**Supported MIME Types:** `application/pdf`, `application/vnd.openxmlformats-*`, `text/*`, `image/*`, `audio/*`, `video/*`, `application/zip`, `application/x-tar`

**Incremental:** File mtime + size + hash comparison

---

### 1.2 Google Takeout Connector (`google-takeout`)
**Priority:** CRITICAL — Single export contains multiple Google services
**Source:** Manual download of `takeout-*.zip` from takeout.google.com
**Auth:** NONE (user-provided export file)

| Stage | Implementation |
|-------|----------------|
| **DISCOVER** | Unzip Takeout archive; parse directory structure; identify service sub-archives (Mail, Drive, Photos, Calendar, YouTube, Contacts, etc.) |
| **ACQUIRE** | Extract each service archive to `00_RAW/google/{service}/` preserving structure |
| **VERIFY** | Validate Takeout manifest (`archive_browser.html` or JSON); check for incomplete exports |
| **HASH** | SHA-256 per extracted file; also hash original `.zip` for provenance |
| **STORE** | Organize by service: `00_RAW/google/gmail/`, `00_RAW/google/drive/`, etc. |
| **INDEX** | Delegate to service-specific sub-connectors (see below) |
| **NORMALIZE** | Produce unified `GoogleTakeoutExport` manifest linking all services |
| **LOG** | Record Takeout export date, Google account, services included |
| **RESUME** | Checkpoint: Takeout zip hash + last extracted service |

**Note:** This is a **meta-connector** that produces raw input for Gmail, Drive, Photos, Calendar, YouTube, Contacts connectors.

---

### 1.3 WhatsApp Export Connector (`whatsapp`)
**Priority:** HIGH — Rich personal communication data
**Source:** WhatsApp "Export Chat" → ZIP (with/without media)
**Auth:** NONE (user-provided export file)

| Stage | Implementation |
|-------|----------------|
| **DISCOVER** | Parse `_chat.txt` or `.zip`; detect format (iOS vs Android), media presence |
| **ACQUIRE** | Extract to `00_RAW/whatsapp/{chat_name}/` |
| **VERIFY** | Validate message count, date range, participant list; detect truncation |
| **HASH** | SHA-256 per message (content + timestamp + sender) + per media file |
| **STORE** | Messages → JSONL; media → `00_RAW/whatsapp/{chat_name}/media/{hash}` |
| **INDEX** | Full-text search on messages; embeddings per conversation chunk; entity extraction (people, places, dates) |
| **NORMALIZE** | `Conversation`, `Message`, `Person` (participants), `MediaAttachment` schemas |
| **LOG** | Chat metadata: participants, date range, message count, export date |
| **RESUME** | Checkpoint: last message index processed |

**Special Handling:** Group chats → multiple `Person` nodes; media deduplication across chats.

---

### 1.4 LinkedIn Export Connector (`linkedin`)
**Priority:** MEDIUM — Professional graph data
**Source:** LinkedIn "Download your data" → ZIP (JSON/CSV)
**Auth:** NONE (user-provided export file)

| Stage | Implementation |
|-------|----------------|
| **DISCOVER** | Extract ZIP; identify files: `Connections.csv`, `Profile.json`, `Messages.json`, `Jobs.json`, `Education.json`, `Skills.json`, `Posts.json` |
| **ACQUIRE** | Copy to `00_RAW/linkedin/` |
| **VERIFY** | Cross-reference record counts; validate date formats |
| **HASH** | Per-record SHA-256 (stable field subset) |
| **STORE** | Organized by data type |
| **INDEX** | Connections → graph edges; Posts → full-text + embeddings; Profile → entity |
| **NORMALIZE** | `Person` (connections), `Organization` (companies), `Job`, `Education`, `Post`, `Skill` |
| **LOG** | Export date, profile URN, connection count |
| **RESUME** | Per-file checkpoint |

**Privacy:** Connections' email addresses → `THIRD_PARTY_PRIVATE` classification.

---

### 1.5 Git Connector (`git`)
**Priority:** HIGH — Complete code history
**Source:** Local `.git` directories (recursive discovery)
**Auth:** NONE (local filesystem)

| Stage | Implementation |
|-------|----------------|
| **DISCOVER** | Find all `.git` dirs under configured roots; `git log --all --format=...` for commits |
| **ACQUIRE** | `git bundle create` for each repo → `00_RAW/git/{repo_name}.bundle`; also export commit metadata JSONL |
| **VERIFY** | `git bundle verify`; commit count match |
| **HASH** | Commit SHA (Git's own) + bundle SHA-256 |
| **STORE** | Bundles in `00_RAW/git/`; commit metadata in `03_NORMALIZED/git_commits/` |
| **INDEX** | Commit messages → full-text; code embeddings (optional); file paths → entities |
| **NORMALIZE** | `GitCommit`, `GitRepository`, `GitBranch`, `GitTag`, `Person` (author/committer) |
| **LOG** | Repo root, remote URLs, branch list, commit count, date range |
| **RESUME** | Checkpoint: last commit SHA processed per repo |

**Incremental:** `git log --since=<last_sync>`

---

### 1.6 GitHub Connector (`github`)
**Priority:** HIGH — Issues, PRs, stars, repos beyond local clones
**Source:** GitHub REST/GraphQL API
**Auth:** OAuth 2.0 (GitHub App) or Personal Access Token (PAT)
**Scopes:** `repo`, `read:user`, `read:org`, `user:email`, `read:project`, `read:packages`

| Stage | Implementation |
|-------|----------------|
| **DISCOVER** | List repos (owned + contributed); for each: issues, PRs, comments, releases, workflows, stars |
| **ACQUIRE** | Paginated API calls; store raw JSON in `00_RAW/github/{owner}/{repo}/` |
| **VERIFY** | ETag/Last-Modified headers; webhook delivery for real-time (future) |
| **HASH** | Per-object (issue, PR, comment) SHA-256 of canonical JSON |
| **STORE** | Organized by repo + object type |
| **INDEX** | Issue/PR bodies → full-text + embeddings; code references → entities |
| **NORMALIZE** | `GitHubRepository`, `GitHubIssue`, `GitHubPullRequest`, `GitHubComment`, `GitHubRelease`, `GitHubWorkflowRun` |
| **LOG** | API rate limit usage, last sync cursor (updated_at) |
| **RESUME** | Cursor: `updated_at` timestamp per object type per repo |

**Rate Limit:** 5,000 req/hr (authenticated) — implement exponential backoff.

---

## 2. Phase 2 Connectors (Core Google Services — OAuth Required)

### 2.1 Gmail Connector (`gmail`)
**Source:** Gmail API
**Auth:** OAuth 2.0 — Scopes: `https://www.googleapis.com/auth/gmail.readonly`, `https://www.googleapis.com/auth/gmail.metadata`
**Incremental:** `historyId` / `internalDate` cursor

| Data Types | Normalized Schema |
|------------|-------------------|
| Messages (sent/received) | `Email`, `Person` (sender/recipients), `Conversation` (thread) |
| Attachments | `Document`, `Image`, `Audio`, `Video` (by MIME) |
| Labels | `EmailLabel` (custom taxonomy) |

**Special:** Handle MIME multipart; decode base64url; extract inline images; thread reconstruction.

---

### 2.2 Google Drive Connector (`google-drive`)
**Source:** Drive API v3
**Auth:** OAuth 2.0 — Scopes: `https://www.googleapis.com/auth/drive.readonly`, `https://www.googleapis.com/auth/drive.metadata.readonly`
**Incremental:** `changes` API with `pageToken` / `startChangeId`

| Data Types | Normalized Schema |
|------------|-------------------|
| Files (docs, sheets, slides, PDFs, images, etc.) | `Document`, `Spreadsheet`, `Presentation`, `Image`, `File` |
| Folders | `DriveFolder` (hierarchy) |
| Permissions | `DrivePermission` (shared-with) |
| Revisions | `DriveRevision` (version history) |

**Special:** Export Google Workspace formats (Doc→PDF/MD, Sheet→CSV, Slides→PDF); handle shortcuts; large file download with resumable media.

---

### 2.3 Google Photos Connector (`google-photos`)
**Source:** Photos Library API
**Auth:** OAuth 2.0 — Scopes: `https://www.googleapis.com/auth/photoslibrary.readonly`, `https://www.googleapis.com/auth/photoslibrary.readonly.appcreateddata`
**Incremental:** `mediaItems:search` with date filters; `albums` listing

| Data Types | Normalized Schema |
|------------|-------------------|
| Media items (photos, videos) | `Photograph`, `Video` |
| Albums | `PhotoAlbum` |
| Metadata (EXIF, location, camera) | Embedded in `Photograph`/`Video` |

**Special:** Base64 download URLs expire; use resumable downloads; handle "archived" items.

---

### 2.4 YouTube Connector (`youtube`)
**Source:** YouTube Data API v3 + YouTube Analytics API
**Auth:** OAuth 2.0 — Scopes: `https://www.googleapis.com/auth/youtube.readonly`, `https://www.googleapis.com/auth/yt-analytics.readonly`
**Incremental:** `publishedAfter` cursor; channel `uploads` playlist

| Data Types | Normalized Schema |
|------------|-------------------|
| Videos (owned) | `Video` + `YouTubeVideo` (analytics) |
| Playlists | `YouTubePlaylist` |
| Comments (on own videos) | `YouTubeComment` |
| Subscriptions | `YouTubeSubscription` |
| Watch history (if enabled) | `YouTubeWatchEvent` |

**Special:** Video files not downloaded by default (size); store metadata + thumbnails. Optional: `youtube-dl` for archive.

---

### 2.5 Google Calendar Connector (`google-calendar`)
**Source:** Calendar API v3
**Auth:** OAuth 2.0 — Scopes: `https://www.googleapis.com/auth/calendar.readonly`, `https://www.googleapis.com/auth/calendar.events.readonly`
**Incremental:** `syncToken` from `events.list`

| Data Types | Normalized Schema |
|------------|-------------------|
| Calendars | `Calendar` |
| Events | `Event` (with attendees → `Person`) |
| Reminders | `CalendarReminder` |

**Special:** Recurring events → expand instances; handle timezone; private events → `PRIVATE` classification.

---

### 2.6 Google Contacts Connector (`google-contacts`)
**Source:** People API
**Auth:** OAuth 2.0 — Scopes: `https://www.googleapis.com/auth/contacts.readonly`
**Incremental:** `syncToken` from `people.connections.list`

| Data Types | Normalized Schema |
|------------|-------------------|
| Contacts | `Person` (with `source: google-contacts`) |
| Contact groups | `ContactGroup` |

**Special:** Merge with other `Person` sources (WhatsApp, LinkedIn, Git) via deduplication.

---

## 3. Phase 3 Connectors (Extended)

### 3.1 LMS Connector (`lms`)
**Sources:** Canvas, Moodle, Coursera, edX, Udemy exports/APIs
**Auth:** Varies — API token, OAuth, or manual export
**Status:** Low priority; implement per-platform as needed

---

### 3.2 Social Exports Connector (`social`)
**Sources:** Twitter/X (archive), Facebook (archive), Instagram (archive), Reddit (export)
**Auth:** Manual export (ZIP/JSON)
**Status:** Medium priority; Twitter/X archive high value

---

### 3.3 Documents Connector (`documents`)
**Source:** Local files (already covered by `local-files`); specialized parsers for:
- PDF (pymupdf, pdfplumber)
- DOCX (python-docx, mammoth)
- ODT, RTF, EPUB
- LaTeX (.tex)
- Markdown (.md, .mdx)
**Status:** Part of `local-files` processing pipeline

---

### 3.4 Spreadsheets Connector (`spreadsheets`)
**Source:** Local files (XLSX, CSV, ODS, Google Sheets export)
**Parsers:** openpyxl, pandas, csv-parse
**Normalized:** `Spreadsheet`, `Sheet`, `Cell`, `Table`
**Status:** Part of `local-files`

---

### 3.5 Images Connector (`images`)
**Source:** Local files (JPEG, PNG, HEIC, WEBP, TIFF, RAW)
**Processing:** EXIF (piexif, pillow), OCR (tesseract), visual description (LLM), location reverse-geocode
**Normalized:** `Photograph`, `Image`, `VisualEntity`
**Status:** Part of `local-files`

---

### 3.6 Audio Connector (`audio`)
**Source:** Local files (MP3, WAV, M4A, FLAC, OGG, OPUS)
**Processing:** Metadata (mutagen), transcription (whisper.cpp), speaker diarization (pyannote - optional), chapter detection
**Normalized:** `Audio`, `Transcript`, `SpeakerSegment`
**Status:** Part of `local-files`

---

### 3.7 Video Connector (`video`)
**Source:** Local files (MP4, MOV, MKV, WEBM, AVI)
**Processing:** Metadata (ffprobe), keyframe extraction, audio extraction → audio connector, scene detection (scenedetect), transcription
**Normalized:** `Video`, `VideoScene`, `VideoKeyframe`
**Status:** Part of `local-files`

---

## 4. Connector Implementation Priority Matrix

| Connector | Phase | Effort | Dependencies | Blockers | Pilot Candidate |
|-----------|-------|--------|--------------|----------|-----------------|
| `local-files` | 1 | Low | None | None | ✅ YES |
| `google-takeout` | 1 | Medium | None (manual export) | User must provide export | ✅ YES |
| `whatsapp` | 1 | Medium | None (manual export) | User must provide export | ✅ YES |
| `linkedin` | 1 | Low | None (manual export) | User must provide export | ✅ YES |
| `git` | 1 | Low | git CLI | None | ✅ YES |
| `github` | 1 | Medium | PAT/OAuth | Credentials needed | ⚠️ Needs creds |
| `gmail` | 2 | High | OAuth credentials | **Credentials required** | ❌ Phase 2 |
| `google-drive` | 2 | High | OAuth credentials | **Credentials required** | ❌ Phase 2 |
| `google-photos` | 2 | High | OAuth credentials | **Credentials required** | ❌ Phase 2 |
| `youtube` | 2 | Medium | OAuth credentials | **Credentials required** | ❌ Phase 2 |
| `google-calendar` | 2 | Medium | OAuth credentials | **Credentials required** | ❌ Phase 2 |
| `google-contacts` | 2 | Low | OAuth credentials | **Credentials required** | ❌ Phase 2 |
| `lms` | 3 | Variable | Platform-specific | Low priority | ❌ Phase 3 |
| `social` | 3 | Medium | Manual exports | User must provide | ❌ Phase 3 |
| `documents` | 1/3 | Low | Part of local-files | None | ✅ In local-files |
| `spreadsheets` | 1/3 | Low | Part of local-files | None | ✅ In local-files |
| `images` | 1/3 | Medium | Part of local-files | OCR deps | ✅ In local-files |
| `audio` | 1/3 | High | Part of local-files | Whisper/ffmpeg | ✅ In local-files |
| `video` | 1/3 | High | Part of local-files | FFmpeg/scenedetect | ✅ In local-files |

---

## 5. Connector Configuration Schema

Each connector configured via `config/connectors/{connector_id}.yaml`:

```yaml
id: gmail
name: "Gmail"
sourceType: GOOGLE
enabled: true
schedule: "0 3 * * *"          # Daily at 3 AM (cron)
incremental: true
batchSize: 500
rateLimit:
  requests: 250
  window: "1m"
auth:
  type: OAUTH2
  configRef: "gmail_oauth"     # References secret store
storage:
  rawRoot: "00_RAW/gmail"
  manifestPath: "01_MANIFEST/source_manifest.jsonl"
processing:
  extractAttachments: true
  maxAttachmentSize: 52428800  # 50 MB
  ocrAttachments: true
  transcribeAudio: true
privacy:
  defaultClassification: "PRIVATE"
  piiDetection: true
resume:
  checkpointInterval: 100      # Save checkpoint every N items
```

---

## 6. Deduplication Strategy (Cross-Connector)

| Level | Method | Action |
|-------|--------|--------|
| **Exact** | SHA-256 match | Mark as `DUPLICATE_OF` in manifest; do not re-store in RAW |
| **Near-duplicate** | Perceptual hash (images), MinHash (text), Chromaprint (audio) | Mark as `NEAR_DUPLICATE_OF`; cluster |
| **Version** | Filename + size + mtime + content similarity | Mark as `VERSION_OF`; preserve all in RAW |
| **Cross-source** | Entity resolution (Person, Organization) | Merge in `05_ENTITIES/`; link in Knowledge Graph |

**Rule:** NEVER delete from `00_RAW/`. Only mark relationships.

---

## 7. Manifest Schema (Section 6 Compliance)

Every source object → one line in `01_MANIFEST/source_manifest.jsonl`:

```json
{
  "archive_id": "sha256:abc123...",
  "source": "gmail",
  "source_identifier": "msg-f:12345",
  "original_filename": "Re: Project Update.eml",
  "mime_type": "message/rfc822",
  "size_bytes": 45231,
  "original_timestamp": "2024-01-15T14:30:00Z",
  "acquisition_timestamp": "2026-08-08T10:00:00Z",
  "sha256": "abc123...",
  "connector": "gmail",
  "ingestion_run_id": "run-20260808-001",
  "privacy_classification": "PRIVATE",
  "processing_status": "INGESTED",
  "dedupe_status": "UNIQUE",
  "dedupe_of": null
}
```

---

## 8. Next Actions

1. **Implement `local-files` connector first** — validates pipeline end-to-end
2. **Request Google Takeout export** from user — enables `google-takeout` + sub-connectors
3. **Request WhatsApp + LinkedIn exports** from user — enables pilot connectors
4. **Create GitHub PAT** for `github` connector
5. **Defer OAuth connectors** (Gmail, Drive, Photos, etc.) until credentials obtained

**See `04_CREDENTIAL_REQUIREMENTS.md` for exact credential specifications.**