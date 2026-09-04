from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

PROTECTED_DEFAULTS = (
    "autoevolve/protected.manifest.yaml",
    "benchmarks/annotations/**",
    "benchmarks/holdout/**",
    "benchmarks/evaluator/**",
    "schemas/**",
    "references/scientific-invariants.md",
    "scripts/pre_verdict_gate.py",
    "scripts/compute_confidence.py",
    "scripts/check_autoresearch_invariants.py",
    "engine/graph_store.py",
    "engine/study_design.py",
    "engine/autoevolve/**",
    ".github/workflows/autoresearch-gates.yml",
)
SAFE_DEFAULTS = (
    "skill/workflows/**",
    "skill/agents/**",
    "skill/sub-skills/**",
    "retrieval/**",
    "references/presentation/**",
)
CONTROLLED_DEFAULTS = (
    "engine/semantics.py",
    "engine/gaps.py",
    "scripts/complexity_gate.py",
    "engine/orchestration.py",
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
    dev_passed: bool = False
    holdout_passed: bool = False
    adversarial_passed: bool = False
    holdout_isolation_verified: bool = False
    eval_suite_hash: str = ""


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


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    normalized = path.replace("\\", "/")
    return any(
        fnmatch.fnmatch(normalized, pattern)
        or (pattern.endswith("/**") and normalized.startswith(pattern[:-3]))
        for pattern in patterns
    )


def _parse_manifest(path: Path) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Parse the intentionally tiny manifest subset without a YAML dependency."""
    protected: list[str] = []
    safe: list[str] = []
    controlled: list[str] = []
    section = ""
    subsection = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1]
            subsection = ""
            continue
        if section == "mutable" and indent == 2 and stripped.endswith(":"):
            subsection = stripped[:-1]
            continue
        if stripped.startswith("- "):
            value = stripped[2:].strip().strip('"\'')
            if section == "protected":
                protected.append(value)
            elif section == "mutable" and subsection == "safe":
                safe.append(value)
            elif section == "mutable" and subsection == "controlled":
                controlled.append(value)
    if not protected or not safe:
        raise ValueError(f"invalid autoresearch manifest: {path}")
    return tuple(protected), tuple(safe), tuple(controlled)


class ProtectedManifest:
    def __init__(
        self,
        patterns=PROTECTED_DEFAULTS,
        *,
        safe_patterns=SAFE_DEFAULTS,
        controlled_patterns=CONTROLLED_DEFAULTS,
    ):
        self.patterns = tuple(patterns)
        self.safe_patterns = tuple(safe_patterns)
        self.controlled_patterns = tuple(controlled_patterns)

    @classmethod
    def from_repo(cls, root: str | Path) -> "ProtectedManifest":
        path = Path(root) / "autoevolve" / "protected.manifest.yaml"
        if not path.is_file():
            return cls()
        protected, safe, controlled = _parse_manifest(path)
        merged_protected = tuple(dict.fromkeys((*protected, *PROTECTED_DEFAULTS)))
        return cls(
            merged_protected,
            safe_patterns=safe,
            controlled_patterns=controlled,
        )

    def is_protected(self, path: str) -> bool:
        return _matches(path, self.patterns)

    def classify(self, path: str) -> str:
        if self.is_protected(path):
            return "protected"
        if _matches(path, self.safe_patterns):
            return "safe"
        if _matches(path, self.controlled_patterns):
            return "controlled"
        return "unknown"

    def validate_changes(self, changed: list[str]) -> tuple[bool, list[str]]:
        bad = [path for path in changed if self.is_protected(path)]
        return (not bad, bad)

    def validate_mutation_scope(
        self,
        changed: list[str],
        *,
        mutation_tiers: tuple[str, ...] | list[str],
        allow_controlled: bool,
    ) -> tuple[bool, list[str]]:
        tiers = set(mutation_tiers)
        bad: list[str] = []
        for path in changed:
            kind = self.classify(path)
            allowed = kind == "safe" and "safe" in tiers
            allowed = allowed or (
                kind == "controlled" and allow_controlled and "controlled" in tiers
            )
            if not allowed:
                bad.append(path)
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


def _promotion_evidence_ready(baseline: EvalSnapshot, candidate: EvalSnapshot) -> tuple[bool, str]:
    if not baseline.eval_suite_hash or baseline.eval_suite_hash != candidate.eval_suite_hash:
        return False, "baseline/candidate eval suite hash missing or mismatched"
    required = (
        baseline.dev_passed,
        baseline.holdout_passed,
        baseline.adversarial_passed,
        baseline.holdout_isolation_verified,
        candidate.dev_passed,
        candidate.holdout_passed,
        candidate.adversarial_passed,
        candidate.holdout_isolation_verified,
    )
    if not all(required):
        return False, "DEV/HOLDOUT/adversarial gates and holdout isolation are required for automatic KEEP"
    return True, ""


def promote(
    baseline: EvalSnapshot,
    candidate: EvalSnapshot,
    *,
    simplicity_tolerance: float = 0.0,
    efficiency_tolerance: float = 0.05,
    minimum_repeats: int = 3,
) -> tuple[str, str]:
    """Constraint-first promotion; automatic KEEP is deliberately conservative."""
    if not candidate.hard_gates_passed:
        return "REJECT", "L0 hard gate failed"
    if candidate.science_score < baseline.science_score:
        return "REJECT", "scientific correctness regressed"
    if min(baseline.repeats, candidate.repeats) < minimum_repeats:
        return "RETEST", f"automatic promotion requires >= {minimum_repeats} repeated runs"

    delta = candidate.research_score - baseline.research_score
    noise = max(baseline.noise_floor, candidate.noise_floor)
    if delta < -noise:
        return "REJECT", "research-quality regression exceeds empirical noise floor"

    regressions = []
    if candidate.robustness < baseline.robustness:
        regressions.append("robustness")
    if baseline.cost > 0 and candidate.cost > baseline.cost * (1 + efficiency_tolerance):
        regressions.append("cost")
    if baseline.latency > 0 and candidate.latency > baseline.latency * (1 + efficiency_tolerance):
        regressions.append("latency")
    if candidate.complexity > baseline.complexity + simplicity_tolerance:
        regressions.append("complexity")

    if abs(delta) <= noise:
        if regressions:
            return "REJECT", "within noise floor with regression: " + ",".join(regressions)
        if candidate.complexity < baseline.complexity - simplicity_tolerance:
            ready, why = _promotion_evidence_ready(baseline, candidate)
            if not ready:
                return "HUMAN_REVIEW", why
            return "KEEP", "equivalent research quality with simpler implementation"
        return "RETEST", "candidate delta is within empirical noise floor"

    if delta > noise and not regressions:
        ready, why = _promotion_evidence_ready(baseline, candidate)
        if not ready:
            return "HUMAN_REVIEW", why
        return "KEEP", "material research-quality improvement without Pareto regression"
    return "HUMAN_REVIEW", "Pareto trade-off: " + ",".join(regressions or ["mixed metrics"])


class ExperimentLog:
    HEADER = (
        "experiment_id",
        "parent_revision",
        "candidate_commit",
        "scope",
        "hypothesis",
        "eval_suite_hash",
        "repeats",
        "dev_passed",
        "holdout_passed",
        "adversarial_passed",
        "holdout_isolation_verified",
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
            str(candidate.eval_suite_hash if candidate else ""),
            str(candidate.repeats if candidate else ""),
            str(candidate.dev_passed if candidate else ""),
            str(candidate.holdout_passed if candidate else ""),
            str(candidate.adversarial_passed if candidate else ""),
            str(candidate.holdout_isolation_verified if candidate else ""),
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
        unknown = set(self.mutation_tiers) - {"safe", "controlled"}
        if unknown:
            raise ValueError(f"unknown mutation tiers: {sorted(unknown)}")
        if "controlled" in self.mutation_tiers and not self.allow_controlled:
            raise ValueError("controlled mutation tier requires allow_controlled=true")
