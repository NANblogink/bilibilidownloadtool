import sys
import os
import requests
import time
import json
import traceback
from PyQt5.QtWidgets import QApplication, QSplashScreen, QLabel, QVBoxLayout, QWidget, QProgressBar
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer
from ui import BilibiliDownloader
from bilibili_parser import BilibiliParser
from downloader import DownloadManager
from config import ConfigLoader
from task_manager import TaskManager
from utils import get_unique_filename
from env_checker import check_environment

IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'


def _get_platform_font():
    """获取跨平台默认字体"""
    if IS_MACOS:
        return QFont("PingFang SC", 13)
    elif IS_WINDOWS:
        return QFont("Microsoft YaHei", 9)
    else:
        return QFont("Noto Sans CJK SC", 10)

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
                print(f"[SafeQApplication] 未处理TypeError: {str(e)}")
                traceback.print_exc()
            except Exception:
                pass
            return True
        except Exception as e:
            try:
                print(f"[SafeQApplication] 未处理异常: {type(e).__name__}: {str(e)}")
            except Exception:
                pass
            return True

def _global_exception_hook(exc_type, exc_value, exc_tb):
    try:
        print(f"[全局异常钩子] {exc_type.__name__}: {exc_value}")
        traceback.print_exception(exc_type, exc_value, exc_tb)
    except Exception:
        pass

sys.excepthook = _global_exception_hook
def load_version_info():
    try:
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        version_file = os.path.join(script_dir, 'version_info.json')
        with open(version_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取版本信息失败：{str(e)}")
        return {
            "version": "2026年5月1日09:38:46维护版",
            "author": "寒烟似雪",
            "qq": "2273962061",
            "description": "B站视频解析下载工具"
        }
version_info = load_version_info()
class SplashScreen(QWidget):
    def __init__(self):
        super().__init__()
        from ui import scale
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
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
    try:
        import time
        start_time = time.time()
        stage_times = {}
        from PyQt5.QtCore import Qt, qInstallMessageHandler
        QApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        def message_handler(msg_type, context, message):
            if "Unknown property z-index" not in message:
                print(f"{message}")
        qInstallMessageHandler(message_handler)
        requests.packages.urllib3.disable_warnings()
        app = SafeQApplication(sys.argv)
        font = _get_platform_font()
        app.setFont(font)
        app.setStyle('Fusion')
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
                print(f"环境检查出错：{str(e)}")
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
            print(f"工具检查失败: {str(e)}")
            import traceback
            traceback.print_exc()
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
                    max_concurrent_tasks=max_threads
                )
                print("DownloadManager初始化成功")
            except Exception as e:
                print(f"初始化组件时出错：{str(e)}")
                import traceback
                traceback.print_exc()
                print(f"初始化失败后，parser[0] = {parser[0]}")
            finally:
                print("组件初始化完成，设置components_ready事件")
                components_ready.set()
        component_thread = threading.Thread(target=init_components, daemon=True)
        component_thread.start()
        progress_timer_start = time.time()
        def poll_component_progress():
            if components_ready.is_set():
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
            window = BilibiliDownloader(
                config=config,
                task_manager=task_manager[0],
                download_manager=download_manager[0]
            )
            window.parser = parser[0]
            app.processEvents()
            splash.update_progress(95, "加载完成...")
            app.processEvents()
            splash.close_with_animation()
            window.showMaximized()
            window.raise_()
            window.activateWindow()
            app.processEvents()
            QTimer.singleShot(100, init_after_ui)
        def ensure_splash_closed():
            import time
            start_time = time.time()
            while time.time() - start_time < 3:
                time.sleep(0.01)
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
                    QTimer.singleShot(0, lambda: window.update_hevc_status(hevc_supported))
                def check_cookie():
                    if parser[0].cookies:
                        success, msg = parser[0].verify_cookie()
                        if not success:
                            QTimer.singleShot(0, lambda: window.show_notification("您的登录状态已过期，请重新登录", "warning"))
                def load_user_info():
                    user_info = parser[0].get_user_info()
                    QTimer.singleShot(0, lambda: window.update_user_info(user_info))
                import threading
                def run_init_tasks():
                    try:
                        check_hevc()
                        check_cookie()
                        load_user_info()
                    except Exception as e:
                        print(f"初始化任务执行失败：{str(e)}")
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
                        print(f"Cookie处理异常：{str(e)}")
                        import traceback
                        traceback.print_exc()
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
                        print(f"加载用户信息异常：{str(e)}")
                        import traceback
                        traceback.print_exc()
                thread = threading.Thread(target=load_in_thread, daemon=True)
                thread.start()
            window.signal_emitter.load_user_info.connect(handle_load_user_info)
            def handle_check_hevc():
                def check_in_thread():
                    try:
                        hevc_supported = parser[0].check_hevc_support()
                        QTimer.singleShot(0, lambda: window.update_hevc_status(hevc_supported))
                    except Exception as e:
                        print(f"检查HEVC支持异常：{str(e)}")
                        import traceback
                        traceback.print_exc()
                thread = threading.Thread(target=check_in_thread, daemon=True)
                thread.start()
            window.signal_emitter.check_hevc.connect(handle_check_hevc)
            def handle_install_hevc():
                def install_in_thread():
                    def progress_callback(progress):
                        QTimer.singleShot(0, lambda: window.update_hevc_progress(progress))
                    try:
                        success, msg = parser[0].install_hevc(progress_callback)
                        QTimer.singleShot(0, lambda: window.on_hevc_install_finish(success, msg))
                    except Exception as e:
                        QTimer.singleShot(0, lambda: window.on_hevc_install_finish(False, f"安装失败：{str(e)}"))
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
                                    QTimer.singleShot(0, lambda: window.update_user_info({"success": False}))
                        except Exception as e:
                            print(f"Cookie轮询异常：{str(e)}")
                        QTimer.singleShot(5 * 60 * 1000, poll_cookie_status)
                    thread = threading.Thread(target=poll_in_thread, daemon=True)
                    thread.start()
                poll_cookie_status()
            start_cookie_polling()
            def handle_parse_media(url, is_tv_mode):
                print("=== handle_parse_media被调用 ===")
                print(f"URL: {url}, is_tv_mode: {is_tv_mode}")
                def progress_callback(progress, message):
                    print(f"解析进度: {progress}%, {message}")
                    QTimer.singleShot(0, lambda: window.update_parse_progress(progress, message))
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
                            media_info = parser[0].parse_media(media_type, media_id, is_tv_mode, progress_callback)
                            print(f"media_info获取成功，发送信号")
                            window.signal_emitter.parse_finished.emit(media_info)
                        except Exception as e:
                            print(f"解析媒体信息时出错: {str(e)}")
                            import traceback
                            traceback.print_exc()
                            window.signal_emitter.parse_finished.emit({"success": False, "error": f"解析失败：{str(e)}"})
                    except Exception as e:
                        print(f"handle_parse_media异常: {str(e)}")
                        import traceback
                        traceback.print_exc()
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
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: window.show_notification("相同的下载任务已存在！", "info") if hasattr(window, 'show_notification') else None)
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
                            print(f"切换到下载窗口失败：{str(e)}")
                QTimer.singleShot(0, switch_to_download)
            download_manager[0].same_task_exists.connect(handle_same_task_exists)
            window.signal_emitter.same_task_exists.connect(handle_same_task_exists)
            def handle_cancel_download():
                download_manager[0].cancel_all()
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, lambda: window.status_label.setText("下载已取消"))
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
                if window:
                    try:
                        window.signal_emitter.show_debug_window.emit(error_msg, code_context, file_path)
                    except Exception:
                        print(f"应用程序运行时错误：{error_msg}")
                else:
                    print(f"应用程序运行时错误：{error_msg}")
            except Exception:
                pass
        sys.excepthook = excepthook
        try:
            app.exec_()
        except Exception as e:
            import traceback
            print(f"应用程序运行时错误：{str(e)}")
            print(traceback.format_exc())
            input("按回车键退出...")
    except Exception as e:
        import traceback
        print(f"应用程序启动失败：{str(e)}")
        print(traceback.format_exc())
        input("按回车键退出...")