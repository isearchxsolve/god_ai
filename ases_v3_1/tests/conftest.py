"""
Shared fixtures for the Selenium QA gate.

Everything is lazy: these fixtures only spin up when a test actually
requests them, so the smoke/syntax/integration gates are unaffected.

    base_url  - session: real FastAPI app (qa/qa_app.py) on a free port,
                served by uvicorn in a daemon thread, fakes for all backends
    driver    - session: one headless Chrome reused across all 1000 cases
    console   - function: reset server state + fresh navigation to /qa
"""

import os
import socket
import sys
import threading
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QA_DIR = os.path.join(ROOT, "qa")
if QA_DIR not in sys.path:
    sys.path.insert(0, QA_DIR)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def base_url():
    import uvicorn
    from qa_app import build_app

    app = build_app()
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 30
    last_err = None
    started = False
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url + "/health", timeout=1) as r:
                if r.status == 200:
                    started = True
                    break
        except Exception as e:  # noqa: BLE001 — retry until deadline
            last_err = e
            time.sleep(0.2)
    if not started:
        raise RuntimeError(f"QA server failed to start on {url}: {last_err}")

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1400,1000")
    d = webdriver.Chrome(options=opts)
    d.set_page_load_timeout(30)
    yield d
    d.quit()


@pytest.fixture
def console(driver, base_url):
    """Reset in-memory server state and load a fresh QA console page."""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait

    req = urllib.request.Request(base_url + "/qa-api/reset", data=b"", method="POST")
    urllib.request.urlopen(req, timeout=5).read()

    driver.get(base_url + "/qa")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="app-title"]'))
    )
    return driver
