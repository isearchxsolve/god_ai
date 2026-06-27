# 🚀 Solana Trader Strategy Collection
# 5 Pre-Built Trading Strategies for Solana Memecoins

> **5 battle-tested trading strategies. One complete package.**
> Each strategy targets a different memecoin lifecycle stage.
> Choose your weapon. Deploy in minutes.

---

## ⚡ What This Is

This is a **collection of 5 distinct trading strategies** for the Solana memecoin market, each optimized for a different market condition and risk profile.

**No coding required to deploy.** Each strategy is a complete, self-contained configuration that can be deployed in under 5 minutes.

---

## 📦 The 5 Strategies

### 1. 🎯 HWR Strategy — High Win-Rate (The Conservative Hunter)
**Target:** Established memecoins with sustained buyer control
**Best for:** Traders who prefer consistency over moonshots
**Risk Profile:** Low-Medium

**Entry Criteria:**
- Buy pressure 5m ≥ 0.70
- Buy pressure 1h ≥ 0.51
- Liquidity ≥ $40,000
- Score ≥ 60
- Age ≤ 6 hours
- Price change 5m ≤ 25% (anti-chase)

**Exit Strategy:**
- Hard take profit: +40%
- Trailing stop: +10% activation, -4% distance
- Stop loss: -5% (cost-widened)
- Max hold: 30 minutes

**Expected Performance:**
- Win rate: ~55-65%
- Avg winner: +15-25%
- Avg loser: -4-6%
- Best for: Small consistent gains that compound

---

### 2. 📈 MG Strategy — Momentum Grind (The Volume Rider)
**Target:** Memecoins in sustained volume expansion
**Best for:** Traders who catch the middle of pumps
**Risk Profile:** Medium

**Entry Criteria:**
- Volume momentum ≥ 1.35
- Price change 5m ≥ 1.2%
- Transaction velocity ≥ 8 per 5m
- Liquidity ≥ $25,000
- Score ≥ 55
- Age ≤ 40 minutes
- Price change 5m ≤ 25% (anti-chase)

**Exit Strategy:**
- Hard take profit: +60%
- Trailing stop: +12% activation, -5% distance
- Stop loss: -5% (cost-widened)
- Max hold: 25 minutes

**Expected Performance:**
- Win rate: ~45-55%
- Avg winner: +20-35%
- Avg loser: -5-7%
- Best for: Riding volume waves that sustain for 10-30 minutes

---

### 3. 🎯 Selective Sniper (The Precision Striker)
**Target:** Fresh launches with perfect metrics
**Best for:** Traders who want the highest probability entries
**Risk Profile:** Medium-High

**Entry Criteria:**
- Score ≥ 85
- Buy pressure 5m ≥ 0.70
- Liquidity ≥ $50,000
- Age ≤ 10 minutes
- Price change 5m ≤ 15% (tight anti-chase)
- RugCheck: ZERO risk flags
- Whale convergence: ≥3 net buyers

**Exit Strategy:**
- Hard take profit: +100%
- Trailing stop: +20% activation, -8% distance
- Stop loss: -5% (cost-widened)
- Max hold: 15 minutes
- Never-green cut: -5% at 18 seconds

**Expected Performance:**
- Win rate: ~35-45%
- Avg winner: +30-50%
- Avg loser: -5-8%
- Best for: Quality over quantity — only the absolute best setups

---

### 4. 🔍 Multi-Indicator (The Analyst)
**Target:** Memecoins confirmed by multiple independent signals
**Best for:** Traders who want confirmation before entry
**Risk Profile:** Medium

**Entry Criteria:**
- Score ≥ 70
- Buy pressure 5m ≥ 0.60
- Volume momentum ≥ 1.0
- Price change 5m ≥ 0.5%
- Transaction velocity ≥ 5 per 5m
- Liquidity ≥ $30,000
- Age ≤ 2 hours
- Requires 3+ of 5 indicators to align

**Exit Strategy:**
- Hard take profit: +50%
- Trailing stop: +15% activation, -6% distance
- Stop loss: -5% (cost-widened)
- Max hold: 35 minutes

**Expected Performance:**
- Win rate: ~50-60%
- Avg winner: +18-30%
- Avg loser: -4-6%
- Best for: Confirmation-based entries with higher probability

---

### 5. ⚡ Enhanced Strategy (The All-Rounder)
**Target:** Any memecoin that passes the basic quality gates
**Best for:** Traders who want maximum frequency
**Risk Profile:** Medium-High

**Entry Criteria:**
- Score ≥ 55
- Buy pressure 5m ≥ 0.55
- Liquidity ≥ $20,000
- Age ≤ 3 hours
- Price change 5m ≤ 30% (loose anti-chase)
- Basic RugCheck pass

**Exit Strategy:**
- Hard take profit: +80%
- Trailing stop: +15% activation, -6% distance
- Stop loss: -5% (cost-widened)
- Max hold: 20 minutes
- Fast-cut enabled at -8% hard floor

**Expected Performance:**
- Win rate: ~40-50%
- Avg winner: +25-40%
- Avg loser: -6-8%
- Best for: Maximum trade frequency with acceptable risk

---

## 📊 Strategy Comparison Matrix

| Strategy | Win Rate | Avg Winner | Avg Loser | Frequency | Best For |
|----------|----------|-----------|-----------|-----------|----------|
| **HWR** | 55-65% | +15-25% | -4-6% | Low | Consistency |
| **MG** | 45-55% | +20-35% | -5-7% | Medium | Volume riding |
| **Selective Sniper** | 35-45% | +30-50% | -5-8% | Low | Quality moonshots |
| **Multi-Indicator** | 50-60% | +18-30% | -4-6% | Medium | Confirmation |
| **Enhanced** | 40-50% | +25-40% | -6-8% | High | Maximum frequency |

---

## 🚀 Quick Start

### 1. Choose Your Strategy

```bash
# List available strategies
./switch_strategy.bat --list

# Output:
# 1. hwr-strategy
# 2. mg-strategy
# 3. selective-sniper
# 4. multi-indicator
# 5. enhanced
```

### 2. Activate Strategy

```bash
# Switch to HWR Strategy
./switch_strategy.bat --strategy hwr

# Confirm switch
cat engine_settings.json | grep strategy
# → "strategy": "hwr"
```

### 3. Deploy

```bash
# Start the engine with the selected strategy
START.cmd

# The engine will now use the HWR configuration
```

### 4. Monitor

Open the dashboard at `http://localhost:5000` and verify:
- Strategy name displayed in header
- Entry criteria match the strategy specs
- Exit settings are correctly configured

---

## 🛠️ Advanced: Customizing Strategies

Each strategy is defined in a JSON configuration file:

```json
{
  "name": "HWR",
  "description": "High Win-Rate — Conservative memecoin hunting",
  "entry": {
    "minScore": 60,
    "minBuyPressure5m": 0.70,
    "minBuyPressure1h": 0.51,
    "minLiquidity": 40000,
    "maxAgeSeconds": 21600,
    "maxPriceChange5m": 25
  },
  "exit": {
    "hardTakeProfit": 40,
    "trailingStopActivation": 10,
    "trailingStopDistance": 4,
    "stopLoss": -5,
    "maxHoldSeconds": 1800,
    "neverGreenEnabled": true
  }
}
```

Edit these values to create your own custom strategy.

---

## 📈 Backtesting Guide

### Historical Paper Testing

```bash
# Run 100 paper trades with a specific strategy
python validate-paper.ps1 --strategy hwr --trades 100

# Results saved to:
# - backtest_hwr_100.json (raw trade data)
# - backtest_hwr_100_summary.json (metrics)
```

### Key Metrics to Evaluate
- **Win rate:** % of trades that closed profitable
- **Profit factor:** Gross profit / gross loss
- **Sharpe ratio:** Risk-adjusted return
- **Max drawdown:** Largest peak-to-trough decline
- **Expectancy:** Average return per trade

---

## 🎯 Choosing the Right Strategy

| Your Goal | Recommended Strategy |
|-----------|---------------------|
| Small consistent gains | **HWR** |
| Riding volume waves | **MG** |
| High-risk moonshots | **Selective Sniper** |
| Confirmation-based entries | **Multi-Indicator** |
| Maximum trade frequency | **Enhanced** |
| Balanced approach | **Start with HWR, then experiment** |

---

## ⚠️ Disclaimer

These strategies are **configurations for educational/research software**. Past performance of any strategy does not guarantee future results. All strategies carry risk of loss. See `DISCLAIMER.md` for full legal text.

---

## 📝 License

Single-user license. See `LICENSE.md` for full terms.

---

**Built for:** Solana traders, bot developers, quant enthusiasts  
**Stack:** TypeScript, Node.js, Solana Web3.js, Jupiter V6  
**Version:** 1.0  
**Requires:** SOL-SNIPER engine base (or works standalone with compatible engine)