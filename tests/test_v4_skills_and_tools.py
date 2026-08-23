"""Unit tests for EduEvidence v4 Universal Agent skills, search, stats & dashboard tools."""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_sub_skills_structure_and_frontmatter():
    skills_dir = ROOT / "skill" / "sub-skills"
    assert skills_dir.exists() and skills_dir.is_dir()
    expected_sub_skills = [
        "research-planning",
        "literature-review",
        "aihot-trend-analysis",
        "evidence-extraction",
        "contradiction-analysis",
        "methodology-audit",
        "evidence-review",
        "gap-analysis",
        "ethics-review",
        "study-design",
        "data-analysis",
        "report-generation",
    ]
    for name in expected_sub_skills:
        skill_file = skills_dir / name / "SKILL.md"
        assert skill_file.exists(), f"Missing sub-skill {name}/SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert content.startswith("---"), f"{name} missing YAML frontmatter start"
        assert f"name: {name}" in content, f"{name} frontmatter missing name"
        assert "description:" in content, f"{name} frontmatter missing description"


def test_references_completeness():
    ref_dir = ROOT / "references"
    expected = [
        "social_science_pitfalls.md",
        "wwc_standards.md",
        "grade_framework.md",
        "effect_size_formulas.md",
    ]
    for r in expected:
        f = ref_dir / r
        assert f.exists(), f"Missing reference: {r}"
        assert len(f.read_text(encoding="utf-8")) > 200


def test_skill_linter_passes():
    from skill_lint import lint_skill
    errors = lint_skill()
    assert errors == [], f"Skill lint errors: {errors}"


def test_benchmark_routing_accuracy():
    from benchmark_routing import run_benchmark
    res = run_benchmark()
    assert res["depth_accuracy"] == 1.0
    assert res["domain_accuracy"] == 1.0


def test_effect_calculator_accuracy():
    from effect_calculator import compute_hedges_g
    res = compute_hedges_g(mean1=78.5, sd1=10.2, n1=90, mean2=72.1, sd2=11.0, n2=90)
    assert res["status"] == "success"
    assert 0.58 <= res["hedges_g"] <= 0.62
    assert 0.58 <= res["cohens_d"] <= 0.62
    assert res["sample_size_total"] == 180
    assert res["ci_95"][0] < res["hedges_g"] < res["ci_95"][1]
    assert res["p_value"] < 0.01


def test_did_regression_on_synthetic_data(tmp_path):
    from did_regression import run_did_analysis
    csv_file = tmp_path / "trial_data.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "treat", "post", "score"])
        # Control Pre (mean ~70)
        for i in range(25):
            writer.writerow([f"C_pre_{i}", 0, 0, 70.0 + (i % 5) - 2])
        # Control Post (mean ~72, trend +2)
        for i in range(25):
            writer.writerow([f"C_post_{i}", 0, 1, 72.0 + (i % 5) - 2])
        # Treatment Pre (mean ~70)
        for i in range(25):
            writer.writerow([f"T_pre_{i}", 1, 0, 70.0 + (i % 5) - 2])
        # Treatment Post (mean ~80, trend +2, treatment effect +8)
        for i in range(25):
            writer.writerow([f"T_post_{i}", 1, 1, 80.0 + (i % 5) - 2])

    res = run_did_analysis(str(csv_file))
    assert res["status"] == "success"
    assert res["sample_size"] == 100
    assert 7.8 <= res["did_coefficient"] <= 8.2
    assert res["p_value"] < 0.001
    # QED/DID can never meet WWC standards without reservations
    assert res["wwc_baseline_rating"] != "Meets Standards Without Reservations"


def test_search_router_status_and_zero_config_providers():
    from retrieval.search import search_router, SearchHit
    status = search_router.get_provider_status()
    assert len(status) >= 5
    provider_names = {s["provider"] for s in status}
    assert "openalex" in provider_names
    assert "semanticscholar" in provider_names
    assert "crossref" in provider_names
    assert "aihot" in provider_names
    assert "agentsearch" in provider_names

    hit = SearchHit(
        title="Test Study",
        url="https://doi.org/10.1234/test",
        snippet="An empirical study",
        provider="openalex",
        doi="10.1234/test",
        year=2025,
        citation_count=42,
        is_academic=True,
    )
    d = hit.to_dict()
    assert d["title"] == "Test Study"
    assert d["is_academic"] is True


def test_dashboard_scanner_and_token_cost_stats():
    from dashboard_server import scan_local_projects, get_aggregate_stats
    projects = scan_local_projects()
    assert len(projects) >= 1
    stats = get_aggregate_stats(projects)
    assert stats["total_projects"] == len(projects)
    assert stats["total_tokens"] > 0
    assert stats["total_prompt_tokens"] > 0
    assert "DeepSeek-V3 / R1" in stats["aggregate_costs"]
    assert stats["aggregate_costs"]["DeepSeek-V3 / R1"]["cost_cny"] > 0
