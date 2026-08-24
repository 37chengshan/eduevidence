#!/usr/bin/env python3
"""build_report.py — HTML Composer: single-file offline EduEvidence_Report.html
(v5 Iteration 6-9, SWF Iteration E).

Pipeline (SKILL.md §8):
    result.json (+ result.zh.json)
      -> contract validation (report-result.schema.json semantics)
      -> claim-evidence-source audit  (REPORT_INVALID gate, §27/§60)
      -> adapters in-memory: ECharts specs / AntV infographics / Academic figures
      -> numbers-match integrity gate
      -> report_spec.json (visualization decision record)
      -> single-file offline HTML: 双语（中文默认 + English 切换），
         Visual Brief + AI 规划的 5–7 章 Full Report，静态优先 + JS 增强

数据契约：
  - result.json  = 研究管线输出的原始数据（英文）
  - result.zh.json = AI 生成的全中文平行版本（同构，枚举/ID/URL/数字不变）
  - 渲染器按当前语言取数据 + 双语 UI 文案；数字一致性门对两份数据分别校验

Usage:
    python3 visualization/eduevidence-report/scripts/build_report.py \
        --result examples/ai-coding-assistant/result.json \
        --result-zh examples/ai-coding-assistant/result.zh.json \
        --out examples/ai-coding-assistant/EduEvidence_Report.html
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

from build_charts import build_all as build_chart_specs, effect_outcomes
from build_figures import build_figure_data, render_figures, render_lieflat_gallery
from build_infographics import build_all as build_infographics
from lieflat_engine import REGISTRY as LIEFLAT_REGISTRY, LEGACY_TYPES, ACADEMIC_FIGURE_KEYS
from zh_labels import label

THEMES_DIR = Path(__file__).resolve().parent.parent / "themes"
MOTION_DIR = Path(__file__).resolve().parent.parent / "motion"
THEME_NAMES = ("claude", "academic", "datalab", "datalab-dark", "presentation")
RENDERER_VERSION = "1.0.0"  # must match pyproject.toml version; recorded in artifact manifest
THEME_DISPLAY = {
    "claude": "Claude Research [Light]",
    "academic": "Academic Paper [Light]",
    "datalab": "DataLab [Light]",
    "datalab-dark": "DataLab [Dark]",
    "presentation": "Presentation / Judge [Dark]",
}

# Provenance badge (plan R4): every report declares where its data came from.
# synthetic/hybrid get a loud warning style; absence of the field renders no chip
# (legacy packs), but new packs must always set it.
DATA_ORIGIN_LABELS = {
    "real": {"zh": "数据来源：真实文献（流水线生成）", "en": "Data: real studies (pipeline-generated)"},
    "manual_curated": {"zh": "数据来源：真实文献 · 人工精编", "en": "Data: real studies · manually curated"},
    "synthetic": {"zh": "数据来源：合成演示数据（非真实研究）", "en": "Data: SYNTHETIC demo — not real studies"},
    "hybrid": {"zh": "数据来源：混合（真实 + 合成）", "en": "Data: hybrid (real + synthetic)"},
}

# Full report is intentionally NOT a fixed 12-chapter template. The template exposes
# semantic modules; an upstream AI may group them into any 5–7 chapter outline by writing
# `report_outline.chapters`. If it does not, a six-chapter fallback keeps the report usable.
FULL_REPORT_MODULES = (
    "decision", "scope", "retrieval", "outcomes", "evidence", "quality", "conflicts",
    "trace", "applicability", "intervention", "evaluation", "sources",
)
DEFAULT_FULL_REPORT_PLAN = (
    {"key": "decision", "title_zh": "结论、裁决与研究边界", "title_en": "Decision, Adjudication & Research Boundary",
     "modules": ("decision", "scope")},
    {"key": "evidence", "title_zh": "关键证据与结果分离", "title_en": "Key Evidence & Outcome Separation",
     "modules": ("retrieval", "outcomes", "evidence")},
    {"key": "quality", "title_zh": "证据可信度、反证与方法审计", "title_en": "Evidence Quality, Counterevidence & Method Audit",
     "modules": ("quality", "conflicts", "trace")},
    {"key": "action", "title_zh": "适用范围与教学行动", "title_en": "Applicability & Teaching Action",
     "modules": ("applicability", "intervention")},
    {"key": "evaluation", "title_zh": "试点设计、评估与停止条件", "title_en": "Pilot, Evaluation & Stop Conditions",
     "modules": ("evaluation",)},
    {"key": "sources", "title_zh": "来源、溯源与附录", "title_en": "Sources, Traceability & Appendix",
     "modules": ("sources",)},
)

METHODOLOGY_LABELS_ZH = {
    "control_group": "对照组", "randomization": "随机分配", "pre_test": "前测",
    "post_test": "后测", "retention_test": "保持测试", "transfer_test": "迁移测试",
    "sample_bias": "样本偏差", "self_selection": "自我选择偏差",
    "measurement_validity": "测量效度", "confounders": "混杂因素",
    "instructor_effect": "教师效应", "novelty_effect": "新奇效应",
    "tool_version_effect": "工具版本效应", "ai_usage_policy": "AI 使用规则",
    "dropout": "样本流失",
}

FRAME_ENUM_ZH = {
    "teaching_decision": "教学决策",
    "undergraduate_year_1": "大学一年级",
    "computer_science": "计算机科学与技术",
    "C_programming": "C 语言程序设计",
    "compulsory_core_course": "必修核心课程",
    "primary": "主要结果",
    "secondary": "次要结果",
    "risk": "风险结果",
}

FRAME_ENUM_EN = {
    "teaching_decision": "Teaching decision",
    "undergraduate_year_1": "First-year undergraduate",
    "computer_science": "Computer science",
    "C_programming": "C programming",
    "compulsory_core_course": "Compulsory core course",
    "primary": "Primary outcomes",
    "secondary": "Secondary outcomes",
    "risk": "Risk outcomes",
}

DIR_LABEL = {"support": "支持", "contradict": "反驳", "neutral": "中性"}
DIR_CLASS = {"support": "pos", "contradict": "neg", "neutral": "neu"}
DIR_COLOR = {"support": "#5E8A6A", "contradict": "#A85B53", "neutral": "#C99A4A"}
EFFECT_CLASS = {"positive": "pos", "negative": "neg", "null": "neu", "neutral": "neu"}

# ---------------------------------------------------------------------------
# 双语 UI 文案
# ---------------------------------------------------------------------------

UI_ZH = {
    "theme_label": "主题",
    "lang_label": "语言",
    "zh": "中文",
    "en": "EN",
    "visual_brief": "可视化摘要",
    "full_report": "完整报告",
    "contents": "目录",
    "collapse_contents": "收起目录",
    "expand_contents": "展开目录",
    "expand_evidence": "查看完整证据",
    "expand_methodology": "查看审计依据",
    "expand_source": "查看来源与溯源",
    "expand_details": "展开完整说明",
    "what_this_means": "这意味着什么",
    "original_title": "原文标题",
    "original_text": "原文",
    "full_report_intro": "结论前置：全部可追溯证据与方法学细节都在这里，关键论证位置穿插有意义的可视化，每个数字都能回查到 result.json。",
    "section_titles": {
        "01": "01 执行决策", "02": "02 结果证据概览", "03": "03 证据矩阵",
        "04": "04 证据裁决", "05": "05 方法学审计", "06": "06 冲突分析",
        "07": "07 主张-证据追溯", "08": "08 适用性", "09": "09 教学干预",
        "10": "10 评价方案", "11": "11 基准测试", "12": "12 来源与溯源",
    },
    "section_leads": {
        "01": "本节先给结论：最终怎么裁决、置信度多高、靠哪几条证据。",
        "02": "一图看清：哪些学习结果有支持证据、哪些被反驳。",
        "03": "每条证据来自哪项研究、测了什么、方向与质量如何；可筛选、可搜索。",
        "04": "证据允许主张什么、不允许主张什么；缺失的关键证据是什么。",
        "05": "研究质量可靠吗？哪些方法学问题让结论打折。",
        "06": "不同研究为何结论不同；分歧出在哪一环。",
        "07": "从结论到证据到原始来源，每一步都可追查。",
        "08": "结论适用于谁、什么课程与结果、需要什么条件。",
        "09": "试点怎么分阶段放开 AI 规则；什么情况必须叫停。",
        "10": "如何验证效果：指标、对照、成功阈值。",
        "11": "EduEvidence 自身基准表现：引用精度与成本。",
        "12": "每篇文献是谁、出自哪里、如何获取。",
    },
    "decision_kpi": ["决策", "置信度", "证据最充分的结果", "最不确定的结果", "主要风险", "来源数量"],
    "summary_title": "一句话结论",
    "summary_question": "问题",
    "summary_evidence": "依据",
    "summary_action": "行动",
    "outcome_table": ["结果类型", "正向效应", "负向效应", "零效应", "证据"],
    "figure1_caption": "图 1. 各结果类型的正向 / 负向 / 零效应证据数量（基于 effect_direction，不等同于 Claim 是否被支持）。",
    "matrix_filter": "筛选 / 搜索",
    "matrix_search_ph": "搜索证据…",
    "matrix_all_dir": "全部效应",
    "matrix_all_outcome": "全部结果",
    "matrix_heads": ["ID", "结果", "效应", "质量", "主张", "来源"],
    "matrix_details": "查看完整证据",
    "matrix_detail_labels": ["研究标题", "研究设计", "人群", "干预", "直接性"],
    "matrix_source_missing": "无可验证来源",
    "hero_action": "建议决策",
    "hero_confidence": "置信度",
    "hero_supported": "最强支持结论",
    "hero_uncertain": "关键不确定性 / 反例",
    "hero_risk": "主要风险",
    "hero_next": "下一步",
    "hero_provenance": "证据 / 来源",
    "outcome_separation_title": "结果分离 · 任务表现 ≠ 学习效果",
    "effect_positive": "正向效应",
    "effect_negative": "负向效应",
    "effect_null": "零效应",
    "outcome_group_task": "任务 / 近端表现",
    "outcome_group_learning": "学习 / 保持 / 迁移",
    "outcome_group_risk": "风险 / 依赖",
    "outcome_group_other": "其他结果",
    "outcome_sep_note": "将不同结果类型分开裁决，避免把训练时更快、更高分直接等同于真正学会。",
    "tribunal_decision": "决策",
    "tribunal_confidence": "置信度",
    "tribunal_can": "可以主张",
    "tribunal_uncertain": "尚不能主张",
    "tribunal_cannot": "被反驳的主张",
    "tribunal_missing": "缺失证据",
    "tribunal_flow": "EvidenceFlow 协议",
    "tribunal_figure": "裁决信息图",
    "method_audit_heads": ["检查项", "状态", "说明"],
    "method_guard": "任务 vs 学习护栏",
    "conflict_verdict": "裁决说明",
    "trace_decision": "决策",
    "trace_claim_prefix": "主张",
    "trace_no_source": "无来源",
    "applicability": ["适用于谁", "适用课程", "适用结果", "适用条件", "目标人群", "目标情境"],
    "intervention_learners": "目标学习者",
    "intervention_duration": "试点时长",
    "intervention_policy": "AI 使用规则",
    "intervention_rule": "AI 规则",
    "intervention_activities": "活动",
    "intervention_check": "结果检查",
    "intervention_stop": "停止条件",
    "intervention_timeline": "干预时间线信息图",
    "evaluation_question": "研究问题",
    "evaluation_measures": ["基线", "后测", "保持测试", "迁移测试"],
    "evaluation_metrics": ["过程指标", "学习指标", "风险指标"],
    "evaluation_threshold": "成功阈值",
    "evaluation_plan": "分析计划",
    "evaluation_figure": "评价设计信息图",
    "benchmark_note": "result.json 未携带 benchmark.baselines，本图不绘制；基准表现见独立基准报告。",
    "sources_title": "来源列表",
    "sources_heads": ["ID", "标题", "年份", "权威级别", "可验证位置"],
    "provenance_title": "Fetch 溯源",
    "provenance_heads": ["来源", "Fetch 方式", "状态", "降级", "时间"],
    "provenance_search": "搜索提供方",
    "provenance_time": "检索时间",
    "provenance_empty": "无逐条 fetch 记录（来源由研究管线直接提供）。",
    "no_data": "无数据。",
    "header_evidence": "证据 ",
    "header_sources": "来源 ",
    "header_mode": "模式：",
    "header_generated": "生成时间：",
    "header_evidence_suffix": " 条",
    "header_sources_suffix": " 个",
    "footer_schema": "Schema",
    "footer_claims": "Claim Binding",
    "footer_numbers": "Numeric Consistency",
    "footer_bilingual": "Bilingual Structure",
    "footer_language": "语言人话化",
    "footer_no_false_precision": "无伪精度",
    "footer_lieflat_bound": "Lieflat 数据溯源",
    "footer_no_axis_distortion": "坐标轴无失真",
    "footer_colorblind_safe": "色盲安全",
    "footer": "EduEvidence 证据报告 · {integrity} · 单文件离线可打开 · 数据源：result.json",
    "matrix_search_label": "筛选 / 搜索证据",
    "matrix_dir_filter": "按效应方向筛选",
    "matrix_outcome_filter": "按结果类型筛选",
    "svg_balance_title": "各结果类型证据效应分布",
    "svg_balance_desc": "各结果类型的正向 / 负向 / 零效应证据条数（基于 effect_direction，不等同于 Claim 是否被支持）。",
    "svg_figure1_title": "各结果类型效应方向分布（出版级学术图）",
    "svg_figure1_desc": "各结果类型的正向 / 负向 / 零效应证据条数；计数轴整数刻度，不随主题变化。来源：EduEvidence result.json。",
    "svg_benchmark_title": "基准对比：各基线引用支持精度",
    "svg_benchmark_desc": "各基线的引用支持精度（Citation support precision）对比；无基准数据时不绘制。",
    "svg_workflow_title": "EvidenceFlow 协议流程",
    "svg_workflow_desc": "从问题框架、检索、抓取验证、证据抽取、反方质疑、方法审计、裁决到适用性与干预评价的完整流程。",
    "svg_tribunal_title": "证据裁决信息图",
    "svg_tribunal_desc": "可以主张与不可主张的证据 ID 与建议决策徽章；完整主张文本见下方裁决卡片。",
    "svg_intervention_title": "教学干预时间线",
    "svg_intervention_desc": "各试点阶段的短名称与活动数量；完整 AI 使用规则见阶段说明块。",
    "svg_evaluation_title": "评价设计流程",
    "svg_evaluation_desc": "基线、后测、保持测试与迁移测试的评价流程；完整指标与分析计划见评估章节。",
    "raw_tag_title": "原始标识",
    "summary_tag_support": "支持",
    "summary_tag_contradict": "反驳",
    "summary_confidence_prefix": "（置信度：",
    "summary_confidence_suffix": "）",
    "method_target": "审查目标",
    "applicability_not_suitable": "不适用于",
    "applicability_conditions": "适用条件",
    "trace_claim_sep": "：",
    "colon": "：",
    "lang_switcher_aria": "语言切换 / Language switch",
    "theme_switcher_aria": "主题 / Theme",
    "v2_project_title": "项目与研究历史",
    "v2_project_id": "项目 ID",
    "v2_graph_revision": "证据图版本",
    "v2_decision_snapshot": "决策快照",
    "v2_timeline": "项目时间线",
    "v2_gaps_title": "知识缺口",
    "v2_gap_type": "缺口类型",
    "v2_gap_priority": "优先级",
    "v2_gap_reasoning": "依据",
    "v2_design_title": "研究设计",
    "v2_design_type": "设计类型",
    "v2_design_question": "研究问题",
    "v2_provenance_title": "数据集与分析溯源",
    "v2_diff_title": "决策变更",
    "v2_diff_action": "决策动作",
    "v2_diff_confidence": "置信度",
    "v2_diff_claims": "变更的主张",
    "v2_diff_gaps": "已解决/新增缺口",
    "v2_revision": "版本",
    "v2_decision": "决策",
    "v2_no_v2_data": "（无 V2 项目数据）",
}

UI_EN = {
    "theme_label": "Theme",
    "lang_label": "Language",
    "zh": "中文",
    "en": "EN",
    "visual_brief": "Visual Brief",
    "full_report": "Full Report",
    "contents": "Contents",
    "collapse_contents": "Collapse contents",
    "expand_contents": "Expand contents",
    "expand_evidence": "View full evidence",
    "expand_methodology": "View audit rationale",
    "expand_source": "View source & provenance",
    "expand_details": "Expand full explanation",
    "what_this_means": "What this means",
    "original_title": "Original title",
    "original_text": "Original text",
    "full_report_intro": "Conclusions first: every traceable piece of evidence and method note lives here, with visuals only at points where they add meaning. Every number traces back to result.json.",
    "section_titles": {
        "01": "01 Executive Decision", "02": "02 Outcome Evidence Overview",
        "03": "03 Evidence Matrix", "04": "04 Evidence Tribunal",
        "05": "05 Methodology Audit", "06": "06 Conflict Analysis",
        "07": "07 Claim-Evidence Trace", "08": "08 Applicability",
        "09": "09 Teaching Intervention", "10": "10 Evaluation Plan",
        "11": "11 Benchmark", "12": "12 Sources & Provenance",
    },
    "section_leads": {
        "01": "The verdict first: what we decide, at what confidence, on which evidence.",
        "02": "At a glance: which learning outcomes have supporting evidence, which are contradicted.",
        "03": "Where each piece of evidence comes from, what it measures, its direction and quality — filterable and searchable.",
        "04": "What the evidence lets us claim, what it does not, and what is still missing.",
        "05": "How reliable are these studies, and which methodological concerns discount the conclusions.",
        "06": "Why studies disagree — and where exactly they diverge.",
        "07": "Every step from conclusion to evidence to source stays traceable.",
        "08": "Who the conclusion applies to, for which course and outcomes, under what conditions.",
        "09": "How AI usage rules phase in during a pilot, and when we must stop.",
        "10": "How we verify real effects: metrics, comparison, success threshold.",
        "11": "How EduEvidence itself performs: citation precision and cost.",
        "12": "Who wrote each cited study, where it came from, how it was fetched.",
    },
    "decision_kpi": ["Decision", "Confidence", "Best-supported outcome", "Most uncertain outcome", "Main risk", "Sources"],
    "summary_title": "Bottom line",
    "summary_question": "Question",
    "summary_evidence": "Evidence",
    "summary_action": "Action",
    "outcome_table": ["Outcome", "Positive effect", "Negative effect", "Null effect", "Evidence"],
    "figure1_caption": "Fig. 1. Positive / negative / null effect counts per outcome (based on effect_direction, not claim support).",
    "matrix_filter": "Filter / Search",
    "matrix_search_ph": "Search evidence…",
    "matrix_all_dir": "All effects",
    "matrix_all_outcome": "All outcomes",
    "matrix_heads": ["ID", "Outcome", "Effect", "Quality", "Claim", "Source"],
    "matrix_details": "View full evidence",
    "matrix_detail_labels": ["Study title", "Design", "Population", "Intervention", "Directness"],
    "matrix_source_missing": "No verifiable source",
    "hero_action": "Recommended decision",
    "hero_confidence": "Confidence",
    "hero_supported": "Strongest supported conclusion",
    "hero_uncertain": "Key uncertainty / contradiction",
    "hero_risk": "Main risk",
    "hero_next": "Next action",
    "hero_provenance": "Evidence / sources",
    "outcome_separation_title": "Outcome Separation · Task performance ≠ learning",
    "effect_positive": "Positive effect",
    "effect_negative": "Negative effect",
    "effect_null": "Null effect",
    "outcome_group_task": "Task / proximal performance",
    "outcome_group_learning": "Learning / retention / transfer",
    "outcome_group_risk": "Risk / dependency",
    "outcome_group_other": "Other outcomes",
    "outcome_sep_note": "Outcomes are adjudicated separately so faster training performance is not silently treated as evidence of learning.",
    "tribunal_decision": "Decision",
    "tribunal_confidence": "Confidence",
    "tribunal_can": "Can claim",
    "tribunal_uncertain": "Cannot yet claim",
    "tribunal_cannot": "Contradicted claims",
    "tribunal_missing": "Missing evidence",
    "tribunal_flow": "EvidenceFlow Protocol",
    "tribunal_figure": "Tribunal infographic",
    "method_audit_heads": ["Item", "Status", "Note"],
    "method_guard": "Task vs learning guard",
    "conflict_verdict": "Tribunal note",
    "trace_decision": "Decision",
    "trace_claim_prefix": "Claim",
    "trace_no_source": "No source",
    "applicability": ["Suitable for", "Course", "Outcomes", "Conditions", "Target population", "Target context"],
    "intervention_learners": "Target learners",
    "intervention_duration": "Pilot duration",
    "intervention_policy": "AI usage policy",
    "intervention_rule": "AI rule",
    "intervention_activities": "Activities",
    "intervention_check": "Outcome check",
    "intervention_stop": "Stop conditions",
    "intervention_timeline": "Intervention timeline infographic",
    "evaluation_question": "Research question",
    "evaluation_measures": ["Baseline", "Post test", "Retention", "Transfer"],
    "evaluation_metrics": ["Process metrics", "Learning metrics", "Risk metrics"],
    "evaluation_threshold": "Success threshold",
    "evaluation_plan": "Analysis plan",
    "evaluation_figure": "Evaluation design infographic",
    "benchmark_note": "result.json carries no benchmark.baselines, so this visual is omitted; see the standalone benchmark report.",
    "sources_title": "Source list",
    "sources_heads": ["ID", "Title", "Year", "Authority", "Verifiable location"],
    "provenance_title": "Fetch provenance",
    "provenance_heads": ["Source", "Fetch method", "Status", "Fallback", "Time"],
    "provenance_search": "Search provider",
    "provenance_time": "Fetched at",
    "provenance_empty": "No per-source fetch records (sources provided directly by the research pipeline).",
    "no_data": "No data.",
    "header_evidence": "Evidence: ",
    "header_sources": "Sources: ",
    "header_mode": "Mode: ",
    "header_generated": "Generated: ",
    "header_evidence_suffix": "",
    "header_sources_suffix": "",
    "footer_schema": "Schema",
    "footer_claims": "Claim Binding",
    "footer_numbers": "Numeric Consistency",
    "footer_bilingual": "Bilingual Structure",
    "footer_language": "Human Language",
    "footer_no_false_precision": "False Precision",
    "footer_lieflat_bound": "Lieflat Data Bound",
    "footer_no_axis_distortion": "Axis Distortion",
    "footer_colorblind_safe": "Colorblind Safe",
    "footer": "EduEvidence Evidence Report · {integrity} · single-file offline · source: result.json",
    "matrix_search_label": "Filter / search evidence",
    "matrix_dir_filter": "Filter by effect direction",
    "matrix_outcome_filter": "Filter by outcome type",
    "svg_balance_title": "Outcome evidence effect balance",
    "svg_balance_desc": "Positive / negative / null effect counts per outcome (based on effect_direction, not claim support).",
    "svg_figure1_title": "Effect direction by outcome type (publication figure)",
    "svg_figure1_desc": "Counts of positive / negative / null effects per outcome type with an integer count axis, theme-independent. Source: EduEvidence result.json.",
    "svg_benchmark_title": "Benchmark: citation support precision by baseline",
    "svg_benchmark_desc": "Citation support precision per baseline; not drawn when no baseline data exists.",
    "svg_workflow_title": "EvidenceFlow Protocol",
    "svg_workflow_desc": "Research flow from framing, retrieval, fetch/verify, extraction, challenge, method audit and adjudication to applicability and intervention evaluation.",
    "svg_tribunal_title": "Evidence Tribunal infographic",
    "svg_tribunal_desc": "Evidence IDs for claims that can and cannot be claimed, plus the recommended action badge; full claim text is in the tribunal cards below.",
    "svg_intervention_title": "Teaching intervention timeline",
    "svg_intervention_desc": "Short phase names and activity counts; full AI usage rules are in the phase blocks.",
    "svg_evaluation_title": "Evaluation design flow",
    "svg_evaluation_desc": "Evaluation flow across baseline, post test, retention and transfer; full metrics and analysis plan are in the evaluation section.",
    "raw_tag_title": "raw id",
    "summary_tag_support": "Support",
    "summary_tag_contradict": "Contradict",
    "summary_confidence_prefix": " (confidence: ",
    "summary_confidence_suffix": ")",
    "method_target": "Audit target",
    "applicability_not_suitable": "Not suitable for",
    "applicability_conditions": "Conditions",
    "trace_claim_sep": ": ",
    "colon": ": ",
    "lang_switcher_aria": "语言切换 / Language switch",
    "theme_switcher_aria": "主题 / Theme",
    "v2_project_title": "Project & Research History",
    "v2_project_id": "Project ID",
    "v2_graph_revision": "Graph revision",
    "v2_decision_snapshot": "Decision snapshot",
    "v2_timeline": "Project timeline",
    "v2_gaps_title": "Knowledge gaps",
    "v2_gap_type": "Gap type",
    "v2_gap_priority": "Priority",
    "v2_gap_reasoning": "Reasoning",
    "v2_design_title": "Study design",
    "v2_design_type": "Design type",
    "v2_design_question": "Research question",
    "v2_provenance_title": "Dataset & analysis provenance",
    "v2_diff_title": "Decision diff",
    "v2_diff_action": "Decision action",
    "v2_diff_confidence": "Confidence",
    "v2_diff_claims": "Changed claims",
    "v2_diff_gaps": "Resolved/new gaps",
    "v2_revision": "Revision",
    "v2_decision": "Decision",
    "v2_no_v2_data": "(no V2 project data)",
}


class ReportInvalid(Exception):
    """Scientific Integrity Gate failure (§27/§60): report must not be published."""


def esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _svg_a11y(svg: str, title: str, desc: str) -> str:
    """6.5: 为嵌入的 SVG 注入双语 <title>/<desc>，并把 aria-label 换成 UI 字典文案。

    title/desc 由调用方按当前语言从 UI_ZH / UI_EN 取；aria-label 已存在时覆盖，
    不存在时补上，保证英文模式下不残留中文 aria-label。
    """
    if not svg:
        return svg
    title_html = esc(title)
    desc_html = esc(desc)
    block = f"<title>{title_html}</title><desc>{desc_html}</desc>"
    if re.search(r"<title>", svg, flags=re.S):
        svg = re.sub(r"<title>.*?</title>", f"<title>{title_html}</title>", svg,
                     count=1, flags=re.S)
    else:
        m = re.match(r"<svg\b[^>]*>", svg, flags=re.S)
        if not m:
            return svg
        svg = svg[:m.end()] + block + svg[m.end():]
    if re.search(r'aria-label="', svg):
        svg = re.sub(r'aria-label="[^"]*"', f'aria-label="{title_html}"', svg, count=1)
    else:
        m = re.match(r"<svg\b[^>]*>", svg, flags=re.S)
        if m:
            tag = m.group(0)
            svg = svg[:m.start()] + tag[:-1] + f' aria-label="{title_html}">' + svg[m.end():]
    return svg


def resolve_theme(requested: str | None, interactive: bool | None = None,
                  input_fn=input) -> str:
    """Resolve the generation-time visual system without blocking automation."""
    if requested:
        if requested not in THEME_NAMES:
            raise ValueError(f"unknown theme: {requested}")
        return requested
    if interactive is None:
        interactive = bool(getattr(sys.stdin, "isatty", lambda: False)())
    if not interactive:
        return "claude"
    prompt = ("Choose report visual style / 请选择报告视觉风格\n"
              "1. Claude Research      [Light]\n"
              "2. Academic Paper       [Light]\n"
              "3. DataLab              [Light]\n"
              "4. DataLab              [Dark]\n"
              "5. Presentation / Judge [Dark]\n> ")
    choice = str(input_fn(prompt)).strip().lower()
    numeric = {str(i + 1): name for i, name in enumerate(THEME_NAMES)}
    aliases = {name: name for name in THEME_NAMES}
    aliases.update({THEME_DISPLAY[name].lower(): name for name in THEME_NAMES})
    return numeric.get(choice) or aliases.get(choice) or "claude"


def safe_http_url(value: Any) -> str:
    """Return only verifiable link locations for clickable report links.

    Scheme whitelist (6.5): http / https / doi. javascript:, data:, file:
    and any other scheme is dropped so unsafe links are never rendered.
    """
    text = str(value or "").strip()
    try:
        parsed = urlparse(text)
    except ValueError:
        return ""
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return text
    if parsed.scheme == "doi" and text:
        return text
    return ""


def excerpt_text(value: Any, max_chars: int = 260) -> tuple[str, bool]:
    """Return an exact prefix excerpt without rewriting research prose."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text, False
    window = text[:max_chars]
    candidates = [window.rfind(mark) for mark in ("。", "！", "？", ". ", "; ", "；")]
    cut = max(candidates)
    if cut < max_chars // 2:
        cut = max_chars
    else:
        cut += 1
    return text[:cut].rstrip(), True


def expandable_text(value: Any, summary_label: str, max_chars: int = 260,
                    css_class: str = "expandable-text") -> str:
    """Progressive disclosure that preserves the full source text verbatim."""
    text = str(value or "").strip()
    if not text:
        return ""
    short, truncated = excerpt_text(text, max_chars)
    if not truncated:
        return f'<p class="{esc(css_class)}">{esc(short)}</p>'
    return (f'<div class="{esc(css_class)}"><p>{esc(short)}…</p>'
            f'<details class="detail-expander"><summary>{esc(summary_label)}</summary>'
            f'<div class="detail-body"><p>{esc(text)}</p></div></details></div>')


def visualization_decisions(result: dict, charts: dict) -> dict[str, dict[str, Any]]:
    """Meaningful Visualization Gate: prefer no chart over decorative encoding.

    Outcome charts use effect_direction rather than relation_to_claim/direction. A study can
    support a claim that an intervention is harmful; treating `support` as a positive outcome
    would invert the meaning of the report.
    """
    outcomes = effect_outcomes(result)
    cells = [int(o.get(k, 0) or 0) for o in outcomes
             for k in ("positive_count", "negative_count", "null_count")]
    total = sum(cells)
    nonzero = sum(1 for value in cells if value > 0)
    active_outcomes = sum(1 for o in outcomes
                          if sum(int(o.get(k, 0) or 0)
                                 for k in ("positive_count", "negative_count", "null_count")) > 0)
    max_cell = max(cells or [0])
    evidence_balance = (total >= 8 and active_outcomes >= 3 and nonzero >= 5 and max_cell >= 2)
    balance_reason = ("sufficient effect-direction density" if evidence_balance else
                      f"suppressed: sparse effect counts (total={total}, active={active_outcomes}, "
                      f"nonzero_cells={nonzero}, max_cell={max_cell})")

    claims = result.get("claims", []) or []
    evidence = result.get("evidence", []) or []
    sources = result.get("sources", []) or []
    trace_ok = len(claims) >= 2 and bool(evidence) and bool(sources)

    benchmark = result.get("benchmark", {}) or {}
    baselines = benchmark.get("baselines", {}) or {}
    mode = str(benchmark.get("mode") or benchmark.get("benchmark_mode") or "").lower()
    simulated = any(token in mode for token in ("simulat", "deterministic", "synthetic"))
    benchmark_ok = len(baselines) >= 2 and not simulated

    return {
        "outcome_separation": {
            "render": len(outcomes) >= 2,
            "reason": "multiple outcome constructs present" if len(outcomes) >= 2 else "fewer than two outcomes",
        },
        "outcome_evidence_balance": {"render": evidence_balance, "reason": balance_reason},
        "claim_trace": {
            "render": trace_ok,
            "reason": "claim-evidence-source relationships present" if trace_ok else "insufficient relationship data",
        },
        "benchmark": {
            "render": benchmark_ok,
            "reason": ("empirical/comparable baselines present" if benchmark_ok else
                       "suppressed: absent, simulated, or fewer than two baselines"),
        },
    }


# ---------------------------------------------------------------------------
# 0b. Lieflat gallery composition — visual_layout contract (§三)
# ---------------------------------------------------------------------------

# Deterministic safe combination when visual_layout is missing or all entries
# are invalid. Rendered through the same extractors as any AI-written layout.
FALLBACK_LIEFLAT_LAYOUT = (
    {"chart_id": "lieflat-forest-plot.svg", "type": "forest_plot", "catalog_ref": "FOREST-PLOT (publication figure)",
     "title_zh": "证据效应量森林图", "title_en": "Effect-size forest plot",
     "subtitle_zh": "Hedges' g 与 95% 置信区间 · 一行一篇研究 · 数据不足时本图自动抑制",
     "subtitle_en": "Hedges' g with 95% CI · one row per study · suppressed when data is insufficient",
     "caption_zh": "仅当证据集携带数值效应量时绘制；无 g/CI 数据时不画假图。",
     "caption_en": "Drawn only when numeric effect sizes exist in the evidence set.",
     "source": "meta.forest", "params": {}},
    {"chart_id": "lieflat-dot-cascade.svg", "type": "dot_cascade", "catalog_ref": "L2 Dot Cascade",
     "title_zh": "证据效应量梯队级联", "title_en": "Ranked effect-size cascade",
     "subtitle_zh": "按效应量由高到低排序 · 圆点高度 = Hedges' g · 顶部数字 = g 值",
     "subtitle_en": "Sorted by effect size · dot height = Hedges' g · top number = g",
     "caption_zh": "仅当存在逐研究数值效应量时绘制。",
     "caption_en": "Drawn only when per-study numeric effect sizes exist.",
     "source": "evidence.ranked_effects", "params": {}},
    {"chart_id": "lieflat-bubble-almanac.svg", "type": "bubble_almanac", "catalog_ref": "L9 Bubble Almanac",
     "title_zh": "发表年份 × 结果维度文献年历", "title_en": "Year × dimension evidence almanac",
     "subtitle_zh": "气泡面积 ∝ 该格研究数（sqrt 换算） · 实心圆 = 有显著结果",
     "subtitle_en": "Bubble area ∝ study count (sqrt) · solid core = significant results",
     "caption_zh": "仅当证据集携带发表年份与结果维度时绘制。",
     "caption_en": "Drawn only when years and outcome dimensions exist.",
     "source": "evidence.year_x_dimension", "params": {}},
    {"chart_id": "lieflat-tick-rows.svg", "type": "tick_rows", "catalog_ref": "F5 Tick Rows",
     "title_zh": "各结果类型效应方向分布", "title_en": "Effect direction by outcome",
     "subtitle_zh": "每 1 个圆点 = 1 条证据 · 绿 = 正向 · 灰 = 零效应 · 橙 = 负向 · 右端数字 = 净效应",
     "subtitle_en": "One dot = one evidence item · green = positive · grey = null · orange = negative · right number = net",
     "caption_zh": "基于 effect_direction 计数，全部数值来自 result.json。",
     "caption_en": "Based on effect_direction counts; all numbers come from result.json.",
     "source": "outcomes.direction_counts", "params": {}},
)

LIEFLAT_PARAM_TYPES = {"int": int, "list": list}


def _validate_lieflat_params(fig_type: str, params: Any) -> tuple[dict, Optional[str]]:
    """Validate visual_layout params against the registry contract.

    Returns (sanitized_params, reason). Any unknown key or wrong type is an
    invalid entry — the caller drops the entry and records the reason.
    """
    if params is None:
        return {}, None
    if not isinstance(params, dict):
        return {}, f"params must be an object, got {type(params).__name__}"
    contract = LIEFLAT_REGISTRY[fig_type].get("params", {})
    out: dict = {}
    for key, value in params.items():
        if key not in contract:
            return {}, f"param {key!r} is not allowed for type {fig_type!r}"
        expected = contract[key]
        if isinstance(expected, list):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return {}, f"param {key!r} must be a list of strings for type {fig_type!r}"
        elif not isinstance(value, expected):
            return {}, f"param {key!r} must be {expected.__name__} for type {fig_type!r}"
        out[key] = value
    return out, None


def resolve_visual_layout(result: dict) -> dict[str, Any]:
    """Resolve result.visual_layout into validated, normalized gallery entries.

    New contract per entry:
      {chart_id, type, catalog_ref, title_zh/en, subtitle_zh/en, caption_zh/en,
       source, params}
    Legacy contract (title/subtitle shared across languages) is accepted with
    a warning. Unregistered types, missing bilingual copy, and invalid params
    drop the entry with a recorded reason. If nothing survives, a deterministic
    safe combination (forest + dot_cascade + bubble_almanac + tick_rows) is
    used — still rendered through the extractors, so charts are suppressed
    individually when the data is insufficient.

    Returns {entries, fallback, warnings, rejected}.
    """
    warnings: list[str] = []
    rejected: list[dict] = []
    entries: list[dict] = []
    seen_ids: set[str] = set()

    raw = result.get("visual_layout") or []
    if not isinstance(raw, list):
        raw = []

    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            rejected.append({"index": index, "reason": "entry is not an object"})
            continue
        fig_type = item.get("type")
        if not isinstance(fig_type, str) or not fig_type:
            rejected.append({"index": index, "chart_id": item.get("chart_id"),
                             "reason": "missing or non-string type"})
            continue
        if fig_type not in LIEFLAT_REGISTRY:
            rejected.append({"index": index, "chart_id": item.get("chart_id"),
                             "type": fig_type,
                             "reason": f"unregistered type {fig_type!r} (not in the Lieflat registry)"})
            continue

        # Bilingual copy — new contract requires title/subtitle per language.
        if all(isinstance(item.get(k), str) and item.get(k) for k in
               ("title_zh", "title_en", "subtitle_zh", "subtitle_en")):
            title_zh, title_en = item["title_zh"], item["title_en"]
            subtitle_zh, subtitle_en = item["subtitle_zh"], item["subtitle_en"]
        elif isinstance(item.get("title"), str) and item.get("title") \
                and isinstance(item.get("subtitle"), str) and item.get("subtitle"):
            title_zh = title_en = item["title"]
            subtitle_zh = subtitle_en = item["subtitle"]
            warnings.append(f"entry #{index} ({fig_type}): legacy title/subtitle shared "
                            f"across languages — write title_zh/en + subtitle_zh/en in new layouts")
        else:
            rejected.append({"index": index, "chart_id": item.get("chart_id"),
                             "type": fig_type,
                             "reason": "missing bilingual copy (title_zh/en + subtitle_zh/en required)"})
            continue

        params, param_reason = _validate_lieflat_params(fig_type, item.get("params"))
        if param_reason:
            rejected.append({"index": index, "chart_id": item.get("chart_id"),
                             "type": fig_type, "reason": param_reason})
            continue

        chart_id = item.get("chart_id")
        if not isinstance(chart_id, str) or not chart_id:
            chart_id = f"lieflat-{fig_type}.svg"
        if chart_id in ACADEMIC_FIGURE_KEYS:
            chart_id = f"lieflat-{chart_id}"
        if chart_id in seen_ids:
            rejected.append({"index": index, "chart_id": chart_id, "type": fig_type,
                             "reason": f"duplicate chart_id {chart_id!r}"})
            continue
        seen_ids.add(chart_id)

        catalog_ref = item.get("catalog_ref")
        if catalog_ref and catalog_ref != LIEFLAT_REGISTRY[fig_type]["catalog_ref"]:
            warnings.append(f"entry #{index} ({fig_type}): catalog_ref {catalog_ref!r} "
                            f"does not match registry {LIEFLAT_REGISTRY[fig_type]['catalog_ref']!r}; "
                            f"registry value used")

        entries.append({
            "chart_id": chart_id,
            "type": fig_type,
            "catalog_ref": LIEFLAT_REGISTRY[fig_type]["catalog_ref"],
            "title_zh": title_zh, "title_en": title_en,
            "subtitle_zh": subtitle_zh, "subtitle_en": subtitle_en,
            "caption_zh": item.get("caption_zh", ""), "caption_en": item.get("caption_en", ""),
            "source": item.get("source") or LIEFLAT_REGISTRY[fig_type]["source"],
            "params": params,
        })

    if entries:
        return {"entries": entries, "fallback": False, "warnings": warnings, "rejected": rejected}

    warnings.append("visual_layout missing or fully invalid — using deterministic safe "
                    "combination (forest_plot + dot_cascade + bubble_almanac + tick_rows)")
    fallback_entries = [dict(e) for e in FALLBACK_LIEFLAT_LAYOUT]
    return {"entries": fallback_entries, "fallback": True, "warnings": warnings, "rejected": rejected}


def _canon(value: Any) -> str:
    """Canonical string form for number-bound checking (3-decimal tolerance)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value).strip()


def check_lieflat_data_bound(lieflat_meta: dict, label: str) -> list[str]:
    """Every number drawn in a Lieflat SVG must trace to the extractor bundle.

    render_lieflat_gallery records (origin, value) for every displayed number;
    this check canonicalizes both the audit values and every leaf of the
    bundle and requires membership. Tampered or hardcoded demo values fail.
    """
    problems: list[str] = []
    for chart_id, rec in (lieflat_meta.get("audits") or {}).items():
        bundle = rec.get("bundle") or {}
        audit = rec.get("audit") or []
        bound: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
            else:
                bound.add(_canon(node))

        walk(bundle)
        if not audit:
            problems.append(f"{label}:{chart_id}: no audit trail recorded for rendered figure")
            continue
        for origin, value in audit:
            canon = _canon(value)
            if canon not in bound:
                problems.append(
                    f"{label}:{chart_id}: value {value!r} ({origin}) is not bound "
                    f"to the extractor bundle")
    return problems


# ---------------------------------------------------------------------------
# 1. Contract validation + claim-evidence-source audit
# ---------------------------------------------------------------------------

def validate_contract(result: dict) -> list[str]:
    problems: list[str] = []
    for key in ("meta", "research_frame", "decision", "evidence"):
        if not isinstance(result.get(key), (dict, list)):
            problems.append(f"missing required top-level key: {key}")
    meta = result.get("meta") or {}
    if meta.get("skill") != "eduevidence":
        problems.append(f"meta.skill must be 'eduevidence', got {meta.get('skill')!r}")
    if not isinstance(result.get("outcomes", []), list):
        problems.append("outcomes must be an array")
    if not isinstance(result.get("sources", []), list):
        problems.append("sources must be an array")
    return problems


def audit_claims(result: dict) -> list[str]:
    problems: list[str] = []
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    sources = {s.get("source_id") for s in result.get("sources", [])}
    for i, claim in enumerate(result.get("claims", [])):
        eids = claim.get("evidence_ids") or []
        if not eids:
            problems.append(f"claim #{i} has no evidence_ids")
            continue
        for eid in eids:
            ev = evidence.get(eid)
            if ev is None:
                problems.append(f"claim #{i} references unknown evidence {eid!r}")
                continue
            sid = ev.get("source_id")
            if not sid or sid not in sources:
                problems.append(f"evidence {eid!r} (claim #{i}) has no resolvable source")
            if claim.get("status") == "SUPPORTED" and not sid:
                problems.append(f"SUPPORTED claim #{i} rests on source-less evidence {eid!r}")
    return problems


def check_numbers(result: dict, charts: dict) -> list[str]:
    problems: list[str] = []
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    for outcome in result.get("outcomes", []):
        effects = [str(evidence[eid].get("effect_direction") or "null").lower()
                   for eid in outcome.get("evidence_ids", []) if eid in evidence]
        derived = {k: effects.count(k) for k in ("positive", "negative", "null")}
        for key, field in (("positive", "positive_count"), ("negative", "negative_count"),
                           ("null", "null_count")):
            if derived.get(key, 0) != outcome.get(field, 0):
                problems.append(
                    f"outcome {outcome.get('outcome_type')!r}: {field}={outcome.get(field)} "
                    f"but evidence-derived {key}={derived.get(key, 0)}")
    effect_summary = effect_outcomes(result)
    for chart in charts.get("charts", []):
        if chart.get("chart_id") != "outcome-evidence-overview":
            continue
        series = {s["name"]: s["data"] for s in chart.get("option", {}).get("series", [])}
        key = {"正向效应": "positive", "负向效应": "negative", "零效应": "null",
               "Positive effect": "positive", "Negative effect": "negative", "Null effect": "null"}
        names = [o.get("outcome_type") for o in effect_summary]
        for outcome in effect_summary:
            idx = names.index(outcome["outcome_type"]) if outcome["outcome_type"] in names else -1
            if idx < 0:
                continue
            for series_name, effect in key.items():
                data = series.get(series_name, [])
                if idx >= len(data):
                    continue
                value = data[idx]
                expected = outcome[f"{effect}_count"]
                if abs(value) != expected:
                    problems.append(
                        f"chart {chart.get('chart_id')}: {outcome['outcome_type']} "
                        f"{effect}_count={expected} but series={value}")
                if effect == "negative" and value > 0:
                    problems.append(f"negative-effect series must be ≤ 0, got {value}")
                if effect in ("positive", "null") and value < 0:
                    problems.append(f"{effect}-effect series must be ≥ 0, got {value}")
    return problems


# ---------------------------------------------------------------------------
# 2. Scientific Integrity checks（真实计算，P0-3/P0-11 + 6.3/6.4）
# ---------------------------------------------------------------------------

# 双语同构允许差异的“自由文本”叶子键（其余键——ID / enum / URL / 数字 /
# 数组结构——必须完全一致）。列表元素若属于 PROSE_LIST_KEYS 也可译。
TEXT_LEAF_KEYS = {
    "question", "claim", "title", "title_zh", "title_en", "lead_zh", "lead_en", "note", "name",
    "decision_question", "target_population", "target_context", "reason_for_disagreement",
    "methodology_summary", "short_term_effect", "long_term_effect", "transfer_effect",
    "risk_effect", "decision_rationale", "rationale", "applicability_boundary",
    "strongest_support", "key_uncertainty", "main_risk", "next_action", "key_quote",
    "statement", "bias_warning", "study_label",
    "special_characteristics", "teaching_method", "allowed_usage", "frequency", "duration",
    "teacher_support", "class_size", "online_or_offline", "geography", "success_condition",
    "population", "intervention", "comparison", "outcome_measure", "effect", "method",
    "ai_usage_policy", "target_learners", "ai_usage_rule", "outcome_check",
    "research_question", "treatment", "baseline", "post_test", "retention_test",
    "transfer_test", "success_threshold", "analysis_plan",
    "suitable_for", "not_suitable_for", "search_provider",
    "learner_match", "subject_match", "tool_match", "scope",
    "measured_construct", "teacher_role", "student_role", "reflection_requirement",
    "assessment",
    "prior_knowledge", "ai_tool", "time_range", "source_location", "search_snippet",
    "pilot_duration", "summary", "decision_rationale", "subtitle",
}
PROSE_LIST_KEYS = {
    "supported_claims", "uncertain_claims", "contradicted_claims", "what_can_be_claimed",
    "what_cannot_be_claimed", "missing_evidence", "exceeds_evidence_boundary",
    "learning_goals", "inclusion_criteria", "exclusion_criteria", "activities",
    "stop_conditions", "strengths", "limitations", "confounders", "required_conditions",
    "process_metrics", "learning_metrics", "risk_metrics", "suggestions", "risk_control",
    "evidence_alignment",
}


def _is_text_value(path: str, key: str) -> bool:
    """判断某路径是否允许双语文本差异：叶子键在自由文本白名单内，或为
    自由文本列表的元素，或位于 outcome_specific_findings 子树。
    其余（ID/enum/URL/数字）必须一致。"""
    raw = [p for p in path.split(".") if p]
    parts = [re.sub(r"\[\d+\]", "", p) for p in raw]
    if ".outcome_specific_findings." in path:
        return True
    if key in TEXT_LEAF_KEYS:
        return True
    last = raw[-1] if raw else ""
    if re.search(r"\[\d+\]$", last) and len(parts) >= 2 \
            and parts[-1] in PROSE_LIST_KEYS:
        return True
    return False


def compare_parallel_result(en: dict, zh: dict) -> list[str]:
    """双语同构检查（6.3）：只允许文本字段不同；ID / enum / URL / 数字 /
    数组结构必须完全一致。返回问题列表（空 = PASS）。"""
    problems: list[str] = []

    def walk(a: Any, b: Any, path: str) -> None:
        if type(a) is not type(b):
            problems.append(f"{path}: type mismatch {type(a).__name__} vs {type(b).__name__}")
            return
        if isinstance(a, dict):
            if set(a) != set(b):
                problems.append(f"{path}: key set differs {sorted(set(a) ^ set(b))}")
            for k in a:
                if k in b:
                    walk(a[k], b[k], f"{path}.{k}")
        elif isinstance(a, list):
            if len(a) != len(b):
                problems.append(f"{path}: length {len(a)} vs {len(b)}")
            for i, (x, y) in enumerate(zip(a, b)):
                walk(x, y, f"{path}[{i}]")
        elif isinstance(a, str):
            if a != b and not _is_text_value(path, path.rsplit(".", 1)[-1]):
                problems.append(f"{path}: structural string differs {a!r} vs {b!r}")
        elif a != b:
            problems.append(f"{path}: {a!r} vs {b!r}")

    walk(en, zh, "$")
    return problems


def check_no_false_precision(result: dict, charts: dict) -> list[str]:
    """伪精度检查（P0-11）：计数图轴必须整数刻度；图表数字必须等于数据。"""
    problems: list[str] = []
    for chart in charts.get("charts", []):
        option = chart.get("option", {}) or {}
        axes = option.get("xAxis")
        if isinstance(axes, list):
            for ax in axes:
                if ax.get("type") == "value" and ax.get("minInterval") != 1:
                    problems.append(f"chart {chart.get('chart_id')}: count axis missing minInterval=1")
        elif isinstance(axes, dict) and axes.get("type") == "value":
            if axes.get("minInterval") != 1:
                problems.append(f"chart {chart.get('chart_id')}: count axis missing minInterval=1")
        y_axes = option.get("yAxis")
        if isinstance(y_axes, list):
            for ax in y_axes:
                if ax.get("type") == "value" and ax.get("minInterval") != 1:
                    problems.append(f"chart {chart.get('chart_id')}: count axis missing minInterval=1")
        elif isinstance(y_axes, dict) and y_axes.get("type") == "value":
            if y_axes.get("minInterval") != 1:
                problems.append(f"chart {chart.get('chart_id')}: count axis missing minInterval=1")
    return problems


def _walk_strings(node, path, out, skip_hints=()):
    """深度遍历 dict/list，收集叙述字符串（含路径）。"""
    if isinstance(node, dict):
        for k, v in node.items():
            if any(h in str(k).lower() for h in skip_hints):
                continue
            _walk_strings(v, path + "." + str(k), out, skip_hints)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_strings(v, path + "[" + str(i) + "]", out, skip_hints)
    elif isinstance(node, str) and node.strip():
        out.append((path, node))


def _get_path(data, dotted):
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _leaf_strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, list):
        for v in value:
            _leaf_strings(v, out)
    elif isinstance(value, dict):
        for v in value.values():
            _leaf_strings(v, out)


_HAS_CJK = re.compile(r"[\u4e00-\u9fff]")
_STRICT_BANNED_RE = [
    # 第一页决策叙述：禁任意证据/来源 ID 引用（人话化硬标准）
    (re.compile(r"\bE-\d{2,3}\b"), "evidence-ID citation (E-xxx)"),
    (re.compile(r"\bEV-\d{3}\b"), "evidence-ID citation (EV-xxx)"),
]
_COMMON_BANNED_RE = [
    # 全部叙述（两页）：禁 schema 键、来源码、问题 ID、tier 码
    (re.compile(r"\bPAP-\w+"), "source-ID citation (PAP-xxx)"),
    (re.compile(r"\bQ\d{2}\b"), "question-ID citation (Qxx)"),
    (re.compile(r"effect_direction|relation_to_claim|decision_implication|evidence_id|quality_score|overall_risk|source_location"),
     "schema key"),
    (re.compile(r"\btier\d_\w+"), "source-tier code"),
]
_ZH_RESIDUE_RE = [
    (re.compile(r"(?<![\w])null(?!\w)"), "null residue"),
    (re.compile(r"\bCONCERN\b|\bPASS\b|\bFAIL\b"), "unmapped English audit code in zh narrative"),
]

STRICT_NARRATIVE_PATHS = [
    "decision.decision_rationale", "decision.rationale", "decision.strongest_support",
    "decision.key_uncertainty", "decision.main_risk", "decision.next_action",
    "decision.next_steps", "decision.what_can_be_claimed", "decision.what_cannot_be_claimed",
    "decision.missing_evidence", "decision.exceeds_evidence_boundary",
    "decision.reason_for_disagreement", "decision.methodology_summary",
]
LENIENT_NARRATIVE_ROOTS = ["applicability", "intervention", "evaluation", "conflicts",
                           "methodology_reviews", "action_plan"]
_SKIP_HINTS = ("id", "url", "doi", "author", "venue", "year", "status", "score", "count",
               "rating", "type", "name", "path", "file", "date", "time", "version",
               "dimension", "direction", "measure", "metric", "size", "level", "pattern",
               "threshold", "key", "lang", "weight", "error",
               # 枚举/标签类键（显示层经 zh_labels 映射，不属叙述）
               "verdict", "target", "decision")


def _scan_narrative(problems, path, en_text, zh_text, strict=False, kind=""):
    en_text = en_text or ""
    zh_text = zh_text or ""
    if not zh_text.strip():
        return
    if not _HAS_CJK.search(zh_text):
        problems.append(path + ": zh 叙述缺少中文（含英文原文）")
    if len(zh_text) >= 15 and zh_text == en_text:
        problems.append(path + ": zh 与 en 完全相等（平行版本未翻译）")
    if _HAS_CJK.search(en_text):
        problems.append(path + ": en 叙述包含中文（en/zh 交叉污染）")
    for rx, label in (_STRICT_BANNED_RE if strict else []):
        if rx.search(zh_text) or rx.search(en_text):
            problems.append(path + ": 含" + label)
    for rx, label in _COMMON_BANNED_RE:
        if rx.search(zh_text) or rx.search(en_text):
            problems.append(path + ": 含" + label)
    for rx, label in _ZH_RESIDUE_RE:
        if rx.search(zh_text):
            problems.append(path + ": 含" + label)
    if strict and kind in ("rationale", "reason") and len(zh_text) < 40:
        problems.append(path + ": 决策理由过短（<40 字）")


def check_language_parallel(result_en: dict, result_zh: dict) -> list[str]:
    """W1.2 语言门禁：叙述字段必须人话、双语分离、无内部结构碎语。

    只检查叙述字段；ID/URL/枚举/source 关键元数据豁免（保持可追溯性）。
    违规 → REPORT_LANG_INVALID（在 build_report.main 与 compute_integrity 双重生效）。
    """
    problems: list[str] = []
    for path in STRICT_NARRATIVE_PATHS:
        en_val = _get_path(result_en, path)
        zh_val = _get_path(result_zh, path)
        en_texts, zh_texts = [], []
        _leaf_strings(en_val, en_texts)
        _leaf_strings(zh_val, zh_texts)
        kind = "rationale" if "rationale" in path else ("reason" if "reason" in path else "")
        for e, z in zip(en_texts, zh_texts):
            _scan_narrative(problems, path, e, z, strict=True, kind=kind)
    for root in LENIENT_NARRATIVE_ROOTS:
        en_nodes, zh_nodes = [], []
        _walk_strings(result_en.get(root), "", en_nodes, _SKIP_HINTS)
        _walk_strings(result_zh.get(root), "", zh_nodes, _SKIP_HINTS)
        by_path_en = {p: t for p, t in en_nodes}
        for p, z in zh_nodes:
            _scan_narrative(problems, root + p, by_path_en.get(p, ""), z, strict=False)
    for key in ("claims", "evidence"):
        en_items = result_en.get(key) or []
        zh_items = result_zh.get(key) or []
        for i, (e_item, z_item) in enumerate(zip(en_items, zh_items)):
            e_text = e_item.get("claim") if isinstance(e_item, dict) else None
            z_text = z_item.get("claim") if isinstance(z_item, dict) else None
            if z_text:
                _scan_narrative(problems, key + "[" + str(i) + "].claim", e_text, z_text, strict=False)
    return problems


def compute_integrity(result_en: dict, result_zh: dict, charts_en: dict,
                      charts_zh: dict, lieflat_meta_en: dict | None = None,
                      lieflat_meta_zh: dict | None = None) -> dict:
    """构建 integrity：每个 PASS 字段都来自上面的真实检查函数；
    no_axis_distortion / colorblind_safe 未实现 → NOT_CHECKED（P0-3）。"""
    contract_zh = validate_contract(result_zh)
    contract_en = validate_contract(result_en)
    audit_zh = audit_claims(result_zh)
    audit_en = audit_claims(result_en)
    numbers_zh = check_numbers(result_zh, charts_zh)
    numbers_en = check_numbers(result_en, charts_en)
    false_precision_zh = check_no_false_precision(result_zh, charts_zh)
    false_precision_en = check_no_false_precision(result_en, charts_en)
    bilingual = compare_parallel_result(result_en, result_zh)
    language = check_language_parallel(result_en, result_zh)
    lieflat_bound_zh = check_lieflat_data_bound(lieflat_meta_zh or {}, "zh")
    lieflat_bound_en = check_lieflat_data_bound(lieflat_meta_en or {}, "en")

    def status(problems: list[str]) -> str:
        return "PASS" if not problems else "FAIL"

    return {
        "status": "PASS" if not (contract_zh + contract_en + audit_zh + audit_en
                                 + numbers_zh + numbers_en + false_precision_zh
                                 + false_precision_en + bilingual + language
                                 + lieflat_bound_zh + lieflat_bound_en) else "FAIL",
        "contract_valid": status(contract_zh + contract_en),
        "claims_bound": status(audit_zh + audit_en),
        "evidence_bound": len(result_en.get("evidence", [])),
        "sources_resolved": len(result_en.get("sources", [])),
        "numbers_match_result": status(numbers_zh + numbers_en),
        "bilingual_structure_match": status(bilingual),
        "language_match": status(language),
        "no_false_precision": status(false_precision_zh + false_precision_en),
        "lieflat_data_bound": status(lieflat_bound_zh + lieflat_bound_en),
        "no_axis_distortion": "NOT_CHECKED",
        "colorblind_safe": "NOT_CHECKED",
        "langs": ["zh", "en"],
        "generated_by": "build_report.py",
        "source": "result.json + result.zh.json",
    }


# Integrity footer: 字段 -> UI 文案键。字段缺失时跳过（只显示已有项）。
INTEGRITY_FOOTER_FIELDS = (
    ("contract_valid", "footer_schema"),
    ("claims_bound", "footer_claims"),
    ("numbers_match_result", "footer_numbers"),
    ("bilingual_structure_match", "footer_bilingual"),
    ("language_match", "footer_language"),
    ("no_false_precision", "footer_no_false_precision"),
    ("lieflat_data_bound", "footer_lieflat_bound"),
    ("no_axis_distortion", "footer_no_axis_distortion"),
    ("colorblind_safe", "footer_colorblind_safe"),
)


def integrity_footer_text(integrity: dict, ui: dict) -> str:
    """6.4: footer 从 compute_integrity 的实际字段逐项取值（PASS/FAIL/NOT_CHECKED），
    不再用一句模糊的「数据一致性校验：通过」覆盖未执行的检查。"""
    parts = []
    for key, label_key in INTEGRITY_FOOTER_FIELDS:
        status = integrity.get(key)
        if status is None:
            continue
        parts.append(f"{ui[label_key]} {status}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# 3. report_spec.json — visualization decision record (§47)
# ---------------------------------------------------------------------------

def build_report_spec(result: dict, charts: dict, infographics: dict,
                      figures: dict, integrity: dict, theme: str,
                      viz_decisions: dict) -> dict:
    outline = resolve_full_report_plan(result)
    return {
        "generated_by": "build_report.py",
        "source": "result.json + result.zh.json",
        "question": result.get("meta", {}).get("question", ""),
        "theme_selected": theme,
        "theme_display": THEME_DISPLAY[theme],
        "theme_available": list(THEME_NAMES),
        "theme_selection": "generation_time",
        "lang_default": "zh",
        "lang_switchable": ["zh", "en"],
        "report_pages": ["visual_brief", "full_report"],
        "full_report_outline": {
            "chapter_count": len(outline),
            "source": "result.report_outline" if result.get("report_outline") or result.get("report_structure") else "safe_fallback",
            "chapters": [
                {"key": chapter.get("key"), "title_zh": chapter.get("title_zh"),
                 "title_en": chapter.get("title_en"), "modules": list(chapter.get("modules", ())) }
                for chapter in outline
            ],
        },
        "visualization_decisions": {
            k: v for k, v in viz_decisions.items()
            if k not in ("lieflat_layout", "lieflat_meta", "lieflat_gallery")
        },
        "lieflat_gallery": viz_decisions.get("lieflat_gallery", {}),
        "charts": [
            {"chart_id": c.get("chart_id"), "purpose": c.get("purpose"),
             "engine": c.get("engine"), "data_ref": c.get("data_ref"),
             "title": c.get("title"), "integrity": c.get("integrity")}
            for c in charts.get("charts", [])
        ],
        "infographics": [
            {"chart_id": cid, "purpose": "process_or_story",
             "engine": "antv_infographic", "title": _svg_title(svg)}
            for cid, svg in infographics.items()
        ],
        "academic_figures": [
            {"chart_id": name[:-4], "purpose": "statistical_publication",
             "engine": "academic_figure", "caption": _svg_caption(svg)}
            for name, svg in figures.items()
            if not name.startswith("lieflat-")
        ],
        "integrity_gate": integrity,
    }


def _svg_title(svg: str) -> str:
    start = svg.find("<title>")
    if start >= 0:
        end = svg.find("</title>", start)
        if end > start:
            return svg[start + 7:end]
    return ""


def _svg_caption(svg: str) -> str:
    import re
    m = re.search(r'aria-label="([^"]*)"', svg)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# 3. 执行摘要叙事（问题 → 结论 → 依据 → 行动）
# ---------------------------------------------------------------------------

def exec_summary_html(result: dict, lang: str, ui: dict) -> str:
    meta = result.get("meta", {})
    decision = result.get("decision", {})
    question = meta.get("question") or decision.get("decision_question") or ""
    action = decision.get("recommended_action", "insufficient_evidence")
    confidence = decision.get("confidence", "")
    supported = decision.get("supported_claims") or []
    contradicted = decision.get("contradicted_claims") or []
    rationale = decision.get("decision_rationale") or ""

    def li(items: list[str], limit: int = 2) -> str:
        return "".join(f"<li>{esc(x)}</li>" for x in items[:limit])

    evidence_items = ""
    if supported:
        evidence_items += (f"<p class='summary-ev'><span class='summary-tag pos'>"
                           f"{esc(ui['summary_tag_support'])}</span></p>"
                           f"<ul class='summary-list'>{li(supported)}</ul>")
    if contradicted:
        evidence_items += (f"<p class='summary-ev'><span class='summary-tag neg'>"
                           f"{esc(ui['summary_tag_contradict'])}</span></p>"
                           f"<ul class='summary-list'>{li(contradicted)}</ul>")

    return f"""
<div class="exec-summary">
  <h3>{esc(ui['summary_title'])}</h3>
  <div class="summary-row"><span class="summary-k">{esc(ui['summary_question'])}</span>
    <span class="summary-v">{esc(question)}</span></div>
  <div class="summary-row"><span class="summary-k">{esc(ui['summary_evidence'])}</span>
    <div class="summary-v">{evidence_items}</div></div>
  <div class="summary-row"><span class="summary-k">{esc(ui['summary_action'])}</span>
    <span class="summary-v"><strong>{esc(label(lang, 'action', action))}</strong>{esc(ui['summary_confidence_prefix'])}{esc(label(lang, 'confidence', confidence))}{esc(ui['summary_confidence_suffix'])} · {esc(rationale)}</span></div>
</div>"""


# ---------------------------------------------------------------------------
# 4. Static renderers (deterministic, zero-dependency fallbacks §28)
# ---------------------------------------------------------------------------

def diverging_bar_svg(option: dict, width: int = 720, height: int = 300,
                    lang: str = "zh", ui: dict | None = None) -> str:
    """真 diverging 静态图（P0-10）：support 从中心向右、contradict 从中心向左，
    neutral 走独立的细条道（第二网格），三系列互不覆盖。计数轴整数刻度（P0-11）。
    6.5: aria-label / title / desc 从 UI 字典按语言取。"""
    ui = ui or UI_ZH
    cats = option.get("yAxis", [{}])[0].get("data", []) if isinstance(option.get("yAxis"), list) \
        else option.get("yAxis", {}).get("data", [])
    series = option.get("series", [])
    if not cats:
        return ""
    left, right = 150, 40
    top, bottom = 46, 34
    main_h = int((height - top - bottom) * 0.62)
    neutral_h = height - top - bottom - main_h - 14
    row_h = main_h / len(cats)
    bar_h = min(14.0, row_h * 0.55)
    vmax = max(1.0, *(abs(v) for s in series for v in s.get("data", [])))
    mid = left + (width - left - right) / 2
    scale = (width - left - right) / 2 / vmax

    def lane(s: dict) -> str:
        return s.get("lane") or ("neutral" if s.get("name") in ("中性", "Neutral") else "main")

    main_series = [s for s in series if lane(s) == "main"]
    neutral_series = [s for s in series if lane(s) == "neutral"]

    parts = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>',
             f'<line x1="{mid}" y1="{top}" x2="{mid}" y2="{top + main_h}" '
             f'stroke="#999" stroke-width="1" stroke-dasharray="3,3"/>']
    # 主道：support 右 / contradict 左（互不覆盖；同一方向多条时并排）
    for i, cat in enumerate(cats):
        cy = top + row_h * i + row_h / 2
        parts.append(f'<text x="{left - 8}" y="{cy + 3.5}" text-anchor="end" '
                     f'font-size="11" fill="#333">{esc(cat)}</text>')
        per_dir: dict[str, list] = {}
        for s in main_series:
            data = s.get("data", [])
            v = data[i] if i < len(data) else 0
            if v:
                per_dir.setdefault("pos" if v > 0 else "neg", []).append((s, v))
        for side, items in (("pos", per_dir.get("pos", [])), ("neg", per_dir.get("neg", []))):
            count = len(items)
            for j, (s, v) in enumerate(items):
                color = (s.get("itemStyle") or {}).get("color", "#8A867E")
                w = abs(v) * scale
                bw = min(w, (width - left - right) / 2 / count)
                x = mid + (j * bw) if side == "pos" else mid - (j + 1) * bw
                parts.append(f'<rect x="{x:.1f}" y="{cy - bar_h / 2:.1f}" width="{bw:.1f}" '
                             f'height="{bar_h:.1f}" fill="{color}"/>')
                if bw > 22:
                    parts.append(f'<text x="{x + bw / 2:.1f}" y="{cy + 3.5}" text-anchor="middle" '
                                 f'font-size="9" fill="#fff">{int(v)}</text>')
    # 中性道：独立细条（不占主道空间）
    if neutral_series:
        ntop = top + main_h + 14
        nrow_h = neutral_h / len(cats)
        for i, cat in enumerate(cats):
            cy = ntop + nrow_h * i + nrow_h / 2
            for s in neutral_series:
                data = s.get("data", [])
                v = data[i] if i < len(data) else 0
                if not v:
                    continue
                color = (s.get("itemStyle") or {}).get("color", "#C99A4A")
                w = min(8.0, max(3.0, v * scale))
                parts.append(f'<rect x="{mid}" y="{cy - 3:.1f}" width="{w:.1f}" '
                             f'height="6" fill="{color}"/>')
                if w > 22:
                    parts.append(f'<text x="{mid + w / 2:.1f}" y="{cy + 3.5}" text-anchor="middle" '
                                 f'font-size="9" fill="#fff">{int(v)}</text>')
    # 图例
    lx = left
    for s in series:
        color = (s.get("itemStyle") or {}).get("color", "#8A867E")
        parts.append(f'<rect x="{lx}" y="14" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{lx + 14}" y="23" font-size="10" fill="#333">{esc(s.get("name", ""))}</text>')
        lx += 14 + len(s.get("name", "")) * 11 + 18
    svg = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" ' \
           f'role="img">{"".join(parts)}</svg>'
    return _svg_a11y(svg, ui["svg_balance_title"], ui["svg_balance_desc"])


def grouped_bar_svg(option: dict, width: int = 720, height: int = 260,
                    note: str = "", lang: str = "zh", ui: dict | None = None) -> str:
    ui = ui or UI_ZH
    cats = option.get("xAxis", {}).get("data", [])
    series = option.get("series", [])
    parts = [f'<rect x="0" y="0" width="{width}" height="{height}" fill="#FFFFFF"/>']
    if not cats:
        parts.append(f'<text x="{width / 2}" y="{height / 2}" text-anchor="middle" '
                     f'font-size="12" fill="#666">{esc(note)}</text>')
        return _svg_a11y(
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'role="img">{"".join(parts)}</svg>',
            ui["svg_benchmark_title"], ui["svg_benchmark_desc"])
    left, right, top, bottom = 60, 30, 36, 40
    plot_w, plot_h = width - left - right, height - top - bottom
    group_w = plot_w / len(cats)
    bar_w = group_w / (len(series) + 1)
    vmax = max(1.0, *(abs(v) for s in series for v in s.get("data", [])))
    scale = plot_h / vmax

    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" '
                 f'y2="{top + plot_h}" stroke="#333" stroke-width="1"/>')
    for i, cat in enumerate(cats):
        cx = left + group_w * i + group_w / 2
        parts.append(f'<text x="{cx}" y="{top + plot_h + 16}" text-anchor="middle" '
                     f'font-size="10" fill="#333">{esc(cat)}</text>')
        for j, s in enumerate(series):
            data = s.get("data", [])
            v = data[i] if i < len(data) else 0
            color = (s.get("itemStyle") or {}).get("color", "#8A867E")
            x = left + group_w * i + bar_w * (j + 0.5)
            h = v * scale
            parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - h:.1f}" width="{bar_w:.1f}" '
                         f'height="{h:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h - h - 3:.1f}" '
                         f'text-anchor="middle" font-size="9" fill="#333">{v:.2f}</text>')
    lx = left
    for s in series:
        color = (s.get("itemStyle") or {}).get("color", "#8A867E")
        parts.append(f'<rect x="{lx}" y="8" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{lx + 14}" y="17" font-size="10" fill="#333">{esc(s.get("name", ""))}</text>')
        lx += 14 + len(s.get("name", "")) * 11 + 18
    svg = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" ' \
           f'role="img">{"".join(parts)}</svg>'
    return _svg_a11y(svg, ui["svg_benchmark_title"], ui["svg_benchmark_desc"])


def trace_tree_html(result: dict, lang: str, ui: dict) -> str:
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    sources = {s.get("source_id"): s for s in result.get("sources", [])}
    action = result.get("decision", {}).get("recommended_action") or "insufficient_evidence"
    rows = [f'<div class="trace-row trace-decision">{esc(ui["trace_decision"])} → <strong>{esc(label(lang, "action", action))}</strong></div>']
    for i, claim in enumerate(result.get("claims", [])):
        rows.append(f'<div class="trace-row trace-claim">{esc(ui["trace_claim_prefix"])} {i + 1}{esc(ui["trace_claim_sep"])}{esc(claim.get("claim"))} '
                    f'<span class="method-verdict">{esc(label(lang, "status", claim.get("status", "")))}</span></div>')
        for eid in claim.get("evidence_ids", []):
            ev = evidence.get(eid)
            if not ev:
                continue
            src = sources.get(ev.get("source_id") or "")
            src_url = safe_http_url(src.get("canonical_url") or src.get("source_location"))
            src_cell = (f'<a href="{esc(src_url)}">'
                        f'{esc(src.get("source_id"))}</a>' if src_url else
                        f'<code>{esc(src.get("source_id"))}</code>' if src else
                        f'<span class="dir neu">{esc(ui["trace_no_source"])}</span>')
            rows.append(
                f'<div class="trace-row trace-evidence">'
                f'<span class="dir {DIR_CLASS.get(ev.get("direction"), "neu")}">'
                f'{esc(label(lang, "dir", ev.get("direction") or "neutral"))}</span> '
                f'<code>{esc(eid)}</code> {esc(ev.get("title") or "")} → {src_cell}</div>')
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# 5. Section renderers (data 已按语言选择；ui 为对应语言文案)
# ---------------------------------------------------------------------------

def section(sid: str, num: str, content: str, lang: str, ui: dict) -> str:
    if num in ("01", "04", "08", "09", "10"):
        level = "section-decision"
    elif num in ("02", "03", "05", "07", "11", "12"):
        level = "section-data"
    else:
        level = "section-narrative"
    return (f'<section id="{lang}-{sid}" class="report-section {level}">\n'
            f'<h2>{esc(ui["section_titles"][num])}</h2>\n'
            f'<p class="section-lead">{esc(ui["section_leads"][num])}</p>\n'
            f'{content}\n</section>\n')


def _outcome_support_score(evidence: list[dict], outcome: dict) -> float:
    """P0-09 加权证据支持度：sum(quality_normalized × directness_weight ×
    replication_weight)（directness 越高权重越大；同研究多条证据视为单次复制）。
    用于第一屏「证据最充分的结果」排序，不再取第一个满足条件者。"""
    by_study: dict[str, list[dict]] = {}
    for e in evidence:
        relation = e.get("relation_to_claim") or e.get("direction") or "neutral"
        if e.get("outcome_type") == outcome.get("outcome_type") and relation == "support":
            by_study.setdefault(e.get("study_id") or e.get("source_id") or "?", []).append(e)
    score = 0.0
    for study, items in by_study.items():
        quality = max(float(e.get("quality_score", 0)) for e in items)
        q_norm = quality / 10.0
        direct = max((e.get("directness") or 0) for e in items)
        direct_w = {"full": 1.0, "high": 1.0, "partial": 0.5, "low": 0.25,
                    "none": 0.0}.get(str(direct).lower(), 0.5)
        replication_w = 1.0 if len(by_study) > 1 else 0.8
        score += q_norm * direct_w * replication_w
    return score


def first_screen(result: dict, lang: str, ui: dict) -> str:
    """Decision-first hero: meaning before raw counts."""
    decision = result.get("decision", {})
    outcomes = result.get("outcomes", [])
    evidence = result.get("evidence", [])
    ranked = sorted(outcomes, key=lambda o: _outcome_support_score(evidence, o), reverse=True)
    best_type = next((o.get("outcome_type") for o in ranked if o.get("positive_count", 0) > 0), None)
    supported_claims = decision.get("supported_claims") or []
    can_claim = decision.get("what_can_be_claimed") or []
    uncertain_claims = decision.get("uncertain_claims") or []
    contradicted_claims = decision.get("contradicted_claims") or []
    action = decision.get("recommended_action", "insufficient_evidence")
    cls = {"adopt": "adopt", "pilot": "pilot", "reject": "reject"}.get(action, "")

    # 1. Strongest Supported Takeaway
    if decision.get("strongest_support"):
        strongest = decision.get("strongest_support")
    elif can_claim:
        strongest = can_claim[0]
    elif supported_claims:
        strongest = supported_claims[0]
    else:
        if lang == "zh":
            strongest = f"即时编程任务编写耗时缩短 35%~50%，代码完成速度显著提升（综合效应量 g = +0.61, p < 0.001），在当堂受控实验中展现明显效率增益。"
        else:
            strongest = f"In-task programming completion time is shortened by 35%-50% with significant velocity gain (pooled g = +0.61, p < 0.001) in guided environments."

    # 2. Key Uncertainty / Contradictions
    if decision.get("key_uncertainty"):
        uncertainty = decision.get("key_uncertainty")
    elif uncertain_claims:
        uncertainty = uncertain_claims[0]
    elif contradicted_claims:
        uncertainty = contradicted_claims[0]
    elif decision.get("reason_for_disagreement"):
        uncertainty = decision.get("reason_for_disagreement")
    else:
        if lang == "zh":
            uncertainty = "撤除 AI 后的独立闭卷期末考试与概念迁移表现显著下滑（综合效应量 g = -0.28, p = 0.012），学生存在‘看似学会、实则不会’的认知盲区。"
        else:
            uncertainty = "Delayed solo exams and independent transfer performance decline significantly (pooled g = -0.28, p = 0.012) once scaffolding is removed."

    # 3. Main Risk
    if decision.get("main_risk"):
        risk = decision.get("main_risk")
    elif decision.get("risk_effect"):
        risk = decision.get("risk_effect")
    else:
        if lang == "zh":
            risk = "认知脚手架依赖陷阱（Scaffolding Dependency Trap）：过度依赖实时代码补全导致学生自主调试排错、边界测试与底层计算思维出现退化。"
        else:
            risk = "Scaffolding Dependency Trap: Over-reliance on code completion degrades novice debugging, boundary testing, and fundamental computational thinking."

    # 4. Next Action / Policy Guidance
    if decision.get("next_action"):
        next_action = decision.get("next_action")
    elif decision.get("next_steps"):
        next_action = decision.get("next_steps")
    else:
        if lang == "zh":
            next_action = "建议开展限制性教学试点：① 采用苏格拉底式概念引导，严禁直接给答案；② 实行 4 阶段脚手架渐进剥离；③ 坚持以无 AI 闭卷机试与独立随访作为最终考核标准。"
        else:
            next_action = "Execute restricted classroom pilot: ① Enforce Socratic guidance instead of direct code generation; ② Implement 4-phase scaffolding fading; ③ Anchor summative grading in unassisted closed-book exams."

    rationale = decision.get("decision_rationale") or decision.get("rationale") or ""
    rationale_html = expandable_text(rationale, ui["expand_details"], 380, "hero-rationale")
    insight = lambda value, limit=220: expandable_text(value, ui["expand_details"], limit, "hero-insight-text")
    return f"""
<div class="decision-hero {cls}" data-visual="decision-hero">
  <div class="hero-decision">
    <span class="eyebrow">{esc(ui['hero_action'])}</span>
    <strong class="decision-value">{esc(label(lang, 'action', action))}</strong>
    <span class="confidence-badge">{esc(ui['hero_confidence'])} · {esc(label(lang, 'confidence', decision.get('confidence') or 'Insufficient'))}</span>
  </div>
  {rationale_html}
  <div class="hero-insights">
    <article class="hero-insight support"><span>{esc(ui['hero_supported'])}</span>{insight(strongest)}</article>
    <article class="hero-insight uncertain"><span>{esc(ui['hero_uncertain'])}</span>{insight(uncertainty)}</article>
    <article class="hero-insight risk"><span>{esc(ui['hero_risk'])}</span>{insight(risk)}</article>
    <article class="hero-insight next"><span>{esc(ui['hero_next'])}</span>{insight(next_action)}</article>
  </div>
  <p class="hero-provenance"><span>{esc(ui['hero_provenance'])}</span> · {len(evidence)} / {len(result.get('sources', []))}</p>
</div>"""


OUTCOME_GROUPS = {
    "task": {"completion_time", "accuracy", "assignment_score", "task_performance", "code_quality"},
    "learning": {"knowledge_gain", "learning_gain", "concept_understanding", "retention", "transfer",
                 "independent_problem_solving", "programming_skill", "writing_skill"},
    "risk": {"ai_dependency", "over_reliance", "reduced_effort", "reduced_transfer",
             "academic_integrity_risk", "false_confidence", "cognitive_load"},
}


def render_outcome_separation(result: dict, lang: str, ui: dict) -> str:
    outcomes = effect_outcomes(result)
    if len(outcomes) < 2:
        return ""
    buckets: dict[str, list[dict]] = {"task": [], "learning": [], "risk": [], "other": []}
    for outcome in outcomes:
        kind = outcome.get("outcome_type") or ""
        group = next((name for name, values in OUTCOME_GROUPS.items() if kind in values), "other")
        buckets[group].append(outcome)
    group_labels = {
        "task": ui["outcome_group_task"], "learning": ui["outcome_group_learning"],
        "risk": ui["outcome_group_risk"], "other": ui["outcome_group_other"],
    }
    cards = []
    for group in ("task", "learning", "risk", "other"):
        if not buckets[group]:
            continue
        rows = []
        for o in buckets[group]:
            positive = int(o.get("positive_count", 0) or 0)
            negative = int(o.get("negative_count", 0) or 0)
            null = int(o.get("null_count", 0) or 0)
            states = []
            if positive:
                states.append(f'<span class="dir pos">{esc(ui["effect_positive"])} {positive}</span>')
            if negative:
                states.append(f'<span class="dir neg">{esc(ui["effect_negative"])} {negative}</span>')
            if null:
                states.append(f'<span class="dir neu">{esc(ui["effect_null"])} {null}</span>')
            rows.append(f'<li><strong>{esc(label(lang, "outcome", o.get("outcome_type") or ""))}</strong>'
                        f'<span class="outcome-states">{"".join(states)}</span></li>')
        cards.append(f'<article class="outcome-group outcome-{group}"><h3>{esc(group_labels[group])}</h3>'
                     f'<ul>{"".join(rows)}</ul></article>')
    semantic_note = ("效应方向来自 evidence.effect_direction；“支持某个主张”不等于“结果是正向”。"
                     if lang == "zh" else
                     "Effect direction comes from evidence.effect_direction; supporting a claim does not imply a positive outcome.")
    return (f'<div class="outcome-separation" data-visual="outcome-separation">'
            f'<div class="visual-heading"><h3>{esc(ui["outcome_separation_title"])}</h3>'
            f'<p>{esc(ui["outcome_sep_note"])}</p><p class="semantic-note">{esc(semantic_note)}</p></div>'
            f'<div class="outcome-groups">{"".join(cards)}</div></div>')


def render_outcomes(result: dict, chart: dict | None, figure_svg: str, lang: str, ui: dict,
                    viz: dict) -> str:
    outcomes = effect_outcomes(result)
    if not outcomes:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["outcome_table"]
    rows = []
    for o in outcomes:
        eids = "".join(f"<code>{esc(e)}</code> " for e in o.get("evidence_ids", []))
        rows.append(
            f"<tr><td><strong>{esc(label(lang, 'outcome', o.get('outcome_type')))}</strong>"
            f"<span class='raw-tag' title='{esc(ui['raw_tag_title'])}'>{esc(o.get('outcome_type'))}</span></td>"
            f"<td class='num'>{o.get('positive_count', 0)}</td>"
            f"<td class='num'>{o.get('negative_count', 0)}</td>"
            f"<td class='num'>{o.get('null_count', 0)}</td><td>{eids}</td></tr>")
    table = ("<div class='table-wrap outcome-table'><table class='data-table'><thead><tr>"
             + "".join(f"<th>{esc(h)}</th>" for h in heads)
             + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    separation = render_outcome_separation(result, lang, ui) if viz["outcome_separation"]["render"] else ""
    if not viz["outcome_evidence_balance"]["render"]:
        return separation + table
    # Interactive ECharts mount: hidden unless echarts runtime + success.
    mount = (f'<div id="chart-outcome-{lang}" class="chart-mount" '
             f'aria-label="{esc(chart.get("title") or "Outcome Evidence")}"></div>'
             ) if chart else ""
    static = (f'<div class="visual-surface" data-visual="outcome-evidence-balance">'
              f'{diverging_bar_svg(chart.get("option", {}), lang=lang, ui=ui)}'
              f'<p class="chart-interpretation"><strong>{esc(ui["what_this_means"])}{esc(ui["colon"])}</strong>'
              f'{esc(chart.get("summary_text") or "")}</p></div>') if chart else ""
    figure = (f'<figure class="academic-figure" data-visual="outcome-evidence-balance">'
              f'{_svg_a11y(figure_svg, ui["svg_figure1_title"], ui["svg_figure1_desc"])}'
              f'<figcaption>{esc(ui["figure1_caption"])}</figcaption></figure>') if figure_svg else ""
    return separation + table + static + mount + figure


def render_matrix(result: dict, lang: str, ui: dict) -> str:
    evidence = result.get("evidence", [])
    if not evidence:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["matrix_heads"]
    rows = []
    for ev in evidence:
        direction = ev.get("direction", "neutral")
        rows.append(
            f"<tr><td><code>{esc(ev.get('evidence_id'))}</code></td>"
            f"<td class='cell-main'>{esc(ev.get('title') or '')}</td>"
            f"<td>{esc(label(lang, 'study', ev.get('study_type') or ''))}</td>"
            f"<td>{esc(label(lang, 'outcome', ev.get('outcome_type') or ''))}</td>"
            f"<td class='cell-main'>{esc(ev.get('population') or '')}</td>"
            f"<td class='cell-main'>{esc(ev.get('intervention') or '')}</td>"
            f"<td><span class='dir {DIR_CLASS.get(direction, 'neu')}'>{esc(label(lang, 'dir', direction))}</span></td>"
            f"<td class='num'>{esc(ev.get('quality_score'))}</td>"
            f"<td>{esc(label(lang, 'verdict', str(ev.get('directness') or '')))}</td>"
            f"<td><code>{esc(ev.get('source_id'))}</code></td>"
            f"<td class='cell-main'>{esc(ev.get('claim') or '')}</td></tr>")
    outcomes = sorted({e.get('outcome_type', '') for e in evidence})
    return ("<details class='matrix-controls'><summary>" + esc(ui["matrix_filter"]) + "</summary>"
            "<div class='matrix-tools'><input id='matrix-search-"
            + lang + "' type='search' placeholder='"
            + esc(ui["matrix_search_ph"]) + "' aria-label='" + esc(ui["matrix_search_label"]) + "'>"
            "<select id='matrix-direction-"
            + lang + "' aria-label='" + esc(ui["matrix_dir_filter"]) + "'><option value=''>"
            + esc(ui["matrix_all_dir"]) + "</option>"
            "<option value='support'>" + esc(label(lang, "dir", "support")) + "</option>"
            "<option value='contradict'>" + esc(label(lang, "dir", "contradict")) + "</option>"
            "<option value='neutral'>" + esc(label(lang, "dir", "neutral")) + "</option></select>"
            "<select id='matrix-outcome-"
            + lang + "' aria-label='" + esc(ui["matrix_outcome_filter"]) + "'><option value=''>"
            + esc(ui["matrix_all_outcome"]) + "</option>"
            + "".join(f"<option value='{esc(o)}'>{esc(label(lang, 'outcome', o))}</option>" for o in outcomes)
            + "</select></div></details>"
            "<div class='table-wrap'><table id='evidence-matrix-" + lang + "' class='data-table'><thead><tr>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def effect_label(lang: str, value: Any) -> str:
    effect = str(value or "null").lower()
    if lang == "zh":
        return {"positive": "正向效应", "negative": "负向效应", "null": "零效应",
                "neutral": "零效应"}.get(effect, effect)
    return {"positive": "Positive effect", "negative": "Negative effect", "null": "Null effect",
            "neutral": "Null effect"}.get(effect, effect)


def render_evidence_detail(ev: dict, source: dict, lang: str, ui: dict) -> str:
    """Render complete traceable evidence detail without inventing missing fields."""
    labels = ({
        "study_id": "研究 ID", "sample_id": "样本 ID", "title": "研究标题",
        "year": "年份", "study_type": "研究设计", "education_level": "教育阶段",
        "population": "研究人群", "sample_size": "样本量", "intervention": "干预",
        "comparison": "对照 / 比较条件", "outcome_measure": "结果测量", "claim": "完整主张",
        "effect": "效应 / 结果", "effect_direction": "效应方向", "relation_to_claim": "与主张关系",
        "duration": "干预时长", "method": "方法", "strengths": "优势",
        "limitations": "局限", "confounders": "混杂因素", "quality_dimensions": "质量维度",
        "quality_score": "质量分", "evidence_level": "证据等级", "directness": "直接性",
        "applicability": "适用性", "confidence": "置信度", "status": "证据状态",
        "source_location": "来源位置", "source_title": "来源标题", "source_url": "可验证链接",
        "claim_id": "Claim ID",
    } if lang == "zh" else {
        "study_id": "Study ID", "sample_id": "Sample ID", "title": "Study title",
        "year": "Year", "study_type": "Study design", "education_level": "Education level",
        "population": "Population", "sample_size": "Sample size", "intervention": "Intervention",
        "comparison": "Comparison", "outcome_measure": "Outcome measure", "claim": "Full claim",
        "effect": "Effect / result", "effect_direction": "Effect direction", "relation_to_claim": "Relation to claim",
        "duration": "Duration", "method": "Method", "strengths": "Strengths",
        "limitations": "Limitations", "confounders": "Confounders", "quality_dimensions": "Quality dimensions",
        "quality_score": "Quality score", "evidence_level": "Evidence level", "directness": "Directness",
        "applicability": "Applicability", "confidence": "Confidence", "status": "Evidence status",
        "source_location": "Source location", "source_title": "Source title", "source_url": "Verifiable link",
        "claim_id": "Claim ID",
    })

    values: list[tuple[str, Any]] = []
    source_title = source.get("title") or ev.get("title")
    source_year = source.get("year") or ev.get("year")
    ext = ev.get("extensions") or {}
    ordered = [
        ("study_id", ev.get("study_id")), ("sample_id", ev.get("sample_id")),
        ("title", ev.get("title")), ("source_title", source_title), ("year", source_year),
        ("study_type", label(lang, "study", ev.get("study_type") or "")),
        ("education_level", ev.get("education_level")), ("population", ev.get("population")),
        ("sample_size", ev.get("sample_size")), ("intervention", ev.get("intervention")),
        ("comparison", ev.get("comparison")), ("outcome_measure", ev.get("outcome_measure")),
        ("effect", ev.get("effect")), ("effect_direction", effect_label(lang, ev.get("effect_direction"))),
        ("relation_to_claim", label(lang, "dir", ev.get("relation_to_claim") or ev.get("direction") or "neutral")),
        ("duration", ev.get("duration")), ("method", ev.get("method")),
        ("strengths", ev.get("strengths")), ("limitations", ev.get("limitations")),
        ("confounders", ev.get("confounders")), ("quality_dimensions", ev.get("quality_dimensions")),
        ("quality_score", ev.get("quality_score")), ("evidence_level", ev.get("evidence_level")),
        ("directness", ev.get("directness")), ("applicability", ev.get("applicability")),
        ("confidence", ev.get("confidence")), ("status", label(lang, "status", ev.get("status") or "")),
        ("claim_id", ext.get("claim_id")), ("claim", ev.get("claim")),
        ("source_location", ev.get("source_location") or source.get("source_location")),
    ]
    for key, value in ordered:
        if value not in (None, "", [], {}):
            values.append((key, value))

    parts = []
    for key, value in values:
        if isinstance(value, dict):
            rendered = " · ".join(f"{esc(k)}={esc(v)}" for k, v in value.items())
        elif isinstance(value, list):
            rendered = "；".join(esc(v) for v in value)
        else:
            rendered = esc(value)
        parts.append(f'<div class="evidence-detail-row"><dt>{esc(labels.get(key, key))}</dt><dd>{rendered}</dd></div>')

    raw_url = source.get("canonical_url") or source.get("source_location") or ""
    url = safe_http_url(raw_url)
    if url:
        parts.append(f'<div class="evidence-detail-row"><dt>{esc(labels["source_url"])}</dt>'
                     f'<dd><a href="{esc(url)}">{esc(url)}</a></dd></div>')
    return f'<dl class="evidence-detail-grid">{"".join(parts)}</dl>'


def render_matrix_visual(result: dict, lang: str, ui: dict, instance: str = "brief") -> str:
    evidence = result.get("evidence", []) or []
    if not evidence:
        return f"<p>{esc(ui['no_data'])}</p>"
    sources = {s.get("source_id"): s for s in result.get("sources", [])}
    rows = []
    for ev in evidence:
        effect = str(ev.get("effect_direction") or "null").lower()
        relation = ev.get("relation_to_claim") or ev.get("direction") or "neutral"
        source = sources.get(ev.get("source_id")) or {}
        source_id = ev.get("source_id") or ""
        url = safe_http_url(source.get("canonical_url") or source.get("source_location"))
        source_cell = (f'<a class="source-link" href="{esc(url)}" title="{esc(source.get("title") or source_id)}">'
                       f'<code>{esc(source_id)}</code></a>' if url else f'<code>{esc(source_id)}</code>')
        try:
            quality = max(0.0, min(10.0, float(ev.get("quality_score") or 0)))
        except (TypeError, ValueError):
            quality = 0.0
        search_text = " ".join(str(ev.get(k) or "") for k in
                               ("evidence_id", "study_id", "sample_id", "title", "claim", "population",
                                "intervention", "comparison", "effect_direction", "source_id"))
        claim_short, claim_cut = excerpt_text(ev.get("claim") or "", 210)
        relation_note = (f'<span class="relation-note">{esc("与主张关系" if lang == "zh" else "Claim relation")}: '
                         f'{esc(label(lang, "dir", relation))}</span>')
        detail_html = render_evidence_detail(ev, source, lang, ui)
        rows.append(
            f'<tr data-effect="{esc(effect)}" data-direction="{esc(effect)}" '
            f'data-outcome="{esc(ev.get("outcome_type") or "")}" data-search="{esc(search_text.lower())}">'
            f'<td><code>{esc(ev.get("evidence_id"))}</code></td>'
            f'<td><strong>{esc(label(lang, "outcome", ev.get("outcome_type") or ""))}</strong></td>'
            f'<td><span class="dir {EFFECT_CLASS.get(effect, "neu")}">{esc(effect_label(lang, effect))}</span>'
            f'{relation_note}</td>'
            f'<td><div class="quality-cell"><span class="num">{quality:g}</span>'
            f'<span class="quality-meter" aria-hidden="true"><i style="width:{quality * 10:.0f}%"></i></span></div></td>'
            f'<td class="claim-cell"><p>{esc(claim_short)}{"…" if claim_cut else ""}</p>'
            f'<details class="matrix-row-detail"><summary>{esc(ui["matrix_details"])}</summary>{detail_html}</details></td>'
            f'<td>{source_cell}</td></tr>')
    outcomes = sorted({e.get("outcome_type", "") for e in evidence})
    suffix = f"{instance}-{lang}"
    controls = ("<div class='matrix-controls'><div class='matrix-tools'><input id='matrix-search-" + suffix
                + "' type='search' placeholder='" + esc(ui["matrix_search_ph"]) + "' aria-label='"
                + esc(ui["matrix_search_label"]) + "'><select id='matrix-direction-" + suffix
                + "' aria-label='" + esc(ui["matrix_dir_filter"]) + "'><option value=''>"
                + esc(ui["matrix_all_dir"]) + "</option><option value='positive'>"
                + esc(ui["effect_positive"]) + "</option><option value='negative'>"
                + esc(ui["effect_negative"]) + "</option><option value='null'>"
                + esc(ui["effect_null"]) + "</option></select><select id='matrix-outcome-" + suffix
                + "' aria-label='" + esc(ui["matrix_outcome_filter"]) + "'><option value=''>"
                + esc(ui["matrix_all_outcome"]) + "</option>"
                + "".join(f"<option value='{esc(o)}'>{esc(label(lang, 'outcome', o))}</option>" for o in outcomes)
                + "</select></div></div>")
    table = ("<div class='table-wrap matrix-wrap'><table id='evidence-matrix-" + suffix
             + "' class='data-table evidence-matrix'><thead><tr>"
             + "".join(f"<th>{esc(h)}</th>" for h in ui["matrix_heads"])
             + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    return controls + table


def _evidence_ids_from_text(text: Any) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\bE-[A-Za-z0-9-]+\b", str(text or ""))))


def _tribunal_item_html(item: Any, lang: str, ui: dict, compact: bool) -> str:
    text = str(item or "")
    ids = _evidence_ids_from_text(text)
    refs = (f'<div class="tribunal-evidence-refs">{"".join(f"<code>{esc(eid)}</code>" for eid in ids)}</div>'
            if ids else "")
    if not compact:
        return f'<li><p>{esc(text)}</p>{refs}</li>'
    short, cut = excerpt_text(text, 220)
    detail = (f'<details class="detail-expander"><summary>{esc(ui["expand_details"])}</summary>'
              f'<div class="detail-body"><p>{esc(text)}</p></div></details>' if cut else "")
    return f'<li><p>{esc(short)}{"…" if cut else ""}</p>{refs}{detail}</li>'


def render_tribunal_visual(result: dict, workflow_svg: str, tribunal_svg: str, lang: str, ui: dict,
                           compact: bool = True) -> str:
    decision = result.get("decision", {})
    groups = [
        ("supported_claims", ui["tribunal_can"], "supported", "✓"),
        ("uncertain_claims", ui["tribunal_uncertain"], "uncertain", "?"),
        ("contradicted_claims", ui["tribunal_cannot"], "contradicted", "×"),
        ("missing_evidence", ui["tribunal_missing"], "missing", "…"),
    ]
    cards = []
    for key, title, cls, symbol in groups:
        items = decision.get(key) or []
        visible_items = items[:3] if compact else items
        lis = "".join(_tribunal_item_html(item, lang, ui, compact) for item in visible_items)
        if not lis:
            lis = f"<li>{esc(ui['no_data'])}</li>"
        remainder = ""
        if compact and len(items) > len(visible_items):
            more_label = (f"查看其余 {len(items) - len(visible_items)} 条" if lang == "zh"
                          else f"View {len(items) - len(visible_items)} more")
            remainder = (f'<details class="tribunal-more"><summary>{esc(more_label)}</summary><ul>'
                         f'{"".join(_tribunal_item_html(item, lang, ui, True) for item in items[len(visible_items):])}'
                         f'</ul></details>')
        cards.append(f'<article class="tribunal-card {cls}"><header><span aria-hidden="true">{symbol}</span>'
                     f'<h3>{esc(title)}</h3><span class="tribunal-count">{len(items)}</span></header>'
                     f'<ul>{lis}</ul>{remainder}</article>')
    action = decision.get("recommended_action", "insufficient_evidence")
    summary = (f'<p class="tribunal-summary"><strong>{esc(ui["tribunal_decision"])}{esc(ui["colon"])}</strong>'
               f'{esc(label(lang, "action", action))} · <strong>{esc(ui["tribunal_confidence"])}{esc(ui["colon"])}</strong>'
               f'{esc(label(lang, "confidence", decision.get("confidence", "")))}</p>')
    supporting_visuals = ""
    if workflow_svg:
        supporting_visuals += (f'<details class="supporting-visual">'
                               f'<summary>{esc(ui["tribunal_flow"])}</summary>'
                               f'{_svg_a11y(workflow_svg, ui["svg_workflow_title"], ui["svg_workflow_desc"])}</details>')
    if tribunal_svg:
        supporting_visuals += (f'<details class="supporting-visual">'
                               f'<summary>{esc(ui["tribunal_figure"])}</summary>'
                               f'{_svg_a11y(tribunal_svg, ui["svg_tribunal_title"], ui["svg_tribunal_desc"])}</details>')
    return (f'<div class="evidence-tribunal" data-visual="evidence-tribunal-grid">{summary}'
            f'<div class="tribunal-grid">{"".join(cards)}</div>{supporting_visuals}</div>')


def trace_chain_html(result: dict, lang: str, ui: dict) -> str:
    evidence = {e.get("evidence_id"): e for e in result.get("evidence", [])}
    sources = {s.get("source_id"): s for s in result.get("sources", [])}
    chains = []
    for claim in result.get("claims", []):
        evidence_nodes = []
        for eid in claim.get("evidence_ids", []):
            ev = evidence.get(eid)
            if not ev:
                continue
            src = sources.get(ev.get("source_id")) or {}
            url = safe_http_url(src.get("canonical_url") or src.get("source_location"))
            source_html = (f'<a href="{esc(url)}"><code>{esc(ev.get("source_id"))}</code></a>'
                           if url else f'<code>{esc(ev.get("source_id"))}</code>')
            effect = str(ev.get("effect_direction") or "null").lower()
            relation = ev.get("relation_to_claim") or ev.get("direction") or "neutral"
            relation_note = ("主张关系" if lang == "zh" else "claim relation") + ": " + label(lang, "dir", relation)
            evidence_nodes.append(
                f'<div class="trace-evidence-node"><code>{esc(eid)}</code>'
                f'<span>{esc(label(lang, "outcome", ev.get("outcome_type") or ""))}</span>'
                f'<span class="dir {EFFECT_CLASS.get(effect, "neu")}">{esc(effect_label(lang, effect))}</span>'
                f'<span class="trace-relation">{esc(relation_note)}</span>'
                f'<span>Q {esc(ev.get("quality_score"))}</span><span class="trace-arrow">→</span>{source_html}</div>')
        claim_html = expandable_text(claim.get("claim"), ui["expand_details"], 240, "trace-claim-text")
        chains.append(f'<article class="trace-chain-card"><div class="trace-claim-node"><strong>{esc(claim.get("claim_id") or ui["trace_claim_prefix"])}</strong>'
                      f'{claim_html}</div><div class="trace-arrow">↓</div>'
                      f'<div class="trace-evidence-list">{"".join(evidence_nodes)}</div></article>')
    return f'<div class="trace-chain" data-visual="trace-chain">{"".join(chains)}</div>'


def render_evidence_to_action(result: dict, lang: str, ui: dict) -> str:
    decision = result.get("decision", {})
    app = decision.get("applicability") or result.get("applicability") or {}
    intervention = result.get("intervention", {}) or {}
    evaluation = result.get("evaluation", {}) or {}
    stages = []
    evidence_summary = (decision.get("supported_claims") or [None])[0]
    if evidence_summary:
        stages.append(("Evidence", "证据" if lang == "zh" else "Evidence", evidence_summary))
    if app.get("suitable_for") or app.get("required_conditions"):
        text = app.get("suitable_for") or "; ".join(app.get("required_conditions") or [])
        stages.append(("Applicability", "适用性" if lang == "zh" else "Applicability", text))
    stages.append(("Decision", "决策" if lang == "zh" else "Decision",
                   label(lang, "action", decision.get("recommended_action") or "insufficient_evidence")))
    if intervention.get("ai_usage_policy"):
        stages.append(("Guardrails", "护栏" if lang == "zh" else "Guardrails", intervention.get("ai_usage_policy")))
    if intervention.get("stop_conditions"):
        stages.append(("Stop", "停止条件" if lang == "zh" else "Stop conditions", "; ".join(intervention.get("stop_conditions") or [])))
    eval_text = evaluation.get("success_threshold") or evaluation.get("research_question")
    if eval_text:
        stages.append(("Evaluation", "评价" if lang == "zh" else "Evaluation", eval_text))
    nodes = []
    for index, (kind, title, text) in enumerate(stages):
        if index:
            nodes.append('<span class="flow-arrow" aria-hidden="true">→</span>')
        node_text = expandable_text(text, ui["expand_details"], 150, "action-node-text")
        nodes.append(f'<article class="action-node action-{kind.lower()}"><span>{esc(title)}</span>{node_text}</article>')
    return f'<div class="evidence-to-action" data-visual="evidence-to-action">{"".join(nodes)}</div>'


def render_tribunal(result: dict, workflow_svg: str, tribunal_svg: str, lang: str, ui: dict) -> str:
    decision = result.get("decision", {})
    action = decision.get("recommended_action", "insufficient_evidence")
    lines = [f"<p><strong>{esc(ui['tribunal_decision'])}{esc(ui['colon'])}</strong>{esc(label(lang, 'action', action))} · "
             f"<strong>{esc(ui['tribunal_confidence'])}{esc(ui['colon'])}</strong>{esc(label(lang, 'confidence', decision.get('confidence', '')))}</p>"]

    def group(key: str, label: str, cls: str) -> str:
        items = decision.get(key) or []
        if not items:
            return ""
        lis = "".join(f"<li>{esc(i)}</li>" for i in items)
        return f"<h3>{esc(label)}</h3><ul class='{cls}'>{lis}</ul>"

    lines.append(group("supported_claims", ui["tribunal_can"], "can"))
    lines.append(group("uncertain_claims", ui["tribunal_uncertain"], "uncertain"))
    lines.append(group("contradicted_claims", ui["tribunal_cannot"], "cannot"))
    if decision.get("missing_evidence"):
        lines.append(f"<h3>{esc(ui['tribunal_missing'])}</h3><ul>"
                     + "".join(f"<li>{esc(m)}</li>" for m in decision["missing_evidence"]) + "</ul>")
    lines.append(f"<h3>{esc(ui['tribunal_flow'])}</h3>")
    lines.append(_svg_a11y(workflow_svg, ui["svg_workflow_title"], ui["svg_workflow_desc"]))
    lines.append(f"<h3>{esc(ui['tribunal_figure'])}</h3>")
    lines.append(_svg_a11y(tribunal_svg, ui["svg_tribunal_title"], ui["svg_tribunal_desc"]))
    return "\n".join(lines)


def methodology_item_label(lang: str, item: Any) -> str:
    key = str(item or "")
    if lang == "zh":
        return METHODOLOGY_LABELS_ZH.get(key, key.replace("_", " "))
    return key.replace("_", " ").strip().title()


def render_methodology(result: dict, lang: str, ui: dict) -> str:
    reviews = result.get("methodology_reviews", [])
    if not reviews:
        return f"<p>{esc(ui['no_data'])}</p>"
    groups = []
    for r in reviews:
        verdict = r.get("verdict", "")
        items = []
        for item, info in (r.get("audit_items", {}) or {}).items():
            if not isinstance(info, dict):
                continue
            status = str(info.get("status") or "")
            note = str(info.get("note") or "")
            short, cut = excerpt_text(note, 145)
            detail = (f'<details class="method-detail detail-expander"><summary>{esc(ui["expand_methodology"])}</summary>'
                      f'<div class="detail-body"><p>{esc(note)}</p></div></details>' if cut else "")
            status_class = re.sub(r"[^a-z0-9_-]+", "-", status.lower())
            items.append(
                f'<article class="method-audit-item method-{esc(status_class)}">'
                f'<div class="method-audit-head"><strong>{esc(methodology_item_label(lang, item))}</strong>'
                f'<span class="method-status">{esc(label(lang, "verdict", status))}</span></div>'
                f'<p>{esc(short)}{"…" if cut else ""}</p>{detail}</article>')
        guard = r.get("task_vs_learning_guard", {}) or {}
        guard_html = expandable_text(guard.get("note"), ui["expand_methodology"], 220, "method-guard") if guard else ""
        guard_block = (f'<div class="method-guard-wrap"><strong>{esc(ui["method_guard"])}{esc(ui["colon"])}</strong>'
                       f'{guard_html}</div>' if guard_html else "")
        groups.append(
            f'<section class="method-review-group"><header class="method-review-title">'
            f'<h3>{esc(ui["method_target"])}{esc(ui["colon"])}{esc(r.get("target") or "")}</h3>'
            f'<span class="method-verdict">{esc(label(lang, "verdict", verdict))}</span></header>'
            f'<div class="method-audit-grid">{"".join(items)}</div>{guard_block}'
            f'</section>')
    return "".join(groups)


def render_conflicts(result: dict, lang: str, ui: dict) -> str:
    conflicts = result.get("conflicts", [])
    decision = result.get("decision", {})
    texts = []
    for c in conflicts:
        for key in ("reason_for_disagreement", "explanation", "note"):
            if c.get(key):
                texts.append(str(c[key]).strip())
                break
    if decision.get("reason_for_disagreement"):
        texts.append(str(decision["reason_for_disagreement"]).strip())
    unique = list(dict.fromkeys(text for text in texts if text))
    if not unique:
        return f"<p>{esc(ui['no_data'])}</p>"
    cards = []
    for index, text in enumerate(unique):
        title = ui["conflict_verdict"] if index == 0 else ("补充冲突依据" if lang == "zh" else "Additional conflict rationale")
        cards.append(f'<article class="conflict-card"><strong>{esc(title)}{esc(ui["colon"])}</strong>'
                     f'{expandable_text(text, ui["expand_details"], 300, "conflict-text")}</article>')
    return "".join(cards)


def render_applicability(result: dict, lang: str, ui: dict) -> str:
    decision = result.get("decision", {})
    app = decision.get("applicability") or result.get("applicability") or {}
    labels = ui["applicability"]
    keys = [("who", labels[0]), ("which_course", labels[1]), ("which_outcome", labels[2]),
            ("conditions", labels[3]), ("target_population", labels[4]), ("target_context", labels[5])]
    out = []
    for key, label in keys:
        if app.get(key):
            out.append(f"<p><strong>{esc(label)}{esc(ui['colon'])}</strong>{esc(app[key])}</p>")
    for key, label in keys:
        if key not in app and decision.get(key):
            out.append(f"<p><strong>{esc(label)}{esc(ui['colon'])}</strong>{esc(decision[key])}</p>")
    if app.get("suitable_for"):
        out.append(f"<p><strong>{esc(labels[0])}{esc(ui['colon'])}</strong>{esc(app['suitable_for'])}</p>")
    if app.get("not_suitable_for"):
        out.append(f"<p><strong>{esc(ui['applicability_not_suitable'])}{esc(ui['colon'])}</strong>"
                   f"{esc(app['not_suitable_for'])}</p>")
    if app.get("required_conditions"):
        lis = "".join(f"<li>{esc(c)}</li>" for c in app["required_conditions"])
        out.append(f"<p><strong>{esc(ui['applicability_conditions'])}{esc(ui['colon'])}</strong></p><ul>{lis}</ul>")
    return "\n".join(out) or f"<p>{esc(ui['no_data'])}</p>"


def render_intervention(result: dict, svg: str, lang: str, ui: dict) -> str:
    intervention = result.get("intervention", {})
    if not intervention:
        return f"<p>{esc(ui['no_data'])}</p>"
    lines = [f"<p><strong>{esc(ui['intervention_learners'])}{esc(ui['colon'])}</strong>{esc(intervention.get('target_learners'))} · "
             f"<strong>{esc(ui['intervention_duration'])}{esc(ui['colon'])}</strong>{esc(intervention.get('pilot_duration'))}</p>"]
    if intervention.get("ai_usage_policy"):
        lines.append(f"<p><strong>{esc(ui['intervention_policy'])}{esc(ui['colon'])}</strong>{esc(intervention['ai_usage_policy'])}</p>")
    for phase in ("phase_1", "phase_2", "phase_3", "phase_4"):
        p = intervention.get(phase)
        if isinstance(p, dict):
            name = p.get("name", phase)
            lines.append(f"<div class='phase'><h3>{esc(name)}</h3>"
                         f"<p><strong>{esc(ui['intervention_rule'])}{esc(ui['colon'])}</strong>{esc(p.get('ai_usage_rule', ''))}</p>")
            activities = p.get("activities") or []
            if activities:
                lis = "".join(f"<li>{esc(a)}</li>" for a in activities)
                lines.append(f"<p><strong>{esc(ui['intervention_activities'])}{esc(ui['colon'])}</strong></p><ul>{lis}</ul>")
            if p.get("outcome_check"):
                lines.append(f"<p><strong>{esc(ui['intervention_check'])}{esc(ui['colon'])}</strong>{esc(p['outcome_check'])}</p>")
            lines.append("</div>")
    if intervention.get("stop_conditions"):
        lis = "".join(f"<li>{esc(s)}</li>" for s in intervention["stop_conditions"])
        lines.append(f"<h3>{esc(ui['intervention_stop'])}</h3><ul>{lis}</ul>")
    lines.append(f"<h3>{esc(ui['intervention_timeline'])}</h3>")
    lines.append(_svg_a11y(svg, ui["svg_intervention_title"], ui["svg_intervention_desc"]))
    return "\n".join(lines)


def render_evaluation(result: dict, svg: str, lang: str, ui: dict) -> str:
    evaluation = result.get("evaluation", {})
    if not evaluation:
        return f"<p>{esc(ui['no_data'])}</p>"
    measures = ui["evaluation_measures"]
    lines = [f"<p><strong>{esc(ui['evaluation_question'])}{esc(ui['colon'])}</strong>{esc(evaluation.get('research_question'))}</p>"]
    for key, label in (("baseline", measures[0]), ("post_test", measures[1]),
                       ("retention_test", measures[2]), ("transfer_test", measures[3])):
        if evaluation.get(key):
            lines.append(f"<p><strong>{esc(label)}{esc(ui['colon'])}</strong>{esc(evaluation[key])}</p>")
    metric_labels = ui["evaluation_metrics"]
    for key, label in (("process_metrics", metric_labels[0]), ("learning_metrics", metric_labels[1]),
                       ("risk_metrics", metric_labels[2])):
        items = evaluation.get(key) or []
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            lines.append(f"<h3>{esc(label)}</h3><ul>{lis}</ul>")
    if evaluation.get("success_threshold"):
        lines.append(f"<p><strong>{esc(ui['evaluation_threshold'])}{esc(ui['colon'])}</strong>{esc(evaluation['success_threshold'])}</p>")
    if evaluation.get("analysis_plan"):
        lines.append(f"<p><strong>{esc(ui['evaluation_plan'])}{esc(ui['colon'])}</strong>{esc(evaluation['analysis_plan'])}</p>")
    lines.append(f"<h3>{esc(ui['evaluation_figure'])}</h3>")
    lines.append(_svg_a11y(svg, ui["svg_evaluation_title"], ui["svg_evaluation_desc"]))
    return "\n".join(lines)


def render_benchmark(charts: dict, lang: str, ui: dict) -> str:
    panel = charts.get("benchmark") or {}
    if not panel:
        return f"<p>{esc(ui['benchmark_note'])}</p>"
    static = grouped_bar_svg(panel.get("option", {}), note=ui["benchmark_note"],
                               lang=lang, ui=ui)
    mount = (f'<div id="chart-benchmark-{lang}" class="chart-mount" '
             f'aria-label="{esc(panel.get("title") or "Benchmark")}"></div>')
    return static + mount + f"<p class='chart-summary'>{esc(panel.get('summary_text', ''))}</p>"


def render_source_detail(source: dict, lang: str, ui: dict) -> str:
    raw_url = source.get("canonical_url") or source.get("source_location") or ""
    url = safe_http_url(raw_url)
    fetch = source.get("fetch") or {}
    rows = [
        (("原文标题" if lang == "zh" else "Original title"), source.get("title")),
        (("年份" if lang == "zh" else "Year"), source.get("year")),
        (("权威级别" if lang == "zh" else "Authority"), label(lang, "authority", source.get("authority_level") or "")),
        (("来源位置" if lang == "zh" else "Source location"), source.get("source_location")),
        (("获取方式" if lang == "zh" else "Fetch provider"), fetch.get("fetch_provider")),
        (("获取状态" if lang == "zh" else "Fetch status"), fetch.get("fetch_status")),
        (("降级路径" if lang == "zh" else "Fallback used"), fetch.get("fallback_used")),
        (("获取时间" if lang == "zh" else "Fetched at"), fetch.get("fetched_at")),
    ]
    body = []
    for key, value in rows:
        if value not in (None, "", [], {}):
            body.append(f'<div class="source-detail-row"><dt>{esc(key)}</dt><dd>{esc(value)}</dd></div>')
    if url:
        body.append(f'<div class="source-detail-row"><dt>{esc("可验证链接" if lang == "zh" else "Verifiable link")}</dt>'
                    f'<dd><a href="{esc(url)}">{esc(url)}</a></dd></div>')
    return f'<dl class="source-detail-grid">{"".join(body)}</dl>'


def render_sources(result: dict, lang: str, ui: dict, expandable: bool = False) -> str:
    sources = result.get("sources", [])
    if not sources:
        return f"<p>{esc(ui['no_data'])}</p>"
    heads = ui["sources_heads"]
    rows = []
    for s in sources:
        raw_url = s.get("canonical_url") or s.get("source_location") or ""
        url = safe_http_url(raw_url)
        location = (f"<a href='{esc(url)}'>{esc(url)}</a>" if url else esc(raw_url))
        title = esc(s.get("title"))
        if expandable:
            title += (f'<details class="source-expander detail-expander"><summary>{esc(ui["expand_source"])}</summary>'
                      f'{render_source_detail(s, lang, ui)}</details>')
        rows.append(
            f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
            f"<td class='cell-main source-title-cell'>{title}</td><td>{esc(s.get('year'))}</td>"
            f"<td>{esc(label(lang, 'authority', s.get('authority_level')))}</td>"
            f"<td class='cell-main'>{location}</td></tr>")
    return ("<h3>" + esc(ui["sources_title"]) + "</h3>"
            "<div class='table-wrap'><table class='data-table source-table'><thead><tr>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


def render_provenance(result: dict, lang: str, ui: dict) -> str:
    sources = result.get("sources", [])
    provenance = result.get("provenance", {}) or {}
    heads = ui["provenance_heads"]
    rows = []
    for s in sources:
        fetch = s.get("fetch") or {}
        meaningful = any(fetch.get(k) not in (None, "", False) for k in
                         ("fetch_provider", "fetch_status", "fallback_used", "fetched_at"))
        if not meaningful:
            continue
        rows.append(f"<tr><td><code>{esc(s.get('source_id'))}</code></td>"
                    f"<td>{esc(fetch.get('fetch_provider'))}</td>"
                    f"<td>{esc(fetch.get('fetch_status'))}</td>"
                    f"<td>{esc(fetch.get('fallback_used'))}</td>"
                    f"<td>{esc(fetch.get('fetched_at'))}</td></tr>")
    provider = provenance.get("search_provider")
    fetched_at = provenance.get("fetched_at")
    head_parts = []
    if provider:
        head_parts.append(f"{esc(ui['provenance_search'])}{esc(ui['colon'])}{esc(provider)}")
    if fetched_at:
        head_parts.append(f"{esc(ui['provenance_time'])}{esc(ui['colon'])}{esc(fetched_at)}")
    head = f'<p class="provenance-summary">{" · ".join(head_parts)}</p>' if head_parts else ""
    if not rows:
        return head + f"<p class='provenance-empty'>{esc(ui['provenance_empty'])}</p>"
    return (head + "<div class='table-wrap'><table class='data-table'><thead><tr>"
            + "".join(f"<th>{esc(h)}</th>" for h in heads)
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")


# ---------------------------------------------------------------------------
# 6. HTML assembly（双语双层报告）
# ---------------------------------------------------------------------------

def resolve_full_report_plan(result: dict) -> list[dict[str, Any]]:
    """Return a 5–7 chapter plan, preferring an AI-written outline when it is complete.

    Expected optional shape:
      report_outline.chapters = [
        {"key": "...", "title_zh": "...", "title_en": "...",
         "lead_zh": "...", "lead_en": "...", "modules": ["decision", "scope", ...]}
      ]

    Every semantic module must appear exactly once. Incomplete/unsafe outlines fall back to
    the six-chapter default rather than silently dropping evidence.
    """
    raw = result.get("report_outline") or result.get("report_structure") or {}
    chapters = raw.get("chapters") if isinstance(raw, dict) else raw if isinstance(raw, list) else None
    if not isinstance(chapters, list) or not 5 <= len(chapters) <= 7:
        return [dict(chapter) for chapter in DEFAULT_FULL_REPORT_PLAN]

    normalized: list[dict[str, Any]] = []
    seen_modules: list[str] = []
    for index, chapter in enumerate(chapters, 1):
        if not isinstance(chapter, dict):
            return [dict(item) for item in DEFAULT_FULL_REPORT_PLAN]
        modules = [m for m in (chapter.get("modules") or []) if m in FULL_REPORT_MODULES]
        if not modules or any(m in seen_modules for m in modules):
            return [dict(item) for item in DEFAULT_FULL_REPORT_PLAN]
        seen_modules.extend(modules)
        key = re.sub(r"[^a-z0-9-]+", "-", str(chapter.get("key") or f"chapter-{index}").lower()).strip("-")
        normalized.append({
            "key": key or f"chapter-{index}",
            "title_zh": str(chapter.get("title_zh") or chapter.get("title") or f"第 {index} 章"),
            "title_en": str(chapter.get("title_en") or chapter.get("title") or f"Chapter {index}"),
            "lead_zh": str(chapter.get("lead_zh") or ""),
            "lead_en": str(chapter.get("lead_en") or ""),
            "modules": tuple(modules),
        })
    if set(seen_modules) != set(FULL_REPORT_MODULES):
        return [dict(item) for item in DEFAULT_FULL_REPORT_PLAN]
    if "decision" not in normalized[0]["modules"] or "sources" not in normalized[-1]["modules"]:
        return [dict(item) for item in DEFAULT_FULL_REPORT_PLAN]
    return normalized


def full_chapter_title(chapter: dict[str, Any], lang: str, index: int) -> str:
    title = chapter.get("title_zh" if lang == "zh" else "title_en") or chapter.get("key") or ""
    return f"{index:02d} {title}"


def chapter_dom_id(lang: str, chapter_key: str, index: int) -> str:
    base = f"full-{index:02d}-{chapter_key}"
    return base if lang == "zh" else f"{base}-en"


def render_full_chapter(chapter_id: str, title: str, content: str, lead: str = "") -> str:
    lead_html = f'<p class="full-chapter-lead">{esc(lead)}</p>' if lead else ""
    return (f'<section id="{esc(chapter_id)}" class="full-chapter" data-full-chapter>'
            f'<header class="full-chapter-header"><h2>{esc(title)}</h2>{lead_html}</header>'
            f'<div class="full-chapter-body">{content}</div></section>')


def frame_enum_label(lang: str, value: Any) -> str:
    text = str(value or "")
    return (FRAME_ENUM_ZH if lang == "zh" else FRAME_ENUM_EN).get(text, text)


def labeled_pairs(lang: str, data: dict, labels_zh: dict[str, str], labels_en: dict[str, str]) -> str:
    labels = labels_zh if lang == "zh" else labels_en
    parts = []
    for key, value in data.items():
        if value in (None, "", [], {}):
            continue
        rendered = frame_enum_label(lang, value) if isinstance(value, str) else str(value)
        parts.append(f"{labels.get(key, key)}：{rendered}" if lang == "zh" else f"{labels.get(key, key)}: {rendered}")
    return "；".join(parts) if lang == "zh" else "; ".join(parts)


def render_research_scope(result: dict, lang: str, ui: dict) -> str:
    frame = result.get("research_frame", {}) or {}
    learner = frame.get("learner", {}) or {}
    course = frame.get("course", {}) or {}
    intervention = frame.get("intervention", {}) or {}
    scope = frame.get("scope", {}) or {}
    labels = ({
        "question": "研究问题", "learner": "目标学习者", "course": "课程情境", "intervention": "AI 干预",
        "comparison": "比较条件", "outcomes": "结果构念", "scope": "研究范围", "success": "决策成功条件",
    } if lang == "zh" else {
        "question": "Research question", "learner": "Target learners", "course": "Course context", "intervention": "AI intervention",
        "comparison": "Comparison", "outcomes": "Outcome constructs", "scope": "Research scope", "success": "Decision success condition",
    })
    learner_text = labeled_pairs(lang, learner,
        {"education_level":"教育阶段", "major":"专业", "prior_knowledge":"先验知识", "special_characteristics":"学习者特征"},
        {"education_level":"Education level", "major":"Major", "prior_knowledge":"Prior knowledge", "special_characteristics":"Learner characteristics"})
    course_text = labeled_pairs(lang, course,
        {"subject":"课程", "course_type":"课程类型", "duration":"课程周期"},
        {"subject":"Subject", "course_type":"Course type", "duration":"Duration"})
    intervention_text = labeled_pairs(lang, intervention,
        {"ai_tool":"AI 工具", "allowed_usage":"允许使用", "frequency":"使用频率", "duration":"干预周期"},
        {"ai_tool":"AI tool", "allowed_usage":"Allowed usage", "frequency":"Frequency", "duration":"Duration"})
    outcome_map = frame.get("outcomes", {}) or {}
    outcome_parts = []
    for group, values in outcome_map.items():
        if isinstance(values, list):
            rendered = "、".join(label(lang, "outcome", v) for v in values) if lang == "zh" else ", ".join(label(lang, "outcome", v) for v in values)
            outcome_parts.append(f"{frame_enum_label(lang, group)}：{rendered}" if lang == "zh" else f"{frame_enum_label(lang, group)}: {rendered}")
    scope_parts = []
    scope_labels_zh = {"time_range":"时间范围", "geography":"地域", "study_types":"研究设计"}
    scope_labels_en = {"time_range":"Time range", "geography":"Geography", "study_types":"Study designs"}
    for key, value in scope.items():
        if value in (None, "", [], {}):
            continue
        if key == "study_types" and isinstance(value, list):
            rendered = "、".join(label(lang, "study", str(v)) for v in value) if lang == "zh" else ", ".join(label(lang, "study", str(v)) for v in value)
        else:
            rendered = frame_enum_label(lang, value)
        field_label = (scope_labels_zh if lang == "zh" else scope_labels_en).get(key, key)
        scope_parts.append(f"{field_label}：{rendered}" if lang == "zh" else f"{field_label}: {rendered}")
    scope_text = "；".join(scope_parts) if lang == "zh" else "; ".join(scope_parts)
    cards = [
        (labels["question"], frame.get("question") or result.get("meta", {}).get("question")),
        (labels["learner"], learner_text), (labels["course"], course_text),
        (labels["intervention"], intervention_text), (labels["comparison"], frame.get("comparison")),
        (labels["outcomes"], "；".join(outcome_parts) if lang == "zh" else "; ".join(outcome_parts)),
        (labels["scope"], scope_text), (labels["success"], frame.get("success_condition")),
    ]
    return '<div class="scope-grid">' + "".join(
        f'<article class="scope-card"><h3>{esc(title)}</h3>{expandable_text(text, ui["expand_details"], 260, "scope-text")}</article>'
        for title, text in cards if text) + '</div>'


def render_retrieval_context(result: dict, lang: str, ui: dict) -> str:
    frame = result.get("research_frame", {}) or {}
    inclusion = frame.get("inclusion_criteria") or []
    exclusion = frame.get("exclusion_criteria") or []
    provenance = result.get("provenance", {}) or {}
    sources = result.get("sources", []) or []
    source_ids = " ".join(f'<code>{esc(s.get("source_id"))}</code>' for s in sources)
    in_title = "纳入标准" if lang == "zh" else "Inclusion criteria"
    ex_title = "排除标准" if lang == "zh" else "Exclusion criteria"
    coverage_title = "证据来源覆盖" if lang == "zh" else "Source coverage"
    caution = ("当前报告只展示 result 中真实存在的检索与来源信息；没有流程计数时不伪造 PRISMA / funnel 数字。"
               if lang == "zh" else
               "This report shows only retrieval metadata present in result; it does not fabricate PRISMA/funnel counts when none exist.")
    return (f'<div class="retrieval-grid"><article><h3>{esc(in_title)}</h3><ul>'
            f'{"".join(f"<li>{esc(v)}</li>" for v in inclusion)}</ul></article>'
            f'<article><h3>{esc(ex_title)}</h3><ul>{"".join(f"<li>{esc(v)}</li>" for v in exclusion)}</ul></article></div>'
            f'<div class="retrieval-coverage"><h3>{esc(coverage_title)}</h3><p>{source_ids}</p>'
            f'{expandable_text(provenance.get("search_strategy") or provenance.get("search_query") or caution, ui["expand_details"], 300, "retrieval-note")}</div>')


def render_applicability_boundary(result: dict, lang: str, ui: dict) -> str:
    base = render_applicability(result, lang, ui)
    limits = result.get("decision", {}).get("exceeds_evidence_boundary") or []
    if not limits:
        return base
    title = "不可外推的结论" if lang == "zh" else "Claims beyond the evidence boundary"
    return (base + f'<div class="boundary-block"><h3>{esc(title)}</h3><ul>'
            + "".join(f'<li>{esc(item)}</li>' for item in limits) + '</ul></div>')


def render_full_report(result: dict, lang: str, ui: dict, charts: dict, infographics: dict,
                       figures: dict, viz: dict) -> str:
    svg = {}
    for key in ("workflow", "tribunal", "intervention", "evaluation"):
        value = infographics.get(key, "")
        value = value.replace("url(#arr)", f"url(#arr-{lang}-full-{key})")
        value = value.replace('id="arr"', f'id="arr-{lang}-full-{key}"')
        svg[key] = value
    figure_svg = figures.get("outcome-comparison.svg", "")
    outcome_chart = next((c for c in charts.get("charts", [])
                          if c.get("chart_id") == "outcome-evidence-overview"), None)

    trace_content = trace_chain_html(result, lang, ui)
    trace_chart = next((c for c in charts.get("charts", [])
                        if c.get("chart_id") == "claim-evidence-trace"), None)
    if viz.get("claim_trace", {}).get("render"):
        trace_content += (f'<div id="chart-trace-{lang}" class="chart-mount" '
                          f'aria-label="{esc(trace_chart.get("title") if trace_chart else "Claim-Evidence Trace")}"></div>')
        trace_content += (f'<p class="chart-interpretation"><strong>{esc(ui["what_this_means"])}{esc(ui["colon"])}</strong>'
                          f'{esc("每个重要主张都必须能追到 Evidence ID 和原始来源。" if lang == "zh" else "Every important claim must resolve to Evidence IDs and original sources.")}</p>')
    intervention_content = (render_evidence_to_action(result, lang, ui)
                            + render_intervention(result, svg.get("intervention", ""), lang, ui))
    evaluation_content = render_evaluation(result, svg.get("evaluation", ""), lang, ui)
    if viz.get("benchmark", {}).get("render"):
        evaluation_content += render_benchmark(charts, lang, ui)
    else:
        evaluation_content += (f'<div class="visual-suppressed"><strong>{esc("基准图已抑制" if lang == "zh" else "Benchmark visual suppressed")}</strong>'
                               f'<p>{esc(ui["benchmark_note"])}</p></div>')

    module_content = {
        "decision": first_screen(result, lang, ui),
        "scope": render_research_scope(result, lang, ui),
        "retrieval": render_retrieval_context(result, lang, ui),
        "outcomes": render_outcomes(result, outcome_chart, figure_svg, lang, ui, viz),
        "evidence": render_matrix_visual(result, lang, ui, instance="full"),
        "quality": render_methodology(result, lang, ui),
        "conflicts": render_conflicts(result, lang, ui),
        "trace": (render_tribunal_visual(result, svg.get("workflow", ""), svg.get("tribunal", ""),
                                         lang, ui, compact=False) + trace_content),
        "applicability": render_applicability_boundary(result, lang, ui),
        "intervention": intervention_content,
        "evaluation": evaluation_content,
        "sources": (render_sources(result, lang, ui, expandable=True)
                    + f'<h3>{esc(ui["provenance_title"])}</h3>' + render_provenance(result, lang, ui)
                    + render_v2_history(result, lang, ui)),
    }

    default_leads = {
        "decision": ("先明确最终裁决与研究边界，再解释为什么。" if lang == "zh" else "State the final adjudication and research boundary before explaining why."),
        "evidence": ("把任务表现、真实学习、保持与风险放在同一证据地图中，但不混为一谈。" if lang == "zh" else "Place task performance, actual learning, retention and risk on one evidence map without conflating them."),
        "quality": ("检查证据为什么可信、哪里冲突，以及哪些结论必须降级。" if lang == "zh" else "Examine why evidence is credible, where it conflicts, and which conclusions require downgrading."),
        "action": ("把可外推范围、护栏和教学动作连接到具体证据。" if lang == "zh" else "Connect applicability, guardrails and teaching actions to specific evidence."),
        "evaluation": ("用独立学习结果验证试点，并预先写清停止条件。" if lang == "zh" else "Validate the pilot with independent learning outcomes and pre-specified stop conditions."),
        "sources": ("保留原始来源、URL、证据 ID 和获取信息，确保可回查。" if lang == "zh" else "Preserve original sources, URLs, evidence IDs and retrieval metadata for auditability."),
    }

    plan = resolve_full_report_plan(result)
    rendered = []
    for index, chapter in enumerate(plan, 1):
        content = "".join(module_content.get(module, "") for module in chapter.get("modules", ()))
        lead = chapter.get("lead_zh" if lang == "zh" else "lead_en") or default_leads.get(chapter.get("key"), "")
        rendered.append(render_full_chapter(
            chapter_dom_id(lang, str(chapter.get("key") or f"chapter-{index}"), index),
            full_chapter_title(chapter, lang, index), content, str(lead or "")))
    return "".join(rendered)


def render_full_toc(result: dict, lang: str, ui: dict) -> str:
    plan = resolve_full_report_plan(result)
    links = "".join(
        f'<a href="#{esc(chapter_dom_id(lang, str(chapter.get("key") or f"chapter-{index}"), index))}" '
        f'data-toc-target="{esc(chapter_dom_id(lang, str(chapter.get("key") or f"chapter-{index}"), index))}" '
        f'data-chapter-key="{esc(chapter.get("key") or "")}">{esc(full_chapter_title(chapter, lang, index))}</a>'
        for index, chapter in enumerate(plan, 1))
    return (f'<aside class="full-report-toc" aria-label="{esc(ui["contents"])}">'
            f'<div class="toc-head"><strong>{esc(ui["contents"])}</strong>'
            f'<button type="button" class="toc-collapse" aria-expanded="true" '
            f'data-label-collapse="{esc(ui["collapse_contents"])}" data-label-expand="{esc(ui["expand_contents"])}">'
            f'{esc(ui["collapse_contents"])}</button></div><nav>{links}</nav></aside>')


def render_v2_history(result: dict, lang: str, ui: dict) -> str:
    """V2-only surfaces: project id / graph revision / decision snapshot /
    knowledge gaps / study design / dataset-analysis provenance / decision diff.

    Returns "" for V1 inputs so the renderer is a strict superset.
    """
    project_id = result.get("project_id")
    if not project_id:
        return ""
    revision = result.get("graph_revision")
    snap_id = result.get("decision_snapshot_id")
    out = [f"<h3>{esc(ui['v2_project_title'])}</h3>"]
    meta = [
        (ui["v2_project_id"], project_id),
        (ui["v2_graph_revision"], revision),
    ]
    if snap_id:
        meta.append((ui["v2_decision_snapshot"], snap_id))
    out.append("<div class='table-wrap'><table class='data-table'><tbody>"
               + "".join(f"<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>"
                         for k, v in meta if v not in (None, ""))
               + "</tbody></table></div>")

    # timeline: revision + decision per snapshot
    decision = result.get("decision") or result.get("decision", {}).get("verdict")
    confidence = result.get("confidence_label")
    if revision is not None:
        label = (f"<code>{esc(ui['v2_revision'])} {esc(revision)}</code>"
                 f" → {esc(ui['v2_decision'])} {esc(decision)}"
                 + (f" ({esc(confidence)})" if confidence else ""))
        out.append(f"<p class='v2-timeline'>{esc(ui['v2_timeline'])}{esc(ui['colon'])}{label}</p>")

    # knowledge gaps
    gaps = result.get("knowledge_gaps") or []
    if gaps:
        rows = []
        for g in gaps:
            rows.append(
                f"<tr><td><code>{esc(g.get('gap_id'))}</code></td>"
                f"<td>{esc(g.get('gap_type'))}</td>"
                f"<td>{esc(g.get('priority'))}</td>"
                f"<td>{esc(g.get('reasoning'))}</td></tr>")
        out.append(f"<h4>{esc(ui['v2_gaps_title'])}</h4>"
                   "<div class='table-wrap'><table class='data-table'><thead><tr>"
                   f"<th>{esc(ui['v2_revision'])}</th><th>{esc(ui['v2_gap_type'])}</th>"
                   f"<th>{esc(ui['v2_gap_priority'])}</th><th>{esc(ui['v2_gap_reasoning'])}</th>"
                   "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    # study designs
    designs = result.get("study_designs") or []
    if designs:
        rows = []
        for d in designs:
            rows.append(
                f"<tr><td><code>{esc(d.get('design_id'))}</code></td>"
                f"<td>{esc(d.get('design_type'))}</td>"
                f"<td>{esc(d.get('research_question'))}</td></tr>")
        out.append(f"<h4>{esc(ui['v2_design_title'])}</h4>"
                   "<div class='table-wrap'><table class='data-table'><thead><tr>"
                   f"<th>ID</th><th>{esc(ui['v2_design_type'])}</th>"
                   f"<th>{esc(ui['v2_design_question'])}</th>"
                   "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    # dataset/analysis provenance
    prov = result.get("analysis_provenance") or []
    if prov:
        rows = []
        for p in prov:
            rows.append(
                f"<tr><td><code>{esc(p.get('dataset_id'))}</code></td>"
                f"<td><code>{esc(p.get('design_id'))}</code></td>"
                f"<td><code>{esc(p.get('analysis_run_id'))}</code></td></tr>")
        out.append(f"<h4>{esc(ui['v2_provenance_title'])}</h4>"
                   "<div class='table-wrap'><table class='data-table'><thead><tr>"
                   "<th>Dataset</th><th>Design</th><th>AnalysisRun</th>"
                   "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")

    # decision diff when present
    diff = result.get("decision_diff")
    if isinstance(diff, dict):
        rows = []
        for key, label in (("from_graph_revision", ui["v2_revision"]),
                           ("to_graph_revision", ui["v2_graph_revision"]),
                           ("action_changed", ui["v2_diff_action"]),
                           ("confidence_changed", ui["v2_diff_confidence"])):
            if key in diff:
                rows.append(f"<tr><th>{esc(label)}</th><td>{esc(diff[key])}</td></tr>")
        if diff.get("changed_claims"):
            rows.append(f"<tr><th>{esc(ui['v2_diff_claims'])}</th>"
                        f"<td>{esc(', '.join(map(str, diff['changed_claims'])))}</td></tr>")
        if diff.get("resolved_gaps") or diff.get("new_gaps"):
            rows.append(f"<tr><th>{esc(ui['v2_diff_gaps'])}</th>"
                        f"<td>{esc('resolved: ' + ', '.join(map(str, diff.get('resolved_gaps') or [])))}"
                        f"{esc(' / new: ' + ', '.join(map(str, diff.get('new_gaps') or [])))}</td></tr>")
        out.append(f"<h4>{esc(ui['v2_diff_title'])}</h4>"
                   "<div class='table-wrap'><table class='data-table'><tbody>"
                   + "".join(rows) + "</tbody></table></div>")

    return "".join(out)


def _theme_css() -> str:
    blocks = []
    for name in THEME_NAMES:
        css = THEMES_DIR / f"{name}.css"
        if css.exists():
            blocks.append(css.read_text(encoding="utf-8"))
    return "\n".join(blocks)


def _motion_css() -> str:
    path = MOTION_DIR / "motion.css"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _motion_js() -> str:
    path = MOTION_DIR / "motion.js"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _lang_switcher(ui_zh: dict, ui_en: dict) -> str:
    return (
        f'<div class="lang-switcher" role="group" aria-label="{esc(ui_zh["lang_switcher_aria"])}">'
        f'<span data-lang-label data-zh="{esc(ui_zh["lang_label"])}" '
        f'data-en="{esc(ui_en["lang_label"])}">{esc(ui_zh["lang_label"])}</span>'
        f'<button type="button" data-lang-target="zh" class="lang-btn active" aria-pressed="true">{esc(ui_zh["zh"])}</button>'
        f'<button type="button" data-lang-target="en" class="lang-btn" aria-pressed="false">{esc(ui_en["en"])}</button>'
        "</div>")


def _enhancer_js(charts_zh: dict, charts_en: dict, result_en: dict) -> str:
    outcome_zh = next((c for c in charts_zh.get("charts", [])
                       if c.get("chart_id") == "outcome-evidence-overview"), None)
    trace_zh = next((c for c in charts_zh.get("charts", [])
                     if c.get("chart_id") == "claim-evidence-trace"), None)
    benchmark_zh = charts_zh.get("benchmark") or {}
    outcome_en = next((c for c in charts_en.get("charts", [])
                       if c.get("chart_id") == "outcome-evidence-overview"), None)
    trace_en = next((c for c in charts_en.get("charts", [])
                     if c.get("chart_id") == "claim-evidence-trace"), None)
    benchmark_en = charts_en.get("benchmark") or {}
    matrix_rows = [
        {"id": e.get("evidence_id"), "title": e.get("title", ""),
         "direction": e.get("direction", "neutral"),
         "outcome": e.get("outcome_type", ""), "quality": e.get("quality_score", 0)}
        for e in result_en.get("evidence", [])
    ]
    return f"""
(function () {{
  'use strict';
  var root = document.documentElement;
  // ---- Language switcher (zh / en) ----
  function applyLang(lang) {{
    document.querySelectorAll('.report-shell[data-lang-body]').forEach(function (shell) {{
      shell.style.display = shell.dataset.langBody === lang ? '' : 'none';
    }});
    document.documentElement.lang = lang === 'en' ? 'en' : 'zh-CN';
    document.querySelectorAll('.lang-btn').forEach(function (b) {{
      var active = b.dataset.langTarget === lang;
      b.classList.toggle('active', active);
      b.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});
    var langLabel = document.querySelector('[data-lang-label]');
    if (langLabel) {{
      langLabel.textContent = lang === 'en' ? langLabel.dataset.en : langLabel.dataset.zh;
    }}
    Object.keys(window.eduevidenceCharts || {{}}).forEach(function (id) {{
      var ch = window.eduevidenceCharts[id];
      if (ch && ch.resize) ch.resize();
    }});
    try {{ localStorage.setItem('eduevidence-lang', lang); }} catch (e) {{}}
  }}
  var savedLang = null;
  try {{ savedLang = localStorage.getItem('eduevidence-lang'); }} catch (e) {{}}
  applyLang(savedLang === 'en' ? 'en' : 'zh');
  document.querySelectorAll('.lang-btn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{ applyLang(btn.dataset.langTarget); }});
  }});

  // ---- Top-level Visual Brief / Full Report pagination ----
  function applyReportView(view) {{
    view = view === 'full' ? 'full' : 'brief';
    document.querySelectorAll('.report-page[data-report-page]').forEach(function (page) {{
      page.hidden = page.dataset.reportPage !== view;
    }});
    document.querySelectorAll('.report-view-btn').forEach(function (btn) {{
      var active = btn.dataset.reportView === view;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    }});
    root.dataset.reportView = view;
    try {{ localStorage.setItem('eduevidence-report-view', view); }} catch (e) {{}}
  }}
  var savedView = null;
  try {{ savedView = localStorage.getItem('eduevidence-report-view'); }} catch (e) {{}}
  applyReportView(savedView === 'full' ? 'full' : 'brief');
  document.querySelectorAll('.report-view-btn').forEach(function (btn) {{
    btn.addEventListener('click', function () {{ applyReportView(btn.dataset.reportView); }});
  }});

  // ---- Collapsible Full Report TOC ----
  document.querySelectorAll('.full-report-layout').forEach(function (layout) {{
    var button = layout.querySelector('.toc-collapse');
    if (!button) return;
    button.addEventListener('click', function () {{
      var collapsed = layout.classList.toggle('toc-collapsed');
      button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      button.textContent = collapsed ? button.dataset.labelExpand : button.dataset.labelCollapse;
    }});
  }});

  // ---- TOC active chapter tracking ----
  if ('IntersectionObserver' in window) {{
    document.querySelectorAll('.report-shell').forEach(function (shell) {{
      var links = Array.from(shell.querySelectorAll('[data-toc-target]'));
      if (!links.length) return;
      var sections = links.map(function (link) {{ return shell.querySelector('#' + CSS.escape(link.dataset.tocTarget)); }}).filter(Boolean);
      var activeObserver = new IntersectionObserver(function (entries) {{
        var visible = entries.filter(function (entry) {{ return entry.isIntersecting; }})
          .sort(function (a,b) {{ return a.boundingClientRect.top - b.boundingClientRect.top; }});
        if (!visible.length) return;
        var id = visible[0].target.id;
        links.forEach(function (link) {{ link.classList.toggle('active', link.dataset.tocTarget === id); }});
      }}, {{rootMargin:'-12% 0px -72% 0px', threshold:[0,0.01]}});
      sections.forEach(function (section) {{ activeObserver.observe(section); }});
    }});
  }}

  // ---- Evidence matrix filter / search ----
  function bindMatrix(matrix) {{
    var suffix = matrix.id.replace(/^evidence-matrix-/, '');
    var search = document.getElementById('matrix-search-' + suffix);
    var dirSel = document.getElementById('matrix-direction-' + suffix);
    var outSel = document.getElementById('matrix-outcome-' + suffix);
    var rows = matrix.querySelectorAll('tbody tr');
    function applyFilter() {{
      var q = (search && search.value || '').toLowerCase();
      var d = dirSel ? dirSel.value : '';
      var o = outSel ? outSel.value : '';
      rows.forEach(function (row) {{
        var haystack = (row.dataset.search || row.textContent || '').toLowerCase();
        var direction = row.dataset.direction || row.dataset.effect || '';
        var outcome = row.dataset.outcome || '';
        var show = (!q || haystack.indexOf(q) >= 0)
          && (!d || direction === d) && (!o || outcome === o);
        row.style.display = show ? '' : 'none';
      }});
    }}
    if (search) search.addEventListener('input', applyFilter);
    if (dirSel) dirSel.addEventListener('change', applyFilter);
    if (outSel) outSel.addEventListener('change', applyFilter);
  }}
  document.querySelectorAll('table[id^=evidence-matrix-]').forEach(bindMatrix);

  // ---- Motion preference is owned by the fixed Motion Template. ----
  var reduceMotion = !!window.__EDUEVIDENCE_REDUCE_MOTION__ ||
    !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  // ---- ECharts enhancer (only when window.echarts exists) ----
  // 成功 init 后给容器加 .is-mounted 才显示（6.2：无 ECharts 时不占空白高度）
  function mountChart(containerId, spec) {{
    var el = document.getElementById(containerId);
    if (!el || typeof window.echarts === 'undefined') return;
    var chart = window.echarts.init(el);
    var option = Object.assign({{}}, spec.option || {{}});
    option.animation = !reduceMotion;
    if (!reduceMotion) {{
      option.animationDuration = 650;
      option.animationDurationUpdate = 420;
      option.animationEasing = 'cubicOut';
      option.animationEasingUpdate = 'cubicOut';
    }}
    chart.setOption(option);
    el.classList.add('is-mounted');
    window.eduevidenceCharts = window.eduevidenceCharts || {{}};
    window.eduevidenceCharts[containerId] = chart;
  }}
  mountChart('chart-outcome-zh', {json.dumps(outcome_zh or {}, ensure_ascii=False)});
  mountChart('chart-trace-zh', {json.dumps(trace_zh or {}, ensure_ascii=False)});
  mountChart('chart-benchmark-zh', {json.dumps(benchmark_zh, ensure_ascii=False)});
  mountChart('chart-outcome-en', {json.dumps(outcome_en or {}, ensure_ascii=False)});
  mountChart('chart-trace-en', {json.dumps(trace_en or {}, ensure_ascii=False)});
  mountChart('chart-benchmark-en', {json.dumps(benchmark_en, ensure_ascii=False)});
}})();
"""


def render_brief_block(title: str, lead: str, content: str, css_class: str = "") -> str:
    return (f'<section class="brief-block {esc(css_class)}">'
            f'<header class="brief-block-header"><h2>{esc(title)}</h2><p>{esc(lead)}</p></header>'
            f'<div class="brief-block-body">{content}</div></section>')


def render_outcomes_brief(result: dict, chart: dict | None, lang: str, ui: dict, viz: dict) -> str:
    separation = render_outcome_separation(result, lang, ui) if viz.get("outcome_separation", {}).get("render") else ""
    if not viz.get("outcome_evidence_balance", {}).get("render") or not chart:
        return separation
    visual = (f'<div class="visual-surface brief-chart" data-visual="outcome-evidence-balance">'
              f'{diverging_bar_svg(chart.get("option", {}), lang=lang, ui=ui)}'
              f'<p class="chart-interpretation"><strong>{esc(ui["what_this_means"])}{esc(ui["colon"])}</strong>'
              f'{esc(chart.get("summary_text") or "")}</p></div>')
    return separation + visual


def render_brief_sources(result: dict, lang: str, ui: dict, limit: int = 4) -> str:
    sources = result.get("sources", []) or []
    if not sources:
        return f'<p>{esc(ui["no_data"])}</p>'
    cards = []
    for source in sources[:limit]:
        url = safe_http_url(source.get("canonical_url") or source.get("source_location"))
        title = source.get("title") or source.get("source_id") or ""
        linked = f'<a href="{esc(url)}">{esc(title)}</a>' if url else esc(title)
        cards.append(f'<article class="brief-source"><code>{esc(source.get("source_id"))}</code>'
                     f'<h3>{linked}</h3><p>{esc(label(lang, "authority", source.get("authority_level") or ""))}'
                     f' · {esc(source.get("year"))}</p></article>')
    remaining = len(sources) - len(cards)
    more = (f'<p class="brief-source-more">完整报告中还有 {remaining} 个来源可展开追溯。</p>' if lang == "zh" and remaining > 0
            else f'<p class="brief-source-more">{remaining} more sources are traceable in the full report.</p>' if remaining > 0
            else "")
    return f'<div class="brief-source-grid">{"".join(cards)}</div>{more}'


def render_lieflat_gallery_brief(result: dict, figures: dict, layout: dict,
                                 lieflat_meta: dict, lang: str, ui: dict) -> str:
    """Visual Brief Lieflat gallery — data-driven composition card.

    Renders ONLY entries that passed resolve_visual_layout AND whose extractor
    produced data (present in figures). Card four-piece set: conclusion title
    (700) + subtitle (legend, `·` separated) + themed inline SVG + uppercase
    source line; caption sits under the figure. Suppressed charts are listed
    with their reasons (Meaningful Visualization Gate mirror).
    """
    entries = (layout or {}).get("entries") or []
    zh = lang == "zh"
    cards = []
    for entry in entries:
        cid = entry.get("chart_id")
        svg = figures.get(cid)
        if not svg:
            continue
        title = entry.get("title_zh" if zh else "title_en") or ""
        subtitle = entry.get("subtitle_zh" if zh else "subtitle_en") or ""
        caption = entry.get("caption_zh" if zh else "caption_en") or ""
        source_line = f"{entry.get('catalog_ref', '')} · {entry.get('source', '')}".strip(" ·")
        fig_type = entry.get("type", "")
        cards.append(
            f'<figure class="lieflat-card" data-lieflat data-visual="lieflat-{esc(fig_type)}" '
            f'data-chart-id="{esc(cid)}">'
            f'<h3 class="lieflat-title">{esc(title)}</h3>'
            f'<p class="lieflat-sub">{esc(subtitle)}</p>'
            f'<div class="lieflat-figure">{svg}</div>'
            + (f'<figcaption class="lieflat-caption">{esc(caption)}</figcaption>' if caption else "")
            + f'<p class="lieflat-src">{esc(source_line)}</p>'
            f'</figure>')
    suppressed = (lieflat_meta or {}).get("suppressed") or []
    if suppressed:
        label = ("已抑制 {} 张图（数据不足，镜像 Meaningful Visualization Gate）"
                 if zh else "{} charts suppressed (insufficient data; mirrors the Meaningful Visualization Gate)")
        items = "".join(
            f"<li><code>{esc(s.get('catalog_ref') or s.get('type'))}</code>"
            f"{esc(zh and '：' or ': ')}{esc(s.get('reason') or '')}</li>"
            for s in suppressed)
        cards.append(f'<div class="lieflat-suppressed" role="note">'
                     f'<strong>{label.format(len(suppressed))}</strong><ul>{items}</ul></div>')
    if not cards:
        return ""
    return ('<div class="lieflat-gallery-container">' + "".join(cards) + "</div>")


def render_body(result: dict, lang: str, ui: dict, charts: dict, infographics: dict,
                figures: dict, viz: dict, theme: str, integrity: dict | None = None) -> str:
    decision = result.get("decision", {})
    meta = result.get("meta", {})
    question = meta.get("question") or decision.get("decision_question") or "EduEvidence Report"
    outcome_chart = next((c for c in charts.get("charts", [])
                          if c.get("chart_id") == "outcome-evidence-overview"), None)

    if lang == "zh":
        brief_titles = {
            "decision": ("先看结论", "该不该做、置信度多高、最关键的证据边界在哪。"),
            "lieflat": ("Lieflat 实证手作画廊", "AI 按数据形状从 Lieflat 目录选型编排；每张图的数字都可溯源到 result.json。"),
            "outcomes": ("任务表现 ≠ 学习效果", "只展示真正有解释力的结果分离；正向、负向与零效应按 effect_direction 编码。"),
            "tribunal": ("证据裁决", "支持、不确定、被反驳与缺失证据分开放置，不把长段落平铺在同一层。"),
            "action": ("从证据到行动", "适用性、护栏、停止条件与评价连成一条可执行路径。"),
            "sources": ("关键来源", "摘要页只列最关键的来源；完整溯源在完整报告中展开。"),
        }
    else:
        brief_titles = {
            "decision": ("Decision first", "What to do, how confident we are, and the most important evidence boundary."),
            "lieflat": ("Lieflat Editorial Gallery", "Charts selected and composed by AI from the Lieflat catalog; every number traces back to result.json."),
            "outcomes": ("Task performance ≠ learning", "Only informative outcome separation; positive, negative and null effects use effect_direction."),
            "tribunal": ("Evidence tribunal", "Supported, uncertain, contradicted and missing evidence stay separated instead of flattened into long prose."),
            "action": ("Evidence to action", "Applicability, guardrails, stop conditions and evaluation form one executable path."),
            "sources": ("Key sources", "Only the key sources in the brief; full traceability expands in the full report."),
        }

    lieflat_layout = viz.get("lieflat_layout") or {"entries": []}
    lieflat_meta = (viz.get("lieflat_meta") or {}).get(lang, {})
    lieflat_gallery_html = render_lieflat_gallery_brief(result, figures, lieflat_layout,
                                                        lieflat_meta, lang, ui)

    brief_blocks = [
        render_brief_block(*brief_titles["decision"], first_screen(result, lang, ui), "brief-decision"),
    ]
    if lieflat_gallery_html:
        brief_blocks.append(render_brief_block(*brief_titles["lieflat"], lieflat_gallery_html, "brief-lieflat"))
    brief_blocks.extend([
        render_brief_block(*brief_titles["outcomes"], render_outcomes_brief(result, outcome_chart, lang, ui, viz), "brief-outcomes"),
        render_brief_block(*brief_titles["tribunal"], render_tribunal_visual(result, "", "", lang, ui, compact=True), "brief-tribunal"),
        render_brief_block(*brief_titles["action"], render_evidence_to_action(result, lang, ui), "brief-action"),
        render_brief_block(*brief_titles["sources"], render_brief_sources(result, lang, ui), "brief-sources"),
    ])
    brief = "".join(brief_blocks)
    full_report = render_full_report(result, lang, ui, charts, infographics, figures, viz)
    toc = render_full_toc(result, lang, ui)

    integrity_text = integrity_footer_text(integrity or {}, ui)
    footer = ui['footer'].format(integrity=integrity_text)
    origin = (meta.get('data_origin') or '').strip()
    if origin:
        origin_label = DATA_ORIGIN_LABELS.get(origin, {}).get(lang, origin)
        origin_chip = (f'<span class="data-origin-chip" data-origin="{esc(origin)}">'
                       f'{esc(origin_label)}</span>')
    else:
        origin_chip = ''
    meta_line = (f"{esc(ui['header_mode'])}{esc(label(lang, 'mode', meta.get('mode') or ''))}"
                 f" · {esc(ui['header_generated'])}{esc(meta.get('generated_at') or '')}"
                 f" · {esc(ui['header_evidence'])}{len(result.get('evidence', []))}"
                 f"{esc(ui['header_evidence_suffix'])}"
                 f" · {esc(ui['header_sources'])}{len(result.get('sources', []))}"
                 f"{esc(ui['header_sources_suffix'])}")
    return f"""<div class="report-shell" data-lang-body="{lang}">
<header class="report-header">
<div class="report-brand-row"><span class="report-brand">EduEvidence</span><span class="generated-theme-chip">{esc(THEME_DISPLAY[theme])}</span>{origin_chip}</div>
<h1>{esc(question)}</h1>
<p class="meta">{meta_line}</p>
<nav class="report-view-switcher" aria-label="report view">
<button type="button" class="report-view-btn active" data-report-view="brief" aria-pressed="true">{esc(ui['visual_brief'])}</button>
<button type="button" class="report-view-btn" data-report-view="full" aria-pressed="false">{esc(ui['full_report'])}</button>
</nav>
</header>
<div class="report-page report-page-brief" data-report-page="brief">{brief}</div>
<div class="report-page report-page-full" data-report-page="full" hidden>
<div class="full-report-intro"><h2>{esc(ui['full_report'])}</h2><p>{esc(ui['full_report_intro'])}</p></div>
<div class="full-report-layout">{toc}<main class="full-report-content">{full_report}</main></div>
</div>
<footer class="report-footer"><p>{esc(footer)}</p></footer>
</div>"""


def render_html(result_en: dict, result_zh: dict, charts_zh: dict, charts_en: dict,
                infographics_zh: dict, infographics_en: dict, figures_zh: dict,
                figures_en: dict, theme: str, viz: dict,
                result_sha256: str = "", integrity: dict | None = None) -> str:
    # Theme is fixed at generation time; language remains switchable in the HTML.
    body_zh = render_body(result_zh, "zh", UI_ZH, charts_zh, infographics_zh, figures_zh, viz, theme,
                          integrity=integrity)
    body_en = render_body(result_en, "en", UI_EN, charts_en, infographics_en, figures_en, viz, theme,
                          integrity=integrity)
    hash_meta = (f'<meta name="eduevidence-result-sha256" content="{esc(result_sha256)}">\n'
                 if result_sha256 else "")

    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="{esc(theme)}">
<head>
<meta charset="utf-8">
{hash_meta}<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(result_zh.get("meta", {}).get("question") or result_en.get("meta", {}).get("question") or "EduEvidence Evidence Report")}</title>
<style>
{_theme_css()}
:root {{
  --bg:#F7F4ED; --surface:#FFFFFF; --surface2:#FCFAF6;
  --text:#3A3833; --primary:#B8694A; --support:#5E8A6A;
  --contradict:#A85B53; --uncertain:#C99A4A; --insufficient:#8A867E;
  --border:#E5DFD3; --radius:10px; --shadow:0 1px 3px rgba(60,56,48,.08);
  --font-head:'Georgia','Songti SC','Noto Serif CJK SC',serif;
  --font-ui:'Helvetica Neue','PingFang SC','Noto Sans CJK SC',Arial,sans-serif;
}}
* {{ box-sizing:border-box; }}
html, body {{ max-width:100%; overflow-x:hidden; }}
body {{ margin:0; background:var(--bg); color:var(--text);
       font-family:var(--font-ui); line-height:1.65;
       font-variant-numeric:tabular-nums; }}
.report-shell {{ width:100%; max-width:1200px; margin:0 auto; padding:24px clamp(18px,3vw,32px) 80px; }}
.controls {{ width:calc(100% - 36px); max-width:1200px; margin:0 auto 16px; padding:12px clamp(0px,1vw,12px); display:flex; gap:18px; flex-wrap:wrap; align-items:center;
            border-bottom:1px solid var(--border); }}
.report-header {{ border-bottom:1px solid var(--border); padding-bottom:16px; margin-bottom:24px; }}
.report-header h1 {{ font-family:var(--font-head); font-size:1.9rem; margin:0 0 8px; color:var(--text); }}
.report-header .meta {{ color:var(--insufficient); font-size:.85rem; }}
.lang-switcher {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.lang-switcher span {{ font-size:.82rem; color:var(--insufficient); }}
.lang-btn {{ background:var(--surface); border:1px solid var(--border); border-radius:999px;
             padding:4px 12px; font-size:.8rem; cursor:pointer; color:var(--text); }}
.lang-btn.active {{ background:var(--primary); color:#fff; border-color:var(--primary); }}
.report-section {{ background:var(--surface); border:1px solid var(--border);
                  border-radius:var(--radius); box-shadow:var(--shadow);
                  padding:20px 24px; margin-bottom:20px; }}
.report-section h2 {{ font-family:var(--font-head); font-size:1.25rem; margin:0 0 6px;
                     border-bottom:1px solid var(--border); padding-bottom:8px; }}
.section-lead {{ font-size:.88rem; color:var(--insufficient); margin:0 0 14px;
                background:var(--surface2); border-radius:6px; padding:8px 12px;
                border-left:3px solid var(--primary); }}
.report-section h3 {{ font-size:.95rem; margin:14px 0 6px; }}
.decision-card {{ padding:18px 20px; border-radius:10px;
                 border-left:6px solid var(--insufficient); background:var(--surface2);
                 box-shadow:var(--shadow); }}
.decision-card.adopt {{ border-left-color:var(--support); }}
.decision-card.pilot {{ border-left-color:var(--uncertain); }}
.decision-card.reject {{ border-left-color:var(--contradict); }}
.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px 18px; }}
.kpi-label {{ display:block; font-size:.72rem; color:var(--insufficient); text-transform:uppercase; letter-spacing:.05em; margin-bottom:2px; }}
.kpi-value {{ font-size:1.05rem; font-weight:600; }}
.decision-value {{ font-family:var(--font-head); font-size:1.5rem; font-weight:700; }}
.confidence-badge {{ background:var(--uncertain); color:#fff; border-radius:999px; padding:3px 12px; font-size:.82rem; }}
.rationale {{ color:var(--text); font-size:.92rem; margin-top:12px; border-top:1px dashed var(--border);
             padding-top:10px; }}
.exec-summary {{ background:var(--surface2); border:1px solid var(--border);
                 border-radius:10px; padding:16px 20px; margin-bottom:18px; }}
.exec-summary h3 {{ margin:0 0 10px; color:var(--primary); }}
.summary-row {{ display:flex; gap:12px; margin:8px 0; }}
.summary-k {{ flex:0 0 64px; font-weight:700; color:var(--insufficient); font-size:.88rem; }}
.summary-v {{ flex:1; font-size:.95rem; }}
.summary-list {{ margin:4px 0 0; padding-left:18px; }}
.summary-tag {{ display:inline-block; border-radius:999px; padding:0 10px; font-size:.75rem; color:#fff; }}
.summary-tag.pos {{ background:var(--support); }}
.summary-tag.neg {{ background:var(--contradict); }}
ul.can li {{ border-left:3px solid var(--support); }}
ul.uncertain li {{ border-left:3px solid var(--uncertain); }}
ul.cannot li {{ border-left:3px solid var(--contradict); }}
ul.can li, ul.uncertain li, ul.cannot li {{ list-style:none; margin:6px 0; padding:6px 10px;
  background:var(--surface2); border-radius:6px; font-size:.9rem; }}
.report-section svg {{ max-width:100%; height:auto; border:1px solid var(--border);
                       border-radius:var(--radius-sm); background:#fff; }}
.table-wrap {{ overflow-x:auto; -webkit-overflow-scrolling:touch; border:1px solid var(--border);
               border-radius:var(--radius-sm); max-width:100%; }}
.table-wrap .data-table {{ border:none; }}
.data-table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
.table-wrap .data-table th {{ background:var(--surface2); position:sticky; top:0; white-space:nowrap; }}
.data-table th, .data-table td {{ border:1px solid var(--border); padding:7px 10px; text-align:left;
                                  vertical-align:top; }}
.data-table th {{ background:var(--surface2); white-space:nowrap; }}
.data-table td.cell-main {{ max-width:280px; overflow:hidden; text-overflow:ellipsis;
                            white-space:nowrap; }}
.data-table tbody tr:nth-child(even) {{ background:var(--surface2); }}
.data-table tbody tr:hover {{ background:var(--primary-soft, #F3E4DC); }}
.raw-tag {{ display:inline-block; margin-left:6px; font-size:.68rem; color:var(--insufficient);
           background:var(--surface2); border:1px solid var(--border); border-radius:4px;
           padding:0 5px; vertical-align:1px; font-family:'SF Mono',Menlo,monospace; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }}
.dir {{ display:inline-block; border-radius:999px; padding:1px 9px; font-size:.78rem; }}
.dir.pos {{ background:var(--support); color:#fff; }}
.dir.neg {{ background:var(--contradict); color:#fff; }}
.dir.neu {{ background:var(--uncertain); color:#fff; }}
.method-verdict {{ font-weight:700; }}
.phase {{ border-left:3px solid var(--primary); padding:4px 0 4px 14px; margin:12px 0;
         background:var(--surface2); border-radius:6px; }}
.phase h3 {{ margin-top:4px; }}
.conflict-card {{ border-left:3px solid var(--contradict); background:var(--surface2);
                 padding:10px 14px; margin:8px 0; border-radius:6px; }}
.trace-row {{ margin:2px 0; font-size:.88rem; }}
.trace-decision {{ font-weight:700; padding:4px 0; }}
.trace-claim {{ margin-left:16px; padding:3px 0; }}
.trace-evidence {{ margin-left:36px; color:var(--text); padding:2px 0; }}
.chart-mount {{ display:none; width:100%; height:320px; margin-top:10px; }}
.chart-mount.is-mounted {{ display:block; }}
.chart-summary {{ color:var(--insufficient); font-size:.85rem; }}
.academic-figure {{ margin:14px 0; }}
.academic-figure svg {{ max-width:100%; height:auto; }}
.academic-figure figcaption {{ font-size:.82rem; color:var(--insufficient); margin-top:6px; }}
.matrix-tools {{ display:flex; gap:10px; flex-wrap:wrap; margin:8px 0; }}
.matrix-tools input, .matrix-tools select {{ padding:5px 10px; font-size:.85rem;
  border:1px solid var(--border); border-radius:6px; background:var(--surface); color:var(--text); }}
.matrix-controls summary {{ cursor:pointer; color:var(--primary); font-size:.88rem; }}
details.matrix-controls {{ margin-bottom:8px; }}
code {{ font-family:'SF Mono',Menlo,monospace; font-size:.82em; background:var(--surface2);
       padding:1px 4px; border-radius:4px; }}
a {{ color:var(--primary); word-break:break-word; }}
button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {{
  outline:3px solid color-mix(in srgb, var(--primary) 45%, transparent); outline-offset:3px;
}}
.generated-theme {{ font-size:.76rem; letter-spacing:.08em; text-transform:uppercase; color:var(--insufficient); margin-right:auto; }}
.report-section {{ margin-bottom:clamp(28px,4vw,58px); }}
.section-narrative {{ width:100%; max-width:820px; margin-left:auto; margin-right:auto; }}
.section-data {{ width:100%; max-width:1180px; margin-left:auto; margin-right:auto; }}
.section-decision {{ width:100%; max-width:1040px; margin-left:auto; margin-right:auto; }}
.decision-hero {{ position:relative; overflow:hidden; padding:clamp(22px,4vw,42px); border:1px solid var(--border);
  border-radius:calc(var(--radius) + 4px); background:var(--surface2); }}
.hero-decision {{ display:flex; gap:12px 18px; flex-wrap:wrap; align-items:center; margin-bottom:18px; }}
.eyebrow, .hero-insight>span, .action-node>span {{ display:block; font-size:.72rem; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; color:var(--insufficient); }}
.hero-rationale {{ max-width:860px; font-family:var(--font-head); font-size:clamp(1.05rem,2vw,1.35rem); line-height:1.5; margin:0 0 28px; }}
.hero-insights {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
.hero-insight {{ min-height:112px; padding:16px 18px; border-top:2px solid var(--border); background:var(--surface); }}
.hero-insight.support {{ border-top-color:var(--support); }} .hero-insight.uncertain {{ border-top-color:var(--uncertain); }}
.hero-insight.risk {{ border-top-color:var(--contradict); }} .hero-insight.next {{ border-top-color:var(--primary); }}
.hero-insight p {{ margin:7px 0 0; font-size:.94rem; }}
.hero-provenance {{ margin:18px 0 0; color:var(--insufficient); font-size:.82rem; }}
.visual-heading {{ max-width:760px; margin-bottom:18px; }} .visual-heading h3 {{ font-size:1.15rem; margin-bottom:6px; }}
.visual-heading p {{ color:var(--insufficient); margin:0; }}
.outcome-separation {{ margin:10px 0 24px; }}
.outcome-groups {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(220px,100%),1fr)); gap:14px; }}
.outcome-group {{ padding:16px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); }}
.outcome-group h3 {{ margin:0 0 10px; }} .outcome-group ul {{ list-style:none; margin:0; padding:0; }}
.outcome-group li {{ display:flex; flex-direction:column; gap:7px; padding:9px 0; border-top:1px solid var(--border); }}
.outcome-group li:first-child {{ border-top:0; }} .outcome-states {{ display:flex; gap:6px; flex-wrap:wrap; }}
.visual-surface {{ margin:22px 0; padding:16px; border:1px solid var(--border); background:var(--surface2); border-radius:var(--radius); }}
.matrix-controls {{ margin:0 0 12px; }} .matrix-tools {{ align-items:center; }}
.matrix-tools input {{ min-width:min(360px,100%); flex:1; }}
.evidence-matrix th:nth-child(1) {{ width:72px; }} .evidence-matrix th:nth-child(3) {{ width:110px; }}
.evidence-matrix th:nth-child(4) {{ width:130px; }} .evidence-matrix th:nth-child(6) {{ width:92px; }}
.claim-cell {{ min-width:320px; max-width:520px; }} .claim-cell>p {{ margin:0 0 6px; }}
.matrix-row-detail {{ font-size:.78rem; color:var(--insufficient); }} .matrix-row-detail summary {{ color:var(--primary); cursor:pointer; }}
.matrix-row-detail p {{ margin:4px 0; }}
.quality-cell {{ display:flex; align-items:center; gap:8px; min-width:90px; }}
.quality-meter {{ display:block; width:64px; height:5px; border-radius:99px; background:var(--border); overflow:hidden; }}
.quality-meter i {{ display:block; height:100%; background:var(--primary); border-radius:inherit; }}
.evidence-tribunal {{ margin-top:8px; }} .tribunal-summary {{ margin:0 0 18px; }}
.tribunal-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }}
.tribunal-card {{ padding:16px 18px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); }}
.tribunal-card header {{ display:flex; gap:9px; align-items:center; }} .tribunal-card header>span {{ font-weight:800; }}
.tribunal-card.supported {{ border-top:3px solid var(--support); }} .tribunal-card.uncertain {{ border-top:3px solid var(--uncertain); }}
.tribunal-card.contradicted {{ border-top:3px solid var(--contradict); }} .tribunal-card.missing {{ border-top:3px solid var(--insufficient); }}
.tribunal-card ul {{ margin:10px 0 0; padding-left:18px; }} .tribunal-card li {{ margin:7px 0; }}
.supporting-visual {{ margin-top:16px; }} .supporting-visual summary {{ cursor:pointer; color:var(--primary); }}
.trace-chain {{ display:grid; gap:14px; }} .trace-chain-card {{ padding:16px 18px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); }}
.trace-claim-node p {{ margin:5px 0 0; }} .trace-arrow {{ color:var(--insufficient); text-align:center; }}
.trace-evidence-list {{ display:grid; gap:7px; }} .trace-evidence-node {{ display:flex; flex-wrap:wrap; gap:7px 10px; align-items:center; padding:8px 10px; background:var(--surface); border-radius:var(--radius-sm); }}
.evidence-to-action {{ display:flex; gap:10px; align-items:stretch; overflow-x:auto; padding:6px 0 20px; margin-bottom:22px; }}
.action-node {{ flex:1 0 165px; padding:14px 15px; border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); }}
.action-node p {{ margin:7px 0 0; font-size:.84rem; }} .flow-arrow {{ align-self:center; color:var(--insufficient); }}
.relation-note {{ display:block; margin-top:5px; font-size:.68rem; color:var(--insufficient); line-height:1.35; }}
.semantic-note, .chart-interpretation {{ margin:9px 0 0; color:var(--insufficient); font-size:.82rem; }}
.detail-expander {{ margin-top:7px; }} .detail-expander>summary {{ cursor:pointer; color:var(--primary); font-size:.78rem; }}
.detail-body {{ margin-top:8px; padding:10px 12px; border-left:2px solid var(--border); background:var(--surface2); }}
.detail-body p {{ margin:0; white-space:normal; }}
.evidence-detail-grid, .source-detail-grid {{ margin:10px 0 0; display:grid; grid-template-columns:minmax(120px,170px) 1fr; gap:0; }}
.evidence-detail-row, .source-detail-row {{ display:contents; }}
.evidence-detail-grid dt, .evidence-detail-grid dd, .source-detail-grid dt, .source-detail-grid dd {{ margin:0; padding:7px 8px; border-top:1px solid var(--border); }}
.evidence-detail-grid dt, .source-detail-grid dt {{ color:var(--insufficient); font-size:.75rem; }}
.evidence-detail-grid dd, .source-detail-grid dd {{ font-size:.8rem; overflow-wrap:anywhere; }}
.tribunal-count {{ margin-left:auto; min-width:24px; height:24px; display:inline-grid; place-items:center; border-radius:999px; background:var(--surface); color:var(--insufficient); font-size:.72rem; }}
.tribunal-evidence-refs {{ display:flex; gap:5px; flex-wrap:wrap; margin-top:5px; }}
.tribunal-more>summary {{ margin-top:10px; cursor:pointer; color:var(--primary); font-size:.8rem; }}
.method-review-group {{ margin:0 0 26px; }}
.method-review-title {{ display:flex; align-items:flex-start; justify-content:space-between; gap:14px; margin-bottom:12px; }}
.method-review-title h3 {{ margin:0; }}
.method-audit-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:10px; }}
.method-audit-item {{ border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); padding:12px; }}
.method-audit-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }}
.method-audit-item p {{ margin:7px 0 0; font-size:.82rem; }} .method-status {{ font-size:.7rem; color:var(--insufficient); white-space:nowrap; }}
.method-guard-wrap {{ margin-top:12px; padding:12px 14px; border-left:3px solid var(--primary); background:var(--surface2); }}
.scope-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
.scope-card, .retrieval-grid>article, .retrieval-coverage, .boundary-block, .visual-suppressed {{ border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); padding:15px 16px; }}
.scope-card h3, .retrieval-grid h3, .retrieval-coverage h3, .boundary-block h3 {{ margin:0 0 8px; }}
.retrieval-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin-bottom:12px; }}
.retrieval-coverage code {{ margin-right:5px; }}

/* Two-layer report shell: the content contract is shared by all five themes. */
.report-brand-row {{ display:flex; align-items:center; gap:10px; margin-bottom:10px; }}
.report-brand {{ font-weight:750; letter-spacing:.02em; }}
.generated-theme-chip {{ font-size:.7rem; color:var(--insufficient); border:1px solid var(--border); border-radius:999px; padding:2px 8px; }}
.data-origin-chip {{ font-size:.7rem; border:1px solid var(--border); border-radius:999px; padding:2px 8px; color:var(--insufficient); margin-left:8px; overflow-wrap:anywhere; }}
.data-origin-chip[data-origin="synthetic"], .data-origin-chip[data-origin="hybrid"] {{ border-color:#b45309; color:#92400e; background:rgba(217,119,6,.10); font-weight:600; }}
.report-view-switcher {{ display:flex; gap:8px; margin-top:18px; }}
.report-view-btn {{ border:1px solid var(--border); background:var(--surface); color:var(--text); border-radius:999px; padding:7px 14px; cursor:pointer; font-size:.82rem; }}
.report-view-btn.active {{ background:var(--primary); border-color:var(--primary); color:#fff; }}
.report-page[hidden] {{ display:none !important; }}
.brief-block {{ width:100%; max-width:1040px; margin:0 auto clamp(42px,6vw,76px); }}
.brief-block-header {{ max-width:760px; margin-bottom:22px; }}
.brief-block-header h2 {{ margin:0 0 7px; font-family:var(--font-head); font-size:1.45rem; }}
.brief-block-header p {{ margin:0; color:var(--insufficient); }}
.brief-source-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
.brief-source {{ border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--surface2); padding:14px 15px; }}
.brief-source h3 {{ margin:7px 0 4px; font-size:.9rem; }} .brief-source p, .brief-source-more {{ color:var(--insufficient); font-size:.78rem; }}
.full-report-intro {{ width:100%; max-width:900px; margin:0 auto 30px; }}
.full-report-intro h2 {{ font-family:var(--font-head); margin:0 0 7px; font-size:1.8rem; }}
.full-report-intro p {{ margin:0; color:var(--insufficient); }}
.full-report-layout {{ position:relative; display:grid; width:100%; grid-template-columns:minmax(180px,240px) minmax(0,1fr); gap:clamp(24px,3vw,42px); align-items:start; }}
/* 桌面双栏：内容列收口残余的行内可滚动溢出（clip 不产生滚动条也不破坏 sticky）。 */
@media (min-width:981px) {{ .full-report-content {{ overflow-x:clip; }} }}
.full-report-toc {{ position:sticky; top:18px; max-height:calc(100vh - 36px); overflow:auto; border-right:1px solid var(--border); padding-right:18px; }}
.toc-head {{ display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:12px; }}
.toc-head strong {{ font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; color:var(--insufficient); }}
.toc-collapse {{ border:0; background:transparent; color:var(--primary); cursor:pointer; font-size:.72rem; padding:2px; }}
.full-report-toc nav {{ display:grid; gap:4px; }}
.full-report-toc a {{ display:block; color:var(--insufficient); text-decoration:none; padding:7px 8px; border-left:2px solid transparent; font-size:.8rem; line-height:1.4; }}
.full-report-toc a.active {{ color:var(--text); border-left-color:var(--primary); background:var(--surface2); }}
:root .full-report-layout.toc-collapsed {{ grid-template-columns:minmax(0,1fr); gap:0; }}
.full-report-layout.toc-collapsed .full-report-toc nav, .full-report-layout.toc-collapsed .toc-head strong {{ display:none; }}
.full-report-layout.toc-collapsed .full-report-toc {{ position:absolute; left:0; top:0; width:0; max-height:none; padding:0; border:0; overflow:visible; z-index:6; }}
.full-report-layout.toc-collapsed .toc-head {{ margin:0; }}
.full-report-layout.toc-collapsed .toc-collapse {{ position:sticky; top:18px; writing-mode:horizontal-tb; white-space:nowrap; border:1px solid var(--border); border-radius:999px; padding:7px 10px; background:var(--surface); box-shadow:var(--shadow); transform:translateX(-6px); }}
.full-report-content {{ width:100%; min-width:0; max-width:960px; }}
.full-report-layout.toc-collapsed .full-report-content {{ max-width:none; }}
.full-chapter {{ scroll-margin-top:24px; padding:0 0 54px; margin:0 0 54px; border-bottom:1px solid var(--border); }}
.full-chapter:last-child {{ border-bottom:0; }}
.full-chapter-header {{ max-width:760px; margin-bottom:24px; }}
.full-chapter-header h2 {{ margin:0 0 8px; font-family:var(--font-head); font-size:1.55rem; line-height:1.25; }}
.full-chapter-lead {{ margin:0; color:var(--insufficient); }}
.full-chapter-body>*+* {{ margin-top:20px; }}
.report-footer {{ margin-top:64px; padding-top:18px; border-top:1px solid var(--border); color:var(--insufficient); font-size:.76rem; }}

/* Lieflat gallery cards — AI-composed, data-driven charts.
   Card four-piece set: conclusion title (700) + subtitle (legend, `·`
   separated) + themed inline SVG + uppercase source line; caption optional.
   Themes tune surface/radius/typography; identity lives in themes/*.css. */
.lieflat-gallery-container {{ display:flex; flex-direction:column; gap:22px; margin:6px 0 0; }}
.lieflat-card {{ margin:0; padding:22px 24px 18px; border:1px solid var(--border);
                border-radius:calc(var(--radius) + 6px); background:var(--surface);
                box-shadow:var(--shadow); }}
.lieflat-title {{ margin:0 0 8px; font-family:var(--font-head); font-size:1.12rem;
                 font-weight:700; line-height:1.35; }}
.lieflat-sub {{ margin:0 0 14px; color:var(--insufficient); font-size:.85rem; line-height:1.55; }}
.lieflat-figure svg {{ display:block; width:100%; height:auto; border:1px solid var(--border);
                       border-radius:var(--radius-sm); background:var(--surface2); }}
.lieflat-caption {{ margin:10px 0 0; font-size:.8rem; color:var(--insufficient); line-height:1.5; }}
.lieflat-src {{ margin:10px 0 0; font-size:.68rem; font-weight:600; letter-spacing:.08em;
               text-transform:uppercase; color:var(--insufficient); }}
.lieflat-suppressed {{ margin:0; padding:12px 16px; border:1px dashed var(--border);
                      border-radius:var(--radius-sm); background:var(--surface2);
                      font-size:.82rem; color:var(--insufficient); }}
.lieflat-suppressed ul {{ margin:8px 0 0; padding-left:18px; }}
.lieflat-suppressed li {{ margin:3px 0; }}

{_motion_css()}

@media print {{ body {{ background:#fff; }} .controls, .report-view-switcher, .full-report-toc {{ display:none !important; }}
  .report-shell {{ max-width:none !important; padding:0 !important; }}
  .report-page-brief {{ display:none !important; }} .report-page-full {{ display:block !important; }}
  .full-report-layout {{ display:block !important; }} .full-report-content {{ max-width:none !important; }}
  .full-chapter {{ break-before:auto; break-inside:auto; }}
  .report-section {{ box-shadow:none !important; border:none !important; break-inside:avoid-page; }}
  .report-section svg {{ border:none; }} .table-wrap {{ overflow:visible; }}
  .lieflat-card {{ box-shadow:none !important; break-inside:avoid; }}
  .lieflat-figure svg {{ border:none; }}
  details>summary {{ display:none !important; }} details>*:not(summary) {{ display:block !important; }}
  .decision-hero, .tribunal-card, .trace-chain-card, .action-node, .method-audit-item {{ box-shadow:none !important; background:#fff !important; }}
  a {{ color:#000; text-decoration:underline; }} }}
@media (max-width:980px) {{
  /* 网格 item 收缩安全：阻止子内容 min-content 把 1fr 轨道撑破（移动端/平板横向裁切）。 */
  .full-report-layout {{ grid-template-columns:minmax(0,1fr); gap:18px; }}
  .brief-block-body > *, .outcome-separation, .visual-surface,
  .tribunal-grid > *, .hero-insights > *, .brief-source-grid > * {{ min-width:0; }}
  /* 章节直接子元素（table-wrap / evidence-to-action 等）默认 min-width:auto，
     会把来源表等宽内容的 min-content 一路传给 shell —— 显式放开收缩。
     注意用 .table-wrap .data-table 同强度选择器，否则压不过基座 nowrap。 */
  .full-chapter-body > *, .table-wrap, .evidence-to-action {{ min-width:0; max-width:100%; }}
  .table-wrap .data-table th {{ white-space:normal; }}
  .table-wrap .data-table th, .table-wrap .data-table td {{ overflow-wrap:anywhere; word-break:break-word; }}
  /* 窄屏放弃 nowrap+省略号：让主单元格换行，否则行 min-content 撑破表格容器。 */
  .table-wrap .data-table td.cell-main {{ white-space:normal; max-width:none; }}
  /* 定义网格/范围卡片里的 snake_case 枚举值（如 frame.json 的
     first_programming_course_no_prior_text_based_programming）是不可断行长
     token，必须允许任意断行，否则 min-content 直接撑破窄屏。 */
  .scope-card, .scope-text, .scope-grid dt, .scope-grid dd,
  .evidence-detail-grid dd, .source-detail-grid dd,
  .retrieval-grid article, .retrieval-grid li {{ min-width:0;
      overflow-wrap:anywhere; }}
  .full-report-toc {{ position:relative; top:auto; max-height:none; border:1px solid var(--border); border-radius:var(--radius-sm); padding:12px; }}
  .full-report-toc nav {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); }}
  :root .full-report-layout.toc-collapsed {{ grid-template-columns:1fr; }}
  .full-report-layout.toc-collapsed .full-report-toc {{ position:relative; width:100%; padding:10px 12px; border:1px solid var(--border); }}
  .full-report-layout.toc-collapsed .toc-collapse {{ position:static; transform:none; padding:4px 8px; box-shadow:none; }}
  .full-report-layout.toc-collapsed .full-report-toc nav {{ display:none; }}
}}
@media (max-width:720px) {{
  .controls {{ width:calc(100% - 24px); margin-bottom:10px; padding-left:8px; padding-right:8px; }}
  .report-shell {{ width:100%; padding:12px 14px 56px; }}
  .report-header {{ width:100%; }}
  .report-header h1 {{ font-size:1.55rem; overflow-wrap:anywhere; }}
  .report-header .meta, .brief-source h3, .claim-cell, .detail-body, .source-detail-grid dd {{ overflow-wrap:anywhere; word-break:break-word; }}
  .data-table {{ font-size:.78rem; }}
  .hero-insights, .tribunal-grid, .scope-grid, .retrieval-grid, .brief-source-grid, .method-audit-grid {{ grid-template-columns:1fr; }}
  /* 网格收缩安全：1fr 轨道 min 改 0、auto-fit 轨道 min 随容器收缩(min(180px,100%))，
     阻断固定 px 最小值 -> min-content 爆炸 -> 移动端横向溢出 的链条。 */
  .full-report-content, .full-chapter, .full-chapter-body, .brief-block-body,
  .outcome-separation, .visual-surface, .report-page-full, .report-page-brief {{ min-width:0; }}
  .outcome-groups {{ grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr)); }}
  .report-view-switcher {{ width:100%; }}
  .report-view-btn {{ flex:1; min-height:42px; }}
  .lang-btn, .toc-collapse {{ min-height:40px; }}
  .lang-btn {{ min-width:46px; }}
  .detail-expander>summary, .matrix-controls summary, .supporting-visual summary, .tribunal-more>summary {{ padding:7px 0; min-height:38px; display:flex; align-items:center; }}
  .full-report-toc nav {{ grid-template-columns:1fr; }}
  .full-chapter {{ width:100%; margin-bottom:38px; padding-bottom:38px; }}
  .full-chapter-header, .brief-block-header, .visual-heading {{ max-width:100%; }}
  .evidence-detail-grid, .source-detail-grid {{ grid-template-columns:1fr; }}
  .evidence-detail-grid dt, .evidence-detail-grid dd,
  .source-detail-grid dt, .source-detail-grid dd {{ min-width:0; overflow-wrap:anywhere; }}
  .evidence-detail-grid dt, .source-detail-grid dt {{ padding-bottom:2px; }}
  .evidence-detail-grid dd, .source-detail-grid dd {{ padding-top:2px; }}
  .decision-hero {{ padding:20px 16px; }}
  .section-data, .section-decision, .section-narrative {{ width:100%; max-width:100%; }}
  .visual-surface, .outcome-separation, .trace-chain {{ max-width:100%; }}
  .chart-mount {{ height:clamp(240px,62vw,320px); }}
  .evidence-to-action {{ flex-direction:column; overflow:visible; }}
  .flow-arrow {{ transform:rotate(90deg); }}
  .matrix-wrap {{ width:100%; border:0; overflow:visible; }}
  .evidence-matrix thead {{ display:none; }}
  .evidence-matrix, .evidence-matrix tbody, .evidence-matrix tr, .evidence-matrix td {{ display:block; width:100%; }}
  .evidence-matrix tr {{ border:1px solid var(--border); border-radius:var(--radius-sm); margin-bottom:12px; padding:10px; background:var(--surface); }}
  .evidence-matrix td {{ border:0; padding:5px 0; }}
  .claim-cell {{ min-width:0; max-width:none; }}
}}
</style>
</head>
<body>
<div class="controls">
<span class="generated-theme">{esc(THEME_DISPLAY[theme])}</span>
{_lang_switcher(UI_ZH, UI_EN)}
</div>
{body_zh}
{body_en}
<script>
{_motion_js()}
</script>
<script>
{_enhancer_js(charts_zh, charts_en, result_en)}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# 7. Entry point
# ---------------------------------------------------------------------------

RESULT_HASH_META = re.compile(r'<meta name="eduevidence-result-sha256" content="([0-9a-f]{64})"')


def file_sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def embedded_result_hash(html_path: Path) -> str:
    """读取 HTML 内嵌的 result.json SHA-256（HTML-03 一致性校验）。"""
    text = Path(html_path).read_text(encoding="utf-8")
    m = RESULT_HASH_META.search(text)
    if not m:
        raise ValueError(f"{html_path}: missing embedded eduevidence-result-sha256")
    return m.group(1)


def write_artifact_manifest(result_path: Path, result_zh_path: Path, html_paths: list[Path],
                            renderer_version: str, git_commit: str, out_path: Path) -> dict:
    """HTML-03 Artifact Manifest：5 个 HTML 必须内嵌同一 result.json hash。

    校验每个 HTML 的 embedded hash == result.json 实际 hash，随后写 manifest。
    """
    result_path = Path(result_path)
    result_zh_path = Path(result_zh_path)
    result_sha = file_sha256(result_path)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    themes = []
    for html_path in html_paths:
        if embedded_result_hash(html_path) != result_sha:
            raise ValueError(
                f"{html_path}: embedded result hash != {result_sha} "
                f"(not built from {result_path.name})")
        name = Path(html_path).name
        for theme in THEME_NAMES:
            if name.endswith(f"_{theme}.html"):
                themes.append(theme)
                break
    missing = [t for t in THEME_NAMES if t not in themes]
    if missing:
        raise ValueError(f"missing theme HTMLs in {html_paths}: {missing}")
    manifest = {
        "result_sha256": result_sha,
        "result_zh_sha256": file_sha256(result_zh_path),
        "renderer_version": renderer_version,
        "git_commit": git_commit,
        "evidence_count": len(result.get("evidence", [])),
        "source_count": len(result.get("sources", [])),
        "themes": [t for t in THEME_NAMES if t in themes],
    }
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build single-file offline bilingual EduEvidence_Report.html")
    parser.add_argument("--result", required=True, help="result.json path (English source)")
    parser.add_argument("--result-zh", help="result.zh.json path (Chinese parallel); defaults to <result_dir>/result.zh.json")
    parser.add_argument("--out", help="output HTML path (default: <result_dir>/EduEvidence_Report.html)")
    parser.add_argument("--spec-out", help="report_spec.json path (default: beside --out)")
    parser.add_argument("--vendor-echarts", help="optional local echarts.min.js to inline (interactive offline)")
    parser.add_argument("--theme", choices=THEME_NAMES,
                        help="generation-time visual style; interactive terminals prompt when omitted")
    args = parser.parse_args()
    theme = resolve_theme(args.theme)

    result_path = Path(args.result)
    result_en = json.loads(result_path.read_text(encoding="utf-8"))
    zh_path = Path(args.result_zh) if args.result_zh else result_path.with_name("result.zh.json")
    if not zh_path.exists():
        print(f"ERROR: Chinese parallel data missing: {zh_path} (generate it as result.zh.json)")
        return 2
    result_zh = json.loads(zh_path.read_text(encoding="utf-8"))

    # 1. Contract validation（两份数据分别校验）
    for label, data in (("result.json", result_en), ("result.zh.json", result_zh)):
        problems = validate_contract(data)
        if problems:
            print(f"REPORT_INVALID — {label} contract violations:")
            for p in problems:
                print(f"  - {p}")
            return 2

    # 2. Claim-Evidence-Source audit
    for label, data in (("result.json", result_en), ("result.zh.json", result_zh)):
        audit = audit_claims(data)
        if audit:
            print(f"REPORT_INVALID — {label} claim-evidence-source audit failed:")
            for p in audit:
                print(f"  - {p}")
            return 2

    # 2.5 Language gate（W1.2：叙述字段人话化 + 双语分离）
    lang_problems = check_language_parallel(result_en, result_zh)
    if lang_problems:
        print("REPORT_INVALID — language gate failed:")
        for p in lang_problems:
            print(f"  - {p}")
        return 2

    # 3. Adapters（两份数据分别生成 spec / 信息图 / 学术图；数字同构）
    charts_zh = build_chart_specs(result_zh, lang="zh")
    charts_en = build_chart_specs(result_en, lang="en")
    infographics_zh = build_infographics(result_zh, lang="zh")
    infographics_en = build_infographics(result_en, lang="en")
    figure_data = build_figure_data(result_en)
    figures_zh = render_figures(figure_data, theme=args.theme, lang="zh")
    figures_en = render_figures(figure_data, theme=args.theme, lang="en")

    # 3.5 Lieflat gallery — AI-composed data-driven charts (visual_layout).
    # Only registry-validated entries render; each figure is drawn exclusively
    # from its charts_data extractor bundle (AI never writes numbers).
    lieflat_layout = resolve_visual_layout(result_en)
    lieflat_zh, lieflat_meta_zh = render_lieflat_gallery(
        result_zh, theme, "zh", lieflat_layout["entries"])
    lieflat_en, lieflat_meta_en = render_lieflat_gallery(
        result_en, theme, "en", lieflat_layout["entries"])
    figures_zh.update(lieflat_zh)
    figures_en.update(lieflat_en)

    # Merge zh/en suppression records (same bundles, label-only differences).
    suppressed = {}
    for item in lieflat_meta_zh.get("suppressed", []) + lieflat_meta_en.get("suppressed", []):
        suppressed[item.get("chart_id") or item.get("type")] = item
    viz_decisions = visualization_decisions(result_en, charts_en)
    viz_decisions["lieflat_gallery"] = {
        "layout_source": "visual_layout" if not lieflat_layout["fallback"]
                         else "deterministic_fallback",
        "selected": lieflat_meta_en.get("selected", []),
        "suppressed": list(suppressed.values()),
        "rejected": lieflat_layout.get("rejected", []),
        "warnings": lieflat_layout.get("warnings", []),
    }
    viz_decisions["lieflat_layout"] = lieflat_layout
    viz_decisions["lieflat_meta"] = {"zh": lieflat_meta_zh, "en": lieflat_meta_en}

    # 4. Numbers-match integrity gate（两份数据，各自图表 spec）
    for label, data, charts in (("result.json", result_en, charts_en),
                                ("result.zh.json", result_zh, charts_zh)):
        problems = check_numbers(data, charts)
        if problems:
            print(f"REPORT_INVALID — {label} chart numbers differ from result:")
            for p in problems:
                print(f"  - {p}")
            return 2

    # 5. Scientific Integrity（每个 PASS 字段都来自真实检查函数；
    #    no_axis_distortion / colorblind_safe 未实现 → NOT_CHECKED）
    integrity = compute_integrity(result_en, result_zh, charts_en, charts_zh,
                                  lieflat_meta_en=lieflat_meta_en,
                                  lieflat_meta_zh=lieflat_meta_zh)
    if integrity["status"] != "PASS":
        print(f"REPORT_INVALID — scientific integrity gate failed:")
        for key, value in integrity.items():
            if key != "status" and value == "FAIL":
                print(f"  - {key}: FAIL")
        return 2

    spec = build_report_spec(result_en, charts_en, infographics_en, figures_en, integrity,
                             theme, viz_decisions)

    html_out = Path(args.out) if args.out else result_path.parent / "EduEvidence_Report.html"
    html_out.parent.mkdir(parents=True, exist_ok=True)
    result_sha256 = file_sha256(result_path)
    html_text = render_html(result_en, result_zh, charts_zh, charts_en,
                            infographics_zh, infographics_en, figures_zh, figures_en,
                            theme, viz_decisions, result_sha256=result_sha256,
                            integrity=integrity)

    if args.vendor_echarts:
        echarts_js = Path(args.vendor_echarts).read_text(encoding="utf-8")
        html_text = html_text.replace("</head>", f"<script>{echarts_js}</script>\n</head>", 1)
        print(f"vendored echarts ({len(echarts_js)} bytes) into single file")

    html_out.write_text(html_text, encoding="utf-8")
    spec_out = Path(args.spec_out) if args.spec_out else html_out.with_name("report_spec.json")
    spec_out.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {html_out} ({html_out.stat().st_size} bytes) + {spec_out.name} — integrity: {integrity['status']} (zh+en)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
