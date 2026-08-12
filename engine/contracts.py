"""V2 schema registry and validation helpers.

Reuses the repository's existing zero-dependency Draft-07 validator
(`scripts.validate_schema`) — the engine layer never prints; errors are
returned as stable strings.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from scripts.validate_schema import SchemaError, validate

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas" / "v2"

# name -> schema file name (frozen registry)
_REGISTRY: dict[str, str] = {
    "research-intent": "research-intent.schema.json",
    "project": "project.schema.json",
    "run": "run.schema.json",
    "source": "source.schema.json",
    "study": "study.schema.json",
    "finding": "finding.schema.json",
    "outcome": "outcome.schema.json",
    "claim": "claim.schema.json",
    "evidence-link": "evidence-link.schema.json",
    "methodology-audit": "methodology-audit.schema.json",
    "graph-revision": "graph-revision.schema.json",
    "knowledge-gap": "knowledge-gap.schema.json",
    "study-design": "study-design.schema.json",
    "dataset-asset": "dataset-asset.schema.json",
    "analysis-plan": "analysis-plan.schema.json",
    "analysis-run": "analysis-run.schema.json",
    "decision-snapshot": "decision-snapshot.schema.json",
}

_cache: dict[str, dict] = {}


def schema_path(name: str) -> Path:
    """Resolve a registered schema name to its file; raise FileNotFoundError."""
    if name not in _REGISTRY:
        raise FileNotFoundError(f"unknown V2 schema name {name!r}")
    return SCHEMA_DIR / _REGISTRY[name]


def load_schema(name: str) -> dict:
    """Load (cached) the schema document for a registered name."""
    if name not in _cache:
        _cache[name] = __import__("json").loads(schema_path(name).read_text(encoding="utf-8"))
    return _cache[name]


def validate_record(name: str, record: dict) -> list[str]:
    """Validate `record` against the named V2 schema.

    Returns a list of stable error strings (empty == valid). Errors are
    collected by re-validating per-property so a single record yields all
    violations, not just the first.
    """
    if name not in _REGISTRY:
        raise FileNotFoundError(f"unknown V2 schema name {name!r}")
    schema = load_schema(name)
    errors: list[str] = []
    try:
        validate(record, schema)
    except SchemaError as exc:
        errors.append(str(exc))
        _collect_property_errors(record, schema, errors)
    return errors


def _collect_property_errors(record: dict, schema: dict, errors: list[str]) -> None:
    """Best-effort per-property error collection after a whole-record failure.

    Individual-property validation keeps errors stable and granular without
    changing the validator's semantics.
    """
    props = schema.get("properties", {})
    for key, prop_schema in props.items():
        if key in record:
            try:
                validate(record[key], prop_schema, f"$.{key}")
            except SchemaError as exc:
                if str(exc) not in errors:
                    errors.append(str(exc))
    required = schema.get("required", [])
    for key in required:
        if key not in record:
            msg = f"$: required property {key!r} is missing"
            if msg not in errors:
                errors.append(msg)
