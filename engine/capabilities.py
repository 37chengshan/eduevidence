"""Capability registry — the scientific capabilities a research plan can use.

The registry is independent of Agent names and model names: planning routes
by capability, execution routing (Agent MCP vs native) happens later and
orthogonally. A capability may be deterministic-local (Native Core) or
capability-discovered (SCP), and may carry a scientific gate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    input_contracts: tuple[str, ...]
    output_contracts: tuple[str, ...]
    deterministic_local: bool
    scientific_gate: str | None
    workflow_ids: tuple[str, ...] = ()
    experimental: bool = False


_REGISTRY: dict[str, CapabilitySpec] = {}

#: Jev / SemDecide Tier-0 acceleration IDs (opt-in via --experimental).
#: Not role-owned scientific work: omitted from capability_registry() by
#: default so the protocol role-ownership gate stays unchanged. Pass
#: include_experimental=True when wiring skill/workflows/experimental-jev.md.
EXPERIMENTAL_CAPABILITY_IDS: frozenset[str] = frozenset({
    "content_screen", "semantic_rerank", "field_extract",
    "classify_check", "claim_verify",
})


def _register(capability_id: str, *, input_contracts: tuple[str, ...],
              output_contracts: tuple[str, ...], deterministic_local: bool,
              scientific_gate: str | None = None,
              experimental: bool = False) -> None:
    _REGISTRY[capability_id] = CapabilitySpec(
        capability_id=capability_id,
        input_contracts=input_contracts,
        output_contracts=output_contracts,
        deterministic_local=deterministic_local,
        scientific_gate=scientific_gate,
        experimental=experimental,
    )


# Evidence Review pipeline
_register("research_framing", input_contracts=("research-intent",),
          output_contracts=("education-frame",), deterministic_local=False)
_register("literature_search", input_contracts=("education-frame",),
          output_contracts=("source",), deterministic_local=False)
_register("counter_evidence_search", input_contracts=("education-frame",),
          output_contracts=("source",), deterministic_local=False,
          scientific_gate="RULE 4: independent counter-evidence search")
_register("source_fetch", input_contracts=("source",),
          output_contracts=("fetch-result",), deterministic_local=False)
_register("source_validation", input_contracts=("source", "fetch-result"),
          output_contracts=("source",), deterministic_local=True,
          scientific_gate="snippet != evidence (RULE 2)")
_register("study_extraction", input_contracts=("source",),
          output_contracts=("study",), deterministic_local=False)
_register("finding_extraction", input_contracts=("study",),
          output_contracts=("finding",), deterministic_local=False)
_register("methodology_appraisal", input_contracts=("study",),
          output_contracts=("methodology-audit",), deterministic_local=False)
_register("claim_linking", input_contracts=("finding", "claim"),
          output_contracts=("evidence-link",), deterministic_local=False,
          scientific_gate="relation_to_claim lives on the link, never the finding")
_register("evidence_synthesis", input_contracts=("evidence-link", "methodology-audit"),
          output_contracts=("synthesis",), deterministic_local=True,
          scientific_gate="independent Study counting, never Finding counting")
_register("tribunal", input_contracts=("synthesis",),
          output_contracts=("decision-snapshot",), deterministic_local=False,
          scientific_gate="Pre-Verdict Gate before Tribunal")
_register("applicability_analysis", input_contracts=("evidence-link",),
          output_contracts=("applicability",), deterministic_local=False)
_register("knowledge_gap_detection", input_contracts=("education-frame", "claim"),
          output_contracts=("knowledge-gap",), deterministic_local=True)
_register("report_projection", input_contracts=("graph-revision",),
          output_contracts=("projection",), deterministic_local=True)
_register("report_rendering", input_contracts=("projection",),
          output_contracts=("report",), deterministic_local=True)

# Full Research Cycle additions
_register("study_design", input_contracts=("knowledge-gap",),
          output_contracts=("study-design",), deterministic_local=False,
          scientific_gate="No new study design without evidence grounding")
_register("measurement_design", input_contracts=("study-design",),
          output_contracts=("analysis-plan",), deterministic_local=False)
_register("data_validation", input_contracts=("dataset-asset",),
          output_contracts=("dataset-manifest",), deterministic_local=True,
          scientific_gate="provenance/hash/missingness before analysis")
_register("data_analysis", input_contracts=("dataset-manifest", "analysis-plan"),
          output_contracts=("analysis-run",), deterministic_local=True,
          scientific_gate="never fabricate p-values; ANALYSIS_CAPABILITY_UNAVAILABLE")
_register("intervention_design", input_contracts=("decision-snapshot",),
          output_contracts=("intervention",), deterministic_local=False)
_register("evaluation_design", input_contracts=("decision-snapshot",),
          output_contracts=("evaluation",), deterministic_local=False)

# Jev experimental Tier-0 (opt-in --experimental; mode 1/2/3).
# Acceleration only — never replaces Skeptic, pre_verdict_gate, methodology
# audit, or tribunal. Uncertain / invalid answers fail closed to the large model.
_register("content_screen", input_contracts=("fetch-result",),
          output_contracts=("screen-verdict",), deterministic_local=False,
          scientific_gate="experimental Tier-0; advisory screen before context; "
                          "RULE 2 snippet != evidence",
          experimental=True)
_register("semantic_rerank", input_contracts=("source",),
          output_contracts=("ranked-candidates",), deterministic_local=False,
          scientific_gate="experimental Tier-0; ranking is discovery order only",
          experimental=True)
_register("field_extract", input_contracts=("source",),
          output_contracts=("field-values",), deterministic_local=False,
          scientific_gate="experimental Tier-0; verbatim substring values only, "
                          "never model-written fields",
          experimental=True)
_register("classify_check", input_contracts=("source",),
          output_contracts=("classification",), deterministic_local=False,
          scientific_gate="experimental Tier-0; labels never replace "
                          "methodology_appraisal or outcome separation",
          experimental=True)
_register("claim_verify", input_contracts=("claim", "source"),
          output_contracts=("claim-verdict",), deterministic_local=False,
          scientific_gate="experimental Tier-0; does NOT replace Skeptic nine "
                          "checks or Pre-Verdict Gate",
          experimental=True)


def capability_registry(*, include_experimental: bool = False) -> dict[str, CapabilitySpec]:
    """Return the capability registry.

    Experimental Jev Tier-0 IDs are omitted by default (they are acceleration
    helpers, not role-owned scientific stages). Opt in with
    ``include_experimental=True`` when resolving --experimental modes 1/2/3.
    """
    if include_experimental:
        return dict(_REGISTRY)
    return {cid: spec for cid, spec in _REGISTRY.items() if not spec.experimental}


def experimental_capability_registry() -> dict[str, CapabilitySpec]:
    """Return only the Jev/SemDecide Tier-0 experimental capabilities."""
    return {cid: spec for cid, spec in _REGISTRY.items() if spec.experimental}


def capability(capability_id: str) -> CapabilitySpec | None:
    return _REGISTRY.get(capability_id)
