from engine.autoresearch import EvidenceAutoresearchController, IterationStatus, detect_saturation, rank_gap


def low_gain():
    return {
        "unique_eligible_evidence": 0,
        "direct_outcome_findings": 0,
        "decision_boundary_delta": 0,
        "duplicate_rate": 0,
    }


def test_high_dvi_is_not_itself_decision_material():
    priority = rank_gap(
        {"gap_id": "G1", "gap_type": "missing_outcome", "priority": "high"},
        decision={"recommended_action": "PILOT"},
    )
    assert priority.dvi_band.value == "HIGH"
    assert priority.decision_material is False


def test_other_gap_failures_do_not_saturate_current_gap():
    controller = EvidenceAutoresearchController()
    other_history = [
        {
            "gap_id": "G2",
            "strategy": {"experiment_type": strategy},
            "candidate_sources": [],
            "evidence_gain": low_gain(),
        }
        for strategy in (
            "TARGETED_RETRIEVAL",
            "CITATION_CHAINING",
            "TEMPORAL_REFRESH",
            "SOURCE_RECOVERY",
        )
    ]
    result = controller.step(
        project_id="P",
        base_graph_revision=1,
        gaps=[{"gap_id": "G1", "gap_type": "missing_transfer", "priority": "high", "status": "open"}],
        decision={"recommended_action": "PILOT"},
        history=other_history,
        executor=lambda strategy, gap: {
            "validated_evidence_ids": [],
            "candidate_sources": [],
            "evidence_gain": low_gain(),
        },
        ethics_feasible=True,
    )
    assert result.iteration.status == IterationStatus.COMPLETED_NO_GAIN
    assert result.next_action == "next_iteration"


def test_empty_searches_can_count_toward_saturation():
    rows = [
        {
            "strategy": {"experiment_type": strategy},
            "candidate_sources": [],
            "evidence_gain": low_gain(),
        }
        for strategy in ("TARGETED_RETRIEVAL", "CITATION_CHAINING")
    ]
    result = detect_saturation(
        rows,
        available_strategy_types={"TARGETED_RETRIEVAL", "CITATION_CHAINING"},
    )
    assert result.saturated


def test_high_dvi_nonmaterial_saturated_gap_does_not_bridge_to_empirical():
    controller = EvidenceAutoresearchController()
    gap = {"gap_id": "G1", "gap_type": "missing_outcome", "priority": "high", "status": "open"}
    strategies = [
        "TARGETED_RETRIEVAL",
        "CITATION_CHAINING",
        "TEMPORAL_REFRESH",
    ]
    history = [
        {
            "gap_id": "G1",
            "strategy": {"experiment_type": strategy},
            "candidate_sources": [],
            "evidence_gain": low_gain(),
        }
        for strategy in strategies
    ]
    result = controller.step(
        project_id="P",
        base_graph_revision=1,
        gaps=[gap],
        decision={"recommended_action": "PILOT"},
        history=history,
        executor=lambda strategy, gap: {
            "validated_evidence_ids": [],
            "candidate_sources": [],
            "evidence_gain": low_gain(),
        },
        ethics_feasible=True,
    )
    # SOURCE_RECOVERY is the final untried strategy; after this no-gain attempt
    # search is saturated, but empirical transition is forbidden because the
    # gap is not decision-material.
    assert result.priority.dvi_band.value == "HIGH"
    assert result.priority.decision_material is False
    assert result.iteration.status == IterationStatus.SEARCH_SATURATED
    assert result.next_action == "stop_search_saturated"


def test_duplicate_only_commit_is_no_gain_not_fake_revision():
    controller = EvidenceAutoresearchController()
    result = controller.step(
        project_id="P",
        base_graph_revision=7,
        gaps=[{"gap_id": "G1", "gap_type": "missing_transfer", "priority": "high", "status": "open"}],
        decision={"recommended_action": "PILOT"},
        history=[],
        executor=lambda strategy, gap: {
            "validated_evidence_ids": ["F-existing"],
            "candidate_sources": ["SRC-existing"],
            "evidence_gain": {"unique_eligible_evidence": 1},
        },
        graph_commit=lambda ids: None,
    )
    assert result.iteration.new_graph_revision is None
    assert result.iteration.status == IterationStatus.COMPLETED_NO_GAIN
    assert result.iteration.evidence_gain["duplicate_only"] is True
