# web/ — Local Web Studio 前端单一源说明（plan E3）

- **唯一权威前端源**：`web/js/*.js`（ES Modules）+ `web/styles.css` + `web/index.html`。
  `scripts/dashboard_server.py` 直接服务本目录；改 UI 只改这里。
- `web/landing.html/.css/.js`：营销落地页，独立入口，不依赖 Studio 运行时。
- `web/showcase_v2/`：独立展示页（含一份**冻结变体**的 js 拷贝）。其 js 与 `web/js`
  的模块级去重是遗留跟进项（见 docs/plans/STATUS.md）；在去重完成前，
  修复 Studio bug 时请同步检查该页是否受影响。
- ~~archive_v1 / archive_v3~~：陈旧快照，已于 v5.2.0（E3）删除——历史在 git。

## 约定

1. 新增页面一律从 `web/js/` import 模块，禁止再复制 js 目录。
2. CDN（echarts/fonts）仅允许出现在 landing/showcase 营销页；Studio 报告本体保持
   zero-CDN。
