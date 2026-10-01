#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成并构建「图形化 Windows 安装程序」。

特点：
  * 图形安装向导（欢迎 -> 目录 -> 选项 -> 安装进度 -> 完成）
  * 安装过程中图形化显示 Python 运行时部署进度
  * 可内置 Python 运行时包与 PyQt5 wheel，实现**完全离线安装**
  * 直接使用 Windows 原生安装体验（控制面板卸载项、开始菜单、桌面快捷方式）

用法：
    python other/windows/build_setup.py                     # 在线安装器
    python other/windows/build_setup.py --embed-wheels      # 内置 PyQt5（离线装 PyQt5）
    python other/windows/build_setup.py --embed-all         # 内置 Python + PyQt5（完全离线）

产物：output/<版本>_installer_gui.exe
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
    raise RuntimeError("未找到项目根目录")


ROOT = _find_root(__file__)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))

from app_config import APP_NAME_EN, VERSION_NUM  # noqa: E402

OUTPUT = os.path.join(ROOT, "output")
WORK = os.path.join(ROOT, "build", "_setup")
SPEC = os.path.join(ROOT, "build", "_setup_%s.spec" % VERSION_NUM)


def log(m):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), m), flush=True)


def _find_python_zip():
    for d in (os.path.join(ROOT, "runtime"), ROOT):
        try:
            for f in sorted(os.listdir(d)):
                low = f.lower()
                if low.startswith("python-") and low.endswith(".zip"):
                    return os.path.join(d, f)
        except Exception:
            continue
    return None


def _find_wheels_dir():
    for cand in (os.path.join(ROOT, "wheels"),
                 os.path.join(ROOT, "cache", "wheels")):
        if os.path.isdir(cand) and any(
                f.lower().endswith(".whl") for f in os.listdir(cand)):
            return cand
    return None


def render_spec(embed_python, embed_wheels):
    """生成安装器 spec。"""
    py = os.path.join(ROOT, "build", "installer.py")
    paths = [
        ROOT,
        os.path.join(ROOT, "core"),
        os.path.join(ROOT, "core", "infra"),
        os.path.join(ROOT, "parsers"),
        os.path.join(ROOT, "build"),
    ]
    datas = []
    if embed_wheels:
        wd = _find_wheels_dir()
        if wd:
            datas.append("('%s', 'wheels')" % wd.replace("\\", "\\\\"))
    if embed_python:
        pz = _find_python_zip()
        if pz:
            datas.append("('%s', '.')" % pz.replace("\\", "\\\\"))

    datas.append("('%s', '.')" % os.path.join(ROOT, "version_info.json")
                 .replace("\\", "\\\\"))
    datas.append("('%s', '.')" % os.path.join(ROOT, "logo.ico")
                 .replace("\\", "\\\\"))

    hidden = [
        "PyQt5.sip", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets",
        "tool_manager", "platform_utils", "pyqt5_bootstrap",
        "python_deploy", "app_config",
    ]

    name = "%s_installer_gui" % VERSION_NUM
    spec = """# -*- mode: python ; coding: utf-8 -*-
# 由 other/windows/build_setup.py 自动生成，请勿手工编辑。

a = Analysis(
    [r'%(py)s'],
    pathex=%(paths)s,
    binaries=[],
    datas=[%(datas)s],
    hiddenimports=%(hidden)s,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'streamlit'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='%(name)s',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=r'%(ver)s',
    icon=[r'%(icon)s'],
)
""" % {
        "py": py,
        "paths": repr(paths),
        "datas": ", ".join(datas),
        "hidden": repr(hidden),
        "name": name,
        "ver": os.path.join(ROOT, "version_info.win"),
        "icon": os.path.join(ROOT, "logo.ico"),
    }
    return spec, name


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--embed-wheels", action="store_true",
                    help="内置 PyQt5 wheel（离线安装界面组件）")
    ap.add_argument("--embed-python", action="store_true",
                    help="内置 Python 运行时包（完全离线）")
    ap.add_argument("--embed-all", action="store_true",
                    help="等同于 --embed-wheels --embed-python")
    a = ap.parse_args()

    ew = a.embed_wheels or a.embed_all
    ep = a.embed_python or a.embed_all

    os.makedirs(OUTPUT, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)

    if ew and not _find_wheels_dir():
        log("警告：未找到 wheels/，请先运行 fetch_wheels.py")
        ew = False
    if ep and not _find_python_zip():
        log("警告：未找到 python-*-embed-*.zip，请先运行 fetch_python.py")
        ep = False

    spec_text, name = render_spec(ep, ew)
    with open(SPEC, "w", encoding="utf-8") as f:
        f.write(spec_text)

    log("生成 spec: %s" % os.path.basename(SPEC))
    log("内置 wheel : %s" % ("是" if ew else "否"))
    log("内置 Python: %s" % ("是" if ep else "否"))

    # 注意：从 spec 构建时不能再传 --noupx 等 makespec 选项，
    # 它们已经在 spec 里表达（见 render_spec 的 EXE(...)）
    args = [sys.executable, "-m", "PyInstaller", SPEC,
            "--noconfirm", "--clean",
            "--distpath", OUTPUT,
            "--workpath", WORK]
    r = subprocess.run(args, cwd=ROOT)

    try:
        os.remove(SPEC)
    except Exception:
        pass

    if r.returncode == 0:
        exe = os.path.join(OUTPUT, name + ".exe")
        if os.path.isfile(exe):
            log("产物: %s (%.1f MB)" % (exe, os.path.getsize(exe) / 1048576.0))
    else:
        log("构建失败，退出码 %d" % r.returncode)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
