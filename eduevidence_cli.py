#!/usr/bin/env python3
"""Console-script shim for ``eduevidence``.

The legacy orchestrator remains authoritative for existing commands. vNext adds
only two intercepted command domains:

    eduevidence research auto ...
    eduevidence evolve ...
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for _p in (str(ROOT / "scripts"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) >= 2 and args[:2] == ["research", "auto"]:
        from vnext_cli import research_auto
        return research_auto(args[2:])
    if args and args[0] == "evolve":
        from vnext_cli import evolve
        return evolve(args[1:])
    from orchestrator import main as legacy_main
    return legacy_main(args)


if __name__ == "__main__":
    sys.exit(main())
