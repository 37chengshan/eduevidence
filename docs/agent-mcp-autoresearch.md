# Agent MCP in EduEvidence vNext

`docs/agent-mcp-enhanced-mode.md` remains the installation/approval guide. This file defines the vNext orchestration semantics.

## One execution architecture

```text
Workflow / Protocol Stage
→ ExecutionPlanner
→ TaskSpec
→ local capability OR delegated worker
→ staging artifact
→ schema/provenance/scientific validation
→ Single Writer
```

`skill/agents/*.md` are scientific-role profiles and compatibility instructions. They are not eight permanent runtime agents.

## Delegation

Delegation is allowed only when the work is actually decomposable. The default topology is S=0 workers; M selectively delegates; L uses a bounded worker pool with a hard maximum of 6. Retrieval splits by evidence axis, not provider.

Every delegated call must pass `integrations/orchestration_dispatch.py`, which validates TaskSpec and then calls the existing `integrations/agent_mcp.py::safe_spawn()`. Existing user approval of CLI/model mappings remains mandatory. Autoresearch does not grant itself new CLI/model authorization.

## Independence

Use independence selectively:

- retrieval workers need objective/search independence when useful;
- Skeptic and high-impact final review prioritize independent context and, when approved/available, different model family;
- Method Reviewer may run independently for L/high-impact tasks;
- do not spend flagship-model budget merely to make every worker different.

## Canonical state

Workers receive `CANONICAL_STATE_WRITE: FORBIDDEN` and may return staging artifacts only. They cannot commit EvidenceGraph/GraphRevision, DecisionSnapshot, persistent KnowledgeGap, StudyDesign, PilotRun or AnalysisRun. Canonical writes are serialized by the lead/single-writer path.

## Autoresearch

Evidence Autoresearch may use Agent MCP workers to execute a bounded ResearchStrategy, but worker output is still staging evidence. Skill Autoresearch may use a separately pre-authorized external agent command inside an isolated `autoresearch/<tag>` worktree. Neither path bypasses scientific/protected gates.
