from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from .contracts import NegativeSearchRecord, ResearchIteration


class ResearchMemory:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.iterations_path = self.root / "research-iterations.jsonl"
        self.negative_path = self.root / "negative-searches.jsonl"

    @staticmethod
    def _append(path: Path, record: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def append_iteration(self, iteration: ResearchIteration) -> None:
        iteration.validate()
        self._append(self.iterations_path, iteration.as_dict())

    def append_negative_search(self, record: NegativeSearchRecord) -> None:
        record.validate()
        self._append(self.negative_path, record.__dict__)

    def load_iterations(
        self,
        gap_id: str | None = None,
        *,
        gap_lineage_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Load iteration history, preferring stable lineage across revisions.

        Legacy rows without `gap_lineage_key` remain queryable by `gap_id`.
        When a lineage key is supplied, new keyed rows match by lineage and old
        unkeyed rows may additionally match the supplied gap_id for migration.
        """
        if not self.iterations_path.exists():
            return []
        rows = [
            json.loads(line)
            for line in self.iterations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if gap_lineage_key is not None:
            return [
                row for row in rows
                if row.get("gap_lineage_key") == gap_lineage_key
                or (
                    not row.get("gap_lineage_key")
                    and gap_id is not None
                    and row.get("gap_id") == gap_id
                )
            ]
        if gap_id is not None:
            return [row for row in rows if row.get("gap_id") == gap_id]
        return rows
