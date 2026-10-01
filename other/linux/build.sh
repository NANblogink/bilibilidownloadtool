#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# B站视频解析工具 —— Linux / macOS 打包脚本（PyInstaller）
#
# 用法：
#   ./build.sh                 打包为目录形式（推荐，启动快）
#   ./build.sh --onefile       打包为单个可执行文件
#   ./build.sh --clean         打包前清理旧产物
#
# 产物：
#   Linux  : dist/BilibiliDownloader/BilibiliDownloader
#   macOS  : dist/B站视频解析工具.app
# ---------------------------------------------------------------------------
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPEC="$SCRIPT_DIR/BilibiliDownloader.spec"

ONEFILE=0
CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --onefile) ONEFILE=1 ;;
        --clean)   CLEAN=1 ;;
        -h|--help) sed -n '3,14p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

cd "$PROJECT_ROOT"

# ---------------------------------------------------------------- Python
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in "$PROJECT_ROOT/.venv/bin/python" "$(command -v python3)" "$(command -v python)"; do
        if [ -n "${cand:-}" ] && [ -x "$cand" ]; then PYTHON="$cand"; break; fi
    done
fi
[ -n "$PYTHON" ] || { echo "未找到 Python 解释器" >&2; exit 1; }
echo "使用 Python: $PYTHON ($("$PYTHON" --version 2>&1))"

# ---------------------------------------------------------------- 依赖
if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "正在安装 PyInstaller ..."
    "$PYTHON" -m pip install --upgrade pyinstaller
fi

if ! "$PYTHON" -c "import PyQt5.QtWidgets" >/dev/null 2>&1; then
    echo "正在安装运行依赖 ..."
    "$PYTHON" -m pip install -r "$PROJECT_ROOT/other/common/requirements.txt"
fi

# ---------------------------------------------------------------- 清理
if [ "$CLEAN" -eq 1 ]; then
    echo "清理旧产物 ..."
    rm -rf "$PROJECT_ROOT/build" "$PROJECT_ROOT/dist" "$PROJECT_ROOT"/*.spec.bak 2>/dev/null || true
fi

# ---------------------------------------------------------------- 打包
echo
echo "开始打包 $(uname -s) ..."
EXTRA=()
if [ "$ONEFILE" -eq 1 ]; then
    EXTRA+=(--onefile)
fi

"$PYTHON" -m PyInstaller \
    --noconfirm \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build" \
    "${EXTRA[@]}" \
    "$SPEC"

# ---------------------------------------------------------------- 收尾
echo
echo "打包完成。产物："
if [ "$(uname -s)" = "Darwin" ]; then
    APP="$PROJECT_ROOT/dist/B站视频解析工具.app"
    if [ -d "$APP" ]; then
        # 去掉隔离属性，避免首次打开被 Gatekeeper 拦截
        xattr -cr "$APP" 2>/dev/null || true
        echo "  $APP"
        echo
        echo "运行：open \"$APP\""
        echo "提示：首次打开如提示未验证开发者，请右键 → 打开，或执行"
        echo "      xattr -cr \"$APP\""
    fi
else
    BIN="$PROJECT_ROOT/dist/BilibiliDownloader/BilibiliDownloader"
    if [ -f "$BIN" ]; then
        chmod +x "$BIN" 2>/dev/null || true
        echo "  $BIN"
        echo
        echo "运行：$BIN"
    fi
fi

echo
echo "注意：打包产物默认不含 ffmpeg / mp4decrypt。"
echo "      请把它们放到产物目录下的 ffmpeg/bin、bento4/bin，"
echo "      或在程序内「设置 → 工具」中一键下载。"
