# Task Brief — stage: audit（角色：method-reviewer）

## 目标
按审计清单审查每个研究的方法学质量，强制执行"任务完成表现 ≠ 学习效果"最高优先级规则。

## 输入
- evidence.jsonl + 来源 fetch 内容

## 产出
- methodology.json：audit_items（含 task_vs_learning_guard）+ 每条 PASS/CONCERN/FAIL verdict
  （显示层经 zh_labels 映射中文）。

## 规则
- 只审"证据站不站得住"，不审"证据说什么"；审计说明（note/summary）为人话叙述，
  枚举/代号（PASS/CONCERN/FAIL）只作标签。