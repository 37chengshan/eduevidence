# EduEvidence 全流程实测问题清单

> 日期：2026-08-12
> 场景：`eduevidence run --question "大一 C 语言课程是否应该允许学生使用生成式 AI 编程助手？"` 全流程实测（模式二 Agent MCP，批准 omp/gpt-5.6-sol 高级 + opencode-go/deepseek-v4-flash 普通）
> 范围：SKILL.md 流程 → 8 角色执行 → Fetch/Validate → Pre-Verdict Gate → 确定性 Confidence → 报告渲染

---

## 一、已修复问题

### FIX-1 `compute_confidence.py` 的 `raw_model_confidence_breakdown` 写 null 导致 schema 违规

- **位置**：`scripts/compute_confidence.py:158`
- **现象**：raw verdict 无 `confidence_breakdown` 时写入 `None`，`verdict.schema.json` 要求 object → Pre-Verdict Gate `deterministic_confidence` fail
- **修复**：`raw_verdict.get("confidence_breakdown") or {}`
- **验证**：gate 重跑 PASS

### FIX-2 Pre-Verdict Gate 真实拦截了 7 处 agent 产物契约违规

全流程中 gate 逐层拦截并修正（真实 gate 价值验证）：

| # | 产物 | 违规 | 修复 |
|---|------|------|------|
| 1 | frame.json | `decision_target` 用长文本非枚举 | → `teaching_decision` |
| 2 | frame.json | `outcomes.primary/secondary/risk` 用长文本 | → 枚举（independent_problem_solving 等） |
| 3 | frame.json | `scope.study_types` 是字符串 | → 数组 |
| 4 | frame.json | `inclusion/exclusion_criteria` 是字符串 | → 数组 |
| 5 | sources.jsonl | `authority_level` 自由文本（"peer-reviewed conference paper"） | → tier1-5 枚举 |
| 6 | sources.jsonl | `source_location` 非 URL（含"Proceedings of..."） | → canonical URL |
| 7 | sources.jsonl | `search_snippet` 不在 schema | → `extensions.search_snippet` |
| 8 | evidence.jsonl | `claim_id` 不在 evidence schema | → `extensions.claim_id` |
| 9 | evidence.jsonl | `study_type` 值 "controlled_experiment" 非枚举 | → `quasi_experimental` |
| 10 | evidence.jsonl | `sample_size` 字符串 | → int/null |

> 根因：8 个角色 agent 的产物由 LLM 生成，schema 契约未在角色 prompt 中严格约束；建议各角色 md 中明确枚举/格式。

### FIX-3 agent-mcp 检测依赖 env 变量

- **位置**：`integrations/agent_mcp.py` `detect_agent_mcp()`
- **现象**：daemon 实际在 8765 端口监听，但 `AGENT_MCP_INSTALLED` env 未设 → 判 `available: False`
- **处理**：运行时显式 `AGENT_MCP_INSTALLED=1` 启用（符合保守设计：env 声明 + daemon 可达双条件）
- **建议**：文档明确"安装后需设 AGENT_MCP_INSTALLED=1 或由宿主 MCP 层注入"

---

## 二、流程中发现的真实证据纠偏（Fetch 价值验证）

### EVID-1 旧演示锚点错误被 Fetch Gate 纠正

| 锚点 | 原演示数据 | Fetch 验证后真相 |
|------|-----------|----------------|
| Kazemitabaar "用时 0.57x" | 写入 evidence | arXiv 摘要未含 → **剔除** |
| Marzuki "显著正向影响写作" | 写入 evidence | 实际 3 名 EFL 学生质性案例研究，无效应量 → **改为感知/态度发现** |
| Wermelinger | 用作证据 | 全文付费墙不可得（FETCH_PARTIAL）→ **完全排除** |
| Denny | 用作证据 | CACM 框架综述无原始数据 → **标 UNSUPPORTED 背景** |

> 证明 RULE 2（Search snippet ≠ Evidence）的必要性：演示数据本身含未验证锚点，Fetch Gate 全部拦截。

### EVID-2 Bastani 2025 全流程采用 PMC 全文验证数据

- N=2848 预注册 RCT（原演示数据写"近千名"）
- 无护栏 GPT Base：练习 +48%、移除访问后独立考试 **-17%**
- 带护栏 GPT Tutor：练习 +127%、无负面学习效应（"拐杖"机制、答对率 51%）
- 拆为 E-001/E-002/E-003 三条证据（Q9）

---

## 三、遗留问题（未修复，需后续处理）

### OPEN-1 uncertain_claims 部分主张无证据 ID 引用

- **现象**：Pre-Verdict Gate `claim_evidence_audit` warn：`uncertain_claims: claim carries no evidence id: 16 周整学期...`
- **影响**：裁决的不确定主张应绑定证据（或标注"证据缺失"），当前部分未绑定
- **建议**：evidence-judge prompt 要求 uncertain_claims 每条标注 `[无直接证据]` 或引用 E-xxx

### OPEN-2 outcome_mapping warn

- **现象**：frame 声明的部分 outcomes（如 ai_dependency）无对应 evidence
- **建议**：框架声明的 outcomes 与 evidence 覆盖之间应有映射报告（哪些 outcome 有证据、哪些无）

### OPEN-3 result.zh.json 为简化生成

- **现象**：本流程 result.zh.json 直接复制 result.json（产物已是中文，但元数据/枚举未做正式双语平行）
- **建议**：正式双语平行生成器（AI 直接产出，非复制）

### OPEN-4 角色 prompt 未内嵌 schema 契约

- **现象**：8 角色 agent 产物首次均有多处 schema 违规，靠 gate 事后拦截
- **建议**：各 `skill/agents/*.md` 增加"输出必须符合 schemas/<对应>.schema.json"的显式约束 + 枚举值表

### OPEN-5 detector 双条件导致 UX 困惑

- **现象**：daemon 在跑但 env 未设 → 用户以为 Agent MCP 不可用
- **建议**：detect 报告区分"daemon 可达但未声明"与"完全不可用"，或 install.sh 安装后自动写 env

### OPEN-6 证据 count 与 claims count 都是 13

- **现象**：本流程 evidence.jsonl 13 条 = claims 13 条（每条 evidence 一个 claim_id）
- **说明**：这是抽取策略（claim-level evidence），符合契约；但 P0-03 强调"独立研究数"计权已由 confidence 使用（studies=6）
- **建议**：多个 evidence 共享同一 claim 的情况应允许（claim_id 复用），本流程未出现

---

## 四、全流程最终产物

| 产物 | 值 |
|------|-----|
| 执行模式 | agent_mcp_enhanced（批准映射，Tier 2 Native 执行） |
| 复杂度 | L（8 角色完整工作流） |
| 来源 | 7 个（全部 CrossRef/PMC/arXiv 验证） |
| 证据 | 13 条（SUPPORTED 12 + UNSUPPORTED 1） |
| 独立研究 / 样本 | 6 / 6 |
| 裁决 | **PILOT**（Moderate 0.612） |
| 支持 / 不确定 / 反驳主张 | 10 / 9 / 4 |
| 可主张 / 不可主张 / 缺失证据 | 7 / 8 / 10 |
| Pre-Verdict Gate | 11/11 PASS |
| 报告 | EduEvidence_Report.html（269KB，integrity PASS） |

**核心结论**：任务表现提升（+48%/+127%/+35%）与学习效应（-17% 独立考试 / null 保持力）分离；无大学 CS 大一直接证据 → 有护栏试点 + 无 AI 独立评测 + 止损点，填补证据空白。
