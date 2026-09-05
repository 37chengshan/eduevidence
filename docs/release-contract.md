# EduEvidence Release Contract（当前实现事实表）

> 本文件记录当前可发布实现与边界。权威运行定义仍以 `SKILL.md`、`schemas/`、结果 JSON、CI 与 `packaging/make_upload.sh` 为准。

## 1. 产品入口

- **介绍页**：`web/landing.html`，用于项目说明与进入 Research Studio。
- **正式控制台开发源**：`studio/`（React + TypeScript + Vite）。
- **正式控制台运行时**：`web/studio/`，由构建生成，不手工编辑。
- **本地入口**：`python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765` 后访问 `/studio/`。
- **公开静态入口**：GitHub Pages 根页保留介绍页，`/studio/` 提供只读公开示例。
- `web/index.html`、`web/js/`、`web/styles.css` 是历史三页控制台的兼容实现，不再是产品开发主线。

## 2. Research Studio 边界

Research Studio 是**只读研究驾驶舱**，可查看：

- Project / Decision / Applicability
- Sources / Studies / Findings / Claims
- Source → Finding → Claim 图谱
- Runs / stage state / execution plan / gates
- Artifacts / Events
- GraphRevision / DecisionSnapshot
- KnowledgeGap / ResearchIteration
- 五主题报告库
- Skill Autoevolve 观测记录

Studio 不拥有研究执行权，不提供绕过 Agent、CLI、Agent MCP、科学门或 canonical single-writer 的写入口。

## 3. 科学展示契约

1. 缺失值保持缺失，不把 `None`、未报告 CI 或无检索命中转换为 0。
2. 合法 `0.0` 端点必须保留。
3. Studio 不自行计算 pooled effect、跨 outcome 平均值或根据数值正负推断 Claim relation。
4. Finding 的 observed effect 与 Finding→Claim 的 relation 是不同概念。
5. DecisionSnapshot 若未绑定当前 GraphRevision，前端必须暴露 stale 状态。
6. Graph 只读取 committed HEAD ancestry；孤立 revision 不进入历史。
7. 报告缺数据时应抑制不适用图表，而不是生成假效应量、假 p 值、假风险或假课堂处方。

## 4. 五主题报告契约

保留五个视觉身份：

- Claude Research
- Academic Paper
- DataLab
- DataLab Dark
- Presentation / Judge

主题可以改变视觉语言、信息密度和阅读节奏，但同一研究版本的证据、来源、数值、适用边界与 Decision 必须一致。

报告包含 Visual Brief 与 Full Report 两种阅读层级。Full Report 由语义模块组成，允许上游 AI 组织通常 5–7 个章节；未提供有效 outline 时使用内置 fallback。图表选择可以由 AI 根据数据形态规划，但数值由确定性提取器从 `result.json` 读取。

报告仍保持 single-file、双语、离线可读；JavaScript 是增强层，不得成为关键科学内容唯一载体。

## 5. Evidence Autoresearch / Skill Autoevolve 边界

- Evidence Autoresearch 可以优化检索策略和研究过程，但不能让 worker 直接解决 KnowledgeGap、修改 canonical scientific state 或自动决定最终结论。
- Skill Autoevolve 不修改真实用户研究状态。
- 自动流程不得自主发起人体研究、merge `main`、release 或 deploy。
- Evidence revision 与 Skill revision 是两条独立历史。

## 6. 静态发布与隐私

GitHub Pages 构建只导出仓库中的公开 examples。以下内容不得进入静态站：

- `EDUEVIDENCE_HOME`
- 本地用户 projects
- research-control SQLite 数据
- 本地 run/event/artifact 历史
- Autoevolve 私有 session / candidate 内容

本地 Studio 的 SQLite 访问是只读；投影不得向浏览器暴露宿主机文件路径。

## 7. 构建与门禁

当前发布门包含：

- Python 3.10 / 3.12 full pytest
- Ruff E9/F63/F7/F82
- metrics gate
- schema smoke
- isolated wheel smoke
- upload build
- SKILL parity
- zero-leak
- Autoresearch scientific / orchestration / protected gates
- benchmark partition contract
- npm locked install + high-severity audit
- TypeScript build
- `web/studio/` reproducible build check
- Playwright browser / responsive / static deployment tests
- serious / critical accessibility scan
- five-theme standalone report validation
- final Skill closure build
- GitHub Pages build and deploy

自动测试不是完整人工 WCAG 认证，也不能替代视觉审查；关键前端变更应同时检查 CI 截图。

## 8. 分发边界

`packaging/make_upload.sh` 以 allowlist 从干净 staging 重建最终 Skill。发布包应包含运行所需的 `SKILL.md`、agents 配置、engine、schemas、references、retrieval、integrations、visualization、构建后的 `web/studio/` 与必要文档；不得携带 `.git`、`.venv`、缓存、本地研究状态、私有 benchmark 历史或 Autoevolve 私有运行目录。

Node 是 Research Studio **开发/构建依赖**，不是最终本地 Studio 的运行依赖；最终用户运行控制台只需要已构建的静态资源与 Python 服务。

## 9. 仓库治理

`main` 的代码合并应以 exact-head CI 为门。仓库当前应优先配置 GitHub branch protection / ruleset，至少要求 PR、CI、Autoresearch Gates 与 Research Studio 检查通过后才能合并；自动研究与 Autoevolve 永远不是 `main` 的 merge authority。
