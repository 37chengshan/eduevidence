from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from research_auto_cli import research_auto
except ImportError:  # imported as scripts.vnext_cli in tests/package contexts
    from scripts.research_auto_cli import research_auto


def _read_json(path, default=None):
    if not path:
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
        rows = (
            (root / "results.tsv").read_text(encoding="utf-8").splitlines()[1:]
            if (root / "results.tsv").exists()
            else []
        )
        best = _read_json(root / "best.json", {}) or {}
        statuses = [row.split("\t")[-2] for row in rows if "\t" in row]
        print(
            json.dumps(
                {
                    "experiments": len(rows),
                    "best": best,
                    "plateau": PlateauTracker().plateau(statuses),
                },
                indent=2,
            )
        )
        return 0
    if args.action == "best":
        print(json.dumps(_read_json(root / "best.json", {}), indent=2))
        return 0
    if args.action == "baseline":
        data = _read_json(args.eval)
        (root / "baseline.json").write_text(
            json.dumps(data, indent=2) + "\n", encoding="utf-8"
        )
        print(data.get("eval_id", "baseline"))
        return 0
    if args.action == "run":
        experiment = SkillExperiment(**_read_json(args.experiment))
        baseline = EvalSnapshot(**_read_json(args.baseline_eval))
        candidate = EvalSnapshot(**_read_json(args.candidate_eval))
        manifest = ProtectedManifest.from_repo(repo)
        ok, bad = manifest.validate_changes(experiment.changed_files)
        scope_ok, scope_bad = manifest.validate_mutation_scope(
            experiment.changed_files,
            mutation_tiers=experiment.mutation_scope,
            allow_controlled="controlled" in experiment.mutation_scope,
        )
        if not ok:
            status, reason = "INVALID", "protected mutation: " + ",".join(bad)
        elif not scope_ok:
            status, reason = "INVALID", "mutation outside approved tier: " + ",".join(scope_bad)
        else:
            status, reason = promote(baseline, candidate)
        experiment.status = status
        experiment.promotion_reason = reason
        ExperimentLog(root).append(experiment, candidate=candidate, description=reason)
        if status == "KEEP":
            (root / "best.json").write_text(
                json.dumps(
                    {
                        "best_experiment_id": experiment.experiment_id,
                        "candidate_commit": experiment.candidate_commit,
                        "eval_id": candidate.eval_id,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        print(json.dumps({"status": status, "reason": reason}, indent=2))
        return 0
    if args.action == "prepare-pr":
        best = _read_json(root / "best.json", {}) or {}
        print(
            json.dumps(
                {
                    "promotion": "branch_only",
                    "best": best,
                    "note": "Human approval is required to open/merge the final PR.",
                },
                indent=2,
            )
        )
        return 0
    return 2
