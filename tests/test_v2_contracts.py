from engine.contracts import validate_record, schema_path, SCHEMA_DIR


def _project(**over):
    base = {
        "project_id": "PRJ-20260812T140000Z-abc12345-deadbeef",
        "title": "Flipped classroom",
        "domain": "education",
        "question": "Should we use flipped classroom?",
        "research_mode": "evidence_review",
        "decision_target": "teaching_decision",
        "created_at": "2026-08-12T00:00:00+00:00",
        "updated_at": "2026-08-12T00:00:00+00:00",
        "engine_version": "2.0.0",
        "schema_version": "2.0",
        "graph_revision": 0,
        "status": "active",
    }
    base.update(over)
    return base


def _run(**over):
    base = {
        "run_id": "RUN-20260812T140000Z-deadbeef",
        "project_id": "PRJ-20260812T140000Z-abc12345-deadbeef",
        "purpose": "initial evidence review",
        "started_at": "2026-08-12T00:00:00+00:00",
        "status": "running",
        "graph_revision_before": 0,
        "graph_revision_after": None,
        "capabilities": ["literature_search"],
        "execution_backend": "host_native_subagents",
        "policy_versions": {
            "source_validation": "2026-08-12.v2",
            "methodology": "2026-08-12.v2",
            "confidence": "2026-08-12.v3",
        },
    }
    base.update(over)
    return base


def _intent(**over):
    base = {
        "decision_target": "teaching_decision",
        "wants_existing_evidence": True,
        "wants_study_design": False,
        "has_user_data": False,
        "wants_data_analysis": False,
        "wants_decision_update": False,
    }
    base.update(over)
    return base


# ---- schema registry -----------------------------------------------------

def test_schema_dir_points_at_v2_schemas():
    assert SCHEMA_DIR.is_dir()
    assert (SCHEMA_DIR / "project.schema.json").is_file()
    assert (SCHEMA_DIR / "run.schema.json").is_file()
    assert (SCHEMA_DIR / "research-intent.schema.json").is_file()


def test_schema_path_resolves_known_and_unknown():
    assert schema_path("project").name == "project.schema.json"
    try:
        schema_path("nope")
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


# ---- project -------------------------------------------------------------

def test_project_accepts_valid_record():
    assert validate_record("project", _project()) == []


def test_project_rejects_unknown_research_mode():
    errors = validate_record("project", _project(research_mode="universal_research"))
    assert errors
    assert any("research_mode" in e for e in errors)


def test_project_rejects_unknown_decision_target():
    errors = validate_record("project", _project(decision_target="everything"))
    assert errors


def test_project_rejects_unknown_status():
    errors = validate_record("project", _project(status="deleted"))
    assert errors


def test_project_rejects_missing_required_fields():
    rec = _project()
    del rec["question"]
    errors = validate_record("project", rec)
    assert errors
    assert any("question" in e for e in errors)


def test_project_rejects_extra_top_level_fields():
    errors = validate_record("project", _project(fabricated_field="x"))
    assert errors


def test_project_accepts_extensions():
    assert validate_record("project", _project(extensions={"note": "ok"})) == []


def test_project_rejects_negative_graph_revision():
    errors = validate_record("project", _project(graph_revision=-1))
    assert errors


# ---- run -----------------------------------------------------------------

def test_run_accepts_valid_record():
    assert validate_record("run", _run()) == []


def test_run_rejects_unknown_status():
    errors = validate_record("run", _run(status="paused"))
    assert errors


def test_run_rejects_missing_capabilities():
    rec = _run()
    del rec["capabilities"]
    errors = validate_record("run", rec)
    assert errors


def test_run_rejects_null_revision_before():
    errors = validate_record("run", _run(graph_revision_before=None))
    assert errors


# ---- research intent -----------------------------------------------------

def test_intent_accepts_valid_record():
    assert validate_record("research-intent", _intent()) == []


def test_intent_rejects_unknown_decision_target():
    errors = validate_record("research-intent", _intent(decision_target="study_only"))
    assert errors
    assert any("decision_target" in e for e in errors)


def test_intent_rejects_non_boolean_flags():
    errors = validate_record("research-intent", _intent(wants_existing_evidence="yes"))
    assert errors
