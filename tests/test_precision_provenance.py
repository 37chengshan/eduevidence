"""Precision provenance / no-false-precision tests (P0 science gate).

Forest plot and meta synthesis must never fabricate CI/SE: missing CI yields
null bounds + precision_provenance="not_available", and studies without CI
and without sample size are excluded from pooling with a recorded reason
instead of a default se=0.20.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evidence_graph import (  # noqa: E402
    EvidenceGraph, EvidenceNode, PaperNode, OutcomeNode,
)
from engine.semantics import OutcomeDimension  # noqa: E402


def _graph_with_evidence(nodes: list[EvidenceNode]) -> EvidenceGraph:
    graph = EvidenceGraph(project_id="precision_test")
    graph.add_paper(PaperNode(paper_id="PAP-1", title="t", authors=["A"], year=2024))
    for ev in nodes:
        graph.add_evidence(ev)
    graph.add_outcome(OutcomeNode(outcome_id="OUT-1", name="post",
                                  dimension=OutcomeDimension.INDEPENDENT_TRANSFER))
    return graph


def test_forest_plot_missing_ci_is_null_with_provenance():
    graph = _graph_with_evidence([
        EvidenceNode(evidence_id="EV-1", paper_id="PAP-1",
                     outcome_metric="Delayed exam",
                     outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
                     effect_size={"metric": "Hedges g", "value": 0.5},
                     sample_size=100),
    ])
    pts = graph.get_forest_plot_data()
    assert pts[0]["effect_size"] == 0.5
    assert pts[0]["ci_lower"] is None
    assert pts[0]["ci_upper"] is None
    assert pts[0]["precision_provenance"] == "not_available"
    # no ±0.2 fabrication
    assert pts[0]["ci_lower"] != pytest.approx(0.3)


def test_forest_plot_reported_ci_kept():
    graph = _graph_with_evidence([
        EvidenceNode(evidence_id="EV-1", paper_id="PAP-1",
                     outcome_metric="Delayed exam",
                     outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
                     effect_size={"metric": "Hedges g", "value": 0.5,
                                  "ci_lower": 0.3, "ci_upper": 0.7},
                     sample_size=100),
    ])
    pts = graph.get_forest_plot_data()
    assert pts[0]["ci_lower"] == pytest.approx(0.3)
    assert pts[0]["ci_upper"] == pytest.approx(0.7)
    assert pts[0]["precision_provenance"] == "reported_ci"


def test_meta_synthesis_excludes_no_precision_studies():
    # CI-only study + sample-size-only study both enter; a bare effect with
    # neither CI nor sample size must be excluded with reason.
    graph = _graph_with_evidence([
        EvidenceNode(evidence_id="EV-1", paper_id="PAP-1",
                     outcome_metric="Delayed exam",
                     outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
                     effect_size={"metric": "Hedges g", "value": 0.40,
                                  "ci_lower": 0.30, "ci_upper": 0.50},
                     sample_size=100),
        EvidenceNode(evidence_id="EV-2", paper_id="PAP-1",
                     outcome_metric="Retention",
                     outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
                     effect_size={"metric": "Hedges g", "value": 0.60},
                     sample_size=200),
        EvidenceNode(evidence_id="EV-3", paper_id="PAP-1",
                     outcome_metric="Transfer",
                     outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
                     effect_size={"metric": "Hedges g", "value": 0.50}),
    ])
    syn = graph.compute_meta_synthesis()
    dim = OutcomeDimension.INDEPENDENT_TRANSFER
    assert dim in syn
    assert syn[dim]["studies_count"] == 2
    assert syn[dim]["precision_sources"] == {"reported_ci": 1,
                                             "derived_from_sample_size": 1}
    assert syn[dim]["excluded_no_precision"] == 1
    # pooled g of the two usable studies (not artificially pulled to 0.5)
    assert 0.0 < syn[dim]["pooled_g"] < 1.0


def test_meta_synthesis_no_precision_dimension_omitted():
    graph = _graph_with_evidence([
        EvidenceNode(evidence_id="EV-1", paper_id="PAP-1",
                     outcome_metric="Speed",
                     outcome_dimension=OutcomeDimension.PROCEDURAL_EFFICIENCY,
                     effect_size={"metric": "Hedges g", "value": 0.5}),
    ])
    syn = graph.compute_meta_synthesis()
    assert OutcomeDimension.PROCEDURAL_EFFICIENCY not in syn