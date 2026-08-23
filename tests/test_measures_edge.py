"""MEASURES edge idempotency tests (P0 science gate).

Evidence nodes carrying an outcome_id must end up connected to that Outcome
with exactly one MEASURES edge regardless of insertion order or repeated
upserts, and that edge must surface in the ECharts export.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.evidence_graph import (  # noqa: E402
    EvidenceGraph, EvidenceNode, OutcomeNode,
)
from engine.semantics import OutcomeDimension  # noqa: E402


def _ev(eid="EV-1", outcome_id="OUT-1"):
    return EvidenceNode(evidence_id=eid, paper_id="PAP-X",
                        outcome_metric="Delayed exam",
                        outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
                        outcome_id=outcome_id)


def _outcome(oid="OUT-1"):
    return OutcomeNode(outcome_id=oid, name="post",
                       dimension=OutcomeDimension.INDEPENDENT_TRANSFER)


def _measures_edges(graph):
    return [e for e in graph.edges if e.relation == "MEASURES"]


def test_evidence_then_outcome_creates_one_edge():
    graph = EvidenceGraph(project_id="m")
    graph.add_evidence(_ev())
    assert _measures_edges(graph) == []
    graph.add_outcome(_outcome())
    edges = _measures_edges(graph)
    assert len(edges) == 1
    assert edges[0].source_id == "EV-1"
    assert edges[0].target_id == "OUT-1"


def test_outcome_then_evidence_creates_one_edge():
    graph = EvidenceGraph(project_id="m")
    graph.add_outcome(_outcome())
    assert _measures_edges(graph) == []
    graph.add_evidence(_ev())
    edges = _measures_edges(graph)
    assert len(edges) == 1
    assert edges[0].source_id == "EV-1"
    assert edges[0].target_id == "OUT-1"


def test_repeated_upsert_stays_single_edge():
    graph = EvidenceGraph(project_id="m")
    graph.add_evidence(_ev())
    graph.add_outcome(_outcome())
    graph.add_evidence(_ev())  # upsert same evidence again
    graph.add_outcome(_outcome())  # upsert same outcome again
    assert len(_measures_edges(graph)) == 1


def test_multiple_evidence_same_outcome():
    graph = EvidenceGraph(project_id="m")
    graph.add_outcome(_outcome())
    graph.add_evidence(_ev("EV-1"))
    graph.add_evidence(_ev("EV-2"))
    graph.add_evidence(_ev("EV-3"))
    edges = _measures_edges(graph)
    assert len(edges) == 3
    assert {e.source_id for e in edges} == {"EV-1", "EV-2", "EV-3"}


def test_measures_edge_surfaces_in_echarts_export():
    graph = EvidenceGraph(project_id="m")
    graph.add_evidence(_ev())
    graph.add_outcome(_outcome())
    payload = graph.export_echarts_graph()
    assert any(l["source"] == "EV-1" and l["target"] == "OUT-1"
               and l["label"]["formatter"] == "MEASURES" for l in payload["links"])


def test_outcome_id_unknown_creates_no_edge():
    graph = EvidenceGraph(project_id="m")
    graph.add_evidence(_ev(outcome_id="OUT-MISSING"))
    graph.add_outcome(_outcome())
    assert _measures_edges(graph) == []