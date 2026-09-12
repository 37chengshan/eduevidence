# EduEvidence 6.2 — 比赛提交目录 / Submission folder

本目录可直接交给支持 Skill 的平台。主入口为根目录 `SKILL.md`；保留整个目录结构，不要只上传这一个文件。

This folder is the complete Skill. Load the root `SKILL.md` and keep its adjacent runtime directories intact.

## 快速查看 / Open the Studio

要求 Python 3.10+，无需 Node，无需先构建前端。

Requires Python 3.10+. Node and a frontend build are not required.

```bash
python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765
```

浏览器打开 / Open: **http://127.0.0.1:8765/studio/**

两个公开案例位于 `examples/`：编程学习与企业客服。各自 `reports-5themes/` 内的 HTML 也可直接离线打开。

The two public examples cover programming learning and workplace customer support. Each includes five standalone HTML reports under `reports-5themes/` for offline reading.

## 核验 / Verification

- 协议与能力：`SKILL.md`；中文说明：`README.zh-CN.md`；English: `README.md`。
- 验收记录：`docs/release-closeout/README.md`。
- 文件完整性：`submission-manifest.json` 记录每个文件的 SHA-256，不包含清单自身。
- 本地确定性验证和浏览器验收已执行；案例为人工文献整理，不代表真实模型研究或企业试点已执行。
- Local deterministic and browser validation are documented. Examples are manually curated literature, not evidence of a completed model research run or an executed workplace pilot.

开发构建与完整测试命令适用于源码仓库；本提交目录包含使用所需的运行资源，排除了测试、Node 依赖、本地研究状态和私有运行历史。

Development builds and full test commands target the source repository. This submission includes the runtime resources and excludes tests, Node dependencies, local research state and private run history.
