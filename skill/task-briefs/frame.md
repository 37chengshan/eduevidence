# Task Brief — stage: frame（角色：education-planner）

## 目标
把原始教育问题结构化为主 Question / Learner / Intervention / Comparison / Outcome / Context 的完整
Education Research Frame；框架完整前禁止生成任何教学建议。

## 输入
- 用户原始问题（run manifest → question）

## 产出（写入本 run workspace）
- frame.json，须通过 schemas/education-frame.schema.json 校验
- 字段：question / decision_target / learner / course / intervention / comparison /
  outcomes（primary/secondary）/ context / scope / inclusion_criteria / exclusion_criteria / success_condition

## 规则
- 语言：面向"阅读证据档案的人"（研究者/决策者），中文叙述通顺，禁内部字段名碎语。
- 复杂度门：随 frame 输出建议 S/M/L（由 scripts/complexity_gate.py 复核）。