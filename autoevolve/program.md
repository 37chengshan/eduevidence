# EduEvidence Autoevolve Program

Run this loop only on an `autoresearch/<run-tag>` branch or isolated worktree.

1. Read `references/scientific-invariants.md`, `autoevolve/protected.manifest.yaml`, prior `results.tsv`, `experiments.jsonl`, and `best.json`.
2. Establish a baseline before proposing a change.
3. State exactly one falsifiable improvement hypothesis.
4. Modify only the approved mutation surface. Daily mode is Tier A (`safe`) only.
5. Record every changed file. A protected-file mutation makes the experiment `INVALID` before scoring.
6. Run deterministic L0 gates first, then DEV. Run repeated empirical / holdout / adversarial evaluation only for promising candidates.
7. Apply constraint-first promotion: hard scientific regression always rejects; improvements within the noise floor retest; equivalent results prefer the simpler implementation.
8. Append both successful and failed experiments to the experiment log.
9. Keep/revert only candidate repository code. Never delete or suppress real evidence because it is unfavorable.
10. Stop at the configured budget, five valid non-improving experiments, blocked execution, or explicit user stop.
11. Promotion is branch-only. Never merge `main`, release, deploy, or launch a human-subject pilot automatically.

Core rule: **Optimize the research process, never the conclusion.**
