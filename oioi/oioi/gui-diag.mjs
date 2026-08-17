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
    const cs = getComputedStyle(el);
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height), pos: cs.position, hProp: cs.height, cls: el.className?.toString?.().slice(0, 80) };
  };
  const panes = document.querySelectorAll('.react-flow__pane');
  const flows = document.querySelectorAll('.react-flow');
  return {
    flowCount: flows.length,
    paneCount: panes.length,
    body: rect(document.body),
    rootDiv: rect(document.querySelector('#__next') || document.body.firstElementChild),
    main: rect(document.querySelector('main')),
    canvasGrid: rect(document.querySelector('.canvas-grid')),
    flow0: rect(flows[0]),
    flow1: rect(flows[1]),
    pane0: rect(panes[0]),
    viewport0: rect(document.querySelector('.react-flow__viewport')),
    renderer: rect(document.querySelector('.react-flow__renderer')),
    edgerenderer: rect(document.querySelector('.react-flow__edges')),
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();
