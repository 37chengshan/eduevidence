"""Tests for the protocol five-way alignment gate.

The gate is the mechanical guarantee behind the repository's claim that a
scientific contract is declared once and referenced everywhere: stages,
briefs, roles, prompts, capabilities, sub-skills, workflows and packaging must
agree. These tests hold the gate itself honest (it must pass on the current
tree) and prove it actually catches drift (it must fail on injected drift).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT), str(ROOT / "scripts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import check_protocol_alignment as gate  # noqa: E402


def test_alignment_gate_passes_on_current_tree():
    assert gate.check() == []


def test_alignment_script_runs_as_a_process():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_protocol_alignment.py")],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Protocol alignment PASSED" in result.stdout


def test_every_scientific_stage_has_an_owning_role():
    from engine.workflows import execution_stages

    registry = gate._registry_roles()
    owned = {stage for entry in registry.values() for stage in entry.get("stages", [])}
    for stage in execution_stages():
        if stage == "projection":
            continue  # projection is outside the scientific stage model
        assert stage in owned, f"stage {stage!r} has no owning role"


def test_role_prompts_never_bind_a_model_or_cli():
    for role_file in sorted((ROOT / "skill" / "agents").glob("*.md")):
        fields = gate._frontmatter(role_file)
        assert "default_model" not in fields, role_file.name
        assert "default_cli" not in fields, role_file.name
        assert not any(token in fields.get("recommended_reasoning", "")
                       for token in ("claude-", "gpt-", "deepseek-", "glm-", "kimi-"))


def test_independence_is_graded_not_boolean():
    registry = gate._registry_roles()
    assert registry["skeptic"]["independence_required"] == "different-model-family"
    assert registry["method-reviewer"]["independence_required"] == "role-separation"


def test_packaging_version_matches_engine_version():
    from engine.versions import ENGINE_VERSION

    manifest = json.loads((ROOT / "packaging" / "scp-manifest.json").read_text(encoding="utf-8"))
    assert manifest["skill"]["version"] == ENGINE_VERSION


# --------------------------------------------------------------- drift probes


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """A throwaway repository copy so drift can be injected safely."""
    copy = tmp_path / "repo"
    shutil.copytree(
        ROOT, copy,
        ignore=shutil.ignore_patterns(
            ".git", ".venv", "__pycache__", "node_modules", "dist", "dist_gh_pages",
            "runs", "*.pyc", ".pytest_cache", ".ruff_cache",
        ),
    )
    monkeypatch.setattr(gate, "ROOT", copy)
    return copy


def test_gate_catches_a_missing_task_brief(sandbox):
    (sandbox / "skill" / "task-briefs" / "audit.md").unlink()
    errors = gate.check()
    assert any("audit" in error and "task brief" in error for error in errors)


def test_gate_catches_a_role_prompt_that_binds_a_model(sandbox):
    path = sandbox / "skill" / "agents" / "skeptic.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("role_id: skeptic",
                                 "role_id: skeptic" + chr(10) + "default_model: some-model"),
                    encoding="utf-8")
    errors = gate.check()
    assert any("default_model" in error for error in errors)


def test_gate_catches_registry_capability_drift(sandbox):
    path = sandbox / "skill" / "roles" / "registry.yaml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("capabilities: [methodology_appraisal]",
                                 "capabilities: [methodology-audit]"), encoding="utf-8")
    errors = gate.check()
    assert any("methodology-audit" in error for error in errors)


def test_gate_catches_packaging_version_drift(sandbox):
    from engine.versions import ENGINE_VERSION

    path = sandbox / "packaging" / "scp-manifest.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(f'"version": "{ENGINE_VERSION}"', '"version": "0.0.1"'),
                    encoding="utf-8")
    errors = gate.check()
    assert any("skill.version" in error for error in errors)


def test_gate_catches_a_missing_workflow_runbook(sandbox):
    (sandbox / "skill" / "workflows" / "evidence-review.md").unlink()
    errors = gate.check()
    assert any("evidence-review" in error for error in errors)


def test_gate_catches_a_stale_doc_metric(sandbox):
    path = sandbox / "docs" / "install-guide.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text + chr(10) + "752 个测试" + chr(10), encoding="utf-8")
    errors = gate.check()
    assert any("stale test count" in error for error in errors)

