#!/usr/bin/env python3
"""
Solana Meme Coin Trader — v1.0
================================
Built on MemeSignalEngine v1.0.

Usage:
  python solana_meme_trader.py --mode paper --balance 1000
  python solana_meme_trader.py --mode live  --balance 500

THIS IS HIGH RISK. READ BEFORE USING:
  - Every trade risks up to 12% of the position (memes are volatile)
  - Rug pulls can take a token to zero instantly — position caps are HARD
  - The daily loss circuit breaker exists for a reason — respect it
  - Paper trade first. Seriously.

WHAT THIS BOT DOES:
  - Scans boosted + new meme listings every 60 seconds
  - Applies 8 meme-specific hard filters (age, mcap, rug flags, etc.)
  - Enters on volume explosion + momentum confirmation
  - Exits at ATR-based TP1/TP2 or trailing stop
  - Emergency dump detection: exits if price drops 12% from peak fast
  - Hard cap: max $150 per trade, max 3 concurrent positions
  - Daily loss limit: 8% of starting equity — halts for the day if hit

POSITION SIZING:
  - Base: 8% of portfolio per trade
  - Hard cap: $150 absolute maximum (regardless of portfolio size)
  - ATR scaled: high-volatility tokens get smaller allocation
  - Compounding: +3% after 3 consecutive wins, -5% on any loss

DISCOVERY:
  - Prioritises NEW LISTINGS and BOOSTED tokens (higher meme upside)
  - Requires: liq $50k-$10M, age >2h, mcap <$50M, volume >$20k/24h
  - Scans up to 15 tokens simultaneously
  - Refresh every 60s (meme opportunities come and go fast)
"""

import time
import argparse
from datetime import datetime, date
from typing import Dict, Optional, List, Tuple

from solana_trading_agent import SolanaTradingAgent, TradingMode, TOKENS
from trending_tokens import EnhancedTrendingTokenDetector, AutoTokenSelector
from meme_signal_engine import MemeSignalEngine, _calc_rsi


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

MAX_POSITION_USD      = 150.0   # absolute hard cap per trade
BASE_POSITION_PCT     = 0.08    # 8% of portfolio base size
MAX_ATR_FOR_FULL_SIZE = 0.08    # ATR above 8% = scale down position
DAILY_LOSS_LIMIT_PCT  = 8.0     # halt if daily loss >= 8%
MAX_CONCURRENT        = 5       # max 3 meme positions at once
WIN_STREAK_REQ        = 3       # wins before compounding up
WIN_STEP              = 0.03    # +3% per compounding step
LOSS_STEP             = 0.05    # -5% on any loss
MAX_MULT              = 1.80
MIN_MULT              = 0.40
DUMP_CANDLES          = 3       # peak-to-dump check window
MIN_PROB              = 55.0    # minimum probability to trade
COOLDOWN_AFTER_STOP   = 600     # 10 min cooldown after stop on a token
EVICTION_FAIL_LIMIT   = 5       # evict a token after this many consecutive hard-fail cycles
EVICTION_COOLDOWN     = 900     # 15 min before an evicted token can re-enter watchlist


# ─────────────────────────────────────────────────────────────────────────────
# POSITION SIZER
# ─────────────────────────────────────────────────────────────────────────────

class MemeSizer:
    """
    Meme-specific position sizer.
    Enforces hard $ cap, ATR scaling, and win-streak compounding.
    """

    def __init__(self):
        self._mult             = 1.0
        self._consecutive_wins = 0

    def get_size(self, prob: float, atr_pct: float,
                 total: float, available_usdc: float) -> Tuple[float, str]:
        """Returns (usdc_amount, label). 0.0 if below minimum probability."""
        if prob < MIN_PROB:
            return 0.0, "SKIP"

        # Base: fixed % of portfolio, adjusted by multiplier
        base_usdc = total * BASE_POSITION_PCT * self._mult

        # ATR scale: reduce size proportionally if volatility is extreme
        # This prevents the stop being so wide that one trade wipes a chunk
        atr_factor = 1.0
        if atr_pct > MAX_ATR_FOR_FULL_SIZE:
            atr_factor = MAX_ATR_FOR_FULL_SIZE / atr_pct
            atr_factor = max(atr_factor, 0.35)   # floor at 35% of base

        scaled_usdc = base_usdc * atr_factor

        # Hard $ cap — protect against portfolio concentration
        capped_usdc = min(scaled_usdc, MAX_POSITION_USD)

        # Never use more than 90% of available USDC
        final_usdc = min(capped_usdc, available_usdc * 0.90)

        label = "CAP" if scaled_usdc > MAX_POSITION_USD else "STD"
        return final_usdc, label

    def record_win(self):
        self._consecutive_wins += 1
        if self._consecutive_wins >= WIN_STREAK_REQ:
            old = self._mult
            self._mult = min(self._mult + WIN_STEP, MAX_MULT)
            self._consecutive_wins = 0
            if self._mult != old:
                print(f"  [compound] {WIN_STREAK_REQ} wins → "
                      f"sizer {old:.2f}x → {self._mult:.2f}x 🚀")

    def record_loss(self):
        self._consecutive_wins = 0
        old = self._mult
        self._mult = max(self._mult - LOSS_STEP, MIN_MULT)
        if self._mult != old:
            print(f"  [compound] Loss → sizer {old:.2f}x → {self._mult:.2f}x")

    @property
    def multiplier(self) -> float:
        return self._mult

    @property
    def consecutive_wins(self) -> int:
        return self._consecutive_wins


# ─────────────────────────────────────────────────────────────────────────────
# EQUITY TRACKER
# ─────────────────────────────────────────────────────────────────────────────

class EquityTracker:
    def __init__(self, starting: float):
        self._hwm              = starting
        self._day_start_equity = starting

    def update(self, equity: float):
        if equity > self._hwm:
            self._hwm = equity

    def reset_day(self, equity: float):
        self._day_start_equity = equity

    def daily_loss_pct(self, equity: float) -> float:
        if self._day_start_equity <= 0:
            return 0.0
        return max(0.0, (self._day_start_equity - equity) / self._day_start_equity * 100)

    def drawdown_pct(self, equity: float) -> float:
        if self._hwm <= 0:
            return 0.0
        return max(0.0, (self._hwm - equity) / self._hwm * 100)

    @property
    def hwm(self) -> float:
        return self._hwm


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TRADER
# ─────────────────────────────────────────────────────────────────────────────

class MemeCoinTrader:

    REGIME_MIN = 0   # lower than established tokens — memes trade in any market

    def __init__(self, agent: SolanaTradingAgent, auto_discover: bool = True):
        self.agent         = agent
        self.auto_discover = auto_discover
        self.running       = False
        self.engine        = MemeSignalEngine()

        starting           = agent.portfolio.get_total_value()
        self.sizer         = MemeSizer()
        self.tracker       = EquityTracker(starting)

        self.min_soft_score = 2   # was 3 — lowered because vol signals score 0 in low-vol markets,
                                   # leaving only 5 non-volume signals available (rsi, macd, room,
                                   # ema_vel, velocity). Min 2 ensures at least 2 of these confirm.

        # Exit state
        self.position_peaks:    Dict[str, float]    = {}
        self.position_entry:    Dict[str, float]     = {}
        self.position_atr:      Dict[str, float]     = {}
        self.position_peak_ts:  Dict[str, float]     = {}  # timestamp of peak
        self.tp1_hit:           Dict[str, bool]      = {}
        self.tp2_hit:           Dict[str, bool]      = {}
        self.tp_lockout:        Dict[str, float]     = {}
        self.tp_lockout_secs    = 120

        # Risk controls
        self.max_trades_per_day  = 60
        self.trade_cooldown_secs = 30    # 30s between trades on same token
        self.min_live_candles    = 15    # lower than established — memes are newer

        self.trades_today  = 0
        self.day_start     = date.today()
        self.halted_today  = False

        self.last_trades:   Dict[str, datetime] = {}
        self.sl_strikes:    Dict[str, int]       = {}
        self.sl_blacklist:  set                  = set()
        self.sl_cooldown:   Dict[str, float]     = {}  # per-token cooldown after stop

        # Auto-eviction: remove dead/quiet tokens from watchlist
        self.eviction_fails:     Dict[str, int]   = {}  # consecutive hard-fail cycles
        self.eviction_blacklist: Dict[str, float] = {}  # sym -> eviction timestamp

        # Discovery
        self.refresh_interval        = 30    # every 60s — meme opportunities are fleeting
        self.last_refresh            = 0
        self.detector                = EnhancedTrendingTokenDetector()
        self.selector                = AutoTokenSelector(self.detector)
        self.token_metadata:          Dict[str, Dict] = {}

        self._current_score     = 50.0
        self.session_trades:    List[Dict] = []

    # ─────────────────────────────────────────────────────────────────────────
    # REGIME CHECK
    # ─────────────────────────────────────────────────────────────────────────

    def _check_regime(self, tokens_analysis: Dict) -> Tuple[bool, float, str]:
        analyzer = getattr(self.agent, "market_analyzer", None)
        if not analyzer:
            return True, 50.0, "no analyzer"

        if not tokens_analysis:
            cached = getattr(analyzer, "_smoothed_score", None)
            if cached is not None:
                self._current_score = cached
                lbl = "🟢" if cached >= 70 else ("🟡" if cached >= 50 else "🔴")
                return cached >= self.REGIME_MIN, cached, f"  [regime] {lbl} ({cached:.0f})"
            return True, 50.0, "  [regime] no data"

        status, reason, details = analyzer.analyze(tokens_analysis)
        score = details["overall_score"]
        self._current_score = score
        self.selector.set_regime(score)

        if score < self.REGIME_MIN:
            return False, score, f"⏸  regime {score:.0f} < {self.REGIME_MIN} — cash only"

        lbl = "🟢 BULLISH" if score >= 70 else "🟡 NEUTRAL"
        print(f"  [regime] {lbl} ({score:.0f})  sizer×{self.sizer.multiplier:.2f}")
        return True, score, f"✅ regime {score:.0f}"

    # ─────────────────────────────────────────────────────────────────────────
    # DAILY RESET + CIRCUIT BREAKER
    # ─────────────────────────────────────────────────────────────────────────

    def _check_daily_reset(self, equity: float):
        today = date.today()
        if today != self.day_start:
            self.day_start    = today
            self.trades_today = 0
            self.halted_today = False
            self.tracker.reset_day(equity)
            print(f"\n  [day] New day — counters reset")

    def _check_circuit_breaker(self, equity: float) -> bool:
        if self.halted_today:
            return True
        loss = self.tracker.daily_loss_pct(equity)
        if loss >= DAILY_LOSS_LIMIT_PCT:
            self.halted_today = True
            print(f"\n  ⛔ CIRCUIT BREAKER: Daily loss {loss:.1f}% — halted for today")
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # DISCOVERY — meme-focused
    # ─────────────────────────────────────────────────────────────────────────

    def refresh_tokens(self):
        try:
            print("\n[discover] Scanning for meme setups...")
            # Prioritise NEW LISTINGS and BOOSTED tokens for meme plays
            self.selector.preferences.update({
                "min_liquidity":        50_000,
                "min_volume":           20_000,
                "max_tokens":           15,
                "prefer_rising":        True,       # memes: catch momentum
                "max_price_change_24h": 9999,       # no cap — 5000% moves are the point
                "prioritize_boosted":   True,       # boosted = project spending money = signal
                "min_score":            25.0,
            })

            selected = self.selector.get_token_symbols()

            # Always show full trending table including new listings
            trending = self.detector.get_trending_tokens(
                min_liquidity=50_000, min_volume_24h=20_000,
                max_tokens=20, prioritize_boosted=True)
            if trending:
                self.detector.display_trending(trending)

            if not selected:
                print("[discover] No tokens pass meme criteria — waiting")
                self.last_refresh = time.time()
                return

            print("\n[discover] MEME CANDIDATES:")
            print("-" * 65)
            added = skipped_rsi = skipped_liq = skipped_para = 0

            for token in selected:
                sym       = token["symbol"]
                addr      = token["address"]
                pair_addr = token.get("pair_address", "")
                liq       = token.get("liquidity_usd", 0)
                ch24      = token.get("price_change_24h", 0)
                ch1       = token.get("price_change_h1", 0)
                score_t   = token.get("score", 0)
                quality   = token.get("quality_indicator", "")
                boosted   = token.get("is_boosted", False)
                mcap      = token.get("market_cap_usd", 0)
                age_h     = token.get("age_hours", None)

                if sym in self.agent.watched_tokens:
                    continue

                # Skip eviction-blacklisted tokens until cooldown expires
                evict_ts = self.eviction_blacklist.get(sym)
                if evict_ts is not None:
                    remaining = EVICTION_COOLDOWN - (time.time() - evict_ts)
                    if remaining > 0:
                        print(f"  [skip] {sym}: evicted — cooldown {remaining/60:.0f}m remaining")
                        continue
                    else:
                        del self.eviction_blacklist[sym]  # cooldown expired — allow re-entry

                # Meme-specific liq bounds
                if liq < 50_000:
                    print(f"  [skip] {sym}: liq ${liq/1000:.0f}k — rug risk")
                    skipped_liq += 1
                    continue
                if liq > 10_000_000:
                    print(f"  [skip] {sym}: liq ${liq/1e6:.1f}M — pump already in")
                    skipped_liq += 1
                    continue
                if mcap and mcap > 50_000_000:
                    print(f"  [skip] {sym}: mcap ${mcap/1e6:.0f}M — too big for meme play")
                    skipped_liq += 1
                    continue

                if sym not in TOKENS:
                    TOKENS[sym] = addr
                self.agent.add_token(sym, addr)

                # Store meme metadata including age and mcap
                self.token_metadata[sym] = {
                    "is_boosted":           boosted,
                    "quality_indicator":    quality,
                    "score":                score_t,
                    "price_change_24h":     ch24,
                    "price_change_h1":      ch1,
                    "liquidity_usd":        liq,
                    "liquidity_change_pct": token.get("liquidity_change_pct", 0.0),
                    "market_cap_usd":       mcap,
                    "age_hours":            age_h,
                    "volume_24h_usd":       token.get("volume_24h_usd", 0),
                }

                print(f"  Fetching {sym} {'🚀[BOOST]' if boosted else ''}...")
                hist, is_real = self.detector.fetch_historical_prices(
                    pair_addr, n_points=500, token_info=token)

                if not hist:
                    print(f"  [skip] No price history")
                    if sym in self.agent.watched_tokens:
                        self.agent.watched_tokens.remove(sym)
                    self.token_metadata.pop(sym, None)
                    continue

                # Skip already-overbought at discovery
                rsi_val = _quick_rsi(hist)
                if rsi_val and rsi_val > 72:
                    print(f"  [skip] RSI {rsi_val:.0f} > 72 — already pumped")
                    if sym in self.agent.watched_tokens:
                        self.agent.watched_tokens.remove(sym)
                    self.token_metadata.pop(sym, None)
                    skipped_rsi += 1
                    continue

                self.agent.prefill_price_history(sym, hist)
                buf = self.agent.price_history[sym]
                buf["live_points"] = len(hist) if is_real else 0
                status_s = f"[OK] {len(hist)} candles" if is_real else "[~] synthetic"

                age_s = f"{age_h:.1f}h" if age_h else "age?"
                mcap_s = f"${mcap/1000:.0f}k" if mcap else "mcap?"
                rsi_s  = f"{rsi_val:.0f}" if rsi_val else "?"
                print(f"  → {added+1}. {sym:<10} {quality:<10}  "
                      f"24h={ch24:+.0f}%  liq=${liq/1000:.0f}k  "
                      f"age={age_s}  mcap={mcap_s}  RSI={rsi_s}  {status_s}")
                added += 1

            print("-" * 65)
            print(f"[discover] Added:{added}  SkippedRSI:{skipped_rsi}  "
                  f"SkippedLiq:{skipped_liq}  "
                  f"Watching:{len(self.agent.watched_tokens)}\n")
            self.last_refresh = time.time()

        except Exception as e:
            import traceback
            print(f"[discover] Error: {e}")
            traceback.print_exc()
            self.last_refresh = time.time() - self.refresh_interval + 30

    # ─────────────────────────────────────────────────────────────────────────
    # ENTRY GATE
    # ─────────────────────────────────────────────────────────────────────────

    def _can_enter(self, token: str, analysis: Dict) -> bool:
        if token in self.sl_blacklist:
            return False
        if analysis.get("hard_fail"):
            return False

        # Per-token stop cooldown (10 min after a stop on this specific token)
        if token in self.sl_cooldown:
            if time.time() < self.sl_cooldown[token]:
                rem = int(self.sl_cooldown[token] - time.time())
                print(f"  [skip] stop cooldown {rem}s")
                return False
            del self.sl_cooldown[token]

        prob = analysis.get("prob_score", 0.0)
        if prob < MIN_PROB:
            print(f"  [skip] prob {prob:.0f} < {MIN_PROB:.0f}")
            return False

        if token in self.tp_lockout:
            if time.time() < self.tp_lockout[token]:
                rem = int(self.tp_lockout[token] - time.time())
                print(f"  [skip] TP lockout {rem}s")
                return False
            del self.tp_lockout[token]

        if token in self.last_trades:
            elapsed = (datetime.now() - self.last_trades[token]).total_seconds()
            if elapsed < self.trade_cooldown_secs:
                print(f"  [skip] cooldown {int(self.trade_cooldown_secs - elapsed)}s")
                return False

        if date.today() != self.day_start:
            self.trades_today = 0
        if self.trades_today >= self.max_trades_per_day:
            print(f"  [skip] daily limit {self.trades_today}/{self.max_trades_per_day}")
            return False

        if token in self.agent.portfolio.positions:
            print(f"  [skip] already holding")
            return False

        if len(self.agent.portfolio.positions) >= MAX_CONCURRENT:
            print(f"  [skip] max {MAX_CONCURRENT} concurrent meme positions")
            return False

        total = self.agent.portfolio.get_total_value()
        if self.agent.portfolio.usdc_balance < 15:
            print(f"  [skip] insufficient USDC")
            return False

        if analysis.get("buy_pts", 0) < self.min_soft_score:
            print(f"  [skip] soft {analysis.get('buy_pts',0)}/{self.min_soft_score}")
            return False

        rr = analysis.get("rr_ratio", 0.0)
        if rr < 1.5:
            print(f"  [skip] R:R {rr:.2f} < 1.5 after 2% fees")
            return False

        # Reject if sell divergence just detected
        if analysis.get("sell_divergence", False):
            print(f"  [skip] sell divergence — insiders distributing")
            return False

        return True

    # ─────────────────────────────────────────────────────────────────────────
    # EXIT MONITORING — meme-adapted
    # ─────────────────────────────────────────────────────────────────────────

    def _monitor_exits(self, current_analyses: Dict):
        for token, position in list(self.agent.portfolio.positions.items()):
            pnl      = position.pnl_percentage
            analysis = current_analyses.get(token, {})

            # Track peak
            if token not in self.position_peaks or pnl > self.position_peaks[token]:
                self.position_peaks[token]   = pnl
                self.position_peak_ts[token] = time.time()
            peak    = self.position_peaks[token]
            peak_ts = self.position_peak_ts.get(token, time.time())

            # ATR levels (locked at entry, recomputed as fallback)
            atr_pct    = self.position_atr.get(token) or analysis.get("atr_pct", 0.05)
            stop_pct   = min(MemeSignalEngine.STOP_ATR_MULT  * atr_pct, MemeSignalEngine.MAX_STOP_PCT) * 100
            tp1_pct    = MemeSignalEngine.TP1_ATR_MULT   * atr_pct * 100
            tp2_pct    = MemeSignalEngine.TP2_ATR_MULT   * atr_pct * 100
            trail_pct  = MemeSignalEngine.TRAIL_ATR_MULT * atr_pct * 100

            # ── DUMP DETECTION — fast drop from peak ─────────────────────────
            # If price drops >12% from peak AND it happened fast = dump, exit NOW
            drop_from_peak = peak - pnl
            time_at_peak   = time.time() - peak_ts
            if (peak > tp1_pct * 0.5   # only check after token has moved meaningfully
                    and drop_from_peak >= MemeSignalEngine.DUMP_DROP_PCT * 100
                    and time_at_peak < 180):   # happened in < 3 minutes
                print(f"\n  🚨 DUMP DETECTED {token}  "
                      f"Peak:{peak:+.1f}%  Now:{pnl:+.1f}%  "
                      f"Drop:{drop_from_peak:.1f}% in {time_at_peak:.0f}s — EXIT NOW")
                trade = self.agent.execute_swap(token, "USDC", position.amount)
                if trade:
                    self.last_trades[token] = datetime.now()
                    self._record(token, "DUMP_EXIT", pnl, position.pnl)
                    self.sizer.record_loss() if pnl < 0 else self.sizer.record_win()
                    self._cleanup_position(token)
                continue

            # ── HARD STOP ────────────────────────────────────────────────────
            if pnl <= -stop_pct:
                print(f"\n  ❌ STOP {token}  P&L:{pnl:+.1f}%  "
                      f"ATR-stop:{-stop_pct:.1f}%  ATR={atr_pct*100:.1f}%")
                trade = self.agent.execute_swap(token, "USDC", position.amount)
                if trade:
                    self.last_trades[token]   = datetime.now()
                    self.sl_strikes[token]    = self.sl_strikes.get(token, 0) + 1
                    self.sl_cooldown[token]   = time.time() + COOLDOWN_AFTER_STOP
                    if self.sl_strikes[token] >= 2:
                        self.sl_blacklist.add(token)
                        print(f"  🚫 Blacklisted {token} (2 stops)")
                    self._record(token, "STOP", pnl, position.pnl)
                    self.sizer.record_loss()
                    self._cleanup_position(token)
                continue

            # ── TP1 — sell 60% ───────────────────────────────────────────────
            if pnl >= tp1_pct and not self.tp1_hit.get(token, False):
                sell_amt = position.amount * MemeSignalEngine.TP1_AMOUNT
                print(f"\n  💰 TP1 {token}  P&L:{pnl:+.1f}%  "
                      f"ATR-TP1:{tp1_pct:.1f}%  Locking {MemeSignalEngine.TP1_AMOUNT*100:.0f}%")
                trade = self.agent.execute_swap(token, "USDC", sell_amt)
                if trade:
                    self.last_trades[token] = datetime.now()
                    self.tp1_hit[token]     = True
                    self._record(token, "TP1", pnl, position.pnl * MemeSignalEngine.TP1_AMOUNT)
                continue

            # ── TP2 — sell remainder ─────────────────────────────────────────
            if (pnl >= tp2_pct and self.tp1_hit.get(token)
                    and not self.tp2_hit.get(token, False)):
                print(f"\n  🚀💰 TP2 {token}  P&L:{pnl:+.1f}%  "
                      f"ATR-TP2:{tp2_pct:.1f}%  Exiting remainder")
                trade = self.agent.execute_swap(token, "USDC", position.amount)
                if trade:
                    self.last_trades[token] = datetime.now()
                    self.tp2_hit[token]     = True
                    self.tp_lockout[token]  = time.time() + self.tp_lockout_secs
                    self._record(token, "TP2", pnl, position.pnl)
                    self.sizer.record_win()
                    self._cleanup_position(token)
                continue

            # ── TRAILING STOP (ATR-based, after TP1) ─────────────────────────
            if peak >= tp1_pct:
                floor = peak - trail_pct
                if pnl <= floor:
                    print(f"\n  🏁 TRAIL {token}  "
                          f"Peak:{peak:+.1f}%  Now:{pnl:+.1f}%  "
                          f"Floor:{floor:+.1f}%  Trail:{trail_pct:.1f}%")
                    trade = self.agent.execute_swap(token, "USDC", position.amount)
                    if trade:
                        self.last_trades[token] = datetime.now()
                        self.tp_lockout[token]  = time.time() + self.tp_lockout_secs
                        self._record(token, "TRAIL", pnl, position.pnl)
                        self.sizer.record_win() if pnl > 0 else self.sizer.record_loss()
                        self._cleanup_position(token)
                else:
                    print(f"  🏃 trail {token}  "
                          f"Peak:{peak:+.1f}%  Now:{pnl:+.1f}%  "
                          f"Floor:{floor:+.1f}%")

    def _cleanup_position(self, token: str):
        self.position_peaks.pop(token, None)
        self.position_peak_ts.pop(token, None)
        self.position_atr.pop(token, None)
        self.tp1_hit.pop(token, None)
        self.tp2_hit.pop(token, None)

    def _record(self, token: str, exit_type: str, pnl_pct: float, pnl_usd: float):
        self.session_trades.append({
            "token": token, "exit": exit_type,
            "pnl_pct": pnl_pct, "pnl_usd": pnl_usd,
            "timestamp": datetime.now(),
            "win": pnl_pct > 0,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # EXECUTE BUY
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_buy(self, token: str, analysis: Dict):
        prob    = analysis.get("prob_score", 0.0)
        cur     = analysis.get("current_price", 0.0)
        atr_pct = analysis.get("atr_pct", 0.05)
        rr      = analysis.get("rr_ratio", 0.0)
        rv      = analysis.get("relative_volume", 1.0)
        vol_lbl = analysis.get("volume_state", "?")
        vel     = analysis.get("velocity_5", 0.0)
        mult    = analysis.get("multiple_from_low", 1.0)
        if cur == 0:
            return

        total    = self.agent.portfolio.get_total_value()
        usdc_amt, size_label = self.sizer.get_size(
            prob, atr_pct, total, self.agent.portfolio.usdc_balance)

        if usdc_amt < 5:
            print(f"  [skip] size ${usdc_amt:.2f} too small")
            return

        detail = analysis.get("buy_pts_detail", {})
        flags  = "".join([
            "V" if detail.get("vol_explosion") else ("v" if detail.get("vol_spike") else "."),
            "P" if detail.get("velocity")  else ".",
            "R" if detail.get("rsi_rise")  else ".",
            "M" if detail.get("macd")      else ".",
            "X" if detail.get("room")      else ".",
            "E" if detail.get("ema_vel")   else ".",
            "A" if detail.get("vol_build") else ".",
        ])

        stop_pct  = min(MemeSignalEngine.STOP_ATR_MULT  * atr_pct, MemeSignalEngine.MAX_STOP_PCT) * 100
        tp1_pct   = MemeSignalEngine.TP1_ATR_MULT   * atr_pct * 100
        tp2_pct   = MemeSignalEngine.TP2_ATR_MULT   * atr_pct * 100

        boosted = self.token_metadata.get(token, {}).get("is_boosted", False)
        age_h   = self.token_metadata.get(token, {}).get("age_hours", None)

        print(f"\n  ══ 🚀 BUY MEME {token} {'🚀[BOOST]' if boosted else ''} ══")
        print(f"     Prob:       {prob:.0f}%  |  Score: {analysis.get('buy_pts',0)}/8  [{flags}]")
        print(f"     Size:       ${usdc_amt:.2f}  ({size_label})  sizer×{self.sizer.multiplier:.2f}")
        print(f"     Wins:       {self.sizer.consecutive_wins}/{WIN_STREAK_REQ}")
        print(f"     Price:      ${cur:.8f}")
        print(f"     Vol:        {vol_lbl}  Velocity: {vel:+.1f}%/5bars")
        print(f"     From low:   {mult:.1f}x  R:R: {rr:.2f}")
        print(f"     ATR:        {atr_pct*100:.1f}%  →  "
              f"Stop:{-stop_pct:.1f}%  TP1:+{tp1_pct:.1f}%  TP2:+{tp2_pct:.1f}%")
        if age_h:
            print(f"     Age:        {age_h:.1f}h")

        trade = self.agent.execute_swap("USDC", token, usdc_amt)
        if trade:
            self.last_trades[token]      = datetime.now()
            self.trades_today           += 1
            self.position_peaks[token]   = 0.0
            self.position_peak_ts[token] = time.time()
            self.position_atr[token]     = atr_pct
            self.tp1_hit[token]          = False
            self.tp2_hit[token]          = False
            print(f"  ✅ Executed")
        else:
            print(f"  ❌ Failed")

    # ─────────────────────────────────────────────────────────────────────────
    # SESSION STATS
    # ─────────────────────────────────────────────────────────────────────────

    def _print_stats(self):
        if not self.session_trades:
            return
        wins   = [t for t in self.session_trades if t["win"]]
        losses = [t for t in self.session_trades if not t["win"]]
        wr     = len(wins) / len(self.session_trades) * 100
        pnl    = sum(t["pnl_usd"] for t in self.session_trades)
        by_exit= {}
        for t in self.session_trades:
            by_exit[t["exit"]] = by_exit.get(t["exit"], 0) + 1

        print(f"\n  ── Meme Session Stats ────────────────────────────────")
        print(f"     Trades: {len(self.session_trades)}  "
              f"WR: {wr:.0f}%  ({len(wins)}W/{len(losses)}L)  "
              f"Net: ${pnl:+.2f}")
        if wins:
            print(f"     Avg win:  +{sum(t['pnl_pct'] for t in wins)/len(wins):.1f}%")
        if losses:
            print(f"     Avg loss:  {sum(t['pnl_pct'] for t in losses)/len(losses):.1f}%")
        if wins and losses:
            avg_w = sum(t["pnl_pct"] for t in wins) / len(wins)
            avg_l = abs(sum(t["pnl_pct"] for t in losses) / len(losses))
            if avg_l > 0:
                print(f"     Realised R:R: {avg_w/avg_l:.2f}")
        exits_str = "  ".join(f"{k}:{v}" for k, v in sorted(by_exit.items()))
        print(f"     Exits:  {exits_str}")
        print(f"     Sizer ×{self.sizer.multiplier:.2f}  "
              f"Win streak: {self.sizer.consecutive_wins}/{WIN_STREAK_REQ}  "
              f"EqHWM: ${self.tracker.hwm:.2f}")

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ─────────────────────────────────────────────────────────────────────────

    def run(self, update_interval: int = 15):
        self.running = True
        SKIP = {"USDC", "USDT", "USDS", "DAI", "USD1", "BUSD", "TUSD"}

        print("\n" + "=" * 70)
        print("  🚀 SOLANA MEME COIN TRADER  —  v1.0")
        print("=" * 70)
        print("\n⚠  HIGH RISK — read the docstring before live trading")
        print(f"\nRegime gate:      score >= {self.REGIME_MIN}  (relaxed for meme markets)")
        print(f"Fee assumption:   2% round trip (1% per leg on low-liq meme DEXs)")
        print(f"Circuit breaker:  halt if daily loss >= {DAILY_LOSS_LIMIT_PCT}%")
        print(f"\nEntry filters:")
        print(f"  Liq:     ${50}k - $10M  (sweet spot for meme moves)")
        print(f"  Age:     > 2h  (skip brand-new = rug risk)")
        print(f"  Mcap:    < $50M  (skip already-pumped)")
        print(f"  RSI:     {MemeSignalEngine.MIN_SOFT_SCORE}-70  (early stage only)")
        print(f"  Vol:     > 1.2x average (some interest required)")
        print(f"  R:R:     > 1.5 after 2% fees")
        print(f"\nATR-based exits:")
        print(f"  Stop:    {MemeSignalEngine.STOP_ATR_MULT}x ATR  (max {MemeSignalEngine.MAX_STOP_PCT*100:.0f}%)")
        print(f"  TP1:     {MemeSignalEngine.TP1_ATR_MULT}x ATR  (sell {MemeSignalEngine.TP1_AMOUNT*100:.0f}%)")
        print(f"  TP2:     {MemeSignalEngine.TP2_ATR_MULT}x ATR  (sell remainder)")
        print(f"  Trail:   {MemeSignalEngine.TRAIL_ATR_MULT}x ATR below peak  (after TP1)")
        print(f"  Dump:    exit if -{MemeSignalEngine.DUMP_DROP_PCT*100:.0f}% from peak in <3 min")
        print(f"\nPosition sizing:")
        print(f"  Base:    {BASE_POSITION_PCT*100:.0f}% of portfolio")
        print(f"  Cap:     ${MAX_POSITION_USD:.0f} absolute maximum")
        print(f"  Concurrent: max {MAX_CONCURRENT}")
        print(f"  Compounding: {WIN_STREAK_REQ} wins → +{WIN_STEP*100:.0f}% size")
        print(f"\nCycle: {update_interval}s  Discovery: every {self.refresh_interval}s")
        print(f"\nCtrl+C to stop")
        print("=" * 70)

        iteration = 0
        try:
            while self.running:
                iteration += 1
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n{'='*70}")
                print(f"Cycle #{iteration} — {now_str}")
                print(f"{'='*70}")

                if hasattr(self.agent, "market_analyzer"):
                    self.agent.market_analyzer.invalidate_cache()

                # Discovery
                if self.auto_discover:
                    if time.time() - self.last_refresh > self.refresh_interval:
                        self.refresh_tokens()

                # Market update
                print("\n[market] Updating prices...")
                self.agent.update_market_data()

                # Build analysis
                tokens_analysis: Dict[str, Dict] = {}
                for token in list(self.agent.watched_tokens):
                    if token in SKIP:
                        continue
                    buf      = self.agent.price_history.get(token, {})
                    live_pts = buf.get("live_points", 0)
                    prices   = buf.get("prices",  [])
                    volumes  = buf.get("volumes", [])
                    if live_pts < self.min_live_candles or not prices:
                        continue
                    meta     = self.token_metadata.get(token, {})
                    analysis = self.engine.analyze(
                        token, prices, volumes,
                        token_meta=meta,
                        min_soft_score=self.min_soft_score,
                    )
                    tokens_analysis[token] = analysis

                # Equity
                equity = self.agent.portfolio.get_total_value()
                self._check_daily_reset(equity)
                self.tracker.update(equity)
                dd           = self.tracker.drawdown_pct(equity)
                daily_loss   = self.tracker.daily_loss_pct(equity)
                halted       = self._check_circuit_breaker(equity)

                # Regime
                allowed, regime_score, regime_msg = self._check_regime(tokens_analysis)
                print(f"\n{regime_msg}")

                if halted:
                    print("  ⛔ Circuit breaker — monitoring exits only")
                    if self.agent.portfolio.positions:
                        self._monitor_exits(tokens_analysis)
                elif not allowed:
                    if self.agent.portfolio.positions:
                        print("[positions] Monitoring stops (regime paused)...")
                        self._monitor_exits(tokens_analysis)
                else:
                    if self.agent.portfolio.positions:
                        print("\n[positions] Monitoring exits...")
                        self._monitor_exits(tokens_analysis)

                    print("\n[analysis] Scanning meme tokens...")
                    qualified = []

                    for token, analysis in tokens_analysis.items():
                        meta      = self.token_metadata.get(token, {})
                        boosted   = meta.get("is_boosted", False)
                        hard_fail = analysis.get("hard_fail", False)
                        hard_msg  = analysis.get("hard_fail_reason", "")
                        soft      = analysis.get("buy_pts", 0)
                        prob      = analysis.get("prob_score", 0.0)
                        rv        = analysis.get("relative_volume", 1.0)
                        vel       = analysis.get("velocity_5", 0.0)
                        mult      = analysis.get("multiple_from_low", 1.0)
                        rr        = analysis.get("rr_ratio", 0.0)
                        atr       = analysis.get("atr_pct", 0.0) * 100
                        sell_div  = analysis.get("sell_divergence", False)
                        ts        = datetime.now().strftime("%H:%M:%S")

                        detail = analysis.get("buy_pts_detail", {})
                        flags  = "".join([
                            "V" if detail.get("vol_explosion") else ("v" if detail.get("vol_spike") else "."),
                            "P" if detail.get("velocity")  else ".",
                            "R" if detail.get("rsi_rise")  else ".",
                            "M" if detail.get("macd")      else ".",
                            "X" if detail.get("room")      else ".",
                            "E" if detail.get("ema_vel")   else ".",
                            "A" if detail.get("vol_build") else ".",
                        ])

                        boost_tag = "🚀" if boosted else "  "
                        sig       = analysis["signal"]
                        sd        = {"BUY": "BUY ", "SELL": "SELL", "HOLD": "HOLD"}.get(sig, "HOLD")
                        score_str = ("✗HARD" if hard_fail else
                                     f"{soft}/8[{flags}] p{prob:.0f}% R{rr:.1f}")
                        div_warn  = " ⚠DIV" if sell_div else ""

                        print(f"  [{ts}] {boost_tag}{token:<12}  "
                              f"${analysis['current_price']:<12.8f}  "
                              f"RSI:{analysis['rsi']:.0f}  {sd}  "
                              f"vol:{rv:.1f}x  vel:{vel:+.1f}%  "
                              f"{mult:.1f}x-low  ATR:{atr:.1f}%  "
                              f"{score_str}{div_warn}")

                        if hard_fail:
                            print(f"           ↳ {hard_msg[:90]}")
                            # Auto-eviction: count consecutive hard-fail cycles
                            self.eviction_fails[token] = self.eviction_fails.get(token, 0) + 1
                            fails = self.eviction_fails[token]
                            if fails >= EVICTION_FAIL_LIMIT:
                                if token in self.agent.watched_tokens:
                                    self.agent.watched_tokens.remove(token)
                                self.token_metadata.pop(token, None)
                                self.eviction_blacklist[token] = time.time()
                                self.eviction_fails.pop(token, None)
                                print(f"           ⏏  {token} evicted after {EVICTION_FAIL_LIMIT} hard-fails "
                                      f"— blacklisted {EVICTION_COOLDOWN//60}m")
                            else:
                                print(f"           ↳ [{fails}/{EVICTION_FAIL_LIMIT}] hard-fails "
                                      f"(evict at {EVICTION_FAIL_LIMIT})")
                        elif sig == "BUY":
                            self.eviction_fails.pop(token, None)  # reset counter on pass
                            qualified.append((token, analysis))
                        else:
                            self.eviction_fails.pop(token, None)  # HOLD — passed hard filters

                    # Execute — highest probability first
                    qualified.sort(key=lambda x: x[1].get("prob_score", 0), reverse=True)
                    for token, analysis in qualified:
                        if self._can_enter(token, analysis):
                            self._execute_buy(token, analysis)

                # Portfolio
                perf = self.agent.portfolio.get_performance()
                print(f"\n[portfolio]")
                print(f"  USDC:         ${self.agent.portfolio.usdc_balance:.2f}")
                print(f"  Total:        ${perf['current_value']:.2f}")
                print(f"  Return:       ${perf['total_return']:+.2f} ({perf['total_return_pct']:+.2f}%)")
                print(f"  HWM:          ${self.tracker.hwm:.2f}  DD: {dd:.1f}%")
                print(f"  Daily P&L:    {-daily_loss:+.2f}%  "
                      f"({'⛔ HALTED' if halted else f'limit {DAILY_LOSS_LIMIT_PCT}%'})")
                print(f"  Sizer ×:      {self.sizer.multiplier:.2f}  "
                      f"wins: {self.sizer.consecutive_wins}/{WIN_STREAK_REQ}")
                print(f"  Trades today: {self.trades_today}/{self.max_trades_per_day}")
                print(f"  Regime:       {self._current_score:.0f}/100")
                print(f"  Watching:     {len(self.agent.watched_tokens)} meme tokens")

                if self.agent.portfolio.positions:
                    print(f"\n  Open positions:")
                    for tok, pos in self.agent.portfolio.positions.items():
                        peak    = self.position_peaks.get(tok, 0)
                        atr_e   = self.position_atr.get(tok, 0.05)
                        stop_l  = -min(MemeSignalEngine.STOP_ATR_MULT * atr_e, MemeSignalEngine.MAX_STOP_PCT) * 100
                        tp1_l   =  MemeSignalEngine.TP1_ATR_MULT  * atr_e * 100
                        tp_flag = ("✓TP2" if self.tp2_hit.get(tok) else
                                   "✓TP1" if self.tp1_hit.get(tok) else "    ")
                        boosted_t = "🚀" if self.token_metadata.get(tok, {}).get("is_boosted") else "  "
                        print(f"    {boosted_t}{tok:<12}  "
                              f"P&L:{pos.pnl_percentage:+.2f}%  "
                              f"Peak:{peak:+.2f}%  "
                              f"{tp_flag}  "
                              f"Stop:{stop_l:.1f}%  TP1:+{tp1_l:.1f}%  "
                              f"ATR:{atr_e*100:.1f}%")

                if self.sl_blacklist:
                    print(f"\n  🚫 Blacklisted: {', '.join(self.sl_blacklist)}")

                self._print_stats()

                nxt = max(0, int(self.refresh_interval - (time.time() - self.last_refresh)))
                print(f"\n[wait] {update_interval}s  |  Discovery in {nxt//60}m{nxt%60}s")
                time.sleep(update_interval)

        except KeyboardInterrupt:
            print("\n\n[stop] Shutting down...")
            self.running = False
            print("\n" + "=" * 70)
            print("  🏁 MEME SESSION COMPLETE")
            print("=" * 70)
            self._print_stats()
            self.agent.show_portfolio()
            print()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _quick_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    gains  = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
    losses = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Solana Meme Coin Trader v1.0")
    parser.add_argument("--mode",             choices=["paper", "live"], default="paper")
    parser.add_argument("--wallet",           default="")
    parser.add_argument("--balance",          type=float, default=1000.0)
    parser.add_argument("--interval",         type=int,   default=15)   # 15s cycles
    parser.add_argument("--refresh-interval", type=int,   default=60)   # 60s discovery
    parser.add_argument("--no-auto-discover", action="store_true")
    parser.add_argument("--manual-tokens",    nargs="+")

    args = parser.parse_args()
    mode = TradingMode.LIVE if args.mode == "live" else TradingMode.PAPER

    wallet_instance = None
    if mode == TradingMode.LIVE:
        try:
            from wallet_integration import load_wallet_config, SolanaWallet
            cfg = load_wallet_config()
            if not cfg:
                print("[ERROR] No wallet config. Run: python setup_wallet.py --setup")
                return
            wallet_instance = SolanaWallet(cfg)
            sol_bal = wallet_instance.get_balance()
            if sol_bal < 0.01:
                if input(f"Low SOL ({sol_bal:.4f}). Continue? (yes/no): ").lower() not in ("yes","y"):
                    return
            print("\n⚠  MEME COIN TRADING IS EXTREMELY HIGH RISK")
            print("   Rug pulls, dumps, and 100% losses can and do happen.")
            print("   Only trade what you can afford to lose entirely.\n")
            if input("Type 'MEME' to confirm live meme trading: ") != "MEME":
                print("Cancelled.")
                return
        except ImportError:
            print("[ERROR] pip install solana solders base58")
            return
        except Exception as e:
            print(f"[ERROR] {e}")
            return

    agent = SolanaTradingAgent(mode, args.wallet, args.balance, wallet=wallet_instance)

    from market_condition_analyzer import MarketConditionAnalyzer
    agent.market_analyzer = MarketConditionAnalyzer()
    print("[market] MarketConditionAnalyzer v8 attached.")

    auto_discover = not args.no_auto_discover
    if not auto_discover and args.manual_tokens:
        for tok in args.manual_tokens:
            agent.add_token(tok.upper())

    trader = MemeCoinTrader(agent, auto_discover=auto_discover)
    trader.refresh_interval = args.refresh_interval

    if auto_discover:
        print("\n[discover] Initial meme token scan...")
        trader.refresh_tokens()

    print("\n[market] Warming up (15 ticks)...")
    for i in range(15):
        agent.update_market_data()
        if (i + 1) % 5 == 0:
            print(f"  {i+1}/15")
        time.sleep(1)
    print("[OK] Ready\n")

    trader.run(update_interval=args.interval)


if __name__ == "__main__":
    main()