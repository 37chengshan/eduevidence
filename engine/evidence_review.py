"""Graph-oriented evidence review mutations.

Every scientific change goes through GraphStore.commit() — nothing in this
module writes JSONL directly. Ingestion gates:
- a Source whose validation_status is neither valid nor accepted_partial
  cannot be used to build a validated Finding path;
- Findings/Studies must reference existing Source provenance;
- Claims may link a negative Finding without changing its direction;
- counter-evidence Findings are never dropped for unfavorable implications.
"""

from __future__ import annotations

from engine.graph_store import GraphStore, GraphMutation, GraphRevision

VALID_SOURCE_STATUSES = ("valid", "accepted_partial")


def ingest_validated_sources(store: GraphStore, *, run_id: str,
                             sources: list[dict]) -> GraphRevision:
    """Commit validated sources (only valid/accepted_partial statuses)."""
    for src in sources:
        if src.get("validation_status") not in VALID_SOURCE_STATUSES:
            raise ValueError(
                f"source {src.get('source_id')} has status "
                f"{src.get('validation_status')!r}; only {list(VALID_SOURCE_STATUSES)} "
                f"can enter the graph as validated evidence"
            )
    return store.commit(
        run_id=run_id, reason="ingest validated sources",
        mutation=GraphMutation(upserts={"sources": sources}, retire_ids={}))


def ingest_extracted_studies_findings(store: GraphStore, *, run_id: str,
                                      studies: list[dict],
                                      findings: list[dict]) -> GraphRevision:
    """Commit extracted Studies + Findings (must reference existing Sources)."""
    source_ids = {s["source_id"] for s in store.read_table("sources")}
    study_ids = {s["study_id"] for s in store.read_table("studies")}
    for s in studies:
        missing = [sid for sid in s.get("source_ids", []) if sid not in source_ids]
        if missing:
            raise ValueError(
                f"study {s.get('study_id')} references missing sources: {missing}")
    for f in findings:
        if f.get("study_id") not in study_ids and f.get("study_id") not in {
                s.get("study_id") for s in studies}:
            raise ValueError(
                f"finding {f.get('finding_id')} references absent study "
                f"{f.get('study_id')}; provenance missing")
    return store.commit(
        run_id=run_id, reason="ingest studies and findings",
        mutation=GraphMutation(upserts={"studies": studies, "findings": findings},
                               retire_ids={}))


def ingest_methodology_audits(store: GraphStore, *, run_id: str,
                              audits: list[dict]) -> GraphRevision:
    """Commit methodology audits (must reference existing Studies)."""
    study_ids = {s["study_id"] for s in store.read_table("studies")}
    for a in audits:
        if a.get("study_id") not in study_ids:
            raise ValueError(
                f"audit {a.get('audit_id')} references missing study "
                f"{a.get('study_id')}")
    return store.commit(
        run_id=run_id, reason="ingest methodology audits",
        mutation=GraphMutation(upserts={"audits": audits}, retire_ids={}))


def ingest_claims_links(store: GraphStore, *, run_id: str,
                        claims: list[dict], links: list[dict]) -> GraphRevision:
    """Commit Claims + EvidenceLinks (must reference existing Findings).

    A link may support a negative Finding; the Finding's effect_direction is
    never rewritten by the link. Counter-evidence links with unfavorable
    decision implications are preserved.
    """
    finding_ids = {f["finding_id"] for f in store.read_table("findings")}
    for link in links:
        if link.get("finding_id") not in finding_ids:
            raise ValueError(
                f"evidence_link {link.get('evidence_link_id')} references "
                f"missing finding {link.get('finding_id')}")
    return store.commit(
        run_id=run_id, reason="ingest claims and links",
        mutation=GraphMutation(upserts={"claims": claims, "evidence_links": links},
                               retire_ids={}))
