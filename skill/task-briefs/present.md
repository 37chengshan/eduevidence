# Task Brief — stage: present（角色：report-generation）

## 目标
汇总 `result.json` → `result.zh.json`（语义对齐、非机翻、数字/ID/枚举/URL 不变），并经
`visualization/eduevidence-report/scripts/build_report.py` 烘焙双语报告
（主题生成时五选一，最终 HTML 只保留中英文切换）。

## 前置输入
- `result.json` + `result.zh.json`（叙述字段必须先过语言门禁 `check_language_parallel`）
- 五主题：claude / academic / datalab / datalab-dark / presentation

## 产出
- `EduEvidence_Report.html` / `reports-5themes/*.html` + `report_spec.json` + `artifact_manifest.json`

## 执行规则
- 语言门禁：叙述字段人话化（禁 E-xxx 堆砌 / schema 键 / null 残留 / 中英交叉污染）；
  表格/ID/URL/枚举保留可追溯性。
- 图表由 AI 写 `visual_layout` 计划、渲染器从 `result.json` 取数：**数值不得由模型写入**；
  未注册 type 显式报错，数据不足则该图抑制并记录原因。
- 主题在生成时锁定，HTML 内不提供运行时换肤。
- 报告与导出是投影：渲染失败不得改变任何科学结论。

## 质量门
- [ ] `check_language_parallel` 通过（中英语义对齐）。
- [ ] 渲染完整性门通过（`REPORT_INVALID` 探针无命中，显示值可回溯到 `result.json`）。
- [ ] 布局不变量通过 `scripts/lint_report_layout.py`（含 390/768/1280 × brief/full）。
- [ ] 溯源表格保留（来源表、证据矩阵、Claim Trace），图表只作补充。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| `REPORT_INVALID` | 阻断发布并重跑渲染；不得带缺陷投放。 |
| 双语不对齐 | 修复 `result.zh.json` 后重新烘焙。 |
| 数据不足以支撑某图 | 抑制该图并写明原因，不用占位或虚构数据补位。 |

## 语言与呈现契约
面向读者的人话报告；可核验行保持可点击、可回查。

## 交接说明
报告仅为投影产物；任何结论修订都回到科学阶段并生成新 revision。
