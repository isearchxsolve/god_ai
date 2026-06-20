#!/usr/bin/env python3
"""
Meme Coin Signal Engine — v1.1
================================
Meme coins are NOT established tokens with noise. They are a completely
different instrument with different physics. This engine is built for that.

MEME COIN PHYSICS:
  - Moves are driven by narrative, not fundamentals
  - Price can go 2-10x in hours; it can also go to zero in minutes
  - Volume is the only honest signal — everything else lags
  - The edge is catching the EARLY PHASE of a pump, not the peak
  - The exit must be fast and rules-based — emotions will kill you

WHAT WORKS ON MEME COINS:
  1. Volume explosion detection — the single most predictive signal.
     A 5x+ volume spike on a meme coin is an institutional/whale accumulation
     event or the start of coordinated buying. This is the trigger.

  2. Early-stage momentum (not overbought RSI).
     RSI 45-65 on entry = early in the move.
     RSI >75 on entry = you are the exit liquidity. Don't.

  3. Price velocity — how fast is price moving RIGHT NOW.
     Memes that are moving fast tend to keep moving fast (momentum).
     Memes that stall after a spike are done.

  4. Not-yet-parabolic check.
     If price is already >3x from its 4h low, the easy money is gone.
     Wait for the retrace or find the next one.

  5. Liquidity SWEET SPOT — not too low, not too high.
     < $30k liq = rug risk, one trade moves the market
     > $10M liq = already on everyone's radar, pump is priced in
     $50k - $3M = the sweet spot for outsized meme moves

  6. Age filter — skip tokens under 2 hours old.
     New tokens in the first 2h have >50% rug rate on Solana.
     Wait for basic survival proof before entering.

  7. Sell pressure detection — is distribution happening?
     If buy pressure is falling while price is rising = insiders selling.
     Classic pump-and-dump fingerprint. Avoid.

FEES ARE BRUTAL ON MEME COINS:
  - 1% per leg is realistic for low-liquidity memes (wide spread)
  - Round trip = 2%. Your trade needs to make >2% just to break even.
  - ATR-based stops MUST be wide enough to survive noise but TP must be fast.
  - R:R minimum is 3:1 AFTER fees (higher bar than established tokens).

EXIT PHILOSOPHY:
  Meme coin profits evaporate faster than they appear.
  - TP1: +15%  (take 60% off — most memes don't go further)
  - TP2: +40%  (take the rest if it runs)
  - Trail: 8% below peak (generous — let rockets ride)
  - Stop: 3x ATR (wide — memes are noisy — but absolute max 12%)
  - Dump detection: if price drops >12% from peak in <3 candles = exit NOW
"""

from typing import List, Dict, Optional, Tuple
import math
import time


# ─────────────────────────────────────────────────────────────────────────────
# MEME COIN CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

MEME_FEE_PCT        = 0.020   # 2% round trip — realistic for meme liquidity
MEME_MIN_RR         = 1.2     # was 3.0 — mathematically IMPOSSIBLE with 7x/3x mults
MEME_ATR_PERIOD     = 10      # shorter ATR period — memes are fast
MEME_STOP_MULT      = 3.0     # 3x ATR stop — memes are noisy
MEME_MAX_STOP_PCT   = 0.12    # absolute stop cap: never risk >12%
MEME_TP1_MULT = 6.0
MEME_TP2_MULT = 12.0

MEME_TRAIL_MULT     = 3.5     # 3.5x ATR trail — generous on runners
MEME_DUMP_DROP_PCT = 0.08    # 12% drop from peak = dump detected, exit

# Liquidity bounds — the meme sweet spot
MEME_MIN_LIQ        = 50_000   # below this = rug risk
MEME_MAX_LIQ        = 10_000_000  # above this = pump likely over
MEME_IDEAL_LIQ_LOW  = 100_000
MEME_IDEAL_LIQ_HIGH = 3_000_000

# Volume explosion thresholds
MEME_VOL_EXPLOSION = 3.0
MEME_VOL_SPIKE = 1.6


# Minimum ATR — tokens quieter than this can never cover 2% fees
MEME_MIN_ATR_PCT    = 0.003   # 0.8% minimum price volatility to trade

# Age and market cap safety
MEME_MIN_AGE_HOURS  = 2.0     # skip tokens < 2h old
MEME_MAX_MCAP_USD   = 50_000_000   # skip tokens already > $50M mcap

# RSI — catch early, not late
MEME_MIN_RSI        = 35
MEME_MAX_RSI_ENTRY = 75      # stricter on memes — >70 = already pumped


class MemeSignalEngine:

    # ATR exit multipliers referenced by trader
    STOP_ATR_MULT  = MEME_STOP_MULT
    TP1_ATR_MULT   = MEME_TP1_MULT
    TP2_ATR_MULT   = MEME_TP2_MULT
    TRAIL_ATR_MULT = MEME_TRAIL_MULT
    TP1_AMOUNT     = 0.60     # sell 60% at TP1 — memes are fast, lock profits
    MAX_STOP_PCT   = MEME_MAX_STOP_PCT
    DUMP_DROP_PCT  = MEME_DUMP_DROP_PCT

    MIN_SOFT_SCORE = 3        # out of 8 meme-specific signals

    def __init__(self):
        pass

    # ─────────────────────────────────────────────────────────────────────────
    # ATR (short-window for meme speed)
    # ─────────────────────────────────────────────────────────────────────────

    def _calc_atr(self, prices: List[float]) -> float:
        """ATR as fraction of price. Uses short MEME_ATR_PERIOD for speed."""
        period = MEME_ATR_PERIOD
        if len(prices) < period + 1:
            if len(prices) < 3:
                return 0.05   # 5% default — memes are volatile
            tr = [abs(prices[i] - prices[i-1]) / prices[i-1]
                  for i in range(1, len(prices)) if prices[i-1] > 0]
            return sum(tr[-period:]) / len(tr[-period:]) if tr else 0.05
        tr = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices))]
        atr_raw = sum(tr[-period:]) / period
        cur = prices[-1]
        return atr_raw / cur if cur > 0 else 0.05

    # ─────────────────────────────────────────────────────────────────────────
    # VOLUME EXPLOSION DETECTION
    # ─────────────────────────────────────────────────────────────────────────

    def _volume_state(self, volumes: List[float]) -> Tuple[float, str]:
        """
        Returns (relative_volume, label).
        Pump-window contamination guard: if 20-bar MA > 3x the 100-bar baseline,
        the MA includes pump candles — use the 100-bar baseline instead.
        """
        if not volumes or len(volumes) < 5:
            return 1.0, "insufficient"
        ma = sum(volumes[-20:]) / min(20, len(volumes))
        if ma == 0:
            return 1.0, "zero_vol"
        if len(volumes) >= 100:
            ma100 = sum(volumes[-100:]) / 100
            if ma100 > 0 and ma > ma100 * 3:
                ma = ma100  # use long-run baseline as denominator
        rv = volumes[-1] / ma
        if rv >= MEME_VOL_EXPLOSION:
            label = f"🚀 EXPLOSION {rv:.1f}x"
        elif rv >= MEME_VOL_SPIKE:
            label = f"⚡ SPIKE {rv:.1f}x"
        elif rv >= 1.5:
            label = f"📈 ELEVATED {rv:.1f}x"
        else:
            label = f"😴 LOW {rv:.1f}x"
        return rv, label

    # ─────────────────────────────────────────────────────────────────────────
    # PRICE VELOCITY
    # ─────────────────────────────────────────────────────────────────────────

    def _price_velocity(self, prices: List[float], window: int = 5) -> float:
        """% price change over last `window` candles. Positive = accelerating up."""
        if len(prices) < window + 1:
            return 0.0
        prev = prices[-(window + 1)]
        if prev <= 0:
            return 0.0
        return (prices[-1] - prev) / prev * 100

    # ─────────────────────────────────────────────────────────────────────────
    # PARABOLIC CHECK — are we already in blow-off?
    # ─────────────────────────────────────────────────────────────────────────

    def _is_parabolic(self, prices: List[float], lookback: int = 60) -> Tuple[bool, float]:
        """
        Returns (is_parabolic, multiple_from_recent_low).
        If price is >3x the low of the last `lookback` bars = blow-off risk.
        """
        if len(prices) < lookback:
            lookback = len(prices)
        if lookback < 5:
            return False, 1.0
        window = prices[-lookback:]
        low    = min(window)
        if low <= 0:
            return False, 1.0
        multiple = prices[-1] / low
        return multiple > 3.0, multiple

    # ─────────────────────────────────────────────────────────────────────────
    # SELL PRESSURE DIVERGENCE
    # ─────────────────────────────────────────────────────────────────────────

    def _sell_divergence(self, prices: List[float], volumes: List[float]) -> bool:
        """
        Detect distribution: price rising but buy pressure falling.
        This is the classic pump-and-dump fingerprint.
        Returns True if divergence detected (danger = avoid or exit).
        """
        if len(prices) < 10 or len(volumes) < 10:
            return False

        # Price trend (last 10 bars)
        price_up = prices[-1] > prices[-10]

        # Volume trend — is volume declining as price rises?
        recent_vol = sum(volumes[-5:]) / 5
        prior_vol  = sum(volumes[-10:-5]) / 5
        vol_fading = recent_vol < prior_vol * 0.70

        # Buy pressure (close vs range approximation)
        pressures = []
        p = prices[-7:]
        for i in range(2, len(p)):
            h = max(p[i-2], p[i-1], p[i])
            l = min(p[i-2], p[i-1], p[i])
            rng = h - l
            if rng > 0:
                pressures.append((p[i] - l) / rng)
        pressure_falling = (sum(pressures) / len(pressures) < 0.40) if pressures else False

        return price_up and vol_fading and pressure_falling

    # ─────────────────────────────────────────────────────────────────────────
    # FEE-AWARE R:R CHECK (meme version — higher fee, wider stops)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_rr(self,
              atr_pct: float,
              prices: Optional[List[float]] = None,
              volumes: Optional[List[float]] = None
              ) -> Tuple[bool, float, str]:

        ignition_override = False

        # 🔥 ATR expansion detection (last 5 candles)
        if prices and len(prices) > 12:
            atr_now  = self._calc_atr(prices)
            atr_prev = self._calc_atr(prices[:-5])
            if atr_prev > 0:
                growth = (atr_now - atr_prev) / atr_prev
                if growth > 0.40:  # +40% expansion
                    ignition_override = True

        # 🔥 Volume ignition detection
        if volumes and len(volumes) > 10:
            rv, _ = self._volume_state(volumes)
            if rv >= 1.8:
                ignition_override = True

        # ATR floor
        if atr_pct < MEME_MIN_ATR_PCT and not ignition_override:
            return False, 0.0, (
                f"ATR {atr_pct*100:.2f}% < {MEME_MIN_ATR_PCT*100:.1f}% min — "
                f"too quiet (no ignition)"
            )

        if atr_pct <= 0:
            return False, 0.0, "atr=0"

        stop_pct = min(MEME_STOP_MULT * atr_pct, MEME_MAX_STOP_PCT)
        tp1_pct  = MEME_TP1_MULT * atr_pct
        fee      = MEME_FEE_PCT

        risk   = stop_pct + fee
        reward = tp1_pct  - fee

        if risk <= 0 or reward <= 0:
            return False, 0.0, "no edge after fees"

        rr = reward / risk
        ok = rr >= MEME_MIN_RR

        msg = f"R:R={rr:.2f} (fee={fee*100:.0f}%)"
        if ignition_override:
            msg += " [IGNITION]"

        return ok, rr, msg


    # ─────────────────────────────────────────────────────────────────────────
    # HARD FILTERS (meme-specific)
    # ─────────────────────────────────────────────────────────────────────────

    def _check_liquidity(self, meta: Dict) -> Tuple[bool, str]:
        liq = meta.get("liquidity_usd", 0)
        if liq < MEME_MIN_LIQ:
            return False, f"liq ${liq/1000:.0f}k < ${MEME_MIN_LIQ/1000:.0f}k — rug risk"
        if liq > MEME_MAX_LIQ:
            return False, f"liq ${liq/1e6:.1f}M > ${MEME_MAX_LIQ/1e6:.0f}M — pump priced in"
        # Liquidity drop = LP withdrawing = potential rug setup
        liq_drop = meta.get("liquidity_change_pct", 0.0)
        if liq_drop < -5.0:
            return False, f"liq drop {liq_drop:.1f}% — LP withdrawing"
        return True, f"liq ${liq/1000:.0f}k (sweet spot)"

    def _check_age(self, meta: Dict) -> Tuple[bool, str]:
        """
        Token age in hours — skip very new tokens (rug risk highest in first 2h).
        Age is approximated from pair_created_at in meta if available.
        """
        age_hours = meta.get("age_hours", None)
        if age_hours is None:
            # No age data — allow but note it
            return True, "age unknown"
        if age_hours < MEME_MIN_AGE_HOURS:
            return False, (f"age {age_hours:.1f}h < {MEME_MIN_AGE_HOURS}h — "
                           f"too new, rug risk high")
        return True, f"age {age_hours:.1f}h ok"

    def _check_market_cap(self, meta: Dict) -> Tuple[bool, str]:
        """Skip if market cap already > $50M — early edge is gone."""
        mcap = meta.get("market_cap_usd", 0)
        if mcap and mcap > MEME_MAX_MCAP_USD:
            return False, f"mcap ${mcap/1e6:.0f}M > ${MEME_MAX_MCAP_USD/1e6:.0f}M — already pumped"
        if mcap:
            return True, f"mcap ${mcap/1000:.0f}k"
        return True, "mcap unknown"

    def _check_volume_minimum(self, volumes: List[float], meta: Dict) -> Tuple[bool, str]:
        """Memes need meaningful volume to be tradeable — not just a few buys."""
        vol_24h = meta.get("volume_24h_usd", 0)
        if vol_24h and vol_24h < 20_000:
            return False, f"24h vol ${vol_24h/1000:.0f}k — not enough liquidity events"
        rv, label = self._volume_state(volumes)
        if rv < 0.5:
            return False, f"vol {rv:.1f}x avg — ghost token, no activity"
        return True, f"vol {label}"

    def _check_rsi_entry(self, prices: List[float]) -> Tuple[bool, str]:
        """Tighter RSI window for memes — don't buy what's already pumped."""
        rsi = _calc_rsi(prices)
        if rsi is None:
            return True, "rsi skip"
        if rsi < MEME_MIN_RSI:
            return False, f"RSI={rsi:.0f} — too weak / dying"
        if rsi > MEME_MAX_RSI_ENTRY:
            return False, f"RSI={rsi:.0f} > {MEME_MAX_RSI_ENTRY} — already pumped, you're exit liquidity"
        return True, f"RSI={rsi:.0f} ok"

    def _check_not_parabolic(self, prices: List[float]) -> Tuple[bool, str]:
        """Reject blow-off tops — if it's already 3x from recent low, wait for retrace."""
        parabolic, multiple = self._is_parabolic(prices, lookback=60)
        if parabolic:
            return False, f"price {multiple:.1f}x from 1h low — blow-off risk"
        return True, f"{multiple:.1f}x from 1h low (ok)"

    def _check_not_dumping(self, prices: List[float], volumes: List[float]) -> Tuple[bool, str]:
        """Detect active distribution (insiders selling into retail buying)."""
        if self._sell_divergence(prices, volumes):
            return False, "sell divergence — insiders distributing, volume fading as price rises"
        return True, "no distribution detected"

    def _check_rr_gate(self,
                   atr_pct: float,
                   prices: List[float],
                   volumes: List[float]) -> Tuple[bool, str]:
        ok, rr, msg = self._check_rr(atr_pct, prices, volumes)
        return ok, msg



    # ─────────────────────────────────────────────────────────────────────────
    # SOFT SCORING — 8 meme-specific signals
    # ─────────────────────────────────────────────────────────────────────────

    def _soft_score(self, prices: List[float], volumes: List[float],
                    meta: Dict) -> Tuple[int, Dict[str, bool], float]:
        """
        8 signals specifically calibrated for meme coin behavior.
        Volume signals are weighted most heavily — they are the only
        honest leading indicator in meme markets.
        """
        N = len(prices)
        if N < 15:
            return 0, {}, 0.0

        cur   = prices[-1]
        ema9  = _ema(prices, min(9,  N))
        ema20 = _ema(prices, min(20, N))
        rsi   = _calc_rsi(prices) or 50.0

        rv, _      = self._volume_state(volumes)
        velocity5  = self._price_velocity(prices, window=5)
        velocity15 = self._price_velocity(prices, window=15)
        _, multiple = self._is_parabolic(prices, lookback=60)

        # MACD
        macd_now  = _ema(prices, min(12, N)) - _ema(prices, min(26, N))
        macd_prev = (_ema(prices[:-1], min(12, N)) - _ema(prices[:-1], min(26, N))
                     if N > 26 else macd_now)

        # Volume acceleration (last 3 vs prior 3)
        vol_accel = False
        if volumes and len(volumes) >= 6:
            vol_accel = (sum(volumes[-3:]) / 3) > (sum(volumes[-6:-3]) / 3) * 1.5

        # EMA slope
        ema9_prev = _ema(prices[:-5], min(9, N)) if N >= 15 else ema9
        slope9    = (ema9 - ema9_prev) / ema9_prev if ema9_prev > 0 else 0.0

        flags = {
            # 1. VOLUME EXPLOSION — the #1 signal for meme moves
            #    5x+ volume = someone is accumulating or coordinated buying starting
            "vol_explosion":   rv >= MEME_VOL_EXPLOSION,

            # 2. Volume spike (softer version — still meaningful)
            "vol_spike":       MEME_VOL_SPIKE <= rv < MEME_VOL_EXPLOSION,

            # 3. Price accelerating NOW (fast, not stalling)
            "price_velocity":  velocity5 > 3.0 and velocity15 > 1.0,

            # 4. RSI in sweet zone AND rising (early momentum confirmation)
            "rsi_sweet":       45 <= rsi <= 65 and (rsi > (_calc_rsi(prices[:-3]) or rsi)),

            # 5. MACD turning bullish (momentum confirmation)
            "macd_cross":      macd_now > macd_prev and macd_now > -0.0001,

            # 6. Not overextended (room to run — not 2x+ from recent low already)
            "room_to_run":     multiple < 2.0,

            # 7. EMA9 steeply rising (short-term trend has strong velocity)
            "ema_velocity":    slope9 > 0.003 and cur > ema9,

            # 8. Volume acceleration (buying is building, not one candle then fade)
            "vol_building":    vol_accel,
        }

        score = sum(flags.values())

        # Probability weights — volume signals weighted most heavily
        weights = {
            "vol_explosion":  20,   # the single most predictive meme signal
            "vol_spike":      12,
            "price_velocity": 10,
            "rsi_sweet":       9,
            "macd_cross":      8,
            "room_to_run":     7,
            "ema_velocity":    9,
            "vol_building":   10,
        }
        raw_prob = 30.0 + sum(weights[k] for k, v in flags.items() if v)
        prob     = min(raw_prob, 96.0)

        return score, flags, prob

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN ANALYZE
    # ─────────────────────────────────────────────────────────────────────────

    def analyze(self, token: str,
                prices: List[float],
                volumes: List[float],
                token_meta: Optional[Dict] = None,
                min_soft_score: int = 3) -> Dict:
        """
        Full meme coin analysis pipeline.

        Returns dict compatible with trader, plus meme-specific fields:
          atr_pct, atr_stop_pct, atr_tp1_pct, atr_tp2_pct,
          rr_ratio, volume_state, velocity_5, multiple_from_low,
          sell_divergence, is_parabolic
        """
        meta = token_meta or {}
        N    = len(prices)
        cur  = prices[-1] if prices else 0.0

        # Base indicators
        cur_rsi = _calc_rsi(prices) or 50.0
        ema20   = _ema(prices, min(20, N)) if N >= 2 else cur
        trend   = "BULLISH" if cur > ema20 else "BEARISH"
        rv, vol_label = self._volume_state(volumes)
        ema_p   = _ema(prices[:-6], min(20, N)) if N >= 27 else ema20
        slope   = (ema20 - ema_p) / ema_p if ema_p > 0 else 0.0

        # ATR and exits
        atr_pct      = self._calc_atr(prices)
        atr_stop_pct = min(MEME_STOP_MULT  * atr_pct, MEME_MAX_STOP_PCT)
        atr_tp1_pct  = MEME_TP1_MULT  * atr_pct
        atr_tp2_pct  = MEME_TP2_MULT  * atr_pct
        atr_trail_pct= MEME_TRAIL_MULT * atr_pct

        # R:R
        rr_ok, rr_ratio, rr_msg = self._check_rr(atr_pct)

        # Meme-specific metrics
        velocity5     = self._price_velocity(prices, window=5)
        is_para, mult = self._is_parabolic(prices, lookback=60)
        sell_div      = self._sell_divergence(prices, volumes)

        _base = {
            "signal":           "HOLD",
            "confidence":       0.0,
            "prob_score":       0.0,
            "reason":           "Insufficient data",
            "rsi":              cur_rsi,
            "rsi_rising":       False,
            "trend":            trend,
            "momentum":         "WEAK",
            "current_price":    cur,
            "sma_20":           ema20,
            "ema_slope":        slope,
            "relative_volume":  rv,
            "rel_vol":          rv,
            "buy_pts":          0,
            "buy_pts_detail":   {},
            "sell_pts":         0,
            "hard_fail":        False,
            "hard_fail_reason": "",
            # Meme-specific
            "atr_pct":          atr_pct,
            "atr_stop_pct":     atr_stop_pct,
            "atr_tp1_pct":      atr_tp1_pct,
            "atr_tp2_pct":      atr_tp2_pct,
            "atr_trail_pct":    atr_trail_pct,
            "rr_ratio":         rr_ratio,
            "volume_state":     vol_label,
            "velocity_5":       velocity5,
            "multiple_from_low":mult,
            "is_parabolic":     is_para,
            "sell_divergence":  sell_div,
        }

        if N < 15:
            _base["reason"] = f"Warming up ({N}/15)"
            return _base

        # ── STAGE 1: HARD FILTERS ─────────────────────────────────────────────
        checks = [
            ("liquidity",   self._check_liquidity(meta)),
            ("age",         self._check_age(meta)),
            ("mcap",        self._check_market_cap(meta)),
            ("volume",      self._check_volume_minimum(volumes, meta)),
            ("rsi_entry",   self._check_rsi_entry(prices)),
            ("parabolic",   self._check_not_parabolic(prices)),
            ("distribution",self._check_not_dumping(prices, volumes)),
            ("rr_gate", self._check_rr_gate(atr_pct, prices, volumes))
        ]

        failures = [(name, msg) for name, (ok, msg) in checks if not ok]
        if failures:
            fail_str = " | ".join(f"{n}:{m}" for n, m in failures)
            _base.update({
                "signal":           "HOLD",
                "reason":           f"HARD FAIL: {fail_str}",
                "hard_fail":        True,
                "hard_fail_reason": fail_str,
            })
            return _base

        # ── STAGE 2: SOFT SCORING ─────────────────────────────────────────────
        soft_score, flags, prob = self._soft_score(prices, volumes, meta)

        buy_pts_detail = {
            "vol_explosion": flags.get("vol_explosion",  False),
            "vol_spike":     flags.get("vol_spike",      False),
            "velocity":      flags.get("price_velocity", False),
            "rsi_rise":      flags.get("rsi_sweet",      False),
            "macd":          flags.get("macd_cross",     False),
            "room":          flags.get("room_to_run",    False),
            "ema_vel":       flags.get("ema_velocity",   False),
            "vol_build":     flags.get("vol_building",   False),
        }

        # DUMP detection for open positions (sell signal)
        sell_pts = sum([
            cur_rsi > 75,
            sell_div,
            slope < -0.003,
        ])
        if sell_pts >= 2:
            _base.update({
                "signal":          "SELL",
                "confidence":      0.80,
                "reason":          f"SELL: RSI={cur_rsi:.0f} div={sell_div} slope={slope:+.4f}",
                "buy_pts":         soft_score,
                "buy_pts_detail":  buy_pts_detail,
                "sell_pts":        sell_pts,
            })
            return _base

        # BUY
        if soft_score >= min_soft_score and trend == "BULLISH":
            active = " ".join(k for k, v in flags.items() if v)
            _base.update({
                "signal":          "BUY",
                "confidence":      min(0.40 + soft_score * 0.08, 0.95),
                "prob_score":      prob,
                "reason":          (f"MEME score={soft_score}/8 prob={prob:.0f}% "
                                    f"R:R={rr_ratio:.1f} ATR={atr_pct*100:.1f}% "
                                    f"vol={rv:.1f}x vel={velocity5:+.1f}% "
                                    f"{mult:.1f}x-from-low [{active}]"),
                "trend":           "BULLISH",
                "buy_pts":         soft_score,
                "buy_pts_detail":  buy_pts_detail,
                "sell_pts":        sell_pts,
                "hard_fail":       False,
            })
            return _base

        # HOLD
        _base.update({
            "signal":         "HOLD",
            "prob_score":     prob,
            "reason":         f"score={soft_score}/{min_soft_score} trend={trend} vol={rv:.1f}x",
            "buy_pts":        soft_score,
            "buy_pts_detail": buy_pts_detail,
            "sell_pts":       sell_pts,
        })
        return _base


# ─────────────────────────────────────────────────────────────────────────────
# INDICATOR HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _ema(data: List[float], period: int) -> float:
    if not data:
        return 0.0
    if len(data) < period:
        return sum(data) / len(data)
    k = 2.0 / (period + 1)
    e = sum(data[:period]) / period
    for v in data[period:]:
        e = v * k + e * (1 - k)
    return e


def _calc_rsi(data: List[float], period: int = 14) -> Optional[float]:
    if len(data) < period + 1:
        return None
    gains  = [max(data[i] - data[i-1], 0) for i in range(1, len(data))]
    losses = [max(data[i-1] - data[i], 0) for i in range(1, len(data))]
    ag = sum(gains[-period:])  / period
    al = sum(losses[-period:]) / period
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)