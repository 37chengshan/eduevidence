# EduEvidence Autoresearch vNext — Multidimensional Implementation Audit

Date: 2026-09-05  
Branch: `feature/autoresearch-hardening-h1-h3`  
Scope: Evidence Autoresearch, Skill Autoevolve, multi-role/subagent orchestration, state consistency, benchmark integrity, packaging, CI, and trusted promotion authority.

## Audit position

The vNext architecture is sound only if autonomy remains subordinate to scientific state and protected evaluation. This review therefore treats "looks agentic" as irrelevant. A feature passes only when the state transition, provenance boundary, failure mode, and promotion authority are mechanically enforceable.

The governing rules remain:

- **Optimize for decision integrity, not answer confidence.**
- **Optimize the research process, never the conclusion.**
- Validated evidence is append-only, including negative/null/contradictory evidence.
- Canonical project state has a single writer.
- Protocol Stage ≠ Scientific Role ≠ Capability ≠ Worker/Subagent ≠ Model/CLI.
- Automatic Skill promotion may never edit its evaluator, holdout, scientific invariants, schemas, or Autoevolve control plane.

## Closed findings

### Evidence-state integrity

The Evidence Autoresearch commit path is atomic and append-only. A ResearchIteration can create at most one GraphRevision. Exact duplicates are true no-ops; the same entity ID with different content fails closed; invalid sources cannot enter; Studies cannot cite unvalidated Sources; stale base revisions are rejected before commit. Duplicate-only retrieval cannot manufacture a GraphRevision.

DVI separates **priority** from **decision materiality**. A HIGH-DVI gap does not by itself justify a new empirical study. The literature-to-pilot bridge requires a decision-material unresolved gap, search saturation, and feasibility/ethics conditions.

Saturation is computed per gap rather than across unrelated gap histories. Empty/no-result searches can count as low-yield attempts, strategy diversity must actually be exhausted, and one gap's failed strategies cannot saturate another gap.

The research CLI pre-allocates a ResearchIteration ID, requires executor-side `query_count`, `candidate_count`, and `fetched_count`, verifies those measurements against the ResearchBudget, checks request/result identity, uses an exclusive project writer lock, and implements stop as a separate request signal instead of racing on canonical state.

### State-machine blockers — CLOSED

**B1 — DecisionSnapshot revision binding: CLOSED.** Any non-empty DecisionSnapshot used for DVI must carry `graph_revision`, and it must equal the KnowledgeGap's `derived_from_graph_revision`. Stale or unbound decision state fails closed before ranking. Regression coverage explicitly exercises the stale-revision case.

**B2 — Worker cannot resolve KnowledgeGap: CLOSED.** Executor/worker output containing `resolved_gap_ids` is rejected by the Evidence Autoresearch controller. Gap resolution is owned by the main engine after validated evidence is committed and coverage/adjudication is re-derived. The obsolete CLI path that would have persisted worker-authored `resolved_gap_ids` has also been removed, so there is no contradictory fallback path.

**B3 — Stable gap lineage is consumed: CLOSED.** KnowledgeGap derivation emits `extensions.autoresearch_key`; ResearchIteration persists the lineage key and strategy/saturation history uses it across GraphRevisions when available, while `gap_id` remains the revision-local artifact identifier. Regression coverage verifies that semantically identical gaps with different revision-local IDs continue prior strategy memory.

### Multi-role / subagent architecture

The runtime contract follows the same model as the design document. `TaskSpec` carries run/revision context, role, evidence axis, delegation rationale, allowed capabilities, forbidden actions, scope, budget, output contract, and termination contract. A delegated task without this context cannot reach `safe_spawn()`.

Execution waves are explicit. M tasks first parallelize direct/counter retrieval and later run independent challenge. L tasks first run four evidence-axis retrieval workers, then independent Skeptic + Method Reviewer. Judge/adjudication stays serial. `max_parallel_workers` therefore means simultaneous workers, not total delegated task count.

Workers remain staging-only. Main-process `WorkerResult` validation ignores worker self-attestation, checks the originating TaskSpec/output contract, rejects canonical-state artifacts, and supplies Judge with validated staging artifacts only. Worker persuasive prose is not itself evidence input to Judge.

### Skill Autoevolve integrity

The mutation agent receives a sanitized DEV-only view with no `.git` and no holdout/adversarial evaluator content. Candidate mutation is separated from the full evaluation worktree. Active experiment memory lives outside the candidate worktree so reject/revert cannot erase logs or accidentally mix them into candidate code.

Mutation tiers are enforced mechanically: protected, safe, controlled, unknown. Unknown paths fail. Daily mode is safe-only by default. The protected surface includes the scientific invariants, benchmark/evaluator surfaces, schemas, graph/study-design core, Autoevolve implementation/control plane, and protected workflows.

Promotion is constraint-first and conservative. L0 failure or scientific regression rejects. Repeated evaluation is required. Improvements inside the empirical noise floor are retested rather than kept. Robustness/cost/latency/complexity regressions become reject or HUMAN_REVIEW rather than automatic KEEP.

RETEST measures the same candidate. REJECT/HUMAN_REVIEW candidates do not leak into the next experiment. Candidate patches/files remain local session artifacts; only structured experiment memory is eligible for branch persistence.

Nightly GitHub execution does not expose a persisted repository write credential to the external Agent/Evaluator. The final workflow-owned step receives the token and may push only one exact `autoresearch/gha-*` ref. The workflow never opens/merges a PR, releases, or deploys.

### H1 — Holdout isolation authority: CLOSED

Evaluator output is no longer authoritative for holdout isolation. `DailyEvolutionRunner` overwrites any evaluator-supplied `holdout_isolation_verified` value with runner-owned state.

A verified automatic-promotion path requires a runner-constructed container boundary. The supported container mode mounts only the sanitized mutation view at `/workspace`, disables networking, uses a read-only container root, supplies a writable tmpfs, and does not implicitly forward host model/API credentials. The runner reports the isolation provider and reason in the session report.

If no supported OS isolation provider is configured, research may still execute but automatic KEEP is disabled by the promotion evidence gate; a materially improved candidate is `HUMAN_REVIEW`, not KEEP. This is the intended safe default.

### H2 — Evaluation-suite identity: CLOSED

The evaluator no longer chooses the identity of the evaluation suite. The runner computes `eval_suite_hash` directly from protected evaluator, holdout, adversarial, gold annotation, partition/question, and scientific-invariant inputs.

Evaluator-supplied `eval_suite_hash` is overwritten. The trusted suite hash is recomputed before candidate evaluation; any drift during an experiment invalidates the candidate. Mutable Skill/workflow files do not affect this hash, while changes to protected evaluation inputs do.

### H3 — Host result-adapter wiring: CLOSED

`integrations/orchestration_dispatch.py` now contains the conformant execution path:

`dispatch_task() -> host executor -> execute_dispatched_task() -> accept_worker_output() -> validate_worker_output()`

Raw worker output is never exposed as Judge input by this adapter. Worker self-attestation is ignored. Canonical-state artifacts are rejected even when a worker labels itself validated. `judge_artifacts()` fails closed unless every WorkerResult has passed main-process acceptance against its originating TaskSpec/output contract.

A host that bypasses this acceptance path remains non-conformant; the repository now provides a mechanical adapter rather than relying on prompt wording alone.

### Packaging / CI / Skill distribution

The Skill bundle contains `agents/openai.yaml`, and the competition package includes the vNext engine/scripts/retrieval/integrations/schemas/Skill/reference/Autoevolve control plane while excluding private benchmark/test/run histories. The wheel package discovers `engine*`, `scripts*`, `retrieval*`, and `integrations*`, and includes vNext schemas.

The main wheel smoke is isolated from the repository checkout: it changes to `/tmp`, loads only `/tmp/wheel-smoke`, and asserts imported module `__file__` paths are physically inside the installed wheel target. This prevents a source-tree import from producing a false-green release test.

The dedicated Autoresearch Gates exercise orchestration, dispatch, worker validation, atomic evidence commits, scientific transitions, research CLI contracts, Autoevolve promotion/runner behavior, git workspace behavior, trusted hardening paths, and vNext wheel imports.

A narrow Ruff exception remains for one legacy postponed `Optional` annotation in the report renderer. It does not relax undefined-name checks repository-wide and is a cleanup item, not a runtime safety dependency.

## Validation result

All technical gates passed on hardening commit `186c65d4a02dac31d4ac7f59894aa92279095697` immediately before this audit-status documentation update:

- B1–B3 closed and regression-tested;
- H1–H3 implemented and regression-tested;
- repository metrics current (`850` tests, `47` schemas);
- Ruff E9/F63/F7/F82 passed;
- full pytest passed;
- Python 3.10 GitHub Actions test job passed;
- Python 3.12 GitHub Actions test job passed;
- schema-smoke passed;
- upload-build + SKILL parity + zero-leak scan passed;
- Autoresearch Gates passed;
- isolated wheel import smoke passed on both Python 3.10 and 3.12;
- protected scientific surfaces were not weakened to obtain green tests.

Because this file update creates a documentation-only successor commit, the successor HEAD must still receive its own GitHub check result before merge.

## Operational boundary

Automatic KEEP is deliberately stricter than ordinary Autoevolve execution. Without a configured runner-owned container isolation boundary, the system may search, mutate a sanitized DEV view, evaluate, log, and prepare a candidate, but it must stop at `HUMAN_REVIEW` for promotion.

This is not a degraded scientific rule. It is the enforcement mechanism that prevents an evaluator or mutation agent from self-certifying access isolation.

## Merge position

There are no remaining known merge-blocking findings from B1–B3 or H1–H3. Once the current documentation successor HEAD reports the same required checks green, the branch is technically ready for human merge.

Merge to `main` remains a human action. Autoevolve may prepare and push experiment branches, but it is never the merge authority.
