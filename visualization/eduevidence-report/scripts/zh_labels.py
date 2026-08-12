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
