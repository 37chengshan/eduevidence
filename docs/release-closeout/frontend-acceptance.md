# 前端验收

环境：本机 macOS、Playwright Chromium 1193。Studio 预构建资源在本地 Python 服务和静态子目录部署下测试。

自动浏览器覆盖 320 / 390 / 768 / 1440px、明暗外观、项目六个标签、总览/阅读室/系统迭代/流程导览；包含错误/空数据、无历史、过期决定、API 失败、静态私有状态排除、五主题双语/全文、下载和离线阅读。serious/critical 可访问性扫描包含测试中列出的页面与报告；这不等同完整人工 WCAG 认证。

动效验证包括 Canvas 图像变化、停止后 400ms rAF 数量不增长、主标题几何不变、触屏静态与 reduced-motion、完整图谱链和播放暂停。导航底板实际采样确认白色背景、由短到长过渡、链接/文本位置不变、减少动态时 transition=0s。移动端完整图谱允许其容器横向滚动，页面本身不横向溢出。

## 图像证据

- 改造前截图：仓库本地 `dist/release-closeout/before/`。
- 最终测试截图及动效 metrics：`studio/test-results/closeout/`。
- README 实拍：`assets/readme/studio-overview.png`、`studio-graph.png`、`studio-reports.png`。
- 最终侧栏尺寸预览：`dist/release-closeout/sidebar-compact.png`。
- 固定视觉基线：`studio/tests/closeout.spec.ts-snapshots/`，四宽度 × 两外观的总览页。

本次没有历史视觉基线。先审阅截图、再创建首组 macOS 基线，并另行执行匹配检查；首次生成截图不作为历史回归通过证据。基线仅覆盖总览矩阵，其余页面依靠本次功能、布局、扫描与截图审阅。更换操作系统、字体或浏览器版本时须审阅后重新建立基线。

人工检查重点为长标题、卡片可读性、移动端折行、图谱节点及连线、报告主题身份和新导航。这里记录本机验收范围，不宣称 Safari/Firefox 或真实触屏硬件已验证。屏幕截图无法单独证明动画连续性，相关结论来自浏览器中的运动/暂停采样。

## 结论

**本机覆盖范围内合格**：29 项浏览器测试通过，包括首组 8 张固定视觉基线的独立匹配复验；最终 TypeScript/生产构建通过，重复构建资源逐字一致。未解决的 serious/critical 扫描缺陷为 0。首次建立基线不代表过去版本的视觉回归已经验证。
