
import os
import sys
import webbrowser
import shutil
import time
import json
import traceback
import logging
import ctypes
import requests

from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QPushButton, QScrollArea,
                             QComboBox, QLabel, QFileDialog, QProgressBar, QMessageBox, QGroupBox,
                             QCheckBox, QTextEdit, QDialog, QListWidget, QListWidgetItem,
                             QStackedWidget, QRadioButton, QButtonGroup, QSpacerItem, QSizePolicy, QMenu,
                             QApplication, QSpinBox, QTabWidget, QSystemTrayIcon, QCompleter)
from PyQt5.QtCore import QSize, Qt, pyqtSignal, QObject, QEvent, pyqtSlot, QPoint, QThread, QTimer, QEventLoop, QUrl, QCoreApplication, QMetaObject, Q_ARG
from PyQt5.QtGui import QFont, QPalette, QColor, QCursor, QPixmap, QPainter, QBrush, QIcon, QPainterPath
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWebChannel import QWebChannel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if hasattr(sys, 'frozen') or sys.platform == 'win32':
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass

global_dpi_scale = 1.0

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

BASE_STYLE = """
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
        height: 10px; 
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
        height: 48px;
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
        width: 140px; 
        margin: 10px; 
        border: 1px solid #e9ecef; 
        border-radius: 8px; 
        height: 90px;
    }
    .card-view QListWidget::item:hover { 
        background-color: #f8fafc; 
    }
    .card-view QListWidget::item:selected { 
        border-color: #409eff; 
        background-color: #e6f7ff;
    }
"""


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
            return int(value * global_dpi_scale)
        
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("人机验证")
        dialog.setMinimumSize(scale(420), scale(380))
        dialog.setModal(True)
        
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        
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
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setStyleSheet(f"background-color: #409eff; color: white; height: {scale(40)}px; border-top-left-radius: {scale(10)}px; border-top-right-radius: {scale(10)}px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(scale(16), 0, scale(12), 0)
        title_layout.setSpacing(scale(10))
        
        title_label = QLabel("人机验证")
        title_label.setStyleSheet(f"font-size: {scale(15)}px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet(f"background-color: transparent; border: none; color: white; font-size: {scale(18)}px; padding: 0; width: {scale(28)}px; height: {scale(28)}px; border-radius: {scale(14)}px;")
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
        web_view.setStyleSheet(f"border-radius: {scale(8)}px; overflow: hidden;")
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
            if event.button() == Qt.LeftButton and event.y() < 36:  
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
        
        self.setStyleSheet("""
            QDialog {
                background-color: white;
                border: 2px solid #409eff;
                border-radius: 10px;
            }
        """)
        
        # 计算DPI缩放因子
        global global_dpi_scale
        screen = QApplication.primaryScreen()
        logical_dpi = screen.logicalDotsPerInch()
        global_dpi_scale = logical_dpi / 96.0  # 96 DPI 是标准DPI
        
        # 自适应屏幕尺寸
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        
        # 根据屏幕尺寸和DPI设置合理的大小
        min_width = max(250, int(screen_width * 0.2))
        min_height = max(200, int(screen_height * 0.2))
        max_width = min(800, int(screen_width * 0.6))
        max_height = min(1000, int(screen_height * 0.8))
        
        self.setMinimumSize(min_width, min_height)
        self.setMaximumSize(max_width, max_height)
        
        # 响应窗口大小变化
        self.resizeEvent = self.on_resize
        
        
        self.create_ui()
        
    def create_ui(self):
        
        # 计算基于DPI的尺寸
        global global_dpi_scale
        def scale(value):
            return int(value * global_dpi_scale)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(scale(8), scale(8), scale(8), scale(8))
        main_layout.setSpacing(scale(10))
        
        self.initial_card = QWidget()
        initial_layout = QVBoxLayout(self.initial_card)
        initial_layout.setContentsMargins(0, 0, 0, 0)
        initial_layout.setSpacing(scale(10))
        
        logo_layout = QVBoxLayout()
        logo_layout.setAlignment(Qt.AlignCenter)
        logo_label = QLabel()
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
        self.url_edit.setStyleSheet(f"padding: {scale(12)}px; border: 1px solid #dee2e6; border-radius: {scale(8)}px; font-size: {scale(12)}px; background-color: #f8fafc;")
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
        self.resolution_combo.setStyleSheet(f"padding: {scale(6)}px; border: 1px solid #dee2e6; border-radius: {scale(4)}px; font-size: {scale(12)}px;")
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
        self.path_edit.setStyleSheet(f"padding: {scale(6)}px; border: 1px solid #dee2e6; border-radius: {scale(4)}px; font-size: {scale(10)}px;")
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
        self.video_list.setStyleSheet(f"border: 1px solid #dee2e6; border-radius: {scale(6)}px; font-size: {scale(10)}px;")
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
        self.download_scroll.setStyleSheet(f"border: 1px solid #dee2e6; border-radius: {scale(8)}px;")
        
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
        # 确保窗口不会太小
        screen = QApplication.primaryScreen()
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
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        # 计算基于DPI的尺寸
        global global_dpi_scale
        self.base_size = int(70 * global_dpi_scale)
        self.min_size = int(50 * global_dpi_scale)
        self.max_size = int(100 * global_dpi_scale)
        
        self.setFixedSize(self.base_size, self.base_size)
        
        # 计算初始位置（屏幕右下角）
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_width = screen_geometry.width()
        screen_height = screen_geometry.height()
        initial_x = screen_width - self.width() - 20
        initial_y = screen_height - self.height() - 100
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
        
        painter = QPainter(self)
        
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        # 绘制圆形背景
        alpha = int(255 * self.opacity)
        brush = QBrush(QColor(64, 158, 255, alpha))
        painter.setBrush(brush)
        painter.drawEllipse(0, 0, self.width() - 1, self.height() - 1)  
        
        # 绘制logo或文字
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # 计算logo大小（自适应DPI）
            logo_size = int(self.width() * 0.6)
            scaled_pixmap = pixmap.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # 居中绘制
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
        else:
            # 绘制文字
            painter.setPen(QColor(255, 255, 255))
            # 自适应字体大小
            font_size = int(self.width() * 0.3)
            ball_font = QFont("Microsoft YaHei", font_size, QFont.Bold)
            painter.setFont(ball_font)
            painter.drawText(self.rect(), Qt.AlignCenter, "B")
    
    def mousePressEvent(self, event):
        print("=== mousePressEvent被触发 ===")
        if event.button() == Qt.LeftButton:
            print("左键按下")
            self.dragging = False
            self.last_pos = event.globalPos()
        elif event.button() == Qt.RightButton:
            print("右键按下")
            self.show_context_menu(event.globalPos())
        event.accept()
    
    def mouseMoveEvent(self, event):
        if self.last_pos:
            current_pos = event.globalPos()
            delta = current_pos - self.last_pos
            
            if delta.manhattanLength() > 5:
                self.dragging = True
                
                new_x = self.x() + delta.x()
                new_y = self.y() + delta.y()
                
                
                screen = QApplication.primaryScreen()
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
    
    def mouseReleaseEvent(self, event):
        print("=== mouseReleaseEvent被触发 ===")
        if event.button() == Qt.LeftButton:
            print(f"左键释放，dragging状态: {self.dragging}")
            if not self.dragging:
                print("判定为点击事件，调用toggle_expanded()")
                
                self.toggle_expanded()
            else:
                print("判定为拖动事件")
            self.dragging = False
            self.last_pos = None
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
            
            # 计算窗口大小（自适应屏幕尺寸）
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
            return int(value * global_dpi_scale)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("悬浮球设置")
        dialog.setFixedSize(scale(300), scale(200))
        
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
        print("=== on_parse_finished被调用 ===")
        print(f"video_info: {video_info}")
        if video_info.get('success'):
            print("解析成功，开始显示视频信息")
            
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
                self.parent.show_notification(f"解析失败：{video_info.get('error', '未知错误')}", "error")
    
    def select_all_videos(self):
        self.video_list.selectAll()
    
    def select_save_path(self):
        
        
        default_path = self.path_edit.text() if hasattr(self, 'path_edit') else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        
        
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
            self.path_edit.setText(folder)
    
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
            if download_video:
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
            
            save_path = self.path_edit.text() if hasattr(self, 'path_edit') else (self.parent.path_edit.text() if hasattr(self.parent, 'path_edit') else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载"))
            
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
        
        
        pass
    
    def update_episode_progress(self, task_id, ep_index, progress, status):
        
        task_key = f"{task_id}_ep{ep_index}"
        
        # 根据设置决定是否显示下载速度
        if self.parent and hasattr(self.parent, 'config'):
            show_speed = self.parent.config.get_app_setting("show_download_speed", True)
            if not show_speed:
                # 移除速度信息 (格式: "下载video流：50% (1.23 MB/s)")
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
            task_widget.setStyleSheet("background-color: #f0fdf4; border-radius: 8px; padding: 12px; margin-bottom: 8px;")
            task_layout = QVBoxLayout(task_widget)
            task_layout.setContentsMargins(8, 8, 8, 8)
            task_layout.setSpacing(8)
            
            
            video_name = status.split(' - ')[0] if ' - ' in status else status
            video_name_label = QLabel(video_name)
            video_name_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #166534;")
            video_name_label.setMinimumHeight(24)
            video_name_label.setMaximumWidth(380)
            video_name_label.setToolTip(status)
            video_name_label.setWordWrap(True)
            
            
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setMinimumHeight(14)
            progress_bar.setStyleSheet("QProgressBar { border-radius: 6px; background-color: #dcfce7; } QProgressBar::chunk { border-radius: 6px; background-color: #22c55e; }")
            
            
            progress_text = QLabel(f"{int(progress)}%")
            progress_text.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 500;")
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
        if success:
            
            if self.parent and hasattr(self.parent, 'show_notification'):
                self.parent.show_notification(f"视频下载完成：{message}", "success")
            
            # 下载完成后打开文件夹
            if self.parent and hasattr(self.parent, 'config'):
                auto_open_folder = self.parent.config.get_app_setting("auto_open_folder", False)
                if auto_open_folder:
                    try:
                        import subprocess
                        # 从消息中提取文件路径
                        if "完成：" in message:
                            file_path = message.replace("完成：", "").strip()
                            folder_path = os.path.dirname(file_path)
                            if os.path.exists(folder_path):
                                if os.name == 'nt':  # Windows
                                    subprocess.run(['explorer', folder_path], shell=True)
                                elif os.name == 'posix':  # macOS/Linux
                                    subprocess.run(['open' if os.uname().sysname == 'Darwin' else 'xdg-open', folder_path])
                    except Exception as e:
                        print(f"打开文件夹失败：{str(e)}")
            
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
        self.setFixedSize(600, 400)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.NonModal)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
        except Exception as e:
            pass
        
        # 设置样式
        custom_style = BASE_STYLE + """
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
                width: 10px;
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
                height: 10px;
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
                height: 12px;
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
        """
        self.setStyleSheet(custom_style)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("解析进度")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 解析状态标题
        status_label = QLabel("正在解析视频信息...")
        status_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        content_layout.addWidget(status_label)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        content_layout.addWidget(self.log_text, stretch=1)
        
        # 进度条
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
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
    
    def show_notification(self, message, notification_type="info"):
        if self.notification_widget:
            self.notification_widget.show_notification(message, notification_type)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            if self.drag_position:
                self.move(event.globalPos() - self.drag_position)
                event.accept()
        
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
    def __init__(self):
        super().__init__()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint | Qt.WindowMaximizeButtonHint)
        
        self.dragging = False
        self.start_pos = None
        self.resizing = False
        self.resize_direction = None
        self.edge_size = 8
    
    def mousePressEvent(self, event):
        
        # 检查是否在窗口边缘
        if event.button() == Qt.LeftButton:
            # 检查鼠标位置是否在窗口边缘
            rect = self.rect()
            if event.x() < self.edge_size and event.y() < self.edge_size:
                # 左上角
                self.resize_direction = 'top-left'
                self.resizing = True
            elif event.x() > rect.width() - self.edge_size and event.y() < self.edge_size:
                # 右上角
                self.resize_direction = 'top-right'
                self.resizing = True
            elif event.x() < self.edge_size and event.y() > rect.height() - self.edge_size:
                # 左下角
                self.resize_direction = 'bottom-left'
                self.resizing = True
            elif event.x() > rect.width() - self.edge_size and event.y() > rect.height() - self.edge_size:
                # 右下角
                self.resize_direction = 'bottom-right'
                self.resizing = True
            elif event.x() < self.edge_size:
                # 左侧
                self.resize_direction = 'left'
                self.resizing = True
            elif event.x() > rect.width() - self.edge_size:
                # 右侧
                self.resize_direction = 'right'
                self.resizing = True
            elif event.y() < self.edge_size:
                # 顶部
                self.resize_direction = 'top'
                self.resizing = True
            elif event.y() > rect.height() - self.edge_size:
                # 底部
                self.resize_direction = 'bottom'
                self.resizing = True
            elif event.y() < 32:  
                # 标题栏拖动
                self.dragging = True
                self.start_pos = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
    
    def mouseMoveEvent(self, event):
        
        # 处理窗口大小调整
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
            
            # 限制最小窗口大小
            min_width = 400
            min_height = 350
            new_width = max(new_width, min_width)
            new_height = max(new_height, min_height)
            
            # 应用新的窗口大小和位置
            self.setGeometry(new_x, new_y, new_width, new_height)
            event.accept()
        # 处理窗口拖动
        elif self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.start_pos)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        
        self.dragging = False
        self.resizing = False
        self.resize_direction = None
        event.accept()
    
    def toggle_maximize(self):
        
        if not self.isMaximized():
            self.showMaximized()

class SignalEmitter(QObject):
    parse_start = pyqtSignal(str, bool)
    parse_finished = pyqtSignal(dict)
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
    same_task_exists = pyqtSignal(dict)  # 信号：相同任务已存在
    show_space_videos = pyqtSignal(dict, list)  # 新信号：显示UP主作品列表


class NotificationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        self.container = QWidget(self)
        self.container.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #e8e8e8;")
        
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.container)
        
        self.content_layout = QHBoxLayout(self.container)
        self.content_layout.setContentsMargins(20, 15, 20, 15)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 24)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.content_layout.addWidget(self.icon_label)
        
        self.message_label = QLabel()
        self.message_label.setStyleSheet("font-size: 14px; color: #333333; font-family: 'Microsoft YaHei', sans-serif;")
        self.message_label.setWordWrap(True)
        self.content_layout.addWidget(self.message_label, stretch=1)
        
        self.close_btn = QPushButton("×")
        self.close_btn.setStyleSheet("background-color: transparent; border: none; font-size: 16px; color: #999999; padding: 0; font-family: 'Microsoft YaHei', sans-serif;")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.hide)
        self.content_layout.addWidget(self.close_btn)
        
        self.setMinimumWidth(300)
        self.setMaximumWidth(500)
        
    def show_notification(self, message, notification_type="info"):
        print(f"NotificationWidget.show_notification called with message: {message}, type: {notification_type}")
        try:
            # 立即更新消息内容和样式
            self.message_label.setText(message)
            
            if notification_type == "success":
                self.container.setStyleSheet("background-color: #f0f9ff; border-left: 4px solid #1890ff; border-radius: 8px; border: 1px solid #e6f7ff;")
                self.icon_label.setText("✓")
                self.icon_label.setStyleSheet("font-size: 16px; color: #1890ff; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;")
            elif notification_type == "error":
                self.container.setStyleSheet("background-color: #fff2f0; border-left: 4px solid #ff4d4f; border-radius: 8px; border: 1px solid #fff1f0;")
                self.icon_label.setText("×")
                self.icon_label.setStyleSheet("font-size: 16px; color: #ff4d4f; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;")
            elif notification_type == "warning":
                self.container.setStyleSheet("background-color: #fff7e6; border-left: 4px solid #faad14; border-radius: 8px; border: 1px solid #fffbe6;")
                self.icon_label.setText("!")
                self.icon_label.setStyleSheet("font-size: 16px; color: #faad14; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;")
            else:  
                self.container.setStyleSheet("background-color: #f6ffed; border-left: 4px solid #52c41a; border-radius: 8px; border: 1px solid #f6ffed;")
                self.icon_label.setText("i")
                self.icon_label.setStyleSheet("font-size: 16px; color: #52c41a; font-weight: bold; font-family: 'Microsoft YaHei', sans-serif;")
            
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
        y = 50  
        
        if x < 0:
            x = 10
        if y < 0:
            y = 10
        if x + window_geometry.width() > screen_geometry.width():
            x = screen_geometry.width() - window_geometry.width() - 10
        if y + window_geometry.height() > screen_geometry.height():
            y = screen_geometry.height() - window_geometry.height() - 10
        self.move(x, y)
        print(f"调整后通知位置：{self.pos()}")
    
    def mousePressEvent(self, event):
        self.hide()

class DebugWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("程序出现错误")
        self.setGeometry(100, 100, 800, 600)
        self.setMinimumSize(600, 400)
        
        
        self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # 设置窗口样式
        self.setStyleSheet("""
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
        """)
        
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
        self.setFixedSize(600, 400)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.Window)
        self.setWindowModality(Qt.NonModal)
        
        # 设置样式
        self.setStyleSheet(BASE_STYLE + """QDialog {
            border: 2px solid #409eff;
            border-radius: 12px;
            background-color: white;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        }
        """)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(2, 2, 2, 2)
        main_layout.setSpacing(0)
        
        # 标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("正在合并音视频...")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label)
        title_layout.addStretch(1)
        
        # 关闭按钮
        close_btn = QPushButton("×")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        # 日志显示区域
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setStyleSheet("""
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
                width: 10px;
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
                height: 10px;
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
        """)
        content_layout.addWidget(self.log_text, stretch=1)
        
        # 进度条
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(5)
        
        self.progress_label = QLabel("准备中...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                height: 12px;
                border-radius: 6px;
                background-color: #e9ecef;
            }
            QProgressBar::chunk {
                border-radius: 6px;
                background-color: #409eff;
            }
        """)
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
            print(f"添加日志: {log_message}")
            self.log_text.append(log_message)
            self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
            QApplication.processEvents()
        except Exception as e:
            print(f"更新进度时出错: {str(e)}")
    
    def add_log(self, message):
        self.add_log_signal.emit(message)
    
    def _add_log_slot(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
        QApplication.processEvents()
    
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
        self.setMinimumSize(800, 500)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
        except Exception as e:
            pass
        
        custom_style = BASE_STYLE + """
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
        """
        self.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)

        title_label = QLabel("选择弹幕")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label, stretch=1)

        close_btn = QPushButton("×")
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(lambda: (self.reject(), self.close()))
        title_layout.addWidget(close_btn)

        main_layout.addWidget(title_bar)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        filter_layout = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索弹幕内容...")
        self.search_edit.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
        self.search_edit.textChanged.connect(self.on_search_changed)
        filter_layout.addWidget(self.search_edit, stretch=1)

        self.filter_combo = QComboBox()
        self.filter_combo.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
        self.filter_combo.addItems(["全部弹幕", "滚动弹幕", "顶部弹幕", "底部弹幕", "逆向弹幕", "高级弹幕"])
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
        self.sort_combo.addItems(["按时间排序", "按颜色排序", "按字体大小排序"])
        self.sort_combo.currentIndexChanged.connect(self.on_sort_changed)
        filter_layout.addWidget(self.sort_combo)

        content_layout.addLayout(filter_layout)

        self.stats_label = QLabel(f"共 {len(self.danmakus)} 条弹幕")
        self.stats_label.setStyleSheet("font-size: 14px; color: #64748b;")
        content_layout.addWidget(self.stats_label)

        self.danmaku_list = QListWidget()
        self.danmaku_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.danmaku_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout.addWidget(self.danmaku_list, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
        select_all_btn = QPushButton("全选")
        select_all_btn.setMinimumHeight(36)
        select_all_btn.setMinimumWidth(100)
        select_all_btn.clicked.connect(self.select_all)
        
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.setMinimumHeight(36)
        deselect_all_btn.setMinimumWidth(100)
        deselect_all_btn.clicked.connect(self.deselect_all)
        
        confirm_btn = QPushButton("确认选择")
        confirm_btn.setMinimumHeight(36)
        confirm_btn.setMinimumWidth(120)
        confirm_btn.clicked.connect(self.accept)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(36)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(select_all_btn)
        btn_layout.addWidget(deselect_all_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(confirm_btn)
        btn_layout.addWidget(cancel_btn)
        
        content_layout.addLayout(btn_layout)
        
        # 分页控件
        pagination_layout = QHBoxLayout()
        pagination_layout.setSpacing(12)
        
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.setMinimumHeight(32)
        self.prev_page_btn.setMinimumWidth(80)
        self.prev_page_btn.clicked.connect(self.prev_page)
        
        self.page_info_label = QLabel("第 1 页，共 1 页")
        self.page_info_label.setStyleSheet("font-size: 14px; color: #64748b;")
        self.page_info_label.setAlignment(Qt.AlignCenter)
        
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.setMinimumHeight(32)
        self.next_page_btn.setMinimumWidth(80)
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
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
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
        content_label.setStyleSheet("font-size: 14px; color: #333333;")
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
        info_label.setStyleSheet("font-size: 12px; color: #64748b;")

        color_widget = QWidget()
        color_widget.setFixedSize(20, 20)
        color_widget.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black; border-radius: 2px;")

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
        min_height = max(size_hint.height(), 80)
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
        self.setMinimumSize(800, 500)
        
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.setWindowIcon(icon)
        except Exception as e:
            pass
        
        
        custom_style = BASE_STYLE + """
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
                width: 200px;
                height: 170px;
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
        """
        self.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("选择集数" + ("（番剧）" if self.is_bangumi else "（合集）"))
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setToolTip("关闭")
        # 确保关闭按钮能够正确关闭对话框
        close_btn.clicked.connect(lambda: (self.reject(), self.close()))
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索集数标题...")
        self.search_edit.setStyleSheet("padding: 10px 12px; border: 1px solid #dee2e6; border-radius: 8px;")
        self.search_edit.textChanged.connect(self.filter_episodes)
        search_layout.addWidget(self.search_edit, stretch=1)
        
        # 排序下拉菜单
        self.sort_combo = QComboBox()
        self.sort_combo.setStyleSheet("padding: 10px 12px; border: 1px solid #dee2e6; border-radius: 8px;")
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
        self.card_view.setSpacing(15)
        self.card_view.setSelectionMode(QListWidget.SingleSelection)
        self.card_view.setSelectionBehavior(QListWidget.SelectItems)
        self.card_view.setStyleSheet(".card-view {}")
        self.populate_card_view()
        self.stacked_view.addWidget(self.card_view)

        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setStyleSheet("background-color: #52c41a; color: white; padding: 10px 20px; border-radius: 8px;")
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.setStyleSheet("background-color: #919191; color: white; padding: 10px 20px; border-radius: 8px;")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.confirm_btn = QPushButton("确认选择")
        self.confirm_btn.setStyleSheet("background-color: #409eff; color: white; padding: 10px 24px; border-radius: 8px; font-weight: 500;")
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        
        checkbox = QCheckBox()
        checkbox.setChecked(index in self.selected_indices)
        checkbox.stateChanged.connect(lambda state, idx=index: self.on_checkbox_changed(state, idx))
        if permission_denied:
            checkbox.setDisabled(True)
            widget.setStyleSheet("opacity: 0.6;")
        layout.addWidget(checkbox, alignment=Qt.AlignCenter)
        
        
        cover_label = QLabel()
        cover_label.setMinimumSize(80, 60)
        cover_label.setMaximumSize(100, 75)
        cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 6px; background-color: #f1f5f9;")
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
                            scaled_pixmap = pixmap.scaled(100, 75, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            cover_label.setPixmap(scaled_pixmap)
                            cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 6px;")
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
        info_layout.setSpacing(4)
        
        
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
            title_label.setStyleSheet("font-weight: 500; font-size: 13px; color: #94a3b8;")
        else:
            title_label.setStyleSheet("font-weight: 500; font-size: 13px;")
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
            duration_label.setStyleSheet("font-size: 11px; color: #64748b;")
            info_layout.addWidget(duration_label)
        
        
        cid = ep.get('cid', '')
        if cid:
            cid_label = QLabel(f"CID: {cid}")
            cid_label.setStyleSheet("font-size: 10px; color: #94a3b8;")
            info_layout.addWidget(cid_label)
        
        layout.addLayout(info_layout, stretch=1)
        
        widget.mousePressEvent = lambda event, cb=checkbox: self._on_widget_clicked(event, cb, ep)
        
        return widget

    def create_episode_card(self, ep, index):
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        
        cover_container = QWidget()
        cover_container.setStyleSheet("""
            QWidget {
                border-radius: 8px 8px 0 0;
                background-color: #f1f5f9;
            }
        """)
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(0)
        
        
        checkbox = QCheckBox()
        checkbox.setChecked(index in self.selected_indices)
        checkbox.stateChanged.connect(lambda state, idx=index: self.on_checkbox_changed(state, idx))
        checkbox.setStyleSheet("""
            QCheckBox {
                position: absolute;
                top: 8px;
                left: 8px;
                z-index: 10;
            }
        """)
        cover_layout.addWidget(checkbox, alignment=Qt.AlignTop | Qt.AlignLeft)
        
        
        cover_label = QLabel()
        cover_label.setMinimumSize(190, 107)
        cover_label.setMaximumSize(190, 107)
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
            duration_label.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 0, 0, 0.7);
                    color: white;
                    padding: 2px 6px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 500;
                }
            """)
            duration_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
            duration_label.setMinimumHeight(20)
            
            
            duration_layout = QGridLayout()
            duration_layout.setContentsMargins(0, 0, 8, 8)
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
                            scaled_pixmap = pixmap.scaled(190, 107, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
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
        title_layout.setContentsMargins(10, 8, 10, 10)
        title_layout.setSpacing(4)
        
        
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
        episode_label.setStyleSheet("""
            QLabel {
                color: #737373;
                font-size: 11px;
                font-weight: 500;
            }
        """)
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
        title_label.setStyleSheet("""
            QLabel {
                color: #18191C;
                font-size: 13px;
                font-weight: 500;
                line-height: 1.4;
            }
        """)
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(45)
        title_label.setMinimumHeight(40)
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
            
            item.setSizeHint(QSize(0, 100))
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
                                        label.setStyleSheet("font-size: 11px; color: #10b981;")
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
                    
                    item.setSizeHint(QSize(0, 100))
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
            item.setSizeHint(QSize(200, 170))
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
                                        label.setStyleSheet("font-size: 11px; color: #10b981;")
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
                    item.setSizeHint(QSize(200, 170))
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
                        
                        scaled_pixmap = pixmap.scaled(100, 75, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        cover_label.setPixmap(scaled_pixmap)
                        cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 6px;")
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
        
        for loader in self.cover_loaders:
            if loader.isRunning():
                loader.terminate()
                loader.wait(100)  
        self.cover_loaders.clear()
        super().closeEvent(event)


class TaskManagerWindow(BaseWindow):
    def __init__(self, task_manager, parser, download_manager, config):
        super().__init__()
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.Tool)
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
        self.setGeometry(100, 100, 1100, 700)
        self.setMinimumSize(800, 600)
        
        custom_style = BASE_STYLE + """
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                height: 28px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                width: 28px;
                height: 28px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """
        self.setStyleSheet(custom_style)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(8)
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
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        title_label = QLabel("下载任务管理")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2563eb;")
        title_label.setMinimumHeight(36)
        content_layout.addWidget(title_label)

        self.task_list = QListWidget()
        self.task_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.task_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.task_list, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setMinimumHeight(36)
        self.refresh_btn.setMinimumWidth(100)
        self.refresh_btn.clicked.connect(self.refresh_task_list)
        self.clear_completed_btn = QPushButton("清除已完成")
        self.clear_completed_btn.setMinimumHeight(36)
        self.clear_completed_btn.setMinimumWidth(100)
        self.clear_completed_btn.clicked.connect(self.clear_completed_tasks)
        self.batch_delete_btn = QPushButton("批量删除")
        self.batch_delete_btn.setMinimumHeight(36)
        self.batch_delete_btn.setMinimumWidth(100)
        self.batch_delete_btn.clicked.connect(self.toggle_checkboxes)
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setMinimumHeight(36)
        self.select_all_btn.setMinimumWidth(80)
        self.select_all_btn.clicked.connect(self.select_all_tasks)
        self.select_all_btn.hide()
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.setMinimumHeight(36)
        self.deselect_all_btn.setMinimumWidth(100)
        self.deselect_all_btn.clicked.connect(self.deselect_all_tasks)
        self.deselect_all_btn.hide()
        self.confirm_delete_btn = QPushButton("确认删除")
        self.confirm_delete_btn.setMinimumHeight(36)
        self.confirm_delete_btn.setMinimumWidth(100)
        self.confirm_delete_btn.clicked.connect(self.batch_delete_tasks)
        self.confirm_delete_btn.hide()
        self.close_btn = QPushButton("关闭")
        self.close_btn.setMinimumHeight(36)
        self.close_btn.setMinimumWidth(80)
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
        
        for task in tasks:
            task_id = task.get("id")
            title = task.get("title", "未知视频")
            status = task.get("status", "未知")
            progress = task.get("progress", 0)
            save_path = task.get("save_path", "")
            url = task.get("url", "")
            error_message = task.get("error_message", "")

            item_widget = QWidget()
            item_layout = QVBoxLayout(item_widget)
            item_layout.setContentsMargins(12, 12, 12, 12)
            item_layout.setSpacing(6)
            item_widget.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")

            title_layout = QHBoxLayout()
            title_layout.setSpacing(10)
            
            if self.show_checkboxes:
                checkbox = QCheckBox()
                checkbox.setMinimumSize(20, 20)
                title_layout.addWidget(checkbox)
                self.checkbox_map[task_id] = checkbox
            
            title_label = QLabel(f"{title}")
            title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
            title_label.setWordWrap(True)
            title_label.setMinimumHeight(24)
            
            # 获取任务类型信息
            download_video = task.get("download_video", True)
            download_danmaku = task.get("download_danmaku", False)
            
            # 确定任务类型
            task_type = ""
            if download_video and download_danmaku:
                task_type = "视频+弹幕"
            elif download_video:
                task_type = "视频"
            elif download_danmaku:
                task_type = "弹幕"
            
            status_map = {
                "completed": "已完成",
                "failed": "失败",
                "downloading": "下载中",
                "pending": "待处理",
                "paused": "已暂停",
                "unknown": "未知"
            }
            status_text = status_map.get(status, "未知")
            status_label = QLabel(f"状态：{status_text}")
            status_label.setMinimumHeight(24)
            if status == "completed":
                status_label.setStyleSheet("color: #52c41a; font-weight: 500; font-size: 12px;")
            elif status == "failed":
                status_label.setStyleSheet("color: #f56c6c; font-weight: 500; font-size: 12px;")
            elif status == "downloading":
                status_label.setStyleSheet("color: #1890ff; font-weight: 500; font-size: 12px;")
            elif status == "pending":
                status_label.setStyleSheet("color: #fa8c16; font-weight: 500; font-size: 12px;")
            elif status == "paused":
                status_label.setStyleSheet("color: #722ed1; font-weight: 500; font-size: 12px;")
            
            # 添加任务类型标签
            if task_type:
                type_label = QLabel(f"类型：{task_type}")
                type_label.setMinimumHeight(24)
                # 根据任务类型设置不同颜色
                if task_type == "视频+弹幕":
                    type_label.setStyleSheet("color: #9333ea; font-weight: 500; font-size: 12px;")
                elif task_type == "视频":
                    type_label.setStyleSheet("color: #10b981; font-weight: 500; font-size: 12px;")
                elif task_type == "弹幕":
                    type_label.setStyleSheet("color: #f59e0b; font-weight: 500; font-size: 12px;")
                title_layout.addWidget(type_label)
            
            title_layout.addWidget(title_label, stretch=1)
            title_layout.addWidget(status_label)
            
            duration = task.get("duration", "")
            if duration:
                duration_label = QLabel(f"耗时：{duration}")
                duration_label.setStyleSheet("font-size: 11px; color: #64748b;")
                duration_label.setMinimumHeight(24)
                title_layout.addWidget(duration_label)
            item_layout.addLayout(title_layout)

            progress_layout = QHBoxLayout()
            progress_layout.setSpacing(10)
            progress_label = QLabel(f"进度：{progress}%")
            progress_label.setStyleSheet("font-size: 12px;")
            progress_label.setMinimumHeight(20)
            progress_label.setFixedWidth(80)
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(progress)
            progress_bar.setFixedHeight(8)
            progress_bar.setStyleSheet("QProgressBar { border-radius: 4px; background-color: #e2e8f0; } QProgressBar::chunk { border-radius: 4px; background-color: #409eff; }")
            progress_layout.addWidget(progress_label)
            progress_layout.addWidget(progress_bar, stretch=1)
            item_layout.addLayout(progress_layout)

            info_layout = QHBoxLayout()
            info_layout.setSpacing(10)
            path_label = QLabel(f"保存路径：{save_path[:50]}..." if len(save_path) > 50 else f"保存路径：{save_path}")
            path_label.setToolTip(save_path)
            path_label.setWordWrap(True)
            path_label.setMinimumHeight(20)
            path_label.setStyleSheet("font-size: 12px;")
            
            if save_path:
                open_dir_btn = QPushButton("打开目录")
                open_dir_btn.setStyleSheet("background-color: #94a3b8; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 20px;")
                open_dir_btn.clicked.connect(lambda checked, p=save_path: self.open_directory(p))
                info_layout.addWidget(open_dir_btn)
            
            info_layout.addWidget(path_label, stretch=1)
            item_layout.addLayout(info_layout)

            url_layout = QHBoxLayout()
            url_layout.setSpacing(8)
            url_text = url[:80] + "..." if len(url) > 80 else url
            url_label = QLabel(f"原始链接：")
            url_label.setStyleSheet("font-size: 12px;")
            url_link = QLabel(f"<a href='{url}'>{url_text}</a>")
            url_link.setOpenExternalLinks(True)
            url_link.setToolTip(f"点击打开链接\n右键复制链接")
            url_link.setStyleSheet("font-size: 12px;")
            
            copy_btn = QPushButton("复制链接")
            copy_btn.setStyleSheet("background-color: #64748b; color: white; padding: 3px 6px; border-radius: 3px; font-size: 11px; min-height: 20px;")
            copy_btn.clicked.connect(lambda checked, u=url: self.copy_to_clipboard(u))
            
            url_layout.addWidget(url_label)
            url_layout.addWidget(url_link, stretch=1)
            url_layout.addWidget(copy_btn)
            item_layout.addLayout(url_layout)

            if error_message:
                error_layout = QHBoxLayout()
                error_label = QLabel(f"错误：{error_message[:100]}..." if len(error_message) > 100 else f"错误：{error_message}")
                error_label.setStyleSheet("color: #f56c6c; font-size: 12px;")
                error_label.setToolTip(error_message)
                error_label.setWordWrap(True)
                error_layout.addWidget(error_label, stretch=1)
                item_layout.addLayout(error_layout)

            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(8)
            
            # 添加下载按钮，所有任务都可以查看下载窗口
            download_btn = QPushButton("查看下载")
            download_btn.setStyleSheet("background-color: #1890ff; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px;")
            download_btn.clicked.connect(lambda checked, t=task: self.open_download_window(t))
            btn_layout.addWidget(download_btn)
            
            if status == "downloading":
                pause_btn = QPushButton("暂停")
                pause_btn.setStyleSheet("background-color: #faad14; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px;")
                pause_btn.clicked.connect(lambda checked, t=task: self.pause_task(t))
                btn_layout.addWidget(pause_btn)
                stop_btn = QPushButton("停止")
                stop_btn.setStyleSheet("background-color: #f56c6c; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px;")
                stop_btn.clicked.connect(lambda checked, t=task: self.stop_task(t))
                btn_layout.addWidget(stop_btn)
            elif status in ["failed", "pending", "paused"]:
                resume_btn = QPushButton("继续")
                resume_btn.setStyleSheet("background-color: #52c41a; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px;")
                resume_btn.clicked.connect(lambda checked, t=task: self.resume_task(t))
                btn_layout.addWidget(resume_btn)
            delete_btn = QPushButton("删除")
            delete_btn.setStyleSheet("background-color: #f56c6c; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px;")
            delete_btn.clicked.connect(lambda checked, tid=task_id: self.delete_task(tid))
            btn_layout.addWidget(delete_btn)
            btn_layout.addStretch(1)
            item_layout.addLayout(btn_layout)

            list_item = QListWidgetItem()
            item_widget.adjustSize()
            min_height = max(180, item_widget.sizeHint().height() + 20)
            list_item.setSizeHint(QSize(0, min_height))
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
                "audio_format": task.get("audio_format", self.config.get_app_setting("audio_output_format", "mp3"))
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
            self.parent().show_notification("请先选择要删除的任务", "warning")
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
        dialog.setWindowTitle(f"任务详情 - {task.get('title', '未知任务')}")
        dialog.setMinimumSize(750, 550)
        
        # 添加自定义标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 32px; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(8)
        
        title_label = QLabel(f"任务详情 - {task.get('title', '未知任务')}")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: white;")
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 14px; width: 28px; height: 28px;")
        close_btn.clicked.connect(dialog.reject)
        
        title_layout.addWidget(title_label, stretch=1)
        title_layout.addWidget(close_btn)
        
        # 添加拖拽功能
        dialog.dragging = False
        dialog.start_pos = None
        
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton and event.y() < 32:
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
        
        # 使用与主窗口一致的样式
        custom_style = BASE_STYLE + """
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
                height: 48px;
            }
            QListWidget::item:hover {
                background-color: #f8fafc;
            }
            QListWidget::item:selected {
                background-color: #e6f7ff;
                color: #2f5496;
            }
        """
        dialog.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 添加标题栏
        main_layout.addWidget(title_bar)
        
        # 内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        info_group = QGroupBox("基本信息")
        info_group.setMinimumHeight(200)
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(12)
        
        title_layout = QHBoxLayout()
        title_layout.setSpacing(10)
        title_label = QLabel("任务标题：")
        title_label.setMinimumWidth(100)
        title_label.setMinimumHeight(36)
        title_content = QLabel(task.get('title', '未知'))
        title_content.setWordWrap(True)
        title_content.setMinimumHeight(36)
        title_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title_layout.addWidget(title_label)
        title_layout.addWidget(title_content, stretch=1)
        info_layout.addLayout(title_layout)
        
        url_layout = QHBoxLayout()
        url_layout.setSpacing(10)
        url_label = QLabel("下载链接：")
        url_label.setMinimumWidth(100)
        url_label.setMinimumHeight(36)
        url_text = task.get('url', '')
        url_link = QLabel(f"<a href='{url_text}'>{url_text[:150]}...</a>")
        url_link.setOpenExternalLinks(True)
        url_link.setWordWrap(True)
        url_link.setMinimumHeight(36)
        url_link.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        copy_url_btn = QPushButton("复制")
        copy_url_btn.setMinimumHeight(32)
        copy_url_btn.setMinimumWidth(80)
        copy_url_btn.setStyleSheet("padding: 6px 12px; font-size: 12px;")
        copy_url_btn.clicked.connect(lambda: self.copy_to_clipboard(url_text))
        url_layout.addWidget(url_label)
        url_layout.addWidget(url_link, stretch=1)
        url_layout.addWidget(copy_url_btn)
        info_layout.addLayout(url_layout)
        
        path_layout = QHBoxLayout()
        path_layout.setSpacing(10)
        path_label = QLabel("保存路径：")
        path_label.setMinimumWidth(100)
        path_label.setMinimumHeight(36)
        path_text = task.get('save_path', '')
        path_content = QLabel(path_text[:150] + "...")
        path_content.setToolTip(path_text)
        path_content.setWordWrap(True)
        path_content.setMinimumHeight(36)
        path_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        open_path_btn = QPushButton("打开")
        open_path_btn.setMinimumHeight(32)
        open_path_btn.setMinimumWidth(80)
        open_path_btn.setStyleSheet("padding: 6px 12px; font-size: 12px;")
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
                qn_layout.setSpacing(10)
                qn_label = QLabel("分辨率：")
                qn_label.setMinimumWidth(100)
                qn_label.setMinimumHeight(36)
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
                qn_content.setMinimumHeight(36)
                qn_layout.addWidget(qn_label)
                qn_layout.addWidget(qn_content)
                info_layout.addLayout(qn_layout)
        
        # 对弹幕任务显示弹幕格式信息
        download_danmaku = task.get("download_danmaku", False)
        if download_danmaku:
            danmaku_format = task.get("danmaku_format", "XML")
            danmaku_layout = QHBoxLayout()
            danmaku_layout.setSpacing(10)
            danmaku_label = QLabel("弹幕格式：")
            danmaku_label.setMinimumWidth(100)
            danmaku_label.setMinimumHeight(36)
            danmaku_content = QLabel(danmaku_format)
            danmaku_content.setMinimumHeight(36)
            danmaku_layout.addWidget(danmaku_label)
            danmaku_layout.addWidget(danmaku_content)
            info_layout.addLayout(danmaku_layout)
        
        status_layout = QHBoxLayout()
        status_layout.setSpacing(10)
        status_label = QLabel("任务状态：")
        status_label.setMinimumWidth(100)
        status_label.setMinimumHeight(36)
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
        status_content.setMinimumHeight(36)
        status_layout.addWidget(status_label)
        status_layout.addWidget(status_content)
        info_layout.addLayout(status_layout)
        
        duration = task.get('duration', '')
        if duration:
            duration_layout = QHBoxLayout()
            duration_layout.setSpacing(10)
            duration_label = QLabel("下载耗时：")
            duration_label.setMinimumWidth(100)
            duration_label.setMinimumHeight(36)
            duration_content = QLabel(duration)
            duration_content.setMinimumHeight(36)
            duration_layout.addWidget(duration_label)
            duration_layout.addWidget(duration_content)
            info_layout.addLayout(duration_layout)
        
        error_msg = task.get('error_message', '')
        if error_msg:
            error_layout = QHBoxLayout()
            error_layout.setSpacing(10)
            error_label = QLabel("错误信息：")
            error_label.setMinimumWidth(100)
            error_label.setMinimumHeight(36)
            error_content = QLabel(error_msg[:200] + "...")
            error_content.setToolTip(error_msg)
            error_content.setStyleSheet("color: #f56c6c;")
            error_content.setWordWrap(True)
            error_content.setMinimumHeight(36)
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
        files_group.setMinimumHeight(250)
        files_layout = QVBoxLayout(files_group)
        files_layout.setSpacing(12)
        
        episodes = task.get('episodes', [])
        video_info = task.get('video_info', {})
        is_bangumi = video_info.get('is_bangumi', task.get('is_bangumi', False))
        
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        search_label = QLabel("搜索：")
        search_label.setMinimumWidth(80)
        search_label.setMinimumHeight(36)
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入关键词筛选文件")
        search_edit.setMinimumHeight(36)
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
                    list_item.setSizeHint(QSize(0, 100))  # 增加行高来显示多行内容
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
        btn_layout.setSpacing(12)
        if task.get('status') in ['failed', 'pending', 'paused']:
            resume_btn = QPushButton("继续下载")
            resume_btn.setMinimumHeight(36)
            resume_btn.setMinimumWidth(100)
            resume_btn.setStyleSheet("background-color: #52c41a; color: white;")
            resume_btn.clicked.connect(lambda: (self.resume_task(task), dialog.accept()))
            btn_layout.addWidget(resume_btn)
        
        delete_btn = QPushButton("删除任务")
        delete_btn.setMinimumHeight(36)
        delete_btn.setMinimumWidth(100)
        delete_btn.setStyleSheet("background-color: #f56c6c; color: white;")
        delete_btn.clicked.connect(lambda: (self.delete_task(task.get('id')), dialog.accept()))
        btn_layout.addWidget(delete_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.setMinimumHeight(36)
        close_btn.setMinimumWidth(80)
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
            dialog.setWindowTitle("弹幕内容")
            dialog.setMinimumSize(800, 600)
            
            # 添加自定义标题栏
            title_bar = QWidget()
            title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
            title_layout = QHBoxLayout(title_bar)
            title_layout.setContentsMargins(16, 0, 12, 0)
            title_layout.setSpacing(10)
            
            title_label = QLabel("弹幕内容")
            title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
            title_layout.addWidget(title_label, stretch=1)
            
            close_btn = QPushButton("×")
            close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
            close_btn.setToolTip("关闭")
            close_btn.clicked.connect(dialog.reject)
            title_layout.addWidget(close_btn)
            
            # 添加拖拽功能
            dialog.dragging = False
            dialog.start_pos = None
            
            def mousePressEvent(event):
                if event.button() == Qt.LeftButton and event.y() < 40:
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
            
            # 设置样式
            custom_style = BASE_STYLE + """
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
                    height: 48px;
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
            """
            dialog.setStyleSheet(custom_style)
            
            # 创建布局
            main_layout = QVBoxLayout(dialog)
            main_layout.setContentsMargins(0, 0, 0, 0)
            main_layout.setSpacing(0)
            
            # 添加标题栏
            main_layout.addWidget(title_bar)
            
            # 内容区域
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            content_layout.setContentsMargins(20, 20, 20, 20)
            content_layout.setSpacing(15)
            
            # 添加文件路径信息
            path_label = QLabel(f"文件路径：{file_path}")
            path_label.setWordWrap(True)
            path_label.setStyleSheet("font-size: 12px; color: #64748b;")
            content_layout.addWidget(path_label)
            
            # 添加弹幕数量信息
            count_label = QLabel(f"共 {len(danmaku_items)} 条弹幕")
            count_label.setStyleSheet("font-size: 12px; color: #64748b;")
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
                # 处理事件，避免界面卡顿
                QApplication.processEvents()
            
            content_layout.addWidget(danmaku_list, stretch=1)
            
            # 添加按钮布局
            btn_layout = QHBoxLayout()
            delete_btn = QPushButton("删除选中")
            delete_btn.setObjectName("deleteBtn")
            delete_btn.setMinimumHeight(36)
            delete_btn.setMinimumWidth(100)
            
            save_btn = QPushButton("保存更改")
            save_btn.setObjectName("saveBtn")
            save_btn.setMinimumHeight(36)
            save_btn.setMinimumWidth(100)
            
            close_btn = QPushButton("关闭")
            close_btn.setMinimumHeight(36)
            close_btn.setMinimumWidth(80)
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
            "audio_format": task.get("audio_format", self.config.get_app_setting("audio_output_format", "mp3"))
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
        if hasattr(self, 'timer'):
            self.timer.stop()
        event.accept()


class BatchDownloadWindow(BaseWindow):
    cancel_all = pyqtSignal()
    window_closed = pyqtSignal()
    
    def __init__(self, video_info, total_episodes, download_manager=None, parser=None):
        super().__init__()
    
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
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
        self.setGeometry(200, 200, 800, 500)
        self.setMinimumSize(600, 400)
        
        custom_style = BASE_STYLE + """
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                height: 28px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                width: 28px;
                height: 28px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """
        self.setStyleSheet(custom_style)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(8)
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
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(12)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(scroll_content)
        content_layout.addWidget(self.scroll_area, stretch=1)

        self.global_progress = QProgressBar()
        self.global_progress.setRange(0, 100)
        self.global_progress.setMinimumHeight(10)
        content_layout.addWidget(self.global_progress)

        self.cancel_btn = QPushButton("取消全部下载")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setMinimumHeight(32)
        self.cancel_btn.setMinimumWidth(110)
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
        group.setMinimumHeight(60)
        group_layout = QHBoxLayout(group)
        group_layout.setContentsMargins(12, 12, 12, 12)
        group_layout.setSpacing(10)

        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setMinimumHeight(8)
        status = QLabel("等待下载...")
        status.setStyleSheet("color: #6b7280; font-size: 11px;")
        status.setMinimumHeight(20)
        status.setWordWrap(True)
        
        pause_btn = QPushButton("暂停")
        pause_btn.setStyleSheet("background-color: #faad14; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;")
        pause_btn.clicked.connect(lambda checked, tid=task_id, eidx=ep_index: self.on_pause_resume(tid, eidx))
        
        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("background-color: #f56c6c; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;")
        delete_btn.clicked.connect(lambda checked, tid=task_id, eidx=ep_index: self.on_delete_task(tid, eidx))
        
        link_btn = QPushButton("查看链接")
        link_btn.setStyleSheet("background-color: #1890ff; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 60px;")
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
        if len(args) == 4:
            task_id, ep_index, progress, status = args
            
            # 根据设置决定是否显示下载速度
            if hasattr(self, 'parent') and self.parent and hasattr(self.parent, 'config'):
                show_speed = self.parent.config.get_app_setting("show_download_speed", True)
                if not show_speed:
                    # 移除速度信息
                    import re
                    status = re.sub(r'\s*\([^)]*B/s\)', '', status)
            
            key = f"{task_id}_{ep_index}"
            if key in self.episode_map:
                bar_index = self.episode_map[key]
                if 0 <= bar_index < len(self.progress_bars):
                    try:
                        progress = max(0, min(100, float(progress)))
                        
                        current_time = time.time()
                        last_time = self.last_update_times.get(key, 0)
                        # 进一步放宽时间限制，确保进度条能够及时更新
                        if current_time - last_time < 0.02:  
                            return
                        self.last_update_times[key] = current_time
                        
                        # 更新状态标签和进度条
                        self.status_labels[bar_index].setText(status)
                        self.progress_bars[bar_index].setValue(int(progress))
                        
                        # 强制刷新UI
                        self.status_labels[bar_index].repaint()
                        self.status_labels[bar_index].update()
                        self.progress_bars[bar_index].repaint()
                        self.progress_bars[bar_index].update()
                        
                        # 处理布局更新
                        if hasattr(self, 'layout'):
                            self.layout().update()
                        self.update()
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
                            # 进一步放宽时间限制，确保进度条能够及时更新
                            if current_time - self.last_update_time < 0.02:  
                                return
                        self.last_update_time = time.time()
                        
                        # 更新状态标签和进度条
                        self.status_labels[index].setText(status)
                        # 确保进度条能够准确显示所有进度值
                        self.progress_bars[index].setValue(int(progress))
                        
                        # 强制刷新UI
                        self.status_labels[index].repaint()
                        self.status_labels[index].update()
                        self.progress_bars[index].repaint()
                        self.progress_bars[index].update()
                        
                        # 处理布局更新
                        if hasattr(self, 'layout'):
                            self.layout().update()
                        self.update()
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
                btn.setStyleSheet("background-color: #52c41a; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;")
                try:
                    if self.download_manager:
                        self.download_manager.pause_task(task_id)
                except Exception as e:
                    logger.error(f"暂停任务失败：{str(e)}")
            else:
                btn.setText("暂停")
                btn.setStyleSheet("background-color: #faad14; color: white; padding: 4px 8px; border-radius: 3px; font-size: 11px; min-height: 24px; min-width: 50px;")
                try:
                    if self.download_manager:
                        self.download_manager.resume_task(task_id)
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
            finished = pyqtSignal(str, str)
            
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
                
                self.finished.emit(video_url, audio_url)
        
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        dialog.setWindowTitle("下载链接")
        dialog.setMinimumSize(700, 500)
        
        
        custom_style = BASE_STYLE + """
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
        """
        dialog.setStyleSheet(custom_style)
        
        
        title_bar = QWidget(dialog)
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 36px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("下载链接")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: white;")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 16px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(dialog.close)
        title_layout.addWidget(close_btn)
        
        
        dialog.dragging = False
        dialog.start_pos = None
        
        def mousePressEvent(event):
            if event.button() == Qt.LeftButton and event.y() < 36:  
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
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)
        
        title_label = QLabel(f"任务 {task_id} - 第{ep_index+1}集 下载链接")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2563eb;")
        content_layout.addWidget(title_label)
        
        
        
        link_list = QListWidget()
        link_list.setMinimumHeight(200)
        content_layout.addWidget(link_list)
        
        
        video_item = QListWidgetItem("视频链接：获取中...")
        audio_item = QListWidgetItem("音频链接：获取中...")
        link_list.addItem(video_item)
        link_list.addItem(audio_item)
        
        hint_label = QLabel("提示：链接可能会在一段时间后失效，建议及时使用。")
        hint_label.setStyleSheet("font-size: 12px; color: #6b7280;")
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
        
        fetcher.finished.connect(update_links)
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
        if len(args) == 4:
            task_id, ep_index, success, message = args
            key = f"{task_id}_{ep_index}"
            if key in self.episode_map:
                bar_index = self.episode_map[key]
                if 0 <= bar_index < len(self.status_labels):
                    self.completed += 1
                    global_progress = min(100, int((self.completed / self.total_episodes) * 100))
                    self.global_progress.setValue(global_progress)

                    if success:
                        self.status_labels[bar_index].setText(f"√ 下载完成 - {message}")
                        self.status_labels[bar_index].setStyleSheet("color: #52c41a; font-size: 12px;")
                    else:
                        self.status_labels[bar_index].setText(f"× 失败：{message[:20]}...")
                        self.status_labels[bar_index].setStyleSheet("color: #f56c6c; font-size: 12px;")
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
            if 0 <= index < len(self.status_labels):
                self.completed += 1
                global_progress = min(100, int((self.completed / self.total_episodes) * 100))
                self.global_progress.setValue(global_progress)

                if success:
                    self.status_labels[index].setText(f"√ 下载完成 - {message}")
                    self.status_labels[index].setStyleSheet("color: #52c41a; font-size: 12px;")
                else:
                    self.status_labels[index].setText(f"× 失败：{message[:20]}...")
                    self.status_labels[index].setStyleSheet("color: #f56c6c; font-size: 12px;")
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
        
        self.window_closed.emit()
        
        
        self._close_with_animation()
        
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
        self.signal_emitter.show_debug_window.connect(self.show_debug_window)
        
        # 在初始化 UI 之前先检查代理和网络连接
        self._check_network_before_start()
        
        try:
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
        
        
        QTimer.singleShot(0, lambda: self.user_info_label.setText("未登录"))
        QTimer.singleShot(0, lambda: self.vip_label.setText("× 未登录"))
        QTimer.singleShot(0, lambda: self.vip_label.setStyleSheet("color: #6b7280;"))
        QTimer.singleShot(0, self.update_login_info_display)
        QTimer.singleShot(500, self.load_local_cookie)
        QTimer.singleShot(600, self.check_cookie_validity)
        
        # 连接下载管理器的合并信号
        if self.download_manager:
            if hasattr(self.download_manager, 'merge_started'):
                self.download_manager.merge_started.connect(self.on_merge_started)
            if hasattr(self.download_manager, 'merge_finished'):
                self.download_manager.merge_finished.connect(self.on_merge_finished)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.y() < 32:
            self.dragging = True
            self.start_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if hasattr(self, 'dragging') and self.dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.start_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.dragging = False
        event.accept()
    
    def keyPressEvent(self, event):
        key = event.text()
        if key and len(key) == 1:  # 确保只处理单个字符
            self.admin_input += key
            # 只保留最后15个字符，避免内存占用
            if len(self.admin_input) > 15:
                self.admin_input = self.admin_input[-15:]
            print(f"当前输入：{self.admin_input}")
            # 检查是否输入了admincaidan
            if len(self.admin_input) >= len(self.admin_code):
                if self.admin_code == self.admin_input[-len(self.admin_code):]:
                    print("检测到admincaidan，显示开发菜单")
                    self.show_admin_menu()
                    self.admin_input = ""
    
    def init_background_tasks(self):
        
        if self.floating_toolbar_enabled:
            self.init_floating_ball()
        
        # 在主线程中初始化系统托盘
        self.init_system_tray()
    
    def show_notification(self, message, notification_type="info"):
        print(f"显示通知：{message}，类型：{notification_type}")
        try:
            self.notification_widget.show_notification(message, notification_type)
            print("通知显示成功")
        except Exception as e:
            print(f"通知显示失败：{str(e)}")
            traceback.print_exc()
    
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
        dialog.setWindowTitle("网络错误")
        dialog.setGeometry(300, 300, 450, 250)
        
        # 自定义样式
        dialog.setStyleSheet(""".QDialog {
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
        }""")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 标题
        title_label = QLabel("网络连接错误")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 错误信息
        error_label = QLabel()
        error_label.setWordWrap(True)
        error_label.setStyleSheet("font-size: 14px; color: #666;")
        error_label.setAlignment(Qt.AlignCenter)
        
        if error_type == "proxy":
            error_text = f"检测到系统或环境变量中存在代理设置，应用不支持代理环境。\n\n当前代理：{proxy_info}\n\n请关闭代理设置后重新启动应用。"
        else:
            error_text = f"网络连接失败，应用无法正常运行。\n\n错误信息：{error_msg}\n\n请检查网络连接后重新启动应用。"
        
        error_label.setText(error_text)
        layout.addWidget(error_label)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
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
        
        # 检查代理设置
        has_proxy, proxy_info = self.check_proxy_settings()
        if has_proxy:
            # 显示代理错误提示并退出
            logger.error(f"检测到代理设置：{proxy_info}，应用不支持代理环境")
            # 创建临时对话框显示错误信息
            
            dialog = QDialog()
            dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowCloseButtonHint)
            dialog.setWindowTitle("网络错误")
            dialog.setGeometry(300, 300, 450, 250)
            
            # 自定义样式
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #f8f9fa;
                    border-radius: 10px;
                }
                QLabel {
                    font-size: 14px;
                    color: #666;
                    margin-bottom: 20px;
                }
                QLabel#title {
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                }
                QPushButton {
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                    background-color: #6c757d;
                    color: white;
                }
                QPushButton:hover {
                    opacity: 0.9;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(30, 30, 30, 30)
            layout.setSpacing(20)
            
            # 标题
            title_label = QLabel("网络连接错误")
            title_label.setObjectName("title")
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # 错误信息
            error_label = QLabel()
            error_label.setWordWrap(True)
            error_label.setAlignment(Qt.AlignCenter)
            error_text = f"检测到系统或环境变量中存在代理设置，应用不支持代理环境。\n\n当前代理：{proxy_info}\n\n请关闭代理设置后重新启动应用。"
            error_label.setText(error_text)
            layout.addWidget(error_label)
            
            # 按钮
            exit_btn = QPushButton("退出")
            layout.addWidget(exit_btn, 0, Qt.AlignCenter)
            
            # 按钮点击事件
            def on_exit():
                dialog.reject()
            
            exit_btn.clicked.connect(on_exit)
            
            # 显示对话框
            dialog.exec_()
            sys.exit()
        
        # 测试网络连接
        network_ok, error_msg = self.test_network_connection()
        if not network_ok:
            # 显示网络错误提示并退出
            logger.error(f"网络连接失败：{error_msg}")
            # 创建临时对话框显示错误信息
            
            dialog = QDialog()
            dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowCloseButtonHint)
            dialog.setWindowTitle("网络错误")
            dialog.setGeometry(300, 300, 450, 250)
            
            # 自定义样式
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #f8f9fa;
                    border-radius: 10px;
                }
                QLabel {
                    font-size: 14px;
                    color: #666;
                    margin-bottom: 20px;
                }
                QLabel#title {
                    font-size: 18px;
                    font-weight: bold;
                    color: #333;
                }
                QPushButton {
                    padding: 10px 20px;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 500;
                    background-color: #6c757d;
                    color: white;
                }
                QPushButton:hover {
                    opacity: 0.9;
                }
            """)
            
            layout = QVBoxLayout(dialog)
            layout.setContentsMargins(30, 30, 30, 30)
            layout.setSpacing(20)
            
            # 标题
            title_label = QLabel("网络连接错误")
            title_label.setObjectName("title")
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # 错误信息
            error_label = QLabel()
            error_label.setWordWrap(True)
            error_label.setAlignment(Qt.AlignCenter)
            error_text = f"网络连接失败，应用无法正常运行。\n\n错误信息：{error_msg}\n\n请检查网络连接后重新启动应用。"
            error_label.setText(error_text)
            layout.addWidget(error_label)
            
            # 按钮
            exit_btn = QPushButton("退出")
            layout.addWidget(exit_btn, 0, Qt.AlignCenter)
            
            # 按钮点击事件
            def on_exit():
                dialog.reject()
            
            exit_btn.clicked.connect(on_exit)
            
            # 显示对话框
            dialog.exec_()
            sys.exit()
    
    def show_admin_menu(self):
        
        print("开始创建开发菜单")
        
        # 创建开发菜单窗口
        dialog = QDialog(self)
        dialog.setWindowTitle("开发者菜单")
        dialog.setGeometry(100, 100, 300, 200)
        dialog.setMinimumSize(250, 180)
        
        # 设置窗口样式
        dialog.setStyleSheet("""
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
        """)
        
        layout = QVBoxLayout(dialog)
        
        # 添加标题
        title_label = QLabel("开发者菜单")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 测试致命错误的按钮
        test_error_btn = QPushButton("测试致命错误")
        test_error_btn.clicked.connect(self.test_fatal_error)
        layout.addWidget(test_error_btn)
        
        # 显示系统信息的按钮
        info_btn = QPushButton("显示系统信息")
        info_btn.clicked.connect(self.show_system_info)
        layout.addWidget(info_btn)
        
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
        
        info = f"Python版本: {platform.python_version()}\n"
        info += f"系统平台: {platform.system()} {platform.release()}\n"
        info += f"Qt版本: {Qt.QT_VERSION_STR}\n"
        info += f"应用路径: {sys.executable}\n"
        
        QMessageBox.information(self, "系统信息", info)
    
    def on_window_closed(self):
        
        if self.floating_toolbar_enabled and self.floating_ball:
            self.floating_ball.show()
            self.floating_ball.raise_()
    
    def on_merge_started(self, task_id, ep_index):
        # 创建并显示合并进度窗口
        window_key = f"{task_id}_{ep_index}"
        if window_key not in self.merge_progress_windows:
            self.merge_progress_windows[window_key] = MergeProgressWindow(self)
            self.merge_progress_windows[window_key].show()
            self.merge_progress_windows[window_key].update_progress(0, "准备合并...")
    
    def on_merge_finished(self, task_id, ep_index):
        # 关闭合并进度窗口
        window_key = f"{task_id}_{ep_index}"
        if window_key in self.merge_progress_windows:
            window = self.merge_progress_windows[window_key]
            if window and not window.isHidden():
                window.update_progress(100, "合并完成")
                # 延迟1秒关闭窗口，让用户有时间看到完成信息
                QTimer.singleShot(1000, window.close)
            del self.merge_progress_windows[window_key]
    
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
        if event.type() == QEvent.User:
            
            if hasattr(event, 'message') and hasattr(event, 'notification_type'):
                self.show_notification(event.message, event.notification_type)
                return True
            # 处理UpdateFolderEvent
            elif hasattr(event, 'folders'):
                logger = logging.getLogger(__name__)
                logger.info("处理UpdateFolderEvent")
                try:
                    logger.info(f"调用update_folder_list，收藏夹数量：{len(event.folders)}")
                    self.update_folder_list(event.folders)
                    logger.info("update_folder_list执行完成")
                    self.status_label.setText("收藏夹列表刷新成功")
                    logger.info("UI更新完成")
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"UI更新失败：{str(e)}")
                return True
            # 处理UpdateContentEvent
            elif hasattr(event, 'items'):
                logger = logging.getLogger(__name__)
                logger.info("处理UpdateContentEvent")
                try:
                    logger.info(f"调用update_content_list，内容数量：{len(event.items)}")
                    self.update_content_list(event.items)
                    logger.info("update_content_list执行完成")
                    # 更新状态标签
                    self.status_label.setText(f"收藏内容获取成功 - 共 {len(event.items)} 个收藏内容")
                    # 强制刷新UI
                    self.content_list.repaint()
                    self.content_list.update()
                    # 强制重新计算布局和刷新
                    QApplication.processEvents()
                    QApplication.processEvents()
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"内容更新失败：{str(e)}")
                    # 显示错误信息
                    self.status_label.setText("就绪")
                return True
            # 处理StatusEvent
            elif hasattr(event, 'status') and hasattr(event, 'message'):
                logger = logging.getLogger(__name__)
                logger.info("处理StatusEvent")
                try:
                    if event.status == "success":
                        self.status_label.setText(f"收藏内容获取成功 - {event.message}")
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"状态更新失败：{str(e)}")
                return True
            # 处理ErrorEvent
            elif hasattr(event, 'error'):
                logger = logging.getLogger(__name__)
                logger.info("处理ErrorEvent")
                try:
                    self.show_notification(f"获取收藏内容失败：{event.error}", "error")
                    self.status_label.setText("就绪")
                    self.update_content_list([])
                except Exception as e:
                    traceback.print_exc()
                    logger.error(f"错误处理失败：{str(e)}")
                return True
        return super().eventFilter(obj, event)
    
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
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        
        self.update_progress_bar_position()
    
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
        except Exception as e:
            print(f"更新解析进度失败：{str(e)}")

    def init_ui(self):
        self.setWindowTitle(f"B站视频解析工具{version_info['version']} - 作者：寒烟似雪(逸雨) QQ：2273962061/3241417097")
        self.setMinimumSize(600, 500)
        
        custom_style = BASE_STYLE + """
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                height: 28px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                width: 28px;
                height: 28px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """
        self.setStyleSheet(custom_style)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 10, 0)
        title_layout.setSpacing(8)
        title_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        
        logo_label = QLabel()
        try:
            
            pixmap = QPixmap("logo.png")
            if not pixmap.isNull():
                
                scaled_pixmap = pixmap.scaled(20, 20, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
                logo_label.setFixedSize(24, 24)
                title_layout.addWidget(logo_label)
        except Exception as e:
            
            pass
        
        
        title_label = QLabel("B站视频解析下载工具")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-size: 14px;")
        title_layout.addWidget(title_label, stretch=1)
        
        
        # 创建登录信息容器
        self.login_info_widget = QWidget()
        self.login_info_layout = QHBoxLayout(self.login_info_widget)
        self.login_info_layout.setContentsMargins(0, 0, 0, 0)
        self.login_info_layout.setSpacing(0)  # 设置间距为0，使头像和昵称完全紧贴
        
        # 头像标签
        self.avatar_label = QLabel()
        self.avatar_label.setFixedSize(24, 24)
        self.avatar_label.setStyleSheet("border-radius: 12px; background-color: #374151;")
        self.avatar_label.setAlignment(Qt.AlignCenter)
        self.login_info_layout.addWidget(self.avatar_label)
        
        # 用户名标签
        self.login_info_label = QLabel("如果想要解析会员内容请登录")
        self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px; padding: 0px;")
        self.login_info_label.setAlignment(Qt.AlignCenter)
        # 设置用户名标签的边距，确保与头像紧贴
        self.login_info_layout.addWidget(self.login_info_label)
        
        # 确保布局紧凑
        self.login_info_widget.adjustSize()
        
        # 设置容器属性
        self.login_info_widget.setMinimumWidth(0)  # 移除最小宽度限制，让容器根据内容自动调整
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
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(15)
        content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title_label = QLabel("B站视频解析下载工具")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2563eb;")
        title_label.setWordWrap(True)
        title_label.setMinimumHeight(32)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        bilibili_label = QLabel("哔哩哔哩：不会玩python的man")
        bilibili_label.setObjectName("bilibiliLabel")
        bilibili_label.setStyleSheet("color: #00a1d6; text-decoration: underline;")
        bilibili_label.setCursor(QCursor(Qt.PointingHandCursor))
        bilibili_label.setWordWrap(True)
        bilibili_label.setMinimumHeight(32)
        bilibili_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        bilibili_label.mousePressEvent = lambda e: webbrowser.open(self.bilibili_space)
        
        self.bilibili_btn = QPushButton("访问主页")
        self.bilibili_btn.setObjectName("bilibiliBtn")
        self.bilibili_btn.setMinimumHeight(28)
        self.bilibili_btn.setMinimumWidth(80)
        self.bilibili_btn.setMaximumWidth(100)
        self.bilibili_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.bilibili_btn.clicked.connect(lambda: webbrowser.open(self.bilibili_space))
        
        header_layout.addWidget(title_label, stretch=2)
        header_layout.addWidget(bilibili_label, stretch=1)
        header_layout.addWidget(self.bilibili_btn)
        content_layout.addLayout(header_layout)

        
        author_label = QLabel("作者：寒烟似雪(逸雨) QQ：2273962061/3241417097")
        author_label.setStyleSheet("font-size: 10px; color: #6b7280; text-align: center;")
        author_label.setWordWrap(True)
        author_label.setMinimumHeight(28)
        author_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        content_layout.addWidget(author_label)

        
        sys_info_group = QGroupBox("系统信息")
        sys_info_group.setMinimumHeight(120)
        sys_info_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        sys_layout = QVBoxLayout(sys_info_group)
        sys_layout.setSpacing(8)
        sys_layout.setContentsMargins(10, 10, 10, 10)

        
        login_layout = QHBoxLayout()
        login_layout.setSpacing(8)
        login_label = QLabel("登录状态：")
        login_label.setMinimumWidth(70)
        login_label.setMinimumHeight(28)
        login_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.user_info_label = QLabel("加载中...")
        self.user_info_label.setWordWrap(True)
        self.user_info_label.setMinimumHeight(28)
        self.user_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.vip_label = QLabel()
        self.vip_label.setMinimumHeight(28)
        self.vip_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        login_layout.addWidget(login_label)
        login_layout.addWidget(self.user_info_label, stretch=1)
        login_layout.addWidget(self.vip_label)
        sys_layout.addLayout(login_layout)

        
        hevc_layout = QHBoxLayout()
        hevc_layout.setSpacing(8)
        hevc_label = QLabel("HEVC支持：")
        hevc_label.setMinimumWidth(70)
        hevc_label.setMinimumHeight(28)
        hevc_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hevc_label = QLabel("检测中...")
        self.hevc_label.setWordWrap(True)
        self.hevc_label.setMinimumHeight(28)
        self.hevc_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.hevc_btn = QPushButton("安装HEVC扩展")
        self.hevc_btn.setObjectName("hevcBtn")
        self.hevc_btn.setMinimumHeight(24)
        self.hevc_btn.setMinimumWidth(90)
        self.hevc_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.hevc_btn.setEnabled(False)
        self.hevc_btn.clicked.connect(lambda: self.signal_emitter.install_hevc.emit())
        hevc_layout.addWidget(hevc_label)
        hevc_layout.addWidget(self.hevc_label, stretch=1)
        hevc_layout.addWidget(self.hevc_btn)
        
        
        floating_layout = QHBoxLayout()
        floating_layout.setSpacing(8)
        floating_label = QLabel("悬浮工具栏：")
        floating_label.setMinimumWidth(70)
        floating_label.setMinimumHeight(28)
        floating_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.floating_checkbox = QCheckBox()
        self.floating_checkbox.setChecked(self.floating_toolbar_enabled)
        self.floating_checkbox.setMinimumHeight(28)
        self.floating_checkbox.setMinimumWidth(20)
        self.floating_checkbox.stateChanged.connect(lambda state: self.toggle_floating_toolbar(state == Qt.Checked))
        floating_layout.addWidget(floating_label)
        floating_layout.addWidget(self.floating_checkbox)
        floating_layout.addStretch(1)
        
        sys_layout.addLayout(floating_layout)

        content_layout.addWidget(sys_info_group)

        
        url_layout = QHBoxLayout()
        url_layout.setSpacing(10)
        url_layout.setContentsMargins(0, 0, 0, 0)
        url_label = QLabel("视频链接：")
        url_label.setMinimumWidth(80)
        url_label.setMinimumHeight(36)
        url_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("支持BV/ss/av号")
        self.url_edit.setMinimumHeight(36)
        self.url_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.parse_btn = QPushButton("解析")
        self.parse_btn.setMinimumHeight(36)
        self.parse_btn.setMinimumWidth(70)
        self.parse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.parse_btn.clicked.connect(self.on_parse)
        self.batch_parse_btn = QPushButton("批量")
        self.batch_parse_btn.setMinimumHeight(36)
        self.batch_parse_btn.setMinimumWidth(70)
        self.batch_parse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.batch_parse_btn.clicked.connect(self.on_batch_parse)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_edit, stretch=1)
        url_layout.addWidget(self.parse_btn)
        url_layout.addWidget(self.batch_parse_btn)
        content_layout.addLayout(url_layout)

        
        self.tv_mode_checkbox = QCheckBox("TV端无水印模式")
        self.tv_mode_checkbox.setMinimumHeight(44)
        self.tv_mode_checkbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.tv_mode_checkbox.setStyleSheet("font-size: 13px;")
        content_layout.addWidget(self.tv_mode_checkbox)



        


        
        # 创建Tab控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setMinimumHeight(320)
        self.tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.tab_widget.setStyleSheet("""
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
        """)
        
        # 视频解析标签页
        video_tab = QWidget()
        video_layout = QVBoxLayout(video_tab)
        video_layout.setSpacing(15)
        video_layout.setContentsMargins(15, 15, 15, 15)
        
        info_layout = QHBoxLayout()
        info_layout.setSpacing(15)
        
        self.cover_label = QLabel()
        self.cover_label.setMinimumSize(120, 80)
        self.cover_label.setMaximumSize(180, 120)
        self.cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("无封面")
        info_layout.addWidget(self.cover_label)
        
        info_right_layout = QVBoxLayout()
        info_right_layout.setSpacing(8)
        
        title_layout = QHBoxLayout()
        title_layout.setSpacing(12)
        title_label = QLabel("标题：")
        title_label.setMinimumWidth(60)
        title_label.setMinimumHeight(24)
        title_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.video_title = QLabel("未解析")
        self.video_title.setWordWrap(True)
        self.video_title.setMinimumHeight(44)
        self.video_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.video_title.setStyleSheet("font-size: 14px; font-weight: 500;")
        title_layout.addWidget(title_label, alignment=Qt.AlignTop)
        title_layout.addWidget(self.video_title, stretch=1)
        info_right_layout.addLayout(title_layout)
        
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(12)
        
        duration_label = QLabel("时长：")
        duration_label.setMinimumWidth(60)
        duration_label.setMinimumHeight(24)
        duration_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.duration_label = QLabel("-")
        self.duration_label.setMinimumHeight(24)
        self.duration_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        type_label = QLabel("类型：")
        type_label.setMinimumWidth(60)
        type_label.setMinimumHeight(24)
        type_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.type_label = QLabel("未解析")
        self.type_label.setMinimumHeight(24)
        self.type_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        meta_layout.addWidget(duration_label)
        meta_layout.addWidget(self.duration_label, stretch=1)
        meta_layout.addWidget(type_label)
        meta_layout.addWidget(self.type_label, stretch=1)
        info_right_layout.addLayout(meta_layout)
        
        info_layout.addLayout(info_right_layout, stretch=1)
        video_layout.addLayout(info_layout)
        
        quality_layout = QHBoxLayout()
        quality_layout.setSpacing(12)
        quality_label = QLabel("清晰度：")
        quality_label.setMinimumWidth(80)
        quality_label.setMinimumHeight(24)
        quality_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        self.select_episode_btn = QPushButton("选择集数")
        self.select_episode_btn.setEnabled(False)
        self.select_episode_btn.setMinimumHeight(24)
        self.select_episode_btn.setMinimumWidth(100)
        self.select_episode_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.select_episode_btn.clicked.connect(self.open_episode_selection)
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItem("请选择清晰度")
        self.quality_combo.setEnabled(False)
        self.quality_combo.setMinimumHeight(24)
        self.quality_combo.setMinimumWidth(150)
        self.quality_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.quality_combo.setStyleSheet("""
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
        """)
        
        self.quality_combo.currentIndexChanged.connect(self.on_quality_combo_changed)
        
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo, stretch=1)
        quality_layout.addWidget(self.select_episode_btn)
        video_layout.addLayout(quality_layout)
        
        # 完全模式
        full_mode_layout = QHBoxLayout()
        full_mode_layout.setSpacing(12)
        self.full_mode_checkbox = QCheckBox("完全模式（自动全选集数并下载）")
        self.full_mode_checkbox.setMinimumHeight(36)
        self.full_mode_checkbox.setStyleSheet("font-size: 13px;")
        self.full_mode_checkbox.setEnabled(False)
        full_mode_layout.addWidget(self.full_mode_checkbox)
        full_mode_layout.addStretch(1)
        video_layout.addLayout(full_mode_layout)
        
        path_layout = QHBoxLayout()
        path_layout.setSpacing(12)
        path_label = QLabel("保存路径：")
        path_label.setMinimumWidth(80)
        path_label.setMinimumHeight(44)
        path_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.path_edit = QLineEdit()
        self.path_edit.setMinimumHeight(44)
        self.path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        last_path = self.config.get_app_setting("last_save_path")
        default_path = last_path if last_path else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        os.makedirs(default_path, exist_ok=True)
        self.path_edit.setText(default_path)
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.setMinimumHeight(44)
        self.browse_btn.setMinimumWidth(80)
        self.browse_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(self.browse_btn)
        video_layout.addLayout(path_layout)
        
        # 弹幕解析标签页
        danmaku_tab = QWidget()
        danmaku_layout = QVBoxLayout(danmaku_tab)
        danmaku_layout.setSpacing(15)
        danmaku_layout.setContentsMargins(15, 15, 15, 15)
        
        danmaku_info_group = QGroupBox("弹幕信息")
        danmaku_info_layout = QVBoxLayout(danmaku_info_group)
        danmaku_info_layout.setSpacing(12)
        
        danmaku_count_layout = QHBoxLayout()
        danmaku_count_label = QLabel("弹幕数量：")
        danmaku_count_label.setMinimumWidth(80)
        danmaku_count_label.setMinimumHeight(24)
        self.danmaku_count_label = QLabel("未解析")
        self.danmaku_count_label.setMinimumHeight(24)
        danmaku_count_layout.addWidget(danmaku_count_label)
        danmaku_count_layout.addWidget(self.danmaku_count_label, stretch=1)
        danmaku_info_layout.addLayout(danmaku_count_layout)
        
        danmaku_format_layout = QHBoxLayout()
        danmaku_format_label = QLabel("弹幕格式：")
        danmaku_format_label.setMinimumWidth(80)
        danmaku_format_label.setMinimumHeight(24)
        self.danmaku_format_combo = QComboBox()
        self.danmaku_format_combo.addItem("XML")
        self.danmaku_format_combo.addItem("ASS")
        self.danmaku_format_combo.addItem("JSON")
        self.danmaku_format_combo.setMinimumHeight(24)
        self.danmaku_format_combo.setEnabled(False)  # 初始禁用
        danmaku_format_layout.addWidget(danmaku_format_label)
        danmaku_format_layout.addWidget(self.danmaku_format_combo, stretch=1)
        danmaku_info_layout.addLayout(danmaku_format_layout)
        
        danmaku_options_layout = QVBoxLayout()
        self.danmaku_checkbox = QCheckBox("下载弹幕")
        self.danmaku_checkbox.setMinimumHeight(24)
        self.danmaku_checkbox.setStyleSheet("font-size: 13px;")
        self.danmaku_checkbox.setEnabled(False)  # 初始禁用
        danmaku_options_layout.addWidget(self.danmaku_checkbox)
        
        # 添加选择弹幕按钮
        self.select_danmaku_btn = QPushButton("选择弹幕")
        self.select_danmaku_btn.setMinimumHeight(24)
        self.select_danmaku_btn.setMinimumWidth(100)
        self.select_danmaku_btn.setEnabled(False)
        self.select_danmaku_btn.clicked.connect(self.open_danmaku_selection)
        danmaku_options_layout.addWidget(self.select_danmaku_btn)
        
        danmaku_info_layout.addLayout(danmaku_options_layout)
        
        danmaku_layout.addWidget(danmaku_info_group)
        
        # 收藏夹标签页
        favorite_tab = QWidget()
        favorite_tab.setStyleSheet("background-color: #f5f5f5;")
        favorite_layout = QVBoxLayout(favorite_tab)
        favorite_layout.setSpacing(16)
        favorite_layout.setContentsMargins(16, 16, 16, 16)
        favorite_tab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 左右布局容器
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(16)
        main_content_layout.setContentsMargins(0, 0, 0, 0)
        
        # 左侧：收藏夹列表区域
        folder_section = QWidget()
        folder_section.setStyleSheet("background-color: white; border-radius: 8px;")
        folder_section.setMinimumWidth(220)
        folder_section.setMaximumWidth(260)
        folder_section.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        folder_section_layout = QVBoxLayout(folder_section)
        folder_section_layout.setSpacing(12)
        folder_section_layout.setContentsMargins(16, 16, 16, 16)
        
        # 收藏夹标题和刷新按钮
        folder_header = QWidget()
        folder_header_layout = QHBoxLayout(folder_header)
        folder_header_layout.setSpacing(12)
        folder_header_layout.setContentsMargins(0, 0, 0, 0)
        
        folder_title = QLabel("收藏夹列表")
        folder_title.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: 600;
                color: #1f2937;
            }
        """)
        
        refresh_folder_btn = QPushButton("刷新")
        refresh_folder_btn.setMinimumHeight(32)
        refresh_folder_btn.setMinimumWidth(60)
        refresh_folder_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #2563eb;
            }
            QPushButton:pressed {
                background-color: #1d4ed8;
            }
        """)
        refresh_folder_btn.clicked.connect(self.refresh_folders)
        
        folder_header_layout.addWidget(folder_title)
        folder_header_layout.addStretch(1)
        folder_header_layout.addWidget(refresh_folder_btn)
        folder_section_layout.addWidget(folder_header)
        
        # 收藏夹列表
        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.SingleSelection)
        self.folder_list.setMinimumHeight(400)
        self.folder_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.folder_list.setStyleSheet("""
            QListWidget {
                border: none;
                border-radius: 6px;
                background-color: #f9fafb;
                padding: 8px;
            }
            QListWidget::item {
                padding: 12px 14px;
                border-radius: 6px;
                margin-bottom: 6px;
                font-size: 14px;
                color: #374151;
            }
            QListWidget::item:hover {
                background-color: #f3f4f6;
            }
            QListWidget::item:selected {
                background-color: #eff6ff;
                color: #2563eb;
            }
        """)
        self.folder_list.itemClicked.connect(self.on_folder_selected)
        folder_section_layout.addWidget(self.folder_list, stretch=1)
        
        main_content_layout.addWidget(folder_section)
        
        # 右侧：收藏内容区域
        content_section = QWidget()
        content_section.setStyleSheet("background-color: white; border-radius: 8px;")
        content_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_section_layout = QVBoxLayout(content_section)
        content_section_layout.setSpacing(12)
        content_section_layout.setContentsMargins(16, 16, 16, 16)
        
        # 收藏内容标题
        content_title = QLabel("收藏内容")
        content_title.setStyleSheet("""
            QLabel {
                font-size: 15px;
                font-weight: 600;
                color: #1f2937;
            }
        """)
        content_title.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # 操作按钮 - 放在右上角
        action_buttons = QWidget()
        action_buttons_layout = QHBoxLayout(action_buttons)
        action_buttons_layout.setSpacing(8)
        action_buttons_layout.setContentsMargins(0, 0, 0, 0)
        
        clear_selection_btn = QPushButton("清空选择")
        clear_selection_btn.setMinimumHeight(32)
        clear_selection_btn.setMinimumWidth(80)
        clear_selection_btn.setStyleSheet("""
            QPushButton {
                background-color: #f3f4f6;
                color: #4b5563;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #e5e7eb;
            }
            QPushButton:pressed {
                background-color: #d1d5db;
            }
        """)
        clear_selection_btn.clicked.connect(lambda: self.content_list.clearSelection())
        
        self.parse_favorite_btn = QPushButton("解析选中")
        self.parse_favorite_btn.setMinimumHeight(32)
        self.parse_favorite_btn.setMinimumWidth(80)
        self.parse_favorite_btn.setEnabled(False)
        self.parse_favorite_btn.setStyleSheet("""
            QPushButton {
                background-color: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
                padding: 6px 16px;
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
        """)
        self.parse_favorite_btn.clicked.connect(self.parse_selected_content)
        
        action_buttons_layout.addWidget(clear_selection_btn)
        action_buttons_layout.addWidget(self.parse_favorite_btn)
        
        # 标题和按钮的水平布局
        title_and_buttons = QWidget()
        title_and_buttons_layout = QHBoxLayout(title_and_buttons)
        title_and_buttons_layout.setSpacing(12)
        title_and_buttons_layout.setContentsMargins(0, 0, 0, 0)
        title_and_buttons_layout.addWidget(content_title)
        title_and_buttons_layout.addStretch(1)
        title_and_buttons_layout.addWidget(action_buttons)
        content_section_layout.addWidget(title_and_buttons)
        
        # 收藏内容列表（卡片模式）
        self.content_list = QListWidget()
        self.content_list.setViewMode(QListWidget.IconMode)
        self.content_list.setResizeMode(QListWidget.Adjust)
        self.content_list.setFlow(QListWidget.LeftToRight)
        self.content_list.setSpacing(12)
        self.content_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.content_list.setMinimumHeight(800)
        self.content_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_list.setWrapping(True)
        self.content_list.setWordWrap(True)
        self.content_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.content_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.content_list.setStyleSheet("""
            QListWidget {
                border: none;
                border-radius: 6px;
                background-color: #f9fafb;
                padding: 12px;
                min-height: 800px;
                max-height: 2000px;
            }
            QListWidget::item {
                border: none;
                background: transparent;
            }
            QListWidget::item:selected {
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #f1f1f1;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c1c1c1;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a1a1a1;
            }
        """)
        self.content_list.itemDoubleClicked.connect(self.on_content_double_clicked)
        self.content_list.itemClicked.connect(self.on_content_clicked)
        
        # 使用QScrollArea确保完整的滚动功能
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("border: none;")
        scroll_area.setMinimumHeight(600)
        scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 创建一个容器widget来容纳内容列表
        scroll_container = QWidget()
        scroll_layout = QVBoxLayout(scroll_container)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.addWidget(self.content_list)
        
        scroll_area.setWidget(scroll_container)
        content_section_layout.addWidget(scroll_area, stretch=1)
        
        main_content_layout.addWidget(content_section, stretch=1)
        
        favorite_layout.addLayout(main_content_layout, stretch=1)
        
        # 添加标签页
        self.tab_widget.addTab(video_tab, "视频解析")
        self.tab_widget.addTab(danmaku_tab, "弹幕解析")
        self.tab_widget.addTab(favorite_tab, "收藏夹")
        
        # 连接标签页切换信号
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        content_layout.addWidget(self.tab_widget)

        
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(12)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        self.main_progress = QProgressBar()
        self.main_progress.setRange(0, 100)
        self.main_progress.setMinimumHeight(14)
        self.main_progress.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        progress_layout.addWidget(self.main_progress)
        self.status_label = QLabel("就绪 - 请输入链接并解析")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumHeight(44)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 11px;")
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        progress_layout.addWidget(self.status_label, alignment=Qt.AlignCenter)
        
        content_layout.addLayout(progress_layout, stretch=1)

        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setEnabled(False)
        self.download_btn.setMinimumHeight(44)
        self.download_btn.setMinimumWidth(110)
        self.download_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.download_btn.clicked.connect(self.on_download)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setMinimumHeight(44)
        self.cancel_btn.setMinimumWidth(80)
        self.cancel_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.cancel_btn.clicked.connect(self.on_cancel_download)
        self.task_manager_btn = QPushButton("任务")
        self.task_manager_btn.setStyleSheet("background-color: #722ed1;")
        self.task_manager_btn.setMinimumHeight(44)
        self.task_manager_btn.setMinimumWidth(80)
        self.task_manager_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.task_manager_btn.clicked.connect(self.open_task_manager)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setStyleSheet("background-color: #94a3b8;")
        self.settings_btn.setMinimumHeight(44)
        self.settings_btn.setMinimumWidth(80)
        self.settings_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.settings_btn.clicked.connect(self.open_settings)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.task_manager_btn)
        btn_layout.addWidget(self.settings_btn)
        content_layout.addLayout(btn_layout)
        
        main_layout.addWidget(content_widget)

        self.signal_emitter.user_info_updated.connect(self.update_user_info)
        self.signal_emitter.hevc_checked.connect(self.update_hevc_status)
        self.signal_emitter.hevc_download_progress.connect(self.update_hevc_progress)
        self.signal_emitter.hevc_install_finished.connect(self.on_hevc_install_finish)
        self.signal_emitter.parse_finished.connect(self.on_parse_finished)
        self.signal_emitter.cookie_verified.connect(self.on_cookie_verified)
        self.signal_emitter.download_progress.connect(self.update_download_progress)
        self.signal_emitter.show_space_videos.connect(self.on_show_space_videos)

        self.selected_episodes = []

    def load_local_cookie(self):
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, "r", encoding="utf-8") as f:
                    cookie = f.read().strip()
                    if cookie:
                        
                        if hasattr(self, 'parser') and self.parser:
                            
                            self.parser.save_cookies(cookie)
            except Exception as e:
                logger.error(f"本地Cookie读取失败：{str(e)[:15]}")
        
        
        import threading
        def verify_cookie_in_thread():
            self.check_cookie_validity()
        
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
        
        import threading
        def get_folders():
            try:
                folders = self.parser.get_user_folders()
                logger.info(f"获取到 {len(folders)} 个收藏夹，准备更新UI")
                
                # 使用QApplication.postEvent确保在主线程中执行UI更新
                
                # 创建一个自定义事件来更新UI
                class UpdateFolderEvent(QEvent):
                    def __init__(self, folders):
                        super().__init__(QEvent.User)
                        self.folders = folders
                
                # 事件处理函数
                def event_handler(event):
                    if isinstance(event, UpdateFolderEvent):
                        logger.info("开始处理UpdateFolderEvent")
                        try:
                            logger.info(f"调用update_folder_list，收藏夹数量：{len(event.folders)}")
                            self.update_folder_list(event.folders)
                            logger.info("update_folder_list执行完成")
                            self.status_label.setText("收藏夹列表刷新成功")
                            logger.info("UI更新完成")
                        except Exception as e:
                            traceback.print_exc()
                            logger.error(f"UI更新失败：{str(e)}")
                        return True
                    return False
                
                # 安装事件过滤器
                self.installEventFilter(self)
                
                # 发送事件
                event = UpdateFolderEvent(folders)
                QCoreApplication.postEvent(self, event)
                logger.info("事件已发送")
            except Exception as e:
                traceback.print_exc()
                logger.error(f"获取收藏夹失败：{str(e)}")
                
                # 使用QApplication.postEvent在主线程中显示错误
                
                class ErrorEvent(QEvent):
                    def __init__(self, error):
                        super().__init__(QEvent.User)
                        self.error = error
                
                def error_event_handler(event):
                    if isinstance(event, ErrorEvent):
                        self.show_notification(f"获取收藏夹失败：{event.error}", "error")
                        self.status_label.setText("就绪")
                        return True
                    return False
                
                event = ErrorEvent(str(e))
                QCoreApplication.postEvent(self, event)
        
        thread = threading.Thread(target=get_folders)
        thread.daemon = True
        thread.start()
    
    def update_folder_list(self, folders):
        logger.info(f"更新收藏夹列表，接收到 {len(folders)} 个收藏夹")
        
        # 确保folder_list存在
        if not hasattr(self, 'folder_list'):
            logger.error("folder_list不存在")
            return
        
        # 清空列表
        self.folder_list.clear()
        
        if not folders:
            # 当没有收藏夹时，显示提示信息
            logger.info("收藏夹列表为空")
            empty_item = QListWidgetItem("无收藏夹")
            empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsSelectable)
            empty_item.setForeground(QColor('#94a3b8'))
            self.folder_list.addItem(empty_item)
            
            # 清空内容列表
            if hasattr(self, 'content_list'):
                self.content_list.clear()
                empty_content_item = QListWidgetItem("无收藏夹")
                empty_content_item.setFlags(empty_content_item.flags() & ~Qt.ItemIsSelectable)
                empty_content_item.setForeground(QColor('#94a3b8'))
                self.content_list.addItem(empty_content_item)
            
            if hasattr(self, 'parse_favorite_btn'):
                self.parse_favorite_btn.setEnabled(False)
        else:
            logger.info(f"开始添加 {len(folders)} 个收藏夹到列表")
            for i, folder in enumerate(folders):
                title = folder.get('title', '未知收藏夹')
                count = folder.get('media_count', 0)
                folder_id = folder.get('id')
                logger.info(f"收藏夹 {i+1}: {title}, ID: {folder_id}, 内容数: {count}")
                item_text = f"{title} ({count}个内容)"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, folder_id)
                self.folder_list.addItem(item)
            
            # 默认选中第一个收藏夹并显示其内容
            if folders:
                logger.info("选中第一个收藏夹并显示内容")
                self.folder_list.setCurrentRow(0)
                first_item = self.folder_list.item(0)
                if first_item:
                    logger.info(f"第一个收藏夹: {first_item.text()}")
                    self.on_folder_selected(first_item)
        
        # 强制刷新UI
        logger.info("强制刷新UI")
        self.folder_list.repaint()
        self.folder_list.update()
        
        # 触发布局更新
        if hasattr(self, 'content_list'):
            self.content_list.repaint()
            self.content_list.update()
        
        # 强制重新计算布局和刷新
        QApplication.processEvents()
        QApplication.processEvents()  # 再次调用确保刷新
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
        
        import threading
        
        def get_folder_content():
            logger = logging.getLogger(__name__)
            logger.info("get_folder_content线程开始执行")
            try:
                logger.info(f"开始获取收藏夹内容，folder_id: {folder_id}")
                content = self.parser.get_folder_content(folder_id)
                logger.info(f"获取收藏夹内容成功，返回数据: {content}")
                logger.info(f"获取收藏夹内容成功，共 {len(content['items'])} 个项目")
                
                # 确保content_items是一个列表
                content_items = content.get('items', [])
                logger.info(f"准备更新UI，内容数量：{len(content_items)}")
                
                # 直接在主线程中更新UI
                def update_ui():
                    try:
                        logger.info("开始更新收藏内容UI")
                        logger.info(f"接收到的内容数量：{len(content_items)}")
                        
                        # 更新内容列表
                        self.update_content_list(content_items)
                        
                        # 更新状态标签
                        self.status_label.setText(f"收藏内容获取成功 - 共 {len(content_items)} 个收藏内容")
                        
                        # 强制刷新UI
                        self.content_list.repaint()
                        self.content_list.update()
                        
                        # 强制处理所有待处理的事件
                        QApplication.processEvents()
                        QApplication.processEvents()
                        
                        logger.info("收藏内容UI更新完成")
                    except Exception as e:
                        traceback.print_exc()
                        logger.error(f"UI更新失败：{str(e)}")
                
                # 使用事件系统在主线程中更新UI
                logger.info("准备使用事件系统在主线程中更新UI")
                
                # 定义事件类
                class UpdateContentEvent(QEvent):
                    def __init__(self, items):
                        super().__init__(QEvent.User)
                        self.items = items
                
                # 发送事件到主线程
                event = UpdateContentEvent(content_items)
                QApplication.postEvent(self, event)
                logger.info("收藏内容更新事件发送成功")
            except Exception as e:
                traceback.print_exc()
                logger.error(f"获取收藏内容失败：{str(e)}")
                
                # 在主线程中显示错误
                def show_error():
                    try:
                        self.show_notification(f"获取收藏内容失败：{str(e)}", "error")
                        self.status_label.setText("就绪")
                        self.update_content_list([])
                    except Exception as e:
                        traceback.print_exc()
                        logger.error(f"错误处理失败：{str(e)}")
                
                # 使用QTimer在主线程中显示错误
                QTimer.singleShot(0, show_error)
        
        # 启动线程
        logger.info("启动获取收藏内容线程")
        thread = threading.Thread(target=get_folder_content)
        thread.daemon = True
        thread.start()
        logger.info("线程已启动")
    
    def update_content_ui(self, content_items):
        logger = logging.getLogger(__name__)
        try:
            logger.info("开始更新收藏内容UI")
            logger.info(f"接收到的内容数量：{len(content_items)}")
            
            # 更新内容列表
            self.update_content_list(content_items)
            
            # 更新状态标签
            self.status_label.setText(f"收藏内容获取成功 - 共 {len(content_items)} 个收藏内容")
            
            # 强制刷新UI
            self.content_list.repaint()
            self.content_list.update()
            
            # 强制处理所有待处理的事件
            QApplication.processEvents()
            QApplication.processEvents()
            
            logger.info("收藏内容UI更新完成")
        except Exception as e:
            traceback.print_exc()
            logger.error(f"UI更新失败：{str(e)}")

    def create_favorite_card(self, item, index):
        widget = QWidget()
        widget.setFixedSize(190, 180)
        widget.setObjectName(f"favorite_card_{index}")
        widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 8px;
                border: 2px solid transparent;
            }
            QWidget[selected="true"] {
                border: 2px solid #3b82f6;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(8)
        
        # 封面容器（带圆角和时长标签）
        cover_container = QWidget()
        cover_container.setFixedSize(186, 103)
        cover_container.setStyleSheet("""
            QWidget {
                background-color: #f1f5f9;
            }
        """)
        cover_layout = QVBoxLayout(cover_container)
        cover_layout.setContentsMargins(0, 0, 0, 0)
        cover_layout.setSpacing(0)
        
        # 封面图片
        cover_label = QLabel()
        cover_label.setFixedSize(186, 103)
        cover_label.setStyleSheet("border: none;")
        cover_label.setAlignment(Qt.AlignCenter)
        cover_label.setText("")
        cover_layout.addWidget(cover_label)
        
        # 添加到布局，居中显示
        layout.addWidget(cover_container, alignment=Qt.AlignCenter)
        
        # 时长标签（右下角）
        duration = item.get('duration', 0)
        minutes = duration // 60
        seconds = duration % 60
        duration_str = f"{minutes}:{seconds:02d}"
        
        duration_label = QLabel(duration_str)
        duration_label.setFixedSize(46, 18)
        duration_label.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                font-size: 11px;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        duration_label.setAlignment(Qt.AlignCenter)
        
        # 将时长标签放在封面右下角
        duration_label.setParent(cover_container)
        duration_label.move(134, 81)
        
        # 加载封面图片
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
                        scaled_pixmap = pixmap.scaled(186, 103, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                        cover_label.setPixmap(scaled_pixmap)
                        cover_label.setStyleSheet("border: none;")
                    else:
                        cover_label.setText("加载失败")
                except Exception:
                    pass
            
            loader = CoverLoader(cover_url)
            loader.signals.finished.connect(on_cover_loaded)
            loader.start()
            
            # 保存线程引用
            self.cover_loaders.append(loader)
        
        # 标题区域
        title = item.get('title', '未知视频')
        title_label = QLabel(title)
        title_label.setFixedSize(186, 48)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                font-weight: 500;
                color: #1f2937;
                line-height: 1.4;
                background: transparent;
                padding: 0 4px;
            }
        """)
        title_label.setWordWrap(True)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        layout.addWidget(title_label, alignment=Qt.AlignCenter)
        
        # UP主
        up_name = item.get('up_name', '未知UP主')
        up_label = QLabel(up_name)
        up_label.setFixedSize(186, 16)
        up_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #6b7280;
                background: transparent;
                padding: 0 4px;
            }
        """)
        up_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(up_label, alignment=Qt.AlignCenter)
        
        return widget
    
    def update_content_list(self, items):
        logger = logging.getLogger(__name__)
        
        # 确保content_list存在
        if not hasattr(self, 'content_list'):
            logger.error("content_list不存在")
            return
        
        # 清空列表
        self.content_list.clear()
        
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
                list_item.setSizeHint(QSize(190, 180))
                list_item.setData(Qt.UserRole, item)
                
                # 添加到列表
                self.content_list.addItem(list_item)
                self.content_list.setItemWidget(list_item, item_widget)
                
                added_count += 1
                logger.info(f"添加收藏内容 {i+1}/{len(items)}：{item.get('title', '未知视频')}")
            
            # 启用解析按钮
            if hasattr(self, 'parse_favorite_btn'):
                self.parse_favorite_btn.setEnabled(added_count > 0)
            logger.info(f"收藏内容列表更新完成，共添加 {added_count} 个项目")
        
        # 强制刷新UI
        logger.info("强制刷新收藏内容列表")
        
        # 强制刷新
        self.content_list.repaint()
        self.content_list.update()
        
        # 强制重新计算布局
        if hasattr(self.content_list, 'parent'):
            parent_widget = self.content_list.parent()
            if parent_widget:
                parent_widget.repaint()
                parent_widget.update()
        
        # 强制处理所有待处理的事件
        QApplication.processEvents()
        QApplication.processEvents()  # 再次调用确保刷新
        QApplication.processEvents()  # 第三次调用确保所有事件都被处理
        
        # 再次检查列表状态
        logger.info(f"收藏内容列表最终状态：{self.content_list.count()} 个项目")
        
        logger.info("收藏内容列表UI更新完成")
    
    def on_tab_changed(self, index):
        logger = logging.getLogger(__name__)
        logger.info(f"标签页切换到索引：{index}")
        
        # 当切换到收藏标签页时，自动刷新收藏夹列表
        if index == 2:  # 收藏夹标签页的索引
            logger.info("切换到收藏夹标签页，开始刷新收藏夹列表")
            self.refresh_folders()
    
    def on_content_clicked(self, item):
        logger = logging.getLogger(__name__)
        logger.info("点击收藏内容")
        
        # 启用解析按钮
        if hasattr(self, 'parse_favorite_btn'):
            self.parse_favorite_btn.setEnabled(True)
        
        # 更新所有卡片的选中状态样式
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
    
    def check_cookie_validity(self):
        
        QTimer.singleShot(0, lambda: self.user_info_label.setText("未登录"))
        QTimer.singleShot(0, lambda: self.vip_label.setText("× 未登录"))
        QTimer.singleShot(0, lambda: self.vip_label.setStyleSheet("color: #6b7280;"))
        QTimer.singleShot(0, self.update_login_info_display)
        
        if hasattr(self, 'parser') and self.parser:
            if self.parser.cookies:
                
                import threading
                def verify_cookie_in_thread():
                    try:
                        success, msg = self.parser.verify_cookie()
                        if success:
                            
                            QTimer.singleShot(0, self.hide_cookie_ui)
                            
                            user_info = self.parser.get_user_info()
                            QTimer.singleShot(0, lambda: self.update_user_info(user_info))
                        else:
                            
                            QTimer.singleShot(0, self.show_cookie_ui)
                            
                            QTimer.singleShot(0, lambda: self.user_info_label.setText("未登录"))
                            QTimer.singleShot(0, lambda: self.vip_label.setText("× 未登录"))
                            QTimer.singleShot(0, lambda: self.vip_label.setStyleSheet("color: #6b7280;"))
                    except Exception as e:
                        logger.error(f"检查cookie有效性失败：{str(e)}")
                        
                        QTimer.singleShot(0, self.show_cookie_ui)
                        
                        QTimer.singleShot(0, lambda: self.user_info_label.setText("未登录"))
                        QTimer.singleShot(0, lambda: self.vip_label.setText("× 未登录"))
                        QTimer.singleShot(0, lambda: self.vip_label.setStyleSheet("color: #6b7280;"))
                
                thread = threading.Thread(target=verify_cookie_in_thread)
                thread.daemon = True
                thread.start()
            else:
                
                QTimer.singleShot(0, self.show_cookie_ui)
    
    def hide_cookie_ui(self):
        
        self.showMaximized()
        
        
        if not hasattr(self, 'logout_btn'):
            self.logout_btn = QPushButton("退出登录")
            self.logout_btn.setStyleSheet("background-color: #f56c6c;")
            self.logout_btn.setMinimumHeight(32)
            self.logout_btn.setMinimumWidth(90)
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
        
        
        self.repaint()
        QApplication.processEvents()
        
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
        
        
        self.repaint()
        QApplication.processEvents()
        
        self.showMaximized()
    
    def adjust_layout_space(self):
        
        pass
    
    def restore_layout_space(self):
        
        pass
    
    def on_logout(self):
        
        dialog = QDialog(self)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        dialog.setWindowTitle("确认退出登录")
        dialog.setMinimumSize(350, 200)
        
        
        custom_style = BASE_STYLE + """
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
        """
        dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("确认退出登录")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        
        info_label = QLabel("确定要退出登录吗？")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setStyleSheet("font-size: 16px; color: #333;")
        content_layout.addWidget(info_label)
        
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)
        
        yes_btn = QPushButton("确定")
        yes_btn.setStyleSheet("background-color: #409eff; color: white; font-weight: 500; padding: 10px 24px;")
        no_btn = QPushButton("取消")
        no_btn.setStyleSheet("background-color: #f56c6c; color: white; font-weight: 500; padding: 10px 24px;")
        
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
                
                if os.path.exists(self.cookie_file):
                    os.remove(self.cookie_file)
                
                
                if hasattr(self, 'parser') and self.parser:
                    self.parser.cookies = {}
                    self.parser.session.cookies.clear()
                    self.parser.csrf_token = ""
                
                self.showMaximized()
                
                
                self.show_cookie_ui()
                
                
                self.user_info_label.setText("未登录")
                self.vip_label.setText("× 未登录")
                self.vip_label.setStyleSheet("color: #6b7280;")
                
                
                self.update_login_info_display()
                
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
        print(f"on_cookie_verified方法被调用，success: {success}, msg: {msg}")
        
        if hasattr(self, 'login_dialog') and self.login_dialog:
            print("关闭登录对话框...")
            self.login_dialog.accept()
            print("登录对话框已关闭")
        else:
            print("未找到登录对话框实例")
        
        if success:
            try:
                
                print("显示成功消息...")
                self.show_success_message(msg)
                print("成功消息已显示")
                print("发出load_user_info信号...")
                self.signal_emitter.load_user_info.emit()
                print("load_user_info信号已发出")
                
                print("检查cookie有效性...")
                self.check_cookie_validity()
                print("cookie有效性检查完成")
                
                self.showMaximized()
            except Exception as e:
                logger.error(f"保存Cookie失败：{str(e)}")
                self.show_notification(f"保存Cookie失败：{str(e)}", "error")
                print(f"处理成功情况时发生异常：{str(e)}")
        else:
            print("显示验证失败消息...")
            self.show_notification(f"验证失败：{msg}", "error")
            print("验证失败消息已显示")
        
        self.showMaximized()
        print("on_cookie_verified方法执行完成")
    
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
                
                # 更新进度
                def progress_callback(progress, message):
                    print(f"收到进度回调: {progress}%, 消息: {message}")
                    try:
                        if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                            self.parse_progress_window.update_progress(progress, message)
                        else:
                            print("解析进度窗口不存在")
                    except Exception as e:
                        print(f"进度回调出错: {str(e)}")
                
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
                        space_info = self.parser.get_space_info(media_id)
                        if not space_info.get("success"):
                            error_msg = space_info.get("error", "获取UP主信息失败")
                            if "访问权限不足" in error_msg:
                                error_msg = "该UP主主页可能需要登录或权限访问，请尝试登录后再解析"
                            self.signal_emitter.parse_finished.emit({"success": False, "error": error_msg})
                            return
                        
                        videos_info = self.parser.get_space_videos(media_id)
                        if not videos_info.get("success"):
                            error_msg = videos_info.get("error", "获取作品列表失败")
                            if "访问权限不足" in error_msg:
                                error_msg = "该UP主作品可能需要登录或权限访问，请尝试登录后再解析"
                            self.signal_emitter.parse_finished.emit({"success": False, "error": error_msg})
                            return
                        
                        # 发送信号，在主线程中显示作品列表窗口
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
        self.cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")
        
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
            # 关闭解析进度窗口
            if hasattr(self, 'parse_progress_window') and self.parse_progress_window:
                QTimer.singleShot(0, lambda: self.parse_progress_window.close())
            
            # 弹出作品列表窗口
            
            class ImageLoader(QThread):
                finished = pyqtSignal(QLabel, QPixmap)
                
                def __init__(self, url, label):
                    super().__init__()
                    self.url = url
                    self.label = label
                
                def run(self):
                    try:
                        response = requests.get(self.url, timeout=3)
                        image = QImage()
                        image.loadFromData(response.content)
                        pixmap = QPixmap.fromImage(image)
                        self.finished.emit(self.label, pixmap)
                    except:
                        pass
            
            class SpaceVideosDialog(QDialog):
                def __init__(self, parent, space_info, videos):
                    super().__init__(parent)
                    self.setWindowTitle(f"{space_info['name']} 的作品列表")
                    self.setGeometry(200, 200, 800, 600)
                    self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
                    self.videos = videos  # 保存视频列表
                    self.loaders = []  # 保存所有加载线程
                    
                    # 标题栏
                    title_bar = QWidget()
                    title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
                    title_layout = QHBoxLayout(title_bar)
                    title_layout.setContentsMargins(16, 0, 12, 0)
                    title_layout.setSpacing(10)
                    
                    title_label = QLabel(f"{space_info['name']} 的作品列表")
                    title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
                    title_layout.addWidget(title_label, stretch=1)
                    
                    close_btn = QPushButton("×")
                    close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
                    close_btn.setToolTip("关闭")
                    close_btn.clicked.connect(self.reject)
                    title_layout.addWidget(close_btn)
                    
                    # 内容区域
                    content_widget = QWidget()
                    content_layout = QVBoxLayout(content_widget)
                    content_layout.setContentsMargins(20, 20, 20, 20)
                    content_layout.setSpacing(15)
                    
                    # UP 主信息
                    info_widget = QWidget()
                    info_layout = QHBoxLayout(info_widget)
                    info_layout.setSpacing(15)
                    
                    # 头像
                    avatar_label = QLabel()
                    avatar_label.setText("加载中...")
                    avatar_label.setFixedSize(80, 80)
                    avatar_label.setStyleSheet("background-color: #e2e8f0; border-radius: 40px; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;")
                    
                    # 基本信息
                    info_detail = QWidget()
                    info_detail_layout = QVBoxLayout(info_detail)
                    info_detail_layout.setContentsMargins(0, 0, 0, 0)
                    info_detail_layout.setSpacing(5)
                    
                    name_label = QLabel(f"{space_info['name']}")
                    name_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #1e293b;")
                    
                    sign_label = QLabel(f"签名: {space_info['sign'] if space_info['sign'] else '无'}")
                    sign_label.setStyleSheet("font-size: 14px; color: #64748b;")
                    sign_label.setWordWrap(True)
                    
                    level_label = QLabel(f"等级: {space_info['level']}")
                    level_label.setStyleSheet("font-size: 14px; color: #64748b;")
                    
                    info_detail_layout.addWidget(name_label)
                    info_detail_layout.addWidget(sign_label)
                    info_detail_layout.addWidget(level_label)
                    
                    info_layout.addWidget(avatar_label)
                    info_layout.addWidget(info_detail, stretch=1)
                    
                    content_layout.addWidget(info_widget)
                    
                    # 作品列表
                    videos_label = QLabel(f"共 {len(videos)} 个作品")
                    videos_label.setStyleSheet("font-size: 16px; font-weight: 500; color: #1e293b;")
                    content_layout.addWidget(videos_label)
                    
                    self.videos_list = QListWidget()
                    self.videos_list.setSelectionMode(QListWidget.MultiSelection)
                    
                    for video in videos:
                        item = QListWidgetItem()
                        widget = QWidget()
                        layout = QHBoxLayout(widget)
                        layout.setContentsMargins(12, 12, 12, 12)
                        layout.setSpacing(12)
                        
                        # 封面
                        cover_label = QLabel()
                        cover_label.setText("加载中...")
                        cover_label.setFixedSize(120, 68)
                        cover_label.setStyleSheet("background-color: #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 12px; color: #64748b;")
                        
                        # 视频信息
                        info_widget = QWidget()
                        info_layout = QVBoxLayout(info_widget)
                        info_layout.setContentsMargins(0, 0, 0, 0)
                        info_layout.setSpacing(5)
                        
                        title_label = QLabel(video['title'])
                        title_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #1e293b;")
                        title_label.setWordWrap(True)
                        
                        stats_label = QLabel(f"播放: {video['play']} | 弹幕: {video['video_review']} | 收藏: {video['favorites']}")
                        stats_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
                        
                        time_label = QLabel(f"时长: {video['length']}")
                        time_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
                        
                        info_layout.addWidget(title_label)
                        info_layout.addWidget(stats_label)
                        info_layout.addWidget(time_label)
                        
                        layout.addWidget(cover_label)
                        layout.addWidget(info_widget, stretch=1)
                        
                        item.setSizeHint(widget.sizeHint())
                        self.videos_list.addItem(item)
                        self.videos_list.setItemWidget(item, widget)
                        
                        # 异步加载封面
                        if video.get('pic'):
                            loader = ImageLoader(video['pic'], cover_label)
                            loader.finished.connect(self.on_image_loaded)
                            self.loaders.append(loader)
                            loader.start()
                    
                    content_layout.addWidget(self.videos_list, stretch=1)
                    
                    # 完全模式选项
                    full_mode_layout = QHBoxLayout()
                    full_mode_layout.setSpacing(12)
                    
                    self.full_mode_checkbox = QCheckBox("完全模式（自动下载全部视频）")
                    self.full_mode_checkbox.setStyleSheet("font-size: 13px; color: #374151;")
                    self.full_mode_checkbox.stateChanged.connect(self.on_full_mode_changed)
                    full_mode_layout.addWidget(self.full_mode_checkbox)
                    
                    # 清晰度选择（完全模式下显示）
                    self.full_mode_quality_label = QLabel("清晰度：")
                    self.full_mode_quality_label.setStyleSheet("font-size: 13px; color: #374151;")
                    self.full_mode_quality_label.setVisible(False)
                    full_mode_layout.addWidget(self.full_mode_quality_label)
                    
                    self.full_mode_quality_combo = QComboBox()
                    self.full_mode_quality_combo.setMinimumHeight(32)
                    self.full_mode_quality_combo.setStyleSheet("""
                        QComboBox {
                            border: 1px solid #d1d5db;
                            border-radius: 6px;
                            padding: 4px 8px;
                            font-size: 13px;
                            min-width: 120px;
                        }
                        QComboBox::drop-down {
                            border: none;
                            width: 24px;
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
                    """)
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
                    
                    full_mode_layout.addStretch(1)
                    
                    content_layout.addLayout(full_mode_layout)
                    
                    # 按钮区域
                    btn_layout = QHBoxLayout()
                    btn_layout.setSpacing(12)
                    
                    select_all_btn = QPushButton("全选")
                    select_all_btn.setMinimumHeight(36)
                    select_all_btn.setStyleSheet("padding: 0 24px; border: 1px solid #409eff; border-radius: 6px; font-size: 14px; background-color: white; color: #409eff;")
                    select_all_btn.clicked.connect(self.select_all_videos)
                    
                    cancel_btn = QPushButton("取消")
                    cancel_btn.setMinimumHeight(36)
                    cancel_btn.setStyleSheet("padding: 0 24px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; background-color: white; color: #374151;")
                    cancel_btn.clicked.connect(self.reject)
                    
                    self.confirm_btn = QPushButton("解析选中 (0)")
                    self.confirm_btn.setMinimumHeight(36)
                    self.confirm_btn.setStyleSheet("padding: 0 24px; border: none; border-radius: 6px; font-size: 14px; background-color: #409eff; color: white;")
                    self.confirm_btn.clicked.connect(self.accept)
                    
                    # 连接选择变化信号
                    self.videos_list.itemSelectionChanged.connect(self.update_confirm_button)
                    
                    btn_layout.addWidget(select_all_btn)
                    btn_layout.addStretch(1)
                    btn_layout.addWidget(cancel_btn)
                    btn_layout.addWidget(self.confirm_btn)
                    
                    content_layout.addLayout(btn_layout)
                    
                    # 主布局
                    main_layout = QVBoxLayout(self)
                    main_layout.setContentsMargins(0, 0, 0, 0)
                    main_layout.setSpacing(0)
                    main_layout.addWidget(title_bar)
                    main_layout.addWidget(content_widget)
                    
                    # 异步加载头像
                    if space_info.get('face'):
                        loader = ImageLoader(space_info['face'], avatar_label)
                        loader.finished.connect(self.on_avatar_loaded)
                        self.loaders.append(loader)
                        loader.start()
                
                def on_image_loaded(self, label, pixmap):
                    # 找到并移除完成的线程
                    sender = self.sender()
                    if sender in self.loaders:
                        self.loaders.remove(sender)
                    if pixmap:
                        pixmap = pixmap.scaled(120, 68, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        label.setPixmap(pixmap)
                        label.setText("")
                        label.setStyleSheet("")
                
                def on_avatar_loaded(self, label, pixmap):
                    # 找到并移除完成的线程
                    sender = self.sender()
                    if sender in self.loaders:
                        self.loaders.remove(sender)
                    if pixmap:
                        pixmap = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        label.setPixmap(pixmap)
                        label.setText("")
                        label.setStyleSheet("")
                
                def closeEvent(self, event):
                    for loader in self.loaders:
                        if loader.isRunning():
                            loader.quit()
                            loader.wait()
                    event.accept()
                
                def select_all_videos(self):
                    for i in range(self.videos_list.count()):
                        item = self.videos_list.item(i)
                        item.setSelected(True)
                
                def update_confirm_button(self):
                    selected_count = len(self.videos_list.selectedItems())
                    self.confirm_btn.setText(f"解析选中 ({selected_count})")
                
                def get_selected_videos(self):
                    selected_items = self.videos_list.selectedItems()
                    selected_videos = []
                    for item in selected_items:
                        index = self.videos_list.row(item)
                        selected_videos.append(self.videos[index])
                    return selected_videos
                
                def on_full_mode_changed(self, state):
                    if state == Qt.Checked:
                        # 勾选完全模式时，自动全选所有视频
                        self.select_all_videos()
                        self.confirm_btn.setText("下载全部")
                        # 显示清晰度选择
                        self.full_mode_quality_label.setVisible(True)
                        self.full_mode_quality_combo.setVisible(True)
                    else:
                        self.update_confirm_button()
                        # 隐藏清晰度选择
                        self.full_mode_quality_label.setVisible(False)
                        self.full_mode_quality_combo.setVisible(False)
                
                def is_full_mode(self):
                    return self.full_mode_checkbox.isChecked()
                
                def get_all_videos(self):
                    return self.videos
                
                def get_selected_quality(self):
                    return self.full_mode_quality_combo.currentData()
            
            dialog = SpaceVideosDialog(self, space_info, videos)
            if dialog.exec_() == QDialog.Accepted:
                # 检查是否启用了完全模式
                if dialog.is_full_mode():
                    # 完全模式：直接下载所有视频
                    all_videos = dialog.get_all_videos()
                    selected_quality = dialog.get_selected_quality()
                    if all_videos and len(all_videos) > 0:
                        self.show_notification(f"完全模式：开始下载 {len(all_videos)} 个视频", "info")
                        # 直接开始下载所有视频，使用选中的清晰度
                        self.download_space_videos(all_videos, space_info, selected_quality)
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
        except Exception as e:
            print(f"on_show_space_videos错误：{str(e)}")
            traceback.print_exc()
            self.signal_emitter.parse_finished.emit({"success": False, "error": f"显示作品列表失败：{str(e)}"})
    
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
                self.cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")
            else:
                print("错误：cover_label控件不存在")
            
            if hasattr(self, 'status_label'):
                self.status_label.setText(f"解析失败：{error_msg[:30]}")
            else:
                print("错误：status_label控件不存在")
            
            # 显示错误通知
            self.show_notification(f"视频解析失败了：{error_msg}", "error")
            
            # 强制更新UI
            self.repaint()
            QApplication.processEvents()
            
            print("=== 错误状态UI更新完成 ===")
        except Exception as e:
            print(f"update_ui_error错误：{str(e)}")
            traceback.print_exc()
    
    def download_space_videos(self, videos, space_info, selected_quality=None):
        try:
            # 获取保存路径
            save_path = self.path_edit.text().strip() if hasattr(self, 'path_edit') else ""
            if not save_path:
                save_path = self.config.get_app_setting("default_download_path", "")
            if not save_path:
                save_path = os.path.join(os.path.expanduser("~"), "Downloads", "Bilibili")
            os.makedirs(save_path, exist_ok=True)
            
            # 获取视频格式设置
            video_format = self.config.get_app_setting("video_output_format", "mp4")
            audio_format = self.config.get_app_setting("audio_output_format", "mp3")
            
            # 获取自动下载设置
            auto_download_danmaku = self.config.get_app_setting("auto_download_danmaku", False)
            auto_download_cover = self.config.get_app_setting("auto_download_cover", True)
            
            # 获取弹幕设置
            download_danmaku = auto_download_danmaku
            if hasattr(self, 'danmaku_checkbox'):
                download_danmaku = self.danmaku_checkbox.isChecked()
            danmaku_format = self.danmaku_format_combo.currentText() if hasattr(self, 'danmaku_format_combo') else 'XML'
            
            # 获取默认清晰度（如果未指定则使用配置中的默认值）
            default_qn = selected_quality if selected_quality else self.config.get_app_setting("default_quality", 80)
            
            # 创建批量下载窗口（只创建一次）
            batch_window = None
            for window in self.batch_windows.values():
                if isinstance(window, BatchDownloadWindow):
                    batch_window = window
                    break
            
            if not batch_window:
                # 创建新的批量下载窗口
                batch_window = BatchDownloadWindow({"title": f"{space_info['name']} - 空间视频", "is_bangumi": False, "is_cheese": False}, 0, self.download_manager, self.parser)
                batch_window.cancel_all.connect(self.on_cancel_download)
                batch_window.show()
                batch_window.raise_()
                batch_window.activateWindow()
            
            # 为每个视频创建下载任务
            success_count = 0
            for i, video in enumerate(videos):
                try:
                    bvid = video.get('bvid')
                    if not bvid:
                        continue
                    
                    # 解析视频获取详细信息
                    media_info = self.parser.parse_media("video", bvid, self.tv_mode_checkbox.isChecked() if hasattr(self, 'tv_mode_checkbox') else False)
                    
                    if not media_info.get('success'):
                        logger.warning(f"完全模式：解析视频 {bvid} 失败，跳过")
                        continue
                    
                    # 获取视频的分辨率选项
                    quality_options = media_info.get('quality_options', [])
                    if quality_options:
                        # 使用选中的清晰度，如果没有则使用第一个可用清晰度
                        selected_qn = default_qn
                        qn_available = [q['qn'] for q in quality_options]
                        if selected_qn not in qn_available:
                            selected_qn = qn_available[0] if qn_available else 80
                    else:
                        selected_qn = default_qn
                    
                    # 创建下载任务
                    task_id = str(int(time.time() * 1000) + i)
                    
                    # 获取视频的集数信息
                    episodes = []
                    if media_info.get('collection'):
                        episodes = media_info.get('collection', [])
                    elif media_info.get('episodes'):
                        episodes = media_info.get('episodes', [])
                    else:
                        # 单集视频
                        episodes = [{
                            'page': 1,
                            'title': media_info.get('title', ''),
                            'duration': media_info.get('duration', ''),
                            'cid': media_info.get('cid', ''),
                            'bvid': bvid
                        }]
                    
                    download_params = {
                        "url": f"https://www.bilibili.com/video/{bvid}",
                        "video_info": media_info,
                        "qn": selected_qn,
                        "save_path": save_path,
                        "episodes": episodes,
                        "resume_download": True,
                        "task_id": task_id,
                        "download_danmaku": download_danmaku,
                        "danmaku_format": danmaku_format,
                        "download_video": True,
                        "video_format": video_format,
                        "audio_format": audio_format
                    }
                    
                    # 添加进度条到批量下载窗口
                    for j, ep in enumerate(episodes):
                        ep_name = f"{video.get('title', bvid)} - 第{ep.get('page', j+1)}集"
                        ep_tooltip = ep.get('title', '')
                        batch_window.add_episode_progress(ep_name, ep_tooltip, task_id, j)
                    
                    # 开始下载
                    if self.download_manager:
                        self.download_manager.start_download(download_params)
                        success_count += 1
                        logger.info(f"完全模式：已添加下载任务 {video.get('title', bvid)}")
                    
                except Exception as e:
                    logger.error(f"完全模式：处理视频 {video.get('bvid', 'unknown')} 时出错：{str(e)}")
                    continue
            
            # 保存批量下载窗口引用
            if batch_window:
                self.batch_windows[task_id] = batch_window
                batch_window.window_closed.connect(lambda tid=task_id: self.on_batch_window_closed(tid))
            
            # 显示完成通知
            self.show_notification(f"完全模式：已成功添加 {success_count}/{len(videos)} 个视频到下载队列", "success")
            
        except Exception as e:
            logger.error(f"完全模式下载出错：{str(e)}")
            traceback.print_exc()
            self.show_notification(f"完全模式下载失败：{str(e)}", "error")
    
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
                    finished = pyqtSignal(QPixmap)
                    
                    def __init__(self, url):
                        super().__init__()
                        self.url = url
                    
                    def run(self):
                        try:
                            response = requests.get(self.url, timeout=10)
                            response.raise_for_status()
                            pixmap = QPixmap()
                            pixmap.loadFromData(response.content)
                            self.finished.emit(pixmap)
                        except:
                            self.finished.emit(QPixmap())
                
                loader = CoverLoader(cover_url)
                if not hasattr(self, 'cover_loaders'):
                    self.cover_loaders = []
                self.cover_loaders.append(loader)  
                
                def on_cover_loaded(pixmap):
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(180, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        cover_label.setPixmap(scaled_pixmap)
                        cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px;")
                    else:
                        cover_label.setText("加载失败")
                        cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")
                    
                    if loader in self.cover_loaders:
                        self.cover_loaders.remove(loader)
                
                loader.finished.connect(on_cover_loaded)
                loader.start()
            else:
                print("无封面")
                cover_label.setText("无封面")
                cover_label.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")
            
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
            
            # 启用下载按钮（无论是否选择集数，因为可以只下载弹幕）
            download_btn.setEnabled(True)
            cancel_btn.setEnabled(True)
            select_episode_btn.setEnabled(True)
            
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
                                        self.danmaku_count_label.repaint()
                                        QApplication.processEvents()
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
                                # 保存弹幕数据
                                self.current_danmaku_data = danmaku_video_info
                                # 启用选择弹幕按钮
                                self.select_danmaku_btn.setEnabled(True)
                                # 直接在主线程中更新UI
                                # 使用QMetaObject.invokeMethod确保在主线程中执行
                                def update_danmaku_count():
                                    try:
                                        print(f"更新弹幕数量UI：{count}条")
                                        self.danmaku_count_label.setText(f"{count}条")
                                        self.danmaku_count_label.repaint()
                                        QApplication.processEvents()
                                        print("弹幕数量UI更新成功")
                                    except Exception as e:
                                        print(f"更新弹幕数量UI失败：{str(e)}")
                                # 确保在主线程中执行
                                QMetaObject.invokeMethod(self.danmaku_count_label, "setText", 
                                                      Qt.QueuedConnection, 
                                                      Q_ARG(str, f"{count}条"))
                                # 同时使用QTimer确保更新
                                QTimer.singleShot(0, update_danmaku_count)
                            else:
                                print("弹幕获取失败")
                                def update_danmaku_error():
                                    try:
                                        print("更新弹幕错误UI：获取失败")
                                        self.danmaku_count_label.setText("获取失败")
                                        self.danmaku_count_label.repaint()
                                        QApplication.processEvents()
                                        print("弹幕错误UI更新成功")
                                    except Exception as e:
                                        print(f"更新弹幕错误UI失败：{str(e)}")
                                QTimer.singleShot(0, update_danmaku_error)
                        except Exception as e:
                            print(f"获取弹幕信息失败：{str(e)}")
                            traceback.print_exc()
                            def update_danmaku_error():
                                try:
                                    print("更新弹幕错误UI：获取失败")
                                    self.danmaku_count_label.setText("获取失败")
                                    self.danmaku_count_label.repaint()
                                    QApplication.processEvents()
                                    print("弹幕错误UI更新成功")
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
            
            # 强制更新UI
            print("强制更新UI")
            self.repaint()
            QApplication.processEvents()
            
            # 输出解析文本框的文字
            if hasattr(self, 'status_label'):
                print(f"解析文本框文字：{self.status_label.text()}")
            
            # 输出弹幕数量label
            if hasattr(self, 'danmaku_count_label'):
                print(f"弹幕数量label：{self.danmaku_count_label.text()}")
            
            print("=== UI更新完成 ===")
        except Exception as e:
            print(f"update_ui错误：{str(e)}")
            traceback.print_exc()

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
            "audio_format": self.config.get_app_setting("audio_output_format", "mp3")
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
            "audio_format": self.config.get_app_setting("audio_output_format", "mp3")
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
        if user_info.get("success"):
            self.user_info_label.setText("已登录")
            if user_info.get("is_vip"):
                self.vip_label.setText("√ 会员")
                self.vip_label.setStyleSheet("color: #faad14;")
            else:
                self.vip_label.setText("× 普通用户")
                self.vip_label.setStyleSheet("color: #6b7280;")
            
            if hasattr(self, 'login_info_label'):
                username = user_info.get("msg", "用户")
                self.login_info_label.setText(f"登录用户：{username}")
                self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px;")
                self.login_info_label.setCursor(QCursor(Qt.ArrowCursor))
                self.login_info_label.mousePressEvent = None
            
            # 更新分辨率下拉框 - 登录用户显示更多选项
            self._update_resolution_combo(is_login=True, is_vip=user_info.get("is_vip", False))
        else:
            self.user_info_label.setText("未登录")
            self.vip_label.setText("× 未登录")
            self.vip_label.setStyleSheet("color: #6b7280;")
            
            if hasattr(self, 'login_info_label'):
                self.login_info_label.setText("如果想要解析会员内容请登录")
                self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px;")
                self.login_info_label.setCursor(QCursor(Qt.PointingHandCursor))
                self.login_info_label.mousePressEvent = self.on_login_click
            
            # 更新分辨率下拉框 - 未登录只显示低分辨率
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
                    user_info = self.parser.get_user_info()
                    if user_info.get("success"):
                        # 只显示用户名，不显示其他信息
                        username = user_info.get("uname", "用户")
                        self.login_info_label.setText(username)
                        self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px;")
                        
                        # 加载头像
                        avatar_url = user_info.get("face", "")
                        print(f"从user_info获取头像URL：{avatar_url}")
                        if avatar_url:
                            self.load_avatar(avatar_url)
                        else:
                            # 如果user_info中没有头像，尝试从user_detail获取
                            try:
                                user_detail = self.parser.get_user_detail()
                                print(f"获取user_detail结果：{user_detail}")
                                if user_detail.get("success"):
                                    avatar_url = user_detail.get("face", "")
                                    print(f"从user_detail获取头像URL：{avatar_url}")
                                    if avatar_url:
                                        self.load_avatar(avatar_url)
                            except Exception as e:
                                print(f"获取用户详情失败：{e}")
                        
                        # 设置点击事件
                        self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                        # 确保点击事件正确绑定
                        def handle_click(event):
                            print("点击事件被触发")
                            self.on_user_info_click(event)
                        self.login_info_widget.mousePressEvent = handle_click
                        print("点击事件绑定成功")
                        
                        if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                            self.user_info_label.setText("已登录")
                            if user_info.get("is_vip"):
                                self.vip_label.setText("√ 会员")
                                self.vip_label.setStyleSheet("color: #faad14;")
                            else:
                                self.vip_label.setText("× 普通用户")
                                self.vip_label.setStyleSheet("color: #6b7280;")
                        
                        # 显示退出登录按钮
                        self.hide_cookie_ui()
                    else:
                        
                        self.login_info_label.setText("如果想要解析会员内容请登录")
                        self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px;")
                        # 使用默认头像
                        default_avatar = "https://i2.hdslb.com/bfs/face/member/noface.jpg"
                        self.load_avatar(default_avatar)
                        
                        # 设置点击事件
                        self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                        self.login_info_widget.mousePressEvent = self.on_login_click
                        
                        if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                            self.user_info_label.setText("未登录")
                            self.vip_label.setText("× 未登录")
                            self.vip_label.setStyleSheet("color: #6b7280;")
                        
                        # 隐藏退出登录按钮
                        self.show_cookie_ui()
                except Exception as e:
                    
                    self.login_info_label.setText("如果想要解析会员内容请登录")
                    self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px;")
                    # 使用默认头像
                    default_avatar = "https://i2.hdslb.com/bfs/face/member/noface.jpg"
                    self.load_avatar(default_avatar)
                    
                    # 设置点击事件
                    self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                    self.login_info_widget.mousePressEvent = self.on_login_click
                    
                    if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                        self.user_info_label.setText("未登录")
                        self.vip_label.setText("× 未登录")
                        self.vip_label.setStyleSheet("color: #6b7280;")
                    
                    # 隐藏退出登录按钮
                    self.show_cookie_ui()
            else:
                
                self.login_info_label.setText("如果想要解析会员内容请登录")
                self.login_info_label.setStyleSheet("color: #ffffff; font-size: 12px;")
                # 使用默认头像
                default_avatar = "https://i2.hdslb.com/bfs/face/member/noface.jpg"
                self.load_avatar(default_avatar)
                
                # 设置点击事件
                self.login_info_widget.setCursor(QCursor(Qt.PointingHandCursor))
                self.login_info_widget.mousePressEvent = self.on_login_click
                
                if hasattr(self, 'user_info_label') and hasattr(self, 'vip_label'):
                    self.user_info_label.setText("未登录")
                    self.vip_label.setText("× 未登录")
                    self.vip_label.setStyleSheet("color: #6b7280;")
                
                # 隐藏退出登录按钮
                self.show_cookie_ui()

    def load_avatar(self, avatar_url):
        print(f"开始加载头像，URL：{avatar_url}")
        try:
            from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest
            
            # 创建事件循环，确保网络请求在函数返回前完成
            loop = QEventLoop()
            
            def on_avatar_loaded(reply):
                try:
                    print(f"头像加载完成，错误码：{reply.error()}")
                    if reply.error() == 0:
                        data = reply.readAll()
                        print(f"获取到头像数据，大小：{len(data)}字节")
                        pixmap = QPixmap()
                        success = pixmap.loadFromData(data)
                        print(f"加载头像数据成功：{success}")
                        if success and not pixmap.isNull():
                            pixmap = pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            
                            path = QPainterPath()
                            path.addEllipse(0, 0, 24, 24)
                            
                            round_pixmap = QPixmap(24, 24)
                            round_pixmap.fill(Qt.transparent)
                            
                            painter = QPainter(round_pixmap)
                            painter.setClipPath(path)
                            painter.drawPixmap(0, 0, 24, 24, pixmap)
                            painter.end()
                            
                            self.avatar_label.setPixmap(round_pixmap)
                            self.avatar_label.setStyleSheet("border-radius: 12px;")
                            print("头像显示成功")
                        else:
                            print("头像数据无效")
                    else:
                        print(f"头像加载失败，错误：{reply.errorString()}")
                    reply.deleteLater()
                except Exception as e:
                    print(f"加载头像失败：{e}")
                finally:
                    # 退出事件循环
                    loop.quit()
            
            manager = QNetworkAccessManager()
            manager.finished.connect(on_avatar_loaded)
            request = QNetworkRequest(QUrl(avatar_url))
            # 添加请求头，模拟浏览器请求
            request.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36")
            request.setRawHeader(b"Referer", b"https://www.bilibili.com/")
            print("发送头像请求")
            manager.get(request)
            
            # 等待网络请求完成，最多等待5秒
            loop.exec_()
        except Exception as e:
            print(f"加载头像失败：{e}")
            # 如果网络请求失败，尝试使用requests库下载头像
            try:
                print("尝试使用requests库下载头像")
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                    "Referer": "https://www.bilibili.com/"
                }
                response = requests.get(avatar_url, headers=headers, timeout=5)
                if response.status_code == 200:
                    print(f"使用requests获取到头像数据，大小：{len(response.content)}字节")
                    pixmap = QPixmap()
                    success = pixmap.loadFromData(response.content)
                    print(f"加载头像数据成功：{success}")
                    if success and not pixmap.isNull():
                        pixmap = pixmap.scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        
                        path = QPainterPath()
                        path.addEllipse(0, 0, 24, 24)
                        
                        round_pixmap = QPixmap(24, 24)
                        round_pixmap.fill(Qt.transparent)
                        
                        painter = QPainter(round_pixmap)
                        painter.setClipPath(path)
                        painter.drawPixmap(0, 0, 24, 24, pixmap)
                        painter.end()
                        
                        self.avatar_label.setPixmap(round_pixmap)
                        self.avatar_label.setStyleSheet("border-radius: 12px;")
                        print("头像显示成功")
                    else:
                        print("头像数据无效")
                else:
                    print(f"requests下载头像失败，状态码：{response.status_code}")
            except Exception as e2:
                print(f"使用requests加载头像失败：{e2}")
    
    def update_hevc_status(self, supported):
        if supported:
            self.hevc_label.setText("√ 已支持HEVC（HDR/杜比视界）")
            self.hevc_label.setStyleSheet("color: #52c41a;")
        else:
            self.hevc_label.setText("× 未支持HEVC（需安装扩展）")
            self.hevc_label.setStyleSheet("color: #fa8c16;")
        
        self.hevc_btn.setEnabled(True)

    def update_hevc_progress(self, progress):
        self.main_progress.setValue(progress)
        self.status_label.setText(f"下载HEVC扩展：{progress}%")

    def on_hevc_install_finish(self, success, msg):
        self.main_progress.setValue(0)
        self.hevc_btn.setEnabled(not success)
        if success:
            self.show_notification(f"操作成功啦：{msg}", "success")
            self.signal_emitter.check_hevc.emit()
            self.status_label.setText("HEVC扩展安装成功")
        else:
            self.show_notification(f"操作失败了：{msg}", "error")
            self.status_label.setText("HEVC扩展安装失败")

    def update_download_progress(self, progress, status):
        
        if not hasattr(self, 'last_main_progress') or progress % 5 == 0 or progress == 100 or self.last_main_status != status:
            self.main_progress.setValue(progress)
            self.status_label.setText(status)
            
            self.last_main_progress = progress
            self.last_main_status = status

    def update_episode_progress(self, *args):
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
                    task_widget.setStyleSheet("background-color: #f0fdf4; border-radius: 8px; padding: 12px; margin-bottom: 8px;")
                    task_layout = QVBoxLayout(task_widget)
                    task_layout.setContentsMargins(8, 8, 8, 8)
                    task_layout.setSpacing(8)
                    
                    video_name = status.split(' - ')[0] if ' - ' in status else status
                    video_name_label = QLabel(video_name)
                    video_name_label.setStyleSheet("font-size: 14px; font-weight: 500; color: #166534;")
                    video_name_label.setMinimumHeight(24)
                    video_name_label.setMaximumWidth(380)
                    video_name_label.setToolTip(status)
                    video_name_label.setWordWrap(True)
                    
                    progress_bar = QProgressBar()
                    progress_bar.setRange(0, 100)
                    progress_bar.setMinimumHeight(14)
                    progress_bar.setStyleSheet("QProgressBar { border-radius: 6px; background-color: #dcfce7; } QProgressBar::chunk { border-radius: 6px; background-color: #22c55e; }")
                    
                    progress_text = QLabel(f"{int(progress)}%")
                    progress_text.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 500;")
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
        if len(args) == 4:
            task_id, ep_index, success, message = args
            
            # 主窗口显示通知
            if success:
                self.show_notification(f"视频下载完成：{message}", "success")
            else:
                self.show_notification(f"视频下载失败：{message}", "error")
            
            # 转发给其他窗口
            for window in self.batch_windows.values():
                if window and window.isVisible():
                    window.finish_episode(task_id, ep_index, success, message)
        elif len(args) == 3:
            index, success, message = args
            
            # 主窗口显示通知
            if success:
                self.show_notification(f"视频下载完成：{message}", "success")
            else:
                self.show_notification(f"视频下载失败：{message}", "error")
            
            # 转发给其他窗口
            for window in self.batch_windows.values():
                if window and window.isVisible():
                    window.finish_episode(index, success, message)
        
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

    
    

    def toggle_maximize(self):
        
        if not self.isMaximized():
            self.showMaximized()

    def custom_close(self):
        if hasattr(self, 'task_manager') and self.task_manager:
            downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
            if downloading_tasks:
                dialog = QDialog(self)
                dialog.setWindowTitle("确认退出")
                dialog.setMinimumSize(400, 200)
                dialog.setStyleSheet(BASE_STYLE)

                main_layout = QVBoxLayout(dialog)
                main_layout.setContentsMargins(20, 20, 20, 20)
                main_layout.setSpacing(15)

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
                        task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config)
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
                        
                        
                        import threading
                        def cleanup_and_close():
                            if hasattr(self, 'download_manager') and self.download_manager:
                                self.download_manager.cancel_all()
                            
                            if hasattr(self, 'task_manager') and self.task_manager:
                                downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
                                for task in downloading_tasks:
                                    self.task_manager.update_task_status(task['id'], 'failed', '异常中断')
                            
                            
                            QTimer.singleShot(100, self._close_with_animation)
                        
                        thread = threading.Thread(target=cleanup_and_close)
                        thread.daemon = True
                        thread.start()
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
                    self._cleanup_before_exit()
                    QApplication.instance().quit()
                except RuntimeError:
                    
                    pass
        
        fade_out()

    def closeEvent(self, event):
        
        try:
            for loader in self.cover_loaders:
                if loader.isRunning():
                    loader.terminate()
                    loader.wait(100)  
            self.cover_loaders.clear()
        except Exception as e:
            print(f"清理线程时出错: {str(e)}")
        
        if hasattr(self, 'task_manager') and self.task_manager:
            downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
            if downloading_tasks:
                dialog = QDialog(self)
                dialog.setWindowTitle("确认退出")
                dialog.setMinimumSize(400, 200)
                dialog.setStyleSheet(BASE_STYLE)

                main_layout = QVBoxLayout(dialog)
                main_layout.setContentsMargins(20, 20, 20, 20)
                main_layout.setSpacing(15)

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

    def on_view_tasks(self, dialog):
        if hasattr(self, 'task_manager') and self.task_manager and hasattr(self, 'parser') and hasattr(self, 'download_manager'):
            task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config)
            task_window.show()
            task_window.raise_()  # 确保窗口在最前面
            task_window.activateWindow()  # 激活窗口
        dialog.accept()

    def on_confirm_close(self, dialog, event):
        if not self.background_checkbox.isChecked():
            
            dialog.accept()
            
            
            import threading
            def cleanup_and_close():
                if hasattr(self, 'download_manager') and self.download_manager:
                    self.download_manager.cancel_all()
                
                if hasattr(self, 'task_manager') and self.task_manager:
                    downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
                    for task in downloading_tasks:
                        self.task_manager.update_task_status(task['id'], 'failed', '异常中断')
                
                
                QTimer.singleShot(0, lambda: self._close_with_animation())
            
            thread = threading.Thread(target=cleanup_and_close)
            thread.daemon = True
            thread.start()
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
        
        import threading
        def cleanup_and_quit():
            if hasattr(self, 'download_manager') and self.download_manager:
                self.download_manager.cancel_all()
            
            if hasattr(self, 'task_manager') and self.task_manager:
                downloading_tasks = self.task_manager.get_tasks_by_status('downloading')
                for task in downloading_tasks:
                    self.task_manager.update_task_status(task['id'], 'failed', '异常中断')
            
            self._cleanup_before_exit()
            
            
            QTimer.singleShot(0, lambda: self.close())
            QTimer.singleShot(100, lambda: sys.exit())
        
        thread = threading.Thread(target=cleanup_and_quit)
        thread.daemon = True
        thread.start()

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
                task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config)
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
            task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager, self.config)
            task_window.show()

    def on_batch_parse(self):
        dialog = QDialog()
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        dialog.setWindowTitle("批量解析")
        dialog.setMinimumSize(600, 400)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        
        # 应用自定义边框样式
        custom_style = BASE_STYLE + """
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
            # 标题栏样式
            # 这里不添加标题栏，因为我们会手动创建
        """
        dialog.setStyleSheet(custom_style)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 添加标题栏
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 2, 10, 2)
        title_layout.setSpacing(8)
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 28px; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        
        title_label = QLabel("批量解析")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        title_layout.addWidget(title_label, stretch=1)
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.setStyleSheet("width: 28px; height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;")
        minimize_btn.clicked.connect(dialog.showMinimized)
        title_layout.addWidget(minimize_btn)
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setStyleSheet("width: 28px; height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;")
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        # 添加内容区域
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

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
            if event.button() == Qt.LeftButton and event.y() < 32:
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
        
        batch_parse_window.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        batch_parse_window.setWindowTitle("批量解析结果")
        batch_parse_window.setGeometry(200, 200, 800, 600)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                batch_parse_window.setWindowIcon(icon)
        except Exception as e:
            pass
        
        batch_parse_window.dragging = False
        batch_parse_window.start_pos = None
        
        
        def mousePressEvent(event):
            
            if event.button() == Qt.LeftButton and event.y() < 32:  
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
        
        custom_style = BASE_STYLE + """
            QMainWindow {
                border: 2px solid #409eff;
                border-radius: 8px;
            }
            #titleBar {
                background-color: #409eff;
                color: white;
                height: 28px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            #titleLabel {
                font-weight: bold;
                font-size: 13px;
            }
            #minimizeBtn, #maximizeBtn, #closeBtn {
                width: 28px;
                height: 28px;
                border: none;
                background-color: transparent;
                color: white;
                font-size: 14px;
            }
            #minimizeBtn:hover, #maximizeBtn:hover {
                background-color: rgba(255, 255, 255, 0.2);
            }
            #closeBtn:hover {
                background-color: #f56c6c;
            }
        """
        batch_parse_window.setStyleSheet(custom_style)

        central_widget = QWidget()
        batch_parse_window.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 2, 10, 2)
        title_layout.setSpacing(8)
        
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
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        title_label = QLabel(f"批量解析结果 - 共{len(urls)}个链接")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2563eb;")
        content_layout.addWidget(title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        
        for i, url in enumerate(urls):
            group = QGroupBox(f"链接 {i+1}")
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(8)

            url_label = QLabel(f"URL: <a href='{url}'>{url[:100]}...</a>")
            url_label.setOpenExternalLinks(True)
            group_layout.addWidget(url_label)

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

            btn_layout = QHBoxLayout()
            btn_layout.addWidget(select_btn)
            btn_layout.addWidget(download_btn)
            group_layout.addLayout(btn_layout)

            scroll_layout.addWidget(group)

            
            link_data = {
                'url': url,
                'group': group,
                'status_label': status_label,
                'title_label': title_label,
                'quality_label': quality_label,
                'select_btn': select_btn,
                'download_btn': download_btn,
                'selected_episodes': [],
                'video_info': None,
                'quality_combo': None
            }

            
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
                    quality_dialog.setMinimumSize(400, 200)
                    quality_dialog.setStyleSheet(BASE_STYLE)

                    quality_layout = QVBoxLayout(quality_dialog)
                    quality_layout.setContentsMargins(20, 20, 20, 20)
                    quality_layout.setSpacing(15)

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
                            "audio_format": self.config.get_app_setting("audio_output_format", "mp3")
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

            
            import threading
            def parse_link(url, link_data):
                try:
                    if self.parser is None:
                        self.update_batch_parse_video_info(link_data, False, "解析器未初始化，请重启应用")
                        return
                    media_parse_video_info = self.parser.parse_media_url(url)
                    if media_parse_video_info.get("error"):
                        self.update_batch_parse_video_info(link_data, False, media_parse_video_info["error"])
                        return

                    media_type = media_parse_video_info["type"]
                    media_id = media_parse_video_info["id"]
                    if not media_type or not media_id:
                        self.update_batch_parse_video_info(link_data, False, "未识别到有效媒体ID")
                        return

                    media_info = self.parser.parse_media(media_type, media_id, self.tv_mode_checkbox.isChecked())
                    self.update_batch_parse_video_info(link_data, True, media_info)
                except Exception as e:
                    self.update_batch_parse_video_info(link_data, False, f"解析失败：{str(e)}")

            thread = threading.Thread(target=parse_link, args=(url, link_data))
            thread.daemon = True
            thread.start()

        scroll_area.setWidget(scroll_content)
        content_layout.addWidget(scroll_area, stretch=1)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(batch_parse_window.close)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(close_btn)
        content_layout.addLayout(btn_layout)
        
        
        main_layout.addWidget(content_widget)

        
        def batch_parse_window_mousePressEvent(event):
            
            if event.button() == Qt.LeftButton and event.y() < 32:  
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
        dialog.setMinimumSize(1100, 800)
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        
        
        custom_style = BASE_STYLE + """
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
            QWidget#titleBar {
                background-color: #409eff;
                color: white;
                height: 40px;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QLabel#titleLabel {
                font-size: 14px;
                font-weight: bold;
                color: white;
            }
            QPushButton#closeBtn {
                width: 28px;
                height: 28px;
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
                width: 2px;
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
        """
        dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(20, 10, 12, 10)
        title_layout.setSpacing(8)
        
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
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(12)
        
        
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
        search_edit.setMaximumWidth(200)
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
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(8)
        
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
        tree_view.setMinimumWidth(280)
        
        
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
        list_view.setIconSize(QSize(64, 64))
        list_view.setUniformItemSizes(True)
        list_view.setSpacing(16)
        list_view.setMinimumWidth(500)
        list_view.setGridSize(QSize(100, 100))
        splitter.addWidget(list_view)
        splitter.setStretchFactor(1, 3)
        
        
        splitter.setSizes([300, 750])
        
        content_layout.addWidget(splitter, stretch=1)
        
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        
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
                list_view.setIconSize(QSize(64, 64))
                list_view.setGridSize(QSize(100, 100))
            else:  
                list_view.setViewMode(QListWidget.ListMode)
                list_view.setIconSize(QSize(24, 24))
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
        self.login_dialog.setWindowTitle("登录B站")
        self.login_dialog.setMinimumSize(800, 500)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                self.login_dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        login_dialog = self.login_dialog
        
        
        custom_style = BASE_STYLE + """
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
        """
        login_dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(login_dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        title_bar = QWidget()
        title_bar.setObjectName("titleBar")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 2, 10, 2)
        title_layout.setSpacing(8)
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 28px; border-top-left-radius: 6px; border-top-right-radius: 6px;")
        
        title_label = QLabel("登录B站")
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        title_layout.addWidget(title_label, stretch=1)
        
        
        minimize_btn = QPushButton("_")
        minimize_btn.setObjectName("minimizeBtn")
        minimize_btn.setStyleSheet("width: 28px; height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;")
        minimize_btn.clicked.connect(login_dialog.hide)
        title_layout.addWidget(minimize_btn)
        
        
        close_btn = QPushButton("×")
        close_btn.setObjectName("closeBtn")
        close_btn.setStyleSheet("width: 28px; height: 28px; border: none; background-color: transparent; color: white; font-size: 14px;")
        close_btn.clicked.connect(login_dialog.hide)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)
        
        main_layout.addWidget(content_widget, stretch=1)
        
        
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(20, 20, 20, 20)
        left_layout.setSpacing(15)
        
        qr_title = QLabel("扫码登录")
        qr_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2563eb;")
        qr_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(qr_title)
        
        
        qr_code_label = QLabel()
        qr_code_label.setAlignment(Qt.AlignCenter)
        qr_code_label.setMinimumSize(200, 200)
        qr_code_label.setMaximumSize(200, 200)
        qr_code_label.setStyleSheet("border: 1px solid #e9ecef; border-radius: 8px; background-color: #f8fafc;")
        left_layout.addWidget(qr_code_label, alignment=Qt.AlignCenter)
        
        qr_status = QLabel("请使用哔哩哔哩App扫码登录")
        qr_status.setAlignment(Qt.AlignCenter)
        qr_status.setStyleSheet("font-size: 14px; color: #6b7280;")
        left_layout.addWidget(qr_status)
        

        
        
        login_poll_thread = None
        
        
        
        class QRCodeThread(QThread):
            finished = pyqtSignal(dict, bytes)  
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
                    
                    
                    self.finished.emit(qrcode_video_info, qr_data)
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
                qr_status.setStyleSheet("font-size: 14px; color: #52c41a; text-align: center;")
                login_dialog.repaint()
                
                user_info = video_info.get("user_info", {})
                if user_info.get("success"):
                    
                    self.load_local_cookie()
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
                    qr_status.setStyleSheet("font-size: 14px; color: #fa8c16; text-align: center;")
                    
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
                            verify_dialog.setMinimumSize(800, 600)
                            
                            
                            web_view = QWebEngineView()
                            web_view.setUrl(QUrl(url))
                            
                            
                            layout = QVBoxLayout(verify_dialog)
                            layout.addWidget(web_view)
                            
                            
                            verify_dialog.exec_()
                    
                    show_risk_message()
                elif video_info.get("status") == "二维码已失效" or "过期" in message:
                    
                    qr_status.setStyleSheet("font-size: 14px; color: #f56c6c; text-align: center;")
                    
                    if login_poll_thread and login_poll_thread.isRunning():
                        login_poll_thread.stop()
                    
                    def on_qr_status_clicked():
                        get_qrcode()
                    qr_status.mousePressEvent = lambda event: on_qr_status_clicked()
                else:
                    
                    qr_status.setStyleSheet("font-size: 14px; color: #6b7280; text-align: center;")
                
                login_dialog.repaint()
        
        def get_qrcode():
            nonlocal login_poll_thread, qr_thread, last_click_time, qrcode_key
            try:
                current_time = time.time()
                if current_time - last_click_time < 2:
                    return
                last_click_time = current_time
                
                qr_status.setText("刷新中...")
                qr_status.setStyleSheet("font-size: 14px; color: #6b7280; text-align: center;")
                login_dialog.repaint()
                
                
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
                qr_thread.finished.connect(on_qr_generated)
                qr_thread.error.connect(on_qr_error)
                qr_thread.start()
                
            except Exception as e:
                error_msg = str(e)
                print(f"获取二维码失败：{error_msg}")
                traceback.print_exc()
                qr_status.setText(f"错误：{error_msg}")
                qr_status.setStyleSheet("font-size: 14px; color: #f56c6c; text-align: center;")
                login_dialog.repaint()
        
        def on_qr_generated(qrcode_video_info, qr_data):
            nonlocal qrcode_key, login_poll_thread
            try:
                
                pixmap = QPixmap()
                success = pixmap.loadFromData(qr_data)
                
                if success:
                    pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    qr_code_label.setPixmap(pixmap)
                    
                    qr_status.setText("二维码生成成功，请扫描")
                    qr_status.setStyleSheet("font-size: 14px; color: #6b7280; text-align: center;")
                    login_dialog.repaint()
                    
                    
                    qrcode_key = qrcode_video_info.get("qrcode_key")
                    
                    from utils import LoginPollThread
                    login_poll_thread = LoginPollThread(self.parser, qrcode_key)
                    login_poll_thread.status_signal.connect(on_login_status_update)
                    login_poll_thread.start()
                else:
                    qr_status.setText("二维码加载失败")
                    login_dialog.repaint()
            except Exception as e:
                error_msg = str(e)
                print(f"显示二维码失败：{error_msg}")
                traceback.print_exc()
                qr_status.setText(f"错误：{error_msg}")
                login_dialog.repaint()
        
        def on_qr_error(error_msg):
            qr_status.setText(f"错误：{error_msg}")
            login_dialog.repaint()


        # 按钮容器
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(10)
        
        refresh_status_btn = QPushButton("刷新状态")
        refresh_status_btn.setMinimumHeight(36)
        refresh_status_btn.setMinimumWidth(100)
        refresh_status_btn.setStyleSheet("background-color: #60a5fa; color: white; font-weight: 500; font-size: 12px; border-radius: 8px; padding: 0 12px;")
        
        def on_refresh_status():
            nonlocal login_poll_thread, qrcode_key
            if qrcode_key:
                qr_status.setText("刷新状态中...")
                login_dialog.repaint()
                
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
        refresh_btn.setMinimumHeight(36)
        refresh_btn.setMinimumWidth(100)
        refresh_btn.setStyleSheet("background-color: #409eff; color: white; font-weight: 500; font-size: 12px; border-radius: 8px; padding: 0 12px;")
        refresh_btn.clicked.connect(get_qrcode)
        buttons_layout.addWidget(refresh_btn)
        
        left_layout.addWidget(buttons_widget, alignment=Qt.AlignCenter)

        left_layout.addStretch(1)
        content_layout.addWidget(left_widget, stretch=1)
        
        
        get_qrcode()
        
        
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)
        
        
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
        tab_layout.setSpacing(0)
        
        password_tab = QPushButton("账号密码")
        password_tab.setStyleSheet("background-color: #409eff; color: white; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
        sms_tab = QPushButton("验证码")
        sms_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
        cookie_tab = QPushButton("Cookie")
        cookie_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
        
        tab_layout.addWidget(password_tab)
        tab_layout.addWidget(sms_tab)
        tab_layout.addWidget(cookie_tab)
        right_layout.addWidget(tab_widget)
        
        
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(15)
        
        
        password_form = QWidget()
        password_layout = QVBoxLayout(password_form)
        password_layout.setSpacing(16)
        
        
        risk_banner = QWidget()
        risk_banner.setStyleSheet("""
            background-color: #fff7e6;
            border: 1px solid #ffd591;
            border-radius: 8px;
            padding: 12px;
        """)
        risk_layout = QHBoxLayout(risk_banner)
        risk_layout.setContentsMargins(12, 12, 12, 12)
        risk_layout.setSpacing(12)
        
        risk_label = QLabel("登录环境存在风险，需要验证")
        risk_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 500;
            color: #fa8c16;
            line-height: 1.4;
        """)
        risk_layout.addWidget(risk_label, stretch=1)
        
        verify_btn = QPushButton("前往验证")
        verify_btn.setStyleSheet("""
            background-color: #fa8c16;
            color: white;
            font-size: 13px;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
        """)
        verify_btn.setMinimumHeight(32)
        risk_layout.addWidget(verify_btn)
        
        risk_banner.hide()
        password_layout.addWidget(risk_banner)
        
        username_edit = QLineEdit()
        username_edit.setPlaceholderText("请输入手机号/邮箱")
        username_edit.setMinimumHeight(44)
        username_edit.setStyleSheet("font-size: 14px; padding: 0 16px;")
        password_layout.addWidget(username_edit)
        
        password_edit = QLineEdit()
        password_edit.setPlaceholderText("请输入密码")
        password_edit.setEchoMode(QLineEdit.Password)
        password_edit.setMinimumHeight(44)
        password_edit.setStyleSheet("font-size: 14px; padding: 0 16px;")
        password_layout.addWidget(password_edit)
        
        login_btn = QPushButton("登录")
        login_btn.setMinimumHeight(44)
        login_btn.setStyleSheet("background-color: #409eff; color: white; font-weight: 500; font-size: 14px;")
        password_layout.addWidget(login_btn)
        
        
        password_form.risk_banner = risk_banner
        password_form.risk_label = risk_label
        password_form.verify_btn = verify_btn
        
        
        sms_form = QWidget()
        sms_layout = QVBoxLayout(sms_form)
        sms_layout.setSpacing(16)
        
        
        cid_combo = QComboBox()
        cid_combo.setEditable(True)  
        cid_combo.setMinimumHeight(44)
        cid_combo.setStyleSheet("font-size: 14px; padding: 0 16px;")
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
        tel_edit.setMinimumHeight(44)
        tel_edit.setStyleSheet("font-size: 14px; padding: 0 16px;")
        sms_layout.addWidget(tel_edit)
        
        
        code_layout = QHBoxLayout()
        code_layout.setSpacing(12)
        
        code_edit = QLineEdit()
        code_edit.setPlaceholderText("请输入验证码")
        code_edit.setMinimumHeight(44)
        code_edit.setStyleSheet("font-size: 14px; padding: 0 16px;")
        code_layout.addWidget(code_edit, stretch=1)
        
        send_code_btn = QPushButton("发送验证码")
        send_code_btn.setMinimumHeight(44)
        send_code_btn.setMinimumWidth(130)
        send_code_btn.setStyleSheet("background-color: #10b981; color: white; font-weight: 500; font-size: 14px;")
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
        sms_login_btn.setMinimumHeight(44)
        sms_login_btn.setStyleSheet("background-color: #409eff; color: white; font-weight: 500; font-size: 14px;")
        sms_layout.addWidget(sms_login_btn)
        
        
        cookie_form = QWidget()
        cookie_layout = QVBoxLayout(cookie_form)
        cookie_layout.setSpacing(16)
        
        cookie_edit = QTextEdit()
        cookie_edit.setPlaceholderText("请输入Cookie（SESSDATA/bili_jct/DedeUserID）")
        cookie_edit.setMinimumHeight(120)
        cookie_edit.setStyleSheet("font-size: 14px; padding: 12px;")
        cookie_layout.addWidget(cookie_edit)
        
        cookie_login_btn = QPushButton("登录")
        cookie_login_btn.setMinimumHeight(44)
        cookie_login_btn.setStyleSheet("background-color: #409eff; color: white; font-weight: 500; font-size: 14px;")
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
                password_tab.setStyleSheet("background-color: #409eff; color: white; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
                sms_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
                cookie_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
            elif tab_index == 1:
                password_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
                sms_tab.setStyleSheet("background-color: #409eff; color: white; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
                cookie_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
            else:
                password_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 8px; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
                sms_tab.setStyleSheet("background-color: #f8f9fa; color: #6b7280; border-top-left-radius: 0; border-top-right-radius: 0; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
                cookie_tab.setStyleSheet("background-color: #409eff; color: white; border-top-left-radius: 0; border-top-right-radius: 8px; border-bottom-left-radius: 0; border-bottom-right-radius: 0; padding: 12px 24px; font-weight: 500;")
        
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
            if event.button() == Qt.LeftButton and event.y() < 32:  
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
            
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                
                event.ignore()
            else:
                
                QDialog.keyPressEvent(login_dialog, event)
        
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
                                        verify_dialog.setMinimumSize(800, 600)
                                        
                                        
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
            print("on_cookie_login函数被调用")
            cookie = cookie_edit.toPlainText().strip()
            print(f"获取到的Cookie长度：{len(cookie)}")
            if not cookie:
                print("Cookie为空，显示警告")
                self.show_notification("请输入Cookie", "warning")
                return
            
            
            print("显示开始登录提示")
            self.show_notification("开始Cookie登录，请稍候...", "info")
            
            
            try:
                print("显示验证中提示")
                self.show_notification("正在验证Cookie...", "info")
                print("开始保存Cookie...")
                
                
                def verify_cookie_in_thread():
                    print("verify_cookie_in_thread函数开始执行")
                    try:
                        
                        if not hasattr(self, 'parser') or not self.parser:
                            print("parser不存在")
                            QTimer.singleShot(0, lambda: self.show_notification("解析器未初始化，请重启应用", "error"))
                            return
                        
                        
                        print("开始保存Cookie")
                        save_success = self.parser.save_cookies(cookie)
                        print(f"Cookie保存结果：{save_success}")
                        if not save_success:
                            
                            QTimer.singleShot(0, lambda: self.show_notification("Cookie格式错误！支持：JSON对象列表、key1=value1;格式", "error"))
                            print("Cookie格式错误，返回")
                            return
                        
                        
                        print("开始验证Cookie...")
                        success, msg = self.parser.verify_cookie()
                        print(f"Cookie验证结果：{success}, {msg}")
                        
                        
                        def handle_verification_video_info():
                            print("handle_verification_video_info函数开始执行")
                            try:
                                if success:
                                    try:
                                        
                                        print("显示成功消息...")
                                        self.show_success_message(msg)
                                        print("成功消息已显示")
                                        
                                        print("加载用户信息...")
                                        user_info = self.parser.get_user_info()
                                        print(f"获取到的用户信息：{user_info}")
                                        self.update_user_info(user_info)
                                        print("用户信息已更新")
                                        
                                        print("检查cookie有效性...")
                                        self.check_cookie_validity()
                                        print("cookie有效性检查完成")
                                        
                                        if hasattr(self, 'login_dialog') and self.login_dialog:
                                            print("隐藏登录对话框...")
                                            self.login_dialog.hide()
                                            print("登录对话框已隐藏")
                                        else:
                                            print("未找到登录对话框实例")
                                        
                                        self.showMaximized()
                                    except Exception as e:
                                        logger.error(f"保存Cookie失败：{str(e)}")
                                        self.show_notification(f"保存Cookie失败：{str(e)}", "error")
                                        print(f"处理成功情况时发生异常：{str(e)}")
                                        traceback.print_exc()
                                else:
                                    print("显示验证失败消息...")
                                    self.show_notification(f"验证失败：{msg}", "error")
                                    print("验证失败消息已显示")
                                    
                                    print("登录失败，保持窗口显示")
                                
                                self.showMaximized()
                                print("验证流程执行完成")
                            except Exception as e:
                                print(f"handle_verification_video_info函数发生异常：{str(e)}")
                                traceback.print_exc()
                        
                        print("准备调用handle_verification_video_info")
                        
                        try:
                            print("直接调用handle_verification_video_info")
                            handle_verification_video_info()
                            print("handle_verification_video_info直接调用完成")
                        except Exception as e:
                            print(f"直接调用handle_verification_video_info失败：{str(e)}")
                            traceback.print_exc()
                            
                            print("尝试通过QTimer调用handle_verification_video_info")
                            QTimer.singleShot(0, handle_verification_video_info)
                            print("handle_verification_video_info已通过QTimer安排执行")
                    except Exception as e:
                        print(f"Cookie处理异常：{str(e)}")
                        traceback.print_exc()
                        
                        QTimer.singleShot(0, lambda: self.show_notification(f"Cookie处理失败：{str(e)}", "error"))
                
                
                import threading
                print("创建验证线程")
                thread = threading.Thread(target=verify_cookie_in_thread)
                thread.daemon = True
                print("启动验证线程")
                thread.start()
                print("验证线程已启动")
            except Exception as e:
                logger.error(f"Cookie登录失败：{str(e)}")
                self.show_notification(f"登录失败：{str(e)}", "error")
                print(f"处理Cookie登录时发生异常：{str(e)}")
                traceback.print_exc()
        
        
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
            
        dialog = QDialog()
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        dialog.setWindowTitle("设置")
        dialog.setMinimumSize(900, 700)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        
        
        custom_style = BASE_STYLE + """
            QDialog {
                border: 2px solid #409eff;
                border-radius: 12px;
                background-color: white;
            }
        """
        dialog.setStyleSheet(custom_style)
        
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 40px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(16, 0, 12, 0)
        title_layout.setSpacing(10)
        
        title_label = QLabel("设置")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: white; letter-spacing: 0.5px;")
        title_layout.addWidget(title_label, stretch=1)
        
        close_btn = QPushButton("×")
        close_btn.setStyleSheet("background-color: transparent; border: none; color: white; font-size: 18px; padding: 0; width: 28px; height: 28px; border-radius: 14px;")
        close_btn.setToolTip("关闭")
        close_btn.clicked.connect(dialog.reject)
        title_layout.addWidget(close_btn)
        
        main_layout.addWidget(title_bar)
        
        
        content_widget = QWidget()
        content_layout = QGridLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)

        main_layout.addWidget(content_widget)

        
        # 默认下载路径
        path_group = QGroupBox("默认下载路径")
        path_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        path_layout = QVBoxLayout(path_group)
        path_layout.setContentsMargins(10, 10, 10, 10)
        path_layout.setSpacing(8)
        
        current_default = self.config.get_app_setting("default_save_path")
        if not current_default:
            current_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        
        path_edit = QLineEdit(current_default)
        path_edit.setMinimumHeight(32)
        path_edit.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
        path_layout.addWidget(path_edit)
        
        browse_btn = QPushButton("浏览")
        browse_btn.setMinimumHeight(32)
        browse_btn.setStyleSheet("background-color: #409eff; color: white; border-radius: 6px; padding: 8px 16px;")
        
        def browse_path():
            path = self.show_custom_file_dialog("选择默认保存路径")
            if path:
                path_edit.setText(path)
        
        browse_btn.clicked.connect(browse_path)
        path_layout.addWidget(browse_btn)
        
        content_layout.addWidget(path_group, 0, 0)

        
        # 下载线程数
        thread_group = QGroupBox("下载线程数")
        thread_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
        thread_layout = QVBoxLayout(thread_group)
        thread_layout.setContentsMargins(10, 10, 10, 10)
        
        thread_spin = QComboBox()
        thread_spin.setMinimumHeight(32)
        thread_spin.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
        for i in range(1, 11):
            thread_spin.addItem(str(i), i)
        current_threads = self.config.get_app_setting("max_threads", 2)
        thread_spin.setCurrentIndex(current_threads - 1)
        thread_layout.addWidget(thread_spin)
        
        content_layout.addWidget(thread_group, 0, 1)
        
        
        # 系统托盘
        tray_group = QGroupBox("系统托盘")
        tray_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QCheckBox { spacing: 8px; font-size: 13px; }")
        tray_layout = QVBoxLayout(tray_group)
        tray_layout.setContentsMargins(10, 10, 10, 10)
        
        minimize_to_tray_checkbox = QCheckBox("关闭窗口时最小化到托盘")
        minimize_to_tray_checkbox.setChecked(self.config.get_app_setting("minimize_to_tray", True))
        tray_layout.addWidget(minimize_to_tray_checkbox)
        
        content_layout.addWidget(tray_group, 1, 0)

        
        # 窗口设置
        window_group = QGroupBox("窗口设置")
        window_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QCheckBox { spacing: 8px; font-size: 13px; }")
        window_layout = QVBoxLayout(window_group)
        window_layout.setContentsMargins(10, 10, 10, 10)
        
        topmost_checkbox = QCheckBox("窗口置顶")
        is_topmost = self.windowFlags() & Qt.WindowStaysOnTopHint
        topmost_checkbox.setChecked(is_topmost)
        window_layout.addWidget(topmost_checkbox)
        
        content_layout.addWidget(window_group, 1, 1)

        # 下载设置组
        download_group = QGroupBox("下载设置")
        download_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QLabel { font-size: 13px; } QCheckBox { spacing: 8px; font-size: 13px; }")
        download_group.setMinimumHeight(320)
        download_layout = QVBoxLayout(download_group)
        download_layout.setContentsMargins(10, 10, 10, 10)
        download_layout.setSpacing(6)
        
        # 默认下载质量
        quality_layout = QHBoxLayout()
        quality_label = QLabel("默认下载质量：")
        quality_label.setMinimumHeight(22)
        quality_combo = QComboBox()
        quality_combo.setMinimumHeight(26)
        quality_combo.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
        
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
        
        # 自动下载封面
        auto_cover_checkbox = QCheckBox("自动下载视频封面")
        auto_cover_checkbox.setMinimumHeight(22)
        auto_cover_checkbox.setChecked(self.config.get_app_setting("auto_download_cover", True))
        download_layout.addWidget(auto_cover_checkbox)
        
        # 自动下载弹幕
        auto_danmaku_checkbox = QCheckBox("自动下载弹幕文件")
        auto_danmaku_checkbox.setMinimumHeight(22)
        auto_danmaku_checkbox.setChecked(self.config.get_app_setting("auto_download_danmaku", False))
        download_layout.addWidget(auto_danmaku_checkbox)
        
        # 下载完成后打开文件夹
        auto_open_folder_checkbox = QCheckBox("下载完成后打开文件夹")
        auto_open_folder_checkbox.setMinimumHeight(22)
        auto_open_folder_checkbox.setChecked(self.config.get_app_setting("auto_open_folder", False))
        download_layout.addWidget(auto_open_folder_checkbox)
        
        # 下载完成后播放提示音
        play_sound_checkbox = QCheckBox("下载完成后播放提示音")
        play_sound_checkbox.setMinimumHeight(22)
        play_sound_checkbox.setChecked(self.config.get_app_setting("play_sound_on_complete", True))
        download_layout.addWidget(play_sound_checkbox)
        
        # 视频输出格式
        video_format_layout = QHBoxLayout()
        video_format_label = QLabel("视频输出格式：")
        video_format_label.setMinimumHeight(22)
        video_format_combo = QComboBox()
        video_format_combo.setMinimumHeight(26)
        video_format_combo.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
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
        
        # 弹幕输出格式
        danmaku_format_layout = QHBoxLayout()
        danmaku_format_label = QLabel("弹幕输出格式：")
        danmaku_format_label.setMinimumHeight(22)
        danmaku_format_combo = QComboBox()
        danmaku_format_combo.setMinimumHeight(26)
        danmaku_format_combo.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
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
        
        content_layout.addWidget(download_group, 2, 0, 1, 2)

        # 网络设置组
        network_group = QGroupBox("网络设置")
        network_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QLabel { font-size: 13px; }")
        network_layout = QVBoxLayout(network_group)
        network_layout.setContentsMargins(10, 10, 10, 10)
        network_layout.setSpacing(8)
        
        # 超时时间
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("网络超时时间（秒）：")
        timeout_spin = QComboBox()
        timeout_spin.setMinimumHeight(28)
        timeout_spin.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
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
        retry_spin.setMinimumHeight(28)
        retry_spin.setStyleSheet("padding: 8px 12px; border: 1px solid #dee2e6; border-radius: 6px;")
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
        
        content_layout.addWidget(network_group, 3, 0)

        # 其他设置组
        other_group = QGroupBox("其他设置")
        other_group.setStyleSheet("QGroupBox { font-weight: 600; color: #2563eb; border: 1px solid #e9ecef; border-radius: 8px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; } QCheckBox { spacing: 8px; font-size: 13px; }")
        other_layout = QVBoxLayout(other_group)
        other_layout.setContentsMargins(10, 10, 10, 10)
        other_layout.setSpacing(6)
        
        # 自动检查更新
        auto_update_checkbox = QCheckBox("启动时自动检查更新")
        auto_update_checkbox.setChecked(self.config.get_app_setting("auto_check_update", True))
        other_layout.addWidget(auto_update_checkbox)
        
        # 显示下载速度
        show_speed_checkbox = QCheckBox("显示下载速度")
        show_speed_checkbox.setChecked(self.config.get_app_setting("show_download_speed", True))
        other_layout.addWidget(show_speed_checkbox)
        
        # 显示悬浮球
        show_float_checkbox = QCheckBox("显示悬浮球")
        show_float_checkbox.setChecked(self.config.get_app_setting("show_floating_ball", True))
        other_layout.addWidget(show_float_checkbox)
        
        content_layout.addWidget(other_group, 3, 1)
        
        # 按钮布局
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setMinimumHeight(32)
        save_btn.setMinimumWidth(80)
        save_btn.setStyleSheet("background-color: #409eff; color: white; font-weight: 500; border-radius: 6px; padding: 6px 16px;")
        cancel_btn = QPushButton("取消")
        cancel_btn.setMinimumHeight(32)
        cancel_btn.setMinimumWidth(80)
        cancel_btn.setStyleSheet("background-color: #f56c6c; color: white; font-weight: 500; border-radius: 6px; padding: 6px 16px;")
        
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
            self.config.set_app_setting("video_output_format", video_format_combo.currentData())
            self.config.set_app_setting("danmaku_output_format", danmaku_format_combo.currentData())
            
            # 保存网络设置
            self.config.set_app_setting("network_timeout", timeout_spin.currentData())
            self.config.set_app_setting("max_retry", retry_spin.currentData())
            
            # 保存其他设置
            self.config.set_app_setting("auto_check_update", auto_update_checkbox.isChecked())
            self.config.set_app_setting("show_download_speed", show_speed_checkbox.isChecked())
            self.config.set_app_setting("show_floating_ball", show_float_checkbox.isChecked())
            
            dialog.accept()
        
        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(save_btn)
        btn_layout.addSpacing(8)
        btn_layout.addWidget(cancel_btn)
        content_layout.addLayout(btn_layout, 4, 0, 1, 2)
        


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
            self.show_notification(f"获取用户信息失败：{str(e)}", "error")
    
    def show_user_info_window(self, user_detail):
        
        dialog = QDialog()
        dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint)
        dialog.setWindowTitle("个人中心")
        dialog.setMinimumSize(800, 600)
        
        # 设置窗口图标
        try:
            logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")
            if os.path.exists(logo_path):
                icon = QIcon(logo_path)
                dialog.setWindowIcon(icon)
        except Exception as e:
            pass
        
        # 应用基础样式
        custom_style = BASE_STYLE + """
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
        """
        dialog.setStyleSheet(custom_style)
        
        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(2, 0, 2, 2)
        main_layout.setSpacing(0)
        
        # 添加鼠标事件处理，实现窗口移动
        dialog.mousePressEvent = lambda event: setattr(dialog, 'mouse_pos', event.globalPos() - dialog.pos())
        dialog.mouseMoveEvent = lambda event: dialog.move(event.globalPos() - getattr(dialog, 'mouse_pos', QPoint(0, 0)))
        
        # 添加标题栏
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #409eff; color: white; height: 36px; border-top-left-radius: 10px; border-top-right-radius: 10px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 8, 0)
        title_layout.setSpacing(6)
        
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
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
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
                    flex: 1;
                }}
                .username {{ 
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 4px;
                }}
                .uid {{ 
                    font-size: 12px;
                    opacity: 0.9;
                    margin-bottom: 8px;
                }}
                .level {{ 
                    display: inline-block;
                    background-color: rgba(255, 255, 255, 0.2);
                    padding: 2px 8px;
                    border-radius: 10px;
                    font-size: 11px;
                    font-weight: 500;
                    margin-bottom: 4px;
                }}
                .vip-status {{ 
                    font-size: 11px;
                    font-weight: 600;
                    color: #ffd700;
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

if __name__ == "__main__":
    from config import ConfigLoader

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    
    config = ConfigLoader()

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    ui = BilibiliDownloader(config)
    ui.show()
    sys.exit(app.exec_())