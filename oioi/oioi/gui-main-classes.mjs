import { chromium } from 'playwright-core';
import { join } from 'node:path';

const exe = join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(4000);

const diag = await page.evaluate(() => {
  const main = document.querySelector('main.flex-1.relative');
  if (!main) return { error: 'main element not found' };
  
  const computed = getComputedStyle(main);
  return {
    classes: main.className,
    flex: computed.flex,
    flexGrow: computed.flexGrow,
    flexShrink: computed.flexShrink,
    flexBasis: computed.flexBasis,
    height: computed.height,
    width: computed.width,
    display: computed.display,
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();