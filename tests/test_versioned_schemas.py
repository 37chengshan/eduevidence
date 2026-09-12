"""Guard: the versioned contract family is data-validated, not JSON-smoke-tested.

schemas/v3, v4 and vNext were only ever parsed, so a renamed required field or a
changed enum shipped silently. check_versioned_schemas.py builds a record from the
producer and validates it; this test keeps that property and proves the checker can
fail."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_versioned_schema_checker_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'check_versioned_schemas.py')],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert 'versioned schemas OK' in result.stdout


def test_checker_covers_all_three_families():
    script = (ROOT / 'scripts' / 'check_versioned_schemas.py').read_text(encoding='utf-8')
    for family in ('v3', 'v4', 'vNext'):
        assert family in script, f'{family} is not validated'
    assert "negative-search-record.schema.json" in script
    assert "run-manifest.schema.json" in script
