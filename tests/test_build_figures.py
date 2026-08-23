"""Tests for visualization/eduevidence-report/scripts/build_figures.py —
学术图：Figure 1 为 Outcome × Direction 三色分组（P0-12），计数轴整数刻度（P0-11），
双语标题/图例/说明（P0-13 扩展）。
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"

from build_figures import build_figure_data, render_figures  # noqa: E402


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_figure1_has_three_direction_series():
    """P0-12：主图必须是 Outcome × effect_direction（positive/negative/null 三色分组）。"""
    data = build_figure_data(_load("examples/ai-coding-assistant/result.json"))
    zh = render_figures(data, lang="zh")["outcome-comparison.svg"]
    en = render_figures(data, lang="en")["outcome-comparison.svg"]
    # 三种图例
    for name in ("正向效应", "负向效应", "零效应"):
        assert name in zh
    for name in ("Positive effect", "Negative effect", "Null effect"):
        assert name in en
    # 不止 support_count：每个结果应有非零方向的柱（demo：5 结果共 6 条非零聚合计数）
    rects = re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="[\d.]+" height="[\d.]+" '
                       r'fill="(#[0-9A-Fa-f]{6})"', zh)
    assert len(rects) >= 6, "Figure 1 must draw positive/negative/null bars"


def test_figure1_counts_match_result():
    """图 1 各方向柱值必须等于 result 的 effect_direction 聚合计数。"""
    result = _load("examples/ai-coding-assistant/result.json")
    data = build_figure_data(result)
    zh = render_figures(data, lang="zh")["outcome-comparison.svg"]
    labels = re.findall(r'<text x="[\d.]+" y="[\d.]+" text-anchor="middle" font-size="9" '
                        r'fill="#333">(\d+)</text>', zh)
    values = [int(v) for v in labels]
    # 预期：每个 outcome 的 positive/negative/null 非零计数（按 outcome 顺序展平）
    expected = []
    for o in data["outcomes"]:
        for k in ("positive_count", "negative_count", "null_count"):
            if o.get(k, 0) > 0:
                expected.append(o[k])
    assert values == expected, f"{values} != {expected}"


def test_figure1_integer_tick_labels():
    """P0-11：计数图 Y 轴刻度为整数（0,1,2…），不得出现小数刻度。"""
    data = build_figure_data(_load("examples/ai-coding-assistant/result.json"))
    zh = render_figures(data, lang="zh")["outcome-comparison.svg"]
    ticks = re.findall(r'<text x="62" y="[\d.]+" text-anchor="end" font-size="9" '
                       r'fill="#666">([^<]+)</text>', zh)
    assert ticks, "y tick labels not found"
    for t in ticks:
        assert t.isdigit(), f"non-integer tick: {t!r}"


def test_figure_titles_and_captions_bilingual():
    data = build_figure_data(_load("examples/ai-coding-assistant/result.json"))
    zh = render_figures(data, lang="zh")
    en = render_figures(data, lang="en")
    assert "各结果类型的正向 / 负向 / 零效应证据条数" in zh["outcome-comparison.svg"]
    assert "Counts of positive / negative / null effects" in en["outcome-comparison.svg"]
    assert "图 1." in zh["outcome-comparison.svg"]
    assert "Fig. 1." in en["outcome-comparison.svg"]


def test_benchmark_figures_present():
    """benchmark 存在基线时生成两张学术图（demo 数据无基线则跳过）。"""
    data = build_figure_data(_load("examples/ai-coding-assistant/result.json"))
    if not data.get("benchmark_baselines"):
        data = {
            "outcomes": data["outcomes"],
            "benchmark_baselines": {
                "B0": {"citation_support_precision": 0.4, "usage": {"cost_usd": 0.1}},
                "B3": {"citation_support_precision": 0.9, "usage": {"cost_usd": 1.2}},
            },
            "confidence": data["confidence"],
            "recommended_action": data["recommended_action"],
        }
    figures = render_figures(data, lang="zh")
    assert "benchmark-citation-support.svg" in figures
    assert "benchmark-quality-cost.svg" in figures


def test_lieflat_renders_only_validated_layout_entries():
    """Lieflat 部分只渲染 resolve_visual_layout 校验通过的条目，键用条目 chart_id。"""
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "visualization" / "eduevidence-report" / "scripts"))
    import build_report as _br
    import build_figures as _bf
    result = _load("examples/ai-coding-assistant-50/result.json")
    layout = _br.resolve_visual_layout(result)
    figures, meta = _bf.render_lieflat_gallery(result, "claude", "zh", layout["entries"])
    selected_ids = [s["chart_id"] for s in meta["selected"]]
    assert set(figures.keys()) == set(selected_ids)
    for cid, svg in figures.items():
        assert svg.startswith("<svg"), cid
        assert 'class="lf-pop"' in svg or 'class="lf-fade"' in svg or 'class="lf-draw"' in svg
