# -*- coding: utf-8 -*-
"""
B站视频字幕解析 Tab 页
功能：使用主界面全局输入框的视频链接，解析各分P的AI字幕，时间轴预览并下载SRT字幕（需登录，跟随全局解析）
"""

import os
import re
import json
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRect, QTimer, QPoint
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QBrush, QPolygon
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QComboBox,
    QMessageBox, QFileDialog, QCheckBox
)

try:
    import requests
except ImportError:
    requests = None

try:
    from ui import scale, scale_style
except ImportError:
    def scale(v): return int(v)
    def scale_style(s): return s

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
_SUB_HEADERS = {"User-Agent": _UA, "Referer": "https://www.bilibili.com/"}


def _extract_bvid(text):
    if not text:
        return None
    m = re.search(r'BV[0-9A-Za-z]{10}', text)
    if m:
        return m.group(0)
    m2 = re.search(r'(?:av|AV)(\d+)', text)
    if m2:
        return m2.group(1)
    if text.strip().isdigit():
        return text.strip()
    return None


def _fmt_ts(ms):
    return f"{ms // 3600000:02d}:{(ms % 3600000) // 60000:02d}:{(ms % 60000) // 1000:02d},{ms % 1000:03d}"


def _body_to_srt(body):
    if not body:
        return ""
    lines = []
    for idx, item in enumerate(body, 1):
        start_ms = int(float(item.get('from', 0)) * 1000)
        end_ms = int(float(item.get('to', 0)) * 1000)
        lines.append(f"{idx}\n{_fmt_ts(start_ms)} --> {_fmt_ts(end_ms)}\n{item.get('content', '')}\n")
    return "\n".join(lines)


def _safe_filename(name):
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip('. ')


def _new_session(cookies=None):
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Referer": "https://www.bilibili.com"})
    if cookies:
        s.cookies.update(cookies)
    return s


class SubtitleTimeline(QWidget):
    """字幕时间分布时间轴（点击/拖动跳转，带当前位置指示线）"""

    seek_requested = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._duration = 0.0
        self._segments = []
        self._current_pos = 0.0
        self._dragging = False
        self.setMinimumHeight(scale(40))
        self.setMaximumHeight(scale(44))
        self.setMinimumWidth(scale(240))
        self.setMouseTracking(True)

    def set_data(self, duration, segments):
        self._segments = segments or []
        last = 0.0
        for s, e in self._segments:
            last = max(last, e)
        self._duration = max(float(duration or 0), last)
        self._current_pos = 0.0
        self.update()

    def set_current_position(self, pos):
        self._current_pos = max(0.0, min(float(pos or 0), self._duration))
        self.update()

    def _pos_to_time(self, x):
        left, right = scale(10), scale(10)
        span = self.width() - left - right
        if span <= 0 or self._duration <= 0:
            return 0.0
        t = (x - left) / span * self._duration
        return max(0.0, min(t, self._duration))

    def _time_to_x(self, t):
        left, right = scale(10), scale(10)
        span = self.width() - left - right
        if span <= 0 or self._duration <= 0:
            return left
        return left + int(t / self._duration * span)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._duration > 0:
            self._dragging = True
            t = self._pos_to_time(event.pos().x())
            self._current_pos = t
            self.update()
            self.seek_requested.emit(t)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._duration > 0:
            t = self._pos_to_time(event.pos().x())
            self._current_pos = t
            self.update()
            self.seek_requested.emit(t)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top = scale(10), scale(10), scale(9)
        bottom = scale(15)
        plot_h = h - top - bottom
        p.fillRect(QRect(0, 0, w, h), QColor("#f7f9fc"))
        p.setPen(QPen(QColor("#d0d7de"), 1))
        p.drawRect(QRect(left, top, w - left - right, plot_h))
        if self._duration > 0:
            span = w - left - right
            p.setPen(QPen(QColor("#9aa4b2"), 1))
            p.setFont(QFont("Microsoft YaHei", scale(8)))
            for f in (0, 0.25, 0.5, 0.75, 1.0):
                x = left + int(f * span)
                p.drawLine(x, top, x, top + plot_h)
                txt = self._fmt_time(self._duration * f)
                p.drawText(QRect(x - scale(28), top + plot_h + 2, scale(56), scale(14)),
                           Qt.AlignCenter, txt)
            for s, e in self._segments:
                x1 = left + int(s / self._duration * span)
                x2 = left + int(e / self._duration * span)
                if x2 - x1 < 2:
                    x2 = x1 + 2
                p.fillRect(QRect(x1, top + 2, x2 - x1, plot_h - 4), QColor(0, 161, 214, 150))
            # 当前位置指示线（红色）与顶部手柄
            if self._current_pos >= 0:
                x = self._time_to_x(self._current_pos)
                p.setPen(QPen(QColor("#ff4d4f"), 2))
                p.drawLine(x, top, x, top + plot_h)
                handle_sz = scale(5)
                tri = QPolygon([
                    QPoint(x, top - handle_sz),
                    QPoint(x - handle_sz, top),
                    QPoint(x + handle_sz, top),
                ])
                p.setPen(QPen(QColor("#ff4d4f"), 1))
                p.setBrush(QBrush(QColor("#ff4d4f")))
                p.drawPolygon(tri)
        else:
            p.setPen(QPen(QColor("#9aa4b2"), 1))
            p.setFont(QFont("Microsoft YaHei", scale(8)))
            p.drawText(QRect(left, top, w - left - right, plot_h), Qt.AlignCenter, "")

    @staticmethod
    def _fmt_time(sec):
        sec = int(sec)
        m, s = divmod(sec, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"


class SubtitleListThread(QThread):
    """解析视频信息及各分P字幕列表线程"""
    list_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)

    def __init__(self, cookies, text):
        super().__init__()
        self.cookies = cookies
        self.text = text

    def run(self):
        if requests is None:
            self.error_occurred.emit("requests库未安装")
            return
        try:
            bvid = _extract_bvid(self.text)
            if not bvid:
                self.error_occurred.emit("无法识别视频链接，请输入BV号/av号/视频URL")
                return
            s = _new_session(self.cookies)
            if bvid.startswith("BV"):
                view_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            else:
                view_url = f"https://api.bilibili.com/x/web-interface/view?aid={bvid}"
            r = s.get(view_url, timeout=15)
            view = r.json()
            if view.get("code") != 0:
                self.error_occurred.emit(f"视频信息获取失败: {view.get('message', view.get('code'))}")
                return
            data = view.get("data", {})
            title = data.get("title", "")
            real_bvid = data.get("bvid", bvid)
            pages = data.get("pages", [])
            if not pages:
                self.error_occurred.emit("该视频没有分P信息")
                return

            results = [None] * len(pages)
            with ThreadPoolExecutor(max_workers=8) as pool:
                futures = {}
                for i, page in enumerate(pages):
                    cid = page.get("cid", 0)
                    futures[pool.submit(
                        self._fetch_page_subs, s, real_bvid, cid)] = i
                done = 0
                for fut in as_completed(futures):
                    i = futures[fut]
                    done += 1
                    self.progress_updated.emit(
                        int(done * 100 / len(pages)),
                        f"正在解析分P字幕 ({done}/{len(pages)})...")
                    try:
                        results[i] = fut.result()
                    except Exception as e:
                        logger.warning(f"分P{i+1}字幕解析失败: {e}")
                        results[i] = []

            page_data = []
            for i, page in enumerate(pages):
                page_data.append({
                    "page": page.get("page", i + 1),
                    "part": page.get("part", f"P{i+1}"),
                    "cid": page.get("cid", 0),
                    "duration": page.get("duration", 0),
                    "subtitles": results[i] or [],
                })
            self.list_ready.emit({"title": title, "bvid": real_bvid, "pages": page_data})
        except Exception as e:
            self.error_occurred.emit(f"解析异常: {str(e)}")

    @staticmethod
    def _fetch_page_subs(session, bvid, cid):
        try:
            player_url = f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}"
            r2 = session.get(player_url, timeout=15)
            pdata = r2.json()
            if pdata.get("code") != 0:
                return []
            return pdata.get("data", {}).get("subtitle", {}).get("subtitles", [])
        except Exception:
            return []


class SubtitleContentThread(QThread):
    """获取单条字幕内容线程"""
    content_ready = pyqtSignal(list, dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, sub_info):
        super().__init__()
        self.sub_info = sub_info

    def run(self):
        if requests is None:
            self.error_occurred.emit("requests库未安装")
            return
        try:
            url = self.sub_info.get("subtitle_url", "")
            if not url:
                self.error_occurred.emit("字幕URL为空")
                return
            if not url.startswith("http"):
                url = "https:" + url
            r = requests.get(url, timeout=15, headers=_SUB_HEADERS)
            r.raise_for_status()
            sub_json = r.json()
            body = sub_json.get("body", []) if isinstance(sub_json, dict) else []
            if not body:
                self.error_occurred.emit("字幕内容为空")
                return
            self.content_ready.emit(body, self.sub_info)
        except Exception as e:
            self.error_occurred.emit(f"字幕下载异常: {str(e)}")


class SubtitleDownloadThread(QThread):
    """批量下载选中分P的全部字幕线程"""
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(bool, str)

    def __init__(self, pages, save_dir, title):
        super().__init__()
        self.pages = pages
        self.save_dir = save_dir
        self.title = title

    def run(self):
        if requests is None:
            self.download_finished.emit(False, "requests库未安装")
            return
        tasks = []
        for pg in self.pages:
            for sub in pg.get("subtitles", []):
                tasks.append((pg, sub))
        total = len(tasks)
        if total == 0:
            self.download_finished.emit(False, "没有可下载的字幕")
            return
        try:
            os.makedirs(self.save_dir, exist_ok=True)
        except Exception as e:
            self.download_finished.emit(False, f"创建目录失败: {e}")
            return
        saved = []
        failed = 0
        for i, (pg, sub) in enumerate(tasks, 1):
            lan = sub.get("lan", "unknown")
            lan_name = sub.get("lan_doc", lan)
            page_no = pg.get("page", "?")
            part = pg.get("part", f"P{page_no}")
            self.progress_updated.emit(
                int((i - 1) * 100 / total),
                f"P{page_no} {part} - {lan_name} ({i}/{total})...")
            try:
                url = sub.get("subtitle_url", "")
                if not url:
                    failed += 1
                    continue
                if not url.startswith("http"):
                    url = "https:" + url
                r = requests.get(url, timeout=15, headers=_SUB_HEADERS)
                r.raise_for_status()
                srt = _body_to_srt(r.json().get("body", []))
                if not srt:
                    failed += 1
                    continue
                safe_lang = "".join(c for c in lan_name if c.isalnum() or c in "_ -") or lan
                safe_part = _safe_filename(part)
                filename = f"{_safe_filename(self.title)}_P{page_no:02d}_{safe_part}_{safe_lang}.srt"
                path = os.path.join(self.save_dir, filename)
                if os.path.exists(path):
                    name, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(os.path.join(self.save_dir, f"{name}_{counter}{ext}")):
                        counter += 1
                    path = os.path.join(self.save_dir, f"{name}_{counter}{ext}")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(srt)
                saved.append(path)
            except Exception as e:
                logger.warning(f"字幕下载失败 {lan}: {e}")
                failed += 1
        self.progress_updated.emit(100, f"完成 {len(saved)}/{total}")
        if saved:
            self.download_finished.emit(True, f"已保存 {len(saved)} 个字幕文件:\n" + "\n".join(saved))
        else:
            self.download_finished.emit(False, "没有字幕下载成功")


class SubtitleTab(QWidget):
    """视频字幕解析 Tab 页（需登录，读取主界面全局输入框，跟随全局解析）"""

    _list_ready_signal = pyqtSignal(dict)
    _list_error_signal = pyqtSignal(str)
    _list_progress_signal = pyqtSignal(int, str)
    _content_ready_signal = pyqtSignal(list, dict)
    _content_error_signal = pyqtSignal(str)
    _download_progress_signal = pyqtSignal(int, str)
    _download_finished_signal = pyqtSignal(bool, str)

    _GB = """
        QGroupBox {
            font-size: 12px; font-weight: 600; color: #555;
            border: 1px solid #e0e4ea; border-radius: 6px;
            margin-top: 12px; padding: 8px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
    """

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_window = parent
        self.list_thread = None
        self.content_thread = None
        self.download_thread = None
        self._pages = []
        self._video_title = ""
        self._sub_cache = {}
        self._is_logged_in = False
        self._previewing_index = -1
        self._current_preview_state = None
        self._preview_groups = []
        self._active_group_index = -1
        self._highlight_cells = []
        self._blink_timer = None

        self._list_ready_signal.connect(self._on_list_ready)
        self._list_error_signal.connect(self._on_list_error)
        self._list_progress_signal.connect(self._on_list_progress)
        self._content_ready_signal.connect(self._on_content_ready)
        self._content_error_signal.connect(self._on_content_error)
        self._download_progress_signal.connect(self._on_download_progress)
        self._download_finished_signal.connect(self._on_download_finished)

        self._init_ui()
        self._update_login_status()

    def _load_cookie_txt(self):
        cookies = {}
        cookie_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookie.txt")
        if not os.path.exists(cookie_path):
            cookie_path = os.path.join(os.getcwd(), "cookie.txt")
        if os.path.exists(cookie_path):
            try:
                with open(cookie_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and "name" in item and "value" in item:
                            name = item["name"].strip()
                            value = item["value"]
                            if name:
                                cookies[name] = value
            except Exception as e:
                logger.warning(f"读取 cookie.txt 失败: {e}")
        return cookies

    def _get_cookies(self):
        cookies = {}
        file_cookies = self._load_cookie_txt()
        if file_cookies:
            cookies.update(file_cookies)
        parent = getattr(self, 'parent_window', None)
        parent_parser = getattr(parent, 'parser', None) if parent else None
        if parent_parser and hasattr(parent_parser, 'cookies') and parent_parser.cookies:
            for k, v in parent_parser.cookies.items():
                cookies.setdefault(k, v)
        return cookies

    def _update_login_status(self):
        cookies = self._get_cookies()
        has_sess = bool(cookies.get('SESSDATA'))
        has_uid = bool(cookies.get('DedeUserID'))
        self._is_logged_in = has_sess and has_uid

    def _get_default_save_path(self):
        path = ""
        if self.config:
            path = self.config.get_app_setting("default_save_path", "") or ""
        if not path:
            path = os.path.join(os.getcwd(), "B站下载")
        return path

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(scale(8))
        main_layout.setContentsMargins(scale(8), scale(8), scale(8), scale(8))

        # 分P字幕列表（时间轴在上，表格在下）
        list_group = QGroupBox("分P字幕列表")
        list_group.setStyleSheet(scale_style(self._GB))
        list_layout = QVBoxLayout(list_group)
        list_layout.setSpacing(scale(6))
        list_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        self.timeline = SubtitleTimeline()
        self.timeline.seek_requested.connect(self._on_seek)
        list_layout.addWidget(self.timeline)

        self.sub_table = QTableWidget(0, 4)
        self.sub_table.setHorizontalHeaderLabels(["选择", "P", "分P标题", "语言"])
        self.sub_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.sub_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.sub_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.sub_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.sub_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sub_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sub_table.setAlternatingRowColors(True)
        self.sub_table.cellClicked.connect(self._on_cell_clicked)
        list_layout.addWidget(self.sub_table)

        # 操作行（一行：全选/全不选/下载/保存路径/浏览/取消）
        op_row = QHBoxLayout()
        op_row.setSpacing(scale(8))

        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setStyleSheet(scale_style(
            "padding: 4px 12px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.select_all_btn.setEnabled(False)
        self.select_all_btn.clicked.connect(lambda: self._set_all_checked(True))
        op_row.addWidget(self.select_all_btn)

        self.select_none_btn = QPushButton("全不选")
        self.select_none_btn.setStyleSheet(scale_style(
            "padding: 4px 12px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.select_none_btn.setEnabled(False)
        self.select_none_btn.clicked.connect(lambda: self._set_all_checked(False))
        op_row.addWidget(self.select_none_btn)

        self.download_btn = QPushButton("下载选中")
        self.download_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #28a745; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        self.download_btn.setMinimumHeight(scale(30))
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._download_selected)
        op_row.addWidget(self.download_btn)

        op_row.addWidget(QLabel("保存到:"))
        self.save_path_input = QLineEdit()
        self.save_path_input.setText(self._get_default_save_path())
        self.save_path_input.setMinimumHeight(scale(30))
        self.save_path_input.setMinimumWidth(scale(80))
        self.save_path_input.setStyleSheet(scale_style("padding: 4px 8px;"))
        op_row.addWidget(self.save_path_input, stretch=1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.browse_btn.setMinimumHeight(scale(30))
        self.browse_btn.clicked.connect(self._browse_save_path)
        op_row.addWidget(self.browse_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #dc3545; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.cancel_btn.setMinimumHeight(scale(30))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
        op_row.addWidget(self.cancel_btn)

        list_layout.addLayout(op_row)
        main_layout.addWidget(list_group)

        # 字幕预览列表
        preview_group = QGroupBox("字幕预览")
        preview_group.setStyleSheet(scale_style(self._GB))
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setSpacing(scale(4))
        preview_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        self.preview_table = QTableWidget(0, 3)
        self.preview_table.setHorizontalHeaderLabels(["序号", "时间", "内容"])
        self.preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.preview_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.verticalHeader().setDefaultSectionSize(scale(26))
        self.preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.preview_table.setSelectionMode(QTableWidget.NoSelection)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setStyleSheet(scale_style("font-size: 12px;"))
        self.preview_table.cellClicked.connect(self._on_preview_cell_clicked)
        preview_layout.addWidget(self.preview_table)
        self.preview_table.verticalScrollBar().valueChanged.connect(self._sync_timeline_from_scroll)
        main_layout.addWidget(preview_group, stretch=1)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(scale_style("font-size: 11px; color: #6c757d; padding: 1px;"))
        main_layout.addWidget(self.status_label)

    def _set_status(self, text):
        self.status_label.setText(text)

    def _set_all_checked(self, checked):
        for row in range(self.sub_table.rowCount()):
            w = self.sub_table.cellWidget(row, 0)
            if w and w.layout().count() > 0:
                chk = w.layout().itemAt(0).widget()
                if isinstance(chk, QCheckBox):
                    chk.setChecked(checked)

    def auto_parse_from_main(self, video_info):
        """主界面解析完成后自动跟随解析"""
        if not self._is_logged_in:
            return
        bvid = (video_info or {}).get('bvid', '') or ''
        if not _extract_bvid(bvid):
            return
        self._start_parse(bvid)

    def _start_parse(self, text):
        self.select_all_btn.setEnabled(False)
        self.select_none_btn.setEnabled(False)
        self.download_btn.setEnabled(False)
        self.sub_table.setRowCount(0)
        self.preview_table.setRowCount(0)
        self.timeline.set_data(0, [])
        self._pages = []
        self._sub_cache.clear()
        self._previewing_index = -1
        self._current_preview_state = None
        self._preview_groups = []
        self._active_group_index = -1
        self._highlight_cells = []
        self._blink_timer = None
        self._set_status("正在解析字幕...")
        cookies = self._get_cookies()
        self.list_thread = SubtitleListThread(cookies, text)
        self.list_thread.list_ready.connect(self._list_ready_signal.emit)
        self.list_thread.error_occurred.connect(self._list_error_signal.emit)
        self.list_thread.progress_updated.connect(self._list_progress_signal.emit)
        self.list_thread.start()

    def _on_list_progress(self, pct, status):
        self._set_status(status)

    def _on_list_ready(self, data):
        self._pages = data.get("pages", [])
        self._video_title = data.get("title", "")
        bvid = data.get("bvid", "")
        with_subs = sum(1 for pg in self._pages if pg.get("subtitles"))
        self.sub_table.setRowCount(0)
        if not self._pages:
            self._set_status("解析结果为空")
            return
        self.sub_table.setRowCount(len(self._pages))
        for row, pg in enumerate(self._pages):
            chk = QCheckBox()
            chk.setEnabled(True)
            chk_widget = QWidget()
            h = QHBoxLayout(chk_widget)
            h.setContentsMargins(0, 0, 0, 0)
            h.setAlignment(Qt.AlignCenter)
            h.addWidget(chk)
            self.sub_table.setCellWidget(row, 0, chk_widget)

            item_page = QTableWidgetItem(str(pg.get("page", row + 1)))
            item_page.setFlags(item_page.flags() & ~Qt.ItemIsEditable)
            item_page.setTextAlignment(Qt.AlignCenter)
            self.sub_table.setItem(row, 1, item_page)

            item_part = QTableWidgetItem(pg.get("part", f"P{row+1}"))
            item_part.setFlags(item_part.flags() & ~Qt.ItemIsEditable)
            self.sub_table.setItem(row, 2, item_part)

            # 语言下拉
            subs = pg.get("subtitles", [])
            combo = QComboBox()
            combo.setStyleSheet(scale_style("padding: 2px 6px; font-size: 12px;"))
            for s in subs:
                combo.addItem(s.get("lan_doc", s.get("lan", "?")), s.get("lan", ""))
            if not subs:
                combo.addItem("无字幕", "")
                combo.setEnabled(False)
                chk.setEnabled(False)
            else:
                chk.setChecked(True)
                combo.currentIndexChanged.connect(
                    lambda _, r=row, c=combo: self._on_lang_changed(r, c))
            self.sub_table.setCellWidget(row, 3, combo)

        self.select_all_btn.setEnabled(True)
        self.select_none_btn.setEnabled(True)
        self.download_btn.setEnabled(True)
        self._set_status(f"解析成功，共{len(self._pages)}个分P，点击分P预览")

    def _on_list_error(self, msg):
        self._set_status(f"解析失败: {msg}")
        QMessageBox.warning(self, "解析失败", msg)

    def _get_selected(self):
        selected = []
        for row in range(self.sub_table.rowCount()):
            if row >= len(self._pages):
                continue
            w = self.sub_table.cellWidget(row, 0)
            checked = False
            if w and w.layout().count() > 0:
                chk = w.layout().itemAt(0).widget()
                if isinstance(chk, QCheckBox):
                    checked = chk.isChecked()
            if checked:
                selected.append(self._pages[row])
        return selected

    def _on_cell_clicked(self, row, col):
        if row >= len(self._pages):
            return
        pg = self._pages[row]
        subs = pg.get("subtitles", [])
        if not subs:
            QMessageBox.information(self, "提示", "该分P没有字幕")
            return
        combo = self.sub_table.cellWidget(row, 3)
        lan = combo.currentData() if combo else None
        self._preview_page(pg, lan, row)

    def _on_lang_changed(self, row, combo):
        if self._previewing_index != row or row >= len(self._pages):
            return
        pg = self._pages[row]
        self._preview_page(pg, combo.currentData(), row)

    def _preview_page(self, pg, lan, row):
        subs = pg.get("subtitles", [])
        if not subs:
            return
        sub_info = next((s for s in subs if s.get("lan") == lan), subs[0])
        self._previewing_index = row
        self._current_preview_state = [sub_info, pg]
        self.timeline.set_data(0, [])
        self._set_status(f"正在加载 P{pg.get('page')} 字幕...")
        self._load_language(sub_info, pg)

    def _load_language(self, sub_info, pg):
        lan = sub_info.get("lan", "unknown")
        if lan in self._sub_cache:
            self._show_preview(self._sub_cache[lan], pg, sub_info)
            return
        self.content_thread = SubtitleContentThread(sub_info)
        self.content_thread.content_ready.connect(self._content_ready_signal.emit)
        self.content_thread.error_occurred.connect(self._content_error_signal.emit)
        self.content_thread.start()

    def _show_preview(self, body, pg, sub_info):
        lan_name = sub_info.get("lan_doc", sub_info.get("lan", ""))
        page_no = pg.get("page", "?")
        part = pg.get("part", f"P{page_no}")
        title_text = f"P{page_no} {part} - {lan_name}"
        segments = [(float(i.get('from', 0)), float(i.get('to', 0))) for i in body]
        duration = pg.get("duration", 0) or (segments[-1][1] if segments else 0)

        # 同集已存在则只展开并定位，不重复追加
        for gi, g in enumerate(self._preview_groups):
            if g['title'] == title_text:
                if not g['expanded']:
                    self._toggle_group(gi)
                self._active_group_index = gi
                self.timeline.set_data(duration, segments)
                self.preview_table.scrollToItem(self.preview_table.item(g['header_row'], 0))
                self._set_status(f"已加载 {lan_name}，共{len(body)}条字幕")
                return

        g = self._append_group(title_text, body)
        self._active_group_index = len(self._preview_groups) - 1
        self.timeline.set_data(duration, segments)
        self.preview_table.scrollToItem(self.preview_table.item(g['header_row'], 0))
        self._set_status(f"已加载 {lan_name}，共{len(body)}条字幕")

    def _append_group(self, title_text, body):
        table = self.preview_table
        header_row = table.rowCount()
        table.insertRow(header_row)
        table.setSpan(header_row, 0, 1, 3)
        head_item = QTableWidgetItem(f"▾ {title_text}")
        head_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        head_item.setBackground(QColor("#eef1f5"))
        font = QFont()
        font.setBold(True)
        head_item.setFont(font)
        table.setItem(header_row, 0, head_item)
        table.resizeRowToContents(header_row)
        start_row = header_row + 1
        row = start_row
        for idx, entry in enumerate(body, 1):
            table.insertRow(row)
            it_no = QTableWidgetItem(str(idx))
            it_no.setTextAlignment(Qt.AlignCenter)
            it_no.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row, 0, it_no)

            start_ms = int(float(entry.get('from', 0)) * 1000)
            end_ms = int(float(entry.get('to', 0)) * 1000)
            it_time = QTableWidgetItem(f"{_fmt_ts(start_ms)} --> {_fmt_ts(end_ms)}")
            it_time.setTextAlignment(Qt.AlignCenter)
            it_time.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row, 1, it_time)

            it_content = QTableWidgetItem(entry.get('content', ''))
            it_content.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            table.setItem(row, 2, it_content)
            row += 1
        g = {'title': title_text, 'header_row': header_row, 'start_row': start_row,
             'body': body, 'expanded': True}
        self._preview_groups.append(g)
        return g

    def _on_preview_cell_clicked(self, row, col):
        for gi, g in enumerate(self._preview_groups):
            if row == g['header_row']:
                self._toggle_group(gi)
                return
        # 点击字幕行：同步时间轴位置
        for g in self._preview_groups:
            if g['expanded'] and g['start_row'] <= row < g['start_row'] + len(g['body']):
                entry = g['body'][row - g['start_row']]
                t = float(entry.get('from', 0))
                self.timeline.set_current_position(t)
                self._highlight_row(g, row - g['start_row'])
                return

    def _toggle_group(self, gi):
        g = self._preview_groups[gi]
        g['expanded'] = not g['expanded']
        head_item = self.preview_table.item(g['header_row'], 0)
        if head_item is not None:
            head_item.setText(f"{'▾' if g['expanded'] else '▸'} {g['title']}")
        start = g['start_row']
        end = g['start_row'] + len(g['body'])
        for r in range(start, end):
            self.preview_table.setRowHidden(r, not g['expanded'])

    def _on_seek(self, t):
        self.timeline.set_current_position(t)
        if not self._preview_groups or self._active_group_index < 0:
            return
        g = self._preview_groups[self._active_group_index]
        body = g['body']
        if not body:
            return
        idx = None
        best = 0
        for i, item in enumerate(body):
            f = float(item.get('from', 0))
            to = float(item.get('to', 1e18))
            if f <= t <= to:
                idx = i
                break
            if f <= t:
                best = i
        if idx is None:
            idx = best
        self._highlight_row(g, idx)

    def _highlight_row(self, g, idx):
        self._clear_highlight()
        row = g['start_row'] + idx
        if row >= self.preview_table.rowCount():
            return
        if not g['expanded']:
            self._toggle_group(self._preview_groups.index(g))
        self.preview_table.scrollToItem(self.preview_table.item(row, 0))
        # 不调用 setCurrentCell，避免选中态的蓝色遮挡黄色高亮闪烁
        cells = []
        for c in range(3):
            it = self.preview_table.item(row, c)
            if it is not None:
                cells.append(it)
        self._highlight_cells = cells
        entry = g['body'][idx]
        self.timeline.set_current_position(float(entry.get('from', 0)))
        # 黄色快速闪烁约1秒
        self._blink_count = 0
        self._blink_on = False
        self._blink_max = 10
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._blink_step)
        self._blink_timer.start(100)
        self._blink_step()

    def _blink_step(self):
        self._blink_on = not self._blink_on
        for it in (self._highlight_cells or []):
            try:
                if self._blink_on:
                    it.setBackground(QColor("#ffd400"))
                    it.setForeground(QColor("#333333"))
                else:
                    it.setBackground(QBrush(Qt.NoBrush))
                    it.setForeground(QBrush(Qt.NoBrush))
            except Exception:
                pass
        self.preview_table.viewport().update()
        self._blink_count += 1
        if self._blink_count >= self._blink_max:
            timer = getattr(self, '_blink_timer', None)
            if timer is not None:
                try:
                    timer.stop()
                    timer.deleteLater()
                except Exception:
                    pass
            self._blink_timer = None
            self._clear_highlight()

    def _sync_timeline_from_scroll(self):
        top_row = self.preview_table.rowAt(1)
        if top_row < 0:
            return
        for g in self._preview_groups:
            if not g['expanded']:
                continue
            start = g['start_row']
            end = start + len(g['body'])
            if start <= top_row < end:
                entry = g['body'][top_row - start]
                self.timeline.set_current_position(float(entry.get('from', 0)))
                return
        # 顶部是标题行或折叠组：向下找第一条可见字幕
        for g in self._preview_groups:
            if not g['expanded']:
                continue
            for r in range(g['start_row'], g['start_row'] + len(g['body'])):
                if r >= top_row:
                    entry = g['body'][r - g['start_row']]
                    self.timeline.set_current_position(float(entry.get('from', 0)))
                    return

    def _clear_highlight(self):
        timer = getattr(self, '_blink_timer', None)
        if timer is not None:
            try:
                timer.stop()
                timer.deleteLater()
            except Exception:
                pass
        self._blink_timer = None
        for it in (self._highlight_cells or []):
            try:
                it.setBackground(QBrush())
            except Exception:
                pass
        self._highlight_cells = []

    def _on_content_ready(self, body, sub_info):
        lan = sub_info.get("lan", "unknown")
        self._sub_cache[lan] = body
        state = self._current_preview_state
        if not state:
            return
        sub_info_cur, pg = state
        if sub_info_cur.get("lan") != lan:
            return
        self._show_preview(body, pg, sub_info)

    def _on_content_error(self, msg):
        state = self._current_preview_state
        self._set_status(f"加载失败: {msg}")
        if state:
            sub_info, pg = state
            subs = pg.get("subtitles", [])
            if subs and subs[0].get("lan") != sub_info.get("lan"):
                self._preview_page(pg, subs[0].get("lan"), self._previewing_index)
                return
        QMessageBox.warning(self, "加载失败", msg)

    def _download_selected(self):
        selected = self._get_selected()
        if not selected:
            QMessageBox.warning(self, "提示", "请先勾选要下载的分P")
            return
        save_dir = self.save_path_input.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存目录")
            return
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._set_status("正在下载字幕...")
        self.download_thread = SubtitleDownloadThread(selected, save_dir, self._video_title or "subtitle")
        self.download_thread.progress_updated.connect(self._download_progress_signal.emit)
        self.download_thread.download_finished.connect(self._download_finished_signal.emit)
        self.download_thread.finished.connect(self._on_download_thread_done)
        self.download_thread.start()

    def _on_download_progress(self, pct, status):
        self._set_status(status)

    def _on_download_finished(self, success, msg):
        self.cancel_btn.setEnabled(False)
        self.download_btn.setEnabled(True)
        if success:
            self._set_status("字幕下载完成")
            QMessageBox.information(self, "下载完成", msg)
        else:
            self._set_status(f"下载失败: {msg}")
            QMessageBox.warning(self, "下载失败", msg)

    def _on_download_thread_done(self):
        self.cancel_btn.setEnabled(False)
        self.download_btn.setEnabled(True)

    def _cancel_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait(2000)
            self.cancel_btn.setEnabled(False)
            self.download_btn.setEnabled(True)
            self._set_status("下载已取消")

    def _browse_save_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_path_input.text())
        if path:
            self.save_path_input.setText(path)

    def cleanup(self):
        for t in [self.list_thread, self.content_thread, self.download_thread]:
            if t and t.isRunning():
                try:
                    if isinstance(t, SubtitleDownloadThread):
                        t.terminate()
                    else:
                        t.quit()
                    t.wait(2000)
                except Exception:
                    pass
