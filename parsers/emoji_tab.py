# -*- coding: utf-8 -*-
"""
B站表情包功能 Tab 页
功能：表情包列表浏览、表情预览、批量下载
子页：我的表情包 / 所有表情包 / 按ID查询
"""

import os
import io
import re
import json
import logging
import threading

import sip
import requests
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtProperty, QSize, QUrl, QTimer, QEasingCurve, QPropertyAnimation, QRect
from PyQt5.QtGui import QPixmap, QIcon, QImage, QColor, QPainter, QLinearGradient, QBrush
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QProgressBar, QGroupBox, QScrollArea,
    QFileDialog, QMessageBox, QSplitter, QTabWidget,
    QListWidget, QListWidgetItem, QSizePolicy, QFrame, QGraphicsOpacityEffect
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Pillow：用于剥离 PNG 的 iCCP/sRGB profile，避免 Qt 加载时崩溃
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from emoji_parser import EmojiParser, PACKAGE_TYPE_MAP, BUSINESS_MAP
except ImportError:
    EmojiParser = None

logger = logging.getLogger(__name__)

# 尝试导入 scale/scale_style
try:
    from ui import scale, scale_style
except ImportError:
    def scale(v): return int(v)
    def scale_style(s): return re.sub(r'(\d+)px', lambda m: str(int(m.group(1))) + 'px', s)


# 表情包列表项角色
ROLE_PACKAGE = Qt.UserRole + 1     # 完整表情包对象
ROLE_EMOTE = Qt.UserRole + 1       # 表情对象（网格项）
ROLE_THUMB_URL = Qt.UserRole + 2   # 封面图 URL（按需加载用）
ROLE_THUMB_LOADED = Qt.UserRole + 3  # 封面图是否已加载（按需加载去重）


def safe_load_pixmap(data):
    """安全加载图片字节为 QPixmap。
    B站表情 PNG 内嵌不规范的 iCCP/sRGB profile，直接用 Qt 加载会崩溃
    (STATUS_STACK_BUFFER_OVERRUN)。用 Pillow 重存剥离元数据后再交给 Qt。
    """
    if not data:
        return QPixmap()
    # 优先用 Pillow 重存，剥离 iCCP/sRGB profile
    if HAS_PIL:
        try:
            im = PILImage.open(io.BytesIO(data))
            im.load()
            buf = io.BytesIO()
            # 统一转 RGBA 避免模式问题，保留透明通道
            if im.mode not in ("RGBA", "RGB"):
                im = im.convert("RGBA")
            im.save(buf, format="PNG", optimize=False)
            img = QImage.fromData(buf.getvalue())
            if not img.isNull():
                return QPixmap.fromImage(img)
        except Exception as e:
            logger.warning(f"Pillow 处理图片失败，回退直接加载: {e}")
    # 回退：直接用 Qt 加载（可能崩溃，仅作为无 Pillow 时的最后手段）
    img = QImage.fromData(data)
    if img.isNull():
        return QPixmap()
    return QPixmap.fromImage(img)


class SkeletonWidget(QWidget):
    """骨架屏占位 widget，带 shimmer 高光扫过动画。
    kind="list"：绘制表情包列表行骨架（图标+两行文字条），铺满自身
    kind="grid"：绘制表情网格卡片骨架，铺满自身
    每个 widget 只覆盖单个栏（pkg_list 或 emote_grid），作为该栏的子控件。
    """
    progressChanged = pyqtSignal(float)

    def __init__(self, parent=None, kind="list", rows=8, cols=6):
        super().__init__(parent)
        self._progress = 0.0
        self._kind = kind
        self._rows = rows
        self._cols = cols
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAutoFillBackground(False)
        # shimmer 循环动画
        self._shimmer = QPropertyAnimation(self, b"progress", self)
        self._shimmer.setDuration(1400)
        self._shimmer.setStartValue(0.0)
        self._shimmer.setEndValue(1.0)
        self._shimmer.setLoopCount(-1)
        self._shimmer.setEasingCurve(QEasingCurve.InOutQuad)
        # 淡出动画
        self._fade_anim = None
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)

    def get_progress(self):
        return self._progress

    def set_progress(self, v):
        self._progress = float(v)
        self.update()

    progress = pyqtProperty(float, get_progress, set_progress, notify=progressChanged)

    def start_shimmer(self):
        self._shimmer.start()

    def fade_out_and_delete(self):
        """淡出后自动销毁"""
        self._shimmer.stop()
        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(1.0)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.finished.connect(self.deleteLater)
        self._fade_anim.start()

    def _rounded(self, painter, x, y, w, h, r):
        """画圆角矩形"""
        from PyQt5.QtGui import QPainterPath
        path = QPainterPath()
        path.addRoundedRect(float(x), float(y), float(w), float(h), float(r), float(r))
        painter.fillPath(path, QBrush(QColor("#eef0f3")))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return
        # 背景半透明白，盖住底层内容
        painter.fillRect(0, 0, w, h, QColor(255, 255, 255, 235))

        gap = scale(8)

        if self._kind == "list":
            # 列表行骨架：图标 + 两行文字条，铺满自身宽度
            row_h = scale(52)
            row_gap = scale(6)
            y = gap
            for i in range(self._rows):
                if y + row_h > h - gap:
                    break
                self._rounded(painter, gap, y, scale(44), scale(44), scale(6))
                tx = gap + scale(44) + scale(10)
                self._rounded(painter, tx, y + scale(8), w - tx - scale(12), scale(10), scale(4))
                self._rounded(painter, tx, y + scale(26), scale(60), scale(8), scale(4))
                y += row_h + row_gap
        else:
            # 网格卡片骨架，铺满自身宽度
            card = scale(88)
            card_gap = scale(10)
            cy = gap
            for r in range(self._rows):
                cx = gap
                for c in range(self._cols):
                    if cx + card > w - gap:
                        break
                    if cy + card > h - gap:
                        break
                    self._rounded(painter, cx, cy, card, card, scale(8))
                    cx += card + card_gap
                cy += card + card_gap

        band_w = max(w, h) * 0.35
        diag = (w + h)
        offset = self._progress * (diag + band_w) - band_w
        grad = QLinearGradient(offset, 0, offset + band_w, 0)
        c0 = QColor(255, 255, 255, 0)
        c1 = QColor(255, 255, 255, 90)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.5, c1)
        grad.setColorAt(1.0, c0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(grad))
        from PyQt5.QtGui import QPolygonF
        from PyQt5.QtCore import QPointF
        shear = h * 0.5
        poly = QPolygonF([
            QPointF(offset, 0),
            QPointF(offset + band_w, 0),
            QPointF(offset + band_w - shear, h),
            QPointF(offset - shear, h),
        ])
        painter.drawPolygon(poly)


class EmojiDownloadThread(QThread):
    """表情包图片批量下载线程（顺序下载）"""
    progress_updated = pyqtSignal(int, int, str)   # done, total, current_name
    one_finished = pyqtSignal(str, bool, str)      # name, ok, path_or_error
    all_finished = pyqtSignal(int, int)            # success_count, fail_count
    error_occurred = pyqtSignal(str)

    def __init__(self, emotes, save_dir, package_name="", overwrite=False):
        """
        :param emotes: 表情对象列表 [{text, url, ...}, ...]
        :param save_dir: 保存目录（表情包子目录的父目录）
        :param package_name: 表情包名称（用于创建子文件夹）
        :param overwrite: 是否覆盖已存在文件
        """
        super().__init__()
        self.emotes = emotes or []
        self.save_dir = save_dir
        self.package_name = package_name or "表情包"
        self.overwrite = overwrite
        self._stop_flag = False

    def run(self):
        # 创建表情包子目录（按表情包名称）
        safe_name = self._sanitize_filename(self.package_name)
        target_dir = os.path.join(self.save_dir, safe_name)
        try:
            os.makedirs(target_dir, exist_ok=True)
        except Exception as e:
            self.error_occurred.emit(f"创建目录失败: {e}")
            return

        total = len(self.emotes)
        success = 0
        fail = 0
        for i, emote in enumerate(self.emotes):
            if self._stop_flag:
                break
            text = emote.get("text", "") or f"emote_{i}"
            url = emote.get("url", "")
            self.progress_updated.emit(i, total, text)
            if not url:
                self.one_finished.emit(text, False, "URL为空")
                fail += 1
                continue
            # 文件名：转义符 + 原始扩展名
            ext = self._get_ext_from_url(url)
            filename = self._sanitize_filename(text) + ext
            filepath = os.path.join(target_dir, filename)
            try:
                if os.path.exists(filepath) and not self.overwrite:
                    self.one_finished.emit(text, True, filepath)
                    success += 1
                    continue
                ok, err = self._download_one(url, filepath)
                if ok:
                    self.one_finished.emit(text, True, filepath)
                    success += 1
                else:
                    self.one_finished.emit(text, False, err)
                    fail += 1
            except Exception as e:
                self.one_finished.emit(text, False, str(e))
                fail += 1
        self.progress_updated.emit(total, total, "")
        self.all_finished.emit(success, fail)

    def _download_one(self, url, filepath):
        """下载单张图片，返回 (ok, error)"""
        try:
            resp = requests.get(url, timeout=15, stream=True,
                                headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if self._stop_flag:
                        return False, "已取消"
                    if chunk:
                        f.write(chunk)
            return True, ""
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _get_ext_from_url(url):
        """从URL推断扩展名"""
        lower = url.lower().split("?")[0]
        for ext in (".gif", ".png", ".webp", ".jpg", ".jpeg"):
            if lower.endswith(ext):
                return ext
        return ".png"

    @staticmethod
    def _sanitize_filename(name):
        """清理文件名中的非法字符"""
        if not name:
            return "未命名"
        # Windows 文件名非法字符: \ / : * ? " < > |
        illegal = '\\/:*?"<>|'
        for ch in illegal:
            name = name.replace(ch, "_")
        name = name.strip().rstrip(".")
        return name or "未命名"

    def stop(self):
        self._stop_flag = True


class EmojiTab(QWidget):
    """表情包功能 Tab 页"""

    # 线程安全信号
    _list_loaded_signal = pyqtSignal(str, bool, object, str)   # subtab_key, success, data, error
    _detail_loaded_signal = pyqtSignal(str, int, bool, object, str)  # subtab_key, pkg_id, success, emote_list, error
    _error_signal = pyqtSignal(str)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_window = parent
        self.emoji_parser = None
        self.download_thread = None
        # 每个子tab的控件与数据：key -> dict
        self._subtabs = {}
        # 当前各子tab选中的表情包对象（用于下载）
        self._current_packages = {}  # subtab_key -> 当前选中的package对象
        # 正在按需加载明细的 pkg_id 集合（防止重复请求）
        self._loading_detail_ids = set()

        self._init_parser()
        self._init_ui()
        self._init_network()

        # 连接线程安全信号
        self._list_loaded_signal.connect(self._on_list_loaded)
        self._detail_loaded_signal.connect(self._on_detail_loaded)
        self._error_signal.connect(self._on_error_msg)

        # 自动刷新：首次显示时自动加载各子tab（my、all；byid 需用户输入不自动加载）
        self._auto_loaded_keys = set()  # 已自动加载过的子tab key
        self._first_show_pending = True

    def showEvent(self, event):
        """首次显示时自动加载列表型子tab"""
        super().showEvent(event)
        if self._first_show_pending:
            self._first_show_pending = False
            # 延迟一点，避免与主窗口初始化抢资源
            QTimer.singleShot(100, self._auto_load_all_tabs)

    def _auto_load_all_tabs(self):
        """自动加载"我的表情包"和"所有表情包"子tab。
        byid 子tab 需要用户输入 ID，不自动加载。
        串行触发：先 my，my 加载完成后再触发 all（避免并发请求争抢）。
        """
        if "my" in self._subtabs and self.emoji_parser and "my" not in self._auto_loaded_keys:
            # 切换到"我的表情包"子tab并触发加载
            idx = self.sub_tabs.indexOf(self._subtabs["my"]["page"])
            if idx >= 0:
                self.sub_tabs.setCurrentIndex(idx)
            self._load_list("my")

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

    def _init_parser(self):
        if EmojiParser is None:
            return
        cookies, csrf_token, source = self._get_cookies_from_parent()
        self.emoji_parser = EmojiParser(config=self.config, cookies=cookies, csrf_token=csrf_token)
        logger.info(f"表情包Tab初始化，Cookie来源={source}, 字段数: {len(cookies)}")

    def _refresh_cookies(self):
        if not self.emoji_parser:
            return
        cookies, csrf_token, source = self._get_cookies_from_parent()
        if cookies:
            self.emoji_parser.update_cookies(cookies, csrf_token)
            logger.info(f"表情包Tab Cookie已刷新，来源={source}, 字段数: {len(cookies)}")

    def _has_login(self):
        """判断是否有登录态"""
        cookies, _, _ = self._get_cookies_from_parent()
        return bool(cookies.get("SESSDATA"))

    def _init_network(self):
        """初始化网络管理器（用于异步加载表情缩略图）"""
        self.network_manager = QNetworkAccessManager()
        self._pending_thumbs = {}  # reply -> (item, url)

    def _abort_pending_thumbs(self, only_for_lists=None):
        """中止未完成的缩略图请求，防止 QNetworkAccessManager 被海量请求堵死。
        only_for_lists: 若提供（QListWidget 列表），仅中止 item 属于这些 list 的请求，
                        不影响其它子tab的请求；为 None 则中止全部。
        中止时会重置 item 的 ROLE_THUMB_LOADED 标记，使其后续可重新加载。
        """
        if only_for_lists is None:
            # 全量中止
            targets = list(self._pending_thumbs.items())
            self._pending_thumbs.clear()
        else:
            targets = []
            for reply, (item, url) in list(self._pending_thumbs.items()):
                try:
                    if sip.isdeleted(item):
                        targets.append((reply, item))
                        self._pending_thumbs.pop(reply, None)
                        continue
                    lw = item.listWidget()
                    if lw in only_for_lists:
                        targets.append((reply, item))
                        self._pending_thumbs.pop(reply, None)
                except Exception:
                    targets.append((reply, None))
                    self._pending_thumbs.pop(reply, None)
        for reply, item in targets:
            try:
                if not sip.isdeleted(reply):
                    reply.abort()
                    reply.deleteLater()
            except Exception:
                pass
            # 重置加载标记，使 item 后续可重新发起缩略图请求
            if item is not None and not sip.isdeleted(item):
                try:
                    item.setData(ROLE_THUMB_LOADED, False)
                except Exception:
                    pass

    _GB = """
        QGroupBox {
            font-size: 12px; font-weight: 600; color: #555;
            border: 1px solid #e0e4ea; border-radius: 6px;
            margin-top: 12px; padding: 8px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }
    """

    def _init_ui(self):
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

        self._create_emoji_subtab("my", "我的表情包", needs_login=True, mode="my")
        self._create_emoji_subtab("all", "所有表情包", needs_login=True, mode="all")
        self._create_emoji_subtab("byid", "按ID查询", needs_login=False, mode="byid")

        main_layout.addWidget(self.sub_tabs)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(scale_style("font-size: 11px; color: #6c757d; padding: 1px;"))
        main_layout.addWidget(self.status_label)

    def _create_emoji_subtab(self, key, title, needs_login, mode):
        """创建一个表情包子tab
        :param key: 子tab唯一标识
        :param title: 子tab标题
        :param needs_login: 是否需要登录
        :param mode: my/all/byid
        """
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(scale(6))
        layout.setContentsMargins(scale(8), scale(8), scale(8), scale(8))

        toolbar = QHBoxLayout()
        toolbar.setSpacing(scale(6))

        if mode == "byid":
            toolbar.addWidget(QLabel("表情包ID:"))
            id_input = QLineEdit()
            id_input.setPlaceholderText("输入表情包ID，多个用逗号分隔")
            id_input.setMinimumHeight(scale(28))
            id_input.setStyleSheet(scale_style("padding: 4px 8px;"))
            id_input.returnPressed.connect(lambda: self._load_byid(key))
            toolbar.addWidget(id_input, stretch=1)
            self._subtabs.setdefault(key, {})["id_input"] = id_input

            query_btn = QPushButton("查询")
            query_btn.setStyleSheet(scale_style(
                "padding: 6px 16px; background-color: #00a1d6; color: white; border: none; border-radius: 4px; font-size: 12px;"))
            query_btn.setMinimumHeight(scale(28))
            query_btn.clicked.connect(lambda: self._load_byid(key))
            toolbar.addWidget(query_btn)
        else:
            refresh_btn = QPushButton("刷新列表")
            refresh_btn.setStyleSheet(scale_style(
                "padding: 6px 16px; background-color: #00a1d6; color: white; border: none; border-radius: 4px; font-size: 12px;"))
            refresh_btn.setMinimumHeight(scale(28))
            refresh_btn.clicked.connect(lambda: self._load_list(key))
            toolbar.addWidget(refresh_btn)

            toolbar.addWidget(QLabel("场景:"))
            biz_combo = QComboBox()
            biz_combo.addItem("评论区", "reply")
            biz_combo.addItem("动态", "dynamic")
            biz_combo.setMinimumHeight(scale(28))
            biz_combo.setStyleSheet(scale_style("padding: 4px 8px;"))
            # 恢复上次选择
            if self.config:
                last_biz = self.config.get_app_setting("emoji_business", "reply")
                idx = biz_combo.findData(last_biz)
                if idx >= 0:
                    biz_combo.setCurrentIndex(idx)
            biz_combo.currentIndexChanged.connect(
                lambda i, k=key: self._on_business_changed(k))
            toolbar.addWidget(biz_combo)
            self._subtabs.setdefault(key, {})["biz_combo"] = biz_combo

            if needs_login:
                login_label = QLabel()
                login_label.setStyleSheet(scale_style("font-size: 11px; color: #6c757d;"))
                toolbar.addWidget(login_label)
                self._subtabs.setdefault(key, {})["login_label"] = login_label

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 左右分栏：左侧表情包列表 + 右侧表情网格
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        # 左侧容器：搜索栏 + 表情包列表
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(scale(4))
        pkg_search_input = QLineEdit()
        pkg_search_input.setPlaceholderText("搜索表情包...")
        pkg_search_input.setMinimumHeight(scale(26))
        pkg_search_input.setStyleSheet(scale_style("padding: 2px 6px;"))
        pkg_search_input.textChanged.connect(lambda _, k=key: self._filter_pkg_list(k))
        left_layout.addWidget(pkg_search_input)
        self._subtabs.setdefault(key, {})["pkg_search_input"] = pkg_search_input

        pkg_list = QListWidget()
        pkg_list.setIconSize(QSize(scale(48), scale(48)))
        pkg_list.setStyleSheet(scale_style("""
            QListWidget { background-color: white; border: 1px solid #e0e4ea; border-radius: 4px; font-size: 12px; }
            QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #f0f0f0; }
            QListWidget::item:selected { background-color: #e6f4ff; color: #00a1d6; }
        """))
        pkg_list.itemClicked.connect(lambda item, k=key: self._on_package_selected(k, item))
        pkg_list.setMinimumWidth(scale(200))
        pkg_list.setContextMenuPolicy(Qt.CustomContextMenu)
        pkg_list.customContextMenuRequested.connect(lambda pos, k=key: self._show_pkg_context_menu(k, pos))
        left_layout.addWidget(pkg_list)
        splitter.addWidget(left_container)
        self._subtabs.setdefault(key, {})["pkg_list"] = pkg_list

        # 右侧容器：搜索栏 + 表情网格
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(scale(4))
        emote_search_input = QLineEdit()
        emote_search_input.setPlaceholderText("搜索表情...")
        emote_search_input.setMinimumHeight(scale(26))
        emote_search_input.setStyleSheet(scale_style("padding: 2px 6px;"))
        emote_search_input.textChanged.connect(lambda _, k=key: self._filter_emote_grid(k))
        right_layout.addWidget(emote_search_input)
        self._subtabs.setdefault(key, {})["emote_search_input"] = emote_search_input

        # 右侧：表情网格
        emote_grid = QListWidget()
        emote_grid.setViewMode(QListWidget.IconMode)
        emote_grid.setIconSize(QSize(scale(72), scale(72)))
        emote_grid.setResizeMode(QListWidget.Adjust)
        emote_grid.setMovement(QListWidget.Static)
        emote_grid.setSelectionMode(QListWidget.ExtendedSelection)
        emote_grid.setWrapping(True)
        emote_grid.setSpacing(scale(6))
        emote_grid.setStyleSheet(scale_style("""
            QListWidget { background-color: #fafbfc; border: 1px solid #e0e4ea; border-radius: 4px; }
            QListWidget::item { background-color: white; border: 1px solid #e0e4ea; border-radius: 4px; padding: 4px; }
            QListWidget::item:selected { background-color: #e6f4ff; border-color: #00a1d6; }
        """))
        emote_grid.setToolTip("点击选择表情，支持Ctrl/Shift多选")
        emote_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        emote_grid.customContextMenuRequested.connect(lambda pos, k=key: self._show_emote_context_menu(k, pos))
        right_layout.addWidget(emote_grid)
        splitter.addWidget(right_container)
        self._subtabs.setdefault(key, {})["emote_grid"] = emote_grid

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([scale(220), scale(600)])
        layout.addWidget(splitter, stretch=1)
        self._subtabs.setdefault(key, {})["splitter"] = splitter

        # 表情包信息标签
        info_label = QLabel("请选择一个表情包")
        info_label.setStyleSheet(scale_style("font-size: 11px; color: #6c757d; padding: 2px;"))
        layout.addWidget(info_label)
        self._subtabs.setdefault(key, {})["info_label"] = info_label

        # 底部下载工具栏
        dl_bar = QHBoxLayout()
        dl_bar.setSpacing(scale(6))

        dl_bar.addWidget(QLabel("保存到:"))
        path_input = QLineEdit()
        path_input.setMinimumHeight(scale(28))
        path_input.setStyleSheet(scale_style("padding: 4px 8px;"))
        if self.config:
            last_path = self.config.get_app_setting("emoji_last_save_path", "") or \
                        self.config.get_app_setting("default_save_path", "")
            path_input.setText(last_path)
        self._subtabs.setdefault(key, {})["path_input"] = path_input
        dl_bar.addWidget(path_input, stretch=1)

        browse_btn = QPushButton("浏览")
        browse_btn.setStyleSheet(scale_style(
            "padding: 6px 12px; background-color: #f0f2f5; color: #333; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px;"))
        browse_btn.setMinimumHeight(scale(28))
        browse_btn.clicked.connect(lambda _, k=key: self._browse_save_path(k))
        dl_bar.addWidget(browse_btn)

        select_all_btn = QPushButton("全选")
        select_all_btn.setStyleSheet(scale_style(
            "padding: 6px 12px; background-color: #f0f2f5; color: #333; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px;"))
        select_all_btn.setMinimumHeight(scale(28))
        select_all_btn.clicked.connect(lambda _, k=key: self._select_all(k, True))
        dl_bar.addWidget(select_all_btn)

        deselect_btn = QPushButton("全不选")
        deselect_btn.setStyleSheet(scale_style(
            "padding: 6px 12px; background-color: #f0f2f5; color: #333; border: 1px solid #d9d9d9; border-radius: 4px; font-size: 12px;"))
        deselect_btn.setMinimumHeight(scale(28))
        deselect_btn.clicked.connect(lambda _, k=key: self._select_all(k, False))
        dl_bar.addWidget(deselect_btn)

        dl_selected_btn = QPushButton("下载选中")
        dl_selected_btn.setStyleSheet(scale_style(
            "padding: 6px 16px; background-color: #52c41a; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        dl_selected_btn.setMinimumHeight(scale(28))
        dl_selected_btn.clicked.connect(lambda _, k=key: self._download_selected(k))
        dl_bar.addWidget(dl_selected_btn)
        self._subtabs.setdefault(key, {})["dl_selected_btn"] = dl_selected_btn

        dl_all_btn = QPushButton("下载整包")
        dl_all_btn.setStyleSheet(scale_style(
            "padding: 6px 16px; background-color: #00a1d6; color: white; border: none; border-radius: 4px; font-size: 12px; font-weight: 500;"))
        dl_all_btn.setMinimumHeight(scale(28))
        dl_all_btn.clicked.connect(lambda _, k=key: self._download_whole(k))
        dl_bar.addWidget(dl_all_btn)
        self._subtabs.setdefault(key, {})["dl_all_btn"] = dl_all_btn

        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet(scale_style(
            "padding: 6px 12px; background-color: #f56c6c; color: white; border: none; border-radius: 4px; font-size: 12px;"))
        cancel_btn.setMinimumHeight(scale(28))
        cancel_btn.setEnabled(False)
        cancel_btn.clicked.connect(self._cancel_download)
        dl_bar.addWidget(cancel_btn)
        self._subtabs.setdefault(key, {})["cancel_btn"] = cancel_btn

        layout.addLayout(dl_bar)

        progress = QProgressBar()
        progress.setValue(0)
        progress.setTextVisible(True)
        progress.setStyleSheet(scale_style("""
            QProgressBar { background-color: #f0f2f5; border: 1px solid #d9d9d9; border-radius: 4px; text-align: center; font-size: 11px; height: 18px; }
            QProgressBar::chunk { background-color: #00a1d6; border-radius: 3px; }
        """))
        layout.addWidget(progress)
        self._subtabs.setdefault(key, {})["progress"] = progress

        # 存储子tab元信息
        self._subtabs[key]["mode"] = mode
        self._subtabs[key]["needs_login"] = needs_login
        self._subtabs[key]["page"] = page
        self._subtabs[key]["packages"] = []  # 当前列表中的所有表情包
        self._subtabs[key]["current_pkg"] = None  # 当前选中的表情包

        self.sub_tabs.addTab(page, title)

        # 更新登录状态显示
        if needs_login:
            self._update_login_status(key)

    def _update_login_status(self, key):
        """更新登录状态标签"""
        sub = self._subtabs.get(key, {})
        label = sub.get("login_label")
        if not label:
            return
        if self._has_login():
            label.setText("已登录")
            label.setStyleSheet(scale_style("font-size: 11px; color: #52c41a;"))
        else:
            label.setText("未登录(仅免费)")
            label.setStyleSheet(scale_style("font-size: 11px; color: #faad14;"))

    def _get_business(self, key):
        sub = self._subtabs.get(key, {})
        combo = sub.get("biz_combo")
        if combo:
            return combo.currentData() or "reply"
        return "reply"

    def _on_business_changed(self, key):
        """业务场景切换，保存配置"""
        biz = self._get_business(key)
        if self.config:
            self.config.set_app_setting("emoji_business", biz)
        sub = self._subtabs.get(key, {})
        sub.get("pkg_list").clear()
        sub.get("emote_grid").clear()
        sub["packages"] = []
        sub["current_pkg"] = None
        self._hide_skeleton(key)
        sub.get("info_label").setText("请选择一个表情包")

    def _show_skeleton(self, key, count=8, cover="all"):
        """显示骨架屏占位（带 shimmer 动画）。
        骨架屏拆成两个独立 widget，分别作为 pkg_list 和 emote_grid 的子控件，
        各盖各的栏，不再用一个 widget 覆盖整个 splitter。
        cover="all"   :左栏列表骨架 + 右栏网格骨架（首次加载列表）
        cover="right" :只右栏网格骨架（按需拉取明细，左栏已有数据保持可见）
        cover="left"  :只左栏列表骨架（备用）
        """
        sub = self._subtabs.get(key, {})
        if not sub:
            return
        pkg_list = sub.get("pkg_list")
        emote_grid = sub.get("emote_grid")

        def _make(host, kind, rows, cols):
            """在 host 上创建/替换骨架屏，返回新 widget"""
            # 移除旧的
            old_key = "skeleton_left" if kind == "list" else "skeleton_right"
            old = sub.get(old_key)
            if old is not None:
                try:
                    old.deleteLater()
                except Exception:
                    pass
            if not host:
                return None
            skel = SkeletonWidget(host, kind=kind, rows=rows, cols=cols)
            skel.setGeometry(host.rect())
            skel.raise_()
            skel.show()
            skel.start_shimmer()
            host.installEventFilter(self)
            sub[old_key] = skel
            return skel

        if cover in ("all", "left"):
            _make(pkg_list, "list", rows=count, cols=6)
        if cover in ("all", "right"):
            _make(emote_grid, "grid", rows=3, cols=6)
        sub.get("info_label").setText("加载中...")

    def eventFilter(self, obj, event):
        """跟踪 host（pkg_list 或 emote_grid）大小变化，同步对应骨架屏几何"""
        from PyQt5.QtCore import QEvent
        if event.type() == QEvent.Resize:
            for sub in self._subtabs.values():
                for skel in (sub.get("skeleton_left"), sub.get("skeleton_right")):
                    if skel is None or sip.isdeleted(skel):
                        continue
                    # 骨架屏的 parent 就是它覆盖的 host
                    if skel.parent() is obj:
                        try:
                            skel.setGeometry(obj.rect())
                        except Exception:
                            pass
                        break
        return super().eventFilter(obj, event)

    def _hide_skeleton(self, key, cover="all"):
        """隐藏并销毁骨架屏（淡出动画）。
        cover="all"   :隐藏左右两侧
        cover="right" :只隐藏右侧网格骨架
        cover="left"  :只隐藏左侧列表骨架
        """
        sub = self._subtabs.get(key, {})
        if not sub:
            return
        keys = []
        if cover in ("all", "left"):
            keys.append("skeleton_left")
        if cover in ("all", "right"):
            keys.append("skeleton_right")
        for sk in keys:
            skel = sub.get(sk)
            if skel is not None:
                sub[sk] = None
                try:
                    if not sip.isdeleted(skel):
                        # 先立即隐藏，再播放淡出动画后删除，确保不会挡住内容
                        skel.hide()
                        skel.fade_out_and_delete()
                except Exception:
                    try:
                        skel.hide()
                        skel.deleteLater()
                    except Exception:
                        pass

    def _load_list(self, key):
        """加载表情包列表（my/all模式）"""
        if not self.emoji_parser:
            self._error_signal.emit("解析器未初始化")
            return
        sub = self._subtabs.get(key, {})
        mode = sub.get("mode")
        biz = self._get_business(key)
        self._refresh_cookies()
        # 标记该子tab已加载过（用于自动加载去重）
        self._auto_loaded_keys.add(key)
        # 中止本子tab上一轮未完成的缩略图请求，避免网络管理器拥塞
        # （仅限本子tab，不影响其它子tab进行中的缩略图请求）
        self._abort_pending_thumbs(only_for_lists=[sub.get("pkg_list"), sub.get("emote_grid")])
        self._set_status(f"正在加载{sub_tabs_title(key)}...")
        self._show_skeleton(key, count=8)
        pkg_list = sub.get("pkg_list")
        if pkg_list is not None:
            pkg_list.setEnabled(False)

        def worker():
            try:
                if mode == "my":
                    result = self.emoji_parser.get_my_emojis(business=biz)
                    if result["success"]:
                        self._list_loaded_signal.emit(key, True, result["data"], "")
                    else:
                        self._list_loaded_signal.emit(key, False, None, result.get("error", "未知错误"))
                elif mode == "all":
                    result = self.emoji_parser.get_all_emojis(business=biz)
                    if result["success"]:
                        self._list_loaded_signal.emit(key, True, result["data"], "")
                    else:
                        self._list_loaded_signal.emit(key, False, None, result.get("error", "未知错误"))
            except Exception as e:
                self._list_loaded_signal.emit(key, False, None, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _load_byid(self, key):
        """按ID查询表情包明细"""
        if not self.emoji_parser:
            self._error_signal.emit("解析器未初始化")
            return
        sub = self._subtabs.get(key, {})
        id_input = sub.get("id_input")
        raw = id_input.text().strip()
        if not raw:
            QMessageBox.warning(self, "提示", "请输入表情包ID")
            return
        # 解析ID列表
        ids = []
        for part in raw.split(","):
            part = part.strip()
            if part:
                try:
                    ids.append(int(part))
                except ValueError:
                    pass
        if not ids:
            QMessageBox.warning(self, "提示", "ID格式不正确")
            return
        biz = self._get_business(key)
        self._refresh_cookies()
        # 中止本子tab上一轮未完成的缩略图请求（不影响其它子tab）
        self._abort_pending_thumbs(only_for_lists=[sub.get("pkg_list"), sub.get("emote_grid")])
        self._set_status("正在查询表情包...")
        self._show_skeleton(key, count=min(len(ids), 6) or 4)
        sub.get("pkg_list").setEnabled(False)

        def worker():
            try:
                result = self.emoji_parser.get_package_detail(ids, business=biz)
                if result["success"]:
                    self._list_loaded_signal.emit(key, True, result["data"], "")
                else:
                    self._list_loaded_signal.emit(key, False, None, result.get("error", "未知错误"))
            except Exception as e:
                self._list_loaded_signal.emit(key, False, None, str(e))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_list_loaded(self, key, success, data, error):
        """列表加载完成回调（主线程）"""
        sub = self._subtabs.get(key, {})
        if not sub:
            return
        pkg_list = sub.get("pkg_list")
        emote_grid = sub.get("emote_grid")
        info_label = sub.get("info_label")
        if pkg_list is None or emote_grid is None:
            return
        pkg_list.setEnabled(True)
        pkg_list.clear()
        emote_grid.clear()
        sub["packages"] = []
        sub["current_pkg"] = None
        # 隐藏骨架屏（淡出动画）
        self._hide_skeleton(key)

        if not success:
            self._set_status(f"加载失败: {error}")
            if info_label is not None:
                info_label.setText(f"加载失败: {error}")
            return

        # 规范化数据为表情包列表
        packages = []
        mode = sub.get("mode")
        if mode == "all" and isinstance(data, dict):
            # all模式返回 {user_packages, all_packages}，合并展示，用户拥有的标记added
            seen_ids = set()
            for p in data.get("user_packages", []):
                p = dict(p)
                p["added"] = True
                p["_source"] = "已拥有"
                packages.append(p)
                if p.get("id") is not None:
                    seen_ids.add(p["id"])
            for p in data.get("all_packages", []):
                if p.get("id") in seen_ids:
                    continue
                p = dict(p)
                p["_source"] = "可添加"
                packages.append(p)
        elif isinstance(data, list):
            for p in data:
                p = dict(p)
                if "_source" not in p:
                    p["_source"] = ""
                packages.append(p)

        # 过滤特殊包："收藏"(id=99999999) 是虚拟收藏夹，API 不返回明细，直接剔除
        packages = [p for p in packages
                    if p.get("id") != 99999999 and p.get("text") != "收藏"]

        sub["packages"] = packages
        # 重置搜索框（不触发过滤，避免在填充前误过滤）
        search_input = sub.get("pkg_search_input")
        if search_input is not None:
            search_input.blockSignals(True)
            search_input.clear()
            search_input.blockSignals(False)
        self._populate_pkg_list(key, packages)

        # 连接滚动信号触发按需加载（只连一次）
        sb = pkg_list.verticalScrollBar()
        if not getattr(sb, "_thumb_loader_connected", False):
            sb.valueChanged.connect(lambda _: self._load_visible_pkg_thumbs(key))
            sb._thumb_loader_connected = True
        # 首次填充后立即加载当前可视区域的缩略图
        QTimer.singleShot(50, lambda: self._load_visible_pkg_thumbs(key))

        self._set_status(f"共加载 {len(packages)} 个表情包")
        if info_label is not None:
            info_label.setText(f"共 {len(packages)} 个表情包，请选择查看详情")

        # 自动选中第一个表情包并加载表情
        if packages and pkg_list.count() > 0:
            first_item = pkg_list.item(0)
            if first_item is not None:
                pkg_list.setCurrentItem(first_item)
                self._on_package_selected(key, first_item)

        # 自动加载串联：my 完成后，若 all 尚未自动加载过，触发 all 加载
        if key == "my" and "all" in self._subtabs and "all" not in self._auto_loaded_keys:
            QTimer.singleShot(150, lambda: self._auto_load_tab("all"))

    def _auto_load_tab(self, key):
        """自动加载指定子tab（供串联自动加载使用）"""
        if key in self._auto_loaded_keys:
            return
        if key in self._subtabs and self.emoji_parser:
            self._load_list(key)

    def _populate_pkg_list(self, key, packages):
        """填充左侧表情包列表（按需加载缩略图）"""
        sub = self._subtabs.get(key, {})
        pkg_list = sub.get("pkg_list")
        if pkg_list is None:
            return
        # 仅中止本子tab左栏列表的缩略图请求并重置标记
        self._abort_pending_thumbs(only_for_lists=[pkg_list])
        pkg_list.clear()
        for pkg in packages:
            item = QListWidgetItem()
            title = pkg.get("text", "未命名")
            count = pkg.get("emote_count", 0)
            source_tag = pkg.get("_source", "")
            suffix = f" [{source_tag}]" if source_tag else ""
            count_text = f"{count}个" if count > 0 else "待加载"
            item.setText(f"{title}  ({count_text}){suffix}")
            item.setData(ROLE_PACKAGE, pkg)
            item.setData(ROLE_THUMB_URL, pkg.get("url", ""))
            item.setData(ROLE_THUMB_LOADED, False)
            pkg_list.addItem(item)
        # 填充后立即加载可视区域缩略图
        QTimer.singleShot(50, lambda: self._load_visible_pkg_thumbs(key))

    def _filter_pkg_list(self, key):
        """按搜索关键词过滤左侧表情包列表"""
        sub = self._subtabs.get(key, {})
        all_pkgs = sub.get("packages", []) or []
        search_input = sub.get("pkg_search_input")
        if search_input is None:
            return
        keyword = search_input.text().strip().lower()
        if not keyword:
            self._populate_pkg_list(key, all_pkgs)
            info_label = sub.get("info_label")
            if info_label is not None:
                info_label.setText(f"共 {len(all_pkgs)} 个表情包，请选择查看详情")
            return
        filtered = []
        for pkg in all_pkgs:
            text = (pkg.get("text", "") or "").lower()
            type_name = (pkg.get("type_name", "") or "").lower()
            if keyword in text or keyword in type_name:
                filtered.append(pkg)
        self._populate_pkg_list(key, filtered)
        info_label = sub.get("info_label")
        if info_label is not None:
            info_label.setText(f"过滤结果：{len(filtered)} / {len(all_pkgs)} 个表情包")

    def _show_pkg_context_menu(self, key, pos):
        """表情包列表右键菜单"""
        from PyQt5.QtWidgets import QApplication, QMenu
        sub = self._subtabs.get(key, {})
        pkg_list = sub.get("pkg_list")
        if pkg_list is None:
            return
        item = pkg_list.itemAt(pos)
        if item is None:
            return
        pkg = item.data(ROLE_PACKAGE)
        if not pkg:
            return
        menu = QMenu(self)
        title = pkg.get("text", "")
        pkg_id = pkg.get("id", "")
        cover_url = pkg.get("url", "")

        act_select = menu.addAction("选中此表情包")
        act_copy_title = menu.addAction("复制表情包名称")
        if pkg_id:
            act_copy_id = menu.addAction("复制表情包ID")
        else:
            act_copy_id = None
        if cover_url:
            act_copy_cover = menu.addAction("复制封面URL")
            act_open_cover = menu.addAction("在浏览器打开封面")
        else:
            act_copy_cover = None
            act_open_cover = None
        menu.addSeparator()
        emotes = pkg.get("emote", []) or []
        if emotes:
            act_download = menu.addAction("下载整个表情包")
        else:
            act_download = None

        action = menu.exec_(pkg_list.viewport().mapToGlobal(pos))
        if action == act_select:
            pkg_list.setCurrentItem(item)
            self._on_package_selected(key, item)
        elif action == act_copy_title:
            QApplication.clipboard().setText(title)
            self._set_status("已复制表情包名称")
        elif act_copy_id is not None and action == act_copy_id:
            QApplication.clipboard().setText(str(pkg_id))
            self._set_status(f"已复制ID: {pkg_id}")
        elif act_copy_cover is not None and action == act_copy_cover:
            QApplication.clipboard().setText(cover_url)
            self._set_status("已复制封面URL")
        elif act_open_cover is not None and action == act_open_cover:
            import webbrowser
            webbrowser.open(cover_url)
        elif act_download is not None and action == act_download:
            pkg_list.setCurrentItem(item)
            self._on_package_selected(key, item)
            self._download_whole(key)

    def _show_emote_context_menu(self, key, pos):
        """表情网格右键菜单"""
        from PyQt5.QtWidgets import QApplication, QMenu
        sub = self._subtabs.get(key, {})
        grid = sub.get("emote_grid")
        if grid is None:
            return
        item = grid.itemAt(pos)
        if item is None:
            return
        emote = item.data(ROLE_EMOTE)
        if not emote:
            return
        menu = QMenu(self)
        text = emote.get("text", "")
        url = emote.get("url", "")
        alias = emote.get("alias", "")
        type_name = emote.get("type_name", "")

        act_copy_text = menu.addAction("复制表情文字")
        if url:
            act_copy_url = menu.addAction("复制图片URL")
            act_open = menu.addAction("在浏览器打开图片")
        else:
            act_copy_url = None
            act_open = None
        menu.addSeparator()
        act_download_one = menu.addAction("下载此表情")
        act_download_selected = menu.addAction("下载选中表情")

        action = menu.exec_(grid.viewport().mapToGlobal(pos))
        if action == act_copy_text:
            QApplication.clipboard().setText(text)
            self._set_status("已复制表情文字")
        elif act_copy_url is not None and action == act_copy_url:
            QApplication.clipboard().setText(url)
            self._set_status("已复制图片URL")
        elif act_open is not None and action == act_open:
            import webbrowser
            webbrowser.open(url)
        elif action == act_download_one:
            # 仅下载当前右键的表情
            grid.clearSelection()
            item.setSelected(True)
            self._download_selected(key)
        elif action == act_download_selected:
            self._download_selected(key)

    def _load_visible_pkg_thumbs(self, key, _retry_count=0):
        """按需加载左栏可视区域的表情包封面缩略图。
        用 visualItemRect 精确判断 item 是否在 viewport 可见区域内，
        对未加载且有 url 的发起请求；
        同时中止已离开可视区域且未完成的请求，防止请求堆积。
        首次填充后 viewport 可能尚未完成布局（高度为 0 / 扫不到 item），
        此时回退加载前 N 个 item，并安排一次延迟重试确保正确加载。
        """
        sub = self._subtabs.get(key, {})
        if not sub:
            return
        pkg_list = sub.get("pkg_list")
        if pkg_list is None:
            return

        viewport = pkg_list.viewport()
        vp_h = viewport.height()
        total = pkg_list.count()

        visible_items = []
        viewport_ready = vp_h > 0

        if viewport_ready:
            # viewport 已有尺寸，用 visualItemRect 精确判断可见性
            for i in range(total):
                item = pkg_list.item(i)
                if item is None:
                    continue
                try:
                    rect = pkg_list.visualItemRect(item)
                    # item 矩形与 viewport(0..vp_h) 有交集即为可见
                    if rect.top() < vp_h and rect.bottom() > 0:
                        visible_items.append(item)
                except Exception:
                    continue

        # 兜底：viewport 未就绪或扫不到可见 item，加载前 N 个
        fallback_used = False
        if not visible_items and total > 0:
            fallback_used = True
            fallback_n = min(20, total)
            for i in range(fallback_n):
                item = pkg_list.item(i)
                if item is not None:
                    visible_items.append(item)

        # QListWidgetItem 不可哈希，用 id() 作为集合键
        visible_set = set(id(i) for i in visible_items)
        # 对可视区域内未加载的 item 发起请求
        for item in visible_items:
            try:
                if sip.isdeleted(item):
                    continue
                if item.data(ROLE_THUMB_LOADED):
                    continue
                url = item.data(ROLE_THUMB_URL) or ""
                if not url:
                    item.setData(ROLE_THUMB_LOADED, True)
                    continue
                item.setData(ROLE_THUMB_LOADED, True)  # 标记已发起，避免重复
                self._load_pkg_thumb(item, url)
            except Exception:
                continue

        # 仅在 viewport 真正就绪（非兜底）时，才中止离开可视区域的请求，
        # 避免 viewport 未就绪时把兜底加载的请求误中止掉。
        if not fallback_used:
            to_abort = []
            for reply, (item, url) in self._pending_thumbs.items():
                # 只处理 pkg_list 的请求（emote_grid 的 item 不在 pkg_list）
                try:
                    if sip.isdeleted(item) or id(item) not in visible_set:
                        # 判断 item 是否属于这个 pkg_list
                        if item.listWidget() is pkg_list:
                            to_abort.append((reply, item))
                except Exception:
                    to_abort.append((reply, None))
            for reply, item in to_abort:
                try:
                    if not sip.isdeleted(reply):
                        reply.abort()
                        reply.deleteLater()
                except Exception:
                    pass
                self._pending_thumbs.pop(reply, None)
                # 重置加载标记，滚回可视区域时可重新发起
                if item is not None and not sip.isdeleted(item):
                    try:
                        item.setData(ROLE_THUMB_LOADED, False)
                    except Exception:
                        pass

        # 首次填充后 viewport 可能尚未布局完，安排一次延迟重试，
        # 确保 viewport 就绪后能正确加载完整可视区域（含中止离开的请求）。
        if fallback_used and _retry_count < 3:
            QTimer.singleShot(150, lambda: self._load_visible_pkg_thumbs(key, _retry_count + 1))

    def _load_pkg_thumb(self, item, url):
        """异步加载表情包封面缩略图"""
        if not url:
            return
        try:
            reply = self.network_manager.get(QNetworkRequest(QUrl(url)))
            self._pending_thumbs[reply] = (item, url)
            # 使用 weakref 避免闭包持有 reply 导致对象已被删除时仍触发访问
            import weakref
            reply_ref = weakref.ref(reply)
            reply.finished.connect(lambda: self._on_thumb_loaded(reply_ref()))
        except Exception as e:
            logger.warning(f"加载封面失败: {e}")

    def _on_thumb_loaded(self, reply):
        """缩略图加载完成"""
        # reply 可能在信号传递过程中已被 Qt 删除
        if reply is None or sip.isdeleted(reply):
            return
        info = self._pending_thumbs.pop(reply, None)
        if not info:
            try:
                reply.deleteLater()
            except RuntimeError:
                pass
            return
        item, url = info
        try:
            # 列表项可能已被销毁（用户切换表情包/刷新列表导致 clear()）
            if sip.isdeleted(item):
                return
            if reply.error() == QNetworkReply.NoError:
                data = reply.readAll()
                pixmap = safe_load_pixmap(bytes(data))
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(
                        scale(48), scale(48), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    item.setIcon(icon)
        except Exception as e:
            logger.warning(f"缩略图显示失败: {e}")
        finally:
            try:
                reply.deleteLater()
            except RuntimeError:
                pass

    def _on_package_selected(self, key, item):
        """选择表情包，加载表情网格。
        若 pkg 已有 emote 列表直接渲染；否则（all 模式）按需调用
        get_package_detail 拉取明细，期间右侧网格显示骨架屏。
        """
        pkg = item.data(ROLE_PACKAGE)
        if not pkg:
            return
        sub = self._subtabs.get(key, {})
        sub["current_pkg"] = pkg
        grid = sub.get("emote_grid")
        if grid is None:
            return
        # 仅中止本子tab右侧表情网格的缩略图请求，保留左栏列表封面缩略图
        self._abort_pending_thumbs(only_for_lists=[grid])
        grid.clear()

        emotes = pkg.get("emote", []) or []
        # emote_loaded 标记表示已按需拉取过明细（即使结果为空也不再重复请求）
        if emotes or pkg.get("emote_loaded"):
            # 已有明细（或已确认无明细），直接渲染
            self._render_emote_grid(key, pkg, emotes)
            return

        # 无明细，按需拉取
        pkg_id = pkg.get("id")
        if pkg_id is None:
            info_label = sub.get("info_label")
            if info_label is not None:
                info_label.setText("该表情包无法获取明细")
            return
        # 防止重复请求同一个包
        if pkg_id in self._loading_detail_ids:
            info_label = sub.get("info_label")
            if info_label is not None:
                info_label.setText("正在加载明细...")
            return
        # 右侧网格显示骨架屏（只覆盖右栏，左栏列表保持可见）
        self._show_skeleton(key, count=0, cover="right")
        self._load_package_detail(key, pkg_id)

    def _load_package_detail(self, key, pkg_id):
        """后台线程拉取单个表情包明细"""
        if not self.emoji_parser:
            return
        biz = self._get_business(key)
        self._loading_detail_ids.add(pkg_id)
        self._set_status(f"正在加载表情包明细 (id={pkg_id})...")

        def worker():
            try:
                result = self.emoji_parser.get_package_detail(pkg_id, business=biz)
                if result["success"]:
                    # result["data"] 是 package 列表，取第一个
                    pkgs = result["data"]
                    emote_list = pkgs[0].get("emote", []) if pkgs else []
                    self._detail_loaded_signal.emit(key, pkg_id, True, emote_list, "")
                else:
                    self._detail_loaded_signal.emit(key, pkg_id, False, None, result.get("error", "未知错误"))
            except Exception as e:
                self._detail_loaded_signal.emit(key, pkg_id, False, None, str(e))
            finally:
                self._loading_detail_ids.discard(pkg_id)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _on_detail_loaded(self, key, pkg_id, success, emote_list, error):
        """单个表情包明细加载完成（主线程）"""
        sub = self._subtabs.get(key, {})
        if not sub:
            return
        # 隐藏右栏网格骨架（明细加载完成）
        self._hide_skeleton(key, cover="right")
        # 只有当前选中的包仍是这个 pkg_id 才渲染（用户可能已切换到别的包）
        pkg = sub.get("current_pkg")
        if not pkg or pkg.get("id") != pkg_id:
            return
        if not success:
            self._set_status(f"加载明细失败: {error}")
            info_label = sub.get("info_label")
            if info_label is not None:
                info_label.setText(f"加载明细失败: {error}")
            return
        # 把明细回填到 pkg 对象，并标记已加载（避免重复请求，即使结果为空）
        pkg["emote"] = emote_list or []
        pkg["emote_count"] = len(emote_list or [])
        pkg["emote_loaded"] = True
        self._render_emote_grid(key, pkg, emote_list or [])

    def _render_emote_grid(self, key, pkg, emotes):
        """渲染表情网格（主线程）"""
        sub = self._subtabs.get(key, {})
        grid = sub.get("emote_grid")
        if grid is None:
            return
        # 保存全量数据用于搜索过滤
        sub["current_emotes"] = list(emotes or [])
        # 重置搜索框（不触发过滤循环）
        search_input = sub.get("emote_search_input")
        if search_input is not None:
            search_input.blockSignals(True)
            search_input.clear()
            search_input.blockSignals(False)
        self._populate_emote_grid(key, pkg, emotes or [])

    def _populate_emote_grid(self, key, pkg, emotes):
        """填充表情网格"""
        sub = self._subtabs.get(key, {})
        grid = sub.get("emote_grid")
        if grid is None:
            return
        info_label = sub.get("info_label")
        # 确保右侧骨架屏已隐藏（双保险）
        self._hide_skeleton(key, cover="right")
        # 仅中止右栏网格的缩略图请求
        self._abort_pending_thumbs(only_for_lists=[grid])
        grid.clear()
        title = pkg.get("text", "未命名") if pkg else ""
        type_name = pkg.get("type_name", "") if pkg else ""
        source_tag = pkg.get("_source", "") if pkg else ""
        suffix = f" [{source_tag}]" if source_tag else ""
        if not emotes:
            # 特殊包（如"收藏"id=99999999）API 不返回明细
            hint = QListWidgetItem("该表情包暂无可用表情（可能为特殊收藏夹）")
            hint.setFlags(Qt.NoItemFlags)
            hint.setTextAlignment(Qt.AlignCenter)
            grid.addItem(hint)
            if info_label is not None:
                info_label.setText(f"当前: {title}  共 0 个表情  类型: {type_name}{suffix}")
            self._set_status(f"{title} 无可用表情")
            return
        for emote in emotes:
            gi = QListWidgetItem()
            text = emote.get("text", "")
            gi.setText(text)
            gi.setToolTip(f"{text}\n{emote.get('alias', '')}\n{emote.get('type_name', '')}")
            gi.setData(ROLE_EMOTE, emote)
            gi.setSizeHint(QSize(scale(88), scale(88)))
            self._load_emote_thumb(gi, emote.get("url", ""))
            grid.addItem(gi)
        count = len(emotes)
        if info_label is not None:
            info_label.setText(f"当前: {title}  共 {count} 个表情  类型: {type_name}{suffix}")
        self._set_status(f"已加载 {title} 的 {count} 个表情")

    def _filter_emote_grid(self, key):
        """按搜索关键词过滤表情网格"""
        sub = self._subtabs.get(key, {})
        all_emotes = sub.get("current_emotes", []) or []
        pkg = sub.get("current_pkg")
        search_input = sub.get("emote_search_input")
        if search_input is None or not pkg:
            return
        keyword = search_input.text().strip().lower()
        if not keyword:
            self._populate_emote_grid(key, pkg, all_emotes)
            return
        filtered = []
        for emote in all_emotes:
            text = (emote.get("text", "") or "").lower()
            alias = (emote.get("alias", "") or "").lower()
            type_name = (emote.get("type_name", "") or "").lower()
            if keyword in text or keyword in alias or keyword in type_name:
                filtered.append(emote)
        self._populate_emote_grid(key, pkg, filtered)
        info_label = sub.get("info_label")
        if info_label is not None:
            info_label.setText(f"过滤结果：{len(filtered)} / {len(all_emotes)} 个表情")

    def _load_emote_thumb(self, item, url):
        """异步加载表情缩略图（复用网络管理器）"""
        if not url:
            return
        try:
            reply = self.network_manager.get(QNetworkRequest(QUrl(url)))
            self._pending_thumbs[reply] = (item, url)
            reply.finished.connect(lambda: self._on_emote_thumb_loaded(reply))
        except Exception as e:
            logger.warning(f"加载表情图失败: {e}")

    def _on_emote_thumb_loaded(self, reply):
        info = self._pending_thumbs.pop(reply, None)
        if not info:
            reply.deleteLater()
            return
        item, url = info
        try:
            # 列表项可能已被销毁（用户切换表情包导致网格 clear()）
            if sip.isdeleted(item):
                return
            if reply.error() == QNetworkReply.NoError:
                data = reply.readAll()
                pixmap = safe_load_pixmap(bytes(data))
                if not pixmap.isNull():
                    icon = QIcon(pixmap.scaled(
                        scale(64), scale(64), Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    item.setIcon(icon)
        except Exception as e:
            logger.warning(f"表情图显示失败: {e}")
        finally:
            reply.deleteLater()

    def _browse_save_path(self, key):
        sub = self._subtabs.get(key, {})
        path_input = sub.get("path_input")
        cur = path_input.text() or ""
        dest = QFileDialog.getExistingDirectory(self, "选择保存路径", cur)
        if dest:
            path_input.setText(dest)
            if self.config:
                self.config.set_app_setting("emoji_last_save_path", dest)

    def _select_all(self, key, select):
        sub = self._subtabs.get(key, {})
        grid = sub.get("emote_grid")
        if select:
            grid.selectAll()
        else:
            grid.clearSelection()

    def _get_selected_emotes(self, key):
        """获取当前选中的表情对象列表"""
        sub = self._subtabs.get(key, {})
        grid = sub.get("emote_grid")
        emotes = []
        for item in grid.selectedItems():
            e = item.data(ROLE_EMOTE)
            if e:
                emotes.append(e)
        return emotes

    def _start_download(self, key, emotes, package_name):
        """启动下载"""
        if not emotes:
            QMessageBox.warning(self, "提示", "没有可下载的表情")
            return
        sub = self._subtabs.get(key, {})
        save_dir = sub.get("path_input").text().strip()
        if not save_dir:
            QMessageBox.warning(self, "提示", "请选择保存路径")
            return
        if not os.path.isdir(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法创建目录: {e}")
                return

        # 取消旧线程
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "提示", "当前有下载任务正在执行")
            return

        # 重置进度
        progress = sub.get("progress")
        progress.setValue(0)
        progress.setFormat(f"0/{len(emotes)}")
        sub.get("cancel_btn").setEnabled(True)
        sub.get("dl_selected_btn").setEnabled(False)
        sub.get("dl_all_btn").setEnabled(False)
        self._set_status(f"开始下载 {package_name} 的 {len(emotes)} 个表情...")

        # 绑定 key 以便信号回调更新对应子tab
        self.download_thread = EmojiDownloadThread(emotes, save_dir, package_name, overwrite=False)
        self._dl_active_key = key
        self.download_thread.progress_updated.connect(self._on_dl_progress)
        self.download_thread.one_finished.connect(self._on_dl_one)
        self.download_thread.all_finished.connect(self._on_dl_all)
        self.download_thread.error_occurred.connect(self._on_dl_error)
        self.download_thread.start()

    def _download_selected(self, key):
        """下载选中的表情"""
        emotes = self._get_selected_emotes(key)
        if not emotes:
            QMessageBox.information(self, "提示", "请先在右侧网格中选择表情")
            return
        sub = self._subtabs.get(key, {})
        pkg = sub.get("current_pkg")
        pkg_name = pkg.get("text", "表情包") if pkg else "表情包"
        self._start_download(key, emotes, pkg_name)

    def _download_whole(self, key):
        """下载整个表情包"""
        sub = self._subtabs.get(key, {})
        pkg = sub.get("current_pkg")
        if not pkg:
            QMessageBox.information(self, "提示", "请先在左侧选择一个表情包")
            return
        emotes = pkg.get("emote", []) or []
        if not emotes:
            QMessageBox.information(self, "提示", "该表情包没有表情数据")
            return
        self._start_download(key, emotes, pkg.get("text", "表情包"))

    def _cancel_download(self):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
            self._set_status("正在取消下载...")
        else:
            self._reset_dl_buttons()

    def _reset_dl_buttons(self):
        key = getattr(self, "_dl_active_key", None)
        if not key:
            return
        sub = self._subtabs.get(key, {})
        sub.get("cancel_btn").setEnabled(False)
        sub.get("dl_selected_btn").setEnabled(True)
        sub.get("dl_all_btn").setEnabled(True)

    def _on_dl_progress(self, done, total, current):
        key = getattr(self, "_dl_active_key", None)
        if not key:
            return
        sub = self._subtabs.get(key, {})
        progress = sub.get("progress")
        pct = int(done * 100 / total) if total else 0
        progress.setValue(pct)
        progress.setFormat(f"{done}/{total}")
        if current:
            self._set_status(f"下载中 ({done}/{total}): {current}")

    def _on_dl_one(self, name, ok, info):
        if not ok:
            logger.warning(f"表情下载失败: {name} -> {info}")

    def _on_dl_all(self, success, fail):
        key = getattr(self, "_dl_active_key", None)
        self._reset_dl_buttons()
        msg = f"下载完成: 成功 {success} 个, 失败 {fail} 个"
        self._set_status(msg)
        if key:
            sub = self._subtabs.get(key, {})
            progress = sub.get("progress")
            progress.setValue(100)
            progress.setFormat(f"{success}/{success + fail}")
        QMessageBox.information(self, "完成", msg)

    def _on_dl_error(self, err):
        self._reset_dl_buttons()
        self._set_status(f"下载错误: {err}")
        QMessageBox.critical(self, "错误", f"下载错误: {err}")

    def _set_status(self, msg):
        self.status_label.setText(msg)

    def _on_error_msg(self, msg):
        self._set_status(f"错误: {msg}")
        QMessageBox.warning(self, "提示", msg)

    def cleanup(self):
        """资源清理（主窗口关闭时调用）"""
        try:
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.stop()
                self.download_thread.wait(2000)
        except Exception:
            pass
        # 清理所有骨架屏动画
        try:
            for key, sub in self._subtabs.items():
                for sk in ("skeleton_left", "skeleton_right"):
                    skel = sub.get(sk)
                    if skel is not None:
                        sub[sk] = None
                        if not sip.isdeleted(skel):
                            skel.deleteLater()
        except Exception:
            pass


def sub_tabs_title(key):
    """子tab标题映射"""
    return {"my": "我的表情包", "all": "所有表情包", "byid": "按ID查询"}.get(key, "表情包")
