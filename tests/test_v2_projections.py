"""V2 projection + V1 compatibility tests."""

import json

from engine.graph_store import GraphStore, GraphMutation
from engine.project import ProjectWorkspace
from engine.projections import (
    build_report_projection, build_v1_compat_result, build_localization_pack,
)
from engine.run import start_run


def _graph(tmp_path):
    ws = ProjectWorkspace.create(tmp_path, question="AI tutor for calculus?",
                                 title="calc", research_mode="evidence_review")
    store = GraphStore.create(ws)
    run = start_run(ws, purpose="p", capabilities=[],
                    execution_backend="sequential_main_agent")
    store.commit(run_id=run["run_id"], reason="bundle",
                 mutation=GraphMutation(
                     upserts={
                         "sources": [{"source_id": "SRC-1", "origin": "external",
                                      "source_type": "journal_article",
                                      "canonical_locator": "https://doi.org/10.0000/1",
                                      "validation_status": "valid",
                                      "content_hash": None, "extensions": {}},
                                     {"source_id": "SRC-2", "origin": "project",
                                      "source_type": "project_study",
                                      "canonical_locator": "project://PRJ-1/datasets/DAT-1",
                                      "validation_status": "valid",
                                      "content_hash": "sha256:x",
                                      "extensions": {"dataset_id": "DAT-1",
                                                     "design_id": "DSN-1",
                                                     "analysis_run_id": "ANL-1"}}],
                         "studies": [{"study_id": "STU-1", "source_ids": ["SRC-1"],
                                      "study_design": "RCT", "population": "u",
                                      "sample_ids": ["S1"], "sample_size": 50,
                                      "intervention": "AI", "comparison": "none",
                                      "independence_key": "k1",
                                      "identity_status": "resolved",
                                      "extensions": {}}],
                         "outcomes": [{"outcome_id": "OUT-1", "name": "post",
                                       "outcome_type": "learning", "extensions": {}},
                                      {"outcome_id": "OUT-2", "name": "completion",
                                       "outcome_type": "task_performance",
                                       "extensions": {}}],
                         "findings": [{"finding_id": "FND-1", "study_id": "STU-1",
                                       "finding_type": "quantitative_effect",
                                       "outcome_id": "OUT-1", "measure": "post",
                                       "timepoint": None, "effect_direction": "positive",
                                       "effect_estimate": None, "raw_result_text": "gained",
                                       "source_locator": "p1", "extensions": {}},
                                      {"finding_id": "FND-2", "study_id": "STU-1",
                                       "finding_type": "quantitative_effect",
                                       "outcome_id": "OUT-2", "measure": "completion",
                                       "timepoint": None, "effect_direction": "null",
                                       "effect_estimate": None, "raw_result_text": "flat",
                                       "source_locator": "p2", "extensions": {}}],
                         "claims": [{"claim_id": "CLM-1", "text": "AI helps",
                                     "claim_type": "effectiveness",
                                     "primary_outcome_ids": ["OUT-1"], "scope": "u",
                                     "created_in_revision": 1, "status": "active",
                                     "extensions": {}}],
                         "evidence_links": [{"evidence_link_id": "LNK-1",
                                             "finding_id": "FND-1", "claim_id": "CLM-1",
                                             "relation_to_claim": "support",
                                             "decision_implication": "support_adoption",
                                             "directness": 2,
                                             "applicability": {"scope_match": "direct"},
                                             "reasoning_note": "r",
                                             "created_in_revision": 1,
                                             "extensions": {}},
                                            {"evidence_link_id": "LNK-2",
                                             "finding_id": "FND-2", "claim_id": "CLM-1",
                                             "relation_to_claim": "neutral",
                                             "decision_implication": "neutral",
                                             "directness": 1,
                                             "applicability": {"scope_match": "partial"},
                                             "reasoning_note": "r",
                                             "created_in_revision": 1,
                                             "extensions": {}}],
                         "audits": [{"audit_id": "AUD-1", "study_id": "STU-1",
                                     "policy_version": "2026-08-12.v2",
                                     "design_quality": 2, "sample_quality": 1,
                                     "measurement_validity": 2, "temporal_strength": 1,
                                     "bias_checks": [], "confounders": [],
                                     "limitations": [], "overall_status": "concern",
                                     "audited_at": "2026-08-12T00:00:00+00:00",
                                     "extensions": {}}],
                     }, retire_ids={}))
    return ws, store


def test_projection_contains_all_surfaces(tmp_path):
    ws, store = _graph(tmp_path)
    proj = build_report_projection(ws)
    assert proj["project_id"] == ws.project_id
    assert proj["graph_revision"] == 1
    assert proj["counts"] == {"source_count": 2, "study_count": 1,
                              "finding_count": 2, "claim_count": 1,
                              "evidence_link_count": 2}
    assert proj["research_frame"]["education_question"] == "AI tutor for calculus?"
    assert proj["decision"] == "INSUFFICIENT_EVIDENCE"
    assert len(proj["outcomes"]) == 2
    assert len(proj["claims"]) == 1
    assert len(proj["sources"]) == 2
    assert len(proj["findings"]) == 2
    assert len(proj["evidence_links"]) == 2
    assert len(proj["methodology_reviews"]) == 1
    assert isinstance(proj["knowledge_gaps"], list)
    assert isinstance(proj["study_designs"], list)
    # analysis provenance surfaces project-local source provenance
    assert len(proj["analysis_provenance"]) == 1
    assert proj["analysis_provenance"][0]["dataset_id"] == "DAT-1"


def test_projection_outcome_aggregation_uses_effect_direction(tmp_path):
    ws, _ = _graph(tmp_path)
    proj = build_report_projection(ws)
    by_id = {o["outcome_id"]: o for o in proj["outcomes"]}
    assert by_id["OUT-1"]["positive_count"] == 1
    assert by_id["OUT-2"]["null_count"] == 1


def test_v1_compat_evidence_rows_preserve_identity(tmp_path):
    ws, _ = _graph(tmp_path)
    compat = build_v1_compat_result(ws)
    assert compat["research_frame"]["education_question"] == "AI tutor for calculus?"
    rows = {e["evidence_id"]: e for e in compat["evidence"]}
    assert "FND-1" in rows
    assert rows["FND-1"]["extensions"]["finding_id"] == "FND-1"
    assert rows["FND-1"]["extensions"]["evidence_link_id"] == "LNK-1"
    assert rows["FND-1"]["relation_to_claim"] == "support"
    assert rows["FND-2"]["extensions"]["evidence_link_id"] == "LNK-2"
    # V1 renderer expects these top-level keys
    for key in ("meta", "execution", "research_frame", "decision", "outcomes",
                "claims", "sources", "evidence", "methodology_reviews",
                "conflicts", "applicability", "intervention", "evaluation",
                "provenance"):
        assert key in compat


def test_localization_pack(tmp_path):
    ws, _ = _graph(tmp_path)
    proj = build_report_projection(ws)
    pack = build_localization_pack(proj, lang="zh",
                                   localized_text={"decision": "决定"})
    assert pack["lang"] == "zh"
    assert pack["localized_text"]["decision"] == "决定"
    assert pack["graph_revision"] == 1
    try:
        build_localization_pack(proj, lang="fr", localized_text={})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_projection_does_not_mutate_graph(tmp_path):
    ws, store = _graph(tmp_path)
    before = store.canonical_hash()
    build_report_projection(ws)
    build_v1_compat_result(ws)
    assert store.canonical_hash() == before


# ---- V2 renderer surfaces (Task 23) ---------------------------------------

def _render(ws, **over):
    """Render a full HTML report from a V2 projection (single-language path)."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "build_report", "visualization/eduevidence-report/scripts/build_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_v2_report_contains_project_surfaces(tmp_path):
    ws, store = _graph(tmp_path)
    proj = build_report_projection(ws)
    compat = build_v1_compat_result(ws)
    # reuse the demo renderer entry to produce HTML from compat shape
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_report", "visualization/eduevidence-report/scripts/build_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    compat["project_id"] = proj["project_id"]
    compat["graph_revision"] = proj["graph_revision"]
    compat["decision_snapshot_id"] = proj["decision_snapshot_id"]
    compat["knowledge_gaps"] = proj["knowledge_gaps"]
    compat["study_designs"] = proj["study_designs"]
    compat["analysis_provenance"] = proj["analysis_provenance"]
    compat["decision_diff"] = {
        "from_graph_revision": 0, "to_graph_revision": 1,
        "action_changed": True, "confidence_changed": True,
        "changed_claims": ["CLM-1"], "resolved_gaps": [], "new_gaps": ["GAP-1"],
    }
    viz = mod.visualization_decisions(compat, {})
    html_zh = mod.render_html(compat, compat, {}, {}, {}, {}, {}, {}, "claude", viz)
    assert str(proj["project_id"]) in html_zh
    assert "Graph revision" in html_zh or "证据图版本" in html_zh
    assert "GAP-1" in html_zh
    assert "DSN-" in html_zh or "DAT-1" in html_zh
    assert "resolved" in html_zh


def test_v1_result_renders_without_v2_surfaces(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "build_report", "visualization/eduevidence-report/scripts/build_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    import json
    v1 = json.loads((Path(tmp_path).parent.parent / "examples" / "ai-coding-assistant" /
                     "result.json").read_text(encoding="utf-8")) if False else None
    from pathlib import Path
    v1_path = Path(__file__).resolve().parent.parent / "examples" / "ai-coding-assistant" / "result.json"
    v1 = json.loads(v1_path.read_text(encoding="utf-8"))
    viz = mod.visualization_decisions(v1, {})
    html = mod.render_html(v1, v1, {}, {}, {}, {}, {}, {}, "claude", viz)
    assert "Project & Research History" not in html
    assert "项目与研究历史" not in html
    assert "CLM-" in html or "C-00" in html  # report still renders claims
