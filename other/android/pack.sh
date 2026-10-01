#!/usr/bin/env bash
# ===========================================================================
# Android APK 打包脚本（必须在 Linux 上运行；buildozer 不支持 Windows/macOS 原生）
#
# 背景
# ====
# buildozer 的 source.dir 不能包含其自身目录之外的文件，所以无法直接用
# "../../core" 这种方式把桌面版核心代码纳入 APK。
#
# 本脚本的做法：先把 other/android/ 与桌面版核心代码**复制到一个临时暂存目录**
# （保持 main_kivy.py 能 import parsers/core 的目录结构），再在该目录里跑
# buildozer。这样既不污染源码树，也不需要把核心代码复制进仓库。
#
# 用法：
#   ./pack.sh              构建 debug APK
#   ./pack.sh --release    构建 release APK（未签名，需自行用 apksigner 签）
#   ./pack.sh --clean      构建前清理暂存目录
#
# 依赖（Ubuntu/Debian）：
#   sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
#       autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
#       cmake libffi-dev libssl-dev build-essential ccache
#   pip install --user buildozer cython
#
# 首次构建会自动下载 Android SDK/NDK（数 GB），耗时较长。
# ===========================================================================
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "${BILI_PROJECT_ROOT:-}" ]; then
    PROJECT_ROOT="$BILI_PROJECT_ROOT"
else
    PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
fi

[ -f "$PROJECT_ROOT/main.py" ] || {
    echo "错误：项目根识别失败 -> $PROJECT_ROOT" >&2
    echo "      请用 BILI_PROJECT_ROOT=/path/to/project 显式指定。" >&2
    exit 1
}

MODE="debug"
CLEAN=0
for arg in "$@"; do
    case "$arg" in
        --release) MODE="release" ;;
        --clean)   CLEAN=1 ;;
        -h|--help) sed -n '3,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "未知参数: $arg" >&2; exit 2 ;;
    esac
done

if [ "$(uname -s)" != "Linux" ]; then
    echo "错误：buildozer 只能在 Linux 上打包 APK（当前 $(uname -s)）。" >&2
    echo "      Windows 用户请用 WSL 或 Docker。macOS 请用虚拟机/容器。" >&2
    exit 1
fi

STAGE="$PROJECT_ROOT/other/android/.build_stage"

echo "=========================================="
echo " Android APK 构建"
echo "   项目根 : $PROJECT_ROOT"
echo "   模式   : $MODE"
echo "   暂存区 : $STAGE"
echo "=========================================="
echo

# ---------------------------------------------------------------- 暂存
# .buildozer/ 里放着 Android SDK/NDK、python-for-android 与已下载的源码包
# （合计数 GB）。每次重建都删掉会重复下载数小时。
#
# 这里**不做跨文件系统 mv**（/mnt/e 与 /tmp 之间移动数 GB 会卡住十几分钟），
# 而是把缓存留在原地，仅清空暂存目录里的源码副本。
BD_CACHE="$STAGE/.buildozer"

if [ "$CLEAN" -eq 1 ]; then
    echo "清理暂存区（--clean：含 SDK 缓存）..."
    rm -rf "$STAGE"
    mkdir -p "$STAGE"
else
    # 保留 .buildozer：先把整个 stage 移开再重建，代价是重命名而非拷贝。
    # 为避免大目录搬运，改为就地删除其余内容。
    if [ -d "$STAGE" ]; then
        find "$STAGE" -mindepth 1 -maxdepth 1 ! -name '.buildozer' -exec rm -rf {} + 2>/dev/null || true
    else
        mkdir -p "$STAGE"
    fi
    [ -d "$BD_CACHE" ] && echo "已保留 .buildozer 缓存（SDK/NDK/python-for-android/源码包）"
fi
mkdir -p "$STAGE"

echo "复制桌面版核心代码到暂存区 ..."
# 业务层（与桌面版同源，保证功能一致）
for item in core parsers; do
    cp -r "$PROJECT_ROOT/$item" "$STAGE/"
    # 去掉缓存与日志，减小 APK 体积
    find "$STAGE/$item" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
    find "$STAGE/$item" -name '*.pyc' -delete 2>/dev/null || true
    rm -rf "$STAGE/$item/log" "$STAGE/$item/infra/log" 2>/dev/null || true
done

# 顶层辅助模块
for f in _pathsetup.py app_config.py version_info.json; do
    [ -f "$PROJECT_ROOT/$f" ] && cp "$PROJECT_ROOT/$f" "$STAGE/"
done

# 图标
[ -f "$PROJECT_ROOT/logo.png" ] && cp "$PROJECT_ROOT/logo.png" "$STAGE/"

# Android 自己的入口、Qt 兼容层与中文字体放到暂存区根目录
#
# qt_compat.py 必须一起打包：桌面版 core/downloader.py 与 core/utils.py
# 顶层 import PyQt5，而 Android 没有 PyQt5；入口脚本在导入核心模块之前
# 会先安装这个影子包。漏掉它 → 启动即 ImportError。
cp "$SCRIPT_DIR/qt_compat.py" "$STAGE/qt_compat.py"

# 中文字体必须随包：Kivy 默认字体不含汉字，缺了界面全是方块（乱码）
for f in NotoSansSC-Regular.ttf NotoSansSC-Bold.ttf; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$STAGE/$f"
    else
        echo "!! 警告：缺少中文字体 $f，界面中文会显示为方块" >&2
        echo "         请先在本目录运行：python make_font.py" >&2
    fi
done

# 界面用的小图标（标题栏）
[ -f "$SCRIPT_DIR/logo_ui.png" ] && cp "$SCRIPT_DIR/logo_ui.png" "$STAGE/logo_ui.png"

# 启动图标源图（spec 的 icon.filename 指向它）
if [ -f "$SCRIPT_DIR/icon.png" ]; then
    cp "$SCRIPT_DIR/icon.png" "$STAGE/icon.png"
elif [ -f "$PROJECT_ROOT/logo.png" ]; then
    # 没生成过就退回项目 logo，至少不会用 Kivy 默认图标
    cp "$PROJECT_ROOT/logo.png" "$STAGE/icon.png"
    echo "!! 提示：未找到 other/android/icon.png，改用项目 logo.png 作为启动图标" >&2
    echo "         （建议先运行 python make_icon.py 生成标准图标）" >&2
fi

cp "$SCRIPT_DIR/main_kivy.py" "$STAGE/main.py"
cp "$SCRIPT_DIR/buildozer.spec" "$STAGE/buildozer.spec"

# 重写 spec 里的 source 配置以适配暂存区布局
python3 - "$STAGE/buildozer.spec" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
# 暂存区里 core/parsers 就在同级目录，不需要 ../../ 前缀
s = s.replace(
    "source.include_patterns = ../../core/*,../../parsers/*,../../assets/*,../../_pathsetup.py,*.ttf,*.png",
    "source.include_patterns = core/*,parsers/*,_pathsetup.py,app_config.py,version_info.json,logo.png,*.ttf,*.png")
s = s.replace(
    "source.include_patterns = ../../core/*,../../parsers/*,../../assets/*,../../_pathsetup.py",
    "source.include_patterns = core/*,parsers/*,_pathsetup.py,app_config.py,version_info.json,logo.png,*.ttf,*.png")
if "*.ttf" not in s.split("source.include_patterns")[1].split("\n")[0]:
    # 老版本 spec 没有 ttf，补上（否则中文字体进不了 APK）
    s = re.sub(r"(source\.include_patterns\s*=\s*[^\n]+)",
               r"\1,*.ttf,*.png", s, count=1)
if "ttf" not in s.split("source.include_exts")[1].split("\n")[0]:
    s = re.sub(r"(source\.include_exts\s*=\s*[^\n]+)", r"\1,ttf", s, count=1)
s = s.replace("source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt",
              "source.include_exts = py,png,jpg,jpeg,kv,atlas,json,txt,ico,ttf")
open(p, 'w', encoding='utf-8').write(s)
print("  buildozer.spec 已适配暂存区布局")
print("    include_exts     =", [l for l in s.split("\n") if l.startswith("source.include_exts")][0].split("=",1)[1].strip())
print("    include_patterns =", [l for l in s.split("\n") if l.startswith("source.include_patterns")][0].split("=",1)[1].strip())
PY

# ---------------------------------------------------------------- 打包前自检
# 缺文件时构建会在 40 分钟后才失败（甚至成功但运行时崩），
# 所以这里先把关键文件确认一遍。
echo "  打包前自检："
_missing=0
for f in main.py qt_compat.py buildozer.spec core/downloader.py \
         parsers/bilibili_parser.py core/infra/platform_utils.py \
         NotoSansSC-Regular.ttf icon.png; do
    if [ -f "$STAGE/$f" ]; then
        echo "    OK   $f"
    else
        echo "    MISS $f" >&2
        _missing=$((_missing + 1))
    fi
done
if [ "$_missing" -ne 0 ]; then
    echo "!! 有 $_missing 个必需文件缺失，终止构建。" >&2
    exit 1
fi
echo

echo "  暂存区内容："
ls "$STAGE" | sed 's/^/    /'
echo

# ---------------------------------------------------------------- 环境检查
command -v buildozer >/dev/null 2>&1 || {
    echo "未找到 buildozer，正在安装 ..." >&2
    python3 -m pip install --user --upgrade buildozer cython
    export PATH="$HOME/.local/bin:$PATH"
    command -v buildozer >/dev/null 2>&1 || {
        echo "buildozer 安装失败，请手动执行：pip install --user buildozer cython" >&2
        exit 1
    }
}
echo "buildozer: $(command -v buildozer)"

# ---------------------------------------------------------------- JDK 信任库
# 若 JDK 是用「解包 deb」方式装的（无 root，没跑 ca-certificates-java），
# 它的 cacerts 会指向不存在的 /etc/ssl/certs/java/cacerts，导致
# sdkmanager 报 "trustAnchors parameter must be non-empty"。
# 通过 JAVA_TOOL_OPTIONS 显式指定信任库（sdkmanager 无法传 -D 参数）。
JAVA_BIN="$(command -v java || true)"
JDK_HOME="${JAVA_HOME:-}"
if [ -n "$JAVA_BIN" ] && [ -z "$JDK_HOME" ]; then
    JDK_HOME="$(dirname "$(dirname "$(readlink -f "$JAVA_BIN")")")"
fi
CACERTS="$JDK_HOME/lib/security/cacerts"
if [ -f "$CACERTS" ] && [ ! -s "$CACERTS" ]; then
    echo "!! 警告：$CACERTS 为空，sdkmanager 可能无法下载 SDK。" >&2
elif [ -f "$CACERTS" ]; then
    export JAVA_TOOL_OPTIONS="-Djavax.net.ssl.trustStore=$CACERTS -Djavax.net.ssl.trustStorePassword=changeit -Djavax.net.ssl.trustStoreType=JKS ${JAVA_TOOL_OPTIONS:-}"
    echo "JAVA_TOOL_OPTIONS 已设置信任库：$CACERTS"
fi

# ---------------------------------------------------------------- GitHub 镜像
# buildozer 需要从 GitHub 克隆 python-for-android。国内网络常常不可达，
# 若发现官方地址不通，则预先把仓库放到 **buildozer 实际使用的目录**。
#
# 注意：buildozer 把平台代码放在 <app_dir>/.buildozer/android/platform/，
# 而不是 $HOME/.buildozer/。之前只克隆到了 $HOME 下，buildozer 仍然
# 去 GitHub 克隆并卡死，所以这里两个位置都要放。
P4A_MIRROR="${P4A_MIRROR:-https://gitee.com/mirrors/python-for-android.git}"
P4A_GITHUB="https://github.com/kivy/python-for-android.git"
STAGE_P4A="$STAGE/.buildozer/android/platform/python-for-android"
HOME_P4A="$HOME/.buildozer/android/platform/python-for-android"

# 关键：buildozer 会执行 `git config --get remote.origin.url`，
# 只要地址不是它期望的 GitHub 地址，就会「Detected old url/branch ... deleting」
# 并删掉整个目录重新克隆，于是又卡在 GitHub 上。
# 所以用镜像加速克隆后，必须把 origin 改回 GitHub 地址。
seed_p4a() {
    local dest="$1"
    if [ -d "$dest/.git" ]; then
        # 已存在：确保 origin 指向 GitHub，避免被 buildozer 判定为旧地址
        git -C "$dest" remote set-url origin "$P4A_GITHUB" 2>/dev/null || true
        echo "  已就位: $dest"
        return 0
    fi
    mkdir -p "$(dirname "$dest")"
    rm -rf "$dest"
    echo "  从镜像克隆到 $dest ..."
    if ! timeout 1200 git clone --depth 1 -b master "$P4A_MIRROR" "$dest" >/dev/null 2>&1; then
        echo "  !! 克隆失败: $dest" >&2
        return 1
    fi
    # 改回 GitHub 地址（对象已在本地，后续无需访问 GitHub）
    git -C "$dest" remote set-url origin "$P4A_GITHUB" 2>/dev/null || true
    echo "    origin -> $(git -C "$dest" remote get-url origin 2>/dev/null)"
    return 0
}

# 判断是否已有可用克隆（origin 必须是 GitHub 地址）
p4a_ready() {
    [ -d "$1/.git" ] || return 1
    local url
    url="$(git -C "$1" remote get-url origin 2>/dev/null || echo '')"
    [ "$url" = "$P4A_GITHUB" ]
}

if p4a_ready "$HOME_P4A"; then
    echo "python-for-android 已就位（镜像克隆，origin 已指向 GitHub）"
else
    echo "准备 python-for-android（使用镜像：$P4A_MIRROR）"
    seed_p4a "$HOME_P4A" || echo "!! 预置失败，构建可能因无法访问 GitHub 而中断" >&2
    seed_p4a "$STAGE_P4A" || true
fi

# 二次确认：buildozer 只认 GitHub 地址，这里再兜底一次，
# 避免上一段因任何原因没把 origin 改过来。
if [ -d "$STAGE_P4A/.git" ]; then
    cur="$(git -C "$STAGE_P4A" remote get-url origin 2>/dev/null || echo '')"
    if [ "$cur" != "$P4A_GITHUB" ]; then
        echo "修正 python-for-android 的 origin：$cur -> $P4A_GITHUB"
        git -C "$STAGE_P4A" remote set-url origin "$P4A_GITHUB" 2>/dev/null || true
    fi
fi

# ---------------------------------------------------------------- 依赖源码预置
# p4a 的许多 recipe 源码托管在 GitHub。国内网络常常无法直连，构建会在
# 下载阶段长时间卡住。这里先尝试直连，失败则通过镜像把源码放进 p4a 的
# 包缓存目录（并写好 .mark- 标记文件，否则 p4a 会删掉重新下载）。
# buildozer 实际使用的存储目录是 $HOME/.buildozer（见构建日志里的
# PACKAGES_PATH / ANDROIDSDK），而不是暂存目录下的 .buildozer。
P4A_PKGS="$HOME/.buildozer/android/platform/build-arm64-v8a_armeabi-v7a/packages"

GH=https://github.com
GH_PXY_1="${GH_PROXY_1:-https://mirror.ghproxy.com/$GH}"
GH_PXY_2="${GH_PROXY_2:-https://ghfast.top/$GH}"
GH_PXY_3="${GH_PROXY_3:-https://gh-proxy.com/$GH}"

# 只探测一次 GitHub 是否直连可用
GITHUB_OK=0
if timeout 15 curl -fsSI "$GH" >/dev/null 2>&1; then
    GITHUB_OK=1
    echo "GitHub 直连可用，跳过源码预置"
fi

if [ "$GITHUB_OK" -eq 0 ]; then
    echo "GitHub 直连不可用，通过镜像预置 recipe 源码 ..."

    # recipe|文件名|镜像候选（逗号分隔，GitHub 放最后）
    RECIPE_SOURCES="
libffi|v3.4.2.tar.gz|https://mirrors.aliyun.com/gnu/libffi/libffi-3.4.2.tar.gz,$GH_PXY_1/libffi/libffi/archive/v3.4.2.tar.gz,$GH_PXY_2/libffi/libffi/archive/v3.4.2.tar.gz,$GH/libffi/libffi/archive/v3.4.2.tar.gz
sdl2_image|SDL2_image-2.8.2.tar.gz|$GH_PXY_1/libsdl-org/SDL_image/releases/download/release-2.8.2/SDL2_image-2.8.2.tar.gz,$GH_PXY_2/libsdl-org/SDL_image/releases/download/release-2.8.2/SDL2_image-2.8.2.tar.gz,$GH/libsdl-org/SDL_image/releases/download/release-2.8.2/SDL2_image-2.8.2.tar.gz
sdl2_mixer|SDL2_mixer-2.6.3.tar.gz|$GH_PXY_1/libsdl-org/SDL_mixer/releases/download/release-2.6.3/SDL2_mixer-2.6.3.tar.gz,$GH_PXY_2/libsdl-org/SDL_mixer/releases/download/release-2.6.3/SDL2_mixer-2.6.3.tar.gz,$GH/libsdl-org/SDL_mixer/releases/download/release-2.6.3/SDL2_mixer-2.6.3.tar.gz
sdl2_ttf|SDL2_ttf-2.22.0.tar.gz|$GH_PXY_1/libsdl-org/SDL_ttf/releases/download/release-2.22.0/SDL2_ttf-2.22.0.tar.gz,$GH_PXY_2/libsdl-org/SDL_ttf/releases/download/release-2.22.0/SDL2_ttf-2.22.0.tar.gz,$GH/libsdl-org/SDL_ttf/releases/download/release-2.22.0/SDL2_ttf-2.22.0.tar.gz
sdl2|SDL2-2.30.11.tar.gz|$GH_PXY_1/libsdl-org/SDL/releases/download/release-2.30.11/SDL2-2.30.11.tar.gz,$GH_PXY_2/libsdl-org/SDL/releases/download/release-2.30.11/SDL2-2.30.11.tar.gz,$GH/libsdl-org/SDL/releases/download/release-2.30.11/SDL2-2.30.11.tar.gz
sqlite3|version-3.50.4.tar.gz|$GH_PXY_1/sqlite/sqlite/archive/refs/tags/version-3.50.4.tar.gz,$GH_PXY_2/sqlite/sqlite/archive/refs/tags/version-3.50.4.tar.gz,$GH/sqlite/sqlite/archive/refs/tags/version-3.50.4.tar.gz
pyjnius|1.7.0.zip|$GH_PXY_1/kivy/pyjnius/archive/1.7.0.zip,$GH_PXY_2/kivy/pyjnius/archive/1.7.0.zip,$GH/kivy/pyjnius/archive/1.7.0.zip
pycparser|pycparser-2.14.tar.gz|https://files.pythonhosted.org/packages/source/p/pycparser/pycparser-2.14.tar.gz,$GH_PXY_1/eliben/pycparser/archive/release_v2.14.tar.gz,$GH_PXY_2/eliben/pycparser/archive/release_v2.14.tar.gz
cffi|v2.0.0.tar.gz|$GH_PXY_1/python-cffi/cffi/archive/refs/tags/v2.0.0.tar.gz,$GH_PXY_2/python-cffi/cffi/archive/refs/tags/v2.0.0.tar.gz,$GH/python-cffi/cffi/archive/refs/tags/v2.0.0.tar.gz
kivy|2.3.1.zip|$GH_PXY_1/kivy/kivy/archive/2.3.1.zip,$GH_PXY_2/kivy/kivy/archive/2.3.1.zip,$GH/kivy/kivy/archive/2.3.1.zip
cryptography|46.0.3.tar.gz|$GH_PXY_1/pyca/cryptography/archive/refs/tags/46.0.3.tar.gz,$GH_PXY_2/pyca/cryptography/archive/refs/tags/46.0.3.tar.gz,$GH/pyca/cryptography/archive/refs/tags/46.0.3.tar.gz
pycryptodome|v3.23.0.tar.gz|$GH_PXY_1/Legrandin/pycryptodome/archive/refs/tags/v3.23.0.tar.gz,$GH_PXY_2/Legrandin/pycryptodome/archive/refs/tags/v3.23.0.tar.gz,$GH/Legrandin/pycryptodome/archive/refs/tags/v3.23.0.tar.gz
"

    seed_recipe_sources() {
        local recipe fname urls dest out sz u oldifs
        while IFS='|' read -r recipe fname urls; do
            [ -z "${recipe:-}" ] && continue
            dest="$P4A_PKGS/$recipe"
            mkdir -p "$dest"
            if [ -s "$dest/$fname" ] && [ -f "$dest/.mark-$fname" ]; then
                echo "  [已有] $recipe/$fname"
                continue
            fi
            out="$(mktemp)"
            oldifs="$IFS"; IFS=','
            for u in $urls; do
                IFS="$oldifs"
                if timeout 240 curl -fsSL --retry 2 -o "$out" "$u" 2>/dev/null; then
                    sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
                    # 校验格式：有些镜像会返回 HTML 索引页而不是压缩包
                    valid=0
                    case "$fname" in
                        *.tar.gz|*.tgz) file -b "$out" 2>/dev/null | grep -qi 'gzip' && valid=1 ;;
                        *.zip)          file -b "$out" 2>/dev/null | grep -qi 'zip'  && valid=1 ;;
                        *)              valid=1 ;;
                    esac
                    if [ "$sz" -gt 4096 ] && [ "$valid" -eq 1 ]; then
                        cp "$out" "$dest/$fname"
                        touch "$dest/.mark-$fname"
                        echo "  [OK]   $recipe/$fname ($(du -h "$out" | cut -f1))"
                        rm -f "$out"; out=""; break
                    fi
                fi
                IFS=','
            done
            IFS="$oldifs"
            [ -n "$out" ] && { rm -f "$out"; echo "  [失败] $recipe/$fname（可设置 GH_PROXY_1 指定其他镜像）"; }
        done <<< "$RECIPE_SOURCES"
    }

    seed_recipe_sources

    # Python 解释器源码（p4a 从 GitHub 取，需重打包为 cpython-<ver> 顶层目录）
    HOSTPY_PKG="$P4A_PKGS/hostpython3"
    if [ ! -s "$HOSTPY_PKG/v3.14.2.tar.gz" ]; then
        echo "  预置 hostpython3 源码 ..."
        mkdir -p "$HOSTPY_PKG"
        _w="$(mktemp -d)"
        for u in https://mirrors.aliyun.com/python-release/source/Python-3.14.2.tar.xz \
                 https://mirrors.huaweicloud.com/python/3.14.2/Python-3.14.2.tar.xz; do
            if timeout 600 curl -fsSL -o "$_w/py.tar.xz" "$u" 2>/dev/null; then
                if tar -xf "$_w/py.tar.xz" -C "$_w" 2>/dev/null && [ -d "$_w/Python-3.14.2" ]; then
                    mv "$_w/Python-3.14.2" "$_w/cpython-3.14.2"
                    tar -czf "$HOSTPY_PKG/v3.14.2.tar.gz" -C "$_w" cpython-3.14.2
                    touch "$HOSTPY_PKG/.mark-v3.14.2.tar.gz"
                    echo "  [OK]   hostpython3/v3.14.2.tar.gz"
                    break
                fi
            fi
        done
        rm -rf "$_w"
        [ -s "$HOSTPY_PKG/v3.14.2.tar.gz" ] || echo "  [失败] hostpython3（首次构建可能卡在这里）"
    else
        echo "  [已有] hostpython3/v3.14.2.tar.gz"
    fi

    # python3 recipe（目标解释器）用同一个 CPython 源码包，直接复用
    if [ -s "$HOSTPY_PKG/v3.14.2.tar.gz" ] && [ ! -s "$P4A_PKGS/python3/v3.14.2.tar.gz" ]; then
        mkdir -p "$P4A_PKGS/python3"
        cp "$HOSTPY_PKG/v3.14.2.tar.gz" "$P4A_PKGS/python3/v3.14.2.tar.gz"
        touch "$P4A_PKGS/python3/.mark-v3.14.2.tar.gz"
        echo "  [OK]   python3/v3.14.2.tar.gz（复用 hostpython3 源码）"
    fi
    echo
fi

# ---------------------------------------------------------------- 构建
cd "$STAGE"
echo
echo "开始构建（首次会下载 Android SDK/NDK，可能需要 30 分钟以上）..."
echo

# 注意：必须传两个独立参数 "android" 与 "$MODE"。
# 写成 "android $MODE"（单个带空格的参数）会被 buildozer 当成一个 token，
# 报 "Unknown command/target android debug"。
BUILD_LOG="/tmp/buildozer_build.log"
set +e
buildozer -v android "$MODE" 2>&1 | tee "$BUILD_LOG" | tail -40
BUILD_RC="${PIPESTATUS[0]}"
set -e

if [ "$BUILD_RC" -ne 0 ]; then
    echo
    echo "!! buildozer 返回非零（$BUILD_RC），完整日志：$BUILD_LOG"
    echo "   最后 40 行："
    tail -40 "$BUILD_LOG" | sed 's/^/   /'
fi

# ---------------------------------------------------------------- 收集产物
APK_DIR="$STAGE/bin"
if [ -d "$APK_DIR" ]; then
    mkdir -p "$PROJECT_ROOT/dist"
    FOUND=0
    for apk in "$APK_DIR"/*.apk; do
        [ -f "$apk" ] || continue
        cp "$apk" "$PROJECT_ROOT/dist/"
        FOUND=1
    done
    echo
    echo "=========================================="
    if [ "$FOUND" -eq 1 ]; then
        echo " 构建完成，APK 已复制到 dist/"
        ls -lh "$PROJECT_ROOT/dist"/*.apk | sed 's/^/   /'
        echo
        echo " 安装到手机："
        echo "   adb install -r dist/<文件名>.apk"
    else
        echo " 未找到 APK，构建可能失败"
        echo "=========================================="
        exit 1
    fi
else
    echo "构建失败：未生成 bin/ 目录" >&2
    exit 1
fi
echo "=========================================="
