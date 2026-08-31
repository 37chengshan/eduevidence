from engine.research_service import ResearchService


def test_research_service_persists_immutable_artifact_and_replayable_events(tmp_path):
    service = ResearchService(tmp_path)
    project = service.create_project(question="Can a policy reduce congestion?", title="policy", domain="policy")
    run = service.start_run(project.project_id, purpose="evidence review", capabilities=["literature_search"])
    first = service.submit_artifact(project.project_id, run_id=run["run_id"], artifact_type="search-plan", content=b"{}")
    second = service.submit_artifact(project.project_id, run_id=run["run_id"], artifact_type="search-plan", content=b"{}")
    assert first["sha256"] == second["sha256"]
    assert len(service.artifacts(project.project_id)) == 1
    events = service.events(project.project_id)
    assert [event["type"] for event in events] == ["project_created", "run_started", "artifact_submitted", "artifact_submitted"]
