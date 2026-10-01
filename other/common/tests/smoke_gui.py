"""GUI 冒烟测试（跨平台）。

在无显示器环境下（offscreen）真实构建主窗口、跑一小段事件循环再关闭，
用于确认跨平台改动没有破坏界面层。

用法：
    python other/common/tests/smoke_gui.py

成功时最后一行输出 GUI_SMOKE_RC=0。
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import install_paths  # noqa: E402

PROJECT_ROOT = install_paths()

#import QApp前
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from PyQt5.QtWidgets import QApplication  # noqa: E402
from PyQt5.QtCore import QTimer  # noqa: E402

app = QApplication(sys.argv)

try:
    from config import ConfigLoader
    from task_manager import TaskManager
    from downloader import DownloadManager
    from bilibili_parser import BilibiliParser
    import ui

    config = ConfigLoader()
    tm = TaskManager()
    parser = BilibiliParser(config=config)
    dm = DownloadManager(parser=parser)

    print("MAIN WINDOW CONSTRUCTING...")
    win = ui.BilibiliDownloader(config=config, task_manager=tm,
                                download_manager=dm)
    print("MAIN WINDOW CONSTRUCTED OK")
    win.show()

    ticks = {"n": 0}

    def _tick():
        ticks["n"] += 1
        if ticks["n"] % 3 == 0:
            print("event loop tick", ticks["n"])

    t = QTimer()
    t.timeout.connect(_tick)
    t.start(200)
    QTimer.singleShot(1500, app.quit)

    app.exec_()
    print("EVENT LOOP RAN OK ticks=", ticks["n"])
    win.close()
    print("WINDOW CLOSED OK")
    print("GUI_SMOKE_RC=0")
except Exception:
    traceback.print_exc()
    print("GUI_SMOKE_RC=1")
    sys.exit(1)
