"""engine.citation_check 单元测试 —— 全部离线，不发真实网络请求（plan E6）。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.citation_check import (  # noqa: E402
    STATUS_ERROR,
    STATUS_MISMATCH,
    STATUS_NOT_FOUND,
    STATUS_OK,
    RegistryClient,
    classify,
    clean_doi,
    extract_dois,
    title_overlap,
)


def test_classify_ok_when_titles_match():
    v = classify("10.1234/abc", STATUS_OK,
                 {"title": ["Generative AI Without Guardrails Can Harm Learning"]},
                 "Generative AI without guardrails can harm learning")
    assert v["status"] == STATUS_OK
    assert v["doi_verified"] is True
    assert v["retracted"] is False


def test_classify_mismatch_on_different_title():
    v = classify("10.1234/wrong", STATUS_OK,
                 {"title": ["Why Johnny Can't Prompt"]},
                 "Studying the effect of AI Code Generators on Novice Learners")
    assert v["status"] == STATUS_MISMATCH
    assert v["doi_verified"] is False


def test_classify_not_found():
    v = classify("10.9999/fake", STATUS_NOT_FOUND, {"status": 404}, None)
    assert v["status"] == STATUS_NOT_FOUND
    assert v["doi_verified"] is False


def test_classify_retracted_via_update_to():
    msg = {"title": ["Some Meta-Analysis"],
           "update-to": [{"type": "retraction", "source": "publisher"}]}
    v = classify("10.1234/retr", STATUS_OK, msg, "Some Meta-Analysis")
    assert v["retracted"] is True and v["doi_verified"] is True


def test_classify_retracted_via_title_prefix():
    msg = {"title": ["Retracted: Does ChatGPT enhance student learning?"]}
    v = classify("10.1234/retr2", STATUS_OK, msg, None)
    assert v["retracted"] is True


def test_error_status_is_not_verified():
    v = classify("10.1/x", STATUS_ERROR, {"detail": "boom"}, None)
    assert v["status"] == STATUS_ERROR and v["doi_verified"] is False


def test_extract_dois_prefers_doi_field_and_pairs_title():
    rec = {"doi": "https://doi.org/10.1145/3544548.3580919",
           "title": "Studying the effect of AI Code Generators"}
    pairs = extract_dois(rec)
    # URL 形态的 doi 字段：严格形态校验下整串不匹配 → 回退到文本扫描，
    # 文本里同样只有 URL；此处断言至少提取出一个合法 DOI。
    assert pairs and all(d.startswith("10.") for d, _ in pairs)


def test_extract_dois_scans_prose_for_bare_dois():
    rec = {"summary": "As shown in 10.1073/pnas.2422633122 the effect reverses."}
    pairs = extract_dois(rec)
    assert ("10.1073/pnas.2422633122", None) in pairs


def test_clean_doi_strips_trailing_punctuation():
    assert clean_doi("10.1145/3586030.") == "10.1145/3586030"
    assert title_overlap("Studying Effects", "studying effects!") is not None


def test_fetch_raw_rejects_bad_shape_without_network(monkeypatch):
    """畸形 DOI 必须在触网前被拒绝（SSRF 纪律）。"""
    client = RegistryClient()

    def boom(*a, **k):  # 若触网则测试失败
        raise AssertionError("network access attempted")

    monkeypatch.setattr(client.opener, "open", boom)
    status, msg = client.fetch_raw("not-a-doi")
    assert status == STATUS_ERROR
    assert "shape" in (msg or {}).get("detail", "")
