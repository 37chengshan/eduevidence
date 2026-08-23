import { state, $, $$, isDark, toast, esc } from './state.js';
import { api } from './api.js';
import { disposeAllCharts, resizeVisible } from './charts.js';
import { renderDashboard } from './dashboard.js';
import { renderVizHeader, renderForest, renderEffectDist, renderOutcome, renderGraph } from './viz.js';

function setTheme(theme) {
  const prev = state.theme;
  state.theme = theme;
  document.documentElement.setAttribute("data-theme", theme);
  $$(".theme-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.themeBtn === theme);
  });
  if (prev !== theme) rebuildCharts();
}

function rebuildCharts() {
  disposeAllCharts();
  if (state.projects.length) renderDashboard();
  if (state.currentProject) loadViz(state.currentProject);
  resizeVisible();
}

function switchView(view) {
  $$(".nav-item").forEach(b => {
    b.classList.toggle("active", b.dataset.view === view);
  });
  $$(".view").forEach(v => {
    if (v.id === "view-" + view) {
      v.classList.add("active");
      // slight delay for animation triggering
      setTimeout(() => v.style.opacity = 1, 10);
    } else {
      v.classList.remove("active");
      v.style.opacity = 0;
    }
  });
  requestAnimationFrame(() => {
    resizeVisible();
    if (view === "viz" && state.currentProject) loadViz(state.currentProject);
  });
}
window.switchView = switchView;

function initSidebar() {
  let saved = null;
  try { saved = localStorage.getItem("eduevidence.sidebar"); } catch (e) {}
  if (saved === "collapsed") $("#sidebar").classList.add("collapsed");
  $("#collapse-btn").addEventListener("click", () => {
    const sb = $("#sidebar");
    const collapsed = sb.classList.toggle("collapsed");
    try { localStorage.setItem("eduevidence.sidebar", collapsed ? "collapsed" : "open"); } catch (e) {}
    requestAnimationFrame(() => resizeVisible());
  });
}

function renderReportList() {
  const list = $("#report-list");
  const withReport = state.projects.filter(p => p.html_report_path);
  if (!withReport.length) {
    list.innerHTML = '<div class="empty-state">暂无已生成的 HTML 报告。</div>';
    return;
  }
  list.innerHTML = withReport.map(p => 
    `<div class="report-item" data-id="${esc(p.id)}">
      <div class="r-title serif-text">${esc(p.title_zh || p.title)}</div>
      <div class="r-meta">${esc(p.verdict || "—")} · ${esc(p.evidence_count || 0)} 条证据</div>
    </div>`
  ).join("");
  list.querySelectorAll(".report-item").forEach(el => {
    el.addEventListener("click", () => openReport(el.dataset.id));
  });
  if (withReport.length && !state.currentReport) openReport(withReport[0].id);
}

function openReport(id) {
  state.currentReport = id;
  $$(".report-item").forEach(el => {
    el.classList.toggle("active", el.dataset.id === id);
  });
  const p = state.projects.find(x => x.id === id);
  renderReportVariants(p);
  refreshReportFrame();
}

function renderReportVariants(p) {
  const titleEl = $("#report-current-title");
  const chipsEl = $("#report-variant-chips");
  if (!titleEl || !chipsEl || !p) return;
  titleEl.textContent = p.title_zh || p.title || p.id;
  const variants = (p.report_variants || []).map(v => v.theme);
  const all = ["default"].concat(variants);
  if (!all.includes(state.currentReportTheme)) state.currentReportTheme = "default";
  chipsEl.innerHTML = all.map(t => 
    `<span class="chip${state.currentReportTheme === t ? " active" : ""}" data-theme="${esc(t)}">
      ${t === "default" ? "默认" : esc(t)}
    </span>`
  ).join("");
  chipsEl.querySelectorAll(".chip").forEach(el => {
    el.addEventListener("click", () => {
      state.currentReportTheme = el.dataset.theme;
      renderReportVariants(p);
      refreshReportFrame();
    });
  });
}

function refreshReportFrame() {
  const p = state.projects.find(x => x.id === state.currentReport);
  if (!p || !p.html_report_path) return;
  const loading = $("#report-loading");
  if (loading) loading.classList.remove("hidden");
  $("#report-frame").src = "/report?id=" + encodeURIComponent(p.id) +
    "&theme=" + encodeURIComponent(state.currentReportTheme || "default");
}

function renderVizSelect() {
  const sel = $("#viz-project-select");
  sel.innerHTML = state.projects.map(p => 
    `<option value="${esc(p.id)}">${esc(p.title_zh || p.title)}</option>`
  ).join("");
  if (!state.currentProject && state.projects.length) state.currentProject = state.projects[0].id;
  sel.value = state.currentProject;
  sel.addEventListener("change", () => loadViz(sel.value));
}

function loadViz(id) {
  state.currentProject = id;
  api("/api/projects/" + encodeURIComponent(id) + "/viz").then(d => {
    state.vizPayload = d;
    renderVizHeader(d);
    renderForest(d.forest || []);
    renderEffectDist(d);
    renderOutcome(d);
    renderGraph(d.graph || null);
  }).catch(err => {
    toast("可视化数据加载失败: " + err.message, true);
  });
}

function loadProjects() {
  Promise.all([api("/api/projects"), api("/api/labels")]).then(pair => {
    const d = pair[0];
    state.projects = d.projects || [];
    state.stats = d.stats || {};
    state.labels = pair[1];
    renderDashboard();
    renderReportList();
    renderVizSelect();
    if (state.projects.length) loadViz(state.currentProject);
  }).catch(err => {
    toast("加载失败: " + err.message, true);
    $("#dash-kpis").innerHTML = `<div class="empty-state">加载失败: ${esc(err.message)}</div>`;
  });
}

function init() {
  initSidebar();
  
  // Theme toggle: simplified to Light / Dark
  $$(".theme-btn").forEach(b => {
    b.addEventListener("click", () => setTheme(b.dataset.themeBtn));
  });
  
  // Try to respect OS preference if not set
  if (!document.documentElement.getAttribute("data-theme") || document.documentElement.getAttribute("data-theme") === "claude") {
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    setTheme(prefersDark ? 'dark' : 'light');
  }

  $$(".nav-item[data-view]").forEach(b => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });

  const reloadBtn = $("#graph-reload");
  if (reloadBtn) {
    reloadBtn.addEventListener("click", () => {
      if (state.vizPayload) {
        if (state.charts.graph) {
          state.charts.graph.dispose();
          delete state.charts.graph;
        }
        renderGraph(state.vizPayload.graph || null);
      }
    });
  }

  const frame = $("#report-frame");
  if (frame) {
    frame.addEventListener("load", () => {
      const l = $("#report-loading");
      if (l) l.classList.add("hidden");
    });
  }

  window.addEventListener("resize", () => resizeVisible());
  loadProjects();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
