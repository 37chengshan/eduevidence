# -*- coding: utf-8 -*-
"""语言门禁测试（W1.2）：叙述字段人话化 + 双语分离 + 无结构碎语。

正例：好人话叙述必须 PASS；反例：证据 ID 堆砌 / schema 键 / null 残留 /
中英夹生 / 交叉污染 / 未翻译平行版本 必须逐条 FAIL。
"""
import copy
import pytest

from build_report import check_language_parallel


def make_docs(rationale_zh, rationale_en, **kw):
    base = {
        "decision": {
            "recommended_action": "pilot",
            "confidence": "Moderate",
            "decision_rationale": rationale_zh,
            "what_can_be_claimed": [],
            "what_cannot_be_claimed": [],
            "missing_evidence": [],
            "exceeds_evidence_boundary": [],
        },
        "applicability": {"suitable_for": "试点班级", "not_suitable_for": "全校"},
        "methodology_reviews": [{"target": "overall", "verdict": "CONCERN",
                                 "audit_items": {}, "limitations": ["无显著效果"]}],
        "intervention": {"decision": "pilot", "ai_usage_policy": "提示而非答案"},
        "evaluation": {"retention_test": "学期后 2-4 周延迟复测"},
        "evidence": [],
        "claims": [],
    }
    en = copy.deepcopy(base)
    zh = copy.deepcopy(base)
    en["decision"]["decision_rationale"] = rationale_en
    en["applicability"] = {"suitable_for": "pilot class", "not_suitable_for": "whole school"}
    en["intervention"] = {"decision": "pilot", "ai_usage_policy": "prompts, not answers"}
    en["evaluation"] = {"retention_test": "delayed retest 2-4 weeks after term"}
    en["methodology_reviews"] = [{"target": "overall", "verdict": "CONCERN",
                                  "audit_items": {}, "limitations": ["no significant effect"]}]
    for k, v in kw.items():
        if k == "en_only":
            en.update(v)
        elif k == "zh_only":
            zh.update(v)
        else:
            setattr(zh, k, v)
    return en, zh


GOOD_ZH = "证据不支持无护栏放开，也不支持一刀切禁止：正效应均来自 AI 在场时的任务表现，而学习测量显示受损或无益。"
GOOD_EN = "The evidence supports neither unguarded use nor an outright ban: gains are task performance with AI present, while learning measures show harm or no benefit."


def test_clean_human_rationale_passes():
    en, zh = make_docs(GOOD_ZH, GOOD_EN)
    assert check_language_parallel(en, zh) == []


def test_evidence_id_pile_fails():
    bad = GOOD_ZH + "（E-001/E-004 均为任务表现）"
    en, zh = make_docs(bad, GOOD_EN)
    problems = check_language_parallel(en, zh)
    assert any("evidence-ID" in p for p in problems)


def test_schema_key_fails():
    bad = GOOD_ZH + "（overall_risk=high）"
    en, zh = make_docs(bad, GOOD_EN)
    assert any("schema key" in p for p in check_language_parallel(en, zh))


def test_null_residue_fails():
    bad = GOOD_ZH + "保持力 null"
    en, zh = make_docs(bad, GOOD_EN)
    assert any("null" in p for p in check_language_parallel(en, zh))


def test_english_code_in_zh_fails():
    bad = GOOD_ZH + "方法学 CONCERN"
    en, zh = make_docs(bad, GOOD_EN)
    assert any("English audit code" in p for p in check_language_parallel(en, zh))


def test_zh_missing_cjk_fails():
    en, zh = make_docs("This is English text in the zh file.", GOOD_EN)
    assert any("缺少中文" in p for p in check_language_parallel(en, zh))


def test_parallel_not_translated_fails():
    en, zh = make_docs(GOOD_EN, GOOD_EN)
    assert any("完全相等" in p for p in check_language_parallel(en, zh))


def test_en_contains_chinese_fails():
    en, zh = make_docs(GOOD_ZH, GOOD_ZH)
    assert any("交叉污染" in p for p in check_language_parallel(en, zh))


def test_short_rationale_fails():
    en, zh = make_docs("太短。", GOOD_EN)
    assert any("过短" in p for p in check_language_parallel(en, zh))


def test_lenient_evidence_id_allowed_but_zh_clean():
    # 详细页（evaluation 等宽松档）允许 E-xxx 交叉引用，但 zh 必须仍是中文叙述
    en, zh = make_docs(GOOD_ZH, GOOD_EN)
    zh["evaluation"]["retention_test"] = "延迟复测（E-005 无显著结果）"
    en["evaluation"]["retention_test"] = "delayed retest (E-005 null)"
    problems = check_language_parallel(en, zh)
    assert all("E-xxx" not in p for p in problems)
