"""Locate immutable bundled resources in a checkout, Skill or installed wheel."""
from pathlib import Path
import sys


def resource_root() -> Path:
    package_root = Path(__file__).resolve().parent.parent
    candidates = (package_root, package_root / "share" / "eduevidence",
                  Path(sys.prefix) / "share" / "eduevidence")
    for candidate in candidates:
        if (candidate / "SKILL.md").is_file():
            return candidate
    return package_root
