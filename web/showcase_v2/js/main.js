/**
 * web/js/main.js — EduEvidence 5.0 Core Application Orchestrator
 */
import { state, $, $$, isDark, toast } from './state.js';
import { api } from './api.js';
import { disposeAllCharts, resizeVisible } from './charts.js';
import { renderDashboard } from './dashboard.js';
import { renderVizHeader, renderForest, renderEffectDist, renderOutcome, renderGraph } from './viz.js';
import { initLandingMotion, initWaveTransition } from './motion.js';
import { initDidSandbox, resizeDidChart } from './did_sandbox.js';
import { initWizard } from './wizard.js';

let activeSpace = "landing"; // "landing" | "console"
let activeConsoleTab = "dashboard"; // "dashboard" | "report" | "viz" | "did" | "wizard"

export function switchSpace(space, targetConsoleTab = null) {
  activeSpace = space;
  const landingEl = $("#view-landing");
  const consoleEl = $("#view-console");
  const floatingNav = $("#floating-landing-nav");

  if (space === "landing") {
    if (landingEl) {
      landingEl.style.display = "block";
      requestAnimationFrame(() => landingEl.classList.add("active-space"));
    }
    if (consoleEl) {
      consoleEl.classList.remove("active-space");
      setTimeout(() => { if (activeSpace === "landing") consoleEl.style.display = "none"; }, 300);
    }
    if (floatingNav) floatingNav.style.display = "flex";
    window.location.hash = "landing";
  } else {
    if (consoleEl) {
      consoleEl.style.display = "flex";
      requestAnimationFrame(() => consoleEl.classList.add("active-space"));
    }
    if (landingEl) {
      landingEl.classList.remove("active-space");
      setTimeout(() => { if (activeSpace === "console") landingEl.style.display = "none"; }, 300);
    }
    if (floatingNav) floatingNav.style.display = "none";
    if (targetConsoleTab) {
      switchConsoleTab(targetConsoleTab);
    } else {
      window.location.hash = "console/" + activeConsoleTab;
      requestAnimationFrame(() => resizeVisible());
    }
  }
}

export function switchConsoleTab(tab) {
  activeConsoleTab = tab;
  $$(".console-nav-item").forEach(b => {
    b.classList.toggle("active", b.dataset.view === tab);
  });
  $$(".console-tab-view").forEach(v => {
    if (v.id === "console-view-" + tab) {
      v.classList.add("active");
      setTimeout(() => v.style.opacity = 1, 10);
    } else {
      v.classList.remove("active");
      v.style.opacity = 0;
    }
  });

  window.location.hash = "console/" + tab;

  requestAnimationFrame(() => {
    resizeVisible();
    if (tab === "did") resizeDidChart();
    if (tab === "viz" && state.currentProject) loadViz(state.currentProject);
  });
}

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
  resizeDidChart();
}

function initSidebar() {
  let saved = null;
  try { saved = localStorage.getItem("eduevidence.sidebar"); } catch (e) {}
  if (saved === "collapsed") $("#console-sidebar")?.classList.add("collapsed");
  
  $("#console-collapse-btn")?.addEventListener("click", () => {
    const sb = $("#console-sidebar");
    if (!sb) return;
    const collapsed = sb.classList.toggle("collapsed");
    try { localStorage.setItem("eduevidence.sidebar", collapsed ? "collapsed" : "open"); } catch (e) {}
    requestAnimationFrame(() => resizeVisible());
  });
}

function renderReportList() {
  const list = $("#report-list");
  if (!list) return;
  const withReport = state.projects.filter(p => p.html_report_path);
  if (!withReport.length) {
    list.innerHTML = '<div class="empty-state">暂无已生成的 HTML 报告。</div>';
    return;
  }
  list.innerHTML = withReport.map(p => 
    `<div class="report-item" data-id="${p.id}">
      <div class="r-title serif-text">${p.title_zh || p.title}</div>
      <div class="r-meta">${p.verdict || "—"} · ${p.evidence_count || 0} 篇实证文献</div>
    </div>`
  ).join("");
  list.querySelectorAll(".report-item").forEach(el => {
    el.addEventListener("click", () => openReport(el.dataset.id));
  });
  if (withReport.length && !state.currentReport) openReport(withReport[0].id);
}

export function openReport(id, targetTheme = null) {
  state.currentReport = id;
  $$(".report-item").forEach(el => {
    el.classList.toggle("active", el.dataset.id === id);
  });
  const p = state.projects.find(x => x.id === id);
  if (targetTheme) state.currentReportTheme = targetTheme;
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
    `<span class="chip${state.currentReportTheme === t ? " active" : ""}" data-theme="${t}">
      ${t === "default" ? "默认 (烘焙)" : t}
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
  if (!sel) return;
  sel.innerHTML = state.projects.map(p => 
    `<option value="${p.id}">${p.title_zh || p.title}</option>`
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
    const kpiEl = $("#dash-kpis");
    if (kpiEl) kpiEl.innerHTML = `<div class="empty-state">加载失败: ${err.message}</div>`;
  });
}

function initHashRouting(waveCtrl) {
  const hash = window.location.hash.replace(/^#/, "");
  if (hash.startsWith("console")) {
    const parts = hash.split("/");
    const subTab = parts[1] || "dashboard";
    switchSpace("console", subTab);
  } else {
    switchSpace("landing");
  }

  // Bind Landing theme accordion buttons to launch report browser
  $$(".accordion-launch-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const theme = btn.dataset.theme;
      if (waveCtrl) {
        waveCtrl.triggerTransition(e, "console");
        setTimeout(() => {
          switchConsoleTab("report");
          openReport("ai-coding-assistant-evidence", theme);
        }, 460);
      } else {
        switchSpace("console", "report");
        openReport("ai-coding-assistant-evidence", theme);
      }
    });
  });
}

function init() {
  initSidebar();

  // Wave transition between Landing & Console
  const waveCtrl = initWaveTransition((targetSpace) => {
    switchSpace(targetSpace);
  });

  // Landing Page Scroll Motion
  initLandingMotion();

  // Console sub-modules
  initDidSandbox();
  initWizard();

  // Theme toggle: Light / Dark
  $$(".theme-btn").forEach(b => {
    b.addEventListener("click", () => setTheme(b.dataset.themeBtn));
  });

  // Console Tabs navigation
  $$(".console-nav-item").forEach(b => {
    b.addEventListener("click", () => switchConsoleTab(b.dataset.view));
  });

  // Forest plot subgroup filter chips
  $$(".forest-filter-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      $$(".forest-filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      if (state.vizPayload && state.vizPayload.forest) {
        renderForest(state.vizPayload.forest, chip.dataset.filter);
      }
    });
  });

  // Graph reload button
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

  // Drawer close button
  $("#drawer-close-btn")?.addEventListener("click", () => {
    $("#graph-node-drawer")?.classList.remove("open");
  });

  // Report frame load handler
  const frame = $("#report-frame");
  if (frame) {
    frame.addEventListener("load", () => {
      const l = $("#report-loading");
      if (l) l.classList.add("hidden");
    });
  }

  window.addEventListener("resize", () => {
    resizeVisible();
    resizeDidChart();
  });

  loadProjects();
  initHashRouting(waveCtrl);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
