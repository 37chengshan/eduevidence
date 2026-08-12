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

from zh_labels import zh_outcome
from build_charts import effect_outcomes

OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7", "#000000"]
NATURE = ["#1F4E5F", "#5B8C9E", "#9E4B3A", "#7A8B5C", "#C2A24A", "#4E4E4E"]
CONSERVATIVE = ["#4E4E4E", "#8C8C8C", "#B0B0B0", "#6B6B6B", "#D0D0D0", "#2E2E2E"]


def _esc(t: Any) -> str:
    return sax.escape(str(t if t is not None else ""))


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
    # 计数图 Y 轴整数刻度（0,1,2,…）；max=1 时只显示 0/1（P0-11）
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
    palette = {"okabe_ito": OKABE_ITO, "nature": NATURE, "conservative": CONSERVATIVE}[theme]
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
    return figures


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
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--theme", choices=["okabe_ito", "nature", "conservative"],
                        default="okabe_ito")
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--export-png", action="store_true",
                        help="try matplotlib export to PNG/PDF (optional)")
    args = parser.parse_args()

    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    figure_data = build_figure_data(result)
    figures = render_figures(figure_data, theme=args.theme, lang=args.lang)

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
