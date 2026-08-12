"""Claim synthesis with independent-study semantics.

Status rule (frozen baseline in code + tests): a usable Study requires
valid/accepted_partial Source provenance, resolvable Study identity, latest
MethodologyAudit != `fail`, and valid active Finding/Link. Multiple Findings
from one Study never create multiple votes.

    support-only usable Studies  → supported
    contradiction-only           → refuted
    both independent directions  → contested
    no decisive usable Study / neutral-only → insufficient
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.contracts import validate_record
from engine.graph_store import GraphStore
from engine.semantics import claim_relation, decision_implication

VALID_SOURCE_STATUSES = ("valid", "accepted_partial")


@dataclass(frozen=True)
class ClaimSynthesis:
    claim_id: str
    status: str
    study_ids: tuple[str, ...]
    independent_sample_keys: tuple[str, ...]
    supporting_link_ids: tuple[str, ...]
    contradicting_link_ids: tuple[str, ...]
    neutral_link_ids: tuple[str, ...]
    methodology_summary: dict
    directness_summary: dict
    unresolved_conflicts: tuple[str, ...]
    missing_evidence: tuple[str, ...]


def _usable_studies(store: GraphStore) -> dict[str, dict]:
    """Study id → Study record for usable studies.

    Usable = resolvable identity + at least one valid/accepted_partial source.
    """
    sources = {s["source_id"]: s for s in store.read_table("sources")}
    usable: dict[str, dict] = {}
    for s in store.read_table("studies"):
        if s.get("identity_status") == "unresolved":
            continue
        if not any(sid in sources and sources[sid]["validation_status"] in VALID_SOURCE_STATUSES
                   for sid in s.get("source_ids", [])):
            continue
        usable[s["study_id"]] = s
    return usable


def _latest_audits(store: GraphStore) -> dict[str, dict]:
    """Study id → latest MethodologyAudit (by audited_at)."""
    latest: dict[str, dict] = {}
    for a in store.read_table("audits"):
        cur = latest.get(a["study_id"])
        if cur is None or a["audited_at"] >= cur["audited_at"]:
            latest[a["study_id"]] = a
    return latest


def synthesize_claim(store: GraphStore, claim_id: str) -> ClaimSynthesis:
    usable_studies = _usable_studies(store)
    audits = _latest_audits(store)
    findings = {f["finding_id"]: f for f in store.read_table("findings")}
    links = store.read_table("evidence_links")
    claims = {c["claim_id"]: c for c in store.read_table("claims")}
    if claim_id not in claims:
        raise KeyError(f"claim {claim_id} not in graph")

    claim = claims[claim_id]
    claim_links = [l for l in links if l["claim_id"] == claim_id]

    # group links per usable study
    study_links: dict[str, list[dict]] = {}
    for link in claim_links:
        fnd = findings.get(link["finding_id"])
        if fnd is None:
            continue
        sid = fnd["study_id"]
        study = usable_studies.get(sid)
        if study is None:
            continue
        audit = audits.get(sid)
        if audit is not None and audit.get("overall_status") == "fail":
            continue
        study_links.setdefault(sid, []).append(link)

    # per-study decision relation (independent votes)
    from collections import Counter
    support_votes: list[str] = []
    oppose_votes: list[str] = []
    neutral_only: list[str] = []
    independent_samples: set[str] = set()

    study_ids: list[str] = []
    supporting_link_ids: list[str] = []
    contradicting_link_ids: list[str] = []
    neutral_link_ids: list[str] = []
    unresolved: list[str] = []

    for sid, links_for_study in sorted(study_links.items()):
        study = usable_studies[sid]
        independent_samples.add(study["independence_key"])
        relations = [claim_relation(l) for l in links_for_study]
        implications = [decision_implication(l) for l in links_for_study]
        has_support = any(r == "support" for r in relations)
        has_contradict = any(r == "contradict" for r in relations)
        has_conditional = any(i == "conditional" for i in implications)
        if has_conditional:
            unresolved.append(f"{sid}: conditional implication")
        if has_support and not has_contradict:
            support_votes.append(sid)
        elif has_contradict and not has_support:
            oppose_votes.append(sid)
        elif has_support and has_contradict:
            # within-study conflict is a real unresolved conflict, not a vote
            unresolved.append(f"{sid}: within-study support+contradict links")
        else:
            neutral_only.append(sid)
        study_ids.append(sid)
        for l in links_for_study:
            rel = claim_relation(l)
            if rel == "support":
                supporting_link_ids.append(l["evidence_link_id"])
            elif rel == "contradict":
                contradicting_link_ids.append(l["evidence_link_id"])
            else:
                neutral_link_ids.append(l["evidence_link_id"])

    if support_votes and not oppose_votes:
        status = "supported"
    elif oppose_votes and not support_votes:
        status = "refuted"
    elif support_votes and oppose_votes:
        status = "contested"
    else:
        status = "insufficient"

    # methodology + directness summaries
    meth_summary: dict = {"studies": len(study_ids), "audit_fail": 0, "concern": 0, "pass": 0}
    directness_values: list[int] = []
    for sid in study_ids:
        a = audits.get(sid)
        if a is None:
            continue
        status_ = a.get("overall_status")
        meth_summary[status_ if status_ in meth_summary else "concern"] += 1
        for l in study_links.get(sid, []):
            directness_values.append(int(l.get("directness", 0)))

    return ClaimSynthesis(
        claim_id=claim_id,
        status=status,
        study_ids=tuple(study_ids),
        independent_sample_keys=tuple(sorted(independent_samples)),
        supporting_link_ids=tuple(supporting_link_ids),
        contradicting_link_ids=tuple(contradicting_link_ids),
        neutral_link_ids=tuple(neutral_link_ids),
        methodology_summary=meth_summary,
        directness_summary={"mean": (sum(directness_values) / len(directness_values)
                                     if directness_values else 0.0),
                            "count": len(directness_values)},
        unresolved_conflicts=tuple(unresolved),
        missing_evidence=(),
    )


def synthesize_project(store: GraphStore) -> tuple[ClaimSynthesis, ...]:
    claims = store.read_table("claims")
    return tuple(synthesize_claim(store, c["claim_id"]) for c in sorted(
        claims, key=lambda c: c["claim_id"]))
