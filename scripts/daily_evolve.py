from __future__ import annotations
import argparse
import json
from engine.autoevolve import DailyEvolutionRunner, DailyProfile


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run bounded branch-only EduEvidence evolution")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--agent-command", required=True)
    parser.add_argument("--eval-command", required=True)
    parser.add_argument("--run-tag")
    parser.add_argument("--max-experiments", type=int, default=20)
    parser.add_argument("--max-cost-usd", type=float, default=5)
    parser.add_argument("--max-wall-minutes", type=int, default=180)
    args = parser.parse_args(argv)
    profile = DailyProfile(args.max_experiments, args.max_cost_usd, args.max_wall_minutes)
    report = DailyEvolutionRunner(args.repo, profile=profile).run(
        agent_command=args.agent_command,
        eval_command=args.eval_command,
        run_tag=args.run_tag,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
