import json
from scripts.vnext_cli import evolve


def test_evolve_init_and_status(tmp_path, capsys):
    assert evolve(["init", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "autoevolve" / "results.tsv").exists()
    assert evolve(["status", "--root", str(tmp_path)]) == 0
    assert "experiments" in capsys.readouterr().out


def test_evolve_rejects_protected_mutation(tmp_path, capsys):
    evolve(["init", "--root", str(tmp_path)])
    experiment = {
        "experiment_id": "E1",
        "session_id": "S",
        "parent_skill_revision": "r",
        "hypothesis": "h",
        "mutation_scope": ["safe"],
        "changed_files": ["schemas/x.json"],
    }
    baseline = {
        "eval_id": "B",
        "hard_gates_passed": True,
        "science_score": 1,
        "research_score": 1,
        "robustness": 1,
        "cost": 1,
        "latency": 1,
        "complexity": 1,
        "repeats": 3,
        "noise_floor": 0.05,
    }
    candidate = dict(baseline, eval_id="C", research_score=2)
    for name, obj in [("e.json", experiment), ("b.json", baseline), ("c.json", candidate)]:
        (tmp_path / name).write_text(json.dumps(obj), encoding="utf-8")
    assert evolve([
        "run",
        "--root",
        str(tmp_path),
        "--experiment",
        str(tmp_path / "e.json"),
        "--baseline-eval",
        str(tmp_path / "b.json"),
        "--candidate-eval",
        str(tmp_path / "c.json"),
    ]) == 0
    assert "INVALID" in capsys.readouterr().out
