#!/usr/bin/env python3
"""
Base Strategy --- Abstract class for all API key harvesters.
FIXED v2: Realistic timeouts, no hardcoded credentials, dynamic selector integration,
       unified _save_credentials, proper error recovery.
"""

import time
import string
import random
from abc import ABC, abstractmethod
from typing import Dict, Optional
import os


class BaseStrategy(ABC):
    """Abstract base for all platform API key harvesters."""

    NAME: str = "base"
    LOGIN_URL: str = ""
    SIGNUP_URL: str = ""
    API_PAGE_URL: str = ""
    EMAIL_VERIFICATION_PLATFORM: str = ""
    SELECTORS: Dict[str, str] = {}

    # Realistic timeout constants (milliseconds)
    TIMEOUT_SHORT = 10000
    TIMEOUT_MEDIUM = 20000
    TIMEOUT_LONG = 30000
    TIMEOUT_EMAIL = 60000
    POLL_INTERVAL = 5000

    def __init__(self, browser, captcha_solver=None):
        self.browser = browser
        self.page = browser.page if hasattr(browser, 'page') else browser
        self.captcha = captcha_solver
        self.log_prefix = f"[{self.NAME}]"

    def _log(self, msg: str):
        print(f"{self.log_prefix} {msg}")

    @abstractmethod
    def login(self) -> bool:
        pass

    @abstractmethod
    def extract_keys(self) -> Dict[str, str]:
        pass

    def signup(self) -> bool:
        self._log("Using generic auto-signup...")
        return self._auto_signup()

    def _scan_fields(self, phase: str) -> dict:
        from utils.smart_field_detector import SmartFieldDetector
        self._log(f">>> BEGIN SCAN [{phase}] <<<")
        fields = SmartFieldDetector.find_all_fields(self.page)
        has_email = any(f.get("type") == "email" for f in fields)
        has_pwd = any(f.get("type") == "password" for f in fields)
        has_code = any(
            f.get("type") in ("text", "tel", "number") and
            any(k in (f.get("labelText", "") + f.get("placeholder", "") + f.get("name", "")).lower()
            for k in ["code", "verification", "otp", "mfa", "2fa"])
            for f in fields
        )
        btns = self.page.query_selector_all("button, a[role='button'], input[type='submit']")
        button_texts = []
        for b in btns:
            try:
                t = b.inner_text().strip()
                if t:
                    button_texts.append(t.lower())
            except:
                pass
        has_submit_btn = any(t in ("create account", "sign up", "register", "submit", "join", "get started", "continue", "save", "next", "log in", "sign in") for t in button_texts)
        self._log(f"    fields={len(fields)}, email={has_email}, pwd={has_pwd}, code={has_code}, submit={has_submit_btn}, buttons={button_texts[:5]}")
        for f in fields:
            t = f.get("type", "none")
            lbl = (f.get("labelText", "") or f.get("placeholder", "") or f.get("name", ""))[:40]
            self._log(f"      - type={t!r} name={f.get('name','')!r} label={lbl!r}")
        self._log(f">>> END SCAN [{phase}] <<<")
        return {
            "fields": fields,
            "has_email": has_email,
            "has_pwd": has_pwd,
            "has_code": has_code,
            "has_submit_btn": has_submit_btn,
            "button_texts": button_texts,
        }

    def _detect_post_submit_state(self) -> str:
        from utils.smart_field_detector import SmartFieldDetector
        self._log(">>> BEGIN SCAN [post_submit_state_detection] <<<")
        self.page.wait_for_timeout(2000)
        url = self.page.url.lower()
        fields = SmartFieldDetector.find_all_fields(self.page)
        code_field = any(
            f.get("type") in ("tel", "text", "number") and
            any(k in (f.get("labelText","") + f.get("placeholder","") + f.get("name","")).lower()
                for k in ["code", "otp", "verification code", "one-time", "mfa", "2fa"])
            for f in fields
        )
        has_name = any(
            f.get("type") in ("text", None) and
            any(k in f.get("labelText", "").lower()
                for k in ["first name", "last name", "full name", "country", "address"])
            for f in fields
        )
        verify_msg = bool(self.page.query_selector("text=/verify your email|check your inbox|confirmation email|verify email/i"))
        is_dashboard = "signup" not in url and "auth" not in url and ("dashboard" in url or "home" in url or url.count("/") <= 3)
        state = "unknown"
        if code_field:
            state = "verify_code"
        elif has_name and len(fields) >= 3:
            state = "profile_form"
        elif verify_msg:
            state = "verify_email"
        elif is_dashboard:
            state = "success"
        self._log(f"    URL={url[:80]}, code={code_field}, name={has_name}, verify={verify_msg}, dash={is_dashboard}")
        self._log(f"    STATE={state}")
        self._log(">>> END SCAN [post_submit_state_detection] <<<")
        return state

    def _handle_profile_form(self) -> bool:
        from utils.smart_field_detector import SmartFieldDetector
        from utils.dynamic_selector import DynamicButtonFinder
        self._log(">>> BEGIN ACTION [handle_profile_form] <<<")
        try:
            creds = self._last_creds
        except AttributeError:
            self._log("    No _last_creds, using defaults")
            creds = {}
        values = {
            "first_name": creds.get("first_name", "Alex"),
            "last_name": creds.get("last_name", "Smith"),
            "full_name": creds.get("full_name", "Alex Smith"),
            "country": creds.get("country", "United States"),
            "phone": creds.get("phone", "555" + str(random.randint(1000000, 9999999))),
            "company": "MoneyBot Inc.",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "address": "123 Wall Street",
            "website": "https://moneybot.ai",
        }
        try:
            results = SmartFieldDetector.fill_all(self.page, values)
            self._log(f"    Profile fill results: {results}")
            try:
                self.page.select_option("select", index=1)
            except:
                pass
            self._click_submit("profile")
        except Exception as e:
            self._log(f"    Profile form crashed (likely redirect): {e}")
        self._log(">>> END ACTION [handle_profile_form] <<<")
        return True

    def _handle_verify_code(self, timeout: int = 60) -> bool:
        self._log(">>> BEGIN ACTION [handle_verify_code] <<<")
        if hasattr(self, 'temp_mail') and self.temp_mail:
            self._log(f"    Waiting {timeout}s for code via TempMail...")
            result = self.temp_mail.wait_for_code(self.NAME.lower(), timeout=timeout)
            if result and result.get("code"):
                code = result["code"]
                self._log(f"    Got code from TempMail: {code}")
                from utils.dynamic_selector import DynamicFieldFinder
                DynamicFieldFinder.find_and_fill(self.page, "code", code)
                self._click_submit("verify_code")
                self._log(">>> END ACTION [handle_verify_code] — CODE ENTERED <<<")
                return True
        self._log("    No code received, looking for skip/later button...")
        for btn_text in ["Skip", "Resend", "Later", "I'll do this later", "Remind me later", "Continue"]:
            btn = self.page.query_selector(f"button:has-text('{btn_text}'), a:has-text('{btn_text}')")
            if btn:
                btn.click()
                self._log(f"    Clicked '{btn_text}'")
                self._log(">>> END ACTION [handle_verify_code] — SKIPPED <<<")
                return True
        self._log(">>> END ACTION [handle_verify_code] — FAILED <<<")
        return False

    def _handle_verify_email(self) -> bool:
        self._log(">>> BEGIN ACTION [handle_verify_email] <<<")
        for btn_text in ["Skip", "Continue", "Remind me later", "I'll do this later", "Resend"]:
            btn = self.page.query_selector(f"button:has-text('{btn_text}'), a:has-text('{btn_text}')")
            if btn:
                btn.click()
                self._log(f"    Clicked '{btn_text}'")
                self._log(">>> END ACTION [handle_verify_email] <<<")
                return True
        self._log(">>> END ACTION [handle_verify_email] — NO SKIP FOUND <<<")
        return False

    def _safe_page(self):
        try:
            _ = self.page.url
            return self.page
        except Exception:
            if hasattr(self, 'browser') and hasattr(self.browser, 'context'):
                pages = self.browser.context.pages
                if pages:
                    self.page = pages[-1]
                    self._log(f"Page replaced! Switched to: {self.page.url}")
                    return self.page
            raise

    def _click_submit(self, phase: str = "", expect_nav: bool = False) -> bool:
        from utils.dynamic_selector import DynamicButtonFinder
        self._log(f">>> BEGIN ACTION [click_submit / {phase}] <<<")
        for action in ["submit", "signup", "create", "next", "continue", "save"]:
            if DynamicButtonFinder.click(self.page, action):
                self._log(f"    Clicked via DynamicButtonFinder: {action}")
                self._log(f">>> END ACTION [click_submit / {phase}] <<<")
                return True
        btns = self.page.query_selector_all("button, a[role='button'], input[type='submit']")
        for b in btns:
            try:
                t = b.inner_text().strip().lower()
                btn_type = b.get_attribute("type") or ""
                if t in ("create account", "sign up", "register", "submit", "join", "get started", "continue", "save", "next", "log in", "sign in") or btn_type == "submit":
                    if expect_nav:
                        with self.page.expect_navigation(timeout=self.TIMEOUT_LONG):
                            b.click()
                    else:
                        b.click()
                    self._log(f"    Clicked: '{b.inner_text().strip()}' (type={btn_type})")
                    self._log(f">>> END ACTION [click_submit / {phase}] <<<")
                    return True
            except:
                pass
        self._log(f">>> END ACTION [click_submit / {phase}] — FAILED <<<")
        return False

    def _auto_signup(self) -> bool:
        from utils.smart_field_detector import SmartFieldDetector
        from utils.dynamic_selector import DynamicFieldFinder, DynamicButtonFinder

        creds = self.generate_credentials()
        email = creds["email"]
        password = creds["password"]
        self._save_credentials(f"{self.NAME.upper()}_EMAIL", email)
        self._save_credentials(f"{self.NAME.upper()}_PASSWORD", password)
        self._last_creds = creds

        if not self.SIGNUP_URL:
            self._log("No SIGNUP_URL configured")
            return False

        self._log(">>> BEGIN ACTION [navigate] <<<")
        self._log(f"Navigating to {self.SIGNUP_URL}")
        self.page.goto(self.SIGNUP_URL, wait_until="domcontentloaded")
        self.human_delay(1500, 2500)
        self._screenshot("signup_01_landed")
        self._log(">>> END ACTION [navigate] <<<")

        self._log("Waiting for form fields to render...")
        try:
            self.page.wait_for_selector(
                "input[type='email'], input[type='password'], input[name*='email'], "
                "input[name*='password'], input[name='username']",
                timeout=self.TIMEOUT_MEDIUM
            )
            self._log("Form fields detected")
        except Exception:
            self._log("No form fields found on initial page load")

        scan1 = self._scan_fields("landing_page")

        if scan1["has_email"] and scan1["has_pwd"]:
            self._log("Form already present — filling directly")
            values = {"email": email, "password": password, "username": creds["username"]}
            SmartFieldDetector.fill_all(self.page, values)
            self.handle_captcha()
            self._click_submit("landing")
            state = self._detect_post_submit_state()
            self._handle_post_submit_state(state, email)
            return True

        if not scan1["has_email"] and not scan1["has_pwd"]:
            clicked = False
            if any("sign up" in t or "join" in t or "create" in t for t in scan1["button_texts"]):
                self._log(">>> BEGIN ACTION [click_signup_button] <<<")
                DynamicButtonFinder.click(self.page, "signup")
                self._log(">>> END ACTION [click_signup_button] <<<")
                clicked = True
            elif any("sign in" in t or "log in" in t for t in scan1["button_texts"]):
                self._log(">>> BEGIN ACTION [click_login_button] <<<")
                DynamicButtonFinder.click(self.page, "submit")
                self._log(">>> END ACTION [click_login_button] <<<")
                clicked = True
            if clicked:
                self.human_delay(2000, 3000)
                if len(self.browser.context.pages) > 1:
                    self.page = self.browser.context.pages[-1]
                    self._log(f"Switched to new tab: {self.page.url}")
                self._screenshot("signup_02_after_join")
                try:
                    self.page.wait_for_selector(
                        "input[type='email'], input[type='password'], input[name*='email'], "
                        "input[name*='password'], input[name='username']",
                        timeout=self.TIMEOUT_MEDIUM
                    )
                    self._log("Form fields appeared")
                except Exception:
                    self._log("No form fields appeared after click")
                self.human_delay(1000, 2000)
                scan2 = self._scan_fields("auth_page")
                has_email_field = scan2["has_email"]
                has_pwd_field = scan2["has_pwd"]
            else:
                has_email_field = scan1["has_email"]
                has_pwd_field = scan1["has_pwd"]
        else:
            has_email_field = scan1["has_email"]
            has_pwd_field = scan1["has_pwd"]

        if not has_email_field:
            self._log("No email field found on page")
            self._screenshot("signup_error_no_email")
            return False

        self._log(">>> BEGIN ACTION [fill_signup_form] <<<")
        values = {"email": email, "password": password, "username": creds["username"]}
        SmartFieldDetector.fill_all(self.page, values)
        if has_pwd_field:
            self._log("Filled email + password")
        else:
            self._log("Filled email (password field not yet visible)")
            self._click_submit("email_step")
            self.human_delay(1000, 2000)
            SmartFieldDetector.fill_all(self.page, values)
            self._log("Filled password after email step")
        self._log(">>> END ACTION [fill_signup_form] <<<")

        self._screenshot("signup_06_before_captcha")
        self.handle_captcha()

        self._screenshot("signup_07_before_submit")
        self._click_submit("signup")
        self._screenshot("signup_08_submitted")

        state = self._detect_post_submit_state()
        self._handle_post_submit_state(state, email)
        return True

    def generate_credentials(self) -> Dict[str, str]:
        email = os.getenv("GMAIL_EMAIL")
        if not email:
            rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"moneybot_{rand}@mail.tm"
        password = os.getenv("GMAIL_APP_PASSWORD")
        if not password:
            password = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=16))
        username = email.split('@')[0]
        return {
            "username": username,
            "email": email,
            "password": password,
            "first_name": "Money",
            "last_name": "Bot",
            "full_name": "Money Bot",
        }

    def wait_for_email_verification(self, timeout: int = 60) -> Optional[Dict]:
        platform = self.EMAIL_VERIFICATION_PLATFORM or self.NAME.lower()
        print(f"{self.log_prefix} Waiting for email verification ({platform})...")

        gmail_alias = getattr(self, '_gmail_alias', None)
        if gmail_alias:
            print(f"{self.log_prefix} Fetching verification via Gmail IMAP (alias: {gmail_alias})...")
            try:
                from utils.email_verifier import GmailAliasVerifier
                verifier = GmailAliasVerifier(gmail_alias)
                result = verifier.wait_for_code(platform, timeout=timeout)
                if result:
                    return result
            except ImportError:
                print(f"{self.log_prefix} GmailAliasVerifier not available")
            except Exception as e:
                print(f"{self.log_prefix} Gmail IMAP error: {e}")

        if hasattr(self, 'temp_mail') and self.temp_mail:
            print(f"{self.log_prefix} Fetching code via TempMail API...")
            result = self.temp_mail.wait_for_code(platform, timeout=timeout)
            if result and result.get("code"):
                print(f"{self.log_prefix} Got code from TempMail: {result['code']}")
                return result
            print(f"{self.log_prefix} TempMail did not return a code")

        try:
            from utils.email_verifier import wait_for_email_verification
            result = wait_for_email_verification(platform, timeout=timeout)
            return result
        except ImportError:
            print(f"{self.log_prefix} Gmail verifier not available")
            return None
        except Exception as e:
            print(f"{self.log_prefix} Email verification error: {e}")
            return None

    def apply_verification(self, verification_result: Dict) -> bool:
        if not verification_result:
            return False

        if verification_result.get("code"):
            code = verification_result["code"]
            print(f"{self.log_prefix} Using verification code: {code}")
            try:
                from utils.dynamic_selector import DynamicFieldFinder
                if DynamicFieldFinder.find_and_fill(self.page, "code", code):
                    self.page.wait_for_timeout(1000)
                    self._click_submit("verify_code")
                    return True
            except Exception as e:
                print(f"{self.log_prefix} Code application failed: {e}")

        if verification_result.get("link"):
            link = verification_result["link"]
            print(f"{self.log_prefix} Following verification link: {link[:80]}...")
            try:
                self.page.goto(link)
                self.page.wait_for_timeout(5000)
                return True
            except Exception as e:
                print(f"{self.log_prefix} Link navigation failed: {e}")

        return False

    def run(self) -> Dict[str, str]:
        print(f"{self.log_prefix} Starting harvest...")
        self._screenshot("run_start")

        if self.login():
            self._screenshot("run_after_login")
            keys = self.extract_keys()
            if keys:
                print(f"{self.log_prefix} Harvested {len(keys)} key(s)")
            else:
                print(f"{self.log_prefix} No keys found")
            return keys

        if os.getenv("AUTO_SIGNUP", "false").lower() == "true":
            print(f"{self.log_prefix} Login failed, attempting signup...")
            self._screenshot("run_before_signup")
            if self.signup():
                self._log("Signup flow complete — extracting keys...")
                keys = self._safe_extract_keys()
                if keys:
                    print(f"{self.log_prefix} Harvested {len(keys)} key(s) after signup")
                else:
                    print(f"{self.log_prefix} No keys found after signup")
                if hasattr(self, 'temp_mail') and self.temp_mail:
                    try:
                        self.temp_mail.cleanup()
                    except Exception:
                        pass
                return keys
            else:
                print(f"{self.log_prefix} Signup failed")

        if hasattr(self, 'temp_mail') and self.temp_mail:
            try:
                self.temp_mail.cleanup()
            except Exception:
                pass

        print(f"{self.log_prefix} Login failed")
        self._screenshot("run_failed")
        return {}

    def _safe_extract_keys(self) -> Dict[str, str]:
        try:
            return self.extract_keys()
        except Exception as e:
            self._log(f"Key extraction failed ({e}) — trying fresh navigation")
            try:
                if hasattr(self, 'browser') and hasattr(self.browser, 'context'):
                    pages = self.browser.context.pages
                    if pages:
                        self.page = pages[0]
                        self._log(f"Using remaining page: {self.page.url}")
                        return self.extract_keys()
                if self.API_PAGE_URL:
                    self._log(f"Navigating fresh to {self.API_PAGE_URL}")
                    self.page.goto(self.API_PAGE_URL, wait_until="domcontentloaded")
                    return self.extract_keys()
            except Exception as e2:
                self._log(f"Fallback also failed: {e2}")
            return {}

    def _complete_profile(self):
        print(f"{self.log_prefix} Checking for additional profile fields...")
        self.human_delay(1000, 2000)
        self._screenshot("profile_start")

        from utils.smart_field_detector import SmartFieldDetector
        from utils.dynamic_selector import DynamicButtonFinder

        creds = getattr(self, '_last_creds', self.generate_credentials())
        print(f"{self.log_prefix} >>> SCAN: SmartFieldDetector scanning for profile fields...")
        fields = SmartFieldDetector.find_all_fields(self.page)
        print(f"{self.log_prefix} >>> SCAN complete: {len(fields)} total fields")

        code_fields = [f for f in fields if f.get("type") in ("tel", "text", "number") and
                       ("code" in f.get("labelText","").lower() or "code" in f.get("placeholder","").lower() or
                        "otp" in f.get("labelText","").lower() or "verification" in f.get("labelText","").lower())]
        if code_fields:
            print(f"{self.log_prefix} Page shows verification code input ({len(code_fields)} field(s)) — skipping profile completion")
            return

        unfilled = [f for f in fields if not f.get("isCheckbox") and (
            f["type"] in ("text", "email", "tel", "url", "password", "select", "textarea", None)
        )]

        if not unfilled:
            print(f"{self.log_prefix} No additional fields to fill")
            return

        print(f"{self.log_prefix} Found {len(unfilled)} additional field(s):")
        for f in unfilled:
            label = f.get("labelText") or f.get("placeholder") or f.get("name") or "unknown"
            print(f"  - {label} ({f['type']})")

        values = {
            "email": creds.get("email", ""),
            "password": creds.get("password", ""),
            "first_name": creds.get("first_name", "Money"),
            "last_name": creds.get("last_name", "Bot"),
            "full_name": creds.get("full_name", "Money Bot"),
            "username": creds.get("username", ""),
            "phone": creds.get("phone", "555" + str(random.randint(1000000, 9999999))),
            "company": "MoneyBot Inc.",
            "website": "https://moneybot.ai",
            "country": "United States",
            "city": "New York",
            "state": "NY",
            "zip": "10001",
            "address": "123 Wall Street",
            "code": "123456",
        }

        filled = SmartFieldDetector.fill_all(self.page, values)
        filled_count = sum(1 for v in filled.values() if v)
        if filled_count:
            print(f"{self.log_prefix} >>> ACTION: Filled {filled_count} field(s)")
            self._screenshot("profile_filled")
            print(f"{self.log_prefix} >>> SCAN: Searching for profile submit button...")
            btns = self.page.query_selector_all("button, a[role='button'], input[type='submit']")
            submit_found = False
            for b in btns:
                try:
                    t = b.inner_text().strip().lower()
                    if any(x in t for x in ("continue", "save", "next", "submit", "complete")):
                        b.click()
                        submit_found = True
                        print(f"{self.log_prefix} Clicked submit: '{b.inner_text().strip()}'")
                        break
                except:
                    pass
            if not submit_found:
                print(f"{self.log_prefix} No submit/continue button found for profile")
            self.human_delay(1000, 2000)
            self._screenshot("profile_submitted")
        else:
            print(f"{self.log_prefix} No fields could be filled")

    def _find_and_fill(self, field_type: str, value: str, hardcoded_selectors: list = None) -> bool:
        from utils.dynamic_selector import DynamicFieldFinder
        if DynamicFieldFinder.find_and_fill(self.page, field_type, value):
            return True
        if hardcoded_selectors:
            for sel in hardcoded_selectors:
                try:
                    el = self.page.wait_for_selector(sel, timeout=self.TIMEOUT_SHORT)
                    if el:
                        el.fill(value)
                        return True
                except Exception:
                    continue
        return False

    def _find_and_click_button(self, action_type: str, hardcoded_selectors: list = None) -> bool:
        from utils.dynamic_selector import DynamicButtonFinder
        if DynamicButtonFinder.click(self.page, action_type):
            return True
        if hardcoded_selectors:
            for sel in hardcoded_selectors:
                try:
                    btn = self.page.wait_for_selector(sel, timeout=self.TIMEOUT_SHORT)
                    if btn:
                        btn.click()
                        return True
                except Exception:
                    continue
        return False

    def _dynamic_login(self, email: str, password: str) -> bool:
        try:
            from utils.dynamic_selector import DynamicLoginFlow
            return DynamicLoginFlow.login(self.page, email, password)
        except ImportError:
            return False

    def _wait_for_post_login(self, timeout: int = None) -> bool:
        timeout = timeout or self.TIMEOUT_LONG
        try:
            self.page.wait_for_url("**/dashboard**", timeout=timeout)
            return True
        except Exception:
            pass
        try:
            self.page.wait_for_url("**/home**", timeout=self.TIMEOUT_SHORT)
            return True
        except Exception:
            pass
        try:
            self.page.wait_for_url(lambda url: "login" not in url.lower() and "signin" not in url.lower(), timeout=self.TIMEOUT_SHORT)
            return True
        except Exception:
            pass
        return False

    def handle_captcha(self):
        if os.getenv("MANUAL_CAPTCHA", "false").lower() == "true":
            self._manual_captcha_wait()
            return
        if self.captcha:
            from utils.helpers import extract_site_key
            site_key = extract_site_key(self.page)
            if site_key:
                print(f"{self.log_prefix} Solving reCAPTCHA...")
                token = self.captcha.solve_recaptcha(site_key, self.page.url)
                self.captcha.inject_recaptcha_token(self.page, token)
                self.page.wait_for_timeout(2000)

    def _manual_captcha_wait(self, timeout_ms: int = 120000):
        deadline = time.time() + timeout_ms / 1000.0
        captcha_selectors = (
            "iframe[title*='recaptcha'], iframe[title*='challenge'], "
            "iframe[src*='recaptcha'], iframe[src*='hcaptcha'], "
            ".g-recaptcha, .h-captcha, "
            "[class*='slide-container'], .verify-slider"
        )
        found = self.page.query_selector(captcha_selectors)
        if not found:
            return
        print(f"{self.log_prefix} MANUAL CAPTCHA: Solve the captcha in the browser window.")
        print(f"{self.log_prefix} Waiting up to {timeout_ms//1000}s for captcha to be solved...")
        while time.time() < deadline:
            remaining = int(deadline - time.time())
            if remaining > 0 and remaining % 15 == 0:
                print(f"{self.log_prefix} Still waiting... ({remaining}s left)")
            try:
                if not self.page.query_selector(captcha_selectors):
                    print(f"{self.log_prefix} Captcha solved! Continuing...")
                    return
            except Exception:
                pass
            self.page.wait_for_timeout(1000)
        print(f"{self.log_prefix} Captcha wait timed out")

    def handle_slider_captcha(self) -> bool:
        if not self.captcha:
            return False
        try:
            slider_container = self.page.query_selector(
                ".verify-slider, .bs-slide-container, [class*='slide-container'], "
                "div[class*='slider'], div[class*='puzzle'], div[id*='captcha'], "
                ".security-verification, [class*='captcha-wrapper']"
            )
            if not slider_container:
                if self.page.query_selector("text=Slide to complete") or \
                   self.page.query_selector("text=Security Verification") or \
                   self.page.query_selector("text=puzzle"):
                    print(f"{self.log_prefix} Slider CAPTCHA detected by text")
                else:
                    return False
            print(f"{self.log_prefix} Slider CAPTCHA detected, capturing image...")
            captcha_img = self.page.query_selector(
                "canvas[class*='geetest'], canvas[class*='slide'], "
                "img[class*='captcha'], img[src*='captcha'], img[alt*='captcha'], "
                ".captcha-image, [class*='puzzle-image'], .bs-main-image"
            )
            if not captcha_img:
                if slider_container:
                    img_bytes = slider_container.screenshot()
                else:
                    img_bytes = self.page.screenshot()
            else:
                img_bytes = captcha_img.screenshot()
            import base64
            img_b64 = base64.b64encode(img_bytes).decode()
            print(f"{self.log_prefix} Sending CAPTCHA to 2Captcha...")
            result = self.captcha.solve_slider_captcha(img_b64, self.page.url)
            slider = self.page.query_selector(
                ".bs-slide-thumb, .bs-slide-thumb:hover, "
                "div[class*='slider-btn'], div[class*='slider-button'], "
                "[class*='slider-handle'], button[class*='slider'], "
                ".slider-arrow, [class*='puzzle-btn'], [id*='slth'], [class*='thumb']"
            )
            if not slider:
                print(f"{self.log_prefix} Slider handle not found")
                return False
            print(f"{self.log_prefix} Found slider handle: {slider.get_attribute('class')[:80]}")
            angle = result.get("angle", "0")
            x_offset = result.get("x_offset")
            print(f"{self.log_prefix} CAPTCHA solved: angle={angle}, x_offset={x_offset}")
            try:
                box = slider.bounding_box()
                if box:
                    start_x = box["x"] + box["width"] / 2
                    start_y = box["y"] + box["height"] / 2
                    if x_offset:
                        target_offset = int(x_offset)
                    else:
                        target_offset = int(float(angle) * 2) if angle else 300
                    print(f"{self.log_prefix} Dragging slider by {target_offset}px...")
                    self.page.mouse.move(start_x, start_y)
                    self.page.mouse.down()
                    self.page.wait_for_timeout(200)
                    self.page.mouse.move(start_x + target_offset, start_y + 2, steps=15)
                    self.page.wait_for_timeout(500)
                    self.page.mouse.up()
                    self.page.wait_for_timeout(3000)
                    if not self.page.query_selector("text=Security Verification", timeout=3000):
                        print(f"{self.log_prefix} Slider CAPTCHA passed!")
                        return True
                    else:
                        print(f"{self.log_prefix} Slider CAPTCHA may have failed")
                        return False
            except Exception as e:
                print(f"{self.log_prefix} Drag action failed: {e}")
                return False
        except Exception as e:
            print(f"{self.log_prefix} Slider CAPTCHA handling error: {e}")
            import traceback
            traceback.print_exc()
            return False
        return False

    def _screenshot(self, name: str):
        path = f"debug_{self.NAME.lower()}_{name}.png"
        try:
            self.page.screenshot(path=path)
            print(f"{self.log_prefix} Screenshot: {path}")
        except Exception:
            pass

    def human_delay(self, min_ms=200, max_ms=800):
        self.page.wait_for_timeout(random.randint(min_ms, max_ms))

    def _save_credentials(self, key: str, value: str):
        try:
            env_path = ".env"
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
            found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}" + "\n"
                    found = True
                    break
            if not found:
                lines.append(f"{key}={value}" + "\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            os.environ[key] = value
            print(f"{self.log_prefix} Saved {key} to .env")
        except Exception as e:
            print(f"{self.log_prefix} Failed to save {key}: {e}")
