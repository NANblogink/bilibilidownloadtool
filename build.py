#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

sys.path.insert(0, SCRIPT_DIR)
from app_config import (
    APP_NAME as APP_NAME_CN,
    APP_NAME_EN,
    APP_VERSION,
    VERSION_NUM,
    APP_DESCRIPTION,
)

APP_NAME = APP_NAME_EN
APP_NAME_ZH = APP_NAME_CN
MAIN_SCRIPT = "main.py"
UNINSTALLER_SCRIPT = "uninstaller.py"
INSTALLER_SCRIPT = "installer.py"
VERSION_FILE = "version_info.win"

DIST_DIR = os.path.join(SCRIPT_DIR, "dist")
BUILD_DIR = os.path.join(SCRIPT_DIR, "build")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")

PYINSTALLER_BASE = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--noupx",
    f"--version-file={os.path.join(SCRIPT_DIR, VERSION_FILE)}",
]

MAIN_EXTRA_ARGS = [
    "--name", APP_NAME,
    "--onedir",
    "--windowed",
    "--contents-directory", "_internal",
    "--icon=logo.ico" if os.path.exists(os.path.join(SCRIPT_DIR, "logo.ico")) else "",
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "scipy",
    "--exclude-module", "PIL",
    "--exclude-module", "streamlit",
    "--exclude-module", "rich",
    f"--add-data={os.path.join(SCRIPT_DIR, 'version_info.json')};.",
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
    "--hidden-import", "live_parser",
    "--hidden-import", "live_tab",
    "--hidden-import", "audio_parser",
    "--hidden-import", "audio_tab",
    MAIN_SCRIPT,
]
if os.path.exists(os.path.join(SCRIPT_DIR, 'logo.ico')):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={os.path.join(SCRIPT_DIR, 'logo.ico')};.")
    MAIN_EXTRA_ARGS.insert(-1, "--icon=logo.ico")
if os.path.exists(os.path.join(SCRIPT_DIR, 'logo.png')):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={os.path.join(SCRIPT_DIR, 'logo.png')};.")
if os.path.exists(os.path.join(SCRIPT_DIR, 'logo_alt_kaisui.ico')):
    MAIN_EXTRA_ARGS.insert(-1, f"--add-data={os.path.join(SCRIPT_DIR, 'logo_alt_kaisui.ico')};.")

UNINSTALL_EXTRA_ARGS = [
    "--name", "uninstaller",
    "--onefile",
    "--windowed",
    "--icon=logo.ico" if os.path.exists(os.path.join(SCRIPT_DIR, "logo.ico")) else "",
    "--hidden-import", "PyQt5.sip",
    "--hidden-import", "PyQt5.QtCore",
    "--hidden-import", "PyQt5.QtGui",
    "--hidden-import", "PyQt5.QtWidgets",
    UNINSTALLER_SCRIPT,
]

CERT_INSTALLER_SCRIPT = "cert_installer.py"
CERT_INSTALLER_EXTRA_ARGS = [
    "--name", "cert_installer",
    "--onefile",
    "--console",
    "--icon=logo.ico" if os.path.exists(os.path.join(SCRIPT_DIR, "logo.ico")) else "",
    CERT_INSTALLER_SCRIPT,
]

INSTALLER_EXTRA_ARGS = [
    "--name", f"{VERSION_NUM}_installer",
    "--onefile",
    "--windowed",
    "--icon=logo.ico" if os.path.exists(os.path.join(SCRIPT_DIR, "logo.ico")) else "",
    "--hidden-import", "PyQt5.sip",
    "--hidden-import", "PyQt5.QtCore",
    "--hidden-import", "PyQt5.QtGui",
    "--hidden-import", "PyQt5.QtWidgets",
    INSTALLER_SCRIPT,
]


def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def run_cmd(cmd, description):
    log(f">>> {description}")
    log(f"    命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        log(f"!!! {description} 失败")
        return False
    log(f"<<< {description} 完成")
    return True


def clean_build_dirs():
    for d in [DIST_DIR, BUILD_DIR, OUTPUT_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d, ignore_errors=True)
            log(f"已清理: {d}")
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def step1_build_main():
    log("=" * 60)
    log("步骤1: 打包主程序")
    log("=" * 60)

    cmd = PYINSTALLER_BASE + [a for a in MAIN_EXTRA_ARGS if a]
    return run_cmd(cmd, "打包主程序")


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

    if not os.path.exists(os.path.join(SCRIPT_DIR, CERT_INSTALLER_SCRIPT)):
        log(f"  {CERT_INSTALLER_SCRIPT} 不存在，跳过")
        return True

    cmd = PYINSTALLER_BASE + [a for a in CERT_INSTALLER_EXTRA_ARGS if a]
    if not run_cmd(cmd, "打包证书安装器"):
        return False

    # 复制 cert_installer.exe 和证书文件到 output 目录
    src_exe = os.path.join(DIST_DIR, "cert_installer.exe")
    cer_file = os.path.join(SCRIPT_DIR, "BilibiliDownloader_dev.cer")

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

    cer_file = os.path.join(SCRIPT_DIR, "BilibiliDownloader_dev.cer")
    if not os.path.exists(cer_file):
        log("  [警告] 未找到 BilibiliDownloader_dev.cer（需先运行 sign_exes.ps1 生成证书）")
        log("  跳过证书复制（主程序和安装程序将无法自动安装证书）")
        return True  # 不算失败，证书是可选的

    dst = os.path.join(main_dir, "BilibiliDownloader_dev.cer")
    shutil.copy2(cer_file, dst)
    size_kb = os.path.getsize(dst) / 1024
    log(f"已复制证书: BilibiliDownloader_dev.cer ({size_kb:.1f} KB)")
    return True


def step3b_copy_tools():
    log("=" * 60)
    log("步骤3b: 复制工具到 _internal 目录")
    log("=" * 60)

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    internal_dir = os.path.join(main_dir, '_internal')
    os.makedirs(internal_dir, exist_ok=True)

    ffmpeg_src = os.path.join(SCRIPT_DIR, "ffmpeg", "bin")
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
    else:
        log("  ffmpeg 目录不存在，跳过")

    mpv_src = os.path.join(SCRIPT_DIR, "mpv")
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
    else:
        log("  mpv 目录不存在，跳过")

    bento4_src = os.path.join(SCRIPT_DIR, "bento4")
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


def step4_zip_folder():
    log("=" * 60)
    log("步骤4: 压缩主程序文件夹为zip")
    log("=" * 60)

    main_dir = os.path.join(DIST_DIR, APP_NAME)
    if not os.path.isdir(main_dir):
        log(f"!!! 主程序目录不存在: {main_dir}")
        return False

    zip_name = f"{APP_NAME}_{VERSION_NUM}.zip"
    zip_path = os.path.join(OUTPUT_DIR, zip_name)

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
    log(f"压缩完成: {zip_name}")
    log(f"  文件数: {count}, 原始大小: {total_size / 1024 / 1024:.1f} MB")
    log(f"  ZIP大小: {zip_size:.1f} MB, 压缩率: {ratio:.0f}%")
    log(f"  路径: {os.path.abspath(zip_path)}")
    return True


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

    iss_path = os.path.join(SCRIPT_DIR, "setup.iss")
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
        inno_output = os.path.join(SCRIPT_DIR, "Output")
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
        zip_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}_{VERSION_NUM}.zip")
        if not os.path.isfile(zip_path):
            log(f"!!! 内嵌版需要 zip 包: {zip_path}")
            return False
        zip_size_mb = os.path.getsize(zip_path) / 1024 / 1024
        log(f"  内嵌 zip 包: {zip_size_mb:.1f} MB")

    name = f"{VERSION_NUM}_installer_embedded" if embedded else f"{VERSION_NUM}_installer"
    args = [
        "--name", name,
        "--onefile",
        "--windowed",
        "--icon=logo.ico" if os.path.exists(os.path.join(SCRIPT_DIR, "logo.ico")) else "",
        "--hidden-import", "PyQt5.sip",
        "--hidden-import", "PyQt5.QtCore",
        "--hidden-import", "PyQt5.QtGui",
        "--hidden-import", "PyQt5.QtWidgets",
    ]

    if embedded:
        zip_path = os.path.join(OUTPUT_DIR, f"{APP_NAME}_{VERSION_NUM}.zip")
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


def main():
    start_time = time.time()
    print()
    print("#" * 60)
    print(f"#  {APP_NAME_ZH} {APP_VERSION} 自动化打包")
    print(f"#  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("#" * 60)
    print()

    clean_build_dirs()

    has_iscc = _find_iscc() is not None

    steps = [
        ("打包主程序（文件夹方式）", step1_build_main),
        ("复制工具到 _internal 目录", step3b_copy_tools),
        ("打包卸载程序（单文件）", step2_build_uninstaller),
        ("复制卸载程序到主程序文件夹", step3_copy_uninstaller),
        ("复制开发者证书到主程序文件夹", step3c_copy_cert),
        ("签名主程序和卸载程序", lambda: step6_sign_exes(phase="dist")),
        ("压缩主程序文件夹为zip", step4_zip_folder),
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
    print(f"#    - {APP_NAME}_{VERSION_NUM}.zip  （完整程序包）")
    print(f"#    - {VERSION_NUM}_installer.exe  （云端版安装程序，小体积）")
    print(f"#    - {VERSION_NUM}_installer_embedded.exe  （内嵌版安装程序，含完整程序）")
    print("#" * 60)
    print()

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
