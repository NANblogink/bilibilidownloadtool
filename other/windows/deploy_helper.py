#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安装期部署工具（由 Inno Setup 调用，无控制台、无 Python 依赖）。

职责：把 Python 运行时 + PyQt5 部署到目标目录。
被打包成单文件 deploy_helper.exe，因此目标机器无需 Python。

用法（由安装程序调用）：
    deploy_helper.exe --target "<安装目录>\runtime" \
                      [--wheels "<wheels目录>"] \
                      [--python-zip "<python-embed.zip>"] \
                      [--progress-file "<文件>"]

进度写入 --progress-file（每行一个百分比），安装程序可据此显示进度。
"""
import argparse
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
for _p in (_HERE, os.path.join(_HERE, "core")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import python_deploy as pd  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--wheels", default=None)
    ap.add_argument("--python-zip", default=None)
    ap.add_argument("--progress-file", default=None)
    ap.add_argument("--log-file", default=None)
    a = ap.parse_args()

    logf = None
    if a.log_file:
        try:
            logf = open(a.log_file, "a", encoding="utf-8")
        except Exception:
            logf = None

    def emit(msg):
        line = str(msg)
        try:
            print(line, flush=True)
        except Exception:
            pass
        if logf:
            try:
                logf.write(line + "\n")
                logf.flush()
            except Exception:
                pass

    def report(pct):
        if not a.progress_file:
            return
        try:
            with open(a.progress_file, "w", encoding="utf-8") as f:
                f.write(str(int(pct)))
        except Exception:
            pass

    pd.set_logger(emit)
    report(0)

    try:
        target = os.path.abspath(a.target)

        # 定位内置资源
        local_py = a.python_zip if (a.python_zip and os.path.isfile(a.python_zip)) else None
        if not local_py:
            for d in (_HERE, os.path.dirname(_HERE), os.getcwd()):
                try:
                    for f in sorted(os.listdir(d)):
                        low = f.lower()
                        if low.startswith("python-") and low.endswith(".zip"):
                            local_py = os.path.join(d, f)
                            break
                except Exception:
                    continue
                if local_py:
                    break

        local_wh = a.wheels if (a.wheels and os.path.isdir(a.wheels)) else None
        if not local_wh:
            for d in (_HERE, os.path.dirname(_HERE), os.getcwd()):
                for sub in ("wheels",):
                    cand = os.path.join(d, sub)
                    try:
                        if os.path.isdir(cand) and any(
                                x.lower().endswith(".whl")
                                for x in os.listdir(cand)):
                            local_wh = cand
                            break
                    except Exception:
                        continue
                if local_wh:
                    break

        if local_py:
            emit("使用内置 Python 运行时包（无需联网）")
        if local_wh:
            emit("使用内置界面组件（离线安装）")

        emit("[1/2] 部署 Python 运行时")
        report(10)
        if not pd.python_ready(target):
            ok = pd.deploy_python(target, local_zip=local_py)
            if not ok:
                emit("Python 运行时部署失败")
                report(100)
                return 2
        else:
            emit("Python 运行时已就位")
        report(55)

        emit("[2/2] 安装界面组件 (PyQt5)")
        if not pd.site_packages_ready(target):
            ok = pd.install_site_packages(target, local_dir=local_wh)
            if not ok:
                emit("PyQt5 安装失败")
                report(100)
                return 3
        else:
            emit("界面组件已就位")
        report(100)

        emit("运行环境准备完成")
        return 0
    except Exception:
        emit("部署出错:\n" + traceback.format_exc())
        report(100)
        return 1
    finally:
        if logf:
            try:
                logf.close()
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
