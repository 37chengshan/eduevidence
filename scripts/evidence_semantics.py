#!/usr/bin/env python3
"""evidence_semantics.py — Centralized Evidence semantic helpers (A-1).

The three evidence "direction" semantics are deliberately distinct; every
consumer must go through these helpers instead of re-interpreting the raw
fields, so the semantics cannot drift across files again:

    claim_relation(ev)     support | contradict | neutral
        Does this evidence support the specific claim it is bound to?
        (field: relation_to_claim; legacy fallback: direction)

    effect_direction(ev)   positive | negative | null
        What did the study observe? (field: effect_direction)

    decision_relation(ev)  support_adoption | oppose_adoption | conditional | neutral
        What does this evidence mean for the final teaching decision?
        (field: decision_relation; deterministic fallback derived from the
        claim relation when the field is absent)

Consumers:

    Claim Audit                    -> claim_relation
    Outcome Visualization          -> effect_direction
    Cross-study Consistency        -> decision_relation

V2 note: the Research Engine's V2 semantics live in `engine/semantics.py`
(finding_effect / claim_relation / decision_implication) and operate on the
versioned graph entities. This module keeps its legacy flat-evidence API for
V1 callers; the two layers are structurally different and must not be mixed.
"""
from __future__ import annotations

from typing import Any

CLAIM_RELATIONS = ("support", "contradict", "neutral")
EFFECT_DIRECTIONS = ("positive", "negative", "null")
DECISION_RELATIONS = ("support_adoption", "oppose_adoption", "conditional", "neutral")

_CLAIM_TO_DECISION = {
    "support": "support_adoption",
    "contradict": "oppose_adoption",
    "neutral": "neutral",
}


def claim_relation(evidence: dict[str, Any]) -> str:
    """Relation of one evidence object to the claim it is bound to.

    Reads the new-contract field ``relation_to_claim`` (support | contradict |
    neutral); falls back to the legacy ``direction`` field for backward
    compatibility. Returns 'neutral' when neither is present/valid.
    """
    relation = evidence.get("relation_to_claim")
    if relation in CLAIM_RELATIONS:
        return relation
    legacy = evidence.get("direction")
    if legacy in CLAIM_RELATIONS:
        return legacy
    return "neutral"


def effect_direction(evidence: dict[str, Any]) -> str:
    """Observed effect direction of one evidence object.

    Reads ``effect_direction`` (positive | negative | null). Returns 'null'
    when the field is absent or invalid — a missing measurement is treated as
    no measurable effect, never as an invented one.
    """
    effect = evidence.get("effect_direction")
    if effect in EFFECT_DIRECTIONS:
        return effect
    return "null"


def decision_relation(evidence: dict[str, Any]) -> str:
    """Relation of one evidence object to the final teaching decision.

    Reads ``decision_relation`` (support_adoption | oppose_adoption |
    conditional | neutral). When the field is absent, derives a deterministic
    fallback from the claim relation (support -> support_adoption,
    contradict -> oppose_adoption, neutral -> neutral) so legacy data keeps
    working without silent semantic drift.
    """
    decision = evidence.get("decision_relation")
    if decision in DECISION_RELATIONS:
        return decision
    return _CLAIM_TO_DECISION[claim_relation(evidence)]
