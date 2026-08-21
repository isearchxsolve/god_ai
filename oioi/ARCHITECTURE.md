## Components

### Expo Frontend Application

**`src/navigation/`**
- `RootNavigator.tsx` — Conditional rendering between landing → dashboard → canvas
- `TabNavigator.tsx` — 5-tab bottom navigator for Home, Canvas, Storyboard, MyAssets, Settings
- `AuthNavigator.tsx` — Mock JWT local only, persists token to `expo-secure-store`

**`src/screens/`**
- `LandingScreen.tsx` — Marketing page with feature highlights, matching oiioii.ai scroll patterns
- `HomeScreen.tsx` — "Good morning, director!" greeting, project grid, quick-create cards (Story Anime, Music Video, 15s Creative Clip, Character Design, Scene Design, IP Creation, Viral Remake, Smart Script Breakdown), recently opened projects carousel
- `CanvasScreen.tsx` — Host for `<InfiniteCanvas />` + `<CreationModeShell />`
- `StoryboardScreen.tsx` — Timeline + linked editing view of `<StoryboardPanel />`
- `MyAssetsScreen.tsx` — Character/scene/style/script library with version stacks, filter tabs, reference-image badges
- `StyleLibraryScreen.tsx` — 150–200 named styles grid/list, category filters, search, `/v1/styles/previews` thumbnails
- `SettingsScreen.tsx` — Provider keys (optional), theme, storage usage display

**`src/components/canvas/`**
- `InfiniteCanvas.tsx` — Pan/zoom surface using `react-native-reanimated` gestures + `@shopify/react-native-skia` drawing layer. Multi-select grouping via long-press. Stores node positions in local SQLite `canvas_layout` table.
- `StoryboardFrameChip.tsx` — Per-frame chip with context menu (re-roll, approve, change model, lock character/style). Renders `frame_id`, `thumbnail_uri`, `agent_source`, `status`.
- `ProjectNode.tsx` — Generic draggable card rendering for script/character/scene/animation outputs. Node has `node_type` (`script` | `character` | `scene` | `storyboard_frame` | `video_clip`), `payload_json`, `position_x`, `position_y`.
- `ImageReferenceZone.tsx` — Drag/paste handler that uploads to `/v1/assets` and returns `asset_id` to lock to character/style nodes.

**`src/components/creation/`**
- `CreationModeShell.tsx` — Collapsible right-aligned panel, toggles between Smart and Chat. Reads `mode` from `useCreationSession()`.
- `SmartFlow.tsx` — One-click orchestrator UI: shows pipeline stepper, calls `POST /v1/generate/smart` with `{ idea, style_id, model_ids }`. Polls `GET /v1/jobs/:id` for progress.
- `ChatInterface.tsx` — SSE consumer subscribing to `/v1/chat/stream?session_id=...`. Streams agent tokens. Per-message agent selector dropdown. Renders `<AgentStatusBubble />`.
- `AgentStatusBubble.tsx` — Visual representation of current agent + status (`queued` | `working` | `complete` | `failed` | `awaiting_approval`). Shows thumbnail preview when asset produced.

**`src/components/common/`**
- `ModelSelector.tsx` — Dropdown listing models grouped by Image/Video/Audio categories. Each chip shows `name`, `provider`, speed badge (`fast`/`balanced`/`quality`), capability tokens (`ref-image`, `first-frame`, `last-frame`, `video`, `audio`). Pulls from `/v1/models`.
- `StylePicker.tsx` — Modal/grid of style cards. Style object: `{ id, name, category, preview_uri, prompt_template, negative_prompt, recommended_models }`.
- `BentoIndicator.tsx` — Credit counter, active jobs, storage used. Reads `credits_remaining`, `storage_used_mb` from local SQLite `bento_cache` table, syncs via `GET /v1/usage`.

**`src/services/`**
- `apiClient.ts` — `fetch` wrapper with base URL, auth header injection, typed response handling
- `sseClient.ts` — EventSource wrapper managing reconnection, per-event handlers, abort
- `localDb.ts` — `expo-sqlite` connection wrapping `bento_cache`, `canvas_layout`, `recent_projects`, `offline_queue`
- `assetCache.ts` — Image/video blob cache to filesystem via `expo-file-system`

**`src/store/`**
- `useCreationSession.ts` — Zustand store holding `session_id`, `mode`, `style_id`, `model_ids`, `project_id`
- `useAgentLog.ts` — Tracks per-agent output history for the canvas

### Node Backend

**`server/router/`**
- `projects.ts` — Hono routes: `POST /v1/projects`, `GET /v1/projects`, `GET /v1/projects/:id`, `PATCH /v1/projects/:id`, `DELETE /v1/projects/:id`. Body schema: `{ title, idea, style_id, mode }`.
- `assets.ts` — `POST /v1/assets` (multipart upload), `GET /v1/assets?project_id=&type=`, `GET /v1/assets/:id`. Asset schema: `{ id, project_id, type, uri, metadata_json, created_at, version }`.
- `jobs.ts` — `GET /v1/jobs/:id`, `GET /v1/jobs?project_id=&status=`. Returns `{ id, status, progress, payload_json, result_json, provider, model, retries, created_at, completed_at }`.
- `styles.ts` — `GET /v1/styles`, `GET /v1/styles/:id`, `GET /v1/styles/previews`. Returns from `style_registry` table.
- `models.ts` — `GET /v1/models`, `GET /v1/models/:id`, `GET /v1/models/health`. Returns from `model_registry` table with live health checks.
- `chat.ts` — `GET /v1/chat/stream` (SSE upgrade), `POST /v1/chat/session`. Params: `{ session_id, project_id, message, target_agent, mode }`. Emits `agent.start`, `agent.token`, `agent.asset`, `agent.complete`, `agent.error` events.
- `generate.ts` — `POST /v1/generate/smart`, `POST /v1/generate/chat`. Consumes `{ idea, style_id, model_ids, project_id }`. Creates a job, enqueues it.

**`server/agents/`**
Each agent imports from `contracts.ts` and `providerRegistry.ts`, produces typed output, logs to `agent_runs` table.

```
contracts.ts
director.ts          # final assembly, sequencing, output coordination
scriptwriter.ts      # LLM: idea → scene breakdown, dialogue, shot list
artDirector.ts       # LLM: aesthetic direction, style prompt enrichment
characterDesigner.ts # LLM + image gen: character sheets, face-ID lock refs
sceneDesigner.ts     # LLM + image gen: background plates, environment refs
storyboardArtist.ts  # LLM + image gen: per-shot frame images
animator.ts          # video gen: 5–15s clips per storyboard frame
soundDirector.ts     # music/SFX gen or retrieval via mood-matched library
ipDesigner.ts        # optional 8th agent for IP-focused projects
```

Agent contract interface:
```typescript
interface AgentRunContext {
  project_id: string;
  session_id: string;
  idea: string;
  style: StyleRecord;
  models: ModelRecord[];
  prior_outputs: Record<AgentName, AgentOutput>;
}

interface AgentOutput {
  agent: AgentName;
  status: 'complete' | 'failed' | 'awaiting_approval';
  artifacts: Artifact[];
  raw_response: string;
  metadata: Record<string, unknown>;
}

interface Artifact {
  type: 'text' | 'image' | 'video' | 'audio';
  uri: string;
  asset_id?: string;
  prompt?: string;
  model_used?: string;
}
```

**`server/agents/pipeline.ts`** — Sequential (Smart mode) or on-demand (Chat mode) execution. Calls agents in order: `scriptwriter → artDirector → characterDesigner → sceneDesigner → storyboardArtist → animator → soundDirector → director`. Passes `prior_outputs` to each agent.

**`server/providers/`**
- `registry.ts` — Provider registry with `priority`, `capabilities`, `healthCheck()`, `failover()` methods.
- `providers/pollinations.ts` — Image gen, free, no key required. Used as fallback for `ref-image` thumbnails and quick storyboards.
- `providers/gemini.ts` — LLM text, free tier, used by `scriptwriter`, `artDirector`.
- `providers/groq.ts` — LLM text, fast inference, used by conversational agents.
- `providers/openrouter.ts` — Multi-model LLM routing, free models available.
- `providers/cerebras.ts` — LLM text, fast inference.
- `providers/cohere.ts` — LLM text, embeddings for asset similarity.
- `providers/cloudflare.ts` — Workers AI for images, free tier.

**`server/queue/`**
- `jobQueue.ts` — `better-queue` instance backed by SQLite. Polls `jobs` table every 2s. Supports 4 concurrent jobs per user. Job shape: `{ id, type, status, payload_json, result_json, provider, model, priority, retry_count }`. Status enum: `pull` → `processing` → `complete` | `failed` (→ `retry` if `retry_count < 3`).
- `worker.ts` — Worker loop popping jobs, dispatching to appropriate agent based on `payload.type` (`smart_full` | `agent_run` | `image_gen` | `video_gen` | `audio_gen` | `video_stitch`).

**`server/db/`**
- `schema.ts` — Drizzle schema for all tables below.
- `connection.ts` — Better-SQLite3 connection, migrations runner.
- `migrations/` — SQL migration files.

**`server/registries/`**
- `styles.seed.ts` — 150+ named styles with `{ id, name, category, preview_uri, prompt_template, negative_prompt, recommended_models[] }`. Categories: Anime, 3D CG, Pixel, Ink, Watercolor, Realistic, Cyberpunk, Clay, Ghibli, Naruto, OnePiece, etc.
- `models.seed.ts` — 25+ models with `{ id, name, provider, category, capabilities[], speed, cost_tier }`. Categories: Image, Video, Audio.

## Data Flow

### Smart Mode (one-click)

1. User types idea on `HomeScreen.tsx`, taps quick-create card → `useCreationSession` initialized with `{ mode: 'smart', idea, style_id }`.
2. Navigates to `CanvasScreen.tsx`. `SmartFlow.tsx` calls `POST /v1/generate/smart` with `{ idea, style_id, model_ids, project_id }`.
3. Backend `generate.ts` creates a `project` row, a `job` row of type `smart_full`, enqueues into `better-queue`.
4. Worker pops job → calls `pipeline.ts.runSmart(context)` which runs agents sequentially:
   - `scriptwriter.run(context)` → LLM call (Gemini/Groq) → returns scene breakdown, shot list → writes `agent_runs` row → emits SSE `scriptwriter.complete`
   - `artDirector.run(context)` → receives scriptwriter output → LLM call → returns style prompt enrichment → writes `agent_runs` → emits SSE `artDirector.complete`
   - `characterDesigner.run(context)` → LLM for character description → image gen (Pollinations/Cloudflare) → uploads to `assets` table with `type='character'` → emits SSE `characterDesigner.complete` with `{ asset_ids }`
   - `sceneDesigner.run(context)` → same pattern, `type='scene'`
   - `storyboardArtist.run(context)` → per-shot image gen → `type='storyboard_frame'` assets
   - `animator.run(context)` → per-frame video clip gen (5–15s) → `type='video_clip'` assets
   - `soundDirector.run(context)` → mood-matched audio → `type='audio'` assets
   - `director.run(context)` → stitches video clips, mixes audio → final `type='video'` asset
5. Frontend polls `GET /v1/jobs/:id` every 1s, receives `progress` percentage + current agent name. Updates `AgentStatusBubble` components.
6. On `status='complete'`, final `result_json` contains `{ final_video_uri, asset_ids[], storyboard_frame_ids[] }`. Canvas renders project nodes.

### Chat Mode (conversational)

1. User selects Chat mode in `CreationModeShell.tsx`. `ChatInterface.tsx` opens SSE connection: `GET /v1/chat/stream?session_id=...&project_id=...`.
2. User selects target agent from dropdown (e.g., "characterDesigner"), types message: "make the cat's eyes blue and more heroic".
3. `ChatInterface.tsx` sends `POST /v1/chat/session` with `{ session_id, project_id, message, target_agent: 'characterDesigner', mode: 'chat' }`.
4. Backend creates `job` with `type='agent_run'`, `payload_json={ agent: 'characterDesigner', message, context }`.
5. Worker dispatches to `characterDesigner.run(context)` which calls LLM with user's message appended to prompt → image gen → uploads asset.
6. SSE emits `agent.start` → multiple `agent.token` events (LLM thinking stream) → `agent.asset` (with thumbnail URI) → `agent.complete`.
7. Frontend renders tokens in chat bubble, shows "Approve" / "Re-roll" / "Change model" buttons on asset output.
8. User taps Approve → `PATCH /v1/assets/:id` with `{ status: 'approved' }`. Pipeline unlocks downstream agents to consume this asset.
9. User taps Re-roll → `POST /v1/generate/chat` with `payload={ re_roll: true, asset_id }`. Worker re-runs the agent, new asset row with incremented `version`.

### Asset Flow

- All generated artifacts upload to `assets` table with `project_id`, `type`, `uri` (filesystem path or CDN URI), `metadata_json`, `version`, `status`.
- `MyAssetsScreen.tsx` queries `GET /v1/assets?project_id=` and renders versioned stacks.
- Reference images pasted into `ImageReferenceZone.tsx` → `POST /v1/assets` with `type='reference'` → asset_id passed to agent `context.prior_outputs.characterDesigner.reference_asset_id` for face-ID/style locking.

### Job Queue Flow

```
User action → POST /v1/generate/* → generate.ts inserts jobs row (status='pull')
  → better-queue polls (every 2s) → worker picks job (status='processing')
  → dispatches to pipeline/agent → on success: status='complete', result_json populated
  → on failure: retry_count++, if <3 status='pull' else status='failed'
  → SSE notifies frontend subscribers on status change
```

## Tech Stack

### Frontend
- **Expo** SDK (React Native + Web via expo-node)
- **TypeScript** for all source
- **react-native-reanimated** 3.x — canvas gestures, transitions
- **@shopify/react-native-skia** — high-performance canvas rendering
- **expo-sqlite** — local persistence (`bento_cache`, `canvas_layout`, `recent_projects`, `offline_queue`)
- **expo-file-system** — asset blob caching
- **expo-secure-store** — auth token storage
- **zustand** — client state management (`useCreationSession`, `useAgentLog`)
- **EventSource** (browser native, polyfilled for RN) — SSE consumption

### Backend
- **Node.js** 20 LTS on Expo Server Functions
- **Hono** — HTTP router
- **better-sqlite3** — embedded database
- **Drizzle ORM** — type-safe schema, queries, migrations
- **better-queue** — in-memory job queue persisted to SQLite
- **zod** — request/response validation
- **EventSource** (server-side EventTarget) — SSE emission
- **fetch** (native) — upstream provider calls (Pollinations, Gemini, Groq, OpenRouter, Cerebras, Cohere, Cloudflare)

### Database Schema (SQLite via Drizzle)

```
projects:          id, title, idea, style_id, mode, created_at, updated_at
assets:            id, project_id, type, uri, metadata_json, version, status, created_at
storyboard_frames: id, project_id, frame_index, shot_description, image_asset_id, video_asset_id, audio_asset_id, duration
agent_runs:        id, project_id, session_id, agent, status, input_json, output_json, model_used, created_at
jobs:              id, project_id, type, status, payload_json, result_json, provider, model, priority, retry_count, created_at, completed_at
style_registry:    id, name, category, preview_uri, prompt_template, negative_prompt, recommended_models, created_at
model_registry:    id, name, provider, category, capabilities_json, speed, cost_tier, health_status, created_at
chat_sessions:     id, project_id, mode, created_at
canvas_layout:     id, project_id, node_type, payload_json, position_x, position_y, created_at
```

Indexes: `assets(project_id, type)`, `jobs(project_id, status)`, `agent_runs(project_id, agent)`, `storyboard_frames(project_id, frame_index)`, `canvas_layout(project_id)`.

### Testing
- **Vitest** — backend unit + integration tests
- **Jest** + **React Native Testing Library** — frontend component tests
- **Supertest** (Hono adapter) — API endpoint tests
- **Playwright** (Expo Web) — E2E smoke tests covering full create → generate → download flow
- Provider calls mocked in CI, real calls in local dev with `.env`

## API Surface

### Projects
```
POST   /v1/projects
  Body: { title: string, idea: string, style_id: string, mode: 'smart' | 'chat' }
  Returns: { id, title, idea, style_id, mode, created_at }

GET    /v1/projects?limit=20&offset=0
  Returns: { items: Project[], total: number }

GET    /v1/projects/:id
  Returns: Project & { assets_count, storyboard_frames_count, last_job_status }

PATCH  /v1/projects/:id
  Body: { title?, idea?, style_id?, mode? }

DELETE /v1/projects/:id
  Returns: { deleted: true }
```

### Assets
```
POST   /