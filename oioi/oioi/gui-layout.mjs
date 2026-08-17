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
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const body = document.body;
  const root = document.querySelector('#__next') || document.body;
  // The column flex is the first child of root that has flex-col
  const columnFlex = Array.from(root.children).find(el => el.classList && el.classList.contains('flex-col'));
  const outerFlex1 = columnFlex?.querySelector('.flex-1.flex.overflow-hidden');
  const topBar = columnFlex?.querySelector('header');
  return {
    body: { ...rect(body), computed: { height: getStyle(body, 'height') } },
    root: { ...rect(root), computed: { height: getStyle(root, 'height') } },
    columnFlex: { ...rect(columnFlex), computed: { height: getStyle(columnFlex, 'height'), flex: getStyle(columnFlex, 'flex'), flexDirection: getStyle(columnFlex, 'flex-direction') } },
    topBar: { ...rect(topBar), computed: { height: getStyle(topBar, 'height') } },
    outerFlex1: { ...rect(outerFlex1), computed: { height: getStyle(outerFlex1, 'height'), flex: getStyle(outerFlex1, 'flex'), flexGrow: getStyle(outerFlex1, 'flex-grow'), flexShrink: getStyle(outerFlex1, 'flex-shrink'), flexBasis: getStyle(outerFlex1, 'flex-basis') } },
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();