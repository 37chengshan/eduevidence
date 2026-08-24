#!/usr/bin/env python3
"""scripts/lint_report_layout.py — 五主题报告排版约束门（静态 + 浏览器级）。

静态审计（无需浏览器）：对基座 CSS（build_report.py 内联）与 5 份主题 CSS 检查
移动安全不变量——任何会撑破视口的写法（裸 1fr 轨道、固定 px 最小值的 auto-fit、
缺少移动端媒体覆写的双列 grid）都必须被拒绝；基座必须携带安全网。

浏览器级门（可选，需要 Chrome + Node ≥21）：对烘焙出的 HTML 报告跑
check_mobile_layout.js，在 390/768/1280 视口 × brief/full 双视图实测：
页面无横向溢出、可见 shell 无内部裁切、画廊卡片滚入后全部 is-live（reveal 生效）。

Usage:
    python3 scripts/lint_report_layout.py                 # 静态审计主题 CSS 与基座
    python3 scripts/lint_report_layout.py --html-dir <dir>  # 追加浏览器级扫描
Exit: 0 = 全部通过；1 = 静态违规；2 = 浏览器级违规。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "visualization" / "eduevidence-report" / "scripts"
THEMES_DIR = SCRIPTS_DIR.parent / "themes"
THEMES = ("claude", "academic", "datalab", "datalab-dark", "presentation")

# 静态不变量 ----------------------------------------------------------------
# 1) 主题 css：双列 grid（含 px 最小值）必须在该主题文件内提供移动端覆写。
TWO_COL_GRID = re.compile(
    r'grid-template-columns:\s*(?:minmax\(\s*\d+px[^,]*,\s*(?:\.?\d+(?:fr|px)?|[^)]*)\)|[^;]*fr)\s*[^;]*;')
# 2) auto-fit 轨道不得使用裸固定 px 最小值（必须 min(min(Npx,100%),1fr)）。
BARE_AUTOFIT = re.compile(r'repeat\(\s*auto-fit\s*,\s*minmax\(\s*\d+px\s*,\s*1fr\s*\)\s*\)')
SAFE_AUTOFIT = re.compile(r'repeat\(\s*auto-fit\s*,\s*minmax\(\s*min\(\s*\d+px\s*,\s*100%\)\s*,\s*1fr\s*\)\s*\)')
# 3) 裸 `1fr 轨道`（无 minmax(0,1fr)）：出现在媒体查询外即为移动端风险。
BARE_1FR = re.compile(r'grid-template-columns:\s*1fr\s*;')
MINMAX0_1FR = re.compile(r'minmax\(\s*0\s*(?:px)?\s*,\s*1fr\s*\)')


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _sections(text: str):
    """Yield (selector_block, css, inside_media) chunks to scope checks."""
    # 简化：按 @media 拆分顶层块
    chunks = []
    pos = 0
    pattern = re.compile(r"@media[^{]*\{")
    for m in pattern.finditer(text):
        if m.start() > pos:
            chunks.append((text[pos:m.start()], False))
        # 平衡取块
        start = m.end() - 1
        depth = 1
        i = start + 1
        while i < len(text) and depth:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        chunks.append((text[start:i], True))
        pos = i
    if pos < len(text):
        chunks.append((text[pos:], False))
    return chunks


def lint_static() -> list[str]:
    problems: list[str] = []

    # 基座内联 CSS（build_report.py render_html 的 <style> 块）
    report_py = (SCRIPTS_DIR / "build_report.py").read_text(encoding="utf-8")
    if "overflow-x:hidden" not in report_py:
        problems.append("base: html/body 缺少 overflow-x:hidden（横向溢出兜底）")
    for needle in (
        ".report-shell {{ width:100%; max-width:1200px;",
        "@media (max-width:980px)",
        "@media (max-width:720px)",
    ):
        if needle not in report_py:
            problems.append(f"base: 缺少必需样式片段 {needle!r}")
    if "minmax(0,1fr)" not in report_py:
        problems.append("base: 缺少 minmax(0,1fr)（移动端 1fr 轨道收缩安全）")
    if "@media (max-width:720px)" not in report_py:
        problems.append("base: @media (max-width:720px) 块缺失")
    elif ".outcome-groups {{ grid-template-columns:repeat(auto-fit,minmax(min(180px,100%),1fr))" not in report_py:
        problems.append("base@720: .outcome-groups 缺少移动端收缩覆写")
    if ".evidence-detail-grid, .source-detail-grid {{ grid-template-columns:1fr;" not in report_py:
        problems.append("base@720: detail 网格缺少 1fr 覆写")

    # 各主题
    for theme in THEMES:
        css_path = THEMES_DIR / f"{theme}.css"
        if not css_path.exists():
            problems.append(f"{theme}: 主题 CSS 缺失")
            continue
        raw = css_path.read_text(encoding="utf-8")
        text = _strip_comments(raw)
        media_regions = _sections(text)
        outside = "".join(c for c, in_media in media_regions if not in_media)
        inside980 = "".join(c for c, in_media in media_regions
                            if in_media and re.search(r"max-width:\s*(980|1100)px", c))

        m = BARE_1FR.search(outside)
        if m:
            problems.append(f"{theme}: 媒体查询外出现裸 grid-template-columns:1fr —— 必须 minmax(0,1fr) 或移入媒体查询")
        for mm in BARE_AUTOFIT.finditer(outside + inside980):
            problems.append(f"{theme}: auto-fit 使用裸固定 px 最小值 {mm.group(0)[:40]} —— 必须 min(min(Npx,100%),1fr)")
        # 双列/多列 grid 且未缩放的：必须在 <=980 媒体块内有同一选择器的覆写
        grid_decls = re.findall(
            r'([^{}]+)\{\s*[^{}]*?grid-template-columns:\s*([^;}]+);', outside)
        for selector, cols in grid_decls:
            if re.search(r"minmax\(\s*0", cols):
                continue
            if "repeat(auto-fit" in cols:
                continue  # 上面已单独检查
            fr_count = len(re.findall(r"(\d+(?:\.\d+)?fr|minmax\([^)]*\))", cols))
            has_px = re.search(r"\d+px", cols) or "1fr" in cols
            if fr_count >= 2 and has_px:
                sel_key = selector.strip()
                # 主题移动覆写应含同一选择器（允许 media 块内是通用 'grid-template-columns' 无选择器？不，需选择器）
                if not re.search(re.escape(sel_key) + r"|" +
                                 re.escape(sel_key.split(" ")[-1]) + r"\s*,\s*[^{]*", inside980) \
                   and sel_key not in inside980 \
                   and selector.strip().split(">")[-1].strip() not in inside980:
                    problems.append(
                        f"{theme}: {selector.strip()[:60]} 双列 grid 在移动端缺少同主题覆写"
                        f"（cols={cols.strip()[:40]}；主题规则特异性高于基座断点，必须自带 @media ≤980）")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduEvidence five-theme report layout gate")
    parser.add_argument("--html-dir", nargs="+", default=None,
                        help="烘焙好的报告目录；提供后追加浏览器级实测（390/768/1280 × brief/full）")
    parser.add_argument("--project", default="ai-coding-assistant-evidence",
                        help="--html-dir 缺省时使用的示例项目名")
    args = parser.parse_args(argv)

    problems = lint_static()
    for p in problems:
        print(f"  [static] {p}")
    code = 1 if problems else 0

    html_dirs: list[Path] = []
    if args.html_dir:
        html_dirs = [Path(d) for d in args.html_dir]
    if html_dirs and code == 0:
        files = sorted({p for d in html_dirs for p in Path(d).glob("*.html")})
        if not files:
            print("  [browser] 没有可扫描的 HTML")
            return 2
        node = subprocess.run(
            ["node", str(SCRIPTS_DIR / "check_mobile_layout.js"),
             "--port", "9290", "--widths", "390,768,1280"]
            + [f"file://{p.resolve()}" for p in files],
            capture_output=True, text=True)
        out = (node.stdout or "") + (node.stderr or "")
        if node.returncode == 0:
            print("  [browser] ALL CLEAN")
        else:
            print(out[-4000:])
            code = 2
    if code == 0:
        print("[+] Layout gate PASSED: 5 themes static invariants clean"
              + (" + browser-level clean" if html_dirs else ""))
    else:
        print(f"[-] Layout gate FAILED ({code})", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())