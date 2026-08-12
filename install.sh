#!/usr/bin/env bash
# EduEvidence 一键安装脚本（macOS / Linux）
# 用法: bash install.sh [--dev]
#   --dev  额外安装 pytest 并运行测试（默认开启）
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
INSTALL_DEV="${1:-}"

echo "==> EduEvidence 安装开始"

# 1. 检查 Python >= 3.10
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "ERROR: 未找到 $PYTHON_BIN，请先安装 Python 3.10+ (https://www.python.org/downloads/)" >&2
    exit 1
fi
PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="${PY_VERSION%%.*}"
PY_MINOR="${PY_VERSION#*.}"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: 需要 Python 3.10+，当前 $PY_VERSION" >&2
    exit 1
fi
echo "    Python $PY_VERSION OK"

# 2. 创建 venv（如不存在）
if [ ! -d ".venv" ]; then
    echo "==> 创建虚拟环境 .venv"
    "$PYTHON_BIN" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
echo "    venv: $(command -v python)"

# 3. 安装依赖（EduEvidence 核心零依赖；--dev 额外安装 pytest）
if [ "$INSTALL_DEV" = "--dev" ] || [ -z "$INSTALL_DEV" ]; then
    echo "==> 安装开发依赖（pytest）"
    pip install --quiet --upgrade pip
    pip install --quiet -e '.[dev]'
else
    echo "==> 安装核心（零第三方依赖）"
    pip install --quiet --upgrade pip
    pip install --quiet -e .
fi

# 4. 可选：matplotlib 用于学术图 PNG/PDF 导出（非必需）
if python -c "import matplotlib" 2>/dev/null; then
    echo "    matplotlib: 已安装（学术图 PNG/PDF 可用）"
else
    echo "    matplotlib: 未安装（学术图仍可输出 SVG；PNG/PDF 导出需要 pip install matplotlib）"
fi

# 5. 自检：Schema 校验 + 报告渲染
echo "==> 自检：Schema 校验"
python scripts/validate_schema.py --schema schemas/verdict.schema.json \
    --data examples/ai-coding-assistant/verdict.json
python scripts/validate_schema.py --schema schemas/evidence.schema.json \
    --data examples/ai-coding-assistant/evidence.jsonl

echo "==> 自检：渲染双语 HTML 报告"
python visualization/eduevidence-report/scripts/build_report.py \
    --result examples/ai-coding-assistant/result.json \
    --out /tmp/eduevidence-smoke.html
rm -f /tmp/eduevidence-smoke.html

# 6. 运行测试（仅 dev 模式）
if [ "$INSTALL_DEV" = "--dev" ] || [ -z "$INSTALL_DEV" ]; then
    echo "==> 运行测试"
    pytest -q
fi

echo ""
echo "安装完成。下一步："
echo "  1. 查看示例报告:  open examples/ai-coding-assistant/EduEvidence_Report.html"
echo "  2. 渲染自己的 result.json（需同时准备 result.zh.json 中文平行数据）:"
echo "     python visualization/eduevidence-report/scripts/build_report.py \\"
echo "         --result <你的 result.json> --out REPORT.html"
