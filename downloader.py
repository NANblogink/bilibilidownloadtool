# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
import os
import time
import shutil
from functools import partial
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QMutex, QWaitCondition
from utils import get_unique_filename

try:
    from logger_config import logger
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)

from typing import Tuple
Task = Tuple[int, dict]


class EpisodeDownloadThread(QThread):
    progress_updated = pyqtSignal(int, int, str)
    episode_finished = pyqtSignal(int, bool, str)
    thread_destroyed = pyqtSignal()

    def __init__(self, ep_index, ep_info, video_info, selected_qn, save_path, parser):
        super().__init__()
        self.ep_index = ep_index
        self.ep_info = ep_info
        self.video_info = video_info
        self.selected_qn = selected_qn
        self.save_path = save_path
        self.parser = parser
        self._is_running = True
        self.ep_title = f"第{ep_index+1}集_未知标题"
        self.temp_files = []
        self._mutex = QMutex()
        logger.info(f"线程{ep_index}：开始下载")

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
            video_url, audio_url = self._get_media_urls_with_retry(bvid)
            if not video_url:
                raise Exception("无有效视频链接")

            video_path = self._download_media_with_retry(video_url, "video", bvid)
            if not video_path or not self.is_running:
                return

            audio_path = None
            if audio_url and self.is_running:
                audio_path = self._download_media_with_retry(audio_url, "audio", bvid)
                if not audio_path:
                    return

            if self.is_running:
                self._merge_media(video_path, audio_path)

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
            else:
                self.ep_title = self.ep_info.get('title', f"第{self.ep_index+1}集")
            for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                self.ep_title = self.ep_title.replace(c, '_')
            self.ep_title = self.ep_title[:30]
        except Exception as e:
            print(f"标题初始化错误: {e}")
            self.ep_title = f"第{self.ep_index+1}集"

    def _check_save_path(self):
        try:
            if not os.path.exists(self.save_path):
                os.makedirs(self.save_path, exist_ok=True)
        except Exception as e:
            raise Exception(f"保存路径异常：{str(e)}")

    def _get_media_urls_with_retry(self, bvid):
        retry_count = 0
        while self.is_running:
            try:
                return self._get_media_urls(bvid)
            except Exception as e:
                if any(keyword in str(e) for keyword in ["Remote end closed", "Read timed out", "403", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"线程{self.ep_index}：获取链接失败，{delay}秒后重试")
                    self.progress_updated.emit(self.ep_index, 0, f"网络错误，{delay}秒后重试...")
                    self.msleep(delay*1000)
                    continue
                elif "下载已取消" in str(e):
                    raise
                else:
                    retry_count += 1
                    if retry_count <= 3:
                        delay = min(retry_count, 3)
                        logger.warning(f"线程{self.ep_index}：发生错误，{delay}秒后重试")
                        self.msleep(delay*1000)
                        continue
                    else:
                        raise

    def _get_media_urls(self, bvid):
        video_url = ""
        audio_url = ""
        try:
            if self.video_info.get('is_bangumi'):
                play_info = self.parser.get_bangumi_episode_playinfo(
                    bvid=self.ep_info.get('bvid', bvid),
                    cid=self.ep_info.get('cid', ''),
                    quality=self.selected_qn
                )
                if not play_info.get('success'):
                    raise Exception(play_info.get('error', '番剧API失败'))
                video_url = play_info.get('video_url', '')
                audio_url = play_info.get('audio_url', '')
            else:
                if not self.ep_info.get('video_urls'):
                    ep_detail = self.parser.get_single_episode_info(
                        media_type=self.video_info.get('type', ''),
                        media_id=bvid,
                        page=self.ep_info.get('page', 1),
                        is_tv_mode=self.video_info.get('is_tv_mode', False)
                    )
                    if not ep_detail.get('success'):
                        raise Exception(ep_detail.get('error', '单集API失败'))
                    self.ep_info = ep_detail

                video_urls = self.ep_info.get('video_urls', {})
                selected_qn = str(self.selected_qn)
                if selected_qn not in video_urls:
                    selected_qn = list(video_urls.keys())[0] if video_urls else ''
                video_url = video_urls.get(selected_qn, '')
                audio_url = self.ep_info.get('audio_url', '')
            return video_url, audio_url
        except Exception as e:
            raise Exception(f"链接获取失败：{str(e)}")

    def _download_media_with_retry(self, url, media_type, bvid):
        retry_count = 0
        while self.is_running:
            try:
                logger.info(f"线程{self.ep_index}：开始下载{media_type}流")
                return self._download_media(url, media_type, bvid)
            except Exception as e:
                if any(keyword in str(e) for keyword in ["Read timed out", "Remote end closed", "Connection aborted", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"线程{self.ep_index}：{media_type}下载超时，{delay}秒后重试")
                    current_progress = self._calc_total_progress(0, media_type)
                    self.progress_updated.emit(self.ep_index, current_progress, f"{media_type}下载超时，{delay}秒后重试...")
                    self.msleep(delay * 1000)
                    continue
                elif "下载已取消" in str(e):
                    raise
                else:
                    retry_count += 1
                    if retry_count <= 3:
                        delay = min(retry_count, 3)
                        logger.warning(f"线程{self.ep_index}：{media_type}下载错误，{delay}秒后重试")
                        current_progress = self._calc_total_progress(0, media_type)
                        self.progress_updated.emit(self.ep_index, current_progress, f"{media_type}下载错误，{delay}秒后重试...")
                        self.msleep(delay * 1000)
                        continue
                    else:
                        raise Exception(f"{media_type}下载失败：{str(e)}")

    def _download_media(self, url, media_type, bvid):
        if not url:
            return None

        start_time = time.time()
        last_time = start_time
        last_size = 0

        def progress_cb(p, downloaded_size=0):
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
            
            if p % 5 == 0 or speed_str:
                status = f"下载{media_type}流：{p}%"
                if speed_str:
                    status += f" ({speed_str})"
                self.progress_updated.emit(self.ep_index, self._calc_total_progress(p, media_type), status)
            
            if not self.is_running:
                raise Exception("下载已取消")

        try:
            file_path = self.parser.download_file(
                url=url,
                save_dir=self.save_path,
                progress_callback=progress_cb,
                file_type=media_type,
                bvid=bvid
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

    def _calc_total_progress(self, p, media_type):
        if media_type == "video":
            return p // 2
        else:
            return 50 + p // 2

    def _merge_media(self, video_path, audio_path):
        output_path = os.path.join(self.save_path, f"{self.ep_title}.mp4")
        output_path = get_unique_filename(output_path)
        self.progress_updated.emit(self.ep_index, 90, "合并音视频...")

        try:
            if audio_path:
                merge_success = self.parser.merge_media(video_path, audio_path, output_path)
                if not merge_success:
                    raise Exception("合并失败")
            else:
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(video_path, output_path)
            self.progress_updated.emit(self.ep_index, 100, "合并完成")
            logger.info(f"线程{self.ep_index}：下载完成")
            self.episode_finished.emit(self.ep_index, True, f"完成：{os.path.basename(output_path)}")
        except Exception as e:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            raise Exception(f"合并失败：{str(e)}")

    def _clean_temp_files(self):
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"线程{self.ep_index}：清理临时文件")
            except:
                logger.warning(f"线程{self.ep_index}：无法清理临时文件")
        self.temp_files.clear()

    def stop(self):
        self.is_running = False
        if hasattr(self.parser, 'stop_download'):
            self.parser.stop_download()


class DownloadManager(QObject):
    global_progress_updated = pyqtSignal(int, str)
    episode_progress_updated = pyqtSignal(int, int, str)
    episode_finished = pyqtSignal(int, bool, str)
    all_finished = pyqtSignal()
    task_added = pyqtSignal(str)
    task_status_changed = pyqtSignal(str)

    def __init__(self, parser, task_manager=None, max_threads=4):
        super().__init__()
        self.parser = parser
        self.task_manager = task_manager
        self.max_threads = min(max_threads, 16)
        self.task_queue: list[Task] = []
        self.running_threads = set()
        self.total_episodes = 0
        self.completed_episodes = 0
        self.failed_episodes = 0
        self._mutex = QMutex()
        self.wait_condition = QWaitCondition()
        self.is_cancelled = False
        self.current_task_id = None
        self.is_running = False
        self.executor = None
        self.futures = []
        logger.info(f"下载管理器初始化，并发数：{self.max_threads}")
    
    def set_max_threads(self, max_threads):
        if max_threads > 0:
            self.max_threads = min(max_threads, 16)
            logger.info(f"线程数已修改为：{self.max_threads}")

    def start_download(self, download_params):
        self.task_start_time = time.time()
        logger.info("开始批量下载")
        
        self._mutex.lock()
        if self.is_running:
            self._mutex.unlock()
            logger.warning("已有下载任务在运行，请勿重复启动")
            self.global_progress_updated.emit(0, "已有下载任务在运行")
            return
        self.is_running = True
        self._mutex.unlock()

        self.download_params = download_params
        self.video_info = download_params.get('video_info', {})
        self.selected_qn = download_params.get('qn', '')
        self.save_path = download_params.get('save_path', '')
        episodes = download_params.get('episodes', [])
        url = download_params.get('url', '')
        resume_download = download_params.get('resume_download', False)

        if hasattr(self.parser, 'reset_running_status'):
            self.parser.reset_running_status()
            logger.info("重置解析器状态")

        self._mutex.lock()
        self.total_episodes = len(episodes)
        self.completed_episodes = 0
        self.failed_episodes = 0
        self.is_cancelled = False
        self.task_queue = [(idx, ep) for idx, ep in enumerate(episodes)]
        self.futures = []
        self._mutex.unlock()

        if self.total_episodes == 0:
            self.global_progress_updated.emit(0, "无选中集数")
            return
        if not self.save_path:
            self.global_progress_updated.emit(0, "保存路径未指定")
            return
        if not self.selected_qn:
            self.global_progress_updated.emit(0, "未选择清晰度")
            return

        if self.task_manager and not resume_download:
            task_info = {
                "url": url,
                "title": self.video_info.get('title', '未知视频'),
                "save_path": self.save_path,
                "progress": 0,
                "status": "downloading",
                "video_info": self.video_info,
                "qn": self.selected_qn,
                "episodes": episodes
            }
            task = self.task_manager.add_task(task_info)
            self.current_task_id = task.get('id')
            self.task_added.emit(self.current_task_id)
            logger.info(f"创建下载任务：{self.current_task_id}")

        logger.info(f"准备下载{self.total_episodes}个视频")
        
        try:
            self.executor = ThreadPoolExecutor(max_workers=self.max_threads)
            logger.info(f"创建线程池，最大线程数：{self.max_threads}")
            
            for idx, ep in self.task_queue:
                future = self.executor.submit(self._download_episode, idx, ep)
                self.futures.append(future)
            
            self._monitor_tasks()
        except Exception as e:
            logger.error(f"线程池创建失败：{str(e)}")
            self.global_progress_updated.emit(0, f"线程池创建失败：{str(e)}")
            self._cleanup()
            return

        self.global_progress_updated.emit(0, f"开始下载{self.total_episodes}集（并发：{self.max_threads}）")

    def _download_episode(self, ep_index, ep_info):
        start_time = time.time()
        logger.info(f"开始下载第{ep_index+1}集")
        temp_files = []
        try:
            ep_title = f"第{ep_index+1}集_未知标题"
            try:
                if self.video_info.get('is_bangumi') and self.video_info.get('bangumi_info'):
                    season = self.video_info['bangumi_info'].get('season_title', '未知季度')
                    ep_idx = ep_info.get('ep_index', '未知集')
                    title_candidates = [
                        ep_info.get('ep_title', ''),
                        ep_info.get('title', ''),
                        ep_info.get('name', '')
                    ]
                    actual_title = next((t for t in title_candidates if t), '')
                    if actual_title:
                        ep_title = f"{season}_{ep_idx}_{actual_title}"
                    else:
                        ep_title = f"{season}_{ep_idx}"
                else:
                    ep_title = ep_info.get('title', f"第{ep_index+1}集")
                for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    ep_title = ep_title.replace(c, '_')
                ep_title = ep_title[:30]
            except Exception as e:
                logger.error(f"标题初始化错误: {e}")
                ep_title = f"第{ep_index+1}集"

            try:
                if not os.path.exists(self.save_path):
                    os.makedirs(self.save_path, exist_ok=True)
            except Exception as e:
                raise Exception(f"保存路径异常：{str(e)}")

            self.episode_progress_updated.emit(ep_index, 0, "准备下载...")

            if self.is_cancelled:
                raise Exception("下载已取消")

            bvid = self.video_info.get('bvid', ep_info.get('bvid', ''))
            video_url, audio_url = self._get_media_urls_with_retry(bvid, ep_info)
            if not video_url:
                raise Exception("无有效视频链接")

            video_path = self._download_media_with_retry(video_url, "video", bvid, ep_index)
            if not video_path or self.is_cancelled:
                return False, "下载已取消"
            temp_files.append(video_path)

            audio_path = None
            if audio_url and not self.is_cancelled:
                audio_path = self._download_media_with_retry(audio_url, "audio", bvid, ep_index)
                if not audio_path:
                    return False, "音频下载失败"
                temp_files.append(audio_path)

            if not self.is_cancelled:
                clean_title = ep_title.replace("正片_", "")
                output_path = os.path.join(self.save_path, f"{clean_title}.mp4")
                output_path = get_unique_filename(output_path)
                self.episode_progress_updated.emit(ep_index, 90, "合并音视频...")

                try:
                    if audio_path:
                        merge_success = self.parser.merge_media(video_path, audio_path, output_path)
                        if not merge_success:
                            raise Exception("合并失败")
                    else:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        os.rename(video_path, output_path)
                    self.episode_progress_updated.emit(ep_index, 100, "合并完成")
                    end_time = time.time()
                    duration = end_time - start_time
                    duration_str = f"{duration:.2f}秒"
                    logger.info(f"第{ep_index+1}集下载完成，耗时：{duration_str}")
                    self._clean_temp_files(temp_files)
                    return True, f"完成：{os.path.basename(output_path)}（耗时：{duration_str}）"
                except Exception as e:
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
                    raise Exception(f"合并失败：{str(e)}")

        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            duration_str = f"{duration:.2f}秒"
            err_msg = str(e)
            if "Remote end closed" in err_msg or "Read timed out" in err_msg:
                err_msg += "（网络问题，已自动重试）"
            if "ffmpeg" in err_msg.lower():
                err_msg += "（检查FFmpeg环境变量）"
            if "下载已取消" in err_msg:
                err_msg = "下载已取消"
            logger.error(f"第{ep_index+1}集下载失败 - {err_msg}，耗时：{duration_str}")
            self._clean_temp_files(temp_files)
            return False, f"{err_msg}（耗时：{duration_str}）"

    def _clean_temp_files(self, temp_files):
        for file_path in temp_files:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"清理临时文件：{file_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败：{str(e)}")

    def _get_media_urls_with_retry(self, bvid, ep_info):
        retry_count = 0
        while not self.is_cancelled:
            try:
                return self._get_media_urls(bvid, ep_info)
            except Exception as e:
                if any(keyword in str(e) for keyword in ["Remote end closed", "Read timed out", "403", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"第{ep_info.get('page', 1)}集获取链接失败，{delay}秒后重试")
                    time.sleep(delay)
                    continue
                elif "下载已取消" in str(e):
                    raise
                else:
                    retry_count += 1
                    if retry_count <= 3:
                        delay = min(retry_count, 3)
                        logger.warning(f"第{ep_info.get('page', 1)}集发生错误，{delay}秒后重试")
                        time.sleep(delay)
                        continue
                    else:
                        raise

    def _get_media_urls(self, bvid, ep_info):
        video_url = ""
        audio_url = ""
        try:
            if self.video_info.get('is_bangumi'):
                play_info = self.parser.get_bangumi_episode_playinfo(
                    bvid=ep_info.get('bvid', bvid),
                    cid=ep_info.get('cid', ''),
                    quality=self.selected_qn
                )
                if not play_info.get('success'):
                    raise Exception(play_info.get('error', '番剧API失败'))
                video_url = play_info.get('video_url', '')
                audio_url = play_info.get('audio_url', '')
            else:
                if not ep_info.get('video_urls'):
                    ep_detail = self.parser.get_single_episode_info(
                        media_type=self.video_info.get('type', ''),
                        media_id=bvid,
                        page=ep_info.get('page', 1),
                        is_tv_mode=self.video_info.get('is_tv_mode', False)
                    )
                    if not ep_detail.get('success'):
                        raise Exception(ep_detail.get('error', '单集API失败'))
                    ep_info = ep_detail

                video_urls = ep_info.get('video_urls', {})
                selected_qn = str(self.selected_qn)
                if selected_qn not in video_urls:
                    selected_qn = list(video_urls.keys())[0] if video_urls else ''
                video_url = video_urls.get(selected_qn, '')
                audio_url = ep_info.get('audio_url', '')
            return video_url, audio_url
        except Exception as e:
            raise Exception(f"链接获取失败：{str(e)}")

    def _download_media_with_retry(self, url, media_type, bvid, ep_index):
        retry_count = 0
        while not self.is_cancelled:
            try:
                logger.info(f"开始下载{media_type}流")
                return self._download_media(url, media_type, bvid, ep_index)
            except Exception as e:
                if any(keyword in str(e) for keyword in ["Read timed out", "Remote end closed", "Connection aborted", "Connection error"]):
                    retry_count += 1
                    delay = min(retry_count, 5)
                    logger.warning(f"{media_type}下载超时，{delay}秒后重试")
                    time.sleep(delay)
                    continue
                elif "下载已取消" in str(e):
                    raise
                else:
                    retry_count += 1
                    if retry_count <= 3:
                        delay = min(retry_count, 3)
                        logger.warning(f"{media_type}下载错误，{delay}秒后重试")
                        time.sleep(delay)
                        continue
                    else:
                        raise Exception(f"{media_type}下载失败：{str(e)}")

    def _download_media(self, url, media_type, bvid, ep_index):
        if not url:
            return None

        start_time = time.time()
        last_time = start_time
        last_size = 0

        def progress_cb(p, downloaded_size=0):
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
            
            if p % 5 == 0 or speed_str:
                status = f"下载{media_type}流：{p}%"
                if speed_str:
                    status += f" ({speed_str})"
                self.episode_progress_updated.emit(ep_index, self._calc_total_progress(p, media_type), status)
            
            if self.is_cancelled:
                raise Exception("下载已取消")

        try:
            file_path = self.parser.download_file(
                url=url,
                save_dir=self.save_path,
                progress_callback=progress_cb,
                file_type=media_type,
                bvid=bvid
            )
            if file_path and os.path.exists(file_path):
                return file_path
            return None
        except Exception as e:
            if "下载已取消" in str(e):
                logger.info(f"{media_type}流下载被取消")
                return None
            raise

    def _calc_total_progress(self, p, media_type):
        if media_type == "video":
            return min(p // 2, 50)
        else:
            return min(50 + p // 2, 100)

    def _monitor_tasks(self):
        import threading
        
        def monitor():
            try:
                completed_tasks = 0
                total_tasks = len(self.futures)
                
                future_to_index = {future: idx for idx, future in enumerate(self.futures)}
                
                for future in as_completed(self.futures):
                    if self.is_cancelled:
                        break
                    
                    try:
                        success, message = future.result()
                        ep_index = future_to_index.get(future, 0)
                        
                        self._mutex.lock()
                        if success:
                            self.completed_episodes += 1
                        else:
                            self.failed_episodes += 1
                        completed_tasks += 1
                        total_processed = self.completed_episodes + self.failed_episodes
                        self._mutex.unlock()

                        self.episode_finished.emit(ep_index, success, message)
                        logger.info(f"结果：第{ep_index+1}集 {'成功' if success else '失败'} - {message}")

                        global_progress = (total_processed * 100) // self.total_episodes
                        self.global_progress_updated.emit(
                            global_progress,
                            f"当前：{self.completed_episodes}完成 / {self.failed_episodes}失败（{total_processed}/{self.total_episodes}）"
                        )
                    except Exception as e:
                        logger.error(f"处理任务结果失败：{str(e)}")
                        self._mutex.lock()
                        self.failed_episodes += 1
                        completed_tasks += 1
                        self._mutex.unlock()

                if not self.is_cancelled and completed_tasks == total_tasks:
                    task_end_time = time.time()
                    total_duration = task_end_time - self.task_start_time
                    total_duration_str = f"{total_duration:.2f}秒"
                    logger.info(f"全部下载完成！成功{self.completed_episodes}集，失败{self.failed_episodes}集，总耗时：{total_duration_str}")
                    self.global_progress_updated.emit(100, f"全部完成！成功{self.completed_episodes} 失败{self.failed_episodes}，总耗时：{total_duration_str}")
                    
                    if self.task_manager and self.current_task_id:
                        task_data = {
                            "duration": total_duration_str,
                            "progress": 100,
                            "completed_episodes": self.completed_episodes,
                            "failed_episodes": self.failed_episodes
                        }
                        if self.failed_episodes > 0:
                            self.task_manager.update_task_status(self.current_task_id, "failed", f"部分失败：成功{self.completed_episodes}集，失败{self.failed_episodes}集", task_data)
                        else:
                            self.task_manager.update_task_status(self.current_task_id, "completed", f"成功{self.completed_episodes}集，总耗时：{total_duration_str}", task_data)
                        self.task_status_changed.emit(self.current_task_id)
                        self.current_task_id = None
                    else:
                        if self.task_manager:
                            task_info = {
                                "url": self.download_params.get('url', ''),
                                "title": self.video_info.get('title', '未知视频'),
                                "save_path": self.save_path,
                                "progress": 100,
                                "status": "completed" if self.failed_episodes == 0 else "failed",
                                "video_info": self.video_info,
                                "qn": self.selected_qn,
                                "episodes": self.download_params.get('episodes', []),
                                "duration": total_duration_str
                            }
                            new_task = self.task_manager.add_task(task_info)
                            self.task_added.emit(new_task.get('id'))
                    
                    self.all_finished.emit()
                    self._cleanup()
            except Exception as e:
                logger.error(f"监控任务失败：{str(e)}")
                self._cleanup()
        
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()

    def _cleanup(self):
        self._mutex.lock()
        try:
            if self.executor:
                self.executor.shutdown(wait=False)
                self.executor = None
            self.task_queue.clear()
            self.running_threads.clear()
            self.futures.clear()
            self.is_running = False
            logger.info("下载任务全部完成，下载管理器已就绪")
        finally:
            self._mutex.unlock()





    def cancel_all(self):
        logger.info("开始取消下载")
        self._mutex.lock()
        self.is_cancelled = True
        self.task_queue.clear()
        self._mutex.unlock()

        if self.task_manager and self.current_task_id:
            self.task_manager.update_task_status(self.current_task_id, "failed", "下载已取消")
            self.current_task_id = None

        self.global_progress_updated.emit(0, "正在取消所有下载...")

        def _wait_for_tasks():
            try:
                if self.executor:
                    self.executor.shutdown(wait=True, cancel_futures=True)
                    logger.info("线程池已关闭")
            except Exception as e:
                logger.error(f"关闭线程池失败：{str(e)}")

            logger.info("下载已取消")
            self.global_progress_updated.emit(0, "所有下载已取消")
            
            self._cleanup()
            self.all_finished.emit()

        import threading
        wait_thread = threading.Thread(target=_wait_for_tasks, daemon=True)
        wait_thread.start()