# 🚀 Solana Memecoin Sniper V9 — Moonshot Architecture
# Autonomous 1000x-100000x World-Record Hunter

> **Complete source code for a production-grade autonomous memecoin trading engine.**
> Built for the Solana blockchain. Designed to hunt the 0.01% of memecoins that achieve 1000x-100000x returns.

---

## ⚡ 30-Second Summary

This is **NOT a trading course.** This is **NOT a signal group.**

This is the **complete source code** for a production-grade quantitative trading engine that:
- Scans **5+ data sources** every 10 seconds for fresh memecoin launches
- Scores candidates with **8 weighted factors** + ML blend + whale convergence
- Runs **6-layer safety gates** (RugCheck, whale detection, LP veto, Jupiter preflight)
- Enters positions via **Jupiter V6** with automatic slippage control
- Exits via **5-tier cascade** (hard floor → partial bank → trailing stop → hard ceiling → moonshot)
- Includes **dual-signal failsafe** watchdog + independent liquidator
- Tracks **honest execution costs** via Shadow Ledger (real Jupiter quotes)

**221 closed paper trades** on real Solana memecoin pairs informed the architecture. The system moved from **-2.14% to -0.33% expectancy** through three surgical fixes.

---

## 📦 What You Get

### Source Code (5400+ Lines of Production TypeScript)
- `server/routes.ts` — The main engine (discovery, scoring, safety, execution, exits)
- `server/jupiter.ts` — Jupiter V6 swap integration with RPC health rotation
- `server/runtime-hooks.ts` — Heartbeat + HALT guard + health endpoint
- `server/storage.ts` — PostgreSQL persistence via Drizzle ORM
- `failsafe.cjs` — Independent watchdog process (HALT → KILL → LIQUIDATE → FLAG)
- `fast_scanner.cjs` — WebSocket memecoin discovery (Raydium + PumpSwap)
- `client/` — React dashboard for real-time monitoring
- `test/` — Failsafe safety invariant test suite

### Configuration & Deployment
- `.env.example` — Complete environment template with all required API keys
- `ecosystem.config.cjs` — PM2 production process manager config
- `engine_settings.json` — Default tuning parameters (all adjustable)
- One-click Windows launchers: `START.cmd`, `STOP.cmd`, `PANIC.cmd`, `STATUS.cmd`, `DASHBOARD.cmd`

### Documentation
- `SETUP_GUIDE.md` — Step-by-step deployment from zero
- `TUNING_GUIDE.md` — How to adjust every parameter
- `SAFETY_GUIDE.md` — Failsafe, circuit breakers, and risk architecture
- `API_REFERENCE.md` — All REST endpoints for the dashboard
- `TROUBLESHOOTING.md` — Common issues and fixes
- `MOONSHOT_ARCHITECTURE.md` — The architectural manifesto
- `LINKEDIN_ARTICLE_BRIEF.md` — The 221-trade calibration story

### Scripts & Tools
- `validate-paper.ps1` — Paper-mode validation run
- `paper-validate.ps1` — Extended paper test with metrics
- `analyze-shadow.cjs` — Shadow ledger analysis tool
- `go_paper.cjs` / `go_live.cjs` — Mode switchers
- `harden_safety.cjs` — Safety hardening script
- `boost_discovery.cjs` — Discovery frequency booster

---

## 🏗️ Architecture Overview

### The Moonshot Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1: Discovery (Every 10 seconds)                       │
│  • DexScreener (22 DEX seeds)                                │
│  • GeckoTerminal (trending + new pools)                     │
│  • Jupiter Verified + Top-Traded                            │
│  • Birdeye (top-volume + top-liquidity)                     │
│  • WebSocket fast scanner (Raydium + PumpSwap)             │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2: Scoring (0-100 composite score)                    │
│  • Liquidity, Buy Pressure, Volume Momentum               │
│  • Price Change, Tx Velocity, Age, FDV Ratio              │
│  • ML blend (10% weight)                                   │
│  • Smart-money convergence (Birdeye top_traders)            │
│  • Whale accumulation/distribution scoring                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3: Safety (6 gates before any buy)                  │
│  • RugCheck: Freeze/Mint authority, LP-unlocked veto        │
│  • Full report: Holder concentration, LP lock %, insider %│
│  • Whale distribution: Net sellers ≥3 → immediate exit      │
│  • Jupiter preflight: Real buy + sell quote simulation      │
│  • Price drift: Anti-chase (reject >25% 5m pump)           │
│  • Edge calculation: expectedMove - roundTripCost ≥ minEdge │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4: Execution (Jupiter V6)                           │
│  • RPC health rotation (Helius + QuickNode + mainnet)       │
│  • Jito bundle engine (MEV protection)                      │
│  • Anti-overspend guard (rejects >110% of target size)      │
│  • Desync grace period (180s for RPC propagation)           │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5: Exit (5-tier cascade)                            │
│  T1: DEEP_RUG_KILL (-50%), PRICE_RUG (-25% from peak)      │
│  T2: HARD_TAKE_PROFIT (+80%), TRAIL_STOP (+15%/-6%)       │
│  T3: NEVER_GREEN_CUT (peak≤1%, hold≥18s, pnl≤-5%)        │
│  T4: MOMENTUM_FADE, LIQUIDITY_EXHAUSTION, VOL_COLLAPSE    │
│  T5: MAX_HOLD (dynamic), ABSOLUTE_MAX_HOLD (1200s)        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  LAYER 6: Safety (Independent watchdog)                    │
│  • Dual-signal failsafe (heartbeat + HTTP health)           │
│  • HALT → KILL → LIQUIDATE → FLAG cascade                  │
│  • Circuit breakers (BTC crash, daily loss, max drawdown)  │
│  • Shadow ledger (honest execution cost tracking)          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎮 Quick Start

### Prerequisites
- Node.js 20+ (recommended: 24 LTS)
- PostgreSQL 15+ (local or cloud)
- Git

### 1. Install & Configure (5 minutes)

```bash
# Clone or unzip the source
cd solana-memecoin-sniper-v9

# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env with your API keys:
# - SOLANA_RPC_URL (Helius or QuickNode)
# - WALLET_PRIVATE_KEY (DEDICATED trading wallet — NOT your main wallet)
# - BIRDEYE_API_KEY_1, _2, _3 (optional but recommended)
# - DATABASE_URL (PostgreSQL connection)
# - ADMIN_SECRET (dashboard password)
```

### 2. Initialize Database (2 minutes)

```bash
# Create the database
npx drizzle-kit push

# Or create manually:
# CREATE DATABASE crypto_db;
```

### 3. Start the Engine (1 minute)

```bash
# Windows (one-click)
START.cmd

# Or manually:
npx cross-env NODE_ENV=development tsx server/index.ts
```

### 4. Open the Dashboard

Navigate to `http://localhost:5000` in your browser.

Default mode: **PAPER**. No real money at risk.

### 5. Verify Paper Mode

Check the dashboard:
- Trading Mode: **paper**
- Wallet Balance: **0.0500 SOL** (starting balance)
- Engine Status: **Running**

You should see scan logs in the terminal: `[SCAN] Discovery: X candidates found.`

---

## ⚙️ Configuration

### Key Environment Variables

```env
# MODE: "paper" or "live" (ALWAYS start with paper)
MODE=paper

# Solana RPC (Helius recommended — free tier: 10M CU/day)
SOLANA_RPC_URL=https://mainnet.helius-rpc.com/?api-key=YOUR_KEY
SOLANA_RPC_BACKUP_URL=https://your-quicknode-url

# Wallet (DEDICATED wallet with minimal funds)
WALLET_PRIVATE_KEY=your_base58_private_key_here

# Birdeye (free tier: 60 RPM, 1000 CU/day — use multiple keys)
BIRDEYE_API_KEY_1=your_key_1
BIRDEYE_API_KEY_2=your_key_2
BIRDEYE_API_KEY_3=your_key_3

# Jito (MEV protection + priority inclusion)
JITO_ENGINE_URL=https://tokyo.mainnet.block-engine.jito.wtf/api/v1/transactions
JITO_TIP_LAMPORTS=100000
PRIORITY_FEE_LAMPORTS=100000

# Database
DATABASE_URL=postgres://postgres:postgres@localhost:5432/crypto_db

# Admin
ADMIN_SECRET=your_secure_password_here

# Paper seed (optional — override starting balance)
PAPER_SEED=0.05
```

### Engine Settings (Tunable via Dashboard or `engine_settings.json`)

| Setting | Default | Description |
|---------|---------|-------------|
| `minScoreToTrade` | 90 | Minimum composite score to enter |
| `sniperMinScore` | 70 | SNIPER mode minimum score |
| `sniperMinLiquidity` | 25000 | Minimum liquidity for SNIPER ($USD) |
| `trailingStopActivation` | 15 | Trailing stop arms at +15% peak |
| `trailingStopDistance` | 6 | Trailing stop distance from peak |
| `hardTakeProfit` | 80 | Hard exit at +80% |
| `stopLoss` | -5 | Cost-widened stop at -5% |
| `maxHoldSeconds` | 420 | Maximum hold time (7 minutes) |
| `scanIntervalMs` | 10000 | Discovery scan interval (10s) |
| `priceCheckIntervalMs` | 1000 | Exit check interval (1s) |

**See `TUNING_GUIDE.md` for the full parameter reference.**

---

## 🛡️ Safety First

### ⚠️ BEFORE YOU EVEN THINK ABOUT LIVE MODE

1. **Run PAPER MODE for at least 80-100 closed trades**
2. **Verify the Shadow Ledger shows positive edge** (`avgShadowPnlPct > 0`)
3. **Confirm the entry-confirm gate is firing** (`[ENTRY-CONFIRM] SKIP` in logs)
4. **Confirm never-green cuts are working** (`[LIFECYCLE:EXIT] NEVER_GREEN_CUT` in logs)
5. **Start with 0.01 SOL in live** (the absolute minimum)
6. **Never trade with money you can't afford to lose 100%**

### The Failsafe System

Even if the engine crashes, the **independent watchdog** (`failsafe.cjs`) will:
1. Detect the crash (dual-signal: heartbeat + HTTP health)
2. Write `.HALT` (stops new buys)
3. Kill the engine process
4. Run the liquidator (sells ALL positions to SOL)
5. Write an incident report

**The watchdog runs in a separate process. It can save your wallet even if the engine is completely frozen.**

---

## 📊 Monitoring

### Dashboard (`http://localhost:5000`)
- Real-time candidate list with scores
- Open positions with PnL tracking
- Engine stats (win rate, total PnL, drawdown)
- Shadow ledger summary
- Circuit breaker status

### Log Files
- `autopilot.log` — Main engine log
- `shadow-trades.jsonl` — Shadow trade history (one line per close)
- `shadow-stats.json` — Aggregate shadow statistics
- `incidents/` — Incident reports (only if failsafe triggers)

### Health Checks
- `http://localhost:5000/api/health` — Engine health
- `.heartbeat` file — Written every 5 seconds
- `.HALT` file — If present, engine refuses new buys

---

## 🧪 Testing

```bash
# Run the failsafe safety test (MUST PASS before live)
npm test

# Expected: 8 passing tests, 0 failures
# Tests: HALT guard, health state, heartbeat, dual-signal liveness
```

---

## 📚 Documentation Index

| Document | What You'll Learn |
|----------|-----------------|
| `SETUP_GUIDE.md` | Deploy from zero to running in 15 minutes |
| `TUNING_GUIDE.md` | Adjust every parameter for your risk tolerance |
| `SAFETY_GUIDE.md` | How the failsafe, circuit breakers, and liquidator work |
| `API_REFERENCE.md` | All REST endpoints for custom integrations |
| `TROUBLESHOOTING.md` | Fix common issues (RPC errors, DB connection, etc.) |
| `MOONSHOT_ARCHITECTURE.md` | The full architectural philosophy |
| `LINKEDIN_ARTICLE_BRIEF.md` | The 221-trade calibration story and data |

---

## 🆘 Support

- **Email:** [your support email]
- **Discord:** [your Discord community link] (private channel for buyers)
- **Response Time:** Within 24 hours for technical issues
- **Update Frequency:** Monthly parameter updates based on market conditions

---

## ⚠️ DISCLAIMER

**THIS IS EDUCATIONAL/RESEARCH SOFTWARE. IT COMES WITH PAPER MODE BY DEFAULT.**

Trading memecoins is **HIGH RISK**. You may lose **100% of your capital**. The authors are **not responsible** for any financial losses. Past performance does not guarantee future results. See `DISCLAIMER.md` for the full legal text.

---

## 📝 License

Single-user, non-transferable, personal use license. See `LICENSE.md` for full terms.

---

**Built by:** [Your Name/Brand]  
**Version:** SOL-SNIPER V.9.0.1 — Moonshot Architecture  
**Last Updated:** 2025-06-26  
**Domain:** Solana Memecoin / Meme Token Universe
