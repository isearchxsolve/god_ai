import { chromium } from 'playwright-core';
import { join } from 'node:path';
import { mkdirSync } from 'node:fs';

const localAppData = process.env.LOCALAPPDATA;
const exe = join(localAppData, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');
const outDir = 'C:\\god_ai\\oioi\\oioi\\gui-test-screenshots';
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const consoleErrors = [];
page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
page.on('pageerror', (err) => consoleErrors.push('PAGEERROR: ' + err.message));

await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(4000); // let react-query fetch models/styles/health

await page.screenshot({ path: join(outDir, 't1_initial.png'), fullPage: false });

// Dump key visible facts
const facts = await page.evaluate(() => {
  const text = document.body.innerText;
  return {
    title: document.title,
    hasTopBar: !!document.querySelector('header'),
    bodyTextSample: text.slice(0, 1500),
    canvasNodes: document.querySelectorAll('.react-flow__node').length,
    buttons: Array.from(document.querySelectorAll('button')).slice(0, 30).map(b => b.textContent?.trim()).filter(Boolean),
  };
});
console.log(JSON.stringify(facts, null, 2));
console.log('CONSOLE_ERRORS:', JSON.stringify(consoleErrors, null, 2));
await browser.close();
