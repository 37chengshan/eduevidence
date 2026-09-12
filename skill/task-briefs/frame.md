# Task Brief — stage: frame（角色：research-planner）

## 目标
把原始决策问题结构化为主 Question / Population / Intervention / Comparison / Outcome / Context 的完整
Research Frame；框架完整前禁止生成任何干预建议。领域决定字段词汇：education 用 learner/course，
policy 用 decision_object/population/stakeholders，其他领域见 `domains/<id>/` 自带的 frame 契约。

## 前置输入
- 用户原始问题（`run manifest → question`）
- 已知的结构化线索：population / intervention / comparison / outcomes / constraints / depth / target
- 目标领域（`eduevidence domain list`）
- 复杂度等级建议（S/M/L，由 `scripts/complexity_gate.py` 复核）

## 产出（写入本 run workspace）
- `frame.json`，须通过所选领域的 frame schema 校验（`domains/<id>/manifest.json` → `frame_schema`；education 为
  `schemas/education-frame.schema.json`，policy 为 `domains/policy/frame.schema.json`）
- 字段：question / decision_target（或 decision_object）/ population 语境 / intervention / comparison /
  outcomes（primary/secondary/risk）/ context / scope / inclusion_criteria / exclusion_criteria / success_condition

## 执行规则
- **Framing 完成前不得输出任何干预建议**——这是第一道科学闸门。
- 缺失的目标人群、干预变体、对照条件、主 outcome 只能向用户询问（`NEEDS_USER_CONTEXT`），禁止编造默认值。
- 决策枚举必须取自所选领域的 schema：education 用 `decision_target`（evidence_review / teaching_decision /
  pilot_design / evaluation_design），policy 用 `decision_object`（adopt / modify / terminate / maintain /
  evaluate_impact）；不得跨领域混用。
- Scope（时间范围、地域、研究类型）与纳排标准必须可判定，不能写成"相关研究"这类不可操作表述。
- 语言：面向"阅读证据档案的人"（研究者/决策者），中文叙述通顺，禁内部字段名碎语。

## 质量门
- [ ] `frame.json` 通过所选领域的 frame schema。
- [ ] PICO 五要素齐全，`comparison` 明确（含 "business as usual" 这类显式对照）。
- [ ] primary outcome 与 secondary/risk outcome 分离，且未把任务表现写成学习效果。
- [ ] `success_condition` 可被后续 Evaluate 阶段度量。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| 缺少关键输入 | `NEEDS_USER_CONTEXT`：向用户提问，不猜测、不继续。 |
| 问题跨多个决策 | 拆分为多个 frame，各自独立成 run；不要在一个 frame 里塞两个决策。 |
| schema 校验失败 | 修复后重跑该阶段，不得带缺陷推进。 |

## 语言与呈现契约
叙述字段为流畅人话；枚举、代号、schema 键只作标签，不进正文。

## 交接说明
`frame.json` 是 Retrieve 的唯一检索边界来源；下游角色只读该文件，不读原始对话。
