from __future__ import annotations
import fnmatch
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROTECTED_DEFAULTS = (
    "benchmarks/annotations/**",
    "benchmarks/holdout/**",
    "benchmarks/evaluator/**",
    "schemas/**",
    "references/scientific-invariants.md",
    "scripts/pre_verdict_gate.py",
    "scripts/compute_confidence.py",
    "tests/scientific_invariants/**",
)


@dataclass(frozen=True)
class EvalSnapshot:
    eval_id: str
    hard_gates_passed: bool
    science_score: float
    research_score: float
    robustness: float
    cost: float
    latency: float
    complexity: float
    repeats: int = 1
    noise_floor: float = 0.0


@dataclass
class SkillExperiment:
    experiment_id: str
    session_id: str
    parent_skill_revision: str
    hypothesis: str
    mutation_scope: tuple[str, ...]
    changed_files: list[str] = field(default_factory=list)
    candidate_commit: str | None = None
    baseline_eval_id: str | None = None
    candidate_eval_id: str | None = None
    protected_hash_before: str | None = None
    protected_hash_after: str | None = None
    status: str = "created"
    promotion_reason: str = ""
    complexity_delta: float = 0.0


class ProtectedManifest:
    def __init__(self, patterns=PROTECTED_DEFAULTS):
        self.patterns = tuple(patterns)

    def is_protected(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        return any(
            fnmatch.fnmatch(normalized, pattern)
            or (pattern.endswith("/**") and normalized.startswith(pattern[:-3]))
            for pattern in self.patterns
        )

    def validate_changes(self, changed: list[str]) -> tuple[bool, list[str]]:
        bad = [path for path in changed if self.is_protected(path)]
        return (not bad, bad)

    def hash_tree(self, root: str | Path) -> str:
        root = Path(root)
        digest = hashlib.sha256()
        files = []
        for file in root.rglob("*"):
            if file.is_file() and self.is_protected(file.relative_to(root).as_posix()):
                files.append(file)
        for file in sorted(files):
            rel = file.relative_to(root).as_posix()
            digest.update(rel.encode())
            digest.update(b"\0")
            digest.update(file.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()


def promote(
    baseline: EvalSnapshot,
    candidate: EvalSnapshot,
    *,
    simplicity_tolerance: float = 0.0,
) -> tuple[str, str]:
    if not candidate.hard_gates_passed:
        return "REJECT", "L0 hard gate failed"
    if candidate.science_score < baseline.science_score:
        return "REJECT", "scientific correctness regressed"
    delta = candidate.research_score - baseline.research_score
    noise = max(baseline.noise_floor, candidate.noise_floor)
    if abs(delta) <= noise and candidate.complexity > baseline.complexity + simplicity_tolerance:
        return "REJECT", "within noise floor but more complex"
    if abs(delta) <= noise:
        return "RETEST", "candidate delta is within empirical noise floor"
    regressions = []
    if candidate.robustness < baseline.robustness:
        regressions.append("robustness")
    if delta > noise and not regressions:
        return "KEEP", "material research-quality improvement without core regression"
    return "HUMAN_REVIEW", "Pareto trade-off: " + ",".join(regressions or ["mixed metrics"])


class ExperimentLog:
    HEADER = (
        "experiment_id",
        "parent_revision",
        "candidate_commit",
        "scope",
        "hypothesis",
        "hard_gates",
        "science_score",
        "research_score",
        "robustness",
        "cost",
        "latency",
        "complexity_delta",
        "status",
        "description",
    )

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.tsv = self.root / "results.tsv"
        self.jsonl = self.root / "experiments.jsonl"
        if not self.tsv.exists():
            self.tsv.write_text("\t".join(self.HEADER) + "\n", encoding="utf-8")

    def append(
        self,
        experiment: SkillExperiment,
        *,
        candidate: EvalSnapshot | None = None,
        description: str = "",
    ) -> None:
        row = [
            experiment.experiment_id,
            experiment.parent_skill_revision,
            experiment.candidate_commit or "",
            ",".join(experiment.mutation_scope),
            experiment.hypothesis,
            str(candidate.hard_gates_passed if candidate else ""),
            str(candidate.science_score if candidate else ""),
            str(candidate.research_score if candidate else ""),
            str(candidate.robustness if candidate else ""),
            str(candidate.cost if candidate else ""),
            str(candidate.latency if candidate else ""),
            str(experiment.complexity_delta),
            experiment.status,
            description,
        ]
        with self.tsv.open("a", encoding="utf-8") as handle:
            handle.write("\t".join(value.replace("\t", " ") for value in row) + "\n")
        with self.jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(experiment), ensure_ascii=False, sort_keys=True) + "\n")


class PlateauTracker:
    def __init__(self, limit: int = 5):
        self.limit = limit

    def plateau(self, statuses: list[str]) -> bool:
        valid = [status for status in statuses if status not in {"CRASH", "INVALID", "RETEST"}]
        return len(valid) >= self.limit and all(status != "KEEP" for status in valid[-self.limit :])


@dataclass(frozen=True)
class DailyProfile:
    max_experiments: int = 20
    max_cost_usd: float = 5.0
    max_wall_minutes: int = 180
    mutation_tiers: tuple[str, ...] = ("safe",)
    allow_controlled: bool = False
    promotion: str = "branch_only"

    def validate(self) -> None:
        if not 1 <= self.max_experiments <= 50:
            raise ValueError("daily max_experiments must be 1..50")
        if self.max_cost_usd <= 0 or self.max_wall_minutes <= 0:
            raise ValueError("daily budget must be positive")
        if self.promotion != "branch_only":
            raise ValueError("daily mode is branch_only")
