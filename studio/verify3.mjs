import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
// 1) landing -> console click lands in the Studio (not back on landing)
await p.goto('http://127.0.0.1:8766/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1500);
await p.click('#nav-launch-btn');
await p.waitForTimeout(2600);
console.log('CLICK -> url:', p.url());
const t = await p.evaluate(() => (document.body.innerText || '').slice(0, 60).replace(/\n+/g, ' '));
console.log('       body starts:', JSON.stringify(t));
await p.screenshot({ path: '/tmp/console-landed.png' });
// 2) sidebar animation: click a nav row and sample the width glide
const glide = await p.evaluate(async () => {
  const rows = [...document.querySelectorAll('.sidebar nav > a')];
  const target = rows.find(r => !r.getAttribute('aria-current'));
  const before = +target.getBoundingClientRect().width.toFixed(1);
  const samples = [];
  target.click();
  const t0 = performance.now();
  await new Promise(r => { function f(){ samples.push(+target.getBoundingClientRect().width.toFixed(1)); if (performance.now()-t0 < 430) requestAnimationFrame(f); else r(); } requestAnimationFrame(f); });
  return { label: target.textContent.trim(), before, trail: samples.filter((_, i) => i % 5 === 0) };
});
console.log('SIDEBAR GLIDE:', JSON.stringify(glide));
await b.close();
