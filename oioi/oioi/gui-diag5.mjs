import { chromium } from 'playwright-core';
import { join } from 'node:path';

const exe = join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(3500);

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
  const parent = root.querySelector(' > div > div.h-screen.flex.flex-col.bg-bg-base.text-fg-primary.overflow-hidden');
  const outerFlex1 = parent?.querySelector(' > div.flex-1.flex.overflow-hidden');
  const topBar = parent?.querySelector(' > header');
  const sidebar = outerFlex1?.querySelector(' > aside.w-80.shrink-0');
  const main = outerFlex1?.querySelector(' > main.flex-1.relative');
  return {
    bodyRect: rect(body),
    rootRect: rect(root),
    parentRect: rect(parent),
    parentComputed: {
      height: getStyle(parent, 'height'),
      flex: getStyle(parent, 'flex'),
      flexGrow: getStyle(parent, 'flex-grow'),
      flexShrink: getStyle(parent, 'flex-shrink'),
      flexBasis: getStyle(parent, 'flex-basis'),
      display: getStyle(parent, 'display'),
      flexDirection: getStyle(parent, 'flex-direction'),
    },
    outerFlex1Rect: rect(outerFlex1),
    outerFlex1Computed: {
      height: getStyle(outerFlex1, 'height'),
      flex: getStyle(outerFlex1, 'flex'),
      flexGrow: getStyle(outerFlex1, 'flex-grow'),
      flexShrink: getStyle(outerFlex1, 'flex-shrink'),
      flexBasis: getStyle(outerFlex1, 'flex-basis'),
      display: getStyle(outerFlex1, 'display'),
      flexDirection: getStyle(outerFlex1, 'flex-direction'),
      classList: Array.from(outerFlex1?.classList || []),
    },
    topBarRect: rect(topBar),
    topBarComputed: { height: getStyle(topBar, 'height') },
    sidebarRect: rect(sidebar),
    sidebarComputed: { height: getStyle(sidebar, 'height'), width: getStyle(sidebar, 'width') },
    mainRect: rect(main),
    mainComputed: { height: getStyle(main, 'height'), width: getStyle(main, 'width'), flexGrow: getStyle(main, 'flex-grow') },
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();