# EduEvidence 上架包说明（给评审 / 上架方）

> 参赛作品：**书生国智科探挑战赛 · 自由赛道（赛道六）AI for Social Science**  
> 上架平台：Intern Discovery（书生科学发现平台）SCP 广场

## 一、项目一句话

**EduEvidence** 是一个 Decision-Grade Evidence Engine：把“是否采用某种教学 / 社科干预、工具或 AI 系统”从经验判断转化为**可追溯、可反驳、可验证**的证据决策流程。

核心链路：

`Frame → Retrieve → Extract → Challenge → Audit → Adjudicate → Applicability → Intervene → Evaluate`

面向用户的三段流程保持简单：

`Evidence Review → Decision & Pilot → Evaluate & Update`

## 二、主要能力

- 四态决策：`ADOPT / PILOT / REJECT / INSUFFICIENT EVIDENCE`。
- 证据矩阵、来源溯源、方法学审计、反证挑战、Claim Trace、适用边界。
- KnowledgeGap 驱动的研究设计与新数据回注。
- bounded Evidence Autoresearch：自动研究过程可迭代，但不能自动改写最终科学结论。
- protected Skill Autoevolve：Skill 自进化与真实课题研究状态完全隔离。
- 五种报告视觉身份：Claude Research、Academic Paper、DataLab、DataLab Dark、Presentation / Judge。
- 双语、single-file、离线 HTML 报告。
- React + TypeScript + Vite **Research Studio**：只读查看项目、证据、图谱、运行记录、版本、KnowledgeGap、ResearchIteration 与报告。

关键科学纪律：

- Task performance ≠ learning。
- Missing evidence ≠ zero effect。
- Search snippets are not evidence。
- Validated evidence append-only。
- Causal estimators fail closed。
- Evidence revisions 与 Skill revisions 是两条独立历史。

## 三、安装

要求 Python ≥ 3.10。

```bash
# 开发 / 完整安装
bash install.sh

# 安装为 AI Agent Skill
bash install.sh --skill
bash install.sh --list-hosts
bash install.sh --dry-run

# 也可以
pip install -e .
```

## 四、最快体验

### 1. 直接查看现成报告

完整双语示例包位于 `examples/`。旗舰示例的 Claude Research 报告可以直接离线打开；五种风格位于对应的 `reports-5themes/`。

### 2. 打开正式 Research Studio

```bash
python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765/studio/
```

Research Studio 是当前唯一正式控制台。它是**只读研究驾驶舱**：

- Projects / Overview
- Evidence / Sources
- Evidence Graph
- Runs / Artifacts / Events
- GraphRevision / DecisionSnapshot
- KnowledgeGap / ResearchIteration
- Report Library
- Skill Autoevolve observations
- Workflow Guide

研究执行仍由 Agent / CLI / Agent MCP 进入；Studio 不提供绕过科学状态机的写操作。

### 3. 命令行研究

```bash
eduevidence run --question "小学是否应采用自适应练习平台替代纸质练习册？" --depth deep
eduevidence status --run-id <id>
eduevidence gate --run-id <id>
```

## 五、前端与报告边界

- 可编辑控制台源：`studio/`。
- 构建后的运行时控制台：`web/studio/`；不要手工编辑 bundle。
- `web/landing.html`：介绍页。
- `web/index.html` + `web/js/` + `web/styles.css`：旧三页控制台兼容实现，不再作为新 UI 的开发入口。
- 报告主题在生成时固定；五种视觉身份可以改变排版密度与阅读节奏，但不能改变科学内容。
- 报告数值由确定性代码从 `result.json` 提取；AI 不直接填写图表数值。
- 数据不足时图表被抑制，不使用伪造的效应量、置信区间或结论填充空白。

## 六、构建与验证

```bash
# Python / scientific gates
python3 -m pytest -q

# Research Studio（开发时需要 Node；运行时不需要）
npm ci --prefix studio
npm run build --prefix studio

# 最终 Skill 闭包
bash packaging/make_upload.sh
```

CI 还会验证：

- Python 3.10 / 3.12 full pytest
- Ruff E9/F63/F7/F82
- schema smoke
- isolated wheel smoke
- SKILL parity
- zero-leak
- Autoresearch scientific gates
- TypeScript build reproducibility
- dependency audit
- Playwright 浏览器矩阵
- 320 / 390 / 768 / 1440 响应式检查
- 五种 standalone 报告的 brief / full / bilingual / accessibility 检查
- GitHub Pages 静态导出不包含本地研究状态

## 七、目录导读

| 路径 | 当前职责 |
|---|---|
| `SKILL.md` | Skill 主入口与协议 |
| `skill/` | 工作流、角色和子技能 |
| `engine/` | 证据、图谱、裁决、研究、Autoresearch、Autoevolve |
| `schemas/` | JSON Schema 契约 |
| `retrieval/` | 检索与抓取 |
| `integrations/` | Agent MCP 等可选集成 |
| `visualization/eduevidence-report/` | 双语五主题报告系统 |
| `studio/` | Research Studio 可编辑前端源 |
| `web/studio/` | Research Studio 构建产物 |
| `web/landing.*` | 公开介绍页 |
| `examples/` | 可公开演示的研究示例 |
| `docs/` | 架构、流程和发布文档 |

## 八、分发边界

最终提交包由 `packaging/make_upload.sh` 以 allowlist 方式构建。不得把 `.git/`、`.venv/`、本地研究数据库、用户项目、Autoevolve 私有运行目录、测试缓存或内部 benchmark 历史带入发布包。

GitHub Pages 同样只导出仓库内公开示例；本地 `EDUEVIDENCE_HOME`、项目状态、运行事件与 Autoevolve 会话不会进入公开静态站。
