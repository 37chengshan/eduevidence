---
name: eduevidence
description: Use when an education question about whether, when, and how to introduce generative AI / AI teaching tools into university courses must be answered with evidence — structured research framing, claim-level evidence extraction, counter-evidence search, methodology audit, evidence tribunal, applicability analysis, pilot intervention design, and evaluation planning. From education questions to evidence-based decisions.
---

# EduEvidence — Evidence-Based AI Teaching Decision & Intervention Skill

**From Education Questions to Evidence-Based Decisions.**
**从教学问题，到有证据支撑的教学决策。**

EduEvidence 帮助高校教师、教学研究者与教学管理者，把"是否采用一种 AI 教学方式"从经验判断转化为**可追溯、可质疑、可验证的证据决策流程**。它不是替教师生成答案，而是帮助教师知道：证据支持什么、不能支持什么、适用于谁、应该怎样试点并验证。

## When to Use

第一版冻结垂直场景：**高校课程中是否、何时、如何引入生成式 AI / AI 助教 / AI 编程助手等 AI 教学工具。**

典型触发问题（命中其一即可使用）：

- 大一 C 语言课程是否应该允许学生使用 AI 编程助手？
- AI 辅助编程提高的是任务完成速度，还是实际编程能力？
- AI 写作助手是否会影响大学生独立写作能力？
- AI Tutor 对高等数学学习是否真正有效？
- AI 反馈应该用于答案生成、错误解释还是形成性评价？
- 哪些学生适合开放 AI，哪些学生需要限制使用？
- 如何设计一轮低风险、可评价的 AI 教学试点？

不使用本 Skill：泛泛的"AI 教学好不好"讨论、与教育决策无关的普通问答、学生个性化诊断、成绩预测、完整 LMS 建设。

## Inputs

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

## Workflow

严格按 EvidenceFlow Protocol 执行，**每一步产出经过 Schema 校验的数据，再进入下一步**。

```text
1. Frame          构建 EducationResearchFrame（问题/学习者/课程/干预/对照/Outcome/范围/纳入排除标准）
2. Retrieve       文献与证据检索（支持证据 + 独立反方证据检索）
3. Extract        抽取 Claim-Level Evidence（Evidence Object，绑定 Outcome）
4. Challenge      Skeptic 反证协议（固定 9 项检查）
5. Audit          Method Reviewer 方法学审查（15 项清单）
6. Adjudicate     Evidence Tribunal 证据裁决（Evidence Matrix + Verdict）
7. Applicability  适用性分析（For whom / which course / which outcome / what conditions）
8. Intervene      Teaching Intervention 设计（最小可验证试点，禁止直接全面部署）
9. Evaluate       Evaluation Plan 设计（任何 PILOT/ADOPT 建议必须附评价方案）
```

**复杂度分级门（先判级，再决定拓扑）：**

| 级别 | 判据 | 执行路径 |
|---|---|---|
| S | 单一问题、单一 Outcome、少量来源、无明显冲突 | Frame → Retrieve → Extract → Verify → Answer（单 Agent，不拆分） |
| M | 多篇研究、2–3 个 Outcome、存在部分冲突、需一次独立验证 | Primary Analysis + Independent Check（增强模式最多 2–3 角色） |
| L | 多种 Outcome、多学习者群体、明显证据冲突、需教学落地方案 | 完整 8 角色工作流（Planner / Retriever / Analyst / Skeptic / Method Reviewer / Judge / Intervention Designer / Evaluation Designer） |

> 角色数量 ≠ 必须启动的 Agent 数量。Platform Native Mode 由单 Agent 串行执行角色协议。

## Decision Rules

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

数字分值仅作内部比较，不作为"科学概率"宣传。

## Evidence Rules

- 所有证据必须绑定到一个 Outcome（Outcome Taxonomy 四类：学习效果 / 任务表现 / 学习过程 / 风险指标）。
- 强制字段：`source_id`、`claim`、`outcome_type`、`direction`、`source_location`。缺失任一 → 标记 `UNSUPPORTED`。
- **任务完成表现 ≠ 学习效果；短期成绩 ≠ 长期保持；AI 协助完成任务 ≠ 无 AI 环境下迁移。**
- Skeptic 必须独立寻找 null / negative / contradictory evidence、AI dependency、reduced transfer、novelty effect、self-selection bias、alternative explanation。**禁止为形成"双边观点"虚构反方证据**；无反方证据时明确输出 `NO CONTRADICTORY EVIDENCE FOUND`。
- 生成最终报告前必须运行 Citation Audit：Claim → Evidence ID → Source ID → Source Location → 支持关系 → Outcome 匹配 → Scope 检查。失败标记 `UNSUPPORTED` 或 `DOWNGRADE_CONFIDENCE`。
- 质量评分使用五维框架（D1 Study Design / D2 Sample Quality / D3 Measurement Validity / D4 Temporal Strength / D5 Directness，每维 0–2，总分 0–10）。

## Output Contract

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

## Failure Handling

出现以下状态时**禁止强行生成高确定性建议**，如实标注并给出下一步：

```text
INSUFFICIENT_SOURCES     来源不足，提示补充检索或标注 insufficient_evidence
UNSUPPORTED_CLAIM        结论无法绑定可靠来源，标注 UNSUPPORTED 并降级
CONFLICT_UNRESOLVED      正反证据冲突无法解释，保持不确定，不强行裁决
SCOPE_MISMATCH           证据适用范围与目标场景不匹配，标注并缩小结论边界
METHODOLOGY_TOO_WEAK     研究设计过弱，不能支撑结论
NEEDS_USER_CONTEXT       缺少学习者/课程/干预信息，先请求补充再继续
TOOL_FAILURE             检索或工具失败，如实报告，不编造来源
```

## Human-in-the-Loop

EduEvidence 是**教学决策辅助**，不代替教师或学校最终决策。涉及高风险评价、学生处分、个体心理判断、学生重大教育机会时**不自动决策**。核心定位：Research & decision support。

## References

- 教育方法论文档（`references/`）：education-framing / outcome-taxonomy / evidence-quality / methodology-audit / skeptic-protocol / tribunal-policy / applicability-policy / intervention-design / evaluation-design
- 数据契约（`schemas/`）：education-frame / evidence / methodology / verdict / intervention / evaluation
- 确定性逻辑（`scripts/`）：validate_schema / evidence_score / evidence_matrix / claim_audit / benchmark / render_report
- 文档（`docs/`）：architecture / methodology / benchmark / demo / reproducibility
- 真实研究锚点示例（`examples/`）：
  - Kazemitabaar et al. (2023, CHI) — AI Code Generators on Novice Learners：任务完成率 ↑ 1.15×、正确率 ↑ 1.8×，但一周后保持测试无显著差异 → **任务表现 ≠ 保持/学习**
  - Marzuki et al. (2024, Smart Learn. Environ.) — ChatGPT 形成性反馈对大学生学术写作有显著正向影响 → 写作场景支持性证据
  - Bastani et al. (2026, PNAS) — 无护栏 GPT Base 学生独立考试比对照组低 17%，有护栏 GPT Tutor 消除负效应 → **工具设计护栏决定学习效应方向**
  - Lee et al. (2025, ACL) — GPT-4 交互式家庭作业提升参与度且不损学习 → 作业场景可行性证据
