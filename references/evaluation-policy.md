# Skill Autoresearch Evaluation Policy

Evaluate candidate EduEvidence implementations with **constraint-first Pareto evaluation**, never a single LLM score.

## Order

1. **L0 hard gates** — schema validity, provenance, graph integrity, study identity, no false precision, no unsupported ADOPT, synthetic/real separation, grounded gaps, protected integrity, privacy. Any failure = REJECT.
2. **L1 scientific correctness** — outcome separation, citation support, contradiction precision/recall, scope/decision calibration, methodology issue detection, gap correctness. Material regression = REJECT.
3. **L2 research quality** — direct evidence gain, unique eligible evidence yield, counter-evidence yield, applicability coverage, gap-resolution and saturation efficiency.
4. **L3 robustness** — S/M/L, domains, model families, repeated runs, provider variation, missing/adversarial conditions.
5. **L4 efficiency** — token, cost, latency, search/fetch calls, subagent count, parallel speedup.
6. **L5 simplicity** — LOC, loaded Skill context, branches, dependencies, maintenance surface. Equal evidence quality prefers the simpler candidate.

## Promotion

- Hard gate fail or scientific regression → `REJECT`.
- Candidate improvement within empirical noise → `RETEST`.
- Material quality improvement without core regression → `KEEP`.
- Real Pareto trade-off → `HUMAN_REVIEW`.
- Protected mutation → `INVALID` before scoring.

Use at least 3 repeated empirical runs, preferably 5, for stochastic model evaluation. DEV is visible to candidate experiments. HOLDOUT and ADVERSARIAL are evaluator-only promotion inputs. Temporal evaluation is timestamped and not permanent gold.

Skill Autoresearch operates only on fixture/benchmark research state and an `autoresearch/<run-tag>` branch/worktree. It never changes real user evidence state, merges main, releases, deploys, or launches a human-subject study automatically.
