import { chromium } from 'playwright-core';
import { join } from 'node:path';

const exe = join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(3500);

const diag = await page.evaluate(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const body = document.body;
  const outerFlex1 = document.querySelector('body > div > div.flex-1.flex.overflow-hidden');
  const topBar = document.querySelector('header');
  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    body: { ...rect(body), computed: { height: getComputedStyle(body).height, display: getComputedStyle(body).display, flexDirection: getComputedStyle(body).flexDirection, flex: getComputedStyle(body).flex } },
    topBar: { ...rect(topBar), computed: { height: getComputedStyle(topBar).height } },
    outerFlex1: { ...rect(outerFlex1), computed: { height: getComputedStyle(outerFlex1).height, flex: getComputedStyle(outerFlex1).flex, flexGrow: getComputedStyle(outerFlex1).flexGrow, flexShrink: getComputedStyle(outerFlex1).flexShrink, flexBasis: getComputedStyle(outerFlex1).flexBasis, classList: Array.from(outerFlex1?.classList || []) } },
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();