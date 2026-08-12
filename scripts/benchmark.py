#!/usr/bin/env python3
"""benchmark.py — Run the EduEvidence benchmark harness (plan sections 30-36).

First version: 30 questions (S x10, M x10, L x10), with at least 10 gold-annotated
questions. Baselines B0-B4 and ablation A1-A7 are defined here as metadata; actual
LLM runs are executed externally and results stored under benchmarks/results/.

Core metrics computed from result files:
    - Citation Support Precision
    - Unsupported Claim Rate
    - Contradiction Discovery Rate
    - Outcome Separation Accuracy
    - Scope Calibration

Usage:
    python scripts/benchmark.py --questions benchmarks/questions.jsonl
    python scripts/benchmark.py --questions benchmarks/questions.jsonl --results benchmarks/results/sample.json --annotations benchmarks/annotations
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LEVELS = ("S", "M", "L")
DOMAINS = ("ai_higher_education", "teaching_methods", "learning_psychology", "assessment_edtech")
OUTCOME_SET = {
    "knowledge_gain", "concept_understanding", "retention", "transfer",
    "independent_problem_solving", "completion_time", "accuracy",
    "code_quality", "assignment_score", "engagement", "motivation",
    "cognitive_load", "help_seeking", "metacognition", "ai_dependency",
    "over_reliance", "reduced_effort", "reduced_transfer",
    "academic_integrity_risk", "false_confidence",
}
BASELINES = ("B0_direct_llm", "B1_search_llm", "B2_standard_agent",
             "B3_eduevidence_single", "B4_eduevidence_agent_mcp")
ABLATIONS = ("A1_no_skeptic", "A2_no_method_reviewer", "A3_no_tribunal",
             "A4_no_applicability", "A5_no_claim_audit", "A6_no_multi_agent",
             "A7_no_complexity_gate")


def load_questions(path: Path) -> list[dict]:
    questions = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            q = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        questions.append(q)
    return questions


def validate_questions(questions: list[dict]) -> list[str]:
    """Structural validation of the question set. Returns a list of issues (empty = valid)."""
    issues = []
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        issues.append("duplicate question ids")
    if len(questions) < 30:
        issues.append(f"expected >= 30 questions, got {len(questions)}")
    for q in questions:
        if q.get("level") not in LEVELS:
            issues.append(f"{q.get('id')}: bad level {q.get('level')!r}")
        if q.get("domain") not in DOMAINS:
            issues.append(f"{q.get('id')}: bad domain {q.get('domain')!r}")
        for o in q.get("expected_outcomes", []):
            if o not in OUTCOME_SET:
                issues.append(f"{q.get('id')}: bad outcome {o!r}")
    # Level distribution
    for level in LEVELS:
        count = sum(1 for q in questions if q.get("level") == level)
        if count < 10:
            issues.append(f"level {level}: expected >= 10, got {count}")
    # Domain distribution (>= 15 ai_higher_education)
    ai = sum(1 for q in questions if q.get("domain") == "ai_higher_education")
    if ai < 15:
        issues.append(f"domain ai_higher_education: expected >= 15, got {ai}")
    return issues


def metric_citation_support_precision(result: dict) -> float:
    """Proportion of cited sources that truly support the claims they are attached to."""
    cited = result.get("citations", [])
    if not cited:
        return 0.0
    supported = sum(1 for c in cited if c.get("supports_claim") is True)
    return supported / len(cited)


def metric_unsupported_claim_rate(result: dict) -> float:
    """Proportion of important claims that cannot be bound to a reliable source."""
    claims = result.get("claims", [])
    if not claims:
        return 0.0
    unsupported = sum(1 for c in claims if c.get("status") == "UNSUPPORTED")
    return unsupported / len(claims)


def metric_contradiction_discovery(result: dict, annotation: dict) -> float:
    """Fraction of known contradictions (from gold annotation) discovered by the system.

    Semantics: if the gold annotation lists no known contradictions, the metric
    scores 1.0 only when the system also reported none (nothing to find); if the
    system reported contradictions where none are known, that counts as failure.
    Membership test is restricted to string entries (model-generated results may
    contain non-string objects).
    """
    known = annotation.get("known_contradictions", [])
    found = result.get("discovered_contradictions", [])
    found_strings = [f for f in found if isinstance(f, str)]
    if not known:
        return 1.0 if not found else 0.0
    hits = sum(1 for k in known if any(k in f for f in found_strings))
    return hits / len(known)


def metric_outcome_separation(result: dict) -> float:
    """Fraction of evidence rows where outcome_type belongs to the taxonomy and is correctly typed."""
    rows = result.get("evidence", [])
    if not rows:
        return 0.0
    correct = sum(1 for r in rows if r.get("outcome_type") in OUTCOME_SET)
    return correct / len(rows)


def metric_scope_calibration(result: dict) -> float:
    """Fraction of verdicts that do not overstate the scope of the sources."""
    verdicts = result.get("verdicts", [])
    if not verdicts:
        return 0.0
    ok = sum(1 for v in verdicts if not v.get("exceeds_evidence_boundary", False))
    return ok / len(verdicts)


def evaluate(result: dict, annotation: dict | None = None) -> dict:
    """Compute the core metrics for one result (optionally against a gold annotation)."""
    metrics = {
        "citation_support_precision": round(metric_citation_support_precision(result), 3),
        "unsupported_claim_rate": round(metric_unsupported_claim_rate(result), 3),
        "outcome_separation_accuracy": round(metric_outcome_separation(result), 3),
        "scope_calibration": round(metric_scope_calibration(result), 3),
    }
    if annotation is not None:
        metrics["contradiction_discovery_rate"] = round(
            metric_contradiction_discovery(result, annotation), 3)
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="EduEvidence benchmark harness")
    parser.add_argument("--questions", required=True, help="benchmarks/questions.jsonl")
    parser.add_argument("--results", help="optional result JSON to score")
    parser.add_argument("--annotations", help="optional annotations directory")
    args = parser.parse_args()

    questions = load_questions(Path(args.questions))
    issues = validate_questions(questions)
    if issues:
        for issue in issues:
            print(f"ISSUE: {issue}", file=sys.stderr)
        return 1

    dist = {level: sum(1 for q in questions if q["level"] == level) for level in LEVELS}
    print(f"OK: {len(questions)} questions | levels {dist}")

    if args.results:
        result = json.loads(Path(args.results).read_text(encoding="utf-8"))
        annotation = None
        if args.annotations:
            ann_path = Path(args.annotations) / f"gold-{result.get('id', '')}.json"
            if ann_path.exists():
                annotation = json.loads(ann_path.read_text(encoding="utf-8"))
        metrics = evaluate(result, annotation)
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
