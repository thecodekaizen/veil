// README landing screenshot of the live site with the Natural export visible (divider pulled left).
import { chromium } from 'playwright';
const OUT = new URL('../../docs/media/', import.meta.url).pathname;
const b = await chromium.launch({ channel: 'chrome' });
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await p.goto('https://thecodekaizen.github.io/veil/');
await p.waitForFunction(() => document.querySelector('.cmp-stage video')?.readyState >= 3, null, { timeout: 60000 });
await p.evaluate(() => document.querySelectorAll('.reveal').forEach(e => e.classList.add('in')));
await p.evaluate(() => document.querySelectorAll('.cmp-stage video').forEach(v => { v.pause(); v.currentTime = 9; }));
await p.waitForFunction(() => [...document.querySelectorAll('.cmp-stage video')].every(v => !v.seeking && v.readyState >= 3));
const st = await p.locator('.cmp-stage').boundingBox();
await p.mouse.move(st.x + st.width * 0.66, st.y + st.height / 2);
await p.mouse.down(); await p.mouse.move(st.x + st.width * 0.12, st.y + st.height / 2, { steps: 12 }); await p.mouse.up();
await p.mouse.move(5, 5);
await p.waitForTimeout(800);
await p.screenshot({ path: OUT + 'site-landing-natural.png' });
console.log(await p.evaluate(() => document.querySelector('.seg .on')?.textContent));
await b.close();
