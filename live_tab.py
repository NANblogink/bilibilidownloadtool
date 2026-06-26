# -*- coding: utf-8 -*-
"""
B站直播功能 Tab 页
功能：直播间信息查询、直播流录制、回放下载
"""

import os
import sys
import json
import time
import logging
import subprocess
import threading
import re
import queue
import socket
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QPixmap, QImage, QFont, QIcon, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTextEdit, QProgressBar, QGroupBox, QScrollArea,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QSplitter, QFrame, QSpinBox, QCheckBox, QTabWidget,
    QGridLayout, QSizePolicy, QSpacerItem, QSystemTrayIcon
)
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

try:
    from live_parser import LiveParser, LIVE_STATUS_MAP, QUALITY_MAP
except ImportError:
    LiveParser = None

try:
    from platform_utils import IS_WINDOWS, exe, subprocess_no_window_kwargs
except ImportError:
    IS_WINDOWS = True
    def exe(name): return name + ('.exe' if os.name == 'nt' else '')
    def subprocess_no_window_kwargs(): return {}

logger = logging.getLogger(__name__)

# 尝试导入 scale/scale_style
try:
    from ui import scale, scale_style
except ImportError:
    def scale(v): return int(v)
    def scale_style(s): return re.sub(r'(\d+)px', lambda m: str(int(m.group(1))) + 'px', s)


def _find_ffmpeg():
    """查找 ffmpeg 可执行文件路径"""
    # 1. _internal/ffmpeg/
    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else sys._MEIPASS
        for d in [os.path.join(base, '_internal', 'ffmpeg'),
                  os.path.join(base, 'ffmpeg'),
                  os.path.join(base, '_internal')]:
            p = os.path.join(d, exe('ffmpeg'))
            if os.path.exists(p):
                return p
    # 2. 当前目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for d in [os.path.join(script_dir, 'ffmpeg'), script_dir]:
        p = os.path.join(d, exe('ffmpeg'))
        if os.path.exists(p):
            return p
    # 3. PATH
    import shutil
    found = shutil.which('ffmpeg')
    return found


class LiveRecordThread(QThread):
    """直播持续录制：每段写临时 .ts，完成后二进制追加到主文件（MPEG-TS 天然支持拼接），最终转 mp4"""
    status_changed = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)
    record_finished = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, stream_url, output_path, format_type="hls", duration=0,
                 url_refresher=None, room_id="", content_type=0):
        super().__init__()
        self.stream_url = stream_url
        self.output_path = output_path
        self.format_type = format_type
        self.duration = duration
        self.url_refresher = url_refresher
        self.room_id = room_id
        self.content_type = content_type  # 0=完整视频, 1=仅音频, 2=仅画面
        self._stop_flag = False
        self._pause_flag = False
        self._paused_elapsed = 0
        self._retry_count = 0
        self._max_retries = 5
        self.process = None
        self.start_time = 0
        self._segment_count = 0

    def run(self):
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            self.error_occurred.emit("未找到 ffmpeg，无法录制")
            return

        base, ext = os.path.splitext(self.output_path)
        self.ts_path = f"{base}.ts"
        current_url = self.stream_url
        self.start_time = time.time()

        while not self._stop_flag:
            if self._pause_flag:
                self._do_pause()
                if self._stop_flag:
                    break
                continue

            # 每段录制到临时 .ts 文件
            temp_path = f"{base}_temp_{self._segment_count:03d}.ts"
            url_expired = self._record_segment(ffmpeg_path, current_url, temp_path)

            if self._stop_flag:
                # 停止时也要把已录内容合并
                self._merge_temp(temp_path)
                break

            if self._pause_flag:
                self._merge_temp(temp_path)
                continue

            # 正常结束或URL过期，合并临时文件到主文件
            self._merge_temp(temp_path)

            if not url_expired:
                # 直播正常结束
                break

            # URL过期，刷新后继续
            new_url = self._handle_retry(current_url)
            if new_url is None:
                break
            current_url = new_url
            self._segment_count += 1

        if self._stop_flag:
            self.status_changed.emit("录制已停止")

        # 最终：.ts → .mp4（如果用户选了mp4）
        self._remux_to_target()
        self.record_finished.emit(True, f"录制结束: {self.output_path}")

    def _record_segment(self, ffmpeg_path, stream_url, output_path):
        """录制一个分段到临时 .ts 文件，返回是否URL过期"""
        try:
            cmd = [ffmpeg_path, '-y',
                   '-rw_timeout', '10000000',
                   '-timeout', '10000000']

            if self.format_type == "hls":
                cmd += ['-protocol_whitelist', 'concat,file,http,https,tcp,tls,crypto',
                        '-max_reload', '3',
                        '-m3u8_hold_counters', '3',
                        '-i', stream_url,
                        '-reconnect', '1',
                        '-reconnect_streamed', '1',
                        '-reconnect_delay_max', '5']
            else:
                cmd += ['-i', stream_url]

            if self.duration > 0:
                remaining = self.duration - self._paused_elapsed
                if remaining <= 0:
                    return False
                cmd += ['-t', str(int(remaining))]

            # 输出为 mpegts，被中断后文件仍可播放
            cmd += ['-c', 'copy',
                    '-f', 'mpegts',
                    output_path]

            self.status_changed.emit("正在连接直播流...")
            logger.info(f"[录制] 分段 {self._segment_count}: {stream_url[:60]}...")

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **subprocess_no_window_kwargs()
            )

            # 非阻塞读取
            q = queue.Queue()
            def reader():
                try:
                    for line in iter(self.process.stdout.readline, b''):
                        q.put(line)
                except Exception:
                    pass
                q.put(None)

            t = threading.Thread(target=reader, daemon=True)
            t.start()

            url_expired = False
            expired_at = None
            last_output = time.time()

            while True:
                try:
                    line = q.get(timeout=1.0)
                    last_output = time.time()
                    if line is None:
                        break
                    if self._stop_flag or self._pause_flag:
                        break

                    line_text = line.decode('utf-8', errors='ignore').strip()
                    if not line_text:
                        continue

                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.?\d*)', line_text)
                    if time_match:
                        h, m, s = time_match.groups()
                        total_sec = float(h) * 3600 + float(m) * 60 + float(s)
                        ih, im, isec = int(float(h)), int(float(m)), float(s)
                        time_str = f"{ih:02d}:{im:02d}:{isec:05.2f}"
                        self._paused_elapsed = int(total_sec)
                        self.progress_updated.emit(int(total_sec), time_str)

                    low = line_text.lower()
                    if any(kw in low for kw in ['404', 'not found', 'server returned 404']):
                        url_expired = True
                        if expired_at is None:
                            expired_at = time.time()
                        logger.warning(f"[录制] URL过期: {line_text}")
                    if 'error' in low or 'failed' in low:
                        logger.warning(f"ffmpeg: {line_text}")

                except queue.Empty:
                    if self._stop_flag or self._pause_flag:
                        break
                    if url_expired and expired_at and (time.time() - expired_at > 6):
                        break
                    if time.time() - last_output > 30:
                        logger.warning("[录制] 30秒无输出")
                        break

            # 优雅停止 ffmpeg（发送 q 让它写完文件头/尾）
            self._graceful_stop()
            return url_expired

        except Exception as e:
            logger.warning(f"[录制] 分段异常: {e}")
            self._kill_process()
            return False

    def _graceful_stop(self):
        """发送 q 让 ffmpeg 优雅退出，保证 .ts 文件完整"""
        proc = self.process
        if proc is None:
            return
        try:
            if proc.poll() is None:
                try:
                    proc.stdin.write(b'q\n')
                    proc.stdin.flush()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=10)
                    self.process = None
                    return
                except Exception:
                    pass
        except Exception:
            pass
        self._kill_process()

    def _kill_process(self):
        proc = self.process
        if proc is None:
            return
        self.process = None
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()
                    try:
                        proc.wait(timeout=3)
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"终止进程失败: {e}")

    def _merge_temp(self, temp_path):
        """将临时 .ts 二进制追加到主 .ts 文件"""
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) < 1024:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            return

        try:
            if not os.path.exists(self.ts_path):
                # 第一段，直接重命名
                os.rename(temp_path, self.ts_path)
            else:
                # 后续段，二进制追加（MPEG-TS 天然支持）
                with open(self.ts_path, 'ab') as main_f:
                    with open(temp_path, 'rb') as temp_f:
                        while True:
                            chunk = temp_f.read(65536)
                            if not chunk:
                                break
                            main_f.write(chunk)
                os.remove(temp_path)
            logger.info(f"[录制] 已合并分段到 {self.ts_path} "
                        f"(总大小: {os.path.getsize(self.ts_path)//1024}KB)")
        except Exception as e:
            logger.warning(f"[录制] 合并临时文件失败: {e}")

    def _remux_to_target(self):
        """最终将 .ts 重封装/提取为用户选择的格式"""
        if not hasattr(self, 'ts_path') or not os.path.exists(self.ts_path) \
                or os.path.getsize(self.ts_path) < 1024:
            return

        try:
            ffmpeg_path = _find_ffmpeg()
            ext = os.path.splitext(self.output_path)[1].lower()
            if self.content_type == 1:
                # 仅音频：提取音频流
                cmd = [ffmpeg_path, '-y', '-i', self.ts_path,
                       '-vn', '-c:a', 'copy', self.output_path]
            elif self.content_type == 2:
                # 仅画面：丢弃音频流
                cmd = [ffmpeg_path, '-y', '-i', self.ts_path,
                       '-an', '-c:v', 'copy', self.output_path]
            elif ext in ['.mp4']:
                cmd = [ffmpeg_path, '-y', '-i', self.ts_path,
                       '-c', 'copy', '-movflags', '+faststart', self.output_path]
            else:
                cmd = [ffmpeg_path, '-y', '-i', self.ts_path,
                       '-c', 'copy', self.output_path]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **subprocess_no_window_kwargs())
            proc.wait(timeout=300)
            if os.path.exists(self.output_path) and os.path.getsize(self.output_path) > 1024:
                try:
                    os.remove(self.ts_path)
                except Exception:
                    pass
                logger.info(f"[录制] 已转封装: {self.output_path}")
        except Exception as e:
            logger.warning(f"[录制] 重封装失败: {e}")

    def _handle_retry(self, current_url):
        """URL过期重试，返回新URL或None"""
        if not self.url_refresher:
            self.status_changed.emit("直播流中断，未配置URL刷新")
            return None
        if self._retry_count >= self._max_retries:
            self.status_changed.emit("超过最大重试次数")
            return None

        self._retry_count += 1
        self.status_changed.emit(
            f"URL可能过期，正在刷新 ({self._retry_count}/{self._max_retries})...")

        new_url = None
        for _ in range(3):
            try:
                new_url = self.url_refresher()
                if new_url:
                    break
            except Exception as e:
                logger.warning(f"[录制] 刷新URL失败: {e}")
            time.sleep(2)

        if new_url:
            logger.info("[录制] 已获取新URL，继续录制")
            self.status_changed.emit("已获取新URL，继续录制...")
            return new_url
        else:
            self.status_changed.emit("刷新URL失败，5秒后重试...")
            time.sleep(5)
            return current_url

    def _do_pause(self):
        self.status_changed.emit("暂停录制中...")
        while self._pause_flag and not self._stop_flag:
            time.sleep(0.5)
        if not self._stop_flag:
            self.status_changed.emit("继续录制中...")

    def stop(self):
        self._stop_flag = True
        self._pause_flag = False

    def pause(self):
        self._pause_flag = True

    def resume(self):
        self._pause_flag = False


class ReplayDownloadThread(QThread):
    """直播回放下载线程（支持ffmpeg下载和HTTP直连下载）"""
    progress_updated = pyqtSignal(int, str)  # (百分比, 状态文本)
    download_finished = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, output_path, use_ffmpeg=False, content_type=0):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.use_ffmpeg = use_ffmpeg
        self.content_type = content_type  # 0=完整视频, 1=仅音频, 2=仅画面
        self._stop_flag = False

    def run(self):
        if self.use_ffmpeg:
            self._download_with_ffmpeg()
        else:
            self._download_with_http()

    def _download_with_http(self):
        """使用HTTP直接下载"""
        try:
            import requests
            self.progress_updated.emit(0, "开始下载回放...")
            resp = requests.get(self.url, stream=True, timeout=30,
                                headers={'User-Agent': 'Mozilla/5.0'})
            resp.raise_for_status()

            total = int(resp.headers.get('content-length', 0))
            downloaded = 0
            start_time = time.time()

            with open(self.output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if self._stop_flag:
                        break
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            speed = downloaded / (time.time() - start_time + 0.1) / 1024 / 1024
                            self.progress_updated.emit(pct, f"下载中 {pct}%  {speed:.1f} MB/s")
                        else:
                            speed = downloaded / (time.time() - start_time + 0.1) / 1024 / 1024
                            self.progress_updated.emit(-1, f"已下载 {downloaded/1024/1024:.1f} MB  {speed:.1f} MB/s")

            if self._stop_flag:
                self.download_finished.emit(False, "下载已取消")
            else:
                if self.content_type != 0:
                    self._post_process()
                self.download_finished.emit(True, f"下载完成: {self.output_path}")

        except Exception as e:
            self.error_occurred.emit(f"下载失败: {str(e)}")

    def _post_process(self):
        """下载完成后按 content_type 提取音频或去除音频"""
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            logger.warning("[回放] 未找到 ffmpeg，跳过后处理")
            return
        try:
            tmp_path = self.output_path + ".tmp"
            if self.content_type == 1:
                cmd = [ffmpeg_path, '-y', '-i', self.output_path,
                       '-vn', '-c:a', 'copy', tmp_path]
            elif self.content_type == 2:
                cmd = [ffmpeg_path, '-y', '-i', self.output_path,
                       '-an', '-c:v', 'copy', tmp_path]
            else:
                return
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **subprocess_no_window_kwargs())
            proc.wait(timeout=300)
            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 1024:
                os.replace(tmp_path, self.output_path)
                logger.info(f"[回放] 已后处理: {self.output_path}")
            else:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[回放] 后处理失败: {e}")

    def _download_with_ffmpeg(self):
        """使用ffmpeg下载（支持m3u8等流媒体链接）"""
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            # 回退到HTTP下载
            self._download_with_http()
            return

        try:
            base_cmd = [ffmpeg_path, '-y',
                        '-protocol_whitelist', 'concat,file,http,https,tcp,tls,crypto',
                        '-i', self.url]
            if self.content_type == 1:
                cmd = base_cmd + ['-vn', '-c:a', 'copy', self.output_path]
            elif self.content_type == 2:
                cmd = base_cmd + ['-an', '-c:v', 'copy', self.output_path]
            else:
                cmd = base_cmd + ['-c', 'copy', '-bsf:a', 'aac_adtstoasc',
                                  '-movflags', '+faststart', self.output_path]

            self.progress_updated.emit(0, "开始下载回放（ffmpeg）...")
            logger.info(f"ffmpeg下载回放: {' '.join(cmd[:6])}...")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                **subprocess_no_window_kwargs()
            )

            for line in iter(process.stdout.readline, b''):
                if self._stop_flag:
                    break
                line_text = line.decode('utf-8', errors='ignore').strip()
                if line_text:
                    time_match = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', line_text)
                    if time_match:
                        h, m, s = time_match.groups()
                        time_str = f"{int(h):02d}:{int(m):02d}:{int(s):05.2f}"
                        self.progress_updated.emit(-1, f"下载中 {time_str}")

            if self._stop_flag:
                try:
                    process.terminate()
                    process.wait(timeout=5)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass
                self.download_finished.emit(False, "下载已取消")
            else:
                ret = process.wait()
                if ret == 0:
                    self.download_finished.emit(True, f"下载完成: {self.output_path}")
                else:
                    self.error_occurred.emit(f"ffmpeg下载失败（代码 {ret}）")

        except Exception as e:
            self.error_occurred.emit(f"ffmpeg下载错误: {str(e)}")

    def stop(self):
        self._stop_flag = True


class LiveTab(QWidget):
    """直播功能 Tab 页"""

    # 线程安全信号
    _query_done_signal = pyqtSignal(bool, object)
    _stream_done_signal = pyqtSignal(bool, object)
    _record_error_signal = pyqtSignal(str)
    _start_record_signal = pyqtSignal(str, str, str, int)  # stream_url, output_path, format_type, duration
    _replay_list_signal = pyqtSignal(object)
    _replay_url_signal = pyqtSignal(object, str, str, int)
    _error_signal = pyqtSignal(str)

    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.config = config
        self.parent_window = parent
        self.live_parser = None
        self.record_thread = None
        self.replay_download_thread = None
        self._recording_session_id = None  # 当前录制会话ID（由父窗口的录播工具管理）
        self._init_parser()
        self._init_ui()
        self._init_network()

        # 连接线程安全信号
        self._query_done_signal.connect(self._on_query_done)
        self._stream_done_signal.connect(self._on_stream_done)
        self._record_error_signal.connect(self._on_record_error_main)
        self._start_record_signal.connect(self._do_start_record)
        self._replay_list_signal.connect(self._on_replay_list_loaded)
        self._replay_url_signal.connect(self._on_replay_url_ready)
        self._error_signal.connect(self._on_error_msg)

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

        # 1) 先以 cookie.txt 为基准（包含 SESSDATA/bili_jct 等登录凭据）
        file_cookies, file_csrf = self._load_cookie_txt()
        if file_cookies:
            cookies.update(file_cookies)
            if file_csrf:
                csrf_token = file_csrf
            sources.append("cookie.txt")

        # 2) 再合并主窗口 parser 的 cookie（可能包含 buvid3/sid/bili_ticket 等动态 cookie）
        #    但保留 cookie.txt 中的核心登录凭据，防止 parser 中的过期/空值覆盖有效登录态
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

        # 3) 兜底：尝试 config 中的 cookie 字符串
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
        """初始化直播解析器"""
        if LiveParser is None:
            return
        cookies, csrf_token, source = self._get_cookies_from_parent()
        self.live_parser = LiveParser(config=self.config, cookies=cookies, csrf_token=csrf_token)
        logger.info(f"直播Tab初始化，来源={source}, Cookie字段数: {len(cookies)}")

    def _refresh_cookies(self):
        """刷新直播解析器的Cookie（确保使用最新的登录状态）"""
        if not self.live_parser:
            return
        cookies, csrf_token, source = self._get_cookies_from_parent()
        if cookies:
            self.live_parser.update_cookies(cookies, csrf_token)
            logger.info(f"直播Tab Cookie已刷新，来源={source}, 字段数: {len(cookies)}")

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
                padding: 3px 10px; border: 1px solid #dee2e6; border-bottom: none;
                border-top-left-radius: 3px; border-top-right-radius: 3px;
                margin-right: 1px; font-size: 11px;
            }
            QTabBar::tab:hover { background-color: #e9ecef; color: #495057; }
            QTabBar::tab:selected { background-color: white; color: #2563eb; border-color: #409eff; border-bottom-color: white; }
            QTabWidget::pane {
                background-color: white; border: 1px solid #dee2e6; border-top: none;
                border-radius: 0 0 3px 3px; padding: 2px;
            }
        """))

        self.sub_tabs.addTab(self._create_info_tab(), "直播间信息")
        self.sub_tabs.addTab(self._create_record_tab(), "直播录制")
        self.sub_tabs.addTab(self._create_replay_tab(), "回放下载")

        main_layout.addWidget(self.sub_tabs)

        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(scale_style("font-size: 11px; color: #6c757d; padding: 1px;"))
        main_layout.addWidget(self.status_label)

    _GB = """
        QGroupBox {
            font-size: 11px; font-weight: 600; color: #555;
            border: 1px solid #e0e4ea; border-radius: 3px;
            margin-top: 8px; padding: 4px;
        }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
    """

    def _create_info_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(scale(4))
        layout.setContentsMargins(scale(4), scale(4), scale(4), scale(4))

        # 输入区
        input_group = QGroupBox("查询直播间")
        input_group.setStyleSheet(scale_style(self._GB))
        input_layout = QHBoxLayout(input_group)
        input_layout.setSpacing(scale(4))
        input_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        input_layout.addWidget(QLabel("房间号:"))
        self.room_id_input = QLineEdit()
        self.room_id_input.setPlaceholderText("输入房间号")
        self.room_id_input.setMinimumHeight(scale(28))
        self.room_id_input.setStyleSheet(scale_style("padding: 2px 6px;"))
        self.room_id_input.returnPressed.connect(self._query_room_info)
        input_layout.addWidget(self.room_id_input, stretch=1)

        self.query_btn = QPushButton("查询")
        self.query_btn.setStyleSheet(scale_style(
            "padding: 2px 10px; background-color: #00a1d6; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.query_btn.setMinimumHeight(scale(24))
        self.query_btn.clicked.connect(self._query_room_info)
        input_layout.addWidget(self.query_btn)

        layout.addWidget(input_group)

        # 信息展示区
        info_group = QGroupBox("直播间信息")
        info_group.setStyleSheet(scale_style(self._GB))
        info_layout = QGridLayout(info_group)
        info_layout.setSpacing(scale(4))
        info_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        self.cover_label = QLabel()
        self.cover_label.setFixedSize(scale(100), scale(66))
        self.cover_label.setStyleSheet(scale_style("border: 1px solid #dee2e6; border-radius: 3px; background: #f8f9fa;"))
        self.cover_label.setAlignment(Qt.AlignCenter)
        self.cover_label.setText("封面")
        info_layout.addWidget(self.cover_label, 0, 0, 4, 1)

        self.info_labels = {}
        fields = [
            ("title", "标题"), ("uname", "主播"), ("room_id", "房间号"),
            ("short_id", "短号"), ("live_status_text", "状态"),
            ("area_name", "分区"), ("online", "人气"),
            ("live_time", "开播时间"), ("description", "简介"),
        ]
        for i, (key, label) in enumerate(fields):
            row = i % 4
            col = (i // 4) * 2 + 1
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet(scale_style("font-size: 11px;"))
            info_layout.addWidget(lbl, row, col)
            val_label = QLabel("-")
            val_label.setStyleSheet(scale_style("font-size: 11px;"))
            self.info_labels[key] = val_label
            info_layout.addWidget(val_label, row, col + 1)

        layout.addWidget(info_group)

        # 直播流信息
        stream_group = QGroupBox("直播流")
        stream_group.setStyleSheet(scale_style(self._GB))
        stream_layout = QVBoxLayout(stream_group)
        stream_layout.setSpacing(scale(4))
        stream_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        q_layout = QHBoxLayout()
        q_layout.setSpacing(scale(4))
        q_layout.addWidget(QLabel("画质:"))
        self.quality_combo = QComboBox()
        self.quality_combo.setMinimumWidth(scale(80))
        self.quality_combo.setMinimumHeight(scale(26))
        q_layout.addWidget(self.quality_combo)
        q_layout.addStretch()

        self.get_stream_btn = QPushButton("获取直播流")
        self.get_stream_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #28a745; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.get_stream_btn.setMinimumHeight(scale(26))
        self.get_stream_btn.clicked.connect(self._get_live_stream)
        q_layout.addWidget(self.get_stream_btn)

        self.copy_url_btn = QPushButton("复制URL")
        self.copy_url_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #6c757d; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.copy_url_btn.setMinimumHeight(scale(26))
        self.copy_url_btn.clicked.connect(self._copy_stream_url)
        q_layout.addWidget(self.copy_url_btn)

        self.play_in_player_btn = QPushButton("播放器查看")
        self.play_in_player_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #e6a23c; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.play_in_player_btn.setMinimumHeight(scale(26))
        self.play_in_player_btn.clicked.connect(self._play_in_stream_player)
        q_layout.addWidget(self.play_in_player_btn)

        stream_layout.addLayout(q_layout)

        self.stream_url_text = QTextEdit()
        self.stream_url_text.setReadOnly(True)
        self.stream_url_text.setMaximumHeight(scale(50))
        self.stream_url_text.setStyleSheet(scale_style("font-size: 10px; background: #f8f9fa;"))
        stream_layout.addWidget(self.stream_url_text)

        layout.addWidget(stream_group)
        layout.addStretch()
        return tab

    def _query_room_info(self):
        """查询直播间信息"""
        raw_input = self.room_id_input.text().strip()
        if not raw_input:
            QMessageBox.warning(self, "提示", "请输入房间号")
            return
        # 兼容完整直播间 URL，提取房间号
        match = re.search(r'live\.bilibili\.com/(\d+)', raw_input, re.IGNORECASE)
        room_id = match.group(1) if match else raw_input
        if room_id != raw_input:
            self.room_id_input.setText(room_id)
        if not self.live_parser:
            QMessageBox.warning(self, "提示", "直播解析器未初始化")
            return

        self.query_btn.setEnabled(False)
        self.status_label.setText("正在查询...")
        logger.info(f"开始查询直播间，房间号: {room_id}")

        # 刷新Cookie，确保使用最新的登录状态
        self._refresh_cookies()

        def worker():
            try:
                # 先用 room_init 获取真实房间号
                init_result = self.live_parser.room_init(room_id)
                if not init_result["success"]:
                    logger.warning(f"room_init 失败: {init_result.get('error')}")
                    self._query_done_signal.emit(False, init_result.get("error", "查询失败"))
                    return

                init_data = init_result["data"]
                real_room_id = init_data["room_id"]
                self._room_id = real_room_id  # 保存供播放器刷新URL使用
                uid = init_data["uid"]
                logger.info(f"room_init 成功: 真实房间号={real_room_id}, 主播UID={uid}")

                # 获取房间信息
                info_result = self.live_parser.get_room_info(real_room_id)
                if not info_result["success"]:
                    logger.warning(f"get_room_info 失败: {info_result.get('error')}")
                    self._query_done_signal.emit(False, info_result.get("error", "查询失败"))
                    return

                room_data = info_result["data"]
                logger.info(f"get_room_info 成功: 标题={room_data.get('title')}, 状态={room_data.get('live_status_text')}")

                # 获取主播信息
                master_result = self.live_parser.get_master_info(uid)
                if master_result["success"]:
                    master_data = master_result["data"]
                    room_data["uname"] = master_data.get("uname", "-")
                    room_data["face"] = master_data.get("face", "")
                    logger.info(f"get_master_info 成功: 主播={room_data['uname']}")
                else:
                    room_data["uname"] = "-"
                    room_data["face"] = ""
                    logger.warning(f"get_master_info 失败: {master_result.get('error')}")

                self._query_done_signal.emit(True, room_data)
            except Exception as e:
                logger.exception("查询直播间异常")
                self._query_done_signal.emit(False, f"内部错误: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_query_done(self, success, data):
        """查询完成回调（主线程，由信号触发）"""
        logger.info(f"_on_query_done 被调用: success={success}")
        self.query_btn.setEnabled(True)
        if not success:
            self.status_label.setText(f"查询失败: {data}")
            return

        self.status_label.setText("查询成功")
        self._current_room_data = data

        try:
            # 更新信息展示
            for key, label in self.info_labels.items():
                val = data.get(key, "-")
                if key == "online" and isinstance(val, (int, float)) and val > 0:
                    label.setText(f"{val:,}")
                else:
                    label.setText(str(val) if val else "-")

            # 加载封面
            cover_url = data.get("user_cover", "")
            if cover_url:
                self._load_cover_image(cover_url)

            # 如果直播中，自动获取直播流
            if data.get("live_status") == 1:
                self.status_label.setText("直播中！自动获取直播流...")
                QTimer.singleShot(300, self._get_live_stream)
            else:
                self.status_label.setText(f"当前状态: {data.get('live_status_text', '未知')}")
        except Exception as e:
            logger.exception("更新直播间UI失败")
            self.status_label.setText(f"显示失败: {e}")

    def _on_error_msg(self, msg):
        """通用错误消息处理（主线程，由信号触发）"""
        self.status_label.setText(msg)

    def _load_cover_image(self, url):
        """异步加载封面图"""
        if not url:
            return
        try:
            from PyQt5.QtCore import QUrl
            reply = self.network_manager.get(QNetworkRequest(QUrl(url)))
            self._pending_covers[reply] = self.cover_label
            reply.finished.connect(lambda: self._on_cover_loaded(reply))
        except Exception as e:
            logger.warning(f"加载封面失败: {e}")

    def _on_cover_loaded(self, reply):
        """封面图加载完成"""
        label = self._pending_covers.pop(reply, None)
        if not label:
            reply.deleteLater()
            return
        try:
            if reply.error() == QNetworkReply.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(data):
                    label.setPixmap(pixmap.scaled(
                        label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        except Exception as e:
            logger.warning(f"封面显示失败: {e}")
        finally:
            reply.deleteLater()

    def _get_live_stream(self):
        """获取直播流"""
        if not hasattr(self, '_current_room_data') or not self._current_room_data:
            QMessageBox.warning(self, "提示", "请先查询直播间信息")
            return

        room_data = self._current_room_data
        if room_data.get("live_status") != 1:
            QMessageBox.warning(self, "提示", "当前未在直播中")
            return

        room_id = room_data.get("room_id")
        if not room_id:
            return

        self.get_stream_btn.setEnabled(False)
        self.status_label.setText("获取直播流中...")

        def worker():
            try:
                logger.info(f"开始获取直播流，房间号: {room_id}")
                result = self.live_parser.get_live_stream_url(room_id, platform="h5")
                if not result["success"]:
                    self._stream_done_signal.emit(False, result.get("error", "获取失败"))
                    return

                data = result["data"]
                self._stream_done_signal.emit(True, data)
            except Exception as e:
                logger.exception("获取直播流异常")
                self._stream_done_signal.emit(False, f"内部错误: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_stream_done(self, success, data):
        """获取直播流完成"""
        try:
            self.get_stream_btn.setEnabled(True)
            if not success:
                self.status_label.setText(f"获取失败: {data}")
                return

            # 回放播放请求
            if isinstance(data, dict) and data.get("for_playback"):
                url = data.get("stream_url", "")
                if url:
                    parent = self.parent_window
                    if parent and hasattr(parent, 'open_stream_player'):
                        parent.open_stream_player(url)
                        self.status_label.setText("已打开回放播放器")
                    else:
                        from PyQt5.QtWidgets import QApplication
                        QApplication.clipboard().setText(url)
                        QMessageBox.information(self, "提示", "播放器未加载，URL已复制到剪贴板")
                return

            # 更新画质选择
            self.quality_combo.clear()
            quality_desc = data.get("quality_description", [])
            for q in quality_desc:
                qn = q.get("qn", "")
                desc = q.get("desc", "")
                self.quality_combo.addItem(f"{desc} ({qn})", qn)

            # 显示流URL
            stream_urls = data.get("stream_urls", [])
            if stream_urls:
                url_text = "\n".join(f"[线路{u.get('order', 0)+1}] {u['url']}" for u in stream_urls)
                self.stream_url_text.setPlainText(url_text)
                self._current_stream_url = stream_urls[0]["url"]
                self.status_label.setText("获取成功，自动打开播放器...")
                # 自动打开流媒体播放器
                QTimer.singleShot(200, self._play_in_stream_player)
            else:
                self.stream_url_text.setPlainText("未获取到直播流URL")
                self.status_label.setText("未获取到直播流")
        except Exception as e:
            logger.exception("显示直播流失败")
            self.status_label.setText(f"显示失败: {e}")

    def _copy_stream_url(self):
        """复制流URL到剪贴板"""
        url = getattr(self, '_current_stream_url', '')
        if not url:
            QMessageBox.warning(self, "提示", "没有可复制的URL")
            return
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(url)
        self.status_label.setText("URL已复制到剪贴板")

    def _play_in_stream_player(self):
        """在流媒体播放器中查看"""
        url = getattr(self, '_current_stream_url', '')
        if not url:
            QMessageBox.warning(self, "提示", "请先获取直播流URL")
            return
        # 调用主窗口打开流媒体播放器弹窗，传入URL刷新回调
        parent = self.parent_window
        if parent and hasattr(parent, 'open_stream_player'):
            # 回调函数：重新获取最新的直播流URL（解决B站流URL过期问题）
            def refresher():
                try:
                    room_id = getattr(self, '_room_id', '')
                    if not room_id:
                        return None
                    # 同步调用API获取最新流URL
                    result = self.live_parser.get_live_stream_url(room_id, platform="h5")
                    if result.get("success"):
                        urls = result.get("data", {}).get("stream_urls", [])
                        if urls:
                            new_url = urls[0]["url"]
                            self._current_stream_url = new_url  # 更新缓存
                            return new_url
                    return None
                except Exception as e:
                    logger.warning(f"[live_tab] 刷新直播流URL失败: {e}")
                    return None
            parent.open_stream_player(url, url_refresher=refresher)
            self.status_label.setText("已打开流媒体播放器")
        else:
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(url)
            QMessageBox.information(self, "提示", "流媒体播放器未加载，URL已复制到剪贴板")

    # ==================== Tab 2: 直播录制 ====================

    def _create_record_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(scale(4))
        layout.setContentsMargins(scale(4), scale(4), scale(4), scale(4))

        # 录制设置
        settings_group = QGroupBox("录制设置")
        settings_group.setStyleSheet(scale_style(self._GB))
        settings_layout = QGridLayout(settings_group)
        settings_layout.setSpacing(scale(4))
        settings_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        settings_layout.addWidget(QLabel("房间号:"), 0, 0)
        self.record_room_input = QLineEdit()
        self.record_room_input.setPlaceholderText("直播间房间号")
        self.record_room_input.setMinimumHeight(scale(28))
        self.record_room_input.setStyleSheet(scale_style("padding: 2px 6px;"))
        settings_layout.addWidget(self.record_room_input, 0, 1)

        settings_layout.addWidget(QLabel("流格式:"), 0, 2)
        self.format_combo = QComboBox()
        self.format_combo.addItem("HLS (m3u8)", "hls")
        self.format_combo.addItem("FLV (http-flv)", "flv")
        self.format_combo.setMinimumHeight(scale(26))
        settings_layout.addWidget(self.format_combo, 0, 3)

        settings_layout.addWidget(QLabel("画质:"), 1, 0)
        self.record_quality_combo = QComboBox()
        self.record_quality_combo.addItem("原画（最高）", 10000)
        self.record_quality_combo.addItem("蓝光", 400)
        self.record_quality_combo.addItem("超清", 250)
        self.record_quality_combo.addItem("高清", 150)
        self.record_quality_combo.addItem("流畅", 80)
        self.record_quality_combo.setMinimumHeight(scale(26))
        settings_layout.addWidget(self.record_quality_combo, 1, 1)

        settings_layout.addWidget(QLabel("录制时长:"), 1, 2)
        duration_layout = QHBoxLayout()
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(0, 86400)
        self.duration_spin.setSuffix(" 秒")
        self.duration_spin.setValue(0)
        self.duration_spin.setMinimumHeight(scale(26))
        self.duration_spin.setToolTip("0 = 一直录制直到手动停止")
        duration_layout.addWidget(self.duration_spin)
        self.duration_label = QLabel("(0=手动停止)")
        self.duration_label.setStyleSheet(scale_style("font-size: 10px; color: #6c757d;"))
        duration_layout.addWidget(self.duration_label)
        settings_layout.addLayout(duration_layout, 1, 3)

        settings_layout.addWidget(QLabel("保存到:"), 2, 0)
        self.save_path_input = QLineEdit()
        default_path = os.path.join(os.getcwd(), "直播录制")
        self.save_path_input.setText(default_path)
        self.save_path_input.setMinimumHeight(scale(28))
        self.save_path_input.setStyleSheet(scale_style("padding: 2px 6px;"))
        settings_layout.addWidget(self.save_path_input, 2, 1, 1, 2)

        self.browse_btn = QPushButton("浏览...")
        self.browse_btn.setMinimumHeight(scale(26))
        self.browse_btn.clicked.connect(self._browse_save_path)
        settings_layout.addWidget(self.browse_btn, 2, 3)

        layout.addWidget(settings_group)

        # 录制控制
        control_layout = QHBoxLayout()
        control_layout.setSpacing(scale(4))
        self.start_record_btn = QPushButton("开始录制")
        self.start_record_btn.setStyleSheet(scale_style(
            "padding: 4px 14px; background-color: #dc3545; color: white; border: none; border-radius: 3px; font-size: 12px; font-weight: bold;"))
        self.start_record_btn.setMinimumHeight(scale(28))
        self.start_record_btn.clicked.connect(self._start_recording)
        control_layout.addWidget(self.start_record_btn)

        self.pause_record_btn = QPushButton("暂停")
        self.pause_record_btn.setStyleSheet(scale_style(
            "padding: 4px 10px; background-color: #ffc107; color: #333; border: none; border-radius: 3px; font-size: 12px;"))
        self.pause_record_btn.setMinimumHeight(scale(28))
        self.pause_record_btn.clicked.connect(self._pause_recording)
        self.pause_record_btn.setEnabled(False)
        control_layout.addWidget(self.pause_record_btn)

        self.stop_record_btn = QPushButton("停止录制")
        self.stop_record_btn.setStyleSheet(scale_style(
            "padding: 4px 14px; background-color: #6c757d; color: white; border: none; border-radius: 3px; font-size: 12px;"))
        self.stop_record_btn.setMinimumHeight(scale(28))
        self.stop_record_btn.clicked.connect(self._stop_recording)
        self.stop_record_btn.setEnabled(False)
        control_layout.addWidget(self.stop_record_btn)

        control_layout.addStretch()
        layout.addLayout(control_layout)

        # 录制状态
        status_group = QGroupBox("录制状态")
        status_group.setStyleSheet(scale_style(self._GB))
        status_layout = QVBoxLayout(status_group)
        status_layout.setSpacing(scale(4))
        status_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        self.record_status_label = QLabel("未开始录制")
        self.record_status_label.setStyleSheet(scale_style("font-size: 12px; font-weight: bold; color: #6c757d;"))
        self.record_status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.record_status_label)

        self.record_time_label = QLabel("00:00:00")
        self.record_time_label.setStyleSheet(scale_style("font-size: 20px; font-weight: bold; color: #00a1d6;"))
        self.record_time_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.record_time_label)

        self.record_progress = QProgressBar()
        self.record_progress.setRange(0, 100)
        status_layout.addWidget(self.record_progress)

        layout.addWidget(status_group)
        layout.addStretch()
        return tab

    def _browse_save_path(self):
        """浏览保存路径"""
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_path_input.text())
        if path:
            self.save_path_input.setText(path)

    def _start_recording(self):
        """开始录制（持续录制模式，后台进行）"""
        room_id = self.record_room_input.text().strip()
        if not room_id:
            QMessageBox.warning(self, "提示", "请输入房间号")
            return

        save_path = self.save_path_input.text().strip()
        if not save_path or not os.path.isdir(save_path):
            QMessageBox.warning(self, "提示", "请选择有效的保存目录")
            return

        if not self.live_parser:
            QMessageBox.warning(self, "提示", "直播解析器未初始化")
            return

        self.start_record_btn.setEnabled(False)
        self.pause_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(True)
        self.record_status_label.setText("正在获取直播流...")
        self.record_time_label.setText("00:00:00")
        self.record_progress.setValue(0)

        format_type = self.format_combo.currentData()
        qn = self.record_quality_combo.currentData()
        duration = self.duration_spin.value()

        def worker():
            # 1. 获取真实房间号
            init_result = self.live_parser.room_init(room_id)
            if not init_result["success"]:
                self._on_record_error(init_result.get("error", "房间号查询失败"))
                return

            real_room_id = init_result["data"]["room_id"]
            live_status = init_result["data"]["live_status"]

            if live_status != 1:
                self._on_record_error("当前未在直播中")
                return

            # 2. 获取直播流
            platform = "h5" if format_type == "hls" else "web"
            stream_result = self.live_parser.get_live_stream_url(real_room_id, platform=platform, qn=qn)
            if not stream_result["success"]:
                self._on_record_error(stream_result.get("error", "获取直播流失败"))
                return

            stream_urls = stream_result["data"].get("stream_urls", [])
            if not stream_urls:
                self._on_record_error("未获取到直播流URL")
                return

            stream_url = stream_urls[0]["url"]

            # 3. 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ext = "mp4" if format_type == "hls" else "flv"
            filename = f"live_{room_id}_{timestamp}.{ext}"
            output_path = os.path.join(save_path, filename)

            # 4. 创建URL刷新回调
            def url_refresher():
                try:
                    result = self.live_parser.get_live_stream_url(real_room_id, platform=platform, qn=qn)
                    if result.get("success"):
                        urls = result.get("data", {}).get("stream_urls", [])
                        if urls:
                            return urls[0]["url"]
                    return None
                except Exception as e:
                    logger.warning(f"[录制] 刷新URL失败: {e}")
                    return None

            # 5. 获取直播间标题（用于托盘显示）
            title = f"直播间 {room_id}"
            try:
                info_result = self.live_parser.get_room_info(real_room_id)
                if info_result.get("success"):
                    title = info_result["data"].get("title", title)
            except Exception:
                pass

            # 6. 保存到实例变量，供主线程注册托盘使用
            self._pending_record_info = {
                "room_id": room_id, "title": title,
                "output_path": output_path, "stream_url": stream_url,
                "format_type": format_type, "duration": duration,
            }

            # 7. 开始录制（主线程中会注册托盘+发送通知）
            self._start_ffmpeg_record(stream_url, output_path, format_type, duration)

        threading.Thread(target=worker, daemon=True).start()

    def _on_record_error(self, msg):
        """录制错误回调（从工作线程调用，通过信号转发到主线程）"""
        self._record_error_signal.emit(msg)

    def _on_record_error_main(self, msg):
        self.start_record_btn.setEnabled(True)
        self.pause_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(False)
        self.record_status_label.setText(f"错误: {msg}")
        self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #dc3545;"))
        self.status_label.setText(msg)
        # 清理托盘会话
        self._cleanup_recording_session()

    def _start_ffmpeg_record(self, stream_url, output_path, format_type, duration):
        """启动 ffmpeg 录制（从工作线程调用，通过信号转发到主线程）"""
        self._start_record_signal.emit(stream_url, output_path, format_type, duration)

    def _do_start_record(self, stream_url, output_path, format_type, duration):
        """主线程：启动录制线程 + 注册托盘会话 + 发送通知"""
        # 从 pending info 获取信息（后台线程 worker 中保存的）
        info = getattr(self, '_pending_record_info', {})
        room_id = info.get("room_id", self.record_room_input.text().strip())
        title = info.get("title", f"直播间 {room_id}")
        rec_output_path = info.get("output_path", output_path)

        platform = "h5" if format_type == "hls" else "web"
        qn = self.record_quality_combo.currentData()

        def url_refresher():
            try:
                if not self.live_parser:
                    return None
                init_result = self.live_parser.room_init(room_id)
                if not init_result.get("success"):
                    return None
                real_room_id = init_result["data"]["room_id"]
                result = self.live_parser.get_live_stream_url(real_room_id, platform=platform, qn=qn)
                if result.get("success"):
                    urls = result.get("data", {}).get("stream_urls", [])
                    if urls:
                        return urls[0]["url"]
                return None
            except Exception as e:
                logger.warning(f"[录制] 刷新URL失败: {e}")
                return None

        # 启动录制线程
        self.record_thread = LiveRecordThread(
            stream_url, output_path, format_type, duration,
            url_refresher=url_refresher, room_id=room_id)
        self.record_thread.status_changed.connect(self._on_record_status)
        self.record_thread.progress_updated.connect(self._on_record_progress)
        self.record_thread.record_finished.connect(self._on_record_finished)
        self.record_thread.error_occurred.connect(self._on_record_error_main)
        self.record_thread.start()
        self._record_start_time = time.time()

        # 通过父窗口注册录播工具托盘会话
        self._register_recording_to_parent(room_id, title, rec_output_path)

        # 更新UI状态
        self.record_status_label.setText("录制中（后台持续录制）")
        self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #28a745;"))

    def _register_recording_to_parent(self, room_id, title, output_path):
        """通过父窗口注册到录播工具托盘，并发送气泡通知"""
        parent = self.parent_window
        tray = getattr(parent, 'recording_tray', None) if parent else None

        if tray:
            session_id = tray.add_session(room_id=room_id, title=title, output_path=output_path)
            self._recording_session_id = session_id
            logger.info(f"[live_tab] 已注册托盘会话: {session_id}")
            # 气泡通知用户
            tray.notify(
                "录播工具",
                f"正在录制「{title}」\n点击托盘图标可查看状态和控制",
                QSystemTrayIcon.Information)
        else:
            # 父窗口没有录播工具，用普通弹窗提示
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "提示",
                "录制已在后台开始进行！\n\n关闭直播页面不影响录制，"
                "可通过系统托盘的「录播工具」图标控制。")

    def _cleanup_recording_session(self):
        """清理当前录制会话（从父窗口托盘中移除）"""
        sid = self._recording_session_id
        if not sid:
            return
        parent = self.parent_window
        tray = getattr(parent, 'recording_tray', None) if parent else None
        if tray:
            tray.remove_session(sid)
        self._recording_session_id = None

    def _on_record_status(self, status):
        self.record_status_label.setText(status)
        self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #00a1d6;"))
        self.status_label.setText(status)

    def _on_record_progress(self, seconds, time_str):
        self.record_time_label.setText(time_str)
        # 如果有设定时长，更新进度条
        if hasattr(self, '_record_start_time') and self.duration_spin.value() > 0:
            total = self.duration_spin.value()
            pct = min(int(seconds * 100 / total), 100)
            self.record_progress.setValue(pct)

    def _on_record_finished(self, success, msg):
        self.start_record_btn.setEnabled(True)
        self.pause_record_btn.setEnabled(False)
        self.pause_record_btn.setText("暂停")
        self.stop_record_btn.setEnabled(False)
        if success:
            self.record_status_label.setText(msg)
            self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #28a745;"))
        else:
            self.record_status_label.setText(msg)
            self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #dc3545;"))
        self.status_label.setText(msg)
        # 清理托盘会话
        self._cleanup_recording_session()

    def _stop_recording(self):
        """停止录制"""
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()
            self.stop_record_btn.setEnabled(False)
            self.pause_record_btn.setEnabled(False)
            self.record_status_label.setText("正在停止...")
        else:
            QMessageBox.information(self, "提示", "没有正在进行的录制")

    def _pause_recording(self):
        """暂停/继续录制"""
        if not self.record_thread or not self.record_thread.isRunning():
            return
        if self.pause_record_btn.text() == "暂停":
            self.record_thread.pause()
            self.pause_record_btn.setText("继续")
            self.pause_record_btn.setStyleSheet(scale_style(
                "padding: 10px 20px; background-color: #28a745; color: white; border: none; border-radius: 4px; font-size: 14px;"))
            self.record_status_label.setText("已暂停")
            self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #ffc107;"))
            # 同步托盘状态
            sid = self._recording_session_id
            parent = self.parent_window
            if sid and parent:
                tray = getattr(parent, 'recording_tray', None)
                if tray:
                    tray.pause_session(sid)
        else:
            self.record_thread.resume()
            self.pause_record_btn.setText("暂停")
            self.pause_record_btn.setStyleSheet(scale_style(
                "padding: 10px 20px; background-color: #ffc107; color: #333; border: none; border-radius: 4px; font-size: 14px;"))
            self.record_status_label.setText("录制中（后台持续录制）")
            self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #28a745;"))
            # 同步托盘状态
            sid = self._recording_session_id
            parent = self.parent_window
            if sid and parent:
                tray = getattr(parent, 'recording_tray', None)
                if tray:
                    tray.resume_session(sid)

    # ==================== 外部控制接口（供父窗口调用） ====================

    def handle_tray_stop(self, session_id):
        """父窗口转发的：托盘请求停止录制"""
        if self._recording_session_id == session_id and self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()
            self.stop_record_btn.setEnabled(False)
            self.pause_record_btn.setEnabled(False)
            self.record_status_label.setText("正在停止...")

    def handle_tray_pause(self, session_id):
        """父窗口转发的：托盘请求暂停录制"""
        if self._recording_session_id == session_id:
            if self.record_thread and self.record_thread.isRunning():
                self.record_thread.pause()
                self.pause_record_btn.setText("继续")
                self.pause_record_btn.setStyleSheet(scale_style(
                    "padding: 10px 20px; background-color: #28a745; color: white; border: none; border-radius: 4px; font-size: 14px;"))
                self.record_status_label.setText("已暂停")
                self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #ffc107;"))

    def handle_tray_resume(self, session_id):
        """父窗口转发的：托盘请求继续录制"""
        if self._recording_session_id == session_id:
            if self.record_thread and self.record_thread.isRunning():
                self.record_thread.resume()
                self.pause_record_btn.setText("暂停")
                self.pause_record_btn.setStyleSheet(scale_style(
                    "padding: 10px 20px; background-color: #ffc107; color: #333; border: none; border-radius: 4px; font-size: 14px;"))
                self.record_status_label.setText("录制中（后台持续录制）")
                self.record_status_label.setStyleSheet(scale_style("font-size: 14px; font-weight: bold; color: #28a745;"))

    # ==================== Tab 3: 回放下载 ====================

    def _create_replay_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(scale(4))
        layout.setContentsMargins(scale(4), scale(4), scale(4), scale(4))

        # 回放列表
        list_group = QGroupBox("直播回放列表")
        list_group.setStyleSheet(scale_style(self._GB))
        list_layout = QVBoxLayout(list_group)
        list_layout.setSpacing(scale(4))
        list_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(scale(4))
        self.refresh_replay_btn = QPushButton("刷新回放列表")
        self.refresh_replay_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #00a1d6; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.refresh_replay_btn.setMinimumHeight(scale(26))
        self.refresh_replay_btn.clicked.connect(self._load_replay_list)
        btn_layout.addWidget(self.refresh_replay_btn)

        self.load_other_replay_btn = QPushButton("查询他人回放")
        self.load_other_replay_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #17a2b8; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.load_other_replay_btn.setMinimumHeight(scale(26))
        self.load_other_replay_btn.clicked.connect(self._load_other_replay)
        btn_layout.addWidget(self.load_other_replay_btn)

        btn_layout.addStretch()
        list_layout.addLayout(btn_layout)

        self.replay_table = QTableWidget(0, 6)
        self.replay_table.setHorizontalHeaderLabels(["标题", "直播时间", "时长", "状态", "回放ID", "操作"])
        self.replay_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.replay_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.replay_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.replay_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.replay_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.replay_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.replay_table.setAlternatingRowColors(True)
        self.replay_table.setEditTriggers(QTableWidget.NoEditTriggers)
        list_layout.addWidget(self.replay_table)

        layout.addWidget(list_group)

        # 下载设置
        dl_settings_group = QGroupBox("下载设置")
        dl_settings_group.setStyleSheet(scale_style(self._GB))
        dl_settings_layout = QHBoxLayout(dl_settings_group)
        dl_settings_layout.setSpacing(scale(4))
        dl_settings_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        dl_settings_layout.addWidget(QLabel("保存到:"))
        self.replay_save_path_input = QLineEdit()
        default_replay_path = os.path.join(os.getcwd(), "回放下载")
        self.replay_save_path_input.setText(default_replay_path)
        self.replay_save_path_input.setMinimumHeight(scale(28))
        self.replay_save_path_input.setStyleSheet(scale_style("padding: 2px 6px;"))
        dl_settings_layout.addWidget(self.replay_save_path_input, stretch=1)

        self.replay_browse_btn = QPushButton("浏览...")
        self.replay_browse_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #6c757d; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.replay_browse_btn.setMinimumHeight(scale(26))
        self.replay_browse_btn.clicked.connect(self._browse_replay_save_path)
        dl_settings_layout.addWidget(self.replay_browse_btn)

        layout.addWidget(dl_settings_group)

        # 下载状态
        dl_group = QGroupBox("下载状态")
        dl_group.setStyleSheet(scale_style(self._GB))
        dl_layout = QVBoxLayout(dl_group)
        dl_layout.setSpacing(scale(4))
        dl_layout.setContentsMargins(scale(4), scale(8), scale(4), scale(4))

        self.replay_dl_status = QLabel("就绪")
        self.replay_dl_status.setStyleSheet(scale_style("font-size: 11px; color: #6c757d;"))
        dl_layout.addWidget(self.replay_dl_status)

        progress_layout = QHBoxLayout()
        self.replay_dl_progress = QProgressBar()
        progress_layout.addWidget(self.replay_dl_progress)

        self.replay_cancel_btn = QPushButton("取消下载")
        self.replay_cancel_btn.setStyleSheet(scale_style(
            "padding: 2px 8px; background-color: #dc3545; color: white; border: none; border-radius: 3px; font-size: 11px;"))
        self.replay_cancel_btn.setMinimumHeight(scale(26))
        self.replay_cancel_btn.clicked.connect(self._cancel_replay_download)
        self.replay_cancel_btn.setEnabled(False)
        progress_layout.addWidget(self.replay_cancel_btn)

        dl_layout.addLayout(progress_layout)

        layout.addWidget(dl_group)
        layout.addStretch()
        return tab

    def _load_replay_list(self):
        """加载自己的回放列表"""
        if not self.live_parser:
            QMessageBox.warning(self, "提示", "直播解析器未初始化")
            return

        # 刷新Cookie确保使用最新登录状态
        self._refresh_cookies()

        self.refresh_replay_btn.setEnabled(False)
        self.status_label.setText("正在获取回放列表...")

        def worker():
            result = self.live_parser.get_replay_list(page=1, page_size=30)
            self._replay_list_signal.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    def _on_replay_list_loaded(self, result):
        self.refresh_replay_btn.setEnabled(True)
        if not result["success"]:
            self.status_label.setText(f"获取失败: {result.get('error')}")
            QMessageBox.warning(self, "提示", f"获取回放列表失败: {result.get('error')}")
            return

        replay_list = result["data"]["replay_list"]
        self.replay_table.setRowCount(0)
        self._replay_data = {}

        if not replay_list:
            self.status_label.setText("没有回放记录")
            return

        for i, replay in enumerate(replay_list):
            self.replay_table.insertRow(i)
            self.replay_table.setItem(i, 0, QTableWidgetItem(replay.get("title", "未知")))
            self.replay_table.setItem(i, 1, QTableWidgetItem(replay.get("live_time", "-")))

            duration = replay.get("duration", 0)
            duration_str = f"{duration//60}分{duration%60}秒" if duration > 0 else "-"
            self.replay_table.setItem(i, 2, QTableWidgetItem(duration_str))

            status = replay.get("replay_status", 0)
            status_map = {0: "未生成", 2: "已完成", 30: "合成中"}
            self.replay_table.setItem(i, 3, QTableWidgetItem(status_map.get(status, str(status))))

            replay_id = replay.get("replay_id", "")
            self.replay_table.setItem(i, 4, QTableWidgetItem(str(replay_id)))

            # 操作按钮（下载 + 播放）
            btn_widget = QWidget()
            btn_layout_cell = QHBoxLayout(btn_widget)
            btn_layout_cell.setContentsMargins(scale(2), scale(2), scale(2), scale(2))
            btn_layout_cell.setSpacing(scale(4))

            dl_video_btn = QPushButton("下载画面")
            dl_video_btn.setStyleSheet(scale_style(
                "padding: 2px 8px; background-color: #17a2b8; color: white; border: none; border-radius: 3px; font-size: 12px;"))
            dl_video_btn.clicked.connect(lambda checked, r=replay: self._download_replay(r, 2))
            btn_layout_cell.addWidget(dl_video_btn)

            dl_audio_btn = QPushButton("下载音频")
            dl_audio_btn.setStyleSheet(scale_style(
                "padding: 2px 8px; background-color: #fd7e14; color: white; border: none; border-radius: 3px; font-size: 12px;"))
            dl_audio_btn.clicked.connect(lambda checked, r=replay: self._download_replay(r, 1))
            btn_layout_cell.addWidget(dl_audio_btn)

            dl_btn = QPushButton("下载完整视频")
            dl_btn.setStyleSheet(scale_style(
                "padding: 2px 8px; background-color: #28a745; color: white; border: none; border-radius: 3px; font-size: 12px;"))
            dl_btn.clicked.connect(lambda checked, r=replay: self._download_replay(r, 0))
            btn_layout_cell.addWidget(dl_btn)

            play_btn = QPushButton("播放")
            play_btn.setStyleSheet(scale_style(
                "padding: 2px 10px; background-color: #e6a23c; color: white; border: none; border-radius: 3px; font-size: 12px;"))
            play_btn.clicked.connect(lambda checked, r=replay: self._play_replay(r))
            btn_layout_cell.addWidget(play_btn)

            self.replay_table.setCellWidget(i, 5, btn_widget)

            self._replay_data[replay_id] = replay

        self.status_label.setText(f"共 {len(replay_list)} 条回放记录")

    def _extract_uid_from_text(self, text):
        """从UID数字或B站主页链接中提取UID"""
        text = text.strip()
        if not text:
            return None
        # 纯数字UID
        if text.isdigit():
            return int(text)
        # 从 space.bilibili.com/xxx 链接提取
        import re
        match = re.search(r'space\.bilibili\.com/(\d+)', text)
        if match:
            return int(match.group(1))
        # 从 live.bilibili.com/xxx 链接提取
        match = re.search(r'live\.bilibili\.com/(\d+)', text)
        if match:
            return int(match.group(1))
        # 从短链接 b23.tv/xxx 暂不处理
        return None

    def _load_other_replay(self):
        """查询他人回放（支持UID数字或主页链接）"""
        from PyQt5.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "查询他人回放", "请输入主播UID或主页链接:")
        if not ok or not text.strip():
            return

        uid = self._extract_uid_from_text(text.strip())
        if uid is None:
            QMessageBox.warning(self, "提示", "无法识别输入内容，请输入数字UID或B站主页链接\n例如：https://space.bilibili.com/123456")
            return

        # 刷新Cookie确保使用最新登录状态
        self._refresh_cookies()

        self.load_other_replay_btn.setEnabled(False)
        self.status_label.setText(f"正在获取主播 {uid} 的回放列表...")

        def worker():
            result = self.live_parser.get_other_replay_list(uid, time_range=3)
            self._replay_list_signal.emit(result)

        threading.Thread(target=worker, daemon=True).start()

    def _download_replay(self, replay_info, content_type=0):
        """下载回放"""
        replay_id = replay_info.get("replay_id")
        live_key = replay_info.get("live_key", "")
        title = replay_info.get("title", f"replay_{replay_id}")

        if not replay_id and not live_key:
            QMessageBox.warning(self, "提示", "缺少回放ID或直播key")
            return

        # 检查是否已有下载在进行
        if self.replay_download_thread and self.replay_download_thread.isRunning():
            QMessageBox.warning(self, "提示", "已有回放在下载中，请等待完成或取消当前下载")
            return

        # 使用保存路径设置
        save_dir = self.replay_save_path_input.text().strip()
        if not save_dir or not os.path.isdir(save_dir):
            save_dir = os.path.join(os.getcwd(), "回放下载")
            os.makedirs(save_dir, exist_ok=True)
            self.replay_save_path_input.setText(save_dir)

        # 清理文件名中的非法字符
        safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)
        if content_type == 1:
            ext = "m4a"
        elif content_type == 2:
            ext = "mp4"
        else:
            ext = "mp4"
        save_path = os.path.join(save_dir, f"{safe_title}.{ext}")

        self.replay_dl_status.setText("正在请求回放下载链接...")
        self.replay_dl_progress.setValue(0)
        self.replay_cancel_btn.setEnabled(True)

        def worker():
            # 请求下载链接
            result = self.live_parser.request_replay_download(
                record_id=replay_id, live_key=live_key)
            self._replay_url_signal.emit(result, save_path, title, content_type)

        threading.Thread(target=worker, daemon=True).start()

    def _play_replay(self, replay_info):
        """在流媒体播放器中播放回放"""
        replay_id = replay_info.get("replay_id")
        live_key = replay_info.get("live_key", "")
        title = replay_info.get("title", "回放")

        if not replay_id and not live_key:
            QMessageBox.warning(self, "提示", "缺少回放ID或直播key")
            return

        self.status_label.setText("正在获取回放播放链接...")

        def worker():
            try:
                result = self.live_parser.request_replay_download(
                    record_id=replay_id, live_key=live_key)
                if not result["success"]:
                    self._error_signal.emit(f"获取回放链接失败: {result.get('error')}")
                    return

                data = result["data"]
                if data.get("is_processing"):
                    self._error_signal.emit("回放正在合成中，请稍后再试")
                    return

                download_url = data.get("download_url", "")
                url_list = data.get("download_url_list", [])
                if not download_url and url_list:
                    download_url = url_list[0] if isinstance(url_list, list) else str(url_list)

                if not download_url:
                    self._error_signal.emit("未获取到回放播放链接")
                    return

                # 通过信号在主线程中打开播放器
                self._stream_done_signal.emit(True, {"stream_url": download_url, "for_playback": True})
            except Exception as e:
                self._error_signal.emit(f"获取回放链接失败: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _on_replay_url_ready(self, result, save_path, title, content_type=0):
        if not result["success"]:
            self.replay_dl_status.setText(f"请求失败: {result.get('error')}")
            self.replay_cancel_btn.setEnabled(False)
            return

        data = result["data"]
        if data.get("is_processing"):
            estimated = data.get("estimated_time", 0)
            current = data.get("current_time", 0)
            wait_sec = max(estimated - current, 0)
            self.replay_dl_status.setText(
                f"回放正在合成中，预计还需 {wait_sec} 秒，请稍后重试")
            self.replay_cancel_btn.setEnabled(False)
            # 自动等待重试
            if wait_sec > 0 and wait_sec <= 300:
                QTimer.singleShot((wait_sec + 5) * 1000, lambda: self._auto_retry_replay(save_path, title))
            return

        download_url = data.get("download_url", "")
        url_list = data.get("download_url_list", [])

        if not download_url and url_list:
            download_url = url_list[0] if isinstance(url_list, list) else str(url_list)

        if not download_url:
            self.replay_dl_status.setText("未获取到下载链接")
            self.replay_cancel_btn.setEnabled(False)
            return

        # 判断是否需要用ffmpeg下载（m3u8链接用ffmpeg）
        use_ffmpeg = '.m3u8' in download_url or 'm3u8' in download_url.lower()

        # 开始下载
        self.replay_dl_status.setText("开始下载...")
        self.replay_download_thread = ReplayDownloadThread(download_url, save_path, use_ffmpeg=use_ffmpeg, content_type=content_type)
        self.replay_download_thread.progress_updated.connect(self._on_replay_dl_progress)
        self.replay_download_thread.download_finished.connect(self._on_replay_dl_finished)
        self.replay_download_thread.error_occurred.connect(self._on_replay_dl_error)
        self.replay_download_thread.start()

    def _auto_retry_replay(self, save_path, title):
        """自动重试回放下载（合成完成后）"""
        if self.replay_download_thread and self.replay_download_thread.isRunning():
            return  # 已有下载在进行
        self.replay_dl_status.setText("自动重试获取回放下载链接...")
        # 这里只是提示用户，实际需要重新点击下载
        self.replay_dl_status.setText("回放可能已合成完成，请重新点击下载")

    def _on_replay_dl_progress(self, pct, status):
        if pct >= 0:
            self.replay_dl_progress.setValue(pct)
        self.replay_dl_status.setText(status)

    def _on_replay_dl_finished(self, success, msg):
        self.replay_cancel_btn.setEnabled(False)
        if success:
            self.replay_dl_progress.setValue(100)
            self.replay_dl_status.setText(msg)
            self.status_label.setText("回放下载完成")
        else:
            self.replay_dl_status.setText(msg)

    def _on_replay_dl_error(self, msg):
        self.replay_cancel_btn.setEnabled(False)
        self.replay_dl_status.setText(f"下载错误: {msg}")

    def _cancel_replay_download(self):
        """取消回放下载"""
        if self.replay_download_thread and self.replay_download_thread.isRunning():
            self.replay_download_thread.stop()
            self.replay_cancel_btn.setEnabled(False)
            self.replay_dl_status.setText("正在取消下载...")

    def _browse_replay_save_path(self):
        """浏览回放保存路径"""
        path = QFileDialog.getExistingDirectory(self, "选择保存目录", self.replay_save_path_input.text())
        if path:
            self.replay_save_path_input.setText(path)

    # ==================== 清理 ====================

    def cleanup(self):
        """清理资源（注意：不清理托盘，托盘归父窗口管理）"""
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()
            self.record_thread.wait(3000)
        if self.replay_download_thread and self.replay_download_thread.isRunning():
            self.replay_download_thread.stop()
            self.replay_download_thread.wait(3000)
