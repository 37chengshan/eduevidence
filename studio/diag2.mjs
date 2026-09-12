import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
await p.goto('http://127.0.0.1:8766/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1200);
// does the tour section render its gifs?
const tour = await p.evaluate(() => {
  const s = document.getElementById('tour-section');
  if (!s) return 'missing';
  const imgs = [...s.querySelectorAll('img')].map(i => ({ src: i.getAttribute('src'), w: i.naturalWidth, h: i.naturalHeight, complete: i.complete }));
  const r = s.getBoundingClientRect();
  return { box: [Math.round(r.width), Math.round(r.height)], imgs };
});
console.log('TOUR:', JSON.stringify(tour));
// jump to the tour section and shoot it
await p.evaluate(() => document.getElementById('tour-section')?.scrollIntoView({ block: 'start' }));
await p.waitForTimeout(1500);
await p.screenshot({ path: '/tmp/tour.png' });
// click the console button and see where we land
await p.evaluate(() => window.scrollTo(0, 0));
await p.waitForTimeout(400);
await p.click('#nav-launch-btn').catch(e => console.log('click err', String(e).slice(0,80)));
await p.waitForTimeout(2500);
console.log('AFTER CLICK url=', p.url());
const txt = await p.evaluate(() => (document.body.innerText || '').slice(0, 200));
console.log('BODY:', JSON.stringify(txt.slice(0, 160)));
await p.screenshot({ path: '/tmp/after-click.png' });
await b.close();
