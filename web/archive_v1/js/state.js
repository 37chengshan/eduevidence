export const state = {
  theme: "light",
  projects: [],
  stats: {},
  labels: null,
  currentProject: null,
  currentReport: null,
  currentReportTheme: "default",
  vizPayload: null,
  dataCache: {},
  charts: {}
};

export let chartTheme = "light";
export function setChartTheme(t) { chartTheme = t; }

export function $(sel) { return document.querySelector(sel); }
export function $$(sel) { return document.querySelectorAll(sel); }

export function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

export function isDark() { return state.theme === "dark"; }

let toastTimer = null;
export function toast(msg, isError) {
  const el = $("#toast");
  if (!el) return;
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast"; }, 3600);
}

export function countUp(el, target, dur) {
  if (!el) return;
  let t0 = null;
  const d = dur || 600;
  function step(ts) {
    if (!t0) t0 = ts;
    const p = Math.min(1, (ts - t0) / d);
    el.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}
