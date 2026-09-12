# Task Brief — stage: applicability（角色：evidence-judge）

## 目标
判定证据可迁移到目标人群与场景的程度：明确支持人群、实施条件、被排除人群、结局边界与不确定性。

## 前置输入
- `evidence.jsonl`（含人群、场景、剂量与结局信息）
- `final_verdict.json`（裁决与边界）
- `references/applicability-policy.md`

## 产出
- `applicability.json`：supported / unsupported populations、conditions、outcome limits、
  boundary of transfer、uncertainty statement；供 Intervene 判断试点人群是否落在支持范围内。

## 执行规则
- **阳性结果不自动迁移**：不能因为"研究有效"就推定目标人群同样有效。
- 逐条对齐：目标人群 vs 研究人群、目标场景 vs 研究场景、目标 outcome vs 已测量 outcome。
- 明确写出被排除人群（例如被排除的补习班学生、特殊需求学习者）与理由。
- 剂量与实施条件（师资培训、课时、工具版本、护栏）必须显式列出——这些常常是效果成立的前提。
- 不确定之处如实标注为不确定，不用"一般来说"这类泛化措辞掩盖缺口。

## 质量门
- [ ] 支持人群、条件、结局边界、排除人群四类信息齐全。
- [ ] 每条边界都追溯到具体证据，而非泛泛陈述。
- [ ] 不确定性显式声明，且与裁决置信度一致。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| `SCOPE_MISMATCH` | 缩小结论范围而非放宽适用条件。 |
| 关键人群信息缺失 | 记入不确定项；不得默认"与目标人群相同"。 |
| 边界与裁决口径冲突 | 以证据为准修正边界，并回退到 Adjudicate 复核。 |

## 语言与呈现契约
面向决策者的人话表述：谁适用、在什么条件下、对哪些结果、到什么程度为止。

## 交接说明
`applicability.json` 约束 Intervene 的试点人群；越界设计必须被拒绝或缩回支持范围。
