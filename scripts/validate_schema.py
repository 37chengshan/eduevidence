#!/usr/bin/env python3
"""validate_schema.py — Validate data files against EduEvidence JSON Schemas.

Zero-dependency JSON Schema (draft-07 subset) validator covering the constructs
used by schemas/*.schema.json: $id, title, description, type, properties,
required, enum, minimum, maximum, minLength, additionalProperties, $ref
(local #/definitions and relative-file references), const, format (uri,
date-time), pattern.

Usage:
    python scripts/validate_schema.py --schema schemas/evidence.schema.json \
        --data examples/ai-coding-assistant/evidence.jsonl
    python scripts/validate_schema.py --schema schemas/verdict.schema.json \
        --data examples/ai-coding-assistant/verdict.json

Exit code 0 = all records valid; 1 = at least one record invalid.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
import urllib.parse
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


def _is_uri(value: str) -> bool:
    """Minimal RFC 3986 absolute-URI check: non-empty scheme plus non-empty rest.

    Uses only the standard library (urllib.parse). Rejects values with
    whitespace and scheme-less strings such as 'example.com/path'.
    """
    if any(ch.isspace() for ch in value):
        return False
    parsed = urllib.parse.urlparse(value)
    if not parsed.scheme:
        return False
    return bool(parsed.netloc or parsed.path or parsed.query or parsed.fragment)


def _is_datetime(value: str) -> bool:
    """RFC 3339 date-time check via stdlib datetime.fromisoformat.

    Accepts 'Z'/'z' UTC markers and numeric offsets; rejects date-only strings
    (no 'T'/' ' separator), offset-less naive timestamps, and unparseable
    values.
    """
    if "T" not in value and " " not in value:
        return False
    separator = "T" if "T" in value else " "
    time_part = value.split(separator, 1)[1]
    # RFC 3339 requires a timezone offset (Z or +/-hh:mm); reject naive times.
    if not value.endswith(("Z", "z")) and not any(c in time_part for c in ("+", "-")):
        return False
    normalized = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        datetime.datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


class Validator:
    """Zero-dependency draft-07 subset validator.

    Supports $ref against local '#/definitions/...' pointers and — when
    ``base_dir`` is supplied — relative file references (e.g.
    report-spec.schema.json's 'chart-spec.schema.json'). Unresolvable $refs
    raise SchemaError instead of being silently ignored.
    """

    def __init__(self, root: dict, base_dir: Path | None = None):
        self.root = root
        self.base_dir = base_dir
        self._ref_cache: dict[str, dict] = {}

    def _resolve_ref(self, ref: str, path: str) -> dict:
        if ref.startswith("#/"):
            node = self.root
            for part in ref[2:].split("/"):
                key = part.replace("~1", "/").replace("~0", "~")
                if not isinstance(node, dict) or key not in node:
                    raise SchemaError(f"{path}: unresolvable $ref {ref!r}")
                node = node[key]
            if not isinstance(node, dict):
                raise SchemaError(f"{path}: $ref {ref!r} does not point to a schema object")
            return node
        if self.base_dir is not None:
            target = self.base_dir / ref
            if target.is_file():
                if str(target) not in self._ref_cache:
                    self._ref_cache[str(target)] = json.loads(target.read_text(encoding="utf-8"))
                return self._ref_cache[str(target)]
        raise SchemaError(f"{path}: unresolvable $ref {ref!r}")

    def validate(self, value, schema: dict, path: str = "$") -> None:
        """Validate `value` against `schema` (draft-07 subset). Raises SchemaError."""
        if "$ref" in schema:
            # draft-07: $ref replaces sibling keywords entirely
            self.validate(value, self._resolve_ref(schema["$ref"], path), path)
            return

        if "type" in schema:
            types = schema["type"]
            if isinstance(types, str):
                types = [types]
            if not any(_type_ok(value, t) for t in types):
                raise SchemaError(f"{path}: expected type {schema['type']}, got {type(value).__name__}")

        if "const" in schema and value != schema["const"]:
            raise SchemaError(f"{path}: expected const {schema['const']!r}, got {value!r}")

        if "enum" in schema and value not in schema["enum"]:
            raise SchemaError(f"{path}: value {value!r} not in enum {schema['enum']}")

        fmt = schema.get("format")
        if isinstance(value, str):
            if fmt == "uri" and not _is_uri(value):
                raise SchemaError(f"{path}: {value!r} is not a valid uri (format: uri)")
            if fmt == "date-time" and not _is_datetime(value):
                raise SchemaError(f"{path}: {value!r} is not a valid date-time (format: date-time)")
            if "pattern" in schema and re.search(schema["pattern"], value) is None:
                raise SchemaError(f"{path}: {value!r} does not match pattern {schema['pattern']!r}")

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
                    self.validate(val, props[key], f"{path}.{key}")
                elif additional is False:
                    raise SchemaError(f"{path}: unexpected property {key!r}")
                elif isinstance(additional, dict):
                    # schema-valued additionalProperties: validate unknown keys
                    self.validate(val, additional, f"{path}.{key}")

        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                raise SchemaError(
                    f"{path}: expected at least {schema['minItems']} items, "
                    f"got {len(value)}")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                raise SchemaError(
                    f"{path}: expected at most {schema['maxItems']} items, "
                    f"got {len(value)}")
            if schema.get("uniqueItems") is True:
                seen: list = []
                for item in value:
                    try:
                        normalized = item if not isinstance(item, (dict, list)) \
                            else json.dumps(item, sort_keys=True, separators=(",", ":"))
                    except (TypeError, ValueError):
                        normalized = repr(item)
                    if normalized in seen:
                        raise SchemaError(
                            f"{path}: array items must be unique, duplicate "
                            f"found: {item!r}")
                    seen.append(normalized)
            items = schema.get("items")
            if items:
                for i, item in enumerate(value):
                    self.validate(item, items, f"{path}[{i}]")


def validate(value, schema: dict, path: str = "$") -> None:
    """Validate `value` against `schema` (draft-07 subset). Raises SchemaError.

    Module-level convenience wrapper (no external $ref resolution; local
    '#/definitions/...' references resolve against ``schema`` itself).
    """
    Validator(schema).validate(value, schema, path)


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

    schema_path = Path(args.schema)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    records = load_records(Path(args.data))

    validator = Validator(schema, base_dir=schema_path.resolve().parent)
    errors = []
    for idx, record in enumerate(records):
        try:
            validator.validate(record, schema, f"record[{idx}]")
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
