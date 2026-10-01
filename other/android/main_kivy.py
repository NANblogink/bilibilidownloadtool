#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B站视频解析工具 —— Android 端入口（Kivy，竖屏）。

设计目标
========

1. **功能与桌面版一模一样**
   界面层是 Kivy 重写的（Android 没有 PyQt5），但**业务层完全复用桌面版
   同一份代码**，不做任何"Android 特供"的实现：

       parsers/bilibili_parser.py   —— 解析（投稿/番剧/合集/课堂/直播/收藏夹）
       core/downloader.py           —— 下载引擎（并发/断点续传/合并）
       core/task_manager.py         —— 任务持久化
       core/tool_manager.py         —— ffmpeg / mp4decrypt 管理
       core/download_history.py     —— 历史记录
       core/config.py               —— 配置

   桌面版的 `core/downloader.py`、`core/utils.py` 顶层 `import PyQt5`，
   而 Android 没有 PyQt5。为了不改动桌面版代码，这里在导入前安装
   `qt_compat` 影子包（提供 QObject/pyqtSignal/QThread/QMutex/
   QWaitCondition/Qt 的最小实现），使同一份引擎代码能原样跑起来。

2. **强制竖屏**
   打包配置 `android.orientation = portrait`，界面按竖屏单列布局设计。

3. **中文不乱码**
   随包携带微软雅黑子集字体（NotoSansSC-Regular/Bold.ttf，
   由 make_font.py 生成），并在启动时把 Kivy 默认字体替换掉。

4. **使用项目自带图标**
   启动图标由 make_icon.py 从项目根目录 logo.png 生成；
   标题栏也直接显示同一张图。

性能取向（"别把电脑搞崩"）
========================

* 并发数按设备内存自动下调
* 不做悬浮球 / 系统托盘（Android 无此概念，改用通知栏）
* 界面切后台暂停刷新
"""
import os
import sys
import threading
import time
import traceback

# ==========================================================================
# 0. 路径注入（必须最早执行）
# ==========================================================================
_HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))

for _sub in ("", _HERE, "core", os.path.join("core", "infra"), "parsers",
             os.path.join("other", "android")):
    _p = os.path.join(PROJECT_ROOT, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

# 移动端不做代理：B站为国内站点，直连最快
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
           "ALL_PROXY", "all_proxy"):
    os.environ.pop(_k, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

# ==========================================================================
# 1. 安装 Qt 兼容层（须先于任何 core 模块）
# ==========================================================================
try:
    import qt_compat
    qt_compat.install()
except Exception:
    traceback.print_exc()

# ==========================================================================
# 2. Kivy
# ==========================================================================
from kivy.app import App                      # noqa: E402
from kivy.clock import Clock                  # noqa: E402
from kivy.core.text import LabelBase          # noqa: E402
from kivy.core.window import Window           # noqa: E402
from kivy.graphics import Color, RoundedRectangle   # noqa: E402
from kivy.lang import Builder                 # noqa: E402
from kivy.metrics import dp, sp               # noqa: E402
from kivy.properties import (BooleanProperty, NumericProperty,  # noqa: E402
                             StringProperty)
from kivy.uix.boxlayout import BoxLayout      # noqa: E402
from kivy.uix.button import Button            # noqa: E402
from kivy.uix.checkbox import CheckBox        # noqa: E402
from kivy.uix.image import Image              # noqa: E402
from kivy.uix.label import Label              # noqa: E402
from kivy.uix.popup import Popup              # noqa: E402
from kivy.uix.progressbar import ProgressBar  # noqa: E402
from kivy.uix.scrollview import ScrollView    # noqa: E402
from kivy.uix.spinner import Spinner          # noqa: E402
from kivy.uix.tabbedpanel import (TabbedPanel,  # noqa: E402
                                  TabbedPanelItem)
from kivy.uix.textinput import TextInput      # noqa: E402
from kivy.utils import platform               # noqa: E402

# ------------------------------------------------------------------ 字体
# Kivy 默认字体无汉字，不换字体界面全是方块
_FONT_DIR = _HERE
_FONT_REG = os.path.join(_FONT_DIR, "NotoSansSC-Regular.ttf")
_FONT_BOLD = os.path.join(_FONT_DIR, "NotoSansSC-Bold.ttf")


def _register_fonts():
    """把随包的中文字体注册给 Kivy。"""
    reg = bold = None
    if os.path.isfile(_FONT_REG):
        LabelBase.register(name="CN", fn_regular=_FONT_REG,
                           fn_bold=_FONT_BOLD if os.path.isfile(_FONT_BOLD)
                           else _FONT_REG)
        reg = "CN"
    elif os.path.isfile(_FONT_BOLD):
        LabelBase.register(name="CN", fn_regular=_FONT_BOLD)
        reg = "CN"
    if reg:
        # 覆盖默认字体，KV 里就不用逐个指定 font_name
        try:
            from kivy.config import Config
            Config.set("kivy", "default_font", "CN")
        except Exception:
            pass
    return reg


FONT_NAME = _register_fonts()

if platform != "android":
    # 桌面调试时模拟竖屏手机；无头窗口无 size，忽略
    try:
        if Window is not None and getattr(Window, "size", None):
            Window.size = (420, 860)
    except Exception:
        pass


def _is_android():
    return platform == "android"


def resource_path(*parts):
    """定位随包资源（打包后位于应用目录）。"""
    return os.path.join(_HERE, *parts)


# ==========================================================================
# 3. 设备自适应（保守，避免拖垮设备）
# ==========================================================================

def device_profile():
    profile = {"concurrency": 2, "max_tasks": 1, "chunk_mb": 2, "cpu": 1,
               "mem_gb": 0}
    try:
        from platform_utils import (recommended_concurrency,
                                    available_memory_bytes, cpu_count)
        profile["concurrency"] = max(1, min(4, recommended_concurrency(cap=4)))
        mem = available_memory_bytes() or 0
        gb = mem / float(1024 ** 3)
        profile["max_tasks"] = 1 if gb < 2 else 2
        profile["chunk_mb"] = 1 if gb < 1.5 else (2 if gb < 4 else 4)
        profile["cpu"] = cpu_count()
        profile["mem_gb"] = round(gb, 2)
    except Exception:
        pass
    return profile


PROFILE = device_profile()

# ==========================================================================
# 4. 界面 KV（配色对齐桌面版：主色/背景/文字）
# ==========================================================================

KV = """
#:import dp kivy.metrics.dp

<Card@BoxLayout>:
    orientation: "vertical"
    padding: dp(12)
    spacing: dp(8)
    size_hint_y: None
    height: self.minimum_height
    canvas.before:
        Color:
            rgba: 1, 1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(10)]

<SectionTitle@Label>:
    size_hint_y: None
    height: dp(28)
    color: 0.13, 0.13, 0.13, 1
    font_size: sp(15)
    bold: True
    halign: "left"
    valign: "middle"
    text_size: self.size

<FieldLabel@Label>:
    size_hint_y: None
    height: dp(24)
    color: 0.25, 0.25, 0.25, 1
    font_size: sp(13)
    halign: "left"
    valign: "middle"
    text_size: self.size

<HintLabel@Label>:
    size_hint_y: None
    height: dp(20)
    color: 0.5, 0.5, 0.5, 1
    font_size: sp(11)
    halign: "left"
    valign: "middle"
    text_size: self.size

<PrimaryButton@Button>:
    background_normal: ""
    background_color: 0.0, 0.63, 0.84, 1
    color: 1, 1, 1, 1
    font_name: app.font_name
    font_size: sp(15)
    size_hint_y: None
    height: dp(46)

<GhostButton@Button>:
    background_normal: ""
    background_color: 0.94, 0.94, 0.94, 1
    color: 0.2, 0.2, 0.2, 1
    font_name: app.font_name
    font_size: sp(14)
    size_hint_y: None
    height: dp(42)

<DangerButton@Button>:
    background_normal: ""
    background_color: 0.98, 0.35, 0.35, 1
    color: 1, 1, 1, 1
    font_name: app.font_name
    font_size: sp(14)
    size_hint_y: None
    height: dp(42)

<ThemedSpinner@Spinner>:
    background_normal: ""
    background_color: 0.97, 0.97, 0.97, 1
    color: 0.15, 0.15, 0.15, 1
    font_name: app.font_name
    font_size: sp(13)
    size_hint_y: None
    height: dp(42)

<ThemedInput@TextInput>:
    font_name: app.font_name
    font_size: sp(13)
    multiline: False
    size_hint_y: None
    height: dp(46)
    background_color: 1, 1, 1, 1
    foreground_color: 0.1, 0.1, 0.1, 1
    cursor_color: 0.0, 0.63, 0.84, 1
    hint_text_color: 0.6, 0.6, 0.6, 1
    padding: dp(10), dp(10)

<ThemedLabel@Label>:
    font_name: app.font_name
"""


# ==========================================================================
# 5. 通用小工具
# ==========================================================================

def themed_label(text="", **kw):
    kw.setdefault("font_name", FONT_NAME or "")
    return Label(text=text, **kw)


def tip(title, message, timeout=2.2):
    """轻量提示（Android 上更接近 toast，这里用自动关闭的 Popup）。"""
    try:
        content = BoxLayout(orientation="vertical", padding=dp(14),
                            spacing=dp(10))
        lbl = themed_label(text=message, font_size=sp(13),
                           halign="center", valign="middle")
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        content.add_widget(lbl)
        pop = Popup(title=title, content=content, size_hint=(0.86, None),
                    height=dp(150), auto_dismiss=True,
                    title_font=FONT_NAME or "", separator_color=(0, 0.63, 0.84, 1))
        pop.open()
        Clock.schedule_once(lambda dt: pop.dismiss(), timeout)
        return pop
    except Exception:
        return None


def confirm(title, message, on_yes, on_no=None):
    """确认对话框。"""
    content = BoxLayout(orientation="vertical", padding=dp(14), spacing=dp(10))
    lbl = themed_label(text=message, font_size=sp(13), halign="left",
                       valign="top", size_hint_y=1)
    lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
    content.add_widget(lbl)

    row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    pop = Popup(title=title, content=content, size_hint=(0.9, 0.42),
                auto_dismiss=False, title_font=FONT_NAME or "")

    def _no(*_):
        pop.dismiss()
        if on_no:
            on_no()

    def _yes(*_):
        pop.dismiss()
        on_yes()

    b_no = Button(text="取消", background_normal="",
                  background_color=(0.94, 0.94, 0.94, 1),
                  color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                  font_size=sp(14))
    b_no.bind(on_release=_no)
    b_yes = Button(text="确定", background_normal="",
                   background_color=(0.0, 0.63, 0.84, 1),
                   color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                   font_size=sp(14))
    b_yes.bind(on_release=_yes)
    row.add_widget(b_no)
    row.add_widget(b_yes)
    content.add_widget(row)
    pop.open()
    return pop


# ==========================================================================
# 6. 解析 Tab（对应桌面版主界面）
# ==========================================================================

# 桌面版 ui.py L19978 的 qn 映射，保持一致
QN_MAP = {"360P": 16, "480P": 32, "720P": 64,
          "1080P": 80, "1080P+": 112, "4K": 126, "8K": 127}
QN_LIST = ["自动（最高）", "8K", "4K", "1080P+", "1080P", "720P", "480P", "360P"]


class ParseTab(BoxLayout):
    """视频链接解析 → 信息展示 → 清晰度/集数/弹幕选择 → 下载。"""

    status_text = StringProperty("就绪")

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.orientation = "vertical"
        self.spacing = dp(6)
        self.padding = dp(10)
        # 用户勾选的集下标集合；None = 全部
        self.selected_ep_indexes = None
        self._build()

    # ------------------------------------------------------------ 构建
    def _build(self):
        scroll = ScrollView()
        root = BoxLayout(orientation="vertical", size_hint_y=None,
                         spacing=dp(10), padding=(0, dp(6)))
        root.bind(minimum_height=root.setter("height"))

        # ---------------- 链接输入卡片 ----------------
        card = BoxLayout(orientation="vertical", size_hint_y=None,
                         padding=dp(12), spacing=dp(8))
        card.bind(minimum_height=card.setter("height"))
        self._white_bg(card)

        card.add_widget(themed_label(text="视频链接", bold=True,
                                     font_size=sp(15), size_hint_y=None,
                                     height=dp(26), halign="left",
                                     valign="middle",
                                     color=(0.13, 0.13, 0.13, 1)))
        self.url_input = TextInput(
            hint_text="粘贴 BV号 / av号 / 番剧 / 合集 / 课堂链接",
            font_name=FONT_NAME or "", font_size=sp(13), multiline=False,
            size_hint_y=None, height=dp(46), padding=(dp(10), dp(10)),
            background_color=(0.97, 0.97, 0.97, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
            cursor_color=(0.0, 0.63, 0.84, 1))
        # 支持与桌面版一致的自动识别剪贴板链接
        self.url_input.bind(focus=self._on_url_focus)
        card.add_widget(self.url_input)

        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.parse_btn = Button(text="解析", background_normal="",
                                background_color=(0.0, 0.63, 0.84, 1),
                                color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                                font_size=sp(15))
        self.parse_btn.bind(on_release=self.toggle_parse)
        btn_row.add_widget(self.parse_btn)

        paste_btn = Button(text="粘贴", background_normal="",
                           background_color=(0.94, 0.94, 0.94, 1),
                           color=(0.2, 0.2, 0.2, 1),
                           font_name=FONT_NAME or "", font_size=sp(15))
        paste_btn.bind(on_release=self.on_paste)
        btn_row.add_widget(paste_btn)

        clear_btn = Button(text="清空", background_normal="",
                           background_color=(0.94, 0.94, 0.94, 1),
                           color=(0.2, 0.2, 0.2, 1),
                           font_name=FONT_NAME or "", font_size=sp(15))
        clear_btn.bind(on_release=lambda *_: self._clear_all())
        btn_row.add_widget(clear_btn)
        card.add_widget(btn_row)
        root.add_widget(card)

        # ---------------- 信息卡片 ----------------
        info = BoxLayout(orientation="vertical", size_hint_y=None,
                         padding=dp(12), spacing=dp(8))
        info.bind(minimum_height=info.setter("height"))
        self._white_bg(info)

        self.title_lbl = themed_label(
            text="尚未解析", bold=True, font_size=sp(15),
            color=(0.12, 0.12, 0.12, 1), size_hint_y=None, height=dp(52),
            halign="left", valign="top")
        self.title_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        info.add_widget(self.title_lbl)

        self.meta_lbl = themed_label(
            text="", font_size=sp(11.5), color=(0.45, 0.45, 0.45, 1),
            size_hint_y=None, height=dp(20), halign="left", valign="middle")
        self.meta_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        info.add_widget(self.meta_lbl)

        self.stat_lbl = themed_label(
            text="", font_size=sp(11.5), color=(0.35, 0.35, 0.35, 1),
            size_hint_y=None, height=dp(20), halign="left", valign="middle")
        self.stat_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        info.add_widget(self.stat_lbl)

        # 清晰度
        q_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        q_row.add_widget(themed_label(text="清晰度", font_size=sp(13),
                                      size_hint_x=0.28, halign="left",
                                      valign="middle",
                                      color=(0.25, 0.25, 0.25, 1)))
        self.quality_spinner = Spinner(
            text="自动（最高）", values=tuple(QN_LIST),
            font_name=FONT_NAME or "", font_size=sp(13),
            size_hint_x=0.72, background_normal="",
            background_color=(0.97, 0.97, 0.97, 1),
            color=(0.15, 0.15, 0.15, 1))
        q_row.add_widget(self.quality_spinner)
        info.add_widget(q_row)

        # 音质
        a_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        a_row.add_widget(themed_label(text="音质", font_size=sp(13),
                                      size_hint_x=0.28, halign="left",
                                      valign="middle",
                                      color=(0.25, 0.25, 0.25, 1)))
        self.audio_spinner = Spinner(
            text="自动（最高）",
            values=("自动（最高）", "Hi-Res", "杜比全景声", "192K", "132K", "64K"),
            font_name=FONT_NAME or "", font_size=sp(13),
            size_hint_x=0.72, background_normal="",
            background_color=(0.97, 0.97, 0.97, 1),
            color=(0.15, 0.15, 0.15, 1))
        a_row.add_widget(self.audio_spinner)
        info.add_widget(a_row)

        # 集数：既支持手填范围，也支持勾选具体集
        e_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        e_row.add_widget(themed_label(text="集数", font_size=sp(13),
                                      size_hint_x=0.2, halign="left",
                                      valign="middle",
                                      color=(0.25, 0.25, 0.25, 1)))
        self.ep_input = TextInput(
            hint_text="全部（可填 1-10 或 3）", font_name=FONT_NAME or "",
            font_size=sp(13), multiline=False, size_hint_x=0.42,
            size_hint_y=None, height=dp(42), padding=(dp(10), dp(8)),
            background_color=(0.97, 0.97, 0.97, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
            cursor_color=(0.0, 0.63, 0.84, 1))
        e_row.add_widget(self.ep_input)

        # 对应桌面版「选择集数」：打开带勾选框的列表
        self.ep_pick_btn = Button(
            text="选择集数", background_normal="",
            background_color=(0.0, 0.63, 0.84, 1), color=(1, 1, 1, 1),
            font_name=FONT_NAME or "", font_size=sp(12.5),
            size_hint_x=0.38, size_hint_y=None, height=dp(42))
        self.ep_pick_btn.bind(on_release=lambda *_: self.open_episode_picker())
        e_row.add_widget(self.ep_pick_btn)
        info.add_widget(e_row)

        # 已选集数摘要（对应桌面版「共 N 集」提示）
        self.ep_summary_lbl = themed_label(
            text="", font_size=sp(11), color=(0.45, 0.45, 0.45, 1),
            size_hint_y=None, height=dp(18), halign="left", valign="middle")
        self.ep_summary_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        info.add_widget(self.ep_summary_lbl)

        # 下载弹幕开关
        d_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        d_row.add_widget(themed_label(text="下载弹幕", font_size=sp(13),
                                      size_hint_x=0.28, halign="left",
                                      valign="middle",
                                      color=(0.25, 0.25, 0.25, 1)))
        self.danmaku_spinner = Spinner(
            text="否", values=("否", "是"),
            font_name=FONT_NAME or "", font_size=sp(13),
            size_hint_x=0.72, background_normal="",
            background_color=(0.97, 0.97, 0.97, 1),
            color=(0.15, 0.15, 0.15, 1))
        d_row.add_widget(self.danmaku_spinner)
        info.add_widget(d_row)

        # 保存目录
        p_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        p_row.add_widget(themed_label(text="保存到", font_size=sp(13),
                                      size_hint_x=0.28, halign="left",
                                      valign="middle",
                                      color=(0.25, 0.25, 0.25, 1)))
        self.path_lbl = themed_label(
            text=self.app.save_dir, font_size=sp(10.5),
            color=(0.45, 0.45, 0.45, 1), size_hint_x=0.72,
            halign="left", valign="middle", shorten=True,
            shorten_from="left")
        self.path_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        p_row.add_widget(self.path_lbl)
        info.add_widget(p_row)
        root.add_widget(info)

        # ---------------- 操作按钮 ----------------
        act = BoxLayout(orientation="vertical", size_hint_y=None,
                        spacing=dp(8))
        act.bind(minimum_height=act.setter("height"))

        self.dl_full_btn = Button(
            text="下载完整视频（画面+音频）", background_normal="",
            background_color=(0.0, 0.63, 0.84, 1), color=(1, 1, 1, 1),
            font_name=FONT_NAME or "", font_size=sp(15),
            size_hint_y=None, height=dp(50))
        self.dl_full_btn.bind(on_release=lambda *_: self.on_download(0))
        act.add_widget(self.dl_full_btn)

        row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        b_v = Button(text="仅下载画面", background_normal="",
                     background_color=(0.94, 0.94, 0.94, 1),
                     color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                     font_size=sp(14))
        b_v.bind(on_release=lambda *_: self.on_download(2))
        row2.add_widget(b_v)
        b_a = Button(text="仅下载音频", background_normal="",
                     background_color=(0.94, 0.94, 0.94, 1),
                     color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                     font_size=sp(14))
        b_a.bind(on_release=lambda *_: self.on_download(1))
        row2.add_widget(b_a)
        act.add_widget(row2)

        row3 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        b_cover = Button(text="保存封面", background_normal="",
                         background_color=(0.94, 0.94, 0.94, 1),
                         color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                         font_size=sp(14))
        b_cover.bind(on_release=self.on_save_cover)
        row3.add_widget(b_cover)
        b_dm = Button(text="单独下载弹幕", background_normal="",
                      background_color=(0.94, 0.94, 0.94, 1),
                      color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                      font_size=sp(14))
        b_dm.bind(on_release=self.on_download_danmaku)
        row3.add_widget(b_dm)
        act.add_widget(row3)

        row4 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        b_folder = Button(text="打开下载目录", background_normal="",
                          background_color=(0.94, 0.94, 0.94, 1),
                          color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                          font_size=sp(14))
        b_folder.bind(on_release=self.on_open_folder)
        row4.add_widget(b_folder)
        b_batch = Button(text="批量下载", background_normal="",
                         background_color=(0.94, 0.94, 0.94, 1),
                         color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                         font_size=sp(14))
        b_batch.bind(on_release=lambda *_: self.app.open_batch())
        row4.add_widget(b_batch)
        act.add_widget(row4)

        root.add_widget(act)

        # ---------------- 状态 ----------------
        self.status_lbl = themed_label(
            text="就绪", font_size=sp(11.5), color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None, height=dp(40), halign="left", valign="top")
        self.status_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(self.status_lbl)

        scroll.add_widget(root)
        self.add_widget(scroll)

    @staticmethod
    def _white_bg(widget):
        from kivy.graphics import Color, RoundedRectangle
        with widget.canvas.before:
            Color(1, 1, 1, 1)
            rect = RoundedRectangle(pos=widget.pos, size=widget.size,
                                    radius=[dp(10)])
        widget.bind(pos=lambda w, v: setattr(rect, "pos", v),
                    size=lambda w, v: setattr(rect, "size", v))

    # ------------------------------------------------------------ 状态
    def set_status(self, text):
        self.status_text = text
        if hasattr(self, "status_lbl"):
            self.status_lbl.text = text

    def _on_url_focus(self, _w, focused):
        if focused:
            self._maybe_paste_from_clipboard()

    def _maybe_paste_from_clipboard(self):
        """与桌面版一致的"剪贴板自动识别"（仅在输入框为空时）。"""
        try:
            if (self.url_input.text or "").strip():
                return
            from kivy.core.clipboard import Clipboard
            data = (Clipboard.paste() or "").strip()
            if not data or len(data) > 500:
                return
            if ("bilibili.com" in data or data.startswith("BV")
                    or data.startswith("av") or "b23.tv" in data):
                self.url_input.text = data
                self.set_status("已自动识别剪贴板链接")
        except Exception:
            pass

    def _clear_all(self):
        self.url_input.text = ""
        self.title_lbl.text = "尚未解析"
        self.meta_lbl.text = ""
        self.stat_lbl.text = ""
        self.quality_spinner.text = "自动（最高）"
        self.audio_spinner.text = "自动（最高）"
        self.ep_input.text = ""
        self.selected_ep_indexes = None
        if hasattr(self, "ep_summary_lbl"):
            self.ep_summary_lbl.text = ""
        self.set_status("已清空")
        self.app.last_info = None

    # ------------------------------------------------------------ 动作
    def on_paste(self, *_):
        try:
            from kivy.core.clipboard import Clipboard
            data = (Clipboard.paste() or "").strip()
            if data:
                self.url_input.text = data
                self.set_status("已从剪贴板粘贴")
            else:
                self.set_status("剪贴板为空")
        except Exception as exc:
            self.set_status("粘贴失败：%s" % exc)

    def on_parse(self, *_):
        url = (self.url_input.text or "").strip()
        if not url:
            self.set_status("请先输入视频链接")
            ti("提示", "请先输入视频链接")
            return

        self.set_status("解析中，请稍候…")
        self.title_lbl.text = "解析中…"
        self.meta_lbl.text = ""
        self.stat_lbl.text = ""
        self.parse_btn.disabled = True
        # 与桌面版一致：解析期间按钮变为「停止解析」
        self._set_parsing_ui(True)

        # 解析结果里的集数选择（桌面版用弹窗，这里同）
        ep_range = (self.ep_input.text or "").strip()

        def _worker():
            try:
                parser = self.app.get_parser()
                info = parser.parse_media(
                    *self._split_url(url),
                    cancel_check=lambda: self.app.parse_cancelled,
                    episode_range=ep_range or None,
                )
                Clock.schedule_once(lambda dt: self._show_result(info), 0)
            except Exception as exc:
                traceback.print_exc()
                msg = str(exc)[:200]
                Clock.schedule_once(
                    lambda dt: self._parse_failed(msg), 0)

        self.app.parse_cancelled = False
        threading.Thread(target=_worker, daemon=True).start()

    def _set_parsing_ui(self, parsing):
        """切换「解析 / 停止解析」按钮外观。"""
        try:
            if parsing:
                self.parse_btn.text = "停止解析"
                self.parse_btn.background_color = (0.98, 0.35, 0.35, 1)
            else:
                self.parse_btn.text = "解析"
                self.parse_btn.background_color = (0.0, 0.63, 0.84, 1)
                self.parse_btn.disabled = False
        except Exception:
            pass

    def on_stop_parse(self, *_):
        """对应桌面版的「停止解析」：请求取消并保留已解析到的部分结果。"""
        self.app.parse_cancelled = True
        self.set_status("正在停止解析…")
        self._set_parsing_ui(False)
        ti("提示", "已请求停止解析")

    def toggle_parse(self, *_):
        """解析按钮：空闲时解析，解析中则停止（对齐桌面版行为）。"""
        if self.parse_btn.text == "停止解析":
            self.on_stop_parse()
        else:
            self.on_parse()

    @staticmethod
    def _split_url(url):
        """把用户输入的链接拆成 (media_type, media_id)，与桌面版逻辑一致。"""
        u = url.strip()
        # 纯 BV / av 号
        if u.startswith("BV") and len(u) >= 12:
            return ("video", u)
        if u.startswith("av") and u[2:].isdigit():
            return ("video", u)
        if u.startswith("ep") and u[2:].isdigit():
            return ("bangumi", u)
        if u.startswith("ss") and u[2:].isdigit():
            return ("bangumi", u)
        if u.startswith("md") and u[2:].isdigit():
            return ("cheese", u)
        # 从链接里提取
        import re as _re
        m = _re.search(r"(BV[0-9A-Za-z]{10})", u)
        if m:
            return ("video", m.group(1))
        m = _re.search(r"/video/av(\d+)", u)
        if m:
            return ("video", "av" + m.group(1))
        m = _re.search(r"/bangumi/play/(ep\d+|ss\d+)", u)
        if m:
            return ("bangumi", m.group(1))
        m = _re.search(r"/cheese/play/(ep\d+|ss\d+)", u)
        if m:
            return ("cheese", m.group(1))
        m = _re.search(r"space\.bilibili\.com/(\d+)", u)
        if m:
            return ("space", m.group(1))
        m = _re.search(r"medialist/detail/ml(\d+)", u)
        if m:
            return ("favlist", m.group(1))
        m = _re.search(r"list/(\d+)", u)
        if m:
            return ("favlist", m.group(1))
        if "live.bilibili.com" in u:
            m = _re.search(r"/(\d+)", u)
            if m:
                return ("live", m.group(1))
        # 兜底：交给 parser 自己判断
        return ("video", u)

    def _parse_failed(self, msg):
        self._set_parsing_ui(False)
        self.title_lbl.text = "解析失败"
        self.set_status("解析失败：%s" % msg)
        ti("解析失败", msg)

    def _show_result(self, info):
        self._set_parsing_ui(False)
        if not info or not info.get("success", True):
            err = (info or {}).get("error") or "未获取到视频信息"
            self._parse_failed(err)
            return

        self.app.last_info = info
        title = info.get("title") or info.get("name") or "未知标题"
        self.title_lbl.text = title

        # 新视频 → 清空上一部片子的集数勾选
        self.selected_ep_indexes = None
        if hasattr(self, "ep_summary_lbl"):
            self.ep_summary_lbl.text = ""

        parts = []
        owner = info.get("owner")
        if owner:
            parts.append(str(owner))
        if info.get("duration"):
            parts.append("时长 %s" % info["duration"])
        if info.get("bvid"):
            parts.append(str(info["bvid"]))
        if info.get("is_bangumi"):
            parts.append("番剧")
        if info.get("is_cheese"):
            parts.append("课堂")
        self.meta_lbl.text = " · ".join(parts)

        eps = info.get("episodes") or []
        self.stat_lbl.text = "共 %d 个视频" % len(eps) if eps else ""
        # 与桌面版一致：集数多时引导点「选择集数」
        if hasattr(self, "ep_summary_lbl"):
            if len(eps) > 1:
                self.ep_summary_lbl.text = (
                    "共 %d 集，默认全部下载；点「选择集数」可只下其中几集"
                    % len(eps))
            else:
                self.ep_summary_lbl.text = ""

        # 用真实返回的清晰度填充下拉框（与桌面版一致）
        quals = ["自动（最高）"]
        try:
            for q in (info.get("qualities") or []):
                name = q.get("desc") if isinstance(q, dict) else str(q)
                if name and name not in quals:
                    quals.append(str(name))
        except Exception:
            pass
        if len(quals) == 1:
            quals = list(QN_LIST)
        self.quality_spinner.values = tuple(quals)
        self.quality_spinner.text = quals[0]

        self.set_status("解析完成，可开始下载")

    # ------------------------------------------------------------ 下载
    def _resolve_qn(self):
        """把界面上的清晰度文本换成 qn 数值。"""
        txt = (self.quality_spinner.text or "").strip()
        if txt in ("自动（最高）", ""):
            return 0                      # 0 = 交给引擎取最高
        for k, v in QN_MAP.items():
            if txt.startswith(k):
                return v
        import re as _re
        m = _re.search(r"(\d{3,4})", txt)
        return int(m.group(1)) if m else 0

    def _resolve_audio_quality(self):
        txt = (self.audio_spinner.text or "").strip()
        table = {"Hi-Res": 30251, "杜比全景声": 30250, "192K": 30280,
                 "132K": 30232, "64K": 30216}
        return table.get(txt, 30280)

    def on_download(self, content_type):
        """content_type: 0=有声视频 1=仅音频 2=仅视频（与桌面版一致）。"""
        info = self.app.last_info
        if not info:
            self.set_status("请先解析视频")
            ti("提示", "请先解析视频")
            return

        eps = info.get("episodes") or []
        if not eps:
            self.set_status("没有可下载的内容")
            ti("提示", "没有可下载的内容")
            return

        # 应用「选择集数」结果：只下载用户选中的集
        # 做法是给引擎一份裁剪过的 episodes 拷贝，
        # 其余字段（标题/封面等）保持原样，与桌面版一致
        picked = self.selected_ep_indexes
        if picked is not None:
            selected = [ep for i, ep in enumerate(eps) if i in picked]
            if not selected:
                self.set_status("没有选中任何集数")
                ti("提示", "没有选中任何集数，请重新选择")
                return
            info = dict(info)
            info["episodes"] = selected
            info["_selected_from"] = len(eps)

        qn = self._resolve_qn()
        want_danmaku = (self.danmaku_spinner.text == "是")
        self.app.start_download(info, qn=qn, content_type=content_type,
                                want_danmaku=want_danmaku,
                                audio_quality=self._resolve_audio_quality())
        n = len(info.get("episodes") or [])
        self.set_status("已加入下载队列（%d 集），可在「任务」页查看进度" % n)

    def on_save_cover(self, *_):
        info = self.app.last_info
        if not info:
            ti("提示", "请先解析视频")
            return
        pic = info.get("pic") or ""
        if not pic:
            ti("提示", "该视频没有封面")
            return
        self.set_status("正在下载封面…")

        def _work():
            try:
                import requests
                r = requests.get(pic, timeout=20,
                                 headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                title = info.get("title") or "cover"
                safe = "".join(c for c in title
                               if c not in '\\/:*?"<>|').strip() or "cover"
                path = os.path.join(self.app.save_dir, safe + ".jpg")
                with open(path, "wb") as fh:
                    fh.write(r.content)
                Clock.schedule_once(
                    lambda dt: (self.set_status("封面已保存：%s" % path),
                                ti("成功", "封面已保存到\n%s" % path)), 0)
            except Exception as exc:
                Clock.schedule_once(
                    lambda dt: (self.set_status("封面下载失败：%s" % exc),
                                ti("失败", "封面下载失败：%s" % str(exc)[:150])), 0)

        threading.Thread(target=_work, daemon=True).start()

    def on_download_danmaku(self, *_):
        info = self.app.last_info
        if not info:
            ti("提示", "请先解析视频")
            return
        eps = info.get("episodes") or []
        if not eps:
            ti("提示", "该视频没有弹幕")
            return
        self.set_status("正在下载弹幕…")
        self.app.download_danmaku_only(info)
        ti("提示", "已开始单独下载弹幕")

    def on_open_folder(self, *_):
        self.app.open_download_dir()

    # ------------------------------------------------------------ 集数选择
    def open_episode_picker(self):
        """对应桌面版的「选择集数」：勾选具体某几集下载。

        桌面版是带复选框的列表；这里用同样的交互（Kivy 的 CheckBox），
        并在确认后把结果写回 self.selected_ep_indexes。
        """
        info = self.app.last_info
        if not info:
            ti("提示", "请先解析视频")
            return
        eps = info.get("episodes") or []
        if not eps:
            ti("提示", "该视频没有分集，无需选择")
            return
        if len(eps) == 1:
            ti("提示", "该视频只有 1 个视频，无需选择")
            return
        EpisodePicker(self.app, info, self).open()

    def set_episode_selection(self, indexes):
        """把勾选结果写回界面。indexes 为集下标集合；None 表示全部。"""
        self.selected_ep_indexes = indexes
        if indexes is None:
            self.ep_input.text = ""
            self.ep_summary_lbl.text = ""
            return
        # 转成 1 基集号文本，便于用户看到选了什么
        nums = sorted(i + 1 for i in indexes)
        if len(nums) <= 12:
            text = ",".join(str(n) for n in nums)
        else:
            text = "%d 集（%d-%d …）" % (len(nums), nums[0], nums[-1])
        self.ep_summary_lbl.text = "已选 %d 集：%s" % (len(nums), text)


# ==========================================================================
# 7. 任务 Tab
# ==========================================================================

class TaskRow(BoxLayout):
    def __init__(self, title, content_type=0, **kw):
        super().__init__(**kw)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(96)
        self.padding = dp(10)
        self.spacing = dp(4)
        from kivy.graphics import Color, RoundedRectangle
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._rect = RoundedRectangle(pos=self.pos, size=self.size,
                                          radius=[dp(8)])
        self.bind(pos=lambda w, v: setattr(self._rect, "pos", v),
                  size=lambda w, v: setattr(self._rect, "size", v))

        self.title_lbl = themed_label(
            text=title or "未命名", bold=True, font_size=sp(13),
            color=(0.12, 0.12, 0.12, 1), size_hint_y=None, height=dp(22),
            halign="left", valign="middle", shorten=True,
            shorten_from="right")
        self.title_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(self.title_lbl)

        self.bar = ProgressBar(max=100, value=0, size_hint_y=None,
                               height=dp(8))
        self.add_widget(self.bar)

        self.stat_lbl = themed_label(
            text="等待中", font_size=sp(10.5), color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None, height=dp(18), halign="left", valign="middle",
            shorten=True, shorten_from="right")
        self.stat_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(self.stat_lbl)

        btns = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(6))
        self.pause_btn = Button(text="暂停", background_normal="",
                                background_color=(0.94, 0.94, 0.94, 1),
                                color=(0.2, 0.2, 0.2, 1),
                                font_name=FONT_NAME or "", font_size=sp(12))
        btns.add_widget(self.pause_btn)
        self.cancel_btn = Button(text="取消", background_normal="",
                                 background_color=(0.98, 0.35, 0.35, 1),
                                 color=(1, 1, 1, 1),
                                 font_name=FONT_NAME or "", font_size=sp(12))
        btns.add_widget(self.cancel_btn)
        self.add_widget(btns)

    def update_progress(self, pct, text=""):
        try:
            self.bar.value = max(0, min(100, float(pct or 0)))
        except Exception:
            pass
        if text:
            self.stat_lbl.text = text


class TaskTab(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(8)

        head = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        head.add_widget(themed_label(text="下载任务", bold=True,
                                     font_size=sp(16),
                                     color=(0.13, 0.13, 0.13, 1),
                                     halign="left", valign="middle"))
        clear_btn = Button(text="清除已完成", background_normal="",
                           background_color=(0.94, 0.94, 0.94, 1),
                           color=(0.2, 0.2, 0.2, 1),
                           font_name=FONT_NAME or "", font_size=sp(12),
                           size_hint_x=None, width=dp(110))
        clear_btn.bind(on_release=self.on_clear_completed)
        head.add_widget(clear_btn)
        self.add_widget(head)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(8), padding=(0, dp(4)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        self.add_widget(self.scroll)

        self.empty_lbl = themed_label(
            text="暂无任务\n\n在「解析」页解析视频后即可开始下载",
            font_size=sp(13), color=(0.55, 0.55, 0.55, 1),
            halign="center", valign="middle", size_hint_y=None,
            height=dp(120))
        self.empty_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.list_box.add_widget(self.empty_lbl)
        self.rows = {}

    def add_task(self, task_id, title, content_type=0):
        if self.empty_lbl.parent:
            self.list_box.remove_widget(self.empty_lbl)
        # 同一个任务不重复添加
        if task_id in self.rows:
            return self.rows[task_id]
        row = TaskRow(title, content_type)
        row.pause_btn.bind(on_release=lambda *_: self.app.toggle_pause(task_id))
        row.cancel_btn.bind(on_release=lambda *_: self.app.cancel_task(task_id))
        self.rows[task_id] = row
        self.list_box.add_widget(row)
        return row

    def update_task(self, task_id, pct, text=""):
        row = self.rows.get(task_id)
        if row:
            row.update_progress(pct, text)

    def set_paused(self, task_id, paused):
        row = self.rows.get(task_id)
        if row:
            row.pause_btn.text = "继续" if paused else "暂停"

    def remove_task(self, task_id):
        row = self.rows.pop(task_id, None)
        if row is not None and row.parent:
            self.list_box.remove_widget(row)
        if not self.rows and not self.empty_lbl.parent:
            self.list_box.add_widget(self.empty_lbl)

    def on_clear_completed(self, *_):
        try:
            for tid in list(self.rows.keys()):
                row = self.rows[tid]
                if row.bar.value >= 100:
                    self.remove_task(tid)
            ti("提示", "已清除完成的任务")
        except Exception as exc:
            ti("失败", str(exc)[:150])


# ==========================================================================
# 8. 历史 Tab
# ==========================================================================

class HistoryTab(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(8)

        head = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        self.search_input = TextInput(
            hint_text="搜索标题 / BV号", font_name=FONT_NAME or "",
            font_size=sp(13), multiline=False, size_hint_y=None,
            height=dp(42), padding=(dp(10), dp(8)),
            background_color=(1, 1, 1, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
            cursor_color=(0.0, 0.63, 0.84, 1))
        head.add_widget(self.search_input)
        s_btn = Button(text="搜索", background_normal="",
                       background_color=(0.0, 0.63, 0.84, 1),
                       color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                       font_size=sp(13), size_hint_x=None, width=dp(72))
        s_btn.bind(on_release=lambda *_: self.reload())
        head.add_widget(s_btn)
        self.add_widget(head)

        filter_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
        self.filter = "全部"
        for name in ("全部", "成功", "失败"):
            b = Button(text=name, background_normal="",
                       background_color=(0.94, 0.94, 0.94, 1),
                       color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                       font_size=sp(12))
            b.bind(on_release=lambda w, n=name: self._set_filter(n))
            filter_row.add_widget(b)
        c_btn = Button(text="清空历史", background_normal="",
                       background_color=(0.98, 0.35, 0.35, 1),
                       color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                       font_size=sp(12))
        c_btn.bind(on_release=self.on_clear)
        filter_row.add_widget(c_btn)
        self.add_widget(filter_row)

        self.scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(6), padding=(0, dp(4)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.scroll.add_widget(self.list_box)
        self.add_widget(self.scroll)
        self.reload()

    def _set_filter(self, name):
        self.filter = name
        self.reload()

    def on_clear(self, *_):
        def _do():
            try:
                self.app.history.clear_records()
                self.reload()
                ti("提示", "历史已清空")
            except Exception as exc:
                ti("失败", str(exc)[:150])
        confirm("清空历史", "确定要清空全部下载历史吗？", _do)

    def reload(self):
        try:
            self.list_box.clear_widgets()
        except Exception:
            return
        try:
            kw = (self.search_input.text or "").strip()
            status = "" if self.filter == "全部" else self.filter
            # 注意：get_records() 返回 (records, total) 元组，
            # 不是列表 —— 这里必须解包
            result = self.app.history.get_records(
                keyword=kw, status_filter=status, limit=200)
            if isinstance(result, tuple):
                records = result[0] or []
            else:
                records = result or []
        except Exception as exc:
            self.list_box.add_widget(themed_label(
                text="读取历史失败：%s" % str(exc)[:120],
                font_size=sp(12), color=(0.8, 0.3, 0.3, 1),
                size_hint_y=None, height=dp(60)))
            return

        if not records:
            self.list_box.add_widget(themed_label(
                text="暂无历史记录", font_size=sp(13),
                color=(0.55, 0.55, 0.55, 1), halign="center",
                valign="middle", size_hint_y=None, height=dp(100)))
            return

        for rec in records:
            self.list_box.add_widget(self._make_row(rec))

    def _make_row(self, rec):
        box = BoxLayout(orientation="vertical", size_hint_y=None,
                        height=dp(92), padding=dp(10), spacing=dp(2))
        from kivy.graphics import Color, RoundedRectangle
        with box.canvas.before:
            Color(1, 1, 1, 1)
            rect = RoundedRectangle(pos=box.pos, size=box.size,
                                    radius=[dp(8)])
        box.bind(pos=lambda w, v: setattr(rect, "pos", v),
                 size=lambda w, v: setattr(rect, "size", v))

        title = rec.get("title") or rec.get("bvid") or "未知标题"
        box.add_widget(themed_label(
            text=title, bold=True, font_size=sp(13),
            color=(0.12, 0.12, 0.12, 1), size_hint_y=None, height=dp(22),
            halign="left", valign="middle", shorten=True,
            shorten_from="right"))

        bits = []
        if rec.get("quality"):
            bits.append(str(rec["quality"]))
        if rec.get("status"):
            bits.append(str(rec["status"]))
        if rec.get("time") or rec.get("created_at"):
            bits.append(str(rec.get("time") or rec.get("created_at"))[:19])
        box.add_widget(themed_label(
            text=" · ".join(bits), font_size=sp(10.5),
            color=(0.5, 0.5, 0.5, 1), size_hint_y=None, height=dp(18),
            halign="left", valign="middle", shorten=True,
            shorten_from="right"))

        path = rec.get("file_path") or rec.get("save_path") or ""
        box.add_widget(themed_label(
            text=path, font_size=sp(10), color=(0.6, 0.6, 0.6, 1),
            size_hint_y=None, height=dp(18), halign="left", valign="middle",
            shorten=True, shorten_from="left"))
        return box


# ==========================================================================
# 9. 设置 Tab
# ==========================================================================

class SettingsTab(BoxLayout):
    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(8)

        scroll = ScrollView()
        root = BoxLayout(orientation="vertical", size_hint_y=None,
                         spacing=dp(10), padding=(0, dp(6)))
        root.bind(minimum_height=root.setter("height"))

        # ---- 账号 ----
        acc = self._card()
        acc.add_widget(themed_label(
            text="账号", bold=True, font_size=sp(15),
            color=(0.13, 0.13, 0.13, 1), size_hint_y=None, height=dp(26),
            halign="left", valign="middle"))
        self.user_lbl = themed_label(
            text="未登录", font_size=sp(12.5), color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None, height=dp(24), halign="left", valign="middle")
        acc.add_widget(self.user_lbl)
        row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        self.login_btn = Button(text="扫码登录", background_normal="",
                                background_color=(0.0, 0.63, 0.84, 1),
                                color=(1, 1, 1, 1),
                                font_name=FONT_NAME or "", font_size=sp(14))
        self.login_btn.bind(on_release=lambda *_: self.app.open_login())
        row.add_widget(self.login_btn)
        self.logout_btn = Button(text="退出登录", background_normal="",
                                 background_color=(0.94, 0.94, 0.94, 1),
                                 color=(0.2, 0.2, 0.2, 1),
                                 font_name=FONT_NAME or "", font_size=sp(14))
        self.logout_btn.bind(on_release=lambda *_: self.app.logout())
        row.add_widget(self.logout_btn)
        acc.add_widget(row)
        root.add_widget(acc)

        # ---- 下载设置 ----
        dl = self._card()
        dl.add_widget(themed_label(
            text="下载设置", bold=True, font_size=sp(15),
            color=(0.13, 0.13, 0.13, 1), size_hint_y=None, height=dp(26),
            halign="left", valign="middle"))

        dl.add_widget(themed_label(
            text="默认清晰度", font_size=sp(12.5), size_hint_y=None,
            height=dp(22), halign="left", valign="middle",
            color=(0.25, 0.25, 0.25, 1)))
        self.quality_spinner = Spinner(
            text=self.app.settings.get("default_quality", "自动（最高）"),
            values=tuple(QN_LIST), font_name=FONT_NAME or "",
            font_size=sp(13), size_hint_y=None, height=dp(42),
            background_normal="", background_color=(0.97, 0.97, 0.97, 1),
            color=(0.15, 0.15, 0.15, 1))
        self.quality_spinner.bind(text=self._on_quality)
        dl.add_widget(self.quality_spinner)

        dl.add_widget(themed_label(
            text="默认保存目录", font_size=sp(12.5), size_hint_y=None,
            height=dp(22), halign="left", valign="middle",
            color=(0.25, 0.25, 0.25, 1)))
        self.path_lbl = themed_label(
            text=self.app.save_dir, font_size=sp(10.5),
            color=(0.45, 0.45, 0.45, 1), size_hint_y=None, height=dp(40),
            halign="left", valign="top")
        self.path_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        dl.add_widget(self.path_lbl)

        rowp = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        b1 = Button(text="选择目录", background_normal="",
                    background_color=(0.94, 0.94, 0.94, 1),
                    color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                    font_size=sp(13))
        b1.bind(on_release=lambda *_: self.app.choose_save_dir())
        rowp.add_widget(b1)
        b2 = Button(text="恢复默认", background_normal="",
                    background_color=(0.94, 0.94, 0.94, 1),
                    color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                    font_size=sp(13))
        b2.bind(on_release=lambda *_: self.app.reset_save_dir())
        rowp.add_widget(b2)
        dl.add_widget(rowp)
        root.add_widget(dl)

        # ---- 工具 ----
        tl = self._card()
        tl.add_widget(themed_label(
            text="外部工具", bold=True, font_size=sp(15),
            color=(0.13, 0.13, 0.13, 1), size_hint_y=None, height=dp(26),
            halign="left", valign="middle"))
        self.tool_lbl = themed_label(
            text="检查中…", font_size=sp(11.5), color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None, height=dp(60), halign="left", valign="top")
        self.tool_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        tl.add_widget(self.tool_lbl)
        rowt = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(8))
        bt = Button(text="检查工具", background_normal="",
                    background_color=(0.94, 0.94, 0.94, 1),
                    color=(0.2, 0.2, 0.2, 1), font_name=FONT_NAME or "",
                    font_size=sp(13))
        bt.bind(on_release=lambda *_: self.refresh_tools())
        rowt.add_widget(bt)
        bd = Button(text="下载工具", background_normal="",
                    background_color=(0.0, 0.63, 0.84, 1),
                    color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                    font_size=sp(13))
        bd.bind(on_release=lambda *_: self.app.download_tools())
        rowt.add_widget(bd)
        tl.add_widget(rowt)
        root.add_widget(tl)

        # ---- 设备信息 ----
        dv = self._card()
        dv.add_widget(themed_label(
            text="设备信息", bold=True, font_size=sp(15),
            color=(0.13, 0.13, 0.13, 1), size_hint_y=None, height=dp(26),
            halign="left", valign="middle"))
        dv.add_widget(themed_label(
            text=("CPU 核心：%s\n可用内存：%s GB\n建议并发：%s\n同时任务：%s"
                  % (PROFILE.get("cpu", "?"), PROFILE.get("mem_gb", "?"),
                     PROFILE.get("concurrency"), PROFILE.get("max_tasks"))),
            font_size=sp(11.5), color=(0.35, 0.35, 0.35, 1),
            size_hint_y=None, height=dp(88), halign="left", valign="top"))
        root.add_widget(dv)

        # ---- 关于 ----
        ab = self._card()
        ab.add_widget(themed_label(
            text="关于", bold=True, font_size=sp(15),
            color=(0.13, 0.13, 0.13, 1), size_hint_y=None, height=dp(26),
            halign="left", valign="middle"))
        ab.add_widget(themed_label(
            text=("B站视频解析工具 v%s（Android 版）\n"
                  "解析与下载内核与桌面版完全同源。\n"
                  "界面为触屏重写，功能与桌面版一致。"
                  % self.app.app_version),
            font_size=sp(11.5), color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None, height=dp(80), halign="left", valign="top"))
        root.add_widget(ab)

        scroll.add_widget(root)
        self.add_widget(scroll)
        Clock.schedule_once(lambda dt: self.refresh_tools(), 0.6)
        Clock.schedule_once(lambda dt: self.refresh_user(), 0.8)

    @staticmethod
    def _card():
        box = BoxLayout(orientation="vertical", size_hint_y=None,
                        padding=dp(12), spacing=dp(8))
        box.bind(minimum_height=box.setter("height"))
        from kivy.graphics import Color, RoundedRectangle
        with box.canvas.before:
            Color(1, 1, 1, 1)
            rect = RoundedRectangle(pos=box.pos, size=box.size,
                                    radius=[dp(10)])
        box.bind(pos=lambda w, v: setattr(rect, "pos", v),
                 size=lambda w, v: setattr(rect, "size", v))
        return box

    def _on_quality(self, _w, value):
        self.app.settings["default_quality"] = value
        self.app.persist_settings()

    def refresh_tools(self):
        def _work():
            try:
                from tool_manager import ToolManager
                tm = ToolManager()
                ffmpeg = tm.get_tool_path("ffmpeg") if hasattr(tm, "get_tool_path") else None
                mp4d = tm.get_tool_path("mp4decrypt") if hasattr(tm, "get_tool_path") else None
                lines = []
                lines.append("ffmpeg：%s" % ("已就绪" if ffmpeg else "未安装"))
                if ffmpeg:
                    lines.append("  %s" % ffmpeg)
                lines.append("mp4decrypt：%s" % ("已就绪" if mp4d else "未安装"))
                if mp4d:
                    lines.append("  %s" % mp4d)
                if not ffmpeg or not mp4d:
                    lines.append("")
                    lines.append("提示：点「下载工具」自动获取，")
                    lines.append("否则无法合并音视频 / 解密 DRM。")
                text = "\n".join(lines)
            except Exception as exc:
                text = "检查失败：%s" % str(exc)[:150]
            Clock.schedule_once(lambda dt: setattr(self.tool_lbl, "text", text), 0)

        threading.Thread(target=_work, daemon=True).start()

    def refresh_user(self):
        try:
            name = self.app.user_name
            self.user_lbl.text = ("已登录：%s" % name) if name else "未登录"
        except Exception:
            pass


# ==========================================================================
# 9.5 集数选择弹窗（对应桌面版「选择集数」）
# ==========================================================================

class EpisodeRow(BoxLayout):
    """一行：勾选框 + 集标题。"""

    def __init__(self, index, title, checked, on_toggle, **kw):
        super().__init__(**kw)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(46)
        self.spacing = dp(6)
        self.index = index

        self.cb = CheckBox(active=checked, size_hint_x=None, width=dp(42),
                           color=(0.0, 0.63, 0.84, 1))
        self.cb.bind(active=lambda w, v: on_toggle(index, v))
        self.add_widget(self.cb)

        lbl = themed_label(
            text=title, font_size=sp(12.5), color=(0.15, 0.15, 0.15, 1),
            halign="left", valign="middle", shorten=True, shorten_from="right")
        lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        self.add_widget(lbl)

    def set_checked(self, value):
        # 避免回调风暴：只在真的变化时改
        if self.cb.active != value:
            self.cb.active = value


class EpisodePicker(Popup):
    """勾选集数。功能对齐桌面版的「选择集数」对话框。

    - 全选 / 取消全选 / 反选
    - 搜索（集数多时非常有用，桌面版同样支持筛选）
    - 逐项勾选
    """

    def __init__(self, app, info, parse_tab, **kw):
        self.app = app
        self.info = info
        self.parse_tab = parse_tab
        self.episodes = list(info.get("episodes") or [])
        self.rows = []
        self.checked = set()
        # 初始沿用上次选择；没有则默认全选
        prev = parse_tab.selected_ep_indexes
        if prev is None:
            self.checked = set(range(len(self.episodes)))
        else:
            self.checked = set(prev)

        content = BoxLayout(orientation="vertical", padding=dp(12),
                            spacing=dp(8))

        # ---- 顶部：计数 + 搜索 ----
        self.count_lbl = themed_label(
            text="", font_size=sp(12), color=(0.35, 0.35, 0.35, 1),
            size_hint_y=None, height=dp(22), halign="left", valign="middle")
        self.count_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        content.add_widget(self.count_lbl)

        self.search_input = TextInput(
            hint_text="搜索集数标题…", font_name=FONT_NAME or "",
            font_size=sp(12.5), multiline=False, size_hint_y=None,
            height=dp(40), padding=(dp(10), dp(8)),
            background_color=(0.97, 0.97, 0.97, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
            cursor_color=(0.0, 0.63, 0.84, 1))
        self.search_input.bind(text=lambda w, v: self._apply_filter(v))
        content.add_widget(self.search_input)

        # ---- 列表 ----
        scroll = ScrollView()
        self.list_box = BoxLayout(orientation="vertical", size_hint_y=None,
                                  spacing=dp(2))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        content.add_widget(scroll)

        # ---- 快捷操作 ----
        quick = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(6))
        for text, fn in (("全选", lambda *_: self._set_all(True)),
                         ("取消全选", lambda *_: self._set_all(False)),
                         ("反选", lambda *_: self._invert())):
            b = Button(text=text, background_normal="",
                       background_color=(0.94, 0.94, 0.94, 1),
                       color=(0.2, 0.2, 0.2, 1),
                       font_name=FONT_NAME or "", font_size=sp(12))
            b.bind(on_release=fn)
            quick.add_widget(b)
        content.add_widget(quick)

        # ---- 确认 / 取消 ----
        bottom = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        b_cancel = Button(text="取消", background_normal="",
                          background_color=(0.94, 0.94, 0.94, 1),
                          color=(0.2, 0.2, 0.2, 1),
                          font_name=FONT_NAME or "", font_size=sp(14))
        b_cancel.bind(on_release=lambda *_: self.dismiss())
        bottom.add_widget(b_cancel)

        b_all = Button(text="下载全部", background_normal="",
                       background_color=(0.0, 0.63, 0.84, 1),
                       color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                       font_size=sp(14))
        b_all.bind(on_release=lambda *_: self._confirm(None))
        bottom.add_widget(b_all)

        b_ok = Button(text="确认选择", background_normal="",
                      background_color=(0.0, 0.63, 0.84, 1),
                      color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                      font_size=sp(14))
        b_ok.bind(on_release=lambda *_: self._confirm(set(self.checked)))
        bottom.add_widget(b_ok)
        content.add_widget(bottom)

        super().__init__(title="选择集数", content=content,
                         size_hint=(0.94, 0.85), auto_dismiss=False,
                         title_font=FONT_NAME or "",
                         separator_color=(0, 0.63, 0.84, 1))
        self._build_rows()
        self._update_count()

    # ------------------------------------------------------------ 内部
    def _ep_title(self, i, ep):
        """尽量还原桌面版取标题的逻辑。"""
        return (ep.get("title") or ep.get("ep_title")
                or ("第%s集" % ep.get("page", i + 1)))

    def _build_rows(self):
        self.list_box.clear_widgets()
        self.rows = []
        for i, ep in enumerate(self.episodes):
            title = "%d. %s" % (i + 1, self._ep_title(i, ep))
            row = EpisodeRow(i, title, i in self.checked, self._on_toggle)
            self.rows.append(row)
            self.list_box.add_widget(row)

    def _on_toggle(self, index, active):
        if active:
            self.checked.add(index)
        else:
            self.checked.discard(index)
        self._update_count()

    def _set_all(self, value):
        self.checked = set(range(len(self.episodes))) if value else set()
        for row in self.rows:
            row.set_checked(value)
        self._update_count()

    def _invert(self):
        self.checked = set(range(len(self.episodes))) - self.checked
        for row in self.rows:
            row.set_checked(row.index in self.checked)
        self._update_count()

    def _apply_filter(self, keyword):
        """按标题过滤显示（不改变勾选状态）。"""
        kw = (keyword or "").strip().lower()
        for row in self.rows:
            ep = self.episodes[row.index]
            title = self._ep_title(row.index, ep)
            hit = (not kw) or (kw in str(title).lower()) \
                or (kw in str(row.index + 1))
            row.height = dp(46) if hit else 0
            row.opacity = 1 if hit else 0
            row.disabled = not hit

    def _update_count(self):
        self.count_lbl.text = "共 %d 集，已选 %d 集" % (
            len(self.episodes), len(self.checked))

    def _confirm(self, indexes):
        if indexes is not None and not indexes:
            ti("提示", "请至少选择一集")
            return
        self.parse_tab.set_episode_selection(indexes)
        self.dismiss()
        if indexes is None:
            ti("提示", "将下载全部 %d 集" % len(self.episodes))
        else:
            ti("提示", "已选择 %d 集" % len(indexes))


# ==========================================================================
# 10. 扫码登录弹窗
# ==========================================================================

class LoginPopup(Popup):
    """扫码登录弹窗。

    旧版本会在 Android 上崩溃：它直接导入 qrcode，而 APK 里既没有 qrcode
    也没有 Pillow，且异常发生在渲染路径上，会直接把界面带崩。
    现在改用自带的 qrgen（纯 Python 直接写 PNG），并且每一步都有兜底：
    任何异常都只会显示提示文字，不会让界面挂掉。
    """

    def __init__(self, app, **kw):
        content = BoxLayout(orientation="vertical", padding=dp(16),
                            spacing=dp(12))

        # ---- 状态提示 ----
        self.status_lbl = themed_label(
            text="正在获取二维码…", font_size=sp(14),
            color=(0.25, 0.25, 0.25, 1), size_hint_y=None, height=dp(34),
            halign="center", valign="middle")
        self.status_lbl.bind(size=lambda w, s: setattr(w, "text_size", s))
        content.add_widget(self.status_lbl)

        # ---- 二维码区域（白底圆角，扫码更清晰）----
        qr_wrap = BoxLayout(size_hint_y=1, padding=dp(10))
        with qr_wrap.canvas.before:
            Color(1, 1, 1, 1)
            self._qr_bg = RoundedRectangle(radius=[dp(14)])
        qr_wrap.bind(pos=self._sync_qr_bg, size=self._sync_qr_bg)

        self.qr_img = Image(size_hint_y=1, allow_stretch=True,
                            keep_ratio=True)
        qr_wrap.add_widget(self.qr_img)
        content.add_widget(qr_wrap)

        # ---- 底部按钮：刷新 / 关闭 ----
        bottom = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        self.refresh_btn = Button(
            text="刷新二维码", background_normal="",
            background_color=(0.94, 0.94, 0.94, 1),
            color=(0.2, 0.2, 0.2, 1),
            font_name=FONT_NAME or "", font_size=sp(14))
        self.refresh_btn.bind(on_release=lambda *_: self.refresh())
        bottom.add_widget(self.refresh_btn)

        close_btn = Button(text="关闭", background_normal="",
                           background_color=(0.0, 0.63, 0.84, 1),
                           color=(1, 1, 1, 1),
                           font_name=FONT_NAME or "", font_size=sp(14))
        close_btn.bind(on_release=lambda *_: self.dismiss())
        bottom.add_widget(close_btn)
        content.add_widget(bottom)

        super().__init__(title="扫码登录", content=content,
                         size_hint=(0.92, 0.86), auto_dismiss=False,
                         title_font=FONT_NAME or "",
                         separator_color=(0, 0.63, 0.84, 1))
        self.app = app
        self._qrcode_key = None
        self._poll_ev = None
        self._alive = True
        self.bind(on_dismiss=self._on_close)

    def _sync_qr_bg(self, widget, _value):
        self._qr_bg.pos = widget.pos
        self._qr_bg.size = widget.size

    def start(self):
        self.refresh()

    def refresh(self):
        """（重新）获取并渲染二维码。"""
        if not self._alive:
            return
        self._stop_poll()
        self._qrcode_key = None
        self._set_status("正在获取二维码…")

        def _work():
            try:
                parser = self.app.get_parser()
                data = parser.get_qrcode()
            except Exception as exc:
                traceback.print_exc()
                msg = str(exc)[:150]
                Clock.schedule_once(
                    lambda dt: self._set_status("获取二维码失败：%s" % msg), 0)
                return
            Clock.schedule_once(lambda dt: self._show_qr(data), 0)

        threading.Thread(target=_work, daemon=True).start()

    def _show_qr(self, data):
        if not self._alive:
            return
        if not data:
            self._set_status("获取二维码失败，请点「刷新二维码」")
            return
        self._qrcode_key = data.get("qrcode_key")
        url = data.get("url") or ""
        img_path = self._render_qr(url)
        if img_path:
            try:
                self.qr_img.source = img_path
                self.qr_img.reload()
            except Exception:
                traceback.print_exc()
            self._set_status("请用 B站 App 扫码登录")
        else:
            # 不让用户卡死：至少把链接打出来，便于排查
            self._set_status("二维码生成失败，请点「刷新二维码」重试")
            if url:
                print("[login] qr url:", url)
            return
        # 开始轮询扫码状态
        self._poll_ev = Clock.schedule_interval(self._poll, 2.0)

    def _render_qr(self, url):
        """用自带 qrgen 生成二维码 PNG（不依赖 qrcode / Pillow）。

        Android 的 APK 里没有这两个库，所以必须走自带实现——
        这是之前扫码闪退的根因（`import qrcode` 直接抛 ImportError）。
        qrgen 的输出已与参考库逐格比对一致，并用真实解码器验证可扫。
        """
        if not url:
            return None
        try:
            import qrgen
            out = os.path.join(self.app.user_data_dir, "login_qr.png")
            qrgen.make_png(url, out, scale=8, border=3)
            return out if os.path.isfile(out) else None
        except Exception:
            traceback.print_exc()
            return None

    def _poll(self, _dt):
        if not self._alive or not self._qrcode_key:
            return False

        def _work():
            try:
                parser = self.app.get_parser()
                res = parser.poll_login_status(self._qrcode_key) or {}
            except Exception:
                # 网络抖动就忽略，下一轮再试，不要因此中断
                return
            Clock.schedule_once(lambda dt: self._on_poll(res), 0)

        threading.Thread(target=_work, daemon=True).start()
        return True

    def _on_poll(self, res):
        if not self._alive:
            return
        if res.get("success"):
            self._stop_poll()
            self._set_status("登录成功！")
            try:
                self.app.on_login_success(res.get("user_info") or {})
            except Exception:
                traceback.print_exc()
            Clock.schedule_once(lambda dt: self.dismiss(), 1.0)
            return

        status = res.get("status") or ""
        code = res.get("code")
        if status:
            self._set_status(status)
        # 86038 = 二维码已失效：自动换一张，省得用户点刷新
        if code == 86038:
            self._stop_poll()
            self._set_status("二维码已失效，正在刷新…")
            Clock.schedule_once(lambda dt: self.refresh(), 1.0)

    def _set_status(self, text):
        try:
            self.status_lbl.text = text
        except Exception:
            pass

    def _stop_poll(self):
        if self._poll_ev is not None:
            try:
                self._poll_ev.cancel()
            except Exception:
                pass
            self._poll_ev = None

    def _on_close(self, *_):
        self._alive = False
        self._stop_poll()


# ==========================================================================
# 11. 批量下载弹窗
# ==========================================================================

class BatchPopup(Popup):
    """批量下载：一行一个链接，或粘贴 UP主空间 / 收藏夹 / 合集链接。"""

    def __init__(self, app, **kw):
        content = BoxLayout(orientation="vertical", padding=dp(14),
                            spacing=dp(10))
        content.add_widget(themed_label(
            text="每行一个链接（视频 / 番剧 / 合集 / UP主空间 / 收藏夹）",
            font_size=sp(12), color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None, height=dp(40), halign="left", valign="top"))
        self.input = TextInput(
            hint_text="BV1xx411c7mD\nBV1yy411c7mE\nhttps://space.bilibili.com/123456",
            font_name=FONT_NAME or "", font_size=sp(12.5), multiline=True,
            background_color=(0.97, 0.97, 0.97, 1),
            foreground_color=(0.1, 0.1, 0.1, 1),
            cursor_color=(0.0, 0.63, 0.84, 1))
        content.add_widget(self.input)

        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        b_cancel = Button(text="取消", background_normal="",
                          background_color=(0.94, 0.94, 0.94, 1),
                          color=(0.2, 0.2, 0.2, 1),
                          font_name=FONT_NAME or "", font_size=sp(14))
        b_cancel.bind(on_release=lambda *_: self.dismiss())
        row.add_widget(b_cancel)
        b_ok = Button(text="开始批量下载", background_normal="",
                      background_color=(0.0, 0.63, 0.84, 1),
                      color=(1, 1, 1, 1), font_name=FONT_NAME or "",
                      font_size=sp(14))
        b_ok.bind(on_release=self._go)
        row.add_widget(b_ok)
        content.add_widget(row)

        super().__init__(title="批量下载", content=content,
                         size_hint=(0.94, 0.72), auto_dismiss=False,
                         title_font=FONT_NAME or "",
                         separator_color=(0, 0.63, 0.84, 1))
        self.app = app

    def _go(self, *_):
        raw = (self.input.text or "").strip()
        urls = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not urls:
            ti("提示", "请先输入至少一个链接")
            return
        self.dismiss()
        self.app.batch_download(urls)


# ==========================================================================
# 12. 应用
# ==========================================================================

class BilibiliAndroidApp(App):
    title = "B站视频解析工具"
    font_name = StringProperty(FONT_NAME or "")
    app_version = "2.2.0"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.last_info = None
        self.parse_cancelled = False
        self.user_name = ""
        self._parser = None
        self._download_manager = None
        self._task_manager = None
        self._history = None
        self._config = None
        self.settings = {}
        self.save_dir = ""
        self._row_titles = {}

    # ------------------------------------------------------------ 基础设施
    @property
    def user_data_dir_(self):
        try:
            return self.user_data_dir
        except Exception:
            return _HERE

    # ------------------------------------------------------------ 业务桥接
    def get_config(self):
        if self._config is None:
            from config import ConfigLoader
            self._config = ConfigLoader()
        return self._config

    def get_parser(self):
        """复用桌面版解析器。"""
        if self._parser is None:
            from bilibili_parser import BilibiliParser
            self._parser = BilibiliParser(config=self.get_config())
        return self._parser

    @property
    def history(self):
        if self._history is None:
            from download_history import DownloadHistory
            self._history = DownloadHistory()
        return self._history

    def get_download_manager(self):
        """复用桌面版下载引擎（靠 qt_compat 提供的 Qt 符号）。"""
        if self._download_manager is None:
            from downloader import DownloadManager
            from task_manager import TaskManager
            self._task_manager = TaskManager()
            self._download_manager = DownloadManager(
                parser=self.get_parser(),
                task_manager=self._task_manager,
                max_threads=PROFILE["concurrency"],
                max_concurrent_tasks=PROFILE["max_tasks"],
            )
            self._hook_signals(self._download_manager)
        return self._download_manager

    def _hook_signals(self, dm):
        """把引擎信号桥接到界面（引擎在工作线程 emit，必须切回主线程）。"""
        mapping = [
            ("global_progress_updated", self._sig_global_progress),
            ("episode_progress_updated", self._sig_episode_progress),
            ("task_added", self._sig_task_added),
            ("task_status_changed", self._sig_task_status),
            ("same_task_exists", self._sig_same_task),
            ("all_finished", self._sig_all_finished),
            ("merge_started", self._sig_merge),
            ("merge_finished", self._sig_merge_done),
        ]
        for name, handler in mapping:
            try:
                sig = getattr(dm, name, None)
                if sig is not None:
                    sig.connect(handler)
            except Exception:
                pass

    # ------------------------------------------------------------ 信号槽
    # 注意：这些可能在工作线程被调用，须 Clock 切主线程
    def _sig_global_progress(self, pct, text=""):
        Clock.schedule_once(
            lambda dt: self._apply_global_progress(pct, text), 0)

    def _apply_global_progress(self, pct, text):
        for tid, row in list(self.task_tab.rows.items()):
            row.update_progress(pct, text)

    def _sig_episode_progress(self, task_id, index, pct, text=""):
        Clock.schedule_once(
            lambda dt: self.task_tab.update_task(task_id, pct, text), 0)

    def _sig_task_added(self, task_id):
        pass

    def _sig_task_status(self, task_id):
        pass

    def _sig_same_task(self, params):
        Clock.schedule_once(
            lambda dt: ti("提示", "该任务已在下载队列中"), 0)

    def _sig_all_finished(self):
        Clock.schedule_once(lambda dt: self._on_all_finished(), 0)

    def _on_all_finished(self):
        self.parse_tab.set_status("全部下载完成")
        ti("完成", "所有下载任务已完成")

    def _sig_merge(self, task_id, index=0):
        Clock.schedule_once(
            lambda dt: self.task_tab.update_task(task_id, 95, "正在合并音视频…"), 0)

    def _sig_merge_done(self, task_id, index=0):
        Clock.schedule_once(
            lambda dt: self.task_tab.update_task(task_id, 100, "已完成"), 0)

    # ------------------------------------------------------------ 目录
    def _default_save_dir(self):
        candidates = []
        if _is_android():
            try:
                from android.storage import primary_external_storage_path
                candidates.append(os.path.join(
                    primary_external_storage_path(), "Download", "B站下载"))
            except Exception:
                pass
            try:
                from jnius import autoclass
                Environment = autoclass("android.os.Environment")
                candidates.append(os.path.join(
                    Environment.getExternalStorageDirectory()
                    .getAbsolutePath(), "Download", "B站下载"))
            except Exception:
                pass
        candidates.append(os.path.join(self.user_data_dir_, "B站下载"))
        for path in candidates:
            try:
                os.makedirs(path, exist_ok=True)
                return path
            except Exception:
                continue
        return self.user_data_dir_

    def open_download_dir(self):
        self.parse_tab.set_status("下载目录：%s" % self.save_dir)
        ti("下载目录", self.save_dir)

    def choose_save_dir(self):
        """Android 上用系统目录选择器；不可用时退回默认目录。"""
        def _fallback(*_):
            ti("提示", "本设备不支持目录选择，继续使用：\n%s" % self.save_dir)

        if not _is_android():
            _fallback()
            return
        try:
            from android import activity  # noqa: F401
            from jnius import autoclass, cast
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            activity = PythonActivity.mActivity
            activity.startActivityForResult(intent, 0x1234)
            ti("提示", "请在系统窗口中选择目录")
        except Exception:
            _fallback()

    def reset_save_dir(self):
        self.save_dir = self._default_save_dir()
        self.settings["save_dir"] = self.save_dir
        self.persist_settings()
        self.parse_tab.path_lbl.text = self.save_dir
        self.settings_tab.path_lbl.text = self.save_dir
        ti("提示", "已恢复默认目录")

    # ------------------------------------------------------------ 设置持久化
    def load_settings(self):
        import json
        path = os.path.join(self.user_data_dir_, "android_settings.json")
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as fh:
                    self.settings = json.load(fh) or {}
        except Exception:
            self.settings = {}
        self.settings.setdefault("default_quality", "自动（最高）")
        self.save_dir = (self.settings.get("save_dir")
                         or self._default_save_dir())
        self.settings["save_dir"] = self.save_dir

    def persist_settings(self):
        import json
        path = os.path.join(self.user_data_dir_, "android_settings.json")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(self.settings, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ------------------------------------------------------------ 下载
    def start_download(self, info, qn=0, content_type=0, want_danmaku=False,
                       audio_quality=30280):
        """组装 download_params —— 字段与桌面版 ui.py 完全一致。"""
        try:
            dm = self.get_download_manager()
            title = info.get("title") or info.get("name") or "video"
            task_id = str(int(time.time() * 1000))

            eps = info.get("episodes") or []
            if not eps:
                ti("提示", "没有可下载的内容")
                return

            # 只保留要下载的集（episode_range 已在解析时应用）
            row = self.task_tab.add_task(task_id, title, content_type)
            row.update_progress(0, "已加入队列")
            self._row_titles[task_id] = title

            cfg = self.get_config()
            params = {
                "url": info.get("url") or "",
                "video_info": info,
                "qn": qn,
                "save_path": self.save_dir,
                "episodes": eps,
                "resume_download": True,
                "task_id": task_id,
                # 0=有声视频 1=仅音频 2=仅视频（与桌面版一致）
                "download_content_type": content_type,
                "download_danmaku": bool(want_danmaku),
                "video_format": cfg.get_app_setting("video_output_format", "mp4"),
                "audio_format": cfg.get_app_setting("audio_output_format", "mp3"),
                "audio_quality": audio_quality,
                "danmaku_format": str(
                    cfg.get_app_setting("danmaku_output_format", "xml")).upper(),
            }

            dm.start_download(params)
            self.parse_tab.set_status("已开始下载到：%s" % self.save_dir)
        except Exception as exc:
            traceback.print_exc()
            msg = str(exc)[:200]
            self.parse_tab.set_status("下载启动失败：%s" % msg)
            ti("下载失败", msg)

    def download_danmaku_only(self, info):
        """只下载弹幕（桌面版有独立入口）。"""
        def _work():
            try:
                parser = self.get_parser()
                eps = info.get("episodes") or []
                done = 0
                for ep in eps:
                    cid = ep.get("cid")
                    if not cid:
                        continue
                    data = parser.get_danmaku(cid, ep.get("aid"))
                    if not data:
                        continue
                    xml = parser.convert_danmaku_format(data, "XML")
                    title = ep.get("title") or info.get("title") or "danmaku"
                    safe = "".join(c for c in str(title)
                                   if c not in '\\/:*?"<>|').strip()
                    path = os.path.join(self.save_dir, safe + ".xml")
                    with open(path, "w", encoding="utf-8") as fh:
                        fh.write(xml if isinstance(xml, str) else str(xml))
                    done += 1
                Clock.schedule_once(
                    lambda dt: (self.parse_tab.set_status(
                        "弹幕下载完成，共 %d 个" % done),
                        ti("完成", "已下载 %d 个弹幕文件" % done)), 0)
            except Exception as exc:
                traceback.print_exc()
                Clock.schedule_once(
                    lambda dt: ti("失败", "弹幕下载失败：%s" % str(exc)[:150]), 0)

        threading.Thread(target=_work, daemon=True).start()

    def toggle_pause(self, task_id):
        try:
            dm = self.get_download_manager()
            task = self._task_manager.get_task(task_id) if self._task_manager else None
            paused = bool(task and task.get("status") == "paused")
            if paused:
                dm.resume_task(task_id)
                self.task_tab.set_paused(task_id, False)
            else:
                dm.pause_task(task_id)
                self.task_tab.set_paused(task_id, True)
        except Exception as exc:
            ti("失败", "操作失败：%s" % str(exc)[:150])

    def cancel_task(self, task_id):
        def _do():
            try:
                dm = self.get_download_manager()
                dm.cancel_task(task_id)
                self.task_tab.update_task(task_id, 0, "已取消")
            except Exception as exc:
                ti("失败", str(exc)[:150])
        confirm("取消下载", "确定取消该任务吗？", _do)

    def batch_download(self, urls):
        """批量下载：逐个解析后入队（用线程池限流，避免打爆设备）。"""
        self.parse_tab.set_status("批量解析中，共 %d 个链接…" % len(urls))

        def _work():
            ok = fail = 0
            for u in urls:
                if self.parse_cancelled:
                    break
                try:
                    parser = self.get_parser()
                    mtype, mid = ParseTab._split_url(u)
                    info = parser.parse_media(mtype, mid)
                    if info and info.get("success", True):
                        Clock.schedule_once(
                            lambda dt, i=info: self.start_download(
                                i, qn=ParseTab._resolve_qn_static(
                                    self.settings.get("default_quality"))), 0)
                        ok += 1
                    else:
                        fail += 1
                except Exception:
                    fail += 1
            Clock.schedule_once(
                lambda dt: (self.parse_tab.set_status(
                    "批量完成：成功 %d，失败 %d" % (ok, fail)),
                    ti("批量下载", "成功 %d 个，失败 %d 个" % (ok, fail))), 0)

        threading.Thread(target=_work, daemon=True).start()

    @staticmethod
    def _resolve_qn_static(text):
        if not text or text.startswith("自动"):
            return 0
        for k, v in QN_MAP.items():
            if text.startswith(k):
                return v
        return 0

    # ------------------------------------------------------------ 工具
    def download_tools(self):
        ti("提示", "开始下载外部工具，请保持网络畅通…")

        def _work():
            try:
                from tool_manager import ToolManager
                tm = ToolManager()
                ok = []
                for name in ("ffmpeg", "mp4decrypt"):
                    fn = getattr(tm, "download_tool", None)
                    if fn is None:
                        continue
                    try:
                        fn(name)
                        ok.append(name)
                    except Exception as exc:
                        print("download %s failed: %s" % (name, exc))
                Clock.schedule_once(
                    lambda dt: (ti("完成", "已下载：%s" % ("、".join(ok) or "无")),
                                self.settings_tab.refresh_tools()), 0)
            except Exception as exc:
                traceback.print_exc()
                Clock.schedule_once(
                    lambda dt: ti("失败", "工具下载失败：%s" % str(exc)[:150]), 0)

        threading.Thread(target=_work, daemon=True).start()

    # ------------------------------------------------------------ 账号
    def open_login(self):
        pop = LoginPopup(self)
        pop.open()
        pop.start()

    def on_login_success(self, user_info):
        try:
            name = (user_info or {}).get("uname") or (user_info or {}).get("name") or "已登录"
            self.user_name = str(name)
            self.settings_tab.refresh_user()
            self.parse_tab.set_status("登录成功：%s" % self.user_name)
        except Exception:
            pass

    def logout(self):
        def _do():
            try:
                parser = self.get_parser()
                parser.save_cookies({})
                self.user_name = ""
                self.settings_tab.refresh_user()
                self.parse_tab.set_status("已退出登录")
                ti("提示", "已退出登录")
            except Exception as exc:
                ti("失败", str(exc)[:150])
        confirm("退出登录", "确定要退出当前账号吗？", _do)

    def open_batch(self):
        BatchPopup(self).open()

    # ------------------------------------------------------------ UI
    def build(self):
        Builder.load_string(KV)
        self.load_settings()

        root = BoxLayout(orientation="vertical")
        self._bg(root, (0.96, 0.96, 0.96, 1))

        # 顶部标题栏（桌面版主色 #00a1d6）
        header = BoxLayout(size_hint_y=None, height=dp(58),
                           padding=(dp(12), 0), spacing=dp(10))
        self._bg(header, (0.0, 0.63, 0.84, 1))
        try:
            logo = resource_path("logo_ui.png")
            if os.path.isfile(logo):
                header.add_widget(Image(source=logo, size_hint_x=None,
                                        width=dp(38), size_hint_y=None,
                                        height=dp(38)))
        except Exception:
            pass
        header.add_widget(themed_label(
            text="B站视频解析工具", bold=True, font_size=sp(18),
            color=(1, 1, 1, 1), halign="left", valign="middle"))
        root.add_widget(header)

        # Tab
        self.tabs = TabbedPanel(do_default_tab=False,
                                tab_width=Window.width / 4.0)
        self.parse_tab = ParseTab(self)
        self.task_tab = TaskTab(self)
        self.history_tab = HistoryTab(self)
        self.settings_tab = SettingsTab(self)

        for name, widget in (("解析", self.parse_tab),
                             ("任务", self.task_tab),
                             ("历史", self.history_tab),
                             ("设置", self.settings_tab)):
            item = TabbedPanelItem(text=name, font_name=FONT_NAME or "")
            item.add_widget(widget)
            self.tabs.add_widget(item)

        self.tabs.default_tab = self.tabs.tab_list[0]
        self.tabs.switch_to(self.tabs.tab_list[0])
        root.add_widget(self.tabs)

        # 切到历史页时刷新
        self.tabs.bind(current_tab=self._on_tab_change)

        # 启动后异步检查登录态 + 工具
        Clock.schedule_once(lambda dt: self._check_login_state(), 1.0)
        return root

    def _on_tab_change(self, _tabs, tab):
        try:
            if tab is self.tabs.tab_list[2]:
                self.history_tab.reload()
        except Exception:
            pass

    @staticmethod
    def _bg(widget, rgba):
        from kivy.graphics import Color, Rectangle
        with widget.canvas.before:
            Color(*rgba)
            rect = Rectangle(pos=widget.pos, size=widget.size)
        widget.bind(pos=lambda w, v: setattr(rect, "pos", v),
                    size=lambda w, v: setattr(rect, "size", v))

    def _check_login_state(self):
        def _work():
            try:
                parser = self.get_parser()
                info = parser.get_user_info()
                if info and info.get("uname"):
                    self.user_name = str(info["uname"])
                    Clock.schedule_once(
                        lambda dt: self.settings_tab.refresh_user(), 0)
            except Exception:
                pass
        threading.Thread(target=_work, daemon=True).start()

    # ------------------------------------------------------------ 生命周期
    def on_pause(self):
        self.parse_cancelled = True
        return True

    def on_resume(self):
        self.parse_cancelled = False

    def on_stop(self):
        try:
            self.persist_settings()
        except Exception:
            pass


# Python 关键字冲突：此处给 ti 一个别名方便调用
ti = tip


def main():
    BilibiliAndroidApp().run()


if __name__ == "__main__":
    main()
