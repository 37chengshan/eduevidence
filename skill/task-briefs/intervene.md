# Task Brief — stage: intervene（角色：intervention-designer）

## 目标
把 Verdict 转化为最小可验证试点（阶段化使用规则、护栏、停止条件、证据对齐）；禁止直接推荐全面部署。
干预对象随领域而定：教学干预、政策工具、组织流程或产品策略都属于同一协议。

## 前置输入
- `final_verdict.json` + `frame.json`（+ `applicability.json`）
- 存在经验缺口时：显式、有证据奠基的 KnowledgeGap ID

## 产出
- `intervention.json`（`schemas/intervention.schema.json`）：phases / ai_usage_policy /
  stop_conditions / evidence_alignment / owner / population，须通过 schema 校验。

## 执行规则
- **无证据奠基不得设计新研究**：设计必须引用显式 KnowledgeGap ID（冻结科学规则）。
- 每个阶段含：时长、参与人群、使用规则与护栏、责任人、停止条件、决策点。
- 停止条件必须包含风险/损害停止，不只是效果不达标停止。
- 叙述为人话；枚举/代号只作标签。
- 伦理与合规先过 `skill/sub-skills/ethics-review/SKILL.md`（涉及学生数据与对照分组时）。

## 质量门
- [ ] `intervention.json` 通过 intervention schema。
- [ ] 每个阶段都有停止条件与决策点，且可在数周内判定。
- [ ] 证据对齐字段把每条设计选择映射到具体证据或 KnowledgeGap。
- [ ] 全文未出现"推荐全面部署/正式采用"这类超范围表述。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| `INSUFFICIENT_EVIDENCE` | 停在评审：安全或损害证据缺失时不得启动试点。 |
| 无 KnowledgeGap | 不设计研究，改为报告"还需要什么证据"。 |
| 伦理审查未通过 | 阻断试点，先行修正设计。 |
| 人群越出适用边界 | 缩小试点人群至支持范围内。 |

## 语言与呈现契约
面向决策责任人的方案：谁、何时、做什么、什么条件下停。

## 交接说明
`intervention.json` 是 Evaluate 的输入；评价方案必须能判定该试点的成功、失败与停止。
