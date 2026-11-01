import { chromium } from 'playwright';
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2, recordVideo: { dir: '/tmp/rectest', size: { width: 2560, height: 1440 } } });
const p = await ctx.newPage(); await p.goto('http://localhost:4173/?run=c2'); await p.waitForTimeout(2000);
await ctx.close(); await b.close();
