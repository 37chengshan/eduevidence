#!/usr/bin/env python3
"""orchestrator.py — Run Orchestrator (Phase 11) + Resume (Phase 32) + Failure Matrix (Phase 33).

The orchestrator owns the RUN mechanics only — stage routing, workspace state,
schema gates, resource routing, execution backend selection, artifacts and
failure handling. It never performs domain reasoning (framing, retrieval,
extraction, skepticism, audit or intervention design are external-agent
stages); the two deterministic stages it executes locally are:

  adjudicate  — Pre-Verdict Gate (scripts/pre_verdict_gate.py) + deterministic
                confidence (scripts/compute_confidence.py) producing
                final_verdict.json from raw_verdict.json + evidence.jsonl
  present     — assemble result.json from the workspace artifacts
                (decision = final_verdict.json; claims carry claim_id per
                report-result.schema.json)

Stage machine (execution_plan.json / state.json):

  frame -> retrieve -> extract -> challenge -> audit -> adjudicate
       -> intervene -> evaluate -> present

Each stage writes exactly one primary artifact and is schema-gated against
schemas/*. When the artifact is missing the orchestrator either seeds it from
a demo pack (--demo-pack, tests/demo mode) or leaves a task brief for an
external agent and marks the stage pending. Resume (Phase 32) continues from
the first non-completed stage using state.json; failures are mapped through
the FAILURE_MATRIX (Phase 33).

CLI (entry points `eduevidence` via eduevidence_cli.py, or directly):

    python scripts/orchestrator.py run --question "..." --depth deep
    python scripts/orchestrator.py run --question "..." --demo-pack examples/ai-coding-assistant
    python scripts/orchestrator.py resume --run-id 20260812-103000
    python scripts/orchestrator.py status --run-id 20260812-103000
    python scripts/orchestrator.py list
    python scripts/orchestrator.py gate --run-id 20260812-103000
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_workspace import (RESOURCE_POLICY_VERSION, STAGES, RunWorkspace,  # noqa: E402
                           load_json, load_jsonl, next_run_id, save_jsonl)
from pre_verdict_gate import apply_enforcement, evaluate_workspace  # noqa: E402

DEPTH_ALIASES = {"quick": "S", "standard": "M", "deep": "L"}
DEPTHS = ("S", "M", "L")

#: Stage -> primary artifact + schema gate + whether it is locally executable.
STAGE_SPEC: dict[str, dict[str, Any]] = {
    "frame":     {"artifact": "frame.json",       "schema": "education-frame.schema.json", "jsonl": False, "local": False},
    "retrieve":  {"artifact": "sources.jsonl",    "schema": "source.schema.json",          "jsonl": True,  "local": False},
    "extract":   {"artifact": "evidence.jsonl",   "schema": "evidence.schema.json",        "jsonl": True,  "local": False},
    "challenge": {"artifact": "skeptic.json",     "schema": None,                          "jsonl": False, "local": False},
    "audit":     {"artifact": "methodology.json", "schema": "methodology.schema.json",     "jsonl": False, "local": False},
    "adjudicate": {"artifact": "final_verdict.json", "schema": "verdict.schema.json",      "jsonl": False, "local": True},
    "intervene": {"artifact": "intervention.json", "schema": "intervention.schema.json",   "jsonl": False, "local": False},
    "evaluate":  {"artifact": "evaluation.json",  "schema": "evaluation.schema.json",      "jsonl": False, "local": False},
    "present":   {"artifact": "result.json",      "schema": "report-result.schema.json",   "jsonl": False, "local": True},
}

#: Phase 33 — canonical failure -> handling-action mapping. Extends the
#: retrieval-layer taxonomy (retrieval/failures.py) with orchestration states.
FAILURE_MATRIX: dict[str, dict[str, Any]] = {
    "TOOL_FAILURE": {"action": "retry_with_fallback_tool", "retry": True,
                     "note": "a tool invocation failed; retry with an alternate tool before aborting"},
    "SCHEMA_INVALID": {"action": "block_stage_advance_and_fix_artifact", "retry": False,
                       "note": "stage artifact violates its schema gate; regenerate or repair the artifact"},
    "STAGE_ARTIFACT_MISSING": {"action": "write_brief_and_mark_pending", "retry": False,
                               "note": "stage waits for an external agent; resume continues when the artifact appears"},
    "GATE_CRITICAL_FAILURE": {"action": "cap_confidence_and_force_pilot_or_insufficient", "retry": False,
                              "note": "Pre-Verdict Gate critical failures forbid high confidence; verdict is capped"},
    "SEARCH_NO_RESULT": {"action": "rerun_search_with_broader_terms", "retry": True,
                         "note": "no results for the query; broaden terms or switch discovery provider"},
    "SEARCH_LOW_QUALITY": {"action": "widen_query_or_accept_lower_authority_tier", "retry": True,
                           "note": "results are low quality; widen the query or accept a lower authority tier"},
    "FETCH_FAILED": {"action": "alternate_fetch_provider_then_alternate_source", "retry": True,
                     "note": "degradation chain exhausted; do not retry the same URL, return to Discovery"},
    "FETCH_PARTIAL": {"action": "rule_confirm_or_human_confirm_before_extraction", "retry": False,
                      "note": "content partially readable; require rule/human confirmation before extraction"},
    "SOURCE_INVALID": {"action": "discard_and_find_alternate_source", "retry": False,
                       "note": "source does not validate; discard and find an alternate source"},
    "SOURCE_DUPLICATE": {"action": "merge_keep_highest_authority", "retry": False,
                         "note": "same paper behind mirror URLs; merge and keep the highest-authority entry"},
    "UNSUPPORTED_CLAIM": {"action": "downgrade_claim_or_drop", "retry": False,
                          "note": "claim cannot be bound to a verifiable source; downgrade or drop"},
    "CONFLICT_UNRESOLVED": {"action": "stay_uncertain_do_not_force_adjudication", "retry": False,
                            "note": "conflicting evidence without resolution; remain uncertain"},
    "SCOPE_MISMATCH": {"action": "shrink_conclusion_scope", "retry": False,
                       "note": "conclusion scope exceeds evidence scope; shrink the conclusion"},
    "METHODOLOGY_TOO_WEAK": {"action": "do_not_use_as_support", "retry": False,
                             "note": "methodology audit fails; the study cannot support claims"},
    "INSUFFICIENT_EVIDENCE": {"action": "mark_insufficient_evidence", "retry": False,
                              "note": "evidence base is too thin; output INSUFFICIENT EVIDENCE"},
    "AGENT_MCP_UNAVAILABLE": {"action": "degrade_to_platform_native_mode", "retry": False,
                              "note": "agent-mcp not reachable; fall back to Mode A semantics"},
    "REPORT_INVALID": {"action": "block_publish_rerun_render", "retry": True,
                       "note": "rendered report fails validation; block publishing and rerun the render"},
    "DEMO_PACK_MISSING": {"action": "write_brief_and_mark_pending", "retry": False,
                          "note": "requested demo seed not in the demo pack; treat as a normal pending stage"},
    # -- states documented in docs/failure-matrix.md (Phase 33), kept as aliases
    #    so the code matrix is a superset of the documented failure taxonomy.
    "INSUFFICIENT_SOURCES": {"action": "supplement_search_or_mark_insufficient", "retry": True,
                             "note": "too few/direct/strong sources to support a conclusion; supplement search or output INSUFFICIENT"},
    "NEEDS_USER_CONTEXT": {"action": "request_user_context_before_continuing", "retry": False,
                           "note": "minimal learner/course/intervention/outcome inputs missing; ask the user, never guess defaults"},
    "AGENT_MCP_APPROVAL_REQUIRED": {"action": "do_not_spawn_confirm_model_table_first", "retry": False,
                                    "note": "agent-mcp installed but model table not user-confirmed; no spawn until approved"},
    "PRE_VERDICT_FAILED": {"action": "fix_pre_verdict_artifacts_rerun_gate", "retry": True,
                           "note": "pre-verdict prerequisites failed (verdict schema / cross-model review / methodology); fix and re-run the gate"},
}

_STAGE_BRIEFS: dict[str, str] = {
    "frame": ("Structure the raw education question into an Education Research Frame "
              "(learner/course/intervention/comparison/outcomes/context/scope). "
              "Write frame.json."),
    "retrieve": ("Search for candidate sources within the frame scope; record Source Objects "
                 "(source_id, title, canonical_url, authority_level) in sources.jsonl "
                 "(one JSON object per line) and store fetched content under fetch/."),
    "extract": ("Extract claim-level Evidence Objects from the retrieved sources "
                "(evidence_id, source_id, claim, outcome_type, direction, source_location) "
                "into evidence.jsonl."),
    "challenge": ("Act as the Skeptic: actively search for counter-evidence, null results and "
                  "confounders; write skeptic.json with search_performed=true and the findings."),
    "audit": ("Method-review every study: methodology.json with audit_items, "
              "task_vs_learning_guard and a PASS/CONCERN/FAIL verdict."),
    "adjudicate": ("Judge the evidence: write raw_verdict.json (model verdict). The orchestrator "
                   "then runs the Pre-Verdict Gate and deterministic confidence to produce "
                   "final_verdict.json."),
    "intervene": ("Design the minimal verifiable teaching intervention (phased pilot, "
                  "stop conditions, evidence alignment); write intervention.json."),
    "evaluate": ("Design the evaluation plan (baseline/post/retention/transfer, task vs learning "
                 "separation); write evaluation.json."),
    "present": ("Translate result.json into result.zh.json and render report_spec.json / "
                "report.html via the visualization layer."),
}


def _utc_now() -> str:
    from run_workspace import utc_now
    return utc_now()


def handle_failure(token: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Phase 33 failure routing: canonical token -> handling action."""
    entry = FAILURE_MATRIX.get(token)
    if entry is None:
        raise ValueError(f"unknown failure state {token!r}; known: {sorted(FAILURE_MATRIX)}")
    plan = {"state": token, **entry}
    if context:
        plan["context"] = context
    return plan


# ---------------------------------------------------------- workspace plans


def init_run(
    runs_dir: Path,
    question: str,
    *,
    depth: str = "M",
    run_id: str | None = None,
    approve_agent_mcp: bool = False,
    scp_available: bool | None = None,
) -> RunWorkspace:
    """Create the run workspace + manifest + planning artifacts (Phase 11-13)."""
    depth = DEPTH_ALIASES.get(depth, depth)
    if depth not in DEPTHS:
        raise ValueError(f"unknown depth {depth!r}; use quick/standard/deep or S/M/L")

    try:
        from integrations.agent_mcp import detect_agent_mcp
        detection = detect_agent_mcp()
        agent_mode = detection["mode"]
        agent_available = detection["available"]
    except Exception:
        agent_mode, agent_available = "platform_native", False

    from run_workspace import build_manifest

    if run_id is None:
        run_id = next_run_id(runs_dir)
    ws = RunWorkspace(runs_dir, run_id)
    ws.create()

    manifest = build_manifest(
        run_id, question,
        execution_mode=agent_mode,
        agent_mcp_available=agent_available,
        agent_mcp_approved=approve_agent_mcp,
        root=ROOT,
    )
    ws.save_manifest(manifest)

    state = ws.load_state()
    state.update({"run_id": run_id, "question": question, "depth": depth,
                  "status": "running", "current_stage": STAGES[0]})
    ws.save_state(state)

    # -- planning artifacts ------------------------------------------------
    capability_plan = {
        "run_id": run_id,
        "depth": depth,
        "required_capabilities": [
            "education_framing", "evidence_retrieval", "evidence_extraction",
            "skeptic_review", "methodology_audit", "adjudication",
            "intervention_design", "evaluation_design", "bilingual_reporting"],
        "local_capabilities": {
            "schema_validation": True, "deterministic_confidence": True,
            "claim_audit": True, "evidence_matrix": True,
            "pre_verdict_gate": True, "result_assembly": True,
            "complexity_gate": True},
        "external_capabilities": {
            "web_fetch": True, "smart_web_fetch": True, "search": True,
            "agent_mcp_dispatch": agent_available},
    }
    resource_plan = {
        "run_id": run_id,
        "execution_mode": agent_mode,
        "resource_policy_version": RESOURCE_POLICY_VERSION,
        "token_budget_per_stage": {
            "frame": 4000, "retrieve": 8000, "extract": 12000, "challenge": 8000,
            "audit": 8000, "adjudicate": 8000, "intervene": 6000,
            "evaluate": 6000, "present": 6000},
        "max_concurrent_agents": {"S": 0, "M": 2, "L": 4}[depth],
        "timeouts_s": {"fetch": 20, "agent": 1800},
    }
    execution_plan = {
        "run_id": run_id,
        "depth": depth,
        "stages": [
            {"name": s, "status": "pending",
             "artifact": STAGE_SPEC[s]["artifact"],
             "schema": STAGE_SPEC[s]["schema"],
             "mode": "local" if STAGE_SPEC[s]["local"] else "external"}
            for s in STAGES],
    }
    model_inventory = {
        "run_id": run_id,
        "execution_mode": agent_mode,
        "routing": {
            "education-planner": "strong/reasoning",
            "evidence-retriever": "fast/low-cost",
            "evidence-analyst": "strong/structured",
            "skeptic": "independent/reasoning",
            "method-reviewer": "strong/reasoning",
            "evidence-judge": "strong/reasoning",
            "intervention-designer": "strong/reasoning",
            "evaluation-designer": "strong/reasoning"} if agent_available else {},
        "agents": {},
    }
    agent_mcp_approval = {
        "run_id": run_id,
        "agent_mcp_available": agent_available,
        "approved": approve_agent_mcp,
        "approved_at": _utc_now() if approve_agent_mcp else None,
        "mode": agent_mode,
        "reason": ("user-approved via --approve-agent-mcp"
                   if approve_agent_mcp else "not yet approved; runs in platform-native mode"),
    }

    for name, data in (("capability_plan", capability_plan),
                       ("resource_plan", resource_plan),
                       ("execution_plan", execution_plan),
                       ("model_inventory", model_inventory),
                       ("agent_mcp_approval", agent_mcp_approval)):
        (ws.path / f"{name}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ws.trace("run_initialized", detail=f"depth={depth} mode={agent_mode} question={question[:120]}")
    return ws


# ------------------------------------------------------------- schema gates


def _load_artifact(ws: RunWorkspace, artifact: str) -> list[dict[str, Any]]:
    path = ws.path / artifact
    if not path.is_file():
        return []
    if artifact.endswith(".jsonl"):
        return load_jsonl(path)
    data = load_json(path)
    return [data] if data else []


def schema_gate(ws: RunWorkspace, stage: str) -> dict[str, Any]:
    """Validate a stage's primary artifact against its schema. Never raises."""
    spec = STAGE_SPEC[stage]
    artifact = spec["artifact"]
    schema_name = spec["schema"]
    if schema_name is None:  # challenge: light parseability contract
        data = load_json(ws.path / artifact)
        ok = bool(data) and isinstance(data, dict)
        return {"passed": ok, "stage": stage, "artifact": artifact,
                "schema": None, "issues": [] if ok else ["skeptic.json missing or unparseable"]}

    from validate_schema import SchemaError, Validator

    schemas_dir = ROOT / "schemas"
    if not (schemas_dir / schema_name).is_file():
        share_dir = Path(sys.prefix) / "share" / "eduevidence" / "schemas"
        if (share_dir / schema_name).is_file():
            schemas_dir = share_dir

    try:
        schema = json.loads((schemas_dir / schema_name).read_text(encoding="utf-8"))
    except OSError:
        return {"passed": False, "stage": stage, "artifact": artifact,
                "schema": schema_name, "issues": [f"schema file {schema_name} not found"]}

    records = _load_artifact(ws, artifact)
    if not records:
        return {"passed": False, "stage": stage, "artifact": artifact,
                "schema": schema_name, "issues": [f"{artifact} missing or empty"]}

    issues = []
    validator = Validator(schema, base_dir=schemas_dir)


    for idx, record in enumerate(records):
        try:
            validator.validate(record, schema, f"{artifact}[{idx}]")
        except SchemaError as exc:
            issues.append(str(exc))
    return {"passed": not issues, "stage": stage, "artifact": artifact,
            "schema": schema_name, "issues": issues[:5]}


# ------------------------------------------------------- deterministic stages


def derive_sources_from_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic source registry derived from evidence records (demo/test mode)."""
    from retrieval.source import make_source

    seen: dict[str, dict[str, Any]] = {}
    for ev in evidence:
        sid = ev.get("source_id", "")
        if not sid or sid in seen:
            continue
        loc = ev.get("source_location", "") or ""
        authority = ("tier1_paper_doi" if loc.startswith(("https://doi.org", "http://doi.org"))
                     else "tier3_professional_institution")
        seen[sid] = make_source(
            source_id=sid,
            title=ev.get("title", sid),
            canonical_url=loc or f"https://doi.org/{sid}",
            authority_level=authority,
            year=ev.get("year"),
        )
        if not seen[sid].get("fetch"):
            # fetchProvenance requires fetch_status; an empty dict is schema-invalid
            seen[sid].pop("fetch", None)
    return list(seen.values())


def derive_skeptic_from_evidence(evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic skeptic summary derived from evidence directions (demo/test mode).

    Records what the corpus itself contains (contradictions / null results /
    confounders); it never invents counter-evidence.
    """
    contradictions = [e.get("evidence_id") for e in evidence if e.get("direction") == "contradict"]
    null_results = [e.get("evidence_id") for e in evidence if e.get("direction") == "neutral"]
    confounders = sorted({c for e in evidence for c in (e.get("confounders", []) or [])})
    return {
        "search_performed": True,
        "method": "derived from evidence corpus directions (demo/test mode)",
        "contradictions": contradictions,
        "null_results": null_results,
        "confounders": confounders,
        "no_contradictory_evidence_found": not contradictions,
    }


def _cap_verdict(gate: dict[str, Any], raw_verdict: dict[str, Any],
                 computed: dict[str, Any]) -> dict[str, Any]:
    """Build final_verdict.json: deterministic confidence + gate enforcement."""
    final = copy.deepcopy(raw_verdict)
    final["raw_model_confidence"] = raw_verdict.get("confidence")
    final["raw_model_confidence_breakdown"] = raw_verdict.get("confidence_breakdown")
    final["confidence"] = computed["confidence"]
    final["confidence_score"] = computed["confidence_breakdown"].get("score")
    final["confidence_policy_version"] = computed["confidence_policy_version"]
    final["independent_studies"] = computed["independent_studies"]
    final["independent_samples"] = computed["independent_samples"]
    final["confidence_breakdown"] = computed["confidence_breakdown"]
    return apply_enforcement(final, gate)


def _run_adjudicate(ws: RunWorkspace, question: str,
                    demo_pack: Path | None = None) -> dict[str, Any]:
    """Local adjudicate: Pre-Verdict Gate + deterministic confidence."""
    from compute_confidence import compute_confidence

    raw_path = ws.path / "raw_verdict.json"
    raw = load_json(raw_path)
    if not raw and demo_pack is not None and Path(demo_pack).is_dir():
        pack_verdict = Path(demo_pack) / "verdict.json"
        if pack_verdict.is_file():
            raw_path.write_bytes(pack_verdict.read_bytes())
            raw = load_json(raw_path)
            ws.trace("demo_seeded", stage="adjudicate",
                     detail="raw_verdict.json seeded from demo pack verdict.json")
    evidence = load_jsonl(ws.path / "evidence.jsonl")
    if not raw:
        ws.write_brief("adjudicate", question, _STAGE_BRIEFS["adjudicate"])
        return {"status": "pending", "detail": "raw_verdict.json missing; brief written for evidence judge"}
    if not evidence:
        ws.write_brief("adjudicate", question, _STAGE_BRIEFS["adjudicate"])
        return {"status": "pending", "detail": "evidence.jsonl empty; extraction must complete first"}

    pre = evaluate_workspace(ws.path, require_final=False)
    computed = compute_confidence(evidence)
    final = _cap_verdict(pre, raw, computed)
    (ws.path / "final_verdict.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    post = evaluate_workspace(ws.path, require_final=True)
    gate_report = {"run_id": ws.run_id, "stage": "adjudicate",
                   "pre": {"passed": pre["passed"], "max_confidence": pre["max_confidence"],
                           "critical_failures": pre["critical_failures"]},
                   "post": post,
                   "final_confidence": final.get("confidence"),
                   "final_action": final.get("recommended_action"),
                   "checked_at": _utc_now()}
    (ws.path / "gate_report.json").write_text(
        json.dumps(gate_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if post["passed"]:
        detail = (f"gate passed; confidence={final.get('confidence')} "
                  f"(policy={final.get('confidence_policy_version')})")
        ws.trace("adjudicate_completed", stage="adjudicate", detail=detail)
        return {"status": "completed", "detail": detail}
    ws.trace("gate_failure_capped", stage="adjudicate",
             detail=f"critical failures: {post['critical_failures']}; confidence capped at "
                    f"{post['max_confidence']}")
    return {"status": "completed",
            "detail": f"gate critical failures {post['critical_failures']}; verdict capped at "
                      f"{post['max_confidence']}"}


def _assemble_result(ws: RunWorkspace, manifest: dict[str, Any]) -> dict[str, Any]:
    """Assemble result.json from workspace artifacts (decision=final_verdict.json)."""
    from build_result import (NOT_CAPTURED_USAGE, OUTCOME_ORDER,
                              aggregate_outcomes, build_claims, derive_provenance)

    frame = load_json(ws.path / "frame.json")
    evidence = load_jsonl(ws.path / "evidence.jsonl")
    verdict = load_json(ws.path / "final_verdict.json") or load_json(ws.path / "raw_verdict.json")
    methodology = load_json(ws.path / "methodology.json")
    methodology_list = [methodology] if methodology else []
    intervention = load_json(ws.path / "intervention.json")
    evaluation = load_json(ws.path / "evaluation.json")
    sources = load_jsonl(ws.path / "sources.jsonl")
    if not sources:
        sources = derive_sources_from_evidence(evidence)

    claims = build_claims(evidence)
    for idx, claim in enumerate(claims, 1):
        claim["claim_id"] = f"C-{idx:03d}"

    mode = manifest.get("execution_mode", "platform_native")
    return {
        "meta": {
            "skill": "eduevidence",
            "version": manifest.get("skill_version", "1.0.0"),
            "generated_at": _utc_now(),
            "mode": mode,
            "question": frame.get("question", manifest.get("question", "")),
        },
        "execution": {
            "complexity": frame.get("complexity") or manifest.get("depth", "M"),
            "mode": mode,
            "agents": [],
            "usage": dict(NOT_CAPTURED_USAGE),
        },
        "research_frame": frame,
        "decision": verdict,
        "outcomes": aggregate_outcomes(evidence),
        "claims": claims,
        "sources": sources,
        "evidence": evidence,
        "methodology_reviews": methodology_list,
        "conflicts": [{"reason_for_disagreement": verdict.get("reason_for_disagreement", "")}]
        if verdict.get("reason_for_disagreement") else [],
        "applicability": verdict.get("applicability", {}),
        "intervention": intervention,
        "evaluation": evaluation,
        "benchmark": {},
        "provenance": derive_provenance(sources),
    }


def _run_present(ws: RunWorkspace, manifest: dict[str, Any], question: str,
                 demo_pack: Path | None = None) -> dict[str, Any]:
    """Local present: assemble + validate result.json, seed render artifacts."""
    required = ("final_verdict.json", "intervention.json", "evaluation.json")
    missing = [name for name in required if not (ws.path / name).is_file()
               or not load_json(ws.path / name)]
    if missing:
        ws.write_brief("present", question, _STAGE_BRIEFS["present"])
        return {"status": "pending",
                "detail": f"missing prerequisite artifacts: {', '.join(missing)}"}

    # demo/test mode: seed the bilingual + render artifacts from the example pack
    seeded = []
    if demo_pack is not None and Path(demo_pack).is_dir():
        pack = Path(demo_pack)
        for name in ("result.zh.json", "report_spec.json"):
            target = ws.path / name
            if (pack / name).is_file() and (not target.is_file() or target.stat().st_size <= 2):
                target.write_bytes((pack / name).read_bytes())
                seeded.append(name)
        if not (ws.path / "report.html").is_file() or (ws.path / "report.html").stat().st_size <= 2:
            for name in ("EduEvidence_Report.html", "report.html"):
                if (pack / name).is_file():
                    (ws.path / "report.html").write_bytes((pack / name).read_bytes())
                    seeded.append(name)
                    break

    result = _assemble_result(ws, manifest)
    (ws.path / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gate = schema_gate(ws, "present")
    if not gate["passed"]:
        return {"status": "failed", "detail": f"result.json schema gate: {gate['issues']}"}
    missing_render = [n for n in ("result.zh.json", "report_spec.json", "report.html")
                      if not (ws.path / n).is_file() or (ws.path / n).stat().st_size <= 2]
    if seeded:
        extras = f"seeded render artifacts: {', '.join(seeded)}"
    elif missing_render:
        extras = f"render artifacts missing: {', '.join(missing_render)}"
    else:
        extras = "render artifacts present"
    return {"status": "completed",
            "detail": (f"result.json assembled (sources={len(result['sources'])}, "
                       f"evidence={len(result['evidence'])}, claims={len(result['claims'])}); "
                       f"{extras}")}


# ------------------------------------------------------------- stage runner


def run_stage(ws: RunWorkspace, stage: str, *, demo_pack: Path | None = None) -> dict[str, Any]:
    """Advance one stage. Returns {status: completed|pending|failed, detail}.

    Deterministic stages execute locally; external stages are either seeded
    from ``demo_pack`` (demo/test mode) or handed off via a task brief.
    """
    ws.trace("stage_started", stage=stage)
    spec = STAGE_SPEC[stage]
    question = ws.load_manifest().get("question", "")
    artifact_path = ws.path / spec["artifact"]

    # already-present artifact -> schema gate only (empty seeds count as missing)
    if artifact_path.is_file() and artifact_path.stat().st_size > 2:
        gate = schema_gate(ws, stage)
        if gate["passed"]:
            ws.mark_stage(stage, "completed",
                          detail=f"artifact {spec['artifact']} schema-valid",
                          artifacts=[spec["artifact"]])
            ws.trace("stage_completed", stage=stage, detail="schema gate passed")
            return {"status": "completed", "detail": "artifact present, schema-valid"}
        ws.trace("schema_invalid", stage=stage, detail=gate["issues"][0])
        ws.mark_stage(stage, "failed", detail=f"schema gate failed: {gate['issues'][0]}")
        return {"status": "failed", "detail": f"schema gate failed: {gate['issues']}"}

    # local deterministic stages
    if stage == "adjudicate":
        result = _run_adjudicate(ws, question, demo_pack=demo_pack)
    elif stage == "present":
        result = _run_present(ws, ws.load_manifest(), question, demo_pack=demo_pack)
    else:
        # demo/test seeding
        if demo_pack is not None:
            seeded = _seed_from_demo(ws, stage, demo_pack)
            if seeded["seeded"]:
                gate = schema_gate(ws, stage)
                if gate["passed"]:
                    ws.mark_stage(stage, "completed",
                                  detail=f"demo-seeded from {demo_pack.name}; schema-valid",
                                  artifacts=[spec["artifact"]])
                    ws.trace("stage_completed", stage=stage, detail="demo seed, schema gate passed")
                    return {"status": "completed", "detail": seeded["detail"]}
                ws.mark_stage(stage, "failed", detail=f"demo seed failed schema gate: {gate['issues']}")
                return {"status": "failed", "detail": f"demo seed failed schema gate: {gate['issues']}"}
            if seeded["reason"]:
                return {"status": "pending", "detail": seeded["reason"]}

        ws.write_brief(stage, question, _STAGE_BRIEFS[stage])
        ws.mark_stage(stage, "pending",
                      detail=f"awaiting external agent; brief at task-briefs/{stage}.md")
        return {"status": "pending",
                "detail": f"external stage; brief written to task-briefs/{stage}.md"}

    if result["status"] == "completed":
        ws.mark_stage(stage, "completed", detail=result["detail"],
                      artifacts=[spec["artifact"]])
    elif result["status"] == "failed":
        ws.mark_stage(stage, "failed", detail=result["detail"])
    else:
        ws.mark_stage(stage, "pending", detail=result["detail"])
    return result


def _seed_from_demo(ws: RunWorkspace, stage: str, demo_pack: Path) -> dict[str, Any]:
    """Copy/derive the stage artifact from a demo pack (tests + --demo-pack)."""
    pack = Path(demo_pack)
    if not pack.is_dir():
        return {"seeded": False, "reason": f"demo pack {demo_pack} not found"}
    evidence = load_jsonl(pack / "evidence.jsonl")

    if stage == "frame":
        if (pack / "frame.json").is_file():
            (ws.path / "frame.json").write_bytes((pack / "frame.json").read_bytes())
            return {"seeded": True, "detail": "frame.json seeded from demo pack"}
    elif stage == "retrieve":
        if (pack / "sources.jsonl").is_file():
            (ws.path / "sources.jsonl").write_bytes((pack / "sources.jsonl").read_bytes())
        elif evidence:
            save_jsonl(ws.path / "sources.jsonl", derive_sources_from_evidence(evidence))
        else:
            return {"seeded": False, "reason": "demo pack has no sources/evidence to derive from"}
        return {"seeded": True, "detail": "sources.jsonl seeded from demo pack"}
    elif stage == "extract":
        if not evidence:
            return {"seeded": False, "reason": "demo pack has no evidence.jsonl"}
        (ws.path / "evidence.jsonl").write_bytes((pack / "evidence.jsonl").read_bytes())
        return {"seeded": True, "detail": "evidence.jsonl seeded from demo pack"}
    elif stage == "challenge":
        (ws.path / "skeptic.json").write_text(
            json.dumps(derive_skeptic_from_evidence(evidence), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return {"seeded": True, "detail": "skeptic.json derived from evidence (demo)"}
    elif stage == "audit":
        if (pack / "methodology.json").is_file():
            (ws.path / "methodology.json").write_bytes((pack / "methodology.json").read_bytes())
            return {"seeded": True, "detail": "methodology.json seeded from demo pack"}
    elif stage == "intervene":
        if (pack / "intervention.json").is_file():
            (ws.path / "intervention.json").write_bytes((pack / "intervention.json").read_bytes())
            return {"seeded": True, "detail": "intervention.json seeded from demo pack"}
    elif stage == "evaluate":
        if (pack / "evaluation.json").is_file():
            (ws.path / "evaluation.json").write_bytes((pack / "evaluation.json").read_bytes())
            return {"seeded": True, "detail": "evaluation.json seeded from demo pack"}
    return {"seeded": False, "reason": f"demo pack has no artifact for stage {stage}"}


def advance(ws: RunWorkspace, *, demo_pack: Path | None = None) -> dict[str, Any]:
    """Resume loop: advance stages in order until blocked (Phase 32).

    Completed stages are skipped; pending/failed stages stop the pass so an
    external agent can act, then ``resume`` continues.
    """
    summary = {"run_id": ws.run_id, "advanced": [], "blocked_on": None,
               "failures": [], "completed_all": False}
    state = ws.load_state()
    for stage in STAGES:
        status = state["stages"].get(stage, {}).get("status", "pending")
        if status == "completed":
            # crash/interruption safety: a completed stage whose primary artifact
            # vanished (or was truncated to an empty seed) must re-run.
            artifact = STAGE_SPEC[stage]["artifact"]
            path = ws.path / artifact
            if path.is_file() and path.stat().st_size > 2:
                continue
            ws.mark_stage(stage, "pending",
                          detail="artifact missing on resume; stage will re-run")
            status = "pending"
        result = run_stage(ws, stage, demo_pack=demo_pack)
        summary["advanced"].append({"stage": stage, **result})
        if result["status"] == "pending":
            summary["blocked_on"] = stage
            break
        if result["status"] == "failed":
            plan = handle_failure("SCHEMA_INVALID" if "schema" in result["detail"] else "TOOL_FAILURE")
            summary["failures"].append({"stage": stage, "detail": result["detail"],
                                        "handling": plan["action"]})
            ws.trace("stage_failed", stage=stage, detail=result["detail"])
            summary["blocked_on"] = stage
            break
        state = ws.load_state()  # refresh after stage writes

    state = ws.load_state()
    remaining = [s for s in STAGES if state["stages"].get(s, {}).get("status") != "completed"]
    if not remaining:
        state = ws.save_state({"status": "completed", "current_stage": STAGES[-1]})
        summary["completed_all"] = True
        ws.trace("run_completed", detail="all stages completed")
    else:
        run_status = "failed" if summary["failures"] else "running"
        state = ws.save_state({"status": run_status, "current_stage": remaining[0]})
        summary["blocked_on"] = summary.get("blocked_on") or remaining[0]
    summary["current_stage"] = state["current_stage"]
    summary["status"] = state["status"]
    return summary


# ---------------------------------------------------------------------- CLI


def _print_status(ws: RunWorkspace) -> None:
    state = ws.load_state()
    print(f"run_id: {ws.run_id}")
    print(f"question: {state.get('question', '')[:120]}")
    print(f"status: {state.get('status')}  current_stage: {state.get('current_stage')}")
    print("stages:")
    for stage in STAGES:
        row = state["stages"].get(stage, {})
        detail = row.get("detail", "")
        print(f"  {stage:12} {row.get('status', 'pending'):10} {detail}")


def _cmd_run(args: argparse.Namespace) -> int:
    ws = init_run(Path(args.runs_dir), args.question, depth=args.depth, run_id=args.run_id,
                  approve_agent_mcp=args.approve_agent_mcp)
    print(f"workspace created: {ws.path}")
    print(f"manifest: {json.dumps(ws.load_manifest(), ensure_ascii=False, indent=2)}")
    if args.dry_run:
        print("[dry-run] workspace initialized; stage execution skipped")
        return 0
    summary = advance(ws, demo_pack=args.demo_pack)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["failures"]:
        return 1
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    ws = RunWorkspace(Path(args.runs_dir), args.run_id)
    if not ws.exists():
        print(f"ERROR: no run {args.run_id} under {args.runs_dir}", file=sys.stderr)
        return 2
    summary = advance(ws, demo_pack=args.demo_pack)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["failures"] else 0


def _cmd_status(args: argparse.Namespace) -> int:
    ws = RunWorkspace(Path(args.runs_dir), args.run_id)
    if not ws.exists():
        print(f"ERROR: no run {args.run_id} under {args.runs_dir}", file=sys.stderr)
        return 2
    _print_status(ws)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    runs_dir = Path(args.runs_dir)
    if not runs_dir.is_dir():
        print("no runs yet")
        return 0
    for entry in sorted(runs_dir.iterdir()):
        if not entry.is_dir():
            continue
        ws = RunWorkspace(runs_dir, entry.name)
        if not ws.exists():
            continue
        state = ws.load_state()
        print(f"{entry.name:24} {state.get('status', '?'):10} {state.get('question', '')[:80]}")
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    ws = RunWorkspace(Path(args.runs_dir), args.run_id)
    if not ws.exists():
        print(f"ERROR: no run {args.run_id} under {args.runs_dir}", file=sys.stderr)
        return 2
    return main_gate(argv=["--workspace", str(ws.path),
                           *(["--require-final"] if args.require_final else []),
                           "--json"])


def main_gate(argv: list[str] | None = None) -> int:
    """Re-export of the Pre-Verdict Gate CLI (used by `eduevidence gate`)."""
    from pre_verdict_gate import main as gate_main
    return gate_main(argv)


# ---- V2 command handlers --------------------------------------------------

def _home(args) -> "object":
    from engine.paths import resolve_home
    return resolve_home(getattr(args, "home", None))


def _cmd_project(args) -> int:
    from engine.project import ProjectWorkspace
    home = _home(args)
    if args.action == "create":
        if not args.question:
            print("project create requires --question", file=sys.stderr)
            return 2
        ws = ProjectWorkspace.create(
            home, question=args.question, title=args.title or args.question,
            research_mode=args.mode)
        print(ws.project_id)
        return 0
    if args.action == "list":
        projects_dir = home / "projects"
        if not projects_dir.is_dir():
            return 0
        for p in sorted(projects_dir.iterdir()):
            manifest = p / "project.json"
            if manifest.is_file():
                import json
                m = json.loads(manifest.read_text(encoding="utf-8"))
                print(f"{m['project_id']}\t{m['status']}\trev {m['graph_revision']}\t{m['question'][:60]}")
        return 0
    # status
    ws = ProjectWorkspace.open(home, args.project)
    m = ws.manifest()
    print(f"project: {m['project_id']}")
    print(f"mode: {m['research_mode']}  target: {m['decision_target']}")
    print(f"status: {m['status']}  graph_revision: {m['graph_revision']}")
    return 0


def _cmd_research(args) -> int:
    from engine.mode_router import recommend_mode
    from engine.planner import build_research_plan
    from engine.project import ProjectWorkspace
    ws = ProjectWorkspace.open(_home(args), args.project)
    if args.action == "plan":
        intent = {
            "decision_target": ws.manifest()["decision_target"],
            "wants_existing_evidence": True,
            "wants_study_design": ws.manifest()["research_mode"] == "full_research_cycle",
            "has_user_data": False,
            "wants_data_analysis": False,
            "wants_decision_update": False,
        }
        rec = recommend_mode(intent, project_has_grounding=ws.current_revision() > 0)
        plan = build_research_plan(
            mode=rec.mode, decision_target=ws.manifest()["decision_target"],
            depth="standard", has_grounding=ws.current_revision() > 0,
            has_dataset=False)
        print(f"mode: {rec.mode}")
        for step in plan:
            print(f"  {step.kind:10s} {step.capability_id or step.wait_state}")
        return 0
    # run/resume: create a Run record
    from engine.run import start_run
    run = start_run(ws, purpose="research run", capabilities=[],
                    execution_backend="sequential_main_agent")
    print(run["run_id"])
    return 0


def _cmd_graph(args) -> int:
    from engine.graph_store import GraphStore
    from engine.project import ProjectWorkspace
    ws = ProjectWorkspace.open(_home(args), args.project)
    store = GraphStore.create(ws)
    problems = store.validate()
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        return 1
    print(f"graph valid at revision {store.active_revision()}")
    return 0


def _cmd_study(args) -> int:
    from engine.study_design import validate_design_grounding
    from engine.project import ProjectWorkspace
    from engine.ids import new_local_id
    ws = ProjectWorkspace.open(_home(args), args.project)
    question = getattr(args, "question", None) or "grounded study"
    design = {
        "design_id": new_local_id("DSN", set()),
        "gap_ids": args.gap,
        "research_question": question,
        "design_type": getattr(args, "design_type", "rct") or "rct",
        "population": getattr(args, "population", "") or "unspecified",
        "sampling_plan": getattr(args, "sampling", "") or "unspecified",
        "intervention": getattr(args, "intervention", None),
        "comparison": getattr(args, "comparison", None),
        "outcomes": [getattr(args, "outcome", "outcome")] if getattr(args, "outcome", None) else ["outcome"],
        "measures": [getattr(args, "measure", "measure")] if getattr(args, "measure", None) else ["measure"],
        "timepoints": ["post"],
        "assignment_strategy": getattr(args, "assignment", "") or "unspecified",
        "confounder_plan": "",
        "analysis_requirements": ["descriptive_statistics"],
        "success_criteria": [],
        "stop_conditions": [],
        "ethics_flags": {"human_subjects": True, "sensitive_data": False,
                         "minors_involved": False, "consent_status": "unknown",
                         "ethics_review_required": True,
                         "deidentification_required": False},
        "preregistration_fields": {},
        "derived_from_graph_revision": ws.current_revision(),
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "extensions": {},
    }
    errors = validate_design_grounding(ws, design)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    from engine.study_design import save_study_design
    path = save_study_design(ws, design)
    print(design["design_id"])
    return 0


def _cmd_data(args) -> int:
    from engine.datasets import ingest_dataset
    from engine.project import ProjectWorkspace
    ws = ProjectWorkspace.open(_home(args), args.project)
    asset = ingest_dataset(
        ws, design_id=args.design, source_path=args.file,
        privacy={"classification": args.privacy, "deidentification_status": "not_done",
                 "consent_metadata": None})
    print(asset["dataset_id"])
    return 0


def _cmd_analyze(args) -> int:
    from engine.analysis import run_native_descriptive
    from engine.project import ProjectWorkspace
    import json
    ws = ProjectWorkspace.open(_home(args), args.project)
    plan_path = ws.path / "analyses" / f"{args.plan}.json"
    if not plan_path.is_file():
        print(f"plan not found: {plan_path}", file=sys.stderr)
        return 1
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    run = run_native_descriptive(ws, plan)
    print(json.dumps(run, ensure_ascii=False, indent=2))
    return 0


def _cmd_adjudicate(args) -> int:
    from engine.graph_store import GraphStore
    from engine.project import ProjectWorkspace
    from engine.tribunal import adjudicate, save_decision_snapshot
    ws = ProjectWorkspace.open(_home(args), args.project)
    store = GraphStore.create(ws)
    snap = adjudicate(store, project=ws)
    path = save_decision_snapshot(ws, snap)
    print(f"{snap['decision']} / {snap['confidence_label']} ({path})")
    return 0


def _cmd_report(args) -> int:
    from engine.project import ProjectWorkspace
    from engine.projections import build_v1_compat_result
    ws = ProjectWorkspace.open(_home(args), args.project)
    compat = build_v1_compat_result(ws)
    out = ws.path / "projections" / f"report-rev-{ws.current_revision():06d}.json"
    out.write_text(__import__("json").dumps(compat, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    print(out)
    return 0


def _cmd_migrate(args) -> int:
    from engine.migration import migrate_v1_pack
    result = migrate_v1_pack(args.pack, home=_home(args), title=args.title)
    print(f"{result.project_id} rev {result.graph_revision}")
    for w in result.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eduevidence",
        description="EduEvidence run orchestrator — stage routing, schema gates, resume, failures")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="create a run workspace and advance stages")
    p_run.add_argument("--question", required=True, help="education question to research")
    p_run.add_argument("--depth", default="M", choices=["quick", "standard", "deep", "S", "M", "L"],
                       help="complexity depth (default: standard/M)")
    p_run.add_argument("--run-id", default=None, help="explicit run id (default: timestamp)")
    p_run.add_argument("--demo-pack", default=None, type=Path,
                       help="seed external stages from an example pack (demo/test mode)")
    p_run.add_argument("--approve-agent-mcp", action="store_true",
                       help="record agent-mcp approval in the manifest")
    p_run.add_argument("--dry-run", action="store_true", help="initialize only, do not advance")
    p_run.add_argument("--runs-dir", default=os.environ.get("EDUEVIDENCE_RUNS_DIR", str(ROOT / "runs")),
                       help="directory holding run workspaces (default: <repo>/runs)")
    p_run.set_defaults(func=_cmd_run)

    p_resume = sub.add_parser("resume", help="continue a run from its state.json")
    p_resume.add_argument("--run-id", required=True)
    p_resume.add_argument("--demo-pack", default=None, type=Path)
    p_resume.add_argument("--runs-dir", default=os.environ.get("EDUEVIDENCE_RUNS_DIR", str(ROOT / "runs")))
    p_resume.set_defaults(func=_cmd_resume)

    p_status = sub.add_parser("status", help="show run state")
    p_status.add_argument("--run-id", required=True)
    p_status.add_argument("--runs-dir", default=os.environ.get("EDUEVIDENCE_RUNS_DIR", str(ROOT / "runs")))
    p_status.set_defaults(func=_cmd_status)

    p_list = sub.add_parser("list", help="list runs")
    p_list.add_argument("--runs-dir", default=os.environ.get("EDUEVIDENCE_RUNS_DIR", str(ROOT / "runs")))
    p_list.set_defaults(func=_cmd_list)

    p_gate = sub.add_parser("gate", help="run the Pre-Verdict Gate over a run")
    p_gate.add_argument("--run-id", required=True)
    p_gate.add_argument("--require-final", action="store_true")
    p_gate.add_argument("--runs-dir", default=os.environ.get("EDUEVIDENCE_RUNS_DIR", str(ROOT / "runs")))
    p_gate.set_defaults(func=_cmd_gate)

    # ---- V2 project-scoped commands ------------------------------------
    p_proj_create = sub.add_parser("project", help="V2 project lifecycle")
    p_proj_create.add_argument("action", choices=["create", "list", "status"])
    p_proj_create.add_argument("--question", default=None, help="research question (create)")
    p_proj_create.add_argument("--title", default=None, help="project title (create)")
    p_proj_create.add_argument("--mode", default="evidence_review",
                               choices=["evidence_review", "full_research_cycle"])
    p_proj_create.add_argument("--project", default=None, help="project id (status)")
    p_proj_create.add_argument("--home", default=None, help="EDUEVIDENCE_HOME override")
    p_proj_create.set_defaults(func=_cmd_project)

    p_research = sub.add_parser("research", help="V2 research planning/run")
    p_research.add_argument("action", choices=["plan", "run", "resume"])
    p_research.add_argument("--project", required=True)
    p_research.add_argument("--home", default=None)
    p_research.set_defaults(func=_cmd_research)

    p_graph = sub.add_parser("graph", help="V2 graph validation")
    p_graph.add_argument("action", choices=["validate"])
    p_graph.add_argument("--project", required=True)
    p_graph.add_argument("--home", default=None)
    p_graph.set_defaults(func=_cmd_graph)

    p_study = sub.add_parser("study", help="V2 study design (grounded)")
    p_study.add_argument("action", choices=["design"])
    p_study.add_argument("--project", required=True)
    p_study.add_argument("--gap", action="append", default=[], help="GAP-xxx ids")
    p_study.add_argument("--question", default=None, help="research question")
    p_study.add_argument("--design-type", default="rct",
                         choices=["rct", "cluster_rct", "quasi_experimental",
                                  "pre_post", "observational", "survey",
                                  "qualitative", "mixed_methods"])
    p_study.add_argument("--population", default=None)
    p_study.add_argument("--sampling", default=None)
    p_study.add_argument("--intervention", default=None)
    p_study.add_argument("--comparison", default=None)
    p_study.add_argument("--outcome", default=None)
    p_study.add_argument("--measure", default=None)
    p_study.add_argument("--assignment", default=None)
    p_study.add_argument("--home", default=None)

    p_data = sub.add_parser("data", help="V2 dataset ingest")
    p_data.add_argument("action", choices=["ingest"])
    p_data.add_argument("--project", required=True)
    p_data.add_argument("--design", required=True)
    p_data.add_argument("--file", required=True, type=Path)
    p_data.add_argument("--privacy", default="internal",
                        choices=["public", "internal", "confidential", "restricted"])
    p_data.add_argument("--home", default=None)
    p_data.set_defaults(func=_cmd_data)

    p_analyze = sub.add_parser("analyze", help="V2 analysis (native descriptive)")
    p_analyze.add_argument("--project", required=True)
    p_analyze.add_argument("--plan", required=True)
    p_analyze.add_argument("--home", default=None)
    p_analyze.set_defaults(func=_cmd_analyze)

    p_adjudicate = sub.add_parser("adjudicate", help="V2 tribunal over current graph")
    p_adjudicate.add_argument("--project", required=True)
    p_adjudicate.add_argument("--home", default=None)
    p_adjudicate.set_defaults(func=_cmd_adjudicate)

    p_report = sub.add_parser("report", help="V2 projection/report")
    p_report.add_argument("--project", required=True)
    p_report.add_argument("--theme", default="claude",
                          choices=["claude", "academic", "datalab", "datalab-dark", "presentation"])
    p_report.add_argument("--home", default=None)
    p_report.set_defaults(func=_cmd_report)

    p_migrate = sub.add_parser("migrate-v1", help="import a V1 pack into a V2 project")
    p_migrate.add_argument("--pack", required=True, type=Path)
    p_migrate.add_argument("--title", default=None)
    p_migrate.add_argument("--home", default=None)
    p_migrate.set_defaults(func=_cmd_migrate)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as exc:
        # V2 project lookups fail cleanly like V1 (ERROR + exit 2)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
