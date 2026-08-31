# Benchmark Card — same model, method off vs on

The claim being tested is not “EduEvidence is smarter.” It is: **under the same model, the method changes the decision quality.**

- Fixed 30-question set: `benchmarks/questions.jsonl` (S/M/L, AI-in-education + teaching methods + learning psychology + edtech).
- Gold annotations: `benchmarks/annotations/gold-Q*.json` (30 entries).
- Baselines: `B0` direct answer, `B1` search+answer, `B2` standard research agent, `B3` EduEvidence single, `B4` agent-mcp multipass.
- Runner: `scripts/benchmark_v3.py`; evaluator: `scripts/benchmark_evaluator.py`; judge: `scripts/benchmark_judge.py` (declared same-family independence limitation).
- Recording each attempt (prompt, response, usage, artifact hashes): run manifests under `benchmarks/empirical/`.

Honest reporting rule: results are only “implementation evidence” if they are from a recorded attempt with the exact model/prompt/search/budget manifest. A simulator run is expressly not performance evidence (`SimDriver` docstring).
