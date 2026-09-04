from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _read_json(path: str | Path | None, default=None):
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


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
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        gap_dir = workspace.path / "gaps"
        files = sorted(gap_dir.glob("gaps-rev-*.jsonl")) if gap_dir.exists() else []
        if not files:
            raise ValueError("no persisted KnowledgeGap file; derive gaps first or pass --gaps")
        rows = [
            json.loads(line)
            for line in files[-1].read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return rows


def _apply_gap_state(gaps: list[dict[str, Any]], state: dict[str, str]) -> None:
    for gap in gaps:
        gap_id = str(gap.get("gap_id", ""))
        if gap_id in state:
            gap["status"] = state[gap_id]


def _save_gap_state(path: Path, gaps: list[dict[str, Any]]) -> None:
    _write_json(
        path,
        {
            str(gap.get("gap_id")): str(gap.get("status", "open"))
            for gap in gaps
            if gap.get("gap_id")
        },
    )


def _require_fresh_research_state(
    *,
    active_revision: int,
    gaps: list[dict[str, Any]],
    decision: dict[str, Any],
    previous_state: dict[str, Any],
) -> None:
    if previous_state.get("next_action") == "re_adjudicate":
        if int(decision.get("graph_revision", -1)) != active_revision:
            raise ValueError(
                "re-adjudication barrier: provide a DecisionSnapshot bound to the current GraphRevision"
            )
    for gap in gaps:
        derived = gap.get("derived_from_graph_revision")
        if derived is not None and int(derived) != active_revision:
            raise ValueError(
                f"stale KnowledgeGap {gap.get('gap_id')}: derived from revision {derived}, "
                f"active revision is {active_revision}; re-derive gaps before continuing"
            )


def _iteration_id(iteration_number: int) -> str:
    return f"RIT-{iteration_number:04d}"


def _request(priority, strategy, project_id, revision, iteration_number, gap):
    iteration_id = _iteration_id(iteration_number)
    return {
        "project_id": project_id,
        "iteration_id": iteration_id,
        "iteration_number": iteration_number,
        "base_graph_revision": revision,
        "gap_id": priority.gap_id,
        "gap": gap,
        "gap_priority": priority.as_dict(),
        "strategy": {
            "strategy_id": strategy.strategy_id,
            "experiment_type": strategy.experiment_type.value,
            "hypothesis": strategy.hypothesis,
            "expected_gain": strategy.expected_gain,
            "budget": strategy.budget.__dict__,
        },
        "contract": {
            "canonical_state_write": "FORBIDDEN",
            "output": "validated staging result JSON only",
            "required_measurements": ["query_count", "candidate_count", "fetched_count"],
            "negative_search_research_iteration_id": iteration_id,
            "negative_search_gap_id": priority.gap_id,
            "search_snippets_are_evidence": False,
        },
    }


def _validate_outcome_budget(outcome: dict[str, Any], strategy) -> None:
    if not isinstance(outcome, dict):
        raise ValueError("executor output must be a JSON object")
    budget = strategy.budget
    checks = (
        ("query_count", budget.max_queries),
        ("candidate_count", budget.max_candidates),
        ("fetched_count", budget.max_fulltext_fetches),
    )
    measured: dict[str, int] = {}
    for key, limit in checks:
        if key not in outcome:
            raise ValueError(f"executor output must report {key} to enforce bounded research")
        try:
            value = int(outcome[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"executor measurement {key} must be an integer") from exc
        if value < 0:
            raise ValueError(f"executor measurement {key} cannot be negative")
        if value > limit:
            raise ValueError(f"research budget exceeded: {key}={value} > {limit}")
        measured[key] = value
    if measured["fetched_count"] > measured["candidate_count"]:
        raise ValueError("fetched_count cannot exceed candidate_count")
    candidates = outcome.get("candidate_sources")
    if isinstance(candidates, list) and len(candidates) > measured["candidate_count"]:
        raise ValueError("candidate_sources length exceeds reported candidate_count")
    attempts = outcome.get("search_attempts")
    if isinstance(attempts, list) and len(attempts) > measured["query_count"]:
        raise ValueError("search_attempts length exceeds reported query_count")


def _validate_outcome_identity(
    outcome: dict[str, Any], *, expected_iteration_id: str, expected_gap_id: str
) -> None:
    supplied_iteration = outcome.get("iteration_id")
    supplied_gap = outcome.get("gap_id")
    if supplied_iteration is not None and supplied_iteration != expected_iteration_id:
        raise ValueError("executor iteration_id does not match ResearchRequest")
    if supplied_gap is not None and supplied_gap != expected_gap_id:
        raise ValueError("executor gap_id does not match ResearchRequest")


def _external_executor(command, request, request_path, *, timeout_seconds: int):
    _write_json(request_path, request)
    argv = shlex.split(command)
    if not argv:
        raise ValueError("empty executor command")
    env = os.environ.copy()
    env["EDUEVIDENCE_RESEARCH_REQUEST"] = str(request_path)
    completed = subprocess.run(
        argv,
        check=True,
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout_seconds,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("executor stdout must be one JSON object")
    return value


def _commit_payload(workspace, run_id, payload, *, expected_base_revision: int):
    from engine.autoresearch import commit_staging_bundle
    from engine.graph_store import GraphStore

    return commit_staging_bundle(
        GraphStore.create(workspace),
        run_id=run_id,
        expected_base_revision=expected_base_revision,
        payload=payload,
    )


@contextmanager
def _writer_lock(path: Path):
    """One research-auto writer per Project; stale locks fail closed."""
    payload = {
        "pid": os.getpid(),
        "acquired_at": datetime.now(timezone.utc).isoformat(),
    }
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError as exc:
        detail = ""
        try:
            detail = path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
        raise RuntimeError(
            f"research auto writer already active or a stale lock exists at {path}. "
            "Do not delete it while another run is active; after confirming no writer is running, "
            f"remove it manually. lock={detail or 'unreadable'}"
        ) from exc
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.write("\n")
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _mutating_research_auto(args, workspace, root, state_path, gap_state_path, stop_path):
    from engine.autoresearch import EvidenceAutoresearchController, NegativeSearchRecord, ResearchMemory
    from engine.graph_store import GraphStore

    memory = ResearchMemory(root)
    gaps = _load_gaps(workspace, args.gaps)
    _apply_gap_state(gaps, _read_json(gap_state_path, {}) or {})
    decision = _read_json(args.decision, {}) or {}
    controller = EvidenceAutoresearchController(max_iterations=args.max_iterations)
    store = GraphStore.create(workspace)
    previous_state = _read_json(state_path, {}) or {}
    _require_fresh_research_state(
        active_revision=store.active_revision(),
        gaps=gaps,
        decision=decision,
        previous_state=previous_state,
    )

    def process(outcome, history, priority, strategy):
        base_revision = GraphStore.create(workspace).active_revision()
        expected_iteration_id = _iteration_id(len(history) + 1)
        _validate_outcome_identity(
            outcome,
            expected_iteration_id=expected_iteration_id,
            expected_gap_id=priority.gap_id,
        )
        _validate_outcome_budget(outcome, strategy)
        evidence_ids = outcome.get("validated_evidence_ids") or [
            item.get("finding_id")
            for item in outcome.get("findings", [])
            if isinstance(item, dict) and item.get("finding_id")
        ]
        outcome["validated_evidence_ids"] = [item for item in evidence_ids if item]

        def executor(actual_strategy, gap):
            if actual_strategy.strategy_id != strategy.strategy_id:
                raise RuntimeError("controller strategy changed between request and execution")
            return outcome

        def commit(_ids):
            return _commit_payload(
                workspace,
                f"autoresearch-{len(history) + 1:04d}",
                outcome,
                expected_base_revision=base_revision,
            )

        result = controller.step(
            project_id=args.project,
            base_graph_revision=base_revision,
            gaps=gaps,
            decision=decision,
            history=history,
            executor=executor,
            graph_commit=commit if outcome["validated_evidence_ids"] else None,
            ethics_feasible=args.ethics_feasible,
        )
        for raw in outcome.get("negative_searches", []):
            record = NegativeSearchRecord(**raw)
            if record.research_iteration_id != result.iteration.iteration_id:
                raise ValueError(
                    "NegativeSearchRecord research_iteration_id does not match current iteration"
                )
            if record.gap_id != result.iteration.gap_id:
                raise ValueError("NegativeSearchRecord gap_id does not match current gap")
            memory.append_negative_search(record)
            if record.negative_search_id not in result.iteration.negative_search_ids:
                result.iteration.negative_search_ids.append(record.negative_search_id)
        memory.append_iteration(result.iteration)
        return result

    def persist_result(result, completed=None):
        selected = next(g for g in gaps if g.get("gap_id") == result.iteration.gap_id)
        if result.next_action == "stop_search_saturated":
            selected["status"] = "search_saturated"
        elif result.next_action == "empirical_evidence_needed":
            selected["status"] = "empirical_needed"
        state = {
            "status": result.iteration.status.value if result.iteration.status else "unknown",
            "next_action": result.next_action,
            "gap_priority": result.priority.as_dict(),
            "iteration": result.iteration.as_dict(),
            "rationale": list(result.rationale),
        }
        if completed is not None:
            state["completed_iterations"] = list(completed)
        _save_gap_state(gap_state_path, gaps)
        _write_json(state_path, state)
        return state

    if args.action == "step":
        history = memory.load_iterations()
        priority = controller.select_gap(gaps, decision)
        gap = next(g for g in gaps if g.get("gap_id") == priority.gap_id)
        strategy = controller.build_strategy(priority, gap, history)
        outcome = _read_json(args.outcome_file) if args.outcome_file else None
        if outcome is None:
            pending = {
                "status": "awaiting_execution",
                **_request(
                    priority,
                    strategy,
                    args.project,
                    GraphStore.create(workspace).active_revision(),
                    len(history) + 1,
                    gap,
                ),
            }
            _write_json(state_path, pending)
            print(json.dumps(pending, ensure_ascii=False, indent=2))
            return 0
        result = process(outcome, history, priority, strategy)
        state = persist_result(result)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0

    if args.outcome_file and args.max_iterations != 1:
        raise ValueError(
            "--outcome-file with start requires --max-iterations 1; use --executor-command for a loop"
        )
    if not args.executor_command and not args.outcome_file:
        raise ValueError(
            "start requires --executor-command or one --outcome-file with --max-iterations 1"
        )

    completed = []
    for _ in range(args.max_iterations):
        if stop_path.exists():
            stop_path.unlink(missing_ok=True)
            latest = _read_json(state_path, {}) or {}
            latest["status"] = "stopped_by_user"
            latest["completed_iterations"] = list(completed)
            _write_json(state_path, latest)
            break
        history = memory.load_iterations()
        priority = controller.select_gap(gaps, decision)
        gap = next(g for g in gaps if g.get("gap_id") == priority.gap_id)
        strategy = controller.build_strategy(priority, gap, history)
        request = _request(
            priority,
            strategy,
            args.project,
            GraphStore.create(workspace).active_revision(),
            len(history) + 1,
            gap,
        )
        outcome = (
            _read_json(args.outcome_file)
            if args.outcome_file
            else _external_executor(
                args.executor_command,
                request,
                root / f"request-{len(history) + 1:04d}.json",
                timeout_seconds=args.executor_timeout_seconds,
            )
        )
        result = process(outcome, history, priority, strategy)
        completed.append(result.iteration.iteration_id)

        for gap_id in outcome.get("resolved_gap_ids", []):
            for gap_row in gaps:
                if gap_row.get("gap_id") == gap_id:
                    gap_row["status"] = "resolved"
        persist_result(result, completed)

        if result.next_action in {
            "re_adjudicate",
            "empirical_evidence_needed",
            "stop_search_saturated",
        }:
            break
        if all(str(row.get("status", "")).lower() == "resolved" for row in gaps):
            break

    final = _read_json(state_path, {"status": "completed_no_iterations"})
    print(json.dumps(final, ensure_ascii=False, indent=2))
    return 0


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
        cmd.add_argument("--executor-timeout-seconds", type=int, default=1800)
        if name == "start":
            cmd.add_argument("--executor-command")
    for name in ("status", "report", "stop"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--project", required=True)
        cmd.add_argument("--home")
    args = parser.parse_args(argv)
    if getattr(args, "executor_timeout_seconds", 1) <= 0:
        raise ValueError("executor timeout must be positive")

    workspace = _project(_home(args.home), args.project)
    root = workspace.path / "autoresearch"
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "state.json"
    gap_state_path = root / "gap-state.json"
    stop_path = root / "stop.requested"
    lock_path = root / ".writer.lock"

    if args.action in {"status", "report"}:
        state = _read_json(state_path, {"status": "not_started"})
        if isinstance(state, dict):
            state = dict(state)
            state["stop_requested"] = stop_path.exists()
            state["writer_active"] = lock_path.exists()
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.action == "stop":
        stop_path.write_text(
            json.dumps(
                {
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "requested_by_pid": os.getpid(),
                }
            )
            + "\n",
            encoding="utf-8",
        )
        print("stop requested")
        return 0

    with _writer_lock(lock_path):
        return _mutating_research_auto(
            args,
            workspace,
            root,
            state_path,
            gap_state_path,
            stop_path,
        )
