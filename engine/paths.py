"""Workspace-root resolution.

EDUEVIDENCE_HOME (default `~/.eduevidence`) is the root that owns the Shared
Research Library and all Projects. An explicit path always wins.
"""

from pathlib import Path
import os


def resolve_home(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    raw = os.environ.get("EDUEVIDENCE_HOME", "~/.eduevidence")
    return Path(raw).expanduser().resolve()
