import os
import time
import threading
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
        self.audio_quality = self.config.get_app_setting("audio_quality", 30280) if self.config else 30280
        logger.info(f"线程{ep_index}：开始下载，音频质量：{self.audio_quality}")

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

            video_path = self._download_media_with_retry(video_url, "video", bvid, 0, kid)
            if not video_path or not self.is_running:
                return

            audio_path = None
            if audio_url and self.is_running:
                audio_path = self._download_media_with_retry(audio_url, "audio", bvid, 0, kid)
                if not audio_path:
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
                    self.ep_title = actual_title
                else:
                    self.ep_title = f"第{self.ep_index+1}集"
            for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                self.ep_title = self.ep_title.replace(c, '_')
            self.ep_title = self.ep_title[:30]
        except Exception as e:
            print(f"标题初始化错误: {e}")
            self.ep_title = f"第{self.ep_index+1}集"

    def _check_save_path(self):
        try:
            # 验证路径是否有效
            if not self.save_path or not isinstance(self.save_path, str):
                raise Exception("保存路径不能为空")
            
            # 规范化路径
            self.save_path = os.path.normpath(self.save_path)
            
            # 如果路径为空或无效，使用默认路径
            if not self.save_path or len(self.save_path.strip()) == 0:
                default_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
                self.save_path = default_path
                logger.warning(f"保存路径无效，使用默认路径: {self.save_path}")
            
            # 创建目录
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
                    if retry_count <= 3:
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
                selected_qn = str(self.selected_qn)
                if selected_qn not in video_urls:
                    selected_qn = list(video_urls.keys())[0] if video_urls else ''
                video_url = video_urls.get(selected_qn, '')
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
                selected_qn = str(self.selected_qn)
                if selected_qn not in video_urls:
                    
                    if video_urls:
                        selected_qn = list(video_urls.keys())[0]
                    else:
                        raise Exception("无可用的视频画质")
                video_url = video_urls.get(selected_qn, '')
                audio_url = play_info.get('audio_url', '')
                kid = play_info.get('kid', None)
            return video_url, audio_url, kid
        except Exception as e:
            error = str(e)
            if "访问权限不足" in error:
                raise Exception("访问权限不足")
            raise Exception(f"链接获取失败：{error}")

    def _download_media_with_retry(self, url, media_type, bvid, ep_index, kid=None):
        retry_count = 0
        while self.is_running:
            try:
                logger.info(f"线程{self.ep_index}：开始下载{media_type}流")
                return self._download_media(url, media_type, bvid, ep_index, kid)
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
                    if retry_count <= 2:
                        delay = min(retry_count, 2)
                        logger.warning(f"线程{self.ep_index}：{media_type}下载错误，{delay}秒后重试")
                        if retry_count == 1:
                            current_progress = self._calc_total_progress(0)
                            self.progress_updated.emit(self.ep_index, current_progress, f"{media_type}下载错误，{delay}秒后重试...")
                        self.msleep(delay * 1000)
                        continue
                    else:
                        raise Exception(f"{media_type}下载失败：{str(e)}")

    def _download_media(self, url, media_type, bvid, ep_index, kid=None):
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
            

            status = f"下载{media_type}流：{p}%"
            if speed_str:
                status += f" ({speed_str})"
            self.progress_updated.emit(self.ep_index, self._calc_total_progress(p), status)
            
            if not self.is_running:
                raise Exception("下载已取消")

        def is_running():
            return self.is_running

        try:
            import asyncio
            file_path = asyncio.run(self.parser.download_file(
                url=url,
                save_path=self.save_path,
                progress_callback=progress_cb,
                file_type=media_type,
                bvid=bvid,
                is_running=is_running,
                kid=kid
            ))
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

    def _merge_media(self, video_path, audio_path, kid=None):

        if not video_path or not os.path.exists(video_path):
            raise Exception("视频文件不存在")
        
        if audio_path and not os.path.exists(audio_path):
            raise Exception("音频文件不存在")
        

        if not self.save_path or not os.path.exists(self.save_path):
            raise Exception("保存路径不存在")
        
        output_path = os.path.join(self.save_path, f"{self.ep_title}.mp4")
        output_path = get_unique_filename(output_path)
        self.progress_updated.emit(self.ep_index, 90, "合并音视频...")
        self.merge_started.emit(self.ep_index)

        try:
            if audio_path:
                import asyncio
                merge_success = asyncio.run(self.parser.merge_media(video_path, audio_path, output_path, kid))
                if not merge_success:
                    raise Exception("合并失败")
            else:
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                    except Exception as e:
                        raise Exception(f"无法删除已存在的文件：{str(e)}")
                try:
                    os.rename(video_path, output_path)
                except Exception as e:
                    
                    if "系统无法将文件移到不同的磁盘驱动器" in str(e):
                        import shutil
                        shutil.move(video_path, output_path)
                    else:
                        raise Exception(f"重命名文件失败：{str(e)}")
            

            if not os.path.exists(output_path):
                raise Exception("合并后文件不存在")
            
            self.progress_updated.emit(self.ep_index, 100, "合并完成")
            self.merge_finished.emit(self.ep_index)
            logger.info(f"线程{self.ep_index}：下载完成")
            self.episode_finished.emit(self.ep_index, True, f"完成：{os.path.basename(output_path)}")
        except Exception as e:
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except Exception as clean_e:
                    logger.warning(f"清理合并失败的文件失败：{str(clean_e)}")
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
    episode_progress_updated = pyqtSignal(str, int, float, str)
    episode_finished = pyqtSignal(str, int, bool, str)
    all_finished = pyqtSignal()
    task_added = pyqtSignal(str)
    task_status_changed = pyqtSignal(str)
    same_task_exists = pyqtSignal(dict)
    merge_started = pyqtSignal(str, int)
    merge_finished = pyqtSignal(str, int)

    def __init__(self, parser, task_manager=None, max_threads=4, max_concurrent_tasks=2):
        super().__init__()
        self.parser_template = parser
        self.task_manager = task_manager
        self.max_threads = min(max_threads, 16)
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks = {}
        self.paused_tasks = {}
        self.task_queue = []
        self._mutex = QMutex()
        self._task_condition = QWaitCondition()
        logger.info(f"下载管理器初始化，并发数：{self.max_threads}，最大并发任务数：{self.max_concurrent_tasks}")
        

        self.scheduler_thread = threading.Thread(target=self._schedule_tasks, daemon=True)
        self.scheduler_thread.start()
    
    def set_max_threads(self, max_threads):
        if max_threads > 0:
            self.max_threads = min(max_threads, 16)
            logger.info(f"线程数已修改为：{self.max_threads}")

    def _schedule_tasks(self):
        while True:
            try:
                self._mutex.lock()

                while len(self.active_tasks) >= self.max_concurrent_tasks and len(self.task_queue) > 0:
                    try:
                        self._task_condition.wait(self._mutex)
                    except Exception as e:
                        logger.error(f"调度线程等待时发生异常：{str(e)}")
                        break
                
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
                    existing_task.get('status') in ['downloading', 'pending']):
    
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

        download_video = download_params.get('download_video', True)
        download_danmaku = download_params.get('download_danmaku', False)
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
            "task_start_time": time.time(),
            "downloaded_episodes": [],
            "parser": task_parser,
            "download_video": download_video,
            "download_danmaku": download_danmaku,
            "danmaku_format": danmaku_format,
            "video_format": video_format,
            "audio_format": audio_format
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
                "audio_format": audio_format
            }
            task = self.task_manager.add_task(task_info_for_manager)
            self.task_added.emit(task_id)
            logger.info(f"创建下载任务：{task_id}")

        logger.info(f"准备下载{len(episodes)}个视频")
        

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
        
        # 验证输入参数
        if not episodes:
            logger.warning(f"任务{task_id}：无选中集数")
            self.global_progress_updated.emit(0, "无选中集数")
            return
            
        # 验证并规范化保存路径
        if not save_path or not isinstance(save_path, str):
            logger.warning(f"任务{task_id}：保存路径未指定或无效")
            save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")
            logger.warning(f"使用默认保存路径: {save_path}")
        else:
            save_path = os.path.normpath(save_path)
            
        # 确保保存路径存在且可写
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
        except Exception as e:
            error_msg = f"保存路径不可用: {str(e)}"
            logger.error(f"任务{task_id}：{error_msg}")
            self.global_progress_updated.emit(0, error_msg)
            return
            
        if not selected_qn and download_video:
            logger.warning(f"任务{task_id}：未选择清晰度")
            self.global_progress_updated.emit(0, "未选择清晰度")
            return
            
        # 更新download_params中的save_path
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

    def _download_episode(self, task_id, ep_index, ep_info):
        self._mutex.lock()
        task_info = self.active_tasks.get(task_id)
        if not task_info or task_info['is_cancelled']:
            self._mutex.unlock()
            return False, "任务已取消"
        self._mutex.unlock()

        start_time = time.time()
        download_video = task_info.get('download_video', True)
        download_danmaku = task_info.get('download_danmaku', False)
        
        logger.info(f"任务{task_id}：开始处理第{ep_index+1}集，视频下载：{download_video}，弹幕下载：{download_danmaku}")
        
        if not download_video and not download_danmaku:
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
                    if actual_title:
                        ep_title = f"{season}_{ep_idx}_{actual_title}"
                    else:
                        ep_title = f"{season}_{ep_idx}"
                else:
                    # 检查课程视频的ep_title字段
                    title_candidates = [
                        ep_info.get('ep_title', ''),
                        ep_info.get('title', ''),
                        ep_info.get('name', '')
                    ]
                    actual_title = next((t for t in title_candidates if t), '')
                    if actual_title:
                        ep_title = actual_title
                    else:
                        ep_title = f"第{ep_index+1}集"
                for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
                    ep_title = ep_title.replace(c, '_')
                ep_title = ep_title[:30]
            except Exception as e:
                logger.error(f"任务{task_id}：标题初始化错误: {e}")
                ep_title = f"第{ep_index+1}集"

            try:
                # 验证保存路径
                if not task_info['save_path'] or not isinstance(task_info['save_path'], str):
                    raise Exception("保存路径无效")
                
                # 规范化路径
                task_info['save_path'] = os.path.normpath(task_info['save_path'])
                
                # 创建目录
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
            if not task_info or task_info['is_cancelled']:
                self._mutex.unlock()
                return False, "任务已取消"
            self._mutex.unlock()

            output_path = None
            clean_title = ep_title.replace("正片_", "")
            
            if download_video:
                self.episode_progress_updated.emit(task_id, ep_index, 5, "获取下载链接...")

                bvid = ep_info.get('bvid', task_info['video_info'].get('bvid', ''))
                try:
                    # 创建ep_info的副本，避免修改原始对象
                    ep_info_copy = ep_info.copy()
                    ep_info_copy['task_id'] = task_id
                    video_url, audio_url, kid = self._get_media_urls_with_retry(bvid, ep_info_copy)
                    if not video_url:
                        raise Exception("无有效视频链接")
                    
                    
                    self.episode_progress_updated.emit(task_id, ep_index, 10, "链接获取成功，开始下载...")
                except Exception as e:
                    logger.error(f"任务{task_id}：获取播放链接失败：{str(e)}")
                    return False, f"获取播放链接失败：{str(e)}"

                video_path = self._download_media_with_retry(task_id, video_url, "video", bvid, ep_index, kid)
                if not video_path:
                    return False, "视频下载失败"
                temp_files.append(video_path)

                audio_path = None
                if audio_url:
                    audio_path = self._download_media_with_retry(task_id, audio_url, "audio", bvid, ep_index, kid)
                    if not audio_path:
                        return False, "音频下载失败"
                    temp_files.append(audio_path)

                video_format = task_info.get('video_format', 'mp4')
                output_path = os.path.join(task_info['save_path'], f"{clean_title}.{video_format}")
                output_path = get_unique_filename(output_path)
                self.episode_progress_updated.emit(task_id, ep_index, 90, "合并音视频...")
                self.merge_started.emit(task_id, ep_index)

                try:
                    if audio_path:
                        import asyncio
                        merge_success = asyncio.run(task_info['parser'].merge_media(video_path, audio_path, output_path, kid))
                        if not merge_success:
                            raise Exception("合并失败")
                    else:
                        if os.path.exists(output_path):
                            os.remove(output_path)
                        try:
                            os.rename(video_path, output_path)
                        except Exception as e:
                            
                            if "系统无法将文件移到不同的磁盘驱动器" in str(e):
                                import shutil
                                shutil.move(video_path, output_path)
                            else:
                                raise Exception(f"重命名文件失败：{str(e)}")
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
                    self.episode_progress_updated.emit(task_id, ep_index, 100, "下载弹幕...")
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
            if download_video and output_path:
                completed_items.append(f"视频：{os.path.basename(output_path)}")
            if download_danmaku:
                completed_items.append("弹幕")
            
            if completed_items:
                completed_msg = "完成：" + "、".join(completed_items)
                return True, f"{completed_msg}（耗时：{duration_str}）"
            else:
                return False, "未完成任何下载"

        except Exception as e:
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
        for file_path in temp_files:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
                    logger.debug(f"清理临时文件：{file_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败：{str(e)}")

    def _get_media_urls_with_retry(self, bvid, ep_info):
        retry_count = 0
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
                    if retry_count <= 3:
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
                
            video_info = task_info['video_info']
            selected_qn = task_info['qn']
            parser = task_info['parser']
            
            if video_info.get('is_bangumi'):
                if 'video_urls' in ep_info:
                    video_urls = ep_info.get('video_urls', {})
                    if selected_qn not in video_urls:
                        selected_qn = list(video_urls.keys())[0] if video_urls else ''
                    video_url = video_urls.get(selected_qn, '')
                    audio_url = ep_info.get('audio_url', '')
                    kid = ep_info.get('kid', None)
                else:
                    # 获取音频质量设置
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
                        selected_qn = list(video_urls.keys())[0] if video_urls else ''
                    video_url = video_urls.get(selected_qn, '')
                    audio_url = play_info.get('audio_url', '')
                    kid = play_info.get('kid', None)
                    ep_info['video_urls'] = video_urls
                    ep_info['audio_url'] = audio_url
                    ep_info['kid'] = kid
            elif video_info.get('is_cheese'):
                video_urls = ep_info.get('video_urls', {})
                if not video_urls:
                    
                    season_id = ep_info.get('season_id', video_info.get('season_id', ''))
                    ep_id = ep_info.get('ep_id', '')
                    cid = ep_info.get('cid', '')
                    bvid = ep_info.get('bvid', bvid)
                    # 获取音频质量设置
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
                    selected_qn = list(video_urls.keys())[0] if video_urls else ''
                video_url = video_urls.get(selected_qn, '')
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
                    
                    # 获取音频质量设置
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
                        # 获取音频质量设置
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
                    selected_qn = list(video_urls.keys())[0] if video_urls else ''
                video_url = video_urls.get(selected_qn, '')
            return video_url, audio_url, kid
        except Exception as e:
            error = str(e)
            if "访问权限不足" in error:
                raise Exception("访问权限不足")
            raise Exception(f"链接获取失败：{error}")

    def _download_media_with_retry(self, task_id, url, media_type, bvid, ep_index, kid=None):
        self._mutex.lock()
        task_info = self.active_tasks.get(task_id)
        if not task_info or task_info['is_cancelled']:
            self._mutex.unlock()
            return None
        self._mutex.unlock()

        retry_count = 0
        while True:
            try:
                logger.info(f"任务{task_id}：开始下载{media_type}流")
                return self._download_media(task_id, url, media_type, bvid, ep_index, kid)
            except Exception as e:
                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if not task_info or task_info['is_cancelled']:
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
                    if retry_count <= 3:
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
            self._mutex.unlock()
            logger.error(f"任务{task_id}：任务不存在")
            return None
        self._mutex.unlock()


        if not task_info.get('save_path'):
            logger.error(f"任务{task_id}：保存路径未设置")
            return None

        start_time = time.time()
        last_time = start_time
        last_size = 0
        last_progress = -1

        def progress_cb(p, downloaded_size=0):
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
                
    
                status = f"下载{media_type}流：{p}%"
                if speed_str:
                    status += f" ({speed_str})"
                
                if p % 10 == 0:
                    print(f"任务{task_id}：{status}")

                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if task_info:
                    task_info['progress'] = self._calc_total_progress(p)
                    if not 'episode_progress' in task_info:
                        task_info['episode_progress'] = {}
                    task_info['episode_progress'][str(ep_index)] = task_info['progress']
                self._mutex.unlock()

                current_progress = int(p)
                if abs(current_progress - last_progress) >= 1 or time_diff >= 0.5:
                    self.episode_progress_updated.emit(task_id, ep_index, self._calc_total_progress(p), status)
                    last_time = current_time
                    last_size = downloaded_size
                    last_progress = current_progress

                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if not task_info or task_info['is_cancelled']:
                    self._mutex.unlock()
                    raise Exception("任务已取消")
                self._mutex.unlock()

        def is_running():
            self._mutex.lock()
            task_info = self.active_tasks.get(task_id)
            running = task_info and not task_info.get('is_cancelled', False)
            self._mutex.unlock()
            return running

        try:
            logger.info(f"任务{task_id}：开始下载{media_type}流，线程：{threading.current_thread().name}")
            import asyncio
            file_path = asyncio.run(task_info['parser'].download_file(
                url=url,
                save_path=task_info['save_path'],
                progress_callback=progress_cb,
                file_type=media_type,
                bvid=bvid,
                is_running=is_running,
                kid=kid
            ))
            if file_path and os.path.exists(file_path):
                logger.info(f"任务{task_id}：{media_type}流下载完成")
                return file_path
            logger.warning(f"任务{task_id}：{media_type}流下载返回空文件路径")
            return None
        except Exception as e:
            if "任务已取消" in str(e):
                logger.info(f"任务{task_id}：{media_type}流下载被取消")
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
                    if not task_info or task_info['is_cancelled']:
                        self._mutex.unlock()
                        break
                    self._mutex.unlock()

                    try:
                        success, message = future.result()
                        ep_index = future_to_index.get(future, 0)
                        
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
                        logger.error(f"任务{task_id}：处理任务结果失败：{str(e)}")
                        self._mutex.lock()
                        task_info = self.active_tasks.get(task_id)
                        if task_info:
                            task_info['failed_episodes'] += 1
                            completed_tasks += 1
                        self._mutex.unlock()

                self._mutex.lock()
                task_info = self.active_tasks.get(task_id)
                if task_info and not task_info['is_cancelled'] and completed_tasks == total_tasks:
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
                            "downloaded_episodes": task_info.get('downloaded_episodes', [])
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
                
                self._cleanup_task(task_id)
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
        
        monitor_thread = threading.Thread(target=monitor, daemon=False)
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
            task_info['is_cancelled'] = True  
            

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
                

                downloaded_episode_ids = []
                for ep in task_info.get('downloaded_episodes', []):
                    if 'ep_index' in ep:
                        downloaded_episode_ids.append(ep['ep_index'])
                    elif 'page' in ep:
                        downloaded_episode_ids.append(ep['page'])
                

                episode_progress = task_info.get('episode_progress', {})
                
                for idx, ep in enumerate(task_info['episodes']):

                    ep_id = ep.get('ep_index') or ep.get('page')
                    if ep_id in downloaded_episode_ids:

                        self.episode_progress_updated.emit(task_id, idx, 100, "已完成")
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
        self._mutex.lock()
        task_ids = list(self.active_tasks.keys())
        for task_id in task_ids:
            self.active_tasks[task_id]['is_cancelled'] = True

        self.task_queue.clear()
        self._mutex.unlock()

        try:
            self.global_progress_updated.emit(0, "正在取消所有下载...")
        except RuntimeError:
            
            logger.warning("DownloadManager对象已被删除，无法发送信号")
            return

        def _wait_for_tasks():
            for task_id in task_ids:
                try:
                    self._mutex.lock()
                    task_info = self.active_tasks.get(task_id)
                    if task_info and task_info.get('executor'):
                        executor = task_info['executor']
                        self._mutex.unlock()
                        try:
        
                            executor.shutdown(wait=True, cancel_futures=True)
                        except TypeError:
        
                            executor.shutdown(wait=True)
                        logger.info(f"任务{task_id}：线程池已关闭")
                    else:
                        self._mutex.unlock()
                except Exception as e:
                    logger.error(f"任务{task_id}：关闭线程池失败：{str(e)}")

            logger.info("所有下载已取消")
            try:
                self.global_progress_updated.emit(0, "所有下载已取消")
                self.all_finished.emit()
            except RuntimeError:

                logger.warning("DownloadManager对象已被删除，无法发送信号")

        import threading
        wait_thread = threading.Thread(target=_wait_for_tasks, daemon=True)
        wait_thread.start()