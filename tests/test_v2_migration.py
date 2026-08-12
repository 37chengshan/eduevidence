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
