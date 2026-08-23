"""adapter_contract.py — shared zero-dependency envelope helpers (P1 contract gate).

Every visualization adapter CLI (build_charts / build_infographics /
build_figures) writes the same envelope through write_adapter_output():
adapter, contract_version, source_ref, source_sha256, locale, data.
build_report.py imports the same core functions, so the CLI path and the
report path can never diverge.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "1.0"
ADAPTERS = ("charts", "infographics", "figures")


def load_result(path: str) -> dict:
    """Load a result.json as a JSON object; fail closed with a clear message."""
    p = Path(path)
    if not p.exists():
        print(f"ERROR: result file not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: result file is not valid JSON: {path} ({exc})", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"ERROR: result file must contain a JSON object: {path}", file=sys.stderr)
        sys.exit(2)
    return data


def result_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_adapter_output(out: str, adapter: str, result_path: str, payload: dict,
                         locale: str = "zh") -> None:
    """Validate inputs and write the adapter envelope; never fabricate data."""
    if adapter not in ADAPTERS:
        print(f"ERROR: unknown adapter {adapter!r} (expected one of {ADAPTERS})",
              file=sys.stderr)
        sys.exit(2)
    if locale not in ("zh", "en"):
        print(f"ERROR: locale must be zh or en (got {locale!r})", file=sys.stderr)
        sys.exit(2)
    envelope = {
        "adapter": adapter,
        "contract_version": CONTRACT_VERSION,
        "source_ref": Path(result_path).name,
        "source_sha256": result_sha256(result_path),
        "locale": locale,
        "data": payload,
    }
    out_path = Path(out)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: cannot create output directory {out_path.parent}: {exc}",
              file=sys.stderr)
        sys.exit(2)
    try:
        out_path.write_text(json.dumps(envelope, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot write output file {out_path}: {exc}", file=sys.stderr)
        sys.exit(2)