"""Immutable DatasetAsset ingest + privacy gate.

Raw bytes are copied once into datasets/raw/<dataset_id>/ and SHA-256 hashed;
re-ingesting identical bytes deduplicates by hash inside the same Project.
Raw user data never enters the Shared Research Library. Missing privacy
classification fails the gate; deidentification_required=True with
deidentification_status=not_done blocks analysis. Raw files are never
mutated after ingest.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.ids import new_local_id
from engine.project import ProjectWorkspace


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_csv_profile(path: Path) -> dict:
    """Row/column count + per-column missingness without pandas."""
    columns: list[str] | None = None
    row_count = 0
    missing: dict[str, int] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i == 0:
                columns = row
                for c in columns:
                    missing[c] = 0
                continue
            row_count += 1
            if columns is not None:
                for idx, c in enumerate(columns):
                    if idx >= len(row) or row[idx].strip() == "":
                        missing[c] += 1
    if columns is None:
        return {"row_count": 0, "column_count": 0, "missingness": {}}
    return {
        "row_count": row_count,
        "column_count": len(columns),
        "missingness": {c: missing[c] for c in columns},
    }


def validate_dataset_asset(project: ProjectWorkspace, asset: dict) -> list[str]:
    """Privacy gate + schema + project locality."""
    errors: list[str] = []
    schema_errors = validate_record("dataset-asset", asset)
    if schema_errors:
        errors.extend(schema_errors)
        return errors
    if asset.get("project_id") != project.project_id:
        errors.append(
            f"asset project_id {asset.get('project_id')} != workspace "
            f"{project.project_id}")
    return errors


def ingest_dataset(project: ProjectWorkspace, *, design_id: str,
                   source_path: Path, privacy: dict,
                   variable_dictionary: dict[str, str] | None = None) -> dict:
    """Ingest raw dataset bytes immutably; returns the DatasetAsset dict."""
    source_path = Path(source_path).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"dataset source missing: {source_path}")

    # privacy gate: classification required
    classification = privacy.get("classification")
    if classification not in ("public", "internal", "confidential", "restricted"):
        raise ValueError(
            f"missing/invalid privacy classification {classification!r}; "
            f"dataset ingest blocked")

    content_hash = _sha256(source_path)

    # dedupe by hash inside this project; a stricter classification request
    # must never silently rebind to a weaker stored classification
    raw_dir = project.path / "datasets" / "raw"
    for existing in sorted(raw_dir.glob("DAT-*")):
        manifest = existing / "manifest.json"
        if manifest.is_file():
            rec = json.loads(manifest.read_text(encoding="utf-8"))
            if rec.get("content_hash") == content_hash:
                stored = rec.get("privacy_classification")
                order = ("public", "internal", "confidential", "restricted")
                if order.index(classification) > order.index(stored):
                    raise ValueError(
                        f"dataset {content_hash[:10]}… already stored with "
                        f"weaker classification {stored!r}; re-ingesting as "
                        f"{classification!r} is refused"
                    )
                return rec

    dataset_id = new_local_id("DAT", {
        p.name for p in raw_dir.iterdir() if p.is_dir()})
    dest_dir = raw_dir / dataset_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    # copy bytes once
    dest_raw = dest_dir / source_path.name
    shutil.copy2(source_path, dest_raw)

    profile = derive_csv_profile(dest_raw)
    asset = {
        "dataset_id": dataset_id,
        "project_id": project.project_id,
        "design_id": design_id,
        "source_type": source_path.suffix.lstrip(".").lower() or "unknown",
        "path": str(dest_raw),
        "content_hash": content_hash,
        "schema_summary": {"columns": profile["column_count"]},
        "row_count": profile["row_count"],
        "column_count": profile["column_count"],
        "variable_dictionary": variable_dictionary,
        "privacy_classification": classification,
        "consent_metadata": privacy.get("consent_metadata"),
        "deidentification_status": privacy.get("deidentification_status", "not_done"),
        "created_at": _now_iso(),
        "extensions": {
            "missingness": profile["missingness"],
            "deidentification_required": bool(
                privacy.get("deidentification_required", False)),
        },
    }
    errors = validate_dataset_asset(project, asset)
    if errors:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise ValueError("dataset asset invalid:\n- " + "\n- ".join(errors))

    # atomic manifest write
    tmp = dest_dir / "manifest.json.tmp"
    tmp.write_text(json.dumps(asset, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(dest_dir / "manifest.json")
    return asset


def analysis_blocked_by_privacy(asset: dict) -> list[str]:
    """Return blocking reasons if analysis must not proceed."""
    reasons: list[str] = []
    if asset.get("deidentification_status") == "not_done" and (
            asset.get("extensions") or {}).get("deidentification_required"):
        reasons.append(
            "deidentification_required but deidentification_status=not_done; "
            "analysis blocked until deidentified")
    return reasons
