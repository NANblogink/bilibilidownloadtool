#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Inno Setup 构建标准 Windows 安装程序。

流程：
  1. 用 PyInstaller 把部署工具打成单文件 deploy_helper.exe
  2. 调用 ISCC.exe 编译 setup.iss，产出标准安装包

用法：
    python other/windows/build_installer.py                 # 在线安装版
    python other/windows/build_installer.py --embed-wheels  # 内置 PyQt5（离线）
    python other/windows/build_installer.py --embed-all     # 完全离线
    python other/windows/build_installer.py --source dist_win/BilibiliDownloader

产物：output/BilibiliDownloader_Setup_<版本>.exe
"""
import argparse
import os
import shutil
import subprocess
import sys
import time


def _find_root(start):
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
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))

from app_config import VERSION_NUM  # noqa: E402

BUILD = os.path.join(ROOT, "build", "_setup")
OUTPUT = os.path.join(ROOT, "output")
ISS = os.path.join(ROOT, "setup.iss")


def log(m):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), m), flush=True)


def make_icon():
    """生成安装包用的合法多尺寸 ICO。

    背景：仓库根目录的 logo.ico 曾经是「PNG 改扩展名」的假 ICO，
    Inno Setup 会以 "Resource update error: File is too large" 拒绝，
    Windows 任务栏也会显示空白图标。该文件现已修正为真正的多尺寸 ICO。

    这里仍从 logo.png 重新生成一份安装包专用 ICO（尺寸/裁剪可控，
    且不受仓库文件被改回的影响），属于稳妥做法。
    """
    os.makedirs(BUILD, exist_ok=True)
    out = os.path.join(BUILD, "app.ico")
    if os.path.isfile(out) and os.path.getsize(out) > 1024:
        return out
    src = None
    for c in ("logo.png", "assets/images/logo.png", "assets/logo.png"):
        p = os.path.join(ROOT, c)
        if os.path.isfile(p):
            src = p
            break
    if not src:
        log("警告：未找到 logo.png，安装包将使用默认图标")
        return None
    try:
        from PIL import Image
    except ImportError:
        log("警告：未安装 Pillow，跳过图标生成")
        return None
    img = Image.open(src).convert("RGBA")
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
             (128, 128), (256, 256)]
    img.save(out, format="ICO", sizes=sizes)
    log("生成安装包图标 app.ico (%.1f KB)" % (os.path.getsize(out) / 1024.0))
    return out


def find_iscc():
    """定位 Inno Setup 编译器。"""
    cands = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"),
                     "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)",
                                    r"C:\Program Files (x86)"),
                     "Inno Setup 6", "ISCC.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""),
                     "Programs", "Inno Setup 6", "ISCC.exe"),
    ]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    # 兜底：从 PATH 找
    w = shutil.which("ISCC") or shutil.which("iscc")
    return w


def build_helper():
    """把 deploy_helper.py 打成单文件 exe（目标机器无需 Python）。"""
    os.makedirs(BUILD, exist_ok=True)
    helper_py = os.path.join(ROOT, "other", "windows", "deploy_helper.py")
    if not os.path.isfile(helper_py):
        raise RuntimeError("缺少 deploy_helper.py: %s" % helper_py)

    args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "deploy_helper",
        "--distpath", BUILD,
        "--workpath", os.path.join(BUILD, "work"),
        "--specpath", os.path.join(BUILD, "spec"),
        "--paths", os.path.join(ROOT, "core"),
        "--paths", ROOT,
        "--hidden-import", "python_deploy",
        "--hidden-import", "app_config",
    ]
    for m in ("PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
              "matplotlib", "numpy", "pandas", "scipy", "PIL", "streamlit"):
        args += ["--exclude-module", m]
    args.append(helper_py)

    log("构建部署工具 deploy_helper.exe")
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError("deploy_helper 构建失败")

    exe = os.path.join(BUILD, "deploy_helper.exe")
    if not os.path.isfile(exe):
        raise RuntimeError("未生成 deploy_helper.exe")
    log("deploy_helper.exe %.1f MB" % (os.path.getsize(exe) / 1048576.0))
    return exe


def find_python_zip():
    for d in (os.path.join(ROOT, "runtime"), ROOT):
        try:
            for f in sorted(os.listdir(d)):
                low = f.lower()
                if low.startswith("python-") and low.endswith(".zip"):
                    return os.path.join(d, f)
        except Exception:
            continue
    return None


def find_wheels():
    for cand in (os.path.join(ROOT, "wheels"),
                 os.path.join(ROOT, "cache", "wheels")):
        if os.path.isdir(cand) and any(
                f.lower().endswith(".whl") for f in os.listdir(cand)):
            return cand
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=None,
                    help="主程序目录（默认 dist_win/BilibiliDownloader）")
    ap.add_argument("--embed-wheels", action="store_true")
    ap.add_argument("--embed-python", action="store_true")
    ap.add_argument("--embed-all", action="store_true")
    ap.add_argument("--embed-tools", action="store_true",
                    help="内置 ffmpeg / Bento4（离线可用，约 +69 MB）")
    ap.add_argument("--skip-helper", action="store_true",
                    help="复用已构建的 deploy_helper.exe")
    a = ap.parse_args()

    ew = a.embed_wheels or a.embed_all
    ep = a.embed_python or a.embed_all
    et = a.embed_tools or a.embed_all

    iscc = find_iscc()
    if not iscc:
        log("未找到 Inno Setup 编译器 ISCC.exe")
        log("请安装：winget install JRSoftware.InnoSetup")
        return 2
    log("ISCC: %s" % iscc)

    src = a.source or os.path.join(ROOT, "dist_win", "BilibiliDownloader")
    if not os.path.isdir(src):
        log("主程序目录不存在: %s" % src)
        log("请先运行 python other/windows/build_main.py（或 build_lean.py）")
        return 3
    src = os.path.abspath(src)
    log("主程序目录: %s" % src)

    if ew and not find_wheels():
        log("警告：未找到 wheels/，请先运行 fetch_wheels.py；改为在线安装")
        ew = False
    if ep and not find_python_zip():
        log("警告：未找到 python-embed zip，请先运行 fetch_python.py")
        ep = False

    helper = os.path.join(BUILD, "deploy_helper.exe")
    if not a.skip_helper or not os.path.isfile(helper):
        helper = build_helper()

    icon = make_icon()

    os.makedirs(OUTPUT, exist_ok=True)

    # 在线版独立文件名
    online_only = "0" if ep else "1"

    args = [
        iscc,
        "/DSourceDir=%s" % src,
        "/DOutputDir=%s" % OUTPUT,
        "/DHelperExe=%s" % os.path.abspath(helper),
        "/DRootDir=%s" % ROOT,
        "/DEmbedWheels=%s" % ("1" if ew else "0"),
        "/DEmbedPython=%s" % ("1" if ep else "0"),
        "/DEmbedTools=%s" % ("1" if et else "0"),
        "/DOnlineOnly=%s" % online_only,
        ISS,
    ]
    if icon:
        args.insert(-1, "/DIconFile=%s" % os.path.abspath(icon))
    log("编译 setup.iss（内置 wheel=%s, 内置 Python=%s）" % (ew, ep))
    r = subprocess.run(args, cwd=ROOT)

    if r.returncode != 0:
        log("ISCC 编译失败，退出码 %d" % r.returncode)
        return r.returncode

    suffix = "_online" if online_only == "1" else ""
    out = os.path.join(OUTPUT, "BilibiliDownloader_Setup_%s%s.exe" % (VERSION_NUM, suffix))
    if os.path.isfile(out):
        log("安装包: %s (%.1f MB)" % (out, os.path.getsize(out) / 1048576.0))
    else:
        log("编译成功，但未找到预期产物；请检查 output/ 目录")
    return 0


if __name__ == "__main__":
    sys.exit(main())
