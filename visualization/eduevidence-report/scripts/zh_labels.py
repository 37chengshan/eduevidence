#!/usr/bin/env python3
"""zh_labels.py — 显示层中文标签映射（v5 §10：格式化显示属于渲染器权限）。

只映射枚举/标签类字段（outcome_type、study_type、authority_level、状态、置信度等），
绝不改写数据内容（Evidence 文本、Claim 文本、Verdict 文本保持 result.json 原文，
以维持 Claim-Evidence-Source 可追溯性与 Scientific Integrity）。

三个适配器 + Composer 共用，保证全报告语言一致。
"""
from __future__ import annotations

OUTCOME_ZH = {
    "knowledge_gain": "知识获得",
    "concept_understanding": "概念理解",
    "retention": "记忆保持",
    "transfer": "迁移能力",
    "independent_problem_solving": "独立问题解决",
    "completion_time": "完成时间",
    "accuracy": "正确率",
    "code_quality": "代码质量",
    "assignment_score": "作业成绩",
    "engagement": "参与度",
    "motivation": "学习动机",
    "cognitive_load": "认知负荷",
    "help_seeking": "求助行为",
    "metacognition": "元认知",
    "ai_dependency": "AI 依赖",
    "over_reliance": "过度依赖",
    "reduced_effort": "努力下降",
    "reduced_transfer": "迁移下降",
    "academic_integrity_risk": "学术诚信风险",
    "false_confidence": "虚假自信",
    "learning_gain": "学习收获",
    "task_performance": "任务表现",
    "programming_skill": "编程技能",
    "writing_skill": "写作技能",
}

STUDY_ZH = {
    "rct": "随机对照试验",
    "quasi_experiment": "准实验",
    "quasi_experimental": "准实验",
    "observational": "观察性研究",
    "mixed_methods": "混合方法",
    "case_study": "案例研究",
    "longitudinal": "纵向研究",
    "meta_analysis": "元分析",
    "systematic_review": "系统综述",
    "survey": "调查",
    "qualitative": "质性研究",
    "correlational": "相关研究",
}

AUTHORITY_ZH = {
    "tier1_paper_doi": "T1 DOI 可验证论文",
    "tier1_peer_reviewed_journal": "T1 同行评议期刊",
    "tier2_peer_reviewed_conference": "T2 同行评议会议",
    "tier3_professional_institution": "T3 专业机构",
    "tier4_reputable_media": "T4 权威媒体",
    "tier5_unverified": "T5 未验证",
}

CLAIM_STATUS_ZH = {
    "SUPPORTED": "已支持",
    "UNSUPPORTED": "无支撑",
    "DOWNGRADE_CONFIDENCE": "降级置信度",
}

VERDICT_ZH = {
    "met": "通过",
    "partial": "部分",
    "not_applicable": "不适用",
    "concern": "关注",
    "CONCERN": "关注",
    "PASS": "通过",
    "FAIL": "失败",
}

CONFIDENCE_ZH = {
    "High": "高",
    "Moderate": "中",
    "Low": "低",
    "Insufficient": "不足",
}

MODE_ZH = {
    "platform_native": "平台原生",
    "agent_mcp_enhanced": "Agent MCP 增强",
}

ACTION_ZH = {
    "adopt": "全面采用",
    "pilot": "试点验证",
    "reject": "不建议采用",
    "insufficient_evidence": "证据不足",
}


# 英文可读标签（lang=en 时显示；无映射时显示原始枚举值）
OUTCOME_EN = {
    "knowledge_gain": "Knowledge gain",
    "concept_understanding": "Concept understanding",
    "retention": "Retention",
    "transfer": "Transfer",
    "independent_problem_solving": "Independent problem solving",
    "completion_time": "Completion time",
    "accuracy": "Accuracy",
    "code_quality": "Code quality",
    "assignment_score": "Assignment score",
    "engagement": "Engagement",
    "motivation": "Motivation",
    "cognitive_load": "Cognitive load",
    "help_seeking": "Help seeking",
    "metacognition": "Metacognition",
    "ai_dependency": "AI dependency",
    "over_reliance": "Over-reliance",
    "reduced_effort": "Reduced effort",
    "reduced_transfer": "Reduced transfer",
    "academic_integrity_risk": "Academic integrity risk",
    "false_confidence": "False confidence",
    "learning_gain": "Learning gain",
    "task_performance": "Task performance",
    "programming_skill": "Programming skill",
    "writing_skill": "Writing skill",
}
STUDY_EN = {
    "rct": "Randomized controlled trial",
    "quasi_experiment": "Quasi-experiment",
    "quasi_experimental": "Quasi-experimental",
    "observational": "Observational",
    "mixed_methods": "Mixed methods",
    "case_study": "Case study",
    "longitudinal": "Longitudinal",
    "meta_analysis": "Meta-analysis",
    "systematic_review": "Systematic review",
    "survey": "Survey",
    "qualitative": "Qualitative",
    "correlational": "Correlational",
}
AUTHORITY_EN = {
    "tier1_paper_doi": "Tier 1 DOI-verified paper",
    "tier1_peer_reviewed_journal": "Tier 1 peer-reviewed journal",
    "tier2_peer_reviewed_conference": "Tier 2 peer-reviewed conference",
    "tier3_professional_institution": "Tier 3 professional institution",
    "tier4_reputable_media": "Tier 4 reputable media",
    "tier5_unverified": "Tier 5 unverified",
}
STATUS_EN = {
    "SUPPORTED": "Supported",
    "UNSUPPORTED": "Unsupported",
    "DOWNGRADE_CONFIDENCE": "Confidence downgraded",
}
VERDICT_EN = {
    "met": "Met", "partial": "Partial", "not_applicable": "N/A",
    "concern": "Concern", "CONCERN": "Concern", "PASS": "Pass", "FAIL": "Fail",
}
CONFIDENCE_EN = {
    "High": "High", "Moderate": "Moderate", "Low": "Low", "Insufficient": "Insufficient",
}
MODE_EN = {
    "platform_native": "Platform native", "agent_mcp_enhanced": "Agent MCP enhanced",
}
ACTION_EN = {
    "adopt": "Adopt", "pilot": "Pilot", "reject": "Reject",
    "insufficient_evidence": "Insufficient evidence",
}
DIR_EN = {"support": "Support", "contradict": "Contradict", "neutral": "Neutral"}
DIR_ZH = {"support": "支持", "contradict": "反驳", "neutral": "中性"}


def label(lang: str, kind: str, value: str) -> str:
    """按语言取枚举可读标签：zh → 中文；en → 英文（无映射时返回原值）。"""
    if lang == "zh":
        table = {"outcome": OUTCOME_ZH, "study": STUDY_ZH, "authority": AUTHORITY_ZH,
                 "status": CLAIM_STATUS_ZH, "verdict": VERDICT_ZH, "confidence": CONFIDENCE_ZH,
                 "mode": MODE_ZH, "action": ACTION_ZH, "dir": DIR_ZH}
    else:
        table = {"outcome": OUTCOME_EN, "study": STUDY_EN, "authority": AUTHORITY_EN,
                 "status": STATUS_EN, "verdict": VERDICT_EN, "confidence": CONFIDENCE_EN,
                 "mode": MODE_EN, "action": ACTION_EN, "dir": DIR_EN}
    return table.get(kind, {}).get(value, value)


def zh_outcome(value: str) -> str:
    return OUTCOME_ZH.get(value, value)


def zh_study(value: str) -> str:
    return STUDY_ZH.get(value, value)


def zh_authority(value: str) -> str:
    return AUTHORITY_ZH.get(value, value)


def zh_status(value: str) -> str:
    return CLAIM_STATUS_ZH.get(value, value)


def zh_verdict(value: str) -> str:
    return VERDICT_ZH.get(value, value)


def zh_confidence(value: str) -> str:
    return CONFIDENCE_ZH.get(value, value)


def zh_mode(value: str) -> str:
    return MODE_ZH.get(value, value)


def zh_action(value: str) -> str:
    return ACTION_ZH.get(value, value)
