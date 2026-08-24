import { state, $, $$, esc, countUp } from './state.js';
import { getChart, textColor, accent } from './charts.js';

export function renderDashboard() {
  const d = state.stats || {};
  const kpis = [
    { label: "纳入实证课题", value: d.total_projects || state.projects.length, sub: "动态扫描 result.json" },
    { label: "证据条目", value: d.total_evidence || 0, sub: "claim-level evidence" },
    { label: "量化效应量", value: d.total_effect_sizes || 0, sub: "Hedges g 效应值" },
    { label: "证据图谱节点", value: d.total_nodes || 0, sub: "SSOT 图谱实体" }
  ];
  $("#dash-kpis").innerHTML = kpis.map((k, i) => 
    `<div class="kpi stagger-item" style="--i:${i}">
      <div class="kpi-label">${esc(k.label)}</div>
      <div class="kpi-value" data-count="${k.value}">0</div>
      <div class="kpi-sub">${esc(k.sub)}</div>
    </div>`
  ).join("");
  
  $$(".kpi-value[data-count]").forEach(el => {
    countUp(el, parseInt(el.dataset.count, 10) || 0, 800);
  });
  
  renderDashboardCharts();
  renderProjCards();
  renderMatrix();
}

export function renderDashboardCharts() {
  renderVerdictChart();
  renderDirectionChart();
  renderCrossChart();
}

function renderVerdictChart() {
  const el = $("#chart-verdict");
  const c = getChart("verdict", el);
  if (!c) return;
  const counts = { adopt: 0, pilot: 0, reject: 0, insufficient: 0, other: 0 };
  state.projects.forEach(p => {
    const v = String(p.verdict || "").toLowerCase();
    if (v === "adopt") counts.adopt++;
    else if (v === "pilot") counts.pilot++;
    else if (v === "reject") counts.reject++;
    else if (v.includes("insufficient")) counts.insufficient++;
    else counts.other++;
  });
  c.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    grid: { left: 8, right: 8, top: 20, bottom: 20, containLabel: true },
    xAxis: { type: "category", data: ["PILOT", "ADOPT", "REJECT", "证据不足"], axisLabel: { color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } },
    yAxis: { type: "value", minInterval: 1, axisLabel: { color: textColor(), fontFamily: 'ui-sans-serif, system-ui, sans-serif' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } } },
    series: [{
      type: "bar",
      barWidth: '45%',
      data: [
        { value: counts.pilot, itemStyle: { color: '#D97757', borderRadius: [4,4,0,0] } },
        { value: counts.adopt, itemStyle: { color: "#10B981", borderRadius: [4,4,0,0] } },
        { value: counts.reject, itemStyle: { color: "#EF4444", borderRadius: [4,4,0,0] } },
        { value: counts.insufficient + counts.other, itemStyle: { color: "#A39E96", borderRadius: [4,4,0,0] } }
      ]
    }]
  }, true);
}

function renderDirectionChart() {
  const el = $("#chart-direction");
  const c = getChart("direction", el);
  if (!c) return;
  let s = 0, ct = 0, n = 0;
  state.projects.forEach(p => {
    const dc = p.direction_counts || {};
    s += dc.support || 0; ct += dc.contradict || 0; n += dc.neutral || 0;
  });
  c.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "item", formatter: "{b}: {c} ({d}%)" },
    series: [{
      type: "pie",
      radius: ["55%", "75%"],
      center: ["50%", "50%"],
      itemStyle: { borderColor: 'var(--bg-card)', borderWidth: 2 },
      label: { show: true, formatter: "{b}: {c}", color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' },
      data: [
        { value: s, name: "支持", itemStyle: { color: "#10B981" } },
        { value: ct, name: "反驳", itemStyle: { color: "#EF4444" } },
        { value: n, name: "中性", itemStyle: { color: "#A39E96" } }
      ]
    }]
  }, true);
}

function renderCrossChart() {
  const el = $("#chart-cross");
  const c = getChart("cross", el);
  if (!c) return;
  const labels = state.projects.map(p => p.id.replace(/^ai-/i, "").replace(/coding-assistant/, "coding"));
  c.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis" },
    legend: { data: ["证据条目", "数值效应量"], top: 0, textStyle: { color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } },
    grid: { left: 40, right: 20, top: 35, bottom: 44 },
    xAxis: { type: "category", data: labels, axisLabel: { color: textColor(), fontSize: 10, rotate: 25, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } },
    yAxis: { type: "value", minInterval: 1, axisLabel: { color: textColor(), fontFamily: 'ui-sans-serif, system-ui, sans-serif' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } } },
    series: [
      { name: "证据条目", type: "bar", barGap: '20%', data: state.projects.map(p => p.evidence_count || 0), itemStyle: { color: '#D97757', borderRadius: [3,3,0,0] } },
      { name: "数值效应量", type: "bar", data: state.projects.map(p => p.effect_count || 0), itemStyle: { color: "#10B981", borderRadius: [3,3,0,0] } }
    ]
  }, true);
}

function renderProjCards() {
  $("#proj-cards").innerHTML = state.projects.map((p, i) => {
    const dc = p.direction_counts || {};
    const conf = typeof p.confidence === "number" ? Math.round(p.confidence * 100) + "%" : (p.confidence || "—");
    let bars;
    if (p.mean_effect_size != null) {
      const v = p.mean_effect_size;
      bars = `<div class="mini-bars"><div class="mini-bar" style="height:${Math.max(8, Math.min(100, Math.abs(v) * 100))}%;${v >= 0 ? "" : " background:var(--red);"}" title="mean g=${v}"></div></div>`;
    } else {
      bars = `<div class="mini-bars">
        <div class="mini-bar" style="height:${Math.min(100, 20 + dc.support * 3)}%;background:var(--green);" title="支持 ${dc.support}"></div>
        <div class="mini-bar" style="height:${Math.min(100, 20 + dc.contradict * 3)}%;background:var(--red);" title="反驳 ${dc.contradict}"></div>
        <div class="mini-bar" style="height:${Math.min(100, 15 + dc.neutral * 3)}%;background:var(--text-muted);" title="中性 ${dc.neutral}"></div>
      </div>`;
    }
    return `<div class="proj-card stagger-item" style="--i:${i}">
      <div class="p-title serif-text">${esc(p.title_zh || p.title)}</div>
      <div class="proj-meta">
        <span class="stat">证据 ${p.evidence_count || 0}</span>
        <span class="stat">效应量 ${p.effect_count || 0}</span>
        <span class="stat">节点 ${p.node_count || 0}</span>${bars}
      </div>
      <div style="margin-top: auto; padding-top: 8px;">
        <span class="badge ${badgeClass(p.verdict)}">${esc(p.verdict || "—")}</span>
        <span style="font-size: 0.72rem; color: var(--text-muted); margin-left: 8px;">置信度 ${esc(conf)}</span>
      </div>
    </div>`;
  }).join("");
}

export function renderMatrix() {
  $("#dash-table tbody").innerHTML = state.projects.map(p => {
    const dc = p.direction_counts || {};
    const conf = typeof p.confidence === "number" ? Math.round(p.confidence * 100) + "%" : (p.confidence || "—");
    const g = p.mean_effect_size == null ? "—" : (p.mean_effect_size > 0 ? "+" : "") + p.mean_effect_size.toFixed(2);
    return `<tr>
      <td><b style="font-family: var(--font-mono); font-size: 0.75rem;">${esc(p.id)}</b></td>
      <td class="serif-text font-medium">${esc(p.title_zh || p.title)}</td>
      <td>${p.evidence_count || 0} 条</td>
      <td style="color: var(--text-muted);"><span style="color:var(--green)">${dc.support}</span> / <span style="color:var(--red)">${dc.contradict}</span> / ${dc.neutral}</td>
      <td style="font-family: var(--font-mono); font-weight: 500;">${esc(g)}</td>
      <td><span class="badge ${badgeClass(p.verdict)}">${esc(p.verdict || "—")}</span></td>
      <td>${esc(conf)}</td>
    </tr>`;
  }).join("");
}

export function badgeClass(v) {
  const s = String(v || "").toLowerCase();
  if (s === "adopt") return "adopt";
  if (s === "reject") return "reject";
  if (s === "pilot") return "pilot";
  return "insufficient";
}
