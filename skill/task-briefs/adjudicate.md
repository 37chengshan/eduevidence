# Task Brief — stage: adjudicate（角色：evidence-judge）

## 目标
整合 Frame + Evidence Matrix + Skeptic Findings + Method Reviews，产出四态裁决
（ADOPT/PILOT/REJECT/INSUFFICIENT EVIDENCE）+ Can/Cannot Claim + 证据边界。

## 输入
- frame.json、evidence.jsonl、skeptic.json、methodology.json

## 产出
- raw_verdict.json（模型裁决）→ orchestrator 跑 Pre-Verdict Gate + 确定性置信度
  → final_verdict.json（schemas/verdict.schema.json）。

## 规则（人话化硬标准，第一页决策语言）
- decision_rationale 必须为 ≤4 句面向读者的流畅散文（en/zh 分写）；
- 禁证据 ID 列表（E-xxx/EV-xxx）、禁 schema 键（overall_risk= 等）、禁截断残留（null）；
- what_can/cannot_be_claimed 等列表同样人话化；统计数字可保留但以自然表达呈现。