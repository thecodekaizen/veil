import { chromium } from 'playwright';
const out = new URL('../shots/', import.meta.url).pathname;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
for (const run of ['c2', 'c3']) {
  await p.goto(`http://localhost:4173/?run=${run}`);
  await p.waitForSelector('video');
  await p.waitForTimeout(800);
  const h = run === 'c2' ? 'Mask check (post-gate)' : 'Timeline';
  await p.evaluate(h => [...document.querySelectorAll('h2')].find(e => e.textContent === h)?.scrollIntoView({ block: 'start' }), h);
  await p.waitForTimeout(300);
  await p.screenshot({ path: `${out}07-${run}-${h.split(' ')[0].toLowerCase()}.png` });
}
await b.close();
