"""
Advanced Trading Strategies for Crypto Trading AI Agent
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
import numpy as np


class StrategyType(Enum):
    """Trading strategy types"""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    SWING = "swing"


class TradingStrategy:
    """Base class for trading strategies"""
    
    def __init__(self, name: str, params: Dict = None):
        self.name = name
        self.params = params or {}
    
    def generate_signal(self, market_data: Dict) -> Dict:
        """Generate trading signal"""
        raise NotImplementedError
    
    def calculate_entry_exit(self, current_price: float) -> Tuple[float, float, float]:
        """Calculate entry, stop loss, and take profit prices"""
        raise NotImplementedError


class MomentumStrategy(TradingStrategy):
    """Momentum-based trading strategy"""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'rsi_period': 14,
            'rsi_oversold': 30,
            'rsi_overbought': 70,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'volume_threshold': 1.5  # 50% above average
        }
        if params:
            default_params.update(params)
        super().__init__("Momentum Strategy", default_params)
    
    def generate_signal(self, market_data: Dict) -> Dict:
        """
        Generate signal based on momentum indicators
        
        Args:
            market_data: Dict with 'prices', 'volumes', 'rsi', 'macd', etc.
        
        Returns:
            Dict with signal, confidence, and reasoning
        """
        rsi = market_data.get('rsi', 50)
        macd = market_data.get('macd', 0)
        macd_signal = market_data.get('macd_signal', 0)
        volume = market_data.get('current_volume', 0)
        avg_volume = market_data.get('avg_volume', 0)
        
        signal = "HOLD"
        confidence = 0.0
        reasons = []
        
        # RSI signals
        if rsi < self.params['rsi_oversold']:
            signal = "BUY"
            confidence += 0.3
            reasons.append(f"RSI oversold at {rsi:.1f}")
        elif rsi > self.params['rsi_overbought']:
            signal = "SELL"
            confidence += 0.3
            reasons.append(f"RSI overbought at {rsi:.1f}")
        
        # MACD signals
        if macd > macd_signal and macd > 0:
            if signal == "BUY" or signal == "HOLD":
                signal = "BUY"
                confidence += 0.3
                reasons.append("MACD bullish crossover")
        elif macd < macd_signal and macd < 0:
            if signal == "SELL" or signal == "HOLD":
                signal = "SELL"
                confidence += 0.3
                reasons.append("MACD bearish crossover")
        
        # Volume confirmation
        if avg_volume > 0:
            volume_ratio = volume / avg_volume
            if volume_ratio > self.params['volume_threshold']:
                confidence += 0.2
                reasons.append(f"High volume ({volume_ratio:.1f}x avg)")
        
        return {
            'signal': signal,
            'confidence': min(confidence, 1.0),
            'reasons': reasons,
            'strategy': self.name
        }
    
    def calculate_entry_exit(self, current_price: float) -> Tuple[float, float, float]:
        """Calculate entry, stop loss, and take profit"""
        entry = current_price
        stop_loss = current_price * 0.97  # 3% stop loss
        take_profit = current_price * 1.06  # 6% take profit
        return entry, stop_loss, take_profit


class MeanReversionStrategy(TradingStrategy):
    """Mean reversion trading strategy"""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'bb_period': 20,
            'bb_std': 2,
            'rsi_period': 14,
            'deviation_threshold': 2.0
        }
        if params:
            default_params.update(params)
        super().__init__("Mean Reversion Strategy", default_params)
    
    def calculate_bollinger_bands(self, prices: List[float]) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands"""
        period = self.params['bb_period']
        std_dev = self.params['bb_std']
        
        if len(prices) < period:
            return 0, 0, 0
        
        sma = sum(prices[-period:]) / period
        variance = sum((x - sma) ** 2 for x in prices[-period:]) / period
        std = variance ** 0.5
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    def generate_signal(self, market_data: Dict) -> Dict:
        """Generate mean reversion signal"""
        prices = market_data.get('prices', [])
        
        if len(prices) < self.params['bb_period']:
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reasons': ['Insufficient data'],
                'strategy': self.name
            }
        
        current_price = prices[-1]
        upper_bb, middle_bb, lower_bb = self.calculate_bollinger_bands(prices)
        
        signal = "HOLD"
        confidence = 0.0
        reasons = []
        
        # Price relative to Bollinger Bands
        if current_price <= lower_bb:
            signal = "BUY"
            deviation = (lower_bb - current_price) / lower_bb
            confidence = min(deviation * 5, 0.9)  # Scale confidence
            reasons.append(f"Price below lower BB (deviation: {deviation:.2%})")
        elif current_price >= upper_bb:
            signal = "SELL"
            deviation = (current_price - upper_bb) / upper_bb
            confidence = min(deviation * 5, 0.9)
            reasons.append(f"Price above upper BB (deviation: {deviation:.2%})")
        
        # Additional RSI confirmation
        rsi = market_data.get('rsi', 50)
        if signal == "BUY" and rsi < 40:
            confidence += 0.1
            reasons.append("RSI confirms oversold")
        elif signal == "SELL" and rsi > 60:
            confidence += 0.1
            reasons.append("RSI confirms overbought")
        
        return {
            'signal': signal,
            'confidence': min(confidence, 1.0),
            'reasons': reasons,
            'strategy': self.name,
            'bb_upper': upper_bb,
            'bb_middle': middle_bb,
            'bb_lower': lower_bb
        }
    
    def calculate_entry_exit(self, current_price: float) -> Tuple[float, float, float]:
        """Calculate entry, stop loss, and take profit"""
        entry = current_price
        stop_loss = current_price * 0.98  # 2% stop loss
        take_profit = current_price * 1.04  # 4% take profit
        return entry, stop_loss, take_profit


class BreakoutStrategy(TradingStrategy):
    """Breakout trading strategy"""
    
    def __init__(self, params: Dict = None):
        default_params = {
            'lookback_period': 20,
            'volume_multiplier': 1.5,
            'atr_multiplier': 2.0
        }
        if params:
            default_params.update(params)
        super().__init__("Breakout Strategy", default_params)
    
    def calculate_atr(self, prices: List[float], period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(prices) < period + 1:
            return 0
        
        true_ranges = []
        for i in range(1, len(prices)):
            high_low = abs(prices[i] - prices[i-1])
            true_ranges.append(high_low)
        
        return sum(true_ranges[-period:]) / period if true_ranges else 0
    
    def generate_signal(self, market_data: Dict) -> Dict:
        """Generate breakout signal"""
        prices = market_data.get('prices', [])
        volumes = market_data.get('volumes', [])
        
        period = self.params['lookback_period']
        
        if len(prices) < period:
            return {
                'signal': 'HOLD',
                'confidence': 0.0,
                'reasons': ['Insufficient data'],
                'strategy': self.name
            }
        
        current_price = prices[-1]
        current_volume = volumes[-1] if volumes else 0
        avg_volume = sum(volumes[-period:]) / period if volumes else 0
        
        # Find support and resistance
        recent_high = max(prices[-period:-1])
        recent_low = min(prices[-period:-1])
        
        signal = "HOLD"
        confidence = 0.0
        reasons = []
        
        # Breakout above resistance
        if current_price > recent_high:
            signal = "BUY"
            breakout_strength = (current_price - recent_high) / recent_high
            confidence = min(breakout_strength * 10, 0.7)
            reasons.append(f"Breakout above resistance at ${recent_high:.2f}")
            
            # Volume confirmation
            if current_volume > avg_volume * self.params['volume_multiplier']:
                confidence += 0.2
                reasons.append("Strong volume confirmation")
        
        # Breakdown below support
        elif current_price < recent_low:
            signal = "SELL"
            breakdown_strength = (recent_low - current_price) / recent_low
            confidence = min(breakdown_strength * 10, 0.7)
            reasons.append(f"Breakdown below support at ${recent_low:.2f}")
            
            # Volume confirmation
            if current_volume > avg_volume * self.params['volume_multiplier']:
                confidence += 0.2
                reasons.append("Strong volume confirmation")
        
        return {
            'signal': signal,
            'confidence': min(confidence, 1.0),
            'reasons': reasons,
            'strategy': self.name,
            'resistance': recent_high,
            'support': recent_low
        }
    
    def calculate_entry_exit(self, current_price: float) -> Tuple[float, float, float]:
        """Calculate entry, stop loss, and take profit"""
        atr = current_price * 0.02  # Simplified ATR
        entry = current_price
        stop_loss = current_price - (atr * self.params['atr_multiplier'])
        take_profit = current_price + (atr * self.params['atr_multiplier'] * 1.5)
        return entry, stop_loss, take_profit


class StrategyManager:
    """Manage multiple trading strategies"""
    
    def __init__(self):
        self.strategies = {
            'momentum': MomentumStrategy(),
            'mean_reversion': MeanReversionStrategy(),
            'breakout': BreakoutStrategy()
        }
        self.active_strategy = 'momentum'
    
    def add_strategy(self, name: str, strategy: TradingStrategy):
        """Add a custom strategy"""
        self.strategies[name] = strategy
    
    def set_active_strategy(self, name: str):
        """Set the active trading strategy"""
        if name in self.strategies:
            self.active_strategy = name
        else:
            raise ValueError(f"Strategy '{name}' not found")
    
    def get_signal(self, market_data: Dict, strategy_name: Optional[str] = None) -> Dict:
        """Get trading signal from strategy"""
        strategy_name = strategy_name or self.active_strategy
        if strategy_name not in self.strategies:
            raise ValueError(f"Strategy '{strategy_name}' not found")
        
        return self.strategies[strategy_name].generate_signal(market_data)
    
    def get_consensus_signal(self, market_data: Dict) -> Dict:
        """Get consensus signal from all strategies"""
        signals = []
        
        for name, strategy in self.strategies.items():
            signal = strategy.generate_signal(market_data)
            signals.append(signal)
        
        # Count votes
        buy_votes = sum(1 for s in signals if s['signal'] == 'BUY')
        sell_votes = sum(1 for s in signals if s['signal'] == 'SELL')
        
        # Calculate average confidence
        buy_confidence = np.mean([s['confidence'] for s in signals if s['signal'] == 'BUY']) if buy_votes > 0 else 0
        sell_confidence = np.mean([s['confidence'] for s in signals if s['signal'] == 'SELL']) if sell_votes > 0 else 0
        
        # Determine consensus
        if buy_votes > sell_votes:
            final_signal = 'BUY'
            final_confidence = buy_confidence
        elif sell_votes > buy_votes:
            final_signal = 'SELL'
            final_confidence = sell_confidence
        else:
            final_signal = 'HOLD'
            final_confidence = 0.5
        
        all_reasons = []
        for signal in signals:
            all_reasons.extend([f"{signal['strategy']}: {r}" for r in signal.get('reasons', [])])
        
        return {
            'signal': final_signal,
            'confidence': final_confidence,
            'buy_votes': buy_votes,
            'sell_votes': sell_votes,
            'reasons': all_reasons,
            'strategy': 'Consensus'
        }


if __name__ == "__main__":
    # Test strategies
    manager = StrategyManager()
    
    # Mock market data
    market_data = {
        'prices': [100 + i * 0.5 for i in range(50)],
        'volumes': [1000 + i * 10 for i in range(50)],
        'rsi': 35,
        'macd': 0.5,
        'macd_signal': 0.3,
        'current_volume': 1500,
        'avg_volume': 1000
    }
    
    print("Testing Strategies:")
    print("="*60)
    
    for name in ['momentum', 'mean_reversion', 'breakout']:
        signal = manager.get_signal(market_data, name)
        print(f"\n{name.upper()} Strategy:")
        print(f"  Signal: {signal['signal']}")
        print(f"  Confidence: {signal['confidence']:.2%}")
        print(f"  Reasons: {', '.join(signal.get('reasons', []))}")
    
    print("\n" + "="*60)
    consensus = manager.get_consensus_signal(market_data)
    print("\nCONSENSUS Signal:")
    print(f"  Signal: {consensus['signal']}")
    print(f"  Confidence: {consensus['confidence']:.2%}")
    print(f"  Buy Votes: {consensus['buy_votes']}")
    print(f"  Sell Votes: {consensus['sell_votes']}")
