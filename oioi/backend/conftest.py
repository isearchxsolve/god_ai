"""Pytest configuration for backend tests."""
import sys
import os
import asyncio

# Add backend directory to Python path for imports
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Also add the parent directory for app module imports
parent_dir = os.path.dirname(backend_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Ensure a fresh event loop is available for tests that call
# asyncio.get_event_loop().run_until_complete() — this is deprecated in
# Python 3.10+ but older tests still rely on it.
try:
    asyncio.set_event_loop(asyncio.new_event_loop())
except Exception:
    pass