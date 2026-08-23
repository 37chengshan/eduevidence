# Task Brief — stage: challenge（角色：skeptic）

## 目标
主动寻找、验证并记录 null/negative/contradictory evidence、AI dependency、reduced transfer、
novelty effect、alternative explanation；禁止虚构反方证据；没有反方证据时输出
NO CONTRADICTORY EVIDENCE FOUND。

## 输入
- evidence.jsonl

## 产出
- skeptic.json：search_performed=true；findings（counter_evidence/null_results/confounders）。

## 规则（人话化硬标准）
- 叙述字段为面向研究者的流畅中文；禁证据 ID 堆砌（用"作者-年份 + 人话描述"替代）。