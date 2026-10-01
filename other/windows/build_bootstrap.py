#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建极简引导器（约 5~10 MB）。

产物不含 Python 运行时、不含 PyQt5：首次运行时自动下载部署，
用户无需安装任何东西。适合网络条件较好的分发场景。

用法：
    python other/windows/build_bootstrap.py
    python other/windows/build_bootstrap.py --distpath=dist_boot
    python other/windows/build_bootstrap.py --embed-wheels   # 内置 wheel（离线回退）
    python other/windows/build_bootstrap.py --embed-python   # 内置 Python 包（完全离线）

产物：dist_boot/BilibiliDownloaderBootstrap/BilibiliDownloaderBootstrap.exe
"""
import argparse
import os
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

from app_config import APP_NAME_EN  # noqa: E402

BOOT_NAME = APP_NAME_EN + "Bootstrap"
DIST = os.path.join(ROOT, "dist_boot")
WORK = os.path.join(ROOT, "build", "_bootstrap")


def log(m):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), m), flush=True)


_ap = argparse.ArgumentParser()
_ap.add_argument("--distpath", default=DIST)
_ap.add_argument("--workpath", default=WORK)
_ap.add_argument("--embed-wheels", action="store_true",
                 help="把 wheels/ 打进引导器（离线安装 PyQt5）")
_ap.add_argument("--embed-python", action="store_true",
                 help="把 Python embeddable zip 打进引导器（完全离线）")
_ap.add_argument("--name", default=BOOT_NAME)
_args = _ap.parse_args()

args = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--noupx",
    "--name", _args.name,
    "--onedir",
    "--windowed",
    "--distpath=" + _args.distpath,
    "--workpath=" + _args.workpath,
    "--specpath=" + _args.workpath,
    # 引导器只需这两个模块
    "--hidden-import", "python_deploy",
    "--hidden-import", "tkinter",
    "--collect-submodules", "tkinter",
    # 明确排除，保持体积最小
]

for m in ("PyQt5", "PyQt5.sip", "PyQt5.QtCore", "PyQt5.QtGui",
          "PyQt5.QtWidgets", "PyQt5.QtNetwork", "PyQt5.QtWebEngineWidgets",
          "matplotlib", "numpy", "pandas", "scipy", "PIL", "streamlit",
          "rich", "requests", "curl_cffi", "qrcode", "Crypto"):
    args += ["--exclude-module", m]

if os.path.isfile(os.path.join(ROOT, "logo.ico")):
    args.append("--icon=" + os.path.join(ROOT, "logo.ico"))

# ---- 运行时zip ----
if _args.embed_python:
    found = None
    for d in (os.path.join(ROOT, "runtime"), ROOT):
        try:
            for f in os.listdir(d):
                if f.lower().startswith("python-") and f.lower().endswith(".zip"):
                    found = os.path.join(d, f)
                    break
        except Exception:
            pass
        if found:
            break
    if found:
        log("内置 Python 运行时: %s" % os.path.basename(found))
        args.append("--add-data=%s;." % found)
    else:
        log("警告：未找到 python-*-embed-*.zip，无法完全离线。")
        log("      请先运行 other/windows/fetch_python.py 生成。")

# ---- 附带的 wheel ----
wheels_dir = None
for cand in (os.path.join(ROOT, "wheels"),
             os.path.join(ROOT, "cache", "wheels")):
    if os.path.isdir(cand) and any(
            f.lower().endswith(".whl") for f in os.listdir(cand)):
        wheels_dir = cand
        break

if _args.embed_wheels and wheels_dir:
    n = len([f for f in os.listdir(wheels_dir) if f.lower().endswith(".whl")])
    log("内置 PyQt5 组件: %s (%d 个 wheel)" % (wheels_dir, n))
    args.append("--add-data=%s;wheels" % wheels_dir)
elif _args.embed_wheels:
    log("警告：未找到 wheels/ 目录，PyQt5 将需要联网下载。")

args.append(os.path.join(ROOT, "boot_bootstrap.py"))

log("构建极简引导器")
log("distpath=%s" % _args.distpath)
log("embed_wheels=%s embed_python=%s" % (_args.embed_wheels,
                                        _args.embed_python))
r = subprocess.run(args, cwd=ROOT)
log("PyInstaller 退出码: %d" % r.returncode)

if r.returncode == 0:
    out = os.path.join(_args.distpath, _args.name)
    if os.path.isdir(out):
        tot = sum(os.path.getsize(os.path.join(dp, f))
                  for dp, _, fs in os.walk(out) for f in fs)
        log("产物: %s (%.1f MB)" % (out, tot / 1048576.0))

sys.exit(r.returncode)
