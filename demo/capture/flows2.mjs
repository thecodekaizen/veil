// v2 captures of the redesigned Veil site (local `vite preview` of veil/web, real r1 run data), recorded in real
// Chrome (H.264 playback) at 2560x1440 with the page CSS-zoomed 2x. Output: out2/flow_<name>.webm + events_<name>.json.
import { chromium } from 'playwright';
import { mkdirSync, renameSync, writeFileSync } from 'node:fs';

const OUT = new URL('./out2/', import.meta.url).pathname;
const BASE = 'http://localhost:4173/';
mkdirSync(OUT, { recursive: true });

async function flow(name, path, steps) {
  const b = await chromium.launch({ channel: 'chrome' });
  const ctx = await b.newContext({ viewport: { width: 2560, height: 1440 }, recordVideo: { dir: OUT + 'tmp', size: { width: 2560, height: 1440 } } });
  const p = await ctx.newPage();
  const t0 = Date.now();
  const events = [];
  const box = async sel => { const r = await p.locator(sel).first().boundingBox(); return r ? [r.x, r.y, r.width, r.height].map(Math.round) : null; };
  const log = async (type, sel, extra = {}) => events.push({ t_ms: Date.now() - t0, type, sel, box: sel ? await box(sel) : null, ...extra });
  await p.goto(BASE + path);
  await p.addStyleTag({ content: 'html{zoom:2;scrollbar-width:none} ::-webkit-scrollbar{display:none} .reveal{opacity:1!important;transform:none!important}' });
  await p.waitForFunction(() => [...document.querySelectorAll('video')].every(v => v.readyState >= 3), null, { timeout: 30000 }).catch(() => {});
  await p.waitForTimeout(400);
  await log('ready', null);
  const scrollTo = async sel => { await p.evaluate(s => document.querySelector(s).scrollIntoView({ behavior: 'smooth', block: 'start' }), sel); await p.waitForTimeout(1000); };
  const glide = async (sel, ms = 700) => { const r = await p.locator(sel).first().boundingBox(); await p.mouse.move(r.x + r.width / 2, r.y + r.height / 2, { steps: Math.round(ms / 16) }); };
  const seek = async s => { await p.evaluate(t => document.querySelectorAll('.cmp-stage video').forEach(v => { v.currentTime = t; }), s); await p.waitForTimeout(300); };
  await steps({ p, log, scrollTo, glide, seek });
  await p.waitForTimeout(500);
  await log('end', null);
  const v = p.video();
  await ctx.close();
  renameSync(await v.path(), `${OUT}flow_${name}.webm`);
  writeFileSync(`${OUT}events_${name}.json`, JSON.stringify({ name, path, events }, null, 1));
  await b.close();
  console.log(name, events.length, 'events');
}

const drag = async (p, from, to, ms = 1400) => {
  const r = await p.locator('.cmp-stage').first().boundingBox();
  const y = r.y + r.height * 0.5;
  await p.mouse.move(r.x + r.width * from, y, { steps: 20 });
  await p.mouse.down();
  const n = Math.round(ms / 16);
  for (let i = 1; i <= n; i++) { const k = i / n; const e = 1 - Math.pow(1 - k, 3); await p.mouse.move(r.x + r.width * (from + (to - from) * e), y); await p.waitForTimeout(16); }
  await p.mouse.up();
};

await flow('hero', '#/', async ({ p, log }) => {
  await p.waitForTimeout(1200);
  await log('focus', '.hero-visual');
  await drag(p, 0.66, 0.30, 1600); await log('drag', '.cmp-stage');
  await p.waitForTimeout(900);
  await drag(p, 0.30, 0.80, 1800);
  await p.waitForTimeout(1500);
});

await flow('desk_play', '#/desk?run=c2', async ({ p, log, seek }) => {
  await seek(5); await p.waitForTimeout(500);
  await log('focus', '.cmp-stage');
  await p.click('.cmp-transport .icon-btn'); await log('click', '.cmp-transport .icon-btn');
  await p.waitForTimeout(9000);
});

await flow('desk_tracks', '#/desk?run=c2', async ({ p, log, glide, seek }) => {
  await seek(9); await p.waitForTimeout(400);
  await log('focus', '.desk-stage');
  await glide('.track-row >> nth=2', 900); await p.click('.track-row >> nth=2'); await log('click', '.track-row >> nth=2');
  await p.waitForTimeout(600);
  await p.click('.cmp-transport .icon-btn');
  await p.waitForTimeout(5000);
});

await flow('desk_checks', '#/desk?run=c2', async ({ p, log, scrollTo }) => {
  await p.waitForTimeout(800);
  await log('focus', '.desk-side');
  await p.waitForTimeout(2500);
  await scrollTo('#checks-h'); await log('focus', '#checks-h');
  await p.waitForTimeout(4000);
});

await flow('desk_mask', '#/desk?run=c2', async ({ p, log, scrollTo, glide }) => {
  await p.waitForTimeout(600);
  await scrollTo('#mask-h'); await log('focus', '#mask-h');
  await glide('.panel .row >> nth=0', 900); await log('hover', '.panel .row >> nth=0');
  await p.waitForTimeout(6000);
});

await flow('desk_voice', '#/desk?run=c3', async ({ p, log, seek, scrollTo }) => {
  await seek(9); await p.waitForTimeout(400);
  await scrollTo('.tracks'); await log('focus', '.tracks');
  await p.click('.cmp-transport .icon-btn').catch(() => {});
  await p.waitForTimeout(4500);
  await log('focus', '.audio');
  await p.waitForTimeout(4500);
});

await flow('desk_verdict', '#/desk?run=c2', async ({ p, log, glide }) => {
  await p.waitForTimeout(800);
  await log('focus', '.verdict');
  await p.waitForTimeout(3000);
  await glide('.filter >> nth=2', 900); await p.click('.filter >> nth=2'); await log('click', '.filter >> nth=2');
  await p.waitForTimeout(5000);
});

await flow('site_results', '#/', async ({ p, log }) => {
  await p.evaluate(() => { const y = document.querySelector('table.gate').getBoundingClientRect().top + window.scrollY - 120; window.scrollTo({ top: y, behavior: 'instant' }); }); await p.waitForTimeout(1000);
  await log('focus', 'table.gate');
  await p.waitForTimeout(7000);
});

await flow('site_ledger', '#/', async ({ p, log, scrollTo }) => {
  await scrollTo('#hood'); await log('focus', '.ledger');
  await p.waitForTimeout(6000);
});

await flow('site_cta', '#/', async ({ p, log, scrollTo, glide }) => {
  await scrollTo('.cta'); await log('focus', '.cta-inner');
  await glide('.cta .btn-primary', 900); await log('hover', '.cta .btn-primary');
  await p.waitForTimeout(3500);
});
