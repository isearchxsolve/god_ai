# 🤖 API Money Bot v3 — The 34-Platform Automation Toolkit
# Auto-Harvest, Auto-Trade, Auto-Monetize Across the Internet

> **The ultimate API automation toolkit. 34 platforms. One command.**
> Harvest API keys. Execute trades. Upload content. Collect payments.
> All automated. All from one interface.

---

## ⚡ What This Is

This is a **complete Python automation toolkit** that connects to **34 platforms** across:
- **Crypto trading** (Binance, Coinbase, KuCoin, Bybit, OKX)
- **Freelancing** (Upwork, Freelancer)
- **Stock media** (Shutterstock, Adobe Stock, Pond5)
- **Digital products** (Gumroad, Etsy, eBay)
- **E-commerce** (Shopify, Printful, Printify)
- **Content** (YouTube, Medium, Patreon, Substack)
- **Social** (Reddit, Twitter/X, GitHub)
- **AI** (OpenAI, Anthropic, Replicate, RapidAPI)
- **Microtasks** (Toloka, Clickworker, Remotasks)
- **Payments** (Stripe, Razorpay, PayPal, Wise)

**One command runs them all.**

---

## 📦 What You Get

### Core Bot
```
api_money_bot_complete/
├── src/
│   └── api_money_bot_v3.py          # Main bot (34 platforms)
├── api_key_harvester/
│   ├── main.py                       # Harvester orchestrator
│   ├── create_zip.py                 # Packaging script
│   ├── requirements.txt              # All dependencies
│   ├── .env.example                  # Complete environment template
│   ├── utils/                        # Browser, captcha, fingerprint
│   │   ├── browser.py                # Stealth Playwright factory
│   │   ├── captcha.py                # 2Captcha integration
│   │   ├── fingerprint.py            # Browser fingerprint randomization
│   │   └── helpers.py                # Key masking, extraction helpers
│   └── strategies/                   # 34 platform strategies
│       ├── binance.py                # Binance API key harvester
│       ├── coinbase.py               # Coinbase harvester
│       ├── kucoin.py                 # KuCoin harvester
│       ├── bybit.py                  # Bybit harvester
│       ├── okx.py                    # OKX harvester
│       ├── github.py                 # GitHub token harvester
│       ├── upwork.py                 # Upwork OAuth harvester
│       ├── gumroad.py                # Gumroad token harvester
│       ├── stripe.py                 # Stripe key harvester
│       ├── openai.py                 # OpenAI key harvester
│       ├── shutterstock.py           # Shutterstock harvester
│       ├── adobestock.py             # Adobe Stock harvester
│       ├── pond5.py                  # Pond5 harvester
│       ├── etsy.py                   # Etsy harvester
│       ├── ebay.py                   # eBay harvester
│       ├── shopify.py                # Shopify harvester
│       ├── printful.py               # Printful harvester
│       ├── printify.py               # Printify harvester
│       ├── medium.py                 # Medium harvester
│       ├── patreon.py                # Patreon harvester
│       ├── substack.py               # Substack harvester
│       ├── reddit.py                 # Reddit app credentials harvester
│       ├── twitter.py                # Twitter/X harvester
│       ├── anthropic.py              # Anthropic harvester
│       ├── replicate.py              # Replicate harvester
│       ├── rapidapi.py               # RapidAPI harvester
│       ├── razorpay.py               # Razorpay harvester
│       ├── wise.py                   # Wise harvester
│       ├── paypal.py                 # PayPal harvester
│       ├── toloka.py                 # Toloka harvester
│       ├── clickworker.py            # Clickworker harvester
│       └── remotasks.py              # Remotasks harvester
```

### Scripts & Launchers
- `run_bot.bat` — Windows menu-driven launcher
- `run_bot.sh` — Linux/Mac menu-driven launcher
- `run_batch.py` — Batch execution across platforms
- `test_all_platforms.py` — Health check suite
- `deploy_all.bat` — One-click deployment

---

## 🚀 Quick Start

### 1. Install Dependencies (5 minutes)

```bash
# Install Python dependencies
pip install -r api_key_harvester/requirements.txt

# Install Playwright browser
playwright install chromium

# Verify installation
python src/api_money_bot_v3.py --health
```

### 2. Configure Environment (10 minutes)

```bash
cp .env.example .env
# Edit .env with your platform credentials
```

**Key variables:**
```env
# Master Switch (ALWAYS false until ready)
LIVE_MODE=false

# Category Gates (enable one at a time)
TRADING_ENABLED=false
AUTO_WITHDRAW=false
MEDIA_UPLOAD_ENABLED=false
FREELANCING_ENABLED=false

# Financial Platforms
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
COINBASE_API_KEY=your_key
KUCOIN_API_KEY=your_key
BYBIT_API_KEY=your_key
OKX_API_KEY=your_key

# Stock Media
SHUTTERSTOCK_API_KEY=your_key
ADOBE_STOCK_API_KEY=your_key
POND5_API_KEY=your_key

# Digital Products
GUMROAD_ACCESS_TOKEN=your_token
ETSY_API_KEY=your_key
SHOPIFY_ACCESS_TOKEN=your_token

# AI Platforms
OPENAI_API_KEY=your_key
ANTHROPIC_API_KEY=your_key
REPLICATE_API_TOKEN=your_token
RAPIDAPI_KEY=your_key

# Social
REDDIT_CLIENT_ID=your_id
REDDIT_CLIENT_SECRET=your_secret
TWITTER_API_KEY=your_key
GITHUB_TOKEN=your_token

# 2Captcha (for automated captcha solving)
TWOCAPTCHA_API_KEY=your_key
```

### 3. Run API Key Harvester (15 minutes)

```bash
# Harvest ALL platform keys
python api_key_harvester/main.py

# Harvest specific platforms
python api_key_harvester/main.py --platforms binance coinbase github

# Show harvested keys
python api_key_harvester/main.py --show
```

### 4. Health Check (Read-Only)

```bash
# Validates all credentials without executing trades
python src/api_money_bot_v3.py --health
```

### 5. Safe Monitoring Run (No money moves)

```bash
# Monitors platforms, logs data, NO trades executed
python src/api_money_bot_v3.py
```

### 6. Live Mode (ONLY when ready)

```bash
# Enable live mode (requires explicit env var)
LIVE_MODE=true TRADING_ENABLED=true python src/api_money_bot_v3.py
```

---

## 🛡️ Safety Architecture

| Layer | Control | Default | Description |
|-------|---------|---------|-------------|
| **Master Switch** | `LIVE_MODE` | `false` | ALL financial actions blocked unless true |
| **Category Gates** | `TRADING_ENABLED`, `AUTO_WITHDRAW`, etc. | `false` | Each category must be explicitly enabled |
| **Spending Caps** | `MAX_TRADE_USD`, `MAX_BID_USD` | Hardcoded | Maximum spend per action |
| **Symbol Allowlist** | `ALLOWED_PAIRS` | `BTCUSDT,ETHUSDT` | Only trade approved pairs |
| **Testnet Default** | `BINANCE_TESTNET`, `BYBIT_TESTNET` | `true` | All crypto platforms default to testnet |
| **Audit Trail** | `payment_audit.json` + `revenue_log.json` | Always on | Immutable record of every action |

### Stealth Features
- **Playwright + playwright-stealth**: Anti-detection browser automation
- **Random fingerprint rotation**: Viewport, timezone, user-agent, WebGL per session
- **Proxy support**: IP rotation for rate limit avoidance
- **Session persistence**: Avoids re-logging
- **Captcha solving**: 2Captcha integration for reCAPTCHA v2/v3 and hCaptcha

---

## 📋 Platform Coverage (34 Platforms)

### 🔴 Tier 1 — Financial (Highest Security)
- **Crypto**: Binance, Coinbase, KuCoin, Bybit, OKX
- **Payments**: Stripe, Razorpay, PayPal, Wise, Payoneer

### 🟠 Tier 2 — High-Value Automation
- **Freelancing**: Upwork, Freelancer.com

### 🟡 Tier 3 — Commerce & Media
- **Stock Media**: Shutterstock, Adobe Stock, Pond5
- **Digital Products**: Gumroad, Etsy, eBay
- **E-commerce**: Shopify, Printful, Printify

### 🟢 Tier 4 — Content, Social, AI, Microtasks
- **Content**: YouTube, Medium, Patreon, Substack
- **Social**: Reddit, Twitter/X, GitHub
- **AI**: OpenAI, Anthropic, Replicate, RapidAPI
- **Microtasks**: Toloka, Clickworker, Remotasks

---

## 🎯 Use Cases

### Use Case 1: Crypto Trading Automation
```bash
LIVE_MODE=true TRADING_ENABLED=true ALLOWED_PAIRS=BTCUSDT,ETHUSDT python src/api_money_bot_v3.py --platform Binance
```
Automatically executes trades on Binance based on signals. Defaults to testnet unless explicitly set.

### Use Case 2: Stock Media Upload
```bash
python src/api_money_bot_v3.py --upload-photo shutterstock ./photo.jpg "My Title"
```
Uploads photos to Shutterstock for passive royalty income.

### Use Case 3: Digital Product Creation
```bash
python src/api_money_bot_v3.py --create-product gumroad "My eBook" 999
```
Creates a Gumroad product listing automatically.

### Use Case 4: AI Content Generation
```bash
python src/api_money_bot_v3.py --platform OpenAI
```
Generates AI content using OpenAI API for blog posts, social media, etc.

### Use Case 5: Microtask Automation
```bash
python src/api_money_bot_v3.py --platform Toloka
```
Automates microtask completion on Toloka for small passive income.

---

## 📊 Audit & Logging

All actions are logged to:
- `api_money_bot.log` — General operation log
- `payment_audit.json` — Every financial action (immutable)
- `revenue_log.json` — Revenue tracking & daily summaries
- `harvested_keys.json` — API key harvest results

---

## ⚠️ Legal & Ethical Notice

This tool is for **authorized security testing and personal account management only**.

### Authorized Use
- ✅ Managing your OWN API keys and accounts
- ✅ Automating tasks on platforms where you have explicit permission
- ✅ Testing your own security configurations
- ✅ Learning about API automation and web scraping

### Unauthorized Use (PROHIBITED)
- ❌ Harvesting keys from accounts you do not own
- ❌ Accessing third-party accounts without consent
- ❌ Violating platform Terms of Service
- ❌ Any illegal activity

### Your Responsibility
- You MUST comply with each platform's Terms of Service
- You MUST respect rate limits and API guidelines
- You MUST obtain explicit permission before automating login on any platform
- You are SOLELY responsible for any consequences of using this tool

---

## 📝 License

Single-user license. See `LICENSE.md` for full terms.

---

**Built for:** Automation engineers, API power users, side hustlers, digital nomads  
**Stack:** Python, Playwright, 2Captcha, 34+ platform APIs  
**Version:** v3.0 | Security-First Architecture