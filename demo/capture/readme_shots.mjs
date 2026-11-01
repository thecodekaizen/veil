// README screenshots of the Veil web UI (real post-gate runs c2, c3) at 2x density.
import { chromium } from 'playwright';
const OUT = new URL('../../docs/media/', import.meta.url).pathname;
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1180, height: 760 }, deviceScaleFactor: 2 });
const go = async run => {
  await p.goto(`http://localhost:4173/?run=${run}`);
  await p.addStyleTag({ content: '::-webkit-scrollbar{display:none}' });
  await p.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 3));
};
const shotEl = async (sel, file, pad = 12) => {
  const r = await p.locator(sel).first().boundingBox();
  await p.screenshot({ path: OUT + file, fullPage: true, clip: { x: r.x - pad, y: r.y - pad, width: r.width + 2 * pad, height: r.height + 2 * pad } });
};
const section = async (h, file, rows = 99) => {
  const box = await p.evaluate(([h, rows]) => {
    const h2 = [...document.querySelectorAll('h2')].find(e => e.textContent === h);
    const t = h2.nextElementSibling.tagName === 'P' ? h2.nextElementSibling.nextElementSibling : h2.nextElementSibling;
    const trs = [...t.querySelectorAll('tr')].slice(0, rows);
    const a = h2.getBoundingClientRect(), z = trs[trs.length - 1].getBoundingClientRect();
    return { x: a.x - 14, y: a.y + scrollY - 10, width: t.getBoundingClientRect().width + 28, height: z.bottom - a.top + 20 };
  }, [h, rows]);
  await p.screenshot({ path: OUT + file, fullPage: true, clip: box });
};
await go('c2');
await p.locator('input[type=range]').fill('12'); await p.waitForTimeout(900);
await shotEl('.videos', 'hero-c2.png', 6);
await section('Mask check (post-gate)', 'mask-check.png');
await section('Findings', 'findings-c2.png', 12);
await section('Checks listed', 'checks.png');
await go('c3');
await p.locator('input[type=range]').fill('11'); await p.waitForTimeout(900);
const tl = await p.evaluate(() => {
  const a = document.querySelector('.timeline').getBoundingClientRect(), z = document.querySelector('.timeline + p').getBoundingClientRect();
  return { x: a.x - 14, y: a.y + scrollY - 50, width: a.width + 28, height: z.bottom - a.top + 64 };
});
await p.screenshot({ path: OUT + 'voice-c3.png', fullPage: true, clip: tl });
await b.close();
console.log('ok');
