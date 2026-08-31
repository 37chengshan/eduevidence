# 参赛/发布状态（诚实清单，2026-08-31）

| 通道 | 状态 | 证据/说明 |
|---|---|---|
| main CI 全绿 | 待最终全量跑 green 后确认 | 本轮新增 4 项测试；`check_version_consistency`、metrics、Ruff、打包门已本地通过 |
| 版本口径 | 已收敛 | ENGINE_VERSION=6.0.0 → pyproject/package.json/CHANGELOG/SKILL.md/metrics 一致 |
| 协议单一真相源 | 已完成 | Applicability 成为科学阶段，Present 归入 Projection；orchestrator/run_workspace/workflows 三处同源 |
| 外部检索可审计 | 已完成 | SearchPlan + 尝试日志 + 反证查询强制 + 筛选/排除导出（`retrieval/audit.py`, `scripts/search_provenance.py`） |
| 控制平面 | 已完成 | `engine/research_service.py`（事件可回放、产物内容寻址不可变）；dashboard `/api/research/*` |
| Policy 可移植性 | 已完成 | 项目 domain=policy + 框架拒绝 learner/course 泄漏测试 |
| Blogger/Web 大改 | 不投入 | 仅缩小五主题 H1（用户确认项） |
| B2 vs B3 same-model | 进行中 | 有界真实运行 `benchmarks/empirical/omp-dsflash-max-smoke/`（OpenCodeGo ds-flash, thinking=max） |
| 真实课堂数据 | 外部依赖 | 等待匿名数据回注（不与虚构） |
| 发布/投票/视频 | 外部动作 | 需要用户账号操作，本仓库不执行 |
