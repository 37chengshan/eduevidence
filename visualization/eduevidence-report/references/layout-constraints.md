# Layout Constraints — 五主题报告排版守则（移动端 + 桌面）

EduEvidence 的五套烘焙主题（claude / academic / datalab / datalab-dark / presentation）
共用同一内容契约，但各自拥有排版策略。主题是实现层的自由舞台，**但不能破坏阅读**：
任何加入/修改主题 CSS 或渲染器内联样式的人，都必须遵守以下不变量，并在改动后跑

```bash
python3 scripts/lint_report_layout.py --html-dir examples/ai-coding-assistant-50/reports-5themes
```

静态审计 + 浏览器级实测（390 / 768 / 1280 px × Visual Brief / Full Report）全部通过才能合入。

## 1. 为什么会有这套守则（历史教训）

- `:root[data-theme="X"] .selector` 特异性是 0,2,0，**压过**基座 `@media (max-width:980px)` 的 0,1,0 断点。
  之前五套主题的桌面 `full-report-layout { grid-template-columns:210px minmax(0,1fr) }` 在手机上
  把内容列挤到 ~104px（390 视口下横向裁切）；`repeat(auto-fit,minmax(240px,1fr))` 的内在尺寸
  爆炸让 768px 平板的第二列结果直接消失在视口外（shell scrollWidth 1025 > 768）。
- 修复范式 = 基座断点提供安全网 + **每个主题在自己的 @media ≤980 内重新声明响应式覆写**。

## 2. 硬性不变量（static lint 会逐条检查）

1. **移动端轨道收缩安全**
   - 网格列一律 `minmax(0, 1fr)`（绝不允许裸 `1fr`，它按内容 min-content 定宽）。
   - `repeat(auto-fit, minmax(Npx, 1fr))` 一律写成 `repeat(auto-fit, minmax(min(Npx,100%), 1fr))`，
     让最小值随容器收缩，杜绝内在尺寸爆炸。
2. **主题必须自带移动端覆写**
   - 主题里任何 ≥2 列、含 px 最小值的 `grid-template-columns`（如 full-report-layout、
     report-page-brief、hero-insights、tribunal-grid、brief-source-grid、outcome-groups……）
     都必须在**同一主题文件**的 `@media (max-width:980px)` 内提供等效单列/收缩覆写——
     基座断点压不过主题特异性。
   - 媒体查询外出现裸 `grid-template-columns:1fr` 直接违规。
3. **基座安全网必须存在**（build_report.py 内联样式）：`html,body` 的 `overflow-x:hidden`；
   @media 980 的 `minmax(0,1fr)`；@media 720 的网格 item `min-width:0` 清单与
   `.outcome-groups` / `.evidence-detail-grid,.source-detail-grid` 收缩覆写。
4. **表格与长文本**：任何数据表外包 `.table-wrap { overflow-x:auto }`（滚动而不是撑破页面）；
   `.source-detail-grid dd` / `.claim-cell` 等长文本位点 `overflow-wrap:anywhere`。

## 3. 浏览器级门（check_mobile_layout.js）

无依赖 Node 脚本（Node ≥21，CDP 驱动 headless Chrome），对每个报告在
390 / 768 / 1280 × brief / full 检查：

- `documentElement.scrollWidth > innerWidth` → 页面级横向溢出；
- 可见 `.report-shell` 的 `scrollWidth > clientWidth` → 内容被裁切；
- 逃逸视口且不在滚动容器/`<svg>` 内的元素 → 真溢出（表内/横向操作条内滚动是合法的）；
- 画廊卡片：滚入后必须全部拿到 `is-live`（reveal 契约：滚入播放 + 点击重播）。

无 Chrome/Node 的环境跳过浏览器级阶段（pytest 用 `skipif` 处理）。

## 4. 移动端体验红线

- 390px：单列全内容可读；控件（lang/视图切换）不挤压标题；图表 `width:100%` 自适应。
- 768px（平板）：两列工作台可优雅回退单列，不出现半列被裁。
- `prefers-reduced-motion` / 打印：图表静态完整可见（motion.css 已覆盖 `data-lieflat`）。
- 新滚动容器（`overflow-x:auto`）只是"容器内滚动"，不得让 `.report-shell` 自身出现横向滚动条。

## 5. 验收清单（改动后必跑）

- [ ] `python3 scripts/lint_report_layout.py --html-dir <报告目录>` → PASS
- [ ] `python3 scripts/rebake_all_5themes.py` 重烘焙无回归
- [ ] `python3 -m pytest tests/test_report_layout_mobile.py -q` 全绿
- [ ] 手机实机（或 Chrome 设备模拟）打开 15 份报告：无横向滚动、图表完整、点击可重播动画