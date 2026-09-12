import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 950 } });
// Keep the page alive: drop the 480ms navigation timer so we can watch the wave.
await p.addInitScript(() => {
  const orig = window.setTimeout;
  window.setTimeout = function (fn, ms, ...rest) {
    if (ms === 480) { window.__droppedNav = true; return 0; }
    return orig.call(this, fn, ms, ...rest);
  };
});
await p.goto('http://127.0.0.1:8766/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1200);
const res = await p.evaluate(async () => {
  const btn = document.getElementById('nav-launch-btn');
  btn.click();
  const ov = document.getElementById('landing-wave-overlay');
  if (!ov) return { error: 'no overlay' };
  const samples = [];
  const t0 = performance.now();
  await new Promise(r => {
    function step() {
      const cs = getComputedStyle(ov);
      samples.push([Math.round(performance.now() - t0), cs.clipPath.slice(0, 46), cs.opacity, cs.transitionProperty.slice(0, 30)]);
      if (performance.now() - t0 < 620) requestAnimationFrame(step); else r();
    }
    requestAnimationFrame(step);
  });
  return { dropped: window.__droppedNav, samples: samples.filter((_, i) => i % 6 === 0) };
});
console.log(JSON.stringify(res, null, 1));
await b.close();
