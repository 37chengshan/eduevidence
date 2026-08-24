# 迭代状态表

> 唯一状态源。每完成一项更新此表并在 CHANGELOG 记一行。计划详情见 `v5.2-v6.0-iteration-plan.md`。
> 状态取值：待办 / 进行中 / 已完成 / 已延后（注明去向）。

## 版本治理先行

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| V0 | versions.py 单一权威 + CI 一致性校验 | 待办 | 最先做，0.5 人日 |

## v5.2.0 「可信度修复」

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| R1 | 全量 DOI 审计（audit_dois.py） | 待办 | 抽查 5/48+，须全量见底 |
| R2 | 旗舰示例真实重建 ai-coding-assistant-evidence | 待办 | 无 LLM 预算则走 manual_curated fallback |
| R3 | ESL/数学示例重建或如实标注 | 待办 | 删除伪造 mode=agent_mcp_enhanced |
| R4 | data_origin 字段 + HTML 徽章 | 待办 | |
| R5 | 指标口径 SSOT + CI 校验 + 卖点文案改写 | 待办 | 含 README.en.md 语言反转修复 |
| R6 | 复现性声明收敛 | 待办 | |
| R7 | 未提交批次收尾 + gitignore + 重打包 | 待办 | 移动端修复批次先行提交 |

## v5.3.0 「开源地基」

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| E1 | src-layout 迁移 | 待办 | 可延后 |
| E2 | build_report.py 拆分 | 待办 | 可拆 5.3.x |
| E3 | web 前端四副本合一 | 待办 | 可拆 5.3.x |
| E4 | logging 贯穿 engine/retrieval | 待办 | |
| E5 | ruff + coverage + flaky quarantine | 待办 | 含收编 test_adversarial_empirical.py |
| E6 | citation_check 产品化 + doi_verified/retracted 字段 | 待办 | 护城河功能 |
| E7 | install.sh pin/checksum + env 披露 | 待办 | |

## v6.0.0 「真闭环与分发」

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| F1 | eduevidence research 上手路径 | 待办 | 2/9→9/9 阶段 |
| F2 | living-evidence 真实试点闭环 | 待办 | |
| F3 | 金标 30 题全量 + B4 | 待办 | |
| F4 | 撤稿监控定期任务 | 待办 | |
| F5 | skills marketplace 打包 + MCP Registry + SCP 重上架 | 待办 | 先核实 #650 链接 |
| F6 | Deep Research vs EduEvidence 对比 demo | 待办 | 实测为准 |

## 持续机制

| 项目 | 状态 | 备注 |
|------|:---:|------|
| CONTRIBUTING.md | 待办 | |
| 检索合规政策页 | 待办 | robots/限速/paywall |
