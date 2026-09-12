import { chromium } from 'playwright';
const b = await chromium.launch();
const shots = [
  ['http://127.0.0.1:8766/', '/tmp/p-landing.png', 1440, 1000],
  ['http://127.0.0.1:8766/studio/', '/tmp/p-studio.png', 1440, 1000],
  ['http://127.0.0.1:8766/architecture.html', '/tmp/p-arch.png', 1440, 1100],
  ['http://127.0.0.1:8766/reports/spaced-retrieval-practice/EduEvidence_Report.html', '/tmp/p-report.png', 1440, 1000],
];
for (const [url, out, w, h] of shots) {
  const p = await b.newPage({ viewport: { width: w, height: h } });
  const errors = [];
  p.on('pageerror', e => errors.push(String(e).slice(0, 120)));
  const bad = [];
  p.on('response', r => { if (r.status() >= 400) bad.push(r.status() + ' ' + r.url().slice(0, 90)); });
  await p.goto(url, { waitUntil: 'networkidle', timeout: 45000 }).catch(e => errors.push('goto: ' + String(e).slice(0, 80)));
  await p.waitForTimeout(1200);
  await p.screenshot({ path: out });
  console.log(url.replace('http://127.0.0.1:8766', ''), '| errors:', errors.length ? errors.slice(0,2) : 'none', '| bad responses:', bad.length ? bad.slice(0,3) : 'none');
  await p.close();
}
await b.close();
