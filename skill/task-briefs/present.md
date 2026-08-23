# Task Brief — stage: present（角色：report-generation）

## 目标
汇总 result.json → result.zh.json（语义对齐、非机翻、数字/ID/枚举/URL 不变），并经
visualization/eduevidence-report/scripts/build_report.py 烘焙双语报告
（主题生成时五选一，最终 HTML 只保留中英文切换）。

## 输入
- result.json + result.zh.json（叙述字段必须先过语言门禁 check_language_parallel）

## 产出
- EduEvidence_Report.html / reports-5themes/*.html + report_spec.json + artifact_manifest.json

## 规则
- 语言门禁：叙述字段人话化（禁 E-xxx 堆砌/schema 键/null 残留/中英交叉污染）；
  表格/ID/URL/枚举保留可追溯性。