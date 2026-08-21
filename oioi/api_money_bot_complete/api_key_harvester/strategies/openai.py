#!/usr/bin/env python3
"""OpenAI API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class OpenaiStrategy(BaseStrategy):
    NAME = "OpenAI"
    LOGIN_URL = "https://platform.openai.com/login"
    SIGNUP_URL = "https://platform.openai.com/signup"
    API_PAGE_URL = "https://platform.openai.com/api-keys"
    EMAIL_VERIFICATION_PLATFORM = "openai"

    def login(self) -> bool:
        email = os.getenv("OPENAI_EMAIL")
        password = os.getenv("OPENAI_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} OPENAI_EMAIL/PASSWORD not set")
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
            DynamicButtonFinder.click(self.page, "submit")
            self.human_delay(2000, 3000)
            if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                self.page.fill("input[name='password']", password)
            DynamicButtonFinder.click(self.page, "submit")
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for OpenAI with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("OPENAI_EMAIL") or creds["email"]
        password = os.getenv("OPENAI_PASSWORD") or creds["password"]

        if not os.getenv("OPENAI_EMAIL"):
            self._save_credentials("OPENAI_EMAIL", email)
            self._save_credentials("OPENAI_PASSWORD", password)

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
            key_rows = self.page.query_selector_all("[data-testid='key-row']")
            for row in key_rows:
                name = row.query_selector(".key-name")
                val = row.query_selector(".key-value")
                if val:
                    keys[name.inner_text() if name else "api_key"] = val.inner_text()
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
