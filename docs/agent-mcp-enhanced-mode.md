# Agent MCP Enhanced Mode — 安装与启用指南

> **直接安装，不迁移能力。** EduEvidence 只做「检测 → 调用 → 降级」，绝不复制 agent-mcp 的 queue / resume / steer / memory / verify / multi-CLI / daemon 实现（总体实施计划 §22–26）。

## 1. 这是什么

Agent MCP 是 EduEvidence 的**可选执行增强层**（Mode B）。它提供：

- 多 CLI / 多模型派发（fast collects → strong reasons → independent verifies）
- 独立模型交叉审核（Cross-Model Review）
- 跨会话 Memory Bank（memory_store / memory_recall）
- 超时 / 恢复 / 成本控制

**核心原则**：Agent MCP 是性能与可靠性增强层，**不是 EduEvidence 成立的前提**。未安装时全部退化为 Platform Native Mode（单 Agent 串行执行 8 角色协议），行为不中断。

## 2. 安装（方式任选其一）

### 方式一：curl 一键安装（macOS / Linux）

```bash
curl -fsSL https://raw.githubusercontent.com/37chengshan/agent-mcp/main/install.sh | bash
```

> ⚠️ 管道执行会以当前用户权限直接运行远程脚本——请先审阅脚本内容再执行；更稳妥见方式二。

### 方式二：git clone + 安装脚本（推荐审阅）

```bash
git clone git@github.com:37chengshan/agent-mcp.git
cd agent-mcp

python3 install.py --install --host all   # 或 --host <单个 host>
python3 start_agent_mcp.py --open          # 幂等启动 daemon，--open 打开监控页
```

支持 host：codex / claude / omp / opencode / kimi / zcode；其它 CLI 用 `custom-clis/*.json` 配置接入（零改码）。

### 方式三：把提示词交给任意 AI

如果你的 agent 不在内置 host 列表，把安装说明（`docs/install-guide.md` 第 3 节通用模板）连同提示词发给任意支持 MCP 的 AI 工具，让它自行注册。

## 3. 检测是否可用

运行：

```bash
python3 integrations/agent_mcp.py
```

输出形如：

```json
{
  "available": true,
  "mode": "agent_mcp_enhanced",
  "port": 8765,
  "enhanced_features": {"multi_cli_dispatch": true, "cross_model_review": true, "memory_bank": true}
}
```

- `available: true` → 启用高级功能
- `available: false` → 输出 `platform_native` 模式，一切照常运行

环境变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_MCP_INSTALLED` | 未设置 | `1/true/yes` 表示已安装 |
| `AGENT_MCP_PORT` | `8765` | daemon 端口 |
| `AGENT_MCP_HOME` | `~/.codex`（或 `CODEX_HOME`） | 状态目录 |

## 4. 高级策略：Fast / Strong / Independent

> **Fast models collect. Strong models reason. Independent models verify.**

| 角色 | 类别 | 默认 CLI/模型 |
|---|---|---|
| evidence-retriever | fast（资料搜索/整理/去重/初筛） | omp / fast-low-cost |
| education-planner | strong（Framing） | claude / reasoning |
| evidence-analyst | strong（结构化抽取） | claude / structured |
| method-reviewer | strong（方法学） | claude / reasoning |
| evidence-judge | strong（Tribunal） | claude / reasoning |
| intervention-designer / evaluation-designer | strong | claude / reasoning |
| skeptic | independent（反证） | claude / reasoning |

具体模型与 CLI 不写死在 Skill 中——由主 Agent 现场决策（`integrations/agent_mcp.py` 的 `ROLE_ROUTING` 只提供默认值）。

## 5. Cross-Model Review（独立模型交叉审核）

流程（总体实施计划 §25）：

```text
Primary Analysis → Draft Verdict → Independent Review → Judge → Final Verdict
```

调用：

```python
from integrations.agent_mcp import cross_model_review

plan = cross_model_review(draft_verdict, independent_model="independent-reasoning")
if plan["status"] == "READY":
    # 用 plan["spawn_call"] 通过 MCP 派发独立审核者
    pass
else:
    # plan["status"] == "AGENT_MCP_UNAVAILABLE" → 单 Agent 自审降级
    print(plan["note"])
```

审核输出必须符合 `schemas/cross-model-review.schema.json`：

```yaml
CrossModelReview:
  agreement:            # 与草稿裁决的一致程度
  disagreements:        # 分歧点
  unsupported_claims:   # 无支撑的结论
  missed_counterevidence:  # 漏掉的反方证据
  scope_violations:     # 越界结论
  methodology_issues:   # 方法学问题
  confidence_adjustment:  # upgrade | downgrade | no_change
  required_revision:    # 是否需要返工
  final_recommendation: # 最终建议
```

## 6. 推荐拓扑（L 级任务）

```text
Planner
  ↓
2–4 Fast Research Workers（并行检索）
  ↓
Evidence Merge
  ↓
Reasoning Analyst
  ↓
Skeptic + Method Reviewer
  ↓
Draft Verdict
  ↓
Independent Model Reviewer（Cross-Model Review）
  ↓
Final Judge
```

## 7. Memory Bank

用于持续教学研究项目（v2 实施方案 §26）。字段：

```text
Course Profile · Learner Profile · Research Questions
Reviewed Sources · Accepted Evidence · Rejected Evidence
Previous Verdict · Pilot Design · Pilot Results · Open Questions
```

形成闭环：`Evidence Review → Pilot → Real Outcome Data → Updated Verdict`。

调用：

```python
from integrations.agent_mcp import build_memory_store_call, build_memory_recall_call

build_memory_store_call("...", kind="research", key="pilot_results", tags=["ai-coding-assistant"])
build_memory_recall_call("previous verdict on AI coding assistant", kind="research", limit=5)
```

## 8. 失败处理

| 症状 | 动作 |
|---|---|
| 未安装 / daemon 不可达 | `AGENT_MCP_UNAVAILABLE`，退化为 Platform Native Mode，照常出结果 |
| 派发超时 | 任务级 `timeout_seconds` 自动终止；等待超时看 wait 存活证据再决策 |
| 独立审核者结果与主分析冲突 | Judge 裁定，必要时 `followup_task` 返工 |
| 会话失联 | `list_agents`（include_other_sessions=true）找回；确认失联再重派 |

## 9. 自检清单

- [ ] `python3 integrations/agent_mcp.py` 可正确报告 available / mode
- [ ] 未安装时（`available: false`）核心流程 100% 可用，无报错
- [ ] 已安装时 Cross-Model Review 能派发独立模型并返回 `CrossModelReview`
- [ ] Memory Bank store / recall 调用格式与 agent-mcp 契约一致
- [ ] 未复制任何 agent-mcp 内部实现（queue/daemon/state-machine 等）
