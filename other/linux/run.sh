#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# B站视频解析工具 —— Linux 启动脚本
#
# 用法：
#   ./run.sh                 正常启动
#   ./run.sh --cli           强制命令行模式
#   ./run.sh --debug         前台运行并打印日志
#   ./run.sh --no-sandbox    以 root 运行时跳过沙箱检查
#
# 脚本会：
#   1. 定位项目根目录
#   2. 找到可用的 Python（优先 .venv）
#   3. 检查 Qt 运行库依赖，缺失时给出明确的安装命令
#   4. 清理代理环境变量（B站为国内站点，走代理反而更慢/失败）
#   5. 启动 main.py
# ---------------------------------------------------------------------------
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT" || { echo "无法进入项目目录: $PROJECT_ROOT" >&2; exit 1; }

FORCE_CLI=0
DEBUG=0
NO_SANDBOX=0
for arg in "$@"; do
    case "$arg" in
        --cli)        FORCE_CLI=1 ;;
        --debug)      DEBUG=1 ;;
        --no-sandbox) NO_SANDBOX=1 ;;
        -h|--help)
            sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
    esac
done

# ---------------------------------------------------------------- Python
find_python() {
    # 优先级：项目虚拟环境 > python3 > python
    for cand in "$PROJECT_ROOT/.venv/bin/python" \
                "$PROJECT_ROOT/venv/bin/python" \
                "$(command -v python3 2>/dev/null)" \
                "$(command -v python 2>/dev/null)"; do
        if [ -n "${cand:-}" ] && [ -x "$cand" ]; then
            # 必须是 3.8+
            if "$cand" -c 'import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)' 2>/dev/null; then
                echo "$cand"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON="$(find_python)" || {
    echo "错误：未找到 Python 3.8 或更高版本。" >&2
    echo "  Debian/Ubuntu : sudo apt install python3 python3-venv python3-pip" >&2
    echo "  Fedora        : sudo dnf install python3 python3-pip" >&2
    echo "  Arch          : sudo pacman -S python python-pip" >&2
    exit 1
}

# ---------------------------------------------------------------- 依赖检查
MISSING_PY=()
while IFS= read -r mod; do
    [ -n "$mod" ] || continue
    if ! "$PYTHON" -c "import $mod" >/dev/null 2>&1; then
        MISSING_PY+=("$mod")
    fi
done <<'EOF'
PyQt5.QtWidgets
requests
qrcode
cryptography
psutil
EOF

if [ "${#MISSING_PY[@]}" -gt 0 ]; then
    echo "缺少 Python 依赖: ${MISSING_PY[*]}"
    echo "正在尝试安装 other/common/requirements.txt ..."
    if "$PYTHON" -m pip install -r "$PROJECT_ROOT/other/common/requirements.txt"; then
        echo "依赖安装完成。"
    else
        echo "依赖安装失败。请手动执行：" >&2
        echo "  $PYTHON -m pip install -r other/common/requirements.txt" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------- Qt 运行库
# PyQt5 的 xcb 平台插件依赖一组系统库；缺失时报错信息晦涩
# （"could not load the Qt platform plugin xcb"），这里提前探测并给出命令。
check_qt_libs() {
    local missing=()
    local lib
    for lib in libxcb-xinerama.so.0 libxcb-icccm.so.4 libxcb-image.so.0 \
               libxcb-keysyms.so.1 libxcb-randr.so.0 libxcb-render-util.so.0 \
               libxcb-shape.so.0 libxcb-xkb.so.1 libxkbcommon-x11.so.0 \
               libGL.so.1; do
        if ! ldconfig -p 2>/dev/null | grep -q "$lib"; then
            missing+=("$lib")
        fi
    done
    printf '%s\n' "${missing[@]:-}"
}

MISSING_LIBS="$(check_qt_libs | grep -v '^$' || true)"
if [ -n "$MISSING_LIBS" ] && [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    # 无图形环境（如 SSH / WSL 纯命令行）时无法运行 GUI，引导到 CLI 模式
    echo "检测到当前没有图形显示环境（DISPLAY/WAYLAND_DISPLAY 均未设置）。"
    echo "将改用命令行模式。若需图形界面，请配置 X11 转发或使用带桌面的环境。"
    FORCE_CLI=1
elif [ -n "$MISSING_LIBS" ]; then
    echo "警告：以下 Qt 依赖库可能缺失，界面可能无法启动："
    echo "  $MISSING_LIBS" | tr '\n' ' '
    echo
    echo "  修复命令（Debian/Ubuntu）："
    echo "    sudo apt install -y libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \\"
    echo "      libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \\"
    echo "      libxcb-xkb1 libxkbcommon-x11-0 libgl1 libegl1"
    echo "  修复命令（Fedora）："
    echo "    sudo dnf install -y xcb-util-wm xcb-util-image xcb-util-keysyms \\"
    echo "      xcb-util-renderutil libxkbcommon-x11 mesa-libGL"
    echo
fi

# ---------------------------------------------------------------- 环境变量
# B站是国内站点：清掉代理，避免用户开着代理导致请求失败或极慢
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy ALL_PROXY all_proxy 2>/dev/null || true
export NO_PROXY='*'
export no_proxy='*'

# 让中文正常输出（部分依赖会打印中文日志）
export PYTHONIOENCODING='utf-8'
export PYTHONUTF8='1'

# 高 DPI 缩放（Qt5 需要显式开启）
export QT_AUTO_SCREEN_SCALE_FACTOR="${QT_AUTO_SCREEN_SCALE_FACTOR:-1}"

# 以 root 运行时 Chromium 沙箱会拒绝启动，提示用户
if [ "$(id -u)" -eq 0 ] && [ "$NO_SANDBOX" -eq 0 ]; then
    echo "提示：当前以 root 运行。若内嵌浏览器（人机验证）崩溃，"
    echo "      请改用普通用户运行，或加 --no-sandbox。"
fi

# ---------------------------------------------------------------- 启动
if [ "$FORCE_CLI" -eq 1 ]; then
    exec "$PYTHON" "$PROJECT_ROOT/core/cli.py" "$@"
fi

if [ "$DEBUG" -eq 1 ]; then
    exec "$PYTHON" "$PROJECT_ROOT/main.py" "$@"
fi

# 正常启动：脱离终端，日志写入文件
exec "$PYTHON" "$PROJECT_ROOT/main.py" "$@" >/dev/null 2>&1
