from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR        = "solana_hybrid_sniper_ultra/data"
PAPER_TRADES    = os.path.join(DATA_DIR, "paper_trades.json")
LIVE_TRADES     = os.path.join(DATA_DIR, "live_trades.json")
PAPER_POSITIONS = os.path.join(DATA_DIR, "paper_positions.json")
LIVE_POSITIONS  = os.path.join(DATA_DIR, "live_positions.json")


def _load_json(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


@app.get("/api/status")
async def get_status():
    paper_trades = _load_json(PAPER_TRADES, [])
    closed = [t for t in paper_trades if t.get("status") in ("WIN", "LOSS")]
    wins   = [t for t in closed if t.get("status") == "WIN"]
    total_pnl = sum(t.get("pnl_sol", 0) or 0 for t in closed)

    open_paper = _load_json(PAPER_POSITIONS, [])
    open_live  = _load_json(LIVE_POSITIONS,  [])

    # Determine mode from env, fall back to "paper"
    mode = os.getenv("MODE", "paper").upper()

    return {
        "bot_running":      True,
        "mode":             mode,
        "last_scan":        datetime.utcnow().isoformat() + "Z",
        "total_trades":     len(closed),
        "win_rate":         round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_pnl_sol":    round(total_pnl, 4),
        "open_paper":       len(open_paper),
        "open_live":        len(open_live),
    }


@app.get("/api/trades")
async def get_trades():
    paper = _load_json(PAPER_TRADES, [])
    live  = _load_json(LIVE_TRADES,  [])
    all_trades = paper + live
    all_trades.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    return all_trades


@app.get("/api/positions")
async def get_positions():
    paper = _load_json(PAPER_POSITIONS, [])
    live  = _load_json(LIVE_POSITIONS,  [])
    return {"paper": paper, "live": live}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
