#!/usr/bin/env python3
"""build_figures.py — Academic Figures adapter (v5 Iteration 4, §23-30).

Purpose = statistical_publication -> Academic Figures (v5 §34 router).
From result.json, produce:
    - figure_data.json     publication-ready data (adapter output, §52)
    - figures/*.svg        publication SVG (Okabe-Ito / Nature / Conservative)
    - figures/*.png|pdf    raster/vector export when matplotlib is available

Publication conventions (v5 §25-30):
    - truthful: only pre-existing error bars / significance from the analysis
    - figure provenance attached to every figure
    - Okabe-Ito colorblind-safe palette by default
    - auto-trigger when result contains numeric comparisons / CI / significance
      (recommend_academic_figure = true, §58)

Zero hard dependency: SVG generation is pure-Python; matplotlib export is
optional (guarded import) for PNG/PDF.

Usage:
    python3 visualization/eduevidence-report/scripts/build_figures.py \
        --result examples/ai-coding-assistant/result.json \
        --out-dir examples/ai-coding-assistant/figures
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.sax.saxutils as sax
from pathlib import Path
from typing import Any

from adapter_contract import load_result, write_adapter_output
from zh_labels import zh_outcome
from build_charts import effect_outcomes

OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]
NATURE = ["#1F4E5F", "#5B8C9E", "#9E4B3A", "#7A8B5C", "#C2A24A", "#4E4E4E"]
PALM = ["#B8694A", "#5E8A6A", "#C99A4A", "#8A867E", "#A85B53", "#3A3833"]
PORCELAIN = ["#0284C7", "#10B981", "#F59E0B", "#64748B", "#EF4444", "#0F172A"]
WIRE = ["#38BDF8", "#10B981", "#F59E0B", "#EF4444", "#818CF8", "#F8FAFC"]
JUDICIAL = ["#F59E0B", "#F24D29", "#10B981", "#B8694A", "#D97706", "#FFFFFF"]
CONSERVATIVE = ["#4E4E4E", "#8C8C8C", "#B0B0B0", "#6B6B6B", "#D0D0D0", "#2E2E2E"]

THEME_PALETTES = {
    "okabe_ito": OKABE_ITO,
    "nature": NATURE,
    "mono": NATURE,
    "academic": NATURE,
    "academic_paper": NATURE,
    "claude": PALM,
    "claude_research": PALM,
    "palm": PALM,
    "datalab": PORCELAIN,
    "datalab_light": PORCELAIN,
    "porcelain": PORCELAIN,
    "datalab_dark": WIRE,
    "datalab-dark": WIRE,
    "wire": WIRE,
    "presentation": JUDICIAL,
    "presentation_judge": JUDICIAL,
    "judicial": JUDICIAL,
    "conservative": CONSERVATIVE
}


def _esc(t: Any) -> str:
    return sax.escape(str(t if t is not None else ""))


def _linear_ticks(maxv: int) -> list[int]:
    """Integer tick labels at roughly uniform intervals (never skip the top)."""
    if maxv <= 0:
        return [0]
    if maxv <= 5:
        return list(range(0, maxv + 1))
    step = max(1, (maxv + 4) // 5)  # ceil division for ~5 intervals
    ticks = list(range(0, maxv + 1, step))
    if ticks[-1] < maxv:
        ticks.append(maxv)
    return ticks


def _figure_svg(title: str, caption: str, body: str, w: int = 720, h: int = 300) -> str:
    return (f'<svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="{_esc(caption)}">'
            f'<rect width="{w}" height="{h}" fill="#FFFFFF"/>'
            f'{body}'
            f'<text x="20" y="{h - 10}" font-size="11" fill="#333333" font-style="italic">{_esc(caption)}</text>'
            f'</svg>')


def _bar_chart(title: str, names: list[str], values: list[float], palette: list[str],
               caption: str, unit: str = "", vmax: float | None = None, h: int = 300) -> str:
    w = 720
    plot_x, plot_w, plot_y, plot_h = 70, 580, 50, 200
    maxv = vmax if vmax is not None else (max(values) * 1.15 if values else 1)
    if maxv <= 0:
        maxv = 1
    bw = min(46, plot_w / max(1, len(names)) * 0.6)
    body = [f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" '
            f'y2="{plot_y + plot_h}" stroke="#333" stroke-width="1"/>']
    for i, (name, value) in enumerate(zip(names, values)):
        bh = (value / maxv) * plot_h
        x = plot_x + (i + 0.5) * (plot_w / len(names)) - bw / 2
        y = plot_y + plot_h - bh
        body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(bh, 1):.1f}" '
                    f'fill="{palette[i % len(palette)]}"/>')
        body.append(f'<text x="{x + bw / 2:.1f}" y="{plot_y + plot_h + 16}" text-anchor="middle" '
                    f'font-size="10" fill="#333">{_esc(name)}</text>')
        body.append(f'<text x="{x + bw / 2:.1f}" y="{y - 4:.1f}" text-anchor="middle" font-size="10" '
                    f'fill="#333">{value:.0f}{_esc(unit)}</text>')
    # 计数图 Y 轴整数刻度：线性间隔，绝不产生 [0,1,2,3,4,12] 式失真刻度
    ticks = _linear_ticks(int(maxv)) if maxv > 0 else [0]
    for t in ticks:
        ty = plot_y + plot_h - (t / maxv) * plot_h
        body.append(f'<line x1="{plot_x - 5}" y1="{ty:.1f}" x2="{plot_x}" y2="{ty:.1f}" stroke="#999"/>')
        body.append(f'<text x="{plot_x - 8}" y="{ty + 3:.1f}" text-anchor="end" font-size="9" '
                    f'fill="#666">{t}</text>')
    body.append(f'<text x="{plot_x + plot_w / 2}" y="30" text-anchor="middle" font-size="14" '
                f'font-weight="700" fill="#111">{_esc(title)}</text>')
    return _figure_svg(title, caption, "".join(body), h=h)


def _grouped_bar_chart(title: str, names: list[str], series: list[dict],
                       caption: str, palette: list[str], h: int = 300) -> str:
    """方向分组条形图：每组一个结果类型，内部并列 support / contradict / neutral
    三根柱（P0-12）。计数轴整数刻度（P0-11）。"""
    w = 720
    plot_x, plot_w, plot_y, plot_h = 70, 580, 50, 200
    maxv = max([1] + [abs(v) for s in series for v in s["data"]])
    group_w = plot_w / max(1, len(names))
    n_series = len(series)
    bar_w = min(34, group_w / (n_series + 1))
    body = [f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" '
            f'y2="{plot_y + plot_h}" stroke="#333" stroke-width="1"/>']
    for i, name in enumerate(names):
        cx = plot_x + group_w * (i + 0.5)
        body.append(f'<text x="{cx:.1f}" y="{plot_y + plot_h + 16}" text-anchor="middle" '
                    f'font-size="10" fill="#333">{_esc(name)}</text>')
        for j, s in enumerate(series):
            value = s["data"][i] if i < len(s["data"]) else 0
            bh = (value / maxv) * plot_h
            x = plot_x + group_w * i + group_w / 2 + bar_w * (j - (n_series - 1) / 2)
            y = plot_y + plot_h - bh
            body.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                        f'height="{max(bh, 1):.1f}" fill="{palette[j % len(palette)]}"/>')
            if bh > 8:
                body.append(f'<text x="{x + bar_w / 2:.1f}" y="{y - 3:.1f}" text-anchor="middle" '
                            f'font-size="9" fill="#333">{value:.0f}</text>')
    ticks = [0]
    while ticks[-1] < maxv and len(ticks) < 5:
        ticks.append(ticks[-1] + 1)
    if ticks[-1] < maxv:
        ticks.append(int(maxv))
    for t in ticks:
        ty = plot_y + plot_h - (t / maxv) * plot_h
        body.append(f'<line x1="{plot_x - 5}" y1="{ty:.1f}" x2="{plot_x}" y2="{ty:.1f}" stroke="#999"/>')
        body.append(f'<text x="{plot_x - 8}" y="{ty + 3:.1f}" text-anchor="end" font-size="9" '
                    f'fill="#666">{t}</text>')
    body.append(f'<text x="{plot_x + plot_w / 2}" y="30" text-anchor="middle" font-size="14" '
                f'font-weight="700" fill="#111">{_esc(title)}</text>')
    # 图例
    lx = plot_x
    for s in series:
        body.append(f'<rect x="{lx}" y="8" width="10" height="10" '
                    f'fill="{palette[series.index(s) % len(palette)]}"/>')
        body.append(f'<text x="{lx + 14}" y="17" font-size="10" fill="#333">{_esc(s["name"])}</text>')
        lx += 14 + len(s["name"]) * 11 + 18
    return _figure_svg(title, caption, "".join(body), h=h)


def _scatter_chart(title: str, points: list[tuple[float, float]], labels: list[str],
                   palette: list[str], caption: str, h: int = 300) -> str:
    w = 720
    plot_x, plot_w, plot_y, plot_h = 70, 580, 50, 200
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xmax = max(xs) * 1.15 if xs else 1
    ymax = 1.0
    body = [
        f'<line x1="{plot_x}" y1="{plot_y + plot_h}" x2="{plot_x + plot_w}" y2="{plot_y + plot_h}" stroke="#333"/>',
        f'<line x1="{plot_x}" y1="{plot_y}" x2="{plot_x}" y2="{plot_y + plot_h}" stroke="#333"/>',
    ]
    for i, ((x, y), label) in enumerate(zip(points, labels)):
        px = plot_x + (x / xmax) * plot_w
        py = plot_y + plot_h - (y / ymax) * plot_h
        body.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="6" fill="{palette[i % len(palette)]}" '
                    f'opacity="0.9"/>')
        body.append(f'<text x="{px + 8:.1f}" y="{py - 6:.1f}" font-size="10" fill="#333">{_esc(label)}</text>')
    body.append(f'<text x="{plot_x + plot_w / 2}" y="30" text-anchor="middle" font-size="14" '
                f'font-weight="700" fill="#111">{_esc(title)}</text>')
    body.append(f'<text x="{plot_x + plot_w - 10}" y="{plot_y + plot_h + 16}" text-anchor="end" '
                f'font-size="10" fill="#666">cost (USD)</text>')
    return _figure_svg(title, caption, "".join(body), h=h)


def _forest_plot_svg(title: str, points: list[dict], caption: str, h: int = 420) -> str:
    """Publication-Grade Meta-Analysis Forest Plot.

    Shows effect sizes (Hedges' g), 95% Confidence Intervals, study weights,
    and the diverging contrast between in-task procedural speed vs delayed unassisted transfer.
    """
    w = 820
    header_y = 52
    row_start_y = 78
    row_height = 28

    # Plot bounds: scale g from -1.0 (x=330) to +1.0 (x=670), center 0.0 at x=500
    plot_left = 330
    plot_right = 670
    plot_center = (plot_left + plot_right) / 2  # x=500
    scale = (plot_right - plot_left) / 2.0  # 170 px per 1.0 g

    total_h = max(h, row_start_y + len(points) * row_height + 70)

    body = [
        f'<text x="{w / 2:.1f}" y="28" text-anchor="middle" font-size="15" font-weight="700" fill="#111">{_esc(title)}</text>',
        f'<text x="24" y="{header_y}" font-size="11" font-weight="700" fill="#444">Study & Venue</text>',
        f'<text x="240" y="{header_y}" font-size="11" font-weight="700" fill="#444">Dimension</text>',
        f'<text x="{plot_center:.1f}" y="{header_y}" text-anchor="middle" font-size="10" font-weight="700" fill="#444">Hedges\' g [95% CI]</text>',
        f'<text x="{w - 24:.1f}" y="{header_y}" text-anchor="end" font-size="11" font-weight="700" fill="#444">Effect [95% CI]</text>',
        f'<line x1="20" y1="{header_y + 8}" x2="{w - 20}" y2="{header_y + 8}" stroke="#333" stroke-width="1"/>',
        # Vertical zero line (g = 0.0)
        f'<line x1="{plot_center:.1f}" y1="{header_y + 8}" x2="{plot_center:.1f}" y2="{total_h - 40}" stroke="#999" stroke-dasharray="3,3"/>',
        # Bottom axis scale
        f'<line x1="{plot_left}" y1="{total_h - 40}" x2="{plot_right}" y2="{total_h - 40}" stroke="#333" stroke-width="1"/>',
    ]

    for tick_g in [-1.0, -0.5, 0.0, 0.5, 1.0]:
        tx = plot_center + tick_g * scale
        body.append(f'<line x1="{tx:.1f}" y1="{total_h - 40}" x2="{tx:.1f}" y2="{total_h - 35}" stroke="#333"/>')
        body.append(f'<text x="{tx:.1f}" y="{total_h - 24}" text-anchor="middle" font-size="9" fill="#555">{tick_g:+.1f}</text>')

    body.append(f'<text x="{plot_left + 10}" y="{total_h - 10}" text-anchor="start" font-size="9" fill="#A85B53">← Favors Control (Deficit)</text>')
    body.append(f'<text x="{plot_right - 10}" y="{total_h - 10}" text-anchor="end" font-size="9" fill="#5E8A6A">Favors AI (Gain) →</text>')

    for i, p in enumerate(points):
        ry = row_start_y + i * row_height
        g_val = p.get("effect_size", 0.0)
        ci_l = p.get("ci_lower")
        ci_u = p.get("ci_upper")
        has_ci = ci_l is not None and ci_u is not None
        dim = p.get("outcome_dimension", "")

        is_pos = g_val > 0.10
        color = "#5E8A6A" if is_pos else ("#A85B53" if g_val < -0.05 else "#C99A4A")

        # Study label & Dimension
        body.append(f'<text x="24" y="{ry + 4}" font-size="10" font-weight="500" fill="#222">{_esc(p.get("study_label", "Study"))}</text>')
        body.append(f'<text x="240" y="{ry + 4}" font-size="9" fill="#666">{_esc(dim.replace("_", " ").title()[:14])}</text>')

        x_pt = max(plot_left, min(plot_right, plot_center + g_val * scale))
        if has_ci:
            x_ci_l = max(plot_left, min(plot_right, plot_center + ci_l * scale))
            x_ci_u = max(plot_left, min(plot_right, plot_center + ci_u * scale))
            body.append(f'<line x1="{x_ci_l:.1f}" y1="{ry}" x2="{x_ci_u:.1f}" y2="{ry}" stroke="{color}" stroke-width="1.5"/>')
            body.append(f'<line x1="{x_ci_l:.1f}" y1="{ry - 4}" x2="{x_ci_l:.1f}" y2="{ry + 4}" stroke="{color}" stroke-width="1.5"/>')
            body.append(f'<line x1="{x_ci_u:.1f}" y1="{ry - 4}" x2="{x_ci_u:.1f}" y2="{ry + 4}" stroke="{color}" stroke-width="1.5"/>')
        # Center square (point only when CI not reported)
        body.append(f'<rect x="{x_pt - 3.5:.1f}" y="{ry - 3.5:.1f}" width="7" height="7" fill="{color}"/>')

        # Numeric label: no fabricated precision when CI missing
        if has_ci:
            body.append(f'<text x="{w - 24:.1f}" y="{ry + 4}" text-anchor="end" font-size="10" font-family="monospace" fill="#333">{g_val:+.2f} [{ci_l:+.2f}, {ci_u:+.2f}]</text>')
        else:
            body.append(f'<text x="{w - 24:.1f}" y="{ry + 4}" text-anchor="end" font-size="10" font-family="monospace" fill="#777">{g_val:+.2f} [CI not reported]</text>')

    return _figure_svg(title, caption, "".join(body), w=w, h=total_h)


def build_figure_data(result: dict) -> dict[str, Any]:
    """figure_data.json — publication-ready adapter output (v5 §52)."""
    outcomes = effect_outcomes(result)
    benchmark = result.get("benchmark", {})
    decision = result.get("decision", {})
    return {
        "source": "result.json",
        "outcomes": [
            {"outcome_type": o.get("outcome_type"),
             "positive_count": o.get("positive_count", 0),
             "negative_count": o.get("negative_count", 0),
             "null_count": o.get("null_count", 0)}
            for o in outcomes
        ],
        "benchmark_baselines": benchmark.get("baselines", {}),
        "confidence": decision.get("confidence"),
        "recommended_action": decision.get("recommended_action"),
        "recommend_academic_figure": True,
        "provenance": {
            "generated_by": "build_figures.py",
            "from": "result.json",
            "statistics_source": "EduEvidence analysis result (no invented p-values)",
        },
    }


FIGURE_TITLES = {
    "zh": {"fig1": "各结果类型的效应方向分布", "fig2": "各基线引用支持精度",
           "fig3": "质量 vs 成本"},
    "en": {"fig1": "Effect direction by outcome type", "fig2": "Citation support by baseline",
           "fig3": "Quality vs Cost"},
}

FIGURE_CAPTIONS = {
    "zh": {
        "fig1": "图 1. 各结果类型的正向 / 负向 / 零效应证据条数（基于 effect_direction；出版级学术图，不随主题变化）。来源：EduEvidence result.json。",
        "fig2": "图 2. B0-B4 各基线的引用支持精度。来源：EduEvidence Benchmark v2。",
        "fig3": "图 3. 各基线的引用支持率与单题成本的对比。",
    },
    "en": {
        "fig1": "Fig. 1. Counts of positive / negative / null effects per outcome type "
                "(based on effect_direction; publication figure, theme-independent). Source: EduEvidence result.json.",
        "fig2": "Fig. 2. Citation support precision per baseline B0-B4. Source: EduEvidence Benchmark v2.",
        "fig3": "Fig. 3. Citation support rate vs cost per question across baselines.",
    },
}

DIR_SERIES = {
    "zh": [{"name": "正向效应", "data": "positive_count"},
           {"name": "负向效应", "data": "negative_count"},
           {"name": "零效应", "data": "null_count"}],
    "en": [{"name": "Positive effect", "data": "positive_count"},
           {"name": "Negative effect", "data": "negative_count"},
           {"name": "Null effect", "data": "null_count"}],
}


def render_figures(figure_data: dict, theme: str = "okabe_ito", lang: str = "zh") -> dict[str, str]:
    """Render publication SVG figures from figure_data (pure Python)."""
    theme_key = (theme or "okabe_ito").lower().replace("-", "_")
    palette = THEME_PALETTES.get(theme_key, OKABE_ITO)
    figures: dict[str, str] = {}

    # Figure 1: Outcome × effect_direction (positive / negative / null 三色分组；
    # 绝不把 relation_to_claim 的 support/contradict 当作 outcome 好坏；计数轴整数刻度。)
    outcomes = figure_data.get("outcomes", [])
    if outcomes:
        names = [zh_outcome(o["outcome_type"]) if lang == "zh"
                 else o["outcome_type"] for o in outcomes]
        series = [{"name": s["name"],
                   "data": [o.get(s["data"], 0) for o in outcomes]}
                  for s in DIR_SERIES[lang]]
        figures["outcome-comparison.svg"] = _grouped_bar_chart(
            FIGURE_TITLES[lang]["fig1"], names, series,
            FIGURE_CAPTIONS[lang]["fig1"], palette)

    # Figure 2: benchmark citation support
    baselines = figure_data.get("benchmark_baselines", {})
    if baselines:
        names = list(baselines.keys())
        citation = [b.get("citation_support_precision", 0) for b in baselines.values()]
        figures["benchmark-citation-support.svg"] = _bar_chart(
            FIGURE_TITLES[lang]["fig2"], names, citation, palette,
            FIGURE_CAPTIONS[lang]["fig2"])
        costs = [b.get("usage", {}).get("cost_usd", 0) for b in baselines.values()]
        if len(costs) == len(citation):
            figures["benchmark-quality-cost.svg"] = _scatter_chart(
                FIGURE_TITLES[lang]["fig3"], list(zip(costs, citation)), names, palette,
                FIGURE_CAPTIONS[lang]["fig3"])

    forest_pts = figure_data.get("forest_plot_data", [])
    if not forest_pts and "evidence_nodes" in figure_data:
        for ev in figure_data["evidence_nodes"][:10]:
            es = ev.get("effect_size")
            es_dict = es if isinstance(es, dict) else {}
            forest_pts.append({
                "study_label": ev.get("study_label", ev.get("evidence_id", "Study")),
                "outcome_dimension": ev.get("outcome_dimension", "GENERAL"),
                "effect_size": es_dict.get("value", 0.0),
                "ci_lower": es_dict.get("ci_lower"),
                "ci_upper": es_dict.get("ci_upper"),
            })

    if forest_pts:
        figures["forest-plot.svg"] = _forest_plot_svg(
            "效应量森林图 (Forest Plot: 任务速度提升 vs 独立迁移赤字)",
            forest_pts,
            "图 4. 效应量森林图（Hedges' g 与 95% 置信区间；展示程序速度提升与无 AI 独立迁移赤字的尖锐分歧）。来源：EduEvidence SSOT 证据图谱。"
        )

    # Lieflat gallery: data-driven composition only. Every chart is rendered
    # from a charts_data extractor bundle; entries come from the validated
    # visual_layout (resolve_visual_layout). Unregistered types never reach
    # this point; insufficient data suppresses the chart with a reason.
    return figures


def render_lieflat_gallery(result: dict, theme: str, lang: str,
                           layout_entries: list) -> tuple[dict[str, str], dict]:
    """Render only the layout entries that passed resolve_visual_layout.

    Each entry {chart_id, type, title_zh/en, subtitle_zh/en, caption_zh/en,
    source, params} is rendered from the extractor bundle for its registry
    source. Returns (figures_by_chart_id, meta) where meta records selected
    charts, suppressed charts with reasons, and the number audit used by the
    lieflat_data_bound integrity gate.
    """
    from lieflat_engine import REGISTRY, render_figure

    figures: dict[str, str] = {}
    meta_out = {"selected": [], "suppressed": [], "audits": {}}
    for entry in layout_entries or []:
        fig_type = entry.get("type")
        reg = REGISTRY.get(fig_type)
        if reg is None:
            meta_out["suppressed"].append({
                "chart_id": entry.get("chart_id"), "type": fig_type,
                "reason": f"unregistered type {fig_type!r}"})
            continue
        bundle, reason = reg["extractor"](result, entry.get("params") or {}, lang)
        if bundle is None:
            meta_out["suppressed"].append({
                "chart_id": entry.get("chart_id"), "type": fig_type,
                "catalog_ref": reg["catalog_ref"], "reason": reason})
            continue
        audit: list = []
        meta = {
            "lang": lang,
            "title": entry.get(f"title_{lang}") or entry.get("title") or "",
            "subtitle": entry.get(f"subtitle_{lang}") or entry.get("subtitle") or "",
            "caption": entry.get(f"caption_{lang}") or entry.get("caption") or "",
            "source": entry.get("source") or reg["source"],
        }
        try:
            svg = render_figure(fig_type, bundle, theme, meta, audit=audit)
        except ValueError as exc:
            meta_out["suppressed"].append({
                "chart_id": entry.get("chart_id"), "type": fig_type,
                "catalog_ref": reg["catalog_ref"], "reason": f"render error: {exc}"})
            continue
        figures[entry.get("chart_id")] = svg
        meta_out["audits"][entry.get("chart_id")] = {
            "type": fig_type, "bundle": bundle, "audit": audit}
        meta_out["selected"].append({
            "chart_id": entry.get("chart_id"), "type": fig_type,
            "catalog_ref": reg["catalog_ref"], "source": reg["source"]})
    return figures, meta_out


def export_png_pdf(svg_path: Path, out_dir: Path) -> None:
    """Optional matplotlib export to PNG/PDF (guarded; skip when unavailable)."""
    try:
        import matplotlib.pyplot as plt
        import numpy as np  # noqa: F401
    except ImportError:
        return
    from io import StringIO
    import re

    svg_text = svg_path.read_text(encoding="utf-8")
    rects = re.findall(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)" fill="(#[0-9A-Fa-f]{6})"',
                       svg_text)
    texts = re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*>([^<]+)</text>', svg_text)
    if not rects:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    for x, y, w, h, color in rects:
        ax.bar(float(x), float(h), bottom=float(y), width=float(w), color=color, edgecolor="none")
    ax.set_xlim(0, 720)
    ax.set_ylim(0, 300)
    ax.axis("off")
    stem = svg_path.stem
    fig.savefig(out_dir / f"{stem}.png", dpi=150, bbox_inches="tight")
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Academic Figures from result.json")
    parser.add_argument("--result", required=True)
    parser.add_argument("--out", required=False,
                        help="output envelope JSON path (new unified contract)")
    parser.add_argument("--out-dir", required=False,
                        help="[deprecated] legacy directory output; use --out")
    parser.add_argument("--theme", choices=["okabe_ito", "nature", "conservative"],
                        default="okabe_ito")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--export-png", action="store_true",
                        help="try matplotlib export to PNG/PDF (optional)")
    args = parser.parse_args()

    if not args.out and not args.out_dir:
        parser.error("one of --out / --out-dir is required")

    result = load_result(args.result)
    figure_data = build_figure_data(result)
    figures = render_figures(figure_data, theme=args.theme, lang=args.lang)

    if args.out:
        # New unified contract: single envelope JSON with structured data + SVG strings.
        write_adapter_output(args.out, "figures", args.result,
                             {"figure_data": figure_data, "figures": figures},
                             locale=args.lang)
        print(f"wrote {args.out} (figures_data + {len(figures)} svg figures)")
        return 0

    # Legacy --out-dir compatibility (deprecated; migrate callers to --out).
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "figure_data.json").write_text(
        json.dumps(figure_data, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, svg in figures.items():
        path = out_dir / name
        path.write_text(svg, encoding="utf-8")
        if args.export_png:
            export_png_pdf(path, out_dir)
    print(f"wrote {len(figures) + 1} files to {args.out_dir}: "
          f"{', '.join(sorted(figures.keys()))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
