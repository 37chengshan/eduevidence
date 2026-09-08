# 验证记录

完整日志保存在仓库本地 `dist/release-closeout/`，不是模型执行历史，也不会作为研究事实输入。最终分发目录附带本报告和逐文件 SHA-256 清单。

| 检查 | 证据 |
|---|---|
| Python 3.12 / 3.10 | `python312-final.log` / `python310-final.log` |
| 浏览器、无障碍、静态子目录 | `browser-final.log` |
| 首组视觉基线建立 | `visual-baseline-create.log`，后续 browser-final 另行验证 |
| 版本 / metrics / Ruff | `version.log` / `metrics-check.log` / `ruff.log` |
| Skill 协议 / 科学不变量 | `skill-lint.log` / `scientific-gates.log` |
| 五主题中宽布局 | `report-layout.log` |
| 锁定依赖 / 安全检查 | `npm-ci.log` / `npm-audit.json` / `python-audit.json` |
| 构建 / 静态导出 | `studio-build.log` / `pages-build.log` |
| wheel / flat Skill | `wheel-build.log` / `final-package-smoke.log` |
| 完整目录清单 | `dist/eduevidence-submission/submission-manifest.json` |

Python 3.12 和 3.10 全量结果均为 **928 passed, 1 skipped**。跳过项是依赖可选第三方 jsonschema 的 `test_approval_matches_schema`；主路径的标准库 schema 验证已执行。六条 warning 来自已有对抗测试返回 dict，并非执行失败。metrics 的 878 表示源码测试函数数，不能与参数化执行用例数混用。版本 6.0.0、47 schemas、Skill lint、科学不变量与 Ruff 通过。

隔离 wheel 和完整 Skill 均通过仓库外 CLI、schema、双领域读取、临时项目创建、HTTP Studio 与两例各五主题报告检查；启动 PATH 不含 Node。npm 锁定安装、官方 registry audit（0 vulnerabilities）和 pip-audit（未发现漏洞）有日志。真实模型九阶段研究、跨后端并行实证效果、企业试点执行均未开展；新客服例是人工文献整理。未知效应、置信区间和运行成本不会补成零。

## 交付结论

- **Skill：本地确定性门禁及独立运行范围内合格。**
- **前端：本机已覆盖功能、视觉、动效和浏览器门禁范围内合格。** 最终 29 项浏览器测试通过，8 张初始基线经独立复验；生产资源二次构建逐字一致。
- **真实模型研究 / 真实企业试点 / 跨后端实证比较：未验证。**

最终提交为 `dist/eduevidence-submission/` 整体目录，未创建本次交付压缩包。根目录 `START-HERE.md` 提供中英启动说明，`submission-manifest.json` 校验文件完整性。
