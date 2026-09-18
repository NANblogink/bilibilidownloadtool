#!/usr/bin/env python
"""
B站视频解析工具 自动化打包脚本

打包流程：
  1. PyInstaller --onedir  打包主程序（文件夹方式）
  2. PyInstaller --onefile  打包卸载程序（单文件）
  3. 复制卸载程序到主程序文件夹内
  4. 压缩主程序文件夹为zip安装包
  5. PyInstaller --onefile  打包安装程序（单文件，保持云端读取逻辑）

用法: python build.py
"""

import os
import sys
import shutil
import subprocess
import zipfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# SCRIPT_DIR 是本脚本所在目录（build/）；ROOT_DIR 才是项目根。
# 资源（logo/version_info）与源码入口 main.py 都在项目根，
# 因此下面凡是定位这些路径的地方一律用 ROOT_DIR。
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

# 关键顺序：app_config 已归入 core/，必须先完成路径注入再导入它。
# 此前是先 from app_config import ... 才插入路径，导致脚本自己都跑不起来
# （ModuleNotFoundError: No module named 'app_config'）。
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import _pathsetup  # noqa: F401,E402  导入即完成 core/ 等子目录注入

from app_config import (  # noqa: E402
    APP_NAME as APP_NAME_CN,
    APP_NAME_EN,
    APP_VERSION,
    VERSION_NUM,
    APP_DESCRIPTION,
)

APP_NAME = APP_NAME_EN
APP_NAME_ZH = APP_NAME_CN
MAIN_SCRIPT = "main.py"
BOOT_SCRIPT = "boot.py"
VERSION_FILE = "version_info.win"

# 卸载/安装/证书安装器脚本在重构时已归入 build/ 目录（本文件所在目录）。
# 而 main.py / boot.py 仍在项目根。
# 构建脚本的工作目录是 ROOT_DIR，因此这里必须给出**绝对路径**，
# 否则 PyInstaller 会报 "Script file 'uninstaller.py' does not exist"。
UNINSTALLER_SCRIPT = os.path.join(SCRIPT_DIR, "uninstaller.py")
INSTALLER_SCRIPT = os.path.join(SCRIPT_DIR, "installer.py")
# 证书安装器在 core/ 下（非 build/）
CERT_INSTALLER_SCRIPT = os.path.join(ROOT_DIR, "core", "cert_installer.py")

# PyInstaller 需要知道源码子目录，否则无法静态分析子目录里的模块
SOURCE_PATHS = [
    ROOT_DIR,
    os.path.join(ROOT_DIR, "core"),
    os.path.join(ROOT_DIR, "core", "infra"),
    os.path.join(ROOT_DIR, "parsers"),
    os.path.join(ROOT_DIR, "build"),
]
PYINSTALLER_PATHEX = []
for _p in SOURCE_PATHS:
    if os.path.isdir(_p):
        PYINSTALLER_PATHEX += ["--paths", _p]

# 构建产物目录：注意工作目录不能叫 build/，否则会与本脚本所在目录
# （也存放源码）冲突，PyInstaller 清理 workpath 时会删掉源码。
BUILD_DIR = os.path.join(ROOT_DIR, "build_parts")
DIST_DIR = os.path.join(ROOT_DIR, "dist")
WORK_DIR = os.path.join(ROOT_DIR, "build_dist")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")

def _refresh_pyinstaller_paths():
    """把 workpath/distpath 同步到当前的 WORK_DIR / DIST_DIR。

    内测渠道会把这两个目录换成 *_beta，PyInstaller 的参数必须一起更新，
    否则两种渠道会写进同一个 dist，互相覆盖。
    LEAN_DIST 在文件后面才定义，因此这里用 globals() 判断后再刷新。
    """
    for i, a in enumerate(PYINSTALLER_BASE):
        if a.startswith("--workpath="):
            PYINSTALLER_BASE[i] = f"--workpath={WORK_DIR}"
        elif a.startswith("--distpath="):
            PYINSTALLER_BASE[i] = f"--distpath={DIST_DIR}"
    if "LEAN_DIST" in globals():
        globals()["LEAN_DIST"] = os.path.join(DIST_DIR, "_lean")


PYINSTALLER_BASE = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--noupx",
    f"--workpath={WORK_DIR}",
    f"--distpath={DIST_DIR}",
    f"--version-file={os.path.join(ROOT_DIR, VERSION_FILE)}",
] + PYINSTALLER_PATHEX

MAIN_EXTRA_ARGS = [
    "--name", APP_NAME,
    "--onedir",
    "--windowed",
    "--icon=logo.ico" if os.path.exists(os.path.join(ROOT_DIR, "logo.ico")) else "",
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "scipy",
    "--exclude-module", "PIL",
    "--exclude-module", "streamlit",
    "--exclude-module", "rich",
    f"--add-data={os.path.join(ROOT_DIR, 'version_info.json')};.",
    "--hidden-import", "PyQt5.sip",
    "--hidden-import", "PyQt5.QtCore",
    "--hidden-import", "PyQt5.QtGui",
    "--hidden-import", "PyQt5.QtWidgets",
    "--hidden-import", "PyQt5.QtWebEngineWidgets",
    "--hidden-import", "PyQt5.QtWebChannel",
    "--hidden-import", "PyQt5.QtNetwork",
    "--hidden-import", "PyQt5.QtPrintSupport",
    "--hidden-import", "PyQt5.QtMultimedia",
    "--hidden-import", "PyQt5.QtMultimediaWidgets",
    "--hidden-import", "requests",
    "--hidden-import", "certifi",
    "--hidden-import", "curl_cffi",
    "--hidden-import", "curl_cffi.requests",
    "--collect-binaries", "curl_cffi",
    "--hidden-import", "qrcode",
    "--hidden-import", "qrcode.constants",
    "--hidden-import", "qrcode.main",
    "--hidden-import", "live_parser",
    "--hidden-import", "live_tab",
    "--hidden-import", "audio_parser",
    "--hidden-import", "audio_tab",
    MAIN_SCRIPT,
]
if os.path.exists(os.path.join(ROOT_DIR, 'logo.ico')):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={os.path.join(ROOT_DIR, 'logo.ico')};.")
    MAIN_EXTRA_ARGS.insert(-1, "--icon=logo.ico")
# logo_alt_kaisui.ico 已归入 assets/icons（备用图标）
_ALT_ICON = os.path.join(ROOT_DIR, 'assets', 'icons', 'logo_alt_kaisui.ico')
if os.path.exists(_ALT_ICON):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={_ALT_ICON};assets/icons")
# logo.png 用于通知中心 Toast 图标（appLogoOverride）
if os.path.exists(os.path.join(ROOT_DIR, 'logo.png')):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={os.path.join(ROOT_DIR, 'logo.png')};.")
# warning_icon.png 用于错误通知左侧警告图标
if os.path.exists(os.path.join(ROOT_DIR, 'warning_icon.png')):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={os.path.join(ROOT_DIR, 'warning_icon.png')};.")
# 关于页面的 svg 图标（QQ/B站/GitHub/网站）位于 assets/icons
_ICONS_DIR = os.path.join(ROOT_DIR, "assets", "icons")
if os.path.isdir(_ICONS_DIR):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={_ICONS_DIR};assets/icons")
# 关于页面的二维码图片（QQ交流群 / 作者QQ）已归入 assets/images
_IMAGES_DIR = os.path.join(ROOT_DIR, "assets", "images")
if os.path.isdir(_IMAGES_DIR):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={_IMAGES_DIR};assets/images")
# 软件著作权登记证书图片（关于页 -> 查看登记证书）
_COPYRIGHT_DIR = os.path.join(ROOT_DIR, "assets", "copyright")
if os.path.isdir(_COPYRIGHT_DIR):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={_COPYRIGHT_DIR};assets/copyright")

UNINSTALL_EXTRA_ARGS = [
    "--name", "uninstaller",
    "--onefile",
    "--windowed",
    "--icon=logo.ico" if os.path.exists(os.path.join(ROOT_DIR, "logo.ico")) else "",
    "--hidden-import", "PyQt5.sip",
    "--hidden-import", "PyQt5.QtCore",
    "--hidden-import", "PyQt5.QtGui",
    "--hidden-import", "PyQt5.QtWidgets",
    UNINSTALLER_SCRIPT,
]

CERT_INSTALLER_EXTRA_ARGS = [
    "--name", "cert_installer",
    "--onefile",
    "--console",
    "--icon=logo.ico" if os.path.exists(os.path.join(ROOT_DIR, "logo.ico")) else "",
    CERT_INSTALLER_SCRIPT,
]

INSTALLER_EXTRA_ARGS = [
    "--name", f"{VERSION_NUM}_installer",
    "--onefile",
    "--windowed",
    "--icon=logo.ico" if os.path.exists(os.path.join(ROOT_DIR, "logo.ico")) else "",
    "--hidden-import", "PyQt5.sip",
    "--hidden-import", "PyQt5.QtCore",
    "--hidden-import", "PyQt5.QtGui",
    "--hidden-import", "PyQt5.QtWidgets",
    INSTALLER_SCRIPT,
]

# 精简主程序（剥离 PyQt5，供云端/绿色版）：入口 boot.py，
# 通过 --hidden-import main 让 PyInstaller 依旧分析收集全部业务依赖进 PYZ，
# 但用 --exclude-module PyQt5 系列把 PyQt5 留在包外（首次启动由 pyqt5_bootstrap 下载注入）。
LEAN_EXTRA_ARGS = [
    "--name", APP_NAME,
    "--onedir",
    "--windowed",
    f"--icon={os.path.join(ROOT_DIR, 'logo.ico')}" if os.path.exists(os.path.join(ROOT_DIR, "logo.ico")) else "",
    "--hidden-import", "main",
    "--hidden-import", "cli",
    "--hidden-import", "live_parser",
    "--hidden-import", "live_tab",
    "--hidden-import", "audio_parser",
    "--hidden-import", "audio_tab",
    "--hidden-import", "requests",
    "--hidden-import", "certifi",
    "--hidden-import", "curl_cffi",
    "--hidden-import", "curl_cffi.requests",
    "--collect-binaries", "curl_cffi",
    "--hidden-import", "qrcode",
    "--hidden-import", "qrcode.constants",
    "--hidden-import", "qrcode.main",
    "--hidden-import", "Crypto",
    "--hidden-import", "runpy",
    "--hidden-import", "pyqt5_bootstrap",
    # 与完整链一致的排除：这些大体积/无关库不随精简包
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "scipy",
    "--exclude-module", "PIL",
    "--exclude-module", "streamlit",
    "--exclude-module", "rich",
    # 剥离 PyQt5 及其常用子模块（运行时下载补装）
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt5.sip",
    "--exclude-module", "PyQt5.QtCore",
    "--exclude-module", "PyQt5.QtGui",
    "--exclude-module", "PyQt5.QtWidgets",
    "--exclude-module", "PyQt5.QtNetwork",
    "--exclude-module", "PyQt5.QtWebEngineWidgets",
    "--exclude-module", "PyQt5.QtWebChannel",
    "--exclude-module", "PyQt5.QtMultimedia",
    "--exclude-module", "PyQt5.QtMultimediaWidgets",
    "--exclude-module", "PyQt5.QtPrintSupport",
]
# 精简主的资源 add-data 与完整链保持一致
if os.path.exists(os.path.join(ROOT_DIR, 'version_info.json')):
    LEAN_EXTRA_ARGS.append(f"--add-data={os.path.join(ROOT_DIR, 'version_info.json')};.")
if os.path.exists(os.path.join(ROOT_DIR, 'logo.ico')):
    LEAN_EXTRA_ARGS.append(f"--add-data={os.path.join(ROOT_DIR, 'logo.ico')};.")
if os.path.exists(os.path.join(ROOT_DIR, 'logo_alt_kaisui.ico')):
    LEAN_EXTRA_ARGS.append(f"--add-data={os.path.join(ROOT_DIR, 'logo_alt_kaisui.ico')};.")
if os.path.exists(os.path.join(ROOT_DIR, 'logo.png')):
    LEAN_EXTRA_ARGS.append(f"--add-data={os.path.join(ROOT_DIR, 'logo.png')};.")
if os.path.exists(os.path.join(ROOT_DIR, 'warning_icon.png')):
    LEAN_EXTRA_ARGS.append(f"--add-data={os.path.join(ROOT_DIR, 'warning_icon.png')};.")
_ICONS_DIR = os.path.join(ROOT_DIR, "assets", "icons")
if os.path.isdir(_ICONS_DIR):
    LEAN_EXTRA_ARGS.append(f"--add-data={_ICONS_DIR};assets/icons")
for _qr_img in ("myqrcode.png", "qunqrcode.png"):
    _qr_path = os.path.join(ROOT_DIR, _qr_img)
    if os.path.exists(_qr_path):
        LEAN_EXTRA_ARGS.append(f"--add-data={_qr_path};.")

LEAN_DIST = os.path.join(DIST_DIR, "_lean")

def _lean_app_dir():
    return os.path.join(LEAN_DIST, APP_NAME)


def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


UPX_EXE = os.path.join(ROOT_DIR, "upx_tool", "upx.exe")


def upx_compress(file_path):
    """用 UPX 无损压缩单个可执行文件，功能不变，仅减小体积。
    压缩失败不影响打包（保持未压缩原文件）。
    """
    if not os.path.isfile(UPX_EXE) or not os.path.isfile(file_path):
        return
    before = os.path.getsize(file_path)
    try:
        result = subprocess.run(
            [UPX_EXE, "--best", "-q", file_path],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        if result.returncode == 0:
            try:
                after = os.path.getsize(file_path)
                log(f"  [UPX] {os.path.basename(file_path)}: {before/1024/1024:.1f}MB -> {after/1024/1024:.1f}MB")
            except Exception:
                pass
    except Exception:
        pass


def run_cmd(cmd, description):
    log(f">>> {description}")
    log(f"    命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT_DIR)
    if result.returncode != 0:
        log(f"!!! {description} 失败")
        return False
    log(f"<<< {description} 完成")
    return True


def _safe_rmtree(path, tries=40, wait=2.0):
    """带重试的目录删除。杀毒软件/索引服务会短暂锁定大体积 exe 导致删除失败，
    ignore_errors 静默忽略会让旧文件残留，进而导致后续 PyInstaller 清理时崩溃。
    这里遇到锁定就等待后重试，确保删干净。"""
    for i in range(tries):
        if not os.path.exists(path):
            return True
        try:
            shutil.rmtree(path)
            return True
        except OSError as _e:
            log(f"  清理 {path} 被占用({_e})，等待重试 {i + 1}/{tries}...")
            time.sleep(wait)
    log(f"  !!! 清理 {path} 重试耗尽，仍失败")
    return not os.path.exists(path)


def clean_build_dirs():
    log("清理构建/输出目录")
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        log(f"已清理: {BUILD_DIR}")
    if _safe_rmtree(DIST_DIR):
        log(f"已清理: {DIST_DIR}")
    if _safe_rmtree(OUTPUT_DIR):
        log(f"已清理: {OUTPUT_DIR}")
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def step1_build_main():
    log("=" * 60)
    log("步骤1: 打包主程序")
    log("=" * 60)

    cmd = PYINSTALLER_BASE + [a for a in MAIN_EXTRA_ARGS if a]
    return run_cmd(cmd, "打包主程序")


def step1_lean_build_main():
    """打包精简主程序：入口 boot.py，剥离 PyQt5，独立 dist 目录避免与完整链冲突。"""
    log("=" * 60)
    log("步骤1(精简): 打包精简主程序（boot 入口，剥离 PyQt5）")
    log("=" * 60)

    build_lean = os.path.join(BUILD_DIR, "_lean")
    cmd = (
        PYINSTALLER_BASE
        + [f"--distpath={LEAN_DIST}", f"--workpath={build_lean}", f"--specpath={build_lean}"]
        + [a for a in LEAN_EXTRA_ARGS if a]
        + [BOOT_SCRIPT]
    )
    return run_cmd(cmd, "打包精简主程序")


def step2_build_uninstaller():
    log("=" * 60)
    log("步骤2: 打包卸载程序")
    log("=" * 60)

    cmd = PYINSTALLER_BASE + [a for a in UNINSTALL_EXTRA_ARGS if a]
    return run_cmd(cmd, "打包卸载程序")


def step2b_build_cert_installer():
    """打包证书安装器（供最终用户在新设备上安装证书）"""
    log("=" * 60)
    log("步骤2b: 打包证书安装器")
    log("=" * 60)

    if not os.path.exists(CERT_INSTALLER_SCRIPT):
        log(f"  {CERT_INSTALLER_SCRIPT} 不存在，跳过")
        return True

    cmd = PYINSTALLER_BASE + [a for a in CERT_INSTALLER_EXTRA_ARGS if a]
    if not run_cmd(cmd, "打包证书安装器"):
        return False

    # 复制 cert_installer.exe 和证书文件到 output 目录
    src_exe = os.path.join(DIST_DIR, "cert_installer.exe")
    cer_file = os.path.join(ROOT_DIR, "BilibiliDownloader_dev.cer")

    if os.path.exists(src_exe):
        dst_exe = os.path.join(OUTPUT_DIR, "cert_installer.exe")
        shutil.copy2(src_exe, dst_exe)
        size_mb = os.path.getsize(dst_exe) / 1024 / 1024
        log(f"  已复制: cert_installer.exe ({size_mb:.1f} MB)")

    if os.path.exists(cer_file):
        dst_cer = os.path.join(OUTPUT_DIR, "BilibiliDownloader_dev.cer")
        shutil.copy2(cer_file, dst_cer)
        log(f"  已复制: BilibiliDownloader_dev.cer")
    else:
        log("  [警告] 未找到 BilibiliDownloader_dev.cer（需先运行 sign_exes.ps1）")

    return True


def step2c_copy_lean_runtime():
    """向精简主程序目录复制 mpv/卸载程序/证书（不复制 ffmpeg/bento4/PyQt5）。"""
    log("=" * 60)
    log("步骤2c: 精简主程序补充运行文件")
    log("=" * 60)

    main_dir = _lean_app_dir()
    if not os.path.isdir(main_dir):
        log("!!! 精简主程序目录不存在，先执行 step1_lean_build_main")
        return False

    internal = os.path.join(main_dir, '_internal')
    os.makedirs(internal, exist_ok=True)
    _copy_mpv(internal)  # 仅 mpv，PyQt5/ffmpeg/bento4 不随精简包

    un = os.path.join(DIST_DIR, "uninstaller.exe")
    if os.path.isfile(un):
        shutil.copy2(un, os.path.join(main_dir, "uninstaller.exe"))
        log(f"  已复制卸载程序到精简包 ({os.path.getsize(un)/1024/1024:.1f} MB)")

    cer = os.path.join(ROOT_DIR, "BilibiliDownloader_dev.cer")
    if os.path.isfile(cer):
        shutil.copy2(cer, os.path.join(main_dir, "BilibiliDownloader_dev.cer"))
        log(f"  已复制证书到精简包")

    return True


def step3_copy_uninstaller():
    log("=" * 60)
    log("步骤3: 复制卸载程序到主程序文件夹")
    log("=" * 60)

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    uninstaller_exe = os.path.join(DIST_DIR, "uninstaller.exe")

    if not os.path.isdir(main_dir):
        log(f"!!! 主程序目录不存在: {main_dir}")
        return False
    if not os.path.isfile(uninstaller_exe):
        log(f"!!! 卸载程序不存在: {uninstaller_exe}")
        return False

    dest = os.path.join(main_dir, "uninstaller.exe")
    shutil.copy2(uninstaller_exe, dest)
    size_mb = os.path.getsize(dest) / 1024 / 1024
    log(f"已复制卸载程序: uninstaller.exe ({size_mb:.1f} MB)")
    return True


def step3c_copy_cert():
    """复制开发者证书到主程序文件夹，便于：
    1. 安装程序解压后在安装目录找到证书并自动安装到系统
    2. 主程序启动时在自身目录找到证书并自动安装（无需用户手动运行 cert_installer）
    """
    log("=" * 60)
    log("步骤3c: 复制开发者证书到主程序文件夹")
    log("=" * 60)

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    if not os.path.isdir(main_dir):
        log(f"!!! 主程序目录不存在: {main_dir}")
        return False

    cer_file = os.path.join(ROOT_DIR, "BilibiliDownloader_dev.cer")
    if not os.path.exists(cer_file):
        log("  [警告] 未找到 BilibiliDownloader_dev.cer（需先运行 sign_exes.ps1 生成证书）")
        log("  跳过证书复制（主程序和安装程序将无法自动安装证书）")
        return True  # 不算失败，证书是可选的

    dst = os.path.join(main_dir, "BilibiliDownloader_dev.cer")
    shutil.copy2(cer_file, dst)
    size_kb = os.path.getsize(dst) / 1024
    log(f"已复制证书: BilibiliDownloader_dev.cer ({size_kb:.1f} KB)")
    return True


def step3b_copy_tools(min_size=False):
    log("=" * 60)
    log("步骤3b: 复制工具到 _internal 目录")
    log("=" * 60)

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    internal_dir = os.path.join(main_dir, '_internal')
    os.makedirs(internal_dir, exist_ok=True)

    # 始终先复制完整工具（含 ffmpeg/bento4/mpv），
    # 供内嵌版使用；min_size 时由 step4b 在生成云端精简包前剥离 ffmpeg/bento4。
    _copy_ffmpeg(internal_dir)
    _copy_mpv(internal_dir)
    _copy_bento4(internal_dir)

    return True


def _copy_ffmpeg(internal_dir):
    ffmpeg_src = os.path.join(ROOT_DIR, "ffmpeg", "bin")
    ffmpeg_dst = os.path.join(internal_dir, "ffmpeg", "bin")
    ffmpeg_files = ["ffmpeg.exe", "ffprobe.exe"]
    if os.path.isdir(ffmpeg_src):
        os.makedirs(ffmpeg_dst, exist_ok=True)
        ffmpeg_size = 0
        for f in ffmpeg_files:
            src = os.path.join(ffmpeg_src, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(ffmpeg_dst, f))
                ffmpeg_size += os.path.getsize(src)
                log(f"  已复制: _internal/ffmpeg/bin/{f} ({os.path.getsize(src)/1024/1024:.1f} MB)")
        log(f"  ffmpeg 合计: {ffmpeg_size/1024/1024:.1f} MB")
        log("  ffmpeg 使用 UPX 无损压缩...")
        for f in ffmpeg_files:
            upx_compress(os.path.join(ffmpeg_dst, f))
    else:
        log("  ffmpeg 目录不存在，跳过")


def _copy_mpv(internal_dir):
    mpv_src = os.path.join(ROOT_DIR, "mpv")
    mpv_dst = os.path.join(internal_dir, "mpv")
    mpv_keep = [
        "mpv.exe", "mpv.com", "vulkan-1.dll",
        "mpv-register.bat", "mpv-unregister.bat"
    ]
    if os.path.isdir(mpv_src):
        os.makedirs(mpv_dst, exist_ok=True)
        mpv_size = 0
        skipped_size = 0
        for f in os.listdir(mpv_src):
            src = os.path.join(mpv_src, f)
            if not os.path.isfile(src):
                continue
            if f in mpv_keep:
                shutil.copy2(src, os.path.join(mpv_dst, f))
                mpv_size += os.path.getsize(src)
                log(f"  已复制: _internal/mpv/{f} ({os.path.getsize(src)/1024/1024:.1f} MB)")
            else:
                skipped_size += os.path.getsize(src)
                log(f"  跳过: _internal/mpv/{f} ({os.path.getsize(src)/1024/1024:.1f} MB)")
        log(f"  mpv 合计: {mpv_size/1024/1024:.1f} MB (跳过 {skipped_size/1024/1024:.1f} MB)")
        mpv_compress = [f for f in mpv_keep if f.lower().endswith(('.exe', '.dll', '.com'))]
        if mpv_compress:
            log("  mpv 使用 UPX 无损压缩...")
            for f in mpv_compress:
                upx_compress(os.path.join(mpv_dst, f))
    else:
        log("  mpv 目录不存在，跳过")


def _copy_bento4(internal_dir):
    bento4_src = os.path.join(ROOT_DIR, "bento4")
    bento4_dst = os.path.join(internal_dir, "bento4")
    if os.path.isdir(bento4_src):
        bin_src = None
        for root, dirs, files in os.walk(bento4_src):
            if 'bin' in dirs:
                bin_src = os.path.join(root, 'bin')
                break
        if bin_src and os.path.isdir(bin_src):
            bin_dst = os.path.join(bento4_dst, "bin")
            os.makedirs(bin_dst, exist_ok=True)
            bento4_size = 0
            count = 0
            for f in os.listdir(bin_src):
                src = os.path.join(bin_src, f)
                if os.path.isfile(src) and f.endswith('.exe'):
                    shutil.copy2(src, os.path.join(bin_dst, f))
                    bento4_size += os.path.getsize(src)
                    count += 1
            log(f"  bento4: {count} 个 exe, {bento4_size/1024/1024:.1f} MB")
        else:
            log("  bento4 bin 目录未找到，跳过")
    else:
        log("  bento4 目录不存在，跳过")

    return True


def _make_zip(main_dir, zip_path, label=""):
    if not os.path.isdir(main_dir):
        log(f"!!! 主程序目录不存在: {main_dir}")
        return False

    exclude_files = {'cookie.txt', 'download_history.json', '__pycache__'}
    exclude_dirs = {'log', '__pycache__', '.git'}

    count = 0
    total_size = 0
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(main_dir):
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for f in files:
                fpath = os.path.join(root, f)
                arcname = os.path.relpath(fpath, main_dir)

                basename = os.path.basename(arcname)
                if basename in exclude_files:
                    continue
                parts = arcname.replace('\\', '/').split('/')
                if any(p in exclude_dirs for p in parts):
                    continue

                zf.write(fpath, arcname)
                count += 1
                total_size += os.path.getsize(fpath)

    zip_size = os.path.getsize(zip_path) / 1024 / 1024
    ratio = (1 - zip_size / (total_size / 1024 / 1024)) * 100 if total_size > 0 else 0
    log(f"压缩完成: {os.path.basename(zip_path)} {label}")
    log(f"  文件数: {count}, 原始大小: {total_size / 1024 / 1024:.1f} MB")
    log(f"  ZIP大小: {zip_size:.1f} MB, 压缩率: {ratio:.0f}%")
    log(f"  路径: {os.path.abspath(zip_path)}")
    return True


def step4_zip_folder():
    log("=" * 60)
    log("步骤4: 压缩主程序文件夹为完整zip")
    log("=" * 60)

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    zip_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}_{VERSION_NUM}_full.zip")
    return _make_zip(main_dir, zip_path, "完整包(含全部工具)")


def _strip_tools_for_min_size(main_dir):
    """保留 mpv，移除 ffmpeg/bento4，使云端精简包不含这两类大体积工具。"""
    internal_dir = os.path.join(main_dir, '_internal')
    removed = []
    for t in ('ffmpeg', 'bento4'):
        d = os.path.join(internal_dir, t)
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            removed.append(t)
    return removed


def step4b_build_cloud_zip(min_size=False):
    """生成云端精简安装包：来源精简链产物（boot 入口、已剥离 PyQt5、仅 mpv）。
    min_size 时再剥离 ffmpeg/bento4（精简链本就不随包拷贝，此处为兼容历史调用保持幂等）。"""
    log("=" * 60)
    log("步骤4b: 生成云端精简安装包（精简链，无PyQt5）")
    log("=" * 60)

    main_dir = _lean_app_dir()
    if not os.path.isdir(main_dir):
        log(f"!!! 精简主程序目录不存在，先执行 step1_lean_build_main: {main_dir}")
        return False

    cloud_zip = os.path.join(OUTPUT_DIR, f"{APP_NAME}_{VERSION_NUM}.zip")
    return _make_zip(main_dir, cloud_zip, "精简包(无PyQt5, 仅mpv)")


def _find_iscc():
    found = shutil.which('ISCC') or shutil.which('iscc')
    if found:
        return found
    search_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]
    for p in search_paths:
        if os.path.isfile(p):
            return p
    return None


def step5_build_installer():
    log("=" * 60)
    log("步骤5: 用 Inno Setup 打包安装程序")
    log("=" * 60)

    iscc = _find_iscc()
    if not iscc:
        log("未找到 Inno Setup (ISCC.exe)，跳过 Inno Setup 打包")
        log("  下载地址: https://jrsoftware.org/isdl.php")
        log("  安装后添加到 PATH 或放在默认路径即可")
        return True

    iss_path = os.path.join(ROOT_DIR, "setup.iss")
    if not os.path.isfile(iss_path):
        log(f"!!! setup.iss 不存在: {iss_path}")
        return False

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    if not os.path.isdir(main_dir):
        log(f"!!! 主程序目录不存在，先执行打包主程序步骤: {main_dir}")
        return False

    cmd = [
        iscc, iss_path,
        f"/DMyAppName={APP_NAME_ZH}",
        f"/DMyAppVersion={VERSION_NUM}",
        f"/DMyAppExeName={APP_NAME}.exe",
    ]
    success = run_cmd(cmd, "Inno Setup 编译安装程序")

    if success:
        inno_output = os.path.join(ROOT_DIR, "Output")
        installer_name = f"BilibiliDownloader_Setup_V{VERSION_NUM}.exe"
        src = os.path.join(inno_output, installer_name)
        dst = os.path.join(OUTPUT_DIR, installer_name)
        if os.path.isfile(src):
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            shutil.copy2(src, dst)
            size_mb = os.path.getsize(dst) / 1024 / 1024
            log(f"Inno Setup 安装程序已复制到 output/: {installer_name} ({size_mb:.1f} MB)")
            log(f"  路径: {os.path.abspath(dst)}")
        else:
            if os.path.isdir(inno_output):
                for f in os.listdir(inno_output):
                    if f.endswith('.exe'):
                        src = os.path.join(inno_output, f)
                        dst = os.path.join(OUTPUT_DIR, f)
                        shutil.copy2(src, dst)
                        size_mb = os.path.getsize(dst) / 1024 / 1024
                        log(f"Inno Setup 安装程序已复制到 output/: {f} ({size_mb:.1f} MB)")
                        break

    return success


def step5b_build_pyinstaller_installer(embedded=False):
    """打包安装程序
    embedded=False: 云端版（小体积，安装时从云端下载）
    embedded=True:  内嵌版（大体积，包含完整程序包）
    """
    suffix = "内嵌版" if embedded else "云端版"
    log("=" * 60)
    log(f"步骤5b: PyInstaller 打包安装程序（{suffix}）")
    log("=" * 60)

    if embedded:
        zip_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}_{VERSION_NUM}_full.zip")
        if not os.path.isfile(zip_path):
            log(f"!!! 内嵌版需要完整 zip 包: {zip_path}")
            return False
        zip_size_mb = os.path.getsize(zip_path) / 1024 / 1024
        log(f"  内嵌 zip 包: {zip_size_mb:.1f} MB")

    name = f"{VERSION_NUM}_installer_embedded" if embedded else f"{VERSION_NUM}_installer"
    args = [
        "--name", name,
        "--onefile",
        "--windowed",
        "--icon=logo.ico" if os.path.exists(os.path.join(ROOT_DIR, "logo.ico")) else "",
        "--hidden-import", "PyQt5.sip",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtGui",
        "--hidden-import", "PyQt5.QtWidgets",
        "--hidden-import", "tool_manager",
        "--hidden-import", "platform_utils",
        "--hidden-import", "pyqt5_bootstrap",
    ]

    if embedded:
        zip_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}_{VERSION_NUM}_full.zip")
        args.append(f"--add-data={zip_path};.")

    args.append(INSTALLER_SCRIPT)

    cmd = PYINSTALLER_BASE + [a for a in args if a]
    success = run_cmd(cmd, f"打包安装程序（{suffix}）")

    if success:
        installer_name = f"{name}.exe"
        src = os.path.join(DIST_DIR, installer_name)
        dst = os.path.join(OUTPUT_DIR, installer_name)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            size_mb = os.path.getsize(dst) / 1024 / 1024
            log(f"安装程序（{suffix}）已复制到 output/: {installer_name} ({size_mb:.1f} MB)")
            log(f"  路径: {os.path.abspath(dst)}")
        else:
            log(f"!!! 安装程序未生成: {src}")

    return success


def step6_sign_exes(phase="all"):
    """对打包生成的 exe 进行数字签名（如有自签名证书则用之，否则提示用户）
    phase: "dist"=仅签名 dist 下的主程序和卸载程序
           "installers"=仅签名 output 下的安装程序
           "all"=全部签名
    """
    log(f"步骤6({phase}): 数字签名")

    cert_subject = "CN=寒烟似雪"

    # 收集需要签名的 exe
    exe_files = []
    main_dist = os.path.join(DIST_DIR, APP_NAME)
    main_exe = os.path.join(main_dist, f"{APP_NAME}.exe")
    uninst_exe = os.path.join(main_dist, "uninstaller.exe")

    if phase in ("dist", "all"):
        if os.path.exists(main_exe):
            exe_files.append(main_exe)
        if os.path.exists(uninst_exe):
            exe_files.append(uninst_exe)
    if phase in ("installers", "all"):
        if os.path.exists(OUTPUT_DIR):
            for f in os.listdir(OUTPUT_DIR):
                if f.lower().endswith(".exe"):
                    exe_files.append(os.path.join(OUTPUT_DIR, f))

    if not exe_files:
        log("  未找到任何 exe 文件，跳过签名")
        return True

    # 用临时 .ps1 文件执行 PowerShell，避免 -Command 参数的变量转义问题
    import tempfile

    def run_ps(script):
        """执行 PowerShell 脚本，返回 (stdout, stderr, returncode)"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ps1", delete=False, encoding="utf-8-sig", newline="\r\n"
        ) as f:
            f.write(script)
            ps_file = f.name
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_file],
                capture_output=True, text=True, timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except Exception as e:
            return "", str(e), -1
        finally:
            try:
                os.unlink(ps_file)
            except Exception:
                pass

    # 检查证书是否已存在于 CurrentUser\My
    check_script = (
        f'$c = Get-ChildItem "Cert:\\CurrentUser\\My" -CodeSigningCert -ErrorAction SilentlyContinue '
        f"| Where-Object {{ $_.Subject -eq '{cert_subject}' }} | Select-Object -First 1\n"
        f"if ($c) {{ Write-Output $c.Thumbprint }} else {{ Write-Output 'NONE' }}\n"
    )
    stdout, stderr, _ = run_ps(check_script)
    thumbprint = stdout

    if thumbprint == "NONE" or not thumbprint:
        log("  未找到 BilibiliDownloader 代码签名证书")
        log("  首次使用需运行 sign_exes.ps1 创建自签名证书（需管理员权限）:")
        log("    1. 右键 PowerShell -> 以管理员身份运行")
        log("    2. 执行: powershell -ExecutionPolicy Bypass -File sign_exes.ps1")
        log("  之后再次运行 build.py 会自动签名")
        log("  注意: 自签名证书仅缓解'未知发行者'警告，彻底解决报毒需商业证书")
        return True  # 不算失败，签名是可选步骤

    log(f"  使用证书: {thumbprint}")

    success = 0
    failed = 0
    for exe in exe_files:
        name = os.path.basename(exe)
        # 用临时 ps1 文件签名，避免变量转义问题
        sign_script = (
            f"$c = Get-ChildItem 'Cert:\\CurrentUser\\My' | "
            f"Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }} | Select-Object -First 1\n"
            f"$exe = '{exe}'\n"
            f"$r = Set-AuthenticodeSignature -FilePath $exe -Certificate $c "
            f"-HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com'\n"
            f"Write-Output $r.Status\n"
            f"if ($r.Status -ne 'Valid') {{ Write-Output $r.StatusMessage }}\n"
        )
        try:
            stdout, stderr, _ = run_ps(sign_script)
            lines = stdout.split("\n")
            status = lines[0].strip() if lines else "UnknownError"
            if status == "Valid":
                size_mb = os.path.getsize(exe) / (1024 * 1024)
                log(f"  [OK] {name} ({size_mb:.1f} MB)")
                success += 1
            elif status == "HashMismatch":
                # 已有签名，先移除再签
                log(f"  [重签] {name}: 移除旧签名...")
                resign_script = (
                    f"$exe = '{exe}'\n"
                    f"& certutil -delsignature $exe 2>&1 | Out-Null\n"
                    f"$c = Get-ChildItem 'Cert:\\CurrentUser\\My' | "
                    f"Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }} | Select-Object -First 1\n"
                    f"$r = Set-AuthenticodeSignature -FilePath $exe -Certificate $c "
                    f"-HashAlgorithm SHA256 -TimestampServer 'http://timestamp.digicert.com'\n"
                    f"Write-Output $r.Status\n"
                )
                stdout2, _, _ = run_ps(resign_script)
                status2 = stdout2.split("\n")[0].strip() if stdout2 else "UnknownError"
                if status2 == "Valid":
                    size_mb = os.path.getsize(exe) / (1024 * 1024)
                    log(f"  [OK] {name} ({size_mb:.1f} MB)")
                    success += 1
                else:
                    log(f"  [失败] {name}: {status2}")
                    failed += 1
            else:
                msg = lines[1].strip() if len(lines) > 1 else ""
                log(f"  [失败] {name}: {status} - {msg}")
                if stderr:
                    log(f"        {stderr[:200]}")
                failed += 1
        except Exception as e:
            log(f"  [异常] {name}: {e}")
            failed += 1

    log(f"  签名结果: 成功 {success}, 失败 {failed}")
    return failed == 0


def generate_version_badge():
    badge_path = os.path.join(ROOT_DIR, "assets", "badges", "version.svg")
    label = "version"
    version = APP_VERSION
    char_w = {
        '0': 6.6, '1': 3.9, '2': 6.6, '3': 6.6, '4': 6.6,
        '5': 6.6, '6': 6.6, '7': 6.6, '8': 6.6, '9': 6.6,
        '.': 3.3, '-': 3.3, '_': 6.6, ' ': 3.3,
        'A': 7.5, 'B': 7.5, 'C': 7.5, 'D': 7.5, 'E': 7.5,
        'F': 7.5, 'G': 7.5, 'H': 7.5, 'I': 3.3, 'J': 7.5,
        'K': 7.5, 'L': 6.6, 'M': 9.5, 'N': 7.5, 'O': 7.5,
        'P': 7.5, 'Q': 7.5, 'R': 7.5, 'S': 7.5, 'T': 6.6,
        'U': 7.5, 'V': 7.2, 'W': 10.0, 'X': 7.5, 'Y': 7.5,
        'Z': 6.6,
    }
    def _tw(t):
        return sum(char_w.get(c, 6.6) for c in t.upper())
    label_w = 52
    version_w = int(_tw(version) + 12)
    total_w = label_w + version_w
    label_x = int(label_w / 2 * 10)
    version_x = int((label_w + version_w / 2) * 10)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{tw}" height="20">\n'
        '  <linearGradient id="a" x2="0" y2="100%">\n'
        '    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>\n'
        '    <stop offset="1" stop-opacity=".1"/>\n'
        '  </linearGradient>\n'
        '  <rect rx="3" width="{tw}" height="20" fill="#555"/>\n'
        '  <rect rx="3" x="{lw}" width="{vw}" height="20" fill="#007ec6"/>\n'
        '  <path fill="#007ec6" d="M{lw} 0h4v20h-4z"/>\n'
        '  <rect rx="3" width="{tw}" height="20" fill="url(#a)"/>\n'
        '  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="110">\n'
        '    <text x="{lx}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)">{label}</text>\n'
        '    <text x="{lx}" y="140" transform="scale(.1)">{label}</text>\n'
        '    <text x="{vx}" y="150" fill="#010101" fill-opacity=".3" transform="scale(.1)">{version}</text>\n'
        '    <text x="{vx}" y="140" transform="scale(.1)">{version}</text>\n'
        '  </g>\n'
        '</svg>\n'
    ).format(tw=total_w, lw=label_w, vw=version_w, lx=label_x, vx=version_x, label=label, version=version)
    os.makedirs(os.path.dirname(badge_path), exist_ok=True)
    with open(badge_path, 'w', encoding='utf-8') as f:
        f.write(svg)
    log(f"已生成版本徽章 {version}")


def _set_beta_flag(beta: bool):
    """把 core/app_config.py 里的 IS_BETA_BUILD 改成指定值，并返回原值。

    内测包与正式包的唯一代码差异就是这个开关：
      True  → 启动时需输入授权QQ验证，且更新走 beta 通道
      False → 无授权限制，更新走 stable 通道
    打包结束后必须还原，避免把内测开关提交进仓库。
    """
    cfg_path = os.path.join(ROOT_DIR, "core", "app_config.py")
    with open(cfg_path, "r", encoding="utf-8") as f:
        content = f.read()
    import re
    m = re.search(r'^IS_BETA_BUILD\s*=\s*(True|False)\s*$', content, re.M)
    if not m:
        raise RuntimeError("未在 core/app_config.py 中找到 IS_BETA_BUILD")
    original = m.group(1)
    want = "True" if beta else "False"
    if original != want:
        content = content[:m.start(1)] + want + content[m.end(1):]
        with open(cfg_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    return original == "True"


def _restore_beta_flag(original_beta: bool):
    _set_beta_flag(original_beta)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="B站视频解析工具 打包脚本")
    parser.add_argument(
        "--min-size", action="store_true",
        help="最小体积模式：不把 ffmpeg/bento4 打入包内（约减 67MB），"
             "这两者会在安装/运行时从 CDN 自动下载补装。mpv 始终保留随包。"
    )
    parser.add_argument(
        "--beta", action="store_true",
        help="打包内测包：把 core/app_config.py 的 IS_BETA_BUILD 置为 True "
             "（启动需授权QQ验证、更新走 beta 通道）。不指定即为正式包。"
    )
    _args, _unknown = parser.parse_known_args()
    min_size = getattr(_args, "min_size", False)
    beta = getattr(_args, "beta", False)

    # 切换内测/正式开关，结束后无论如何都还原
    _orig_beta = _set_beta_flag(beta)

    try:
        return _run_build(min_size=min_size, beta=beta)
    finally:
        _restore_beta_flag(_orig_beta)


def _run_build(min_size: bool, beta: bool):
    start_time = time.time()
    # 内测包输出到独立目录：clean_build_dirs() 会清空 OUTPUT_DIR，
    # 若两个渠道共用同一目录，后打的包会把先打的覆盖掉。
    global OUTPUT_DIR, DIST_DIR, WORK_DIR, BUILD_DIR
    if beta:
        OUTPUT_DIR = os.path.join(ROOT_DIR, "output_beta")
        DIST_DIR = os.path.join(ROOT_DIR, "dist_beta")
        WORK_DIR = os.path.join(ROOT_DIR, "build_dist_beta")
        BUILD_DIR = os.path.join(ROOT_DIR, "build_parts_beta")
        _refresh_pyinstaller_paths()

    print()
    print("#" * 60)
    print(f"#  {APP_NAME_ZH} {APP_VERSION} 自动化打包")
    print(f"#  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"#  模式: {'最小体积(工具随包外置)' if min_size else '完整(工具随包携带)'}")
    print(f"#  渠道: {'内测包 IS_BETA_BUILD=True' if beta else '正式包 IS_BETA_BUILD=False'}")
    print(f"#  输出: {OUTPUT_DIR}")
    print("#" * 60)
    print()

    clean_build_dirs()

    generate_version_badge()

    has_iscc = _find_iscc() is not None

    steps = [
        ("打包主程序（完整链，含PyQt5）", step1_build_main),
        ("复制工具到完整包 _internal", lambda: step3b_copy_tools(min_size=min_size)),
        ("打包卸载程序（单文件）", step2_build_uninstaller),
        ("复制卸载程序到完整包主程序文件夹", step3_copy_uninstaller),
        ("复制开发者证书到完整包主程序文件夹", step3c_copy_cert),
        ("签名主程序和卸载程序", lambda: step6_sign_exes(phase="dist")),
        ("压缩完整主程序文件夹为 full.zip", step4_zip_folder),
        ("打包精简主程序（boot入口，剥离PyQt5）", step1_lean_build_main),
        ("精简包补充运行文件（mpv/卸载/证书）", step2c_copy_lean_runtime),
        ("生成云端精简安装包", lambda: step4b_build_cloud_zip(min_size=min_size)),
        ("PyInstaller 打包安装程序（云端版）", lambda: step5b_build_pyinstaller_installer(embedded=False)),
        ("PyInstaller 打包安装程序（内嵌版）", lambda: step5b_build_pyinstaller_installer(embedded=True)),
        ("打包证书安装器", step2b_build_cert_installer),
        ("签名安装程序和证书安装器", lambda: step6_sign_exes(phase="installers")),
    ]

    failed = []
    for i, (desc, func) in enumerate(steps, 1):
        try:
            ok = func()
            if not ok:
                failed.append(desc)
                log(f"!!! 步骤{i}失败: {desc}")
        except Exception as e:
            failed.append(desc)
            log(f"!!! 步骤{i}异常: {desc} - {e}")

    elapsed = time.time() - start_time
    print()
    print("#" * 60)
    if failed:
        print(f"#  打包完成（有 {len(failed)} 个步骤失败）")
        for f in failed:
            print(f"#    ✗ {f}")
    else:
        print(f"#  全部打包完成!")
    print(f"#  耗时: {elapsed:.1f} 秒")
    print(f"#  输出目录: {os.path.abspath(OUTPUT_DIR)}")
    print(f"#    - {APP_NAME}_{VERSION_NUM}_full.zip  （完整程序包，含 PyQt5+ffmpeg/bento4/mpv，供内嵌版/MSIX）")
    print(f"#    - {APP_NAME}_{VERSION_NUM}.zip  （云端精简包，已剥离 PyQt5，仅 mpv，首次启动在线下载 PyQt5）")
    print(f"#    - {VERSION_NUM}_installer.exe  （云端版安装程序，小体积）")
    print(f"#    - {VERSION_NUM}_installer_embedded.exe  （内嵌版安装程序，含完整程序）")
    print("#" * 60)
    print()

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
