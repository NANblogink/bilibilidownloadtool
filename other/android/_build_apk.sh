#!/usr/bin/env bash
# ===========================================================================
# 构建 Android APK（在 WSL 里跑，绕过 Windows 中文路径导致的 javac 失败）
#
# 用法：
#   tr -d '\r' < .../other/android/_build_apk.sh > /tmp/bapk.sh
#   setsid nohup bash /tmp/bapk.sh > /tmp/bapk_run.log 2>&1 < /dev/null &
# ===========================================================================
set -euo pipefail

SRC="/mnt/e/旧桌面备份/来自：电脑桌面/B站视频解析工具V1.8"
STAGE="$HOME/bili_android_build"
AND="$SRC/other/android"

echo "=========================================="
echo " 同步源码到 ASCII 暂存区"
echo "=========================================="

mkdir -p "$STAGE"
if [ -d "$STAGE/.buildozer" ]; then
    find "$STAGE" -mindepth 1 -maxdepth 1 ! -name '.buildozer' -exec rm -rf {} + 2>/dev/null || true
fi

for item in core parsers; do
    cp -r "$SRC/$item" "$STAGE/"
    find "$STAGE/$item" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find "$STAGE/$item" -name '*.pyc' -delete 2>/dev/null || true
    rm -rf "$STAGE/$item/log" "$STAGE/$item/infra/log" 2>/dev/null || true
done

for f in _pathsetup.py app_config.py version_info.json; do
    [ -f "$SRC/$f" ] && cp "$SRC/$f" "$STAGE/"
done

# Android 入口 + Qt 兼容层（必须）
cp "$AND/main_kivy.py" "$STAGE/main.py"
cp "$AND/qt_compat.py" "$STAGE/qt_compat.py"
# 自带二维码生成器（必须）：APK 里没有 qrcode / Pillow，
# 扫码登录全靠这个纯 Python 实现，漏掉就会扫码闪退。
cp "$AND/qrgen.py" "$STAGE/qrgen.py"

# 中文字体（必须，否则乱码）
for f in NotoSansSC-Regular.ttf NotoSansSC-Bold.ttf; do
    [ -f "$AND/$f" ] || { echo "!! 缺少字体 $f" >&2; exit 1; }
    cp "$AND/$f" "$STAGE/$f"
done

# 图标：用户自己的 logo（logo.png / logo.ico 内容相同）
[ -f "$AND/icon.png" ] && cp "$AND/icon.png" "$STAGE/icon.png"
[ -f "$AND/logo_ui.png" ] && cp "$AND/logo_ui.png" "$STAGE/logo_ui.png"
[ -f "$SRC/logo.png" ] && cp "$SRC/logo.png" "$STAGE/logo.png"
[ -f "$SRC/logo.ico" ] && cp "$SRC/logo.ico" "$STAGE/logo.ico"

python3 - "$AND/buildozer.spec" "$STAGE/buildozer.spec" <<'PY'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
s = open(src, encoding='utf-8').read()
new = "source.include_patterns = core/*,parsers/*,_pathsetup.py,app_config.py,version_info.json,logo.png,logo.ico,*.ttf,*.png"
s = re.sub(r"source\.include_patterns\s*=.*", new, s, count=1)
if "ttf" not in s.split("source.include_exts")[1].split("\n")[0]:
    s = re.sub(r"(source\.include_exts\s*=\s*[^\n]+)", r"\1,ttf", s, count=1)
if "ico" not in s.split("source.include_exts")[1].split("\n")[0]:
    s = re.sub(r"(source\.include_exts\s*=\s*[^\n]+)", r"\1,ico", s, count=1)
open(dst, 'w', encoding='utf-8').write(s)
print("  spec 已适配")
for line in s.split("\n"):
    if line.split("=")[0].strip() in (
            "source.include_exts", "source.include_patterns",
            "orientation", "icon.filename", "android.skip_update"):
        print("   ", line.strip())
PY

echo
echo " 暂存区自检："
miss=0
for f in main.py qt_compat.py qrgen.py buildozer.spec icon.png logo.ico \
         NotoSansSC-Regular.ttf core/downloader.py core/utils.py \
         core/task_manager.py core/config.py core/download_history.py \
         core/tool_manager.py core/infra/platform_utils.py \
         core/infra/logger_config.py parsers/bilibili_parser.py _pathsetup.py; do
    if [ -f "$STAGE/$f" ]; then echo "   OK   $f"; else echo "   MISS $f" >&2; miss=$((miss+1)); fi
done
[ "$miss" -eq 0 ] || { echo "!! 缺 $miss 个必需文件" >&2; exit 1; }
echo

echo "=========================================="
echo " 链接构建缓存"
echo "=========================================="
CACHE="$HOME/.buildozer/android/platform"
DEST="$STAGE/.buildozer/android/platform"
mkdir -p "$DEST"
for name in python-for-android android-sdk android-ndk-r28c; do
    if [ -e "$CACHE/$name" ] && [ ! -e "$DEST/$name" ]; then
        ln -s "$CACHE/$name" "$DEST/$name"; echo "   链接 $name"
    fi
done
for d in "$CACHE"/build-*; do
    [ -e "$d" ] || continue
    n="$(basename "$d")"
    if [ ! -e "$DEST/$n" ]; then ln -s "$d" "$DEST/$n"; echo "   链接 $n"; fi
done
if [ -d "$DEST/python-for-android/.git" ]; then
    url="$(git -C "$DEST/python-for-android" remote get-url origin 2>/dev/null || echo '')"
    if [ "$url" != "https://github.com/kivy/python-for-android.git" ]; then
        git -C "$DEST/python-for-android" remote set-url origin \
            "https://github.com/kivy/python-for-android.git" 2>/dev/null || true
        echo "   已修正 p4a origin"
    fi
    echo "   p4a 就绪"
else
    echo "!! p4a 不可用" >&2
fi

echo
echo "=========================================="
echo " 开始构建"
echo "=========================================="
cd "$STAGE"

export PATH="$HOME/jdk17/bin:$HOME/.local/bin:$HOME/hosttools/root/usr/bin:/usr/local/bin:/usr/bin:/bin"
export JAVA_HOME="$HOME/jdk17"
export LANG=C.UTF-8 LC_ALL=C.UTF-8
export ANDROIDSDK="$HOME/.buildozer/android/platform/android-sdk"
export ANDROIDNDK="$(ls -d "$HOME"/.buildozer/android/platform/android-ndk-* 2>/dev/null | grep -v '\.zip$' | head -1)"
export ANDROIDAPI=33
export ANDROIDMINAPI=24
export GRADLE_OPTS="-Dorg.gradle.jvmargs=-Xmx2g"

LOG="$HOME/bz_build.log"
set +e
timeout 7200 python3 -m buildozer -v android debug > "$LOG" 2>&1
RC=$?
set -e

echo
echo "buildozer 退出码: $RC"
tail -25 "$LOG"

[ "$RC" -eq 0 ] || { echo "!! 构建失败，日志: $LOG" >&2; exit "$RC"; }

echo
APK=$(ls -1 "$STAGE"/bin/*.apk 2>/dev/null | head -1)
if [ -n "$APK" ]; then
    cp "$APK" "$AND/"
    echo " APK 已复制到 other/android/"
    ls -lh "$AND"/*.apk
    sha256sum "$APK"
else
    echo " 未找到 APK" >&2; exit 1
fi
