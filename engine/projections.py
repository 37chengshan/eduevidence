"""V2 graph projections + V1 compatibility result.json.

Projections are read-only views of a graph revision: they never mutate graph
entities. Outcome aggregation uses Finding.effect_direction; claim trace uses
EvidenceLink.relation_to_claim; study counts use Study IDs. Compatibility
`evidence` rows are view rows with explicit finding_id/evidence_link_id in
extensions so no identity is lost.
"""

from __future__ import annotations

import json
from pathlib import Path

from engine.graph_store import GraphStore
from engine.project import ProjectWorkspace
from engine.semantics import claim_relation, decision_implication, finding_effect


def _load_latest_snapshot(project: ProjectWorkspace,
                          decision_snapshot_id: str | None) -> dict | None:
    decisions = project.path / "decisions"
    if not decisions.is_dir():
        return None
    if decision_snapshot_id:
        p = decisions / f"{decision_snapshot_id}.json"
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
        return None
    snaps = sorted(decisions.glob("DEC-*.json"))
    if not snaps:
        return None
    return json.loads(snaps[-1].read_text(encoding="utf-8"))


def _load_gaps(project: ProjectWorkspace) -> list[dict]:
    gaps: list[dict] = []
    gaps_dir = project.path / "gaps"
    if gaps_dir.is_dir():
        for f in sorted(gaps_dir.glob("gaps-rev-*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    gaps.append(json.loads(line))
    return gaps


def _load_study_designs(project: ProjectWorkspace) -> list[dict]:
    designs: list[dict] = []
    ddir = project.path / "study-designs"
    if ddir.is_dir():
        for f in sorted(ddir.glob("DSN-*.json")):
            designs.append(json.loads(f.read_text(encoding="utf-8")))
    return designs


def build_report_projection(project: ProjectWorkspace, *,
                            graph_revision: int | None = None,
                            decision_snapshot_id: str | None = None) -> dict:
    """Project the active (or named) graph revision into a report view."""
    store = GraphStore.create(project)
    revision = graph_revision or store.active_revision()
    if revision != store.active_revision():
        raise ValueError(
            f"projection of historical revision {revision} not yet supported; "
            f"active revision is {store.active_revision()}")

    manifest = project.manifest()
    sources = store.read_table("sources")
    studies = store.read_table("studies")
    findings = store.read_table("findings")
    outcomes = store.read_table("outcomes")
    claims = store.read_table("claims")
    links = store.read_table("evidence_links")
    audits = store.read_table("audits")

    snapshot = _load_latest_snapshot(project, decision_snapshot_id)

    # outcome aggregation by effect_direction
    outcome_rows: dict[str, dict] = {}
    for o in outcomes:
        outcome_rows[o["outcome_id"]] = {
            "outcome_id": o["outcome_id"],
            "name": o["name"],
            "outcome_type": o["outcome_type"],
            "positive_count": 0, "negative_count": 0, "null_count": 0,
            "evidence_ids": [],
        }
    for f in findings:
        row = outcome_rows.setdefault(f["outcome_id"], {
            "outcome_id": f["outcome_id"], "name": f.get("measure", f["outcome_id"]),
            "outcome_type": "learning", "positive_count": 0,
            "negative_count": 0, "null_count": 0, "evidence_ids": []})
        direction = finding_effect(f)
        if direction == "positive":
            row["positive_count"] += 1
        elif direction == "negative":
            row["negative_count"] += 1
        else:
            row["null_count"] += 1
        row["evidence_ids"].append(f["finding_id"])

    # claim trace via EvidenceLink semantics
    claim_rows: list[dict] = []
    for c in claims:
        c_links = [l for l in links if l["claim_id"] == c["claim_id"]]
        claim_rows.append({
            "claim_id": c["claim_id"],
            "claim": c["text"],
            "claim_type": c["claim_type"],
            "outcome_type": c["primary_outcome_ids"][0] if c["primary_outcome_ids"] else None,
            "evidence_ids": [l["finding_id"] for l in c_links],
            "status": c["status"],
            "supporting_links": [l["evidence_link_id"] for l in c_links
                                 if claim_relation(l) == "support"],
            "contradicting_links": [l["evidence_link_id"] for l in c_links
                                    if claim_relation(l) == "contradict"],
        })

    # evidence view rows (compat) with identity preserved
    study_source: dict[str, str | None] = {}
    for s in studies:
        study_source[s["study_id"]] = s["source_ids"][0] if s.get("source_ids") else None
    evidence_rows = []
    for f in findings:
        f_links = [l for l in links if l["finding_id"] == f["finding_id"]]
        evidence_rows.append({
            "evidence_id": f["finding_id"],
            "source_id": study_source.get(f["study_id"]),
            "study_id": f["study_id"],
            "claim": f.get("raw_result_text", ""),
            "outcome_type": f.get("measure", ""),
            "relation_to_claim": claim_relation(f_links[0]) if f_links else "neutral",
            "effect_direction": finding_effect(f),
            "decision_relation": decision_implication(f_links[0]) if f_links else "neutral",
            "source_location": f.get("source_locator", ""),
            "extensions": {
                "finding_id": f["finding_id"],
                "evidence_link_id": f_links[0]["evidence_link_id"] if f_links else None,
            },
        })

    return {
        "project_id": project.project_id,
        "graph_revision": revision,
        "decision_snapshot_id": snapshot["decision_snapshot_id"] if snapshot else None,
        "decision": snapshot["decision"] if snapshot else "INSUFFICIENT_EVIDENCE",
        "confidence_label": snapshot["confidence_label"] if snapshot else None,
        "research_frame": {
            "education_question": manifest["question"],
            "research_mode": manifest["research_mode"],
            "decision_target": manifest["decision_target"],
        },
        "counts": {
            "source_count": len(sources),
            "study_count": len(studies),
            "finding_count": len(findings),
            "claim_count": len(claims),
            "evidence_link_count": len(links),
        },
        "sources": sources,
        "studies": studies,
        "findings": findings,
        "evidence_links": links,
        "outcomes": list(outcome_rows.values()),
        "claims": claim_rows,
        "evidence": evidence_rows,
        "methodology_reviews": audits,
        "knowledge_gaps": _load_gaps(project),
        "study_designs": _load_study_designs(project),
        "analysis_provenance": [
            {
                "dataset_id": (s.get("extensions") or {}).get("dataset_id"),
                "design_id": (s.get("extensions") or {}).get("design_id"),
                "analysis_run_id": (s.get("extensions") or {}).get("analysis_run_id"),
            }
            for s in sources if s.get("origin") == "project"
        ],
        "provenance": {
            "project_id": project.project_id,
            "graph_revision": revision,
            "projected_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(),
        },
    }


def build_v1_compat_result(project: ProjectWorkspace, *,
                           graph_revision: int | None = None,
                           decision_snapshot_id: str | None = None) -> dict:
    """Map the projection into the V1 result.json shape the renderer expects."""
    proj = build_report_projection(project, graph_revision=graph_revision,
                                   decision_snapshot_id=decision_snapshot_id)
    return {
        "meta": {"engine_version": "2.0.0-dev", "project_id": proj["project_id"]},
        "execution": {"graph_revision": proj["graph_revision"]},
        "research_frame": proj["research_frame"],
        "decision": {
            "verdict": proj["decision"],
            "confidence": proj["confidence_label"],
            "summary": "",
        },
        "outcomes": proj["outcomes"],
        "claims": proj["claims"],
        "sources": proj["sources"],
        "evidence": proj["evidence"],
        "methodology_reviews": proj["methodology_reviews"],
        "conflicts": [],
        "applicability": {},
        "intervention": {},
        "evaluation": {},
        "knowledge_gaps": proj["knowledge_gaps"],
        "study_designs": proj["study_designs"],
        "analysis_provenance": proj["analysis_provenance"],
        "benchmark": {},
        "provenance": proj["provenance"],
    }


def build_localization_pack(projection: dict, *, lang: str,
                            localized_text: dict[str, str]) -> dict:
    """Wrap a projection with a localization layer (language strings)."""
    if lang not in ("zh", "en"):
        raise ValueError(f"unsupported language {lang!r}")
    return {
        "lang": lang,
        "project_id": projection.get("project_id"),
        "graph_revision": projection.get("graph_revision"),
        "decision_snapshot_id": projection.get("decision_snapshot_id"),
        "decision": projection.get("decision"),
        "confidence_label": projection.get("confidence_label"),
        "localized_text": dict(localized_text),
        "counts": projection.get("counts", {}),
    }
