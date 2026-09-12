# Report Copy Style — 读者向文案规范

本规范约束**报告里面向读者的文字**（第一屏决策叙事、裁决列表、章节引导语、图表标题与说明）。它服务于一个判断标准：**读者能否一次读懂，且能核对**。规则由 `skill/agents/evidence-judge.md`（写作前）与 `visualization/eduevidence-report/scripts/build_report.py` 的语言门禁（交付后）双向执行。

## 1. 谁写什么

| 内容 | 作者 | 说明 |
|---|---|---|
| 决策叙事四件套（`strongest_support` / `key_uncertainty` / `main_risk` / `next_action`） | **裁决角色（模型）撰写** | 渲染器只呈现，缺字段就报缺，禁止用列表片段拼装句子 |
| `decision_rationale` | 裁决角色 | ≤4 句，可独立阅读 |
| 章节引导语、图例、按钮、兜底句 | 渲染器（固定文案表） | 不随研究内容变化 |
| 证据与主张原文 | 抽取/裁决角色 | 渲染器不改写 |

**为什么写死这条**：报告第一屏曾由渲染器从 `what_can_be_claimed[0]` 之类的片段拼出，读起来像拼装而非撰写，且掩盖了「该字段没人产出」这一事实。撰写责任在模型，呈现责任在渲染器。

## 2. 语言

- 面向**非本领域的决策者**：不假设读者熟悉术语。
- 一句话一个意思；先结论、后依据。
- 中文用中文，英文用英文；两种语言各自成篇，不做逐字直译。
- 允许保留原文的例外：AI、RCT、DOI、WWC、GRADE、论文原标题（须标注「原文标题」）。

## 3. 字数上限

| 字段 | 上限 | 约合 |
|---|---|---|
| `strongest_support` | 60 字 | 2 句 |
| `key_uncertainty` | 70 字 | 2–3 句 |
| `main_risk` | 60 字 | 2 句 |
| `next_action` | 80 字 | 2–3 句 |
| `decision_rationale` | 160 字 | ≤4 句 |

英文字数上限按等义折算（约为中文字数 ÷ 3 个单词）。

## 4. 术语对照

同一概念全文只用一个说法：

| 内部字段 | 中文 | 英文 |
|---|---|---|
| `outcome` / `outcome_type` | 结果 | outcome |
| `claim` | 主张 | claim |
| `evidence` | 证据 | evidence |
| `relation_to_claim` | 与主张的关系 | relation to claim |
| `effect_direction` | 效应方向 | effect direction |
| `directness` | 直接性 | directness |
| `task_performance` | 任务表现 | task performance |
| `retention` | 保持 | retention |
| `transfer` | 迁移 | transfer |
| `applicability` | 适用性 | applicability |

## 5. 禁止

- 内部字段名与存储标识（`effect_direction`、`first_programming_course_...`）出现在叙述句里；它们只能出现在「原始标识」提示或溯源展开区。
- 证据 ID 堆砌（`E-001、E-006`）出现在决策叙事里；引用研究用「作者-年份 + 人话描述」。
- 图表标题写公式（如 `position = (positive − negative) ÷ count`）；用自然语言说明图形含义。
- 半句截断、`null` 残留、中英夹生。
- 用兜底句掩盖缺失：字段没产出就如实说没产出。

## 6. 门禁如何执行

- `check_language_parallel()`：叙述字段必须为对应语言、双语不得完全相同、不得含内部键名。
- 原始标识检查：`research_frame` 与决策字段中的多词串若含未注册的 `snake_case`，记为缺陷。
- 字数检查：四件套超过上限即失败。
- 一致性检查：`result.json` 与 `result.zh.json` 的证据在 id/来源/研究/样本/方向/关系六个结构字段上必须逐条相等（自由文本可不同）。

相关：`visualization/eduevidence-report/references/bilingual-style.md`（双语渲染约定）、`references/scientific-invariants.md`（科学不变量）。
