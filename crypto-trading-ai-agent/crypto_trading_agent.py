#!/usr/bin/env python3
"""
Sophisticated Crypto Trading AI Agent
Supports CoinDCX integration with paper and live trading modes
"""

import json
import time
import hmac
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import argparse
import sys
from dataclasses import dataclass, asdict
from enum import Enum


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    LIMIT = "limit_order"
    MARKET = "market_order"


@dataclass
class Trade:
    timestamp: str
    symbol: str
    side: str
    price: float
    quantity: float
    total: float
    order_id: str
    status: str


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    current_price: float
    pnl: float
    pnl_percentage: float


class CoinDCXClient:
    """CoinDCX API Client"""
    
    def __init__(self, api_key: str = "", api_secret: str = "", mode: TradingMode = TradingMode.PAPER):
        self.api_key = api_key
        self.api_secret = api_secret
        self.mode = mode
        self.base_url = "https://api.coindcx.com"
        self.public_url = "https://public.coindcx.com"
        
    def _generate_signature(self, secret_key: str, payload: str) -> str:
        """Generate HMAC signature for authenticated requests"""
        signature = hmac.new(
            secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, endpoint: str, method: str = "GET", payload: Optional[Dict] = None) -> Dict:
        """Make authenticated API request"""
        if self.mode == TradingMode.PAPER:
            # In paper trading mode, simulate responses
            return self._simulate_response(endpoint, method, payload)
        
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json"
        }
        
        if payload:
            payload_json = json.dumps(payload, separators=(',', ':'))
            headers["X-AUTH-APIKEY"] = self.api_key
            headers["X-AUTH-SIGNATURE"] = self._generate_signature(self.api_secret, payload_json)
            
            response = requests.post(url, data=payload_json, headers=headers)
        else:
            if self.api_key:
                headers["X-AUTH-APIKEY"] = self.api_key
            response = requests.get(url, headers=headers)
        
        return response.json()
    
    def _simulate_response(self, endpoint: str, method: str, payload: Optional[Dict]) -> Dict:
        """Simulate API responses for paper trading"""
        if "ticker" in endpoint or "market_data" in endpoint:
            # Simulate market data with realistic crypto prices
            symbol = payload.get("market") if payload else "B-BTC_USDT"
            base_prices = {
                "B-BTC_USDT": 45000,
                "B-ETH_USDT": 2500,
                "I-BNB_USDT": 350,
                "I-ADA_USDT": 0.50,
                "I-SOL_USDT": 100
            }
            base_price = base_prices.get(symbol, 1000)
            # Add some random variation
            import random
            price = base_price * (1 + random.uniform(-0.02, 0.02))
            
            return {
                "market": symbol,
                "last_price": str(price),
                "bid": str(price * 0.999),
                "ask": str(price * 1.001),
                "volume": str(random.uniform(100, 1000)),
                "timestamp": int(time.time())
            }
        elif "place_order" in endpoint:
            # Simulate order placement
            return {
                "orders": [{
                    "id": f"paper_{int(time.time())}_{random.randint(1000,9999)}",
                    "status": "filled",
                    "market": payload.get("market"),
                    "side": payload.get("side"),
                    "order_type": payload.get("order_type"),
                    "price": payload.get("price_per_unit", "0"),
                    "quantity": payload.get("total_quantity"),
                    "timestamp": datetime.now().isoformat()
                }]
            }
        elif "balances" in endpoint:
            # Simulate account balance
            return [
                {"currency": "USDT", "balance": 10000.0, "locked_balance": 0.0},
                {"currency": "BTC", "balance": 0.1, "locked_balance": 0.0},
                {"currency": "ETH", "balance": 1.5, "locked_balance": 0.0}
            ]
        return {}
    
    def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker data for a symbol"""
        if self.mode == TradingMode.LIVE:
            try:
                response = requests.get(f"{self.public_url}/market_data/ticker?pair={symbol}")
                if response.status_code == 200:
                    return response.json()
            except:
                pass
        return self._simulate_response("ticker", "GET", {"market": symbol})
    
    def get_balances(self) -> List[Dict]:
        """Get account balances"""
        endpoint = "/exchange/v1/users/balances"
        payload = {"timestamp": int(time.time() * 1000)}
        return self._make_request(endpoint, "POST", payload)
    
    def place_order(self, symbol: str, side: OrderSide, order_type: OrderType, 
                   quantity: float, price: Optional[float] = None) -> Dict:
        """Place a trading order"""
        endpoint = "/exchange/v1/orders/create"
        
        payload = {
            "market": symbol,
            "side": side.value,
            "order_type": order_type.value,
            "total_quantity": quantity,
            "timestamp": int(time.time() * 1000)
        }
        
        if price and order_type == OrderType.LIMIT:
            payload["price_per_unit"] = price
        
        return self._make_request(endpoint, "POST", payload)
    
    def get_order_status(self, order_id: str) -> Dict:
        """Get status of a specific order"""
        endpoint = "/exchange/v1/orders/status"
        payload = {
            "id": order_id,
            "timestamp": int(time.time() * 1000)
        }
        return self._make_request(endpoint, "POST", payload)
    
    def cancel_order(self, order_id: str) -> Dict:
        """Cancel an order"""
        endpoint = "/exchange/v1/orders/cancel"
        payload = {
            "id": order_id,
            "timestamp": int(time.time() * 1000)
        }
        return self._make_request(endpoint, "POST", payload)


class TradingAI:
    """AI-powered trading decision engine"""
    
    def __init__(self):
        self.indicators_cache = {}
    
    def calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        if len(prices) < period + 1:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(prices) < period:
            return self.calculate_sma(prices, len(prices))
        
        multiplier = 2 / (period + 1)
        ema = self.calculate_sma(prices[:period], period)
        
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def analyze_market(self, symbol: str, prices: List[float], volume: List[float]) -> Dict:
        """Perform comprehensive market analysis"""
        if len(prices) < 20:
            return {"signal": "HOLD", "confidence": 0.0, "reason": "Insufficient data"}
        
        current_price = prices[-1]
        rsi = self.calculate_rsi(prices)
        sma_20 = self.calculate_sma(prices, 20)
        sma_50 = self.calculate_sma(prices, 50) if len(prices) >= 50 else sma_20
        ema_12 = self.calculate_ema(prices, 12)
        ema_26 = self.calculate_ema(prices, 26)
        
        # Calculate MACD
        macd = ema_12 - ema_26
        signal_line = self.calculate_ema([macd], 9)
        
        # Trend analysis
        trend = "BULLISH" if sma_20 < current_price else "BEARISH"
        momentum = "STRONG" if abs(current_price - sma_20) / sma_20 > 0.02 else "WEAK"
        
        # Generate trading signal
        buy_signals = 0
        sell_signals = 0
        
        # RSI signals
        if rsi < 30:
            buy_signals += 2
        elif rsi > 70:
            sell_signals += 2
        
        # Moving average crossover
        if sma_20 > sma_50:
            buy_signals += 1
        elif sma_20 < sma_50:
            sell_signals += 1
        
        # Price vs SMA
        if current_price > sma_20:
            buy_signals += 1
        else:
            sell_signals += 1
        
        # MACD
        if macd > signal_line:
            buy_signals += 1
        else:
            sell_signals += 1
        
        # Determine final signal
        if buy_signals > sell_signals + 1:
            signal = "BUY"
            confidence = min(buy_signals / 5.0, 1.0)
        elif sell_signals > buy_signals + 1:
            signal = "SELL"
            confidence = min(sell_signals / 5.0, 1.0)
        else:
            signal = "HOLD"
            confidence = 0.5
        
        return {
            "signal": signal,
            "confidence": confidence,
            "rsi": rsi,
            "trend": trend,
            "momentum": momentum,
            "current_price": current_price,
            "sma_20": sma_20,
            "sma_50": sma_50,
            "macd": macd,
            "reason": self._generate_reason(signal, rsi, trend, macd, signal_line)
        }
    
    def _generate_reason(self, signal: str, rsi: float, trend: str, macd: float, signal_line: float) -> str:
        """Generate human-readable reasoning for the signal"""
        reasons = []
        
        if rsi < 30:
            reasons.append("RSI indicates oversold condition")
        elif rsi > 70:
            reasons.append("RSI indicates overbought condition")
        
        if trend == "BULLISH":
            reasons.append("Price above moving averages (bullish trend)")
        else:
            reasons.append("Price below moving averages (bearish trend)")
        
        if macd > signal_line:
            reasons.append("MACD shows bullish momentum")
        else:
            reasons.append("MACD shows bearish momentum")
        
        return "; ".join(reasons) if reasons else "Mixed signals"


class Portfolio:
    """Portfolio management and tracking"""
    
    def __init__(self, initial_balance: float = 10000.0):
        self.initial_balance = initial_balance
        self.cash = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []
        self.balance_history = [initial_balance]
    
    def add_trade(self, trade: Trade):
        """Record a trade"""
        self.trade_history.append(trade)
        
        if trade.side == "buy":
            self.cash -= trade.total
            if trade.symbol in self.positions:
                pos = self.positions[trade.symbol]
                total_cost = (pos.avg_price * pos.quantity) + trade.total
                pos.quantity += trade.quantity
                pos.avg_price = total_cost / pos.quantity
            else:
                self.positions[trade.symbol] = Position(
                    symbol=trade.symbol,
                    quantity=trade.quantity,
                    avg_price=trade.price,
                    current_price=trade.price,
                    pnl=0.0,
                    pnl_percentage=0.0
                )
        else:  # sell
            self.cash += trade.total
            if trade.symbol in self.positions:
                self.positions[trade.symbol].quantity -= trade.quantity
                if self.positions[trade.symbol].quantity <= 0.0001:
                    del self.positions[trade.symbol]
    
    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for positions"""
        for symbol, price in prices.items():
            if symbol in self.positions:
                pos = self.positions[symbol]
                pos.current_price = price
                pos.pnl = (price - pos.avg_price) * pos.quantity
                pos.pnl_percentage = ((price - pos.avg_price) / pos.avg_price) * 100
    
    def get_total_value(self) -> float:
        """Calculate total portfolio value"""
        positions_value = sum(
            pos.quantity * pos.current_price 
            for pos in self.positions.values()
        )
        return self.cash + positions_value
    
    def get_performance(self) -> Dict:
        """Get portfolio performance metrics"""
        total_value = self.get_total_value()
        total_return = total_value - self.initial_balance
        total_return_pct = (total_return / self.initial_balance) * 100
        
        winning_trades = [t for t in self.trade_history if t.side == "sell" and t.status == "filled"]
        total_trades = len([t for t in self.trade_history if t.status == "filled"])
        
        return {
            "initial_balance": self.initial_balance,
            "current_value": total_value,
            "cash": self.cash,
            "total_return": total_return,
            "total_return_pct": total_return_pct,
            "total_trades": total_trades,
            "win_rate": (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
        }


class TradingAgent:
    """Main trading agent orchestrator"""
    
    def __init__(self, mode: TradingMode = TradingMode.PAPER, 
                 api_key: str = "", api_secret: str = "",
                 initial_balance: float = 10000.0):
        self.mode = mode
        self.client = CoinDCXClient(api_key, api_secret, mode)
        self.ai = TradingAI()
        self.portfolio = Portfolio(initial_balance)
        self.active = False
        self.watched_symbols = []
        self.price_history = {}
        
    def add_symbol(self, symbol: str):
        """Add a symbol to watch list"""
        if symbol not in self.watched_symbols:
            self.watched_symbols.append(symbol)
            self.price_history[symbol] = {"prices": [], "volumes": []}
            print(f"✓ Added {symbol} to watch list")
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from watch list"""
        if symbol in self.watched_symbols:
            self.watched_symbols.remove(symbol)
            print(f"✓ Removed {symbol} from watch list")
    
    def update_market_data(self):
        """Fetch and update market data for all watched symbols"""
        for symbol in self.watched_symbols:
            try:
                ticker = self.client.get_ticker(symbol)
                price = float(ticker.get('last_price', ticker.get('last', 0)))
                volume = float(ticker.get('volume', 0))
                
                self.price_history[symbol]["prices"].append(price)
                self.price_history[symbol]["volumes"].append(volume)
                
                # Keep last 100 data points
                if len(self.price_history[symbol]["prices"]) > 100:
                    self.price_history[symbol]["prices"].pop(0)
                    self.price_history[symbol]["volumes"].pop(0)
                
                # Update portfolio prices
                self.portfolio.update_prices({symbol: price})
                
            except Exception as e:
                print(f"Error updating {symbol}: {e}")
    
    def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """Analyze a specific symbol"""
        if symbol not in self.price_history:
            print(f"No data for {symbol}")
            return None
        
        prices = self.price_history[symbol]["prices"]
        volumes = self.price_history[symbol]["volumes"]
        
        if len(prices) < 20:
            print(f"Insufficient data for {symbol} (need at least 20 data points)")
            return None
        
        analysis = self.ai.analyze_market(symbol, prices, volumes)
        return analysis
    
    def execute_trade(self, symbol: str, side: OrderSide, quantity: float, 
                     price: Optional[float] = None, order_type: OrderType = OrderType.MARKET):
        """Execute a trade"""
        try:
            result = self.client.place_order(symbol, side, order_type, quantity, price)
            
            if result and 'orders' in result:
                order = result['orders'][0]
                trade_price = float(order.get('price', price or 0))
                if trade_price == 0 and symbol in self.price_history:
                    trade_price = self.price_history[symbol]["prices"][-1] if self.price_history[symbol]["prices"] else 0
                    
                trade = Trade(
                    timestamp=datetime.now().isoformat(),
                    symbol=symbol,
                    side=side.value,
                    price=trade_price,
                    quantity=quantity,
                    total=trade_price * quantity,
                    order_id=order.get('id', ''),
                    status=order.get('status', 'pending')
                )
                
                self.portfolio.add_trade(trade)
                print(f"\n✓ Trade executed: {side.value.upper()} {quantity} {symbol} @ ${trade.price:.2f}")
                print(f"  Order ID: {trade.order_id}")
                print(f"  Total: ${trade.total:.2f}")
                return trade
            else:
                print(f"✗ Trade failed: {result}")
                return None
                
        except Exception as e:
            print(f"✗ Error executing trade: {e}")
            return None
    
    def show_portfolio(self):
        """Display current portfolio status"""
        print("\n" + "="*60)
        print("PORTFOLIO STATUS")
        print("="*60)
        
        perf = self.portfolio.get_performance()
        print(f"\nCash Balance: ${self.portfolio.cash:,.2f}")
        print(f"Total Value: ${perf['current_value']:,.2f}")
        print(f"Total Return: ${perf['total_return']:,.2f} ({perf['total_return_pct']:.2f}%)")
        print(f"Total Trades: {perf['total_trades']}")
        print(f"Win Rate: {perf['win_rate']:.1f}%")
        
        if self.portfolio.positions:
            print("\n" + "-"*60)
            print("OPEN POSITIONS")
            print("-"*60)
            print(f"{'Symbol':<15} {'Qty':<12} {'Avg Price':<12} {'Current':<12} {'P&L':<15}")
            print("-"*60)
            
            for symbol, pos in self.portfolio.positions.items():
                pnl_color = "+" if pos.pnl >= 0 else "-"
                print(f"{symbol:<15} {pos.quantity:<12.6f} ${pos.avg_price:<11.2f} "
                      f"${pos.current_price:<11.2f} {pnl_color}${abs(pos.pnl):<7.2f} ({pos.pnl_percentage:+.2f}%)")
        
        print("="*60 + "\n")
    
    def show_analysis(self, symbol: str):
        """Display technical analysis for a symbol"""
        analysis = self.analyze_symbol(symbol)
        if not analysis:
            return
        
        print("\n" + "="*60)
        print(f"TECHNICAL ANALYSIS: {symbol}")
        print("="*60)
        print(f"\nCurrent Price: ${analysis['current_price']:.2f}")
        print(f"Signal: {analysis['signal']} (Confidence: {analysis['confidence']:.1%})")
        print(f"Trend: {analysis['trend']} - {analysis['momentum']}")
        print(f"\nIndicators:")
        print(f"  RSI: {analysis['rsi']:.2f}")
        print(f"  SMA(20): ${analysis['sma_20']:.2f}")
        print(f"  SMA(50): ${analysis['sma_50']:.2f}")
        print(f"  MACD: {analysis['macd']:.4f}")
        print(f"\nReason: {analysis['reason']}")
        print("="*60 + "\n")


def main():
    """Main CLI interface"""
    parser = argparse.ArgumentParser(description="Crypto Trading AI Agent")
    parser.add_argument("--mode", choices=["paper", "live"], default="paper", 
                       help="Trading mode (default: paper)")
    parser.add_argument("--api-key", default="", help="CoinDCX API Key")
    parser.add_argument("--api-secret", default="", help="CoinDCX API Secret")
    parser.add_argument("--balance", type=float, default=10000.0, 
                       help="Initial balance for paper trading (default: 10000)")
    
    args = parser.parse_args()
    
    mode = TradingMode.LIVE if args.mode == "live" else TradingMode.PAPER
    
    if mode == TradingMode.LIVE and (not args.api_key or not args.api_secret):
        print("✗ Error: API key and secret required for live trading")
        print("  Use --api-key and --api-secret arguments")
        sys.exit(1)
    
    agent = TradingAgent(mode, args.api_key, args.api_secret, args.balance)
    
    print("\n" + "="*60)
    print("CRYPTO TRADING AI AGENT")
    print("="*60)
    print(f"Mode: {mode.value.upper()}")
    if mode == TradingMode.PAPER:
        print(f"Initial Balance: ${args.balance:,.2f}")
    print("="*60 + "\n")
    
    print("Commands:")
    print("  add <symbol>          - Add symbol to watch list (e.g., add B-BTC_USDT)")
    print("  remove <symbol>       - Remove symbol from watch list")
    print("  list                  - Show watch list")
    print("  analyze <symbol>      - Analyze symbol")
    print("  buy <symbol> <qty>    - Buy cryptocurrency")
    print("  sell <symbol> <qty>   - Sell cryptocurrency")
    print("  portfolio             - Show portfolio status")
    print("  balance               - Show account balances")
    print("  update                - Update market data")
    print("  help                  - Show this help")
    print("  quit                  - Exit\n")
    
    while True:
        try:
            command = input("crypto-ai> ").strip().lower()
            
            if not command:
                continue
            
            parts = command.split()
            cmd = parts[0]
            
            if cmd == "quit" or cmd == "exit":
                print("Goodbye!")
                break
            
            elif cmd == "help":
                print("\nAvailable commands:")
                print("  add <symbol>          - Add symbol to watch list")
                print("  remove <symbol>       - Remove symbol from watch list")
                print("  list                  - Show watch list")
                print("  analyze <symbol>      - Analyze symbol")
                print("  buy <symbol> <qty>    - Buy cryptocurrency")
                print("  sell <symbol> <qty>   - Sell cryptocurrency")
                print("  portfolio             - Show portfolio status")
                print("  balance               - Show account balances")
                print("  update                - Update market data")
                print("  quit                  - Exit\n")
            
            elif cmd == "add" and len(parts) > 1:
                agent.add_symbol(parts[1].upper())
            
            elif cmd == "remove" and len(parts) > 1:
                agent.remove_symbol(parts[1].upper())
            
            elif cmd == "list":
                if agent.watched_symbols:
                    print("\nWatched Symbols:")
                    for symbol in agent.watched_symbols:
                        print(f"  - {symbol}")
                    print()
                else:
                    print("\nNo symbols in watch list\n")
            
            elif cmd == "update":
                print("Updating market data...")
                agent.update_market_data()
                print("✓ Market data updated\n")
            
            elif cmd == "analyze" and len(parts) > 1:
                symbol = parts[1].upper()
                if symbol not in agent.watched_symbols:
                    print(f"Symbol {symbol} not in watch list. Adding it...")
                    agent.add_symbol(symbol)
                    agent.update_market_data()
                agent.show_analysis(symbol)
            
            elif cmd == "buy" and len(parts) >= 3:
                symbol = parts[1].upper()
                try:
                    quantity = float(parts[2])
                    if symbol not in agent.watched_symbols:
                        agent.add_symbol(symbol)
                        agent.update_market_data()
                    agent.execute_trade(symbol, OrderSide.BUY, quantity)
                except ValueError:
                    print("✗ Invalid quantity\n")
            
            elif cmd == "sell" and len(parts) >= 3:
                symbol = parts[1].upper()
                try:
                    quantity = float(parts[2])
                    agent.execute_trade(symbol, OrderSide.SELL, quantity)
                except ValueError:
                    print("✗ Invalid quantity\n")
            
            elif cmd == "portfolio":
                agent.show_portfolio()
            
            elif cmd == "balance":
                print("\nFetching account balances...")
                balances = agent.client.get_balances()
                print("\n" + "="*60)
                print("ACCOUNT BALANCES")
                print("="*60)
                for bal in balances:
                    if isinstance(bal, dict):
                        currency = bal.get('currency', 'Unknown')
                        balance = float(bal.get('balance', 0))
                        locked = float(bal.get('locked_balance', 0))
                        if balance > 0 or locked > 0:
                            print(f"{currency:<10} Available: {balance:<15.8f} Locked: {locked:.8f}")
                print("="*60 + "\n")
            
            else:
                print(f"✗ Unknown command: {cmd}")
                print("  Type 'help' for available commands\n")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"✗ Error: {e}\n")


if __name__ == "__main__":
    main()
