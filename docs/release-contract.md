# EduEvidence Release Contract（开发事实表，2026-08-23）

> 状态：P0–P4 已完成并复核；本文件只记录当前实现与发布决策。
> 权威运行定义：`SKILL.md`、`schemas/`、结果 JSON、`packaging/make_upload.sh`。

## 1. 最终提交包（P4 实测）

| 项 | 值 |
|---|---|
| 路径 | `dist/eduevidence-submission/`（每次构建清空重建） |
| 文件数 | 301（manifest 不含自身） |
| 总大小 | 24,693,641 bytes（约 23.5 MiB） |
| 构建 | `bash packaging/make_upload.sh`（allowlist staging + Python manifest） |
| 干净包 smoke | 任意 cwd：核心 import、DID error 契约、三适配器 envelope、主报告 integrity PASS、Web 启动（5 课题/96 证据、viz/report 200、landing 404）通过 |
| 泄漏 | dist 内无 `__pycache__`/`*.pyc`/`.DS_Store`/competition-brief/superpowers/wizard/did_sandbox/landing/lieflat-charts |
| F09 | `urls.jsonl` 不在包内；`MOE China Education News` 仅作为原始 benchmark fixture 标题，不是包级硬门 |

## 2. 本轮实现

1. **科学失败关闭**：`scripts/did_regression.py` 对不可估计 DID 返回结构化 `status="error"` + 稳定 `error_code`，推断字段为 `null`；普通 DID 标记 `non_cluster_warning`；DID/QED 不越界为 `Meets Standards Without Reservations`。
2. **学习证据门**：`engine/tribunal.py` 要求 learning/transfer 且 `directness=2` 才允许 High+support → `ADOPT`；任务表现、程序效率、主观体验不足时降级为 `PILOT`。
3. **精度与图谱契约**：缺 CI 不生成代理误差线；meta 不使用默认 `se=0.20`；精度 provenance 与 `MEASURES` 幂等边均有契约测试。
4. **可视化适配器**：三 CLI 共享 `adapter/contract_version/source_ref/source_sha256/locale/data` envelope；`build_figures --out-dir` 保留兼容解析。
5. **报告**：forest plot、ticks、tspan、双语标签、ECharts mount/static fallback 与完整性门已验证。
6. **Web Studio**：仅三页只读视图；POST 405；未知路由、项目、主题、路径越界均 404；前端动态值经 `esc()`；报告 iframe 使用 `sandbox="allow-scripts"`，响应含 CSP/nosniff。
7. **发布脚本**：allowlist staging 输出 `dist/eduevidence-submission/`；manifest 排除自身并记录 POSIX 路径、字节数、SHA-256。

## 3. 延后事项（明确不属于本轮）

- Liang–Zeger cluster-robust 推断：需完整统计规格、参考数值与下游消费测试。
- EventBus 异步队列/SSE 完整重构：本轮保持现有实现。
- 仓库级删除旧 Web 文件：旧入口仅从提交包 allowlist 排除。
- `--out-dir` 参数移除：待真实调用闭包迁移后处理。
- 官方比赛规则核验：提交媒介、大小限制、联网策略、Python/浏览器版本需以官方页面为准；当前 24.7MB 不代表官方上限。

## 4. 核心验证证据

| 验证项 | 结果 |
|---|---|
| 开发仓库全量测试 | `786 passed, 1 skipped` |
| Skill lint | PASS |
| 主报告 | integrity `PASS` |
| Web handler | 三页入口、项目/主题 allowlist、POST 405、路径越界 404 |
| 浏览器 smoke | 3 nav、报告 iframe sandbox、5 主题、viz 图表渲染 |
| 干净包 | 任意 cwd 可运行核心 import、适配器、报告和 Web |
| manifest | 301 个内容文件，首项 hash 可复核；无缓存/敏感文件泄漏 |

## 5. 运行时依赖口径

- Python 核心与三适配器使用标准库。
- 报告静态 HTML/SVG 是离线真实能力。
- Web 交互图依赖 `web/index.html` 当前声明的 jsDelivr ECharts 5.4.3；未将 ECharts runtime 纳入提交包，因此不得宣称 Web 交互图离线独立运行。
- 五主题是生成时烘焙的报告变体，不是 Web 运行时换肤。

## 6. 提交边界

提交包包含 `SKILL.md`、运行时源码、schemas、references、报告渲染器、三页 Web、主 Demo、必要 docs 和 packaging 说明；排除 `.git`、`.venv`、缓存、`.agents`、`.mimosa`、内部 brief、旧 Web 归档、tests、benchmarks 和 `visualization/lieflat-charts`。仓库旧文件不在本轮删除。

工作树中除本轮收尾改动外的既有用户变更不应被自动清理；提交前必须按明确文件范围暂存。