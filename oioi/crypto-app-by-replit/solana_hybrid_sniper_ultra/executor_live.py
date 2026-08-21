import asyncio
import aiohttp
import json
import os
import logging
from datetime import datetime
from utils.swap_executor import JupiterSwap
from strategy import ABSOLUTE_MAX_SOL   # single source of truth for position cap

logger = logging.getLogger("LiveExecutor")

SOL_MINT        = "So11111111111111111111111111111111111111112"
LAMPORTS_PER_SOL = 1_000_000_000


class LiveExecutor:
    def __init__(self, strategy=None):
        """
        Pass the HybridStrategy instance so LiveExecutor can update the
        per-token blacklist whenever a position is closed.
        """
        self._strategy            = strategy
        self.jupiter              = JupiterSwap()
        self.private_key          = os.getenv("PRIVATE_KEY", "")
        self.rpc_url              = os.getenv("RPC_URL", "https://api.mainnet-beta.solana.com")
        self.max_position_sol     = float(os.getenv("MAX_POSITION_SOL", "0.5"))
        self.default_slippage_bps = int(os.getenv("DEFAULT_SLIPPAGE_BPS", "500"))
        self.max_price_impact_pct = float(os.getenv("MAX_PRICE_IMPACT_PCT", "5.0"))

        self.trade_log_path    = "solana_hybrid_sniper_ultra/data/live_trades.json"
        self.positions_path    = "solana_hybrid_sniper_ultra/data/live_positions.json"

        os.makedirs("solana_hybrid_sniper_ultra/data", exist_ok=True)
        for path in (self.trade_log_path, self.positions_path):
            if not os.path.exists(path):
                with open(path, "w") as f:
                    json.dump([], f)

        self._positions: dict[str, dict] = {}
        self._load_positions()

    # ── BUY ─────────────────────────────────────────────────────────────────

    async def execute_buy(self, token: dict, mode: str, signal: dict) -> bool:
        address        = token.get("address")
        symbol         = token.get("symbol", "UNKNOWN")
        size_sol       = min(signal.get("size_sol", 0.1), self.max_position_sol, ABSOLUTE_MAX_SOL)
        slippage_bps   = int(signal.get("slippage", 5) * 100)
        amount_lamports = int(size_sol * LAMPORTS_PER_SOL)

        if address in self._positions:
            logger.warning(f"Already holding {symbol} — skipping duplicate buy")
            return False

        logger.info(f"LIVE BUY: {symbol} ({address}) | {size_sol} SOL | {slippage_bps}bps | mode={mode}")

        try:
            quote = await self.jupiter.get_quote(
                input_mint=SOL_MINT,
                output_mint=address,
                amount=amount_lamports,
                slippage=slippage_bps,
            )

            if "error" in quote:
                logger.error(f"Quote error for {symbol}: {quote['error']}")
                return False

            price_impact = float(quote.get("priceImpactPct", 0))
            if price_impact > self.max_price_impact_pct:
                logger.warning(f"Price impact too high for {symbol}: {price_impact:.1f}% — skipping")
                return False

            out_amount = int(quote.get("outAmount", 0))
            if out_amount == 0:
                logger.error(f"Zero output amount for {symbol} — aborting")
                return False

            swap_result = await self.jupiter.execute_swap(quote, self.private_key)

            if not swap_result.get("success"):
                logger.error(f"Swap failed for {symbol}: {swap_result}")
                self._log_trade(self._build_trade_record(
                    symbol, address, mode, "BUY", size_sol,
                    out_amount=0, price_impact=price_impact,
                    tx_hash="", status="FAILED",
                ))
                return False

            # ── Track position ───────────────────────────────────────────────
            entry_price = size_sol / (out_amount / LAMPORTS_PER_SOL) if out_amount else 0
            self._positions[address] = {
                "symbol":          symbol,
                "mode":            mode,
                "entry_price":     entry_price,
                "remaining_tokens": out_amount,
                "size_sol":        size_sol,
                "peak_price":      entry_price,
                "tp1_triggered":   False,
                "tp2_triggered":   False,
                "trailing_active": False,
                "opened_at":       datetime.utcnow().isoformat(),
                "tx_buy":          swap_result.get("txid", ""),
            }

            # --- DASHBOARD API BRIDGE: Sync Live Buy ---
            ui_trade = {
                "tokenAddress": address,
                "tokenSymbol": symbol,
                "type": "BUY",
                "mode": mode,
                "tradingMode": "live",
                "status": "OPEN",
                "amount": str(size_sol),
                "price": str(entry_price),
                "currentPrice": str(entry_price),
                "peakPrice": str(entry_price),
                "pnl": "0",
                "peakPnl": "0",
                "score": str(token.get("score", 85)),
                "txHash": swap_result.get("txid", ""),
            }
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post("http://localhost:5000/api/internal/trade/open", json=ui_trade, timeout=2) as res:
                        if res.status == 200:
                            data = await res.json()
                            self._positions[address]["db_id"] = data.get("id")
            except Exception:
                pass
            # -------------------------------------------

            self._save_positions()

            trade = self._build_trade_record(
                symbol, address, mode, "BUY", size_sol,
                out_amount=out_amount, price_impact=price_impact,
                tx_hash=swap_result.get("txid", ""), status="CONFIRMED",
            )
            self._log_trade(trade)
            logger.info(f"✅ BUY CONFIRMED: {symbol} | {out_amount} tokens | TX: {trade['tx_hash']}")
            return True

        except Exception as e:
            logger.error(f"Live buy failed for {symbol}: {e}")
            self._log_trade(self._build_trade_record(
                symbol, address, mode, "BUY", size_sol,
                out_amount=0, status="ERROR", error=str(e),
            ))
            return False

    # ── PRICE TICK ───────────────────────────────────────────────────────────

    async def on_price_update(self, address: str, current_price: float) -> None:
        pos = self._positions.get(address)
        if not pos or pos["entry_price"] == 0:
            return

        if self._strategy:
            exit_signal = self._strategy.check_exit(address, current_price)
            if exit_signal:
                await self.execute_exit(
                    address,
                    exit_signal.get("close_pct", 1.0),
                    exit_signal["reason"],
                )
            return

        entry   = pos["entry_price"]
        pnl_pct = (current_price - entry) / entry
        if pnl_pct <= -0.15:
            logger.warning(f"🛑 FALLBACK STOP-LOSS for {pos['symbol']}: {pnl_pct:+.1%}")
            await self.execute_exit(address, 1.0, "STOP_LOSS")

    # ── Public exit executor ────────────────────────────────────────────────

    async def execute_exit(self, address: str, close_pct: float, reason: str) -> bool:
        pos = self._positions.get(address)
        if not pos:
            logger.debug(f"execute_exit: no open position for {address[:8]}… — already closed?")
            return False
        return await self._execute_sell(address, pos, close_pct=close_pct, reason=reason)

    # ── Internal sell executor ───────────────────────────────────────────────

    async def _execute_sell(self, address: str, pos: dict, close_pct: float, reason: str) -> bool:
        symbol    = pos["symbol"]
        remaining = pos.get("remaining_tokens", 0)
        sell_amt  = int(remaining * close_pct)

        if sell_amt == 0:
            logger.warning(f"Zero sell amount for {symbol} — removing stale position")
            self._positions.pop(address, None)
            self._save_positions()
            return False

        is_emergency = reason == "EMERGENCY_STOP"
        slippage     = 5000 if is_emergency else self.default_slippage_bps

        logger.info(f"LIVE SELL: {symbol} | reason={reason} | close={close_pct:.0%} | {sell_amt} tokens | slippage={slippage}bps")

        try:
            quote = await self.jupiter.get_quote(
                input_mint=address,
                output_mint=SOL_MINT,
                amount=sell_amt,
                slippage=slippage,
            )

            if "error" in quote:
                logger.error(f"Sell quote error for {symbol}: {quote['error']}")
                return False

            swap_result = await self.jupiter.execute_swap(quote, self.private_key)
            sol_received = int(quote.get("outAmount", 0)) / LAMPORTS_PER_SOL
            exit_price = (sol_received / (sell_amt / LAMPORTS_PER_SOL)) if sell_amt > 0 else 0

            trade = {
                "timestamp":    datetime.utcnow().isoformat(),
                "symbol":       symbol,
                "mint":         address,
                "mode":         pos["mode"],
                "trading_mode": "live",
                "action":       "SELL",
                "close_pct":    close_pct,
                "reason":       reason,
                "tokens_sold":  sell_amt,
                "sol_received": sol_received,
                "tx_hash":      swap_result.get("txid", ""),
                "status":       "CONFIRMED" if swap_result.get("success") else "FAILED",
            }
            self._log_trade(trade)

            if swap_result.get("success"):
                db_id = pos.get("db_id")
                
                # Setup risk metrics for strategy callback
                pnl_pct = 0.0
                entry = pos.get("entry_price", 0)
                if entry and sol_received:
                    sol_in = pos.get("size_sol", sol_received)
                    pnl_pct = (sol_received - sol_in * close_pct) / (sol_in * close_pct)

                if close_pct >= 1.0:
                    self._positions.pop(address, None)
                else:
                    pos["remaining_tokens"] = remaining - sell_amt
                
                self._save_positions()

                # --- DASHBOARD API BRIDGE: Sync Live Sell ---
                if db_id and close_pct >= 1.0:
                    try:
                        async with aiohttp.ClientSession() as session:
                            await session.post("http://localhost:5000/api/internal/trade/close", json={
                                "id": db_id,
                                "currentPrice": str(exit_price),
                                "pnl": f"{pnl_pct * 100:.2f}",
                                "exitReason": reason,
                                "newBalance": "LIVE" # Live updates balance differently
                            }, timeout=2)
                    except Exception:
                        pass
                # --------------------------------------------

                if self._strategy:
                    self._strategy.risk._exit(address, reason, pnl_pct, close_pct)

                logger.info(f"✅ SELL CONFIRMED: {symbol} | reason={reason} | +{sol_received:.4f} SOL")
                return True

            logger.error(f"Sell swap failed for {symbol}")
            return False

        except Exception as e:
            logger.error(f"Live sell failed for {symbol}: {e}")
            return False

    # ── Manual sell ─────────────────────────────────────────────────────────

    async def execute_sell(self, token: dict, mode: str, amount: int) -> bool:
        address = token.get("address")
        pos     = self._positions.get(address)
        if not pos:
            pos = {"symbol": token.get("symbol","UNKNOWN"), "mode": mode,
                   "remaining_tokens": amount, "entry_price": 0,
                   "peak_price": 0, "tp1_triggered": False, "tp2_triggered": False,
                   "trailing_active": False, "opened_at": datetime.utcnow().isoformat()}
        return await self._execute_sell(address, pos, close_pct=1.0, reason="MANUAL")

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load_positions(self) -> None:
        try:
            with open(self.positions_path) as f:
                data = json.load(f)
            for p in data:
                addr = p.get("mint") or p.get("address")
                if addr:
                    self._positions[addr] = p
            if self._positions:
                logger.info(f"Restored {len(self._positions)} live position(s) from disk")
        except Exception:
            pass

    def _save_positions(self) -> None:
        try:
            with open(self.positions_path, "w") as f:
                json.dump(list(self._positions.values()), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save positions: {e}")

    def _log_trade(self, trade: dict) -> None:
        try:
            with open(self.trade_log_path, "r") as f:
                trades = json.load(f)
            trades.append(trade)
            with open(self.trade_log_path, "w") as f:
                json.dump(trades, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_trade_record(self, symbol, address, mode, action, size_sol,
                             out_amount=0, price_impact=0, tx_hash="",
                             status="UNKNOWN", error=None) -> dict:
        record = {
            "timestamp":    datetime.utcnow().isoformat(),
            "symbol":       symbol,
            "mint":         address,
            "mode":         mode,
            "trading_mode": "live",
            "action":       action,
            "size_sol":     size_sol,
            "out_amount":   out_amount,
            "price_impact": price_impact,
            "tx_hash":      tx_hash,
            "status":       status,
        }
        if error:
            record["error"] = error
        return record

    def get_open_positions(self) -> list[dict]:
        return list(self._positions.values())

    def is_holding(self, address: str) -> bool:
        return address in self._positions