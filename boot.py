"""
精简版（剥离 PyQt5）的引导启动器。

PyInstaller 打包时主程序目录里不包含 PyQt5，本引导器负责：
  1. 检查 / 下载 / 解压 PyQt5 运行环境（复用 pyqt5_bootstrap）
  2. 注入 sys.path 后，以 __main__ 的方式运行 main.py 的原入口逻辑

注意：本文件顶层严禁 import PyQt5 / main / ui 等业务模块，
否则 PyInstaller 会把它们连带收集进精简包，失去剥离意义。
"""
import sys
import os
import traceback

# 确保能 import 到同一目录下的 pyqt5_bootstrap（源码/打包均可用）
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

# 注入 core/ 等子目录，使 pyqt5_bootstrap 等模块可被导入
import _pathsetup  # noqa: F401,E402  导入即完成路径注入

import pyqt5_bootstrap  # noqa: E402


def _fatal(msg):
    """下载失败时的兜底提示（无 PyQt5 时用原生 MessageBoxW 显示）。"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            ("无法获取 PyQt5 运行环境。\n\n%s\n\n"
             "请检查网络后重试，或改用完整安装版。") % msg,
            "B站视频下载工具", 0x10)
    except Exception:
        pass
    try:
        print(msg)
    except Exception:
        pass
    os._exit(1)


def main():
    # 1. 保证 PyQt5 就位（首次启动会弹控制台显示下载进度）
    try:
        ok = pyqt5_bootstrap.ensure_pyqt5(log=print, console=True)
    except Exception as e:
        traceback.print_exc()
        _fatal(str(e))
        return 1

    # 下载完成后释放控制台，避免主窗口旁残留黑窗
    try:
        pyqt5_bootstrap.free_console()
    except Exception:
        pass

    if not ok:
        _fatal("PyQt5 运行环境下载失败或无法导入。")
        return 1

    # 2. 以 __main__ 名运行 main.py（触发其 if __name__ == "__main__" 原入口逻辑）
    try:
        # runpy 会用新模块对象并设置 __name__ = "__main__"，无需改动 main.py
        import runpy
        runpy.run_module("main", run_name="__main__")
    except SystemExit:
        raise
    except BaseException as e:
        traceback.print_exc()
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                ("程序启动失败：%s" % e),
                "B站视频下载工具",
                0x10)
        except Exception:
            pass
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())