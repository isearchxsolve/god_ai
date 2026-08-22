import sys
from pathlib import Path
import json

PROJECT_ROOT = Path("D:/omniroute-monetizer").resolve()
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "automation"))

from omniroute_api import OmniRouteAPI
from oauth_keepalive import resolve_password

OMNI_BASE = "http://localhost:20128"

def heal_combos():
    pw = resolve_password()
    api = OmniRouteAPI(password=pw)
    if not api.login():
        print("[-] Login failed")
        return False
        
    session = api.session
    r = session.get(f"{OMNI_BASE}/api/combos")
    combos = r.json().get("combos", [])
    
    for combo in combos:
        cid = combo["id"]
        # The user strictly demands DeepSeek-R1 for brutal truth and Claude 3.5 for UI Vision.
        # Since 'ainative' keys are dead but 'openrouter' keys are ALIVE, we route through OpenRouter.
        new_models = [
            {
                "id": "model_openrouter_deepseek_deepseek-r1",
                "kind": "model",
                "model": "openrouter/deepseek/deepseek-r1",
                "providerId": "openrouter",
                "weight": 100
            },
            {
                "id": "model_openrouter_anthropic_claude-3.5-sonnet",
                "kind": "model",
                "model": "openrouter/anthropic/claude-3.5-sonnet",
                "providerId": "openrouter",
                "weight": 95
            },
            {
                "id": "model_nvidia_nemotron-3-super-120b-a12b",
                "kind": "model",
                "model": "nvidia/nemotron-3-super-120b-a12b",
                "providerId": "nvidia",
                "weight": 90
            }
        ]
        
        existing_models = combo.get("models", [])
        current_weight = 40
        for em in existing_models:
            if em["providerId"] not in ["nvidia", "openrouter"]:
                em["weight"] = current_weight
                new_models.append(em)
                current_weight -= 1
                if current_weight < 1: current_weight = 1
                    
        payload = {
            "id": cid,
            "name": combo["name"],
            "description": combo.get("description", ""),
            "models": new_models,
            "strategy": "priority",
            "config": combo.get("config", {"maxRetries": 3, "retryDelayMs": 500}),
            "isHidden": combo.get("isHidden", False),
        }
        
        session.put(f"{OMNI_BASE}/api/combos/{cid}", json=payload)
        
if __name__ == "__main__":
    heal_combos()
