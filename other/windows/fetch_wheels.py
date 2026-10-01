#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 PyQt5 系列 wheel 到本地，供精简包内置（离线可用）。

发布版必须自带这些 wheel：用户不会自己装 Python/PyQt5，也不能假设
他们能联网。构建前跑一次本脚本，把 wheel 存到 wheels/，
build_lean.py 会自动打包进去。

用法：
    python other/windows/fetch_wheels.py                 # 当前解释器对应架构
    python other/windows/fetch_wheels.py --arch win_amd64
    python other/windows/fetch_wheels.py --arch win32
    python other/windows/fetch_wheels.py --all-windows   # 同时准备 32/64 位
    python other/windows/fetch_wheels.py --dir wheels

产物：wheels/*.whl
"""
import argparse
import os
import shutil
import sys
import tempfile
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
sys.path.insert(0, os.path.join(ROOT, "core", "infra"))

import pyqt5_bootstrap as pb  # noqa: E402

# 需内置的包名到前缀
PACKAGES = [
    ("pyqt5", "PyQt5", pb.PYQT5_VER),
    ("pyqt5-qt5", "PyQt5_Qt5", pb.PYQT5_VER),
    ("pyqt5-sip", "PyQt5_sip", None),
    ("pyqtwebengine", "PyQtWebEngine", None),
    ("pyqtwebengine-qt5", "PyQtWebEngine_Qt5", None),
]

# 目标架构wheel标签
ARCH_TAGS = {
    "win_amd64": "win_amd64",
    "win32": "win32",
    "win_arm64": "win_arm64",
}


def log(m):
    print(m, flush=True)


def _pick(entries, prefix, want_ver, arch_tag, py_tag):
    """在候选列表里挑出指定架构 + 指定解释器版本的 wheel。

    entries 里的每一项都应已带解析结果（name/pyver/abi/version/platform）。
    """
    best = None
    best_score = -1
    for e in entries:
        fn = e["filename"]
        low = fn.lower()
        if arch_tag not in low:
            continue
        p = e
        if not p.get("name"):
            try:
                p = pb._split_wheel(fn)
            except Exception:
                continue
        if p["name"].lower() != prefix.lower():
            continue
        # ABI须用于py_tag
        if not pb._compat_ok(p["pyver"], p["abi"], py_tag):
            continue
        score = 0
        if want_ver:
            if p["version"] == want_ver:
                score += 100
            elif p["version"].startswith(want_ver + "."):
                score += 90
        if p["pyver"].lower() == py_tag.lower():
            score += 50
        if p["abi"] == "abi3":
            score += 10
        if p["abi"] == "none":
            score += 5
        try:
            score += sum(int(x) for x in p["version"].split(".")) * 0.01
        except Exception:
            pass
        if score > best_score:
            best_score = score
            best = e
    return best


def fetch_for_arch(arch_tag, outdir, py_tag):
    """抓取某一架构所需的全部 wheel，返回成功数 / 是否全齐。"""
    ok = 0
    total = len(PACKAGES)
    tmp = tempfile.mkdtemp(prefix="fetchwheels_")
    try:
        for pkg_name, prefix, want_ver in PACKAGES:
            dst = None
            last = None
            for mirror in pb.MIRROR_SIMPLE:
                try:
                    entries = pb._load_simple_entries(mirror, pkg_name)
                except Exception as e:
                    last = e
                    continue
                # 不能按本机过滤
                # 只按文件名架构
                # _pick需要pyver
                cand = []
                for e in entries:
                    if arch_tag not in e["filename"].lower():
                        continue
                    try:
                        parsed = pb._split_wheel(e["filename"])
                    except Exception:
                        continue
                    item = dict(parsed)
                    item["filename"] = e["filename"]
                    item["url"] = e["url"]
                    cand.append(item)
                picked = _pick(cand, prefix, want_ver, arch_tag, py_tag)
                if not picked:
                    last = "未找到 %s (%s)" % (prefix, arch_tag)
                    continue
                f = os.path.join(tmp, picked["filename"])
                try:
                    pb._download(picked["url"], f,
                                 "%s-%s" % (prefix, picked["version"]))
                except Exception as e:
                    last = e
                    continue
                if not os.path.isfile(f) or os.path.getsize(f) < 1024:
                    last = "文件异常小"
                    continue
                dst = os.path.join(outdir, picked["filename"])
                shutil.move(f, dst)
                log("   %-22s -> %s" % (prefix, picked["filename"]))
                ok += 1
                break
            if dst is None:
                log("   %-22s !! 获取失败: %s" % (prefix, last))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default=None,
                    help="目标架构标签，如 win_amd64 / win32 / win_arm64")
    ap.add_argument("--all-windows", action="store_true",
                    help="同时准备 win_amd64 与 win32 两套")
    ap.add_argument("--py", default=None,
                    help="目标 CPython 标签，如 cp310（默认当前解释器）")
    ap.add_argument("--dir", default=os.path.join(ROOT, "wheels"),
                    help="输出目录")
    a = ap.parse_args()

    py_tag = a.py or ("cp%d%d" % (sys.version_info.major, sys.version_info.minor))

    if a.all_windows:
        archs = ["win_amd64", "win32"]
    elif a.arch:
        archs = [a.arch]
    else:
        archs = [pb._win_arch_tag()]

    for arch in archs:
        if arch not in ARCH_TAGS:
            log("不支持的架构: %s（支持 %s）" % (arch, ", ".join(ARCH_TAGS)))
            return 2

    outdir = os.path.abspath(a.dir)
    os.makedirs(outdir, exist_ok=True)

    log("目标解释器标签: %s" % py_tag)
    log("输出目录      : %s" % outdir)
    log("")

    failed = False
    for arch in archs:
        log("=== 架构 %s ===" % arch)
        ok, total = fetch_for_arch(arch, outdir, py_tag)
        log("   %d/%d 已就位" % (ok, total))
        if ok < total:
            failed = True
        log("")

    files = sorted(f for f in os.listdir(outdir) if f.lower().endswith(".whl"))
    log("共 %d 个 wheel 位于 %s" % (len(files), outdir))
    if failed:
        log("")
        log("注意：部分 wheel 获取失败（该架构上游可能未发布）。")
        log("      精简包仍会构建，但对应环境需要联网下载。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
