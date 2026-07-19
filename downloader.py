import os
import re
import time
import threading
import shutil
from datetime import datetime
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QMutex, QWaitCondition
from utils import get_unique_filename
from platform_utils import IS_MACOS, IS_WINDOWS, illegal_filename_chars

try:
    from logger_config import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

from bilibili_parser import BilibiliParser
from typing import Tuple
Task = Tuple[int, dict]


class EpisodeDownloadThread(QThread):
    progress_updated = pyqtSignal(int, int, str)
    episode_finished = pyqtSignal(int, bool, str)
    thread_destroyed = pyqtSignal()
    merge_started = pyqtSignal(int)
    merge_finished = pyqtSignal(int)

    def __init__(self, ep_index, ep_info, video_info, selected_qn, save_path, parser, config=None):
        super().__init__()
        self.ep_index = ep_index
        self.ep_info = ep_info
        self.video_info = video_info
        self.selected_qn = selected_qn
        self.save_path = save_path
        self.parser = parser
        self.config = config
        self._is_running = True
        self.ep_title = f"第{ep_index+1}集_未知标题"
        self.temp_files = []
        self._mutex = QMutex()
        self.audio_quality = self.config.get_app_setting("audio_quality", 0) if self.config else 0
        self.video_process_mode = self.config.get_app_setting("video_process_mode", "copy") if self.config else "copy"
        _AQ_NAMES = {0: "自动（最高音质）", 30251: "Hi-Res无损", 30250: "杜比全景声", 100010: "320K高音质", 30280: "192K高音质", 100009: "192K标准音质", 30232: "132K标准音质", 100008: "128K标准音质", 30216: "64K低音质"}
        logger.info(f"线程{ep_index}：开始下载，音频质量：{_AQ_NAMES.get(self.audio_quality, f'音质({self.audio_quality})')}")

    @property
    def is_running(self):
        self._mutex.lock()
        val = self._is_running
        self._mutex.unlock()
        return val

    @is_running.setter
    def is_running(self, value):
        self._mutex.lock()
        self._is_running = value
        self._mutex.unlock()
        logger.debug(f"线程{self.ep_index}：状态变为{value}")

    def run(self):
        logger.info(f"线程{self.ep_index}：开始下载")
        try:
            self._init_ep_title()
            self._check_save_path()
            self.progress_updated.emit(self.ep_index, 0, "准备下载...")

            if not self.is_running:
                raise Exception("下载已取消")

            bvid = self.video_info.get('bvid', self.ep_info.get('bvid', ''))
            video_url, audio_url, kid = self._get_media_urls_with_retry(bvid, self.ep_info)
            if not video_url:
                raise Exception("无有效视频链接")

            # 并行下载video和audio流（不同CDN URL，互不限速）
            video_path = None
            audio_path = None
            has_audio = bool(audio_url)

            if has_audio:
                self._video_progress = 0
                self._audio_progress = 0
                self._progress_lock = threading.Lock()

                def _dl_video():
                    nonlocal video_path
                    video_path = self._download_media_with_retry(
                        video_url, "video", bvid, 0, kid,
                        stream_type='video', stream_weight=0.5
                    )

                def _dl_audio():
                    nonlocal audio_path
                    audio_path = self._download_media_with_retry(
                        audio_url, "audio", bvid, 0, kid,
                        stream_type='audio', stream_weight=0.5
                    )

                with ThreadPoolExecutor(max_workers=2) as executor:
                    v_future = executor.submit(_dl_video)
                    a_future = executor.submit(_dl_audio)
                    for f in as_completed([v_future, a_future]):
                        try:
                            f.result()
                        except Exception:
                            raise
            else:
                video_path = self._download_media_with_retry(video_url, "video", bvid, 0, kid)

            if not video_path or not self.is_running:
                return
            if has_audio and not audio_path:
                return

            if self.is_running:
                self._merge_media(video_path, audio_path, kid)

        except Exception as e:
            err_msg = str(e)
            if "Remote end closed" in err_msg or "Read timed out" in err_msg:
                err_msg += "（网络问题，已自动重试）"
            if "ffmpeg" in err_msg.lower():
                err_msg += "（检查FFmpeg环境变量）"
            if "下载已取消" in err_msg:
                err_msg = "下载已取消"
            logger.error(f"线程{self.ep_index}：下载失败 - {err_msg}")
            self.episode_finished.emit(self.ep_index, False, err_msg)
        finally:
            self.msleep(50)
            self._clean_temp_files()
            logger.info(f"线程{self.ep_index}：下载结束")
            self.thread_destroyed.emit()
            self.deleteLater()

    def _init_ep_title(self):
        try:
            if self.video_info.get('is_bangumi') and self.video_info.get('bangumi_info'):
                season = self.video_info['bangumi_info'].get('season_title', '未知季度')
                ep_idx = self.ep_info.get('ep_index', '未知集')
                title_candidates = [
                    self.ep_info.get('ep_title', ''),
                    self.ep_info.get('title', ''),
                    self.ep_info.get('name', '')
                ]
                actual_title = next((t for t in title_candidates if t), '')
                if actual_title:
                    self.ep_title = f"{season}_{ep_idx}_{actual_title}"
                else:
                    self.ep_title = f"{season}_{ep_idx}"
            elif self.video_info.get('is_cheese'):
                title_candidates = [
                    self.ep_info.get('ep_title', ''),
                    self.ep_info.get('title', ''),
                    self.ep_info.get('name', '')
                ]
                actual_title = next((t for t in title_candidates if t), '')
                if actual_title:
                    self.ep_title = actual_title
                else:
                    self.ep_title = f"第{self.ep_index+1}集"
            else:
                # 普通视频使用视频标题
                title_candidates = [
                    self.ep_info.get('title', ''),
                    self.video_info.get('title', ''),
                    self.ep_info.get('name', '')
                ]
                actual_title = next((t for t in title_candidates if t), '')
                if actual_title:
                    import re as _re
                    actual_title = _re.sub(r'^\s*│\s*', '', actual_title)
                    actual_title = _re.sub(r'^P\d+\s*-\s*', '', actual_title)
                    if actual_title:
                        self.ep_title = actual_title
                    else:
                        self.ep_title = f"第{self.ep_index+1}集"
                else:
                    self.ep_title = f"第{self.ep_index+1}集"
            for c in illegal_filename_chars():
                self.ep_title = self.ep_title.replace(c, '_')
            self.ep_title = self.ep_title[:30]
        except Exception as e:
            logger.error(f"标题初始化错误: {e}")
            self.ep_title = f"第{self.ep_index+1}集"

    def _check_save_path(self):
        try:
            if not self.save_path or not isinstance(self.save_path, str):
                raise Exception("保存路径不能为空")

            self.save_path = os.path.normpath(self.save_path)

            if not self.save_path or len(self.save_path.strip()) == 0:
                default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
                self.save_path = default_path
                logger.warning(f"保存路径无效，使用默认路径: {self.save_path}")

            if not os.path.exists(self.save_path):
                os.makedirs(self.save_path, exist_ok=True)

            # 测试写入权限 - 使用UUID确保文件名唯一，避免多线程冲突
            import uuid
            test_file = os.path.join(self.save_path, f"permission_test_{uuid.uuid4().hex[:8]}.tmp")
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                raise Exception(f"没有权限写入到保存路径: {str(e)}")
                
        except Exception as e:
            error_msg = f"保存路径验证失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    def _get_media_urls_with_retry(self, bvid, ep_info):
        retry_count = 0
        max_retry = self.config.get_app_setting("max_retry", 3) if self.config else 3
        while self.is_running:
            try:
                return self._get_media_urls(bvid, ep_info)
            except Exception as e:
                error_str = str(e)
                if any(keyword in error_str for keyword in ["Remote end closed", "Read timed out", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"线程{self.ep_index}：获取链接失败，{delay}秒后重试")
                    self.progress_updated.emit(self.ep_index, 0, f"网络错误，{delay}秒后重试...")
                    self.msleep(delay*1000)
                    continue
                elif any(keyword in error_str for keyword in ["403", "访问权限不足"]):

                    logger.error(f"线程{self.ep_index}：权限不足，无法下载")
                    raise
                elif "下载已取消" in error_str:
                    raise
                else:
                    retry_count += 1
                    if retry_count <= max_retry:
                        delay = min(retry_count, 3)
                        logger.warning(f"线程{self.ep_index}：发生错误，{delay}秒后重试")
                        self.msleep(delay*1000)
                        continue
                    else:
                        raise

    def _get_media_urls(self, bvid, ep_info):
        video_url = ""
        audio_url = ""
        kid = None
        try:
            if self.video_info.get('is_bangumi'):
                play_info = self.parser.get_bangumi_episode_playinfo(
                    bvid=self.ep_info.get('bvid', bvid),
                    cid=self.ep_info.get('cid', ''),
                    quality=self.selected_qn,
                    ep_id=self.ep_info.get('ep_id', '')
                )
                if not play_info.get('success'):
                    error = play_info.get('error', '番剧API失败')
                    if "访问权限不足" in error:
                        raise Exception("访问权限不足")
                    raise Exception(error)
                video_url = play_info.get('video_url', '')
                audio_url = play_info.get('audio_url', '')
                if not kid:
                    play_info_full = self.parser._get_play_info(
                        'bangumi',
                        bvid=self.ep_info.get('bvid', bvid),
                        cid=self.ep_info.get('cid', ''),
                        is_tv_mode=self.video_info.get('is_tv_mode', False),
                        ep_id=self.ep_info.get('ep_id', ''),
                        audio_quality=self.audio_quality
                    )
                    kid = play_info_full.get('kid', None)
            elif self.video_info.get('is_cheese'):
                video_urls = self.ep_info.get('video_urls', {})
                if not video_urls:
                    
                    season_id = self.ep_info.get('season_id', self.video_info.get('season_id', ''))
                    ep_id = self.ep_info.get('ep_id', '')
                    cid = self.ep_info.get('cid', '')
                    bvid = self.ep_info.get('bvid', bvid)
                    play_info = self.parser._get_play_info(
                        'cheese', 
                        bvid, 
                        cid, 
                        self.video_info.get('is_tv_mode', False),
                        season_id=season_id,
                        ep_id=ep_id,
                        audio_quality=self.audio_quality
                    )
                    if not play_info['success']:
                        error = play_info.get('error', '课程API失败')
                        if "访问权限不足" in error:
                            raise Exception("访问权限不足")
                        raise Exception(error)
                    video_urls = play_info['video_urls']
                    audio_url = play_info.get('audio_url', '')
                    kid = play_info.get('kid', None)
                    self.ep_info['video_urls'] = video_urls
                    self.ep_info['audio_url'] = audio_url
                    self.ep_info['kid'] = kid
                else:
                    audio_url = self.ep_info.get('audio_url', '')
                    kid = self.ep_info.get('kid', None)
                # video_urls 的 key 是整数，保持 selected_qn 为整数以正确匹配
                selected_qn = int(self.selected_qn) if str(self.selected_qn).isdigit() else self.selected_qn
                if selected_qn not in video_urls:
                    # 尝试字符串匹配（兼容旧数据）
                    if str(selected_qn) in video_urls:
                        selected_qn = str(selected_qn)
                    else:
                        selected_qn = max(video_urls.keys(), key=lambda k: int(k)) if video_urls else ''
                video_url, actual_codecid = self._find_video_url(video_urls, selected_qn, task_info.get('selected_codecid', 0) if task_info else 0, task_info.get('video_output_codec', None) if task_info else 0)
                # 存储编码信息供merge_media使用
                self.ep_info['actual_codecid'] = actual_codecid
                _tc = task_info.get('selected_codecid', 0) if task_info else 0
                if not _tc and task_info:
                    _tc_map = {"h264": 7, "hevc": 12, "av1": 13}
                    _tc = _tc_map.get(task_info.get('video_output_codec', 'h264'), 0)
                self.ep_info['target_codecid'] = _tc
            else:
                
                play_info = self.parser._get_play_info(
                    media_type=self.video_info.get('type', 'video'),
                    bvid=bvid,
                    cid=self.ep_info.get('cid', ''),
                    is_tv_mode=self.video_info.get('is_tv_mode', False),
                    audio_quality=self.audio_quality
                )
                if not play_info.get('success'):
                    error = play_info.get('error', '获取播放信息失败')
                    if "访问权限不足" in error:
                        raise Exception("访问权限不足")
                    raise Exception(error)
                video_urls = play_info.get('video_urls', {})
                # video_urls 的 key 是整数，保持 selected_qn 为整数以正确匹配
                selected_qn = int(self.selected_qn) if str(self.selected_qn).isdigit() else self.selected_qn
                if selected_qn not in video_urls:
                    # 尝试字符串匹配（兼容旧数据）
                    if str(selected_qn) in video_urls:
                        selected_qn = str(selected_qn)
                    elif video_urls:
                        selected_qn = list(video_urls.keys())[0]
                    else:
                        raise Exception("无可用的视频画质")
                video_url, actual_codecid = self._find_video_url(video_urls, selected_qn, task_info.get('selected_codecid', 0) if task_info else 0, task_info.get('video_output_codec', None) if task_info else 0)
                audio_url = play_info.get('audio_url', '')
                # 存储编码信息供merge_media使用
                self.ep_info['actual_codecid'] = actual_codecid
                _tc2 = task_info.get('selected_codecid', 0) if task_info else 0
                if not _tc2 and task_info:
                    _tc2_map = {"h264": 7, "hevc": 12, "av1": 13}
                    _tc2 = _tc2_map.get(task_info.get('video_output_codec', 'h264'), 0)
                self.ep_info['target_codecid'] = _tc2
                kid = play_info.get('kid', None)
            return video_url, audio_url, kid
        except Exception as e:
            error = str(e)
            if "访问权限不足" in error:
                raise Exception("访问权限不足")
            raise Exception(f"链接获取失败：{error}")

    def _download_media_with_retry(self, url, media_type, bvid, ep_index, kid=None, stream_type=None, stream_weight=1.0):
        retry_count = 0
        max_retry = self.config.get_app_setting("max_retry", 3) if self.config else 3
        while self.is_running:
            try:
                logger.info(f"线程{self.ep_index}：开始下载{media_type}流")
                return self._download_media(url, media_type, bvid, ep_index, kid, stream_type=stream_type, stream_weight=stream_weight)
            except Exception as e:
                if any(keyword in str(e) for keyword in ["Read timed out", "Remote end closed", "Connection aborted", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 3)
                    logger.warning(f"线程{self.ep_index}：{media_type}下载超时，{delay}秒后重试")
                    if retry_count == 1:
                        current_progress = self._calc_total_progress(0)
                        self.progress_updated.emit(self.ep_index, current_progress, f"{media_type}下载超时，{delay}秒后重试...")
                    self.msleep(delay * 1000)
                    continue
                elif "403" in str(e) or "访问权限不足" in str(e):
                    logger.error(f"线程{self.ep_index}：{media_type}下载权限不足，无法下载")
                    raise
                elif "下载已取消" in str(e):
                    raise
                else:
                    retry_count += 1
                    if retry_count <= max_retry:
                        delay = min(retry_count, 2)
                        logger.warning(f"线程{self.ep_index}：{media_type}下载错误，{delay}秒后重试")
                        if retry_count == 1:
                            current_progress = self._calc_total_progress(0)
                            self.progress_updated.emit(self.ep_index, current_progress, f"{media_type}下载错误，{delay}秒后重试...")
                        self.msleep(delay * 1000)
                        continue
                    else:
                        raise Exception(f"{media_type}下载失败：{str(e)}")

    def _download_media(self, url, media_type, bvid, ep_index, kid=None, stream_type=None, stream_weight=1.0):
        if not url:
            return None

        start_time = time.time()
        last_time = start_time
        last_size = 0

        def progress_cb(p, downloaded_size=0, chunk_progresses=None):
            nonlocal start_time, last_time, last_size

            current_time = time.time()
            time_diff = current_time - last_time
            size_diff = downloaded_size - last_size

            speed = 0
            if time_diff > 0:
                speed = size_diff / time_diff

            last_time = current_time
            last_size = downloaded_size

            speed_str = ""
            if speed > 1024 * 1024:
                speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
            elif speed > 1024:
                speed_str = f"{speed / 1024:.2f} KB/s"
            elif speed > 0:
                speed_str = f"{speed:.2f} B/s"

            eta_str = ""
            if speed > 0 and p > 0 and p < 100:
                elapsed = current_time - start_time
                if elapsed > 0:
                    remaining_pct = 100 - p
                    eta_seconds = elapsed * remaining_pct / p
                    if eta_seconds > 3600:
                        eta_str = f" 剩余{int(eta_seconds // 3600)}时{int((eta_seconds % 3600) // 60)}分"
                    elif eta_seconds > 60:
                        eta_str = f" 剩余{int(eta_seconds // 60)}分{int(eta_seconds % 60)}秒"
                    else:
                        eta_str = f" 剩余{int(eta_seconds)}秒"

            # 计算总进度：并行下载时合并video和audio进度
            total_p = p
            if stream_type and hasattr(self, '_progress_lock'):
                with self._progress_lock:
                    if stream_type == 'video':
                        self._video_progress = p
                    elif stream_type == 'audio':
                        self._audio_progress = p
                    v_p = self._video_progress
                    a_p = self._audio_progress
                    total_p = int(v_p * stream_weight + a_p * stream_weight)
                    if a_p > 0:
                        status = f"视频{v_p}% | 音频{a_p}%"
                    else:
                        status = f"下载视频：{v_p}%"
            else:
                status = f"下载{media_type}流：{p}%"

            if speed_str:
                status += f" ({speed_str})"
            if eta_str:
                status += eta_str
            # 将分片进度编码到状态字符串中
            emit_status = status
            if chunk_progresses:
                import json
                try:
                    emit_status = f"__CHUNKS__{json.dumps(chunk_progresses)}__ {status}"
                except Exception:
                    pass
            self.progress_updated.emit(self.ep_index, self._calc_total_progress(total_p), emit_status)

            if not self.is_running:
                raise Exception("下载已取消")

        def is_running():
            return self.is_running

        try:
            file_path = self.parser.download_file(
                url=url,
                save_path=self.save_path,
                progress_callback=progress_cb,
                file_type=media_type,
                bvid=bvid,
                is_running=is_running,
                kid=kid
            )
            if file_path and os.path.exists(file_path):
                self.temp_files.append(file_path)
                return file_path
            return None
        except Exception as e:
            if "下载已取消" in str(e):
                logger.info(f"线程{self.ep_index}：{media_type}流下载被取消")
                return None
            raise

    def _calc_total_progress(self, p):

        try:
            p = float(p)
            p = max(0, min(100, p))

            return p
        except (ValueError, TypeError):

            return 0

    def _find_video_url(self, video_urls, selected_qn, selected_codecid=0, video_output_codec=None):
        """根据用户选择的视频编码偏好，从video_urls中选择最匹配的视频URL

        Args:
            video_urls: 视频URL字典，key可能是整数qn或(qn, codecid)元组
            selected_qn: 用户选择的清晰度
            selected_codecid: 直接指定的编码ID（备用）
            video_output_codec: UI中选择的编码名称（h264/hevc/av1/vp9/auto）

        Returns:
            (video_url, actual_codecid): 视频URL和实际使用的编码ID
        """
        codec_name_map = {"h264": 7, "hevc": 12, "av1": 13, "vp9": 14, "auto": None}
        # codecid优先级（用户选择优先）
        codec_priority = {12: 0, 13: 1, 7: 2, 14: 3}  # HEVC > AV1 > H.264 > VP9

        target_codecid = selected_codecid
        if not target_codecid and video_output_codec:
            target_codecid = codec_name_map.get(video_output_codec)

        logger.info(f"[编码选择] selected_qn={selected_qn}, video_output_codec={video_output_codec}, "
                     f"target_codecid={target_codecid}, video_urls keys={list(video_urls.keys())[:10]}")

        # 尝试1: 精确匹配 (qn, target_codecid) 元组键
        if target_codecid:
            tuple_key = (int(selected_qn) if str(selected_qn).isdigit() else selected_qn, target_codecid)
            if tuple_key in video_urls:
                logger.info(f"[编码选择] 精确匹配元组键 {tuple_key} 成功")
                return video_urls[tuple_key], target_codecid

        # 尝试2: 在元组键中找同qn的任意编码，优先选目标编码
        qn_int = int(selected_qn) if str(selected_qn).isdigit() else selected_qn
        matching_entries = []
        for key in video_urls:
            if isinstance(key, tuple) and len(key) >= 2 and key[0] == qn_int:
                codecid = key[1]
                matching_entries.append((key, codecid))
            elif key == qn_int or key == selected_qn or str(key) == str(selected_qn):
                # 纯qn键，编码未知（默认7=AVC）
                matching_entries.append((key, 7))

        if matching_entries:
            if target_codecid:
                # 按目标编码优先排序
                def sort_key(entry):
                    codecid = entry[1]
                    if codecid == target_codecid:
                        return 0  # 精确匹配最高优先
                    return codec_priority.get(codecid, 99)
                matching_entries.sort(key=sort_key)
            best_key, best_codecid = matching_entries[0]
            logger.info(f"[编码选择] 选择键={best_key}, 实际编码codecid={best_codecid}")
            return video_urls[best_key], best_codecid

        # 尝试3: 纯qn匹配（向后兼容）
        if selected_qn in video_urls:
            logger.info(f"[编码选择] 纯qn匹配: {selected_qn}")
            return video_urls[selected_qn], 7  # 默认AVC

        # 尝试4: 字符串qn匹配
        if str(selected_qn) in video_urls:
            logger.info(f"[编码选择] 字符串qn匹配: {str(selected_qn)}")
            return video_urls[str(selected_qn)], 7

        # 兜底：返回第一个可用URL
        if video_urls:
            fallback_key = list(video_urls.keys())[0]
            logger.warning(f"[编码选择] 无精确匹配，使用兜底: {fallback_key}")
            return video_urls[fallback_key], 7

        raise Exception(f"未找到匹配的视频流: qn={selected_qn}")

    def _merge_media(self, video_path, audio_path, kid=None):

        if not video_path or not os.path.exists(video_path):
            raise Exception("视频文件不存在")
        
        if audio_path and not os.path.exists(audio_path):
            raise Exception("音频文件不存在")
        

        if not self.save_path or not os.path.exists(self.save_path):
            raise Exception("保存路径不存在")
        
        add_episode_prefix = self.config.get_app_setting("add_episode_to_filename", True) if self.config else True
        if add_episode_prefix:
            # 去除 ep_title 中已存在的 "第X集" 前缀，避免重复
            _clean_ep_title = re.sub(r'^第\d+集[ _\-]*', '', self.ep_title) if self.ep_title else ''
            _final_ep_title = _clean_ep_title if _clean_ep_title else self.ep_title
            if _final_ep_title:
                output_path = os.path.join(self.save_path, f"第{self.ep_index+1}集 - {_final_ep_title}.mp4")
            else:
                output_path = os.path.join(self.save_path, f"第{self.ep_index+1}集.mp4")
        else:
            output_path = os.path.join(self.save_path, f"{self.ep_title}.mp4")
        output_path = get_unique_filename(output_path)
        if self.video_process_mode == 're-encode':
            merge_status = "正在重编码合并..."
        else:
            merge_status = "合并音视频..."
        self.progress_updated.emit(self.ep_index, 90, merge_status)
        self.merge_started.emit(self.ep_index)

        try:
            if audio_path:
                _tgt_cc = self.ep_info.get('target_codecid', 0)
                _act_cc = self.ep_info.get('actual_codecid', 0)
                merge_result, merge_error = self.parser.merge_media(video_path, audio_path, output_path, kid, target_codecid=_tgt_cc, actual_codecid=_act_cc, audio_quality=self.audio_quality, video_process_mode=self.video_process_mode)
                if not merge_result:
                    raise Exception(f"合并失败：{merge_error}" if merge_error else "合并失败")
            else:
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except Exception as e:
                        raise Exception(f"无法删除已存在的文件：{str(e)}")
                try:
                    os.rename(video_path, output_path)
                except Exception as e:
                    shutil.move(video_path, output_path)

            if not os.path.exists(output_path):
                from utils import verify_and_ensure_save
                actual_path, saved = verify_and_ensure_save(output_path, source_path=video_path if not audio_path else None)
                if saved and actual_path != output_path:
                    output_path = actual_path
                    logger.warning(f"合并后文件不在目标路径，已备用保存到：{output_path}")
                elif not saved:
                    raise Exception("合并后文件不存在且备用保存失败")

            self.progress_updated.emit(self.ep_index, 100, "合并完成")
            self.merge_finished.emit(self.ep_index)
            logger.info(f"线程{self.ep_index}：下载完成")
            self.episode_finished.emit(self.ep_index, True, f"完成：{os.path.basename(output_path)}")

            # 合并成功后立即清理临时文件（video/audio流），避免遗留多余的音频文件
            self._clean_temp_files()
        except Exception as e:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as clean_e:
                    logger.warning(f"清理合并失败的文件失败：{str(clean_e)}")
            raise Exception(f"合并失败：{str(e)}")

    def _clean_temp_files(self):
        """清理下载产生的临时文件（video/audio流）

        增强清理逻辑：
        - 文件不存在则跳过
        - 删除失败时尝试用 shutil 强制删除（应对文件占用）
        - 最终仍失败则记录路径，下次启动时清理
        """
        import shutil
        failed_paths = []
        for file_path in self.temp_files:
            try:
                if not file_path or not os.path.exists(file_path):
                    continue
                try:
                    os.remove(file_path)
                    logger.debug(f"线程{self.ep_index}：清理临时文件: {file_path}")
                except Exception:
                    # 删除失败可能是文件占用，尝试 shutil.rmtree 强制删除
                    try:
                        shutil.rmtree(file_path, ignore_errors=True)
                    except Exception:
                        failed_paths.append(file_path)
            except Exception as e:
                logger.warning(f"线程{self.ep_index}：清理临时文件失败: {file_path}, {e}")
                failed_paths.append(file_path)
        self.temp_files.clear()
        # 清理失败的路径记录到全局待清理列表，下次启动时清理
        if failed_paths:
            try:
                cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", "_pending_cleanup.txt")
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, 'a', encoding='utf-8') as f:
                    for p in failed_paths:
                        f.write(p + "\n")
            except Exception:
                pass

    @staticmethod
    def cleanup_pending_temp_files():
        """启动时调用，清理上次遗留的临时文件"""
        try:
            cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", "_pending_cleanup.txt")
            if not os.path.exists(cache_file):
                return
            import shutil
            with open(cache_file, 'r', encoding='utf-8') as f:
                for line in f:
                    p = line.strip()
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except Exception:
                            try:
                                shutil.rmtree(p, ignore_errors=True)
                            except Exception:
                                pass
            try:
                os.remove(cache_file)
            except Exception:
                pass
            # 同时清理 temp 目录下的 .m4s 和 .decrypted 临时文件
            temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
            if os.path.isdir(temp_dir):
                for fn in os.listdir(temp_dir):
                    if fn.endswith('.m4s') or fn.endswith('.decrypted') or fn.startswith('bili_merge_'):
                        try:
                            os.remove(os.path.join(temp_dir, fn))
                        except Exception:
                            pass
        except Exception:
            pass

    def stop(self):
        self.is_running = False
        if hasattr(self.parser, 'stop_download'):
            self.parser.stop_download()


class DownloadManager(QObject):
    global_progress_updated = pyqtSignal(int, str)
    episode_progress_updated = pyqtSignal(str, int, float, str)
    episode_finished = pyqtSignal(str, int, bool, str)
    all_finished = pyqtSignal()
    task_added = pyqtSignal(str)
    task_status_changed = pyqtSignal(str)
    same_task_exists = pyqtSignal(dict)
    merge_started = pyqtSignal(str, int)
    merge_finished = pyqtSignal(str, int)

    def __init__(self, parser, task_manager=None, max_threads=4, max_concurrent_tasks=2, config=None):
        super().__init__()
        self.parser_template = parser
        self.task_manager = task_manager
        self.config = config
        self.max_threads = min(max_threads, 16)
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks = {}
        self.paused_tasks = {}
        self.task_queue = []
        self._mutex = QMutex()
        self._task_condition = QWaitCondition()
        self._shutting_down = False
        logger.info(f"下载管理器初始化，并发数：{self.max_threads}，最大并发任务数：{self.max_concurrent_tasks}")
        

        self.scheduler_thread = threading.Thread(target=self._schedule_tasks, daemon=True)
        self.scheduler_thread.start()
    
    def set_max_threads(self, max_threads):
        if max_threads > 0:
            self.max_threads = min(max_threads, 16)
            self.max_concurrent_tasks = min(max_threads, 16)
            logger.info(f"线程数已修改为：{self.max_threads}，最大并发任务数：{self.max_concurrent_tasks}")

    def _schedule_tasks(self):
        while not self._shutting_down:
            try:
                self._mutex.lock()

                while len(self.active_tasks) >= self.max_concurrent_tasks and len(self.task_queue) > 0:
                    if self._shutting_down:
                        self._mutex.unlock()
                        return
                    try:
                        self._task_condition.wait(self._mutex, 1000)
                    except Exception as e:
                        logger.error(f"调度线程等待时发生异常：{str(e)}")
                        break
                
                if self._shutting_down:
                    self._mutex.unlock()
                    return

                if len(self.task_queue) > 0 and len(self.active_tasks) < self.max_concurrent_tasks:
                    download_params = self.task_queue.pop(0)
                    task_id = download_params.get('task_id', 'unknown')
                    logger.info(f"调度线程：从队列取出任务，任务ID：{task_id}，剩余队列长度：{len(self.task_queue)}")
                    self._mutex.unlock()

                    try:
                        logger.info(f"调度线程：开始执行任务{task_id}")
                        self._execute_task(download_params)
                        logger.info(f"调度线程：任务{task_id}执行完成")
                    except Exception as e:
                        logger.error(f"执行任务时发生异常：{str(e)}")
                else:
                    self._mutex.unlock()
                    time.sleep(0.1)
            except Exception as e:
                logger.error(f"调度线程发生异常：{str(e)}")
                try:
                    self._mutex.unlock()
                except:
                    pass
                time.sleep(1)

    def _execute_task(self, download_params):

        video_info = download_params.get('video_info', {})
        selected_qn = download_params.get('qn', '')
        save_path = download_params.get('save_path', '')
        episodes = download_params.get('episodes', [])
        url = download_params.get('url', '')
        resume_download = download_params.get('resume_download', False)
        

        if not episodes:
            try:
                self.global_progress_updated.emit(0, "无选中集数")
            except RuntimeError:

                logger.warning("DownloadManager对象已被删除，无法发送信号")
            return
        if not save_path:
            try:
                self.global_progress_updated.emit(0, "保存路径未指定")
            except RuntimeError:

                logger.warning("DownloadManager对象已被删除，无法发送信号")
            return
        if not selected_qn:
            try:
                self.global_progress_updated.emit(0, "未选择清晰度")
            except RuntimeError:

                logger.warning("DownloadManager对象已被删除，无法发送信号")
            return
        


        self._mutex.lock()
        task_exists = False
        for existing_task_id, existing_task in self.active_tasks.items():

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
        self._mutex.unlock()
        
        if task_exists:
            logger.info(f"相同的下载任务已存在")
            return
        

        if self.task_manager:
            all_tasks = self.task_manager.get_all_tasks()
            for existing_task in all_tasks:
                
                if (existing_task.get('url') == url and 
                    existing_task.get('qn') == selected_qn and 
                    existing_task.get('status') in ['downloading', 'pending'] and
                    existing_task.get('status') != 'cancelled'):
    
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
                            logger.info(f"相同的下载任务已在任务列表中")
                            return
        

        task_id = download_params.get('task_id', str(int(time.time() * 1000)))
        logger.info(f"开始下载任务：{task_id}")


        
        
        task_parser = self.parser_template

        # download_content_type: 0=有声视频, 1=仅音频, 2=仅视频
        download_content_type = download_params.get('download_content_type', 0)
        download_video = download_content_type in (0, 2)  # 有声视频或仅视频时下载视频
        download_audio = download_content_type in (0, 1)  # 有声视频或仅音频时下载音频
        download_danmaku = download_params.get('download_danmaku', False)
        download_cover = download_params.get('download_cover', False)
        download_subtitle = download_params.get('download_subtitle', False)
        danmaku_format = download_params.get('danmaku_format', 'XML')
        video_format = download_params.get('video_format', 'mp4')
        audio_format = download_params.get('audio_format', 'mp3')

        task_info = {
            "id": task_id,
            "url": url,
            "title": video_info.get('title', '未知视频'),
            "save_path": save_path,
            "progress": 0,
            "status": "downloading",
            "video_info": video_info,
            "qn": selected_qn,
            "episodes": episodes,
            "total_episodes": len(episodes),
            "completed_episodes": 0,
            "failed_episodes": 0,
            "is_cancelled": False,
            "is_paused": False,
            "task_start_time": time.time(),
            "downloaded_episodes": [],
            "parser": task_parser,
            "download_content_type": download_content_type,
            "download_video": download_video,
            "download_audio": download_audio,
            "download_danmaku": download_danmaku,
            "danmaku_format": danmaku_format,
            "video_format": video_format,
            "audio_format": audio_format,
            "video_output_codec": download_params.get('video_output_codec', self.config.get_app_setting("video_output_codec", "h264") if self.config else "h264"),
            "audio_quality": download_params.get('audio_quality', self.config.get_app_setting("audio_quality", 30280) if self.config else 30280),
            "video_process_mode": download_params.get('video_process_mode', self.config.get_app_setting("video_process_mode", "copy") if self.config else "copy"),
            "download_cover": download_params.get('download_cover', False),
            "download_subtitle": download_params.get('download_subtitle', False)
        }

        self._mutex.lock()
        self.active_tasks[task_id] = task_info
        self._mutex.unlock()

        if self.task_manager:
            task_info_for_manager = {
                "id": task_id,
                "url": url,
                "title": video_info.get('title', '未知视频'),
                "save_path": save_path,
                "progress": 0,
                "status": "downloading",
                "video_info": video_info,
                "qn": selected_qn,
                "episodes": episodes,
                "download_video": download_video,
                "download_danmaku": download_danmaku,
                "danmaku_format": danmaku_format,
                "video_format": video_format,
            "audio_format": audio_format,
            "audio_quality": download_params.get('audio_quality', 0),
            "video_process_mode": download_params.get('video_process_mode', self.config.get_app_setting("video_process_mode", "copy") if self.config else "copy"),
                "bvid": video_info.get("bvid", ""),
                "aid": video_info.get("aid", ""),
                "up_name": video_info.get("owner", {}).get("name", ""),
                "cover_url": video_info.get("pic", ""),
                "total_episodes": len(episodes),
                "completed_episodes": 0,
                "task_start_time": datetime.now().isoformat(),
                "task_type": "video",
            }
            task = self.task_manager.add_task(task_info_for_manager)
            self.task_added.emit(task_id)
            logger.info(f"创建下载任务：{task_id}")

        logger.info(f"准备下载{len(episodes)}个视频")

        # 计算附加内容（弹幕/封面/字幕）在进度条中的索引偏移
        extra_base_idx = len(episodes)
        extra_offsets = {}
        offset = extra_base_idx
        if download_danmaku:
            extra_offsets['danmaku'] = offset
            offset += 1
        if download_cover:
            extra_offsets['cover'] = offset
            offset += 1
        if download_subtitle:
            extra_offsets['subtitle'] = offset
            offset += 1
        task_info['extra_offsets'] = extra_offsets

        for idx, ep in enumerate(episodes):
            self.episode_progress_updated.emit(task_id, idx, 0, "准备下载...")
        
        try:
            self.global_progress_updated.emit(0, f"任务{task_id}：开始下载{len(episodes)}集（并发：{min(self.max_threads, len(episodes))}")

            actual_threads = min(self.max_threads, len(episodes))
            task_info['executor'] = ThreadPoolExecutor(max_workers=actual_threads)
            logger.info(f"创建线程池，最大线程数：{actual_threads}")
            
            
            task_info['futures'] = []
            for idx, ep in enumerate(episodes):
                
                future = task_info['executor'].submit(self._download_episode, task_id, idx, ep)
                task_info['futures'].append(future)
                logger.info(f"任务{task_id}：提交第{idx+1}集到线程池")
            
            
            self._monitor_tasks(task_id)
        except Exception as e:
            logger.error(f"线程池创建失败：{str(e)}")
            self.global_progress_updated.emit(0, f"线程池创建失败：{str(e)}")
            self._cleanup_task(task_id)
            return

    def start_download(self, download_params):
        video_info = download_params.get('video_info', {})
        selected_qn = download_params.get('qn', '')
        save_path = download_params.get('save_path', '')
        episodes = download_params.get('episodes', [])
        task_id = download_params.get('task_id', 'unknown')
        download_video = download_params.get('download_video', True)
        download_danmaku = download_params.get('download_danmaku', False)
        danmaku_format = download_params.get('danmaku_format', 'XML')
        video_format = download_params.get('video_format', 'mp4')
        audio_format = download_params.get('audio_format', 'mp3')
        
        logger.info(f"收到下载请求，任务ID：{task_id}，集数：{len(episodes)}，视频下载：{download_video}，弹幕下载：{download_danmaku}，弹幕格式：{danmaku_format}，视频格式：{video_format}，音频格式：{audio_format}")
        
        if not episodes:
            logger.warning(f"任务{task_id}：无选中集数")
            self.global_progress_updated.emit(0, "无选中集数")
            return

        if not save_path or not isinstance(save_path, str):
            logger.warning(f"任务{task_id}：保存路径未指定或无效")
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
            logger.warning(f"使用默认保存路径: {save_path}")
        else:
            save_path = os.path.normpath(save_path)

        # 批量下载时多个任务共享同一 save_path，缓存已验证路径避免重复文件 I/O
        if not hasattr(self, '_validated_save_paths'):
            self._validated_save_paths = set()
        if save_path not in self._validated_save_paths:
            try:
                if not os.path.exists(save_path):
                    os.makedirs(save_path, exist_ok=True)

                # 测试写入权限 - 使用UUID确保文件名唯一，避免多线程冲突
                import uuid
                test_file = os.path.join(save_path, f"permission_test_{uuid.uuid4().hex[:8]}.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                logger.info(f"任务{task_id}：保存路径验证通过: {save_path}")
                self._validated_save_paths.add(save_path)
            except Exception as e:
                error_msg = f"保存路径不可用: {str(e)}"
                logger.error(f"任务{task_id}：{error_msg}")
                self.global_progress_updated.emit(0, error_msg)
                return
            
        if not selected_qn and download_video:
            logger.warning(f"任务{task_id}：未选择清晰度")
            self.global_progress_updated.emit(0, "未选择清晰度")
            return

        # 下载前检查磁盘空间是否足够
        try:
            import shutil as _shutil
            total_bytes, used_bytes, free_bytes = _shutil.disk_usage(save_path)
            # 估算所需空间：根据选中集数和清晰度估算
            estimated_size_mb = 0
            try:
                est_size = download_params.get('estimated_size_mb', 0)
                if est_size:
                    estimated_size_mb = float(est_size)
                else:
                    # 兜底估算：每集按500MB估算（合并前视频+音频流会临时占用约2倍空间）
                    episodes_count = len(download_params.get('episodes', []))
                    estimated_size_mb = episodes_count * 500
            except Exception:
                estimated_size_mb = len(download_params.get('episodes', [])) * 500

            # 合并需要临时空间（约2倍最终大小），加上安全系数1.2
            required_mb = estimated_size_mb * 2 * 1.2
            free_mb = free_bytes / (1024 * 1024)

            if free_mb < required_mb:
                error_msg = (f"磁盘空间不足！\n"
                             f"保存位置：{save_path}\n"
                             f"可用空间：{free_mb:.0f} MB\n"
                             f"预计需要：{required_mb:.0f} MB（含临时合并空间）\n"
                             f"请清理磁盘空间后再试")
                logger.error(f"任务{task_id}：{error_msg}")
                self.global_progress_updated.emit(0, error_msg)
                return
            else:
                logger.info(f"任务{task_id}：磁盘空间检查通过，可用 {free_mb:.0f} MB，需要约 {required_mb:.0f} MB")
        except Exception as e:
            logger.warning(f"任务{task_id}：磁盘空间检查失败: {e}")

        download_params['save_path'] = save_path

        same_task_exists = False
        current_url = download_params.get('url')
        current_qn = download_params.get('qn')
        current_episodes = download_params.get('episodes', [])
        
        current_ep_indices = set()
        for ep in current_episodes:
            ep_idx = ep.get('ep_index', ep.get('page'))
            if ep_idx is not None:
                current_ep_indices.add(ep_idx)
        
        for existing_task_id, existing_task in list(self.active_tasks.items()):
            if (existing_task.get('url') == current_url and 
                existing_task.get('qn') == current_qn):
                
                existing_episodes = existing_task.get('episodes', [])
                existing_ep_indices = set()
                for ep in existing_episodes:
                    ep_idx = ep.get('ep_index', ep.get('page'))
                    if ep_idx is not None:
                        existing_ep_indices.add(ep_idx)
                
                if current_ep_indices == existing_ep_indices:
                    same_task_exists = True
                    break
        
        if not same_task_exists:
            for queued_task in self.task_queue:
                if (queued_task.get('url') == current_url and 
                    queued_task.get('qn') == current_qn):
                    
                    existing_episodes = queued_task.get('episodes', [])
                    existing_ep_indices = set()
                    for ep in existing_episodes:
                        ep_idx = ep.get('ep_index', ep.get('page'))
                        if ep_idx is not None:
                            existing_ep_indices.add(ep_idx)
                    
                    if current_ep_indices == existing_ep_indices:
                        same_task_exists = True
                        break
        
        if same_task_exists:
            logger.info(f"相同的下载任务已存在（URL+清晰度+集数），发出same_task_exists信号")
            self.same_task_exists.emit(download_params)
            return
        
        logger.info(f"任务{task_id}：参数验证通过，准备添加到队列")

        download_params['download_video'] = download_video
        download_params['download_danmaku'] = download_danmaku
        download_params['danmaku_format'] = danmaku_format
        download_params['video_format'] = video_format
        download_params['audio_format'] = audio_format

        self._mutex.lock()
        self.task_queue.append(download_params)
        logger.info(f"任务{task_id}：已添加到队列，当前队列长度：{len(self.task_queue)}")

        self._task_condition.wakeOne()
        logger.info(f"任务{task_id}：已唤醒调度线程")
        self._mutex.unlock()

    def _find_video_url(self, video_urls, selected_qn, selected_codecid=0, video_output_codec=None):
        """根据清晰度和编码查找视频URL

        返回: (url, actual_codecid) 元组
        - url: 视频下载地址
        - actual_codecid: 实际使用的编码ID (7=AVC, 12=HEVC, 13=AV1)

        优先级：
        1. 用户在UI中明确选择的编码 (selected_codecid)
        2. 设置中的编码偏好 (video_output_codec)
        3. 按兼容性优先级回退：AVC > HEVC > AV1
        4. 纯 qn 查找（向后兼容）
        """
        codec_name_to_id = {"h264": 7, "hevc": 12, "av1": 13, "vp9": 14}
        target_codecid = None
        if selected_codecid and selected_codecid > 0:
            target_codecid = int(selected_codecid)
        elif video_output_codec and video_output_codec != "auto":
            target_codecid = codec_name_to_id.get(video_output_codec, None)

        # 1. 优先使用用户在UI中明确选择的编码
        if selected_codecid and selected_codecid > 0:
            url = video_urls.get((int(selected_qn), int(selected_codecid)))
            if url:
                logger.info(f"[编码选择] 使用UI指定编码: qn={selected_qn}, codecid={selected_codecid}")
                return url, int(selected_codecid)
            else:
                logger.warning(f"[编码选择] UI指定的编码(codecid={selected_codecid})不可用，将回退")

        # 2. 使用设置中的编码偏好
        if video_output_codec and video_output_codec != "auto":
            preferred_codecid = codec_name_to_id.get(video_output_codec, 0)
            if preferred_codecid and preferred_codecid > 0:
                url = video_urls.get((int(selected_qn), preferred_codecid))
                if url:
                    logger.info(f"[编码选择] 使用设置编码偏好: qn={selected_qn}, codec={video_output_codec}, codecid={preferred_codecid}")
                    return url, preferred_codecid
                else:
                    logger.warning(f"[编码选择] 设置的编码({video_output_codec}, codecid={preferred_codecid})不可用，将回退")

        # 3. 回退：按编码优先级 AVC > HEVC > AV1 查找
        for codecid in [7, 12, 13]:
            url = video_urls.get((int(selected_qn), codecid))
            if url:
                codec_name = {7: "H.264(AVC)", 12: "H.265(HEVC)", 13: "AV1"}.get(codecid, str(codecid))
                if target_codecid and target_codecid != codecid:
                    logger.warning(f"[编码选择] 目标编码不可用！已回退到 {codec_name} (qn={selected_qn})。下载后可能需要转码。")
                else:
                    logger.info(f"[编码选择] 回退使用可用编码: {codec_name} (qn={selected_qn})")
                return url, codecid

        # 4. 最终回退：纯 qn 查找（向后兼容）
        url = video_urls.get(str(selected_qn)) or video_urls.get(int(selected_qn), '')
        if url:
            logger.warning(f"[编码选择] 未找到(qn, codecid)格式的URL，使用纯qn回退 (qn={selected_qn})")
            # 尝试从纯qn URL推断编码（无法精确判断，返回0表示未知）
            return url, 0
        return '', 0

    def _download_episode(self, task_id, ep_index, ep_info):
        self._mutex.lock()
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            task_info = self.paused_tasks.get(task_id)
        if not task_info:
            self._mutex.unlock()
            return False, "任务已取消"
        if task_info.get('is_paused'):
            self._mutex.unlock()
            return False, "TASK_PAUSED"
        if task_info['is_cancelled']:
            self._mutex.unlock()
            return False, "任务已取消"
        self._mutex.unlock()

        start_time = time.time()
        download_content_type = task_info.get('download_content_type', 0)
        download_video = task_info.get('download_video', True)
        download_audio = download_content_type in (0, 1)
        download_danmaku = task_info.get('download_danmaku', False)
        download_cover = task_info.get('download_cover', False)
        download_subtitle = task_info.get('download_subtitle', False)
        extra_offsets = task_info.get('extra_offsets', {})
        
        logger.info(f"任务{task_id}：开始处理第{ep_index+1}集，内容类型：{download_content_type}，视频：{download_video}，音频：{download_audio}，弹幕：{download_danmaku}，封面：{download_cover}，字幕：{download_subtitle}")
        
        has_media = download_video or download_audio
        if not has_media and not download_danmaku and not download_cover and not download_subtitle:
            logger.warning(f"任务{task_id}：第{ep_index+1}集未选择任何下载内容")
            return False, "未选择下载内容"
        
        temp_files = []
        try:
            ep_title = f"第{ep_index+1}集_未知标题"
            try:
                if task_info['video_info'].get('is_bangumi') and task_info['video_info'].get('bangumi_info'):
                    season = task_info['video_info']['bangumi_info'].get('season_title', '未知季度')
                    ep_idx = ep_info.get('ep_index', '未知集')
                    title_candidates = [
                        ep_info.get('ep_title', ''),
                        ep_info.get('title', ''),
                        ep_info.get('name', '')
                    ]
                    actual_title = next((t for t in title_candidates if t), '')
                    # ep_idx 可能已经是 "第4集" 格式，避免重复包裹
                    ep_prefix = ep_idx if '第' in str(ep_idx) else f"第{ep_idx}集"
                    if actual_title:
                        ep_title = f"{ep_prefix}_{actual_title}"
                    else:
                        ep_title = ep_prefix
                elif task_info['video_info'].get('is_cheese'):
                    title_candidates = [
                        ep_info.get('ep_title', ''),
                        ep_info.get('title', ''),
                        ep_info.get('name', '')
                    ]
                    actual_title = next((t for t in title_candidates if t), '')
                    ep_idx = ep_info.get('ep_index', ep_index + 1)
                    # ep_idx 可能已经是 "第4集" 格式，避免重复包裹
                    ep_prefix = ep_idx if '第' in str(ep_idx) else f"第{ep_idx}集"
                    if actual_title:
                        ep_title = f"{ep_prefix}_{actual_title}"
                    else:
                        ep_title = ep_prefix
                else:
                    # 普通视频：优先使用ep_info中的标题，如果没有则使用视频总标题
                    title_candidates = [
                        ep_info.get('ep_title', ''),
                        ep_info.get('part', ''),  # 分P标题
                        ep_info.get('title', ''),
                        ep_info.get('name', '')
                    ]
                    actual_title = next((t for t in title_candidates if t), '')
                    page = ep_info.get('page', ep_index + 1)
                    # 获取视频总标题作为后备
                    video_main_title = task_info['video_info'].get('title', '')
                    if actual_title:
                        # 去除 actual_title 中已存在的 "第X集" 前缀，避免重复
                        _actual_clean = re.sub(r'^第\d+集[ _\-]*', '', actual_title) if actual_title else ''
                        if _actual_clean:
                            ep_title = f"第{page}集_{_actual_clean}"
                        else:
                            ep_title = f"第{page}集"
                    elif video_main_title:
                        # 使用视频总标题作为文件名基础
                        _clean_main = re.sub(r'^第\d+集[ _\-]*', '', video_main_title)
                        ep_title = f"第{page}集_{_clean_main[:25]}"
                    else:
                        ep_title = f"第{page}集"
                for c in illegal_filename_chars():
                    ep_title = ep_title.replace(c, '_')
                # 不再截断标题，保持完整文件名
            except Exception as e:
                logger.error(f"任务{task_id}：标题初始化错误: {e}")
                ep_title = f"第{ep_index+1}集"

            try:
                if not task_info['save_path'] or not isinstance(task_info['save_path'], str):
                    raise Exception("保存路径无效")

                task_info['save_path'] = os.path.normpath(task_info['save_path'])

                if not os.path.exists(task_info['save_path']):
                    os.makedirs(task_info['save_path'], exist_ok=True)

                # 测试写入权限 - 使用UUID确保文件名唯一，避免多线程冲突
                import uuid
                test_file = os.path.join(task_info['save_path'], f"permission_test_{uuid.uuid4().hex[:8]}.tmp")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                raise Exception(f"保存路径异常：{str(e)}")

            self.episode_progress_updated.emit(task_id, ep_index, 0, "准备下载...")

            self._mutex.lock()
            task_info = self.active_tasks.get(task_id)
            if not task_info:
                task_info = self.paused_tasks.get(task_id)
            if not task_info:
                self._mutex.unlock()
                return False, "任务已取消"
            if task_info.get('is_paused'):
                self._mutex.unlock()
                return False, "TASK_PAUSED"
            if task_info['is_cancelled']:
                self._mutex.unlock()
                return False, "任务已取消"
            self._mutex.unlock()

            output_path = None
            clean_title = ep_title.replace("正片_", "")
            download_content_type = task_info.get('download_content_type', 0)
            download_video = task_info.get('download_video', True)
            download_audio = task_info.get('download_audio', True)

            if download_video or download_audio:
                self.episode_progress_updated.emit(task_id, ep_index, 5, "获取下载链接...")

                bvid = ep_info.get('bvid', task_info['video_info'].get('bvid', ''))
                try:
                    # 创建ep_info的副本，避免修改原始对象
                    ep_info_copy = ep_info.copy()
                    ep_info_copy['task_id'] = task_id
                    video_url, audio_url, kid = self._get_media_urls_with_retry(bvid, ep_info_copy)

                    # 根据下载类型检查链接有效性
                    if download_video and not video_url:
                        raise Exception("无有效视频链接")
                    if download_audio and not audio_url:
                        # 仅音频模式下必须有音频，有声视频模式下无音频也可以继续
                        if download_content_type == 1:
                            raise Exception("无有效音频链接")

                    self.episode_progress_updated.emit(task_id, ep_index, 10, "链接获取成功，开始下载...")
                except Exception as e:
                    logger.error(f"任务{task_id}：获取播放链接失败：{str(e)}")
                    return False, f"获取播放链接失败：{str(e)}"

                video_path = None
                audio_path = None

                if download_content_type == 1:
                    audio_path = self._download_media_with_retry(task_id, audio_url, "audio", bvid, ep_index, kid)
                    if not audio_path:
                        return False, "音频下载失败"
                    temp_files.append(audio_path)
                    audio_format = task_info.get('audio_format', 'mp3')
                    _audio_quality = task_info.get('audio_quality', 30280)
                    # Hi-Res/杜比自动使用FLAC格式
                    if _audio_quality in (30251, 30250) and audio_format.lower() in ('mp3', 'aac', 'ogg', 'm4a'):
                        audio_format = 'flac'
                        logger.info(f"任务{task_id}：仅音频模式，Hi-Res/杜比自动使用FLAC格式")
                    output_path = os.path.join(task_info['save_path'], f"{clean_title}.{audio_format}")
                    output_path = get_unique_filename(output_path)
                    # 直接重命名音频文件为输出文件
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        os.rename(audio_path, output_path)
                    except Exception as e:
                        shutil.move(audio_path, output_path)
                    temp_files.remove(audio_path)  # 已移动到输出路径，不再清理
                    self.episode_progress_updated.emit(task_id, ep_index, 100, "音频下载完成")
                    logger.info(f"任务{task_id}：第{ep_index+1}集音频下载完成：{output_path}")

                elif download_content_type == 2:
                    video_path = self._download_media_with_retry(task_id, video_url, "video", bvid, ep_index, kid)
                    if not video_path:
                        return False, "视频下载失败"
                    temp_files.append(video_path)
                    # 输出视频文件（不合并音频）
                    video_format = task_info.get('video_format', 'mp4')
                    output_path = os.path.join(task_info['save_path'], f"{clean_title}.{video_format}")
                    output_path = get_unique_filename(output_path)
                    # 直接重命名视频文件为输出文件
                    try:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        os.rename(video_path, output_path)
                    except Exception as e:
                        shutil.move(video_path, output_path)
                    temp_files.remove(video_path)  # 已移动到输出路径，不再清理
                    self.episode_progress_updated.emit(task_id, ep_index, 100, "视频下载完成（无声）")
                    logger.info(f"任务{task_id}：第{ep_index+1}集视频下载完成（无声）：{output_path}")

                else:  # download_content_type == 0
                    has_audio = bool(audio_url)

                    if has_audio:
                        self._dm_video_progress = 0
                        self._dm_audio_progress = 0
                        self._dm_progress_lock = threading.Lock()

                        # 并发控制：当 max_threads >= 3 时，音视频改为串行下载
                        # 避免总并发连接数 = max_threads × 2(video+audio) 过高触发 CDN 限流
                        # 单连接速度反而比多连接抢带宽更快
                        try:
                            _mt = int(self.config.get_app_setting('max_threads', 4)) if self.config else 4
                        except Exception:
                            _mt = 4
                        if _mt >= 3:
                            # 串行：先下完视频再下音频，总连接数 = max_threads × 1
                            video_path = self._download_media_with_retry(task_id, video_url, "video", bvid, ep_index, kid)
                            if not video_path:
                                pass  # 下方统一检查
                            else:
                                audio_path = self._download_media_with_retry(task_id, audio_url, "audio", bvid, ep_index, kid)
                        else:
                            # 任务并发少(1-2)时，音视频并行下载以利用带宽
                            def _dl_v():
                                nonlocal video_path
                                video_path = self._download_media_with_retry(task_id, video_url, "video", bvid, ep_index, kid)

                            def _dl_a():
                                nonlocal audio_path
                                audio_path = self._download_media_with_retry(task_id, audio_url, "audio", bvid, ep_index, kid)

                            with ThreadPoolExecutor(max_workers=2) as executor:
                                v_future = executor.submit(_dl_v)
                                a_future = executor.submit(_dl_a)
                                for f in as_completed([v_future, a_future]):
                                    try:
                                        f.result()
                                    except Exception:
                                        raise
                    else:
                        video_path = self._download_media_with_retry(task_id, video_url, "video", bvid, ep_index, kid)

                    if not video_path:
                        self._mutex.lock()
                        task_info_check = self.active_tasks.get(task_id)
                        if not task_info_check:
                            task_info_check = self.paused_tasks.get(task_id)
                        is_paused = (task_id in self.paused_tasks) or (task_info_check is not None and task_info_check.get('is_paused'))
                        in_active = task_id in self.active_tasks
                        self._mutex.unlock()
                        if is_paused or not in_active:
                            return False, "TASK_PAUSED"
                        return False, "视频下载失败"
                    temp_files.append(video_path)

                    if has_audio and not audio_path:
                        self._mutex.lock()
                        task_info_check = self.active_tasks.get(task_id)
                        if not task_info_check:
                            task_info_check = self.paused_tasks.get(task_id)
                        is_paused = (task_id in self.paused_tasks) or (task_info_check is not None and task_info_check.get('is_paused'))
                        in_active = task_id in self.active_tasks
                        self._mutex.unlock()
                        if is_paused or not in_active:
                            return False, "TASK_PAUSED"
                        return False, "音频下载失败"
                    if audio_path:
                        temp_files.append(audio_path)

                    video_format = task_info.get('video_format', 'mp4')
                    output_path = os.path.join(task_info['save_path'], f"{clean_title}.{video_format}")
                    output_path = get_unique_filename(output_path)

                # 有声视频模式（download_content_type == 0）：处理合并逻辑
                # 仅音频/仅视频模式已在上方分支直接输出文件，无需合并
                if download_content_type == 0:
                    batch_download_first = self.config.get_app_setting("batch_download_first", False) if self.config else False

                    # 批量先下载后合并模式：仅在有声视频模式下有效
                    if batch_download_first and has_audio and download_content_type == 0:
                        # 批量先下载后合并模式：跳过合并，将合并信息存入待合并队列
                        self._mutex.lock()
                        if 'pending_merges' not in task_info:
                            task_info['pending_merges'] = []
                        task_info['pending_merges'].append({
                            'ep_index': ep_index,
                            'video_path': video_path,
                            'audio_path': audio_path,
                            'output_path': output_path,
                            'kid': kid,
                            'clean_title': clean_title,
                            'actual_codecid': ep_info_copy.get('actual_codecid', 0),
                        })
                        self._mutex.unlock()
                        self.episode_progress_updated.emit(task_id, ep_index, 100, "下载完成（等待合并）")
                        self.merge_started.emit(task_id, ep_index)
                        self.merge_finished.emit(task_id, ep_index)
                        logger.info(f"任务{task_id}：第{ep_index+1}集视频下载完成（待合并）")
                        # 不清理临时文件，合并时再清理
                    else:
                        # 默认模式：下载完立即合并
                        _vpm = task_info.get('video_process_mode', 'copy')
                        if _vpm == 're-encode':
                            merge_status = "正在重编码合并..."
                        else:
                            merge_status = "合并音视频..."
                        self.episode_progress_updated.emit(task_id, ep_index, 90, merge_status)
                        self.merge_started.emit(task_id, ep_index)

                        try:
                            if audio_path:
                                _tc_map = {'h264': 7, 'hevc': 12, 'av1': 13, 'vp9': 14}
                                _t_cc = _tc_map.get(task_info.get('video_output_codec', 'h264'), 0)
                                _a_cc = ep_info_copy.get('actual_codecid', 0)
                                _aq = task_info.get('audio_quality', 30280)
                                _aq_names = {0: "自动", 30251: "Hi-Res无损", 30250: "杜比全景声", 100010: "320K高音质", 30280: "192K高音质", 100009: "192K标准音质", 30232: "132K标准音质", 100008: "128K标准音质", 30216: "64K低音质"}
                                logger.info(f"任务{task_id}：合并参数 target_codecid={_t_cc}, actual_codecid={_a_cc}, audio_quality={_aq_names.get(_aq, _aq)}")
                                merge_result, merge_error = task_info['parser'].merge_media(video_path, audio_path, output_path, kid, target_codecid=_t_cc, actual_codecid=_a_cc, audio_quality=_aq, video_process_mode=task_info.get('video_process_mode', 'copy'))
                                if not merge_result:
                                    raise Exception(f"合并失败：{merge_error}" if merge_error else "合并失败")
                            else:
                                if os.path.exists(output_path):
                                    os.remove(output_path)
                                try:
                                    os.rename(video_path, output_path)
                                except Exception as e:
                                    shutil.move(video_path, output_path)

                            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                                from utils import verify_and_ensure_save
                                actual_path, saved = verify_and_ensure_save(output_path, source_path=video_path if not audio_path else None)
                                if saved and actual_path != output_path:
                                    output_path = actual_path
                                    logger.warning(f"任务{task_id}：合并后文件不在目标路径，已备用保存到：{output_path}")
                                elif not saved:
                                    raise Exception("合并后文件不存在且备用保存失败")

                            self.episode_progress_updated.emit(task_id, ep_index, 100, "合并完成")
                            self.merge_finished.emit(task_id, ep_index)
                            logger.info(f"任务{task_id}：第{ep_index+1}集视频下载完成")

                            self._clean_temp_files(temp_files)
                        except Exception as e:
                            if os.path.exists(output_path):
                                try:
                                    os.remove(output_path)
                                except:
                                    pass
                            raise Exception(f"合并失败：{str(e)}")
            
            if download_danmaku:
                try:
                    danmaku_idx = extra_offsets.get('danmaku', ep_index)
                    self.episode_progress_updated.emit(task_id, danmaku_idx, 0, "下载弹幕...")
                    cid = ep_info.get('cid', '')
                    if cid:
                        danmaku_format = task_info.get('danmaku_format', 'XML')
                        danmaku_result = task_info['parser'].get_danmaku(cid)
                        if danmaku_result.get('error') == "":
                            danmaku_list = danmaku_result.get('data', {}).get('danmaku', [])
                            if danmaku_list:
                                danmaku_content = task_info['parser'].convert_danmaku_format(danmaku_list, danmaku_format)
                                if danmaku_content:
                                    danmaku_ext = {
                                        'XML': '.xml',
                                        'ASS': '.ass',
                                        'SRT': '.srt',
                                        'JSON': '.json'
                                    }.get(danmaku_format, '.xml')
                                    danmaku_path = os.path.join(task_info['save_path'], f"{clean_title}{danmaku_ext}")
                                    with open(danmaku_path, 'w', encoding='utf-8') as f:
                                        f.write(danmaku_content)
                                    if not os.path.exists(danmaku_path) or os.path.getsize(danmaku_path) == 0:
                                        from utils import verify_and_ensure_save
                                        danmaku_path, danmaku_saved = verify_and_ensure_save(danmaku_path, content=danmaku_content)
                                        if not danmaku_saved:
                                            logger.warning(f"任务{task_id}：第{ep_index+1}集弹幕保存验证失败")
                                    logger.info(f"任务{task_id}：第{ep_index+1}集弹幕下载完成，保存为{danmaku_format}格式")
                                else:
                                    logger.warning(f"任务{task_id}：第{ep_index+1}集弹幕格式转换失败")
                            else:
                                logger.warning(f"任务{task_id}：第{ep_index+1}集无弹幕数据")
                        else:
                            logger.warning(f"任务{task_id}：第{ep_index+1}集获取弹幕失败：{danmaku_result.get('error', '未知错误')}")
                    else:
                        logger.warning(f"任务{task_id}：第{ep_index+1}集无cid，无法下载弹幕")
                except Exception as e:
                    logger.error(f"任务{task_id}：第{ep_index+1}集下载弹幕失败：{str(e)}")
                self.episode_progress_updated.emit(task_id, danmaku_idx, 100, "弹幕下载完成")

            if download_cover:
                try:
                    cover_idx = extra_offsets.get('cover', ep_index)
                    self.episode_progress_updated.emit(task_id, cover_idx, 0, "下载封面...")
                    cover_url = ep_info.get('cover', '')
                    if not cover_url:
                        cover_url = task_info['video_info'].get('pic', '')
                    if not cover_url:
                        if task_info['video_info'].get('is_bangumi') and task_info['video_info'].get('bangumi_info'):
                            cover_url = task_info['video_info']['bangumi_info'].get('cover', '')
                        elif task_info['video_info'].get('is_cheese') and task_info['video_info'].get('cheese_info'):
                            cover_url = task_info['video_info']['cheese_info'].get('cover', '')
                    if cover_url:
                        import requests as _req
                        resp = _req.get(cover_url, timeout=self.config.get_app_setting('network_timeout', 15) if self.config else 15, headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                            'Referer': 'https://www.bilibili.com/'
                        })
                        resp.raise_for_status()
                        cover_ext = cover_url.rsplit('.', 1)[-1].split('?')[0] if '.' in cover_url else 'png'
                        if cover_ext not in ('png', 'jpg', 'jpeg', 'bmp', 'webp'):
                            cover_ext = 'png'
                        cover_path = os.path.join(task_info['save_path'], f"{clean_title}_cover.{cover_ext}")
                        with open(cover_path, 'wb') as f:
                            f.write(resp.content)
                        logger.info(f"任务{task_id}：第{ep_index+1}集封面下载完成")
                    else:
                        logger.warning(f"任务{task_id}：第{ep_index+1}集无封面URL")
                except Exception as e:
                    logger.warning(f"任务{task_id}：第{ep_index+1}集下载封面失败：{str(e)}")
                self.episode_progress_updated.emit(task_id, cover_idx, 100, "封面下载完成")

            if download_subtitle:
                try:
                    subtitle_idx = extra_offsets.get('subtitle', ep_index)
                    self.episode_progress_updated.emit(task_id, subtitle_idx, 0, "下载字幕...")
                    cid = ep_info.get('cid', '')
                    bvid_for_sub = ep_info.get('bvid', task_info['video_info'].get('bvid', ''))
                    if cid:
                        import requests as _req2
                        sub_url = f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid_for_sub}&cid={cid}"
                        sub_resp = task_info['parser'].session.get(sub_url, timeout=task_info['parser'].config.get_app_setting('network_timeout', 15) if task_info['parser'].config else 15)
                        sub_data = sub_resp.json() if sub_resp.status_code == 200 else {}
                        subtitles = sub_data.get('data', {}).get('subtitle', {}).get('subtitles', [])
                        if subtitles:
                            for sub_info in subtitles:
                                sub_download_url = sub_info.get('subtitle_url', '')
                                sub_lang = sub_info.get('lan', 'unknown')
                                sub_lang_name = sub_info.get('lan_doc', sub_lang)
                                if sub_download_url:
                                    if not sub_download_url.startswith('http'):
                                        sub_download_url = 'https:' + sub_download_url
                                    sub_resp2 = _req2.get(sub_download_url, timeout=15, headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                        'Referer': 'https://www.bilibili.com/'
                                    })
                                    sub_resp2.raise_for_status()
                                    sub_content = sub_resp2.json()
                                    # B站字幕格式为JSON，转换为SRT
                                    srt_content = self._convert_subtitle_to_srt(sub_content)
                                    safe_lang = "".join(c for c in sub_lang_name if c.isalnum() or c in "_ -") or sub_lang
                                    sub_path = os.path.join(task_info['save_path'], f"{clean_title}_{safe_lang}.srt")
                                    with open(sub_path, 'w', encoding='utf-8') as f:
                                        f.write(srt_content)
                                    logger.info(f"任务{task_id}：第{ep_index+1}集字幕({sub_lang_name})下载完成")
                        else:
                            logger.warning(f"任务{task_id}：第{ep_index+1}集无字幕数据")
                    else:
                        logger.warning(f"任务{task_id}：第{ep_index+1}集无cid，无法下载字幕")
                except Exception as e:
                    logger.warning(f"任务{task_id}：第{ep_index+1}集下载字幕失败：{str(e)}")
                self.episode_progress_updated.emit(task_id, subtitle_idx, 100, "字幕下载完成")
            
            self._mutex.lock()
            task_info = self.active_tasks.get(task_id)
            if task_info:
                downloaded_episodes = task_info.get("downloaded_episodes", [])
                if ep_info not in downloaded_episodes:
                    downloaded_episodes.append(ep_info)
                    task_info["downloaded_episodes"] = downloaded_episodes
            self._mutex.unlock()
            
            end_time = time.time()
            duration = end_time - start_time
            duration_str = f"{duration:.2f}秒"
            
            completed_items = []
            has_media = download_video or download_audio
            if has_media and output_path and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                if download_video and download_audio:
                    completed_items.append(f"视频：{os.path.basename(output_path)}")
                elif download_video:
                    completed_items.append(f"画面：{os.path.basename(output_path)}")
                else:
                    completed_items.append(f"音频：{os.path.basename(output_path)}")
            if download_danmaku:
                completed_items.append("弹幕")
            if download_cover:
                completed_items.append("封面")
            if download_subtitle:
                completed_items.append("字幕")
            
            if completed_items:
                completed_msg = "完成：" + "、".join(completed_items)
                return True, f"{completed_msg}（耗时：{duration_str}）"
            else:
                return False, "未完成任何下载"

        except Exception as e:
            if str(e) == "TASK_PAUSED":
                return False, "TASK_PAUSED"
            end_time = time.time()
            duration = end_time - start_time
            duration_str = f"{duration:.2f}秒"
            err_msg = str(e)
            if "Remote end closed" in err_msg or "Read timed out" in err_msg:
                err_msg += "（网络问题，已自动重试）"
            if "ffmpeg" in err_msg.lower():
                err_msg += "（检查FFmpeg环境变量）"
            if "任务已取消" in err_msg:
                err_msg = "下载已取消"
            logger.error(f"任务{task_id}：第{ep_index+1}集处理失败 - {err_msg}，耗时：{duration_str}")

            if "任务已取消" not in err_msg:
                self._clean_temp_files(temp_files)
            return False, f"{err_msg}（耗时：{duration_str}）"

    def _clean_temp_files(self, temp_files):
        """清理批量下载产生的临时文件（增强版：处理占用、记录失败路径）

        删除失败的路径会记录到 temp/_pending_cleanup.txt，
        由 DownloadManager.cleanup_pending_temp_files() 在下次启动时清理。
        """
        import shutil
        failed_paths = []
        for file_path in temp_files:
            try:
                if not file_path or not os.path.exists(file_path):
                    continue
                try:
                    os.remove(file_path)
                    logger.debug(f"清理临时文件：{file_path}")
                except Exception:
                    # 删除失败可能是文件被占用，尝试强制删除
                    try:
                        shutil.rmtree(file_path, ignore_errors=True)
                    except Exception as e:
                        logger.warning(f"强制清理临时文件失败：{file_path}, {e}")
                        failed_paths.append(file_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败：{str(e)}")
                failed_paths.append(file_path)
        # 清理失败的路径记录到全局待清理列表，下次启动时清理
        if failed_paths:
            try:
                cache_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp", "_pending_cleanup.txt")
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                with open(cache_file, 'a', encoding='utf-8') as f:
                    for p in failed_paths:
                        f.write(p + "\n")
            except Exception:
                pass

    @staticmethod
    def cleanup_pending_temp_files():
        """启动时调用，清理上次遗留的临时文件（复用单视频版清理逻辑）"""
        EpisodeDownloadThread.cleanup_pending_temp_files()

    def _convert_subtitle_to_srt(self, subtitle_json):
        """将B站字幕JSON格式转换为SRT格式"""
        try:
            body = subtitle_json.get('body', [])
            if not body:
                return ""
            srt_lines = []
            for idx, item in enumerate(body, 1):
                start_ms = int(item.get('from', 0) * 1000)
                end_ms = int(item.get('to', 0) * 1000)
                start_h = start_ms // 3600000
                start_m = (start_ms % 3600000) // 60000
                start_s = (start_ms % 60000) // 1000
                start_ms_rem = start_ms % 1000
                end_h = end_ms // 3600000
                end_m = (end_ms % 3600000) // 60000
                end_s = (end_ms % 60000) // 1000
                end_ms_rem = end_ms % 1000
                time_str = (f"{start_h:02d}:{start_m:02d}:{start_s:02d},{start_ms_rem:03d}"
                           f" --> {end_h:02d}:{end_m:02d}:{end_s:02d},{end_ms_rem:03d}")
                content = item.get('content', '')
                srt_lines.append(f"{idx}\n{time_str}\n{content}\n")
            return "\n".join(srt_lines)
        except Exception:
            return ""

    def _get_media_urls_with_retry(self, bvid, ep_info):
        retry_count = 0
        max_retry = self.config.get_app_setting("max_retry", 3) if self.config else 3
        while True:
            try:
                return self._get_media_urls(bvid, ep_info)
            except Exception as e:
                error_str = str(e)

                episode_num = ep_info.get('ep_index', ep_info.get('page', 1))
                if any(keyword in error_str for keyword in ["Remote end closed", "Read timed out", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"第{episode_num}集获取链接失败，{delay}秒后重试")
                    time.sleep(delay)
                    continue
                elif any(keyword in error_str for keyword in ["403", "访问权限不足"]):

                    logger.error(f"第{episode_num}集权限不足，无法下载")
                    raise
                else:
                    retry_count += 1
                    if retry_count <= max_retry:
                        delay = min(retry_count, 3)
                        logger.warning(f"第{episode_num}集发生错误，{delay}秒后重试")
                        time.sleep(delay)
                        continue
                    else:
                        raise

    def _get_media_urls(self, bvid, ep_info):
        video_url = ""
        audio_url = ""
        kid = None
        try:
            task_id = ep_info.get('task_id')
            if not task_id:
                raise Exception("任务ID不存在")
            
            self._mutex.lock()
            task_info = self.active_tasks.get(task_id)
            self._mutex.unlock()
            
            if not task_info:
                raise Exception("任务信息不存在")
            
            video_output_codec = task_info.get('video_output_codec', 'h264')
            logger.info(f"[编码诊断] video_output_codec={video_output_codec}, selected_codecid={task_info.get('selected_codecid', 0)}")
            video_info = task_info['video_info']
            selected_qn = task_info['qn']
            parser = task_info['parser']
            
            if video_info.get('is_bangumi'):
                if 'video_urls' in ep_info:
                    video_urls = ep_info.get('video_urls', {})
                    if selected_qn not in video_urls:
                        selected_qn = max(video_urls.keys(), key=lambda k: int(k)) if video_urls else ''
                    video_url, actual_codecid = self._find_video_url(video_urls, selected_qn, task_info.get('selected_codecid', 0) if task_info else 0, task_info.get('video_output_codec', None) if task_info else None)
                    logger.info(f"[编码诊断] _find_video_url返回: actual_codecid={actual_codecid}, video_urls可用编码={[(k,v[:30]+'...') for k,v in video_urls.items() if isinstance(k,tuple)]}")
                    audio_url = ep_info.get('audio_url', '')
                    kid = ep_info.get('kid', None)
                    ep_info['actual_codecid'] = actual_codecid
                else:
                    audio_quality = task_info.get('audio_quality', 30280)
                    play_info = parser._get_play_info(
                        'bangumi',
                        bvid=ep_info.get('bvid', bvid),
                        cid=ep_info.get('cid', ''),
                        is_tv_mode=video_info.get('is_tv_mode', False),
                        ep_id=ep_info.get('ep_id', ''),
                        audio_quality=audio_quality
                    )
                    if not play_info['success']:
                        error = play_info.get('error', '番剧API失败')
                        if "访问权限不足" in error:
                            raise Exception("访问权限不足")
                        raise Exception(error)
                    video_urls = play_info['video_urls']
                    if selected_qn not in video_urls:
                        selected_qn = max(video_urls.keys(), key=lambda k: int(k)) if video_urls else ''
                    video_url, actual_codecid = self._find_video_url(video_urls, selected_qn, task_info.get('selected_codecid', 0) if task_info else 0, task_info.get('video_output_codec', None) if task_info else None)
                    audio_url = play_info.get('audio_url', '')
                    kid = play_info.get('kid', None)
                    ep_info['video_urls'] = video_urls
                    ep_info['audio_url'] = audio_url
                    ep_info['kid'] = kid
                    ep_info['actual_codecid'] = actual_codecid
            elif video_info.get('is_cheese'):
                video_urls = ep_info.get('video_urls', {})
                if not video_urls:
                    
                    season_id = ep_info.get('season_id', video_info.get('season_id', ''))
                    ep_id = ep_info.get('ep_id', '')
                    cid = ep_info.get('cid', '')
                    bvid = ep_info.get('bvid', bvid)
                    audio_quality = task_info.get('audio_quality', 30280)
                    play_info = parser._get_play_info(
                        'cheese',
                        bvid, 
                        cid, 
                        video_info.get('is_tv_mode', False),
                        season_id=season_id,
                        ep_id=ep_id,
                        audio_quality=audio_quality
                    )
                    if not play_info['success']:
                        error = play_info.get('error', '课程API失败')
                        if "访问权限不足" in error:
                            raise Exception("访问权限不足")
                        raise Exception(error)
                    video_urls = play_info['video_urls']
                    audio_url = play_info.get('audio_url', '')
                    kid = play_info.get('kid', None)
                    ep_info['video_urls'] = video_urls
                    ep_info['audio_url'] = audio_url
                    ep_info['kid'] = kid
                else:
                    audio_url = ep_info.get('audio_url', '')
                    kid = ep_info.get('kid', None)
                if selected_qn not in video_urls:
                    selected_qn = max(video_urls.keys(), key=lambda k: int(k)) if video_urls else ''
                video_url, actual_codecid = self._find_video_url(video_urls, selected_qn, task_info.get('selected_codecid', 0) if task_info else 0, task_info.get('video_output_codec', None) if task_info else None)
                ep_info['actual_codecid'] = actual_codecid
            else:
                video_urls = ep_info.get('video_urls', {})
                if not video_urls:

                    cid = ep_info.get('cid', '')
                    if not cid:

                        ep_detail = parser.get_single_episode_info(
                            media_type=video_info.get('type', ''),
                            media_id=bvid,
                            page=ep_info.get('page', 1),
                            is_tv_mode=video_info.get('is_tv_mode', False)
                        )
                        if not ep_detail.get('success'):
                            error = ep_detail.get('error', '单集API失败')
                            if "访问权限不足" in error:
                                raise Exception("访问权限不足")
                            raise Exception(error)
                        cid = ep_detail.get('cid', '')
                    
                    audio_quality = task_info.get('audio_quality', 30280)
                    play_info = parser._get_play_info(
                        media_type=video_info.get('type', ''),
                        bvid=bvid,
                        cid=cid,
                        is_tv_mode=video_info.get('is_tv_mode', False),
                        audio_quality=audio_quality
                    )
                    if not play_info['success']:
                        error = play_info.get('error', '播放信息获取失败')
                        if "访问权限不足" in error:
                            raise Exception("访问权限不足")
                        raise Exception(error)
                    video_urls = play_info['video_urls']
                    audio_url = play_info.get('audio_url', '')
                    kid = play_info.get('kid', None)

                    ep_info['video_urls'] = video_urls
                    ep_info['audio_url'] = audio_url
                    ep_info['kid'] = kid
                else:
                    # 即使有缓存的video_urls，也需要根据音频质量重新获取音频URL
                    cid = ep_info.get('cid', '')
                    if cid:
                        audio_quality = task_info.get('audio_quality', 30280)
                        play_info = parser._get_play_info(
                            media_type=video_info.get('type', ''),
                            bvid=bvid,
                            cid=cid,
                            is_tv_mode=video_info.get('is_tv_mode', False),
                            audio_quality=audio_quality
                        )
                        if play_info['success']:
                            audio_url = play_info.get('audio_url', '')
                            ep_info['audio_url'] = audio_url
                    else:
                        audio_url = ep_info.get('audio_url', '')
                    kid = ep_info.get('kid', None)

                if selected_qn not in video_urls:
                    selected_qn = max(video_urls.keys(), key=lambda k: int(k)) if video_urls else ''
                video_url, actual_codecid = self._find_video_url(video_urls, selected_qn, task_info.get('selected_codecid', 0) if task_info else 0, task_info.get('video_output_codec', None) if task_info else None)
                ep_info['actual_codecid'] = actual_codecid
            return video_url, audio_url, kid
        except Exception as e:
            error = str(e)
            if "访问权限不足" in error:
                raise Exception("访问权限不足")
            raise Exception(f"链接获取失败：{error}")

    def _download_media_with_retry(self, task_id, url, media_type, bvid, ep_index, kid=None):
        self._mutex.lock()
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            self._mutex.unlock()
            raise Exception("TASK_PAUSED")
        if task_info.get('is_paused'):
            self._mutex.unlock()
            raise Exception("TASK_PAUSED")
        if task_info['is_cancelled']:
            self._mutex.unlock()
            return None
        self._mutex.unlock()

        retry_count = 0
        max_retry = self.config.get_app_setting("max_retry", 3) if self.config else 3
        while True:
            try:
                logger.info(f"任务{task_id}：开始下载{media_type}流")
                return self._download_media(task_id, url, media_type, bvid, ep_index, kid)
            except Exception as e:
                if str(e) == "TASK_PAUSED":
                    raise
                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if not task_info:
                    task_info = self.paused_tasks.get(task_id)
                if not task_info or task_info.get('is_paused'):
                    self._mutex.unlock()
                    raise Exception("TASK_PAUSED")
                if task_info['is_cancelled']:
                    self._mutex.unlock()
                    return None
                self._mutex.unlock()

                if any(keyword in str(e) for keyword in ["Read timed out", "Remote end closed", "Connection aborted", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"任务{task_id}：{media_type}下载超时，{delay}秒后重试")
                    time.sleep(delay)
                    continue
                elif "403" in str(e) or "访问权限不足" in str(e):

                    logger.error(f"任务{task_id}：{media_type}下载权限不足，无法下载")
                    raise
                else:
                    retry_count += 1
                    if retry_count <= max_retry:
                        delay = min(retry_count, 3)
                        logger.warning(f"任务{task_id}：{media_type}下载错误，{delay}秒后重试")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"{media_type}下载失败：{str(e)}")

    def _download_media(self, task_id, url, media_type, bvid, ep_index, kid=None):
        if not url:
            logger.error(f"任务{task_id}：{media_type}流下载失败，URL为空")
            return None

        self._mutex.lock()
        task_info = self.active_tasks.get(task_id)
        if not task_info:
            task_info = self.paused_tasks.get(task_id)
        if not task_info:
            self._mutex.unlock()
            raise Exception("TASK_PAUSED")
        if task_info.get('is_paused'):
            self._mutex.unlock()
            raise Exception("TASK_PAUSED")
        if task_info['is_cancelled']:
            self._mutex.unlock()
            return None
        self._mutex.unlock()


        if not task_info.get('save_path'):
            logger.error(f"任务{task_id}：保存路径未设置")
            return None

        start_time = time.time()
        last_time = start_time
        last_size = 0
        last_progress = -1

        def progress_cb(p, downloaded_size=0, chunk_progresses=None):
                nonlocal start_time, last_time, last_size, last_progress
                
                current_time = time.time()
                time_diff = current_time - last_time
                size_diff = downloaded_size - last_size
                
                speed = 0
                if time_diff > 0:
                    speed = size_diff / time_diff
                
                speed_str = ""
                if speed > 1024 * 1024:
                    speed_str = f"{speed / (1024 * 1024):.2f} MB/s"
                elif speed > 1024:
                    speed_str = f"{speed / 1024:.2f} KB/s"
                elif speed > 0:
                    speed_str = f"{speed:.2f} B/s"
                
                eta_str = ""
                if speed > 0 and p > 0 and p < 100:
                    elapsed = current_time - start_time
                    if elapsed > 0:
                        remaining_pct = 100 - p
                        eta_seconds = elapsed * remaining_pct / p
                        if eta_seconds > 3600:
                            eta_str = f" 剩余{int(eta_seconds // 3600)}时{int((eta_seconds % 3600) // 60)}分"
                        elif eta_seconds > 60:
                            eta_str = f" 剩余{int(eta_seconds // 60)}分{int(eta_seconds % 60)}秒"
                        else:
                            eta_str = f" 剩余{int(eta_seconds)}秒"
    
                status = f"下载{media_type}流：{p}%"
                if speed_str:
                    status += f" ({speed_str})"
                if eta_str:
                    status += eta_str
                
                if p % 10 == 0:
                    logger.debug(f"任务{task_id}：{status}")

                # 节流：仅在进度变化 >= 3% 或时间间隔 >= 1.5 秒时才发射信号和加锁检查状态
                # 避免多线程并发下载时 mutex 争用 + 信号洪泛导致 UI 线程饥饿（"未响应"）
                current_progress = int(p)
                if abs(current_progress - last_progress) >= 3 or time_diff >= 1.5:
                    # 只需一次锁：更新进度并检查任务状态（原代码每次回调加锁2次）
                    self._mutex.lock()
                    task_info = self.active_tasks.get(task_id)
                    if task_info:
                        task_info['progress'] = self._calc_total_progress(p)
                        if 'episode_progress' not in task_info:
                            task_info['episode_progress'] = {}
                        task_info['episode_progress'][str(ep_index)] = task_info['progress']
                        cancelled = task_info.get('is_cancelled', False)
                        paused = task_info.get('is_paused', False)
                    else:
                        task_info = self.paused_tasks.get(task_id)
                        cancelled = task_info.get('is_cancelled', False) if task_info else False
                        paused = True if task_info else False
                    self._mutex.unlock()

                    # 将分片进度编码到状态字符串中，供UI层解析
                    emit_status = status
                    if chunk_progresses:
                        import json
                        try:
                            emit_status = f"__CHUNKS__{json.dumps(chunk_progresses)}__ {status}"
                        except Exception:
                            pass
                    self.episode_progress_updated.emit(task_id, ep_index, self._calc_total_progress(p), emit_status)
                    last_time = current_time
                    last_size = downloaded_size
                    last_progress = current_progress

                    if cancelled:
                        raise Exception("任务已取消")
                    if paused:
                        raise Exception("TASK_PAUSED")

        def is_running():
            # 用 tryLock 避免与 progress_cb 争抢 mutex；锁不上时假定仍在运行（避免误中断）
            # 实际的取消/暂停检查在 progress_cb 节流回调中执行
            if self._mutex.tryLock(10):
                try:
                    task_info = self.active_tasks.get(task_id)
                    if not task_info:
                        task_info = self.paused_tasks.get(task_id)
                    running = task_info and not task_info.get('is_cancelled', False) and not task_info.get('is_paused', False)
                    return running
                finally:
                    self._mutex.unlock()
            return True

        try:
            logger.info(f"任务{task_id}：开始下载{media_type}流，线程：{threading.current_thread().name}")
            file_path = task_info['parser'].download_file(
                url=url,
                save_path=task_info['save_path'],
                progress_callback=progress_cb,
                file_type=media_type,
                bvid=bvid,
                is_running=is_running,
                kid=kid
            )
            if file_path and os.path.exists(file_path):
                logger.info(f"任务{task_id}：{media_type}流下载完成")
                return file_path
            logger.warning(f"任务{task_id}：{media_type}流下载返回空文件路径")
            return None
        except Exception as e:
            if str(e) == "TASK_PAUSED":
                logger.info(f"任务{task_id}：{media_type}流下载暂停")
                raise
            if "任务已取消" in str(e) or "下载已取消" in str(e):
                logger.info(f"任务{task_id}：{media_type}流下载被取消")
                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if not task_info:
                    task_info = self.paused_tasks.get(task_id)
                is_paused = (task_id in self.paused_tasks) or (task_info is not None and task_info.get('is_paused'))
                self._mutex.unlock()
                if is_paused:
                    raise Exception("TASK_PAUSED")
                return None
            logger.error(f"任务{task_id}：{media_type}流下载失败：{str(e)}")
            raise

    def _calc_total_progress(self, p):

        try:
            p = float(p)
            p = max(0, min(100, p))

            return p
        except (ValueError, TypeError):

            return 0

    def _monitor_tasks(self, task_id):
        import threading
        
        def monitor():
            try:
                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if not task_info:
                    self._mutex.unlock()
                    return
                self._mutex.unlock()

                completed_tasks = 0
                total_tasks = len(task_info['futures'])
                
                future_to_index = {future: idx for idx, future in enumerate(task_info['futures'])}
                
                for future in as_completed(task_info['futures']):
                    self._mutex.lock()
                    task_info = self.active_tasks.get(task_id)
                    if not task_info or task_info['is_cancelled'] or task_info.get('is_paused'):
                        self._mutex.unlock()
                        break
                    self._mutex.unlock()

                    try:
                        success, message = future.result()
                        ep_index = future_to_index.get(future, 0)
                        
                        if message == "TASK_PAUSED":
                            continue
                        
                        if not success:
                            max_retries = self.config.get_app_setting("max_retry", 3) if self.config else 3
                            try:
                                max_retries = int(max_retries)
                            except (ValueError, TypeError):
                                max_retries = 3
                            for retry in range(1, max_retries + 1):
                                logger.info(f"任务{task_id}：第{ep_index+1}集下载失败，自动重试 {retry}/{max_retries}...")
                                try:
                                    self._mutex.lock()
                                    task_info = self.active_tasks.get(task_id)
                                    if not task_info or task_info['is_cancelled'] or task_info.get('is_paused'):
                                        self._mutex.unlock()
                                        break
                                    video_info = task_info.get('video_info', {})
                                    bvid = video_info.get('bvid', '')
                                    is_tv_mode = video_info.get('is_tv_mode', False)
                                    parser = task_info.get('parser')
                                    episodes_list = task_info.get('episodes', [])
                                    retry_ep_info = episodes_list[ep_index] if ep_index < len(episodes_list) else {}
                                    self._mutex.unlock()
                                    
                                    new_media_info = None
                                    if parser and bvid:
                                        try:
                                            new_media_info = parser.parse_media("video", bvid, is_tv_mode)
                                        except Exception as parse_err:
                                            logger.warning(f"任务{task_id}：重试解析失败：{parse_err}")
                                    
                                    if new_media_info and new_media_info.get('success'):
                                        new_video_urls = new_media_info.get('video_urls', {})
                                        new_audio_url = new_media_info.get('audio_url', '')
                                        new_qualities = new_media_info.get('qualities', [])
                                        if new_video_urls or new_audio_url:
                                            self._mutex.lock()
                                            task_info = self.active_tasks.get(task_id)
                                            if task_info:
                                                task_info['video_info'].update({
                                                    'video_urls': new_video_urls,
                                                    'audio_url': new_audio_url,
                                                })
                                                if new_qualities:
                                                    task_info['video_info']['qualities'] = new_qualities
                                                if ep_index < len(task_info.get('episodes', [])):
                                                    task_info['episodes'][ep_index].update({
                                                        'video_urls': new_video_urls,
                                                        'audio_url': new_audio_url,
                                                    })
                                            self._mutex.unlock()
                                            logger.info(f"任务{task_id}：重试解析成功，获取到新链接")
                                    
                                    retry_success, retry_message = self._download_episode(task_id, ep_index, retry_ep_info)
                                    if retry_success:
                                        success = True
                                        message = retry_message
                                        logger.info(f"任务{task_id}：第{ep_index+1}集重试成功")
                                        break
                                    else:
                                        logger.warning(f"任务{task_id}：第{ep_index+1}集重试 {retry} 失败：{retry_message}")
                                        import time as retry_time
                                        retry_time.sleep(retry * 2)
                                except Exception as retry_err:
                                    logger.error(f"任务{task_id}：第{ep_index+1}集重试异常：{retry_err}")
                        
                        self._mutex.lock()
                        task_info = self.active_tasks.get(task_id)
                        if task_info:
                            if success:
                                task_info['completed_episodes'] += 1
                            else:
                                task_info['failed_episodes'] += 1
                            completed_tasks += 1
                            total_processed = task_info['completed_episodes'] + task_info['failed_episodes']
                        self._mutex.unlock()

                        try:
                            self.episode_finished.emit(task_id, ep_index, success, message)
                            logger.info(f"任务{task_id}：结果：第{ep_index+1}集 {'成功' if success else '失败'} - {message}")
                        except RuntimeError:
            
                            logger.warning("DownloadManager对象已被删除，无法发送信号")
                            return

                        self._mutex.lock()
                        task_info = self.active_tasks.get(task_id)
                        if task_info:
                            global_progress = (total_processed * 100) // task_info['total_episodes']
                            try:
                                self.global_progress_updated.emit(
                                    global_progress,
                                    f"任务{task_id}：{task_info['completed_episodes']}完成 / {task_info['failed_episodes']}失败（{total_processed}/{task_info['total_episodes']}）"
                                )
                            except RuntimeError:
                
                                logger.warning("DownloadManager对象已被删除，无法发送信号")
                                return
                            
                            if self.task_manager:
                                self.task_manager.update_task_progress(task_id, global_progress)
                                try:
                                    self.task_status_changed.emit(task_id)
                                except RuntimeError:
                    
                                    logger.warning("DownloadManager对象已被删除，无法发送信号")
                                    return
                        self._mutex.unlock()
                    except Exception as e:
                        if "CancelledError" in type(e).__name__:
                            logger.info(f"任务{task_id}：future被取消（暂停或取消）")
                            continue
                        logger.error(f"任务{task_id}：处理任务结果失败：{str(e)}")
                        self._mutex.lock()
                        task_info = self.active_tasks.get(task_id)
                        if task_info:
                            task_info['failed_episodes'] += 1
                            completed_tasks += 1
                        self._mutex.unlock()

                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                was_paused = task_id in self.paused_tasks
                if task_info and not task_info['is_cancelled'] and completed_tasks == total_tasks:
                    # 批量先下载后合并模式：所有下载完成后统一合并
                    pending_merges = task_info.get('pending_merges', [])
                    if pending_merges:
                        self._mutex.unlock()
                        merge_total = len(pending_merges)
                        merge_completed = 0
                        merge_failed = 0
                        logger.info(f"任务{task_id}：开始批量合并{merge_total}个视频...")
                        try:
                            self.global_progress_updated.emit(90, f"任务{task_id}：开始批量合并{merge_total}个视频...")
                        except RuntimeError:
                            pass

                        for merge_info in pending_merges:
                            self._mutex.lock()
                            task_info = self.active_tasks.get(task_id)
                            if not task_info or task_info['is_cancelled']:
                                self._mutex.unlock()
                                break
                            self._mutex.unlock()

                            ep_idx = merge_info['ep_index']
                            v_path = merge_info['video_path']
                            a_path = merge_info['audio_path']
                            o_path = merge_info['output_path']
                            kid = merge_info['kid']

                            _vpm_batch = task_info.get('video_process_mode', 'copy')
                            if _vpm_batch == 're-encode':
                                merge_status_batch = "正在重编码合并..."
                            else:
                                merge_status_batch = "合并音视频..."
                            self.episode_progress_updated.emit(task_id, ep_idx, 90, merge_status_batch)
                            self.merge_started.emit(task_id, ep_idx)

                            try:
                                _tc_map3 = {'h264': 7, 'hevc': 12, 'av1': 13, 'vp9': 14}
                                _t_cc3 = _tc_map3.get(task_info.get('video_output_codec', 'h264'), 0)
                                _a_cc3 = merge_info.get('actual_codecid', 0)
                                _aq3 = task_info.get('audio_quality', 30280)
                                _vpm3 = task_info.get('video_process_mode', 'copy')
                                _aq3_names = {0: "自动", 30251: "Hi-Res无损", 30250: "杜比全景声", 100010: "320K高音质", 30280: "192K高音质", 100009: "192K标准音质", 30232: "132K标准音质", 100008: "128K标准音质", 30216: "64K低音质"}
                                logger.info(f"任务{task_id}批量合并：target_codecid={_t_cc3}, actual_codecid={_a_cc3}, audio_quality={_aq3_names.get(_aq3, _aq3)}, video_process_mode={_vpm3}")
                                merge_result, merge_error = task_info['parser'].merge_media(v_path, a_path, o_path, kid, target_codecid=_t_cc3, actual_codecid=_a_cc3, audio_quality=_aq3, video_process_mode=_vpm3)
                                if not merge_result:
                                    raise Exception(f"合并失败：{merge_error}" if merge_error else "合并失败")

                                if not os.path.exists(o_path) or os.path.getsize(o_path) == 0:
                                    from utils import verify_and_ensure_save
                                    actual_path, saved = verify_and_ensure_save(o_path)
                                    if saved and actual_path != o_path:
                                        o_path = actual_path
                                    elif not saved:
                                        raise Exception("合并后文件不存在且备用保存失败")

                                merge_completed += 1
                                self.episode_progress_updated.emit(task_id, ep_idx, 100, "合并完成")
                                self.merge_finished.emit(task_id, ep_idx)
                                logger.info(f"任务{task_id}：第{ep_idx+1}集合并完成")
                                self._clean_temp_files([v_path, a_path])
                            except Exception as e:
                                merge_failed += 1
                                logger.error(f"任务{task_id}：第{ep_idx+1}集合并失败 - {str(e)}")
                                self.episode_progress_updated.emit(task_id, ep_idx, 100, f"合并失败：{str(e)}")
                                self._clean_temp_files([v_path, a_path])
                                if os.path.exists(o_path):
                                    try:
                                        os.remove(o_path)
                                    except:
                                        pass

                        if merge_failed > 0:
                            task_info['failed_episodes'] += merge_failed
                            task_info['completed_episodes'] -= merge_failed

                        logger.info(f"任务{task_id}：批量合并完成，成功{merge_completed}个，失败{merge_failed}个")
                        try:
                            self.global_progress_updated.emit(95, f"任务{task_id}：批量合并完成，成功{merge_completed}个，失败{merge_failed}个")
                        except RuntimeError:
                            pass

                        self._mutex.lock()
                        task_info = self.active_tasks.get(task_id)

                    task_end_time = time.time()
                    total_duration = task_end_time - task_info['task_start_time']
                    total_duration_str = f"{total_duration:.2f}秒"
                    logger.info(f"任务{task_id}：全部下载完成！成功{task_info['completed_episodes']}集，失败{task_info['failed_episodes']}集，总耗时：{total_duration_str}")
                    try:
                        self.global_progress_updated.emit(100, f"任务{task_id}：全部完成！成功{task_info['completed_episodes']} 失败{task_info['failed_episodes']}，总耗时：{total_duration_str}")
                    except RuntimeError:
        
                        logger.warning("DownloadManager对象已被删除，无法发送信号")
                        self._mutex.unlock()
                        return
                    
                    if self.task_manager:
                        task_data = {
                            "duration": total_duration_str,
                            "progress": 100,
                            "completed_episodes": task_info['completed_episodes'],
                            "failed_episodes": task_info['failed_episodes'],
                            "downloaded_episodes": task_info.get('downloaded_episodes', []),
                            "task_end_time": datetime.now().isoformat(),
                        }
                        if task_info['failed_episodes'] > 0:
                            self.task_manager.update_task_status(task_id, "failed", f"部分失败：成功{task_info['completed_episodes']}集，失败{task_info['failed_episodes']}集", task_data)
                        else:
                            self.task_manager.update_task_status(task_id, "completed", f"成功{task_info['completed_episodes']}集，总耗时：{total_duration_str}", task_data)
                        try:
                            self.task_status_changed.emit(task_id)
                        except RuntimeError:
            
                            logger.warning("DownloadManager对象已被删除，无法发送信号")
                    
                    try:
                        self.all_finished.emit()
                    except RuntimeError:

                        logger.warning("DownloadManager对象已被删除，无法发送信号")
                self._mutex.unlock()
                
                if not was_paused:
                    self._cleanup_task(task_id)
                else:
                    logger.info(f"任务{task_id}：暂停中，跳过清理")
            except Exception as e:
                logger.error(f"任务{task_id}：监控任务失败：{str(e)}")
                try:
                    self._mutex.unlock()
                except:
                    pass
                try:
                    self._cleanup_task(task_id)
                except Exception as cleanup_e:
                    logger.error(f"任务{task_id}：清理任务失败：{str(cleanup_e)}")
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    def _cleanup_task(self, task_id):
        self._mutex.lock()
        try:
            task_info = self.active_tasks.get(task_id)
            if task_info:
                try:
                    
                    if task_info.get('executor'):
                        try:
                            
                            task_info['executor'].shutdown(wait=False, cancel_futures=True)
                        except TypeError:
                            
                            task_info['executor'].shutdown(wait=False)
                        task_info['executor'] = None
                    
                    
                    if 'futures' in task_info:
                        task_info['futures'] = []
                    
                    
                    if 'parser' in task_info:
                        try:
                            del task_info['parser']
                        except Exception as e:
                            logger.error(f"任务{task_id}：清理解析器失败：{str(e)}")
                    
                    
                    for key in list(task_info.keys()):
                        if key not in ['id', 'url', 'title', 'status']:
                            try:
                                del task_info[key]
                            except Exception:
                                pass
                except Exception as e:
                    logger.error(f"任务{task_id}：清理任务失败：{str(e)}")
                finally:
                    
                    if task_id in self.active_tasks:
                        del self.active_tasks[task_id]
                    logger.info(f"任务{task_id}：任务已清理")
                    
                    self._task_condition.wakeOne()
        except Exception as e:
            logger.error(f"任务{task_id}：清理任务时发生异常：{str(e)}")
        finally:
            self._mutex.unlock()

    def pause_task(self, task_id):
        logger.info(f"暂停任务：{task_id}")
        self._mutex.lock()
        task_info = self.active_tasks.get(task_id)
        if task_info:

            task_info['is_paused'] = True

            task_info['paused_progress'] = task_info.get('progress', 0)

            task_info['downloaded_episodes'] = task_info.get('downloaded_episodes', [])

            if not 'episode_progress' in task_info:
                task_info['episode_progress'] = {}

            if task_info.get('executor'):
                try:

                    task_info['executor'].shutdown(wait=False, cancel_futures=True)
                except TypeError:

                    task_info['executor'].shutdown(wait=False)
            

            self.paused_tasks[task_id] = task_info
            del self.active_tasks[task_id]
            

            if self.task_manager:
                self.task_manager.update_task_status(task_id, "paused", "下载已暂停")
                self.task_status_changed.emit(task_id)
            
            logger.info(f"任务{task_id}已暂停")
        self._mutex.unlock()

    def resume_task(self, task_id):
        logger.info(f"继续任务：{task_id}")
        self._mutex.lock()
        task_info = self.paused_tasks.get(task_id)
        if task_info:

            del self.paused_tasks[task_id]
            

            task_info['is_paused'] = False
            task_info['is_cancelled'] = False
            task_info['task_start_time'] = time.time()

            if 'paused_progress' in task_info:
                task_info['progress'] = task_info['paused_progress']
                del task_info['paused_progress']
            

            downloaded_episodes = task_info.get('downloaded_episodes', [])
            task_info['completed_episodes'] = len(downloaded_episodes)
            task_info['failed_episodes'] = 0
            

            self.active_tasks[task_id] = task_info
            

            if self.task_manager:
                self.task_manager.update_task_status(task_id, "downloading", "继续下载")
                self.task_status_changed.emit(task_id)
            

            try:
        
                from config import ConfigLoader
                config = ConfigLoader()
                task_parser = BilibiliParser(config=config)
                task_info['parser'] = task_parser
                
                task_info['executor'] = ThreadPoolExecutor(max_workers=self.max_threads)
                task_info['futures'] = []
                

                downloaded_episode_ids = set()
                for ep in downloaded_episodes:
                    ep_id = ep.get('ep_index') or ep.get('page') or ep.get('cid')
                    if ep_id is not None:
                        downloaded_episode_ids.add(str(ep_id))
                

                episode_progress = task_info.get('episode_progress', {})
                
                for idx, ep in enumerate(task_info['episodes']):

                    ep_id = ep.get('ep_index') or ep.get('page') or ep.get('cid')
                    if ep_id is not None and str(ep_id) in downloaded_episode_ids:

                        self.episode_progress_updated.emit(task_id, idx, 100, "已完成")
                        continue
    

                    output_exists = False
                    if task_info.get('save_path'):
                        try:
                            is_bangumi = task_info.get('video_info', {}).get('is_bangumi', False)
                            bangumi_info = task_info.get('video_info', {}).get('bangumi_info', {})
                            if is_bangumi and bangumi_info:
                                season = bangumi_info.get('season_title', '未知季度')
                                ep_idx = ep.get('ep_index', '未知集')
                                title_candidates = [ep.get('ep_title', ''), ep.get('title', ''), ep.get('name', '')]
                                actual_title = next((t for t in title_candidates if t), '')
                                if actual_title:
                                    check_title = f"{season}_{ep_idx}_{actual_title}"
                                else:
                                    check_title = f"{season}_{ep_idx}"
                            else:
                                title_candidates = [ep.get('ep_title', ''), ep.get('title', ''), ep.get('name', '')]
                                actual_title = next((t for t in title_candidates if t), '')
                                check_title = actual_title if actual_title else f"第{idx+1}集"
                            for c in illegal_filename_chars():
                                check_title = check_title.replace(c, '_')
                            check_title = check_title[:30]
                            check_title = check_title.replace("正片_", "")
                            video_format = task_info.get('video_format', 'mp4')
                            output_path = os.path.join(task_info['save_path'], f"{check_title}.{video_format}")
                            if os.path.exists(output_path):
                                output_exists = True
                                logger.info(f"任务{task_id}：第{idx+1}集文件已存在，跳过")
                        except Exception:
                            pass
                    
                    if output_exists:
                        self.episode_progress_updated.emit(task_id, idx, 100, "已完成")
                        current_downloaded = task_info.get("downloaded_episodes", [])
                        if ep not in current_downloaded:
                            current_downloaded.append(ep)
                            task_info["downloaded_episodes"] = current_downloaded
                            task_info['completed_episodes'] = len(current_downloaded)
                        continue
                    
                    ep_progress = episode_progress.get(str(idx), 0)
                    

                    self.episode_progress_updated.emit(task_id, idx, ep_progress, "继续下载...")
                    future = task_info['executor'].submit(self._download_episode, task_id, idx, ep)
                    task_info['futures'].append(future)
                
                self._monitor_tasks(task_id)
                logger.info(f"任务{task_id}已继续")
            except Exception as e:
                logger.error(f"任务{task_id}继续失败：{str(e)}")
        self._mutex.unlock()

    def cancel_task(self, task_id):
        logger.info(f"取消任务：{task_id}")
        self._mutex.lock()
        try:

            if task_id in self.active_tasks:
                task_info = self.active_tasks[task_id]
                task_info['is_cancelled'] = True
                
    
                if task_info.get('executor'):
                    try:
    
                        task_info['executor'].shutdown(wait=False, cancel_futures=True)
                    except TypeError:
    
                        task_info['executor'].shutdown(wait=False)
                

                del self.active_tasks[task_id]
                logger.info(f"任务{task_id}已从活动任务列表中移除")

                # 更新task_manager中的任务状态为cancelled，避免重复检测时误判
                if self.task_manager:
                    self.task_manager.update_task_status(task_id, "cancelled", "下载已取消")
                    try:
                        self.task_status_changed.emit(task_id)
                    except RuntimeError:
                        pass
            

            elif task_id in self.paused_tasks:
                del self.paused_tasks[task_id]
                logger.info(f"任务{task_id}已从暂停任务列表中移除")
            

            else:

                new_queue = []
                for task in self.task_queue:
                    if task.get('task_id') != task_id:
                        new_queue.append(task)
                self.task_queue = new_queue
                logger.info(f"任务{task_id}已从任务队列中移除")
            
    
            self._task_condition.wakeOne()
        finally:
            self._mutex.unlock()

    def cancel_all(self):
        logger.info("开始取消所有下载任务")
        self._shutting_down = True
        self._mutex.lock()
        task_ids = list(self.active_tasks.keys())
        for task_id in task_ids:
            self.active_tasks[task_id]['is_cancelled'] = True

        paused_ids = list(self.paused_tasks.keys())
        for task_id in paused_ids:
            self.paused_tasks[task_id]['is_cancelled'] = True

        self.task_queue.clear()
        self._mutex.unlock()

        self._task_condition.wakeAll()

        try:
            self.global_progress_updated.emit(0, "正在取消所有下载...")
        except RuntimeError:
            logger.warning("DownloadManager对象已被删除，无法发送信号")

        for task_id in task_ids:
            try:
                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if task_info and task_info.get('executor'):
                    executor = task_info['executor']
                    self._mutex.unlock()
                    try:
                        executor.shutdown(wait=False, cancel_futures=True)
                    except TypeError:
                        executor.shutdown(wait=False)
                    logger.info(f"任务{task_id}：线程池已关闭")
                else:
                    self._mutex.unlock()
            except Exception as e:
                logger.error(f"任务{task_id}：关闭线程池失败：{str(e)}")

        # 更新task_manager中所有活动任务的状态为cancelled
        if self.task_manager:
            for task_id in task_ids:
                self.task_manager.update_task_status(task_id, "cancelled", "下载已取消")
            for task_id in paused_ids:
                self.task_manager.update_task_status(task_id, "cancelled", "下载已取消")

        self._mutex.lock()
        self.active_tasks.clear()
        self.paused_tasks.clear()
        self._mutex.unlock()

        logger.info("所有下载已取消")
        try:
            self.global_progress_updated.emit(0, "所有下载已取消")
            self.all_finished.emit()
        except RuntimeError:
            logger.warning("DownloadManager对象已被删除，无法发送信号")