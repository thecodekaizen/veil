import { chromium } from 'playwright';
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1280, height: 720 } });
await p.goto('http://localhost:8765/teleprompter.html'); await p.keyboard.press('ArrowRight'); await p.keyboard.press('ArrowRight');
await p.screenshot({ path: new URL('../shots/teleprompter.png', import.meta.url).pathname }); await b.close();
