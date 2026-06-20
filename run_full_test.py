"""
Comprehensive Platform Diagnostic & Harvester Runner
====================================================
Visits each platform's LOGIN_URL, takes screenshots, reports status.
Then runs the full harvester pipeline (signup -> login -> extract keys)
on any platforms that have credentials configured.
"""
import os, sys, json, time
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent / "api_key_harvester"))
load_dotenv()

from utils.browser import StealthBrowser
from utils.captcha import CaptchaSolver
from strategies import *
from main import STRATEGIES, save_keys, load_keys, mask_key

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
CAPTCHA_API_KEY = os.getenv("CAPTCHA_API_KEY", "")
MANUAL_CAPTCHA = os.getenv("MANUAL_CAPTCHA", "false").lower() == "true"

# Which platforms have login credentials?
def has_login_creds(name):
    prefix = name.upper()
    email = os.getenv(f"{prefix}_EMAIL") or os.getenv(f"{prefix}_USERNAME")
    pwd = os.getenv(f"{prefix}_PASSWORD")
    # Special cases
    if name == "github":
        email = os.getenv("GITHUB_USERNAME")
        pwd = os.getenv("GITHUB_PASSWORD")
    if name == "reddit":
        email = os.getenv("REDDIT_USERNAME")
        pwd = os.getenv("REDDIT_PASSWORD")
    if name == "twitter":
        email = os.getenv("TWITTER_USERNAME")
        pwd = os.getenv("TWITTER_PASSWORD")
    if name == "shopify":
        email = os.getenv("SHOPIFY_EMAIL") or os.getenv("SHOPIFY_STORE")
        pwd = os.getenv("SHOPIFY_PASSWORD")
    if name == "youtube":
        email = os.getenv("YOUTUBE_EMAIL") or os.getenv("GOOGLE_EMAIL")
        pwd = os.getenv("YOUTUBE_PASSWORD") or os.getenv("GOOGLE_PASSWORD")
    return bool(email and pwd and email not in ("", "your_email@gmail.com") and pwd not in ("", "your_password"))

def main():
    print("=" * 60)
    print("  PLATFORM DIAGNOSTIC REPORT")
    print("=" * 60)

    # Check which platforms have credentials
    creds_available = [name for name in STRATEGIES if has_login_creds(name)]
    creds_missing = [name for name in STRATEGIES if not has_login_creds(name)]

    print(f"\nPlatforms with login credentials: {len(creds_available)}/34")
    for p in sorted(creds_available):
        print(f"  [OK] {p}")
    print(f"\nPlatforms missing credentials: {len(creds_missing)}/34")
    for p in sorted(creds_missing):
        print(f"  [--] {p}")

    if not creds_available:
        print("\n*** No platforms have login credentials configured. ***")
        print("Add credentials to .env or set AUTO_SIGNUP=true for signup automation.")
        return

    # Run harvester on platforms that have credentials
    print(f"\n{'=' * 60}")
    print(f"  RUNNING HARVESTER ON {len(creds_available)} PLATFORMS")
    print(f"  HEADLESS={HEADLESS}, MANUAL_CAPTCHA={MANUAL_CAPTCHA}")
    print(f"{'=' * 60}")

    captcha = CaptchaSolver() if CAPTCHA_API_KEY else None
    all_keys = load_keys() or {}

    for name in creds_available:
        print(f"\n--- {name.upper()} ---")
        session_path = f"api_key_harvester/sessions/{name}.json"

        try:
            with StealthBrowser(headless=HEADLESS, storage_state=session_path) as browser:
                strategy_class = STRATEGIES[name]
                strategy = strategy_class(browser=browser, captcha_solver=captcha)

                # Screenshot initial page
                try:
                    strategy._screenshot(f"{name}_start")
                except Exception:
                    pass

                keys = strategy.run()
                if keys:
                    all_keys[name] = keys
                    print(f"  -> Harvested {len(keys)} key(s): { {k: mask_key(v) for k, v in keys.items()} }")
                else:
                    print(f"  -> No keys harvested")

                if os.getenv("SAVE_SESSION", "true").lower() == "true":
                    try:
                        browser.save_session(session_path)
                    except Exception:
                        pass

        except Exception as e:
            print(f"  -> ERROR: {e}")

    save_keys(all_keys)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS saved to harvested_keys.json")
    print(f"  Platforms harvested: {len(all_keys)}")
    for pname, pkeys in all_keys.items():
        if isinstance(pkeys, dict):
            masked = {k: mask_key(v) if isinstance(v, str) else v for k, v in pkeys.items()}
            print(f"  {pname}: {masked}")
        else:
            print(f"  {pname}: {pkeys}")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
