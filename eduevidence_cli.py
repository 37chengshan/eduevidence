#!/usr/bin/env python3
"""eduevidence_cli.py — console-script shim for `eduevidence`.

Installed via pyproject.toml [project.scripts]: the real implementation lives
in scripts/orchestrator.py; this module only puts scripts/ (and the repo root
for retrieval/integrations packages) on sys.path and forwards to it.

Usage:
    eduevidence run --question "..." --depth deep
    eduevidence resume --run-id <id>
    eduevidence status --run-id <id>
    eduevidence list
    eduevidence gate --run-id <id>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from orchestrator import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
