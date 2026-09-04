"""HTML-03：Artifact Manifest 与 5 HTML 同源一致性。

5 个主题 HTML 必须内嵌同一 result.json SHA-256（与 manifest 一致）；manifest
记录 result / result_zh 哈希、渲染器版本、git commit、evidence/source 计数与
主题列表。校验 manifest 与磁盘文件实际一致。
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

import build_report as br

ROOT = Path(__file__).resolve().parent.parent
DEMO = ROOT / "examples" / "ai-coding-assistant"
RESULT = DEMO / "result.json"
RESULT_ZH = DEMO / "result.zh.json"

HASH_META = re.compile(r'<meta name="eduevidence-result-sha256" content="([0-9a-f]{64})"')


def _sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture()
def built_themes(tmp_path, monkeypatch):
    """用最终示例数据构建 5 个主题 HTML 到 tmp 目录。"""
    paths = {}
    for theme in br.THEME_NAMES:
        out = tmp_path / f"EduEvidence_Report_{theme}.html"
        argv = [
            "build_report.py",
            "--result", str(RESULT),
            "--result-zh", str(RESULT_ZH),
            "--out", str(out),
            "--spec-out", str(tmp_path / f"report_spec_{theme}.json"),
            "--theme", theme,
        ]
        monkeypatch.setattr(sys, "argv", argv)
        assert br.main() == 0
        paths[theme] = out
    return paths


def test_five_htmls_embed_same_result_hash(built_themes):
    """5 个 HTML 内嵌 result hash 相同且等于数据文件实际哈希。"""
    expected = _sha(RESULT)
    hashes = {theme: br.embedded_result_hash(path) for theme, path in built_themes.items()}
    assert len(set(hashes.values())) == 1
    assert hashes["claude"] == expected


def test_manifest_matches_actual_artifacts(built_themes, tmp_path):
    """manifest 字段与实际文件一致：哈希、计数、主题列表、渲染器版本。"""
    manifest_path = tmp_path / "artifact_manifest.json"
    manifest = br.write_artifact_manifest(
        RESULT, RESULT_ZH, list(built_themes.values()),
        renderer_version=br.RENDERER_VERSION, git_commit="test-commit",
        out_path=manifest_path)

    assert manifest["result_sha256"] == _sha(RESULT)
    assert manifest["result_zh_sha256"] == _sha(RESULT_ZH)
    assert manifest["renderer_version"] == br.RENDERER_VERSION
    assert manifest["git_commit"] == "test-commit"
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert manifest["evidence_count"] == len(result["evidence"])
    assert manifest["source_count"] == len(result["sources"])
    assert manifest["evidence_count"] > 0 and manifest["source_count"] > 0
    assert manifest["themes"] == list(br.THEME_NAMES)

    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert on_disk == manifest
    for theme, path in built_themes.items():
        assert br.embedded_result_hash(path) == manifest["result_sha256"]


def test_manifest_rejects_html_from_other_data(tmp_path, monkeypatch):
    """不同版本 result.json 构建的 HTML 必须被 manifest 校验拒绝。"""
    other_result = tmp_path / "result-other.json"
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    data["decision"]["decision_rationale"] = data["decision"]["decision_rationale"] + " (variant)"
    other_result.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    out = tmp_path / "EduEvidence_Report_claude.html"
    argv = [
        "build_report.py",
        "--result", str(other_result),
        "--result-zh", str(RESULT_ZH),
        "--out", str(out),
        "--spec-out", str(tmp_path / "report_spec.json"),
        "--theme", "claude",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    assert br.main() == 0
    assert _sha(other_result) != _sha(RESULT)

    with pytest.raises(ValueError, match="embedded result hash"):
        br.write_artifact_manifest(
            RESULT, RESULT_ZH, [out],
            renderer_version=br.RENDERER_VERSION, git_commit="test-commit",
            out_path=tmp_path / "manifest.json")
