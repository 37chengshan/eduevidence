"""Evidence-grounded StudyDesign gate + persistence.

A StudyDesign may only be created from explicit KnowledgeGap entities that
exist in THIS project (same project_id) and were derived from the current
graph revision. The engine validates grounding and stores designs; it does
not itself claim ethics approval — human-subject flags are surfaced, and
institutional review remains the institution's decision.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.project import ProjectWorkspace


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_design_grounding(project: ProjectWorkspace, design: dict) -> list[str]:
    """Validate that the design references real, project-local GAP ids.

    Returns a list of error strings (empty == valid).
    """
    errors: list[str] = []
    schema_errors = validate_record("study-design", design)
    if schema_errors:
        errors.extend(schema_errors)
        return errors

    gap_ids = design.get("gap_ids", [])
    if not gap_ids:
        errors.append("gap_ids must be non-empty: no new study design without "
                      "evidence grounding")
        return errors

    # load this project's gaps (all revisions; the gap file records revision)
    gaps_dir = project.path / "gaps"
    known_gap_ids: set[str] = set()
    if gaps_dir.is_dir():
        for f in sorted(gaps_dir.glob("gaps-rev-*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    known_gap_ids.add(rec["gap_id"])
                    # gap must be derived from the current graph revision
                    if rec["gap_id"] in gap_ids and rec.get(
                            "derived_from_graph_revision") != project.current_revision():
                        errors.append(
                            f"gap {rec['gap_id']} derives from revision "
                            f"{rec.get('derived_from_graph_revision')} but the "
                            f"project is at revision {project.current_revision()}")
    missing = [g for g in gap_ids if g not in known_gap_ids]
    if missing:
        errors.append(f"design references unknown gaps: {missing}")
    return errors


def save_study_design(project: ProjectWorkspace, design: dict) -> Path:
    """Persist a StudyDesign under study-designs/ (never rewritten)."""
    errors = validate_design_grounding(project, design)
    if errors:
        raise ValueError("design fails grounding gate:\n- " + "\n- ".join(errors))
    path = project.path / "study-designs" / f"{design['design_id']}.json"
    if path.exists():
        raise FileExistsError(f"study design already exists: {path}")
    path.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path


def save_analysis_plan(project: ProjectWorkspace, plan: dict) -> Path:
    """Persist an AnalysisPlan under study-designs/ (or analyses/)."""
    errors = validate_record("analysis-plan", plan)
    if errors:
        raise ValueError(f"invalid analysis plan: {errors}")
    path = project.path / "analyses" / f"{plan['analysis_plan_id']}.json"
    if path.exists():
        raise FileExistsError(f"analysis plan already exists: {path}")
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
