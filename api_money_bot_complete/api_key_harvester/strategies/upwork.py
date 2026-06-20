#!/usr/bin/env python3
"""Upwork API Key Harvester - FIXED with dynamic selectors and verified URLs"""
import os
from typing import Dict
from .base import BaseStrategy

class UpworkStrategy(BaseStrategy):
    NAME = "Upwork"
    LOGIN_URL = "https://www.upwork.com/ab/account-security/login"
    SIGNUP_URL = "https://www.upwork.com/nx/join"
    API_PAGE_URL = "https://www.upwork.com/freelancers/settings/contact-info"
    EMAIL_VERIFICATION_PLATFORM = "upwork"

    def login(self) -> bool:
        email = os.getenv("UPWORK_EMAIL")
        password = os.getenv("UPWORK_PASSWORD")
        if not email or not password:
            print(f"{self.log_prefix} UPWORK_EMAIL/PASSWORD not set")
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
                self.page.fill("input[name='login[username]']", email)
            DynamicButtonFinder.click(self.page, "submit")
            self.human_delay(2000, 3000)
            if not DynamicFieldFinder.find_and_fill(self.page, "password", password):
                self.page.fill("input[name='login[password]']", password)
            self.handle_captcha()
            DynamicButtonFinder.click(self.page, "submit")
        except Exception as e:
            print(f"{self.log_prefix} Login error: {e}")
            return False

        return self._wait_for_post_login()

    def signup(self) -> bool:
        """Automated signup for Upwork with dynamic field discovery."""
        print(f"{self.log_prefix} Starting automated signup...")

        creds = self.generate_credentials()
        email = os.getenv("UPWORK_EMAIL") or creds["email"]
        password = os.getenv("UPWORK_PASSWORD") or creds["password"]

        if not os.getenv("UPWORK_EMAIL"):
            self._save_credentials("UPWORK_EMAIL", email)
            self._save_credentials("UPWORK_PASSWORD", password)

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
            token = self.page.query_selector(".oauth-token")
            if token:
                keys["oauth_token"] = token.inner_text()
        except Exception as e:
            print(f"{self.log_prefix} Extraction error: {e}")
        return keys
