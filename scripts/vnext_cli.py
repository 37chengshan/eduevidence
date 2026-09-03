from __future__ import annotations
import argparse
import json
from pathlib import Path


def _read_json(path, default=None):
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _home(value):
    if value:
        return Path(value).expanduser().resolve()
    from engine.paths import resolve_home
    return resolve_home()


def _project(home, project_id):
    from engine.project import ProjectWorkspace
    return ProjectWorkspace.open(home, project_id)


def _load_gaps(workspace, explicit=None):
    if explicit:
        path = Path(explicit)
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    gap_dir = workspace.path / "gaps"
    files = sorted(gap_dir.glob("gaps-rev-*.jsonl")) if gap_dir.exists() else []
    if not files:
        raise ValueError("no persisted KnowledgeGap file; run gap derivation first or pass --gaps")
    return [json.loads(line) for line in files[-1].read_text(encoding="utf-8").splitlines() if line.strip()]


def _commit_payload(workspace, run_id, payload):
    from engine.evidence_review import (
        ingest_claims_links,
        ingest_extracted_studies_findings,
        ingest_methodology_audits,
        ingest_validated_sources,
    )
    from engine.graph_store import GraphStore
    store = GraphStore.create(workspace)
    if payload.get("sources"):
        ingest_validated_sources(store, run_id=run_id, sources=payload["sources"])
    if payload.get("studies") or payload.get("findings"):
        ingest_extracted_studies_findings(
            store,
            run_id=run_id,
            studies=payload.get("studies", []),
            findings=payload.get("findings", []),
        )
    if payload.get("audits"):
        ingest_methodology_audits(store, run_id=run_id, audits=payload["audits"])
    if payload.get("claims") or payload.get("links"):
        ingest_claims_links(
            store,
            run_id=run_id,
            claims=payload.get("claims", []),
            links=payload.get("links", []),
        )
    return store.active_revision()


def research_auto(argv):
    parser = argparse.ArgumentParser(prog="eduevidence research auto")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("step", "start"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--home")
        cmd.add_argument("--gaps")
        cmd.add_argument("--decision")
        cmd.add_argument("--outcome-file")
        cmd.add_argument("--max-iterations", type=int, default=5)
        cmd.add_argument("--ethics-feasible", action="store_true")
    for name in ("status", "report", "stop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--home")
    args = parser.parse_args(argv)
    workspace = _project(_home(args.home), args.project)
    root = workspace.path / "autoresearch"
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "state.json"

    if args.action in {"status", "report"}:
        print(json.dumps(_read_json(state_path, {"status": "not_started"}), ensure_ascii=False, indent=2))
        return 0
    if args.action == "stop":
        state = _read_json(state_path, {}) or {}
        state["status"] = "stopped_by_user"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("stopped")
        return 0

    from engine.autoresearch import EvidenceAutoresearchController, NegativeSearchRecord, ResearchMemory
    from engine.graph_store import GraphStore
    memory = ResearchMemory(root)
    gaps = _load_gaps(workspace, args.gaps)
    decision = _read_json(args.decision, {}) or {}
    history = memory.load_iterations()
    controller = EvidenceAutoresearchController(max_iterations=args.max_iterations)
    outcome = _read_json(args.outcome_file) if args.outcome_file else None

    if outcome is None:
        priority = controller.select_gap(gaps, decision)
        gap = next(g for g in gaps if g.get("gap_id") == priority.gap_id)
        strategy = controller.build_strategy(priority, gap)
        pending = {
            "status": "awaiting_execution",
            "project_id": args.project,
            "base_graph_revision": GraphStore.create(workspace).active_revision(),
            "gap_priority": priority.as_dict(),
            "strategy": {
                "strategy_id": strategy.strategy_id,
                "experiment_type": strategy.experiment_type.value,
                "hypothesis": strategy.hypothesis,
                "expected_gain": strategy.expected_gain,
                "budget": strategy.budget.__dict__,
            },
        }
        state_path.write_text(json.dumps(pending, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(pending, ensure_ascii=False, indent=2))
        return 0

    evidence_ids = outcome.get("validated_evidence_ids") or [
        item.get("finding_id") for item in outcome.get("findings", []) if item.get("finding_id")
    ]
    outcome["validated_evidence_ids"] = evidence_ids

    def executor(strategy, gap):
        return outcome

    def commit(ids):
        return _commit_payload(workspace, f"autoresearch-{len(history) + 1:04d}", outcome)

    result = controller.step(
        project_id=args.project,
        base_graph_revision=GraphStore.create(workspace).active_revision(),
        gaps=gaps,
        decision=decision,
        history=history,
        executor=executor,
        graph_commit=commit if evidence_ids else None,
        ethics_feasible=args.ethics_feasible,
    )
    for raw in outcome.get("negative_searches", []):
        record = NegativeSearchRecord(**raw)
        memory.append_negative_search(record)
        if record.negative_search_id not in result.iteration.negative_search_ids:
            result.iteration.negative_search_ids.append(record.negative_search_id)
    memory.append_iteration(result.iteration)
    state = {
        "status": result.iteration.status.value if result.iteration.status else "unknown",
        "next_action": result.next_action,
        "gap_priority": result.priority.as_dict(),
        "iteration": result.iteration.as_dict(),
        "rationale": list(result.rationale),
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


def evolve(argv):
    parser = argparse.ArgumentParser(prog="eduevidence evolve")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("init", "status", "report", "best"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--root", default=".")
    cmd = sub.add_parser("baseline")
    cmd.add_argument("--root", default=".")
    cmd.add_argument("--eval", required=True)
    cmd = sub.add_parser("run")
    cmd.add_argument("--root", default=".")
    cmd.add_argument("--experiment", required=True)
    cmd.add_argument("--baseline-eval", required=True)
    cmd.add_argument("--candidate-eval", required=True)
    cmd = sub.add_parser("prepare-pr")
    cmd.add_argument("--root", default=".")
    args = parser.parse_args(argv)
    repo = Path(args.root).resolve()
    root = repo / "autoevolve"
    root.mkdir(parents=True, exist_ok=True)
    from engine.autoevolve import (
        DailyProfile,
        EvalSnapshot,
        ExperimentLog,
        PlateauTracker,
        ProtectedManifest,
        SkillExperiment,
        promote,
    )
    if args.action == "init":
        DailyProfile().validate()
        (root / "runs").mkdir(exist_ok=True)
        if not (root / "best.json").exists():
            (root / "best.json").write_text('{"best_experiment_id": null}\n', encoding="utf-8")
        ExperimentLog(root)
        print(root)
        return 0
    if args.action in {"status", "report"}:
        rows = (root / "results.tsv").read_text(encoding="utf-8").splitlines()[1:] if (root / "results.tsv").exists() else []
        best = _read_json(root / "best.json", {}) or {}
        statuses = [row.split("\t")[-2] for row in rows if "\t" in row]
        print(json.dumps({"experiments": len(rows), "best": best, "plateau": PlateauTracker().plateau(statuses)}, indent=2))
        return 0
    if args.action == "best":
        print(json.dumps(_read_json(root / "best.json", {}), indent=2))
        return 0
    if args.action == "baseline":
        data = _read_json(args.eval)
        (root / "baseline.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(data.get("eval_id", "baseline"))
        return 0
    if args.action == "run":
        experiment = SkillExperiment(**_read_json(args.experiment))
        baseline = EvalSnapshot(**_read_json(args.baseline_eval))
        candidate = EvalSnapshot(**_read_json(args.candidate_eval))
        ok, bad = ProtectedManifest().validate_changes(experiment.changed_files)
        if not ok:
            status, reason = "INVALID", "protected mutation: " + ",".join(bad)
        else:
            status, reason = promote(baseline, candidate)
        experiment.status = status
        experiment.promotion_reason = reason
        ExperimentLog(root).append(experiment, candidate=candidate, description=reason)
        if status == "KEEP":
            (root / "best.json").write_text(
                json.dumps({"best_experiment_id": experiment.experiment_id, "candidate_commit": experiment.candidate_commit, "eval_id": candidate.eval_id}, indent=2) + "\n",
                encoding="utf-8",
            )
        print(json.dumps({"status": status, "reason": reason}, indent=2))
        return 0
    if args.action == "prepare-pr":
        best = _read_json(root / "best.json", {}) or {}
        print(json.dumps({"promotion": "branch_only", "best": best, "note": "Human approval is required to open/merge the final PR."}, indent=2))
        return 0
    return 2
