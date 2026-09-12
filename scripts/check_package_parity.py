#!/usr/bin/env python3
"""check_package_parity.py - prove the shipped package matches the source tree.

The upload package is a projection of this repository. If a source file changed
and the package still carries the old bytes, reviewers receive a different
product from the one under source control. CI previously compared only
SKILL.md, so a renamed role file went unnoticed for a whole change set.

Compares every file the shared payload allowlist ships: content must match and
nothing may be missing. Stdlib only; exit 1 on any drift.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

PACKAGE = ROOT / "dist" / "eduevidence-submission"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not PACKAGE.is_dir():
        print(f"ERROR: no package at {PACKAGE}; run bash packaging/make_upload.sh")
        return 1

    from skill_payload import payload_files

    expected = set(payload_files(ROOT))
    # The manifest and the packaging notes are written by the build, not copied.
    generated = {"submission-manifest.json", "UPLOAD-README.md", "START-HERE.md",
                 "scp-manifest.json", "upload-layout.md", "README.zh-CN.md"}
    expected |= {name for name in generated if (PACKAGE / name).is_file()}

    missing = sorted(rel for rel in expected if not (PACKAGE / rel).is_file())

    # Reverse direction: a file the package carries but the source does not is
    # stale output from an earlier build. A one-way check cannot see that,
    # which is how pre-rename report copies once survived inside a package.
    unexpected = []
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(PACKAGE).as_posix()
        if rel in expected or rel == "submission-manifest.json":
            continue
        if any(part in {"__pycache__", ".git"} for part in path.parts):
            continue
        if path.suffix in {".pyc", ".pyo"} or path.name == ".DS_Store":
            continue
        if not (ROOT / rel).exists():
            unexpected.append(rel)
    differing = []
    for rel in sorted(expected):
        source = ROOT / rel
        shipped = PACKAGE / rel
        if not source.is_file() or not shipped.is_file():
            continue
        if digest(source) != digest(shipped):
            differing.append(rel)

    if missing or differing or unexpected:
        print("ERROR: package does not match the source tree", file=sys.stderr)
        for rel in missing[:20]:
            print(f"  missing from package: {rel}", file=sys.stderr)
        for rel in differing[:20]:
            print(f"  differs from source:  {rel}", file=sys.stderr)
        for rel in unexpected[:20]:
            print(f"  stale in package:     {rel}", file=sys.stderr)
        print("  fix: bash packaging/make_upload.sh", file=sys.stderr)
        return 1

    print(f"package parity OK ({len(expected)} files byte-identical to source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
