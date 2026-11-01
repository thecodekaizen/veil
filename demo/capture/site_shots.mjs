// Visual QA of the redesigned site: landing (desktop + mobile, full page) and desk (desktop + mobile).
import { chromium } from 'playwright';
const OUT = '/tmp/site-qa/';
import { mkdirSync } from 'node:fs'; mkdirSync(OUT, { recursive: true });
const b = await chromium.launch();
const errors = [];
for (const [name, w, h] of [['desktop', 1440, 900], ['mobile', 390, 844]]) {
  const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  p.on('console', m => m.type() === 'error' && errors.push(`${name}: ${m.text()}`));
  p.on('pageerror', e => errors.push(`${name}: ${e.message}`));
  await p.goto('http://localhost:4173/#/');
  await p.waitForTimeout(2500);
  await p.evaluate(() => document.querySelectorAll('.reveal').forEach(e => e.classList.add('in')));
  await p.screenshot({ path: `${OUT}landing-${name}-fold.png` });
  await p.screenshot({ path: `${OUT}landing-${name}-full.png`, fullPage: true });
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log(name, 'landing horizontal overflow px:', overflow);
  await p.goto('http://localhost:4173/#/desk?run=c2'); await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}desk-${name}-fold.png` });
  await p.screenshot({ path: `${OUT}desk-${name}-full.png`, fullPage: true });
  console.log(name, 'desk overflow px:', await p.evaluate(() => document.documentElement.scrollWidth - window.innerWidth));
  await p.goto('http://localhost:4173/#/desk?run=c3'); await p.waitForTimeout(2000);
  await p.screenshot({ path: `${OUT}desk3-${name}-fold.png` });
  await p.close();
}
console.log('errors:', errors.length ? errors : 'none');
await b.close();
