---
name: intake
description: One-shot two-round user intake before any research workflow. User answers only mode and questions; the agent infers the rest and then runs unattended.
---

# Intake — 一次性两轮引导

Use this **before** selecting `evidence-review` / `decision-and-pilot` / `evaluate-and-update`.
The user answers **only** mode and questions. Everything else is agent judgment.
After the wrap-up summary is confirmed once, run **unattended**.

Programmatic twin: `scripts/intake/` package (`session.py` + `prefs.py` + `hooks.py`) +
`schemas/v2/intake.schema.json`.
Non-question preferences persist to `~/.eduevidence/prefs.json`
(`enhancement`, `mcp`/`jev` mappings, `depth_preference`, `open_browser`,
`default_main_theme`). **Never record the research question in prefs.**
All five report themes stay rendered; `default_main_theme` only decides which one to open.

---

## 第一轮固定语句（逐字使用）

```text
1) 研究问题（必填）
2) 执行增强（可多选，各附一句话简介）：
   [agent_mcp] Agent MCP — 多 CLI/多模型分工、独立子上下文、超时恢复（可选执行增强）
   [jev]       Jev — 轻量工具子集派发，适合把确定性小步交给受限工具面
   [semdecide] SemDecide — 语义决策辅助，只结构化上游意图，不改下游确定性路由
   [none]      均不启用 — 平台原生模式，零外部执行增强
3) 深度：
   [S]    S 快检 — 单点问题，最小检索面，直接给边界结论
   [M]    M 标准 — 常规采用/比较问题，标准证据到决策流程
   [L]    L 深研 — 高影响、有争议或要试点，完整深研与决策扩展
   [auto] 自动 — 不选则按指南判定
```

### 深度自动判定指南（仅当用户选 auto / 不选）

| 信号 | 判定 |
|---|---|
| 单点问题（查定义、查公式、单条事实） | **S** |
| 常规采用 / 是否有效 / 比较对照 | **M** |
| 高影响、有争议、要试点 / 全面部署 / 政策级 | **L** |
| 不确定 | **M** |

用户显式选 S / M / L 时**不再**自动判定。CLI 同义词：`quick=S`，`standard=M`，`deep=L`。

---

## 第二轮（仅在需要时追问）

### A. 增强项（仅当第一轮勾选了对应增强）

| 增强开启时 | 第二轮只问这一项 | 落盘位置 |
|---|---|---|
| **Agent MCP** | 角色 → CLI / 模型 **授权表**（只展示本机扫描到的真实 CLI/模型；确认后固化 `~/.eduevidence/agent_mcp_approval.json`，含 `role_mapping_hash`） | prefs.`mcp.role_mapping` + 批准文件 |
| **Jev** | 工具子集（如 `search` / `fetch` / `validate`；只派发确定性小步，禁止旁路 spawn） | prefs.`jev.tool_subset` |
| **SemDecide** | 用途说明（只结构化上游 ResearchIntent / Frame，供 `recommend_mode`；**不改**下游确定性路由） | prefs / intake.`semdecide.purpose` |

未勾选的增强**不得**追问。勾选「均不启用」则整段跳过。

### B. 背景智能深挖（始终执行）

按题目推断领域 Frame 骨架后，针对该题追问 **3–6** 个影响边界的问题：

1. **人群**（目标学习者 / 决策对象）
2. **干预**（具体方法 / 工具及用法）
3. **对照**（与什么比较；可用 business as usual）
4. **主结果**（一个主要结果指标）
5. **情境**（学制 / 班型 / 线上线下 / 支持条件）

规则：

- **智能默认 + 一次确认**：能从题目直接推出的字段给出默认值，用户回车即采纳；推出不出的字段留空追问，**禁止编造**。
- 全部边界答完后，打印一次摘要，**一次确认**。
- 摘要确认后进入无人值守，不再逐步打断。

### C. 收尾摘要（一次确认）

```text
—— 收尾摘要（一次确认后无人值守）——
  问题：…
  增强：…
  深度：…（判定理由）
  边界：population / intervention / comparison / primary_outcome / context
  结束后打开报告：是|否 ｜ 主主题：claude|academic|datalab|datalab-dark|presentation
  确认并开始无人值守执行？[Y/n]
```

用户确认后：写入 `intake.json`（过 `schemas/v2/intake.schema.json`），更新 `prefs.json`（不含研究问题），调用 `eduevidence run` / 工作流，**不再提问**。

---

## 无人值守与浏览器

- `python3 -m intake.cli --print-prompts`（或 `python3 scripts/intake/__main__.py --print-prompts`）
- `eduevidence run --yes` 或非 TTY：跳过全部提问，只用 prefs + CLI 标志，**不**弹浏览器。
- 结束时若 `prefs.open_browser` 为 true 且终端可交互：用 `webbrowser.open` 打开**主报告**。
- 五主题全部渲染并保留在 `reports-5themes/`；主报告 = `default_main_theme` 对应的那份，只决定**打开哪份**，不删除其余主题。
- `python3 scripts/dashboard_server.py --open`（或 `eduevidence dashboard --open`）启动后打开 Studio URL `/studio/`。

## 与 Canonical Protocol 的关系

Intake 不是协议阶段，只是启动前的**一次性**用户契约收集。收集完成后的流程仍走：

```text
Evidence Review → Decision & Pilot → Evaluate & Update
```

Frame 阶段（`skill/task-briefs/frame.md`）继续负责完整 Research Frame 与 `NEEDS_USER_CONTEXT`；
本文件的边界追问只是提前把用户才知道的边界收齐，避免中途反复打断。

## 失败处理

| 失败 | 处理 |
|---|---|
| 研究问题为空 | 第一轮重问；不得带空问题进入工作流。 |
| 用户不确认收尾摘要 | 回到对应轮次修改，不得静默开跑。 |
| 增强不可用（如 Agent MCP 未安装） | 记录 `AGENT_MCP_UNAVAILABLE` 并降级 Platform Native；不阻断科学正确性。 |
| 边界字段用户拒绝提供 | 显式标注 `unknown + 如何获取`（FR-03），禁止用默认值冒充事实。 |
