#!/usr/bin/env python3
"""pre_verdict_gate.py — Pre-Verdict Gate (Phase 15).

An 11-item checklist that must pass (or be explicitly degraded) before a
verdict may carry a high confidence label. The gate is deterministic and
reads ONLY the run workspace — no model call, no network.

Checklist:

  1.  research_frame_valid       frame.json validates against the run domain frame schema
  2.  sources_valid              sources.jsonl non-empty and schema-valid
  3.  evidence_schema_valid      evidence.jsonl non-empty and schema-valid
  4.  source_dedupe              no duplicate sources remain (dedupe applied)
  5.  counter_evidence_search    skeptic.json present with search_performed=true
  6.  methodology_audit          methodology.json schema-valid, verdict != FAIL,
                                task_vs_learning_guard not equating task with learning
  7.  claim_evidence_audit       every evidence id referenced by verdict claims exists;
                                no claim is bound to evidence that contradicts its category
  8.  outcome_mapping            verdict outcome keys are known taxonomy tokens;
                                frame-declared outcomes covered by evidence
  9.  scope_calibration          verdict carries what_can/cannot_be_claimed +
                                exceeds_evidence_boundary
  10. independent_study_count    independent studies/samples counted; >= 2 for High
  11. deterministic_confidence   final verdict carries confidence_score +
                                confidence_policy_version + raw model value preserved

Failure model (per item): status pass | warn | fail. An item may be
``critical`` (its failure forbids any High confidence) and/or ``blocks_high``
(any non-pass state forbids High confidence; e.g. a single independent study).
Overall result:

  passed                  no critical item failed
  high_confidence_allowed passed AND no blocks_high item is non-pass
  max_confidence          High / Moderate / Low (never High when blocked)

Usage:
    python scripts/pre_verdict_gate.py --workspace runs/<run_id>
    python scripts/pre_verdict_gate.py --workspace runs/<run_id> \\
        --apply-verdict final_verdict.json --out gate_report.json
    python scripts/pre_verdict_gate.py --workspace runs/<run_id> --json

Exit code 0 = gate passed; 1 = critical failures (verdict must be capped);
2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from validate_schema import SchemaError, Validator  # noqa: E402
from evidence_score import independent_samples, independent_studies  # noqa: E402
from evidence_semantics import claim_relation, decision_relation  # noqa: E402
from run_workspace import utc_now  # noqa: E402

GATE_VERSION = "2026-08-13.v1"

CONFIDENCE_RANK = {"Insufficient": 0, "Low": 1, "Moderate": 2, "High": 3}

#: Advisory taxonomy for verdict outcome keys (shared with claim_audit).
def _supported_outcomes() -> set[str]:
    """Every registered outcome token, read from the domain registry.

    This was a hand-copied 20-token education list in three separate files;
    it silently rejected policy tokens such as policy_effectiveness. The
    registry (domains/<id>/outcome_taxonomy.json) is the single authority.
    """
    from engine.taxonomy import all_tokens_ordered

    return set(all_tokens_ordered())


SUPPORTED_OUTCOMES = _supported_outcomes()

_CLAIM_ID_RE = re.compile(r"\b[A-Z]{1,3}-\d{2,4}\b")

_SCHEMA_CACHE: dict[str, dict[str, Any]] = {}


def _schema_path(name: str) -> Path:
    """Resolve a schema name to a file.

    Accepts a bare name in schemas/ as well as a repository-relative path,
    because a domain may own its frame contract outside schemas/ (policy does:
    domains/policy/frame.schema.json).
    """
    candidate = ROOT / "schemas" / name
    if candidate.is_file():
        return candidate
    owned = ROOT / name
    if owned.is_file():
        return owned
    return candidate  # missing: the caller reports it


def _schema(name: str) -> dict[str, Any]:
    path = _schema_path(name)
    key = str(path)
    if key not in _SCHEMA_CACHE:
        _SCHEMA_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE[key]


def _validate_records(records: list[dict[str, Any]], schema_name: str, path: str) -> list[str]:
    schema = _schema(schema_name)
    validator = Validator(schema, base_dir=_schema_path(schema_name).parent)
    errors = []
    for idx, record in enumerate(records):
        try:
            validator.validate(record, schema, f"{path}[{idx}]")
        except SchemaError as exc:
            errors.append(str(exc))
    return errors


def _load_ws_json(workspace: Path, name: str) -> dict[str, Any]:
    try:
        data = json.loads((workspace / name).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_ws_jsonl(workspace: Path, name: str) -> list[dict[str, Any]]:
    path = workspace / name
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                records.append(data)
    return records


# ------------------------------------------------------------- item checks


def _item_res(status: str, detail: str, *, blocks_high: bool | None = None) -> dict[str, str]:
    res = {"status": status, "detail": detail}
    if blocks_high is not None:
        res["blocks_high"] = blocks_high
    return res


def workspace_domain(ws: Path) -> str:
    """The domain this run/pack registered; defaults to education when absent.

    A run workspace records it in run_manifest.json, but an example pack has
    no manifest: reading only that file made a policy pack validate against the
    education frame schema and fail item 1. Fall back to the same declared
    places the read model uses, in the same order.
    """
    manifest = _load_ws_json(ws, "run_manifest.json")
    if manifest.get("domain"):
        return str(manifest["domain"])
    frame = _load_ws_json(ws, "frame.json")
    declared = (frame.get("extensions") or {}).get("domain")
    if declared:
        return str(declared)
    result_meta = (_load_ws_json(ws, "result.json").get("meta") or {})
    if result_meta.get("domain"):
        return str(result_meta["domain"])
    return "education"


def frame_schema_name(domain: str) -> str:
    """Registered frame schema for a domain (repository-relative path)."""
    from engine.evidencecore import load_domain

    return str(load_domain(domain)["frame_schema"])


def check_research_frame(ws: Path) -> dict[str, str]:
    frame = _load_ws_json(ws, "frame.json")
    if not frame:
        return _item_res("fail", "frame.json missing or empty (research question not framed)")
    try:
        schema_name = frame_schema_name(workspace_domain(ws))
    except KeyError as exc:
        return _item_res("fail", f"run declares an unknown domain: {exc}")
    errors = _validate_records([frame], schema_name, "frame")
    if errors:
        return _item_res("fail", f"frame.json schema invalid: {errors[0]}")
    return _item_res("pass", f"frame.json valid (question={frame.get('question', '')[:80]})")


def check_sources(ws: Path) -> dict[str, str]:
    sources = _load_ws_jsonl(ws, "sources.jsonl")
    if not sources:
        return _item_res("fail", "sources.jsonl missing or empty (no sources retrieved)")
    errors = _validate_records(sources, "source.schema.json", "sources")
    if errors:
        return _item_res("fail", f"{len(errors)} invalid source record(s): {errors[0]}")
    return _item_res("pass", f"{len(sources)} source record(s) schema-valid")


def check_evidence_schema(ws: Path) -> dict[str, str]:
    evidence = _load_ws_jsonl(ws, "evidence.jsonl")
    if not evidence:
        return _item_res("fail", "evidence.jsonl missing or empty (no evidence extracted)")
    errors = _validate_records(evidence, "evidence.schema.json", "evidence")
    if errors:
        return _item_res("fail", f"{len(errors)} invalid evidence record(s): {errors[0]}")
    return _item_res("pass", f"{len(evidence)} evidence record(s) schema-valid")


def check_source_dedupe(ws: Path) -> dict[str, str]:
    from retrieval.dedupe import dedupe_sources  # repo package, bootstrapped above

    sources = _load_ws_jsonl(ws, "sources.jsonl")
    if not sources:
        return _item_res("fail", "sources.jsonl empty (dedupe cannot run)")
    unique = dedupe_sources(sources)
    duplicates = len(sources) - len(unique)
    if duplicates:
        return _item_res("fail", f"{duplicates} duplicate source(s) remain; dedupe not applied")
    return _item_res("pass", f"{len(unique)} unique source(s), no duplicates")


def check_counter_evidence(ws: Path) -> dict[str, str]:
    skeptic = _load_ws_json(ws, "skeptic.json")
    if not skeptic:
        return _item_res("fail", "skeptic.json missing or empty (counter-evidence search not performed)")
    if skeptic.get("search_performed") is not True:
        return _item_res("fail", "skeptic.json lacks search_performed=true")

    # The nine fixed checks are the contract (skill/task-briefs/challenge.md).
    # A two-key shell used to pass this gate, which made the counter-evidence
    # check cosmetic on every deterministic path.
    required_checks = (
        "1_null_result", "2_negative_result", "3_contradictory_evidence",
        "4_alternative_explanation", "5_measurement_mismatch", "6_sampling_bias",
        "7_novelty_effect", "8_ai_dependency", "9_scope_overreach",
    )
    findings = skeptic.get("skeptic_findings")
    if not isinstance(findings, list) or not findings:
        return _item_res(
            "fail", "skeptic.json lacks skeptic_findings[] (nine fixed checks not run)")
    present = {str(f.get("check")) for f in findings if isinstance(f, dict)}
    missing = [c for c in required_checks if c not in present]
    if missing:
        return _item_res("fail", f"skeptic findings incomplete; missing {missing}")
    for item in findings:
        if not isinstance(item, dict) or item.get("status") not in ("found", "not_found"):
            return _item_res(
                "fail", f"skeptic finding {item.get('check')!r} lacks a found/not_found status")

    found = bool(skeptic.get("contradictory_evidence_found"))
    statement = skeptic.get("no_contradictory_evidence_statement")
    if not found and not statement:
        # Absence of counter-evidence must be asserted, not left implicit.
        return _item_res(
            "fail", "no contradictory evidence found but no statement recorded")
    if found and statement:
        return _item_res(
            "fail", "contradictory_evidence_found=true together with a no-evidence statement")

    found_checks = sum(1 for f in findings if f.get("status") == "found")
    detail = (f"search_performed=true; 9/9 checks run; findings={found_checks}; "
              f"contradictory_evidence_found={found}")
    return _item_res("pass", detail)


def check_methodology(ws: Path) -> dict[str, str]:
    methodology = _load_ws_json(ws, "methodology.json")
    if not methodology:
        return _item_res("fail", "methodology.json missing or empty (no method audit)")
    errors = _validate_records([methodology], "methodology.schema.json", "methodology")
    if errors:
        return _item_res("fail", f"methodology.json schema invalid: {errors[0]}")
    verdict = methodology.get("verdict", "")
    guard = methodology.get("task_vs_learning_guard", {}) or {}
    if verdict == "FAIL":
        return _item_res("fail", "methodology verdict is FAIL (evidence base does not stand)")
    if guard.get("equates_task_with_learning") is True:
        return _item_res("fail", "task_vs_learning_guard equates task performance with learning")
    return _item_res("pass", f"methodology verdict={verdict}; task/learning separated")


def _verdict_for_audit(ws: Path) -> dict[str, Any]:
    final = _load_ws_json(ws, "final_verdict.json")
    if final:
        return final
    return _load_ws_json(ws, "raw_verdict.json")


#: Explicit markers a verdict claim may carry to declare "no direct evidence
#: exists" instead of silently omitting a binding (OPEN-1). A hedged claim
#: that carries no evidence id AND no such marker blocks High confidence.
NO_DIRECT_EVIDENCE_MARKERS = ("[无直接证据]", "no direct evidence", "NO_DIRECT_EVIDENCE")


def _claim_has_no_evidence_marker(claim_text: str) -> bool:
    return any(marker in claim_text for marker in NO_DIRECT_EVIDENCE_MARKERS)


def check_claim_evidence(ws: Path) -> dict[str, str]:
    verdict = _verdict_for_audit(ws)
    if not verdict:
        return _item_res("fail", "no verdict artifact (raw_verdict.json or final_verdict.json)")
    evidence = {e.get("evidence_id"): e for e in _load_ws_jsonl(ws, "evidence.jsonl")}
    if not evidence:
        return _item_res("fail", "evidence.jsonl empty (claim-evidence binding cannot be audited)")

    issues: list[str] = []
    warnings: list[str] = []
    for category in ("supported_claims", "uncertain_claims", "contradicted_claims"):
        for claim_text in verdict.get(category, []) or []:
            if not isinstance(claim_text, str) or not claim_text.strip():
                continue
            ids = _CLAIM_ID_RE.findall(claim_text)
            if not ids:
                if _claim_has_no_evidence_marker(claim_text):
                    continue  # explicitly declared "no direct evidence": acceptable
                warnings.append(f"{category}: claim carries no evidence id: {claim_text[:60]}")
                continue
            for eid in ids:
                ev = evidence.get(eid)
                if ev is None:
                    issues.append(f"{category}: evidence {eid} referenced but not found in corpus")
                    continue
                relation = claim_relation(ev)
                if category == "supported_claims" and relation == "contradict":
                    warnings.append(f"supported claim cites contradicting evidence {eid} "
                                    "(may be an intentional negative finding)")
                if category == "contradicted_claims" and relation == "support":
                    warnings.append(f"contradicted claim cites supporting evidence {eid} "
                                    "(may be an intentional positive finding)")

    if issues:
        return _item_res("fail", "; ".join(issues[:3]) + (f" (+{len(issues)-3} more)" if len(issues) > 3 else ""))
    if warnings:
        # ANY claim category without an evidence id (and without an explicit
        # "no direct evidence" marker) is unverifiable and blocks High
        # confidence — uncertain claims must bind evidence or declare the gap
        # (OPEN-1); hedged/contradicted claims without ids were previously
        # only noted but could still mislead the confidence label.
        unverifiable = [w for w in warnings if "carries no evidence id" in w]
        note = "; ".join(warnings[:2]) + (f" (+{len(warnings)-2} more)" if len(warnings) > 2 else "")
        return _item_res("warn", note, blocks_high=bool(unverifiable))
    return _item_res("pass", "all verdict claims bind to existing evidence with consistent categories")


def _primary_evidence_summary(ws: Path) -> dict[str, Any]:
    """Re-derive ADOPT eligibility from the pack's own evidence records.

    The gate audits an artifact another party wrote, so it cannot trust the
    verdict about itself: primary-result directness is read back from the
    corpus (frame primary outcomes + per-record D5 Directness), using the same
    domain registry and directness threshold the tribunal imports.
    """
    from engine.decision_policy import (
        ADOPT_DIRECTNESS,
        outcome_category,
        primary_effect_categories,
    )

    domain = workspace_domain(ws)
    try:
        primary = primary_effect_categories(domain)
    except (KeyError, ValueError) as exc:
        return {"domain": domain, "primary": (), "direct": False, "error": str(exc)}

    frame = _load_ws_json(ws, "frame.json")
    declared_primary = [
        str(token) for token in ((frame.get("outcomes") or {}).get("primary") or [])
    ]
    evidence = _load_ws_jsonl(ws, "evidence.jsonl")
    direct_hits: list[str] = []
    for ev in evidence:
        token = str(ev.get("outcome_type") or "")
        category = outcome_category(domain, token, primary)
        if category is None or category not in primary:
            continue
        dims = ev.get("quality_dimensions") or {}
        d5 = dims.get("D5_directness")
        if isinstance(d5, bool) or not isinstance(d5, int):
            continue
        if d5 >= ADOPT_DIRECTNESS:
            direct_hits.append(str(ev.get("evidence_id") or "?"))
    return {
        "domain": domain,
        "primary": primary,
        "declared_primary": declared_primary,
        "direct": bool(direct_hits),
        "direct_evidence_ids": direct_hits,
    }


def check_decision_action(ws: Path) -> dict[str, str]:
    """The stated action must be the action the evidence supports.

    A verdict cannot hand itself ADOPT: the gate requires High confidence, a
    supporting decisive relation, and primary-outcome evidence at directness 2.
    Anything less is capped to pilot - the conservative bound - because the
    underlying evidence may still justify a bounded trial.
    """
    verdict = _verdict_for_audit(ws)
    if not verdict:
        return _item_res("warn", "no verdict artifact yet; action not audited")
    action = str(verdict.get("recommended_action") or "").lower()
    if action != "adopt":
        label = action or "unset"
        return _item_res("pass", "action=" + label + " is within the conservative bound")

    from engine.decision_policy import ADOPT_REQUIRED_LABEL, decision_action

    evidence = _load_ws_jsonl(ws, "evidence.jsonl")
    relations = [decision_relation(ev) for ev in evidence]
    decisive = {str(index): rel for index, rel in enumerate(relations)
                if rel in ("support_adoption", "oppose_adoption")}
    label = str(verdict.get("confidence") or "")
    summary = _primary_evidence_summary(ws)
    expected = decision_action(
        confidence_label=label,
        decisive_relations=decisive,
        has_direct_primary_evidence=bool(summary.get("direct")),
    )
    if expected == "ADOPT":
        detail = "ADOPT is supported: " + label + " confidence with direct primary-outcome evidence"
        return _item_res("pass", detail)
    reasons: list[str] = []
    if label != ADOPT_REQUIRED_LABEL:
        reasons.append("confidence=" + (label or "unset") + " (needs " + ADOPT_REQUIRED_LABEL + ")")
    if "support_adoption" not in relations:
        reasons.append("no decisive supporting evidence")
    if not summary.get("direct"):
        reasons.append("no primary-outcome evidence at directness 2")
    detail = ("recommended_action=adopt is not supported (" + "; ".join(reasons)
              + "); the evidence bounds this decision to pilot")
    return _item_res("fail", detail)


def check_outcome_mapping(ws: Path) -> dict[str, str]:
    verdict = _verdict_for_audit(ws)
    frame = _load_ws_json(ws, "frame.json")
    issues: list[str] = []
    notes: list[str] = []

    findings = verdict.get("outcome_specific_findings", {}) or {}
    unknown = [k for k in findings if k not in SUPPORTED_OUTCOMES]
    if unknown:
        issues.append(f"unknown outcome key(s) in verdict: {', '.join(sorted(unknown))}")

    evidence_outcomes = {e.get("outcome_type") for e in _load_ws_jsonl(ws, "evidence.jsonl")}
    frame_outcomes = frame.get("outcomes", {}) or {}
    declared = set()
    for group in ("primary", "secondary", "risk"):
        declared.update(frame_outcomes.get(group, []) or [])
    if declared:
        missing = sorted(d for d in declared if d and d not in evidence_outcomes)
        if missing:
            # Missing evidence is not a zero effect, and a secondary or risk
            # outcome the frame named but the corpus never measured does not
            # contaminate the decision. Only a PRIMARY outcome with no
            # evidence at all means the decision rests on the wrong construct,
            # so only that case blocks High confidence.
            primary_missing = sorted(
                d for d in (frame_outcomes.get("primary", []) or [])
                if d and d not in evidence_outcomes)
            note = f"frame-declared outcomes without evidence: {', '.join(missing)}"
            if primary_missing:
                return _item_res(
                    "warn",
                    note + f"; primary outcomes unmeasured: {', '.join(primary_missing)}",
                    blocks_high=True)
            notes.append(note)
        else:
            notes.append("all frame-declared outcomes are covered by evidence")

    if issues:
        return _item_res("fail", "; ".join(issues))
    if notes and "without evidence" in notes[0]:
        return _item_res("warn", "outcome keys known; " + notes[0], blocks_high=False)
    if not declared:
        return _item_res("warn", "outcome keys known; frame declares no outcomes to map")
    return _item_res("pass", f"outcome mapping complete ({len(evidence_outcomes)} outcome type(s) covered)")


def check_scope_calibration(ws: Path) -> dict[str, str]:
    verdict = _verdict_for_audit(ws)
    if not verdict:
        return _item_res("fail", "no verdict artifact to calibrate")
    missing = []
    for field in ("what_can_be_claimed", "what_cannot_be_claimed", "exceeds_evidence_boundary"):
        if field not in verdict or not isinstance(verdict.get(field), list):
            missing.append(field)
    if missing:
        return _item_res("fail", f"scope calibration incomplete: missing {', '.join(missing)}")
    boundary = len(verdict["exceeds_evidence_boundary"])
    detail = (f"claims bounded: can={len(verdict['what_can_be_claimed'])}, "
              f"cannot={len(verdict['what_cannot_be_claimed'])}, exceeds_boundary={boundary}")
    return _item_res("pass", detail)


def check_study_count(ws: Path) -> dict[str, str]:
    evidence = _load_ws_jsonl(ws, "evidence.jsonl")
    if not evidence:
        return _item_res("fail", "no evidence to count independent studies/samples")
    studies = independent_studies(evidence)
    samples = independent_samples(evidence)
    detail = f"independent studies={studies}, samples={samples}"
    if studies == 0:
        return _item_res("fail", detail + "; zero independent studies")
    if studies < 2:
        return _item_res("warn", detail + "; single study cannot support High confidence")
    return _item_res("pass", detail)


def check_deterministic_confidence(ws: Path, *, require_final: bool) -> dict[str, str]:
    final = _load_ws_json(ws, "final_verdict.json")
    if not final:
        if require_final:
            return _item_res("fail", "final_verdict.json missing (deterministic confidence not applied)")
        return _item_res("warn", "final_verdict.json pending (run adjudicate to apply deterministic confidence)")

    errors = _validate_records([final], "verdict.schema.json", "final_verdict")
    if errors:
        return _item_res("fail", f"final_verdict.json schema invalid: {errors[0]}")
    problems = []
    if not isinstance(final.get("confidence_score"), (int, float)) or isinstance(final.get("confidence_score"), bool):
        problems.append("confidence_score missing/non-numeric")
    if not final.get("confidence_policy_version"):
        problems.append("confidence_policy_version missing")
    if final.get("confidence") not in ("High", "Moderate", "Low", "Insufficient"):
        problems.append(f"confidence {final.get('confidence')!r} not in allowed bands")
    if problems:
        return _item_res("fail", "final_verdict.json " + "; ".join(problems))
    note = ""
    if "raw_model_confidence" not in final:
        note = "; raw model confidence not preserved"
    return _item_res("pass" if not note else "warn",
                     f"deterministic confidence={final['confidence']} "
                     f"(score={final.get('confidence_score')}, "
                     f"policy={final.get('confidence_policy_version')}){note}")


# ---------------------------------------------------------------- gate spec

GATE_ITEMS: list[dict[str, Any]] = [
    {"id": "research_frame_valid", "title": "Research Frame valid", "critical": True,
     "blocks_high": True, "check": check_research_frame},
    {"id": "sources_valid", "title": "Sources valid", "critical": True,
     "blocks_high": True, "check": check_sources},
    {"id": "evidence_schema_valid", "title": "Evidence Schema valid", "critical": True,
     "blocks_high": True, "check": check_evidence_schema},
    {"id": "source_dedupe", "title": "Source dedupe", "critical": True,
     "blocks_high": True, "check": check_source_dedupe},
    {"id": "counter_evidence_search", "title": "Counter-evidence search", "critical": True,
     "blocks_high": True, "check": check_counter_evidence},
    {"id": "methodology_audit", "title": "Methodology audit", "critical": True,
     "blocks_high": True, "check": check_methodology},
    {"id": "claim_evidence_audit", "title": "Claim-Evidence Audit", "critical": True,
     "blocks_high": False, "check": check_claim_evidence},
    {"id": "outcome_mapping", "title": "Outcome mapping", "critical": False,
     "blocks_high": True, "check": check_outcome_mapping},
    {"id": "scope_calibration", "title": "Scope calibration", "critical": False,
     "blocks_high": True, "check": check_scope_calibration},
    {"id": "independent_study_count", "title": "Independent study-sample count", "critical": True,
     "blocks_high": True, "check": check_study_count},
    {"id": "deterministic_confidence", "title": "Deterministic confidence", "critical": True,
     "blocks_high": True, "check": None},
    {"id": "decision_action_consistency", "title": "Decision action consistency",
     "critical": True, "blocks_high": False, "check": check_decision_action},
]


def evaluate_workspace(workspace: Path, *, require_final: bool = True) -> dict[str, Any]:
    """Run the 11-item gate over a run workspace. Pure, deterministic, read-only."""
    ws = Path(workspace)
    items: dict[str, dict[str, Any]] = {}
    for spec in GATE_ITEMS:
        if spec["id"] == "deterministic_confidence":
            result = check_deterministic_confidence(ws, require_final=require_final)
        else:
            result = spec["check"](ws)
        items[spec["id"]] = {
            "title": spec["title"],
            "status": result["status"],
            "detail": result["detail"],
            "critical": spec["critical"],
            "blocks_high": result.get("blocks_high", spec["blocks_high"]),
        }

    critical_failures = [iid for iid, it in items.items() if it["critical"] and it["status"] == "fail"]
    passed = not critical_failures
    high_blockers = [iid for iid, it in items.items() if it["blocks_high"] and it["status"] != "pass"]
    high_confidence_allowed = passed and not high_blockers
    if high_confidence_allowed:
        max_confidence = "High"
    elif passed:
        max_confidence = "Moderate"
    else:
        max_confidence = "Low"

    return {
        "gate_version": GATE_VERSION,
        "checked_at": utc_now(),
        "workspace": str(ws),
        "items": items,
        "passed": passed,
        "critical_failures": critical_failures,
        "high_confidence_allowed": high_confidence_allowed,
        "max_confidence": max_confidence,
        "enforcement": {
            "rule": ("confidence capped at {max}; High confidence requires a fully passing gate "
                     "and >= 2 independent studies"),
            "max_confidence": max_confidence,
            "requires_action_change": not passed,
            "action_override": "pilot" if not passed else None,
        },
    }


def apply_enforcement(verdict: dict[str, Any], gate: dict[str, Any]) -> dict[str, Any]:
    """Cap a verdict's confidence per the gate result (in-place on a copy).

    - gate failed            -> confidence at most Low; adopt downgraded to pilot
    - gate passed but High blocked -> confidence at most Moderate
    - stated adopt the evidence does not support -> downgraded to pilot
    Always records the enforcement inside verdict.extensions.gate_enforcement.
    """
    import copy

    out = copy.deepcopy(verdict)
    cap = gate.get("max_confidence", "Low")
    current = out.get("confidence", "Insufficient")
    if CONFIDENCE_RANK.get(current, 0) > CONFIDENCE_RANK.get(cap, 0):
        out["confidence"] = cap
    if not gate.get("passed", False) and out.get("recommended_action") == "adopt":
        out["recommended_action"] = "pilot"
    action_item = (gate.get("items") or {}).get("decision_action_consistency") or {}
    if action_item.get("status") == "fail" and out.get("recommended_action") == "adopt":
        out["recommended_action"] = "pilot"
    extensions = out.setdefault("extensions", {})
    if not isinstance(extensions, dict):
        extensions = {}
        out["extensions"] = extensions
    enforcement = extensions.setdefault("gate_enforcement", {})
    enforcement.update({
        "gate_version": gate.get("gate_version"),
        "checked_at": gate.get("checked_at"),
        "passed": gate.get("passed"),
        "critical_failures": gate.get("critical_failures"),
        "max_confidence": cap,
        "confidence_before": current,
        "action_before": verdict.get("recommended_action"),
    })
    return out


# ---------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduEvidence Pre-Verdict Gate (11-item checklist)")
    parser.add_argument("--workspace", required=True, help="run workspace directory (runs/<run_id>)")
    parser.add_argument("--require-final", action="store_true",
                        help="item 11 fails when final_verdict.json is missing (default: warn)")
    parser.add_argument("--apply-verdict", metavar="PATH",
                        help="cap the given verdict JSON per the gate result and write it back")
    parser.add_argument("--out", metavar="PATH", help="write the gate report JSON to PATH")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    report = evaluate_workspace(Path(args.workspace), require_final=args.require_final)

    if args.apply_verdict:
        verdict_path = Path(args.apply_verdict)
        verdict = _load_ws_json(verdict_path.parent, verdict_path.name)
        if not verdict:
            print(f"ERROR: verdict file {verdict_path} missing or empty", file=sys.stderr)
            return 2
        capped = apply_enforcement(verdict, report)
        verdict_path.write_text(json.dumps(capped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report["verdict_applied"] = str(verdict_path)
        report["verdict_confidence"] = capped.get("confidence")
        report["verdict_action"] = capped.get("recommended_action")

    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for iid, item in report["items"].items():
            print(f"[{item['status'].upper():4}] {iid}: {item['detail']}")
        print(f"passed={report['passed']} high_confidence_allowed="
              f"{report['high_confidence_allowed']} max_confidence={report['max_confidence']}")
        if report["critical_failures"]:
            print(f"critical failures: {', '.join(report['critical_failures'])}", file=sys.stderr)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
