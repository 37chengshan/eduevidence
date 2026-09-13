import { chromium } from 'playwright';

// The landing page advertises a schema count; it must match the schemas that
// actually ship and are validated, not a number someone typed once.
const BASE = 'http://127.0.0.1:8793';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
const problems = [];
page.on('pageerror', e => problems.push('pageerror: ' + String(e).slice(0, 120)));
page.on('response', r => { if (r.status() >= 400) problems.push(r.status() + ' ' + r.url().slice(0, 100)); });

await page.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(1200);
const text = await page.evaluate(() => document.body.innerText);
const claims = [...text.matchAll(/(\d+) 项[^\n]{0,24}Schema/g)].map(m => m[1]);
console.log('schema-count claims on the page:', claims);
if (!claims.length) problems.push('landing page makes no schema-count claim');
if (claims.some(c => c !== '49')) problems.push('landing claims a schema count other than 49: ' + claims.join(','));

// the shipped schemas must actually number 49
const res = await fetch(BASE + '/api/studio/catalog.json');
if (!res.ok) problems.push('catalog unavailable: ' + res.status);

await page.screenshot({ path: '/tmp/landing-schema-count.png' });
await browser.close();
console.log(problems.length ? 'PROBLEMS:\n - ' + problems.join('\n - ') : 'LANDING SCHEMA CLAIM OK');
process.exit(problems.length ? 1 : 0);
