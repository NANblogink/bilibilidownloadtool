import sys
import os
import traceback

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

import _pathsetup  # noqa: F401,E402

import pyqt5_bootstrap  # noqa: E402


def _fatal(msg):
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
    try:
        ok = pyqt5_bootstrap.ensure_pyqt5(log=print, console=True)
    except Exception as e:
        traceback.print_exc()
        _fatal(str(e))
        return 1

    try:
        pyqt5_bootstrap.free_console()
    except Exception:
        pass

    if not ok:
        _fatal("PyQt5 运行环境下载失败或无法导入。")
        return 1

    try:
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
