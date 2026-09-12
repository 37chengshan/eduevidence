import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
const bad = [];
p.on('response', r => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url().slice(0, 100)); });
const errs = [];
p.on('pageerror', e => errs.push(String(e).slice(0, 150)));
await p.goto('http://127.0.0.1:8769/landing.html', { waitUntil: 'networkidle', timeout: 45000 });
await p.waitForTimeout(1500);
await p.screenshot({ path: '/tmp/landing-top.png' });
// scroll through the whole page to catch layout breakage
const h = await p.evaluate(() => document.body.scrollHeight);
const shots = [];
for (let i = 1; i <= 5; i++) {
  await p.evaluate(y => window.scrollTo(0, y), Math.round(h * i / 6));
  await p.waitForTimeout(900);
  await p.screenshot({ path: `/tmp/landing-s${i}.png` });
  shots.push(Math.round(h * i / 6));
}
console.log(JSON.stringify({ height: h, scrolls: shots, errors: errs, badResponses: bad.slice(0, 5), secs: await p.evaluate(() => document.querySelectorAll('section').length) }));
await b.close();
