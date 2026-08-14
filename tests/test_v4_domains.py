"""tests/test_v4_domains.py - v4 领域包机制（EvidenceCore 抽象第一步）。

验收点：
1. 注册表完整：domains/manifest.json 含 education + policy，字段齐全；
2. education 指向真实存在：frame schema / outcome taxonomy（20 token 四类）/
   methodology checklist（15 项）/ golds_dir / references_dir 全部真实存在，
   且 education 不新增任何逻辑路径（只注册、不引入新契约）；
3. policy 契约可校验：合法 policy frame 通过、非法 frame（缺必需字段 /
   越界 outcome token / 混入 education 概念）被拒绝；
4. list_domains 顺序 = 注册表顺序（education, policy）。

只允许创建本文件；其他 tests/ 文件一律只读。
"""

import json
from pathlib import Path

import pytest

from engine.evidencecore import (
    DECISION_STATES,
    PROTOCOL_STEPS,
    REPO_ROOT,
    list_domains,
    load_domain,
    validate_frame,
)

#: 注册表条目必备字段（domains/manifest.json）
REGISTRY_FIELDS = {
    "id", "name", "description", "frame_schema", "outcome_taxonomy",
    "methodology_checklist", "golds_dir", "references_dir",
}

#: schemas/evidence.schema.json outcome_type enum（20 token）
EDUCATION_TOKENS = [
    "knowledge_gain", "concept_understanding", "retention", "transfer",
    "independent_problem_solving", "completion_time", "accuracy",
    "code_quality", "assignment_score", "engagement", "motivation",
    "cognitive_load", "help_seeking", "metacognition", "ai_dependency",
    "over_reliance", "reduced_effort", "reduced_transfer",
    "academic_integrity_risk", "false_confidence",
]

#: engine/pilot.py _OUTCOME_CATEGORY（四类映射，教育域零回归锚点）
EDUCATION_CATEGORY = {
    "knowledge_gain": "learning", "concept_understanding": "learning",
    "retention": "learning", "transfer": "learning",
    "independent_problem_solving": "learning",
    "completion_time": "task_performance", "accuracy": "task_performance",
    "code_quality": "task_performance", "assignment_score": "task_performance",
    "engagement": "process", "motivation": "process",
    "cognitive_load": "process", "help_seeking": "process",
    "metacognition": "process",
    "ai_dependency": "risk", "over_reliance": "risk",
    "reduced_effort": "risk", "reduced_transfer": "risk",
    "academic_integrity_risk": "risk", "false_confidence": "risk",
}

#: skill/agents/method-reviewer.md 15 项审查清单（顺序即原文顺序）
METHODOLOGY_ITEMS = [
    "control_group", "randomization", "pre_test", "post_test",
    "retention_test", "transfer_test", "sample_bias", "self_selection",
    "measurement_validity", "confounders", "instructor_effect",
    "novelty_effect", "tool_version_effect", "ai_usage_policy", "dropout",
]


def _resolve(rel: str) -> Path:
    return REPO_ROOT / rel


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---- 注册表完整 ------------------------------------------------------------

def test_registry_complete_and_fields():
    manifest = _json(_resolve("domains/manifest.json"))
    assert set(manifest) >= {"version", "description", "domains"}
    domains = manifest["domains"]
    assert [d["id"] for d in domains] == ["education", "policy"]
    for entry in domains:
        assert REGISTRY_FIELDS <= set(entry), entry["id"]


def test_list_domains_order():
    # list_domains 顺序 == 注册表顺序
    assert [d["id"] for d in list_domains()] == ["education", "policy"]


def test_load_domain_unknown_raises():
    with pytest.raises(KeyError):
        load_domain("not_a_domain")


def test_domain_independent_constants():
    assert DECISION_STATES == (
        "adopt", "pilot", "reject", "insufficient_evidence")
    assert PROTOCOL_STEPS == (
        "Frame", "Retrieve", "Extract", "Challenge", "Audit",
        "Adjudicate", "Applicability", "Intervene", "Evaluate")


# ---- education：指向现有契约的注册域（零逻辑路径） --------------------------

def test_education_frame_schema_points_to_existing_contract():
    edu = load_domain("education")
    schema_path = _resolve(edu["frame_schema"])
    assert schema_path.is_file()
    assert schema_path.name == "education-frame.schema.json"
    schema = _json(schema_path)
    # 现有契约的硬约束：顶层 additionalProperties=false，required 含
    # question / decision_target
    assert schema["additionalProperties"] is False
    assert "question" in schema["required"]
    assert "decision_target" in schema["required"]


def test_education_golds_and_references_dirs_exist():
    edu = load_domain("education")
    assert _resolve(edu["golds_dir"]).is_dir()       # benchmarks/annotations
    assert _resolve(edu["references_dir"]).is_dir()  # references
    golds = list(_resolve(edu["golds_dir"]).glob("gold-Q*.json"))
    assert golds, "benchmarks/annotations must contain gold-Q*.json files"


def test_education_outcome_taxonomy_20_tokens_four_categories():
    edu = load_domain("education")
    tax = _json(_resolve(edu["outcome_taxonomy"]))
    assert tax["domain"] == "education"
    assert len(tax["tokens"]) == 20
    assert {t["id"] for t in tax["tokens"]} == set(EDUCATION_TOKENS)
    assert set(tax["categories"]) == {
        "learning", "task_performance", "process", "risk"}
    mapping = {t["id"]: t["category"] for t in tax["tokens"]}
    # 与 engine/pilot.py _OUTCOME_CATEGORY 完全一致（零回归锚点）
    assert mapping == EDUCATION_CATEGORY
    # 每个 token 都有中文描述
    for token in tax["tokens"]:
        assert token["description_zh"]


def test_education_methodology_checklist_15_items_from_method_reviewer():
    edu = load_domain("education")
    raw = edu["methodology_checklist"]
    # 注册表用 JSON Pointer 引用 education manifest 中的内联清单
    assert raw.startswith("domains/education/manifest.json#/methodology_checklist")
    edu_manifest = _json(_resolve("domains/education/manifest.json"))
    items = edu_manifest["methodology_checklist"]
    assert len(items) == 15
    assert [i["id"] for i in items] == METHODOLOGY_ITEMS
    for item in items:
        assert item["label_zh"]
        assert item["statuses"] == ["met", "partial", "missing", "not_applicable"]


def test_education_validate_frame_uses_existing_schema_validator():
    # education 的 frame 校验复用现有 schemas/education-frame.schema.json
    frame = {
        "question": "Should first-year CS students use generative AI coding assistants?",
        "decision_target": "evidence_review",
    }
    assert validate_frame("education", frame) == []
    # 顶层 additionalProperties=false：混入 schema 未定义字段被拒绝
    # （learner/course 是 education frame 的合法属性，不能用它们测未知字段）
    bad = dict(frame, mystery_field={"x": 1})
    assert validate_frame("education", bad) != []
    # 缺 required 字段被拒绝
    missing = {"question": "Should we adopt flipped classroom?"}
    assert validate_frame("education", missing) != []


# ---- policy：自带契约领域 ---------------------------------------------------

def test_policy_frame_schema_has_policy_concepts_not_education():
    pol = load_domain("policy")
    schema = _json(_resolve(pol["frame_schema"]))
    props = schema["properties"]
    for key in ("decision_object", "intervention", "population",
                "stakeholders", "outcomes", "context", "scope"):
        assert key in props, f"policy frame must include {key!r}"
    # 刻意不使用 education-frame 的 learner/course 概念
    assert "learner" not in props
    assert "course" not in props
    assert schema["additionalProperties"] is False


def _valid_policy_frame(**over) -> dict:
    frame = {
        "question": "是否应在公立高中全面推行无手机课堂政策？",
        "decision_object": "adopt",
        "intervention": {
            "policy_name": "classroom_phone_ban",
            "policy_type": "regulation",
            "jurisdiction": "public_high_schools",
            "mechanism": "prohibition_with_exceptions",
            "duration": "3_years",
        },
        "population": {
            "target_group": "public_high_school_students",
            "scale": "district_wide",
        },
        "stakeholders": {
            "decision_maker": "school_board",
            "beneficiaries": ["students", "teachers"],
            "affected_parties": ["parents"],
            "implementers": ["school_administrators"],
        },
        "outcomes": {"primary": ["policy_effectiveness", "equity"]},
        "context": {"policy_environment": "provincial_education_budget_constraint"},
        "scope": {"time_range": "2015-2025", "geography": "CN"},
    }
    frame.update(over)
    return frame


def test_policy_valid_frame_passes():
    assert validate_frame("policy", _valid_policy_frame()) == []


def test_policy_invalid_frames_rejected():
    # 缺必需字段 decision_object
    missing = _valid_policy_frame()
    del missing["decision_object"]
    assert validate_frame("policy", missing) != []

    # outcome token 超出 policy 五类 taxonomy
    bad_token = _valid_policy_frame(outcomes={"primary": ["learner_satisfaction"]})
    assert validate_frame("policy", bad_token) != []

    # 混入 education 概念（learner）——additionalProperties=false 拒绝
    bad_learner = _valid_policy_frame(learner={"education_level": "high_school"})
    assert validate_frame("policy", bad_learner) != []

    # 空 question（minLength 5）
    short = _valid_policy_frame(question="abc")
    assert validate_frame("policy", short) != []


def test_policy_outcome_taxonomy_five_tokens_with_chinese():
    pol = load_domain("policy")
    tax = _json(_resolve(pol["outcome_taxonomy"]))
    assert tax["domain"] == "policy"
    assert [t["id"] for t in tax["tokens"]] == [
        "policy_effectiveness", "cost_effectiveness", "equity",
        "feasibility", "implementation_risk",
    ]
    for token in tax["tokens"]:
        assert token["description_zh"]


def test_policy_methodology_checklist_12_items():
    pol = load_domain("policy")
    checklist = _json(_resolve(pol["methodology_checklist"]))
    items = checklist["items"]
    assert len(items) == 12
    assert len({i["id"] for i in items}) == 12
    for item in items:
        assert item["label_zh"]
        assert item["question_zh"]
    assert checklist["statuses"] == ["met", "partial", "missing", "not_applicable"]


def test_policy_references_five_methodology_notes():
    pol = load_domain("policy")
    refs = _resolve(pol["references_dir"])
    md_files = sorted(p.name for p in refs.glob("*.md"))
    assert md_files == [
        "causal-identification.md", "cost-evidence.md", "equity.md",
        "evidence-hierarchy.md", "implementation-evidence.md",
    ]
    for path in refs.glob("*.md"):
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert 30 <= lines <= 60, f"{path.name}: {lines} lines"


def test_policy_golds_dir_optional():
    # policy 暂无金标目录：注册表显式 null，load_domain 不报错
    pol = load_domain("policy")
    assert pol["golds_dir"] is None
