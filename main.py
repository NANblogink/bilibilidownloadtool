import sys
import requests
import time
import json
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
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setFixedSize(600, 400)
        self.setStyleSheet("background-color: #1890ff;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(20)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignCenter)
        content_layout.setSpacing(20)
        title_label = QLabel(f"B站解析工具{version_info['version']}")
        title_label.setStyleSheet("font-size: 36px; font-weight: bold; color: white;")
        title_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(title_label)
        author_label = QLabel("作者：寒烟似雪")
        author_label.setStyleSheet("font-size: 18px; color: white;")
        author_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(author_label)
        qq_label = QLabel("QQ：2273962061")
        qq_label.setStyleSheet("font-size: 16px; color: white;")
        qq_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(qq_label)
        self.loading_label = QLabel("加载中...")
        self.loading_label.setStyleSheet("font-size: 14px; color: white;")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setFixedHeight(20)
        content_layout.addWidget(self.loading_label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(400)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.setStyleSheet("QProgressBar { border-radius: 6px; background-color: rgba(255, 255, 255, 0.2); color: #1890ff; font-size: 10px; } QProgressBar::chunk { border-radius: 6px; background-color: white; background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffffff, stop:1 #e0e0e0); }")
        content_layout.addWidget(self.progress_bar, 0, Qt.AlignCenter)
        main_layout.addWidget(content_widget, stretch=1)
        copyright_label = QLabel("© 2026 寒烟似雪. All rights reserved.")
        copyright_label.setStyleSheet("font-size: 12px; color: rgba(255, 255, 255, 0.8);")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setFixedHeight(30)
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
        print("正在检查环境...")
        from env_checker import check_environment
        env_result = check_environment()
        print("环境检查结果:")
        print(f'Python版本: {env_result["python"]["version"]} - {"OK" if env_result["python"]["ok"] else "需要Python 3.6+"}')
        print(f'FFmpeg: {env_result["ffmpeg"]["path"] if env_result["ffmpeg"]["path"] else "未找到"} - {"OK" if env_result["ffmpeg"]["ok"] else "需要修复"}')
        print(f'依赖包: {"全部安装" if env_result["dependencies"]["ok"] else "缺失: " + str(env_result["dependencies"]["missing"])}')
        print(f'网络连接: {"OK" if env_result["network"]["ok"] else "需要检查网络"}')
        print(f'写入权限: {"OK" if env_result["write_permission"]["ok"] else "需要检查权限"}')
        print(f'整体状态: {"就绪" if env_result["all_ok"] else "需要修复"}')
        
        import time
        start_time = time.time()
        stage_times = {}
        from PyQt5.QtCore import Qt, qInstallMessageHandler
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        def message_handler(msg_type, context, message):
            if "Unknown property z-index" not in message:
                print(f"{message}")
        qInstallMessageHandler(message_handler)
        requests.packages.urllib3.disable_warnings()
        app = QApplication(sys.argv)
        font = QFont("SimHei", 9)
        app.setFont(font)
        app.setStyle('Fusion')
        stage_times['app_init'] = time.time() - start_time
        splash = SplashScreen()
        splash.show()
        app.processEvents()
        stage_times['splash_show'] = time.time() - start_time
        splash.update_progress(10, "初始化配置...")
        config = ConfigLoader()
        app.processEvents()
        stage_times['config_init'] = time.time() - start_time
        splash.update_progress(30, "检查依赖库...")
        import threading
        def check_dependencies():
            try:
                from env_checker import check_environment
                env_result = check_environment()
            except Exception as e:
                print(f"检查环境时出错：{str(e)}")
        dependency_thread = threading.Thread(target=check_dependencies)
        dependency_thread.start()
        # 等待环境检测完成
        dependency_thread.join(timeout=30)
        app.processEvents()
        splash.update_progress(50, "初始化组件...")
        app.processEvents()
        
        # 检查工具状态
        tool_missing = False
        try:
            splash.update_progress(55, "检查工具文件...")
            app.processEvents()
            from tool_manager import get_tool_manager
            tool_manager = get_tool_manager()
            
            # 检查工具是否已安装
            tool_status = tool_manager.check_tools_installed()
            print(f"工具检查结果: {tool_status}")
            
            if not (tool_status['ffmpeg_exists'] and tool_status['bento4_exists']):
                tool_missing = True
                print("工具未完全安装")
            else:
                print("工具已安装")
            
            splash.update_progress(65, "工具检查完成")
            app.processEvents()
        except Exception as e:
            print(f"工具检查失败: {str(e)}")
            import traceback
            traceback.print_exc()
            splash.update_progress(65, "工具检查跳过")
            app.processEvents()
        
        import threading
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
                    max_threads=max_threads
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
        component_thread = threading.Thread(target=init_components)
        component_thread.daemon = True
        component_thread.start()
        import time
        start_time = time.time()
        max_wait_time = 10
        wait_start = time.time()
        while not components_ready.is_set() and time.time() - wait_start < max_wait_time:
            app.processEvents()
            time.sleep(0.01)
            progress = 65 + min(int((time.time() - wait_start) / max_wait_time * 35), 35)
            splash.update_progress(progress, "初始化组件...")
        app.processEvents()
        from PyQt5.QtCore import QTimer
        window = None
        def init_ui():
            global window
            window = BilibiliDownloader(
                config=config,
                task_manager=task_manager[0],
                download_manager=download_manager[0]
            )
            window.parser = parser[0]
            app.processEvents()
            splash.update_progress(100, "加载完成...")
            app.processEvents()
            splash.close_with_animation()
            window.showMaximized()
            window.raise_()
            window.activateWindow()
            app.processEvents()
            QTimer.singleShot(100, init_after_ui)
        QTimer.singleShot(100, init_ui)
        import threading
        def ensure_splash_closed():
            import time
            start_time = time.time()
            while splash.isVisible() and time.time() - start_time < 3:
                time.sleep(0.01)
            try:
                splash.hide()
            except Exception:
                pass
        thread = threading.Thread(target=ensure_splash_closed)
        thread.daemon = True
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
            
            # 检查工具是否缺失，如果缺失则弹窗提示
            if tool_missing:
                def show_tool_missing_dialog():
                    from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
                    from PyQt5.QtCore import Qt
                    
                    dialog = QDialog(window)
                    dialog.setWindowTitle("工具缺失提示")
                    dialog.setMinimumSize(450, 250)
                    
                    layout = QVBoxLayout(dialog)
                    
                    # 标题
                    title_label = QLabel("工具缺失提示")
                    title_label.setAlignment(Qt.AlignCenter)
                    title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #d4380d; margin: 15px 10px 5px 10px;")
                    layout.addWidget(title_label)
                    
                    # 提示文字
                    info_label = QLabel(
                        "检测到 FFmpeg 和 Bento4 工具未完整安装！\n\n"
                        "这些工具对于视频下载和处理非常重要。\n"
                        "是否现在安装这些工具？"
                    )
                    info_label.setAlignment(Qt.AlignCenter)
                    info_label.setWordWrap(True)
                    info_label.setStyleSheet("font-size: 14px; margin: 10px; color: #333;")
                    layout.addWidget(info_label)
                    
                    # 按钮
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
                    
                    # 显示对话框
                    result = dialog.exec_()
                    
                    # 如果用户选择安装
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
                thread = threading.Thread(target=run_init_tasks)
                thread.daemon = True
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
                            QTimer.singleShot(0, lambda: window.on_cookie_verified(False, "Cookie格式错误！支持：JSON对象列表、key1=value1;格式"))
                            return
                        print("开始验证Cookie...")
                        success, msg = parser[0].verify_cookie()
                        print(f"Cookie验证结果：{success}, {msg}")
                        print("准备调用on_cookie_verified方法...")
                        def call_on_cookie_verified():
                            try:
                                window.on_cookie_verified(success, msg)
                                print("on_cookie_verified方法调用成功")
                            except Exception as e:
                                print(f"调用on_cookie_verified方法失败：{str(e)}")
                                import traceback
                                traceback.print_exc()
                        QTimer.singleShot(0, call_on_cookie_verified)
                    except Exception as e:
                        print(f"Cookie处理异常：{str(e)}")
                        import traceback
                        traceback.print_exc()
                        def call_on_cookie_verified_error():
                            try:
                                window.on_cookie_verified(False, f"Cookie处理失败：{str(e)}")
                                print("on_cookie_verified方法调用成功（错误情况）")
                            except Exception as e2:
                                print(f"调用on_cookie_verified方法失败（错误情况）：{str(e2)}")
                                import traceback
                                traceback.print_exc()
                        QTimer.singleShot(0, call_on_cookie_verified_error)
                thread = threading.Thread(target=verify_in_thread)
                thread.daemon = True
                thread.start()
            window.signal_emitter.verify_cookie.connect(handle_cookie_verification)
            def handle_load_user_info():
                def load_in_thread():
                    try:
                        user_info = parser[0].get_user_info()
                        QTimer.singleShot(0, lambda: window.update_user_info(user_info))
                    except Exception as e:
                        print(f"加载用户信息异常：{str(e)}")
                        import traceback
                        traceback.print_exc()
                thread = threading.Thread(target=load_in_thread)
                thread.daemon = True
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
                thread = threading.Thread(target=check_in_thread)
                thread.daemon = True
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
                thread = threading.Thread(target=install_in_thread)
                thread.daemon = True
                thread.start()
            window.signal_emitter.install_hevc.connect(handle_install_hevc)
            def start_cookie_polling():
                def poll_cookie_status():
                    try:
                        if parser[0] and parser[0].cookies:
                            success, msg = parser[0].verify_cookie()
                            if not success:
                                QTimer.singleShot(0, lambda: window.update_user_info({"success": False}))
                    except Exception as e:
                        print(f"Cookie轮询异常：{str(e)}")
                    QTimer.singleShot(5 * 60 * 1000, poll_cookie_status)
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
                thread = threading.Thread(target=parse_in_thread)
                thread.daemon = True
                thread.start()
            print("=== 连接parse_start信号 ===")
            window.signal_emitter.parse_start.connect(handle_parse_media)
            print("=== parse_start信号连接成功 ===")
            window.signal_emitter.start_download.connect(download_manager[0].start_download)
            def handle_same_task_exists(download_params):
                print("检测到相同任务已存在，打开下载窗口")
                if hasattr(window, 'show_notification'):
                    window.show_notification("相同的下载任务已存在！", "info")
                from PyQt5.QtCore import QTimer
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
                window.status_label.setText("下载已取消")
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
                window.signal_emitter.show_debug_window.emit(error_msg, code_context, file_path)
            else:
                print(f"应用程序运行时错误：{error_msg}")
                input("按回车键退出...")
        
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