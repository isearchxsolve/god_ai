## Requirements

### Audit & Gap Analysis (Phase 0)
- Produce a formal UI map of oiioii.ai covering landing, /features/canvas, /features/image-generation, pricing, and home screens. Diff against the existing `oioi` scaffold and log every missing route, component, and data source.

### Frontend — Expo (React Native + web via expo-node)
- Implement a responsive tab navigator with: Home, Canvas, Storyboard, My Assets, Settings.
- Build the landing/home screen with “Good morning, director!” greeting, quick-create cards (Story Anime, Music Video, 15s Creative Clip, Character Design, Scene Design, IP Creation, Viral Remake, Smart Script Breakdown), recently opened projects, and dark animation-studio visual language (deep black `#0A0A0B` base, neon `#7C3AED`/`#22D3EE` accents, 16px rounded cards, 1px `#FFFFFF14` borders, 40px motion-safe transitions).
- Build the Infinite AI Animation Canvas using `react-native-reanimated` + `@shopify/react-native-skia` pan/zoom, multi-select grouping, drag-paste image reference zones, per-frame chip context menus (re-roll, approve, change model, lock character/style).
- Build the dual-mode shell: Smart (one-click fully managed) and Chat (conversational conversational direction of individual agents) using a collapsible right-aligned panel. Chat must consume SSE streams and render agent status bubbles in real-time.
- Build the Style Library screen with 150–200 named styles, preview thumbnails loaded from `/v1/styles/previews`, category filter chips, search, and grid/list toggle.
- Build the Model Selector dropdown listing 25+ models grouped by category (Image, Video, Audio) — each chip showing name, provider, speed badge, capability tokens (`ref-image`, `first-frame`, `last-frame`, `video`, `audio`).
- Build My Assets screen (characters, scenes, styles, scripts) with version stacks, reference-image badges, and re-use buttons.
- Build a Bento/credit indicator showing remaining credits, active jobs, and storage used — persisted to local SQLite via `expo-sqlite` and synced from backend.
- Remove all placeholder/lorem text. Every string must be real product copy sourced from a translation file.

### Backend — expo-node GraphQL + tRPChybrid
- Expose REST routes via `hono` for `/v1/projects`, `/v1/assets`, `/v1/jobs`, `/v1/styles`, `/v1/models`, `/v1/chat/stream`, `/v1/generate`.
- Persist projects, assets, agent execution logs, storyboards, and job states in SQLite-backed Drizzle ORM tables (`projects`, `assets`, `storyboard_frames`, `agent_runs`, `jobs`, `style_registry`, `model_registry`) with indexes on `project_id` and `status`.
- Implement a job queue backed by SQLite + `better-queue` with `pull`, `processing`, `complete`, `failed`, `retry_count`, `payload_json`, `result_json`, `provider`, `model`, `priority`. Workers poll every 2 s and support up to 4 concurrent generations per user.
- Implement SSE chat endpoint (`/v1/chat/stream`) that streams agent tokens, status updates (`scriptwriter.working`, `character_designer.complete`, etc.), artifact URIs, and approval requests to the client.

### Provider Registry & Agent Pipeline
- Expand `models_registry` to 25+ real provider entries: Pollinations (flux, flux-realism, flux-anime, turbo), Gemini free (gemini-1.5-flash, gemini-1.5-pro), Groq (llama-3.1-70b-versatile, mixtral-8x7b), OpenRouter free tier (mistral-7b-instruct, nova-mistral-7b), Cerebras, Cohere command-r, CloudflareWorkers AI. Each entry must have `id, display_name, provider, category, context_window, capabilities[], max_output, latency_ms_est, priority, enabled, health_url`.
- Expand `styles_registry` to 150+ named styles with structured prompt templates: `style_id, display_name, category, positive_prompt, negative_prompt, recommended_models[], example_seed, preview_path`. Categories: Anime (30), 3D/Cg (25), Illustrated (25), Pixel/Retro (20), Painting (20), Photographic (15), Cyberpunk (10), Minimalist (15).
- Every agent must hold an explicit typed contract (`scriptwriter_contract.py`, `character_designer_contract.py`, etc.) defining input schema, output schema, retry policy, provider fallback chain, and required capabilities.
- Scriptwriter — calls LLM, outputs a JSON scene-by-scene script (title, logline, scenes with beat description, characters present, scene description, mood, duration_seconds, dialogue).
- Art Director — calls LLM, reviews script, outputs a shot list with framing, camera movement, style directives, and a constraint set for downstream agents.
- Character Designer — calls LLM for character description + image model for character sheet, stores reference image URI, assigns a persistent `character_id`, supports face-lock via reference image reuse.
- Scene Designer — calls LLM for scene description + image model for environment panels; each scene gets a `scene_id` and reference image URI.
- Storyboard Artist — calls LLM for shot framing + image model for each storyboard frame (N frames per scene), producing a frame list: `frame_id, scene_id, shot_index, prompt, seed, model_id, image_uri, first_frame_uri, last_frame_uri_estimate`.
- Animator — calls video model for each storyboard frame to produce 5–15s clips; stores clip URI, duration, and provider metadata. For longer videos, stitches via `ffmpeg` or `fluent-ffmpeg` in a worker process.
- Sound Director — calls music/SFX provider (or free-tier retrieval from freesound-style API if generation not available) matching scene mood; produces `audio_uri, duration_seconds, segments[]` tied to scene IDs.
- Director — final assembly agent that concatenates clips, overlays audio, writes `ffmpeg` concat demuxer commands, produces `final_video_uri`, and updates project status to `complete`.
- Smart mode orchestrates agents in a deterministic flow: Scriptwriter → Art Director → Character + Scene in parallel → Storyboard → Animator (per-shot concurrent, max 3) → Sound in parallel with Animator → Director. No user intervention required.
- Chat mode exposes agents individually via streaming, allowing user to direct, approve, re-roll, or skip any agent. Agent state machine persists `pending`/`working`/`awaiting_approval`/`rejected`/`approved`/`complete`.

### Real Generation Capabilities
- Auto-prompt optimization: before calling any image/video model, a lightweight LLM preprocessor expands the user prompt with selected style template, character reference, negative prompt, and model-specific safety tokens.
- First/last-frame image reference: video models supporting `image_ref` must accept a `first_frame_uri` and optionally `last_frame_uri` from the storyboard frame.
- Concurrent batch: image generation must parallelize up to 4 requests per user with per-request timeouts (30s) and provider failover.
- Final output must be a real MP4/WebM file accessible via a playable URL (local file server or CDN-backed blob). If ffmpeg stitching isn't feasible on free-tier, emit a frame-by-frame slideshow as fallback with explicit documentation in CONSUMER_COMPENSATION.md.

### Persistence & Auth
- JWT auth (mock or local) with `user_id`, `credits`, `created_at`. All routes require Bearer token.
- Project autosave every 30 s during active sessions and on every agent output emit.

### Tests
- Replace all stub-only unit tests with real integration tests that hit a free provider (at least one provider call per agent).
- E2E test: user submits "a shy cat becomes a superhero in rainy Tokyo" in Smart mode + Ghibli style, waits for the Director agent, and asserts final video URI is present and playable (even if 4 frames at 5fps).
- Add contract tests for every agent_contract file.
- Add provider health check tests that fail the build if any enabled free provider is unreachable.

### State & Documentation
- Update `.neon_project_state.json` to `phase: complete, status: verified, verified_against: oiioii.ai-2026-snapshot`.
- Update VERIFICATION.md with a test run log showing real generation output (URIs, durations, model IDs used) and a checklist mapping each success criterion to passing tests.
- Create CONSUMER_COMPENSATION.md listing every approximation (e.g., wired music retrieval instead of generated), the gap vs oiioii.ai, and the future premium path.

## Risks

- **Free-tier rate limits**: Pollinations/Groq/Gemini free tier can throttle under concurrent batch generation. Mitigation: implement provider priority + failover, exponential backoff (cap 5 retries, max 30 s), and cap concurrency at 3 for free providers. Document provider quotas in `providers/README.md`.
- **Character consistency limitation**: Free image models lack face-ID infrastructure. Prompt engineering + reuse of `first_frame_uri` as `image_ref` is only partially effective. Mitigation: enforce reference-image reuse on every downstream shot and document the limitation; prepare plugin interface for a future paid face-ID provider.
- **Video generation on free tier**: Pollinations does not offer true text-to-video. We may need to rely on frame interpolation (`ffmpeg minterpolate`) or external free providers if discovered. Risk: final video quality is visibly below oiioii.ai. Mitigation: accept the gap, use frame-interpolation stitching, document in CONSUMER_COMPENSATION.md, and keep the `Animator` interface provider-agnostic so a real video model can be slotted in.
- **Music/SFX gap**: No reliable free text-to-music API exists at scale. Mitigation: build a `SoundDirector` that queries free SFX APIs (freesound.org tier) and generates simple mood-based playlists. Fake-the-feature clearly. Leave a `MusicGeneratorProvider` interface ready for a premium slot (Suno/Udio).
- **SSE reliability on Expo web**: Expo's web fetch doesn't natively support EventSource in all polyfill configurations. Mitigation: use `react-native-sse` library or fallback to long-poll `/v1/jobs/:id/status` if SSE fails.
- **Long-running jobs blocking the event loop**: Node single-thread + image/video generation could stall the API. Mitigation: `better-queue` isolates work, job table is polling-driven, and we cap concurrency per user.
- **Infinite canvas performance**: Skia + Reanimated with >100 storyboard frames can drop below 60fps. Mitigation: virtualize off-screen frames with `react-native-reanimated` `useAnimatedReaction` on zoom level and recycle Skia picture caches.
- **Provider health flakiness**: Free providers can go dark without notice. Mitigation: periodic `health_check` job (every 5 min) disables failing providers automatically; UI shows disabled models as "currently unavailable" rather than crashing.
- **Copyright/ToS**: Using free LLM APIs for automated story generation may violate some provider ToS for commercial use. Mitigation: keep project clearly labeled as personal/non-commercial evaluation; document in `LEGAL.md`.

## Acceptance Criteria

1. A user logs in (or is auto-provisioned a mock JWT) and sees the landing page with “Good morning, director!” greeting, quick-create cards, and their projects list — pixel-conformant to oiioii.ai within 8px of reference layout on a 1440-wide viewport.
2. Selecting a quick-create card and entering a story idea in Smart mode + choosing a style triggers the Scriptwriter agent to call a real LLM (Groq or OpenRouter) and return a structured JSON scene list, visible in the UI within 10s.
3. The Art Director agent receives the script and emits a shot list with framing + style directives before any image generation begins.
4. The Character Designer agent produces at least one real generated character reference image (via Pollinations flux or equivalent) and the image is visible in My Assets under a persistent `character_id` with a face-lock badge.
5. The Scene Designer agent produces at least one real generated environment image per scene, visible in My Assets and inline in the Canvas.
6. The Storyboard Artist agent generates N real storyboard frames (where N ≥ scenes × shots_per_scene, default 2 shots/scene) visible as editable clips on the infinite canvas.
7. The Animator agent produces a real video clip (5+ seconds, MP4 or WebM) OR a stitched frame sequence for each shot, downloadable from the UI.
8. The Sound Director agent attaches audio (generated or retrieved) to at least 60% of scene frames, with segments aligned to scene durations.
9. The Director agent assembles the final video with audio via ffmpeg, produces a single `final_video_uri`, and the project status flips to `complete`. The video is playable in-app and downloadable.
10. Chat mode allows the user to open the right panel, select any agent, send a text instruction, and receive a streamed LLM response that updates the agent's output with the ability to approve/reject/re-roll.
11. Style Library is populated with 150+ named styles, each with a working preview image and a structured prompt template that is actually applied during generation (visible in the expanded "Prompt" drawer on a frame).
12. Model Selector dropdown lists 25+ models grouped by category, each with correct capability tokens, enabled flag driven by live provider health checks, and selecting a model changes downstream generation calls.
13. My Assets screen shows all created characters, scenes, styles, and scripts for the current project with version history and re-use buttons.
14. Projects persist across sessions: create a project, log out, log in, and the project reappears with all assets and storyboard frames intact.
15. Provider Registry has built-in failover: disable Pollinations mid-run by editing the DB or sending a fail signal; the next image generation retry routes to an alternate provider without crashing the pipeline.
16. Job Queue shows live progress per job in the UI: queued → working → complete, with elapsed time and retry count.
17. Auth is enforced: all `/v1/*` routes reject requests without a valid JWT with 401.
18. Test suite includes at least one integration test per agent that makes a real provider call and asserts a non-empty, schema-valid artifact. Tests must not rely on hardcoded strings.
19. A real end-to-end test (Playwright or Detox) submits the canonical prompt "a shy cat becomes a superhero in rainy Tokyo" in Smart mode + Ghibli style, waits up to 5 minutes, and asserts: project status `complete`, at least one character image exists, final video URI is present, and video duration ≥ 5 seconds.
20. `.neon_project_state.json` updated to `verified: true` with timestamp; VERIFICATION.md contains a test-run log showing real artifact URIs and model IDs; CONSUMER_COMPENSATION.md present and lists all approximation gaps with future premium paths.