#!/usr/bin/env bash
# ===========================================================================
# Linux 分发包构建脚本（在 Linux 主机上运行）
#
# 产出：
#   dist/BilibiliDownloader/            可直接运行的目录（绿色版）
#   dist/BilibiliDownloader-linux-x86_64.tar.gz   分发包
#
# 用法：
#   ./pack.sh                构建
#   ./pack.sh --skip-tests   跳过打包后的自检
# ===========================================================================
set -eu

# 允许通过环境变量指定项目根（脚本被复制到 /tmp 执行时 SPECPATH 会失效）
if [ -n "${BILI_PROJECT_ROOT:-}" ]; then
    PROJECT_ROOT="$BILI_PROJECT_ROOT"
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi
SPEC="$PROJECT_ROOT/other/linux/BilibiliDownloader.spec"

# 校验项目根找对了（PyInstaller 的 SPECPATH 依赖真实路径）
if [ ! -f "$PROJECT_ROOT/main.py" ] || [ ! -d "$PROJECT_ROOT/core" ]; then
    echo "错误：项目根识别失败 -> $PROJECT_ROOT" >&2
    echo "      请用 BILI_PROJECT_ROOT=/path/to/project 显式指定。" >&2
    exit 1
fi

SKIP_TESTS=0
for arg in "$@"; do
    case "$arg" in
        --skip-tests) SKIP_TESTS=1 ;;
        -h|--help) sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

cd "$PROJECT_ROOT"

# ---------------------------------------------------------------- Python
PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
    for cand in "$PROJECT_ROOT/.venv/bin/python" "$(command -v python3)"; do
        if [ -n "${cand:-}" ] && [ -x "$cand" ]; then PYTHON="$cand"; break; fi
    done
fi
[ -n "$PYTHON" ] || { echo "未找到 Python 解释器" >&2; exit 1; }

ARCH="$(uname -m)"
echo "=========================================="
echo " Linux 分发包构建"
echo "   Python : $PYTHON ($("$PYTHON" --version 2>&1))"
echo "   架构   : $ARCH"
echo "=========================================="
echo

# ---------------------------------------------------------------- 依赖
"$PYTHON" -c "import PyInstaller" >/dev/null 2>&1 || {
    echo "安装 PyInstaller ..."
    "$PYTHON" -m pip install --upgrade pyinstaller
}
"$PYTHON" -c "import PyQt5.QtWidgets" >/dev/null 2>&1 || {
    echo "安装运行依赖 ..."
    "$PYTHON" -m pip install -r "$PROJECT_ROOT/other/common/requirements.txt"
}

# ---------------------------------------------------------------- 打包
echo "清理旧产物 ..."
rm -rf "$PROJECT_ROOT/build" "$PROJECT_ROOT/dist" 2>/dev/null || true

echo
echo "PyInstaller 打包中（可能需要几分钟）..."
"$PYTHON" -m PyInstaller \
    --noconfirm --log-level WARN \
    --distpath "$PROJECT_ROOT/dist" \
    --workpath "$PROJECT_ROOT/build" \
    "$SPEC" 2>&1 | tail -5

APP_DIR="$PROJECT_ROOT/dist/BilibiliDownloader"
[ -d "$APP_DIR" ] || { echo "打包失败：未生成 $APP_DIR" >&2; exit 1; }

# 可执行位
chmod +x "$APP_DIR/BilibiliDownloader" 2>/dev/null || true

# 附上启动说明与启动脚本，方便用户直接解压运行
cp "$PROJECT_ROOT/other/linux/run.sh" "$APP_DIR/run.sh" 2>/dev/null || true
chmod +x "$APP_DIR/run.sh" 2>/dev/null || true

cat > "$APP_DIR/启动说明.txt" <<'TXT'
B站视频解析工具 —— Linux 版
================================

【直接运行】
    ./BilibiliDownloader
  或
    ./run.sh

【缺失依赖时】
  若提示 Qt 平台插件加载失败，请安装系统库：

  Debian / Ubuntu:
    sudo apt install -y libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
      libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
      libxcb-xkb1 libxkbcommon-x11-0 libgl1 libegl1 libnss3

  Fedora:
    sudo dnf install -y xcb-util-wm xcb-util-image xcb-util-keysyms \
      xcb-util-renderutil libxkbcommon-x11 mesa-libGL nss

【ffmpeg / mp4decrypt】
  本包未内置（体积大且架构相关）。首次运行时在
  「设置 → 工具」中一键下载，或安装系统版：
    sudo apt install ffmpeg          # Debian/Ubuntu
    sudo dnf install ffmpeg          # Fedora

【桌面快捷方式（可选）】
    ./install.sh

【无声音/无通知提示】
    sudo apt install libnotify-bin
TXT

# 顺带放一份安装脚本（要在源码树里才能用，这里只作参考）
cp "$PROJECT_ROOT/other/linux/install.sh" "$APP_DIR/install.sh" 2>/dev/null || true
chmod +x "$APP_DIR/install.sh" 2>/dev/null || true

# ---------------------------------------------------------------- 自检
if [ "$SKIP_TESTS" -eq 0 ]; then
    echo
    echo "打包后自检（offscreen 启动 + 看门狗自动退出）..."
    export QT_QPA_PLATFORM=offscreen
    export PYTHONIOENCODING=utf-8

    # 用 sitecustomize 注入看门狗，N 秒后自动 quit，避免自检永久挂住。
    # 放在 ASCII 路径下，避免非 ASCII 路径导致的加载问题。
    WD="/tmp/pack_autoclose"
    rm -rf "$WD"; mkdir -p "$WD"
    cat > "$WD/sitecustomize.py" <<'PY'
import os
try:
    _secs = float(os.environ.get("BILI_AUTOCLOSE_SECONDS", "0"))
except Exception:
    _secs = 0.0
if _secs > 0:
    import threading, time
    def _wd():
        time.sleep(_secs)
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if app is not None:
                app.quit()
        except Exception:
            pass
    threading.Thread(target=_wd, daemon=True).start()
PY

    # 用 timeout 兜底：即使看门狗失效也不会卡住构建。
    # 在临时目录里跑，避免把 log/、cookie 等运行期文件写进待打包目录。
    RUNDIR="$(mktemp -d)"
    cp -a "$APP_DIR/." "$RUNDIR/"
    ( cd "$RUNDIR" && \
      PYTHONPATH="$WD" BILI_AUTOCLOSE_SECONDS=8 \
      timeout -s KILL 90 ./BilibiliDownloader >/tmp/pack_smoke.log 2>&1 ) || true
    rm -rf "$RUNDIR"

    if grep -qiE 'traceback|ModuleNotFoundError|ImportError' /tmp/pack_smoke.log; then
        echo "  !! 启动日志中存在错误："
        grep -iE 'traceback|ModuleNotFoundError|ImportError' /tmp/pack_smoke.log | head -5
        echo "  （构建产物可能不可用，请检查）"
    else
        echo "  启动无导入错误 OK"
    fi
    echo "  日志尾部："
    tail -3 /tmp/pack_smoke.log 2>/dev/null | sed 's/^/    /'
fi

# ---------------------------------------------------------------- 压缩
echo
echo "生成 tar.gz 分发包 ..."

# 清理自检与运行期产生的文件，保证分发包干净
# （cookie/缓存/日志/临时文件不应进入用户拿到的包里）
rm -rf "$APP_DIR/log" "$APP_DIR/temp" 2>/dev/null || true
rm -f "$APP_DIR/cookie.txt" \
      "$APP_DIR/client_id.txt" \
      "$APP_DIR/wbi_cache.json" \
      "$APP_DIR/data_consent.json" \
      "$APP_DIR/download_history.json" 2>/dev/null || true
find "$APP_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
find "$APP_DIR" -name '*.pyc' -delete 2>/dev/null || true

OUT="$PROJECT_ROOT/dist/BilibiliDownloader-linux-${ARCH}.tar.gz"
rm -f "$OUT"
# 先把目录复制成稳定快照再压缩，彻底避免 "file changed as we read it"
SNAP="$(mktemp -d)"
cp -a "$APP_DIR" "$SNAP/BilibiliDownloader"
# 兜底：快照里再清一次运行期文件（自检过程中可能被重新创建）
rm -rf "$SNAP/BilibiliDownloader/log" "$SNAP/BilibiliDownloader/temp" 2>/dev/null || true
rm -f "$SNAP/BilibiliDownloader/cookie.txt" \
      "$SNAP/BilibiliDownloader/client_id.txt" \
      "$SNAP/BilibiliDownloader/wbi_cache.json" \
      "$SNAP/BilibiliDownloader/data_consent.json" \
      "$SNAP/BilibiliDownloader/download_history.json" 2>/dev/null || true
tar -C "$SNAP" -czf "$OUT" BilibiliDownloader
rm -rf "$SNAP"

SIZE="$(du -h "$OUT" | cut -f1)"
echo
echo "=========================================="
echo " 构建完成"
echo "=========================================="
echo " 目录版 : $APP_DIR"
echo " 分发包 : $OUT  ($SIZE)"
echo
echo " 用户使用："
echo "   tar -xzf $(basename "$OUT")"
echo "   cd BilibiliDownloader && ./BilibiliDownloader"
echo "=========================================="
