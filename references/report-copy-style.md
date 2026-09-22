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

## 4. 按域选文案（Domain copy packs）

报告层**不得**再写死教育域用语。面向读者的研究文案、章节标题、模块标签与框架枚举一律从领域文案包读取：

```
domains/<domain_id>/copy/
  framing_lexicon.json   # frame 枚举 + 字段/子字段标签
  section_titles.json    # 01–12 章节标题与引导语、默认章节大纲、摘要块标题
  module_labels.json     # 域敏感 UI 模块标签（干预/评价/护栏/分组）
  terminology.json       # 方法学项标签 + 字段展示名
  risk_constructs.json   # 结果分组、结果分离标题/注、构念护栏
  few_shots.json         # 四态（adopt / pilot / reject / insufficient_evidence）各 1 例文案
```

中性 UI 词典在 `domains/_neutral/copy/`（`module_labels*.json` 按主题拆分；渲染器 chrome，无研究口吻）。大词典允许主题拆伴文件：`framing_enums.json`、`module_labels_*.json`，加载时并入上述六件套视图。加载与合并：`visualization/eduevidence-report/scripts/report_copy_pack.py`。

**域名解析**：`result.meta.domain` → `result.research_frame.extensions.domain`。缺省按 `education`（引擎惯例）并告警；未知域中性回退 + 告警（`strict=True` 则 fail-clear）。

**域差异（写作时对照）**：

| 概念 | education | policy |
|---|---|---|
| 干预 | AI 干预 / 教学干预 | **干预方案**（禁止「AI 干预」） |
| target_learners | 目标学习者 | **目标人群** |
| 结果分离 | 任务表现 ≠ 学习效果 | 过程产出 ≠ 政策效果 |
| 评价指标 | 过程 / **学习** / 风险 | 过程 / **效果** / 风险 |
| 构念护栏 | 任务 vs 学习护栏 | 产出 vs 效果护栏 |
| 章节 09 | 教学干预 | 干预方案 |

**policy 词典硬约束**：`python3 domains/check_copy_packs.py` 断言 policy 文案包不含教学词（教学/学习者/学习指标/AI 干预/…）；`report_copy_pack.assert_policy_copy_clean` 在加载时同样 fail-clear。`build_infographics` 遗留的教育 SVG 标题由 `retitle_infographics()` 按域改写，不改适配器本体。

**新增第三域（例如 workplace / health）**：

1. 在 `domains/manifest.json` 注册 `id` / frame_schema / outcome_taxonomy / methodology_checklist（沿用 v4 领域契约）。
2. 新建 `domains/<id>/copy/`，写入上述 6 个 JSON（`domain` 字段必须等于 `<id>`）。
3. 口吻：从 policy 包复制结构，换成该域构念词；禁止混入其他域硬词（用 `check_copy_packs.py` 的词表扩展后自检）。
4. `few_shots.json` 四态各写 1 例该域决策口吻（≤ 规范字数上限）。
5. 结果分组：在 `risk_constructs.json` 的 `outcome_groups` 把该域 outcome token 映射到 `task` / `learning` / `risk`（内部桶名不变，展示名由 `module_labels` 决定）。
6. 跑 `python3 domains/check_copy_packs.py` + 用该域 `result.json` 跑一次 `build_report.py`，确认 HTML 无外域硬词。

## 5. 术语对照

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

## 6. 禁止

- 内部字段名与存储标识（`effect_direction`、`first_programming_course_...`）出现在叙述句里；它们只能出现在「原始标识」提示或溯源展开区。
- 证据 ID 堆砌（`E-001、E-006`）出现在决策叙事里；引用研究用「作者-年份 + 人话描述」。
- 图表标题写公式（如 `position = (positive − negative) ÷ count`）；用自然语言说明图形含义。
- 半句截断、`null` 残留、中英夹生。
- 用兜底句掩盖缺失：字段没产出就如实说没产出。

## 7. 门禁如何执行

- `check_language_parallel()`：叙述字段必须为对应语言、双语不得完全相同、不得含内部键名。
- 原始标识检查：`research_frame` 与决策字段中的多词串若含未注册的 `snake_case`，记为缺陷。
- 字数检查：四件套超过上限即失败。
- 一致性检查：`result.json` 与 `result.zh.json` 的证据在 id/来源/研究/样本/方向/关系六个结构字段上必须逐条相等（自由文本可不同）。

相关：`visualization/eduevidence-report/references/bilingual-style.md`（双语渲染约定）、`references/scientific-invariants.md`（科学不变量）。
