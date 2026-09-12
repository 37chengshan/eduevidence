# Task Brief — stage: adjudicate（角色：evidence-judge）

## 目标
整合 Frame + Evidence Matrix + Skeptic Findings + Method Reviews，产出四态裁决
（ADOPT/PILOT/REJECT/INSUFFICIENT EVIDENCE）+ Can/Cannot Claim + 证据边界。

## 前置输入
- `frame.json`、`evidence.jsonl`、`skeptic.json`、`methodology.json`
- 确定性置信度脚本 `scripts/compute_confidence.py` 与裁决前闸门 `scripts/pre_verdict_gate.py`

## 产出
- `raw_verdict.json`（模型裁决）→ orchestrator 跑 Pre-Verdict Gate + 确定性置信度
  → `final_verdict.json`（`schemas/verdict.schema.json`）。

## 执行规则（人话化硬标准，第一页决策语言）
- `decision_rationale` 必须为 ≤4 句面向读者的流畅散文（en/zh 分写）；
- 禁证据 ID 列表（E-xxx/EV-xxx）、禁 schema 键（overall_risk= 等）、禁截断残留（null）；
- what_can/cannot_be_claimed 等列表同样人话化；统计数字可保留但以自然表达呈现。
- **先过 Pre-Verdict Gate 再定稿**：critical 失败会封顶置信度并禁止高置信 ADOPT。
- 置信度由规则化公式给出（0.30 质量 + 0.25 一致性 + 0.20 直接性 + 0.25 独立研究数 − 双罚分），不由模型自评。
- 证据不足时输出 INSUFFICIENT EVIDENCE，并写明"什么证据会改变这个决定"。
- 语言人话化规则见 `references/scientific-invariants.md` 与角色提示词。

## 质量门
- [ ] `final_verdict.json` 通过 verdict schema，action 取自四态枚举。
- [ ] Pre-Verdict Gate 已执行并留痕（`gate_report.json`）。
- [ ] 置信度可复算，分解项可审计。
- [ ] 反证与 threats_to_validity 均被显式回应（采纳、限定或驳回并说明理由）。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| `PRE_VERDICT_FAILED` | 修复前置产物（schema / 交叉评审 / 方法学）后重跑闸门。 |
| `GATE_CRITICAL_FAILURE` | 封顶置信度，强制降至 PILOT 或 INSUFFICIENT EVIDENCE。 |
| `CONFLICT_UNRESOLVED` | 保持不确定，不强行裁决。 |
| 证据仅支持任务表现 | 不得据以产出学习效果类结论。 |

## 语言与呈现契约
面向决策者的第一页语言；ID、枚举、URL 保留可追溯性，但不出现在叙述句中。

## 交接说明
`final_verdict.json` 是 Applicability / Intervene / Evaluate 与一切投影的唯一依据。
