# EduEvidence

## Evidence-Based AI Teaching Decision & Intervention Skill

> **From Education Questions to Evidence-Based Decisions.**
> **从教学问题，到有证据支撑的教学决策。**

EduEvidence 面向高校教师、教学研究者与教学管理者，把"是否采用一种 AI 教学方式"从经验判断转化为**可追溯、可质疑、可验证的证据决策流程**。

- ⚖️ 不是替教师生成答案，而是帮助教师知道：证据支持什么、不能支持什么、适用于谁、应该怎样试点并验证。
- 🧪 基于真实研究（示例包含 CHI 2023 / PNAS 2026 / ACL 2025 / Springer 2024 的实证证据），不做无来源断言。
- 🚦 最终输出不是"允许/禁止"的二元结论，而是 **ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE** 四态决策 + 可落地的教学干预与评价方案。

---

## What Problem We Solve

普通 AI 面对教育问题通常执行：

```text
问题 → 搜索若干材料 → 总结观点 → 给出建议
```

EduEvidence 执行：

```text
教学问题
  → Education Research Framing（学习者/干预/对照/Outcome/场景）
  → 文献与证据检索（支持证据 + 独立反方证据）
  → Claim-Level Evidence Extraction
  → Skeptic 反证协议 + Method Reviewer 方法学审查
  → Evidence Tribunal（证据裁决）
  → Applicability Analysis（适用性）
  → Decision: ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE
  → Teaching Intervention（最小可验证试点）
  → Evaluation Plan（效果评价）
```

最终回答六个问题：

1. 当前证据到底支持什么？
2. 当前证据不能支持什么？
3. 为什么不同研究会得到不同结果？
4. 对哪类学生、什么课程、什么条件适用？
5. 如果学校真的要用，怎样低风险落地？
6. 实施后如何验证它到底有没有效果？

## 30-second Demo

> 主 Demo：**大一 C 语言课程是否应该允许学生使用生成式 AI 编程助手？**

| 时间 | 阶段 |
|---|---|
| 0–20s | 输入教学问题 |
| 20–45s | Education Research Frame |
| 45–75s | Evidence Retrieval |
| 75–110s | Evidence Matrix |
| 110–135s | Methodology + Skeptic |
| 135–155s | Evidence Tribunal |
| 155–170s | Teaching Intervention + Evaluation |
| 170–180s | Benchmark |

完整示例包见 [`examples/ai-coding-assistant/`](examples/ai-coding-assistant/)。

## Why Education Evidence Is Hard

教育研究证据有几个天然陷阱，EduEvidence 的核心创新就是把应对这些陷阱的环节标准化：

- **Outcome Separation**：`代码完成更快 ≠ 真正学会编程`；`短期成绩提高 ≠ 长期保持提高`；`AI 协助完成任务 ≠ 无 AI 环境下能够迁移`。
- **Counter-Evidence Search**：不能只验证用户的最初假设，必须独立寻找 null / negative / contradictory 证据、AI dependency、novelty effect、self-selection bias 等。
- **Evidence Tribunal**：不是简单把正反论文列在一起，而是判断哪些研究更可信、冲突来自样本/测量/课程/工具还是实验设计、目前最多能得出什么结论。
- **Evidence-to-Action Bridge**：不能停在"研究显示……"，必须连到适用性判断、教学决策、试点干预与评价设计。

## How EduEvidence Works

```text
┌─────────────────────────────────────┐
│            EduEvidence              │
│  教育领域知识 + 决策 + 干预 + 评价   │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│        EvidenceFlow Protocol        │
│ Frame / Retrieve / Extract /        │
│ Challenge / Audit / Adjudicate      │
└────────────────┬────────────────────┘
                 │
        ┌────────┴────────┐
        ▼                 ▼
 Platform Native      Agent MCP
 Execution Mode      Enhanced Mode
```

完整工作流（9 步）：

```text
1. Frame          构建 EducationResearchFrame
2. Retrieve       文献与证据检索（支持证据 + 独立反方证据）
3. Extract        抽取 Claim-Level Evidence（绑定 Outcome）
4. Challenge      Skeptic 反证协议（固定 9 项检查）
5. Audit          Method Reviewer 方法学审查（15 项清单）
6. Adjudicate     Evidence Tribunal 证据裁决（Evidence Matrix + Verdict）
7. Applicability  适用性分析
8. Intervene      Teaching Intervention 设计（最小可验证试点）
9. Evaluate       Evaluation Plan 设计
```

每一步产出经过 JSON Schema 校验（`schemas/`），确定性逻辑由 `scripts/` 提供，教育方法论在 `references/` 中独立成文。

## Outcome Separation

EduEvidence 强制区分 20 类 Outcome（`references/outcome-taxonomy.md`）：

```text
学习效果:   Knowledge Gain / Concept Understanding / Retention / Transfer / Independent Problem Solving
任务表现:   Completion Time / Accuracy / Code Quality / Assignment Score
学习过程:   Engagement / Motivation / Cognitive Load / Help-Seeking / Metacognition
风险指标:   AI Dependency / Over-reliance / Reduced Effort / Reduced Transfer / Academic Integrity Risk / False Confidence
```

主 Demo 的高光点正是这种区分：Kazemitabaar et al. (CHI 2023) 中 AI 代码助手使任务完成率提升 1.15×、得分提升 1.8×，但一周后的保持测试差异不显著——**任务表现 ≠ 学习效果**。

## Evidence Tribunal

`references/tribunal-policy.md` 定义了裁决规则：输入 Frame + Evidence Matrix + Skeptic Findings + Method Reviews，输出 EducationVerdict（`schemas/verdict.schema.json`），包括：

- supported / uncertain / contradicted claims
- 冲突来源分析（样本 / 测量 / 课程 / 工具 / 实验设计）
- Can Claim / Cannot Claim 边界
- 四态决策 + Confidence（规则化计算，不由模型自由生成）

## From Evidence to Action

证据必须连接到真实教学现场（`references/applicability-policy.md`、`intervention-design.md`、`evaluation-design.md`）：

- **Applicability**：For whom? For which course? For which outcome? Under what conditions? With what AI usage policy?
- **Intervention**：永远是"最小可验证试点"，禁止直接全面部署；含 AI 使用规则、教师/学生角色、反思要求、停止条件。
- **Evaluation**：任何 PILOT/ADOPT 建议必须附评价方案；区分基线/后测/保持测试/迁移测试；区分任务表现指标与学习指标。

## Benchmark

第一版 30 个教育研究问题（`benchmarks/questions.jsonl`），S×10 / M×10 / L×10；其中 15 题为主域"高校 AI 辅助教学"，10 题含人工金标注（`benchmarks/annotations/`）。

基线设计：

```text
B0 Direct LLM
B1 Search + LLM
B2 Standard Research Agent
B3 EduEvidence Single-Agent     ← 证明教育方法论价值（B2 vs B3）
B4 EduEvidence + Agent MCP      ← 证明多 Agent 增强价值（B3 vs B4）
```

核心指标：Citation Support Precision / Unsupported Claim Rate / Contradiction Discovery Rate / Outcome Separation Accuracy / Scope Calibration / Intervention Evidence Alignment。详见 `docs/benchmark.md`。

## Example: AI Coding Assistant

> **大学一年级 C 语言课程是否应该允许学生使用生成式 AI 编程助手？**

`examples/ai-coding-assistant/` 完整展示了从问题到决策的全过程：

- **证据**（7 条，均绑定真实来源）：任务表现提升（Kazemitabaar 2023）、无护栏访问损害独立考试表现 -17%（Bastani 2026, PNAS）、护栏设计消除负效应（Bastani 2026）、形成性反馈写作证据（Marzuki 2024）。
- **决策**：**PILOT** —— 任务表现证据强，但大学编程课程的直接学习效应证据缺失，无护栏风险已被证实。
- **干预**：4 阶段试点（Independent Foundation → Explain Don't Solve → Structured Collaboration → Transfer Check）。
- **评价**：无 AI 基线/后测/期末考试保持/无 AI 迁移任务 + AI 依赖风险指标。

另外两个示例：AI 写作助手（`examples/ai-writing-assistant/`）、高数 AI Tutor（`examples/ai-tutor/`）——证明 Skill 不是为一个问题写死。

## Architecture

详见 [`docs/architecture.md`](docs/architecture.md)：

```
EduEvidence/
├── SKILL.md                 # 核心 Skill（短，自包含）
├── references/              # 9 个教育方法论文档
├── schemas/                 # 6 个 JSON Schema 数据契约
├── scripts/                 # 6 个确定性逻辑脚本
├── benchmarks/              # 30 题 + 10 题金标注 + 评测框架
├── examples/                # 3 个完整 Research & Decision Pack
├── docs/                    # architecture / methodology / benchmark / demo / reproducibility
└── tests/                   # pytest 测试矩阵（43 个用例）
```

### SCP / Platform Native Mode

EduEvidence 可完全脱离 Agent MCP 独立运行（比赛验收主路径）：

- 不依赖本地 daemon
- 不依赖某一个 CLI
- 不依赖 Agent MCP
- SKILL.md 可单独理解，核心工作流可完整执行
- 所有 Schema / 方法 / 输出契约独立存在

### Agent MCP Enhanced Mode

Agent MCP 是**性能与可靠性增强层，不是 EduEvidence 成立的前提**（`docs/methodology.md` 的 Complexity Gate）：

- S 级任务：单 Agent 直接执行，0 spawn
- M 级任务：Primary Analysis + Independent Check
- L 级任务：8 角色工作流（Planner / Retriever / Analyst / Skeptic / Method Reviewer / Judge / Intervention Designer / Evaluation Designer）

> 角色数量 ≠ 必须启动的 Agent 数量。Platform Native Mode 由单 Agent 串行执行角色协议。

## Install

```bash
git clone https://github.com/37chengshan/eduevidence.git
cd eduevidence
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## Usage

```bash
# 1. 验证数据符合 Schema 契约
python3 scripts/validate_schema.py --schema schemas/evidence.schema.json \
    --data examples/ai-coding-assistant/evidence.jsonl

# 2. 计算证据质量分与 Confidence
python3 scripts/evidence_score.py examples/ai-coding-assistant/evidence.jsonl

# 3. 生成 Evidence Matrix（主产品界面之一）
python3 scripts/evidence_matrix.py examples/ai-coding-assistant/evidence.jsonl

# 4. 运行 Citation Audit（Claim-证据追溯）
python3 scripts/claim_audit.py --claims claims.jsonl --evidence evidence.jsonl

# 5. 渲染 Research & Decision Pack
python3 scripts/render_report.py \
    --frame examples/ai-coding-assistant/frame.json \
    --evidence examples/ai-coding-assistant/evidence.jsonl \
    --methodology examples/ai-coding-assistant/methodology.json \
    --verdict examples/ai-coding-assistant/verdict.json \
    --intervention examples/ai-coding-assistant/intervention.json \
    --evaluation examples/ai-coding-assistant/evaluation.json \
    --out REPORT.md

# 6. 校验 Benchmark 题目集
python3 scripts/benchmark.py --questions benchmarks/questions.jsonl

# 7. 运行测试
pytest
```

> 真实使用中，Skill 由 Agent 读取 SKILL.md 执行 9 步工作流；`scripts/` 保证结构化数据的确定性校验，`examples/` 是完整运行示例。

## Methodology

- 教育证据质量框架：五维 0–2 分（D1 研究设计 / D2 样本质量 / D3 测量效度 / D4 时间强度 / D5 直接性），总分 0–10（`references/evidence-quality.md`）。
- 方法学审查 15 项清单，最高优先级规则：**任务完成表现不能自动等价为学习效果**（`references/methodology-audit.md`）。
- Confidence 规则化计算：`Evidence Quality + Consistency + Directness + Evidence Count - Conflict Penalty - Unsupported Penalty` → High / Moderate / Low / Insufficient（`scripts/evidence_score.py`）。
- 失败处理：INSUFFICIENT_SOURCES / UNSUPPORTED_CLAIM / CONFLICT_UNRESOLVED / SCOPE_MISMATCH / METHODOLOGY_TOO_WEAK / NEEDS_USER_CONTEXT / TOOL_FAILURE —— 失败时禁止强行生成高确定性建议。

## Limitations

- 第一版冻结垂直场景：**高校 AI 辅助教学**；翻转课堂、项目式学习等第二阶段扩展。
- Benchmark 基于真实文献的可检索证据；模型实际运行结果需按 `docs/benchmark.md` 的 B0–B4 基线采集。
- 搜索与抽取依赖可用检索资源；`TOOL_FAILURE` 时不编造来源。
- EduEvidence 是教学决策辅助，**不代替教师或学校最终决策**；涉及高风险评价、学生处分、个体心理判断、学生重大教育机会时不自动决策。

## Roadmap

- [x] Phase 0 Domain Freeze（场景 + Taxonomy + 决策态 + Schema）
- [x] Phase 1 Single-Agent Core（Frame → Retrieve → Extract → Matrix → Verdict）
- [x] Phase 2 Education Methodology（Outcome Separation / Quality / Audit / Scope）
- [x] Phase 3 Challenge & Tribunal（Skeptic / Conflict / Tribunal）
- [x] Phase 4 Evidence-to-Action（Applicability / Decision / Intervention / Evaluation）
- [x] Phase 5 Benchmark v1（30 题 + 10 题金标注 + B0–B3 框架）
- [ ] Phase 6 Agent MCP（Complexity Gate / Conditional Spawn / Memory）
- [ ] Phase 7 Benchmark v2（B4 / Ablation / 成本对比）
- [ ] Phase 8 Product UI（5 页核心体验）
- [ ] Phase 9 Submission（Demo 视频 / 复现指南）

## License

MIT — 见 [LICENSE](LICENSE)。
