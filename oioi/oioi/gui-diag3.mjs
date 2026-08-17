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
  const root = document.querySelector('#__next') || document.body;
  const topBar = document.querySelector('header');
  const innerFlex = root.querySelector(' > div > div.flex-1.flex.overflow-hidden');
  const sidebar = innerFlex?.querySelector('aside.w-80');
  const main = innerFlex?.querySelector('main.flex-1.relative');
  return {
    root: rect(root),
    topBar: rect(topBar),
    innerFlex: rect(innerFlex),
    sidebar: rect(sidebar),
    main: rect(main),
    computed: {
      topBarHeight: getComputedStyle(topBar).height,
      innerFlexHeight: getComputedStyle(innerFlex).height,
      mainHeight: getComputedStyle(main).height,
      sidebarWidth: getComputedStyle(sidebar).width,
    }
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();