import { chromium } from 'playwright-core';
import { join } from 'node:path';

const exe = join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const outDir = 'C:\\god_ai\\oioi\\oioi\\gui-test-screenshots';

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const consoleErrors = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text()); });
page.on('pageerror', (e) => consoleErrors.push('PAGEERROR: ' + e.message));

await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(4000);

// DOM geometry facts for canvas widgets
const widgets = await page.evaluate(() => {
  const pick = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { found: true, x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), visible: r.width > 0 && r.height > 0 };
  };
  return {
    controls: pick('.react-flow__controls'),
    minimap: pick('.react-flow__minimap'),
    background: pick('.react-flow__background'),
    pane: pick('.react-flow__pane'),
    topbarBadges: document.querySelectorAll('header .rounded-full').length,
  };
});
console.log(JSON.stringify(widgets, null, 2));

// Zoomed screenshots: bottom-right corner (controls), bottom-left (minimap), top bar
await page.screenshot({ path: join(outDir, 't1b_canvas_bottom_right.png'), clip: { x: 1140, y: 700, width: 300, height: 200 } });
await page.screenshot({ path: join(outDir, 't1c_topbar.png'), clip: { x: 0, y: 0, width: 1440, height: 60 } });
await page.screenshot({ path: join(outDir, 't1d_canvas_bottom_left.png'), clip: { x: 0, y: 600, width: 400, height: 300 } });
console.log('CONSOLE_ERRORS:', JSON.stringify(consoleErrors));
await browser.close();
