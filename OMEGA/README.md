# OMEGA SOTA UI

Dynamic automation agent: web research → plan (DAG) → materialize deliverables → **verify / learn / fix** → zip.

## Quick start

```powershell
pip install -r requirements.txt
$env:GROQ_API_KEY = "your-key"
python -m omega_agent.ui.gradio_app
```

Mock mode (no API key, fast, skips npm verify):

```powershell
python -c "import asyncio; from omega_agent import OmegaAgent, Config; asyncio.run(OmegaAgent(Config(use_mock_llm=True)).run('Build a React app'))"
```

## Deliverable verification loop

For build / workspace goals with LLM credentials enabled:

1. Materialize files (`llm_generate_files`, scaffolds, etc.)
2. DAG task **`verify_deliverable`**: `run_shell` with install + build + test
3. **Finalize convergence**: on failure, LLM reads stderr → patches files → re-runs verify (up to N times)
4. Zip only when verify passes (unless `OMEGA_DELIVERABLE_ZIP_ON_FAILURE=true`)

See [docs/CONVERGENCE.md](docs/CONVERGENCE.md) for architecture and notebook parity.

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Groq LLM (recommended) |
| `OMEGA_DELIVERABLE_VERIFY_ENABLED` | `true` | Enable verify/fix loop |
| `OMEGA_DELIVERABLE_VERIFY_MAX_RETRIES` | `5` | Max verify→fix cycles |
| `OMEGA_DELIVERABLE_VERIFY_TIMEOUT` | `300` | Shell timeout per verify (seconds) |
| `OMEGA_DELIVERABLE_ZIP_ON_FAILURE` | `false` | Zip project even if verify failed |
| `OMEGA_DEFAULT_TENANT_ID` | `default` | Tenant namespace for workspaces |
| `OMEGA_MAX_CONCURRENT_GOALS` | `8` | Max parallel goal executions (API) |
| `OMEGA_GRADIO_CONCURRENCY` | `4` | Gradio queue workers |
| `OMEGA_REDIS_URL` | — | Shared session store (required for multi-replica) |

See [docs/SCALING.md](docs/SCALING.md) for multitenancy and production deployment.

### Smoke test (real LLM + npm)

```powershell
$env:GROQ_API_KEY = "your-key"
python scripts/run_deliverable_verify_smoke.py
```

## Tests

```powershell
python -m pytest test_deliverable_convergence.py test_build_actions.py test_interactive_ui.py -q
```

## API

```powershell
uvicorn omega_agent.api:app --reload
```


$env:OMEGA_LLM_PROVIDER="google"
$env:GOOGLE_API_KEY="AQ.Ab8RN6LG_UF9yptggeb8AGympiohU0VydWcbmXmLxe7Hc5dCsg"
python -m omega_agent.cli --ui


$env:OMEGA_LLM_PROVIDER="github"
$env:GITHUB_TOKEN="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"
$env:OMEGA_TENANT_RPM_LIMIT="14"  # You can set this high because GitHub has high limits
python -m omega_agent.cli --ui

$env:OPENROUTER_API_KEY="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"
$env:OMEGA_LLM_PROVIDER="openrouter"
$env:OMEGA_TENANT_RPM_LIMIT="14"
python -m omega_agent.cli --ui



$env:MOONSHOT_API_KEY="sk-cl7ht2Gf0rFsXqCSkwX9avZWVjeZ2uCCzZuGalJihpe6tWHE"
$env:OMEGA_LLM_PROVIDER="moonshot"
$env:OMEGA_TENANT_RPM_LIMIT="20"
python -m omega_agent.cli --ui


$env:OMEGA_LLM_PROVIDER="groq"
$env:GROQ_API_KEY="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"
$env:OMEGA_TENANT_RPM_LIMIT="14"   # Groq free tier allows ~30 RPM
python -m omega_agent.cli --ui


check the zip contents if the solution is actually solving tsp at O(n) time

✓ Wrote 4 file(s) to .\outputs\workspaces\default\tsp_workspace\project; generated 4 files via LLM reasoning over 2 evidence snippets; generated 4 files via LLM reasoning over 2 evidence snippets
✓ Created zip .\outputs\workspaces\default\tsp_workspace\tsp_workspace-20260605-112507.zip (1.4 KB)

b
