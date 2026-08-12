"""Capability task-DAG planner.

Plans research by scientific capability, never by Agent/model names. A
`PlanStep(kind="capability")` maps 1:1 to a capability; a
`PlanStep(kind="wait", wait_state="waiting_for_user_data")` is a real state
when the user's dataset is required but not yet present — never a fake
capability.

`intervention_design` / `evaluation_design` are decision_target-dependent:
included for `teaching_pilot` / `evaluation_plan` / `research_cycle`, not
forced for `evidence_review` to satisfy a fixed report template.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.capabilities import capability, capability_registry

_FULL_CYCLE_EXTRAS = ("study_design", "measurement_design")


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    kind: str  # capability | wait
    capability_id: str | None
    wait_state: str | None
    depends_on: tuple[str, ...]
    input_refs: tuple[str, ...]
    output_contract: str | None
    gate: str | None


def _step(step_id: str, capability_id: str, depends_on: tuple[str, ...]) -> PlanStep:
    spec = capability(capability_id)
    if spec is None:
        raise ValueError(f"unknown capability {capability_id!r}")
    return PlanStep(
        step_id=step_id,
        kind="capability",
        capability_id=capability_id,
        wait_state=None,
        depends_on=depends_on,
        input_refs=spec.input_contracts,
        output_contract=spec.output_contracts[0] if spec.output_contracts else None,
        gate=spec.scientific_gate,
    )


_EVIDENCE_REVIEW_STEPS = (
    ("research_framing", ()),
    ("literature_search", ("research_framing",)),
    ("counter_evidence_search", ("research_framing",)),
    ("source_fetch", ("literature_search", "counter_evidence_search")),
    ("source_validation", ("source_fetch",)),
    ("study_extraction", ("source_validation",)),
    ("finding_extraction", ("study_extraction",)),
    ("methodology_appraisal", ("study_extraction",)),
    ("claim_linking", ("finding_extraction",)),
    ("evidence_synthesis", ("claim_linking", "methodology_appraisal")),
    ("tribunal", ("evidence_synthesis",)),
    ("applicability_analysis", ("claim_linking",)),
    ("knowledge_gap_detection", ("research_framing", "claim_linking")),
    ("report_projection", ("tribunal", "knowledge_gap_detection")),
    ("report_rendering", ("report_projection",)),
)


def build_research_plan(*, mode: str, decision_target: str, depth: str,
                        has_grounding: bool,
                        has_dataset: bool) -> tuple[PlanStep, ...]:
    """Build the capability task DAG for a research mode.

    - evidence_review: the fixed 15-step pipeline.
    - full_research_cycle: Evidence Review + study_design/measurement_design
      after grounding/gap tasks; if `has_dataset=False`, emits a wait step
      instead of pretending data exists.
    - intervention/evaluation design depend on decision_target.
    """
    steps: list[PlanStep] = []
    for capability_id, depends in _EVIDENCE_REVIEW_STEPS:
        steps.append(_step(capability_id, capability_id, depends))

    if mode == "full_research_cycle":
        if not has_grounding:
            # the plan must not design a study before grounding exists; the
            # router already flagged requires_grounding_review, and the
            # executor runs the minimum Evidence Review first. The planner
            # still emits the design steps but they depend on tribunal/gap.
            pass
        for capability_id in _FULL_CYCLE_EXTRAS:
            dep = ("knowledge_gap_detection",) if capability_id == "study_design" \
                else ("study_design",)
            steps.append(_step(capability_id, capability_id, dep))
        if has_dataset:
            steps.append(_step("data_validation", "data_validation",
                               ("measurement_design",)))
            steps.append(_step("data_analysis", "data_analysis",
                               ("data_validation",)))
        else:
            steps.append(PlanStep(
                step_id="wait_for_user_data",
                kind="wait",
                capability_id=None,
                wait_state="waiting_for_user_data",
                depends_on=("measurement_design",),
                input_refs=(),
                output_contract=None,
                gate=None,
            ))

    target_design = decision_target in ("teaching_pilot", "evaluation_plan",
                                        "research_cycle")
    if target_design:
        steps.append(_step("intervention_design", "intervention_design",
                           ("tribunal",)))
        steps.append(_step("evaluation_design", "evaluation_design",
                           ("tribunal",)))

    return tuple(steps)


def plan_capability_ids(plan: tuple[PlanStep, ...]) -> list[str]:
    """Capability ids in plan order (excludes wait steps)."""
    return [s.capability_id for s in plan if s.kind == "capability" and s.capability_id]
