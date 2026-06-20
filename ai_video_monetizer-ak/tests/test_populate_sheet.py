"""Tests for scripts/populate_sheet.py."""
import os
import sys
import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

# ---------------------------------------------------------------------------
# Set env vars BEFORE any import of populate_sheet
# ---------------------------------------------------------------------------
os.environ["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "test_sheet_123"
os.environ["GOOGLE_SHEETS_TAB_NAME"] = "MySheet"

# ---------------------------------------------------------------------------
# Prevent populate_sheet from making real subprocess calls at import time
# ---------------------------------------------------------------------------
subprocess.run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))

# ---------------------------------------------------------------------------
# Mock the video_prompts.json file read during import
# ---------------------------------------------------------------------------
sample_matrix = [
    {"day": "1", "status": "Ready", "hook": "Hook 1", "prompt": "Prompt 1",
     "pinned_comment": "Comment 1"},
    {"day": "2", "status": "Ready", "hook": "Hook 2", "prompt": "Prompt 2",
     "pinned_comment": "Comment 2"},
]

open_patcher = patch("scripts.populate_sheet.open",
                      mock_open(read_data=json.dumps(sample_matrix)), create=True)
open_patcher.start()

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scripts import populate_sheet

# Critical: stop the open patcher after import so other tests aren't affected
open_patcher.stop()


class TestModuleLevel:
    def test_sheet_id_loaded(self):
        assert populate_sheet.SHEET_ID == "test_sheet_123"

    def test_sheet_tab_loaded(self):
        assert populate_sheet.SHEET_TAB == "MySheet"

    def test_matrix_loaded(self):
        assert len(populate_sheet.matrix) >= 1

    def test_headers_present(self):
        assert "Day" in populate_sheet.HEADERS
        assert "Status" in populate_sheet.HEADERS
        assert "Video Link" in populate_sheet.HEADERS


class TestFormatRow:
    def test_format_row_returns_correct_fields(self):
        item = {"day": "1", "status": "Ready", "hook": "Test Hook",
                "prompt": "Test prompt", "pinned_comment": "Test comment"}
        result = populate_sheet.format_row(item)
        assert result[0] == "1"
        assert result[1] == "Ready"
        assert result[2] == "Test Hook"
        assert result[3] == "Test prompt"
        assert result[4] == "Test comment"
        assert result[5] == ""   # Video Link placeholder
        assert result[6] == ""   # Views placeholder

    def test_format_all_rows(self):
        for item in populate_sheet.matrix:
            row = populate_sheet.format_row(item)
            assert len(row) == 7


class TestFallbackFunctions:
    def test_sheets_update_success(self):
        with patch("scripts.populate_sheet.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            result = populate_sheet.sheets_update("A1:B2", [["a", "b"]])
            assert result is True

    def test_sheets_update_failure(self):
        with patch("scripts.populate_sheet.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "error"
            mock_run.return_value = mock_result
            result = populate_sheet.sheets_update("A1:B2", [["a", "b"]])
            assert result is False

    def test_sheets_append_success(self):
        with patch("scripts.populate_sheet.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            result = populate_sheet.sheets_append("Sheet1!A1", [["a", "b"]])
            assert result is True

    def test_sheets_append_failure(self):
        with patch("scripts.populate_sheet.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stderr = "error"
            mock_run.return_value = mock_result
            result = populate_sheet.sheets_append("Sheet1!A1", [["a", "b"]])
            assert result is False

    def test_sheets_update_exception(self):
        with patch("scripts.populate_sheet.subprocess.run", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                populate_sheet.sheets_update("A1:B2", [["a", "b"]])

    def test_sheets_append_exception(self):
        with patch("scripts.populate_sheet.subprocess.run", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                populate_sheet.sheets_append("Sheet1!A1", [["a", "b"]])

class TestMainExecution:
    @pytest.fixture(autouse=True)
    def restore_subprocess(self):
        import subprocess
        orig = subprocess.run
        import importlib
        importlib.reload(subprocess)
        yield
        subprocess.run = orig

    def test_dotenv_import_error(self, tmp_path):
        """Test missing dotenv triggers install."""
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

import subprocess
calls = []
subprocess.check_call = lambda args: calls.append(args)

try:
    import scripts.populate_sheet
except SystemExit:
    pass

if any("dotenv" in str(c) for c in calls):
    print("DOTENV_INSTALLED")
"""
        test_script = tmp_path / "test_dotenv.py"
        test_script.write_text(script_content)
        
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
        assert "Installing python-dotenv" in result.stdout
        
    def test_missing_sheet_id(self, tmp_path):
        """Test script exits when SHEET_ID is missing."""
        env = os.environ.copy()
        # Explicitly override what dotenv might load
        env["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "your_sheet_id_here"
            
        script_path = str(Path(__file__).parent.parent / "scripts" / "populate_sheet.py")
        result = subprocess.run([sys.executable, script_path], capture_output=True, text=True, env=env)
        assert result.returncode == 1
        assert "not set in .env" in result.stdout
        
    def test_headers_update_fails(self, tmp_path):
        """Test fallback exits when headers fail."""
        script_content = """
import sys
sys.modules['google_workspace.scripts.google_api'] = None
import builtins
original_import = builtins.__import__
def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'google_workspace.scripts.google_api':
        raise ImportError("Mocked")
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = mock_import

import subprocess
def mock_run(cmd, *args, **kwargs):
    class MockResult:
        returncode = 1
        stderr = "Mock Error"
        stdout = ""
    return MockResult()
subprocess.run = mock_run

try:
    import scripts.populate_sheet
except SystemExit as e:
    print(f"EXIT_CODE_{e.code}")
"""
        test_script = tmp_path / "test_headers.py"
        test_script.write_text(script_content)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        env["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "test_sheet_123"
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
        assert "EXIT_CODE_1" in result.stdout

    def test_rows_update_fails(self, tmp_path):
        """Test fallback exits when rows update fails."""
        script_content = """
import sys
sys.modules['google_workspace.scripts.google_api'] = None
import builtins
original_import = builtins.__import__
def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == 'google_workspace.scripts.google_api':
        raise ImportError("Mocked")
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = mock_import

import subprocess
call_count = [0]
def mock_run(cmd, *args, **kwargs):
    call_count[0] += 1
    class MockResult:
        returncode = 0 if call_count[0] == 1 else 1
        stderr = "Mock Error" if call_count[0] > 1 else ""
        stdout = ""
    return MockResult()
subprocess.run = mock_run

try:
    import scripts.populate_sheet
except SystemExit as e:
    print(f"EXIT_CODE_{e.code}")
"""
        test_script = tmp_path / "test_rows.py"
        test_script.write_text(script_content)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        env["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "test_sheet_123"
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
        assert "EXIT_CODE_1" in result.stdout

    def test_main_block(self, tmp_path):
        """Test if __name__ == '__main__' path."""
        # This simulates having google_workspace available and running main
        script_content = """
import sys
import types

gw = types.ModuleType("google_workspace")
gws = types.ModuleType("google_workspace.scripts")
gw_api = types.ModuleType("google_workspace.scripts.google_api")

def mock_main():
    print("GAPI_MAIN_CALLED")
gw_api.main = mock_main

sys.modules["google_workspace"] = gw
sys.modules["google_workspace.scripts"] = gws
sys.modules["google_workspace.scripts.google_api"] = gw_api

# Mock google.oauth2, etc.
goauth = types.ModuleType("google")
goauth_auth = types.ModuleType("google.auth")
goauth_auth_tr = types.ModuleType("google.auth.transport")
goauth_auth_tr_req = types.ModuleType("google.auth.transport.requests")
goauth2 = types.ModuleType("google.oauth2")
goauth2_creds = types.ModuleType("google.oauth2.credentials")
ggapiclient = types.ModuleType("googleapiclient")
ggapiclient_dis = types.ModuleType("googleapiclient.discovery")
gapi_errors = types.ModuleType("googleapiclient.errors")
ggapiclient.__path__ = []
goauth.__path__ = []
goauth_auth.__path__ = []
goauth_auth_tr.__path__ = []
goauth2.__path__ = []
ggapiclient.discovery = ggapiclient_dis
ggapiclient.errors = gapi_errors
goauth.auth = goauth_auth
goauth_auth.transport = goauth_auth_tr
goauth_auth_tr.requests = goauth_auth_tr_req
goauth.oauth2 = goauth2
goauth2.credentials = goauth2_creds

class MockRequest: pass
goauth_auth_tr_req.Request = MockRequest
class MockCreds:
    def __init__(self, **kw): pass
    @classmethod
    def from_authorized_user_file(cls, path, scopes=None): return cls()
    @property
    def valid(self): return True
    @property
    def expired(self): return False
    @property
    def refresh_token(self): return "mock_refresh_token"
goauth2_creds.Credentials = MockCreds

sys.modules["google"] = goauth
sys.modules["google.auth"] = goauth_auth
sys.modules["google.auth.transport"] = goauth_auth_tr
sys.modules["google.auth.transport.requests"] = goauth_auth_tr_req
sys.modules["google.oauth2"] = goauth2
sys.modules["google.oauth2.credentials"] = goauth2_creds
sys.modules["googleapiclient"] = ggapiclient
sys.modules["googleapiclient.discovery"] = ggapiclient_dis
sys.modules["googleapiclient.errors"] = gapi_errors

class MockSheetsResource:
    def values(self): return self
    def update(self, spreadsheetId, range, valueInputOption, body):
        class MockUpdateReq:
            def execute(self): return {"updatedCells": 10}
        return MockUpdateReq()
    def clear(self, spreadsheetId, range):
        class MockClearReq:
            def execute(self): return {}
        return MockClearReq()

def build_mock(service, version, credentials):
    class MockService:
        def spreadsheets(self): return MockSheetsResource()
    return MockService()

import pathlib
orig_home = pathlib.Path.home
def mock_home():
    class MockPath:
        def __truediv__(self, other):
            return self
        def exists(self): return True
        def __str__(self): return "mock_token.json"
    return MockPath()
pathlib.Path.home = mock_home

ggapiclient_dis.build = build_mock

try:
    import runpy
    runpy.run_module("scripts.populate_sheet", run_name="__main__")
except SystemExit as e:
    print(f"MAIN_EXIT_{e.code}")
except Exception as e:
    print(f"ERROR: {e}")
"""
        test_script = tmp_path / "test_main.py"
        test_script.write_text(script_content)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        env["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "test_sheet_123"
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
        assert "✅ Successfully populated 30 days in Google Sheets!" in result.stdout
        
    def test_main_block_no_token(self, tmp_path):
        """Test __main__ without token.json."""
        script_content = """
import sys
import types
import os

gw = types.ModuleType("google_workspace")
gws = types.ModuleType("google_workspace.scripts")
gw_api = types.ModuleType("google_workspace.scripts.google_api")
sys.modules["google_workspace"] = gw
sys.modules["google_workspace.scripts"] = gws

try:
    import runpy
    runpy.run_module("scripts.populate_sheet", run_name="__main__")
except SystemExit as e:
    print(f"MAIN_EXIT_{e.code}")
"""
        test_script = tmp_path / "test_main_no_token.py"
        test_script.write_text(script_content)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        env["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "test_sheet_123"
        
        # Hide token.json if it exists
        token_path = Path(__file__).parent.parent / "token.json"
        if token_path.exists():
            token_path.rename(token_path.with_suffix(".json.bak"))
            
        try:
            result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
            assert "MAIN_EXIT_1" in result.stdout
        finally:
            if token_path.with_suffix(".json.bak").exists():
                token_path.with_suffix(".json.bak").rename(token_path)
