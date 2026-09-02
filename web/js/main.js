import { state, $, $$, isDark, toast, esc } from './state.js';
import { api } from './api.js';
import { disposeAllCharts, resizeVisible } from './charts.js';
import { renderDashboard } from './dashboard.js';
import { renderVizHeader, renderForest, renderEffectDist, renderOutcome, renderGraph } from './viz.js';

function getPagesBaseMain() {
  const p = window.location.pathname || "/";
  if (p.startsWith("/eduevidence/")) return "/eduevidence/";
  return "/";
}
function isStaticHosting() {
  return window.location.hostname.includes("github.io") || window.location.hostname.includes("gitee.io");
}
function staticReportUrl(id, theme) {
  const base = getPagesBaseMain();
  const safeTheme = theme || "default";
  let filename = "EduEvidence_Report.html";
  if (safeTheme !== "default") filename = "EduEvidence_Report_" + safeTheme + ".html";
  return window.location.origin + base + "reports/" + encodeURIComponent(id) + "/" + filename;
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
  // On GitHub Pages (static) the /report endpoint does not exist; use pre-baked HTML under /reports/
  // Also fall back to static when live API is not reachable (detected via hostname).
  let src;
  if (isStaticHosting()) {
    src = staticReportUrl(p.id, state.currentReportTheme || "default");
  } else {
    src = "/report?id=" + encodeURIComponent(p.id) +
      "&theme=" + encodeURIComponent(state.currentReportTheme || "default");
  }
  const frame = $("#report-frame");
  frame.src = src;
  // If live /report 404s (e.g. static preview), retry once with static URL
  frame.onerror = null;
  let retried = false;
  frame.addEventListener("error", () => {
    if (!retried && !isStaticHosting()) {
      retried = true;
      frame.src = staticReportUrl(p.id, state.currentReportTheme || "default");
    }
  }, { once: true });
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

function landingCandidates() {
  const list = [];
  const hostname = window.location.hostname || "127.0.0.1";
  const origin = window.location.origin;
  const base = getPagesBaseMain();
  // GitHub Pages: landing lives at base ("/eduevidence/")
  if (isStaticHosting()) {
    list.push(origin + base);
    list.push(origin + base + "landing.html");
    if (document.referrer && document.referrer.includes("eduevidence")) list.push(document.referrer);
    return Array.from(new Set(list));
  }
  // 从落地页跳转过来时，document.referrer 就是最可靠的首页地址
  if (document.referrer && document.referrer.includes("landing.html")) list.push(document.referrer);
  // 同源优先（旧式单服务器部署时 dashboard/landing 同源）
  list.push(origin + "/landing.html");
  // 否则探测本机 8870-8879 静态托管
  for (let port = 8870; port <= 8879; port++) {
    list.push("http://" + hostname + ":" + port + "/landing.html");
  }
  return Array.from(new Set(list));
}

function wireLandingLinks() {
  const anchors = $$("#btn-back-to-landing, #topbar-to-landing");
  if (!anchors.length) return;
  const base = getPagesBaseMain();
  const fallback = isStaticHosting() ? (window.location.origin + base) : (window.location.origin + "/landing.html");
  (async () => {
    let target = null;
    for (const url of landingCandidates()) {
      try {
        const r = await fetch(url, { method: "GET", cache: "no-store" });
        if (r.ok) { target = url; break; }
      } catch (e) {
        /* 端口未监听 / 跨源被拒，试下一个 */
      }
    }
    anchors.forEach(a => { a.href = target || fallback; });
  })();
}

// 返回首页动画：纸面幕布自下而上收拢（与落地页进入控制台的向外热浪区分）。
// 动画结束后跳转到 wireLandingLinks() 解析出的落地页地址。
function initReturnHome() {
  const anchors = $$("#btn-back-to-landing, #topbar-to-landing");
  if (!anchors.length) return;
  let wave = document.getElementById("return-wave");
  if (!wave) {
    wave = document.createElement("div");
    wave.id = "return-wave";
    wave.setAttribute("aria-hidden", "true");
    document.body.appendChild(wave);
  }
  const base = getPagesBaseMain();
  const fallback = isStaticHosting() ? (window.location.origin + base) : (window.location.origin + "/landing.html");
  anchors.forEach(a => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      const raw = a.getAttribute("href");
      const target = (raw && raw !== "#") ? a.href : fallback;

      // 幕布初始在屏幕外，双重 rAF 确保首帧状态先渲染
      wave.style.transition = "none";
      wave.style.transform = "translateY(101%)";
      wave.style.opacity = "1";
      document.body.classList.add("leaving-page");
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          wave.style.transition = "transform 0.6s cubic-bezier(0.65, 0, 0.35, 1), opacity 0.25s ease 0.55s";
          wave.style.transform = "translateY(0)";
        });
      });
      setTimeout(() => { window.location.href = target; }, 620);
    });
  });
}

function init() {
  initSidebar();
  wireLandingLinks();
  initReturnHome();
  
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
