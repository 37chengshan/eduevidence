#!/usr/bin/env python3
"""render_report.py — Render a Research & Decision Pack (plan section 29) to Markdown.

The final output is not a single essay but a Research & Decision Pack:

    01 Executive Decision     06 Conflict Analysis         11 Claim-Evidence Trace
    02 Education Research Frame 07 Evidence Tribunal       12 Sources
    03 Evidence Summary       08 Applicability
    04 Evidence Matrix        09 Teaching Intervention
    05 Methodology Audit      10 Evaluation Plan

Usage:
    python scripts/render_report.py \
        --frame frame.json \
        --evidence evidence.jsonl \
        --verdict verdict.json \
        --intervention intervention.json \
        --evaluation evaluation.json \
        --methodology methodology.json \
        --out REPORT.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence_matrix import evidence_matrix, render_markdown


def load_json(path: Path | None) -> dict | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def section(title: str, body: str) -> str:
    return f"## {title}\n\n{body}\n"


def render_frame(frame: dict) -> str:
    if not frame:
        return "_no frame provided_"
    lines = [f"**问题**: {frame.get('question', '')}",
             f"**决策目标**: {frame.get('decision_target', '')}"]
    for key in ("learner", "course", "intervention", "context", "scope"):
        if frame.get(key):
            lines.append(f"**{key}**: " + ", ".join(
                f"{k}={v}" for k, v in frame[key].items()))
    if frame.get("comparison"):
        lines.append(f"**对照**: {frame['comparison']}")
    if frame.get("success_condition"):
        lines.append(f"**成功条件**: {frame['success_condition']}")
    return "\n".join(lines)


def render_evidence_summary(evidence: list[dict]) -> str:
    if not evidence:
        return "_no evidence provided_"
    by_outcome: dict[str, list[dict]] = {}
    for ev in evidence:
        by_outcome.setdefault(ev.get("outcome_type", "unknown"), []).append(ev)
    lines = []
    for outcome, evs in sorted(by_outcome.items()):
        lines.append(f"### {outcome} ({len(evs)})")
        for ev in evs:
            direction = ev.get("direction", "neutral")
            lines.append(f"- [{direction}] {ev.get('claim', '')} "
                         f"(source={ev.get('source_id', '?')}, quality={ev.get('quality_score', '?')})")
    return "\n".join(lines)


def render_verdict(verdict: dict) -> str:
    if not verdict:
        return "_no verdict provided_"
    action = verdict.get("recommended_action", "")
    lines = [
        f"**决策**: **{action.upper()}**",
        f"**置信度**: {verdict.get('confidence', '')}",
    ]
    if verdict.get("what_can_be_claimed"):
        lines.append("\n**可以主张**:\n" + "\n".join(f"- {c}" for c in verdict["what_can_be_claimed"]))
    if verdict.get("what_cannot_be_claimed"):
        lines.append("\n**不能主张**:\n" + "\n".join(f"- {c}" for c in verdict["what_cannot_be_claimed"]))
    if verdict.get("missing_evidence"):
        lines.append("\n**缺失证据**:\n" + "\n".join(f"- {m}" for m in verdict["missing_evidence"]))
    if verdict.get("exceeds_evidence_boundary"):
        lines.append("\n**超出证据边界**:\n" + "\n".join(f"- {e}" for e in verdict["exceeds_evidence_boundary"]))
    if verdict.get("decision_rationale"):
        lines.append(f"\n**理由**: {verdict['decision_rationale']}")
    return "\n".join(lines)


def render_intervention(intervention: dict) -> str:
    if not intervention:
        return "_no intervention provided_"
    lines = [f"**决策**: {intervention.get('decision', '')}",
             f"**目标学习者**: {intervention.get('target_learners', '')}",
             f"**试点时长**: {intervention.get('pilot_duration', '')}"]
    if intervention.get("ai_usage_policy"):
        lines.append(f"\n**AI 使用规则**: {intervention['ai_usage_policy']}")
    for phase in ("phase_1", "phase_2", "phase_3"):
        if intervention.get(phase):
            p = intervention[phase]
            name = p.get("name", phase)
            lines.append(f"\n**{name}**: {p.get('ai_usage_rule', '')}")
            if p.get("activities"):
                lines.append("\n".join(f"- {a}" for a in p["activities"]))
    if intervention.get("stop_conditions"):
        lines.append("\n**停止条件**:\n" + "\n".join(f"- {s}" for s in intervention["stop_conditions"]))
    return "\n".join(lines)


def render_evaluation(evaluation: dict) -> str:
    if not evaluation:
        return "_no evaluation plan provided_"
    lines = [f"**研究问题**: {evaluation.get('research_question', '')}"]
    groups = evaluation.get("groups", {})
    if groups:
        lines.append(f"**组**: 干预={groups.get('treatment', '')} / 对照={groups.get('comparison', '')}")
    for key, label in (("baseline", "基线"), ("post_test", "后测"), ("retention_test", "保持测试"),
                       ("transfer_test", "迁移测试")):
        if evaluation.get(key):
            lines.append(f"**{label}**: {evaluation[key]}")
    if evaluation.get("success_threshold"):
        lines.append(f"**成功阈值**: {evaluation['success_threshold']}")
    if evaluation.get("stop_conditions"):
        lines.append("\n**停止条件**:\n" + "\n".join(f"- {s}" for s in evaluation["stop_conditions"]))
    return "\n".join(lines)


def render_pack(frame, evidence, methodology, verdict, intervention, evaluation) -> str:
    matrix = evidence_matrix(evidence)
    matrix_md = render_markdown(matrix)

    parts = [
        "# EduEvidence Research & Decision Pack\n",
        section("01 Executive Decision", render_verdict(verdict)),
        section("02 Education Research Frame", render_frame(frame)),
        section("03 Evidence Summary", render_evidence_summary(evidence)),
        section("04 Evidence Matrix", matrix_md),
        section("05 Methodology Audit",
                f"```json\n{json.dumps(methodology, ensure_ascii=False, indent=2)}\n```"
                if methodology else "_no methodology audit provided_"),
        section("09 Teaching Intervention", render_intervention(intervention)),
        section("10 Evaluation Plan", render_evaluation(evaluation)),
    ]
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Research & Decision Pack to Markdown")
    parser.add_argument("--frame")
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--methodology")
    parser.add_argument("--verdict")
    parser.add_argument("--intervention")
    parser.add_argument("--evaluation")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    evidence = load_jsonl(Path(args.evidence))
    md = render_pack(
        load_json(Path(args.frame)) if args.frame else None,
        evidence,
        load_json(Path(args.methodology)) if args.methodology else None,
        load_json(Path(args.verdict)) if args.verdict else None,
        load_json(Path(args.intervention)) if args.intervention else None,
        load_json(Path(args.evaluation)) if args.evaluation else None,
    )
    Path(args.out).write_text(md, encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
