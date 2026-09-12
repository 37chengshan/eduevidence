# Task Brief — stage: evaluate（角色：evaluation-designer）

## 目标
为 PILOT/ADOPT 配套评价方案：基线/后测/保持/迁移 + 过程/学习/风险指标 + 成功阈值与停止条件。

## 前置输入
- `intervention.json` + `final_verdict.json`
- 评价框架：`references/evaluation-design.md`、`references/evaluation-policy.md`、`references/outcome-taxonomy.md`

## 产出
- `evaluation.json`（`schemas/evaluation.schema.json`）：baseline / post / retention / transfer 测量点，
  过程与风险指标，成功与失败阈值，分析计划（可被 `scripts/did_regression.py` 直接执行）。

## 执行规则
- 分离 Task Performance 与 Learning Effect；两者指标不得合并成一个"效果"。
- 保持（retention）与迁移（transfer）必须单独设计测量点，不能只做即测。
- 阈值在数据到达前固定；事后改阈值属协议偏离，须记录而非吸收。
- 分析计划要具体到可执行（设计类型、比较组、协变量、缺失处理），使 DID/效应量脚本无需再做决定。
- 叙述为人话。

## 质量门
- [ ] `evaluation.json` 通过 evaluation schema。
- [ ] 基线、即测、保持、迁移四类测量点齐全。
- [ ] 成功、失败、停止阈值三者都在，且先于数据固定。
- [ ] 分析计划可被确定性脚本执行（无残留人工决策）。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| 无法做对照 | 改为单组前后测并显式标注设计局限，不得仍按因果口径表述。 |
| 阈值事后调整 | 记录为协议偏离并降级结论强度。 |
| 样本量不足 | 报告功效局限；不得以不显著当作"无效果"。 |

## 语言与呈现契约
人话评价方案；统计符号与阈值数字保留原样以便复算。

## 交接说明
试用数据回收后由 `evaluate-and-update` 工作流重新注入证据图谱并再裁决。
