# EduEvidence vNext — Autoresearch 自进化研究系统完整实施计划

> 状态：Implementation Blueprint  
> 范围：EduEvidence Skill + Research Engine + Benchmark + Agent MCP 编排 + Living Evidence  
> 配套文档：[`docs/orchestration-role-model.md`](./orchestration-role-model.md)

---

# 0. 最终定义

EduEvidence 下一阶段不增加一个新的“Autoresearch 用户功能页”，也不把现有研究流程改造成无限自主 Agent。

保持当前三个用户入口：

```text
Evidence Review
→ Decision & Pilot
→ Evaluate & Update
```

保持 Canonical 9-step Protocol：

```text
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate
→ Applicability → Intervene → Evaluate
```

在它们下面增加一个 **Autonomous Research Meta-Layer**，形成三条不同性质的闭环：

```text
┌────────────────────────────────────────────────────────────┐
│ Loop A — Evidence Autoresearch                             │
│ “当前决策最值得继续寻找哪一条证据？”                        │
│ Gap → Research Hypothesis → Experiment → Evidence Gain    │
│ → GraphRevision → Decision Drift → Next Gap               │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Loop B — Decision-to-Outcome                              │
│ “真实 Pilot 数据会不会改变当前决定？”                       │
│ Decision → Pilot → Data → Analysis → GraphRevision        │
│ → DecisionSnapshot                                        │
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Loop C — Skill Autoresearch                               │
│ “EduEvidence 这个研究系统本身还能不能做得更好？”             │
│ Hypothesis → One Change → Eval → Keep/Revert → Repeat     │
└────────────────────────────────────────────────────────────┘
```

三条循环对应三个问题：

```text
Evidence Loop：我们还缺什么知识？
Decision Loop：新证据是否改变行动？
Skill Loop：我们的研究方法本身还能不能更好？
```

最终产品定位升级为：

> **Living Decision Research Engine**  
> 不只把证据变成决定，还主动判断下一条最值得寻找的证据，并持续验证怎样让研究系统本身变得更好。

---

# 1. 核心思想来源

## 1.1 Karpathy autoresearch：吸收“实验组织代码”，不复制训练任务

`karpathy/autoresearch` 的关键设计不是“让 AI 一晚上跑很多次”，而是：

```text
固定 evaluator
固定实验预算
限制 mutation surface
先跑 baseline
一次只改一个核心变量
真实运行
机械测量
keep / discard
append-only 实验日志
git 作为长期实验记忆
```

原版刻意把：

```text
prepare.py / evaluate_bpb
```

冻结，只允许 Agent 修改 `train.py`；每次训练使用固定 5 分钟时间预算，以单一 `val_bpb` 比较，并执行：

```text
commit
→ run
→ measure
→ keep / reset
→ log
→ next experiment
```

其中 `program.md` 本质是“研究组织代码”：人类不是逐次编辑训练代码，而是定义 AI 研究员怎样组织自主实验。

EduEvidence 直接吸收以下原则：

1. **Evaluator 与研究对象分离。**
2. **Mutation surface 有边界。**
3. **Baseline 必跑。**
4. **一次实验一个主假设。**
5. **失败必须记录。**
6. **结果弱而复杂度大，不保留。**
7. **实验历史本身是未来推理输入。**
8. **循环有预算、Plateau 和停止条件。**

不照搬：

```text
单一 score 决定所有研究质量
validated evidence keep/discard
无限运行
Agent 可改 evaluator
```

参考：
- https://github.com/karpathy/autoresearch
- https://github.com/karpathy/autoresearch/blob/master/program.md

---

## 1.2 通用 Autoresearch Skill：吸收“薄路由 + 可验证目标 + plateau”

后续通用 autoresearch 实现进一步验证了几个适合 EduEvidence 的工程模式：

```text
薄 control-plane Skill
子命令 / references 按需加载
Success predicate
Round-0 baseline/dry-run
bounded iteration
holdout / adversarial verify hop
Plateau detection
checkpoint + resumable state
simplicity criterion
```

EduEvidence 不复制它的 14 个命令，但采用：

```text
Control Plane ≠ Detailed Procedures
```

这也与当前 Skill 的 progressive loading 方向一致。

参考：
- https://github.com/uditgoenka/autoresearch
- https://github.com/uditgoenka/autoresearch/blob/master/guide/autoresearch-orchestrator.md

---

## 1.3 Living Systematic Review：Autoresearch 不能破坏系统综述纪律

Cochrane 对 living systematic review 的核心定义是：

> Review 持续更新，新证据出现后被识别并纳入，而不是每次重新从零生成一个结论。

这与 EduEvidence 当前 `engine/living.py` 的：

```text
DecisionSnapshot subscription
→ incremental evidence
→ GraphRevision n+1
→ drift
```

高度一致。

Autoresearch 不替换 Living Evidence，而是让 Living Evidence 从：

```text
“监控预设 query terms”
```

升级为：

```text
“根据当前 Evidence Graph / KnowledgeGap / Decision Boundary
动态决定下一轮最有价值的检索目标”
```

参考：
- https://training.cochrane.org/handbook/current/chapter-22

---

## 1.4 Active Learning Screening：优化“先看什么”，不能决定“什么是真证据”

ASReview 等 active-learning systematic review 工具证明：

```text
机器学习可以显著改善 record screening 的排序效率
```

EduEvidence 可以吸收为：

```text
Screening Priority
```

用于回答：

> 下一篇最值得 Fetch / Screen 的候选 Source 是哪一篇？

但严格禁止把 active-learning ranking 直接解释为：

```text
证据权重
研究质量
支持结论概率
```

Ranking 只优化 screening order。

参考：
- https://asreview.nl/project/read-the-docs/

---

## 1.5 Value of Information：把“下一步研究什么”连接到 Decision

Value of Information 的核心不是“信息越多越好”，而是：

> 新信息是否足以减少当前决策的不确定性，从而避免错误行动？

完整 EVPI / EVPPI / EVSI 通常需要明确的 decision model、utility / loss 和概率分布。EduEvidence 当前没有资格默认生成这些正式统计量。

因此 vNext 首先实现：

```text
Conceptual Decision Value of Information
```

简称：

```text
DVI — Decision Value of Information
```

它是**透明的研究优先级启发式**，不是概率、不是效应量、不是正式 EVSI。

只有未来某个项目具备完整 decision-analytic model 时，才允许接入 formal VOI adapter。

参考：
- https://pubmed.ncbi.nlm.nih.gov/32113617/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC7613968/
- https://pubmed.ncbi.nlm.nih.gov/25986471/

---

# 2. 三条“宪法级”原则

保留现有：

> **Optimize for decision integrity, not answer confidence.**

新增：

> **Optimize the research process, never the conclusion.**

新增：

> **Every iteration must improve the evidence state, improve the research system, or teach us why an attempted path failed.**

这三条进入 `references/scientific-invariants.md`，并纳入 protected manifest。

---

# 3. 当前仓库的可复用地基

本次不是重建。

现有模块直接复用：

| 当前能力 | 文件/目录 | vNext 用途 |
|---|---|---|
| Canonical 9-step | `docs/architecture.md` | 不变 |
| Project/Run/Revision/DecisionSnapshot | `engine/` | 继续作为 canonical state |
| Immutable Graph Revision | `engine/graph_store.py` | Evidence Autoresearch 的写入基础 |
| KnowledgeGap derivation | `engine/gaps.py` | 加 DVI / lifecycle，不替换原推导 |
| Study Design grounding | `engine/study_design.py` | Search saturation → Pilot 的硬 gate |
| Pilot reinjection | `engine/pilot.py` / `engine/update.py` | Decision-to-Outcome Loop |
| Living Evidence | `engine/living.py` | Evidence Autoresearch 的增量 ingestion 基础 |
| Decision adjudication | `engine/tribunal.py` | 新 GraphRevision 后重算 |
| EventBus | `engine/events.py` | Autoresearch 全过程事件流 |
| Agent MCP adapter | `integrations/agent_mcp.py` | bounded worker dispatch |
| `safe_spawn()` | `integrations/agent_mcp.py` | 唯一多代理派发入口继续保留 |
| S/M/L Complexity | `scripts/complexity_gate.py` | ExecutionPlanner 输入 |
| 30 题 Benchmark | `benchmarks/questions.jsonl` | DEV eval 起点 |
| Gold annotations | `benchmarks/annotations/` | scientific eval 起点 |
| Empirical benchmark | `benchmarks/empirical/` | Outer Loop 真实评估 |
| Graph deterministic metrics | `benchmarks/evaluator/v2_graph_metrics.py` | L0 contract gates |
| CI | `.github/workflows/ci.yml` | protected / autoresearch gate 扩展 |

---

# 4. 必须消除的架构混淆

当前仓库同时存在：

```text
9 个 Protocol Stage
8 个 skill/agents profiles
多个 skill/sub-skills capabilities
Agent MCP multi-model dispatch
```

vNext 唯一定义：

```text
Protocol Stage
≠ Scientific Role
≠ Capability
≠ Worker/Subagent
≠ Model/CLI
```

完整规则见：

[`docs/orchestration-role-model.md`](./orchestration-role-model.md)

核心一句：

> **Parallelize independent evidence acquisition; serialize canonical state transitions.**

以及：

> **Subagent count is determined by task decomposability, not role count.**

---

# 5. 最终总体架构

```text
                          USER
                            │
                            ▼
                    EduEvidence Skill
                            │
          Evidence Review / Decision & Pilot /
                 Evaluate & Update
                            │
                            ▼
                     Lead Researcher
                            │
               Workflow + Complexity Gate
                            │
                     Capability DAG
                            │
              ┌─────────────┴────────────┐
              │                          │
              ▼                          ▼
       Platform Native            Agent MCP Enhanced
         Local execution          bounded subagents
              │                          │
              └─────────────┬────────────┘
                            ▼
                    Staging Artifacts
                            │
            Schema / Provenance / Science Gates
                            │
                            ▼
                    Single Writer Engine
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        Evidence Graph  Decision State  Research Memory
              │
              ▼
        GraphRevision N
              │
         ┌────┴───────────────┐
         ▼                    ▼
 Evidence Autoresearch   Decision-to-Outcome
         │                    │
         └─────────┬──────────┘
                   ▼
             GraphRevision N+1


Repository / Skill Implementation
              │
              ▼
        Skill Autoresearch
 Hypothesis → Candidate → Protected Eval
         → Keep/Revert → SkillRevision
```

---

# 6. Canonical State 命名重新冻结

避免“Revision”概念混乱。

## 现实研究状态

```text
Project
Run
GraphRevision
DecisionSnapshot
ResearchIteration
KnowledgeGap
```

### GraphRevision

表示：

> 我们对现实问题所拥有的 Evidence Graph 变了。

例如：

```text
GraphRevision 7 → 8
```

---

### DecisionSnapshot

表示：

> 基于某个 GraphRevision 的当前 decision-bounded adjudication。

---

### ResearchIteration

表示：

> Evidence Autoresearch 做过的一轮“下一条证据”实验。

它可以：

```text
找到 valid evidence
只找到重复 evidence
没有找到 eligible evidence
tool failure
search saturation evidence
```

ResearchIteration 不等于 GraphRevision。

没有新 validated evidence 时：

```text
ResearchIteration +1
GraphRevision 不变
```

这是必须保留的信息。

---

## Skill 自身状态

```text
SkillRevision
SkillExperiment
EvalSnapshot
```

### SkillRevision

表示：

> EduEvidence 研究系统本身的一版实现。

它与 GraphRevision 完全分离。

---

# 7. Loop A — Evidence Autoresearch

## 7.1 目标

现在的 Evidence Review 主要回答：

```text
当前证据支持什么？
```

Evidence Autoresearch 再回答：

```text
如果我们还允许花下一单位 research budget，
最值得获取哪类新证据？
```

---

## 7.2 基本循环

```text
READ STATE
Project + GraphRevision N + DecisionSnapshot N
+ KnowledgeGaps + previous ResearchIterations
        ↓
RANK GAPS
Decision Value of Information
        ↓
SELECT ONE
one KnowledgeGap / one research objective
        ↓
HYPOTHESIZE
one falsifiable research strategy
        ↓
PLAN
TaskSpec + budget + termination
        ↓
EXECUTE
Retrieve / Fetch / Validate / Extract
+ Challenge / Audit when triggered
        ↓
MEASURE
Evidence Gain / Search Yield / Decision Relevance
        ↓
COMMIT
valid evidence append-only → GraphRevision N+1
or no-change iteration log
        ↓
RE-ADJUDICATE
candidate DecisionSnapshot / drift
        ↓
LEARN
append ResearchIteration + negative search memory
        ↓
NEXT
recompute gap priority
```

---

# 8. KnowledgeGap vNext

当前 `engine/gaps.py` 的强项是：Gap 来自真实 graph coverage，而不是自由文本 future work。

保留这个定义。

新增 metadata：

```json
{
  "gap_id": "GAP-...",
  "status": "open",
  "gap_type": "missing_transfer",
  "derived_from_graph_revision": 8,
  "decision_relevance": "high",
  "uncertainty_source": "directness",
  "minimum_useful_evidence": {
    "population": "novice CS1",
    "outcome": "independent_problem_solving",
    "measurement_context": "without_ai"
  },
  "research_priority": {
    "dvi_band": "high",
    "rationale": []
  },
  "attempted_strategy_ids": [],
  "negative_search_ids": [],
  "resolution_status": "unresolved"
}
```

---

# 9. Gap Lifecycle

新增 lifecycle：

```text
OPEN
↓
PRIORITIZED
↓
SEARCHING
↓
PARTIALLY_RESOLVED
↓
RESOLVED
```

另一条：

```text
OPEN
↓
SEARCHING
↓
SEARCH_SATURATED
↓
EMPIRICAL_EVIDENCE_NEEDED
↓
StudyDesign / Pilot
```

另一条：

```text
OPEN
↓
LOW_DECISION_VALUE
```

Low DVI 不代表“永远不研究”，只是当前 decision context 下不优先。

---

# 10. DVI — Decision Value of Information

## 10.1 vNext 只实现 Conceptual DVI

禁止输出：

```text
“这项研究有 83.7% 的信息价值”
```

也禁止把 DVI 称为正式 EVPI / EVSI。

DVI 是透明优先级模型。

---

## 10.2 排序维度

每个 Gap 计算以下 ordinal dimensions：

```text
Decision Sensitivity
当前 decision 对这个未知量有多敏感？

Current Uncertainty
当前 evidence 对它有多不确定？

Directness Deficit
缺的是直接 outcome 证据还是仅补充性信息？

Applicability Relevance
是否直接关系目标人群 / 场景？

Expected Evidence Availability
二手证据是否可能存在？

Research Cost
预计检索/筛选/新研究成本？

Risk / Irreversibility
如果现在做错决定，后果是否高？
```

---

## 10.3 结果只分 band

```text
HIGH
MEDIUM
LOW
```

同时返回 rationale：

```json
{
  "gap_id": "GAP-...",
  "dvi_band": "HIGH",
  "drivers": [
    "当前 ADOPT/PILOT 边界主要被 independent transfer 缺失限制",
    "目标人群完全匹配",
    "已有候选文献线索"
  ],
  "cost_band": "LOW",
  "next_research_mode": "secondary_evidence_search"
}
```

排序必须可解释。

---

# 11. 一轮只能有一个主 Research Hypothesis

示例：

```json
{
  "research_iteration_id": "RIT-0017",
  "gap_id": "GAP-transfer-novice",
  "hypothesis": "针对 novice CS1 + without-AI transfer test 的定向检索，将发现至少一条比当前证据更直接的 eligible Study",
  "strategy_id": "STRAT-targeted-transfer-v1",
  "expected_gain": "directness",
  "budget": {
    "max_queries": 6,
    "max_candidates": 30,
    "max_fulltext_fetches": 12
  }
}
```

禁止一轮同时：

```text
换检索算法
换 OutcomeClassifier
改 Gap ranking
加新数据库
改 Method Audit prompt
```

否则无法归因。

---

# 12. Research Experiment 类型

首版只允许明确枚举：

```text
TARGETED_RETRIEVAL
COUNTER_EVIDENCE_RETRIEVAL
APPLICABILITY_RETRIEVAL
TEMPORAL_REFRESH
CITATION_CHAINING
SCREENING_PRIORITY
SOURCE_RECOVERY
```

未来再增加。

它们都是：

> 获取证据的研究策略实验。

不是：

> 自动改变科学规则。

---

# 13. Evidence 绝对 Append-only

这是从 autoresearch 移植时最重要的差异。

代码候选可以：

```text
keep / revert
```

Validated Evidence 不可以：

```text
支持当前结论 → keep
反对当前结论 → discard
```

只要符合：

```text
真实来源
符合纳排标准
provenance 可验证
schema 合法
```

就必须保留，不论：

```text
support
contradict
neutral
null
```

科学不变量：

> **Never optimize the evidence set toward a preferred conclusion.**

---

# 14. Negative Search Result 也是 Artifact

新增：

```text
NegativeSearchRecord
```

记录：

```json
{
  "negative_search_id": "NSR-...",
  "research_iteration_id": "RIT-...",
  "gap_id": "GAP-...",
  "queries": [],
  "providers": [],
  "candidate_count": 23,
  "fetched_count": 8,
  "eligible_count": 0,
  "exclusion_reasons": {},
  "searched_at": "...",
  "scope": {},
  "conclusion": "no_eligible_evidence_found_within_search_scope"
}
```

禁止写：

```text
“No evidence exists.”
```

只能说：

```text
“在本轮明确 search scope 内未找到 eligible evidence。”
```

---

# 15. Search Saturation Gate

不能无限搜论文。

每个 Gap 追踪：

```text
new independent studies per iteration
new eligible findings per iteration
new direct-outcome findings
new population coverage
new contradiction yield
new DOI/source uniqueness
Decision Boundary delta
query/provider novelty
```

当连续多轮出现：

```text
unique eligible evidence ≈ 0
直接证据增量 = 0
重复来源持续升高
Decision Boundary 无变化
新的 search strategies 已基本耗尽
```

标记：

```text
SEARCH_SATURATED
```

首版不用一个武断的单阈值。

使用：

```text
2–3 consecutive low-yield iterations
+ strategy diversity exhausted
+ no high-value unresolved retrievable path
```

作为 deterministic + policy 判定。

---

# 16. 自动从 Literature 转向 Pilot 的条件

必须同时满足：

```text
Gap DVI = HIGH
Gap 对 Decision material
Secondary Search = saturated
Gap 仍 unresolved
新实证研究在伦理 / 可行性上允许
```

然后：

```text
KnowledgeGap
→ EMPIRICAL_EVIDENCE_NEEDED
→ StudyDesign grounding gate
→ preregistration-ready Pilot
```

这直接复用当前：

```text
No Study Design Without Grounded Gap
```

---

# 17. Evidence Autoresearch 的停止条件

任何一项满足即可停：

```text
目标 Gap RESOLVED
Decision 对该 Gap 不再敏感
所有 HIGH-DVI gaps 已处理
research budget exhausted
search saturation
需要新的 empirical study
用户要求停止
工具不可用且无有效降级路径
```

不允许“NEVER STOP”。

研究系统必须 bounded。

---

# 18. Decision 的自动化边界

Evidence Autoresearch 可以自动：

```text
生成新的 GraphRevision
运行 deterministic tribunal
生成 candidate DecisionSnapshot / DriftReport
```

但不得自动：

```text
执行真实世界干预
改变学校政策
开始人类受试 Pilot
对高影响 Decision 自动 promote 为 accepted operational decision
```

新增：

```text
DecisionSnapshot.status
= candidate | reviewed | accepted
```

若迁移成本过高，首版可先在 `extensions.review_status` 实现，再升级 schema。

Living refresh 生成：

```text
candidate
```

用户 / human gate 接受后：

```text
accepted
```

---

# 19. Loop B — Decision-to-Outcome 保持现有语义

不重写 `engine/pilot.py`。

保持：

```text
Decision
→ grounded StudyDesign
→ PilotRun
→ privacy-safe Data
→ validated AnalysisRun
→ local Finding
→ GraphRevision
→ DecisionSnapshot
```

Autoresearch 只负责在前面回答：

> 为什么现在应该从 literature 转入这个 Pilot？

---

# 20. Loop C — Skill Autoresearch

## 20.1 目标

自动实验：

> 怎样让 EduEvidence 的真实研究质量更高，同时不破坏科学纪律、鲁棒性和成本？

---

## 20.2 基本循环

```text
BASELINE
↓
Read previous experiments
↓
Propose ONE hypothesis
↓
Create candidate branch/worktree
↓
Modify allowed surface
↓
Fast deterministic gates
↓
DEV benchmark
↓
If promising → repeated empirical eval
↓
HOLDOUT / adversarial verify
↓
Promotion policy
├─ KEEP → candidate best branch
├─ REJECT → discard candidate code
├─ RETEST → more repeats
└─ HUMAN_REVIEW → ambiguous/high-impact
↓
Log everything
↓
Next experiment
```

---

# 21. Protected Scientific Core

新增：

```text
autoevolve/protected.manifest.yaml
```

首版保护：

```yaml
protected:
  - benchmarks/annotations/**
  - benchmarks/holdout/**
  - benchmarks/evaluator/**
  - schemas/**
  - references/scientific-invariants.md
  - scripts/pre_verdict_gate.py
  - scripts/compute_confidence.py
  - engine/graph_store.py::revision_integrity
  - engine/study_design.py::grounding_gate
  - tests/scientific_invariants/**
```

Runner 在实验前后计算 hash。

任何 protected mutation：

```text
EXPERIMENT_INVALID
```

不进入评分。

---

# 22. Mutation Surface

## Tier A — Safe Mutable

适合自动实验：

```text
retrieval query templates
search ordering
Challenge prompts
context packing
role instructions
workflow wording
few-shot examples
report phrasing
routing heuristics that do not alter scientific invariants
model routing / cost strategy
cache strategy
```

---

## Tier B — Controlled Mutable

需要完整 regression：

```text
OutcomeClassifier implementation
ranking weights
Complexity Gate thresholds
Gap priority heuristics
Graph linking heuristics
retrieval dedupe heuristics
orchestration policy
```

---

## Tier C — Protected

不可自动修改：

```text
Gold / Holdout
Evaluator definitions
Schema ground truth
No Direct Learning Evidence → No ADOPT
No False Precision
Fail-closed causal analysis
Synthetic/real separation
StudyDesign grounding
privacy / ethics constraints
canonical revision integrity
```

---

# 23. Outer Loop 不是单分数优化

Karpathy 原版可使用：

```text
val_bpb ↓
```

EduEvidence 必须采用：

```text
Constraint-first Pareto Evaluation
```

---

# 24. 评估层级

## L0 — Scientific / Contract Hard Gates

任意失败：

```text
REJECT
```

包括：

```text
Schema validity
Graph traceability
Study identity correctness
Independent study counting
No false precision
No unsupported ADOPT
Synthetic-data separation
Grounded Gap requirement
Protected file integrity
PII / privacy guards
```

当前 `v2_graph_metrics.py` 继续作为其中一部分。

它明确只能测 software / contract conformance，不能声称 scientific truth；该边界保持。

---

## L1 — Scientific Correctness

```text
Outcome Separation
Citation Support
Contradiction precision/recall
Decision Calibration
Scope Calibration
Methodology issue detection
Gap correctness
```

使用：

```text
gold annotations
human/judge annotations where appropriate
```

---

## L2 — Research Quality

新增：

```text
Direct Evidence Gain
Unique Eligible Evidence Yield
Counter-evidence Yield
Applicability Coverage
Gap Resolution Rate
Research Saturation Efficiency
Decision-relevant Evidence Gain
```

---

## L3 — Robustness

```text
S/M/L
multiple domains
multiple model families
repeated runs
retrieval provider variation
missing-data scenarios
adversarial cases
```

---

## L4 — Efficiency

```text
token
cost
latency
search calls
fetch calls
subagent count
parallel speedup
```

---

## L5 — Simplicity

```text
LOC delta
SKILL.md token load
number of rules
number of branches
new dependencies
maintenance surface
```

同等质量：

```text
更简单 = 更优
```

---

# 25. Promotion Policy

先看 hard gates。

```text
if L0 fails:
    REJECT
```

然后：

```text
if core scientific metric material regression:
    REJECT
```

否则比较 Pareto：

```text
quality
robustness
efficiency
simplicity
```

状态：

```text
KEEP
REJECT
RETEST
HUMAN_REVIEW
CRASH
INVALID
```

---

# 26. Noise Floor 与重复运行

LLM 输出不是 deterministic benchmark。

保持当前 benchmark 的：

```text
repeats >= 3
prefer 5
mean + variance / CI
```

并进一步：

```text
小于 noise floor 的提升不得自动 KEEP
```

候选状态：

```text
candidate delta < empirical noise
→ RETEST
```

不要让 +0.2% 的偶然波动累计成“自我进化”。

---

# 27. Benchmark 三分区

当前 30 题不能让 Agent 反复看到全部内容。

重组：

```text
benchmarks/
├── dev/
├── holdout/
├── adversarial/
├── temporal/
└── evaluator/
```

---

## DEV

Agent 可以读取。

用途：

```text
fast iteration
```

---

## HOLDOUT

Candidate 不能读取题目与 gold。

只允许 protected evaluator 调用。

用途：

```text
promotion gate
```

---

## ADVERSARIAL

至少覆盖：

```text
fake DOI
fabricated citation
search snippet pretending to be evidence
missing CI
same Study split into multiple Findings
task performance treated as learning
population mismatch
subgroup overclaim
contradictory evidence
retracted / corrected source
synthetic evidence leakage
prompt injection in source content
PII in empirical dataset
singular DID / invalid causal design
```

---

## TEMPORAL

用于：

```text
recent evidence refresh
new publications
model/provider drift
```

不能 hard-code 成永久 gold；保留 evaluation timestamp。

---

# 28. Benchmark Hacking Guard

任何实验不得：

```text
修改 evaluator
读取 holdout gold
减少 benchmark workload
跳过失败题
把 unknown 当 pass
针对 question ID 写特例
通过少输出降低 unsupported rate
```

防止“少说少错”：

```text
precision + recall 必须成对报告
```

例如：

```text
Contradiction precision
Contradiction recall
```

同时看。

---

# 29. Experiment Memory

新增：

```text
autoevolve/
├── program.md
├── config.yaml
├── protected.manifest.yaml
├── results.tsv
├── experiments.jsonl
├── best.json
├── ideas.md
├── findings.md
└── runs/
```

---

# 30. `results.tsv`

```text
experiment_id
parent_revision
candidate_commit
scope
hypothesis
eval_suite_hash
model_manifest
repeats
hard_gates
science_score
research_score
robustness
cost
latency
complexity_delta
status
description
```

失败同样写入。

`results.tsv` 是 append-only。

---

# 31. `experiments.jsonl`

每轮保留完整机器可读结构：

```json
{
  "experiment_id": "EXP-0017",
  "hypothesis": "显式拆分 direct evidence 与 transfer query 能提高 contradiction/directness recall",
  "why": "E12/E15 显示当前 retrieve 在 outcome axis 上混合",
  "change": [],
  "baseline": {},
  "candidate": {},
  "result": "KEEP",
  "interpretation": "...",
  "what_this_rules_out": [],
  "next_ideas": []
}
```

Research Memory 不只保存 score。

---

# 32. Git Workflow

Autoresearch 永远不直接在 `main` 上实验。

```text
main
└── autoresearch/<run-tag>
    ├── experiment commit 1
    ├── experiment commit 2
    └── best candidate
```

更稳妥实现：

```text
git worktree
```

每个 candidate 有独立工作树。

---

# 33. 自动 Promotion 边界

自动允许：

```text
在 autoresearch branch 内 keep / revert
更新 best candidate pointer
生成 PR 内容
```

自动禁止：

```text
merge main
release
修改 protected core
删除 benchmark history
force push
真实部署
```

最终 merge 人工确认。

---

# 34. Plateau / Ceiling

Skill Autoresearch 不无限运行。

默认：

```text
max_experiments_per_session = 25
```

每日 unattended 可配置：

```text
max_experiments = 50
max_cost
max_wall_time
```

Plateau：

```text
连续 5 个 valid experiments
没有超过 noise floor 的 Pareto improvement
```

停止并输出：

```text
plateau report
best revision
near misses
next hypotheses
```

---

# 35. 每日自动进化模式

未来 CLI：

```bash
eduevidence evolve run --budget daily
```

配置：

```yaml
schedule_profile: daily
max_experiments: 20
max_cost_usd: 5
max_wall_minutes: 180
mutation_tiers:
  - safe
allow_controlled: false
promotion: branch_only
```

每次运行结束：

```text
Daily Evolution Report
├── baseline
├── experiments attempted
├── kept
├── rejected
├── crashes
├── best candidate
├── metric deltas
├── cost
├── protected integrity
└── next ideas
```

初版不让 daily mode 自动改 Tier B。

---

# 36. 多角色 / 子代理编排

完整权威定义：

[`docs/orchestration-role-model.md`](./orchestration-role-model.md)

核心改变：

```text
8 role profiles
≠
8 permanent agents
```

---

# 37. 新增 Lead Researcher / ExecutionPlanner

逻辑组件：

```text
engine/orchestration/planner.py
```

职责：

```text
Workflow routing
Complexity classification
Capability DAG
local vs delegate decision
parallel groups
TaskSpec creation
budget allocation
independence requirements
fallback
```

它不直接调用外部 daemon。

执行仍走：

```text
integrations/agent_mcp.py::safe_spawn()
```

---

# 38. TaskSpec

新增 schema：

```text
schemas/vNext/task-spec.schema.json
```

必须包括：

```text
task_id
run_id
base_revision
role_profile
objective
reason_for_delegation
input_artifacts
allowed_capabilities
forbidden_actions
scope
budget
output_contract
termination
```

没有 TaskSpec 不 spawn。

---

# 39. Single Writer

任何 Worker 只能输出：

```text
Staging Artifact
```

只有主引擎可以：

```text
Graph commit
DecisionSnapshot write
KnowledgeGap persistent update
StudyDesign write
```

并行只发生在证据获取 / 分析。

Canonical State transition 串行。

---

# 40. 默认 S/M/L 拓扑

## S

```text
Lead only
subagents = 0
```

---

## M

典型：

```text
Lead
├─ direct/support retrieval worker
├─ counter/risk retrieval worker
├─ optional Method Reviewer
└─ Judge / Lead adjudication
```

典型 active workers：

```text
2–4
```

---

## L

```text
Lead
│
├─ Retrieval Worker — direct causal
├─ Retrieval Worker — transfer/retention
├─ Retrieval Worker — harms/null/counter
├─ Retrieval Worker — applicability/freshness
│
├─ deterministic merge/dedupe
├─ optional Extraction batches
│
├─ independent Skeptic
├─ Method Reviewer
│
├─ Single Writer Graph commit
├─ Evidence Judge
└─ high-impact Independent Final Review
```

默认：

```text
parallel active workers <= 6
```

禁止 recursive swarm。

---

# 41. Worker 按 Evidence Axis 拆，不按 Provider 拆

优先：

```text
直接效果
transfer / retention
negative / null / risks
population / subgroup
current/fresh evidence
```

而不是：

```text
Google Worker
Crossref Worker
Semantic Scholar Worker
```

Provider 是工具，不是 epistemic objective。

---

# 42. Independence 的三种含义

```text
Search independence
Context independence
Model-family independence
```

只在需要时使用。

Skeptic / final reviewer 才优先强调：

```text
context + model-family independence
```

Retriever workers 不必浪费成本全部使用不同旗舰模型。

---

# 43. Multi-agent Autoresearch

Outer Loop 可以自动实验：

```text
1 vs 2 vs 4 retrieval workers
provider split vs evidence-axis split
Skeptic always vs triggered
Method Review batch size
TaskSpec detail level
worker context bundle size
S/M/L spawn thresholds
fast/strong routing
```

优化目标：

```text
Marginal Evidence Gain / Added Cost
```

不是：

```text
Agent 数量越多越高级
```

---

# 44. Orchestration Metrics

新增：

```text
Duplicate Search Rate
Unique Eligible Evidence / Worker
Coverage Gain / Worker
Counter Evidence Yield
Artifact Acceptance Rate
Worker Failure Recovery Rate
Coordination Token Cost
Parallel Speedup
Canonical State Conflict
Unvalidated Text Used by Judge
```

硬目标：

```text
Canonical State Conflict = 0
Unvalidated Text Used by Judge = 0
```

---

# 45. EventBus 新事件

## Evidence Autoresearch

```text
autoresearch.evidence.started
autoresearch.gap.ranked
autoresearch.hypothesis.created
autoresearch.iteration.started
autoresearch.search.completed
autoresearch.iteration.no_gain
autoresearch.iteration.evidence_gain
autoresearch.saturation.detected
autoresearch.empirical_needed
autoresearch.evidence.completed
```

## Skill Autoresearch

```text
autoevolve.session.started
autoevolve.experiment.created
autoevolve.candidate.built
autoevolve.eval.completed
autoevolve.candidate.kept
autoevolve.candidate.rejected
autoevolve.candidate.retest
autoevolve.plateau
autoevolve.session.completed
```

## Orchestration

```text
orchestrator.plan.created
orchestrator.task.dispatched
orchestrator.task.completed
orchestrator.task.failed
orchestrator.artifact.accepted
orchestrator.artifact.rejected
```

---

# 46. CLI 设计

不破坏现有命令。

新增两个命令域：

```text
research auto

evolve
```

---

## Evidence Autoresearch

```bash
eduevidence research auto start --project PRJ-...
eduevidence research auto step  --project PRJ-...
eduevidence research auto status --project PRJ-...
eduevidence research auto report --project PRJ-...
eduevidence research auto stop --project PRJ-...
```

`step` 永远只执行一轮，便于测试。

`start` 才执行 bounded loop。

---

## Skill Autoresearch

```bash
eduevidence evolve init
eduevidence evolve baseline
eduevidence evolve run --max-experiments 20
eduevidence evolve status
eduevidence evolve report
eduevidence evolve best
eduevidence evolve prepare-pr
```

不提供：

```text
auto-merge-main
```

---

# 47. 新目录

```text
eduevidence/
├── autoevolve/
│   ├── program.md
│   ├── config.yaml
│   ├── protected.manifest.yaml
│   ├── results.tsv
│   ├── experiments.jsonl
│   ├── best.json
│   └── runs/
│
├── engine/
│   ├── autoresearch/
│   │   ├── controller.py
│   │   ├── gap_priority.py
│   │   ├── hypothesis.py
│   │   ├── iteration.py
│   │   ├── saturation.py
│   │   ├── research_memory.py
│   │   └── contracts.py
│   │
│   ├── orchestration/
│   │   ├── planner.py
│   │   ├── role_registry.py
│   │   ├── task_spec.py
│   │   ├── worker_result.py
│   │   └── merge.py
│   │
│   └── autoevolve/
│       ├── controller.py
│       ├── mutation_scope.py
│       ├── evaluator.py
│       ├── promotion.py
│       ├── experiment_log.py
│       └── git_workspace.py
│
├── skill/
│   ├── roles/
│   │   └── registry.yaml
│   └── agents/                 # compatibility during migration
│
├── benchmarks/
│   ├── dev/
│   ├── holdout/
│   ├── adversarial/
│   ├── temporal/
│   └── evaluator/
│
└── schemas/vNext/
```

---

# 48. 新 Schema

首版：

```text
research-iteration.schema.json
research-strategy.schema.json
negative-search-record.schema.json
gap-priority.schema.json
task-spec.schema.json
worker-result.schema.json
execution-plan.schema.json
skill-experiment.schema.json
eval-snapshot.schema.json
autoevolve-session.schema.json
```

不立即重写原 v2/v3/v4 schema。

---

# 49. ResearchIteration Schema 核心字段

```text
iteration_id
project_id
base_graph_revision
gap_id
hypothesis
strategy
budget
execution_plan_id
search_attempts
candidate_sources
validated_evidence_ids
negative_search_ids
evidence_gain
new_graph_revision|null
decision_snapshot_id|null
status
started_at
completed_at
```

状态：

```text
completed_gain
completed_no_gain
search_saturated
empirical_needed
budget_exhausted
tool_failure
invalid
```

---

# 50. SkillExperiment Schema 核心字段

```text
experiment_id
session_id
parent_skill_revision
hypothesis
mutation_scope
changed_files
candidate_commit
baseline_eval_id
candidate_eval_id
protected_hash_before
protected_hash_after
status
promotion_reason
complexity_delta
```

---

# 51. Dashboard / Web Studio

不是 P0。

在 Engine 稳定后新增两个面板：

## Research Loop

```text
Current Decision
Open Gaps ranked by DVI
Current Research Hypothesis
Iterations
Evidence Gain
Search Saturation
Decision Drift
```

## Skill Evolution

```text
Baseline vs Best
Experiment Timeline
Keep / Reject
Metric Radar
Cost
Plateau
Protected Core status
```

不要做“8 个 Agent 头像同时工作”。

展示：

```text
Capability DAG + active TaskSpec
```

---

# 52. SKILL.md 改造原则

不要把整套 Autoresearch 写进顶层 `SKILL.md`。

SKILL.md 只加入：

```text
Autonomous Research Meta-Layer
```

约 20–35 行，说明：

```text
何时启用 Evidence Autoresearch
何时启用 Skill Autoresearch（仅维护者/开发模式）
科学不变量
references 路由
```

详细内容进入：

```text
references/autoresearch.md
references/orchestration.md
references/evaluation-policy.md
```

保持 SKILL.md control-plane。

---

# 53. Skill 自进化绝不能改用户研究状态

Skill Autoresearch 使用 fixture / benchmark project。

不得对真实用户 Project：

```text
自动修改 Graph
生成新的 accepted Decision
删除证据
重写研究历史
```

Outer Loop 与用户数据物理隔离。

---

# 54. Evidence Autoresearch 绝不能改 Skill

相反：

Evidence Autoresearch 只可以影响：

```text
Project research state
ResearchIteration log
GraphRevision
candidate DecisionSnapshot
```

不能修改 repo：

```text
SKILL.md
retrieval prompts
engine code
evaluator
```

两条 loop 权限完全分离。

---

# 55. Agent MCP 权限

继续遵守：

```text
Detect
→ Recommend
→ explicit user approval
→ safe_spawn
```

Autoresearch 不绕过用户已经建立的模型 / CLI authorization。

在 unattended Skill Autoresearch session 中，只能使用：

```text
session 开始前已批准的 model/CLI allowlist
```

不能中途自行授权新模型。

---

# 56. 安全与研究诚信

硬规则：

```text
No evaluator mutation
No holdout leakage
No evidence deletion because unfavorable
No fake precision
No fake citations
No autonomous human-subject study launch
No PII upload
No automatic main merge
No recursive unbounded agent spawning
No evidence-set optimization toward desired verdict
```

---

# 57. Tests — Evidence Autoresearch

新增：

```text
tests/test_autoresearch_gap_priority.py
tests/test_autoresearch_iteration.py
tests/test_autoresearch_negative_search.py
tests/test_autoresearch_saturation.py
tests/test_autoresearch_transition_to_pilot.py
tests/test_autoresearch_append_only.py
tests/test_autoresearch_decision_drift.py
```

必须覆盖：

```text
negative evidence 不被丢弃
no-result 不被写成 no evidence exists
no-gain iteration 不产生 GraphRevision
重复 evidence 不产生 revision
high-DVI saturated gap → empirical_needed
low-DVI gap 不自动生成 Pilot
```

---

# 58. Tests — Orchestration

新增：

```text
tests/test_execution_planner.py
tests/test_task_spec.py
tests/test_worker_merge.py
tests/test_single_writer.py
tests/test_role_registry.py
tests/test_orchestration_budget.py
```

硬测：

```text
S task = 0 workers by default
M can selectively spawn
L <= configured worker cap
worker cannot graph_commit
Judge only consumes validated artifacts
no direct spawn bypasses safe_spawn
```

---

# 59. Tests — Skill Autoresearch

新增：

```text
tests/test_autoevolve_protected_manifest.py
tests/test_autoevolve_experiment_log.py
tests/test_autoevolve_promotion.py
tests/test_autoevolve_noise_floor.py
tests/test_autoevolve_plateau.py
tests/test_autoevolve_holdout_isolation.py
tests/test_autoevolve_git_workspace.py
```

---

# 60. CI 扩展

现有三 job 继续。

新增：

```text
scientific-invariants
protected-manifest
orchestration-contract
```

PR 来自 `autoresearch/*` 时额外运行：

```text
DEV regression
holdout promotion gate
adversarial gate
complexity report
```

Empirical model eval 成本较高：

```text
不放在每个普通 commit
```

只在：

```text
manual workflow_dispatch
nightly / scheduled environment
candidate promotion
```

运行。

---

# 61. Phase 0 — Architecture Freeze

交付：

```text
docs/autoresearch-evolution-plan.md
docs/orchestration-role-model.md
references/scientific-invariants.md
```

冻结：

```text
3 loops
5 orchestration concepts
Single Writer
protected evaluator
append-only evidence
```

验收：

所有核心文档不再把 8 role 写成 8 常驻 Agents。

---

# 62. Phase 1 — Orchestration Clarity

实现：

```text
skill/roles/registry.yaml
ExecutionPlanner
TaskSpec
WorkerResult
ExecutionPlan artifact
```

先不做 Autoresearch。

原因：

> 不能在不清晰的 agent topology 上建立自主循环。

验收：

```text
S/M/L deterministic plan tests
Agent MCP approval tests 全通过
safe_spawn 仍是唯一 spawn path
```

---

# 63. Phase 2 — Evidence Research Memory

实现：

```text
ResearchIteration
NegativeSearchRecord
ResearchStrategy
append-only iteration history
```

此阶段仍由人工选择 Gap。

CLI：

```bash
eduevidence research auto step --gap GAP-...
```

验收：

```text
一轮可完整复现
no-gain 正确记录
Graph 只在 valid evidence 时 revision
```

---

# 64. Phase 3 — Gap Priority + DVI

扩展 `engine/gaps.py`，不替换现有 coverage derivation。

新增：

```text
DVI band
minimum useful evidence
researchability
research cost band
```

验收 fixture：

CS1 案例中：

```text
missing independent transfer
```

应优先于：

```text
低 decision relevance 的满意度缺口
```

同时必须给出可读 rationale。

---

# 65. Phase 4 — Bounded Evidence Autoresearch

实现 controller：

```text
rank
→ select
→ hypothesize
→ dispatch
→ validate
→ measure
→ log
→ next
```

首版：

```text
max_iterations = 5
```

默认不是无限。

验收：

```text
可以跑完整 3–5 iteration
worker failure 可恢复
不重复同一个失败策略
```

---

# 66. Phase 5 — Search Saturation → Pilot Bridge

实现：

```text
saturation.py
```

然后连接：

```text
SEARCH_SATURATED
+ HIGH DVI
→ EMPIRICAL_EVIDENCE_NEEDED
→ existing StudyDesign gate
```

验收：

```text
不能直接凭“资料少”生成 Pilot
必须有 Gap + attempts + saturation evidence
```

---

# 67. Phase 6 — Skill Autoresearch MVP

先只允许 Tier A mutation。

运行：

```text
baseline
→ one change
→ deterministic gates
→ DEV
→ keep/reject
→ log
```

不做 nightly。

验收：

```text
protected mutation = INVALID
bad candidate 自动回退
results.tsv append-only
best pointer 正确
```

---

# 68. Phase 7 — Holdout / Adversarial / Empirical Promotion

实现：

```text
DEV / HOLDOUT separation
noise floor
repeated empirical run
adversarial suite
Pareto promotion
```

验收：

不能通过：

```text
输出更少
只在 DEV 特化
破坏 contradiction recall
增加巨大复杂度换微小收益
```

的方式 KEEP。

---

# 69. Phase 8 — Daily Evolution

加入：

```text
bounded daily profile
checkpoint
plateau
budget
PR preparation
```

初版只：

```text
branch_only
```

绝不自动 merge。

---

# 70. Phase 9 — UI / Showcase

Research Studio 增加：

```text
Decision State
Gap Priority
Autoresearch Iterations
Research Saturation
Revision Diff
```

Developer 模式增加：

```text
Skill Evolution
```

公开报告默认不展示内部自我优化 debug 信息。

---

# 71. 文件变更矩阵

| 文件/目录 | 动作 |
|---|---|
| `SKILL.md` | 小改：加入 meta-layer 路由，不塞实现细节 |
| `docs/architecture.md` | Phase 1 后更新 5 概念分层 |
| `docs/living-evidence.md` | Phase 4 后加入主动 Gap research loop |
| `docs/benchmark.md` | Phase 7 更新 DEV/HOLDOUT/ADV |
| `docs/agent-mcp-enhanced-mode.md` | Phase 1 改成 ExecutionPlanner → TaskSpec → safe_spawn |
| `skill/agents/*` | 先兼容保留 |
| `skill/roles/registry.yaml` | 新增 |
| `engine/gaps.py` | 扩展 priority metadata，不改 coverage truth |
| `engine/living.py` | 复用 ingestion；增加 controller adapter，不塞 orchestrator |
| `engine/autoresearch/*` | 新增 |
| `engine/orchestration/*` | 新增 |
| `engine/autoevolve/*` | 新增 |
| `integrations/agent_mcp.py` | Phase 1 改读取 registry / TaskSpec，保留 gate |
| `benchmarks/*` | 重组 eval partitions，保持历史结果 |
| `.github/workflows/ci.yml` | 加 scientific/protected gates |

---

# 72. 不做的架构

明确排除：

```text
“八 Agent 一起跑所有问题”
“每一个 Stage 一个 Agent”
“无限 swarm”
“Agent 互相自由聊天决定研究方向”
“自动删除不利证据”
“用一个综合 LLM Judge score 决定科学质量”
“自动改 evaluator 让 benchmark 变好”
“自动 merge main”
“没有 Gap 就自动设计研究”
“搜不到三轮就声称不存在证据”
“DVI 伪装成 EVPI 概率”
```

---

# 73. 旗舰 CS1 案例的最终运行示例

用户问题：

> 大一 C/Python 是否应该允许生成式 AI 编程助手？

初始 Evidence Review：

```text
Task Performance：有收益
Independent Learning：冲突
Transfer：不足
Retention：不足
Decision：PILOT
```

Graph 生成：

```text
GAP-101 missing_transfer
GAP-102 missing_retention
GAP-103 population heterogeneity
```

DVI：

```text
GAP-101 HIGH
GAP-102 MEDIUM
GAP-103 MEDIUM
```

Iteration 1：

```text
Hypothesis：novice CS1 + without-AI transfer targeted query
Result：找到 1 个 eligible Study
GraphRevision 8 → 9
```

Iteration 2：

```text
重新排名
GAP-101 仍 HIGH 但 directness 改善
尝试 citation chaining
Result：0 eligible, 6 duplicates
记录 NegativeSearchRecord
```

Iteration 3：

```text
独立 counter/risk search
Result：1 个 relevant Finding
GraphRevision 9 → 10
```

Iteration 4：

```text
search yield 接近 0
strategy diversity 基本耗尽
GAP-101 → SEARCH_SATURATED
```

系统判断：

```text
HIGH DVI
+ unresolved
+ secondary evidence saturated
→ EMPIRICAL_EVIDENCE_NEEDED
```

然后才：

```text
Gap
→ StudyDesign
→ restricted Pilot
→ Data
→ New Finding
→ GraphRevision 11
→ DecisionSnapshot
```

这是最终要实现的“研究不是报告终点”的系统行为。

---

# 74. Competition / Product Differentiation

Autoresearch 迭代后，不要宣传：

> “24 小时无人值守自动科研。”

更准确的表达：

> **EduEvidence 不只在新证据出现后更新决定，还会识别当前决策中最值得解决的证据缺口，执行有边界的下一轮研究，并持续用受保护的评估体系改进自己的研究方法。**

英文：

> **EduEvidence does not only update decisions when evidence changes. It identifies which evidence is most worth seeking next, runs bounded research iterations, and continuously tests how to become a better research system without optimizing the conclusion itself.**

---

# 75. 最终 Definition of Done

## Evidence Autoresearch

- [ ] Gap 来源仍是 Evidence Graph，不是自由脑暴
- [ ] Gap 有透明 DVI band 与 rationale
- [ ] 每轮一个主 hypothesis
- [ ] 每轮有明确 budget / termination
- [ ] Negative search 可追溯
- [ ] Valid Evidence append-only
- [ ] No-gain iteration 不生成假 GraphRevision
- [ ] Search saturation 可解释
- [ ] 高 DVI + saturated 才能桥接 empirical study
- [ ] Decision action 不被自动真实执行

## Orchestration

- [ ] Protocol / Role / Capability / Worker / Model 完全分离
- [ ] S 级默认 0 subagents
- [ ] M/L 按 evidence axis 并行
- [ ] TaskSpec 是所有 spawn 的前置条件
- [ ] safe_spawn 仍是唯一 Agent MCP path
- [ ] Single Writer
- [ ] Judge 不读取 unvalidated worker prose
- [ ] parallel worker cap 生效

## Skill Autoresearch

- [ ] Baseline 必跑
- [ ] One change per experiment
- [ ] Protected manifest 生效
- [ ] DEV / HOLDOUT / ADV 隔离
- [ ] empirical repeats + noise floor
- [ ] Pareto promotion
- [ ] simplicity criterion
- [ ] results / failures append-only
- [ ] plateau / budget / ceiling
- [ ] branch only；不 auto merge main

## Scientific Integrity

- [ ] 不优化 conclusion
- [ ] 不删除反证
- [ ] 不伪造 precision
- [ ] 不把 active-learning ranking 当 evidence weight
- [ ] 不把 conceptual DVI 当正式 EVSI
- [ ] 不把 simulation benchmark 当真实性能证据
- [ ] human-subject Pilot 仍有人类 / ethics gate

---

# 76. 实施优先级

```text
P0  Orchestration clarity / Single Writer
↓
P1  ResearchIteration + NegativeSearch memory
↓
P2  DVI / Gap lifecycle
↓
P3  bounded Evidence Autoresearch
↓
P4  Saturation → Pilot bridge
↓
P5  Skill Autoresearch protected MVP
↓
P6  Holdout / adversarial / repeated empirical eval
↓
P7  Daily evolution
↓
P8  Studio visualization
```

不要先做 UI。

不要先做“每天自动跑”。

先让：

```text
状态
责任
评估
保护区
```

四件事正确。

---

# 77. 最终架构一句话

> **EduEvidence vNext = 一个以 Evidence Graph 为事实状态、以 Decision 为目标、以 KnowledgeGap 为下一步研究入口、以 bounded experiments 为学习机制、以 protected evals 约束自我改进、以按需 subagents 扩展执行能力的 Living Decision Research Engine。**
