"""Tests for scripts/test_google_connection.py."""
import os
import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

# Set env vars before import
os.environ.setdefault("GOOGLE_SHEETS_CONTENT_PIPELINE_ID", "test_sheet_123")
os.environ.setdefault("GOOGLE_SHEETS_TAB_NAME", "Sheet1")

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scripts import test_google_connection as tgc


class TestSheetsConnection:
    @pytest.fixture
    def mock_creds(self):
        """Standard mock credentials that pass the basic checks."""
        creds = MagicMock()
        creds.expired = False
        creds.valid = True
        creds.refresh_token = None
        return creds

    def _setup_token_file(self, tmp_path):
        """Create a fake token file and return the token dir."""
        token_dir = tmp_path / ".hermes"
        token_dir.mkdir()
        token_file = token_dir / "google_token.json"
        token_file.write_text(json.dumps({"token": "fake"}))
        return token_dir

    def test_success(self, tmp_path, mock_creds):
        """Test successful sheets connection."""
        self._setup_token_file(tmp_path)
        mock_service = MagicMock()
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["header"], ["row1"]]
        }

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("google.auth.transport.requests.Request"):
                with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds):
                    with patch("googleapiclient.discovery.build", return_value=mock_service):
                        result = tgc.test_sheets_connection()
                        assert result is True

    def test_creds_expired_with_refresh(self, tmp_path):
        """Test creds refresh flow when expired but has refresh_token."""
        self._setup_token_file(tmp_path)
        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "token123"
        mock_creds.valid = True
        mock_service = MagicMock()
        mock_service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["header"]]
        }

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("google.auth.transport.requests.Request") as mock_request:
                with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds):
                    with patch("googleapiclient.discovery.build", return_value=mock_service):
                        result = tgc.test_sheets_connection()
                        assert result is True
                        mock_creds.refresh.assert_called_once()

    def test_no_token_path(self, tmp_path):
        """Test missing token file returns False."""
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = tgc.test_sheets_connection()
            assert result is False

    def test_general_exception(self, tmp_path):
        """Test exception in API call returns False."""
        self._setup_token_file(tmp_path)
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("googleapiclient.discovery.build", side_effect=Exception("API error")):
                result = tgc.test_sheets_connection()
                assert result is False


class TestDriveConnection:
    @pytest.fixture
    def mock_creds(self):
        creds = MagicMock()
        creds.expired = False
        creds.valid = True
        return creds

    def test_success(self, tmp_path, mock_creds):
        token_dir = tmp_path / ".hermes"
        token_dir.mkdir()
        (token_dir / "google_token.json").write_text(json.dumps({"token": "fake"}))

        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {
            "files": [{"name": "test.txt"}]
        }

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds):
                with patch("googleapiclient.discovery.build", return_value=mock_service):
                    result = tgc.test_drive_connection()
                    assert result is True

    def test_creds_expired_refresh(self, tmp_path):
        token_dir = tmp_path / ".hermes"
        token_dir.mkdir()
        (token_dir / "google_token.json").write_text(json.dumps({"token": "fake"}))

        mock_creds = MagicMock()
        mock_creds.expired = True
        mock_creds.refresh_token = "rtok"
        mock_creds.valid = True
        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("google.auth.transport.requests.Request"):
                with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds):
                    with patch("googleapiclient.discovery.build", return_value=mock_service):
                        result = tgc.test_drive_connection()
                        assert result is True
                        mock_creds.refresh.assert_called_once()

    def test_api_error(self, tmp_path):
        token_dir = tmp_path / ".hermes"
        token_dir.mkdir()
        (token_dir / "google_token.json").write_text(json.dumps({"token": "fake"}))

        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_creds.valid = True

        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds):
                with patch("googleapiclient.discovery.build", side_effect=Exception("API error")):
                    result = tgc.test_drive_connection()
                    assert result is False

    def test_no_token(self, tmp_path):
        with patch("pathlib.Path.home", return_value=tmp_path):
            result = tgc.test_drive_connection()
            assert result is False

    def test_drive_connection_no_folder_id(self, tmp_path):
        """Test listing root folders when GOOGLE_DRIVE_ROOT_FOLDER_ID is missing."""
        token_dir = tmp_path / ".hermes"
        token_dir.mkdir(parents=True)
        token_file = token_dir / "google_token.json"
        token_file.write_text("{}")

        mock_creds = MagicMock()
        mock_creds.expired = False
        
        with patch("google.oauth2.credentials.Credentials.from_authorized_user_file", return_value=mock_creds):
            with patch("scripts.test_google_connection.Path.home", return_value=tmp_path):
                with patch("googleapiclient.discovery.build") as mock_build:
                    with patch.dict(os.environ, {"GOOGLE_DRIVE_ROOT_FOLDER_ID": ""}):
                        mock_files = mock_build.return_value.files.return_value
                        mock_files.list.return_value.execute.return_value = {"files": [{"name": "A", "id": "1"}]}
                        result = tgc.test_drive_connection()
                        assert result is True
                        mock_files.list.assert_called_once()


class TestMain:
    def test_success(self):
        with patch.object(tgc, "test_sheets_connection", return_value=True):
            with patch.object(tgc, "test_drive_connection", return_value=True):
                assert tgc.main() == 0

    def test_sheets_fails(self):
        with patch.object(tgc, "test_sheets_connection", return_value=False):
            with patch.object(tgc, "test_drive_connection", return_value=True):
                assert tgc.main() == 1

    def test_drive_fails(self):
        with patch.object(tgc, "test_sheets_connection", return_value=True):
            with patch.object(tgc, "test_drive_connection", return_value=False):
                assert tgc.main() == 1

    def test_both_fail(self):
        with patch.object(tgc, "test_sheets_connection", return_value=False):
            with patch.object(tgc, "test_drive_connection", return_value=False):
                assert tgc.main() == 1
    def test_missing_sheet_id(self):
        """Test main fails when SHEET_ID is missing."""
        with patch.object(tgc, "SHEET_ID", ""):
            assert tgc.main() == 1

class TestImportExecution:
    def test_dotenv_import_error(self, tmp_path):
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

import subprocess
calls = []
subprocess.run = lambda args, **kw: calls.append(args)

try:
    import scripts.test_google_connection
except ImportError:
    pass
if any("python-dotenv" in str(c) for c in calls):
    print("DOTENV_INSTALLED")
"""
        test_script = tmp_path / "test_dotenv.py"
        test_script.write_text(script_content)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
        assert "DOTENV_INSTALLED" in result.stdout

    def test_run_as_main(self, tmp_path):
        import subprocess
        script_content = """
import sys
import types
import runpy
try:
    runpy.run_module("scripts.test_google_connection", run_name="__main__")
except SystemExit as e:
    print(f"MAIN_EXIT_{e.code}")
"""
        test_script = tmp_path / "test_main.py"
        test_script.write_text(script_content)
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parent.parent)
        # Ensure we have a valid SHEET_ID to get to test_sheets_connection
        env["GOOGLE_SHEETS_CONTENT_PIPELINE_ID"] = "123"
        
        result = subprocess.run([sys.executable, str(test_script)], capture_output=True, text=True, env=env)
        # It will fail connecting if no token, returning 1, or pass. Just check MAIN_EXIT
        assert "MAIN_EXIT" in result.stdout
