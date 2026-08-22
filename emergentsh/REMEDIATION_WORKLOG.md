# REMEDIATION_WORKLOG — emergentsh (C:\god_ai\emergentsh)

Executing `D:\omniroute-monetizer\MASTER_REMEDIATION_PROMPT.md` gaps EM-1..EM-6.
Baseline before remediation: **8 failed, 68 passed, 1 skipped** (all 8 failures
pre-existing; root causes catalogued in entry #1).

---

### [2026-08-22] #1 — BASELINE RECON + ROOT-CAUSE CATALOGUE OF THE 8 PRE-EXISTING FAILURES

**[VERIFY]** Ran `python -m pytest tests/ -q` before touching anything:
`8 failed, 68 passed, 1 skipped in 5.35s`. Investigated each failure:

1. `tests/baseline/test_suite.py::TestL1VisionAndNIMExclusivity::test_no_mock_fallback_in_pipeline_router`
   — ROOT_DIR bug: `ROOT_DIR = Path(__file__).resolve().parents[1]` resolves to
   `emergentsh/tests/`, so it looks for `tests/backend/app/api/pipeline.py`.
   Needs `parents[2]`.
2. `test_next_config_has_standalone_output` — same ROOT_DIR bug (file exists
   and DOES contain `output: 'standalone'`; test just looks in wrong dir).
3. `test_workspace_component_hydration_safety` — same ROOT_DIR bug.
4. `test_frontend_dockerfile_multistage_structure` — same ROOT_DIR bug
   (frontend/Dockerfile exists, is multi-stage, copies .next/standalone).
5. `test_docker_compose_config_validity` — same ROOT_DIR bug (docker-compose.yml
   exists and references NIM_API_KEY/NVIDIA_API_KEY at lines 49-50).
6-8. `tests/test_integration.py::TestFullPipeline` (3 tests) — REAL pipeline
   bug, maps to gap EM-3: `AgentPipeline.run()` has a 3-retry self-heal loop
   for ValueError, but `stream_run()` has NO retry loop. The mock NIM client's
   designer branch yields a Markdown heading ("# Design Specification...")
   instead of JSON, DesignerAgent raises ValueError, stream_run fails the
   pipeline after 2 of 7 agents (`assert 2 == 7`). Also the mock fixture has
   no "qa"/"devops" branches, so even with retry parity the fixture needs
   those branches to complete all 7 agents.

Also discovered during recon:
- `backend/app/api/pipeline.py` routes `/run /stream /status /jobs /export
  /credits` are ALL unauthenticated; `USER_CREDITS = 10` is a process-global.
- `backend/app/core/auth.py:14` — `SECRET_KEY = os.getenv("SECRET_KEY",
  "your-secret-key-change-in-production")` — forgeable default, no boot check.
- Ambient shell carries stale `DATABASE_URL=postgres://postgres:***@localhost:5432/crypto_db`
  (legacy from another project; SQLAlchemy rejects the `postgres://` scheme).
  No existing test imports `backend.app.main`, which is why this never
  surfaced. New tests pin `DATABASE_URL=sqlite+aiosqlite` before import.
  (Secrets redacted per T11 — the password in that URL is a local dev default
  and is not logged here.)

---

### [2026-08-22] #2 — GAP-EM-1 FIXED: SECRET_KEY fail-closed boot + pipeline route auth + bcrypt/passlib runtime break

**[VERIFY]** Confirmed by reading `backend/app/core/auth.py` (hardcoded
forgeable default, no validation anywhere) and `backend/app/api/pipeline.py`
(six routes with zero auth dependencies, global credit counter).

**[FIX]** Three changes:

1. **Fail-closed boot** (`backend/app/core/auth.py` + `backend/app/main.py`):
   - Added `INSECURE_SECRET_KEYS` frozenset (empty string, the shipped
     default, and other common defaults), `MIN_SECRET_KEY_LENGTH = 32`.
   - Added `validate_secret_key(secret=None)` raising `RuntimeError` on
     missing / known-insecure / too-short keys.
   - `main.py` lifespan now calls `validate_secret_key()` BEFORE `init_db()`:
     a served app refuses to boot on a forgeable signing key. Module import
     stays side-effect-free so unit tests can still import.
2. **Route auth + job ownership** (`backend/app/api/pipeline.py`):
   - All six routes now take `current_user: User = Depends(get_current_active_user)`.
   - `/run` records `user_id` on the job; `_job_owner()` enforces ownership
     on `/status`, `/stream`, `/export` (returns 404, not 403, to avoid job
     existence leaks); `/jobs` is scoped to the owner (superuser sees all).
3. **Latent runtime break found while testing (fixed as part of EM-1):**
   `passlib 1.7.4` is incompatible with the installed `bcrypt 5.0.0` —
   `get_password_hash()` raised `ValueError: password cannot be longer than
   72 bytes` for ANY password, so `/api/auth/register` was broken at runtime
   (no test exercised it because the only TestAuth class lives inside a mock
   string literal in test_integration.py). Replaced the passlib CryptContext
   with direct `bcrypt.hashpw/checkpw` calls and explicit 72-byte truncation
   (bcrypt's algorithm cap, which passlib used to apply silently).

**[TEST]** New `tests/test_em1_auth_fail_closed.py` — **22/22 PASS**:
- `TestPasswordHashing` (3): hash/verify round trip, >72-byte password
  truncated not crashed, garbage hash returns False.
- `TestValidateSecretKey` (6): missing/known-default/short refused, strong
  accepted, every entry of INSECURE_SECRET_KEYS refused, shipped module
  default refused.
- `TestBootFailClosed` (3): lifespan raises on insecure default, raises on
  short key, boots cleanly on strong key.
- `TestPipelineRouteAuth` (10): 401 matrix across all six routes for
  anonymous callers; valid-token /run accepted and records owner; cross-user
  isolation (user B gets 404 on user A's status/export, A's jobs absent from
  B's list); /credits with token; token FORGED with the old insecure default
  key is rejected 401.

Test-infra notes (honest): pytest-asyncio 0.23.5 async fixtures crash with
`'FixtureDef' object has no attribute 'unittest'` on this pytest version, so
the client is a sync `client_factory` fixture returning an async context
manager. The get_db override must commit per-request (mirroring the real
get_db) or register→login can't see the new user.

**[VERIFY-REGRESSION]** Full suite after fix: **90 passed, 8 failed, 1 skipped**
— exactly the same 8 pre-existing failures as baseline (68+22=90), zero new
failures. The 8 are tracked for EM-3/EM-4 and the ROOT_DIR bug.

**[COMMIT]** next.

---

### [2026-08-22] #3 — GAP-EM-2 FIXED: per-user persisted credit ledger replaces process-global USER_CREDITS

**[VERIFY]** `backend/app/api/pipeline.py` had `USER_CREDITS = 10` as a
module global: every caller shared one balance, it reset on every restart,
and `/credits` reported it regardless of who asked. Meanwhile the schema
ALREADY had the right primitives unused by the pipeline: `User.credits`
(default 1000) and `CreditTransaction` (amount/transaction_type/description
audit rows, already used by /api/credits/purchase).

**[FIX]** `backend/app/api/pipeline.py`:
- Deleted the `USER_CREDITS` global entirely; added `PIPELINE_RUN_COST = 1`.
- New `_debit_credits(db, user, amount, description)`: raises 402 when the
  caller's persisted balance cannot cover the cost, else decrements
  `user.credits` and writes a `CreditTransaction(amount=-1,
  transaction_type="usage")` row; both land in the request session's single
  commit (atomic).
- `/run` now depends on `get_db` and calls `_debit_credits` before creating
  the job — a refused run creates no job.
- `/credits` now returns the CALLER's persisted balance
  (`current_user.credits`), not a shared global.

**[TEST]** New `tests/test_em2_credit_ledger.py` — **6/6 PASS**:
- global USER_CREDITS attribute is gone (regression guard)
- /credits reports own persisted balance (1000 model default, not 10)
- /run debits exactly 1 credit AND writes exactly 1 usage audit row
- zero balance -> 402 AND no job created
- user A's run leaves user B's balance untouched
- 3 runs -> balance 997 AND exactly 3 audit rows summing to -3 (atomicity)

**[VERIFY-REGRESSION]** Full suite: **96 passed, 8 failed, 1 skipped** —
same 8 pre-existing failures, zero new.

**[COMMIT]** next.
