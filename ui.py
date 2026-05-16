
import os
import sys
import webbrowser
import shutil
import time
import json
import traceback
import logging
import ctypes
import re
import requests
import threading

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QPushButton, QScrollArea,
                             QComboBox, QLabel, QFileDialog, QProgressBar, QMessageBox, QGroupBox,
                             QCheckBox, QTextEdit, QDialog, QListWidget, QListWidgetItem,
                             QStackedWidget, QRadioButton, QButtonGroup, QSpacerItem, QSizePolicy, QMenu,
                             QApplication, QSpinBox, QTabWidget, QSystemTrayIcon, QCompleter, QToolBar, QAction, QStyle, QSplitter, QTreeView, QFileSystemModel, QFrame)
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QObject, QEvent, pyqtSlot, QPoint, QThread, QTimer, QEventLoop, QUrl, QCoreApplication, QMetaObject, Q_ARG, QDir
from PyQt5.QtGui import QFont, QPalette, QColor, QCursor, QPixmap, QPainter, QBrush, QIcon, QPainterPath, QImage
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if hasattr(sys, 'frozen') or sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

global_dpi_scale = 1.0
global_ui_shrink = 1.0

def init_dpi_scale():
    global global_dpi_scale, global_ui_shrink
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                dpi = screen.logicalDotsPerInch()
                global_dpi_scale = dpi / 96.0
                global_ui_shrink = max(0.35, 1.0 / (global_dpi_scale ** 1.2))
                return
        import ctypes
        hdc = ctypes.windll.user32.GetDC(0)
        if hdc:
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            ctypes.windll.user32.ReleaseDC(0, hdc)
            if dpi > 0:
                global_dpi_scale = dpi / 96.0
                global_ui_shrink = max(0.35, 1.0 / (global_dpi_scale ** 1.2))
                return
    except:
        pass
    global_dpi_scale = 1.0
    global_ui_shrink = 1.0

init_dpi_scale()

def scale(value):
    return int(value * global_dpi_scale * global_ui_shrink)

def scale_style(style_str):
    return re.sub(r'(\d+)px', lambda m: str(scale(int(m.group(1)))) + 'px', style_str)

def load_version_info():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        version_file = os.path.join(script_dir, 'version_info.json')
        with open(version_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"读取版本信息失败：{str(e)}")
        return {
            "version": "V1.8",
            "author": "寒烟似雪",
            "qq": "2273962061",
            "description": "B站视频解析下载工具"
        }

version_info = load_version_info()

_BASE_STYLE = """
    /* 全局样式 */
    QMainWindow { 
        background-color: #f8f9fa; 
        border: 1px solid #e9ecef;
    }
    QWidget { 
        font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif; 
        font-size: 13px; 
        color: #333333;
    }
    
    /* 输入控件 */
    QLineEdit, QTextEdit, QComboBox, QListWidget {
        padding: 10px 12px;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        background-color: white;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QListWidget:focus {
        border-color: #409eff;
    }
    
    /* 按钮 */
    QPushButton {
        padding: 10px 20px;
        border: none;
        border-radius: 8px;
        color: white;
        background-color: #409eff;
        font-weight: 500;
    }
    QPushButton:hover { 
        background-color: #66b1ff; 
    }
    QPushButton:pressed { 
        background-color: #3a8ee6; 
    }
    QPushButton:disabled { 
        background-color: #d1d5db; 
    }
    QPushButton#cancelBtn { background-color: #f56c6c; }
    QPushButton#cancelBtn:hover { background-color: #f78989; }
    QPushButton#hevcBtn { background-color: #fa8c16; }
    QPushButton#hevcBtn:hover { background-color: #fb9e3c; }
    QPushButton#selectAllBtn { background-color: #52c41a; }
    QPushButton#selectAllBtn:hover { background-color: #73d13d; }
    QPushButton#deselectAllBtn { background-color: #919191; }
    QPushButton#deselectAllBtn:hover { background-color: #a8a8a8; }
    QPushButton#applyCookieBtn { background-color: #9f7aea; }
    QPushButton#applyCookieBtn:hover { background-color: #b392f0; }
    QPushButton#bilibiliBtn { background-color: #00a1d6; }
    QPushButton#bilibiliBtn:hover { background-color: #19b5e0; }
    
    /* 分组框 */
    QGroupBox {
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 20px;
        margin-top: 16px;
        background-color: white;
    }
    QGroupBox::title { 
        font-size: 14px; 
        font-weight: 600; 
        color: #2563eb; 
        margin-left: 12px;
        padding: 0 8px;
    }
    
    /* 进度条 */
    QProgressBar { 
        min-height: 10px; 
        border-radius: 5px; 
        background-color: #e9ecef; 
    }
    QProgressBar::chunk { 
        border-radius: 5px; 
        background-color: #409eff; 
    }
    
    /* 对话框 */
    QDialog { 
        border-radius: 10px; 
        background-color: white;
    }
    QDialog QLabel { font-size: 14px; }
    
    /* 列表控件 */
    QListWidget { 
        border-radius: 8px; 
        background-color: white;
    }
    QListWidget::item { 
        padding: 10px 16px; 
        border-bottom: 1px solid #f0f2f5; 
        min-height: 48px;
    }
    QListWidget::item:hover { 
        background-color: #f8fafc; 
    }
    QListWidget::item:selected { 
        background-color: #e6f7ff; 
        color: #2f5496;
    }
    
    /* 卡片视图 */
    .card-view QListWidget::item { 
        min-width: 140px; 
        margin: 10px; 
        border: 1px solid #e9ecef; 
        border-radius: 8px; 
        min-height: 90px;
    }
    .card-view QListWidget::item:hover { 
        background-color: #f8fafc; 
    }
    .card-view QListWidget::item:selected { 
        border-color: #409eff; 
        background-color: #e6f7ff;
    }
"""

def get_base_style():
    return scale_style(_BASE_STYLE)


from PyQt5.QtWebEngineWidgets import QWebEngineView


class CaptchaHandler(QObject):
    def __init__(self, callback, dialog):
        super().__init__()
        self.callback = callback
        self.dialog = dialog
    
    @pyqtSlot(str, str, str)
    def onCaptchaSuccess(self, validate, seccode, challenge):
        if validate:
            self.callback(validate, seccode, challenge)
            self.dialog.accept()

def show_captcha_dialog(gt, challenge, callback, parent=None):
    try:
        
        global global_dpi_scale
        def scale(value):
            return int(value * global_dpi_scale * global_ui_shrink)
        
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("人机验证")
        dialog.setMinimumSize(scale(420), scale(380))
        dialog.setModal(True)
        
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        dialog.setAutoFillBackground(True)
        
        style_sheet = """
            QDialog {
                background-color: white;
                border: 2px solid #409eff;
                border-radius: %dpx;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
            }
            QPushButton {
                padding: %dpx %dpx;
                border-radius: %dpx;
                font-size: %dpx;
                font-weight: 500;
            }
            QPushButton#cancelBtn {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #d9d9d9;
            }
            QPushButton#cancelBtn:hover {
                background-color: #e6e6e6;
                border-color: #409eff;
            }
            QPushButton#cancelBtn:pressed {
            }
        """ % (scale(12), scale(10), scale(20), scale(8), scale(14))
        dialog.setStyleSheet(style_sheet)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        title_bar = QWidget()
        title_bar.setStyleSheet(f"background-color: #409eff; color: white; min-height: {scale(40)}px; border-top-left-radius: {scale(10)}px; border-top-right-radius: {scale(10)}px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), 0, scale(12), 0)
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("人机验证")
        title_label.setStyleSheet(f"font-size: {scale(15)}px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(f"background-color: transparent; border: none; color: white; font-size: {scale(18)}px; padding: 0; min-width: {scale(28)}px; min-height: {scale(28)}px; border-radius: {scale(14)}px;")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(lambda: (callback(None, None, None), dialog.reject()))
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(24), scale(24), scale(24), scale(24))
        content_layout.setSpacing(scale(20))
        
        info_label = QLabel("请完成以下验证")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet(f"font-size: {scale(18)}px; font-weight: 600; color: #333; letter-spacing: 0.5px;")
        content_layout.addWidget(info_label)
        
        web_view = QWebEngineView()
        web_view.setMinimumSize(scale(380), scale(260))
        web_view.setStyleSheet(f"border-radius: {scale(8)}px;")
        content_layout.addWidget(web_view)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(12))
        btn_layout.addStretch(1)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        cancel_btn.setMinimumWidth(scale(120))
        cancel_btn.setMinimumHeight(scale(36))
        cancel_btn.clicked.connect(lambda: (callback(None, None, None), dialog.reject()))
        btn_layout.addWidget(cancel_btn)
        
        content_layout.addLayout(btn_layout)
        main_layout.addWidget(content_widget, stretch=1)
        
        
        web_settings = web_view.page().settings()
        web_settings.setAttribute(web_settings.JavascriptEnabled, True)
        web_settings.setAttribute(web_settings.JavascriptCanOpenWindows, True)
        web_settings.setAttribute(web_settings.JavascriptCanAccessClipboard, True)
        web_settings.setAttribute(web_settings.LocalContentCanAccessRemoteUrls, True)
        web_settings.setAttribute(web_settings.LocalContentCanAccessFileUrls, True)
        web_settings.setAttribute(web_settings.PluginsEnabled, True)
        web_settings.setAttribute(web_settings.AutoLoadImages, True)
        
        
        channel = QWebChannel()
        handler = CaptchaHandler(callback, dialog)
        channel.registerObject('handler', handler)
        web_view.page().setWebChannel(channel)
        
        
        captcha_html = '''
        <html>
        <head>
            <meta charset="UTF-8">
            <title>极验验证码</title>
            <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
            <script src="https://static.geetest.com/static/js/gt.0.5.0.js"></script>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                #captcha {
                    width: 300px;
                    height: 200px;
                    margin: 0 auto;
                    background-color: #ffffff;
                    border: 1px solid #e0e0e0;
                    border-radius: 8px;
                    padding: 20px;
                    position: relative;
                }
                #status {
                    text-align: center;
                    margin-top: 20px;
                    color: #666666;
                    font-size: 14px;
                }
                #wait {
                    text-align: center;
                    padding: 40px;
                }
                .loading {
                    display: inline-block;
                }
                .loading-dot {
                    display: inline-block;
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background-color: #409eff;
                    margin: 0 5px;
                    animation: loading 1.5s infinite ease-in-out;
                }
                .loading-dot:nth-child(2) {
                    animation-delay: 0.2s;
                }
                .loading-dot:nth-child(3) {
                    animation-delay: 0.4s;
                }
                .loading-dot:nth-child(4) {
                    animation-delay: 0.6s;
                }
                @keyframes loading {
                    0%, 100% {
                        transform: scale(0.3);
                        opacity: 0.3;
                    }
                    50% {
                        transform: scale(1);
                        opacity: 1;
                    }
                }
                .error-message {
                    color: #f56c6c;
                    text-align: center;
                    margin-top: 10px;
                    font-size: 14px;
                }
            </style>
            <script>
                console.log('验证码页面加载');
                
                // 全局变量
                var captchaObj = null;
                var handler = null;
                
                // 初始化QWebChannel
                function initWebChannel() {
                    console.log('初始化QWebChannel');
                    if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                        console.log('QWebChannel可用');
                        new QWebChannel(qt.webChannelTransport, function(channel) {
                            console.log('QWebChannel连接成功');
                            handler = channel.objects.handler;
                            console.log('Handler设置成功');
                        });
                    } else {
                        console.log('QWebChannel不可用');
                        showError('无法建立通信通道');
                    }
                }
                
                // 显示错误信息
                function showError(message) {
                    var status = document.getElementById('status');
                    status.innerHTML = message;
                    status.className = 'error-message';
                }
                
                // 验证码回调函数
                function captchaHandler(captchaObj) {
                    console.log('验证码对象创建成功');
                    window.captchaObj = captchaObj;
                    
                    // 将验证码添加到页面
                    captchaObj.appendTo('#captcha');
                    console.log('验证码添加到页面');
                    
                    // 验证码准备就绪
                    captchaObj.onReady(function () {
                        console.log('验证码加载完成');
                        document.getElementById('wait').style.display = 'none';
                        document.getElementById('status').innerHTML = '验证码加载完成，请完成验证';
                    });
                    
                    // 验证成功
                    captchaObj.onSuccess(function () {
                        console.log('验证码验证成功');
                        var video_info = captchaObj.getValidate();
                        console.log('验证结果:', video_info);
                        
                        if (video_info) {
                            console.log('验证结果完整');
                            // 构造验证结果对象
                            var validateResult = {
                                validate: video_info.geetest_validate,
                                seccode: video_info.geetest_seccode,
                                challenge: video_info.geetest_challenge
                            };
                            
                            console.log('构造验证结果:', validateResult);
                            
                            if (handler) {
                                console.log('调用handler.onCaptchaSuccess');
                                handler.onCaptchaSuccess(video_info.geetest_validate, video_info.geetest_seccode, video_info.geetest_challenge);
                            } else {
                                console.error('handler不可用');
                                showError('验证成功，但无法提交结果');
                            }
                        } else {
                            console.error('验证结果为空');
                            showError('验证失败，结果为空');
                        }
                    });
                    
                    // 验证错误
                    captchaObj.onError(function (err) {
                        console.error('验证码错误:', err);
                        showError('验证码加载失败，请刷新重试');
                    });
                    
                    // 验证码关闭
                    captchaObj.onClose(function () {
                        console.log('验证码关闭');
                    });
                }
                
                // 初始化验证码
                function initGeetestCaptcha() {
                    console.log('初始化极验验证码');
                    
                    if (typeof initGeetest === 'undefined') {
                        console.error('initGeetest未定义');
                        showError('验证码脚本加载失败');
                        return;
                    }
                    
                    console.log('调用initGeetest');
                    initGeetest({
                        // 必须参数
                        gt: '__GT__',
                        challenge: '__CHALLENGE__',
                        offline: false,
                        new_captcha: true,
                        
                        // 可选参数
                        product: 'popup',
                        width: '300px',
                        https: true
                    }, captchaHandler);
                }
                
                // 页面加载完成后初始化
                window.onload = function() {
                    console.log('页面加载完成');
                    
                    // 先初始化WebChannel
                    initWebChannel();
                    
                    // 然后初始化验证码
                    setTimeout(function() {
                        initGeetestCaptcha();
                    }, 100);
                };
            </script>
        </head>
        <body>
            <div id="captcha">
                <div id="wait">
                    <div class="loading">
                        <div class="loading-dot"></div>
                        <div class="loading-dot"></div>
                        <div class="loading-dot"></div>
                        <div class="loading-dot"></div>
                    </div>
                </div>
            </div>
            <div id="status">验证码加载中...</div>
        </body>
        </html>
        '''
        
        
        captcha_html = captcha_html.replace('__GT__', gt).replace('__CHALLENGE__', challenge)
        
        web_view.setHtml(captcha_html)
        
        
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton and event.y() < scale(36):
                dialog.dragging = True
                dialog.start_pos = event.globalPos() - dialog.frameGeometry().topLeft()
                event.accept()
        
        def mouseMoveEvent(event):
            if hasattr(dialog, 'dragging') and dialog.dragging and event.buttons() == Qt.LeftButton:
                dialog.move(event.globalPos() - dialog.start_pos)
                event.accept()
        
        def mouseReleaseEvent(event):
            if hasattr(dialog, 'dragging'):
                dialog.dragging = False
            event.accept()
        
        
        dialog.mousePressEvent = mousePressEvent
        dialog.mouseMoveEvent = mouseMoveEvent
        dialog.mouseReleaseEvent = mouseReleaseEvent
        
        
        dialog.exec_()
    except Exception as e:
        print(f"验证码对话框错误：{str(e)}")
        print(traceback.format_exc())
        callback(None, None, None)

class ExpandedCard(QDialog):
    def __init__(self, floating_ball, parent=None):
        super().__init__(parent)
        self.floating_ball = floating_ball
        
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAutoFillBackground(True)
        
        self.setStyleSheet(scale_style("""
            QDialog {
                background-color: white;
                border: 2px solid #409eff;
                border-radius: 10px;
            }
        """))
        
        # 使用全局DPI缩放因子
        global global_dpi_scale
        
        # 自适应屏幕尺寸
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # 根据屏幕尺寸和DPI设置合理的大小
        min_width = max(scale(250), int(screen_width * 0.2))
        min_height = max(scale(200), int(screen_height * 0.2))
        max_width = min(scale(800), int(screen_width * 0.6))
        max_height = min(scale(1000), int(screen_height * 0.8))
        
        self.setMinimumSize(min_width, min_height)
        self.setMaximumSize(max_width, max_height)
        
        # 响应窗口大小变化
        self.resizeEvent = self.on_resize
        
        
        self.create_ui()
        
    def create_ui(self):
        
        # 计算基于DPI的尺寸
        global global_dpi_scale
        def scale(value):
            return int(value * global_dpi_scale * global_ui_shrink)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(scale(8), scale(8), scale(8), scale(8))
        main_layout.setSpacing(scale(10))
        
        self.initial_card = QWidget()
        initial_layout = QVBoxLayout(self.initial_card)
        initial_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        initial_layout.setSpacing(scale(10))
        
        logo_layout = QVBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)
        logo_label = QLabel()
        # 处理logo路径
        import sys
        if hasattr(sys, '_MEIPASS'):
            # 在EXE模式下
            logo_path = os.path.join(sys._MEIPASS, "logo.png")
        else:
            # 在开发模式下
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_size = scale(80)
            pixmap = pixmap.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            logo_label.setPixmap(pixmap)
        else:
            logo_size = scale(80)
            logo_label.setStyleSheet(f"background-color: #409eff; color: white; border-radius: {scale(40)}px; font-size: {scale(40)}px; font-weight: bold;")
            logo_label.setText("B")
        logo_label.setFixedSize(scale(80), scale(80))
        logo_label.setAlignment(Qt.AlignCenter)
        logo_layout.addWidget(logo_label)
        initial_layout.addLayout(logo_layout)
        
        # 自适应URL输入框
        url_layout = QHBoxLayout()
        url_layout.setContentsMargins(scale(10), 0, scale(10), 0)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("输入B站视频链接...")
        self.url_edit.setStyleSheet(f"padding: {scale(12)}px; border: {scale(1)}px solid #dee2e6; border-radius: {scale(8)}px; font-size: {scale(12)}px; background-color: #f8fafc;")
        self.url_edit.setMinimumHeight(scale(36))
        url_layout.addWidget(self.url_edit, stretch=1)
        initial_layout.addLayout(url_layout)
        
        # 自适应按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(scale(10), 0, scale(10), 0)
        btn_layout.setSpacing(scale(8))
        
        parse_btn = QPushButton("解析")
        parse_btn.setStyleSheet(f"background-color: #409eff; color: white; padding: {scale(12)}px; border-radius: {scale(8)}px; font-size: {scale(12)}px; font-weight: 600;")
        parse_btn.setMinimumHeight(scale(36))
        parse_btn.setMinimumWidth(scale(60))
        parse_btn.clicked.connect(self.on_parse_clicked)
        
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(f"background-color: #f56c6c; color: white; padding: {scale(12)}px; border-radius: {scale(8)}px; font-size: {scale(12)}px; font-weight: 600;")
        close_btn.setMinimumHeight(scale(36))
        close_btn.setMinimumWidth(scale(60))
        close_btn.clicked.connect(self.on_close_clicked)
        
        btn_layout.addWidget(parse_btn, stretch=1)
        btn_layout.addWidget(close_btn, stretch=1)
        initial_layout.addLayout(btn_layout)
        
        main_layout.addWidget(self.initial_card)
        
        self.video_info_widget = QWidget()
        video_info_layout = QVBoxLayout(self.video_info_widget)
        video_info_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        video_info_layout.setSpacing(scale(10))
        
        # 分辨率选择
        resolution_layout = QHBoxLayout()
        resolution_layout.setSpacing(scale(5))
        resolution_layout.setContentsMargins(scale(5), 0, scale(5), 0)
        resolution_label = QLabel("分辨率：")
        resolution_label.setStyleSheet(f"font-size: {scale(12)}px; font-weight: 500; color: #333;")
        resolution_label.setMinimumHeight(scale(28))
        resolution_label.setMinimumWidth(scale(60))
        self.resolution_combo = QComboBox()
        self.resolution_combo.setStyleSheet(f"padding: {scale(6)}px; border: {scale(1)}px solid #dee2e6; border-radius: {scale(4)}px; font-size: {scale(12)}px;")
        self.resolution_combo.setMinimumHeight(scale(28))
        # 默认只显示无需登录的分辨率，登录后会更新
        self.resolution_combo.addItems(["480P", "360P"])
        self.resolution_combo.setCurrentIndex(0)  # 默认选择最高质量
        resolution_layout.addWidget(resolution_label)
        resolution_layout.addWidget(self.resolution_combo, stretch=1)
        video_info_layout.addLayout(resolution_layout)
        
        # 保存路径
        path_layout = QHBoxLayout()
        path_layout.setSpacing(scale(5))
        path_layout.setContentsMargins(scale(5), 0, scale(5), 0)
        path_label = QLabel("保存路径：")
        path_label.setStyleSheet(f"font-size: {scale(12)}px; font-weight: 500; color: #333;")
        path_label.setMinimumHeight(scale(28))
        path_label.setMinimumWidth(scale(60))
        self.path_edit = QLineEdit()
        self.path_edit.setStyleSheet(f"padding: {scale(6)}px; border: {scale(1)}px solid #dee2e6; border-radius: {scale(4)}px; font-size: {scale(10)}px;")
        self.path_edit.setMinimumHeight(scale(28))
        default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        self.path_edit.setText(default_path)
        path_btn = QPushButton("选择")
        path_btn.setStyleSheet(f"background-color: #6c757d; color: white; padding: {scale(6)}px {scale(8)}px; border-radius: {scale(4)}px; font-size: {scale(10)}px; font-weight: 500;")
        path_btn.setMinimumHeight(scale(28))
        path_btn.setMinimumWidth(scale(50))
        path_btn.clicked.connect(self.on_select_path_clicked)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(path_btn)
        video_info_layout.addLayout(path_layout)
        
        # 视频列表
        list_layout = QHBoxLayout()
        list_layout.setContentsMargins(scale(5), 0, scale(5), 0)
        self.video_list = QListWidget()
        self.video_list.setStyleSheet(f"border: {scale(1)}px solid #dee2e6; border-radius: {scale(6)}px; font-size: {scale(10)}px;")
        self.video_list.setUniformItemSizes(True)
        self.video_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.video_list.setMinimumHeight(scale(80))
        list_layout.addWidget(self.video_list, stretch=1)
        video_info_layout.addLayout(list_layout)
        
        # 下载类型选择
        download_type_layout = QHBoxLayout()
        download_type_layout.setSpacing(scale(8))
        download_type_layout.setContentsMargins(scale(5), 0, scale(5), 0)
        download_type_label = QLabel("下载类型：")
        download_type_label.setStyleSheet(f"font-size: {scale(12)}px; font-weight: 500; color: #333;")
        download_type_label.setMinimumHeight(scale(28))
        download_type_label.setMinimumWidth(scale(60))
        
        self.download_video_checkbox = QCheckBox("视频")
        self.download_video_checkbox.setStyleSheet(f"font-size: {scale(10)}px;")
        self.download_video_checkbox.setChecked(True)
        
        self.download_danmaku_checkbox = QCheckBox("弹幕")
        self.download_danmaku_checkbox.setStyleSheet(f"font-size: {scale(10)}px;")
        self.download_danmaku_checkbox.setChecked(True)
        
        download_type_layout.addWidget(download_type_label)
        download_type_layout.addWidget(self.download_video_checkbox)
        download_type_layout.addWidget(self.download_danmaku_checkbox)
        download_type_layout.addStretch(1)
        video_info_layout.addLayout(download_type_layout)
        
        # 操作按钮
        action_layout = QHBoxLayout()
        action_layout.setSpacing(scale(5))
        action_layout.setContentsMargins(scale(5), 0, scale(5), 0)
        
        back_btn = QPushButton("返回")
        back_btn.setStyleSheet(f"background-color: #6c757d; color: white; padding: {scale(6)}px {scale(8)}px; border-radius: {scale(4)}px; font-size: {scale(10)}px; font-weight: 500;")
        back_btn.setMinimumHeight(scale(28))
        back_btn.setMinimumWidth(scale(50))
        back_btn.clicked.connect(self.on_back_clicked)
        
        select_all_btn = QPushButton("全选")
        select_all_btn.setStyleSheet(f"background-color: #52c41a; color: white; padding: {scale(6)}px {scale(8)}px; border-radius: {scale(4)}px; font-size: {scale(10)}px; font-weight: 500;")
        select_all_btn.setMinimumHeight(scale(28))
        select_all_btn.setMinimumWidth(scale(50))
        select_all_btn.clicked.connect(self.on_select_all_clicked)
        
        download_btn = QPushButton("下载")
        download_btn.setStyleSheet(f"background-color: #1890ff; color: white; padding: {scale(6)}px {scale(8)}px; border-radius: {scale(4)}px; font-size: {scale(10)}px; font-weight: 500;")
        download_btn.setMinimumHeight(scale(28))
        download_btn.setMinimumWidth(scale(50))
        download_btn.clicked.connect(self.on_download_clicked)
        
        action_layout.addWidget(back_btn)
        action_layout.addWidget(select_all_btn)
        action_layout.addWidget(download_btn)
        action_layout.addStretch(1)
        video_info_layout.addLayout(action_layout)
        
        self.video_info_widget.hide()
        main_layout.addWidget(self.video_info_widget)
        
        self.download_widget = QWidget()
        download_layout = QVBoxLayout(self.download_widget)
        download_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        download_layout.setSpacing(scale(15))
        
        download_label = QLabel("下载进度")
        download_label.setStyleSheet(f"font-size: {scale(14)}px; font-weight: 500; color: #333;")
        download_label.setMinimumHeight(scale(36))
        download_layout.addWidget(download_label)
        
        self.download_scroll = QScrollArea()
        self.download_scroll.setWidgetResizable(True)
        self.download_scroll.setStyleSheet(f"border: {scale(1)}px solid #dee2e6; border-radius: {scale(8)}px;")
        
        self.download_container = QWidget()
        self.download_container_layout = QVBoxLayout(self.download_container)
        self.download_container_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        self.download_container_layout.setSpacing(scale(10))
        
        self.download_scroll.setWidget(self.download_container)
        self.download_scroll.setMinimumHeight(scale(150))
        download_layout.addWidget(self.download_scroll, stretch=1)
        
        download_action_layout = QHBoxLayout()
        download_action_layout.setSpacing(scale(15))
        
        download_back_btn = QPushButton("返回")
        download_back_btn.setStyleSheet(f"background-color: #6c757d; color: white; padding: {scale(10)}px {scale(20)}px; border-radius: {scale(6)}px; font-size: {scale(14)}px; font-weight: 500;")
        download_back_btn.setMinimumHeight(scale(36))
        download_back_btn.clicked.connect(self.on_download_back_clicked)
        
        download_action_layout.addWidget(download_back_btn)
        download_action_layout.addStretch(1)
        download_layout.addLayout(download_action_layout)
        
        self.download_tasks = {}
        self.download_widget.hide()
        main_layout.addWidget(self.download_widget)
        
    def on_parse_clicked(self):
        print("解析按钮被点击了！")
        url = self.url_edit.text().strip()
        print(f"URL: {url}")
        if url:
            self.floating_ball.current_video_info = None
            self.floating_ball.url_edit = self.url_edit
            self.floating_ball.resolution_combo = self.resolution_combo
            self.floating_ball.path_edit = self.path_edit
            self.floating_ball.video_list = self.video_list
            self.floating_ball.video_info_widget = self.video_info_widget
            self.floating_ball.download_widget = self.download_widget
            self.floating_ball.download_container_layout = self.download_container_layout
            self.floating_ball.download_tasks = self.download_tasks
            self.floating_ball.download_video_checkbox = self.download_video_checkbox
            self.floating_ball.download_danmaku_checkbox = self.download_danmaku_checkbox
            self.floating_ball.on_parse()
            
    def on_close_clicked(self):
        print("关闭按钮被点击了！")
        self.floating_ball.collapse()
        
    def on_select_path_clicked(self):
        self.floating_ball.path_edit = self.path_edit
        self.floating_ball.select_save_path()
        
    def on_select_all_clicked(self):
        self.video_list.selectAll()
        
    def on_download_clicked(self):
        
        self.floating_ball.url_edit = self.url_edit
        self.floating_ball.current_video_info = self.floating_ball.current_video_info
        self.floating_ball.video_list = self.video_list
        self.floating_ball.resolution_combo = self.resolution_combo
        self.floating_ball.path_edit = self.path_edit
        self.floating_ball.download_widget = self.download_widget
        self.floating_ball.download_container_layout = self.download_container_layout
        self.floating_ball.download_tasks = self.download_tasks
        self.floating_ball.video_info_widget = self.video_info_widget
        self.floating_ball.download_video_checkbox = self.download_video_checkbox
        self.floating_ball.download_danmaku_checkbox = self.download_danmaku_checkbox
        
        self.floating_ball.on_download()
        
    def on_back_clicked(self):
        print("返回按钮被点击了！")
        
        self.initial_card.show()
        self.video_info_widget.hide()
        
        self.url_edit.clear()
        
        # 调整窗口大小以适应初始卡片
        self.adjustSize()
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.geometry()
            min_width = int(screen_geometry.width() * 0.3)
            min_height = int(screen_geometry.height() * 0.3)
            if self.width() < min_width or self.height() < min_height:
                self.resize(max(self.width(), min_width), max(self.height(), min_height))
        
    def on_download_back_clicked(self):
        print("下载返回按钮被点击了！")
        
        self.video_info_widget.show()
        self.download_widget.hide()
        
        self.adjustSize()
    
    def on_resize(self, event):
        # 确保内容区域自适应窗口大小
        if self.initial_card and self.initial_card.isVisible():
            self.initial_card.resize(self.width(), self.height())
            self._adjust_initial_card_layout()
        elif self.video_info_widget and self.video_info_widget.isVisible():
            self.video_info_widget.resize(self.width(), self.height())
            self._adjust_video_info_layout()
        elif self.download_widget and self.download_widget.isVisible():
            self.download_widget.resize(self.width(), self.height())
            self._adjust_download_layout()
        
        # 调整字体大小以适应窗口
        self.adjust_font_size()
    
    def _adjust_initial_card_layout(self):
        if not hasattr(self, 'initial_card'):
            return
        
        # 调整URL输入框大小
        if hasattr(self, 'url_edit'):
            # 根据窗口宽度调整输入框大小
            new_width = max(200, self.width() - 100)
            self.url_edit.setFixedWidth(new_width)
        
        # 调整按钮大小和位置
        if hasattr(self, 'parse_btn') and hasattr(self, 'close_btn'):
            button_width = max(60, int(self.width() * 0.2))
            self.parse_btn.setFixedWidth(button_width)
            self.close_btn.setFixedWidth(button_width)
    
    def _adjust_video_info_layout(self):
        if not hasattr(self, 'video_info_widget'):
            return
        
        # 调整分辨率下拉框大小
        if hasattr(self, 'resolution_combo'):
            new_width = max(150, self.width() - 400)
            self.resolution_combo.setFixedWidth(new_width)
        
        # 调整路径输入框大小
        if hasattr(self, 'path_edit'):
            new_width = max(200, self.width() - 300)
            self.path_edit.setFixedWidth(new_width)
    
    def _adjust_download_layout(self):
        if not hasattr(self, 'download_widget'):
            return
        
        # 调整进度条大小
        if hasattr(self, 'progress_bar'):
            new_width = max(200, self.width() - 100)
            self.progress_bar.setFixedWidth(new_width)
    
    def adjust_font_size(self):
        window_width = self.width()
        window_height = self.height()
        
        # 综合考虑窗口宽度和高度
        min_dimension = min(window_width, window_height)
        
        # 根据窗口大小调整字体大小
        if min_dimension < 300:
            font_size = 8
        elif min_dimension < 350:
            font_size = 9
        elif min_dimension < 400:
            font_size = 10
        elif min_dimension < 450:
            font_size = 11
        elif min_dimension < 500:
            font_size = 12
        elif min_dimension < 600:
            font_size = 13
        elif min_dimension < 700:
            font_size = 14
        elif min_dimension < 800:
            font_size = 15
        else:
            font_size = 16
        
        # 调整所有子控件的字体大小
        self._adjust_widget_font(self, font_size)
    
    def _adjust_widget_font(self, widget, font_size):
        
        # 调整当前控件的字体
        if hasattr(widget, 'setFont'):
            font = widget.font()
            font.setPointSize(font_size)
            widget.setFont(font)
        
        # 递归调整子控件
        if isinstance(widget, QWidget):
            for child in widget.children():
                if isinstance(child, QWidget):
                    self._adjust_widget_font(child, font_size)
        
        # 处理布局中的控件
        if hasattr(widget, 'layout') and widget.layout():
            layout = widget.layout()
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget():
                    self._adjust_widget_font(item.widget(), font_size)
                elif item and item.layout():
                    # 递归处理嵌套布局
                    for j in range(item.layout().count()):
                        sub_item = item.layout().itemAt(j)
                        if sub_item and sub_item.widget():
                            self._adjust_widget_font(sub_item.widget(), font_size)

class FloatingBall(QWidget):
    def __init__(self, parent=None):
        super().__init__(None)  
        self.parent = parent
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAutoFillBackground(True)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # 计算基于DPI的尺寸
        global global_dpi_scale
        self.base_size = int(70 * global_dpi_scale * global_ui_shrink)
        self.min_size = int(50 * global_dpi_scale * global_ui_shrink)
        self.max_size = int(100 * global_dpi_scale * global_ui_shrink)
        
        self.setFixedSize(self.base_size, self.base_size)
        
        # 计算初始位置
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        initial_x = screen_width - self.width() - scale(20)
        initial_y = screen_height - self.height() - scale(100)
        self.move(initial_x, initial_y)
        
        self.dragging = False
        self.last_pos = None
        
        self.expanded = False
        self.expanded_widget = None
        
        self.current_video_info = None
        
        self.last_progress = -1
        self.last_status = ""
        
        self.opacity = 0.8  
        self.size = self.base_size  
        self.min_opacity = 0.3  
        self.signal_connected = False
    
    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            alpha = int(255 * self.opacity)
            brush = QBrush(QColor(64, 158, 255, alpha))
            painter.setBrush(brush)
            painter.drawEllipse(0, 0, self.width() - 1, self.height() - 1)
            import sys
            if hasattr(sys, '_MEIPASS'):
                logo_path = os.path.join(sys._MEIPASS, "logo.png")
            else:
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                logo_size = int(self.width() * 0.6)
                scaled_pixmap = pixmap.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                x = (self.width() - scaled_pixmap.width()) // 2
                y = (self.height() - scaled_pixmap.height()) // 2
                painter.drawPixmap(x, y, scaled_pixmap)
            else:
                painter.setPen(QColor(255, 255, 255))
                font_size = int(self.width() * 0.3)
                ball_font = QFont("Microsoft YaHei", font_size, QFont.Bold)
                painter.setFont(ball_font)
                painter.drawText(self.rect(), Qt.AlignCenter, "B")
            painter.end()
        except Exception:
            try:
                painter = QPainter(self)
                painter.end()
            except Exception:
                pass
    
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                self.dragging = False
                self.last_pos = event.globalPos()
            elif event.button() == Qt.RightButton:
                self.show_context_menu(event.globalPos())
            event.accept()
        except Exception:
            event.accept()
    
    def mouseMoveEvent(self, event):
        try:
            if self.last_pos:
                current_pos = event.globalPos()
                delta = current_pos - self.last_pos
                if delta.manhattanLength() > scale(5):
                    self.dragging = True
                    new_x = self.x() + delta.x()
                    new_y = self.y() + delta.y()
                    screen = QApplication.primaryScreen()
                    if screen:
                        screen_geometry = screen.geometry()
                        if new_x < 0:
                            new_x = 0
                        if new_x + self.width() > screen_geometry.width():
                            new_x = screen_geometry.width() - self.width()
                        if new_y < 0:
                            new_y = 0
                        if new_y + self.height() > screen_geometry.height():
                            new_y = screen_geometry.height() - self.height()
                    self.move(new_x, new_y)
                    if self.expanded_widget and self.expanded:
                        widget_pos = self.expanded_widget.pos()
                        widget_delta_x = new_x - self.x()
                        widget_delta_y = new_y - self.y()
                        self.expanded_widget.move(widget_pos.x() + widget_delta_x, widget_pos.y() + widget_delta_y)
                    self.last_pos = current_pos
        except Exception:
            pass
    
    def mouseReleaseEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                if not self.dragging:
                    self.toggle_expanded()
                self.dragging = False
                self.last_pos = None
            event.accept()
        except Exception:
            event.accept()
    
    def toggle_expanded(self):
        print("=== toggle_expanded被调用 ===")
        print(f"当前expanded状态: {self.expanded}")
        if self.expanded:
            print("调用collapse()")
            self.collapse()
        else:
            print("调用expand()")
            self.expand()
    
    def expand(self):
        try:
            if self.expanded_widget:
                
                try:
                    
                    _ = self.expanded_widget.isVisible()
                    
                    self.expanded = True
                    print("=== 显示已存在的窗口 ===")
                    
                    
                    self.url_edit = self.expanded_widget.url_edit
                    self.resolution_combo = self.expanded_widget.resolution_combo
                    self.path_edit = self.expanded_widget.path_edit
                    self.video_list = self.expanded_widget.video_list
                    self.video_info_widget = self.expanded_widget.video_info_widget
                    self.download_widget = self.expanded_widget.download_widget
                    self.download_container_layout = self.expanded_widget.download_container_layout
                    self.download_tasks = self.expanded_widget.download_tasks
                    self.download_video_checkbox = self.expanded_widget.download_video_checkbox
                    self.download_danmaku_checkbox = self.expanded_widget.download_danmaku_checkbox
                    
                    while self.download_container_layout.count() > 0:
                        item = self.download_container_layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                    
                    
                    if hasattr(self, 'pending_global_progress'):
                        for task_id, progress_info in self.pending_global_progress.items():
                            self.update_download_progress(progress_info['progress'], progress_info['status'])
                        del self.pending_global_progress
                    
                    
                    if hasattr(self, 'pending_progress'):
                        for task_key, progress_info in self.pending_progress.items():
                            self.update_episode_progress(
                                progress_info['task_id'],
                                progress_info['ep_index'],
                                progress_info['progress'],
                                progress_info['status']
                            )
                        del self.pending_progress
                    
                    self.expanded_widget.show()
                    print("窗口显示成功")
                    self.expanded_widget.raise_()
                    print("窗口置顶成功")
                    self.expanded_widget.activateWindow()
                    print("窗口激活成功")
                    
                    self.expanded_widget.setFocus(Qt.ActiveWindowFocusReason)
                    print("窗口获得焦点成功")
                    print("=== 已存在窗口显示完成 ===")
                    return
                except Exception as e:
                    print(f"expanded_widget无效，重新创建: {str(e)}")
                    
                    self.expanded_widget = None
            
            self.expanded = True
            print("=== 开始创建展开窗口 ===")
            
            
            
            
            self.expanded_widget = ExpandedCard(self)
            print("ExpandedCard创建成功")
            
            
            ball_pos = self.mapToGlobal(self.rect().topRight())
            screen = QApplication.primaryScreen()
            screen_geometry = screen.geometry()
            screen_width = screen_geometry.width()
            screen_height = screen_geometry.height()
            
            # 计算窗口大小
            window_width = min(int(screen_width * 0.5), 550)
            window_height = min(int(screen_height * 0.7), 750)
            
            # 计算窗口位置
            x = ball_pos.x() + 10
            y = ball_pos.y()
            
            # 确保窗口不会超出屏幕
            if x + window_width > screen_width:
                x = ball_pos.x() - window_width - 10
            if y + window_height > screen_height:
                y = screen_height - window_height
            if x < 0:
                x = 10
            if y < 0:
                y = 10
            
            self.expanded_widget.move(x, y)
            
            
            self.url_edit = self.expanded_widget.url_edit
            self.resolution_combo = self.expanded_widget.resolution_combo
            self.path_edit = self.expanded_widget.path_edit
            self.video_list = self.expanded_widget.video_list
            self.video_info_widget = self.expanded_widget.video_info_widget
            self.download_widget = self.expanded_widget.download_widget
            self.download_container_layout = self.expanded_widget.download_container_layout
            self.download_tasks = self.expanded_widget.download_tasks
            self.download_video_checkbox = self.expanded_widget.download_video_checkbox
            self.download_danmaku_checkbox = self.expanded_widget.download_danmaku_checkbox
            
            while self.download_container_layout.count() > 0:
                item = self.download_container_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            
            if hasattr(self, 'pending_global_progress'):
                for task_id, progress_info in self.pending_global_progress.items():
                    self.update_download_progress(progress_info['progress'], progress_info['status'])
                del self.pending_global_progress
            
            
            if hasattr(self, 'pending_progress'):
                for task_key, progress_info in self.pending_progress.items():
                    self.update_episode_progress(
                        progress_info['task_id'],
                        progress_info['ep_index'],
                        progress_info['progress'],
                        progress_info['status']
                    )
                del self.pending_progress
            
            print("=== 开始显示窗口 ===")
            
            self.expanded_widget.show()
            print("窗口显示成功")
            self.expanded_widget.raise_()
            print("窗口置顶成功")
            self.expanded_widget.activateWindow()
            print("窗口激活成功")
            print("=== 窗口显示完成 ===")
        except Exception as e:
            
            print(f"展开悬浮球时出错：{str(e)}")
            
            self.expanded = False
            self.expanded_widget = None
            
            
            traceback.print_exc()
    
    def collapse(self):
        print("关闭按钮被点击了！")
        if self.expanded_widget:
            print("expanded_widget存在，开始隐藏")
            
            try:
                self.expanded_widget.hide()
                print("expanded_widget已隐藏")
            except Exception as e:
                print(f"隐藏时出错: {str(e)}")
        else:
            print("expanded_widget不存在")
        self.expanded = False
        print("收起完成")
    
    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        settings_action = menu.addAction("设置")
        settings_action.triggered.connect(self.show_settings_dialog)
        
        menu.addSeparator()
        close_action = menu.addAction("关闭悬浮球")
        close_action.triggered.connect(self.hide)
        menu.exec_(pos)
    
    def show_settings_dialog(self):
        
        # 计算基于DPI的尺寸
        global global_dpi_scale
        def scale(value):
            return int(value * global_dpi_scale * global_ui_shrink)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("悬浮球设置")
        dialog.setMinimumSize(scale(300), scale(200))
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        layout.setSpacing(scale(15))
        
        opacity_layout = QVBoxLayout()
        opacity_label = QLabel(f"透明度: {int(self.opacity * 100)}%")
        opacity_label.setStyleSheet(f"font-size: {scale(14)}px;")
        opacity_slider = QSlider(Qt.Horizontal)
        opacity_slider.setMinimum(int(self.min_opacity * 100))
        opacity_slider.setMaximum(100)
        opacity_slider.setValue(int(self.opacity * 100))
        opacity_slider.setMinimumHeight(scale(20))
        
        def update_opacity(value):
            opacity = value / 100.0
            self.set_opacity(opacity)
            opacity_label.setText(f"透明度: {value}%")
        
        opacity_slider.valueChanged.connect(update_opacity)
        
        opacity_layout.addWidget(opacity_label)
        opacity_layout.addWidget(opacity_slider)
        
        size_layout = QVBoxLayout()
        size_label = QLabel(f"大小: {self.size}px")
        size_label.setStyleSheet(f"font-size: {scale(14)}px;")
        size_slider = QSlider(Qt.Horizontal)
        size_slider.setMinimum(self.min_size)
        size_slider.setMaximum(self.max_size)
        size_slider.setValue(self.size)
        size_slider.setMinimumHeight(scale(20))
        
        def update_size(value):
            self.set_size(value)
            size_label.setText(f"大小: {value}px")
        
        size_slider.valueChanged.connect(update_size)
        
        size_layout.addWidget(size_label)
        size_layout.addWidget(size_slider)
        
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(f"padding: {scale(8)}px {scale(16)}px; font-size: {scale(14)}px;")
        close_btn.setMinimumHeight(scale(32))
        close_btn.clicked.connect(dialog.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(opacity_layout)
        layout.addLayout(size_layout)
        layout.addLayout(btn_layout)
        
        dialog.exec_()
    
    def set_opacity(self, opacity):
        
        if opacity < self.min_opacity:
            opacity = self.min_opacity
        self.opacity = opacity
        self.update()  
    
    def set_size(self, size):
        
        if size < self.min_size:
            size = self.min_size
        elif size > self.max_size:
            size = self.max_size
        
        
        old_center = self.mapToGlobal(self.rect().center())
        self.size = size
        self.setFixedSize(size, size)
        
        new_rect = self.rect()
        new_pos = old_center - new_rect.center()
        self.move(new_pos)
        self.update()  
    
    def on_parse(self):
        print("解析按钮被点击了！")
        print(f"self.parent: {self.parent}")
        
        if not self.signal_connected and self.parent and hasattr(self.parent, 'signal_emitter'):
            if hasattr(self.parent.signal_emitter, 'parse_finished'):
                
                try:
                    self.parent.signal_emitter.parse_finished.disconnect(self.on_parse_finished)
                except:
                    pass
                
                self.parent.signal_emitter.parse_finished.connect(self.on_parse_finished)
                self.signal_connected = True
                print("=== parse_finished信号连接成功 ===")
        
        url = self.url_edit.text().strip()
        print(f"输入的URL: {url}")
        if url:
            if self.parent and hasattr(self.parent, 'signal_emitter'):
                print("parent和signal_emitter存在")
                print(f"准备发送信号，signal_emitter对象: {self.parent.signal_emitter}")
                self.parent.signal_emitter.parse_start.emit(url, False)
                print("发送了解析信号")
            else:
                print("parent或signal_emitter不存在")
        else:
            print("URL为空")
    
    def on_parse_finished(self, video_info):
        try:
            self._on_parse_finished_impl(video_info)
        except Exception:
            pass

    def _on_parse_finished_impl(self, video_info):
        if video_info.get('success'):
            self.current_video_info = video_info
            
            if self.expanded_widget:
                self.url_edit = self.expanded_widget.url_edit
                self.resolution_combo = self.expanded_widget.resolution_combo
                self.path_edit = self.expanded_widget.path_edit
                self.video_list = self.expanded_widget.video_list
                self.video_info_widget = self.expanded_widget.video_info_widget
                self.download_widget = self.expanded_widget.download_widget
                self.download_container_layout = self.expanded_widget.download_container_layout
                self.download_tasks = self.expanded_widget.download_tasks
                
                self.expanded_widget.initial_card.hide()
                print("初始卡片已隐藏")
                
                self.video_info_widget.show()
                print("video_info_widget已显示")
                
                self.expanded_widget.adjustSize()
                print("窗口大小已调整")
                
                self.video_list.clear()
                print("视频列表已清空")
            
            
            if self.expanded_widget:
                if 'episodes' in video_info:
                    for episode in video_info['episodes']:
                        if 'title' in episode:
                            title = episode['title']
                        elif 'ep_title' in episode:
                            title = episode['ep_title']
                        else:
                            title = f"第{episode.get('page', 0)}集"
                        
                        duration = episode.get('duration', '')
                        item_text = f"{title} - {duration}"
                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, episode)
                        self.video_list.addItem(item)
                else:
                    
                    title = video_info.get('title', '未知视频')
                    duration = video_info.get('duration', '')
                    item_text = f"{title} - {duration}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, video_info)
                    self.video_list.addItem(item)
            
            # 获取弹幕信息
            if self.parent and hasattr(self.parent, 'danmaku_count_label') and hasattr(self.parent, 'parser'):
                cid = video_info.get("cid", "")
                # 尝试从episodes或collection中获取cid
                if not cid:
                    # 检查番剧
                    if video_info.get("is_bangumi") and video_info.get("bangumi_info"):
                        episodes = video_info["bangumi_info"].get("episodes", [])
                        if episodes:
                            cid = episodes[0].get("cid", "")
                    # 检查课程
                    elif video_info.get("is_cheese") and video_info.get("cheese_info"):
                        episodes = video_info["cheese_info"].get("episodes", [])
                        if episodes:
                            cid = episodes[0].get("cid", "")
                    # 检查普通合集
                    elif video_info.get("collection"):
                        collection = video_info.get("collection", [])
                        if collection:
                            cid = collection[0].get("cid", "")
                    # 检查episodes
                    elif video_info.get("episodes"):
                        episodes = video_info.get("episodes", [])
                        if episodes:
                            cid = episodes[0].get("cid", "")
                
                if cid:
                    import threading
                    def get_danmaku_info():
                        try:
                            if not hasattr(self.parent, 'parser') or not self.parent.parser:
                                print("parser未初始化，无法获取弹幕信息")
                                return
                            
                            print(f"开始获取弹幕信息，cid: {cid}")
                            danmaku_video_info = self.parent.parser.get_danmaku(cid)
                            print(f"获取弹幕信息结果: {danmaku_video_info}")
                            if danmaku_video_info.get('error') == "":
                                count = danmaku_video_info.get('data', {}).get('count', 0)
                                QTimer.singleShot(0, lambda: self.parent.danmaku_count_label.setText(f"{count}条"))
                            else:
                                QTimer.singleShot(0, lambda: self.parent.danmaku_count_label.setText("获取失败"))
                        except Exception as e:
                            print(f"获取弹幕信息失败：{str(e)}")
                            traceback.print_exc()
                            QTimer.singleShot(0, lambda: self.parent.danmaku_count_label.setText("获取失败"))
                    
                    thread = threading.Thread(target=get_danmaku_info, daemon=True)
                    thread.start()
                else:
                    print("未找到cid，无法获取弹幕信息")
                    QTimer.singleShot(0, lambda: self.parent.danmaku_count_label.setText("无cid"))
        else:
            
            if self.parent and hasattr(self.parent, 'show_notification'):
                error_msg = video_info.get('error', '未知错误')
                if '取消' in error_msg:
                    self.parent.show_notification(error_msg, "info")
                else:
                    self.parent.show_notification(f"解析失败：{error_msg}", "error")
    
    def select_all_videos(self):
        self.video_list.selectAll()
    
    def select_save_path(self):
        default_path = self.path_edit.text() if hasattr(self, 'path_edit') and self.path_edit.text() else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        
        if self.parent and hasattr(self.parent, 'show_custom_file_dialog'):
            folder = self.parent.show_custom_file_dialog("选择保存路径")
        else:
            folder = QFileDialog.getExistingDirectory(
                None,  
                "选择保存路径",
                default_path,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
        
        if folder:
            # 验证选择的路径
            try:
                # 规范化路径
                folder = os.path.normpath(folder)
                
                # 确保路径存在且可写
                if not os.path.exists(folder):
                    os.makedirs(folder, exist_ok=True)

                # 测试写入权限 - 使用UUID确保文件名唯一，避免多线程冲突
                import uuid
                test_file = os.path.join(folder, f"permission_test_{uuid.uuid4().hex[:8]}.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                
                self.path_edit.setText(folder)
                if self.parent and hasattr(self.parent, 'show_notification'):
                    self.parent.show_notification("保存路径选择成功", "success")
                    
            except Exception as e:
                error_msg = f"无法使用该路径: {str(e)}"
                logger.error(error_msg)
                if self.parent and hasattr(self.parent, 'show_notification'):
                    self.parent.show_notification(error_msg, "error")
    
    def on_download(self):
        
        if not hasattr(self, 'video_list') or not hasattr(self, 'resolution_combo') or not hasattr(self, 'url_edit') or not hasattr(self, 'path_edit'):
            if self.parent and hasattr(self.parent, 'show_notification'):
                self.parent.show_notification("内部错误：缺少必要组件", "error")
            return
        
        # 获取下载类型选择
        download_video = True
        download_danmaku = True
        if hasattr(self, 'download_video_checkbox'):
            download_video = self.download_video_checkbox.isChecked()
        if hasattr(self, 'download_danmaku_checkbox'):
            download_danmaku = self.download_danmaku_checkbox.isChecked()
        
        # 至少选择一种下载类型
        if not download_video and not download_danmaku:
            if self.parent and hasattr(self.parent, 'show_notification'):
                self.parent.show_notification("请至少选择一种下载类型", "warning")
            return
        
        # 获取选中的视频
        selected_items = self.video_list.selectedItems()
        if not selected_items:
            # 如果只有一个视频，自动选择它
            if self.video_list.count() == 1:
                selected_items = [self.video_list.item(0)]
            elif download_video:
                if self.parent and hasattr(self.parent, 'show_notification'):
                    self.parent.show_notification("请选择要下载的视频", "warning")
                return
            else:
                # 只下载弹幕时，自动选择第一个视频
                if self.video_list.count() > 0:
                    selected_items = [self.video_list.item(0)]
                else:
                    if self.parent and hasattr(self.parent, 'show_notification'):
                        self.parent.show_notification("无视频可选择", "warning")
                    return
        
        selected_videos = [item.data(Qt.UserRole) for item in selected_items]
        
        resolution = self.resolution_combo.currentText()
        
        qn_map = {
            "1080P": 80,
            "720P": 64,
            "480P": 32,
            "360P": 16
        }
        qn = qn_map.get(resolution, 80)  
        
        if self.parent and hasattr(self.parent, 'signal_emitter'):
            
            task_id = str(int(time.time() * 1000))
            
            url = self.url_edit.text().strip()
            
            # 获取并验证保存路径
            save_path = self.path_edit.text() if hasattr(self, 'path_edit') else (self.parent.path_edit.text() if hasattr(self.parent, 'path_edit') else "")
            
            # 验证并规范化保存路径
            try:
                if not save_path or not isinstance(save_path, str) or len(save_path.strip()) == 0:
                    save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
                    logger.warning(f"保存路径无效，使用默认路径: {save_path}")
                else:
                    save_path = os.path.normpath(save_path)
                
                # 确保路径存在且可写
                if not os.path.exists(save_path):
                    os.makedirs(save_path, exist_ok=True)

                # 测试写入权限 - 使用UUID确保文件名唯一，避免多线程冲突
                import uuid
                test_file = os.path.join(save_path, f"permission_test_{uuid.uuid4().hex[:8]}.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                
                logger.info(f"保存路径验证通过: {save_path}")
                
            except Exception as e:
                error_msg = f"保存路径验证失败: {str(e)}"
                logger.error(error_msg)
                if self.parent and hasattr(self.parent, 'show_notification'):
                    self.parent.show_notification(error_msg, "error")
                return
            
            if not self.current_video_info:
                if self.parent and hasattr(self.parent, 'show_notification'):
                    self.parent.show_notification("请先解析视频", "warning")
                return
            
            download_params = {
                "url": url,
                "video_info": self.current_video_info,
                "qn": qn,
                "save_path": save_path,
                "episodes": selected_videos,
                "resume_download": True,
                "task_id": task_id,
                "download_video": download_video,
                "download_danmaku": download_danmaku,
                "video_format": self.config.get_app_setting("video_output_format", "mp4"),
                "audio_format": self.config.get_app_setting("audio_output_format", "mp3"),
                "audio_quality": self.config.get_app_setting("audio_quality", 30280),
                "danmaku_format": self.config.get_app_setting("danmaku_output_format", "xml").upper()
            }
            
            logger.info(f"添加下载任务：{self.current_video_info.get('title', '未知标题')}，共{len(selected_videos)}个视频")
            logger.info(f"分辨率：{resolution} (qn={qn})")
            logger.info(f"保存路径：{save_path}")
            logger.info(f"任务ID：{task_id}")
            logger.info(f"下载视频：{download_video}")
            logger.info(f"下载弹幕：{download_danmaku}")
            logger.info(f"视频格式：{download_params.get('video_format')}")
            logger.info(f"音频格式：{download_params.get('audio_format')}")
            logger.info(f"弹幕格式：{download_params.get('danmaku_format')}")
            logger.info(f"下载参数：{download_params}")

            # 检查HEVC/AV1视频并询问
            if download_video and self.parent and hasattr(self.parent, 'parser'):
                hevc_ask = self.parent.config.get_app_setting("hevc_not_supported_ask", True)
                if hevc_ask:
                    self._check_hevc_before_download(selected_videos, save_path)

            try:
                
                if self.parent and hasattr(self.parent, 'download_manager') and self.parent.download_manager:
                    logger.info("直接调用download_manager.start_download")
                    self.parent.download_manager.start_download(download_params)
                    logger.info("download_manager.start_download调用成功")
                else:
                    
                    if self.parent and hasattr(self.parent, 'signal_emitter'):
                        logger.info("通过信号发送下载请求")
                        self.parent.signal_emitter.start_download.emit(download_params)
                        logger.info("下载信号发送成功")
                    else:
                        logger.error("无法发送下载请求：缺少download_manager或signal_emitter")
                        if self.parent and hasattr(self.parent, 'show_notification'):
                            self.parent.show_notification("无法发送下载请求：缺少必要组件", "error")
                        return
            except Exception as e:
                logger.error(f"发送下载请求失败：{str(e)}")
                if self.parent and hasattr(self.parent, 'show_notification'):
                    self.parent.show_notification(f"发送下载请求失败：{str(e)}", "error")
                return
            
            # 构建通知消息
            download_types = []
            if download_video:
                download_types.append("视频")
            if download_danmaku:
                download_types.append("弹幕")
            download_type_str = "和".join(download_types)
            
            if hasattr(self.parent, 'show_notification'):
                self.parent.show_notification(f"开始下载 {len(selected_videos)} 个{download_type_str}", "success")
            
            # 对于 BilibiliDownloader 主窗口，使用 BatchDownloadWindow 显示下载进度
            if hasattr(self.parent, 'batch_windows'):
                # 检查是否已经有 BatchDownloadWindow
                existing_window = None
                for window in self.parent.batch_windows.values():
                    from ui import BatchDownloadWindow
                    if isinstance(window, BatchDownloadWindow):
                        existing_window = window
                        break
                
                if existing_window:
                    existing_window.show()
                else:
                    # 创建新的 BatchDownloadWindow
                    from ui import BatchDownloadWindow
                    batch_window = BatchDownloadWindow(self.current_video_info, 0, self.parent.download_manager, self.parent.parser)
                    for i, ep in enumerate(selected_videos):
                        if self.current_video_info.get("is_bangumi") or self.current_video_info.get("is_cheese"):
                            ep_name = f"{ep.get('ep_index', '')}"
                            ep_tooltip = ep.get('ep_title', '')
                        else:
                            ep_name = f"第{ep.get('page', i+1)}集"
                            ep_tooltip = ep.get('title', '')
                        batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
                    batch_window.cancel_all.connect(self.parent.on_cancel_download)
                    batch_window.window_closed.connect(lambda tid=task_id: self.parent.on_batch_window_closed(tid))
                    batch_window.show()
                    self.parent.batch_windows[task_id] = batch_window
            # 对于 FloatingBall 自身，使用内置的 download_widget
            elif hasattr(self, 'video_info_widget') and hasattr(self, 'download_widget'):
                self.video_info_widget.hide()
                self.download_widget.show()
                
                if self.expanded_widget:
                    self.expanded_widget.adjustSize()
    
    def update_download_progress(self, progress, status):
        try:
            pass
        except Exception:
            pass
    
    def update_episode_progress(self, task_id, ep_index, progress, status):
        try:
            self._update_episode_progress_impl(task_id, ep_index, progress, status)
        except Exception:
            pass

    def _update_episode_progress_impl(self, task_id, ep_index, progress, status):
        show_speed = self.parent.config.get_app_setting("show_download_speed", True)
        if not show_speed:
            import re
            status = re.sub(r'\s*\([^)]*B/s\)', '', status)
        
        if (not hasattr(self.parent, 'expanded_widget') or not self.parent.expanded_widget) or not hasattr(self.parent, 'download_container_layout') or not self.parent.download_container_layout:
            
            if not hasattr(self.parent, 'pending_progress'):
                self.parent.pending_progress = {}
            self.parent.pending_progress[task_key] = {
                'progress': progress,
                'status': status,
                'task_id': task_id,
                'ep_index': ep_index
            }
            return
        
        
        if hasattr(self.parent, 'pending_progress') and task_key in self.parent.pending_progress:
            pending_info = self.parent.pending_progress[task_key]
            progress = pending_info['progress']
            status = pending_info['status']
            del self.parent.pending_progress[task_key]
        
        if task_key not in self.parent.download_tasks:
            
            task_widget = QWidget()
            task_widget.setStyleSheet(scale_style("background-color: #f0fdf4; border-radius: 8px; padding: 12px; margin-bottom: 8px;"))
            task_layout = QVBoxLayout(task_widget)
            task_layout.setContentsMargins(scale(8), scale(8), scale(8), scale(8))
            task_layout.setSpacing(scale(8))
            
            
            video_name = status.split(' - ')[0] if ' - ' in status else status
            video_name_label = QLabel(video_name)
            video_name_label.setStyleSheet(scale_style("font-size: 14px; font-weight: 500; color: #166534;"))
            video_name_label.setMinimumHeight(scale(24))
            video_name_label.setMaximumWidth(scale(380))
            video_name_label.setToolTip(status)
            video_name_label.setWordWrap(True)
            
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setMinimumHeight(scale(14))
            progress_bar.setStyleSheet(scale_style("QProgressBar { border-radius: 6px; background-color: #dcfce7; } QProgressBar::chunk { border-radius: 6px; background-color: #22c55e; }"))
            
            
            progress_text = QLabel(f"{int(progress)}%")
            progress_text.setStyleSheet(scale_style("font-size: 12px; color: #64748b; font-weight: 500;"))
            progress_text.setAlignment(Qt.AlignRight)
            
            
            task_layout.addWidget(video_name_label)
            task_layout.addWidget(progress_bar)
            task_layout.addWidget(progress_text)
            
            
            try:
                self.parent.download_container_layout.addWidget(task_widget)
                
                self.parent.download_tasks[task_key] = {
                    'widget': task_widget,
                    'name_label': video_name_label,
                    'progress_bar': progress_bar,
                    'progress_text': progress_text
                }
            except Exception as e:
                print(f"添加剧集进度条失败：{str(e)}")
                return
        
        
        if task_key in self.parent.download_tasks:
            task_info = self.parent.download_tasks[task_key]
            try:
                task_info['progress_bar'].setValue(int(progress))
                task_info['progress_text'].setText(f"{int(progress)}%")
                task_info['name_label'].setToolTip(status)
                
                
                if "下载" in status and "流" in status:
                    
                    status_parts = status.split('：')
                    if len(status_parts) > 0:
                        video_name = status_parts[0]
                        task_info['name_label'].setText(video_name)
                elif "合并" in status:
                    task_info['name_label'].setText("合并音视频")
                elif "完成" in status:
                    task_info['name_label'].setText("下载完成")
            except Exception as e:
                print(f"更新剧集进度失败：{str(e)}")
    
    def finish_episode(self, task_id, ep_index, success, message):
        try:
            self._finish_episode_impl(task_id, ep_index, success, message)
        except Exception:
            pass

    def _finish_episode_impl(self, task_id, ep_index, success, message):
        if message == "TASK_PAUSED":
            return
        if success:
            
            if self.parent and hasattr(self.parent, 'show_notification'):
                self.parent.show_notification(f"视频下载完成：{message}", "success")
            

            
            # 下载完成后播放提示音
            if self.parent and hasattr(self.parent, 'config'):
                play_sound = self.parent.config.get_app_setting("play_sound_on_complete", True)
                if play_sound:
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                    except Exception as e:
                        print(f"播放提示音失败：{str(e)}")
        else:
            
            if self.parent and hasattr(self.parent, 'show_notification'):
                self.parent.show_notification(f"视频下载失败：{message}", "error")

class ParseProgressWindow(QDialog):
    # 定义信号
    update_progress_signal = pyqtSignal(int, str)
    add_log_signal = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("解析进度")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.setMinimumSize(max(scale(400), int(sg.width() * 0.3)), max(scale(300), int(sg.height() * 0.3)))
        else:
            self.setMinimumSize(scale(400), scale(300))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAutoFillBackground(True)
        self.setWindowModality(Qt.NonModal)
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
        except Exception as e:
            pass
        
        # 设置样式
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            }
            QTextEdit {
                background-color: #1e1e1e;
                color: #4ec9b0;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 14px;
                selection-background-color: #264f78;
                selection-color: #ffffff;
                show-decoration-selected: 1;
                min-height: 200px;
            }
            QScrollBar:vertical {
                min-width: 10px;
                background: #1e1e1e;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #4ec9b0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #68d3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                min-height: 10px;
                background: #1e1e1e;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #4ec9b0;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #68d3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            QProgressBar {
                min-height: 12px;
                border-radius: 6px;
                background-color: #e9ecef;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #409eff;
            }
            QLabel {
                font-size: 14px;
                color: #333;
            }
        """)
        self.setStyleSheet(custom_style)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("解析进度")
        title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setMinimumSize(scale(28), scale(28))
        close_btn.setMaximumSize(scale(28), scale(28))
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))
        
        # 解析状态标题
        status_label = QLabel("正在解析视频信息...")
        status_label.setStyleSheet(scale_style("font-size: 16px; font-weight: 600;"))
        content_layout.addWidget(status_label)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        content_layout.addWidget(self.log_text, stretch=1)
        
        # 进度条
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(scale(5))
        
        self.progress_label = QLabel("准备中...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_bar)
        
        content_layout.addLayout(progress_layout)

        main_layout.addWidget(content_widget)

        # 连接信号到槽
        self.update_progress_signal.connect(self._update_progress_slot)
        self.add_log_signal.connect(self._add_log_slot)
        
        # 鼠标拖动相关变量
        self.drag_position = None
        
        # 初始化通知组件
        self.notification_widget = NotificationWidget(self)
        self._announcement_bar = None
        self._pending_announcements = []
    
    def show_notification(self, message, notification_type="info"):
        if self.notification_widget:
            self.notification_widget.show_notification(message, notification_type)
    
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
        except Exception:
            event.accept()
    
    def mouseMoveEvent(self, event):
        try:
            if event.buttons() & Qt.LeftButton:
                if self.drag_position:
                    self.move(event.globalPos() - self.drag_position)
                    event.accept()
        except Exception:
            pass
        
    def update_progress(self, progress, message):
        self.update_progress_signal.emit(progress, message)
    
    def _update_progress_slot(self, progress, message):
        try:
            print(f"更新进度: {progress}%, 消息: {message}")
            self.progress_bar.setValue(progress)
            self.progress_label.setText(message)
            log_message = f"[{progress}%] {message}"
            print(f"添加日志: {log_message}")
            self.log_text.append(log_message)
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        except Exception as e:
            print(f"更新进度时出错: {str(e)}")
    
    def add_log(self, message):
        self.add_log_signal.emit(message)
    
    def _add_log_slot(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())


class BaseWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        self.setAutoFillBackground(True)
        
        self.dragging = False
        self.start_pos = None
        self.resizing = False
        self.resize_direction = None
        self.edge_size = scale(8)
    
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton:
                rect = self.rect()
                if event.x() < self.edge_size and event.y() < self.edge_size:
                    self.resize_direction = 'top-left'
                    self.resizing = True
                elif event.x() > rect.width() - self.edge_size and event.y() < self.edge_size:
                    self.resize_direction = 'top-right'
                    self.resizing = True
                elif event.x() < self.edge_size and event.y() > rect.height() - self.edge_size:
                    self.resize_direction = 'bottom-left'
                    self.resizing = True
                elif event.x() > rect.width() - self.edge_size and event.y() > rect.height() - self.edge_size:
                    self.resize_direction = 'bottom-right'
                    self.resizing = True
                elif event.x() < self.edge_size:
                    self.resize_direction = 'left'
                    self.resizing = True
                elif event.x() > rect.width() - self.edge_size:
                    self.resize_direction = 'right'
                    self.resizing = True
                elif event.y() < self.edge_size:
                    self.resize_direction = 'top'
                    self.resizing = True
                elif event.y() > rect.height() - self.edge_size:
                    self.resize_direction = 'bottom'
                    self.resizing = True
                elif event.y() < scale(32):
                    self.dragging = True
                    self.start_pos = event.globalPos() - self.frameGeometry().topLeft()
                    event.accept()
        except Exception:
            event.accept()
    
    def mouseMoveEvent(self, event):
        try:
            if self.resizing and event.buttons() == Qt.LeftButton:
                global_pos = event.globalPos()
                frame_geometry = self.frameGeometry()
                if self.resize_direction == 'top-left':
                    new_width = frame_geometry.width() + (frame_geometry.left() - global_pos.x())
                    new_height = frame_geometry.height() + (frame_geometry.top() - global_pos.y())
                    new_x = global_pos.x()
                    new_y = global_pos.y()
                elif self.resize_direction == 'top-right':
                    new_width = global_pos.x() - frame_geometry.left()
                    new_height = frame_geometry.height() + (frame_geometry.top() - global_pos.y())
                    new_x = frame_geometry.left()
                    new_y = global_pos.y()
                elif self.resize_direction == 'bottom-left':
                    new_width = frame_geometry.width() + (frame_geometry.left() - global_pos.x())
                    new_height = global_pos.y() - frame_geometry.top()
                    new_x = global_pos.x()
                    new_y = frame_geometry.top()
                elif self.resize_direction == 'bottom-right':
                    new_width = global_pos.x() - frame_geometry.left()
                    new_height = global_pos.y() - frame_geometry.top()
                    new_x = frame_geometry.left()
                    new_y = frame_geometry.top()
                elif self.resize_direction == 'left':
                    new_width = frame_geometry.width() + (frame_geometry.left() - global_pos.x())
                    new_height = frame_geometry.height()
                    new_x = global_pos.x()
                    new_y = frame_geometry.top()
                elif self.resize_direction == 'right':
                    new_width = global_pos.x() - frame_geometry.left()
                    new_height = frame_geometry.height()
                    new_x = frame_geometry.left()
                    new_y = frame_geometry.top()
                elif self.resize_direction == 'top':
                    new_width = frame_geometry.width()
                    new_height = frame_geometry.height() + (frame_geometry.top() - global_pos.y())
                    new_x = frame_geometry.left()
                    new_y = global_pos.y()
                elif self.resize_direction == 'bottom':
                    new_width = frame_geometry.width()
                    new_height = global_pos.y() - frame_geometry.top()
                    new_x = frame_geometry.left()
                    new_y = frame_geometry.top()
                else:
                    return
                min_width = scale(400)
                min_height = scale(350)
                new_width = max(new_width, min_width)
                new_height = max(new_height, min_height)
                self.setGeometry(new_x, new_y, new_width, new_height)
                event.accept()
            elif self.dragging and event.buttons() == Qt.LeftButton:
                self.move(event.globalPos() - self.start_pos)
                event.accept()
        except Exception:
            pass
    
    def mouseReleaseEvent(self, event):
        try:
            self.dragging = False
            self.resizing = False
            self.resize_direction = None
            event.accept()
        except Exception:
            event.accept()
    
    def toggle_maximize(self):
        
        if not self.isMaximized():
            self.showMaximized()

class SignalEmitter(QObject):
    parse_start = pyqtSignal(str, bool)
    parse_finished = pyqtSignal(dict)
    parse_progress = pyqtSignal(int, str)  # 信号：解析进度更新
    show_parse_progress = pyqtSignal()  # 信号：显示解析进度窗口
    load_user_info = pyqtSignal()
    user_info_updated = pyqtSignal(dict)
    check_hevc = pyqtSignal()
    hevc_checked = pyqtSignal(bool)
    install_hevc = pyqtSignal()
    hevc_download_progress = pyqtSignal(int)
    hevc_install_finished = pyqtSignal(bool, str)
    verify_cookie = pyqtSignal(str)
    cookie_verified = pyqtSignal(bool, str)
    start_download = pyqtSignal(dict)
    cancel_download = pyqtSignal()
    download_progress = pyqtSignal(int, str)
    set_max_threads = pyqtSignal(int)
    show_notification = pyqtSignal(str, str)
    show_debug_window = pyqtSignal(str, str, str)
    same_task_exists = pyqtSignal(dict)
    show_space_videos = pyqtSignal(dict, list)
    avatar_loaded = pyqtSignal(bytes)
    network_test_result = pyqtSignal(bool, str)
    folders_loaded = pyqtSignal(list)
    folder_content_loaded = pyqtSignal(list)
    folder_error = pyqtSignal(str)
    batch_parse_result = pyqtSignal(object, bool, object)
    batch_parse_progress = pyqtSignal(int, int, str)
    update_available = pyqtSignal(dict)
    announcements_ready = pyqtSignal(list)


class NotificationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self.container = QWidget(self)
        self.container.setStyleSheet(scale_style("background-color: white; border-radius: 8px; border: 1px solid #e8e8e8;"))
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.container)
        
        self.content_layout = QHBoxLayout(self.container)
        self.content_layout.setContentsMargins(scale(20), scale(15), scale(20), scale(15))
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(scale(24), scale(24))
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.icon_label)
        
        self.message_label = QLabel()
        self.message_label.setStyleSheet(scale_style("font-size: 14px; color: #333333; font-family: 'Microsoft YaHei', sans-serif;"))
        self.message_label.setWordWrap(True)
        self.content_layout.addWidget(self.message_label, stretch=1)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; font-size: 16px; color: #999999; padding: 0; font-family: 'Microsoft YaHei', sans-serif;"))
        self.close_btn.setFixedSize(scale(24), scale(24))
        self.close_btn.clicked.connect(self.hide)
        self.content_layout.addWidget(self.close_btn)
        
        self.setMinimumWidth(scale(300))
        self.setMaximumWidth(scale(500))
        
    def show_notification(self, message, notification_type="info"):
        print(f"NotificationWidget.show_notification called with message: {message}, type: {notification_type}")
        try:
            # 立即更新消息内容和样式
            self.message_label.setText(message)
            
            if notification_type == "success":
                self.container.setStyleSheet(scale_style("background-color: #f0f9ff; border-left: 4px solid #1890ff; border-radius: 8px; border: 1px solid #e6f7ff;"))
                self.icon_label.setText("✓")
                self.icon_label.setStyleSheet(scale_style("font-size: 16px; color: #1890ff; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;"))
            elif notification_type == "error":
                self.container.setStyleSheet(scale_style("background-color: #fff2f0; border-left: 4px solid #ff4d4f; border-radius: 8px; border: 1px solid #fff1f0;"))
                self.icon_label.setText("×")
                self.icon_label.setStyleSheet(scale_style("font-size: 16px; color: #ff4d4f; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;"))
            elif notification_type == "warning":
                self.container.setStyleSheet(scale_style("background-color: #fff7e6; border-left: 4px solid #faad14; border-radius: 8px; border: 1px solid #fffbe6;"))
                self.icon_label.setText("!")
                self.icon_label.setStyleSheet(scale_style("font-size: 16px; color: #faad14; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;"))
            else:  
                self.container.setStyleSheet(scale_style("background-color: #f6ffed; border-left: 4px solid #52c41a; border-radius: 8px; border: 1px solid #f6ffed;"))
                self.icon_label.setText("i")
                self.icon_label.setStyleSheet(scale_style("font-size: 16px; color: #52c41a; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;"))
            
            # 调整大小和位置
            self.adjustSize()
            print(f"通知大小：{self.size()}")
            
            self.center()
            print(f"通知位置：{self.pos()}")
            
            # 显示通知
            self.show()
            self.raise_()
            self.activateWindow()
            print("通知已显示")
            
            # 5秒后自动隐藏
            QTimer.singleShot(5000, self.hide)
            print("通知显示成功，5秒后自动隐藏")
        except Exception as e:
            print(f"通知显示失败：{str(e)}")
            traceback.print_exc()
    
    def center(self):
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        window_geometry = self.geometry()
        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = scale(50)  
        
        if x < 0:
            x = scale(10)
        if y < 0:
            y = scale(10)
        if x + window_geometry.width() > screen_geometry.width():
            x = screen_geometry.width() - window_geometry.width() - scale(10)
        if y + window_geometry.height() > screen_geometry.height():
            y = screen_geometry.height() - window_geometry.height() - scale(10)
        self.move(x, y)
        print(f"调整后通知位置：{self.pos()}")
    
    def mousePressEvent(self, event):
        self.hide()

class UpdateDialog(QDialog):
    _progress_signal = pyqtSignal(int, str)
    _status_signal = pyqtSignal(str, bool)

    def __init__(self, parent, update_info):
        try:
            super().__init__(parent)
            self.update_info = update_info
            self.setAttribute(Qt.WA_DeleteOnClose)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
            self.setAutoFillBackground(True)
            self.setFixedSize(scale(460), scale(400))

            self._progress_signal.connect(self._on_progress)
            self._status_signal.connect(self._on_status_update)

            container = QWidget(self)
            container.setObjectName("updateDialogContainer")
            container.setStyleSheet(scale_style("""
                #updateDialogContainer {
                    background-color: white;
                    border-radius: 12px;
                    border: 1px solid #e0e0e0;
                }
                QLabel { font-family: 'Microsoft YaHei', sans-serif; }
                QPushButton { font-family: 'Microsoft YaHei', sans-serif; }
            """))

            main_layout = QVBoxLayout(self)
            main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
            main_layout.addWidget(container)

            layout = QVBoxLayout(container)
            layout.setContentsMargins(scale(24), scale(20), scale(24), scale(20))
            layout.setSpacing(scale(10))

            header_layout = QHBoxLayout()
            header_layout.setSpacing(scale(10))

            icon_label = QLabel()
            icon_label.setFixedSize(scale(36), scale(36))
            icon_label.setStyleSheet(scale_style("""
                background-color: #1890ff;
                border-radius: 18px;
                color: white;
                font-size: 18px;
                font-weight: bold;
                qproperty-alignment: AlignCenter;
            """))
            icon_label.setText("↑")
            header_layout.addWidget(icon_label)

            title_label = QLabel("发现新版本")
            title_label.setStyleSheet(scale_style("font-size: 18px; font-weight: bold; color: #1a1a1a;"))
            header_layout.addWidget(title_label, stretch=1)

            close_btn = QPushButton("×")
            close_btn.setFixedSize(scale(28), scale(28))
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.setStyleSheet(scale_style("""
                QPushButton {
                    background-color: transparent; border: none; border-radius: 14px;
                    font-size: 18px; color: #999; font-weight: bold;
                }
                QPushButton:hover { background-color: #f0f0f0; color: #333; }
            """))
            if not update_info.get("force_update", False):
                close_btn.clicked.connect(self.reject)
            else:
                close_btn.setEnabled(False)
                close_btn.setStyleSheet("background-color: transparent; border: none;")
            header_layout.addWidget(close_btn)
            layout.addLayout(header_layout)

            latest = update_info.get("latest_version", "")
            ver_label = QLabel(f"V{latest} 已发布")
            ver_label.setStyleSheet(scale_style("font-size: 14px; color: #1890ff; font-weight: bold;"))
            layout.addWidget(ver_label)

            notes = update_info.get("release_notes", "")
            if notes:
                notes_edit = QTextEdit()
                notes_edit.setReadOnly(True)
                notes_edit.setPlainText(notes)
                notes_edit.setStyleSheet(scale_style("""
                    QTextEdit {
                        background-color: #f8f9fa; border: 1px solid #e8e8e8;
                        border-radius: 6px; padding: 8px; font-size: 13px;
                        color: #333; font-family: 'Microsoft YaHei', sans-serif;
                    }
                """))
                notes_edit.setMaximumHeight(scale(120))
                layout.addWidget(notes_edit, stretch=1)

            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.progress_bar.setFixedHeight(scale(6))
            self.progress_bar.setTextVisible(False)
            self.progress_bar.setStyleSheet(scale_style("""
                QProgressBar {
                    background-color: #f0f0f0; border: none; border-radius: 3px;
                }
                QProgressBar::chunk {
                    background-color: #1890ff; border-radius: 3px;
                }
            """))
            self.progress_bar.hide()
            layout.addWidget(self.progress_bar)

            self.status_label = QLabel("")
            self.status_label.setStyleSheet(scale_style("font-size: 12px; color: #999;"))
            self.status_label.hide()
            layout.addWidget(self.status_label)

            btn_layout = QHBoxLayout()
            btn_layout.addStretch(1)

            if update_info.get("force_update", False):
                self.download_btn = QPushButton("立即更新")
                self.download_btn.setStyleSheet(scale_style("""
                    QPushButton {
                        background-color: #f5222d; color: white; border: none;
                        border-radius: 6px; padding: 8px 28px; font-size: 14px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #cf1322; }
                    QPushButton:disabled { background-color: #ddd; color: #999; }
                """))
            else:
                skip_btn = QPushButton("稍后再说")
                skip_btn.setStyleSheet(scale_style("""
                    QPushButton {
                        background-color: #f0f0f0; color: #666; border: none;
                        border-radius: 6px; padding: 8px 16px; font-size: 13px;
                    }
                    QPushButton:hover { background-color: #e0e0e0; }
                """))
                skip_btn.clicked.connect(self.reject)
                btn_layout.addWidget(skip_btn)

                self.download_btn = QPushButton("立即更新")
                self.download_btn.setStyleSheet(scale_style("""
                    QPushButton {
                        background-color: #1890ff; color: white; border: none;
                        border-radius: 6px; padding: 8px 28px; font-size: 14px; font-weight: bold;
                    }
                    QPushButton:hover { background-color: #096dd9; }
                    QPushButton:disabled { background-color: #ddd; color: #999; }
                """))

            self.download_btn.clicked.connect(self._on_download)
            btn_layout.addWidget(self.download_btn)
            layout.addLayout(btn_layout)

            self._drag_pos = None
            self._is_downloading = False
        except Exception as e:
            logger.error(f"创建更新对话框失败: {e}")

    def _on_download(self):
        if self._is_downloading:
            return
        self._is_downloading = True
        self.download_btn.setEnabled(False)
        self.download_btn.setText("正在下载...")
        self.progress_bar.show()
        self.status_label.show()
        self.status_label.setText("正在下载更新包...")

        import threading
        def _worker():
            try:
                from cloud_service import CloudService
                import tempfile
                import zipfile
                import shutil
                import subprocess

                download_url = self.update_info.get("download_url", "")
                if not download_url:
                    self._update_status("错误：下载地址为空", True)
                    return

                temp_dir = tempfile.mkdtemp(prefix="bilidown_update_")
                save_path = os.path.join(temp_dir, "update.zip")

                def progress_cb(pct, done, total):
                    try:
                        mb_done = done / 1048576
                        mb_total = total / 1048576
                        self._progress_signal.emit(pct, f"正在下载... {mb_done:.1f}/{mb_total:.1f} MB ({pct}%)")
                    except Exception:
                        pass

                cs = CloudService()
                if not cs.download_update(download_url, save_path, progress_cb):
                    self._update_status("下载失败，请检查网络连接", True)
                    return

                sha256 = self.update_info.get("sha256", "")
                if sha256 and not CloudService.verify_file(save_path, sha256):
                    self._update_status("文件校验失败，请重新下载", True)
                    return

                self._update_status("正在解压更新包...")
                self._progress_signal.emit(-1, "正在解压更新包...")

                extract_dir = os.path.join(temp_dir, "extracted")
                with zipfile.ZipFile(save_path, 'r') as zf:
                    zf.extractall(extract_dir)

                self._update_status("正在替换文件...")

                if hasattr(sys, 'frozen') or hasattr(sys, '_MEIPASS'):
                    app_dir = os.path.dirname(sys.executable)
                else:
                    app_dir = os.path.dirname(os.path.abspath(__file__))

                update_script = os.path.join(temp_dir, "updater.bat")
                script_content = f"""@echo off
chcp 65001 >nul
echo 正在更新B站视频解析工具...
timeout /t 2 /nobreak >nul

xcopy /E /Y /Q "{extract_dir}\\*" "{app_dir}\\"

if %errorlevel% neq 0 (
    echo 更新失败！
    pause
    exit /b 1
)

echo 更新完成，正在启动程序...
start "" "{app_dir}\\{os.path.basename(sys.executable) if hasattr(sys, 'frozen') else 'main.py'}"
exit /b 0
"""
                with open(update_script, 'w', encoding='utf-8') as f:
                    f.write(script_content)

                self._update_status("更新即将完成，程序将自动重启...")

                subprocess.Popen(
                    ['cmd', '/c', update_script],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                import time
                time.sleep(1)

                try:
                    from PyQt5.QtWidgets import QApplication
                    QApplication.quit()
                except Exception:
                    pass
                os._exit(0)

            except Exception as e:
                logger.error(f"热更新失败: {e}")
                self._update_status(f"更新失败：{str(e)}", True)

        threading.Thread(target=_worker, daemon=True).start()

    def _update_status(self, text, is_error=False):
        self._status_signal.emit(text, is_error)

    def _on_progress(self, pct, text):
        try:
            if pct < 0:
                self.progress_bar.setRange(0, 0)
                self.progress_bar.setValue(0)
            else:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(pct)
            self.status_label.setText(text)
        except Exception:
            pass

    def _on_status_update(self, text, is_error):
        try:
            self.status_label.setText(text)
            if is_error:
                self.status_label.setStyleSheet(scale_style("font-size: 12px; color: #f5222d;"))
                self.download_btn.setEnabled(True)
                self.download_btn.setText("重试")
                self._is_downloading = False
        except Exception:
            pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


class AnnouncementBar(QWidget):
    closed = pyqtSignal(str)
    action_triggered = pyqtSignal(dict)

    def __init__(self, parent, announcement):
        super().__init__(parent)
        self.ann = announcement
        ann_type = announcement.get("type", "info")
        dismissible = announcement.get("dismissible", True)

        colors = {
            "info": {"bg": "#e8f4fd", "border": "#91d5ff", "text": "#1890ff", "accent": "#1890ff", "icon_char": "i"},
            "warning": {"bg": "#fff8e6", "border": "#ffe58f", "text": "#fa8c16", "accent": "#fa8c16", "icon_char": "!"},
            "error": {"bg": "#fff2f0", "border": "#ffccc7", "text": "#f5222d", "accent": "#f5222d", "icon_char": "x"},
        }
        c = colors.get(ann_type, colors["info"])

        self.setObjectName("announcementBar")
        self.setFixedHeight(scale(44))
        self.setStyleSheet(f"""
            QWidget#announcementBar {{
                background-color: {c['bg']};
                border-bottom: {scale(2)}px solid {c['border']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(scale(16), scale(4), scale(8), scale(4))
        layout.setSpacing(scale(10))

        try:
            icon_container = QLabel()
            icon_container.setFixedSize(scale(20), scale(20))
            icon_container.setStyleSheet(f"""
                background-color: {c['accent']};
                border-radius: {scale(10)}px;
                color: white;
                font-size: {scale(12)}px;
                font-weight: bold;
                font-family: 'Georgia', serif;
            """)
            icon_container.setText(c["icon_char"])
            icon_container.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_container)
        except Exception:
            pass

        title = announcement.get("title", "")
        content = announcement.get("content", "")
        msg_label = QLabel(f"<b>{title}</b>&nbsp;&nbsp;{content}")
        msg_label.setWordWrap(False)
        msg_label.setStyleSheet(f"color: {c['text']}; font-size: {scale(13)}px; border: none; background: transparent; font-family: 'Microsoft YaHei', sans-serif;")
        msg_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(msg_label, stretch=1)

        action = announcement.get("action", {})
        action_type = action.get("type", "none")
        if action_type in ("update", "url"):
            action_btn = QPushButton("查看详情" if action_type == "url" else "立即更新")
            action_btn.setCursor(Qt.PointingHandCursor)
            action_btn.setFixedHeight(scale(26))
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['accent']}; color: white; border: none;
                    border-radius: {scale(13)}px; padding: 0 {scale(14)}px; font-size: {scale(12)}px;
                    font-family: 'Microsoft YaHei', sans-serif; font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {c['text']}; }}
            """)
            action_btn.clicked.connect(lambda: self.action_triggered.emit(self.ann))
            layout.addWidget(action_btn)

        if dismissible:
            close_btn = QPushButton("×")
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.setFixedSize(scale(28), scale(28))
            close_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent; border: none;
                    border-radius: {scale(14)}px;
                    font-size: {scale(16)}px; color: {c['text']}; font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: rgba(0,0,0,0.08);
                }}
            """)
            close_btn.clicked.connect(self._on_close_clicked)
            layout.addWidget(close_btn)

    def mousePressEvent(self, event):
        event.accept()

    def _on_close_clicked(self):
        try:
            self.closed.emit(self.ann.get("id", ""))
        except Exception:
            pass
        self.hide()
        self.deleteLater()


class DebugWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("程序出现错误")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            win_w = min(scale(800), int(sg.width() * 0.85))
            win_h = min(scale(600), int(sg.height() * 0.85))
            self.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
        else:
            self.setGeometry(scale(100), scale(100), scale(800), scale(600))
        self.setMinimumSize(scale(400), scale(300))
        
        
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # 设置窗口样式
        self.setStyleSheet(scale_style("""
            QWidget {
                background-color: #fff2f0;
            }
            QGroupBox {
                background-color: white;
                border: 1px solid #ffccc7;
                border-radius: 8px;
                margin: 10px;
            }
            QGroupBox::title {
                color: #cf1322;
                font-weight: bold;
                padding: 0 10px;
            }
            QTextEdit {
                font-family: Consolas, monospace;
                font-size: 12px;
                border: 1px solid #ffccc7;
                border-radius: 4px;
                background-color: white;
            }
            QPushButton {
                background-color: #ff4d4f;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #ff7875;
            }
            QPushButton:pressed {
                background-color: #cf1322;
            }
        """))
        
        # 初始化UI
        main_layout = QVBoxLayout(self)
        
        # 错误信息区域
        error_group = QGroupBox("错误信息")
        error_layout = QVBoxLayout()
        self.error_text = QTextEdit()
        self.error_text.setReadOnly(True)
        error_layout.addWidget(self.error_text)
        error_group.setLayout(error_layout)
        main_layout.addWidget(error_group, stretch=1)
        
        # 代码区域
        code_group = QGroupBox("相关代码")
        code_layout = QVBoxLayout()
        self.code_text = QTextEdit()
        self.code_text.setReadOnly(True)
        code_layout.addWidget(self.code_text)
        code_group.setLayout(code_layout)
        main_layout.addWidget(code_group, stretch=2)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        self.copy_btn = QPushButton("复制错误信息")
        self.copy_btn.clicked.connect(self.copy_error)
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.copy_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)
    
    def set_error_info(self, error_msg, code_context, file_path):
        # 提取错误原因
        error_reason = "未知错误"
        lines = error_msg.split('\n')
        for line in lines:
            if 'ZeroDivisionError' in line or 'Error' in line:
                error_reason = line.strip()
                break
        
        # 设置窗口标题
        self.setWindowTitle(f"程序出现错误：{error_reason}")
        
        # 显示错误信息
        error_text = f"文件：{file_path}\n\n错误信息：\n{error_msg}"
        self.error_text.setPlainText(error_text)
        
        # 显示代码上下文，错误行标红
        self.code_text.setHtml(code_context)
    
    def copy_error(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.error_text.toPlainText())
        self.show_notification("错误信息已复制到剪贴板", "success")
    
    def show_notification(self, message, notification_type="info"):
        notification = NotificationWidget(self)
        notification.show_notification(message, notification_type)

class MergeProgressWindow(QDialog):
    update_progress_signal = pyqtSignal(int, str)
    add_log_signal = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("合并进度")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.setMinimumSize(max(scale(400), int(sg.width() * 0.3)), max(scale(300), int(sg.height() * 0.3)))
        else:
            self.setMinimumSize(scale(400), scale(300))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Window)
        self.setAutoFillBackground(True)
        self.setWindowModality(Qt.NonModal)
        
        # 设置样式
        self.setStyleSheet(get_base_style() + scale_style("""QDialog {
            border: 2px solid #409eff;
            border-radius: 12px;
            background-color: white;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        }
        """))
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(scale(2), scale(2), scale(2), scale(2))
        main_layout.setSpacing(scale(0))
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("正在合并音视频...")
        title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setMinimumSize(scale(28), scale(28))
        close_btn.setMaximumSize(scale(28), scale(28))
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setStyleSheet(scale_style("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #4ec9b0;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 14px;
                selection-background-color: #264f78;
                selection-color: #ffffff;
                show-decoration-selected: 1;
                min-height: 200px;
            }
            QScrollBar:vertical {
                min-width: 10px;
                background: #1e1e1e;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #4ec9b0;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #68d3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                min-height: 10px;
                background: #1e1e1e;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal {
                background: #4ec9b0;
                border-radius: 5px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #68d3b8;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """))
        content_layout.addWidget(self.log_text, stretch=1)
        
        # 进度条
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(scale(5))
        
        self.progress_label = QLabel("准备中...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(scale_style("""
            QProgressBar {
                min-height: 12px;
                border-radius: 6px;
                background-color: #e9ecef;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #409eff;
            }
        """))
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        content_layout.addLayout(progress_layout)
        main_layout.addWidget(content_widget)
        
        # 连接信号
        self.update_progress_signal.connect(self._update_progress_slot)
        self.add_log_signal.connect(self._add_log_slot)
        
        # 鼠标拖动
        self.dragging = False
        self.drag_start_position = QPoint()
        title_bar.mousePressEvent = self.mouse_press_event
        title_bar.mouseMoveEvent = self.mouse_move_event
        title_bar.mouseReleaseEvent = self.mouse_release_event
        
        # 通知组件
        self.notification_widget = NotificationWidget()
    
    def mouse_press_event(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouse_move_event(self, event):
        if self.dragging:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()
    
    def mouse_release_event(self, event):
        self.dragging = False
        event.accept()
    
    def update_progress(self, progress, message):
        self.update_progress_signal.emit(progress, message)
    
    def _update_progress_slot(self, progress, message):
        try:
            self.progress_bar.setValue(progress)
            self.progress_label.setText(message)
            log_message = f"[{progress}%] {message}"
            self.log_text.append(log_message)
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        except Exception:
            pass
    
    def add_log(self, message):
        self.add_log_signal.emit(message)
    
    def _add_log_slot(self, message):
        try:
            self.log_text.append(message)
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        except Exception:
            pass
    
    def show_notification(self, message, notification_type="info"):
        self.notification_widget.show_notification(message, notification_type)

class DanmakuSelectionDialog(QDialog):
    def __init__(self, parent, danmakus, selected_danmakus=None):
        super().__init__(parent)
        self.danmakus = danmakus
        self.selected_danmakus = selected_danmakus or []
        self.selected_indices = set()
        self.drag_position = None  
        self.current_sort = "time"  # 默认按时间排序
        self.current_filter = "all"  # 默认显示所有弹幕
        self.search_text = ""  # 搜索文本
        self.current_page = 1  # 当前页码
        self.batch_size = 50  # 每页显示的弹幕数量
        self.filtered_danmakus = []  # 筛选后的弹幕
        
        # 构建选中索引集合
        selected_ids = {d.get('id') for d in self.selected_danmakus}
        for i, d in enumerate(self.danmakus):
            if d.get('id') in selected_ids:
                self.selected_indices.add(i)
        
        self.init_ui()
        self.update_filtered_danmakus()

    def init_ui(self):
        self.setWindowTitle("选择弹幕")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(350), int(sg.height() * 0.3)))
        else:
            self.setMinimumSize(scale(500), scale(350))
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAutoFillBackground(True)
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
        except Exception as e:
            pass
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            }
            QListWidget {
                border: none;
                background-color: #f8fafc;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #e2e8f0;
            }
            QListWidget::item:hover {
                background-color: #e6f7ff;
            }
            QListWidget::item:selected {
                background-color: #bae6fd;
                color: #0284c7;
            }
        """)
        self.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))

        title_label = QLabel("选择弹幕")
        title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
        title_layout.addWidget(title_label, stretch=1)

        close_btn = QPushButton("×")
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(lambda: (self.reject(), self.close()))
        title_layout.addWidget(close_btn)

        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))
        
        filter_layout = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索弹幕内容...")
        self.search_edit.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;"))
        self.search_edit.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_edit, stretch=1)

        self.filter_combo = QComboBox()
        self.filter_combo.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;"))
        self.filter_combo.addItems(["全部弹幕", "滚动弹幕", "顶部弹幕", "底部弹幕", "逆向弹幕", "高级弹幕"])
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;"))
        self.sort_combo.addItems(["按时间排序", "按颜色排序", "按字体大小排序"])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        filter_layout.addWidget(self.sort_combo)

        content_layout.addLayout(filter_layout)

        self.stats_label = QLabel(f"共 {len(self.danmakus)} 条弹幕")
        self.stats_label.setStyleSheet(scale_style("font-size: 14px; color: #64748b;"))
        content_layout.addWidget(self.stats_label)

        self.danmaku_list = QListWidget()
        self.danmaku_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.danmaku_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout.addWidget(self.danmaku_list, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(12))
        
        select_all_btn = QPushButton("全选")
        select_all_btn.setMinimumHeight(scale(36))
        select_all_btn.setMinimumWidth(scale(100))
        select_all_btn.clicked.connect(self.select_all)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.setMinimumHeight(scale(36))
        deselect_all_btn.setMinimumWidth(scale(100))
        deselect_all_btn.clicked.connect(self.deselect_all)
        
        confirm_btn = QPushButton("确认选择")
        confirm_btn.setMinimumHeight(scale(36))
        confirm_btn.setMinimumWidth(scale(120))
        confirm_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(scale(36))
        cancel_btn.setMinimumWidth(scale(100))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        
        content_layout.addLayout(btn_layout)
        
        # 分页控件
        pagination_layout = QHBoxLayout()
        pagination_layout.setSpacing(scale(12))
        
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.setMinimumHeight(scale(32))
        self.prev_page_btn.setMinimumWidth(scale(80))
        self.prev_page_btn.clicked.connect(self.prev_page)
        
        self.page_info_label = QLabel("第 1 页，共 1 页")
        self.page_info_label.setStyleSheet(scale_style("font-size: 14px; color: #64748b;"))
        self.page_info_label.setAlignment(Qt.AlignCenter)
        
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.setMinimumHeight(scale(32))
        self.next_page_btn.setMinimumWidth(scale(80))
        self.next_page_btn.clicked.connect(self.next_page)
        
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.page_info_label, stretch=1)
        pagination_layout.addWidget(self.next_page_btn)
        
        content_layout.addLayout(pagination_layout)
        
        # 初始加载弹幕
        self.load_danmakus()
        
        main_layout.addWidget(content_widget)
    
    def _format_time(self, seconds):
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    def select_all(self):
        # 选择所有筛选后的弹幕
        for original_index, _ in self.filtered_danmakus:
            self.selected_indices.add(original_index)
        # 更新当前页面的复选框状态
        self.load_danmakus()
    
    def deselect_all(self):
        # 取消选择所有筛选后的弹幕
        for original_index, _ in self.filtered_danmakus:
            if original_index in self.selected_indices:
                self.selected_indices.remove(original_index)
        # 更新当前页面的复选框状态
        self.load_danmakus()
    
    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_danmakus()
    
    def next_page(self):
        total_pages = (len(self.filtered_danmakus) + self.batch_size - 1) // self.batch_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_danmakus()
    
    def get_selected_danmakus(self):
        selected_danmakus = []
        # 处理所有选中的弹幕
        for i in self.selected_indices:
            if i < len(self.danmakus):
                selected_danmakus.append(self.danmakus[i])
        return selected_danmakus
    
    def on_search_changed(self, text):
        self.search_text = text
        self.update_filtered_danmakus()
    
    def on_filter_changed(self, index):
        filter_options = ["all", "scroll", "top", "bottom", "reverse", "advanced"]
        if index < len(filter_options):
            self.current_filter = filter_options[index]
            self.update_filtered_danmakus()
    
    def on_sort_changed(self, index):
        sort_options = ["time", "color", "fontsize"]
        if index < len(sort_options):
            self.current_sort = sort_options[index]
            self.update_filtered_danmakus()
    
    def update_filtered_danmakus(self):
        filtered = []
        for i, danmaku in enumerate(self.danmakus):
            if self.search_text and self.search_text.lower() not in danmaku.get('content', '').lower():
                continue

            mode = danmaku.get('mode', 0)
            if self.current_filter != "all":
                if self.current_filter == "scroll" and mode != 1:
                    continue
                elif self.current_filter == "top" and mode != 4:
                    continue
                elif self.current_filter == "bottom" and mode != 5:
                    continue
                elif self.current_filter == "reverse" and mode != 7:
                    continue
                elif self.current_filter == "advanced" and mode != 8:
                    continue

            filtered.append((i, danmaku))

        if self.current_sort == "time":
            filtered.sort(key=lambda x: x[1].get('progress', 0))
        elif self.current_sort == "color":
            filtered.sort(key=lambda x: x[1].get('color', 0))
        elif self.current_sort == "fontsize":
            filtered.sort(key=lambda x: x[1].get('fontsize', 0))

        self.filtered_danmakus = filtered
        self.stats_label.setText(f"共 {len(filtered)} 条弹幕")
        self.current_page = 1
        self.danmaku_list.clear()
        self.load_danmakus()

    def load_danmakus(self):
        self.danmaku_list.clear()

        total_pages = (len(self.filtered_danmakus) + self.batch_size - 1) // self.batch_size

        self.page_info_label.setText(f"第 {self.current_page} 页，共 {total_pages} 页")

        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        start = (self.current_page - 1) * self.batch_size
        end = min(start + self.batch_size, len(self.filtered_danmakus))
        
        # 加载当前页的弹幕
        for i in range(start, end):
            original_index, danmaku = self.filtered_danmakus[i]
            self._add_danmaku_item(original_index, danmaku)
    
    def _add_danmaku_item(self, original_index, danmaku):
        item = QListWidgetItem()
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))
        layout.setSpacing(scale(8))
        
        # 模式映射
        mode_map = {
            1: "滚动弹幕",
            4: "顶部弹幕",
            5: "底部弹幕",
            7: "逆向弹幕",
            8: "高级弹幕"
        }
        
        # 获取模式含义
        mode = danmaku.get('mode', 0)
        mode_text = mode_map.get(mode, f"未知模式({mode})")
        
        content = danmaku.get('content', '无内容')
        time_str = self._format_time(danmaku.get('progress', 0) / 1000)
        
        content_label = QLabel(f"{time_str} - {content}")
        content_label.setStyleSheet(scale_style("font-size: 14px; color: #333333;"))
        content_label.setWordWrap(True)
        
        color = danmaku.get('color', 16777215)
        color_hex = f"#{color:06x}"

        checkbox = QCheckBox()
        checkbox.setChecked(original_index in self.selected_indices)

        def on_checkbox_state_changed(state, idx=original_index):
            if state == Qt.Checked:
                self.selected_indices.add(idx)
            else:
                if idx in self.selected_indices:
                    self.selected_indices.remove(idx)

        checkbox.stateChanged.connect(on_checkbox_state_changed)

        info_layout = QHBoxLayout()
        info_label = QLabel(f"模式: {mode_text} | 字体大小: {danmaku.get('fontsize', 25)} | 颜色: {color_hex}")
        info_label.setStyleSheet(scale_style("font-size: 12px; color: #64748b;"))

        color_widget = QWidget()
        color_widget.setFixedSize(scale(20), scale(20))
        color_widget.setStyleSheet(f"background-color: {color_hex}; border: {scale(1)}px solid black; border-radius: {scale(2)}px;")

        info_layout.addWidget(checkbox)
        info_layout.addWidget(info_label, stretch=1)
        info_layout.addWidget(color_widget)

        layout.addWidget(content_label)
        layout.addLayout(info_layout)

        def on_widget_clicked(event, cb=checkbox):
            cb.setChecked(not cb.isChecked())

        widget.mousePressEvent = on_widget_clicked

        widget.setProperty('original_index', original_index)

        self.danmaku_list.addItem(item)
        size_hint = widget.sizeHint()
        min_height = max(size_hint.height(), scale(80))
        size_hint.setHeight(min_height)
        item.setSizeHint(size_hint)
        self.danmaku_list.setItemWidget(item, widget)
        
        if original_index in self.selected_indices:
            item.setSelected(True)
    
    def on_scroll(self, value):
        pass

class EpisodeSelectionDialog(QDialog):
    def __init__(self, parent, episodes, is_bangumi=False, selected_episodes=None):
        super().__init__(parent)
        self.episodes = episodes
        self.is_bangumi = is_bangumi
        self.filtered_episodes = episodes.copy()
        self.cover_loaders = []  
        self.active_loaders = 0  
        self.max_loaders = 3  
        self.pending_cover_loading = []  
        self.loaded_episodes = 0  
        self.batch_size = 100  
        self.selected_episodes = selected_episodes or []
        self.selected_indices = set()
        self.drag_position = None  
        self.search_text = ""  # 搜索文本
        self.current_sort = "index"  # 默认按集数排序
        
        for ep in self.selected_episodes:
            for i, episode in enumerate(self.episodes):
                
                ep_id_match = episode.get('ep_id') and ep.get('ep_id') and episode.get('ep_id') == ep.get('ep_id')
                page_match = episode.get('page') and ep.get('page') and episode.get('page') == ep.get('page')
                if ep_id_match or page_match:
                    self.selected_indices.add(i)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("选择集数" + ("（番剧）" if self.is_bangumi else "（合集）"))
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(350), int(sg.height() * 0.3)))
        else:
            self.setMinimumSize(scale(500), scale(350))
        
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAutoFillBackground(True)
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
        except Exception as e:
            pass
        
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
            }
            QListWidget {
                border: none;
                background-color: #f8fafc;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #e2e8f0;
            }
            QListWidget::item:hover {
                background-color: #e6f7ff;
            }
            QListWidget::item:selected {
                background-color: #bae6fd;
                color: #0284c7;
            }
            .card-view QListWidget::item {
                min-width: 200px;
                min-height: 170px;
                margin: 10px;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                background-color: white;
            }
            .card-view QListWidget::item:hover {
                border-color: #409eff;
                box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
            }
            .card-view QListWidget::item:selected {
                border-color: #409eff;
                background-color: #e6f7ff;
            }
        """)
        self.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        
        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("选择集数" + ("（番剧）" if self.is_bangumi else "（合集）"))
        title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setToolTip("关闭")
        # 确保关闭按钮能够正确关闭对话框
        close_btn.clicked.connect(lambda: (self.reject(), self.close()))
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索集数标题...")
        self.search_edit.setStyleSheet(scale_style("padding: 10px 12px; border: 1px solid #dee2e6; border-radius: 8px;"))
        self.search_edit.textChanged.connect(self.filter_episodes)
        search_layout.addWidget(self.search_edit, stretch=1)
        
        # 排序下拉菜单
        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet(scale_style("padding: 10px 12px; border: 1px solid #dee2e6; border-radius: 8px;"))
        self.sort_combo.addItems(["按集数排序", "按标题排序"])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        search_layout.addWidget(self.sort_combo)
        
        content_layout.addLayout(search_layout)

        view_layout = QHBoxLayout()
        self.list_radio = QRadioButton("列表模式")
        self.card_radio = QRadioButton("卡片模式")
        self.view_group = QButtonGroup()
        self.view_group.addButton(self.list_radio)
        self.view_group.addButton(self.card_radio)
        self.list_radio.setChecked(True)
        self.list_radio.toggled.connect(lambda: self.switch_view("list"))
        self.card_radio.toggled.connect(lambda: self.switch_view("card"))
        view_layout.addWidget(self.list_radio)
        view_layout.addWidget(self.card_radio)
        view_layout.addStretch(1)
        content_layout.addLayout(view_layout)

        self.stacked_view = QStackedWidget()
        content_layout.addWidget(self.stacked_view, stretch=1)

        self.list_view = QListWidget()
        self.list_view.setAlternatingRowColors(True)
        self.list_view.setSelectionMode(QListWidget.SingleSelection)
        self.list_view.setSelectionBehavior(QListWidget.SelectItems)
        self.populate_list_view()
        self.stacked_view.addWidget(self.list_view)

        self.card_view = QListWidget()
        self.card_view.setViewMode(QListWidget.IconMode)
        self.card_view.setResizeMode(QListWidget.Adjust)
        self.card_view.setFlow(QListWidget.LeftToRight)
        self.card_view.setSpacing(scale(15))
        self.card_view.setSelectionMode(QListWidget.SingleSelection)
        self.card_view.setSelectionBehavior(QListWidget.SelectItems)
        self.card_view.setStyleSheet(".card-view {}")
        self.populate_card_view()
        self.stacked_view.addWidget(self.card_view)

        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setStyleSheet(scale_style("background-color: #52c41a; color: white; padding: 10px 20px; border-radius: 8px;"))
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.setStyleSheet(scale_style("background-color: #919191; color: white; padding: 10px 20px; border-radius: 8px;"))
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.confirm_btn = QPushButton("确认选择")
        self.confirm_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; padding: 10px 24px; border-radius: 8px; font-weight: 500;"))
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.confirm_btn)
        content_layout.addLayout(btn_layout)
        
        main_layout.addWidget(content_widget)

    def _on_widget_clicked(self, event, checkbox, ep):
        if ep.get('permission_denied', False) and not ep.get('has_free_part', False):
            return
        if not checkbox.geometry().contains(checkbox.mapFromParent(event.pos())):
            checkbox.setChecked(not checkbox.isChecked())

    def create_episode_widget(self, ep, index, permission_denied=False):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        layout.setSpacing(scale(12))
        
        
        checkbox = QCheckBox()
        checkbox.setChecked(index in self.selected_indices)
        checkbox.stateChanged.connect(lambda state, idx=index: self.on_checkbox_changed(state, idx))
        if permission_denied:
            checkbox.setDisabled(True)
            widget.setStyleSheet("opacity: 0.6;")
        layout.addWidget(checkbox, alignment=Qt.AlignCenter)
        
        
        cover_label = QLabel()
        cover_label.setMinimumSize(scale(80), scale(60))
        cover_label.setMaximumSize(scale(100), scale(75))
        cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 6px; background-color: #f1f5f9;"))
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setText("无封面")
        layout.addWidget(cover_label)
        
        
        cover_url = ep.get('cover', '')
        if cover_url:
            
            def load_cover():
                
                class CoverLoader(QThread):
                    class SignalEmitter(QObject):
                        finished = pyqtSignal(QPixmap, int)
                    
                    def __init__(self, url, label_index):
                        super().__init__()
                        self.url = url
                        self.label_index = label_index
                        self.signals = self.SignalEmitter()
                    
                    def run(self):
                        try:
                            response = requests.get(self.url, timeout=3)  
                            response.raise_for_status()
                            pixmap = QPixmap()
                            pixmap.loadFromData(response.content)
                            self.signals.finished.emit(pixmap, self.label_index)
                        except:
                            self.signals.finished.emit(QPixmap(), self.label_index)
                
                def on_cover_loaded(pixmap, label_index):
                    try:
                        if not pixmap.isNull():
                            scaled_pixmap = pixmap.scaled(scale(100), scale(75), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            cover_label.setPixmap(scaled_pixmap)
                            cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 6px;"))
                        else:
                            cover_label.setText("加载失败")
                    except Exception:
                        pass
                    finally:
                        
                        self.active_loaders -= 1
                        
                        self.process_pending_cover_loading()
                
                def start_loader():
                    if self.active_loaders < self.max_loaders:
                        self.active_loaders += 1
                        loader = CoverLoader(cover_url, index)
                        self.cover_loaders.append(loader)
                        loader.signals.finished.connect(on_cover_loaded)
                        loader.start()
                    else:
                        
                        self.pending_cover_loading.append((cover_url, cover_label))
                
                start_loader()
            
            
            QTimer.singleShot(10 * index, load_cover)
        
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(scale(4))
        
        
        if self.is_bangumi:
            title = f"{ep.get('ep_index', '')} - {ep.get('ep_title', '')}"
        else:
            if 'page' in ep and 'title' in ep:
                title = f"第{ep['page']}集 - {ep['title']}"
            elif 'ep_index' in ep and 'ep_title' in ep:
                title = f"{ep['ep_index']} - {ep['ep_title']}"
            else:
                title = f"第{index+1}集"
        
        title_label = QLabel(title)
        if permission_denied and not ep.get('has_free_part', False):
            title_label.setStyleSheet(scale_style("font-weight: 500; font-size: 13px; color: #94a3b8;"))
        else:
            title_label.setStyleSheet(scale_style("font-weight: 500; font-size: 13px;"))
        title_label.setWordWrap(True)
        info_layout.addWidget(title_label)
        
        
        duration = ep.get('duration_str', '') or ep.get('duration', '')
        if duration:
            if isinstance(duration, int):
                
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                if hours > 0:
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = str(duration)
            duration_label = QLabel(f"时长: {duration_str}")
            duration_label.setStyleSheet(scale_style("font-size: 11px; color: #64748b;"))
            info_layout.addWidget(duration_label)
        
        
        cid = ep.get('cid', '')
        if cid:
            cid_label = QLabel(f"CID: {cid}")
            cid_label.setStyleSheet(scale_style("font-size: 10px; color: #94a3b8;"))
            info_layout.addWidget(cid_label)
        
        layout.addLayout(info_layout, stretch=1)
        
        widget.mousePressEvent = lambda event, cb=checkbox: self._on_widget_clicked(event, cb, ep)
        
        return widget

    def create_episode_card(self, ep, index):
        widget = QWidget()
        widget.setStyleSheet(scale_style("""
            QWidget {
                background-color: white;
                border-radius: 8px;
            }
        """))
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        layout.setSpacing(scale(0))
        
        
        cover_container = QWidget()
        cover_container.setStyleSheet(scale_style("""
            QWidget {
                border-radius: 8px 8px 0 0;
                background-color: #f1f5f9;
            }
        """))
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        cover_layout.setSpacing(scale(0))
        
        
        checkbox = QCheckBox()
        checkbox.setChecked(index in self.selected_indices)
        checkbox.stateChanged.connect(lambda state, idx=index: self.on_checkbox_changed(state, idx))
        checkbox.setStyleSheet(scale_style("""
            QCheckBox {
                position: absolute;
                top: 8px;
                left: 8px;
                z-index: 10;
            }
        """))
        cover_layout.addWidget(checkbox, alignment=Qt.AlignTop | Qt.AlignLeft)
        
        
        cover_label = QLabel()
        cover_label.setMinimumSize(scale(190), scale(107))
        cover_label.setMaximumSize(scale(190), scale(107))
        cover_label.setStyleSheet("border: none;")
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setText("")
        cover_layout.addWidget(cover_label)
        
        
        duration = ep.get('duration_str', '') or ep.get('duration', '')
        if duration:
            if isinstance(duration, int):
                
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                if hours > 0:
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = str(duration)
            
            duration_label = QLabel(duration_str)
            duration_label.setStyleSheet(scale_style("""
                QLabel {
                    background-color: rgba(0, 0, 0, 0.7);
                    color: white;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                }
            """))
            duration_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
            duration_label.setMinimumHeight(scale(20))
            
            
            duration_layout = QGridLayout()
            duration_layout.setContentsMargins(scale(0), scale(0), scale(8), scale(8))
            duration_layout.addWidget(duration_label, 0, 0, Qt.AlignRight | Qt.AlignBottom)
            cover_layout.addLayout(duration_layout)
        
        layout.addWidget(cover_container)
        
        
        cover_url = ep.get('cover', '')
        if cover_url:
            
            def load_cover():
                
                class CoverLoader(QThread):
                    class SignalEmitter(QObject):
                        finished = pyqtSignal(QPixmap, int)
                    
                    def __init__(self, url, label_index):
                        super().__init__()
                        self.url = url
                        self.label_index = label_index
                        self.signals = self.SignalEmitter()
                    
                    def run(self):
                        try:
                            response = requests.get(self.url, timeout=3)  
                            response.raise_for_status()
                            pixmap = QPixmap()
                            pixmap.loadFromData(response.content)
                            self.signals.finished.emit(pixmap, self.label_index)
                        except:
                            self.signals.finished.emit(QPixmap(), self.label_index)
                
                def on_cover_loaded(pixmap, label_index):
                    try:
                        if not pixmap.isNull():
                            scaled_pixmap = pixmap.scaled(scale(190), scale(107), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                            cover_label.setPixmap(scaled_pixmap)
                            cover_label.setStyleSheet("border: none;")
                    except Exception:
                        pass
                    finally:
                        
                        self.active_loaders -= 1
                        
                        self.process_pending_cover_loading()
                
                def start_loader():
                    if self.active_loaders < self.max_loaders:
                        self.active_loaders += 1
                        loader = CoverLoader(cover_url, index)
                        self.cover_loaders.append(loader)
                        loader.signals.finished.connect(on_cover_loaded)
                        loader.start()
                    else:
                        
                        self.pending_cover_loading.append((cover_url, cover_label))
                
                start_loader()
            
            
            QTimer.singleShot(10 * index, load_cover)
        
        
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(scale(10), scale(8), scale(10), scale(10))
        title_layout.setSpacing(scale(4))
        
        
        if self.is_bangumi:
            episode_num = ep.get('ep_index', f"第{index+1}集")
        else:
            if 'page' in ep:
                episode_num = f"第{ep['page']}集"
            elif 'ep_index' in ep:
                episode_num = ep['ep_index']
            else:
                episode_num = f"第{index+1}集"
        
        episode_label = QLabel(episode_num)
        episode_label.setStyleSheet(scale_style("""
            QLabel {
                color: #737373;
                font-size: 11px;
                font-weight: 500;
            }
        """))
        title_layout.addWidget(episode_label)
        
        
        if self.is_bangumi:
            title = ep.get('ep_title', "")
        else:
            if 'title' in ep:
                title = ep['title']
            elif 'ep_title' in ep:
                title = ep['ep_title']
            else:
                title = ""
        
        title_label = QLabel(title)
        title_label.setStyleSheet(scale_style("""
            QLabel {
                color: #18191C;
                font-size: 13px;
                font-weight: 500;
                line-height: 1.4;
            }
        """))
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(scale(45))
        title_label.setMinimumHeight(scale(40))
        title_layout.addWidget(title_label)
        
        layout.addWidget(title_container)
        
        widget.mousePressEvent = lambda event, cb=checkbox: self._on_widget_clicked(event, cb, ep)
        
        return widget

    def populate_list_view(self):
        self.list_view.clear()
        
        
        self.pending_cover_loading.clear()
        self.active_loaders = 0
        
        
        self.loaded_episodes = 0
        
        
        
        def create_item(i):
            if i >= len(self.filtered_episodes) or i >= self.loaded_episodes + self.batch_size:
                return
            
            ep = self.filtered_episodes[i]
            
            original_index = self.episodes.index(ep)
            item = QListWidgetItem()
            item_widget = self.create_episode_widget(ep, original_index, ep.get('permission_denied', False))
            
            item.setSizeHint(QSize(scale(0), scale(100)))
            item.setData(Qt.UserRole, original_index)
            
            if ep.get('permission_denied', False):
                # 检查是否有免费部分
                has_free_part = ep.get('has_free_part', False)
                if has_free_part:
                    # 有免费部分，保持亮色，但显示免费时长
                    free_duration = ep.get('free_duration', 0)
                    if free_duration > 0:
                        # 更新时长显示为免费时长
                        for i in range(item_widget.layout().count()):
                            widget = item_widget.layout().itemAt(i).widget()
                            if isinstance(widget, QVBoxLayout):
                                for j in range(widget.count()):
                                    label = widget.itemAt(j).widget()
                                    if isinstance(label, QLabel) and label.text().startswith('时长:'):
                                        # 计算免费时长
                                        hours = free_duration // 3600
                                        minutes = (free_duration % 3600) // 60
                                        seconds = free_duration % 60
                                        if hours > 0:
                                            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                                        else:
                                            duration_str = f"{minutes:02d}:{seconds:02d}"
                                        label.setText(f"免费时长: {duration_str}")
                                        label.setStyleSheet(scale_style("font-size: 11px; color: #10b981;"))
                else:
                    # 完全权限不足，变灰
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item_widget.setStyleSheet("opacity: 0.6;")
            
            self.list_view.addItem(item)
            self.list_view.setItemWidget(item, item_widget)
            
            
            QTimer.singleShot(0, lambda: create_item(i + 1))
        
        
        if self.filtered_episodes:
            create_item(0)
            self.loaded_episodes = min(self.batch_size, len(self.filtered_episodes))
        
        
        def on_scroll_bar_value_changed(value):
            scroll_bar = self.list_view.verticalScrollBar()
            if value >= scroll_bar.maximum() - 200 and self.loaded_episodes < len(self.filtered_episodes):
                
                start = self.loaded_episodes
                end = min(start + self.batch_size, len(self.filtered_episodes))
                
                def load_more(i):
                    if i >= end:
                        return
                    
                    ep = self.filtered_episodes[i]
                    
                    original_index = self.episodes.index(ep)
                    item = QListWidgetItem()
                    item_widget = self.create_episode_widget(ep, original_index, ep.get('permission_denied', False))
                    
                    item.setSizeHint(QSize(scale(0), scale(100)))
                    item.setData(Qt.UserRole, original_index)
                    
                    if ep.get('permission_denied', False):
                        item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                        item_widget.setStyleSheet("opacity: 0.6;")
                    
                    self.list_view.addItem(item)
                    self.list_view.setItemWidget(item, item_widget)
                    
                    
                    QTimer.singleShot(0, lambda: load_more(i + 1))
                
                load_more(start)
                self.loaded_episodes = end
        
        
        self.list_view.verticalScrollBar().valueChanged.connect(on_scroll_bar_value_changed)

    def populate_card_view(self):
        self.card_view.clear()
        
        
        self.pending_cover_loading.clear()
        self.active_loaders = 0
        
        
        self.loaded_episodes = 0
        
        
        
        def create_item(i):
            if i >= len(self.filtered_episodes) or i >= self.loaded_episodes + self.batch_size:
                return
            
            ep = self.filtered_episodes[i]
            
            original_index = self.episodes.index(ep)
            item = QListWidgetItem()
            item_widget = self.create_episode_card(ep, original_index)
            item.setSizeHint(QSize(scale(200), scale(170)))
            item.setData(Qt.UserRole, original_index)
            
            if ep.get('permission_denied', False):
                # 检查是否有免费部分
                has_free_part = ep.get('has_free_part', False)
                if has_free_part:
                    # 有免费部分，保持亮色，但显示免费时长
                    free_duration = ep.get('free_duration', 0)
                    if free_duration > 0:
                        # 更新时长显示为免费时长
                        for i in range(item_widget.layout().count()):
                            widget = item_widget.layout().itemAt(i).widget()
                            if isinstance(widget, QVBoxLayout):
                                for j in range(widget.count()):
                                    label = widget.itemAt(j).widget()
                                    if isinstance(label, QLabel) and label.text().startswith('时长:'):
                                        # 计算免费时长
                                        hours = free_duration // 3600
                                        minutes = (free_duration % 3600) // 60
                                        seconds = free_duration % 60
                                        if hours > 0:
                                            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                                        else:
                                            duration_str = f"{minutes:02d}:{seconds:02d}"
                                        label.setText(f"免费时长: {duration_str}")
                                        label.setStyleSheet(scale_style("font-size: 11px; color: #10b981;"))
                else:
                    # 完全权限不足，变灰
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                    item_widget.setStyleSheet("opacity: 0.6;")
            
            self.card_view.addItem(item)
            self.card_view.setItemWidget(item, item_widget)
            
            
            QTimer.singleShot(0, lambda: create_item(i + 1))
        
        
        if self.filtered_episodes:
            create_item(0)
            self.loaded_episodes = min(self.batch_size, len(self.filtered_episodes))
        
        
        def on_scroll_bar_value_changed(value):
            scroll_bar = self.card_view.verticalScrollBar()
            if value >= scroll_bar.maximum() - 200 and self.loaded_episodes < len(self.filtered_episodes):
                
                start = self.loaded_episodes
                end = min(start + self.batch_size, len(self.filtered_episodes))
                
                def load_more(i):
                    if i >= end:
                        return
                    
                    ep = self.filtered_episodes[i]
                    
                    original_index = self.episodes.index(ep)
                    item = QListWidgetItem()
                    item_widget = self.create_episode_card(ep, original_index)
                    item.setSizeHint(QSize(scale(200), scale(170)))
                    item.setData(Qt.UserRole, original_index)
                    
                    if ep.get('permission_denied', False):
                        item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                        item_widget.setStyleSheet("opacity: 0.6;")
                    
                    self.card_view.addItem(item)
                    self.card_view.setItemWidget(item, item_widget)
                    
                    
                    QTimer.singleShot(0, lambda: load_more(i + 1))
                
                load_more(start)
                self.loaded_episodes = end
        
        
        self.card_view.verticalScrollBar().valueChanged.connect(on_scroll_bar_value_changed)

    def filter_episodes(self, keyword):
        keyword = keyword.lower()
        
        selected_indices = list(self.selected_indices)

        if not keyword:
            self.filtered_episodes = self.episodes.copy()
        else:
            self.filtered_episodes = [
                ep for ep in self.episodes
                if keyword in (ep.get('ep_title', '').lower() if self.is_bangumi else ep.get('title', '').lower())
            ]

        # 应用排序
        self.apply_sort()

        if self.list_radio.isChecked():
            self.populate_list_view()
        else:
            self.populate_card_view()
    
    def on_sort_changed(self, index):
        sort_options = ["index", "title"]
        if index < len(sort_options):
            self.current_sort = sort_options[index]
            self.apply_sort()
            if self.list_radio.isChecked():
                self.populate_list_view()
            else:
                self.populate_card_view()
    
    def apply_sort(self):
        if self.current_sort == "index":
            # 按集数排序
            def get_episode_index(ep):
                # 尝试获取page或ep_index
                page = ep.get('page')
                if page:
                    try:
                        return int(page)
                    except:
                        pass
                ep_index = ep.get('ep_index')
                if ep_index:
                    try:
                        return int(ep_index)
                    except:
                        pass
                return 0
            self.filtered_episodes.sort(key=get_episode_index)
        elif self.current_sort == "title":
            # 按标题排序
            self.filtered_episodes.sort(key=lambda x: x.get('title', '') or x.get('ep_title', ''))

    def switch_view(self, view_type):
        
        selected_indices = list(self.selected_indices)

        if view_type == "list":
            self.stacked_view.setCurrentWidget(self.list_view)
            self.populate_list_view()
        else:
            self.stacked_view.setCurrentWidget(self.card_view)
            self.populate_card_view()
    
    def on_checkbox_changed(self, state, index):
        ep = self.episodes[index]
        if ep.get('permission_denied', False) and not ep.get('has_free_part', False):
            return
        if state == Qt.Checked:
            self.selected_indices.add(index)
        else:
            self.selected_indices.discard(index)
    
    def process_pending_cover_loading(self):
        while self.pending_cover_loading and self.active_loaders < self.max_loaders:
            cover_url, cover_label = self.pending_cover_loading.pop(0)
            self.active_loaders += 1
            
            
            class CoverLoader(QThread):
                class SignalEmitter(QObject):
                    finished = pyqtSignal(QPixmap)
                
                def __init__(self, url):
                    super().__init__()
                    self.url = url
                    self.signals = self.SignalEmitter()
                
                def run(self):
                    try:
                        response = requests.get(self.url, timeout=3)
                        response.raise_for_status()
                        pixmap = QPixmap()
                        pixmap.loadFromData(response.content)
                        self.signals.finished.emit(pixmap)
                    except:
                        self.signals.finished.emit(QPixmap())
            
            def on_cover_loaded(pixmap):
                try:
                    if not pixmap.isNull():
                        
                        scaled_pixmap = pixmap.scaled(scale(100), scale(75), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        cover_label.setPixmap(scaled_pixmap)
                        cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 6px;"))
                    else:
                        cover_label.setText("加载失败")
                except Exception:
                    pass
                finally:
                    
                    self.active_loaders -= 1
                    
                    self.process_pending_cover_loading()
            
            loader = CoverLoader(cover_url)
            self.cover_loaders.append(loader)
            loader.signals.finished.connect(on_cover_loaded)
            loader.start()

    def select_all(self):
        
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        for i in range(current_view.count()):
            item = current_view.item(i)
            index = item.data(Qt.UserRole)
            ep = self.episodes[index]
            if ep.get('permission_denied', False) and not ep.get('has_free_part', False):
                continue
            self.selected_indices.add(index)
            
            widget = current_view.itemWidget(item)
            if widget:
                for child in widget.findChildren(QCheckBox):
                    child.setChecked(True)

    def deselect_all(self):
        
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        for i in range(current_view.count()):
            item = current_view.item(i)
            index = item.data(Qt.UserRole)
            self.selected_indices.discard(index)
            
            widget = current_view.itemWidget(item)
            if widget:
                for child in widget.findChildren(QCheckBox):
                    child.setChecked(False)

    def accept(self):
        
        self.selected_episodes = [self.episodes[i] for i in sorted(self.selected_indices)]
        super().accept()
    
    def mousePressEvent(self, event):
        
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position') and self.drag_position is not None:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        
        self.drag_position = None
        event.accept()

    def closeEvent(self, event):
        try:
            for loader in self.cover_loaders:
                if loader.isRunning():
                    loader.terminate()
                    loader.wait(100)
            self.cover_loaders.clear()
        except Exception:
            pass
        try:
            super().closeEvent(event)
        except Exception:
            event.accept()


class TaskManagerWindow(BaseWindow):
    def __init__(self, task_manager, parser, download_manager, config, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.Tool)
        self.setAutoFillBackground(True)
        self.task_manager = task_manager
        self.parser = parser
        self.download_manager = download_manager
        self.config = config
        self.batch_windows = {}
        self.init_ui()
        if hasattr(self.download_manager, 'task_status_changed'):
            self.download_manager.task_status_changed.connect(self.refresh_task_list)
        if hasattr(self.download_manager, 'task_added'):
            self.download_manager.task_added.connect(self.refresh_task_list)

    def init_ui(self):
        self.setWindowTitle("任务管理")
        screen = QApplication.primaryScreen()
        sg = screen.geometry() if screen else None
        if sg:
            win_w = min(scale(1100), int(sg.width() * 0.85))
            win_h = min(scale(700), int(sg.height() * 0.85))
            self.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
            self.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
        else:
            self.setGeometry(scale(100), scale(100), scale(1100), scale(700))
            self.setMinimumSize(scale(500), scale(400))
        
        custom_style = get_base_style() + scale_style("""
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
                background-color: white;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                min-height: 32px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                min-width: 32px;
                min-height: 32px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
                padding: 0px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """)
        self.setStyleSheet(custom_style)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(0), scale(10), scale(0))
        title_layout.setSpacing(scale(8))
        title_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        title_label = QLabel("任务管理")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label, stretch=1)
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        maximize_btn = QPushButton("□")
        maximize_btn.setObjectName("maximizeBtn")
        maximize_btn.clicked.connect(self.toggle_maximize)
        title_layout.addWidget(maximize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.custom_close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))
        
        title_label = QLabel("下载任务管理")
        title_label.setStyleSheet(scale_style("font-size: 16px; font-weight: bold; color: #2563eb;"))
        title_label.setMinimumHeight(scale(36))
        content_layout.addWidget(title_label)

        self.task_list = QListWidget()
        self.task_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.task_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.task_list.setStyleSheet(scale_style("""
            QListWidget {
                border: none;
                background-color: transparent;
                outline: none;
            }
            QListWidget::item {
                border: none;
                padding: 4px 0px;
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: transparent;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f5f9;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                min-height: 30px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94a3b8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """))
        content_layout.addWidget(self.task_list, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(12))
        btn_style_primary = scale_style("QPushButton { background-color: #3b82f6; color: white; padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500; min-height: 32px; border: none; } QPushButton:hover { background-color: #2563eb; } QPushButton:pressed { background-color: #1d4ed8; }")
        btn_style_danger = scale_style("QPushButton { background-color: #ef4444; color: white; padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500; min-height: 32px; border: none; } QPushButton:hover { background-color: #dc2626; } QPushButton:pressed { background-color: #b91c1c; }")
        btn_style_secondary = scale_style("QPushButton { background-color: #f1f5f9; color: #475569; padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500; min-height: 32px; border: 1px solid #e2e8f0; } QPushButton:hover { background-color: #e2e8f0; } QPushButton:pressed { background-color: #cbd5e1; }")
        btn_style_warning = scale_style("QPushButton { background-color: #f59e0b; color: white; padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 500; min-height: 32px; border: none; } QPushButton:hover { background-color: #d97706; } QPushButton:pressed { background-color: #b45309; }")
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setStyleSheet(btn_style_primary)
        self.refresh_btn.setMinimumHeight(scale(36))
        self.refresh_btn.setMinimumWidth(scale(100))
        self.refresh_btn.clicked.connect(self.refresh_task_list)
        self.clear_completed_btn = QPushButton("清除已完成")
        self.clear_completed_btn.setStyleSheet(btn_style_secondary)
        self.clear_completed_btn.setMinimumHeight(scale(36))
        self.clear_completed_btn.setMinimumWidth(scale(100))
        self.clear_completed_btn.clicked.connect(self.clear_completed_tasks)
        self.batch_delete_btn = QPushButton("批量删除")
        self.batch_delete_btn.setStyleSheet(btn_style_warning)
        self.batch_delete_btn.setMinimumHeight(scale(36))
        self.batch_delete_btn.setMinimumWidth(scale(100))
        self.batch_delete_btn.clicked.connect(self.toggle_checkboxes)
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setStyleSheet(btn_style_secondary)
        self.select_all_btn.setMinimumHeight(scale(36))
        self.select_all_btn.setMinimumWidth(scale(80))
        self.select_all_btn.clicked.connect(self.select_all_tasks)
        self.select_all_btn.hide()
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.setStyleSheet(btn_style_secondary)
        self.deselect_all_btn.setMinimumHeight(scale(36))
        self.deselect_all_btn.setMinimumWidth(scale(100))
        self.deselect_all_btn.clicked.connect(self.deselect_all_tasks)
        self.deselect_all_btn.hide()
        self.confirm_delete_btn = QPushButton("确认删除")
        self.confirm_delete_btn.setStyleSheet(btn_style_danger)
        self.confirm_delete_btn.setMinimumHeight(scale(36))
        self.confirm_delete_btn.setMinimumWidth(scale(100))
        self.confirm_delete_btn.clicked.connect(self.batch_delete_tasks)
        self.confirm_delete_btn.hide()
        self.close_btn = QPushButton("关闭")
        self.close_btn.setStyleSheet(btn_style_secondary)
        self.close_btn.setMinimumHeight(scale(36))
        self.close_btn.setMinimumWidth(scale(80))
        self.close_btn.clicked.connect(self.custom_close)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.clear_completed_btn)
        btn_layout.addWidget(self.batch_delete_btn)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addWidget(self.confirm_delete_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.close_btn)
        content_layout.addLayout(btn_layout)
        
        self.show_checkboxes = False
        self.checkbox_map = {}
        
        main_layout.addWidget(content_widget)

        self.refresh_task_list()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_task_list)
        self.timer.start(5000)

    def refresh_task_list(self):
        current_scroll_pos = self.task_list.verticalScrollBar().value()
        current_selection = None
        if self.task_list.currentItem():
            current_selection = self.task_list.currentItem().data(Qt.UserRole)
        
        self.task_list.clear()
        self.checkbox_map.clear()
        tasks = self.task_manager.get_all_tasks()
        
        status_color_map = {
            "completed": "#22c55e",
            "failed": "#ef4444",
            "downloading": "#3b82f6",
            "pending": "#f59e0b",
            "paused": "#8b5cf6",
            "unknown": "#94a3b8"
        }
        status_map = {
            "completed": "已完成",
            "failed": "失败",
            "downloading": "下载中",
            "pending": "待处理",
            "paused": "已暂停",
            "unknown": "未知"
        }
        progress_gradient_map = {
            "completed": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22c55e, stop:1 #4ade80)",
            "failed": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #f87171)",
            "downloading": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #60a5fa)",
            "pending": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #fbbf24)",
            "paused": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8b5cf6, stop:1 #a78bfa)",
            "unknown": "#94a3b8"
        }
        type_color_map = {
            "视频+弹幕": "#8b5cf6",
            "视频": "#10b981",
            "弹幕": "#f59e0b"
        }
        type_bg_map = {
            "视频+弹幕": "#f5f3ff",
            "视频": "#ecfdf5",
            "弹幕": "#fffbeb"
        }
        
        card_base_style = scale_style("""
            QWidget#taskCard {
                background-color: white;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QWidget#taskCard:hover {
                border: 1px solid #cbd5e1;
            }
        """)
        
        for task in tasks:
            task_id = task.get("id")
            title = task.get("title", "未知视频")
            status = task.get("status", "未知")
            progress = task.get("progress", 0)
            save_path = task.get("save_path", "")
            url = task.get("url", "")
            error_message = task.get("error_message", "")
            
            status_color = status_color_map.get(status, "#94a3b8")
            status_text = status_map.get(status, "未知")
            progress_gradient = progress_gradient_map.get(status, "#94a3b8")
            
            download_video = task.get("download_video", True)
            download_danmaku = task.get("download_danmaku", False)
            
            task_type = ""
            if download_video and download_danmaku:
                task_type = "视频+弹幕"
            elif download_video:
                task_type = "视频"
            elif download_danmaku:
                task_type = "弹幕"
            
            item_widget = QWidget()
            item_widget.setObjectName("taskCard")
            item_widget.setStyleSheet(card_base_style)
            
            card_layout = QVBoxLayout(item_widget)
            card_layout.setContentsMargins(scale(16), scale(14), scale(16), scale(14))
            card_layout.setSpacing(scale(8))
            
            header_layout = QHBoxLayout()
            header_layout.setSpacing(scale(10))
            
            if self.show_checkboxes:
                checkbox = QCheckBox()
                checkbox.setMinimumSize(scale(20), scale(20))
                header_layout.addWidget(checkbox)
                self.checkbox_map[task_id] = checkbox
            
            dot_size = scale(8)
            dot_label = QLabel()
            dot_label.setFixedSize(dot_size, dot_size)
            dot_label.setStyleSheet(scale_style(f"background-color: {status_color}; border-radius: 4px; min-width: 8px; max-width: 8px; min-height: 8px; max-height: 8px;"))
            header_layout.addWidget(dot_label)
            
            title_label = QLabel(title)
            title_label.setStyleSheet(scale_style("font-weight: 600; font-size: 13px; color: #1e293b;"))
            title_label.setWordWrap(True)
            header_layout.addWidget(title_label, stretch=1)
            
            if task_type:
                type_tag = QLabel(task_type)
                type_color = type_color_map.get(task_type, "#64748b")
                type_bg = type_bg_map.get(task_type, "#f1f5f9")
                type_tag.setStyleSheet(scale_style(f"background-color: {type_bg}; color: {type_color}; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 500;"))
                type_tag.setAlignment(Qt.AlignCenter)
                header_layout.addWidget(type_tag)
            
            status_badge = QLabel(status_text)
            status_badge.setStyleSheet(scale_style(f"background-color: {status_color}18; color: {status_color}; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: 600;"))
            status_badge.setAlignment(Qt.AlignCenter)
            header_layout.addWidget(status_badge)
            
            duration = task.get("duration", "")
            if duration:
                duration_label = QLabel(duration)
                duration_label.setStyleSheet(scale_style("font-size: 11px; color: #94a3b8;"))
                header_layout.addWidget(duration_label)
            
            card_layout.addLayout(header_layout)
            
            progress_layout = QHBoxLayout()
            progress_layout.setSpacing(scale(10))
            progress_pct = QLabel(f"{progress}%")
            progress_pct.setStyleSheet(scale_style("font-size: 12px; font-weight: 600; color: #475569; min-width: 40px;"))
            progress_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(progress)
            progress_bar.setFixedHeight(scale(6))
            progress_bar.setTextVisible(False)
            progress_bar.setStyleSheet(scale_style(f"""
                QProgressBar {{
                    border-radius: 3px;
                    background-color: #f1f5f9;
                    border: none;
                }}
                QProgressBar::chunk {{
                    border-radius: 3px;
                    background: {progress_gradient};
                }}
            """))
            progress_layout.addWidget(progress_bar, stretch=1)
            progress_layout.addWidget(progress_pct)
            card_layout.addLayout(progress_layout)
            
            info_layout = QHBoxLayout()
            info_layout.setSpacing(scale(8))
            
            path_icon_label = QLabel("📁")
            path_icon_label.setStyleSheet(scale_style("font-size: 12px;"))
            info_layout.addWidget(path_icon_label)
            
            path_text = save_path[:50] + "..." if len(save_path) > 50 else save_path
            path_label = QLabel(path_text if save_path else "未设置保存路径")
            path_label.setToolTip(save_path)
            path_label.setWordWrap(False)
            path_label.setStyleSheet(scale_style("font-size: 11px; color: #94a3b8;"))
            info_layout.addWidget(path_label, stretch=1)
            
            if save_path:
                open_dir_btn = QPushButton("打开目录")
                open_dir_btn.setStyleSheet(scale_style("QPushButton { background-color: transparent; color: #3b82f6; padding: 2px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #3b82f6; } QPushButton:hover { background-color: #eff6ff; }"))
                open_dir_btn.clicked.connect(lambda checked, p=save_path: self.open_directory(p))
                info_layout.addWidget(open_dir_btn)
            
            card_layout.addLayout(info_layout)
            
            url_layout = QHBoxLayout()
            url_layout.setSpacing(scale(6))
            url_icon_label = QLabel("🔗")
            url_icon_label.setStyleSheet(scale_style("font-size: 12px;"))
            url_layout.addWidget(url_icon_label)
            url_text = url[:60] + "..." if len(url) > 60 else url
            url_link = QLabel(f"<a href='{url}' style='color: #3b82f6; text-decoration: none;'>{url_text}</a>")
            url_link.setOpenExternalLinks(True)
            url_link.setToolTip(f"点击打开链接\n右键复制链接")
            url_link.setStyleSheet(scale_style("font-size: 11px;"))
            url_layout.addWidget(url_link, stretch=1)
            
            copy_btn = QPushButton("复制")
            copy_btn.setStyleSheet(scale_style("QPushButton { background-color: transparent; color: #64748b; padding: 2px 8px; border-radius: 4px; font-size: 11px; border: 1px solid #e2e8f0; } QPushButton:hover { background-color: #f8fafc; color: #475569; border: 1px solid #cbd5e1; }"))
            copy_btn.clicked.connect(lambda checked, u=url: self.copy_to_clipboard(u))
            url_layout.addWidget(copy_btn)
            
            card_layout.addLayout(url_layout)
            
            if error_message:
                error_label = QLabel(f"⚠ {error_message[:80]}{'...' if len(error_message) > 80 else ''}")
                error_label.setStyleSheet(scale_style("color: #ef4444; font-size: 11px; background-color: #fef2f2; padding: 4px 8px; border-radius: 4px;"))
                error_label.setToolTip(error_message)
                error_label.setWordWrap(True)
                card_layout.addWidget(error_label)
            
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(scale(8))
            
            card_btn_style = scale_style("QPushButton { padding: 4px 12px; border-radius: 5px; font-size: 11px; font-weight: 500; min-height: 26px; border: none; }")
            
            download_btn = QPushButton("查看下载")
            download_btn.setStyleSheet(card_btn_style + scale_style("QPushButton { background-color: #3b82f6; color: white; } QPushButton:hover { background-color: #2563eb; } QPushButton:pressed { background-color: #1d4ed8; }"))
            download_btn.clicked.connect(lambda checked, t=task: self.open_download_window(t))
            btn_layout.addWidget(download_btn)
            
            if status == "downloading":
                pause_btn = QPushButton("暂停")
                pause_btn.setStyleSheet(card_btn_style + scale_style("QPushButton { background-color: #f59e0b; color: white; } QPushButton:hover { background-color: #d97706; } QPushButton:pressed { background-color: #b45309; }"))
                pause_btn.clicked.connect(lambda checked, t=task: self.pause_task(t))
                btn_layout.addWidget(pause_btn)
                stop_btn = QPushButton("停止")
                stop_btn.setStyleSheet(card_btn_style + scale_style("QPushButton { background-color: #ef4444; color: white; } QPushButton:hover { background-color: #dc2626; } QPushButton:pressed { background-color: #b91c1c; }"))
                stop_btn.clicked.connect(lambda checked, t=task: self.stop_task(t))
                btn_layout.addWidget(stop_btn)
            elif status in ["failed", "pending", "paused"]:
                resume_btn = QPushButton("继续")
                resume_btn.setStyleSheet(card_btn_style + scale_style("QPushButton { background-color: #22c55e; color: white; } QPushButton:hover { background-color: #16a34a; } QPushButton:pressed { background-color: #15803d; }"))
                resume_btn.clicked.connect(lambda checked, t=task: self.resume_task(t))
                btn_layout.addWidget(resume_btn)
            delete_btn = QPushButton("删除")
            delete_btn.setStyleSheet(card_btn_style + scale_style("QPushButton { background-color: #f1f5f9; color: #ef4444; border: 1px solid #fecaca; } QPushButton:hover { background-color: #fef2f2; } QPushButton:pressed { background-color: #fee2e2; }"))
            delete_btn.clicked.connect(lambda checked, tid=task_id: self.delete_task(tid))
            btn_layout.addWidget(delete_btn)
            btn_layout.addStretch(1)
            card_layout.addLayout(btn_layout)
            
            list_item = QListWidgetItem()
            item_widget.adjustSize()
            hint_h = item_widget.sizeHint().height() + scale(8)
            list_item.setSizeHint(QSize(0, hint_h))
            list_item.setData(Qt.UserRole, task)
            self.task_list.addItem(list_item)
            self.task_list.setItemWidget(list_item, item_widget)
            
            if current_selection and task_id == current_selection.get("id"):
                self.task_list.setCurrentItem(list_item)
        
        try:
            self.task_list.itemDoubleClicked.disconnect()
        except:
            pass
        self.task_list.itemDoubleClicked.connect(self.on_task_clicked)
        
        self.task_list.verticalScrollBar().setValue(current_scroll_pos)

    def resume_task(self, task):
        task_id = task.get("id")
        if task.get("status") == "paused":
            if self.download_manager:
                self.download_manager.resume_task(task_id)
        else:
            new_task_id = str(int(time.time() * 1000))
            download_params = {
                "url": task.get("url", ""),
                "video_info": task.get("video_info", {}),
                "qn": task.get("qn", ""),
                "save_path": task.get("save_path", ""),
                "episodes": task.get("episodes", []),
                "resume_download": True,
                "task_id": new_task_id,
                "download_video": task.get("download_video", True),
                "download_danmaku": task.get("download_danmaku", False),
                "danmaku_format": task.get("danmaku_format", "XML"),
                "video_format": task.get("video_format", self.config.get_app_setting("video_output_format", "mp4")),
                "audio_format": task.get("audio_format", self.config.get_app_setting("audio_output_format", "mp3")),
                "audio_quality": task.get("audio_quality", self.config.get_app_setting("audio_quality", 30280))
            }

            self.download_manager.start_download(download_params)
            
            batch_window = BatchDownloadWindow(task.get("video_info", {}), 0, self.download_manager, self.parser)
            episodes = task.get("episodes", [])
            for i, ep in enumerate(episodes):
                if task.get("video_info", {}).get("is_bangumi"):
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                batch_window.add_episode_progress(ep_name, ep_tooltip, new_task_id, i)
            if self.download_manager:
                self.download_manager.episode_progress_updated.connect(batch_window.update_episode_progress)
                self.download_manager.episode_finished.connect(batch_window.finish_episode)
            batch_window.cancel_all.connect(lambda: self.download_manager.cancel_all())
            batch_window.window_closed.connect(lambda tid=new_task_id: self.on_batch_window_closed(tid))
            batch_window.show()
            
            if new_task_id:
                self.batch_windows[new_task_id] = batch_window
        
        self.refresh_task_list()

    def delete_task(self, task_id):
        self.task_manager.delete_task(task_id)
        self.refresh_task_list()

    def toggle_checkboxes(self):
        self.show_checkboxes = not self.show_checkboxes
        if self.show_checkboxes:
            self.batch_delete_btn.setText("取消选择")
            self.select_all_btn.show()
            self.deselect_all_btn.show()
            self.confirm_delete_btn.show()
        else:
            self.batch_delete_btn.setText("批量删除")
            self.select_all_btn.hide()
            self.deselect_all_btn.hide()
            self.confirm_delete_btn.hide()
        QTimer.singleShot(0, self.refresh_task_list)

    def select_all_tasks(self):
        for task_id, checkbox in self.checkbox_map.items():
            checkbox.setChecked(True)

    def deselect_all_tasks(self):
        for task_id, checkbox in self.checkbox_map.items():
            checkbox.setChecked(False)

    def batch_delete_tasks(self):
        selected_task_ids = []
        for task_id, checkbox in self.checkbox_map.items():
            if checkbox.isChecked():
                selected_task_ids.append(task_id)
        
        if not selected_task_ids:
            if self.parent() and hasattr(self.parent(), 'show_notification'):
                self.parent().show_notification("请先选择要删除的任务", "warning")
            else:
                QMessageBox.warning(self, "提示", "请先选择要删除的任务")
            return
        
        task_count = len(selected_task_ids)
        
        reply = QMessageBox.question(self, "确认删除", f"确定要删除选中的{task_count}个任务吗？", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for task_id in selected_task_ids:
                self.task_manager.delete_task(task_id)
            self.refresh_task_list()
            self.show_checkboxes = False
            self.batch_delete_btn.setText("批量删除")
            self.select_all_btn.hide()
            self.deselect_all_btn.hide()
            self.confirm_delete_btn.hide()

    def clear_completed_tasks(self):
        self.task_manager.clear_completed_tasks()
        self.refresh_task_list()

    def open_directory(self, path):
        import subprocess
        try:
            if os.name == 'nt':
                subprocess.run(['explorer', os.path.normpath(path)], check=False)
            elif os.name == 'posix':
                subprocess.run(['open', path] if sys.platform == 'darwin' else ['xdg-open', path], check=True)
        except Exception as e:
            print(f"打开目录失败：{str(e)}")

    def copy_to_clipboard(self, text):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        except Exception as e:
            logger.error(f"复制到剪贴板失败：{str(e)}")

    def on_task_clicked(self, item):
        task = item.data(Qt.UserRole)
        if not task:
            return
        
        # 创建无边框的对话框
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle(f"任务详情 - {task.get('title', '未知任务')}")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
        else:
            dialog.setMinimumSize(scale(500), scale(400))
        
        # 添加自定义标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 32px; border-top-left-radius: 6px; border-top-right-radius: 6px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(0), scale(10), scale(0))
        title_layout.setSpacing(scale(8))
        
        title_label = QLabel(f"任务详情 - {task.get('title', '未知任务')}")
        title_label.setStyleSheet(scale_style("font-weight: bold; font-size: 13px; color: white;"))
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 14px; min-width: 28px; min-height: 28px;"))
        close_btn.clicked.connect(dialog.reject)
        
        title_layout.addWidget(title_label, stretch=1)
        title_layout.addWidget(close_btn)
        
        # 添加拖拽功能
        dialog.dragging = False
        dialog.start_pos = None
        
        def mousePressEvent(event):
            try:
                if event.button() == Qt.LeftButton and event.y() < scale(32):
                    dialog.dragging = True
                    dialog.start_pos = event.globalPos() - dialog.frameGeometry().topLeft()
                    event.accept()
            except Exception:
                event.accept()
        
        def mouseMoveEvent(event):
            try:
                if dialog.dragging and event.buttons() == Qt.LeftButton:
                    dialog.move(event.globalPos() - dialog.start_pos)
                    event.accept()
            except Exception:
                pass
        
        def mouseReleaseEvent(event):
            try:
                dialog.dragging = False
                event.accept()
            except Exception:
                event.accept()
        
        dialog.mousePressEvent = mousePressEvent
        dialog.mouseMoveEvent = mouseMoveEvent
        dialog.mouseReleaseEvent = mouseReleaseEvent
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 8px;
                background-color: white;
            }
            QGroupBox {
                border: 1px solid #e9ecef;
                border-radius: 10px;
                padding: 20px;
                margin-top: 16px;
                background-color: white;
            }
            QGroupBox::title {
                font-size: 14px;
                font-weight: 600;
                color: #2563eb;
                margin-left: 12px;
                padding: 0 8px;
            }
            QPushButton {
                padding: 8px 16px;
                border: none;
                border-radius: 6px;
                color: white;
                background-color: #409eff;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:pressed {
                background-color: #3a8ee6;
            }
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
            }
            QListWidget::item {
                padding: 10px 16px;
                border-bottom: 1px solid #f0f2f5;
                min-height: 48px;
            }
            QListWidget::item:hover {
                background-color: #f8fafc;
            }
            QListWidget::item:selected {
                background-color: #e6f7ff;
                color: #2f5496;
            }
        """)
        dialog.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        # 添加标题栏
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))

        info_group = QGroupBox("基本信息")
        info_group.setMinimumHeight(scale(200))
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(scale(12))
        
        title_layout = QHBoxLayout()
        title_layout.setSpacing(scale(10))
        title_label = QLabel("任务标题：")
        title_label.setMinimumWidth(scale(100))
        title_label.setMinimumHeight(scale(36))
        title_content = QLabel(task.get('title', '未知'))
        title_content.setWordWrap(True)
        title_content.setMinimumHeight(scale(36))
        title_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title_layout.addWidget(title_label)
        title_layout.addWidget(title_content, stretch=1)
        info_layout.addLayout(title_layout)
        
        url_layout = QHBoxLayout()
        url_layout.setSpacing(scale(10))
        url_label = QLabel("下载链接：")
        url_label.setMinimumWidth(scale(100))
        url_label.setMinimumHeight(scale(36))
        url_text = task.get('url', '')
        url_link = QLabel(f"<a href='{url_text}'>{url_text[:150]}...</a>")
        url_link.setOpenExternalLinks(True)
        url_link.setWordWrap(True)
        url_link.setMinimumHeight(scale(36))
        url_link.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        copy_url_btn = QPushButton("复制")
        copy_url_btn.setMinimumHeight(scale(32))
        copy_url_btn.setMinimumWidth(scale(80))
        copy_url_btn.setStyleSheet(scale_style("padding: 6px 12px; font-size: 12px;"))
        copy_url_btn.clicked.connect(lambda: self.copy_to_clipboard(url_text))
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_link, stretch=1)
        url_layout.addWidget(copy_url_btn)
        info_layout.addLayout(url_layout)
        
        path_layout = QHBoxLayout()
        path_layout.setSpacing(scale(10))
        path_label = QLabel("保存路径：")
        path_label.setMinimumWidth(scale(100))
        path_label.setMinimumHeight(scale(36))
        path_text = task.get('save_path', '')
        path_content = QLabel(path_text[:150] + "...")
        path_content.setToolTip(path_text)
        path_content.setWordWrap(True)
        path_content.setMinimumHeight(scale(36))
        path_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        open_path_btn = QPushButton("打开")
        open_path_btn.setMinimumHeight(scale(32))
        open_path_btn.setMinimumWidth(scale(80))
        open_path_btn.setStyleSheet(scale_style("padding: 6px 12px; font-size: 12px;"))
        open_path_btn.clicked.connect(lambda: self.open_directory(path_text))
        path_layout.addWidget(path_label)
        path_layout.addWidget(path_content, stretch=1)
        path_layout.addWidget(open_path_btn)
        info_layout.addLayout(path_layout)
        
        # 只对视频任务显示分辨率信息
        download_video = task.get("download_video", True)
        if download_video:
            qn = task.get('qn', '')
            if qn:
                qn_layout = QHBoxLayout()
                qn_layout.setSpacing(scale(10))
                qn_label = QLabel("分辨率：")
                qn_label.setMinimumWidth(scale(100))
                qn_label.setMinimumHeight(scale(36))
                qn_map = {
                    '112': '1080P60 (会员)',
                    '120': '1080P+ (会员)',
                    '125': '4K (会员)',
                    '127': '8K (会员)',
                    '80': '1080P',
                    '64': '720P',
                    '32': '480P',
                    '16': '360P'
                }
                qn_text = qn_map.get(str(qn), str(qn))
                qn_content = QLabel(qn_text)
                qn_content.setMinimumHeight(scale(36))
                qn_layout.addWidget(qn_label)
                qn_layout.addWidget(qn_content)
                info_layout.addLayout(qn_layout)
        
        # 对弹幕任务显示弹幕格式信息
        download_danmaku = task.get("download_danmaku", False)
        if download_danmaku:
            danmaku_format = task.get("danmaku_format", "XML")
            danmaku_layout = QHBoxLayout()
            danmaku_layout.setSpacing(scale(10))
            danmaku_label = QLabel("弹幕格式：")
            danmaku_label.setMinimumWidth(scale(100))
            danmaku_label.setMinimumHeight(scale(36))
            danmaku_content = QLabel(danmaku_format)
            danmaku_content.setMinimumHeight(scale(36))
            danmaku_layout.addWidget(danmaku_label)
            danmaku_layout.addWidget(danmaku_content)
            info_layout.addLayout(danmaku_layout)
        
        status_layout = QHBoxLayout()
        status_layout.setSpacing(scale(10))
        status_label = QLabel("任务状态：")
        status_label.setMinimumWidth(scale(100))
        status_label.setMinimumHeight(scale(36))
        status_map = {
                "completed": "已完成",
                "failed": "失败",
                "downloading": "下载中",
                "pending": "待处理",
                "paused": "已暂停",
                "unknown": "未知"
            }
        status_text = status_map.get(task.get('status', 'unknown'), '未知')
        status_content = QLabel(status_text)
        status_content.setMinimumHeight(scale(36))
        status_layout.addWidget(status_label)
        status_layout.addWidget(status_content)
        info_layout.addLayout(status_layout)
        
        duration = task.get('duration', '')
        if duration:
            duration_layout = QHBoxLayout()
            duration_layout.setSpacing(scale(10))
            duration_label = QLabel("下载耗时：")
            duration_label.setMinimumWidth(scale(100))
            duration_label.setMinimumHeight(scale(36))
            duration_content = QLabel(duration)
            duration_content.setMinimumHeight(scale(36))
            duration_layout.addWidget(duration_label)
            duration_layout.addWidget(duration_content)
            info_layout.addLayout(duration_layout)
        
        error_msg = task.get('error_message', '')
        if error_msg:
            error_layout = QHBoxLayout()
            error_layout.setSpacing(scale(10))
            error_label = QLabel("错误信息：")
            error_label.setMinimumWidth(scale(100))
            error_label.setMinimumHeight(scale(36))
            error_content = QLabel(error_msg[:200] + "...")
            error_content.setToolTip(error_msg)
            error_content.setStyleSheet("color: #f56c6c;")
            error_content.setWordWrap(True)
            error_content.setMinimumHeight(scale(36))
            error_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            error_layout.addWidget(error_label)
            error_layout.addWidget(error_content, stretch=1)
            info_layout.addLayout(error_layout)
        
        content_layout.addWidget(info_group)

        # 根据任务类型显示不同的标题
        download_video = task.get("download_video", True)
        download_danmaku = task.get("download_danmaku", False)
        
        if download_danmaku and not download_video:
            files_group = QGroupBox("下载弹幕")
        else:
            files_group = QGroupBox("下载文件")
        files_group.setMinimumHeight(scale(250))
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(scale(12))
        
        episodes = task.get('episodes', [])
        video_info = task.get('video_info', {})
        is_bangumi = video_info.get('is_bangumi', task.get('is_bangumi', False))
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(scale(10))
        search_label = QLabel("搜索：")
        search_label.setMinimumWidth(scale(80))
        search_label.setMinimumHeight(scale(36))
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入关键词筛选文件")
        search_edit.setMinimumHeight(scale(36))
        search_edit.textChanged.connect(lambda text: self.filter_file_list(text, episodes, task, is_bangumi))
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_edit, stretch=1)
        files_layout.addLayout(search_layout)
        
        file_list = QListWidget()
        file_list.setSelectionMode(QListWidget.SingleSelection)
        file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        files_layout.addWidget(file_list, stretch=1)
        
        file_data = []
        
        # 获取任务类型
        download_video = task.get("download_video", True)
        download_danmaku = task.get("download_danmaku", False)
        danmaku_format = task.get("danmaku_format", "XML")
        
        if episodes:
            for i, ep in enumerate(episodes):
                # 构建与下载时一致的标题格式
                if is_bangumi and task.get('video_info', {}).get('bangumi_info'):
                    season = task['video_info']['bangumi_info'].get('season_title', '未知季度')
                    ep_idx = ep.get('ep_index', '未知集')
                    title_candidates = [
                        ep.get('ep_title', ''),
                        ep.get('title', ''),
                        ep.get('name', '')
                    ]
                    actual_title = next((t for t in title_candidates if t), '')
                    if actual_title:
                        ep_title = f"{season}_{ep_idx}_{actual_title}"
                    else:
                        ep_title = f"{season}_{ep_idx}"
                    display_name = f"{ep_idx} - {actual_title}"
                else:
                    page = ep.get('page', i+1)
                    ep_title = ep.get('title', f"第{page}集")
                    display_name = f"第{page}集 - {ep_title}"
                
                # 清理标题
                clean_title = ep_title.replace("正片_", "")
                for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    clean_title = clean_title.replace(c, '_')
                clean_title = clean_title[:30]
                
                # 显示视频文件
                if download_video:
                    file_exists = False
                    try:
                        file_path = os.path.join(task.get('save_path', ''), f"{clean_title}.mp4")
                        file_exists = os.path.exists(file_path)
                    except:
                        pass
                    
                    file_item_data = {
                        'ep': ep,
                        'ep_name': f"[视频] {display_name}",
                        'file_path': file_path,
                        'file_exists': file_exists,
                        'task': task,
                        'type': 'video'
                    }
                    file_data.append(file_item_data)
                    
                    list_item = QListWidgetItem(f"[视频] {display_name}")
                    if not file_exists:
                        list_item.setFlags(list_item.flags() & ~Qt.ItemIsEnabled)
                        list_item.setForeground(QColor('#94a3b8'))
                        list_item.setToolTip("文件已被移动或删除")
                    list_item.setData(Qt.UserRole, file_item_data)
                    file_list.addItem(list_item)
                
                # 显示弹幕文件
                if download_danmaku:
                    danmaku_exists = False
                    danmaku_count = 0
                    danmaku_content = []
                    try:
                        danmaku_ext = {
                            'XML': '.xml',
                            'ASS': '.ass',
                            'SRT': '.srt',
                            'JSON': '.json'
                        }.get(danmaku_format, '.xml')
                        danmaku_path = os.path.join(task.get('save_path', ''), f"{clean_title}{danmaku_ext}")
                        danmaku_exists = os.path.exists(danmaku_path)
                        
                        # 调试信息
                        print(f"弹幕文件路径: {danmaku_path}")
                        print(f"弹幕文件是否存在: {danmaku_exists}")
                        print(f"弹幕格式: {danmaku_format}")
                        
                        # 读取弹幕文件，提取弹幕内容
                        if danmaku_exists:
                            with open(danmaku_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                print(f"弹幕文件内容长度: {len(content)}")
                                # 根据不同格式提取弹幕内容
                                if danmaku_format == 'XML':
                                    import re
                                    # 提取XML格式的弹幕内容
                                    danmaku_matches = re.findall(r'<d p=[^>]+>(.*?)</d>', content, re.DOTALL)
                                    danmaku_content = [match.strip() for match in danmaku_matches if match.strip()]
                                elif danmaku_format == 'ASS':
                                    # 提取ASS格式的弹幕内容
                                    for line in content.split('\n'):
                                        if line.strip().startswith('Dialogue:'):
                                            # 提取对话内容（ASS格式：Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text）
                                            parts = line.split(',', 9)
                                            if len(parts) > 9:
                                                danmaku_content.append(parts[9].strip())
                                elif danmaku_format == 'SRT':
                                    # 提取SRT格式的弹幕内容
                                    lines = content.split('\n')
                                    for i, line in enumerate(lines):
                                        if line.strip().isdigit() and i + 2 < len(lines):
                                            # SRT格式：序号\n时间\n内容\n\n
                                            text_line = lines[i + 2].strip()
                                            if text_line:
                                                danmaku_content.append(text_line)
                                danmaku_count = len(danmaku_content)
                                print(f"提取的弹幕数量: {danmaku_count}")
                    except Exception as e:
                        print(f"读取弹幕文件出错: {str(e)}")
                        pass
                    
                    # 构建显示内容
                    if danmaku_count > 0:
                        # 显示前3条弹幕作为预览
                        preview_lines = danmaku_content[:3]
                        preview_text = '\n'.join(preview_lines)
                        if danmaku_count > 3:
                            preview_text += f"\n... 共{danmaku_count}条弹幕"
                        display_name = f"[弹幕] {display_name}\n{preview_text}"
                    else:
                        display_name = f"[弹幕] {display_name}\n无弹幕内容"
                    
                    file_item_data = {
                        'ep': ep,
                        'ep_name': display_name,
                        'file_path': danmaku_path,
                        'file_exists': danmaku_exists,
                        'task': task,
                        'type': 'danmaku',
                        'danmaku_count': danmaku_count,
                        'danmaku_content': danmaku_content
                    }
                    file_data.append(file_item_data)
                    
                    list_item = QListWidgetItem(display_name)
                    list_item.setSizeHint(QSize(scale(0), scale(100)))  # 增加行高来显示多行内容
                    if not danmaku_exists:
                        list_item.setFlags(list_item.flags() & ~Qt.ItemIsEnabled)
                        list_item.setForeground(QColor('#94a3b8'))
                        list_item.setToolTip("文件已被移动或删除")
                    else:
                        list_item.setToolTip(f"点击查看全部弹幕内容\n包含 {danmaku_count} 条弹幕")
                    list_item.setData(Qt.UserRole, file_item_data)
                    file_list.addItem(list_item)
        else:
            file_list.addItem("无下载文件信息")
        
        self.file_list = file_list
        self.file_data = file_data
        
        content_layout.addWidget(files_group)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(12))
        if task.get('status') in ['failed', 'pending', 'paused']:
            resume_btn = QPushButton("继续下载")
            resume_btn.setMinimumHeight(scale(36))
            resume_btn.setMinimumWidth(scale(100))
            resume_btn.setStyleSheet("background-color: #52c41a; color: white;")
            resume_btn.clicked.connect(lambda: (self.resume_task(task), dialog.accept()))
            btn_layout.addWidget(resume_btn)
        
        delete_btn = QPushButton("删除任务")
        delete_btn.setMinimumHeight(scale(36))
        delete_btn.setMinimumWidth(scale(100))
        delete_btn.setStyleSheet("background-color: #f56c6c; color: white;")
        delete_btn.clicked.connect(lambda: (self.delete_task(task.get('id')), dialog.accept()))
        btn_layout.addWidget(delete_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(scale(36))
        close_btn.setMinimumWidth(scale(80))
        close_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(close_btn)
        
        btn_layout.addStretch(1)
        content_layout.addLayout(btn_layout)
        
        # 将内容区域添加到主布局
        main_layout.addWidget(content_widget)

        dialog.exec_()

    def filter_file_list(self, text, episodes, task, is_bangumi):
        self.file_list.clear()
        
        for file_data in self.file_data:
            if text.lower() in file_data['ep_name'].lower():
                list_item = QListWidgetItem(file_data['ep_name'])
                if not file_data['file_exists']:
                    list_item.setFlags(list_item.flags() & ~Qt.ItemIsEnabled)
                    list_item.setForeground(QColor('#94a3b8'))
                    list_item.setToolTip("文件已被移动或删除")
                list_item.setData(Qt.UserRole, file_data)
                self.file_list.addItem(list_item)

    def show_file_context_menu(self, position):
        item = self.file_list.itemAt(position)
        if not item:
            return
        
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return
        
        menu = QMenu()
        
        if file_data['file_exists']:
            open_action = menu.addAction("打开文件")
            open_action.triggered.connect(lambda: self.open_file(file_data['file_path']))
            
            # 为弹幕文件添加查看弹幕内容的选项
            if file_data.get('type') == 'danmaku':
                view_action = menu.addAction("查看弹幕内容")
                view_action.triggered.connect(lambda: self.view_danmaku_content(file_data['file_path']))
        
        redownload_action = menu.addAction("重新下载")
        redownload_action.triggered.connect(lambda: self.redownload_episode(file_data['ep'], file_data['task']))
        
        menu.exec_(self.file_list.mapToGlobal(position))

    def open_file(self, file_path):
        import subprocess
        try:
            if os.name == 'nt':  
                subprocess.run(['explorer', '/select,', file_path], check=False)
            elif os.name == 'posix':  
                subprocess.run(['open', file_path] if sys.platform == 'darwin' else ['xdg-open', os.path.dirname(file_path)], check=False)
        except Exception as e:
            print(f"打开文件失败：{str(e)}")
    
    def view_danmaku_content(self, file_path):
        try:
            # 解析弹幕内容
            danmaku_format = os.path.splitext(file_path)[1].lower()
            danmaku_items = []
            
            if danmaku_format == '.xml':
                import re
                # 逐行读取XML文件，避免一次性加载大文件到内存
                pattern = re.compile(r'(<d p=[^>]+>(.*?)</d>)')
                p_pattern = re.compile(r'p="([^"]+)"')
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    buffer = ''
                    i = 0
                    for line in f:
                        buffer += line
                        # 查找完整的弹幕标签
                        matches = pattern.findall(buffer)
                        if matches:
                            for full_match, text in matches:
                                # 提取p属性值
                                p_match = p_pattern.search(full_match)
                                p_value = p_match.group(1) if p_match else ''
                                danmaku_items.append({
                                    'id': i,
                                    'full_match': full_match,
                                    'text': text.strip(),
                                    'format': 'xml',
                                    'p_value': p_value
                                })
                                # 从缓冲区中移除已处理的部分
                                buffer = buffer.replace(full_match, '')
                                i += 1
            elif danmaku_format == '.ass':
                # 逐行读取ASS文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    i = 0
                    for line in f:
                        if line.strip().startswith('Dialogue:'):
                            danmaku_items.append({
                                'id': i,
                                'full_match': line.rstrip(),
                                'text': line.split(',', 9)[9].strip() if len(line.split(',', 9)) > 9 else '',
                                'format': 'ass'
                            })
                        i += 1
            elif danmaku_format == '.srt':
                # 逐行读取SRT文件
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = []
                    i = 0
                    for line in f:
                        lines.append(line.rstrip())
                        if len(lines) == 4:
                            if lines[0].strip().isdigit():
                                danmaku_items.append({
                                    'id': i,
                                    'full_match': '\n'.join(lines),
                                    'text': lines[2].strip(),
                                    'format': 'srt'
                                })
                            lines = []
                        i += 1
                    # 处理最后一组可能不完整的字幕
                    if len(lines) >= 3 and lines[0].strip().isdigit():
                        danmaku_items.append({
                            'id': i,
                            'full_match': '\n'.join(lines),
                            'text': lines[2].strip(),
                            'format': 'srt'
                        })
            
            # 创建无边框的弹幕内容查看窗口
            dialog = QDialog(self)
            dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            dialog.setAutoFillBackground(True)
            dialog.setWindowTitle("弹幕内容")
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
            else:
                dialog.setMinimumSize(scale(500), scale(400))
            
            # 添加自定义标题栏
            title_bar = QWidget()
            title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
            title_layout = QHBoxLayout(title_bar)
            title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
            title_layout.setSpacing(scale(10))
            
            title_label = QLabel("弹幕内容")
            title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
            title_layout.addWidget(title_label, stretch=1)
            
            close_btn = QPushButton("×")
            close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
            close_btn.setToolTip("关闭")
            close_btn.clicked.connect(dialog.reject)
            title_layout.addWidget(close_btn)
            
            # 添加拖拽功能
            dialog.dragging = False
            dialog.start_pos = None
            
            def mousePressEvent(event):
                try:
                    if event.button() == Qt.LeftButton and event.y() < scale(40):
                        dialog.dragging = True
                        dialog.start_pos = event.globalPos() - dialog.frameGeometry().topLeft()
                        event.accept()
                except Exception:
                    event.accept()
            
            def mouseMoveEvent(event):
                try:
                    if dialog.dragging and event.buttons() == Qt.LeftButton:
                        dialog.move(event.globalPos() - dialog.start_pos)
                        event.accept()
                except Exception:
                    pass
            
            def mouseReleaseEvent(event):
                try:
                    dialog.dragging = False
                    event.accept()
                except Exception:
                    event.accept()
            
            dialog.mousePressEvent = mousePressEvent
            dialog.mouseMoveEvent = mouseMoveEvent
            dialog.mouseReleaseEvent = mouseReleaseEvent
            
            custom_style = get_base_style() + scale_style("""
                QDialog {
                    border: 2px solid #409eff;
                    border-radius: 12px;
                    background-color: white;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
                }
                QListWidget {
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    font-family: Consolas, Monaco, 'Courier New', monospace;
                    font-size: 12px;
                    background-color: #f8fafc;
                }
                QListWidget::item {
                    padding: 10px 16px;
                    border-bottom: 1px solid #f0f2f5;
                    min-height: 48px;
                }
                QListWidget::item:hover {
                    background-color: #e6f7ff;
                }
                QListWidget::item:selected {
                    background-color: #bae6fd;
                    color: #0284c7;
                }
                QPushButton {
                    padding: 8px 16px;
                    border: none;
                    border-radius: 6px;
                    color: white;
                    background-color: #409eff;
                    font-weight: 500;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #66b1ff;
                }
                QPushButton:pressed {
                    background-color: #3a8ee6;
                }
                QPushButton#deleteBtn {
                    background-color: #f56c6c;
                }
                QPushButton#deleteBtn:hover {
                    background-color: #f78989;
                }
                QPushButton#saveBtn {
                    background-color: #52c41a;
                }
                QPushButton#saveBtn:hover {
                    background-color: #73d13d;
                }
            """)
            dialog.setStyleSheet(custom_style)
            
            # 创建布局
            main_layout = QVBoxLayout(dialog)
            main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
            main_layout.setSpacing(scale(0))
            
            # 添加标题栏
            main_layout.addWidget(title_bar)
            
            # 内容区域
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
            content_layout.setSpacing(scale(15))
            
            # 添加文件路径信息
            path_label = QLabel(f"文件路径：{file_path}")
            path_label.setWordWrap(True)
            path_label.setStyleSheet(scale_style("font-size: 12px; color: #64748b;"))
            content_layout.addWidget(path_label)
            
            # 添加弹幕数量信息
            count_label = QLabel(f"共 {len(danmaku_items)} 条弹幕")
            count_label.setStyleSheet(scale_style("font-size: 12px; color: #64748b;"))
            content_layout.addWidget(count_label)
            
            # 添加弹幕列表
            danmaku_list = QListWidget()
            danmaku_list.setSelectionMode(QListWidget.ExtendedSelection)
            danmaku_list.setContextMenuPolicy(Qt.CustomContextMenu)
            
            # 批量填充弹幕列表，优化性能
            batch_size = 100
            for i in range(0, len(danmaku_items), batch_size):
                batch_items = danmaku_items[i:i+batch_size]
                for item in batch_items:
                    list_item = QListWidgetItem(f"[{item['id']+1}] {item['text']}")
                    list_item.setData(Qt.UserRole, item)
                    danmaku_list.addItem(list_item)
            
            content_layout.addWidget(danmaku_list, stretch=1)
            
            # 添加按钮布局
            btn_layout = QHBoxLayout()
            delete_btn = QPushButton("删除选中")
            delete_btn.setObjectName("deleteBtn")
            delete_btn.setMinimumHeight(scale(36))
            delete_btn.setMinimumWidth(scale(100))
            
            save_btn = QPushButton("保存更改")
            save_btn.setObjectName("saveBtn")
            save_btn.setMinimumHeight(scale(36))
            save_btn.setMinimumWidth(scale(100))
            
            close_btn = QPushButton("关闭")
            close_btn.setMinimumHeight(scale(36))
            close_btn.setMinimumWidth(scale(80))
            close_btn.clicked.connect(dialog.reject)
            
            btn_layout.addWidget(delete_btn)
            btn_layout.addWidget(save_btn)
            btn_layout.addStretch(1)
            btn_layout.addWidget(close_btn)
            content_layout.addLayout(btn_layout)
            
            main_layout.addWidget(content_widget)
            
            # 定义删除功能
            def delete_selected():
                selected_items = danmaku_list.selectedItems()
                for item in selected_items:
                    danmaku_list.takeItem(danmaku_list.row(item))
            
            # 定义保存功能
            def save_changes():
                try:
                    # 收集剩余的弹幕
                    remaining_items = []
                    for i in range(danmaku_list.count()):
                        list_item = danmaku_list.item(i)
                        if list_item:
                            remaining_items.append(list_item.data(Qt.UserRole))
                    
                    # 重新生成文件内容
                    new_content = content
                    if danmaku_format == '.xml':
                        # 重新生成XML内容
                        import xml.etree.ElementTree as ET
                        # 解析原始XML
                        root = ET.fromstring(content)
                        # 移除所有现有的d标签
                        for d in root.findall('.//d'):
                            root.remove(d)
                        # 添加剩余的弹幕
                        for item in remaining_items:
                            ET.SubElement(root, 'd', {'p': item['p_value']}).text = item['text']
                        # 生成新的XML内容
                        new_content = ET.tostring(root, encoding='utf-8').decode('utf-8')
                    elif danmaku_format == '.ass':
                        # 重新生成ASS内容
                        lines = content.split('\n')
                        new_lines = []
                        for line in lines:
                            if not line.strip().startswith('Dialogue:'):
                                new_lines.append(line)
                        for item in remaining_items:
                            new_lines.append(item['full_match'])
                        new_content = '\n'.join(new_lines)
                    elif danmaku_format == '.srt':
                        # 重新生成SRT内容
                        new_lines = []
                        for i, item in enumerate(remaining_items, 1):
                            # 重新编号
                            parts = item['full_match'].split('\n')
                            parts[0] = str(i)
                            new_lines.extend(parts)
                            new_lines.append('')
                        new_content = '\n'.join(new_lines)
                    
                    # 保存文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    
                    self.show_notification("弹幕文件已保存", "success")
                    dialog.accept()
                except Exception as e:
                    print(f"保存弹幕文件失败：{str(e)}")
                    self.show_notification(f"保存弹幕文件失败：{str(e)}", "error")
            
            # 连接信号
            delete_btn.clicked.connect(delete_selected)
            save_btn.clicked.connect(save_changes)
            
            dialog.exec_()
        except Exception as e:
            print(f"查看弹幕内容失败：{str(e)}")
            self.show_notification(f"查看弹幕内容失败：{str(e)}", "error")

    def redownload_episode(self, episode, task):
        task_id = str(int(time.time() * 1000))
        download_params = {
            "url": task.get("url", ""),
            "video_info": task.get("video_info", {}),
            "qn": task.get("qn", ""),
            "save_path": task.get("save_path", ""),
            "episodes": [episode],
            "resume_download": True,
            "task_id": task_id,
            "download_video": task.get("download_video", True),
            "download_danmaku": task.get("download_danmaku", False),
            "danmaku_format": task.get("danmaku_format", "XML"),
            "video_format": task.get("video_format", self.config.get_app_setting("video_output_format", "mp4")),
            "audio_format": task.get("audio_format", self.config.get_app_setting("audio_output_format", "mp3")),
            "audio_quality": task.get("audio_quality", self.config.get_app_setting("audio_quality", 30280))
        }

        self.download_manager.start_download(download_params)
        
        batch_window = BatchDownloadWindow(task.get("video_info", {}), 0, self.download_manager, self.parser)
        video_info = task.get("video_info", {})
        is_bangumi = video_info.get("is_bangumi", False)
        
        if is_bangumi:
            ep_name = f"{episode.get('ep_index', '')}"
            ep_tooltip = episode.get('ep_title', '')
        else:
            ep_name = f"第{episode.get('page', 1)}集"
            ep_tooltip = episode.get('title', '')
        
        batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, 0)
        if self.download_manager:
            self.download_manager.episode_progress_updated.connect(batch_window.update_episode_progress)
            self.download_manager.episode_finished.connect(batch_window.finish_episode)
        batch_window.cancel_all.connect(lambda: self.download_manager.cancel_all())
        batch_window.window_closed.connect(lambda tid=task_id: self.on_batch_window_closed(tid))
        batch_window.show()
        
        if task_id:
            self.batch_windows[task_id] = batch_window

    def open_download_window(self, task):
        task_id = task.get("id")
        episodes = task.get("episodes", [])
        video_info = task.get("video_info", {})
        is_bangumi = video_info.get("is_bangumi", False)
        
        existing_window = None
        # 检查是否存在已有的下载窗口，不管是否可见
        if task_id and task_id in self.batch_windows:
            existing_window = self.batch_windows[task_id]
        else:
            # 如果没有对应task_id的窗口，检查是否有其他BatchDownloadWindow
            for window in self.batch_windows.values():
                if isinstance(window, BatchDownloadWindow):
                    existing_window = window
                    break
        
        if existing_window:
            for i, ep in enumerate(episodes):
                if is_bangumi:
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                existing_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
            if self.download_manager:
                self.download_manager.episode_progress_updated.connect(existing_window.update_episode_progress)
                self.download_manager.episode_finished.connect(existing_window.finish_episode)
            existing_window.show()  # 显示窗口
            existing_window.raise_()  # 确保窗口在最前面
            batch_window = existing_window
        else:
            batch_window = BatchDownloadWindow(video_info, 0, self.download_manager, self.parser)
            for i, ep in enumerate(episodes):
                if is_bangumi:
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
            batch_window.cancel_all.connect(lambda: self.download_manager.cancel_all())
            
            if self.download_manager:
                self.download_manager.episode_progress_updated.connect(batch_window.update_episode_progress)
                self.download_manager.episode_finished.connect(batch_window.finish_episode)
            
            batch_window.show()
            
            if task_id:
                self.batch_windows[task_id] = batch_window

    def on_batch_window_closed(self, task_id=None):
        if task_id and task_id in self.batch_windows:
            del self.batch_windows[task_id]

    def pause_task(self, task):
        task_id = task.get("id")
        if self.download_manager:
            self.download_manager.pause_task(task_id)
        self.refresh_task_list()

    def stop_task(self, task):
        task_id = task.get("id")
        if self.download_manager:
            self.download_manager.cancel_task(task_id)
        if self.task_manager:
            self.task_manager.update_task_status(task_id, "failed", "任务已停止")
        self.refresh_task_list()

    
    

    def toggle_maximize(self):
        
        if not self.isMaximized():
            self.showMaximized()

    def custom_close(self):
        self.hide()

    def closeEvent(self, event):
        try:
            if hasattr(self, 'timer'):
                self.timer.stop()
        except Exception:
            pass
        event.accept()


class BatchDownloadWindow(BaseWindow):
    cancel_all = pyqtSignal()
    window_closed = pyqtSignal()
    
    def __init__(self, video_info, total_episodes, download_manager=None, parser=None):
        super().__init__()
    
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setAutoFillBackground(True)
        self.video_info = video_info
        self.total_episodes = 0
        self.completed = 0
        self.failed = []
        self.episode_map = {}
        self.download_manager = download_manager
        self.parser = parser
        self.last_update_times = {}
        self.init_ui()



    def init_ui(self):
        self.setWindowTitle(f"批量下载 - 共{self.total_episodes}集")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            win_w = min(scale(800), int(sg.width() * 0.85))
            win_h = min(scale(500), int(sg.height() * 0.85))
            self.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
        else:
            self.setGeometry(scale(100), scale(100), scale(800), scale(500))
        self.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(350), int(sg.height() * 0.3)))
        
        custom_style = get_base_style() + scale_style("""
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
                background-color: white;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                min-height: 32px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                min-width: 32px;
                min-height: 32px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
                padding: 0px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """)
        self.setStyleSheet(custom_style)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(0), scale(10), scale(0))
        title_layout.setSpacing(scale(8))
        title_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        title_label = QLabel(f"批量下载 - {self.video_info.get('title', '未知视频')}")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label, stretch=1)
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        maximize_btn = QPushButton("□")
        maximize_btn.setObjectName("maximizeBtn")
        maximize_btn.clicked.connect(self.toggle_maximize)
        title_layout.addWidget(maximize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.custom_close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        content_layout.setSpacing(scale(12))

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(scale(8))
        self.scroll_area.setWidget(scroll_content)
        content_layout.addWidget(self.scroll_area, stretch=1)

        self.global_progress = QProgressBar()
        self.global_progress.setRange(0, 100)
        self.global_progress.setMinimumHeight(scale(10))
        content_layout.addWidget(self.global_progress)

        self.cancel_btn = QPushButton("取消全部下载")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setMinimumHeight(scale(32))
        self.cancel_btn.setMinimumWidth(scale(110))
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.cancel_btn)
        content_layout.addLayout(btn_layout)

        self.progress_bars = []
        self.status_labels = []
        
        main_layout.addWidget(content_widget)

    def add_episode_progress(self, ep_name, ep_tooltip, task_id=None, ep_index=None):
        group = QGroupBox(ep_name)
        group.setToolTip(ep_tooltip)
        group.setMinimumHeight(scale(60))
        group_layout = QHBoxLayout(group)
        group_layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))
        group_layout.setSpacing(scale(10))

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setMinimumHeight(scale(8))
        status = QLabel("等待下载...")
        status.setStyleSheet(scale_style("color: #6b7280; font-size: 11px;"))
        status.setMinimumHeight(scale(20))
        status.setWordWrap(True)
        
        pause_btn = QPushButton("暂停")
        pause_btn.setStyleSheet(scale_style("background-color: #faad14; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;"))
        pause_btn.clicked.connect(lambda checked, tid=task_id, eidx=ep_index: self.on_pause_resume(tid, eidx))
        
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet(scale_style("background-color: #f56c6c; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;"))
        delete_btn.clicked.connect(lambda checked, tid=task_id, eidx=ep_index: self.on_delete_task(tid, eidx))
        
        link_btn = QPushButton("查看链接")
        link_btn.setStyleSheet(scale_style("background-color: #1890ff; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 60px;"))
        link_btn.clicked.connect(lambda checked, tid=task_id, eidx=ep_index: self.on_view_links(tid, eidx))

        group_layout.addWidget(progress, stretch=1)
        group_layout.addWidget(status, stretch=1)
        group_layout.addWidget(pause_btn)
        group_layout.addWidget(delete_btn)
        group_layout.addWidget(link_btn)
        self.scroll_layout.addWidget(group)

        bar_index = len(self.progress_bars)
        self.progress_bars.append(progress)
        self.status_labels.append(status)
        self.total_episodes += 1
        self.setWindowTitle(f"批量下载 - 共{self.total_episodes}集")
        
        if task_id and ep_index is not None:
            key = f"{task_id}_{ep_index}"
            self.episode_map[key] = bar_index
            if not hasattr(self, 'pause_buttons'):
                self.pause_buttons = {}
            if not hasattr(self, 'delete_buttons'):
                self.delete_buttons = {}
            if not hasattr(self, 'link_buttons'):
                self.link_buttons = {}
            self.pause_buttons[key] = pause_btn
            self.delete_buttons[key] = delete_btn
            self.link_buttons[key] = link_btn

    def update_episode_progress(self, *args):
        try:
            self._update_episode_progress_impl(*args)
        except Exception:
            pass

    def _update_episode_progress_impl(self, *args):
        if len(args) == 4:
            task_id, ep_index, progress, status = args
            
            if hasattr(self, 'parent') and self.parent and hasattr(self.parent, 'config'):
                show_speed = self.parent.config.get_app_setting("show_download_speed", True)
                if not show_speed:
                    import re
                    status = re.sub(r'\s*\([^)]*B/s\)', '', status)
            
            key = f"{task_id}_{ep_index}"
            if key in self.episode_map:
                bar_index = self.episode_map[key]
                if 0 <= bar_index < len(self.progress_bars):
                    try:
                        import time
                        progress = max(0, min(100, float(progress)))
                        
                        current_time = time.time()
                        last_time = self.last_update_times.get(key, 0)
                        if current_time - last_time < 0.02:  
                            return
                        self.last_update_times[key] = current_time
                        
                        self.status_labels[bar_index].setText(status)
                        self.progress_bars[bar_index].setValue(int(progress))
                    except (ValueError, TypeError):
                        pass
        elif len(args) == 3:
            index, progress, status = args
            try:
                index = int(index)
                if 0 <= index < len(self.progress_bars):
                    try:
                        progress = max(0, min(100, float(progress)))
                        
                        if hasattr(self, 'last_update_time'):
                            current_time = time.time()
                            if current_time - self.last_update_time < 0.02:  
                                return
                        self.last_update_time = time.time()
                        
                        self.status_labels[index].setText(status)
                        self.progress_bars[index].setValue(int(progress))
                    except (ValueError, TypeError):
                        pass
            except ValueError:
                pass

    def on_pause_resume(self, task_id, ep_index):
        key = f"{task_id}_{ep_index}"
        if key in self.pause_buttons:
            btn = self.pause_buttons[key]
            if btn.text() == "暂停":
                btn.setText("继续")
                btn.setStyleSheet(scale_style("background-color: #52c41a; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;"))
                try:
                    if self.download_manager:
                        self.download_manager.pause_task(task_id)
                except Exception as e:
                    logger.error(f"暂停任务失败：{str(e)}")
            else:
                btn.setText("暂停")
                btn.setStyleSheet(scale_style("background-color: #faad14; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;"))
                try:
                    if self.download_manager:
                        self.download_manager.resume_task(task_id)
                        self.completed = 0
                        for i in range(len(self.status_labels)):
                            if self.status_labels[i].text().startswith("√"):
                                self.completed += 1
                        global_progress = min(100, int((self.completed / self.total_episodes) * 100)) if self.total_episodes > 0 else 0
                        self.global_progress.setValue(global_progress)
                except Exception as e:
                    logger.error(f"继续任务失败：{str(e)}")

    def on_delete_task(self, task_id, ep_index):
        try:
            if self.download_manager:
                self._cancel_task(task_id)
        except Exception as e:
            logger.error(f"取消任务失败：{str(e)}")
        
        key = f"{task_id}_{ep_index}"
        if key in self.episode_map:
            bar_index = self.episode_map[key]
            if 0 <= bar_index < len(self.progress_bars):
                group = self.progress_bars[bar_index].parentWidget()
                if group:
                    self.scroll_layout.removeWidget(group)
                    group.deleteLater()
                
                del self.progress_bars[bar_index]
                del self.status_labels[bar_index]
                
                del self.episode_map[key]
                if key in self.pause_buttons:
                    del self.pause_buttons[key]
                if key in self.delete_buttons:
                    del self.delete_buttons[key]
                if hasattr(self, 'link_buttons') and key in self.link_buttons:
                    del self.link_buttons[key]
                
                self.total_episodes = max(0, self.total_episodes - 1)
                self.setWindowTitle(f"批量下载 - 共{self.total_episodes}集")
                
                if self.total_episodes > 0:
                    global_progress = min(100, int((self.completed / self.total_episodes) * 100))
                    self.global_progress.setValue(global_progress)
                else:
                    self.global_progress.setValue(0)

    def on_view_links(self, task_id, ep_index):
        
        class LinkFetcher(QThread):
            link_ready = pyqtSignal(str, str)
            
            def __init__(self, parent, task_id, ep_index):
                super().__init__(parent)
                self.task_id = task_id
                self.ep_index = ep_index
                self.parent_window = parent
                self.ep_info = None  
            
            def run(self):
                video_url = "视频链接获取中..."
                audio_url = "音频链接获取中..."
                
                try:
                    
                    start_time = time.time()
                    timeout = 30  
                    
                    
                    parser = None
                    if hasattr(self.parent_window, 'parser') and self.parent_window.parser:
                        parser = self.parent_window.parser
                    elif hasattr(self.parent_window.parent(), 'parser') and self.parent_window.parent().parser:
                        parser = self.parent_window.parent().parser
                    
                    
                    task_info = None
                    if time.time() - start_time > timeout:
                        video_url = "获取链接失败：超时"
                        audio_url = "获取链接失败：超时"
                    elif hasattr(self.parent_window, 'download_manager') and self.parent_window.download_manager:
                        download_manager = self.parent_window.download_manager
                        if download_manager and hasattr(download_manager, 'active_tasks'):
                            try:
                                download_manager._mutex.lock()
                                task_info = download_manager.active_tasks.get(self.task_id)
                                download_manager._mutex.unlock()
                            except:
                                download_manager._mutex.unlock()
                    
                    
                    if time.time() - start_time > timeout:
                        video_url = "获取链接失败：超时"
                        audio_url = "获取链接失败：超时"
                    elif not task_info and hasattr(self.parent_window.parent(), 'download_manager'):
                        download_manager = self.parent_window.parent().download_manager
                        if download_manager and hasattr(download_manager, 'active_tasks'):
                            try:
                                download_manager._mutex.lock()
                                task_info = download_manager.active_tasks.get(self.task_id)
                                download_manager._mutex.unlock()
                            except:
                                download_manager._mutex.unlock()
                    
                    
                    if time.time() - start_time > timeout:
                        video_url = "获取链接失败：超时"
                        audio_url = "获取链接失败：超时"
                    elif not task_info:
                        
                        task_manager = None
                        if hasattr(self.parent_window, 'task_manager') and self.parent_window.task_manager:
                            task_manager = self.parent_window.task_manager
                        elif hasattr(self.parent_window.parent(), 'task_manager'):
                            task_manager = self.parent_window.parent().task_manager
                        
                        if task_manager:
                            all_tasks = task_manager.get_all_tasks()
                            for t in all_tasks:
                                if t.get('id') == self.task_id:
                                    task_info = t
                                    break
                    
                    
                    if not parser:
                        
                        if hasattr(self.parent_window, 'parser') and self.parent_window.parser:
                            parser = self.parent_window.parser
                        elif hasattr(self.parent_window.parent(), 'parser') and self.parent_window.parent().parser:
                            parser = self.parent_window.parent().parser
                    
                    if time.time() - start_time > timeout:
                        video_url = "获取链接失败：超时"
                        audio_url = "获取链接失败：超时"
                    elif task_info and parser:
                        episodes = task_info.get('episodes', [])
                        if self.ep_index < len(episodes):
                            ep_info = episodes[self.ep_index]
                            self.ep_info = ep_info  
                            bvid = ep_info.get('bvid', task_info.get('video_info', {}).get('bvid', ''))
                            cid = ep_info.get('cid', '')
                            qn = task_info.get('qn', 80)
                            
                            if bvid and cid:
                                video_info = task_info.get('video_info', {})
                                is_bangumi = video_info.get('is_bangumi', False)
                                is_cheese = video_info.get('is_cheese', False)
                                
                                if time.time() - start_time > timeout:
                                    video_url = "获取链接失败：超时"
                                    audio_url = "获取链接失败：超时"
                                elif is_bangumi:
                                    
                                    try:
                                        play_info = parser._get_play_info('bangumi', bvid, cid, False)
                                        if play_info['success']:
                                            video_urls = play_info.get('video_urls', {})
                                            selected_qn = str(qn)
                                            if selected_qn in video_urls:
                                                video_url = video_urls[selected_qn]
                                            else:
                                                for url in video_urls.values():
                                                    video_url = url
                                                    break
                                            audio_url = play_info.get('audio_url', '未获取到音频链接')
                                        else:
                                            video_url = f"获取链接失败：{play_info.get('error', '未知错误')}"
                                            audio_url = f"获取链接失败：{play_info.get('error', '未知错误')}"
                                    except Exception as e:
                                        video_url = f"获取链接失败：{str(e)}"
                                        audio_url = f"获取链接失败：{str(e)}"
                                elif is_cheese:
                                    
                                    try:
                                        season_id = ep_info.get('season_id', video_info.get('season_id', ''))
                                        ep_id = ep_info.get('ep_id', '')
                                        play_info = parser._get_play_info('cheese', bvid, cid, False, season_id=season_id, ep_id=ep_id)
                                        if play_info['success']:
                                            video_urls = play_info.get('video_urls', {})
                                            selected_qn = str(qn)
                                            if selected_qn in video_urls:
                                                video_url = video_urls[selected_qn]
                                            else:
                                                for url in video_urls.values():
                                                    video_url = url
                                                    break
                                            audio_url = play_info.get('audio_url', '未获取到音频链接')
                                        else:
                                            video_url = f"获取链接失败：{play_info.get('error', '未知错误')}"
                                            audio_url = f"获取链接失败：{play_info.get('error', '未知错误')}"
                                    except Exception as e:
                                        video_url = f"获取链接失败：{str(e)}"
                                        audio_url = f"获取链接失败：{str(e)}"
                                else:
                                    
                                    try:
                                        play_info = parser._get_play_info('video', bvid, cid, False)
                                        if play_info['success']:
                                            video_urls = play_info.get('video_urls', {})
                                            selected_qn = str(qn)
                                            if selected_qn in video_urls:
                                                video_url = video_urls[selected_qn]
                                            else:
                                                for url in video_urls.values():
                                                    video_url = url
                                                    break
                                            audio_url = play_info.get('audio_url', '未获取到音频链接')
                                        else:
                                            video_url = f"获取链接失败：{play_info.get('error', '未知错误')}"
                                            audio_url = f"获取链接失败：{play_info.get('error', '未知错误')}"
                                    except Exception as e:
                                        video_url = f"获取链接失败：{str(e)}"
                                        audio_url = f"获取链接失败：{str(e)}"
                            else:
                                video_url = "获取链接失败：缺少BV号或CID"
                                audio_url = "获取链接失败：缺少BV号或CID"
                        else:
                            video_url = "获取链接失败：剧集索引超出范围"
                            audio_url = "获取链接失败：剧集索引超出范围"
                    elif task_info:
                        video_url = "获取链接失败：解析器未初始化"
                        audio_url = "获取链接失败：解析器未初始化"
                    else:
                        video_url = "获取链接失败：任务信息不存在"
                        audio_url = "获取链接失败：任务信息不存在"
                except Exception as e:
                    logger.error(f"获取下载链接失败：{str(e)}")
                    video_url = f"获取链接失败：{str(e)}"
                    audio_url = f"获取链接失败：{str(e)}"
                
                self.link_ready.emit(video_url, audio_url)
        
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle("下载链接")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(350), int(sg.height() * 0.3)))
        else:
            dialog.setMinimumSize(scale(500), scale(350))
        
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                background-color: white;
            }
        """)
        dialog.setStyleSheet(custom_style)
        
        
        title_bar = QWidget(dialog)
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 36px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("下载链接")
        title_label.setStyleSheet(scale_style("font-weight: bold; font-size: 14px; color: white;"))
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 16px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(dialog.close)
        title_layout.addWidget(close_btn)
        
        
        dialog.dragging = False
        dialog.start_pos = None
        
        def mousePressEvent(event):
            try:
                if event.button() == Qt.LeftButton and event.y() < scale(36):
                    dialog.dragging = True
                    dialog.start_pos = event.globalPos() - dialog.frameGeometry().topLeft()
                    event.accept()
            except Exception:
                event.accept()
        
        def mouseMoveEvent(event):
            try:
                if dialog.dragging and event.buttons() == Qt.LeftButton:
                    dialog.move(event.globalPos() - dialog.start_pos)
                    event.accept()
            except Exception:
                pass
        
        def mouseReleaseEvent(event):
            try:
                dialog.dragging = False
                event.accept()
            except Exception:
                event.accept()
        
        dialog.mousePressEvent = mousePressEvent
        dialog.mouseMoveEvent = mouseMoveEvent
        dialog.mouseReleaseEvent = mouseReleaseEvent
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))
        
        title_label = QLabel(f"任务 {task_id} - 第{ep_index+1}集 下载链接")
        title_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #2563eb;"))
        content_layout.addWidget(title_label)
        
        
        
        link_list = QListWidget()
        link_list.setMinimumHeight(scale(200))
        content_layout.addWidget(link_list)
        
        
        video_item = QListWidgetItem("视频链接：获取中...")
        audio_item = QListWidgetItem("音频链接：获取中...")
        link_list.addItem(video_item)
        link_list.addItem(audio_item)
        
        hint_label = QLabel("提示：链接可能会在一段时间后失效，建议及时使用。")
        hint_label.setStyleSheet(scale_style("font-size: 12px; color: #6b7280;"))
        content_layout.addWidget(hint_label)
        
        btn_layout = QHBoxLayout()
        copy_video_btn = QPushButton("复制视频链接")
        copy_audio_btn = QPushButton("复制音频链接")
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.reject)
        
        btn_layout.addWidget(copy_video_btn)
        btn_layout.addWidget(copy_audio_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        content_layout.addLayout(btn_layout)
        
        
        main_layout.addWidget(content_widget)
        
        
        
        episodes = []
        video_info = None
        qn = 80
        
        
        parent_window = self.parent()
        if parent_window:
            
            if hasattr(parent_window, 'task_manager') and parent_window.task_manager:
                task_info = parent_window.task_manager.get_task(task_id)
                if task_info:
                    episodes = task_info.get('episodes', [])
                    video_info = task_info.get('video_info', {})
                    qn = task_info.get('qn', 80)
            
            
            if not episodes and hasattr(parent_window, 'download_manager') and parent_window.download_manager:
                download_manager = parent_window.download_manager
                if hasattr(download_manager, 'active_tasks'):
                    try:
                        download_manager._mutex.lock()
                        task_info = download_manager.active_tasks.get(task_id)
                        download_manager._mutex.unlock()
                        if task_info:
                            episodes = task_info.get('episodes', [])
                            video_info = task_info.get('video_info', {})
                            qn = task_info.get('qn', 80)
                    except Exception as e:
                        print(f"获取任务信息失败: {e}")
                        download_manager._mutex.unlock()
                
                if not episodes and hasattr(download_manager, 'task_queue'):
                    try:
                        download_manager._mutex.lock()
                        for task in download_manager.task_queue:
                            if task.get('task_id') == task_id:
                                episodes = task.get('episodes', [])
                                video_info = task.get('video_info', {})
                                qn = task.get('qn', 80)
                                break
                        download_manager._mutex.unlock()
                    except Exception as e:
                        print(f"获取队列任务信息失败: {e}")
                        download_manager._mutex.unlock()
        
        fetcher = LinkFetcher(self, task_id, ep_index)
        
        def update_links(video, audio):
            link_list.clear()
            video_item = QListWidgetItem(f"视频链接：{video}")
            audio_item = QListWidgetItem(f"音频链接：{audio}")
            link_list.addItem(video_item)
            link_list.addItem(audio_item)
            
            
            try:
                copy_video_btn.clicked.disconnect()
            except:
                pass
            copy_video_btn.clicked.connect(lambda: self.copy_to_clipboard(video))
            try:
                copy_audio_btn.clicked.disconnect()
            except:
                pass
            copy_audio_btn.clicked.connect(lambda: self.copy_to_clipboard(audio))
        
        fetcher.link_ready.connect(update_links)
        fetcher.start()
        
        
        def check_fetcher():
            if fetcher.isRunning():
                fetcher.terminate()
                link_list.clear()
                video_item = QListWidgetItem("视频链接：获取链接超时：请检查网络连接")
                audio_item = QListWidgetItem("音频链接：获取链接超时：请检查网络连接")
                link_list.addItem(video_item)
                link_list.addItem(audio_item)
        
        timer = QTimer(dialog)
        timer.timeout.connect(check_fetcher)
        timer.start(15000)  
        
        dialog.exec_()
        
        
        timer.stop()
    
    def copy_to_clipboard(self, text):
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        except Exception as e:
            logger.error(f"复制到剪贴板失败：{str(e)}")
    
    def _cancel_task(self, task_id):
        try:
            if self.download_manager:
                self.download_manager.cancel_task(task_id)
        except Exception as e:
            logger.error(f"取消任务失败：{str(e)}")

    def finish_episode(self, *args):
        try:
            self._finish_episode_impl(*args)
        except Exception:
            pass

    def _finish_episode_impl(self, *args):
        if len(args) == 4:
            task_id, ep_index, success, message = args
            if message == "TASK_PAUSED":
                return
            key = f"{task_id}_{ep_index}"
            if key in self.episode_map:
                bar_index = self.episode_map[key]
                if 0 <= bar_index < len(self.status_labels):
                    self.completed += 1
                    global_progress = min(100, int((self.completed / self.total_episodes) * 100))
                    self.global_progress.setValue(global_progress)

                    if success:
                        self.status_labels[bar_index].setText(f"√ 下载完成 - {message}")
                        self.status_labels[bar_index].setStyleSheet(scale_style("color: #52c41a; font-size: 12px;"))
                    else:
                        self.status_labels[bar_index].setText(f"× 失败：{message[:20]}...")
                        self.status_labels[bar_index].setStyleSheet(scale_style("color: #f56c6c; font-size: 12px;"))
                        self.failed.append(message)

                    all_completed = self.completed == self.total_episodes
                    if all_completed:
                        self.cancel_btn.setText("关闭窗口")
                        self.cancel_btn.clicked.disconnect()
                        self.cancel_btn.clicked.connect(self.close)

                        if self.failed:
                            msg = f"下载完成！\n成功：{self.total_episodes - len(self.failed)}集\n失败：{len(self.failed)}集"
                            parent = self.parent()
                            if parent and hasattr(parent, 'show_notification'):
                                parent.show_notification(msg, "warning")
                        else:
                            parent = self.parent()
                            if parent and hasattr(parent, 'show_notification'):
                                parent.show_notification("全部集数下载成功！", "success")
        elif len(args) == 3:
            index, success, message = args
            if message == "TASK_PAUSED":
                return
            if 0 <= index < len(self.status_labels):
                self.completed += 1
                global_progress = min(100, int((self.completed / self.total_episodes) * 100))
                self.global_progress.setValue(global_progress)

                if success:
                    self.status_labels[index].setText(f"√ 下载完成 - {message}")
                    self.status_labels[index].setStyleSheet(scale_style("color: #52c41a; font-size: 12px;"))
                else:
                    self.status_labels[index].setText(f"× 失败：{message[:20]}...")
                    self.status_labels[index].setStyleSheet(scale_style("color: #f56c6c; font-size: 12px;"))
                    self.failed.append(message)

                all_completed = self.completed == self.total_episodes
                if all_completed:
                    self.cancel_btn.setText("关闭窗口")
                    self.cancel_btn.clicked.disconnect()
                    self.cancel_btn.clicked.connect(self.close)

                    if self.failed:
                        msg = f"下载完成！\n成功：{self.total_episodes - len(self.failed)}集\n失败：{len(self.failed)}集"
                        parent = self.parent()
                        if parent and hasattr(parent, 'show_notification'):
                            parent.show_notification(msg, "warning")
                    else:
                        parent = self.parent()
                        if parent and hasattr(parent, 'show_notification'):
                            parent.show_notification("全部集数下载成功！", "success")

    def on_cancel(self):
        self.cancel_all.emit()
        self.close()

    
    

    def toggle_maximize(self):
        
        if not self.isMaximized():
            self.showMaximized()

    def custom_close(self):
        self.window_closed.emit()
        self._close_with_animation()

    def closeEvent(self, event):
        try:
            self.window_closed.emit()
            self._close_with_animation()
        except Exception:
            pass
        event.ignore()

    def _close_with_animation(self):
        
        
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


class BilibiliDownloader(BaseWindow):
    
    window_closed = pyqtSignal()
    
    def __init__(self, config, task_manager=None, download_manager=None):
        super().__init__()
        self.signal_emitter = SignalEmitter()
        self.config = config
        self.task_manager = task_manager
        self.download_manager = download_manager
        
        self.parser = None
        self.current_video_info = None
        self.cookie_file = "cookie.txt"
        self.bilibili_space = "https://space.bilibili.com/3546841002019157"
        self.batch_windows = {}
        self.cover_loaders = []  
        
        self.selected_qn = None
        self.current_danmaku_data = None
        self.selected_danmakus = []
        
        # 合并进度窗口
        self.merge_progress_windows = {}
        
        # 下载相关属性
        self.download_container_layout = None
        self.download_tasks = {}
        self.pending_progress = {}
        
        # 开发菜单相关
        self.admin_input = ""
        self.admin_code = "admincaidan"
        
        is_topmost = self.config.get_app_setting("window_topmost", False)
        if is_topmost:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        
        self.floating_ball = None
        self.floating_toolbar_enabled = self.config.get_app_setting("floating_toolbar_enabled", False)
        
        self.last_main_progress = -1
        self.last_main_status = ""
        
        # 窗口拖动相关属性
        self.dragging = False
        self.start_pos = None
        
        self.notification_widget = NotificationWidget(self)
        
        self.signal_emitter.show_notification.connect(self.show_notification)
        # 连接显示解析进度窗口的信号
        self.signal_emitter.show_parse_progress.connect(self.show_parse_progress_window)
        # 连接解析进度更新的信号
        self.signal_emitter.parse_progress.connect(self.update_parse_progress)
        self.signal_emitter.show_debug_window.connect(self.show_debug_window)
        self.signal_emitter.network_test_result.connect(self._on_network_test_result)
        self.signal_emitter.folders_loaded.connect(self._on_folders_loaded)
        self.signal_emitter.folder_content_loaded.connect(self._on_folder_content_loaded)
        self.signal_emitter.folder_error.connect(self._on_folder_error)
        self.signal_emitter.batch_parse_result.connect(self._on_batch_parse_result)
        self.signal_emitter.batch_parse_progress.connect(self._on_batch_parse_progress)
        self.signal_emitter.update_available.connect(self._on_update_available)
        self.signal_emitter.announcements_ready.connect(self._on_announcements_ready)
        
        # 在初始化 UI 之前先检查代理和网络连接
        self._check_network_before_start()
        
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
                logger.info("窗口图标使用logo.ico成功")
        except Exception as e:
            logger.error(f"设置窗口图标失败：{str(e)}")
        
        self.init_ui()
        
        # 确保主窗口能够捕获键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.window_closed.connect(self.on_window_closed)
        
        self.installEventFilter(self)
        
        QTimer.singleShot(100, self.init_background_tasks)

        from cloud_service import CloudService
        self.cloud_service = CloudService(version_info.get("version", "2.0.1"))
        QTimer.singleShot(3000, self._check_cloud_info)
        self.update_check_timer = QTimer(self)
        self.update_check_timer.timeout.connect(self._check_cloud_info)
        self.update_check_timer.start(30 * 60 * 1000)
        
        
        QTimer.singleShot(0, lambda: self.user_info_label.setText("未登录"))
        QTimer.singleShot(0, lambda: self.vip_label.setText("× 未登录"))
        QTimer.singleShot(0, lambda: self.vip_label.setStyleSheet("color: #6b7280;"))
        QTimer.singleShot(0, self.update_login_info_display)
        QTimer.singleShot(100, self.load_default_avatar)
        QTimer.singleShot(500, self.load_local_cookie)
        QTimer.singleShot(600, self.check_cookie_validity)
        
        # 连接下载管理器的合并信号
        if self.download_manager:
            if hasattr(self.download_manager, 'merge_started'):
                self.download_manager.merge_started.connect(self.on_merge_started)
            if hasattr(self.download_manager, 'merge_finished'):
                self.download_manager.merge_finished.connect(self.on_merge_finished)
    
    def mousePressEvent(self, event):
        try:
            if event.button() == Qt.LeftButton and event.y() < scale(32):
                self.dragging = True
                self.start_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
            else:
                super().mousePressEvent(event)
        except Exception:
            event.accept()
    
    def mouseMoveEvent(self, event):
        try:
            if hasattr(self, 'dragging') and self.dragging and event.buttons() == Qt.LeftButton:
                self.move(event.globalPos() - self.start_pos)
                event.accept()
            else:
                super().mouseMoveEvent(event)
        except Exception:
            pass
    
    def mouseReleaseEvent(self, event):
        try:
            self.dragging = False
            event.accept()
        except Exception:
            event.accept()
    
    def keyPressEvent(self, event):
        try:
            key = event.text()
            if key and len(key) == 1:
                self.admin_input += key
                if len(self.admin_input) > 15:
                    self.admin_input = self.admin_input[-15:]
                if len(self.admin_input) >= len(self.admin_code):
                    if self.admin_code == self.admin_input[-len(self.admin_code):]:
                        self.show_admin_menu()
                        self.admin_input = ""
            else:
                super().keyPressEvent(event)
        except Exception:
            event.ignore()
    
    def init_background_tasks(self):
        
        if self.floating_toolbar_enabled:
            self.init_floating_ball()
        
        # 在主线程中初始化系统托盘
        self.init_system_tray()
    
    def _check_cloud_info(self):
        import threading
        def _worker():
            try:
                update_info = self.cloud_service.check_update()
                if update_info.get("has_update"):
                    self.signal_emitter.update_available.emit(update_info)
            except Exception as e:
                logger.debug(f"检查更新失败: {e}")
            try:
                announcement_info = self.cloud_service.get_announcements()
                announcements = announcement_info.get("announcements", [])
                filtered = self.cloud_service.filter_announcements(announcements)
                if filtered:
                    self.signal_emitter.announcements_ready.emit(filtered)
            except Exception as e:
                logger.debug(f"获取公告失败: {e}")
        threading.Thread(target=_worker, daemon=True).start()
    
    def _on_update_available(self, update_info):
        try:
            dialog = UpdateDialog(self, update_info)
            dialog.exec_()
        except Exception as e:
            logger.error(f"显示更新对话框失败: {e}")
    
    def _on_announcements_ready(self, announcements):
        try:
            if not hasattr(self, '_announcement_bar') or self._announcement_bar is None:
                self._show_announcement_bar(announcements)
        except Exception as e:
            logger.error(f"显示公告失败: {e}")
    
    def _show_announcement_bar(self, announcements):
        if not announcements:
            return
        ann = announcements[0]
        bar = AnnouncementBar(self, ann)
        bar.closed.connect(self._on_announcement_closed)
        bar.action_triggered.connect(self._on_announcement_action)
        central = self.centralWidget()
        if central:
            layout = central.layout()
            if layout:
                layout.insertWidget(0, bar)
                self._announcement_bar = bar
                self._pending_announcements = announcements[1:]
    
    def _on_announcement_closed(self, ann_id):
        try:
            self.cloud_service.dismiss_announcement(ann_id)
        except Exception:
            pass
        if hasattr(self, '_announcement_bar') and self._announcement_bar:
            self._announcement_bar.deleteLater()
            self._announcement_bar = None
        if hasattr(self, '_pending_announcements') and self._pending_announcements:
            self._show_announcement_bar(self._pending_announcements)
    
    def _on_announcement_action(self, ann):
        action = ann.get("action", {})
        action_type = action.get("type", "none")
        if action_type == "update":
            self._check_cloud_info()
        elif action_type == "url":
            url = action.get("url", "")
            if url:
                webbrowser.open(url)
    
    def show_notification(self, message, notification_type="info"):
        print(f"显示通知：{message}，类型：{notification_type}")
        try:
            self.notification_widget.show_notification(message, notification_type)
            print("通知显示成功")
        except Exception as e:
            print(f"通知显示失败：{str(e)}")
            traceback.print_exc()
    
    def show_parse_progress_window(self):
        """显示解析进度窗口"""
        print("显示解析进度窗口")
        try:
            if not hasattr(self, 'parse_progress_window') or not self.parse_progress_window:
                print("创建解析进度窗口")
                self.parse_progress_window = ParseProgressWindow(self)
            print("显示解析进度窗口")
            self.parse_progress_window.show()
            self.parse_progress_window.raise_()
            self.parse_progress_window.activateWindow()
        except Exception:
            pass
    
    def show_debug_window(self, error_msg, code_context, file_path):
        print("显示调试窗口")
        try:
            debug_window = DebugWindow(self)
            debug_window.set_error_info(error_msg, code_context, file_path)
            debug_window.show()
            debug_window.raise_()
            debug_window.activateWindow()
            print("调试窗口显示成功")
        except Exception as e:
            print(f"调试窗口显示失败：{str(e)}")
            traceback.print_exc()
    
    def check_proxy_settings(self):
        try:
            import platform
            
            if platform.system() == 'Windows':
                # 检查Windows代理设置
                import winreg
                try:
                    internet_settings = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                                   r'SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings',
                                                   0, winreg.KEY_READ)
                    proxy_enable = winreg.QueryValueEx(internet_settings, 'ProxyEnable')[0]
                    proxy_server = winreg.QueryValueEx(internet_settings, 'ProxyServer')[0]
                    winreg.CloseKey(internet_settings)
                    
                    if proxy_enable:
                        logger.warning(f"检测到系统代理设置：{proxy_server}")
                        return True, proxy_server
                except Exception as e:
                    logger.debug(f"检查Windows代理设置失败：{str(e)}")
            
            # 检查环境变量中的代理设置
            http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
            https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
            
            if http_proxy or https_proxy:
                logger.warning(f"检测到环境变量代理设置：HTTP={http_proxy}, HTTPS={https_proxy}")
                return True, f"HTTP={http_proxy}, HTTPS={https_proxy}"
            
            return False, None
        except Exception as e:
            logger.error(f"检查代理设置失败：{str(e)}")
            return False, None
    
    def show_network_error_dialog(self, error_type, error_msg, proxy_info=None):
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowCloseButtonHint)
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle("网络错误")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            win_w = min(scale(450), int(sg.width() * 0.85))
            win_h = min(scale(250), int(sg.height() * 0.85))
            dialog.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
        else:
            dialog.setGeometry(scale(100), scale(100), scale(450), scale(250))
        
        # 自定义样式
        dialog.setStyleSheet(scale_style(""".QDialog {
            background-color: #f8f9fa;
            border-radius: 10px;
        }
        .QPushButton {
            padding: 10px 20px;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 500;
        }
        .QPushButton:hover {
            opacity: 0.9;
        }
        .QPushButton#exitBtn {
            background-color: #6c757d;
            color: white;
        }"""))
        
        layout = QVBoxLayout()
        layout.setContentsMargins(scale(30), scale(30), scale(30), scale(30))
        layout.setSpacing(scale(20))
        
        # 标题
        title_label = QLabel("网络连接错误")
        title_label.setStyleSheet(scale_style("font-size: 18px; font-weight: bold; color: #333;"))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 错误信息
        error_label = QLabel()
        error_label.setWordWrap(True)
        error_label.setStyleSheet(scale_style("font-size: 14px; color: #666;"))
        error_label.setAlignment(Qt.AlignCenter)
        
        if error_type == "proxy":
            error_text = f"检测到系统或环境变量中存在代理设置，应用不支持代理环境。\n\n当前代理：{proxy_info}\n\n请关闭代理设置后重新启动应用。"
        else:
            error_text = f"网络连接失败，应用无法正常运行。\n\n错误信息：{error_msg}\n\n请检查网络连接后重新启动应用。"
        
        error_label.setText(error_text)
        layout.addWidget(error_label)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(15))
        
        exit_btn = QPushButton("退出")
        exit_btn.setObjectName("exitBtn")
        
        btn_layout.addStretch()
        btn_layout.addWidget(exit_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        dialog.setLayout(layout)
        
        # 按钮点击事件
        def on_exit():
            dialog.reject()
        
        exit_btn.clicked.connect(on_exit)
        
        # 显示对话框
        dialog.exec_()
        return False  # 总是返回False，表示不重试
    
    def test_network_connection(self):
        try:
            from requests.exceptions import RequestException
            
            # 测试连接B站API
            test_url = "https://api.bilibili.com/x/web-interface/nav"
            response = requests.get(test_url, timeout=5)
            return True, None
        except RequestException as e:
            return False, str(e)
    
    def init_background_tasks(self):
        
        if self.floating_toolbar_enabled:
            self.init_floating_ball()
        
        # 在主线程中初始化系统托盘
        self.init_system_tray()
    
    def _check_network_before_start(self):
        
        # 检查代理设置（本地操作，非常快，保留在主线程）
        has_proxy, proxy_info = self.check_proxy_settings()
        if has_proxy:
            logger.error(f"检测到代理设置：{proxy_info}，应用不支持代理环境")
            self.show_network_error_dialog("proxy", None, proxy_info)
            sys.exit()
        
        # 网络连接测试移到后台线程，避免阻塞主线程
        import threading
        def _do_network_test():
            try:
                result = self.test_network_connection()
                self.signal_emitter.network_test_result.emit(result[0], result[1] or "")
            except Exception as e:
                self.signal_emitter.network_test_result.emit(False, str(e))
        
        thread = threading.Thread(target=_do_network_test, daemon=True)
        thread.start()
    
    def _on_network_test_result(self, success, error_msg):
        try:
            if not success:
                logger.error(f"网络连接失败：{error_msg}")
                self.show_network_error_dialog("network", error_msg)
                sys.exit()
        except Exception:
            pass
    
    def _on_folders_loaded(self, folders):
        try:
            self.update_folder_list(folders)
            self.status_label.setText("收藏夹列表刷新成功")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"更新收藏夹列表失败：{str(e)}")
    
    def _on_folder_content_loaded(self, items):
        try:
            self.update_content_list(items)
            self.status_label.setText(f"收藏内容获取成功 - 共 {len(items)} 个收藏内容")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"更新收藏内容失败：{str(e)}")
    
    def _on_folder_error(self, error_msg):
        try:
            self.show_notification(error_msg, "error")
            self.status_label.setText("就绪")
        except Exception:
            pass
    
    def _on_batch_parse_result(self, link_data, success, video_info):
        try:
            self.update_batch_parse_video_info(link_data, success, video_info)
        except Exception:
            pass
    
    def _on_batch_parse_progress(self, finished, total, message):
        try:
            if hasattr(self, 'batch_progress_bar') and self.batch_progress_bar:
                self.batch_progress_bar.setMaximum(total)
                self.batch_progress_bar.setValue(finished)
            if hasattr(self, 'batch_progress_label') and self.batch_progress_label:
                if finished >= total:
                    self.batch_progress_label.setText(f"解析完成 {total}/{total}")
                    self.batch_progress_label.setStyleSheet(scale_style("font-size: 13px; color: #52c41a;"))
                else:
                    self.batch_progress_label.setText(message)
        except Exception:
            pass
    
    def show_admin_menu(self):
        
        print("开始创建开发菜单")
        
        # 创建开发菜单窗口
        dialog = QDialog(self)
        dialog.setWindowTitle("开发者菜单")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            win_w = min(scale(500), int(sg.width() * 0.85))
            win_h = min(scale(600), int(sg.height() * 0.85))
            dialog.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
        else:
            dialog.setGeometry(scale(100), scale(100), scale(500), scale(600))
        dialog.setMinimumSize(scale(350), scale(400))
        
        # 设置窗口样式
        dialog.setStyleSheet(scale_style("""
            QDialog {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QLabel {
                font-size: 16px;
                font-weight: bold;
                color: #333333;
                margin-bottom: 20px;
            }
            QPushButton {
                background-color: #1890ff;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 14px;
                margin: 5px;
            }
            QPushButton:hover {
                background-color: #40a9ff;
            }
            QPushButton:pressed {
                background-color: #096dd9;
            }
            QPushButton#checkBtn {
                background-color: #52c41a;
            }
            QPushButton#checkBtn:hover {
                background-color: #73d13d;
            }
            QPushButton#installBtn {
                background-color: #faad14;
            }
            QPushButton#installBtn:hover {
                background-color: #ffc53d;
            }
            QPushButton#envBtn {
                background-color: #722ed1;
            }
            QPushButton#envBtn:hover {
                background-color: #9254de;
            }
        """))
        
        layout = QVBoxLayout(dialog)
        
        # 添加标题
        title_label = QLabel("开发者菜单")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 添加工具管理区域
        tool_group_label = QLabel("🛠️ 工具管理")
        tool_group_label.setStyleSheet(scale_style("font-size: 14px; color: #1890ff; margin-top: 10px;"))
        layout.addWidget(tool_group_label)
        
        # 检查工具是否存在的按钮
        check_tools_btn = QPushButton("检查工具文件")
        check_tools_btn.setObjectName("checkBtn")
        check_tools_btn.clicked.connect(self.check_tools_existence)
        layout.addWidget(check_tools_btn)
        
        # 安装工具到系统的按钮
        install_tools_btn = QPushButton("安装工具到系统")
        install_tools_btn.setObjectName("installBtn")
        install_tools_btn.clicked.connect(lambda: self.install_tools())
        layout.addWidget(install_tools_btn)
        
        # 添加环境变量的按钮
        add_env_btn = QPushButton("添加到环境变量")
        add_env_btn.setObjectName("envBtn")
        add_env_btn.clicked.connect(lambda: self.add_to_env())
        layout.addWidget(add_env_btn)
        
        # 工具管理区域的分隔线
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # 添加其他功能区域
        other_group_label = QLabel("📋 其他功能")
        other_group_label.setStyleSheet(scale_style("font-size: 14px; color: #1890ff; margin-top: 10px;"))
        layout.addWidget(other_group_label)
        
        # 测试致命错误的按钮
        test_error_btn = QPushButton("测试致命错误")
        test_error_btn.clicked.connect(self.test_fatal_error)
        layout.addWidget(test_error_btn)
        
        # 显示系统信息的按钮
        info_btn = QPushButton("显示系统信息")
        info_btn.clicked.connect(self.show_system_info)
        layout.addWidget(info_btn)
        
        # 测试Cookie的按钮
        cookie_test_btn = QPushButton("测试Cookie")
        cookie_test_btn.clicked.connect(self.show_cookie_test)
        layout.addWidget(cookie_test_btn)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        # 显示窗口
        dialog.exec_()
    
    def test_fatal_error(self):
        print("测试致命错误")
        1 / 0
    
    def show_system_info(self):
        import platform
        from PyQt5.QtCore import QT_VERSION_STR
        
        info = f"Python版本: {platform.python_version()}\n"
        info += f"系统平台: {platform.system()} {platform.release()}\n"
        info += f"Qt版本: {QT_VERSION_STR}\n"
        info += f"应用路径: {sys.executable}\n"
        
        QMessageBox.information(self, "系统信息", info)
    
    def show_cookie_test(self):
        print("显示Cookie测试对话框")
        if hasattr(self, 'parser') and self.parser:
            dialog = CookieTestDialog(self.parser, self)
            dialog.exec_()
        else:
            QMessageBox.warning(self, "错误", "parser未初始化，请重启应用")
    
    def check_tools_existence(self):
        """检查必需的工具文件是否存在"""
        print("开始检查工具文件")
        
        # 收集检查结果
        results = []
        
        # 检查FFmpeg
        results.append("=== FFmpeg 检查 ===")
        if hasattr(self, 'parser') and self.parser:
            ffmpeg_path = self.parser.ffmpeg_local
            results.append(f"FFmpeg路径: {ffmpeg_path}")
            if os.path.exists(ffmpeg_path):
                results.append(f"✅ FFmpeg存在: {ffmpeg_path}")
            else:
                results.append(f"❌ FFmpeg不存在: {ffmpeg_path}")
        else:
            results.append("❌ parser未初始化，无法检查FFmpeg")
        
        # 检查Bento4
        results.append("\n=== Bento4 检查 ===")
        if hasattr(self, 'parser') and self.parser:
            bento4_dir = self.parser.bento4_dir
            results.append(f"Bento4目录: {bento4_dir}")
            if os.path.exists(bento4_dir):
                results.append(f"✅ Bento4目录存在: {bento4_dir}")
                
                # 检查mp4decrypt.exe
                mp4decrypt_path = os.path.join(bento4_dir, 'mp4decrypt.exe')
                if os.path.exists(mp4decrypt_path):
                    results.append(f"✅ mp4decrypt.exe存在: {mp4decrypt_path}")
                else:
                    results.append(f"❌ mp4decrypt.exe不存在: {mp4decrypt_path}")
                    
                # 列出目录内容
                try:
                    files = os.listdir(bento4_dir)
                    results.append(f"目录内容: {', '.join(files) if files else '空目录'}")
                except Exception as e:
                    results.append(f"列出目录失败: {str(e)}")
            else:
                results.append(f"❌ Bento4目录不存在: {bento4_dir}")
                
                # 尝试检查其他可能的路径
                results.append("\n尝试查找其他路径:")
                import sys
                possible_paths = []
                if hasattr(sys, '_MEIPASS'):
                    possible_paths.append(os.path.join(sys._MEIPASS, 'bento4'))
                    possible_paths.append(os.path.join(sys._MEIPASS, 'bento4', 'bin'))
                    possible_paths.append(os.path.join(sys._MEIPASS, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin'))
                possible_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4'))
                possible_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', 'bin'))
                possible_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin'))
                
                for path in possible_paths:
                    if os.path.exists(path):
                        results.append(f"✅ 找到备选路径: {path}")
                        if os.path.exists(os.path.join(path, 'mp4decrypt.exe')):
                            results.append(f"   ✅ mp4decrypt.exe在备选路径中存在")
                        else:
                            results.append(f"   ❌ mp4decrypt.exe在备选路径中不存在")
                    else:
                        results.append(f"❌ 备选路径不存在: {path}")
        else:
            results.append("❌ parser未初始化，无法检查Bento4")
        
        # 检查其他可能的路径
        results.append("\n=== 系统路径检查 ===")
        import sys
        results.append(f"sys._MEIPASS: {sys._MEIPASS if hasattr(sys, '_MEIPASS') else '不存在'}")
        results.append(f"当前工作目录: {os.getcwd()}")
        results.append(f"脚本目录: {os.path.dirname(os.path.abspath(__file__))}")
        
        # 检查sys._MEIPASS目录内容
        if hasattr(sys, '_MEIPASS') and os.path.exists(sys._MEIPASS):
            results.append("\nsys._MEIPASS目录内容:")
            try:
                meipass_files = os.listdir(sys._MEIPASS)
                for f in sorted(meipass_files)[:30]:
                    results.append(f"  - {f}")
                if len(meipass_files) > 30:
                    results.append(f"  ... (还有 {len(meipass_files) - 30} 个文件)")
            except Exception as e:
                results.append(f"  列出目录失败: {str(e)}")
        
        # 显示结果
        print("\n".join(results))
        
        # 创建对话框显示结果
        dialog = QDialog(self)
        dialog.setWindowTitle("工具文件检查结果")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            win_w = min(scale(600), int(sg.width() * 0.85))
            win_h = min(scale(500), int(sg.height() * 0.85))
            dialog.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
        else:
            dialog.setGeometry(scale(100), scale(100), scale(600), scale(500))
        dialog.setMinimumSize(scale(400), scale(350))
        
        layout = QVBoxLayout(dialog)
        
        # 创建文本编辑框显示结果
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText("\n".join(results))
        text_edit.setStyleSheet(scale_style("font-family: 'Consolas', 'Monaco', monospace; font-size: 12px;"))
        layout.addWidget(text_edit)
        
        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        # 显示对话框
        dialog.exec_()
    
    def install_tools(self):
        """安装工具到系统"""
        try:
            from tool_manager import get_tool_manager
            
            tool_manager = get_tool_manager()
            paths = tool_manager.get_tool_paths()
            
            # 显示确认对话框
            confirm_dialog = QMessageBox()
            confirm_dialog.setWindowTitle("确认安装")
            confirm_dialog.setText(f"即将将工具安装到:\n{paths['install_dir']}\n\n是否继续?")
            confirm_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_dialog.setDefaultButton(QMessageBox.No)
            
            if confirm_dialog.exec_() == QMessageBox.Yes:
                # 创建进度对话框
                progress_dialog = QDialog(self)
                progress_dialog.setWindowTitle("正在安装工具")
                progress_dialog.setMinimumSize(scale(500), scale(350))
                
                progress_layout = QVBoxLayout(progress_dialog)
                
                # 安装路径信息
                path_info_label = QLabel(f"安装路径:\n{paths['install_dir']}")
                path_info_label.setAlignment(Qt.AlignCenter)
                path_info_label.setStyleSheet("font-weight: bold; color: #1890ff;")
                path_info_label.setWordWrap(True)
                progress_layout.addWidget(path_info_label)
                
                # 添加分隔线
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFrameShadow(QFrame.Sunken)
                progress_layout.addWidget(line)
                
                # 进度标签
                progress_label = QLabel("初始化...")
                progress_label.setAlignment(Qt.AlignCenter)
                progress_layout.addWidget(progress_label)
                
                # 进度条
                progress_bar = QProgressBar()
                progress_bar.setMinimum(0)
                progress_bar.setMaximum(100)
                progress_bar.setValue(0)
                progress_bar.setStyleSheet(scale_style("""
                    QProgressBar {
                        border: 2px solid #e0e0e0;
                        border-radius: 5px;
                        text-align: center;
                        min-height: 25px;
                    }
                    QProgressBar::chunk {
                        background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #1890ff, stop:1 #36cfc9);
                        border-radius: 3px;
                    }
                """))
                progress_layout.addWidget(progress_bar)
                
                # 详细日志区域
                log_label = QLabel("详细日志:")
                log_label.setStyleSheet(scale_style("font-weight: bold; margin-top: 10px;"))
                progress_layout.addWidget(log_label)
                
                log_text = QTextEdit()
                log_text.setReadOnly(True)
                log_text.setMaximumHeight(scale(120))
                log_text.setStyleSheet(scale_style("font-family: 'Consolas', 'Monaco', monospace; font-size: 11px; background-color: #f5f5f5;"))
                progress_layout.addWidget(log_text)
                
                progress_dialog.show()
                
                # 存储日志信息
                log_messages = []
                
                # 创建进度更新回调 - 使用信号槽方式确保线程安全
                class ProgressSignals(QObject):
                    update = pyqtSignal(int, str)
                
                progress_signals = ProgressSignals()
                
                def update_ui(progress, message):
                    """UI更新函数，必须在主线程调用"""
                    try:
                        progress_bar.setValue(progress)
                        progress_label.setText(message)
                        
                        # 添加到日志
                        log_messages.append(f"[{progress}%] {message}")
                        log_text.setText("\n".join(log_messages))
                        
                        # 滚动到底部
                        scrollbar = log_text.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
                    except Exception:
                        pass
                
                # 连接信号
                progress_signals.update.connect(update_ui)
                
                # 创建进度更新回调
                def progress_callback(progress, message):
                    """从子线程调用的回调"""
                    progress_signals.update.emit(progress, message)
                
                # 在后台线程中安装
                def do_install():
                    try:
                        result = tool_manager.install_tools(force=False, progress_callback=progress_callback)
                        
                        def finish():
                            self.on_install_finished(result, progress_dialog, tool_manager)
                        QTimer.singleShot(0, finish)
                    except Exception as e:
                        logger.error(f"安装过程出错: {str(e)}")
                        def error():
                            progress_dialog.close()
                            QMessageBox.critical(self, "安装失败", f"安装过程出错: {str(e)}")
                        QTimer.singleShot(0, error)
                
                import threading
                t = threading.Thread(target=do_install)
                t.daemon = True
                t.start()
                
        except ImportError:
            QMessageBox.warning(self, "错误", "工具管理器不可用")
        except Exception as e:
            logger.error(f"安装工具失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"安装工具失败: {str(e)}")
    
    def on_install_finished(self, result, progress_dialog, tool_manager):
        """安装完成的回调"""
        progress_dialog.close()
        
        if result['success']:
            msg = result['message']
            if result['ffmpeg_installed'] or result['bento4_installed']:
                msg += "\n\n是否立即重启应用以使用新安装的工具?"
                
                reply = QMessageBox.question(
                    self, "安装成功", msg,
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    import sys
                    import os
                    os.execl(sys.executable, sys.executable, *sys.argv)
            else:
                QMessageBox.information(self, "安装结果", msg)
        else:
            # 检查是否需要管理员权限
            if result.get('needs_admin', False):
                # 显示询问对话框，是否以管理员权限重新启动
                reply = QMessageBox.question(
                    self, 
                    "权限不足", 
                    f"{result['message']}\n\n是否以管理员权限重新启动程序？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 请求管理员权限
                    tool_manager.request_admin_permission()
                else:
                    QMessageBox.critical(self, "安装失败", result['message'])
            else:
                QMessageBox.critical(self, "安装失败", result['message'])
    
    def add_to_env(self):
        """添加工具到环境变量"""
        try:
            from tool_manager import get_tool_manager
            
            tool_manager = get_tool_manager()
            paths = tool_manager.get_tool_paths()
            
            # 显示确认对话框
            confirm_dialog = QMessageBox()
            confirm_dialog.setWindowTitle("确认操作")
            confirm_dialog.setText(f"即将将以下路径添加到用户环境变量PATH:\n\n{paths['ffmpeg_dir']}\n{paths['bento4_dir']}\n\n是否继续?\n\n注意: 此操作需要重新登录或重启应用才能生效")
            confirm_dialog.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            confirm_dialog.setDefaultButton(QMessageBox.No)
            
            if confirm_dialog.exec_() == QMessageBox.Yes:
                result = tool_manager.add_to_path(user_only=True)
                
                if result['success']:
                    QMessageBox.information(self, "操作成功", result['message'])
                else:
                    QMessageBox.warning(self, "操作失败", result['message'])
                    
        except ImportError:
            QMessageBox.warning(self, "错误", "工具管理器不可用")
        except Exception as e:
            logger.error(f"添加环境变量失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"添加环境变量失败: {str(e)}")
    
    def on_window_closed(self):
        try:
            if self.floating_toolbar_enabled and self.floating_ball:
                self.floating_ball.show()
                self.floating_ball.raise_()
        except Exception:
            pass
    
    def on_merge_started(self, task_id, ep_index):
        try:
            window_key = f"{task_id}_{ep_index}"
            if window_key not in self.merge_progress_windows:
                self.merge_progress_windows[window_key] = MergeProgressWindow(self)
                show_merge_window = self.config.get_app_setting("show_merge_window", False)
                if show_merge_window:
                    self.merge_progress_windows[window_key].show()
                    self.merge_progress_windows[window_key].update_progress(0, "准备合并...")
        except Exception:
            pass
    
    def on_merge_finished(self, task_id, ep_index):
        try:
            window_key = f"{task_id}_{ep_index}"
            if window_key in self.merge_progress_windows:
                window = self.merge_progress_windows[window_key]
                if window and not window.isHidden():
                    window.update_progress(100, "合并完成")
                    QTimer.singleShot(1000, window.close)
                del self.merge_progress_windows[window_key]
        except Exception:
            pass
    
    def show(self):
        
        if self.floating_toolbar_enabled and self.floating_ball:
            self.floating_ball.hide()
        
        
        super().showMaximized()
        
        self.showMaximized()
        
        self.raise_()
        self.activateWindow()
        
        self.update_progress_bar_position()
    
    def on_quality_selected(self, qn, name):
        
        if hasattr(self, 'quality_combo'):
            
            for i in range(self.quality_combo.count()):
                if self.quality_combo.itemData(i) == qn:
                    self.quality_combo.setCurrentIndex(i)
                    break
        elif hasattr(self, 'quality_btn'):
            self.quality_btn.setText(name)
        self.selected_qn = qn
    
    def on_quality_combo_changed(self, index):
        if index > 0 and hasattr(self, 'quality_combo') and self.quality_combo:
            qn = self.quality_combo.itemData(index)
            name = self.quality_combo.currentText()
            self.selected_qn = qn
    
    def eventFilter(self, obj, event):
        try:
            return bool(super().eventFilter(obj, event))
        except Exception:
            return False
    
    def init_floating_ball(self):
        if not self.floating_ball:
            
            self.floating_ball = FloatingBall(self)
            
            self.floating_ball.parent = self
            
            if hasattr(self, 'download_manager') and self.download_manager:
                
                try:
                    self.download_manager.global_progress_updated.disconnect(self.floating_ball.update_download_progress)
                except:
                    pass
                try:
                    self.download_manager.episode_progress_updated.disconnect(self.floating_ball.update_episode_progress)
                except:
                    pass
                try:
                    self.download_manager.episode_finished.disconnect(self.floating_ball.finish_episode)
                except:
                    pass
                
                self.download_manager.global_progress_updated.connect(self.floating_ball.update_download_progress)
                self.download_manager.episode_progress_updated.connect(self.floating_ball.update_episode_progress)
                self.download_manager.episode_finished.connect(self.floating_ball.finish_episode)
                print("=== 下载进度信号已连接到悬浮球 ===")
            
            if hasattr(self, 'signal_emitter'):
                print("=== 在init_floating_ball中连接parse_finished信号 ===")
                
                try:
                    self.signal_emitter.parse_finished.disconnect(self.floating_ball.on_parse_finished)
                except:
                    pass
                
                self.signal_emitter.parse_finished.connect(self.floating_ball.on_parse_finished)
                self.floating_ball.signal_connected = True
                print("=== parse_finished信号连接成功 ===")
            
            self.floating_ball.hide()
    
    def changeEvent(self, event):
        try:
            super().changeEvent(event)
            if event.type() == event.WindowStateChange:
                if self.windowState() & Qt.WindowMinimized:
                    if self.floating_toolbar_enabled and self.floating_ball:
                        self.floating_ball.show()
                        self.floating_ball.raise_()
                elif self.windowState() == Qt.WindowNoState or self.windowState() == Qt.WindowMaximized:
                    if self.floating_toolbar_enabled and self.floating_ball:
                        self.floating_ball.hide()
                    self.update_progress_bar_position()
        except Exception:
            pass
    
    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
            self.update_progress_bar_position()
        except Exception:
            pass
    
    def update_progress_bar_position(self):
        if hasattr(self, 'main_progress'):
            
            self.main_progress.setMaximumWidth(int(self.width() * 0.98))
            
            self.main_progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            if self.main_progress.parent():
                self.main_progress.parent().layout().update()
            self.main_progress.update()
    
    def toggle_floating_toolbar(self, enabled):
        self.floating_toolbar_enabled = enabled
        self.config.set_app_setting("floating_toolbar_enabled", enabled)
        if enabled:
            self.init_floating_ball()
            
            if self.floating_ball and (self.windowState() & Qt.WindowMinimized):
                
                self.floating_ball.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.WindowDoesNotAcceptFocus)
                self.floating_ball.show()
                
                self.floating_ball.raise_()
        else:
            if self.floating_ball:
                self.floating_ball.hide()
                self.floating_ball.deleteLater()
                self.floating_ball = None
    
    def update_parse_progress(self, progress, message):
        try:
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"解析进度：{progress}% - {message}")
            if hasattr(self, 'main_progress'):
                self.main_progress.setValue(progress)
            # 更新解析进度窗口的进度
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                self.parse_progress_window.update_progress(progress, message)
        except Exception as e:
            print(f"更新解析进度失败：{str(e)}")
            import traceback
            traceback.print_exc()

    def init_ui(self):
        self.setWindowTitle(f"B站视频解析工具{version_info['version']} - 作者：寒烟似雪(逸雨) QQ：2273962061/3241417097")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.setMinimumSize(max(scale(400), int(sg.width() * 0.3)), max(scale(300), int(sg.height() * 0.3)))
        else:
            self.setMinimumSize(scale(400), scale(300))
        
        custom_style = get_base_style() + scale_style("""
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
                background-color: white;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                min-height: 32px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                min-width: 32px;
                min-height: 32px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
                padding: 0px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """)
        self.setStyleSheet(custom_style)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(0), scale(10), scale(0))
        title_layout.setSpacing(scale(8))
        title_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        
        logo_label = QLabel()
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.png")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
            if os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(scale(20), scale(20), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    logo_label.setPixmap(scaled_pixmap)
                    logo_label.setFixedSize(scale(24), scale(24))
                    title_layout.addWidget(logo_label)
        except Exception as e:
            pass
        
        
        title_label = QLabel("B站视频解析下载工具")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet(scale_style("font-size: 14px;"))
        title_layout.addWidget(title_label, stretch=1)
        
        
        # 创建登录信息容器
        self.login_info_widget = QWidget()
        self.login_info_layout = QHBoxLayout(self.login_info_widget)
        self.login_info_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        self.login_info_layout.setSpacing(scale(0))  # 设置间距为0，使头像和昵称完全紧贴
        
        # 头像标签
        self.avatar_label = QLabel()
        self.avatar_label.setMinimumSize(scale(24), scale(24))
        self.avatar_label.setMaximumSize(scale(24), scale(24))
        self.avatar_label.setStyleSheet(scale_style("border-radius: 12px; background-color: #374151;"))
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.login_info_layout.addWidget(self.avatar_label)
        
        # 用户名标签
        self.login_info_label = QLabel("如果想要解析会员内容请登录")
        self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px; padding: 0px;"))
        self.login_info_label.setAlignment(Qt.AlignCenter)
        self.login_info_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        # 设置用户名标签的边距，确保与头像紧贴
        self.login_info_layout.addWidget(self.login_info_label)
        
        # 确保布局紧凑
        self.login_info_widget.adjustSize()
        
        # 设置容器属性
        self.login_info_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
        self.login_info_widget.mousePressEvent = self.on_login_click
        title_layout.addWidget(self.login_info_widget)
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.clicked.connect(self.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.custom_close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        content_layout.setSpacing(scale(15))
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(scale(10))
        header_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        
        title_label = QLabel("B站视频解析下载工具")
        title_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #2563eb;"))
        title_label.setWordWrap(True)
        title_label.setMinimumHeight(scale(32))
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        bilibili_label = QLabel("哔哩哔哩：不会玩python的man")
        bilibili_label.setObjectName("bilibiliLabel")
        bilibili_label.setStyleSheet("color: #00a1d6; text-decoration: underline;")
        bilibili_label.setCursor(QCursor(Qt.PointingHandCursor))
        bilibili_label.setWordWrap(True)
        bilibili_label.setMinimumHeight(scale(32))
        bilibili_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bilibili_label.mousePressEvent = lambda e: webbrowser.open(self.bilibili_space)
        
        self.bilibili_btn = QPushButton("访问主页")
        self.bilibili_btn.setObjectName("bilibiliBtn")
        self.bilibili_btn.setMinimumHeight(scale(28))
        self.bilibili_btn.setMinimumWidth(scale(50))
        self.bilibili_btn.setMaximumWidth(scale(120))
        self.bilibili_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.bilibili_btn.clicked.connect(lambda: webbrowser.open(self.bilibili_space))
        
        header_layout.addWidget(title_label, stretch=2)
        header_layout.addWidget(bilibili_label, stretch=1)
        header_layout.addWidget(self.bilibili_btn)
        content_layout.addLayout(header_layout)

        
        author_label = QLabel("作者：寒烟似雪(逸雨) QQ：2273962061/3241417097")
        author_label.setStyleSheet(scale_style("font-size: 10px; color: #6b7280; text-align: center;"))
        author_label.setWordWrap(True)
        author_label.setMinimumHeight(scale(28))
        author_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        content_layout.addWidget(author_label)

        
        sys_info_group = QGroupBox("系统信息")
        sys_info_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        sys_layout = QVBoxLayout(sys_info_group)
        sys_layout.setSpacing(scale(8))
        sys_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))

        
        login_layout = QHBoxLayout()
        login_layout.setSpacing(scale(8))
        login_label = QLabel("登录状态：")
        login_label.setMinimumWidth(scale(50))
        login_label.setMinimumHeight(scale(28))
        login_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.user_info_label = QLabel("加载中...")
        self.user_info_label.setWordWrap(True)
        self.user_info_label.setMinimumHeight(scale(28))
        self.user_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.vip_label = QLabel()
        self.vip_label.setMinimumHeight(scale(28))
        self.vip_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        login_layout.addWidget(login_label)
        login_layout.addWidget(self.user_info_label, stretch=1)
        login_layout.addWidget(self.vip_label)
        sys_layout.addLayout(login_layout)

        
        hevc_layout = QHBoxLayout()
        hevc_layout.setSpacing(scale(8))
        hevc_label = QLabel("HEVC支持：")
        hevc_label.setMinimumWidth(scale(50))
        hevc_label.setMinimumHeight(scale(28))
        hevc_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hevc_label = QLabel("检测中...")
        self.hevc_label.setWordWrap(True)
        self.hevc_label.setMinimumHeight(scale(28))
        self.hevc_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hevc_btn = QPushButton("安装HEVC扩展")
        self.hevc_btn.setObjectName("hevcBtn")
        self.hevc_btn.setMinimumHeight(scale(24))
        self.hevc_btn.setMinimumWidth(scale(70))
        self.hevc_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hevc_btn.setEnabled(False)
        self.hevc_btn.clicked.connect(lambda: self.signal_emitter.install_hevc.emit())
        hevc_layout.addWidget(hevc_label)
        hevc_layout.addWidget(self.hevc_label, stretch=1)
        hevc_layout.addWidget(self.hevc_btn)
        
        
        floating_layout = QHBoxLayout()
        floating_layout.setSpacing(scale(8))
        floating_label = QLabel("悬浮工具栏：")
        floating_label.setMinimumWidth(scale(50))
        floating_label.setMinimumHeight(scale(28))
        floating_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.floating_checkbox = QCheckBox()
        self.floating_checkbox.setChecked(self.floating_toolbar_enabled)
        self.floating_checkbox.setMinimumHeight(scale(28))
        self.floating_checkbox.setMinimumWidth(scale(20))
        self.floating_checkbox.stateChanged.connect(lambda state: self.toggle_floating_toolbar(state == Qt.Checked))
        floating_layout.addWidget(floating_label)
        floating_layout.addWidget(self.floating_checkbox)
        floating_layout.addStretch(1)
        
        # 添加系统详细信息
        import platform
        import subprocess
        
        # 系统信息
        system_info = platform.system()
        system_release = platform.release()
        system_version = platform.version()
        machine = platform.machine()
        processor = platform.processor()
        
        # 屏幕信息
        screen = QApplication.primaryScreen()
        if screen:
            geometry = screen.geometry()
            screen_resolution = f"{geometry.width()}x{geometry.height()}"
            dpi = screen.logicalDotsPerInch()
        else:
            screen_resolution = "未知"
            dpi = "未知"
        
        # 优化布局：自适应不同分辨率和DPI
        info_layout = QVBoxLayout()
        
        # 基础信息布局
        basic_info_layout = QHBoxLayout()
        basic_info_layout.setSpacing(scale(12))
        
        # 系统信息
        system_label = QLabel(f"系统: {system_info} {system_release} {machine}")
        system_label.setWordWrap(True)
        system_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        basic_info_layout.addWidget(system_label)
        
        # 屏幕信息
        screen_label = QLabel(f"屏幕: {screen_resolution}, DPI: {dpi}")
        screen_label.setWordWrap(True)
        screen_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        basic_info_layout.addWidget(screen_label)
        
        # 第二行信息
        secondary_info_layout = QHBoxLayout()
        secondary_info_layout.setSpacing(scale(12))
        
        # Python信息
        python_label = QLabel(f"Python: {platform.python_version()}")
        python_label.setWordWrap(True)
        python_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        secondary_info_layout.addWidget(python_label)
        
        # 处理器信息
        cpu_label = QLabel(f"处理器: {processor}")
        cpu_label.setWordWrap(True)
        cpu_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        secondary_info_layout.addWidget(cpu_label)
        
        # 添加到主布局
        info_layout.addLayout(basic_info_layout)
        info_layout.addLayout(secondary_info_layout)
        
        sys_layout.addLayout(info_layout)
        sys_layout.addLayout(floating_layout)

        content_layout.addWidget(sys_info_group)

        
        url_layout = QHBoxLayout()
        url_layout.setSpacing(scale(10))
        url_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        url_label = QLabel("视频链接：")
        url_label.setMinimumWidth(scale(50))
        url_label.setMinimumHeight(scale(36))
        url_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("支持BV/ss/av号")
        self.url_edit.setMinimumHeight(scale(36))
        self.url_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.parse_btn = QPushButton("解析")
        self.parse_btn.setMinimumHeight(scale(36))
        self.parse_btn.setMinimumWidth(scale(50))
        self.parse_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.parse_btn.clicked.connect(self.on_parse)
        self.batch_parse_btn = QPushButton("批量")
        self.batch_parse_btn.setMinimumHeight(scale(36))
        self.batch_parse_btn.setMinimumWidth(scale(50))
        self.batch_parse_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.batch_parse_btn.clicked.connect(self.on_batch_parse)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit, stretch=1)
        url_layout.addWidget(self.parse_btn)
        url_layout.addWidget(self.batch_parse_btn)
        content_layout.addLayout(url_layout)

        
        self.tv_mode_checkbox = QCheckBox("TV端无水印模式")
        self.tv_mode_checkbox.setMinimumHeight(scale(44))
        self.tv_mode_checkbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tv_mode_checkbox.setStyleSheet(scale_style("font-size: 13px;"))
        content_layout.addWidget(self.tv_mode_checkbox)



        


        
        # 创建Tab控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumHeight(scale(200))
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet(scale_style("""
            QTabWidget {
                background-color: white;
                border-radius: 8px;
            }
            QTabBar {
                background-color: #f8f9fa;
                border-bottom: 1px solid #dee2e6;
            }
            QTabBar::tab {
                background-color: #f8f9fa;
                color: #6c757d;
                padding: 10px 20px;
                border: 1px solid #dee2e6;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }
            QTabBar::tab:hover {
                background-color: #e9ecef;
                color: #495057;
            }
            QTabBar::tab:selected {
                background-color: white;
                color: #2563eb;
                border-color: #409eff;
                border-bottom-color: white;
            }
            QTabWidget::pane {
                background-color: white;
                border: 1px solid #dee2e6;
                border-top: none;
                border-radius: 0 0 8px 8px;
                padding: 10px;
            }
        """))
        
        # 视频解析标签页
        video_tab = QWidget()
        video_layout = QVBoxLayout(video_tab)
        video_layout.setSpacing(scale(15))
        video_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(scale(15))
        
        self.cover_label = QLabel()
        self.cover_label.setMinimumSize(scale(100), scale(70))
        self.cover_label.setMaximumSize(scale(200), scale(130))
        self.cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;"))
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("无封面")
        
        self.save_main_cover_btn = QPushButton("保存封面")
        self.save_main_cover_btn.setEnabled(False)
        self.save_main_cover_btn.setMinimumHeight(scale(20))
        self.save_main_cover_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #4f6ef7;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 500;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #3b5de7;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
        """))
        self.save_main_cover_btn.clicked.connect(self.on_save_main_cover)
        
        cover_v_layout = QVBoxLayout()
        cover_v_layout.setSpacing(scale(4))
        cover_v_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        cover_v_layout.addWidget(self.cover_label)
        cover_v_layout.addWidget(self.save_main_cover_btn, alignment=Qt.AlignCenter)
        
        info_layout.addLayout(cover_v_layout)
        
        info_right_layout = QVBoxLayout()
        info_right_layout.setSpacing(scale(8))
        
        title_layout = QHBoxLayout()
        title_layout.setSpacing(scale(12))
        title_label = QLabel("标题：")
        title_label.setMinimumWidth(scale(40))
        title_label.setMinimumHeight(scale(24))
        title_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.video_title = QLabel("未解析")
        self.video_title.setWordWrap(True)
        self.video_title.setMinimumHeight(scale(44))
        self.video_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_title.setStyleSheet(scale_style("font-size: 14px; font-weight: 500;"))
        title_layout.addWidget(title_label, alignment=Qt.AlignTop)
        title_layout.addWidget(self.video_title, stretch=1)
        info_right_layout.addLayout(title_layout)
        
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(scale(12))
        
        duration_label = QLabel("时长：")
        duration_label.setMinimumWidth(scale(40))
        duration_label.setMinimumHeight(scale(24))
        duration_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.duration_label = QLabel("-")
        self.duration_label.setMinimumHeight(scale(24))
        self.duration_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        type_label = QLabel("类型：")
        type_label.setMinimumWidth(scale(40))
        type_label.setMinimumHeight(scale(24))
        type_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.type_label = QLabel("未解析")
        self.type_label.setMinimumHeight(scale(24))
        self.type_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        meta_layout.addWidget(duration_label)
        meta_layout.addWidget(self.duration_label, stretch=1)
        meta_layout.addWidget(type_label)
        meta_layout.addWidget(self.type_label, stretch=1)
        info_right_layout.addLayout(meta_layout)
        
        info_layout.addLayout(info_right_layout, stretch=1)
        video_layout.addLayout(info_layout)
        
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(scale(12))
        
        # 清晰度选择
        quality_label = QLabel("清晰度：")
        quality_label.setMinimumWidth(scale(50))
        quality_label.setMinimumHeight(scale(24))
        quality_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("请选择清晰度")
        self.quality_combo.setEnabled(False)
        self.quality_combo.setMinimumHeight(scale(24))
        self.quality_combo.setMinimumWidth(scale(80))
        self.quality_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.quality_combo.setStyleSheet(scale_style("""
            QComboBox {
                padding: 4px 10px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 14px;
                min-height: 24px;
                background-color: white;
                color: #333333;
            }
            QComboBox:hover {
                border-color: #409eff;
            }
            QComboBox:focus {
                border-color: #409eff;
            }
            QComboBox:disabled {
                color: #999999;
                background-color: #f5f5f5;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 5px;
                background-color: white;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 12px;
                min-height: 36px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #f8fafc;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #e6f7ff;
                color: #0284c7;
            }
        """))
        
        # 音频质量选择
        audio_quality_label = QLabel("音质：")
        audio_quality_label.setMinimumWidth(scale(40))
        audio_quality_label.setMinimumHeight(scale(24))
        audio_quality_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        self.audio_quality_combo = QComboBox()
        self.audio_quality_combo.addItem("请选择音质")
        self.audio_quality_combo.setEnabled(False)
        self.audio_quality_combo.setMinimumHeight(scale(24))
        self.audio_quality_combo.setMinimumWidth(scale(80))
        self.audio_quality_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.audio_quality_combo.setStyleSheet(scale_style("""
            QComboBox {
                padding: 4px 10px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 14px;
                min-height: 24px;
                background-color: white;
                color: #333333;
            }
            QComboBox:hover {
                border-color: #409eff;
            }
            QComboBox:focus {
                border-color: #409eff;
            }
            QComboBox:disabled {
                color: #999999;
                background-color: #f5f5f5;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 5px;
                background-color: white;
            }
            QComboBox QAbstractItemView::item {
                padding: 10px 12px;
                min-height: 36px;
                border-radius: 4px;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #f8fafc;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #e6f7ff;
                color: #0284c7;
            }
        """))
        
        # 选择集数按钮
        self.select_episode_btn = QPushButton("选择集数")
        self.select_episode_btn.setEnabled(False)
        self.select_episode_btn.setMinimumHeight(scale(24))
        self.select_episode_btn.setMinimumWidth(scale(70))
        self.select_episode_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.select_episode_btn.clicked.connect(self.open_episode_selection)
        
        self.quality_combo.currentIndexChanged.connect(self.on_quality_combo_changed)
        
        # 添加到布局
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo, stretch=1)
        quality_layout.addWidget(audio_quality_label)
        quality_layout.addWidget(self.audio_quality_combo, stretch=1)
        quality_layout.addWidget(self.select_episode_btn)
        video_layout.addLayout(quality_layout)
        
        # 完全模式
        full_mode_layout = QHBoxLayout()
        full_mode_layout.setSpacing(scale(12))
        self.full_mode_checkbox = QCheckBox("完全模式（自动全选集数并下载）")
        self.full_mode_checkbox.setMinimumHeight(scale(36))
        self.full_mode_checkbox.setStyleSheet(scale_style("font-size: 13px;"))
        self.full_mode_checkbox.setEnabled(True)
        full_mode_layout.addWidget(self.full_mode_checkbox)
        full_mode_layout.addStretch(1)
        video_layout.addLayout(full_mode_layout)
        
        path_layout = QHBoxLayout()
        path_layout.setSpacing(scale(12))
        path_label = QLabel("保存路径：")
        path_label.setMinimumWidth(scale(50))
        path_label.setMinimumHeight(scale(44))
        path_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.path_edit = QLineEdit()
        self.path_edit.setMinimumHeight(scale(44))
        self.path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        last_path = self.config.get_app_setting("last_save_path")
        default_path = last_path if last_path else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        os.makedirs(default_path, exist_ok=True)
        self.path_edit.setText(default_path)
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setMinimumHeight(scale(44))
        self.browse_btn.setMinimumWidth(scale(50))
        self.browse_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(self.browse_btn)
        video_layout.addLayout(path_layout)
        
        # 弹幕解析标签页
        danmaku_tab = QWidget()
        danmaku_layout = QVBoxLayout(danmaku_tab)
        danmaku_layout.setSpacing(scale(15))
        danmaku_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        
        danmaku_info_group = QGroupBox("弹幕信息")
        danmaku_info_layout = QVBoxLayout(danmaku_info_group)
        danmaku_info_layout.setSpacing(scale(12))
        
        danmaku_count_layout = QHBoxLayout()
        danmaku_count_label = QLabel("弹幕数量：")
        danmaku_count_label.setMinimumWidth(scale(50))
        danmaku_count_label.setMinimumHeight(scale(24))
        self.danmaku_count_label = QLabel("未解析")
        self.danmaku_count_label.setMinimumHeight(scale(24))
        danmaku_count_layout.addWidget(danmaku_count_label)
        danmaku_count_layout.addWidget(self.danmaku_count_label, stretch=1)
        danmaku_info_layout.addLayout(danmaku_count_layout)
        
        danmaku_format_layout = QHBoxLayout()
        danmaku_format_label = QLabel("弹幕格式：")
        danmaku_format_label.setMinimumWidth(scale(50))
        danmaku_format_label.setMinimumHeight(scale(24))
        self.danmaku_format_combo = QComboBox()
        self.danmaku_format_combo.addItem("XML")
        self.danmaku_format_combo.addItem("ASS")
        self.danmaku_format_combo.addItem("JSON")
        self.danmaku_format_combo.setMinimumHeight(scale(24))
        self.danmaku_format_combo.setEnabled(False)  # 初始禁用
        danmaku_format_layout.addWidget(danmaku_format_label)
        danmaku_format_layout.addWidget(self.danmaku_format_combo, stretch=1)
        danmaku_info_layout.addLayout(danmaku_format_layout)
        
        danmaku_options_layout = QVBoxLayout()
        self.danmaku_checkbox = QCheckBox("下载弹幕")
        self.danmaku_checkbox.setMinimumHeight(scale(24))
        self.danmaku_checkbox.setStyleSheet(scale_style("font-size: 13px;"))
        self.danmaku_checkbox.setEnabled(False)  # 初始禁用
        danmaku_options_layout.addWidget(self.danmaku_checkbox)
        
        # 添加选择弹幕按钮
        self.select_danmaku_btn = QPushButton("选择弹幕")
        self.select_danmaku_btn.setMinimumHeight(scale(24))
        self.select_danmaku_btn.setMinimumWidth(scale(70))
        self.select_danmaku_btn.setEnabled(False)
        self.select_danmaku_btn.clicked.connect(self.open_danmaku_selection)
        danmaku_options_layout.addWidget(self.select_danmaku_btn)
        
        danmaku_info_layout.addLayout(danmaku_options_layout)
        
        danmaku_layout.addWidget(danmaku_info_group)
        
        # 收藏夹标签页
        favorite_tab = QWidget()
        favorite_tab.setAutoFillBackground(True)
        favorite_tab.setStyleSheet("background-color: #f0f2f5;")
        favorite_layout = QVBoxLayout(favorite_tab)
        favorite_layout.setSpacing(scale(16))
        favorite_layout.setContentsMargins(scale(16), scale(16), scale(16), scale(16))
        favorite_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 左右布局容器
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(scale(16))
        main_content_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        
        # 左侧：收藏夹列表区域
        folder_section = QWidget()
        folder_section.setAutoFillBackground(True)
        folder_section.setStyleSheet(scale_style("background-color: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);"))
        folder_section.setMinimumWidth(scale(200))
        folder_section.setMaximumWidth(scale(280))
        folder_section.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        folder_section_layout = QVBoxLayout(folder_section)
        folder_section_layout.setSpacing(scale(12))
        folder_section_layout.setContentsMargins(scale(16), scale(16), scale(16), scale(16))
        
        # 收藏夹标题和刷新按钮
        folder_header = QWidget()
        folder_header_layout = QHBoxLayout(folder_header)
        folder_header_layout.setSpacing(scale(8))
        folder_header_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        
        folder_title = QLabel("收藏夹列表")
        folder_title.setStyleSheet(scale_style("""
            QLabel {
                font-size: 16px;
                font-weight: 700;
                color: #1a1a2e;
            }
        """))
        
        self.folder_count_label = QLabel("")
        self.folder_count_label.setStyleSheet(scale_style("""
            QLabel {
                font-size: 11px;
                color: #8b95a5;
                background-color: #f0f2f5;
                border-radius: 10px;
                padding: 2px 8px;
            }
        """))
        self.folder_count_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        refresh_folder_btn = QPushButton("刷新")
        refresh_folder_btn.setMinimumHeight(scale(30))
        refresh_folder_btn.setMinimumWidth(scale(48))
        refresh_folder_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #4f6ef7;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #3b5de7;
            }
            QPushButton:pressed {
                background-color: #2a4cd6;
            }
        """))
        refresh_folder_btn.clicked.connect(self.refresh_folders)
        
        folder_header_layout.addWidget(folder_title)
        folder_header_layout.addWidget(self.folder_count_label)
        folder_header_layout.addStretch(1)
        folder_header_layout.addWidget(refresh_folder_btn)
        folder_section_layout.addWidget(folder_header)
        
        # 搜索框
        self.folder_search_edit = QLineEdit()
        self.folder_search_edit.setPlaceholderText("搜索收藏夹...")
        self.folder_search_edit.setMinimumHeight(scale(34))
        self.folder_search_edit.setStyleSheet(scale_style("""
            QLineEdit {
                border: 1px solid #e0e4ea;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 13px;
                color: #1a1a2e;
                background-color: #f7f8fa;
            }
            QLineEdit:focus {
                border: 1px solid #4f6ef7;
                background-color: white;
            }
            QLineEdit::placeholder {
                color: #b0b8c4;
            }
        """))
        self.folder_search_edit.textChanged.connect(self.on_folder_search_changed)
        folder_section_layout.addWidget(self.folder_search_edit)
        
        # 收藏夹列表
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.SingleSelection)
        self.folder_list.setMinimumHeight(scale(200))
        self.folder_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.folder_list.setStyleSheet(scale_style("""
            QListWidget {
                border: none;
                border-radius: 8px;
                background-color: transparent;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 8px;
                margin-bottom: 4px;
                font-size: 13px;
                color: #3a3f4b;
                background-color: transparent;
            }
            QListWidget::item:hover {
                background-color: #f0f4ff;
            }
            QListWidget::item:selected {
                background-color: #e8edfb;
                color: #4f6ef7;
                font-weight: 600;
            }
        """))
        self.folder_list.itemClicked.connect(self.on_folder_selected)
        folder_section_layout.addWidget(self.folder_list, stretch=1)
        
        main_content_layout.addWidget(folder_section)
        
        # 右侧：收藏内容区域
        content_section = QWidget()
        content_section.setAutoFillBackground(True)
        content_section.setStyleSheet(scale_style("background-color: white; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); z-index: 1000;"))
        content_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_section_layout = QVBoxLayout(content_section)
        content_section_layout.setSpacing(scale(12))
        content_section_layout.setContentsMargins(scale(16), scale(16), scale(16), scale(16))
        
        # 收藏内容标题
        content_title = QLabel("收藏内容")
        content_title.setStyleSheet(scale_style("""
            QLabel {
                font-size: 16px;
                font-weight: 700;
                color: #1a1a2e;
            }
        """))
        content_title.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # 操作按钮区域
        action_buttons = QWidget()
        action_buttons_layout = QHBoxLayout(action_buttons)
        action_buttons_layout.setSpacing(scale(8))
        action_buttons_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        
        select_all_btn = QPushButton("全选")
        select_all_btn.setMinimumHeight(scale(30))
        select_all_btn.setMinimumWidth(scale(48))
        select_all_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #f0f2f5;
                color: #3a3f4b;
                border: 1px solid #e0e4ea;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e4e7ec;
            }
            QPushButton:pressed {
                background-color: #d5d9e0;
            }
        """))
        select_all_btn.clicked.connect(self.on_select_all_content)
        
        clear_selection_btn = QPushButton("清空选择")
        clear_selection_btn.setMinimumHeight(scale(30))
        clear_selection_btn.setMinimumWidth(scale(48))
        clear_selection_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #f0f2f5;
                color: #3a3f4b;
                border: 1px solid #e0e4ea;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e4e7ec;
            }
            QPushButton:pressed {
                background-color: #d5d9e0;
            }
        """))
        clear_selection_btn.clicked.connect(lambda: self.content_list.clearSelection())
        
        self.download_cover_favorite_btn = QPushButton("下载选中封面")
        self.download_cover_favorite_btn.setMinimumHeight(scale(30))
        self.download_cover_favorite_btn.setMinimumWidth(scale(60))
        self.download_cover_favorite_btn.setEnabled(False)
        self.download_cover_favorite_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #f59e0b;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #d97706;
            }
            QPushButton:pressed {
                background-color: #b45309;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
        """))
        self.download_cover_favorite_btn.clicked.connect(self.on_download_selected_covers)
        
        self.parse_favorite_btn = QPushButton("解析选中")
        self.parse_favorite_btn.setMinimumHeight(scale(30))
        self.parse_favorite_btn.setMinimumWidth(scale(48))
        self.parse_favorite_btn.setEnabled(False)
        self.parse_favorite_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
        """))
        self.parse_favorite_btn.clicked.connect(self.parse_selected_content)
        
        action_buttons_layout.addWidget(select_all_btn)
        action_buttons_layout.addWidget(clear_selection_btn)
        action_buttons_layout.addWidget(self.download_cover_favorite_btn)
        action_buttons_layout.addWidget(self.parse_favorite_btn)
        
        # 标题和按钮的水平布局
        title_and_buttons = QWidget()
        title_and_buttons_layout = QHBoxLayout(title_and_buttons)
        title_and_buttons_layout.setSpacing(scale(12))
        title_and_buttons_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        title_and_buttons_layout.addWidget(content_title)
        title_and_buttons_layout.addStretch(1)
        title_and_buttons_layout.addWidget(action_buttons)
        content_section_layout.addWidget(title_and_buttons)
        
        # 收藏内容列表（卡片模式）
        self.content_list = QListWidget()
        self.content_list.setViewMode(QListWidget.IconMode)
        self.content_list.setResizeMode(QListWidget.Adjust)
        self.content_list.setFlow(QListWidget.LeftToRight)
        self.content_list.setSpacing(scale(8))
        self.content_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.content_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_list.setWrapping(True)
        self.content_list.setWordWrap(True)
        self.content_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.content_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_list._card_width = scale(190)
        self.content_list._card_height = scale(160)
        self.content_list.setStyleSheet(scale_style("""
            QListWidget {
                border: none;
                border-radius: 8px;
                background-color: #f7f8fa;
                padding: 12px;
                z-index: 1000;
                outline: none;
            }
            QListWidget::item {
                border: none;
                background: transparent;
                border-radius: 10px;
                z-index: 1000;
            }
            QListWidget::item:hover {
                background: transparent;
                z-index: 1000;
            }
            QListWidget::item:selected {
                background: transparent;
                z-index: 1000;
            }
            QScrollBar:vertical {
                min-width: 6px;
                background: transparent;
                border-radius: 3px;
                margin: 4px 0;
            }
            QScrollBar::handle:vertical {
                background: #d0d5dd;
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #b0b8c4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """))
        self.content_list.itemDoubleClicked.connect(self.on_content_double_clicked)
        self.content_list.itemClicked.connect(self.on_content_clicked)
        
        # 使用QScrollArea确保完整的滚动功能
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none; z-index: 1000;")
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建一个容器widget来容纳内容列表
        scroll_container = QWidget()
        scroll_container.setStyleSheet("z-index: 1000;")
        scroll_layout = QVBoxLayout(scroll_container)
        scroll_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        scroll_layout.addWidget(self.content_list)
        
        scroll_area.setWidget(scroll_container)
        content_section_layout.addWidget(scroll_area, stretch=1)
        
        # 确保内容区域置顶
        content_section.raise_()
        scroll_area.raise_()
        self.content_list.raise_()
        
        main_content_layout.addWidget(content_section, stretch=1)
        
        favorite_layout.addLayout(main_content_layout, stretch=1)
        
        # 封面下载标签页
        cover_tab = QWidget()
        cover_tab.setAutoFillBackground(True)
        cover_tab.setStyleSheet("background-color: #f0f2f5;")
        cover_layout = QVBoxLayout(cover_tab)
        cover_layout.setSpacing(scale(4))
        cover_layout.setContentsMargins(scale(6), scale(6), scale(6), scale(6))
        cover_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        cover_main_splitter = QSplitter(Qt.Vertical)
        cover_main_splitter.setStyleSheet(scale_style("""
            QSplitter::handle {
                background-color: #e0e4ea;
                height: 2px;
            }
        """))
        
        preview_section = QWidget()
        preview_section.setAutoFillBackground(True)
        preview_section.setStyleSheet(scale_style("background-color: white; border-radius: 6px;"))
        preview_section_layout = QVBoxLayout(preview_section)
        preview_section_layout.setSpacing(scale(4))
        preview_section_layout.setContentsMargins(scale(6), scale(6), scale(6), scale(6))
        
        preview_header = QWidget()
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setSpacing(scale(4))
        preview_header_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        
        preview_title = QLabel("封面预览")
        preview_title.setStyleSheet(scale_style("""
            QLabel {
                font-size: 11px;
                font-weight: 600;
                color: #1a1a2e;
            }
        """))
        
        self.save_cover_btn = QPushButton("保存封面")
        self.save_cover_btn.setMinimumHeight(scale(22))
        self.save_cover_btn.setEnabled(False)
        self.save_cover_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #4f6ef7;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 500;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #3b5de7;
            }
            QPushButton:pressed {
                background-color: #2a4cd6;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
        """))
        self.save_cover_btn.clicked.connect(self.on_save_cover)
        
        self.batch_download_cover_btn = QPushButton("批量下载封面")
        self.batch_download_cover_btn.setMinimumHeight(scale(22))
        self.batch_download_cover_btn.setEnabled(False)
        self.batch_download_cover_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 10px;
                font-weight: 500;
                padding: 3px 8px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
            QPushButton:pressed {
                background-color: #047857;
            }
            QPushButton:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
        """))
        self.batch_download_cover_btn.clicked.connect(self.on_batch_download_covers)
        
        preview_header_layout.addWidget(preview_title)
        preview_header_layout.addStretch(1)
        preview_header_layout.addWidget(self.save_cover_btn)
        preview_header_layout.addWidget(self.batch_download_cover_btn)
        preview_section_layout.addWidget(preview_header)
        
        self.cover_preview_label = QLabel("请先解析视频以获取封面")
        self.cover_preview_label.setAlignment(Qt.AlignCenter)
        self.cover_preview_label.setMinimumHeight(scale(120))
        self.cover_preview_label.setStyleSheet(scale_style("""
            QLabel {
                background-color: #f7f8fa;
                border: 1px dashed #d0d5dd;
                border-radius: 6px;
                color: #8b95a5;
                font-size: 10px;
            }
        """))
        self.cover_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cover_preview_label.setScaledContents(False)
        preview_section_layout.addWidget(self.cover_preview_label, stretch=1)
        
        cover_main_splitter.addWidget(preview_section)
        
        cover_list_section = QWidget()
        cover_list_section.setAutoFillBackground(True)
        cover_list_section.setStyleSheet(scale_style("background-color: white; border-radius: 6px;"))
        cover_list_section_layout = QVBoxLayout(cover_list_section)
        cover_list_section_layout.setSpacing(scale(4))
        cover_list_section_layout.setContentsMargins(scale(6), scale(6), scale(6), scale(6))
        
        cover_list_header = QLabel("封面列表")
        cover_list_header.setStyleSheet(scale_style("""
            QLabel {
                font-size: 11px;
                font-weight: 600;
                color: #1a1a2e;
            }
        """))
        cover_list_section_layout.addWidget(cover_list_header)
        
        self.cover_list_widget = QListWidget()
        self.cover_list_widget.setViewMode(QListWidget.IconMode)
        self.cover_list_widget.setResizeMode(QListWidget.Adjust)
        self.cover_list_widget.setFlow(QListWidget.LeftToRight)
        self.cover_list_widget.setSpacing(scale(4))
        self.cover_list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.cover_list_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.cover_list_widget.setWrapping(True)
        self.cover_list_widget.setWordWrap(True)
        self.cover_list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.cover_list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cover_list_widget.setMinimumHeight(scale(80))
        self.cover_list_widget.setStyleSheet(scale_style("""
            QListWidget {
                border: none;
                border-radius: 6px;
                background-color: #f7f8fa;
                padding: 4px;
                outline: none;
            }
            QListWidget::item {
                border: none;
                background: transparent;
                border-radius: 6px;
            }
            QListWidget::item:hover {
                background: transparent;
            }
            QListWidget::item:selected {
                background: transparent;
                border: 2px solid #4f6ef7;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                min-width: 5px;
                background: transparent;
                border-radius: 2px;
                margin: 2px 0;
            }
            QScrollBar::handle:vertical {
                background: #d0d5dd;
                border-radius: 2px;
                min-height: 16px;
            }
            QScrollBar::handle:vertical:hover {
                background: #b0b8c4;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """))
        self.cover_list_widget.itemClicked.connect(self.on_cover_list_item_clicked)
        cover_list_section_layout.addWidget(self.cover_list_widget)
        
        cover_main_splitter.addWidget(cover_list_section)
        cover_main_splitter.setSizes([scale(180), scale(100)])
        
        cover_layout.addWidget(cover_main_splitter, stretch=1)
        
        self.cover_data_list = []
        self.current_cover_pixmap = None
        
        self.tab_widget.addTab(video_tab, "视频解析")
        self.tab_widget.addTab(danmaku_tab, "弹幕解析")
        self.tab_widget.addTab(favorite_tab, "收藏夹")
        self.tab_widget.addTab(cover_tab, "封面下载")
        
        # 连接标签页切换信号
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # 为tab_widget设置合适的大小策略
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.tab_widget, stretch=1)

        
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(scale(12))
        progress_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        self.main_progress = QProgressBar()
        self.main_progress.setRange(0, 100)
        self.main_progress.setMinimumHeight(scale(14))
        self.main_progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        progress_layout.addWidget(self.main_progress)
        self.status_label = QLabel("就绪 - 请输入链接并解析")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(scale(44))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet(scale_style("font-size: 11px;"))
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress_layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        
        content_layout.addLayout(progress_layout)

        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(15))
        btn_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setEnabled(False)
        self.download_btn.setMinimumHeight(scale(44))
        self.download_btn.setMinimumWidth(scale(80))
        self.download_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.download_btn.clicked.connect(self.on_download)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(scale(44))
        self.cancel_btn.setMinimumWidth(scale(50))
        self.cancel_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.cancel_btn.clicked.connect(self.on_cancel_download)
        self.task_manager_btn = QPushButton("任务")
        self.task_manager_btn.setStyleSheet("background-color: #722ed1;")
        self.task_manager_btn.setMinimumHeight(scale(44))
        self.task_manager_btn.setMinimumWidth(scale(50))
        self.task_manager_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.task_manager_btn.clicked.connect(self.open_task_manager)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setStyleSheet("background-color: #94a3b8;")
        self.settings_btn.setMinimumHeight(scale(44))
        self.settings_btn.setMinimumWidth(scale(50))
        self.settings_btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.open_settings)
        
        btn_layout.addStretch(2)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.task_manager_btn)
        btn_layout.addWidget(self.settings_btn)
        content_layout.addLayout(btn_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area, stretch=1)

        self.signal_emitter.user_info_updated.connect(self.update_user_info)
        self.signal_emitter.hevc_checked.connect(self.update_hevc_status)
        self.signal_emitter.hevc_download_progress.connect(self.update_hevc_progress)
        self.signal_emitter.hevc_install_finished.connect(self.on_hevc_install_finish)
        self.signal_emitter.parse_finished.connect(self.on_parse_finished)
        self.signal_emitter.cookie_verified.connect(self.on_cookie_verified)
        self.signal_emitter.download_progress.connect(self.update_download_progress)
        self.signal_emitter.show_space_videos.connect(self.on_show_space_videos)
        self.signal_emitter.avatar_loaded.connect(self.on_avatar_loaded)

        self.selected_episodes = []

    def load_local_cookie(self):
        cookie_path = self.cookie_file
        if hasattr(self, 'parser') and self.parser and hasattr(self.parser, 'cookie_path'):
            cookie_path = self.parser.cookie_path
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, "r", encoding="utf-8") as f:
                    cookie = f.read().strip()
                    if cookie:
                        
                        if hasattr(self, 'parser') and self.parser:
                            
                            self.parser.save_cookies(cookie)
            except Exception as e:
                logger.error(f"本地Cookie读取失败：{str(e)[:15]}")
        
        
        import threading
        def verify_cookie_in_thread():
            try:
                if hasattr(self, 'parser') and self.parser and self.parser.cookies:
                    success, msg = self.parser.verify_cookie()
                    self.signal_emitter.cookie_verified.emit(success, msg)
                else:
                    self.signal_emitter.cookie_verified.emit(False, "无Cookie")
            except Exception as e:
                logger.error(f"检查cookie有效性失败：{str(e)}")
                self.signal_emitter.cookie_verified.emit(False, str(e))
        
        thread = threading.Thread(target=verify_cookie_in_thread)
        thread.daemon = True
        thread.start()
    
    def refresh_folders(self):
        if not self.parser:
            self.show_notification("解析器未初始化", "error")
            return
        
        if not self.parser.cookies:
            self.show_notification("请先登录", "warning")
            return
        
        self.status_label.setText("正在获取收藏夹列表...")
        
        # 清空内容列表并显示骨架屏
        def clear_content_and_show_skeleton():
            if hasattr(self, 'content_list'):
                # 清空内容列表
                self.content_list.clear()
                
                # 显示骨架屏
                for i in range(12):  # 显示12个骨架屏
                    skeleton_widget = QWidget()
                    skeleton_widget.setMinimumSize(scale(150), scale(130))
                    skeleton_layout = QVBoxLayout()
                    
                    # 骨架屏样式
                    skeleton_style = """
                        QWidget {
                            background-color: #f3f4f6;
                            border-radius: 8px;
                        }
                    """
                    
                    cover_skeleton = QWidget()
                    cover_skeleton.setMinimumSize(scale(150), scale(85))
                    cover_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(cover_skeleton, alignment=Qt.AlignCenter)
                    
                    # 标题骨架
                    skeleton_layout.addSpacing(15)
                    title_skeleton = QWidget()
                    title_skeleton.setMinimumSize(scale(160), scale(16))
                    title_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(title_skeleton, alignment=Qt.AlignCenter)
                    
                    # UP主骨架
                    skeleton_layout.addSpacing(8)
                    up_skeleton = QWidget()
                    up_skeleton.setMinimumSize(scale(100), scale(12))
                    up_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(up_skeleton, alignment=Qt.AlignCenter)
                    
                    # 时长骨架
                    duration_skeleton = QWidget()
                    duration_skeleton.setMinimumSize(scale(60), scale(12))
                    duration_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(duration_skeleton, alignment=Qt.AlignCenter)
                    
                    skeleton_widget.setLayout(skeleton_layout)
                    
                    # 创建列表项并设置大小
                    skeleton_item = QListWidgetItem()
                    skeleton_item.setSizeHint(QSize(scale(190), scale(160)))
                    
                    # 添加到列表
                    self.content_list.addItem(skeleton_item)
                    self.content_list.setItemWidget(skeleton_item, skeleton_widget)
                
        # 在主线程中执行
        QTimer.singleShot(0, clear_content_and_show_skeleton)
        
        import threading
        def get_folders():
            try:
                folders = self.parser.get_user_folders()
                logger.info(f"获取到 {len(folders)} 个收藏夹，准备更新UI")
                self.signal_emitter.folders_loaded.emit(folders)
            except Exception as e:
                traceback.print_exc()
                logger.error(f"获取收藏夹失败：{str(e)}")
                self.signal_emitter.folder_error.emit(f"获取收藏夹失败：{str(e)}")
        
        thread = threading.Thread(target=get_folders)
        thread.daemon = True
        thread.start()
    
    def update_folder_list(self, folders):
        logger.info(f"更新收藏夹列表，接收到 {len(folders)} 个收藏夹")
        
        if not hasattr(self, 'folder_list'):
            logger.error("folder_list不存在")
            return
        
        self.folder_list.clear()
        
        if hasattr(self, 'folder_count_label'):
            self.folder_count_label.setText(str(len(folders)))
        
        if not folders:
            logger.info("收藏夹列表为空")
            empty_item = QListWidgetItem("无收藏夹")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsSelectable)
            empty_item.setForeground(QColor('#8b95a5'))
            self.folder_list.addItem(empty_item)
            
            if hasattr(self, 'content_list'):
                self.content_list.clear()
                empty_content_item = QListWidgetItem("无收藏夹")
                empty_content_item.setFlags(empty_content_item.flags() & ~Qt.ItemIsSelectable)
                empty_content_item.setForeground(QColor('#8b95a5'))
                self.content_list.addItem(empty_content_item)
            
            if hasattr(self, 'parse_favorite_btn'):
                self.parse_favorite_btn.setEnabled(False)
            if hasattr(self, 'download_cover_favorite_btn'):
                self.download_cover_favorite_btn.setEnabled(False)
        else:
            logger.info(f"开始添加 {len(folders)} 个收藏夹到列表")
            for i, folder in enumerate(folders):
                title = folder.get('title', '未知收藏夹')
                count = folder.get('media_count', 0)
                folder_id = folder.get('id')
                logger.info(f"收藏夹 {i+1}: {title}, ID: {folder_id}, 内容数: {count}")
                
                item_widget = QWidget()
                item_widget.setAutoFillBackground(True)
                item_widget.setObjectName(f"folder_item_{i}")
                item_widget.setStyleSheet(scale_style(f"""
                    QWidget#folder_item_{i} {{
                        background-color: white;
                        border: 1px solid #e8ecf1;
                        border-radius: 8px;
                    }}
                    QWidget#folder_item_{i}:hover {{
                        background-color: #f8f9fc;
                        border: 1px solid #c7cdd6;
                    }}
                """))
                item_layout = QVBoxLayout(item_widget)
                item_layout.setContentsMargins(scale(12), scale(8), scale(12), scale(8))
                item_layout.setSpacing(scale(4))
                
                name_label = QLabel(title)
                name_label.setStyleSheet(scale_style("""
                    QLabel {
                        font-size: 14px;
                        font-weight: 600;
                        color: #1a1a2e;
                        background: transparent;
                    }
                """))
                name_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                
                bottom_layout = QHBoxLayout()
                bottom_layout.setSpacing(scale(6))
                
                count_label = QLabel(str(count) + " 个内容")
                count_label.setStyleSheet(scale_style("""
                    QLabel {
                        font-size: 11px;
                        color: #8b95a5;
                        background-color: #f0f2f5;
                        border-radius: 10px;
                        padding: 2px 8px;
                    }
                """))
                count_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
                
                id_label = QLabel("ID: " + str(folder_id))
                id_label.setStyleSheet(scale_style("""
                    QLabel {
                        font-size: 10px;
                        color: #b0b8c4;
                        background: transparent;
                    }
                """))
                id_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
                
                bottom_layout.addWidget(count_label)
                bottom_layout.addWidget(id_label)
                bottom_layout.addStretch(1)
                
                item_layout.addWidget(name_label)
                item_layout.addLayout(bottom_layout)
                
                list_item = QListWidgetItem()
                list_item.setData(Qt.UserRole, folder_id)
                list_item.setData(Qt.UserRole + 1, title)
                list_item.setSizeHint(QSize(scale(200), scale(80)))
                
                self.folder_list.addItem(list_item)
                self.folder_list.setItemWidget(list_item, item_widget)
            
            if folders:
                logger.info("选中第一个收藏夹并显示内容")
                self.folder_list.setCurrentRow(0)
                first_item = self.folder_list.item(0)
                if first_item:
                    logger.info("选中第一个收藏夹")
                    self.on_folder_selected(first_item)
        
        logger.info("收藏夹列表更新完成")
    
    def on_folder_selected(self, item):
        from functools import partial
        
        logger = logging.getLogger(__name__)
        logger.info("on_folder_selected方法被调用")
        
        folder_id = item.data(Qt.UserRole)
        logger.info(f"获取到folder_id: {folder_id}")
        
        if not folder_id:
            logger.error("folder_id为空，返回")
            return
        
        logger.info("更新状态标签为'正在获取收藏内容...'")
        self.status_label.setText("正在获取收藏内容...")
        
        # 清空内容列表并显示骨架屏
        def clear_content_and_show_skeleton():
            if hasattr(self, 'content_list'):
                # 清空内容列表
                self.content_list.clear()
                
                # 显示骨架屏
                for i in range(12):  # 显示12个骨架屏
                    skeleton_widget = QWidget()
                    skeleton_widget.setMinimumSize(scale(190), scale(150))
                    skeleton_layout = QVBoxLayout()
                    
                    skeleton_style = """
                        QWidget {
                            background-color: #f3f4f6;
                            border-radius: 8px;
                        }
                    """
                    
                    cover_skeleton = QWidget()
                    cover_skeleton.setMinimumSize(scale(180), scale(100))
                    cover_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(cover_skeleton, alignment=Qt.AlignCenter)
                    
                    # 标题骨架
                    skeleton_layout.addSpacing(15)
                    title_skeleton = QWidget()
                    title_skeleton.setMinimumSize(scale(160), scale(16))
                    title_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(title_skeleton, alignment=Qt.AlignCenter)
                    
                    # UP主骨架
                    skeleton_layout.addSpacing(8)
                    up_skeleton = QWidget()
                    up_skeleton.setMinimumSize(scale(100), scale(12))
                    up_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(up_skeleton, alignment=Qt.AlignCenter)
                    
                    # 时长骨架
                    duration_skeleton = QWidget()
                    duration_skeleton.setMinimumSize(scale(60), scale(12))
                    duration_skeleton.setStyleSheet(skeleton_style)
                    skeleton_layout.addWidget(duration_skeleton, alignment=Qt.AlignCenter)
                    
                    skeleton_widget.setLayout(skeleton_layout)
                    
                    # 创建列表项并设置大小
                    skeleton_item = QListWidgetItem()
                    skeleton_item.setSizeHint(QSize(scale(190), scale(160)))
                    
                    # 添加到列表
                    self.content_list.addItem(skeleton_item)
                    self.content_list.setItemWidget(skeleton_item, skeleton_widget)
                
        # 在主线程中执行
        QTimer.singleShot(0, clear_content_and_show_skeleton)
        
        import threading
        
        def get_folder_content():
            logger = logging.getLogger(__name__)
            logger.info("get_folder_content线程开始执行")
            try:
                logger.info(f"开始获取收藏夹内容，folder_id: {folder_id}")
                content = self.parser.get_folder_content(folder_id, page_size=50, get_all=True)
                logger.info(f"获取收藏夹内容成功，共 {len(content['items'])} 个项目")
                content_items = content.get('items', [])
                self.signal_emitter.folder_content_loaded.emit(content_items)
            except Exception as e:
                traceback.print_exc()
                logger.error(f"获取收藏内容失败：{str(e)}")
                self.signal_emitter.folder_error.emit(f"获取收藏内容失败：{str(e)}")
        
        # 启动线程
        logger.info("启动获取收藏内容线程")
        thread = threading.Thread(target=get_folder_content)
        thread.daemon = True
        thread.start()
        logger.info("线程已启动")
    
    def update_content_ui(self, content_items):
        try:
            self.update_content_list(content_items)
            self.status_label.setText(f"收藏内容获取成功 - 共 {len(content_items)} 个收藏内容")
        except Exception:
            pass

    def create_favorite_card(self, item, index):
        card_w = self.content_list._card_width
        card_h = self.content_list._card_height
        cover_w = card_w - scale(8)
        cover_h = int(cover_w * 9 / 16)
        text_w = card_w - scale(4)

        widget = QWidget()
        widget.setFixedSize(card_w, card_h)
        widget.setObjectName(f"favorite_card_{index}")
        widget.setStyleSheet(scale_style("""
            QWidget#favorite_card_%d {
                background-color: white;
                border-radius: 10px;
                border: 2px solid transparent;
            }
            QWidget#favorite_card_%d[selected="true"] {
                border: 2px solid #4f6ef7;
                background-color: #f0f4ff;
            }
        """ % (index, index)))
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(scale(2), scale(4), scale(2), scale(4))
        layout.setSpacing(scale(0))
        
        cover_container = QWidget()
        cover_container.setFixedSize(cover_w, cover_h)
        cover_container.setStyleSheet(scale_style("""
            QWidget {
                background-color: #e8ecf1;
                border-radius: 8px;
            }
        """))
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        cover_layout.setSpacing(scale(0))
        
        cover_label = QLabel()
        cover_label.setFixedSize(cover_w, cover_h)
        cover_label.setStyleSheet("background: transparent; border: none;")
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setScaledContents(False)
        cover_label.setText("")
        cover_layout.addWidget(cover_label)
        
        layout.addWidget(cover_container, alignment=Qt.AlignCenter)
        
        duration = item.get('duration', 0)
        minutes = duration // 60
        seconds = duration % 60
        duration_str = f"{minutes}:{seconds:02d}"
        
        duration_label = QLabel(duration_str)
        duration_label.setFixedSize(scale(46), scale(18))
        duration_label.setStyleSheet(scale_style("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                font-size: 11px;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """))
        duration_label.setAlignment(Qt.AlignCenter)
        
        duration_label.setParent(cover_container)
        def update_duration_pos():
            try:
                cw = cover_container.width()
                ch = cover_container.height()
                dw = duration_label.width()
                dh = duration_label.height()
                duration_label.move(max(0, cw - dw - scale(6)), max(0, ch - dh - scale(6)))
            except Exception:
                pass
        QTimer.singleShot(0, update_duration_pos)
        cover_container.resizeEvent = lambda e: (update_duration_pos(),)
        
        cover_url = item.get('cover')
        if cover_url:
            
            class CoverLoader(QThread):
                class SignalEmitter(QObject):
                    finished = pyqtSignal(QPixmap)
                
                def __init__(self, url):
                    super().__init__()
                    self.url = url
                    self.signals = self.SignalEmitter()
                
                def run(self):
                    try:
                        response = requests.get(self.url, timeout=3)
                        response.raise_for_status()
                        pixmap = QPixmap()
                        pixmap.loadFromData(response.content)
                        self.signals.finished.emit(pixmap)
                    except:
                        self.signals.finished.emit(QPixmap())
            
            def on_cover_loaded(pixmap):
                try:
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(cover_w, cover_h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        crop_w = min(scaled_pixmap.width(), cover_w)
                        crop_h = min(scaled_pixmap.height(), cover_h)
                        x = (scaled_pixmap.width() - crop_w) // 2
                        y = (scaled_pixmap.height() - crop_h) // 2
                        cropped = scaled_pixmap.copy(x, y, crop_w, crop_h)
                        cover_label.setPixmap(cropped)
                        cover_label.setStyleSheet("background: transparent; border: none;")
                    else:
                        cover_label.setText("加载失败")
                except Exception:
                    pass
            
            loader = CoverLoader(cover_url)
            loader.signals.finished.connect(on_cover_loaded)
            loader.start()
            
            self.cover_loaders.append(loader)
        
        layout.addSpacing(4)
        
        title = item.get('title', '未知视频')
        title_label = QLabel(title)
        title_label.setFixedHeight(scale(26))
        title_label.setFixedWidth(text_w)
        title_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        title_label.setStyleSheet(scale_style("""
            QLabel {
                font-size: 12px;
                font-weight: 500;
                color: #1f2937;
                background: transparent;
            }
        """))
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setWordWrap(False)
        title_label.setTextInteractionFlags(Qt.NoTextInteraction)
        
        if len(title) > 18:
            class MarqueeTimer(QTimer):
                def __init__(self, label):
                    super().__init__()
                    self.label = label
                    self.text = label.text()
                    self.index = 0
                    self.timeout.connect(self.update_text)
                    self.start(200)
                
                def update_text(self):
                    try:
                        if hasattr(self.label, 'isVisible') and self.label.isVisible():
                            self.index = (self.index + 1) % len(self.text)
                            display_text = self.text[self.index:] + ' ' + self.text[:self.index]
                            self.label.setText(display_text)
                        else:
                            self.stop()
                    except RuntimeError:
                        self.stop()
            
            timer = MarqueeTimer(title_label)
            if not hasattr(self, 'marquee_timers'):
                self.marquee_timers = []
            self.marquee_timers.append(timer)
        
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        
        layout.addSpacing(2)
        
        up_name = item.get('up_name', '未知UP主')
        up_label = QLabel(up_name)
        up_label.setFixedHeight(scale(22))
        up_label.setFixedWidth(text_w)
        up_label.setStyleSheet(scale_style("""
            QLabel {
                font-size: 11px;
                color: #6b7280;
                background: transparent;
            }
        """))
        up_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(up_label, alignment=Qt.AlignCenter)
        
        layout.addSpacing(2)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(4))
        
        parse_btn = QPushButton("解析")
        parse_btn.setMinimumSize(scale(80), scale(40))
        parse_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """))
        bvid = item.get('bvid', '')
        parse_btn.clicked.connect(lambda checked, b=bvid: self.parse_favorite_video(b))
        btn_layout.addWidget(parse_btn)
        
        cover_btn = QPushButton("封面")
        cover_btn.setMinimumSize(scale(80), scale(40))
        cover_btn.setStyleSheet(scale_style("""
            QPushButton {
                background-color: #4f6ef7;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3b5de7;
            }
        """))
        cover_btn.clicked.connect(lambda checked, url=cover_url, t=title: self.download_favorite_cover(url, t))
        btn_layout.addWidget(cover_btn)
        
        layout.addLayout(btn_layout)
        
        return widget
    
    def _calc_card_size(self):
        try:
            list_w = self.content_list.viewport().width()
            if list_w <= 0:
                list_w = self.content_list.width()
            if list_w <= 0:
                return
            base_card_w = scale(190)
            spacing = scale(8)
            padding = scale(24)
            available_w = list_w - padding
            cols = max(1, int(available_w / (base_card_w + spacing)))
            card_w = int((available_w - (cols - 1) * spacing) / cols)
            card_w = max(base_card_w, card_w)
            cover_w = card_w - scale(8)
            cover_h = int(cover_w * 9 / 16)
            card_h = cover_h + scale(120)
            self.content_list._card_width = card_w
            self.content_list._card_height = card_h
        except Exception:
            pass
    
    def update_content_list(self, items):
        logger = logging.getLogger(__name__)
        
        # 确保content_list存在
        if not hasattr(self, 'content_list'):
            logger.error("content_list不存在")
            return
        
        # 清空列表
        self.content_list.clear()
        
        # 根据当前列表宽度计算卡片尺寸
        self._calc_card_size()
        
        # 记录处理的项目数量
        logger.info(f"开始更新收藏内容列表，共 {len(items)} 个项目")
        
        if not items:
            # 当没有内容时，显示提示信息
            empty_item = QListWidgetItem("收藏夹为空")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsSelectable)
            empty_item.setForeground(QColor('#94a3b8'))
            self.content_list.addItem(empty_item)
            if hasattr(self, 'parse_favorite_btn'):
                self.parse_favorite_btn.setEnabled(False)
            logger.info("收藏内容列表为空")
        else:
            # 显示骨架屏
            skeleton_items = []
            card_w = self.content_list._card_width
            card_h = self.content_list._card_height
            for i in range(min(12, len(items))):  # 显示最多12个骨架屏
                skeleton_widget = QWidget()
                skeleton_widget.setMinimumSize(card_w, card_h)
                skeleton_layout = QVBoxLayout()
                
                skeleton_style = """
                    QWidget {
                        background-color: #f3f4f6;
                        border-radius: 8px;
                    }
                """
                
                # 封面骨架
                cover_skeleton = QWidget()
                cover_skeleton.setMinimumSize(card_w - scale(8), int((card_w - scale(8)) * 9 / 16))
                cover_skeleton.setStyleSheet(skeleton_style)
                skeleton_layout.addWidget(cover_skeleton, alignment=Qt.AlignCenter)
                
                # 标题骨架
                skeleton_layout.addSpacing(10)
                title_skeleton = QWidget()
                title_skeleton.setMinimumSize(card_w - scale(20), scale(16))
                title_skeleton.setStyleSheet(skeleton_style)
                skeleton_layout.addWidget(title_skeleton, alignment=Qt.AlignCenter)
                
                # UP主骨架
                skeleton_layout.addSpacing(6)
                up_skeleton = QWidget()
                up_skeleton.setMinimumSize(scale(100), scale(12))
                up_skeleton.setStyleSheet(skeleton_style)
                skeleton_layout.addWidget(up_skeleton, alignment=Qt.AlignCenter)
                
                # 时长骨架
                duration_skeleton = QWidget()
                duration_skeleton.setMinimumSize(scale(60), scale(12))
                duration_skeleton.setStyleSheet(skeleton_style)
                skeleton_layout.addWidget(duration_skeleton, alignment=Qt.AlignCenter)
                
                skeleton_widget.setLayout(skeleton_layout)
                
                # 创建列表项并设置大小
                skeleton_item = QListWidgetItem()
                skeleton_item.setSizeHint(QSize(card_w, card_h))
                
                # 添加到列表
                self.content_list.addItem(skeleton_item)
                self.content_list.setItemWidget(skeleton_item, skeleton_widget)
                skeleton_items.append(skeleton_item)
                
            
            # 短暂延迟，让骨架屏显示一会儿
            time.sleep(0.2)
            
            # 清空骨架屏
            self.content_list.clear()
            
            # 确保items是一个列表
            if not isinstance(items, list):
                logger.error(f"items类型错误，期望列表，实际是：{type(items)}")
                return
            
            # 批量添加项目
            added_count = 0
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    logger.error(f"item类型错误，期望字典，实际是：{type(item)}")
                    continue
                    
                # 创建卡片widget
                item_widget = self.create_favorite_card(item, i)
                
                # 创建列表项并设置大小
                list_item = QListWidgetItem()
                list_item.setSizeHint(QSize(self.content_list._card_width, self.content_list._card_height))
                list_item.setData(Qt.UserRole, item)
                
                # 添加到列表
                self.content_list.addItem(list_item)
                self.content_list.setItemWidget(list_item, item_widget)
                
                added_count += 1
                
                time.sleep(0.05)
            
            if hasattr(self, 'parse_favorite_btn'):
                self.parse_favorite_btn.setEnabled(added_count > 0)
            if hasattr(self, 'download_cover_favorite_btn'):
                self.download_cover_favorite_btn.setEnabled(False)
    
    def on_tab_changed(self, index):
        logger = logging.getLogger(__name__)
        logger.info(f"标签页切换到索引：{index}")
        
        if index == 2:
            logger.info("切换到收藏夹标签页，开始刷新收藏夹列表")
            self.refresh_folders()
        elif index == 3:
            logger.info("切换到封面下载标签页")
            self.update_cover_tab()
    
    def on_content_clicked(self, item):
        logger = logging.getLogger(__name__)
        logger.info("点击收藏内容")
        
        if hasattr(self, 'parse_favorite_btn'):
            self.parse_favorite_btn.setEnabled(True)
        if hasattr(self, 'download_cover_favorite_btn'):
            self.download_cover_favorite_btn.setEnabled(True)
        
        self.update_card_selection_styles()
    
    def update_card_selection_styles(self):
        logger = logging.getLogger(__name__)
        
        # 获取所有选中的项目
        selected_items = self.content_list.selectedItems()
        selected_indices = set()
        for item in selected_items:
            # 通过列表项找到对应的widget
            widget = self.content_list.itemWidget(item)
            if widget:
                # 从objectName中提取索引
                object_name = widget.objectName()
                if object_name.startswith("favorite_card_"):
                    try:
                        index = int(object_name.split("_")[-1])
                        selected_indices.add(index)
                    except ValueError:
                        pass
        
        # 更新所有卡片的样式
        for i in range(self.content_list.count()):
            item = self.content_list.item(i)
            widget = self.content_list.itemWidget(item)
            if widget:
                if i in selected_indices:
                    widget.setProperty("selected", "true")
                else:
                    widget.setProperty("selected", "false")
                # 刷新样式
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
    
    def on_content_double_clicked(self, item):
        content_item = item.data(Qt.UserRole)
        if not content_item:
            return
        
        bvid = content_item.get('bvid')
        if not bvid:
            self.show_notification("无BV号，无法解析", "error")
            return
        
        # 构造视频链接
        video_url = f"https://www.bilibili.com/video/{bvid}"
        
        # 切换到视频解析标签页
        self.tab_widget.setCurrentIndex(0)
        
        # 填充URL并解析
        self.url_edit.setText(video_url)
        self.on_parse()
    
    def parse_selected_content(self):
        selected_items = self.content_list.selectedItems()
        if not selected_items:
            self.show_notification("请选择要解析的内容", "warning")
            return
        
        # 收集所有选中视频的URL
        urls = []
        for item in selected_items:
            content_item = item.data(Qt.UserRole)
            if not content_item:
                continue
            
            bvid = content_item.get('bvid')
            if not bvid:
                continue
            
            # 构造视频链接
            video_url = f"https://www.bilibili.com/video/{bvid}"
            urls.append(video_url)
        
        if not urls:
            self.show_notification("没有可解析的视频", "warning")
            return
        
        # 如果只选择了一个视频，使用单独解析逻辑
        if len(urls) == 1:
            video_url = urls[0]
            self.url_edit.setText(video_url)
            self.on_parse()
        else:
            # 如果选择了多个视频，使用批量解析逻辑
            self.start_batch_parse_with_urls(urls)
    
    def check_cookie_validity(self, skip_user_info=False):
        
        self.user_info_label.setText("未登录")
        self.vip_label.setText("× 未登录")
        self.vip_label.setStyleSheet("color: #6b7280;")
        
        if hasattr(self, 'parser') and self.parser:
            if self.parser.cookies:
                
                import threading
                def verify_cookie_in_thread():
                    try:
                        success, msg = self.parser.verify_cookie()
                        self.signal_emitter.cookie_verified.emit(success, msg)
                    except Exception as e:
                        logger.error(f"检查cookie有效性失败：{str(e)}")
                        self.signal_emitter.cookie_verified.emit(False, str(e))
                
                thread = threading.Thread(target=verify_cookie_in_thread)
                thread.daemon = True
                thread.start()
            else:
                
                self.show_cookie_ui()
    
    def hide_cookie_ui(self):
        
        self.showMaximized()
        
        
        if not hasattr(self, 'logout_btn'):
            self.logout_btn = QPushButton("退出登录")
            self.logout_btn.setStyleSheet("background-color: #f56c6c;")
            self.logout_btn.setMinimumHeight(scale(32))
            self.logout_btn.setMinimumWidth(scale(90))
            self.logout_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            self.logout_btn.clicked.connect(self.on_logout)
            
            for child in self.findChildren(QGroupBox):
                if "系统信息" in child.title():
                    sys_group = child
                    sys_layout = sys_group.layout()
                    if sys_layout:
                        
                        for i in range(sys_layout.count()):
                            item = sys_layout.itemAt(i)
                            if isinstance(item, QHBoxLayout):
                                
                                item.addWidget(self.logout_btn)
                                break
                        break
        else:
            self.logout_btn.show()
        
        

        
        
        main_widget = self.centralWidget()
        if main_widget:
            content_widget = main_widget.findChild(QWidget)
            if content_widget:
                content_layout = content_widget.layout()
                if content_layout:
                    content_layout.update()
        
        self.showMaximized()
    
    def show_cookie_ui(self):
        
        self.showMaximized()
        
        
        if hasattr(self, 'logout_btn'):
            self.logout_btn.hide()
        
        

        
        
        main_widget = self.centralWidget()
        if main_widget:
            content_widget = main_widget.findChild(QWidget)
            if content_widget:
                content_layout = content_widget.layout()
                if content_layout:
                    content_layout.update()
        
        
        
        self.showMaximized()
    
    def adjust_layout_space(self):
        
        pass
    
    def restore_layout_space(self):
        
        pass
    
    def on_logout(self):
        
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle("确认退出登录")
        dialog.setMinimumSize(scale(350), scale(200))
        
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                background-color: white;
            }
        """)
        dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        dialog.mousePressEvent = lambda event: setattr(dialog, '_mouse_pos', event.globalPos() - dialog.pos())
        dialog.mouseMoveEvent = lambda event: dialog.move(event.globalPos() - getattr(dialog, '_mouse_pos', QPoint(0, 0))) if hasattr(dialog, '_mouse_pos') else None
        dialog.mouseReleaseEvent = lambda event: setattr(dialog, '_mouse_pos', None)
        
        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("确认退出登录")
        title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(20))
        
        
        info_label = QLabel("确定要退出登录吗？")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet(scale_style("font-size: 16px; color: #333;"))
        content_layout.addWidget(info_label)
        
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(15))
        
        yes_btn = QPushButton("确定")
        yes_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; font-weight: 500; padding: 10px 24px;"))
        no_btn = QPushButton("取消")
        no_btn.setStyleSheet(scale_style("background-color: #f56c6c; color: white; font-weight: 500; padding: 10px 24px;"))
        
        def on_yes():
            dialog.accept()
        
        def on_no():
            dialog.reject()
        
        yes_btn.clicked.connect(on_yes)
        no_btn.clicked.connect(on_no)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(yes_btn)
        btn_layout.addWidget(no_btn)
        btn_layout.addStretch(1)
        content_layout.addLayout(btn_layout)
        
        main_layout.addWidget(content_widget)
        
        
        reply = dialog.exec_()
        
        reply = QMessageBox.Yes if reply == QDialog.Accepted else QMessageBox.No
        
        if reply == QMessageBox.Yes:
            try:
                cookie_files_to_delete = set()
                cookie_files_to_delete.add(os.path.abspath(self.cookie_file))
                if hasattr(self, 'parser') and self.parser and hasattr(self.parser, 'cookie_path'):
                    cookie_files_to_delete.add(self.parser.cookie_path)
                for f in cookie_files_to_delete:
                    try:
                        if os.path.exists(f):
                            os.remove(f)
                    except Exception as del_err:
                        logger.error(f"删除cookie文件失败({f})：{del_err}")
                
                if hasattr(self, 'parser') and self.parser:
                    self.parser.cookies = {}
                    self.parser.session.cookies.clear()
                    self.parser.csrf_token = ""
                    self.parser.user_info = None
                    if hasattr(self.parser, '_api_cache'):
                        self.parser._api_cache.clear()
                    if 'X-CSRF-Token' in self.parser.session.headers:
                        del self.parser.session.headers['X-CSRF-Token']
                
                self.showMaximized()
                
                
                self.show_cookie_ui()
                
                
                self.user_info_label.setText("未登录")
                self.vip_label.setText("× 未登录")
                self.vip_label.setStyleSheet("color: #6b7280;")
                
                
                self.update_login_info_display()
                self.load_default_avatar()
                
                # 重置登录对话框，确保下次点击登录时创建新的对话框
                self.login_dialog = None
                
                self.show_notification("退出登录成功！", "success")
                
                self.showMaximized()
            except Exception as e:
                logger.error(f"退出登录失败：{str(e)}")
                self.show_notification(f"退出登录失败：{str(e)}", "error")
                
                self.showMaximized()

    def on_apply_cookie(self):
        
        pass

    def on_clear_cookie(self):
        
        pass
    


    def on_cookie_verified(self, success, msg):
        try:
            is_user_login = hasattr(self, '_cookie_login_btn') and self._cookie_login_btn is not None
            
            if hasattr(self, '_cookie_login_btn') and self._cookie_login_btn:
                self._cookie_login_btn.setEnabled(True)
                self._cookie_login_btn.setText("登录")
                self._cookie_login_btn = None
            
            if success:
                if hasattr(self, 'login_dialog') and self.login_dialog:
                    self.login_dialog.accept()
                    self.login_dialog = None
                
                if is_user_login:
                    self.show_notification(f"Cookie验证通过！{msg}", "success")
                self.hide_cookie_ui()
                
                import threading
                def post_login_tasks():
                    try:
                        user_info = self.parser.get_user_info(force_refresh=True)
                        self.signal_emitter.user_info_updated.emit(user_info)
                    except Exception as e:
                        logger.error(f"登录后处理失败：{str(e)}")
                
                thread = threading.Thread(target=post_login_tasks)
                thread.daemon = True
                thread.start()
            else:
                if is_user_login:
                    self.show_notification(f"Cookie验证失败：{msg}", "error")
                self.show_cookie_ui()
                self.user_info_label.setText("未登录")
                self.vip_label.setText("× 未登录")
                self.vip_label.setStyleSheet("color: #6b7280;")
                self.load_default_avatar()
                if hasattr(self, 'login_dialog') and self.login_dialog:
                    self.login_dialog.raise_()
        except Exception:
            pass
    
    def handle_verification_result(self, success, msg):
        """处理Cookie验证结果"""
        print("handle_verification_result函数开始执行")
        try:
            if success:
                try:
                    print("显示成功消息...")
                    self.show_success_message(msg)
                    print("成功消息已显示")
                    
                    if hasattr(self, 'login_dialog') and self.login_dialog:
                        print("隐藏登录对话框...")
                        self.login_dialog.hide()
                        print("登录对话框已隐藏")
                    
                    # 显示主窗口
                    self.showMaximized()
                    print("主窗口已显示")
                    
                    # 在子线程中加载用户信息，避免UI卡死
                    import threading
                    def load_user_info_in_thread():
                        try:
                            print("加载用户信息...")
                            user_info = self.parser.get_user_info(force_refresh=True)
                            print(f"获取到的用户信息：{user_info}")
                            self.signal_emitter.user_info_updated.emit(user_info)
                            print("登录后处理完成")
                        except Exception as e:
                            logger.error(f"加载用户信息失败：{str(e)}")
                            print(f"加载用户信息失败：{str(e)}")
                            print(f"处理成功情况时发生异常：{str(e)}")
                            import traceback
                            traceback.print_exc()
                    
                    thread = threading.Thread(target=load_user_info_in_thread)
                    thread.daemon = True
                    thread.start()
                    
                except Exception as e:
                    logger.error(f"保存Cookie失败：{str(e)}")
                    self.show_notification(f"保存Cookie失败：{str(e)}", "error")
                    print(f"处理成功情况时发生异常：{str(e)}")
                    import traceback
                    traceback.print_exc()
            else:
                print("显示验证失败消息...")
                self.show_notification(f"验证失败：{msg}", "error")
                print("验证失败消息已显示")
                
                print("登录失败，保持窗口显示")
            
            print("验证流程执行完成")
        except Exception as e:
            print(f"handle_verification_result函数发生异常：{str(e)}")
            import traceback
            traceback.print_exc()
    
    def show_success_message(self, msg):
        self.show_notification(f"Cookie验证通过啦！\n{msg}", "success")
    
    def show_error_message(self, msg):
        self.show_notification(f"Cookie验证失败了：{msg}", "error")

    def on_parse(self):
        url = self.url_edit.text().strip()
        if not url:
            self.show_notification("请输入有效的视频链接", "warning")
            return
        self.clear_parse_video_info()
        self.parse_btn.setEnabled(False)
        self.video_title.setText("解析中...")
        self.status_label.setText("正在解析链接...")
        
        # 创建解析进度窗口
        self.parse_progress_window = ParseProgressWindow(self)
        self.parse_progress_window.show()
        
        # 显示解析开始的通知
        self.show_notification("解析开始，正在处理视频信息...", "info")
        
        import threading
        
        def parse_in_thread():
            try:
                if self.parser is None:
                    self.signal_emitter.parse_finished.emit({"success": False, "error": "解析器未初始化，请重启应用"})
                    return
                
                def progress_callback(progress, message):
                    self.signal_emitter.parse_progress.emit(progress, message)
                
                # 发送信号，在主线程中显示解析进度窗口
                self.signal_emitter.show_parse_progress.emit()
                
                # 发送进度更新信号
                progress_callback(10, "解析URL...")
                media_parse_video_info = self.parser.parse_media_url(url)
                if media_parse_video_info.get("error"):
                    
                    self.signal_emitter.parse_finished.emit({"success": False, "error": media_parse_video_info["error"]})
                    return

                media_type = media_parse_video_info["type"]
                media_id = media_parse_video_info["id"]
                if not media_type or not media_id:
                    self.signal_emitter.parse_finished.emit({"success": False, "error": "未识别到有效媒体ID（支持BV/ss/av号）"})
                    return

                try:
                    if media_type == "space":
                        # 处理 UP 主主页
                        progress_callback(30, "获取UP主信息...")
                        space_info = self.parser.get_space_info(media_id)
                        if not space_info.get("success"):
                            error_msg = space_info.get("error", "获取UP主信息失败")
                            if "访问权限不足" in error_msg:
                                error_msg = "该UP主主页可能需要登录或权限访问，请尝试登录后再解析"
                            self.signal_emitter.parse_finished.emit({"success": False, "error": error_msg})
                            return
                        
                        def update_video_list_progress(msg):
                            progress_callback(60, msg)
                        
                        progress_callback(50, "获取UP主作品列表...")
                        videos_info = self.parser.get_space_videos(media_id, progress_callback=update_video_list_progress)
                        if not videos_info.get("success"):
                            error_msg = videos_info.get("error", "获取作品列表失败")
                            if "访问权限不足" in error_msg:
                                error_msg = "该UP主作品可能需要登录或权限访问，请尝试登录后再解析"
                            self.signal_emitter.parse_finished.emit({"success": False, "error": error_msg})
                            return
                        
                        progress_callback(100, "加载完成！")
                        self.signal_emitter.show_space_videos.emit(space_info, videos_info['videos'])
                        return
                    else:
                        # 处理其他类型
                        media_info = self.parser.parse_media(media_type, media_id, self.tv_mode_checkbox.isChecked(), progress_callback)
                        self.signal_emitter.parse_finished.emit(media_info)
                except Exception as e:
                    self.signal_emitter.parse_finished.emit({"success": False, "error": f"解析失败：{str(e)}"})
            except Exception as e:
                self.signal_emitter.parse_finished.emit({"success": False, "error": f"解析失败：{str(e)}"})
        
        
        thread = threading.Thread(target=parse_in_thread)
        thread.daemon = True
        thread.start()

    def clear_parse_video_info(self):
        self.video_title.setText("未解析")
        self.duration_label.setText("-")
        self.type_label.setText("未解析")
        self.type_label.setStyleSheet("")
        self.cover_label.setText("无封面")
        self.cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;"))
        
        video_info_group = self.findChild(QGroupBox, "video_info_group")
        if not video_info_group:
            
            for child in self.findChildren(QGroupBox):
                if child.title() == "解析结果":
                    video_info_group = child
                    break
        if video_info_group:
            video_info_group.setStyleSheet("")
        
        while hasattr(self, 'quality_combo') and self.quality_combo.count() > 1:
            self.quality_combo.removeItem(1)
        if hasattr(self, 'quality_combo'):
            self.quality_combo.setCurrentIndex(0)
            self.quality_combo.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.select_episode_btn.setEnabled(False)
        self.selected_episodes = []
        self.selected_qn = None
        self.select_episode_btn.setText("选择集数")

    def on_parse_finished(self, video_info):
        try:
            print(f"=== on_parse_finished被调用，video_info: {video_info}")
            
            # 更新进度为100%并显示加载完成
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                QTimer.singleShot(0, lambda: self.parse_progress_window.update_progress(100, "加载完成"))
                # 延迟关闭窗口，让用户看到加载完成的提示
                QTimer.singleShot(1000, lambda: self.parse_progress_window.close())
            
            # 确保parse_btn存在
            if hasattr(self, 'parse_btn'):
                self.parse_btn.setEnabled(True)
            else:
                print("错误：parse_btn控件不存在")
            
            # 确保main_progress存在
            if hasattr(self, 'main_progress'):
                self.main_progress.setValue(0)
            else:
                print("错误：main_progress控件不存在")
            
            if not video_info.get("success"):
                error_msg = video_info.get("error", "未知错误")
                print(f"解析失败：{error_msg}")
                
                # 确保在主线程中更新UI
                QTimer.singleShot(0, lambda: self.update_ui_error(error_msg))
                return

            self.current_video_info = video_info
            
            print(f"解析成功，标题：{video_info.get('title', '未知标题')}")
            
            # 显示解析成功的通知
            QTimer.singleShot(0, lambda: self.show_notification(f"解析成功，共找到 {len(video_info.get('episodes', [1]))} 个视频", "success"))
            
            # 确保在主线程中更新UI
            QTimer.singleShot(0, lambda: self.update_ui(video_info))
        except Exception as e:
            print(f"on_parse_finished错误：{str(e)}")
            traceback.print_exc()
            # 关闭解析进度窗口
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                QTimer.singleShot(0, lambda: self.parse_progress_window.close())
            # 确保在主线程中显示通知
            QTimer.singleShot(0, lambda: self.show_notification(f"解析失败：{str(e)}", "error"))
    
    def on_show_space_videos(self, space_info, videos):
        try:
            self._on_show_space_videos_impl(space_info, videos)
        except Exception:
            pass

    def _on_show_space_videos_impl(self, space_info, videos):
        if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
            QTimer.singleShot(0, lambda: self.parse_progress_window.close())
        
        class ImageLoader(QThread):
            image_ready = pyqtSignal(QLabel, QPixmap)
            
            def __init__(self, url, label):
                super().__init__()
                self.url = url
                self.label = label
            
            def run(self):
                try:
                    response = requests.get(self.url, timeout=5)
                    image = QImage()
                    success = image.loadFromData(response.content)
                    if success:
                        pixmap = QPixmap.fromImage(image)
                        self.image_ready.emit(self.label, pixmap)
                except Exception:
                    pass
        
        class ImageLoadManager:
            MAX_CONCURRENT = 5
            
            def __init__(self, dialog):
                self.dialog = dialog
                self.queue = []
                self.active_count = 0
            
            def enqueue(self, url, label):
                self.queue.append((url, label))
                self._try_next()
            
            def _try_next(self):
                while self.active_count < self.MAX_CONCURRENT and self.queue:
                    url, label = self.queue.pop(0)
                    self.active_count += 1
                    loader = ImageLoader(url, label)
                    self.dialog.loaders.append(loader)
                    def make_handler(l):
                        def handler(lb, pm):
                            self._on_loader_finished(l, lb, pm)
                        return handler
                    loader.image_ready.connect(make_handler(loader))
                    loader.start()
            
            def _on_loader_finished(self, loader, label, pixmap):
                self.active_count -= 1
                if loader in self.dialog.loaders:
                    self.dialog.loaders.remove(loader)
                try:
                    self.dialog.on_image_loaded(label, pixmap)
                except RuntimeError:
                    pass
                if self.queue:
                    self._try_next()
        
        class SpaceVideosDialog(QDialog):
            def __init__(self, parent, space_info, videos):
                super().__init__(parent)
                self.setWindowTitle(f"{space_info['name']} 的作品列表")
                screen = QApplication.primaryScreen()
                if screen:
                    sg = screen.geometry()
                    win_w = min(scale(800), int(sg.width() * 0.85))
                    win_h = min(scale(600), int(sg.height() * 0.85))
                    self.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
                else:
                    self.setGeometry(scale(100), scale(100), scale(800), scale(600))
                self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
                self.setAutoFillBackground(True)
                self.videos = videos
                self.loaders = []
                self.image_manager = ImageLoadManager(self)
                self.drag_position = None
                self.parent_widget = parent
                    
                # 标题栏
                title_bar = QWidget()
                title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
                title_layout = QHBoxLayout(title_bar)
                title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
                title_layout.setSpacing(scale(10))
                
                title_label = QLabel(f"{space_info['name']} 的作品列表")
                title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
                title_layout.addWidget(title_label, stretch=1)
                
                close_btn = QPushButton("×")
                close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
                close_btn.setToolTip("关闭")
                close_btn.clicked.connect(self.reject)
                title_layout.addWidget(close_btn)
                
                # 内容区域
                content_widget = QWidget()
                content_widget.setStyleSheet("border: none;")
                content_layout = QVBoxLayout(content_widget)
                content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
                content_layout.setSpacing(scale(15))
                
                # UP 主信息
                info_widget = QWidget()
                info_layout = QHBoxLayout(info_widget)
                info_layout.setSpacing(scale(15))
                
                # 头像
                avatar_label = QLabel()
                avatar_label.setText("加载中...")
                avatar_label.setFixedSize(scale(80), scale(80))
                avatar_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                avatar_label.setStyleSheet(scale_style("background-color: #e2e8f0; border-radius: 40px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;"))
                
                # 基本信息
                info_detail = QWidget()
                info_detail_layout = QVBoxLayout(info_detail)
                info_detail_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
                info_detail_layout.setSpacing(scale(5))
                
                name_label = QLabel(f"{space_info['name']}")
                name_label.setStyleSheet(scale_style("font-size: 18px; font-weight: 600; color: #1e293b;"))
                
                sign_label = QLabel(f"签名: {space_info['sign'] if space_info['sign'] else '无'}")
                sign_label.setStyleSheet(scale_style("font-size: 14px; color: #64748b;"))
                sign_label.setWordWrap(True)
                
                level_label = QLabel(f"等级: {space_info['level']}")
                level_label.setStyleSheet(scale_style("font-size: 14px; color: #64748b;"))
                
                info_detail_layout.addWidget(name_label)
                info_detail_layout.addWidget(sign_label)
                info_detail_layout.addWidget(level_label)
                
                info_layout.addWidget(avatar_label)
                info_layout.addWidget(info_detail, stretch=1)
                
                content_layout.addWidget(info_widget)
                
                # 作品列表
                videos_label = QLabel(f"共 {len(videos)} 个作品")
                videos_label.setStyleSheet(scale_style("font-size: 16px; font-weight: 500; color: #1e293b;"))
                content_layout.addWidget(videos_label)
                
                self.videos_list = QListWidget()
                self.videos_list.setSelectionMode(QListWidget.MultiSelection)
                content_layout.addWidget(self.videos_list, stretch=1)
                
                # 保存视频列表用于异步加载
                self.pending_videos = list(videos)
                self.current_video_index = 0
                self.videos_label = videos_label
                
                # 先显示对话框，然后再异步加载视频
                def start_loading_videos():
                    self.load_videos_batch()
                
                QTimer.singleShot(10, start_loading_videos)
                
                # 完全模式选项
                full_mode_layout = QHBoxLayout()
                full_mode_layout.setSpacing(scale(12))
                
                self.full_mode_checkbox = QCheckBox("完全模式（自动下载全部视频）")
                self.full_mode_checkbox.setStyleSheet(scale_style("font-size: 13px; color: #374151;"))
                self.full_mode_checkbox.stateChanged.connect(self.on_full_mode_changed)
                full_mode_layout.addWidget(self.full_mode_checkbox)
                
                # 清晰度选择（完全模式下显示）
                self.full_mode_quality_label = QLabel("清晰度：")
                self.full_mode_quality_label.setStyleSheet(scale_style("font-size: 13px; color: #374151;"))
                self.full_mode_quality_label.setVisible(False)
                full_mode_layout.addWidget(self.full_mode_quality_label)
                
                self.full_mode_quality_combo = QComboBox()
                self.full_mode_quality_combo.setMinimumHeight(scale(32))
                self.full_mode_quality_combo.setStyleSheet(scale_style("""
                    QComboBox {
                        border: 1px solid #d1d5db;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-size: 13px;
                        min-width: 120px;
                    }
                    QComboBox::drop-down {
                        border: none;
                        min-width: 24px;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 6px solid #6b7280;
                        margin-right: 8px;
                    }
                    QComboBox QAbstractItemView {
                        border: 1px solid #d1d5db;
                        border-radius: 6px;
                        background-color: white;
                        selection-background-color: #409eff;
                    }
                """))
                # 添加清晰度选项
                self.full_mode_quality_combo.addItem("1080P 高码率", 112)
                self.full_mode_quality_combo.addItem("1080P 高清", 80)
                self.full_mode_quality_combo.addItem("720P 高清", 64)
                self.full_mode_quality_combo.addItem("480P 清晰", 32)
                self.full_mode_quality_combo.addItem("360P 流畅", 16)
                # 默认选择1080P高清
                self.full_mode_quality_combo.setCurrentIndex(1)
                self.full_mode_quality_combo.setVisible(False)
                full_mode_layout.addWidget(self.full_mode_quality_combo)
                
                # 音质选择（完全模式下显示）
                self.full_mode_audio_label = QLabel("音质：")
                self.full_mode_audio_label.setStyleSheet(scale_style("font-size: 13px; color: #374151;"))
                self.full_mode_audio_label.setVisible(False)
                full_mode_layout.addWidget(self.full_mode_audio_label)
                
                self.full_mode_audio_combo = QComboBox()
                self.full_mode_audio_combo.setMinimumHeight(scale(32))
                self.full_mode_audio_combo.setStyleSheet(scale_style("""
                    QComboBox {
                        border: 1px solid #d1d5db;
                        border-radius: 6px;
                        padding: 4px 8px;
                        font-size: 13px;
                        min-width: 120px;
                    }
                    QComboBox::drop-down {
                        border: none;
                        min-width: 24px;
                    }
                    QComboBox::down-arrow {
                        image: none;
                        border-left: 4px solid transparent;
                        border-right: 4px solid transparent;
                        border-top: 6px solid #6b7280;
                        margin-right: 8px;
                    }
                    QComboBox QAbstractItemView {
                        border: 1px solid #d1d5db;
                        border-radius: 6px;
                        background-color: white;
                        selection-background-color: #409eff;
                    }
                """))
                # 添加音质选项
                self.full_mode_audio_combo.addItem("Hi-Res无损", 30251)
                self.full_mode_audio_combo.addItem("杜比全景声", 30250)
                self.full_mode_audio_combo.addItem("192K", 30280)
                self.full_mode_audio_combo.addItem("132K", 30232)
                self.full_mode_audio_combo.addItem("64K", 30216)
                # 默认选择192K
                self.full_mode_audio_combo.setCurrentIndex(2)
                self.full_mode_audio_combo.setVisible(False)
                full_mode_layout.addWidget(self.full_mode_audio_combo)
                
                full_mode_layout.addStretch(1)
                
                content_layout.addLayout(full_mode_layout)
                
                # 按钮区域
                btn_layout = QHBoxLayout()
                btn_layout.setSpacing(scale(12))
                
                select_all_btn = QPushButton("全选")
                select_all_btn.setMinimumHeight(scale(36))
                select_all_btn.setStyleSheet(scale_style("padding: 0 24px; border: 1px solid #409eff; border-radius: 6px; font-size: 14px; background-color: white; color: #409eff;"))
                select_all_btn.clicked.connect(self.select_all_videos)
                
                cancel_btn = QPushButton("取消")
                cancel_btn.setMinimumHeight(scale(36))
                cancel_btn.setStyleSheet(scale_style("padding: 0 24px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; background-color: white; color: #374151;"))
                cancel_btn.clicked.connect(self.reject)
                
                self.confirm_btn = QPushButton("解析选中 (0)")
                self.confirm_btn.setMinimumHeight(scale(36))
                self.confirm_btn.setStyleSheet(scale_style("padding: 0 24px; border: none; border-radius: 6px; font-size: 14px; background-color: #409eff; color: white;"))
                self.confirm_btn.clicked.connect(self.accept)
                
                # 连接选择变化信号
                self.videos_list.itemSelectionChanged.connect(self.update_confirm_button)
                
                btn_layout.addWidget(select_all_btn)
                btn_layout.addStretch(1)
                btn_layout.addWidget(cancel_btn)
                btn_layout.addWidget(self.confirm_btn)
                
                content_layout.addLayout(btn_layout)
                
                # 创建一个外层widget来实现边框效果
                outer_widget = QWidget()
                outer_widget.setStyleSheet(scale_style("border-left: 2px solid #409eff; border-right: 2px solid #409eff; border-bottom: 2px solid #409eff; border-bottom-left-radius: 10px; border-bottom-right-radius: 10px;"))
                outer_layout = QVBoxLayout(outer_widget)
                outer_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
                outer_layout.setSpacing(scale(0))
                outer_layout.addWidget(content_widget)
                
                # 主布局
                main_layout = QVBoxLayout(self)
                main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
                main_layout.setSpacing(scale(0))
                main_layout.addWidget(title_bar)
                main_layout.addWidget(outer_widget)
                
                if space_info.get('face'):
                    self.image_manager.enqueue(space_info['face'], avatar_label)
            
            def on_image_loaded(self, label, pixmap):
                if pixmap:
                    if label.width() > scale(80):
                        pixmap = pixmap.scaled(scale(120), scale(68), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    else:
                        pixmap = pixmap.scaled(scale(80), scale(80), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    label.setPixmap(pixmap)
                    label.setText("")
                    label.setStyleSheet("")
            
            def closeEvent(self, event):
                try:
                    self.image_manager.queue.clear()
                    self.image_manager.active_count = 0
                    for loader in self.loaders:
                        if loader.isRunning():
                            loader.quit()
                            loader.wait(1000)
                    self.loaders.clear()
                except Exception:
                    pass
                event.accept()
            
            def download_single_cover(self, cover_url, title):
                if not cover_url:
                    QMessageBox.information(self, "提示", "该视频没有封面信息")
                    return
                safe_title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or "cover"
                save_path, _ = QFileDialog.getSaveFileName(
                    self, "保存封面", os.path.join(os.path.expanduser("~"), "Desktop", f"{safe_title}.png"),
                    "PNG图片 (*.png);;JPEG图片 (*.jpg);;BMP图片 (*.bmp);;所有文件 (*)"
                )
                if save_path:
                    import threading, requests
                    from PyQt5.QtGui import QPixmap
                    def download():
                        try:
                            response = requests.get(cover_url, timeout=15)
                            response.raise_for_status()
                            pixmap = QPixmap()
                            pixmap.loadFromData(response.content)
                            if not pixmap.isNull():
                                pixmap.save(save_path)
                                self.parent_widget.show_notification(f"封面已保存到：{os.path.basename(save_path)}", "success")
                            else:
                                self.parent_widget.show_notification("封面数据无效", "error")
                        except Exception as e:
                            self.parent_widget.show_notification(f"保存失败：{str(e)}", "error")
                    thread = threading.Thread(target=download, daemon=True)
                    thread.start()
            
            def select_all_videos(self):
                # 先断开信号避免频繁触发
                self.videos_list.blockSignals(True)
                for i in range(self.videos_list.count()):
                    item = self.videos_list.item(i)
                    item.setSelected(True)
                self.videos_list.blockSignals(False)
                self.update_confirm_button()
            
            def update_confirm_button(self):
                selected_count = len(self.videos_list.selectedItems())
                self.confirm_btn.setText(f"解析选中 ({selected_count})")
            
            def get_selected_videos(self):
                selected_items = self.videos_list.selectedItems()
                selected_videos = []
                for item in selected_items:
                    # 直接从item中获取存储的视频数据，避免通过itemWidget查找
                    video = item.data(Qt.UserRole)
                    if video:
                        selected_videos.append(video)
                return selected_videos
            
            def mousePressEvent(self, event):
                # 当鼠标在标题栏按下时，开始拖动
                if event.button() == Qt.LeftButton:
                    self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                    event.accept()
            
            def mouseMoveEvent(self, event):
                # 当鼠标移动时，更新窗口位置
                if event.buttons() == Qt.LeftButton and self.drag_position is not None:
                    self.move(event.globalPos() - self.drag_position)
                    event.accept()
            
            def mouseReleaseEvent(self, event):
                # 当鼠标释放时，结束拖动
                self.drag_position = None
                event.accept()
            
            def load_videos_batch(self):
                batch_size = 30
                end_index = min(self.current_video_index + batch_size, len(self.pending_videos))
                
                for i in range(self.current_video_index, end_index):
                    video = self.pending_videos[i]
                    
                    item = QListWidgetItem()
                    widget = QWidget()
                    layout = QHBoxLayout(widget)
                    layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))
                    layout.setSpacing(scale(12))
                    
                    cover_label = QLabel()
                    cover_label.setText("加载中...")
                    cover_label.setMinimumSize(scale(120), scale(68))
                    cover_label.setMaximumSize(scale(120), scale(68))
                    cover_label.setStyleSheet(scale_style("background-color: #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;"))
                    
                    info_widget = QWidget()
                    info_layout = QVBoxLayout(info_widget)
                    info_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
                    info_layout.setSpacing(scale(5))
                    
                    title_label = QLabel(video['title'])
                    title_label.setStyleSheet(scale_style("font-size: 14px; font-weight: 500; color: #1e293b;"))
                    title_label.setWordWrap(True)
                    
                    stats_label = QLabel(f"播放: {video['play']} | 弹幕: {video['video_review']} | 收藏: {video['favorites']}")
                    stats_label.setStyleSheet(scale_style("font-size: 12px; color: #94a3b8;"))
                    
                    time_label = QLabel(f"时长: {video['length']}")
                    time_label.setStyleSheet(scale_style("font-size: 12px; color: #94a3b8;"))
                    
                    info_layout.addWidget(title_label)
                    info_layout.addWidget(stats_label)
                    info_layout.addWidget(time_label)
                    
                    layout.addWidget(cover_label)
                    layout.addWidget(info_widget, stretch=1)
                    
                    cover_btn = QPushButton("下载封面")
                    cover_btn.setFixedSize(scale(70), scale(26))
                    cover_btn.setStyleSheet(scale_style("""
                        QPushButton {
                            background-color: #4f6ef7;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            font-size: 10px;
                            font-weight: 500;
                        }
                        QPushButton:hover {
                            background-color: #3b5de7;
                        }
                    """))
                    cover_url = video.get('pic', '')
                    cover_btn.clicked.connect(lambda checked, url=cover_url, title=video['title']: self.download_single_cover(url, title))
                    layout.addWidget(cover_btn)
                    
                    item.setData(Qt.UserRole, video)
                    item.setSizeHint(widget.sizeHint())
                    self.videos_list.addItem(item)
                    self.videos_list.setItemWidget(item, widget)
                    
                    if video.get('pic'):
                        self.image_manager.enqueue(video['pic'], cover_label)
                
                self.current_video_index = end_index
                
                self.videos_label.setText(f"已加载 {self.current_video_index} / {len(self.pending_videos)} 个作品")
                
                if self.current_video_index < len(self.pending_videos):
                    QTimer.singleShot(50, self.load_videos_batch)
            
            def on_full_mode_changed(self, state):
                if state == Qt.Checked:
                    # 勾选完全模式时，自动全选所有视频
                    self.select_all_videos()
                    self.confirm_btn.setText("下载全部")
                    # 显示清晰度和音质选择
                    self.full_mode_quality_label.setVisible(True)
                    self.full_mode_quality_combo.setVisible(True)
                    self.full_mode_audio_label.setVisible(True)
                    self.full_mode_audio_combo.setVisible(True)
                else:
                    self.update_confirm_button()
                    # 隐藏清晰度和音质选择
                    self.full_mode_quality_label.setVisible(False)
                    self.full_mode_quality_combo.setVisible(False)
                    self.full_mode_audio_label.setVisible(False)
                    self.full_mode_audio_combo.setVisible(False)
            
            def is_full_mode(self):
                return self.full_mode_checkbox.isChecked()
            
            def get_all_videos(self):
                return self.videos
            
            def get_selected_quality(self):
                return self.full_mode_quality_combo.currentData()
            
            def get_selected_audio_quality(self):
                return self.full_mode_audio_combo.currentData()
        
        dialog = SpaceVideosDialog(self, space_info, videos)
        if dialog.exec_() == QDialog.Accepted:
            # 检查是否启用了完全模式
            if dialog.is_full_mode():
                # 完全模式：直接下载所有视频
                all_videos = dialog.get_all_videos()
                selected_quality = dialog.get_selected_quality()
                selected_audio_quality = dialog.get_selected_audio_quality()
                if all_videos and len(all_videos) > 0:
                    self.show_notification(f"完全模式：开始下载 {len(all_videos)} 个视频", "info")
                    # 直接开始下载所有视频，使用选中的清晰度和音质
                    self.download_space_videos(all_videos, space_info, selected_quality, selected_audio_quality)
                else:
                    self.signal_emitter.parse_finished.emit({"success": False, "error": "没有可下载的视频"})
            else:
                # 普通模式：解析选中的视频
                selected_videos = dialog.get_selected_videos()
                if selected_videos and len(selected_videos) > 0:
                    if len(selected_videos) == 1:
                        # 单个视频，直接解析
                        media_info = self.parser.parse_media("video", selected_videos[0]['bvid'], self.tv_mode_checkbox.isChecked())
                        self.signal_emitter.parse_finished.emit(media_info)
                    else:
                        # 多个视频，使用批量解析逻辑
                        urls = []
                        for video in selected_videos:
                            bvid = video.get('bvid')
                            if bvid:
                                video_url = f"https://www.bilibili.com/video/{bvid}"
                                urls.append(video_url)
                        
                        if urls:
                            # 关闭当前对话框后，在主线程中调用批量解析
                            QTimer.singleShot(0, lambda: self.start_batch_parse_with_urls(urls))
                        else:
                            self.signal_emitter.parse_finished.emit({"success": False, "error": "没有可解析的视频"})
                else:
                    self.signal_emitter.parse_finished.emit({"success": False, "error": "请选择要解析的视频"})
        else:
            self.signal_emitter.parse_finished.emit({"success": False, "error": "取消解析"})
    
    def update_ui_error(self, error_msg):
        try:
            print(f"=== 开始更新错误状态UI，错误信息：{error_msg}")
            
            # 确保所有UI控件都存在
            if hasattr(self, 'video_title'):
                self.video_title.setText("解析失败")
            else:
                print("错误：video_title控件不存在")
            
            if hasattr(self, 'duration_label'):
                self.duration_label.setText("-")
            else:
                print("错误：duration_label控件不存在")
            
            if hasattr(self, 'type_label'):
                self.type_label.setText("未解析")
            else:
                print("错误：type_label控件不存在")
            
            if hasattr(self, 'cover_label'):
                self.cover_label.setText("无封面")
                self.cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;"))
            else:
                print("错误：cover_label控件不存在")
            
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"解析失败：{error_msg[:30]}")
            else:
                print("错误：status_label控件不存在")
            
            # 显示错误通知
            self.show_notification(f"视频解析失败了：{error_msg}", "error")
            
            
            print("=== 错误状态UI更新完成 ===")
        except Exception as e:
            print(f"update_ui_error错误：{str(e)}")
            traceback.print_exc()
    
    def event(self, event):
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.User:
            if hasattr(event, 'all_download_tasks'):
                logger.info("收到CreateWindowEvent事件")
                try:
                    self.create_window_and_start_downloads_wrapper(
                        event.all_download_tasks,
                        event.success_count,
                        event.total_videos,
                        event.space_info
                    )
                    logger.info("CreateWindowEvent事件处理完成")
                except Exception as e:
                    logger.error(f"处理CreateWindowEvent事件时出错：{str(e)}")
                    import traceback
                    traceback.print_exc()
                return True
            return True
        try:
            return bool(super().event(event))
        except Exception:
            return True

    def create_window_and_start_downloads_wrapper(self, all_download_tasks, success_count, total_videos, space_info):
        """在主线程中创建批量下载窗口并添加所有任务的包装方法"""
        try:
            logger.info("=== 开始创建批量下载窗口 ===")
            
            # 检查all_download_tasks是否为空
            if not all_download_tasks:
                logger.error("all_download_tasks为空，无法创建批量下载窗口")
                self.show_notification("没有可下载的任务", "error")
                return
            
            # 显示解析进度窗口，用于显示添加任务的过程
            self.signal_emitter.show_parse_progress.emit()
            
            # 显示开始添加任务的通知
            self.show_notification(f"开始添加 {len(all_download_tasks)} 个任务到下载队列", "info")
            
            # 创建一个唯一的task_id用于标识这次批量下载
            import time
            batch_task_id = str(int(time.time() * 1000))
            
            logger.info(f"批量下载窗口任务ID：{batch_task_id}")
            logger.info(f"共有 {len(all_download_tasks)} 个任务要添加")
            
            # 检查self.download_manager是否存在
            if not self.download_manager:
                logger.error("self.download_manager不存在，无法创建批量下载窗口")
                self.show_notification("下载管理器不存在", "error")
                return
            
            # 检查BatchDownloadWindow是否存在
            try:
                from ui import BatchDownloadWindow
                logger.info("BatchDownloadWindow导入成功")
            except Exception as e:
                logger.error(f"导入BatchDownloadWindow失败：{str(e)}")
                self.show_notification(f"导入BatchDownloadWindow失败：{str(e)}", "error")
                return
            
            # 创建批量下载窗口
            logger.info("创建BatchDownloadWindow实例")
            batch_window = BatchDownloadWindow({"title": f"{space_info['name']} - 空间视频", "is_bangumi": False, "is_cheese": False}, 0, self.download_manager, self.parser)
            logger.info(f"BatchDownloadWindow实例创建成功：{batch_window}")
            
            # 连接信号
            logger.info("连接信号")
            batch_window.cancel_all.connect(self.on_cancel_download)
            self.download_manager.episode_progress_updated.connect(batch_window.update_episode_progress)
            self.download_manager.episode_finished.connect(batch_window.finish_episode)
            batch_window.window_closed.connect(lambda tid=batch_task_id: self.on_batch_window_closed(tid))
            logger.info("信号连接完成")
            
            # 确保窗口在最前面
            logger.info("设置窗口标志")
            from PyQt5.QtCore import Qt
            # 只添加WindowStaysOnTopHint标志，保留其他默认标志
            batch_window.setWindowFlags(batch_window.windowFlags() | Qt.WindowStaysOnTopHint)
            logger.info("窗口标志设置完成")
            
            # 先显示窗口
            logger.info("显示批量下载窗口")
            batch_window.show()
            batch_window.raise_()
            batch_window.activateWindow()
            logger.info("窗口显示完成")
            
            from PyQt5.QtWidgets import QApplication
            
            logger.info("添加任务到窗口")
            total_tasks = len(all_download_tasks)
            for i, (video, episodes, task_id, download_params) in enumerate(all_download_tasks):
                progress = int((i / total_tasks) * 100)
                if i % 50 == 0:
                    self.signal_emitter.parse_progress.emit(progress, f"添加任务 {i+1}/{total_tasks}...")
                    QApplication.processEvents()
                
                bvid = video.get('bvid')
                for j, ep in enumerate(episodes):
                    ep_name = f"{video.get('title', bvid)} - 第{ep.get('page', j+1)}集"
                    ep_tooltip = ep.get('title', '')
                    batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, j)
            
            # 显示处理完成的通知
            self.signal_emitter.parse_progress.emit(100, "任务添加完成")
            logger.info("任务添加完成")
            
            # 关闭解析进度窗口
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                logger.info("关闭解析进度窗口")
                QTimer.singleShot(1000, lambda: self.parse_progress_window.close())
            
            logger.info("强制处理事件，确保窗口显示")
            # 再次处理事件，确保窗口完全显示
            logger.info("事件处理完成")
            
            # 保存窗口引用
            self.batch_windows[batch_task_id] = batch_window
            logger.info(f"保存窗口引用，当前窗口数量：{len(self.batch_windows)}")
            
            # 开始下载所有任务
            logger.info("开始下载所有任务")
            for i, (_, _, _, download_params) in enumerate(all_download_tasks):
                self.download_manager.start_download(download_params)
                if i % 50 == 0:
                    QApplication.processEvents()
            logger.info("所有任务开始下载")
            
            # 显示完成通知
            logger.info(f"完全模式：已成功添加 {success_count}/{total_videos} 个视频到下载队列")
            self.show_notification(f"完全模式：已成功添加 {success_count}/{total_videos} 个视频到下载队列", "success")
            
            logger.info("=== 批量下载窗口创建完成 ===")
        except Exception as e:
            logger.error(f"创建批量下载窗口时出错：{str(e)}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"创建批量下载窗口失败：{str(e)}", "error")
            # 关闭解析进度窗口
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                logger.info("关闭解析进度窗口")
                QTimer.singleShot(1000, lambda: self.parse_progress_window.close())
    
    def download_space_videos(self, videos, space_info, selected_quality=None, selected_audio_quality=None):
        """处理空间视频下载"""
        logger.info("=== 开始处理空间视频下载 ===")
        logger.info(f"视频数量：{len(videos)}")
        logger.info(f"空间信息：{space_info}")
        
        # 显示解析进度窗口
        self.signal_emitter.show_parse_progress.emit()
        
        # 显示开始处理的通知
        self.show_notification(f"完全模式：开始处理 {len(videos)} 个视频", "info")
        
        # 在主线程中获取UI元素的值，避免在子线程中访问UI元素
        tv_mode = self.tv_mode_checkbox.isChecked() if hasattr(self, 'tv_mode_checkbox') else False
        save_path = self.path_edit.text().strip() if hasattr(self, 'path_edit') else ""
        if not save_path:
            save_path = self.config.get_app_setting("default_download_path", "")
        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), "Downloads", "Bilibili")
        os.makedirs(save_path, exist_ok=True)
        
        download_danmaku = self.config.get_app_setting("auto_download_danmaku", False)
        if hasattr(self, 'danmaku_checkbox'):
            download_danmaku = self.danmaku_checkbox.isChecked()
        danmaku_format = self.danmaku_format_combo.currentText() if hasattr(self, 'danmaku_format_combo') else 'XML'
        
        # 获取视频格式设置
        video_format = self.config.get_app_setting("video_output_format", "mp4")
        audio_format = self.config.get_app_setting("audio_output_format", "mp3")
        logger.info(f"视频格式：{video_format}, 音频格式：{audio_format}")
        
        # 弹幕设置
        logger.info(f"弹幕设置：{download_danmaku}, 格式：{danmaku_format}")
        
        # 获取默认清晰度（如果未指定则使用配置中的默认值）
        default_qn = selected_quality if selected_quality else self.config.get_app_setting("default_quality", 80)
        logger.info(f"默认清晰度：{default_qn}")
        
        # 创建一个线程来处理视频解析，避免阻塞UI线程
        class SpaceVideoParserThread(QThread):
            parse_done = pyqtSignal(list, int, int, dict)
            error = pyqtSignal(str)
            progress = pyqtSignal(int, str)
            
            def __init__(self, videos, space_info, parser, tv_mode, save_path, download_danmaku, danmaku_format, video_format, audio_format, default_qn, selected_audio_quality, config):
                super().__init__()
                self.videos = videos
                self.space_info = space_info
                self.parser = parser
                self.tv_mode = tv_mode
                self.save_path = save_path
                self.download_danmaku = download_danmaku
                self.danmaku_format = danmaku_format
                self.video_format = video_format
                self.audio_format = audio_format
                self.default_qn = default_qn
                self.selected_audio_quality = selected_audio_quality
                self.config = config
            
            def run(self):
                try:
                    logger.info("=== 开始处理视频 ===")
                    import time
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    
                    success_count = 0
                    total_videos = len(self.videos)
                    logger.info(f"处理视频数量：{total_videos}")
                    
                    all_download_tasks = []
                    max_workers = min(self.config.get_app_setting("max_threads", 4), 8, total_videos)
                    logger.info(f"并发解析线程数：{max_workers}")
                    
                    finished_count = [0]
                    parse_lock = threading.Lock()
                    
                    def parse_single_video(i, video):
                        try:
                            bvid = video.get('bvid')
                            if not bvid:
                                logger.warning("视频没有bvid，跳过")
                                return None
                            
                            logger.info(f"处理视频：{bvid} - {video.get('title', '未知标题')}")
                            
                            media_info = self.parser.parse_media("video", bvid, self.tv_mode)
                            
                            if not media_info.get('success'):
                                logger.warning(f"完全模式：解析视频 {bvid} 失败，跳过")
                                return None
                            
                            quality_options = media_info.get('qualities', [])
                            if quality_options:
                                selected_qn = self.default_qn
                                qn_available = [qn for qn, name in quality_options]
                                if selected_qn not in qn_available:
                                    selected_qn = qn_available[0] if qn_available else 80
                            else:
                                selected_qn = self.default_qn
                            logger.info(f"视频清晰度：{selected_qn}")
                            
                            task_id = str(int(time.time() * 1000) + i)
                            
                            episodes = []
                            if media_info.get('collection'):
                                episodes = media_info.get('collection', [])
                            elif media_info.get('episodes'):
                                episodes = media_info.get('episodes', [])
                            else:
                                episodes = [{
                                    'page': 1,
                                    'title': media_info.get('title', ''),
                                    'duration': media_info.get('duration', ''),
                                    'cid': media_info.get('cid', ''),
                                    'bvid': bvid
                                }]
                            logger.info(f"视频集数：{len(episodes)}")
                            
                            download_params = {
                                "url": f"https://www.bilibili.com/video/{bvid}",
                                "video_info": media_info,
                                "qn": selected_qn,
                                "save_path": self.save_path,
                                "episodes": episodes,
                                "resume_download": True,
                                "task_id": task_id,
                                "download_danmaku": self.download_danmaku,
                                "danmaku_format": self.danmaku_format,
                                "download_video": True,
                                "video_format": self.video_format,
                                "audio_format": self.audio_format,
                                "audio_quality": self.selected_audio_quality if self.selected_audio_quality else self.config.get_app_setting("audio_quality", 30280)
                            }
                            
                            logger.info(f"完全模式：已添加下载任务 {video.get('title', bvid)}")
                            return (video, episodes, task_id, download_params)
                            
                        except Exception as e:
                            logger.error(f"完全模式：处理视频 {video.get('bvid', 'unknown')} 时出错：{str(e)}")
                            return None
                        finally:
                            with parse_lock:
                                finished_count[0] += 1
                                progress = int((finished_count[0] / total_videos) * 100)
                            self.progress.emit(progress, f"处理视频 {finished_count[0]}/{total_videos}...")
                    
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {}
                        for i, video in enumerate(self.videos):
                            future = executor.submit(parse_single_video, i, video)
                            futures[future] = i
                        
                        for future in as_completed(futures):
                            try:
                                result = future.result()
                                if result is not None:
                                    all_download_tasks.append(result)
                                    success_count += 1
                            except Exception as e:
                                logger.error(f"完全模式：获取解析结果时出错：{str(e)}")
                    
                    self.progress.emit(100, "处理完成")
                    
                    logger.info(f"处理完成，共有 {len(all_download_tasks)} 个任务")
                    
                    self.parse_done.emit(all_download_tasks, success_count, len(self.videos), self.space_info)
                    
                except Exception as e:
                    logger.error(f"完全模式下载出错：{str(e)}")
                    import traceback
                    traceback.print_exc()
                    self.error.emit(str(e))
                finally:
                    logger.info("=== 处理完成 ===")
        
        # 创建并启动解析线程
        self.parser_thread = SpaceVideoParserThread(
            videos, space_info, self.parser, tv_mode, save_path, 
            download_danmaku, danmaku_format, video_format, audio_format, 
            default_qn, selected_audio_quality, self.config
        )
        
        # 设置线程的父对象为当前窗口，确保线程能够正确清理
        self.parser_thread.setParent(self)
        
        # 连接信号
        self.parser_thread.progress.connect(self.signal_emitter.parse_progress)
        self.parser_thread.parse_done.connect(self.on_space_videos_parsed)
        self.parser_thread.error.connect(lambda error: self.show_notification(f"完全模式下载失败：{error}", "error"))
        
        # 启动线程
        logger.info("启动空间视频解析线程")
        self.parser_thread.start()
    
    def on_space_videos_parsed(self, all_download_tasks, success_count, total_videos, space_info):
        """空间视频解析完成后的处理"""
        logger.info(f"空间视频解析完成，成功解析 {success_count} 个视频")
        
        # 检查all_download_tasks是否为空
        if not all_download_tasks:
            logger.error("all_download_tasks为空，无法创建批量下载窗口")
            self.show_notification("没有可下载的任务", "error")
            # 关闭解析进度窗口
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                logger.info("关闭解析进度窗口")
                QTimer.singleShot(1000, lambda: self.parse_progress_window.close())
            return
        
        # 直接在主线程中创建批量下载窗口
        logger.info("直接在主线程中创建批量下载窗口")
        self.create_window_and_start_downloads_wrapper(all_download_tasks, success_count, total_videos, space_info)
        logger.info("窗口创建完成")
    
    def update_ui(self, video_info):
        try:
            print("=== 开始更新UI ===")
            print(f"视频信息：{video_info}")
            
            # 直接使用类属性获取控件
            video_title = self.video_title
            type_label = self.type_label
            duration_label = self.duration_label
            cover_label = self.cover_label
            quality_combo = self.quality_combo
            select_episode_btn = self.select_episode_btn
            
            # 确保所有需要的控件都存在
            if not hasattr(self, 'video_title'):
                print("错误：video_title控件不存在")
                return
            if not hasattr(self, 'type_label'):
                print("错误：type_label控件不存在")
                return
            if not hasattr(self, 'duration_label'):
                print("错误：duration_label控件不存在")
                return
            if not hasattr(self, 'cover_label'):
                print("错误：cover_label控件不存在")
                return
            if not hasattr(self, 'quality_combo'):
                print("错误：quality_combo控件不存在")
                return
            if not hasattr(self, 'select_episode_btn'):
                print("错误：select_episode_btn控件不存在")
                return
            
            # 确保状态标签存在
            status_label = None
            if hasattr(self, 'status_label'):
                status_label = self.status_label
            else:
                print("错误：status_label控件不存在")
                return
            
            # 确保下载按钮存在
            download_btn = None
            cancel_btn = None
            if hasattr(self, 'download_btn'):
                download_btn = self.download_btn
            else:
                print("错误：download_btn控件不存在")
                return
            if hasattr(self, 'cancel_btn'):
                cancel_btn = self.cancel_btn
            else:
                print("错误：cancel_btn控件不存在")
                return
            
            # 确保弹幕计数标签存在
            danmaku_count_label = None
            if hasattr(self, 'danmaku_count_label'):
                danmaku_count_label = self.danmaku_count_label
            
            title = video_info.get("title", "未知标题")
            print(f"设置标题：{title}")
            video_title.setText(title)
            
            is_bangumi = video_info.get("is_bangumi", False)
            is_cheese = video_info.get("is_cheese", False)
            is_interact = video_info.get("is_interact", False)
            
            if is_bangumi:
                video_type = "番剧"
                type_style = "color: #ff6b6b; font-weight: 500;"
                group_style = "QGroupBox { border: 2px solid #ff6b6b; border-radius: 10px; } QGroupBox::title { color: #ff6b6b; }"
            elif is_cheese:
                video_type = "课程"
                type_style = "color: #4ecdc4; font-weight: 500;"
                group_style = "QGroupBox { border: 2px solid #4ecdc4; border-radius: 10px; } QGroupBox::title { color: #4ecdc4; }"
            elif is_interact:
                video_type = "互动视频"
                type_style = "color: #45b7d1; font-weight: 500;"
                group_style = "QGroupBox { border: 2px solid #45b7d1; border-radius: 10px; } QGroupBox::title { color: #45b7d1; }"
            else:
                video_type = "普通视频"
                type_style = "color: #409eff; font-weight: 500;"
                group_style = "QGroupBox { border: 2px solid #409eff; border-radius: 10px; } QGroupBox::title { color: #409eff; }"
            
            print(f"设置视频类型：{video_type}")
            type_label.setText(video_type)
            type_label.setStyleSheet(type_style)
            
            # 查找视频信息组
            video_info_group = None
            for child in self.findChildren(QGroupBox):
                if child.title() == "解析结果":
                    video_info_group = child
                    break
            if video_info_group:
                print("设置视频信息组样式")
                video_info_group.setStyleSheet(group_style)
            else:
                print("警告：未找到视频信息组")
            
            duration = video_info.get("duration", "")
            if not duration:
                collection = video_info.get("collection", [])
                if collection:
                    duration = collection[0].get("duration_str", "")
            print(f"设置时长：{duration}")
            duration_label.setText(duration if duration else "-")
            
            print("设置状态标签")
            status_label.setText("解析成功，请选择集数、清晰度并开始下载")
            
            cover_url = video_info.get("pic", "")
            if not cover_url:
                if is_bangumi and video_info.get("bangumi_info"):
                    cover_url = video_info["bangumi_info"].get("cover", "")
                elif is_cheese and video_info.get("cheese_info"):
                    cover_url = video_info["cheese_info"].get("cover", "")
            
            if cover_url:
                print(f"加载封面：{cover_url}")
                
                class CoverLoader(QThread):
                    cover_ready = pyqtSignal(QPixmap)
                    
                    def __init__(self, url):
                        super().__init__()
                        self.url = url
                    
                    def run(self):
                        try:
                            response = requests.get(self.url, timeout=10)
                            response.raise_for_status()
                            pixmap = QPixmap()
                            pixmap.loadFromData(response.content)
                            self.cover_ready.emit(pixmap)
                        except:
                            self.cover_ready.emit(QPixmap())
                
                loader = CoverLoader(cover_url)
                if not hasattr(self, 'cover_loaders'):
                    self.cover_loaders = []
                self.cover_loaders.append(loader)  
                
                def on_cover_loaded(pixmap):
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(scale(180), scale(120), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        cover_label.setPixmap(scaled_pixmap)
                        cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 8px;"))
                    else:
                        cover_label.setText("加载失败")
                        cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;"))
                    
                    if loader in self.cover_loaders:
                        self.cover_loaders.remove(loader)
                
                loader.cover_ready.connect(on_cover_loaded)
                loader.start()
            else:
                print("无封面")
                cover_label.setText("无封面")
                cover_label.setStyleSheet(scale_style("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;"))
            
            # 启用相关控件
            print("启用控件")
            if video_info.get("qualities"):
                while quality_combo.count() > 1:
                    quality_combo.removeItem(1)
                
                # 获取用户登录和VIP状态
                is_vip = video_info.get("is_vip", False)
                
                for qn, name in video_info["qualities"]:
                    # 根据qn值添加适当的标签
                    if qn in [112, 120, 125, 126, 127]:
                        display_name = f"{name}（会员）"
                    elif qn == 80:
                        display_name = f"{name}（登录）"
                    elif qn == 64:
                        display_name = f"{name}（登录）"
                    else:
                        display_name = name
                    quality_combo.addItem(display_name, qn)
                
                quality_combo.setEnabled(True)
                # 默认选择最高质量（第一个可用选项）
                if quality_combo and quality_combo.count() > 1:
                    quality_combo.setCurrentIndex(1)
                    self.selected_qn = quality_combo.itemData(1)
            
            # 更新音频质量选择
            if hasattr(self, 'audio_quality_combo'):
                audio_quality_combo = self.audio_quality_combo
                while audio_quality_combo.count() > 1:
                    audio_quality_combo.removeItem(1)
                
                # 音频质量名称映射
                audio_quality_map = {
                    30251: "Hi-Res无损",
                    30250: "杜比全景声",
                    100010: "高音质 (320K)",
                    30280: "高音质 (192K)",
                    100009: "标准音质 (192K)",
                    30232: "标准音质 (132K)",
                    100008: "低音质 (128K)",
                    30216: "低音质 (64K)"
                }
                
                # 从视频信息中获取实际支持的音频质量
                audio_qualities = []
                if video_info.get('audio_qualities'):
                    # 如果视频信息中包含音频质量信息，使用它
                    audio_qualities = video_info['audio_qualities']
                elif video_info.get('episodes') and len(video_info['episodes']) > 0:
                    # 如果视频信息中包含集数信息，尝试从第一个集数中获取音频质量信息
                    first_episode = video_info['episodes'][0]
                    if first_episode.get('audio_qualities'):
                        audio_qualities = first_episode['audio_qualities']
                
                # 如果没有获取到音频质量信息，使用默认的音频质量选项
                if not audio_qualities:
                    # 使用默认的音频质量选项
                    default_audio_qualities = [
                        (30280, "高音质 (192K)"),
                        (30232, "标准音质 (132K)"),
                        (30216, "低音质 (64K)")
                    ]
                    for audio_id, quality_name in default_audio_qualities:
                        audio_quality_combo.addItem(quality_name, audio_id)
                else:
                    # 只添加视频实际支持的音频质量选项
                    for audio_id, quality_name in audio_qualities:
                        audio_quality_combo.addItem(quality_name, audio_id)
                
                audio_quality_combo.setEnabled(True)
                # 默认选择第一个可用选项（最高质量）
                if audio_quality_combo and audio_quality_combo.count() > 1:
                    audio_quality_combo.setCurrentIndex(1)
            
            # 启用下载按钮（无论是否选择集数，因为可以只下载弹幕）
            download_btn.setEnabled(True)
            cancel_btn.setEnabled(True)
            select_episode_btn.setEnabled(True)
            
            if hasattr(self, 'save_main_cover_btn'):
                self.save_main_cover_btn.setEnabled(True)
            
            # 启用完全模式复选框
            if hasattr(self, 'full_mode_checkbox'):
                self.full_mode_checkbox.setEnabled(True)
                
                # 检查是否勾选了完全模式，如果是则自动全选集数并下载
                if self.full_mode_checkbox.isChecked():
                    # 自动全选集数
                    self.auto_select_all_episodes()
                    # 延迟一点时间后自动开始完全模式下载
                    QTimer.singleShot(500, self.on_full_mode_download)
            
            # 获取弹幕信息
            print("获取弹幕信息")
            if hasattr(self, 'danmaku_count_label'):
                cid = video_info.get("cid", "")
                # 尝试从episodes或collection中获取cid
                if not cid:
                    # 检查番剧
                    if video_info.get("is_bangumi") and video_info.get("bangumi_info"):
                        episodes = video_info["bangumi_info"].get("episodes", [])
                        if episodes:
                            cid = episodes[0].get("cid", "")
                    # 检查课程
                    elif video_info.get("is_cheese") and video_info.get("cheese_info"):
                        episodes = video_info["cheese_info"].get("episodes", [])
                        if episodes:
                            cid = episodes[0].get("cid", "")
                    # 检查普通合集
                    elif video_info.get("collection"):
                        collection = video_info.get("collection", [])
                        if collection:
                            cid = collection[0].get("cid", "")
                    # 检查episodes
                    elif video_info.get("episodes"):
                        episodes = video_info.get("episodes", [])
                        if episodes:
                            cid = episodes[0].get("cid", "")
                
                if cid:
                    print(f"获取弹幕，cid: {cid}")
                    import threading
                    logger = logging.getLogger(__name__)
                    def get_danmaku_info():
                        try:
                            if not hasattr(self, 'parser') or not self.parser:
                                print("parser未初始化，无法获取弹幕信息")
                                def update_danmaku_error():
                                    try:
                                        self.danmaku_count_label.setText("获取失败")
                                    except Exception as e:
                                        print(f"更新弹幕错误UI失败：{str(e)}")
                                QTimer.singleShot(0, update_danmaku_error)
                                return
                            
                            print(f"开始获取弹幕信息，cid: {cid}")
                            danmaku_video_info = self.parser.get_danmaku(cid)
                            print(f"获取弹幕信息结果: {danmaku_video_info}")
                            if danmaku_video_info.get('error') == "":
                                count = danmaku_video_info.get('data', {}).get('count', 0)
                                print(f"弹幕数量：{count}条")
                                self.current_danmaku_data = danmaku_video_info
                                def update_danmaku_count():
                                    try:
                                        print(f"更新弹幕数量UI：{count}条")
                                        self.select_danmaku_btn.setEnabled(True)
                                        self.danmaku_count_label.setText(f"{count}条")
                                        print("弹幕数量UI更新成功")
                                    except Exception as e:
                                        print(f"更新弹幕数量UI失败：{str(e)}")
                                QTimer.singleShot(0, update_danmaku_count)
                            else:
                                print("弹幕获取失败")
                                def update_danmaku_error():
                                    try:
                                        self.danmaku_count_label.setText("获取失败")
                                    except Exception as e:
                                        print(f"更新弹幕错误UI失败：{str(e)}")
                                QTimer.singleShot(0, update_danmaku_error)
                        except Exception as e:
                            print(f"获取弹幕信息失败：{str(e)}")
                            traceback.print_exc()
                            def update_danmaku_error():
                                try:
                                    self.danmaku_count_label.setText("获取失败")
                                except Exception as e:
                                    print(f"更新弹幕错误UI失败：{str(e)}")
                            QTimer.singleShot(0, update_danmaku_error)
                    
                    thread = threading.Thread(target=get_danmaku_info, daemon=True)
                    thread.start()
                else:
                    print("未找到cid")
                    print("未找到cid，无法获取弹幕信息")
                    self.danmaku_count_label.setText("无cid")
            else:
                print("警告：danmaku_count_label控件不存在")
            
            print("强制更新UI")
            
            # 输出解析文本框的文字
            if hasattr(self, 'status_label'):
                print(f"解析文本框文字：{self.status_label.text()}")
            
            # 输出弹幕数量label
            if hasattr(self, 'danmaku_count_label'):
                print(f"弹幕数量label：{self.danmaku_count_label.text()}")
            
            print("=== UI更新完成 ===")
            
            # 更新封面下载tab
            self.update_cover_tab()
        except Exception as e:
            print(f"update_ui错误：{str(e)}")
            traceback.print_exc()

    def update_cover_tab(self):
        try:
            if not hasattr(self, 'cover_preview_label'):
                return
            
            if not self.current_video_info:
                self.cover_preview_label.setText("请先解析视频以获取封面")
                self.cover_preview_label.setPixmap(QPixmap())
                if hasattr(self, 'save_cover_btn'):
                    self.save_cover_btn.setEnabled(False)
                if hasattr(self, 'batch_download_cover_btn'):
                    self.batch_download_cover_btn.setEnabled(False)
                return
            
            video_info = self.current_video_info
            self.cover_data_list = []
            
            main_cover_url = video_info.get("pic", "")
            is_bangumi = video_info.get("is_bangumi", False)
            is_cheese = video_info.get("is_cheese", False)
            
            if not main_cover_url:
                if is_bangumi and video_info.get("bangumi_info"):
                    main_cover_url = video_info["bangumi_info"].get("cover", "")
                elif is_cheese and video_info.get("cheese_info"):
                    main_cover_url = video_info["cheese_info"].get("cover", "")
            
            if main_cover_url:
                self.cover_data_list.append({
                    "url": main_cover_url,
                    "title": video_info.get("title", "主封面"),
                    "type": "main"
                })
            
            episodes = []
            if is_bangumi and video_info.get("bangumi_info"):
                episodes = video_info["bangumi_info"].get("episodes", [])
            elif is_cheese and video_info.get("cheese_info"):
                episodes = video_info["cheese_info"].get("episodes", [])
            elif video_info.get("collection"):
                episodes = video_info.get("collection", [])
            elif video_info.get("episodes"):
                episodes = video_info.get("episodes", [])
            
            for i, ep in enumerate(episodes):
                ep_cover = ep.get("pic", "") or ep.get("cover", "")
                if ep_cover and ep_cover != main_cover_url:
                    ep_title = ep.get("title", ep.get("index_title", f"第{i+1}集"))
                    self.cover_data_list.append({
                        "url": ep_cover,
                        "title": ep_title,
                        "type": "episode"
                    })
            
            if hasattr(self, 'cover_list_widget'):
                self.cover_list_widget.clear()
                for i, cover_data in enumerate(self.cover_data_list):
                    item_widget = QWidget()
                    item_widget.setAutoFillBackground(True)
                    item_widget.setFixedSize(scale(100), scale(80))
                    item_widget.setStyleSheet(scale_style("""
                        QWidget {
                            background-color: white;
                            border-radius: 4px;
                            border: 1px solid #e0e4ea;
                        }
                    """))
                    item_layout = QVBoxLayout(item_widget)
                    item_layout.setContentsMargins(scale(4), scale(4), scale(4), scale(4))
                    item_layout.setSpacing(scale(2))
                    
                    thumb_label = QLabel()
                    thumb_label.setFixedSize(scale(90), scale(50))
                    thumb_label.setAlignment(Qt.AlignCenter)
                    thumb_label.setStyleSheet(scale_style("""
                        QLabel {
                            background-color: #f0f2f5;
                            border-radius: 3px;
                            color: #8b95a5;
                            font-size: 9px;
                        }
                    """))
                    thumb_label.setText("加载中...")
                    item_layout.addWidget(thumb_label)
                    
                    name_label = QLabel(cover_data["title"])
                    name_label.setFixedHeight(scale(14))
                    name_label.setStyleSheet(scale_style("""
                        QLabel {
                            font-size: 9px;
                            color: #3a3f4b;
                            background: transparent;
                        }
                    """))
                    name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    name_label.setWordWrap(False)
                    item_layout.addWidget(name_label)
                    
                    list_item = QListWidgetItem()
                    list_item.setSizeHint(QSize(scale(100), scale(80)))
                    list_item.setData(Qt.UserRole, cover_data)
                    
                    self.cover_list_widget.addItem(list_item)
                    self.cover_list_widget.setItemWidget(list_item, item_widget)
                    
                    if cover_data["url"]:
                        class CoverThumbLoader(QThread):
                            class Signals(QObject):
                                finished = pyqtSignal(QLabel, QPixmap)
                            
                            def __init__(self, url, label):
                                super().__init__()
                                self.url = url
                                self.label = label
                                self.signals = self.Signals()
                            
                            def run(self):
                                try:
                                    response = requests.get(self.url, timeout=10)
                                    response.raise_for_status()
                                    pixmap = QPixmap()
                                    pixmap.loadFromData(response.content)
                                    self.signals.finished.emit(self.label, pixmap)
                                except:
                                    self.signals.finished.emit(self.label, QPixmap())
                        
                        def on_thumb_loaded(label, pixmap):
                            try:
                                if not pixmap.isNull():
                                    scaled = pixmap.scaled(scale(90), scale(50), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                                    cw = min(scaled.width(), scale(90))
                                    ch = min(scaled.height(), scale(50))
                                    x = (scaled.width() - cw) // 2
                                    y = (scaled.height() - ch) // 2
                                    cropped = scaled.copy(x, y, cw, ch)
                                    label.setPixmap(cropped)
                                    label.setStyleSheet("background: transparent; border: none;")
                                else:
                                    label.setText("加载失败")
                            except:
                                pass
                        
                        thumb_loader = CoverThumbLoader(cover_data["url"], thumb_label)
                        thumb_loader.signals.finished.connect(on_thumb_loaded)
                        thumb_loader.start()
                        
                        if not hasattr(self, 'cover_thumb_loaders'):
                            self.cover_thumb_loaders = []
                        self.cover_thumb_loaders.append(thumb_loader)
            
            if self.cover_data_list:
                first_cover = self.cover_data_list[0]
                self.load_cover_preview(first_cover["url"])
                if hasattr(self, 'save_cover_btn'):
                    self.save_cover_btn.setEnabled(True)
                if hasattr(self, 'batch_download_cover_btn'):
                    self.batch_download_cover_btn.setEnabled(len(self.cover_data_list) > 0)
            else:
                self.cover_preview_label.setText("未找到封面信息")
                self.cover_preview_label.setPixmap(QPixmap())
                if hasattr(self, 'save_cover_btn'):
                    self.save_cover_btn.setEnabled(False)
                if hasattr(self, 'batch_download_cover_btn'):
                    self.batch_download_cover_btn.setEnabled(False)
        except Exception as e:
            print(f"update_cover_tab错误：{str(e)}")
            traceback.print_exc()
    
    def load_cover_preview(self, url):
        if not url or not hasattr(self, 'cover_preview_label'):
            return
        
        self.cover_preview_label.setText("加载中...")
        self.cover_preview_label.setPixmap(QPixmap())
        
        class PreviewLoader(QThread):
            class Signals(QObject):
                finished = pyqtSignal(QPixmap)
            
            def __init__(self, url):
                super().__init__()
                self.url = url
                self.signals = self.Signals()
            
            def run(self):
                try:
                    response = requests.get(self.url, timeout=15)
                    response.raise_for_status()
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    self.signals.finished.emit(pixmap)
                except:
                    self.signals.finished.emit(QPixmap())
        
        def on_preview_loaded(pixmap):
            try:
                if not pixmap.isNull():
                    self.current_cover_pixmap = pixmap
                    label_w = self.cover_preview_label.width()
                    label_h = self.cover_preview_label.height()
                    if label_w > 0 and label_h > 0:
                        scaled = pixmap.scaled(label_w - scale(10), label_h - scale(10), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    else:
                        scaled = pixmap.scaled(scale(320), scale(180), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.cover_preview_label.setPixmap(scaled)
                    self.cover_preview_label.setStyleSheet(scale_style("""
                        QLabel {
                            background-color: #f7f8fa;
                            border: 1px solid #e0e4ea;
                            border-radius: 6px;
                        }
                    """))
                else:
                    self.current_cover_pixmap = None
                    self.cover_preview_label.setText("封面加载失败")
                    self.cover_preview_label.setStyleSheet(scale_style("""
                        QLabel {
                            background-color: #f7f8fa;
                            border: 1px dashed #d0d5dd;
                            border-radius: 6px;
                            color: #8b95a5;
                            font-size: 10px;
                        }
                    """))
            except:
                pass
        
        loader = PreviewLoader(url)
        loader.signals.finished.connect(on_preview_loaded)
        loader.start()
        
        if not hasattr(self, 'cover_preview_loaders'):
            self.cover_preview_loaders = []
        self.cover_preview_loaders.append(loader)
    
    def on_cover_list_item_clicked(self, item):
        cover_data = item.data(Qt.UserRole)
        if cover_data and cover_data.get("url"):
            self.load_cover_preview(cover_data["url"])
    
    def on_save_main_cover(self):
        if not self.current_video_info:
            self.show_notification("请先解析视频", "warning")
            return
        
        cover_url = self.current_video_info.get("pic", "")
        is_bangumi = self.current_video_info.get("is_bangumi", False)
        is_cheese = self.current_video_info.get("is_cheese", False)
        if not cover_url:
            if is_bangumi and self.current_video_info.get("bangumi_info"):
                cover_url = self.current_video_info["bangumi_info"].get("cover", "")
            elif is_cheese and self.current_video_info.get("cheese_info"):
                cover_url = self.current_video_info["cheese_info"].get("cover", "")
        
        if not cover_url:
            self.show_notification("未找到封面信息", "warning")
            return
        
        title = self.current_video_info.get("title", "cover")
        safe_title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or "cover"
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存封面", os.path.join(os.path.expanduser("~"), "Desktop", f"{safe_title}.png"),
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;BMP图片 (*.bmp);;所有文件 (*)"
        )
        
        if save_path:
            self.show_notification("正在下载封面...", "info")
            import threading
            def download_cover():
                try:
                    response = requests.get(cover_url, timeout=15)
                    response.raise_for_status()
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        pixmap.save(save_path)
                        self.show_notification(f"封面已保存到：{os.path.basename(save_path)}", "success")
                    else:
                        self.show_notification("封面数据无效", "error")
                except Exception as e:
                    self.show_notification(f"保存失败：{str(e)}", "error")
            thread = threading.Thread(target=download_cover, daemon=True)
            thread.start()
    
    def on_batch_cover_download(self, link_data):
        video_info = link_data.get('video_info')
        if not video_info:
            self.show_notification("请先解析视频", "warning")
            return
        
        cover_url = video_info.get("pic", "")
        is_bangumi = video_info.get("is_bangumi", False)
        is_cheese = video_info.get("is_cheese", False)
        if not cover_url:
            if is_bangumi and video_info.get("bangumi_info"):
                cover_url = video_info["bangumi_info"].get("cover", "")
            elif is_cheese and video_info.get("cheese_info"):
                cover_url = video_info["cheese_info"].get("cover", "")
        
        if not cover_url:
            self.show_notification("未找到封面信息", "warning")
            return
        
        title = video_info.get("title", "cover")
        safe_title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or "cover"
        
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存封面", os.path.join(os.path.expanduser("~"), "Desktop", f"{safe_title}.png"),
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;BMP图片 (*.bmp);;所有文件 (*)"
        )
        
        if save_path:
            self.show_notification("正在下载封面...", "info")
            import threading
            def download_cover():
                try:
                    response = requests.get(cover_url, timeout=15)
                    response.raise_for_status()
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        pixmap.save(save_path)
                        self.show_notification(f"封面已保存到：{os.path.basename(save_path)}", "success")
                    else:
                        self.show_notification("封面数据无效", "error")
                except Exception as e:
                    self.show_notification(f"保存失败：{str(e)}", "error")
            thread = threading.Thread(target=download_cover, daemon=True)
            thread.start()
    
    def on_save_cover(self):
        if not self.current_cover_pixmap or self.current_cover_pixmap.isNull():
            self.show_notification("没有可保存的封面", "warning")
            return
        
        title = ""
        if self.current_video_info:
            title = self.current_video_info.get("title", "cover")
        title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or "cover"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存封面", os.path.join(os.path.expanduser("~"), "Desktop", f"{title}.png"),
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;BMP图片 (*.bmp);;所有文件 (*)"
        )
        
        if file_path:
            try:
                self.current_cover_pixmap.save(file_path)
                self.show_notification(f"封面已保存到：{os.path.basename(file_path)}", "success")
            except Exception as e:
                self.show_notification(f"保存失败：{str(e)}", "error")
    
    def on_batch_download_covers(self):
        if not self.cover_data_list:
            self.show_notification("没有可下载的封面", "warning")
            return
        
        save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录", os.path.expanduser("~"))
        if not save_dir:
            return
        
        self.show_notification("开始批量下载封面...", "info")
        
        import threading
        
        def download_all():
            success_count = 0
            fail_count = 0
            for i, cover_data in enumerate(self.cover_data_list):
                try:
                    url = cover_data["url"]
                    title = cover_data.get("title", f"cover_{i+1}")
                    safe_title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or f"cover_{i+1}"
                    
                    response = requests.get(url, timeout=15)
                    response.raise_for_status()
                    
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    
                    if not pixmap.isNull():
                        file_path = os.path.join(save_dir, f"{safe_title}.png")
                        pixmap.save(file_path)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1
            
            def show_result():
                msg = f"批量下载完成：成功 {success_count} 个"
                if fail_count > 0:
                    msg += f"，失败 {fail_count} 个"
                self.show_notification(msg, "success" if fail_count == 0 else "warning")
            
            QTimer.singleShot(0, show_result)
        
        thread = threading.Thread(target=download_all, daemon=True)
        thread.start()
    
    def on_select_all_content(self):
        if not hasattr(self, 'content_list'):
            return
        self.content_list.selectAll()
        if hasattr(self, 'parse_favorite_btn'):
            self.parse_favorite_btn.setEnabled(True)
        if hasattr(self, 'download_cover_favorite_btn'):
            self.download_cover_favorite_btn.setEnabled(True)
        self.update_card_selection_styles()
    
    def on_download_selected_covers(self):
        selected_items = self.content_list.selectedItems()
        if not selected_items:
            self.show_notification("请选择要下载封面的内容", "warning")
            return
        
        save_dir = QFileDialog.getExistingDirectory(self, "选择保存目录", os.path.expanduser("~"))
        if not save_dir:
            return
        
        self.show_notification("开始下载选中封面...", "info")
        
        import threading
        
        def download_selected():
            success_count = 0
            fail_count = 0
            for item in selected_items:
                try:
                    content_item = item.data(Qt.UserRole)
                    if not content_item:
                        continue
                    
                    cover_url = content_item.get("cover", "")
                    if not cover_url:
                        fail_count += 1
                        continue
                    
                    title = content_item.get("title", "cover")
                    safe_title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or "cover"
                    
                    response = requests.get(cover_url, timeout=15)
                    response.raise_for_status()
                    
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    
                    if not pixmap.isNull():
                        file_path = os.path.join(save_dir, f"{safe_title}.png")
                        pixmap.save(file_path)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1
            
            def show_result():
                msg = f"封面下载完成：成功 {success_count} 个"
                if fail_count > 0:
                    msg += f"，失败 {fail_count} 个"
                self.show_notification(msg, "success" if fail_count == 0 else "warning")
            
            QTimer.singleShot(0, show_result)
        
        thread = threading.Thread(target=download_selected, daemon=True)
        thread.start()
    
    def parse_favorite_video(self, bvid):
        if not bvid:
            self.show_notification("无BV号，无法解析", "error")
            return
        video_url = f"https://www.bilibili.com/video/{bvid}"
        self.tab_widget.setCurrentIndex(0)
        self.url_edit.setText(video_url)
        self.on_parse()
    
    def download_favorite_cover(self, cover_url, title):
        if not cover_url:
            self.show_notification("该视频没有封面信息", "warning")
            return
        safe_title = "".join(c for c in title if c.isalnum() or c in "_ -()[]（）【】") or "cover"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存封面", os.path.join(os.path.expanduser("~"), "Desktop", f"{safe_title}.png"),
            "PNG图片 (*.png);;JPEG图片 (*.jpg);;BMP图片 (*.bmp);;所有文件 (*)"
        )
        if save_path:
            self.show_notification("正在下载封面...", "info")
            import threading
            def download():
                try:
                    response = requests.get(cover_url, timeout=15)
                    response.raise_for_status()
                    pixmap = QPixmap()
                    pixmap.loadFromData(response.content)
                    if not pixmap.isNull():
                        pixmap.save(save_path)
                        self.show_notification(f"封面已保存到：{os.path.basename(save_path)}", "success")
                    else:
                        self.show_notification("封面数据无效", "error")
                except Exception as e:
                    self.show_notification(f"保存失败：{str(e)}", "error")
            thread = threading.Thread(target=download, daemon=True)
            thread.start()
    
    def on_folder_search_changed(self, text):
        if not hasattr(self, 'folder_list'):
            return
        
        search_text = text.strip().lower()
        for i in range(self.folder_list.count()):
            item = self.folder_list.item(i)
            if search_text:
                item_title = (item.data(Qt.UserRole + 1) or '').lower()
                item.setHidden(search_text not in item_title)
            else:
                item.setHidden(False)
    
    def open_episode_selection(self):
        if not self.current_video_info:
            return
        is_bangumi = self.current_video_info.get("is_bangumi", False)
        is_cheese = self.current_video_info.get("is_cheese", False)
        episodes = []
        if is_bangumi:
            episodes = self.current_video_info["bangumi_info"].get("episodes", [])
        elif is_cheese:
            episodes = self.current_video_info["cheese_info"].get("episodes", [])
        else:
            episodes = self.current_video_info.get("collection", [])
        if not episodes:
            self.show_notification("这个视频没有分集可以选择哦", "info")
            return

        dialog = EpisodeSelectionDialog(self, episodes, is_bangumi or is_cheese, self.selected_episodes)
        if dialog.exec_() == QDialog.Accepted:
            self.selected_episodes = dialog.selected_episodes
            self.select_episode_btn.setText(f"已选{len(self.selected_episodes)}集")
            self.select_episode_btn.setToolTip("点击修改集数选择")
            
            # 启用弹幕下载选项
            if hasattr(self, 'danmaku_checkbox'):
                self.danmaku_checkbox.setEnabled(True)
            if hasattr(self, 'danmaku_format_combo'):
                self.danmaku_format_combo.setEnabled(True)
            if hasattr(self, 'select_danmaku_btn'):
                self.select_danmaku_btn.setEnabled(True)

    def auto_select_all_episodes(self):
        if not self.current_video_info:
            return
        
        is_bangumi = self.current_video_info.get("is_bangumi", False)
        is_cheese = self.current_video_info.get("is_cheese", False)
        episodes = []
        
        if is_bangumi:
            episodes = self.current_video_info["bangumi_info"].get("episodes", [])
        elif is_cheese:
            episodes = self.current_video_info["cheese_info"].get("episodes", [])
        else:
            # 检查是否有 collection 或 episodes
            if self.current_video_info.get("collection"):
                episodes = self.current_video_info.get("collection", [])
            elif self.current_video_info.get("episodes"):
                episodes = self.current_video_info.get("episodes", [])
        
        if episodes:
            self.selected_episodes = episodes.copy()
            self.select_episode_btn.setText(f"已选{len(self.selected_episodes)}集")
            self.select_episode_btn.setToolTip("点击修改集数选择")
            
            # 启用弹幕下载选项
            if hasattr(self, 'danmaku_checkbox'):
                self.danmaku_checkbox.setEnabled(True)
            if hasattr(self, 'danmaku_format_combo'):
                self.danmaku_format_combo.setEnabled(True)
            if hasattr(self, 'select_danmaku_btn'):
                self.select_danmaku_btn.setEnabled(True)
    
    def open_danmaku_selection(self):
        if not hasattr(self, 'current_danmaku_data') or not self.current_danmaku_data:
            self.show_notification("请先解析视频获取弹幕信息", "warning")
            return
        
        danmakus = self.current_danmaku_data.get('data', {}).get('danmaku', [])
        if not danmakus:
            self.show_notification("当前视频没有弹幕", "info")
            return
        
        # 打开弹幕选择对话框
        dialog = DanmakuSelectionDialog(self, danmakus, self.selected_danmakus)
        if dialog.exec_() == QDialog.Accepted:
            self.selected_danmakus = dialog.get_selected_danmakus()
            self.select_danmaku_btn.setText(f"已选{len(self.selected_danmakus)}条")
            self.select_danmaku_btn.setToolTip("点击修改弹幕选择")

    def on_download(self):
        if not self.current_video_info:
            self.show_notification("请先解析视频链接哦", "warning")
            return
        
        # 获取自动下载设置
        auto_download_danmaku = self.config.get_app_setting("auto_download_danmaku", False)
        auto_download_cover = self.config.get_app_setting("auto_download_cover", True)
        
        # 获取弹幕下载设置（优先使用界面设置，如果没有则使用自动设置）
        download_danmaku = auto_download_danmaku
        if hasattr(self, 'danmaku_checkbox'):
            download_danmaku = self.danmaku_checkbox.isChecked()
        elif hasattr(self, 'download_danmaku_checkbox'):
            download_danmaku = self.download_danmaku_checkbox.isChecked()
        
        danmaku_format = self.danmaku_format_combo.currentText() if hasattr(self, 'danmaku_format_combo') else 'XML'
        
        # 检查是否只下载弹幕
        download_video = True  # 默认下载视频
        if hasattr(self, 'download_video_checkbox'):
            download_video = self.download_video_checkbox.isChecked()
        
        # 无论是下载视频还是只下载弹幕，都需要选择集数
        if not self.selected_episodes:
            self.show_notification("请先选择要下载的集数哦", "warning")
            return
        
        if download_video:
            if not self.selected_qn:
                self.show_notification("请选择视频清晰度哦", "warning")
                return
            selected_qn = self.selected_qn
        else:
            # 只下载弹幕时，使用默认清晰度
            selected_qn = 80  # 1080P
        
        save_path = self.path_edit.text().strip()
        if not save_path:
            self.show_notification("请选择视频保存路径哦", "warning")
            return
        os.makedirs(save_path, exist_ok=True)
        
        url = self.url_edit.text().strip()
        
        # 如果只下载弹幕且没有选择集数，使用第一个集数
        episodes = self.selected_episodes
        if not episodes and download_danmaku and not download_video:
            # 尝试从视频信息中获取第一个集数
            if self.current_video_info.get("is_bangumi") and self.current_video_info.get("bangumi_info"):
                episodes = [self.current_video_info["bangumi_info"].get("episodes", [])[0]] if self.current_video_info["bangumi_info"].get("episodes", []) else []
            elif self.current_video_info.get("is_cheese") and self.current_video_info.get("cheese_info"):
                episodes = [self.current_video_info["cheese_info"].get("episodes", [])[0]] if self.current_video_info["cheese_info"].get("episodes", []) else []
            elif self.current_video_info.get("collection"):
                episodes = [self.current_video_info.get("collection", [])[0]] if self.current_video_info.get("collection", []) else []
            elif self.current_video_info.get("episodes"):
                episodes = [self.current_video_info.get("episodes", [])[0]] if self.current_video_info.get("episodes", []) else []
            else:
                # 如果没有集数信息，创建一个默认的集数
                episodes = [self.current_video_info.copy()]
        
        task_exists = False
        existing_task_id = None
        if hasattr(self, 'download_manager') and self.download_manager:
            
            if hasattr(self.download_manager, 'active_tasks'):
                for existing_task_id, existing_task in self.download_manager.active_tasks.items():
                    
                    if existing_task.get('url') == url and existing_task.get('qn') == selected_qn:
                        
                        existing_episodes = existing_task.get('episodes', [])
                        if len(existing_episodes) == len(episodes):
                            
                            all_episodes_match = True
                            for i, ep in enumerate(episodes):
                                if i < len(existing_episodes):
                                    existing_ep = existing_episodes[i]
                                    
                                    if (ep.get('ep_index') != existing_ep.get('ep_index') or 
                                        ep.get('page') != existing_ep.get('page')):
                                        all_episodes_match = False
                                        break
                                else:
                                    all_episodes_match = False
                                    break
                            if all_episodes_match:
                                task_exists = True
                                break
        
        if task_exists:
            
            for window in self.batch_windows.values():
                if isinstance(window, BatchDownloadWindow):
                    window.show()
                    return
        
        
        task_id = str(int(time.time() * 1000))
        
        # 获取用户选择的音频质量
        audio_quality = 30280  # 默认高音质
        if hasattr(self, 'audio_quality_combo') and self.audio_quality_combo.currentIndex() > 0:
            audio_quality = self.audio_quality_combo.currentData()
        else:
            # 如果没有选择，使用配置中的值
            audio_quality = self.config.get_app_setting("audio_quality", 30280)
        
        download_params = {
            "url": url,
            "video_info": self.current_video_info,
            "qn": selected_qn,
            "save_path": save_path,
            "episodes": episodes,
            "resume_download": True,
            "task_id": task_id,
            "download_danmaku": download_danmaku,
            "danmaku_format": danmaku_format,
            "download_video": download_video,
            "video_format": self.config.get_app_setting("video_output_format", "mp4"),
            "audio_format": self.config.get_app_setting("audio_output_format", "mp3"),
            "audio_quality": audio_quality
        }
        
        
        existing_window = None
        for window in self.batch_windows.values():
            if isinstance(window, BatchDownloadWindow):
                existing_window = window
                break
        
        if existing_window:
            
            for i, ep in enumerate(episodes):
                if self.current_video_info.get("is_bangumi") or self.current_video_info.get("is_cheese"):
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                
                existing_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
            existing_window.show()
            existing_window.raise_()  # 确保窗口在最前面
            existing_window.activateWindow()  # 激活窗口
        else:
            
            batch_window = BatchDownloadWindow(self.current_video_info, 0, self.download_manager, self.parser)
            for i, ep in enumerate(episodes):
                if self.current_video_info.get("is_bangumi") or self.current_video_info.get("is_cheese"):
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                
                batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
            batch_window.cancel_all.connect(self.on_cancel_download)
            batch_window.window_closed.connect(lambda tid=task_id: self.on_batch_window_closed(tid))
            batch_window.show()
            batch_window.raise_()  # 确保窗口在最前面
            batch_window.activateWindow()  # 激活窗口
            
            self.batch_windows[task_id] = batch_window
        
        
        time.sleep(0.1)  
        
        logger.info(f"BilibiliDownloader：直接调用下载方法，任务ID：{task_id}")
        if self.download_manager:
            self.download_manager.start_download(download_params)
            logger.info(f"BilibiliDownloader：下载方法已调用")
        else:
            logger.error("BilibiliDownloader：下载管理器未初始化")
        
        self.download_btn.setEnabled(False)

    def on_full_mode_download(self):
        if not self.current_video_info:
            self.show_notification("请先解析视频链接哦", "warning")
            return
        
        # 获取自动下载设置
        auto_download_danmaku = self.config.get_app_setting("auto_download_danmaku", False)
        auto_download_cover = self.config.get_app_setting("auto_download_cover", True)
        
        # 获取弹幕下载设置
        download_danmaku = auto_download_danmaku
        if hasattr(self, 'danmaku_checkbox'):
            download_danmaku = self.danmaku_checkbox.isChecked()
        
        danmaku_format = self.danmaku_format_combo.currentText() if hasattr(self, 'danmaku_format_combo') else 'XML'
        
        # 检查是否只下载弹幕
        download_video = True
        if hasattr(self, 'download_video_checkbox'):
            download_video = self.download_video_checkbox.isChecked()
        
        # 完全模式下自动全选集数
        if not self.selected_episodes:
            self.auto_select_all_episodes()
        
        if not self.selected_episodes:
            self.show_notification("没有可下载的集数", "warning")
            return
        
        if download_video:
            if not self.selected_qn:
                self.show_notification("请选择视频清晰度哦", "warning")
                return
            selected_qn = self.selected_qn
        else:
            selected_qn = 80
        
        save_path = self.path_edit.text().strip()
        if not save_path:
            self.show_notification("请选择视频保存路径哦", "warning")
            return
        os.makedirs(save_path, exist_ok=True)
        
        url = self.url_edit.text().strip()
        episodes = self.selected_episodes
        
        # 检查是否已存在相同的下载任务
        task_exists = False
        if hasattr(self, 'download_manager') and self.download_manager:
            if hasattr(self.download_manager, 'active_tasks'):
                for existing_task_id, existing_task in self.download_manager.active_tasks.items():
                    if existing_task.get('url') == url and existing_task.get('qn') == selected_qn:
                        existing_episodes = existing_task.get('episodes', [])
                        if len(existing_episodes) == len(episodes):
                            all_episodes_match = True
                            for i, ep in enumerate(episodes):
                                if i < len(existing_episodes):
                                    existing_ep = existing_episodes[i]
                                    if (ep.get('ep_index') != existing_ep.get('ep_index') or 
                                        ep.get('page') != existing_ep.get('page')):
                                        all_episodes_match = False
                                        break
                                else:
                                    all_episodes_match = False
                                    break
                            if all_episodes_match:
                                task_exists = True
                                break
        
        if task_exists:
            self.show_notification("相同的下载任务已存在", "info")
            return
        
        task_id = str(int(time.time() * 1000))
        
        # 获取用户选择的音频质量
        audio_quality = 30280  # 默认高音质
        if hasattr(self, 'audio_quality_combo') and self.audio_quality_combo.currentIndex() > 0:
            audio_quality = self.audio_quality_combo.currentData()
        else:
            # 如果没有选择，使用配置中的值
            audio_quality = self.config.get_app_setting("audio_quality", 30280)
        
        download_params = {
            "url": url,
            "video_info": self.current_video_info,
            "qn": selected_qn,
            "save_path": save_path,
            "episodes": episodes,
            "resume_download": True,
            "task_id": task_id,
            "download_danmaku": download_danmaku,
            "danmaku_format": danmaku_format,
            "download_video": download_video,
            "video_format": self.config.get_app_setting("video_output_format", "mp4"),
            "audio_format": self.config.get_app_setting("audio_output_format", "mp3"),
            "audio_quality": audio_quality
        }
        
        # 完全模式也弹出批量下载窗口显示进度
        logger.info(f"完全模式：开始下载，任务ID：{task_id}，共{len(episodes)}集")
        
        # 检查是否已有批量下载窗口
        existing_window = None
        for window in self.batch_windows.values():
            if isinstance(window, BatchDownloadWindow):
                existing_window = window
                break
        
        if existing_window:
            # 使用已有的窗口添加新的下载任务
            for i, ep in enumerate(episodes):
                if self.current_video_info.get("is_bangumi") or self.current_video_info.get("is_cheese"):
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                
                existing_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
            existing_window.show()
            existing_window.raise_()
            existing_window.activateWindow()
        else:
            # 创建新的批量下载窗口
            batch_window = BatchDownloadWindow(self.current_video_info, 0, self.download_manager, self.parser)
            for i, ep in enumerate(episodes):
                if self.current_video_info.get("is_bangumi") or self.current_video_info.get("is_cheese"):
                    ep_name = f"{ep.get('ep_index', '')}"
                    ep_tooltip = ep.get('ep_title', '')
                else:
                    ep_name = f"第{ep.get('page', i+1)}集"
                    ep_tooltip = ep.get('title', '')
                
                batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
            batch_window.cancel_all.connect(self.on_cancel_download)
            batch_window.window_closed.connect(lambda tid=task_id: self.on_batch_window_closed(tid))
            batch_window.show()
            batch_window.raise_()
            batch_window.activateWindow()
            
            self.batch_windows[task_id] = batch_window
        
        # 开始下载
        if self.download_manager:
            self.download_manager.start_download(download_params)
            self.show_notification(f"完全模式：已开始下载{len(episodes)}集视频", "success")
        else:
            logger.error("完全模式：下载管理器未初始化")
            self.show_notification("下载管理器未初始化", "error")
        
        self.download_btn.setEnabled(False)

    def on_cancel_download(self):
        self.signal_emitter.cancel_download.emit()
        self.cleanup_temp_files()

    def cleanup_temp_files(self):
        # 临时文件现在保存在下载目录中，不需要单独清理
        pass

    def update_user_info(self, user_info):
        try:
            self._update_user_info_impl(user_info)
        except Exception:
            pass

    def _update_user_info_impl(self, user_info):
        if user_info.get("success"):
            self.user_info_label.setText("已登录")
            if user_info.get("is_vip"):
                self.vip_label.setText("√ 会员")
                self.vip_label.setStyleSheet("color: #faad14;")
            else:
                self.vip_label.setText("× 普通用户")
                self.vip_label.setStyleSheet("color: #6b7280;")
            
            if hasattr(self, 'login_info_label'):
                username = user_info.get("uname", user_info.get("msg", "用户"))
                self.login_info_label.setText(username)
                self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px;"))
                
                if hasattr(self, 'login_info_widget'):
                    self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                    def handle_click(event):
                        self.on_user_info_click(event)
                    self.login_info_widget.mousePressEvent = handle_click
                
                avatar_url = user_info.get("face", "")
                if avatar_url and hasattr(self, 'avatar_label'):
                    import threading
                    def fetch_avatar(url=avatar_url):
                        try:
                            headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Referer": "https://www.bilibili.com/"
                            }
                            response = requests.get(url, headers=headers, timeout=5)
                            if response.status_code == 200:
                                self.signal_emitter.avatar_loaded.emit(response.content)
                        except Exception as e:
                            logger.error(f"下载头像失败：{e}")
                    
                    t = threading.Thread(target=fetch_avatar, daemon=True)
                    t.start()
            
            self._update_resolution_combo(is_login=True, is_vip=user_info.get("is_vip", False))
        else:
            self.user_info_label.setText("未登录")
            self.vip_label.setText("× 未登录")
            self.vip_label.setStyleSheet("color: #6b7280;")
            
            if hasattr(self, 'login_info_label'):
                self.login_info_label.setText("如果想要解析会员内容请登录")
                self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px;"))
                self.login_info_label.setCursor(QCursor(Qt.PointingHandCursor))
                self.login_info_label.mousePressEvent = self.on_login_click
            
            self.load_default_avatar()
            
            self._update_resolution_combo(is_login=False, is_vip=False)
    
    def _update_resolution_combo(self, is_login=False, is_vip=False):
        if not hasattr(self, 'resolution_combo'):
            return
        
        # 保存当前选择
        current_text = self.resolution_combo.currentText()
        
        # 清空并重新添加选项
        self.resolution_combo.clear()
        
        if is_vip:
            # VIP用户显示所有分辨率
            self.resolution_combo.addItems(["1080P+", "1080P", "720P", "480P", "360P"])
        elif is_login:
            # 普通登录用户显示到1080P
            self.resolution_combo.addItems(["1080P", "720P", "480P", "360P"])
        else:
            # 未登录用户只显示480P和360P
            self.resolution_combo.addItems(["480P", "360P"])
        
        # 尝试恢复之前的选择
        index = self.resolution_combo.findText(current_text)
        if index >= 0:
            self.resolution_combo.setCurrentIndex(index)
        else:
            self.resolution_combo.setCurrentIndex(0)

    def update_login_info_display(self):
        if hasattr(self, 'login_info_widget') and hasattr(self, 'login_info_label') and hasattr(self, 'avatar_label'):
            if hasattr(self, 'parser') and self.parser and hasattr(self.parser, 'cookies') and self.parser.cookies:
                
                try:
                    user_info = self.parser.user_info
                    if user_info and user_info.get("success"):
                        username = user_info.get("uname", "用户")
                        self.login_info_label.setText(username)
                        self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px;"))
                        
                        avatar_url = user_info.get("face", "")
                        if avatar_url:
                            import threading
                            def fetch_avatar(url=avatar_url):
                                try:
                                    headers = {
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                        "Referer": "https://www.bilibili.com/"
                                    }
                                    response = requests.get(url, headers=headers, timeout=5)
                                    if response.status_code == 200:
                                        self.signal_emitter.avatar_loaded.emit(response.content)
                                except Exception as e:
                                    logger.error(f"下载头像失败：{e}")
                            t = threading.Thread(target=fetch_avatar, daemon=True)
                            t.start()
                        
                        self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                        def handle_click(event):
                            self.on_user_info_click(event)
                        self.login_info_widget.mousePressEvent = handle_click
                        
                        if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                            self.user_info_label.setText("已登录")
                            if user_info.get("is_vip"):
                                self.vip_label.setText("√ 会员")
                                self.vip_label.setStyleSheet("color: #faad14;")
                            else:
                                self.vip_label.setText("× 普通用户")
                                self.vip_label.setStyleSheet("color: #6b7280;")
                    else:
                        self.login_info_label.setText("如果想要解析会员内容请登录")
                        self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px;"))
                        
                        self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                        self.login_info_widget.mousePressEvent = self.on_login_click
                        
                        if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                            self.user_info_label.setText("未登录")
                            self.vip_label.setText("× 未登录")
                            self.vip_label.setStyleSheet("color: #6b7280;")
                        
                        self.load_default_avatar()
                except Exception as e:
                    logger.error(f"更新登录信息显示失败：{e}")
                    self.login_info_label.setText("如果想要解析会员内容请登录")
                    self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px;"))
                    
                    self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                    self.login_info_widget.mousePressEvent = self.on_login_click
                    
                    if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                        self.user_info_label.setText("未登录")
                        self.vip_label.setText("× 未登录")
                        self.vip_label.setStyleSheet("color: #6b7280;")
                    
                    self.load_default_avatar()
            else:
                
                self.login_info_label.setText("如果想要解析会员内容请登录")
                self.login_info_label.setStyleSheet(scale_style("color: #ffffff; font-size: 12px;"))
                
                self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                self.login_info_widget.mousePressEvent = self.on_login_click
                
                if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                    self.user_info_label.setText("未登录")
                    self.vip_label.setText("× 未登录")
                    self.vip_label.setStyleSheet("color: #6b7280;")
                
                self.load_default_avatar()
                
                self.show_cookie_ui()

    def on_avatar_loaded(self, avatar_data):
        try:
            pixmap = QPixmap()
            if pixmap.loadFromData(avatar_data) and not pixmap.isNull():
                pixmap = pixmap.scaled(scale(24), scale(24), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                path = QPainterPath()
                path.addEllipse(0, 0, 24, 24)
                round_pixmap = QPixmap(24, 24)
                round_pixmap.fill(Qt.transparent)
                painter = QPainter(round_pixmap)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, 24, 24, pixmap)
                painter.end()
                self.avatar_label.setPixmap(round_pixmap)
                self.avatar_label.setStyleSheet(scale_style("border-radius: 12px;"))
            else:
                self.load_default_avatar()
        except Exception as e:
            logger.error(f"设置头像失败：{e}")
            self.load_default_avatar()

    def load_default_avatar(self):
        import threading
        def fetch_default():
            try:
                url = "https://static.hdslb.com/images/member/noface.gif"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.bilibili.com/"
                }
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    self.signal_emitter.avatar_loaded.emit(response.content)
            except Exception as e:
                logger.error(f"加载默认头像失败：{e}")
        t = threading.Thread(target=fetch_default, daemon=True)
        t.start()

    def load_avatar(self, avatar_url):
        print(f"开始加载头像，URL：{avatar_url}")
        try:
            print("使用requests库下载头像")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/"
            }
            response = requests.get(avatar_url, headers=headers, timeout=5)
            if response.status_code == 200:
                print(f"获取到头像数据，大小：{len(response.content)}字节")
                
                pixmap = QPixmap()
                success = pixmap.loadFromData(response.content)
                if success and not pixmap.isNull():
                    pixmap = pixmap.scaled(scale(24), scale(24), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    
                    path = QPainterPath()
                    path.addEllipse(0, 0, 24, 24)
                    
                    round_pixmap = QPixmap(24, 24)
                    round_pixmap.fill(Qt.transparent)
                    
                    painter = QPainter(round_pixmap)
                    painter.setClipPath(path)
                    painter.drawPixmap(0, 0, 24, 24, pixmap)
                    painter.end()
                    
                    self.avatar_label.setPixmap(round_pixmap)
                    self.avatar_label.setStyleSheet(scale_style("border-radius: 12px;"))
                    print("头像显示成功")
                else:
                    print("头像数据无效")
            else:
                print(f"下载头像失败，状态码：{response.status_code}")
        except Exception as e:
            print(f"加载头像失败：{e}")
            import traceback
            traceback.print_exc()
    
    def update_hevc_status(self, supported):
        try:
            if supported:
                self.hevc_label.setText("√ 已支持HEVC（HDR/杜比视界）")
                self.hevc_label.setStyleSheet("color: #52c41a;")
            else:
                self.hevc_label.setText("× 未支持HEVC（需安装扩展）")
                self.hevc_label.setStyleSheet("color: #fa8c16;")
            self.hevc_btn.setEnabled(True)
        except Exception:
            pass

    def update_hevc_progress(self, progress):
        try:
            self.main_progress.setValue(progress)
            self.status_label.setText(f"下载HEVC扩展：{progress}%")
        except Exception:
            pass

    def on_hevc_install_finish(self, success, msg):
        try:
            self.main_progress.setValue(0)
            self.hevc_btn.setEnabled(not success)
            if success:
                self.show_notification(f"操作成功啦：{msg}", "success")
                self.signal_emitter.check_hevc.emit()
                self.status_label.setText("HEVC扩展安装成功")
            else:
                self.show_notification(f"操作失败了：{msg}", "error")
                self.status_label.setText("HEVC扩展安装失败")
        except Exception:
            pass

    def update_download_progress(self, progress, status):
        try:
            self._update_download_progress_impl(progress, status)
        except Exception:
            pass

    def _update_download_progress_impl(self, progress, status):
        if not hasattr(self, 'last_main_progress') or progress % 5 == 0 or progress == 100 or self.last_main_status != status:
            self.main_progress.setValue(progress)
            self.status_label.setText(status)
            
            self.last_main_progress = progress
            self.last_main_status = status

    def update_episode_progress(self, *args):
        try:
            self._update_episode_progress_impl(*args)
        except Exception:
            pass

    def _update_episode_progress_impl(self, *args):
        if len(args) == 4:
            task_id, ep_index, progress, status = args
            
            # 处理主窗口的下载进度
            if hasattr(self, 'download_container_layout') and hasattr(self, 'download_tasks') and self.download_container_layout:
                task_key = f"{task_id}_ep{ep_index}"
                
                # 处理待处理的进度
                if hasattr(self, 'pending_progress') and task_key in self.pending_progress:
                    pending_info = self.pending_progress[task_key]
                    progress = pending_info['progress']
                    status = pending_info['status']
                    del self.pending_progress[task_key]
                
                # 创建新的任务进度 widget
                if task_key not in self.download_tasks:
                    task_widget = QWidget()
                    task_widget.setStyleSheet(scale_style("background-color: #f0fdf4; border-radius: 8px; padding: 12px; margin-bottom: 8px;"))
                    task_layout = QVBoxLayout(task_widget)
                    task_layout.setContentsMargins(scale(8), scale(8), scale(8), scale(8))
                    task_layout.setSpacing(scale(8))
                    
                    video_name = status.split(' - ')[0] if ' - ' in status else status
                    video_name_label = QLabel(video_name)
                    video_name_label.setStyleSheet(scale_style("font-size: 14px; font-weight: 500; color: #166534;"))
                    video_name_label.setMinimumHeight(scale(24))
                    video_name_label.setMaximumWidth(scale(380))
                    video_name_label.setToolTip(status)
                    video_name_label.setWordWrap(True)
                    
                    progress_bar = QProgressBar()
                    progress_bar.setRange(0, 100)
                    progress_bar.setMinimumHeight(scale(14))
                    progress_bar.setStyleSheet(scale_style("QProgressBar { border-radius: 6px; background-color: #dcfce7; } QProgressBar::chunk { border-radius: 6px; background-color: #22c55e; }"))
                    
                    progress_text = QLabel(f"{int(progress)}%")
                    progress_text.setStyleSheet(scale_style("font-size: 12px; color: #64748b; font-weight: 500;"))
                    progress_text.setAlignment(Qt.AlignRight)
                    
                    task_layout.addWidget(video_name_label)
                    task_layout.addWidget(progress_bar)
                    task_layout.addWidget(progress_text)
                    
                    try:
                        self.download_container_layout.addWidget(task_widget)
                        self.download_tasks[task_key] = {
                            'widget': task_widget,
                            'name_label': video_name_label,
                            'progress_bar': progress_bar,
                            'progress_text': progress_text
                        }
                    except Exception as e:
                        print(f"添加剧集进度条失败：{str(e)}")
                
                # 更新进度
                if task_key in self.download_tasks:
                    task_info = self.download_tasks[task_key]
                    try:
                        task_info['progress_bar'].setValue(int(progress))
                        task_info['progress_text'].setText(f"{int(progress)}%")
                        task_info['name_label'].setToolTip(status)
                        
                        if "下载" in status and "流" in status:
                            status_parts = status.split('：')
                            if len(status_parts) > 0:
                                video_name = status_parts[0]
                                task_info['name_label'].setText(video_name)
                        elif "合并" in status:
                            task_info['name_label'].setText("合并音视频")
                        elif "完成" in status:
                            task_info['name_label'].setText("下载完成")
                    except Exception as e:
                        print(f"更新剧集进度失败：{str(e)}")
            
            # 转发给其他窗口
            for window in self.batch_windows.values():
                if window:
                    window.update_episode_progress(task_id, ep_index, progress, status)
            
            if hasattr(self, 'floating_ball') and self.floating_ball:
                self.floating_ball.update_episode_progress(task_id, ep_index, progress, status)
        elif len(args) == 3:
            index, progress, status = args
            
            for window in self.batch_windows.values():
                if window:
                    try:
                        index = int(index)
                        window.update_episode_progress(index, progress, status)
                    except ValueError:
                        pass

    def finish_episode(self, *args):
        try:
            self._finish_episode_impl(*args)
        except Exception:
            pass

    def _finish_episode_impl(self, *args):
        if len(args) == 4:
            task_id, ep_index, success, message = args

            if message == "TASK_PAUSED":
                return

            # 主窗口显示通知
            if success:
                self.show_notification(f"视频下载完成：{message}", "success")
                
                # 下载完成后打开文件夹
                auto_open_folder = self.config.get_app_setting("auto_open_folder", False)
                if auto_open_folder:
                    try:
                        import subprocess
                        import re
                        import os
                        # 从消息中提取文件路径
                        match = re.search(r'完成：视频：(.+?)\.mp4', message)
                        if match:
                            # 获取保存路径
                            save_path = self.config.get_app_setting("save_path", os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载"))
                            folder_path = save_path
                            if os.path.exists(folder_path):
                                if os.name == 'nt':  # Windows
                                    subprocess.run(['explorer', folder_path], shell=True)
                                elif os.name == 'posix':  # macOS/Linux
                                    subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', folder_path])
                    except Exception as e:
                        print(f"打开文件夹失败：{str(e)}")
            else:
                self.show_notification(f"视频下载失败：{message}", "error")

            # 转发给其他窗口
            for window in self.batch_windows.values():
                if window and window.isVisible():
                    window.finish_episode(task_id, ep_index, success, message)

            # 检查视频兼容性并处理
            if success:
                self._check_and_convert_video(task_id, ep_index, message)
        elif len(args) == 3:
            index, success, message = args

            if message == "TASK_PAUSED":
                return

            # 主窗口显示通知
            if success:
                self.show_notification(f"视频下载完成：{message}", "success")
                
                # 下载完成后打开文件夹
                auto_open_folder = self.config.get_app_setting("auto_open_folder", False)
                if auto_open_folder:
                    try:
                        import subprocess
                        import re
                        import os
                        # 从消息中提取文件路径
                        match = re.search(r'完成：视频：(.+?)\.mp4', message)
                        if match:
                            # 获取保存路径
                            save_path = self.config.get_app_setting("save_path", os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载"))
                            folder_path = save_path
                            if os.path.exists(folder_path):
                                if os.name == 'nt':  # Windows
                                    subprocess.run(['explorer', folder_path], shell=True)
                                elif os.name == 'posix':  # macOS/Linux
                                    subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', folder_path])
                    except Exception as e:
                        print(f"打开文件夹失败：{str(e)}")
            else:
                self.show_notification(f"视频下载失败：{message}", "error")

            # 转发给其他窗口
            for window in self.batch_windows.values():
                if window and window.isVisible():
                    window.finish_episode(index, success, message)

            # 检查视频兼容性并处理
            if success:
                self._check_and_convert_video(None, index, message)
        
        # 检查是否所有下载任务都已完成
        all_completed = True
        if hasattr(self, 'download_manager') and self.download_manager:
            if hasattr(self.download_manager, 'active_tasks'):
                all_completed = len(self.download_manager.active_tasks) == 0
        
        # 如果所有任务都已完成，重新启用下载按钮
        if all_completed and hasattr(self, 'download_btn'):
            self.download_btn.setEnabled(True)
            if hasattr(self, 'status_label'):
                self.status_label.setText("下载完成，可继续选择其他内容下载")

    def on_batch_window_closed(self, task_id=None):
        # 从 batch_windows 中移除已关闭的窗口
        if task_id and task_id in self.batch_windows:
            del self.batch_windows[task_id]
        
        # 重新启用下载按钮
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # 更新状态标签
        self.status_label.setText("下载窗口已关闭，可重新开始下载")

    def _check_hevc_before_download(self, selected_videos, save_path):
        try:
            import os

            if not hasattr(self, 'parser') or not self.parser:
                return

            # 检查HEVC是否支持
            hevc_supported = self.parser.check_hevc_support()
            if hevc_supported:
                return

            # 获取视频编码信息（这里通过API获取，实际视频下载后才能确定，但可以检测B站返回的编码格式）
            has_hevc = False
            for ep in selected_videos:
                ep_title = ep.get('title', ep.get('ep_title', f"第{ep.get('ep_index', 0)+1}集"))
                # 检测是否有HEVC/AV1编码的剧集（通过检查dash信息）
                video_urls = ep.get('video_urls', {})
                if video_urls:
                    for qn, url in video_urls.items():
                        if 'hevc' in str(url).lower() or 'av01' in str(url).lower():
                            has_hevc = True
                            break

            if not has_hevc:
                return

            # 显示询问对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("检测到不兼容编码")
            dialog.setMinimumSize(scale(500), scale(200))
            dialog.setStyleSheet(self.styleSheet())

            layout = QVBoxLayout(dialog)

            label = QLabel(f"检测到选中的视频包含HEVC/AV1编码，您的电脑尚未安装对应的解码器。\n\n是否现在安装HEVC解码器扩展？\n（安装后可正常播放HEVC/AV1编码的视频）")
            label.setWordWrap(True)
            layout.addWidget(label)

            dont_ask_checkbox = QCheckBox("不再询问（可随时在设置中重新开启）")
            layout.addWidget(dont_ask_checkbox)

            btn_layout = QHBoxLayout()
            install_btn = QPushButton("安装解码器")
            install_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; padding: 8px 16px; border-radius: 4px;"))
            skip_btn = QPushButton("跳过（下载后手动转换）")
            skip_btn.setStyleSheet(scale_style("padding: 8px 16px; border-radius: 4px;"))

            btn_layout.addWidget(install_btn)
            btn_layout.addWidget(skip_btn)
            layout.addLayout(btn_layout)

            def on_install():
                self.signal_emitter.install_hevc.emit()
                if dont_ask_checkbox.isChecked():
                    self.config.set_app_setting("hevc_not_supported_ask", False)
                dialog.accept()

            def on_skip():
                if dont_ask_checkbox.isChecked():
                    self.config.set_app_setting("hevc_not_supported_ask", False)
                dialog.accept()

            install_btn.clicked.connect(on_install)
            skip_btn.clicked.connect(on_skip)

            dialog.exec_()

        except Exception as e:
            print(f"HEVC检测失败：{str(e)}")

    def _check_and_convert_video(self, task_id, ep_index, message):
        try:
            import os
            import re

            if not hasattr(self, 'parser') or not self.parser:
                return

            auto_convert = self.config.get_app_setting("auto_convert_incompatible", False)
            if not auto_convert:
                return

            match = re.search(r'完成：(.+\.mp4)', message)
            if not match:
                return

            video_path = match.group(1)
            if not os.path.exists(video_path):
                return

            codec_info = self.parser.check_video_codec_compatible(video_path)
            if codec_info.get("compatible", True):
                return

            codec_name = codec_info.get("codec", "unknown")
            output_path = video_path.rsplit('.', 1)[0] + f"_{codec_name}_converted.mp4"

            self.show_notification(f"检测到{codec_name}编码视频，正在转换为H.264...", "info")

            def progress_callback(progress):
                pass

            success, result_msg = self.parser.convert_video_to_h264(video_path, output_path, progress_callback)
            if success:
                self.show_notification(f"视频转换成功：{os.path.basename(output_path)}", "success")
            else:
                self.show_notification(f"视频转换失败：{result_msg}", "error")

        except Exception as e:
            print(f"视频兼容性检查失败：{str(e)}")

    def toggle_maximize(self):
        
        if not self.isMaximized():
            self.showMaximized()

    def custom_close(self):
        if hasattr(self, 'task_manager') and self.task_manager:
            downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
            if downloading_tasks:
                dialog = QDialog(self)
                dialog.setWindowTitle("确认退出")
                dialog.setMinimumSize(scale(400), scale(200))
                dialog.setStyleSheet(get_base_style())

                main_layout = QVBoxLayout(dialog)
                main_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
                main_layout.setSpacing(scale(15))

                task_count = len(downloading_tasks)
                message = f"有 {task_count} 个下载任务尚未完成，确定要退出吗？"
                label = QLabel(message)
                label.setWordWrap(True)
                main_layout.addWidget(label)

                background_checkbox = QCheckBox("在后台继续任务")
                main_layout.addWidget(background_checkbox)

                btn_layout = QHBoxLayout()
                
                view_btn = QPushButton("查看任务")
                def on_view_tasks():
                    if hasattr(self, 'task_manager') and hasattr(self, 'parser') and hasattr(self, 'download_manager'):
                        task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config, self)
                        task_window.show()
                        task_window.raise_()
                    dialog.accept()
                view_btn.clicked.connect(on_view_tasks)
                btn_layout.addWidget(view_btn)
                
                cancel_btn = QPushButton("取消")
                cancel_btn.clicked.connect(dialog.reject)
                btn_layout.addWidget(cancel_btn)
                
                close_btn = QPushButton("关闭")
                def on_confirm_close():
                    if not background_checkbox.isChecked():
                        dialog.accept()
                        if hasattr(self, 'download_manager') and self.download_manager:
                            self.download_manager.cancel_all()
                        if hasattr(self, 'task_manager') and self.task_manager:
                            downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
                            for task in downloading_tasks:
                                self.task_manager.update_task_status(task['id'], 'failed', '异常中断')
                        self._close_with_animation()
                    else:
                        self.hide()
                        dialog.accept()
                close_btn.clicked.connect(on_confirm_close)
                btn_layout.addWidget(close_btn)
                
                main_layout.addLayout(btn_layout)

                video_info = dialog.exec_()
                if video_info == QDialog.Rejected:
                    return
            else:
                self._close_with_animation()
        else:
            self._close_with_animation()

    def _close_with_animation(self):
        try:
            self._cleanup_before_exit()
        except Exception as e:
            logger.error(f"清理失败：{str(e)}")
        
        opacity = 1.0
        
        def fade_out():
            nonlocal opacity
            opacity -= 0.05
            if opacity >= 0:
                try:
                    self.setWindowOpacity(opacity)
                    QTimer.singleShot(15, fade_out)
                except RuntimeError:
                    pass
            else:
                try:
                    self.hide()
                    QApplication.instance().quit()
                    import os
                    os._exit(0)
                except RuntimeError:
                    import os
                    os._exit(0)
        
        fade_out()

    def closeEvent(self, event):
        try:
            for loader in self.cover_loaders:
                if loader.isRunning():
                    loader.terminate()
                    loader.wait(100)
            self.cover_loaders.clear()
        except Exception:
            pass
        try:
            if hasattr(self, 'task_manager') and self.task_manager:
                downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
                if downloading_tasks:
                    dialog = QDialog(self)
                    dialog.setWindowTitle("确认退出")
                    dialog.setMinimumSize(scale(400), scale(200))
                    dialog.setStyleSheet(get_base_style())

                    main_layout = QVBoxLayout(dialog)
                    main_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
                    main_layout.setSpacing(scale(15))

                    task_count = len(downloading_tasks)
                    message = f"有 {task_count} 个下载任务尚未完成，确定要退出吗？"
                    label = QLabel(message)
                    label.setWordWrap(True)
                    main_layout.addWidget(label)

                    self.background_checkbox = QCheckBox("在后台继续任务")
                    main_layout.addWidget(self.background_checkbox)

                    btn_layout = QHBoxLayout()
                    
                    view_btn = QPushButton("查看任务")
                    view_btn.clicked.connect(lambda: self.on_view_tasks(dialog))
                    btn_layout.addWidget(view_btn)
                    
                    cancel_btn = QPushButton("取消")
                    cancel_btn.clicked.connect(dialog.reject)
                    btn_layout.addWidget(cancel_btn)
                    
                    close_btn = QPushButton("关闭")
                    close_btn.clicked.connect(lambda: self.on_confirm_close(dialog, event))
                    btn_layout.addWidget(close_btn)
                    
                    main_layout.addLayout(btn_layout)

                    video_info = dialog.exec_()
                    if video_info == QDialog.Rejected:
                        event.ignore()
                        return
                else:
                    self._close_with_animation()
                    event.ignore()
            else:
                self._close_with_animation()
                event.ignore()
        except Exception:
            event.ignore()

    def on_view_tasks(self, dialog):
        if hasattr(self, 'task_manager') and self.task_manager and hasattr(self, 'parser') and hasattr(self, 'download_manager'):
            task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config, self)
            task_window.show()
            task_window.raise_()  # 确保窗口在最前面
            task_window.activateWindow()  # 激活窗口
        dialog.accept()

    def on_confirm_close(self, dialog, event):
        if not self.background_checkbox.isChecked():
            dialog.accept()
            
            if hasattr(self, 'download_manager') and self.download_manager:
                self.download_manager.cancel_all()
            
            if hasattr(self, 'task_manager') and self.task_manager:
                downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
                for task in downloading_tasks:
                    self.task_manager.update_task_status(task['id'], 'failed', '异常中断')
            
            self._close_with_animation()
        else:
            self.hide()
            dialog.accept()
            event.ignore()
            return

    def _cleanup_before_exit(self):
        self.cleanup_temp_files()
        if hasattr(self, 'download_manager') and self.download_manager:
            self.download_manager.cancel_all()

    def quit_directly(self):
        if hasattr(self, 'download_manager') and self.download_manager:
            self.download_manager.cancel_all()
        if hasattr(self, 'task_manager') and self.task_manager:
            downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
            for task in downloading_tasks:
                self.task_manager.update_task_status(task['id'], 'failed', '异常中断')
        self._cleanup_before_exit()
        import os
        os._exit(0)

    def init_system_tray(self):
        
        
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统不支持系统托盘")
            return
        
        
        app = QApplication.instance()
        if not app:
            logger.warning("应用程序实例不存在")
            return
        
        
        if hasattr(self, 'tray_icon'):
            try:
                self.tray_icon.hide()
                del self.tray_icon
            except Exception as e:
                logger.warning(f"移除旧托盘图标失败：{str(e)}")
        
        
        self.tray_icon = QSystemTrayIcon()
        
        
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.tray_icon.setIcon(icon)
                logger.info("托盘图标使用logo.ico成功")
            else:
                
                logo_png_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
                if os.path.exists(logo_png_path):
                    icon = QIcon(logo_png_path)
                    self.tray_icon.setIcon(icon)
                    logger.info("托盘图标使用logo.png成功")
                else:
                    
                    pixmap = QPixmap(32, 32)
                    pixmap.fill(Qt.blue)  
                    painter = QPainter(pixmap)
                    painter.setPen(Qt.white)
                    painter.drawText(8, 22, "B")  
                    painter.end()
                    icon = QIcon(pixmap)
                    self.tray_icon.setIcon(icon)
                    logger.info("托盘图标创建成功")
        except Exception as e:
            logger.error(f"创建托盘图标失败：{str(e)}")
            
            self.tray_icon.setIcon(QIcon())
        
        
        self.tray_icon.setToolTip(f"B站视频解析工具{version_info['version']}")
        
        
        self.tray_menu = QMenu()
        
        
        show_action = self.tray_menu.addAction("显示主窗口")
        def show_main():
            print("显示主窗口")
            logger.info("显示主窗口")
            self.show()
            self.raise_()
            self.activateWindow()
        show_action.triggered.connect(show_main)
        
        view_tasks_action = self.tray_menu.addAction("查看任务")
        def view_tasks():
            print("查看任务")
            logger.info("查看任务")
            if hasattr(self, 'task_manager') and self.task_manager and hasattr(self, 'parser') and hasattr(self, 'download_manager'):
                task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config, self)
                task_window.show()
        view_tasks_action.triggered.connect(view_tasks)
        
        
        self.tray_menu.addSeparator()
        
        exit_action = self.tray_menu.addAction("退出")
        def exit_app():
            print("退出应用")
            logger.info("退出应用")
            self.quit_directly()
        exit_action.triggered.connect(exit_app)
        
        
        self.tray_icon.setContextMenu(self.tray_menu)
        
        
        self.tray_icon.show()
        logger.info("托盘图标已显示")
        
        
        def on_tray_activated(reason):
            print(f"托盘图标被激活，原因：{reason}")
            logger.info(f"托盘图标被激活，原因：{reason}")
            if reason == QSystemTrayIcon.Trigger:
                
                print("左键点击托盘图标")
                logger.info("左键点击托盘图标")
                if self.isVisible():
                    self.hide()
                    print("主窗口已隐藏")
                    logger.info("主窗口已隐藏")
                else:
                    show_main()
            elif reason == QSystemTrayIcon.DoubleClick:
                
                print("双击托盘图标")
                logger.info("双击托盘图标")
                show_main()
            
        
        
        self.tray_icon.activated.connect(on_tray_activated)
        
        
        self.tray_icon.setVisible(True)
        
        print("系统托盘初始化完成")
        logger.info("系统托盘初始化完成")



    def show_main_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def show_task_manager(self):
        if hasattr(self, 'task_manager') and self.task_manager and hasattr(self, 'parser') and hasattr(self, 'download_manager'):
            task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config, self)
            task_window.show()

    def on_batch_parse(self):
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle("批量解析")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            dialog.setMinimumSize(max(scale(400), int(sg.width() * 0.3)), max(scale(300), int(sg.height() * 0.3)))
        else:
            dialog.setMinimumSize(scale(400), scale(300))
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        
        # 应用自定义边框样式
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
            # 标题栏样式
            # 这里不添加标题栏，因为我们会手动创建
        """)
        dialog.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        # 添加标题栏
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(2), scale(10), scale(2))
        title_layout.setSpacing(scale(8))
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 28px; border-top-left-radius: 6px; border-top-right-radius: 6px;"))
        
        title_label = QLabel("批量解析")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet(scale_style("font-weight: bold; font-size: 13px;"))
        title_layout.addWidget(title_label, stretch=1)
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.setStyleSheet(scale_style("min-width: 28px; min-height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;"))
        minimize_btn.clicked.connect(dialog.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setStyleSheet(scale_style("min-width: 28px; min-height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;"))
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        # 添加内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))

        label = QLabel("请输入多个视频链接（每行一个）：")
        content_layout.addWidget(label)

        self.batch_url_edit = QTextEdit()
        self.batch_url_edit.setPlaceholderText("https://www.bilibili.com/video/BV1koiiYTELe/\nhttps://www.bilibili.com/video/BV1xx411c7mK/")
        content_layout.addWidget(self.batch_url_edit, stretch=1)

        btn_layout = QHBoxLayout()
        start_btn = QPushButton("开始解析")
        start_btn.clicked.connect(lambda: self.start_batch_parse(dialog))
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addStretch(1)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(cancel_btn)
        content_layout.addLayout(btn_layout)
        
        main_layout.addWidget(content_widget, stretch=1)
        
        # 添加鼠标事件处理，实现窗口移动
        dialog.dragging = False
        dialog.start_pos = None
        
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton and event.y() < scale(32):
                dialog.dragging = True
                dialog.start_pos = event.globalPos() - dialog.frameGeometry().topLeft()
                event.accept()
        
        def mouseMoveEvent(event):
            if dialog.dragging and event.buttons() == Qt.LeftButton:
                dialog.move(event.globalPos() - dialog.start_pos)
                event.accept()
        
        def mouseReleaseEvent(event):
            dialog.dragging = False
            event.accept()
        
        dialog.mousePressEvent = mousePressEvent
        dialog.mouseMoveEvent = mouseMoveEvent
        dialog.mouseReleaseEvent = mouseReleaseEvent

        dialog.exec_()

    def start_batch_parse(self, dialog):
        urls = self.batch_url_edit.toPlainText().strip().split('\n')
        urls = [url.strip() for url in urls if url.strip()]
        if not urls:
            self.show_notification("请输入至少一个视频链接", "warning")
            return

        dialog.accept()
        self.start_batch_parse_with_urls(urls)
    
    def start_batch_parse_with_urls(self, urls):
        if not urls:
            self.show_notification("请选择至少一个视频", "warning")
            return

        self.status_label.setText(f"开始批量解析{len(urls)}个链接...")

        
        batch_parse_window = QMainWindow()
        batch_parse_window.setAutoFillBackground(True)
        batch_parse_window.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        batch_parse_window.setWindowTitle("批量解析结果")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.geometry()
            win_w = min(scale(800), int(sg.width() * 0.85))
            win_h = min(scale(600), int(sg.height() * 0.85))
            batch_parse_window.setGeometry((sg.width() - win_w) // 2, (sg.height() - win_h) // 2, win_w, win_h)
        else:
            batch_parse_window.setGeometry(scale(100), scale(100), scale(800), scale(600))
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                batch_parse_window.setWindowIcon(icon)
        except Exception as e:
            pass
        
        batch_parse_window.dragging = False
        batch_parse_window.start_pos = None
        
        
        def mousePressEvent(event):
            
            if event.button() == Qt.LeftButton and event.y() < scale(32):  
                batch_parse_window.dragging = True
                batch_parse_window.start_pos = event.globalPos() - batch_parse_window.frameGeometry().topLeft()
                event.accept()
        
        def mouseMoveEvent(event):
            
            if batch_parse_window.dragging and event.buttons() == Qt.LeftButton:
                batch_parse_window.move(event.globalPos() - batch_parse_window.start_pos)
                event.accept()
        
        def mouseReleaseEvent(event):
            
            batch_parse_window.dragging = False
            event.accept()
        
        
        batch_parse_window.mousePressEvent = mousePressEvent
        batch_parse_window.mouseMoveEvent = mouseMoveEvent
        batch_parse_window.mouseReleaseEvent = mouseReleaseEvent
        
        custom_style = get_base_style() + scale_style("""
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
                background-color: white;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                min-height: 32px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                min-width: 32px;
                min-height: 32px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
                padding: 0px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """)
        batch_parse_window.setStyleSheet(custom_style)

        central_widget = QWidget()
        batch_parse_window.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(2), scale(10), scale(2))
        title_layout.setSpacing(scale(8))
        
        title_label = QLabel("批量解析结果")
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label, stretch=1)
        
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.clicked.connect(batch_parse_window.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        
        maximize_btn = QPushButton("□")
        maximize_btn.setObjectName("maximizeBtn")
        def toggle_maximize():
            if batch_parse_window.isMaximized():
                batch_parse_window.showNormal()
            else:
                batch_parse_window.showMaximized()
        maximize_btn.clicked.connect(toggle_maximize)
        title_layout.addWidget(maximize_btn)
        
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(batch_parse_window.close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(15))

        title_label = QLabel(f"批量解析结果 - 共{len(urls)}个链接")
        title_label.setStyleSheet(scale_style("font-size: 16px; font-weight: bold; color: #2563eb;"))
        content_layout.addWidget(title_label)

        self.batch_progress_label = QLabel(f"正在解析 0/{len(urls)}...")
        self.batch_progress_label.setStyleSheet(scale_style("font-size: 13px; color: #6b7280;"))
        content_layout.addWidget(self.batch_progress_label)

        self.batch_progress_bar = QProgressBar()
        self.batch_progress_bar.setMinimum(0)
        self.batch_progress_bar.setMaximum(len(urls))
        self.batch_progress_bar.setValue(0)
        self.batch_progress_bar.setStyleSheet(scale_style("""
            QProgressBar {
                min-height: 8px;
                border-radius: 4px;
                background-color: #e9ecef;
                border: none;
            }
            QProgressBar::chunk {
                border-radius: 4px;
                background-color: #409eff;
            }
        """))
        content_layout.addWidget(self.batch_progress_bar)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(scale(10))

        
        batch_parse_finished_count = [0]
        batch_parse_total = len(urls)
        batch_parse_lock = threading.Lock()
        all_link_data = []

        for i, url in enumerate(urls):
            group = QGroupBox(f"链接 {i+1}")
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(scale(8))

            checkbox_row = QHBoxLayout()
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox.setStyleSheet(scale_style("QCheckBox { spacing: 4px; }"))
            checkbox_row.addWidget(checkbox)
            url_label = QLabel(f"URL: <a href='{url}'>{url[:100]}...</a>")
            url_label.setOpenExternalLinks(True)
            checkbox_row.addWidget(url_label, stretch=1)
            group_layout.addLayout(checkbox_row)

            status_label = QLabel("状态：解析中...")
            status_label.setStyleSheet("color: #6b7280;")
            group_layout.addWidget(status_label)

            title_label = QLabel("标题：-")
            title_label.setWordWrap(True)
            group_layout.addWidget(title_label)

            quality_label = QLabel("清晰度：-")
            group_layout.addWidget(quality_label)

            select_btn = QPushButton("选择集数")
            select_btn.setEnabled(False)
            download_btn = QPushButton("开始下载")
            download_btn.setEnabled(False)
            cover_btn = QPushButton("下载封面")
            cover_btn.setEnabled(False)
            cover_btn.setStyleSheet(scale_style("""
                QPushButton {
                    background-color: #4f6ef7;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-size: 10px;
                    font-weight: 500;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #3b5de7;
                }
                QPushButton:disabled {
                    background-color: #e5e7eb;
                    color: #9ca3af;
                }
            """))

            btn_layout = QHBoxLayout()
            btn_layout.addWidget(select_btn)
            btn_layout.addWidget(download_btn)
            btn_layout.addWidget(cover_btn)
            group_layout.addLayout(btn_layout)

            scroll_layout.addWidget(group)

            
            link_data = {
                'url': url,
                'group': group,
                'checkbox': checkbox,
                'status_label': status_label,
                'title_label': title_label,
                'quality_label': quality_label,
                'select_btn': select_btn,
                'download_btn': download_btn,
                'cover_btn': cover_btn,
                'selected_episodes': [],
                'video_info': None,
                'quality_combo': None
            }
            all_link_data.append(link_data)
            cover_btn.clicked.connect(lambda checked, ld=link_data: self.on_batch_cover_download(ld))

            
            def create_select_handler(ld):
                def handler():
                    if not ld['video_info']:
                        return
                    is_bangumi = ld['video_info'].get("is_bangumi", False)
                    is_cheese = ld['video_info'].get("is_cheese", False)
                    episodes = []
                    if is_bangumi:
                        episodes = ld['video_info']['bangumi_info'].get("episodes", [])
                    elif is_cheese:
                        episodes = ld['video_info']['cheese_info'].get("episodes", [])
                    else:
                        episodes = ld['video_info'].get("collection", [])
                    if not episodes:
                        QMessageBox.information(batch_parse_window, "提示", "这个视频没有分集可以选择哦")
                        return

                    dialog = EpisodeSelectionDialog(batch_parse_window, episodes, is_bangumi)
                    if dialog.exec_() == QDialog.Accepted:
                        ld['selected_episodes'] = dialog.selected_episodes
                        # 检查UI元素是否仍然存在
                        try:
                            if ld['select_btn'] and ld['select_btn'].isVisible():
                                ld['select_btn'].setText(f"已选{len(ld['selected_episodes'])}集")
                                ld['select_btn'].setToolTip("点击修改集数选择")
                        except RuntimeError:
                            # UI元素已被删除，忽略
                            pass
                return handler

            
            def create_download_handler(ld):
                def handler():
                    if not ld['video_info']:
                        QMessageBox.warning(batch_parse_window, "提示", "请先解析视频链接哦")
                        return
                    if not ld['selected_episodes']:
                        QMessageBox.warning(batch_parse_window, "提示", "请先选择要下载的集数哦")
                        return
                    
                    
                    quality_dialog = QDialog(batch_parse_window)
                    quality_dialog.setWindowTitle("选择清晰度")
                    quality_dialog.setMinimumSize(scale(400), scale(200))
                    quality_dialog.setStyleSheet(get_base_style())

                    quality_layout = QVBoxLayout(quality_dialog)
                    quality_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
                    quality_layout.setSpacing(scale(15))

                    quality_label = QLabel("请选择视频清晰度：")
                    quality_layout.addWidget(quality_label)

                    quality_combo = QComboBox()
                    for qn, name in ld['video_info']['qualities']:
                        if qn in [112, 120, 125, 127]:
                            quality_combo.addItem(f"{name}（会员）", qn)
                        else:
                            quality_combo.addItem(name, qn)
                    quality_layout.addWidget(quality_combo)

                    path_label = QLabel("保存路径：")
                    quality_layout.addWidget(path_label)

                    path_edit = QLineEdit()
                    last_path = self.config.get_app_setting("last_save_path")
                    default_path = last_path if last_path else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
                    path_edit.setText(default_path)
                    quality_layout.addWidget(path_edit)

                    browse_btn = QPushButton("浏览")
                    browse_btn.clicked.connect(lambda: self.browse_settings_path(path_edit))
                    quality_layout.addWidget(browse_btn)

                    btn_layout = QHBoxLayout()
                    ok_btn = QPushButton("确定")
                    cancel_btn = QPushButton("取消")
                    btn_layout.addStretch(1)
                    btn_layout.addWidget(ok_btn)
                    btn_layout.addWidget(cancel_btn)
                    quality_layout.addLayout(btn_layout)

                    def on_ok():
                        if quality_combo.currentIndex() == -1:
                            QMessageBox.warning(batch_parse_window, "提示", "请选择视频清晰度哦")
                            return
                        selected_qn = quality_combo.itemData(quality_combo.currentIndex())
                        save_path = path_edit.text().strip()
                        if not save_path:
                            QMessageBox.warning(batch_parse_window, "提示", "请选择视频保存路径哦")
                            return
                        os.makedirs(save_path, exist_ok=True)
                        
                        
                        task_id = str(int(time.time() * 1000))
                        
                        download_params = {
                            "url": ld['url'],
                            "video_info": ld['video_info'],
                            "qn": selected_qn,
                            "save_path": save_path,
                            "episodes": ld['selected_episodes'],
                            "resume_download": True,
                            "task_id": task_id,
                            "download_video": True,
                            "download_danmaku": False,
                            "danmaku_format": "XML",
                            "video_format": self.config.get_app_setting("video_output_format", "mp4"),
                            "audio_format": self.config.get_app_setting("audio_output_format", "mp3"),
                            "audio_quality": self.config.get_app_setting("audio_quality", 30280)
                        }
                        
                        # 直接调用download_manager.start_download，就像单独下载一样
                        time.sleep(0.1)  
                        
                        logger.info(f"批量解析：直接调用下载方法，任务ID：{task_id}")
                        if self.download_manager:
                            self.download_manager.start_download(download_params)
                            logger.info(f"批量解析：下载方法已调用")
                        else:
                            logger.error("批量解析：下载管理器未初始化")
                        
                        
                        existing_window = None
                        for window in self.batch_windows.values():
                            if isinstance(window, BatchDownloadWindow) and window.isVisible():
                                existing_window = window
                                break
                        
                        if existing_window:
                            
                            for i, ep in enumerate(ld['selected_episodes']):
                                if ld['video_info'].get("is_bangumi") or ld['video_info'].get("is_cheese"):
                                    ep_name = f"{ep['ep_index']}"
                                    ep_tooltip = ep['ep_title']
                                else:
                                    if 'page' in ep and 'title' in ep:
                                        ep_name = f"第{ep['page']}集"
                                        ep_tooltip = ep['title']
                                    elif 'ep_index' in ep and 'ep_title' in ep:
                                        ep_name = f"{ep['ep_index']}"
                                        ep_tooltip = ep['ep_title']
                                    else:
                                        ep_name = f"第{i+1}集"
                                        ep_tooltip = f"第{i+1}集"
                                
                                existing_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
                            
                            if hasattr(self, 'download_manager') and self.download_manager:
                                self.download_manager.episode_progress_updated.connect(existing_window.update_episode_progress)
                                self.download_manager.episode_finished.connect(existing_window.finish_episode)
                            existing_window.show()
                            existing_window.raise_()  # 确保窗口在最前面
                            existing_window.activateWindow()  # 激活窗口
                        else:
                            
                            batch_window = BatchDownloadWindow(ld['video_info'], 0, self.download_manager, self.parser)
                            for i, ep in enumerate(ld['selected_episodes']):
                                if ld['video_info'].get("is_bangumi") or ld['video_info'].get("is_cheese"):
                                    ep_name = f"{ep['ep_index']}"
                                    ep_tooltip = ep['ep_title']
                                else:
                                    if 'page' in ep and 'title' in ep:
                                        ep_name = f"第{ep['page']}集"
                                        ep_tooltip = ep['title']
                                    elif 'ep_index' in ep and 'ep_title' in ep:
                                        ep_name = f"{ep['ep_index']}"
                                        ep_tooltip = ep['ep_title']
                                    else:
                                        ep_name = f"第{i+1}集"
                                        ep_tooltip = f"第{i+1}集"
                                
                                batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, i)
                            batch_window.cancel_all.connect(self.on_cancel_download)
                            batch_window.window_closed.connect(lambda tid=task_id: self.on_batch_window_closed(tid))
                            batch_window.show()
                            batch_window.raise_()  # 确保窗口在最前面
                            batch_window.activateWindow()  # 激活窗口
                            
                            self.batch_windows[task_id] = batch_window
                        quality_dialog.accept()

                    ok_btn.clicked.connect(on_ok)
                    cancel_btn.clicked.connect(quality_dialog.reject)
                    quality_dialog.exec_()
                return handler

            
            select_btn.clicked.connect(create_select_handler(link_data))
            download_btn.clicked.connect(create_download_handler(link_data))


            def parse_link(url, link_data):
                try:
                    if self.parser is None:
                        self.signal_emitter.batch_parse_result.emit(link_data, False, "解析器未初始化，请重启应用")
                        return
                    media_parse_video_info = self.parser.parse_media_url(url)
                    if media_parse_video_info.get("error"):
                        self.signal_emitter.batch_parse_result.emit(link_data, False, media_parse_video_info["error"])
                        return

                    media_type = media_parse_video_info["type"]
                    media_id = media_parse_video_info["id"]
                    if not media_type or not media_id:
                        self.signal_emitter.batch_parse_result.emit(link_data, False, "未识别到有效媒体ID")
                        return

                    media_info = self.parser.parse_media(media_type, media_id, self.tv_mode_checkbox.isChecked())
                    self.signal_emitter.batch_parse_result.emit(link_data, True, media_info)
                except Exception as e:
                    self.signal_emitter.batch_parse_result.emit(link_data, False, f"解析失败：{str(e)}")
                finally:
                    with batch_parse_lock:
                        batch_parse_finished_count[0] += 1
                        finished = batch_parse_finished_count[0]
                    self.signal_emitter.batch_parse_progress.emit(finished, batch_parse_total, f"正在解析 {finished}/{batch_parse_total}...")

            thread = threading.Thread(target=parse_link, args=(url, link_data))
            thread.daemon = True
            thread.start()

        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(10))

        select_all_btn = QPushButton("全选")
        select_all_btn.setStyleSheet(scale_style("padding: 0 16px; border: 1px solid #409eff; border-radius: 6px; font-size: 13px; background-color: white; color: #409eff; min-height: 32px;"))
        def on_select_all():
            for ld in all_link_data:
                try:
                    ld['checkbox'].setChecked(True)
                except RuntimeError:
                    pass
        select_all_btn.clicked.connect(on_select_all)

        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.setStyleSheet(scale_style("padding: 0 16px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; background-color: white; color: #374151; min-height: 32px;"))
        def on_deselect_all():
            for ld in all_link_data:
                try:
                    ld['checkbox'].setChecked(False)
                except RuntimeError:
                    pass
        deselect_all_btn.clicked.connect(on_deselect_all)

        batch_download_btn = QPushButton("批量下载选中")
        batch_download_btn.setStyleSheet(scale_style("padding: 0 20px; border: none; border-radius: 6px; font-size: 13px; background-color: #409eff; color: white; min-height: 32px;"))
        def on_batch_download():
            selected_items = [ld for ld in all_link_data if ld['checkbox'].isChecked() and ld['video_info']]
            if not selected_items:
                QMessageBox.warning(batch_parse_window, "提示", "请至少勾选一个已解析成功的视频")
                return
            for ld in selected_items:
                try:
                    if not ld['selected_episodes']:
                        is_bangumi = ld['video_info'].get("is_bangumi", False)
                        is_cheese = ld['video_info'].get("is_cheese", False)
                        if is_bangumi:
                            episodes = ld['video_info']['bangumi_info'].get("episodes", [])
                        elif is_cheese:
                            episodes = ld['video_info']['cheese_info'].get("episodes", [])
                        else:
                            episodes = ld['video_info'].get("collection", [])
                        if not episodes:
                            episodes = [{
                                'page': 1,
                                'title': ld['video_info'].get('title', ''),
                                'duration': ld['video_info'].get('duration', ''),
                                'cid': ld['video_info'].get('cid', ''),
                                'bvid': ld['video_info'].get('bvid', '')
                            }]
                        ld['selected_episodes'] = episodes
                        try:
                            ld['select_btn'].setText(f"已选{len(episodes)}集")
                        except RuntimeError:
                            pass
                except Exception:
                    pass

            save_path = self.path_edit.text().strip() if hasattr(self, 'path_edit') else ""
            if not save_path:
                save_path = self.config.get_app_setting("last_save_path", "")
            if not save_path:
                save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
            os.makedirs(save_path, exist_ok=True)

            default_qn = self.config.get_app_setting("default_quality", 80)
            video_format = self.config.get_app_setting("video_output_format", "mp4")
            audio_format = self.config.get_app_setting("audio_output_format", "mp3")
            audio_quality = self.config.get_app_setting("audio_quality", 30280)
            download_danmaku = False
            if hasattr(self, 'danmaku_checkbox'):
                download_danmaku = self.danmaku_checkbox.isChecked()
            danmaku_format = self.danmaku_format_combo.currentText() if hasattr(self, 'danmaku_format_combo') else 'XML'

            for ld in selected_items:
                try:
                    quality_options = ld['video_info'].get('qualities', [])
                    if quality_options:
                        qn_available = [qn for qn, name in quality_options]
                        selected_qn = default_qn if default_qn in qn_available else qn_available[0]
                    else:
                        selected_qn = default_qn

                    task_id = str(int(time.time() * 1000) + id(ld))
                    download_params = {
                        "url": ld['url'],
                        "video_info": ld['video_info'],
                        "qn": selected_qn,
                        "save_path": save_path,
                        "episodes": ld['selected_episodes'],
                        "resume_download": True,
                        "task_id": task_id,
                        "download_danmaku": download_danmaku,
                        "danmaku_format": danmaku_format,
                        "download_video": True,
                        "video_format": video_format,
                        "audio_format": audio_format,
                        "audio_quality": audio_quality
                    }

                    if self.download_manager:
                        self.download_manager.start_download(download_params)

                    existing_window = None
                    for window in self.batch_windows.values():
                        if isinstance(window, BatchDownloadWindow) and window.isVisible():
                            existing_window = window
                            break

                    if existing_window:
                        for idx, ep in enumerate(ld['selected_episodes']):
                            if ld['video_info'].get("is_bangumi") or ld['video_info'].get("is_cheese"):
                                ep_name = f"{ep['ep_index']}"
                                ep_tooltip = ep['ep_title']
                            else:
                                if 'page' in ep and 'title' in ep:
                                    ep_name = f"第{ep['page']}集"
                                    ep_tooltip = ep['title']
                                elif 'ep_index' in ep and 'ep_title' in ep:
                                    ep_name = f"{ep['index']}"
                                    ep_tooltip = ep['ep_title']
                                else:
                                    ep_name = f"第{idx+1}集"
                                    ep_tooltip = f"第{idx+1}集"
                            existing_window.add_episode_progress(ep_name, ep_tooltip, task_id, idx)

                        if hasattr(self, 'download_manager') and self.download_manager:
                            self.download_manager.episode_progress_updated.connect(existing_window.update_episode_progress)
                            self.download_manager.episode_finished.connect(existing_window.finish_episode)
                        existing_window.show()
                        existing_window.raise_()
                        existing_window.activateWindow()
                    else:
                        batch_window = BatchDownloadWindow(ld['video_info'], 0, self.download_manager, self.parser)
                        for idx, ep in enumerate(ld['selected_episodes']):
                            if ld['video_info'].get("is_bangumi") or ld['video_info'].get("is_cheese"):
                                ep_name = f"{ep['ep_index']}"
                                ep_tooltip = ep['ep_title']
                            else:
                                if 'page' in ep and 'title' in ep:
                                    ep_name = f"第{ep['page']}集"
                                    ep_tooltip = ep['title']
                                elif 'ep_index' in ep and 'ep_title' in ep:
                                    ep_name = f"{ep['ep_index']}"
                                    ep_tooltip = ep['ep_title']
                                else:
                                    ep_name = f"第{idx+1}集"
                                    ep_tooltip = f"第{idx+1}集"
                            batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, idx)
                        batch_window.cancel_all.connect(self.on_cancel_download)
                        batch_window.window_closed.connect(lambda tid=task_id: self.on_batch_window_closed(tid))
                        batch_window.show()
                        batch_window.raise_()
                        batch_window.activateWindow()
                        self.batch_windows[task_id] = batch_window
                except Exception as e:
                    logger.error(f"批量下载出错：{str(e)}")

            self.show_notification(f"已开始下载 {len(selected_items)} 个视频", "success")

        batch_download_btn.clicked.connect(on_batch_download)

        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(batch_download_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet(scale_style("padding: 0 16px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 13px; background-color: white; color: #374151; min-height: 32px;"))
        close_btn.clicked.connect(batch_parse_window.close)
        btn_layout.addWidget(close_btn)
        content_layout.addLayout(btn_layout)
        
        
        main_layout.addWidget(content_widget)

        
        def batch_parse_window_mousePressEvent(event):
            
            if event.button() == Qt.LeftButton and event.y() < scale(32):  
                batch_parse_window.dragging = True
                batch_parse_window.start_pos = event.globalPos() - batch_parse_window.frameGeometry().topLeft()
                event.accept()

        def batch_parse_window_mouseMoveEvent(event):
            
            if batch_parse_window.dragging and event.buttons() == Qt.LeftButton:
                batch_parse_window.move(event.globalPos() - batch_parse_window.start_pos)
                event.accept()

        def batch_parse_window_mouseReleaseEvent(event):
            
            batch_parse_window.dragging = False
            event.accept()

        
        batch_parse_window.mousePressEvent = batch_parse_window_mousePressEvent
        batch_parse_window.mouseMoveEvent = batch_parse_window_mouseMoveEvent
        batch_parse_window.mouseReleaseEvent = batch_parse_window_mouseReleaseEvent

        batch_parse_window.show()

    def update_batch_parse_video_info(self, link_data, success, video_info):
        
        if not all(key in link_data for key in ['status_label', 'title_label', 'quality_label', 'select_btn', 'download_btn']):
            return

        
        try:
            
            _ = link_data['status_label'].parent()
        except RuntimeError:
            return

        if success:
            link_data['status_label'].setText("状态：解析成功")
            link_data['status_label'].setStyleSheet("color: #52c41a;")
            link_data['title_label'].setText(f"标题：{video_info.get('title', '未知标题')}")
            
            if video_info.get("qualities"):
                quality_text = ", ".join([name for qn, name in video_info["qualities"]])
                link_data['quality_label'].setText(f"清晰度：{quality_text}")
                link_data['select_btn'].setEnabled(True)
                link_data['download_btn'].setEnabled(True)
                link_data['video_info'] = video_info
                if 'cover_btn' in link_data and link_data['cover_btn'] is not None:
                    link_data['cover_btn'].setEnabled(True)
        else:
            link_data['status_label'].setText(f"状态：解析失败")
            link_data['status_label'].setStyleSheet("color: #f56c6c;")
            link_data['title_label'].setText(f"错误：{video_info}")

    def browse_settings_path(self, path_edit):
        path = self.show_custom_file_dialog("选择默认保存路径")
        if path:
            path_edit.setText(path)

    def browse_path(self):
        path = self.show_custom_file_dialog("选择保存路径")
        if path:
            self.path_edit.setText(path)
            
            self.config.set_app_setting("last_save_path", path)
    
    def show_custom_file_dialog(self, title, select_folder=True, file_filters=None, allow_multiselect=False):
        
        
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            dialog.setMinimumSize(max(scale(700), int(sg.width() * 0.4)), max(scale(500), int(sg.height() * 0.4)))
        else:
            dialog.setMinimumSize(scale(700), scale(500))
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        dialog.setAutoFillBackground(True)
        
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
            QWidget#titleBar {
                background-color: #409eff;
                color: white;
                min-height: 40px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QLabel#titleLabel {
                font-size: 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton#closeBtn {
                min-width: 28px;
                min-height: 28px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
            }
            QPushButton#closeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            QToolBar {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 8px;
            }
            QToolBar QPushButton {
                border: none;
                background-color: transparent;
                padding: 6px 10px;
                border-radius: 4px;
                color: #333333;
            }
            QToolBar QPushButton:hover {
                background-color: #e6f7ff;
            }
            QWidget#pathWidget {
                background-color: white;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 10px 12px;
            }
            QLabel#pathLabel {
                font-size: 13px;
                font-weight: 500;
                color: #666666;
            }
            QLineEdit#pathEdit {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 13px;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 10px;
                background-color: white;
            }
            QSplitter {
                background-color: #f8f9fa;
            }
            QSplitter::handle {
                background-color: #dee2e6;
                min-width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #409eff;
            }
            QTreeView {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
            }
            QTreeView::item:hover {
                background-color: #e6f7ff;
            }
            QTreeView::item:selected {
                background-color: #409eff;
                color: white;
            }
            QListWidget {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                background-color: white;
            }
            QListWidget::item {
                padding: 12px;
                margin: 4px;
                border-radius: 4px;
                text-align: center;
            }
            QListWidget::item:hover {
                background-color: #e6f7ff;
            }
            QListWidget::item:selected {
                background-color: #409eff;
                color: white;
            }
            QPushButton#okBtn {
                background-color: #409eff;
                color: white;
                padding: 10px 24px;
            }
            QPushButton#okBtn:hover {
                background-color: #66b1ff;
            }
            QPushButton#cancelBtn {
                background-color: #f56c6c;
                color: white;
                padding: 10px 24px;
            }
            QPushButton#cancelBtn:hover {
                background-color: #f78989;
            }
            QComboBox {
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: 8px 12px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #409eff;
            }
        """)
        dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(20), scale(10), scale(12), scale(10))
        title_layout.setSpacing(scale(8))
        
        title_label = QLabel(title)
        title_label.setObjectName("titleLabel")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_widget.setObjectName("contentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(16), scale(16), scale(16), scale(16))
        content_layout.setSpacing(scale(12))
        
        
        toolbar = QToolBar()
        toolbar.setObjectName("toolbar")
        
        
        back_action = QAction("返回", dialog)
        back_action.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowBack))
        toolbar.addAction(back_action)
        
        forward_action = QAction("前进", dialog)
        forward_action.setIcon(QApplication.style().standardIcon(QStyle.SP_ArrowForward))
        toolbar.addAction(forward_action)
        
        toolbar.addSeparator()
        
        
        home_action = QAction("主页", dialog)
        home_action.setIcon(QApplication.style().standardIcon(QStyle.SP_DirHomeIcon))
        def go_home():
            home_path = os.path.expanduser("~")
            path_edit.setText(home_path)
            load_file_list(home_path)
            
            index = file_system_model.index(home_path)
            if index.isValid():
                tree_view.setCurrentIndex(index)
                
                temp_index = index
                while temp_index.isValid():
                    tree_view.expand(temp_index)
                    temp_index = temp_index.parent()
        home_action.triggered.connect(go_home)
        toolbar.addAction(home_action)
        
        desktop_action = QAction("桌面", dialog)
        desktop_action.setIcon(QApplication.style().standardIcon(QStyle.SP_ComputerIcon))
        def go_desktop():
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            if os.path.exists(desktop_path):
                path_edit.setText(desktop_path)
                load_file_list(desktop_path)
                
                index = file_system_model.index(desktop_path)
                if index.isValid():
                    tree_view.setCurrentIndex(index)
                    
                    temp_index = index
                    while temp_index.isValid():
                        tree_view.expand(temp_index)
                        temp_index = temp_index.parent()
        desktop_action.triggered.connect(go_desktop)
        toolbar.addAction(desktop_action)
        
        downloads_action = QAction("下载", dialog)
        downloads_action.setIcon(QApplication.style().standardIcon(QStyle.SP_DriveNetIcon))
        def go_downloads():
            downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
            if os.path.exists(downloads_path):
                path_edit.setText(downloads_path)
                load_file_list(downloads_path)
                
                index = file_system_model.index(downloads_path)
                if index.isValid():
                    tree_view.setCurrentIndex(index)
                    
                    temp_index = index
                    while temp_index.isValid():
                        tree_view.expand(temp_index)
                        temp_index = temp_index.parent()
        downloads_action.triggered.connect(go_downloads)
        toolbar.addAction(downloads_action)
        
        toolbar.addSeparator()
        
        
        view_mode_combo = QComboBox()
        view_mode_combo.addItems(["图标视图", "列表视图"])
        toolbar.addWidget(QLabel("视图："))
        toolbar.addWidget(view_mode_combo)
        
        
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("搜索文件...")
        search_edit.setMaximumWidth(scale(200))
        def on_search():
            search_text = search_edit.text().strip()
            if search_text:
                
                current_path = path_edit.text()
                if os.path.exists(current_path) and os.path.isdir(current_path):
                    list_view.clear()
                    
                    if current_path != "/":
                        parent_item = QListWidgetItem("..")
                        up_icon = style.standardIcon(QStyle.SP_FileDialogToParent)
                        parent_item.setIcon(up_icon)
                        parent_item.setData(Qt.UserRole, os.path.dirname(current_path))
                        list_view.addItem(parent_item)
                    
                    
                    try:
                        for item in os.listdir(current_path):
                            item_path = os.path.join(current_path, item)
                            
                            match = False
                            
                            
                            if search_text.lower() in item.lower():
                                match = True
                            
                            
                            if not match and search_text.startswith('.'):
                                ext = os.path.splitext(item)[1].lower()
                                if ext == search_text.lower():
                                    match = True
                            
                            
                            if not match:
                                
                                keywords = search_text.lower().split()
                                item_lower = item.lower()
                                if all(keyword in item_lower for keyword in keywords):
                                    match = True
                            
                            if match:
                                list_item = QListWidgetItem(item)
                                list_item.setData(Qt.UserRole, item_path)
                                
                                
                                if os.path.isdir(item_path):
                                    folder_icon = style.standardIcon(QStyle.SP_DirIcon)
                                    list_item.setIcon(folder_icon)
                                else:
                                    
                                    ext = os.path.splitext(item)[1].lower()
                                    if ext in ['.txt', '.log']:
                                        file_icon = style.standardIcon(QStyle.SP_FileIcon)
                                    elif ext in ['.jpg', '.jpeg', '.png', '.gif']:
                                        file_icon = style.standardIcon(QStyle.SP_FileDialogContentsView)
                                    elif ext in ['.mp4', '.avi', '.mkv']:
                                        file_icon = style.standardIcon(QStyle.SP_MediaPlay)
                                    elif ext in ['.mp3', '.wav', '.flac']:
                                        file_icon = style.standardIcon(QStyle.SP_MediaPlay)
                                    elif ext in ['.zip', '.rar', '.7z']:
                                        file_icon = style.standardIcon(QStyle.SP_FileIcon)
                                    elif ext in ['.exe', '.msi']:
                                        file_icon = style.standardIcon(QStyle.SP_FileIcon)
                                    else:
                                        file_icon = style.standardIcon(QStyle.SP_FileIcon)
                                    list_item.setIcon(file_icon)
                                
                                list_view.addItem(list_item)
                    except Exception as e:
                        print(f"搜索文件失败: {e}")
                        pass
        search_edit.returnPressed.connect(on_search)
        toolbar.addWidget(QLabel("搜索："))
        toolbar.addWidget(search_edit)
        
        content_layout.addWidget(toolbar)
        
        
        path_widget = QWidget()
        path_widget.setObjectName("pathWidget")
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        path_layout.setSpacing(scale(8))
        
        path_label = QLabel("路径：")
        path_label.setObjectName("pathLabel")
        path_edit = QLineEdit()
        path_edit.setObjectName("pathEdit")
        path_edit.setPlaceholderText("输入路径或点击浏览...")
        
        
        def on_path_edited():
            path = path_edit.text().strip()
            if os.path.exists(path) and os.path.isdir(path):
                load_file_list(path)
                
                index = file_system_model.index(path)
                if index.isValid():
                    tree_view.setCurrentIndex(index)
                    
                    temp_index = index
                    while temp_index.isValid():
                        tree_view.expand(temp_index)
                        temp_index = temp_index.parent()
        
        path_edit.editingFinished.connect(on_path_edited)
        
        path_layout.addWidget(path_label)
        path_layout.addWidget(path_edit, stretch=1)
        content_layout.addWidget(path_widget)
        
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(2)
        
        
        tree_view = QTreeView()
        tree_view.setMinimumWidth(scale(280))
        
        
        file_system_model = QFileSystemModel()
        file_system_model.setRootPath("/")
        file_system_model.setFilter(QDir.AllDirs | QDir.NoDotAndDotDot | QDir.Files)
        file_system_model.setReadOnly(True)
        
        
        tree_view.setModel(file_system_model)
        for i in range(1, file_system_model.columnCount()):
            tree_view.hideColumn(i)
        
        splitter.addWidget(tree_view)
        splitter.setStretchFactor(0, 1)
        
        
        list_view = QListWidget()
        list_view.setViewMode(QListWidget.IconMode)
        list_view.setIconSize(QSize(scale(64), scale(64)))
        list_view.setUniformItemSizes(True)
        list_view.setSpacing(scale(16))
        list_view.setMinimumWidth(scale(500))
        list_view.setGridSize(QSize(scale(100), scale(100)))
        splitter.addWidget(list_view)
        splitter.setStretchFactor(1, 3)
        
        
        splitter.setSizes([300, 750])
        
        content_layout.addWidget(splitter, stretch=1)
        
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(12))
        
        ok_btn = QPushButton("确定")
        ok_btn.setObjectName("okBtn")
        cancel_btn = QPushButton("取消")
        cancel_btn.setObjectName("cancelBtn")
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        content_layout.addLayout(btn_layout)
        
        main_layout.addWidget(content_widget, stretch=1)
        
        
        style = QApplication.style()
        
        
        history = []
        history_index = -1
        
        
        def load_file_list(path):
            list_view.clear()
            try:
                
                nonlocal history, history_index
                if history and history_index >= 0 and history[history_index] == path:
                    pass
                else:
                    history = history[:history_index+1] if history_index >= 0 else []
                    history.append(path)
                    history_index = len(history) - 1
                
                
                back_action.setEnabled(history_index > 0)
                forward_action.setEnabled(history_index < len(history) - 1)
                
                
                path_edit.setText(path)
                
                
                if path != "/":
                    parent_item = QListWidgetItem("..")
                    up_icon = style.standardIcon(QStyle.SP_FileDialogToParent)
                    parent_item.setIcon(up_icon)
                    parent_item.setData(Qt.UserRole, os.path.dirname(path))
                    list_view.addItem(parent_item)
                
                
                folders = []
                files = []
                
                for item in os.listdir(path):
                    item_path = os.path.join(path, item)
                    if os.path.isdir(item_path):
                        folders.append(item)
                    else:
                        
                        if not file_filters or any(item.lower().endswith(filter.lower()) for filter in file_filters):
                            files.append(item)
                
                
                folders.sort()
                files.sort()
                
                
                for item in folders:
                    item_path = os.path.join(path, item)
                    list_item = QListWidgetItem(item)
                    list_item.setData(Qt.UserRole, item_path)
                    folder_icon = style.standardIcon(QStyle.SP_DirIcon)
                    list_item.setIcon(folder_icon)
                    list_view.addItem(list_item)
                
                
                if not select_folder:
                    for item in files:
                        item_path = os.path.join(path, item)
                        list_item = QListWidgetItem(item)
                        list_item.setData(Qt.UserRole, item_path)
                        
                        
                        ext = os.path.splitext(item)[1].lower()
                        if ext in ['.txt', '.log']:
                            file_icon = style.standardIcon(QStyle.SP_FileIcon)
                        elif ext in ['.jpg', '.jpeg', '.png', '.gif']:
                            file_icon = style.standardIcon(QStyle.SP_FileDialogContentsView)
                        elif ext in ['.mp4', '.avi', '.mkv']:
                            file_icon = style.standardIcon(QStyle.SP_MediaPlay)
                        elif ext in ['.mp3', '.wav', '.flac']:
                            file_icon = style.standardIcon(QStyle.SP_MediaPlay)
                        elif ext in ['.zip', '.rar', '.7z']:
                            file_icon = style.standardIcon(QStyle.SP_FileIcon)
                        elif ext in ['.exe', '.msi']:
                            file_icon = style.standardIcon(QStyle.SP_FileIcon)
                        else:
                            file_icon = style.standardIcon(QStyle.SP_FileIcon)
                        list_item.setIcon(file_icon)
                        list_view.addItem(list_item)
            except Exception as e:
                print(f"加载文件列表失败: {e}")
                pass
        
        
        def on_tree_clicked(index):
            path = file_system_model.filePath(index)
            if os.path.isdir(path):
                path_edit.setText(path)
                load_file_list(path)
        
        tree_view.clicked.connect(on_tree_clicked)
        
        
        def on_list_double_clicked(item):
            path = item.data(Qt.UserRole)
            if path and os.path.isdir(path):
                
                index = file_system_model.index(path)
                if index.isValid():
                    tree_view.setCurrentIndex(index)
                    tree_view.expand(index)
                    path_edit.setText(path)
                    load_file_list(path)
            else:
                
                if not select_folder:
                    
                    if not file_filters or any(path.lower().endswith(filter.lower()) for filter in file_filters):
                        path_edit.setText(path)
                        selected_path = path
                        dialog.accept()
                
        
        list_view.itemDoubleClicked.connect(on_list_double_clicked)
        
        
        def on_list_clicked(item):
            path = item.data(Qt.UserRole)
            if path:
                path_edit.setText(path)
        
        
        if select_folder or not allow_multiselect:
            
            list_view.setSelectionMode(QListWidget.SingleSelection)
        else:
            
            list_view.setSelectionMode(QListWidget.ExtendedSelection)
        list_view.itemClicked.connect(on_list_clicked)
        
        
        def on_view_mode_changed(index):
            if index == 0:  
                list_view.setViewMode(QListWidget.IconMode)
                list_view.setIconSize(QSize(scale(64), scale(64)))
                list_view.setGridSize(QSize(scale(100), scale(100)))
            else:  
                list_view.setViewMode(QListWidget.ListMode)
                list_view.setIconSize(QSize(scale(24), scale(24)))
                list_view.setGridSize(QSize())
        
        view_mode_combo.currentIndexChanged.connect(on_view_mode_changed)
        
        
        def on_back():
            nonlocal history, history_index
            if history_index > 0:
                history_index -= 1
                path = history[history_index]
                path_edit.setText(path)
                load_file_list(path)
                
                index = file_system_model.index(path)
                if index.isValid():
                    tree_view.setCurrentIndex(index)
                    
                    temp_index = index
                    while temp_index.isValid():
                        tree_view.expand(temp_index)
                        temp_index = temp_index.parent()
        
        def on_forward():
            nonlocal history, history_index
            if history_index < len(history) - 1:
                history_index += 1
                path = history[history_index]
                path_edit.setText(path)
                load_file_list(path)
                
                index = file_system_model.index(path)
                if index.isValid():
                    tree_view.setCurrentIndex(index)
                    
                    temp_index = index
                    while temp_index.isValid():
                        tree_view.expand(temp_index)
                        temp_index = temp_index.parent()
        
        back_action.triggered.connect(on_back)
        forward_action.triggered.connect(on_forward)
        
        
        selected_path = None
        selected_paths = []
        
        def on_ok():
            nonlocal selected_path, selected_paths
            if allow_multiselect and not select_folder:
                
                selected_items = list_view.selectedItems()
                if not selected_items:
                    
                    QMessageBox.warning(dialog, "错误", "请选择至少一个文件")
                    return
                
                
                valid_paths = []
                for item in selected_items:
                    path = item.data(Qt.UserRole)
                    if os.path.isfile(path):
                        if not file_filters or any(path.lower().endswith(filter.lower()) for filter in file_filters):
                            valid_paths.append(path)
                
                if not valid_paths:
                    
                    QMessageBox.warning(dialog, "错误", "选择的文件不符合筛选条件")
                    return
                
                selected_paths = valid_paths
                dialog.accept()
            else:
                
                path = path_edit.text()
                if select_folder:
                    
                    if os.path.isdir(path):
                        selected_path = path
                        dialog.accept()
                    else:
                        
                        QMessageBox.warning(dialog, "错误", "请选择一个文件夹")
                else:
                    
                    if os.path.isfile(path):
                        if not file_filters or any(path.lower().endswith(filter.lower()) for filter in file_filters):
                            selected_path = path
                            dialog.accept()
                        else:
                            
                            QMessageBox.warning(dialog, "错误", "选择的文件不符合筛选条件")
                    else:
                        
                        QMessageBox.warning(dialog, "错误", "请选择一个文件")
        
        def on_cancel():
            dialog.reject()
        
        ok_btn.clicked.connect(on_ok)
        cancel_btn.clicked.connect(on_cancel)
        
        
        if os.name == 'nt':
            drives = []
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for i in range(26):
                if bitmask & (1 << i):
                    drive = chr(65 + i) + ':/'
                    drives.append(drive)
        else:
            drives = ['/']
        
        
        initial_path = QDir.currentPath()
        path_edit.setText(initial_path)
        load_file_list(initial_path)
        
        
        index = file_system_model.index(initial_path)
        if index.isValid():
            tree_view.setCurrentIndex(index)
            
            while index.isValid():
                tree_view.expand(index)
                index = index.parent()
        
        
        if dialog.exec_() == QDialog.Accepted:
            if allow_multiselect and not select_folder:
                return selected_paths
            else:
                return selected_path
        else:
            return None

    def open_task_manager(self):
        if self.task_manager and self.download_manager:
            
            if not hasattr(self, 'task_window') or not self.task_window or not self.task_window.isVisible():
                
                self.task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config)
                self.task_window.show()
            else:
                
                self.task_window.show()
                self.task_window.raise_()
        else:
            QMessageBox.warning(self, "提示", "任务管理器初始化失败")

    def on_login_click(self, event):
        
        if not hasattr(self, 'parser') or not self.parser:
            self.show_notification("解析器未初始化，请重启应用", "error")
            return
        
        
        if hasattr(self, 'login_dialog') and self.login_dialog:
            self.login_dialog.show()
            self.login_dialog.raise_()
            return
        
        try:
            from utils import generate_qrcode, LoginPollThread
        except ImportError as e:
            self.show_notification(f"导入模块失败：{str(e)}", "error")
            return
        
        
        self.login_dialog = QDialog()
        self.login_dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.login_dialog.setAutoFillBackground(True)
        self.login_dialog.setWindowTitle("登录B站")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.login_dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(350), int(sg.height() * 0.3)))
        else:
            self.login_dialog.setMinimumSize(scale(500), scale(350))
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.login_dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        login_dialog = self.login_dialog
        
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
            QPushButton {
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #66b1ff;
            }
            QPushButton:pressed {
                background-color: #3a8ee6;
            }
            QLineEdit, QComboBox, QTextEdit {
                border-radius: 8px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border-color: #409eff;
            }
            QGroupBox {
                border: 1px solid #e9ecef;
                border-radius: 10px;
                padding: 20px;
                margin-top: 16px;
                background-color: white;
            }
            QGroupBox::title {
                font-size: 14px;
                font-weight: 600;
                color: #2563eb;
                margin-left: 12px;
                padding: 0 8px;
            }
        """)
        login_dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(login_dialog)
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        main_layout.setSpacing(scale(0))
        
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(15), scale(2), scale(10), scale(2))
        title_layout.setSpacing(scale(8))
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 28px; border-top-left-radius: 6px; border-top-right-radius: 6px;"))
        
        title_label = QLabel("登录B站")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet(scale_style("font-weight: bold; font-size: 13px;"))
        title_layout.addWidget(title_label, stretch=1)
        
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.setStyleSheet(scale_style("min-width: 28px; min-height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;"))
        minimize_btn.clicked.connect(login_dialog.hide)
        title_layout.addWidget(minimize_btn)
        
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setStyleSheet(scale_style("min-width: 28px; min-height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;"))
        close_btn.clicked.connect(login_dialog.hide)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        content_layout.setSpacing(scale(20))
        
        main_layout.addWidget(content_widget, stretch=1)
        
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        left_layout.setSpacing(scale(15))
        
        qr_title = QLabel("扫码登录")
        qr_title.setStyleSheet(scale_style("font-size: 18px; font-weight: bold; color: #2563eb;"))
        qr_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(qr_title)
        
        
        qr_code_label = QLabel()
        qr_code_label.setAlignment(Qt.AlignCenter)
        qr_code_label.setMinimumSize(scale(240), scale(240))
        qr_code_label.setMaximumSize(scale(240), scale(240))
        qr_code_label.setStyleSheet("border: none; background-color: #f8fafc; padding: 0; margin: 0;")
        left_layout.addWidget(qr_code_label, alignment=Qt.AlignCenter)
        
        qr_status = QLabel("请使用哔哩哔哩App扫码登录")
        qr_status.setAlignment(Qt.AlignCenter)
        qr_status.setStyleSheet(scale_style("font-size: 14px; color: #6b7280;"))
        left_layout.addWidget(qr_status)
        

        
        
        login_poll_thread = None
        
        
        
        class QRCodeThread(QThread):
            qrcode_ready = pyqtSignal(dict, bytes)  
            error = pyqtSignal(str)
            
            def __init__(self, parser):
                super().__init__()
                self.parser = parser
            
            def run(self):
                try:
                    
                    qrcode_video_info = self.parser.get_qrcode()
                    if not qrcode_video_info.get("success"):
                        error_msg = qrcode_video_info.get('error', '未知错误')
                        self.error.emit(error_msg)
                        return
                    
                    qrcode_url = qrcode_video_info.get("url")
                    qrcode_key = qrcode_video_info.get("qrcode_key")
                    
                    
                    qr_buffer = generate_qrcode(qrcode_url)
                    qr_data = qr_buffer.getvalue()
                    
                    
                    self.qrcode_ready.emit(qrcode_video_info, qr_data)
                except Exception as e:
                    error_msg = str(e)
                    print(f"获取二维码失败：{error_msg}")
                    traceback.print_exc()
                    self.error.emit(str(e))
        
        
        qr_thread = None
        qrcode_key = None
        last_click_time = 0
        
        def on_login_status_update(video_info):
            nonlocal login_poll_thread
            if video_info.get("success"):
                qr_status.setText("登录成功！正在加载用户信息...")
                qr_status.setStyleSheet(scale_style("font-size: 14px; color: #52c41a; text-align: center;"))
                
                user_info = video_info.get("user_info", {})
                if user_info.get("success"):
                    
                    self.load_local_cookie()
                    self.parser.user_info = user_info
                    self.show_notification("登录成功！", "success")
                    
                    self.update_login_info_display()
                else:
                    self.show_notification(f"登录成功但获取用户信息失败：{user_info.get('msg')}", "warning")
                
                if login_poll_thread and login_poll_thread.isRunning():
                    login_poll_thread.stop()
                login_dialog.hide()
            else:
                
                message = video_info.get("message", video_info.get("status", "未知状态"))
                qr_status.setText(message)
                
                
                if video_info.get("risk"):
                    qr_status.setStyleSheet(scale_style("font-size: 14px; color: #fa8c16; text-align: center;"))
                    
                    url = video_info.get("url", "")
                    def show_risk_message():
                        msg_box = QMessageBox()
                        msg_box.setWindowTitle("登录风险")
                        msg_box.setText(f"{message}\n\n请使用手机号进行验证或绑定。")
                        msg_box.setIcon(QMessageBox.Warning)
                        if url:
                            msg_box.addButton("打开验证链接", QMessageBox.ActionRole)
                        msg_box.addButton("取消", QMessageBox.RejectRole)
                        
                        reply = msg_box.exec_()
                        if reply == 0 and url:
                            
                            
                            
                            verify_dialog = QDialog(login_dialog)
                            verify_dialog.setWindowTitle("登录验证")
                            screen = QApplication.primaryScreen()
                            if screen:
                                sg = screen.availableGeometry()
                                verify_dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
                            else:
                                verify_dialog.setMinimumSize(scale(500), scale(400))
                            
                            
                            web_view = QWebEngineView()
                            web_view.setUrl(QUrl(url))
                            
                            
                            layout = QVBoxLayout(verify_dialog)
                            layout.addWidget(web_view)
                            
                            
                            verify_dialog.exec_()
                    
                    show_risk_message()
                elif video_info.get("status") == "二维码已失效" or "过期" in message:
                    
                    qr_status.setStyleSheet(scale_style("font-size: 14px; color: #f56c6c; text-align: center;"))
                    
                    if login_poll_thread and login_poll_thread.isRunning():
                        login_poll_thread.stop()
                    
                    def on_qr_status_clicked():
                        get_qrcode()
                    qr_status.mousePressEvent = lambda event: on_qr_status_clicked()
                else:
                    
                    qr_status.setStyleSheet(scale_style("font-size: 14px; color: #6b7280; text-align: center;"))
                
        
        def get_qrcode():
            nonlocal login_poll_thread, qr_thread, last_click_time, qrcode_key
            try:
                current_time = time.time()
                if current_time - last_click_time < 2:
                    return
                last_click_time = current_time
                
                qr_status.setText("刷新中...")
                qr_status.setStyleSheet(scale_style("font-size: 14px; color: #6b7280; text-align: center;"))
                
                
                if login_poll_thread:
                    if login_poll_thread.isRunning():
                        login_poll_thread.stop()
                        login_poll_thread.wait(1000)
                    login_poll_thread = None
                
                
                if qr_thread:
                    if qr_thread.isRunning():
                        qr_thread.quit()
                        qr_thread.wait(1000)
                    qr_thread = None
                
                
                qr_thread = QRCodeThread(self.parser)
                qr_thread.qrcode_ready.connect(on_qr_generated)
                qr_thread.error.connect(on_qr_error)
                qr_thread.start()
                
            except Exception as e:
                error_msg = str(e)
                print(f"获取二维码失败：{error_msg}")
                traceback.print_exc()
                qr_status.setText(f"错误：{error_msg}")
                qr_status.setStyleSheet(scale_style("font-size: 14px; color: #f56c6c; text-align: center;"))
        
        def on_qr_generated(qrcode_video_info, qr_data):
            nonlocal qrcode_key, login_poll_thread
            try:
                
                pixmap = QPixmap()
                success = pixmap.loadFromData(qr_data)
                
                if success:
                    pixmap = pixmap.scaled(scale(240), scale(240), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                    qr_code_label.setPixmap(pixmap)
                    
                    qr_status.setText("二维码生成成功，请扫描")
                    qr_status.setStyleSheet(scale_style("font-size: 14px; color: #6b7280; text-align: center;"))
                    
                    
                    qrcode_key = qrcode_video_info.get("qrcode_key")
                    
                    from utils import LoginPollThread
                    login_poll_thread = LoginPollThread(self.parser, qrcode_key)
                    login_poll_thread.status_signal.connect(on_login_status_update)
                    login_poll_thread.start()
                else:
                    qr_status.setText("二维码加载失败")
            except Exception as e:
                error_msg = str(e)
                print(f"显示二维码失败：{error_msg}")
                traceback.print_exc()
                qr_status.setText(f"错误：{error_msg}")
        
        def on_qr_error(error_msg):
            qr_status.setText(f"错误：{error_msg}")


        # 按钮容器
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        buttons_layout.setSpacing(scale(10))
        
        refresh_status_btn = QPushButton("刷新状态")
        refresh_status_btn.setMinimumHeight(scale(36))
        refresh_status_btn.setMinimumWidth(scale(100))
        refresh_status_btn.setStyleSheet(scale_style("background-color: #60a5fa; color: white; font-weight: 500; font-size: 12px; border-radius: 8px; padding: 0 12px;"))
        
        def on_refresh_status():
            nonlocal login_poll_thread, qrcode_key
            if qrcode_key:
                qr_status.setText("刷新状态中...")
                
                from utils import LoginPollThread
                if login_poll_thread and login_poll_thread.isRunning():
                    login_poll_thread.stop()
                    login_poll_thread.wait(1000)
                
                login_poll_thread = LoginPollThread(self.parser, qrcode_key)
                login_poll_thread.status_signal.connect(on_login_status_update)
                login_poll_thread.start()
        
        refresh_status_btn.clicked.connect(on_refresh_status)
        buttons_layout.addWidget(refresh_status_btn)
        
        refresh_btn = QPushButton("刷新二维码")
        refresh_btn.setMinimumHeight(scale(36))
        refresh_btn.setMinimumWidth(scale(100))
        refresh_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; font-weight: 500; font-size: 12px; border-radius: 8px; padding: 0 12px;"))
        refresh_btn.clicked.connect(get_qrcode)
        buttons_layout.addWidget(refresh_btn)
        
        left_layout.addWidget(buttons_widget, alignment=Qt.AlignCenter)

        left_layout.addStretch(1)
        content_layout.addWidget(left_widget, stretch=1)
        
        
        get_qrcode()
        
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(scale(20), scale(20), scale(20), scale(20))
        right_layout.setSpacing(scale(15))
        
        
        def on_dialog_close():
            
            if login_poll_thread:
                if login_poll_thread.isRunning():
                    login_poll_thread.stop()
                    login_poll_thread.wait(1000)
                login_poll_thread = None
            
            if qr_thread:
                if qr_thread.isRunning():
                    qr_thread.quit()
                    qr_thread.wait(1000)
                qr_thread = None  
        
        login_dialog.closeEvent = on_dialog_close
        
        
        tab_widget = QWidget()
        tab_layout = QHBoxLayout(tab_widget)
        tab_layout.setSpacing(scale(0))
        
        password_tab = QPushButton("账号密码")
        password_tab.setStyleSheet(scale_style("background-color: #409eff; color: white; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
        sms_tab = QPushButton("验证码")
        sms_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
        cookie_tab = QPushButton("Cookie")
        cookie_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
        
        tab_layout.addWidget(password_tab)
        tab_layout.addWidget(sms_tab)
        tab_layout.addWidget(cookie_tab)
        right_layout.addWidget(tab_widget)
        
        
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(scale(15))
        
        
        password_form = QWidget()
        password_layout = QVBoxLayout(password_form)
        password_layout.setSpacing(scale(16))
        
        
        risk_banner = QWidget()
        risk_banner.setStyleSheet(scale_style("""
            background-color: #fff7e6;
            border: 1px solid #ffd591;
            border-radius: 8px;
            padding: 12px;
        """))
        risk_layout = QHBoxLayout(risk_banner)
        risk_layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))
        risk_layout.setSpacing(scale(12))
        
        risk_label = QLabel("登录环境存在风险，需要验证")
        risk_label.setStyleSheet(scale_style("""
            font-size: 14px;
            font-weight: 500;
            color: #fa8c16;
            line-height: 1.4;
        """))
        risk_layout.addWidget(risk_label, stretch=1)
        
        verify_btn = QPushButton("前往验证")
        verify_btn.setStyleSheet(scale_style("""
            background-color: #fa8c16;
            color: white;
            font-size: 13px;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
        """))
        verify_btn.setMinimumHeight(scale(32))
        risk_layout.addWidget(verify_btn)
        
        risk_banner.hide()
        password_layout.addWidget(risk_banner)
        
        username_edit = QLineEdit()
        username_edit.setPlaceholderText("请输入手机号/邮箱")
        username_edit.setMinimumHeight(scale(44))
        username_edit.setStyleSheet(scale_style("font-size: 14px; padding: 0 16px;"))
        password_layout.addWidget(username_edit)
        
        password_edit = QLineEdit()
        password_edit.setPlaceholderText("请输入密码")
        password_edit.setEchoMode(QLineEdit.Password)
        password_edit.setMinimumHeight(scale(44))
        password_edit.setStyleSheet(scale_style("font-size: 14px; padding: 0 16px;"))
        password_layout.addWidget(password_edit)
        
        login_btn = QPushButton("登录")
        login_btn.setMinimumHeight(scale(44))
        login_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; font-weight: 500; font-size: 14px;"))
        password_layout.addWidget(login_btn)
        
        
        password_form.risk_banner = risk_banner
        password_form.risk_label = risk_label
        password_form.verify_btn = verify_btn
        
        
        sms_form = QWidget()
        sms_layout = QVBoxLayout(sms_form)
        sms_layout.setSpacing(scale(16))
        
        
        cid_combo = QComboBox()
        cid_combo.setEditable(True)  
        cid_combo.setMinimumHeight(scale(44))
        cid_combo.setStyleSheet(scale_style("font-size: 14px; padding: 0 16px;"))
        cid_combo.setMaxVisibleItems(6)  
        sms_layout.addWidget(cid_combo)
        
        
        def on_search_text_changed(text):
            
            cid_combo.lineEdit().textChanged.disconnect(on_search_text_changed)
            
            try:
                
                current_data = cid_combo.currentData()
                
                
                cid_combo.clear()
                
                
                if text:
                    
                    for country in global_country_list:
                        cid = country.get('cid')
                        name = country.get('name')
                        code = country.get('code')
                        if cid and name and code:
                            if text.lower() in name.lower() or text in str(code):
                                cid_combo.addItem(f"{name} (+{code})", cid)
                else:
                    
                    for country in global_country_list:
                        cid = country.get('cid')
                        name = country.get('name')
                        code = country.get('code')
                        if cid and name and code:
                            cid_combo.addItem(f"{name} (+{code})", cid)
                
                
                if current_data:
                    for i in range(cid_combo.count()):
                        if cid_combo.itemData(i) == current_data:
                            cid_combo.setCurrentIndex(i)
                            break
                else:
                    
                    if cid_combo.count() > 0:
                        cid_combo.setCurrentIndex(0)
            finally:
                
                cid_combo.lineEdit().textChanged.connect(on_search_text_changed)
        
        
        def on_combo_activated(index):
            
            if cid_combo.currentText() == "":
                cid_combo.clear()
                for country in global_country_list:
                    cid = country.get('cid')
                    name = country.get('name')
                    code = country.get('code')
                    if cid and name and code:
                        cid_combo.addItem(f"{name} (+{code})", cid)
                if cid_combo.count() > 0:
                    cid_combo.setCurrentIndex(0)
                    cid_combo.lineEdit().setText(cid_combo.itemText(0))
        
        
        
        
        cid_combo.activated.connect(on_combo_activated)
        
        
        cid_combo.lineEdit().textChanged.connect(on_search_text_changed)
        
        
        class ComboEventFilter(QObject):
            def eventFilter(self, obj, event):
                if event.type() == QEvent.MouseButtonPress:
                    try:
                        if cid_combo.currentText() == "":
                            cid_combo.clear()
                            for country in global_country_list:
                                cid = country.get('cid')
                                name = country.get('name')
                                code = country.get('code')
                                if cid and name and code:
                                    cid_combo.addItem(f"{name} (+{code})", cid)
                            if cid_combo.count() > 0:
                                cid_combo.setCurrentIndex(0)
                                line_edit = cid_combo.lineEdit()
                                if line_edit:
                                    line_edit.setText(cid_combo.itemText(0))
                    except Exception:
                        pass
                return False
        
        
        event_filter = ComboEventFilter()
        cid_combo.installEventFilter(event_filter)
        
        
        global_country_list = []
        
        
        def load_country_list():
            nonlocal global_country_list
            try:
                country_list = self.parser.get_country_list()
                global_country_list = country_list  
                if country_list:
                    
                    def update_country_combo():
                        
                        try:
                            cid_combo.lineEdit().textChanged.disconnect(on_search_text_changed)
                        except:
                            pass
                        
                        try:
                            
                            cid_combo.clear()
                            
                            for country in country_list:
                                cid = country.get('cid')
                                name = country.get('name')
                                code = country.get('code')
                                if cid and name and code:
                                    cid_combo.addItem(f"{name} (+{code})", cid)
                            
                            if cid_combo.count() > 0:
                                cid_combo.setCurrentIndex(0)
                        finally:
                            
                            cid_combo.lineEdit().textChanged.connect(on_search_text_changed)
                    QTimer.singleShot(0, update_country_combo)
                else:
                    
                    def add_default_country():
                        if cid_combo.count() == 0:
                            cid_combo.addItem("中国大陆 (+86)", 1)
                    QTimer.singleShot(0, add_default_country)
            except Exception as e:
                logger.error(f"获取国家代码列表失败：{str(e)}")
                
                def add_default_country():
                    if cid_combo.count() == 0:
                        cid_combo.addItem("中国大陆 (+86)", 1)
                QTimer.singleShot(0, add_default_country)
        
        
        import threading
        thread = threading.Thread(target=load_country_list)
        thread.daemon = True
        thread.start()
        
        
        cid_combo.addItem("中国大陆 (+86)", 1)
        
        cid_combo.setCurrentIndex(0)
        cid_combo.lineEdit().setText("中国大陆 (+86)")
        
        tel_edit = QLineEdit()
        tel_edit.setPlaceholderText("请输入手机号")
        tel_edit.setMinimumHeight(scale(44))
        tel_edit.setStyleSheet(scale_style("font-size: 14px; padding: 0 16px;"))
        sms_layout.addWidget(tel_edit)
        
        
        code_layout = QHBoxLayout()
        code_layout.setSpacing(scale(12))
        
        code_edit = QLineEdit()
        code_edit.setPlaceholderText("请输入验证码")
        code_edit.setMinimumHeight(scale(44))
        code_edit.setStyleSheet(scale_style("font-size: 14px; padding: 0 16px;"))
        code_layout.addWidget(code_edit, stretch=1)
        
        send_code_btn = QPushButton("发送验证码")
        send_code_btn.setMinimumHeight(scale(44))
        send_code_btn.setMinimumWidth(scale(130))
        send_code_btn.setStyleSheet(scale_style("background-color: #10b981; color: white; font-weight: 500; font-size: 14px;"))
        code_layout.addWidget(send_code_btn)
        
        
        if hasattr(self, 'sms_countdown_seconds') and self.sms_countdown_seconds > 0:
            send_code_btn.setEnabled(False)
            send_code_btn.setText(f"{self.sms_countdown_seconds}s后重新发送")
            
            self.sms_send_btn = send_code_btn
            
            
            def update_countdown():
                if hasattr(self, 'sms_countdown_seconds') and self.sms_countdown_seconds > 0:
                    self.sms_countdown_seconds -= 1
                    if hasattr(self, 'sms_send_btn') and self.sms_send_btn:
                        self.sms_send_btn.setText(f"{self.sms_countdown_seconds}s后重新发送")
                        QTimer.singleShot(1000, update_countdown)
                else:
                    if hasattr(self, 'sms_send_btn') and self.sms_send_btn:
                        self.sms_send_btn.setEnabled(True)
                        self.sms_send_btn.setText("发送验证码")
                        
                        if hasattr(self, 'sms_countdown_seconds'):
                            delattr(self, 'sms_countdown_seconds')
                        if hasattr(self, 'sms_send_btn'):
                            delattr(self, 'sms_send_btn')
            
            
            QTimer.singleShot(1000, update_countdown)
        
        sms_layout.addLayout(code_layout)
        
        sms_login_btn = QPushButton("登录")
        sms_login_btn.setMinimumHeight(scale(44))
        sms_login_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; font-weight: 500; font-size: 14px;"))
        sms_layout.addWidget(sms_login_btn)
        
        
        cookie_form = QWidget()
        cookie_layout = QVBoxLayout(cookie_form)
        cookie_layout.setSpacing(scale(16))
        
        cookie_edit = QTextEdit()
        cookie_edit.setPlaceholderText("请输入Cookie（SESSDATA/bili_jct/DedeUserID）")
        cookie_edit.setMinimumHeight(scale(120))
        cookie_edit.setStyleSheet(scale_style("font-size: 14px; padding: 12px;"))
        cookie_layout.addWidget(cookie_edit)
        
        cookie_login_btn = QPushButton("登录")
        cookie_login_btn.setMinimumHeight(scale(44))
        cookie_login_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; font-weight: 500; font-size: 14px;"))
        cookie_layout.addWidget(cookie_login_btn)
        
        
        form_stack = QStackedWidget()
        form_stack.addWidget(password_form)
        form_stack.addWidget(sms_form)
        form_stack.addWidget(cookie_form)
        form_layout.addWidget(form_stack)
        right_layout.addWidget(form_widget, stretch=1)
        content_layout.addWidget(right_widget, stretch=1)
        
        
        def switch_tab(tab_index):
            form_stack.setCurrentIndex(tab_index)
            if tab_index == 0:
                password_tab.setStyleSheet(scale_style("background-color: #409eff; color: white; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
                sms_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
                cookie_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
            elif tab_index == 1:
                password_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
                sms_tab.setStyleSheet(scale_style("background-color: #409eff; color: white; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
                cookie_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
            else:
                password_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
                sms_tab.setStyleSheet(scale_style("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
                cookie_tab.setStyleSheet(scale_style("background-color: #409eff; color: white; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;"))
        
        password_tab.clicked.connect(lambda: switch_tab(0))
        sms_tab.clicked.connect(lambda: switch_tab(1))
        cookie_tab.clicked.connect(lambda: switch_tab(2))
        
        
        QTimer.singleShot(100, lambda: None)
        
        
        def on_dialog_close(event):
            
            if login_poll_thread and login_poll_thread.isRunning():
                login_poll_thread.stop()
            
            if qr_thread and qr_thread.isRunning():
                qr_thread.quit()
                qr_thread.wait(1000)  
            
            login_dialog.hide()
            event.ignore()  
        
        login_dialog.closeEvent = on_dialog_close
        
        
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton and event.y() < scale(32):  
                login_dialog.dragging = True
                login_dialog.start_pos = event.globalPos() - login_dialog.frameGeometry().topLeft()
                event.accept()
        
        def mouseMoveEvent(event):
            if hasattr(login_dialog, 'dragging') and login_dialog.dragging and event.buttons() == Qt.LeftButton:
                login_dialog.move(event.globalPos() - login_dialog.start_pos)
                event.accept()
        
        def mouseReleaseEvent(event):
            if hasattr(login_dialog, 'dragging'):
                login_dialog.dragging = False
            event.accept()
        
        
        login_dialog.mousePressEvent = mousePressEvent
        login_dialog.mouseMoveEvent = mouseMoveEvent
        login_dialog.mouseReleaseEvent = mouseReleaseEvent
        
        
        def keyPressEvent(event):
            try:
                if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                    event.ignore()
                else:
                    QDialog.keyPressEvent(login_dialog, event)
            except Exception:
                event.ignore()
        
        login_dialog.keyPressEvent = keyPressEvent
        
        
        def on_password_login():
            username = username_edit.text().strip()
            password = password_edit.text().strip()
            if not username or not password:
                self.show_notification("请输入账号和密码", "warning")
                return
            
            
            self.show_notification("开始账号密码登录，请稍候...", "info")
            
            
            try:
                
                self.show_notification("正在获取验证码参数...", "info")
                captcha_video_info = self.parser.get_captcha()
                if not captcha_video_info.get("success"):
                    self.show_notification(f"获取验证码失败：{captcha_video_info.get('error')}", "error")
                    return
                
                gt = captcha_video_info.get("gt")
                challenge = captcha_video_info.get("challenge")
                token = captcha_video_info.get("token")
                print(f"获取验证码参数成功: gt={gt}, challenge={challenge}, token={token}")
                self.show_notification("获取验证码参数成功，准备显示人机验证...", "info")
                
                
                username_value = username
                password_value = password
                token_value = token
                login_dialog_ref = login_dialog
                
                
                def captcha_callback(validate, seccode, challenge):
                    if not validate:
                        self.show_notification("验证码验证取消", "info")
                        return
                    print(f"验证码验证成功: validate={validate}")
                    self.show_notification("人机验证成功，正在执行登录...", "info")
                    
                    
                    import threading
                    
                    
                    try:
                        
                        print("开始执行登录...")
                        video_info = self.parser.login_with_password(username_value, password_value, token_value, challenge, validate)
                        print(f"登录结果：{video_info}")
                        
                        if video_info.get("success"):
                            user_info = video_info.get("user_info", {})
                            if user_info.get("success"):
                                self.parser.user_info = user_info
                            self.show_notification("登录成功！", "success")
                            
                            self.update_login_info_display()
                            login_dialog_ref.hide()
                        else:
                            
                            error_msg = video_info.get("error", "登录失败")
                            self.show_notification(f"登录失败：{error_msg}", "error")
                            
                            
                            if video_info.get("risk"):
                                status = video_info.get("status", "未知风险")
                                url = video_info.get("url", "")
                                
                                self.show_notification(f"{status}\n\n请使用手机号进行验证或绑定。", "warning")
                                
                                
                                password_form.risk_banner.show()
                                password_form.risk_label.setText(status)
                                
                                
                                def on_verify_click():
                                    if url:
                                        
                                        
                                        
                                        verify_dialog = QDialog(login_dialog)
                                        verify_dialog.setWindowTitle("登录验证")
                                        screen = QApplication.primaryScreen()
                                        if screen:
                                            sg = screen.availableGeometry()
                                            verify_dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
                                        else:
                                            verify_dialog.setMinimumSize(scale(500), scale(400))
                                        
                                        
                                        web_view = QWebEngineView()
                                        web_view.setUrl(QUrl(url))
                                        
                                        
                                        layout = QVBoxLayout(verify_dialog)
                                        layout.addWidget(web_view)
                                        
                                        
                                        verify_dialog.exec_()
                                        
                                        
                                        self.show_notification("验证完成，正在重新尝试登录...", "info")
                                        
                                        
                                        try:
                                            video_info = self.parser.login_with_password(username_value, password_value, token_value, challenge, validate)
                                            print(f"验证后登录结果：{video_info}")
                                            
                                            if video_info.get("success"):
                                                user_info = video_info.get("user_info", {})
                                                if user_info.get("success"):
                                                    self.parser.user_info = user_info
                                                self.show_notification("登录成功！", "success")
                                                
                                                self.update_login_info_display()
                                                login_dialog_ref.hide()
                                            else:
                                                
                                                error_msg = video_info.get("error", "登录失败")
                                                self.show_notification(f"登录失败：{error_msg}", "error")
                                        except Exception as e:
                                            print(f"验证后登录失败：{str(e)}")
                                            self.show_notification(f"登录失败：{str(e)}", "error")
                                
                                
                                try:
                                    password_form.verify_btn.clicked.disconnect()
                                except:
                                    pass
                                
                                
                                password_form.verify_btn.clicked.connect(on_verify_click)
                                
                                
                                switch_tab(1)
                            else:
                                
                                if "环境" in error_msg or "异常" in error_msg:
                                    
                                    self.show_notification(f"{error_msg}\n\n请检查网络环境或尝试使用其他登录方式。", "warning")
                                    
                                    switch_tab(1)
                    except Exception as e:
                        logger.error(f"账号密码登录失败：{str(e)}")
                        self.show_notification(f"登录失败：{str(e)}", "error")
                
                
                show_captcha_dialog(gt, challenge, captcha_callback, login_dialog)
            except Exception as e:
                logger.error(f"获取验证码失败：{str(e)}")
                self.show_notification(f"获取验证码失败：{str(e)}", "error")
        
        
        def on_send_code():
            
            if hasattr(self, 'sms_countdown_seconds') and self.sms_countdown_seconds > 0:
                self.show_notification(f"请在{self.sms_countdown_seconds}秒后重新发送", "info")
                return
            
            tel = tel_edit.text().strip()
            if not tel:
                self.show_notification("请输入手机号", "warning")
                return
            
            
            import re
            if not re.match(r'^1[3-9]\d{9}$', tel):
                self.show_notification("请输入正确的手机号", "warning")
                return
            
            
            self.show_notification("开始发送验证码，请稍候...", "info")
            
            
            try:
                
                self.show_notification("正在获取验证码参数...", "info")
                captcha_video_info = self.parser.get_captcha()
                if not captcha_video_info.get("success"):
                    self.show_notification(f"获取验证码失败：{captcha_video_info.get('error')}", "error")
                    return
                
                gt = captcha_video_info.get("gt")
                challenge = captcha_video_info.get("challenge")
                token = captcha_video_info.get("token")
                print(f"获取验证码参数成功: gt={gt}, challenge={challenge}, token={token}")
                self.show_notification("获取验证码参数成功，准备显示人机验证...", "info")
                
                
                cid_value = cid_combo.currentData()
                
                if cid_value is None:
                    cid_value = 86
                    print("cid值为None，使用默认值86")
                tel_value = tel
                token_value = token
                send_code_btn_ref = send_code_btn
                
                
                def captcha_callback(validate, seccode, challenge):
                    if not validate:
                        self.show_notification("验证码验证取消", "info")
                        return
                    print(f"验证码验证成功: validate={validate}")
                    self.show_notification("人机验证成功，正在发送验证码...", "info")
                    
                    
                    try:
                        
                        print("开始发送验证码...")
                        video_info = self.parser.send_sms_code(cid_value, tel_value, token_value, challenge, validate)
                        print(f"发送验证码结果：{video_info}")
                        
                        
                        if video_info.get('success'):
                            
                            captcha_key = video_info.get('data', {}).get('captcha_key', '')
                            if captcha_key:
                                
                                self.sms_captcha_key = captcha_key
                                print(f"保存captcha_key成功: {captcha_key}")
                            
                            
                            self.show_notification("验证码发送成功！", "success")
                            
                            
                            print("开始60秒倒计时...")
                            
                            self.sms_countdown_seconds = 60
                            self.sms_send_btn = send_code_btn_ref
                            send_code_btn_ref.setEnabled(False)
                            
                            def update_countdown():
                                if hasattr(self, 'sms_countdown_seconds') and self.sms_countdown_seconds > 0:
                                    self.sms_countdown_seconds -= 1
                                    if hasattr(self, 'sms_send_btn') and self.sms_send_btn:
                                        self.sms_send_btn.setText(f"{self.sms_countdown_seconds}s后重新发送")
                                        QTimer.singleShot(1000, update_countdown)
                                else:
                                    if hasattr(self, 'sms_send_btn') and self.sms_send_btn:
                                        self.sms_send_btn.setEnabled(True)
                                        self.sms_send_btn.setText("发送验证码")
                                        
                                        if hasattr(self, 'sms_countdown_seconds'):
                                            delattr(self, 'sms_countdown_seconds')
                                        if hasattr(self, 'sms_send_btn'):
                                            delattr(self, 'sms_send_btn')
                            
                            
                            QTimer.singleShot(0, update_countdown)
                            print("发送验证码执行完成")
                        else:
                            
                            error_msg = video_info.get('error', '发送失败')
                            logger.error(f"发送验证码失败：{error_msg}")
                            self.show_notification(f"发送验证码失败：{error_msg}", "error")
                    except Exception as e:
                        logger.error(f"发送验证码失败：{str(e)}")
                        self.show_notification(f"发送验证码失败：{str(e)}", "error")
                
                
                show_captcha_dialog(gt, challenge, captcha_callback, login_dialog)
            except Exception as e:
                logger.error(f"获取验证码失败：{str(e)}")
                self.show_notification(f"获取验证码失败：{str(e)}", "error")
        
        
        def on_sms_login():
            tel = tel_edit.text().strip()
            code = code_edit.text().strip()
            if not tel or not code:
                self.show_notification("请输入手机号和验证码", "warning")
                return
            
            
            if not hasattr(self, 'sms_captcha_key') or not self.sms_captcha_key:
                self.show_notification("请先发送验证码", "warning")
                return
            
            
            self.show_notification("开始验证码登录，请稍候...", "info")
            
            try:
                
                cid_value = cid_combo.currentData()
                
                if cid_value is None:
                    cid_value = 86
                    print("cid值为None，使用默认值86")
                tel_value = tel
                code_value = code
                captcha_key_value = self.sms_captcha_key
                login_dialog_ref = login_dialog
                
                
                try:
                    
                    print("开始执行短信验证码登录...")
                    video_info = self.parser.login_with_sms(cid_value, tel_value, code_value, captcha_key_value)
                    print(f"登录结果：{video_info}")
                    
                    if video_info.get("success"):
                        user_info = video_info.get("user_info", {})
                        if user_info.get("success"):
                            self.parser.user_info = user_info
                        self.show_notification("登录成功！", "success")
                        
                        self.update_login_info_display()
                        login_dialog_ref.hide()
                    else:
                        
                        error_msg = video_info.get("error", "登录失败")
                        self.show_notification(f"登录失败：{error_msg}", "error")
                        
                        
                        if video_info.get("risk"):
                            status = video_info.get("status", "未知风险")
                            url = video_info.get("url", "")
                            
                            self.show_notification(f"{status}\n\n请使用手机号进行验证或绑定。", "warning")
                        else:
                            
                            if "环境" in error_msg or "异常" in error_msg:
                                
                                self.show_notification(f"{error_msg}\n\n请检查网络环境或尝试使用其他登录方式。", "warning")
                except Exception as e:
                    logger.error(f"验证码登录失败：{str(e)}")
                    self.show_notification(f"登录失败：{str(e)}", "error")
            except Exception as e:
                logger.error(f"登录失败：{str(e)}")
                self.show_notification(f"登录失败：{str(e)}", "error")
        
        
        def on_cookie_login():
            cookie = cookie_edit.toPlainText().strip()
            
            if not cookie:
                self.show_notification("请输入Cookie", "warning")
                return
            
            if not hasattr(self, 'parser') or not self.parser:
                self.show_notification("解析器未初始化，请重启应用", "error")
                return
            
            self._cookie_login_btn = cookie_login_btn
            cookie_login_btn.setEnabled(False)
            cookie_login_btn.setText("登录中...")
            self.show_notification("正在验证Cookie，请稍候...", "info")
            
            import threading
            def login_thread():
                try:
                    logger.info("Cookie登录线程启动，开始保存Cookie...")
                    save_success = self.parser.save_cookies(cookie)
                    logger.info(f"Cookie保存结果：{save_success}")
                    
                    if save_success:
                        success, msg = self.parser.verify_cookie()
                        logger.info(f"Cookie验证结果：success={success}, msg={msg}")
                        self.signal_emitter.cookie_verified.emit(success, msg)
                    else:
                        logger.warning("Cookie格式错误，保存失败")
                        self.signal_emitter.cookie_verified.emit(False, "Cookie格式错误，请检查格式")
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Cookie登录异常：{error_msg}")
                    self.signal_emitter.cookie_verified.emit(False, f"登录异常：{error_msg}")
            
            thread = threading.Thread(target=login_thread)
            thread.daemon = True
            thread.start()
        
        
        login_btn.clicked.connect(on_password_login)
        send_code_btn.clicked.connect(on_send_code)
        sms_login_btn.clicked.connect(on_sms_login)
        cookie_login_btn.clicked.connect(on_cookie_login)
        
        
        username_edit.returnPressed.connect(on_password_login)
        password_edit.returnPressed.connect(on_password_login)
        tel_edit.returnPressed.connect(on_send_code)
        code_edit.returnPressed.connect(on_sms_login)
        
        
        login_dialog.show()

    def open_settings(self):
        if hasattr(self, 'settings_dialog') and self.settings_dialog and self.settings_dialog.isVisible():
            self.settings_dialog.show()
            self.settings_dialog.raise_()
            return
            
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        dialog.setAutoFillBackground(True)
        dialog.setWindowTitle("设置")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
            dialog.resize(min(scale(900), int(sg.width() * 0.85)), min(scale(750), int(sg.height() * 0.85)))
        else:
            dialog.setMinimumSize(scale(500), scale(400))
            dialog.resize(scale(900), scale(750))
        
        # 设置窗口图标
        try:
            import sys
            if hasattr(sys, '_MEIPASS'):
                # 在EXE模式下
                logo_path = os.path.join(sys._MEIPASS, "logo.ico")
            else:
                # 在开发模式下
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        
        custom_style = get_base_style() + scale_style("""
            QDialog {
                border: 2px solid #409eff;
                background-color: white;
            }
        """)
        dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(scale(2), scale(0), scale(2), scale(2))
        main_layout.setSpacing(scale(0))

        dialog.mousePressEvent = lambda event: setattr(dialog, '_mouse_pos', event.globalPos() - dialog.pos())
        dialog.mouseMoveEvent = lambda event: dialog.move(event.globalPos() - getattr(dialog, '_mouse_pos', QPoint(0, 0))) if hasattr(dialog, '_mouse_pos') else None
        dialog.mouseReleaseEvent = lambda event: setattr(dialog, '_mouse_pos', None)

        title_bar = QWidget()
        title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), scale(0), scale(12), scale(0))
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("设置")
        title_label.setStyleSheet(scale_style("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;"))
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(scale_style("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; min-width: 28px; min-height: 28px; border-radius: 14px;"))
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
        body_layout.setSpacing(scale(0))

        sidebar = QListWidget()
        sidebar.setFixedWidth(scale(160))
        sidebar_items = ["下载设置", "网络设置", "窗口设置", "其他设置"]
        for item_text in sidebar_items:
            item = QListWidgetItem(item_text)
            sidebar.addItem(item)
        sidebar.setCurrentRow(0)
        sidebar.setStyleSheet(scale_style("""
            QListWidget {
                background-color: #f5f7fa;
                border: none;
                border-right: 1px solid #e9ecef;
                outline: none;
                padding: 8px 4px;
            }
            QListWidget::item {
                padding: 12px 16px;
                margin: 4px 6px;
                border-radius: 8px;
                color: #333333;
                font-size: 14px;
                font-weight: 500;
            }
            QListWidget::item:selected {
                background-color: #409eff;
                color: white;
            }
            QListWidget::item:hover:!selected {
                background-color: #e8f4ff;
                color: #333333;
            }
        """))
        body_layout.addWidget(sidebar)

        stacked_widget = QStackedWidget()
        stacked_widget.setStyleSheet("QStackedWidget { background-color: white; }")

        
        # 默认下载路径
        path_group = QGroupBox("默认下载路径")
        path_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"))
        path_layout = QVBoxLayout(path_group)
        path_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        path_layout.setSpacing(scale(8))
        
        current_default = self.config.get_app_setting("default_save_path")
        if not current_default:
            current_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        
        path_edit = QLineEdit(current_default)
        path_edit.setMinimumHeight(scale(32))
        path_edit.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;"))
        path_layout.addWidget(path_edit)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setMinimumHeight(scale(32))
        browse_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; border-radius: 6px; padding: 8px 16px;"))
        
        def browse_path():
            path = self.show_custom_file_dialog("选择默认保存路径")
            if path:
                path_edit.setText(path)
        
        browse_btn.clicked.connect(browse_path)
        path_layout.addWidget(browse_btn)
        
        

        
        # 下载线程数
        thread_group = QGroupBox("下载线程数")
        thread_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }"))
        thread_layout = QVBoxLayout(thread_group)
        thread_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        
        thread_spin = QComboBox()
        thread_spin.setMinimumHeight(scale(32))
        thread_spin.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;"))
        for i in range(1, 11):
            thread_spin.addItem(str(i), i)
        current_threads = self.config.get_app_setting("max_threads", 2)
        thread_spin.setCurrentIndex(current_threads - 1)
        thread_layout.addWidget(thread_spin)
        
        
        
        # 系统托盘
        tray_group = QGroupBox("系统托盘")
        tray_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QCheckBox { spacing: 8px; font-size: 13px; }"))
        tray_layout = QVBoxLayout(tray_group)
        tray_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        
        minimize_to_tray_checkbox = QCheckBox("关闭窗口时最小化到托盘")
        minimize_to_tray_checkbox.setChecked(self.config.get_app_setting("minimize_to_tray", True))
        tray_layout.addWidget(minimize_to_tray_checkbox)
        
        

        
        # 窗口设置
        window_group = QGroupBox("窗口设置")
        window_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QCheckBox { spacing: 8px; font-size: 13px; }"))
        window_layout = QVBoxLayout(window_group)
        window_layout.setContentsMargins(scale(10), scale(10), scale(10), scale(10))
        
        topmost_checkbox = QCheckBox("窗口置顶")
        is_topmost = self.windowFlags() & Qt.WindowStaysOnTopHint
        topmost_checkbox.setChecked(is_topmost)
        window_layout.addWidget(topmost_checkbox)
        
        

        # 下载设置组
        download_group = QGroupBox("下载设置")
        download_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QLabel { font-size: 13px; } QCheckBox { spacing: 8px; font-size: 13px; } QComboBox { max-width: 200px; }"))
        download_layout = QVBoxLayout(download_group)
        download_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        download_layout.setSpacing(scale(8))
        
        # 默认下载质量
        quality_layout = QHBoxLayout()
        quality_label = QLabel("默认下载质量：")
        quality_label.setMinimumHeight(scale(22))
        quality_combo = QComboBox()
        quality_combo.setMinimumHeight(scale(26))
        quality_combo.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px; max-width: 200px;"))
        
        # 获取用户登录状态
        is_vip = False
        if self.parser:
            user_info = self.parser.get_user_info()
            is_vip = user_info.get('is_vip', False)
        
        # 根据VIP状态设置可用的质量选项
        quality_options = [
            ("自动选择最高质量", 0),
            ("1080P", 80),
            ("720P", 64),
            ("480P", 32),
            ("360P", 16)
        ]
        
        # VIP用户额外的质量选项
        if is_vip:
            vip_options = [
                ("4K 杜比视界", 127),
                ("4K HDR", 125),
                ("1080P高码率", 120),
                ("1080P60", 116),
                ("1080P+", 112),
                ("720P高码率", 74)
            ]
            # 将VIP选项插入到自动选择之后
            quality_options = [quality_options[0]] + vip_options + quality_options[1:]
        
        for text, value in quality_options:
            quality_combo.addItem(text, value)
        current_quality = self.config.get_app_setting("default_quality", 0)
        
        # 确保当前选择的质量在可用选项中
        current_index = 0
        for i, (text, value) in enumerate(quality_options):
            if value == current_quality:
                current_index = i
                break
        quality_combo.setCurrentIndex(current_index)
        self.config.set_app_setting("default_quality", quality_combo.itemData(current_index))
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(quality_combo, stretch=1)
        download_layout.addLayout(quality_layout)
        
        # 复选框布局（三行两列）
        checkbox_layout = QGridLayout()
        checkbox_layout.setSpacing(scale(8))
        
        # 自动下载封面
        auto_cover_checkbox = QCheckBox("自动下载视频封面")
        auto_cover_checkbox.setMinimumHeight(scale(22))
        auto_cover_checkbox.setChecked(self.config.get_app_setting("auto_download_cover", True))
        checkbox_layout.addWidget(auto_cover_checkbox, 0, 0)
        
        # 自动下载弹幕
        auto_danmaku_checkbox = QCheckBox("自动下载弹幕文件")
        auto_danmaku_checkbox.setMinimumHeight(scale(22))
        auto_danmaku_checkbox.setChecked(self.config.get_app_setting("auto_download_danmaku", False))
        checkbox_layout.addWidget(auto_danmaku_checkbox, 0, 1)
        
        # 下载完成后打开文件夹
        auto_open_folder_checkbox = QCheckBox("下载完成后打开文件夹")
        auto_open_folder_checkbox.setMinimumHeight(scale(22))
        auto_open_folder_checkbox.setChecked(self.config.get_app_setting("auto_open_folder", False))
        checkbox_layout.addWidget(auto_open_folder_checkbox, 1, 0)
        
        # 下载完成后播放提示音
        play_sound_checkbox = QCheckBox("下载完成后播放提示音")
        play_sound_checkbox.setMinimumHeight(scale(22))
        play_sound_checkbox.setChecked(self.config.get_app_setting("play_sound_on_complete", True))
        checkbox_layout.addWidget(play_sound_checkbox, 1, 1)
        
        # 文件名添加集数前缀
        add_episode_prefix_checkbox = QCheckBox("文件名添加集数前缀（如：第1集 - 标题）")
        add_episode_prefix_checkbox.setMinimumHeight(scale(22))
        add_episode_prefix_checkbox.setChecked(self.config.get_app_setting("add_episode_to_filename", True))
        checkbox_layout.addWidget(add_episode_prefix_checkbox, 2, 0, 1, 2)
        
        download_layout.addLayout(checkbox_layout)
        
        # 视频输出格式
        video_format_layout = QHBoxLayout()
        video_format_label = QLabel("视频输出格式：")
        video_format_label.setMinimumHeight(scale(22))
        video_format_combo = QComboBox()
        video_format_combo.setMinimumHeight(scale(26))
        video_format_combo.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px; max-width: 200px;"))
        video_format_options = [
            ("MP4", "mp4"),
            ("MKV", "mkv"),
            ("WEBM", "webm"),
            ("AVI", "avi"),
            ("MOV", "mov"),
            ("WMV", "wmv"),
            ("FLV", "flv"),
            ("TS", "ts"),
            ("MTS", "mts"),
            ("M2TS", "m2ts"),
            ("OGV", "ogv"),
            ("M4V", "m4v"),
            ("3GP", "3gp"),
            ("3G2", "3g2"),
            ("ASF", "asf"),
            ("DIVX", "divx"),
            ("XVID", "xvid"),
            ("MPEG", "mpeg"),
            ("MPG", "mpg"),
            ("MPEG2", "mp2"),
            ("MPEG4", "mp4"),
            ("H264", "h264"),
            ("H265", "h265"),
            ("HEVC", "hevc"),
            ("VP8", "vp8"),
            ("VP9", "vp9"),
            ("AV1", "av1"),
            ("MJPEG", "mjpeg"),
            ("MJPG", "mjpg"),
            ("YUV", "yuv"),
            ("RAW", "raw"),
            ("DV", "dv"),
            ("OGG", "ogg"),
            ("MXF", "mxf"),
            ("GXF", "gxf"),
            ("VOB", "vob"),
            ("IFO", "ifo"),
            ("BDAV", "bdav"),
            ("PVA", "pva"),
            ("F4V", "f4v"),
            ("SWF", "swf"),
            ("RM", "rm"),
            ("RMVB", "rmvb"),
            ("MPEGTS", "ts"),
            ("M2TS", "m2ts"),
            ("MTS", "mts"),
            ("TP", "tp"),
            ("TRP", "trp"),
            ("MPEGPS", "mpg"),
            ("MPEG1", "mpg"),
            ("MPEG2", "mpg"),
            ("VCD", "dat"),
            ("SVCD", "svcd"),
            ("DVD", "vob"),
            ("Blu-ray", "m2ts"),
            ("AMV", "amv")
        ]
        for text, value in video_format_options:
            video_format_combo.addItem(text, value)
        current_video_format = self.config.get_app_setting("video_output_format", "mp4")
        for i, (text, value) in enumerate(video_format_options):
            if value == current_video_format:
                video_format_combo.setCurrentIndex(i)
                break
        video_format_combo.setMaxVisibleItems(5)
        video_format_combo.setEditable(True)
        video_format_combo.setInsertPolicy(QComboBox.NoInsert)
        completer = QCompleter([text for text, value in video_format_options])
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        video_format_combo.setCompleter(completer)
        video_format_layout.addWidget(video_format_label)
        video_format_layout.addWidget(video_format_combo, stretch=1)
        download_layout.addLayout(video_format_layout)
        
        # 音频质量选择
        audio_quality_layout = QHBoxLayout()
        audio_quality_label = QLabel("音频质量：")
        audio_quality_label.setMinimumHeight(scale(22))
        audio_quality_combo = QComboBox()
        audio_quality_combo.setMinimumHeight(scale(26))
        audio_quality_combo.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px; max-width: 200px;"))
        audio_quality_options = [
            ("Hi-Res无损", 30251),
            ("杜比全景声", 30250),
            ("高音质 (320K)", 100010),
            ("高音质 (192K)", 30280),
            ("标准音质 (192K)", 100009),
            ("标准音质 (132K)", 30232),
            ("低音质 (128K)", 100008),
            ("低音质 (64K)", 30216)
        ]
        for text, value in audio_quality_options:
            audio_quality_combo.addItem(text, value)
        current_audio_quality = self.config.get_app_setting("audio_quality", 30280)
        for i, (text, value) in enumerate(audio_quality_options):
            if value == current_audio_quality:
                audio_quality_combo.setCurrentIndex(i)
                break
        audio_quality_combo.setMaxVisibleItems(5)
        audio_quality_combo.setEditable(False)
        audio_quality_layout.addWidget(audio_quality_label)
        audio_quality_layout.addWidget(audio_quality_combo, stretch=1)
        download_layout.addLayout(audio_quality_layout)
        
        # 弹幕输出格式
        danmaku_format_layout = QHBoxLayout()
        danmaku_format_label = QLabel("弹幕输出格式：")
        danmaku_format_label.setMinimumHeight(scale(22))
        danmaku_format_combo = QComboBox()
        danmaku_format_combo.setMinimumHeight(scale(26))
        danmaku_format_combo.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px; max-width: 200px;"))
        danmaku_format_options = [
            ("XML", "xml"),
            ("ASS", "ass"),
            ("JSON", "json")
        ]
        for text, value in danmaku_format_options:
            danmaku_format_combo.addItem(text, value)
        current_danmaku_format = self.config.get_app_setting("danmaku_output_format", "xml")
        for i, (text, value) in enumerate(danmaku_format_options):
            if value == current_danmaku_format:
                danmaku_format_combo.setCurrentIndex(i)
                break
        danmaku_format_combo.setMaxVisibleItems(5)
        danmaku_format_combo.setEditable(True)
        danmaku_format_combo.setInsertPolicy(QComboBox.NoInsert)
        completer = QCompleter([text for text, value in danmaku_format_options])
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        danmaku_format_combo.setCompleter(completer)
        danmaku_format_layout.addWidget(danmaku_format_label)
        danmaku_format_layout.addWidget(danmaku_format_combo, stretch=1)
        download_layout.addLayout(danmaku_format_layout)
        
        
        # 网络设置组
        network_group = QGroupBox("网络设置")
        network_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QLabel { font-size: 13px; } QComboBox { max-width: 150px; }"))
        network_layout = QVBoxLayout(network_group)
        network_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        network_layout.setSpacing(scale(10))
        
        # 超时时间
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("网络超时时间（秒）：")
        timeout_spin = QComboBox()
        timeout_spin.setMinimumHeight(scale(28))
        timeout_spin.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px; max-width: 150px;"))
        for i in [5, 10, 15, 20, 30, 60]:
            timeout_spin.addItem(str(i), i)
        current_timeout = self.config.get_app_setting("network_timeout", 15)
        for i in range(timeout_spin.count()):
            if timeout_spin.itemData(i) == current_timeout:
                timeout_spin.setCurrentIndex(i)
                break
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(timeout_spin, stretch=1)
        network_layout.addLayout(timeout_layout)
        
        # 重试次数
        retry_layout = QHBoxLayout()
        retry_label = QLabel("下载失败重试次数：")
        retry_spin = QComboBox()
        retry_spin.setMinimumHeight(scale(28))
        retry_spin.setStyleSheet(scale_style("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px; max-width: 150px;"))
        for i in [1, 2, 3, 5, 10]:
            retry_spin.addItem(str(i), i)
        current_retry = self.config.get_app_setting("max_retry", 3)
        for i in range(retry_spin.count()):
            if retry_spin.itemData(i) == current_retry:
                retry_spin.setCurrentIndex(i)
                break
        retry_layout.addWidget(retry_label)
        retry_layout.addWidget(retry_spin, stretch=1)
        network_layout.addLayout(retry_layout)
        
        
        # 其他设置组
        other_group = QGroupBox("其他设置")
        other_group.setStyleSheet(scale_style("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QCheckBox { spacing: 8px; font-size: 13px; }"))
        other_layout = QVBoxLayout(other_group)
        other_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        other_layout.setSpacing(scale(8))
        
        # 复选框布局（两行三列）
        other_checkbox_layout = QGridLayout()
        other_checkbox_layout.setSpacing(scale(8))
        
        # 自动检查更新
        auto_update_checkbox = QCheckBox("启动时自动检查更新")
        auto_update_checkbox.setChecked(self.config.get_app_setting("auto_check_update", True))
        other_checkbox_layout.addWidget(auto_update_checkbox, 0, 0)
        
        # 显示下载速度
        show_speed_checkbox = QCheckBox("显示下载速度")
        show_speed_checkbox.setChecked(self.config.get_app_setting("show_download_speed", True))
        other_checkbox_layout.addWidget(show_speed_checkbox, 0, 1)
        
        # 显示悬浮球
        show_float_checkbox = QCheckBox("显示悬浮球")
        show_float_checkbox.setChecked(self.config.get_app_setting("show_floating_ball", True))
        other_checkbox_layout.addWidget(show_float_checkbox, 0, 2)
        
        # 显示合并窗口
        show_merge_window_checkbox = QCheckBox("显示合并进度窗口")
        show_merge_window_checkbox.setChecked(self.config.get_app_setting("show_merge_window", False))
        other_checkbox_layout.addWidget(show_merge_window_checkbox, 1, 0)

        # 自动转换不兼容视频
        auto_convert_checkbox = QCheckBox("下载完成后自动转换不兼容视频(AV1/HEVC)")
        auto_convert_checkbox.setChecked(self.config.get_app_setting("auto_convert_incompatible", False))
        other_checkbox_layout.addWidget(auto_convert_checkbox, 1, 1)

        # HEVC不支持时询问
        hevc_not_support_ask_checkbox = QCheckBox("HEVC/AV1视频下载时询问是否安装解码器")
        hevc_not_support_ask_checkbox.setChecked(self.config.get_app_setting("hevc_not_supported_ask", True))
        other_checkbox_layout.addWidget(hevc_not_support_ask_checkbox, 2, 0, 1, 3)
        
        other_layout.addLayout(other_checkbox_layout)

        page1_scroll = QScrollArea()
        page1_scroll.setWidgetResizable(True)
        page1_scroll.setStyleSheet("QScrollArea { border: none; }")
        page1_widget = QWidget()
        page1_layout = QVBoxLayout(page1_widget)
        page1_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        page1_layout.setSpacing(scale(15))
        page1_layout.addWidget(path_group)
        page1_layout.addWidget(thread_group)
        page1_layout.addWidget(download_group)
        page1_layout.addStretch(1)
        page1_scroll.setWidget(page1_widget)
        stacked_widget.addWidget(page1_scroll)

        page2_scroll = QScrollArea()
        page2_scroll.setWidgetResizable(True)
        page2_scroll.setStyleSheet("QScrollArea { border: none; }")
        page2_widget = QWidget()
        page2_layout = QVBoxLayout(page2_widget)
        page2_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        page2_layout.setSpacing(scale(15))
        page2_layout.addWidget(network_group)
        page2_layout.addStretch(1)
        page2_scroll.setWidget(page2_widget)
        stacked_widget.addWidget(page2_scroll)

        page3_scroll = QScrollArea()
        page3_scroll.setWidgetResizable(True)
        page3_scroll.setStyleSheet("QScrollArea { border: none; }")
        page3_widget = QWidget()
        page3_layout = QVBoxLayout(page3_widget)
        page3_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        page3_layout.setSpacing(scale(15))
        page3_layout.addWidget(tray_group)
        page3_layout.addWidget(window_group)
        page3_layout.addStretch(1)
        page3_scroll.setWidget(page3_widget)
        stacked_widget.addWidget(page3_scroll)

        page4_scroll = QScrollArea()
        page4_scroll.setWidgetResizable(True)
        page4_scroll.setStyleSheet("QScrollArea { border: none; }")
        page4_widget = QWidget()
        page4_layout = QVBoxLayout(page4_widget)
        page4_layout.setContentsMargins(scale(15), scale(15), scale(15), scale(15))
        page4_layout.setSpacing(scale(15))
        page4_layout.addWidget(other_group)
        page4_layout.addStretch(1)
        page4_scroll.setWidget(page4_widget)
        stacked_widget.addWidget(page4_scroll)

        sidebar.currentRowChanged.connect(stacked_widget.setCurrentIndex)
        body_layout.addWidget(stacked_widget, stretch=1)
        main_layout.addLayout(body_layout, stretch=1)

        # 按钮布局（放在滚动区域外面）
        btn_widget = QWidget()
        btn_widget.setStyleSheet(scale_style("background-color: #f8f9fa; border-top: 1px solid #e9ecef;"))
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(scale(15), scale(10), scale(15), scale(10))
        btn_layout.setSpacing(scale(10))
        
        save_btn = QPushButton("保存")
        save_btn.setMinimumHeight(scale(32))
        save_btn.setMinimumWidth(scale(80))
        save_btn.setStyleSheet(scale_style("background-color: #409eff; color: white; font-weight: 500; border-radius: 6px; padding: 6px 16px;"))
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(scale(32))
        cancel_btn.setMinimumWidth(scale(80))
        cancel_btn.setStyleSheet(scale_style("background-color: #f56c6c; color: white; font-weight: 500; border-radius: 6px; padding: 6px 16px;"))
        
        def on_save():
            new_path = path_edit.text().strip()
            if new_path:
                self.config.set_app_setting("default_save_path", new_path)
                self.config.set_app_setting("last_save_path", new_path)
                self.path_edit.setText(new_path)
            
            new_threads = thread_spin.currentData()
            self.config.set_app_setting("max_threads", new_threads)
            if self.download_manager:
                self.download_manager.set_max_threads(new_threads)
            
            
            is_topmost = topmost_checkbox.isChecked()
            self.config.set_app_setting("window_topmost", is_topmost)
            
            if is_topmost:
                self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
            
            self.show()
            logger.info(f"线程数已修改为：{new_threads}")
            
            
            minimize_to_tray = minimize_to_tray_checkbox.isChecked()
            self.config.set_app_setting("minimize_to_tray", minimize_to_tray)
            
            # 保存下载设置
            self.config.set_app_setting("default_quality", quality_combo.currentData())
            self.config.set_app_setting("auto_download_cover", auto_cover_checkbox.isChecked())
            self.config.set_app_setting("auto_download_danmaku", auto_danmaku_checkbox.isChecked())
            self.config.set_app_setting("auto_open_folder", auto_open_folder_checkbox.isChecked())
            self.config.set_app_setting("play_sound_on_complete", play_sound_checkbox.isChecked())
            self.config.set_app_setting("add_episode_to_filename", add_episode_prefix_checkbox.isChecked())
            self.config.set_app_setting("video_output_format", video_format_combo.currentData())
            self.config.set_app_setting("audio_quality", audio_quality_combo.currentData())
            self.config.set_app_setting("danmaku_output_format", danmaku_format_combo.currentData())
            
            # 保存网络设置
            self.config.set_app_setting("network_timeout", timeout_spin.currentData())
            self.config.set_app_setting("max_retry", retry_spin.currentData())
            
            # 保存其他设置
            self.config.set_app_setting("auto_check_update", auto_update_checkbox.isChecked())
            self.config.set_app_setting("show_download_speed", show_speed_checkbox.isChecked())
            self.config.set_app_setting("show_floating_ball", show_float_checkbox.isChecked())
            self.config.set_app_setting("show_merge_window", show_merge_window_checkbox.isChecked())
            self.config.set_app_setting("auto_convert_incompatible", auto_convert_checkbox.isChecked())
            self.config.set_app_setting("hevc_not_supported_ask", hevc_not_support_ask_checkbox.isChecked())
            
            dialog.accept()
        
        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addWidget(btn_widget)
        


        self.settings_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def browse_settings_path(self, line_edit):
        path = self.show_custom_file_dialog("选择默认保存路径")
        if path:
            line_edit.setText(path)
    
    def on_user_info_click(self, event=None):
        print("on_user_info_click被调用")
        try:
            print("开始获取用户信息")
            # 先获取基本用户信息
            user_info = self.parser.get_user_info()
            if not user_info.get("success"):
                print("获取用户基本信息失败")
                self.show_notification("获取用户信息失败：未登录或Cookie失效", "error")
                return
            
            # 尝试获取详细用户信息
            try:
                user_detail = self.parser.get_user_detail()
                print(f"获取用户详情结果：{user_detail}")
                if user_detail.get("success"):
                    print("用户详情获取成功，显示用户信息窗口")
                    self.show_user_info_window(user_detail)
                else:
                    # 如果获取详细信息失败，使用基本信息创建用户详情对象
                    print("用户详情获取失败，使用基本信息")
                    user_detail = {
                        "success": True,
                        "mid": user_info.get("mid", ""),
                        "name": user_info.get("uname", "未知用户"),
                        "sex": "保密",
                        "face": user_info.get("face", ""),
                        "sign": "无签名",
                        "level": user_info.get("level", 0),
                        "coins": 0,
                        "vip": {"status": 1 if user_info.get("is_vip") else 0}
                    }
                    self.show_user_info_window(user_detail)
            except Exception as e:
                # 如果发生异常，使用基本信息
                print(f"获取用户详情异常：{e}")
                user_detail = {
                    "success": True,
                    "mid": user_info.get("mid", ""),
                    "name": user_info.get("uname", "未知用户"),
                    "sex": "保密",
                    "face": user_info.get("face", ""),
                    "sign": "无签名",
                    "level": user_info.get("level", 0),
                    "coins": 0,
                    "vip": {"status": 1 if user_info.get("is_vip") else 0}
                }
                self.show_user_info_window(user_detail)
        except Exception as e:
            print(f"获取用户信息失败：{e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"获取用户信息失败：{str(e)}", "error")
    
    def show_user_info_window(self, user_detail):
        try:
            print("开始显示用户信息窗口")
            dialog = QDialog(self)
            dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
            dialog.setAutoFillBackground(True)
            dialog.setWindowTitle("个人中心")
            screen = QApplication.primaryScreen()
            if screen:
                sg = screen.availableGeometry()
                dialog.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(400), int(sg.height() * 0.3)))
            else:
                dialog.setMinimumSize(scale(500), scale(400))
        
            # 设置窗口图标
            try:
                import sys
                if hasattr(sys, '_MEIPASS'):
                    logo_path = os.path.join(sys._MEIPASS, "logo.ico")
                else:
                    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
                if os.path.exists(logo_path):
                    icon = QIcon(logo_path)
                    dialog.setWindowIcon(icon)
            except Exception as e:
                pass
            
            # 应用基础样式
            custom_style = get_base_style() + scale_style("""
                QDialog {
                    background-color: white;
                    border: 2px solid #409eff;
                    border-radius: 10px;
                }
                QLabel#windowTitle {
                    font-size: 13px;
                    font-weight: 600;
                    color: white;
                }
                QPushButton#minimizeBtn {
                    background-color: transparent;
                    color: white;
                    font-size: 14px;
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                QPushButton#minimizeBtn:hover {
                    background-color: rgba(255, 255, 255, 0.2);
                }
                QPushButton#closeBtn {
                    background-color: transparent;
                    color: white;
                    font-size: 14px;
                    padding: 4px 8px;
                    border-radius: 4px;
                }
                QPushButton#closeBtn:hover {
                    background-color: rgba(255, 0, 0, 0.3);
                }
            """)
            dialog.setStyleSheet(custom_style)
            
            main_layout = QVBoxLayout(dialog)
            main_layout.setContentsMargins(scale(2), scale(0), scale(2), scale(2))
            main_layout.setSpacing(scale(0))
            
            # 添加鼠标事件处理，实现窗口移动
            dialog.mousePressEvent = lambda event: setattr(dialog, 'mouse_pos', event.globalPos() - dialog.pos())
            dialog.mouseMoveEvent = lambda event: dialog.move(event.globalPos() - getattr(dialog, 'mouse_pos', QPoint(0, 0)))
            
            # 添加标题栏
            title_bar = QWidget()
            title_bar.setStyleSheet(scale_style("background-color: #409eff; color: white; min-height: 36px; border-top-left-radius: 10px; border-top-right-radius: 10px;"))
            title_layout = QHBoxLayout(title_bar)
            title_layout.setContentsMargins(scale(12), scale(0), scale(8), scale(0))
            title_layout.setSpacing(scale(6))
            
            # 窗口标题
            window_title = QLabel("个人中心")
            window_title.setObjectName("windowTitle")
            title_layout.addWidget(window_title, stretch=1)
            
            # 最小化按钮
            minimize_btn = QPushButton("_")
            minimize_btn.setObjectName("minimizeBtn")
            minimize_btn.clicked.connect(dialog.showMinimized)
            title_layout.addWidget(minimize_btn)
            
            # 关闭按钮
            close_btn = QPushButton("×")
            close_btn.setObjectName("closeBtn")
            close_btn.clicked.connect(dialog.close)
            title_layout.addWidget(close_btn)
            
            main_layout.addWidget(title_bar)
            
            # 内容区域
            content_widget = QWidget()
            content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))
            content_layout.setSpacing(scale(0))
            
            # 创建WebEngineView
            web_view = QWebEngineView()
            web_view.setStyleSheet("border: none;")
            web_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            content_layout.addWidget(web_view)
            
            main_layout.addWidget(content_widget, stretch=1)
            
            # 构建HTML内容
            username = user_detail.get("name", "未知用户")
            mid = user_detail.get("mid", "未知")
            level = user_detail.get("level", 0)
            vip = user_detail.get("vip", {})
            vip_status = vip.get("status", 0)
            vip_type = vip.get("type", 0)
            sign = user_detail.get("sign", "无签名")
            sex = user_detail.get("sex", "保密")
            coins = user_detail.get("coins", 0)
            is_senior_member = user_detail.get("is_senior_member", 0)
            jointime = user_detail.get("jointime", 0)
            birthday = user_detail.get("birthday", "")
            
            # 处理注册时间
            if jointime > 0:
                register_time = time.strftime("%Y-%m-%d", time.localtime(jointime))
            else:
                register_time = "未知"
            
            # 处理生日
            birthday_text = birthday if birthday else "未设置"
            
            # 处理会员类型
            if vip_status == 1:
                vip_type_text = "年度会员" if vip_type == 2 else "月度会员"
            else:
                vip_type_text = "未开通"
            
            # 处理硬核会员
            senior_text = "是" if is_senior_member == 1 else "否"
            
            # 处理会员状态
            vip_status_text = "大会员" if vip_status == 1 else "普通用户"
            
            # 头像URL
            avatar_url = user_detail.get("face", "https://i2.hdslb.com/bfs/face/member/noface.jpg")
            
            # 构建HTML
            html = '''
            <!DOCTYPE html>
            <html lang="zh-CN">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>个人中心</title>
                <style>
                    * {{ 
                        margin: 0;
                        padding: 0;
                        box-sizing: border-box;
                    }}
                    body {{ 
                        font-family: 'Microsoft YaHei', 'PingFang SC', sans-serif;
                        background-color: #f8f9fa;
                        color: #333;
                        line-height: 1.5;
                    }}
                    .container {{ 
                        padding: 20px;
                    }}
                    .profile-header {{ 
                        background-color: #00a1d6;
                        border-radius: 8px;
                        padding: 20px;
                        margin-bottom: 16px;
                        color: white;
                        display: flex;
                        align-items: center;
                        gap: 20px;
                    }}
                    .avatar {{ 
                        width: 80px;
                        height: 80px;
                        border-radius: 50%;
                        background-color: white;
                        overflow: hidden;
                        border: 2px solid rgba(255, 255, 255, 0.3);
                    }}
                    .avatar img {{
                        width: 100%;
                        height: 100%;
                        object-fit: cover;
                    }}
                    .basic-info {{
                        display: flex;
                        flex-direction: column;
                        gap: 5px;
                    }}
                    .username {{
                        font-size: 24px;
                        font-weight: 600;
                    }}
                    .uid, .level, .vip-status {{
                        font-size: 14px;
                        opacity: 0.9;
                    }}
                    .info-section {{ 
                        background-color: white;
                        border-radius: 8px;
                        padding: 20px;
                        border: 1px solid #e0e0e0;
                    }}
                    .sign {{ 
                        background-color: #f5f5f5;
                        border-left: 3px solid #00a1d6;
                        padding: 12px;
                        border-radius: 4px;
                        margin-bottom: 16px;
                        font-size: 13px;
                        color: #555;
                        line-height: 1.5;
                    }}
                    .section-title {{ 
                        font-size: 16px;
                        font-weight: 600;
                        color: #333;
                        margin-bottom: 16px;
                        padding-bottom: 8px;
                        border-bottom: 1px solid #e0e0e0;
                    }}
                    .detail-grid {{ 
                        display: grid;
                        grid-template-columns: repeat(3, 1fr);
                        gap: 16px;
                    }}
                    .info-item {{
                        display: flex;
                        flex-direction: column;
                        gap: 3px;
                    }}
                    .info-label {{
                        font-size: 12px;
                        color: #888;
                        font-weight: 500;
                    }}
                    .info-value {{ 
                        font-size: 13px;
                        color: #333;
                        font-weight: 500;
                    }}
                    @media (max-width: 768px) {{ 
                        .detail-grid {{ 
                            grid-template-columns: repeat(2, 1fr);
                        }}
                        .profile-header {{ 
                            flex-direction: column;
                            text-align: center;
                            gap: 15px;
                        }}
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="profile-header">
                        <div class="avatar">
                            <img src="{avatar_url}" alt="头像">
                        </div>
                        <div class="basic-info">
                            <div class="username">{username}</div>
                            <div class="uid">UID：{mid}</div>
                            <div class="level">Lv.{level}</div>
                            <div class="vip-status">{vip_status_text}</div>
                        </div>
                    </div>
                    
                    <div class="info-section">
                        <div class="sign">{sign}</div>
                        
                        <div class="section-title">详细信息</div>
                        <div class="detail-grid">
                            <div class="info-item">
                                <div class="info-label">性别</div>
                                <div class="info-value">{sex}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">硬币</div>
                                <div class="info-value">{coins}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">硬核会员</div>
                                <div class="info-value">{senior_text}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">注册时间</div>
                                <div class="info-value">{register_time}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">会员类型</div>
                                <div class="info-value">{vip_type_text}</div>
                            </div>
                            <div class="info-item">
                                <div class="info-label">生日</div>
                                <div class="info-value">{birthday_text}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            '''
            
            # 替换变量
            html = html.format(
                avatar_url=avatar_url,
                username=username,
                mid=mid,
                level=level,
                vip_status_text=vip_status_text,
                sign=sign,
                sex=sex,
                coins=coins,
                senior_text=senior_text,
                register_time=register_time,
                vip_type_text=vip_type_text,
                birthday_text=birthday_text
            )
            
            # 加载HTML
            web_view.setHtml(html)
            
            # 显示对话框
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        except Exception as e:
            print(f"显示用户信息窗口失败：{e}")
            import traceback
            traceback.print_exc()
            self.show_notification(f"打开个人中心失败：{str(e)}", "error")


class CookieTestDialog(QDialog):
    def __init__(self, parser, parent=None):
        super().__init__(parent)
        self.parser = parser
        self.setWindowTitle("Cookie测试")
        screen = QApplication.primaryScreen()
        if screen:
            sg = screen.availableGeometry()
            self.setMinimumSize(max(scale(500), int(sg.width() * 0.3)), max(scale(350), int(sg.height() * 0.3)))
        else:
            self.setMinimumSize(scale(500), scale(350))
        
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout()
        
        # 测试按钮
        self.test_btn = QPushButton("测试Cookie验证")
        self.test_btn.clicked.connect(self.test_cookie)
        layout.addWidget(self.test_btn)
        
        # 进度标签
        self.progress_label = QLabel("等待测试...")
        layout.addWidget(self.progress_label)
        
        # 结果文本框
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)
        
        # Cookie信息
        self.cookie_info_label = QLabel("Cookie状态: 未检查")
        layout.addWidget(self.cookie_info_label)
        
        # 关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        layout.addWidget(self.close_btn)
        
        self.setLayout(layout)
    
    def test_cookie(self):
        self.result_text.clear()
        self.progress_label.setText("开始测试...")
        self.result_text.append("="*60)
        self.result_text.append("开始Cookie测试")
        self.result_text.append("="*60)
        
        try:
            # 步骤1：检查parser
            self.result_text.append("\n【步骤1】检查parser是否存在...")
            if self.parser:
                self.result_text.append("   ✓ parser存在")
            else:
                self.result_text.append("   ✗ parser不存在！")
                self.progress_label.setText("测试失败：parser不存在")
                return
            
            # 步骤2：检查cookies
            self.result_text.append("\n【步骤2】检查cookies是否存在...")
            if hasattr(self.parser, 'cookies') and self.parser.cookies:
                self.result_text.append(f"   ✓ cookies存在，共 {len(self.parser.cookies)} 个cookie")
                self.result_text.append(f"   主要cookie: {list(self.parser.cookies.keys())[:5]}...")
            else:
                self.result_text.append("   ✗ cookies不存在！")
                self.cookie_info_label.setText("Cookie状态: 不存在")
                self.progress_label.setText("测试失败：cookie不存在")
                return
            
            # 步骤3：检查SESSDATA
            self.result_text.append("\n【步骤3】检查关键Cookie (SESSDATA)...")
            if 'SESSDATA' in self.parser.cookies:
                sessdata = self.parser.cookies['SESSDATA']
                self.result_text.append(f"   ✓ SESSDATA存在，长度: {len(sessdata)}")
                self.result_text.append(f"   SESSDATA前20字符: {sessdata[:20]}...")
            else:
                self.result_text.append("   ✗ SESSDATA不存在！")
                self.result_text.append(f"   存在的cookie: {list(self.parser.cookies.keys())}")
                self.cookie_info_label.setText("Cookie状态: 缺少SESSDATA")
                self.progress_label.setText("测试失败：缺少SESSDATA")
                return
            
            # 步骤4：调用verify_cookie
            self.result_text.append("\n【步骤4】调用verify_cookie方法...")
            self.result_text.append("   正在验证，请稍候...")
            
            success, msg = self.parser.verify_cookie()
            
            self.result_text.append(f"   verify_cookie返回: success={success}, msg={msg}")
            
            if success:
                self.result_text.append("\n【结果】✓ Cookie验证成功！")
                self.progress_label.setText("测试成功！")
                self.cookie_info_label.setText("Cookie状态: 有效")
                
                # 步骤5：获取用户信息
                self.result_text.append("\n【步骤5】获取用户信息...")
                user_info = self.parser.get_user_info()
                if user_info.get("success"):
                    self.result_text.append(f"   ✓ 用户名: {user_info.get('uname', '未知')}")
                    self.result_text.append(f"   ✓ 用户ID: {user_info.get('uid', user_info.get('mid', '未知'))}")
                    self.result_text.append(f"   ✓ 头像URL: {user_info.get('face', '无')[:50]}...")
                else:
                    self.result_text.append(f"   ✗ 获取用户信息失败: {user_info.get('msg', '未知错误')}")
            else:
                self.result_text.append(f"\n【结果】✗ Cookie验证失败!")
                self.result_text.append(f"   失败原因: {msg}")
                self.progress_label.setText(f"测试失败: {msg}")
                self.cookie_info_label.setText(f"Cookie状态: 无效 - {msg}")
        except Exception as e:
            import traceback
            self.result_text.append(f"\n【错误】发生异常: {str(e)}")
            self.result_text.append(traceback.format_exc())
            self.progress_label.setText(f"测试出错: {str(e)}")
            self.cookie_info_label.setText("Cookie状态: 错误")


if __name__ == "__main__":
    from config import ConfigLoader

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    
    config = ConfigLoader()

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", scale(10)))
    ui = BilibiliDownloader(config)
    ui.show()
    sys.exit(app.exec_())
