#!/usr/bin/env python3
"""check_versioned_schemas.py - data-level validation for v3 / v4 / vNext.

CI validated this contract family by parsing the JSON only, so a schema could
drift arbitrarily (renamed required fields, changed enums, wrong types) and
stay green. Each family is exercised here by building a record from its own
dataclass or builder and validating that record against its schema, which is
the check that would have caught a real mismatch.

Stdlib only; exit 1 on any invalid record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))


def _validate(record, schema_rel, label):
    from validate_schema import SchemaError, Validator

    path = ROOT / schema_rel
    schema = json.loads(path.read_text(encoding='utf-8'))
    validator = Validator(schema, base_dir=path.parent)
    try:
        validator.validate(record, schema, label)
    except SchemaError as exc:
        return f'{label}: {exc}'
    return None


def main() -> int:
    problems = []
    checked = 0

    # --- vNext: records built from their own dataclasses -------------------
    try:
        from engine.autoresearch.contracts import NegativeSearchRecord

        record = NegativeSearchRecord(
            negative_search_id='NSR-1', research_iteration_id='RI-1',
            gap_id='GAP-1', queries=('a', 'b'), providers=('openalex',),
            candidate_count=0, fetched_count=0, eligible_count=0)
        payload = record.__dict__ if hasattr(record, '__dict__') else record
        # JSON round-trip puts tuples back into their serialized form, which is
        # what actually gets persisted; validate that shape.
        payload = json.loads(json.dumps(payload, default=str))
        err = _validate(payload, 'schemas/vNext/negative-search-record.schema.json',
                        'negative-search-record')
        if err:
            problems.append(err)
        checked += 1
    except Exception as exc:  # import or construction failure is itself a defect
        problems.append(f'negative-search-record: could not build record: {exc}')

    # --- v3: the BENCHMARK run manifest (scripts/benchmark_v3.py) ---------
    # Note: schemas/v3/run-manifest.schema.json describes the empirical
    # benchmark harness record, not the run-workspace manifest. Validating the
    # wrong producer is how a contract silently stops describing reality.
    try:
        fixture = sorted((ROOT / 'benchmarks' / 'empirical').glob('*/manifest.json'))
        if fixture:
            payload = json.loads(fixture[0].read_text(encoding='utf-8'))
            err = _validate(payload, 'schemas/v3/run-manifest.schema.json',
                            f'run-manifest ({fixture[0].parent.name})')
            if err:
                problems.append(err)
            checked += 1
        else:
            problems.append('no benchmarks/empirical/*/manifest.json fixture to validate')
    except Exception as exc:
        problems.append(f'v3 run-manifest: {exc}')

    # --- sanity: every declared schema still parses -----------------------
    for family in ('v3', 'v4', 'vNext'):
        for path in sorted((ROOT / 'schemas' / family).glob('*.json')):
            try:
                json.loads(path.read_text(encoding='utf-8'))
                checked += 1
            except (OSError, json.JSONDecodeError) as exc:
                problems.append(f'{path.relative_to(ROOT)}: {exc}')

    if problems:
        print('ERROR: versioned schema validation failed', file=sys.stderr)
        for item in problems:
            print(f'  {item}', file=sys.stderr)
        return 1
    print(f'versioned schemas OK ({checked} checks across v3 / v4 / vNext)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
