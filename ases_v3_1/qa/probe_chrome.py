"""Probe: can Selenium launch headless Chrome on this machine?"""
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=1280,900")

try:
    driver = webdriver.Chrome(options=opts)
    driver.get("data:text/html,<html><title>probe</title><body><h1 id='ok'>OK</h1></body></html>")
    title = driver.title
    text = driver.find_element("id", "ok").text
    ver = driver.capabilities.get("browserVersion", "?")
    driver.quit()
    print(f"PROBE_OK title={title!r} text={text!r} chrome={ver}")
    sys.exit(0)
except Exception as e:
    print(f"PROBE_FAIL {type(e).__name__}: {e}")
    sys.exit(1)
