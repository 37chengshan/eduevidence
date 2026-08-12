"""Schema-bound task briefs.

A task brief is generated from the registered schema metadata — required
fields and enums are read from the schema, never hard-coded twice in this
module. `build_task_brief()` accepts only `PlanStep(kind="capability")`;
calling it on a wait step raises a clear ValueError instead of generating a
fake agent task.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.contracts import load_schema, schema_path
from engine.planner import PlanStep


def _schema_section(schema: dict) -> str:
    lines: list[str] = []
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    for key in sorted(props):
        prop = props[key]
        line = f"- `{key}`"
        if key in required:
            line += " (REQUIRED)"
        if "enum" in prop:
            line += f" enum={prop['enum']}"
        if "pattern" in prop:
            line += f" pattern={prop['pattern']!r}"
        if "const" in prop:
            line += f" const={prop['const']!r}"
        lines.append(line)
    return "\n".join(lines) if lines else "(no properties)"


def build_task_brief(step: PlanStep, *, project: ProjectWorkspace,
                     input_payload: dict, output_path: Path) -> str:
    """Render a capability step into an executable agent brief.

    `project` is the ProjectWorkspace (for context ids); `input_payload`
    carries the input entity ids/records for this step; `output_path` is
    where the step's output artifact must be written.
    """
    if step.kind != "capability" or step.capability_id is None:
        raise ValueError(
            f"cannot build a task brief for non-capability step "
            f"{step.step_id!r} (kind={step.kind}); wait steps are real "
            f"states, not fake agent tasks"
        )
    cap = step.capability_id
    schema_name = step.output_contract
    if schema_name is None:
        raise ValueError(f"capability {cap} has no output contract")

    sch = load_schema(schema_name)
    sch_file = schema_path(schema_name)

    lines = [
        f"# Task brief: {cap}",
        "",
        f"Project: {project.project_id}",
        f"Output schema: {sch_file.relative_to(Path.cwd()) if sch_file.is_relative_to(Path.cwd()) else sch_file}",
        "",
        "## Output contract (schema-derived)",
        _schema_section(sch),
        "",
        "## Required fields",
        ", ".join(sch.get("required", [])) or "(none)",
        "",
        "## Validation",
        f"Validate the output with `engine.contracts.validate_record({schema_name!r}, record)` — "
        f"it must return [] (empty errors).",
        "",
        f"## Output path",
        str(output_path),
        "",
        "## Inputs",
        json.dumps(input_payload, ensure_ascii=False, indent=2),
    ]

    # capability-specific hard rules
    rules: dict[str, str] = {
        "finding_extraction": (
            "HARD RULE: `relation_to_claim` does NOT belong in a Finding. "
            "Findings record only what the study observed (`effect_direction`); "
            "the relation to a Claim lives on the EvidenceLink."),
        "source_validation": (
            "HARD RULE: a search snippet is never evidence content (RULE 2). "
            "Only fetched + validated source content may be extracted."),
        "counter_evidence_search": (
            "HARD RULE: seek null/negative/contradictory evidence, AI "
            "dependency, reduced transfer, novelty effects, self-selection "
            "bias, alternative explanations. Never fabricate counter-evidence."),
        "evidence_synthesis": (
            "HARD RULE: independent-study counting only. 5 Findings from one "
            "Study = 1 independent study; never count Findings as Studies."),
        "tribunal": (
            "HARD RULE: pass the Pre-Verdict Gate before adjudicating; "
            "critical failures forbid high-confidence verdicts."),
    }
    if cap in rules:
        lines += ["", "## Hard rules", rules[cap]]

    return "\n".join(lines) + "\n"
