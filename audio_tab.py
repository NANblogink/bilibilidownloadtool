# -*- coding: utf-8 -*-
"""
B站音频（歌曲）功能 Tab 页
功能：歌曲信息解析、音频流下载、歌词获取、音频榜单浏览
子页：歌曲解析 / 歌词获取 / 音频榜单
API 文档：
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/info.html
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/musicstream_url.html
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/rank.html
"""

import os
import re
import json
import time
import logging
import threading

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTextEdit, QProgressBar, QGroupBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QSplitter, QTabWidget, QGridLayout, QSizePolicy,
    QListWidget, QListWidgetItem, QCheckBox, QMenu
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

try:
    from audio_parser import AudioParser, QUALITY_MAP, QUALITY_TYPE_MAP, RANK_TYPE_MAP, MEMBER_TYPE_MAP
except ImportError:
    AudioParser = None

try:
    from platform_utils import IS_WINDOWS
except ImportError:
    IS_WINDOWS = True

logger = logging.getLogger(__name__)

# 尝试导入 scale/scale_style
try:
    from ui import scale, scale_style
except ImportError:
    def scale(v): return int(v)
    def scale_style(s): return re.sub(r'(\d+)px', lambda m: str(int(m.group(1))) + 'px', s)


class AudioInfoThread(QThread):
    """查询歌曲信息线程（含TAG、创作成员、收藏/投币状态）"""
    info_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, parser, sid):
        super().__init__()
        self.parser = parser
        self.sid = sid

    def run(self):
        try:
            info = self.parser.get_song_info(self.sid)
            if not info.get("success"):
                self.error_occurred.emit(info.get("error", "查询失败"))
                return
            data = info["data"]
            # 并发获取TAG、创作成员、收藏/投币状态
            tags_result = self.parser.get_song_tags(self.sid)
            members_result = self.parser.get_song_members(self.sid)
            collect_result = self.parser.get_collect_status(self.sid)
            coin_result = self.parser.get_coin_num(self.sid)
            data["tags"] = tags_result.get("data", []) if tags_result.get("success") else []
            data["members"] = members_result.get("data", []) if members_result.get("success") else []
            data["collected"] = collect_result.get("data", False) if collect_result.get("success") else False
            data["coin_num_self"] = coin_result.get("data", 0) if coin_result.get("success") else 0
            self.info_ready.emit(data)
        except Exception as e:
            self.error_occurred.emit(f"查询异常: {str(e)}")


class AudioStreamThread(QThread):
    """获取音频流URL线程"""
    stream_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, parser, sid, quality=2, use_full_api=False, mid=0):
        super().__init__()
        self.parser = parser
        self.sid = sid
        self.quality = quality
        self.use_full_api = use_full_api
        self.mid = mid

    def run(self):
        try:
            if self.use_full_api:
                result = self.parser.get_stream_url_full(
                    self.sid, quality=self.quality, privilege=2,
                    mid=self.mid, platform="web"
                )
            else:
                result = self.parser.get_stream_url_web(self.sid)
            if not result.get("success"):
                self.error_occurred.emit(result.get("error", "获取失败"))
                return
            self.stream_ready.emit(result["data"])
        except Exception as e:
            self.error_occurred.emit(f"获取异常: {str(e)}")


class AudioDownloadThread(QThread):
    """音频流下载线程"""
    progress_updated = pyqtSignal(int, str)  # (百分比, 状态文本)
    download_finished = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parser, stream_url, output_path, referer="https://www.bilibili.com/"):
        super().__init__()
        self.parser = parser
        self.stream_url = stream_url
        self.output_path = output_path
        self.referer = referer
        self._stop_flag = False

    def run(self):
        try:
            self.progress_updated.emit(0, "开始下载...")
            start_time = time.time()

            def progress_cb(downloaded, total, speed):
                if self._stop_flag:
                    return
                if total > 0:
                    pct = int(downloaded * 100 / total)
                    speed_mb = speed / 1024 / 1024
                    self.progress_updated.emit(pct, f"下载中 {pct}%  {speed_mb:.1f} MB/s")
                else:
                    speed_mb = speed / 1024 / 1024
                    self.progress_updated.emit(-1, f"已下载 {downloaded/1024/1024:.1f} MB  {speed_mb:.1f} MB/s")

            def cancel_check():
                return self._stop_flag

            result = self.parser.download_stream(
                self.stream_url, self.output_path,
                progress_callback=progress_cb,
                cancel_check=cancel_check,
                referer=self.referer
            )

            if self._stop_flag:
                self.download_finished.emit(False, "下载已取消")
            elif result.get("success"):
                self.progress_updated.emit(100, "下载完成")
                self.download_finished.emit(True, f"下载完成: {self.output_path}")
            else:
                self.error_occurred.emit(result.get("error", "下载失败"))
        except Exception as e:
            self.error_occurred.emit(f"下载异常: {str(e)}")

    def stop(self):
        self._stop_flag = True


class LyricThread(QThread):
    """歌词获取线程"""
    lyric_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parser, sid):
        super().__init__()
        self.parser = parser
        self.sid = sid

    def run(self):
        try:
            result = self.parser.get_song_lyric(self.sid)
            if not result.get("success"):
                self.error_occurred.emit(result.get("error", "获取歌词失败"))
                return
            self.lyric_ready.emit(result.get("data") or "")
        except Exception as e:
            self.error_occurred.emit(f"获取异常: {str(e)}")


class RankPeriodsThread(QThread):
    """获取榜单每期列表线程"""
    periods_ready = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, parser, list_type=1):
        super().__init__()
        self.parser = parser
        self.list_type = list_type

    def run(self):
        try:
            result = self.parser.get_rank_periods(self.list_type)
            if not result.get("success"):
                self.error_occurred.emit(result.get("error", "获取榜单失败"))
                return
            self.periods_ready.emit(result.get("data") or {})
        except Exception as e:
            self.error_occurred.emit(f"获取异常: {str(e)}")


class RankMusicListThread(QThread):
    """获取榜单单期内容线程"""
    music_list_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, parser, list_id):
        super().__init__()
        self.parser = parser
        self.list_id = list_id

    def run(self):
        try:
            result = self.parser.get_rank_music_list(self.list_id)
            if not result.get("success"):
                self.error_occurred.emit(result.get("error", "获取榜单内容失败"))
                return
            self.music_list_ready.emit(result.get("data") or [])
        except Exception as e:
            self.error_occurred.emit(f"获取异常: {str(e)}")


class AudioTab(QWidget):
    """音频（歌曲）功能 Tab 页"""

    # 线程安全信号
    _info_ready_signal = pyqtSignal(dict)
    _info_error_signal = pyqtSignal(str)
    _stream_ready_signal = pyqtSignal(dict)
    _stream_error_signal = pyqtSignal(str)
    _lyric_ready_signal = pyqtSignal(str)
    _lyric_error_signal = pyqtSignal(str)
    _periods_ready_signal = pyqtSignal(dict)
    _periods_error_signal = pyqtSignal(str)
    _music_list_ready_signal = pyqtSignal(list)
    _music_list_error_signal = pyqtSignal(str)

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
        self.audio_parser = None
        self.info_thread = None
        self.stream_thread = None
        self.download_thread = None
        self.lyric_thread = None
        self.rank_periods_thread = None
        self.rank_music_thread = None
        # 当前解析的歌曲信息缓存
        self._current_song = None
        self._current_stream = None
        # 当前榜单查询状态
        self._current_rank_type = 1

        self._init_parser()
        self._init_ui()
        self._init_network()

        # 连接线程安全信号
        self._info_ready_signal.connect(self._on_info_ready)
        self._info_error_signal.connect(self._on_info_error)
        self._stream_ready_signal.connect(self._on_stream_ready)
        self._stream_error_signal.connect(self._on_stream_error)
        self._lyric_ready_signal.connect(self._on_lyric_ready)
        self._lyric_error_signal.connect(self._on_lyric_error)
        self._periods_ready_signal.connect(self._on_periods_ready)
        self._periods_error_signal.connect(self._on_periods_error)
        self._music_list_ready_signal.connect(self._on_music_list_ready)
        self._music_list_error_signal.connect(self._on_music_list_error)

    def _load_cookie_txt(self):
        """从 cookie.txt 读取完整登录 cookie（JSON 数组格式）"""
        cookies = {}
        csrf_token = ""
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
                                if name == 'bili_jct':
                                    csrf_token = value
            except Exception as e:
                logger.warning(f"读取 cookie.txt 失败: {e}")
        return cookies, csrf_token

    def _get_cookies_from_parent(self):
        """合并主窗口 parser 与 cookie.txt 的 cookie，确保登录态完整"""
        cookies = {}
        csrf_token = ""
        sources = []

        file_cookies, file_csrf = self._load_cookie_txt()
        if file_cookies:
            cookies.update(file_cookies)
            if file_csrf:
                csrf_token = file_csrf
            sources.append("cookie.txt")

        parent = getattr(self, 'parent_window', None)
        parent_parser = getattr(parent, 'parser', None) if parent else None
        essential_keys = {'SESSDATA', 'bili_jct', 'DedeUserID', 'DedeUserID__ckMd5'}
        if parent_parser and hasattr(parent_parser, 'cookies') and parent_parser.cookies:
            for k, v in parent_parser.cookies.items():
                if k in essential_keys and k in file_cookies and file_cookies[k]:
                    continue
                cookies[k] = v
                if k == 'bili_jct':
                    csrf_token = v
            sources.append("parent_parser")

        if not cookies and self.config:
            cookie_str = self.config.get_app_setting("cookie", "") or ""
            if cookie_str:
                for pair in cookie_str.split(';'):
                    pair = pair.strip()
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        k = k.strip()
                        v = v.strip()
                        if k:
                            cookies[k] = v
                            if k == 'bili_jct':
                                csrf_token = v
                if cookies:
                    sources.append("config")

        return cookies, csrf_token, "+".join(sources) if sources else "none"

    def _get_user_mid(self):
        """获取当前登录用户mid"""
        parent = getattr(self, 'parent_window', None)
        parent_parser = getattr(parent, 'parser', None) if parent else None
        if parent_parser:
            user_info = getattr(parent_parser, 'user_info', None)
            if user_info and isinstance(user_info, dict):
                mid = user_info.get('mid') or user_info.get('uid')
                if mid:
                    return int(mid)
            cookies = getattr(parent_parser, 'cookies', {}) or {}
            dede = cookies.get('DedeUserID', '')
            if dede and str(dede).isdigit():
                return int(dede)
        # 兜底从 cookie.txt 取
        cookies, _ = self._load_cookie_txt()
        dede = cookies.get('DedeUserID', '')
        if dede and str(dede).isdigit():
            return int(dede)
        return 0

    def _init_parser(self):
        if AudioParser is None:
            return
        cookies, csrf_token, source = self._get_cookies_from_parent()
        self.audio_parser = AudioParser(config=self.config, cookies=cookies, csrf_token=csrf_token)
        logger.info(f"音频Tab初始化，Cookie来源={source}, 字段数: {len(cookies)}")

    def _refresh_cookies(self):
        if not self.audio_parser:
            return
        cookies, csrf_token, source = self._get_cookies_from_parent()
        if cookies:
            self.audio_parser.update_cookies(cookies, csrf_token)
            logger.info(f"音频Tab Cookie已刷新，来源={source}, 字段数: {len(cookies)}")

    def _init_network(self):
        """初始化网络管理器（用于加载封面图）"""
        self.network_manager = QNetworkAccessManager()
        self._pending_covers = {}  # reply -> label

    def _init_ui(self):
        """初始化UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(scale(2))
        main_layout.setContentsMargins(scale(0), scale(0), scale(0), scale(0))

        self.sub_tabs = QTabWidget()
        self.sub_tabs.setStyleSheet(scale_style("""
            QTabWidget { background-color: white; }
            QTabBar { background-color: #f8f9fa; border-bottom: 1px solid #dee2e6; }
            QTabBar::tab {
                background-color: #f8f9fa; color: #6c757d;
                padding: 6px 16px; border: 1px solid #dee2e6; border-bottom: none;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
                margin-right: 2px; font-size: 12px;
            }
            QTabBar::tab:hover { background-color: #e9ecef; color: #495057; }
            QTabBar::tab:selected { background-color: white; color: #2563eb; border-color: #409eff; border-bottom-color: white; }
            QTabWidget::pane {
                background-color: white; border: 1px solid #dee2e6; border-top: none;
                border-radius: 0 0 4px 4px; padding: 0px;
            }
        """))

        self.sub_tabs.addTab(self._create_parse_tab(), "歌曲解析")
        self.sub_tabs.addTab(self._create_lyric_tab(), "歌词获取")
        self.sub_tabs.addTab(self._create_rank_tab(), "音频榜单")

        # 切换到"音频榜单"子页时自动加载最新一期（仅一次）
        self._rank_auto_loaded = False
        self.sub_tabs.currentChanged.connect(self._on_subtab_changed)

        main_layout.addWidget(self.sub_tabs)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(scale_style("font-size: 11px; color: #6c757d; padding: 1px;"))
        main_layout.addWidget(self.status_label)

    def _create_parse_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(scale(10))
        layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))

        input_group = QGroupBox("查询歌曲")
        input_group.setStyleSheet(scale_style(self._GB))
        input_layout = QHBoxLayout(input_group)
        input_layout.setSpacing(scale(8))
        input_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        input_layout.addWidget(QLabel("音频au号:"))
        self.au_input = QLineEdit()
        self.au_input.setPlaceholderText("输入 au号 / 纯数字 / 音频页链接")
        self.au_input.setMinimumHeight(scale(30))
        self.au_input.setStyleSheet(scale_style("padding: 4px 8px;"))
        self.au_input.returnPressed.connect(self._query_song_info)
        input_layout.addWidget(self.au_input, stretch=1)

        self.query_btn = QPushButton("查询")
        self.query_btn.setStyleSheet(scale_style(
            "padding: 6px 16px; background-color: #00a1d6; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        self.query_btn.setMinimumHeight(scale(30))
        self.query_btn.clicked.connect(self._query_song_info)
        input_layout.addWidget(self.query_btn)

        layout.addWidget(input_group)

        # 信息展示区
        info_group = QGroupBox("歌曲信息")
        info_group.setStyleSheet(scale_style(self._GB))
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(scale(8))
        info_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(scale(120), scale(120))
        self.cover_label.setStyleSheet(scale_style("border: 1px solid #dee2e6; border-radius: 4px; background: #f8f9fa;"))
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("封面")
        info_layout.addWidget(self.cover_label, 0, 0, 6, 1)

        self.info_labels = {}
        fields = [
            ("title", "标题"), ("uname", "UP主"), ("author", "作者"),
            ("duration_text", "时长"), ("passtime_text", "发布时间"),
            ("bvid", "关联稿件"), ("coin_num", "投币数"),
            ("play", "播放数"), ("collect", "收藏数"),
            ("comment", "评论数"), ("share", "分享数"),
            ("tags_text", "标签"), ("members_text", "创作成员"),
            ("collected_text", "已收藏"), ("vip_text", "UP主会员"),
        ]
        for i, (key, label) in enumerate(fields):
            row = i % 7
            col = (i // 7) * 2 + 1
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(scale_style("font-size: 11px;"))
            info_layout.addWidget(lbl, row, col)
            val_label = QLabel("-")
            val_label.setStyleSheet(scale_style("font-size: 11px;"))
            val_label.setWordWrap(True)
            val_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.info_labels[key] = val_label
            info_layout.addWidget(val_label, row, col + 1)

        # 简介单独一行
        intro_lbl = QLabel("简介:")
        intro_lbl.setStyleSheet(scale_style("font-size: 11px;"))
        info_layout.addWidget(intro_lbl, 7, 1, 1, 4)
        self.info_labels["intro"] = QLabel("-")
        self.info_labels["intro"].setStyleSheet(scale_style("font-size: 11px;"))
        self.info_labels["intro"].setWordWrap(True)
        self.info_labels["intro"].setTextInteractionFlags(Qt.TextSelectableByMouse)
        info_layout.addWidget(self.info_labels["intro"], 8, 1, 1, 4)

        layout.addWidget(info_group)

        # 音频流获取与下载区
        stream_group = QGroupBox("音频流下载")
        stream_group.setStyleSheet(scale_style(self._GB))
        stream_layout = QVBoxLayout(stream_group)
        stream_layout.setSpacing(scale(8))
        stream_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        q_layout = QHBoxLayout()
        q_layout.setSpacing(scale(8))
        q_layout.addWidget(QLabel("音质:"))
        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(scale(160))
        self.quality_combo.setMinimumHeight(scale(30))
        self.quality_combo.setStyleSheet(scale_style("padding: 2px 6px;"))
        # 默认填充web端可用音质（192K）
        self._fill_quality_combo(full=False)
        q_layout.addWidget(self.quality_combo)

        self.use_full_api_chk = QCheckBox("使用付费接口（需大会员登录）")
        self.use_full_api_chk.setStyleSheet(scale_style("font-size: 11px;"))
        self.use_full_api_chk.stateChanged.connect(self._on_full_api_changed)
        q_layout.addWidget(self.use_full_api_chk)
        q_layout.addStretch()

        self.get_stream_btn = QPushButton("获取音频流")
        self.get_stream_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #28a745; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        self.get_stream_btn.setMinimumHeight(scale(30))
        self.get_stream_btn.clicked.connect(self._get_stream_url)
        q_layout.addWidget(self.get_stream_btn)

        self.copy_url_btn = QPushButton("复制URL")
        self.copy_url_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.copy_url_btn.setMinimumHeight(scale(30))
        self.copy_url_btn.clicked.connect(self._copy_stream_url)
        q_layout.addWidget(self.copy_url_btn)

        stream_layout.addLayout(q_layout)

        self.stream_url_text = QTextEdit()
        self.stream_url_text.setReadOnly(True)
        self.stream_url_text.setMaximumHeight(scale(50))
        self.stream_url_text.setStyleSheet(scale_style("font-size: 10px; background: #f8f9fa;"))
        stream_layout.addWidget(self.stream_url_text)

        path_layout = QHBoxLayout()
        path_layout.setSpacing(scale(8))
        path_layout.addWidget(QLabel("保存到:"))
        self.save_path_input = QLineEdit()
        default_audio_path = ""
        if self.config:
            default_audio_path = self.config.get_app_setting("audio_last_save_path", "") or \
                                 self.config.get_app_setting("default_save_path", "")
        if not default_audio_path:
            default_audio_path = os.path.join(os.getcwd(), "音频下载")
        self.save_path_input.setText(default_audio_path)
        self.save_path_input.setMinimumHeight(scale(30))
        self.save_path_input.setStyleSheet(scale_style("padding: 4px 8px;"))
        path_layout.addWidget(self.save_path_input, stretch=1)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.browse_btn.setMinimumHeight(scale(30))
        self.browse_btn.clicked.connect(self._browse_save_path)
        path_layout.addWidget(self.browse_btn)

        stream_layout.addLayout(path_layout)

        # 下载进度
        dl_layout = QHBoxLayout()
        dl_layout.setSpacing(scale(8))
        self.dl_progress = QProgressBar()
        self.dl_progress.setMinimumHeight(scale(20))
        dl_layout.addWidget(self.dl_progress, stretch=1)

        self.download_btn = QPushButton("下载音频")
        self.download_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #fd7e14; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        self.download_btn.setMinimumHeight(scale(30))
        self.download_btn.setEnabled(False)
        self.download_btn.clicked.connect(self._start_download)
        dl_layout.addWidget(self.download_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #dc3545; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.cancel_btn.setMinimumHeight(scale(30))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_download)
        dl_layout.addWidget(self.cancel_btn)

        stream_layout.addLayout(dl_layout)

        self.dl_status = QLabel("就绪")
        self.dl_status.setStyleSheet(scale_style("font-size: 11px; color: #6c757d;"))
        stream_layout.addWidget(self.dl_status)

        layout.addWidget(stream_group)
        layout.addStretch()
        scroll.setWidget(tab)
        return scroll

    def _fill_quality_combo(self, full=False):
        """填充音质下拉框"""
        self.quality_combo.clear()
        if full:
            # 完整接口支持全部音质
            for qn, name in QUALITY_MAP.items():
                self.quality_combo.addItem(f"{name} (qn={qn})", qn)
            # 默认选择高品质320K
            idx = self.quality_combo.findData(2)
            if idx >= 0:
                self.quality_combo.setCurrentIndex(idx)
        else:
            # web端仅192K
            self.quality_combo.addItem("标准 192K (qn=1)", 1)

    def _on_full_api_changed(self, state):
        full = self.use_full_api_chk.isChecked()
        self._fill_quality_combo(full=full)

    def _create_lyric_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(scale(10))
        layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))

        input_group = QGroupBox("获取歌词")
        input_group.setStyleSheet(scale_style(self._GB))
        input_layout = QHBoxLayout(input_group)
        input_layout.setSpacing(scale(8))
        input_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        input_layout.addWidget(QLabel("音频au号:"))
        self.lyric_au_input = QLineEdit()
        self.lyric_au_input.setPlaceholderText("输入 au号 / 纯数字 / 音频页链接")
        self.lyric_au_input.setMinimumHeight(scale(30))
        self.lyric_au_input.setStyleSheet(scale_style("padding: 4px 8px;"))
        self.lyric_au_input.returnPressed.connect(self._get_lyric)
        input_layout.addWidget(self.lyric_au_input, stretch=1)

        self.get_lyric_btn = QPushButton("获取歌词")
        self.get_lyric_btn.setStyleSheet(scale_style(
            "padding: 6px 16px; background-color: #00a1d6; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        self.get_lyric_btn.setMinimumHeight(scale(30))
        self.get_lyric_btn.clicked.connect(self._get_lyric)
        input_layout.addWidget(self.get_lyric_btn)

        self.save_lyric_btn = QPushButton("保存歌词")
        self.save_lyric_btn.setStyleSheet(scale_style(
            "padding: 6px 16px; background-color: #28a745; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.save_lyric_btn.setMinimumHeight(scale(30))
        self.save_lyric_btn.setEnabled(False)
        self.save_lyric_btn.clicked.connect(self._save_lyric)
        input_layout.addWidget(self.save_lyric_btn)

        layout.addWidget(input_group)

        self.lyric_text = QTextEdit()
        self.lyric_text.setReadOnly(True)
        self.lyric_text.setStyleSheet(scale_style("font-size: 12px; background: #fafafa;"))
        self.lyric_text.setPlaceholderText("歌词内容将显示在此...")
        layout.addWidget(self.lyric_text, stretch=1)

        return tab

    def _create_rank_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(scale(10))
        layout.setContentsMargins(scale(12), scale(12), scale(12), scale(12))

        # 榜单类型与期数选择
        sel_group = QGroupBox("选择榜单")
        sel_group.setStyleSheet(scale_style(self._GB))
        sel_layout = QHBoxLayout(sel_group)
        sel_layout.setSpacing(scale(8))
        sel_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        sel_layout.addWidget(QLabel("榜单类型:"))
        self.rank_type_combo = QComboBox()
        for t, name in RANK_TYPE_MAP.items():
            self.rank_type_combo.addItem(name, t)
        self.rank_type_combo.setMinimumWidth(scale(100))
        self.rank_type_combo.setMinimumHeight(scale(30))
        self.rank_type_combo.setStyleSheet(scale_style("padding: 2px 6px;"))
        sel_layout.addWidget(self.rank_type_combo)

        sel_layout.addWidget(QLabel("期数:"))
        self.rank_period_combo = QComboBox()
        self.rank_period_combo.setMinimumWidth(scale(160))
        self.rank_period_combo.setMinimumHeight(scale(30))
        self.rank_period_combo.setStyleSheet(scale_style("padding: 2px 6px;"))
        sel_layout.addWidget(self.rank_period_combo)

        self.load_periods_btn = QPushButton("加载期数")
        self.load_periods_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #17a2b8; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.load_periods_btn.setMinimumHeight(scale(30))
        self.load_periods_btn.clicked.connect(self._load_rank_periods)
        sel_layout.addWidget(self.load_periods_btn)

        self.load_music_btn = QPushButton("加载榜单内容")
        self.load_music_btn.setStyleSheet(scale_style(
            "padding: 6px 14px; background-color: #28a745; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.load_music_btn.setMinimumHeight(scale(30))
        self.load_music_btn.clicked.connect(self._load_rank_music)
        sel_layout.addWidget(self.load_music_btn)

        sel_layout.addStretch()
        layout.addWidget(sel_group)

        # 榜单内容表格
        list_group = QGroupBox("榜单内容")
        list_group.setStyleSheet(scale_style(self._GB))
        list_layout = QVBoxLayout(list_group)
        list_layout.setSpacing(scale(8))
        list_layout.setContentsMargins(scale(10), scale(14), scale(10), scale(10))

        # 搜索栏
        search_layout = QHBoxLayout()
        search_layout.setSpacing(scale(6))
        search_layout.addWidget(QLabel("搜索:"))
        self.rank_search_input = QLineEdit()
        self.rank_search_input.setPlaceholderText("输入关键词过滤标题/歌手/专辑...")
        self.rank_search_input.setMinimumHeight(scale(28))
        self.rank_search_input.setStyleSheet(scale_style("padding: 4px 8px;"))
        self.rank_search_input.textChanged.connect(self._filter_rank_table)
        search_layout.addWidget(self.rank_search_input, stretch=1)
        self.rank_search_clear_btn = QPushButton("清除")
        self.rank_search_clear_btn.setStyleSheet(scale_style(
            "padding: 4px 12px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        self.rank_search_clear_btn.setMinimumHeight(scale(28))
        self.rank_search_clear_btn.clicked.connect(lambda: self.rank_search_input.clear())
        search_layout.addWidget(self.rank_search_clear_btn)
        list_layout.addLayout(search_layout)

        self.rank_table = QTableWidget(0, 7)
        self.rank_table.setHorizontalHeaderLabels(["排名", "标题", "歌手", "专辑", "热度", "可听", "关联稿件"])
        self.rank_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.rank_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.rank_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.rank_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.rank_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.rank_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.rank_table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.rank_table.setAlternatingRowColors(True)
        self.rank_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.rank_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 右键菜单
        self.rank_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rank_table.customContextMenuRequested.connect(self._show_rank_context_menu)
        list_layout.addWidget(self.rank_table)

        self.rank_status = QLabel("就绪")
        self.rank_status.setStyleSheet(scale_style("font-size: 11px; color: #6c757d;"))
        list_layout.addWidget(self.rank_status)

        layout.addWidget(list_group, stretch=1)
        return tab

    def _set_status(self, text):
        self.status_label.setText(text)

    def _query_song_info(self):
        """查询歌曲信息"""
        if not self.audio_parser:
            QMessageBox.warning(self, "提示", "音频解析器未初始化")
            return
        raw = self.au_input.text().strip()
        if not raw:
            QMessageBox.warning(self, "提示", "请输入音频au号")
            return
        sid = AudioParser.parse_auid(raw)
        if not sid:
            QMessageBox.warning(self, "提示", "无法识别音频au号，请输入如 au13598 或 13598")
            return
        # 自动回填标准化au号
        if raw != sid:
            self.au_input.setText(sid)

        self.query_btn.setEnabled(False)
        self._set_status("正在查询歌曲信息...")
        logger.info(f"开始查询歌曲信息，sid={sid}")
        self._refresh_cookies()

        self.info_thread = AudioInfoThread(self.audio_parser, sid)
        # 通过信号回主线程
        self.info_thread.info_ready.connect(self._info_ready_signal.emit)
        self.info_thread.error_occurred.connect(self._info_error_signal.emit)
        self.info_thread.finished.connect(lambda: self.query_btn.setEnabled(True))
        self.info_thread.start()

    def _on_info_ready(self, data):
        self._current_song = data
        self._display_song_info(data)
        self._set_status(f"查询成功：{data.get('title', '')}")
        # 查询成功后启用获取音频流按钮
        self.get_stream_btn.setEnabled(True)
        # 自动解析歌词：同步填入歌词子页的au号并触发获取
        sid = data.get("id")
        if sid:
            try:
                self.lyric_au_input.blockSignals(True)
                self.lyric_au_input.setText(str(sid))
                self.lyric_au_input.blockSignals(False)
                self._get_lyric(auto=True)
            except Exception as e:
                logger.warning(f"自动获取歌词失败: {e}")

    def _on_info_error(self, msg):
        self._set_status(f"查询失败: {msg}")
        QMessageBox.warning(self, "查询失败", msg)

    def _display_song_info(self, d):
        """显示歌曲信息"""
        def fmt_time(ts):
            if not ts:
                return "-"
            try:
                return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ts)))
            except Exception:
                return "-"
        def fmt_duration(sec):
            try:
                sec = int(sec)
                m, s = sec // 60, sec % 60
                return f"{m:02d}:{s:02d}"
            except Exception:
                return "-"

        self.info_labels["title"].setText(d.get("title", "-") or "-")
        self.info_labels["uname"].setText(d.get("uname", "-") or "-")
        self.info_labels["author"].setText(d.get("author", "-") or "-")
        self.info_labels["duration_text"].setText(fmt_duration(d.get("duration", 0)))
        self.info_labels["passtime_text"].setText(fmt_time(d.get("passtime", 0)))
        bvid = d.get("bvid", "")
        self.info_labels["bvid"].setText(bvid if bvid else "无")
        self.info_labels["coin_num"].setText(str(d.get("coin_num", 0)))
        stat = d.get("statistic", {}) or {}
        self.info_labels["play"].setText(str(stat.get("play", 0)))
        self.info_labels["collect"].setText(str(stat.get("collect", 0)))
        self.info_labels["comment"].setText(str(stat.get("comment", 0)))
        self.info_labels["share"].setText(str(stat.get("share", 0)))
        tags = d.get("tags", []) or []
        self.info_labels["tags_text"].setText("、".join(tags) if tags else "无")
        members = d.get("members", []) or []
        member_strs = [f"{m['type_name']}: {'/'.join(m['names'])}" for m in members if m.get("names")]
        self.info_labels["members_text"].setText("\n".join(member_strs) if member_strs else "无")
        self.info_labels["collected_text"].setText("是" if d.get("collected") else "否")
        vip = d.get("vip_info", {}) or {}
        self.info_labels["vip_text"].setText(vip.get("type_name", "-"))
        self.info_labels["intro"].setText(d.get("intro", "-") or "-")

        cover_url = d.get("cover", "")
        if cover_url:
            self._load_cover(cover_url, self.cover_label)
        else:
            self.cover_label.clear()
            self.cover_label.setText("无封面")

    def _load_cover(self, url, label):
        """异步加载封面图"""
        if not url:
            label.clear()
            label.setText("无封面")
            return
        try:
            req = QNetworkRequest(QUrl(url))
            req.setAttribute(QNetworkRequest.FollowRedirectsAttribute, True)
            reply = self.network_manager.get(req)
            self._pending_covers[reply] = label

            def on_finished():
                if reply not in self._pending_covers:
                    return
                lbl = self._pending_covers.pop(reply)
                try:
                    data = bytes(reply.readAll())
                    if data:
                        img = QImage.fromData(data)
                        if not img.isNull():
                            pix = QPixmap.fromImage(img)
                            lbl.setPixmap(pix.scaled(
                                lbl.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
                        else:
                            lbl.setText("封面加载失败")
                    else:
                        lbl.setText("无封面")
                except Exception as e:
                    logger.warning(f"封面加载失败: {e}")
                    lbl.setText("封面加载失败")
                finally:
                    reply.deleteLater()

            reply.finished.connect(on_finished)
        except Exception as e:
            logger.warning(f"请求封面失败: {e}")
            label.setText("无封面")

    def _get_stream_url(self):
        if not self.audio_parser:
            QMessageBox.warning(self, "提示", "音频解析器未初始化")
            return
        raw = self.au_input.text().strip()
        sid = AudioParser.parse_auid(raw)
        if not sid:
            QMessageBox.warning(self, "提示", "请先输入或查询有效的音频au号")
            return

        self.get_stream_btn.setEnabled(False)
        self._set_status("正在获取音频流URL...")
        self._refresh_cookies()

        quality = self.quality_combo.currentData() or 1
        use_full = self.use_full_api_chk.isChecked()
        mid = self._get_user_mid() if use_full else 0

        self.stream_thread = AudioStreamThread(
            self.audio_parser, sid, quality=quality, use_full_api=use_full, mid=mid
        )
        self.stream_thread.stream_ready.connect(self._stream_ready_signal.emit)
        self.stream_thread.error_occurred.connect(self._stream_error_signal.emit)
        self.stream_thread.finished.connect(lambda: self.get_stream_btn.setEnabled(True))
        self.stream_thread.start()

    def _on_stream_ready(self, data):
        self._current_stream = data
        cdns = data.get("cdns", []) or []
        url_text = "\n".join(cdns) if cdns else "无可用URL"
        self.stream_url_text.setPlainText(url_text)

        type_name = data.get("type_name", "")
        is_trial = data.get("is_trial", False)
        size = data.get("size", 0)
        size_mb = size / 1024 / 1024 if size else 0
        timeout_sec = data.get("timeout", 0)
        timeout_h = timeout_sec / 3600 if timeout_sec else 0

        hint = f"音质: {type_name}"
        if is_trial:
            hint += "（试听片段）"
        if size:
            hint += f"  大小: {size_mb:.2f} MB"
        if timeout_sec:
            hint += f"  有效期: {timeout_h:.1f} 小时"
        self._set_status(hint)

        if cdns:
            self.download_btn.setEnabled(True)
        else:
            QMessageBox.warning(self, "提示", "未获取到音频流URL")

    def _on_stream_error(self, msg):
        self._set_status(f"获取失败: {msg}")
        QMessageBox.warning(self, "获取失败", msg)

    def _copy_stream_url(self):
        text = self.stream_url_text.toPlainText().strip()
        if not text or text == "无可用URL":
            QMessageBox.information(self, "提示", "暂无音频流URL可复制")
            return
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(text)
        self._set_status("音频流URL已复制到剪贴板")

    def _browse_save_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_path_input.text())
        if path:
            self.save_path_input.setText(path)
            if self.config:
                self.config.set_app_setting("audio_last_save_path", path)

    def _build_audio_filename(self, song, stream_data):
        """构造音频文件名"""
        title = ""
        if song:
            title = song.get("title", "")
        if not title and stream_data:
            title = stream_data.get("title", "")
        if not title:
            title = f"audio_{int(time.time())}"
        # 清理非法字符
        safe_title = re.sub(r'[\\/:*?"<>|]', "_", title).strip()
        type_code = stream_data.get("type", 1) if stream_data else 1
        # 试听片段加标记
        suffix = "_试听" if (stream_data and stream_data.get("is_trial")) else ""
        # 根据音质选择扩展名
        if type_code == 3:
            ext = ".flac"
        else:
            ext = ".m4a"
        return f"{safe_title}{suffix}{ext}"

    def _start_download(self):
        if not self._current_stream:
            QMessageBox.warning(self, "提示", "请先获取音频流URL")
            return
        cdns = self._current_stream.get("cdns", []) or []
        if not cdns:
            QMessageBox.warning(self, "提示", "无可用音频流URL")
            return
        save_dir = self.save_path_input.text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存目录")
            return
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "提示", f"创建目录失败: {e}")
            return

        filename = self._build_audio_filename(self._current_song, self._current_stream)
        # 去重
        full_path = os.path.join(save_dir, filename)
        if os.path.exists(full_path):
            name, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(os.path.join(save_dir, f"{name}_{counter}{ext}")):
                counter += 1
            full_path = os.path.join(save_dir, f"{name}_{counter}{ext}")

        stream_url = cdns[0]
        self.download_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.dl_progress.setValue(0)

        self.download_thread = AudioDownloadThread(
            self.audio_parser, stream_url, full_path,
            referer="https://www.bilibili.com/"
        )
        self.download_thread.progress_updated.connect(self._on_dl_progress)
        self.download_thread.download_finished.connect(self._on_dl_finished)
        self.download_thread.error_occurred.connect(self._on_dl_error)
        self.download_thread.start()

    def _cancel_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.cancel_btn.setEnabled(False)
            self.dl_status.setText("正在取消下载...")

    def _on_dl_progress(self, pct, status):
        if pct >= 0:
            self.dl_progress.setValue(pct)
        self.dl_status.setText(status)

    def _on_dl_finished(self, success, msg):
        self.cancel_btn.setEnabled(False)
        self.download_btn.setEnabled(True)
        if success:
            self.dl_progress.setValue(100)
            self.dl_status.setText(msg)
            self._set_status("音频下载完成")
            QMessageBox.information(self, "下载完成", msg)
        else:
            self.dl_status.setText(msg)
            self._set_status(msg)

    def _on_dl_error(self, msg):
        self.cancel_btn.setEnabled(False)
        self.download_btn.setEnabled(True)
        self.dl_status.setText(f"下载错误: {msg}")
        self._set_status(f"下载错误: {msg}")
        QMessageBox.warning(self, "下载错误", msg)

    def _get_lyric(self, auto=False):
        if not self.audio_parser:
            if not auto:
                QMessageBox.warning(self, "提示", "音频解析器未初始化")
            return
        raw = self.lyric_au_input.text().strip()
        if not raw:
            if not auto:
                QMessageBox.warning(self, "提示", "请输入音频au号")
            return
        sid = AudioParser.parse_auid(raw)
        if not sid:
            if not auto:
                QMessageBox.warning(self, "提示", "无法识别音频au号")
            return
        if raw != sid:
            self.lyric_au_input.setText(sid)

        self.get_lyric_btn.setEnabled(False)
        self.save_lyric_btn.setEnabled(False)
        self.lyric_text.clear()
        self._set_status("正在获取歌词..." if not auto else f"正在自动获取歌词 (au{sid})...")
        self._refresh_cookies()

        self.lyric_thread = LyricThread(self.audio_parser, sid)
        self.lyric_thread.lyric_ready.connect(self._lyric_ready_signal.emit)
        self.lyric_thread.error_occurred.connect(self._lyric_error_signal.emit)
        self.lyric_thread.finished.connect(lambda: self.get_lyric_btn.setEnabled(True))
        self.lyric_thread.start()

    def _on_lyric_ready(self, lyric):
        if not lyric:
            self.lyric_text.setPlainText("该歌曲暂无歌词")
            self._set_status("该歌曲暂无歌词")
            return
        self.lyric_text.setPlainText(lyric)
        self.save_lyric_btn.setEnabled(True)
        self._set_status("歌词获取成功")

    def _on_lyric_error(self, msg):
        self._set_status(f"歌词获取失败: {msg}")
        # 自动获取时不弹错误框，避免打断主流程；仅在歌词子页状态栏提示
        if not hasattr(self, '_lyric_auto_silent') or not self._lyric_auto_silent:
            QMessageBox.warning(self, "获取失败", msg)

    def _save_lyric(self):
        text = self.lyric_text.toPlainText()
        if not text or text == "该歌曲暂无歌词":
            QMessageBox.information(self, "提示", "暂无歌词可保存")
            return
        raw = self.lyric_au_input.text().strip()
        sid = AudioParser.parse_auid(raw) or str(int(time.time()))
        default_name = f"au{sid}_lyric.lrc"
        # 默认保存到音频下载目录
        default_dir = ""
        if self.config:
            default_dir = self.config.get_app_setting("audio_last_save_path", "") or \
                          self.config.get_app_setting("default_save_path", "")
        if not default_dir:
            default_dir = os.getcwd()
        default_path = os.path.join(default_dir, default_name)

        path, _ = QFileDialog.getSaveFileName(self, "保存歌词", default_path, "LRC歌词 (*.lrc);;文本文件 (*.txt);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
            self._set_status(f"歌词已保存: {path}")
            QMessageBox.information(self, "保存成功", f"歌词已保存到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))

    def _on_subtab_changed(self, idx):
        """子页切换时触发自动加载"""
        if idx < 0 or idx >= self.sub_tabs.count():
            return
        name = self.sub_tabs.tabText(idx)
        if name == "音频榜单" and not self._rank_auto_loaded:
            self._rank_auto_loaded = True
            # 延迟触发，避免切换动画抢资源
            QTimer.singleShot(100, self._auto_load_latest_rank)

    def _auto_load_latest_rank(self):
        """自动加载最新一期榜单内容"""
        if not self.audio_parser:
            return
        if self.rank_period_combo.count() > 0:
            # 已有期数，直接加载第0项（最新一期）
            self.rank_period_combo.setCurrentIndex(0)
            self._load_rank_music()
            return
        # 没有期数，先加载期数，完成后自动加载第0项
        self._rank_auto_load_pending = True
        self._load_rank_periods()

    def _load_rank_periods(self):
        if not self.audio_parser:
            QMessageBox.warning(self, "提示", "音频解析器未初始化")
            return
        list_type = self.rank_type_combo.currentData() or 1
        self._current_rank_type = list_type
        self.rank_period_combo.clear()
        self.load_periods_btn.setEnabled(False)
        self.rank_status.setText("正在加载榜单期数...")
        self._refresh_cookies()

        self.rank_periods_thread = RankPeriodsThread(self.audio_parser, list_type)
        self.rank_periods_thread.periods_ready.connect(self._periods_ready_signal.emit)
        self.rank_periods_thread.error_occurred.connect(self._periods_error_signal.emit)
        self.rank_periods_thread.finished.connect(lambda: self.load_periods_btn.setEnabled(True))
        self.rank_periods_thread.start()

    def _on_periods_ready(self, periods):
        self.rank_period_combo.clear()
        if not periods:
            self.rank_status.setText("暂无榜单数据")
            return
        # 按年份倒序，期数倒序填充
        for year in sorted(periods.keys(), reverse=True):
            year_items = sorted(periods[year], key=lambda x: x.get("period", 0), reverse=True)
            for item in year_items:
                period = item.get("period", "?")
                pub_time = item.get("publish_time", 0)
                pub_str = ""
                if pub_time:
                    try:
                        pub_str = time.strftime("%Y-%m-%d", time.localtime(int(pub_time)))
                    except Exception:
                        pub_str = ""
                label = f"{year}年 第{period}期"
                if pub_str:
                    label += f" ({pub_str})"
                self.rank_period_combo.addItem(label, item.get("id"))
        self.rank_status.setText(f"已加载 {self.rank_period_combo.count()} 期榜单，请选择期数后加载内容")
        # 自动加载衔接：期数加载完成后自动加载第0项（最新一期）
        if getattr(self, '_rank_auto_load_pending', False):
            self._rank_auto_load_pending = False
            if self.rank_period_combo.count() > 0:
                self.rank_period_combo.setCurrentIndex(0)
                QTimer.singleShot(100, self._load_rank_music)

    def _on_periods_error(self, msg):
        self.rank_status.setText(f"加载失败: {msg}")
        QMessageBox.warning(self, "加载失败", msg)

    def _load_rank_music(self):
        if not self.audio_parser:
            QMessageBox.warning(self, "提示", "音频解析器未初始化")
            return
        list_id = self.rank_period_combo.currentData()
        if not list_id:
            QMessageBox.warning(self, "提示", "请先加载并选择榜单期数")
            return
        self.load_music_btn.setEnabled(False)
        self.rank_status.setText("正在加载榜单内容...")
        self._refresh_cookies()

        self.rank_music_thread = RankMusicListThread(self.audio_parser, list_id)
        self.rank_music_thread.music_list_ready.connect(self._music_list_ready_signal.emit)
        self.rank_music_thread.error_occurred.connect(self._music_list_error_signal.emit)
        self.rank_music_thread.finished.connect(lambda: self.load_music_btn.setEnabled(True))
        self.rank_music_thread.start()

    def _on_music_list_ready(self, items):
        self.rank_table.setRowCount(0)
        # 保存全量数据用于搜索过滤
        self._rank_all_items = list(items or [])
        # 重置搜索框（不触发过滤循环）
        if hasattr(self, 'rank_search_input'):
            self.rank_search_input.blockSignals(True)
            self.rank_search_input.clear()
            self.rank_search_input.blockSignals(False)
        self._populate_rank_table(items)
        if not items:
            self.rank_status.setText("该期榜单暂无内容")
        else:
            self.rank_status.setText(f"已加载 {len(items)} 首歌曲")

    def _populate_rank_table(self, items):
        """填充榜单表格"""
        self.rank_table.setRowCount(0)
        if not items:
            return
        self.rank_table.setRowCount(len(items))
        for row, item in enumerate(items):
            rank = item.get("rank", 0)
            title = item.get("music_title", "")
            singer = item.get("singer", "")
            album = item.get("album", "")
            heat = item.get("heat", 0)
            can_listen = "是" if item.get("can_listen") else "否"
            bvid = item.get("creation_bvid", "") or item.get("mv_bvid", "")
            bvid_text = bvid if bvid else "-"

            cells = [str(rank), title, singer, album, str(heat), can_listen, bvid_text]
            for col, val in enumerate(cells):
                cell = QTableWidgetItem(val)
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                if col == 0:
                    cell.setTextAlignment(Qt.AlignCenter)
                self.rank_table.setItem(row, col, cell)
            # 保存完整对象供右键菜单使用
            self.rank_table.item(row, 0).setData(Qt.UserRole, item)

    def _filter_rank_table(self):
        """按搜索关键词过滤榜单表格"""
        keyword = self.rank_search_input.text().strip().lower()
        all_items = getattr(self, '_rank_all_items', []) or []
        if not keyword:
            self._populate_rank_table(all_items)
            self.rank_status.setText(f"已加载 {len(all_items)} 首歌曲")
            return
        filtered = []
        for item in all_items:
            title = (item.get("music_title", "") or "").lower()
            singer = (item.get("singer", "") or "").lower()
            album = (item.get("album", "") or "").lower()
            if keyword in title or keyword in singer or keyword in album:
                filtered.append(item)
        self._populate_rank_table(filtered)
        self.rank_status.setText(f"过滤结果：{len(filtered)} / {len(all_items)} 首歌曲")

    def _show_rank_context_menu(self, pos):
        """榜单表格右键菜单"""
        from PyQt5.QtWidgets import QApplication
        item = self.rank_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        rank_item = self.rank_table.item(row, 0).data(Qt.UserRole) if self.rank_table.item(row, 0) else None
        if not rank_item:
            return
        menu = QMenu(self)
        title = rank_item.get("music_title", "")
        bvid = rank_item.get("creation_bvid", "") or rank_item.get("mv_bvid", "")

        act_copy_title = menu.addAction("复制歌曲标题")
        act_copy_singer = menu.addAction("复制歌手名")
        if bvid:
            act_copy_bvid = menu.addAction("复制关联稿件BV号")
            act_open_browser = menu.addAction("在浏览器打开稿件")
        else:
            act_copy_bvid = None
            act_open_browser = None
        menu.addSeparator()
        act_query_audio = menu.addAction("去歌曲解析查询此歌曲")

        action = menu.exec_(self.rank_table.viewport().mapToGlobal(pos))
        if action == act_copy_title:
            QApplication.clipboard().setText(title)
            self.rank_status.setText("已复制歌曲标题")
        elif action == act_copy_singer:
            QApplication.clipboard().setText(rank_item.get("singer", ""))
            self.rank_status.setText("已复制歌手名")
        elif act_copy_bvid is not None and action == act_copy_bvid:
            QApplication.clipboard().setText(bvid)
            self.rank_status.setText("已复制BV号")
        elif act_open_browser is not None and action == act_open_browser:
            import webbrowser
            url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""
            if url:
                webbrowser.open(url)
        elif action == act_query_audio:
            # 切到歌曲解析子页并填入歌曲标题（用户可手动确认）
            self.sub_tabs.setCurrentIndex(0)
            self.au_input.setFocus()
            self.au_input.setText(title)
            self.rank_status.setText(f"已填入歌曲名，请确认后查询")

    def _on_music_list_error(self, msg):
        self.rank_status.setText(f"加载失败: {msg}")
        QMessageBox.warning(self, "加载失败", msg)

    def cleanup(self):
        """清理资源"""
        for t in [self.info_thread, self.stream_thread, self.lyric_thread,
                  self.rank_periods_thread, self.rank_music_thread]:
            if t and t.isRunning():
                try:
                    t.quit()
                    t.wait(2000)
                except Exception:
                    pass
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self.download_thread.wait(3000)
