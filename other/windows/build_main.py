#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
组装 Windows 发布包（复刻历史 build.py 的步骤 3b/4）。

前置：先执行 PyInstaller 主程序构建
    python -m PyInstaller BilibiliDownloader.spec --noconfirm \
        --distpath=dist_win --workpath=build_win

用法：
    python other/windows/build_main.py              # 清理冗余 + UPX 压缩 + 打完整包
    python other/windows/build_main.py --no-upx     # 跳过 UPX（打包最快，体积最大）
    python other/windows/build_main.py --upx-budget 20   # 限制 UPX 最多跑 20 分钟
    python other/windows/build_main.py --keep-unused     # 保留未用 Qt 组件（调试用）
    python other/windows/build_main.py --lean       # 改打云端精简包（需先跑 build_lean.py）

体积优化（默认开启）：
    1. 清理未使用的 Qt 组件（Quick/Qml/Charts/Location…）
    2. UPX 无损压缩大文件（Chromium/图形驱动 DLL 自动跳过）
    3. 剔除本机运行状态（client_id/data_consent 等）

产物：
    dist_win/BilibiliDownloader/                        完整程序目录
    output/BilibiliDownloader_<版本>_full.zip            完整包（含 ffmpeg/mpv/bento4）
    output/BilibiliDownloader_<版本>.zip                 精简包（--lean，无 PyQt5/ffmpeg/bento4）
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import zipfile


def _find_root(start):
    """向上查找包含 core/app_config.py 的目录作为项目根。"""
    cur = os.path.abspath(start)
    for _ in range(6):
        if os.path.isfile(os.path.join(cur, "core", "app_config.py")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    raise RuntimeError("未找到项目根目录（缺少 core/app_config.py）")


ROOT = _find_root(__file__)
DIST_DIR = os.path.join(ROOT, "dist_win")
OUTPUT_DIR = os.path.join(ROOT, "output")
APP_NAME = "BilibiliDownloader"
MAIN_DIR = os.path.join(DIST_DIR, APP_NAME)
INTERNAL_DIR = os.path.join(MAIN_DIR, "_internal")
UPX_EXE = os.path.join(ROOT, "upx_tool", "upx.exe")

sys.path.insert(0, ROOT)                                  #_pathsetup
sys.path.insert(0, os.path.join(ROOT, "core"))            #app_config
import _pathsetup  # noqa: E402,F401
from app_config import VERSION_NUM  # noqa: E402


def log(msg):
    """输出日志。

    控制台默认是 GBK 时，emoji/特殊符号会抛 UnicodeEncodeError 并中断打包流程。
    这里对不可编码字符做降级替换，保证打包不会被日志打断。
    """
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        enc = sys.stdout.encoding or "utf-8"
        print(line.encode(enc, "replace").decode(enc, "replace"), flush=True)


def upx_compress(path, timeout=1800):
    """UPX 无损压缩单个文件；失败不影响打包。

    返回 (压缩前字节, 压缩后字节)；未压缩时返回 (n, n)。
    """
    if not os.path.isfile(UPX_EXE) or not os.path.isfile(path):
        return 0, 0
    before = os.path.getsize(path)
    if before == 0:
        return 0, 0
    try:
        r = subprocess.run([UPX_EXE, "-9", "-q", "--force", path],
                           capture_output=True, timeout=timeout)
        after = os.path.getsize(path)
        if r.returncode == 0 and after < before:
            log("    UPX: %-34s %6.1f -> %6.1f MB (省 %5.1f MB)"
                % (os.path.basename(path), before / 1048576, after / 1048576,
                   (before - after) / 1048576))
            return before, after
        log("    UPX 跳过（返回码 %d）: %s" % (r.returncode, os.path.basename(path)))
        return before, before
    except Exception as e:
        log("    UPX 失败（忽略）: %s -> %s" % (os.path.basename(path), e))
        return before, before


# UPX 跳过内核驱动
UPX_SKIP_NAMES = {
    "qt5webenginecore.dll", "qtwebengineprocess.exe",
    "opengl32sw.dll", "d3dcompiler_47.dll",
    "libglesv2.dll", "libegl.dll",
    "nvapi64.dll", "igdml64.dll", "aticfx64.dll",
}
# 已压缩文件不再压
UPX_SKIP_EXT = {".pak", ".dat", ".zip", ".7z", ".gz", ".bz2", ".xz", ".whl", ".pyz"}


def _should_upx(path):
    name = os.path.basename(path).lower()
    if name in UPX_SKIP_NAMES:
        return False
    if os.path.splitext(name)[1] in UPX_SKIP_EXT:
        return False
    try:
        return os.path.getsize(path) >= 512 * 1024   # 只压 >=512KB 的
    except OSError:
        return False


def upx_tree(internal_dir, budget_mb=0):
    """对 _internal 下的大文件批量 UPX 压缩。

    budget_mb>0 时限制总耗时预算（按已用时间估算），避免打包过慢。
    返回 (压缩前合计, 压缩后合计) 字节。
    """
    if not os.path.isfile(UPX_EXE):
        log("未找到 upx_tool/upx.exe，跳过压缩")
        return 0, 0

    targets = []
    for root, dirs, files in os.walk(internal_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            p = os.path.join(root, f)
            if _should_upx(p):
                targets.append(p)
    # 大文件优先，收益最高
    targets.sort(key=lambda p: os.path.getsize(p), reverse=True)

    log("UPX 待压缩文件: %d 个" % len(targets))
    tb = ta = 0
    t0 = time.time()
    for i, p in enumerate(targets, 1):
        if budget_mb and (time.time() - t0) > budget_mb * 60:
            log("UPX 已达时间预算（%d 分钟），剩余 %d 个文件跳过"
                % (budget_mb, len(targets) - i + 1))
            break
        b, a = upx_compress(p)
        tb += b
        ta += a
    if tb:
        log("UPX 合计: %.1f -> %.1f MB（省 %.1f MB，耗时 %.0f 秒）"
            % (tb / 1048576, ta / 1048576, (tb - ta) / 1048576, time.time() - t0))
    return tb, ta


# 未使用的 Qt 组件
QT_UNUSED_DLLS = [
    "Qt5Quick.dll", "Qt5Qml.dll", "Qt5Quick3D.dll", "Qt5Quick3DAssetImport.dll",
    "Qt5Quick3DRender.dll", "Qt5Quick3DRuntimeRender.dll", "Qt5Quick3DUtils.dll",
    "Qt5QuickControls2.dll", "Qt5QuickShapes.dll", "Qt5QuickTemplates2.dll",
    "Qt5QuickWidgets.dll", "Qt5QmlModels.dll", "Qt5QmlWorkerScript.dll",
    "Qt5Charts.dll", "Qt5Location.dll", "Qt5Positioning.dll", "Qt5PositioningQuick.dll",
    "Qt5XmlPatterns.dll", "Qt5Multimedia.dll", "Qt5MultimediaWidgets.dll",
    "Qt5MultimediaQuick.dll", "Qt5Sensors.dll", "Qt5SerialPort.dll",
    "Qt5Bluetooth.dll", "Qt5Nfc.dll", "Qt5WebSockets.dll", "Qt5Sql.dll",
    "Qt5Test.dll", "Qt5RemoteObjects.dll", "Qt5Designer.dll", "Qt5Help.dll",
    "Qt5Script.dll", "Qt5ScriptTools.dll", "Qt5Xml.dll",
]
QT_UNUSED_DIRS = [
    os.path.join("PyQt5", "Qt5", "qml"),          # QML不用Quick
]
QT_UNUSED_PYD = [
    "QtQuick.pyd", "QtQml.pyd", "QtMultimedia.pyd", "QtMultimediaWidgets.pyd",
    "QtPositioning.pyd", "QtLocation.pyd", "QtCharts.pyd", "QtXmlPatterns.pyd",
    "QtSql.pyd", "QtTest.pyd", "QtBluetooth.pyd", "QtNfc.pyd",
    "QtSensors.pyd", "QtSerialPort.pyd", "QtWebSockets.pyd", "QtDesigner.pyd",
    "QtHelp.pyd", "QtQuickWidgets.pyd", "QtQmlModels.pyd",
]


def prune_unused(internal_dir):
    """删除确认未使用的运行时组件，减小体积。

    安全性：这些模块在代码中零引用（QtQuick/Qml/Charts/Location/Multimedia/
    Sql/Test/Bluetooth/Nfc/Sensors/SerialPort/WebSockets/Designer/Help），
    删掉后功能不受影响。QtWebEngine 仍然保留（登录验证码/内置播放需要）。
    """
    log("-" * 60)
    log("清理未使用组件")
    freed = 0
    removed = 0

    # 1) 未用 DLL
    bin_dir = os.path.join(internal_dir, "PyQt5", "Qt5", "bin")
    if os.path.isdir(bin_dir):
        for name in QT_UNUSED_DLLS:
            p = os.path.join(bin_dir, name)
            if os.path.isfile(p):
                try:
                    sz = os.path.getsize(p)
                    os.remove(p)
                    freed += sz
                    removed += 1
                except OSError as e:
                    log("    删除失败 %s: %s" % (name, e))

    # 2) 未用 .pyd
    pyqt_dir = os.path.join(internal_dir, "PyQt5")
    if os.path.isdir(pyqt_dir):
        for name in QT_UNUSED_PYD:
            p = os.path.join(pyqt_dir, name)
            if os.path.isfile(p):
                try:
                    sz = os.path.getsize(p)
                    os.remove(p)
                    freed += sz
                    removed += 1
                except OSError as e:
                    log("    删除失败 %s: %s" % (name, e))

    # 3) QML 目录
    for rel in QT_UNUSED_DIRS:
        d = os.path.join(internal_dir, rel)
        if os.path.isdir(d):
            sz = sum(os.path.getsize(os.path.join(r, f))
                     for r, _dd, ff in os.walk(d) for f in ff)
            shutil.rmtree(d, ignore_errors=True)
            if not os.path.isdir(d):
                freed += sz
                removed += 1

    # logo 两份都留
    log("  清理 %d 项，释放 %.1f MB" % (removed, freed / 1048576))
    return freed


# 本机状态不发包
PRIVATE_STATE_FILES = (
    "client_id.txt", "app_config.json", "data_consent.json",
    "download_history.json", "download_tasks.json",
    "dismissed_announcements.json", "wbi_cache.json", "beta_bind.json",
    "browser_env.json", "cloud_config.json", "cookie.txt", "cookies.txt",
)
PRIVATE_STATE_DIRS = ("log", "logs")


def sanitize_private_state(main_dir):
    """从发布目录中剔除开发机的本机状态文件。

    打包脚本会先复制工具再打 zip，而 dist 目录可能残留上次运行的
    client_id/data_consent 等文件；这一步保证交付物是干净的。
    """
    log("-" * 60)
    log("清理本机运行状态（避免随包分发）")
    removed = 0
    for name in PRIVATE_STATE_FILES:
        p = os.path.join(main_dir, name)
        if os.path.isfile(p):
            try:
                os.remove(p)
                log("  已删除 %s" % name)
                removed += 1
            except OSError as e:
                log("  删除失败 %s: %s" % (name, e))
    for d in PRIVATE_STATE_DIRS:
        p = os.path.join(main_dir, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
            if not os.path.isdir(p):
                log("  已删除 %s/" % d)
                removed += 1
    if removed == 0:
        log("  无残留，无需清理")
    return removed



def _is_upx_packed(path):
    """判断文件是否已被 UPX 压缩过（文件内含 UPX! 标记）。"""
    try:
        with open(path, "rb") as f:
            # UPX 标记在文件头
            return b"UPX!" in f.read(4096)
    except OSError:
        return False


def _needs_copy(src, dst):
    """是否需要从 src 复制到 dst。

    关键：若 dst 已存在且已被 UPX 压缩过，则 **不要** 再用未压缩的 src 覆盖它
    （否则重复执行打包脚本会把上一轮的压缩成果抹掉，体积反弹）。
    """
    if not os.path.isfile(dst):
        return True
    if _is_upx_packed(dst):
        return False
    try:
        return os.path.getsize(dst) != os.path.getsize(src)
    except OSError:
        return True


def copy_ffmpeg():
    src_dir = os.path.join(ROOT, "ffmpeg", "bin")
    dst_dir = os.path.join(INTERNAL_DIR, "ffmpeg", "bin")
    if not os.path.isdir(src_dir):
        log("  ffmpeg 目录不存在，跳过")
        return 0
    os.makedirs(dst_dir, exist_ok=True)
    total = 0
    for f in ("ffmpeg.exe", "ffprobe.exe"):
        src = os.path.join(src_dir, f)
        dst = os.path.join(dst_dir, f)
        if os.path.isfile(src):
            if _needs_copy(src, dst):
                shutil.copy2(src, dst)
                log("  已复制 _internal/ffmpeg/bin/%s (%.1f MB)"
                    % (f, os.path.getsize(src) / 1048576))
            else:
                log("  保留已压缩的 _internal/ffmpeg/bin/%s" % f)
            total += os.path.getsize(dst)
    return total


def copy_mpv():
    src_dir = os.path.join(ROOT, "mpv")
    dst_dir = os.path.join(INTERNAL_DIR, "mpv")
    keep = ["mpv.exe", "mpv.com", "vulkan-1.dll",
            "mpv-register.bat", "mpv-unregister.bat"]
    if not os.path.isdir(src_dir):
        log("  mpv 目录不存在，跳过")
        return 0
    os.makedirs(dst_dir, exist_ok=True)
    total = 0
    for f in keep:
        src = os.path.join(src_dir, f)
        dst = os.path.join(dst_dir, f)
        if os.path.isfile(src):
            if _needs_copy(src, dst):
                shutil.copy2(src, dst)
                log("  已复制 _internal/mpv/%s (%.1f MB)"
                    % (f, os.path.getsize(src) / 1048576))
            else:
                log("  保留已压缩的 _internal/mpv/%s" % f)
            total += os.path.getsize(dst)
    return total


def copy_bento4():
    src_root = os.path.join(ROOT, "bento4")
    if not os.path.isdir(src_root):
        log("  bento4 目录不存在，跳过")
        return 0
    bin_src = None
    for root, dirs, _files in os.walk(src_root):
        if "bin" in dirs:
            bin_src = os.path.join(root, "bin")
            break
    if not bin_src:
        log("  bento4 bin 目录未找到，跳过")
        return 0
    dst_dir = os.path.join(INTERNAL_DIR, "bento4", "bin")
    os.makedirs(dst_dir, exist_ok=True)
    total, count = 0, 0
    for f in os.listdir(bin_src):
        src = os.path.join(bin_src, f)
        if os.path.isfile(src) and f.lower().endswith(".exe"):
            shutil.copy2(src, os.path.join(dst_dir, f))
            total += os.path.getsize(src)
            count += 1
    log("  bento4: %d 个 exe, %.1f MB" % (count, total / 1048576))
    return total


EXCLUDE_FILES = {"cookie.txt", "cookies.txt", "download_history.json",
                 "app_config.json", "client_id.txt", "data_consent.json",
                 "download_tasks.json", "wbi_cache.json",
                 "dismissed_announcements.json", "beta_bind.json",
                 "browser_env.json", "cloud_config.json"}
EXCLUDE_DIRS = {"__pycache__", "log", "logs", ".git", ".workbuddy-ai", "temp"}


def make_zip(main_dir, zip_path, label=""):
    if not os.path.isdir(main_dir):
        log("!!! 主程序目录不存在: %s" % main_dir)
        return False
    count = 0
    raw = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(main_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                fpath = os.path.join(root, f)
                arcname = os.path.relpath(fpath, main_dir)
                if os.path.basename(arcname) in EXCLUDE_FILES:
                    continue
                parts = arcname.replace("\\", "/").split("/")
                if any(p in EXCLUDE_DIRS for p in parts):
                    continue
                zf.write(fpath, arcname)
                count += 1
                raw += os.path.getsize(fpath)
    zsize = os.path.getsize(zip_path) / 1048576
    log("压缩完成: %s %s" % (os.path.basename(zip_path), label))
    log("  文件数 %d | 原始 %.1f MB | ZIP %.1f MB" % (count, raw / 1048576, zsize))
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-upx", action="store_true", help="跳过 UPX 压缩")
    ap.add_argument("--upx-budget", type=int, default=0, metavar="MINUTES",
                    help="UPX 时间预算（分钟），0=不限制")
    ap.add_argument("--keep-unused", action="store_true",
                    help="保留未使用的 Qt 组件（默认会清理以减小体积）")
    ap.add_argument("--lean", action="store_true",
                    help="组装云端精简包（dist/_lean，仅 mpv，剥离 PyQt5/ffmpeg/bento4）")
    args = ap.parse_args()

    if args.lean:
        return pack_lean()

    log("=" * 60)
    log("组装 Windows 发布包  V%s" % VERSION_NUM)
    log("=" * 60)

    if not os.path.isdir(MAIN_DIR):
        log("!!! 主程序目录不存在，请先执行 PyInstaller 构建: %s" % MAIN_DIR)
        return 1

    # --- 卸载程序 ---
    un = os.path.join(DIST_DIR, "uninstaller.exe")
    if os.path.isfile(un):
        shutil.copy2(un, os.path.join(MAIN_DIR, "uninstaller.exe"))
        log("已复制 uninstaller.exe (%.1f MB)" % (os.path.getsize(un) / 1048576))
    else:
        log("[警告] uninstaller.exe 不存在，跳过")

    # --- 工具 ---
    log("-" * 60)
    log("复制内置工具到 _internal/")
    t1 = copy_ffmpeg()
    t2 = copy_mpv()
    t3 = copy_bento4()
    log("工具合计: %.1f MB" % ((t1 + t2 + t3) / 1048576))

    # --- 清理未用组件 ---
    if not args.keep_unused:
        prune_unused(INTERNAL_DIR)
    else:
        log("已跳过未使用组件清理（--keep-unused）")

    # --- 剔除本机状态 ---
    sanitize_private_state(MAIN_DIR)

    # --- UPX ---
    if not args.no_upx and os.path.isfile(UPX_EXE):
        log("-" * 60)
        log("UPX 无损压缩（已自动跳过 Chromium/驱动类 DLL）")
        upx_tree(INTERNAL_DIR, budget_mb=args.upx_budget)
    elif args.no_upx:
        log("已跳过 UPX 压缩（--no-upx）")
    else:
        log("未找到 upx_tool/upx.exe，跳过压缩")

    # --- 打包 ---
    log("-" * 60)
    full_zip = os.path.join(OUTPUT_DIR, "%s_%s_full.zip" % (APP_NAME, VERSION_NUM))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ok = make_zip(MAIN_DIR, full_zip, "完整包(含 ffmpeg/mpv/bento4)")

    log("=" * 60)
    if ok:
        log("完成 ✅  %s" % full_zip)
        return 0
    log("失败 ❌")
    return 1


LEAN_MAIN_DIR = os.path.join(ROOT, "dist", "_lean", APP_NAME)


def pack_lean():
    """组装云端精简包：仅 mpv，不含 PyQt5/ffmpeg/bento4。"""
    log("=" * 60)
    log("组装云端精简包  V%s" % VERSION_NUM)
    log("=" * 60)
    if not os.path.isdir(LEAN_MAIN_DIR):
        log("!!! 精简目录不存在，请先构建（temp/_build_lean.py）: %s" % LEAN_MAIN_DIR)
        return 1

    lean_internal = os.path.join(LEAN_MAIN_DIR, "_internal")
    os.makedirs(lean_internal, exist_ok=True)

    log("复制 mpv 到 _internal/")
    t = copy_mpv_to(lean_internal)

    # 确认精简包无残留
    for bad in ("PyQt5", "ffmpeg", "bento4"):
        p = os.path.join(lean_internal, bad)
        if os.path.exists(p):
            log("[警告] 精简包内意外存在 %s，已移除" % bad)
            shutil.rmtree(p, ignore_errors=True)

    un = os.path.join(DIST_DIR, "uninstaller.exe")
    if os.path.isfile(un):
        shutil.copy2(un, os.path.join(LEAN_MAIN_DIR, "uninstaller.exe"))
        log("已复制 uninstaller.exe (%.1f MB)" % (os.path.getsize(un) / 1048576))

    log("mpv 合计: %.1f MB" % (t / 1048576))
    log("-" * 60)
    zip_path = os.path.join(OUTPUT_DIR, "%s_%s.zip" % (APP_NAME, VERSION_NUM))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ok = make_zip(LEAN_MAIN_DIR, zip_path, "精简包(无 PyQt5，仅 mpv)")
    log("=" * 60)
    if ok:
        log("完成 ✅  %s" % zip_path)
        return 0
    log("失败 ❌")
    return 1


def copy_mpv_to(internal_dir):
    src_dir = os.path.join(ROOT, "mpv")
    dst_dir = os.path.join(internal_dir, "mpv")
    keep = ["mpv.exe", "mpv.com", "vulkan-1.dll",
            "mpv-register.bat", "mpv-unregister.bat"]
    if not os.path.isdir(src_dir):
        log("  mpv 目录不存在，跳过")
        return 0
    os.makedirs(dst_dir, exist_ok=True)
    total = 0
    for f in keep:
        src = os.path.join(src_dir, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dst_dir, f))
            total += os.path.getsize(src)
            log("  已复制 _internal/mpv/%s (%.1f MB)"
                % (f, os.path.getsize(src) / 1048576))
    return total


if __name__ == "__main__":
    sys.exit(main())
