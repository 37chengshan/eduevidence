import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:8791';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const problems = [];
page.on('pageerror', e => problems.push('pageerror: ' + String(e).slice(0, 120)));
page.on('response', r => { if (r.status() >= 400) problems.push(r.status() + ' ' + r.url().slice(0, 100)); });

// 1) landing page carries both decision ends
await page.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 45000 });
const landing = await page.evaluate(() => document.body.innerText);
console.log('landing: PILOT mention =', landing.includes('PILOT'), '| ADOPT mention =', landing.includes('ADOPT'));

// 2) studio catalog shows the three cases with their actions
await page.goto(BASE + '/studio/', { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(1500);
const catalog = await page.evaluate(async () => {
  const res = await fetch('/api/studio/catalog.json');
  const data = await res.json();
  return data.projects.map(p => ({ id: p.id, action: p.decision && p.decision.action, confidence: p.decision && p.decision.confidence }));
});
for (const row of catalog) {
  console.log('catalog:', row.id, '->', row.action, '/', row.confidence);
}
const adopt = catalog.find(c => c.action === 'adopt');
if (!adopt) problems.push('no ADOPT case in the studio catalog');
const pilot = catalog.filter(c => c.action === 'pilot');
if (pilot.length !== 2) problems.push('expected 2 pilot cases, found ' + pilot.length);

// 3) the ADOPT case report actually renders it
await page.goto(BASE + '/reports/spaced-retrieval-practice/EduEvidence_Report.html',
                { waitUntil: 'networkidle', timeout: 45000 });
const reportText = await page.evaluate(() => document.body.innerText);
console.log('report: 全面采用 =', reportText.includes('全面采用'), '| 试点验证 =', reportText.includes('试点验证'));
if (!reportText.includes('全面采用')) problems.push('ADOPT report does not show the 采用 label');

// 4) legacy console data endpoint the landing links to
await page.goto(BASE + '/api/projects/spaced-retrieval-practice/viz.json', { timeout: 30000 });
const viz = JSON.parse(await page.evaluate(() => document.body.innerText));
console.log('viz:', viz.verdict, '/', viz.confidence);
if (viz.verdict !== 'adopt') problems.push('viz verdict is ' + viz.verdict);

await page.screenshot({ path: '/tmp/verify-decision.png' });
await browser.close();
console.log(problems.length ? 'PROBLEMS:\n - ' + problems.join('\n - ') : 'ALL CHECKS PASSED');
process.exit(problems.length ? 1 : 0);
