#!/usr/bin/env python3
"""build_charts.py — ECharts chart-spec generator (v5 Iteration 3, §34 router).

From result.json, produce ECharts option specs for the interactive surfaces:
    - Outcome Evidence Overview   (diverging evidence bar)
    - Benchmark panel             (bar + quality-vs-cost scatter)
    - Claim-Evidence Trace        (graph: Decision -> Claim -> Evidence -> Source)

Purpose = interactive_analysis -> engine = echarts (v5 §34). The specs are
plain JSON consumed by the report's ECharts enhancement layer; when ECharts is
unavailable (offline/no JS), the static tables/SVGs still carry the report
(v5 §28 static degradation).

语言：spec 按 lang 生成（系列名/标题/摘要随语言，数字不变）。diverging bar 为真
diverging：support 从中心向右、contradict 从中心向左，neutral 走独立子网格细条道，
三系列互不覆盖（P0-10）；计数轴强制整数刻度 minInterval=1（P0-11）。

Usage:
    python3 visualization/eduevidence-report/scripts/build_charts.py \
        --result examples/ai-coding-assistant/result.json \
        --out examples/ai-coding-assistant/chart_specs.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from adapter_contract import load_result, write_adapter_output
from zh_labels import label

WARM_PALETTE = ["#B8694A", "#5E8A6A", "#A85B53", "#C99A4A", "#8A867E", "#4F7A55"]
OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00",
             "#CC79A7", "#000000"]

TITLES = {
    "zh": {"overview": "结果证据概览", "benchmark": "基准测试：B0-B4",
           "quality_cost": "质量 vs 成本", "trace": "主张-证据追溯"},
    "en": {"overview": "Outcome Evidence Overview", "benchmark": "Benchmark: B0-B4",
           "quality_cost": "Quality vs Cost", "trace": "Claim-Evidence Trace"},
}

SUMMARIES = {
    "zh": {
        "overview": "各 Outcome 的正向 / 负向 / 零效应证据条数对比。这里展示的是 effect_direction，不是“这条证据是否支持某个主张”。",
        "benchmark": "B0-B4 基线在引用支持/无支撑率/反方发现上的对比及质量-成本散点。",
        "trace": "决策→结论→证据→来源 的可追溯图谱；点击节点可追踪支持/反驳路径。",
    },
    "en": {
        "overview": "Positive / negative / null effect-direction evidence counts per outcome. "
                    "This visual encodes effect_direction, not whether evidence supports a claim.",
        "benchmark": "B0-B4 baselines compared on citation support, unsupported rate and "
                     "contradiction discovery, plus the quality-cost scatter.",
        "trace": "Traceable graph Decision → Claim → Evidence → Source; click nodes to follow "
                 "support/contradict paths.",
    },
}


def effect_outcomes(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate evidence by outcome using effect_direction, not relation_to_claim.

    `direction` / `relation_to_claim` answers whether evidence supports a claim. It does
    not say whether the measured outcome improved or worsened. Outcome visuals must use
    `effect_direction` to avoid turning evidence for a harmful effect into a green bar.
    """
    ordered = [o.get("outcome_type", "") for o in result.get("outcomes", []) if o.get("outcome_type")]
    seen = set(ordered)
    for ev in result.get("evidence", []) or []:
        outcome = ev.get("outcome_type") or ""
        if outcome and outcome not in seen:
            ordered.append(outcome)
            seen.add(outcome)

    buckets = {name: {"positive_count": 0, "negative_count": 0, "null_count": 0,
                      "evidence_ids": []} for name in ordered}
    for ev in result.get("evidence", []) or []:
        outcome = ev.get("outcome_type") or ""
        if not outcome:
            continue
        bucket = buckets.setdefault(outcome, {"positive_count": 0, "negative_count": 0,
                                              "null_count": 0, "evidence_ids": []})
        effect = str(ev.get("effect_direction") or "null").lower()
        field = {"positive": "positive_count", "negative": "negative_count",
                 "null": "null_count", "neutral": "null_count"}.get(effect, "null_count")
        bucket[field] += 1
        if ev.get("evidence_id"):
            bucket["evidence_ids"].append(ev["evidence_id"])

    return [{"outcome_type": name, **buckets[name]} for name in ordered if name in buckets]


def outcome_overview(result: dict[str, Any], lang: str = "zh") -> dict[str, Any]:
    """Diverging effect-direction bar: positive right, negative left, null thin lane."""
    outcomes = effect_outcomes(result)
    names = [label(lang, "outcome", o.get("outcome_type", "")) for o in outcomes]
    positive = [o.get("positive_count", 0) for o in outcomes]
    negative = [-o.get("negative_count", 0) for o in outcomes]
    null = [o.get("null_count", 0) for o in outcomes]
    vmax = max([1] + [abs(v) for v in positive + negative + null])
    series_names = (["正向效应", "负向效应", "零效应"] if lang == "zh"
                    else ["Positive effect", "Negative effect", "Null effect"])
    return {
        "chart_id": "outcome-evidence-overview",
        "purpose": "interactive_analysis",
        "engine": "echarts",
        "chart_type": "diverging_bar",
        "semantic_basis": "effect_direction",
        "title": TITLES[lang]["overview"],
        "option": {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": series_names},
            "grid": [
                {"left": 150, "right": 40, "top": 30, "height": "52%"},
                {"left": 150, "right": 40, "top": "70%", "height": "18%"},
            ],
            "xAxis": [
                {"type": "value", "gridIndex": 0, "minInterval": 1},
                {"type": "value", "gridIndex": 1, "min": 0, "max": vmax, "minInterval": 1},
            ],
            "yAxis": [
                {"type": "category", "data": names, "inverse": True, "gridIndex": 0},
                {"type": "category", "data": names, "inverse": True, "gridIndex": 1, "show": False},
            ],
            "series": [
                {"name": series_names[0], "type": "bar", "data": positive,
                 "itemStyle": {"color": "#5E8A6A"}, "xAxisIndex": 0, "yAxisIndex": 0,
                 "lane": "main"},
                {"name": series_names[1], "type": "bar", "data": negative,
                 "itemStyle": {"color": "#A85B53"}, "xAxisIndex": 0, "yAxisIndex": 0,
                 "lane": "main"},
                {"name": series_names[2], "type": "bar", "data": null,
                 "itemStyle": {"color": "#C99A4A"}, "xAxisIndex": 1, "yAxisIndex": 1,
                 "barWidth": 6, "lane": "neutral"},
            ],
        },
        "summary_text": SUMMARIES[lang]["overview"],
        "integrity": {"numbers_match_result": "NOT_CHECKED", "no_axis_distortion": "NOT_CHECKED",
                      "no_false_precision": "NOT_CHECKED", "colorblind_safe": "NOT_CHECKED"},
    }


def benchmark_panel(benchmark: dict[str, Any], lang: str = "zh") -> dict[str, Any]:
    """Benchmark four-chart panel (v5 §20): bar charts + quality-vs-cost scatter."""
    baselines = benchmark.get("baselines", {})
    names = list(baselines.keys())
    citation = [b.get("citation_support_precision", 0) for b in baselines.values()]
    unsupported = [b.get("unsupported_claim_rate", 0) for b in baselines.values()]
    contradiction = [b.get("contradiction_discovery_rate", 0) for b in baselines.values()]
    costs = [b.get("usage", {}).get("cost_usd", 0) for b in baselines.values()]
    return {
        "chart_id": "benchmark-panel",
        "purpose": "interactive_analysis",
        "engine": "echarts",
        "chart_type": "composite",
        "title": TITLES[lang]["benchmark"],
        "option": {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["Citation Support", "Unsupported Rate", "Contradiction"]},
            "grid": {"left": 60, "right": 40},
            "xAxis": {"type": "category", "data": names},
            "yAxis": {"type": "value", "max": 1, "min": 0},
            "series": [
                {"name": "Citation Support", "type": "bar", "data": citation},
                {"name": "Unsupported Rate", "type": "bar", "data": unsupported},
                {"name": "Contradiction", "type": "bar", "data": contradiction},
            ],
        },
        "cost_vs_quality": {
            "chart_id": "benchmark-quality-cost",
            "purpose": "interactive_analysis",
            "engine": "echarts",
            "chart_type": "scatter",
            "title": TITLES[lang]["quality_cost"],
            "option": {
                "tooltip": {"trigger": "item"},
                "xAxis": {"type": "value", "name": "cost (USD)", "min": 0},
                "yAxis": {"type": "value", "name": "citation support", "min": 0, "max": 1},
                "series": [{
                    "type": "scatter",
                    "data": [[c, q, n] for c, q, n in zip(costs, citation, names)],
                }],
            },
        },
        "summary_text": SUMMARIES[lang]["benchmark"],
        "integrity": {"numbers_match_result": "NOT_CHECKED", "no_axis_distortion": "NOT_CHECKED",
                      "no_false_precision": "NOT_CHECKED", "colorblind_safe": "NOT_CHECKED"},
    }


def claim_trace(result: dict[str, Any], lang: str = "zh") -> dict[str, Any]:
    """Claim-Evidence Trace graph (v5 §16 / §41): Decision -> Claim -> Evidence -> Source."""
    evidence = result.get("evidence", [])
    claims = result.get("claims", [])
    sources = result.get("sources", [])
    decision = result.get("decision", {})
    action = decision.get("recommended_action", "insufficient_evidence")

    nodes: list[dict] = []
    edges: list[dict] = []
    node_ids: set[str] = set()

    def add_node(nid: str, name: str, category: int) -> None:
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({"id": nid, "name": name, "category": category})

    add_node("decision", action.upper(), 0)
    for i, claim in enumerate(claims):
        cid = f"claim-{i}"
        add_node(cid, (claim.get("claim") or "")[:40], 1)
        edges.append({"source": "decision", "target": cid})
        for eid in claim.get("evidence_ids", []):
            ev = next((e for e in evidence if e.get("evidence_id") == eid), None)
            if ev:
                add_node(eid, eid, 2)
                direction = ev.get("direction", "neutral")
                edges.append({"source": cid, "target": eid,
                              "label": direction, "lineStyle": {"color": {
                                  "support": "#5E8A6A", "contradict": "#A85B53",
                                  "neutral": "#C99A4A"}.get(direction, "#C99A4A")}})
                sid = ev.get("source_id", "")
                src = next((s for s in sources if s.get("source_id") == sid), None)
                if src:
                    add_node(sid, sid, 3)
                    edges.append({"source": eid, "target": sid})

    return {
        "chart_id": "claim-evidence-trace",
        "purpose": "interactive_analysis",
        "engine": "echarts",
        "chart_type": "graph",
        "title": TITLES[lang]["trace"],
        "option": {
            "tooltip": {"trigger": "item"},
            "legend": {"data": ["Decision", "Claim", "Evidence", "Source"]},
            "series": [{
                "type": "graph",
                "layout": "force",
                "roam": True,
                "draggable": True,
                "categories": [{"name": "Decision"}, {"name": "Claim"},
                               {"name": "Evidence"}, {"name": "Source"}],
                "data": nodes,
                "links": edges,
                "label": {"show": True, "position": "right", "fontSize": 9},
                "lineStyle": {"curveness": 0.15},
            }],
        },
        "summary_text": SUMMARIES[lang]["trace"],
        "integrity": {"numbers_match_result": "NOT_CHECKED", "no_axis_distortion": "NOT_CHECKED",
                      "no_false_precision": "NOT_CHECKED", "colorblind_safe": "NOT_CHECKED"},
    }


def build_all(result: dict[str, Any], lang: str = "zh") -> dict[str, Any]:
    return {
        "charts": [
            outcome_overview(result, lang),
            claim_trace(result, lang),
        ],
        "benchmark": benchmark_panel(result.get("benchmark", {}), lang),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ECharts chart specs from result.json")
    parser.add_argument("--result", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    args = parser.parse_args()

    result = load_result(args.result)
    specs = build_all(result, lang=args.lang)
    write_adapter_output(args.out, "charts", args.result, specs, locale=args.lang)
    print(f"wrote {args.out} (charts={len(specs['charts'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
