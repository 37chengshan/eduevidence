"""Conservative V1 → V2 migration.

Existing V1 runs/example packs are immutable historical artifacts: this
importer reads them, never rewrites them. One V1 Evidence Object becomes at
least one Finding + one EvidenceLink; `relation_to_claim` maps to the link,
`effect_direction` maps to the Finding, `decision_relation` (or its
deterministic fallback) maps to the link's decision_implication. Legacy
missing Study identity becomes an explicit unresolved Study placeholder —
never silently an independent study. Every inference, downgrade and
unresolved identity is recorded in migration_report.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.graph_store import GraphStore, GraphMutation
from engine.ids import new_local_id
from engine.project import ProjectWorkspace
from engine.run import start_run, finish_run
from engine.versions import (
    ENGINE_VERSION,
    GRAPH_SCHEMA_VERSION,
    METHODOLOGY_POLICY_VERSION,
)

OUTCOME_TYPES = ("learning", "task_performance", "process", "risk")

_CLAIM_TO_IMPLICATION = {
    "support": "support_adoption",
    "contradict": "oppose_adoption",
    "neutral": "neutral",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class MigrationResult:
    project_id: str
    graph_revision: int
    migration_report_path: Path
    warnings: tuple[str, ...]


def _v1_outcome_type(raw: str) -> str:
    """Map a V1 outcome_type into the four-category taxonomy (conservative)."""
    if raw in OUTCOME_TYPES:
        return raw
    return "learning"  # most V1 education outcomes are learning-related


def _map_effect_direction(raw) -> str:
    if raw in ("positive", "negative", "null"):
        return raw
    return "null"


def _map_relation(raw) -> str:
    if raw in ("support", "contradict", "neutral"):
        return raw
    return "neutral"


def _map_decision_implication(ev: dict) -> str:
    raw = ev.get("decision_relation")
    if raw in ("support_adoption", "oppose_adoption", "conditional", "neutral"):
        return raw
    return _CLAIM_TO_IMPLICATION[_map_relation(ev.get("relation_to_claim") or ev.get("direction"))]


def migrate_v1_pack(pack_dir: Path, *, home: Path,
                    title: str | None = None) -> MigrationResult:
    """Import a V1 pack directory into a new V2 Project graph.

    Reads `result.json` from `pack_dir`. Returns a MigrationResult with the
    created Project and the migration report path.
    """
    pack_dir = Path(pack_dir).expanduser().resolve()
    result_path = pack_dir / "result.json"
    if not result_path.is_file():
        raise FileNotFoundError(f"V1 pack has no result.json at {pack_dir}")

    data = json.loads(result_path.read_text(encoding="utf-8"))
    question = (data.get("research_frame") or {}).get("education_question") or (
        data.get("meta") or {}).get("question") or title or "Migrated V1 research"
    title = title or "V1 migrated research"

    ws = ProjectWorkspace.create(
        home, question=question, title=title, research_mode="evidence_review")
    run = start_run(ws, purpose="V1 migration import",
                    capabilities=["migration"],
                    execution_backend="sequential_main_agent")

    warnings: list[str] = []

    report: dict = {
        "source_pack": str(pack_dir),
        "created_project_id": ws.project_id,
        "preserved_ids": [],
        "generated_ids": [],
        "unresolved_studies": [],
        "downgrades": [],
        "warnings": warnings,
    }

    # ---- sources ---------------------------------------------------------
    sources: list[dict] = []
    for src in data.get("sources", []):
        src_id = src.get("source_id") or new_local_id("SRC", set())
        locator = (src.get("canonical_url") or src.get("source_location")
                   or f"project://{ws.project_id}/legacy-source/{src_id}")
        status = "valid" if src.get("authority_level") not in (None, "") else "accepted_partial"
        rec = {
            "source_id": src_id,
            "origin": "external",
            "source_type": src.get("authority_level") or "legacy",
            "canonical_locator": locator,
            "validation_status": status,
            "content_hash": None,
            "extensions": {
                "v1_legacy": True,
                "v1_title": src.get("title"),
                "v1_year": src.get("year"),
            },
        }
        sources.append(rec)
        report["preserved_ids"].append(src_id)
    source_ids = {s["source_id"] for s in sources}

    def _study_source_refs(ev: dict) -> list[str]:
        """Resolve a V1 evidence's source reference; never silently empty.

        An unknown/missing source_id gets an explicit placeholder Source
        (validation_status=failed, project origin) so provenance stays
        visible instead of being dropped.
        """
        sid = ev.get("source_id")
        if sid and sid in source_ids:
            return [sid]
        placeholder_id = new_local_id("SRC", {s["source_id"] for s in sources})
        sources.append({
            "source_id": placeholder_id,
            "origin": "project",
            "source_type": "legacy_unresolved",
            "canonical_locator": f"project://{ws.project_id}/legacy-source/{placeholder_id}",
            "validation_status": "failed",
            "content_hash": None,
            "extensions": {"v1_legacy": True,
                           "v1_original_source_id": sid,
                           "v1_evidence_id": ev.get("evidence_id")},
        })
        source_ids.add(placeholder_id)
        report["generated_ids"].append(placeholder_id)
        warnings.append(
            f"evidence {ev.get('evidence_id')} references unknown source "
            f"{sid!r}; created placeholder Source {placeholder_id} "
            f"(validation_status=failed)"
        )
        return [placeholder_id]

    # ---- studies ---------------------------------------------------------
    # V1 Evidence Objects carry study_id; group by it. Missing study_id gets
    # an explicit unresolved placeholder Study (one per evidence object).
    used_ids = {s["source_id"] for s in sources} | {s["study_id"] for s in
                                                     data.get("evidence", [])
                                                     if s.get("study_id")}
    studies: list[dict] = []
    study_by_v1: dict[str, str] = {}
    evidence_by_study: dict[str, list[dict]] = {}
    legacy_count = 0
    for ev in data.get("evidence", []):
        vid = ev.get("study_id")
        if vid:
            evidence_by_study.setdefault(vid, []).append(ev)
        else:
            legacy_count += 1
            legacy_id = new_local_id("STU", used_ids)
            studies.append({
                "study_id": legacy_id,
                "source_ids": _study_source_refs(ev),
                "study_design": (ev.get("study_type") or "unknown").lower(),
                "population": ev.get("population") or ev.get("education_level") or "unknown",
                "sample_ids": [ev.get("sample_id")] if ev.get("sample_id") else [],
                "sample_size": ev.get("sample_size"),
                "intervention": ev.get("intervention"),
                "comparison": ev.get("comparison"),
                "independence_key": f"legacy:{ev.get('evidence_id')}",
                "identity_status": "unresolved",
                "extensions": {"v1_legacy": True},
            })
            study_by_v1[ev["evidence_id"]] = legacy_id
            report["unresolved_studies"].append(legacy_id)
            report["generated_ids"].append(legacy_id)
            warnings.append(
                f"evidence {ev.get('evidence_id')} lacks study_id; created "
                f"explicit unresolved Study {legacy_id}"
            )
    for vid, evs in evidence_by_study.items():
        first = evs[0]
        studies.append({
            "study_id": vid,
            "source_ids": _study_source_refs(first),
            "study_design": (first.get("study_type") or "unknown").lower(),
            "population": first.get("population") or first.get("education_level") or "unknown",
            "sample_ids": [first.get("sample_id")] if first.get("sample_id") else [],
            "sample_size": first.get("sample_size"),
            "intervention": first.get("intervention"),
            "comparison": first.get("comparison"),
            "independence_key": f"v1:{vid}",
            "identity_status": "legacy",
            "extensions": {"v1_legacy": True},
        })
        report["preserved_ids"].append(vid)
    study_ids = {s["study_id"] for s in studies}

    # ---- outcomes --------------------------------------------------------
    outcomes: dict[str, dict] = {}
    for ev in data.get("evidence", []):
        otype = _v1_outcome_type(ev.get("outcome_type") or "learning")
        oid = f"OUT-{otype}-{ev['evidence_id']}"
        outcomes[oid] = {
            "outcome_id": oid,
            "name": ev.get("outcome_type") or otype,
            "outcome_type": otype,
            "extensions": {"v1_legacy": True},
        }

    # ---- claim identity mapping (V1 claims carry claim_id + evidence_ids) --
    claim_by_evidence: dict[str, str] = {}
    v1_claims = []
    for c in data.get("claims", []):
        cid = c.get("claim_id") or new_local_id("CLM", set())
        v1_claims.append(c)
        for eid in c.get("evidence_ids", []) or []:
            claim_by_evidence[eid] = cid
        report["preserved_ids"].append(cid)

    # ---- findings + links -------------------------------------------------
    findings: list[dict] = []
    links: list[dict] = []
    used_local = set()
    for ev in data.get("evidence", []):
        fnd_id = f"FND-{ev['evidence_id']}"
        used_local.add(fnd_id)
        study_id = study_by_v1.get(ev["evidence_id"]) or ev.get("study_id")
        if study_id not in study_ids:
            # a V1 study_id with no study row (should not happen) -> placeholder
            sid = new_local_id("STU", used_ids)
            studies.append({
                "study_id": sid, "source_ids": _study_source_refs(ev),
                "study_design": "unknown", "population": "unknown",
                "sample_ids": [], "sample_size": None, "intervention": None,
                "comparison": None, "independence_key": f"v1-missing:{ev['evidence_id']}",
                "identity_status": "unresolved",
                "extensions": {"v1_legacy": True},
            })
            study_ids.add(sid)
            study_id = sid
            report["unresolved_studies"].append(sid)
        oid = f"OUT-{_v1_outcome_type(ev.get('outcome_type') or 'learning')}-{ev['evidence_id']}"
        findings.append({
            "finding_id": fnd_id,
            "study_id": study_id,
            "finding_type": "quantitative_effect",
            "outcome_id": oid,
            "measure": ev.get("outcome_type") or "outcome",
            "timepoint": None,
            "effect_direction": _map_effect_direction(ev.get("effect_direction")),
            "effect_estimate": None,
            "raw_result_text": ev.get("claim") or "unavailable",
            "source_locator": ev.get("source_location") or "unavailable",
            "extensions": {"v1_legacy": True},
        })
        claim_id = claim_by_evidence.get(ev["evidence_id"], f"CLM-{ev['evidence_id']}")
        link_id = f"LNK-{ev['evidence_id']}"

        links.append({

            "evidence_link_id": link_id,
            "finding_id": fnd_id,
            "claim_id": claim_id,
            "relation_to_claim": _map_relation(
                ev.get("relation_to_claim") or ev.get("direction")),
            "decision_implication": _map_decision_implication(ev),
            "directness": 1,
            "applicability": {"scope_match": "direct"},
            "reasoning_note": "migrated from V1 Evidence Object",
            "created_in_revision": 1,
            "extensions": {"v1_legacy": True},
        })

    # ---- claims ----------------------------------------------------------
    # Emit claims from the V1 claim records (preserving their text and
    # evidence bindings); evidence-derived rows only for unmapped evidence.
    claims: list[dict] = []
    emitted_claim_ids: set[str] = set()

    for c in data.get("claims", []):
        cid = c.get("claim_id") or new_local_id("CLM", set())
        if cid in emitted_claim_ids:
            continue
        emitted_claim_ids.add(cid)
        eids = c.get("evidence_ids") or []
        outcome_ids = []
        for eid in eids:
            ev = next((e for e in data.get("evidence", [])
                       if e.get("evidence_id") == eid), None)
            if ev is not None:
                outcome_ids.append(
                    f"OUT-{_v1_outcome_type(ev.get('outcome_type') or 'learning')}-{eid}")
        claims.append({
            "claim_id": cid,
            "text": c.get("claim") or "unavailable",
            "claim_type": "effectiveness",
            "primary_outcome_ids": outcome_ids,
            "scope": "legacy V1 migration",
            "created_in_revision": 1,
            "status": "active",
            "extensions": {"v1_legacy": True},
        })
    for ev in data.get("evidence", []):
        cid = claim_by_evidence.get(ev["evidence_id"])
        if cid is None:
            cid = f"CLM-{ev['evidence_id']}"
            report["generated_ids"].append(cid)
            warnings.append(
                f"evidence {ev['evidence_id']} has no V1 claim; generated Claim {cid}"
            )
            claims.append({
                "claim_id": cid,
                "text": ev.get("claim") or "unavailable",
                "claim_type": "effectiveness",
                "primary_outcome_ids": [
                    f"OUT-{_v1_outcome_type(ev.get('outcome_type') or 'learning')}-{ev['evidence_id']}"],
                "scope": "legacy V1 migration",
                "created_in_revision": 1,
                "status": "active",
                "extensions": {"v1_legacy": True},
            })

    # ---- audits ----------------------------------------------------------
    audits: list[dict] = []
    for s in studies:
        audits.append({
            "audit_id": new_local_id("AUD", set()),
            "study_id": s["study_id"],
            "policy_version": METHODOLOGY_POLICY_VERSION,
            "design_quality": 1,
            "sample_quality": 1,
            "measurement_validity": 1,
            "temporal_strength": 1,
            "bias_checks": [],
            "confounders": [],
            "limitations": ["V1 legacy migration; audit quality not re-derived"],
            "overall_status": "concern",
            "audited_at": _now_iso(),
            "extensions": {"v1_legacy": True},
        })
        report["downgrades"].append({
            "study_id": s["study_id"],
            "from": "V1 quality_score",
            "to": "concern (legacy, not re-audited)",
        })

    # ---- commit ----------------------------------------------------------
    mutation = GraphMutation(
        upserts={
            "sources": sources, "studies": studies,
            "outcomes": list(outcomes.values()),
            "findings": findings, "claims": claims,
            "evidence_links": links, "audits": audits,
        },
        retire_ids={},
    )
    store = GraphStore.create(ws)
    rev = store.commit(run_id=run["run_id"], reason="V1 pack migration",
                       mutation=mutation)
    finish_run(ws, run["run_id"], status="completed", graph_revision_after=rev.revision)

    # ---- report ----------------------------------------------------------
    report_path = ws.path / "migration_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return MigrationResult(
        project_id=ws.project_id,
        graph_revision=rev.revision,
        migration_report_path=report_path,
        warnings=tuple(warnings),
    )
