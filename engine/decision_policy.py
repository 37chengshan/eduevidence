"""Single source of truth for the four-state decision gate.

The four-state decision (ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE) is
computed by two layers that must never drift apart:

  * engine/tribunal.py - V2 Evidence Graph adjudication
  * scripts/pre_verdict_gate.py - V1 run/example-pack gate enforcement

Before this module existed the rule lived only inside the tribunal, so the V1
gate could not enforce it and a hand-written verdict could carry any action it
liked. Both layers now resolve the 'which outcome categories count for this
domain' question here, and the V1 gate additionally re-derives direct-evidence
presence from the pack's own evidence records.

Decision matrix (gate-enforced):

  conflict/mixed/support+oppose        -> INSUFFICIENT_EVIDENCE (unresolved_conflict)
  oppose_adoption (oppose-only)        -> REJECT
  High    + support + direct_primary   -> ADOPT
  High    + support + missing direct   -> PILOT   (downgrade_reason=missing_direct_primary)
  Moderate+ support (+/- direct)    -> PILOT   (confidence_band | missing_direct_primary)
  Low / 无支持 / 间接无 Moderate    -> INSUFFICIENT_EVIDENCE

Stdlib only, consistent with the "Native Core" policy of engine/.
"""
from __future__ import annotations

#: Category buckets that count as a domain's PRIMARY effect for the ADOPT gate.
#: The gate asks 'is there direct evidence on the outcome this decision is
#: actually about?' - for education that is a learning outcome (task
#: performance and process measures never qualify); for policy it is the
#: policy-effectiveness / cost class. Every entry must name a category the
#: domain registry declares, which check_protocol_alignment.py enforces.
PRIMARY_EFFECT_CATEGORIES: dict[str, tuple[str, ...]] = {
    "education": ("learning",),
    "policy": ("effectiveness", "cost"),
}

#: Directness (0-2) at which an evidence link may carry an ADOPT claim.
ADOPT_DIRECTNESS = 2

#: Confidence band required before ADOPT is possible at all.
ADOPT_REQUIRED_LABEL = "High"

#: Confidence band that can still reach PILOT given a verifiable primary path.
PILOT_REQUIRED_LABEL = "Moderate"

#: Auditable reasons a decision was stepped down from a higher action.
DOWNGRADE_MISSING_DIRECT_PRIMARY = "missing_direct_primary"
DOWNGRADE_CONFIDENCE_BAND = "confidence_band"
DOWNGRADE_GATE_CRITICAL = "gate_critical"
DOWNGRADE_UNRESOLVED_CONFLICT = "unresolved_conflict"

#: Relation values that mark unresolved conflict rather than a clean vote.
CONFLICT_RELATIONS = frozenset({"conflict", "mixed"})


def primary_effect_categories(domain: str) -> tuple[str, ...]:
    """Categories that satisfy the ADOPT direct-evidence gate for a domain."""
    from engine.taxonomy import categories as taxonomy_categories

    declared = PRIMARY_EFFECT_CATEGORIES.get(domain)
    if declared:
        known = taxonomy_categories(domain)
        missing = [c for c in declared if c not in known]
        if missing:
            raise ValueError(
                'domain ' + repr(domain) + ' ADOPT gate references undeclared '
                'categories ' + repr(missing) + '; declared: ' + repr(sorted(known)))
        return declared
    known = taxonomy_categories(domain)
    if not known:
        raise ValueError('domain ' + repr(domain) + ' declares no outcome categories')
    return (next(iter(known)),)


def outcome_category(domain: str, value: str, primary: tuple[str, ...]) -> str | None:
    """Resolve an outcome value to its category, or None when unresolvable.

    The outcomes table stores CATEGORY buckets (learning / task_performance /
    process / risk, plus each domain's own buckets), while V1 packs store raw
    taxonomy tokens. Accept a category directly and, for a token, resolve it
    through the registry. An unknown value returns None so callers fail
    closed instead of silently treating it as decision-grade evidence.
    """
    from engine.taxonomy import TaxonomyError, category_of

    if value in primary:
        return value
    try:
        return category_of(domain, value)
    except (TaxonomyError, ValueError):
        return None


def decision_outcome(*, confidence_label: str, decisive_relations: dict[str, str],
                     has_direct_primary_evidence: bool) -> dict[str, str | None]:
    """Gate-enforced decision action plus auditable downgrade_reason.

    Returns ``{"action": <uppercase four-state>, "downgrade_reason": <str|None>}``.

    REJECT requires usable direct opposition evidence and no decisive support
    (oppose-only). Mixed support+oppose or any conflict/conditional/mixed
    relation is an unresolved conflict → INSUFFICIENT_EVIDENCE (never ADOPT,
    never a bare REJECT). ADOPT requires High confidence, decisive support,
    AND direct evidence on the domain's PRIMARY outcome category. PILOT is
    the bounded-trial exit: High + support missing that direct primary
    evidence (``missing_direct_primary``), or Moderate + support on a
    verifiable primary-outcome path (``confidence_band``).
    """
    has_oppose = any(r == "oppose_adoption" for r in decisive_relations.values())
    has_support = any(r == "support_adoption" for r in decisive_relations.values())
    has_conflict = any(r in CONFLICT_RELATIONS for r in decisive_relations.values())

    # Unresolved conflict (mixed votes or explicit conflict tags) fails closed
    # before any ADOPT/PILOT/REJECT claim.
    if has_conflict or (has_oppose and has_support):
        return {"action": "INSUFFICIENT_EVIDENCE",
                "downgrade_reason": DOWNGRADE_UNRESOLVED_CONFLICT}

    if has_oppose:
        return {"action": "REJECT", "downgrade_reason": None}

    if (confidence_label == ADOPT_REQUIRED_LABEL and has_support
            and has_direct_primary_evidence):
        return {"action": "ADOPT", "downgrade_reason": None}

    if confidence_label == ADOPT_REQUIRED_LABEL and has_support:
        return {"action": "PILOT", "downgrade_reason": DOWNGRADE_MISSING_DIRECT_PRIMARY}

    # Bounded-trial exit: Moderate + support reaches PILOT even without a
    # verified primary path (Gate C allows PILOT / INSUFFICIENT / REJECT).
    if confidence_label == PILOT_REQUIRED_LABEL and has_support:
        reason = (None if has_direct_primary_evidence
                  else DOWNGRADE_MISSING_DIRECT_PRIMARY)
        if has_direct_primary_evidence:
            reason = DOWNGRADE_CONFIDENCE_BAND
        return {"action": "PILOT", "downgrade_reason": reason}

    # Low / 间接 (Moderate without a verifiable primary path) -> INSUFFICIENT.
    if confidence_label in ("Low", "Insufficient"):
        return {"action": "INSUFFICIENT_EVIDENCE",
                "downgrade_reason": DOWNGRADE_CONFIDENCE_BAND}
    if confidence_label == PILOT_REQUIRED_LABEL and has_support:
        return {"action": "INSUFFICIENT_EVIDENCE",
                "downgrade_reason": DOWNGRADE_MISSING_DIRECT_PRIMARY}
    return {"action": "INSUFFICIENT_EVIDENCE", "downgrade_reason": None}


def decision_action(*, confidence_label: str, decisive_relations: dict[str, str],
                    has_direct_primary_evidence: bool) -> str:
    """Gate-enforced decision action (uppercase four-state)."""
    return decision_outcome(
        confidence_label=confidence_label,
        decisive_relations=decisive_relations,
        has_direct_primary_evidence=has_direct_primary_evidence,
    )["action"]


def downgrade_reason(*, confidence_label: str, decisive_relations: dict[str, str],
                     has_direct_primary_evidence: bool) -> str | None:
    """Auditable reason the action was stepped down (or None when not downgraded)."""
    return decision_outcome(
        confidence_label=confidence_label,
        decisive_relations=decisive_relations,
        has_direct_primary_evidence=has_direct_primary_evidence,
    )["downgrade_reason"]
