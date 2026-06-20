# ASES — Autonomous Software Engineering System

## SOTA Quality Guarantee
Every app ASES generates passes **5 quality gates**:
1. **Planner** � Comprehensive plan including source, tests, config, CI/CD, docs, deployment
2. **Static Review** � AST analysis, linting (ruff/eslint), dep vuln scan (npm audit/pip-audit), **design compliance** (CSS variables, data-testid, focus-visible, semantic HTML, ARIA, reduced-motion)
3. **LLM Reviewer** � 15-point SOTA checklist (TypeScript strict, security, performance, accessibility WCAG 2.1 AA, observability, deployment readiness)
4. **Visual Review** � Screenshot capture + GPT-4o vision eval (layout, contrast, interactivity, polish)
5. **Interaction Review** � Playwright browser tests (click, type, hover, keyboard, touch, accessibility states)

## Quick Commands

| Task | Command |
|------|---------|
| Start dev stack | `docker compose -f docker-compose.dev.yml up -d` |
| Start prod stack | `docker compose -f docker/docker-compose.yml up -d` |
| View logs | `docker compose logs -f agent` |
| Run tests | `docker compose exec agent python -m pytest` |
| Open shell | `docker compose exec agent bash` |
| DB shell | `docker compose exec postgres psql -U ases -d ases_production` |
| Health check | `curl http://localhost:8000/health` |

## Architecture

```
n8n (orchestrator) → FastAPI Agent Service → Docker Sandboxes → PostgreSQL + Redis
```

**Key Components:**
- **agent_service/main.py** - FastAPI entry point, routes, auth, rate limiting
- **agent_service/agent_loop.py** - Core pipeline: Planner → Coder → Executor → Reviewer (5-iteration loop)
- **agent_service/sandbox.py** - Docker container management (1 CPU, 512MB, no network)
- **agent_service/job_queue.py** - RQ/Redis queue, async job processing
- **agent_service/worker.py** - RQ worker, runs `execute_job()` 
- **agent_service/db.py** - Async PostgreSQL (asyncpg), tenant config, execution persistence
- **agent_service/billing.py** - Cost enforcement (pre-flight + mid-job checkpoints)
- **agent_service/redis_cache.py** - Prompt cache (SHA-256 keys, per-agent TTLs)

## Core Patterns

### Agent Loop (agent_loop.py:535)
```python
async def run_multi_agent(task_type, payload, config, execution_id):
    # Routes: lead_pipeline, dev_*, outreach_personalize
```

### Dev Pipeline (agent_loop.py:562)
1. **Clarifier** - scores task clarity, augments requirements
2. **BillingFence** - preflight + per-iteration checkpoint
3. **Vector Memory** - retrieves similar past solutions (pgvector)
4. **Planner** - breaks task into file steps (gpt-4o-mini)
5. **Designer** - frontend pre-spec if needed (v2.6)
6. **Sandbox** - Docker container creation
7. **Iteration Loop** (max 5):
   - Coder generates files (gpt-4o)
   - Write to sandbox
   - Run tests (`npm test` / `pytest`)
   - Static review (ruff/eslint, AST, deps)
   - LLM Reviewer (gpt-4o-mini)
   - Visual review (Playwright screenshot diff)
   - Interaction review (behavior tests)
8. **On success**: GitHub commit → Vercel deploy

### Authentication (auth.py)
Headers required: `x-tenant-id`, `x-api-key`
- Keys stored as SHA-256 hashes
- Auto-bootstrap on first call (check logs for generated key)

### Sandbox (sandbox.py)
- `create_sandbox()` - spawns container, registers in Postgres + Redis counter
- `run_command()` - `docker exec` with timeout
- `cleanup_sandbox()` - stops container, removes workspace, decrements counter
- Max 10 concurrent (configurable via `MAX_CONCURRENT_SANDBOXES`)

### Job Queue (job_queue.py)
- RQ with priority queues (P0-P3) via scheduler.py
- Job status polling via `GET /jobs/{execution_id}`
- Retries: 2 attempts with 10s/30s backoff

## Environment Variables (.env)

Required: `OPENAI_API_KEY`, `GITHUB_TOKEN`
Optional: `VERCEL_TOKEN`, `TELEGRAM_BOT_TOKEN`, `UPWORK_RSS_URL`, `SENDGRID_API_KEY`

Production secrets auto-generated in .env.example:
- `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `N8N_BASIC_AUTH_PASSWORD`, `N8N_ENCRYPTION_KEY`, `ADMIN_SECRET`

## Database Schema (database/init.sql)

Key tables: `tenants`, `jobs`, `clients`, `executions`, `code_patterns` (vector), `sandbox_registry`, `design_specs`

## Non-Obvious Gotchas

1. **Docker-in-Docker**: Agent container needs `/var/run/docker.sock` mounted for sandbox creation
2. **API Key Bootstrap**: First request to new tenant returns 401 with key in logs — must capture it
3. **BillingFence**: Checks daily/monthly limits BEFORE job starts AND at each iteration
4. **Prompt Cache**: Redis cache returns (0,0) tokens on hit — don't add to billing
5. **Iteration Journal**: Scored constraint queue (not flat list) — only top 8 injected
6. **Design Regeneration**: Capped at 2 retries, then falls back to best A/B spec
6. **Vector Memory**: Uses pgvector cosine similarity (not ILIKE) for pattern retrieval
7. **Rate Limiting**: Sliding 60s window per tenant (20 RPM + 5 burst default)
8. **Worker Scaling**: `docker compose up --scale worker=4` for horizontal scaling

## Testing

```bash
# Quick dev task test
curl -X POST http://localhost:8000/dev-task \
  -H "Content-Type: application/json" \
  -H "x-tenant-id: default" \
  -H "x-api-key: YOUR_KEY" \
  -d '{"action":"scaffold","task":"Hello API","tech_stack":"Node.js + Express","project_name":"test"}'
```

Then poll: `curl -H "x-tenant-id: default" -H "x-api-key: YOUR_KEY" http://localhost:8000/jobs/{execution_id}`

## File Structure

```
agent_service/
├── main.py              # FastAPI app, routes, auth, lifespan
├── agent_loop.py        # Multi-agent orchestration
├── sandbox.py           # Docker sandbox management
├── job_queue.py         # RQ queue operations
├── worker.py            # RQ worker entrypoint
├── scheduler.py         # Priority queue scheduler
├── db.py                # PostgreSQL async layer
├── billing.py           # Cost enforcement
├── redis_cache.py       # Prompt caching
├── auth.py              # API key auth
├── parser.py            # FILE: block extraction
├── tools.py             # Cost calc, context truncation
├── models.py            # Pydantic models
├── config.py            # Settings (pydantic-settings)
├── observability.py     # Prometheus + OpenTelemetry
├── static_reviewer.py   # AST/lint/dep/security review
├── iteration_journal.py # Scored architectural memory
├── semantic_differ.py   # Interface regression detection
├── clarifier_agent.py   # Pre-flight ambiguity check
├── visual_reviewer.py   # Playwright screenshot diff
├── interaction_reviewer.py # Behavior test runner
├── design_agent.py      # Frontend design spec generator
├── design_regenerator.py # Design spec patch/regen
├── design_ab_tester.py  # A/B design spec selection
├── failure_classifier.py # Learned failure classification
├── dependency_debugger.py # Import graph error enrichment
├── interface_cache.py   # Cross-job signature cache
├── vector_memory.py     # pgvector pattern storage
├── testid_validator.py  # data-testid presence check
└── requirements.txt     # Python deps
```