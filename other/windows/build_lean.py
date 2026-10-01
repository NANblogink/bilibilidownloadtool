#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建云端精简包（剥离 PyQt5，入口 boot.py）——复刻历史 build.py 的 step1_lean_build_main。

用法：
    python other/windows/build_lean.py
    python other/windows/build_lean.py --distpath=dist_beta/_lean   # 内测包用
    python other/windows/build_main.py --lean      # 再打 zip

产物：dist/_lean/BilibiliDownloader/（默认）
"""
import argparse
import os
import subprocess
import sys
import time


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
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
import _pathsetup  # noqa: E402,F401
from app_config import APP_NAME_EN as APP_NAME  # noqa: E402

LEAN_DIST = os.path.join(ROOT, "dist", "_lean")
BUILD_LEAN = os.path.join(ROOT, "build", "_lean")


def log(m):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), m), flush=True)


_ap = argparse.ArgumentParser()
_ap.add_argument("--distpath", default=LEAN_DIST, help="PyInstaller 输出目录")
_ap.add_argument("--workpath", default=BUILD_LEAN, help="PyInstaller 中间目录")
_ap.add_argument("--embed-wheels", action="store_true",
                 help="把 wheels/ 打进包内（绿色免安装版用；"
                      "标准安装包不需要，会被安装程序单独提供）")
_ap.add_argument("--no-wheels", action="store_true",
                 help="明确不内置 wheel（默认行为，保留以兼容旧调用）")
_args = _ap.parse_args()

LEAN_DIST = _args.distpath
BUILD_LEAN = _args.workpath

# 默认不内置wheel
if not _args.embed_wheels:
    _args.no_wheels = True


args = [
    sys.executable, "-m", "PyInstaller",
    "--noconfirm", "--clean", "--noupx",
    "--version-file=" + os.path.join(ROOT, "version_info.win"),
    "--name", APP_NAME,
    "--onedir",
    "--windowed",
    "--icon=" + os.path.join(ROOT, "logo.ico"),
    "--distpath=" + LEAN_DIST,
    "--workpath=" + BUILD_LEAN,
    "--specpath=" + BUILD_LEAN,
    # 须加core分析路径
    # 否则hidden-import丢
    # 致ModuleNotFound
    "--paths", ROOT,
    "--paths", os.path.join(ROOT, "core"),
    "--paths", os.path.join(ROOT, "core", "infra"),
    "--paths", os.path.join(ROOT, "parsers"),
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
]

for m in ("matplotlib", "numpy", "pandas", "scipy", "PIL", "streamlit", "rich",
          "PyQt5", "PyQt5.sip", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
          "PyQt5.QtNetwork", "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebChannel",
          "PyQt5.QtMultimedia", "PyQt5.QtMultimediaWidgets", "PyQt5.QtPrintSupport"):
    args += ["--exclude-module", m]

# add-data
for rel, dest in [("version_info.json", "."), ("logo.ico", "."),
                  ("logo.png", "."), ("warning_icon.png", "."),
                  ("assets/icons", "assets/icons"),
                  ("assets/images", "assets/images")]:
    src = os.path.join(ROOT, rel)
    if os.path.exists(src):
        args.append("--add-data=%s;%s" % (src, dest))
for extra in ("logo_alt_kaisui.ico", "myqrcode.png", "qunqrcode.png"):
    p = os.path.join(ROOT, extra)
    if os.path.exists(p):
        args.append("--add-data=%s;." % p)

# ---------------------------------------------------------------- 内置 wheel
# 默认不再打进精简包
#
# Inno自己放wheels
# 再内置会重复占体积
# 安装包里就会出现两份
#
# 只有绿色版才用该参数
_wheel_src = None
if not _args.no_wheels:
    for cand in (os.path.join(ROOT, "wheels"),
                 os.path.join(ROOT, "cache", "wheels")):
        if os.path.isdir(cand) and any(
                f.lower().endswith(".whl") for f in os.listdir(cand)):
            _wheel_src = cand
            break

if _wheel_src:
    _n = len([f for f in os.listdir(_wheel_src) if f.lower().endswith(".whl")])
    log("内置离线组件: %s (%d 个 wheel)" % (_wheel_src, _n))
    args.append("--add-data=%s;wheels" % _wheel_src)
else:
    log("未内置 wheel（由安装程序或首次启动负责部署）")

args.append(os.path.join(ROOT, "boot.py"))

log("构建云端精简包（剥离 PyQt5，入口 boot.py）")
log("distpath=%s" % LEAN_DIST)
r = subprocess.run(args, cwd=ROOT)
log("PyInstaller 退出码: %d" % r.returncode)
sys.exit(r.returncode)
