#!/usr/bin/env python3
"""claim_audit.py — Citation Audit (plan section 11).

Runs before final report generation. For each claim-evidence pair:

    Claim exists? -> Evidence exists? -> Source exists? -> Source supports claim?
    -> Outcome matches? -> Scope exceeds source?

Failures are marked:
    UNSUPPORTED             evidence cannot be bound to a verifiable source
    CONTRADICT              bound evidence contradicts the claim (relation_to_claim)
    DOWNGRADE_CONFIDENCE    claim overstates the source (scope/outcome mismatch)

Citation relation is judged ONLY by relation_to_claim (via
evidence_semantics.claim_relation) — never by effect_direction or the legacy
direction field: a negative effect can support a negative claim.

Usage:
    python scripts/claim_audit.py --claims claims.jsonl --evidence evidence.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence_semantics import claim_relation

SUPPORTED_OUTCOMES = {
    "knowledge_gain", "concept_understanding", "retention", "transfer",
    "independent_problem_solving", "completion_time", "accuracy",
    "code_quality", "assignment_score", "engagement", "motivation",
    "cognitive_load", "help_seeking", "metacognition", "ai_dependency",
    "over_reliance", "reduced_effort", "reduced_transfer",
    "academic_integrity_risk", "false_confidence",
}


def load_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def audit_claim(claim: dict, evidence_by_id: dict[str, dict]) -> dict:
    """Audit a single claim. Returns a status record."""
    result = {
        "claim": claim.get("claim", ""),
        "status": "SUPPORTED",
        "issues": [],
    }

    # 1. Claim exists?
    if not claim.get("claim"):
        result["status"] = "UNSUPPORTED"
        result["issues"].append("claim is empty")
        return result

    # 2. Evidence exists?
    evidence_ids = claim.get("evidence_ids", [])
    if not evidence_ids:
        result["status"] = "UNSUPPORTED"
        result["issues"].append("no evidence_ids bound to claim")
        return result

    bound = []
    for eid in evidence_ids:
        ev = evidence_by_id.get(eid)
        if ev is None:
            result["issues"].append(f"evidence {eid} not found")
            continue
        bound.append(ev)

    if not bound:
        result["status"] = "UNSUPPORTED"
        result["issues"].append("no bound evidence found in corpus")
        return result

    # 3. Source exists (source_id + source_location)
    for ev in bound:
        if not ev.get("source_id"):
            result["issues"].append(f"{ev.get('evidence_id')}: missing source_id")
        if not ev.get("source_location"):
            result["issues"].append(f"{ev.get('evidence_id')}: missing source_location")

    # 4. Source supports claim (judged ONLY by relation_to_claim; a negative
    #    effect can support a negative claim — never use effect_direction or
    #    the legacy direction field as a citation relation)
    for ev in bound:
        if claim_relation(ev) == "contradict":
            result["issues"].append(
                f"{ev.get('evidence_id')}: evidence contradicts claim (relation_to_claim=contradict)")

    # 5. Outcome matches
    for ev in bound:
        outcome = ev.get("outcome_type", "")
        if outcome not in SUPPORTED_OUTCOMES:
            result["issues"].append(
                f"{ev.get('evidence_id')}: unknown outcome_type {outcome!r}")
        claimed_outcome = claim.get("outcome_type")
        if claimed_outcome and outcome and claimed_outcome != outcome:
            result["issues"].append(
                f"{ev.get('evidence_id')}: outcome mismatch (claim={claimed_outcome}, evidence={outcome})")

    # 6. Scope exceeds source?
    claim_scope = claim.get("scope")
    if claim_scope:
        for ev in bound:
            ev_scope = ev.get("applicability", {}).get("scope", "")
            if ev_scope and claim_scope not in ev_scope:
                result["issues"].append(
                    f"{ev.get('evidence_id')}: claim scope {claim_scope!r} exceeds source scope {ev_scope!r}")

    if result["issues"]:
        if any("contradicts claim" in i for i in result["issues"]):
            # Contradiction is the dominant signal: the claim is contradicted
            # by its own evidence, distinct from being unverifiable.
            result["status"] = "CONTRADICT"
        else:
            severe = any("missing source" in i or "not found" in i
                         for i in result["issues"])
            result["status"] = "UNSUPPORTED" if severe else "DOWNGRADE_CONFIDENCE"
    return result


def audit_claims(claims: list[dict], evidence_list: list[dict]) -> list[dict]:
    evidence_by_id = {ev.get("evidence_id"): ev for ev in evidence_list}
    return [audit_claim(c, evidence_by_id) for c in claims]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Citation Audit over claims and evidence")
    parser.add_argument("--claims", required=True, help="claims.jsonl (each line: claim, evidence_ids, outcome_type, scope)")
    parser.add_argument("--evidence", required=True, help="evidence.jsonl")
    args = parser.parse_args()

    claims = load_records(Path(args.claims))
    evidence = load_records(Path(args.evidence))
    results = audit_claims(claims, evidence)

    summary = {"SUPPORTED": 0, "UNSUPPORTED": 0, "DOWNGRADE_CONFIDENCE": 0, "CONTRADICT": 0}
    for r in results:
        summary[r["status"]] += 1
        if r["issues"]:
            print(f"[{r['status']}] {r['claim']}")
            for issue in r["issues"]:
                print(f"    - {issue}")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["UNSUPPORTED"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
