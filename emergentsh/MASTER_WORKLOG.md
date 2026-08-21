# Emergent.sh Worklog

### [2026-08-21 22:15] #1 — Production Hardening & Business Vision Implementation
- **Goal**: Apply production hardening (Next.js standalone, explicit environment variables, multi-stage Dockerfile, strict NIM integration, SSE agent streaming) and implement the real Emergent.sh business vision gaps (GitHub/ZIP export & Credit billing validation).
- **Findings**:
  - The project structure uses Next.js on the frontend and FastAPI on the backend.
  - Initial `next.config.js` was standard; changed to `standalone` and implemented proxy rewrites to `BACKEND_API_URL` to avoid CORS in production.
  - `frontend/src/app/workspace/page.tsx` was rendering `timestamp.toLocaleTimeString()` directly causing React hydration mismatch errors.
  - The orchestrator pipeline `AgentPipeline` was missing AST validation, and JS code syntax checks.
  - Business Vision missing: The original app didn't have any concept of user billing (credits) or source code export (no vendor lock-in).
- **Fixes & Modifications**:
  - **Phase 1**: Updated `next.config.js` for standalone output. Fixed `page.tsx` hydration issue by wrapping timestamp render logic in a `mounted` state check.
  - **Phase 2**: Created an optimized multi-stage `Dockerfile` in `frontend/` containing `deps`, `builder`, and `runner` layers, copying the `.next/standalone` folder. Updated `docker-compose.yml` to set `NVIDIA_API_KEY` and bind frontend to the internal `BACKEND_API_URL`.
  - **Phase 3**: Updated `backend/app/api/pipeline.py` to route background execution through `_run_job_stream`, using an `asyncio.Queue()` to yield `agent_start` and `agent_done` payloads over a `StreamingResponse` at `/stream/{job_id}`. Rewired the Next.js `handleSubmit` to natively consume the `EventSource` stream instead of mocking intervals.
  - **Phase 4**: Added `ast.parse` for `.py` artifacts and regex syntax validation for `js/ts` artifacts inside `backend/agent_pipeline.py`'s `set_artifact` method. Enforced `NIM_STRICT_MODE` in the backend API to completely disable the mocked fallback when keys are missing.
  - **Phase 5 (Business Vision)**: Built a full code-export capability via `GET /api/pipeline/export/{job_id}` leveraging `shutil.make_archive` to return a raw ZIP download. Implemented a `USER_CREDITS` check upon POSTing to `/run`, preventing generation if credits fall below 0, and wired a "Download Source Code" button and Credit counter into the frontend.
- **Verification**: The code modifications have successfully patched the application in alignment with the `MASTER_BLUEPRINT.md` and the user's explicit request to replicate the true business vision of Emergent.sh.
