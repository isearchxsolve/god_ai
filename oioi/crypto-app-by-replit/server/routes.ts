import type { Express } from "express";
import type { Server } from "http";
import { storage } from "./storage";
import { api } from "@shared/routes";

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

const TRAILING_STOP_ACTIVATION = 8;
const TRAILING_STOP_DISTANCE = 5;
const HARD_TAKE_PROFIT = 50;
const STOP_LOSS = -12;
const MAX_HOLD_SECONDS = 600;
const MAX_OPEN_POSITIONS = 8;
const STARTING_BALANCE = 10;
const SCAN_INTERVAL_MS = 10000;
const PRICE_CHECK_INTERVAL_MS = 5000;
const MIN_SCORE_TO_TRADE = 70;

const ML_SERVICE_URL = "http://localhost:5001";
const ML_WEIGHT = 0.35;
const SCORE_WEIGHT = 0.65;

let liveCandidatesCache: any[] = [];
let lastScanTime = 0;
let tradedAddresses = new Set<string>();
let paperBalance = STARTING_BALANCE;
let balanceInitialized = false;
let consecutiveWins = 0;
let consecutiveLosses = 0;
let mlServiceAvailable = false;

async function checkMLService(): Promise<boolean> {
  try {
    const resp = await fetch(`${ML_SERVICE_URL}/health`, { signal: AbortSignal.timeout(2000) });
    if (resp.ok) {
      const data = await resp.json() as any;
      if (!mlServiceAvailable) {
        console.log(`[DASHBOARD] Connected to XGBoost model v${data.model_version} (${data.features?.length} features)`);
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

    const resp = await fetch(`${ML_SERVICE_URL}/predict`, {
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

    const resp = await fetch(`${ML_SERVICE_URL}/predict/batch`, {
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
    const data = await resp.json() as { pairs?: DexScreenerPair[] };
    if (!data.pairs || data.pairs.length === 0) return { price: 0, pair: null };
    const solanaPairs = data.pairs.filter((p: DexScreenerPair) => p.chainId === "solana");
    if (solanaPairs.length === 0) return { price: 0, pair: null };
    const best = solanaPairs.reduce((a: DexScreenerPair, b: DexScreenerPair) =>
      ((a.liquidity?.usd || 0) > (b.liquidity?.usd || 0) ? a : b)
    );
    return { price: parseFloat(best.priceUsd || "0"), pair: best };
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

  if (liq < 1000) return { score: 0, mlScore: null, combinedScore: 0, breakdown: {}, metrics: {}, qualifiedMode: null, sizeSol: 0, slippage: 0 };

  let breakdown: Record<string, number> = {};

  const bpScore = buyPressure5m > 0.7 ? 20 : buyPressure5m > 0.6 ? 15 : buyPressure5m > 0.55 ? 10 : buyPressure5m > 0.5 ? 5 : 0;
  breakdown.buyPressure = bpScore;

  const vmScore = volMomentum > 3 ? 20 : volMomentum > 2 ? 15 : volMomentum > 1.5 ? 10 : volMomentum > 1 ? 5 : 0;
  breakdown.volumeMomentum = vmScore;

  let trendScore = 0;
  if (priceChange5m > 10) trendScore += 8;
  else if (priceChange5m > 5) trendScore += 6;
  else if (priceChange5m > 2) trendScore += 3;
  else if (priceChange5m < -5) trendScore -= 5;
  if (priceChange1h > 20) trendScore += 7;
  else if (priceChange1h > 10) trendScore += 5;
  else if (priceChange1h > 0) trendScore += 2;
  else if (priceChange1h < -10) trendScore -= 5;
  breakdown.trend = Math.max(0, Math.min(15, trendScore));

  const txScore = txVelocity5m > 100 ? 15 : txVelocity5m > 50 ? 12 : txVelocity5m > 20 ? 8 : txVelocity5m > 10 ? 5 : 0;
  breakdown.txVelocity = txScore;

  let liqScore = 0;
  if (liq > 50000) liqScore = 10;
  else if (liq > 20000) liqScore = 8;
  else if (liq > 5000) liqScore = 6;
  else if (liq > 2000) liqScore = 4;
  breakdown.liquidity = liqScore;

  let freshScore = 0;
  if (ageSeconds < 60) freshScore = 10;
  else if (ageSeconds < 300) freshScore = 8;
  else if (ageSeconds < 900) freshScore = 5;
  else if (ageSeconds < 3600) freshScore = 3;
  breakdown.freshness = freshScore;

  let multiTfScore = 0;
  const alignedUp = (priceChange5m > 0 ? 1 : 0) + (priceChange1h > 0 ? 1 : 0) + (priceChange6h > 0 ? 1 : 0);
  if (alignedUp >= 3) multiTfScore = 10;
  else if (alignedUp >= 2 && priceChange5m > 0) multiTfScore = 7;
  else if (alignedUp >= 2) multiTfScore = 4;
  if (priceChange5m > 0 && priceChange1h > 0 && priceChange5m > priceChange1h / 12) multiTfScore += 3;
  breakdown.multiTimeframe = Math.min(10, multiTfScore);

  const totalScore = Object.values(breakdown).reduce((a, b) => a + b, 0);

  const metrics = {
    liq, ageSeconds, buyPressure5m, buyPressure1h, volMomentum,
    priceChange5m, priceChange1h, priceChange6h, priceChange24h,
    vol5m, vol1h, vol24h, txVelocity5m, fdv, mcap,
    m5buys, m5sells, h1buys, h1sells
  };

  const mlScore = mlPrediction ? Math.round(mlPrediction.pumpProb * 100) : null;

  let combinedScore: number;
  if (mlScore !== null) {
    combinedScore = Math.round(totalScore * SCORE_WEIGHT + mlScore * ML_WEIGHT);
    if (mlScore >= 90 && totalScore >= 60) combinedScore = Math.max(combinedScore, totalScore + 10);
    if (mlScore < 30 && totalScore >= 70) combinedScore = Math.min(combinedScore, totalScore - 10);
  } else {
    combinedScore = totalScore;
  }

  const effectiveScore = combinedScore;

  let qualifiedMode: string | null = null;
  let sizeSol = 0;
  let slippage = 2;

  if (ageSeconds < 180 && effectiveScore >= 60 && buyPressure5m > 0.55 && liq > 1000) {
    qualifiedMode = "SNIPER";
    sizeSol = Math.min(1.5, liq / 30000);
    slippage = liq < 20000 ? 15 : 10;
  } else if (effectiveScore >= 70 && volMomentum > 1.5 && priceChange5m > 2 && txVelocity5m > 15) {
    qualifiedMode = "MG";
    sizeSol = Math.min(1.0, liq / 50000);
    slippage = 5;
  } else if (effectiveScore >= 75 && buyPressure5m > 0.6 && buyPressure1h > 0.55 && liq > 5000) {
    qualifiedMode = "HWR";
    sizeSol = Math.min(0.8, liq / 80000);
    slippage = 3;
  }

  if (effectiveScore >= 85) sizeSol *= 1.5;
  if (effectiveScore >= 90) sizeSol *= 1.3;

  if (consecutiveWins >= 3) sizeSol *= 1.2;
  if (consecutiveLosses >= 3) sizeSol *= 0.6;

  sizeSol = Math.min(2.0, Math.max(0.01, Math.round(sizeSol * 1000) / 1000));

  return { score: totalScore, mlScore, combinedScore, breakdown, metrics, qualifiedMode, sizeSol, slippage };
}

async function fetchDexScreenerCandidates(): Promise<any[]> {
  const now = Date.now();
  if (now - lastScanTime < 6000 && liveCandidatesCache.length > 0) {
    return liveCandidatesCache;
  }

  try {
    const searchQueries = ["pump", "moon", "sol new"];
    const allPairs: DexScreenerPair[] = [];

    const fetchPromises = [
      fetch("https://api.dexscreener.com/token-profiles/latest/v1").then(r => r.ok ? r.json() : []).catch(() => []),
      ...searchQueries.map(q =>
        fetch(`https://api.dexscreener.com/latest/dex/search?q=${encodeURIComponent(q)}`)
          .then(r => r.ok ? r.json() : { pairs: [] })
          .catch(() => ({ pairs: [] }))
      ),
    ];

    const [profiles, ...searchResults] = await Promise.all(fetchPromises);

    for (const sr of searchResults) {
      if (sr.pairs) {
        const solanaPairs = (sr.pairs as DexScreenerPair[])
          .filter(p => p.chainId === "solana" && (p.liquidity?.usd || 0) > 1000)
          .slice(0, 10);
        allPairs.push(...solanaPairs);
      }
    }

    const solanaProfiles = ((profiles as any[]) || [])
      .filter((t: any) => t.chainId === "solana")
      .slice(0, 8);

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

    for (const profile of solanaProfiles) {
      if (seenAddresses.has(profile.tokenAddress)) continue;
      try {
        const { price, pair } = await fetchTokenPrice(profile.tokenAddress);
        if (!pair) continue;

        const mlPred = await getMLPrediction(scoreToken(pair).metrics);
        const scoring = scoreToken(pair, mlPred);
        const liq = pair.liquidity?.usd || 0;
        const createdAt = pair.pairCreatedAt || Date.now();
        const ageSeconds = Math.floor((Date.now() - createdAt) / 1000);
        seenAddresses.add(profile.tokenAddress);

        results.push({
          tokenAddress: pair.baseToken.address,
          tokenSymbol: pair.baseToken.symbol,
          tokenName: pair.baseToken.name,
          dex: pair.dexId,
          price: pair.priceUsd || "0",
          liquidity: liq.toFixed(0),
          score: scoring.combinedScore,
          mlScore: scoring.mlScore,
          ruleScore: scoring.score,
          pumpProbability: (scoring.combinedScore / 100).toFixed(3),
          dumpRisk: (1 - scoring.combinedScore / 100).toFixed(3),
          ageSeconds,
          qualifiedMode: scoring.qualifiedMode,
          volume5m: (pair.volume?.m5 || 0).toFixed(0),
          volume1h: (pair.volume?.h1 || 0).toFixed(0),
          volume24h: (pair.volume?.h24 || 0).toFixed(0),
          priceChange5m: pair.priceChange?.m5 || 0,
          priceChange1h: pair.priceChange?.h1 || 0,
          buys5m: pair.txns?.m5?.buys || 0,
          sells5m: pair.txns?.m5?.sells || 0,
          buys1h: pair.txns?.h1?.buys || 0,
          sells1h: pair.txns?.h1?.sells || 0,
          buyPressure5m: scoring.metrics.buyPressure5m?.toFixed(3) || "0.500",
          fdv: pair.fdv || 0,
          marketCap: pair.marketCap || 0,
          mlActive: mlPred !== null,
          source: "dexscreener_live",
          timestamp: new Date().toISOString(),
        });
      } catch {
        continue;
      }
    }

    results.sort((a, b) => (b.score || 0) - (a.score || 0));

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

async function startTradingEngine() {
  console.log("[DASHBOARD] UI Backend started. Node.js Trading Engine is DISABLED.");
  console.log("[DASHBOARD] Routing logic deferred to Python execution layer.");

  const mlUp = await checkMLService();
  if (mlUp) {
    console.log("[DASHBOARD] ✓ ML Service connected for live UI scanning");
  } else {
    console.log("[DASHBOARD] ⚠ ML Service not available — running on rule-based scoring only");
  }

  setInterval(checkMLService, 30000);
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
    
    const status = await storage.getBotStatus();

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
      paperBalance: status.walletBalance || "10.00",
      engineVersion: "3.0+ML (UI Dashboard Mode)",
      mlServiceActive: mlServiceAvailable,
      scoreBlend: `Rule ${SCORE_WEIGHT * 100}% + ML ${ML_WEIGHT * 100}%`,
      trailingStop: `Controlled by Python Engine`,
      hardTP: `Controlled by Python Engine`,
      stopLoss: `Controlled by Python Engine`,
    });
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

  // --- INTERNAL API FOR PYTHON BOT (DO NOT EXPOSE TO FRONTEND) ---

  app.post("/api/internal/trade/open", async (req, res) => {
    try {
      const tradeData = req.body;
      const trade = await storage.addTrade(tradeData);
      
      const openTrades = await storage.getOpenTrades();
      const allTrades = await storage.getTrades();
      await storage.updateBotStats({
        openPositions: openTrades.length,
        totalTrades: allTrades.length,
        lastSignal: `🎯 PYTHON BUY $${tradeData.tokenSymbol} (Score: ${tradeData.score})`
      });

      res.json(trade);
    } catch (e) {
      console.error("Failed to open trade from Python:", e);
      res.status(500).json({ error: "Failed to open trade" });
    }
  });

  app.post("/api/internal/trade/update", async (req, res) => {
    try {
      const { id, currentPrice, pnl, peakPrice, peakPnl } = req.body;
      if (id) {
        await storage.updateTradeCurrentPrice(id, currentPrice, pnl);
        await storage.updateTradePeakPrice(id, peakPrice, peakPnl);
      }
      res.json({ success: true });
    } catch (e) {
      // Silently fail to avoid console log spam during rapid polling
      res.status(500).json({ error: "Failed to update trade" });
    }
  });

  app.post("/api/internal/trade/close", async (req, res) => {
    try {
      const { id, currentPrice, pnl, exitReason, newBalance } = req.body;
      if (id) {
        await storage.closeTrade(id, currentPrice, pnl, exitReason);
      }
      
      const openTrades = await storage.getOpenTrades();
      const allTrades = await storage.getTrades();
      const closedTrades = allTrades.filter((t: any) => t.status === "CLOSED");
      const wins = closedTrades.filter((t: any) => parseFloat(t.pnl || "0") > 0).length;
      const wr = closedTrades.length > 0 ? ((wins / closedTrades.length) * 100).toFixed(1) : "0";
      
      const isWin = parseFloat(pnl) > 0;
      const emoji = isWin ? "💰" : "🔻";

      await storage.updateBotStats({
        openPositions: openTrades.length,
        walletBalance: newBalance,
        winRate: wr,
        lastSignal: `${emoji} PYTHON SOLD | ${parseFloat(pnl).toFixed(1)}% | ${exitReason}`
      });

      res.json({ success: true });
    } catch (e) {
      console.error("Failed to close trade from Python:", e);
      res.status(500).json({ error: "Failed to close trade" });
    }
  });

  return httpServer;
}