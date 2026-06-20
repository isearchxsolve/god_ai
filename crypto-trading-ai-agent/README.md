# Crypto Trading AI Agent

A sophisticated cryptocurrency trading agent with AI-powered decision making, technical analysis, and CoinDCX integration. Supports both paper trading and live trading modes.

## Features

### Core Functionality
- **Dual Trading Modes**: Paper trading for testing and live trading for real execution
- **CoinDCX Integration**: Full API integration with CoinDCX exchange
- **AI-Powered Analysis**: Advanced technical analysis with multiple indicators
- **Multiple Strategies**: Momentum, mean reversion, and breakout strategies
- **Risk Management**: Configurable position sizing, stop loss, and take profit
- **Portfolio Tracking**: Real-time P&L tracking and performance metrics
- **Command-Line Interface**: Easy-to-use CLI for all trading operations

### Technical Indicators
- **RSI** (Relative Strength Index)
- **SMA** (Simple Moving Average)
- **EMA** (Exponential Moving Average)
- **MACD** (Moving Average Convergence Divergence)
- **Bollinger Bands**
- **ATR** (Average True Range)
- **Volume Analysis**

### Trading Strategies
1. **Momentum Strategy**: Identifies trends using RSI, MACD, and volume
2. **Mean Reversion Strategy**: Trades based on Bollinger Bands and price deviations
3. **Breakout Strategy**: Detects breakouts above resistance or below support
4. **Consensus Mode**: Combines all strategies for robust signals

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager
- CoinDCX account (for live trading)

### Setup

1. **Clone or download the project**
```bash
mkdir crypto-trading-ai
cd crypto-trading-ai
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure API credentials** (for live trading only)
   - Get your API key and secret from CoinDCX
   - Either pass them as command-line arguments or set in config.json

## Usage

### Quick Start - Paper Trading

Start the trading agent in paper trading mode (default):

```bash
python crypto_trading_agent.py
```

With custom initial balance:
```bash
python crypto_trading_agent.py --balance 50000
```

### Live Trading

For live trading, you need CoinDCX API credentials:

```bash
python crypto_trading_agent.py --mode live --api-key YOUR_API_KEY --api-secret YOUR_API_SECRET
```

### Command Reference

Once the agent is running, use these commands:

#### Symbol Management
```bash
add <symbol>           # Add symbol to watchlist (e.g., add B-BTC_USDT)
remove <symbol>        # Remove symbol from watchlist
list                   # Show all watched symbols
```

#### Market Analysis
```bash
update                 # Update market data for all watched symbols
analyze <symbol>       # Perform technical analysis on a symbol
```

#### Trading Operations
```bash
buy <symbol> <qty>     # Buy cryptocurrency (e.g., buy B-BTC_USDT 0.01)
sell <symbol> <qty>    # Sell cryptocurrency
portfolio              # Show current portfolio status
balance                # Show account balances
```

#### Utility
```bash
help                   # Show available commands
quit                   # Exit the program
```

### Example Workflow

```bash
# Start the agent
python crypto_trading_agent.py

# Add cryptocurrencies to watch
crypto-ai> add B-BTC_USDT
crypto-ai> add B-ETH_USDT
crypto-ai> add I-SOL_USDT

# Update market data
crypto-ai> update

# Analyze a symbol
crypto-ai> analyze B-BTC_USDT

# Execute a trade based on analysis
crypto-ai> buy B-BTC_USDT 0.001

# Check your portfolio
crypto-ai> portfolio

# View account balances
crypto-ai> balance
```

## CoinDCX Symbol Format

CoinDCX uses specific symbol formats:
- **B-** prefix: CoinDCX markets (e.g., B-BTC_USDT, B-ETH_USDT)
- **I-** prefix: International markets (e.g., I-BTC_USDT, I-ETH_USDT)

Common symbols:
- `B-BTC_USDT` - Bitcoin
- `B-ETH_USDT` - Ethereum
- `I-BNB_USDT` - Binance Coin
- `I-ADA_USDT` - Cardano
- `I-SOL_USDT` - Solana

## Configuration

The agent can be configured through `config.json`:

```json
{
  "api": {
    "coindcx_key": "your-api-key",
    "coindcx_secret": "your-api-secret"
  },
  "trading": {
    "default_mode": "paper",
    "initial_balance": 10000.0,
    "risk_per_trade": 0.02,
    "max_position_size": 0.1,
    "stop_loss_pct": 0.05,
    "take_profit_pct": 0.10
  },
  "strategies": {
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "sma_fast": 20,
    "sma_slow": 50
  }
}
```

### Configuration Parameters

#### Trading Settings
- `risk_per_trade`: Maximum risk per trade as % of account (default: 2%)
- `max_position_size`: Maximum position size as % of account (default: 10%)
- `stop_loss_pct`: Stop loss percentage (default: 5%)
- `take_profit_pct`: Take profit percentage (default: 10%)

#### Strategy Parameters
- `rsi_oversold`: RSI level for oversold condition (default: 30)
- `rsi_overbought`: RSI level for overbought condition (default: 70)
- `sma_fast`: Fast SMA period (default: 20)
- `sma_slow`: Slow SMA period (default: 50)

## Advanced Features

### Using Different Strategies

The agent includes multiple trading strategies that can be used independently:

```python
from strategies import StrategyManager

# Create strategy manager
manager = StrategyManager()

# Get signal from specific strategy
signal = manager.get_signal(market_data, 'momentum')

# Get consensus signal from all strategies
consensus = manager.get_consensus_signal(market_data)
```

### Risk Management

The agent includes comprehensive risk management:

```python
from config_manager import RiskManager, ConfigManager

config = ConfigManager()
risk_mgr = RiskManager(config)

# Calculate position size based on risk
position_size = risk_mgr.calculate_position_size(
    account_balance=10000,
    entry_price=45000,
    stop_loss_price=43000
)

# Calculate stop loss and take profit
stop_loss = risk_mgr.calculate_stop_loss(entry_price=45000, side='buy')
take_profit = risk_mgr.calculate_take_profit(entry_price=45000, side='buy')
```

### Trade Logging

All trades are automatically logged:

```python
from config_manager import TradeLogger

logger = TradeLogger()

# Trades are logged in logs/trades.jsonl
# Performance metrics in logs/performance.json
```

## Technical Analysis Explained

### RSI (Relative Strength Index)
- **Range**: 0-100
- **Oversold**: Below 30 (potential buy signal)
- **Overbought**: Above 70 (potential sell signal)
- **Neutral**: 40-60

### MACD (Moving Average Convergence Divergence)
- **Bullish**: MACD line crosses above signal line
- **Bearish**: MACD line crosses below signal line
- **Momentum**: Distance between MACD and signal line

### Bollinger Bands
- **Upper Band**: Resistance level
- **Lower Band**: Support level
- **Price at upper**: Overbought condition
- **Price at lower**: Oversold condition

## Paper Trading vs Live Trading

### Paper Trading (Default)
- Simulated trading environment
- No real money at risk
- Perfect for testing strategies
- Uses simulated market data and order execution
- Great for learning and experimentation

### Live Trading
- Real money trading on CoinDCX
- Requires API credentials
- Real-time market data
- Actual order execution
- **Use with caution and proper risk management**

## Safety and Best Practices

### Risk Management
1. Never risk more than 1-2% of your account on a single trade
2. Always use stop losses
3. Diversify across multiple cryptocurrencies
4. Start with small position sizes

### Testing
1. Always test new strategies in paper trading mode first
2. Verify your API credentials work correctly
3. Understand the technical analysis before trading
4. Monitor trades closely, especially when starting

### Security
1. Never share your API keys
2. Use API keys with trading-only permissions (no withdrawal)
3. Regularly rotate API keys
4. Keep your credentials in environment variables or secure config files

## Troubleshooting

### Common Issues

**"Insufficient data for analysis"**
- Solution: Run `update` command multiple times to collect more price data
- Need at least 20 data points for basic analysis

**"API authentication failed"**
- Check your API key and secret are correct
- Ensure API key has trading permissions
- Verify you're using the correct CoinDCX account

**"Trade exceeds max position size"**
- Reduce trade quantity
- Adjust `max_position_size` in config.json

**"Symbol not found"**
- Verify symbol format (B-BTC_USDT not BTC-USDT)
- Check symbol exists on CoinDCX
- Use `list` command to see valid symbols

## Project Structure

```
crypto-trading-ai/
├── crypto_trading_agent.py    # Main trading agent
├── config_manager.py           # Configuration and risk management
├── strategies.py               # Trading strategies
├── requirements.txt            # Python dependencies
├── config.json                 # Configuration file
├── README.md                   # This file
└── logs/                       # Trade and performance logs
    ├── trades.jsonl
    └── performance.json
```

## Dependencies

- **requests**: HTTP requests for API calls
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computations
- **tabulate**: Pretty table printing
- **colorama**: Colored terminal output
- **python-dotenv**: Environment variable management

## Disclaimer

**IMPORTANT**: This software is for educational purposes only. Cryptocurrency trading carries significant risk of financial loss. The developers are not responsible for any financial losses incurred through the use of this software.

- Past performance does not guarantee future results
- Always do your own research (DYOR)
- Never invest more than you can afford to lose
- This is not financial advice

## Contributing

Contributions are welcome! Areas for improvement:
- Additional trading strategies
- More technical indicators
- Better visualization
- Backtesting capabilities
- Machine learning integration
- Multi-exchange support

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
1. Check this README thoroughly
2. Review CoinDCX API documentation
3. Test in paper trading mode first
4. Start with small amounts in live trading

## Acknowledgments

- CoinDCX for providing the API
- The cryptocurrency trading community
- Open source technical analysis libraries

---

**Happy Trading! 🚀📈**
