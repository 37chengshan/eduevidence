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

FIXTURE = ROOT / "examples" / "ai-coding-assistant-evidence" / "result.json"
FIXTURE_13 = ROOT / "examples" / "ai-coding-assistant" / "result.json"
# 数值型夹具：旗舰包为真实文献，摘要不暴露 g/SE 时 effect_size 按策略留空；
# g/CI 的格式与追溯正确性用带完整数值的（已打 SYNTHETIC 徽章的）演示包验证。
FIXTURE_NUMERIC = ROOT / "tests" / "fixtures" / "legacy-examples" / "highschool-math-ai-tutor" / "result.json"
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
    result = _load(FIXTURE_NUMERIC)
    bundle, reason = CD.extract_ranked_effects(result, {}, "en")
    assert bundle is not None, reason
    source = {}
    for ev in result["evidence"]:
        es = ev.get("effect_size")
        if isinstance(es, dict) and es.get("value") is not None:
            val = (float(es["value"]), float(ev.get("sample_size") or 0))
            # 提取器标签回退链：study_label → study_id → evidence_id
            for key in (ev.get("study_label"), ev.get("study_id"), ev.get("evidence_id")):
                if key:
                    source[key] = val
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
    result = _load(FIXTURE_NUMERIC)
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
    """An explicitly requested chart with too little data is suppressed WITH a reason.

    The data-driven fallback only offers shapes the data already supports, so it
    cannot report a suppression by construction; suppression has to be exercised
    through an explicit layout - which is exactly the case that matters, because
    a reader following an AI-written visual_layout needs to know why a requested
    chart is absent.
    """
    result = _load(FIXTURE_13)
    result["visual_layout"] = [{
        "type": "forest_plot",
        "title_zh": "效应量森林图", "title_en": "Forest plot",
        "subtitle_zh": "逐研究 g 与 CI", "subtitle_en": "Per-study g with CI",
    }]
    layout = BR.resolve_visual_layout(result)
    assert layout["fallback"] is False
    figures, meta = BF.render_lieflat_gallery(result, "claude", "zh", layout["entries"])
    assert meta["suppressed"], "a requested chart with too little data must be recorded"
    for s in meta["suppressed"]:
        assert s["reason"], "every suppression carries a reason"


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
    # The fallback is data-driven: it probes the registry and keeps only the
    # shapes this result can support (one per data source, capped at six),
    # instead of a fixed quartet that suppressed most charts on packs without
    # numeric effect sizes. Assert the contract, not one frozen combination.
    types = [e["type"] for e in layout["entries"]]
    assert types, "fallback must select at least one supported chart"
    assert len(types) <= 6, "fallback is capped at six charts"
    assert len(set(types)) == len(types), "fallback never repeats a chart type"
    registry = {name for name in LE.REGISTRY} if "LE" in dir() else None
    from lieflat_engine import REGISTRY as _REGISTRY
    assert set(types) <= set(_REGISTRY), f"unknown chart type selected: {types}"


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


# ---------------------------------------------------------------------------
# 9. 几何防线：任何画布外的绘制都必须失败，而不是被浏览器裁掉
# ---------------------------------------------------------------------------

FIXTURE_DIRS = (
    ROOT / "examples",
    ROOT / "tests" / "fixtures" / "legacy-examples",
)


def _fixture_results():
    """每个真实 result*.json 夹具（旗舰包 + 旧演示包）。"""
    seen, out = set(), []
    for base in FIXTURE_DIRS:
        for path in sorted(base.glob("**/result*.json")):
            if path not in seen:
                seen.add(path)
                out.append(path)
    return out


def _render_all(path, lang):
    result = _load(path)
    for fig_type, reg in LE.REGISTRY.items():
        bundle, _reason = reg["extractor"](result, {}, lang)
        if bundle is None:
            continue
        yield fig_type, LE.render_figure(
            fig_type, bundle, "claude",
            {"lang": lang, "title": "T", "subtitle": "S"}, audit=[])


def test_geometry_overflow_raises():
    """越界图必须抛错：固定画布 + 行数由数据决定就是被裁的那一类。"""
    overflowing = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 300">'
        '<circle cx="150" cy="318" r="7.5"/></svg>'
    )
    assert LE.geometry_overflows(overflowing), "the guard must see the escape"
    with pytest.raises(LE.GeometryOverflowError) as excinfo:
        LE.check_geometry(overflowing, "brand_spectrum")
    message = str(excinfo.value)
    assert "brand_spectrum" in message, "错误信息必须含图类型"
    # 错误信息必须给到越界元素的坐标（圆心 318 + r 7.5 = 325.5）
    assert "325.5" in message and "25.5px" in message, message
    # GeometryOverflowError 是 ValueError 子类：gallery 会记录抑制原因后继续
    assert issubclass(LE.GeometryOverflowError, ValueError)


def test_overflow_bundle_raises_through_render_figure(monkeypatch):
    """数据驱动的行数撞上固定画布：render_figure 必须当场报错，不是静默裁掉。"""
    bundle = {"rows": [{"label": f"r{i}"} for i in range(12)]}

    def fixed_canvas_renderer(b, theme, meta, audit=None):
        """The regression shape: 300px canvas, one 46px row per data item."""
        p = LE.get_theme(theme)
        out = LE._svg_open(p, 540, 300, "overflow probe")
        for i, row in enumerate(b["rows"]):
            out.append(f'<text x="30" y="{88 + i * 46}" font-size="9">{row["label"]}</text>')
        out.append("</svg>")
        return "\n".join(out)

    monkeypatch.setitem(LE.REGISTRY, "overflow_probe",
                        {"catalog_ref": "probe", "source": "probe",
                         "extractor": lambda result, params, lang: (bundle, None),
                         "renderer": fixed_canvas_renderer, "params": {}})
    with pytest.raises(LE.GeometryOverflowError) as excinfo:
        LE.render_figure("overflow_probe", bundle, "claude", {"lang": "en", "title": "T"})
    message = str(excinfo.value)
    assert "overflow_probe" in message, "错误信息必须含图类型"
    assert "y=" in message and "outside" in message, message

    # 同一 bundle 用会成长的画布渲染就不再越界 —— 防线针对几何，不针对数据
    def growing_canvas_renderer(b, theme, meta, audit=None):
        p = LE.get_theme(theme)
        body = [f'<text x="30" y="{88 + i * 46}" font-size="9">{row["label"]}</text>'
                for i, row in enumerate(b["rows"])]
        w, h = LE._fit_canvas(body)
        return "\n".join(LE._svg_open(p, w, h, "probe") + body + ["</svg>"])

    monkeypatch.setitem(LE.REGISTRY, "overflow_probe",
                        dict(LE.REGISTRY["overflow_probe"],
                             renderer=growing_canvas_renderer))
    svg = LE.render_figure("overflow_probe", bundle, "claude", {"lang": "en", "title": "T"})
    assert LE.geometry_overflows(svg) == []


def test_render_figure_enforces_geometry_for_every_type():
    """REGISTRY 里每个 type 的渲染结果都必须过防线（合成越界会被抓到）。"""
    entries = {}
    for path in _fixture_results():
        for lang in ("zh", "en"):
            for fig_type, svg in _render_all(path, lang):
                entries.setdefault(fig_type, svg)
    assert set(entries) == set(LE.REGISTRY), \
        f"每个注册类型都要有可渲染夹具: missing {sorted(set(LE.REGISTRY) - set(entries))}"
    for fig_type, svg in entries.items():
        assert LE.geometry_overflows(svg) == [], f"{fig_type} draws outside its viewBox"


@pytest.mark.parametrize("lang", ["zh", "en"])
def test_no_fixture_figure_overflows(lang):
    """现有全部夹具 × 全部图型：没有任何元素落在 viewBox 之外。"""
    checked, offenders = 0, []
    for path in _fixture_results():
        for fig_type, svg in _render_all(path, lang):
            checked += 1
            hits = LE.geometry_overflows(svg)
            if hits:
                offenders.append((path.name, fig_type, max(hits, key=lambda h: h[3])))
    assert checked > 100, f"夹具覆盖太少 ({checked})"
    assert offenders == [], f"overflowing figures: {offenders[:5]}"


def test_dynamic_canvas_never_shrinks_below_design_minimum():
    """动态画布只在装不下时增长：既有形状的比例与最小尺寸不变。"""
    result = _load(FIXTURE)
    bundle, _reason = CD.extract_bipolar_axes(result, {}, "en")
    axis = bundle["axes"][0]
    heights = {}
    for count in (2, 6, 12):
        trimmed = dict(bundle, axes=[dict(axis) for _ in range(count)])
        svg = LE.render_figure("brand_spectrum", trimmed, "claude",
                               {"lang": "en", "title": "T"})
        w, h = (int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
        heights[count] = h
        assert w >= LE.MIN_CANVAS_W and h >= LE.MIN_CANVAS_H
        assert LE.geometry_overflows(svg) == []
    assert heights[2] == LE.MIN_CANVAS_H, "少行数仍用设计最小高度"
    assert heights[12] > heights[6] > heights[2], "行数增加时画布必须跟着长高"


def test_brand_spectrum_six_axis_case_is_whole():
    """用户实测的裁切案例：6 个 axes 时最后一行标签与圆点都要在画布内。"""
    result = _load(FIXTURE)
    bundle, _reason = CD.extract_bipolar_axes(result, {}, "zh")
    assert len(bundle["axes"]) >= 6, "旗舰夹具必须有 6 条双极轴"
    svg = LE.render_figure("brand_spectrum", bundle, "claude",
                           {"lang": "zh", "title": "结果双极光谱"}, audit=[])
    assert LE.geometry_overflows(svg) == []
    w, h = (int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
    assert h > 300, f"6 行必须长高（旧画布 300px 会裁掉最后一行），实际 {h}"
    last_row_y = 88 + 5 * 46
    assert last_row_y + 7.5 <= h, "最后一行圆点必须完整落在画布内"


# ---------------------------------------------------------------------------
# 9. 几何防线：数据量扫描（行数 / 列数 / 标签宽度都随数据变化）
# ---------------------------------------------------------------------------

def _film(fig_type, bundle, lang="en"):
    return LE.render_figure(fig_type, bundle, "claude",
                            {"lang": lang, "title": "T"}, audit=[])


@pytest.mark.parametrize("count", [2, 5, 6, 8, 12, 20, 30])
def test_brand_spectrum_grows_with_axis_count(count):
    """行数由 axes 决定：任何条数都不许被固定画布裁掉。"""
    axis = {"label": "outcome", "position": 0.5, "net": 0.1,
            "positive": 2, "negative": 1, "null": 0}
    svg = _film("brand_spectrum", {"axes": [dict(axis) for _ in range(count)],
                                   "left_en": "neg", "right_en": "pos"})
    assert LE.geometry_overflows(svg) == [], f"{count} axes overflow"
    w, h = (int(v) for v in re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).groups())
    assert w >= LE.MIN_CANVAS_W and h >= LE.MIN_CANVAS_H


@pytest.mark.parametrize("fig_type,bundle", [
    ("bubble_almanac", {"years": [str(2000 + i) for i in range(12)],
                        "dimensions": ["a", "b"],
                        "cells": [{"year": str(2000 + i), "dim": d, "n": 12, "sig": 1}
                                  for i in range(12) for d in ("a", "b")]}),
    ("dotty_matrix", {"layers": [{"label": f"Phase {i}",
                                  "cells": [{"r": r, "c": c}
                                            for r in range(6) for c in range(6)]}
                                 for i in range(6)]}),
    ("dot_cascade", {"studies": [{"label": f"LongStudyName{i}", "g": 0.4 + i * 0.02,
                                  "n": 90 + i} for i in range(20)]}),
    ("tick_rows", {"rows": [{"label": f"o{i}", "positive": 5, "negative": 3,
                             "null": 2} for i in range(14)]}),
    ("rung_bars", {"rows": [{"label": f"o{i}", "positive": 8, "negative": 6,
                             "null": 2} for i in range(14)]}),
    ("paired_rungs", {"rows": [{"label": f"o{i}", "positive": 9, "negative": 7}
                               for i in range(14)]}),
    ("ballot_tally", {"items": [{"label": f"f{i}", "total": 20, "flagged": 4}
                                for i in range(14)]}),
    ("jitter_strip", {"groups": [{"label": f"g{i}", "values": [0.1, 0.4, 0.9]}
                                 for i in range(14)]}),
    ("launch_fan", {"items": [{"label": f"activity-set-{i}", "w": 7 + i}
                              for i in range(10)]}),
    ("hundred_field", {"categories": [{"label": f"cat-{i}", "count": 9}
                                      for i in range(12)]}),
    ("tick_donut", {"total": 60, "categories": [{"label": f"cat-{i}", "count": 15}
                                                for i in range(6)]}),
    ("parallel_coordinates", {
        "axes": [{"key": k, "label_en": k} for k in ("g", "n", "quality", "year")],
        "rows": [{"label": f"s{i}", "g": 0.2, "n": 100, "quality": 7, "year": 2020}
                 for i in range(14)]}),
    ("barcode_lollipop", {
        "weeks": [{"week": w, "phase": (w % 4) + 1} for w in range(1, 121)],
        "peaks": [{"week": 1, "phase": 1, "label_en": "Phase 1 starts"}],
        "phases": [{"phase": 1, "label_en": "Phase 1", "start": 1, "end": 5}],
        "first": 1, "derived": "stem height = phase index"}),
    ("forest_plot", {"studies": [{"label": f"study-{i}", "dimension": "d", "g": 0.3,
                                  "ci_lower": 0.1, "ci_upper": 0.5, "n": 200}
                                 for i in range(12)], "pooled": None}),
    ("tick_gauge", {"score": 0.815, "label": "WWWWWWWWWWWWWWWWWWWWWWWW"}),
    ("bubble_almanac", {"years": ["2020", "2021"], "dimensions": ["a", "b"],
                        "cells": [{"year": "2020", "dim": "a", "n": 900, "sig": 1},
                                  {"year": "2021", "dim": "b", "n": 900, "sig": 1}]}),
    ("ballot_tally", {"items": [{"label": "WWWWWWWWWWWW", "total": 60,
                                 "flagged": 30}]}),
    ("tick_rows", {"rows": [{"label": "WWWWWWWWWWWW", "positive": 60,
                             "negative": 40, "null": 20}]}),
])
def test_dense_and_extreme_data_stays_inside_the_canvas(fig_type, bundle):
    """高密度行数与极端值（巨大气泡、满宽标签、六位数 N）都不许越界。

    这些数据来自 render_* 的对抗性扫描：固定画布 + 数据决定的行数是裁切的
    成因，而防线只在越界时抛错，所以每个图型的边界都要真的走在画布内。
    """
    svg = _film(fig_type, bundle)
    assert LE.geometry_overflows(svg) == [], f"{fig_type} draws outside its viewBox"
