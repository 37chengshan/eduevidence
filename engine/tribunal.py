"""V2 Evidence Tribunal — revision-bound DecisionSnapshot generation.

Confidence policy (migration baseline, CONFIDENCE_POLICY_VERSION
2026-08-12.v3):

    quality_term      = mean per usable independent Study of
                        (design+sample+measurement+temporal) / 8
    study relation    = collapse active relevant links in one Study:
                        support-only → support_adoption; oppose-only →
                        oppose_adoption; both/conditional → conditional;
                        neutral-only → neutral
    consistency_term  = majority proportion over decisive Study relations
    directness_term   = mean across Studies of (mean link directness / 2)
    count_term        = min(1.0, usable independent studies / 4)
    conflict_penalty  = 0.15 only when independent support_adoption AND
                        oppose_adoption Studies both exist
    uncertainty_penalty = min(0.20, 0.05 * critical_uncertainty_units)

    score = 0.30*q + 0.25*c + 0.20*d + 0.25*n - conflict - uncertainty

    High >= .72 | Moderate >= .45 | Low >= .20 | else Insufficient

Directness is NOT double-counted (it is excluded from the quality term's
methodology scope by construction here: quality reads only the four audit
dimensions). The score is an auditable internal index, never a probability.

Decision action is gate-enforced:
    Low/Insufficient cannot yield ADOPT
    REJECT requires usable direct negative/opposition evidence
    unresolved but promising evidence may yield PILOT
    otherwise INSUFFICIENT_EVIDENCE
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.graph_store import GraphStore
from engine.ids import new_local_id
from engine.semantics import claim_relation, decision_implication
from engine.synthesis import ClaimSynthesis, synthesize_project
from engine.versions import (
    CONFIDENCE_POLICY_VERSION,
    METHODOLOGY_POLICY_VERSION,
    SOURCE_VALIDATION_POLICY_VERSION,
)

THRESHOLD_HIGH = 0.72
THRESHOLD_MODERATE = 0.45
THRESHOLD_LOW = 0.20
CONFLICT_PENALTY = 0.15
UNCERTAINTY_PER_UNIT = 0.05
UNCERTAINTY_CAP = 0.20


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _label(score: float) -> str:
    if score >= THRESHOLD_HIGH:
        return "High"
    if score >= THRESHOLD_MODERATE:
        return "Moderate"
    if score >= THRESHOLD_LOW:
        return "Low"
    return "Insufficient"


def _study_relation(store: GraphStore, claim_syn: ClaimSynthesis,
                    study_id: str, findings: dict, links: list[dict]) -> str:
    """Collapse all active relevant links of one Study into one relation."""
    implications = []
    for link in links:
        if link["claim_id"] != claim_syn.claim_id:
            continue
        fnd = findings.get(link["finding_id"])
        if fnd is None or fnd["study_id"] != study_id:
            continue
        implications.append(decision_implication(link))
    if not implications:
        return "neutral"
    support = any(i == "support_adoption" for i in implications)
    oppose = any(i == "oppose_adoption" for i in implications)
    conditional = any(i == "conditional" for i in implications)
    if support and oppose:
        return "conditional"
    if conditional:
        return "conditional"
    if support:
        return "support_adoption"
    if oppose:
        return "oppose_adoption"
    return "neutral"


def _usable_studies(store: GraphStore) -> dict[str, dict]:
    sources = {s["source_id"]: s for s in store.read_table("sources")}
    usable: dict[str, dict] = {}
    for s in store.read_table("studies"):
        if s.get("identity_status") == "unresolved":
            continue
        if not any(sid in sources and sources[sid]["validation_status"] in
                   ("valid", "accepted_partial") for sid in s.get("source_ids", [])):
            continue
        usable[s["study_id"]] = s
    return usable


def _latest_audits(store: GraphStore) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for a in store.read_table("audits"):
        cur = latest.get(a["study_id"])
        if cur is None or a["audited_at"] >= cur["audited_at"]:
            latest[a["study_id"]] = a
    return latest


def _study_implication(implications: list[str]) -> str:
    """Collapse all active links of one Study into one decision relation.

    support-only → support_adoption; oppose-only → oppose_adoption;
    any conditional or both directions → conditional; neutral-only → neutral.
    This is Study-level folding: every Study is folded exactly once across
    ALL its links, so a multi-claim Study can never vote twice or be
    overwritten by a later Claim.
    """
    if not implications:
        return "neutral"
    support = any(i == "support_adoption" for i in implications)
    oppose = any(i == "oppose_adoption" for i in implications)
    conditional = any(i == "conditional" for i in implications)
    if conditional or (support and oppose):
        return "conditional"
    if support:
        return "support_adoption"
    if oppose:
        return "oppose_adoption"
    return "neutral"


def _confidence(store: GraphStore, syntheses: tuple[ClaimSynthesis, ...]) -> dict:
    """Deterministic confidence over usable independent studies.

    Each usable Study (valid source provenance, resolved identity, latest
    audit != fail) is folded exactly once across ALL its links, independent
    of Claim: support_adoption / oppose_adoption are decisive votes,
    conditional counts as a critical-uncertainty unit, neutral is ignored.

        quality_term     = mean over usable studies of
                           (design+sample+measurement+temporal) / 8
        consistency_term = majority proportion over decisive relations
        directness_term  = mean across studies of (mean link directness / 2)
        count_term       = min(1.0, usable_independent_studies / 4)
        conflict_penalty = 0.15 only when independent support_adoption AND
                           oppose_adoption studies both exist
        uncertainty      = min(0.20, 0.05 * critical_uncertainty_units)

    Directness is not double-counted (quality reads only the four audit
    dimensions). The score is an auditable internal index, never a
    probability.
    """
    usable = _usable_studies(store)
    audits = _latest_audits(store)
    findings = {f["finding_id"]: f for f in store.read_table("findings")}
    links = store.read_table("evidence_links")

    # group links per study (one fold per study across all claims)
    study_link_map: dict[str, list[dict]] = {}
    for link in links:
        fnd = findings.get(link["finding_id"])
        if fnd is not None:
            study_link_map.setdefault(fnd["study_id"], []).append(link)

    decisive: dict[str, str] = {}  # study_id -> support_adoption|oppose_adoption
    usable_studies: list[str] = []
    quality_sum = 0.0
    directness_sum = 0.0
    directness_count = 0
    critical_uncertainty_units = 0

    for sid, study in sorted(usable.items()):
        audit = audits.get(sid)
        if audit is None or audit.get("overall_status") == "fail":
            continue
        usable_studies.append(sid)
        impls = [decision_implication(l) for l in study_link_map.get(sid, [])]
        relation = _study_implication(impls)
        if relation in ("support_adoption", "oppose_adoption"):
            decisive[sid] = relation
        elif relation == "conditional":
            critical_uncertainty_units += 1
        quality_sum += (
            audit.get("design_quality", 0) + audit.get("sample_quality", 0)
            + audit.get("measurement_validity", 0)
            + audit.get("temporal_strength", 0)) / 8.0
        dirs = [int(l.get("directness", 0)) for l in study_link_map.get(sid, [])]
        if dirs:
            directness_sum += sum(dirs) / len(dirs) / 2.0
            directness_count += 1

    n_decisive = len(decisive)
    n_usable = len(usable_studies)
    if n_decisive == 0:
        return {"score": 0.0, "label": "Insufficient",
                "decisive_studies": 0, "usable_studies": n_usable,
                "decisive_relations": {}}

    quality_term = quality_sum / n_usable if n_usable else 0.0
    counts: dict[str, int] = {}
    for r in decisive.values():
        counts[r] = counts.get(r, 0) + 1
    majority = max(counts.values())
    consistency_term = majority / n_decisive
    directness_term = (directness_sum / directness_count) if directness_count else 0.0
    count_term = min(1.0, n_usable / 4.0)
    conflict = CONFLICT_PENALTY if (counts.get("support_adoption", 0) > 0
                                    and counts.get("oppose_adoption", 0) > 0) else 0.0
    uncertainty = min(UNCERTAINTY_CAP, UNCERTAINTY_PER_UNIT * critical_uncertainty_units)
    score = (0.30 * quality_term + 0.25 * consistency_term
             + 0.20 * directness_term + 0.25 * count_term
             - conflict - uncertainty)
    score = max(0.0, min(1.0, score))
    return {"score": round(score, 4), "label": _label(score),
            "decisive_studies": n_decisive, "usable_studies": n_usable,
            "decisive_relations": dict(decisive)}


def _has_direct_learning_evidence(store: GraphStore,
                                  decisive_relations: dict[str, str]) -> bool:
    """True when at least one decisive support_adoption Study measures a
    learning outcome directly.

    Learning evidence means the finding's outcome is declared
    outcome_type == "learning" AND its evidence link carries directness == 2.
    Task performance / process / risk outcomes never qualify, and a missing
    outcome record or missing directness fails closed (False).
    """
    findings = {f["finding_id"]: f for f in store.read_table("findings")}
    outcomes = {o["outcome_id"]: o for o in store.read_table("outcomes")}
    links_by_finding: dict[str, list[dict]] = {}
    for link in store.read_table("evidence_links"):
        links_by_finding.setdefault(link["finding_id"], []).append(link)

    support_studies = {sid for sid, rel in decisive_relations.items()
                       if rel == "support_adoption"}
    if not support_studies:
        return False
    for fid, fnd in findings.items():
        if fnd.get("study_id") not in support_studies:
            continue
        outcome = outcomes.get(fnd.get("outcome_id"))
        if outcome is None or outcome.get("outcome_type") != "learning":
            continue
        for link in links_by_finding.get(fid, []):
            directness = link.get("directness")
            if isinstance(directness, (int, float)) and int(directness) == 2:
                return True
    return False


def _decision_action(syn_statuses: dict[str, str], confidence: dict,
                     decisive_relations: dict[str, str],
                     has_direct_learning_evidence: bool = False) -> str:
    """Gate-enforced decision action.

    REJECT requires usable direct opposition evidence (an independent Study
    folded to oppose_adoption). Low/Insufficient can never yield ADOPT.
    ADOPT additionally requires direct learning/transfer evidence: High +
    decisive support WITHOUT a direct learning outcome downgrades to PILOT
    (task performance / procedural efficiency is not learning). Moderate +
    decisive support → PILOT; otherwise INSUFFICIENT_EVIDENCE.
    """
    label = confidence["label"]
    has_oppose = any(r == "oppose_adoption" for r in decisive_relations.values())
    has_support = any(r == "support_adoption" for r in decisive_relations.values())
    if has_oppose:
        return "REJECT"
    if label == "High" and has_support and has_direct_learning_evidence:
        return "ADOPT"
    if label in ("High", "Moderate") and has_support:
        return "PILOT"
    return "INSUFFICIENT_EVIDENCE"





def adjudicate(store: GraphStore, *, project: ProjectWorkspace,
               claim_syntheses: tuple[ClaimSynthesis, ...] | None = None,
               applicability: dict | None = None,
               policy_versions: dict[str, str] | None = None) -> dict:
    """Generate a DecisionSnapshot dict (not yet persisted)."""
    syntheses = claim_syntheses if claim_syntheses is not None else synthesize_project(store)
    confidence = _confidence(store, syntheses)
    applicability = applicability or {"boundary": "evidence scope", "notes": ""}

    syn_statuses = {s.claim_id: s.status for s in syntheses}
    decisive_relations = confidence.get("decisive_relations", {})
    direct_learning = _has_direct_learning_evidence(store, decisive_relations)

    decision = _decision_action(syn_statuses, confidence, decisive_relations,
                                has_direct_learning_evidence=direct_learning)

    key_links: list[str] = []
    for syn in syntheses:
        key_links.extend(syn.supporting_link_ids)
        key_links.extend(syn.contradicting_link_ids)

    risks: list[str] = []
    for syn in syntheses:
        risks.extend(syn.unresolved_conflicts)
    if not risks and decision == "ADOPT":
        risks.append("long-term retention/transfer may still be untested")

    missing: list[str] = []
    for syn in syntheses:
        missing.extend(syn.missing_evidence)
    if not missing:
        missing.append("no explicit knowledge-gap analysis in this snapshot")

    claim_assessments = {}
    for syn in syntheses:
        claim_assessments[syn.claim_id] = {
            "status": syn.status,
            "independent_studies": len(syn.study_ids),
            "independent_samples": len(syn.independent_sample_keys),
            "supporting_links": list(syn.supporting_link_ids),
            "contradicting_links": list(syn.contradicting_link_ids),
        }

    snapshot = {
        "decision_snapshot_id": new_local_id("DEC", set()),
        "decision": decision,
        "confidence_label": confidence["label"],
        "confidence_score_internal": confidence["score"],
        "claim_assessments": claim_assessments,
        "key_evidence_links": sorted(set(key_links)),
        "key_risks": sorted(set(risks)),
        "applicability_boundary": applicability.get("boundary", ""),
        "missing_evidence": sorted(set(missing)),
        "graph_revision": store.active_revision(),
        "policy_versions": policy_versions or {
            "confidence": CONFIDENCE_POLICY_VERSION,
            "methodology": METHODOLOGY_POLICY_VERSION,
            "source_validation": SOURCE_VALIDATION_POLICY_VERSION,
        },
        "created_at": _now_iso(),
        "extensions": {"confidence_components": {
            "decisive_studies": confidence.get("decisive_studies", 0),
            "usable_studies": confidence.get("usable_studies", 0),
            "has_direct_learning_evidence": direct_learning,
        }},
    }
    errors = validate_record("decision-snapshot", snapshot)
    if errors:
        raise ValueError(f"invalid decision snapshot: {errors}")
    return snapshot


def save_decision_snapshot(project: ProjectWorkspace, snapshot: dict) -> Path:
    """Persist a snapshot under decisions/ (immutable; never rewritten)."""
    path = project.path / "decisions" / f"{snapshot['decision_snapshot_id']}.json"
    if path.exists():
        raise FileExistsError(f"decision snapshot already exists: {path}")
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def decision_diff(previous: dict | None, current: dict, *,
                  previous_gaps: tuple[dict, ...] = (),
                  current_gaps: tuple[dict, ...] = ()) -> dict:
    """Machine-readable diff between two revision-bound DecisionSnapshots.

    `resolved_gaps` / `new_gaps` are computed from the GAP inputs, never
    claimed by the report layer. The diff never attributes graph change to
    the report.
    """
    prev_links = set(previous.get("key_evidence_links", [])) if previous else set()
    cur_links = set(current.get("key_evidence_links", []))
    prev_claims = dict(previous.get("claim_assessments", {})) if previous else {}
    cur_claims = dict(current.get("claim_assessments", {}))

    prev_gap_ids = {g["gap_id"] for g in previous_gaps}
    cur_gap_ids = {g["gap_id"] for g in current_gaps}

    changed_claims = []
    if previous:
        for cid in sorted(prev_claims | cur_claims):
            if prev_claims.get(cid) != cur_claims.get(cid):
                changed_claims.append(cid)

    return {
        "from_decision_snapshot_id": (previous or {}).get("decision_snapshot_id"),
        "to_decision_snapshot_id": current.get("decision_snapshot_id"),
        "from_graph_revision": (previous or {}).get("graph_revision"),
        "to_graph_revision": current.get("graph_revision"),
        "action_changed": (previous or {}).get("decision") != current.get("decision"),
        "confidence_changed": (previous or {}).get("confidence_label") != current.get("confidence_label"),
        "changed_claims": changed_claims,
        "new_key_evidence_links": sorted(cur_links - prev_links),
        "resolved_gaps": sorted(prev_gap_ids - cur_gap_ids),
        "new_gaps": sorted(cur_gap_ids - prev_gap_ids),
    }
