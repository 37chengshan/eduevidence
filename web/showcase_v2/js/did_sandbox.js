/**
 * web/js/did_sandbox.js — Live Difference-in-Differences (DID) Interactive Statistical Sandbox
 */
import { state, $, $$, isDark, toast } from './state.js';
import { api } from './api.js';

let didChartInstance = null;

export function initDidSandbox() {
  const runBtn = $("#did-run-btn");
  const presetBtns = $$(".did-preset-btn");
  const sliders = $$(".did-slider");

  if (runBtn) {
    runBtn.addEventListener("click", () => fetchAndRenderDid());
  }

  presetBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      presetBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      applyPreset(btn.dataset.preset);
      fetchAndRenderDid();
    });
  });

  sliders.forEach(slider => {
    const valEl = $(`#${slider.id}-val`);
    slider.addEventListener("input", () => {
      if (valEl) {
        let suffix = "";
        if (slider.id.includes("lift")) suffix = " 分";
        else if (slider.id.includes("weeks") || slider.id.includes("intervene")) suffix = " 周";
        else if (slider.id.includes("sample")) suffix = " 人";
        valEl.textContent = slider.value + suffix;
      }
      debounce(fetchAndRenderDid, 150)();
    });
  });

  // Initial render
  fetchAndRenderDid();
}

let debounceTimer = null;
function debounce(fn, delay) {
  return function(...args) {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fn.apply(this, args), delay);
  };
}

function applyPreset(preset) {
  if (preset === "cs1") {
    $("#did-param-weeks").value = 12;
    $("#did-param-intervene").value = 5;
    $("#did-param-lift").value = 8.5;
    $("#did-param-sample").value = 200;
    $("#did-param-noise").value = 3;
  } else if (preset === "tutor") {
    $("#did-param-weeks").value = 16;
    $("#did-param-intervene").value = 6;
    $("#did-param-lift").value = 6.2;
    $("#did-param-sample").value = 180;
    $("#did-param-noise").value = 4;
  } else if (preset === "writing") {
    $("#did-param-weeks").value = 8;
    $("#did-param-intervene").value = 3;
    $("#did-param-lift").value = 4.8;
    $("#did-param-sample").value = 140;
    $("#did-param-noise").value = 2;
  }

  // Update labels
  ["weeks", "intervene", "lift", "sample", "noise"].forEach(k => {
    const s = $(`#did-param-${k}`);
    const v = $(`#did-param-${k}-val`);
    if (s && v) {
      let suffix = "";
      if (k === "lift") suffix = " 分";
      else if (k === "weeks" || k === "intervene") suffix = " 周";
      else if (k === "sample") suffix = " 人";
      v.textContent = s.value + suffix;
    }
  });
}

function getDidParams() {
  return {
    weeks: parseInt($("#did-param-weeks")?.value || "12", 10),
    intervene_week: parseInt($("#did-param-intervene")?.value || "5", 10),
    treat_lift: parseFloat($("#did-param-lift")?.value || "8.5"),
    sample_n: parseInt($("#did-param-sample")?.value || "200", 10),
    noise: parseFloat($("#did-param-noise")?.value || "3.0"),
    baseline_diff: 0.2
  };
}

export function fetchAndRenderDid() {
  const params = getDidParams();
  
  fetch("/api/did/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params)
  })
  .then(res => res.json())
  .then(data => {
    if (data.status === "success") {
      renderDidChart(data);
      renderDidStats(data);
    } else {
      toast("DID 分析失败: " + (data.message || "未知错误"), true);
    }
  })
  .catch(err => {
    toast("DID 服务请求异常: " + err.message, true);
  });
}

function renderDidStats(data) {
  const reg = data.regression || {};
  const cells = data.cell_means || {};

  const deltaEl = $("#did-stat-delta");
  const gEl = $("#did-stat-g");
  const pEl = $("#did-stat-p");
  const r2El = $("#did-stat-r2");
  const ciEl = $("#did-stat-ci");
  const ratingEl = $("#did-stat-wwc");

  if (deltaEl) deltaEl.textContent = `+${reg.did_coefficient} 分`;
  if (gEl) gEl.textContent = `${reg.hedges_g > 0 ? "+" : ""}${reg.hedges_g}g`;
  if (pEl) pEl.textContent = reg.p_value < 0.001 ? "< 0.001 (极显著)" : `p = ${reg.p_value}`;
  if (r2El) r2El.textContent = `${(reg.r_squared * 100).toFixed(1)}%`;
  if (ciEl && reg.ci_95) ciEl.textContent = `[+${reg.ci_95[0]}, +${reg.ci_95[1]}]`;

  if (ratingEl) {
    ratingEl.textContent = reg.wwc_baseline_rating || "Meets Standards";
    ratingEl.className = "tag " + (
      reg.wwc_baseline_rating?.includes("Without") ? "tag-emerald" :
      reg.wwc_baseline_rating?.includes("With") ? "tag-amber" : "tag-crimson"
    );
  }

  // 2x2 Cell Means Table
  const tableEl = $("#did-2x2-tbody");
  if (tableEl) {
    tableEl.innerHTML = `
      <tr>
        <td class="font-medium">实验组 (Treatment)</td>
        <td>${cells.treatment_pre} 分</td>
        <td>${cells.treatment_post} 分</td>
        <td class="text-terracotta font-semibold">+${(cells.treatment_post - cells.treatment_pre).toFixed(2)}</td>
      </tr>
      <tr>
        <td class="font-medium">对照组 (Control)</td>
        <td>${cells.control_pre} 分</td>
        <td>${cells.control_post} 分</td>
        <td class="text-slate font-semibold">+${(cells.control_post - cells.control_pre).toFixed(2)}</td>
      </tr>
      <tr class="highlight-row">
        <td class="font-bold">净因果效应 (DID Δ)</td>
        <td colspan="2" class="text-center font-mono text-xs text-muted">Δ = (T_post - T_pre) - (C_post - C_pre)</td>
        <td class="font-bold text-terracotta text-lg">+${reg.did_coefficient} 分</td>
      </tr>
    `;
  }
}

function renderDidChart(data) {
  const chartDom = $("#chart-did-trends");
  if (!chartDom || !window.echarts) return;

  if (!didChartInstance) {
    didChartInstance = echarts.init(chartDom);
    window.addEventListener("resize", () => didChartInstance && didChartInstance.resize());
  }

  const dark = isDark();
  const weeks = data.weeks || [];
  const control = data.series?.control || [];
  const treatment = data.series?.treatment || [];
  const counterfactual = data.series?.counterfactual || [];
  const interveneIdx = (data.intervene_week || 5) - 1;

  const option = {
    backgroundColor: "transparent",
    animationDuration: 600,
    tooltip: {
      trigger: "axis",
      backgroundColor: dark ? "#1e293b" : "#ffffff",
      borderColor: dark ? "#334155" : "#e2e8f0",
      textStyle: { color: dark ? "#f8fafc" : "#0f172a", fontSize: 12 },
      formatter: function(params) {
        let res = `<div style="font-weight:600;margin-bottom:4px;">${params[0].name}</div>`;
        params.forEach(p => {
          if (p.value != null) {
            res += `<div style="display:flex;justify-content:space-between;gap:16px;">
              <span>${p.marker} ${p.seriesName}</span>
              <span style="font-weight:600;">${p.value} 分</span>
            </div>`;
          }
        });
        return res;
      }
    },
    legend: {
      top: 4,
      right: 12,
      textStyle: { color: dark ? "#94a3b8" : "#475569", fontSize: 11 },
      data: ["实验组 (引入AI支架)", "对照组 (传统教学)", "实验组反事实基准 (无干预)"]
    },
    grid: {
      left: "3%",
      right: "4%",
      bottom: "6%",
      top: "16%",
      containLabel: true
    },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: weeks,
      axisLine: { lineStyle: { color: dark ? "#334155" : "#cbd5e1" } },
      axisLabel: { color: dark ? "#94a3b8" : "#64748b", fontSize: 11 }
    },
    yAxis: {
      type: "value",
      name: "考试均分 (0-100)",
      nameTextStyle: { color: dark ? "#64748b" : "#94a3b8", fontSize: 11 },
      min: function(value) { return Math.max(0, Math.floor(value.min - 4)); },
      max: function(value) { return Math.min(100, Math.ceil(value.max + 4)); },
      splitLine: { lineStyle: { color: dark ? "#1e293b" : "#f1f5f9" } },
      axisLabel: { color: dark ? "#94a3b8" : "#64748b" }
    },
    series: [
      {
        name: "实验组 (引入AI支架)",
        type: "line",
        smooth: true,
        data: treatment,
        symbolSize: 6,
        itemStyle: { color: "#f24d29" },
        lineStyle: { width: 3.5, color: "#f24d29" },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: "rgba(242, 77, 41, 0.28)" },
            { offset: 1, color: "rgba(242, 77, 41, 0.0)" }
          ])
        },
        markLine: {
          silent: true,
          symbol: "none",
          data: [
            {
              xAxis: interveneIdx,
              label: {
                show: true,
                position: "insideEndTop",
                formatter: `⚡ 第 ${data.intervene_week} 周：干预启动`,
                color: "#f24d29",
                fontSize: 11,
                fontWeight: "bold",
                backgroundColor: dark ? "rgba(30,41,59,0.85)" : "rgba(255,255,255,0.9)",
                padding: [4, 8],
                borderRadius: 4,
                borderColor: "#f24d29",
                borderWidth: 1
              },
              lineStyle: {
                color: "#f24d29",
                type: "dashed",
                width: 2
              }
            }
          ]
        }
      },
      {
        name: "对照组 (传统教学)",
        type: "line",
        smooth: true,
        data: control,
        symbolSize: 5,
        itemStyle: { color: "#64748b" },
        lineStyle: { width: 2.5, color: "#64748b" }
      },
      {
        name: "实验组反事实基准 (无干预)",
        type: "line",
        smooth: true,
        data: counterfactual,
        symbol: "none",
        lineStyle: { width: 2, type: "dotted", color: "#94a3b8" }
      }
    ]
  };

  didChartInstance.setOption(option);
}

export function resizeDidChart() {
  if (didChartInstance) didChartInstance.resize();
}
