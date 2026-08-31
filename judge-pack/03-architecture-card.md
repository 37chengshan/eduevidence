# Architecture Card — Workflow → Capability DAG → Contract

The public surface is intentionally small:

```text
User intent → Workflow → Capability DAG → Scientific gate → Artifact
            → Evidence Graph revision → Decision Snapshot → Projection
```

- Three user workflows: `skill/workflows/evidence-review.md`, `decision-and-pilot.md`, `evaluate-and-update.md`.
- The capability registry is the only execution abstraction and does not name agents or models: `engine/capabilities.py`.
- The canonical protocol (with Applicability inside science and presentation as Projection) is enforced at runtime: `engine/workflows.py`, `scripts/run_workspace.py`, `scripts/orchestrator.py`.
- Durable control plane: `engine/research_service.py` (replayable events, content-addressed immutable artifacts) with read API in `scripts/dashboard_server.py` (`/api/research/*`).
- The 12 legacy sub-skills are capability recipes for compatible installs, not separate workflows (`SKILL.md`).

System tests that lock the invariants: `tests/test_workflows.py`, `tests/test_research_service.py`, `tests/test_skill_behavior.py`, `tests/test_v2_release_contract.py`.
