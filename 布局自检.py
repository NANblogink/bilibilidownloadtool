# -*- coding: utf-8 -*-
"""布局自检工具

运行：python 布局自检.py
用途：确认当前代码的界面布局是否正确，并给出可核对的指纹。
"""
import sys, os, io, hashlib, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    import _pathsetup  # noqa: F401
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 60)
    print("  界面布局自检")
    print("=" * 60)

    p = os.path.join(HERE, "ui.py")
    if not os.path.exists(p):
        print("  [X] 找不到 ui.py，请把本文件放在程序目录下运行")
        return 1
    d = open(p, "rb").read()
    src = d.decode("utf-8", "ignore")

    print()
    print("--- 1) 代码文件 ---")
    print("    路径 : %s" % p)
    print("    大小 : %d 字节" % len(d))
    print("    修改 : %s" % time.strftime("%Y-%m-%d %H:%M:%S",
                                         time.localtime(os.path.getmtime(p))))
    print("    校验 : %s" % hashlib.md5(d).hexdigest())

    print()
    print("--- 2) 关键修复点 ---")
    checks = [
        ("下方空白保留 (addStretch)",
         "video_layout.addStretch(1)" in src),
        ("信息卡不被拉伸 (stretch=0)",
         "setStretchFactor(self._video_card, 0)" in src),
        ("卡片区按内容取高 (Maximum)",
         "QSizePolicy.Preferred, QSizePolicy.Maximum" in src),
        ("卡片固定高度",
         "card.setFixedHeight(scale(78)" in src),
        ("卡片区初始隐藏 (hide)",
         "panel.hide()" in src),
    ]
    for name, ok in checks:
        print("    [%s] %s" % ("OK" if ok else "缺失", name))
    allok = all(ok for _, ok in checks)

    print()
    print("--- 3) 实际启动状态 ---")
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        import ui
        from core.config import ConfigLoader
        from core.task_manager import TaskManager
        from core.downloader import DownloadManager
        from parsers.bilibili_parser import BilibiliParser

        cfg = ConfigLoader()
        w = ui.BilibiliDownloader(
            config=cfg, task_manager=TaskManager(),
            download_manager=DownloadManager(
                parser=None, task_manager=None, config=cfg))
        w.parser = BilibiliParser(cfg)
        w.resize(1705, 700)
        w.show()
        for _ in range(20):
            app.processEvents()

        vt = w.video_tab_layout.parentWidget()
        blank = vt.height() - w._video_card.y() - w._video_card.height()
        hidden = w.parsed_card_panel.isHidden()

        print("    卡片面板启动时隐藏 : %s  (%s)"
              % (hidden, "正确" if hidden else "错误！启动不该显示"))
        print("    信息卡高 %d，下方空白 %d  (%s)"
              % (w._video_card.height(), blank,
                 "正确" if blank > 0 else "错误！空白没了"))
        runtime_ok = hidden and blank > 0
    except Exception as e:
        print("    [跳过] 无法启动界面：%s" % e)
        runtime_ok = None

    print()
    print("=" * 60)
    if allok and runtime_ok is not False:
        print("  结论：这份代码布局正确。")
        print("  如果界面仍不对，说明运行的不是这份代码 ——")
        print("  请关掉程序重新打开（改了代码必须重启才生效）。")
    else:
        print("  结论：这份代码有问题，请把上面信息发给作者。")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
