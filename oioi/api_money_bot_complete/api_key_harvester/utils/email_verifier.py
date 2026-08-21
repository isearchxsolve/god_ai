#!/usr/bin/env python3
"""
Gmail Email Verification Automation
====================================
Uses IMAP to read verification emails and extract codes/links.
Requires Gmail App Password (not main password) with IMAP enabled.
"""

import os
import re
import imaplib
import email
import time
import requests
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from email.header import decode_header


class IMAPVerifier:
    """Automated email verification code/link extractor (Gmail + ProtonMail)."""

    def __init__(self, email_addr: str = None, password: str = None, imap_server: str = None):
        self.email_addr = email_addr or os.getenv("GMAIL_EMAIL") or os.getenv("EMAIL_ADDR")
        self.password = password or os.getenv("GMAIL_APP_PASSWORD") or os.getenv("EMAIL_PASSWORD")

        # Auto-detect server from email domain if not specified
        if imap_server:
            self.imap_server = imap_server
        elif self.email_addr and "protonmail" in self.email_addr:
            self.imap_server = "imap.protonmail.ch"
        else:
            self.imap_server = os.getenv("IMAP_SERVER", "imap.gmail.com")

        self.imap_port = int(os.getenv("IMAP_PORT", 993))
        self.connection = None

    def connect(self) -> bool:
        """Establish IMAP connection."""
        if not self.email_addr or not self.password:
            print("[IMAP] Email or password not set")
            return False

        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.email_addr, self.password)
            self.connection.select("INBOX")
            print(f"[IMAP] Connected to {self.email_addr} via {self.imap_server}")
            return True
        except Exception as e:
            print(f"[IMAP] Connection failed: {e}")
            return False

    def disconnect(self):
        """Close IMAP connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except Exception:
                pass
            self.connection = None
    
    def _build_or_chain(self, keyword: str, values: List[str]) -> str:
        """Build proper IMAP prefix-OR chain: OR FROM 'a' FROM 'b' FROM 'c'."""
        if not values:
            return ""
        if len(values) == 1:
            return f'{keyword} "{values[0]}"'
        result = f'{keyword} "{values[-1]}"'
        for val in reversed(values[:-1]):
            result = f'OR {keyword} "{val}" {result}'
        return result

    def search_verification_email(
        self,
        sender_keywords: List[str] = None,
        subject_keywords: List[str] = None,
        since_minutes: int = 10,
        max_results: int = 5
    ) -> List[Dict]:
        """
        Search for verification emails.

        Args:
            sender_keywords: List of sender domains/emails to match
            subject_keywords: List of subject keywords
            since_minutes: Only search emails from last N minutes
            max_results: Maximum emails to return
        """
        if not self.connection and not self.connect():
            return []

        # Build search criteria using prefix OR
        criteria = []

        # Time filter
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        dt = datetime.now() - timedelta(minutes=since_minutes)
        since_date = f"{dt.day:02d}-{months[dt.month - 1]}-{dt.year}"
        criteria.append(f'SINCE "{since_date}"')

        # Sender filter (prefix OR chain)
        if sender_keywords:
            sender_part = self._build_or_chain("FROM", sender_keywords)
            if sender_part:
                criteria.append(sender_part)

        # Subject filter (prefix OR chain)
        if subject_keywords:
            subject_part = self._build_or_chain("SUBJECT", subject_keywords)
            if subject_part:
                criteria.append(subject_part)

        search_criteria = " ".join(criteria)
        
        try:
            status, messages = self.connection.search(None, search_criteria)
            if status != "OK":
                return []
            
            email_ids = messages[0].split()
            if not email_ids:
                return []
            
            # Get latest emails first
            email_ids = email_ids[-max_results:][::-1]
            
            results = []
            for eid in email_ids:
                email_data = self._fetch_email(eid)
                if email_data:
                    results.append(email_data)
            
            return results
            
        except Exception as e:
            print(f"[IMAPVerifier] Search error: {e}")
            return []
    
    def _fetch_email(self, email_id: bytes) -> Optional[Dict]:
        """Fetch and parse a single email."""
        try:
            status, msg_data = self.connection.fetch(email_id, "(RFC822)")
            if status != "OK":
                return None
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            # Decode subject
            subject = ""
            if msg["Subject"]:
                decoded = decode_header(msg["Subject"])[0]
                subject = decoded[0].decode(decoded[1] or "utf-8") if isinstance(decoded[0], bytes) else decoded[0]
            
            # Get sender
            sender = msg.get("From", "")
            
            # Get body
            body = self._get_email_body(msg)
            
            return {
                "id": email_id.decode(),
                "subject": subject,
                "sender": sender,
                "body": body,
                "date": msg.get("Date", "")
            }
            
        except Exception as e:
            print(f"[IMAPVerifier] Fetch error: {e}")
            return None
    
    def _get_email_body(self, msg) -> str:
        """Extract text body from email (handles multipart)."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body = part.get_payload(decode=True).decode(charset)
                        break
                    except Exception:
                        continue
                elif content_type == "text/html" and "attachment" not in content_disposition and not body:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        body = part.get_payload(decode=True).decode(charset)
                    except Exception:
                        continue
        else:
            charset = msg.get_content_charset() or "utf-8"
            try:
                body = msg.get_payload(decode=True).decode(charset)
            except Exception:
                pass
        
        return body
    
    def extract_verification_code(self, body: str, patterns: List[str] = None) -> Optional[str]:
        """Extract verification code from email body."""
        default_patterns = [
            r'\b(\d{6})\b',                    # 6-digit code
            r'\b(\d{4,8})\b',                  # 4-8 digit code
            r'code[:\s]+(\d{4,8})',            # "code: 123456"
            r'verification code[:\s]+(\d{4,8})', # "verification code: 123456"
        ]
        
        search_patterns = patterns or default_patterns
        
        for pattern in search_patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                # Return the longest match (more likely to be the code)
                return max(matches, key=len)
        
        return None
    
    def extract_verification_link(self, body: str, domain_keywords: List[str] = None) -> Optional[str]:
        """Extract verification link from email body."""
        # Find all URLs
        url_pattern = r'https?://[^\s<>"]+'
        urls = re.findall(url_pattern, body)
        
        if domain_keywords:
            # Filter by domain
            for url in urls:
                for kw in domain_keywords:
                    if kw in url:
                        return url
        else:
            # Return first URL that looks like verification
            for url in urls:
                if any(kw in url.lower() for kw in ["verify", "confirm", "activate", "auth", "token", "code"]):
                    return url
        
        return urls[0] if urls else None
    
    def wait_for_verification(
        self,
        sender_keywords: List[str],
        subject_keywords: List[str] = None,
        timeout_seconds: int = 120,
        poll_interval: int = 10
    ) -> Optional[Dict]:
        """
        Wait for verification email and extract code/link.
        
        Returns:
            Dict with 'code' and/or 'link' if found, None otherwise
        """
        print(f"[IMAPVerifier] Waiting for verification email (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        subject_kw = subject_keywords or ["verify", "confirm", "code", "activate", "welcome"]
        
        while time.time() - start_time < timeout_seconds:
            emails = self.search_verification_email(
                sender_keywords=sender_keywords,
                subject_keywords=subject_kw,
                since_minutes=5,
                max_results=3
            )
            
            for email_data in emails:
                body = email_data["body"]
                
                # Try to extract code
                code = self.extract_verification_code(body)
                link = self.extract_verification_link(body, sender_keywords)
                
                if code or link:
                    print(f"[IMAPVerifier] Found verification - Code: {code}, Link: {link}")
                    return {"code": code, "link": link, "email": email_data}
            
            elapsed = int(time.time() - start_time)
            print(f"[IMAPVerifier] Waiting... ({elapsed}s elapsed)")
            time.sleep(poll_interval)
        
        print(f"[IMAPVerifier] Timeout - no verification email found")
        return None


class TempMailVerifier:
    """Disposable email verifier using Mail.tm API — no account needed."""

    API_BASE = "https://api.mail.tm"
    SENDER_MAP = {
        "binance": ["binance.com", "mail.binance.com", "noreply@binance.com"],
        "coinbase": ["coinbase.com", "mail.coinbase.com", "no-reply@coinbase.com"],
        "bybit": ["bybit.com", "mail.bybit.com", "noreply@bybit.com"],
        "kucoin": ["kucoin.com", "mail.kucoin.com", "noreply@kucoin.com"],
        "okx": ["okx.com", "mail.okx.com", "noreply@okx.com"],
        "github": ["github.com", "noreply@github.com"],
        "upwork": ["upwork.com", "mail.upwork.com"],
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.email = None
        self.password = None
        self.token = None
        self.account_id = None

    def create_inbox(self) -> str:
        """Create a disposable inbox. Returns email address."""
        import random
        import string
        domains_resp = self.session.get(f"{self.API_BASE}/domains").json()
        if isinstance(domains_resp, dict):
            domains_list = domains_resp.get("hydra:member", [])
        else:
            domains_list = domains_resp or []
        if not domains_list:
            raise Exception("No mail.tm domains available")
        domain = domains_list[0]["domain"]
        rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
        self.email = f"moneybot_{rand}@{domain}"
        self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        resp = self.session.post(f"{self.API_BASE}/accounts", json={
            "address": self.email,
            "password": self.password
        })
        if resp.status_code not in (200, 201):
            raise Exception(f"Failed to create inbox: {resp.status_code} {resp.text}")
        self.account_id = resp.json().get("id")
        token_resp = self.session.post(f"{self.API_BASE}/token", json={
            "address": self.email,
            "password": self.password
        })
        self.token = token_resp.json().get("token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        print(f"[TempMail] Created inbox: {self.email}")
        return self.email

    def check_messages(self) -> List[Dict]:
        """Fetch all messages in inbox."""
        if not self.token:
            return []
        try:
            resp = self.session.get(f"{self.API_BASE}/messages", timeout=10)
            if resp.status_code != 200:
                return []
            msgs = resp.json().get("hydra:member", [])
            results = []
            for msg in msgs:
                msg_id = msg["id"]
                detail = self.session.get(f"{self.API_BASE}/messages/{msg_id}", timeout=10).json()
                html = detail.get("html", "") or []
                body = "\n".join(html) if isinstance(html, list) else str(html)
                results.append({
                    "id": msg_id,
                    "subject": detail.get("subject", ""),
                    "sender": detail.get("from", {}).get("address", ""),
                    "body": body,
                    "date": detail.get("createdAt", ""),
                })
            return results
        except Exception as e:
            print(f"[TempMail] Check error: {e}")
            return []

    def extract_verification_code(self, body: str) -> Optional[str]:
        patterns = [
            r'(?:code|verification|otp|pin)[\s#:=]+(\d{6})',
            r'\b(\d{6})\b',
            r'\b(\d{4,8})\b',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                for m in matches:
                    if len(str(m)) == 6:
                        return str(m)
                return str(matches[0])
        return None

    def wait_for_code(self, platform: str, timeout: int = 120) -> Optional[Dict]:
        """Poll for verification email and extract code."""
        print(f"[TempMail] Waiting for {platform} verification email (timeout {timeout}s)...")
        sender_kw = self.SENDER_MAP.get(platform.lower(), [platform.lower()])
        deadline = time.time() + timeout
        while time.time() < deadline:
            msgs = self.check_messages()
            for msg in msgs:
                sender = msg.get("sender", "").lower()
                if any(kw in sender for kw in sender_kw):
                    code = self.extract_verification_code(msg["body"])
                    if code:
                        print(f"[TempMail] Found code: {code}")
                        return {"code": code, "email_data": msg}
            time.sleep(5)
        print(f"[TempMail] Timeout - no verification email")
        return None

    def cleanup(self):
        """Delete the disposable inbox."""
        if self.account_id:
            try:
                self.session.delete(f"{self.API_BASE}/accounts/{self.account_id}")
            except Exception:
                pass


class GmailAliasVerifier:
    """
    Verify emails sent to a Gmail plus-alias (user+tag@gmail.com) via IMAP.
    Uses GMAIL_EMAIL / GMAIL_APP_PASSWORD from .env for IMAP auth.
    """

    def __init__(self, alias_email: str):
        self.alias = alias_email
        # Extract base (pre-+) local part for IMAP login
        self.base_email = os.getenv("GMAIL_EMAIL")
        self.app_password = os.getenv("GMAIL_APP_PASSWORD")
        self._connection = None

    def _connect(self) -> bool:
        if not self.base_email or not self.app_password:
            print("[GmailAlias] GMAIL_EMAIL or GMAIL_APP_PASSWORD not set")
            return False
        try:
            self._connection = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            self._connection.login(self.base_email, self.app_password)
            self._connection.select("INBOX")
            return True
        except Exception as e:
            print(f"[GmailAlias] IMAP connect failed: {e}")
            return False

    def _disconnect(self):
        if self._connection:
            try:
                self._connection.close()
                self._connection.logout()
            except Exception:
                pass

    def extract_verification_code(self, body: str) -> Optional[str]:
        patterns = [
            r'(?:code|verification|otp|pin)[\s#:=]+(\d{6})',
            r'\b(\d{6})\b',
            r'\b(\d{4,8})\b',
        ]
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            if matches:
                for m in matches:
                    if len(str(m)) == 6:
                        return str(m)
                return str(matches[0])
        return None

    def wait_for_code(self, platform: str, timeout: int = 180) -> Optional[Dict]:
        """
        Poll Gmail inbox for an email addressed to the alias To: header.
        Returns dict with 'code' if found.
        """
        print(f"[GmailAlias] Waiting for {platform} email to {self.alias}...")
        if not self._connect():
            return None
        try:
            # Search by To: header matching the alias local part
            local_part = self.alias.split("@")[0]
            # Gmail stores the full address (with +tag) in To header
            search_criteria = f'(TO "{local_part}@gmail.com")'
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    status, ids = self._connection.search(None, search_criteria)
                    if status == "OK":
                        for msg_id in ids[0].split() if ids[0] else []:
                            status, data = self._connection.fetch(msg_id, "(RFC822)")
                            if status != "OK":
                                continue
                            raw = data[0][1] if isinstance(data[0], tuple) else data[0]
                            msg = email.message_from_bytes(raw)
                            body = ""
                            if msg.is_multipart():
                                for part in msg.walk():
                                    if part.get_content_type() == "text/plain":
                                        body = part.get_payload(decode=True).decode(errors="replace")
                                        break
                            else:
                                body = msg.get_payload(decode=True).decode(errors="replace")
                            sender = msg.get("From", "").lower()
                            if platform.lower() in sender:
                                code = self.extract_verification_code(body)
                                # Also extract verification links
                                link = None
                                link_match = re.search(r'https?://[^\s"\']*(?:verify|confirm|activate)[^\s"\']*', body, re.I)
                                if link_match:
                                    link = link_match.group(0)
                                result = {"code": code, "email_data": {"subject": msg.get("Subject",""), "from": sender, "body": body[:2000]}}
                                if link:
                                    result["link"] = link
                                if code or link:
                                    print(f"[GmailAlias] Found {'code: ' + code if code else ''}{' and ' if code and link else ''}{'link' if link else ''}")
                                    return result
                except Exception:
                    pass
                time.sleep(5)
            print(f"[GmailAlias] Timeout — no email found")
            return None
        finally:
            self._disconnect()


# Convenience function
def wait_for_email_verification(
    platform: str,
    email_addr: str = None,
    password: str = None,
    imap_server: str = None,
    timeout: int = 120
) -> Optional[Dict]:
    """
    Wait for verification email. Tries Gmail/IMAP first, then falls back to Mail.tm.
    """
    sender_map = {
        "binance": ["binance.com", "mail.binance.com", "noreply@binance.com"],
        "coinbase": ["coinbase.com", "mail.coinbase.com", "no-reply@coinbase.com"],
        "bybit": ["bybit.com", "mail.bybit.com", "noreply@bybit.com"],
        "kucoin": ["kucoin.com", "mail.kucoin.com", "noreply@kucoin.com"],
        "okx": ["okx.com", "mail.okx.com", "noreply@okx.com"],
        "github": ["github.com", "noreply@github.com"],
        "upwork": ["upwork.com", "mail.upwork.com"],
        "gumroad": ["gumroad.com", "mail.gumroad.com"],
        "stripe": ["stripe.com", "mail.stripe.com"],
        "openai": ["openai.com", "mail.openai.com"],
        "shutterstock": ["shutterstock.com", "mail.shutterstock.com"],
        "adobestock": ["adobe.com", "mail.adobe.com"],
        "pond5": ["pond5.com", "mail.pond5.com"],
        "etsy": ["etsy.com", "mail.etsy.com"],
        "ebay": ["ebay.com", "mail.ebay.com"],
        "shopify": ["shopify.com", "mail.shopify.com"],
        "printful": ["printful.com", "mail.printful.com"],
        "printify": ["printify.com", "mail.printify.com"],
        "medium": ["medium.com", "mail.medium.com"],
        "patreon": ["patreon.com", "mail.patreon.com"],
        "substack": ["substack.com", "mail.substack.com"],
        "reddit": ["reddit.com", "mail.reddit.com"],
        "twitter": ["twitter.com", "x.com", "mail.twitter.com"],
        "anthropic": ["anthropic.com", "mail.anthropic.com"],
        "replicate": ["replicate.com", "mail.replicate.com"],
        "rapidapi": ["rapidapi.com", "mail.rapidapi.com"],
        "razorpay": ["razorpay.com", "mail.razorpay.com"],
        "wise": ["wise.com", "mail.wise.com", "transferwise.com"],
        "paypal": ["paypal.com", "mail.paypal.com"],
        "toloka": ["toloka.yandex.com", "yandex.com"],
        "clickworker": ["clickworker.com", "mail.clickworker.com"],
        "remotasks": ["remotasks.com", "mail.remotasks.com"],
    }
    sender_keywords = sender_map.get(platform.lower(), [platform.lower()])

    # Try IMAP if configured
    gmail = os.getenv("GMAIL_EMAIL", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    if gmail and gmail_pass and gmail != "your_email@gmail.com":
        verifier = IMAPVerifier(email_addr, password, imap_server)
        try:
            result = verifier.wait_for_verification(
                sender_keywords=sender_keywords, timeout_seconds=timeout
            )
            if result:
                return result
        finally:
            verifier.disconnect()

    # Fallback to Mail.tm
    print("[TempMail] IMAP not configured; using disposable inbox")
    tm = TempMailVerifier()
    return tm.wait_for_code(platform, timeout=timeout)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = wait_for_email_verification(sys.argv[1])
        print(f"Result: {result}")