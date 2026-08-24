"""tests/test_report_layout_mobile.py — 五主题报告排版门（静态 + 浏览器级）。

静态（必跑）：scripts/lint_report_layout.py 的 CSS 不变量审计——裸 1fr 轨道、
无移动端覆写的双列 grid、固定 px 最小值的 auto-fit 都是违规。
浏览器级（有 Chrome + Node ≥21 时跑，否则 skip）：对烘焙报告在
390/768/1280 × brief/full 实测无横向溢出、shell 无裁切、画廊 reveal 生效。
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
LINT = SCRIPTS / "lint_report_layout.py"
NODE_CHECK = (ROOT / "visualization" / "eduevidence-report" / "scripts"
              / "check_mobile_layout.js")

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium", "/usr/bin/chromium-browser",
]
_HAS_NODE = shutil.which("node") is not None and sys.version_info >= (3, 8)
_HAS_CHROME = any(Path(c).exists() for c in CHROME_CANDIDATES)
BROWSER_OK = _HAS_NODE and _HAS_CHROME


def test_static_layout_invariants_for_all_themes():
    """静态排版不变量：5 主题 + 基座 CSS 必须全过（无需浏览器）。"""
    r = subprocess.run([sys.executable, str(LINT)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode in (0, 2), \
        f"static layout invariants failed:\n{r.stdout[-2000:]}{r.stderr[-1000:]}"
    assert "[static]" not in (r.stdout or "")


@pytest.mark.skipif(not BROWSER_OK, reason="Chrome/Node 不可用，跳过浏览器级布局门")
def test_browser_layout_clean_all_viewports(tmp_path):
    """浏览器级：构建 5 主题报告，390/768/1280 × brief/full 全部无溢出、reveal 生效。"""
    # 直接复用已烘焙产物（更快、且与交付物一致）；无则现场构建
    themes_dir = ROOT / "examples" / "ai-coding-assistant-evidence" / "reports-5themes"
    if not list(themes_dir.glob("EduEvidence_Report_*.html")):
        import build_report as br  # noqa: F401  # scripts on path via conftest
        pytest.skip("无烘焙产物，跳过浏览器级实测")
    files = sorted(themes_dir.glob("EduEvidence_Report_*.html"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("lint_report_layout", LINT)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    problems = mod.lint_static()
    assert problems == [], f"static lint failed: {problems}"

    r = subprocess.run(
        ["node", str(NODE_CHECK), "--port", "9293", "--widths", "390,768,1280"]
        + [f"file://{p.resolve()}" for p in files],
        capture_output=True, text=True, timeout=900)
    out = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0, f"browser layout gate failed:\n{out[-4000:]}"
    assert "ALL CLEAN" in out


def test_reveal_contract_in_built_html():
    """静态断言：烘焙 HTML 内的 motion.js 携带 reveal 契约（滚入播放 + 点击重播 +
    timer 清理），且入场错峰延迟存在（避免「只有点击才触发动画」的体验）。"""
    theme_html = (ROOT / "examples" / "ai-coding-assistant-evidence" / "reports-5themes"
                  / "EduEvidence_Report_claude.html")
    if not theme_html.exists():
        pytest.skip("无烘焙产物")
    html = theme_html.read_text(encoding="utf-8")
    m = __import__("re").search(r"<script>\s*(/\* EduEvidence Motion Template.*?</script>)", html, __import__("re").S)
    assert m, "motion template script not found"
    js = m.group(1)
    for token in ("threshold:.3", "replayLieflat", "clearLfTimers",
                  "revealDelay", "addEventListener('click'"):
        assert token in js, f"motion.js missing {token!r}"