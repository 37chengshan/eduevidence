"""Conservative V1 → V2 migration tests.

A V1 Evidence Object becomes at least one Finding + one EvidenceLink; legacy
identity is preserved where present and made explicit where missing; no
heuristic silently invents research facts. Original V1 fixtures stay
byte-for-byte unchanged.
"""

import json
import shutil
from pathlib import Path

import pytest

from engine.migration import migrate_v1_pack

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "ai-coding-assistant"


def _pack_copy(tmp_path) -> Path:
    """Copy the V1 fixture into a temp dir (we must not mutate the original)."""
    pack = tmp_path / "pack"
    shutil.copytree(FIXTURE, pack)
    return pack


def _project_graph(project_id, home):
    from engine.graph_store import GraphStore
    from engine.project import ProjectWorkspace
    ws = ProjectWorkspace.open(home, project_id)
    return GraphStore.create(ws), ws


def test_migration_preserves_v1_ids(tmp_path):
    pack = _pack_copy(tmp_path)
    result = migrate_v1_pack(pack, home=tmp_path, title="Migrated AI coding")
    store, ws = _project_graph(result.project_id, tmp_path)
    sources = store.read_table("sources")
    studies = store.read_table("studies")
    v1_src_ids = {s["source_id"] for s in sources}
    v1_study_ids = {s["study_id"] for s in studies}
    # V1 source ids (S-...) and study ids (STUDY-...) are preserved
    assert "S-2023-Kazemitabaar" in v1_src_ids
    assert "STUDY-Bastani-2025" in v1_study_ids
    assert len(sources) >= 7
    assert len(studies) >= 5


def test_migration_maps_semantics(tmp_path):
    pack = _pack_copy(tmp_path)
    result = migrate_v1_pack(pack, home=tmp_path)
    store, _ = _project_graph(result.project_id, tmp_path)
    findings = store.read_table("findings")
    links = store.read_table("evidence_links")
    v1 = json.loads((pack / "result.json").read_text(encoding="utf-8"))
    v1_ev = {e["evidence_id"]: e for e in v1["evidence"]}
    assert len(findings) >= len(v1_ev)
    assert len(links) >= len(v1_ev)
    for link in links:
        fnd = next(f for f in findings if f["finding_id"] == link["finding_id"])
        # effect_direction stays on the Finding; relation lives on the link
        assert fnd["effect_direction"] in ("positive", "negative", "null")
        assert link["relation_to_claim"] in ("support", "contradict", "neutral")
        assert link["decision_implication"] in (
            "support_adoption", "oppose_adoption", "conditional", "neutral")
        # decision_relation absent in V1 -> deterministic fallback from relation
        if link["relation_to_claim"] == "support":
            assert link["decision_implication"] == "support_adoption"


def test_migration_preserves_claim_ids(tmp_path):
    pack = _pack_copy(tmp_path)
    result = migrate_v1_pack(pack, home=tmp_path)
    store, _ = _project_graph(result.project_id, tmp_path)
    claims = store.read_table("claims")
    v1 = json.loads((pack / "result.json").read_text(encoding="utf-8"))
    v1_claim_ids = {c["claim_id"] for c in v1["claims"]}
    migrated_ids = {c["claim_id"] for c in claims}
    assert v1_claim_ids <= migrated_ids


def test_no_finding_without_study(tmp_path):
    pack = _pack_copy(tmp_path)
    result = migrate_v1_pack(pack, home=tmp_path)
    store, _ = _project_graph(result.project_id, tmp_path)
    study_ids = {s["study_id"] for s in store.read_table("studies")}
    for f in store.read_table("findings"):
        assert f["study_id"] in study_ids


def test_migration_report_exists_and_complete(tmp_path):
    pack = _pack_copy(tmp_path)
    result = migrate_v1_pack(pack, home=tmp_path)
    report = json.loads(result.migration_report_path.read_text(encoding="utf-8"))
    assert report["source_pack"] == str(pack)
    assert report["created_project_id"] == result.project_id
    for key in ("preserved_ids", "generated_ids", "unresolved_studies",
                "downgrades", "warnings"):
        assert key in report


def test_original_fixture_byte_for_byte_unchanged(tmp_path):
    pack = _pack_copy(tmp_path)
    before = (FIXTURE / "result.json").read_bytes()
    migrate_v1_pack(pack, home=tmp_path)
    after = (FIXTURE / "result.json").read_bytes()
    assert before == after


def test_legacy_evidence_without_study_gets_explicit_unresolved_study(tmp_path):
    pack = _pack_copy(tmp_path)
    # synthesize a legacy Evidence Object missing study_id
    result_path = pack / "result.json"
    data = json.loads(result_path.read_text(encoding="utf-8"))
    data["evidence"].append({
        "evidence_id": "E-LEGACY", "source_id": "S-2023-Kazemitabaar",
        "claim": "legacy claim without study identity",
        "outcome_type": "learning",
        "relation_to_claim": "support", "effect_direction": "positive",
        "direction": "support", "study_type": "rct",
        "source_location": "legacy note", "extensions": {},
    })
    result_path.write_text(json.dumps(data), encoding="utf-8")
    result = migrate_v1_pack(pack, home=tmp_path)
    store, _ = _project_graph(result.project_id, tmp_path)
    # an explicit unresolved Study placeholder exists for the legacy object
    studies = store.read_table("studies")
    unresolved = [s for s in studies if s["identity_status"] == "unresolved"]
    assert unresolved, "expected at least one unresolved legacy Study"
    # and the migration report records the warning
    report = json.loads(result.migration_report_path.read_text(encoding="utf-8"))
    assert report["unresolved_studies"]
    assert any("legacy" in w.lower() or "unresolved" in w.lower()
               for w in report["warnings"])


# ---- review-fix regressions ----------------------------------------------

def test_v1_claim_text_preserved_for_multi_evidence_claims(tmp_path):
    pack = _pack_copy(tmp_path)
    data = json.loads((pack / "result.json").read_text(encoding="utf-8"))
    eids = [e["evidence_id"] for e in data["evidence"][:2]]
    data["claims"].append({
        "claim_id": "C-MULTI", "claim": "THE REAL MULTI-EVIDENCE CLAIM",
        "outcome_type": "learning", "evidence_ids": eids, "status": "SUPPORTED",
    })
    (pack / "result.json").write_text(json.dumps(data), encoding="utf-8")
    result = migrate_v1_pack(pack, home=tmp_path)
    store, _ = _project_graph(result.project_id, tmp_path)
    claims = {c["claim_id"]: c for c in store.read_table("claims")}
    assert claims["C-MULTI"]["text"] == "THE REAL MULTI-EVIDENCE CLAIM"
    assert len(claims["C-MULTI"]["primary_outcome_ids"]) == 2


def test_migration_tolerates_missing_claim_text(tmp_path):
    pack = _pack_copy(tmp_path)
    data = json.loads((pack / "result.json").read_text(encoding="utf-8"))
    ev = dict(data["evidence"][0])
    ev["evidence_id"] = "E-NO-TEXT"
    del ev["claim"]
    del ev["source_location"]
    data["evidence"].append(ev)
    (pack / "result.json").write_text(json.dumps(data), encoding="utf-8")
    result = migrate_v1_pack(pack, home=tmp_path)  # must not raise
    store, _ = _project_graph(result.project_id, tmp_path)
    fnd = next(f for f in store.read_table("findings")
               if f["finding_id"] == f"FND-{ev['evidence_id']}")
    assert fnd["raw_result_text"] == "unavailable"
    assert fnd["source_locator"] == "unavailable"


def test_migration_unknown_source_gets_explicit_placeholder(tmp_path):
    pack = _pack_copy(tmp_path)
    data = json.loads((pack / "result.json").read_text(encoding="utf-8"))
    ev = dict(data["evidence"][0])
    ev["evidence_id"] = "E-UNKNOWN-SRC"
    ev["source_id"] = "S-NO-SUCH-SOURCE"
    del ev["study_id"]  # legacy path: no study identity
    data["evidence"].append(ev)
    (pack / "result.json").write_text(json.dumps(data), encoding="utf-8")
    result = migrate_v1_pack(pack, home=tmp_path)
    store, _ = _project_graph(result.project_id, tmp_path)
    placeholders = [s for s in store.read_table("sources")
                    if s["validation_status"] == "failed"
                    and (s.get("extensions") or {}).get("v1_original_source_id") == "S-NO-SUCH-SOURCE"]
    assert placeholders, "expected an explicit failed placeholder Source"
    # the study still references it (no empty source_ids after minItems fix)
    studies = {s["study_id"]: s for s in store.read_table("studies")}
    target = next(s for s in studies.values() if s["independence_key"].startswith("legacy:"))
    assert target["source_ids"]
    report = json.loads(result.migration_report_path.read_text(encoding="utf-8"))
    assert any("unknown source" in w for w in report["warnings"])
