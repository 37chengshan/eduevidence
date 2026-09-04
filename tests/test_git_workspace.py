import subprocess
from engine.autoevolve.git_workspace import GitWorkspace


def git(cwd, *args):
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def test_workspace_branch_restore_and_commit(tmp_path):
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "a@b.c"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True)
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, check=True, capture_output=True)

    workspace = GitWorkspace.create(tmp_path, "test")
    (workspace.path / "a.txt").write_text("b", encoding="utf-8")
    assert workspace.changed_files() == ["a.txt"]
    workspace.restore()
    assert (workspace.path / "a.txt").read_text(encoding="utf-8") == "a"

    (workspace.path / "a.txt").write_text("c", encoding="utf-8")
    sha = workspace.commit("experiment: E1")
    assert len(sha) == 40
    assert git(workspace.path, "branch", "--show-current") == "autoresearch/test"
