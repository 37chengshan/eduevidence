"""tests/test_evidence_graph.py — Tests for EvidenceGraph, EventBus, and Semantics."""
from __future__ import annotations

import json
from engine.events import event_bus
from engine.semantics import OutcomeClassifier, OutcomeDimension
from engine.evidence_graph import (
    EvidenceGraph,
    PaperNode,
    EvidenceNode,
    OutcomeNode,
    ClaimNode,
    RiskNode,
    GapNode,
    DecisionNode,
)


def test_semantics_classifier():
    assert OutcomeClassifier.classify("Task completion time") == OutcomeDimension.PROCEDURAL_EFFICIENCY
    assert OutcomeClassifier.classify("代码编写速度与错误率") == OutcomeDimension.PROCEDURAL_EFFICIENCY
    assert OutcomeClassifier.classify("Delayed unassisted retention test") == OutcomeDimension.INDEPENDENT_TRANSFER
    assert OutcomeClassifier.classify("期末闭卷考试独立迁移能力") == OutcomeDimension.INDEPENDENT_TRANSFER
    assert OutcomeClassifier.classify("Conceptual mental model and abstraction") == OutcomeDimension.CONCEPTUAL_MASTERY
    assert OutcomeClassifier.classify("Student anxiety and cognitive engagement") == OutcomeDimension.AFFECTIVE_PSYCHOSOCIAL
    assert OutcomeClassifier.classify("Family socioeconomic burden") == OutcomeDimension.SOCIOECONOMIC_POLICY


def test_event_bus():
    received = []
    def sub(ev):
        received.append(ev)

    event_bus.subscribe(sub)
    event_bus.publish("test_event", {"value": 42})
    assert len(received) >= 1
    assert received[-1]["type"] == "test_event"
    assert received[-1]["payload"]["value"] == 42
    event_bus.unsubscribe(sub)


def test_evidence_graph_ssot_flow():
    graph = EvidenceGraph(project_id="test_ai_coding")

    # 1. Add Papers
    p1 = graph.add_paper(PaperNode(
        paper_id="PAP-BASTANI-2025",
        title="Generative AI in Education: Evidence from a Randomized Controlled Trial",
        authors=["Bastani, H.", "Bastani, O."],
        year=2025,
        venue="PNAS",
        authority_tier=1,
    ))
    p2 = graph.add_paper(PaperNode(
        paper_id="PAP-KAZEM-2023",
        title="Studying the Effect of AI Code Generators on Novice Programmers",
        authors=["Kazemitabaar, M."],
        year=2023,
        venue="ACM CHI 2023",
        authority_tier=1,
    ))

    # 2. Add Evidence Nodes
    ev1 = graph.add_evidence(EvidenceNode(
        evidence_id="EV-001",
        paper_id=p1.paper_id,
        outcome_metric="Task Completion Velocity",
        effect_size={"metric": "Hedges g", "value": 0.68, "ci_lower": 0.45, "ci_upper": 0.91, "p_value": 0.001},
        sample_size=1200,
        direction="SUPPORTS",
        wwc_rating="Meets Standards without Reservations",
    ))
    assert ev1.outcome_dimension == OutcomeDimension.PROCEDURAL_EFFICIENCY

    ev2 = graph.add_evidence(EvidenceNode(
        evidence_id="EV-002",
        paper_id=p1.paper_id,
        outcome_metric="Delayed Solo Exam Score",
        effect_size={"metric": "Hedges g", "value": -0.34, "ci_lower": -0.52, "ci_upper": -0.16, "p_value": 0.01},
        sample_size=1200,
        direction="CONTRADICTS",
        wwc_rating="Meets Standards without Reservations",
    ))
    assert ev2.outcome_dimension == OutcomeDimension.INDEPENDENT_TRANSFER

    # 3. Add Claims
    c1 = graph.add_claim(ClaimNode(
        claim_id="CLM-001",
        statement="AI coding assistant accelerates novice task completion velocity",
        outcome_dimension=OutcomeDimension.PROCEDURAL_EFFICIENCY,
        status="SUPPORTED",
        pooled_effect_g=0.68,
        evidence_ids=["EV-001"],
    ))
    c2 = graph.add_claim(ClaimNode(
        claim_id="CLM-002",
        statement="AI coding assistant improves unassisted long-term conceptual retention",
        outcome_dimension=OutcomeDimension.INDEPENDENT_TRANSFER,
        status="CONTRADICTED",
        pooled_effect_g=-0.34,
        evidence_ids=["EV-002"],
    ))

    # 4. Add Risk & Gap
    r1 = graph.add_risk(RiskNode(
        risk_id="RSK-001",
        risk_type="Scaffolding Dependency Trap",
        severity="HIGH",
        description="Students perform well with AI active, but suffer a 17% deficit on solo retention exams.",
        mitigation="Enforce 'Explain Before Code' and structured fading protocol.",
        triggered_by_evidence_ids=["EV-002"],
    ))

    g1 = graph.add_gap(GapNode(
        gap_id="GAP-001",
        gap_type="Measurement/Retention Gap",
        description="Lack of long-term longitudinal evaluations (t > 12 weeks) measuring cognitive retention in CS1.",
        target_outcome="Delayed Concept Retention",
        recommended_trial_design="12-Week Cluster Randomized DID Trial with fading scaffold",
    ))

    # 5. Set Decision
    dec = graph.set_decision(DecisionNode(
        decision_id="DEC-001",
        verdict="PILOT",
        confidence_score=0.88,
        rationale="Supported for procedural acceleration; rejected for open unassisted summative testing.",
        applicability_boundary="Introductory CS1 courses with strict scaffolding fade and no-AI transfer exams.",
    ))

    # Test serialization roundtrip
    serialized = graph.to_json()
    reloaded = EvidenceGraph.from_json(serialized)
    assert len(reloaded.papers) == 2
    assert len(reloaded.evidence) == 2
    assert len(reloaded.claims) == 2
    assert len(reloaded.risks) == 1
    assert len(reloaded.gaps) == 1
    assert reloaded.decision is not None
    assert reloaded.decision.verdict == "PILOT"

    # Test ECharts export
    echarts_payload = graph.export_echarts_graph()
    assert len(echarts_payload["nodes"]) >= 7
    assert len(echarts_payload["links"]) >= 4

    # Test Meta Synthesis
    synthesis = graph.compute_meta_synthesis()
    assert OutcomeDimension.PROCEDURAL_EFFICIENCY in synthesis
    assert synthesis[OutcomeDimension.PROCEDURAL_EFFICIENCY]["pooled_g"] == 0.68
    assert OutcomeDimension.INDEPENDENT_TRANSFER in synthesis
    assert synthesis[OutcomeDimension.INDEPENDENT_TRANSFER]["pooled_g"] == -0.34
