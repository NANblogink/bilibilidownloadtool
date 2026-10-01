# -*- coding: utf-8 -*-
"""极简引导器入口。

流程：
  1. 检查/部署 Python 运行时（首次运行自动下载，约 8 MB）
  2. 检查/安装 PyQt5（优先本地内置 wheel，可离线）
  3. 用部署好的 pythonw.exe 启动主程序

这个脚本本身由 PyInstaller 打成很小的 exe（约 5~10 MB），
**不包含** Python 运行时和 PyQt5，也不要求用户安装任何东西。
"""
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(
    sys.executable if getattr(sys, "frozen", False) else __file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# 允许在源码方式下直接运行
for _p in (os.path.join(_HERE, "core"), _HERE):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

import python_deploy as pd  # noqa: E402

APP_ENTRY = "main"          # 主程序模块名


# ---------------------------------------------------------------- 界面反馈

class _Progress(object):
    """轻量进度窗口：无 PyQt 时用 Tk（标准库），保证首次运行有反馈。"""

    def __init__(self):
        self.root = None
        self.label = None
        try:
            import tkinter as tk
            self.root = tk.Tk()
            self.root.title("B站视频下载工具 - 首次运行准备")
            self.root.geometry("460x150")
            self.root.resizable(False, False)
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass
            tk.Label(self.root, text="正在准备运行环境",
                     font=("Microsoft YaHei", 12, "bold")).pack(pady=(18, 6))
            self.label = tk.Label(self.root, text="初始化...",
                                  font=("Microsoft YaHei", 9),
                                  wraplength=420, justify="left")
            self.label.pack(pady=4)
            self.detail = tk.Label(self.root, text="",
                                   font=("Microsoft YaHei", 8), fg="#666",
                                   wraplength=420, justify="left")
            self.detail.pack(pady=2)
            self.root.update()
        except Exception:
            self.root = None

    def log(self, msg):
        try:
            msg = str(msg)
        except Exception:
            msg = "?"
        print(msg, flush=True)
        if self.label is not None:
            try:
                low = msg.lower()
                if any(k in msg for k in ("下载", "解压", "安装", "部署")):
                    self.label.config(text=msg.strip()[:90])
                else:
                    self.detail.config(text=msg.strip()[:90])
                self.root.update()
            except Exception:
                pass

    def close(self):
        if self.root is not None:
            try:
                self.root.destroy()
            except Exception:
                pass
            self.root = None


def _fatal(msg):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "运行环境准备失败。\n\n%s\n\n"
            "请确认网络连接后重试；\n"
            "若处于内网/离线环境，请把 wheels 目录放在程序目录下再试。"
            % msg,
            "B站视频下载工具", 0x10)
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        pass


# ---------------------------------------------------------------- 主流程

def _find_local_python_zip():
    """查找随包内置的 Python 运行时压缩包（完全离线时用）。"""
    cands = []
    for root in (_HERE, os.path.dirname(_HERE)):
        for sub in ("", "runtime", "python"):
            d = os.path.join(root, sub) if sub else root
            try:
                for f in os.listdir(d):
                    if f.lower().startswith("python-") and f.lower().endswith(".zip"):
                        cands.append(os.path.join(d, f))
            except Exception:
                continue
    return cands[0] if cands else None


def _find_local_wheel_dir():
    for d in pd.local_wheel_dirs():
        try:
            if any(f.lower().endswith(".whl") for f in os.listdir(d)):
                return d
        except Exception:
            continue
    return None


def main():
    ui = _Progress()
    try:
        pd.set_logger(ui.log)
        ui.log("检查运行环境...")

        root = pd.deploy_root()
        local_py = _find_local_python_zip()
        local_wh = _find_local_wheel_dir()
        if local_py:
            ui.log("发现内置 Python 包: %s" % os.path.basename(local_py))
        if local_wh:
            ui.log("发现内置组件目录: %s" % local_wh)

        ok = pd.ensure_environment(root, local_py_zip=local_py,
                                   local_wheel_dir=local_wh)
        if not ok:
            ui.close()
            _fatal("无法准备 Python 运行时或界面组件。")
            return 1

        ui.log("启动主程序...")
        exe = pd.python_exe(root, windowed=True)
        if not os.path.isfile(exe):
            exe = pd.python_exe(root, windowed=False)
        if not os.path.isfile(exe):
            ui.close()
            _fatal("找不到已部署的 Python 解释器。")
            return 1

        ui.close()
        return _launch(exe, root)
    except Exception:
        ui.close()
        tb = traceback.format_exc()
        try:
            print(tb, flush=True)
        except Exception:
            pass
        _fatal(tb.strip().splitlines()[-1] if tb else "未知错误")
        return 1


def _launch(exe, root):
    """用部署好的解释器启动主程序。

    重要：embeddable Python 存在 `._pth` 文件时进入 isolated 模式，
    **完全忽略 PYTHONPATH**（实测验证）。因此不能用环境变量传路径，
    必须：
      1. 把程序目录写进 `._pth`，或
      2. 在 -c 代码里显式 sys.path.insert
    这里两者都做，确保任何布局下都能找到主程序。
    """
    import subprocess
    app_dir = _HERE

    # 把程序目录登记到部署运行时的 ._pth，使其长期可见
    _register_app_path(root, app_dir)

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    # 兜底：即便 ._pth 未生效，下面的 -c 代码也会显式插入
    env["PYTHONPATH"] = os.pathsep.join(
        [app_dir, os.path.join(app_dir, "core")] +
        ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))

    bootstrap = (
        "import sys,os,runpy;"
        "app=r'%s';"
        "[sys.path.insert(0,p) for p in (app, os.path.join(app,'core')) "
        " if os.path.isdir(p) and p not in sys.path];"
        "sys.argv[0]='main';"
        "runpy.run_module('%s',run_name='__main__')"
    ) % (app_dir, APP_ENTRY)

    CREATE_NO_WINDOW = 0x08000000
    cmd = [exe, "-c", bootstrap]
    try:
        subprocess.Popen(cmd, cwd=app_dir, env=env,
                         creationflags=CREATE_NO_WINDOW)
        return 0
    except Exception:
        pass
    try:
        subprocess.Popen(cmd, cwd=app_dir, env=env)
        return 0
    except Exception as e:
        _fatal("启动主程序失败：%s" % e)
        return 1


def _register_app_path(root, app_dir):
    """把程序目录及其 core/ 写入部署运行时的 ._pth（幂等）。"""
    try:
        pydir = pd.python_dir(root)
        cands = [f for f in os.listdir(pydir) if f.endswith("._pth")]
    except Exception:
        return
    for fn in cands:
        p = os.path.join(pydir, fn)
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        changed = False
        for d in (app_dir, os.path.join(app_dir, "core")):
            if not os.path.isdir(d):
                continue
            if d not in lines:
                lines.append(d)
                changed = True
        if changed:
            try:
                with open(p, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
