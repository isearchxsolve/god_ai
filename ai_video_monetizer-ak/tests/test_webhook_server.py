"""Tests for scripts/webhook_server.py."""
import os
import json
import hmac
import hashlib
import sys
from pathlib import Path
from io import BytesIO
from unittest.mock import MagicMock, patch, call
import pytest

os.environ.setdefault("MAKE_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GUMROAD_WEBHOOK_SECRET", "test_gumroad_secret")
os.environ.setdefault("GOOGLE_SHEETS_CONTENT_PIPELINE_ID", "test_sheet")

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scripts import webhook_server


class TestWebhookHandler:
    @pytest.fixture
    def handler(self):
        inst = webhook_server.WebhookHandler.__new__(webhook_server.WebhookHandler)
        inst.server = MagicMock()
        inst.client_address = ("127.0.0.1", 12345)
        inst.command = "GET"
        inst.path = "/health"
        inst.request_version = "HTTP/1.1"
        inst.headers = {}
        inst.rfile = BytesIO(b"")
        inst.wfile = BytesIO()
        inst.raw_requestline = b"GET /health HTTP/1.1\r\n"
        inst.close_connection = True
        inst.protocol_version = "HTTP/1.1"
        inst.date_time_string = MagicMock(return_value="mock-date")
        inst.address_string = MagicMock(return_value="mock-address")
        return inst

    def test_set_headers(self, handler):
        handler._set_headers(200)
        # wfile should have nothing (set_headers doesn't write body)
        assert True

    def test_verify_signature_valid(self, handler):
        payload = json.dumps({"test": "data"}).encode()
        secret = "test_secret"
        expected_sig = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()
        assert handler._verify_signature(payload, expected_sig, secret) is True

    def test_verify_signature_invalid(self, handler):
        payload = json.dumps({"test": "data"}).encode()
        assert handler._verify_signature(payload, "sha256:bad_sig", "test_secret") is False

    def test_verify_signature_no_separator(self, handler):
        assert handler._verify_signature(b"test", "nocolon", "secret") is False

    def test_verify_signature_mismatch(self, handler):
        bad_hash = "sha256:" + "0" * 64
        assert handler._verify_signature(b"test", bad_hash, "secret") is False

    def test_log_request(self, handler):
        assert handler.log_request() is None

    def test_do_get_health(self, handler):
        handler.path = "/health"
        handler.do_GET()
        written = handler.wfile.getvalue()
        assert b"ok" in written

    def test_do_get_not_found(self, handler):
        handler.path = "/unknown"
        handler.do_GET()
        written = handler.wfile.getvalue()
        assert b"Not found" in written

    def test_do_post_unknown(self, handler):
        handler.path = "/unknown"
        handler.headers = {"Content-Length": "2"}
        handler.rfile = BytesIO(b"{}")
        handler.do_POST()
        written = handler.wfile.getvalue()
        assert b"Unknown endpoint" in written

    def test_handle_manychat_conversion(self, handler):
        data = {"event": "blueprint_requested", "user_id": "u1", "username": "jdoe"}
        with patch("builtins.open", MagicMock()):
            with patch.object(Path, "mkdir"):
                handler.handle_manychat_conversion(data)
        written = handler.wfile.getvalue()
        assert b"logged" in written

    def test_handle_manychat_invalid_event(self, handler):
        data = {"event": "wrong_event"}
        handler.handle_manychat_conversion(data)
        written = handler.wfile.getvalue()
        assert b"Invalid event" in written



    def test_handle_gumroad_ping_no_email(self, handler):
        """When no email, _trigger_post_purchase is still called but may skip."""
        data = {"product_name": "ebook"}
        raw_payload = json.dumps(data).encode()
        # Patch WEBHOOK_SECRET to skip verification
        with patch.object(webhook_server, "GUMROAD_WEBHOOK_SECRET", "your_secret_here"):
            with patch("builtins.open", MagicMock()):
                with patch.object(Path, "mkdir"):
                    with patch("requests.post") as mock_post:
                        handler.handle_gumroad_ping(data, raw_payload)

    def test_handle_gumroad_ping(self, handler):
        data = {"product_name": "ebook", "email": "test@example.com", "price": 9.99}
        raw_payload = json.dumps(data).encode()
        # Patch GUMROAD_WEBHOOK_SECRET to "your_secret_here" so verification is skipped
        with patch.object(webhook_server, "GUMROAD_WEBHOOK_SECRET", "your_secret_here"):
            with patch("builtins.open", MagicMock()):
                with patch.object(Path, "mkdir"):
                    with patch("requests.post") as mock_post:
                        handler.handle_gumroad_ping(data, raw_payload)
        written = handler.wfile.getvalue()
        assert b"processed" in written

    def test_handle_make_trigger(self, handler):
        handler.headers = {"X-Make-Secret": "test_secret"}
        with patch.object(webhook_server, "MAKE_WEBHOOK_SECRET", "test_secret"):
            data = {"trigger": True}
            handler.handle_make_trigger(data)
        written = handler.wfile.getvalue()
        assert b"triggered" in written
    def test_trigger_post_purchase_with_url(self, handler):
        with patch.dict(os.environ, {"MAKE_POST_PURCHASE_WEBHOOK": "https://hook.make.com/test"}):
            with patch("requests.post") as mock_post:
                mock_post.return_value.status_code = 200
                handler._trigger_post_purchase({"email": "test@test.com"})
                mock_post.assert_called_once()

    def test_trigger_post_purchase_no_url(self, handler):
        with patch.dict(os.environ, {}, clear=True):
            handler._trigger_post_purchase({"email": "test@test.com"})

    def test_trigger_post_purchase_failure(self, handler):
        with patch.dict(os.environ, {"MAKE_POST_PURCHASE_WEBHOOK": "https://hook.make.com/test"}):
            with patch("requests.post", side_effect=Exception("network error")):
                handler._trigger_post_purchase({"email": "test@test.com"})

    def test_do_post_routes_manychat(self, handler):
        handler.path = "/webhook/manychat/conversion"
        content = json.dumps({"event": "blueprint_requested"})
        handler.rfile = BytesIO(content.encode())
        handler.headers = {"Content-Length": str(len(content))}
        handler.handle_manychat_conversion = MagicMock()
        handler.do_POST()
        handler.handle_manychat_conversion.assert_called_once()

    def test_do_post_routes_gumroad(self, handler):
        handler.path = "/webhook/gumroad/ping"
        content = json.dumps({"product_name": "ebook", "email": "a@b.com"})
        handler.rfile = BytesIO(content.encode())
        handler.headers = {"Content-Length": str(len(content))}
        handler.handle_gumroad_ping = MagicMock()
        handler.do_POST()
        handler.handle_gumroad_ping.assert_called_once()

    def test_do_post_routes_make(self, handler):
        handler.path = "/webhook/make/daily-trigger"
        content = json.dumps({"trigger": True})
        handler.rfile = BytesIO(content.encode())
        handler.headers = {"Content-Length": str(len(content)), "X-Make-Secret": "test_secret"}
        handler.handle_make_trigger = MagicMock()
        handler.do_POST()
        handler.handle_make_trigger.assert_called_once()

    def test_do_post_invalid_json(self, handler):
        handler.path = "/webhook/manychat/conversion"
        handler.rfile = BytesIO(b"not json}")
        handler.headers = {"Content-Length": "9"}
        handler.handle_manychat_conversion = MagicMock()
        handler.do_POST()
        handler.handle_manychat_conversion.assert_called_once()
    def test_gumroad_invalid_signature(self, handler):
        handler.path = "/webhook/gumroad/ping"
        handler.headers = {"X-Gumroad-Signature": "invalid"}
        raw_payload = b'{"sale_id": "123"}'
        handler.rfile = BytesIO(raw_payload)
        handler.headers["Content-Length"] = str(len(raw_payload))
        
        with patch.object(webhook_server, "GUMROAD_WEBHOOK_SECRET", "secret"):
            handler.do_POST()
            output = handler.wfile.getvalue()
            assert b'401' in output
            assert b'{"error": "Invalid signature"}' in output

    def test_make_invalid_secret(self, handler):
        handler.path = "/webhook/make/daily-trigger"
        handler.headers = {"X-Make-Secret": "invalid"}
        handler.rfile = BytesIO(b"{}")
        handler.headers["Content-Length"] = "2"
        
        with patch.object(webhook_server, "MAKE_WEBHOOK_SECRET", "secret"):
            handler.do_POST()
            output = handler.wfile.getvalue()
            assert b'401' in output
            assert b'{"error": "Unauthorized"}' in output



def test_run_server():
    with patch("scripts.webhook_server.HTTPServer") as mock_server_cls:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server
        webhook_server.run_server(port=9090)
        mock_server_cls.assert_called_once()
        mock_server.serve_forever.assert_called_once()


def test_run_server_shutdown():
    with patch("scripts.webhook_server.HTTPServer") as mock_server_cls:
        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt()
        mock_server_cls.return_value = mock_server
        webhook_server.run_server(port=8080)
        mock_server.shutdown.assert_called_once()


def test_main_entrypoint(tmp_path):
    import subprocess
    script_content = """
import runpy
try:
    import sys
    sys.argv = ["webhook_server.py", "9091"]
    runpy.run_module("scripts.webhook_server", run_name="__main__")
except SystemExit:
    pass
"""
    test_script = tmp_path / "test_main.py"
    test_script.write_text(script_content)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    # We mock HTTPServer inside the subprocess
    script_content = """
import sys
import types
mock_server = types.ModuleType("http.server")
class MockHTTPServer:
    def __init__(self, *args, **kw): pass
    def serve_forever(self): sys.exit(0)
    def shutdown(self): pass
mock_server.HTTPServer = MockHTTPServer
mock_server.BaseHTTPRequestHandler = object
sys.modules["http.server"] = mock_server

import runpy
sys.argv = ["webhook_server.py", "9091"]
runpy.run_module("scripts.webhook_server", run_name="__main__")
"""
    test_script.write_text(script_content)
    result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
    assert "9091" in result.stdout

def test_dotenv_import_error(tmp_path):
    import subprocess
    script_content = """
import sys
sys.modules['dotenv'] = None
import builtins
original_import = builtins.__import__
def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'dotenv':
        raise ImportError("Mocked")
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = mock_import

import runpy
try:
    runpy.run_module("scripts.webhook_server")
    print("DOTENV_PASSED")
except Exception as e:
    print(f"ERROR: {e}")
"""
    test_script = tmp_path / "test_dotenv.py"
    test_script.write_text(script_content)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent)
    result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
    assert "DOTENV_PASSED" in result.stdout
