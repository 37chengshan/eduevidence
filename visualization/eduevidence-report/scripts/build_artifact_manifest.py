#!/usr/bin/env python3
"""build_artifact_manifest.py — HTML-03 Artifact Manifest generator.

Validates that every HTML under --html-dir embeds the same result.json SHA-256
(matching the actual result files) and writes artifact_manifest.json:

    examples/ai-coding-assistant/artifact_manifest.json
    {
      "result_sha256": "...", "result_zh_sha256": "...",
      "renderer_version": "1.0.0", "git_commit": "...",
      "evidence_count": 13, "source_count": 7,
      "themes": ["claude", "academic", "datalab", "datalab-dark", "presentation"]
    }

Usage:
    python3 visualization/eduevidence-report/scripts/build_artifact_manifest.py \
        --result examples/ai-coding-assistant/result.json \
        --result-zh examples/ai-coding-assistant/result.zh.json \
        --html-dir examples/ai-coding-assistant/reports-5themes \
        --out examples/ai-coding-assistant/artifact_manifest.json
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from build_report import RENDERER_VERSION, THEME_NAMES, write_artifact_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate HTML-03 artifact manifest")
    parser.add_argument("--result", required=True)
    parser.add_argument("--result-zh", required=True)
    parser.add_argument("--html-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--renderer-version", default=RENDERER_VERSION)
    parser.add_argument("--git-commit", default="")
    args = parser.parse_args()

    html_dir = Path(args.html_dir)
    html_paths = sorted(
        p for p in html_dir.glob("EduEvidence_Report_*.html")
        if any(p.name.endswith(f"_{t}.html") for t in THEME_NAMES))
    if len(html_paths) != len(THEME_NAMES):
        print(f"ERROR: expected {len(THEME_NAMES)} theme HTMLs in {html_dir}, found {len(html_paths)}")
        return 2
    commit = args.git_commit or git_commit()
    manifest = write_artifact_manifest(Path(args.result), Path(args.result_zh), html_paths,
                                       args.renderer_version, commit, Path(args.out))
    print(f"wrote {args.out}: result={manifest['result_sha256'][:12]}… "
          f"evidence={manifest['evidence_count']} sources={manifest['source_count']} "
          f"themes={len(manifest['themes'])} commit={commit or '(none)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
