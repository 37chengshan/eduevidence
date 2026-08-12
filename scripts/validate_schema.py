#!/usr/bin/env python3
"""validate_schema.py — Validate data files against EduEvidence JSON Schemas.

Zero-dependency JSON Schema (draft-07 subset) validator covering the constructs
used by schemas/*.schema.json: $id, title, description, type, properties,
required, enum, minimum, maximum, minLength, additionalProperties.

Usage:
    python scripts/validate_schema.py --schema schemas/evidence.schema.json \
        --data examples/ai-coding-assistant/evidence.jsonl
    python scripts/validate_schema.py --schema schemas/verdict.schema.json \
        --data examples/ai-coding-assistant/verdict.json

Exit code 0 = all records valid; 1 = at least one record invalid.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class SchemaError(Exception):
    """Raised when a value violates the schema."""


def _type_ok(value, expected: str) -> bool:
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "null":
        return value is None
    return True


def validate(value, schema: dict, path: str = "$") -> None:
    """Validate `value` against `schema` (draft-07 subset). Raises SchemaError."""
    if "type" in schema:
        types = schema["type"]
        if isinstance(types, str):
            types = [types]
        if not any(_type_ok(value, t) for t in types):
            raise SchemaError(f"{path}: expected type {schema['type']}, got {type(value).__name__}")

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path}: value {value!r} not in enum {schema['enum']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, str) and "minLength" in schema and len(value) < schema["minLength"]:
        raise SchemaError(f"{path}: string shorter than minLength {schema['minLength']}")

    if isinstance(value, dict):
        if "required" in schema:
            for field in schema["required"]:
                if field not in value:
                    raise SchemaError(f"{path}: missing required field {field!r}")
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties")
        for key, val in value.items():
            if key in props:
                validate(val, props[key], f"{path}.{key}")
            elif additional is False:
                raise SchemaError(f"{path}: unexpected property {key!r}")
            elif isinstance(additional, dict):
                # schema-valued additionalProperties: validate unknown keys
                validate(val, additional, f"{path}.{key}")

    if isinstance(value, list):
        items = schema.get("items")
        if items:
            for i, item in enumerate(value):
                validate(item, items, f"{path}[{i}]")


def load_records(path: Path):
    """Load JSON or JSONL records from a file."""
    if path.suffix == ".jsonl":
        records = []
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SchemaError(f"{path}:{lineno}: invalid JSON line: {exc}") from exc
        return records
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else [data]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate data against an EduEvidence schema")
    parser.add_argument("--schema", required=True, help="Path to schema JSON file")
    parser.add_argument("--data", required=True, help="Path to data file (JSON or JSONL)")
    args = parser.parse_args()

    schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
    records = load_records(Path(args.data))

    errors = []
    for idx, record in enumerate(records):
        try:
            validate(record, schema, f"record[{idx}]")
        except SchemaError as exc:
            errors.append(str(exc))

    if errors:
        for err in errors:
            print(f"INVALID: {err}", file=sys.stderr)
        print(f"{len(errors)} error(s) in {len(records)} record(s)", file=sys.stderr)
        return 1
    print(f"OK: {len(records)} record(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
