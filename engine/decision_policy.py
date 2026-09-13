"""Single source of truth for the ADOPT direct-evidence gate.

The four-state decision (ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE) is
computed by two layers that must never drift apart:

  * engine/tribunal.py - V2 Evidence Graph adjudication
  * scripts/pre_verdict_gate.py - V1 run/example-pack gate enforcement

Before this module existed the rule lived only inside the tribunal, so the V1
gate could not enforce it and a hand-written verdict could carry any action it
liked. Both layers now resolve the 'which outcome categories count for this
domain' question here, and the V1 gate additionally re-derives direct-evidence
presence from the pack's own evidence records.

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


def decision_action(*, confidence_label: str, decisive_relations: dict[str, str],
                    has_direct_primary_evidence: bool) -> str:
    """Gate-enforced decision action (uppercase four-state).

    REJECT requires usable direct opposition evidence (an independent Study
    folded to oppose_adoption). Low/Insufficient can never yield ADOPT.
    ADOPT additionally requires direct evidence on the domain's PRIMARY
    outcome category: High + decisive support WITHOUT such evidence downgrades
    to PILOT - task performance and procedural efficiency are not
    decision-grade effects. Moderate + decisive support -> PILOT; otherwise
    INSUFFICIENT_EVIDENCE.
    """
    has_oppose = any(r == "oppose_adoption" for r in decisive_relations.values())
    has_support = any(r == "support_adoption" for r in decisive_relations.values())
    if has_oppose:
        return "REJECT"
    if (confidence_label == ADOPT_REQUIRED_LABEL and has_support
            and has_direct_primary_evidence):
        return "ADOPT"
    if confidence_label in ("High", "Moderate") and has_support:
        return "PILOT"
    return "INSUFFICIENT_EVIDENCE"
