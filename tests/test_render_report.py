"""Tests for scripts/render_report.py — Research & Decision Pack rendering."""
import json
from pathlib import Path

from render_report import render_frame, render_pack, render_verdict

ROOT = Path(__file__).resolve().parent.parent


def _load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _load_evidence(rel: str):
    return [json.loads(line) for line in
            (ROOT / rel).read_text(encoding="utf-8").splitlines() if line.strip()]


def test_render_pack_contains_all_sections():
    frame = _load("examples/ai-coding-assistant/frame.json")
    evidence = _load_evidence("examples/ai-coding-assistant/evidence.jsonl")
    verdict = _load("examples/ai-coding-assistant/verdict.json")
    methodology = _load("examples/ai-coding-assistant/methodology.json")
    intervention = _load("examples/ai-coding-assistant/intervention.json")
    evaluation = _load("examples/ai-coding-assistant/evaluation.json")

    md = render_pack(frame, evidence, methodology, verdict, intervention, evaluation)
    for section in ("01 Executive Decision", "02 Education Research Frame",
                    "03 Evidence Summary", "04 Evidence Matrix",
                    "05 Methodology Audit", "06 Conflict Analysis",
                    "07 Evidence Tribunal", "08 Applicability",
                    "09 Teaching Intervention", "10 Evaluation Plan",
                    "11 Claim-Evidence Trace", "12 Sources"):
        assert section in md
    assert "PILOT" in md or "pilot" in md


def test_render_verdict_shows_can_cannot():
    verdict = _load("examples/ai-coding-assistant/verdict.json")
    md = render_verdict(verdict)
    assert "可以主张" in md
    assert "不能主张" in md
    assert "PILOT" in md


def test_render_frame_shows_question():
    frame = _load("examples/ai-coding-assistant/frame.json")
    md = render_frame(frame)
    assert frame["question"] in md


def test_empty_pack_graceful():
    md = render_pack(None, [], None, None, None, None)
    for section in ("01 Executive Decision", "02 Education Research Frame",
                    "04 Evidence Matrix", "11 Claim-Evidence Trace",
                    "12 Sources"):
        assert section in md
    assert "_no verdict provided_" in md
