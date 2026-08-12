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


_REGISTRY: dict[str, CapabilitySpec] = {}


def _register(capability_id: str, *, input_contracts: tuple[str, ...],
              output_contracts: tuple[str, ...], deterministic_local: bool,
              scientific_gate: str | None = None) -> None:
    _REGISTRY[capability_id] = CapabilitySpec(
        capability_id=capability_id,
        input_contracts=input_contracts,
        output_contracts=output_contracts,
        deterministic_local=deterministic_local,
        scientific_gate=scientific_gate,
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
          scientific_gate="never fabricate p-values; ANALAYSIS_CAPABILITY_UNAVAILABLE")
_register("intervention_design", input_contracts=("decision-snapshot",),
          output_contracts=("intervention",), deterministic_local=False)
_register("evaluation_design", input_contracts=("decision-snapshot",),
          output_contracts=("evaluation",), deterministic_local=False)


def capability_registry() -> dict[str, CapabilitySpec]:
    """Return the frozen capability registry."""
    return dict(_REGISTRY)


def capability(capability_id: str) -> CapabilitySpec | None:
    return _REGISTRY.get(capability_id)
