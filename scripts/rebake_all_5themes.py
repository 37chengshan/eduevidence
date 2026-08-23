#!/usr/bin/env python3
"""scripts/rebake_all_5themes.py — Re-bake all 5 themes for all 3 projects with Lieflat figures and human language.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROJECTS = [
    "examples/highschool-math-ai-tutor",
    "examples/esl-academic-writing-ai",
    "examples/ai-coding-assistant-50"
]

THEMES = ["claude", "academic", "datalab", "datalab-dark", "presentation"]


def rebake():
    for proj in PROJECTS:
        p_dir = ROOT / proj
        r_en = p_dir / "result.json"
        r_zh = p_dir / "result.zh.json"
        out_html = p_dir / "EduEvidence_Report.html"
        themes_dir = p_dir / "reports-5themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n==========================================")
        print(f"Re-baking project: {proj}")
        print(f"==========================================")
        
        # 1. Main report (default claude theme)
        cmd = [
            sys.executable,
            str(ROOT / "visualization/eduevidence-report/scripts/build_report.py"),
            "--result", str(r_en),
            "--result-zh", str(r_zh),
            "--out", str(out_html)
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print(f"Main report: code={res.returncode}")
        if res.returncode != 0:
            print("STDERR:", res.stderr)
            sys.exit(1)
            
        # 2. 5 theme reports
        for t in THEMES:
            t_out = themes_dir / f"report_{t}.html"
            t_cmd = [
                sys.executable,
                str(ROOT / "visualization/eduevidence-report/scripts/build_report.py"),
                "--result", str(r_en),
                "--result-zh", str(r_zh),
                "--theme", t,
                "--out", str(t_out)
            ]
            t_res = subprocess.run(t_cmd, capture_output=True, text=True)
            print(f"  Theme {t:15s} -> {t_out.name} (code={t_res.returncode})")
            if t_res.returncode != 0:
                print("  STDERR:", t_res.stderr)
                sys.exit(1)
            # Also copy to EduEvidence_Report_{t}.html for compatibility
            compat_out = themes_dir / f"EduEvidence_Report_{t}.html"
            compat_out.write_bytes(t_out.read_bytes())

        # 3. Artifact manifest (HTML-03): all 5 theme HTMLs must embed the same
        #    result.json hash; refresh artifact_manifest.json after the bake.
        manifest_cmd = [
            sys.executable,
            str(ROOT / "visualization/eduevidence-report/scripts/build_artifact_manifest.py"),
            "--result", str(r_en),
            "--result-zh", str(r_zh),
            "--html-dir", str(themes_dir),
            "--out", str(p_dir / "artifact_manifest.json"),
        ]
        m_res = subprocess.run(manifest_cmd, capture_output=True, text=True)
        print(f"Manifest: code={m_res.returncode} {m_res.stdout.strip()}")
        if m_res.returncode != 0:
            print("STDERR:", m_res.stderr)
            sys.exit(1)

    print("\nAll 3 projects (15 theme reports) successfully re-baked with Lieflat Charts!")


if __name__ == "__main__":
    rebake()
