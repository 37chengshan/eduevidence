# Task Brief — stage: audit（角色：method-reviewer）

## 目标
按审计清单审查每个研究的方法学质量，强制执行"任务完成表现 ≠ 学习效果"最高优先级规则。

## 前置输入
- `evidence.jsonl` + 来源 fetch 内容
- 审计框架：`references/wwc_standards.md`、`references/grade_framework.md`、`references/methodology-audit.md`

## 产出
- `methodology.json`：15 项 `audit_items`（control_group / randomization / pre_test / post_test /
  retention_test / transfer_test / sample_bias / self_selection / measurement_validity / confounders /
  instructor_effect / novelty_effect / tool_version_effect / ai_usage_policy / dropout，每项 status:
  met|partial|missing|not_applicable）+ 每条 PASS/CONCERN/FAIL verdict + `task_vs_learning_guard`
  （显示层经 zh_labels 映射中文），须通过 `schemas/methodology.schema.json`。

## 执行规则
- 只审"证据站不站得住"，不审"证据说什么"——审计结论不得夹带对效果的判断。
- `task_vs_learning_guard.equates_task_with_learning` 必须显式给出；为 true 时该研究不得支撑任何学习效果声明。
- 审计说明（note/summary）为人话叙述，枚举/代号（PASS/CONCERN/FAIL）只作标签。
- 独立性：Method Reviewer 与内容判断角色分离（`independence_required: true`），且需强上下文能力。

## 质量门
- [ ] 15 项审计项齐全，无缺项、无自造项。
- [ ] 每项状态取自四值枚举，`not_applicable` 必须说明为何不适用。
- [ ] `task_vs_learning_guard` 存在且结论明确。
- [ ] 每条 PASS/CONCERN/FAIL 有可核验依据（对应原文特征）。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| 关键信息缺失（如未报告随机化） | 记 `missing` 并在说明中写清缺什么，不猜测。 |
| 结论依赖任务表现 | 触发 guard，剥夺其学习效果支撑资格。 |
| schema 校验失败 | 修复后重跑审计。 |

## 语言与呈现契约
审计叙述为人话；状态枚举只作标签显示。

## 交接说明
`methodology.json` 直接决定每条证据能否支持 claim；Adjudicate 必须读取 `task_vs_learning_guard` 与各条 verdict。
