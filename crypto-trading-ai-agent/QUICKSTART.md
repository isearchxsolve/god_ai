# Quick Start Guide - Crypto Trading AI Agent

## 5-Minute Setup

### Step 1: Install Dependencies
```bash
pip install requests pandas numpy tabulate colorama python-dotenv
```

### Step 2: Start Paper Trading (No API Required)
```bash
python crypto_trading_agent.py
```

You should see:
```
============================================================
CRYPTO TRADING AI AGENT
============================================================
Mode: PAPER
Initial Balance: $10,000.00
============================================================
```

## Your First Trades

### Example Session
```bash
# 1. Add Bitcoin to watchlist
crypto-ai> add B-BTC_USDT
✓ Added B-BTC_USDT to watch list

# 2. Update market data
crypto-ai> update
Updating market data...
✓ Market data updated

# 3. Analyze Bitcoin
crypto-ai> analyze B-BTC_USDT

============================================================
TECHNICAL ANALYSIS: B-BTC_USDT
============================================================

Current Price: $45,234.50
Signal: BUY (Confidence: 65.0%)
Trend: BULLISH - STRONG

Indicators:
  RSI: 35.23
  SMA(20): $44,890.00
  SMA(50): $44,200.00
  MACD: 0.0234

Reason: RSI indicates oversold condition; Price above moving averages
============================================================

# 4. Execute a buy trade
crypto-ai> buy B-BTC_USDT 0.01

✓ Trade executed: BUY 0.01 B-BTC_USDT @ $45,234.50
  Order ID: paper_1234567890_5678
  Total: $452.35

# 5. Check your portfolio
crypto-ai> portfolio

============================================================
PORTFOLIO STATUS
============================================================

Cash Balance: $9,547.65
Total Value: $10,000.00
Total Return: $0.00 (0.00%)
Total Trades: 1
Win Rate: 0.0%

------------------------------------------------------------
OPEN POSITIONS
------------------------------------------------------------
Symbol          Qty          Avg Price    Current      P&L            
------------------------------------------------------------
B-BTC_USDT      0.010000     $45234.50    $45234.50    +$0.00 (+0.00%)
============================================================

# 6. Add more symbols
crypto-ai> add B-ETH_USDT
crypto-ai> add I-SOL_USDT

# 7. Update and analyze Ethereum
crypto-ai> update
crypto-ai> analyze B-ETH_USDT

# 8. Exit
crypto-ai> quit
Goodbye!
```

## Popular Commands

### Must-Know Commands
| Command | Description | Example |
|---------|-------------|---------|
| `add` | Add symbol to watchlist | `add B-BTC_USDT` |
| `update` | Fetch latest prices | `update` |
| `analyze` | Get AI analysis | `analyze B-BTC_USDT` |
| `buy` | Buy cryptocurrency | `buy B-BTC_USDT 0.01` |
| `sell` | Sell cryptocurrency | `sell B-BTC_USDT 0.005` |
| `portfolio` | Show holdings | `portfolio` |
| `list` | Show watchlist | `list` |

## Popular Trading Pairs

### Bitcoin (BTC)
- `B-BTC_USDT` - Bitcoin to USDT (CoinDCX)
- `I-BTC_USDT` - Bitcoin to USDT (International)

### Ethereum (ETH)
- `B-ETH_USDT` - Ethereum to USDT (CoinDCX)
- `I-ETH_USDT` - Ethereum to USDT (International)

### Other Popular Coins
- `I-BNB_USDT` - Binance Coin
- `I-SOL_USDT` - Solana
- `I-ADA_USDT` - Cardano
- `I-DOT_USDT` - Polkadot
- `I-MATIC_USDT` - Polygon

## Understanding the Analysis

When you run `analyze`, you'll see:

### Signal Types
- **BUY**: Indicators suggest buying opportunity
- **SELL**: Indicators suggest selling opportunity  
- **HOLD**: No clear signal, wait for better opportunity

### Confidence Levels
- **70-100%**: Strong signal, high confidence
- **50-70%**: Moderate signal, proceed with caution
- **Below 50%**: Weak signal, consider waiting

### Key Indicators

**RSI (Relative Strength Index)**
- < 30: Oversold (possible buy)
- > 70: Overbought (possible sell)
- 40-60: Neutral

**Trend**
- BULLISH: Price trending up
- BEARISH: Price trending down

**Momentum**
- STRONG: Large price movements
- WEAK: Small price movements

## Paper Trading Tips

### Practice These Strategies

1. **Start Small**
   - Begin with 1% of your portfolio per trade
   - Example: With $10,000, trade $100 worth

2. **Collect Data First**
   - Run `update` at least 20-30 times
   - This builds price history for better analysis

3. **Analyze Before Trading**
   - Always check `analyze` before buying/selling
   - Look for confidence above 60%

4. **Monitor Your Positions**
   - Use `portfolio` regularly
   - Track your wins and losses

5. **Diversify**
   - Don't put all money in one coin
   - Add 3-5 different symbols

### Practice Workflow

```bash
# Morning routine
crypto-ai> update
crypto-ai> portfolio
crypto-ai> analyze B-BTC_USDT
crypto-ai> analyze B-ETH_USDT

# If strong BUY signal (>65% confidence)
crypto-ai> buy B-BTC_USDT 0.005

# Afternoon check
crypto-ai> update
crypto-ai> portfolio

# If position is profitable or strong SELL signal
crypto-ai> sell B-BTC_USDT 0.005
```

## Moving to Live Trading

⚠️ **Only after practicing in paper mode!**

### Get CoinDCX API Keys

1. Sign up at https://coindcx.com
2. Complete KYC verification
3. Go to Settings → API Management
4. Create new API key
5. **Important**: Only enable "Trade" permission (NOT withdrawal)
6. Save your API Key and Secret securely

### Start Live Trading

```bash
python crypto_trading_agent.py \
  --mode live \
  --api-key YOUR_API_KEY \
  --api-secret YOUR_API_SECRET
```

### Live Trading Safety Rules

1. **Start with small amounts** (₹1,000-5,000)
2. **Never trade more than 1-2% per trade**
3. **Always use stop losses**
4. **Test with one coin first**
5. **Monitor trades actively**

## Common Mistakes to Avoid

❌ **Trading without analysis**
✅ Always run `analyze` before trading

❌ **Ignoring the confidence score**
✅ Only trade when confidence > 60%

❌ **Going all-in on one trade**
✅ Risk max 2% per trade

❌ **Not updating market data**
✅ Run `update` before every decision

❌ **Revenge trading after losses**
✅ Stick to your strategy

## Next Steps

1. ✅ Practice 10 trades in paper mode
2. ✅ Learn to read the technical indicators
3. ✅ Try different trading pairs
4. ✅ Keep a trading journal
5. ✅ Study your wins and losses
6. 🎯 Only then consider live trading

## Getting Help

### Troubleshooting

**"Insufficient data for analysis"**
- Run `update` 20-30 times to build history
- Wait a few seconds between updates

**"Symbol not found"**
- Check the symbol format: `B-BTC_USDT` not `BTC-USDT`
- Use `list` to see added symbols

**Need more data points?**
```bash
# Quick data collection
crypto-ai> add B-BTC_USDT
crypto-ai> update
crypto-ai> update
crypto-ai> update
# ... repeat 20 times
crypto-ai> analyze B-BTC_USDT
```

## Resources

- 📖 Read the full [README.md](README.md) for advanced features
- 📚 Learn about [technical indicators](https://www.investopedia.com/trading/)
- 🔑 Never share your API keys
- 💡 Practice makes perfect

---

**Ready to start? Just run:**
```bash
python crypto_trading_agent.py
```

Happy trading! 🚀
