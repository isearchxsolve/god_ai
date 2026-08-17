# FLEET WORKLOG — ASES v3.1 production hardening

Live, append-only monitoring feed. Newest entries at the bottom.

### [step 1] Baseline assessment
- Reviewed added agent modules, DB schema, and n8n orchestrator contract.
- Identified schema gaps for vector memory, design specs, interface cache, and failure classifier tables.
- Identified lint/runtime hazards in interaction_reviewer dead code and job_queue retry import ordering.

### [step 2] Added schema and module hardening
- Extended database/init.sql with pgvector, code_patterns tech_stack/embedding, design_specs, interface_signatures, tenant_classifiers, and classifier_training_data.
- Fixed vector_memory and design_agent upserts to use explicit hashes and existing/added schema constraints.
- Fixed interaction_reviewer undefined helper constants/imports, static_reviewer event-loop usage, and job_queue Retry import ordering.

### [step 3] Added generated QA suite bootstrap
- Created new tests/test_zprod_*.py parameterized suites covering design scoring, semantic diff, static design compliance, dependency parsing, journal scoring, failure classifier, interface cache, visual gate, interaction spec generation, design agent parsing, and n8n contract.
- Added a smoke-marked subset in tests/test_zprod_smoke.py.
- Next blocker: need existing tests/ directory and core executor files in chat to stabilize baseline, harden sandbox executor, and verify every test status.

### [step 4] Fixed SyntaxError in test_zprod_static_design_compliance.py
- Line 23 had an extra `}` closing brace (`"}}]` → `"}]`), causing a SyntaxError that blocked test collection.
- SQL linter warnings on init.sql are false positives (flake8 parsing SQL); no changes needed.
- Next: run full test suite to verify collection passes.

### [step 5] Production-readiness audit started
- Confirmed an existing append-only worklog and pre-existing local modifications; no `CHANGES*.md` files will be modified.
- Inventory found a Docker-backed sandbox with resource flags but no command allowlist, plus dependency ranges in `agent_service/requirements.txt`.
- Next: capture the authoritative pytest baseline and inspect the current test contracts before changing behavior.

### [step 6] Authoritative baseline failed at collection
- Ran `python -m pytest tests/ -v`: 3,048 cases discovered, then collection stopped with exit code 1.
- Actual blocker: `tests/test_design_regenerator.py` imports missing `design_regenerator._apply_patches` (ImportError); pytest also warns that `asyncio_default_fixture_loop_scope` is unsupported by installed pytest-asyncio.
- Next: restore the tested patch helper contract and rerun collection before addressing runtime failures.

### [step 7] Restored design-regeneration helper contract
- Implemented safe JSON extraction, constrained in-memory patching, test-id derivation, and complete design-token CSS flattening in `agent_service/design_regenerator.py`.
- Verified `tests/test_design_regenerator.py` and `tests/test_zprod_design_regenerator.py`: 253 passed, exit code 0; the pytest-asyncio configuration warning remains.
- Next: rerun the full suite to identify every remaining failure, then add executor/pipeline hardening without reducing coverage.

### [step 8] Hardened executor boundary and added adversarial coverage
- Added exact command allowlisting, container-name validation, timeout bounds, byte-capped UTF-8 output, and resolved workspace-path jail enforcement in `agent_service/sandbox.py`.
- Added `tests/test_executor_security.py`; sandbox + adversarial suite passed 36/36 (exit code 0), proving command-injection and traversal inputs never reach subprocess execution.
- Next: remove credential-like example values, correct deployment configuration, and run the full suite after the changes.

### [step 9] Hardened startup and deployment configuration
- Added startup validation and awaited sandbox cleanup; pinned `agent_service/requirements.txt`, redacted `.env.example`, required production secrets in Compose, enabled n8n healthchecks, and replaced the invalid root Dockerfile with a non-root image.
- Initial config verification had one failure because Windows did not regard Linux `/tmp/...` paths as absolute; the validator now accepts POSIX absolute paths for Linux deployment and retains relative-path rejection.
- Next: verify config plus service tests, refresh README/CI documentation, then run the complete suite.

### [step 10] Verified config controls and completed operator documentation
- `tests/test_config_hardening.py` plus `tests/test_main.py` passed 17/17 (exit code 0); removed an unsupported pytest-asyncio setting that had produced a warning.
- README now documents the four-stage loop, gates, full/smoke/security commands, n8n wiring, required secrets, and key runtime settings; CI now lints and runs the full suite on every push.
- Next: run full collection and tests, smoke subset, lint, and Compose syntax validation; log every result without suppressing failures.
