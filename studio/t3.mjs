import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
// WITHOUT interpolate-size: does width animate from fit-content to 100%?
await p.setContent(`<style>
.wrap{width:200px;display:grid}
#x{display:flex;width:fit-content;transition:width 300ms linear;background:#eee}
</style><div class=wrap><a id=x href=#><span>abc</span></a></div>`);
const out = await p.evaluate(async () => {
  const el = document.getElementById('x');
  const w0 = el.getBoundingClientRect().width;
  el.style.width = '100%';
  const s = [];
  const t0 = performance.now();
  await new Promise(r => { function f(){ s.push(+el.getBoundingClientRect().width.toFixed(1)); if (performance.now()-t0 < 330) requestAnimationFrame(f); else r(); } requestAnimationFrame(f); });
  return { w0: +w0.toFixed(1), samples: s.slice(0, 8) };
});
console.log('WITHOUT interpolate-size:', JSON.stringify(out));
await b.close();
