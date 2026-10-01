#!/usr/bin/env bash
# ===========================================================================
# macOS 分发包构建脚本（必须在 macOS 上运行）
#
# 产出：
#   dist/B站视频解析工具.app                       应用包
#   dist/B站视频解析工具-<版本>-macOS-<arch>.dmg   分发镜像
#   dist/B站视频解析工具-<版本>-macOS-<arch>.zip   备用（保留权限位）
#
# 用法：
#   ./pack.sh              构建 .app + .dmg + .zip
#   ./pack.sh --no-dmg     只出 .app + .zip
#   ./pack.sh --arch arm64 指定架构（默认 universal2）
#
# 说明：产物未签名。首次打开需右键 → 打开，
#       或执行 xattr -cr "B站视频解析工具.app"。
# ===========================================================================
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VERSION="2.2.0"
APP_NAME="B站视频解析工具"

MAKE_DMG=1
ARCH=""
for arg in "$@"; do
    case "$arg" in
        --no-dmg) MAKE_DMG=0 ;;
        --arch) ARCH="${2:-}"; shift ;;
        -h|--help) sed -n '3,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

if [ "$(uname -s)" != "Darwin" ]; then
    echo "错误：本脚本必须在 macOS 上运行（当前 $(uname -s)）。" >&2
    echo "      PyInstaller 无法跨平台生成 .app。" >&2
    exit 1
fi

HOST_ARCH="$(uname -m)"
[ -n "$ARCH" ] || ARCH="$HOST_ARCH"

echo "=========================================="
echo " macOS 分发包构建"
echo "   版本   : $VERSION"
echo "   架构   : $ARCH"
echo "=========================================="
echo

# ---------------------------------------------------------------- 打包 .app
bash "$SCRIPT_DIR/build.sh" ${ARCH:+--arch "$ARCH"}

APP="$PROJECT_ROOT/dist/$APP_NAME.app"
[ -d "$APP" ] || { echo "打包失败：未生成 .app" >&2; exit 1; }

# 附上说明文件
cat > "$APP/Contents/Resources/启动说明.txt" <<'TXT'
B站视频解析工具 —— macOS 版
================================

【首次打开】
  本应用未做代码签名，macOS 会拦截。请任选一种：

  方式一：在「访达」中右键点击 App → 选择「打开」→ 再次点「打开」
  方式二：终端执行一次
          xattr -cr "/Applications/B站视频解析工具.app"

  之后即可正常双击启动。

【ffmpeg / mp4decrypt】
  本包未内置。首次运行时在「设置 → 工具」中一键下载，
  或安装系统版：
      brew install ffmpeg

【Apple Silicon / Intel】
  arm64 版用于 M 系列芯片，x86_64 版用于 Intel Mac。
  在 M 系列机器上运行 x86_64 版需要 Rosetta 2：
      softwareupdate --install-rosetta

【日志位置】
  ~/Library/Logs/BilibiliDownloadTool/
TXT

# ---------------------------------------------------------------- ZIP
echo
echo "生成 ZIP 分发包 ..."
ZIP="$PROJECT_ROOT/dist/${APP_NAME}-${VERSION}-macOS-${ARCH}.zip"
rm -f "$ZIP"
# 用 ditto 保留符号链接与可执行权限（zip 命令会破坏 .app 结构）
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
echo "  $ZIP ($(du -h "$ZIP" | cut -f1))"

# ---------------------------------------------------------------- DMG
if [ "$MAKE_DMG" -eq 1 ]; then
    DMG="$PROJECT_ROOT/dist/${APP_NAME}-${VERSION}-macOS-${ARCH}.dmg"
    echo
    echo "生成 DMG ..."
    rm -f "$DMG"

    if command -v create-dmg >/dev/null 2>&1; then
        create-dmg \
            --volname "$APP_NAME" \
            --window-size 640 400 \
            --icon-size 110 \
            --icon "$APP_NAME.app" 160 185 \
            --app-drop-link 480 185 \
            --no-internet-enable \
            "$DMG" "$APP" >/dev/null 2>&1 || true
    fi

    # create-dmg 不存在或失败时，退回 hdiutil
    if [ ! -f "$DMG" ]; then
        STAGE="$(mktemp -d)"
        cp -R "$APP" "$STAGE/"
        ln -s /Applications "$STAGE/Applications"
        hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" \
            -ov -format UDZO "$DMG" >/dev/null
        rm -rf "$STAGE"
    fi

    if [ -f "$DMG" ]; then
        echo "  $DMG ($(du -h "$DMG" | cut -f1))"
    else
        echo "  !! DMG 生成失败，请使用 ZIP 分发"
    fi
fi

# ---------------------------------------------------------------- 完成
echo
echo "=========================================="
echo " 构建完成"
echo "=========================================="
ls -lh "$PROJECT_ROOT/dist" | grep -vE '^total|BilibiliDownloader$' | tail -6
echo
echo " 验证方式："
echo "   open \"$APP\""
echo "=========================================="
