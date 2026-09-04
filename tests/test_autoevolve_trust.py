from __future__ import annotations

import json
from pathlib import Path

import engine.autoevolve.trust as trust
from engine.autoevolve.runner import _trusted_eval_snapshot


def _seed_suite(root: Path) -> None:
    (root / "benchmarks" / "evaluator").mkdir(parents=True)
    (root / "benchmarks" / "holdout").mkdir(parents=True)
    (root / "benchmarks" / "adversarial").mkdir(parents=True)
    (root / "benchmarks" / "annotations").mkdir(parents=True)
    (root / "references").mkdir(parents=True)
    (root / "benchmarks" / "evaluator" / "score.py").write_text("score = 1\n", encoding="utf-8")
    (root / "benchmarks" / "holdout" / "q.json").write_text('{"id":"H1"}\n', encoding="utf-8")
    (root / "benchmarks" / "adversarial" / "a.json").write_text('{"id":"A1"}\n', encoding="utf-8")
    (root / "benchmarks" / "annotations" / "gold-H1.json").write_text('{"gold":1}\n', encoding="utf-8")
    (root / "benchmarks" / "partitions.json").write_text(
        json.dumps({"dev": ["D1"], "holdout": ["H1"]}), encoding="utf-8"
    )
    (root / "benchmarks" / "questions.jsonl").write_text('{"id":"D1"}\n{"id":"H1"}\n', encoding="utf-8")
    (root / "references" / "scientific-invariants.md").write_text("invariant\n", encoding="utf-8")


def _payload(**overrides):
    value = {
        "eval_id": "E1",
        "hard_gates_passed": True,
        "science_score": 1.0,
        "research_score": 1.1,
        "robustness": 1.0,
        "cost": 0.1,
        "latency": 1.0,
        "complexity": 1.0,
        "repeats": 3,
        "noise_floor": 0.01,
        "dev_passed": True,
        "holdout_passed": True,
        "adversarial_passed": True,
        "holdout_isolation_verified": True,
        "eval_suite_hash": "evaluator-forged",
    }
    value.update(overrides)
    return value


def test_eval_suite_hash_is_runner_computed_and_sensitive_to_protected_inputs(tmp_path):
    _seed_suite(tmp_path)
    first = trust.compute_eval_suite_hash(tmp_path)
    (tmp_path / "skill").mkdir()
    (tmp_path / "skill" / "mutable.md").write_text("change\n", encoding="utf-8")
    assert trust.compute_eval_suite_hash(tmp_path) == first
    (tmp_path / "benchmarks" / "holdout" / "q.json").write_text('{"id":"H2"}\n', encoding="utf-8")
    assert trust.compute_eval_suite_hash(tmp_path) != first


def test_trusted_snapshot_ignores_evaluator_self_attestation():
    snap = _trusted_eval_snapshot(
        _payload(),
        suite_hash="runner-suite",
        isolation_verified=False,
    )
    assert snap.eval_suite_hash == "runner-suite"
    assert snap.holdout_isolation_verified is False


def test_container_isolation_requires_runner_runtime_and_image(monkeypatch):
    monkeypatch.setenv("EDUEVIDENCE_AUTOEVOLVE_ISOLATION", "container")
    monkeypatch.delenv("EDUEVIDENCE_AUTOEVOLVE_ISOLATION_IMAGE", raising=False)
    monkeypatch.setattr(trust.shutil, "which", lambda name: f"/usr/bin/{name}" if name == "docker" else None)
    assert trust.AgentIsolation.from_environment().verified is False

    monkeypatch.setenv("EDUEVIDENCE_AUTOEVOLVE_ISOLATION_IMAGE", "eduevidence-agent:locked")
    policy = trust.AgentIsolation.from_environment()
    assert policy.verified is True
    assert policy.runtime == "docker"


def test_container_wrapper_mounts_only_sanitized_view_and_remaps_paths(tmp_path):
    view = tmp_path / "view"
    (view / "autoevolve").mkdir(parents=True)
    policy = trust.AgentIsolation(
        mode="container",
        verified=True,
        runtime="docker",
        image="agent:locked",
        reason="test",
    )
    command, host_env = policy.wrap_command(
        "python agent.py",
        view,
        {
            "EDUEVIDENCE_PROGRAM": str(view / "autoevolve" / "program.md"),
            "SECRET_API_KEY": "must-not-forward",
        },
    )
    assert "--network none" in command
    assert "--read-only" in command
    assert f"src={view.resolve()},dst=/workspace,rw" in command
    assert "EDUEVIDENCE_PROGRAM=/workspace/autoevolve/program.md" in command
    assert "SECRET_API_KEY" not in command
    assert "SECRET_API_KEY" not in host_env
