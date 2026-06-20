#!/usr/bin/env python3
"""Freelancer API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class FreelancerStrategy(BaseStrategy):
    NAME = "Freelancer"
    LOGIN_URL = "https://www.freelancer.com/login"
    SIGNUP_URL = "https://www.freelancer.com/signup"
    API_PAGE_URL = "https://www.freelancer.com/developers/api_keys"
    EMAIL_VERIFICATION_PLATFORM = "freelancer"

    def login(self) -> bool:
        email = os.getenv("FREELANCER_EMAIL")
        password = os.getenv("FREELANCER_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} FREELANCER_EMAIL/PASSWORD not set")
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
                self.page.fill("input[name='email'], input[type='email'], #email", email)
            if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                self.page.fill("input[name='password'], input[type='password'], #password", password)
            DynamicButtonFinder.click(self.page, "submit")
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for Freelancer with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("FREELANCER_EMAIL") or creds["email"]
        password = os.getenv("FREELANCER_PASSWORD") or creds["password"]

        if not os.getenv("FREELANCER_EMAIL"):
            self._save_credentials("FREELANCER_EMAIL", email)
            self._save_credentials("FREELANCER_PASSWORD", password)

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
            key_rows = self.page.query_selector_all(".api-key-row, .key-item, [class*='api_key'], tr")
            for row in key_rows:
                cells = row.query_selector_all("td, .key-value, .key-name, span")
                for cell in cells:
                    text = cell.inner_text().strip()
                    if len(text) > 20 and any(c in text for c in ['-', '_', '.']):
                        label = row.query_selector(".key-label, .key-name, td:first-child")
                        label_text = label.inner_text().strip() if label else "api_key"
                        keys[label_text] = text
                        break
            if not keys:
                page_text = self.page.content()
                import re
                possible_keys = re.findall(r'[A-Za-z0-9_-]{32,}', page_text)
                for i, k in enumerate(possible_keys):
                    keys[f"token_{i}"] = k
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
