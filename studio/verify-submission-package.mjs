import { chromium } from 'playwright';

const BASE = 'http://127.0.0.1:8792';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const problems = [];
page.on('pageerror', e => problems.push('pageerror: ' + String(e).slice(0, 140)));
page.on('response', r => { if (r.status() >= 400) problems.push(r.status() + ' ' + r.url().slice(0, 110)); });

// the documented entry point in START-HERE.md
await page.goto(BASE + '/studio/', { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(2000);
const heading = await page.evaluate(() => (document.querySelector('h1') || {}).textContent || '');
console.log('studio heading:', JSON.stringify(heading.trim()));
if (!heading.trim()) problems.push('studio rendered no heading');

const catalog = await page.evaluate(async () => {
  // The local server exposes /api/studio/catalog; the static export writes
  // catalog.json. Try the live route first, then the static file name.
  for (const url of ['/api/studio/catalog', '/api/studio/catalog.json']) {
    const res = await fetch(url);
    if (res.ok) {
      const data = await res.json();
      return data.projects.map(p => ({
        id: p.id, action: p.decision && p.decision.action, confidence: p.decision && p.decision.confidence }));
    }
  }
  return null;
});
if (!catalog) problems.push('catalog endpoint failed from the package');
else for (const row of catalog) console.log('catalog:', row.id, '->', row.action, '/', row.confidence);

// The package serves reports through the Studio projection route, not a
// filesystem path (the catalog advertises absolute paths that a browser
// cannot open); verify the route the UI actually calls.
const cases = ['ai-coding-assistant-evidence', 'spaced-retrieval-practice', 'workplace-ai-assistant'];
const themes = ['claude', 'academic', 'datalab', 'datalab-dark', 'presentation'];
for (const c of cases) {
  for (const t of themes) {
    const url = BASE + '/api/studio/projects/example--' + c + '/report?theme=' + t;
    const res = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(e => null);
    if (!res || !res.ok()) problems.push('report ' + c + '/' + t + ' -> ' + (res ? res.status() : 'load error'));
  }
}
console.log('five themes x three cases served through the projection route');

await page.goto(BASE + '/studio/', { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/submission-studio.png' });
await browser.close();
console.log(problems.length ? 'PROBLEMS:\n - ' + problems.join('\n - ') : 'SUBMISSION PACKAGE OK');
process.exit(problems.length ? 1 : 0);
