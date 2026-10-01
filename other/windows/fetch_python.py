#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""下载 embeddable Python 到 runtime/，供引导器内置（完全离线部署）。

用法：
    python other/windows/fetch_python.py                # 当前架构
    python other/windows/fetch_python.py --arch win_amd64
    python other/windows/fetch_python.py --all-windows  # 32 + 64 位

产物：runtime/python-3.10.11-embed-amd64.zip
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))

import python_deploy as pd  # noqa: E402


def _size(u):
    try:
        import urllib.request
        req = urllib.request.Request(u, method="HEAD",
                                     headers={"User-Agent": "fetch/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arch", default=None)
    ap.add_argument("--all-windows", action="store_true")
    ap.add_argument("--dir", default=os.path.join(ROOT, "runtime"))
    a = ap.parse_args()

    archs = ["win_amd64", "win32"] if a.all_windows else \
            [a.arch or pd.target_arch_tag()]
    archs = [x for x in archs if x]

    outdir = os.path.abspath(a.dir)
    os.makedirs(outdir, exist_ok=True)

    print("Python 版本 : %s" % pd.PY_VER)
    print("输出目录    : %s" % outdir)
    print()

    rc = 0
    for arch in archs:
        url = pd._py_url(arch)
        if not url:
            print("不支持架构: %s" % arch)
            rc = 2
            continue
        name = url.rsplit("/", 1)[-1]
        dst = os.path.join(outdir, name)
        if os.path.isfile(dst) and os.path.getsize(dst) > 1024 * 1024:
            print("%-10s 已存在: %s (%.2f MB)"
                  % (arch, name, os.path.getsize(dst) / 1048576.0))
            continue
        sz = _size(url)
        print("%-10s 下载 %s (%.2f MB)..." % (arch, name, sz / 1048576.0))
        try:
            pd._download(url, dst, "Python-%s" % arch, retries=3)
        except Exception as e:
            print("   失败: %s" % e)
            rc = 1
            continue
        if sz and os.path.getsize(dst) < sz:
            print("   不完整: %d/%d" % (os.path.getsize(dst), sz))
            rc = 1
            continue
        print("   完成: %.2f MB" % (os.path.getsize(dst) / 1048576.0))

    files = [f for f in os.listdir(outdir) if f.lower().endswith(".zip")]
    print()
    print("runtime/ 共 %d 个文件" % len(files))
    return rc


if __name__ == "__main__":
    sys.exit(main())
