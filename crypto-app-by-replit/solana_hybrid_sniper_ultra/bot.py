import asyncio
import aiohttp
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
from strategy import HybridStrategy
from utils.data_fetcher import DataFetcher
from ml.predict import Predictor
from executor_paper import PaperExecutor
from executor_live import LiveExecutor

# --- FIX WINDOWS EMOJI ERROR ---
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("solana_hybrid_sniper_ultra/logs/bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("SniperBot")

load_dotenv()

# How often (seconds) to poll prices for ALL open positions, independent of scanner
POSITION_MONITOR_INTERVAL = float(os.getenv("POSITION_MONITOR_INTERVAL", "1"))

# DexScreener endpoint for on-demand price fetching
DEXSCREENER_URL = "https://api.dexscreener.com/latest/dex/tokens/{}"

# Tokens older than this (seconds) are outside the sniper window and skipped
MAX_TOKEN_AGE_SECONDS = int(os.getenv("MAX_TOKEN_AGE", "900"))


class SolanaSniperBot:
    def __init__(self):
        self.fetcher        = DataFetcher()
        self.strategy       = HybridStrategy()
        self.predictor      = Predictor()
        self.paper_executor = PaperExecutor(strategy=self.strategy)
        self.live_executor  = LiveExecutor(strategy=self.strategy)

        self.is_running   = False
        self.trading_mode = os.getenv("MODE", "paper")
        self.scan_interval = float(os.getenv("SCAN_INTERVAL", "5"))
        
        self.stats = {"scanned": 0, "signals": 0, "errors": 0, "last_logged_scan": 0}
        self._session: aiohttp.ClientSession | None = None

        # Restore open positions into RiskManager on startup
        self._sync_risk_manager_from_executors()

    def _sync_risk_manager_from_executors(self) -> None:
        """Rebuild strategy.risk.positions from executor state on startup."""
        restored = 0
        # Paper positions
        for pos in self.paper_executor.get_open_positions():
            addr = pos.get("mint")
            if not addr or addr in self.strategy.risk.positions:
                continue
            opened_raw = pos.get("timestamp")
            try:
                opened_at = datetime.fromisoformat(opened_raw) if opened_raw else datetime.utcnow()
            except Exception:
                opened_at = datetime.utcnow()
            self.strategy.risk.positions[addr] = {
                "symbol":          pos.get("symbol", "?"),
                "mode":            pos.get("mode", "DEFAULT"),
                "entry_price":     pos.get("entry_price", 0),
                "size_sol":        pos.get("size_sol", 0),
                "peak_price":      pos.get("peak_price", pos.get("entry_price", 0)),
                "tp1_triggered":   pos.get("tp1_triggered", False),
                "tp2_triggered":   pos.get("tp2_triggered", False),
                "trailing_active": pos.get("trailing_active", False),
                "opened_at":       opened_at,
                "pnl_pct":         0.0,
            }
            restored += 1
        # Live positions
        for pos in self.live_executor.get_open_positions():
            addr = pos.get("mint") or pos.get("address")
            if not addr or addr in self.strategy.risk.positions:
                continue
            opened_raw = pos.get("opened_at")
            try:
                opened_at = datetime.fromisoformat(opened_raw) if opened_raw else datetime.utcnow()
            except Exception:
                opened_at = datetime.utcnow()
            self.strategy.risk.positions[addr] = {
                "symbol":          pos.get("symbol", "?"),
                "mode":            pos.get("mode", "DEFAULT"),
                "entry_price":     pos.get("entry_price", 0),
                "size_sol":        pos.get("size_sol", 0),
                "peak_price":      pos.get("peak_price", pos.get("entry_price", 0)),
                "tp1_triggered":   pos.get("tp1_triggered", False),
                "tp2_triggered":   pos.get("tp2_triggered", False),
                "trailing_active": pos.get("trailing_active", False),
                "opened_at":       opened_at,
                "pnl_pct":         0.0,
            }
            restored += 1
        if restored:
            logger.info(f"Restored {restored} position(s) into RiskManager from executor state")

    def set_trading_mode(self, mode: str) -> None:
        if mode in ("paper", "live"):
            self.trading_mode = mode
            logger.info(f"Trading mode switched to: {mode.upper()}")

    # ── Entry point — runs TWO loops concurrently ────────────────────────────

    async def start(self) -> None:
        logger.info(f"Starting Solana Hybrid Sniper Ultra [Mode: {self.trading_mode.upper()}]")
        logger.info(f"Model: {self.predictor.version} | Scan: {self.scan_interval}s | Monitor: {POSITION_MONITOR_INTERVAL}s")

        if self.predictor.is_using_heuristic:
            logger.warning("=" * 60)
            logger.warning("⚠️  RUNNING IN HEURISTIC MODE — XGBoost model not loaded.")
            logger.warning("   Accuracy is lower. Thresholds auto-tightened by +0.05.")
            logger.warning("   Fix: pip install xgboost  then restart.")
            logger.warning("=" * 60)

        self.is_running = True
        self._session   = aiohttp.ClientSession()

        try:
            # Run scanner + position monitor truly in parallel
            await asyncio.gather(
                self._scan_loop(),
                self._position_monitor_loop(),
            )
        finally:
            await self.fetcher.close()
            if self._session:
                await self._session.close()
            logger.info("Bot shutdown complete.")

    # ── Loop 1: Scanner — finds new entry signals ────────────────────────────

    async def _scan_loop(self) -> None:
        while self.is_running:
            try:
                tokens = await self.fetcher.get_new_listings()
                self.stats["scanned"] += len(tokens)

                for token in tokens:
                    address = token.get("address")
                    if not address:
                        continue

                    age = token.get("age_seconds", 99999)
                    if age > MAX_TOKEN_AGE_SECONDS:
                        logger.debug(
                            f"Skipping {token.get('symbol','?')} — "
                            f"age {age:.0f}s > {MAX_TOKEN_AGE_SECONDS}s limit"
                        )
                        continue

                    features = self.fetcher.process_features(token)
                    features["address"] = address
                    features["symbol"]  = token.get("symbol", "UNKNOWN")

                    predictions = self.predictor.predict(features)
                    signal      = self.strategy.analyze(features, predictions)

                    if signal and signal["action"] == "BUY":
                        entry_price = token.get("price", 0)
                        mode        = signal["mode"]
                        self.stats["signals"] += 1

                        heuristic_tag = " [⚠️HEURISTIC]" if predictions.get("is_heuristic") else ""
                        logger.info(
                            f"SIGNAL #{self.stats['signals']}: ${token['symbol']} | "
                            f"Strategy={mode} | Prob={predictions['pump_probability']:.2f}{heuristic_tag} | "
                            f"Size={signal['size_sol']} SOL | "
                            f"Liq=${token.get('liquidity', 0):,.0f} | "
                            f"Age={token.get('age_seconds', 0):.0f}s"
                        )

                        if self.trading_mode == "live":
                            success = await self.live_executor.execute_buy(token, mode, signal)
                        else:
                            success = await self.paper_executor.execute_trade(token, mode, signal)

                        if success:
                            self.strategy.risk.open_position(
                                address, entry_price, signal["size_sol"],
                                mode, token.get("symbol", "?")
                            )

                # Periodic stats
                if self.stats["scanned"] - self.stats.get("last_logged_scan", 0) >= 50:
                    self.stats["last_logged_scan"] = self.stats["scanned"]
                    ps       = self.paper_executor.get_stats()
                    live_cnt = len(self.live_executor.get_open_positions())
                    logger.info(
                        f"Stats | Scanned={self.stats['scanned']} | "
                        f"Signals={self.stats['signals']} | Errors={self.stats['errors']} | "
                        f"PaperPnL={ps.get('total_pnl_sol',0):+.4f} SOL | "
                        f"WinRate={ps.get('win_rate',0)}% | LiveOpen={live_cnt}"
                    )

                await asyncio.sleep(self.scan_interval)

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(f"[Scanner] Error: {e}")
                await asyncio.sleep(10)

    # ── Loop 2: Position monitor — runs independently of scanner ─────────────

    async def _position_monitor_loop(self) -> None:
        while self.is_running:
            try:
                open_positions = list(self.strategy.risk.positions.items())

                if not open_positions:
                    await asyncio.sleep(POSITION_MONITOR_INTERVAL)
                    continue

                # Fetch prices for all held tokens concurrently
                tasks = {
                    address: asyncio.create_task(self._fetch_price(address))
                    for address, _ in open_positions
                }
                await asyncio.gather(*tasks.values(), return_exceptions=True)

                for address, task in tasks.items():
                    try:
                        price = task.result()
                    except Exception:
                        continue

                    if not price:
                        continue

                    # Keep peak_price current so trailing stop simulation is accurate
                    self.paper_executor.update_peak(address, price)

                    # --- DASHBOARD API BRIDGE: Live PNL Update ---
                    pos_data = self.strategy.risk.positions.get(address, {})
                    entry = pos_data.get("entry_price", 0)
                    if entry > 0 and self._session:
                        pnl_pct = (price - entry) / entry * 100
                        peak = max(pos_data.get("peak_price", entry), price)
                        peak_pnl = (peak - entry) / entry * 100
                        
                        db_id = None
                        if self.trading_mode == "paper":
                            db_id = self.paper_executor._open.get(address, {}).get("db_id")
                        else:
                            db_id = self.live_executor._positions.get(address, {}).get("db_id")

                        if db_id:
                            # Safely fire background UI update to prevent socket leak
                            asyncio.create_task(self._ping_dashboard(db_id, price, pnl_pct, peak, peak_pnl))
                    # ---------------------------------------------

                    sym = pos_data.get("symbol", address[:8])

                    exit_signal = self.strategy.check_exit(address, price)
                    if not exit_signal:
                        continue

                    reason    = exit_signal["reason"]
                    close_pct = exit_signal.get("close_pct", 1.0)
                    pnl       = exit_signal.get("pnl_pct", 0)
                    is_emergency = reason == "EMERGENCY_STOP"

                    logger.warning(
                        f"{'🚨' if is_emergency else '🔔'} EXIT: ${sym} | "
                        f"reason={reason} | pnl={pnl:+.1%} | close={close_pct:.0%}"
                    )

                    if self.trading_mode == "paper":
                        await self.paper_executor.close_position(
                            address, price, reason, close_pct
                        )
                    else:
                        await self.live_executor.execute_exit(address, close_pct, reason)

            except Exception as e:
                logger.error(f"[PositionMonitor] Error: {e}")

            await asyncio.sleep(POSITION_MONITOR_INTERVAL)

    # ── Safe Dashboard Ping ──────────────────────────────────────────────────

    async def _ping_dashboard(self, db_id, price, pnl_pct, peak, peak_pnl):
        """Safely updates the UI without leaking network sockets."""
        if not self._session:
            return
        try:
            async with self._session.post(
                "http://localhost:5000/api/internal/trade/update",
                json={
                    "id": db_id,
                    "currentPrice": str(price),
                    "pnl": f"{pnl_pct:.2f}",
                    "peakPrice": str(peak),
                    "peakPnl": f"{peak_pnl:.2f}"
                },
                timeout=aiohttp.ClientTimeout(total=1)
            ) as resp:
                await resp.read() # Forces the connection to close and return to the pool
        except Exception:
            pass # Silently fail if UI is off, ensuring the bot keeps trading

    # ── Price fetch via DexScreener (free, no key required) ─────────────────

    async def _fetch_price(self, address: str) -> float | None:
        try:
            url = DEXSCREENER_URL.format(address)
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                pairs = data.get("pairs") or []
                if not pairs:
                    return None
                sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                best = sorted(sol_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0)), reverse=True)
                if not best:
                    return None
                price_str = best[0].get("priceUsd", "0")
                return float(price_str) if price_str else None
        except Exception as e:
            logger.debug(f"Price fetch failed for {address[:8]}: {e}")
            return None

    def stop(self) -> None:
        self.is_running = False
        logger.info("Stopping bot...")


if __name__ == "__main__":
    bot = SolanaSniperBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        bot.stop()