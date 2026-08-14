"""Stable entity ID helpers.

Project and Run IDs are **creation identities**, not question hashes: two
teams may intentionally create two independent Projects with the same
question, so uniqueness comes from UTC creation time plus a short entropy
suffix. The normalized question fingerprint is metadata only, never identity.

Local entity prefixes are frozen in the V2 design:

    PRJ Project  RUN Run  SRC Source  STU Study  FND Finding  OUT Outcome
    CLM Claim    LNK EvidenceLink  AUD MethodologyAudit  GAP KnowledgeGap
    DSN StudyDesign  DAT DatasetAsset  APL AnalysisPlan  ANL AnalysisRun
    DEC DecisionSnapshot  PIL PilotRun

Interpretive entities (Claim, EvidenceLink, KnowledgeGap, DecisionSnapshot)
keep stable Project-local IDs across edits; version/revision metadata records
change instead of silently re-identifying.
"""

from datetime import datetime, timezone
import hashlib
import secrets

_LOCAL_PREFIXES = frozenset({
    "SRC", "STU", "FND", "OUT", "CLM", "LNK", "AUD", "GAP",
    "DSN", "DAT", "APL", "ANL", "DEC", "PIL",
})


def _utc_compact(now: datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _question_fingerprint(question: str) -> str:
    norm = " ".join(question.strip().lower().split())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:8]


def _unique_suffix(existing: set[str]) -> str:
    while True:
        suffix = secrets.token_hex(4)
        if suffix not in existing:
            return suffix


def new_project_id(question: str, *, now: datetime | None = None,
                   existing: set[str] | None = None) -> str:
    """Create a unique Project creation identity.

    `existing` (when supplied) is the set of suffixes already in use, so a
    caller can guarantee collision-free allocation within its namespace.
    """
    now = now or datetime.now(timezone.utc)
    existing = existing or set()
    suffix = _unique_suffix(existing)
    return f"PRJ-{_utc_compact(now)}-{_question_fingerprint(question)}-{suffix}"


def new_run_id(now: datetime | None = None, existing: set[str] | None = None) -> str:
    """Create a unique Run creation identity."""
    now = now or datetime.now(timezone.utc)
    existing = existing or set()
    suffix = _unique_suffix(existing)
    return f"RUN-{_utc_compact(now)}-{suffix}"


def new_local_id(prefix: str, existing: set[str]) -> str:
    """Create a unique local entity ID with a frozen design prefix."""
    if prefix not in _LOCAL_PREFIXES:
        raise ValueError(
            f"unknown entity prefix {prefix!r}; frozen prefixes: "
            f"{sorted(_LOCAL_PREFIXES)}"
        )
    suffix = _unique_suffix(existing)
    return f"{prefix}-{suffix}"
