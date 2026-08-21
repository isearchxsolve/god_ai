#!/usr/bin/env python3
"""
Misc Helpers
============
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, Optional


def _default_keys_path() -> str:
    """Return cross-platform default path for harvested keys."""
    # Prefer project directory structure if it exists
    project_dir = Path(__file__).parent.parent
    default_dir = project_dir / "api_key_harvester"
    if default_dir.exists():
        return str(default_dir / "harvested_keys.json")
    # Fallback to current working directory
    return "harvested_keys.json"


def save_keys(keys: Dict, path: str = None):
    """Save harvested keys to JSON."""
    path = path or _default_keys_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(keys, f, indent=2, default=str)


def load_keys(path: str = None) -> Optional[Dict]:
    """Load previously harvested keys."""
    path = path or _default_keys_path()
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def mask_key(key: str) -> str:
    """Mask an API key for display."""
    if not key or len(key) < 8:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


def extract_site_key(page) -> Optional[str]:
    """Try to extract reCAPTCHA site key from page."""
    # Try data-sitekey attribute
    elem = page.query_selector("[data-sitekey]")
    if elem:
        return elem.get_attribute("data-sitekey")

    # Try from page source
    html = page.content()
    match = re.search(r'data-sitekey="([a-zA-Z0-9_-]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r"sitekey[\'\"]?\s*:\s*[\'\"]([a-zA-Z0-9_-]+)", html)
    if match:
        return match.group(1)

    # Try to extract from reCAPTCHA iframe URL (v3 invisible)
    for frame in page.frames:
        if 'recaptcha' in frame.url and 'k=' in frame.url:
            # Extract sitekey from iframe URL parameter k=
            match = re.search(r'[?&]k=([a-zA-Z0-9_-]+)', frame.url)
            if match:
                return match.group(1)

    return None


def safe_evaluate(page, js: str, default=None):
    """Safely evaluate JS on page, return default on error."""
    try:
        return page.evaluate(js)
    except Exception:
        return default
