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
    """P0-12：主图必须是 Outcome × Direction（support/contradict/neutral 三色分组）。"""
    data = build_figure_data(_load("examples/ai-coding-assistant/result.json"))
    zh = render_figures(data, lang="zh")["outcome-comparison.svg"]
    en = render_figures(data, lang="en")["outcome-comparison.svg"]
    # 三种图例
    for name in ("支持", "反驳", "中性"):
        assert name in zh
    for name in ("Support", "Contradict", "Neutral"):
        assert name in en
    # 不止 support_count：每个结果应有非零方向的柱（demo：5 结果共 9 条非零计数）
    rects = re.findall(r'<rect x="[\d.]+" y="[\d.]+" width="[\d.]+" height="[\d.]+" '
                       r'fill="(#[0-9A-Fa-f]{6})"', zh)
    assert len(rects) >= 6, "Figure 1 must draw support/contradict/neutral bars"


def test_figure1_counts_match_result():
    """图 1 各方向柱值必须等于 result 计数。"""
    result = _load("examples/ai-coding-assistant/result.json")
    data = build_figure_data(result)
    zh = render_figures(data, lang="zh")["outcome-comparison.svg"]
    labels = re.findall(r'<text x="[\d.]+" y="[\d.]+" text-anchor="middle" font-size="9" '
                        r'fill="#333">(\d+)</text>', zh)
    values = [int(v) for v in labels]
    expected = [n for o in result["outcomes"] for n in
                (o["support_count"], o["contradict_count"], o["neutral_count"]) if n > 0]
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
    assert "各结果类型的方向证据分布" in zh["outcome-comparison.svg"]
    assert "Direction of evidence by outcome type" in en["outcome-comparison.svg"]
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
