"""Immutable revision snapshots with atomic HEAD commits.

A commit either fully lands (revision dir + HEAD + project mirror) or leaves
the prior active revision intact. A crash after the immutable revision
directory exists but before HEAD changes leaves only an inactive orphan
revision, which readers ignore. `graph/HEAD` is authoritative; the
`project.json.graph_revision` mirror is repaired/flagged on divergence.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.graph_validate import validate_graph
from engine.project import ProjectWorkspace

GRAPH_TABLES = (
    "sources", "studies", "findings", "outcomes",
    "claims", "evidence_links", "audits",
)

# graph table name -> entity id field
_TABLE_ID_KEY = {
    "sources": "source_id",
    "studies": "study_id",
    "findings": "finding_id",
    "outcomes": "outcome_id",
    "claims": "claim_id",
    "evidence_links": "evidence_link_id",
    "audits": "audit_id",
}

# graph table name -> schema name
_TABLE_SCHEMA = {
    "sources": "source",
    "studies": "study",
    "findings": "finding",
    "outcomes": "outcome",
    "claims": "claim",
    "evidence_links": "evidence-link",
    "audits": "methodology-audit",
}

_REV_FORMAT = "rev-{:06d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GraphMutation:
    upserts: dict[str, list[dict]] = field(default_factory=dict)
    retire_ids: dict[str, list[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphRevision:
    revision: int
    parent_revision: int
    run_id: str
    reason: str
    touched_entities: dict[str, list[str]]
    before_hash: str
    after_hash: str
    created_at: str


def _table_hash(rows: list[dict], id_key: str) -> str:
    """Deterministic canonical hash of one table (sorted by entity id)."""
    ordered = sorted(rows, key=lambda r: r[id_key])
    h = hashlib.sha256()
    for row in ordered:
        h.update(json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


class GraphStore:
    """Versioned evidence graph for one Project."""

    def __init__(self, project: ProjectWorkspace):
        self.project = project
        self.graph_dir = project.path / "graph"
        self.revisions_dir = self.graph_dir / "revisions"
        self.head_path = self.graph_dir / "HEAD"

    @classmethod
    def create(cls, project: ProjectWorkspace) -> "GraphStore":
        store = cls(project)
        store.revisions_dir.mkdir(parents=True, exist_ok=True)
        if not store.head_path.is_file():
            _atomic_write_text(store.head_path, "0")
        return store

    # ---- reads -----------------------------------------------------------

    def active_revision(self) -> int:
        return int(self.head_path.read_text(encoding="utf-8").strip())

    def _revision_dir(self, revision: int) -> Path:
        return self.revisions_dir / _REV_FORMAT.format(revision)

    def _read_snapshot(self, revision: int) -> dict[str, list[dict]]:
        """Read the complete active snapshot; empty tables for revision 0."""
        if revision == 0:
            return {table: [] for table in GRAPH_TABLES}
        rev_dir = self._revision_dir(revision)
        snapshot: dict[str, list[dict]] = {}
        for table in GRAPH_TABLES:
            path = rev_dir / f"{table}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(
                    f"revision {revision} is missing table file {path.name}; "
                    f"graph is corrupt"
                )
            rows = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(json.loads(line))
            snapshot[table] = rows
        return snapshot

    def read_table(self, table: str) -> list[dict]:
        if table not in GRAPH_TABLES:
            raise ValueError(f"unknown graph table {table!r}")
        return self._read_snapshot(self.active_revision())[table]

    def get(self, table: str, entity_id: str) -> dict | None:
        id_key = _TABLE_ID_KEY[table]
        for row in self.read_table(table):
            if row[id_key] == entity_id:
                return row
        return None

    def canonical_hash(self, revision: int | None = None) -> str:
        """Deterministic canonical hash of a snapshot (default: active)."""
        snapshot = self._read_snapshot(
            self.active_revision() if revision is None else revision
        )
        return self._hash_snapshot(snapshot)

    @staticmethod
    def _hash_snapshot(snapshot: dict[str, list[dict]]) -> str:
        h = hashlib.sha256()
        for table in GRAPH_TABLES:
            h.update(_table_hash(snapshot.get(table, []), _TABLE_ID_KEY[table]).encode("utf-8"))
            h.update(b"\n")
        return h.hexdigest()

    @classmethod
    def empty_graph_hash(cls) -> str:
        return cls._hash_snapshot({t: [] for t in GRAPH_TABLES})

    # ---- validation ------------------------------------------------------

    def validate(self) -> list[str]:
        """Cross-entity integrity + HEAD/mirror consistency of active state."""
        problems: list[str] = []
        try:
            snapshot = self._read_snapshot(self.active_revision())
        except FileNotFoundError as exc:
            return [str(exc)]
        problems.extend(validate_graph(snapshot))
        mirror = self.project.current_revision()
        head = self.active_revision()
        if mirror != head:
            problems.append(
                f"project.json graph_revision ({mirror}) diverges from "
                f"graph/HEAD ({head}); repair with repair_head_mirror()"
            )
        return problems

    def repair_head_mirror(self) -> None:
        """HEAD is authoritative; mirror the project manifest to it."""
        self.project.update_manifest(graph_revision=self.active_revision())

    # ---- commit ----------------------------------------------------------

    def commit(self, *, run_id: str, reason: str,
               mutation: GraphMutation) -> GraphRevision:
        before_rev = self.active_revision()
        before_snapshot = self._read_snapshot(before_rev)
        next_rev = before_rev + 1

        # 1. apply mutation in memory
        after_snapshot = self._apply(before_snapshot, mutation)

        # 2. per-entity schema validation
        for table, rows in after_snapshot.items():
            schema = _TABLE_SCHEMA[table]
            id_key = _TABLE_ID_KEY[table]
            for row in rows:
                errors = validate_record(schema, row)
                if errors:
                    raise ValueError(
                        f"commit rejected: {table} {row.get(id_key, '?')} "
                        f"fails schema: {'; '.join(errors)}"
                    )

        # 3. cross-entity validation
        problems = validate_graph(after_snapshot)
        if problems:
            raise ValueError(
                "commit rejected: cross-entity integrity:\n- " + "\n- ".join(problems)
            )

        before_hash = self._hash_snapshot(before_snapshot)
        after_hash = self._hash_snapshot(after_snapshot)

        # 4. write the complete next snapshot to a temp revision dir
        tmp_dir = self.revisions_dir / f".tmp-{run_id}"
        if tmp_dir.exists():
            import shutil
            shutil.rmtree(tmp_dir)
        tmp_dir.mkdir(parents=True)
        try:
            for table in GRAPH_TABLES:
                _write_jsonl(tmp_dir / f"{table}.jsonl", after_snapshot[table])
            touched = {
                table: [row[_TABLE_ID_KEY[table]] for row in mutation.upserts.get(table, [])]
                + list(mutation.retire_ids.get(table, []))
                for table in GRAPH_TABLES
                if mutation.upserts.get(table) or mutation.retire_ids.get(table)
            }
            manifest = {
                "revision": next_rev,
                "parent_revision": before_rev,
                "run_id": run_id,
                "reason": reason,
                "touched_entities": touched,
                "before_hash": before_hash,
                "after_hash": after_hash,
                "created_at": _now_iso(),
                "extensions": {},
            }
            manifest_errors = validate_record("graph-revision", manifest)
            if manifest_errors:
                raise ValueError(
                    f"commit rejected: revision manifest invalid: "
                    f"{'; '.join(manifest_errors)}")
            _write_json(tmp_dir / "manifest.json", manifest)

            # 5. atomically promote: .tmp-<run> -> rev-00000N
            rev_dir = self._revision_dir(next_rev)
            if rev_dir.exists():
                # an orphan occupying the next revision number (not reached
                # by HEAD) is inactive: remove it and retake the number
                if self.active_revision() == before_rev:
                    import shutil
                    shutil.rmtree(rev_dir)
                else:
                    raise FileExistsError(
                        f"refusing to rewrite existing revision directory {rev_dir}"
                    )
            os.replace(tmp_dir, rev_dir)


            # 6. atomically switch HEAD
            _atomic_write_text(self.head_path, str(next_rev))

            # 7. atomically mirror into project.json; on failure roll HEAD
            # back so the caller never sees a failure for a landed commit
            try:
                self.project.update_manifest(graph_revision=next_rev)
            except Exception:
                _atomic_write_text(self.head_path, str(before_rev))
                raise
        except Exception:
            # never leave a half-promoted state behind
            if tmp_dir.exists():
                import shutil
                shutil.rmtree(tmp_dir)
            raise

        return GraphRevision(
            revision=next_rev,
            parent_revision=before_rev,
            run_id=run_id,
            reason=reason,
            touched_entities=touched,
            before_hash=before_hash,
            after_hash=after_hash,
            created_at=manifest["created_at"],
        )

    @staticmethod
    def _apply(snapshot: dict[str, list[dict]],
               mutation: GraphMutation) -> dict[str, list[dict]]:
        after: dict[str, list[dict]] = {
            table: [dict(row) for row in rows] for table, rows in snapshot.items()
        }
        for table, upserts in mutation.upserts.items():
            if table not in GRAPH_TABLES:
                raise ValueError(f"unknown graph table {table!r}")
            id_key = _TABLE_ID_KEY[table]
            by_id = {row[id_key]: row for row in after[table]}
            for row in upserts:
                if id_key not in row:
                    raise ValueError(f"{table} upsert missing {id_key}: {row!r}")
                by_id[row[id_key]] = dict(row)
            after[table] = list(by_id.values())
        for table, retire_ids in mutation.retire_ids.items():
            if table not in GRAPH_TABLES:
                raise ValueError(f"unknown graph table {table!r}")
            id_key = _TABLE_ID_KEY[table]
            retired = set(retire_ids)
            after[table] = [row for row in after[table] if row[id_key] not in retired]
        return after


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows
    )
    path.write_text(lines, encoding="utf-8")


def _write_json(path: Path, record: dict) -> None:
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
