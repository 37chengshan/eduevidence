# Task Brief — stage: extract（角色：evidence-analyst）

## 目标
从校验通过的来源中抽取 Claim 级证据对象，执行 Outcome Separation；只结构化，不裁决。

## 输入
- sources.jsonl + fetch/ 全文内容

## 产出
- evidence.jsonl：每行一个 Evidence Object（evidence_id/source_id/claim/outcome_type/
  effect_direction/relation_to_claim/source_location/quality_score），须通过
  schemas/evidence.schema.json 校验。

## 规则
- 任务表现 ≠ 学习效果：outcome 分类不得混用。
- claim 文本用可读人话，禁止把内部字段名写进叙述。