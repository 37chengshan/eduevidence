"""Pytest configuration: make scripts/ importable as a package."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for scripts_dir in (ROOT / "scripts",
                    ROOT / "visualization" / "eduevidence-report" / "scripts"):
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
