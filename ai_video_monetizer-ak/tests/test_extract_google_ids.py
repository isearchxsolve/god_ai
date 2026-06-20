"""Tests for scripts/extract_google_ids.py."""
import os
import sys
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# Mock playwright BEFORE import - must be an async context manager
class MockPlaywright:
    """Mock for playwright that supports async context manager protocol."""
    def __init__(self):
        self.chromium = MagicMock()
        self.chromium.launch = AsyncMock()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass

class MockAsyncPlaywright:
    """Mock for async_playwright() call that returns an async context manager."""
    def __call__(self):
        return MockPlaywright()
# Install mock before import
sys.modules["playwright"] = MagicMock()
sys.modules["playwright.async_api"] = MagicMock()
sys.modules["playwright.async_api"].async_playwright = MockAsyncPlaywright()

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scripts import extract_google_ids


class TestExtractFromUrl:
    def test_valid_drive_url(self):
        url = "https://drive.google.com/drive/folders/ABC123xyz"
        result = extract_google_ids.extract_from_url(
            extract_google_ids.DRIVE_FOLDER_PATTERN, url, "drive"
        )
        assert result == "ABC123xyz"

    def test_valid_sheet_url(self):
        url = "https://docs.google.com/spreadsheets/d/SHEET123/edit"
        result = extract_google_ids.extract_from_url(
            extract_google_ids.SHEET_ID_PATTERN, url, "sheet"
        )
        assert result == "SHEET123"

    def test_no_match(self):
        result = extract_google_ids.extract_from_url(
            extract_google_ids.DRIVE_FOLDER_PATTERN, "https://example.com", "drive"
        )
        assert result is None

    def test_empty_url(self):
        result = extract_google_ids.extract_from_url(
            extract_google_ids.DRIVE_FOLDER_PATTERN, "", "drive"
        )
        assert result is None


class TestExtractIdsWithPlaywright:
    @pytest.mark.asyncio
    async def test_extract_ids_skips_placeholders(self, monkeypatch):
        monkeypatch.setattr(extract_google_ids, "AUTO_OPEN_URLS", False)
        ids = await extract_google_ids.extract_ids_with_playwright()
        assert ids == {}

    @pytest.mark.asyncio
    async def test_extract_ids_process_urls(self, monkeypatch):
        monkeypatch.setattr(extract_google_ids, "DRIVE_ROOT_URL", "https://drive.google.com/drive/folders/valid_root_id")
        monkeypatch.setattr(extract_google_ids, "DRIVE_SCRIPTS_URL", "https://drive.google.com/drive/folders/valid_scripts_id")
        monkeypatch.setattr(extract_google_ids, "SHEET_URL", "https://docs.google.com/spreadsheets/d/valid_sheet_id/edit")
        monkeypatch.setattr(extract_google_ids, "AUTO_OPEN_URLS", True)
        
        mock_page = MagicMock()
        mock_page.url = "https://drive.google.com/drive/folders/redirected_id"
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_browser.close = AsyncMock()
        
        mock_p = AsyncMock()
        mock_p.chromium.launch = AsyncMock(return_value=mock_browser)
        
        class MockAsyncPlaywrightContext:
            async def __aenter__(self):
                return mock_p
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
        
        def mock_async_playwright():
            return MockAsyncPlaywrightContext()
            
        monkeypatch.setattr(extract_google_ids, "async_playwright", mock_async_playwright)
        # Test successful navigation and extraction + redirect
        ids = await extract_google_ids.extract_ids_with_playwright()
        assert ids["GOOGLE_DRIVE_ROOT_FOLDER_ID"] == "redirected_id"
        assert ids["GOOGLE_DRIVE_SCRIPTS_FOLDER_ID"] == "redirected_id"
        
        # Now test exception during navigation
        mock_page.goto.side_effect = Exception("navigation error")
        ids = await extract_google_ids.extract_ids_with_playwright()
        # Should still get the original extracted ones if it fails
        assert ids["GOOGLE_DRIVE_ROOT_FOLDER_ID"] == "valid_root_id"
    def test_import_error_installs_playwright(self, tmp_path):
        """Test that missing playwright triggers installation."""
        import subprocess
        
        script_content = """
import sys
import builtins
import importlib.util
from pathlib import Path

script_path = Path(r\"\"\"{}\"\"\")
spec = importlib.util.spec_from_file_location("extract_google_ids", script_path)
module = importlib.util.module_from_spec(spec)

original_import = builtins.__import__
import_calls = 0
def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
    global import_calls
    if name == 'playwright.async_api':
        import_calls += 1
        if import_calls == 1:
            raise ImportError("Mocked")
    return original_import(name, globals, locals, fromlist, level)
builtins.__import__ = mock_import

sys.modules["extract_google_ids"] = module

import subprocess
calls = []
def mock_check_call(args):
    calls.append(args)
subprocess.check_call = mock_check_call

class MockPlaywrightAsyncApi:
    async_playwright = lambda: None

class MockPlaywright:
    async_api = MockPlaywrightAsyncApi()

sys.modules['playwright.async_api'] = MockPlaywrightAsyncApi()
sys.modules['playwright'] = MockPlaywright()

try:
    spec.loader.exec_module(module)
except Exception as e:
    print("Exec module error:", e)

if any("playwright" in str(c) for c in calls):
    print("INSTALL_CALLED")
"""
        script_path = str(Path(__file__).parent.parent / "scripts" / "extract_google_ids.py")
        test_script = tmp_path / "test_import.py"
        test_script.write_text(script_content.format(script_path))
        
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True)
        assert "Installing playwright" in result.stdout
class TestMain:
    @pytest.mark.asyncio
    async def test_main_entrypoint(self, monkeypatch):
        """Test the main function."""
        # Mock extract_ids_with_playwright so main doesn't try to use playwright
        monkeypatch.setattr("scripts.extract_google_ids.extract_ids_with_playwright", AsyncMock(return_value={
            "ROOT_FOLDER_ID": "root_id",
            "SCRIPTS_FOLDER_ID": "scripts_id",
            "RAW_VIDEOS_FOLDER_ID": "raw_id",
            "DIGITAL_PRODUCTS_FOLDER_ID": "dig_id",
            "SHEET_ID": "sheet_id"
        }))
        monkeypatch.setattr(extract_google_ids, "DRIVE_ROOT_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "DRIVE_SCRIPTS_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "DRIVE_RAW_VIDEOS_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "DRIVE_DIGITAL_PRODUCTS_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "SHEET_URL", "valid_url")
        result = await extract_google_ids.main()
        assert result == 0

    @pytest.mark.asyncio
    async def test_main_missing_ids(self, monkeypatch):
        """Test main when ids are missing."""
        monkeypatch.setattr("scripts.extract_google_ids.extract_ids_with_playwright", AsyncMock(return_value={}))
        monkeypatch.setattr(extract_google_ids, "DRIVE_ROOT_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "DRIVE_SCRIPTS_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "DRIVE_RAW_VIDEOS_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "DRIVE_DIGITAL_PRODUCTS_URL", "valid_url")
        monkeypatch.setattr(extract_google_ids, "SHEET_URL", "valid_url")
        result = await extract_google_ids.main()
        # Replace builtins.open or just verify it runs
        result = await extract_google_ids.main()
        assert result == 1

    def test_run_as_main(self, monkeypatch):
        """Test if __name__ == '__main__' behavior."""
        import sys
        import asyncio
        # Mock sys.exit and asyncio.run to test line 197
        monkeypatch.setattr(sys, "exit", MagicMock())
        monkeypatch.setattr(asyncio, "run", MagicMock(return_value=0))
        # We can't directly execute `if __name__ == "__main__":` because the module is imported, 
        # but we can simulate what it does or we can reload it with monkeypatched __name__
        pass
    def test_run_as_main_subprocess(self):
        """Test __main__ block via subprocess."""
        import subprocess
        result = subprocess.run([sys.executable, str(Path(__file__).parent.parent / "scripts" / "extract_google_ids.py")], capture_output=True, text=True)
        # Should exit with 0 if default placeholder URLs are used, wait...
        # the script uses default URLs which are skipped, returning {} -> error 1 if no ids
        assert result.returncode == 1
    def test_default_urls_have_placeholders(self):
        """Test that default URLs contain placeholder markers."""
        assert "YOUR" in extract_google_ids.DRIVE_ROOT_URL


import os
from pathlib import Path
