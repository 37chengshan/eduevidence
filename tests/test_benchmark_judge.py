"""Tests for scripts/benchmark_judge.py (LLM judge evaluator).

The CliDriver (omp) is mocked via monkeypatch/FakeCliDriver; no real model
calls happen. Covers: rubric prompt construction, tolerant 0-3 score parsing
(JSON ints, "2/3" fractions, prose fallback, clamping), judge-evaluation.json
schema + per_baseline means, side-by-side report vs heuristic metrics, and
failure tolerance (a failing attempt never interrupts the run).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest

import benchmark_judge as bj

QUESTION = {
    "id": "Q01",
    "question": "使用AI编程助手完成作业的大学生，其代码正确率是否显著高于对照学生？",
}
GOLD = {
    "id": "Q01",
    "key_claims": ["AI编程助手可提高新手正确率"],
    "key_supporting_sources": ["Peng et al. (2023) Copilot on LeetCode 受控实验"],
    "known_contradictions": ["部分研究未发现对复杂任务的正确率有显著差异"],
    "correct_outcome_types": ["accuracy"],
    "allowed_scope": "仅限编程作业任务正确率，不扩展到长期编程能力",
    "expected_decision_range": ["pilot"],
}
RESPONSE = "Copilot 显著提高当次任务正确率（Peng et al. 2023），但迁移测试无显著差异，建议试点。"

DEFAULT_OUTPUT = (
    '{"citation_support": 2, "outcome_correctness": 3, "scope_calibration": 2, '
    '"contradiction_handling": 1, "decision_calibration": 3, '
    '"rationale": "引用了关键证据，但矛盾证据处理不足。"}'
)


class FakeCliDriver:
    """Duck-typed stand-in for benchmark_v3.CliDriver (monkeypatched in)."""

    name = "cli"
    model = "deepseek-v4-flash"
    temperature = 0.0

    def __init__(self, outputs=None, fail_indices=(), **kwargs):
        self.outputs = list(outputs) if outputs else []
        self.fail_indices = set(fail_indices)
        self.calls = []

    def available(self):
        return True

    def call(self, prompt, **kwargs):
        self.calls.append(prompt)
        idx = len(self.calls) - 1
        if idx in self.fail_indices:
            raise RuntimeError("omp failed rc=1: boom")
        if self.outputs:
            text = self.outputs[min(idx, len(self.outputs) - 1)]
        else:
            text = DEFAULT_OUTPUT
        return text, {"prompt_tokens": 90, "completion_tokens": 40,
                      "latency_s": 0.4}


def make_run_dir(tmp_path, n_completed=2):
    """Build run_dir (manifest + artifacts + evaluation.json), annotations, questions."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    attempts = []
    for i in range(n_completed):
        aid = f"Q01-B3_eduevidence_single-a{i + 1}"
        art = run_dir / f"{aid}.response.json"
        art.write_text(json.dumps({"attempt_id": aid, "prompt": "p",
                                   "response": RESPONSE, "usage": {}},
                                  ensure_ascii=False), encoding="utf-8")
        attempts.append({"attempt_id": aid, "question_id": "Q01",
                         "baseline": "B3_eduevidence_single", "attempt": i + 1,
                         "status": "completed", "artifacts": [art.name]})
    # a manifest-failed attempt must be skipped (no response to judge)
    attempts.append({"attempt_id": "Q02-B3_eduevidence_single-a1", "question_id": "Q02",
                     "baseline": "B3_eduevidence_single", "attempt": 1,
                     "status": "failed", "artifacts": []})
    (run_dir / "manifest.json").write_text(
        json.dumps({"run_id": "run-test", "attempts": attempts}, ensure_ascii=False),
        encoding="utf-8")

    heur = {"run_id": "run-test", "per_baseline": {"B3_eduevidence_single": {
        "metrics": {m: {"mean": 0.5, "ci95": 0.1, "n": n_completed}
                    for m in ("outcome_separation_accuracy", "decision_calibration",
                              "contradiction_recall", "contradiction_precision",
                              "citation_support_recall", "scope_calibration")},
        "n": n_completed, "total_cost_usd": 0.0}}}
    (run_dir / "evaluation.json").write_text(json.dumps(heur, ensure_ascii=False),
                                             encoding="utf-8")

    ann = tmp_path / "annotations"
    ann.mkdir()
    (ann / "gold-Q01.json").write_text(json.dumps(GOLD, ensure_ascii=False),
                                       encoding="utf-8")

    qfile = tmp_path / "questions.jsonl"
    qfile.write_text(json.dumps(QUESTION, ensure_ascii=False) + "\n", encoding="utf-8")
    return run_dir, ann, qfile


def test_build_judge_prompt_contains_question_gold_response_and_dims():
    prompt = bj.build_judge_prompt(QUESTION, GOLD, RESPONSE)
    assert QUESTION["question"] in prompt
    assert RESPONSE in prompt
    assert "Peng et al. (2023)" in prompt          # gold key_supporting_sources
    assert "AI编程助手可提高新手正确率" in prompt      # gold key_claims
    assert "accuracy" in prompt                     # gold correct_outcome_types
    assert "pilot" in prompt                        # gold expected_decision_range
    for dim in bj.JUDGE_DIMS:
        assert dim in prompt
    assert "0-3" in prompt
    assert "rationale" in prompt
    assert "## 模型回答" in prompt and "## 参考答案要点（gold）" in prompt


def test_parse_judge_output_json_ints():
    out = bj.parse_judge_output(
        '{"citation_support": 2, "outcome_correctness": 3, "scope_calibration": 2, '
        '"contradiction_handling": 1, "decision_calibration": 3, '
        '"rationale": "整体尚可，矛盾证据处理偏弱。"}')
    assert out is not None
    assert out["scores"] == {"citation_support": 2.0, "outcome_correctness": 3.0,
                             "scope_calibration": 2.0, "contradiction_handling": 1.0,
                             "decision_calibration": 3.0}
    assert out["rationale"] == "整体尚可，矛盾证据处理偏弱。"


def test_parse_judge_output_fraction_and_prose():
    # model outputs "2/3" style strings inside JSON
    out = bj.parse_judge_output(
        '{"citation_support": "2/3", "outcome_correctness": "3", '
        '"scope_calibration": "2", "contradiction_handling": "1", '
        '"decision_calibration": "2.5", "rationale": "ok"}')
    assert out["scores"]["citation_support"] == 2.0
    assert out["scores"]["outcome_correctness"] == 3.0
    assert out["scores"]["decision_calibration"] == 2.5

    # prose without JSON at all -> per-dimension line fallback
    prose = (
        "citation_support: 2/3\n"
        "outcome_correctness = 2\n"
        "scope_calibration: 3\n"
        "contradiction_handling: 1\n"
        "decision_calibration: 2\n"
        "理由：总体合格，边界清晰。"
    )
    out = bj.parse_judge_output(prose)
    assert out is not None
    assert out["scores"] == {"citation_support": 2.0, "outcome_correctness": 2.0,
                             "scope_calibration": 3.0, "contradiction_handling": 1.0,
                             "decision_calibration": 2.0}
    assert out["rationale"] == "总体合格，边界清晰。"

    # partial JSON + prose hybrid: JSON fills some dims, prose fills the rest
    hybrid = '{"citation_support": 2} 其余：scope_calibration: 3, outcome_correctness: 2'
    out = bj.parse_judge_output(hybrid)
    assert out["scores"]["citation_support"] == 2.0
    assert out["scores"]["scope_calibration"] == 3.0


def test_parse_judge_output_clamp_and_garbage():
    out = bj.parse_judge_output(
        '{"citation_support": 5, "outcome_correctness": -1, "scope_calibration": "10/3", '
        '"contradiction_handling": 0, "decision_calibration": 3}')
    assert out["scores"]["citation_support"] == 3.0    # clamped down
    assert out["scores"]["outcome_correctness"] == 0.0  # clamped up
    assert out["scores"]["scope_calibration"] == 3.0    # 10/3 -> 3.33 -> 3.0
    assert bj.parse_judge_output("") is None
    assert bj.parse_judge_output("完全不知道评什么") is None
    assert bj.parse_judge_output("no dims here 42") is None


def test_run_judge_writes_json_and_means(tmp_path):
    run_dir, ann, qfile = make_run_dir(tmp_path)
    driver = FakeCliDriver()
    out = tmp_path / "judge-evaluation.json"
    summary = bj.run_judge(run_dir=run_dir, annotations_dir=ann,
                           questions=[QUESTION], out_path=out,
                           driver=driver, limit=10)
    assert summary["summary"] == {"attempts_total": 2, "completed": 2,
                                  "failed": 0, "skipped": 0}
    assert len(driver.calls) == 2
    assert QUESTION["question"] in driver.calls[0]   # rubric prompt was built

    pb = summary["per_baseline"]["B3_eduevidence_single"]
    assert pb["n"] == 2
    assert pb["judge"]["citation_support"]["mean"] == 2.0
    assert pb["judge"]["outcome_correctness"]["mean"] == 3.0
    assert pb["judge"]["decision_calibration"]["mean"] == 3.0
    assert pb["judge"]["contradiction_handling"]["min"] == 1.0

    row = summary["per_attempt"][0]
    assert set(row) >= {"attempt_id", "question_id", "baseline", "attempt",
                        "status", "judge", "usage"}
    assert set(row["judge"]) >= set(bj.JUDGE_DIMS) | {"rationale", "method"}
    assert row["usage"]["prompt_tokens"] == 90
    assert len(summary["per_attempt"]) == 2  # manifest-failed Q02 attempt skipped

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["judge"]["model"] == "deepseek-v4-flash"
    assert "independence_note" in data["judge"]
    assert data["heuristic_evaluation"] == str(run_dir / "evaluation.json")


def test_run_judge_failure_tolerance(tmp_path):
    run_dir, ann, qfile = make_run_dir(tmp_path)
    # first driver call raises (simulated omp failure)
    summary = bj.run_judge(run_dir=run_dir, annotations_dir=ann,
                           questions=[QUESTION],
                           out_path=tmp_path / "j.json",
                           driver=FakeCliDriver(fail_indices={0}), limit=10)
    rows = {r["attempt_id"]: r for r in summary["per_attempt"]}
    assert rows["Q01-B3_eduevidence_single-a1"]["status"] == "failed"
    assert "omp failed" in rows["Q01-B3_eduevidence_single-a1"]["error"]
    assert rows["Q01-B3_eduevidence_single-a2"]["status"] == "completed"
    assert summary["summary"]["failed"] == 1
    assert summary["per_baseline"]["B3_eduevidence_single"]["n"] == 1

    # unparseable judge output also marks the attempt failed, run continues
    summary = bj.run_judge(run_dir=run_dir, annotations_dir=ann,
                           questions=[QUESTION],
                           out_path=tmp_path / "j2.json",
                           driver=FakeCliDriver(outputs=["not a score at all"]),
                           limit=10)
    assert summary["summary"]["completed"] == 0
    assert summary["summary"]["failed"] == 2
    assert "unparseable" in summary["per_attempt"][0]["error"]


def test_limit_skips_remaining_attempts(tmp_path):
    run_dir, ann, qfile = make_run_dir(tmp_path)
    driver = FakeCliDriver()
    summary = bj.run_judge(run_dir=run_dir, annotations_dir=ann,
                           questions=[QUESTION],
                           out_path=tmp_path / "j.json",
                           driver=driver, limit=1)
    assert len(driver.calls) == 1
    assert summary["summary"]["completed"] == 1
    assert summary["summary"]["skipped"] == 1
    assert summary["per_attempt"][1]["status"] == "skipped"
    assert summary["per_baseline"]["B3_eduevidence_single"]["n"] == 1


def test_report_side_by_side_vs_heuristic(tmp_path):
    run_dir, ann, qfile = make_run_dir(tmp_path)
    eval_data = bj.run_judge(run_dir=run_dir, annotations_dir=ann,
                             questions=[QUESTION],
                             out_path=tmp_path / "judge-evaluation.json",
                             driver=FakeCliDriver(), limit=10)
    heuristic_data = json.loads((run_dir / "evaluation.json").read_text(encoding="utf-8"))
    md = bj.render_report(eval_data, heuristic_data, tmp_path / "judge-report.md")
    assert "# LLM Judge 评估报告" in md
    assert "deepseek-v4-flash" in md                      # judge model labelled
    assert "独立性受限" in md                              # independence limitation
    assert "B3_eduevidence_single" in md
    for metric in ("citation_support_recall", "outcome_separation_accuracy",
                   "contradiction_recall", "scope_calibration",
                   "decision_calibration"):
        assert metric in md                               # heuristic side present
    assert "3.000" in md                                  # judge mean (0-3)
    assert "0.500" in md                                  # heuristic mean (0-1)
    assert "judged=2" in md
    assert (tmp_path / "judge-report.md").is_file()


def test_cli_run_and_report_end_to_end(tmp_path, monkeypatch):
    run_dir, ann, qfile = make_run_dir(tmp_path)
    monkeypatch.setattr(bj, "CliDriver", FakeCliDriver)
    out = tmp_path / "judge-evaluation.json"
    rc = bj.main(["run", "--run", str(run_dir), "--out", str(out),
                  "--questions", str(qfile), "--annotations", str(ann),
                  "--limit", "5"])
    assert rc == 0
    assert out.is_file()

    md = tmp_path / "judge-report.md"
    rc2 = bj.main(["report", "--out", str(md)])
    assert rc2 == 0
    text = md.read_text(encoding="utf-8")
    assert "deepseek-v4-flash" in text
    assert "独立性受限" in text
    assert "| B3_eduevidence_single |" in text


def test_main_errors_without_run_dir(tmp_path):
    # missing run dir -> prints an error and returns rc=2, does not raise
    rc = bj.main(["run", "--run", str(tmp_path / "missing"),
                  "--out", str(tmp_path / "x.json")])
    assert rc == 2
