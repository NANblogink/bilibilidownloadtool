import sys
import os

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _pathsetup  # noqa: F401


def _is_msix_environment():
    try:
        exe_path = os.path.abspath(sys.executable).lower().replace('/', '\\')
        return 'windowsapps' in exe_path
    except Exception:
        return False


_STARTUP_STATE = {'window_visible': False, 'fatal_dialog': False, 'constructing': False}


def _fatal_error_dialog(title, message):
    try:
        from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
                                     QLabel, QPushButton, QFrame)
        from PyQt5.QtCore import Qt
        from PyQt5 import QtCore
    except Exception:
        return False  #无PyQt

    app = QApplication.instance()
    if app is None:
        try:
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
            QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
        except Exception:
            pass
        app = QApplication([])

    def _copy_logs():
        try:
            from ui import copy_logs_for_support
            return copy_logs_for_support()
        except Exception:
            return False

    def _join_group():
        try:
            import webbrowser as _wb
            _wb.open("https://qm.qq.com/q/FuEDO9DXmG")
            return True
        except Exception:
            return False

    top = None
    from PyQt5.QtWidgets import QApplication as _QA
    _inst = _QA.instance()
    if _inst is not None and getattr(_inst, 'topLevelWidgets', None):
        try:
            wins = _inst.topLevelWidgets()
            for w in wins:
                if w.isVisible() and w.window():
                    top = w.window()
                    break
        except Exception:
            top = None

    dlg = QDialog(top)
    dlg.setWindowTitle(title)
    dlg.setWindowFlags(Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
    dlg.resize(560, 380)
    dlg.setMinimumSize(440, 300)
    if top is None:
        dlg.setAttribute(Qt.WA_DeleteOnClose, False)

    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 18)
    layout.setSpacing(12)

    heading = QLabel(title)
    heading.setStyleSheet("font-size: 16px; font-weight: 700; color: #d4380d;")
    layout.addWidget(heading)

    body = QLabel(str(message)[:1800])
    body.setWordWrap(True)
    body.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    body.setTextInteractionFlags(Qt.TextSelectableByMouse)
    body.setStyleSheet("font-size: 13px; color: #333333;")
    layout.addWidget(body, 1)

    support_info = QLabel(
        "遇到这个错误，请把日志和报错信息复制后发给作者，方便我尽快修复：\n"
        "QQ：2273962061 / 3241417097\n"
        "用户交流QQ群：714822491")
    support_info.setWordWrap(True)
    support_info.setStyleSheet("font-size: 12px; color: #595959;")
    layout.addWidget(support_info)

    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    line.setStyleSheet("color: #e8e8e8;")
    layout.addWidget(line)

    btn_row = QHBoxLayout()
    btn_row.setSpacing(10)
    copy_btn = QPushButton("一键复制日志")
    copy_btn.setStyleSheet(
        "QPushButton { background-color: #fafafa; color: #374151; border: 1px solid #d9d9d9; "
        "border-radius: 4px; padding: 8px 16px; font-size: 13px; }"
        "QPushButton:hover { background-color: #f0f0f0; }")
    def _on_copy():
        _copy_logs()
        try:
            from ui import windows_notify
            windows_notify("日志已复制", "日志已复制到剪贴板，可直接粘贴发送给作者")
        except Exception:
            pass
    copy_btn.clicked.connect(_on_copy)
    btn_row.addWidget(copy_btn)

    join_btn = QPushButton("加入交流群获取支持")
    join_btn.setStyleSheet(
        "QPushButton { background-color: #00a1d6; color: white; border: none; "
        "border-radius: 4px; padding: 8px 16px; font-size: 13px; font-weight: 600; }"
        "QPushButton:hover { background-color: #0091c2; }")
    def _on_join():
        _join_group()
    join_btn.clicked.connect(_on_join)
    btn_row.addWidget(join_btn)

    exit_btn = QPushButton("退出")
    exit_btn.setStyleSheet(
        "QPushButton { background-color: #f5f5f5; color: #333333; border: 1px solid #d9d9d9; "
        "border-radius: 4px; padding: 8px 20px; font-size: 13px; }"
        "QPushButton:hover { background-color: #ebebeb; }")
    exit_btn.clicked.connect(dlg.reject)
    btn_row.addWidget(exit_btn)

    btn_row.addStretch(1)
    layout.addLayout(btn_row)

    dlg.exec_()
    return True


def _fatal_error_exit(title, message):
    _STARTUP_STATE['fatal_dialog'] = True
    try:
        import traceback as _tb
        _log_path = os.path.join(os.path.expanduser('~'), 'bilidown_startup_error.log')
        with open(_log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {title} =====\n{message}\n")
    except Exception:
        pass
    if sys.platform == 'win32':
        _on_main_thread = True
        try:
            import threading as _th
            _on_main_thread = _th.get_ident() == _th.main_thread().ident
        except Exception:
            pass
        try:
            if _on_main_thread and _fatal_error_dialog(title, message):
                pass
            else:
                # 非主线程创建 QDialog 不可靠，改用系统原生弹框
                import ctypes
                ctypes.windll.user32.MessageBoxW(None, str(message)[:1800], title, 0x10)
        except Exception:
            pass
    os._exit(1)

for _k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy'):
    os.environ.pop(_k, None)
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*sipPyTypeDict.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*sipPyName.*")
import requests
requests.Session.trust_env = False
import time
import json
import traceback
import logging
from platform_utils import IS_MACOS, IS_WINDOWS, platform_font

if sys.platform == 'win32' and getattr(sys, 'frozen', False):
    try:
        import ctypes
        ctypes.windll.kernel32.GetConsoleWindow.restype = ctypes.c_void_p
        ctypes.windll.user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        ctypes.windll.user32.ShowWindow.restype = ctypes.c_bool
        _console_hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if _console_hwnd:
            ctypes.windll.user32.ShowWindow(_console_hwnd, 0)
    except Exception:
        pass

if IS_WINDOWS:
    try:
        _internal_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
        _qt_bin_dir = os.path.join(_internal_dir, 'PyQt5', 'Qt5', 'bin')
        _qt_resources_dir = os.path.join(_internal_dir, 'PyQt5', 'Qt5', 'resources')
        _qt_plugins_dir = os.path.join(_internal_dir, 'PyQt5', 'Qt5', 'plugins')

        # 设Qt插件路径防报错
        _platforms_dir = os.path.join(_qt_plugins_dir, 'platforms')
        if os.path.isdir(_platforms_dir):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = _platforms_dir
        elif getattr(sys, 'frozen', False):
            for _search in [
                os.path.join(_internal_dir, 'PyQt5', 'Qt', 'plugins', 'platforms'),
                os.path.join(_internal_dir, 'platforms'),
                os.path.join(os.path.dirname(sys.executable), 'platforms'),
            ]:
                if os.path.isdir(_search):
                    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = _search
                    break

        _webengine_process = os.path.join(_qt_bin_dir, 'QtWebEngineProcess.exe')
        if os.path.exists(_webengine_process):
            os.environ['QTWEBENGINEPROCESS_PATH'] = _webengine_process

        if os.path.isdir(_qt_resources_dir):
            os.environ['QTWEBENGINE_RESOURCES_PATH'] = _qt_resources_dir

        if os.path.isdir(_qt_bin_dir):
            if not _is_msix_environment():
                os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--single-process --no-sandbox --disable-gpu'
            else:
                os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--no-sandbox --disable-gpu'

        if _is_msix_environment():
            os.environ['QT_OPENGL'] = 'software'
            os.environ['QT_QUICK_BACKEND'] = 'software'
    except Exception:
        pass

from logger_config import logger


class _HangRecovered(Exception):
    pass


def qt_message_handler(msg_type, msg_log_context, msg_string):
    pass

from PyQt5.QtCore import qInstallMessageHandler
qInstallMessageHandler(qt_message_handler)

from PyQt5.QtWidgets import QApplication, QSplashScreen, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer
from ui import BilibiliDownloader, run_on_main_thread
from bilibili_parser import BilibiliParser
from downloader import DownloadManager
from config import ConfigLoader, default_run_as_admin
from icon_manager import get_effective_icon_path
from task_manager import TaskManager
from utils import get_unique_filename
from env_checker import check_environment

class SafeQApplication(QApplication):
    def notify(self, receiver, event):
        try:
            return super().notify(receiver, event)
        except TypeError as e:
            if 'sipBadCatcherResult' in str(e):
                try:
                    receiver_name = ''
                    event_type = ''
                    if receiver:
                        try:
                            receiver_name = receiver.metaObject().className()
                        except Exception:
                            receiver_name = str(type(receiver))
                    if event:
                        try:
                            event_type = str(event.type())
                        except Exception:
                            event_type = str(type(event))
                    print(f"[SafeQApplication] sipBadCatcherResult 抑制: receiver={receiver_name}, event={event_type}")
                except Exception:
                    pass
                return True
            try:
                logger.debug("SafeQApplication 未处理TypeError: %s", str(e))
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                logger.error("SafeQApplication 异常: %s", str(e))
            except Exception:
                pass
            try:
                import sys as _sys
                _hook = getattr(_sys, 'excepthook', None)
                if _hook is not None and _hook is not _sys.__excepthook__:
                    _hook(type(e), e, e.__traceback__)
            except Exception:
                pass
            return True

def _global_exception_hook(exc_type, exc_value, exc_tb):
    try:
        logger.error("全局未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
        traceback.print_exception(exc_type, exc_value, exc_tb)
    except Exception:
        pass

sys.excepthook = _global_exception_hook

from app_config import load_version_info

version_info = load_version_info()

def _get_platform_font():
    font_family, font_size = platform_font()
    return QFont(font_family, font_size)

class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        from ui import scale
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setFixedSize(scale(600), scale(400))
        self.setStyleSheet("background-color: #1890ff;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(scale(20))
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignCenter)
        content_layout.setSpacing(scale(20))
        title_label = QLabel(f"B站解析工具{version_info['version']}")
        title_label.setStyleSheet(f"font-size: {scale(36)}px; font-weight: bold; color: white;")
        title_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title_label)
        author_label = QLabel("作者：寒烟似雪")
        author_label.setStyleSheet(f"font-size: {scale(18)}px; color: white;")
        author_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(author_label)
        qq_label = QLabel("QQ：2273962061")
        qq_label.setStyleSheet(f"font-size: {scale(16)}px; color: white;")
        qq_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(qq_label)
        self.loading_label = QLabel("加载中...")
        self.loading_label.setStyleSheet(f"font-size: {scale(14)}px; color: white;")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFixedHeight(scale(20))
        content_layout.addWidget(self.loading_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(scale(400))
        self.progress_bar.setFixedHeight(scale(12))
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet(f"QProgressBar {{ border-radius: {scale(6)}px; background-color: rgba(255, 255, 255, 0.2); color: #1890ff; font-size: {scale(10)}px; }} QProgressBar::chunk {{ border-radius: {scale(6)}px; background-color: white; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffffff, stop:1 #e0e0e0); }}")
        content_layout.addWidget(self.progress_bar, 0, Qt.AlignCenter)
        main_layout.addWidget(content_widget, stretch=1)
        copyright_label = QLabel("© 2026 寒烟似雪. All rights reserved.")
        copyright_label.setStyleSheet(f"font-size: {scale(12)}px; color: rgba(255, 255, 255, 0.8);")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setFixedHeight(scale(30))
        main_layout.addWidget(copyright_label)
        self.center()
    def center(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.geometry()
        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2
        self.move(x, y)
    def update_progress(self, value, text="加载中..."):
        if value % 5 == 0 or value == 100:
            self.progress_bar.setValue(value)
            self.progress_bar.setFormat(f"{text} ({value}%)")
            self.loading_label.hide()
    def close_with_animation(self):
        from PyQt5.QtCore import QTimer
        opacity = 1.0
        def fade_out():
            nonlocal opacity
            opacity -= 0.1
            if opacity >= 0:
                try:
                    self.setWindowOpacity(opacity)
                    QTimer.singleShot(30, fade_out)
                except RuntimeError:
                    pass
            else:
                try:
                    self.hide()
                except RuntimeError:
                    pass
        fade_out()

if __name__ == "__main__":
    if sys.platform == 'win32' and not _is_msix_environment():
        try:
            import ctypes
            _already_elevated = (
                ('--elevated' in sys.argv)
                or (os.environ.get('BILIDOWN_ELEVATING') == '1')
            )
            if '--elevated' in sys.argv:
                sys.argv = [a for a in sys.argv if a != '--elevated']
            os.environ.pop('BILIDOWN_ELEVATING', None)
            _want_admin = True
            try:
                _setting = ConfigLoader().get_app_setting("run_as_admin", None)
                if _setting is None:
                    _want_admin = default_run_as_admin()
                else:
                    _want_admin = bool(_setting)
            except Exception:
                _want_admin = True
            if not _already_elevated and _want_admin and not ctypes.windll.shell32.IsUserAnAdmin():
                if getattr(sys, 'frozen', False):
                    _base_params = list(sys.argv[1:])
                    _base_params.append('--elevated')
                    params = " ".join(f'"{a}"' for a in _base_params)
                else:
                    script_path = os.path.abspath(__file__)
                    _extra = " ".join(f'"{a}"' for a in sys.argv[1:])
                    params = f'-u "{script_path}" --elevated'
                    if _extra:
                        params += " " + _extra
                ctypes.windll.shell32.ShellExecuteW.restype = ctypes.c_void_p
                os.environ['BILIDOWN_ELEVATING'] = '1'
                result = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, params, None, 1
                )
                if result and int(result) > 32:
                    sys.exit(0)
                os.environ.pop('BILIDOWN_ELEVATING', None)
        except Exception:
            pass

    # 单实例锁防多开
    _INSTANCE_MUTEX = None
    if sys.platform == 'win32':
        try:
            import ctypes
            from ctypes import wintypes

            def _find_windows_by_title_prefixes(prefixes):
                """按标题前缀查找可见窗口，返回hwnd或None"""
                hwnd_found = [None]
                try:
                    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

                    def _find_cb(hwnd, lparam):
                        if not ctypes.windll.user32.IsWindowVisible(hwnd):
                            return True
                        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                        if length <= 0:
                            return True
                        buf = ctypes.create_unicode_buffer(length + 1)
                        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                        for _p in prefixes:
                            if buf.value.startswith(_p):
                                hwnd_found[0] = hwnd
                                return False
                        return True

                    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_find_cb), 0)
                except Exception:
                    pass
                return hwnd_found[0]

            def _is_dialog_window(hwnd):
                try:
                    _buf = ctypes.create_unicode_buffer(256)
                    ctypes.windll.user32.GetClassNameW(hwnd, _buf, 256)
                    return _buf.value == "#32770"
                except Exception:
                    return False

            def _enum_instance_pids():
                """枚举与本进程同名的其他实例PID"""
                pids = []
                if not getattr(sys, 'frozen', False):
                    return pids
                try:
                    class PROCESSENTRY32W(ctypes.Structure):
                        _fields_ = [
                            ('dwSize', wintypes.DWORD),
                            ('cntUsage', wintypes.DWORD),
                            ('th32ProcessID', wintypes.DWORD),
                            ('th32DefaultHeapID', ctypes.POINTER(wintypes.ULONG)),
                            ('th32ModuleID', wintypes.DWORD),
                            ('cntThreads', wintypes.DWORD),
                            ('th32ParentProcessID', wintypes.DWORD),
                            ('pcPriClassBase', wintypes.LONG),
                            ('dwFlags', wintypes.DWORD),
                            ('szExeFile', wintypes.WCHAR * 260),
                        ]
                    exe_name = os.path.basename(sys.executable).lower()
                    kernel32 = ctypes.windll.kernel32
                    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
                    if snap and snap != ctypes.c_void_p(-1).value and snap != -1:
                        entry = PROCESSENTRY32W()
                        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                        ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
                        while ok:
                            try:
                                if (entry.szExeFile or '').lower() == exe_name and entry.th32ProcessID != os.getpid():
                                    pids.append(entry.th32ProcessID)
                            except Exception:
                                pass
                            ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
                        kernel32.CloseHandle(snap)
                except Exception:
                    pass
                return pids

            def _find_window_of_instance_pids(pids):
                if not pids:
                    return None, None
                pid_set = set(pids)
                titled = [None]
                visible = [None]
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

                def _cb(hwnd, lparam):
                    try:
                        pid = wintypes.DWORD(0)
                        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        if pid.value not in pid_set:
                            return True
                        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                        title = ''
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value
                        is_visible = bool(ctypes.windll.user32.IsWindowVisible(hwnd))
                        for _p in ("B站视频解析工具", "B站视频下载工具", "BilibiliDownloader"):
                            if title.startswith(_p):
                                titled[0] = hwnd
                                return False
                        if is_visible and visible[0] is None and not _is_dialog_window(hwnd):
                            visible[0] = hwnd
                    except Exception:
                        pass
                    return True

                try:
                    ctypes.windll.user32.EnumWindows(WNDENUMPROC(_cb), 0)
                except Exception:
                    pass
                if titled[0]:
                    return titled[0], 'titled'
                if visible[0]:
                    return visible[0], 'visible'
                return None, None

            def _activate_window(hwnd):
                try:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                    ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                    ctypes.windll.user32.BringWindowToTop(hwnd)
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

            def _notify_already_running():
                try:
                    _user32 = ctypes.windll.user32
                    _text = "程序已经在运行，已为你切换到已打开的窗口。"
                    _title = "提示"
                    # MB_ICONINFORMATION(0x40) | MB_SETFOREGROUND(0x10000) | MB_TOPMOST(0x40000)
                    _flags = 0x40 | 0x10000 | 0x40000
                    try:
                        _user32.MessageBoxTimeoutW(None, _text, _title, _flags, 0, 2500)
                    except Exception:
                        _user32.MessageBoxW(None, _text, _title, _flags)
                except Exception:
                    pass

            _mutex_name = "Local\\BilibiliDownloader_SingleInstance_v2"
            _is_restart = "--restart" in sys.argv or "--restart" in os.environ.get("_BILI_RESTART_ARGV", "")
            _INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, _mutex_name)
            _last_error = ctypes.windll.kernel32.GetLastError()
            if _is_restart:
                for _try in range(40):
                    if _last_error != 183:
                        break
                    ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
                    time.sleep(0.25)
                    _INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, _mutex_name)
                    _last_error = ctypes.windll.kernel32.GetLastError()
                # 旧实例超过 10 秒还不走：按进程名清掉再接管
                if _last_error == 183:
                    for _pid in _enum_instance_pids():
                        try:
                            if _pid != os.getpid():
                                ctypes.windll.kernel32.TerminateProcess(
                                    ctypes.windll.kernel32.OpenProcess(0x0001, False, _pid), 0)
                        except Exception:
                            pass
                    time.sleep(1.0)
                    ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
                    _INSTANCE_MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, _mutex_name)
                    _last_error = ctypes.windll.kernel32.GetLastError()
            if _last_error == 183 and not _is_restart:
                _hwnd = _find_windows_by_title_prefixes(("B站视频解析工具", "B站视频下载工具", "BilibiliDownloader"))
                if _hwnd:
                    _activate_window(_hwnd)
                    try:
                        ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
                    except Exception:
                        pass
                    _INSTANCE_MUTEX = None
                    _notify_already_running()
                    sys.exit(0)

                _old_pids = _enum_instance_pids()
                _pid_hwnd, _kind = _find_window_of_instance_pids(_old_pids)
                if _pid_hwnd:
                    _activate_window(_pid_hwnd)
                    try:
                        ctypes.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
                    except Exception:
                        pass
                    _INSTANCE_MUTEX = None
                    _notify_already_running()
                    sys.exit(0)

                time.sleep(2)
                _old_pids = _enum_instance_pids()
                _pid_hwnd, _kind = _find_window_of_instance_pids(_old_pids)
                if _pid_hwnd:
                    _activate_window(_pid_hwnd)
                    sys.exit(0)
                for _pid in _old_pids:
                    try:
                        _h = ctypes.windll.kernel32.OpenProcess(1, False, _pid)  # PROCESS_TERMINATE
                        if _h:
                            ctypes.windll.kernel32.TerminateProcess(_h, 1)
                            ctypes.windll.kernel32.CloseHandle(_h)
                    except Exception:
                        pass
                time.sleep(0.5)
        except SystemExit:
            raise
        except Exception:
            pass

    try:
        from downloader import EpisodeDownloadThread
        EpisodeDownloadThread.cleanup_pending_temp_files(ConfigLoader())
    except Exception as e:
        try:
            logger.debug(f"启动清理临时文件失败: {e}")
        except Exception:
            pass

    if sys.platform == 'win32' and not _is_msix_environment():
        try:
            import threading
            from cert_installer import auto_install_cert
            def _install_cert_async():
                try:
                    auto_install_cert(silent=True)
                except Exception as e:
                    try:
                        logger.debug(f"自动安装证书失败: {e}")
                    except Exception:
                        pass
            threading.Thread(target=_install_cert_async, daemon=True).start()
        except Exception as e:
            try:
                logger.debug(f"启动证书安装线程失败: {e}")
            except Exception:
                pass

    try:
        import time
        start_time = time.time()
        try:
            from PyQt5.QtCore import Qt, qInstallMessageHandler
        except ImportError as e:
            _fallback_reason = f"PyQt5导入失败: {e}"
            if getattr(sys, 'frozen', False):
                _fatal_error_exit("启动失败", f"{_fallback_reason}\n\n程序即将退出。")
            print(f"\n[降级模式] {_fallback_reason}")
            print("[降级模式] 已自动降级为命令行模式\n")
            from cli import main as cli_main
            cli_main(fallback_reason=_fallback_reason)
            sys.exit(0)
        stage_times = {}
        QApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        try:
            import pyqt5_bootstrap
            pyqt5_bootstrap.ensure_qt_plugins()
        except Exception as _qe:
            print(f"[启动] Qt 插件路径注册失败(可忽略): {_qe}")
        def message_handler(msg_type, context, message):
            if "Unknown property z-index" not in message:
                print(f"{message}")
        qInstallMessageHandler(message_handler)
        requests.packages.urllib3.disable_warnings()
        try:
            app = SafeQApplication(sys.argv)
        except Exception as e:
            _fallback_reason = f"GUI初始化失败: {e}"
            if getattr(sys, 'frozen', False):
                _fatal_error_exit("启动失败", f"{_fallback_reason}\n\n程序即将退出。")
            print(f"\n[降级模式] {_fallback_reason}")
            print("[降级模式] 已自动降级为命令行模式\n")
            from cli import main as cli_main
            cli_main(fallback_reason=_fallback_reason)
            sys.exit(0)
        font_family, font_size = platform_font()
        font = QFont(font_family, font_size)
        app.setFont(font)
        app.setStyle('Fusion')
        if IS_WINDOWS:
            try:
                from toast_winrt import set_process_app_user_model_id
                set_process_app_user_model_id()
            except Exception:
                pass
            try:
                from toast_winrt import register_aumid_shortcut_async
                register_aumid_shortcut_async()
            except Exception:
                pass
        try:
            from PyQt5.QtGui import QIcon
            _icon_path = get_effective_icon_path()
            if os.path.exists(_icon_path):
                app.setWindowIcon(QIcon(_icon_path))
        except Exception:
            pass
        from ui import init_dpi_scale
        init_dpi_scale()
        from ui import global_dpi_scale
        print(f"DPI scale factor: {global_dpi_scale}")
        stage_times['app_init'] = time.time() - start_time
        splash = SplashScreen()
        splash.show()
        app.processEvents()
        stage_times['splash_show'] = time.time() - start_time
        splash.update_progress(10, "初始化配置...")
        config = ConfigLoader()
        try:
            from PyQt5.QtGui import QIcon
            _icon_path = get_effective_icon_path(config)
            if os.path.exists(_icon_path):
                _icon = QIcon(_icon_path)
                app.setWindowIcon(_icon)
                splash.setWindowIcon(_icon)
        except Exception:
            pass
        app.processEvents()
        stage_times['config_init'] = time.time() - start_time
        import threading
        env_check_done = threading.Event()
        env_result_holder = [None]
        def run_env_check():
            try:
                from env_checker import check_environment
                result = check_environment()
                env_result_holder[0] = result
                print("环境检查结果:")
                print(f'Python版本: {result["python"]["version"]} - {"OK" if result["python"]["ok"] else "需要Python 3.6+"}')
                print(f'FFmpeg: {result["ffmpeg"]["path"] if result["ffmpeg"]["path"] else "未找到"} - {"OK" if result["ffmpeg"]["ok"] else "需要修复"}')
                print(f'依赖包: {"全部安装" if result["dependencies"]["ok"] else "缺失: " + str(result["dependencies"]["missing"])}')
                print(f'网络连接: {"OK" if result["network"]["ok"] else "需要检查网络"}')
                print(f'写入权限: {"OK" if result["write_permission"]["ok"] else "需要检查权限"}')
                print(f'整体状态: {"就绪" if result["all_ok"] else "需要修复"}')
            except Exception as e:
                logger.error(f"环境检查失败: {e}")
            finally:
                env_check_done.set()
        env_thread = threading.Thread(target=run_env_check, daemon=True)
        env_thread.start()
        splash.update_progress(20, "检查环境...")
        app.processEvents()
        splash.update_progress(30, "初始化组件...")
        app.processEvents()
        tool_missing = False
        try:
            splash.update_progress(35, "检查工具文件...")
            app.processEvents()
            from tool_manager import get_tool_manager
            tool_manager = get_tool_manager()
            tool_status = tool_manager.check_tools_installed()
            print(f"工具检查结果: {tool_status}")
            if not (tool_status['ffmpeg_exists'] and tool_status['bento4_exists']):
                tool_missing = True
                print("工具未完全安装")
            else:
                print("工具已安装")
            splash.update_progress(45, "工具检查完成")
            app.processEvents()
        except Exception as e:
            logger.error(f"工具检查失败: {e}")
            import traceback
            logger.debug("traceback", exc_info=True)
            splash.update_progress(45, "工具检查跳过")
            app.processEvents()
        parser = [None]
        task_manager = [None]
        download_manager = [None]
        components_ready = threading.Event()
        def init_components():
            try:
                print("开始初始化组件...")
                from task_manager import TaskManager
                print("正在初始化TaskManager...")
                task_manager[0] = TaskManager()
                print("TaskManager初始化成功")
                from bilibili_parser import BilibiliParser
                print("正在初始化BilibiliParser...")
                parser[0] = BilibiliParser(config=config)
                print(f"BilibiliParser初始化成功，parser[0] = {parser[0]}")
                from downloader import DownloadManager
                print("正在初始化DownloadManager...")
                max_threads = config.get_app_setting("max_threads", 2)
                download_manager[0] = DownloadManager(
                    parser=parser[0],
                    task_manager=task_manager[0],
                    max_threads=max_threads,
                    max_concurrent_tasks=max_threads,
                    config=config
                )
                print("DownloadManager初始化成功")
            except Exception as e:
                logger.error(f"组件初始化失败: {e}")
                import traceback
                logger.debug("traceback", exc_info=True)
                logger.error(f"组件初始化异常详情已记录")
            finally:
                print("组件初始化完成，设置components_ready事件")
                components_ready.set()
        component_thread = threading.Thread(target=init_components, daemon=True)
        component_thread.start()
        progress_timer_start = time.time()
        def poll_component_progress():
            # 30秒超时不再等待
            if components_ready.is_set() or time.time() - progress_timer_start > 30:
                if not components_ready.is_set():
                    try:
                        logger.error("组件初始化超时(30秒)，跳过等待直接创建主窗口")
                    except Exception:
                        pass
                splash.update_progress(80, "组件初始化完成")
                app.processEvents()
                QTimer.singleShot(50, create_main_window)
                return
            elapsed = time.time() - progress_timer_start
            progress = 45 + min(int(elapsed / 8 * 35), 35)
            splash.update_progress(progress, "初始化组件...")
            app.processEvents()
            QTimer.singleShot(100, poll_component_progress)
        QTimer.singleShot(100, poll_component_progress)
        window = None
        def create_main_window():
            global window
            _STARTUP_STATE['constructing'] = True
            # 主窗口必须创建成功
            try:
                window = BilibiliDownloader(
                    config=config,
                    task_manager=task_manager[0],
                    download_manager=download_manager[0]
                )
                window.parser = parser[0]
                _STARTUP_STATE['constructing'] = False
            except Exception:
                _STARTUP_STATE['constructing'] = False
                import traceback as _tb
                _err = _tb.format_exc()
                try:
                    logger.error(f"主窗口创建失败:\n{_err}")
                except Exception:
                    pass
                _fatal_error_exit("启动失败", f"主窗口创建失败，程序即将退出。\n\n{_err[-1500:]}")

            def _setup_v_voucher_callback(win, par):
                if not par:
                    return
                def _v_voucher_callback(data):
                    if data.get('type') != 'geetest':
                        return {}
                    result = {}
                    done_event = threading.Event()
                    def _on_done(res):
                        result.update(res)
                        done_event.set()
                    win.v_voucher_captcha_requested.emit(data, _on_done)
                    done_event.wait(timeout=120)
                    return {
                        'validate': result.get('validate', ''),
                        'seccode': result.get('seccode', '')
                    } if result.get('validate') and result.get('seccode') else {}
                par.v_voucher_callback = _v_voucher_callback
            try:
                _setup_v_voucher_callback(window, parser[0])
            except Exception:
                pass

            try:
                app.aboutToQuit.connect(window._apply_pending_update_on_exit)
            except Exception:
                pass

            try:
                app.processEvents()
                splash.update_progress(95, "加载完成...")
                app.processEvents()
                splash.close_with_animation()
                try:
                    _start_max = bool(config.get_app_setting("start_maximized", True))
                except Exception:
                    _start_max = True
                try:
                    _last_maxed = bool(config.get_app_setting("window_maximized", False))
                except Exception:
                    _last_maxed = False
                saved_geo = config.get_app_setting("window_geometry", "")
                screen = QApplication.primaryScreen()
                if _start_max or _last_maxed:
                    if not saved_geo and screen:
                        window.setGeometry(screen.availableGeometry())
                    window.showMaximized()
                else:
                    if saved_geo:
                        window.show()
                    else:
                        sg = screen.availableGeometry() if screen else None
                        if sg:
                            w = int(sg.width() * 0.72)
                            h = int(sg.height() * 0.78)
                            window.resize(w, h)
                            window.move(sg.left() + (sg.width() - w) // 2,
                                        sg.top() + (sg.height() - h) // 2)
                        window.show()
                window.raise_()
                window.activateWindow()
            except Exception:
                import traceback as _tb
                _err = _tb.format_exc()
                try:
                    logger.error(f"主窗口显示失败:\n{_err}")
                except Exception:
                    pass
                try:
                    window.showMaximized()
                    window.raise_()
                    window.activateWindow()
                except Exception:
                    _fatal_error_exit("启动失败", f"主窗口显示失败，程序即将退出。\n\n{_err[-1500:]}")
            app.processEvents()
            _STARTUP_STATE['window_visible'] = bool(window is not None and window.isVisible())
            try:
                from ui import repair_shortcuts_after_update
                threading.Thread(target=repair_shortcuts_after_update, daemon=True).start()
            except Exception:
                pass
            QTimer.singleShot(100, init_after_ui)
        def ensure_splash_closed():
            import time
            start_time = time.time()
            while time.time() - start_time < 180:
                if window is not None:
                    break
                time.sleep(0.1)
            time.sleep(3)
            try:
                QTimer.singleShot(0, splash.hide)
            except Exception:
                pass
        thread = threading.Thread(target=ensure_splash_closed, daemon=True)
        thread.start()
        def init_after_ui():
            print("=== init_after_ui开始执行 ===")
            import time
            for _ in range(10):
                if window:
                    break
                time.sleep(0.1)
            if not window:
                print("window未准备好，退出init_after_ui")
                return
            print("window已准备好，继续执行init_after_ui")
            if tool_missing:
                def show_tool_missing_dialog():
                    from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
                    from PyQt5.QtCore import Qt
                    dialog = QDialog(window)
                    dialog.setWindowTitle("工具缺失提示")
                    dialog.setMinimumSize(450, 250)
                    layout = QVBoxLayout(dialog)
                    title_label = QLabel("工具缺失提示")
                    title_label.setAlignment(Qt.AlignCenter)
                    title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #d4380d; margin: 15px 10px 5px 10px;")
                    layout.addWidget(title_label)
                    info_label = QLabel(
                        "检测到 FFmpeg 和 Bento4 工具未完整安装！\n\n"
                        "这些工具对于视频下载和处理非常重要。\n"
                        "是否现在安装这些工具？"
                    )
                    info_label.setAlignment(Qt.AlignCenter)
                    info_label.setWordWrap(True)
                    info_label.setStyleSheet("font-size: 14px; margin: 10px; color: #333;")
                    layout.addWidget(info_label)
                    button_layout = QHBoxLayout()
                    install_button = QPushButton("立即安装")
                    install_button.setMinimumHeight(40)
                    install_button.setStyleSheet("""
                        QPushButton {
                            background-color: #1890ff;
                            color: white;
                            border: none;
                            border-radius: 6px;
                            font-size: 14px;
                            font-weight: bold;
                        }
                        QPushButton:hover {
                            background-color: #40a9ff;
                        }
                    """)
                    install_button.clicked.connect(dialog.accept)
                    button_layout.addWidget(install_button)
                    later_button = QPushButton("稍后安装")
                    later_button.setMinimumHeight(40)
                    later_button.setStyleSheet("""
                        QPushButton {
                            background-color: #f0f0f0;
                            color: #333;
                            border: none;
                            border-radius: 6px;
                            font-size: 14px;
                        }
                        QPushButton:hover {
                            background-color: #e0e0e0;
                        }
                    """)
                    later_button.clicked.connect(dialog.reject)
                    button_layout.addWidget(later_button)
                    layout.addLayout(button_layout)
                    result = dialog.exec_()
                    if result == QDialog.Accepted:
                        QTimer.singleShot(100, lambda: window.install_tools())
                QTimer.singleShot(500, show_tool_missing_dialog)
            def init_tasks():
                def check_hevc():
                    hevc_supported = parser[0].check_hevc_support()
                    window.signal_emitter.hevc_checked.emit(hevc_supported)
                def check_cookie():
                    if parser[0].cookies:
                        success, msg = parser[0].verify_cookie()
                        if not success:
                            window.signal_emitter.show_notification.emit("您的登录状态已过期，请重新登录", "warning")
                def load_user_info():
                    user_info = parser[0].get_user_info()
                    window.signal_emitter.user_info_updated.emit(user_info)
                import threading
                def run_init_tasks():
                    try:
                        check_hevc()
                        check_cookie()
                        load_user_info()
                    except Exception as e:
                        logger.error(f"初始化任务失败: {str(e)}")
                thread = threading.Thread(target=run_init_tasks, daemon=True)
                thread.start()
            def handle_cookie_verification(cookie_input):
                print(f"收到Cookie验证请求，Cookie长度：{len(cookie_input)}")
                def verify_in_thread():
                    try:
                        print("开始保存Cookie...")
                        save_success = parser[0].save_cookies(cookie_input)
                        print(f"Cookie保存结果：{save_success}")
                        if not save_success:
                            print("Cookie格式错误")
                            window.signal_emitter.cookie_verified.emit(False, "Cookie格式错误！支持：JSON对象列表、key1=value1;格式")
                            return
                        print("开始验证Cookie...")
                        success, msg = parser[0].verify_cookie()
                        print(f"Cookie验证结果：{success}, {msg}")
                        window.signal_emitter.cookie_verified.emit(success, msg)
                    except Exception as e:
                        logger.warning(f"Cookie处理异常: {e}")
                        import traceback
                        logger.debug("traceback", exc_info=True)
                        window.signal_emitter.cookie_verified.emit(False, f"Cookie处理失败：{str(e)}")
                thread = threading.Thread(target=verify_in_thread, daemon=True)
                thread.start()
            window.signal_emitter.verify_cookie.connect(handle_cookie_verification)
            def handle_load_user_info():
                def load_in_thread():
                    try:
                        user_info = parser[0].get_user_info(force_refresh=True)
                        window.signal_emitter.user_info_updated.emit(user_info)
                    except Exception as e:
                        logger.warning(f"加载用户信息失败: {e}")
                        import traceback
                        logger.debug("traceback", exc_info=True)
                thread = threading.Thread(target=load_in_thread, daemon=True)
                thread.start()
            window.signal_emitter.load_user_info.connect(handle_load_user_info)
            def handle_check_hevc():
                def check_in_thread():
                    try:
                        hevc_supported = parser[0].check_hevc_support()
                        window.signal_emitter.hevc_checked.emit(hevc_supported)
                    except Exception as e:
                        logger.warning(f"检查HEVC支持失败: {e}")
                        import traceback
                        logger.debug("traceback", exc_info=True)
                thread = threading.Thread(target=check_in_thread, daemon=True)
                thread.start()
            window.signal_emitter.check_hevc.connect(handle_check_hevc)
            def handle_install_hevc():
                def install_in_thread():
                    def progress_callback(progress):
                        window.signal_emitter.hevc_download_progress.emit(int(progress))
                    try:
                        success, msg = parser[0].install_hevc(progress_callback)
                        window.signal_emitter.hevc_install_finished.emit(success, msg)
                    except Exception as e:
                        window.signal_emitter.hevc_install_finished.emit(False, f"安装失败：{str(e)}")
                thread = threading.Thread(target=install_in_thread, daemon=True)
                thread.start()
            window.signal_emitter.install_hevc.connect(handle_install_hevc)
            def start_cookie_polling():
                def poll_cookie_status():
                    def poll_in_thread():
                        try:
                            if parser[0] and parser[0].cookies:
                                success, msg = parser[0].verify_cookie()
                                if not success:
                                    window.signal_emitter.user_info_updated.emit({"success": False})
                        except Exception as e:
                            logger.warning(f"Cookie轮询验证失败: {e}")
                        run_on_main_thread(lambda: QTimer.singleShot(5 * 60 * 1000, poll_cookie_status))
                    thread = threading.Thread(target=poll_in_thread, daemon=True)
                    thread.start()
                poll_cookie_status()
            start_cookie_polling()
            def handle_parse_media(url, is_tv_mode, episode_page=0, parse_mode=None):
                print("=== handle_parse_media被调用 ===")
                if parse_mode == "auto" or not parse_mode:
                    parse_mode = None
                try:
                    _rw = getattr(window, 'episode_range_edit', None)
                    episode_range = _rw.text().strip() if _rw else ""
                except Exception:
                    episode_range = ""
                print(f"URL: {url}, is_tv_mode: {is_tv_mode}, episode_page: {episode_page}, parse_mode: {parse_mode}, episode_range: {episode_range}")
                def progress_callback(progress, message):
                    print(f"解析进度: {progress}%, {message}")
                    window.signal_emitter.parse_progress.emit(int(progress), message)
                def parse_in_thread():
                    print("=== parse_in_thread开始执行 ===")
                    try:
                        print("开始解析URL...")
                        if parser[0] is None:
                            print("解析器未初始化")
                            window.signal_emitter.parse_finished.emit({"success": False, "error": "解析器未初始化，请重启应用"})
                            return
                        media_parse_result = parser[0].parse_media_url(url)
                        print(f"media_parse_result: {media_parse_result}")
                        if media_parse_result.get("error"):
                            print("发送解析失败信号")
                            window.signal_emitter.parse_finished.emit({"success": False, "error": media_parse_result["error"]})
                            return
                        media_type = media_parse_result["type"]
                        media_id = media_parse_result["id"]
                        print(f"media_type: {media_type}, media_id: {media_id}")
                        if not media_type or not media_id:
                            print("发送无效媒体ID信号")
                            window.signal_emitter.parse_finished.emit({"success": False, "error": "未识别到有效媒体ID（支持BV/ss/av号）"})
                            return
                        try:
                            print("开始解析媒体信息...")
                            url_page = media_parse_result.get("page")
                            if url_page and not episode_page and parse_mode != "video_only":
                                episode_page = url_page
                            ep = episode_page if episode_page and episode_page > 0 else None
                            media_info = parser[0].parse_media(media_type, media_id, is_tv_mode, progress_callback, episode_page=ep, parse_mode=parse_mode, episode_range=episode_range)
                            print(f"media_info获取成功，发送信号")
                            window.signal_emitter.parse_finished.emit(media_info)
                        except Exception as e:
                            logger.error(f"解析媒体信息失败: {e}")
                            import traceback
                            logger.debug("traceback", exc_info=True)
                            window.signal_emitter.parse_finished.emit({"success": False, "error": f"解析失败：{str(e)}"})
                    except Exception as e:
                        logger.warning(f"解析URL失败: {e}")
                        import traceback
                        logger.debug("traceback", exc_info=True)
                        window.signal_emitter.parse_finished.emit({"success": False, "error": f"解析失败：{str(e)}"})
                print("启动解析线程")
                thread = threading.Thread(target=parse_in_thread, daemon=True)
                thread.start()
            print("=== 连接parse_start信号 ===")
            window.signal_emitter.parse_start.connect(handle_parse_media)
            print("=== parse_start信号连接成功 ===")
            window.signal_emitter.start_download.connect(download_manager[0].start_download)
            def handle_same_task_exists(download_params):
                print("检测到相同任务已存在，打开下载窗口")
                window.show_notification("相同的下载任务已存在！", "info")
                def switch_to_download():
                    if hasattr(window, 'batch_windows'):
                        existing_window = None
                        for w in window.batch_windows.values():
                            try:
                                from ui import BatchDownloadWindow
                                if isinstance(w, BatchDownloadWindow):
                                    existing_window = w
                                    break
                            except:
                                pass
                        if existing_window:
                            existing_window.show()
                            existing_window.raise_()
                    elif hasattr(window, 'download_widget') and hasattr(window, 'video_info_widget'):
                        try:
                            window.video_info_widget.hide()
                            window.download_widget.show()
                            if hasattr(window, 'expanded_widget') and window.expanded_widget:
                                window.expanded_widget.adjustSize()
                        except Exception as e:
                            logger.error(f"切换下载界面失败: {e}")
                run_on_main_thread(switch_to_download)
            download_manager[0].same_task_exists.connect(handle_same_task_exists)
            window.signal_emitter.same_task_exists.connect(handle_same_task_exists)
            def handle_cancel_download():
                download_manager[0].cancel_all()
                run_on_main_thread(lambda: window.status_label.setText("下载已取消"))
            window.signal_emitter.cancel_download.connect(handle_cancel_download)
            download_manager[0].global_progress_updated.connect(window.update_download_progress)
            download_manager[0].episode_progress_updated.connect(window.update_episode_progress)
            download_manager[0].episode_finished.connect(window.finish_episode)
            if hasattr(window, 'floating_ball') and window.floating_ball:
                download_manager[0].global_progress_updated.connect(window.floating_ball.update_download_progress)
                download_manager[0].episode_progress_updated.connect(window.floating_ball.update_episode_progress)
                print("=== 下载进度信号已连接到悬浮球 ===")
            else:
                def connect_floating_ball_signals():
                    if hasattr(window, 'floating_ball') and window.floating_ball:
                        download_manager[0].global_progress_updated.connect(window.floating_ball.update_download_progress)
                        download_manager[0].episode_progress_updated.connect(window.floating_ball.update_episode_progress)
                        print("=== 下载进度信号已连接到悬浮球 ===")
                QTimer.singleShot(1000, connect_floating_ball_signals)
            init_tasks()
        stage_times['startup_complete'] = time.time() - start_time
        print("=== 启动性能分析 ===")
        print(f"应用初始化: {stage_times['app_init']:.3f}s")
        print(f"启动界面显示: {stage_times['splash_show']:.3f}s")
        print(f"配置初始化: {stage_times['config_init']:.3f}s")
        print(f"总启动时间: {stage_times['startup_complete']:.3f}s")
        print("====================")
        def excepthook(exc_type, exc_value, exc_traceback):
            try:
                if exc_type is _HangRecovered:
                    logger.error("[卡死检测] 主线程已从阻塞中恢复，进度已保留")
                    try:
                        def _notify_hang_recovered():
                            try:
                                from PyQt5.QtWidgets import QMessageBox
                                if window:
                                    QMessageBox.information(window, "卡死恢复", "检测到程序卡死，已自动摆脱卡死")
                            except Exception:
                                pass
                        QTimer.singleShot(200, _notify_hang_recovered)
                    except Exception:
                        pass
                    return
                if 'sipBadCatcherResult' in str(exc_value):
                    try:
                        import traceback as _tb
                        _tb.print_exception(exc_type, exc_value, exc_traceback)
                    except Exception:
                        pass
                    return
                import traceback
                import os
                error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
                file_path = "未知文件"
                line_number = 0
                if exc_traceback:
                    frame = exc_traceback.tb_frame
                    file_path = frame.f_code.co_filename
                    line_number = exc_traceback.tb_lineno
                code_context = ""
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        start_line = max(0, line_number - 5)
                        end_line = min(len(lines), line_number + 4)
                        code_lines = []
                        for i in range(start_line, end_line):
                            line_num = i + 1
                            line_content = lines[i].rstrip()
                            if line_num == line_number:
                                code_lines.append(f"<span style='color: red; font-weight: bold;'>{line_num:4d} | {line_content}</span>")
                            else:
                                code_lines.append(f"{line_num:4d} | {line_content}")
                        code_context = '<br>'.join(code_lines)
                    except Exception:
                        code_context = "无法读取文件内容"
                try:
                    _cs = getattr(window, 'cloud_service', None)
                    if _cs is None:
                        from cloud_service import CloudService
                        _cs = CloudService()
                    log_content = ""
                    try:
                        import logging
                        log_dir = os.path.join(os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)), "logs")
                        if os.path.isdir(log_dir):
                            log_files = sorted([f for f in os.listdir(log_dir) if f.endswith('.log')], key=lambda x: os.path.getmtime(os.path.join(log_dir, x)), reverse=True)
                            if log_files:
                                log_path = os.path.join(log_dir, log_files[0])
                                with open(log_path, 'r', encoding='utf-8', errors='replace') as lf:
                                    log_content = lf.read()[-500000:]  # 最近500KB
                    except Exception:
                        pass
                    _cs.report_error(exc_type.__name__, str(exc_value), error_msg,
                                     {"file": file_path, "line": line_number},
                                     error_line=line_number, error_file=file_path,
                                     log_content=log_content)
                except Exception:
                    pass
                if window:
                    try:
                        window.signal_emitter.show_debug_window.emit(error_msg, code_context, file_path)
                    except Exception:
                        logger.error(f"显示调试窗口失败: {error_msg[:100]}")
                else:
                    logger.error(f"未捕获异常(无窗口): {error_msg[:200]}")
            except Exception:
                pass
        sys.excepthook = excepthook

        # 心跳+看门狗防卡死
        _heartbeat = [time.time()]

        def _update_heartbeat():
            _heartbeat[0] = time.time()

        _hb_timer = QTimer()
        _hb_timer.timeout.connect(_update_heartbeat)
        _hb_timer.start(1000)

        def _hang_watchdog():
            import threading as _th
            import subprocess
            import ctypes as _ct
            hang_threshold = 10.0
            injected_at = None
            restart_limit = int(os.environ.get('BILIDOWN_HANG_RESTART', '0') or '0')
            while True:
                time.sleep(1)
                elapsed = time.time() - _heartbeat[0]
                if elapsed <= hang_threshold:
                    injected_at = None
                    continue

                # 启动阶段主线程忙于构建窗口属正常，注入异常会打断启动；
                # 已弹出致命错误框时同样不再注入，避免掩盖真实错误
                if not _STARTUP_STATE['window_visible'] or _STARTUP_STATE['fatal_dialog']:
                    injected_at = None
                    if elapsed > 30 and int(elapsed) % 30 == 0:
                        try:
                            logger.error(f"[卡死检测] 启动阶段主线程已 {int(elapsed)} 秒未响应，暂不注入异常")
                        except Exception:
                            pass
                    continue

                if injected_at is None:
                    injected_at = time.time()
                    try:
                        logger.error(f"[卡死检测] 主线程已 {int(elapsed)} 秒未响应，注入恢复异常")
                        for _tid, _frame in sys._current_frames().items():
                            if _tid == _th.main_thread().ident:
                                _stack = ''.join(traceback.format_stack(_frame))
                                logger.error(f"[卡死检测] 主线程堆栈:\n{_stack}")
                                break
                    except Exception:
                        pass
                    try:
                        _main_tid = _th.main_thread().ident
                        _ct.pythonapi.PyThreadState_SetAsyncExc.argtypes = [_ct.c_ulong, _ct.py_object]
                        _ct.pythonapi.PyThreadState_SetAsyncExc.restype = _ct.c_int
                        _ret = _ct.pythonapi.PyThreadState_SetAsyncExc(_main_tid, _ct.py_object(_HangRecovered))
                        if _ret == 0:
                            logger.error("[卡死检测] 注入恢复异常失败：无效线程")
                        elif _ret > 1:
                            _ct.pythonapi.PyThreadState_SetAsyncExc(_main_tid, None)
                            logger.error("[卡死检测] 注入恢复异常状态异常，已撤销")
                        else:
                            logger.error("[卡死检测] 已向主线程注入恢复异常")
                    except Exception as _e:
                        logger.error(f"[卡死检测] 注入恢复异常失败: {_e}")
                    continue

                if time.time() - injected_at > 30:
                    if restart_limit >= 3:
                        logger.error("[卡死检测] 已达自动重启上限，放弃恢复")
                        break
                    try:
                        logger.error("[卡死检测] 注入恢复无效，作为最后手段重启")
                        os.environ['BILIDOWN_HANG_RESTART'] = str(restart_limit + 1)
                        if _INSTANCE_MUTEX:
                            try:
                                _ct.windll.kernel32.CloseHandle(_INSTANCE_MUTEX)
                            except Exception:
                                pass
                        if getattr(sys, 'frozen', False):
                            _exe = sys.executable
                            _args = list(sys.argv[1:])
                        else:
                            _exe = sys.executable
                            _args = ['-u', os.path.abspath(__file__)] + list(sys.argv[1:])
                        subprocess.Popen([_exe] + _args, cwd=os.path.dirname(os.path.abspath(__file__)))
                        logger.error("[卡死检测] 已启动新实例，即将退出当前进程")
                    except Exception as _e:
                        logger.error(f"[卡死检测] 自动重启失败: {_e}")
                        break
                    os._exit(1)

        _wd_thread = threading.Thread(target=_hang_watchdog, daemon=True)
        _wd_thread.start()

        def _window_watchdog():
            import threading as _th
            _main_tid = _th.main_thread().ident
            _deadline = 150.0
            _t0 = time.time()
            while True:
                time.sleep(5)
                try:
                    _visible = window is not None and window.isVisible()
                except Exception:
                    _visible = False
                if _visible:
                    return  # 窗口已显示看门狗退役
                if _STARTUP_STATE['fatal_dialog']:
                    return  # 已弹出致命错误框，真实原因已在其中显示，不再重复误报
                if _STARTUP_STATE['constructing']:
                    continue  # 正在构建主窗口，主线程在加载界面与网络数据，不判定为启动失败
                if time.time() - _t0 > _deadline:
                    _dumps = []
                    try:
                        for _tid, _frame in sys._current_frames().items():
                            _tag = "主线程" if _tid == _main_tid else f"线程{_tid}"
                            _dumps.append(f"=== {_tag} ===\n" + ''.join(traceback.format_stack(_frame)))
                        _stack_info = '\n'.join(_dumps)
                    except Exception:
                        _stack_info = "堆栈获取失败"
                    _fatal_error_exit(
                        "启动失败",
                        f"启动后{int(_deadline)}秒主窗口仍未显示，为避免占用单实例锁已自动退出。\n\n{_stack_info[-1200:]}"
                    )
        threading.Thread(target=_window_watchdog, daemon=True).start()

        try:
            app.exec_()
        except Exception as e:
            import traceback
            logger.error(f"应用运行异常: {e}")
            logger.debug("traceback", exc_info=True)
            if getattr(sys, 'frozen', False):
                os._exit(1)
            input("按回车键退出...")
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        logger.error(f"GUI启动失败: {error_msg}")
        if getattr(sys, 'frozen', False):
            _fatal_error_exit("启动失败", f"GUI启动失败，程序即将退出。\n\n{error_msg[-1500:]}")
        print(f"\n[降级模式] GUI启动失败: {e}")
        print("[降级模式] 已自动降级为命令行模式\n")
        try:
            from cli import main as cli_main
            cli_main(fallback_reason=str(e))
        except Exception as cli_err:
            print(f"[错误] CLI模式也启动失败: {cli_err}")
            input("按回车键退出...")
