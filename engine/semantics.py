"""engine/semantics.py — Centralized V2 & V4/V5 semantics and Outcome Ontology.

Combines:
1. V2 Direction & Implication Semantics (finding_effect, claim_relation, decision_implication)
2. V5 Social Science Outcome Ontology & OutcomeClassifier (OutcomeDimension, OutcomeClassifier)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

# --- V2 Direction & Relation Constants ---
FINDING_EFFECTS = ("positive", "negative", "null", "mixed", "not_applicable")
CLAIM_RELATIONS = ("support", "contradict", "neutral")
DECISION_IMPLICATIONS = ("support_adoption", "oppose_adoption", "conditional", "neutral")

_RELATION_TO_IMPLICATION = {
    "support": "support_adoption",
    "contradict": "oppose_adoption",
    "neutral": "neutral",
}


def finding_effect(finding: dict) -> str:
    """Observed effect direction of a V2 Finding."""
    effect = finding.get("effect_direction")
    if effect in FINDING_EFFECTS:
        return effect
    return "null"


def claim_relation(link: dict) -> str:
    """Relation of an EvidenceLink to the Claim it binds."""
    relation = link.get("relation_to_claim")
    if relation in CLAIM_RELATIONS:
        return relation
    return "neutral"


def decision_implication(link: dict) -> str:
    """Implication of an EvidenceLink for the current teaching decision."""
    implication = link.get("decision_implication")
    if implication in DECISION_IMPLICATIONS:
        return implication
    return _RELATION_TO_IMPLICATION[claim_relation(link)]


def independent_study_ids(findings: list[dict]) -> set[str]:
    """Unique Study IDs behind a set of Findings (independent-study counting)."""
    return {f["study_id"] for f in findings if f.get("study_id")}


def independent_sample_keys(studies: list[dict]) -> set[str]:
    """Unique independence keys across Studies (independent sample counting)."""
    keys = {s["independence_key"] for s in studies if s.get("independence_key")}
    return keys


def graph_counts(store) -> dict[str, int]:
    """Entity counts of the active graph revision."""
    return {
        "source_count": len(store.read_table("sources")),
        "study_count": len(store.read_table("studies")),
        "finding_count": len(store.read_table("findings")),
        "outcome_count": len(store.read_table("outcomes")),
        "claim_count": len(store.read_table("claims")),
        "evidence_link_count": len(store.read_table("evidence_links")),
        "audit_count": len(store.read_table("audits")),
    }


# --- V5 Outcome Ontology & Dimension Classifier ---

class OutcomeDimension:
    PROCEDURAL_EFFICIENCY = "PROCEDURAL_EFFICIENCY"   # Speed, task velocity, immediate completion during intervention
    CONCEPTUAL_MASTERY = "CONCEPTUAL_MASTERY"         # Deep understanding, mental model construction, reasoning
    INDEPENDENT_TRANSFER = "INDEPENDENT_TRANSFER"     # Delayed retention, unassisted solo closed-book transfer
    AFFECTIVE_PSYCHOSOCIAL = "AFFECTIVE_PSYCHOSOCIAL" # Anxiety, engagement, self-efficacy, motivation
    SOCIOECONOMIC_POLICY = "SOCIOECONOMIC_POLICY"     # Family expenditure, equity gap, resource allocation
    GENERAL_MEASURE = "GENERAL_MEASURE"

    ALL = [
        PROCEDURAL_EFFICIENCY,
        CONCEPTUAL_MASTERY,
        INDEPENDENT_TRANSFER,
        AFFECTIVE_PSYCHOSOCIAL,
        SOCIOECONOMIC_POLICY,
        GENERAL_MEASURE,
    ]


class OutcomeClassifier:
    """Classifies outcome metric descriptions into canonical social science dimensions."""

    @staticmethod
    def classify(metric_text: str) -> str:
        if not metric_text:
            return OutcomeDimension.GENERAL_MEASURE

        t = metric_text.lower()
        # 1. Independent Transfer & Delayed Retention (Highest Priority to detect Scaffolding Traps)
        if any(k in t for k in [
            "transfer", "retention", "delayed", "exam", "solo", "unassisted", "no-ai",
            "post-test", "follow-up", "long-term", "persistence",
            "迁移", "闭卷", "期末", "长期", "留存", "保持", "无ai测试", "独立解题", "手写代码"
        ]):
            return OutcomeDimension.INDEPENDENT_TRANSFER
        # 2. Conceptual Mastery & Deep Reasoning
        elif any(k in t for k in [
            "thinking", "conceptual", "problem solving", "reasoning", "comprehension",
            "mental model", "algorithmic", "abstraction", "debugging strategy",
            "思维", "概念", "架构", "认知", "问题解决", "算法理解", "心智模型", "调试策略"
        ]):
            return OutcomeDimension.CONCEPTUAL_MASTERY
        # 3. Procedural Efficiency & In-task velocity
        elif any(k in t for k in [
            "speed", "velocity", "completion", "time", "procedural", "task performance",
            "accuracy", "efficiency", "correctness", "syntax", "lines of code", "loc",
            "速度", "耗时", "效率", "作业完成", "完成时间", "语法正确", "即时准确率", "代码量"
        ]):
            return OutcomeDimension.PROCEDURAL_EFFICIENCY
        # 4. Affective & Psychosocial
        elif any(k in t for k in [
            "anxiety", "engagement", "interest", "efficacy", "collaboration", "motivation",
            "confidence", "self-regulation", "frustration",
            "焦虑", "投入", "效能", "协作", "动机", "自信", "自我调节", "挫败感", "学习兴趣"
        ]):
            return OutcomeDimension.AFFECTIVE_PSYCHOSOCIAL
        # 5. Socioeconomic & Policy
        elif any(k in t for k in [
            "expenditure", "cost", "equity", "burden", "socioeconomic", "disparity",
            "支出", "负担", "公平", "成本", "数字鸿沟", "社会经济"
        ]):
            return OutcomeDimension.SOCIOECONOMIC_POLICY

        return OutcomeDimension.GENERAL_MEASURE
