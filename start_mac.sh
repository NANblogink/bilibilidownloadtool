#!/bin/bash
# B站视频解析工具 macOS 启动脚本

echo "=== B站视频解析工具 macOS 启动 ==="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 Python3
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到 python3，请先安装 Python3"
    echo "建议使用 Homebrew 安装: brew install python3"
    exit 1
fi

# 检查并安装依赖
echo "检查依赖..."
pip3 install -q PyQt5 requests aiohttp pycryptodome brotli orjson qrcode Pillow browser-cookie3 2>/dev/null

# 检查 PyQt5 WebEngine
pip3 install -q PyQtWebEngine 2>/dev/null

# 检查 FFmpeg
if ! command -v ffmpeg &> /dev/null; then
    echo "警告: 未找到 FFmpeg"
    echo "建议安装: brew install ffmpeg"
    echo ""
fi

# 检查 Bento4
if ! command -v mp4decrypt &> /dev/null; then
    if [ ! -f "$SCRIPT_DIR/bento4/bin/mp4decrypt" ]; then
        echo "警告: 未找到 mp4decrypt (Bento4)"
        echo "建议安装: brew install bento4"
        echo ""
    fi
fi

# 启动程序
echo "正在启动程序..."
python3 main.py
