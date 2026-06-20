#!/usr/bin/env python3
"""
Stealth Stack Integration Module
================================
Provides unified access to CloakBrowser and Stealth Stack Captcha Solver
as drop-in replacements for the existing browser and captcha utilities.

Usage:
    from utils.stealth_integration import get_browser, get_captcha_solver

    # Get CloakBrowser-based stealth browser
    browser = get_browser(use_cloakbrowser=True, headless=False)

    # Get Stealth Stack captcha solver (Gemini + Whisper + BrightData)
    captcha = get_captcha_solver(use_stealth_stack=True)
"""

import os
from typing import Optional, Any


def _use_cloakbrowser() -> bool:
    return os.getenv("USE_CLOAKBROWSER", "false").lower() == "true"


def _use_stealth_stack_captcha() -> bool:
    return os.getenv("USE_STEALTH_STACK_CAPTCHA", "false").lower() == "true"


def get_browser(
    use_cloakbrowser: bool = None,
    headless: bool = None,
    proxy: str = None,
    storage_state: str = None,
    **kwargs
) -> Any:
    """
    Factory function to get a stealth browser instance.

    Args:
        use_cloakbrowser: If True, use CloakBrowser (C++-level stealth).
                          If False, use Playwright+playwright-stealth.
                          If None, uses USE_CLOAKBROWSER env var.
        headless: Headless mode (overrides env)
        proxy: Proxy URL (overrides env)
        storage_state: Path to session storage file
        **kwargs: Additional arguments passed to browser constructor

    Returns:
        Browser instance with .page property and context manager support
    """
    use_cloak = use_cloakbrowser if use_cloakbrowser is not None else _use_cloakbrowser()

    if use_cloak:
        from utils.cloak_browser import CloakStealthBrowser
        return CloakStealthBrowser(
            headless=headless,
            proxy=proxy,
            storage_state=storage_state,
            **kwargs
        )
    else:
        from utils.browser import StealthBrowser
        return StealthBrowser(
            headless=headless,
            proxy=proxy,
            storage_state=storage_state,
        )


def get_captcha_solver(
    use_stealth_stack: bool = None,
    **kwargs
) -> Any:
    """
    Factory function to get a captcha solver instance.

    Args:
        use_stealth_stack: If True, use Stealth Stack (Gemini + Whisper + BrightData).
                           If False, use 2Captcha.
                           If None, uses USE_STEALTH_STACK_CAPTCHA env var.
        **kwargs: Additional arguments passed to solver constructor

    Returns:
        Captcha solver instance compatible with strategy interface
    """
    use_stealth = use_stealth_stack if use_stealth_stack is not None else _use_stealth_stack_captcha()

    if use_stealth:
        from utils.stealth_captcha import StealthStackCaptchaSolver
        return StealthStackCaptchaSolver(**kwargs)
    else:
        from utils.captcha import CaptchaSolver
        # Only create if API key is available
        api_key = kwargs.get("api_key") or os.getenv("CAPTCHA_API_KEY")
        if api_key and api_key not in ("", "***"):
            return CaptchaSolver(api_key=api_key)
        return None


def configure_stealth_stack(
    gemini_api_key: str = None,
    brightdata_token: str = None,
    whisper_model: str = "base",
    use_cloakbrowser: bool = True,
    use_stealth_captcha: bool = True,
):
    """
    Configure the stealth stack globally via environment variables.

    Args:
        gemini_api_key: Google AI Studio API key for Gemini 3.5 Flash
        brightdata_token: Bright Data Web Unlocker API token (optional)
        whisper_model: Whisper model size (tiny, base, small, medium, large-v3)
        use_cloakbrowser: Enable CloakBrowser for stealth browsing
        use_stealth_captcha: Enable Stealth Stack captcha solver
    """
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key
    if brightdata_token:
        os.environ["BRIGHTDATA_TOKEN"] = brightdata_token
    os.environ["WHISPER_MODEL"] = whisper_model
    os.environ["USE_CLOAKBROWSER"] = "true" if use_cloakbrowser else "false"
    os.environ["USE_STEALTH_STACK_CAPTCHA"] = "true" if use_stealth_captcha else "false"


# Backward compatibility - module-level constants (evaluated at import time)
USE_CLOAKBROWSER = _use_cloakbrowser()
USE_STEALTH_STACK_CAPTCHA = _use_stealth_stack_captcha()

# Auto-configure from environment on import
if os.getenv("GEMINI_API_KEY"):
    os.environ.setdefault("USE_STEALTH_STACK_CAPTCHA", "true")
if os.getenv("CLOAKBROWSER_LICENSE") or os.getenv("USE_CLOAKBROWSER") == "true":
    os.environ.setdefault("USE_CLOAKBROWSER", "true")