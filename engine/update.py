"""Close the Full Research Cycle: validated project analysis → graph evidence.

One atomic mutation: a project-local Source (portable project:// locator,
derived from DatasetAsset + AnalysisRun provenance), one Study, its
Findings, MethodologyAudit, and contextual Claims/Links commit in ONE graph
revision — never one revision per Finding.

AnalysisRun.status must be `validated`; otherwise ANALYSIS_INVALID is
returned and the graph stays unchanged. The engine derives the Source; the
caller supplies schema-valid Study/Findings/Audit/Claims/Links.
"""

from __future__ import annotations

from datetime import datetime, timezone

from engine.contracts import validate_record
from engine.graph_store import GraphStore, GraphMutation, GraphRevision
from engine.project import ProjectWorkspace


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def project_study_mutation(*, project: ProjectWorkspace,
                           design: dict,
                           dataset_asset: dict,
                           analysis_run: dict,
                           study: dict,
                           findings: list[dict],
                           methodology_audit: dict,
                           claims: list[dict],
                           links: list[dict]) -> GraphMutation:
    """Build the bundle mutation; raises ValueError on invalid inputs.

    The derived project-local Source carries a portable `project://` locator
    referencing the dataset; raw filesystem paths stay provenance metadata.
    """
    if analysis_run.get("status") != "validated":
        raise ValueError(
            f"ANALYSIS_INVALID: AnalysisRun {analysis_run.get('analysis_run_id')} "
            f"status {analysis_run.get('status')!r} is not 'validated'; graph "
            f"unchanged")

    source_id = f"SRC-{dataset_asset['dataset_id']}"
    source = {
        "source_id": source_id,
        "origin": "project",
        "source_type": "project_study",
        "canonical_locator": (
            f"project://{project.project_id}/datasets/{dataset_asset['dataset_id']}"),
        "validation_status": "valid",
        "content_hash": dataset_asset["content_hash"],
        "extensions": {
            "dataset_id": dataset_asset["dataset_id"],
            "design_id": design["design_id"],
            "analysis_run_id": analysis_run["analysis_run_id"],
            "provenance": {
                "provider": (analysis_run.get("extensions") or {}).get("provider"),
                "software": (analysis_run.get("extensions") or {}).get("software"),
            },
        },
    }
    errors = validate_record("source", source)
    if errors:
        raise ValueError(f"derived project source invalid: {errors}")

    # validate the whole bundle before touching the store
    for label, schema, rec in (
        ("study", "study", study),
        ("audit", "methodology-audit", methodology_audit),
    ):
        errs = validate_record(schema, rec)
        if errs:
            raise ValueError(f"{label} invalid: {errs}")
    for f in findings:
        errs = validate_record("finding", f)
        if errs:
            raise ValueError(f"finding {f.get('finding_id')} invalid: {errs}")
    for c in claims:
        errs = validate_record("claim", c)
        if errs:
            raise ValueError(f"claim {c.get('claim_id')} invalid: {errs}")
    for l in links:
        errs = validate_record("evidence-link", l)
        if errs:
            raise ValueError(f"evidence_link {l.get('evidence_link_id')} invalid: {errs}")

    return GraphMutation(
        upserts={
            "sources": [source],
            "studies": [study],
            "findings": findings,
            "audits": [methodology_audit],
            "claims": claims,
            "evidence_links": links,
        },
        retire_ids={},
    )


def commit_project_study(*, store: GraphStore, run_id: str,
                         design: dict, dataset_asset: dict,
                         analysis_run: dict, study: dict,
                         findings: list[dict], methodology_audit: dict,
                         claims: list[dict], links: list[dict]) -> GraphRevision:
    """Validate the bundle and commit it as exactly ONE graph revision."""
    mutation = project_study_mutation(
        project=store.project, design=design, dataset_asset=dataset_asset,
        analysis_run=analysis_run, study=study, findings=findings,
        methodology_audit=methodology_audit, claims=claims, links=links)
    return store.commit(run_id=run_id, reason="project study evidence",
                        mutation=mutation)
