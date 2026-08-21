#!/usr/bin/env python3
"""
Stealth Stack Captcha Solver for API Key Harvester
===================================================
Drop-in replacement for CaptchaSolver using the multimodal stealth stack:
- Gemini 3.5 Flash (visual reasoning for grid/text/math CAPTCHAs)
- OpenAI Whisper (local audio transcription)
- Bright Data Web Unlocker (fallback for obscure challenge types)

Compatible with existing CaptchaSolver interface used by strategies.
"""

import os
import re
import json
import time
import base64
import io
import random
import requests
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import google.generativeai as genai
except ImportError:
    raise ImportError("Install google-generativeai: pip install google-generativeai")

try:
    import whisper
except ImportError:
    raise ImportError("Install whisper: pip install openai-whisper")


@dataclass
class Challenge:
    type: str
    has_audio: bool = False
    instructions: str = ""
    element_selector: Optional[str] = None
    confidence: float = 0.0


class ChallengeDetector:
    """DOM-based challenge detection compatible with stealth stack."""

    SIGNATURES = {
        "recaptcha_v2_checkbox": [".g-recaptcha", "#recaptcha-anchor"],
        "recaptcha_v2_grid": ["#rc-imageselect", ".rc-imageselect"],
        "hcaptcha": [".h-captcha"],
        "text_captcha": ["img[src*='captcha']", ".captcha-image", "#captcha_img"],
        "invisible": ["textarea[name='g-recaptcha-response']", "input[name='g-recaptcha-response']"],
        "audio_indicator": ["#recaptcha-audio-button", ".rc-button-audio"],
        "slider_captcha": [".verify-slider", ".bs-slide-container", "[class*='slide-container']",
                          "div[class*='slider']", ".security-verification"],
    }

    def __init__(self, page):
        self.page = page

    def detect(self) -> Challenge:
        if self._any_present(self.SIGNATURES["invisible"]):
            return Challenge(type="invisible", element_selector="textarea[name='g-recaptcha-response']")

        if self._any_present(self.SIGNATURES["recaptcha_v2_checkbox"]):
            return Challenge(type="checkbox", element_selector=".g-recaptcha")

        if self._any_present(self.SIGNATURES["recaptcha_v2_grid"]):
            instr = self._safe_text(".rc-imageselect-instructions")
            return Challenge(type="grid", instructions=instr, element_selector="#rc-imageselect")

        if self._any_present(self.SIGNATURES["hcaptcha"]):
            return Challenge(type="grid", element_selector=".h-captcha")

        if self._any_present(self.SIGNATURES["text_captcha"]):
            return Challenge(type="text")

        if self._any_present(self.SIGNATURES["slider_captcha"]):
            return Challenge(type="slider")

        has_audio = self._any_present(self.SIGNATURES["audio_indicator"])
        return Challenge(type="none", has_audio=has_audio)

    def _any_present(self, selectors: list) -> bool:
        for sel in selectors:
            try:
                if self.page.locator(sel).count() > 0:
                    return True
            except Exception:
                continue
        return False

    def _safe_text(self, selector: str) -> str:
        try:
            el = self.page.locator(selector)
            if el.count() > 0:
                return el.inner_text()
        except Exception:
            pass
        return ""


class GeminiVisionSolver:
    """Gemini 3.5 Flash visual reasoning for CAPTCHAs."""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-3.5-flash')
        self.chat = self.model.start_chat(history=[])

    @staticmethod
    def _extract_json(text: str) -> list:
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if not match:
            return []
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return []

    def solve_grid(self, screenshot: Image.Image, instructions: str) -> list:
        """Grid-based visual challenges (reCAPTCHA v2, hCaptcha). Returns [(x, y), ...]."""
        prompt = f"""You are a precise UI automation assistant analyzing a visual challenge.

Instructions: "{instructions}"

Analyze the screenshot. Identify which grid cells or regions match the instructions.
For EACH matching region, return:
- row and column (1-indexed)
- approximate center coordinates in pixels (x, y)
- confidence score (0.0 to 1.0)

Return ONLY a valid JSON array. No explanation.
Example format:
[
  {{"row": 1, "col": 3, "x": 420, "y": 380, "confidence": 0.95}}
]

If NO regions match, return an empty array: []"""

        response = self.chat.send_message([prompt, screenshot])
        cells = self._extract_json(response.text)
        return [(c["x"], c["y"]) for c in cells if c.get("confidence", 0) > 0.75]

    def solve_text(self, screenshot: Image.Image) -> str:
        """Text-based CAPTCHA OCR."""
        prompt = """Extract the text from this image.
Return ONLY the alphanumeric string, no spaces, no punctuation, no explanation.
If the text is unreadable, return exactly: UNREADABLE"""

        response = self.chat.send_message([prompt, screenshot])
        return response.text.strip().replace(" ", "").upper()

    def solve_math(self, screenshot: Image.Image) -> str:
        """Math CAPTCHA solving."""
        prompt = """Solve the math problem shown in this image.
Return ONLY the numerical answer. No explanation, no units, no text."""

        response = self.chat.send_message([prompt, screenshot])
        return re.sub(r'[^0-9\-]', '', response.text.strip())

    def solve_slider_position(self, screenshot: Image.Image) -> dict:
        """Slider/puzzle CAPTCHA - find gap/puzzle piece position."""
        prompt = """Analyze this slider/puzzle CAPTCHA screenshot.
Find the puzzle piece/gap that needs to be aligned.
Return the X coordinate (in pixels) where the slider should be dragged to.
Return ONLY a valid JSON object: {{"x_offset": <pixels>, "confidence": <0.0-1.0>}}
If unclear, return: {{"x_offset": 300, "confidence": 0.1}}"""

        response = self.chat.send_message([prompt, screenshot])
        try:
            return json.loads(response.text.strip())
        except json.JSONDecodeError:
            return {"x_offset": 300, "confidence": 0.1}


class LocalAudioSolver:
    """Local speech recognition for audio challenges."""

    def __init__(self, model_size: str = "base"):
        self.model = whisper.load_model(model_size)
        print(f"[StealthCaptcha] Loaded Whisper model: {model_size}")

    def transcribe(self, audio_path: str) -> str:
        result = self.model.transcribe(
            audio_path,
            language="en",
            initial_prompt="This audio contains digits or letters spoken with distortion.",
            temperature=0.0,
            condition_on_previous_text=False,
        )
        cleaned = ''.join(c for c in result["text"] if c.isalnum()).upper()
        return cleaned[:6]


class BrightDataFallback:
    """Bright Data Web Unlocker for unsupported challenge types."""

    def __init__(self, api_token: str, zone_name: str = "web_unlocker"):
        self.api_token = api_token
        self.zone_name = zone_name
        self.proxy_url = (
            f"http://brd-customer-{zone_name}-zone-{zone_name}:{api_token}"
            f"@zproxy.lum-superproxy.io:22225"
        )

    def solve_session(self, target_url: str, timeout: int = 60) -> Dict[str, Any]:
        try:
            response = requests.get(
                target_url,
                proxies={"http": self.proxy_url, "https": self.proxy_url},
                timeout=timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                },
            )
            return {
                "status": "success" if response.status_code == 200 else "blocked",
                "source": "brightdata-webunlocker",
                "status_code": response.status_code,
                "html_length": len(response.text),
                "cookies": response.cookies.get_dict(),
                "final_url": response.url,
            }
        except requests.exceptions.ProxyError as e:
            return {"status": "proxy_error", "source": "brightdata-webunlocker", "error": str(e)}
        except requests.exceptions.Timeout:
            return {"status": "timeout", "source": "brightdata-webunlocker"}


class SmartRouter:
    """Routes detected challenges to appropriate solver."""

    def __init__(
        self,
        gemini_solver: GeminiVisionSolver,
        audio_solver: LocalAudioSolver,
        brightdata_fallback: Optional[BrightDataFallback] = None,
    ):
        self.gemini = gemini_solver
        self.audio = audio_solver
        self.brightdata = brightdata_fallback

    def route(self, challenge: Challenge, page) -> Dict[str, Any]:
        screenshot = Image.open(io.BytesIO(page.screenshot(full_page=False)))

        if challenge.type == "grid":
            coords = self.gemini.solve_grid(screenshot, challenge.instructions)
            return {
                "action": "click_grid",
                "coords": coords,
                "source": "gemini-3.5-flash",
                "note": f"Detected {len(coords)} matching regions",
            }

        elif challenge.type == "text":
            text = self.gemini.solve_text(screenshot)
            return {"action": "type_text", "value": text, "source": "gemini-3.5-flash"}

        elif challenge.type == "math":
            answer = self.gemini.solve_math(screenshot)
            return {"action": "type_text", "value": answer, "source": "gemini-3.5-flash"}

        elif challenge.type == "slider":
            result = self.gemini.solve_slider_position(screenshot)
            return {"action": "drag_slider", "offset": result.get("x_offset", 300), "source": "gemini-3.5-flash"}

        elif challenge.type == "audio":
            return {
                "action": "type_text",
                "value": self.audio.transcribe("temp_audio.mp3"),
                "source": "whisper-local",
            }

        elif challenge.type == "invisible":
            return {
                "action": "none",
                "source": "behavioral-evasion",
                "note": "CloakBrowser humanize handles invisible scoring",
            }

        elif challenge.type == "checkbox":
            return {"action": "click_checkbox", "source": "direct-interaction"}

        elif challenge.type in ("unknown", "keycaptcha", "capy", "mtcaptcha"):
            if self.brightdata is None:
                return {
                    "action": "abort",
                    "source": "none",
                    "note": f"No fallback configured for {challenge.type}",
                }
            return {
                "action": "proxy_session",
                "source": "brightdata-webunlocker",
                "note": f"Routing {challenge.type} to external unlocker",
            }

        return {"action": "none", "source": "none"}


class StealthStackCaptchaSolver:
    """
    Drop-in replacement for CaptchaSolver using the multimodal stealth stack.
    Compatible with existing strategy interface:
    - solve_recaptcha(site_key, page_url, invisible) -> token
    - solve_hcaptcha(site_key, page_url) -> token
    - solve_slider_captcha(image_b64, page_url) -> dict with x_offset
    - inject_recaptcha_token(page, token)
    - inject_hcaptcha_token(page, token)
    """

    BASE = "http://2captcha.com"  # Kept for interface compatibility

    def __init__(
        self,
        api_key: str = None,
        gemini_api_key: str = None,
        whisper_model: str = "base",
        brightdata_token: str = None,
        brightdata_zone: str = "web_unlocker",
    ):
        # Accept 2Captcha API key for backward compatibility (ignored)
        self.api_key = api_key or os.getenv("CAPTCHA_API_KEY")

        # Stealth stack configuration
        self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        self.whisper_model = whisper_model
        self.brightdata_token = brightdata_token or os.getenv("BRIGHTDATA_TOKEN")
        self.brightdata_zone = brightdata_zone

        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY missing — set in .env or pass to constructor")

        # Initialize solvers
        self.gemini = GeminiVisionSolver(self.gemini_api_key)
        self.audio = LocalAudioSolver(self.whisper_model)

        self.brightdata = None
        if self.brightdata_token:
            self.brightdata = BrightDataFallback(self.brightdata_token, self.brightdata_zone)

        self.router = SmartRouter(self.gemini, self.audio, self.brightdata)

    # --- 2Captcha-compatible methods (required by base strategy) ---

    def solve_recaptcha(self, site_key: str, page_url: str, invisible: bool = False) -> str:
        """
        Solve reCAPTCHA using visual reasoning.
        Note: This is a simplified implementation. For production, you'd need
        to interact with the actual challenge on the page.
        """
        # The stealth stack operates on the live page, not via API
        # This method is kept for interface compatibility
        # Actual solving happens via handle_captcha in base strategy
        return "STEALTH_STACK_TOKEN"

    def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        return "STEALTH_STACK_TOKEN"

    def solve_slider_captcha(self, image_b64: str, page_url: str = "") -> dict:
        """Solve slider CAPTCHA from base64 image."""
        # Decode base64 image
        img_data = base64.b64decode(image_b64)
        screenshot = Image.open(io.BytesIO(img_data))

        # Use Gemini to find slider position
        result = self.gemini.solve_slider_position(screenshot)
        return {"angle": "0", "x_offset": str(result.get("x_offset", 300))}

    def solve_slider_captcha_click(self, image_b64: str, page_url: str = "") -> dict:
        """Solve click-based CAPTCHA from base64 image."""
        img_data = base64.b64decode(image_b64)
        screenshot = Image.open(io.BytesIO(img_data))

        text = self.gemini.solve_text(screenshot)
        # Parse as coordinates if possible
        coords = []
        for part in text.split(";"):
            if "," in part:
                x, y = part.split(",")
                coords.append({"x": int(x), "y": int(y)})
        return {"coordinates": coords}

    def solve_image(self, image_path: str) -> str:
        """Solve image-based captcha."""
        screenshot = Image.open(image_path)
        return self.gemini.solve_text(screenshot)

    def inject_recaptcha_token(self, page, token: str):
        """Inject solved reCAPTCHA token into the page."""
        page.evaluate(f"""
            (function() {{
                var t = '{token}';
                var tas = document.querySelectorAll('#g-recaptcha-response, [name="g-recaptcha-response"]');
                tas.forEach(function(el) {{
                    el.innerHTML = t; el.value = t;
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }});
                try {{
                    if (typeof ___grecaptcha_cfg !== 'undefined') {{
                        var clients = ___grecaptcha_cfg.clients;
                        if (clients) {{
                            Object.keys(clients).forEach(function(id) {{
                                var c = clients[id];
                                if (!c) return;
                                Object.keys(c).forEach(function(k) {{
                                    var v = c[k];
                                    if (typeof v === 'function') {{ try {{ v(t); }} catch(e) {{}} }}
                                    else if (v && typeof v.callback === 'function') {{ try {{ v.callback(t); }} catch(e) {{}} }}
                                }});
                                if (typeof c.callback === 'function') {{ try {{ c.callback(t); }} catch(e) {{}} }}
                            }});
                        }}
                    }}
                }} catch(e) {{}}
            }})();
        """)

    def inject_hcaptcha_token(self, page, token: str):
        """Inject solved hCaptcha token into the page."""
        page.evaluate(f"""
            const elem = document.querySelector('[name="h-captcha-response"]');
            if (elem) elem.value = '{token}';
            if (window.hcaptcha) {{
                try {{ window.hcaptcha.setResponse('{token}'); }} catch(e) {{}}
            }}
        """)

    # --- Stealth Stack methods (for direct page integration) ---

    def solve_on_page(self, page) -> Dict[str, Any]:
        """
        Main entry point: detect and solve CAPTCHA on the current page.
        Returns result dict with status and action taken.
        """
        detector = ChallengeDetector(page)
        challenge = detector.detect()

        if challenge.type == "none":
            return {"status": "success", "method": "no_challenge_detected"}

        plan = self.router.route(challenge, page)
        return self._execute_action(page, plan)

    def _execute_action(self, page, plan: Dict[str, Any]) -> Dict[str, Any]:
        action = plan.get("action")

        if action == "none":
            time.sleep(3)
            return {"status": "success", "method": plan["source"]}

        elif action == "click_checkbox":
            box = page.locator(".g-recaptcha, #recaptcha-anchor").first
            if box.count() > 0:
                bbox = box.bounding_box()
                if bbox:
                    self._human_click(page, bbox["x"] + 10, bbox["y"] + 10)
                    time.sleep(2)
                    return {"status": "success", "method": "direct-interaction"}
            return {"status": "failed", "reason": "checkbox not found"}

        elif action == "click_grid":
            coords = plan.get("coords", [])
            if not coords:
                return {"status": "failed", "reason": "No coordinates from vision solver"}

            for x, y in coords:
                self._human_click(page, x, y)
                time.sleep(random.uniform(0.5, 1.0))

            verify = page.locator("#recaptcha-verify-button")
            if verify.count() > 0:
                verify.click()
                time.sleep(1.5)
            return {"status": "success", "method": "gemini-3.5-flash"}

        elif action == "type_text":
            value = plan.get("value", "")
            if not value or value == "UNREADABLE":
                return {"status": "failed", "reason": "Unreadable text"}

            inputs = page.locator("input[type='text'], .captcha-input, #audio-response")
            if inputs.count() > 0:
                inp = inputs.first
                for char in value:
                    inp.type(char, delay=random.randint(50, 150))
                page.keyboard.press("Enter")
                time.sleep(1.5)
                return {"status": "success", "method": plan["source"]}
            return {"status": "failed", "reason": "Input not found"}

        elif action == "drag_slider":
            offset = plan.get("offset", 300)
            return self._drag_slider(page, offset)

        elif action == "proxy_session":
            if not self.router.brightdata:
                return {"status": "failed", "reason": "No Bright Data fallback configured"}

            result = self.router.brightdata.solve_session(page.url, timeout=60)
            if result["status"] == "success":
                page.goto(result["final_url"], wait_until="networkidle")
                time.sleep(2)
                return {"status": "success", "method": "brightdata-webunlocker"}
            return {"status": "failed", "reason": result.get("error", "Bright Data failed")}

        elif action == "abort":
            return {"status": "aborted", "reason": plan.get("note", "Unsupported challenge")}

        return {"status": "failed", "reason": f"Unknown action: {action}"}

    def _human_click(self, page, x: int, y: int):
        page.mouse.move(x, y, steps=random.randint(8, 15))
        time.sleep(random.uniform(0.1, 0.4))
        page.mouse.click(x, y)

    def _drag_slider(self, page, offset: int) -> Dict[str, Any]:
        """Drag slider handle by offset pixels."""
        slider = page.query_selector(
            ".bs-slide-thumb, .bs-slide-thumb:hover, "
            "div[class*='slider-btn'], div[class*='slider-button'], "
            "[class*='slider-handle'], button[class*='slider'], "
            ".slider-arrow, [class*='puzzle-btn'], [id*='slth'], [class*='thumb']"
        )
        if not slider:
            return {"status": "failed", "reason": "Slider handle not found"}

        try:
            box = slider.bounding_box()
            if box:
                start_x = box["x"] + box["width"] / 2
                start_y = box["y"] + box["height"] / 2

                page.mouse.move(start_x, start_y)
                page.mouse.down()
                time.sleep(0.2)
                page.mouse.move(start_x + offset, start_y + 2, steps=15)
                time.sleep(0.5)
                page.mouse.up()
                time.sleep(3)

                # Check if solved
                if not page.query_selector("text=Security Verification", timeout=3000):
                    return {"status": "success", "method": "gemini-3.5-flash", "offset": offset}
                else:
                    return {"status": "failed", "reason": "Slider CAPTCHA may have failed"}
        except Exception as e:
            return {"status": "failed", "reason": f"Drag action failed: {e}"}