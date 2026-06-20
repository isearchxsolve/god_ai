#!/usr/bin/env python3
"""
CloakBrowser Integration for API Key Harvester
===============================================
Drop-in replacement for StealthBrowser using CloakBrowser stealth runtime.
Compatible with existing strategy interface (has .page, context manager, save_session, etc.)
"""

import os
import random
import time
from pathlib import Path
from typing import Optional

try:
    from cloakbrowser import launch
except ImportError:
    raise ImportError("CloakBrowser not installed. Install via: pip install cloakbrowser")


class CloakStealthBrowser:
    """
    Context manager for CloakBrowser stealth sessions.
    Mimics StealthBrowser interface for drop-in compatibility.
    """

    def __init__(
        self,
        headless: bool = None,
        proxy: str = None,
        storage_state: str = None,
        fingerprint_seed: str = None,
    ):
        self.headless = headless if headless is not None else (os.getenv("HEADLESS", "false").lower() == "true")
        self.proxy = proxy or os.getenv("PROXY_SERVER")
        self.storage_state = storage_state
        self.fingerprint_seed = fingerprint_seed or f"edu_{int(time.time())}_{random.randint(1000, 9999)}"

        # Random fingerprint per session
        self.viewport = {
            "width": random.choice([1366, 1440, 1536, 1920]),
            "height": random.choice([768, 900, 864, 1080]),
        }
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        self.timezone = random.choice([
            "America/New_York", "Europe/London", "Europe/Berlin",
            "Asia/Tokyo", "Asia/Singapore", "America/Los_Angeles"
        ])
        self.locale = random.choice(["en-US", "en-GB", "en-CA"])

        self._browser = None
        self._page = None
        self._context = None

    def __enter__(self):
        self._browser = launch(
            headless=self.headless,
            humanize=True,
            human_preset="careful",
            proxy=self.proxy,
            geoip=True,
            args=[
                f"--fingerprint={self.fingerprint_seed}",
                "--fingerprint-platform=windows",
                "--fingerprint-webrtc-ip=auto",
            ],
        )
        # CloakBrowser uses pages directly, no separate context concept
        self._page = self._browser.new_page()
        self._setup_page()
        return self

    def _setup_page(self):
        """Apply stealth evasions and fingerprint masking."""
        # Set viewport
        self._page.set_viewport_size(self.viewport)

        # Mask webdriver and inject fingerprint fixes
        self._page.evaluate("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            if (!window.chrome) { window.chrome = {}; }
            if (!window.chrome.loadTimes) {
                window.chrome.loadTimes = function() {
                    return {
                        requestTime: 0, startLoadTime: 0, commitLoadTime: 0,
                        finishDocumentLoadTime: 0, finishLoadTime: 0,
                        firstPaintTime: 0, firstPaintAfterLoadTime: 0,
                        navigationType: 'other', wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false, npnNegotiatedProtocol: 'unknown',
                        wasAlternateProtocolAvailable: false, connectionInfo: 'http/2',
                    };
                };
            }
            if (!window.chrome.csi) {
                window.chrome.csi = function() { return { onloadT: 0, startE: 0, pageT: Date.now(), tran: 15 }; };
            }
            const origOuterHeight = Object.getOwnPropertyDescriptor(Window.prototype, 'outerHeight');
            if (origOuterHeight && origOuterHeight.get) {
                const realGet = origOuterHeight.get;
                Object.defineProperty(window, 'outerHeight', {
                    get: () => Math.max(realGet.call(window), 600)
                });
            }
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)

        # Extra HTTP headers
        self._page.set_extra_http_headers({
            "Accept-Language": f"{self.locale},{self.locale.split('-')[0]};q=0.9",
            "DNT": "1",
        })

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, value):
        self._page = value

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            self._browser.close()
        return False

    def save_session(self, path: str):
        """Save cookies/storage state to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # CloakBrowser doesn't have storage_state, but we can save cookies via CDP
        try:
            cookies = self._page.context.cookies()
            import json
            with open(path, 'w') as f:
                json.dump(cookies, f)
        except Exception as e:
            print(f"[CloakBrowser] Warning: Could not save session: {e}")

    def human_delay(self, min_ms: int = 800, max_ms: int = 3500):
        """Random delay to mimic human behavior."""
        time.sleep(random.uniform(min_ms / 1000.0, max_ms / 1000.0))

    def human_type(self, selector: str, text: str):
        """Type like a human with random delays between keystrokes."""
        self._page.focus(selector)
        self.human_delay(0.1, 0.3)
        for char in text:
            self._page.type(selector, char, delay=random.randint(50, 150))
        self.human_delay(0.2, 0.5)

    def goto(self, url: str, wait_until: str = "domcontentloaded", min_wait: float = 3.0):
        """Navigate without CDP artifacts that behavioral checks detect."""
        self._page.goto(url, wait_until=wait_until)
        time.sleep(min_wait)

        # Simulate reading behavior with natural mouse drift
        self._page.mouse.move(
            400 + random.randint(-50, 50),
            300 + random.randint(-30, 30),
        )
        time.sleep(random.uniform(0.3, 0.8))
        self._page.mouse.move(
            450 + random.randint(-40, 40),
            500 + random.randint(-20, 20),
        )
        time.sleep(random.uniform(0.5, 1.2))

    def pre_challenge_warming(self):
        """Simulate natural page engagement before challenge interaction."""
        paragraphs = self._page.locator("p").all()
        for p in paragraphs[:random.randint(2, 5)]:
            try:
                box = p.bounding_box()
                if box:
                    self._page.mouse.move(
                        box["x"] + random.randint(10, max(15, int(box["width"]) - 10)),
                        box["y"] + random.randint(5, max(10, int(box["height"]) - 5)),
                    )
                    time.sleep(random.uniform(0.5, 2.0))
            except Exception:
                continue

        # Scroll down then up
        self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(1, 3))
        self._page.evaluate("window.scrollTo(0, 0)")
        time.sleep(2)