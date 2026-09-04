from engine.autoresearch.projection import research_loop_projection
from engine.autoevolve.projection import skill_evolution_projection


def test_research_projection_has_ranked_gaps():
    projection = research_loop_projection(
        decision={"recommended_action": "pilot", "graph_revision": 2},
        gaps=[{
            "gap_id": "G",
            "gap_type": "missing_transfer",
            "priority": "high",
            "derived_from_graph_revision": 2,
        }],
        iterations=[],
        revision=2,
    )
    assert projection["gap_priorities"][0]["gap_id"] == "G"
    assert projection["graph_revision"] == 2


def test_skill_projection_is_branch_only():
    projection = skill_evolution_projection(
        baseline=None,
        best=None,
        experiments=[{"status": "REJECT"}] * 5,
    )
    assert projection["plateau"]
    assert projection["promotion"] == "branch_only"
