"""Snapshot-based Shared Research Library.

Reusable research facts (Source/Study/Finding/MethodologyAudit) live in an
immutable library revision model mirroring the Project GraphStore's
crash-safe pattern. Projects import snapshots: a Project never evaluates
directly against library JSONL, and a later library change never silently
changes an existing Project's conclusions — only an explicit import/sync
advances the Project graph.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from engine.contracts import validate_record
from engine.graph_store import GraphStore, GraphMutation, GraphRevision, _atomic_write_text

LIBRARY_TABLES = ("sources", "studies", "findings", "audits")
_TABLE_SCHEMA = {
    "sources": "source",
    "studies": "study",
    "findings": "finding",
    "audits": "methodology-audit",
}
_TABLE_ID_KEY = {
    "sources": "source_id",
    "studies": "study_id",
    "findings": "finding_id",
    "audits": "audit_id",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchLibrary:
    """Shared Research Library under `home/library/`."""

    def __init__(self, home: Path):
        self.home = Path(home).expanduser().resolve()
        self.library_dir = self.home / "library"
        self.revisions_dir = self.library_dir / "revisions"
        self.head_path = self.library_dir / "HEAD"

    @classmethod
    def open(cls, home: Path) -> "ResearchLibrary":
        lib = cls(home)
        lib.revisions_dir.mkdir(parents=True, exist_ok=True)
        if not lib.head_path.is_file():
            _atomic_write_text(lib.head_path, "0")
        return lib

    def active_revision(self) -> int:
        return int(self.head_path.read_text(encoding="utf-8").strip())

    def _revision_dir(self, revision: int) -> Path:
        return self.revisions_dir / f"rev-{revision:06d}"

    def _read_snapshot(self, revision: int) -> dict[str, list[dict]]:
        if revision == 0:
            return {t: [] for t in LIBRARY_TABLES}
        rev_dir = self._revision_dir(revision)
        snapshot: dict[str, list[dict]] = {}
        for table in LIBRARY_TABLES:
            path = rev_dir / f"{table}.jsonl"
            if not path.is_file():
                raise FileNotFoundError(f"library revision {revision} missing {path.name}")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            snapshot[table] = rows
        return snapshot

    def read_table(self, table: str) -> list[dict]:
        if table not in LIBRARY_TABLES:
            raise ValueError(f"unknown library table {table!r}")
        return self._read_snapshot(self.active_revision())[table]

    # ---- mutation --------------------------------------------------------

    def add_verified_bundle(self, *, sources: list[dict], studies: list[dict],
                            findings: list[dict], audits: list[dict]) -> int:
        """Append verified facts as a new immutable library revision.

        Returns the new revision number. Existing revisions are never
        rewritten. Upserts are by entity id within each table.
        """
        before_rev = self.active_revision()
        before = self._read_snapshot(before_rev)
        after = {t: [dict(r) for r in rows] for t, rows in before.items()}
        for table, incoming in (
            ("sources", sources), ("studies", studies),
            ("findings", findings), ("audits", audits),
        ):
            id_key = _TABLE_ID_KEY[table]
            by_id = {r[id_key]: r for r in after[table]}
            for rec in incoming:
                errors = validate_record(_TABLE_SCHEMA[table], rec)
                if errors:
                    raise ValueError(f"library {table} {rec.get(id_key, '?')} invalid: {errors}")
                by_id[rec[id_key]] = dict(rec)
            after[table] = list(by_id.values())

        next_rev = before_rev + 1
        tmp_dir = self.revisions_dir / f".tmp-{next_rev:06d}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        try:
            for table in LIBRARY_TABLES:
                lines = "".join(
                    json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n"
                    for r in after[table]
                )
                (tmp_dir / f"{table}.jsonl").write_text(lines, encoding="utf-8")
            manifest = {
                "revision": next_rev,
                "parent_revision": before_rev,
                "created_at": _now_iso(),
                "extensions": {},
            }
            (tmp_dir / "manifest.json").write_text(
                json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            rev_dir = self._revision_dir(next_rev)
            if rev_dir.exists():
                raise FileExistsError(f"refusing to rewrite library revision {rev_dir}")
            os.replace(tmp_dir, rev_dir)
            _atomic_write_text(self.head_path, str(next_rev))
        except Exception:
            if tmp_dir.exists():
                import shutil
                shutil.rmtree(tmp_dir)
            raise
        return next_rev

    # ---- find ------------------------------------------------------------

    def find_source(self, canonical_locator: str) -> dict | None:
        for src in self.read_table("sources"):
            if src["canonical_locator"] == canonical_locator:
                return src
        return None

    # ---- snapshot import -------------------------------------------------

    def import_snapshot(self, *, project, source_ids: list[str],
                        run_id: str) -> GraphRevision:
        """Import the selected library facts into a Project graph revision.

        Imported entities get `extensions.origin` metadata recording the
        library revision/entity id/content hash, so the Project never depends
        on the live library.
        """
        snapshot = self._read_snapshot(self.active_revision())
        requested_ids = set(source_ids)
        sources = [s for s in snapshot["sources"] if s["source_id"] in requested_ids]
        if len(sources) != len(requested_ids):
            missing = requested_ids - {s["source_id"] for s in sources}
            raise ValueError(f"library has no sources for: {sorted(missing)}")
        src_ids = {s["source_id"] for s in sources}
        # a Study citing multiple sources must import them all (transitive
        # closure) so cross-entity validation never sees a dangling reference
        studies = [s for s in snapshot["studies"] if set(s["source_ids"]) & src_ids]
        for s in studies:
            extra = set(s["source_ids"]) - src_ids
            if extra:
                sources.extend(
                    src for src in snapshot["sources"] if src["source_id"] in extra)
                src_ids.update(extra)
        study_ids = {s["study_id"] for s in studies}
        findings = [f for f in snapshot["findings"] if f["study_id"] in study_ids]
        audits = [a for a in snapshot["audits"] if a["study_id"] in study_ids]

        lib_rev = self.active_revision()

        # origin metadata per table: record library revision + entity id so the
        def stamp(table: str, rec: dict) -> dict:
            out = dict(rec)
            ext = dict(out.get("extensions") or {})
            ext["origin"] = {
                "library_revision": lib_rev,
                "library_entity_id": out[_TABLE_ID_KEY[table]],
                "content_hash": hashlib.sha256(
                    json.dumps(out, sort_keys=True, separators=(",", ":"))
                    .encode("utf-8")).hexdigest(),
                "imported_at": _now_iso(),
            }
            out["extensions"] = ext
            return out
        store = GraphStore.create(project)
        existing_outcomes = {o["outcome_id"] for o in store.read_table("outcomes")}
        outcomes: list[dict] = []
        for f in findings:
            oid = f["outcome_id"]
            if oid in existing_outcomes:
                continue
            existing_outcomes.add(oid)
            outcomes.append({
                "outcome_id": oid,
                "name": f.get("measure", oid),
                "outcome_type": (f.get("extensions") or {}).get(
                    "outcome_type", "learning"),
                "extensions": {
                    "auto_created_from_library_import": True,
                    "library_revision": lib_rev,
                },
            })
        mutation = GraphMutation(
            upserts={
                "sources": [stamp("sources", s) for s in sources],
                "studies": [stamp("studies", s) for s in studies],
                "findings": [stamp("findings", f) for f in findings],
                "audits": [stamp("audits", a) for a in audits],
                "outcomes": outcomes,
            },
            retire_ids={},
        )
        return store.commit(run_id=run_id, reason="library snapshot import", mutation=mutation)

    def diff_project_snapshot(self, *, project, source_ids: list[str]) -> dict:
        """Diff imported facts vs the current library revision.

        Compares every library entity reachable from the selected source_ids
        (sources/studies/findings/audits) against the Project graph's copy
        (ignoring import origin metadata). Returns added/changed/removed
        entity ids so the caller can decide whether an explicit sync is
        warranted.
        """
        snapshot = self._read_snapshot(self.active_revision())
        src_ids = set(source_ids)
        lib_sources = {s["source_id"]: s for s in snapshot["sources"] if s["source_id"] in src_ids}
        lib_studies = {s["study_id"]: s for s in snapshot["studies"]
                       if set(s["source_ids"]) & src_ids}
        lib_findings = {f["finding_id"]: f for f in snapshot["findings"]
                        if f["study_id"] in lib_studies}
        lib_audits = {a["audit_id"]: a for a in snapshot["audits"]
                      if a["study_id"] in lib_studies}
        lib_entities: dict[str, tuple[str, dict]] = {}
        for table, ents in (("sources", lib_sources), ("studies", lib_studies),
                            ("findings", lib_findings), ("audits", lib_audits)):
            for eid, rec in ents.items():
                lib_entities[eid] = (table, rec)

        store = GraphStore.create(project)
        proj_by_table = {
            t: {r[_TABLE_ID_KEY[t]]: r for r in store.read_table(t)}
            for t in LIBRARY_TABLES
        }
        diff: dict = {"added": [], "changed": [], "removed": []}
        for eid, (table, lib_rec) in lib_entities.items():
            proj_rec = proj_by_table[table].get(eid)
            if proj_rec is None:
                diff["added"].append(eid)
                continue
            lib_content = {k: v for k, v in lib_rec.items() if k != "extensions"}
            proj_content = {k: v for k, v in proj_rec.items() if k != "extensions"}
            if lib_content != proj_content:
                diff["changed"].append(eid)
        for table in LIBRARY_TABLES:
            for eid, rec in proj_by_table[table].items():
                if eid in lib_entities:
                    continue
                # only entities imported FROM this library may be reported
                # removed; project-local entities are never "removed" by a
                # library diff
                origin = ((rec.get("extensions") or {}).get("origin") or {})
                if origin.get("library_revision") is not None:
                    diff["removed"].append(eid)
        return diff
