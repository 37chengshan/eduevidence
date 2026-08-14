"""engine/meta_synthesis.py - cross-project synthesis over the Shared Library (v3).

Aggregates verified facts of one immutable library revision (sources/studies/
findings/audits) into an outcome-level overview:

    per outcome token (OUT-<token> convention) -> positive/negative/null
    finding ids + the independent study keys behind them; plus library-wide
    independent-study and source counts.

The synthesis is an interpretive projection: it never mutates library state.
Contract: schemas/v3/synthesis.schema.json.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.ids import new_local_id
from engine.library import ResearchLibrary
from scripts.validate_schema import SchemaError, validate

_SYNTHESIS_SCHEMA = (Path(__file__).resolve().parent.parent / "schemas" / "v3"
                     / "synthesis.schema.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _outcome_token(outcome_id: str) -> str:
    return outcome_id[len("OUT-"):] if outcome_id.startswith("OUT-") else outcome_id


def _latest_audits(audits: list[dict]) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for a in audits:
        cur = latest.get(a["study_id"])
        if cur is None or a["audited_at"] >= cur["audited_at"]:
            latest[a["study_id"]] = a
    return latest


def synthesize_library(library: ResearchLibrary) -> dict:
    """Build a LibrarySynthesis over the library's ACTIVE revision."""
    findings = library.read_table("findings")
    studies = {s["study_id"]: s for s in library.read_table("studies")}
    sources = {s["source_id"]: s for s in library.read_table("sources")}
    audits = _latest_audits(library.read_table("audits"))

    by_outcome: dict[str, dict[str, Any]] = {}
    usable_study_keys: set[str] = set()

    for fnd in findings:
        study = studies.get(fnd.get("study_id"))
        if study is None:
            continue
        # Usability filter aligned with engine/tribunal._usable_studies (P2-11):
        # unresolved identity, no validated source, or no passing audit -> not usable.
        if study.get("identity_status") == "unresolved":
            continue
        if not any(
            sid in sources and sources[sid].get("validation_status")
            in ("valid", "accepted_partial")
            for sid in study.get("source_ids", [])
        ):
            continue
        audit = audits.get(fnd["study_id"])
        if audit is None or audit.get("overall_status") == "fail":
            continue
        token = _outcome_token(fnd.get("outcome_id", ""))
        row = by_outcome.setdefault(token, {
            "outcome_token": token,
            "positive_findings": [], "negative_findings": [],
            "null_findings": [], "study_keys": [],
        })
        bucket = {"positive": "positive_findings",
                  "negative": "negative_findings"}.get(
                      fnd.get("effect_direction"), "null_findings")
        row[bucket].append(fnd["finding_id"])
        key = study.get("independence_key") or fnd["study_id"]
        if key not in row["study_keys"]:
            row["study_keys"].append(key)
        usable_study_keys.add(key)

    existing = set()  # fresh synthesis id; collisions impossible in practice
    synthesis = {
        "synthesis_id": new_local_id("SYN", existing),
        "library_revision": library.active_revision(),
        "generated_at": _now_iso(),
        "independent_studies": len(usable_study_keys),
        "source_count": len(sources),
        "outcomes": [by_outcome[k] for k in sorted(by_outcome)],
        "extensions": {"finding_count": len(findings),
                       "study_count": len(studies)},
    }
    schema = json.loads(_SYNTHESIS_SCHEMA.read_text(encoding="utf-8"))
    try:
        validate(synthesis, schema)
    except SchemaError as exc:
        raise ValueError(f"invalid library synthesis: {exc}") from exc
    return synthesis


def save_synthesis(synthesis: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{synthesis['synthesis_id']}.json"
    path.write_text(json.dumps(synthesis, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    return path
