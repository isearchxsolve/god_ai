#!/usr/bin/env python3
"""Binance API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class BinanceStrategy(BaseStrategy):
    NAME = "Binance"
    LOGIN_URL = "https://accounts.binance.com/en/login"
    SIGNUP_URL = "https://accounts.binance.com/en/register"
    API_PAGE_URL = "https://www.binance.com/en/my/settings/api-management"
    EMAIL_VERIFICATION_PLATFORM = "binance"

    def login(self) -> bool:
        email = os.getenv("BINANCE_EMAIL")
        password = os.getenv("BINANCE_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} BINANCE_EMAIL/PASSWORD not set")
            return False

        self.page.goto(self.LOGIN_URL)
        self.human_delay(1000, 2000)

        # Try dynamic login first, fallback to hardcoded selectors
        if self._dynamic_login(email, password):
            return self._wait_for_post_login()

        # Fallback to hardcoded selectors
        try:
            from utils.dynamic_selector import DynamicFieldFinder, DynamicButtonFinder
            if not DynamicFieldFinder.find_and_fill(self.page, "email", email):
                self.page.fill("input[name='username'], input[type='email']", email)
            DynamicButtonFinder.click(self.page, "submit")
            self.human_delay(1000, 2000)
            if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                self.page.fill("input[type='password'], input[name='password']", password)
            self.handle_captcha()
            DynamicButtonFinder.click(self.page, "submit")
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for Binance with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("BINANCE_EMAIL") or creds["email"]
        password = os.getenv("BINANCE_PASSWORD") or creds["password"]

        if not os.getenv("BINANCE_EMAIL"):
            self._save_credentials("BINANCE_EMAIL", email)
            self._save_credentials("BINANCE_PASSWORD", password)

        self.page.goto(self.SIGNUP_URL)
        self.human_delay(2000, 3000)

        # Use dynamic field discovery first
        from utils.smart_field_detector import SmartFieldDetector
        from utils.dynamic_selector import DynamicFieldFinder, DynamicButtonFinder

        values = {"email": email, "password": password, "username": creds["username"]}
        filled = SmartFieldDetector.fill_all(self.page, values)

        if not filled.get("email"):
            # Fallback to hardcoded selectors
            try:
                self.page.fill("input[type='email'], input[name='email']", email)
                self.page.fill("input[type='password'], input[name='password']", password)
            except Exception as e:
                print(f"{self.log_prefix} Fallback signup error: {e}")

        self.human_delay(1000, 2000)
        self.handle_captcha()
        self._click_submit("signup")

        # Handle post-submit states
        state = self._detect_post_submit_state()
        self._handle_post_submit_state(state, email)

        return self._wait_for_post_login(self.TIMEOUT_LONG)

    def extract_keys(self) -> Dict[str, str]:
        self.page.goto(self.API_PAGE_URL)
        self.human_delay(2000, 4000)
        keys = {}
        try:
            rows = self.page.query_selector_all(".api-key-row, [data-testid='api-key-row'], .bn-table-row, tr:has(td)")
            for row in rows:
                key_name = row.query_selector(".api-key-name, [data-testid='api-key-name'], td:first-child")
                key_val = row.query_selector(".api-key-val, [data-testid='api-key-value'], td:nth-child(2)")
                if key_val and key_val.inner_text().strip():
                    keys[key_name.inner_text().strip() if key_name else "api_key"] = key_val.inner_text().strip()
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
