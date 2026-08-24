---
name: eduevidence
description: "Evidence-based decisions for ANY educational & social science question — whether, when, and how to adopt a teaching method, curriculum change, AI tool, or policy intervention. Orchestrates modular sub-skills for literature review, methodology bias audit (WWC 5.0 / GRADE), SSOT causal evidence graph construction, gap lens discovery, pre-registered trial design, and empirical DID data re-injection."
---

# EduEvidence 5.2 — Universal Evidence-Based Decision Skill

> **AI4SS Track | 科艺融合 · 通用智能**
> **From Empirical Questions to Evidence-Based Decisions & Causal Trial Loops.**

EduEvidence delivers the **EduEvidence Research Engine** — a persistent system transforming research questions into verifiable decisions. State lives in a unified **Project Workspace** (Project / Run / Revision / DecisionSnapshot) and a **Single Source of Truth (SSOT) Evidence Graph** (engine/evidence_graph.py), linking Papers, Quantitative Effect Sizes (g), Claims, Social Science Risks, and Shared Research Library knowledge.

The canonical protocol below is the single authoritative definition (docs/architecture.md); every stage output is schema-gated (schemas/, 13 contracts).

**Schema 版本口径**：schemas/ 顶层 13 个 = V1 契约（evidence.schema.json 当前修订 1.1、education-frame / verdict 等）；schemas/v2/ 17 个 = V2 契约（evidence-link / research-intent / study / graph-revision / project 等）。文档与代理配置一律以此口径命名。

## 🧭 双研究模式（Research Mode）与执行层

- **Evidence Review**（二手证据综述）与 **Full Research Cycle**（综述 → 知识缺口 → 研究设计 → 本地数据 → 分析 → 图更新 → 再裁决）两种 Research Mode。
- **Project Workspace + Evidence Graph** 为不可变 revision 模型；result.json / HTML / Markdown 都是投影，不是事实库。
- **Shared Research Library**：已验证外部事实（Source/Study/Finding/Audit）跨项目快照复用；研究事实可复用，解释（Claim/EvidenceLink/Applicability/Decision）必须项目本地。
- 冻结科学规则：**No new study design without evidence grounding** — 任何新研究设计必须引用显式、有证据奠基的 KnowledgeGap ID。
- 唯一事实来源与防重规则：**Single Canonical Project per Research Question** — 同一研究问题严格保持单实例，禁止重复建立同名主题目录；更新时采用不可变 Revision 升级机制。
- **执行层双模式**：Mode A **Platform Native**（纯 SKILL 零依赖交付）/ Mode B **Agent MCP** Enhanced（可选增强：启动检测 → 推荐 → 用户授权 → safe_spawn；未启用自动降级 Native）。

---

## 📜 Canonical Protocol — 9 Steps = Research Core 6 + Decision Extension 3

```text
Research Core（6 阶段，证据纪律核心）:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate

Decision Extension（3 阶段，证据到行动）:
Applicability → Intervene → Evaluate

端到端 9 步:
Frame → Retrieve → Extract → Challenge → Audit → Adjudicate
→ Applicability → Intervene → Evaluate

Fetch / Validate = Retrieve 内部强制 gate（RULE 2：snippet ≠ 证据内容）
Present = 最终呈现层（不计入 9 步协议）
```

| # | 阶段 | 输出契约（schemas/） |
|---|------|----------------------|
| 1 | Frame | education-frame.schema.json |
| 2 | Retrieve（内含 Fetch/Validate gate） | source.schema.json / fetch-result.schema.json |
| 3 | Extract | evidence.schema.json |
| 4 | Challenge | evidence.schema.json（反方/未发现/confounder） |
| 5 | Audit | methodology.schema.json（task_vs_learning_guard） |
| 6 | Adjudicate | verdict.schema.json（规则化置信度 + Pre-Verdict Gate） |
| 7 | Applicability | applicability-policy.md（For whom / which course / which outcome / conditions） |
| 8 | Intervene | intervention.schema.json（最小可验证 PILOT + Stop Conditions） |
| 9 | Evaluate | evaluation.schema.json（基/后/保持/迁移 + 成功阈值） |
| Present | 呈现层 | result.json / result.zh.json → 烘焙主题报告 |

**Present 主题显示名（生成时五选一，烘焙定主题，最终 HTML 仅中英文切换）**：

```text
    ├─ Claude Research      [Light]
    ├─ Academic Paper       [Light]
    ├─ DataLab              [Light]
    ├─ DataLab              [Dark]
    └─ Presentation / Judge [Dark]
```

---

## 🗺️ Sub-Skill Map（12 个子 skill 归位）

| 阶段 | 实现组件 |
|------|----------|
| 1 Frame | skill/sub-skills/research-planning + Complexity Gate（S/M/L，scripts/complexity_gate.py） |
| 2 Retrieve | skill/sub-skills/literature-review + skill/sub-skills/aihot-trend-analysis（retrieval/fetch.py + validate.py 为内部 gate） |
| 3 Extract | skill/sub-skills/evidence-extraction |
| 4 Challenge | skill/sub-skills/contradiction-analysis |
| 5 Audit | skill/sub-skills/methodology-audit（WWC 5.0 / GRADE） |
| 6 Adjudicate | skill/sub-skills/evidence-review + scripts/pre_verdict_gate.py + scripts/compute_confidence.py（meta-analysis：DerSimonian-Laird、Q、I²、Egger） |
| 7 Applicability | references/applicability-policy.md |
| 8 Intervene | references/intervention-design.md + skill/agents/intervention-designer.md |
| 9 Evaluate | references/evaluation-design.md + skill/agents/evaluation-designer.md |
| Present | skill/sub-skills/report-generation + visualization/eduevidence-report（静态报告与三适配器；Lieflat 仅作开发期图表参考，不是提交包运行时） |
| Full Research Cycle 扩展 | skill/sub-skills/gap-analysis → skill/sub-skills/study-design → skill/sub-skills/data-analysis（DID 回注） |
| 横切 | skill/sub-skills/ethics-review（IRB 合规） |

**Full Research Cycle = Decision-to-Outcome Loop**：证据综述 → 知识缺口（Gap）→ 预注册研究设计 → 本地课堂/田野数据 → DID/OLS 分析 → Evidence Graph 更新 → 再裁决。Grounding Rule：不基于证据奠基的 KnowledgeGap ID，禁止产生新研究设计。

**Complexity Gate（S/M/L）**：S（Quick Fact）快速路径；M（Standard Review）八角色全走；L（Deep Causal Cycle）标准路径 + 系统化搜索 + 独立双审 + 干预/评价强制产出。默认门控 M，向上从严。

---

## 🎯 Killer Demo Scenario: AI Coding Assistants in CS1

**Question**: *Should first-year university C/Python students be allowed to use generative AI coding assistants?*
- **50 Empirical Studies Synthesized**: PNAS 2025, ACM CHI, ICER, SIGCSE, ICSE, IEEE TSE.
- **Empirical Paradox Discovered**: In-task speed +0.64g vs delayed solo exam -0.28g (WWC 5.0 Scaffolding Dependency Trap).
- **Tribunal Verdict**: **PILOT** (Restricted 4-phase fading pilot; unconstrained adoption rejected).
- **Causal Closed Loop**: 12-week Quasi-Experimental DID trial design + Classroom CSV data injection.

---

## 🖥️ Local Web Studio（3 页，无 Agent 派遣）

```bash
python3 scripts/dashboard_server.py --port 8765
# http://127.0.0.1:8765/
```

静态前端（web/）+ 轻量 API 服务，直接读取 examples/<project_id>/ 下的 skill 工件：

1. **仪表盘 (Dashboard)** — 跨课题 KPI、效应量对比、课题资产矩阵。
2. **报告浏览 (Report Browser)** — 列出有 EduEvidence_Report.html 的课题；若存在 reports-5themes/EduEvidence_Report_<theme>.html 则提供 5 主题烘焙变体选择。报告仅在生成时定主题，最终 HTML 只保留中英文切换，不做运行时换肤。
3. **数据可视化 (Data Visualization)** — 按课题选择，查看森林图、效应量分布、结果维度与 SSOT 证据图谱。

页面是 **契约驱动**：新课题只要产出 result.json / evidence_graph.json 即自动出现，无硬编码 demo 数据。

---

## 📦 Visualization Data Contract（Skill ↔ Web 同步）

| 工件 | 产出阶段 | 消费页面 |
| --- | --- | --- |
| result.json → forest_plot_data | Extract + Adjudicate | 森林图 |
| result.json → evidence（数值 effect_size） | Extract | 效应量分布 |
| result.json → outcome_mapping | Extract + Audit | 结果维度 |
| evidence_graph.json → export_echarts_graph() | Adjudicate（evidence-review） | SSOT 证据图谱 |
| EduEvidence_Report.html + reports-5themes/*.html | Present（visualization/eduevidence-report/scripts/build_report.py） | 报告浏览（烘焙变体） |
| result.json → meta.question + decision | Present | 仪表盘 / 可视化标题与裁决 |

关键 forest_plot_data 字段：study_label、outcome_dimension、effect_size（Hedges g）、ci_lower/ci_upper、sample_size、direction、wwc_rating。

---

## 🛡️ 科学可信度强制（失败关闭）

- **DID 失败关闭**：`scripts/did_regression.py` 对奇异/共线设计、空 2×2 格、零方差、
  饱和模型等不可估计输入返回 `status="error"` + 稳定 `error_code`，且
  `did_coefficient` / `standard_error` / `p_value` / `ci_95` / `hedges_g` 全部为
  `null`，绝不伪造 `SE=1.0` 或虚假 p 值。
- **非 cluster 显式标注**：普通 DID 结果带 `inference_status="non_cluster_warning"`；
  DID/准实验（QED）永远不得标注 `Meets Standards Without Reservations`。
- **无直接学习证据不得 ADOPT**：裁决要求 learning/独立迁移结果（直接性 directness=2）
  才允许 High+支持 → ADOPT；任务表现、程序效率、主观体验只能 PILOT/INSUFFICIENT。
- **无伪精度**：缺 CI 的森林图点只画点、不画误差线并标记 "CI not reported"；
  meta 合并不使用默认 `se=0.20`，无精度证据的条目记录排除原因。

## 📦 三适配器统一契约（Python 标准库）

三个可视化适配器共享同一 envelope 契约，适配器本身只使用 Python 标准库；ECharts 是 Web Studio 的可选浏览器运行时，不属于适配器或提交包：
统一 CLI：`--result <result.json> --out <out.json> [--lang zh|en]`：

```bash
python3 visualization/eduevidence-report/scripts/build_charts.py \
    --result examples/ai-coding-assistant/result.json --out /tmp/charts.json
python3 visualization/eduevidence-report/scripts/build_infographics.py \
    --result examples/ai-coding-assistant/result.json --out /tmp/infographics.json
python3 visualization/eduevidence-report/scripts/build_figures.py \
    --result examples/ai-coding-assistant/result.json --out /tmp/figures.json --theme okabe_ito
```

输出 envelope：`adapter` / `contract_version` / `source_ref` / `source_sha256`（provenance）
/ `locale` / `data`。报告渲染器 `build_report.py` 与 CLI 共享同一核心函数。
（`build_figures.py --out-dir` 为兼容参数，迁移后移除。）

## 🛠️ CLI Quick Commands

```bash
# 1. 3 页 Local Web Studio
python3 scripts/dashboard_server.py --port 8765

# 2. 学术与实时趋势检索
python3 -m retrieval.search "AI coding assistants learning transfer"

# 3. 田野数据 DID 回归（数据契约回写见 skill/sub-skills/data-analysis）
python3 scripts/did_regression.py examples/ai-coding-assistant/field_classroom_data.csv

# 4. 效应量计算器
python3 scripts/effect_calculator.py --mean1 78.5 --sd1 10.2 --n1 90 --mean2 72.1 --sd2 11.0 --n2 90

# 5. Skill 一致性检查
python3 scripts/skill_lint.py
```
