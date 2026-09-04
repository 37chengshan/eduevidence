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


def _gap(gap_id, gap_type, priority="high", revision=3, lineage=None):
    row = {
        "gap_id": gap_id,
        "gap_type": gap_type,
        "priority": priority,
        "status": "open",
        "derived_from_graph_revision": revision,
    }
    if lineage:
        row["extensions"] = {"autoresearch_key": lineage}
    return row


def test_transfer_gap_ranks_above_low_value_missing_outcome():
    gaps = [
        _gap("G1", "missing_transfer", revision=3),
        _gap("G2", "missing_outcome", priority="low", revision=3),
    ]
    ranked = rank_gaps(
        gaps,
        decision={"recommended_action": "pilot", "graph_revision": 3},
    )
    assert ranked[0].gap_id == "G1"
    assert ranked[0].dvi_band == Band.HIGH
    try:
        rank_gaps(
            gaps,
            decision={"recommended_action": "pilot", "graph_revision": 2},
        )
        assert False, "stale DecisionSnapshot must fail closed"
    except ValueError as exc:
        assert "stale DecisionSnapshot" in str(exc)


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
    gaps = [_gap("G1", "missing_transfer", revision=3)]
    decision = {"recommended_action": "pilot", "graph_revision": 3}
    result = controller.step(
        project_id="P",
        base_graph_revision=3,
        gaps=gaps,
        decision=decision,
        history=[],
        executor=lambda strategy, gap: {
            "validated_evidence_ids": [],
            "evidence_gain": {"duplicate_rate": 0.2},
        },
    )
    assert result.iteration.new_graph_revision is None
    assert result.iteration.status == IterationStatus.COMPLETED_NO_GAIN
    try:
        controller.step(
            project_id="P",
            base_graph_revision=3,
            gaps=gaps,
            decision=decision,
            history=[],
            executor=lambda strategy, gap: {
                "validated_evidence_ids": [],
                "resolved_gap_ids": ["G1"],
                "evidence_gain": {},
            },
        )
        assert False, "worker-authored resolved state must fail closed"
    except ValueError as exc:
        assert "must not author KnowledgeGap RESOLVED" in str(exc)


def test_valid_negative_evidence_is_appended_and_creates_revision():
    controller = EvidenceAutoresearchController()
    gaps = [_gap("G1", "unresolved_conflict", revision=4)]
    seen = []

    def commit(ids):
        seen.extend(ids)
        return 5

    result = controller.step(
        project_id="P",
        base_graph_revision=4,
        gaps=gaps,
        decision={"recommended_action": "pilot", "graph_revision": 4},
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
    lineage = "KGK-same-semantic-gap"
    first = ResearchIteration(
        "R1",
        "P",
        0,
        "G-old",
        ResearchStrategy("S", ResearchExperimentType.TARGETED_RETRIEVAL, "h", "gain"),
        gap_lineage_key=lineage,
    )
    first.complete(IterationStatus.COMPLETED_NO_GAIN)
    memory.append_iteration(first)
    second = ResearchIteration(
        "R2",
        "P",
        1,
        "G-new",
        ResearchStrategy("S2", ResearchExperimentType.CITATION_CHAINING, "h2", "gain"),
        gap_lineage_key=lineage,
    )
    second.complete(IterationStatus.COMPLETED_NO_GAIN)
    memory.append_iteration(second)
    assert [
        row["iteration_id"]
        for row in memory.load_iterations("G-new", gap_lineage_key=lineage)
    ] == ["R1", "R2"]

    controller = EvidenceAutoresearchController()
    new_gap = _gap("G-new", "missing_transfer", revision=2, lineage=lineage)
    next_strategy = controller.build_strategy(
        controller.select_gap(
            [new_gap],
            {"recommended_action": "pilot", "graph_revision": 2},
        ),
        new_gap,
        memory.load_iterations(),
    )
    assert next_strategy.experiment_type == ResearchExperimentType.TEMPORAL_REFRESH
