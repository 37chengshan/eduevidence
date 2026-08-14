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
  "state": "available",
  "mode": "agent_mcp_enhanced",
  "port": 8765,
  "reason": "agent-mcp installed and daemon reachable",
  "hint": "",
  "enhanced_features": {"multi_cli_dispatch": true, "cross_model_review": true, "memory_bank": true}
}
```

检测结果是**三态**（`state` 字段，新增；旧字段全部保留，向后兼容）：

| `state` | 含义 | 动作 |
|---|---|---|
| `available` | `AGENT_MCP_INSTALLED` 已声明 **且** daemon 可达（`available: true`，`mode: agent_mcp_enhanced`） | 直接启用高级功能 |
| `daemon_reachable_undeclared` | daemon 在 8765 端口可达，但 `AGENT_MCP_INSTALLED` 未声明（`available: false`，`mode: platform_native`） | 设置 `AGENT_MCP_INSTALLED=1`（见下）即可启用，无需重装；`hint` 字段给出指引 |
| `unavailable` | 未安装 / daemon 不可达（`available: false`，`mode: platform_native`；`reasons` 说明原因） | 安装并启动 agent-mcp daemon |

> 「daemon 在跑但 env 未设」不再被误报为完全不可用（OPEN-5）：`state` 如实区分，
> 并给出可执行提示（`hint`）。`available: true` 仅在三态为 `available` 时为真。

环境变量 / 声明文件：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AGENT_MCP_INSTALLED` | 未设置 | `1/true/yes` 表示已安装；`~/.eduevidence/env` 中的 `AGENT_MCP_INSTALLED=1` 作为后备来源（`bash install.sh` 安装完成后自动写入） |
| `AGENT_MCP_PORT` | `8765` | daemon 端口 |
| `AGENT_MCP_HOME` | `~/.codex`（或 `CODEX_HOME`） | 状态目录 |
| `AGENT_MCP_ENV_FILE` | `~/.eduevidence/env` | 声明文件路径；优先级：真实环境变量 > 该文件 > 默认值 |

**设置 `AGENT_MCP_INSTALLED=1` 的三种方式**（任选其一）：

1. `bash install.sh` 安装完成后自动写入 `~/.eduevidence/env`（`AGENT_MCP_INSTALLED=1`，幂等）；
2. 手动写入 shell profile：`echo 'export AGENT_MCP_INSTALLED=1' >> ~/.zshrc`（或 `~/.bashrc`）后 `source`；
3. 由宿主 MCP 层在启动会话时注入该环境变量（`daemon_reachable_undeclared` 的 `hint` 会提示这一点）。

> 本仓库 `install.sh` 只写「已安装」声明，**不安装 agent-mcp daemon**（daemon 请用
> agent-mcp 仓库的安装脚本安装并启动）。声明 ≠ daemon 可达：声明了但 daemon 未起 →
> `state: unavailable`；daemon 起了但未声明 → `state: daemon_reachable_undeclared`。

## 4. 高级策略：Fast / Strong / Independent

> **Fast models collect. Strong models reason. Independent models verify.**

| 角色 | 类别 | 建议（示例，须用户确认） |
|---|---|---|
| evidence-retriever | fast（资料搜索/整理/去重/初筛） | omp / fast-low-cost |
| education-planner | strong（Framing） | claude / reasoning |
| evidence-analyst | strong（结构化抽取） | claude / structured |
| method-reviewer | strong（方法学） | claude / reasoning |
| evidence-judge | strong（Tribunal） | claude / reasoning |
| intervention-designer / evaluation-designer | strong | claude / reasoning |
| skeptic | independent（反证） | claude / reasoning |

**具体模型与 CLI 不写死在代码中**——`integrations/agent_mcp.py` 的 `ROLE_REQUIREMENTS` 只描述**能力需求**（reasoning/speed/cost/structured_output/context/tool_use）。实际 CLI/模型必须来自用户确认的 `agent_mcp_approval.json`：先扫描（`model_inventory.json`）→ 展示推荐表 → 用户明确确认 → `safe_spawn()` 才放行；任何一步缺失都返回 `AGENT_MCP_APPROVAL_REQUIRED`，业务代码禁止绕过 `safe_spawn` 直接 spawn。

## 5. Cross-Model Review（独立模型交叉审核）

流程（总体实施计划 §25）：

```text
Primary Analysis → Draft Verdict → Independent Review → Judge → Final Verdict
```

调用：

```python
from integrations.agent_mcp import cross_model_review

# 独立审核者的 CLI/模型必须是用户已确认的（skeptic 角色映射）；
# 未确认时返回 AGENT_MCP_APPROVAL_REQUIRED，不会 spawn。
plan = cross_model_review(draft_verdict, target_cli="claude",
                          model="<用户确认的独立模型>", approval=approval_record)
if plan["status"] == "READY":
    # 用 plan["spawn_call"] 通过 MCP 派发独立审核者
    pass
elif plan["status"] == "AGENT_MCP_APPROVAL_REQUIRED":
    # 先展示推荐表，请用户确认映射后再重试
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
| 未安装 / daemon 不可达 | `state: unavailable`，`AGENT_MCP_UNAVAILABLE`，退化为 Platform Native Mode，照常出结果 |
| daemon 可达但未声明 `AGENT_MCP_INSTALLED` | `state: daemon_reachable_undeclared`；按 `hint` 设置 `AGENT_MCP_INSTALLED=1`（写入 `~/.eduevidence/env` / shell profile / 宿主 MCP 注入）后重试 |
| 已安装但未确认模型映射 / approval 哈希不匹配 | `AGENT_MCP_APPROVAL_REQUIRED`，禁止 spawn；展示推荐表请用户确认后再执行 |
| 派发超时 | 任务级 `timeout_seconds` 自动终止；等待超时看 wait 存活证据再决策 |
| 独立审核者结果与主分析冲突 | Judge 裁定，必要时 `followup_task` 返工 |
| 会话失联 | `list_agents`（include_other_sessions=true）找回；确认失联再重派 |

## 9. 自检清单

- [ ] `python3 integrations/agent_mcp.py` 可正确报告 available / mode / state（三态）
- [ ] 未安装时（`available: false`）核心流程 100% 可用，无报错
- [ ] 已安装时 Cross-Model Review 能派发独立模型并返回 `CrossModelReview`
- [ ] Memory Bank store / recall 调用格式与 agent-mcp 契约一致
- [ ] 未复制任何 agent-mcp 内部实现（queue/daemon/state-machine 等）
