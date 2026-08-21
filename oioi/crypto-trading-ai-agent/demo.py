#!/usr/bin/env python3
"""
Demo script to showcase the Crypto Trading AI Agent capabilities
"""

import time
from crypto_trading_agent import TradingAgent, TradingMode, OrderSide
from strategies import StrategyManager


def print_separator(title=""):
    """Print a formatted separator"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}\n")
    else:
        print("="*60)


def demo_paper_trading():
    """Demonstrate paper trading functionality"""
    print_separator("CRYPTO TRADING AI AGENT - DEMO")
    
    # Initialize agent in paper trading mode
    print("Initializing agent in PAPER TRADING mode...")
    agent = TradingAgent(
        mode=TradingMode.PAPER,
        initial_balance=10000.0
    )
    print("✓ Agent initialized with $10,000 balance\n")
    
    # Add symbols to watch
    print_separator("Step 1: Adding Symbols to Watchlist")
    symbols = ["B-BTC_USDT", "B-ETH_USDT", "I-SOL_USDT"]
    
    for symbol in symbols:
        agent.add_symbol(symbol)
    
    print("\nWatched symbols:")
    for symbol in agent.watched_symbols:
        print(f"  ✓ {symbol}")
    
    # Update market data
    print_separator("Step 2: Fetching Market Data")
    print("Collecting price data (this may take a moment)...\n")
    
    for i in range(25):
        agent.update_market_data()
        if (i + 1) % 5 == 0:
            print(f"  Data points collected: {i + 1}/25")
        time.sleep(0.1)  # Small delay to simulate real data collection
    
    print("\n✓ Market data collected successfully")
    
    # Analyze first symbol
    print_separator("Step 3: Technical Analysis")
    symbol = "B-BTC_USDT"
    print(f"Analyzing {symbol}...\n")
    agent.show_analysis(symbol)
    
    # Execute a trade
    print_separator("Step 4: Executing Trade")
    print(f"Executing BUY order for {symbol}...")
    agent.execute_trade(symbol, OrderSide.BUY, 0.01)
    
    # Show portfolio
    print_separator("Step 5: Portfolio Status")
    agent.show_portfolio()
    
    # Demonstrate strategy manager
    print_separator("Step 6: Advanced Strategy Analysis")
    
    if symbol in agent.price_history and len(agent.price_history[symbol]["prices"]) >= 20:
        manager = StrategyManager()
        
        market_data = {
            'prices': agent.price_history[symbol]["prices"],
            'volumes': agent.price_history[symbol]["volumes"],
            'rsi': agent.ai.calculate_rsi(agent.price_history[symbol]["prices"]),
            'macd': 0,
            'macd_signal': 0,
            'current_volume': agent.price_history[symbol]["volumes"][-1] if agent.price_history[symbol]["volumes"] else 0,
            'avg_volume': sum(agent.price_history[symbol]["volumes"][-20:]) / 20 if len(agent.price_history[symbol]["volumes"]) >= 20 else 0
        }
        
        print("Testing different strategies:\n")
        
        for strategy_name in ['momentum', 'mean_reversion', 'breakout']:
            signal = manager.get_signal(market_data, strategy_name)
            print(f"{strategy_name.upper()} Strategy:")
            print(f"  Signal: {signal['signal']}")
            print(f"  Confidence: {signal['confidence']:.1%}")
            if signal.get('reasons'):
                print(f"  Reason: {signal['reasons'][0]}")
            print()
        
        # Consensus signal
        consensus = manager.get_consensus_signal(market_data)
        print("CONSENSUS Signal:")
        print(f"  Signal: {consensus['signal']}")
        print(f"  Confidence: {consensus['confidence']:.1%}")
        print(f"  Buy Votes: {consensus['buy_votes']}")
        print(f"  Sell Votes: {consensus['sell_votes']}")
    
    print_separator("Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("  ✓ Paper trading mode (no real money)")
    print("  ✓ Multi-symbol tracking")
    print("  ✓ Real-time market data collection")
    print("  ✓ Technical analysis with multiple indicators")
    print("  ✓ Trade execution and tracking")
    print("  ✓ Portfolio management")
    print("  ✓ Multiple trading strategies")
    print("  ✓ Consensus signal generation")
    
    print("\nNext Steps:")
    print("  1. Run: python crypto_trading_agent.py")
    print("  2. Try the interactive CLI")
    print("  3. Practice with paper trading")
    print("  4. Read QUICKSTART.md for guided tutorial")
    print("\n" + "="*60 + "\n")


def demo_risk_management():
    """Demonstrate risk management features"""
    from config_manager import RiskManager, ConfigManager
    
    print_separator("Risk Management Demo")
    
    config = ConfigManager()
    risk_mgr = RiskManager(config)
    
    account_balance = 10000.0
    entry_price = 45000.0
    
    print(f"Account Balance: ${account_balance:,.2f}")
    print(f"Entry Price: ${entry_price:,.2f}\n")
    
    # Calculate stop loss
    stop_loss = risk_mgr.calculate_stop_loss(entry_price, 'buy')
    print(f"Stop Loss: ${stop_loss:,.2f} ({((entry_price - stop_loss) / entry_price * 100):.1f}% below entry)")
    
    # Calculate take profit
    take_profit = risk_mgr.calculate_take_profit(entry_price, 'buy')
    print(f"Take Profit: ${take_profit:,.2f} ({((take_profit - entry_price) / entry_price * 100):.1f}% above entry)")
    
    # Calculate position size
    position_size = risk_mgr.calculate_position_size(account_balance, entry_price, stop_loss)
    print(f"\nRecommended Position Size: {position_size:.6f} BTC")
    print(f"Position Value: ${position_size * entry_price:,.2f}")
    print(f"Risk Amount: ${account_balance * 0.02:,.2f} (2% of account)")
    
    # Validate trade
    is_valid, message = risk_mgr.validate_trade("BTC", position_size, entry_price, account_balance)
    print(f"\nTrade Validation: {'✓ VALID' if is_valid else '✗ INVALID'}")
    print(f"Message: {message}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  CRYPTO TRADING AI AGENT - COMPREHENSIVE DEMO")
    print("="*60 + "\n")
    
    print("This demo will showcase:")
    print("  • Paper trading functionality")
    print("  • Technical analysis")
    print("  • Trading strategies")
    print("  • Risk management")
    print("\nStarting demo in 2 seconds...\n")
    
    time.sleep(2)
    
    # Run main demo
    demo_paper_trading()
    
    # Run risk management demo
    demo_risk_management()
    
    print("Demo completed! 🚀")
    print("\nTo start trading:")
    print("  python crypto_trading_agent.py\n")
