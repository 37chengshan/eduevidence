# EduEvidence 角色、能力与子代理编排模型

> 本文定义 EduEvidence 下一阶段唯一的多角色 / 多代理语义。  
> 核心目标：消除“Protocol Stage = Role = Sub-skill = Subagent”的混淆。

---

## 1. 唯一分层模型

EduEvidence 从此严格区分 5 个概念：

```text
Protocol Stage
≠ Scientific Role
≠ Capability
≠ Worker/Subagent
≠ Model/CLI
```

### Protocol Stage

回答：**研究流程现在进行到哪里？**

权威定义仍然只有 Canonical 9-step Protocol：

```text
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate
→ Applicability → Intervene → Evaluate
```

Stage 是科学流程，不是 Agent。

---

### Scientific Role

回答：**谁对某一种科学责任负责？**

Role 是责任边界，不代表一定要启动独立模型。

例如：

```text
Skeptic
= 对反证充分性负责

Methodologist
= 对方法学审计负责

Adjudicator
= 对最终 evidence-bounded decision 负责
```

---

### Capability

回答：**完成任务需要什么可复用能力？**

例如：

```text
query expansion
full-text fetch
study identity resolution
finding extraction
contradiction analysis
methodology audit
gap derivation
study design
data analysis
report rendering
```

Capability 可以由：

```text
脚本
Python engine
Skill recipe
单 Agent
Subagent
MCP tool
```

执行。

Capability 不是角色。

---

### Worker / Subagent

回答：**这一次运行里，要不要创建一个独立执行实例？**

Subagent 是 runtime object，不是静态架构成员。

同一个 `evidence-retrieval` Capability：

```text
S 级任务
→ 主 Agent 自己调用工具

M 级任务
→ 2 个 Search Worker 并行

L 级任务
→ 4 个按证据轴拆分的 Search Worker
```

所以：

> **子代理数量由任务独立性和复杂度决定，不由角色数量决定。**

---

### Model / CLI

回答：**Worker 在哪个执行底座上运行？**

它只是 execution adapter。

```text
Role / TaskSpec
↓
能力需求
↓
Agent MCP approval / inventory
↓
CLI + model
```

不允许：

```text
Skeptic 永远等于 Claude
Retriever 永远等于 OMP
```

具体映射仍遵守现有 `agent_mcp_approval.json + safe_spawn()`。

---

# 2. 当前 8 个 `skill/agents` 如何重新解释

当前仓库有：

```text
education-planner
evidence-retriever
evidence-analyst
skeptic
method-reviewer
evidence-judge
intervention-designer
evaluation-designer
```

不再称它们为“八个一定存在的 Agent”。

重新分类：

## A. Scientific Authority Roles

这些角色承担不可省略的独立科学责任：

```text
Skeptic
Method Reviewer
Evidence Judge
```

其中 Skeptic / Method Reviewer 在高复杂度场景适合独立上下文；Evidence Judge 在高影响任务中适合与主分析分离。

---

## B. Domain Responsibility Profiles

```text
Education Planner
Intervention Designer
Evaluation Designer
```

它们定义责任与输出契约，但多数时候可以由 Lead Researcher 调用对应 capability 完成，不必单独 spawn。

只有当：

```text
任务复杂
上下文很大
需要专门定量推理
需要独立设计复核
```

才转成独立 Worker。

---

## C. Execution Worker Profiles

```text
Evidence Retriever
Evidence Analyst
```

它们本质最接近 worker template。

可以有：

```text
Retriever Worker #1
Retriever Worker #2
Retriever Worker #3
```

但三者共享同一个 profile，TaskSpec 不同。

不需要创造：

```text
retriever-1.md
retriever-2.md
retriever-3.md
```

---

# 3. 新增唯一 Orchestrator：Lead Researcher

新增逻辑角色：

```text
Lead Researcher / Orchestrator
```

它负责：

```text
理解用户任务
选择 Workflow
运行 Complexity Gate
建立 Capability DAG
决定哪些节点本地执行
决定哪些节点 spawn
分配 TaskSpec
控制预算
等待 / 恢复 worker
合并 staging artifacts
触发 scientific gates
决定是否继续 research loop
```

它**不拥有以下权力**：

```text
绕过 schema
绕过 provenance
修改 gold/evaluator
把未验证 worker 输出直接写入 Graph
在高影响模式下自己审核自己的最终 verdict
```

Lead Researcher 是 workflow control plane，不是“最权威专家”。

---

# 4. Single Writer Principle

Canonical State 只能由主引擎写入：

```text
Evidence Graph
GraphRevision
DecisionSnapshot
KnowledgeGap persistent state
StudyDesign
PilotRun
AnalysisRun
```

所有 Subagent：

```text
read snapshot
→ perform bounded task
→ return staging artifact
```

禁止直接：

```text
commit Graph
rewrite HEAD
write DecisionSnapshot
modify evaluator
modify protected scientific rules
```

流程：

```text
Subagent Result
↓
Staging Artifact
↓
Schema Gate
↓
Provenance Gate
↓
Semantic / Scientific Gate
↓
Lead accepts
↓
Engine commit
```

这样可以避免并行 worker 同时写状态导致 race / evidence corruption。

---

# 5. TaskSpec：所有子代理派发的唯一契约

任何 `safe_spawn()` 前先创建 TaskSpec。

建议 Contract：

```json
{
  "task_id": "TSK-...",
  "run_id": "RUN-...",
  "project_id": "PRJ-...",
  "base_revision": 8,
  "role_profile": "evidence-retriever",
  "objective": "寻找 novice CS1 中关闭 AI 后的 transfer/independent performance 直接证据",
  "why_parallel": "independent evidence axis",
  "input_artifacts": [
    "frame.json",
    "gap:GAP-..."
  ],
  "allowed_capabilities": [
    "web_search",
    "academic_search",
    "fetch_source"
  ],
  "forbidden_actions": [
    "adjudicate",
    "graph_commit",
    "modify_scope"
  ],
  "search_boundary": {
    "population": "novice CS1",
    "outcomes": ["transfer", "independent_problem_solving"]
  },
  "budget": {
    "max_queries": 5,
    "max_sources": 20,
    "timeout_seconds": 240
  },
  "output_contract": "candidate-source-batch",
  "termination": "budget_exhausted_or_sufficient_candidates"
}
```

TaskSpec 必须回答：

```text
目标是什么？
为什么需要独立 worker？
给它什么上下文？
不能做什么？
预算多少？
返回什么 schema？
什么时候停止？
```

没有完整 TaskSpec，不派发。

---

# 6. WorkerResult

每个 worker 只返回结构化结果：

```json
{
  "task_id": "TSK-...",
  "status": "completed",
  "artifacts": [],
  "source_ids": [],
  "limitations": [],
  "negative_results": [],
  "budget_used": {},
  "needs_followup": false
}
```

不要返回 5000 字“工作总结”给 Orchestrator。

Lead 需要的是：

```text
Artifact
Provenance
Limitations
Status
```

而不是 worker 的完整思考过程。

---

# 7. Capability DAG 决定派发，不是 Role List

示例：Evidence Review。

```text
Frame
 ↓
Retrieve ────────┐
 ↓               │
Extract          │
 ↓               │
Challenge ◄──────┘
 ↓
Audit
 ↓
Adjudicate
 ↓
Applicability
```

真正适合并行的是：

```text
Retrieve 的独立搜索方向
Extract 的不同 Source batch
Challenge 的独立反证路径
部分 Method review batch
```

不适合并行的是：

```text
最终 Graph commit
最终 Decision adjudication
依赖上一阶段完整状态的 Gap derivation
```

原则：

> **Parallelize independent evidence acquisition; serialize canonical state transitions.**

---

# 8. 子代理派发判定器

新增 `ExecutionPlanner`。

输入：

```text
workflow
complexity
capability DAG
current evidence size
budget
Agent MCP availability
user approval
```

输出：

```text
local nodes
worker nodes
parallel groups
dependencies
model capability requirements
```

判定条件：

## 应 spawn

满足至少一类：

```text
A. 可以真正并行的独立搜索空间
B. 需要独立反证，避免 path dependence
C. 需要独立方法学判断
D. 上下文过大，需要隔离
E. 专门工具集与主 Agent 明显不同
F. 高影响 verdict 需要 independent review
```

## 不应 spawn

```text
简单单问题
工作只需一次工具调用
任务高度串行
worker 会读取几乎完全相同上下文并做相同搜索
spawn 协调成本高于工作本身
只是为了“八角色齐全”
```

---

# 9. S / M / L 的默认执行拓扑

## S — Single Agent First

默认：

```text
Lead Researcher
  ├─ Frame capability
  ├─ Retrieve capability
  ├─ Extract capability
  ├─ Challenge checklist
  ├─ Audit checklist
  └─ Adjudicate
```

```text
Subagents = 0
```

只有用户显式要求独立验证时才 spawn。

---

## M — Selective Delegation

默认：

```text
Lead Researcher
  │
  ├─ Search Worker A — direct/support evidence
  ├─ Search Worker B — contradiction/null/risk evidence
  │
  ├─ [optional] Extraction Worker — large source batch
  │
  ├─ Skeptic — independent challenge if decision-relevant
  ├─ Method Reviewer — when design quality matters
  │
  └─ Lead / Judge → final bounded decision
```

典型并发 worker：

```text
2–4
```

不是固定 8 个。

---

## L — Orchestrator + Bounded Worker Pool

```text
Lead Researcher
│
├─ Retrieval Fan-out
│   ├─ Worker A: direct causal evidence
│   ├─ Worker B: transfer / retention
│   ├─ Worker C: harms / null / contradiction
│   └─ Worker D: applicability / subgroup / current evidence
│
├─ Evidence Merge + deterministic dedupe
│
├─ Extraction Fan-out（仅来源多时）
│   ├─ Worker E: batch 1
│   └─ Worker F: batch 2
│
├─ Scientific Independence
│   ├─ Skeptic
│   └─ Method Reviewer
│
├─ Canonical Graph Commit
│
├─ Evidence Judge
│
└─ [high impact] Independent Final Reviewer
```

默认硬上限：

```text
active parallel workers <= 6
```

具体值由 budget/config 调整。

禁止递归 spawn swarm。

---

# 10. Retrieval Worker 应按“证据轴”拆，不按网站拆

坏拆法：

```text
Agent A 搜 Google Scholar
Agent B 搜 Semantic Scholar
Agent C 搜 Crossref
```

因为三个 worker 很可能搜同样的问题。

优先拆法：

```text
A：直接 Outcome / causal evidence
B：retention / transfer / independent performance
C：negative / null / risk / dependency
D：population / subgroup / applicability
E：最新 temporal evidence（需要时）
```

Provider 是 capability，不是研究方向。

这样每个 worker 有不同 epistemic objective。

---

# 11. Independence 有三种，不要混淆

## Search Independence

不同 query / evidence axis。

适用 Retriever Workers。

## Context Independence

Reviewer 不读取主分析的推理过程，只读取 canonical artifacts。

适用 Method Reviewer / Skeptic。

## Model-family Independence

使用不同模型家族。

适用高影响 Cross-Model Review。

现有 Agent MCP 对 Skeptic 已支持 `different-model-family` capability constraint；继续保留。

不是所有 worker 都必须不同模型。

---

# 12. Skeptic 的正确位置

Skeptic 不只是一个“最后检查员”。

有两个触发点：

```text
Challenge Search
→ 独立寻找 counter/null/alternative evidence

Pre-Verdict Review
→ 检查是否仍漏反证 / scope / unsupported claim
```

同一个责任 profile 可以被调用两次，但不意味着启动两个永久 Agent。

---

# 13. Method Reviewer 的正确位置

Method Reviewer 只审：

```text
study design
measurement
bias
precision
Task vs Learning
```

不要让它承担：

```text
总体 verdict
检索
最终 intervention design
```

来源很多时：

```text
Method Reviewer worker 可以按 Study batch 并行
```

但 body-of-evidence appraisal 最终要统一合并。

---

# 14. Evidence Judge 的正确位置

Evidence Judge 必须在：

```text
Graph 已稳定
Challenge 完成
Method Audit 完成
Pre-Verdict Gate 通过
```

之后执行。

Judge 不再从 worker 自然语言总结做决策。

只读取 canonical / validated artifacts：

```text
Frame
Graph Revision
Claim synthesis
Audits
Gap state
Applicability inputs
```

这会显著降低 coordination noise。

---

# 15. Intervention / Evaluation 不再默认派 Agent

只有：

```text
用户进入 Decision & Pilot
或 Full Research Cycle
且当前 Decision 允许继续
```

才激活。

简单 PILOT：

```text
Lead + study-design capability
```

复杂 Pilot：

```text
Intervention Designer worker
+
Evaluation Designer worker
```

若涉及人类受试：

```text
Ethics capability / human gate
```

---

# 16. Autoresearch 的子代理拓扑

## Evidence Autoresearch

```text
Research Loop Controller
│
├─ Gap Priority capability
├─ Hypothesis Planner capability
│
├─ bounded Retrieval Workers
│   ├─ directness axis
│   ├─ contradiction axis
│   └─ applicability/freshness axis（按需要）
│
├─ validation / extraction
├─ independent challenge/method review（按门触发）
│
├─ Single Writer Graph Commit
├─ Decision Drift
│
└─ Next Gap
```

不要让每个 iteration 自动启动全套 8 角色。

---

## Skill Autoresearch

使用“研究组织”而不是 swarm：

```text
Experiment Orchestrator
│
├─ Hypothesis Proposer
├─ Candidate Implementer
│
├─ Protected Evaluator（不是可变 Agent）
│   ├─ deterministic tests
│   ├─ DEV benchmark
│   ├─ HOLDOUT
│   └─ adversarial
│
└─ Promotion Policy
```

`Evaluator` 必须是 protected harness；LLM judge 只能作为补充 grader，不能拥有最终 override 权。

可以使用独立 Reviewer 对复杂结果做解释，但它同样不能修改 evaluator。

---

# 17. Autoresearch 中 Worker 绝不能修改这些对象

```text
benchmarks/annotations/**
benchmarks/holdout/**
benchmarks/evaluator/**
schemas/**
protected scientific rules
Graph historical revisions
Decision history
```

即使 worker 拥有写权限，也由 protected manifest / CI hard gate 拦截。

---

# 18. Worker Context 最小化

子代理不继承主 Agent 整个对话。

只收到：

```text
TaskSpec
必要 artifact refs
必要 protocol excerpt
必要 schema
必要 source batch
```

不发送：

```text
整个项目 README
整个 SKILL.md
所有历史对话
所有其他 worker 输出
```

除非任务确实需要。

目的：

```text
减少 context pollution
降低 path dependence
降低 token cost
提高责任边界清晰度
```

---

# 19. Worker 间默认不直接通信

拓扑：

```text
Worker A ─┐
Worker B ─┼→ Lead / Artifact Merge
Worker C ─┘
```

不要默认：

```text
A ↔ B ↔ C ↔ D
```

Peer-to-peer 会增加：

```text
状态一致性
重复讨论
错误传播
无法归因
```

需要 follow-up 时，由 Lead 重新创建 TaskSpec。

---

# 20. 动态 Steering

如果 Agent MCP 支持 steer / followup，EduEvidence 只通过 adapter 使用，不复制其 queue/state machine。

Steer 只用于：

```text
worker 明显偏题
新证据改变搜索方向
预算即将耗尽，需要收敛
```

所有 steer 记录到 run log。

---

# 21. Failure / Timeout

每个 TaskSpec 必须有 timeout。

worker：

```text
completed
partial
timeout
tool_failure
blocked
invalid_output
```

Lead 对 partial 结果可以：

```text
接受已有 artifact
重派更小任务
降级本地执行
```

不能因为一个 worker timeout 让整个 Evidence Graph 状态半写入。

Single Writer 保证失败前后 canonical state 一致。

---

# 22. 成本控制

ExecutionPlanner 先估计：

```text
parallelism benefit
coordination cost
model cost
tool cost
context cost
```

只有：

```text
Expected information gain > delegation overhead
```

才 spawn。

这不是展示 Agent 数量的产品。

---

# 23. EventBus 事件

新增：

```text
orchestrator.plan.created
orchestrator.task.dispatched
orchestrator.task.completed
orchestrator.task.failed
orchestrator.artifact.accepted
orchestrator.artifact.rejected
orchestrator.merge.completed
orchestrator.gate.failed
```

每个事件至少包含：

```text
run_id
task_id
role_profile
capability
status
cost/latency when available
```

Dashboard 显示 DAG，而不是“八个头像都亮了”。

---

# 24. Role Registry

新增：

```text
skill/roles/registry.yaml
```

建议结构：

```yaml
roles:
  skeptic:
    class: scientific_authority
    duties:
      - contradiction_sufficiency
      - scope_challenge
    capabilities:
      - contradiction_analysis
    spawn_policy: independent_when_M_or_L
    independence: context

  method-reviewer:
    class: scientific_authority
    duties:
      - study_methodology
    capabilities:
      - methodology_audit
    spawn_policy: when_methodology_material

  evidence-judge:
    class: scientific_authority
    duties:
      - bounded_decision
    capabilities:
      - adjudication
    spawn_policy: separate_for_high_impact

  evidence-retriever:
    class: worker_profile
    capabilities:
      - retrieve
      - fetch
    spawn_policy: parallel_when_search_space_decomposable
```

Registry 是 runtime source of truth。

`skill/agents/*.md` 暂时作为 detailed profile / compatibility layer。

---

# 25. `skill/agents` 迁移策略

Phase 1：

```text
不改路径
新增 Role Registry
SKILL.md 改用“role profile”语言
```

Phase 2：

```text
新增 skill/roles/
旧 skill/agents/ 变兼容 shim / alias
integrations/agent_mcp.py 改读取 registry
```

Phase 3：

```text
所有内部引用迁移完成后
决定是否删除 agents 命名
```

避免一次大改破坏 Agent MCP approval / tests。

---

# 26. ExecutionPlan Artifact

每次运行保存：

```text
runs/<RUN>/execution-plan.json
```

示例：

```json
{
  "complexity": "L",
  "workflow": "evidence-review",
  "nodes": [
    {"id":"frame","mode":"local"},
    {"id":"retrieve-direct","mode":"worker","parallel_group":"R1"},
    {"id":"retrieve-counter","mode":"worker","parallel_group":"R1"},
    {"id":"extract","mode":"local_or_batch_worker"},
    {"id":"skeptic","mode":"worker","independent":true},
    {"id":"audit","mode":"worker"},
    {"id":"adjudicate","mode":"judge"}
  ]
}
```

这样每次“为什么派了 4 个 Agent”都有可审计答案。

---

# 27. 多代理 Benchmark

不要只测最终答案。

新增 orchestration 指标：

```text
Duplicate Search Rate
Coverage Gain per Worker
Unique Eligible Evidence per Worker
Coordination Token Cost
Worker Failure Recovery Rate
Artifact Acceptance Rate
Parallel Speedup
Cross-Worker Contradiction Yield
Judge Dependency on Unvalidated Text = 0
Canonical State Conflict = 0
```

重点指标：

```text
Marginal Evidence Gain / Added Cost
```

如果 4 worker 相比 2 worker：

```text
cost +90%
evidence gain +3%
```

则 4 worker 拓扑应被 autoresearch 淘汰。

---

# 28. Orchestration Autoresearch

Outer Loop 可以自动实验：

```text
2 vs 3 retrieval workers
按 provider 拆 vs 按 evidence axis 拆
是否独立 Skeptic
何时启用 Method Reviewer
哪个 complexity threshold 值得 spawn
context bundle 大小
TaskSpec wording
```

但评价目标是：

```text
科学质量
+ unique evidence gain
+ robustness
+ cost
```

不是“更多 Agent”。

---

# 29. 默认最终拓扑

```text
                       User
                        │
                        ▼
                Lead Researcher
                        │
              Workflow + Complexity
                        │
                 Capability DAG
                        │
          ┌─────────────┴─────────────┐
          │                           │
       Local                      Delegated
     Capability                    TaskSpec
          │                           │
          │                  Agent MCP safe_spawn
          │                           │
          │                     Worker Pool
          │                           │
          └─────────────┬─────────────┘
                        ▼
                  Staging Artifacts
                        │
              Schema + Provenance Gate
                        │
                 Scientific Gates
                        │
                        ▼
                 Single Writer Engine
                        │
                 Graph Revision
                        │
            Skeptic / Method Review
                        │
                        ▼
                 Evidence Judge
                        │
                DecisionSnapshot
```

---

# 30. 最终规则

1. **9 步协议是流程，不是 9 个 Agent。**
2. **8 个现有 role profile 不是 8 个常驻子代理。**
3. **Capability 是可复用能力，不是组织结构。**
4. **Subagent 是按需 runtime worker。**
5. **只并行真正独立的工作。**
6. **主 Agent/Lead 保持唯一 workflow control。**
7. **Canonical state 单写者。**
8. **子代理只返回 staging artifacts。**
9. **高影响 Challenge / Audit / Verdict 才强调独立性。**
10. **模型/CLI 只是 adapter，继续由 approval + safe_spawn 控制。**
11. **多代理是否值得，用 benchmark 测，不靠视觉上“很 Agentic”。**
12. **Autoresearch 可以优化编排策略，但不能修改科学不变量。**

---

# 31. 外部架构依据

本模型吸收但不照搬以下实践：

- Anthropic Multi-Agent Research：使用 orchestrator-worker，Lead 规划并派发明确边界的独立搜索任务；其公开复盘特别强调，模糊 delegation 会导致 worker 重复搜索、遗漏和 coordination overhead。
- OpenAI Practical Guide to Building Agents：优先从单 Agent 开始，只有逻辑复杂度、工具重叠或独立专业化真正需要时进入 multi-agent；需要统一用户控制时使用 manager pattern。
- Anthropic Long-running Harness：把 planner / generator / evaluator 的责任分开，并通过结构化 artifact 做跨阶段 handoff，而不是传递无限自然语言上下文。

EduEvidence 在此基础上进一步增加科学研究特有约束：

```text
provenance
evidence append-only
scientific independence
single canonical writer
protected evaluator
```

这使多代理只是执行增强，不成为科学真理来源。