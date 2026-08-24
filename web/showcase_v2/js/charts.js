import { state, isDark, chartTheme, setChartTheme } from './state.js';

export function getChart(id, el) {
  if (!el || typeof echarts === "undefined") return null;
  let c = state.charts[id];
  if (c && chartTheme === state.theme) return c;
  if (c && c.dispose) c.dispose();
  setChartTheme(state.theme);
  c = echarts.init(el, isDark() ? "dark" : null);
  state.charts[id] = c;
  return c;
}

export function disposeAllCharts() {
  Object.keys(state.charts).forEach(k => {
    try { state.charts[k].dispose(); } catch (e) {}
    delete state.charts[k];
  });
}

export function textColor() { return isDark() ? "#E8E5E1" : "#2C2825"; }
export function accent() { return isDark() ? "#D97757" : "#D97757"; }

export function resizeVisible() {
  const active = document.querySelector(".view.active");
  Object.keys(state.charts).forEach(k => {
    const host = state.charts[k].getDom ? state.charts[k].getDom() : null;
    if (host && active && active.contains(host)) {
      try { state.charts[k].resize(); } catch (e) {}
    }
  });
}
