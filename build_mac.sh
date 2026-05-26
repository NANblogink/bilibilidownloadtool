#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VERSION="2.0.2"
APP_NAME="BilibiliDownloader"
DIST_DIR="$SCRIPT_DIR/dist"
BUILD_DIR="$SCRIPT_DIR/build"
DMG_NAME="${APP_NAME}_macOS_v${VERSION}.dmg"

echo "=========================================="
echo "  B站视频解析工具 macOS 打包脚本"
echo "  版本: ${VERSION}"
echo "=========================================="

if [[ "$(uname)" != "Darwin" ]]; then
    echo "错误: 此脚本只能在 macOS 上运行"
    exit 1
fi

echo ""
echo "[1/6] 检查依赖..."
python3 -c "import PyQt5" 2>/dev/null || { echo "安装 PyQt5..."; pip3 install PyQt5 PyQtWebEngine; }
python3 -c "import PyInstaller" 2>/dev/null || { echo "安装 PyInstaller..."; pip3 install pyinstaller; }
python3 -c "import requests" 2>/dev/null || { echo "安装 requests..."; pip3 install requests; }
python3 -c "import Cryptodome" 2>/dev/null || { echo "安装 pycryptodome..."; pip3 install pycryptodome; }

echo ""
echo "[2/6] 清理旧构建..."
rm -rf "$BUILD_DIR" "$DIST_DIR"

echo ""
echo "[3/6] PyInstaller 打包..."
pyinstaller BilibiliDownloader.spec \
    --clean \
    --noconfirm \
    --distpath "$DIST_DIR" \
    --workpath "$BUILD_DIR"

APP_PATH="$DIST_DIR/${APP_NAME}.app"
if [ ! -d "$APP_PATH" ]; then
    echo "错误: .app 未生成"
    exit 1
fi
echo "  .app 生成成功: $APP_PATH"

echo ""
echo "[4/6] 复制资源到 .app/Contents/MacOS/..."
APP_MACOS="$APP_PATH/Contents/MacOS"

if command -v ffmpeg &> /dev/null; then
    FFMPEG_PATH="$(which ffmpeg)"
    echo "  复制 ffmpeg: $FFMPEG_PATH"
    mkdir -p "$APP_MACOS/ffmpeg/bin"
    cp "$FFMPEG_PATH" "$APP_MACOS/ffmpeg/bin/"
    if [ -f "$(dirname "$FFMPEG_PATH")/ffprobe" ]; then
        cp "$(dirname "$FFMPEG_PATH")/ffprobe" "$APP_MACOS/ffmpeg/bin/"
    fi
fi

if command -v mp4decrypt &> /dev/null; then
    MP4DECRYPT_PATH="$(which mp4decrypt)"
    echo "  复制 mp4decrypt: $MP4DECRYPT_PATH"
    mkdir -p "$APP_MACOS/bento4/bin"
    cp "$MP4DECRYPT_PATH" "$APP_MACOS/bento4/bin/"
fi

echo ""
echo "[5/6] 创建 DMG..."
DMG_PATH="$DIST_DIR/$DMG_NAME"
rm -f "$DMG_PATH"

hdiutil create -volname "$APP_NAME" \
    -srcfolder "$APP_PATH" \
    -ov -format UDZO \
    "$DMG_PATH"

if [ ! -f "$DMG_PATH" ]; then
    echo "警告: DMG 创建失败，尝试创建 ZIP 替代..."
    cd "$DIST_DIR"
    zip -r "${APP_NAME}_macOS_v${VERSION}.zip" "$(basename "$APP_PATH")"
    cd "$SCRIPT_DIR"
    echo "  ZIP 创建成功: $DIST_DIR/${APP_NAME}_macOS_v${VERSION}.zip"
else
    DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)
    echo "  DMG 创建成功: $DMG_PATH ($DMG_SIZE)"
fi

echo ""
echo "[6/6] 计算文件哈希..."
if [ -f "$DMG_PATH" ]; then
    shasum -a 256 "$DMG_PATH" | cut -d' ' -f1 > "${DMG_PATH}.sha256"
    echo "  SHA256: $(cat "${DMG_PATH}.sha256")"
fi

echo ""
echo "=========================================="
echo "  打包完成！"
echo "=========================================="
echo "  输出目录: $DIST_DIR"
ls -la "$DIST_DIR/"
