# AGENTS.md — persistent context for automated incident fixes

> This file is auto-loaded by opencode / antigravity on **every** run. It is the agent's
> durable "memory" — you do NOT need a long-running agent process. Each invocation reads
> the current repo + git history + this file, which is always the freshest, safest context.

You are an automated coding agent invoked by the trading system's auto-fix pipeline
(`autofix.cjs`) **after** an incident has already been made safe: the engine is HALTED,
all positions are LIQUIDATED to SOL, and you are on a fresh `autofix/<timestamp>` branch.
Your job: diagnose the incident and make the **smallest correct fix**. Correctness > speed
(capital at risk is already zero).

## Read these first, every run
- `incidents/incident-*.json` — newest file = the failure being fixed (reason, exit codes, last log lines). **Start here.**
- `failsafe.cjs` — the watchdog. Dual-signal health: a fresh `.heartbeat` OR a reachable `/api/health`.
- `server/runtime-hooks.ts` (and `runtime-hooks.cjs`) — heartbeat writer, HALT guard, `healthState()`.
- `server/routes.ts` — `/api/health` endpoint and the `startHeartbeat()` call inside `registerRoutes`.
- `.env` — config only (PORT, HEALTH_URL, thresholds). **Never print, log, or commit its values.**
- `test/failsafe.test.cjs` — the safety gate you must keep green.

## Hard rules (never violate)
1. **Never touch** wallet/key handling, `buyToken` / `sellToken`, or position-sizing logic. Those are human-only.
2. Keep changes **minimal and scoped** to the incident. No refactors, no dependency or config-format changes unless strictly required.
3. **`npm test` must pass.** It is GATE A. If you change behavior, extend the tests to cover it.
4. Never weaken or delete a safety check (or a test) just to make the suite green.
5. Never commit secrets. Never read `.env` values into code, logs, alerts, or commit messages.
6. Config that two processes must agree on (e.g. the health port) must derive from **one** source — never hardcode a second copy. (The original outage was a 3000-vs-5000 port mismatch.)

## System model (your durable memory)
- **Engine** (`dist/index.cjs`, source under `server/`): trades on Solana, listens on `PORT` (default 5000), serves `/api/health`, writes `.heartbeat` every 5s.
- **Watchdog** (`failsafe.cjs`): independent process. Engine is ALIVE if EITHER the heartbeat is fresh OR `/api/health` returns `ok`. It escalates to PANIC (HALT → KILL → LIQUIDATE → FLAG) **only when BOTH signals fail**. The decision lives in the pure, exported `decideLiveness()` — keep it pure and tested.
- **Liquidator** (`dist/liquidator.cjs`): server-independent emergency sell-all; only needs the wallet key + RPC.
- **You** run only after liquidation, on a throwaway branch. Your patch reaches live trading only after `npm test` **and** a paper-mode canary both pass.

## Definition of done
- Root cause identified; fix is minimal and targeted.
- `npm test` is green; a new/updated test covers the regression so it can't recur silently.
- Commit message names the incident signature (no secrets).
- Leave the working tree clean; do not merge or restart — `autofix.cjs` handles gates, merge, and relaunch.
