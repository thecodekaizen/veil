// Phase 5: record real Veil UI flows (served by `vite preview` on :4173, data = real post-gate runs).
// Output: out/flow_<name>.webm (2560x1440) + out/events_<name>.json (ms since recording start, target boxes in video px).
import { chromium } from 'playwright';
import { mkdirSync, renameSync, writeFileSync } from 'node:fs';

const OUT = new URL('./out/', import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });
const SCALE = 1; // boundingBox is already in viewport px (page is CSS-zoomed 2x)

async function flow(name, run, steps) {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 2560, height: 1440 }, deviceScaleFactor: 1,
    recordVideo: { dir: OUT + 'tmp', size: { width: 2560, height: 1440 } } });
  const p = await ctx.newPage();
  const t0 = Date.now();
  const events = [];
  const log = async (type, sel, extra = {}) => {
    let box = null;
    if (sel) {
      const r = await p.locator(sel).first().boundingBox();
      if (r) box = [r.x, r.y, r.width, r.height].map(v => Math.round(v * SCALE));
    }
    events.push({ t_ms: Date.now() - t0, type, sel, box, ...extra });
  };
  await p.addStyleTag({ content: '' }).catch(() => {});
  await p.goto(`http://localhost:4173/?run=${run}`);
  await p.addStyleTag({ content: '::-webkit-scrollbar{display:none} html{scrollbar-width:none;zoom:2}' });
  await p.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 3));
  await log('ready', null);
  const h2 = async text => {
    await p.evaluate(t => [...document.querySelectorAll('h2')].find(e => e.textContent === t)
      .scrollIntoView({ behavior: 'smooth', block: 'start' }), text);
    await p.waitForTimeout(900);
  };
  const glide = async (sel, ms = 700) => { // eased mouse path to the element centre
    const r = await p.locator(sel).first().boundingBox();
    await p.mouse.move(r.x + r.width / 2, r.y + r.height / 2, { steps: Math.round(ms / 16) });
  };
  await steps({ p, log, h2, glide });
  await p.waitForTimeout(500);
  await log('end', null);
  const v = p.video();
  await ctx.close();
  renameSync(await v.path(), `${OUT}flow_${name}.webm`);
  writeFileSync(`${OUT}events_${name}.json`, JSON.stringify({ name, run, events }, null, 1));
  await b.close();
  console.log(name, events.length, 'events');
}

const seek = (p, s) => p.locator('input[type=range]').fill(String(s));

await flow('overview', 'c2', async ({ p, log, glide }) => {
  await seek(p, 4); await p.waitForTimeout(800);
  await glide('button:has-text("Play both")'); await p.waitForTimeout(300);
  await log('click', 'button:has-text("Play both")'); await p.click('button:has-text("Play both")');
  await log('focus', '.videos');
  await p.waitForTimeout(10000);
  await log('click', 'button:has-text("Pause")'); await p.click('button:has-text("Pause")');
  await p.waitForTimeout(800);
});

await flow('scrub', 'c2', async ({ p, log }) => {
  await seek(p, 5); await p.waitForTimeout(600);
  const r = await p.locator('input[type=range]').boundingBox();
  const x = s => r.x + r.width * (s / 25), y = r.y + r.height / 2;
  await p.mouse.move(x(5), y, { steps: 20 }); await log('press', 'input[type=range]');
  await p.mouse.down();
  for (let s = 5; s <= 13; s += 0.1) { await p.mouse.move(x(s), y); await p.waitForTimeout(45); }
  await p.mouse.up(); await log('release', '.videos');
  await p.waitForTimeout(1500);
});

await flow('maskcheck', 'c2', async ({ p, log, h2, glide }) => {
  await p.waitForTimeout(600);
  await h2('Mask check (post-gate)'); await log('focus', 'tr.verify');
  await glide('tr.verify >> nth=0', 900); await log('hover', 'tr.verify >> nth=0');
  await p.waitForTimeout(3500);
  await glide('tr.verify >> nth=1', 600); await log('hover', 'tr.verify >> nth=1');
  await p.waitForTimeout(2500);
});

await flow('findings', 'c2', async ({ p, log, h2 }) => {
  await p.waitForTimeout(600);
  await h2('Findings'); await log('focus', 'h2:has-text("Findings") + table');
  await p.waitForTimeout(2500);
  await p.mouse.wheel(0, 380); await p.waitForTimeout(900);
  await log('focus', 'td.UNRESOLVED >> nth=0');
  await p.waitForTimeout(3000);
});

await flow('checks', 'c2', async ({ p, log, h2 }) => {
  await p.waitForTimeout(600);
  await h2('Checks listed'); await log('focus', 'h2:has-text("Checks listed") + table');
  await p.waitForTimeout(4000);
});

await flow('voice', 'c3', async ({ p, log, h2 }) => {
  await p.waitForTimeout(600);
  await h2('Timeline'); await log('focus', '.timeline');
  await p.waitForTimeout(2500);
  await log('focus', '.timeline + p');
  await p.waitForTimeout(3000);
  await h2('Findings'); await log('focus', 'h2:has-text("Findings") + table');
  await p.waitForTimeout(3000);
});
