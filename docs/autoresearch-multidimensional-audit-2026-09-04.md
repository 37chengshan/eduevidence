# EduEvidence Autoresearch vNext — Multidimensional Implementation Audit

Date: 2026-09-04  
Branch: `feature/autoresearch-phase1`  
Scope: Evidence Autoresearch, Skill Autoevolve, multi-role/subagent orchestration, state consistency, benchmark integrity, packaging, CI, and Skill distribution.

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

The Evidence Autoresearch commit path is now atomic and append-only. A ResearchIteration can create at most one GraphRevision. Exact duplicates are true no-ops; the same entity ID with different content fails closed; invalid sources cannot enter; Studies cannot cite unvalidated Sources; stale base revisions are rejected before commit. Duplicate-only retrieval cannot manufacture a GraphRevision.

DVI now separates **priority** from **decision materiality**. A HIGH-DVI gap does not by itself justify a new empirical study. The literature-to-pilot bridge requires a decision-material unresolved gap, search saturation, and feasibility/ethics conditions.

Saturation is computed per gap rather than across unrelated gap histories. Empty/no-result searches can count as low-yield attempts, strategy diversity must actually be exhausted, and one gap's failed strategies cannot saturate another gap.

The research CLI now pre-allocates a ResearchIteration ID, requires executor-side `query_count`, `candidate_count`, and `fetched_count`, verifies those measurements against the ResearchBudget, checks request/result identity, uses an exclusive project writer lock, and implements stop as a separate request signal instead of racing on canonical state.

### Multi-role / subagent architecture

The runtime contract now follows the same model as the design document. `TaskSpec` carries run/revision context, role, evidence axis, delegation rationale, allowed capabilities, forbidden actions, scope, budget, output contract, and termination contract. A delegated task without this context cannot reach `safe_spawn()`.

Execution waves are explicit. M tasks first parallelize direct/counter retrieval and later run independent challenge. L tasks first run four evidence-axis retrieval workers, then independent Skeptic + Method Reviewer. Judge/adjudication stays serial. `max_parallel_workers` therefore means simultaneous workers, not total delegated task count.

Workers remain staging-only. Main-process `WorkerResult` validation ignores worker self-attestation, checks the originating TaskSpec/output contract, rejects canonical-state artifacts, and supplies Judge with validated staging artifacts only. Worker persuasive prose is not itself evidence input to Judge.

### Skill Autoevolve integrity

The mutation agent now receives a sanitized DEV-only view with no `.git` and no holdout/adversarial evaluator content. Candidate mutation is separated from the full evaluation worktree. Active experiment memory lives outside the candidate worktree so reject/revert cannot erase logs or accidentally mix them into candidate code.

Mutation tiers are enforced mechanically: protected, safe, controlled, unknown. Unknown paths fail. Daily mode is safe-only by default. The protected surface includes the scientific invariants, benchmark/evaluator surfaces, schemas, graph/study-design core, Autoevolve implementation/control plane, and protected workflows.

Promotion is constraint-first and conservative. L0 failure or scientific regression rejects. Repeated evaluation is required. Improvements inside the empirical noise floor are retested rather than kept. Robustness/cost/latency/complexity regressions become reject or HUMAN_REVIEW rather than automatic KEEP. Automatic KEEP additionally requires DEV, HOLDOUT, adversarial, holdout-isolation evidence and a matching evaluation-suite hash.

RETEST measures the same candidate. REJECT/HUMAN_REVIEW candidates do not leak into the next experiment. Candidate patches/files remain local session artifacts; only structured experiment memory is eligible for branch persistence.

Nightly GitHub execution no longer exposes a persisted repository write credential to the external Agent/Evaluator. The final workflow-owned step receives the token and may push only one exact `autoresearch/gha-*` ref. The workflow never opens/merges a PR, releases, or deploys.

### Packaging / CI / Skill distribution

The Skill bundle now contains `agents/openai.yaml`, and the competition package includes the vNext engine/scripts/retrieval/integrations/schemas/Skill/reference/Autoevolve control plane while excluding private benchmark/test/run histories. The wheel package now discovers `engine*`, `scripts*`, `retrieval*`, and `integrations*`, and includes vNext schemas.

The dedicated Autoresearch Gates exercise orchestration, dispatch, worker validation, atomic evidence commits, scientific transitions, research CLI contracts, Autoevolve promotion/runner behavior, git workspace behavior, and vNext wheel imports. Historical CI references to deleted examples and stale packaging paths were removed rather than hidden behind broad ignores.

A narrow Ruff exception remains for one legacy postponed `Optional` annotation in the report renderer. It does not relax undefined-name checks repository-wide and is a cleanup item, not a runtime safety dependency.

## Merge blockers still to verify/close

### B1 — DecisionSnapshot revision binding

Any DecisionSnapshot used to calculate DVI must be bound to the currently active GraphRevision. This must be checked on every research-auto entry, not only after a previous `re_adjudicate` transition. A non-empty stale DecisionSnapshot must fail closed before gap ranking.

### B2 — Worker cannot declare a KnowledgeGap resolved

Executor output must not be authoritative for `RESOLVED`. A worker may return evidence and observations; only main-engine graph coverage + re-adjudication/re-derivation may resolve the gap. Any direct persistence path from worker-supplied `resolved_gap_ids` must be removed.

### B3 — Stable gap lineage must be consumed, not only emitted

KnowledgeGap derivation now emits `extensions.autoresearch_key`, a stable semantic lineage key across GraphRevisions. Research history/saturation/attempted-strategy matching must use this key when available, with `gap_id` retained as the revision-local artifact identifier. Merely writing the key without consuming it does not solve cross-revision repeated-search memory.

These three are state-machine correctness items and should be closed before merging the vNext branch.

## Important hardening after merge blockers

### H1 — Holdout isolation authority

The sanitized mutation view prevents accidental leakage but is not an OS sandbox. A hostile external process could attempt to inspect paths outside its cwd. Therefore unattended automatic KEEP should be trusted only when the evaluator/runtime provides a real isolation boundary that the runner trusts. `holdout_isolation_verified` must not become a meaningless self-asserted boolean.

### H2 — Evaluation-suite identity

Baseline/candidate suite hashes are compared, but the strongest implementation computes the expected suite identity in the trusted runner from protected evaluator/partition/gold/adversarial inputs rather than trusting an arbitrary evaluator-supplied string.

### H3 — Host result-adapter wiring

The repository now contains the correct TaskSpec dispatch gate and WorkerResult acceptance gate. Any host/Agent-MCP adapter that actually executes a spawn must route returned worker artifacts through `validate_worker_output()` before Judge context construction. A host that bypasses that acceptance boundary is non-conformant even if the worker prompt says "staging only".

## Validation policy

The branch should be considered technically mergeable only after all of the following are true on the same current HEAD:

- merge blockers B1–B3 are closed and regression-tested;
- repository metrics are current;
- Ruff E9/F63/F7/F82 passes;
- full pytest passes;
- Python 3.10 and Python 3.12 GitHub Actions test jobs pass;
- schema-smoke passes;
- upload-build passes;
- Autoresearch Gates pass;
- wheel isolated-import smoke passes;
- no protected surface was weakened to make the tests green.

Even after all gates pass, merge to `main` remains a human action. Autoevolve may prepare and push experiment branches, but it is never the merge authority.
