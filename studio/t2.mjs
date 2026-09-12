import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
console.log('chrome', b.version());
await p.setContent(`<style>
.interp { interpolate-size: allow-keywords; }
.wrap{width:200px;display:grid}
#x{display:flex;align-items:center;gap:6px;width:fit-content;transition:width 400ms linear;background:#eee}
#y{display:flex;align-items:center;gap:6px;transition:width 400ms linear;background:#ddd}
</style><div class=wrap><a id=x class=interp href=#><span>abc</span></a><a id=y class=interp href=#><span>abcdef</span></a></div>`);
const out = await p.evaluate(async () => {
  const run = async (id) => {
    const el = document.getElementById(id);
    const w0 = el.getBoundingClientRect().width;
    el.style.width = '100%';
    const samples = [];
    const t0 = performance.now();
    await new Promise(r => { function s(){ samples.push(+el.getBoundingClientRect().width.toFixed(1)); if (performance.now()-t0 < 430) requestAnimationFrame(s); else r(); } requestAnimationFrame(s); });
    return { w0: +w0.toFixed(1), trail: samples.slice(0, 12) };
  };
  return { x: await run('x'), y: await run('y') };
});
console.log(JSON.stringify(out));
await b.close();
