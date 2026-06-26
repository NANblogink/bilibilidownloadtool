# -*- coding: utf-8 -*-
"""
录播工具托盘管理器
- 独立的系统托盘图标，名称"录播工具"
- 点击显示录制工具条（时长+控制按钮）
- 支持多个同时进行的录制任务
- 气泡通知录制开始/结束
- 归主窗口所有，不依赖子页面生命周期
"""

import os
import sys
import time
import logging

from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt5.QtWidgets import (
    QSystemTrayIcon, QMenu, QAction, QDialog, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QFrame, QApplication,
    QGraphicsDropShadowEffect
)

logger = logging.getLogger(__name__)

try:
    from ui import scale, scale_style
except ImportError:
    def scale(v): return int(v)
    def scale_style(s): return s


class RecordingSession:
    """单个录制会话的信息"""
    def __init__(self, session_id, room_id, title, output_path):
        self.session_id = session_id
        self.room_id = room_id
        self.title = title or f"直播间 {room_id}"
        self.output_path = output_path
        self.start_time = time.time()
        self.paused = False
        self.pause_start_time = None
        self.total_paused_duration = 0

    def get_elapsed_seconds(self):
        if self.paused and self.pause_start_time:
            elapsed = self.pause_start_time - self.start_time - self.total_paused_duration
        else:
            elapsed = time.time() - self.start_time - self.total_paused_duration
        return max(0, int(elapsed))

    def get_elapsed_str(self):
        sec = self.get_elapsed_seconds()
        h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def pause(self):
        if not self.paused:
            self.paused = True
            self.pause_start_time = time.time()

    def resume(self):
        if self.paused and self.pause_start_time:
            self.total_paused_duration += time.time() - self.pause_start_time
            self.paused = False
            self.pause_start_time = None


class RecordingTrayManager(QObject):
    """录播工具托盘管理器（由主窗口持有）"""

    stop_requested = pyqtSignal(str)   # session_id
    pause_requested = pyqtSignal(str)  # session_id
    resume_requested = pyqtSignal(str) # session_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sessions = {}
        self._next_id = 0
        self.tray_icon = None
        self.tray_menu = None
        self._timer = None
        self._panel = None  # 当前显示的工具条面板
        self._init_tray()

    # ==================== 托盘初始化 ====================

    def _init_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统不支持系统托盘")
            return

        self.tray_icon = QSystemTrayIcon()

        # 红色REC图标
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(220, 53, 69))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.setPen(QColor(255, 255, 255))
        font = QFont("Arial", 8, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "REC")
        painter.end()

        self.tray_icon.setIcon(QIcon(pixmap))
        self.tray_icon.setToolTip("录播工具")

        # 右键菜单
        self.tray_menu = QMenu()
        self._rebuild_menu()
        self.tray_icon.setContextMenu(self.tray_menu)

        # 左键点击 → 显示工具条
        self.tray_icon.activated.connect(self._on_tray_activated)

        self.tray_icon.show()

        # 每秒更新
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_display)
        self._timer.start(1000)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_panel()

    # ==================== 菜单 & 显示更新 ====================

    def _rebuild_menu(self):
        self.tray_menu.clear()

        if not self.sessions:
            a = self.tray_menu.addAction("当前无录制任务")
            a.setEnabled(False)
        else:
            for sid, session in self.sessions.items():
                status = "⏸ 暂停中" if session.paused else "● 录制中"
                elapsed = session.get_elapsed_str()
                sub = self.tray_menu.addMenu(f"{status} {session.title} [{elapsed}]")
                if session.paused:
                    sub.addAction("▶ 继续").triggered.connect(
                        lambda checked, s=sid: self.resume_requested.emit(s))
                else:
                    sub.addAction("⏸ 暂停").triggered.connect(
                        lambda checked, s=sid: self.pause_requested.emit(s))
                sub.addAction("⏹ 停止").triggered.connect(
                    lambda checked, s=sid: self.stop_requested.emit(s))
                sub.addAction("📂 文件夹").triggered.connect(
                    lambda checked, p=session.output_path: self._open_folder(p))

        self.tray_menu.addSeparator()
        self.tray_menu.addAction("隐藏").triggered.connect(self._hide_if_no_tasks)

    def _update_display(self):
        if not self.sessions:
            self.tray_icon.setToolTip("录播工具 - 无录制任务")
            return
        active = sum(1 for s in self.sessions.values() if not s.paused)
        paused = len(self.sessions) - active
        parts = []
        if active:
            parts.append(f"{active}个录制中")
        if paused:
            parts.append(f"{paused}个暂停")
        self.tray_icon.setToolTip(f"录播工具 - {'、'.join(parts)}")
        self._rebuild_menu()
        # 同步刷新工具条面板
        if self._panel and not self._panel.isHidden():
            self._panel.refresh()

    # ==================== 工具条面板 ====================

    def show_panel(self):
        """在托盘附近弹出录制工具条"""
        if not self.sessions and not self._panel:
            return

        # 关闭旧面板
        if self._panel:
            self._panel.close()
            self._panel = None

        self._panel = RecordingPanel(self)
        # 定位到托盘图标附近
        geo = QApplication.primaryScreen().availableGeometry()
        tray_geo = self.tray_icon.geometry()
        x = tray_geo.x()
        y = tray_geo.y() - self._panel.height() - 5
        if y < geo.y():
            y = tray_geo.y() + tray_geo.height() + 5
        if x + self._panel.width() > geo.x() + geo.width():
            x = geo.x() + geo.width() - self._panel.width() - 5
        self._panel.move(x, y)
        self._panel.show()
        self._panel.activateWindow()
        self._panel.raise_()

    def close_panel(self):
        if self._panel:
            self._panel.close()
            self._panel = None

    # ==================== 气泡通知 ====================

    def notify(self, title, msg, icon=QSystemTrayIcon.Information):
        """发送气泡通知"""
        if self.tray_icon and QSystemTrayIcon.supportsMessages():
            self.tray_icon.showMessage(title, msg, icon, 5000)

    # ==================== 公共接口 ====================

    def add_session(self, room_id, title, output_path):
        session_id = f"rec_{self._next_id}"
        self._next_id += 1
        session = RecordingSession(session_id, room_id, title, output_path)
        self.sessions[session_id] = session
        if self.tray_icon:
            self.tray_icon.show()
        self._rebuild_menu()
        logger.info(f"[录播工具] 注册会话: {session_id} 房间={room_id}")
        return session_id

    def remove_session(self, session_id):
        if session_id in self.sessions:
            sess = self.sessions.pop(session_id)
            logger.info(f"[录播工具] 移除会话: {session_id} 时长={sess.get_elapsed_str()}")
            self._rebuild_menu()
            if not self.sessions:
                self.tray_icon.setToolTip("录播工具 - 无录制任务")

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def pause_session(self, session_id):
        s = self.sessions.get(session_id)
        if s:
            s.pause()
            self._rebuild_menu()

    def resume_session(self, session_id):
        s = self.sessions.get(session_id)
        if s:
            s.resume()
            self._rebuild_menu()

    def has_active_sessions(self):
        """是否有活跃的录制会话"""
        return bool(self.sessions)

    def get_active_count(self):
        return len(self.sessions)

    def stop_all(self):
        """停止所有录制（退出时调用）"""
        for sid in list(self.sessions.keys()):
            self.stop_requested.emit(sid)

    # ==================== 内部方法 ====================

    def _open_folder(self, filepath):
        try:
            folder = os.path.dirname(os.path.abspath(filepath))
            if os.path.isdir(folder):
                os.startfile(folder)
        except Exception as e:
            logger.warning(f"打开文件夹失败: {e}")

    def _hide_if_no_tasks(self):
        if self.sessions:
            return
        if self.tray_icon:
            self.tray_icon.hide()

    def cleanup(self):
        if self._timer:
            self._timer.stop()
        self.close_panel()
        if self.tray_icon:
            self.tray_icon.hide()


class RecordingPanel(QDialog):
    """点击托盘弹出的录制工具条"""

    def __init__(self, tray_manager, parent=None):
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.tray_manager = tray_manager
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._setup_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start(500)

    def _setup_ui(self):
        # 外层容器（带圆角和阴影）
        container = QFrame(self)
        container.setObjectName("recording_panel_container")
        container.setStyleSheet("""
            QFrame#recording_panel_container {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
            }
        """)
        layout_outer = QVBoxLayout(self)
        layout_outer.setContentsMargins(1, 1, 1, 1)
        layout_outer.addWidget(container)

        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 4)
        container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(container)
        layout.setSpacing(scale(8))
        layout.setContentsMargins(scale(16), scale(14), scale(16), scale(14))

        # 标题栏
        header = QHBoxLayout()
        title_lbl = QLabel("录播工具")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #dc3545;")
        header.addWidget(title_lbl)
        header.addStretch()

        close_btn = QLabel("\u2715")
        close_btn.setStyleSheet(
            "font-size: 14px; color: #999; padding: 4px 6px;"
            "border-radius: 4px;"
        )
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.mousePressEvent = lambda e: self.close()
        header.addWidget(close_btn)
        layout.addLayout(header)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("background: #e9ecef;")
        line.setFixedHeight(1)
        layout.addWidget(line)

        # 会话列表
        self.session_widgets = {}
        sessions = self.tray_manager.sessions
        for sid, session in sessions.items():
            w = self._make_session_widget(sid, session)
            layout.addWidget(w)
            self.session_widgets[sid] = w

        if not sessions:
            lbl = QLabel("当前无录制任务")
            lbl.setStyleSheet("color: #999; font-size: 13px;")
            lbl.setAlignment(Qt.AlignCenter)
            layout.addWidget(lbl)

        # 底部提示
        hint = QLabel("录制将在后台持续进行，关闭此窗口不影响录制")
        hint.setStyleSheet("color: #adb5bd; font-size: 11px;")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        self.setFixedWidth(scale(340))

    def _make_session_widget(self, sid, session):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: #f8f9fa;
                border: 1px solid #e9ecef;
                border-radius: 8px;
            }
        """)
        lyt = QVBoxLayout(frame)
        lyt.setSpacing(scale(5))
        lyt.setContentsMargins(scale(10), scale(8), scale(10), scale(8))

        # 头部：状态 + 标题
        hdr = QHBoxLayout()
        stxt = "已暂停" if session.paused else "正在录制"
        scolor = "#e0a800" if session.paused else "#dc3545"
        sl = QLabel(stxt)
        sl.setStyleSheet(f"font-weight:bold;font-size:12px;color:{scolor};")
        hdr.addWidget(sl)
        tl = QLabel(session.title)
        tl.setStyleSheet("font-weight:bold;font-size:13px;color:#333;")
        hdr.addWidget(tl)
        hdr.addStretch()
        lyt.addLayout(hdr)

        # 大号时长
        tm = QLabel(session.get_elapsed_str())
        tm.setStyleSheet("font-size:26px;font-weight:bold;color:#00a1d6;")
        tm.setAlignment(Qt.AlignCenter)
        lyt.addWidget(tm)

        # 路径
        pl = QLabel(os.path.basename(session.output_path))
        pl.setStyleSheet("color:#888;font-size:11px;")
        pl.setToolTip(session.output_path)
        pl.setAlignment(Qt.AlignCenter)
        lyt.addWidget(pl)

        # 按钮
        btns = QHBoxLayout()
        btns.setSpacing(scale(6))

        if session.paused:
            rb = QPushButton("继续")
            rb.setStyleSheet("""padding:5px 18px;background:#28a745;color:white;
                border:none;border-radius:5px;font-size:12px;font-weight:bold;""")
            rb.clicked.connect(lambda checked, s=sid: self._on_resume(s))
            btns.addWidget(rb)
        else:
            pb = QPushButton("暂停")
            pb.setStyleSheet("""padding:5px 18px;background:#ffc107;color:#333;
                border:none;border-radius:5px;font-size:12px;font-weight:bold;""")
            pb.clicked.connect(lambda checked, s=sid: self._on_pause(s))
            btns.addWidget(pb)

            sb = QPushButton("停止")
            sb.setStyleSheet("""padding:5px 18px;background:#dc3545;color:white;
                border:none;border-radius:5px;font-size:12px;font-weight:bold;""")
            sb.clicked.connect(lambda checked, s=sid: self._on_stop(s))
            btns.addWidget(sb)

        btns.addStretch()
        lyt.addLayout(btns)

        frame._sl = sl
        frame._tm = tm
        return frame

    def _on_stop(self, sid):
        self.tray_manager.stop_requested.emit(sid)
        self.close()

    def _on_pause(self, sid):
        self.tray_manager.pause_requested.emit(sid)
        self.close()

    def _on_resume(self, sid):
        self.tray_manager.resume_requested.emit(sid)
        self.close()

    def refresh(self):
        sessions = self.tray_manager.sessions
        for sid, w in list(self.session_widgets.items()):
            s = sessions.get(sid)
            if not s:
                continue
            w._tm.setText(s.get_elapsed_str())
            stxt = "已暂停" if s.paused else "正在录制"
            scolor = "#e0a800" if s.paused else "#dc3545"
            w._sl.setText(stxt)
            w._sl.setStyleSheet(f"font-weight:bold;font-size:12px;color:{scolor};")

    def closeEvent(self, event):
        self._refresh_timer.stop()
        super().closeEvent(event)
