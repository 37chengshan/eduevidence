"""Centralized V2 semantics — the three "direction" meanings never conflate:

    finding_effect(finding)        = what the study actually observed
                                     (Finding.effect_direction)
    claim_relation(link)           = does this result support the Claim?
                                     (EvidenceLink.relation_to_claim)
    decision_implication(link)     = what it means for the current decision
                                     (EvidenceLink.decision_implication)

Independent evidence counting is Study/sample-level, never Finding-level:
5 Findings from one Study = 1 independent study.
"""

from __future__ import annotations

FINDING_EFFECTS = ("positive", "negative", "null", "mixed", "not_applicable")
CLAIM_RELATIONS = ("support", "contradict", "neutral")
DECISION_IMPLICATIONS = ("support_adoption", "oppose_adoption", "conditional", "neutral")

_RELATION_TO_IMPLICATION = {
    "support": "support_adoption",
    "contradict": "oppose_adoption",
    "neutral": "neutral",
}


def finding_effect(finding: dict) -> str:
    """Observed effect direction of a V2 Finding.

    Missing/invalid direction is reported as 'null' (no measurable effect) —
    never invented as positive or negative.
    """
    effect = finding.get("effect_direction")
    if effect in FINDING_EFFECTS:
        return effect
    return "null"


def claim_relation(link: dict) -> str:
    """Relation of an EvidenceLink to the Claim it binds."""
    relation = link.get("relation_to_claim")
    if relation in CLAIM_RELATIONS:
        return relation
    return "neutral"


def decision_implication(link: dict) -> str:
    """Implication of an EvidenceLink for the current teaching decision.

    Falls back deterministically from the claim relation when the field is
    absent (legacy safety); schema-valid links always carry the field.
    """
    implication = link.get("decision_implication")
    if implication in DECISION_IMPLICATIONS:
        return implication
    return _RELATION_TO_IMPLICATION[claim_relation(link)]


def independent_study_ids(findings: list[dict]) -> set[str]:
    """Unique Study IDs behind a set of Findings (independent-study counting)."""
    return {f["study_id"] for f in findings if f.get("study_id")}


def independent_sample_keys(studies: list[dict]) -> set[str]:
    """Unique independence keys across Studies (independent sample counting)."""
    keys = {s["independence_key"] for s in studies if s.get("independence_key")}
    return keys


def graph_counts(store) -> dict[str, int]:
    """Entity counts of the active graph revision.

    `study_count` is the number of Study entities — never the number of
    Findings. Use `independent_study_ids`/`independent_sample_keys` for
    synthesis-level independent counting.
    """
    return {
        "source_count": len(store.read_table("sources")),
        "study_count": len(store.read_table("studies")),
        "finding_count": len(store.read_table("findings")),
        "outcome_count": len(store.read_table("outcomes")),
        "claim_count": len(store.read_table("claims")),
        "evidence_link_count": len(store.read_table("evidence_links")),
        "audit_count": len(store.read_table("audits")),
    }
