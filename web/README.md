# web/ — 前端分发与兼容边界

EduEvidence 当前正式控制台是 **Research Studio**。开发源与运行时分发物必须明确区分：

- **唯一权威可编辑控制台源**：`studio/`（React + TypeScript + Vite）。新功能、交互、可访问性、移动端和数据契约只在这里开发。
- **正式运行时控制台**：`web/studio/`。它是 `studio/` 的可复现构建产物，由 Python 本地服务、Skill 上架包和 GitHub Pages 直接提供；不要手工编辑其中的 bundle。
- `web/landing.html/.css/.js`：公开介绍页，保持独立视觉叙事；它只负责介绍和进入 Research Studio，不拥有研究状态。
- `web/index.html`、`web/js/`、`web/styles.css`：v5 时代三页控制台的**兼容层 / 历史实现**。现有兼容 API 或旧链接在确有需要时可以继续读取它们，但不得把它们当作新 UI 的开发入口，也不要向其中增加新的产品功能。
- `web/showcase_v2/`：冻结展示页。除安全或断链修复外不再与 Research Studio 同步演进。

## 约定

1. 新的 Research Studio 页面、组件和交互只能进入 `studio/src/`；禁止继续扩展旧 `web/js/` 控制台。
2. `npm run build --prefix studio` 必须可复现 `web/studio/`；CI 使用 `git diff --exit-code -- web/studio` 守护这一点。
3. 本地正式入口是 `http://127.0.0.1:<port>/studio/`；`dashboard_server.py` 的 `/`、`/console` 也应指向同一构建。
4. GitHub Pages 根页保留介绍页，`/studio/` 是公开只读 Research Studio；静态导出只包含仓库示例，不包含本地研究项目、运行事件或 Autoevolve 会话。
5. 五种报告主题属于 `visualization/eduevidence-report/` 的**生成时视觉身份**，不是 Research Studio 的运行时换肤；同一研究版本的科学内容不得因主题改变。
6. 报告本体保持 single-file / zero-CDN；营销介绍页可以使用外部字体等展示资源，但不应把它们引入研究报告的离线能力声明。
