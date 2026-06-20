"""
Configuration Manager for Crypto Trading AI Agent
"""

import os
import json
from typing import Dict, Optional
from pathlib import Path


class ConfigManager:
    """Manage configuration and API credentials"""
    
    def __init__(self, config_file: str = "config.json"):
        self.config_file = config_file
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self._create_default_config()
    
    def _create_default_config(self) -> Dict:
        """Create default configuration"""
        return {
            "api": {
                "coindcx_key": "",
                "coindcx_secret": ""
            },
            "trading": {
                "default_mode": "paper",
                "initial_balance": 10000.0,
                "risk_per_trade": 0.02,  # 2% risk per trade
                "max_position_size": 0.1,  # 10% max position
                "stop_loss_pct": 0.05,  # 5% stop loss
                "take_profit_pct": 0.10  # 10% take profit
            },
            "watchlist": [],
            "strategies": {
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "sma_fast": 20,
                "sma_slow": 50,
                "macd_fast": 12,
                "macd_slow": 26,
                "macd_signal": 9
            }
        }
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get(self, key: str, default=None):
        """Get configuration value"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def set(self, key: str, value):
        """Set configuration value"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
    
    def add_to_watchlist(self, symbol: str):
        """Add symbol to watchlist"""
        if "watchlist" not in self.config:
            self.config["watchlist"] = []
        if symbol not in self.config["watchlist"]:
            self.config["watchlist"].append(symbol)
            self.save_config()
    
    def remove_from_watchlist(self, symbol: str):
        """Remove symbol from watchlist"""
        if "watchlist" in self.config and symbol in self.config["watchlist"]:
            self.config["watchlist"].remove(symbol)
            self.save_config()
    
    def get_watchlist(self) -> list:
        """Get watchlist"""
        return self.config.get("watchlist", [])


class TradeLogger:
    """Log trades and performance"""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.trade_log = self.log_dir / "trades.jsonl"
        self.performance_log = self.log_dir / "performance.json"
    
    def log_trade(self, trade_data: Dict):
        """Log a trade"""
        with open(self.trade_log, 'a') as f:
            f.write(json.dumps(trade_data) + '\n')
    
    def log_performance(self, performance_data: Dict):
        """Log performance metrics"""
        with open(self.performance_log, 'w') as f:
            json.dump(performance_data, f, indent=2)
    
    def get_trade_history(self) -> list:
        """Get trade history"""
        if not self.trade_log.exists():
            return []
        
        trades = []
        with open(self.trade_log, 'r') as f:
            for line in f:
                trades.append(json.loads(line))
        return trades
    
    def get_performance(self) -> Dict:
        """Get performance data"""
        if not self.performance_log.exists():
            return {}
        
        with open(self.performance_log, 'r') as f:
            return json.load(f)


class RiskManager:
    """Manage trading risk"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    def calculate_position_size(self, account_balance: float, 
                               entry_price: float, 
                               stop_loss_price: float) -> float:
        """Calculate position size based on risk management"""
        risk_per_trade = self.config.get('trading.risk_per_trade', 0.02)
        max_position_size = self.config.get('trading.max_position_size', 0.1)
        
        # Calculate risk amount
        risk_amount = account_balance * risk_per_trade
        
        # Calculate position size based on stop loss
        price_risk = abs(entry_price - stop_loss_price)
        if price_risk == 0:
            return 0
        
        position_size = risk_amount / price_risk
        
        # Apply max position size limit
        max_position_value = account_balance * max_position_size
        if position_size * entry_price > max_position_value:
            position_size = max_position_value / entry_price
        
        return position_size
    
    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price"""
        stop_loss_pct = self.config.get('trading.stop_loss_pct', 0.05)
        
        if side.lower() == 'buy':
            return entry_price * (1 - stop_loss_pct)
        else:
            return entry_price * (1 + stop_loss_pct)
    
    def calculate_take_profit(self, entry_price: float, side: str) -> float:
        """Calculate take profit price"""
        take_profit_pct = self.config.get('trading.take_profit_pct', 0.10)
        
        if side.lower() == 'buy':
            return entry_price * (1 + take_profit_pct)
        else:
            return entry_price * (1 - take_profit_pct)
    
    def validate_trade(self, symbol: str, quantity: float, 
                      price: float, account_balance: float) -> tuple[bool, str]:
        """Validate if trade meets risk parameters"""
        trade_value = quantity * price
        
        # Check if trade exceeds max position size
        max_position_value = account_balance * self.config.get('trading.max_position_size', 0.1)
        if trade_value > max_position_value:
            return False, f"Trade exceeds max position size (${max_position_value:.2f})"
        
        # Check if sufficient balance
        if trade_value > account_balance:
            return False, "Insufficient account balance"
        
        return True, "Trade validated"


if __name__ == "__main__":
    # Test configuration manager
    config = ConfigManager()
    print("Configuration loaded:", config.config)
    
    # Test trade logger
    logger = TradeLogger()
    logger.log_trade({
        "timestamp": "2024-01-01T12:00:00",
        "symbol": "BTC-USDT",
        "side": "buy",
        "price": 45000,
        "quantity": 0.1
    })
    print("Trade logged")
    
    # Test risk manager
    risk_mgr = RiskManager(config)
    position_size = risk_mgr.calculate_position_size(10000, 45000, 43000)
    print(f"Calculated position size: {position_size}")
