import logging
import os
from datetime import datetime, timedelta

logger = logging.getLogger("Strategy")

# ── Risk constants ──────────────────────────────────────────────────────────
# Per-mode stop losses instead of one global value.
STOP_LOSS_BY_MODE = {
    "HWR":    -0.08,   # -8%  (conservative)
    "MG":     -0.10,   # -10% (momentum)
    "SNIPER": -0.13,   # -13% (sniper tokens are volatile, need more room)
    "DEFAULT":-0.10,   # fallback
}
STOP_LOSS_HARD_PCT     = -0.16   # Emergency gap-down limit

TAKE_PROFIT_1_PCT      =  0.30   # First TP: +30% → close 50%
TAKE_PROFIT_2_PCT      =  0.60   # Second TP: +60% → close remaining 75%
TRAILING_STOP_PCT      =  0.10   # Trail: 10% below peak

# Early-exit velocity guard.
# If price drops >DROP_VELOCITY_PCT within the first DROP_VELOCITY_WINDOW_S
# seconds of entry, exit immediately — this catches fast gap-downs early.
DROP_VELOCITY_PCT      = -0.05   # -5% in ...
DROP_VELOCITY_WINDOW_S =  45     # ... first 45 seconds = emergency exit

MAX_HOLD_SECONDS       = 1800    # Force exit after 30 min
COOLDOWN_SECONDS       = 180     # Cooldown after loss
TOKEN_BLACKLIST_SECS   = 900     # Block same token for 15 min after ANY exit
MAX_ENTRIES_PER_TOKEN  = 2
MAX_OPEN_POSITIONS     = 4

# Hard minimum pump_probability below which we NEVER enter.
MIN_PUMP_PROB          = 0.62    # below this = skip entirely, no exceptions
ABSOLUTE_MAX_SOL       = 0.25    # Hard ceiling per trade regardless of liquidity


class RiskManager:
    """Tracks open positions and enforces exit rules."""

    HISTORY_PATH = "solana_hybrid_sniper_ultra/data/token_blacklist.json"

    def __init__(self):
        self.positions: dict[str, dict] = {}
        self._last_loss_time: datetime | None = None
        self._consecutive_losses = 0
        self._token_history: dict[str, dict] = {}
        self._load_history()

    # ── History persistence ──────────────────────────────────────────────────

    def _load_history(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.HISTORY_PATH), exist_ok=True)
            if not os.path.exists(self.HISTORY_PATH):
                return
            import json
            with open(self.HISTORY_PATH) as f:
                raw = json.load(f)
            for addr, rec in raw.items():
                last = rec.get("last_exit")
                self._token_history[addr] = {
                    "exits":     rec.get("exits", 0),
                    "last_exit": datetime.fromisoformat(last) if last else None,
                }
            logger.info(f"Loaded blacklist: {len(self._token_history)} token(s)")
        except Exception as e:
            logger.warning(f"Could not load blacklist: {e}")

    def _save_history(self) -> None:
        try:
            import json
            serialisable = {
                addr: {
                    "exits":     rec["exits"],
                    "last_exit": rec["last_exit"].isoformat() if rec["last_exit"] else None,
                }
                for addr, rec in self._token_history.items()
            }
            with open(self.HISTORY_PATH, "w") as f:
                json.dump(serialisable, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save blacklist: {e}")

    # ── Position lifecycle ──────────────────────────────────────────────────

    def open_position(self, address: str, entry_price: float, size_sol: float,
                      mode: str, symbol: str) -> None:
        self.positions[address] = {
            "symbol":          symbol,
            "mode":            mode,
            "entry_price":     entry_price,
            "size_sol":        size_sol,
            "peak_price":      entry_price,
            "tp1_triggered":   False,
            "tp2_triggered":   False,
            "trailing_active": False,
            "opened_at":       datetime.utcnow(),
            "pnl_pct":         0.0,
        }
        stop = STOP_LOSS_BY_MODE.get(mode, STOP_LOSS_BY_MODE["DEFAULT"])
        logger.info(
            f"Position opened: {symbol} @ {entry_price:.2e} | {size_sol:.3f} SOL | "
            f"mode={mode} | stop={stop:.0%} | hard_stop={STOP_LOSS_HARD_PCT:.0%}"
        )

    def update_position(self, address: str, current_price: float) -> dict | None:
        """
        Feed current price. Returns exit signal dict if exit triggered, else None.
        """
        pos = self.positions.get(address)
        if not pos or pos["entry_price"] == 0:
            return None

        entry    = pos["entry_price"]
        peak     = pos["peak_price"]
        mode     = pos.get("mode", "DEFAULT")
        pnl_pct  = (current_price - entry) / entry

        pos["pnl_pct"]    = pnl_pct
        pos["peak_price"] = max(peak, current_price)
        peak              = pos["peak_price"]
        age_s             = (datetime.utcnow() - pos["opened_at"]).total_seconds()

        # ── Emergency hard stop ────────────────────
        if pnl_pct <= STOP_LOSS_HARD_PCT:
            logger.warning(
                f"🚨 EMERGENCY STOP for {pos['symbol']}: {pnl_pct:+.1%} gap-down "
                f"(hard stop={STOP_LOSS_HARD_PCT:.0%})"
            )
            return self._exit(address, "EMERGENCY_STOP", pnl_pct, 1.0)

        # ── Per-mode stop loss ──────────────────────────────────────────
        stop_loss_pct = STOP_LOSS_BY_MODE.get(mode, STOP_LOSS_BY_MODE["DEFAULT"])
        if pnl_pct <= stop_loss_pct:
            logger.warning(
                f"🛑 STOP_LOSS for {pos['symbol']} [{mode}]: {pnl_pct:+.1%} "
                f"(threshold={stop_loss_pct:.0%})"
            )
            return self._exit(address, "STOP_LOSS", pnl_pct, 1.0)

        # ── Drop velocity guard ─────────────────────────────────────────
        if age_s < DROP_VELOCITY_WINDOW_S and pnl_pct <= DROP_VELOCITY_PCT:
            logger.warning(
                f"⚡ VELOCITY EXIT for {pos['symbol']}: {pnl_pct:+.1%} in "
                f"{age_s:.0f}s (limit={DROP_VELOCITY_PCT:.0%} / {DROP_VELOCITY_WINDOW_S}s)"
            )
            return self._exit(address, "VELOCITY_STOP", pnl_pct, 1.0)

        # ── Time-based exit ─────────────────────────────────────────────────
        if age_s >= MAX_HOLD_SECONDS:
            return self._exit(address, "TIMEOUT", pnl_pct, 1.0)

        # ── Take-profit ladder ──────────────────────────────────────────────
        if not pos["tp1_triggered"] and pnl_pct >= TAKE_PROFIT_1_PCT:
            pos["tp1_triggered"]   = True
            pos["trailing_active"] = True
            logger.info(f"TP1 hit for {pos['symbol']}: {pnl_pct:+.1%} — closing 50%")
            return self._partial_exit(address, "TP1", pnl_pct, 0.50)

        if pos["tp1_triggered"] and not pos["tp2_triggered"] and pnl_pct >= TAKE_PROFIT_2_PCT:
            pos["tp2_triggered"] = True
            logger.info(f"TP2 hit for {pos['symbol']}: {pnl_pct:+.1%} — closing 75% of remainder")
            return self._partial_exit(address, "TP2", pnl_pct, 0.75)

        # ── Trailing stop (active after TP1) ────────────────────────────────
        if pos["trailing_active"]:
            trail_threshold = (peak - entry) / entry - TRAILING_STOP_PCT
            if pnl_pct < trail_threshold:
                return self._exit(address, "TRAIL_STOP", pnl_pct, 1.0)

        return None   # hold

    def _exit(self, address: str, reason: str, pnl_pct: float, close_pct: float) -> dict:
        self.positions.pop(address, None)
        if pnl_pct < 0:
            self._last_loss_time     = datetime.utcnow()
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        hist = self._token_history.setdefault(address, {"exits": 0, "last_exit": None})
        hist["exits"]    += 1
        hist["last_exit"] = datetime.utcnow()
        logger.info(
            f"Token {address[:8]}… exit #{hist['exits']} | reason={reason} | pnl={pnl_pct:+.1%} | "
            f"blacklisted for {TOKEN_BLACKLIST_SECS//60} min"
        )
        self._save_history()
        return {"action": "SELL", "close_pct": close_pct, "reason": reason, "pnl_pct": pnl_pct}

    def _partial_exit(self, address: str, reason: str, pnl_pct: float, close_pct: float) -> dict:
        return {"action": "SELL_PARTIAL", "close_pct": close_pct, "reason": reason, "pnl_pct": pnl_pct}

    # ── Guards ──────────────────────────────────────────────────────────────

    def is_in_cooldown(self) -> bool:
        if self._last_loss_time is None:
            return False
        return (datetime.utcnow() - self._last_loss_time).total_seconds() < COOLDOWN_SECONDS

    def at_max_positions(self) -> bool:
        return len(self.positions) >= MAX_OPEN_POSITIONS

    def already_open(self, address: str) -> bool:
        return address in self.positions

    def is_token_blacklisted(self, address: str) -> bool:
        hist = self._token_history.get(address)
        if not hist:
            return False
        if hist["exits"] >= MAX_ENTRIES_PER_TOKEN:
            logger.debug(f"Token {address[:8]}… blocked: hit max {MAX_ENTRIES_PER_TOKEN} entries/session")
            return True
        if hist["last_exit"]:
            elapsed = (datetime.utcnow() - hist["last_exit"]).total_seconds()
            if elapsed < TOKEN_BLACKLIST_SECS:
                remaining = int(TOKEN_BLACKLIST_SECS - elapsed)
                logger.debug(f"Token {address[:8]}… blacklisted for {remaining}s more")
                return True
        return False


class HybridStrategy:
    def __init__(self):
        self.current_mode = "SCANNING"
        self.risk         = RiskManager()

    # ── Entry analysis ──────────────────────────────────────────────────────

    def analyze(self, features: dict, predictions: dict) -> dict | None:
        """Return entry signal dict or None."""
        age          = features.get("age_seconds",        99999)
        liq          = features.get("liquidity_usd",          0)
        pump_prob    = predictions.get("pump_probability",      0)
        dump_risk    = predictions.get("dump_risk",             1)
        vol_momentum = features.get("volume_change_1m",        0)
        buy_pressure = features.get("buy_pressure_5m",       0.5)
        price_chg_5m = features.get("price_change_5m",         0)
        tx_velocity  = features.get("tx_velocity_per_hour",    0)
        liq_to_mcap  = features.get("liq_to_mcap",             0)
        address      = features.get("address",               "")
        symbol       = features.get("symbol",           "UNKNOWN")

        is_heuristic = predictions.get("is_heuristic", False)
        boost = 0.05 if is_heuristic else 0.0

        # ── Hard filters (instant reject) ───────────────────────────────────
        if liq < 2_000:                                     return None
        if dump_risk > 0.55:                                return None
        if liq_to_mcap < 0.02 and liq < 10_000:             return None
        if buy_pressure < 0.50:                             return None
        
        if pump_prob < MIN_PUMP_PROB:
            logger.debug(f"Skipping {symbol} — pump_prob {pump_prob:.2f} below floor {MIN_PUMP_PROB}")
            return None

        # ── Global guards ────────────────────────────────────────────────────
        if self.risk.is_in_cooldown():
            logger.debug("Skipping entry — in cooldown after loss")
            return None
        if self.risk.at_max_positions():
            logger.debug("Skipping entry — max open positions reached")
            return None
        if address and self.risk.already_open(address):
            return None
        if address and self.risk.is_token_blacklisted(address):
            return None

        # ── SNIPER mode: ultra-fresh token, high conviction ─────────────────
        if (age < 180
                and 40_000 < liq < 150_000     # 🛑 FIX: Avoid sub-$40k micro-pools entirely
                and pump_prob > 0.80 + boost   # 🛑 FIX: Demands 80% AI confidence
                and buy_pressure > 0.70        # 🛑 FIX: Demands 70% of volume is buys
                and vol_momentum > 1.5):
            self.current_mode = "SNIPER"
            size     = self._risk_size(liq, max_sol=0.10, liq_divisor=60_000) # 🛑 Cap risk at 0.10 SOL
            slippage = 15.0 if liq < 50_000 else 10.0
            return self._signal("BUY", size, slippage, "SNIPER")

        # ── MG (Momentum Grab): trending token ──────────────────────────────
        if (pump_prob > 0.78 + boost           # 🛑 FIX: Raised to 78% confidence
                and vol_momentum > 2.0
                and price_chg_5m > 5
                and tx_velocity > 100          # 🛑 FIX: Require faster tx velocity
                and buy_pressure > 0.65        # 🛑 FIX: Require higher buyer dominance
                and liq > 15_000):             # 🛑 FIX: Raised min liq to 15k
            self.current_mode = "MG"
            size = self._risk_size(liq, max_sol=0.20, liq_divisor=120_000)
            return self._signal("BUY", size, 5.0, "MG")

        # ── HWR (High Win-Rate): conservative, quality setups only ───────────
        if (pump_prob > 0.82 + boost
                and dump_risk < 0.20
                and buy_pressure > 0.65
                and liq > 25_000               # 🛑 FIX: Raised from 20k
                and vol_momentum > 1.0
                and price_chg_5m > 2):
            self.current_mode = "HWR"
            size = self._risk_size(liq, max_sol=0.12, liq_divisor=250_000)
            return self._signal("BUY", size, 2.0, "HWR")

        self.current_mode = "SCANNING"
        return None

    # ── Exit analysis ───────────────────────────────────────────────────────

    def check_exit(self, address: str, current_price: float) -> dict | None:
        """Call every tick for each open position. Returns exit signal or None."""
        return self.risk.update_position(address, current_price)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _risk_size(self, liq: float, max_sol: float, liq_divisor: float) -> float:
        """Scale size by liquidity. Triple-capped: per-mode max, absolute max, minimum."""
        raw    = liq / liq_divisor
        capped = min(raw, max_sol, ABSOLUTE_MAX_SOL)
        return max(0.01, round(capped, 3))

    def _signal(self, action: str, size: float, slippage: float, mode: str) -> dict:
        self.current_mode = mode
        return {
            "action":    action,
            "size_sol":  size,
            "slippage":  slippage,
            "mode":      mode,
            "timestamp": datetime.utcnow().isoformat(),
        }