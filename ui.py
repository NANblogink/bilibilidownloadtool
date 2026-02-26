# 作者：寒烟似雪(逸雨)
# QQ：2273962061/3241417097
# 哔哩哔哩：不会玩python的man
# 个人主页：https://space.bilibili.com/3546841002019157
# 转载时请勿删除
# -*- coding: utf-8 -*-

import os
import sys
import webbrowser
import shutil

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                             QComboBox, QLabel, QFileDialog, QProgressBar, QMessageBox, QGroupBox,
                             QCheckBox, QScrollArea, QTextEdit, QDialog, QListWidget, QListWidgetItem,
                             QStackedWidget, QRadioButton, QButtonGroup, QSpacerItem, QSizePolicy, QMenu)
from PyQt5.QtCore import QSize
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QFont, QPalette, QColor, QCursor

BASE_STYLE = """
    QMainWindow { background-color: #f5f7fa; }
    QWidget { font-family: "Microsoft YaHei", "Segoe UI", sans-serif; font-size: 13px; }
    QLineEdit, QTextEdit, QComboBox, QListWidget {
        padding: 8px 10px;
        border: 1px solid #e2e8f0;
        border-radius: 6px;
        background-color: white;
    }
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QListWidget:focus {
        border-color: #409eff;
    }
    QPushButton {
        padding: 9px 18px;
        border: none;
        border-radius: 6px;
        color: white;
        background-color: #409eff;
    }
    QPushButton:hover { background-color: #66b1ff; }
    QPushButton:disabled { background-color: #d1d5db; }
    QPushButton#cancelBtn { background-color: #f56c6c; }
    QPushButton#hevcBtn { background-color: #fa8c16; }
    QPushButton#selectAllBtn { background-color: #52c41a; }
    QPushButton#deselectAllBtn { background-color: #919191; }
    QPushButton#applyCookieBtn { background-color: #9f7aea; }
    QPushButton#bilibiliBtn { background-color: #00a1d6; }
    QGroupBox {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 15px;
        margin-top: 12px;
        background-color: white;
    }
    QGroupBox::title { font-size: 14px; font-weight: 600; color: #2563eb; margin-left: 10px; }
    QProgressBar { height: 8px; border-radius: 4px; background-color: #e2e8f0; }
    QProgressBar::chunk { border-radius: 4px; background-color: #409eff; }
    QLabel#statusLabel { color: #6b7280; font-size: 12px; }
    QLabel#bilibiliLabel { color: #00a1d6; text-decoration: underline; }
    QCheckBox { margin: 6px 0; spacing: 8px; }
    QScrollArea { border: none; background-color: transparent; }
    QScrollBar:vertical { width: 8px; }
    QScrollBar::handle:vertical { background-color: #cbd5e1; border-radius: 4px; }
    QDialog { 
        border-radius: 8px; 
        background-color: white;
    }
    QDialog QLabel { font-size: 14px; }
    QListWidget { border-radius: 6px; }
    QListWidget::item { 
        padding: 8px 12px; 
        border-bottom: 1px solid #f0f2f5; 
        height: 40px;
    }
    QListWidget::item:hover { background-color: #f8fafc; }
    QListWidget::item:selected { 
        background-color: #e6f7ff; 
        color: #2f5496;
    }
    .card-view QListWidget::item { 
        width: 120px; 
        margin: 8px; 
        border: 1px solid #e2e8f0; 
        border-radius: 6px; 
        height: 80px;
    }
    .card-view QListWidget::item:hover { background-color: #f8fafc; }
    .card-view QListWidget::item:selected { 
        border-color: #409eff; 
        background-color: #e6f7ff;
    }
"""


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


class EpisodeSelectionDialog(QDialog):
    def __init__(self, parent, episodes, is_bangumi=False):
        super().__init__(parent)
        self.episodes = episodes
        self.is_bangumi = is_bangumi
        self.filtered_episodes = episodes.copy()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("选择集数" + ("（番剧）" if self.is_bangumi else "（合集）"))
        self.setMinimumSize(600, 400)
        self.setStyleSheet(BASE_STYLE)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索集数标题...")
        self.search_edit.textChanged.connect(self.filter_episodes)
        search_layout.addWidget(self.search_edit, stretch=1)
        main_layout.addLayout(search_layout)

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
        main_layout.addLayout(view_layout)

        self.stacked_view = QStackedWidget()
        main_layout.addWidget(self.stacked_view, stretch=1)

        self.list_view = QListWidget()
        self.list_view.setAlternatingRowColors(True)
        self.list_view.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_view.setSelectionBehavior(QListWidget.SelectItems)
        self.populate_list_view()
        self.stacked_view.addWidget(self.list_view)

        self.card_view = QListWidget()
        self.card_view.setViewMode(QListWidget.IconMode)
        self.card_view.setResizeMode(QListWidget.Adjust)
        self.card_view.setFlow(QListWidget.LeftToRight)
        self.card_view.setSpacing(10)
        self.card_view.setSelectionMode(QListWidget.ExtendedSelection)
        self.card_view.setSelectionBehavior(QListWidget.SelectItems)
        self.populate_card_view()
        self.stacked_view.addWidget(self.card_view)

        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.clicked.connect(self.select_all)
        self.deselect_all_btn = QPushButton("取消全选")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        self.confirm_btn = QPushButton("确认选择")
        self.confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.select_all_btn)
        btn_layout.addWidget(self.deselect_all_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.confirm_btn)
        main_layout.addLayout(btn_layout)

    def populate_list_view(self):
        self.list_view.clear()
        for i, ep in enumerate(self.filtered_episodes):
            if self.is_bangumi:
                text = f"{ep['ep_index']} - {ep['ep_title']}"
            else:
                text = f"第{ep['page']}集 - {ep['title']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, i)
            item.setToolTip(ep['ep_title'] if self.is_bangumi else ep['title'])
            self.list_view.addItem(item)

    def populate_card_view(self):
        self.card_view.clear()
        for i, ep in enumerate(self.filtered_episodes):
            if self.is_bangumi:
                text = f"{ep['ep_index']}\n{ep['ep_title'][:10]}"
                tooltip = ep['ep_title']
            else:
                text = f"第{ep['page']}集\n{ep['title'][:10]}"
                tooltip = ep['title']
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, i)
            item.setToolTip(tooltip)
            self.card_view.addItem(item)

    def filter_episodes(self, keyword):
        keyword = keyword.lower()
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        selected_indices = [item.data(Qt.UserRole) for item in current_view.selectedItems()]

        if not keyword:
            self.filtered_episodes = self.episodes.copy()
        else:
            self.filtered_episodes = [
                ep for ep in self.episodes
                if keyword in (ep['ep_title'].lower() if self.is_bangumi else ep['title'].lower())
            ]

        if self.list_radio.isChecked():
            self.populate_list_view()
        else:
            self.populate_card_view()

        for i in range(current_view.count()):
            item = current_view.item(i)
            if item.data(Qt.UserRole) in selected_indices:
                item.setSelected(True)

    def switch_view(self, view_type):
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        selected_indices = [item.data(Qt.UserRole) for item in current_view.selectedItems()]

        if view_type == "list":
            self.stacked_view.setCurrentWidget(self.list_view)
            self.populate_list_view()
            for i in range(self.list_view.count()):
                item = self.list_view.item(i)
                if item.data(Qt.UserRole) in selected_indices:
                    item.setSelected(True)
        else:
            self.stacked_view.setCurrentWidget(self.card_view)
            self.populate_card_view()
            for i in range(self.card_view.count()):
                item = self.card_view.item(i)
                if item.data(Qt.UserRole) in selected_indices:
                    item.setSelected(True)

    def select_all(self):
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        current_view.selectAll()

    def deselect_all(self):
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        current_view.clearSelection()

    def accept(self):
        current_view = self.list_view if self.list_radio.isChecked() else self.card_view
        selected_items = current_view.selectedItems()
        selected_indices = [item.data(Qt.UserRole) for item in selected_items]
        self.selected_episodes = [self.episodes[i] for i in selected_indices]
        super().accept()


class TaskManagerWindow(QMainWindow):
    def __init__(self, task_manager, parser, download_manager):
        super().__init__()
        self.task_manager = task_manager
        self.parser = parser
        self.download_manager = download_manager
        self.init_ui()
        # 连接任务状态变化信号
        if hasattr(self.download_manager, 'task_status_changed'):
            self.download_manager.task_status_changed.connect(self.refresh_task_list)
        if hasattr(self.download_manager, 'task_added'):
            self.download_manager.task_added.connect(self.refresh_task_list)

    def init_ui(self):
        self.setWindowTitle("任务管理")
        self.setGeometry(100, 100, 1000, 600)
        self.setMinimumSize(900, 600)  # 增加最小宽度，避免界面被挤压
        self.setStyleSheet(BASE_STYLE)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("下载任务管理")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2563eb;")
        main_layout.addWidget(title_label)

        # 任务列表
        self.task_list = QListWidget()
        self.task_list.setSelectionMode(QListWidget.SingleSelection)
        self.task_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 设置任务列表为可扩展
        main_layout.addWidget(self.task_list, stretch=1)

        # 按钮布局
        btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.clicked.connect(self.refresh_task_list)
        self.clear_completed_btn = QPushButton("清除已完成")
        self.clear_completed_btn.clicked.connect(self.clear_completed_tasks)
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addWidget(self.clear_completed_btn)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.close_btn)
        main_layout.addLayout(btn_layout)

        self.refresh_task_list()
        
        # 添加定时器，每3秒自动刷新任务状态
        from PyQt5.QtCore import QTimer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_task_list)
        self.timer.start(3000)  # 3秒刷新一次

    def refresh_task_list(self):
        current_scroll_pos = self.task_list.verticalScrollBar().value()
        current_selection = None
        if self.task_list.currentItem():
            current_selection = self.task_list.currentItem().data(Qt.UserRole)
        
        self.task_list.clear()
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
            item_layout.setContentsMargins(15, 15, 15, 15)
            item_layout.setSpacing(8)
            item_widget.setStyleSheet("border: 1px solid #e2e8f0; border-radius: 8px; background-color: #f8fafc;")

            title_layout = QHBoxLayout()
            title_label = QLabel(f"{title}")
            title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            title_label.setWordWrap(True)
            
            status_map = {
                "completed": "已完成",
                "failed": "失败",
                "downloading": "下载中",
                "pending": "待处理",
                "unknown": "未知"
            }
            status_text = status_map.get(status, "未知")
            status_label = QLabel(f"状态：{status_text}")
            if status == "completed":
                status_label.setStyleSheet("color: #52c41a; font-weight: 500;")
            elif status == "failed":
                status_label.setStyleSheet("color: #f56c6c; font-weight: 500;")
            elif status == "downloading":
                status_label.setStyleSheet("color: #1890ff; font-weight: 500;")
            elif status == "pending":
                status_label.setStyleSheet("color: #fa8c16; font-weight: 500;")
            
            title_layout.addWidget(title_label, stretch=1)
            title_layout.addWidget(status_label)
            
            duration = task.get("duration", "")
            if duration:
                duration_label = QLabel(f"耗时：{duration}")
                duration_label.setStyleSheet("font-size: 12px; color: #64748b;")
                title_layout.addWidget(duration_label)
            item_layout.addLayout(title_layout)

            progress_layout = QHBoxLayout()
            progress_label = QLabel(f"进度：{progress}%")
            progress_bar = QProgressBar()
            progress_bar.setRange(0, 100)
            progress_bar.setValue(progress)
            progress_bar.setFixedHeight(8)
            progress_bar.setStyleSheet("QProgressBar { border-radius: 4px; background-color: #e2e8f0; } QProgressBar::chunk { border-radius: 4px; background-color: #409eff; }")
            progress_layout.addWidget(progress_label)
            progress_layout.addWidget(progress_bar, stretch=1)
            item_layout.addLayout(progress_layout)

            info_layout = QHBoxLayout()
            path_label = QLabel(f"保存路径：{save_path[:60]}..." if len(save_path) > 60 else f"保存路径：{save_path}")
            path_label.setToolTip(save_path)
            path_label.setWordWrap(True)
            
            if save_path:
                open_dir_btn = QPushButton("打开目录")
                open_dir_btn.setStyleSheet("background-color: #94a3b8; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px;")
                open_dir_btn.clicked.connect(lambda checked, p=save_path: self.open_directory(p))
                info_layout.addWidget(open_dir_btn)
            
            info_layout.addWidget(path_label, stretch=1)
            item_layout.addLayout(info_layout)

            url_layout = QHBoxLayout()
            url_text = url[:100] + "..." if len(url) > 100 else url
            url_label = QLabel(f"原始链接：")
            url_link = QLabel(f"<a href='{url}'>{url_text}</a>")
            url_link.setOpenExternalLinks(True)
            url_link.setToolTip(f"点击打开链接\n右键复制链接")
            
            copy_btn = QPushButton("复制链接")
            copy_btn.setStyleSheet("background-color: #64748b; color: white; padding: 4px 8px; border-radius: 3px; font-size: 12px;")
            copy_btn.clicked.connect(lambda checked, u=url: self.copy_to_clipboard(u))
            
            url_layout.addWidget(url_label)
            url_layout.addWidget(url_link, stretch=1)
            url_layout.addWidget(copy_btn)
            item_layout.addLayout(url_layout)

            if error_message:
                error_layout = QHBoxLayout()
                error_label = QLabel(f"错误：{error_message[:120]}..." if len(error_message) > 120 else f"错误：{error_message}")
                error_label.setStyleSheet("color: #f56c6c;")
                error_label.setToolTip(error_message)
                error_label.setWordWrap(True)
                error_layout.addWidget(error_label, stretch=1)
                item_layout.addLayout(error_layout)

            btn_layout = QHBoxLayout()
            if status == "downloading":
                open_download_btn = QPushButton("查看下载")
                open_download_btn.setStyleSheet("background-color: #1890ff; color: white; padding: 6px 12px; border-radius: 4px;")
                open_download_btn.clicked.connect(lambda checked, t=task: self.open_download_window(t))
                btn_layout.addWidget(open_download_btn)
                btn_layout.addSpacing(10)
                stop_btn = QPushButton("停止下载")
                stop_btn.setStyleSheet("background-color: #f56c6c; color: white; padding: 6px 12px; border-radius: 4px;")
                stop_btn.clicked.connect(lambda checked, t=task: self.stop_task(t))
                btn_layout.addWidget(stop_btn)
                btn_layout.addSpacing(10)
            elif status in ["failed", "pending"]:
                resume_btn = QPushButton("继续下载")
                resume_btn.setStyleSheet("background-color: #52c41a; color: white; padding: 6px 12px; border-radius: 4px;")
                resume_btn.clicked.connect(lambda checked, t=task: self.resume_task(t))
                btn_layout.addWidget(resume_btn)
                btn_layout.addSpacing(10)
            delete_btn = QPushButton("删除任务")
            delete_btn.setStyleSheet("background-color: #f56c6c; color: white; padding: 6px 12px; border-radius: 4px;")
            delete_btn.clicked.connect(lambda checked, tid=task_id: self.delete_task(tid))
            btn_layout.addWidget(delete_btn)
            btn_layout.addStretch(1)
            item_layout.addLayout(btn_layout)

            list_item = QListWidgetItem()
            item_widget.adjustSize()
            min_height = max(200, item_widget.sizeHint().height() + 20)
            list_item.setSizeHint(QSize(0, min_height))
            list_item.setData(Qt.UserRole, task)
            self.task_list.addItem(list_item)
            self.task_list.setItemWidget(list_item, item_widget)
            
            if current_selection and task_id == current_selection.get("id"):
                self.task_list.setCurrentItem(list_item)
        
        try:
            self.task_list.itemClicked.disconnect()
        except:
            pass
        self.task_list.itemClicked.connect(self.on_task_clicked)
        
        self.task_list.verticalScrollBar().setValue(current_scroll_pos)

    def resume_task(self, task):
        # 准备下载参数
        download_params = {
            "url": task.get("url", ""),
            "video_info": task.get("video_info", {}),
            "qn": task.get("qn", ""),
            "save_path": task.get("save_path", ""),
            "episodes": task.get("episodes", []),
            "resume_download": True
        }

        # 开始下载
        self.download_manager.start_download(download_params)
        
        # 创建并显示批量下载窗口
        batch_window = BatchDownloadWindow(task.get("video_info", {}), len(task.get("episodes", [])))
        episodes = task.get("episodes", [])
        for i, ep in enumerate(episodes):
            if task.get("video_info", {}).get("is_bangumi"):
                ep_name = f"{ep.get('ep_index', '')}"
                ep_tooltip = ep.get('ep_title', '')
            else:
                ep_name = f"第{ep.get('page', i+1)}集"
                ep_tooltip = ep.get('title', '')
            batch_window.add_episode_progress(ep_name, ep_tooltip)
        batch_window.cancel_all.connect(lambda: self.download_manager.cancel_all())
        batch_window.show()
        
        self.refresh_task_list()

    def delete_task(self, task_id):
        self.task_manager.delete_task(task_id)
        self.refresh_task_list()

    def clear_completed_tasks(self):
        self.task_manager.clear_completed_tasks()
        self.refresh_task_list()

    def open_directory(self, path):
        import os
        import subprocess
        try:
            if os.name == 'nt':  # Windows
                # 修复Windows路径处理，使用正确的引号
                subprocess.run(['explorer', os.path.normpath(path)], check=False)
            elif os.name == 'posix':  # macOS or Linux
                subprocess.run(['open', path] if sys.platform == 'darwin' else ['xdg-open', path], check=True)
        except Exception as e:
            print(f"打开目录失败：{str(e)}")

    def copy_to_clipboard(self, text):
        from PyQt5.QtWidgets import QApplication
        try:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
        except Exception as e:
            logger.error(f"复制到剪贴板失败：{str(e)}")

    def on_task_clicked(self, item):
        task = item.data(Qt.UserRole)
        if not task:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"任务详情 - {task.get('title', '未知任务')}")
        dialog.setMinimumSize(800, 600)
        dialog.setStyleSheet(BASE_STYLE)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 基本信息
        info_group = QGroupBox("基本信息")
        info_layout = QVBoxLayout(info_group)
        
        # 任务标题
        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("任务标题："))
        title_label = QLabel(task.get('title', '未知'))
        title_label.setWordWrap(True)
        title_layout.addWidget(title_label, stretch=1)
        info_layout.addLayout(title_layout)
        
        # 下载链接
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("下载链接："))
        url_text = task.get('url', '')
        url_link = QLabel(f"<a href='{url_text}'>{url_text[:150]}...</a>")
        url_link.setOpenExternalLinks(True)
        url_layout.addWidget(url_link, stretch=1)
        copy_url_btn = QPushButton("复制")
        copy_url_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        copy_url_btn.clicked.connect(lambda: self.copy_to_clipboard(url_text))
        url_layout.addWidget(copy_url_btn)
        info_layout.addLayout(url_layout)
        
        # 保存路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("保存路径："))
        path_text = task.get('save_path', '')
        path_label = QLabel(path_text[:150] + "...")
        path_label.setToolTip(path_text)
        path_layout.addWidget(path_label, stretch=1)
        open_path_btn = QPushButton("打开")
        open_path_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        open_path_btn.clicked.connect(lambda: self.open_directory(path_text))
        path_layout.addWidget(open_path_btn)
        info_layout.addLayout(path_layout)
        
        # 分辨率
        qn = task.get('qn', '')
        if qn:
            qn_layout = QHBoxLayout()
            qn_layout.addWidget(QLabel("分辨率："))
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
            qn_layout.addWidget(QLabel(qn_text))
            info_layout.addLayout(qn_layout)
        
        # 任务状态
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("任务状态："))
        status_map = {
            "completed": "已完成",
            "failed": "失败",
            "downloading": "下载中",
            "pending": "待处理",
            "unknown": "未知"
        }
        status_text = status_map.get(task.get('status', 'unknown'), '未知')
        status_layout.addWidget(QLabel(status_text))
        info_layout.addLayout(status_layout)
        
        # 下载耗时
        duration = task.get('duration', '')
        if duration:
            duration_layout = QHBoxLayout()
            duration_layout.addWidget(QLabel("下载耗时："))
            duration_layout.addWidget(QLabel(duration))
            info_layout.addLayout(duration_layout)
        
        # 错误信息
        error_msg = task.get('error_message', '')
        if error_msg:
            error_layout = QHBoxLayout()
            error_layout.addWidget(QLabel("错误信息："))
            error_label = QLabel(error_msg[:200] + "...")
            error_label.setToolTip(error_msg)
            error_label.setStyleSheet("color: #f56c6c;")
            error_layout.addWidget(error_label, stretch=1)
            info_layout.addLayout(error_layout)
        
        main_layout.addWidget(info_group)

        # 下载文件列表
        files_group = QGroupBox("下载文件")
        files_layout = QVBoxLayout(files_group)
        
        # 添加搜索筛选功能
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索：")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("输入关键词筛选文件")
        self.search_edit.textChanged.connect(lambda text: self.filter_file_list(text, episodes, task, is_bangumi))
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_edit)
        files_layout.addLayout(search_layout)
        
        # 使用QListWidget展示文件列表
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.SingleSelection)
        self.file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_file_context_menu)
        files_layout.addWidget(self.file_list, stretch=1)
        
        episodes = task.get('episodes', [])
        video_info = task.get('video_info', {})
        is_bangumi = video_info.get('is_bangumi', task.get('is_bangumi', False))
        
        # 存储文件数据
        self.file_data = []
        
        if episodes:
            for i, ep in enumerate(episodes):
                if is_bangumi:
                    ep_index = ep.get('ep_index', '')
                    ep_title = ep.get('ep_title', '') or ep.get('title', '') or ep.get('name', '')
                    ep_name = f"{ep_index} - {ep_title}"
                else:
                    page = ep.get('page', i+1)
                    ep_title = ep.get('title', '') or ep.get('ep_title', '') or ep.get('name', '')
                    ep_name = f"第{page}集 - {ep_title}"
                
                # 实时检测文件是否存在
                file_exists = False
                try:
                    # 构建文件路径
                    clean_title = ep_name.replace(' - ', '_')
                    for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                        clean_title = clean_title.replace(c, '_')
                    file_path = os.path.join(task.get('save_path', ''), f"{clean_title}.mp4")
                    file_exists = os.path.exists(file_path)
                except:
                    pass
                
                # 存储文件数据
                file_item_data = {
                    'ep': ep,
                    'ep_name': ep_name,
                    'file_path': file_path,
                    'file_exists': file_exists,
                    'task': task
                }
                self.file_data.append(file_item_data)
                
                # 创建列表项
                list_item = QListWidgetItem(ep_name)
                if not file_exists:
                    list_item.setFlags(list_item.flags() & ~Qt.ItemIsEnabled)
                    list_item.setForeground(QColor('#94a3b8'))
                    list_item.setToolTip("文件已被移动或删除")
                list_item.setData(Qt.UserRole, file_item_data)
                self.file_list.addItem(list_item)
        else:
            self.file_list.addItem("无下载文件信息")
        
        main_layout.addWidget(files_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        if task.get('status') in ['failed', 'pending']:
            resume_btn = QPushButton("继续下载")
            resume_btn.setStyleSheet("background-color: #52c41a; color: white;")
            resume_btn.clicked.connect(lambda: (self.resume_task(task), dialog.accept()))
            btn_layout.addWidget(resume_btn)
        
        delete_btn = QPushButton("删除任务")
        delete_btn.setStyleSheet("background-color: #f56c6c; color: white;")
        delete_btn.clicked.connect(lambda: (self.delete_task(task.get('id')), dialog.accept()))
        btn_layout.addWidget(delete_btn)
        
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(close_btn)
        
        btn_layout.addStretch(1)
        main_layout.addLayout(btn_layout)

        dialog.exec_()

    def filter_file_list(self, text, episodes, task, is_bangumi):
        """根据搜索关键词筛选文件列表"""
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
        """显示文件列表的右键菜单"""
        item = self.file_list.itemAt(position)
        if not item:
            return
        
        file_data = item.data(Qt.UserRole)
        if not file_data:
            return
        
        menu = QMenu()
        
        # 打开文件菜单项
        if file_data['file_exists']:
            open_action = menu.addAction("打开文件")
            open_action.triggered.connect(lambda: self.open_file(file_data['file_path']))
        
        # 重新下载菜单项
        redownload_action = menu.addAction("重新下载")
        redownload_action.triggered.connect(lambda: self.redownload_episode(file_data['ep'], file_data['task']))
        
        # 显示菜单
        menu.exec_(self.file_list.mapToGlobal(position))

    def open_file(self, file_path):
        import subprocess
        try:
            if os.name == 'nt':  # Windows
                subprocess.run(['explorer', '/select,', file_path], check=False)
            elif os.name == 'posix':  # macOS or Linux
                subprocess.run(['open', file_path] if sys.platform == 'darwin' else ['xdg-open', os.path.dirname(file_path)], check=False)
        except Exception as e:
            print(f"打开文件失败：{str(e)}")

    def redownload_episode(self, episode, task):
        # 准备单个剧集的下载参数
        download_params = {
            "url": task.get("url", ""),
            "video_info": task.get("video_info", {}),
            "qn": task.get("qn", ""),
            "save_path": task.get("save_path", ""),
            "episodes": [episode],  # 只包含单个剧集
            "resume_download": True
        }

        # 开始下载
        self.download_manager.start_download(download_params)
        
        # 创建并显示批量下载窗口
        batch_window = BatchDownloadWindow(task.get("video_info", {}), 1)
        video_info = task.get("video_info", {})
        is_bangumi = video_info.get("is_bangumi", False)
        
        if is_bangumi:
            ep_name = f"{episode.get('ep_index', '')}"
            ep_tooltip = episode.get('ep_title', '')
        else:
            ep_name = f"第{episode.get('page', 1)}集"
            ep_tooltip = episode.get('title', '')
        
        batch_window.add_episode_progress(ep_name, ep_tooltip)
        batch_window.cancel_all.connect(lambda: self.download_manager.cancel_all())
        batch_window.show()

    def open_download_window(self, task):
        batch_window = BatchDownloadWindow(task.get("video_info", {}), len(task.get("episodes", [])))
        episodes = task.get("episodes", [])
        video_info = task.get("video_info", {})
        is_bangumi = video_info.get("is_bangumi", False)
        
        for i, ep in enumerate(episodes):
            if is_bangumi:
                ep_name = f"{ep.get('ep_index', '')}"
                ep_tooltip = ep.get('ep_title', '')
            else:
                ep_name = f"第{ep.get('page', i+1)}集"
                ep_tooltip = ep.get('title', '')
            batch_window.add_episode_progress(ep_name, ep_tooltip)
        batch_window.cancel_all.connect(lambda: self.download_manager.cancel_all())
        batch_window.show()

    def stop_task(self, task):
        self.download_manager.cancel_all()
        if self.task_manager:
            self.task_manager.update_task_status(task.get("id"), "failed", "任务已停止")
        self.refresh_task_list()

    def closeEvent(self, event):
        if hasattr(self, 'timer'):
            self.timer.stop()
        event.accept()


class BatchDownloadWindow(QMainWindow):
    cancel_all = pyqtSignal()
    window_closed = pyqtSignal()

    def __init__(self, video_info, total_episodes):
        super().__init__()
        self.video_info = video_info
        self.total_episodes = total_episodes
        self.completed = 0
        self.failed = []
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle(f"批量下载 - 共{self.total_episodes}集")
        self.setGeometry(200, 200, 750, 450)
        self.setMinimumSize(700, 400)
        self.setStyleSheet(BASE_STYLE)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(12)

        title_label = QLabel(f"批量下载 - {self.video_info.get('title', '未知视频')}")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #2563eb;")
        main_layout.addWidget(title_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(8)
        self.scroll_area.setWidget(scroll_content)
        main_layout.addWidget(self.scroll_area, stretch=1)

        self.global_progress = QProgressBar()
        self.global_progress.setRange(0, 100)
        main_layout.addWidget(self.global_progress)

        self.cancel_btn = QPushButton("取消全部下载")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.cancel_btn)
        main_layout.addLayout(btn_layout)

        self.progress_bars = []
        self.status_labels = []

    def add_episode_progress(self, ep_name, ep_tooltip):
        group = QGroupBox(ep_name)
        group.setToolTip(ep_tooltip)
        group_layout = QHBoxLayout(group)
        group_layout.setSpacing(10)

        progress = QProgressBar()
        progress.setRange(0, 100)
        status = QLabel("等待下载...")
        status.setStyleSheet("color: #6b7280; font-size: 12px;")

        group_layout.addWidget(progress, stretch=1)
        group_layout.addWidget(status)
        self.scroll_layout.addWidget(group)

        self.progress_bars.append(progress)
        self.status_labels.append(status)

    def update_episode_progress(self, index, progress, status):
        if 0 <= index < len(self.progress_bars):
            self.progress_bars[index].setValue(progress)
            self.status_labels[index].setText(status)

    def finish_episode(self, index, success, message):
        self.completed += 1
        self.global_progress.setValue(int((self.completed / self.total_episodes) * 100))

        if success:
            self.status_labels[index].setText(f"√ 下载完成 - {message}")
            self.status_labels[index].setStyleSheet("color: #52c41a; font-size: 12px;")
        else:
            self.status_labels[index].setText(f"× 失败：{message[:20]}...")
            self.status_labels[index].setStyleSheet("color: #f56c6c; font-size: 12px;")
            self.failed.append(message)

        if self.completed == self.total_episodes:
            self.cancel_btn.setText("关闭窗口")
            self.cancel_btn.clicked.disconnect()
            self.cancel_btn.clicked.connect(self.close)

            if self.failed:
                msg = f"下载完成！\n成功：{self.total_episodes - len(self.failed)}集\n失败：{len(self.failed)}集"
                QMessageBox.warning(self, "下载结果", msg)
            else:
                QMessageBox.information(self, "下载结果", "全部集数下载成功！")

    def on_cancel(self):
        self.cancel_all.emit()
        self.close()

    def closeEvent(self, event):
        # 关闭窗口时不取消下载任务，只发送窗口关闭信号
        self.window_closed.emit()
        event.accept()


class BilibiliDownloader(QMainWindow):
    def __init__(self, config, task_manager=None, download_manager=None):
        super().__init__()
        self.signal_emitter = SignalEmitter()
        self.config = config
        self.task_manager = task_manager
        self.download_manager = download_manager
        self.current_video_info = None
        self.cookie_file = "cookie.txt"
        self.bilibili_space = "https://space.bilibili.com/3546841002019157"
        self.temp_dir = "temp"
        self.init_ui()
        self.load_local_cookie()

    def init_ui(self):
        self.setWindowTitle("B站视频解析下载工具 - 作者：寒烟似雪(逸雨) QQ：2273962061/3241417097")
        self.setGeometry(100, 100, 900, 800)
        self.setMinimumSize(850, 750)
        self.setStyleSheet(BASE_STYLE)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(25, 20, 25, 20)
        main_layout.setSpacing(15)

        title_label = QLabel("B站视频解析下载工具 - 作者：寒烟似雪(逸雨) QQ：2273962061/3241417097")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #2563eb; text-align: center;")
        title_label.setWordWrap(True)
        main_layout.addWidget(title_label)

        bilibili_layout = QHBoxLayout()
        bilibili_label = QLabel("哔哩哔哩：不会玩python的man")
        bilibili_label.setObjectName("bilibiliLabel")
        bilibili_label.setStyleSheet("color: #00a1d6; text-decoration: underline;")
        bilibili_label.setCursor(QCursor(Qt.PointingHandCursor))
        bilibili_label.mousePressEvent = lambda e: webbrowser.open(self.bilibili_space)
        
        self.bilibili_btn = QPushButton("访问主页")
        self.bilibili_btn.setObjectName("bilibiliBtn")
        self.bilibili_btn.clicked.connect(lambda: webbrowser.open(self.bilibili_space))
        
        bilibili_layout.addStretch(1)
        bilibili_layout.addWidget(bilibili_label)
        bilibili_layout.addWidget(self.bilibili_btn)
        main_layout.addLayout(bilibili_layout)

        sys_info_group = QGroupBox("系统信息")
        sys_layout = QVBoxLayout(sys_info_group)
        sys_layout.setSpacing(8)

        login_layout = QHBoxLayout()
        login_layout.addWidget(QLabel("登录状态："))
        self.user_info_label = QLabel("加载中...")
        self.vip_label = QLabel()
        login_layout.addWidget(self.user_info_label, stretch=1)
        login_layout.addWidget(self.vip_label)
        sys_layout.addLayout(login_layout)

        hevc_layout = QHBoxLayout()
        hevc_layout.addWidget(QLabel("HEVC支持："))
        self.hevc_label = QLabel("检测中...")
        self.hevc_btn = QPushButton("安装HEVC扩展")
        self.hevc_btn.setObjectName("hevcBtn")
        self.hevc_btn.setEnabled(False)
        self.hevc_btn.clicked.connect(lambda: self.signal_emitter.install_hevc.emit())
        hevc_layout.addWidget(self.hevc_label, stretch=1)
        hevc_layout.addWidget(self.hevc_btn)
        sys_layout.addLayout(hevc_layout)

        main_layout.addWidget(sys_info_group)

        cookie_group = QGroupBox("Cookie设置")
        cookie_layout = QVBoxLayout(cookie_group)
        cookie_layout.setSpacing(10)

        self.cookie_edit = QTextEdit()
        self.cookie_edit.setPlaceholderText("请输入Cookie（SESSDATA/bili_jct/DedeUserID）")
        self.cookie_edit.setMaximumHeight(180)
        cookie_layout.addWidget(self.cookie_edit)

        btn_layout = QHBoxLayout()
        self.apply_cookie_btn = QPushButton("验证并保存")
        self.apply_cookie_btn.setObjectName("applyCookieBtn")
        self.apply_cookie_btn.clicked.connect(self.on_apply_cookie)
        self.clear_cookie_btn = QPushButton("清空")
        self.clear_cookie_btn.setStyleSheet("background-color: #919191;")
        self.clear_cookie_btn.clicked.connect(self.on_clear_cookie)
        btn_layout.addWidget(self.apply_cookie_btn)
        btn_layout.addWidget(self.clear_cookie_btn)
        btn_layout.addStretch(1)
        cookie_layout.addLayout(btn_layout)

        self.cookie_status = QLabel("状态：未输入Cookie")
        self.cookie_status.setStyleSheet("font-size: 11px; color: #6b7280;")
        cookie_layout.addWidget(self.cookie_status)
        main_layout.addWidget(cookie_group)

        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("视频链接："))
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("支持BV/ss/av号")
        self.parse_btn = QPushButton("解析链接")
        self.parse_btn.clicked.connect(self.on_parse)
        url_layout.addWidget(self.url_edit, stretch=1)
        url_layout.addWidget(self.parse_btn)
        main_layout.addLayout(url_layout)

        self.tv_mode_checkbox = QCheckBox("TV端无水印模式")
        main_layout.addWidget(self.tv_mode_checkbox)

        result_group = QGroupBox("解析结果")
        result_layout = QVBoxLayout(result_group)
        result_layout.setSpacing(12)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("标题："), alignment=Qt.AlignTop)
        self.video_title = QLabel("未解析")
        self.video_title.setWordWrap(True)
        title_layout.addWidget(self.video_title, stretch=1)
        result_layout.addLayout(title_layout)

        self.select_episode_btn = QPushButton("选择集数")
        self.select_episode_btn.setEnabled(False)
        self.select_episode_btn.clicked.connect(self.open_episode_selection)
        result_layout.addWidget(self.select_episode_btn)

        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("清晰度："))
        self.quality_combo = QComboBox()
        self.quality_combo.setEnabled(False)
        quality_layout.addWidget(self.quality_combo, stretch=1)
        result_layout.addLayout(quality_layout)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("保存路径："))
        self.path_edit = QLineEdit()
        # 从配置文件读取上次使用的保存路径
        last_path = self.config.get_app_setting("last_save_path")
        default_path = last_path if last_path else os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        os.makedirs(default_path, exist_ok=True)
        self.path_edit.setText(default_path)
        self.browse_btn = QPushButton("浏览")
        self.browse_btn.clicked.connect(self.browse_path)
        path_layout.addWidget(self.path_edit, stretch=1)
        path_layout.addWidget(self.browse_btn)
        result_layout.addLayout(path_layout)
        main_layout.addWidget(result_group)

        progress_layout = QVBoxLayout()
        self.main_progress = QProgressBar()
        self.main_progress.setRange(0, 100)
        progress_layout.addWidget(self.main_progress)
        self.status_label = QLabel("就绪 - 请输入链接并解析")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        progress_layout.addWidget(self.status_label)
        main_layout.addLayout(progress_layout)

        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self.on_download)
        self.cancel_btn = QPushButton("取消下载")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.on_cancel_download)
        self.task_manager_btn = QPushButton("任务管理")
        self.task_manager_btn.setStyleSheet("background-color: #722ed1;")
        self.task_manager_btn.clicked.connect(self.open_task_manager)
        self.settings_btn = QPushButton("设置")
        self.settings_btn.setStyleSheet("background-color: #94a3b8;")
        self.settings_btn.clicked.connect(self.open_settings)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(self.task_manager_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(self.settings_btn)
        main_layout.addLayout(btn_layout)

        self.signal_emitter.user_info_updated.connect(self.update_user_info)
        self.signal_emitter.hevc_checked.connect(self.update_hevc_status)
        self.signal_emitter.hevc_download_progress.connect(self.update_hevc_progress)
        self.signal_emitter.hevc_install_finished.connect(self.on_hevc_install_finish)
        self.signal_emitter.parse_finished.connect(self.on_parse_finished)
        self.signal_emitter.cookie_verified.connect(self.on_cookie_verified)
        self.signal_emitter.download_progress.connect(self.update_download_progress)

        self.selected_episodes = []

    def load_local_cookie(self):
        if os.path.exists(self.cookie_file):
            try:
                with open(self.cookie_file, "r", encoding="utf-8") as f:
                    cookie = f.read().strip()
                    if cookie:
                        self.cookie_edit.setText(cookie)
                        self.cookie_status.setText("状态：已加载本地Cookie（未验证）")
                        # self.signal_emitter.verify_cookie.emit(cookie)
            except Exception as e:
                self.cookie_status.setText(f"状态：本地Cookie读取失败：{str(e)[:15]}")

    def on_apply_cookie(self):
        cookie = self.cookie_edit.toPlainText().strip()
        if not cookie:
            QMessageBox.warning(self, "提示", "请输入有效的Cookie信息")
            return
        self.cookie_status.setText("状态：正在验证...")
        self.apply_cookie_btn.setEnabled(False)
        self.signal_emitter.verify_cookie.emit(cookie)

    def on_clear_cookie(self):
        reply = QMessageBox.question(self, "确认", "确定要清空Cookie并删除本地文件吗？", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.cookie_edit.clear()
            if os.path.exists(self.cookie_file):
                try:
                    os.remove(self.cookie_file)
                except Exception as e:
                    QMessageBox.warning(self, "失败", f"删除Cookie文件失败，请检查文件权限")
            self.cookie_status.setText("状态：未输入Cookie")
            self.signal_emitter.verify_cookie.emit("")
            self.update_user_info({"success": False, "msg": "未登录", "is_vip": False})

    def on_cookie_verified(self, success, msg):
        self.apply_cookie_btn.setEnabled(True)
        if success:
            cookie = self.cookie_edit.toPlainText().strip()
            try:
                with open(self.cookie_file, "w", encoding="utf-8") as f:
                    f.write(cookie)
                self.cookie_status.setText(f"状态：验证成功（{msg}）")
                QMessageBox.information(self, "成功", f"Cookie验证通过啦！\n{msg}")
                self.signal_emitter.load_user_info.emit()
            except Exception as e:
                self.cookie_status.setText(f"状态：验证成功，保存失败：{str(e)[:15]}")
        else:
            self.cookie_status.setText(f"状态：验证失败：{msg[:20]}")
            QMessageBox.warning(self, "失败", f"Cookie验证失败了：{msg}")

    def on_parse(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入有效的视频链接")
            return
        self.clear_parse_result()
        self.parse_btn.setEnabled(False)
        self.video_title.setText("解析中...")
        self.status_label.setText("正在解析链接...")
        self.signal_emitter.parse_start.emit(url, self.tv_mode_checkbox.isChecked())

    def clear_parse_result(self):
        self.video_title.setText("未解析")
        self.quality_combo.clear()
        self.quality_combo.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.select_episode_btn.setEnabled(False)
        self.selected_episodes = []
        self.select_episode_btn.setText("选择集数")

    def on_parse_finished(self, result):
        self.parse_btn.setEnabled(True)
        self.main_progress.setValue(0)
        if not result.get("success"):
            error_msg = result.get("error", "未知错误")
            self.video_title.setText("解析失败")
            self.status_label.setText(f"解析失败：{error_msg[:30]}")
            QMessageBox.warning(self, "解析失败", f"视频解析失败了：{error_msg}")
            return

        self.current_video_info = result
        self.video_title.setText(result.get("title", "未知标题"))
        self.status_label.setText("解析成功，请选择集数、清晰度并开始下载")

        if result.get("qualities"):
            for qn, name in result["qualities"]:
                if qn in [112, 120, 125, 127]:
                    self.quality_combo.addItem(f"{name}（会员）", qn)
                else:
                    self.quality_combo.addItem(name, qn)
            self.quality_combo.setEnabled(True)
            self.download_btn.setEnabled(True)
            self.cancel_btn.setEnabled(True)

        self.select_episode_btn.setEnabled(True)

    def open_episode_selection(self):
        if not self.current_video_info:
            return
        is_bangumi = self.current_video_info.get("is_bangumi", False)
        episodes = []
        if is_bangumi:
            episodes = self.current_video_info["bangumi_info"].get("episodes", [])
        else:
            episodes = self.current_video_info.get("collection", [])
        if not episodes:
            QMessageBox.information(self, "提示", "这个视频没有分集可以选择哦")
            return

        dialog = EpisodeSelectionDialog(self, episodes, is_bangumi)
        if dialog.exec_() == QDialog.Accepted:
            self.selected_episodes = dialog.selected_episodes
            self.select_episode_btn.setText(f"已选{len(self.selected_episodes)}集")
            self.select_episode_btn.setToolTip("点击修改集数选择")

    def on_download(self):
        if not self.current_video_info:
            QMessageBox.warning(self, "提示", "请先解析视频链接哦")
            return
        if not self.selected_episodes:
            QMessageBox.warning(self, "提示", "请先选择要下载的集数哦")
            return
        if self.quality_combo.currentIndex() == -1:
            QMessageBox.warning(self, "提示", "请选择视频清晰度哦")
            return
        selected_qn = self.quality_combo.itemData(self.quality_combo.currentIndex())
        save_path = self.path_edit.text().strip()
        if not save_path:
            QMessageBox.warning(self, "提示", "请选择视频保存路径哦")
            return
        os.makedirs(save_path, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        download_params = {
            "url": self.url_edit.text().strip(),
            "video_info": self.current_video_info,
            "qn": selected_qn,
            "save_path": save_path,
            "episodes": self.selected_episodes,
            "resume_download": True
        }
        self.signal_emitter.start_download.emit(download_params)
        self.batch_window = BatchDownloadWindow(self.current_video_info, len(self.selected_episodes))
        for ep in self.selected_episodes:
            if self.current_video_info.get("is_bangumi"):
                ep_name = f"{ep['ep_index']}"
                ep_tooltip = ep['ep_title']
            else:
                ep_name = f"第{ep['page']}集"
                ep_tooltip = ep['title']
            self.batch_window.add_episode_progress(ep_name, ep_tooltip)
        self.batch_window.cancel_all.connect(self.on_cancel_download)
        self.batch_window.window_closed.connect(self.on_batch_window_closed)
        self.batch_window.show()
        self.download_btn.setEnabled(False)

    def on_cancel_download(self):
        self.signal_emitter.cancel_download.emit()
        self.cleanup_temp_files()

    def cleanup_temp_files(self):
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                os.makedirs(self.temp_dir, exist_ok=True)
            except Exception as e:
                print(f"清理临时文件失败：{str(e)}")

    def update_user_info(self, user_info):
        if user_info.get("success"):
            self.user_info_label.setText(f"已登录：{user_info['msg']}")
            if user_info.get("is_vip"):
                self.vip_label.setText("√ 会员")
                self.vip_label.setStyleSheet("color: #faad14;")
            else:
                self.vip_label.setText("× 普通用户")
                self.vip_label.setStyleSheet("color: #6b7280;")
        else:
            self.user_info_label.setText(user_info.get("msg", "未登录"))
            self.vip_label.setText("× 未登录")
            self.vip_label.setStyleSheet("color: #6b7280;")

    def update_hevc_status(self, supported):
        if supported:
            self.hevc_label.setText("√ 已支持HEVC（HDR/杜比视界）")
            self.hevc_label.setStyleSheet("color: #52c41a;")
        else:
            self.hevc_label.setText("× 未支持HEVC（需安装扩展）")
            self.hevc_label.setStyleSheet("color: #fa8c16;")
        # 始终启用HEVC扩展按钮，方便用户随时安装或更新
        self.hevc_btn.setEnabled(True)

    def update_hevc_progress(self, progress):
        self.main_progress.setValue(progress)
        self.status_label.setText(f"下载HEVC扩展：{progress}%")

    def on_hevc_install_finish(self, success, msg):
        self.main_progress.setValue(0)
        self.hevc_btn.setEnabled(not success)
        if success:
            QMessageBox.information(self, "成功", f"操作成功啦：{msg}")
            self.signal_emitter.check_hevc.emit()
            self.status_label.setText("HEVC扩展安装成功")
        else:
            QMessageBox.warning(self, "失败", f"操作失败了：{msg}")
            self.status_label.setText("HEVC扩展安装失败")

    def update_download_progress(self, progress, status):
        self.main_progress.setValue(progress)
        self.status_label.setText(status)

    def update_episode_progress(self, index, progress, status):
        if hasattr(self, "batch_window") and self.batch_window.isVisible():
            self.batch_window.update_episode_progress(index, progress, status)

    def finish_episode(self, index, success, message):
        if hasattr(self, "batch_window") and self.batch_window.isVisible():
            self.batch_window.finish_episode(index, success, message)

    def on_batch_window_closed(self):
        self.download_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        if hasattr(self, "batch_window"):
            delattr(self, "batch_window")

        self.status_label.setText("下载窗口已关闭，可重新开始下载")

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if path:
            self.path_edit.setText(path)
            # 更新配置文件中的上次保存路径
            self.config.set_app_setting("last_save_path", path)

    def open_task_manager(self):
        if self.task_manager and self.download_manager:
            self.task_window = TaskManagerWindow(self.task_manager, self.parser, self.download_manager)
            self.task_window.show()
        else:
            QMessageBox.warning(self, "提示", "任务管理器初始化失败")

    def open_settings(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("设置")
        dialog.setMinimumSize(500, 300)
        dialog.setStyleSheet(BASE_STYLE)

        main_layout = QVBoxLayout(dialog)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # 默认下载路径设置
        path_group = QGroupBox("默认下载路径")
        path_layout = QVBoxLayout(path_group)
        
        current_default = self.config.get_app_setting("default_save_path")
        if not current_default:
            current_default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
        
        path_edit = QLineEdit(current_default)
        path_layout.addWidget(path_edit)
        
        browse_btn = QPushButton("浏览")
        browse_btn.clicked.connect(lambda: self.browse_settings_path(path_edit))
        path_layout.addWidget(browse_btn)
        
        main_layout.addWidget(path_group)

        # 线程数设置
        thread_group = QGroupBox("下载线程数")
        thread_layout = QVBoxLayout(thread_group)
        
        thread_spin = QComboBox()
        for i in range(1, 11):
            thread_spin.addItem(str(i), i)
        current_threads = self.config.get_app_setting("max_threads", 2)
        thread_spin.setCurrentIndex(current_threads - 1)
        thread_layout.addWidget(thread_spin)
        
        main_layout.addWidget(thread_group)

        # 按钮布局
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        
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
                logger.info(f"线程数已修改为：{new_threads}")
            
            dialog.accept()
        
        save_btn.clicked.connect(on_save)
        cancel_btn.clicked.connect(dialog.reject)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(save_btn)
        btn_layout.addSpacing(10)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)

        dialog.exec_()

    def browse_settings_path(self, line_edit):
        path = QFileDialog.getExistingDirectory(self, "选择默认保存路径")
        if path:
            line_edit.setText(path)


if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))
    ui = BilibiliDownloader()
    ui.show()
    sys.exit(app.exec_())