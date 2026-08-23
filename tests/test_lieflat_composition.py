"""tests/test_lieflat_composition.py — Lieflat 组合管线（数据层 + 注册表 + 完整性门）。

覆盖：提取器数值 == result.json、注册表拒绝未知 type、数据不足抑制、
渲染 SVG 不含旧硬编码演示值、visual_layout 新契约校验与 schema 校验、
lieflat_data_bound 溯源门。
"""
import copy
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "visualization" / "eduevidence-report" / "scripts"
sys_mod = __import__("sys")
sys_mod.path.insert(0, str(SCRIPTS))

import charts_data as CD  # noqa: E402
import lieflat_engine as LE  # noqa: E402
import build_figures as BF  # noqa: E402
import build_report as BR  # noqa: E402
from validate_schema import validate  # noqa: E402

FIXTURE = ROOT / "examples" / "ai-coding-assistant-50" / "result.json"
FIXTURE_13 = ROOT / "examples" / "ai-coding-assistant" / "result.json"
LAYOUT_SCHEMA = (ROOT / "visualization" / "eduevidence-report" / "schemas"
                 / "visual-layout.schema.json")

# 旧演示数据（lieflat_engine 重构前的硬编码值）——渲染 SVG 里必须绝迹。
OLD_DEMO_STRINGS = (
    "课后做题卡壳", "Bastani &#x27;25", "Ninety days as a barcode",
    "Twelve features, fanned out", "Four squads, stacked in space",
    "Where the brand sits", "Eight years of tickets", "VanLehn &#x27;25",
    "苏格拉底反问", "阶段熔断机制", "文风千篇一律",
)


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. 提取器数值 == result.json
# ---------------------------------------------------------------------------

def test_ranked_effects_trace_to_evidence():
    """dot_cascade 提取器的 g 与 N 必须等于 evidence.effect_size / sample_size。"""
    result = _load(FIXTURE)
    bundle, reason = CD.extract_ranked_effects(result, {}, "en")
    assert bundle is not None, reason
    source = {}
    for ev in result["evidence"]:
        es = ev.get("effect_size")
        if isinstance(es, dict) and es.get("value") is not None:
            source[ev.get("study_label") or ev.get("evidence_id")] = (
                float(es["value"]), float(ev.get("sample_size") or 0))
    for row in bundle["studies"]:
        label = row["label"]
        match = next((v for k, v in source.items() if k.startswith(label)), None)
        assert match is not None, f"study label {label!r} not traceable to evidence"
        assert abs(row["g"] - match[0]) < 1e-6
        assert abs(row["n"] - match[1]) < 1e-6
    gs = [r["g"] for r in bundle["studies"]]
    assert gs == sorted(gs, reverse=True), "cascade must be sorted by g desc"


def test_direction_counts_trace_to_outcomes():
    result = _load(FIXTURE)
    bundle, reason = CD.extract_direction_counts(result, {}, "en")
    assert bundle is not None, reason
    by_type = {o["outcome_type"]: o for o in result["outcomes"]}
    for row in bundle["rows"]:
        o = by_type[row["label"]]
        assert row["positive"] == o["positive_count"]
        assert row["negative"] == o["negative_count"]
        assert row["null"] == o["null_count"]


def test_confidence_score_traces_to_decision():
    result = _load(FIXTURE)
    bundle, reason = CD.extract_confidence_score(result, {}, "en")
    assert bundle is not None, reason
    assert abs(bundle["score"] - result["decision"]["confidence_score"]) < 1e-6


def test_forest_uses_g_and_ci():
    result = _load(FIXTURE)
    bundle, reason = CD.extract_meta_forest(result, {"max_studies": 6}, "en")
    assert bundle is not None, reason
    assert all(isinstance(s["ci_lower"], float) for s in bundle["studies"])
    source = {CD._short_label(e): e["effect_size"]["value"]
              for e in result["evidence"] if isinstance(e.get("effect_size"), dict)}
    for s in bundle["studies"]:
        assert abs(s["g"] - source[s["label"]]) < 1e-6, \
            f"{s['label']} g={s['g']} not traceable to evidence"


# ---------------------------------------------------------------------------
# 2. 注册表：未知 type 显式报错，不静默回退
# ---------------------------------------------------------------------------

def test_registry_rejects_unknown_type():
    with pytest.raises(ValueError, match="unregistered lieflat chart type"):
        LE.render_figure("pie_chart_3d", {}, "claude", {})


def test_registry_has_spec_types():
    for t in ("forest_plot", "dot_cascade", "bubble_almanac", "jitter_strip",
              "parallel_coordinates", "hundred_field", "tick_donut", "tick_rows",
              "rung_bars", "paired_rungs", "brand_spectrum", "barcode_lollipop",
              "launch_fan", "dotty_matrix", "tick_gauge", "ballot_tally", "matrix_heat"):
        assert t in LE.REGISTRY, t
        assert LE.REGISTRY[t]["catalog_ref"] and LE.REGISTRY[t]["extractor"] and LE.REGISTRY[t]["renderer"]


# ---------------------------------------------------------------------------
# 3. 数据不足 → 抑制并给原因
# ---------------------------------------------------------------------------

def test_extractor_returns_none_with_reason_on_sparse_data():
    sparse = {"meta": {}, "decision": {}, "evidence": [], "outcomes": [],
              "intervention": {}, "methodology_reviews": []}
    for source, fn in CD.EXTRACTORS.items():
        bundle, reason = fn(sparse, {}, "en")
        if bundle is not None:  # 少数提取器对空数据可能给出空 bundle 外的 None
            continue
        assert reason, f"{source} suppressed without a reason"


def test_sparse_fixture_forest_suppressed():
    result = _load(FIXTURE_13)
    bundle, reason = CD.extract_meta_forest(result, {}, "en")
    assert bundle is None and reason


def test_gallery_suppresses_insufficient_charts():
    result = _load(FIXTURE_13)
    layout = BR.resolve_visual_layout(result)
    figures, meta = BF.render_lieflat_gallery(result, "claude", "zh", layout["entries"])
    assert figures, "deterministic fallback must render at least one chart"
    assert meta["suppressed"], "sparse fixture must record suppressed charts with reasons"
    for s in meta["suppressed"]:
        assert s["reason"]


# ---------------------------------------------------------------------------
# 4. 渲染 SVG 无硬编码演示值、无内嵌 <style>、动画类 + stagger
# ---------------------------------------------------------------------------

def test_svg_has_no_old_demo_values_and_no_style():
    result = _load(FIXTURE)
    for fig_type, reg in LE.REGISTRY.items():
        bundle, reason = reg["extractor"](result, {}, "zh")
        if bundle is None:
            continue
        svg = LE.render_figure(fig_type, bundle, "claude",
                               {"lang": "zh", "title": "T", "subtitle": "S",
                                "source": reg["source"]}, audit=[])
        assert "<style>" not in svg, fig_type
        for demo in OLD_DEMO_STRINGS:
            assert demo not in svg, f"{fig_type} still contains demo value {demo!r}"


def test_svg_motion_classes_and_stagger():
    result = _load(FIXTURE)
    bundle, reason = CD.extract_direction_counts(result, {}, "en")
    svg = LE.render_figure("tick_rows", bundle, "claude", {}, audit=[])
    assert 'class="lf-pop"' in svg
    assert "--motion-delay:" in svg
    # 点阵 stagger 用 12ms 步进
    assert "12ms" in svg
    # 数值字重 800
    assert 'font-weight="800"' in svg


def test_area_uses_sqrt():
    """气泡/扇形面积编码必须 sqrt：radius = 3.6·sqrt(n)，而不是 n 本身。"""
    import math
    result = _load(FIXTURE)
    bundle, reason = CD.extract_year_x_dimension(result, {}, "en")
    svg = LE.render_figure("bubble_almanac", bundle, "claude", {}, audit=[])
    assert "math.sqrt" not in svg  # Python 端已换算
    radii = [float(r) for r in re.findall(r'<circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)"', svg)]
    assert radii, "no bubbles drawn"
    max_n = max(c["n"] for c in bundle["cells"])
    max_r = max(radii)
    assert abs(max_r - 3.6 * math.sqrt(max_n)) < 0.6, \
        f"max radius {max_r} should be ≈3.6·sqrt({max_n}), not the raw count"


# ---------------------------------------------------------------------------
# 5. visual_layout 契约：resolve_visual_layout
# ---------------------------------------------------------------------------

def test_resolve_new_contract_entries():
    result = copy.deepcopy(_load(FIXTURE))
    result["visual_layout"] = [{
        "chart_id": "lieflat-gauge.svg", "type": "tick_gauge",
        "catalog_ref": "F11 Tick Gauge",
        "title_zh": "置信度", "title_en": "Confidence",
        "subtitle_zh": "刻度 0–100%", "subtitle_en": "ticks 0–100%",
        "caption_zh": "注", "caption_en": "note",
        "source": "decision.confidence_score", "params": {},
    }]
    layout = BR.resolve_visual_layout(result)
    assert not layout["fallback"] and not layout["rejected"] and not layout["warnings"]
    assert layout["entries"][0]["chart_id"] == "lieflat-gauge.svg"
    assert layout["entries"][0]["title_zh"] == "置信度"


def test_resolve_rejects_unregistered_and_invalid_params():
    result = copy.deepcopy(_load(FIXTURE))
    result["visual_layout"] = [
        {"type": "radar_chart", "title_zh": "a", "title_en": "b",
         "subtitle_zh": "c", "subtitle_en": "d"},
        {"type": "tick_gauge", "title_zh": "a", "title_en": "b",
         "subtitle_zh": "c", "subtitle_en": "d", "params": {"bogus": 1}},
        {"type": "tick_rows", "title_zh": "a", "title_en": "b",
         "subtitle_zh": "c", "subtitle_en": "d", "params": {"outcomes": "notalist"}},
    ]
    layout = BR.resolve_visual_layout(result)
    assert layout["fallback"] is True, "all invalid entries must trigger the safe fallback"
    reasons = " | ".join(r["reason"] for r in layout["rejected"])
    assert "unregistered" in reasons and "not allowed" in reasons and "must be" in reasons


def test_resolve_legacy_contract_with_warning():
    result = copy.deepcopy(_load(FIXTURE))
    result["visual_layout"] = [{"type": "dot_cascade", "title": "梯队", "subtitle": "按 g 排序"}]
    layout = BR.resolve_visual_layout(result)
    assert not layout["fallback"] and not layout["rejected"]
    assert any("legacy" in w for w in layout["warnings"])
    assert layout["entries"][0]["title_zh"] == layout["entries"][0]["title_en"] == "梯队"


def test_resolve_missing_layout_uses_fallback():
    result = copy.deepcopy(_load(FIXTURE))
    result.pop("visual_layout", None)
    layout = BR.resolve_visual_layout(result)
    assert layout["fallback"] is True
    assert [e["type"] for e in layout["entries"]] == ["forest_plot", "dot_cascade",
                                                       "bubble_almanac", "tick_rows"]


def test_academic_chart_id_namespaced():
    result = copy.deepcopy(_load(FIXTURE))
    result["visual_layout"] = [{
        "chart_id": "forest-plot.svg", "type": "forest_plot",
        "title_zh": "a", "title_en": "b", "subtitle_zh": "c", "subtitle_en": "d",
    }]
    layout = BR.resolve_visual_layout(result)
    assert layout["entries"][0]["chart_id"] == "lieflat-forest-plot.svg"


# ---------------------------------------------------------------------------
# 6. visual-layout schema 校验
# ---------------------------------------------------------------------------

def test_visual_layout_schema_accepts_new_contract():
    schema = json.loads(LAYOUT_SCHEMA.read_text(encoding="utf-8"))
    entry = {"type": "tick_gauge", "chart_id": "x.svg", "catalog_ref": "F11 Tick Gauge",
             "title_zh": "t", "title_en": "t", "subtitle_zh": "s", "subtitle_en": "s",
             "source": "decision.confidence_score", "params": {}}
    validate([entry], schema)  # 不抛异常即通过


def test_visual_layout_schema_rejects_unknown_type():
    from validate_schema import SchemaError
    schema = json.loads(LAYOUT_SCHEMA.read_text(encoding="utf-8"))
    entry = {"type": "not_a_chart", "title_zh": "t", "title_en": "t",
             "subtitle_zh": "s", "subtitle_en": "s"}
    with pytest.raises(SchemaError):
        validate([entry], schema)


# ---------------------------------------------------------------------------
# 7. lieflat_data_bound 溯源门
# ---------------------------------------------------------------------------

def test_lieflat_data_bound_passes_for_extractor_renders():
    result = _load(FIXTURE)
    layout = BR.resolve_visual_layout(result)
    _, meta = BF.render_lieflat_gallery(result, "claude", "en", layout["entries"])
    assert meta["selected"]
    problems = BR.check_lieflat_data_bound(meta, "en")
    assert problems == []


def test_lieflat_data_bound_fails_on_tampered_audit():
    result = _load(FIXTURE)
    layout = BR.resolve_visual_layout(result)
    _, meta = BF.render_lieflat_gallery(result, "claude", "en", layout["entries"])
    cid = meta["selected"][0]["chart_id"]
    meta["audits"][cid]["audit"].append(("tampered.value", 3.14159))
    problems = BR.check_lieflat_data_bound(meta, "en")
    assert any(cid in p and "not bound" in p for p in problems)


# ---------------------------------------------------------------------------
# 8. build_figures：只渲染 layout 校验通过的条目
# ---------------------------------------------------------------------------

def test_render_figures_no_unconditional_lieflat():
    result = _load(FIXTURE)
    data = BF.build_figure_data(result)
    figures = BF.render_figures(data, theme="claude", lang="zh")
    assert not [k for k in figures if k.startswith("lieflat-")], \
        "render_figures must not render lieflat charts unconditionally"


def test_render_lieflat_gallery_keys_by_chart_id():
    result = _load(FIXTURE)
    layout = BR.resolve_visual_layout(result)
    figures, meta = BF.render_lieflat_gallery(result, "claude", "zh", layout["entries"])
    for entry in layout["entries"]:
        if any(s["chart_id"] == entry["chart_id"] for s in meta["selected"]):
            assert entry["chart_id"] in figures
