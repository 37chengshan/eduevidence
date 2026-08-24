# 迭代状态表（v5.2.0 执行完毕后更新于 2026-08-24）

> 唯一状态源。每完成一项更新此表并在 CHANGELOG 记一行。计划详情见 `v5.2-v6.0-iteration-plan.md`。
> 状态取值：待办 / 进行中 / 已完成 / 已延后（注明去向）/ 外部依赖（软件侧就绪，等待现实世界输入）。

## 版本治理先行

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| V0 | versions.py 单一权威 + CI 一致性校验 | ✅ 已完成 | 5.2.0；`check_version_consistency.py` 进 CI |

## v5.2.0 「可信度修复」

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| R1 | 全量 DOI 审计 | ✅ 已完成 | 88 唯一 DOI：16 ok / 35 mismatch / 37 not_found；报告 `benchmarks/doi-audit/report.(json\|md)` |
| R2 | 旗舰示例真实文献重建 | ✅ 已完成 | `ai-coding-assistant-evidence`：8 来源全核验、12 证据、引擎置信度 Moderate/0.586、五主题 ALL CLEAN |
| R3 | ESL/数学示例如实标注 | ✅ 已完成 | 删除伪造 `-50` 包；esl/math 改 platform_native+data_origin=synthetic+首次过 schema |
| R4 | data_origin 字段 + HTML 徽章 | ✅ 已完成 | 四值枚举进 schema/meta；报告头徽章（synthetic 高亮警示） |
| R5 | 指标口径 SSOT | ✅ 已完成 | `generate_metrics.py --check` 进 CI；README 语言命名归位 zh-CN；landing 清泄漏词+虚构统计 |
| R6 | 复现性声明收敛 | ✅ 已完成 | 两层边界（确定性层/LLM 层）写入 reproducibility.md |
| R7 | 收尾与重打包 | ✅ 已完成 | 移动端批次/gitignore/删除伪造包；`make_upload.sh` 重建上传包并本地复核：零泄漏（canary 0 命中）、本地专属文件排除、SKILL.md parity OK、新旗舰包纳入且伪造 `-50` 包不存在、徽章随包分发（21MB / 327 文件） |

## v5.3.0 「开源地基」

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| E1 | src-layout 完整迁移 | 🔶 按计划条款延后 | 以 **wheel 隔离安装冒烟进 CI** 守护导入契约；build_result bootstrap 已修；完整迁移见下方"延后理由" |
| E2 | build_report.py 样式外置 | ✅ 已完成 | 基座 CSS → `assets/base.css`（渲染器 −337 行）；lint 同步扫描双源；规则集零差异验证 |
| E3 | web 副本整合 | ✅ 核心完成 | archive_v1/v3 删除（零引用）；web/README 声明单一源；showcase_v2 js 深度去重列为跟进项 |
| E4 | logging 贯穿 | ✅ 已完成 | engine/log.py + fetch/search/orchestrator 关键路径；EDUEVIDENCE_LOG_LEVEL 开关 |
| E5 | CI 强化 | ✅ 已完成 | 红队套件收编(6/6 绿)+ruff(E9/F)+pytest-cov 报告+移除静默重试+metrics/version 门 |
| E6 | citation_check 产品化 | ✅ 已完成 | engine/citation_check.py + CLI(--write-back) + schema 字段 + HTML 徽章；离线单测 ×10 |
| E7 | install.sh 加固 | ✅ 已完成 | 脚本头供应链提示+副作用披露；README×2/install-guide 同步 |

## v6.0.0 「真闭环与分发」

| ID | 项目 | 状态 | 备注 |
|----|------|:---:|------|
| F1 | quickstart 引导器 | ✅ 就绪 | `scripts/quickstart.py`：run 创建+NEXT_STEPS 清单（外部 LLM 阶段仍需用户 agent 执行——这是产品形态本身） |
| F2 | living-evidence 真实试点 | ⏸ 外部依赖 | 软件侧就绪（engine/pilot.py + did_regression + NEXT_STEPS 流程）；**等待真实匿名课堂数据**——不可虚构 |
| F3 | 金标 30 题全量运行 | ⏸ 外部依赖 | 基线与金标齐备（benchmarks/）；**需要真实 LLM API key 与预算**执行 benchmark_v3 |
| F4 | 撤稿监控 | ✅ 已完成 | `scripts/retraction_watch.py`：state 快照+diff 报告；首跑 0 撤稿/0 异常 |
| F5 | marketplace/MCP 打包 + SCP 重上架 | ⏸ 外部依赖 | SKILL.md 结构已符合 skills 规范；SCP 链接核实与重新上架需用户账号操作 |
| F6 | Deep Research 对比页 | ✅ 已完成 | `web/comparison.html`（引用逐条可验证 demo + 伪造 DOI 对照），挂入 landing 导航 |

## 持续机制

| 项目 | 状态 | 备注 |
|------|:---:|------|
| CONTRIBUTING.md | 待办 | 下迭代 |
| 检索合规政策页 | 待办 | robots/限速/paywall |
| CONTRIBUTING 之外的口径自检 | ✅ | metrics/version 双门在 CI |

## 延后与残留（诚实清单）

1. **E1 完整 src-layout**：计划原文允许"若社区安装反馈少可延后"。当前以 wheel 冒烟守护导入契约；迁移涉及 ~40 文件路径假设，宜独立迭代执行。
2. **esl/math 包内演示性"引文"仍在**（SYNTHETIC 徽章下）：徽章+文档已声明不构成实证；若要彻底清除需重写两包内容（下一迭代候选）。
3. **F2/F3/F5**：分别等待真实课堂数据、LLM API 预算、SCP 账号操作（外部依赖，软件侧均已就绪）。
