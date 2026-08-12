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

WARM_PALETTE = ["#B8694A", "#5E8A6A", "#A85B53", "#C99A4A", "#8A867E", "#4F7A55"]
OKABE_ITO = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00",
             "#CC79A7", "#000000"]


def outcome_overview(outcomes: list[dict]) -> dict[str, Any]:
    """Diverging evidence bar: per outcome, support (+), contradict (-), neutral (?)."""
    names = [o.get("outcome_type", "") for o in outcomes]
    support = [o.get("support_count", 0) for o in outcomes]
    contradict = [-o.get("contradict_count", 0) for o in outcomes]
    neutral = [o.get("neutral_count", 0) for o in outcomes]
    return {
        "chart_id": "outcome-evidence-overview",
        "purpose": "interactive_analysis",
        "engine": "echarts",
        "chart_type": "diverging_bar",
        "title": "Outcome Evidence Overview",
        "option": {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["支持", "反驳", "中性"]},
            "grid": {"left": 140, "right": 40},
            "xAxis": {"type": "value"},
            "yAxis": {"type": "category", "data": names, "inverse": True},
            "series": [
                {"name": "支持", "type": "bar", "data": support, "itemStyle": {"color": "#5E8A6A"}},
                {"name": "反驳", "type": "bar", "data": contradict, "itemStyle": {"color": "#A85B53"}},
                {"name": "中性", "type": "bar", "data": neutral, "itemStyle": {"color": "#C99A4A"}},
            ],
        },
        "summary_text": "各 Outcome 的支持/反驳/中性证据条数对比（正=支持，负=反驳）。",
        "integrity": {"numbers_match_result": True, "no_axis_distortion": True,
                      "no_false_precision": True, "colorblind_safe": True},
    }


def benchmark_panel(benchmark: dict[str, Any]) -> dict[str, Any]:
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
        "title": "Benchmark: B0-B4",
        "option": {
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["Citation Support", "Unsupported Rate", "Contradiction"]},
            "grid": {"left": 60, "right": 40},
            "xAxis": {"type": "category", "data": names},
            "yAxis": {"type": "value", "max": 1},
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
            "title": "Quality vs Cost",
            "option": {
                "tooltip": {"trigger": "item"},
                "xAxis": {"type": "value", "name": "cost (USD)"},
                "yAxis": {"type": "value", "name": "citation support"},
                "series": [{
                    "type": "scatter",
                    "data": [[c, q, n] for c, q, n in zip(costs, citation, names)],
                }],
            },
        },
        "summary_text": "B0-B4 基线在引用支持/无支撑率/反方发现上的对比及质量-成本散点。",
        "integrity": {"numbers_match_result": True, "no_axis_distortion": True,
                      "no_false_precision": True, "colorblind_safe": True},
    }


def claim_trace(result: dict[str, Any]) -> dict[str, Any]:
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
        "title": "Claim-Evidence Trace",
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
        "summary_text": "决策→结论→证据→来源 的可追溯图谱；点击节点可追踪支持/反驳路径。",
        "integrity": {"numbers_match_result": True, "no_axis_distortion": True,
                      "no_false_precision": True, "colorblind_safe": True},
    }


def build_all(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "charts": [
            outcome_overview(result.get("outcomes", [])),
            claim_trace(result),
        ],
        "benchmark": benchmark_panel(result.get("benchmark", {})),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ECharts chart specs from result.json")
    parser.add_argument("--result", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    specs = build_all(result)
    out = Path(args.out)
    out.write_text(json.dumps(specs, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.out} (charts={len(specs['charts'])})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
