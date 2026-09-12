# Task Brief — stage: projection（投影层，非科学阶段）

## 目标
仅从已完成的科学产物与 decision snapshot 生成报告与导出；投影错误不得改变任何科学结论。
记录确切的来源 revision 与渲染产物哈希。

## 前置输入
- 已通过各自 schema 与闸门的科学产物（frame / evidence / skeptic / methodology / verdict / 等）
- 当前 Graph Revision 与 decision snapshot 标识

## 产出
- `result.json` / `result.zh.json`、`report_spec.json`、`report.html`、`reports-5themes/*.html`、
  `artifact_manifest.json`（含来源 revision 与产物哈希）、各类导出（证据包 / 判题包）。

## 执行规则
- 投影只读：**不得回写或修改任何科学产物**，不得据显示需要调整结论。
- 投影产物一律标注来源 revision 与渲染哈希，使报告可被追溯回具体快照。
- 呈现层与事实层分离：`result.json` / HTML / Markdown 都不是事实库。
- 渲染失败只影响该产物本身：阻断发布、重跑渲染，不降级、不改写结论。

## 质量门
- [ ] `artifact_manifest.json` 记录来源 revision 与各产物哈希。
- [ ] 投影内容与快照一一对应，无"报告比证据更新"的情况。
- [ ] 渲染完整性门与布局不变量通过。

## 失败模式与回退
| 失败 | 处理 |
|---|---|
| 渲染失败 | 阻断发布，重跑渲染（`REPORT_INVALID` → `block_publish_rerun_render`）。 |
| 快照缺失 | 回到上游科学阶段补齐；禁止用默认值或占位内容生成报告。 |
| 报告与快照不一致 | 以快照为准重建投影。 |

## 语言与呈现契约
面向读者的人话呈现；可追溯行（ID / URL / 数值）保持可核验。

## 交接说明
投影产物可自由删除重建；重建不应改变任何科学结论或修订历史。
