"""Release smoke test for the public ai-coding-assistant HTML demo."""
import sys
from pathlib import Path

import build_report as br

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "ai-coding-assistant"


def test_public_demo_generator_smoke_uses_current_report_contract(tmp_path, monkeypatch):
    out = tmp_path / "EduEvidence_Report.html"
    spec_out = tmp_path / "report_spec.json"
    argv = [
        "build_report.py",
        "--result", str(DEMO / "result.json"),
        "--result-zh", str(DEMO / "result.zh.json"),
        "--out", str(out),
        "--spec-out", str(spec_out),
        "--theme", "claude",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    assert br.main() == 0
    html = out.read_text(encoding="utf-8")
    assert 'data-theme="claude"' in html
    assert 'data-theme="editorial"' not in html
    assert 'data-theme="datalab-dark"' in html
    assert 'data-report-page="brief"' in html
    assert 'data-report-page="full"' in html
    assert 'class="theme-switcher"' not in html
