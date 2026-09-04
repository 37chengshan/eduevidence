# EduEvidence vNext Autoresearch — Implementation Status

This file maps `docs/autoresearch-evolution-plan.md` to shipped runtime surfaces.

## Phase 0 — Architecture Freeze

Implemented:
- `docs/autoresearch-evolution-plan.md`
- `docs/orchestration-role-model.md`
- `references/scientific-invariants.md`

## Phase 1 — Orchestration Clarity

Implemented:
- `engine/orchestration.py` — RoleSpec, TaskSpec, ExecutionPlan, deterministic S/M/L planner, Single Writer guard.
- `skill/roles/registry.yaml` — role accountability registry; legacy `skill/agents/*` remain compatibility profiles.
- `integrations/orchestration_dispatch.py` — TaskSpec → existing Agent MCP `safe_spawn()` gate.
- Parallelization is by evidence axis; hard cap 6; S defaults to zero subagents.

## Phase 2 — Evidence Research Memory

Implemented:
- `engine/autoresearch/contracts.py` — ResearchStrategy, ResearchIteration, NegativeSearchRecord and budgets/status.
- `engine/autoresearch/research_memory.py` — append-only iteration and negative-search JSONL memory.
- `schemas/vNext/*` contracts.

## Phase 3 — Gap Priority / DVI

Implemented:
- `engine/autoresearch/gap_priority.py` — explainable HIGH/MEDIUM/LOW conceptual DVI.
- DVI is explicitly not EVPI/EVSI or a probability.
- Existing `engine/gaps.py` remains the authority for evidence-grounded gap derivation.

## Phase 4 — Bounded Evidence Autoresearch

Implemented:
- `engine/autoresearch/controller.py` — select one unresolved gap, create one research hypothesis/strategy, consume bounded staging results, append evidence through a single-writer callback, or log no-gain.
- `eduevidence research auto step/start/status/report/stop` command domain.
- With no external execution artifact, the command stops at `awaiting_execution`; it never invents search results.

## Phase 5 — Search Saturation → Pilot Bridge

Implemented:
- `engine/autoresearch/saturation.py`.
- Saturation requires consecutive low-yield iterations plus strategy-diversity exhaustion.
- Empirical transition requires HIGH DVI + decision materiality + unresolved gap + saturation + ethical/operational feasibility.
- Existing StudyDesign grounding gate remains authoritative for the actual study design.

## Phase 6 — Skill Autoresearch MVP

Implemented:
- `engine/autoevolve/core.py` — protected manifest, EvalSnapshot, SkillExperiment, promotion, noise floor, simplicity, append-only log, plateau, daily profile.
- `engine/autoevolve/git_workspace.py` — isolated `autoresearch/<tag>` worktree, restore, experiment commit, non-force branch push.
- `engine/autoevolve/runner.py` — bounded external-agent loop with cost, wall-time and plateau ceilings.
- `autoevolve/program.md`, `config.yaml`, `protected.manifest.yaml`, `results.tsv`, `best.json`.
- `eduevidence evolve init/baseline/run/status/report/best/prepare-pr`.

## Phase 7 — Evaluation Isolation

Implemented:
- `benchmarks/partitions.json` — Q01–Q15 DEV; Q16–Q30 HOLDOUT.
- `benchmarks/adversarial/cases.jsonl` — fake DOI, snippet-as-evidence, missing CI, task/learning substitution, prompt injection, PII, singular DID.
- Constraint-first promotion in `engine/autoevolve/core.py`.
- `references/evaluation-policy.md` defines repeated empirical evaluation, noise floor and Pareto/simplicity policy.

Actual paid/model empirical runs are intentionally not fabricated by the repository. The runner accepts external pre-authorized evaluator commands and records their real EvalSnapshot results.

## Phase 8 — Daily Evolution

Implemented:
- `scripts/daily_evolve.py`.
- `.github/workflows/autoevolve-nightly.yml` — scheduled/manual opt-in runner.
- It is disabled until repository variables explicitly provide the approved agent and evaluator commands.
- Promotion is branch-only. It may push `autoresearch/*`, but never opens/merges PRs, releases or deploys.

## Phase 9 — Studio / Showcase Data Surface

Implemented as projection APIs so UI remains a projection rather than canonical state:
- `engine/autoresearch/projection.py` — decision, DVI-ranked gaps, current iteration, saturation and revision state.
- `engine/autoevolve/projection.py` — baseline, best, experiment timeline, plateau and protected integrity.

The public report does not expose self-evolution debug state by default. A future visual shell can consume these projection APIs without changing scientific state.

## CI / Distribution

Implemented:
- `.github/workflows/autoresearch-gates.yml` — scientific invariants, orchestration, schemas, focused tests, wheel subpackage smoke and benchmark partition contract.
- `scripts/check_autoresearch_invariants.py` — additionally blocks protected mutations on `autoresearch/*` branches.
- Existing CI updated to current example packs and vNext wheel imports.
- `packaging/make_upload.sh` ships the vNext runtime/control plane, uses the current real-literature flagship, and surfaces Python compile failures instead of hiding them.

## Runtime Principles

1. Optimize for decision integrity, not answer confidence.
2. Optimize the research process, never the conclusion.
3. Validated evidence is append-only.
4. One canonical writer; subagents return staging artifacts.
5. Agent count follows decomposability, not role count.
6. Evidence Autoresearch cannot modify the Skill/repository.
7. Skill Autoresearch cannot modify real user research state.
8. No automatic main merge, release, deployment, policy action, or human-subject study launch.
