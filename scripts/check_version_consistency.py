#!/usr/bin/env python3
"""Version consistency gate: engine/versions.py is the single version authority.

Fails (exit 1) when the declared versions drift apart:

- engine/versions.py  ENGINE_VERSION            <- authority
- pyproject.toml      [project] version
- CHANGELOG.md        first `## [x.y.z]` heading
- SKILL.md            `# EduEvidence X.Y` title (major.minor only)

Stdlib only; run in CI before tests.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSIONS_PY_RE = re.compile(r'^ENGINE_VERSION\s*=\s*"(\d+\.\d+\.\d+)"', re.M)
PYPROJECT_RE = re.compile(r'^version\s*=\s*"(\d+\.\d+\.\d+)"', re.M)
CHANGELOG_RE = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]", re.M)
SKILL_TITLE_RE = re.compile(r"^#\s*EduEvidence\s+(\d+\.\d+)", re.M)


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    m = VERSIONS_PY_RE.search(_read("engine/versions.py"))
    if not m:
        print("FAIL: cannot parse ENGINE_VERSION from engine/versions.py")
        return 1
    authoritative = m.group(1)
    if not VERSION_RE.match(authoritative):
        errors.append(f"engine/versions.py ENGINE_VERSION not semver: {authoritative!r}")

    def check_full(label: str, found: str) -> None:
        if found != authoritative:
            errors.append(f"{label} = {found} != engine/versions.py {authoritative}")

    def check_minor(label: str, found: str) -> None:
        prefix = authoritative.rsplit(".", 1)[0]
        if found != prefix:
            errors.append(f"{label} = {found} != {prefix} (from {authoritative})")

    # -- pyproject.toml ------------------------------------------------------
    pp = PYPROJECT_RE.search(_read("pyproject.toml"))
    if pp:
        check_full("pyproject.toml", pp.group(1))
    else:
        errors.append("cannot parse version from pyproject.toml")

    # -- CHANGELOG.md ---------------------------------------------------------
    cl = CHANGELOG_RE.search(_read("CHANGELOG.md"))
    if cl:
        check_full("CHANGELOG.md head entry", cl.group(1))
    else:
        errors.append("cannot parse leading '## [x.y.z]' from CHANGELOG.md")

    # -- SKILL.md (major.minor only) ------------------------------------------
    sk = SKILL_TITLE_RE.search(_read("SKILL.md"))
    if sk:
        check_minor("SKILL.md title", sk.group(1))
    else:
        errors.append("cannot parse '# EduEvidence X.Y' title from SKILL.md")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        print(f"Version authority: engine/versions.py = {authoritative}")
        return 1
    print(f"version consistency OK ({authoritative})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
