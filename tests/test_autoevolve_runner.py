import json
import os
import subprocess
from pathlib import Path

from engine.autoevolve import DailyEvolutionRunner, DailyProfile, ExperimentLog
from engine.autoevolve.agent_view import AgentMutationView


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def init_repo(root: Path):
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    (root / "skill" / "workflows").mkdir(parents=True)
    (root / "skill" / "workflows" / "a.md").write_text("baseline\n", encoding="utf-8")
    auto = root / "autoevolve"
    auto.mkdir()
    (auto / "protected.manifest.yaml").write_text(
        "protected:\n"
        "  - benchmarks/holdout/**\n"
        "  - benchmarks/evaluator/**\n"
        "  - schemas/**\n"
        "mutable:\n"
        "  safe:\n"
        "    - skill/workflows/**\n"
        "  controlled:\n"
        "    - engine/orchestration.py\n"
        "promotion: branch_only\n",
        encoding="utf-8",
    )
    (auto / "program.md").write_text("one change only\n", encoding="utf-8")
    (auto / "best.json").write_text('{"best_experiment_id": null}\n', encoding="utf-8")
    ExperimentLog(auto)

    benchmarks = root / "benchmarks"
    (benchmarks / "annotations").mkdir(parents=True)
    (benchmarks / "partitions.json").write_text(
        json.dumps({"dev": ["Q01"], "holdout": ["Q16"]}), encoding="utf-8"
    )
    (benchmarks / "questions.jsonl").write_text(
        json.dumps({"id": "Q01", "question": "dev"}) + "\n"
        + json.dumps({"id": "Q16", "question": "holdout"}) + "\n",
        encoding="utf-8",
    )
    (benchmarks / "annotations" / "gold-Q01.json").write_text('{"id":"Q01"}', encoding="utf-8")
    (benchmarks / "annotations" / "gold-Q16.json").write_text('{"id":"Q16"}', encoding="utf-8")

    (root / "agent.py").write_text(
        "import json, pathlib\n"
        "p=pathlib.Path('skill/workflows/a.md')\n"
        "p.write_text('improved\\n', encoding='utf-8')\n"
        "print(json.dumps({'hypothesis':'improve workflow','mutation_scope':['safe'],'cost_usd':0.1}))\n",
        encoding="utf-8",
    )
    (root / "eval.py").write_text(
        "import json, pathlib\n"
        "improved='improved' in pathlib.Path('skill/workflows/a.md').read_text()\n"
        "print(json.dumps({"
        "'eval_id':'candidate' if improved else 'baseline',"
        "'hard_gates_passed':True,'science_score':1,'research_score':2 if improved else 1,"
        "'robustness':1,'cost':0.1,'latency':1,'complexity':1,'repeats':3,'noise_floor':0.05,"
        "'dev_passed':True,'holdout_passed':True,'adversarial_passed':True,"
        "'holdout_isolation_verified':True,'eval_suite_hash':'suite-v1'}))\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)


def test_agent_mutation_view_hides_holdout_question_and_gold(tmp_path):
    init_repo(tmp_path)
    view = AgentMutationView.create(tmp_path)
    try:
        questions = (view.path / "benchmarks" / "questions.jsonl").read_text(encoding="utf-8")
        assert "Q01" in questions
        assert "Q16" not in questions
        assert (view.path / "benchmarks" / "annotations" / "gold-Q01.json").is_file()
        assert not (view.path / "benchmarks" / "annotations" / "gold-Q16.json").exists()
        assert not (view.path / ".git").exists()
    finally:
        view.cleanup()


def test_runner_keeps_candidate_without_mixing_live_session_log(tmp_path, monkeypatch):
    init_repo(tmp_path)
    state_base = tmp_path.parent / (tmp_path.name + "-state")
    monkeypatch.setenv("EDUEVIDENCE_AUTOEVOLVE_STATE_DIR", str(state_base))
    runner = DailyEvolutionRunner(
        tmp_path,
        profile=DailyProfile(max_experiments=1, max_cost_usd=5, max_wall_minutes=10),
    )
    report = runner.run(
        agent_command=f"{os.sys.executable} agent.py",
        eval_command=f"{os.sys.executable} eval.py",
        run_tag="keep-test",
    )
    assert report["statuses"] == ["KEEP"]
    worktree = tmp_path / ".autoevolve-worktrees" / "keep-test"
    assert (worktree / "skill" / "workflows" / "a.md").read_text() == "improved\n"
    run_dir = worktree / "autoevolve" / "runs" / "keep-test"
    assert (run_dir / "results.tsv").is_file()
    assert not (run_dir / "candidates").exists()
    assert "KEEP" in (worktree / "autoevolve" / "results.tsv").read_text()
    # The original main worktree remains untouched by branch-only evolution.
    assert (tmp_path / "skill" / "workflows" / "a.md").read_text() == "baseline\n"
    assert git(worktree, "branch", "--show-current") == "autoresearch/keep-test"
