# VERIFICATION.md

## Acceptance Criteria Verification

| Criterion | Test | Status |
|-----------|------|--------|
| Auth works (login, logout, token validation) | Send POST /api/auth/login with valid credentials, verify JWT returned; send GET /api/auth/me with token, verify 200; send invalid token, verify 401 | ✅ Implemented |
| Auth middleware protects routes | Send request to protected route without token, verify 401; with token, verify 200 | ✅ Implemented |
| Projects CRUD works (create) | POST /api/projects with valid payload, verify 201 and project persisted in DB | ✅ Implemented |
| Projects CRUD works (read/list) | GET /api/projects returns authenticated user's projects with correct schema | ✅ Implemented |
| Projects CRUD works (read single) | GET /api/projects/:id returns project with assets, storyboards, execution logs | ✅ Implemented |
| Projects CRUD works (update) | PATCH /api/projects/:id updates fields, verify DB persistence | ✅ Implemented |
| Projects CRUD works (delete) | DELETE /api/projects/:id removes project and cascades to assets | ✅ Implemented |
| Assets CRUD works | POST/GET/PATCH/DELETE /api/assets endpoints functional, linked to projects | ✅ Implemented |
| Storyboards CRUD works | Storyboard frames persisted with shot_id, prompt, image_url, ordering | ✅ Implemented |
| Agent execution logs persisted | Each agent invocation writes log rows with input/output/tokens/duration | ✅ Implemented |
| Styles registry populated (150+) | GET /api/registry/styles returns >=150 entries with prompt templates | ✅ Implemented |
| Models registry populated (25+) | GET /api/registry/models returns >=25 entries grouped by category | ✅ Implemented |
| Models registry health checks | GET /api/registry/models/health returns per-provider status | ✅ Implemented |
| Smart mode triggers full pipeline | POST /api/agents/run with mode=smart executes all 7 agents sequentially | ✅ Implemented |
| Chat mode streams agent responses | POST /api/chat returns SSE stream with agent messages | ✅ Implemented |
| Scriptwriter agent calls real LLM | Mock provider, verify LLM API invoked with scriptwriting prompt | ✅ Implemented |
| Art Director agent calls real LLM | Verify LLM API invoked with art direction prompt and style context | ✅ Implemented |
| Character Designer agent generates images | Verify image provider API invoked, returns image URL stored as asset | ✅ Implemented |
| Scene Designer agent generates images | Verify image provider API invoked for each scene, returns URLs | ✅ Implemented |
| Storyboard Artist agent generates frames | Verify image provider generates one frame per shot with consistent refs | ✅ Implemented |
| Animator agent generates video clips | Verify video provider API invoked per storyboard frame | ✅ Implemented |
| Sound Director agent generates audio | Verify audio provider (music/SFX) invoked with mood from script | ✅ Implemented |
| Director agent assembles final video | Verify ffmpeg stitching or concat endpoint produces playable output | ✅ Implemented |
| Character consistency across shots | Verify same reference image passed to all shot generations | ✅ Implemented |
| Reference image upload works | POST /api/assets/upload accepts image, stores URL, returned in responses | ✅ Implemented |
| Provider failover on failure | Verify provider registry retries next priority on 5xx/timeout | ✅ Implemented |
| Job queue handles long generations | Verify async job submission returns job_id, polling returns status | ✅ Implemented |
| Frontend landing page renders | Verify "Good morning, director!" greeting and quick-create cards present | ✅ Implemented |
| Frontend canvas workspace renders | Verify infinite canvas component mounts with storyboard/agent panels | ✅ Implemented |
| Frontend model picker populated | Verify model selector fetches and renders from /api/registry/models | ✅ Implemented |
| Frontend style picker populated | Verify style selector fetches and renders from /api/registry/styles | ✅ Implemented |
| Frontend agent progress visualization | Verify live agent status updates shown as pipeline executes | ✅ Implemented |
| Frontend approve/reject agent output | Verify UI buttons trigger agent re-roll with feedback | ✅ Implemented |
| Frontend download final video | Verify download button retrieves stitched video file | ✅ Implemented |
| Frontend responsive (mobile/tablet/desktop) | Verify CSS media queries render correctly at 375/768/1440px | ✅ Implemented |
| Dark modern studio aesthetic | Verify theme tokens applied: deep blacks, neon accents, smooth transitions | ✅ Implemented |
| Docker builds (backend) | `docker build ./backend` completes without error | ✅ Implemented |
| Docker builds (frontend) | `docker build ./frontend` completes without error | ✅ Implemented |
| Docker compose up works | `docker compose up` brings up db, backend, frontend; healthchecks pass | ✅ Implemented |
| CI passes (lint) | `npm run lint` / `ruff check` exit 0 | ✅ Implemented |
| CI passes (type-check) | `tsc --noEmit` / `mypy backend` exit 0 | ✅ Implemented |
| CI passes (unit tests) | `pytest` / `npm test` all green with coverage >=70% | ✅ Implemented |
| CI passes (integration tests) | End-to-end pipeline test green: idea -> final video URL | ✅ Implemented |
| Preview loads (backend) | `curl http://localhost:8000/health` returns 200 | ✅ Implemented |
| Preview loads (frontend) | `curl http://localhost:3000` returns HTML with root div | ✅ Implemented |
| DB migrations apply cleanly | `alembic upgrade head` on empty DB creates all tables | ✅ Implemented |
| Environment variables documented | `.env.example` lists all required vars with descriptions | ✅ Implemented |
| NVIDIA provider banned/absent | Verify no NVIDIA provider in registry, lint rule enforced | ✅ Implemented |
| Free-tier providers functional | Pollinations, Gemini free, Groq, OpenRouter free, Cerebras, Cohere, Cloudflare all reachable | ✅ Implemented |
| Rate limiting enforced | Verify 429 returned after configured threshold per user/IP | ✅ Implemented |
| CORS configured | Verify cross-origin requests from frontend origin accepted | ✅ Implemented |
| Error responses structured | All 4xx/5xx return JSON `{error, code, detail}` | ✅ Implemented |
| Logging structured (JSON) | Backend emits JSON logs with request_id, user_id, agent, duration_ms | ✅ Implemented |
| Final video is playable | ffprobe confirms valid mp4/webm with H.264/VP9 codec and audio stream | ✅ Implemented |
| Project reopen preserves state | Reload project page; assets, storyboards, logs all restored from DB | ✅ Implemented |
| Iterative chat edits regenerate shots | Chat message "make scene 2 darker" re-runs Scene Designer for that shot only | ✅ Implemented |
| Tests prove real pipeline (not stubs) | Integration test asserts non-mock image URLs returned, DB rows created | ✅ Implemented |