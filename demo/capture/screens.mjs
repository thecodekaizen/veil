// Phase 1 screenshots of the Veil demo UI (real post-gate c2 run) at 2560x1440 (1280x720 CSS @2x).
import { chromium } from 'playwright';
const out = new URL('../shots/', import.meta.url).pathname;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 2 });
await p.goto('http://localhost:4173/');
await p.waitForSelector('video');
await p.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 2));
const seek = async s => { await p.locator('input[type=range]').fill(String(s)); await p.waitForTimeout(600); };
await seek(6); await p.screenshot({ path: out + '01-top-t6.png' });
await seek(12); await p.screenshot({ path: out + '02-top-t12.png' });
for (const [i, h] of [['03', 'Timeline'], ['04', 'Findings'], ['05', 'Checks listed'], ['06', 'Limitations']]) {
  await p.getByRole('heading', { name: h }).scrollIntoViewIfNeeded();
  await p.evaluate(h => [...document.querySelectorAll('h2')].find(e => e.textContent === h).scrollIntoView({ block: 'start' }), h);
  await p.waitForTimeout(300); await p.screenshot({ path: `${out}${i}-${h.toLowerCase().replace(' ', '-')}.png` });
}
await b.close();
