# EduEvidence Benchmark 设计

Benchmark 回答两个问题：**方法论有没有用**（EduEvidence 是否优于普通研究 Agent）与**多 Agent 有没有用**（EduEvidence+Agent MCP 是否优于 Single-Agent）。本文档定义第一版评测题目集、基线、消融与指标。

## 零、Simulation 与 Empirical 分层（必须先读）

Benchmark 分两层，**只有第二层可作为性能证据**：

| 层 | 名称 | 数据 | 用途 | 能否作性能证据 |
|----|------|------|------|----------------|
| Layer A | Harness Validation | deterministic simulation（`benchmark_v2.py`，固定种子 + 人工预设 profile） | 验证题目集 / evaluator / 报告 / 图表 / 成本字段 / Ablation 管线可运行 | ❌ 不能，产物必须标注 `SIMULATED` |
| Layer B | Empirical Runs | B0–B4 真实模型调用 | 证明方法论 / 多 Agent 的真实增益 | ✅ 唯一可用证据 |

**Empirical Run 必须记录 run manifest**：模型家族与版本、temperature、工具集、检索 provider、题目版本、时间戳、重复次数（≥3，最好 5）、每次的 token / latency / cost，报告均值 + 方差 / CI。

**指标升级要求（gold-based）**：Citation Support 由独立标注判断 Claim 与 Source excerpt 是否一致；Outcome Separation Accuracy 对照 gold outcome 而非只查枚举；Scope Calibration 对照 gold allowed_scope；Contradiction Discovery 同时报告 precision 与 recall。


## 一、评测题目集（第一版 30 题）

### 1.1 结构与复杂度分布

30 题按 Complexity Gate 均分三级：

| 复杂度 | 题数 | 判定特征 | 题目来源 |
|--------|------|----------|----------|
| S | 10 | 单课常规教学决策，证据较充足 | 课程内教学方法选择 |
| M | 10 | 跨课/跨专业，存在正反证据 | 教学工具与心理干预 |
| L | 10 | 全校/政策级，证据冲突或缺失 | 学术诚信、评价体系改革 |

### 1.2 领域分布

| 领域 | 题数 | 示例主题 |
|------|------|----------|
| 高校 AI 辅助教学 | 15 | 编程课是否允许 Copilot、AI 写作助手对论文写作的影响 |
| 教学方法 | 5 | 翻转课堂 vs 讲授、同伴互评 vs 教师评分 |
| 学习心理 | 5 | 认知负荷、自我效能、动机对成绩的作用 |
| 评价 / 教育技术 | 5 | 形成性评价频率、电子白板/在线平台有效性 |

### 1.3 题目格式（questions.jsonl）

每题包含（与 `scripts/benchmark.py validate_questions()` 严格一致）：

| 字段 | 说明 |
|------|------|
| `id` | 唯一编号，如 `Q01` |
| `level` | 复杂度 S / M / L（S×10、M×10、L×10） |
| `domain` | `ai_higher_education` / `teaching_methods` / `learning_psychology` / `assessment_edtech` |
| `question` | 原始教育问题（中文） |
| `expected_outcomes` | 期望考察的 Outcome 枚举（须在 20 类 Outcome Taxonomy 内） |
| `notes` | 难度与考察点说明 |

期望决策与已知反方证据等人工金标注放在 `benchmarks/annotations/gold-<id>.json`（字段：`key_claims` / `key_supporting_sources` / `known_contradictions` / `correct_outcome_types` / `allowed_scope` / `known_methodological_limitations` / `expected_decision_range`）。

## 二、基线与关键对比（B0–B4）

| 基线 | 全称 | 定义 |
|------|------|------|
| B0 | Direct LLM | 直接问模型"该不该这样做"，无检索、无协议 |
| B1 | Search+LLM | 模型先做一次搜索，再直接回答 |
| B2 | Standard Research Agent | 通用研究 Agent：检索+摘要，无教育方法学约束 |
| B3 | EduEvidence Single-Agent | 单模型按 EvidenceFlow Protocol 跑完八角色 |
| B4 | EduEvidence+Agent MCP | 多 CLI/多模型/独立上下文/超时恢复/Memory Bank |

### 2.1 关键对比对

| 对比 | 目的 | 证明的命题 |
|------|------|------------|
| **B2 vs B3** | 方法论价值 | 同样是单 Agent，加上教育方法学协议（Skeptic、Method Reviewer、规则化置信度）后，Citation Support Precision 与 Unsupported Claim Rate 显著改善 → **证明"方法论价值"** |
| **B3 vs B4** | 多 Agent 价值 | 同一套方法论，接入 Agent MCP（真实检索、多模型、独立上下文）后，检索真实性与证据覆盖面提升 → **证明"多 Agent 价值"** |

### 2.2 对比设计约束

- 三对基线使用**同一模型家族**，避免把"模型能力差异"误读成"方法学差异"；
- B0/B1/B2 不提供任何 EduEvidence schema 与协议；
- B3/B4 使用同一套 Protocol 与 Schema，仅执行层不同；
- 每对对比在 30 题上逐题配对，用同题差分（per-question delta）统计显著性。

## 三、消融实验（Ablation A1–A7）

逐项关闭协议组件，量化每个组件的边际贡献：

| 消融 | 关闭的组件 | 观察指标 |
|------|------------|----------|
| A1 | 去掉 Skeptic | Contradiction Discovery Rate 是否崩塌 |
| A2 | 去掉 Method Reviewer | Unsupported Claim Rate 是否上升（把任务完成当学习） |
| A3 | 去掉规则化 Confidence（改让模型自评） | Confidence 与人工标注的偏差是否扩大 |
| A4 | 去掉 Unsupported Penalty | 幻觉来源是否回流 |
| A5 | 跳过 Complexity Gate（全部走 S 路径） | L 级题目指标是否显著劣化 |
| A6 | 去掉 Memory Bank（B4 降级） | 重复题目上的时间/成本与一致性变化 |
| A7 | 单模型跑全流程（B4 降为 B3） | 独立上下文与多模型分工的增量价值 |

A1–A7 全部以 B3（单 Agent 全协议）为基准对比，归因到单一变量。

## 四、核心指标

| 指标 | 英文名 | 定义 / 计算 |
|------|--------|-------------|
| 引用支撑精度 | Citation Support Precision | 输出中每个引用的 claim 与来源原文是否一致，一致率 |
| 无支撑声称率 | Unsupported Claim Rate | 输出中缺乏证据支撑/编造来源的声称占比（对应 UNSUPPORTED） |
| 矛盾发现率 | Contradiction Discovery Rate | 能主动报告与主结论冲突的负面/反驳证据的题目占比 |
| 结果分离准确率 | Outcome Separation Accuracy | 是否正确区分 Immediate / Retention / Transfer 与 Task vs Learning |
| 范围校准 | Scope Calibration | 结论是否被限制在检索 scope 与 evidence boundary 之内（exceeds_evidence_boundary 越少越好） |
| 干预证据对齐 | Intervention Evidence Alignment | 输出的 PILOT 设计是否能逐条追溯回 evidence_id |

### 4.1 指标口径

- 每项指标都由 `benchmarks/annotations/` 中的人工标注作为 ground truth，评估器（`benchmarks/evaluator/`）自动计算；
- Confusion 类指标（Contradiction、Unsupported）同时报告 precision 与 recall，防止"少说少错"刷分；
- Outcome Separation 与 Scope Calibration 为多档评分（0/1/2），由标注者对输出逐条打分。

## 五、工程指标

在核心指标之外，记录运行层面的工程表现：

| 类别 | 指标 |
|------|------|
| 时间 | 端到端延迟（中位数 P50 / 长尾 P95）、每阶段耗时分解 |
| 成本 | 每题 Token 消耗、预估成本（按模型单价）、Memory Bank 命中率带来的成本节省 |
| 稳定性 | 同题重复运行（×5）结论一致率、超时重试率、降级恢复率 |
| 规模 | 证据条数、来源数、检索调用次数、审计项覆盖率 |
| 工程健壮性 | Schema 校验通过率（100% 为合格线）、失败注入下的存活率 |

## 六、评估流程

1. `python scripts/benchmark.py --questions benchmarks/questions.jsonl` 逐题运行五个基线与消融；
2. 输出落到 `benchmarks/results/`，生成 per-question JSON；
3. `benchmarks/evaluator/` 对照 `benchmarks/annotations/` 计算核心指标；
4. 汇总输出对比表：B2 vs B3、B3 vs B4 的差值、方向与显著性。

## 七、第一版接受标准

- B3 相比 B2：Unsupported Claim Rate 相对下降 ≥ 30%，Citation Support Precision 上升 ≥ 15 个百分点；
- B4 相比 B3：Contradiction Discovery Rate 上升 ≥ 20 个百分点，P95 延迟与成本不劣于 B3；
- B0/B1 的 Unsupported Claim Rate 显著高于 B3，作为"基线很弱"的 sanity check；
- A1（去 Skeptic）与 A2（去 Method Reviewer）造成对应指标明显回退，证明组件不可移除；
- 30 题全部通过 `validate_schema.py` 校验。
