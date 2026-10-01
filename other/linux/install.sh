#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# B站视频解析工具 —— Linux 安装脚本
#
# 把程序安装到 ~/.local（默认，无需 root）或 /opt（用 --system）。
#
# 用法：
#   ./install.sh                 安装到 ~/.local/share/bilibili-downloader
#   ./install.sh --system        安装到 /opt/bilibili-downloader（需要 sudo）
#   ./install.sh --with-deps     同时安装系统 Qt 依赖（需要 sudo）
#   ./install.sh --uninstall     卸载
#
# 安装后会创建：
#   ~/.local/bin/bilibili-downloader      启动器
#   ~/.local/share/applications/*.desktop  应用菜单项
#   ~/.local/share/icons/hicolor/...       应用图标
# ---------------------------------------------------------------------------
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_NAME="bilibili-downloader"

MODE="user"
WITH_DEPS=0
UNINSTALL=0
for arg in "$@"; do
    case "$arg" in
        --system)     MODE="system" ;;
        --with-deps)  WITH_DEPS=1 ;;
        --uninstall)  UNINSTALL=1 ;;
        -h|--help)
            sed -n '3,18p' "$0" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

if [ "$MODE" = "system" ]; then
    PREFIX="/opt/$APP_NAME"
    BIN_DIR="/usr/local/bin"
    DESKTOP_DIR="/usr/share/applications"
    ICON_ROOT="/usr/share/icons/hicolor"
    NEED_SUDO=1
else
    PREFIX="$HOME/.local/share/$APP_NAME"
    BIN_DIR="$HOME/.local/bin"
    DESKTOP_DIR="$HOME/.local/share/applications"
    ICON_ROOT="$HOME/.local/share/icons/hicolor"
    NEED_SUDO=0
fi

as_root() {
    if [ "$NEED_SUDO" -eq 1 ]; then
        sudo "$@"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------- 卸载
if [ "$UNINSTALL" -eq 1 ]; then
    echo "正在卸载 $APP_NAME ..."
    as_root rm -rf "$PREFIX"
    as_root rm -f "$BIN_DIR/$APP_NAME"
    as_root rm -f "$DESKTOP_DIR/$APP_NAME.desktop"
    find "$ICON_ROOT" -name "$APP_NAME.png" -delete 2>/dev/null || true
    if command -v update-desktop-database >/dev/null 2>&1; then
        as_root update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        as_root gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true
    fi
    echo "卸载完成（用户配置与下载文件未删除）。"
    echo "  如需清理配置：rm -rf ~/.config/BilibiliDownloadTool"
    exit 0
fi

# ---------------------------------------------------------------- 系统依赖
if [ "$WITH_DEPS" -eq 1 ]; then
    echo "正在安装系统 Qt 依赖..."
    if command -v apt-get >/dev/null 2>&1; then
        sudo apt-get update
        sudo apt-get install -y \
            python3 python3-venv python3-pip \
            libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
            libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xkb1 \
            libxkbcommon-x11-0 libgl1 libegl1 libnss3 libasound2 \
            libnotify-bin ffmpeg
    elif command -v dnf >/dev/null 2>&1; then
        sudo dnf install -y python3 python3-pip \
            xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil \
            libxkbcommon-x11 mesa-libGL nss alsa-lib libnotify ffmpeg
    elif command -v pacman >/dev/null 2>&1; then
        sudo pacman -S --needed --noconfirm python python-pip \
            xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil \
            libxkbcommon-x11 mesa nss alsa-lib libnotify ffmpeg
    else
        echo "未识别的包管理器，请手动安装 Qt 运行库。" >&2
    fi
fi

# ---------------------------------------------------------------- 复制文件
echo "正在安装到 $PREFIX ..."
as_root mkdir -p "$PREFIX"

COPY_ITEMS=(core parsers assets other/common/requirements.txt)
for item in "${COPY_ITEMS[@]}"; do
    if [ -e "$PROJECT_ROOT/$item" ]; then
        as_root rm -rf "$PREFIX/$(basename "$item")" 2>/dev/null || true
        as_root cp -r "$PROJECT_ROOT/$item" "$PREFIX/"
    fi
done
for f in main.py ui.py boot.py _pathsetup.py app_config.py \
         logo.png warning_icon.png version_info.json README.md; do
    [ -e "$PROJECT_ROOT/$f" ] && as_root cp "$PROJECT_ROOT/$f" "$PREFIX/"
done

# 随包工具（若仓库里存在对应平台的二进制）
for d in ffmpeg bento4 mpv; do
    if [ -d "$PROJECT_ROOT/$d" ]; then
        as_root rm -rf "$PREFIX/$d"
        as_root cp -r "$PROJECT_ROOT/$d" "$PREFIX/"
    fi
done

# 清理 Windows 专有二进制（避免误当成 Linux 工具）
as_root find "$PREFIX/ffmpeg" "$PREFIX/bento4" -name '*.exe' -delete 2>/dev/null || true

# 保留启动脚本
as_root cp "$SCRIPT_DIR/run.sh" "$PREFIX/run.sh"
as_root chmod +x "$PREFIX/run.sh"

# ---------------------------------------------------------------- 启动器
as_root mkdir -p "$BIN_DIR"
cat > /tmp/${APP_NAME}.launcher <<EOF
#!/usr/bin/env bash
# 由 install.sh 生成，直接启动已安装的 $APP_NAME
exec "$PREFIX/run.sh" "\$@"
EOF
as_root install -m 0755 /tmp/${APP_NAME}.launcher "$BIN_DIR/$APP_NAME"
rm -f /tmp/${APP_NAME}.launcher

# ---------------------------------------------------------------- 图标 + 桌面项
if [ -f "$PROJECT_ROOT/logo.png" ]; then
    for size in 48 64 128 256 512; do
        dir="$ICON_ROOT/${size}x${size}/apps"
        if command -v convert >/dev/null 2>&1; then
            as_root mkdir -p "$dir"
            convert "$PROJECT_ROOT/logo.png" -resize ${size}x${size} "$dir/$APP_NAME.png" 2>/dev/null || true
        fi
    done
    # 没有 ImageMagick 时至少放一张原图
    as_root mkdir -p "$ICON_ROOT/256x256/apps"
    as_root cp -f "$PROJECT_ROOT/logo.png" "$ICON_ROOT/256x256/apps/$APP_NAME.png" 2>/dev/null || true
fi

as_root mkdir -p "$DESKTOP_DIR"
sed "s|^Exec=.*|Exec=$BIN_DIR/$APP_NAME %u|" \
    "$SCRIPT_DIR/$APP_NAME.desktop" > /tmp/${APP_NAME}.desktop
as_root install -m 0644 /tmp/${APP_NAME}.desktop "$DESKTOP_DIR/$APP_NAME.desktop"
rm -f /tmp/${APP_NAME}.desktop

command -v update-desktop-database >/dev/null 2>&1 && \
    as_root update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && \
    as_root gtk-update-icon-cache -f -t "$ICON_ROOT" 2>/dev/null || true

# ---------------------------------------------------------------- 完成
echo
echo "安装完成！"
echo "  程序目录 : $PREFIX"
echo "  启动命令 : $APP_NAME"
echo "  菜单项   : $DESKTOP_DIR/$APP_NAME.desktop"
echo
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        echo "提示：$BIN_DIR 不在 PATH 中，请把下面这行加入 ~/.bashrc 或 ~/.zshrc："
        echo "    export PATH=\"\$PATH:$BIN_DIR\""
        echo "  或直接运行：$PREFIX/run.sh"
        ;;
esac
echo
echo "首次运行如需 ffmpeg，可在程序内「设置 → 工具」中一键下载。"
