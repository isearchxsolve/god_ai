"""Ensure the life_archive package under python/ is importable in tests."""

import sys
from pathlib import Path

_PYTHON_DIR = str(Path(__file__).resolve().parents[2] / "python")
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)
