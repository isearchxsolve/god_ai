#!/usr/bin/env python3
"""Patreon API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class PatreonStrategy(BaseStrategy):
    NAME = "Patreon"
    LOGIN_URL = "https://www.patreon.com/login"
    SIGNUP_URL = "https://www.patreon.com/signup"
    API_PAGE_URL = "https://www.patreon.com/portal/registration/register-clients"
    EMAIL_VERIFICATION_PLATFORM = "patreon"

    def login(self) -> bool:
        email = os.getenv("PATREON_EMAIL")
        password = os.getenv("PATREON_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} PATREON_EMAIL/PASSWORD not set")
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
                self.page.fill("input[name='email']", email)
            DynamicButtonFinder.click(self.page, "next")
            self.human_delay(1000, 2000)
            if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                self.page.fill("input[name='password']", password)
            DynamicButtonFinder.click(self.page, "submit")
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for Patreon with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("PATREON_EMAIL") or creds["email"]
        password = os.getenv("PATREON_PASSWORD") or creds["password"]

        if not os.getenv("PATREON_EMAIL"):
            self._save_credentials("PATREON_EMAIL", email)
            self._save_credentials("PATREON_PASSWORD", password)

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
            clients = self.page.query_selector_all(".client-card")
            for client in clients:
                name = client.query_selector(".client-name")
                key = client.query_selector(".client-key")
                if key:
                    keys[name.inner_text() if name else "api_key"] = key.inner_text()
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
