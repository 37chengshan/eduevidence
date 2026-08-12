"""Tests for 双语同构门（6.3）：compare_parallel_result 只允许文本字段不同；
ID / enum / URL / 数字 / 数组结构必须一致；作为 integrity gate 阻止构建。
"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RESULT = ROOT / "examples" / "ai-coding-assistant" / "result.json"
RESULT_ZH = ROOT / "examples" / "ai-coding-assistant" / "result.zh.json"

import build_report as br  # noqa: E402


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parallel():
    return _load("examples/ai-coding-assistant/result.json"), \
        _load("examples/ai-coding-assistant/result.zh.json")


def test_demo_data_is_isomorphic(parallel):
    """示例数据必须通过同构检查（数字一致、双语同构）。"""
    en, zh = parallel
    assert br.compare_parallel_result(en, zh) == []


def test_id_mismatch_detected(parallel):
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["evidence"][0]["evidence_id"] = "E-999"
    problems = br.compare_parallel_result(en, bad)
    assert any("evidence_id" in p for p in problems)


def test_claim_id_mismatch_detected(parallel):
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["claims"][0]["claim_id"] = "C-999"
    problems = br.compare_parallel_result(en, bad)
    assert any("claim_id" in p for p in problems)


def test_enum_mismatch_detected(parallel):
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["evidence"][0]["direction"] = "nonsense"
    problems = br.compare_parallel_result(en, bad)
    assert any("direction" in p for p in problems)


def test_url_mismatch_detected(parallel):
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["sources"][0]["canonical_url"] = "https://evil.example"
    problems = br.compare_parallel_result(en, bad)
    assert any("canonical_url" in p for p in problems)


def test_number_mismatch_detected(parallel):
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["evidence"][0]["quality_score"] = 99.0
    problems = br.compare_parallel_result(en, bad)
    assert any("quality_score" in p for p in problems)


def test_array_structure_mismatch_detected(parallel):
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["claims"] = bad["claims"][:3]
    problems = br.compare_parallel_result(en, bad)
    assert any("length" in p for p in problems)


def test_text_differences_allowed(parallel):
    """自由文本（决策理由、结论句等）允许双语不同。"""
    en, zh = parallel
    bad = copy.deepcopy(zh)
    bad["decision"]["decision_rationale"] = "这是中文改写"
    bad["claims"][0]["claim"] = "这是中文结论"
    assert br.compare_parallel_result(en, bad) == []


def test_build_fails_on_id_mismatch(tmp_path, monkeypatch, capsys):
    """制造 ID 不一致 → 报告构建必须失败（REPORT_INVALID）。"""
    en = _load("examples/ai-coding-assistant/result.json")
    bad_zh = copy.deepcopy(_load("examples/ai-coding-assistant/result.zh.json"))
    bad_zh["sources"][0]["source_id"] = "S-DIFFERENT"
    en_path = tmp_path / "result.json"
    zh_path = tmp_path / "result.zh.json"
    en_path.write_text(json.dumps(en, ensure_ascii=False), encoding="utf-8")
    zh_path.write_text(json.dumps(bad_zh, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "out.html"
    monkeypatch.setattr(sys, "argv", ["build_report.py", "--result", str(en_path),
                                      "--result-zh", str(zh_path), "--out", str(out)])
    assert br.main() == 2
    assert not out.exists()
    assert "REPORT_INVALID" in capsys.readouterr().out


def test_build_fails_on_number_mismatch(tmp_path, monkeypatch):
    """制造 outcome 计数不一致 → 构建失败。"""
    bad_en = copy.deepcopy(_load("examples/ai-coding-assistant/result.json"))
    bad_en["outcomes"][0]["positive_count"] = 42
    zh = _load("examples/ai-coding-assistant/result.zh.json")
    en_path = tmp_path / "result.json"
    zh_path = tmp_path / "result.zh.json"
    en_path.write_text(json.dumps(bad_en, ensure_ascii=False), encoding="utf-8")
    zh_path.write_text(json.dumps(zh, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["build_report.py", "--result", str(en_path),
                                      "--result-zh", str(zh_path),
                                      "--out", str(tmp_path / "out.html")])
    assert br.main() == 2
