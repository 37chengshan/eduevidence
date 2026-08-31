# Problem Card — “AI read eight papers and said: yes.” Can we trust that?

`examples/ai-coding-assistant-evidence/` is a real reconstruction of the flagship question *“Should first-year C students use AI coding assistants?”* This pack shows the failure mode the engine exists to prevent:

- Task performance improves while students are using the tool — this is not learning.
- Strictly separating **task performance** from **learning** is a scientific rule, not a style choice: `references/wwc_standards.md`, `skill/agents/method-reviewer.md`.
- A report that only cites supporting papers cannot carry a decision boundary. EduEvidence forces the boundary (`scope`), the counter-evidence (`skeptic`), and the method audit before any verdict.

Evidence that the rule is machine-enforced:

- `scripts/pre_verdict_gate.py` — item 6 `methodology_audit` and item 7 `claim_evidence_audit`;
- `engine/tribunal.py` — “no direct learning evidence ⇒ no ADOPT”;
- `scripts/skill_lint.py` and `tests/test_tribunal_learning_gate.py`.
