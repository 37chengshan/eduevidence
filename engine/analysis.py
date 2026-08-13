"""AnalysisPlan/AnalysisRun + Native Core descriptive analysis.

Native Core (stdlib only — no scipy/pandas/statsmodels) supports
deterministic: row/column/type profile, missingness, group counts,
mean/median/min/max, explicit pre/post descriptive difference, explicit
between-group descriptive difference. Advanced analysis (regression,
multilevel, meta-analysis, thematic analysis) is capability-discovered; an
unavailable capability returns `ANALYSIS_CAPABILITY_UNAVAILABLE` and never
fabricates p-values. Advanced results enter only through
`record_external_analysis()` with explicit provider/software provenance.
"""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.datasets import analysis_blocked_by_privacy
from engine.ids import new_local_id
from engine.project import ProjectWorkspace


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AnalysisCapabilityResult:
    status: str
    capability_id: str
    output: dict
    warnings: tuple[str, ...]


NATIVE_CAPABILITIES = frozenset({
    "row_column_type_profile", "missingness", "group_counts",
    "descriptive_statistics", "pre_post_descriptive_difference",
    "between_group_descriptive_difference",
})

ADVANCED_CAPABILITIES = frozenset({
    "regression", "multilevel_analysis", "meta_analysis",
    "qualitative_thematic_analysis", "structural_equation_modeling",
})


def _load_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def _num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_analysis_plan(project: ProjectWorkspace, plan: dict) -> list[str]:
    errors = validate_record("analysis-plan", plan)
    return errors


def run_native_descriptive(project: ProjectWorkspace, plan: dict) -> dict:
    """Run deterministic Native Core descriptive analyses for the plan.

    `plan` carries dataset_ids + primary_analysis; analysis_requirements
    from the design select which native capabilities run. Returns an
    AnalysisRun record (status completed or capability_unavailable).
    """
    # privacy gate: block on required-but-undone deidentification
    from engine.datasets import ingest_dataset  # noqa: F401  (registry use)
    manifests = {}
    for dsid in plan.get("dataset_ids", []):
        manifest = project.path / "datasets" / "raw" / dsid / "manifest.json"
        if not manifest.is_file():
            return {
                "analysis_run_id": new_local_id("ANL", set()),
                "analysis_plan_id": plan["analysis_plan_id"],
                "dataset_ids": plan.get("dataset_ids", []),
                "status": "failed",
                "outputs": {"error": f"dataset {dsid} not found in project"},
                "assumption_checks": [],
                "created_at": _now_iso(),
                "extensions": {},
            }
        asset = json.loads(manifest.read_text(encoding="utf-8"))
        reasons = analysis_blocked_by_privacy(asset)
        if reasons:
            return {
                "analysis_run_id": new_local_id("ANL", set()),
                "analysis_plan_id": plan["analysis_plan_id"],
                "dataset_ids": plan.get("dataset_ids", []),
                "status": "failed",
                "outputs": {"privacy_block": reasons},
                "assumption_checks": [],
                "created_at": _now_iso(),
                "extensions": {},
            }
        manifests[dsid] = asset

    outputs: dict = {}
    warnings: list[str] = []
    for dsid, asset in manifests.items():
        path = Path(asset["path"])
        cols, rows = _load_rows(path)

        # type profile
        types: dict[str, str] = {}
        numeric_cols: dict[str, list[float]] = {c: [] for c in cols}
        for row in rows:
            for idx, c in enumerate(cols):
                if idx < len(row):
                    v = row[idx].strip()
                    if v == "":
                        continue
                    if _num(v) is not None:
                        types.setdefault(c, "number")
                        numeric_cols[c].append(_num(v))
                    else:
                        types[c] = "string"
        missing = {
            c: sum(1 for row in rows if len(row) <= idx or row[idx].strip() == "")
            for idx, c in enumerate(cols)
        }

        # group counts (all columns with <= 10 distinct values)
        group_counts: dict[str, dict] = {}
        for idx, c in enumerate(cols):
            counts: dict[str, int] = {}
            for row in rows:
                if idx < len(row) and row[idx].strip():
                    counts[row[idx].strip()] = counts.get(row[idx].strip(), 0) + 1
            if 0 < len(counts) <= 10:
                group_counts[c] = counts

        # descriptive statistics
        desc: dict[str, dict] = {}
        for c, vals in numeric_cols.items():
            if vals:
                desc[c] = {
                    "count": len(vals),
                    "mean": round(statistics.fmean(vals), 4),
                    "median": statistics.median(vals),
                    "min": min(vals),
                    "max": max(vals),
                }

        outputs[dsid] = {
            "columns": cols,
            "row_count": len(rows),
            "types": types,
            "missingness": missing,
            "group_counts": group_counts,
            "descriptive_statistics": desc,
        }

    # explicit pre/post descriptive difference (same dataset, mapped columns)
    pre_post = (plan.get("extensions") or {}).get("pre_post_mapping")
    if pre_post:
        dsid = pre_post.get("dataset_id")
        if dsid in outputs:
            pre_col = pre_post["pre_column"]
            post_col = pre_post["post_column"]
            pre_vals = outputs[dsid]["descriptive_statistics"].get(pre_col, {})
            post_vals = outputs[dsid]["descriptive_statistics"].get(post_col, {})
            if pre_vals and post_vals:
                outputs[dsid]["pre_post_descriptive_difference"] = {
                    "pre_mean": pre_vals["mean"],
                    "post_mean": post_vals["mean"],
                    "mean_difference": round(post_vals["mean"] - pre_vals["mean"], 4),
                    "note": "descriptive only; no p-value inferred",
                }

    # explicit between-group descriptive difference
    between = (plan.get("extensions") or {}).get("between_group_mapping")
    if between:
        dsid = between.get("dataset_id")
        if dsid in outputs:
            group_col = between["group_column"]
            value_col = between["value_column"]
            path = Path(manifests[dsid]["path"])
            cols2, rows2 = _load_rows(path)
            if group_col in cols2 and value_col in cols2:
                gi = cols2.index(group_col)
                vi = cols2.index(value_col)
                groups: dict[str, list[float]] = {}
                for row in rows2:
                    if gi < len(row) and vi < len(row):
                        v = _num(row[vi])
                        g = row[gi].strip()
                        if v is not None and g:
                            groups.setdefault(g, []).append(v)
                means = {g: round(statistics.fmean(vs), 4) for g, vs in groups.items() if vs}
                outputs[dsid]["between_group_descriptive_difference"] = {
                    "group_means": means,
                    "note": "descriptive only; no p-value inferred",
                }

    if warnings:
        outputs["warnings"] = list(warnings)

    run = {
        "analysis_run_id": new_local_id("ANL", set()),
        "analysis_plan_id": plan["analysis_plan_id"],
        "dataset_ids": plan.get("dataset_ids", []),
        "status": "completed",
        "outputs": outputs,
        "assumption_checks": [],
        "created_at": _now_iso(),
        "extensions": {"engine": "native_core", "capabilities": sorted(NATIVE_CAPABILITIES)},
    }
    errors = validate_record("analysis-run", run)
    if errors:
        raise ValueError(f"invalid analysis run: {errors}")
    return run


def record_external_analysis(project: ProjectWorkspace, *, plan: dict,
                             provider: str, software: dict,
                             outputs: dict, assumption_checks: list[dict],
                             status: str) -> dict:
    """Record an analysis produced by a discovered external capability."""
    run = {
        "analysis_run_id": new_local_id("ANL", set()),
        "analysis_plan_id": plan["analysis_plan_id"],
        "dataset_ids": plan.get("dataset_ids", []),
        "status": "completed" if status == "completed" else "failed",
        "outputs": outputs,
        "assumption_checks": assumption_checks,
        "created_at": _now_iso(),
        "extensions": {
            "provider": provider,
            "software": software,
            "external": True,
        },
    }
    errors = validate_record("analysis-run", run)
    if errors:
        raise ValueError(f"invalid external analysis run: {errors}")
    return run


def save_analysis_run(project: ProjectWorkspace, run: dict) -> Path:
    """Persist an AnalysisRun under analyses/ (atomic; never rewritten)."""
    errors = validate_record("analysis-run", run)
    if errors:
        raise ValueError(f"invalid analysis run: {errors}")
    path = project.path / "analyses" / f"{run['analysis_run_id']}.json"
    if path.exists():
        raise FileExistsError(f"analysis run already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(__import__("json").dumps(run, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def mark_analysis_validated(project: ProjectWorkspace, run_id: str) -> dict:
    """Promote a persisted AnalysisRun to `validated`.

    `validated` is the ONLY status that closes the Full Research Cycle gate
    in engine/update.py (ANALYSIS_INVALID otherwise). A human or automated
    review gate calls this after checking the run's outputs.
    """
    path = project.path / "analyses" / f"{run_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"analysis run {run_id} not persisted under {path}")
    run = json.loads(path.read_text(encoding="utf-8"))
    if run.get("status") not in ("completed", "validated"):
        raise ValueError(
            f"cannot validate analysis run {run_id} with status "
            f"{run.get('status')!r}; only completed runs may be validated"
        )
    run["status"] = "validated"
    errors = validate_record("analysis-run", run)
    if errors:
        raise ValueError(f"invalid validated run: {errors}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return run


def capability_unavailable(capability_id: str, plan: dict) -> AnalysisCapabilityResult:
    """Honest degradation for undiscovered advanced capabilities."""
    return AnalysisCapabilityResult(
        status="ANALYSIS_CAPABILITY_UNAVAILABLE",
        capability_id=capability_id,
        output={},
        warnings=(
            f"capability {capability_id!r} not discovered; no p-values or "
            f"effect estimates were fabricated",
        ),
    )
