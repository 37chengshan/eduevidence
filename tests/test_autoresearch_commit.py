from types import SimpleNamespace

import pytest

from engine.autoresearch.commit import build_append_only_mutation, commit_staging_bundle


class FakeStore:
    def __init__(self, revision=3, tables=None):
        self.revision = revision
        self.tables = {
            "sources": [],
            "studies": [],
            "findings": [],
            "outcomes": [],
            "claims": [],
            "evidence_links": [],
            "audits": [],
        }
        if tables:
            self.tables.update(tables)
        self.commit_calls = 0
        self.last_mutation = None

    def active_revision(self):
        return self.revision

    def read_table(self, table):
        return [dict(row) for row in self.tables[table]]

    def commit(self, *, run_id, reason, mutation):
        self.commit_calls += 1
        self.last_mutation = mutation
        for table, rows in mutation.upserts.items():
            key = {
                "sources": "source_id",
                "studies": "study_id",
                "findings": "finding_id",
                "outcomes": "outcome_id",
                "claims": "claim_id",
                "evidence_links": "evidence_link_id",
                "audits": "audit_id",
            }[table]
            by_id = {row[key]: row for row in self.tables[table]}
            for row in rows:
                by_id[row[key]] = dict(row)
            self.tables[table] = list(by_id.values())
        self.revision += 1
        return SimpleNamespace(revision=self.revision)


def source(source_id="SRC-1", status="valid"):
    return {
        "source_id": source_id,
        "validation_status": status,
        "origin": "external",
        "source_type": "article",
        "canonical_locator": "https://example.org/a",
        "extensions": {},
    }


def study(study_id="STU-1", source_id="SRC-1"):
    return {"study_id": study_id, "source_ids": [source_id]}


def test_bundle_creates_at_most_one_revision_for_multiple_entity_types():
    store = FakeStore()
    revision = commit_staging_bundle(
        store,
        run_id="R1",
        expected_base_revision=3,
        payload={"sources": [source()], "studies": [study()]},
    )
    assert revision == 4
    assert store.commit_calls == 1
    assert set(store.last_mutation.upserts) == {"sources", "studies"}


def test_identical_duplicate_bundle_is_true_noop():
    existing_source = source()
    store = FakeStore(tables={"sources": [existing_source]})
    revision = commit_staging_bundle(
        store,
        run_id="R1",
        expected_base_revision=3,
        payload={"sources": [dict(existing_source)]},
    )
    assert revision is None
    assert store.commit_calls == 0
    assert store.active_revision() == 3


def test_same_entity_id_with_different_content_fails_append_only():
    existing_source = source()
    store = FakeStore(tables={"sources": [existing_source]})
    changed = dict(existing_source, canonical_locator="https://example.org/other")
    with pytest.raises(ValueError, match="append-only conflict"):
        build_append_only_mutation(store, {"sources": [changed]})


def test_stale_base_revision_fails_closed_before_commit():
    store = FakeStore(revision=4)
    with pytest.raises(RuntimeError, match="STALE_RESEARCH_STATE"):
        commit_staging_bundle(
            store,
            run_id="R1",
            expected_base_revision=3,
            payload={"sources": [source()]},
        )
    assert store.commit_calls == 0


def test_invalid_source_cannot_enter_atomic_autoresearch_path():
    store = FakeStore()
    with pytest.raises(ValueError, match="only valid/accepted_partial"):
        build_append_only_mutation(store, {"sources": [source(status="invalid")]})


def test_new_study_cannot_reference_unvalidated_existing_source():
    store = FakeStore(tables={"sources": [source(status="invalid")]})
    with pytest.raises(ValueError, match="without validated provenance"):
        build_append_only_mutation(store, {"studies": [study()]})
