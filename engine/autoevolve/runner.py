from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_view import AgentMutationView
from .core import (
    DailyProfile,
    EvalSnapshot,
    ExperimentLog,
    PlateauTracker,
    ProtectedManifest,
    SkillExperiment,
    promote,
)
from .git_workspace import GitWorkspace


def _run_json(command: str, cwd: Path, env=None) -> dict:
    argv = shlex.split(command)
    if not argv:
        raise ValueError("empty command")
    completed = subprocess.run(
        argv,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
        env=env,
    )
    value = json.loads(completed.stdout)
    if not isinstance(value, dict):
        raise ValueError("command stdout must be one JSON object")
    return value


def _read_jsonl(path: Path, limit: int = 25) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]


def _session_root(repo: Path, tag: str) -> Path:
    configured = os.environ.get("EDUEVIDENCE_AUTOEVOLVE_STATE_DIR")
    base = (
        Path(configured).expanduser().resolve()
        if configured
        else repo.parent / ".eduevidence-autoevolve-state"
    )
    root = base / tag
    if root.exists():
        raise FileExistsError(f"autoevolve session state already exists: {root}")
    root.mkdir(parents=True)
    return root


def _session_context(workspace: GitWorkspace, state_root: Path) -> dict[str, Any]:
    repo_history = _read_jsonl(workspace.path / "autoevolve" / "experiments.jsonl")
    current_history = _read_jsonl(state_root / "experiments.jsonl")
    return {
        "branch": workspace.branch,
        "parent_revision": workspace.head(),
        "prior_experiments": (repo_history + current_history)[-25:],
        "holdout_policy": (
            "This mutation view intentionally contains DEV benchmark material only. "
            "Do not seek or infer hidden HOLDOUT/adversarial cases."
        ),
    }


def _append_file(source: Path, target: Path, *, skip_first_line: bool = False) -> None:
    if not source.is_file():
        return
    lines = source.read_text(encoding="utf-8").splitlines()
    if skip_first_line and lines:
        lines = lines[1:]
    if not lines:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line + "\n")


def _copy_public_session_files(state_root: Path, run_target: Path) -> None:
    """Persist only structured, non-candidate session records to Git."""
    run_target.mkdir(parents=True, exist_ok=False)
    for name in ("results.tsv", "experiments.jsonl", "daily-report.json"):
        source = state_root / name
        if source.is_file():
            shutil.copy2(source, run_target / name)


def _export_session(
    workspace: GitWorkspace,
    state_root: Path,
    *,
    tag: str,
    best_experiment_id: str | None,
    best_commit: str | None,
) -> str:
    """Persist audit memory only after candidate evaluation has finished.

    Candidate patches/files remain local in the external state directory. They
    are deliberately excluded from automatic branch persistence because an
    external agent could have written sensitive/transient material into them.
    """
    run_target = workspace.path / "autoevolve" / "runs" / tag
    if run_target.exists():
        raise FileExistsError(f"session run target exists: {run_target}")
    run_target.parent.mkdir(parents=True, exist_ok=True)
    _copy_public_session_files(state_root, run_target)

    _append_file(
        state_root / "results.tsv",
        workspace.path / "autoevolve" / "results.tsv",
        skip_first_line=True,
    )
    _append_file(
        state_root / "experiments.jsonl",
        workspace.path / "autoevolve" / "experiments.jsonl",
    )
    if best_experiment_id:
        (workspace.path / "autoevolve" / "best.json").write_text(
            json.dumps(
                {
                    "best_experiment_id": best_experiment_id,
                    "candidate_commit": best_commit,
                    "session": tag,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return workspace.commit(f"autoevolve: record session {tag}")


class DailyEvolutionRunner:
    """Run bounded branch-only autoresearch against an external approved agent.

    Candidate mutation occurs in a sanitized view; evaluator execution occurs
    in the full isolated worktree. Session logs live outside the candidate
    worktree during experimentation so reject/revert can never erase history or
    accidentally commit evaluator logs as part of a candidate code change.
    """

    def __init__(self, repo: str | Path, *, profile: DailyProfile | None = None):
        self.repo = Path(repo).resolve()
        self.profile = profile or DailyProfile()
        self.profile.validate()

    def run(
        self,
        *,
        agent_command: str,
        eval_command: str,
        run_tag: str | None = None,
        push_branch: bool = False,
        max_retests: int = 2,
    ) -> dict:
        if max_retests < 0 or max_retests > 5:
            raise ValueError("max_retests must be 0..5")
        tag = run_tag or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        workspace = GitWorkspace.create(self.repo, tag)
        state_root = _session_root(self.repo, tag)
        log = ExperimentLog(state_root)
        manifest = ProtectedManifest.from_repo(workspace.path)
        plateau = PlateauTracker()
        baseline = EvalSnapshot(**_run_json(eval_command, workspace.path))
        statuses: list[str] = []
        spent = float(baseline.cost)
        best = None
        best_commit = None
        stop_reason = "completed"
        started = time.monotonic()

        for index in range(1, self.profile.max_experiments + 1):
            if spent >= self.profile.max_cost_usd:
                stop_reason = "cost_budget_exhausted"
                break
            if (time.monotonic() - started) / 60 >= self.profile.max_wall_minutes:
                stop_reason = "wall_time_exhausted"
                break

            experiment_id = f"EXP-{index:04d}"
            parent_revision = workspace.head()
            protected_before = manifest.hash_tree(workspace.path)
            view = AgentMutationView.create(
                workspace.path,
                session_context=_session_context(workspace, state_root),
            )
            candidate = None
            attempted: list[str] = []
            budget_hit = False
            try:
                env = os.environ.copy()
                env.update(
                    {
                        "EDUEVIDENCE_EXPERIMENT_ID": experiment_id,
                        "EDUEVIDENCE_PROGRAM": str(view.path / "autoevolve" / "program.md"),
                        "EDUEVIDENCE_SESSION_CONTEXT": str(view.path / "autoevolve" / "session-context.json"),
                        "EDUEVIDENCE_HOLDOUT_ACCESS": "FORBIDDEN",
                    }
                )
                proposal = _run_json(agent_command, view.path, env)
                hypothesis = str(proposal.get("hypothesis", "")).strip()
                if not hypothesis:
                    raise ValueError("empty hypothesis")
                proposal_cost = float(proposal.get("cost_usd", 0) or 0)
                if proposal_cost < 0:
                    raise ValueError("agent cost_usd cannot be negative")
                spent += proposal_cost
                attempted = view.changed_files()
                proposal_tiers = tuple(proposal.get("mutation_scope") or self.profile.mutation_tiers)
                if not set(proposal_tiers).issubset(set(self.profile.mutation_tiers)):
                    status, reason = "INVALID", "agent requested a mutation tier not allowed by session profile"
                else:
                    protected_ok, protected_bad = manifest.validate_changes(attempted)
                    scope_ok, scope_bad = manifest.validate_mutation_scope(
                        attempted,
                        mutation_tiers=self.profile.mutation_tiers,
                        allow_controlled=self.profile.allow_controlled,
                    )
                    if not attempted:
                        status, reason = "REJECT", "agent made no change"
                    elif not protected_ok:
                        status, reason = "INVALID", "protected mutation: " + ",".join(protected_bad)
                    elif not scope_ok:
                        status, reason = "INVALID", "mutation outside approved tier: " + ",".join(scope_bad)
                    elif spent >= self.profile.max_cost_usd:
                        status, reason = "REJECT", "session cost budget exhausted before candidate evaluation"
                        budget_hit = True
                    else:
                        view.sync_to(workspace.path, attempted)
                        protected_after_sync = manifest.hash_tree(workspace.path)
                        if protected_after_sync != protected_before:
                            status, reason = "INVALID", "protected tree hash changed"
                        else:
                            eval_env = os.environ.copy()
                            eval_env["EDUEVIDENCE_EXPERIMENT_ID"] = experiment_id
                            for retest_index in range(max_retests + 1):
                                eval_env["EDUEVIDENCE_RETEST_INDEX"] = str(retest_index)
                                candidate = EvalSnapshot(**_run_json(eval_command, workspace.path, eval_env))
                                spent += float(candidate.cost)
                                status, reason = promote(baseline, candidate)
                                if status != "RETEST":
                                    break
                                if spent >= self.profile.max_cost_usd:
                                    budget_hit = True
                                    reason += "; session cost budget exhausted"
                                    break
                            if spent > self.profile.max_cost_usd and status == "KEEP":
                                status = "HUMAN_REVIEW"
                                reason = "candidate passed quality gates but session cost ceiling was exceeded"
                                budget_hit = True

                protected_after = manifest.hash_tree(workspace.path)
                experiment = SkillExperiment(
                    experiment_id=experiment_id,
                    session_id=tag,
                    parent_skill_revision=parent_revision,
                    hypothesis=hypothesis,
                    mutation_scope=proposal_tiers,
                    changed_files=attempted,
                    baseline_eval_id=baseline.eval_id,
                    candidate_eval_id=candidate.eval_id if candidate else None,
                    protected_hash_before=protected_before,
                    protected_hash_after=protected_after,
                    status=status,
                    promotion_reason=reason,
                    complexity_delta=(candidate.complexity - baseline.complexity) if candidate else 0.0,
                )
                if status == "KEEP":
                    experiment.candidate_commit = workspace.commit(
                        f"experiment: {experiment_id} {hypothesis[:72]}"
                    )
                    baseline = candidate
                    best = experiment_id
                    best_commit = experiment.candidate_commit
                else:
                    if attempted:
                        artifact_dir = state_root / "candidates" / experiment_id
                        view.export_changes(artifact_dir / "files", attempted)
                        diff = workspace.diff()
                        if diff:
                            (artifact_dir / "candidate.diff").parent.mkdir(parents=True, exist_ok=True)
                            (artifact_dir / "candidate.diff").write_text(diff, encoding="utf-8")
                    workspace.restore()
                log.append(experiment, candidate=candidate, description=reason)
                statuses.append(status)
            except Exception as exc:
                if attempted:
                    try:
                        view.export_changes(state_root / "candidates" / experiment_id / "files", attempted)
                    except Exception:
                        pass
                workspace.restore()
                experiment = SkillExperiment(
                    experiment_id=experiment_id,
                    session_id=tag,
                    parent_skill_revision=parent_revision,
                    hypothesis="invalid-or-crashed",
                    mutation_scope=self.profile.mutation_tiers,
                    changed_files=attempted,
                    baseline_eval_id=baseline.eval_id,
                    protected_hash_before=protected_before,
                    protected_hash_after=manifest.hash_tree(workspace.path),
                    status="CRASH",
                    promotion_reason=str(exc),
                )
                log.append(experiment, description=str(exc))
                statuses.append("CRASH")
            finally:
                view.cleanup()

            if budget_hit:
                stop_reason = "cost_budget_exhausted"
                break
            if plateau.plateau(statuses):
                stop_reason = "plateau"
                break

        report = {
            "run_tag": tag,
            "branch": workspace.branch,
            "experiments": len(statuses),
            "statuses": statuses,
            "best_experiment_id": best,
            "best_candidate_commit": best_commit,
            "cost": spent,
            "wall_minutes": round((time.monotonic() - started) / 60, 3),
            "plateau": plateau.plateau(statuses),
            "stop_reason": stop_reason,
            "promotion": "branch_only",
            "branch_push_requested": push_branch,
            "branch_pushed": False,
            "mutation_view": "dev_only_context_isolation",
            "security_note": "OS-level holdout isolation must be attested by evaluator for automatic KEEP",
            "candidate_artifacts": "local session state only; never auto-pushed",
        }
        (state_root / "daily-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        metadata_commit = _export_session(
            workspace,
            state_root,
            tag=tag,
            best_experiment_id=best,
            best_commit=best_commit,
        )
        report["session_metadata_commit"] = metadata_commit
        if push_branch:
            workspace.push()
            report["branch_pushed"] = True
        (state_root / "daily-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return report
