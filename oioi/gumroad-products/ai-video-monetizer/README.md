# 🤖 AI Video Monetizer — The Faceless Empire Blueprint
# Complete AI Video → Automation → Monetization Pipeline

> **The exact system that builds a passive income empire from AI-generated videos.**
> From video generation to automatic posting to DM funnels to Gumroad checkout.
> **Fully automated. Fully documented. Ready to deploy.**

---

## ⚡ What This Is

This is the **complete blueprint and automation scripts** for a "faceless YouTube/TikTok monetization empire" built entirely with AI tools and no-code automation.

**You get:**
- ✅ 30-day content matrix (hooks, prompts, pinned comments)
- ✅ AI video generation scripts (Runway, Luma, Kling)
- ✅ Make.com automation scenarios (watch Sheets → generate video → save to Drive → update Sheet)
- ✅ ManyChat DM funnel (comment keyword → auto-reply → DM with Gumroad link)
- ✅ Gumroad product setup (checkout, delivery, upsells, email drip)
- ✅ Social media scheduler integration (Buffer, Metricool, Later)
- ✅ Complete Google Workspace setup (Sheets, Drive, Docs)

**What you DON'T need:**
- ❌ No video editing skills
- ❌ No on-camera presence
- ❌ No coding skills (beyond config setup)
- ❌ No ad spend

---

## 📦 What You Get

### Core Automation Scripts
```
ai-video-monetizer/
├── scripts/
│   ├── deploy_all.bat              # One-click Windows deployment
│   ├── deploy_all.ps1              # PowerShell deployment
│   ├── run_automation.bat          # Start the automation pipeline
│   ├── deploy_minimal.bat          # Minimal setup (faster)
│   └── test_deploy.bat             # Test all connections
├── src/
│   └── [automation scripts]        # Python scripts for the pipeline
├── config/
│   ├── video_prompts.json          # 30-day content matrix
│   └── [other config files]        # Platform settings
└── content/
    ├── ebook_manuscript.md         # The Magnetism Blueprint
    └── texting_framework.md        # 50 texting scripts
```

### Documentation
- `README.md` — This file (complete setup guide)
- `ENV_CONFIGURATION_GUIDE.md` — Every .env variable explained
- `GOOGLE_FREE_SETUP.md` — Free Google Workspace setup
- `PDF_BLUEPRINT.pdf` — The original master blueprint

### 30-Day Content Matrix (`config/video_prompts.json`)
Each day includes:
- **Hook**: Scroll-stopping opening line
- **Prompt**: Detailed AI video generation prompt (Runway/Luma/Kling)
- **Pinned Comment**: Call-to-action with keyword trigger

Example Day 1:
```json
{
  "day": 1,
  "hook": "Psychology says: when someone is intensely thinking about you, they do this...",
  "prompt": "Cinematic editorial film style, close up shot of a beautiful woman looking away thoughtfully, dramatic chiaroscuro lighting, soft shadows, warm ambient light, photorealistic skin pores, 35mm lens, atmospheric dust, 8k resolution, slow motion 0.5x --ar 9:16",
  "pinned_comment": "They will completely overcompensate by acting overly casual or avoiding your eye contact entirely when you walk into a room. Their subconscious mind is trying to hide how loud their thoughts are. Want to become completely unforgettable? Comment 'MAGNETIC' below and I'll DM you our magnetism guide. 🖤"
}
```

---

## 🚀 Quick Start (30 minutes)

### Step 1: Google Workspace (5 min)
1. Create OAuth app at [Google Cloud Console](https://console.cloud.google.com)
2. Enable Sheets + Drive APIs
3. Download `client_secret.json`
4. Run auth flow:
```bash
python -m google_workspace.scripts.setup --client-secret ./client_secret.json
python -m google_workspace.scripts.setup --auth-url --services sheets,drive --format json
# → Open browser, approve, paste redirect URL
python -m google_workspace.scripts.setup --auth-code "PASTED_URL_HERE" --format json
python -m google_workspace.scripts.setup --check
# → Should print: AUTHENTICATED
```

### Step 2: Create Drive Folders (5 min)
- `🪐 Premium Faceless Empire`
  - `01_Scripts_and_Copy`
  - `02_Raw_AI_Videos`
  - `03_Digital_Products`

Copy folder IDs from URLs into `.env`.

### Step 3: Create Content Pipeline Sheet (5 min)
- New Google Sheet in `01_Scripts_and_Copy`
- Name: `Content Pipeline & Video Database`
- Copy Sheet ID from URL into `.env`

### Step 4: Configure AI Video APIs (5 min)
Choose at least one:
- **Runway Gen-3** (recommended): `RUNWAY_API_KEY=rnt_your_key`
- **Luma Dream Machine**: `LUMA_API_KEY=luma_your_key`
- **Kling AI**: `KLING_API_KEY=kling_your_key`

### Step 5: Configure Gumroad (5 min)
1. Create account at [gumroad.com](https://gumroad.com)
2. Get API token: [app.gumroad.com/api](https://app.gumroad.com/api)
3. Create products:
   - The Magnetism Blueprint ($9.99)
   - The Texting Framework ($10.00) — order bump
   - Attraction Masterclass ($97.00) — upsell
4. Add token to `.env`

### Step 6: Configure ManyChat (5 min)
1. Create account, connect Instagram/TikTok
2. Get API token: [developers.manychat.com](https://developers.manychat.com)
3. Set trigger keywords: `MAGNETIC, BLUEPRINT, SECRET, CODE`
4. Build flow: Comment → Auto-reply → DM with Gumroad link

### Step 7: Deploy (5 min)
```bash
# Windows
deploy_all.bat

# Or PowerShell
./deploy_all.ps1
```

---

## 🎯 The Pipeline

```
┌─────────────────┐
│  Google Sheets  │  ← Content pipeline (30-day matrix)
└────────┬────────┘
         │ (Make.com watches for new rows)
         ↓
┌─────────────────┐
│  AI Video API   │  ← Runway/Luma/Kling generates video
│  (Runway/etc)   │
└────────┬────────┘
         │ (Make.com saves video)
         ↓
┌─────────────────┐
│  Google Drive   │  ← Video stored in folder
└────────┬────────┘
         │ (Make.com updates Sheet with status)
         ↓
┌─────────────────┐
│  Social Media   │  ← Buffer/Metricool/Later posts video
│  Scheduler      │    at optimal time
└────────┬────────┘
         │ (User comments keyword on video)
         ↓
┌─────────────────┐
│  ManyChat       │  ← Auto-replies to comment
│  DM Funnel      │    Sends DM with Gumroad link
└────────┬────────┘
         │ (User clicks, buys on Gumroad)
         ↓
┌─────────────────┐
│  Gumroad        │  ← Checkout, instant delivery,
│  Checkout       │    order bump, email drip
└─────────────────┘
```

**Result:** A fully automated pipeline that generates AI videos, posts them, captures leads via DM, and converts them to customers — all while you sleep.

---

## 💰 Monetization Strategy

### The Product Ladder

| Product | Price | Description |
|---------|-------|-------------|
| **The Magnetism Blueprint** | $9.99 | Digital ebook (PDF) — delivered instantly via Gumroad |
| **The Texting Framework** | $10.00 | Order bump at checkout — 50 scripts |
| **Attraction Masterclass** | $97.00 | Upsell in email sequence — video course |

### Revenue Math
- **1 video/day** × 30 days = 30 videos/month
- **100 views/video** = 3,000 views/month
- **2% conversion** on keyword comments = 60 DM leads
- **20% conversion** on DM link = 12 sales
- **$9.99 + $10.00 order bump** = $19.99 average order
- **Monthly revenue:** 12 × $19.99 = **$240/month per channel**
- **Scale:** 5 channels = **$1,200/month**
- **10 channels** = **$2,400/month**

**With upsells ($97 masterclass at 5% conversion):**
- 12 buyers × 5% = 0.6 masterclass sales = **$58/month**
- **Total per channel: ~$298/month**
- **10 channels: ~$2,980/month**

---

## 📚 Full Setup Guide

See `ENV_CONFIGURATION_GUIDE.md` for the complete configuration walkthrough with screenshots.

See `GOOGLE_FREE_SETUP.md` for the free Google Workspace setup (no paid plan required).

---

## ⚠️ Disclaimer

This is a **business automation blueprint**. Results depend on:
- Quality of AI-generated videos
- Platform algorithm performance
- Niche selection and audience resonance
- Consistent execution

**No guaranteed income. This is a system, not a magic button.**

---

## 📝 License

Single-user license. See `LICENSE.md` for full terms.

---

**Built for:** Faceless content creators, digital marketers, passive income builders  
**Stack:** Python, Make.com, Google Workspace, Runway/Luma/Kling, Gumroad, ManyChat, Buffer/Metricool/Later