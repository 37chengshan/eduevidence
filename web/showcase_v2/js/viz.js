/**
 * web/js/viz.js — Enhanced ECharts Forest Plot & SSOT Evidence Graph Visualizer
 */
import { state, $, esc } from './state.js';
import { getChart, textColor, accent } from './charts.js';

export function renderVizHeader(d) {
  const conf = typeof d.confidence === "number" ? Math.round(d.confidence * 100) + "%" : (d.confidence || "—");
  const dc = d.direction_counts || {};
  $("#viz-kpis").innerHTML =
    `<span class="viz-kpi">裁决 <span style="color:var(--brand-orange); font-weight:700;">${esc(d.verdict || "—")}</span></span>` +
    `<span class="viz-kpi">置信度 <span style="color:var(--text-primary); font-weight:600;">${esc(conf)}</span></span>` +
    `<span class="viz-kpi"><span style="color:var(--emerald)">支持 ${dc.support || 0}</span> / <span style="color:var(--crimson)">反驳 ${dc.contradict || 0}</span> / 中性 ${dc.neutral || 0}</span>` +
    `<span class="viz-kpi">森林图文献 <span style="color:var(--text-primary); font-weight:600;">${(d.forest || []).length}</span> 篇</span>`;
  $("#viz-question").textContent = d.question || d.title || "";
}

function calculateDerSimonianLaird(items) {
  let num = 0, den = 0;
  const valid = [];
  
  items.forEach(f => {
    const g = Number(f.effect_size);
    if (!isFinite(g)) return;
    const ci = (Number(f.ci_upper) - Number(f.ci_lower)) || 0;
    const se = ci > 0 ? ci / (2 * 1.96) : 0.25;
    const w = 1 / (se * se);
    valid.push({ g, se, w, f });
    num += w * g;
    den += w;
  });

  if (!valid.length || den === 0) return { mean: 0, ciLo: 0, ciHi: 0, i2: 0, q: 0 };

  const fixedMean = num / den;

  // Cochran's Q
  let Q = 0;
  valid.forEach(v => {
    Q += v.w * Math.pow(v.g - fixedMean, 2);
  });

  const k = valid.length;
  const df = Math.max(1, k - 1);
  const I2 = Math.max(0, Math.min(100, ((Q - df) / Math.max(1, Q)) * 100));

  // Between-study variance tau^2
  let sumW2 = 0;
  valid.forEach(v => { sumW2 += v.w * v.w; });
  const C = den - (sumW2 / den);
  const tau2 = C > 0 ? Math.max(0, (Q - df) / C) : 0;

  // Random effects pooled mean
  let reNum = 0, reDen = 0;
  valid.forEach(v => {
    const reW = 1 / (v.se * v.se + tau2);
    reNum += reW * v.g;
    reDen += reW;
  });

  const randomMean = reDen > 0 ? reNum / reDen : fixedMean;
  const randomSE = reDen > 0 ? Math.sqrt(1 / reDen) : 0.1;

  return {
    mean: Number(randomMean.toFixed(3)),
    ciLo: Number((randomMean - 1.96 * randomSE).toFixed(3)),
    ciHi: Number((randomMean + 1.96 * randomSE).toFixed(3)),
    i2: Number(I2.toFixed(1)),
    q: Number(Q.toFixed(2)),
    k: k
  };
}

export function renderForest(forest, activeFilter = "all") {
  const el = $("#forest-plot");
  const c = getChart("forest", el);
  if (!c) return;
  if (!forest.length) {
    el.innerHTML = '<div class="empty-state">该课题暂无可量化的森林图数据 (result.json → forest_plot_data)。</div>';
    return;
  }

  // Filter if needed
  let filtered = forest;
  if (activeFilter !== "all") {
    filtered = forest.filter(f => {
      const dim = (f.outcome_dimension || "").toLowerCase();
      const label = (f.study_label || "").toLowerCase();
      if (activeFilter === "speed") return dim.includes("speed") || dim.includes("time") || dim.includes("in-task") || dim.includes("完成") || dim.includes("速度");
      if (activeFilter === "exam") return dim.includes("exam") || dim.includes("retention") || dim.includes("solo") || dim.includes("考试") || dim.includes("概念");
      if (activeFilter === "wwc") return (f.wwc_rating || "").includes("Without");
      return true;
    });
    if (!filtered.length) filtered = forest;
  }

  // Sort by effect size
  const sorted = filtered.slice().sort((a, b) => (a.effect_size || 0) - (b.effect_size || 0));
  const stats = calculateDerSimonianLaird(sorted);

  const yAxisData = [];
  const scatterData = [];
  const customData = [];

  sorted.forEach((f, idx) => {
    let label = f.study_label || `Study ${idx + 1}`;
    if (f.wwc_rating) label += ` [${f.wwc_rating.replace("Meets Standards", "WWC")}]`;

    yAxisData.push(label);
    const g = Number(f.effect_size) || 0;
    const ciLo = Number(f.ci_lower) || (g - 0.25);
    const ciHi = Number(f.ci_upper) || (g + 0.25);

    scatterData.push({
      value: [g, idx],
      itemStyle: { color: g >= 0 ? '#10b981' : '#f24d29' },
      info: f
    });

    customData.push({
      value: [ciLo, ciHi, idx],
      itemStyle: { color: textColor() }
    });
  });

  // Add Summary Diamond
  yAxisData.push(`◆ 合并效应量 (DerSimonian-Laird, I²=${stats.i2}%)`);
  scatterData.push({
    value: [stats.mean, sorted.length],
    itemStyle: { color: '#f24d29' },
    info: { effect_size: stats.mean, ci_lower: stats.ciLo, ci_upper: stats.ciHi, isMean: true, stats }
  });
  customData.push({
    value: [stats.ciLo, stats.ciHi, sorted.length],
    itemStyle: { color: '#f24d29' }
  });

  const renderItem = (params, api) => {
    const yValue = api.value(2);
    const pointLo = api.coord([api.value(0), yValue]);
    const pointHi = api.coord([api.value(1), yValue]);
    const isDiamond = yValue === sorted.length;
    const halfWidth = isDiamond ? 6 : 3;

    if (isDiamond) {
      const midPoint = api.coord([api.value(0) + (api.value(1) - api.value(0))/2, yValue]);
      return {
        type: 'polygon',
        shape: {
          points: [
            [pointLo[0], midPoint[1]],
            [midPoint[0], midPoint[1] - halfWidth],
            [pointHi[0], midPoint[1]],
            [midPoint[0], midPoint[1] + halfWidth]
          ]
        },
        style: api.style({ fill: 'rgba(242, 77, 41, 0.65)', stroke: '#f24d29', lineWidth: 1.5 })
      };
    }

    return {
      type: 'group',
      children: [
        {
          type: 'line',
          shape: { x1: pointLo[0], y1: pointLo[1], x2: pointHi[0], y2: pointHi[1] },
          style: api.style({ stroke: api.visual('color'), lineWidth: 2, opacity: 0.6 })
        },
        {
          type: 'line',
          shape: { x1: pointLo[0], y1: pointLo[1] - halfWidth, x2: pointLo[0], y2: pointLo[1] + halfWidth },
          style: api.style({ stroke: api.visual('color'), lineWidth: 2, opacity: 0.8 })
        },
        {
          type: 'line',
          shape: { x1: pointHi[0], y1: pointHi[1] - halfWidth, x2: pointHi[0], y2: pointHi[1] + halfWidth },
          style: api.style({ stroke: api.visual('color'), lineWidth: 2, opacity: 0.8 })
        }
      ]
    };
  };

  c.setOption({
    backgroundColor: "transparent",
    tooltip: {
      trigger: 'item',
      backgroundColor: 'var(--bg-surface)',
      borderColor: 'var(--border)',
      textStyle: { color: 'var(--text-primary)', fontFamily: 'Inter, sans-serif' },
      formatter: function (params) {
        if (params.seriesType === 'custom') return '';
        const f = params.data.info;
        if (f.isMean) {
          return `<div style="font-size:0.85rem;padding:2px;">
            <strong style="color:var(--brand-orange);">◆ 随机效应合并效应量 (DerSimonian-Laird)</strong><br/>
            合并效应量 g = <strong>${f.effect_size > 0 ? "+" : ""}${f.effect_size.toFixed(2)}</strong><br/>
            95% 置信区间: [${f.ci_lower.toFixed(2)}, ${f.ci_upper.toFixed(2)}]<br/>
            异质性检验: I² = <strong>${f.stats.i2}%</strong> (Q = ${f.stats.q})<br/>
            纳入研究数: ${f.stats.k} 篇
          </div>`;
        }
        return `<div style="font-size:0.8rem;padding:2px;">
          <strong class="font-medium">${esc(f.study_label)}</strong><br/>
          维度: ${esc(f.outcome_dimension)}<br/>
          样本量(N): ${f.sample_size == null ? '未知' : f.sample_size}<br/>
          效应量(g): <strong>${Number(f.effect_size).toFixed(2)}</strong> [${Number(f.ci_lower).toFixed(2)}, ${Number(f.ci_upper).toFixed(2)}]<br/>
          WWC评级: ${esc(f.wwc_rating || '—')}
        </div>`;
      }
    },
    grid: { left: 10, right: 30, top: 20, bottom: 30, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: textColor(), fontFamily: 'Inter, sans-serif' },
      splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } },
      axisLine: { show: true, lineStyle: { color: textColor() } }
    },
    yAxis: {
      type: 'category',
      data: yAxisData,
      axisLabel: {
        color: textColor(),
        fontFamily: 'Inter, sans-serif',
        width: 180,
        overflow: 'truncate'
      },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [
      {
        type: 'custom',
        name: '置信区间',
        renderItem: renderItem,
        itemStyle: { borderWidth: 1.5 },
        data: customData,
        z: 1
      },
      {
        type: 'scatter',
        name: '效应量',
        symbolSize: (data, params) => params.data.info && params.data.info.isMean ? 16 : 10,
        symbol: (data, params) => params.data.info && params.data.info.isMean ? 'diamond' : 'circle',
        itemStyle: { opacity: 0.9, borderColor: 'var(--bg-card)', borderWidth: 1.5 },
        data: scatterData,
        z: 2
      }
    ]
  }, true);

  const calculatedHeight = Math.max(320, yAxisData.length * 32 + 80);
  el.style.height = `${calculatedHeight}px`;
  c.resize();
}

export function renderEffectDist(d) {
  const el = $("#chart-effect-dist");
  const c = getChart("effect", el);
  if (!c) return;
  const items = d.effect_sizes || [];
  const vals = items.map(i => Number(i.value)).filter(v => isFinite(v));
  if (!vals.length) {
    const dc = d.direction_counts || { support: 0, contradict: 0, neutral: 0 };
    c.setOption({
      backgroundColor: "transparent",
      tooltip: { trigger: "item", formatter: "{b}: {c} 条 ({d}%)" },
      title: { text: "无数值效应量 · 方向分布回退", left: "center", top: 4, textStyle: { color: textColor(), fontSize: 11, fontWeight: 400 } },
      series: [{
        type: "pie", radius: ["45%", "70%"], center: ["50%", "55%"],
        itemStyle: { borderColor: 'var(--bg-card)', borderWidth: 2 },
        label: { show: true, formatter: "{b}: {c}", color: textColor(), fontSize: 11, fontFamily: 'Inter, sans-serif' },
        data: [
          { value: dc.support || 0, name: "支持", itemStyle: { color: "#10b981" } },
          { value: dc.contradict || 0, name: "反驳", itemStyle: { color: "#f24d29" } },
          { value: dc.neutral || 0, name: "中性", itemStyle: { color: "#94a3b8" } }
        ]
      }]
    }, true);
    return;
  }
  const min = Math.floor(Math.min(...vals) * 4) / 4;
  const max = Math.ceil(Math.max(...vals) * 4) / 4;
  const step = Math.max(0.1, (max - min) / 8);
  const buckets = [];
  for (let b = min; b < max; b += step) {
    const hiB = b + step;
    const cnt = vals.filter(v => v >= b && (v < hiB || (hiB >= max && v <= hiB))).length;
    buckets.push({ label: (b + step / 2).toFixed(2), count: cnt });
  }
  c.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border)', textStyle: { color: 'var(--text-primary)' } },
    grid: { left: 40, right: 16, top: 20, bottom: 40 },
    xAxis: { type: "category", data: buckets.map(b => b.label), axisLabel: { color: textColor(), fontSize: 11, fontFamily: 'Inter, sans-serif' } },
    yAxis: { type: "value", name: "研究数", minInterval: 1, axisLabel: { color: textColor(), fontFamily: 'Inter, sans-serif' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } } },
    series: [{ type: "bar", barWidth: '60%', data: buckets.map(b => b.count), itemStyle: { color: '#f24d29', borderRadius: [4, 4, 0, 0] } }]
  }, true);
}

function outcomeLabel(labels, key) {
  if (!key) return "—";
  if (labels && labels.outcomes && labels.outcomes[key]) return labels.outcomes[key];
  return key;
}

export function renderOutcome(d) {
  const el = $("#chart-outcome");
  const c = getChart("outcome", el);
  if (!c) return;
  const entries = d.outcome_mapping || [];
  if (!entries.length) {
    c.setOption({
      backgroundColor: "transparent",
      title: { text: "暂无结果维度数据", left: "center", top: "middle", textStyle: { color: textColor(), fontSize: 13, fontFamily: 'Inter, sans-serif' } }
    }, true);
    return;
  }
  const labels = entries.map(e => outcomeLabel(d.labels, e.outcome_type || e.outcome || ""));
  const support = entries.map(e => e.support_count || 0);
  const cont = entries.map(e => e.contradict_count || 0);
  const neut = entries.map(e => e.neutral_count || 0);
  c.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border)', textStyle: { color: 'var(--text-primary)' } },
    legend: { data: ["支持", "反驳", "中性"], top: 0, textStyle: { color: textColor(), fontSize: 11, fontFamily: 'Inter, sans-serif' } },
    grid: { left: 10, right: 20, top: 30, bottom: 20, containLabel: true },
    xAxis: { type: "value", minInterval: 1, axisLabel: { color: textColor(), fontFamily: 'Inter, sans-serif' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } } },
    yAxis: { type: "category", data: labels, axisLabel: { color: textColor(), fontSize: 11, fontFamily: 'Inter, sans-serif' } },
    series: [
      { name: "支持", type: "bar", stack: "t", barWidth: '40%', data: support, itemStyle: { color: "#10b981", borderRadius: [0, 2, 2, 0] } },
      { name: "反驳", type: "bar", stack: "t", barWidth: '40%', data: cont, itemStyle: { color: "#f24d29" } },
      { name: "中性", type: "bar", stack: "t", barWidth: '40%', data: neut, itemStyle: { color: "#94a3b8" } }
    ]
  }, true);
}

export function renderGraph(graph) {
  const el = $("#chart-graph");
  const c = getChart("graph", el);
  if (!c) return;
  if (!graph || !graph.nodes || !graph.nodes.length) {
    c.setOption({
      backgroundColor: "transparent",
      title: { text: "该课题暂无 evidence_graph.json", left: "center", top: "middle", textStyle: { color: textColor(), fontSize: 13 } }
    }, true);
    return;
  }

  const nodeCount = graph.nodes.length;
  let layoutType = "force";
  let repulsion = 180;

  if (nodeCount > 80) {
    repulsion = 60;
  } else if (nodeCount > 40) {
    repulsion = 120;
  }

  c.setOption({
    backgroundColor: "transparent",
    tooltip: { trigger: "item", backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border)', textStyle: { color: 'var(--text-primary)' } },
    legend: graph.categories && graph.categories.length
      ? { data: graph.categories.map(a => a.name), top: 10, textStyle: { fontSize: 11, color: textColor(), fontFamily: 'Inter, sans-serif' } }
      : undefined,
    series: [{
      type: "graph",
      layout: layoutType,
      data: graph.nodes,
      links: graph.links || graph.edges || [],
      categories: graph.categories || [],
      roam: true,
      label: { show: true, position: "right", formatter: "{b}", fontSize: 10, color: 'var(--text-primary)', fontFamily: 'Inter, sans-serif' },
      force: { repulsion: repulsion, edgeLength: [40, 100], gravity: 0.1 },
      lineStyle: { curveness: 0.15, color: 'var(--text-muted)', opacity: 0.4 },
      itemStyle: { borderColor: 'var(--bg-card)', borderWidth: 1 }
    }]
  }, true);

  // Click listener for node details drawer
  c.off("click");
  c.on("click", (params) => {
    if (params.dataType === "node") {
      openNodeDrawer(params.data);
    }
  });
}

function openNodeDrawer(node) {
  const drawer = $("#graph-node-drawer");
  const titleEl = $("#drawer-node-title");
  const bodyEl = $("#drawer-node-body");
  if (!drawer || !titleEl || !bodyEl) return;

  titleEl.textContent = node.name || node.id || "节点详情";
  
  let detailsHtml = `
    <div class="drawer-field">
      <label>节点类型</label>
      <div class="drawer-val"><span class="tag tag-terracotta">${node.category || node.type || "Evidence"}</span></div>
    </div>
  `;

  if (node.value != null) {
    detailsHtml += `
      <div class="drawer-field">
        <label>效应量 / 权重</label>
        <div class="drawer-val font-mono">${node.value}</div>
      </div>
    `;
  }

  if (node.doi || node.url) {
    detailsHtml += `
      <div class="drawer-field">
        <label>文献来源 / DOI</label>
        <div class="drawer-val font-mono text-xs">${esc(node.doi || node.url)}</div>
      </div>
    `;
  }

  if (node.summary || node.description || node.text) {
    detailsHtml += `
      <div class="drawer-field">
        <label>实证摘要 / 主张内容</label>
        <div class="drawer-val text-sm" style="line-height:1.5;">${esc(node.summary || node.description || node.text)}</div>
      </div>
    `;
  }

  bodyEl.innerHTML = detailsHtml;
  drawer.classList.add("open");
}
