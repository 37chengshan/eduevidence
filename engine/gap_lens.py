"""engine/gap_lens.py — Research Gap Discovery & Contradiction Lens.

Inspired by BioGapLens & PICO gap taxonomy. Analyzes the EvidenceGraph to identify:
1. Population Gaps (unexplored cohorts, demographic bias)
2. Measurement / Retention Gaps (missing delayed post-tests, lack of unassisted transfer)
3. Methodological Gaps (lack of baseline equivalence, missing active controls)
4. Contradiction Lenses (identifying moderators explaining divergent study findings)

Generates pre-registered 12-week quasi-experimental DID / RCT trial protocols
specifically grounded on verified gaps (enforcing the rule: 'No study design without evidence grounding').
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from engine.evidence_graph import EvidenceGraph, GapNode, RiskNode
from engine.semantics import OutcomeDimension


class GapLensAnalyzer:
    """Automated research gap discovery and contradiction diagnostic engine."""

    def analyze_gaps(self, graph: EvidenceGraph) -> List[GapNode]:
        gaps: List[GapNode] = []
        pico = graph.intent.get("pico", {})
        intervention = pico.get("intervention", "Target Intervention")
        population = pico.get("population", "Target Population")

        ev_list = list(graph.evidence.values())
        if not ev_list:
            return gaps

        # 1. Measurement & Retention Gap Check
        transfer_nodes = [ev for ev in ev_list if ev.outcome_dimension == OutcomeDimension.INDEPENDENT_TRANSFER]
        procedural_nodes = [ev for ev in ev_list if ev.outcome_dimension == OutcomeDimension.PROCEDURAL_EFFICIENCY]

        if procedural_nodes and not transfer_nodes:
            gaps.append(GapNode(
                gap_id=f"GAP-RETENTION-001",
                gap_type="Measurement/Retention Gap",
                description=f"Existing studies on {intervention} exclusively evaluate immediate in-session task speed without measuring delayed conceptual retention or unassisted transfer.",
                target_outcome="Delayed Unassisted Transfer",
                existing_evidence_summary=f"{len(procedural_nodes)} studies evaluated active speed; 0 studies measured unassisted delayed retention.",
                recommended_trial_design="12-Week Cluster Randomized Trial with 4-week delayed post-test without AI assistance.",
            ))
        elif transfer_nodes and any(ev.effect_size.get("value", 0.0) <= 0.05 for ev in transfer_nodes):
            avg_proc = (
                sum(ev.effect_size.get("value", 0.0) for ev in procedural_nodes) / len(procedural_nodes)
                if procedural_nodes else 0.0
            )
            avg_trans = (
                sum(ev.effect_size.get("value", 0.0) for ev in transfer_nodes) / len(transfer_nodes)
                if transfer_nodes else 0.0
            )
            gaps.append(GapNode(
                gap_id=f"GAP-SCAFFOLD-FADE-001",
                gap_type="Methodological Gap",
                description=f"Delayed transfer tests indicate cognitive offloading/scaffolding dependency under unguarded {intervention}. Lack of trials evaluating structured 'fading' protocols.",
                target_outcome="Independent Problem Solving",
                existing_evidence_summary=f"Synthesized evidence shows {avg_proc:+.2f}g in-task speed ({len(procedural_nodes)} studies) vs {avg_trans:+.2f}g delayed unassisted transfer ({len(transfer_nodes)} studies).",
                recommended_trial_design="2x2 Factorial Trial: Unguarded Access vs Structured Socratic Fading Scaffold vs Control.",
            ))

        # 2. Population & Context Heterogeneity Gap
        cohorts = [ev.sample_description.lower() for ev in ev_list if ev.sample_description]
        has_novice = any("freshman" in c or "novice" in c or "cs1" in c or "intro" in c or "初学" in c for c in cohorts)
        has_advanced = any("senior" in c or "advanced" in c or "professional" in c or "高年级" in c or "专家" in c for c in cohorts)

        if has_novice and not has_advanced:
            gaps.append(GapNode(
                gap_id=f"GAP-POP-EXPERTISE-001",
                gap_type="Population Gap",
                description=f"Evidence is heavily skewed toward introductory novices; efficacy on advanced algorithmic design and large-scale software engineering remains unexplored.",
                target_outcome="Advanced Software Architecture",
                existing_evidence_summary=f"Evaluations across {len(cohorts)} studies are restricted to introductory novice cohorts ({population}).",
                recommended_trial_design="Comparative Quasi-Experimental Study evaluating CS3/CS4 upper-division capstone cohorts.",
            ))

        # 3. Contradiction Lens (Divergent effect size isolation)
        pos_studies = [ev for ev in ev_list if ev.effect_size.get("value", 0.0) > 0.20]
        neg_studies = [ev for ev in ev_list if ev.effect_size.get("value", 0.0) < -0.10]

        if pos_studies and neg_studies:
            gaps.append(GapNode(
                gap_id=f"GAP-CONTRADICTION-001",
                gap_type="Contradiction Lens",
                description=f"Contradictory findings detected across {len(pos_studies)} positive vs {len(neg_studies)} negative studies. Moderator hypothesis: Degree of real-time Socratic prompting vs direct code generation.",
                target_outcome="Syntax Speed vs Algorithmic Reasoning",
                existing_evidence_summary=f"Positive studies ({[s.evidence_id for s in pos_studies[:2]]}) measured active code drafting; negative studies ({[s.evidence_id for s in neg_studies[:2]]}) measured unassisted closed-book exams.",
                recommended_trial_design="Dismantling Study isolating the active ingredient of AI prompting modality.",
            ))

        # Register discovered gaps into graph
        for g in gaps:
            graph.add_gap(g)

        return gaps

    def generate_pre_registered_protocol(self, gap: GapNode, graph: EvidenceGraph) -> Dict[str, Any]:
        """Generates a complete 12-week pre-registered quasi-experimental DID trial protocol."""
        pico = graph.intent.get("pico", {})
        intervention = pico.get("intervention", "Target Intervention")
        population = pico.get("population", "Target Population")

        return {
            "protocol_id": f"PROTO-{gap.gap_id}",
            "grounded_gap_id": gap.gap_id,
            "title": f"Pre-Registered 12-Week Field Trial: Evaluating {gap.target_outcome} under {intervention}",
            "design_type": "Difference-in-Differences (DID) with Baseline Equivalence",
            "duration_weeks": 12,
            "target_population": population,
            "sample_size_target": 240,
            "arms": [
                {"name": "Treatment Arm (Scaffolded Intervention)", "n": 120, "description": f"{intervention} with mandatory reflection and phased scaffolding fade"},
                {"name": "Active Control Arm (Standard Curriculum)", "n": 120, "description": "Traditional IDE with standard pedagogical TA support"},
            ],
            "timeline": [
                {"week": "Week 1", "phase": "Pre-Test Baseline", "measurement": "Baseline Equivalence & Prior Achievement Test (WWC 5.0 compliant)"},
                {"week": "Weeks 2-5", "phase": "Phase 1: Assisted Foundation", "measurement": "In-task procedural completion time and cognitive load"},
                {"week": "Weeks 6-9", "phase": "Phase 2: Scaffolding Fade", "measurement": "Socratic prompt fidelity and conceptual mental model check"},
                {"week": "Week 10", "phase": "Phase 3: Unassisted Transfer", "measurement": "Solo unassisted closed-book problem solving exam"},
                {"week": "Week 12", "phase": "Phase 4: Delayed Retention Wave", "measurement": "4-week delayed retention test + DID regression data export"},
            ],
            "statistical_model": "DID Regression: Y_it = beta_0 + beta_1*Treat_i + beta_2*Post_t + delta*(Treat_i * Post_t) + gamma*X_it + epsilon_it",
            "causal_estimand": "delta (Average Treatment Effect on the Treated / ATT)",
            "stopping_rules": [
                "Severe drop in solo mid-term exam performance (> 1.0 SD deficit vs control)",
                "Academic integrity breach rate exceeding 15% in treatment cohort",
            ]
        }


gap_lens = GapLensAnalyzer()
