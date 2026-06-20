#!/usr/bin/env python3
"""Coinbase API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class CoinbaseStrategy(BaseStrategy):
    NAME = "Coinbase"
    LOGIN_URL = "https://login.coinbase.com/signin"
    SIGNUP_URL = "https://login.coinbase.com/signup"
    API_PAGE_URL = "https://cloud.coinbase.com/access/api"
    EMAIL_VERIFICATION_PLATFORM = "coinbase"

    def login(self) -> bool:
        email = os.getenv("COINBASE_EMAIL")
        password = os.getenv("COINBASE_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} COINBASE_EMAIL/PASSWORD not set")
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
                self.page.fill("input[type='email']", email)
            DynamicButtonFinder.click(self.page, "submit")
            self.human_delay(2000, 3000)
            if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                self.page.fill("input[type='password']", password)
            self.handle_captcha()
            DynamicButtonFinder.click(self.page, "submit")
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for Coinbase with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("COINBASE_EMAIL") or creds["email"]
        password = os.getenv("COINBASE_PASSWORD") or creds["password"]

        if not os.getenv("COINBASE_EMAIL"):
            self._save_credentials("COINBASE_EMAIL", email)
            self._save_credentials("COINBASE_PASSWORD", password)

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
            rows = self.page.query_selector_all("[data-testid='api-key-row']")
            for row in rows:
                name = row.query_selector(".key-name")
                key = row.query_selector(".key-value")
                if key:
                    keys[name.inner_text() if name else "api_key"] = key.inner_text()
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
