#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# B站视频解析工具 —— macOS 打包脚本
#
# 生成 dist/B站视频解析工具.app（含 .app bundle 与 Info.plist）
#
# 用法：
#   ./build.sh                 打包（默认 arm64+x86_64 通用二进制，若工具链支持）
#   ./build.sh --arch arm64    仅 arm64（Apple Silicon）
#   ./build.sh --arch x86_64   仅 Intel
#   ./build.sh --dmg           打包后再生成 .dmg 安装镜像
#
# 说明：生成未签名的 .app，首次打开需右键 → 打开，或执行
#       xattr -cr "dist/B站视频解析工具.app"
# ---------------------------------------------------------------------------
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SPEC="$SCRIPT_DIR/BilibiliDownloader.spec"

if [ "$(uname -s)" != "Darwin" ]; then
    echo "错误：本脚本必须在 macOS 上运行（当前为 $(uname -s)）。" >&2
    echo "      PyInstaller 无法跨平台生成 .app。" >&2
    exit 1
fi

ARCH=""
MAKE_DMG=0
for arg in "$@"; do
    case "$arg" in
        --arch) ARCH="${2:-}"; shift ;;
        --dmg)  MAKE_DMG=1 ;;
        -h|--help) sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

cd "$PROJECT_ROOT"

# ---------------------------------------------------------------- Python
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in "$PROJECT_ROOT/.venv/bin/python" \
                "$(command -v python3)" \
                "/opt/homebrew/bin/python3" \
                "/usr/local/bin/python3"; do
        if [ -n "${cand:-}" ] && [ -x "$cand" ]; then PYTHON="$cand"; break; fi
    done
fi
[ -n "$PYTHON" ] || { echo "未找到 Python 解释器" >&2; exit 1; }
echo "使用 Python: $PYTHON ($("$PYTHON" --version 2>&1))"

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
    echo "正在安装 PyInstaller ..."
    "$PYTHON" -m pip install --upgrade pyinstaller
fi

if ! "$PYTHON" -c "import PyQt5.QtWidgets" >/dev/null 2>&1; then
    echo "正在安装运行依赖 ..."
    "$PYTHON" -m pip install -r "$PROJECT_ROOT/other/common/requirements.txt"
fi

# ---------------------------------------------------------------- 图标
# macOS 需要 .icns。没有的话从 logo.png 现场生成。
ICNS="$PROJECT_ROOT/logo.icns"
if [ ! -f "$ICNS" ] && [ -f "$PROJECT_ROOT/logo.png" ]; then
    echo "正在从 logo.png 生成 logo.icns ..."
    TMPICON="$(mktemp -d)"
    mkdir -p "$TMPICON/logo.iconset"
    for size in 16 32 64 128 256 512; do
        sips -z $size $size "$PROJECT_ROOT/logo.png" \
            --out "$TMPICON/logo.iconset/icon_${size}x${size}.png" >/dev/null 2>&1 || true
        dbl=$((size * 2))
        sips -z $dbl $dbl "$PROJECT_ROOT/logo.png" \
            --out "$TMPICON/logo.iconset/icon_${size}x${size}@2x.png" >/dev/null 2>&1 || true
    done
    if iconutil -c icns "$TMPICON/logo.iconset" -o "$ICNS" 2>/dev/null; then
        echo "  logo.icns 生成成功"
    else
        echo "  icns 生成失败，将使用默认图标（不影响功能）"
        ICNS=""
    fi
    rm -rf "$TMPICON"
fi

# ---------------------------------------------------------------- 打包
echo
echo "开始打包 macOS .app ..."
rm -rf "$PROJECT_ROOT/build" "$PROJECT_ROOT/dist" 2>/dev/null || true

EXTRA=()
if [ -n "$ARCH" ]; then
    EXTRA+=(--target-arch "$ARCH")
fi

"$PYTHON" -m PyInstaller \
    --noconfirm \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build" \
    "${EXTRA[@]}" \
    "$SPEC"

APP="$PROJECT_ROOT/dist/B站视频解析工具.app"
if [ ! -d "$APP" ]; then
    echo "打包失败：未生成 .app" >&2
    exit 1
fi

# 去掉隔离属性，避免首次打开被 Gatekeeper 直接拦截
xattr -cr "$APP" 2>/dev/null || true

echo
echo "打包完成：$APP"
echo "运行：open \"$APP\""
echo "提示：首次打开请右键 → 打开；若提示已损坏，执行："
echo "      xattr -cr \"$APP\""

# ---------------------------------------------------------------- DMG
if [ "$MAKE_DMG" -eq 1 ]; then
    DMG="$PROJECT_ROOT/dist/B站视频解析工具-2.2.0.dmg"
    echo
    echo "正在生成 DMG ..."
    rm -f "$DMG"
    if command -v create-dmg >/dev/null 2>&1; then
        create-dmg \
            --volname "B站视频解析工具" \
            --window-size 600 400 \
            --icon-size 100 \
            --app-drop-link 450 185 \
            "$DMG" "$APP" || true
    else
        hdiutil create -volname "B站视频解析工具" -srcfolder "$APP" \
            -ov -format UDZO "$DMG"
    fi
    if [ -f "$DMG" ]; then
        echo "DMG 已生成：$DMG"
    fi
fi

echo
echo "注意：打包产物默认不含 ffmpeg / mp4decrypt。"
echo "      可执行 brew install ffmpeg，或在程序内「设置 → 工具」一键下载。"
