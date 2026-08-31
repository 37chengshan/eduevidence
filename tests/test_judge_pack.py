from engine.judge_pack import export_judge_pack
from engine.project import ProjectWorkspace


def test_judge_pack_lists_missing_categories_instead_of_inventing_evidence(tmp_path):
    project = ProjectWorkspace.create(tmp_path, question="q?", title="t", research_mode="evidence_review")
    manifest = export_judge_pack(project, tmp_path / "pack")
    assert "project_manifest" in {row["name"] for row in manifest["copied_files"]}
    assert "decisions" in manifest["missing_categories"]
