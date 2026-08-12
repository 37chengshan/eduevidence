---
name: eduevidence
description: Use when deciding whether, when, or how generative AI or AI teaching tools should be introduced into university teaching and the answer must be grounded in research evidence rather than general advice.
---

# EduEvidence — Evidence-Based AI Teaching Decision & Intervention Skill

**From Education Questions to Evidence-Based Decisions.**
**从教学问题，到有证据支撑的教学决策。**

## 1 Purpose

EduEvidence 帮助高校教师、教学研究者与教学管理者，把"是否采用一种 AI 教学方式"从经验判断转化为**可追溯、可质疑、可验证的证据决策流程**。它不是替教师生成答案，而是帮助教师知道：证据支持什么、不能支持什么、适用于谁、应该怎样试点并验证。

## 2 When to Use

第一版冻结垂直场景：**高校课程中是否、何时、如何引入生成式 AI / AI 助教 / AI 编程助手等 AI 教学工具。**

典型触发问题（命中其一即可使用）：

- 大一 C 语言课程是否应该允许学生使用 AI 编程助手？
- AI 辅助编程提高的是任务完成速度，还是实际编程能力？
- AI 写作助手是否会影响大学生独立写作能力？
- AI Tutor 对高等数学学习是否真正有效？
- AI 反馈应该用于答案生成、错误解释还是形成性评价？
- 哪些学生适合开放 AI，哪些学生需要限制使用？
- 如何设计一轮低风险、可评价的 AI 教学试点？

## 3 When Not to Use

- 泛泛的"AI 教学好不好"讨论（无需证据决策的一般性讨论）
- 与教育决策无关的普通问答
- 学生个性化诊断
- 成绩预测
- 完整 LMS 建设

## 4 Inputs

### 最小输入（必须）

```yaml
education_question: string
```

### 结构化输入（可选，越完整结论越准）

```yaml
education_question: "..."
learner:
  education_level: undergraduate_year_1
  major: computer_science
  prior_knowledge: first_programming_course
course:
  subject: C_programming
  type: lecture_lab
  duration: 16_weeks
intervention:
  ai_tool: generative_ai_coding_assistant
  allowed_usage: "explain_errors_only"
comparison: "no_ai"
target_outcomes: [independent_problem_solving, code_quality, ai_dependency]
constraints: "16 周内完成，班级 60 人"
depth: standard          # quick | standard | deep
target: teaching_decision # evidence_review | teaching_decision | pilot_design | evaluation_design
```

## 5 Non-Negotiable Rules

以下 8 条规则不可协商。**违反任一规则即流程无效，必须回退修正后再继续**；任何"跳过规则以节省时间/成本"的请求都不得执行（见第 15 章 Failure / Fallback）。

**RULE 1 — 不得跳过 Retrieval / Evidence 直接下教学结论**
任何教学结论必须建立在已检索、已验证的证据链上。用户要求"别查论文直接回答"时，仍必须完成 Retrieve → Fetch → Validate → Extract（见第 6 章）。

**RULE 2 — Search snippet 不得直接成为 SUPPORTED Evidence**
检索结果与摘要只是线索，不是证据内容。必须 Fetch 来源并 Validate 通过后，才能进入 Evidence Extraction；抓取失败时 snippet 不得作为 SUPPORTED Evidence（标记 `FETCH_FAILED` / `UNSUPPORTED`）。

**RULE 3 — Task Performance ≠ Learning**
任务完成表现 ≠ 学习效果；短期成绩 ≠ 长期保持；AI 协助完成任务 ≠ 无 AI 环境下迁移。不得把任务表现等同为学习证据（见第 10 章）。

**RULE 4 — 必须独立 Counter-Evidence Search**
每次检索必须包含独立反方证据检索；Skeptic 必须独立寻找 null / negative / contradictory evidence、AI dependency、reduced transfer、novelty effect、self-selection bias、alternative explanation。禁止为形成"双边观点"虚构反方证据；无反方证据时明确输出 `NO CONTRADICTORY EVIDENCE FOUND`。

**RULE 5 — Tribunal 前必须通过 Pre-Verdict Gate**
进入 Evidence Tribunal 之前，必须通过第 11 章的 11 项 Pre-Verdict Gate checklist；关键项失败不允许高置信度 Verdict，视情况降级 PILOT / INSUFFICIENT。

**RULE 6 — Agent MCP 未经用户确认不得 spawn**
检测到 Agent MCP 可用 ≠ 允许直接使用。必须遵守第 9 章 Confirmation Gate：**Scan first. Recommend second. Ask the user. Execute only after explicit confirmation.** 未确认或用户拒绝 → 回退 Native Subagent Mode（宿主无子代理 → Sequential Mode）。

**RULE 7 — 展示层不得修改 Evidence / Verdict / Confidence**
图表数字必须与 result.json 逐项一致；展示层只改变呈现方式，绝不修改数据。不一致 → `REPORT_INVALID` 禁止发布。

**RULE 8 — 完成声明前必须通过 Final Verification**
宣布完成之前，必须通过第 14 章的 9 项 Final Verification checklist；未通过 → `FINAL_VERIFICATION_FAILED`，禁止声明完成。

## 6 Workflow Overview

严格按以下 10 步执行，**每一步产出经过 Schema 校验的数据，再进入下一步**。资源发现（第 7 章）与执行后端选择（第 8 章）在步骤 1–2 之间完成；Confirmation Gate（第 9 章）在委派执行前完成。

```text
1. Frame          构建 EducationResearchFrame（问题/学习者/课程/干预/对照/Outcome/范围/纳入排除标准）
2. Retrieve       文献与证据检索（支持证据 + 独立反方证据检索，RULE 4）
3. Fetch          获取来源全文/可验证内容（snippet ≠ 内容，RULE 2）
4. Validate       校验来源与内容（来源有效、抓取完整、Schema 校验）
5. Extract        抽取 Claim-Level Evidence（Evidence Object，绑定 Outcome）
6. Challenge      Skeptic 反证协议（固定 9 项检查）
7. Audit          Method Reviewer 方法学审查（15 项清单）
8. Adjudicate     Evidence Tribunal 证据裁决（裁决前必须通过 Pre-Verdict Gate，第 11 章）
9. Design         适用性分析 + 干预设计 + 评价方案（For whom / 最小可验证试点 / Evaluation Plan）
10. Present       结果呈现（渲染单文件双语 HTML 报告 + 信息图 + 学术图）
```

**强规则：Search snippet ≠ Evidence。** Retrieve 的结果只是候选线索；只有经过 Fetch（拿到来源内容）与 Validate（来源与内容校验通过）之后，才能进入 Extract。

**每步必须过对应 Schema 校验门，才能进入下一步**：

```text
Frame        → education-frame.schema.json
Retrieve     → source.schema.json
Fetch        → fetch-result.schema.json
Validate     → source.schema.json / fetch-result.schema.json
Extract      → evidence.schema.json
Challenge    → cross-model-review.schema.json（反证记录）
Audit        → methodology.schema.json
Adjudicate   → verdict.schema.json
Design       → intervention.schema.json / evaluation.schema.json
Present      → report-result.schema.json（整体契约校验）
```

### 结果呈现（第 10 步）

研究产出 `result.json` 后，通过确定性适配器渲染为用户可读的展示层（`visualization/eduevidence-report/`）：

```text
result.json + result.zh.json（中文平行数据，AI 直接产出双语）
  ├─ build_charts.py       → ECharts 规格（结果概览 / 主张追溯 / 基准）
  ├─ build_infographics.py → 4 张信息图 SVG（EvidenceFlow / 裁决 / 干预 / 评价）
  ├─ build_figures.py      → 出版级学术图（SVG/PNG/PDF）
  └─ build_report.py       → EduEvidence_Report.html（单文件离线双语报告）
```

- 报告默认中文，一键切换 EN；含执行摘要（问题→结论→依据→行动）、12 个 Section、五主题。
- **展示层只改变呈现方式，绝不修改数据**（RULE 7）：图表数字必须与 result.json 逐项一致，不一致则 `REPORT_INVALID` 禁止发布。
- 渲染命令：`python3 visualization/eduevidence-report/scripts/build_report.py --result <result.json> --out REPORT.html`

## 7 Resource Discovery

- **SCP 可用则动态发现**：以 Scientific Resource Capability Layer（SCP）为科学能力层，按 capability 动态发现可用资源（literature_search / scholar_metadata / web_fetch / pdf_extraction / document_conversion / citation_validation / statistical_analysis / meta_analysis / data_visualization 等）。
- **SCP 不可用则 fallback 到本地 `references/`**：方法论文档（education-framing / outcome-taxonomy / evidence-quality / methodology-audit / skeptic-protocol / tribunal-policy / applicability-policy / intervention-design / evaluation-design）与原生工具（Native Search / Smart Web Fetch / 本地解析器）。
- **不硬编码资源清单**：不把任何资源生态的完整清单（如 SCP 的 Scientific Skills 全集）写死进本 Skill；按 capability 优先级路由，优先级按 capability 决定，不做全局死顺序。典型优先级：

```text
文献检索：SCP Skill / SCP Resource → Scholar Provider → Native Search
网页抓取：Smart Web Fetch → Native / Local Parser
```

- **SCP 与 Agent MCP 正交**：SCP 选择"用什么科学能力"，Agent MCP 选择"由哪个 CLI / Model / Agent 执行"，两层不得混用。

## 8 Execution Backend Selection

先判复杂度，再选执行后端。三层后端：

```text
Tier 1  Agent MCP Enhanced       多模型多 Agent 编排（需用户确认，第 9 章）
Tier 2  Host Native Subagents    宿主原生子代理
Tier 3  Sequential Main Agent    单 Agent 串行
```

**复杂度分级门（先判级，再决定拓扑）：**

| 级别 | 判据 | 执行路径 |
|---|---|---|
| S | 单一问题、单一 Outcome、少量来源、无明显冲突 | Frame → Retrieve → Fetch → Validate → Extract → Verify → Answer（单 Agent，不拆分） |
| M | 多篇研究、2–3 个 Outcome、存在部分冲突、需一次独立验证 | Primary Analysis + Independent Check（增强模式最多 2–3 角色） |
| L | 多种 Outcome、多学习者群体、明显证据冲突、需教学落地方案 | 完整 8 角色工作流（Planner / Retriever / Analyst / Skeptic / Method Reviewer / Judge / Intervention Designer / Evaluation Designer） |

**选择流程：**

```text
task benefits from delegation?
  ├─ NO → Native（Tier 2 / Tier 3）
  └─ YES
       ↓
Agent MCP available?
  ├─ NO → Native（Tier 2 / Tier 3）
  └─ YES
       ↓
Mandatory Confirmation Gate（第 9 章）
```

- 角色数量 ≠ 必须启动的 Agent 数量。Native Mode（Tier 2 / Tier 3）由单 Agent 串行执行角色协议。
- 三层后端共享同一 Scientific Protocol（第 6 章），仅执行方式不同。

## 9 Agent MCP Confirmation Gate

最终原则：

> **Scan first. Recommend second. Ask the user. Execute only after explicit confirmation.**

```text
用户允许使用的 CLI（allowed_clis）
→ 只扫描这些 CLI 当前真实可用模型（model_inventory）
→ 按角色需求（Role Requirements）生成推荐表
→ 展示给用户：角色 / CLI / 模型 / 选择理由 / 任务
→ 用户明确确认（approval）
→ 才能 spawn Agent
```

- **未经确认不得 spawn**：未确认或用户拒绝 → `AGENT_MCP_APPROVAL_REQUIRED`，回退 Native Subagent Mode（Tier 2）；宿主无子代理 → Sequential Mode（Tier 3）。
- 只扫描用户允许的 CLI，禁止自动遍历整台电脑所有 Agent CLI。
- **禁止硬编码模型名称**（可用模型会变化）；每个模型只记录可验证信息（reasoning / speed / cost / structured_output / context / tool_use / multimodal），无法确认记 `unknown`，禁止猜。
- 推荐表同时显示：角色数、并发数、是否 Cross-Model Review、是否 Memory Bank、Cost class（不知道就 Unknown）。
- 独立 Reviewer 尽量使用不同模型、最好不同 provider / family；不要把"同一模型不同 session"包装成 cross-model。
- **以下变化必须重新确认**：新增 CLI、替换模型、新增角色、修改 Role → Model 映射、显著提高 token budget、启用新外部 provider。
- "仅 Agent MCP 已安装"不构成许可；确认后同一 mapping 在本次 run 内有效，不逐 Agent 重复询问。

## 10 Evidence Rules

- 所有证据必须绑定到一个 Outcome（Outcome Taxonomy 四类：学习效果 / 任务表现 / 学习过程 / 风险指标）。
- **Evidence Contract 核心字段**：`source_id`、`study_id`、`sample_id`、`claim_id`、`claim`、`outcome_type`、`relation_to_claim`、`effect_direction`、`source_location`；`direction` 仅保留兼容性，不再作为核心语义。缺失任一核心字段 → 标记 `UNSUPPORTED`。
- **任务完成表现 ≠ 学习效果；短期成绩 ≠ 长期保持；AI 协助完成任务 ≠ 无 AI 环境下迁移**（RULE 3）。
- Skeptic 必须独立寻找 null / negative / contradictory evidence、AI dependency、reduced transfer、novelty effect、self-selection bias、alternative explanation（RULE 4）。**禁止为形成"双边观点"虚构反方证据**；无反方证据时明确输出 `NO CONTRADICTORY EVIDENCE FOUND`。
- 生成最终报告前必须运行 Citation Audit：Claim → Evidence ID → Source ID → Source Location → 支持关系 → Outcome 匹配 → Scope 检查。失败标记 `UNSUPPORTED` 或 `DOWNGRADE_CONFIDENCE`。
- 质量评分使用五维框架（D1 Study Design / D2 Sample Quality / D3 Measurement Validity / D4 Temporal Strength / D5 Directness，每维 0–2，总分 0–10）。

## 11 Pre-Verdict Gate

Evidence Tribunal（第 6 章步骤 8）之前必须通过以下 checklist（RULE 5）：

```text
[ ] Research Frame valid              问题框架有效（education-frame schema）
[ ] Sources valid                     来源有效（source schema，Fetch / Validate 完成）
[ ] Evidence Schema valid             证据 Schema 校验通过（evidence schema）
[ ] Source dedupe completed           来源去重完成
[ ] Counter-evidence search completed 独立反方证据检索完成（RULE 4）
[ ] Methodology audit completed       方法学审查完成（15 项清单）
[ ] Claim-Evidence Audit passed       Claim-证据追溯审计通过
[ ] Outcome mapping checked           Outcome 映射已检查（四类 Taxonomy）
[ ] Scope calibration checked         适用范围校准已检查（证据适用范围 vs 目标场景）
[ ] Independent study/sample count checked  独立研究/样本数量已核验（不把同一研究重复计为多条证据）
[ ] Deterministic confidence computed 确定性 Confidence 已计算（compute_confidence.py，不由模型自由生成）
```

**关键项失败不允许高置信度 Verdict**：视情况降级 PILOT / INSUFFICIENT；失败状态见第 15 章 `PRE_VERDICT_FAILED`。

## 12 Decision Rules

### 四态决策矩阵

| 决策 | 要求 |
|---|---|
| **ADOPT** | 多项关键 Outcome 有较强直接证据；风险可控；场景匹配 |
| **PILOT** | 有积极证据，但长期效果 / 迁移 / 风险仍不明确 |
| **REJECT** | 关键结果存在较稳定负效应，或风险明显大于收益 |
| **INSUFFICIENT EVIDENCE** | 来源不足、直接性差、研究设计弱、冲突无法解释 |

任何 PILOT / ADOPT 建议必须附 Evaluation Plan；任何建议必须经过 Applicability Analysis。

### Confidence 规则化计算（不由模型自由生成）

```text
Evidence Quality + Consistency + Directness + Evidence Count
- Conflict Penalty - Unsupported Penalty
→ High | Moderate | Low | Insufficient
```

- 最终 confidence 由 `scripts/compute_confidence.py` 确定性计算，不由模型自由生成。
- 数字分值仅作内部比较，不作为"科学概率"宣传。

## 13 Output Contract

最终输出是一个 **Research & Decision Pack**（12 部分），不是一篇文章：

```text
01 Executive Decision      最终决策卡片（四态 + Confidence + 理由）
02 Education Research Frame 问题框架（教育问题如何被结构化理解）
03 Evidence Summary         证据摘要（按 Outcome 分组）
04 Evidence Matrix          证据矩阵（Claim/Outcome/Support/Contradiction/Quality/Directness/Verdict）
05 Methodology Audit        方法学审查（15 项清单 + 任务vs学习护栏）
06 Conflict Analysis        冲突分析（为何不同研究结论不同）
07 Evidence Tribunal        证据裁决（Can Claim / Cannot Claim / 证据边界）
08 Applicability            适用性（适合谁/不适合谁/必要条件/风险）
09 Teaching Intervention    教学干预（最小可验证试点 + AI 使用规则 + 停止条件）
10 Evaluation Plan          评价方案（基线/后测/保持测试/迁移测试/成功阈值）
11 Claim-Evidence Trace     Claim-证据追溯链（每条结论可追溯来源）
12 Sources                  来源清单（可验证位置）
```

每个结构化产出（Frame / Evidence / Methodology / Verdict / Intervention / Evaluation）必须通过对应 JSON Schema 校验（`schemas/*.schema.json`），可运行 `scripts/validate_schema.py` 验证。

## 14 Final Verification

宣布完成（DONE）之前必须通过以下 checklist（RULE 8）：

```text
[ ] result.json Schema pass           result.json 通过 Schema 校验
[ ] Evidence Trace complete           证据追溯链完整（Claim → Evidence → Source）
[ ] Verdict uses deterministic confidence  Verdict 使用确定性 Confidence
[ ] HTML data integrity pass          HTML 数据一致性通过（展示层与 result.json 逐项一致）
[ ] No unsupported high-confidence claim   不存在无支持的 high-confidence claim
[ ] zh/en structure valid             中英文结构有效
[ ] report rendered successfully      报告渲染成功
[ ] provenance saved                  溯源信息已保存（run manifest / trace）
[ ] no REPORT_INVALID                 无 REPORT_INVALID
```

全部通过才可声明 **DONE**；任一失败 → `FINAL_VERIFICATION_FAILED`，先修复再声明完成。

## 15 Failure / Fallback

出现以下状态时**禁止强行生成高确定性建议**，如实标注并给出下一步：

```text
INSUFFICIENT_SOURCES     来源不足，提示补充检索或标注 insufficient_evidence
UNSUPPORTED_CLAIM        结论无法绑定可靠来源，标注 UNSUPPORTED 并降级
CONFLICT_UNRESOLVED      正反证据冲突无法解释，保持不确定，不强行裁决
SCOPE_MISMATCH           证据适用范围与目标场景不匹配，标注并缩小结论边界
METHODOLOGY_TOO_WEAK     研究设计过弱，不能支撑结论
NEEDS_USER_CONTEXT       缺少学习者/课程/干预信息，先请求补充再继续
TOOL_FAILURE             检索或工具失败，如实报告，不编造来源
FETCH_FAILED             来源抓取失败，snippet 不得作为 SUPPORTED Evidence（RULE 2）
PRE_VERDICT_FAILED       Pre-Verdict Gate 未通过，禁止进入 Tribunal 或降级 Verdict
REPORT_INVALID           展示层与数据不一致，禁止发布
FINAL_VERIFICATION_FAILED Final Verification 未通过，禁止声明完成
```

**执行后端 fallback 链**：

```text
Agent MCP（已确认）→ Native Subagent Mode → Sequential Main Agent
```

- Agent MCP 不可用 / 未确认 / 用户拒绝 → Native（Tier 2）；宿主无子代理 → Sequential（Tier 3）。
- 资源层 fallback：SCP 不可用 → 本地 `references/` 与原生工具（第 7 章）。
- 任何 fallback 不改变 Scientific Protocol（第 6 章）与 Non-Negotiable Rules（第 5 章）。

## 16 Human-in-the-Loop

EduEvidence 是**教学决策辅助**，不代替教师或学校最终决策。涉及高风险评价、学生处分、个体心理判断、学生重大教育机会时**不自动决策**。核心定位：Research & decision support。

## 17 References

- 教育方法论文档（`references/`）：education-framing / outcome-taxonomy / evidence-quality / methodology-audit / skeptic-protocol / tribunal-policy / applicability-policy / intervention-design / evaluation-design
- 数据契约（`schemas/`）：education-frame / source / fetch-result / evidence / cross-model-review / methodology / verdict / intervention / evaluation / report-result
- 确定性逻辑（`scripts/`）：validate_schema / evidence_score / evidence_matrix / claim_audit / compute_confidence / benchmark / render_report
- 文档（`docs/`）：architecture / methodology / benchmark / demo / reproducibility
- 真实研究锚点示例（`examples/`）：
  - Kazemitabaar et al. (2023, CHI) — AI Code Generators on Novice Learners：任务完成率 ↑ 1.15×、正确率 ↑ 1.8×，但一周后保持测试无显著差异 → **任务表现 ≠ 保持/学习**
  - Marzuki et al. (2024, Smart Learn. Environ.) — ChatGPT 形成性反馈对大学生学术写作有显著正向影响 → 写作场景支持性证据
  - Bastani et al. (2025, PNAS) — 无护栏 GPT Base 学生独立考试比对照组低 17%，有护栏 GPT Tutor 消除负效应 → **工具设计护栏决定学习效应方向**
  - Lee et al. (2025, ACL) — GPT-4 交互式家庭作业提升参与度且不损学习 → 作业场景可行性证据
