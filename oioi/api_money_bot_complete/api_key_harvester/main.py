#!/usr/bin/env python3
"""
API Key Harvester --- Main Orchestrator
========================================
Runs all platform strategies, saves session state, exports keys.
Supports parallel execution for multiple platforms simultaneously.

Stealth Stack Integration:
    Set USE_CLOAKBROWSER=true and USE_STEALTH_STACK_CAPTCHA=true in .env
    to enable CloakBrowser + Gemini/Whisper/BrightData CAPTCHA solving.
"""
import os
import sys
import json
import concurrent.futures
import threading
from pathlib import Path
from dotenv import load_dotenv

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from utils.stealth_integration import get_browser, get_captcha_solver
from utils.helpers import save_keys, load_keys, mask_key

# Import all strategies
from strategies.binance import BinanceStrategy
from strategies.coinbase import CoinbaseStrategy
from strategies.kucoin import KucoinStrategy
from strategies.bybit import BybitStrategy
from strategies.okx import OkxStrategy
from strategies.github import GithubStrategy
from strategies.upwork import UpworkStrategy
from strategies.gumroad import GumroadStrategy
from strategies.stripe import StripeStrategy
from strategies.openai import OpenaiStrategy
from strategies.shutterstock import ShutterstockStrategy
from strategies.adobestock import AdobestockStrategy
from strategies.pond5 import Pond5Strategy
from strategies.etsy import EtsyStrategy
from strategies.ebay import EbayStrategy
from strategies.shopify import ShopifyStrategy
from strategies.printful import PrintfulStrategy
from strategies.printify import PrintifyStrategy
from strategies.medium import MediumStrategy
from strategies.patreon import PatreonStrategy
from strategies.substack import SubstackStrategy
from strategies.reddit import RedditStrategy
from strategies.twitter import TwitterStrategy
from strategies.anthropic import AnthropicStrategy
from strategies.replicate import ReplicateStrategy
from strategies.rapidapi import RapidapiStrategy
from strategies.razorpay import RazorpayStrategy
from strategies.wise import WiseStrategy
from strategies.paypal import PaypalStrategy
from strategies.toloka import TolokaStrategy
from strategies.clickworker import ClickworkerStrategy
from strategies.remotasks import RemotasksStrategy
from strategies.freelancer import FreelancerStrategy
from strategies.youtube import YoutubeStrategy

load_dotenv()

STRATEGIES = {
    "binance": BinanceStrategy,
    "coinbase": CoinbaseStrategy,
    "kucoin": KucoinStrategy,
    "bybit": BybitStrategy,
    "okx": OkxStrategy,
    "github": GithubStrategy,
    "upwork": UpworkStrategy,
    "gumroad": GumroadStrategy,
    "stripe": StripeStrategy,
    "openai": OpenaiStrategy,
    "shutterstock": ShutterstockStrategy,
    "adobestock": AdobestockStrategy,
    "pond5": Pond5Strategy,
    "etsy": EtsyStrategy,
    "ebay": EbayStrategy,
    "shopify": ShopifyStrategy,
    "printful": PrintfulStrategy,
    "printify": PrintifyStrategy,
    "medium": MediumStrategy,
    "patreon": PatreonStrategy,
    "substack": SubstackStrategy,
    "reddit": RedditStrategy,
    "twitter": TwitterStrategy,
    "anthropic": AnthropicStrategy,
    "replicate": ReplicateStrategy,
    "rapidapi": RapidapiStrategy,
    "razorpay": RazorpayStrategy,
    "wise": WiseStrategy,
    "paypal": PaypalStrategy,
    "toloka": TolokaStrategy,
    "clickworker": ClickworkerStrategy,
    "remotasks": RemotasksStrategy,
    "freelancer": FreelancerStrategy,
    "youtube": YoutubeStrategy,
}

_results_lock = threading.Lock()
_parallel_results = {}


def run_single_platform(name: str, headless: bool) -> dict:
    """Run harvest for a single platform (intended for parallel execution). Returns keys dict."""
    session_path = f"api_key_harvester/sessions/{name}.json"

    # Use factory functions that support stealth stack
    captcha = get_captcha_solver()

    try:
        with get_browser(headless=headless, storage_state=session_path) as browser_instance:
            strategy_class = STRATEGIES[name]
            strategy = strategy_class(browser=browser_instance, captcha_solver=captcha)
            keys = strategy.run()
            if keys:
                print(f"  [{name}] -> Keys: { {k: mask_key(v) for k, v in keys.items()} }")
            if os.getenv("SAVE_SESSION", "true").lower() == "true":
                browser_instance.save_session(session_path)
            return keys
    except Exception as e:
        print(f"[Harvester] [{name}] Failed: {e}")
        return {"error": str(e)}


def run_harvester(targets: list = None, headless: bool = None, parallel: int = 1):
    """Run harvester for specified platforms (or all if None).
    
    Args:
        targets: List of platform names to run, or None for all.
        headless: Whether to run browsers headless.
        parallel: Number of platforms to run simultaneously (default 1).
    """
    targets = targets or list(STRATEGIES.keys())
    all_keys = load_keys() or {}

    if parallel <= 1:
        # Sequential execution (original behavior)
        for name in targets:
            if name not in STRATEGIES:
                print(f"[Harvester] Unknown platform: {name}")
                continue
            h = headless if headless is not None else (os.getenv("HEADLESS", "false").lower() == "true")
            keys = run_single_platform(name, h)
            if keys:
                all_keys[name] = keys
            save_keys(all_keys)
    else:
        # Parallel execution
        print(f"[Harvester] Running {len(targets)} platforms with {parallel} workers...")
        h = headless if headless is not None else (os.getenv("HEADLESS", "false").lower() == "true")
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as executor:
            future_to_name = {
                executor.submit(run_single_platform, name, h): name
                for name in targets if name in STRATEGIES
            }
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    keys = future.result()
                    if keys:
                        all_keys[name] = keys
                        save_keys(all_keys)
                except Exception as e:
                    print(f"[Harvester] [{name}] Exception: {e}")
                    all_keys[name] = {"error": str(e)}

    save_keys(all_keys)
    print(f"\n*** Harvesting complete. {len(targets)} platforms processed. Results saved to harvested_keys.json ***")
    return all_keys


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="API Key Harvester v3.0")
    parser.add_argument("--platforms", nargs="+", help="Target platforms (default: all)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--show", action="store_true", help="Show previously harvested keys")
    parser.add_argument("--parallel", type=int, default=1, help="Number of platforms to run in parallel (default: 1)")

    # Stealth Stack options
    parser.add_argument("--cloakbrowser", action="store_true", help="Use CloakBrowser (C++-level stealth)")
    parser.add_argument("--stealth-captcha", action="store_true", help="Use Stealth Stack CAPTCHA solver (Gemini+Whisper+BrightData)")
    parser.add_argument("--gemini-key", type=str, help="Gemini API key (or set GEMINI_API_KEY in .env)")
    parser.add_argument("--brightdata-token", type=str, help="Bright Data Web Unlocker token (or set BRIGHTDATA_TOKEN in .env)")
    parser.add_argument("--whisper-model", type=str, default="base", help="Whisper model size (tiny, base, small, medium, large-v3)")

    args = parser.parse_args()

    # Configure stealth stack from CLI args
    if args.cloakbrowser:
        os.environ["USE_CLOAKBROWSER"] = "true"
    if args.stealth_captcha:
        os.environ["USE_STEALTH_STACK_CAPTCHA"] = "true"
    if args.gemini_key:
        os.environ["GEMINI_API_KEY"] = args.gemini_key
    if args.brightdata_token:
        os.environ["BRIGHTDATA_TOKEN"] = args.brightdata_token
    if args.whisper_model:
        os.environ["WHISPER_MODEL"] = args.whisper_model

    if args.show:
        keys = load_keys()
        for platform, platform_keys in keys.items():
            print(f"\n[{platform}]")
            for k, v in platform_keys.items():
                if isinstance(v, str):
                    print(f"  {k}: {mask_key(v)}")
                else:
                    print(f"  {k}: {v}")
    else:
        run_harvester(targets=args.platforms, headless=args.headless, parallel=args.parallel)
