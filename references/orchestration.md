# Orchestration

Treat these concepts as distinct:

`Protocol Stage ≠ Scientific Role ≠ Capability ≠ Worker/Subagent ≠ Model/CLI`.

A Scientific Role is an accountability boundary. It does not imply a permanent agent. A Capability is reusable implementation. A Worker/Subagent is a temporary execution instance. Model/CLI selection is an execution adapter governed by existing user approval.

## Default topology

- **S**: lead-only, zero delegated workers.
- **M**: selectively delegate independent direct/counter evidence acquisition and, when useful, an independent Skeptic.
- **L**: split retrieval by evidence axis (direct causal; transfer/retention; null/negative/risk; applicability/freshness), then deterministic merge, optional independent Skeptic/Method Reviewer, single-writer commit, Judge, and high-impact independent final review.
- Hard parallel cap: 6. Never recursive swarm.

## TaskSpec and dispatch

Every delegated worker requires a validated TaskSpec. Workers are read-only against canonical project state and return staging artifacts only. Agent MCP delegation must pass through the TaskSpec dispatch adapter and the existing `safe_spawn()` approval gate. Do not route by provider name; providers are tools, while evidence axes are epistemic objectives.

## Single Writer

Parallelize independent evidence acquisition and analysis; serialize canonical state transitions. Only the lead/single-writer path may commit GraphRevision, DecisionSnapshot, persistent KnowledgeGap state, StudyDesign, PilotRun, or AnalysisRun. Judges consume validated artifacts, never unvalidated worker prose.
