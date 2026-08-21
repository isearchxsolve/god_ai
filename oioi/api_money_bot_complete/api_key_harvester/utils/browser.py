#!/usr/bin/env python3
"""
Stealth Browser Factory
========================
Uses Playwright + playwright-stealth with fingerprint rotation,
proxy support, and session persistence.
"""

import random
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from dotenv import load_dotenv

load_dotenv()


class StealthBrowser:
    """Context manager for stealth browser sessions."""

    def __init__(self, headless: bool = None, proxy: str = None, storage_state: str = None):
        self.headless = headless if headless is not None else (os.getenv("HEADLESS", "false").lower() == "true")
        self.proxy = proxy or os.getenv("PROXY_SERVER")
        self.storage_state = storage_state
        self._stealth = Stealth()

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

        self.browser = None
        self.context = None
        self._page = None
        self.playwright = None

    def __enter__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080",
                "--start-maximized",
            ]
        )

        context_options = {
            "viewport": self.viewport,
            "user_agent": self.user_agent,
            "timezone_id": self.timezone,
            "locale": self.locale,
            "permissions": ["geolocation"],
            "geolocation": {
                "latitude": random.uniform(25.0, 50.0),
                "longitude": random.uniform(-125.0, -70.0),
            },
            "color_scheme": random.choice(["light", "dark"]),
        }

        if self.proxy and self.proxy != "http://user:pass@ip:port":
            context_options["proxy"] = {"server": self.proxy}

        if self.storage_state and Path(self.storage_state).exists():
            context_options["storage_state"] = self.storage_state

        self.context = self.browser.new_context(**context_options)
        self.context.set_extra_http_headers({
            "Accept-Language": f"{self.locale},{self.locale.split('-')[0]};q=0.9",
            "DNT": "1",
        })

        self._page = self.context.new_page()
        self._stealth.apply_stealth_sync(self._page)

        # Mask webdriver, fix chrome.loadTimes for BFP detection
        self._page.evaluate("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            // Fix chrome.loadTimes — Adobe BFP checks for this
            if (!window.chrome) { window.chrome = {}; }
            if (!window.chrome.loadTimes) {
                window.chrome.loadTimes = function() {
                    return {
                        requestTime: 0,
                        startLoadTime: 0,
                        commitLoadTime: 0,
                        finishDocumentLoadTime: 0,
                        finishLoadTime: 0,
                        firstPaintTime: 0,
                        firstPaintAfterLoadTime: 0,
                        navigationType: 'other',
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: false,
                        npnNegotiatedProtocol: 'unknown',
                        wasAlternateProtocolAvailable: false,
                        connectionInfo: 'http/2',
                    };
                };
            }
            if (!window.chrome.csi) {
                window.chrome.csi = function() { return { onloadT: 0, startE: 0, pageT: Date.now(), tran: 15 }; };
            }
            // Fix outerHeight — Adobe BFP checks for window resizing
            const origOuterHeight = Object.getOwnPropertyDescriptor(Window.prototype, 'outerHeight');
            if (origOuterHeight && origOuterHeight.get) {
                const realGet = origOuterHeight.get;
                Object.defineProperty(window, 'outerHeight', {
                    get: () => Math.max(realGet.call(window), 600)
                });
            }
            // Languages array
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)

        return self

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, value):
        self._page = value

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        self.playwright.stop()

    def save_session(self, path: str):
        """Save cookies/storage state to file."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=path)

    def human_delay(self, min_ms: int = 800, max_ms: int = 3500):
        """Random delay to mimic human behavior."""
        self._page.wait_for_timeout(random.randint(min_ms, max_ms))

    def human_type(self, selector: str, text: str):
        """Type like a human with random delays between keystrokes."""
        self._page.focus(selector)
        self.human_delay(100, 300)
        for char in text:
            self._page.type(selector, char, delay=random.randint(50, 150))
        self.human_delay(200, 500)
