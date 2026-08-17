import { chromium } from 'playwright-core';
import { join } from 'node:path';

const exe = join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(4000);

const diag = await page.evaluate(() => {
  const getStyle = (el, prop) => {
    if (!el) return null;
    return getComputedStyle(el).getPropertyValue(prop);
  };
  const html = document.documentElement;
  const body = document.body;
  const root = document.querySelector('#__next') || document.body;
  return {
    html: {
      height: getStyle(html, 'height'),
      minHeight: getStyle(html, 'min-height'),
      display: getStyle(html, 'display'),
    },
    body: {
      height: getStyle(body, 'height'),
      minHeight: getStyle(body, 'min-height'),
      display: getStyle(body, 'display'),
    },
    root: {
      height: getStyle(root, 'height'),
      minHeight: getStyle(root, 'min-height'),
      display: getStyle(root, 'display'),
    },
    viewport: { w: window.innerWidth, h: window.innerHeight },
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();