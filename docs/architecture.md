# EduEvidence 架构说明

## 它是什么（先读这一段）

EduEvidence 是一套**决策级证据合成**流程，交付形态是一个开源 Skills/CLI 能力包：**你交进来一个"要不要采用、怎么采用"的问题，它交回去一份可以逐条核对的结论**。

它回答的不是"大家怎么看"，而是四个具体问题：证据到底支持什么、不支持什么、分歧出在哪里、如果要落地第一步该怎么走。最后落到四种判定之一：
**可以推广（ADOPT）/ 先小范围试点（PILOT）/ 不采用（REJECT）/ 证据还不够（INSUFFICIENT EVIDENCE）**，并附上试点方案与评价方案。

适用范围不限于课堂。教育与政策等应用社科场景是它的主场（仓库内置 `education` 与 `policy` 两个领域），
企业管理、公共服务等同类"要不要上、怎么上"的决策走的是同一套流程——换的是领域契约（研究框架、结果分类、方法学清单），不换流程。

三句话说明它和"让大模型写一篇综述"的区别：

1. **读原文**：搜索结果的摘要只是线索（snippet 不算证据），必须抓回正文并通过校验才能进入证据。
2. **反着查**：反证要单独构造检索式去找，不能把正面结果"翻个面"充数。
3. **给不出结论时就说给不出**：证据太薄、太间接、分歧无法解释时，输出"证据不足"，并写明"什么证据会改变这个判断"。

本文档说明其三层架构、双运行模式、九步流程、八个角色、产物与状态模型，以及一条真实运行的完整轨迹。以下断言全部对应仓库内可核验的文件。

## Canonical Protocol（唯一权威定义）

EduEvidence 的端到端流程统一为 **9 步**，由两部分组成：前 6 步回答"证据站不站得住"（Research Core），后 3 步回答"证据怎么变成行动"（Decision Extension）。
此为本项目唯一权威定义，`docs/methodology.md`、README 等所有文档的协议表述均以本节为准：

```text
Research Core（6 阶段，证据纪律核心）:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate

Decision Extension（3 阶段，证据到行动）:
Applicability → Intervene → Evaluate

端到端 9 步:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate
→ Applicability → Intervene → Evaluate
```

每一步在做什么，先说人话：

| 步 | 阶段 | 这一步的目的 |
|---|---|---|
| 1 | Frame 框定 | 把模糊的问题变成可检索、可验收的问题：给谁、在什么课程或场景、与什么对照、要看哪些后果 |
| 2 | Retrieve 检索 | 找候选文献；摘要只能当线索，必须抓回正文并通过来源校验才算证据（正文留在 `fetch/`） |
| 3 | Extract 抽取 | 把每篇研究里的具体发现抽成结构化条目，绑定原文位置，并标明它测的是哪一种结果 |
| 4 | Challenge 质询 | **独立**去找反证：零结果、负结果、矛盾证据、替代解释、混淆因素、范围越界 |
| 5 | Audit 审计 | 审"这些研究做得够不够好"：对照、随机、前测后测、保持与迁移测量、样本偏差、教师效应等 |
| 6 | Adjudicate 裁决 | 在证据边界内下判定，写明"能主张什么、不能主张什么"；定稿前还要过 Pre-Verdict Gate |
| 7 | Applicability 适用性 | 这份结论对谁成立、在什么条件下成立：人群、课程、结果类型、实施条件是否对得上 |
| 8 | Intervene 干预 | 设计最小可验证的试点：分阶段规则、护栏、停止条件，以及每条规则对应的证据 |
| 9 | Evaluate 评价 | 写清怎么验收：基线、后测、保持、迁移，过程与风险指标，成功阈值与停止阈值 |

四种判定（第 6 步的输出，全项目统一口径，不要写成"支持/不支持"两态）：

| 判定 | 含义 | 触发条件（`engine/tribunal.py` 的门控） |
|---|---|---|
| **ADOPT** 可以推广 | 证据够硬、风险可控、场景对得上 | 把握程度 High + 存在决定性的支持证据 + 在**主要结果**上有直接证据（教育域 = 学习类结果，政策域 = 效果/成本类）——教育场景只测出"做题变快"不够 |
| **PILOT** 先小范围试点 | 方向有积极证据，但长期效果、迁移或风险仍不明确 | 把握程度 High 或 Moderate + 存在支持证据 |
| **REJECT** 不采用 | 关键结果稳定为负，或风险明显大于收益 | 存在可用的、直接反对采用的独立研究 |
| **INSUFFICIENT EVIDENCE** 证据不足 | 来源不足、直接性差、设计弱，或分歧无法解释 | 以上条件都不满足 |

两条硬约束：**把握程度为 Low 或 Insufficient 时永远不可能给 ADOPT**；**只要存在反对采用的独立证据，就直接判 REJECT**。
也就是说，四态不是模型自由发挥的结果，而是由确定性公式与门控算出（见「§五 一次真实运行」与「§七 产物与状态」）。

- `Fetch` 与 `Validate` 是 `Retrieve` 阶段内部的强制 gate（snippet ≠ 证据内容，RULE 2），不单独计为阶段。
- `Present` 是最终呈现层（报告渲染），不属于协议阶段计数。
- 每个阶段的输出仍须通过对应 JSON Schema 校验：`schemas/` 顶层共 **15 个** Schema（`ls schemas/*.json`），
  连同子目录（`schemas/v2|v3|v4|vNext`）合计 49 个，口径见 `docs/metrics.json`（由 `scripts/generate_metrics.py` 生成）。

## 〇、EduEvidence Research Engine（V2 内部能力内核）

Skill 本体不变；Skill 内部操作 **EduEvidence Research Engine** —— 以 Project / Run / Revision / DecisionSnapshot 为状态模型的持久化研究引擎。
先用一句话分清这四个词（后面所有章节都依赖它们）：

| 概念 | 白话解释 |
|---|---|
| Project 项目 | 一个研究问题对应一个长期项目，可以跨学期持续使用（默认落在 `~/.eduevidence/projects/`） |
| Run 一次运行 | 项目里的一次执行：这一轮跑到哪一步、留下哪些产物文件 |
| Revision 版本 | 证据图每提交一次就生成一个完整的新版本（`rev-N`），旧版本只增不改 |
| DecisionSnapshot 决定快照 | 每次裁决留下的不可变记录，报告引用的是具体哪一个版本，永远查得到 |
| Projection 投影 | 给人看的产物：报告、图表、导出包。可删可重建，不是事实本身 |

- **Project Workspace**（`~/.eduevidence/projects/PRJ-.../`）：长期研究项目，持有版本化 **Evidence Graph**（Source→Study→Finding→EvidenceLink→Claim→Outcome→Decision）与 gaps/study-designs/datasets/analyses/decisions/projections/runs。
- **Evidence Graph 是不可变 revision 模型**：每次提交生成完整快照 `rev-N` 并原子切换 `graph/HEAD`（原子 = 要么整份生效、要么完全不变，读者不会看到半成品）；`result.json`/HTML/Markdown 均为投影，不是事实库。
- **Shared Research Library**：已核验的外部事实（Source/Study/Finding/Audit）可以通过快照导入被复用；**事实可复用，解释必须项目本地**（Claim/EvidenceLink/Applicability/Decision 不能跨项目照搬）。
- **两种 Research Mode**：**Evidence Review** 只用二手文献回答"要不要采用"；**Full Research Cycle** 走完整闭环——证据综述→找出知识缺口→设计新研究→接入用户自己的数据→分析→把新证据写回证据图→更新判定。
- **冻结科学规则：No new study design without evidence grounding**（没有证据打底，不许提新研究设计）——任何研究设计必须引用一个显式的、由证据推出的知识缺口 ID（KnowledgeGap ID）；缺了它，`engine/study_design.py` 会直接拒绝写入。
- 引擎是内部能力架构，**不是独立服务或应用**：核心只依赖 Python 标准库，不强制 Agent MCP，也不需要常驻进程（daemon）。

## 一、三层架构总览

在往下看之前先记住一句话：**三层不是三个程序，而是三种关注点的分工**——最上层管"这个领域的专业判断"，
中间层管"证据必须按什么顺序走、要过哪些门"，最下层管"用什么把它跑起来"。换执行方式（第 3 层）不会动摇前两层，
这也是它能同时适配不同 Agent 平台的原因。

```
┌─────────────────────────────────────────────────────────────────┐
│ 第 1 层  EduEvidence（领域层）                                    │
│  教育领域知识 + 决策 + 干预 + 评价                                 │
│  · 教育研究问题结构化（Education Frame）                          │
│  · 教学决策（ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE）     │
│  · 最小可验证干预（Phase 化试点 + Stop Conditions）                │
│  · 评价设计（Task vs Learning，Immediate vs Retention vs Transfer）│
├─────────────────────────────────────────────────────────────────┤
│ 第 2 层  EvidenceFlow Protocol（流程层）                           │
│  Frame → Retrieve → Extract → Challenge → Audit → Adjudicate      │
│  （Retrieve 内含 Fetch/Validate gate；Decision Extension 3 阶段）   │
│  每一步有独立输入/输出契约，由顶层 15 个 JSON Schema 约束             │
├─────────────────────────────────────────────────────────────────┤
│ 第 3 层  执行层（Execution Layer）                                 │
│  Mode A  Platform Native Mode                                    │
│  Mode B  Agent MCP Enhanced Mode                                 │
└─────────────────────────────────────────────────────────────────┘
```
### 1.1 第 1 层：EduEvidence 领域层

领域层承载学科专业判断，不依赖任何具体 Agent 框架。以教育域为例：

- **领域知识（先框定，再建议）**：把"谁学、什么课、做什么干预、和什么比、看什么结果、在什么条件下"结构化下来（`education-frame.schema.json`）；
  没完成这一步，不允许给任何教学建议。
- **决策（说清支持什么、不支持什么）**：输出 `adopt / pilot / reject / insufficient_evidence` 四类动作之一（`verdict.schema.json`），
  并单独列出"可以主张"与"不能主张"（见文首四种判定的门控条件）。
- **干预（默认先试点）**：任何决策默认落到一个最小可验证的干预设计（`intervention.schema.json`）——分阶段规则、护栏、停止条件与证据对齐。
  只有主要结果上存在较强直接证据、风险可控且场景高度匹配时才允许推广。
- **评价（把"效果好不好"拆开量）**：为试点/推广配套评价方案（`evaluation.schema.json`），
  强制把**任务表现**（做题快不快、分数高不高）与**学习效果**分开，并要求分别设计保持测试与迁移测试。
- **领域注册表（换领域换契约，不换流程）**：`domains/<id>/` 里每个领域自带研究框架 schema、结果分类与方法学清单；
  教育域的结果分四类（学习 / 任务表现 / 过程 / 风险），政策域分五类（效果 / 成本 / 公平 / 可行性 / 实施风险）。
  未知的结果类型直接报错，不会被悄悄归到某一类里。

### 1.2 第 2 层：EvidenceFlow Protocol

证据流协议采用 **Canonical Protocol**（见文首「唯一权威定义」）：**Research Core 六阶段**（证据纪律核心）+ **Decision Extension 三阶段**（证据到行动）= **9 步端到端**；`Present` 为最终呈现层，不计入协议阶段。

这一层是**可剥离的**：即使不用任何 Agent 框架，只要按这个顺序组织检索、抽取、审计与裁决，也能得到一条可复现的决策链。
下面两张表给的是每一步的输入/输出契约，和文首那张"人话表"是同一件事的两种写法。

**Research Core（六阶段，可剥离的核心）：**

| 阶段 | 英文名 | 输入 | 输出 |
|------|--------|------|------|
| 1. 框定 | Frame | 原始教育问题 | Education Research Frame（含 decision_target、scope、inclusion/exclusion criteria） |
| 2. 检索 | Retrieve | Frame | 校验通过的来源与 Claim 级证据基础（内部强制 gate：Fetch 抓取全文 + Validate 来源/内容校验，snippet ≠ 证据内容，RULE 2；对应 `source.schema.json` / `fetch-result.schema.json`） |
| 3. 抽取 | Extract | 校验后的来源文献 | Claim 级证据对象（`evidence.schema.json`） |
| 4. 质询 | Challenge | 证据对象 | 反方证据、负面结果、未发现、confounder 清单 |
| 5. 审计 | Audit | 证据对象 | 方法学审计（`methodology.schema.json`），含 task_vs_learning_guard |
| 6. 裁决 | Adjudicate | 全部证据 + 审计 | Education Verdict + Recommended Action + Confidence |

**Decision Extension（三阶段，证据到行动，即端到端第 7–9 步）：**

| 阶段 | 英文名 | 输入 | 输出 |
|------|--------|------|------|
| 7. 适用 | Applicability | Verdict | 适用性分析（For whom / which course / which outcome / what conditions） |
| 8. 干预 | Intervene | Verdict + Applicability | Teaching Intervention（最小可验证试点 + 停止条件） |
| 9. 评价 | Evaluate | 干预方案 | Evaluation Plan（基线/后测/保持/迁移 + 成功阈值） |

**Present（呈现，不计入 9 步协议）：**

| 阶段 | 英文名 | 输入 | 输出 |
|------|--------|------|------|
| 10. 呈现 | Present | result.json + result.zh.json | 单文件双语 HTML 报告 + 信息图 + 学术图 + **AI 自由组合的 Lieflat 数据驱动画廊**（`visualization/`；主题在生成前从 `claude`[Light] / `academic`[Light] / `datalab`[Light] / `datalab-dark`[Dark] / `presentation`[Dark] 五选一，最终 HTML 不提供主题切换，仅保留中英文切换） |

**Present 可视化管线（AI 组合 + 数据驱动）：**

```text
result.json.visual_layout（AI 写图表计划：type + 目录编号 + 双语文案 + 数据源参数）
        │ resolve_visual_layout（build_report.py）
        │   · 只接受注册表内 type（lieflat_engine.REGISTRY），未注册显式报错
        │   · 双语缺失 / 参数非法 → 丢弃该条 + 原因入 report_spec
        │   · 缺失或全无效 → 确定性安全组合（forest + dot_cascade +
        │     bubble_almanac + tick_rows）
        ▼
charts_data.py 提取器（唯一数字来源，读 result.json → 规范化 bundle）
        │   数据不足 → 抑制该图 + 原因（镜像 Meaningful Visualization Gate）
        ▼
lieflat_engine.render_figure(type, bundle, theme, meta)
        │   主题化内联 SVG：lf-pop/lf-fade/lf-draw + --motion-delay stagger，
        │   无内嵌 <style>、无硬编码演示数据；每个显示数值登记 audit
        ▼
完整性门 lieflat_data_bound（compute_integrity + 页脚）
        │   渲染值逐一比对提取器 bundle——篡改数值天然不被采用
        ▼
motion/motion.css + motion/motion.js（data-lieflat reveal：滚入播放、
        点击重播 + timer 清理、prefers-reduced-motion 降级、打印全开）
```

学术图（outcome-comparison / benchmark / forest）保持主题无关的出版级渲染；Lieflat 部分只渲染 `resolve_visual_layout` 校验通过的条目。注册表、契约与推荐组合见 `visualization/eduevidence-report/references/lieflat-composition.md`，schema 见 `visualization/eduevidence-report/schemas/visual-layout.schema.json`。

该协议是**可剥离的**：即使没有 Agent 框架，只要按此协议组织检索、抽取、审计与裁决，也能得到可复现的决策链。

### 1.3 第 3 层：执行层

执行层负责把第 1、2 层真正跑起来，提供两种运行模式。**它只决定"谁来做"，不改变"做完要满足什么"**：
无论用哪种模式，门、校验与判定规则完全一样（细节见 §八）。

## 二、双运行模式

### Mode A：Platform Native Mode（平台原生模式）

- **零外部依赖**：不需要常驻进程、CLI 或 Agent MCP，是一份提示词加标准库脚本就能跑的形态。
- **`SKILL.md` 单文件可独立理解**：领域知识、九步流程、数据结构说明、示例与复现命令都在里面，
  任何支持自定义指令的 AI 平台都能直接加载。
- 适合：Claude Projects、ChatGPT 自定义指令、Cursor Rules 这类"以文档为技能载体"的平台。
- 局限（如实说）：检索依赖模型自身或平台内建工具；上下文不跨会话保留，一致性靠提示词与磁盘上的产物保证。

### Mode B：Agent MCP Enhanced Mode（Agent MCP 增强模式）

在 Mode A 基础上，通过 MCP（Model Context Protocol，一种让模型调用外部工具的标准协议）接入执行工具，换来这些增强能力：

- **多 CLI**：检索、代码、测试、校验等命令行工具可并行挂载；检索不再是模型"猜来源"，而是真的调用检索器。
- **多模型**：检索 / 抽取 / 裁决可以交给不同模型，例如轻量模型负责检索，强推理模型负责裁决。
- **独立上下文**：每个子任务有各自的上下文，避免长对话把关键证据稀释掉，最后再合并。
- **超时恢复**：子任务可设超时与重试；网络或工具失败时退回 Mode A 的语义继续产出。
- **成本优化**：按阶段选模型与预算——框定与抽取走便宜路径，裁决与审计走强路径。
- **跨会话记忆（Memory Bank）**：缓存已核验来源、历史判定与常用检索词，二次提问命中缓存就不再重复检索。

| 能力维度 | Mode A Platform Native | Mode B Agent MCP Enhanced |
|----------|------------------------|---------------------------|
| 依赖 | 无（纯 SKILL.md） | daemon / CLI / MCP Server |
| 检索 | 模型内建/平台工具 | 真实多 CLI 检索 |
| 模型 | 单模型 | 多模型分工 |
| 上下文 | 单上下文 | 独立子上下文 + 汇总 |
| 超时 | 无 | 可配置超时与恢复 |
| 成本 | 固定 | 分阶段 Token 预算优化 |
| 记忆 | 无 | Memory Bank 跨会话缓存 |

**推荐组合**：先用 Mode A 把流程与协议跑通（任何人都能独立读懂和使用），需要更真实的检索、更多独立复核时再接入 MCP 升级到 Mode B；
两种模式下的产物、门与判定语义完全一致，因此升级不需要重做研究。

## 三、项目目录结构

```
edu/
├── SKILL.md                # 技能入口：EduEvidence 使用说明（Mode A 可独立理解）
├── README.md / README.zh-CN.md  # 双语说明（英文 / 中文）
├── pyproject.toml          # 打包元数据（wheel 自带 CLI + engine；核心零第三方依赖）
├── install.sh              # 一键安装（本地 / 多 Agent Skill）+ 自检
├── skill/                  # 技能组件
│   ├── agents/             # 8 个角色提示词（research-planner / evidence-retriever /
│   │                       # evidence-analyst / skeptic / method-reviewer /
│   │                       # evidence-judge / intervention-designer / evaluation-designer）
│   ├── roles/registry.yaml # 角色 → 阶段 → 能力映射与独立性要求（角色侧唯一权威）
│   ├── sub-skills/         # 12 个子技能配方（每个一个 SKILL.md，原 skills/，v5 合并至此）
│   ├── task-briefs/        # 每个阶段一份任务简报模板
│   └── workflows/          # 三个用户工作流的运行手册
├── references/             # 方法学与政策文档（education-framing / outcome-taxonomy /
│                           # evidence-quality / methodology-audit / skeptic-protocol /
│                           # tribunal-policy / applicability-policy / intervention-design /
│                           # evaluation-design / retrieval-protocol / source-validity 等）
├── domains/                # 领域注册表：每个领域自带研究框架 schema、结果分类与方法学清单
│   ├── education/          # 教育域（复用 schemas/education-frame.schema.json）
│   └── policy/             # 政策域（自带 frame.schema.json 与 5 类政策结果分类）
├── schemas/                # 15 个顶层 JSON Schema 数据契约 + v2/v3/v4/vNext 子目录
│   ├── education-frame.schema.json
│   ├── source.schema.json
│   ├── fetch-result.schema.json
│   ├── evidence.schema.json
│   ├── skeptic.schema.json
│   ├── methodology.schema.json
│   ├── verdict.schema.json
│   ├── applicability.schema.json
│   ├── intervention.schema.json
│   ├── evaluation.schema.json
│   ├── cross-model-review.schema.json
│   ├── report-result.schema.json
│   ├── report-spec.schema.json
│   ├── chart-spec.schema.json
│   └── agent-mcp-approval.schema.json
├── engine/                 # Research Engine 内核（Project / Run / Revision /
│                           # DecisionSnapshot、Evidence Graph、tribunal / synthesis /
│                           # gaps / study-design / datasets / analysis / projections、
│                           # v3: pilot 决策闭环 / meta_synthesis 跨项目综述）
├── scripts/                # 工具脚本（validate_schema / pre_verdict_gate /
│                           # compute_confidence / orchestrator / benchmark /
│                           # render_report 等确定性逻辑）
├── retrieval/              # 检索与抓取层（fetch / validate / dedupe / failures）
├── integrations/           # 集成层（Agent MCP 增强 + Smart Web Fetch）
├── visualization/          # 呈现层（eduevidence-report：build_report / build_charts /
│                           # build_infographics / build_figures / charts_data 提取器 /
│                           # lieflat_engine 注册表渲染器 / motion / themes / schemas；
│                           # lieflat-charts：图表品味法典正本）
├── benchmarks/             # 基准评测（questions / annotations / baselines /
│                           # evaluator / results / v2）
├── examples/               # 端到端示例
│   ├── ai-coding-assistant-evidence/ # 主示例：大一 C 语言课程该不该放开 AI 编程助手
│   ├── spaced-retrieval-practice/    # 真实检索示例：间隔重复与检索练习（Sciverse 通道）
│   └── workplace-ai-assistant/       # 政策域示例：企业客服团队该不该上 AI 助手
├── docs/                   # 本文档（架构/方法学/Benchmark/Demo/复现指南）
└── tests/                  # pytest 测试
```

各目录职责单一：`domains/` 决定"这套流程用在哪个领域、看哪些结果"；`schemas/` 是数据契约（每一步的产物必须长成什么样）；
`scripts/` 是确定性校验与评测入口；`engine/` 是证据图与裁决内核；`retrieval/` 负责把文献真的抓回来；
`visualization/` 只做投影（报告与图表）；`benchmarks/` 沉淀评估资产；`examples/` 提供可复现案例；`docs/` 解释"为什么这样设计"。

## 四、设计原则

1. **领域层独立于 Agent 层**：判断逻辑不耦合任何 Agent 框架；将来换执行方案，第一、二层不用动。
2. **协议可剥离**：EvidenceFlow Protocol 可以完全脱离 MCP 自己跑，最低运行成本可用（只要能读提示词、能跑标准库脚本）。
3. **决策可追溯**：从最终判定出发，可以一路反查到具体的证据条目、原文位置、方法学审计项与置信度分解项。
4. **默认偏向最小可验证 PILOT，但 ADOPT 真实可达**：体系内置"先试点、后部署"约束，从结构上防止跳过验证直接上全量方案；只有主要结果上存在较强的直接证据、风险可控且场景高度匹配时才允许 ADOPT——该出口由公开案例 spaced-retrieval-practice（ADOPT / High）实证可达，不是一条写死不通的路。
5. **降级友好**：Mode B 的任何子任务失败，都会退回 Mode A 的语义把活干完，保证结果不中断（并注明降级过）。
6. **缺失保持缺失**：没有报告置信区间就不许编一个，抽不出的效应量就留空——宁可少一个数，也不给假数（见 `docs/release-contract.md` 科学展示契约）。

## 五、一次真实运行的完整轨迹（旗舰示例逐阶段）

抽象协议读十遍，不如跟着一条真实证据链走一遍。本节用仓库里两个真实产物包，把九步落到**具体文件**上：
主例是 `examples/ai-coding-assistant-evidence/`（问题：大一 C 语言课程该不该放开生成式 AI 编程助手），
另一例是 `examples/spaced-retrieval-practice/`（间隔重复与检索练习能否替代集中式复习，来源经 Sciverse 通道逐条读回原文）。

先说这两个例子里最值得记住的一课：**"练习时做题变快"和"撤掉 AI 后还能不能自己做"是两件事**。主例中，练习表现提升 48–127%，
而撤掉 AI 后的独立考试是 −17%；正是因为这条反证与这条测量构念问题，判定停在 **PILOT（先试点）**，而不是 **ADOPT（可以推广）**。

> 诚实标注：主例的文献是人工整理（`data_origin=manual_curated`），用于演示"一份完成的评审长什么样"，**不代表**已执行模型研究运行；
> 第二例的检索走的是真实 Sciverse 通道（`data_origin=real_run_sciverse`），但结论仍是针对演示问题、不代表真实学校现场。

| 阶段 | 角色 | 产物文件 | 这一份里是什么 | 校验门 |
|---|---|---|---|---|
| 1 Frame | research-planner | `frame.json` | 决策目标=教学决策；学习者=大一 C 语言混合能力大班（16 周讲练课）；对照=无 AI 常规教学；主要结果=独立解题（属"学习"类） | `education-frame.schema.json` |
| 2 Retrieve | evidence-retriever | `sources.jsonl` + `fetch/` | 8 篇来源：7 篇带 DOI 的期刊/会议论文（tier 1）+ 1 篇预印本；正文抓回本地，另附检索审计（检索计划 / 每次尝试 / 筛查表 / 排除理由）四件套 | `source.schema.json`；RULE 2（先抓取校验，再用作证据） |
| 3 Extract | evidence-analyst | `evidence.jsonl` | 12 条证据条目；每条的"结果类型"分开记（如"完成时间"与"独立解题"不混） | `evidence.schema.json`；结果分类分离 |
| 4 Challenge | skeptic | `skeptic.json` | 9 项检查逐条给结论；本例核心反证=无护栏组的独立考试 −17%（950 人） | 九项齐全，禁止虚构反证 |
| 5 Audit | method-reviewer | `methodology.json` | 15 项审计；护栏项明确写下：练习表现 +48–127% 与独立考试 −17% 并存时**不得等同** | `methodology.schema.json` |
| 6 Adjudicate | evidence-judge | `raw_verdict.json` → `final_verdict.json` | 四态裁决：**PILOT**（限制性四阶段渐退试点）；把握程度 Moderate，且分解项可复算 | `verdict.schema.json` + Pre-Verdict Gate |
| 7 Applicability | evidence-judge | `applicability.json` | 适合谁=大一初学者；必须满足的条件含护栏设计；对排除人群与不确定性逐条声明 | 四类边界齐全 |
| 8 Intervene | intervention-designer | `intervention.json` | 分阶段使用规则 + 护栏 + 停止条件 + 证据对齐 | `intervention.schema.json` |
| 9 Evaluate | evaluation-designer | `evaluation.json` | 基线 / 即测 / 保持（第 16 周）/ 迁移（第 8 周无 AI 新题）+ 过程与风险指标 + 成功阈值与停止阈值 | `evaluation.schema.json` |
| Projection 投影 | report-generation | `result.json` / `result.zh.json` / `EduEvidence_Report.html` / `reports-5themes/*.html` / `artifact_manifest.json` | 双语报告与五种版式成品；报告里的数字由提取器从结果文件读出，不是手写的 | 语言门禁 + 渲染完整性门 + `lint_report_layout` |

四个要点值得单独记住：

- **Retrieve 的隐藏闸门**：`fetch/` 里存的是抓回来的正文与降级链记录；没有这一步，模型只能拿到摘要——而摘要不是证据。
- **Audit 与 Challenge 的分工**：Skeptic 负责找反证（内容风险），Method Reviewer 负责判方法（结论站不站得住）。本例"练习大涨、独立考试下滑"正是两者交汇处：既是反证，也是测量构念问题。
- **Adjudicate 的封顶机制**：`final_verdict.json` 是过了 Pre-Verdict Gate、又经确定性公式算过把握程度的产物；模型直接给出的 `raw_verdict.json` 只是草稿。
- **Pre-Verdict Gate 的 12 项**：研究框架、来源、证据、去重、反证检索、方法学审计、主张与证据对齐、结果映射、结论边界、独立研究计数、置信度可复算、决策动作一致性；
  关键项失败会封顶：不允许高置信度，也不允许给 ADOPT（实现见 `scripts/pre_verdict_gate.py`，结果落在运行目录的 `gate_report.json`）。

要重跑这条链：

```bash
eduevidence run --question "大一 C 语言课程是否应该允许学生使用生成式 AI 编程助手？" --run-id ai-cs1
eduevidence status --run-id ai-cs1     # 看阶段状态与待补产物
eduevidence gate   --run-id ai-cs1     # 跑 Pre-Verdict Gate
eduevidence report --run-id ai-cs1 --theme claude
```

（注意：这条链里的"文献与证据"是外部阶段——CLI 负责建工作区、推进状态、跑门与渲染；
抓取、抽取、审计、裁决这几步由你接入的模型按各阶段的简报完成，写出的产物再交给门校验。这不是遗漏，而是产品形态本身。）

第二个例子值得对照着看，因为它的来源是**真的联网检索回来的**：

| 要点 | `examples/spaced-retrieval-practice/` |
|---|---|
| 问题 | 大学程序设计入门课该不该用"间隔重复 + 检索练习"替代集中式复习 |
| 检索通道 | 经 Sciverse 通道：先语义检索定位到具体段落，再按定位 `/content` 读回原文，逐条过校验 |
| 产物规模 | 7 篇来源（全部带 DOI、全部 tier 1）→ 6 条证据 → 3 条主张（延迟保持 / 收益取决于设计 / 迁移也受益） |
| 方法学审计 | 15 项，整体判定 PASS；护栏明确写了"测的是延迟保持与迁移，不是即时练习速度" |
| 反证结果 | 9 项反证检查中"零结果"命中 1 项（E-005），其余未发现；如实写明"未发现矛盾证据" |
| 判定 | **ADOPT**，把握程度 High（引擎复算 0.893）；理由=延迟保持与迁移两个主要结果上都有 directness=2 的直接且一致证据，实施成本低、风险可控。最佳间隔安排与课程现场证据的厚度记录为采用后持续监测的不确定性 |
| 试点与验收 | 第 1 周统一前测 → 第 2–13 周每周 10 分钟闭卷检索练习（只给反馈不给答案）→ 第 14–16 周无辅助延迟测试与新题型迁移任务；停止条件=延迟测试低于基线或完成率低于 60% |

两例对照说明了四态设计的实际作用：旗舰包的证据只到"任务表现"这一层，因此停在 **PILOT**；间隔重复包的证据落在主要结果（延迟保持、迁移）上，就如实给出 **ADOPT**。判定既不为了保守而一律试点，也不越过证据边界。

## 六、角色与提示词地图（8 角色 → 阶段 → 能力要求）

角色是**责任单元**，不是"必须真的开出 8 个 Agent"：小任务（S 级）可以让一个模型依次扮演全部角色，只要产物与门都满足契约。
但**三个角色声明了独立性要求，这是硬约束**，不能靠"换个会话"糊弄过去。

多数角色是可以换人的；下面三个不行——它们的存在就是为了让结论不能自己给自己盖章：

| 角色 | 它保证什么 | 为什么不能省 |
|---|---|---|
| **skeptic** 反证质疑 | 反证必须来自**不同的模型家族** | 同一个模型换个会话，会沿用同一套宽容标准重新肯定自己，等于没有独立审核 |
| **method-reviewer** 方法学审计 | 与内容判断**分离**：输入只有设计与测量，不含结论评价 | 审"怎么测的"和判断"结论对不对"是两件事，混在一起就会替结论辩护 |
| **evidence-judge** 裁决 | 在证据边界内下判定、划适用边界 | 判定由公式与门控收口（见 §五），不让它自由发挥 |

| 角色 | 提示词 | 负责阶段 | 角色注册表能力 | 路由侧能力要求 | 独立性 |
|---|---|---|---|---|---|
| research-planner | `skill/agents/research-planner.md` | frame | research_framing | reasoning: high | — |
| evidence-retriever | `skill/agents/evidence-retriever.md` | retrieve | literature_search / counter_evidence_search / source_fetch / source_validation | tool_use: strong、cost: low | — |
| evidence-analyst | `skill/agents/evidence-analyst.md` | extract | study_extraction / finding_extraction / claim_linking | reasoning: medium+、structured_output: strong | — |
| skeptic | `skill/agents/skeptic.md` | challenge | counter_evidence_search | reasoning: high | **different-model-family** |
| method-reviewer | `skill/agents/method-reviewer.md` | audit | methodology_appraisal | reasoning: high、context: high | **role-separation** |
| evidence-judge | `skill/agents/evidence-judge.md` | adjudicate / applicability | evidence_synthesis / tribunal / applicability_analysis / knowledge_gap_detection | reasoning: highest、structured_output: strong | — |
| intervention-designer | `skill/agents/intervention-designer.md` | intervene | study_design / measurement_design / intervention_design | reasoning: high | — |
| evaluation-designer | `skill/agents/evaluation-designer.md` | evaluate | evaluation_design / data_validation / data_analysis | reasoning: high、quantitative: preferred | — |

三方同源（由 `scripts/check_protocol_alignment.py` 强制）：`skill/roles/registry.yaml`（科学映射）、
`skill/agents/*.md` 的 frontmatter（提示词侧声明）、`integrations/agent_mcp.py::ROLE_REQUIREMENTS`（路由侧能力等级）。
**三者都不写具体模型名**——用哪个模型是运行时的用户决策（见 §八 与 §十）。

两层独立性语义不同，不要混用：

- **Skeptic 的 `different-model-family`**：反证必须来自不同先验。换个会话问同一个模型不算独立审核——它会用同一套宽容标准重新肯定自己。
- **Method Reviewer 的 `role-separation`**：审的是"怎么测的"，输入只含设计与测量，不含结论评价；它与内容判断分离，但不要求跨模型。

每个角色的提示词结构统一为：职责 / 输入 / 输出（含 schema 与枚举值表）/ 输出契约 / 红线 / 输出格式 / 卡住升级 / 独立性与交叉评审 / 失败模式与回退。
换句话说，读一份角色提示词就知道：它该做什么、不许做什么、卡住了找谁、以及它凭什么算独立。

## 七、产物与状态地图（Project / Run / Revision / 投影边界）

先用一句话把四个词站稳：**Project 是长期项目，Run 是一次执行，Revision 是版本，Projection 是投影**。
**唯一算事实的只有证据图**；报告、图表、导出包都是投影——投影可以删、可以重建，重建之后结论一个字都不会变。

```text
Project（长期研究项目，唯一对应一个研究问题）
  └── Evidence Graph（append-only revisions）  ── 事实层
        ├── Source → Study → Finding → EvidenceLink → Claim → Outcome → Decision
        └── graph/HEAD 原子切换；历史 revision 只增不改
  └── Run（一次执行）
        ├── 科学产物：frame / sources / evidence / skeptic / methodology / verdict / applicability / intervention / evaluation
        ├── 运行产物：state.json、trace.jsonl、task-briefs/、fetch/
        └── 检索审计：search-provenance / attempts / screening / exclusion（+ Sciverse chunks.jsonl）
  └── DecisionSnapshot（每次裁决的不可变快照）
  └── Projections（可删可重建）
        └── result.json / result.zh.json / HTML 报告 / 图表 / 导出包
```

三条边界决定了系统行为：

1. **事实层在证据图里，不在报告里**：`result.json`、HTML、Markdown 全是投影；报告损坏不影响结论，要改结论必须产生新版本（append-only，旧版本只增不改）。
2. **投影层在科学流程之外**：`Projection` 不是"第十步"，它根本不在 `SCIENTIFIC_STAGE_IDS` 里（`engine/workflows.py`）。渲染失败只阻挡发布，不改变任何判定。
3. **检索留痕是证据链的一部分**：没有出处记录的检索结果只是"候选"，不是证据——这正是 Sciverse 通道要把段落定位写进 `chunks.jsonl`、
   并标注 `discovery_only_requires_content_fetch`（定位 ≠ 证据，必须再读回正文）的原因。
4. **报告落款绑定版本**：每次裁决生成一个不可变的 `DecisionSnapshot`，并记录它基于哪个证据图版本；报告引用的是具体版本，因此"这份报告用的是哪一版证据"永远查得到，不会出现"报告悄悄变新"的情况。

## 八、执行层与审批闭环（Native vs Agent MCP）

执行层决定"**谁来做**"，科学层决定"**做完要满足什么**"。两者互不替代：换执行方式不会放宽任何一道门。

两种跑法：**Mode A（平台原生）**不需要任何外部依赖，一份提示词加标准库脚本就能跑完九步，适合先用起来；
**Mode B（Agent MCP 增强）**才接入外部 CLI 与多模型，用来换更真实的检索和更强的独立复核，跑不动时照样降级回 Mode A。

| 维度 | Mode A Platform Native | Mode B Agent MCP Enhanced |
|---|---|---|
| 依赖 | 无（提示词 + 标准库脚本） | daemon / CLI / MCP Server |
| 检索 | 内建通道（含 Sciverse 等 key 通道） | 同上 + 多 CLI 派遣 |
| 模型 | 单模型 | 按角色分工的多模型 |
| 失败语义 | 直接降级 | 超时/失败降级回 Mode A |

Mode B 的关键不是"多开几个 Agent"，而是一套**审批闭环**——模型换人必须有人签字，而且签字的内容会被钉死：

```text
detect_agent_mcp()  → 扫描可用 CLI 与模型（不预设默认值）
build_recommendation_table()  → 按 ROLE_REQUIREMENTS 生成"角色→模型"候选表
用户确认  → write_approval()：写入 ~/.eduevidence/agent_mcp_approval.json（含角色映射哈希）
safe_spawn(role)  → 校验（未确认 / 哈希不匹配 / CLI 不在允许集）→ AGENT_MCP_APPROVAL_REQUIRED，不 spawn
cross_model_review()  → 独立模型复核草稿裁决；无独立模型时降级为原生自审并标注
```

为什么这么严：一旦允许"悄悄换模型"，`skeptic` 的跨家族独立性就名存实亡，而**报告读起来毫无差别**——用户根本发现不了。
审批记录里存着一份角色→模型的映射哈希，把"用户当时同意的是哪一套"钉死；之后任何改动（换 CLI、换模型、加角色）都会让哈希对不上，
必须重新确认。`safe_spawn` 是唯一的派遣入口，未确认的调用一律返回 `AGENT_MCP_APPROVAL_REQUIRED` 且不启动任何进程。

模型清单来自实际扫描（`scan_cli_models`），并显式排除用户不可用的条目；`build_spawn_call` 在缺少 CLI 或模型时直接报错——
不存在的模型不会被"自动补一个默认值"。同样地，没有独立模型可用时，交叉复核会降级为原生自审**并如实标注**，不会假装做过独立复核。

## 九、内部内容地图（harness 侧）

同一套科学约定分散在多个位置存放。这看起来重复，但每一份都有自己的职责，而且**由机器强制对齐**——改了一处忘了另一处，门会红。

| 位置 | 作用 | 契约约束 |
|---|---|---|
| `engine/workflows.py` | 九步清单与四种工作流（只做综述 / 做到试点 / 只做评价 / 全流程）的唯一权威定义 | —— |
| `engine/capabilities.py` | 能力注册表：每项能力的输入/输出契约与是否为确定性本地执行 | 能力 ID 是全仓库的公共词汇 |
| `domains/<id>/` | 领域注册表：研究框架 schema、结果分类、方法学清单 | 未知结果类型报错（fail closed），不静默归类 |
| `skill/workflows/*.md` | 三个用户工作流的运行手册（步骤表 / 门 / 失败处理 / 交接 / 验收清单） | 与 `engine/workflows.py` 的阶段集一致 |
| `skill/task-briefs/*.md` | 每个阶段一份执行简报（目标 / 前置 / 产物 / 规则 / 质量门 / 失败模式） | 阶段名 ↔ 简报一一对应 |
| `skill/sub-skills/*/SKILL.md` | 内部能力配方（何时用 / 输入 / 过程 / 产出 / 门 / 反模式 / 例子） | frontmatter `capability` ∈ `engine/capabilities.py` |
| `skill/roles/registry.yaml` | 角色 → 阶段 → 能力映射、独立性要求 | 与角色提示词、路由要求三方同源 |
| `references/*.md` | 方法学与政策（WWC / GRADE / 检索协议 / 合规 / 适用性等） | 检索合规由 `references/retrieval-compliance.md` 统一约束 |
| `docs/plans/STATUS.md` | 迭代状态单一来源 | 每完成一项更新此表并记 CHANGELOG |

防漂移靠四道机器门（都会在 CI 里跑）：

```bash
python3 scripts/check_protocol_alignment.py   # 语义：五方说的是不是同一件事（含领域分类与版本口径）
python3 scripts/skill_lint.py                 # 结构：文件在不在、frontmatter 对不对
python3 scripts/check_version_consistency.py  # 版本：engine/versions.py 是唯一权威
python3 scripts/generate_metrics.py --check   # 数字：文档里引用的计数与仓库实际一致
```

四道门分工明确：`skill_lint` 问"文件在不在、格式对不对"，`check_protocol_alignment` 问"各处说的是不是同一件事"，
`check_version_consistency` 问"版本号是不是只有一个来源"，`generate_metrics` 问"文档里的数字和仓库实际是否一致"。

对齐门不是纸面功夫——在本仓库的迭代中它实际抓出过：4 个不存在的能力 ID、1 份落后两个大版本的打包清单、2 处过期的测试计数，
以及领域注册表与 schema 枚举之间的漂移。新增能力 / 子技能 / 角色 / 检索通道的步骤见 `CONTRIBUTING.md`。

## 十、延伸阅读

- **协议单一权威**：本文第「Canonical Protocol」节；实现见 `engine/workflows.py::SCIENTIFIC_STAGE_IDS`。
- **HTML 单页导读**：`web/architecture.html`（同一份内容的浏览版，含流程与角色示意图）。
- **方法学细节**：`docs/methodology.md`、`references/wwc_standards.md`、`references/grade_framework.md`。
- **检索与合规**：`references/retrieval-protocol.md`、`references/retrieval-compliance.md`、`docs/sciverse-api.md`（Sciverse 通道契约）。
- **复现边界**：`docs/reproducibility.md`（哪一层是确定性的、哪一层依赖模型）。
- **发布事实表**：`docs/release-contract.md`（当前实现与边界、报告契约、静态发布与隐私）。
- **参与开发**：`CONTRIBUTING.md`（门清单、科学不变量、如何新增能力 / 子技能 / 角色 / 检索通道）。
