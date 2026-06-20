#!/usr/bin/env python3
"""YouTube API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class YouTubeStrategy(BaseStrategy):
    NAME = "YouTube"
    LOGIN_URL = "https://accounts.google.com/signin"
    SIGNUP_URL = "https://accounts.google.com/signup"
    API_PAGE_URL = "https://console.cloud.google.com/apis/credentials"
    EMAIL_VERIFICATION_PLATFORM = "google"

    def login(self) -> bool:
        email = os.getenv("YOUTUBE_EMAIL")
        password = os.getenv("YOUTUBE_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} YOUTUBE_EMAIL/PASSWORD not set")
            return False

        self.page.goto(self.LOGIN_URL)
        self.human_delay(1000, 2000)

        # Try dynamic login first, fallback to hardcoded selectors
        if self._dynamic_login(email, password):
            return self._wait_for_post_login()

        # Fallback to hardcoded selectors
        try:
            from utils.dynamic_selector import DynamicFieldFinder, DynamicButtonFinder
            try:
                email_input = self.page.wait_for_selector("input[type='email'], input[name='identifier']", timeout=self.TIMEOUT_MEDIUM)
                if not DynamicFieldFinder.find_and_fill(self.page, "email", email):
                    email_input.fill(email)
                DynamicButtonFinder.click(self.page, "next")
                self.human_delay(2000, 3000)
                pwd_input = self.page.wait_for_selector("input[type='password'], input[name='password']", timeout=self.TIMEOUT_MEDIUM)
                if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                    pwd_input.fill(password)
                DynamicButtonFinder.click(self.page, "next")
            except Exception as e:
                print(f"{self.log_prefix} Google login error: {e}")
                return False
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for YouTube with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("YOUTUBE_EMAIL") or creds["email"]
        password = os.getenv("YOUTUBE_PASSWORD") or creds["password"]

        if not os.getenv("YOUTUBE_EMAIL"):
            self._save_credentials("YOUTUBE_EMAIL", email)
            self._save_credentials("YOUTUBE_PASSWORD", password)

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
            import re
            key_rows = self.page.query_selector_all("[data-testid='key-row'], .api-key-row, .key-item, .credential-row, md-list-item")
            for row in key_rows:
                name_el = row.query_selector(".key-name, .name, td:first-child, .credential-name")
                key_el = row.query_selector(".key-value, .value, .api-key-value, td:nth-child(2), code")
                if key_el:
                    key_text = key_el.inner_text().strip()
                    if key_text and len(key_text) >= 10:
                        name_text = name_el.inner_text().strip() if name_el else "api_key"
                        keys[name_text] = key_text
            if not keys:
                page_text = self.page.content()
                api_keys = re.findall(r'AIza[0-9A-Za-z_-]{35}', page_text)
                for i, k in enumerate(api_keys):
                    keys[f"api_key_{i}"] = k
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
