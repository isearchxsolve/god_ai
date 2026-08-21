import type { Express } from "express";
import type { Server } from "http";
import { storage } from "./storage";
import { api } from "@shared/routes";
import { JupiterService, createJupiterService } from "./jupiter";

interface DexScreenerPair {
  chainId: string;
  dexId: string;
  pairAddress: string;
  baseToken: { address: string; name: string; symbol: string };
  quoteToken: { address: string; name: string; symbol: string };
  priceUsd?: string;
  priceNative?: string;
  txns?: {
    m5?: { buys: number; sells: number };
    h1?: { buys: number; sells: number };
    h24?: { buys: number; sells: number };
  };
  volume?: { m5?: number; h1?: number; h6?: number; h24?: number };
  priceChange?: { m5?: number; h1?: number; h6?: number; h24?: number };
  liquidity?: { usd?: number };
  fdv?: number;
  marketCap?: number;
  pairCreatedAt?: number;
}

let engineSettings = {
  trailingStopActivation: 3,    // activate sooner — don't let gains evaporate (was 5)
  trailingStopDistance: 2.5,    // tighter lock — meme tokens dump fast (was 4)
  hardTakeProfit: 80,
  // Additional price-move loss tolerated BEYOND the round-trip transaction cost.
  // e.g. -6 on a SNIPER with 8% round-trip costs => stop fires at ~-14% price move,
  // total max loss ~22% of position. HWR with 4% round-trip => stop at ~-10% price move.
  stopLoss: -6,
  maxHoldSeconds: 360,
  maxOpenPositions: 12,
  startingBalance: 10,
  scanIntervalMs: 5000,
  priceCheckIntervalMs: 3000,
  
  // --- AGGRESSIVE SCORING ---
  minScoreToTrade: 52,
  mlServiceUrl: "http://localhost:5001",
  mlWeight: 0.1,
  scoreWeight: 0.99,
  dailyLossLimitPct: 20,
  maxDrawdownPct: 45,
  lossCooldownMs: 300000,        // 5 min cooldown after 3 consecutive losses (was 5s — useless)
  partialTpRatio: 0.5,
  partialTpThreshold: 15,   // take partial profit sooner (was 20)

  // --- TIGHTENED STRATEGY GATES ---
  sniperMinScore: 60,           // raised: low-score snipers lose too often (was 50)
  sniperMaxAge: 900,
  sniperMinBuyPressure: 0.58,
  sniperMinLiquidity: 700,
  sniperMaxSize: 0.25,          // hard cap: one SNIPER loss cannot wipe multiple wins (was 2.0)
  mgMinScore: 60,               // raised: marginal MG setups are net negative (was 52)
  mgMinVolMomentum: 1.5,
  mgMinPriceChange5m: 1.5,
  mgMinTxVelocity: 10,
  mgMaxSize: 0.5,               // reduced: MG on thin pools bleeds on gapped stops (was 1.8)
  hwrMinScore: 62,              // raised: HWR should have real conviction (was 57)
  hwrMinBuyPressure5m: 0.57,
  hwrMinBuyPressure1h: 0.53,
  hwrMinLiquidity: 1500,
  hwrMaxSize: 0.6,              // reduced proportionally (was 1.5)

  maxPositionSize: 1.0,         // absolute cap: no single trade > 1 SOL (was 5.0)
  minPositionSize: 0.05,
  maxTradesPerCycle: 2,         // enter slower — fewer marginal trades (was 6)
  reentryDelayMs: 60000,        // 60s minimum between any re-entry on same token (was 15s)
  slReentryDelayMs: 600000,     // 10 min block on tokens that stopped out (new)
  
  // Transaction cost simulation
  txCostsEnabled: 1,           
  txFeePercent: 0.5,           
  
  // --- RELAXED SAFETY & DISCOVERY ---
  safetyChecksEnabled: 1,      
  rugcheckMinScore: 100,       
  maxVolLiqRatioNewToken: 20,  
  maxDiscoveryAgeSeconds: 7200,
  
  dynamicHoldEnabled: 1,
  dynamicHoldMaxSeconds: 1800, 
};

let liveCandidatesCache: any[] = [];
let lastScanTime = 0;
let tradedAddresses = new Map<string, number>();
// Tracks tokens that exited via STOP_LOSS — reentry blocked for slReentryDelayMs.
// Separate from tradedAddresses so normal reentry delay and SL blackout are independent.
let stoppedOutAddresses = new Map<string, number>();
let scannerInterval: ReturnType<typeof setInterval> | null = null;
let priceCheckerInterval: ReturnType<typeof setInterval> | null = null;
let paperBalance = engineSettings.startingBalance;
let balanceInitialized = false;
let peakPrices = new Map<number, number>();
// Stores the PnL% from the previous price-check cycle for each open trade.
// Required to detect when profit is actively declining (was +X, now +Y where Y < X).
let prevPnlMap = new Map<number, number>();
// Tracks when the PnL last moved by more than 0.1% while the trade is in profit.
// Shape: { pnl: number (last "different" pnl), since: number (ms timestamp) }
// Used to detect stagnant profitable positions that should be exited.
let pnlStableMap = new Map<number, { pnl: number; since: number }>();
// Stores the computed cost-aware stop price (in token USD) for each open trade id.
// Calculated once at entry so the exit threshold is always consistent with what was
// actually paid in slippage/fees — never updated after that.
let tradeStopPrices = new Map<number, number>();
let partialTpTaken = new Set<number>();
let consecutiveWins = 0;
let consecutiveLosses = 0;
let mlServiceAvailable = false;

// 25002500 Live trading state 25002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500
let jupiterService: JupiterService | null = null;
// Maps trade.id 2192 raw SPL token units received at buy, needed for exact sell
let liveTokenBalances = new Map<number, bigint>();

let dailyPnlSol = 0;
let dailyTradeCount = 0;
let dailyStartBalance = engineSettings.startingBalance;
let lastDailyReset = new Date().toDateString();
let peakBalance = engineSettings.startingBalance;
let circuitBreakerActive = false;
let lastLossCooldownEnd = 0;
let totalTradesAllTime = 0;
let engineStartTime = Date.now();

function resetDailyStats() {
  const today = new Date().toDateString();
  if (today !== lastDailyReset) {
    dailyPnlSol = 0;
    dailyTradeCount = 0;
    dailyStartBalance = paperBalance;
    lastDailyReset = today;
    if (!circuitBreakerActive) {
      console.log(`[RISK] Daily stats reset | Start balance: ${dailyStartBalance.toFixed(3)} SOL`);
    }
  }
}

async function getEffectiveBalance(): Promise<number> {
  try {
    const openTrades = await storage.getOpenTrades();
    let openCapital = 0;
    for (const t of openTrades) {
      openCapital += parseFloat(t.amount || "0");
    }
    return paperBalance + openCapital;
  } catch {
    return paperBalance;
  }
}

let scanLock = false;

async function checkCircuitBreakers(): Promise<{ canTrade: boolean; reason: string }> {
  resetDailyStats();

  const realizedLoss = dailyPnlSol < 0 ? Math.abs(dailyPnlSol) : 0;
  const dailyLossPct = dailyStartBalance > 0 ? (realizedLoss / dailyStartBalance) * 100 : 0;
  if (dailyLossPct >= engineSettings.dailyLossLimitPct) {
    circuitBreakerActive = true;
    return { canTrade: false, reason: `DAILY_LOSS_LIMIT (${dailyLossPct.toFixed(1)}% >= ${engineSettings.dailyLossLimitPct}%)` };
  }

  const effectiveBal = await getEffectiveBalance();
  const drawdownPct = peakBalance > 0 ? ((peakBalance - effectiveBal) / peakBalance) * 100 : 0;
  if (drawdownPct >= engineSettings.maxDrawdownPct) {
    circuitBreakerActive = true;
    return { canTrade: false, reason: `MAX_DRAWDOWN (${drawdownPct.toFixed(1)}% >= ${engineSettings.maxDrawdownPct}%)` };
  }

  if (Date.now() < lastLossCooldownEnd) {
    const remaining = Math.ceil((lastLossCooldownEnd - Date.now()) / 1000);
    return { canTrade: false, reason: `LOSS_COOLDOWN (${remaining}s remaining)` };
  }

  circuitBreakerActive = false;
  return { canTrade: true, reason: "OK" };
}

async function checkMLService(): Promise<boolean> {
  try {
    const resp = await fetch(`${engineSettings.mlServiceUrl}/health`, { signal: AbortSignal.timeout(2000) });
    if (resp.ok) {
      const data = await resp.json() as any;
      if (!mlServiceAvailable) {
        console.log(`[ML] Connected to XGBoost model v${data.model_version} (${data.features?.length} features)`);
      }
      mlServiceAvailable = true;
      return true;
    }
  } catch {}
  mlServiceAvailable = false;
  return false;
}

function sanitizeNum(v: any, fallback = 0): number {
  const n = Number(v);
  return isNaN(n) || !isFinite(n) ? fallback : n;
}

async function getMLPrediction(metrics: Record<string, number>): Promise<{ pumpProb: number; dumpRisk: number; version: string } | null> {
  if (!mlServiceAvailable) return null;
  const liq = sanitizeNum(metrics.liq);
  if (liq < 500) return null;
  try {
    const vol5m = sanitizeNum(metrics.vol5m);
    const vol1h = sanitizeNum(metrics.vol1h);
    const volMomentum = vol1h > 0 ? (vol5m * 12) / vol1h : 0;
    const fdv = sanitizeNum(metrics.fdv);

    const body = {
      age_seconds: sanitizeNum(metrics.ageSeconds, 99999),
      liquidity_usd: liq,
      volume_5m: vol5m,
      volume_1h: vol1h,
      volume_change_1m: sanitizeNum(volMomentum),
      price_change_5m: sanitizeNum(metrics.priceChange5m),
      price_change_1h: sanitizeNum(metrics.priceChange1h),
      buy_pressure_5m: sanitizeNum(metrics.buyPressure5m, 0.5),
      buy_pressure_1h: sanitizeNum(metrics.buyPressure1h, 0.5),
      buy_sell_ratio: sanitizeNum(metrics.h1buys, 0) / (sanitizeNum(metrics.h1sells, 0) + 0.001),
      tx_velocity_per_hour: sanitizeNum(metrics.txVelocity5m) * 12,
      fdv: fdv,
      liq_to_mcap: fdv > 0 ? liq / fdv : 0,
    };

    const resp = await fetch(`${engineSettings.mlServiceUrl}/predict`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(3000),
    });

    if (!resp.ok) return null;
    const data = await resp.json() as any;
    if (data.error) return null;
    const pumpProb = Math.max(0, Math.min(1, Number(data.pump_probability) || 0));
    const dumpRisk = Math.max(0, Math.min(1, Number(data.dump_risk) || 1));
    return { pumpProb, dumpRisk, version: data.model_version || "unknown" };
  } catch {
    return null;
  }
}

async function getMLBatchPredictions(tokenMetrics: Record<string, number>[]): Promise<(ReturnType<typeof getMLPrediction> extends Promise<infer T> ? T : never)[]> {
  if (!mlServiceAvailable || tokenMetrics.length === 0) return tokenMetrics.map(() => null);
  try {
    const validIndices: number[] = [];
    const tokens: any[] = [];
    for (let i = 0; i < tokenMetrics.length; i++) {
      const m = tokenMetrics[i];
      const liq = sanitizeNum(m.liq);
      if (liq < 500) continue;
      validIndices.push(i);
      const vol5m = sanitizeNum(m.vol5m);
      const vol1h = sanitizeNum(m.vol1h);
      const volMomentum = vol1h > 0 ? (vol5m * 12) / vol1h : 0;
      const fdv = sanitizeNum(m.fdv);
      tokens.push({
        age_seconds: sanitizeNum(m.ageSeconds, 99999),
        liquidity_usd: liq,
        volume_5m: vol5m,
        volume_1h: vol1h,
        volume_change_1m: sanitizeNum(volMomentum),
        price_change_5m: sanitizeNum(m.priceChange5m),
        price_change_1h: sanitizeNum(m.priceChange1h),
        buy_pressure_5m: sanitizeNum(m.buyPressure5m, 0.5),
        buy_pressure_1h: sanitizeNum(m.buyPressure1h, 0.5),
        buy_sell_ratio: sanitizeNum(m.h1buys, 0) / (sanitizeNum(m.h1sells, 0) + 0.001),
        tx_velocity_per_hour: sanitizeNum(m.txVelocity5m) * 12,
        fdv: fdv,
        liq_to_mcap: fdv > 0 ? liq / fdv : 0,
      });
    }
    if (tokens.length === 0) return tokenMetrics.map(() => null);

    const resp = await fetch(`${engineSettings.mlServiceUrl}/predict/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tokens }),
      signal: AbortSignal.timeout(5000),
    });

    if (!resp.ok) return tokenMetrics.map(() => null);
    const data = await resp.json() as any;
    const preds = data.predictions || [];
    if (preds.length !== validIndices.length) {
      console.warn(`[ML] Batch response mismatch: expected ${validIndices.length}, got ${preds.length}`);
      return tokenMetrics.map(() => null);
    }
    const results: any[] = tokenMetrics.map(() => null);
    for (let j = 0; j < preds.length; j++) {
      const p = preds[j];
      if (p.error) continue;
      results[validIndices[j]] = {
        pumpProb: Math.max(0, Math.min(1, Number(p.pump_probability) || 0)),
        dumpRisk: Math.max(0, Math.min(1, Number(p.dump_risk) || 1)),
        version: p.model_version || "unknown",
      };
    }
    return results;
  } catch {
    return tokenMetrics.map(() => null);
  }
}

async function fetchTokenPrice(tokenAddress: string): Promise<{ price: number; pair: DexScreenerPair | null }> {
  try {
    const resp = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${tokenAddress}`);
    if (!resp.ok) return { price: 0, pair: null };
    const data = await resp.json() as any;
    const pairs = (data.pairs || []) as DexScreenerPair[];
    const solanaPair = pairs.find(p => p.chainId === "solana");
    if (!solanaPair) return { price: 0, pair: null };
    return { price: parseFloat(solanaPair.priceUsd || "0"), pair: solanaPair };
  } catch {
    return { price: 0, pair: null };
  }
}

function scoreToken(pair: DexScreenerPair, mlPrediction?: { pumpProb: number; dumpRisk: number; version: string } | null): {
  score: number;
  mlScore: number | null;
  combinedScore: number;
  breakdown: Record<string, number>;
  metrics: Record<string, number>;
  qualifiedMode: string | null;
  sizeSol: number;
  slippage: number;
} {
  const liq = pair.liquidity?.usd || 0;
  const createdAt = pair.pairCreatedAt || Date.now();
  const ageSeconds = Math.floor((Date.now() - createdAt) / 1000);
  const m5buys = pair.txns?.m5?.buys || 0;
  const m5sells = pair.txns?.m5?.sells || 0;
  const h1buys = pair.txns?.h1?.buys || 0;
  const h1sells = pair.txns?.h1?.sells || 0;
  const h24buys = pair.txns?.h24?.buys || 0;
  const h24sells = pair.txns?.h24?.sells || 0;
  const buyPressure5m = (m5buys + m5sells) > 0 ? m5buys / (m5buys + m5sells) : 0.5;
  const buyPressure1h = (h1buys + h1sells) > 0 ? h1buys / (h1buys + h1sells) : 0.5;
  const buyPressure24h = (h24buys + h24sells) > 0 ? h24buys / (h24buys + h24sells) : 0.5;
  const priceChange5m = pair.priceChange?.m5 || 0;
  const priceChange1h = pair.priceChange?.h1 || 0;
  const priceChange6h = pair.priceChange?.h6 || 0;
  const priceChange24h = pair.priceChange?.h24 || 0;
  const vol5m = pair.volume?.m5 || 0;
  const vol1h = pair.volume?.h1 || 0;
  const vol24h = pair.volume?.h24 || 0;
  const volMomentum = vol1h > 0 ? (vol5m * 12) / vol1h : 0;
  const txVelocity5m = m5buys + m5sells;
  const fdv = pair.fdv || 0;
  const mcap = pair.marketCap || 0;

  // Hard liquidity floor
  if (liq < 400) return { score: 0, mlScore: null, combinedScore: 0, breakdown: {}, metrics: {}, qualifiedMode: null, sizeSol: 0, slippage: 0 };

  let breakdown: Record<string, number> = {};

  // ── 1. BUY PRESSURE (5m + 1h composite, max 20, penalties allowed) ──────────
  // 5m pressure is the primary signal; 1h confirms the trend
  const rawBp5m = buyPressure5m > 0.75 ? 15
    : buyPressure5m > 0.65 ? 11
    : buyPressure5m > 0.57 ? 7
    : buyPressure5m > 0.52 ? 3
    : buyPressure5m < 0.38 ? -8   // heavy sell pressure — strong negative signal
    : buyPressure5m < 0.45 ? -4   // moderate sell pressure
    : 0;
  const rawBp1h = buyPressure1h > 0.62 ? 5
    : buyPressure1h > 0.54 ? 3
    : buyPressure1h > 0.50 ? 1
    : buyPressure1h < 0.40 ? -4   // hourly trend is bearish
    : 0;
  breakdown.buyPressure = Math.max(0, Math.min(20, rawBp5m + rawBp1h));
  const bpPenalty = Math.min(0, rawBp5m + rawBp1h); // carry negative portion separately

  // ── 2. VOLUME MOMENTUM (penalise declining volume, max 20) ──────────────────
  // volMomentum < 1 = current 5m pace is BELOW the 1h average — bearish divergence
  const rawVm = volMomentum > 3.5 ? 20
    : volMomentum > 2.5 ? 16
    : volMomentum > 1.8 ? 12
    : volMomentum > 1.3 ? 7
    : volMomentum > 1.0 ? 3
    : volMomentum > 0.6 ? -3     // volume decelerating below hourly trend
    : -7;                         // significant volume dry-up
  breakdown.volumeMomentum = Math.max(0, rawVm);
  const vmPenalty = Math.min(0, rawVm);

  // ── 3. TREND QUALITY (5m + 1h + 24h context, max 15) ───────────────────────
  let trendScore = 0;
  // 5m price action
  if (priceChange5m > 15) trendScore += 8;
  else if (priceChange5m > 8) trendScore += 6;
  else if (priceChange5m > 3) trendScore += 3;
  else if (priceChange5m < -6) trendScore -= 7;
  else if (priceChange5m < -2) trendScore -= 3;
  // 1h context
  if (priceChange1h > 25) trendScore += 7;
  else if (priceChange1h > 12) trendScore += 5;
  else if (priceChange1h > 3) trendScore += 2;
  else if (priceChange1h < -15) trendScore -= 6;
  else if (priceChange1h < -5) trendScore -= 3;
  // Late-entry penalty: token already ran hard over 24h
  if (priceChange24h > 300) trendScore -= 12;
  else if (priceChange24h > 150) trendScore -= 8;
  else if (priceChange24h > 80) trendScore -= 4;
  // Dead-cat-bounce detection: big 6h drop with small 5m pump
  if (priceChange6h < -25 && priceChange5m > 3) trendScore -= 6;
  else if (priceChange6h < -15 && priceChange5m > 0) trendScore -= 3;
  breakdown.trend = Math.max(0, Math.min(15, trendScore));
  const trendPenalty = Math.min(0, trendScore);

  // ── 4. TX VELOCITY (activity level, max 15) ─────────────────────────────────
  const rawTx = txVelocity5m > 120 ? 15
    : txVelocity5m > 60  ? 12
    : txVelocity5m > 25  ? 8
    : txVelocity5m > 10  ? 5
    : txVelocity5m > 3   ? 1
    : -3;                         // near-zero activity = illiquid / dead
  breakdown.txVelocity = Math.max(0, rawTx);
  const txPenalty = Math.min(0, rawTx);

  // ── 5. LIQUIDITY QUALITY (size + sanity checks, max 10) ─────────────────────
  let liqScore = liq > 50000 ? 10 : liq > 20000 ? 8 : liq > 5000 ? 6 : liq > 2000 ? 4 : 1;
  // High vol-to-liq ratio in very new tokens = potential wash trading / bot activity
  const volLiqRatio = liq > 0 ? vol5m / liq : 0;
  if (volLiqRatio > 8) liqScore -= 4;
  else if (volLiqRatio > 5) liqScore -= 2;
  breakdown.liquidity = Math.max(0, liqScore);
  const liqPenalty = Math.min(0, liqScore - Math.max(0, liqScore));

  // ── 6. FRESHNESS (age of pair, max 10) ──────────────────────────────────────
  const freshScore = ageSeconds < 60 ? 10
    : ageSeconds < 300  ? 8
    : ageSeconds < 900  ? 5
    : ageSeconds < 3600 ? 3
    : 0;
  breakdown.freshness = freshScore;

  // ── 7. MULTI-TIMEFRAME ALIGNMENT (max 13) ───────────────────────────────────
  const alignedUp = (priceChange5m > 0 ? 1 : 0) + (priceChange1h > 0 ? 1 : 0) + (priceChange6h > 0 ? 1 : 0);
  let multiTfScore = 0;
  if (alignedUp === 3) {
    multiTfScore = 10;
    // Bonus: 5m momentum is accelerating above the 1h baseline
    if (priceChange5m > priceChange1h / 12) multiTfScore += 3;
  } else if (alignedUp === 2 && priceChange5m > 0 && priceChange1h > 0) {
    multiTfScore = 7;
  } else if (alignedUp === 2 && priceChange5m > 0) {
    multiTfScore = 4;
  } else if (alignedUp === 0) {
    multiTfScore = 0; // all timeframes negative — no bonus
  }
  breakdown.multiTimeframe = Math.min(13, multiTfScore);

  // ── 8. SELL ACCELERATION (hidden penalty, not shown in breakdown) ────────────
  // If recent 1h buyers are a significantly lower % than 24h buyers,
  // smart money is distributing into this pump — dangerous for new entries
  let sellAccelPenalty = 0;
  const h1total = h1buys + h1sells;
  const h24total = h24buys + h24sells;
  if (h1total > 5 && h24total > 10) {
    const bpDelta = buyPressure24h - buyPressure1h; // positive = recent hour is more bearish
    if (bpDelta > 0.15) sellAccelPenalty = -8;       // strong distribution signal
    else if (bpDelta > 0.08) sellAccelPenalty = -4;  // moderate distribution
    else if (bpDelta > 0.04) sellAccelPenalty = -2;
  }

  // ── TOTAL SCORE (positives from breakdown + accumulated penalties) ───────────
  const positiveTotal = Object.values(breakdown).reduce((a, b) => a + b, 0);
  const allPenalties = bpPenalty + vmPenalty + trendPenalty + txPenalty + sellAccelPenalty;
  const totalScore = Math.max(0, positiveTotal + allPenalties);

  const metrics = {
    liq, ageSeconds, buyPressure5m, buyPressure1h, buyPressure24h, volMomentum,
    priceChange5m, priceChange1h, priceChange6h, priceChange24h,
    vol5m, vol1h, vol24h, txVelocity5m, fdv, mcap,
    m5buys, m5sells, h1buys, h1sells, h24buys, h24sells,
  };

  const mlScore = mlPrediction ? Math.round(mlPrediction.pumpProb * 100) : null;

  let combinedScore: number;
  if (mlScore !== null) {
    combinedScore = Math.round(totalScore * engineSettings.scoreWeight + mlScore * engineSettings.mlWeight);
    if (mlScore >= 90 && totalScore >= 55) combinedScore = Math.max(combinedScore, totalScore + 15);
    else if (mlScore >= 80 && totalScore >= 50) combinedScore = Math.max(combinedScore, totalScore + 10);
    else if (mlScore >= 70 && totalScore >= 45) combinedScore = Math.max(combinedScore, totalScore + 5);
    if (mlScore < 25 && totalScore >= 60) combinedScore = Math.min(combinedScore, totalScore - 12);
  } else {
    combinedScore = totalScore;
  }

  const effectiveScore = combinedScore;

  let qualifiedMode: string | null = null;
  let sizeSol = 0;
  let slippage = 2;

  if (ageSeconds < engineSettings.sniperMaxAge && effectiveScore >= engineSettings.sniperMinScore && buyPressure5m > engineSettings.sniperMinBuyPressure && liq > engineSettings.sniperMinLiquidity) {
    qualifiedMode = "SNIPER";
    sizeSol = Math.min(engineSettings.sniperMaxSize, liq / 28000);
    slippage = liq < 20000 ? 15 : 10;
  } else if (effectiveScore >= engineSettings.mgMinScore && volMomentum > engineSettings.mgMinVolMomentum && priceChange5m > engineSettings.mgMinPriceChange5m && txVelocity5m > engineSettings.mgMinTxVelocity) {
    qualifiedMode = "MG";
    sizeSol = Math.min(engineSettings.mgMaxSize, liq / 42000);
    slippage = 5;
  } else if (effectiveScore >= engineSettings.hwrMinScore && buyPressure5m > engineSettings.hwrMinBuyPressure5m && buyPressure1h > engineSettings.hwrMinBuyPressure1h && liq > engineSettings.hwrMinLiquidity) {
    qualifiedMode = "HWR";
    sizeSol = Math.min(engineSettings.hwrMaxSize, liq / 65000);
    slippage = 3;
  }

  // ── POSITION SIZING: score-based confidence scaling ─────────────────────────
  // SNIPER: never scale up. These are the highest-risk, thinnest-pool trades.
  // Scaling a SNIPER larger on a high score is how a single loss wipes multiple wins.
  // MG / HWR: modest scale-up only at very high conviction scores.
  if (qualifiedMode !== "SNIPER") {
    if (effectiveScore >= 90) sizeSol *= 1.5;
    else if (effectiveScore >= 85) sizeSol *= 1.2;
    // No multiplier below 85 — base size is already calibrated to liquidity.
  }

  // Reduce size after losses — capital preservation during drawdown
  if (consecutiveLosses >= 3) sizeSol *= 0.4;
  else if (consecutiveLosses >= 2) sizeSol *= 0.65;

  sizeSol = Math.min(engineSettings.maxPositionSize, Math.max(engineSettings.minPositionSize, Math.round(sizeSol * 1000) / 1000));

  return { score: totalScore, mlScore, combinedScore, breakdown, metrics, qualifiedMode, sizeSol, slippage };
}

function getScoreBasedTP(score: number): number {
  if (score >= 90) return 100;
  if (score >= 80) return 80;
  if (score >= 70) return 65;
  return engineSettings.hardTakeProfit;
}

// ── CHANGE 2: Transaction cost modelling ──────────────────────────────────────
function calcTransactionCosts(liqUsd: number, sizeSol: number, solPriceUsd = 150): {
  entrySlippagePct: number;
  exitSlippagePct: number;
  entryFeePct: number;
  exitFeePct: number;
  totalRoundTripPct: number;
} {
  if (!engineSettings.txCostsEnabled) {
    return { entrySlippagePct: 0, exitSlippagePct: 0, entryFeePct: 0, exitFeePct: 0, totalRoundTripPct: 0 };
  }
  const tradeValueUsd = sizeSol * solPriceUsd;
  const priceImpactPct = liqUsd > 0 ? Math.min(20, (tradeValueUsd / (liqUsd * 2)) * 100) : 10;
  const baseSlippage = liqUsd < 2000 ? 8 : liqUsd < 5000 ? 5 : liqUsd < 20000 ? 2.5 : 1.2;
  const entrySlippagePct = Math.max(baseSlippage, priceImpactPct);
  const exitSlippagePct = entrySlippagePct * 1.3;
  const fee = engineSettings.txFeePercent;
  return {
    entrySlippagePct,
    exitSlippagePct,
    entryFeePct: fee,
    exitFeePct: fee,
    totalRoundTripPct: entrySlippagePct + exitSlippagePct + fee * 2,
  };
}

// ── Cost-aware stop price ────────────────────────────────────────────────────
// Returns the token price (in USD) at which the stop should fire, given:
//   entryPrice   – USD price at time of buy
//   mode         – "SNIPER" | "MG" | "HWR"
//   liq          – pool liquidity in USD at time of buy
//   sizeSol      – position size in SOL
// The stop fires when the price move loss + projected exit costs + already-paid
// entry costs would exceed (round-trip cost + engineSettings.stopLoss extra).
// This prevents the stop from triggering on the very first price check purely
// because slippage has already eaten past the hard-coded -5% threshold.
function calcCostAwareStopPrice(entryPrice: number, mode: string | null, liq: number, sizeSol: number): number {
  if (entryPrice <= 0) return 0;

  const costs = calcTransactionCosts(liq, sizeSol);
  // Entry cost is already paid (sunk). The remaining exposure on a stop-out is:
  //   price move loss  +  exit slippage  +  exit fee
  // We want: price move loss <= additionalTolerance
  // where additionalTolerance = |engineSettings.stopLoss| (extra pain beyond costs)
  //
  // We add a small per-mode buffer on top to match the typical volatility profile:
  //   SNIPER  – brand-new thin pools, high noise → widest buffer
  //   MG      – moderate liquidity momentum trade → medium buffer
  //   HWR     – deeper pool, calmer setup → tightest buffer
  const modeBuffer = mode === "SNIPER" ? 4 : mode === "MG" ? 2 : 1;
  const exitCostPct = costs.exitSlippagePct + costs.exitFeePct;

  // priceMoveTolerance: how far price can drop before we close
  //   = engineSettings.stopLoss extra  +  mode volatility buffer
  //   We do NOT add exitCostPct here — it is debited at close time, not now.
  //   What we DO ensure is that the stop is wide enough that the exit cost
  //   alone cannot trigger it (minimum floor = exitCostPct + 1%).
  const rawTolerance = Math.abs(engineSettings.stopLoss) + modeBuffer;
  const priceMoveTolerance = Math.max(rawTolerance, exitCostPct + 1);

  const stopPrice = entryPrice * (1 - priceMoveTolerance / 100);
  return stopPrice;
}

// ── CHANGE 3: On-chain / API safety gate ──────────────────────────────────────
async function checkTokenSafety(tokenAddress: string, pair: DexScreenerPair): Promise<{ safe: boolean; reason: string }> {
  if (!engineSettings.safetyChecksEnabled) return { safe: true, reason: "checks_disabled" };

  const liq = pair.liquidity?.usd || 0;
  const fdv = pair.fdv || 0;
  const createdAt = pair.pairCreatedAt || Date.now();
  const ageSeconds = (Date.now() - createdAt) / 1000;
  const vol5m = pair.volume?.m5 || 0;

  if (liq < 500) return { safe: false, reason: "liq_below_minimum" };

  if (ageSeconds < 60 && vol5m > liq * engineSettings.maxVolLiqRatioNewToken) {
    return { safe: false, reason: `suspicious_vol_liq_ratio(${(vol5m / liq).toFixed(1)}x at ${ageSeconds.toFixed(0)}s)` };
  }

  if (fdv > 0 && liq / fdv < 0.001) {
    return { safe: false, reason: `honeypot_risk_liq_fdv_ratio(${(liq / fdv * 100).toFixed(3)}%)` };
  }

  const m5buys = pair.txns?.m5?.buys || 0;
  const m5sells = pair.txns?.m5?.sells || 0;
  if (ageSeconds < 120 && m5buys > 20 && m5sells === 0) {
    return { safe: false, reason: "zero_sells_coordinated_buy" };
  }

  try {
    const resp = await fetch(
      `https://api.rugcheck.xyz/v1/tokens/${tokenAddress}/report/summary`,
      { signal: AbortSignal.timeout(2500) }
    );
    if (resp.ok) {
      const data = await resp.json() as any;
      const score = typeof data.score === "number" ? data.score : 1000;
      const risks: Array<{ name: string; level: string }> = data.risks || [];

      const dangerRisks = risks.filter(r => r.level === "danger");
      if (dangerRisks.length > 0) {
        return { safe: false, reason: `rugcheck_danger:${dangerRisks.map(r => r.name).join(",")}` };
      }

      if (score < engineSettings.rugcheckMinScore) {
        return { safe: false, reason: `rugcheck_score_low(${score})` };
      }

      console.log(`[SAFETY] ${tokenAddress.substring(0, 8)}... rugcheck OK (score ${score}, ${risks.length} risks)`);
    }
  } catch {
    console.log(`[SAFETY] rugcheck.xyz unreachable for ${tokenAddress.substring(0, 8)}... — heuristics only`);
  }

  return { safe: true, reason: "ok" };
}

// ── CHANGE 5: Dynamic max hold ────────────────────────────────────────────────
function getScoreBasedMaxHold(score: number, currentPnlPct: number, currentBuyPressure: number): number {
  if (!engineSettings.dynamicHoldEnabled) return engineSettings.maxHoldSeconds;

  let base = score >= 85 ? 900
    : score >= 75 ? 720
    : score >= 65 ? 540
    : engineSettings.maxHoldSeconds; 

  if (currentPnlPct > 20 && currentBuyPressure > 0.60) base = Math.max(base, 1200);
  else if (currentPnlPct > 10 && currentBuyPressure > 0.55) base = Math.max(base, base * 1.4);
  else if (currentPnlPct > 5 && currentBuyPressure > 0.52) base = Math.max(base, base * 1.2);

  if (currentPnlPct < -2) base = Math.min(base, 300);
  if (currentPnlPct < -3.5) base = Math.min(base, 180);

  return Math.min(Math.round(base), engineSettings.dynamicHoldMaxSeconds);
}

// Converts a GeckoTerminal pool object into the DexScreenerPair shape that scoreToken expects.
// GeckoTerminal gives h1/h24 tx counts but not m5 — we approximate m5 from h1 data.
function geckoPoolToDexPair(pool: any): DexScreenerPair | null {
  try {
    const attr = pool.attributes;
    const baseToken = pool.relationships?.base_token?.data;
    const quoteToken = pool.relationships?.quote_token?.data;
    if (!attr || !baseToken) return null;

    // GeckoTerminal token IDs are "solana_<address>"
    const baseAddress = baseToken.id?.replace(/^solana_/, "") || "";
    const quoteAddress = quoteToken?.id?.replace(/^solana_/, "") || "";
    if (!baseAddress) return null;

    const h1buys  = parseInt(attr.transactions?.h1?.buys  || "0");
    const h1sells = parseInt(attr.transactions?.h1?.sells || "0");
    const h24buys  = parseInt(attr.transactions?.h24?.buys  || "0");
    const h24sells = parseInt(attr.transactions?.h24?.sells || "0");

    // Approximate m5 from h1 by dividing by 12 (rough but consistent)
    const m5buys  = Math.round(h1buys  / 12);
    const m5sells = Math.round(h1sells / 12);

    const vol1h  = parseFloat(attr.volume_usd?.h1  || "0");
    const vol24h = parseFloat(attr.volume_usd?.h24 || "0");
    const liqUsd = parseFloat(attr.reserve_in_usd  || "0");
    const priceUsd = parseFloat(attr.base_token_price_usd || "0");

    return {
      chainId:      "solana",
      dexId:        pool.relationships?.dex?.data?.id || "unknown",
      pairAddress:  attr.address || "",
      baseToken: {
        address: baseAddress,
        name:    attr.name?.split(" / ")[0] || baseAddress.slice(0, 8),
        symbol:  attr.name?.split(" / ")[0] || "?",
      },
      quoteToken: {
        address: quoteAddress,
        name:    attr.name?.split(" / ")[1] || "SOL",
        symbol:  attr.name?.split(" / ")[1] || "SOL",
      },
      priceUsd:    priceUsd > 0 ? priceUsd.toString() : undefined,
      priceNative: attr.base_token_price_native_currency || undefined,
      txns: {
        m5:  { buys: m5buys,  sells: m5sells  },
        h1:  { buys: h1buys,  sells: h1sells  },
        h24: { buys: h24buys, sells: h24sells },
      },
      volume: {
        m5:  vol1h / 12,
        h1:  vol1h,
        h6:  vol24h / 4,
        h24: vol24h,
      },
      priceChange: {
        m5:  parseFloat(attr.price_change_percentage?.m5  || "0"),
        h1:  parseFloat(attr.price_change_percentage?.h1  || "0"),
        h6:  parseFloat(attr.price_change_percentage?.h6  || "0"),
        h24: parseFloat(attr.price_change_percentage?.h24 || "0"),
      },
      liquidity: { usd: liqUsd },
      fdv:       parseFloat(attr.fdv_usd        || "0"),
      marketCap: parseFloat(attr.market_cap_usd || "0"),
      pairCreatedAt: attr.pool_created_at
        ? new Date(attr.pool_created_at).getTime()
        : undefined,
    };
  } catch {
    return null;
  }
}

// Batch-fetch full DexScreener pair data for a list of token addresses.
// DexScreener allows up to 30 addresses per call — returns the best Solana pair per token.
async function batchFetchDexPairs(addresses: string[]): Promise<Map<string, DexScreenerPair>> {
  const result = new Map<string, DexScreenerPair>();
  if (addresses.length === 0) return result;

  // Chunk into batches of 30 (DexScreener limit)
  for (let i = 0; i < addresses.length; i += 30) {
    const chunk = addresses.slice(i, i + 30);
    try {
      const url = `https://api.dexscreener.com/latest/dex/tokens/${chunk.join(",")}`;
      const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
      if (!resp.ok) continue;
      const data = await resp.json() as any;
      const pairs: DexScreenerPair[] = data.pairs || [];
      for (const addr of chunk) {
        // Pick the Solana pair with the highest liquidity for this token
        const best = pairs
          .filter(p => p.chainId === "solana" && p.baseToken.address === addr)
          .sort((a, b) => (b.liquidity?.usd || 0) - (a.liquidity?.usd || 0))[0];
        if (best) result.set(addr, best);
      }
    } catch {
      continue;
    }
  }
  return result;
}

async function fetchDexScreenerCandidates(): Promise<any[]> {
  const now = Date.now();
  if (now - lastScanTime < 5000 && liveCandidatesCache.length > 0) {
    return liveCandidatesCache;
  }

  try {
    const allPairs: DexScreenerPair[] = [];
    const maxAgeMs = engineSettings.maxDiscoveryAgeSeconds * 1000;

    // ── SOURCE 1 & 2: GeckoTerminal — organic signal, no API key, 30 req/min ──
    // trending_pools: ranked by on-chain activity + web visits (not paid promotion)
    // new_pools: most recently created pools — catches moves at birth
    const geckoFetches = [
      fetch("https://api.geckoterminal.com/api/v2/networks/solana/trending_pools?page=1", {
        headers: { "Accept": "application/json;version=20230302" },
      }).then(r => r.ok ? r.json() : { data: [] }).catch(() => ({ data: [] })),
      fetch("https://api.geckoterminal.com/api/v2/networks/solana/new_pools?page=1", {
        headers: { "Accept": "application/json;version=20230302" },
      }).then(r => r.ok ? r.json() : { data: [] }).catch(() => ({ data: [] })),
    ];

    // ── SOURCE 3, 4, 5: DexScreener search — free, 300 req/min, no key ────────
    // These are keyword searches, not paid promo. Keep them as they surface
    // Raydium/Pump/Orca pairs not yet picked up by GeckoTerminal trending.
    const dexFetches = [
      fetch("https://api.dexscreener.com/latest/dex/search?q=raydium+sol")
        .then(r => r.ok ? r.json() : { pairs: [] }).catch(() => ({ pairs: [] })),
      fetch("https://api.dexscreener.com/latest/dex/search?q=pumpfun+solana")
        .then(r => r.ok ? r.json() : { pairs: [] }).catch(() => ({ pairs: [] })),
      fetch("https://api.dexscreener.com/latest/dex/search?q=orca+solana+new")
        .then(r => r.ok ? r.json() : { pairs: [] }).catch(() => ({ pairs: [] })),
    ];

    const [gtTrending, gtNew, raydiumResult, pumpfunResult, orcaResult] =
      await Promise.all([...geckoFetches, ...dexFetches]);

    // Convert GeckoTerminal pools → DexScreenerPair shape
    // GeckoTerminal data is scored directly (m5 approximated from h1/12).
    // For the top candidates we'll enrich with a DexScreener batch call below.
    const geckoAddresses: string[] = [];
    for (const pool of [...(gtTrending.data || []), ...(gtNew.data || [])]) {
      const pair = geckoPoolToDexPair(pool);
      if (!pair) continue;
      const pairAge = pair.pairCreatedAt ? now - pair.pairCreatedAt : Infinity;
      if (pairAge > maxAgeMs) continue;
      if ((pair.liquidity?.usd || 0) < 400) continue;
      allPairs.push(pair);
      geckoAddresses.push(pair.baseToken.address);
    }
    console.log(`[SCAN] GeckoTerminal: ${geckoAddresses.length} addresses from trending+new pools`);

    // Enrich GeckoTerminal addresses with full DexScreener m5 data in one batch call.
    // This replaces the old sequential fetchTokenPrice loop — O(1) calls not O(n).
    if (geckoAddresses.length > 0) {
      const enriched = await batchFetchDexPairs(geckoAddresses);
      for (let i = 0; i < allPairs.length; i++) {
        const addr = allPairs[i].baseToken.address;
        const dexPair = enriched.get(addr);
        if (dexPair) allPairs[i] = dexPair; // replace approximated with exact data
      }
      console.log(`[SCAN] Enriched ${enriched.size}/${geckoAddresses.length} GeckoTerminal tokens with DexScreener m5 data`);
    }

    // DexScreener search results (already have full m5 data, no enrichment needed)
    for (const result of [raydiumResult, pumpfunResult, orcaResult]) {
      if (result.pairs) {
        const fresh = (result.pairs as DexScreenerPair[]).filter(p => {
          if (p.chainId !== "solana") return false;
          if ((p.liquidity?.usd || 0) < 400) return false;
          const pairAge = p.pairCreatedAt ? now - p.pairCreatedAt : Infinity;
          return pairAge <= maxAgeMs;
        }).slice(0, 20);
        allPairs.push(...fresh);
      }
    }

    const results: any[] = [];
    const seenAddresses = new Set<string>();

    const dedupedPairs: DexScreenerPair[] = [];
    for (const sp of allPairs) {
      if (seenAddresses.has(sp.baseToken.address)) continue;
      seenAddresses.add(sp.baseToken.address);
      dedupedPairs.push(sp);
    }

    const pairMetrics = dedupedPairs.map(sp => {
      const scoring = scoreToken(sp);
      return scoring.metrics;
    });
    const mlPredictions = await getMLBatchPredictions(pairMetrics);

    for (let idx = 0; idx < dedupedPairs.length; idx++) {
      const sp = dedupedPairs[idx];
      const mlPred = mlPredictions[idx] || null;
      const scoring = scoreToken(sp, mlPred);
      const liq = sp.liquidity?.usd || 0;
      const createdAt = sp.pairCreatedAt || Date.now();
      const ageSeconds = Math.floor((Date.now() - createdAt) / 1000);

      results.push({
        tokenAddress: sp.baseToken.address,
        tokenSymbol: sp.baseToken.symbol,
        tokenName: sp.baseToken.name,
        dex: sp.dexId,
        price: sp.priceUsd || "0",
        liquidity: liq.toFixed(0),
        score: scoring.combinedScore,
        mlScore: scoring.mlScore,
        ruleScore: scoring.score,
        pumpProbability: (scoring.combinedScore / 100).toFixed(3),
        dumpRisk: (1 - scoring.combinedScore / 100).toFixed(3),
        ageSeconds,
        qualifiedMode: scoring.qualifiedMode,
        volume5m: (sp.volume?.m5 || 0).toFixed(0),
        volume1h: (sp.volume?.h1 || 0).toFixed(0),
        volume24h: (sp.volume?.h24 || 0).toFixed(0),
        priceChange5m: sp.priceChange?.m5 || 0,
        priceChange1h: sp.priceChange?.h1 || 0,
        buys5m: sp.txns?.m5?.buys || 0,
        sells5m: sp.txns?.m5?.sells || 0,
        buys1h: sp.txns?.h1?.buys || 0,
        sells1h: sp.txns?.h1?.sells || 0,
        buyPressure5m: scoring.metrics.buyPressure5m?.toFixed(3) || "0.500",
        fdv: sp.fdv || 0,
        marketCap: sp.marketCap || 0,
        mlActive: mlPred !== null,
        source: "dexscreener_live",
        timestamp: new Date().toISOString(),
      });
    }

    results.sort((a, b) => (b.score || 0) - (a.score || 0));

    console.log(`[SCAN] Found ${results.length} candidates within ${engineSettings.maxDiscoveryAgeSeconds}s discovery window`);

    if (results.length > 0) {
      liveCandidatesCache = results;
      lastScanTime = now;
    }
    return liveCandidatesCache;
  } catch (e) {
    console.error("DexScreener fetch error:", e);
    return liveCandidatesCache;
  }
}

async function initBalanceFromDB() {
  if (balanceInitialized) return;
  const status = await storage.getBotStatus();
  const storedBalance = parseFloat(status.walletBalance || "0");
  if (storedBalance > 0) {
    paperBalance = storedBalance;
    dailyStartBalance = paperBalance;
    peakBalance = paperBalance;
    circuitBreakerActive = false;
    console.log(`[ENGINE] Restored wallet balance from DB: ${paperBalance.toFixed(3)} SOL`);
  }
  const openTrades = await storage.getOpenTrades();
  for (const t of openTrades) {
    tradedAddresses.set(t.tokenAddress, new Date(t.timestamp).getTime());
    if (t.peakPrice) {
      peakPrices.set(t.id, parseFloat(t.peakPrice));
    }
    // Reconstruct a cost-aware stop price from the stored entry price and mode.
    // We don't have the original liquidity at entry time, so use a conservative
    // per-mode estimate. It's better to use a slightly wrong stop than none at all.
    if (!tradeStopPrices.has(t.id)) {
      const ep = parseFloat(t.price || "0");
      if (ep > 0) {
        const fallbackLiq = t.mode === "SNIPER" ? 5000 : t.mode === "MG" ? 15000 : 30000;
        const fallbackSize = parseFloat(t.amount || "0.1");
        tradeStopPrices.set(t.id, calcCostAwareStopPrice(ep, t.mode, fallbackLiq, fallbackSize));
      }
    }
  }
  balanceInitialized = true;
}

// Returns a dynamically raised minimum score based on session health.
// When the bot is losing, it must become MORE selective, not equally selective.
//
//  Tier 0 (healthy):   use engineSettings.minScoreToTrade as-is
//  Tier 1 (any loss):  +5 — small daily loss means the market isn't cooperating; be choosier
//  Tier 2 (>5% down):  +10 — significant loss; only take high-conviction setups
//  Tier 3 (>10% down): +15 — deep loss; near-emergency, only the best signals
//
// Additionally: each consecutive loss adds +3 on top of the tier bonus (capped at +15),
// because a losing streak means current market conditions are actively hostile to entries.
function getEffectiveMinScore(): number {
  const base = engineSettings.minScoreToTrade;

  const dailyLossPct = dailyStartBalance > 0
    ? Math.max(0, (-dailyPnlSol / dailyStartBalance) * 100)
    : 0;

  const tierBonus = dailyLossPct >= 10 ? 15
    : dailyLossPct >= 5  ? 10
    : dailyLossPct >  0  ? 5
    : 0;

  const streakBonus = Math.min(15, consecutiveLosses * 3);

  const effective = base + tierBonus + streakBonus;
  if (effective > base) {
    console.log(`[SCORE_GATE] Raised min score: ${base} → ${effective} (dailyLoss=${dailyLossPct.toFixed(1)}%, streak=${consecutiveLosses})`);
  }
  return effective;
}

async function runScanCycle() {
  if (scanLock) return;
  scanLock = true;
  try {
    await initBalanceFromDB();

    const cleanupThreshold = engineSettings.reentryDelayMs * 3;
    const now = Date.now();
    for (const [addr, ts] of tradedAddresses) {
      if (now - ts > cleanupThreshold) tradedAddresses.delete(addr);
    }
    for (const [addr, ts] of stoppedOutAddresses) {
      if (now - ts > engineSettings.slReentryDelayMs) stoppedOutAddresses.delete(addr);
    }

    const status = await storage.getBotStatus();
    if (!status.isRunning) { scanLock = false; return; }

    const riskCheck = await checkCircuitBreakers();
    if (!riskCheck.canTrade) {
      scanLock = false;
      return;
    }

    const openTrades = await storage.getOpenTrades();
    if (openTrades.length >= engineSettings.maxOpenPositions) { scanLock = false; return; }

    // ── OPEN-POSITION HEALTH CHECK ────────────────────────────────────────────
    // If any open trade is more than 5% underwater, the market is clearly moving
    // against us right now. Skip this scan cycle entirely — do not add new exposure.
    // This is separate from the circuit breaker (which only fires at 20% daily loss);
    // this fires on current open-position state, not just realised PnL.
    if (openTrades.length > 0) {
      const worstOpenPnl = Math.min(
        ...openTrades.map((t: any) => parseFloat(t.pnl || "0"))
      );
      if (worstOpenPnl <= -5) {
        console.log(`[SCAN] Skipping new entries — worst open position at ${worstOpenPnl.toFixed(1)}%. Waiting for recovery.`);
        scanLock = false;
        return;
      }
    }

    const candidates = await fetchDexScreenerCandidates();

    const openAddresses = new Set(openTrades.map((t: any) => t.tokenAddress));
    const boughtThisCycle = new Set<string>();
    let currentOpenCount = openTrades.length;
    let tradesThisCycle = 0;

    for (const candidate of candidates) {
      const addr = candidate.tokenAddress;
      if (boughtThisCycle.has(addr)) continue;
      const lastTraded = tradedAddresses.get(addr);
      if (lastTraded && (Date.now() - lastTraded) < engineSettings.reentryDelayMs) continue;
      // Tokens that stopped out are blocked for slReentryDelayMs (default 10 min).
      // This prevents re-entering a clearly broken token immediately after a loss.
      const lastStopped = stoppedOutAddresses.get(addr);
      if (lastStopped && (Date.now() - lastStopped) < engineSettings.slReentryDelayMs) continue;
      if (openAddresses.has(addr)) continue;
      if (currentOpenCount >= engineSettings.maxOpenPositions) break;
      if (tradesThisCycle >= engineSettings.maxTradesPerCycle) break;

      const { price, pair } = await fetchTokenPrice(candidate.tokenAddress);
      if (!pair || price <= 0) continue;

      const mlPred = await getMLPrediction(scoreToken(pair).metrics);
      const scoring = scoreToken(pair, mlPred);
      const effectiveMinScore = getEffectiveMinScore();
      if (!scoring.qualifiedMode || scoring.combinedScore < effectiveMinScore || scoring.sizeSol < engineSettings.minPositionSize) continue;

      if (status.mode !== "AUTO" && scoring.qualifiedMode !== status.mode) continue;

      const safety = await checkTokenSafety(candidate.tokenAddress, pair);
      if (!safety.safe) {
        console.log(`[SAFETY] BLOCKED $${candidate.tokenSymbol} — ${safety.reason}`);
        tradedAddresses.set(addr, Date.now()); 
        continue;
      }

      const liq = pair.liquidity?.usd || 0;
      const txCosts = calcTransactionCosts(liq, scoring.sizeSol);
      const entryTotalCostSol = scoring.sizeSol * (1 + (txCosts.entrySlippagePct + txCosts.entryFeePct) / 100);

      const isLiveBuy = status.tradingMode === "live" && jupiterService !== null;

      let actualSizeSol = scoring.sizeSol;
      let buyTxHash: string;

      if (isLiveBuy) {
        const walletBal = await jupiterService!.getWalletBalance();
        if (walletBal < scoring.sizeSol + 0.02) {
          console.log(`[LIVE] Insufficient wallet balance (${walletBal.toFixed(4)} SOL) for $${candidate.tokenSymbol} — skipping`);
          continue;
        }

        const slippageBps = scoring.slippage * 100; 
        const buyResult = await jupiterService!.buyToken(
          candidate.tokenAddress,
          scoring.sizeSol,
          slippageBps
        );

        if (!buyResult.success) {
          console.log(`[LIVE] BUY FAILED $${candidate.tokenSymbol}: ${buyResult.error}`);
          tradedAddresses.set(addr, Date.now());
          continue;
        }

        actualSizeSol = buyResult.actualSolSpent;
        buyTxHash     = buyResult.txSignature!;

        tradedAddresses.set(addr, Date.now());
        openAddresses.add(addr);
        boughtThisCycle.add(addr);
        currentOpenCount++;
        tradesThisCycle++;
        dailyTradeCount++;
        totalTradesAllTime++;

        const trade = await storage.addTrade({
          tokenAddress: candidate.tokenAddress,
          tokenSymbol:  candidate.tokenSymbol,
          type:         "BUY",
          mode:         scoring.qualifiedMode,
          tradingMode:  "live",
          status:       "OPEN",
          amount:       actualSizeSol.toFixed(4),
          price:        price.toString(),
          currentPrice: price.toString(),
          peakPrice:    price.toString(),
          pnl:          "0",
          peakPnl:      "0",
          score:        scoring.combinedScore.toString(),
          txHash:       buyTxHash,
        });

        liveTokenBalances.set(trade.id, buyResult.tokenAmountRaw);
        peakPrices.set(trade.id, price);
        tradeStopPrices.set(trade.id, calcCostAwareStopPrice(price, scoring.qualifiedMode, liq, actualSizeSol));

        const mlTag = scoring.mlScore !== null ? ` | ML: ${scoring.mlScore}%` : " | ML: offline";
        console.log(`[LIVE] BUY $${candidate.tokenSymbol} @ $${price.toFixed(8)} | ${scoring.qualifiedMode} | Score: ${scoring.combinedScore}/100 | SOL: ${actualSizeSol.toFixed(4)} | tx: ${buyTxHash.slice(0, 20)}...${mlTag}`);
        console.log(`  Breakdown: BP=${scoring.breakdown.buyPressure} VM=${scoring.breakdown.volumeMomentum} TR=${scoring.breakdown.trend} TX=${scoring.breakdown.txVelocity} LQ=${scoring.breakdown.liquidity} FR=${scoring.breakdown.freshness} MTF=${scoring.breakdown.multiTimeframe}`);

      } else {
        if (paperBalance < entryTotalCostSol) continue;

        paperBalance -= entryTotalCostSol;
        buyTxHash = `paper_${Date.now().toString(36)}_${candidate.tokenAddress.substring(0, 6)}`;

        tradedAddresses.set(addr, Date.now());
        openAddresses.add(addr);
        boughtThisCycle.add(addr);
        currentOpenCount++;
        tradesThisCycle++;
        dailyTradeCount++;
        totalTradesAllTime++;

        const trade = await storage.addTrade({
          tokenAddress: candidate.tokenAddress,
          tokenSymbol:  candidate.tokenSymbol,
          type:         "BUY",
          mode:         scoring.qualifiedMode,
          tradingMode:  "paper",
          status:       "OPEN",
          amount:       scoring.sizeSol.toFixed(3),
          price:        price.toString(),
          currentPrice: price.toString(),
          peakPrice:    price.toString(),
          pnl:          "0",
          peakPnl:      "0",
          score:        scoring.combinedScore.toString(),
          txHash:       buyTxHash,
        });

        peakPrices.set(trade.id, price);
        tradeStopPrices.set(trade.id, calcCostAwareStopPrice(price, scoring.qualifiedMode, liq, scoring.sizeSol));

        const mlTag = scoring.mlScore !== null ? ` | ML: ${scoring.mlScore}%` : " | ML: offline";
        const costTag = engineSettings.txCostsEnabled ? ` | TxCost: ${txCosts.totalRoundTripPct.toFixed(1)}% round-trip` : "";
        console.log(`[PAPER] BUY $${candidate.tokenSymbol} @ $${price.toFixed(8)} | ${scoring.qualifiedMode} | Score: ${scoring.combinedScore}/100 (Rule:${scoring.score} + ML:${scoring.mlScore ?? 'N/A'}) | Size: ${scoring.sizeSol} SOL | Bal: ${paperBalance.toFixed(3)}${costTag}`);
        console.log(`  Breakdown: BP=${scoring.breakdown.buyPressure} VM=${scoring.breakdown.volumeMomentum} TR=${scoring.breakdown.trend} TX=${scoring.breakdown.txVelocity} LQ=${scoring.breakdown.liquidity} FR=${scoring.breakdown.freshness} MTF=${scoring.breakdown.multiTimeframe}${mlTag}`);
      }

      const allTrades = await storage.getTrades();
      const closedTrades = allTrades.filter((t: any) => t.status === "CLOSED");
      const wins = closedTrades.filter((t: any) => parseFloat(t.pnl || "0") > 0).length;
      const wr = closedTrades.length > 0 ? ((wins / closedTrades.length) * 100).toFixed(1) : "0";

      const displayBalance = isLiveBuy && jupiterService
        ? (await jupiterService.getWalletBalance().catch(() => paperBalance)).toFixed(4)
        : paperBalance.toFixed(3);

      const mlLabel = scoring.mlScore !== null ? ` [ML:${scoring.mlScore}%]` : "";
      await storage.updateBotStats({
        walletBalance: displayBalance,
        totalTrades: allTrades.length,
        openPositions: currentOpenCount,
        winRate: wr,
        lastSignal: `BUY $${candidate.tokenSymbol} via ${scoring.qualifiedMode} (Score: ${scoring.combinedScore})${mlLabel}`,
      });
    }
  } catch (e) {
    console.error("[SCANNER] Error:", e);
  } finally {
    scanLock = false;
  }
}

async function checkOpenPositions() {
  try {
    const openTrades = await storage.getOpenTrades();
    if (openTrades.length === 0) return;

    for (const trade of openTrades) {
      try {
      const { price: currentPrice, pair } = await fetchTokenPrice(trade.tokenAddress);
      if (currentPrice <= 0) continue;

      const entryPrice = parseFloat(trade.price);
      if (entryPrice <= 0) continue;

      let pnlPct = ((currentPrice - entryPrice) / entryPrice) * 100;
      const MAX_REALISTIC_PNL = 500;
      if (pnlPct > MAX_REALISTIC_PNL) {
        console.log(`[TRADE] SUSPICIOUS PNL $${trade.tokenSymbol} | +${pnlPct.toFixed(1)}% exceeds ${MAX_REALISTIC_PNL}% cap — likely bad price data, capping`);
        pnlPct = MAX_REALISTIC_PNL;
      }
      const holdTime = (Date.now() - new Date(trade.timestamp).getTime()) / 1000;
      const tradeScore = parseInt(trade.score || "0");
      const dynamicTP = getScoreBasedTP(tradeScore);

      const liveBP = (() => {
        if (!pair) return 0.5;
        const b = pair.txns?.m5?.buys || 0;
        const s = pair.txns?.m5?.sells || 0;
        return (b + s) > 0 ? b / (b + s) : 0.5;
      })();
      const dynamicMaxHold = getScoreBasedMaxHold(tradeScore, pnlPct, liveBP);

      let peak = peakPrices.get(trade.id) || entryPrice;
      if (currentPrice > peak) {
        peak = currentPrice;
        peakPrices.set(trade.id, peak);
      }
      const peakPnl = ((peak - entryPrice) / entryPrice) * 100;
      const drawdownFromPeak = peak > 0 ? ((peak - currentPrice) / peak) * 100 : 0;

      await storage.updateTradeCurrentPrice(trade.id, currentPrice.toString(), pnlPct.toFixed(2));
      await storage.updateTradePeakPrice(trade.id, peak.toString(), peakPnl.toFixed(2));

      if (!partialTpTaken.has(trade.id) && pnlPct >= engineSettings.partialTpThreshold && pnlPct < dynamicTP) {
        const sizeSol = parseFloat(trade.amount);
        const partialSize = sizeSol * engineSettings.partialTpRatio;
        const partialReturn = partialSize * (1 + pnlPct / 100);
        paperBalance += partialReturn;
        partialTpTaken.add(trade.id);
        dailyPnlSol += partialReturn - partialSize;

        const newAmount = (sizeSol - partialSize).toFixed(3);
        await storage.updateTradeAmount(trade.id, newAmount);

        console.log(`[TRADE] PARTIAL TP $${trade.tokenSymbol} | Sold ${engineSettings.partialTpRatio * 100}% @ +${pnlPct.toFixed(1)}% | Secured: ${partialReturn.toFixed(3)} SOL | Remaining: ${newAmount} SOL`);
      }

      // ── PROFIT TREND TRACKING ────────────────────────────────────────────────
      // Read last cycle's PnL, then update the map with this cycle's value.
      // prevPnl is used below to detect declining profit.
      const prevPnl = prevPnlMap.get(trade.id) ?? null;
      prevPnlMap.set(trade.id, pnlPct);

      // Track how long the PnL has been stable (changed by less than 0.1%).
      // Only meaningful when the trade is in profit (pnlPct >= 1).
      if (pnlPct >= 1) {
        const stable = pnlStableMap.get(trade.id);
        if (!stable) {
          pnlStableMap.set(trade.id, { pnl: pnlPct, since: Date.now() });
        } else if (Math.abs(pnlPct - stable.pnl) >= 0.1) {
          // PnL moved meaningfully — reset the clock with the new value.
          pnlStableMap.set(trade.id, { pnl: pnlPct, since: Date.now() });
        }
        // else: PnL hasn't moved — leave since unchanged so the timer keeps ticking.
      } else {
        pnlStableMap.delete(trade.id);
      }

      let shouldClose = false;
      let reason = "";

      // ── COST-AWARE STOP PRICE ────────────────────────────────────────────────
      // Look up the pre-computed stop price set at entry time.  This already
      // embeds entry slippage, exit slippage estimate, fees, and the per-mode
      // volatility buffer — so it will never trigger purely because transaction
      // costs have eaten past a naïve -5% PnL threshold.
      const costAwareStopPrice = tradeStopPrices.get(trade.id) ?? 0;
      // Express it also as a PnL% for time-based cut thresholds below.
      const stopLossPct = costAwareStopPrice > 0 && entryPrice > 0
        ? ((costAwareStopPrice - entryPrice) / entryPrice) * 100   // negative number
        : engineSettings.stopLoss;
      // Half-stop: used for early/fast cuts — halfway between entry and full stop.
      const halfStopPct = stopLossPct / 2;

      // Trailing floor: how much of peak gain to lock in before stopping out
      const trailingFloor = peakPnl > 30 ? peakPnl * 0.50
        : peakPnl > 15 ? peakPnl * 0.38
        : peakPnl > 8  ? peakPnl * 0.25
        : 0;

      if (pnlPct >= 20) {
        // ── TAKE_PROFIT_20: lock gains the moment PnL hits 20% ───────────────
        shouldClose = true;
        reason = `TAKE_PROFIT_20 (+${pnlPct.toFixed(2)}%)`;
      } else if (pnlPct >= dynamicTP) {
        // ── HARD_TP: score-based ceiling (65–100%) ────────────────────────────
        shouldClose = true;
        reason = "HARD_TP";
      } else if (
        prevPnl !== null &&
        prevPnl > 0 &&          // was in profit last cycle
        pnlPct > 0 &&           // still in profit (not crossed zero)
        pnlPct < prevPnl &&     // profit is lower than last cycle
        prevPnl >= 1.0 &&       // ignore micro-gains — 1% minimum meaningful profit
        (prevPnl - pnlPct) >= 1.0 && // require at least 1% actual drop, not just noise
        holdTime > 30           // ignore first 30s after entry (slippage settling)
      ) {
        // ── PROFIT_DECLINE: profit was real and is now visibly shrinking ──────
        // Exit immediately — a declining profit on a meme coin almost never recovers.
        shouldClose = true;
        reason = `PROFIT_DECLINE (was +${prevPnl.toFixed(2)}%, now +${pnlPct.toFixed(2)}%, drop=${( prevPnl - pnlPct).toFixed(2)}%)`;
      } else if ((() => {
        const stable = pnlStableMap.get(trade.id);
        return pnlPct >= 1 && stable !== undefined && (Date.now() - stable.since) >= 60_000;
      })()) {
        // ── PNL_STAGNANT: profit >= 1% but unchanged for 60 seconds ──────────
        shouldClose = true;
        const stableSec = Math.round((Date.now() - (pnlStableMap.get(trade.id)!.since)) / 1000);
        reason = `PNL_STAGNANT (+${pnlPct.toFixed(2)}% unchanged for ${stableSec}s)`;
      } else if (peakPnl >= engineSettings.trailingStopActivation && drawdownFromPeak >= engineSettings.trailingStopDistance) {
        if (pnlPct < trailingFloor) {
          pnlPct = trailingFloor;
          console.log(`[TRADE] TRAILING FLOOR $${trade.tokenSymbol} | Peak +${peakPnl.toFixed(1)}% → locked exit at +${trailingFloor.toFixed(1)}%`);
        }
        shouldClose = true;
        reason = `TRAIL_STOP (peak +${peakPnl.toFixed(1)}%, fell ${drawdownFromPeak.toFixed(1)}%)`;
      } else if (costAwareStopPrice > 0 && currentPrice <= costAwareStopPrice) {
        // Primary stop: price has fallen to the cost-aware threshold
        shouldClose = true;
        reason = `STOP_LOSS (stop $${costAwareStopPrice.toFixed(8)}, price $${currentPrice.toFixed(8)}, pnl ${pnlPct.toFixed(1)}%)`;
      } else if (holdTime > dynamicMaxHold && pnlPct < 5) {
        shouldClose = true;
        reason = `MAX_HOLD(${Math.round(dynamicMaxHold)}s)`;
      } else if (holdTime > dynamicMaxHold / 2 && pnlPct < halfStopPct) {
        // EARLY_CUT: at half the max hold time and already more than halfway to stop
        shouldClose = true;
        reason = `EARLY_CUT (pnl ${pnlPct.toFixed(1)}% < halfStop ${halfStopPct.toFixed(1)}%)`;
      } else if (holdTime > 120 && pnlPct < stopLossPct * 0.7) {
        // FAST_CUT: after 2 minutes, if 70% of the way to stop, exit rather than wait
        shouldClose = true;
        reason = `FAST_CUT (pnl ${pnlPct.toFixed(1)}% past 70% of stop ${(stopLossPct * 0.7).toFixed(1)}%)`;
      }

      // ── MOMENTUM FADE: buy pressure collapsing while in trade ───────────────
      if (!shouldClose && pair && holdTime > 45) {
        const m5b = pair.txns?.m5?.buys || 0;
        const m5s = pair.txns?.m5?.sells || 0;
        const currentBP = (m5b + m5s) > 0 ? m5b / (m5b + m5s) : 0.5;
        const priceChange5m = pair.priceChange?.m5 || 0;

        if (currentBP < 0.38 && priceChange5m < -2) {
          shouldClose = true;
          reason = `MOMENTUM_FADE (BP=${currentBP.toFixed(2)}, Δ5m=${priceChange5m.toFixed(1)}%)`;
        } else if (pnlPct > 5 && currentBP < 0.43 && priceChange5m < -4) {
          shouldClose = true;
          reason = `PROFIT_PROTECT_FADE (BP=${currentBP.toFixed(2)}, Δ5m=${priceChange5m.toFixed(1)}%, PNL=+${pnlPct.toFixed(1)}%)`;
        }
      }

      // ── VOLUME COLLAPSE: token going dead while we're holding ───────────────
      if (!shouldClose && pair && holdTime > 180 && pnlPct > 1) {
        const currentVol5m = pair.volume?.m5 || 0;
        const vol1hNow = pair.volume?.h1 || 0;
        const expectedVol5m = vol1hNow / 12;
        if (expectedVol5m > 100 && currentVol5m < expectedVol5m * 0.15) {
          shouldClose = true;
          reason = `VOL_COLLAPSE (5m vol ${currentVol5m.toFixed(0)} is <15% of expected ${expectedVol5m.toFixed(0)})`;
        }
      }

      if (shouldClose) {
        const sizeSol = parseFloat(trade.amount);
        const isLiveSell = trade.tradingMode === "live" && jupiterService !== null;
        let finalPnlPct: number;
        let sellTxSig: string | null = null;

        if (isLiveSell) {
          const tokenAmountRaw = liveTokenBalances.get(trade.id) ?? BigInt(0);
          const exitLiqUsd = pair?.liquidity?.usd ?? 1000;
          // Derive exit slippage tolerance from the same cost model used to set the
          // stop price — keeps live Jupiter tolerance consistent with the stop calibration.
          // We add a 50% buffer on top of the modelled exit slippage to give Jupiter
          // room to fill without failing, while still being tighter than flat tiers.
          const exitCostsModel = calcTransactionCosts(exitLiqUsd, sizeSol);
          const exitSlippageBps = Math.min(
            3000, // hard cap: never allow >30% slippage on exit
            Math.max(
              150,  // floor: always allow at least 1.5% for dust/rounding
              Math.round(exitCostsModel.exitSlippagePct * 1.5 * 100)
            )
          );

          const sellResult = await jupiterService!.sellToken(
            trade.tokenAddress,
            tokenAmountRaw,
            exitSlippageBps
          );

          if (!sellResult.success) {
            console.warn(
              `[LIVE] SELL FAILED $${trade.tokenSymbol}: ${sellResult.error} — will retry next cycle`
            );
            continue;
          }

          sellTxSig   = sellResult.txSignature;
          finalPnlPct = sizeSol > 0
            ? ((sellResult.solReceived - sizeSol) / sizeSol) * 100
            : 0;

          dailyPnlSol += sellResult.solReceived - sizeSol;
          liveTokenBalances.delete(trade.id);

          console.log(
            `[LIVE] ${finalPnlPct >= 0 ? "WIN" : "LOSS"} SELL $${trade.tokenSymbol} | ` +
            `PNL: ${finalPnlPct >= 0 ? "+" : ""}${finalPnlPct.toFixed(2)}% | ` +
            `SOL in: ${sizeSol.toFixed(4)} → out: ${sellResult.solReceived.toFixed(4)} | ` +
            `${reason} | tx: ${sellTxSig?.slice(0, 20)}...`
          );

        } else {
          let exitPnlPct = pnlPct;
          // Do NOT clamp to stopLossPct. The stop price is a trigger, not a guarantee.
          // If price gapped through the stop (polling latency), the model should record
          // the actual loss so paper results remain honest about what live would get.
          // The only guard here is the existing hard floor: don't go below full position loss.
          exitPnlPct = Math.max(pnlPct, -99);

          const exitLiq = pair?.liquidity?.usd || 1000;
          const exitTxCosts = calcTransactionCosts(exitLiq, sizeSol);
          const exitCostPct = exitTxCosts.exitSlippagePct + exitTxCosts.exitFeePct;
          exitPnlPct -= exitCostPct;

          const returnSol = sizeSol * (1 + exitPnlPct / 100);
          paperBalance += returnSol;
          dailyPnlSol  += returnSol - sizeSol;
          finalPnlPct   = exitPnlPct;

          if (paperBalance > peakBalance) peakBalance = paperBalance;

          const costInfo = engineSettings.txCostsEnabled
            ? ` | ExitCost: -${exitCostPct.toFixed(1)}%`
            : "";
          console.log(
            `[PAPER] ${finalPnlPct >= 0 ? "WIN" : "LOSS"} SELL $${trade.tokenSymbol} ` +
            `@ $${currentPrice.toFixed(8)} | PNL: ${finalPnlPct >= 0 ? "+" : ""}${finalPnlPct.toFixed(2)}% | ` +
            `Peak: +${peakPnl.toFixed(1)}% | ${reason}${costInfo} | Bal: ${paperBalance.toFixed(3)} SOL`
          );
        }

        const isWin = finalPnlPct > 0;
        if (isWin) {
          consecutiveWins++;
          consecutiveLosses = 0;
        } else {
          consecutiveLosses++;
          consecutiveWins = 0;
          if (consecutiveLosses >= 3) {
            lastLossCooldownEnd = Date.now() + engineSettings.lossCooldownMs;
            console.log(`[RISK] 3 consecutive losses — ${engineSettings.lossCooldownMs / 1000}s cooldown activated`);
          }
        }

        await storage.closeTrade(trade.id, currentPrice.toString(), finalPnlPct.toFixed(2), reason);
        tradedAddresses.set(trade.tokenAddress, Date.now());
        // If this was a stop-loss exit, record in the SL blackout map so the same
        // token cannot be re-entered for slReentryDelayMs (default 10 minutes).
        if (reason.startsWith("STOP_LOSS") || reason === "EARLY_CUT" || reason.startsWith("FAST_CUT")) {
          stoppedOutAddresses.set(trade.tokenAddress, Date.now());
          console.log(`[RISK] SL blackout set for $${trade.tokenSymbol} — no re-entry for ${(engineSettings.slReentryDelayMs / 60000).toFixed(0)} min`);
        }
        peakPrices.delete(trade.id);
        partialTpTaken.delete(trade.id);
        tradeStopPrices.delete(trade.id);
        prevPnlMap.delete(trade.id);
        pnlStableMap.delete(trade.id);

        const allTrades = await storage.getTrades();
        const closedTrades = allTrades.filter((t: any) => t.status === "CLOSED");
        const wins = closedTrades.filter((t: any) => parseFloat(t.pnl || "0") > 0).length;
        const totalPnl = closedTrades.reduce((sum: number, t: any) => sum + parseFloat(t.pnl || "0"), 0);
        const wr = closedTrades.length > 0 ? ((wins / closedTrades.length) * 100).toFixed(1) : "0";
        const openNow = allTrades.filter((t: any) => t.status === "OPEN").length;

        const displayBal = isLiveSell && jupiterService
          ? (await jupiterService.getWalletBalance().catch(() => 0)).toFixed(4)
          : paperBalance.toFixed(3);

        const emoji = isWin ? "+" : "";
        await storage.updateBotStats({
          walletBalance: displayBal,
          totalPnl: (totalPnl / Math.max(closedTrades.length, 1)).toFixed(2),
          winRate: wr,
          totalTrades: allTrades.length,
          openPositions: openNow,
          lastSignal: `SOLD $${trade.tokenSymbol} | ${emoji}${finalPnlPct.toFixed(1)}% | ${reason}`,
        });
      }
      } catch (tradeErr) {
        console.error(`[POSITION_MANAGER] Error processing $${trade.tokenSymbol}:`, tradeErr);
      }
    }
  } catch (e) {
    console.error("[POSITION_MANAGER] Error:", e);
  }
}

async function startTradingEngine() {
  if (scannerInterval) clearInterval(scannerInterval);
  if (priceCheckerInterval) clearInterval(priceCheckerInterval);

  console.log("[ENGINE] ULTRA SNIPER ENGINE v4.1 + ML starting...");
  console.log(`[ENGINE] Trailing Stop: activates +${engineSettings.trailingStopActivation}%, trails ${engineSettings.trailingStopDistance}% | Dynamic TP: +${engineSettings.hardTakeProfit}-100% | SL: ${engineSettings.stopLoss}%`);
  console.log(`[ENGINE] Max Hold: dynamic (${engineSettings.maxHoldSeconds}s base → ${engineSettings.dynamicHoldMaxSeconds}s ceiling) | Max Positions: ${engineSettings.maxOpenPositions} | Min Score: ${engineSettings.minScoreToTrade}/100`);
  console.log(`[ENGINE] Score Blend: Rule ${engineSettings.scoreWeight * 100}% + ML ${engineSettings.mlWeight * 100}%`);
  console.log(`[ENGINE] Partial TP: ${engineSettings.partialTpRatio * 100}% @ +${engineSettings.partialTpThreshold}% | Daily Loss Limit: ${engineSettings.dailyLossLimitPct}% | Max DD: ${engineSettings.maxDrawdownPct}%`);
  console.log(`[ENGINE] Scan: ${engineSettings.scanIntervalMs / 1000}s | Price Check: ${engineSettings.priceCheckIntervalMs / 1000}s`);
  console.log(`[ENGINE] Tx Costs: ${engineSettings.txCostsEnabled ? `ENABLED (base fee ${engineSettings.txFeePercent}% each side + liquidity-scaled slippage)` : "DISABLED (paper only)"}`);
  console.log(`[ENGINE] Safety Checks: ${engineSettings.safetyChecksEnabled ? `ENABLED (rugcheck min score ${engineSettings.rugcheckMinScore}, max vol:liq ${engineSettings.maxVolLiqRatioNewToken}x)` : "DISABLED"}`);
  console.log(`[ENGINE] Discovery: tokens created within last ${engineSettings.maxDiscoveryAgeSeconds}s only (no keyword-pump searches)`);
  console.log(`[ENGINE] Dynamic Hold: ${engineSettings.dynamicHoldEnabled ? `ENABLED (score-scaled ${engineSettings.maxHoldSeconds}s–${engineSettings.dynamicHoldMaxSeconds}s, momentum-extended)` : "DISABLED"}`);

  jupiterService = createJupiterService();
  if (jupiterService) {
    const walletBal = await jupiterService.getWalletBalance().catch(() => 0);
    console.log(`[ENGINE] Live trading ENABLED | wallet: ${jupiterService.walletAddress} | balance: ${walletBal.toFixed(4)} SOL`);
    await syncLiveTokenBalances();
  } else {
    console.log("[ENGINE] Live trading DISABLED (no WALLET_PRIVATE_KEY) — paper mode only");
  }

  const mlUp = await checkMLService();
  if (mlUp) {
    console.log("[ENGINE] ML Service connected — XGBoost predictions active");
  } else {
    console.log("[ENGINE] ML Service not available — running on rule-based scoring only");
  }

  setInterval(checkMLService, 30000);

  scannerInterval = setInterval(runScanCycle, engineSettings.scanIntervalMs);
  priceCheckerInterval = setInterval(checkOpenPositions, engineSettings.priceCheckIntervalMs);

  setTimeout(runScanCycle, 3000);
  setTimeout(checkOpenPositions, 8000);
}

async function syncLiveTokenBalances() {
  if (!jupiterService) return;
  try {
    const openTrades = await storage.getOpenTrades();
    const liveTrades = openTrades.filter((t: any) => t.tradingMode === "live");
    if (liveTrades.length === 0) return;

    console.log(`[JUPITER] Syncing token balances for ${liveTrades.length} open live trade(s)...`);
    for (const trade of liveTrades) {
      if (liveTokenBalances.has(trade.id)) continue; 
      const raw = await jupiterService!.getTokenBalance(trade.tokenAddress);
      if (raw > BigInt(0)) {
        liveTokenBalances.set(trade.id, raw);
        console.log(`[JUPITER] Restored trade #${trade.id} ($${trade.tokenSymbol}): ${raw} raw tokens`);
      } else {
        console.warn(`[JUPITER] Trade #${trade.id} ($${trade.tokenSymbol}): no ATA balance found — may already be sold on-chain`);
      }
    }
  } catch (e) {
    console.error("[JUPITER] syncLiveTokenBalances error:", e);
  }
}

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {

  await storage.seedInitialData();

  startTradingEngine();

  app.get(api.status.get.path, async (req, res) => {
    const status = await storage.getBotStatus();
    res.json(status);
  });

  app.get(api.trades.list.path, async (req, res) => {
    const tradesList = await storage.getTrades();
    res.json(tradesList);
  });

  app.get(api.candidates.list.path, async (req, res) => {
    const candidatesList = await storage.getCandidates();
    res.json(candidatesList);
  });

  app.get("/api/candidates/live", async (_req, res) => {
    try {
      const live = await fetchDexScreenerCandidates();
      res.json(live);
    } catch (e) {
      console.error("Live candidates error:", e);
      res.json([]);
    }
  });

  app.get("/api/trades/open", async (_req, res) => {
    const open = await storage.getOpenTrades();
    res.json(open);
  });

  app.get("/api/engine/stats", async (_req, res) => {
    const allTrades = await storage.getTrades();
    const closedTrades = allTrades.filter((t: any) => t.status === "CLOSED");
    const openTrades = allTrades.filter((t: any) => t.status === "OPEN");
    const wins = closedTrades.filter((t: any) => parseFloat(t.pnl || "0") > 0);
    const losses = closedTrades.filter((t: any) => parseFloat(t.pnl || "0") <= 0);
    const avgWin = wins.length > 0 ? wins.reduce((s: number, t: any) => s + parseFloat(t.pnl || "0"), 0) / wins.length : 0;
    const avgLoss = losses.length > 0 ? losses.reduce((s: number, t: any) => s + parseFloat(t.pnl || "0"), 0) / losses.length : 0;
    const totalPnlSol = closedTrades.reduce((s: number, t: any) => {
      const size = parseFloat(t.amount || "0");
      const pnl = parseFloat(t.pnl || "0");
      return s + (size * pnl / 100);
    }, 0);
    const bestTrade = closedTrades.length > 0 ? closedTrades.reduce((best: any, t: any) => parseFloat(t.pnl || "0") > parseFloat(best?.pnl || "-999") ? t : best, closedTrades[0]) : null;
    const worstTrade = closedTrades.length > 0 ? closedTrades.reduce((worst: any, t: any) => parseFloat(t.pnl || "0") < parseFloat(worst?.pnl || "999") ? t : worst, closedTrades[0]) : null;

    const uptimeSeconds = Math.floor((Date.now() - engineStartTime) / 1000);
    const solPerHour = uptimeSeconds > 0 ? (dailyPnlSol / (uptimeSeconds / 3600)).toFixed(4) : "0";

    res.json({
      totalTrades: allTrades.length,
      closedTrades: closedTrades.length,
      openTrades: openTrades.length,
      wins: wins.length,
      losses: losses.length,
      winRate: closedTrades.length > 0 ? ((wins.length / closedTrades.length) * 100).toFixed(1) : "0",
      avgWinPct: avgWin.toFixed(2),
      avgLossPct: avgLoss.toFixed(2),
      totalPnlSol: totalPnlSol.toFixed(4),
      bestTrade: bestTrade ? { symbol: bestTrade.tokenSymbol, pnl: bestTrade.pnl, mode: bestTrade.mode } : null,
      worstTrade: worstTrade ? { symbol: worstTrade.tokenSymbol, pnl: worstTrade.pnl, mode: worstTrade.mode } : null,
      consecutiveWins,
      consecutiveLosses,
      paperBalance: paperBalance.toFixed(3),
      engineVersion: "4.1+ML",
      mlServiceActive: mlServiceAvailable,
      scoreBlend: `Rule ${engineSettings.scoreWeight * 100}% + ML ${engineSettings.mlWeight * 100}%`,
      trailingStop: `+${engineSettings.trailingStopActivation}% / -${engineSettings.trailingStopDistance}%`,
      hardTP: `+${engineSettings.hardTakeProfit}-100%`,
      stopLoss: `${engineSettings.stopLoss}%`,
      solPerHour,
      uptimeSeconds,
      dailyPnlSol: dailyPnlSol.toFixed(4),
      dailyTradeCount,
      peakBalance: peakBalance.toFixed(3),
      drawdownPct: peakBalance > 0 ? Math.max(0, (peakBalance - (await getEffectiveBalance())) / peakBalance * 100).toFixed(1) : "0",
      circuitBreakerActive,
      dailyLossLimitPct: engineSettings.dailyLossLimitPct,
      maxDrawdownPct: engineSettings.maxDrawdownPct,
      txCostsEnabled: !!engineSettings.txCostsEnabled,
      safetyChecksEnabled: !!engineSettings.safetyChecksEnabled,
      dynamicHoldEnabled: !!engineSettings.dynamicHoldEnabled,
      discoveryWindowSeconds: engineSettings.maxDiscoveryAgeSeconds,
    });
  });

  app.get("/api/engine/risk-status", async (_req, res) => {
    const riskCheck = await checkCircuitBreakers();
    const effectiveBal = await getEffectiveBalance();
    const drawdownPct = peakBalance > 0 ? ((peakBalance - effectiveBal) / peakBalance * 100) : 0;
    const realizedLossPct = dailyPnlSol < 0 && dailyStartBalance > 0
      ? (Math.abs(dailyPnlSol) / dailyStartBalance * 100) : 0;

    res.json({
      canTrade: riskCheck.canTrade,
      reason: riskCheck.reason,
      circuitBreakerActive,
      drawdownPct: Math.max(0, drawdownPct).toFixed(1),
      dailyLossPct: realizedLossPct.toFixed(1),
      dailyLossLimitPct: engineSettings.dailyLossLimitPct,
      maxDrawdownPct: engineSettings.maxDrawdownPct,
      peakBalance: peakBalance.toFixed(3),
      dailyStartBalance: dailyStartBalance.toFixed(3),
      consecutiveLosses,
      cooldownActive: Date.now() < lastLossCooldownEnd,
      cooldownRemainingMs: Math.max(0, lastLossCooldownEnd - Date.now()),
    });
  });

  app.get("/api/settings", async (_req, res) => {
    res.json(engineSettings);
  });

  app.post("/api/settings", async (req, res) => {
    try {
      const updates = req.body;
      if (!updates || typeof updates !== "object") {
        return res.status(400).json({ message: "Invalid settings payload" });
      }

      const validKeys = Object.keys(engineSettings) as (keyof typeof engineSettings)[];
      let restartIntervals = false;

      const minValues: Record<string, number> = {
        scanIntervalMs: 1000, priceCheckIntervalMs: 1000, reentryDelayMs: 0, slReentryDelayMs: 0,
        lossCooldownMs: 0, maxHoldSeconds: 10, maxOpenPositions: 1,
        maxTradesPerCycle: 1, minScoreToTrade: 0, startingBalance: 0.1,
        minPositionSize: 0.01, maxPositionSize: 0.1,
        txFeePercent: 0, rugcheckMinScore: 0, maxVolLiqRatioNewToken: 1,
        maxDiscoveryAgeSeconds: 60, dynamicHoldMaxSeconds: 60,
        txCostsEnabled: 0, safetyChecksEnabled: 0, dynamicHoldEnabled: 0,
      };
      const maxValues: Record<string, number> = {
        mlWeight: 1, scoreWeight: 1, partialTpRatio: 1,
        dailyLossLimitPct: 100, maxDrawdownPct: 100,
        txFeePercent: 5, rugcheckMinScore: 1000, maxVolLiqRatioNewToken: 50,
        maxDiscoveryAgeSeconds: 86400, dynamicHoldMaxSeconds: 7200,
        txCostsEnabled: 1, safetyChecksEnabled: 1, dynamicHoldEnabled: 1,
      };

      for (const key of validKeys) {
        if (key in updates) {
          const newVal = updates[key];
          const currentType = typeof engineSettings[key];
          if (currentType === "number" && typeof newVal === "number" && isFinite(newVal)) {
            let clamped = newVal;
            if (key in minValues) clamped = Math.max(clamped, minValues[key]);
            if (key in maxValues) clamped = Math.min(clamped, maxValues[key]);
            (engineSettings as any)[key] = clamped;
            if (key === "scanIntervalMs" || key === "priceCheckIntervalMs") {
              restartIntervals = true;
            }
          } else if (currentType === "string" && typeof newVal === "string") {
            (engineSettings as any)[key] = newVal;
          }
        }
      }

      if (restartIntervals) {
        if (scannerInterval) clearInterval(scannerInterval);
        if (priceCheckerInterval) clearInterval(priceCheckerInterval);
        scannerInterval = setInterval(runScanCycle, engineSettings.scanIntervalMs);
        priceCheckerInterval = setInterval(checkOpenPositions, engineSettings.priceCheckIntervalMs);
        console.log(`[ENGINE] Intervals restarted: scan=${engineSettings.scanIntervalMs}ms, price=${engineSettings.priceCheckIntervalMs}ms`);
      }

      console.log(`[SETTINGS] Updated engine settings:`, JSON.stringify(updates));
      res.json(engineSettings);
    } catch (e) {
      console.error("[SETTINGS] Error:", e);
      res.status(500).json({ message: "Failed to update settings" });
    }
  });

  app.post("/api/bot/force-sell-all", async (_req, res) => {
    try {
      const openTrades = await storage.getOpenTrades();
      let closedCount = 0;

      for (const trade of openTrades) {
        const { price: currentPrice } = await fetchTokenPrice(trade.tokenAddress);
        if (currentPrice <= 0) continue;

        const entryPrice = parseFloat(trade.price);
        const pnlPct = entryPrice > 0 ? ((currentPrice - entryPrice) / entryPrice) * 100 : 0;
        const sizeSol = parseFloat(trade.amount);
        const returnSol = sizeSol * (1 + pnlPct / 100);
        paperBalance += returnSol;
        dailyPnlSol += returnSol - sizeSol;

        if (paperBalance > peakBalance) peakBalance = paperBalance;

        await storage.closeTrade(trade.id, currentPrice.toString(), pnlPct.toFixed(2), "FORCE_SELL");
        tradedAddresses.set(trade.tokenAddress, Date.now());
        peakPrices.delete(trade.id);
        partialTpTaken.delete(trade.id);
        tradeStopPrices.delete(trade.id);
        prevPnlMap.delete(trade.id);
        pnlStableMap.delete(trade.id);
        closedCount++;

        console.log(`[FORCE] Sold $${trade.tokenSymbol} @ $${currentPrice.toFixed(8)} | PNL: ${pnlPct.toFixed(2)}%`);
      }

      await storage.updateBotStats({
        walletBalance: paperBalance.toFixed(3),
        openPositions: 0,
        lastSignal: `Force sold ${closedCount} positions`,
      });

      res.json({ success: true, closedCount, newBalance: paperBalance.toFixed(3) });
    } catch (e) {
      console.error("[FORCE_SELL] Error:", e);
      res.status(500).json({ success: false, error: "Failed to force sell" });
    }
  });

  app.post("/api/bot/reset-balance", async (_req, res) => {
    try {
      const openTrades = await storage.getOpenTrades();
      for (const trade of openTrades) {
        await storage.closeTrade(trade.id, trade.currentPrice || trade.price, "0", "RESET");
        tradedAddresses.set(trade.tokenAddress, Date.now());
        peakPrices.delete(trade.id);
        partialTpTaken.delete(trade.id);
        tradeStopPrices.delete(trade.id);
        prevPnlMap.delete(trade.id);
        pnlStableMap.delete(trade.id);
      }

      paperBalance = engineSettings.startingBalance;
      peakBalance = engineSettings.startingBalance;
      dailyStartBalance = engineSettings.startingBalance;
      dailyPnlSol = 0;
      dailyTradeCount = 0;
      consecutiveWins = 0;
      consecutiveLosses = 0;
      circuitBreakerActive = false;
      lastLossCooldownEnd = 0;
      tradeStopPrices.clear();
      stoppedOutAddresses.clear();
      prevPnlMap.clear();
      pnlStableMap.clear();

      await storage.updateBotStats({
        walletBalance: engineSettings.startingBalance.toFixed(3),
        totalPnl: "0",
        openPositions: 0,
        lastSignal: `Balance reset to ${engineSettings.startingBalance} SOL`,
      });

      console.log(`[ENGINE] Paper balance reset to ${engineSettings.startingBalance} SOL`);
      res.json({ success: true, newBalance: engineSettings.startingBalance.toFixed(3) });
    } catch (e) {
      console.error("[RESET] Error:", e);
      res.status(500).json({ success: false, error: "Failed to reset" });
    }
  });

  app.post("/api/bot/trading-mode", async (req, res) => {
    const { mode, confirmed } = req.body;
    if (!mode || !["paper", "live"].includes(mode)) {
      return res.status(400).json({ message: "Invalid trading mode. Use 'paper' or 'live'." });
    }
    if (mode === "live" && !confirmed) {
      return res.status(400).json({ message: "Live trading requires explicit confirmation. Set confirmed: true." });
    }
    const status = await storage.updateTradingMode(mode);
    res.json(status);
  });

  app.post("/api/bot/toggle", async (req, res) => {
    const { isRunning } = req.body;
    if (typeof isRunning !== "boolean") {
      return res.status(400).json({ message: "isRunning must be boolean" });
    }
    if (isRunning) {
      circuitBreakerActive = false;
      lastLossCooldownEnd = 0;
    }
    const status = await storage.updateBotRunning(isRunning);
    res.json(status);
  });

  app.post("/api/bot/strategy-mode", async (req, res) => {
    const { mode } = req.body;
    if (!mode || !["SNIPER", "MG", "HWR", "AUTO"].includes(mode)) {
      return res.status(400).json({ message: "Invalid strategy mode" });
    }
    const status = await storage.updateStrategyMode(mode);
    res.json(status);
  });

  app.get("/api/wallet", async (_req, res) => {
    if (!jupiterService) {
      return res.json({
        connected: false,
        address: null,
        balanceSol: null,
        liveTradesActive: 0,
        message: "WALLET_PRIVATE_KEY not set — live trading disabled",
      });
    }
    try {
      const [balanceSol, openTrades] = await Promise.all([
        jupiterService.getWalletBalance(),
        storage.getOpenTrades(),
      ]);
      const liveOpen = (openTrades as any[]).filter(t => t.tradingMode === "live");
      res.json({
        connected: true,
        address: jupiterService.walletAddress,
        balanceSol: parseFloat(balanceSol.toFixed(4)),
        liveTradesActive: liveOpen.length,
        trackedTokenBalances: liveTokenBalances.size,
        rpcUrl: process.env.SOLANA_RPC_URL?.slice(0, 40) + "...",
        priorityFeeMicrolamports: parseInt(process.env.PRIORITY_FEE_MICROLAMPORTS ?? "200000"),
      });
    } catch (e: any) {
      res.status(500).json({ connected: true, address: jupiterService.walletAddress, error: e.message });
    }
  });

  return httpServer;
}