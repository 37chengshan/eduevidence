"""engine/evidence_graph.py — Unified SSOT Evidence Graph for EduEvidence.

Provides a unified, strongly-typed graph data model holding all 7 core node entities:
1. PaperNode (Sources & Bibliographic records)
2. EvidenceNode (Empirical findings, Hedges' g effect sizes, sample sizes, WWC ratings)
3. OutcomeNode (Ontology-mapped outcome dimensions)
4. ClaimNode (Hypothesized assertions & pooled status)
5. RiskNode (Methodological & social science pitfalls, e.g. Scaffolding Dependency)
6. GapNode (Identified research gaps & future trial recommendations)
7. DecisionNode (Adjudicated four-state verdict, confidence, boundaries & protocols)

All downstream modules (Tribunal, GapLens, Meta-Analysis, Visual Reports, Web Dashboard)
consume and update this unified graph model.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from engine.events import event_bus
from engine.semantics import OutcomeClassifier, OutcomeDimension


# ============================================================================
# 1. Standard Node Data Models
# ============================================================================

@dataclass
class PaperNode:
    paper_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: int = 2024
    venue: str = "Academic Publication"
    doi: Optional[str] = None
    url: Optional[str] = None
    authority_tier: int = 1  # Tier 1 (peer-reviewed / gold) to Tier 5 (grey/web)
    peer_reviewed: bool = True
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceNode:
    evidence_id: str
    paper_id: str
    outcome_metric: str
    outcome_dimension: str = OutcomeDimension.GENERAL_MEASURE
    claim_id: Optional[str] = None
    outcome_id: Optional[str] = None
    effect_size: Dict[str, Any] = field(default_factory=lambda: {"metric": "Hedges g", "value": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "p_value": 0.05})
    sample_size: int = 0
    sample_description: str = ""
    study_design: str = "Quasi-Experimental"  # RCT, Quasi-Experimental DID, Meta-Analysis, Observational
    direction: str = "NEUTRAL"  # SUPPORTS, CONTRADICTS, NEUTRAL, MIXED
    confidence_score: float = 0.85
    wwc_rating: str = "Meets Standards with Reservations"  # WWC 5.0
    key_quote: str = ""
    calibrated_weight: float = 1.0
    bias_flag: Optional[str] = None

    def __post_init__(self):
        if self.outcome_dimension == OutcomeDimension.GENERAL_MEASURE and self.outcome_metric:
            self.outcome_dimension = OutcomeClassifier.classify(self.outcome_metric)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutcomeNode:
    outcome_id: str
    name: str
    dimension: str = OutcomeDimension.GENERAL_MEASURE
    category: str = "Learning"  # Learning, Task, Process, Risk, Policy
    description: str = ""

    def __post_init__(self):
        if self.dimension == OutcomeDimension.GENERAL_MEASURE and self.name:
            self.dimension = OutcomeClassifier.classify(self.name)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimNode:
    claim_id: str
    statement: str
    outcome_dimension: str = OutcomeDimension.GENERAL_MEASURE
    outcome_metric: str = ""
    status: str = "UNCERTAIN"  # SUPPORTED, CONTRADICTS, MIXED, UNCERTAIN, INSUFFICIENT_EVIDENCE
    pooled_effect_g: float = 0.0
    evidence_ids: List[str] = field(default_factory=list)
    bias_warning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskNode:
    risk_id: str
    risk_type: str  # Scaffolding Dependency Trap, Novice Illusion, Academic Integrity, Transfer Deficit, Equity Gap
    severity: str = "MODERATE"  # HIGH, MODERATE, LOW
    description: str = ""
    mitigation: str = ""
    triggered_by_evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GapNode:
    gap_id: str
    gap_type: str  # Population Gap, Measurement/Retention Gap, Methodological Gap, Contradiction Lens
    description: str = ""
    target_outcome: str = ""
    existing_evidence_summary: str = ""
    recommended_trial_design: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DecisionNode:
    decision_id: str
    verdict: str  # ADOPT, PILOT, REJECT, INSUFFICIENT_EVIDENCE
    confidence_score: float = 0.85
    rationale: str = ""
    applicability_boundary: str = ""
    intervention_plan: Dict[str, Any] = field(default_factory=dict)
    evaluation_plan: Dict[str, Any] = field(default_factory=dict)
    stop_conditions: List[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str  # EXTRACTED_FROM, EVALUATES, SUPPORTS, CONTRADICTS, EXPOSES_RISK,
    #               IDENTIFIES_GAP, GROUNDS_DECISION, MEASURES
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# 2. Unified EvidenceGraph Single Source of Truth (SSOT)
# ============================================================================

class EvidenceGraph:
    """The central Single Source of Truth (SSOT) evidence graph."""

    def __init__(self, project_id: str = "default_project"):
        self.project_id = project_id
        self.revision_id: int = 1
        self.intent: Dict[str, Any] = {}
        
        # 7 Core Node Storage Tables
        self.papers: Dict[str, PaperNode] = {}
        self.evidence: Dict[str, EvidenceNode] = {}
        self.outcomes: Dict[str, OutcomeNode] = {}
        self.claims: Dict[str, ClaimNode] = {}
        self.risks: Dict[str, RiskNode] = {}
        self.gaps: Dict[str, GapNode] = {}
        self.decision: Optional[DecisionNode] = None

        # Edges Table
        self.edges: List[GraphEdge] = []
        self.audit_warnings: List[str] = []
        self.created_at: str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.updated_at: str = self.created_at

    # --- Node Add / Upsert Helpers ---

    def add_paper(self, paper: PaperNode) -> PaperNode:
        self.papers[paper.paper_id] = paper
        self._touch()
        return paper

    def _ensure_measures_edge(self, evidence_id: str, outcome_id: str) -> None:
        """Idempotently connect an Evidence node to the Outcome it measures.

        add_edge already dedupes on (source, target, relation), so repeated
        upserts in either order produce exactly one MEASURES edge.
        """
        if evidence_id in self.evidence and outcome_id in self.outcomes:
            self.add_edge(evidence_id, outcome_id, "MEASURES")
            self._touch()

    def add_evidence(self, ev: EvidenceNode) -> EvidenceNode:
        self.evidence[ev.evidence_id] = ev
        # Auto-create edge to paper if paper exists
        if ev.paper_id in self.papers:
            self.add_edge(ev.evidence_id, ev.paper_id, "EXTRACTED_FROM", weight=ev.calibrated_weight)
        if ev.outcome_id:
            self._ensure_measures_edge(ev.evidence_id, ev.outcome_id)
        self._touch()
        return ev

    def add_outcome(self, outcome: OutcomeNode) -> OutcomeNode:
        self.outcomes[outcome.outcome_id] = outcome
        # Back-fill MEASURES edges for evidence already in the graph
        for ev in self.evidence.values():
            if ev.outcome_id == outcome.outcome_id:
                self._ensure_measures_edge(ev.evidence_id, outcome.outcome_id)
        self._touch()
        return outcome

    def add_claim(self, claim: ClaimNode) -> ClaimNode:
        self.claims[claim.claim_id] = claim
        for ev_id in claim.evidence_ids:
            if ev_id in self.evidence:
                rel = "SUPPORTS" if self.evidence[ev_id].direction == "SUPPORTS" else (
                    "CONTRADICTS" if self.evidence[ev_id].direction == "CONTRADICTS" else "EVALUATES"
                )
                self.add_edge(ev_id, claim.claim_id, rel)
        self._touch()
        return claim

    def add_risk(self, risk: RiskNode) -> RiskNode:
        self.risks[risk.risk_id] = risk
        for ev_id in risk.triggered_by_evidence_ids:
            if ev_id in self.evidence:
                self.add_edge(ev_id, risk.risk_id, "EXPOSES_RISK")
        self._touch()
        return risk

    def add_gap(self, gap: GapNode) -> GapNode:
        self.gaps[gap.gap_id] = gap
        self._touch()
        return gap

    def set_decision(self, decision: DecisionNode) -> DecisionNode:
        self.decision = decision
        # Connect decision to claims & risks
        for c_id in self.claims:
            self.add_edge(c_id, decision.decision_id, "GROUNDS_DECISION")
        for r_id in self.risks:
            self.add_edge(r_id, decision.decision_id, "GROUNDS_DECISION")
        self._touch()
        return decision

    def add_edge(self, source_id: str, target_id: str, relation: str, weight: float = 1.0, metadata: Optional[Dict[str, Any]] = None) -> GraphEdge:
        # Check duplicate
        for e in self.edges:
            if e.source_id == source_id and e.target_id == target_id and e.relation == relation:
                e.weight = weight
                if metadata:
                    e.metadata.update(metadata)
                return e
        edge = GraphEdge(source_id=source_id, target_id=target_id, relation=relation, weight=weight, metadata=metadata or {})
        self.edges.append(edge)
        return edge

    def _touch(self):
        self.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # --- Query & Aggregation Helpers ---

    def get_evidence_by_dimension(self, dimension: str) -> List[EvidenceNode]:
        return [ev for ev in self.evidence.values() if ev.outcome_dimension == dimension]

    def get_evidence_for_claim(self, claim_id: str) -> List[EvidenceNode]:
        claim = self.claims.get(claim_id)
        if not claim:
            return []
        return [self.evidence[eid] for eid in claim.evidence_ids if eid in self.evidence]

    def get_forest_plot_data(self) -> List[Dict[str, Any]]:
        """Extracts structured forest plot data points across all evidence nodes."""
        points = []
        for ev in self.evidence.values():
            paper = self.papers.get(ev.paper_id)
            study_label = f"{paper.authors[0] if paper and paper.authors else ev.paper_id} ({paper.year if paper else ''})"
            effect_val = ev.effect_size.get("value", 0.0)
            ci_l = ev.effect_size.get("ci_lower")
            ci_u = ev.effect_size.get("ci_upper")
            has_ci = ci_l is not None and ci_u is not None and float(ci_u) >= float(ci_l)
            points.append({
                "evidence_id": ev.evidence_id,
                "study_label": study_label,
                "venue": paper.venue if paper else "Academic",
                "outcome_metric": ev.outcome_metric,
                "outcome_dimension": ev.outcome_dimension,
                "effect_size": effect_val,
                "ci_lower": round(float(ci_l), 3) if has_ci else None,
                "ci_upper": round(float(ci_u), 3) if has_ci else None,
                "precision_provenance": "reported_ci" if has_ci else "not_available",
                "sample_size": ev.sample_size,
                "weight": ev.calibrated_weight,
                "direction": ev.direction,
                "wwc_rating": ev.wwc_rating,
            })
        # Sort by dimension and effect size
        return sorted(points, key=lambda p: (p["outcome_dimension"], p["effect_size"]), reverse=True)

    def compute_meta_synthesis(self) -> Dict[str, Any]:
        """Calculates pooled effect sizes across outcome dimensions using Inverse-Variance weighting."""
        by_dim: Dict[str, List[EvidenceNode]] = {}
        for ev in self.evidence.values():
            by_dim.setdefault(ev.outcome_dimension, []).append(ev)

        dim_results = {}
        for dim, nodes in by_dim.items():
            effects = []
            variances = []
            precision_counts = {"reported_ci": 0, "derived_from_sample_size": 0}
            excluded_no_precision = 0
            for n in nodes:
                eff = n.effect_size.get("value")
                if eff is None or math.isnan(float(eff)) or math.isinf(float(eff)):
                    continue

                # Statistical variance derivation (Borenstein et al. 2009)
                ci_l = n.effect_size.get("ci_lower")
                ci_u = n.effect_size.get("ci_upper")
                if ci_l is not None and ci_u is not None and float(ci_u) > float(ci_l):
                    se = (float(ci_u) - float(ci_l)) / (2.0 * 1.95996)
                    precision_counts["reported_ci"] += 1
                elif n.sample_size and n.sample_size > 0:
                    eff_f = float(eff)
                    se = math.sqrt(4.0 / n.sample_size + (eff_f ** 2) / (2.0 * n.sample_size))
                    precision_counts["derived_from_sample_size"] += 1
                else:
                    # No CI and no sample size: precision is genuinely unknown;
                    # never substitute a default SE (no false precision).
                    excluded_no_precision += 1
                    continue

                effects.append(float(eff))
                variances.append(max(1e-4, se ** 2))

            if not effects:
                continue

            inv_w = [1.0 / v for v in variances]
            sum_w = sum(inv_w)
            weighted_g = sum(e * w for e, w in zip(effects, inv_w)) / sum_w

            k = len(effects)
            if k > 1:
                q_stat = sum(w * ((e - weighted_g) ** 2) for e, w in zip(effects, inv_w))
                df = k - 1
                i_squared = max(0.0, min(100.0, ((q_stat - df) / q_stat) * 100.0)) if q_stat > df else 0.0
            else:
                q_stat = 0.0
                i_squared = 0.0

            dim_results[dim] = {
                "dimension": dim,
                "studies_count": len(effects),
                "pooled_g": round(weighted_g, 3),
                "q_statistic": round(q_stat, 2),
                "i_squared": round(i_squared, 1),
                "precision_sources": precision_counts,
                "excluded_no_precision": excluded_no_precision,
                "interpretation": (
                    "Substantial Positive Effect" if weighted_g > 0.50 else (
                        "Moderate Positive Effect" if weighted_g > 0.20 else (
                            "Null / Negligible Effect" if weighted_g >= -0.05 else "Negative Deficit"
                        )
                    )
                )
            }
        return dim_results

    def export_echarts_graph(self) -> Dict[str, Any]:
        """Exports graph topology formatted for ECharts Force graph visualization."""
        category_map = {
            "PaperNode": 0,
            "EvidenceNode": 1,
            "ClaimNode": 2,
            "OutcomeNode": 3,
            "RiskNode": 4,
            "GapNode": 5,
            "DecisionNode": 6,
        }
        categories = [
            {"name": "Literature Paper (文献)"},
            {"name": "Evidence Node (实证发现)"},
            {"name": "Claim (研究主张)"},
            {"name": "Outcome (测量指标)"},
            {"name": "Methodological Risk (学术陷阱)"},
            {"name": "Research Gap (学术缺口)"},
            {"name": "Decision (裁决快照)"},
        ]

        nodes = []
        for p in self.papers.values():
            nodes.append({
                "id": p.paper_id,
                "name": f"{p.authors[0] if p.authors else p.paper_id} ({p.year})",
                "category": category_map["PaperNode"],
                "category_name": "PaperNode (文献)",
                "symbolSize": 28,
                "value": p.title,
                "authors": p.authors,
                "year": p.year,
                "venue": p.venue,
                "doi": p.doi,
                "tier": p.authority_tier,
                "quote": p.summary,
            })
        for ev in self.evidence.values():
            effect_val = ev.effect_size.get("value", 0.0)
            symbol_size = max(18, min(45, int(18 + abs(effect_val) * 20)))
            nodes.append({
                "id": ev.evidence_id,
                "name": f"{ev.evidence_id}: {ev.outcome_metric} (g={effect_val:+.2f})",
                "category": category_map["EvidenceNode"],
                "category_name": "EvidenceNode (实证效应量)",
                "symbolSize": symbol_size,
                "dimension": ev.outcome_dimension,
                "direction": ev.direction,
                "effect_size": effect_val,
                "ci_lower": ev.effect_size.get("ci_lower", "N/A"),
                "ci_upper": ev.effect_size.get("ci_upper", "N/A"),
                "sample_size": ev.sample_size,
                "wwc_rating": ev.wwc_rating,
                "quote": ev.key_quote,
            })
        for o in self.outcomes.values():
            nodes.append({
                "id": o.outcome_id,
                "name": f"📊 {o.name}",
                "category": category_map["OutcomeNode"],
                "category_name": "OutcomeNode (测量指标)",
                "symbolSize": 30,
                "dimension": o.dimension,
                "value": o.description,
            })
        for c in self.claims.values():
            nodes.append({
                "id": c.claim_id,
                "name": f"{c.claim_id}: {c.statement[:24]}...",
                "category": category_map["ClaimNode"],
                "category_name": "ClaimNode (科学主张)",
                "symbolSize": 34,
                "status": c.status,
                "pooled_g": c.pooled_effect_g,
                "value": c.statement,
                "quote": c.bias_warning,
            })
        for r in self.risks.values():
            nodes.append({
                "id": r.risk_id,
                "name": f"⚠️ {r.risk_type}",
                "category": category_map["RiskNode"],
                "category_name": "RiskNode (方法学风险)",
                "symbolSize": 36,
                "severity": r.severity,
                "value": r.description,
                "quote": r.mitigation,
            })
        for g in self.gaps.values():
            nodes.append({
                "id": g.gap_id,
                "name": f"🔬 {g.gap_type}",
                "category": category_map["GapNode"],
                "category_name": "GapNode (研究缺口)",
                "symbolSize": 32,
                "value": g.description,
                "quote": g.recommended_trial_design,
            })
        if self.decision:
            nodes.append({
                "id": self.decision.decision_id,
                "name": f"⚖️ {self.decision.verdict}",
                "category": category_map["DecisionNode"],
                "category_name": "DecisionNode (裁决快照)",
                "symbolSize": 50,
                "verdict": self.decision.verdict,
                "confidence": self.decision.confidence_score,
                "value": self.decision.rationale,
                "quote": self.decision.applicability_boundary,
            })

        links = []
        for e in self.edges:
            line_color = (
                "#2ea043" if e.relation == "SUPPORTS" else (
                    "#f85149" if e.relation in ("CONTRADICTS", "EXPOSES_RISK") else "#58a6ff"
                )
            )
            links.append({
                "source": e.source_id,
                "target": e.target_id,
                "label": {"show": True, "formatter": e.relation},
                "lineStyle": {"color": line_color, "width": max(1.0, e.weight * 2.0)},
            })

        return {
            "categories": categories,
            "nodes": nodes,
            "links": links,
        }

    # --- Serialization & Persistence ---

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "revision_id": self.revision_id,
            "intent": self.intent,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "audit_warnings": self.audit_warnings,
            "papers": {k: v.to_dict() for k, v in self.papers.items()},
            "evidence": {k: v.to_dict() for k, v in self.evidence.items()},
            "outcomes": {k: v.to_dict() for k, v in self.outcomes.items()},
            "claims": {k: v.to_dict() for k, v in self.claims.items()},
            "risks": {k: v.to_dict() for k, v in self.risks.items()},
            "gaps": {k: v.to_dict() for k, v in self.gaps.items()},
            "decision": self.decision.to_dict() if self.decision else None,
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> EvidenceGraph:
        graph = cls(project_id=data.get("project_id", "default_project"))
        graph.revision_id = data.get("revision_id", 1)
        graph.intent = data.get("intent", {})
        graph.created_at = data.get("created_at", graph.created_at)
        graph.updated_at = data.get("updated_at", graph.updated_at)
        graph.audit_warnings = data.get("audit_warnings", [])

        for k, v in data.get("papers", {}).items():
            graph.papers[k] = PaperNode(**v)
        for k, v in data.get("evidence", {}).items():
            graph.evidence[k] = EvidenceNode(**v)
        for k, v in data.get("outcomes", {}).items():
            graph.outcomes[k] = OutcomeNode(**v)
        for k, v in data.get("claims", {}).items():
            graph.claims[k] = ClaimNode(**v)
        for k, v in data.get("risks", {}).items():
            graph.risks[k] = RiskNode(**v)
        for k, v in data.get("gaps", {}).items():
            graph.gaps[k] = GapNode(**v)
        if data.get("decision"):
            graph.decision = DecisionNode(**data["decision"])
        for e in data.get("edges", []):
            graph.edges.append(GraphEdge(**e))

        return graph

    @classmethod
    def from_json(cls, json_str: str) -> EvidenceGraph:
        return cls.from_dict(json.loads(json_str))
