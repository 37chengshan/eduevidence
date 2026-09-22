"""python -m intake — CLI entry."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `python scripts/intake/__main__.py` without installing the package.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from intake.cli import main  # noqa: E402

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
