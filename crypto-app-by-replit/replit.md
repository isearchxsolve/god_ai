# Solana Hybrid Sniper Ultra

## Overview
A Solana meme token trading bot combining SNIPER, MG (Mega Growth), and HWR (High Win Rate) strategies, with an XGBoost ML prediction engine and a cyberpunk-themed React web dashboard. Features Ultra Sniper Engine v3.0+ML with blended composite scoring (65% rule + 35% ML), trailing stop loss, momentum fade detection, and dynamic position sizing.

## Architecture

### Web Dashboard (Node.js / React)
- **Backend**: Express server on port 5000 serving API + Vite frontend
- **Frontend**: React with Shadcn UI, cyberpunk neon dark theme (green/purple)
- **Database**: PostgreSQL via Drizzle ORM
- **Trading Engine**: Ultra Sniper Engine v3.0+ML — background scanner + position manager
- **API Routes**:
  - `GET /api/bot/status` - Bot status (balance, PNL, win rate, open positions, last signal)
  - `GET /api/bot/trades` - All trades with live P&L for open positions
  - `GET /api/trades/open` - Currently open positions only
  - `GET /api/bot/candidates` - DB candidates
  - `GET /api/candidates/live` - Real-time DexScreener token scanning (6s cache)
  - `GET /api/engine/stats` - Detailed engine stats (W/L, avg win/loss, best/worst trade, SOL profit, streak, ML status)
  - `POST /api/bot/trading-mode` - Toggle paper/live trading
  - `POST /api/bot/toggle` - Start/stop bot
  - `POST /api/bot/strategy-mode` - Switch strategy (SNIPER/MG/HWR/AUTO)

### ML Service (Python FastAPI)
- **Port**: 5001 (separate workflow "ML Service")
- **Model**: XGBoost v2.0, 13 features (age_seconds, liquidity_usd, volume_5m, volume_1h, volume_change_1m, price_change_5m/1h, buy_pressure_5m/1h, buy_sell_ratio, tx_velocity_per_hour, fdv, liq_to_mcap)
- **Endpoints**: `GET /health`, `POST /predict`, `POST /predict/batch`
- **Integration**: Node.js engine calls ML at scan time; batch for DexScreener pairs, individual for profiles
- **Blending**: Combined score = 65% rule-based + 35% ML prediction (pump probability × 100)
- **Fallback**: Gracefully falls back to pure rule-based if ML service unavailable
- **Health Check**: Every 30s, engine pings ML `/health` endpoint

### Ultra Sniper Engine v3.0+ML (server/routes.ts)
- **Scanner**: Every 10s, fetches tokens from DexScreener (3 search queries: pump, moon, sol new + token profiles)
- **Composite Scoring**: 7-factor scoring system (0-100 scale):
  - Buy Pressure (0-20), Volume Momentum (0-20), Trend (0-15), TX Velocity (0-15), Liquidity (0-10), Freshness (0-10), Multi-Timeframe Alignment (0-10)
- **ML Enhancement**: XGBoost pump probability blended at 35% weight; skips tokens with <$500 liquidity
- **Strategies**: SNIPER (new <3min, score≥60), MG (score≥70, momentum), HWR (score≥75, high confidence)
- **Position Manager**: Every 5s, checks current prices for open trades
  - Trailing Stop: Activates at +8%, trails 5% from peak
  - Hard Take Profit: +50%
  - Stop Loss: -12%
  - Momentum Fade Detection: Exits if buy pressure drops <35% and price falling >3%
  - Early Cut: Exits losing positions faster (>50% hold time, <-5% PNL)
  - Max Hold Time: 600s (10 min) unless in profit ≥5%
  - Max Open Positions: 8
- **Dynamic Position Sizing**: Score-based (1.5x at 85+, 1.95x at 90+), streak-adjusted (1.2x on 3+ wins, 0.6x on 3+ losses), hard cap 2.0 SOL
- **Wallet Tracking**: Paper balance starts at 10 SOL, persists to DB, restores on restart

### Python Trading Bot (`solana_hybrid_sniper_ultra/`)
- **bot.py**: Standalone async bot with same logic (for CLI use)
- **strategy.py**: Hybrid strategy with rug-pull/liquidity filters
- **ml_server.py**: FastAPI ML microservice with robust input sanitization
- **ml/train.py**: XGBoost model training (5000 samples, 13 features)
- **ml/predict.py**: ML predictions with heuristic fallback
- **executor_paper.py / executor_live.py**: Paper/live execution

## Database Schema
- `bot_status`: mode, tradingMode, isRunning, walletBalance, totalPnl, winRate, totalTrades, openPositions, lastSignal
- `trades`: tokenAddress, tokenSymbol, type (BUY/SELL), mode, tradingMode, status (OPEN/CLOSED), amount, price, currentPrice, peakPrice, pnl, peakPnl, exitPrice, exitReason, score, txHash, closedAt
- `candidates`: tokenAddress, tokenSymbol, liquidity, pumpProbability, dumpRisk, ageSeconds, qualifiedMode

## Key Files
- `shared/schema.ts` - Database schema with peak/score/exitReason tracking
- `server/routes.ts` - Ultra Sniper Engine v3.0+ML + DexScreener integration + API routes
- `server/storage.ts` - Database CRUD with trade management and peak price tracking
- `client/src/pages/dashboard.tsx` - Dashboard with 6 stat cards, best/worst trade cards, 3 tabs, ML status badge
- `client/src/components/live-feed-table.tsx` - Trade table with score, peak PNL, exit reason columns
- `client/src/hooks/use-bot-data.ts` - React Query hooks including engine stats
- `solana_hybrid_sniper_ultra/ml_server.py` - FastAPI ML microservice with NaN/Infinity sanitization
- `solana_hybrid_sniper_ultra/ml/predict.py` - XGBoost predictor with heuristic fallback

## Running
- Web dashboard: `npm run dev` (auto-started via "Start application" workflow)
- ML Service: `python3 solana_hybrid_sniper_ultra/ml_server.py` (auto-started via "ML Service" workflow)
- Python bot: `cd solana_hybrid_sniper_ultra && python3 bot.py`
- Train ML model: `python3 solana_hybrid_sniper_ultra/ml/train.py`

## Dependencies
- Node.js packages managed via package.json
- Python 3.11 with: pandas, xgboost, numpy, scikit-learn, aiohttp, fastapi, uvicorn, python-dotenv, base58, solders
