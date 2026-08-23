#!/usr/bin/env python3
"""charts_data.py — The ONLY numeric source for Lieflat gallery charts.

Every extractor reads result.json and returns a normalized, JSON-serializable
data bundle whose values can all be traced back to result.json. When the data
is insufficient for an honest encoding, the extractor returns (None, reason)
and the caller suppresses the chart (mirrors the Meaningful Visualization Gate).

Honesty rules (per the Lieflat Charts codex):
  - Never invent units or per-record values that do not exist in result.json.
  - Declare derived statistics in the bundle so renderers can state them in
    the subtitle (e.g. position = net direction share).
  - Area encodings receive raw values; renderers apply sqrt, never here.

Bundles are language-neutral (raw keys); `lang` only affects display labels.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from zh_labels import label as _label, OUTCOME_ZH as _OUTCOME_ZH, OUTCOME_EN as _OUTCOME_EN, STUDY_ZH as _STUDY_ZH

# Methodology audit item display labels (local copy — charts_data must not
# import build_report, which imports the renderers that import this module).
_AUDIT_ZH = {
    "control_group": "对照组", "randomization": "随机分配", "pre_test": "前测",
    "post_test": "后测", "retention_test": "保持测试", "transfer_test": "迁移测试",
    "sample_bias": "样本偏差", "self_selection": "自我选择偏差",
    "measurement_validity": "测量效度", "confounders": "混杂因素",
    "instructor_effect": "教师效应", "novelty_effect": "新奇效应",
    "tool_version_effect": "工具版本效应", "ai_usage_policy": "AI 使用规则",
    "dropout": "样本流失",
}
_AUDIT_EN = {
    "control_group": "Control group", "randomization": "Randomization", "pre_test": "Pre-test",
    "post_test": "Post-test", "retention_test": "Retention test", "transfer_test": "Transfer test",
    "sample_bias": "Sample bias", "self_selection": "Self-selection",
    "measurement_validity": "Measurement validity", "confounders": "Confounders",
    "instructor_effect": "Instructor effect", "novelty_effect": "Novelty effect",
    "tool_version_effect": "Tool version effect", "ai_usage_policy": "AI usage policy",
    "dropout": "Dropout",
}

_PHASE_RANGE_EN = re.compile(r"weeks?\s*(\d+)\s*[-–—]\s*(\d+)", re.IGNORECASE)
_PHASE_RANGE_ZH = re.compile(r"第\s*(\d+)\s*[-–—]\s*(\d+)\s*周")
_SPAN_RE = re.compile(r"(\d+)\s*[-–—]?\s*week", re.IGNORECASE)


def outcome_label(value: str, lang: str) -> str:
    table = _OUTCOME_ZH if lang == "zh" else _OUTCOME_EN
    return table.get(value, value)


def audit_label(key: str, lang: str) -> str:
    table = _AUDIT_ZH if lang == "zh" else _AUDIT_EN
    return table.get(key, key.replace("_", " ").title())


def _num(value: Any) -> Optional[float]:
    """Coerce a scalar to float; None for anything non-numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN guard
        return None
    return f


def _effect_of(ev: dict) -> Optional[dict]:
    """Return the effect-size dict of an evidence item, if numeric."""
    es = ev.get("effect_size")
    if isinstance(es, dict):
        g = _num(es.get("value"))
        if g is None:
            return None
        return {
            "g": g,
            "ci_lower": _num(es.get("ci_lower")),
            "ci_upper": _num(es.get("ci_upper")),
            "p_value": _num(es.get("p_value")),
            "metric": es.get("metric") or "effect size",
        }
    g = _num(es)
    if g is None:
        return None
    return {"g": g, "ci_lower": None, "ci_upper": None, "p_value": None, "metric": "effect size"}


def _short_label(ev: dict) -> str:
    """Short human label for a study: author surname first, else ID."""
    raw = ev.get("study_label") or ev.get("study_id") or ev.get("evidence_id") or "study"
    text = str(raw).strip()
    if "(" in text:
        text = text.split("(")[0]
    if "," in text and re.match(r"^[A-Za-z]", text):
        text = text.split(",")[0]
    return text.strip()[:24]


# ---------------------------------------------------------------------------
# meta.forest — forest plot (Hedges' g + CI per study, optional pooled)
# ---------------------------------------------------------------------------

def extract_meta_forest(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    studies: list[dict] = []
    meta = result.get("meta") or {}
    forest = meta.get("forest") or {}
    fpd = forest.get("forest_plot_data") if isinstance(forest, dict) else None
    if isinstance(fpd, list) and fpd:
        for row in fpd:
            if not isinstance(row, dict):
                continue
            g = _num(row.get("effect_size") if isinstance(row.get("effect_size"), (int, float))
                     else (row.get("effect_size") or {}).get("value"))
            if g is None:
                continue
            studies.append({
                "label": str(row.get("study_label") or "study"),
                "dimension": str(row.get("outcome_dimension") or row.get("outcome_type") or "GENERAL"),
                "g": g,
                "ci_lower": _num(row.get("ci_lower")),
                "ci_upper": _num(row.get("ci_upper")),
                "n": _num(row.get("sample_size")),
                "wwc": row.get("wwc_rating"),
            })
    else:
        for ev in result.get("evidence") or []:
            if not isinstance(ev, dict):
                continue
            fx = _effect_of(ev)
            if fx is None:
                continue
            studies.append({
                "label": _short_label(ev),
                "dimension": str(ev.get("outcome_dimension") or ev.get("outcome_type") or "GENERAL"),
                "g": fx["g"],
                "ci_lower": fx["ci_lower"],
                "ci_upper": fx["ci_upper"],
                "n": _num(ev.get("sample_size")),
                "wwc": ev.get("wwc_rating"),
            })
    max_studies = params.get("max_studies", 10)
    studies = sorted(studies, key=lambda s: abs(s["g"]), reverse=True)[:max_studies]
    pooled = None
    if isinstance(forest, dict):
        pv = forest.get("pooled_effect") or forest.get("summary")
        if isinstance(pv, dict):
            g = _num(pv.get("value") if "value" in pv else pv.get("g"))
            if g is not None:
                pooled = {"g": g, "ci_lower": _num(pv.get("ci_lower")), "ci_upper": _num(pv.get("ci_upper"))}
    if len(studies) < 3:
        return None, f"fewer than 3 studies with numeric effect size (got {len(studies)})"
    return {
        "studies": studies,
        "pooled": pooled,
        "unit": "Hedges' g",
        "label_zh": "效应量森林图", "label_en": "Effect-size forest plot",
    }, None


# ---------------------------------------------------------------------------
# evidence.ranked_effects — L2 Dot Cascade
# ---------------------------------------------------------------------------

def extract_ranked_effects(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    rows = []
    for ev in result.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        fx = _effect_of(ev)
        if fx is None:
            continue
        rows.append({"label": _short_label(ev), "g": fx["g"], "n": _num(ev.get("sample_size")),
                     "dimension": str(ev.get("outcome_dimension") or ev.get("outcome_type") or "")})
    if len(rows) < 3:
        return None, f"fewer than 3 studies with numeric effect size (got {len(rows)})"
    rows = sorted(rows, key=lambda r: r["g"], reverse=True)
    limit = int(params.get("limit", 12))
    rows = rows[:max(3, min(limit, 20))]
    return {"studies": rows, "unit": "Hedges' g",
            "label_zh": "效应量梯队", "label_en": "Ranked effect sizes"}, None


# ---------------------------------------------------------------------------
# evidence.year_x_dimension — L9 Bubble Almanac
# ---------------------------------------------------------------------------

def extract_year_x_dimension(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    years: list[str] = []
    dims: list[str] = []
    cells: dict[tuple[str, str], dict] = {}
    for ev in result.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        year = ev.get("year")
        if year is None:
            continue
        y = str(year)
        dim = str(ev.get("outcome_dimension") or ev.get("outcome_type") or "GENERAL")
        if y not in years:
            years.append(y)
        if dim not in dims:
            dims.append(dim)
        cell = cells.setdefault((y, dim), {"n": 0, "sig": 0})
        cell["n"] += 1
        fx = _effect_of(ev)
        if fx and fx.get("p_value") is not None and fx["p_value"] < 0.05:
            cell["sig"] += 1
    if len(years) < 2:
        return None, f"fewer than 2 distinct publication years (got {len(years)})"
    if len(dims) < 2:
        return None, f"fewer than 2 outcome dimensions (got {len(dims)})"
    years = sorted(years)
    grid = []
    for y in years:
        for d in dims:
            c = cells.get((y, d))
            if c:
                grid.append({"year": y, "dim": d, "n": c["n"], "sig": c["sig"]})
    if len(grid) < 3:
        return None, f"fewer than 3 populated year×dimension cells (got {len(grid)})"
    return {"years": years, "dimensions": dims, "cells": grid,
            "unit": "1 study", "label_zh": "年份 × 维度文献年历", "label_en": "Year × dimension almanac"}, None


# ---------------------------------------------------------------------------
# evidence.grouped_distribution — G15 Jitter Strip
# ---------------------------------------------------------------------------

def extract_grouped_distribution(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    groups: dict[str, list[float]] = {}
    for ev in result.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        fx = _effect_of(ev)
        if fx is None:
            continue
        key = str(ev.get("outcome_dimension") or ev.get("outcome_type") or "GENERAL")
        groups.setdefault(key, []).append(fx["g"])
    keep = {k: v for k, v in groups.items() if len(v) >= 3}
    if len(keep) < 2:
        return None, (f"need at least 2 groups with 3+ effect sizes "
                      f"(got {len(keep)} groups: " + ", ".join(f"{k}={len(v)}" for k, v in keep.items()) + ")")
    limit = int(params.get("limit", 60))
    return {"groups": [{"label": k, "values": sorted(v)[:limit]} for k, v in keep.items()],
            "unit": "Hedges' g", "label_zh": "分组效应量分布", "label_en": "Grouped effect distribution"}, None


# ---------------------------------------------------------------------------
# evidence.multidim_top — L20 Parallel Coordinates (g / N / quality / year)
# ---------------------------------------------------------------------------

def extract_multidim_top(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    rows = []
    for ev in result.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        fx = _effect_of(ev)
        q = _num(ev.get("quality_score"))
        y = _num(ev.get("year"))
        n = _num(ev.get("sample_size"))
        if fx is None or q is None or y is None or n is None:
            continue
        rows.append({"label": _short_label(ev), "g": fx["g"], "n": n, "quality": q, "year": y})
    if len(rows) < 3:
        return None, f"fewer than 3 studies with g/N/quality/year (got {len(rows)})"
    rows = sorted(rows, key=lambda r: abs(r["g"]), reverse=True)
    limit = int(params.get("limit", 12))
    rows = rows[:max(3, min(limit, 12))]
    return {
        "axes": [
            {"key": "g", "label_zh": "效应量 g", "label_en": "Effect g"},
            {"key": "n", "label_zh": "样本量 N", "label_en": "Sample N"},
            {"key": "quality", "label_zh": "质量分", "label_en": "Quality"},
            {"key": "year", "label_zh": "发表年份", "label_en": "Year"},
        ],
        "rows": rows,
        "label_zh": "跨维度平行坐标", "label_en": "Parallel coordinates",
    }, None


# ---------------------------------------------------------------------------
# evidence.study_type_composition / evidence.wwc_composition — L14 / F4
# ---------------------------------------------------------------------------

def _composition_counts(result: dict, measure: str) -> list[dict]:
    counts: dict[str, int] = {}
    for ev in result.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        if measure == "wwc":
            value = ev.get("wwc_rating")
        else:
            value = ev.get("study_type") or ev.get("study_design")
        if value in (None, ""):
            continue
        counts[str(value)] = counts.get(str(value), 0) + 1
    return [{"label": k, "count": v} for k, v in sorted(counts.items(), key=lambda kv: -kv[1])]


def extract_study_type_composition(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    cats = _composition_counts(result, "study_type")
    if len(cats) < 2:
        return None, f"fewer than 2 study types recorded (got {len(cats)})"
    total = sum(c["count"] for c in cats)
    if total < 3:
        return None, f"fewer than 3 studies with study type (got {total})"
    return {"categories": cats, "total": total, "unit": "1 study",
            "label_zh": "研究类型构成", "label_en": "Study type composition"}, None


def extract_wwc_composition(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    cats = _composition_counts(result, "wwc")
    if len(cats) < 2:
        return None, f"fewer than 2 WWC ratings recorded (got {len(cats)})"
    total = sum(c["count"] for c in cats)
    if total < 3:
        return None, f"fewer than 3 studies with WWC rating (got {total})"
    return {"categories": cats, "total": total, "unit": "1 study",
            "label_zh": "WWC 评级构成", "label_en": "WWC rating composition"}, None


# ---------------------------------------------------------------------------
# outcomes.direction_counts — F5 Tick Rows / F1 Rung Bars
# ---------------------------------------------------------------------------

def extract_direction_counts(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    rows = []
    for o in result.get("outcomes") or []:
        if not isinstance(o, dict):
            continue
        pos = int(o.get("positive_count") or 0)
        neg = int(o.get("negative_count") or 0)
        nul = int(o.get("null_count") or 0)
        if pos + neg + nul <= 0:
            continue
        key = str(o.get("outcome_type") or f"outcome-{len(rows)}")
        rows.append({"label": key,
                     "label_zh": outcome_label(key, "zh"), "label_en": outcome_label(key, "en"),
                     "positive": pos, "negative": neg, "null": nul})
    wanted = params.get("outcomes")
    if isinstance(wanted, list) and wanted:
        rows = [r for r in rows if r["label"] in [str(w) for w in wanted]]
    if len(rows) < 3:
        return None, f"fewer than 3 outcomes with effect counts (got {len(rows)})"
    return {"rows": rows, "unit": "1 evidence item",
            "label_zh": "结果效应方向分布", "label_en": "Outcome direction counts"}, None


# ---------------------------------------------------------------------------
# outcomes.paired_counts — F6 Paired Rungs
# ---------------------------------------------------------------------------

def extract_paired_counts(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    bundle, reason = extract_direction_counts(result, params, lang)
    if bundle is None:
        return None, reason
    rows = [{"label": r["label"], "label_zh": r["label_zh"], "label_en": r["label_en"],
             "positive": r["positive"], "negative": r["negative"]} for r in bundle["rows"]]
    if sum(1 for r in rows if r["positive"] or r["negative"]) < 2:
        return None, "fewer than 2 outcomes with a positive or negative count"
    return {"rows": rows, "unit": "1 evidence item",
            "label_zh": "正向 vs 负向配对", "label_en": "Positive vs negative pairs"}, None


# ---------------------------------------------------------------------------
# outcomes.bipolar_axes — L7 Brand Spectrum (position = net direction share)
# ---------------------------------------------------------------------------

def extract_bipolar_axes(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    bundle, reason = extract_direction_counts(result, params, lang)
    if bundle is None:
        return None, reason
    axes = []
    for r in bundle["rows"]:
        total = r["positive"] + r["negative"]
        if total <= 0:
            continue
        net = (r["positive"] - r["negative"]) / total  # -1 .. +1
        axes.append({
            "label": r["label"], "label_zh": r["label_zh"], "label_en": r["label_en"],
            "position": round(0.5 + net / 2.0, 4),  # 0 .. 1 bipolar position
            "net": round(net, 4),
            "positive": r["positive"], "negative": r["negative"], "null": r["null"],
        })
    if len(axes) < 2:
        return None, f"fewer than 2 outcomes with direction counts (got {len(axes)})"
    return {"axes": axes,
            "left_zh": "负向主导", "left_en": "Negative-led",
            "right_zh": "正向主导", "right_en": "Positive-led",
            "derived": "position = (positive − negative) ÷ total direction counts",
            "label_zh": "结果双极光谱", "label_en": "Outcome bipolar spectrum"}, None


# ---------------------------------------------------------------------------
# intervention.phase_weeks — L3 Barcode Lollipop (phase membership per week)
# ---------------------------------------------------------------------------

def _phase_ranges(result: dict) -> list[dict]:
    """Parse phase_1..phase_4 week ranges from phase names (zh + en)."""
    inter = result.get("intervention") or {}
    phases = []
    for i in range(1, 5):
        ph = inter.get(f"phase_{i}")
        if not isinstance(ph, dict):
            continue
        name = str(ph.get("name") or "")
        m = _PHASE_RANGE_ZH.search(name) or _PHASE_RANGE_EN.search(name)
        start, end = (int(m.group(1)), int(m.group(2))) if m else (None, None)
        if start is None or end is None or end < start or end - start > 60:
            continue
        phases.append({"index": i, "start": start, "end": end, "name": name,
                       "activities": ph.get("activities") or []})
    return phases


def extract_phase_weeks(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    phases = _phase_ranges(result)
    if len(phases) < 3:
        return None, f"fewer than 3 phases with parseable week ranges (got {len(phases)})"
    first = min(p["start"] for p in phases)
    last = max(p["end"] for p in phases)
    span = last - first + 1
    if span < 8:
        return None, f"phase span too short for a barcode ({span} weeks)"
    weeks = []
    for week in range(first, last + 1):
        owner = next((p["index"] for p in phases if p["start"] <= week <= p["end"]), 0)
        weeks.append({"week": week, "phase": owner})
    peaks = [{"week": p["start"], "phase": p["index"],
              "label_zh": f"第{p['index']}阶段开始", "label_en": f"Phase {p['index']} starts"}
             for p in phases]
    phase_labels = [
        {"phase": p["index"], "label_zh": f"第{p['index']}阶段", "label_en": f"Phase {p['index']}",
         "start": p["start"], "end": p["end"]}
        for p in phases
    ]
    return {
        "weeks": weeks, "peaks": peaks, "phases": phase_labels, "first": first, "last": last,
        "derived": "stem height = phase index (1–4); no per-week activity data exists in result.json",
        "label_zh": "16 周阶段归属", "label_en": "Weekly phase membership",
    }, None


# ---------------------------------------------------------------------------
# intervention.activity_weights — L1 Launch Fan (weight = activity count)
# ---------------------------------------------------------------------------

def extract_activity_weights(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    phases = _phase_ranges(result)
    if not phases:
        # fall back to phase dicts without ranges (still honest: weight = activity count)
        inter = result.get("intervention") or {}
        phases = []
        for i in range(1, 5):
            ph = inter.get(f"phase_{i}")
            if isinstance(ph, dict):
                phases.append({"index": i, "start": None, "end": None,
                               "name": str(ph.get("name") or ""), "activities": ph.get("activities") or []})
    items = []
    for p in phases:
        w = len(p.get("activities") or [])
        if w <= 0:
            continue
        name = p["name"].split(":")[0].split("（")[0].strip()
        items.append({"label": name[:16] or f"phase {p['index']}", "w": w, "index": p["index"]})
    if len(items) < 3:
        return None, f"fewer than 3 phases with activities (got {len(items)})"
    max_items = int(params.get("max_items", 8))
    items = items[:max_items]
    return {"items": items, "unit": "1 activity",
            "derived": "head dot area = number of activities listed for the phase",
            "label_zh": "阶段活动权重扇", "label_en": "Phase activity fan"}, None


# ---------------------------------------------------------------------------
# intervention.phase_groups — L8 Dotty Matrix (1 cell = 1 activity per phase)
# ---------------------------------------------------------------------------

def extract_phase_groups(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    phases = _phase_ranges(result)
    layers = []
    for p in phases:
        acts = p.get("activities") or []
        if len(acts) < 2:
            continue
        cells = [{"r": i % 6, "c": i // 6} for i in range(min(len(acts), 36))]
        name = p["name"].split(":")[0].split("（")[0].strip()
        layers.append({"label": name[:16] or f"phase {p['index']}", "cells": cells, "index": p["index"]})
    if len(layers) < 3:
        return None, f"fewer than 3 phases with 2+ activities (got {len(layers)})"
    return {"layers": layers, "unit": "1 activity",
            "derived": "one dot = one listed activity; intensity is uniform (no mastery data)",
            "label_zh": "阶段活动点阵", "label_en": "Phase activity matrix"}, None


# ---------------------------------------------------------------------------
# decision.confidence_score — F11 Tick Gauge
# ---------------------------------------------------------------------------

def extract_confidence_score(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    decision = result.get("decision") or {}
    score = _num(decision.get("confidence_score"))
    if score is None:
        return None, "decision.confidence_score missing or non-numeric"
    score = max(0.0, min(1.0, score))
    return {"score": round(score, 4), "label": str(decision.get("confidence") or ""),
            "label_zh": "决策置信度", "label_en": "Decision confidence"}, None


# ---------------------------------------------------------------------------
# methodology.flag_rates — L15 Ballot Tally (1 tick = 1 audit verdict)
# ---------------------------------------------------------------------------

def extract_flag_rates(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    # tally per audit item: how many review entries mark it below "met"
    tally: dict[str, dict] = {}
    for review in result.get("methodology_reviews") or []:
        if not isinstance(review, dict):
            continue
        items = review.get("audit_items") or {}
        if not isinstance(items, dict):
            continue
        for key, entry in items.items():
            status = (entry or {}).get("status") if isinstance(entry, dict) else None
            if status is None:
                continue
            slot = tally.setdefault(key, {"total": 0, "flagged": 0})
            slot["total"] += 1
            if str(status).lower() not in ("met", "pass", "passed", "satisfied"):
                slot["flagged"] += 1
    items = [{"key": k, "total": v["total"], "flagged": v["flagged"]} for k, v in tally.items()]
    items = [i for i in items if i["total"] >= 1]
    if len(items) < 3 or not any(i["flagged"] for i in items):
        return None, (f"audit tally insufficient for a ballot ({len(items)} items, "
                      f"{sum(i['flagged'] for i in items)} flagged)")
    items = sorted(items, key=lambda i: (-i["flagged"] / i["total"], -i["total"]))
    out = []
    for i in items:
        out.append({"label": i["key"],
                    "label_zh": audit_label(i["key"], "zh"), "label_en": audit_label(i["key"], "en"),
                    "total": i["total"], "flagged": i["flagged"]})
    return {"items": out, "unit": "1 audit verdict",
            "derived": "one tick = one methodology-review verdict; filled = below 'met'",
            "label_zh": "审计未达标计票", "label_en": "Audit flag tally"}, None


# ---------------------------------------------------------------------------
# evidence.year_x_outcome_counts — L16 Matrix Heat
# ---------------------------------------------------------------------------

def extract_year_x_outcome_counts(result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    years: list[str] = []
    outcomes: list[str] = []
    counts: dict[tuple[str, str], int] = {}
    for ev in result.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        year = ev.get("year")
        if year is None:
            continue
        y = str(year)
        o = str(ev.get("outcome_dimension") or ev.get("outcome_type") or "GENERAL")
        if y not in years:
            years.append(y)
        if o not in outcomes:
            outcomes.append(o)
        counts[(y, o)] = counts.get((y, o), 0) + 1
    if len(years) < 2:
        return None, f"fewer than 2 years (got {len(years)})"
    if len(outcomes) < 2:
        return None, f"fewer than 2 outcomes (got {len(outcomes)})"
    years = sorted(years)
    cells = [[counts.get((y, o), 0) for y in years] for o in outcomes]
    return {"years": years,
            "outcomes": [{"label": o, "label_zh": outcome_label(o, "zh"), "label_en": outcome_label(o, "en")}
                         for o in outcomes],
            "cells": cells, "unit": "1 study",
            "label_zh": "年份 × 结果计数矩阵", "label_en": "Year × outcome count matrix"}, None


# ---------------------------------------------------------------------------
# Dispatcher — used by lieflat_engine.REGISTRY
# ---------------------------------------------------------------------------

EXTRACTORS = {
    "meta.forest": extract_meta_forest,
    "evidence.ranked_effects": extract_ranked_effects,
    "evidence.year_x_dimension": extract_year_x_dimension,
    "evidence.grouped_distribution": extract_grouped_distribution,
    "evidence.multidim_top": extract_multidim_top,
    "evidence.study_type_composition": extract_study_type_composition,
    "evidence.wwc_composition": extract_wwc_composition,
    "outcomes.direction_counts": extract_direction_counts,
    "outcomes.paired_counts": extract_paired_counts,
    "outcomes.bipolar_axes": extract_bipolar_axes,
    "intervention.phase_weeks": extract_phase_weeks,
    "intervention.activity_weights": extract_activity_weights,
    "intervention.phase_groups": extract_phase_groups,
    "decision.confidence_score": extract_confidence_score,
    "methodology.flag_rates": extract_flag_rates,
    "evidence.year_x_outcome_counts": extract_year_x_outcome_counts,
}


def run_extractor(source: str, result: dict, params: dict, lang: str = "en") -> tuple[Optional[dict], Optional[str]]:
    fn = EXTRACTORS.get(source)
    if fn is None:
        return None, f"unknown extractor source {source!r}"
    try:
        return fn(result, params or {}, lang)
    except Exception as exc:  # extractors must never crash the report
        return None, f"extractor error: {type(exc).__name__}: {exc}"
