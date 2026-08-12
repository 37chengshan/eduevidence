from pathlib import Path

import pytest

from engine.paths import resolve_home
from engine.ids import new_project_id, new_run_id, new_local_id


def test_explicit_home_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUEVIDENCE_HOME", "/ignored")
    assert resolve_home(tmp_path) == tmp_path.resolve()


def test_env_home_is_used_when_explicit_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("EDUEVIDENCE_HOME", str(tmp_path))
    assert resolve_home() == tmp_path.resolve()


def test_default_home_is_eduevidence_dir(monkeypatch):
    monkeypatch.delenv("EDUEVIDENCE_HOME", raising=False)
    assert resolve_home().name == ".eduevidence"


def test_project_id_is_unique_even_for_same_question():
    from datetime import datetime, timezone
    now = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)
    a = new_project_id("Should we use flipped classroom?", now=now, existing=set())
    b = new_project_id("  Should we use flipped classroom?  ", now=now, existing={a})
    assert a.startswith("PRJ-")
    assert b.startswith("PRJ-")
    assert a != b


def test_project_id_stable_prefix_and_creation_identity():
    from datetime import datetime, timezone
    now = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)
    pid = new_project_id("flipped classroom", now=now)
    # creation identity embeds UTC creation time, not a question hash
    assert "20260812" in pid


def test_run_id_unique_and_prefixed():
    from datetime import datetime, timezone
    now = datetime(2026, 8, 12, 14, 0, tzinfo=timezone.utc)
    a = new_run_id(now=now)
    b = new_run_id(now=now)
    assert a.startswith("RUN-")
    assert a != b


def test_local_id_respects_existing_and_prefix():
    existing = {"STU-aaaa1111"}
    a = new_local_id("STU", existing=existing)
    b = new_local_id("STU", existing=existing | {a})
    assert a.startswith("STU-")
    assert a not in existing
    assert a != b


def test_local_id_rejects_unknown_prefixes():
    # prefixes are frozen in the design; unknown ones are a programming error
    with pytest.raises(ValueError):
        new_local_id("XXX", existing=set())
