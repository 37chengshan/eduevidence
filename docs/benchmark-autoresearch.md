# vNext Autoresearch Benchmark Policy

This document extends, rather than replaces, `docs/benchmark.md`. Historical B0–B4 empirical results remain historical evidence; this file defines the candidate-promotion policy used by Skill Autoresearch.

## Partitions

Authoritative partition manifest: `benchmarks/partitions.json`.

- DEV: Q01–Q15. Candidate experiments may use these during fast iteration.
- HOLDOUT: Q16–Q30. Candidate context bundles must not include prompts/gold from this partition; protected evaluator uses it at promotion time.
- ADVERSARIAL: integrity and failure cases in `benchmarks/adversarial/cases.jsonl`.
- TEMPORAL: dynamically timestamped current-evidence checks; never permanent gold.

Open-source visibility does not make HOLDOUT cryptographically secret. The contract is execution isolation: the autoresearch candidate process must not load it while designing the mutation.

## Evaluation ladder

```text
L0 deterministic scientific/contract gates
→ L1 gold scientific correctness
→ L2 research quality
→ L3 robustness
→ L4 efficiency
→ L5 simplicity
```

Hard scientific regression always rejects before aggregate scoring. Precision/recall are paired where omission could game precision. Missing output is not automatically success.

## Stochastic evaluation

Real model evaluation requires at least 3 repeats, preferably 5. Record model family/version, tool/provider manifest, timestamp, token/cost/latency, mean/variance or CI. A candidate improvement smaller than the empirical noise floor is `RETEST`, not `KEEP`.

Simulation validates harness behavior only. It must never be reported as real model performance.

## Promotion

`KEEP` requires material research-quality improvement without core scientific regression. Equal/near-equal results prefer the simpler implementation. Pareto trade-offs become `HUMAN_REVIEW`. Protected mutation becomes `INVALID` before scoring.

The repository never auto-merges a promoted candidate to main.
