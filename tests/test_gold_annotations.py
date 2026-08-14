"""Gold annotation consistency checks (benchmarks/annotations)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from benchmark import OUTCOME_SET

ROOT = Path(__file__).resolve().parent.parent
ACTIONS = {"adopt", "pilot", "reject", "insufficient_evidence"}


def load_golds():
    golds = {}
    for path in sorted((ROOT / "benchmarks" / "annotations").glob("gold-*.json")):
        g = json.loads(path.read_text(encoding="utf-8"))
        golds[g["id"]] = g
    return golds


def test_all_30_golds_present_and_wellformed():
    golds = load_golds()
    assert len(golds) == 30
    for qid, g in golds.items():
        for field in ("key_claims", "key_supporting_sources", "known_contradictions",
                      "correct_outcome_types", "allowed_scope",
                      "known_methodological_limitations", "expected_decision_range"):
            assert field in g, f"{qid}: missing {field}"
        assert g["key_claims"] and g["key_supporting_sources"], f"{qid}: empty core"
        for o in g["correct_outcome_types"]:
            assert o in OUTCOME_SET, f"{qid}: outcome {o} not in taxonomy"
        for a in g["expected_decision_range"]:
            assert a in ACTIONS, f"{qid}: action {a} invalid"
        assert g["allowed_scope"].strip(), f"{qid}: empty scope"


def test_gold_ids_match_questions():
    questions = {json.loads(l)["id"] for l in
                 (ROOT / "benchmarks" / "questions.jsonl").read_text(encoding="utf-8").splitlines()
                 if l.strip()}
    assert set(load_golds()) == questions
