#!/usr/bin/env node
/* check_mobile_layout.js — Browser-level layout gate for the five baked report
   themes. Zero dependencies (Node ≥21: global WebSocket + fetch).

   Measures each report at the given viewports in BOTH Visual Brief and Full
   Report views. Flags TRUE layout problems only:
     - page horizontal overflow (documentElement.scrollWidth > innerWidth)
     - visible .report-shell whose scrollWidth exceeds clientWidth
     - elements escaping the viewport that are NOT inside a scrollable
       ancestor and NOT inside an <svg> (those are legit: tables/actions scroll
       inside their own overflow-x:auto containers)
     - non-scrollable elements whose content is clipped (scrollW > clientW)
     - gallery reveal contract: every [data-lieflat] card in the visible shell
       must gain is-live once scrolled into view (scroll-reveal works).
   LocalStorage is cleared per URL so view state never leaks between themes.

   Usage:
     node check_mobile_layout.js --port 9230 [--widths 390,768,1280] <url>...
   Exit 0 = clean; 1 = violations; 42 = runtime failure.
 */
'use strict';

const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const CHROME = (() => {
  for (const p of [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium', '/usr/bin/chromium-browser',
  ]) if (fs.existsSync(p)) return p;
  return null;
})();

const args = process.argv.slice(2);
const PORT = Number((args.find(a => a.startsWith('--port=')) || '--port=9230').split('=')[1]);
const WIDTHS = (args.find(a => a.startsWith('--widths=')) || '--widths=390,768,1280')
  .split('=')[1].split(',').map(Number);
const HEIGHT = Number((args.find(a => a.startsWith('--height=')) || '--height=1200').split('=')[1]);
const urls = args.filter(a => a.startsWith('http') || a.startsWith('file://'));
if (!CHROME) { console.log('SKIP no chrome binary'); process.exit(0); }
if (!urls.length) { console.error('usage: node check_mobile_layout.js --port 9230 <url>...'); process.exit(2); }

let chrome = null, seq = 0;
const pending = new Map();

function cdpSend(ws, method, params = {}) {
  const id = ++seq;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

const MEASURE = `(() => {
  const vw = window.innerWidth;
  const chain = el => { const c = []; let n = el;
    while (n && n.tagName !== 'BODY' && c.length < 5) {
      c.push(n.tagName.toLowerCase() + (n.className ? '.' + String(typeof n.className==='object' ? n.className.baseVal||'' : n.className||'').trim().split(/\\s+/)[0] : ''));
      n = n.parentElement; }
    return c.join(' < '); };
  const inScroll = el => { let n = el.parentElement;
    while (n) { const s = getComputedStyle(n);
      if (s.overflowX === 'auto' || s.overflowX === 'scroll' || s.overflowY === 'auto' || s.overflowY === 'scroll') return true;
      if (n.tagName === 'BODY' || n.tagName === 'HTML') break;
      n = n.parentElement; }
    return false; };
  const inSvg = el => { let n = el.parentElement;
    while (n) { if (n.tagName && n.tagName.toLowerCase() === 'svg') return true; const p = n.parentElement; if (!p) break; n = p; }
    return false; };
  const visible = el => { const s = getComputedStyle(el);
    return s.display !== 'none' && s.visibility !== 'hidden' && el.getClientRects().length > 0; };
  const dsw = document.documentElement.scrollWidth;
  const escapes = [...document.querySelectorAll('body *')]
    .filter(visible)
    .filter(el => !inSvg(el))
    .filter(el => !inScroll(el))
    .map(el => { const r = el.getBoundingClientRect();
      return { chain: chain(el), right: Math.round(r.right), left: Math.round(r.left), w: Math.round(r.width) }; })
    .filter(o => o.right > vw + 2 || o.left < -2)
    .slice(0, 6);
  let shell = null;
  const shells = [...document.querySelectorAll('.report-shell')].filter(visible);
  if (shells.length) { const s = shells[0]; shell = { sw: s.scrollWidth, cw: s.clientWidth, full: getComputedStyle(s).overflowX }; }
  const clipped = [...document.querySelectorAll('body *')]
    .filter(visible).filter(el => !inSvg(el)).filter(el => !inScroll(el))
    .filter(el => el.scrollWidth > el.clientWidth + 3)
    .map(el => ({ chain: chain(el), sw: el.scrollWidth, cw: el.clientWidth }))
    .slice(0, 4);
  // gallery reveal contract: zh+en shells; only the visible shell matters
  const okReveal = (() => {
    const cards = [...document.querySelectorAll('[data-lieflat]')].filter(visible);
    return { cards: cards.length, live: cards.filter(c => c.classList.contains('is-live')).length };
  })();
  // Elements whose BOX extends past the shell's right edge — that is what
  // actually creates horizontal scroll overflow (scrollWidth can mislead).
  const shellCw = shells.length ? shells[0].clientWidth : vw;
  const shellLeft = shells.length ? shells[0].getBoundingClientRect().left : 0;
  const widest = shells.length
    ? [...shells[0].querySelectorAll('*')]
        .filter(visible)
        .filter(el => !inSvg(el)) // SVG 内部随 viewBox 缩放，不参与布局溢出
        .filter(el => !inScroll(el)) // 内部滚动容器已裁剪，不会撑破 shell
        .map(el => {
          const r = el.getBoundingClientRect();
          return { chain: chain(el), over: Math.round(r.right - shellLeft - shellCw),
                   w: Math.round(r.width),
                   hint: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 70) };
        })
        .filter(o => o.over > 4)
        .sort((a, b) => b.over - a.over)
        .slice(0, 8)
    : [];
  return { vw, dsw, overflow: dsw > vw + 4, shell, escapes, clipped, okReveal, widest };
})()`;

async function measure(ws, width, height, view) {
  await cdpSend(ws, 'Emulation.setDeviceMetricsOverride',
    { width, height, deviceScaleFactor: 1, mobile: width <= 768 });
  await cdpSend(ws, 'Page.enable').catch(() => {});
  // clear persisted view/lang state, force reload in the requested view
  await cdpSend(ws, 'Runtime.evaluate', {
    expression: `try{localStorage.removeItem('eduevidence-report-view');localStorage.setItem('eduevidence-report-view','${view}')}catch(e){}`,
  });
  await cdpSend(ws, 'Page.reload', { ignoreCache: true }).catch(() => {});
  await sleep(1200);
  // let the language switcher settle then scroll through the page so
  // IntersectionObserver reveal can fire for below-fold cards
  await cdpSend(ws, 'Runtime.evaluate', {
    expression: `(() => { const max = document.body.scrollHeight; let y = 0;
      const step = () => { window.scrollTo(0, y); y += Math.max(200, window.innerHeight * 0.7);
        if (y < max) { setTimeout(step, 90); } };
      step(); })()`,
  });
  await sleep(2400);
  await cdpSend(ws, 'Runtime.evaluate', { expression: 'window.scrollTo(0, 0)' });
  await sleep(300);
  const r = await cdpSend(ws, 'Runtime.evaluate', { expression: MEASURE, returnByValue: true });
  return r.result.value;
}

async function main() {
  chrome = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${fs.mkdtempSync(path.join(os.tmpdir(), 'edue-layout-'))}`,
    '--no-report-upload', 'about:blank',
  ], { stdio: ['ignore', 'ignore', 'ignore'] });
  let wsInfo = null;
  for (let i = 0; i < 60; i++) {
    try {
      const v = await (await fetch(`http://127.0.0.1:${PORT}/json/version`)).json();
      if (v.webSocketDebuggerUrl) { wsInfo = v; break; }
    } catch (e) { /* retry */ }
    await sleep(400);
  }
  if (!wsInfo) { console.error('FAIL chrome CDP not reachable'); process.exit(42); }

  const browserWs = new WebSocket(wsInfo.webSocketDebuggerUrl);
  await new Promise((res, rej) => { browserWs.onopen = res; browserWs.onerror = rej; });
  browserWs.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
    }
  };

  let violations = 0;
  for (const url of urls) {
    const target = await (await fetch(`http://127.0.0.1:${PORT}/json/new?about:blank`, { method: 'PUT' })).json();
    const pageWs = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((res, rej) => { pageWs.onopen = res; pageWs.onerror = rej; });
    pageWs.onmessage = ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) {
        const p = pending.get(m.id); pending.delete(m.id);
        m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
      }
    };
    await cdpSend(pageWs, 'Page.navigate', { url });
    await sleep(1000);
    for (const w of WIDTHS) {
      for (const view of ['brief', 'full']) {
        let m;
        try { m = await measure(pageWs, w, HEIGHT, view); }
        catch (e) { console.log(`err ${path.basename(new URL(url).pathname)} @${w} [${view}]: ${e.message}`); violations++; continue; }
        const label = `${path.basename(new URL(url).pathname)} @${w}px [${view}]`;
        const problems = [];
        if (m.overflow) problems.push(`page overflow scrollWidth=${m.dsw}>innerWidth=${m.vw}`);
        if (m.shell && m.shell.sw > m.shell.cw + 4) problems.push(`shell scrollW=${m.shell.sw}>clientW=${m.shell.cw}`);
        if (m.escapes.length) problems.push(`escapes(${m.escapes.length})`);
        if (m.clipped.length) problems.push(`clipped(${m.clipped.length})`);
        if (m.okReveal.cards > 0 && m.okReveal.live < m.okReveal.cards) {
          problems.push(`reveal ${m.okReveal.live}/${m.okReveal.cards} cards got is-live`);
        }
        if (problems.length) {
          violations++;
          console.log(`VIOLATION ${label}: ${problems.join(' | ')}`);
          for (const e of m.escapes.slice(0, 3)) console.log(`    esc <${e.chain}> right=${e.right} w=${e.w}`);
          for (const c of m.clipped.slice(0, 2)) console.log(`    clip <${c.chain}> sw=${c.sw} cw=${c.cw}`);
          for (const wd of m.widest || []) console.log(`    wide <${wd.chain}> over=${wd.over}px w=${wd.w} "${wd.hint}"`);
        } else {
          console.log(`ok ${label}: scrollW=${m.dsw} shell=${m.shell ? m.shell.sw + '/' + m.shell.cw : 'n/a'} reveal=${m.okReveal.live}/${m.okReveal.cards}`);
        }
      }
    }
    pageWs.close();
  }
  browserWs.close();
  try { chrome.kill(); } catch (e) {}
  if (violations) { console.error(`FAIL ${violations} layout violations`); process.exit(1); }
  console.log('ALL CLEAN');
  process.exit(0);
}

main().catch(e => { console.error('FATAL', e.message); try { chrome && chrome.kill(); } catch (_) {} process.exit(42); });