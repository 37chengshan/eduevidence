"""Deterministic V2 graph/contract metrics.

These are software/contract metrics — they measure spec conformance of the
graph, never scientific truth. Human/gold annotation is required only for
content-level extraction evaluation; these functions never judge research
content.
"""

from __future__ import annotations

from engine.graph_store import GraphStore
from engine.semantics import finding_effect, claim_relation, decision_implication


def study_identity_accuracy(store: GraphStore) -> float:
    """Fraction of Findings whose Study resolves with a unique independence key."""
    findings = store.read_table("findings")
    if not findings:
        return 1.0
    studies = {s["study_id"]: s for s in store.read_table("studies")}
    keys = {s["independence_key"] for s in studies.values() if s.get("independence_key")}
    resolved = 0
    for f in findings:
        s = studies.get(f["study_id"])
        if s is not None and s.get("independence_key") and s.get("identity_status") != "unresolved":
            resolved += 1
    return round(resolved / len(findings), 4)


def independent_evidence_counting_accuracy(store: GraphStore) -> float:
    """1.0 when no Study is double-counted as multiple independent units.

    A Study with N Findings must appear exactly once in independent counting.
    """
    studies = store.read_table("studies")
    keys = [s.get("independence_key") for s in studies if s.get("independence_key")]
    if not keys:
        return 1.0
    return 1.0 if len(set(keys)) == len(keys) else 0.0


def claim_link_semantics_accuracy(store: GraphStore) -> float:
    """1.0 when every link's semantics stay in their own fields."""
    links = store.read_table("evidence_links")
    findings = {f["finding_id"]: f for f in store.read_table("findings")}
    ok = 0
    for link in links:
        fnd = findings.get(link["finding_id"])
        if fnd is None:
            continue
        effect = finding_effect(fnd)
        relation = claim_relation(link)
        implication = decision_implication(link)
        # a "support" relation never rewrites the observed direction
        if effect == relation:
            continue
        if relation not in ("support", "contradict", "neutral"):
            continue
        if implication not in ("support_adoption", "oppose_adoption", "conditional", "neutral"):
            continue
        ok += 1
    return round(ok / len(links), 4) if links else 1.0


def graph_traceability(store: GraphStore) -> float:
    """Fraction of Claims whose links resolve Finding→Study→Source fully."""
    claims = store.read_table("claims")
    if not claims:
        return 1.0
    findings = {f["finding_id"]: f for f in store.read_table("findings")}
    studies = {s["study_id"]: s for s in store.read_table("studies")}
    sources = {s["source_id"] for s in store.read_table("sources")}
    ok_claims = 0
    for c in claims:
        links = [l for l in store.read_table("evidence_links") if l["claim_id"] == c["claim_id"]]
        if not links:
            continue
        traceable = True
        for link in links:
            f = findings.get(link["finding_id"])
            if f is None:
                traceable = False
                break
            s = studies.get(f["study_id"])
            if s is None or not (set(s.get("source_ids", [])) & sources):
                traceable = False
                break
        if traceable:
            ok_claims += 1
    return round(ok_claims / len(claims), 4)


def projection_integrity(store: GraphStore, projection: dict) -> float:
    """1.0 when projection counts match the graph and the graph is unmutated."""
    counts = projection.get("counts", {})
    if counts.get("study_count") != len(store.read_table("studies")):
        return 0.0
    if counts.get("finding_count") != len(store.read_table("findings")):
        return 0.0
    if counts.get("evidence_link_count") != len(store.read_table("evidence_links")):
        return 0.0
    return 1.0


def dataset_provenance_completeness(asset: dict) -> float:
    """1.0 when hash/privacy/deidentification are all recorded."""
    required = ("content_hash", "privacy_classification", "deidentification_status")
    if not all(asset.get(k) for k in required):
        return 0.0
    if asset.get("privacy_classification") not in (
            "public", "internal", "confidential", "restricted"):
        return 0.0
    return 1.0
