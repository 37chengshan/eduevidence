import { chromium } from 'playwright';
const b = await chromium.launch();
for (const base of ['http://127.0.0.1:8766', 'http://127.0.0.1:8765']) {
  const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
  const errs = []; const bad = [];
  p.on('pageerror', e => errs.push(String(e).slice(0, 160)));
  p.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });
  p.on('response', r => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url().replace(base, '').slice(0, 80)); });
  await p.goto(base + '/studio/', { waitUntil: 'networkidle', timeout: 45000 }).catch(e => errs.push('goto ' + String(e).slice(0, 80)));
  await p.waitForTimeout(2000);
  await p.screenshot({ path: base.includes('8766') ? '/tmp/st-8766.png' : '/tmp/st-8765.png' });
  const info = await p.evaluate(() => ({ text: (document.body.innerText || '').slice(0, 400), links: document.querySelectorAll('a').length }));
  console.log(base, JSON.stringify({ errors: errs.slice(0, 4), bad: bad.slice(0, 6), info }));
  await p.close();
}
await b.close();
