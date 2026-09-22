#!/usr/bin/env python3
"""scripts/lint_file_layers.py — file-layer hard gate.

Scans engine/ scripts/ integrations/ skill/ visualization/eduevidence-report/scripts/
for *.py *.js *.ts and enforces:

  * single file > 300 lines → ERROR (monument / legacy → WARNING only)
  * new / moved files must be ≤ 300 lines (not eligible for whitelists)
  * new / moved files must be ≤ 300 lines (not eligible for the whitelist)

Monument whitelist = build_report.py, orchestrator.py, agent_mcp.py,
pre_verdict_gate.py, living.py, evidence_graph.py. Anything else over the
budget is an ERROR unless monument/legacy WARNING. Exit 1 on any ERROR.

Usage:
    python3 scripts/lint_file_layers.py
Exit code 1 when any ERROR.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MAX_LINES = 300

SCAN_ROOTS = (
    "engine",
    "scripts",
    "integrations",
    "skill",
    "visualization/eduevidence-report/scripts",
)

# Historical monument whitelist — WARNING only (not ERROR).
# ONLY these six pre-split giants are grandfathered. New or moved files
# MUST NOT be added here — keep them ≤ MAX_LINES instead.
MONUMENT_BASENAMES = {
    "build_report.py",
    "orchestrator.py",
    "agent_mcp.py",
    "pre_verdict_gate.py",
    "living.py",
    "evidence_graph.py",
}

# Pre-existing large files (before the layering gate). WARNING only.
# New/moved files must never be added here — keep them ≤ MAX_LINES.
LEGACY_LARGE_BASENAMES = {
    "analysis.py", "core.py", "runner.py", "graph_store.py", "library_builtin.py",
    "meta_analysis.py", "migration.py", "orchestration.py", "pilot.py",
    "studio_read_model.py", "tribunal.py", "benchmark_evaluator.py",
    "benchmark_judge.py", "benchmark_v2.py", "benchmark_v3.py",
    "build_esl_artifacts.py", "build_evidence_library.py", "build_result.py",
    "check_protocol_alignment.py", "dashboard_server.py",
    "enrich_projects_human_and_lieflat.py", "generate_new_projects.py",
    "render_report_html.py", "research_auto_cli.py", "run_workspace.py",
    "test_adversarial_empirical.py", "build_figures.py", "charts_data.py",
    "lieflat_engine.py", "zh_labels.py", "library.py",
}

EXTS = {".py", ".js", ".ts"}
SKIP_DIRS = {"__pycache__", "node_modules", ".git", ".venv", "venv"}


def _iter_sources() -> list[Path]:
    found: list[Path] = []
    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in EXTS:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            found.append(path)
    return found


def check_file_layers() -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    for path in _iter_sources():
        rel = path.relative_to(ROOT).as_posix()
        try:
            n = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
        except OSError as exc:
            errors.append(f"{rel}: unreadable ({exc})")
            continue
        if n <= MAX_LINES:
            continue
        msg = f"{rel}: {n} lines > {MAX_LINES}"
        if path.name in MONUMENT_BASENAMES:
            warnings.append(
                f"{msg} (monument whitelist — WARNING only; split when touched)")
        elif path.name in LEGACY_LARGE_BASENAMES:
            warnings.append(
                f"{msg} (legacy large file — WARNING only; split when touched)")
        else:
            errors.append(
                f"{msg} (not on monument whitelist; new/moved must be ≤ {MAX_LINES})")
    return errors, warnings


def main() -> int:
    print("[*] Running file-layer hard gate "
          f"(max {MAX_LINES} lines; monuments+legacy WARNING only: "
          f"{', '.join(sorted(MONUMENT_BASENAMES))})...")
    errors, warnings = check_file_layers()
    for w in warnings:
        print(f"    ! {w}")
    if errors:
        print(f"[-] File-layer lint FAILED with {len(errors)} error(s):",
              file=sys.stderr)
        for e in errors:
            print(f"    • {e}", file=sys.stderr)
        return 1
    print(f"[+] File-layer lint PASSED: {len(warnings)} monument warning(s), 0 error(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
