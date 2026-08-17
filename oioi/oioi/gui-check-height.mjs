import { chromium } from 'playwright-core';
import { join } from 'node:path';

const exe = join(process.env.LOCALAPPDATA, 'ms-playwright', 'chromium-1234', 'chrome-win64', 'chrome.exe');

const browser = await chromium.launch({ executablePath: exe, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://localhost:3000/', { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(4000); // let react-query fetch

const diag = await page.evaluate(() => {
  const rect = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
  };
  const body = document.body;
  const outerFlex1 = document.querySelector('body > div > div.flex-1.flex.overflow-hidden');
  const topBar = document.querySelector('header');
  const sidebar = outerFlex1?.querySelector('aside.w-80');
  const main = outerFlex1?.querySelector('main.flex-1.relative');
  const canvasGrid = main?.querySelector('.canvas-grid');
  const flow = document.querySelector('.react-flow');
  const pane = document.querySelector('.react-flow__pane');
  const viewport = document.querySelector('.react-flow__viewport');
  const renderer = document.querySelector('.react-flow__renderer');
  const controls = document.querySelector('.react-flow__controls');
  const minimap = document.querySelector('.react-flow__minimap');
  const background = document.querySelector('.react-flow__background');
  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    body: { ...rect(body), computed: { height: getComputedStyle(body).height } },
    outerFlex1: { ...rect(outerFlex1), computed: { height: getComputedStyle(outerFlex1).height, flex: getComputedStyle(outerFlex1).flex } },
    topBar: { ...rect(topBar), computed: { height: getComputedStyle(topBar).height } },
    sidebar: { ...rect(sidebar), computed: { width: getComputedStyle(sidebar).width, height: getComputedStyle(sidebar).height } },
    main: { ...rect(main), computed: { height: getComputedStyle(main).height, flexGrow: getComputedStyle(main).flexGrow } },
    canvasGrid: { ...rect(canvasGrid), computed: { height: getComputedStyle(canvasGrid).height, width: getComputedStyle(canvasGrid).width } },
    flow: { ...rect(flow), computed: { height: getComputedStyle(flow).height, width: getComputedStyle(flow).width } },
    pane: { ...rect(pane), computed: { height: getComputedStyle(pane).height, width: getComputedStyle(pane).width } },
    viewport: { ...rect(viewport), computed: { height: getComputedStyle(viewport).height, width: getComputedStyle(viewport).width } },
    renderer: { ...rect(renderer), computed: { height: getComputedStyle(renderer).height, width: getComputedStyle(renderer).width } },
    controls: { ...rect(controls), computed: { height: getComputedStyle(controls).height, width: getComputedStyle(controls).width, visible: !!controls && controls.getBoundingClientRect().height > 0 && controls.getBoundingClientRect().width > 0 } },
    minimap: { ...rect(minimap), computed: { height: getComputedStyle(minimap).height, width: getComputedStyle(minimap).width, visible: !!minimap && minimap.getBoundingClientRect().height > 0 && minimap.getBoundingClientRect().width > 0 } },
    background: { ...rect(background), computed: { height: getComputedStyle(background).height, width: getComputedStyle(background).width, visible: !!background && background.getBoundingClientRect().height > 0 && background.getBoundingClientRect().width > 0 } },
  };
});
console.log(JSON.stringify(diag, null, 2));
await browser.close();