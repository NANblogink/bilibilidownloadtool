#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MSIX 打包脚本 - 上架 Microsoft Store 用

依赖:
  - PyInstaller 已打包 dist/BilibiliDownloader/ (先运行 build.py)
  - Windows SDK (makeappx.exe)
  - Pillow

用法: python build_msix.py
"""
import os
import sys
import shutil
import subprocess
import time
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(SCRIPT_DIR, "dist")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output")
MAIN_APP_DIR = os.path.join(DIST_DIR, "BilibiliDownloader")
APP_EXE_NAME = "BilibiliDownloader.exe"
APP_DISPLAY_NAME = "B站视频下载工具"
APP_DESCRIPTION = "B站视频解析下载工具"

PACKAGE_NAME = "80F5BBD6.B"
PUBLISHER = "CN=2F4AE534-61FA-4616-9EDE-128FE5A6F25E"
PUBLISHER_DISPLAY_NAME = "寒烟似雪"
LOCAL_SIGN_THUMBPRINT = "8F51958C15FAA09938B16A6A1195C13649C70E62"
STORE_ID = "9P4JG61P3XW6"
APP_VERSION = "2.1.9.0"

SDK_BASE = r"C:\Program Files (x86)\Windows Kits\10\bin"
MAKEAPPX = None
SIGNTOOL = None
MAKEPRI = None

STAGING_DIR = os.path.join(SCRIPT_DIR, "msix_staging")
ASSETS_DIR = os.path.join(STAGING_DIR, "Assets")
ONEFILE_DIR = os.path.join(SCRIPT_DIR, "dist_onefile")


def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")


def find_sdk_tools():
    global MAKEAPPX, SIGNTOOL, MAKEPRI
    if not os.path.isdir(SDK_BASE):
        log(f"!!! 找不到 Windows SDK 目录: {SDK_BASE}")
        log("    请安装 Windows SDK: https://developer.microsoft.com/windows/downloads/windows-sdk/")
        return False
    versions = sorted([d for d in os.listdir(SDK_BASE) if d.startswith("10.") and os.path.isdir(os.path.join(SDK_BASE, d))])
    log(f"找到 SDK 版本: {versions}")
    for v in reversed(versions):
        for arch in ("x64", "x86"):
            mp = os.path.join(SDK_BASE, v, arch, "makeappx.exe")
            st = os.path.join(SDK_BASE, v, arch, "signtool.exe")
            mpri = os.path.join(SDK_BASE, v, arch, "makepri.exe")
            if os.path.isfile(mp) and not MAKEAPPX:
                MAKEAPPX = mp
            if os.path.isfile(st) and not SIGNTOOL:
                SIGNTOOL = st
            if os.path.isfile(mpri) and not MAKEPRI:
                MAKEPRI = mpri
        if MAKEAPPX and SIGNTOOL:
            break
    if MAKEAPPX:
        log(f"makeappx: {MAKEAPPX}")
    if SIGNTOOL:
        log(f"signtool: {SIGNTOOL}")
    return bool(MAKEAPPX)


def generate_icons():
    log("=" * 60)
    log("步骤1: 生成图标资源")
    log("=" * 60)

    logo_path = os.path.join(SCRIPT_DIR, "logo.png")
    if not os.path.isfile(logo_path):
        log(f"!!! 找不到 logo.png: {logo_path}")
        return False

    os.makedirs(ASSETS_DIR, exist_ok=True)
    img = Image.open(logo_path).convert("RGBA")

    def make_icon(size, filename, padding_ratio=0.08):
        if isinstance(size, int):
            w = h = size
        else:
            w, h = size
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        logo_w, logo_h = img.size
        max_dim = max(logo_w, logo_h)
        target = (1 - 2 * padding_ratio) * min(w, h)
        ratio = target / max_dim
        nw, nh = int(logo_w * ratio), int(logo_h * ratio)
        if nw > 0 and nh > 0:
            resized = img.resize((nw, nh), Image.LANCZOS)
            x = (w - nw) // 2
            y = (h - nh) // 2
            canvas.paste(resized, (x, y), resized)
        canvas.save(os.path.join(ASSETS_DIR, filename), "PNG")

    def make_splash(w, h, filename):
        canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
        logo_w, logo_h = img.size
        target_h = h * 0.5
        ratio = target_h / logo_h
        nw, nh = int(logo_w * ratio), int(target_h)
        if nw > w:
            ratio = w * 0.9 / logo_w
            nw, nh = int(logo_w * ratio), int(logo_h * ratio)
        resized = img.resize((nw, nh), Image.LANCZOS)
        x = (w - nw) // 2
        y = (h - nh) // 2
        canvas.paste(resized, (x, y), resized)
        canvas.save(os.path.join(ASSETS_DIR, filename), "PNG")

    make_icon(44, "Square44x44Logo.png")
    make_icon(150, "Square150x150Logo.png")
    make_icon(310, "Square310x310Logo.png")
    make_icon((310, 150), "Wide310x150Logo.png")
    make_icon(50, "StoreLogo.png")
    make_splash(620, 300, "SplashScreen.png")

    for size in [16, 24, 32, 48, 256]:
        make_icon(size, f"Square44x44Logo.targetsize-{size}.png")
        make_icon(size, f"Square44x44Logo.targetsize-{size}_altform-unplated.png")

    make_icon(55, "Square44x44Logo.scale-125.png")
    make_icon(66, "Square44x44Logo.scale-150.png")
    make_icon(88, "Square44x44Logo.scale-200.png")
    make_icon(176, "Square44x44Logo.scale-400.png")
    make_icon(300, "Square150x150Logo.scale-200.png")
    make_icon(100, "StoreLogo.scale-200.png")
    make_icon((620, 300), "SplashScreen.scale-200.png")

    count = len([f for f in os.listdir(ASSETS_DIR) if f.endswith('.png')])
    log(f"生成 {count} 个图标文件到 {ASSETS_DIR}")
    return True


def generate_manifest():
    log("=" * 60)
    log("步骤2: 生成 AppxManifest.xml")
    log("=" * 60)

    manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:uap3="http://schemas.microsoft.com/appx/manifest/uap/windows10/3"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  xmlns:desktop="http://schemas.microsoft.com/appx/manifest/desktop/windows10"
  IgnorableNamespaces="uap uap3 rescap desktop">

  <Identity Name="{PACKAGE_NAME}"
            Publisher="{PUBLISHER}"
            Version="{APP_VERSION}"
            ProcessorArchitecture="x64"/>

  <Properties>
    <DisplayName>{APP_DISPLAY_NAME}</DisplayName>
    <PublisherDisplayName>{PUBLISHER_DISPLAY_NAME}</PublisherDisplayName>
    <Description>{APP_DESCRIPTION}</Description>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>

  <Resources>
    <Resource Language="zh-CN"/>
  </Resources>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22621.0"/>
  </Dependencies>

  <Applications>
    <Application Id="BilibiliDownloader"
                 Executable="{APP_EXE_NAME}"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="{APP_DISPLAY_NAME}"
        Description="{APP_DESCRIPTION}"
        BackgroundColor="transparent"
        Square150x150Logo="Assets\\Square150x150Logo.png"
        Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png"
                         Square310x310Logo="Assets\\Square310x310Logo.png"
                         ShortName="{APP_DISPLAY_NAME}">
        </uap:DefaultTile>
        <uap:SplashScreen Image="Assets\\SplashScreen.png"/>
      </uap:VisualElements>
    </Application>
  </Applications>

  <Capabilities>
    <Capability Name="internetClient"/>
    <rescap:Capability Name="runFullTrust"/>
  </Capabilities>
</Package>'''
    manifest_path = os.path.join(STAGING_DIR, "AppxManifest.xml")
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest)
    log(f"已生成: {manifest_path}")
    return True


def build_onefile_exe():
    """用 PyInstaller --onefile 打包主程序（MSIX 兼容性更好）。
    --onefile 的 bootloader 把嵌入文件提取到 %TEMP% 后再启动，
    不依赖 _internal/ 目录查找机制，完美绕开 MSIX 容器的路径限制。"""
    log("=" * 60)
    log("步骤3a: PyInstaller --onefile 打包")
    log("=" * 60)

    exe_path = os.path.join(ONEFILE_DIR, APP_EXE_NAME)

    # 若源码/资源比现有 exe 新，则视为过期，必须重建；否则 MSIX 会重复打包旧内容，
    # 造成"版本号已变但功能/资源未更新"的假更新问题。
    def _stale(exe):
        if not os.path.isfile(exe):
            return True
        exe_mtime = os.path.getmtime(exe)
        watch = [
            os.path.join(SCRIPT_DIR, "app_config.py"),
            os.path.join(SCRIPT_DIR, "build.py"),
            os.path.join(SCRIPT_DIR, "ui.py"),
            os.path.join(SCRIPT_DIR, "version_info.json"),
            os.path.join(SCRIPT_DIR, "logo.png"),
            os.path.join(SCRIPT_DIR, "myqrcode.png"),
            os.path.join(SCRIPT_DIR, "qunqrcode.png"),
            os.path.join(_ICONS_DIR := os.path.join(SCRIPT_DIR, "assets", "icons"), "qq_blue.svg"),
            os.path.join(SCRIPT_DIR, "main.py"),
            os.path.join(SCRIPT_DIR, "bilibili_parser.py"),
        ]
        for w in watch:
            if os.path.isfile(w) and os.path.getmtime(w) > exe_mtime:
                return True
        return False

    if "--force" in sys.argv or _stale(exe_path):
        for d in (ONEFILE_DIR, os.path.join(SCRIPT_DIR, "build_onefile")):
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
                log(f"已清理陈旧构建目录: {d}")
    else:
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        log(f"已存在且最新的 --onefile exe ({size_mb:.1f} MB)，跳过重建")
        return True

    # 复用 build.py 的参数配置
    from build import MAIN_EXTRA_ARGS, PYINSTALLER_BASE

    # 过滤 --onedir，替换为 --onefile
    args_no_onedir = [a for a in MAIN_EXTRA_ARGS if a not in ("--onedir", "--onefile")]

    cmd = PYINSTALLER_BASE.copy()
    cmd.extend(["--onefile"])
    cmd.extend(args_no_onedir)
    cmd.extend([
        "--distpath", ONEFILE_DIR,
        "--workpath", os.path.join(SCRIPT_DIR, "build_onefile"),
        "--specpath", SCRIPT_DIR,
    ])
    cmd = [c for c in cmd if c]

    log(f"命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        log("!!! PyInstaller --onefile 构建失败")
        return False

    if not os.path.isfile(exe_path):
        log(f"!!! 未找到输出 exe: {exe_path}")
        return False

    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    log(f"已生成: {exe_path} ({size_mb:.1f} MB)")
    return True


def copy_app_files():
    """把 --onefile 构建的单个 exe 复制到 staging。"""
    log("=" * 60)
    log("步骤3: 复制应用文件到 staging 目录")
    log("=" * 60)

    exe_path = os.path.join(ONEFILE_DIR, APP_EXE_NAME)
    if not os.path.isfile(exe_path):
        log(f"!!! --onefile exe 不存在: {exe_path}")
        return False

    log(f"从 {ONEFILE_DIR} 复制到 {STAGING_DIR}")
    dst = os.path.join(STAGING_DIR, APP_EXE_NAME)
    shutil.copy2(exe_path, dst)
    size_mb = os.path.getsize(dst) / (1024 * 1024)
    log(f"已复制: {dst} ({size_mb:.1f} MB)")

    # 复制 version_info.json（供读取版本号）
    vi_src = os.path.join(SCRIPT_DIR, "version_info.json")
    if os.path.isfile(vi_src):
        shutil.copy2(vi_src, os.path.join(STAGING_DIR, "version_info.json"))
        log("已复制 version_info.json")

    return True


def copy_tools():
    """复制 ffmpeg/ffprobe、mpv、bento4 到 staging 根目录（与 exe 同级）。
    --onefile 模式没有 _internal 目录，工具放在 exe 同级目录即可，
    app 里的查找逻辑（env_checker._find_ffmpeg 等）已支持多路径匹配。"""
    log("=" * 60)
    log("步骤3b: 复制工具到 staging 根目录")
    log("=" * 60)

    # ffmpeg / ffprobe
    ffmpeg_src = os.path.join(SCRIPT_DIR, "ffmpeg", "bin")
    ffmpeg_dst = os.path.join(STAGING_DIR, "ffmpeg", "bin")
    if os.path.isdir(ffmpeg_src):
        os.makedirs(ffmpeg_dst, exist_ok=True)
        copied = 0
        for f in ("ffmpeg.exe", "ffprobe.exe"):
            src = os.path.join(ffmpeg_src, f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(ffmpeg_dst, f))
                copied += os.path.getsize(src)
                log(f"  已复制: ffmpeg/bin/{f} ({os.path.getsize(src)/1024/1024:.1f} MB)")
        log(f"  ffmpeg 合计: {copied/1024/1024:.1f} MB")
    else:
        log("  !!! ffmpeg/bin 目录不存在，工具将缺失")
        return False

    # mpv（只保留运行必需文件）
    mpv_src = os.path.join(SCRIPT_DIR, "mpv")
    mpv_dst = os.path.join(STAGING_DIR, "mpv")
    mpv_keep = ("mpv.exe", "mpv.com", "vulkan-1.dll", "mpv-register.bat", "mpv-unregister.bat")
    if os.path.isdir(mpv_src):
        os.makedirs(mpv_dst, exist_ok=True)
        copied = 0
        for f in os.listdir(mpv_src):
            src = os.path.join(mpv_src, f)
            if os.path.isfile(src) and f in mpv_keep:
                shutil.copy2(src, os.path.join(mpv_dst, f))
                copied += os.path.getsize(src)
                log(f"  已复制: mpv/{f} ({os.path.getsize(src)/1024/1024:.1f} MB)")
        log(f"  mpv 合计: {copied/1024/1024:.1f} MB")

    # UPX 无损压缩（与现有程序一致，减小体积）
    from build import upx_compress
    for f in ("ffmpeg.exe", "ffprobe.exe"):
        upx_compress(os.path.join(ffmpeg_dst, f))
    for f in mpv_keep:
        if f.lower().endswith((".exe", ".dll", ".com")):
            upx_compress(os.path.join(mpv_dst, f))

    # bento4
    bento4_src = os.path.join(SCRIPT_DIR, "bento4")
    if os.path.isdir(bento4_src):
        bin_src = None
        for root, dirs, files in os.walk(bento4_src):
            if 'bin' in dirs:
                bin_src = os.path.join(root, 'bin')
                break
        if bin_src and os.path.isdir(bin_src):
            bin_dst = os.path.join(STAGING_DIR, "bento4", "bin")
            os.makedirs(bin_dst, exist_ok=True)
            copied = 0
            count = 0
            for f in os.listdir(bin_src):
                src = os.path.join(bin_src, f)
                if os.path.isfile(src) and f.endswith('.exe'):
                    shutil.copy2(src, os.path.join(bin_dst, f))
                    copied += os.path.getsize(src)
                    count += 1
            log(f"  bento4: {count} 个 exe, {copied/1024/1024:.1f} MB")
            if not os.path.isfile(os.path.join(bin_dst, "mp4decrypt.exe")):
                log("  !!! bento4 bin 中缺少 mp4decrypt.exe")
                return False
        else:
            log("  !!! bento4 bin 目录未找到")
            return False
    else:
        log("  !!! bento4 目录不存在，工具将缺失")
        return False

    return True


def build_resources_pri():
    """用 makepri.exe 将 Resources/*.resw 编译成 resources.pri，使 MSIX 安装对话框显示中文。"""
    log("=" * 60)
    log("步骤3c: 生成 resources.pri 本地化索引")
    log("=" * 60)

    if not MAKEPRI:
        log("!!! 找不到 makepri.exe，跳过资源索引生成")
        return True

    res_dir = os.path.join(STAGING_DIR, 'Resources')
    if not os.path.isdir(res_dir):
        log("  无 Resources 目录，跳过")
        return True

    pri_file = os.path.join(STAGING_DIR, 'resources.pri')
    config_file = os.path.join(STAGING_DIR, 'priconfig.xml')
    mn_path = os.path.join(STAGING_DIR, "AppxManifest.xml")

    # Step 1: createconfig
    if os.path.exists(config_file):
        os.remove(config_file)
    cmd1 = f'"{MAKEPRI}" createconfig /cf "{config_file}" /dq zh-CN'
    log(f"  创建配置: {cmd1}")
    r1 = subprocess.run(cmd1, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
    if r1.returncode != 0 or not os.path.isfile(config_file):
        log(f"  [警告] createconfig 失败: {r1.returncode}")
        return True

    # Step 2: new
    if os.path.exists(pri_file):
        os.remove(pri_file)
    cmd2 = f'"{MAKEPRI}" new /pr "{STAGING_DIR}" /cf "{config_file}" /of "{pri_file}" /mn "{mn_path}" /o'
    log(f"  生成 PRI: {cmd2}")
    r2 = subprocess.run(cmd2, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=True)
    if os.path.isfile(pri_file):
        log(f"  已生成: resources.pri ({os.path.getsize(pri_file)/1024:.1f} KB)")
    else:
        log(f"  [警告] resources.pri 未生成 (returncode={r2.returncode})")
        if r2.stderr:
            log(f"  stderr: {r2.stderr.strip()[:200]}")
    return True


def build_msix():
    log("=" * 60)
    log("步骤4: makeappx 打包 .msix")
    log("=" * 60)

    if not MAKEAPPX:
        log("!!! makeappx.exe 未找到")
        return None

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    msix_name = f"BilibiliDownloader_{APP_VERSION}_x64.msix"
    msix_path = os.path.join(OUTPUT_DIR, msix_name)

    if os.path.exists(msix_path):
        os.remove(msix_path)

    cmd = [
        MAKEAPPX, "pack",
        "/d", STAGING_DIR,
        "/p", msix_path,
        "/v",
        "/o",
    ]
    log(f"命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        log(f"!!! makeappx 失败 (returncode={result.returncode})")
        return None

    if not os.path.isfile(msix_path):
        log(f"!!! 未生成 MSIX 文件: {msix_path}")
        return None

    size_mb = os.path.getsize(msix_path) / 1024 / 1024
    log(f"生成: {msix_path}")
    log(f"大小: {size_mb:.1f} MB")
    return msix_path


def sign_msix(msix_path):
    """用匹配 Publisher 的本地证书签名 MSIX，供本地测试安装（非商店上架用）。
    上架商店时需用未经此本地签名（或商店会重新签名）的包。"""
    log("=" * 60)
    log("步骤5: 本地签名 MSIX（测试安装用）")
    log("=" * 60)

    if not SIGNTOOL:
        log("!!! signtool.exe 未找到，跳过本地签名")
        return msix_path

    if not os.path.isfile(msix_path):
        log(f"!!! MSIX 不存在: {msix_path}")
        return msix_path

    cmd = [
        SIGNTOOL, "sign", "/fd", "SHA256", "/sha1", LOCAL_SIGN_THUMBPRINT,
        msix_path,
    ]
    log(f"命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=SCRIPT_DIR, capture_output=True, text=True, errors='replace')
    if result.returncode == 0:
        log("  本地签名成功")
    else:
        log(f"  [警告] 本地签名失败 (returncode={result.returncode}): {result.stdout.strip()[:200]}")
    return msix_path


def main():
    start_time = time.time()
    print()
    print("#" * 60)
    print(f"#  MSIX 打包 - {APP_DISPLAY_NAME} {APP_VERSION}")
    print(f"#  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"#  Store ID: {STORE_ID}")
    print("#" * 60)
    print()

    if not find_sdk_tools():
        return 1

    if os.path.exists(STAGING_DIR):
        shutil.rmtree(STAGING_DIR, ignore_errors=True)
        log(f"已清理 staging 目录: {STAGING_DIR}")
    os.makedirs(STAGING_DIR, exist_ok=True)

    steps = [
        ("生成图标资源", generate_icons),
        ("生成 AppxManifest.xml", generate_manifest),
        ("PyInstaller --onefile 打包", build_onefile_exe),
        ("复制应用文件", copy_app_files),
        ("复制内嵌工具(ffmpeg/mpv/bento4)", copy_tools),
    ]
    for desc, func in steps:
        try:
            if not func():
                log(f"!!! 步骤失败: {desc}")
                return 1
        except Exception as e:
            log(f"!!! 步骤异常: {desc} - {e}")
            import traceback
            traceback.print_exc()
            return 1

    msix_path = build_msix()
    if not msix_path:
        return 1

    msix_path = sign_msix(msix_path)

    elapsed = time.time() - start_time
    print()
    print("#" * 60)
    print(f"#  打包完成!")
    print(f"#  耗时: {elapsed:.1f} 秒")
    print(f"#  输出: {msix_path}")
    print("#")
    print("#  上架 Microsoft Store:")
    print("#    1. 登录 Partner Center: https://partner.microsoft.com/")
    print(f"#    2. 打开产品 (Store ID: {STORE_ID})")
    print("#    3. 开始提交 -> 包 -> 上传此 .msix 文件")
    print("#    4. 商店会自动用关联证书重签名，无需本地签名")
    print("#" * 60)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
