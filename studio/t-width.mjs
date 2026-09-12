import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.setContent(`<style>
.wrap{width:200px;display:flex}
#x{display:flex;align-items:center;gap:6px;width:fit-content;transition:width 400ms linear;background:#eee}
</style><div class=wrap><a id=x href=#><span>abc</span></a></div>`);
const res = await p.evaluate(async () => {
  const x = document.getElementById('x');
  const w0 = x.getBoundingClientRect().width;
  x.style.width = '100%';
  const samples = [];
  const t0 = performance.now();
  await new Promise(r => {
    function step() {
      samples.push([Math.round(performance.now()-t0), +x.getBoundingClientRect().width.toFixed(1)]);
      if (performance.now()-t0 < 450) requestAnimationFrame(step); else r();
    }
    requestAnimationFrame(step);
  });
  return { w0, samples: samples.filter((_, i) => i % 4 === 0) };
});
console.log(JSON.stringify(res));
// also test flex-grow transition
const res2 = await p.evaluate(async () => {
  const wrap = document.querySelector('.wrap');
  wrap.innerHTML = '<span id=y style="flex:0 1 auto;background:#ddd;transition:flex-grow 400ms linear">abc</span>';
  const y = document.getElementById('y');
  const w0 = y.getBoundingClientRect().width;
  y.style.flexGrow = '1';
  const samples = [];
  const t0 = performance.now();
  await new Promise(r => {
    function step(){ samples.push([Math.round(performance.now()-t0), +y.getBoundingClientRect().width.toFixed(1)]); if (performance.now()-t0 < 450) requestAnimationFrame(step); else r(); }
    requestAnimationFrame(step);
  });
  return { w0, samples: samples.filter((_, i) => i % 4 === 0) };
});
console.log(JSON.stringify(res2));
await b.close();
