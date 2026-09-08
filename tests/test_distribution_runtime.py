"""Exercise installed resources, not just imports from the source checkout."""
from pathlib import Path
import os
import subprocess
import sys

from scripts.skill_payload import copy_payload, payload_files

ROOT = Path(__file__).resolve().parents[1]


def test_payload_excludes_private_state_and_legacy_ui(tmp_path):
    for relative in (
        "engine/good.py", "engine/__pycache__/bad.pyc", "autoevolve/runs/private.json",
        "autoevolve/best.json", "web/js/main.js", "web/studio/index.html",
        "docs/competition-brief.md", "benchmarks/results/private.json",
        "benchmarks/evidence-library.json", "examples/ai-coding-assistant-evidence/result.json",
        "examples/ai-coding-assistant-evidence/private.txt",
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    (tmp_path / "engine" / "leak.py").symlink_to(tmp_path / "docs" / "competition-brief.md")
    assert set(payload_files(tmp_path)) == {
        "engine/good.py", "web/studio/index.html", "benchmarks/evidence-library.json",
        "examples/ai-coding-assistant-evidence/result.json",
    }


def test_flat_skill_runs_without_repository(tmp_path):
    payload = tmp_path / "skill"
    copy_payload(ROOT, payload)
    environment = {**os.environ, "PYTHONPATH": str(payload), "EDUEVIDENCE_HOME": str(tmp_path / "research")}
    probe = """
from engine._resources import resource_root
from engine.contracts import load_schema
from engine.evidencecore import load_domain
from engine.research_service import ResearchService
from engine.meta_synthesis import _SYNTHESIS_SCHEMA
from scripts.dashboard_server import WEB_DIR, StudioReader, EXAMPLES_DIR, RESEARCH_HOME
import os
assert load_schema('project')
assert load_domain('education')
assert load_domain('policy')
assert _SYNTHESIS_SCHEMA.is_file()
assert (WEB_DIR / 'studio/index.html').is_file()
assert StudioReader(EXAMPLES_DIR, RESEARCH_HOME).catalog()['projects']
from pathlib import Path
project = ResearchService(Path(os.environ['EDUEVIDENCE_HOME'])).create_project(question='Synthetic distribution smoke', title='Synthetic fixture')
assert project.project_id
assert (resource_root() / 'skill/workflows/evidence-review.md').is_file()
assert not (resource_root() / 'benchmarks/annotations').exists()
print('isolated runtime OK')
"""
    result = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path,
                            env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    for args in (["--help"], ["research", "auto", "--help"], ["evolve", "--help"]):
        result = subprocess.run([sys.executable, str(payload / "eduevidence_cli.py"), *args],
                                cwd=tmp_path, env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
