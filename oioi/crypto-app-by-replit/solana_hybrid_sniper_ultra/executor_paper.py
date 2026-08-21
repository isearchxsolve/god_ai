import asyncio
import aiohttp
import json
import os
import logging
from datetime import datetime
from strategy import ABSOLUTE_MAX_SOL   # single source of truth for position cap

logger = logging.getLogger("PaperExecutor")


class PaperExecutor:
    def __init__(self, db_path="solana_hybrid_sniper_ultra/data/paper_trades.json", strategy=None):
        """
        strategy: pass the HybridStrategy instance so every close updates
                  the per-token blacklist in RiskManager.
        """
        self._strategy      = strategy
        self.db_path        = db_path
        self.positions_path = db_path.replace("paper_trades.json", "paper_positions.json")

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        for path in (self.db_path, self.positions_path):
            if not os.path.exists(path):
                with open(path, "w") as f:
                    json.dump([], f)

        # address → position dict
        self._open: dict[str, dict] = {}
        self._load_open_positions()

        self.total_pnl_sol = 0.0
        self.wins          = 0
        self.losses        = 0
        self._load_stats_from_trades()

    # ── Entry ────────────────────────────────────────────────────────────────

    async def execute_trade(self, token: dict, mode: str, signal: dict) -> bool:
        address     = token.get("address", "UNKNOWN")
        symbol      = token.get("symbol",  "UNKNOWN")
        entry_price = token.get("price", 0)
        size_sol    = min(signal.get("size_sol", 0.05), ABSOLUTE_MAX_SOL)

        if address in self._open:
            logger.warning(f"Already holding {symbol} in paper — skipping duplicate buy")
            return False

        trade = {
            "id":           f"{symbol}_{int(datetime.utcnow().timestamp())}",
            "timestamp":    datetime.utcnow().isoformat(),
            "symbol":       symbol,
            "mint":         address,
            "mode":         mode,
            "trading_mode": "paper",
            "entry_price":  entry_price,
            "size_sol":     size_sol,
            "status":       "OPEN",
            "exit_price":   None,
            "exit_reason":  None,
            "pnl_pct":      None,
            "pnl_sol":      None,
            "peak_price":   entry_price,
            "_partial_pnl_sol": 0.0,
        }

        # --- DASHBOARD API BRIDGE: Sync Buy ---
        # Map the payload to match what the Node UI expects
        ui_trade = {
            "tokenAddress": address,
            "tokenSymbol": symbol,
            "type": "BUY",
            "mode": mode,
            "tradingMode": "paper",
            "status": "OPEN",
            "amount": str(size_sol),
            "price": str(entry_price),
            "currentPrice": str(entry_price),
            "peakPrice": str(entry_price),
            "pnl": "0",
            "peakPnl": "0",
            "score": str(token.get("score", 85)),
            "txHash": f"paper_{trade['id']}",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("http://localhost:5000/api/internal/trade/open", json=ui_trade, timeout=2) as res:
                    if res.status == 200:
                        data = await res.json()
                        trade["db_id"] = data.get("id")
        except Exception as e:
            pass # Dashboard is likely off
        # ---------------------------------------

        self._open[address] = trade.copy()
        self._append_trade(trade)
        self._save_open_positions()

        logger.info(f"[PAPER] BUY  {symbol:<12} @ {entry_price:.2e}  |  {size_sol:.3f} SOL  |  mode={mode}")
        return True

    # ── Exit ─────────────────────────────────────────────────────────────────

    async def execute_exit(self, address: str, current_price: float,
                           close_pct: float = 1.0, reason: str = "MANUAL") -> dict | None:
        """
        Unified exit method. Alias: close_position() delegates here.
        """
        pos = self._open.get(address)
        if not pos:
            return None

        entry    = pos["entry_price"]
        size_sol = pos["size_sol"]
        pnl_pct  = (current_price - entry) / entry if entry else 0
        pnl_sol  = size_sol * close_pct * pnl_pct

        is_emergency = reason == "EMERGENCY_STOP"
        is_full_close = close_pct >= 1.0

        if is_full_close:
            total_pnl_sol = pnl_sol + pos.get("_partial_pnl_sol", 0.0)
            self.total_pnl_sol += total_pnl_sol
            if pnl_pct >= 0:
                self.wins += 1
            else:
                self.losses += 1
        else:
            pos["_partial_pnl_sol"] = pos.get("_partial_pnl_sol", 0.0) + pnl_sol

        closed_trade = {
            **{k: v for k, v in pos.items() if not k.startswith("_")},
            "exit_price":  current_price,
            "exit_reason": reason,
            "close_pct":   close_pct,
            "pnl_pct":     round(pnl_pct * 100, 2),
            "pnl_sol":     round(pnl_sol, 4),
            "simulated_slippage": -0.05 if is_emergency else 0.0,
            "status":      "WIN" if pnl_pct >= 0 else ("LOSS" if is_full_close else "PARTIAL"),
            "closed_at":   datetime.utcnow().isoformat(),
        }

        db_id = pos.get("db_id")

        if is_full_close:
            del self._open[address]
        else:
            self._open[address]["size_sol"] *= (1.0 - close_pct)

        self._update_trade(pos["id"], closed_trade)
        self._save_open_positions()

        # --- DASHBOARD API BRIDGE: Sync Sell ---
        if db_id and is_full_close:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.post("http://localhost:5000/api/internal/trade/close", json={
                        "id": db_id,
                        "currentPrice": str(current_price),
                        "pnl": f"{pnl_pct * 100:.2f}",
                        "exitReason": reason,
                        "newBalance": f"{10.0 + self.total_pnl_sol:.3f}"
                    }, timeout=2)
            except Exception:
                pass
        # ---------------------------------------

        emoji = "🚨" if is_emergency else ("✅" if pnl_pct >= 0 else "❌")
        logger.info(
            f"[PAPER] {emoji} {'CLOSE' if is_full_close else 'PARTIAL'} "
            f"{pos['symbol']:<10} | reason={reason:<16} "
            f"| {pnl_pct:+.1%} ({close_pct:.0%}) | {pnl_sol:+.4f} SOL "
            f"| total PnL: {self.total_pnl_sol:+.4f} SOL"
        )
        return closed_trade

    async def close_position(self, address: str, current_price: float,
                              reason: str, close_pct: float = 1.0) -> dict | None:
        """Legacy name — delegates to execute_exit for API consistency."""
        return await self.execute_exit(address, current_price, close_pct, reason)

    # ── Price update ─────────────────────────────────────────────────────────

    def update_peak(self, address: str, current_price: float) -> None:
        if address in self._open:
            self._open[address]["peak_price"] = max(
                self._open[address].get("peak_price", 0), current_price
            )

    def get_open_positions(self) -> list[dict]:
        return list(self._open.values())

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        total = self.wins + self.losses
        return {
            "open_positions": len(self._open),
            "wins":           self.wins,
            "losses":         self.losses,
            "win_rate":       round(self.wins / total * 100, 1) if total else 0,
            "total_pnl_sol":  round(self.total_pnl_sol, 4),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_open_positions(self) -> None:
        try:
            with open(self.positions_path) as f:
                data = json.load(f)
            for pos in data:
                if pos.get("mint"):
                    self._open[pos["mint"]] = pos
            if self._open:
                logger.info(f"Restored {len(self._open)} paper position(s) from disk")
        except Exception:
            pass

    def _load_stats_from_trades(self) -> None:
        try:
            with open(self.db_path) as f:
                trades = json.load(f)
            for t in trades:
                status = t.get("status")
                if status == "WIN":
                    self.wins += 1
                    self.total_pnl_sol += t.get("pnl_sol", 0) or 0
                elif status == "LOSS":
                    self.losses += 1
                    self.total_pnl_sol += t.get("pnl_sol", 0) or 0
            if self.wins + self.losses:
                logger.info(
                    f"Restored stats from disk: {self.wins}W / {self.losses}L "
                    f"| PnL={self.total_pnl_sol:+.4f} SOL"
                )
        except Exception:
            pass

    def _save_open_positions(self) -> None:
        try:
            with open(self.positions_path, "w") as f:
                json.dump(list(self._open.values()), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save paper positions: {e}")

    def _append_trade(self, trade: dict) -> None:
        try:
            with open(self.db_path, "r") as f:
                trades = json.load(f)
            trades.append(trade)
            with open(self.db_path, "w") as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to append paper trade: {e}")

    def _update_trade(self, trade_id: str, updated: dict) -> None:
        try:
            with open(self.db_path, "r") as f:
                trades = json.load(f)
            for i, t in enumerate(trades):
                if t.get("id") == trade_id:
                    trades[i] = updated
                    break
            with open(self.db_path, "w") as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to update paper trade {trade_id}: {e}")