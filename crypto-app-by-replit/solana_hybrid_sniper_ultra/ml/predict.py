import pickle
import os
import numpy as np
import logging

logger = logging.getLogger("Predictor")

_BASE_SCORE = 0.20  # Even lower base — tokens must earn confidence

# FIX: Check xgboost at import time so failure is visible immediately on startup.
# Previously xgboost was only imported inside pickle.load(), which threw a silent
# exception caught by the broad except → heuristic fallback with no operator warning.
try:
    import xgboost  # noqa: F401
    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False
    logger.warning(
        "⚠️  xgboost NOT installed — ML model cannot load. "
        "Bot will use heuristic fallback (lower accuracy). "
        "Fix: pip install xgboost"
    )


class Predictor:
    def __init__(self):
        self.model_path      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.pkl")
        self.model           = None
        self.feature_columns = None
        self.version         = "1.0"
        self.is_using_heuristic = True  # flipped False only on clean model load
        self._load_model()

    def _load_model(self):
        # FIX: bail out immediately with a clear message if xgboost isn't installed.
        if not _XGBOOST_AVAILABLE:
            logger.warning("Skipping model load — xgboost not installed. Run: pip install xgboost")
            return
        if not os.path.exists(self.model_path):
            logger.warning("No trained model found. Using heuristic fallback.")
            return
        try:
            with open(self.model_path, "rb") as f:
                payload = pickle.load(f)
            if isinstance(payload, dict):
                self.model           = payload["model"]
                self.feature_columns = payload["features"]
                self.version         = payload.get("version", "2.0")
                logger.info(f"Loaded model v{self.version} with {len(self.feature_columns)} features")
            else:
                self.model           = payload
                self.feature_columns = ["age_seconds", "liquidity_usd", "volume_change_1m"]
                self.version         = "1.0"
            self.is_using_heuristic = False  # model loaded cleanly
        except Exception as e:
            logger.error(f"Failed to load model: {e}")

    def predict(self, features: dict) -> dict:
        if not self.model:
            return self._heuristic_predict(features)
        try:
            feature_values = [float(features.get(col, 0) or 0) for col in self.feature_columns]
            prob    = self.model.predict_proba(np.array([feature_values]))[0][1]
            penalty = self._compute_penalties(features)
            prob    = max(0.05, min(0.95, prob - penalty))
            return {
                "pump_probability": float(prob),
                "dump_risk":        1.0 - float(prob),
                "model_version":    self.version,
                "is_heuristic":     False,
            }
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return self._heuristic_predict(features)

    def _heuristic_predict(self, features: dict) -> dict:
        score = _BASE_SCORE

        age          = features.get("age_seconds",        99999)
        liq          = features.get("liquidity_usd",          0)
        buy_pressure = features.get("buy_pressure_5m",      0.5)
        price_chg_5m = features.get("price_change_5m",        0)
        price_chg_1h = features.get("price_change_1h",        0)
        vol_momentum = features.get("volume_change_1m",        0)
        tx_velocity  = features.get("tx_velocity_per_hour",    0)
        liq_to_mcap  = features.get("liq_to_mcap",             0)
        buy_sell_r   = features.get("buy_sell_ratio",         1.0)

        # ── Age (fresh = good, but only in sweet spot) ────────────────────────
        if age < 60:
            score += 0.16
        elif age < 180:
            score += 0.10
        elif age < 600:
            score += 0.03

        # ── Liquidity sweet spot ──────────────────────────────────────────────
        if 5_000 < liq < 80_000:
            score += 0.10
        elif 2_000 < liq <= 5_000:
            score += 0.03

        # ── Buy pressure ──────────────────────────────────────────────────────
        if buy_pressure > 0.72:
            score += 0.14
        elif buy_pressure > 0.62:
            score += 0.07
        elif buy_pressure > 0.55:
            score += 0.02

        # ── Price momentum (moderate is good, extreme is already-peaked) ──────
        if 5 < price_chg_5m < 50:
            score += 0.10
        elif 2 < price_chg_5m <= 5:
            score += 0.04

        # ── Volume momentum — FIXED: moderate is signal, extreme is rug ───────
        # Original bug: treated all high vol_momentum as positive.
        # Reality: vol_momentum 1.5–4 = healthy pump, >8 = rug spike
        if 1.5 < vol_momentum < 4.0:
            score += 0.10
        elif 1.0 < vol_momentum <= 1.5:
            score += 0.04
        elif vol_momentum > 8.0:
            score -= 0.15    # extreme spike = rug fingerprint

        # ── Transaction velocity ──────────────────────────────────────────────
        if tx_velocity > 100:
            score += 0.08
        elif tx_velocity > 50:
            score += 0.03

        # ── Liquidity/mcap ratio ──────────────────────────────────────────────
        if liq_to_mcap > 0.04:
            score += 0.06
        elif liq_to_mcap > 0.02:
            score += 0.02

        # ── Buy/sell ratio ────────────────────────────────────────────────────
        if buy_sell_r > 2.5:
            score += 0.08
        elif buy_sell_r > 1.5:
            score += 0.04

        score -= self._compute_penalties(features)
        score = max(0.05, min(0.95, score))

        return {
            "pump_probability": round(score, 4),
            "dump_risk":        round(1.0 - score, 4),
            "model_version":    "heuristic_v3",
            "is_heuristic":     True,  # FIX: lets strategy and bot.py tighten thresholds
        }

    def _compute_penalties(self, features: dict) -> float:
        penalty      = 0.0
        liq          = features.get("liquidity_usd",      0)
        price_chg_5m = features.get("price_change_5m",    0)
        price_chg_1h = features.get("price_change_1h",    0)
        buy_pressure = features.get("buy_pressure_5m",  0.5)
        liq_to_mcap  = features.get("liq_to_mcap",        0)
        vol_momentum = features.get("volume_change_1m",   0)
        age          = features.get("age_seconds",      9999)
        tx_velocity  = features.get("tx_velocity_per_hour", 0)

        # Low liquidity → rug risk
        if liq < 1_000:
            penalty += 0.40
        elif liq < 3_000:
            penalty += 0.18

        # Honeypot fingerprint: ultra-low liq/mcap
        if 0 < liq_to_mcap < 0.005:
            penalty += 0.25

        # Extreme vol spike relative to tiny liq = bot-driven rug setup
        # vol_5m > liq is a strong rug signal
        vol_5m = features.get("volume_5m", 0)
        if liq > 0 and vol_5m > liq * 3:
            penalty += 0.20
        elif liq > 0 and vol_5m > liq * 1.5:
            penalty += 0.08

        # Already pumped hard → likely at the top
        if price_chg_5m > 100:
            penalty += 0.25
        elif price_chg_5m > 60:
            penalty += 0.12

        # 1h already very hot → latecomers get dumped on
        if price_chg_1h > 300:
            penalty += 0.18
        elif price_chg_1h > 150:
            penalty += 0.08

        # Seller domination
        if buy_pressure < 0.38:
            penalty += 0.25
        elif buy_pressure < 0.48:
            penalty += 0.12

        # Extreme vol spike = rug (separate from momentum check above)
        if vol_momentum > 10:
            penalty += 0.20
        elif vol_momentum > 8:
            penalty += 0.10

        # Abnormally high tx velocity on tiny liq = bot wash trading
        if tx_velocity > 2000 and liq < 10_000:
            penalty += 0.15

        return penalty
