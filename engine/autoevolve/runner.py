from __future__ import annotations
import json
import os
import shlex
import subprocess
from datetime import datetime, timezone
from pathlib import Path
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
        argv, cwd=cwd, check=True, text=True, capture_output=True, env=env
    )
    return json.loads(completed.stdout)


class DailyEvolutionRunner:
    """Run branch-only autoresearch against an external, pre-authorized agent.

    The runner never chooses or authorizes a model. Agent and evaluator commands
    are explicit inputs. Commands run without a shell, and the runner never
    merges, pushes, releases or deploys.
    """

    def __init__(self, repo: str | Path, *, profile: DailyProfile | None = None):
        self.repo = Path(repo).resolve()
        self.profile = profile or DailyProfile()
        self.profile.validate()

    def run(self, *, agent_command: str, eval_command: str, run_tag: str | None = None) -> dict:
        tag = run_tag or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        workspace = GitWorkspace.create(self.repo, tag)
        log = ExperimentLog(workspace.path / "autoevolve")
        manifest = ProtectedManifest()
        plateau = PlateauTracker()
        baseline = EvalSnapshot(**_run_json(eval_command, workspace.path))
        statuses: list[str] = []
        spent = 0.0
        best = None

        for index in range(1, self.profile.max_experiments + 1):
            if spent >= self.profile.max_cost_usd:
                break
            experiment_id = f"EXP-{index:04d}"
            env = os.environ.copy()
            env.update(
                {
                    "EDUEVIDENCE_EXPERIMENT_ID": experiment_id,
                    "EDUEVIDENCE_PROGRAM": str(workspace.path / "autoevolve" / "program.md"),
                }
            )
            candidate = None
            try:
                proposal = _run_json(agent_command, workspace.path, env)
                hypothesis = str(proposal["hypothesis"]).strip()
                if not hypothesis:
                    raise ValueError("empty hypothesis")
                changed = workspace.changed_files()
                ok, bad = manifest.validate_changes(changed)
                experiment = SkillExperiment(
                    experiment_id,
                    tag,
                    baseline.eval_id,
                    hypothesis,
                    tuple(proposal.get("mutation_scope") or ["safe"]),
                    changed_files=changed,
                )
                if not changed:
                    status, reason = "REJECT", "agent made no change"
                elif not ok:
                    status, reason = "INVALID", "protected mutation: " + ",".join(bad)
                else:
                    candidate = EvalSnapshot(**_run_json(eval_command, workspace.path))
                    spent += candidate.cost
                    status, reason = promote(baseline, candidate)
                    experiment.candidate_eval_id = candidate.eval_id
                experiment.status = status
                experiment.promotion_reason = reason
                if status == "KEEP":
                    experiment.candidate_commit = workspace.commit(
                        f"experiment: {experiment_id} {hypothesis[:72]}"
                    )
                    baseline = candidate
                    best = experiment_id
                else:
                    workspace.restore()
                log.append(experiment, candidate=candidate, description=reason)
                statuses.append(status)
            except Exception as exc:
                workspace.restore()
                experiment = SkillExperiment(
                    experiment_id,
                    tag,
                    baseline.eval_id,
                    "invalid-or-crashed",
                    ("safe",),
                    status="CRASH",
                    promotion_reason=str(exc),
                )
                log.append(experiment, description=str(exc))
                statuses.append("CRASH")
            if plateau.plateau(statuses):
                break

        report = {
            "run_tag": tag,
            "branch": workspace.branch,
            "worktree": str(workspace.path),
            "experiments": len(statuses),
            "statuses": statuses,
            "best_experiment_id": best,
            "cost": spent,
            "plateau": plateau.plateau(statuses),
            "promotion": "branch_only",
        }
        (workspace.path / "autoevolve" / "daily-report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        return report
