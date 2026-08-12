#!/usr/bin/env bash
# EduEvidence 一键安装脚本（macOS / Linux）
#
# 用法:
#   bash install.sh                    # 本地安装：venv + 依赖 + 自检 + 测试（等价 --dev）
#   bash install.sh --dev              # 同上（向后兼容，默认行为）
#   bash install.sh --skill            # 交互式安装为 AI Agent Skill（选择宿主 Agent）
#   bash install.sh --list-hosts       # 显示支持的宿主 Agent 与 Skill 落点
#   bash install.sh --dry-run          # 只预览将执行的变更，不写入任何文件
#   bash install.sh --skill --dry-run  # 预览 Skill 安装（仍会交互选择宿主）
set -euo pipefail

REPO_URL="https://github.com/37chengshan/eduevidence"
SKILL_NAME="eduevidence"
# Skill 本体（对应仓库根目录结构：SKILL.md + skill/agents/ + references/ + schemas/ + scripts/）
SKILL_PAYLOAD=(SKILL.md skill references schemas scripts)

# ---------- 参数解析 ----------
INSTALL_DEV=""
HAS_DEV_FLAG=0
MODE="local"      # local | skill | list
DRY_RUN=0
while [ $# -gt 0 ]; do
    case "$1" in
        --dev)        INSTALL_DEV="--dev"; HAS_DEV_FLAG=1; shift ;;
        --skill)      MODE="skill"; shift ;;
        --list-hosts) MODE="list"; shift ;;
        --dry-run)    DRY_RUN=1; shift ;;
        *) echo "ERROR: 未知参数: $1" >&2; exit 1 ;;
    esac
done
# 向后兼容：裸 `bash install.sh` 等价于 `bash install.sh --dev`
if [ "$MODE" = "local" ] && [ "$HAS_DEV_FLAG" -eq 0 ]; then
    INSTALL_DEV="--dev"
fi

# ---------- 宿主 Agent 表 ----------
HOSTS=(claude codex omp opencode kimi zcode openclaw harness grok copilot cline)

# 探测宿主是否已安装（尽力而为；未探测到不阻塞安装，只做提示）
host_detect() {
    case "$1" in
        claude)   [ -d "$HOME/.claude" ] || [ -f "$HOME/.claude.json" ] ;;
        codex)    [ -d "$HOME/.codex" ] || command -v codex >/dev/null 2>&1 ;;
        omp)      [ -d "$HOME/.omp" ] ;;
        opencode) [ -d "$HOME/.config/opencode" ] || command -v opencode >/dev/null 2>&1 ;;
        kimi)     [ -d "${KIMI_CODE_HOME:-$HOME/.kimi-code}" ] || command -v kimi >/dev/null 2>&1 ;;
        zcode)    [ -d "$HOME/.zcode" ] ;;
        openclaw) [ -d "$HOME/.openclaw" ] ;;
        harness)  [ -d "$HOME/.harness" ] ;;
        grok)     [ -d "$HOME/.grok" ] ;;
        copilot)  [ -d "$HOME/.copilot" ] || command -v copilot >/dev/null 2>&1 ;;
        cline)    [ -d "$HOME/.cline" ] || [ -d "$HOME/.config/cline" ] ;;
        *) return 1 ;;
    esac
}

# 返回某宿主的 skill 根目录（eduevidence/ 会创建为其子目录）
host_skill_root() {
    case "$1" in
        claude)
            if [ -d "$HOME/.claude/skills" ] || [ -d "$HOME/.claude" ]; then
                echo "$HOME/.claude/skills"          # 用户级配置存在 → 用户级落点
            else
                echo "$PWD/.claude/skills"           # 否则装到项目级 .claude/skills/
            fi
            ;;
        codex)
            # 官方标准 ~/.agents/skills，兼容 ~/.codex/skills 与 ~/.codex/prompts，按探测顺序取
            if [ -d "$HOME/.agents/skills" ]; then
                echo "$HOME/.agents/skills"
            elif [ -d "$HOME/.codex/skills" ]; then
                echo "$HOME/.codex/skills"
            elif [ -d "$HOME/.codex/prompts" ]; then
                echo "$HOME/.codex/prompts"
            else
                echo "$HOME/.agents/skills"
            fi
            ;;
        omp)      echo "$HOME/.omp/agent/skills" ;;
        opencode) echo "$HOME/.config/opencode/skills" ;;
        kimi)     echo "${KIMI_CODE_HOME:-$HOME/.kimi-code}/skills" ;;
        zcode)    echo "$HOME/.zcode/skills" ;;
        openclaw) echo "$HOME/.openclaw/skills" ;;
        harness)  echo "$HOME/.harness/skills" ;;
        grok)     echo "$HOME/.grok/skills" ;;
        copilot)  echo "$HOME/.copilot/skills" ;;
        cline)    echo "$HOME/.cline/skills" ;;
    esac
}

# ---------- 通用提示词（方式三：宿主不在支持列表时交给任意 AI） ----------
UNIVERSAL_PROMPT="请把 https://github.com/37chengshan/eduevidence 仓库中的 EduEvidence 安装为 skill：
1. 将仓库根目录的 SKILL.md、skill/、references/、schemas/、scripts/ 复制到你的 skill 目录
   （如 ~/.claude/skills/eduevidence/、~/.omp/agent/skills/eduevidence/、~/.agents/skills/eduevidence/ 等），
   或按你的 skill 装载机制导入；
2. 安装完成后确认能读取 SKILL.md，并能运行 scripts/ 下的确定性脚本；
3. 告诉我安装结果，并提醒我为项目点 star（${REPO_URL}）。"

print_universal_prompt() {
    echo ""
    echo "============================================================"
    echo "方式三：通用提示词（宿主 Agent 不在支持列表时使用）"
    echo "============================================================"
    echo "把下面这段提示词原样交给任意支持 skill / 自定义指令的 AI："
    echo ""
    echo "$UNIVERSAL_PROMPT"
    echo ""
    echo "============================================================"
}

# ---------- 安装完成后的 star 环节 ----------
star_prompt() {
    echo ""
    echo "==> 如果觉得 EduEvidence 有用，欢迎为项目点个 star ⭐"
    if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "    [dry-run] 检测到 GitHub CLI 已登录，将执行: gh repo star 37chengshan/eduevidence"
            return 0
        fi
        echo "    检测到 GitHub CLI 已登录，正在为项目点 star ..."
        if gh repo star 37chengshan/eduevidence 2>/dev/null; then
            echo "    ✅ 已为 37chengshan/eduevidence 点亮 star，感谢支持！"
        else
            echo "    点 star 未成功（可能已经点过），忽略。"
        fi
    else
        echo "    未检测到已登录的 GitHub CLI，请打开浏览器点 star："
        echo "    $REPO_URL"
        echo "    （或执行: open ${REPO_URL}）"
    fi
}

# ---------- 本地安装：Python 检查 + venv + 依赖 + 自检（--dev 时含 pytest） ----------
local_setup() {
    local PYTHON_BIN="${PYTHON:-python3}"

    echo "==> EduEvidence 安装开始"

    # 1. 检查 Python >= 3.10
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        echo "ERROR: 未找到 ${PYTHON_BIN}，请先安装 Python 3.10+ (https://www.python.org/downloads/)" >&2
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
        if [ "$DRY_RUN" -eq 1 ]; then
            echo "    [dry-run] 将创建虚拟环境 .venv"
        else
            echo "==> 创建虚拟环境 .venv"
            "$PYTHON_BIN" -m venv .venv
        fi
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] 将激活 .venv 并安装依赖（pip install -e .）"
        echo "    [dry-run] 将运行自检：Schema 校验 + 渲染双语 HTML 报告"
        return 0
    fi
    # shellcheck disable=SC1091
    source .venv/bin/activate
    echo "    venv: $(command -v python)"

    # 3. 安装依赖（EduEvidence 核心零依赖；--dev 额外安装 pytest）
    if [ "$INSTALL_DEV" = "--dev" ]; then
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
    if [ "$INSTALL_DEV" = "--dev" ]; then
        echo "==> 运行测试"
        pytest -q
    fi
}

local_finish() {
    echo ""
    echo "安装完成。下一步："
    echo "  1. 查看示例报告:  open examples/ai-coding-assistant/EduEvidence_Report.html"
    echo "  2. 渲染自己的 result.json（需同时准备 result.zh.json 中文平行数据）:"
    echo "     python visualization/eduevidence-report/scripts/build_report.py \\"
    echo "         --result <你的 result.json> --out REPORT.html"
}

# ---------- Skill 安装 ----------
# 复制 Skill 本体到指定目录（写前自动备份：cp -r 到 .bak-时间戳）
install_to_dir() {
    local dest="$1"
    if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] 将备份已有目录: $dest → $dest.bak-<时间戳>（如存在）"
        echo "    [dry-run] 将复制: ${SKILL_PAYLOAD[*]} → $dest/"
        return 0
    fi
    if [ -e "$dest" ]; then
        local bak="${dest}.bak-$(date +%Y%m%d%H%M%S)"
        cp -r "$dest" "$bak"
        echo "    已备份: $dest → $bak"
        rm -rf "$dest"
    fi
    mkdir -p "$dest"
    cp -R "${SKILL_PAYLOAD[@]}" "$dest"/
    echo "    ✅ 已安装: $dest"
}

# 安装到单个宿主
install_one_host() {
    local host="$1"
    local dest
    dest="$(host_skill_root "$host")/$SKILL_NAME"
    echo ""
    echo "==> 安装 Skill 到 $host"
    echo "    目标目录: $dest"
    install_to_dir "$dest"
    echo "    提示: 重启 $host 会话后 Skill 即可自动发现（或按宿主机制手动装载）"
}

# custom：手动指定 skill 根目录
custom_install() {
    local dir=""
    read -r -p "请输入 skill 根目录（将创建 <目录>/$SKILL_NAME/）: " dir || true
    dir="${dir%/}"
    dir="${dir/#\~/$HOME}"        # 展开 ~
    if [ -z "$dir" ]; then
        echo "ERROR: 未输入目录，取消安装。" >&2
        exit 1
    fi
    echo "==> 安装 Skill 到自定义目录"
    echo "    目标目录: $dir/$SKILL_NAME"
    install_to_dir "$dir/$SKILL_NAME"
}

# 交互式选择宿主并安装 Skill
skill_install() {
    local i=1 choice="" mark=""
    echo ""
    echo "==> 选择安装到哪个宿主 Agent（Skill 落点见: bash install.sh --list-hosts）："
    for h in "${HOSTS[@]}"; do
        if host_detect "$h"; then mark="✓ 已探测到"; else mark="未探测到"; fi
        printf '  %2d) %-9s %s\n' "$i" "$h" "$mark"
        i=$((i + 1))
    done
    printf '  %2d) %-9s 安装到全部 Agent\n' "$i" "all"
    i=$((i + 1))
    printf '  %2d) %-9s 手动指定 skill 目录\n' "$i" "custom"
    i=$((i + 1))
    printf '  %2d) %-9s 只装本地（venv + pytest + 自检）\n' "$i" "local"

    read -r -p "请输入编号或名称 [claude]: " choice || true
    choice="${choice:-claude}"

    # 数字编号 → 名称
    if [[ "$choice" =~ ^[0-9]+$ ]]; then
        local idx=$((choice - 1))
        if [ "$idx" -lt "${#HOSTS[@]}" ]; then
            choice="${HOSTS[$idx]}"
        else
            case "$idx" in
                11) choice="all" ;;
                12) choice="custom" ;;
                13) choice="local" ;;
                *) echo "ERROR: 无效编号" >&2; exit 1 ;;
            esac
        fi
    fi
    # 名称校验
    case "$choice" in
        all|local|custom) ;;
        *)
            local found=0 h
            for h in "${HOSTS[@]}"; do
                [ "$h" = "$choice" ] && found=1
            done
            if [ "$found" -eq 0 ]; then
                echo "ERROR: 无效选择: $choice" >&2
                exit 1
            fi
            ;;
    esac
    echo "    已选择: $choice"

    case "$choice" in
        local)
            echo "==> 仅本地安装：安装 pytest 并运行测试"
            if [ "$DRY_RUN" -eq 1 ]; then
                echo "    [dry-run] 将执行: pip install -e '.[dev]' && pytest -q"
            else
                pip install --quiet -e '.[dev]'
                pytest -q
            fi
            ;;
        all)
            for h in "${HOSTS[@]}"; do install_one_host "$h"; done
            print_universal_prompt
            ;;
        custom)
            custom_install
            print_universal_prompt
            ;;
        *)
            install_one_host "$choice"
            print_universal_prompt
            ;;
    esac
}

# ---------- --list-hosts：显示支持列表与落点 ----------
list_hosts() {
    echo "==> EduEvidence 支持的宿主 Agent 与 Skill 落点"
    printf '  %-10s %-12s %s\n' "宿主" "探测" "Skill 安装落点"
    printf '  %-10s %-12s %s\n' "----" "----" "----------------"
    for h in "${HOSTS[@]}"; do
        if host_detect "$h"; then mark="✓ 已探测到"; else mark="未探测到"; fi
        printf '  %-10s %-12s %s/%s/\n' "$h" "$mark" "$(host_skill_root "$h")" "$SKILL_NAME"
    done
    echo ""
    echo "  选择 all 安装到全部 Agent；custom 手动指定目录；local 只装本地。"
    echo "  未列出的 Agent（方式三）：用通用提示词手动安装，详见 README「安装为 Skill」。"
}

# ---------- 主流程 ----------
case "$MODE" in
    list)
        list_hosts
        ;;
    skill)
        local_setup
        skill_install
        star_prompt
        ;;
    local)
        local_setup
        local_finish
        star_prompt
        ;;
esac
echo ""
echo "完成。"
