#!/usr/bin/env python3
"""check_protocol_alignment.py — Protocol five-way alignment gate.

Every scientific contract in this repository is declared in more than one
place: the workflow registry (engine/workflows.py), the capability registry
(engine/capabilities.py), the role registry (skill/roles/registry.yaml), the
role prompts (skill/agents/*.md), the stage briefs (skill/task-briefs/*.md),
the sub-skill recipes (skill/sub-skills/*/SKILL.md), the routing requirements
(integrations/agent_mcp.py) and the packaging manifest (packaging/*).

Drift between them is silent: a role can lose its brief, a capability can
exist with no recipe, a version can be bumped in one file only. This gate
makes that drift fail loudly. Stdlib only; a non-zero exit blocks CI.

Usage:
    python3 scripts/check_protocol_alignment.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.capabilities import capability_registry  # noqa: E402
from engine.versions import ENGINE_VERSION  # noqa: E402
from engine.workflows import execution_stages, workflow_registry  # noqa: E402

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

#: Projection-layer capabilities sit outside the scientific stage model
#: (engine/workflows.py: Projection is not a scientific stage), so they are
#: owned by the projection brief rather than by a scientific role.
PROJECTION_CAPABILITIES = {"report_projection", "report_rendering"}


def list_domains_from_registry() -> list[dict]:
    """Registered domains (evidencecore is the registry owner)."""
    from engine.evidencecore import list_domains

    return list_domains()


def _frontmatter(path: Path) -> dict[str, str]:
    """Parse the flat key: value frontmatter used by skills and role prompts."""
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if line.strip().startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.split("#", 1)[0].strip()
    return fields


def _registry_roles() -> dict[str, dict]:
    """The role registry is a small fixed-shape YAML file; parse it narrowly."""
    text = (ROOT / "skill" / "roles" / "registry.yaml").read_text(encoding="utf-8")
    roles: dict[str, dict] = {}
    current: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        if raw.startswith("roles:"):
            continue
        if raw.startswith("execution:"):
            break
        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", raw):
            current = raw.strip().rstrip(":")
            roles[current] = {}
            continue
        if current and raw.strip().startswith("stages:"):
            stages = raw.split(":", 1)[1].strip().strip("[]")
            roles[current]["stages"] = [s.strip() for s in stages.split(",") if s.strip()]
        elif current and raw.strip().startswith("capabilities:"):
            caps = raw.split(":", 1)[1].strip().strip("[]")
            roles[current]["capabilities"] = [c.strip() for c in caps.split(",") if c.strip()]
        elif current and ":" in raw.strip():
            key, _, value = raw.strip().partition(":")
            roles[current][key.strip()] = value.strip()
    return roles


def _merge_role(roles: dict[str, dict], name: str, stage: str, capability: str,
                critical: bool | None = None, independence: bool | None = None) -> None:
    entry = roles.setdefault(name, {"stages": [], "capabilities": []})
    if stage not in entry["stages"]:
        entry["stages"].append(stage)
    for cap in capability.split("+"):
        cap = cap.strip()
        if cap and cap not in entry["capabilities"]:
            entry["capabilities"].append(cap)
    if critical is not None:
        entry["critical_path"] = "true" if critical else "false"
    if independence:
        entry["independence_required"] = "true"


def check() -> list[str]:
    errors: list[str] = []

    stages = list(execution_stages())
    scientific_stages = [s for s in stages if s != "projection"]

    # ---------------------------------------------------------------- briefs
    brief_dir = ROOT / "skill" / "task-briefs"
    briefs = {p.stem for p in brief_dir.glob("*.md")}
    for stage in stages:
        if stage not in briefs:
            errors.append(f"stage {stage!r} has no task brief in skill/task-briefs/")
    for extra in sorted(briefs - set(stages) - {"present"}):
        errors.append(f"task brief {extra!r} does not map to a canonical stage")

    # ---------------------------------------------------------------- roles
    registry = _registry_roles()
    if not registry:
        errors.append("skill/roles/registry.yaml declares no roles")
    agent_files = {p.stem: p for p in (ROOT / "skill" / "agents").glob("*.md")}
    if set(registry) != set(agent_files):
        errors.append("role registry and skill/agents/*.md disagree: "
                      f"registry-only={sorted(set(registry) - set(agent_files))} "
                      f"agent-only={sorted(set(agent_files) - set(registry))}")

    stage_owner: dict[str, str] = {}
    for role, entry in registry.items():
        for stage in entry.get("stages", []):
            if stage in stage_owner:
                errors.append(f"stage {stage!r} is owned by both {stage_owner[stage]!r} and {role!r}")
            stage_owner[stage] = role
    for stage in scientific_stages:
        if stage not in stage_owner:
            errors.append(f"stage {stage!r} has no owning role in the registry")

    # Registry capabilities must be engine capability IDs: a free-text label
    # here silently detaches the role from the capability it claims to run.
    for role, entry in registry.items():
        for cap in entry.get("capabilities", []):
            if cap not in capability_registry():
                errors.append(f"registry role {role!r} declares capability {cap!r}, "
                              "which is not in engine/capabilities.py")

    # Independence is graded: the skeptic must come from a different model
    # family, the method reviewer must be separated from the content judgement.
    independence = {role: entry.get("independence_required")
                    for role, entry in registry.items() if entry.get("independence_required")}
    if independence != {"skeptic": "different-model-family",
                        "method-reviewer": "role-separation"}:
        expected = {"skeptic": "different-model-family", "method-reviewer": "role-separation"}
        errors.append("independence_required must be "
                      f"{expected}, found {independence}")

    # ------------------------------------------------- role prompt frontmatter
    for role, path in agent_files.items():
        fields = _frontmatter(path)
        if fields.get("name") != role:
            errors.append(f"{path.name}: frontmatter name {fields.get('name')!r} != filename {role!r}")
        if fields.get("role_id") != role:
            errors.append(f"{path.name}: missing role_id: {role}")
        if not fields.get("capabilities"):
            errors.append(f"{path.name}: missing capabilities declaration")
        if not fields.get("output_contracts"):
            errors.append(f"{path.name}: missing output_contracts declaration")
        for banned in ("default_cli", "default_model"):
            if banned in fields:
                errors.append(f"{path.name}: {banned} must not be bound in the role prompt "
                              "(model/CLI choice is a user-confirmed routing decision)")
        for token in ("claude-", "gpt-", "deepseek-", "glm-", "kimi-"):
            if token in fields.get("recommended_reasoning", ""):
                errors.append(f"{path.name}: recommended_reasoning must not contain a model name")
        if role in registry:
            declared = set(registry[role].get("capabilities", []))
            prompt_caps = {c.strip() for c in fields.get("capabilities", "").split(",") if c.strip()}
            unknown = {c for c in prompt_caps if c not in capability_registry()}
            unmapped = {c for c in unknown if not c.startswith("(")}
            if unmapped:
                errors.append(f"{path.name}: capabilities not in the capability registry: {sorted(unmapped)}")
            missing = {c for c in declared if c in capability_registry()} - prompt_caps
            if missing:
                errors.append(f"{path.name}: registry capabilities absent from the prompt: "
                              f"{sorted(missing)}")
        if registry.get(role, {}).get("critical_path") == "true":
            if fields.get("critical_path") != "true":
                errors.append(f"{path.name}: registry marks this role critical_path but the "
                              "prompt does not declare critical_path: true")

    # ----------------------------------------------- routing-side requirements
    from integrations.agent_mcp import ROLE_REQUIREMENTS  # noqa: E402
    if set(ROLE_REQUIREMENTS) != set(registry):
        errors.append("integrations.agent_mcp.ROLE_REQUIREMENTS and the role registry disagree: "
                      f"routing-only={sorted(set(ROLE_REQUIREMENTS) - set(registry))} "
                      f"registry-only={sorted(set(registry) - set(ROLE_REQUIREMENTS))}")
    for role, reqs in ROLE_REQUIREMENTS.items():
        for banned in ("default_cli", "default_model", "model", "cli"):
            if banned in reqs:
                errors.append(f"ROLE_REQUIREMENTS[{role!r}] must not bind {banned!r}")
        wants_family = registry.get(role, {}).get("independence_required") == "different-model-family"
        if wants_family and reqs.get("independence") != "different-model-family":
            errors.append(f"ROLE_REQUIREMENTS[{role!r}] must require a different model family")

    # ------------------------------------------------------------ capabilities
    capabilities = capability_registry()
    sub_skills = sorted(p for p in (ROOT / "skill" / "sub-skills").iterdir()
                        if p.is_dir() and not p.name.startswith("."))
    if len(sub_skills) < 5:
        errors.append(f"expected at least 5 sub-skills, found {len(sub_skills)}")
    mapped: set[str] = set()
    for skill_dir in sub_skills:
        path = skill_dir / "SKILL.md"
        if not path.is_file():
            errors.append(f"sub-skill {skill_dir.name} has no SKILL.md")
            continue
        fields = _frontmatter(path)
        if fields.get("name") != skill_dir.name:
            errors.append(f"{skill_dir.name}/SKILL.md: name {fields.get('name')!r} != directory")
        declared = fields.get("capability", "")
        if not declared:
            errors.append(f"{skill_dir.name}/SKILL.md: missing capability declaration")
            continue
        for cap in declared.split("+"):
            cap = cap.strip().split()[0] if cap.strip() else ""
            if cap and not cap.startswith("("):
                mapped.add(cap)
                if cap not in capabilities:
                    errors.append(f"{skill_dir.name}/SKILL.md: capability {cap!r} is not in "
                                  "engine/capabilities.py")
    # Every registered capability must be owned by at least one role, and every
    # recipe capability must be one the engine actually registers.
    owned: set[str] = set()
    for entry in registry.values():
        owned.update(entry.get("capabilities", []))
    for cap in capabilities:
        if cap not in owned and cap not in PROJECTION_CAPABILITIES:
            errors.append(f"capability {cap!r} is registered in engine/capabilities.py "
                          "but no role owns it")
    for cap in sorted(mapped):
        if cap in capabilities and cap not in owned and cap not in PROJECTION_CAPABILITIES:
            errors.append(f"sub-skill capability {cap!r} is owned by no role")

    # ---------------------------------------------------------------- workflows
    workflow_dir = ROOT / "skill" / "workflows"
    workflow_files = {p.stem for p in workflow_dir.glob("*.md")}
    registry_workflows = workflow_registry()
    public = {w for w in registry_workflows if w != "full_research_cycle"}
    normalised = {name.replace("_", "-") for name in public}
    if not normalised <= workflow_files:
        errors.append("workflows missing a runbook: "
                      f"{sorted(normalised - workflow_files)}")
    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for name in public:
        reference = f"skill/workflows/{name.replace('_', '-')}.md"
        if reference not in skill_text:
            errors.append(f"SKILL.md does not route to {reference}")

    skill_md = root_skill_text = skill_text  # alias for readability
    for stage in scientific_stages:
        if f"| {stage.capitalize()} " not in skill_md and stage not in skill_md:
            errors.append(f"SKILL.md does not mention stage {stage!r}")

    # ------------------------------------------------------------- taxonomy
    # The registry is the authority for outcome tokens and their categories;
    # the JSON Schemas carry static enums because JSON Schema cannot read a
    # file at validation time. This dimension is what keeps the static enums
    # honest: drift between a schema enum and the registry fails the gate.
    from engine.taxonomy import (
        all_tokens_ordered,
        categories as taxonomy_categories,
    )

    registered_tokens = set(all_tokens_ordered())
    evidence_path = ROOT / "schemas" / "evidence.schema.json"
    if evidence_path.is_file():
        evidence_schema = json.loads(evidence_path.read_text(encoding="utf-8"))
        enum = (evidence_schema.get("properties", {})
                .get("outcome_type", {}).get("enum"))
        if not isinstance(enum, list) or not enum:
            errors.append("schemas/evidence.schema.json declares no outcome_type enum")
        else:
            missing = sorted(registered_tokens - set(enum))
            extra = sorted(set(enum) - registered_tokens)
            if missing:
                errors.append(
                    "outcome_type enum is missing registered token(s): " + repr(missing))
            if extra:
                errors.append(
                    "outcome_type enum declares unregistered token(s): " + repr(extra))

    # Every domain's ADOPT-gate categories must be categories it declares.
    from engine.tribunal import primary_effect_categories

    for domain_id in (d["id"] for d in list_domains_from_registry()):
        declared = set(taxonomy_categories(domain_id))
        try:
            primary = primary_effect_categories(domain_id)
        except ValueError as exc:
            errors.append(f"domain {domain_id!r}: ADOPT gate misconfigured: {exc}")
            continue
        for category in primary:
            if category not in declared:
                errors.append(
                    f"domain {domain_id!r}: ADOPT gate names undeclared category "
                    + repr(category))

    # Every V2 outcome bucket must be a category some domain declares.
    v2_outcome = ROOT / "schemas" / "v2" / "outcome.schema.json"
    if v2_outcome.is_file():
        v2_schema = json.loads(v2_outcome.read_text(encoding="utf-8"))
        buckets = (v2_schema.get("properties", {})
                   .get("outcome_type", {}).get("enum"))
        if isinstance(buckets, list) and buckets:
            every = set()
            for domain_id in (d["id"] for d in list_domains_from_registry()):
                every.update(taxonomy_categories(domain_id))
            orphan = sorted(set(buckets) - every)
            # Reverse direction too: a category a domain declares but the V2
            # contract omits would reject that domain's outcomes at the graph
            # layer, which is exactly how policy was blocked.
            missing_bucket = sorted(every - set(buckets))
            if missing_bucket:
                errors.append(
                    "schemas/v2/outcome.schema.json is missing category bucket(s) "
                    "that domains declare: " + repr(missing_bucket))
            if orphan:
                errors.append(
                    "schemas/v2/outcome.schema.json declares bucket(s) no domain "
                    "registers: " + repr(orphan))

    # ---------------------------------------------------------------- versions
    for relative in ("packaging/scp-manifest.json",):
        path = ROOT / relative
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        declared = (data.get("skill") or {}).get("version")
        if declared != ENGINE_VERSION:
            errors.append(f"{relative}: skill.version {declared!r} != ENGINE_VERSION {ENGINE_VERSION!r}")
    start_here = ROOT / "packaging" / "START-HERE.md"
    if start_here.is_file():
        text = start_here.read_text(encoding="utf-8")
        major_minor = ".".join(ENGINE_VERSION.split(".")[:2])
        if f"EduEvidence {major_minor}" not in text:
            errors.append(f"packaging/START-HERE.md does not state EduEvidence {major_minor}")

    # ------------------------------------------------------- docs must not drift
    for doc in ("docs/architecture.md", "README.zh-CN.md", "docs/install-guide.md"):
        path = ROOT / doc
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for stale in ("752 个测试", "752 tests"):
            if stale in text:
                errors.append(f"{doc}: stale test count {stale!r}; use docs/metrics.json")

    return errors


def main() -> int:
    print("[*] Checking protocol alignment across workflows, roles, capabilities and packaging...")
    errors = check()
    if errors:
        print(f"[-] Protocol alignment FAILED with {len(errors)} error(s):", file=sys.stderr)
        for error in errors:
            print(f"    • {error}", file=sys.stderr)
        return 1
    print("[+] Protocol alignment PASSED: stages, briefs, roles, prompts, capabilities, "
          "sub-skills, workflows and packaging agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
