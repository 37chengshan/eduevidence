"""Atomic, append-only Graph commit for Evidence Autoresearch staging bundles.

One ResearchIteration may add several graph entity types, but it must create at
most one GraphRevision. Identical already-present entities are no-ops; the same
entity id with different scientific content is an append-only conflict rather
than an overwrite. The caller must supply the graph revision against which the
research request was created so stale results fail closed.
"""
from __future__ import annotations

from typing import Any

from engine.graph_store import GRAPH_TABLES, GraphMutation, GraphStore

_ID_KEYS = {
    "sources": "source_id",
    "studies": "study_id",
    "findings": "finding_id",
    "outcomes": "outcome_id",
    "claims": "claim_id",
    "evidence_links": "evidence_link_id",
    "audits": "audit_id",
}
_VALID_SOURCE_STATUSES = {"valid", "accepted_partial"}


def _rows(payload: dict[str, Any], table: str) -> list[dict]:
    value = payload.get(table, [])
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError(f"staging bundle field {table!r} must be a list of objects")
    return value


def build_append_only_mutation(
    store: GraphStore,
    payload: dict[str, Any],
) -> tuple[GraphMutation, dict[str, list[str]]]:
    """Return only genuinely new entities plus their ids.

    GraphStore performs schema and cross-entity validation on the final merged
    snapshot. This function adds the Autoresearch-specific append-only and
    validated-source gates before that atomic commit.
    """
    upserts: dict[str, list[dict]] = {}
    added: dict[str, list[str]] = {}

    existing_tables = {table: store.read_table(table) for table in GRAPH_TABLES}
    for table in GRAPH_TABLES:
        id_key = _ID_KEYS[table]
        existing = {row[id_key]: row for row in existing_tables[table]}
        seen_incoming: dict[str, dict] = {}
        fresh: list[dict] = []
        fresh_ids: list[str] = []
        for row in _rows(payload, table):
            entity_id = row.get(id_key)
            if not isinstance(entity_id, str) or not entity_id:
                raise ValueError(f"{table} staging entity missing {id_key}")
            prior_incoming = seen_incoming.get(entity_id)
            if prior_incoming is not None:
                if prior_incoming != row:
                    raise ValueError(
                        f"append-only conflict: duplicate incoming {table} id {entity_id} has different content"
                    )
                continue
            seen_incoming[entity_id] = row
            prior = existing.get(entity_id)
            if prior is not None:
                if prior != row:
                    raise ValueError(
                        f"append-only conflict: {table} {entity_id} already exists with different content"
                    )
                continue
            if table == "sources" and row.get("validation_status") not in _VALID_SOURCE_STATUSES:
                raise ValueError(
                    f"source {entity_id} has validation_status={row.get('validation_status')!r}; "
                    "only valid/accepted_partial sources may enter Evidence Autoresearch"
                )
            fresh.append(row)
            fresh_ids.append(entity_id)
        if fresh:
            upserts[table] = fresh
            added[table] = fresh_ids

    # A newly added Study may only cite a validated existing/new Source. This
    # preserves the Fetch -> Validate -> Extract gate in the atomic path.
    source_status = {
        row["source_id"]: row.get("validation_status")
        for row in existing_tables["sources"]
    }
    for row in upserts.get("sources", []):
        source_status[row["source_id"]] = row.get("validation_status")
    for study in upserts.get("studies", []):
        for source_id in study.get("source_ids", []):
            status = source_status.get(source_id)
            if status not in _VALID_SOURCE_STATUSES:
                raise ValueError(
                    f"study {study['study_id']} references source {source_id} "
                    f"without validated provenance (status={status!r})"
                )

    return GraphMutation(upserts=upserts, retire_ids={}), added


def commit_staging_bundle(
    store: GraphStore,
    *,
    run_id: str,
    expected_base_revision: int,
    payload: dict[str, Any],
) -> int | None:
    """Atomically append one staging bundle, or return None for a true no-op."""
    active = store.active_revision()
    if active != expected_base_revision:
        raise RuntimeError(
            f"STALE_RESEARCH_STATE: request was based on graph revision "
            f"{expected_base_revision}, active revision is {active}; re-plan before commit"
        )
    mutation, added = build_append_only_mutation(store, payload)
    if not added:
        return None
    # Single Writer is an architectural invariant. Recheck immediately before
    # commit so an intervening canonical transition is detected before write.
    if store.active_revision() != expected_base_revision:
        raise RuntimeError("STALE_RESEARCH_STATE: graph changed while validating staging bundle")
    revision = store.commit(
        run_id=run_id,
        reason="autoresearch atomic validated evidence append",
        mutation=mutation,
    )
    return revision.revision
