# EduEvidence 架构说明

EduEvidence 是一个"基于证据的 AI 教学决策与干预"能力（Evidence-Based AI Teaching Decision & Intervention Skill）：输入一条教育问题，输出一份可追溯的证据综述、方法论审计、结论判定、试点干预与评估设计。本文档说明其三层架构与双运行模式。

## Canonical Protocol（唯一权威定义）

EduEvidence 的端到端流程统一为 **9 步**，由两部分组成。此为本项目唯一权威定义，`docs/methodology.md`、README 等所有文档的协议表述均以本节为准：

```text
Research Core（6 阶段，证据纪律核心）:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate

Decision Extension（3 阶段，证据到行动）:
Applicability → Intervene → Evaluate

端到端 9 步:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate
→ Applicability → Intervene → Evaluate
```

- `Fetch` 与 `Validate` 是 `Retrieve` 阶段内部的强制 gate（snippet ≠ 证据内容，RULE 2），不单独计为阶段。
- `Present` 是最终呈现层（报告渲染），不属于协议阶段计数。
- 每个阶段的输出仍须通过对应 JSON Schema 校验（`schemas/` 顶层共 13 个 Schema，见 §三 目录结构）。

## 〇、EduEvidence Research Engine（V2 内部能力内核）

Skill 本体不变；Skill 内部操作 **EduEvidence Research Engine** —— 以 Project/Run/Revision/DecisionSnapshot 为状态模型的持久化研究引擎：

- **Project Workspace**（`~/.eduevidence/projects/PRJ-.../`）：长期研究项目，持有版本化 **Evidence Graph**（Source→Study→Finding→EvidenceLink→Claim→Outcome→Decision）与 gaps/study-designs/datasets/analyses/decisions/projections/runs。
- **Evidence Graph 是不可变 revision 模型**：每次提交生成完整快照 `rev-N` 并原子切换 `graph/HEAD`；`result.json`/HTML/Markdown 均为投影，不是事实库。
- **Shared Research Library**：已验证外部事实（Source/Study/Finding/Audit）经 snapshot import 复用；研究事实可复用，解释（Claim/EvidenceLink/Applicability/Decision）必须项目本地。
- **两种 Research Mode**：Evidence Review（二手证据）与 Full Research Cycle（证据综述→知识缺口→新研究设计→用户数据→分析→新证据→更新决策）。
- **冻结科学规则：No new study design without evidence grounding**——任何研究设计必须引用显式、有证据奠基的 KnowledgeGap ID。
- 引擎是内部能力架构，不是独立服务/应用；Native Core 仅依赖 Python 标准库，不强制 Agent MCP 或 daemon。

## 一、三层架构总览

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
│  每一步有独立输入/输出契约，由 13 个 JSON Schema 约束                │
├─────────────────────────────────────────────────────────────────┤
│ 第 3 层  执行层（Execution Layer）                                 │
│  Mode A  Platform Native Mode                                    │
│  Mode B  Agent MCP Enhanced Mode                                 │
└─────────────────────────────────────────────────────────────────┘
```
### 1.1 第 1 层：EduEvidence 领域层

领域层承载教育学科的专业判断，不依赖任何具体 Agent 框架：

- **教育领域知识**：learner / course / intervention / comparison / outcomes / context 的结构化建模（`education-frame.schema.json`），强制在给出任何教学建议前先完成 Framing。
- **决策**：基于证据三角的判定输出（`verdict.schema.json`），明确区分"证据支持什么"与"证据不能支持什么"，并给出 `adopt / pilot / reject / insufficient_evidence` 四类动作。
- **干预**：任何决策都默认落到最小可验证的干预设计（`intervention.schema.json`），默认偏向最小可验证 PILOT；只有关键 Outcome 存在较强直接证据、风险可控且场景高度匹配时才允许 ADOPT。Pilot 必须带 Stop Conditions 与 Evidence Alignment。
- **评价**：为 PILOT / ADOPT 配套评价方案（`evaluation.schema.json`），强制分离 Task Performance 与 Learning Effect，并单独设计 Retention Test 与 Transfer Test。

### 1.2 第 2 层：EvidenceFlow Protocol

证据流协议采用 **Canonical Protocol**（见文首「唯一权威定义」）：**Research Core 六阶段**（证据纪律核心）+ **Decision Extension 三阶段**（证据到行动）= **9 步端到端**；`Present` 为最终呈现层，不计入协议阶段。

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

执行层负责把第 1、2 层的能力实际跑起来，提供两种运行模式。

## 二、双运行模式

### Mode A：Platform Native Mode（平台原生模式）

- **不依赖** daemon、CLI、Agent MCP 或任何外部进程，是纯提示词/静态技能交付。
- **SKILL.md 可单独理解**：单文件包含领域知识、EvidenceFlow Protocol、JSON Schema 说明、示例与复现命令，任一支持自定义指令的 AI 平台均可直接加载。
- 适合：Claude Projects、ChatGPT Custom Instructions、Cursor Rules 等"以文档为技能载体"的平台。
- 局限：检索依赖模型自身或平台内建工具，上下文不持久，跨会话一致性靠提示词保证。

### Mode B：Agent MCP Enhanced Mode（Agent MCP 增强模式）

在 Mode A 基础上，通过 MCP（Model Context Protocol）接入执行工具，获得以下增强能力：

- **多 CLI**：可同时挂载检索、代码、测试、Schema 校验等命令行工具，检索不再是模型"猜测来源"，而是真实调用检索器。
- **多模型**：允许检索/抽取/裁决由不同模型承担，例如轻量模型负责 Retrieve，强推理模型负责 Adjudicate。
- **独立上下文**：每个子任务拥有独立 Context，避免长对话稀释关键证据，裁决阶段再合并。
- **超时恢复**：子任务可设置超时与重试，网络/工具失败可降级回 Mode A 语义继续。
- **成本优化**：按阶段选择模型与 Token 预算，Framing 与 Extraction 用低成本路径，裁决与审计用高成本路径。
- **Memory Bank**：跨会话缓存已审来源、历史裁决与常用检索词，二次提问命中缓存则跳过重复检索。

| 能力维度 | Mode A Platform Native | Mode B Agent MCP Enhanced |
|----------|------------------------|---------------------------|
| 依赖 | 无（纯 SKILL.md） | daemon / CLI / MCP Server |
| 检索 | 模型内建/平台工具 | 真实多 CLI 检索 |
| 模型 | 单模型 | 多模型分工 |
| 上下文 | 单上下文 | 独立子上下文 + 汇总 |
| 超时 | 无 | 可配置超时与恢复 |
| 成本 | 固定 | 分阶段 Token 预算优化 |
| 记忆 | 无 | Memory Bank 跨会话缓存 |

**推荐组合**：文档与协议以 Mode A 形式交付（任何人可独立理解与使用），接入 MCP 后自动升级为 Mode B（检索更真实、决策更稳健、成本更低）。

## 三、项目目录结构

```
edu/
├── SKILL.md                # 技能入口：EduEvidence 使用说明（Mode A 可独立理解）
├── README.md / README.en.md# 双语说明（英文 / 中文）
├── pyproject.toml          # 打包元数据（wheel 自带 CLI + engine；核心零第三方依赖）
├── install.sh              # 一键安装（本地 / 多 Agent Skill）+ 自检
├── skill/                  # 技能组件
│   ├── agents/             # 8 个角色协议（education-planner / evidence-retriever /
│   │                       # evidence-analyst / skeptic / method-reviewer /
│   │                       # evidence-judge / intervention-designer / evaluation-designer）
│   ├── sub-skills/        # 12 个子技能 SKILL.md（原 skills/，v5 合并至此）
│   └── task-briefs/        # 任务简报模板
├── references/             # 15 份教育方法论文档（education-framing / outcome-taxonomy /
│                           # evidence-quality / methodology-audit / skeptic-protocol /
│                           # tribunal-policy / applicability-policy / intervention-design /
│                           # evaluation-design / retrieval-protocol / source-validity）
├── schemas/                # 13 个顶层 JSON Schema 数据契约 + schemas/v2/（V2 契约）
│   ├── education-frame.schema.json
│   ├── source.schema.json
│   ├── fetch-result.schema.json
│   ├── evidence.schema.json
│   ├── cross-model-review.schema.json
│   ├── methodology.schema.json
│   ├── verdict.schema.json
│   ├── intervention.schema.json
│   ├── evaluation.schema.json
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
├── examples/               # 端到端示例（按教育问题组织）
│   └── ai-coding-assistant/ # 主 Demo：大一 C 语言课程 AI 编程助手
├── docs/                   # 本文档（架构/方法学/Benchmark/Demo/复现指南）
└── tests/                  # pytest 测试
```

各目录职责单一：`schemas/` 是协议契约，`scripts/` 是校验与评测入口，`benchmarks/` 沉淀评估资产，`examples/` 提供可复现案例，`docs/` 解释"为什么这样设计"。

## 四、设计原则

1. **领域层独立于 Agent 层**：EduEvidence 的判断逻辑不耦合任何框架，未来换 Agent 方案时第 1、2 层无需改动。
2. **协议可剥离**：EvidenceFlow Protocol 可脱离 MCP 单独执行，保证最低运行成本可用。
3. **决策可追溯**：从 Verdict 出发可反查到 evidence_id、source_location、方法学审计项与置信度分解。
4. **默认偏向最小可验证 PILOT**：领域层内置"先试点、后部署"约束，从架构上防止跳过验证直接给出全量方案；只有关键 Outcome 存在较强直接证据、风险可控且场景高度匹配时才允许 ADOPT。
5. **降级友好**：Mode B 的任何子任务失败，都可降级为 Mode A 语义继续产出，保证结果不中断。
