"""Cross-entity integrity checks for the V2 evidence graph.

Reference integrity is a commit precondition: a Finding may not point at a
missing Study, an EvidenceLink at a missing Finding/Claim, an Audit at a
missing Study. Returns stable error strings; no printing from the engine.
"""

from __future__ import annotations


# graph table name -> entity id field
_TABLE_ID_KEY = {
    "sources": "source_id",
    "studies": "study_id",
    "findings": "finding_id",
    "outcomes": "outcome_id",
    "claims": "claim_id",
    "evidence_links": "evidence_link_id",
    "audits": "audit_id",
}


def _ids(rows: list[dict], table: str) -> set[str]:
    key = _TABLE_ID_KEY[table]
    return {row[key] for row in rows}


def validate_graph(tables: dict[str, list[dict]]) -> list[str]:
    """Validate cross-entity references across all graph tables.

    `tables` maps table name -> list of entity dicts (the in-memory graph
    state being validated, already schema-validated per entity).
    """
    errors: list[str] = []

    sources = _ids(tables.get("sources", []), "sources")
    studies = _ids(tables.get("studies", []), "studies")
    findings = _ids(tables.get("findings", []), "findings")
    outcomes = _ids(tables.get("outcomes", []), "outcomes")
    claims = _ids(tables.get("claims", []), "claims")
    links = tables.get("evidence_links", [])
    audits = tables.get("audits", [])

    for f in tables.get("findings", []):
        if f["study_id"] not in studies:
            errors.append(
                f"finding {f['finding_id']} references missing study {f['study_id']}"
            )
        if f["outcome_id"] not in outcomes:
            errors.append(
                f"finding {f['finding_id']} references missing outcome {f['outcome_id']}"
            )

    for s in tables.get("studies", []):
        for sid in s.get("source_ids", []):
            if sid not in sources:
                errors.append(
                    f"study {s['study_id']} references missing source {sid}"
                )

    for link in links:
        if link["finding_id"] not in findings:
            errors.append(
                f"evidence_link {link['evidence_link_id']} references missing "
                f"finding {link['finding_id']}"
            )
        if link["claim_id"] not in claims:
            errors.append(
                f"evidence_link {link['evidence_link_id']} references missing "
                f"claim {link['claim_id']}"
            )

    for c in tables.get("claims", []):
        for oid in c.get("primary_outcome_ids", []):
            if oid not in outcomes:
                errors.append(
                    f"claim {c['claim_id']} references missing outcome {oid}"
                )

    for a in audits:
        if a["study_id"] not in studies:
            errors.append(
                f"methodology_audit {a['audit_id']} references missing "
                f"study {a['study_id']}"
            )

    return errors
