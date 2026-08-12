"""Tests for visualization/eduevidence-report/scripts/build_charts.py —
ECharts spec（P0-10 diverging 双道 / P0-11 整数刻度 / 双语 spec）。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"
RESULT_ZH = ROOT / "examples" / "ai-coding-assistant" / "result.zh.json"

from build_charts import build_all  # noqa: E402


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def test_diverging_series_lanes():
    """正/负向效应走主道（xAxisIndex 0），零效应走独立细条道（xAxisIndex 1）。"""
    result = _load("examples/ai-coding-assistant/result.json")
    spec = build_all(result, lang="zh")
    overview = next(c for c in spec["charts"] if c["chart_id"] == "outcome-evidence-overview")
    option = overview["option"]
    series = {s["name"]: s for s in option["series"]}
    assert series["正向效应"]["xAxisIndex"] == 0 and series["正向效应"]["yAxisIndex"] == 0
    assert series["负向效应"]["xAxisIndex"] == 0 and series["负向效应"]["yAxisIndex"] == 0
    assert series["零效应"]["xAxisIndex"] == 1 and series["零效应"]["yAxisIndex"] == 1
    assert series["零效应"].get("barWidth")  # 细条


def test_diverging_sign_encoding():
    """正向 ≥ 0、负向 ≤ 0、零效应 ≥ 0；数字与 result 的 effect_direction 聚合一致。"""
    result = _load("examples/ai-coding-assistant/result.json")
    spec = build_all(result, lang="zh")
    overview = next(c for c in spec["charts"] if c["chart_id"] == "outcome-evidence-overview")
    series = {s["name"]: s["data"] for s in overview["option"]["series"]}
    # effect_direction 聚合：每个 outcome 按 direction 计数（负向为负数）
    from collections import Counter
    for o in result["outcomes"]:
        rel_ev = [e for e in result["evidence"] if e["outcome_type"] == o["outcome_type"]]
        dirs = Counter(e.get("effect_direction", "null") for e in rel_ev)
        idx = result["outcomes"].index(o)
        assert series["正向效应"][idx] == dirs.get("positive", 0)
        assert series["负向效应"][idx] == -dirs.get("negative", 0)
        assert series["零效应"][idx] == dirs.get("null", 0)
        assert series["正向效应"][idx] >= 0 and series["负向效应"][idx] <= 0 and series["零效应"][idx] >= 0


def test_count_axis_integer_ticks():
    """P0-11：计数轴 minInterval=1（0,1,2…），避免伪精度。"""
    result = _load("examples/ai-coding-assistant/result.json")
    for lang in ("zh", "en"):
        spec = build_all(result, lang=lang)
        overview = next(c for c in spec["charts"] if c["chart_id"] == "outcome-evidence-overview")
        option = overview["option"]
        for ax in option["xAxis"]:
            assert ax.get("minInterval") == 1, f"{lang}: count axis must be integer ticks"
        # 中性道上限 = vmax 整数，避免小数刻度
        neutral_ax = option["xAxis"][1]
        assert float(neutral_ax["max"]) == int(neutral_ax["max"])


def test_benchmark_axes_are_fractions_not_counts():
    """benchmark 是比例（0-1），不该被强制整数刻度。"""
    result = _load("examples/ai-coding-assistant/result.json")
    spec = build_all(result, lang="zh")
    panel = spec["benchmark"]
    assert panel["option"]["yAxis"]["max"] == 1
    assert panel["option"]["yAxis"]["min"] == 0


def test_bilingual_specs_same_numbers():
    """双语 spec：系列名随语言，数字必须一致。"""
    en = _load("examples/ai-coding-assistant/result.json")
    zh = _load("examples/ai-coding-assistant/result.zh.json")
    spec_zh = build_all(zh, lang="zh")
    spec_en = build_all(en, lang="en")
    ov_zh = next(c for c in spec_zh["charts"] if c["chart_id"] == "outcome-evidence-overview")
    ov_en = next(c for c in spec_en["charts"] if c["chart_id"] == "outcome-evidence-overview")
    assert ov_zh["title"] == "结果证据概览" and ov_en["title"] == "Outcome Evidence Overview"
    data_zh = {s["name"]: s["data"] for s in ov_zh["option"]["series"]}
    data_en = {s["name"]: s["data"] for s in ov_en["option"]["series"]}
    for zh_name, en_name in (("正向效应", "Positive effect"), ("负向效应", "Negative effect"),
                             ("零效应", "Null effect")):
        assert data_zh[zh_name] == data_en[en_name]


def test_claim_trace_binds_all_ids():
    """trace 图的节点必须覆盖 claims/evidence，以及被 evidence 引用的 sources。"""
    result = _load("examples/ai-coding-assistant/result.json")
    spec = build_all(result, lang="en")
    trace = next(c for c in spec["charts"] if c["chart_id"] == "claim-evidence-trace")
    nodes = {n["id"] for n in trace["option"]["series"][0]["data"]}
    for ev in result["evidence"]:
        assert ev["evidence_id"] in nodes
        # evidence 引用的来源必须出现在图中
        if ev.get("source_id"):
            assert ev["source_id"] in nodes
