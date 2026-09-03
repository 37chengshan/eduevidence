from pathlib import Path

from engine.autoresearch import (
    Band,
    EvidenceAutoresearchController,
    IterationStatus,
    NegativeSearchRecord,
    ResearchExperimentType,
    ResearchIteration,
    ResearchMemory,
    ResearchStrategy,
    detect_saturation,
    rank_gaps,
    transition_to_empirical,
)


def test_transfer_gap_ranks_above_low_value_missing_outcome():
    gaps = [
        {"gap_id": "G1", "gap_type": "missing_transfer", "priority": "high", "status": "open"},
        {"gap_id": "G2", "gap_type": "missing_outcome", "priority": "low", "status": "open"},
    ]
    ranked = rank_gaps(gaps, decision={"recommended_action": "pilot"})
    assert ranked[0].gap_id == "G1"
    assert ranked[0].dvi_band == Band.HIGH


def test_negative_search_scope_bounded():
    record = NegativeSearchRecord("N1", "R1", "G1", ("q",), ("web",), 3, 2, 0)
    record.validate()
    try:
        NegativeSearchRecord(
            "N2", "R1", "G1", (), (), 1, 1, 0, conclusion="no_evidence_exists"
        ).validate()
        assert False
    except ValueError:
        pass


def test_no_gain_no_revision():
    controller = EvidenceAutoresearchController()
    gaps = [{"gap_id": "G1", "gap_type": "missing_transfer", "priority": "high", "status": "open"}]
    result = controller.step(
        project_id="P",
        base_graph_revision=3,
        gaps=gaps,
        decision={"recommended_action": "pilot"},
        history=[],
        executor=lambda strategy, gap: {
            "validated_evidence_ids": [],
            "evidence_gain": {"duplicate_rate": 0.2},
        },
    )
    assert result.iteration.new_graph_revision is None
    assert result.iteration.status == IterationStatus.COMPLETED_NO_GAIN


def test_valid_negative_evidence_is_appended_and_creates_revision():
    controller = EvidenceAutoresearchController()
    gaps = [{"gap_id": "G1", "gap_type": "unresolved_conflict", "priority": "high", "status": "open"}]
    seen = []

    def commit(ids):
        seen.extend(ids)
        return 5

    result = controller.step(
        project_id="P",
        base_graph_revision=4,
        gaps=gaps,
        decision={"recommended_action": "pilot"},
        history=[],
        executor=lambda strategy, gap: {
            "validated_evidence_ids": ["E-negative"],
            "evidence_gain": {"unique_eligible_evidence": 1},
        },
        graph_commit=commit,
    )
    assert seen == ["E-negative"]
    assert result.iteration.new_graph_revision == 5


def test_saturation_requires_streak_and_diversity():
    history = [
        {
            "strategy": {"experiment_type": "TARGETED_RETRIEVAL"},
            "evidence_gain": {
                "unique_eligible_evidence": 0,
                "direct_outcome_findings": 0,
                "decision_boundary_delta": 0,
                "duplicate_rate": 0.8,
            },
        },
        {
            "strategy": {"experiment_type": "CITATION_CHAINING"},
            "evidence_gain": {
                "unique_eligible_evidence": 0,
                "direct_outcome_findings": 0,
                "decision_boundary_delta": 0,
                "duplicate_rate": 0.9,
            },
        },
    ]
    saturation = detect_saturation(history)
    assert saturation.saturated
    ok, _ = transition_to_empirical(
        dvi_band="HIGH",
        decision_material=True,
        unresolved=True,
        saturation=saturation,
        ethics_feasible=True,
    )
    assert ok


def test_research_memory_is_append_only(tmp_path: Path):
    memory = ResearchMemory(tmp_path)
    first = ResearchIteration(
        "R1",
        "P",
        0,
        "G",
        ResearchStrategy("S", ResearchExperimentType.TARGETED_RETRIEVAL, "h", "gain"),
    )
    first.complete(IterationStatus.COMPLETED_NO_GAIN)
    memory.append_iteration(first)
    second = ResearchIteration(
        "R2",
        "P",
        0,
        "G",
        ResearchStrategy("S2", ResearchExperimentType.CITATION_CHAINING, "h2", "gain"),
    )
    second.complete(IterationStatus.COMPLETED_NO_GAIN)
    memory.append_iteration(second)
    assert [row["iteration_id"] for row in memory.load_iterations("G")] == ["R1", "R2"]
