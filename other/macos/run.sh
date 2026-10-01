#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# B站视频解析工具 —— macOS 启动脚本
#
# 用法：
#   ./run.sh                 正常启动
#   ./run.sh --cli           强制命令行模式
#   ./run.sh --debug         前台运行并打印日志
#
# 首次运行会自动创建 .venv 并安装依赖。
# ---------------------------------------------------------------------------
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT" || { echo "无法进入项目目录" >&2; exit 1; }

FORCE_CLI=0
DEBUG=0
for arg in "$@"; do
    case "$arg" in
        --cli)   FORCE_CLI=1 ;;
        --debug) DEBUG=1 ;;
        -h|--help) sed -n '3,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    esac
done

# ---------------------------------------------------------------- Python
# macOS 自带的 /usr/bin/python3 是 Command Line Tools 提供的，可用但可能缺 tk；
# 优先用 Homebrew 的 python3，其次项目 venv，最后系统 python3。
find_python() {
    for cand in "$PROJECT_ROOT/.venv/bin/python" \
                "$(command -v python3 2>/dev/null)" \
                "/opt/homebrew/bin/python3" \
                "/usr/local/bin/python3" \
                "/usr/bin/python3"; do
        if [ -n "${cand:-}" ] && [ -x "$cand" ]; then
            if "$cand" -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' 2>/dev/null; then
                echo "$cand"; return 0
            fi
        fi
    done
    return 1
}

PYTHON="$(find_python)" || {
    echo "错误：未找到 Python 3.8 或更高版本。" >&2
    echo "  推荐安装：brew install python@3.11" >&2
    echo "  或从 https://www.python.org/downloads/macos/ 下载安装" >&2
    exit 1
}
echo "使用 Python: $PYTHON"

# ---------------------------------------------------------------- 依赖
NEED_VENV=0
if ! "$PYTHON" -c "import PyQt5.QtWidgets" >/dev/null 2>&1; then
    NEED_VENV=1
fi

if [ "$NEED_VENV" -eq 1 ]; then
    if [ ! -x "$PROJECT_ROOT/.venv/bin/python" ]; then
        echo "正在创建虚拟环境 .venv ..."
        "$PYTHON" -m venv "$PROJECT_ROOT/.venv" || {
            echo "创建虚拟环境失败。请确认已安装 Python，且未被系统完整性保护限制。" >&2
            exit 1
        }
    fi
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
    echo "正在安装依赖（首次运行需要几分钟）..."
    "$PYTHON" -m pip install --upgrade pip
    if ! "$PYTHON" -m pip install -r "$PROJECT_ROOT/other/common/requirements.txt"; then
        echo "依赖安装失败。请检查网络后重试。" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------- 环境变量
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true
export NO_PROXY='*'
export no_proxy='*'
export PYTHONIOENCODING='utf-8'
export PYTHONUTF8='1'

# macOS 上 QtWebEngine 偶发因沙箱/GPU 驱动崩溃，用软件渲染更稳
export QT_MAC_WANTS_LAYER=1

# ---------------------------------------------------------------- 启动
if [ "$FORCE_CLI" -eq 1 ]; then
    exec "$PYTHON" "$PROJECT_ROOT/core/cli.py" "$@"
fi

if [ "$DEBUG" -eq 1 ]; then
    exec "$PYTHON" "$PROJECT_ROOT/main.py" "$@"
fi

# 正常启动：把输出重定向到日志，避免在 .app 启动时无处显示
LOG_DIR="$HOME/Library/Logs/BilibiliDownloadTool"
mkdir -p "$LOG_DIR" 2>/dev/null || true
exec "$PYTHON" "$PROJECT_ROOT/main.py" "$@" \
    >>"$LOG_DIR/launcher.log" 2>&1
