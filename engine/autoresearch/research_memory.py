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

    def load_iterations(self, gap_id: str | None = None) -> list[dict[str, Any]]:
        if not self.iterations_path.exists():
            return []
        rows = [
            json.loads(line)
            for line in self.iterations_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return [r for r in rows if gap_id is None or r.get("gap_id") == gap_id]
