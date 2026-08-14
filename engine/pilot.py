"""engine/pilot.py - Decision-to-Outcome Loop (v3).

Closes the v2 Full Research Cycle: a PILOT DecisionSnapshot -> PilotRun
registration -> outcome data import (provenance-safe, PII-blocked) -> analysis
link -> graph revision with pilot evidence -> tribunal re-adjudication ->
new DecisionSnapshot + machine-readable diff.

Privacy discipline (matches engine/datasets.py): student data stays local,
PII columns (names / student ids / emails / phones) are refused at import.

Contracts: schemas/v3/pilot-outcome.schema.json for the pilot record;
graph entities follow schemas/v2/*.json (study/finding/evidence-link/source).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.datasets import analysis_blocked_by_privacy, derive_csv_profile, ingest_dataset
from engine.graph_store import GraphMutation, GraphStore
from engine.ids import new_local_id, new_run_id
from engine.project import ProjectWorkspace
from engine.synthesis import synthesize_project
from engine.tribunal import adjudicate, decision_diff, save_decision_snapshot
from engine.versions import (
    CONFIDENCE_POLICY_VERSION,
    METHODOLOGY_POLICY_VERSION,
    SOURCE_VALIDATION_POLICY_VERSION,
)

#: Outcome Taxonomy tokens that pilots may measure (mirrors outcome-taxonomy.md).
OUTCOME_TAXONOMY = {
    "knowledge_gain", "concept_understanding", "retention", "transfer",
    "independent_problem_solving", "completion_time", "accuracy",
    "code_quality", "assignment_score", "engagement", "motivation",
    "cognitive_load", "help_seeking", "metacognition", "ai_dependency",
    "over_reliance", "reduced_effort", "reduced_transfer",
    "academic_integrity_risk", "false_confidence",
}

PILOT_STATUSES = ("registered", "data_imported", "analyzed", "adjudicated")

#: Column names that reveal individuals; any match blocks pilot data import.
PII_COLUMN_HINTS = ("name", "student", "学号", "姓名", "email", "mail",
                    "phone", "手机", "电话", "id_card", "身份证", "address", "地址")

_DECISION_IMPLICATION = {"support": "support_adoption",
                         "contradict": "oppose_adoption", "neutral": "neutral"}

#: Outcome Taxonomy token -> graph outcome category enum (schemas/v2/outcome).
_OUTCOME_CATEGORY = {
    "knowledge_gain": "learning", "concept_understanding": "learning",
    "retention": "learning", "transfer": "learning",
    "independent_problem_solving": "learning",
    "completion_time": "task_performance", "accuracy": "task_performance",
    "code_quality": "task_performance", "assignment_score": "task_performance",
    "engagement": "process", "motivation": "process",
    "cognitive_load": "process", "help_seeking": "process",
    "metacognition": "process",
    "ai_dependency": "risk", "over_reliance": "risk",
    "reduced_effort": "risk", "reduced_transfer": "risk",
    "academic_integrity_risk": "risk", "false_confidence": "risk",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pilot_path(project: ProjectWorkspace, pilot_id: str) -> Path:
    return project.path / "pilots" / f"{pilot_id}.json"


def _load_pilot(project: ProjectWorkspace, pilot_id: str) -> dict:
    path = _pilot_path(project, pilot_id)
    if not path.is_file():
        raise FileNotFoundError(f"pilot not found: {pilot_id} (missing {path})")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_pilot(project: ProjectWorkspace, pilot: dict) -> Path:
    from scripts.validate_schema import SchemaError, validate  # noqa: PLC0415

    schema_path = (Path(__file__).resolve().parent.parent / "schemas" / "v3"
                   / "pilot-outcome.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        validate(pilot, schema)
    except SchemaError as exc:
        raise ValueError(f"invalid pilot record: {exc}") from exc
    path = _pilot_path(project, pilot["pilot_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(pilot, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(path)
    return path


def register_pilot(project: ProjectWorkspace, *,
                   decision_snapshot_id: str, title: str,
                   start_date: str, end_date: str,
                   conditions: list[str], sample_size: int, design_id: str,
                   anon_policy: dict, outcome_columns: list[str]) -> dict:
    """Register a PilotRun bound to an existing DecisionSnapshot."""
    decisions_dir = project.path / "decisions"
    if not (decisions_dir / f"{decision_snapshot_id}.json").is_file():
        raise ValueError(
            f"decision snapshot {decision_snapshot_id} not found in this project; "
            "a pilot must bind to a real adjudication")
    unknown = [o for o in outcome_columns if o not in OUTCOME_TAXONOMY]
    if unknown:
        raise ValueError(
            f"outcome_columns outside Outcome Taxonomy: {sorted(unknown)}")
    if not conditions or sample_size < 1:
        raise ValueError("conditions must be non-empty and sample_size >= 1")
    if anon_policy.get("no_pii_columns") is not True:
        raise ValueError("anon_policy.no_pii_columns must be true (student data stays local)")

    existing = {p.stem for p in (project.path / "pilots").glob("PIL-*.json")} \
        if (project.path / "pilots").is_dir() else set()
    pilot = {
        "pilot_id": new_local_id("PIL", existing),
        "project_id": project.project_id,
        "decision_snapshot_id": decision_snapshot_id,
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "conditions": list(conditions),
        "sample_size": int(sample_size),
        "design_id": design_id,
        "anon_policy": dict(anon_policy),
        "outcome_columns": list(outcome_columns),
        "dataset_asset_id": None,
        "analysis_run_id": None,
        "status": "registered",
        "redecide": None,
        "created_at": _now_iso(),
        "extensions": {},
    }
    _save_pilot(project, pilot)
    return pilot


def import_outcomes(project: ProjectWorkspace, pilot_id: str, *,
                    source_path: Path, privacy: dict,
                    variable_dictionary: dict[str, str] | None = None) -> dict:
    """Ingest pilot outcome data (CSV) with a PII column gate.

    Blocks: PII column names, missing outcome columns, and datasets whose
    deidentification requirements are unmet.
    """
    pilot = _load_pilot(project, pilot_id)
    if pilot["status"] not in ("registered", "data_imported"):
        raise ValueError(
            f"pilot {pilot_id} status {pilot['status']!r} cannot import outcomes")

    source_path = Path(source_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"outcome data missing: {source_path}")

    profile = derive_csv_profile(source_path)
    columns = list((profile.get("missingness") or {}).keys())
    lower = {str(c).strip().lower(): str(c).strip() for c in columns}

    blocked = [c for c in lower if any(hint in c for hint in PII_COLUMN_HINTS)]
    if blocked:
        raise ValueError(
            "PII columns detected and refused: " + ", ".join(sorted(blocked)) +
            "; deidentify the file before import")

    missing = [o for o in pilot["outcome_columns"]
               if o.lower() not in lower and o not in columns]
    if missing:
        raise ValueError(
            f"outcome column(s) missing from CSV: {missing}; available: {sorted(columns)}")

    asset = ingest_dataset(project, design_id=pilot["design_id"],
                           source_path=source_path, privacy=privacy,
                           variable_dictionary=variable_dictionary)
    privacy_reasons = analysis_blocked_by_privacy(asset)
    if privacy_reasons:
        raise ValueError("pilot data blocked from analysis:\n- " +
                         "\n- ".join(privacy_reasons))

    pilot["dataset_asset_id"] = asset["dataset_id"]
    pilot["status"] = "data_imported"
    _save_pilot(project, pilot)
    return asset


def link_analysis(project: ProjectWorkspace, pilot_id: str, *,
                  analysis_run_id: str) -> dict:
    """Link a completed analysis run to the pilot (status -> analyzed)."""
    pilot = _load_pilot(project, pilot_id)
    if pilot["status"] not in ("data_imported", "analyzed"):
        raise ValueError(
            f"pilot {pilot_id} must import data before linking an analysis")
    run_path = project.path / "analyses" / f"{analysis_run_id}.json"
    if not run_path.is_file():
        raise ValueError(f"analysis run not found: {analysis_run_id}")
    pilot["analysis_run_id"] = analysis_run_id
    pilot["status"] = "analyzed"
    _save_pilot(project, pilot)
    return pilot


def _ensure_outcome(store: GraphStore, outcome_id: str) -> dict:
    existing = store.get("outcomes", outcome_id)
    if existing:
        return existing
    token = outcome_id[len("OUT-"):]
    return {
        "outcome_id": outcome_id,
        "name": token,
        "outcome_type": _OUTCOME_CATEGORY.get(token, "learning"),
        "extensions": {"pilot_outcome": True},
    }


def redecide(project: ProjectWorkspace, pilot_id: str, *,
             claim_id: str, outcome_token: str, measure: str,
             effect_direction: str, raw_result_text: str,
             relation_to_claim: str, effect_estimate: dict | None = None,
             directness: int = 2, reasoning_note: str = "") -> dict:
    """Fold pilot outcome evidence into the graph and re-adjudicate.

    Creates (or reuses) a project-origin source + study for the pilot,
    upserts one finding + evidence link, commits a new graph revision,
    runs the tribunal and writes a new DecisionSnapshot with a diff against
    the decision the pilot was bound to.
    """
    if effect_direction not in ("positive", "negative", "null"):
        raise ValueError(f"invalid effect_direction {effect_direction!r}")
    if relation_to_claim not in ("support", "contradict", "neutral"):
        raise ValueError(f"invalid relation_to_claim {relation_to_claim!r}")
    if outcome_token not in OUTCOME_TAXONOMY:
        raise ValueError(
            f"outcome_token {outcome_token!r} outside Outcome Taxonomy")
    outcome_id = f"OUT-{outcome_token}"
    pilot = _load_pilot(project, pilot_id)
    if pilot["status"] not in ("analyzed", "data_imported"):
        raise ValueError(
            f"pilot {pilot_id} status {pilot['status']!r}; import data (and ideally "
            "link an analysis) before re-adjudication")
    # Idempotency guard (final review P1-3): a pilot that already produced a
    # new DecisionSnapshot must never be re-adjudicated — a retry after a
    # partial failure would silently duplicate pilot evidence in the graph.
    if pilot.get("redecide") is not None:
        raise ValueError(
            f"pilot {pilot_id} already adjudicated into "
            f"{pilot['redecide']['new_decision_snapshot_id']}; refusing re-entry "
            "(create a new pilot for a new cycle)")

    store = GraphStore(project)
    claims = {c["claim_id"]: c for c in store.read_table("claims")}
    if claim_id not in claims:
        raise ValueError(f"claim {claim_id} not found in project graph")

    source_id = new_local_id("SRC", {s["source_id"] for s in store.read_table("sources")})
    source = {
        "source_id": source_id,
        "origin": "project",
        "source_type": "dataset",
        "canonical_locator": f"project:pilot/{pilot_id}",
        "validation_status": "valid",
        "content_hash": None,
        "extensions": {"pilot_id": pilot_id,
                       "dataset_asset_id": pilot.get("dataset_asset_id")},
    }
    study_id = new_local_id("STU", {s["study_id"] for s in store.read_table("studies")})
    study = {
        "study_id": study_id,
        "source_ids": [source_id],
        "study_design": "pilot",
        "population": f"pilot cohort (n={pilot['sample_size']})",
        "sample_ids": [f"PILOT-{pilot['pilot_id']}"],
        "independence_key": f"pilot:{pilot['pilot_id']}",
        "identity_status": "resolved",
        "extensions": {"pilot_id": pilot_id},
    }
    outcome = _ensure_outcome(store, outcome_id)
    estimate = None
    if effect_estimate is not None:
        estimate = {
            "metric": measure,
            "value": effect_estimate.get("value"),
            "raw_text": raw_result_text,
        }
    finding_id = new_local_id("FND", {f["finding_id"] for f in store.read_table("findings")})
    finding = {
        "finding_id": finding_id,
        "study_id": study_id,
        "finding_type": "quantitative_effect" if estimate else "descriptive",
        "outcome_id": outcome_id,
        "measure": measure,
        "timepoint": pilot.get("end_date"),
        "effect_direction": effect_direction,
        "effect_estimate": estimate,
        "raw_result_text": raw_result_text,
        "source_locator": source["canonical_locator"],
        "extensions": {"pilot_id": pilot_id,
                       "analysis_run_id": pilot.get("analysis_run_id")},
    }
    link_id = new_local_id("LNK", {l["evidence_link_id"] for l in store.read_table("evidence_links")})
    link = {
        "evidence_link_id": link_id,
        "finding_id": finding_id,
        "claim_id": claim_id,
        "relation_to_claim": relation_to_claim,
        "decision_implication": _DECISION_IMPLICATION[relation_to_claim],
        "directness": directness,
        "applicability": {"scope_match": "direct",
                          "target_population": f"pilot cohort (n={pilot['sample_size']})",
                          "context_notes": f"pilot {pilot_id}: {pilot['title']}"},
        "reasoning_note": reasoning_note or f"pilot outcomes: {pilot['title']}",
        "created_in_revision": store.active_revision() + 1,
        "extensions": {"pilot_id": pilot_id},
    }

    mutation = GraphMutation(upserts={
        "sources": [source],
        "studies": [study],
        "outcomes": [outcome] if store.get("outcomes", outcome_id) is None else [],
        "findings": [finding],
        "evidence_links": [link],
    })
    revision = store.commit(
        run_id=new_run_id(), reason=f"pilot outcomes re-adjudication: {pilot_id}",
        mutation=mutation)

    try:
        store.repair_head_mirror()
        syntheses = synthesize_project(store)
        snapshot = adjudicate(
            store, project=project, claim_syntheses=syntheses,
            policy_versions={"confidence": CONFIDENCE_POLICY_VERSION,
                             "methodology": METHODOLOGY_POLICY_VERSION,
                             "source_validation": SOURCE_VALIDATION_POLICY_VERSION})
        path = save_decision_snapshot(project, snapshot)

        previous = None
        prev_path = project.path / "decisions" / f"{pilot['decision_snapshot_id']}.json"
        if prev_path.is_file():
            previous = json.loads(prev_path.read_text(encoding="utf-8"))
        diff = decision_diff(previous, snapshot)
    except Exception as exc:  # noqa: BLE001 - graph committed, mark failure for diagnosis
        # The graph revision is already committed; never let the pilot record
        # claim success. Record the failure so the state machine is
        # diagnosable and a human can recover (P1-3).
        pilot.setdefault("extensions", {})["redecide_failed"] = {
            "graph_revision": revision.revision,
            "error": str(exc),
        }
        _save_pilot(project, pilot)
        raise

    pilot["redecide"] = {
        "new_decision_snapshot_id": snapshot["decision_snapshot_id"],
        "graph_revision": revision.revision,
        "diff": diff,
    }
    pilot["status"] = "adjudicated"
    _save_pilot(project, pilot)
    return {"snapshot": snapshot, "revision": revision.revision,
            "diff": diff, "snapshot_path": str(path)}
