# Evidence Tribunal（证据裁判庭）

## 1. 职责

Evidence Tribunal 是所有证据流（正面证据、反方证据、方法学审查）的**汇总结点**：
接收各分析产物，裁定哪些结论可以成立、哪些不能，并解释冲突来源。

## 2. 输入（四个必填产物）

| 输入 | 来源 | 说明 |
| --- | --- | --- |
| Education Research Frame | education-framing.md | 未完成的 Frame 直接驳回，不得进入裁判 |
| Evidence Matrix | 证据整理结果 | 每条证据含五维质量分（evidence-quality.md）与绑定 Outcome（outcome-taxonomy.md） |
| Skeptic Findings | skeptic-protocol.md | 9 项任务报告，缺项或虚构即驳回 |
| Method Reviews | methodology-audit.md | 逐项审查报告，含 HIGH-PRIORITY 标记 |

裁判庭确认四份输入**齐全且合规**后才可开庭。

## 3. 输出：EducationVerdict

### 3.1 Verdict 结构

```yaml
EducationVerdict:
  candidate_claim: <待裁判的结论陈述，逐条裁判>
  decision:
    can_claim: <可成立的结论列表>
    cannot_claim: <不可成立的结论列表 + 原因>
    claim_boundary: <每条可成立结论的有效范围限定>
  conflict_analysis:
    - source: <冲突来源>
      detail: <冲突内容>
      resolution: <如何处理>
  overall_confidence: high | moderate | low
```

### 3.2 裁判原则

- 裁判只看输入中的证据，禁止引入输入之外的新证据。
- 结论必须绑定 Outcome（C1–C4）与适用范围（Frame 的组合）。
- `cannot_claim` 必须给出原因，原因只能是：无证据 / 证据弱（<5 分）/ 测量错配 / 反方证据更优 / 超出 Frame 范围。

## 4. 冲突来源分析（五种）

当证据间结论冲突时，从以下五类定位冲突根源，逐项排查：

| 来源 | 排查问题 | 冲突示例 |
| --- | --- | --- |
| 样本（sample） | 学习者层次、专业、先验是否不同？ | 研究生研究说"无差异"，本科生研究说"有显著提升"→ 冲突来自样本 |
| 测量（measurement） | Outcome 指标是否不同？是否把 C2 当 C1？ | 一个用"完成时间"(C2)，一个用"保持测试"(C1) → 冲突来自测量 |
| 课程（course） | 学科、课程类型、时长是否不同？ | 编程课有效、写作课无效 → 冲突来自课程 |
| 工具（tool） | 工具类型/版本/使用方式是否不同？ | 代码补全 vs 完整生成 → 冲突来自工具能力差异 |
| 实验设计（design） | 对照、随机、前测、保持测量是否不同？ | 弱设计研究显著、强设计研究不显著 → 冲突来自设计质量 |

排查输出固定为：

```
conflict_pair: <证据 A> vs <证据 B>
source        : sample | measurement | course | tool | design（可多选）
detail        : <具体差异一句话>
resolution    : <冲突不成立 / 弱证据让位 / 按 subgroup 拆分结论>
```

## 5. Can Claim / Cannot Claim 边界

### Can Claim（可成立）所需条件

1. 至少 1 条 `strong`（或 2 条 `moderate`）且方向一致的证据；
2. 证据绑定的 Outcome 与结论声称的 Outcome 一致（无测量错配）；
3. Skeptic 无反方证据，或反方证据已被正面证据明确压过；
4. 结论范围严格落在 Frame 之内。

### Cannot Claim（不可成立）情形

| 情形 | 示例 |
| --- | --- |
| 证据只覆盖 C2 | 只测了作业正确率 → 不可声称"学习效果改善" |
| 无保持/迁移测量 | 只有即时后测 → 不可声称"长期有效" |
| 样本外推 | 研究生样本 → 不可声称"对大一新生有效" |
| 工具错配 | 完整代码生成工具的结论 → 不可声称适用于"仅解释报错"场景 |
| 弱证据占优 | 证据总分 < 5 → 只能"待验证"，不可成立 |
| 反方证据更强 | 反方 `moderate/strong` 且正面只有 `weak` → 结论按反方方向限缩 |

## 6. 裁判示例

```
candidate_claim: "允许 Copilot 会提高大一 C 语言学生的编程学习效果。"

Evidence Matrix:
  E1 (RCT, 大一 C 语言, Copilot 补全, 8 周, 保持+迁移测试, 总分 9 strong)
     结果: 无 AI 迁移测试无显著差异 → Outcome C1/transfer, 方向=持平
  E2 (准实验, 同一批学生, 作业正确率提升) → Outcome C2/accuracy, 方向=上升
  E3 (研究生样本研究, 无保持测量, 总分 4 weak) → 迁移测试显著下降

Skeptic: S-05 找到测量错配 (E2 的 C2 当 C1)；S-08 找到依赖风险证据。
Method Reviews: E2 触发 HIGH-PRIORITY-VIOLATION（C2 当 C1）。

Verdict:
  can_claim:
    - "Copilot 可提高 AI 环境下的作业完成正确率（C2）"（由 E2）
    - "无证据表明其提高无 AI 环境的独立编程能力（C1/transfer 持平）"（由 E1）
  cannot_claim:
    - "Copilot 提高大一 C 语言学生学习效果" — 原因: E1 迁移测试持平 + E2 测量错配
    - "允许使用无风险" — 原因: Skeptic S-08 报告依赖风险证据
  claim_boundary:
    - 以上结论仅适用于: 大一 C 语言、代码补全型工具、8 周试点、线下实验课、
      有助教情境；不适用于完整代码生成、无教师支持的 MOOC。
  conflict_analysis:
    - source: measurement — E2(C2) 与 E1(C1) 结论冲突实为测量类别不同，非真冲突
    - source: sample — E3 研究生样本与目标大一样本冲突，按 applicability 排除
  overall_confidence: moderate
```
