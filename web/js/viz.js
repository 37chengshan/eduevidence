import { $, esc } from './state.js';
import { getChart, textColor } from './charts.js';

export function renderVizHeader(d) {
  const conf = typeof d.confidence === "number" ? Math.round(d.confidence * 100) + "%" : (d.confidence || "—");
  const dc = d.direction_counts || {};
  $("#viz-kpis").innerHTML =
    `<span class="viz-kpi">裁决 <span style="color:var(--text-primary); font-weight:600;">${esc(d.verdict || "—")}</span></span>` +
    `<span class="viz-kpi">置信度 <span style="color:var(--text-primary); font-weight:600;">${esc(conf)}</span></span>` +
    `<span class="viz-kpi"><span style="color:var(--green)">支持 ${dc.support || 0}</span> / <span style="color:var(--red)">反驳 ${dc.contradict || 0}</span> / 中性 ${dc.neutral || 0}</span>` +
    `<span class="viz-kpi">森林图数据 <span style="color:var(--text-primary); font-weight:600;">${(d.forest || []).length}</span> 条</span>`;
  $("#viz-question").textContent = d.question || d.title || "";
}

function hasReportedCi(f) {
  return f.ci_lower != null && f.ci_upper != null &&
    Number.isFinite(Number(f.ci_lower)) && Number.isFinite(Number(f.ci_upper));
}

function pooledMean(forest) {
  let num = 0, den = 0;
  forest.forEach(f => {
    const g = Number(f.effect_size);
    const hasCi = hasReportedCi(f);
    const ci = hasCi ? Number(f.ci_upper) - Number(f.ci_lower) : 0;
    const suppliedWeight = Number(f.weight);
    const w = ci > 0 ? 3.84 / (ci * ci) :
      (Number.isFinite(suppliedWeight) && suppliedWeight > 0 ? suppliedWeight : 0);
    if (isFinite(g) && w > 0) { num += w * g; den += w; }
  });
  return den > 0 ? num / den : null;
}

export function renderForest(forest) {
  const el = $("#forest-plot");
  const c = getChart("forest", el);
  if (!c) {
    el.innerHTML = '<div class="empty-state">图表运行时未加载；森林图数据仍可在报告中查看。</div>';
    return;
  }
  if (!forest.length) {
    el.innerHTML = '<div class="empty-state">该课题暂无可量化的森林图数据 (result.json → forest_plot_data)。</div>';
    return;
  }
  // Sort by effect size
  const sorted = forest.slice().sort((a, b) => (a.effect_size || 0) - (b.effect_size || 0));
  const mean = pooledMean(sorted);
  
  const yAxisData = [];
  const scatterData = [];
  const customData = [];
  
  sorted.forEach((f, idx) => {
    // Label with WWC rating and explicit precision status.
    let label = f.study_label || `Study ${idx + 1}`;
    const hasCi = hasReportedCi(f);
    if (f.wwc_rating) label += ` [${f.wwc_rating}]`;
    if (!hasCi) label += " [CI not reported]";
    yAxisData.push(label);
    const g = Number(f.effect_size);
    const safeG = Number.isFinite(g) ? g : 0;

    scatterData.push({
      value: [safeG, idx],
      itemStyle: { color: safeG >= 0 ? '#10B981' : '#EF4444' },
      info: f
    });

    if (hasCi) {
      customData.push({
        value: [Number(f.ci_lower), Number(f.ci_upper), idx],
        itemStyle: { color: textColor() }
      });
    }
  });

  if (mean != null) {
    yAxisData.push('合并效应量 (加权均值)');
    scatterData.push({
      value: [mean, sorted.length],
      itemStyle: { color: '#F59E0B' },
      info: { effect_size: mean, isMean: true }
    });
  }

  const renderItem = (params, api) => {
    const yValue = api.value(2);
    const pointLo = api.coord([api.value(0), yValue]);
    const pointHi = api.coord([api.value(1), yValue]);
    const halfWidth = 3;
    
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
      textStyle: { color: 'var(--text-primary)', fontFamily: 'ui-sans-serif, system-ui, sans-serif' },
      formatter: function (params) {
        if (params.seriesType === 'custom') return '';
        const f = params.data.info;
        if (f.isMean) return `合并效应量: ${f.effect_size.toFixed(2)}`;
        const ci = hasReportedCi(f)
          ? ` [${Number(f.ci_lower).toFixed(2)}, ${Number(f.ci_upper).toFixed(2)}]`
          : " [CI not reported]";
        return `<div style="font-size:0.8rem;">
          <strong class="serif-text">${esc(f.study_label)}</strong><br/>
          维度: ${esc(f.outcome_dimension)}<br/>
          样本量(N): ${f.sample_size == null ? '未知' : f.sample_size}<br/>
          效应量(g): ${Number(f.effect_size).toFixed(2)}${ci}<br/>
          WWC评级: ${esc(f.wwc_rating || '—')}
        </div>`;
      }
    },
    grid: { left: 10, right: 30, top: 20, bottom: 30, containLabel: true },
    xAxis: {
      type: 'value',
      axisLabel: { color: textColor(), fontFamily: 'ui-sans-serif, system-ui, sans-serif' },
      splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } },
      axisLine: { show: true, lineStyle: { color: textColor() } }
    },
    yAxis: {
      type: 'category',
      data: yAxisData,
      axisLabel: { 
        color: textColor(), 
        fontFamily: 'ui-serif, Georgia, serif',
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
        symbolSize: (data, params) => params.data.info && params.data.info.isMean ? 14 : 10,
        symbol: (data, params) => params.data.info && params.data.info.isMean ? 'diamond' : 'circle',
        itemStyle: { opacity: 0.9, borderColor: 'var(--bg-card)', borderWidth: 1.5 },
        data: scatterData,
        z: 2
      }
    ]
  }, true);
  
  // Set explicit height to avoid crowding
  const calculatedHeight = Math.max(300, yAxisData.length * 35 + 80);
  el.style.height = `${calculatedHeight}px`;
  c.resize();
}

export function renderEffectDist(d) {
  const el = $("#chart-effect-dist");
  const c = getChart("effect", el);
  if (!c) {
    el.innerHTML = '<div class="empty-state">交互图需要联网加载 ECharts；可查看静态 HTML 报告。</div>';
    return;
  }
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
        label: { show: true, formatter: "{b}: {c}", color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' },
        data: [
          { value: dc.support || 0, name: "支持", itemStyle: { color: "#10B981" } },
          { value: dc.contradict || 0, name: "反驳", itemStyle: { color: "#EF4444" } },
          { value: dc.neutral || 0, name: "中性", itemStyle: { color: "#A39E96" } }
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
    xAxis: { type: "category", data: buckets.map(b => b.label), axisLabel: { color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } },
    yAxis: { type: "value", name: "研究数", minInterval: 1, axisLabel: { color: textColor(), fontFamily: 'ui-sans-serif, system-ui, sans-serif' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } } },
    series: [{ type: "bar", barWidth: '60%', data: buckets.map(b => b.count), itemStyle: { color: '#D97757', borderRadius: [4, 4, 0, 0] } }]
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
  if (!c) {
    el.innerHTML = '<div class="empty-state">交互图需要联网加载 ECharts；可查看静态 HTML 报告。</div>';
    return;
  }
  const entries = d.outcome_mapping || [];
  if (!entries.length) {
    c.setOption({
      backgroundColor: "transparent",
      title: { text: "暂无结果维度数据", left: "center", top: "middle", textStyle: { color: textColor(), fontSize: 13, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } }
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
    legend: { data: ["支持", "反驳", "中性"], top: 0, textStyle: { color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } },
    grid: { left: 10, right: 20, top: 30, bottom: 20, containLabel: true },
    xAxis: { type: "value", minInterval: 1, axisLabel: { color: textColor(), fontFamily: 'ui-sans-serif, system-ui, sans-serif' }, splitLine: { lineStyle: { type: 'dashed', color: 'rgba(150,150,150,0.15)' } } },
    yAxis: { type: "category", data: labels, axisLabel: { color: textColor(), fontSize: 11, fontFamily: 'ui-sans-serif, system-ui, sans-serif' } },
    series: [
      { name: "支持", type: "bar", stack: "t", barWidth: '40%', data: support, itemStyle: { color: "#10B981", borderRadius: [0, 2, 2, 0] } },
      { name: "反驳", type: "bar", stack: "t", barWidth: '40%', data: cont, itemStyle: { color: "#EF4444" } },
      { name: "中性", type: "bar", stack: "t", barWidth: '40%', data: neut, itemStyle: { color: "#A39E96" } }
    ]
  }, true);
}

export function renderGraph(graph) {
  const el = $("#chart-graph");
  const c = getChart("graph", el);
  if (!c) {
    el.innerHTML = '<div class="empty-state">交互图需要联网加载 ECharts；证据图谱数据仍保留在 evidence_graph.json。</div>';
    return;
  }
  if (!graph || !graph.nodes || !graph.nodes.length) {
    c.setOption({
      backgroundColor: "transparent",
      title: { text: "该课题暂无 evidence_graph.json", left: "center", top: "middle", textStyle: { color: textColor(), fontSize: 13 } }
    }, true);
    return;
  }
  
  // Smart layout fallback for too many nodes
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
      ? { data: graph.categories.map(a => a.name), top: 10, textStyle: { fontSize: 11, color: textColor(), fontFamily: 'ui-sans-serif, system-ui, sans-serif' } }
      : undefined,
    series: [{
      type: "graph", 
      layout: layoutType,
      data: graph.nodes, 
      links: graph.links || graph.edges || [], 
      categories: graph.categories || [],
      roam: true,
      label: { show: true, position: "right", formatter: "{b}", fontSize: 10, color: 'var(--text-primary)', fontFamily: 'ui-sans-serif, system-ui, sans-serif' },
      force: { repulsion: repulsion, edgeLength: [40, 100], gravity: 0.1 },
      lineStyle: { curveness: 0.15, color: 'var(--text-muted)', opacity: 0.4 },
      itemStyle: { borderColor: 'var(--bg-card)', borderWidth: 1 }
    }]
  }, true);
}
