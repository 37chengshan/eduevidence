# Task Brief — stage: challenge（角色：skeptic）

## 目标
主动寻找、验证并记录 null/negative/contradictory evidence、AI dependency、reduced transfer、
novelty effect、alternative explanation；禁止虚构反方证据；没有反方证据时输出
NO CONTRADICTORY EVIDENCE FOUND。

## 前置输入
- `evidence.jsonl`
- `frame.json`（用于判断结论是否超出研究范围）

## 产出
- `skeptic.json`：`search_performed=true`；`skeptic_findings[]`（九项检查，字段名稳定：
  `check` / `status`（found|not_found）/ `detail` / `related_evidence_ids`）；
  `contradictory_evidence_found`；`no_contradictory_evidence_statement`；`threats_to_validity`。
- 作为独立交叉审核角色时的输出须符合 `schemas/cross-model-review.schema.json`
  （必需字段 `agreement`、`final_recommendation`）。

## 执行规则（固定 9 项检查，缺一不可）
1. null result　2. negative result　3. contradictory evidence　4. alternative explanation
5. measurement mismatch（测的是任务完成还是学习）　6. sampling bias
7. novelty effect　8. AI dependency / over-reliance　9. scope overreach

- 反方检索必须独立构造查询，不复用支持证据的检索式。
- 找不到反证就是 "not_found"，并输出标准语句；**不得为了凑数虚构反方文献**。
- 独立性：Skeptic 不得与主分析使用同一模型家族（`independence_required: true`）。

## 质量门
- [ ] 九项检查全部有 `status`，无遗漏项。
- [ ] 每条 `found` 的 finding 都绑定 `related_evidence_ids` 或明确来源。
- [ ] `no_contradictory_evidence_statement` 与 `contradictory_evidence_found` 语义一致。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| 反证检索为空 | 记录 negative-search record；输出标准语句，不填充虚构来源。 |
| 反证与支持证据冲突 | 保留双方，交 Adjudicate 处理；不在此阶段裁决。 |
| 交叉审核不可用（无独立模型） | 降级为原生自审并显式标注，不得伪装为独立审核。 |

## 语言与呈现契约（人话化硬标准）
叙述字段为面向研究者的流畅中文；禁证据 ID 堆砌（用"作者-年份 + 人话描述"替代）。

## 交接说明
`skeptic.json` 是 Adjudicate 的必读输入；其 `threats_to_validity` 必须被裁决明确回应或采纳。
