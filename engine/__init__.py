"""EduEvidence V2 Research Engine — internal capability core.

The competition artifact remains the EduEvidence Skill; this package is the
engine behind it. Native Core depends only on the Python standard library.
"""

# Single source of truth for the engine version lives in engine/versions.py;
# re-exported here so `from engine import ENGINE_VERSION` stays valid.
from .versions import ENGINE_VERSION

__all__ = ["ENGINE_VERSION"]
