import json

import pytest

from engine.autoresearch import ResearchBudget, ResearchExperimentType, ResearchStrategy, rank_gap
from scripts.research_auto_cli import (
    _iteration_id,
    _request,
    _validate_outcome_budget,
    _validate_outcome_identity,
    _writer_lock,
)


def strategy():
    return ResearchStrategy(
        "STRAT-1",
        ResearchExperimentType.TARGETED_RETRIEVAL,
        "find direct evidence",
        "directness",
        ResearchBudget(max_queries=2, max_candidates=4, max_fulltext_fetches=2),
    )


def test_request_preassigns_iteration_and_negative_search_identity():
    gap = {"gap_id": "G1", "gap_type": "missing_transfer", "priority": "high"}
    priority = rank_gap(gap)
    value = _request(priority, strategy(), "P1", 7, 3, gap)
    assert value["iteration_id"] == "RIT-0003"
    assert value["gap_id"] == "G1"
    assert value["contract"]["negative_search_research_iteration_id"] == "RIT-0003"
    assert value["contract"]["negative_search_gap_id"] == "G1"
    assert value["contract"]["required_measurements"] == [
        "query_count",
        "candidate_count",
        "fetched_count",
    ]


def test_budget_measurements_are_required_not_optional():
    with pytest.raises(ValueError, match="must report query_count"):
        _validate_outcome_budget({}, strategy())


def test_budget_measurements_fail_on_overrun_and_inconsistent_counts():
    with pytest.raises(ValueError, match="query_count=3"):
        _validate_outcome_budget(
            {"query_count": 3, "candidate_count": 4, "fetched_count": 2}, strategy()
        )
    with pytest.raises(ValueError, match="fetched_count cannot exceed"):
        _validate_outcome_budget(
            {"query_count": 1, "candidate_count": 1, "fetched_count": 2}, strategy()
        )


def test_budget_measurements_validate_candidate_and_attempt_lists():
    with pytest.raises(ValueError, match="candidate_sources length"):
        _validate_outcome_budget(
            {
                "query_count": 1,
                "candidate_count": 1,
                "fetched_count": 1,
                "candidate_sources": ["S1", "S2"],
            },
            strategy(),
        )
    with pytest.raises(ValueError, match="search_attempts length"):
        _validate_outcome_budget(
            {
                "query_count": 1,
                "candidate_count": 1,
                "fetched_count": 1,
                "search_attempts": [{}, {}],
            },
            strategy(),
        )


def test_executor_identity_if_supplied_must_match_request():
    _validate_outcome_identity(
        {"iteration_id": "RIT-0001", "gap_id": "G1"},
        expected_iteration_id="RIT-0001",
        expected_gap_id="G1",
    )
    with pytest.raises(ValueError, match="iteration_id"):
        _validate_outcome_identity(
            {"iteration_id": "RIT-0002"},
            expected_iteration_id="RIT-0001",
            expected_gap_id="G1",
        )


def test_writer_lock_is_exclusive_and_cleans_up(tmp_path):
    lock = tmp_path / ".writer.lock"
    with _writer_lock(lock):
        payload = json.loads(lock.read_text(encoding="utf-8"))
        assert payload["pid"] > 0
        with pytest.raises(RuntimeError, match="writer already active"):
            with _writer_lock(lock):
                pass
    assert not lock.exists()


def test_iteration_id_is_stable():
    assert _iteration_id(42) == "RIT-0042"
