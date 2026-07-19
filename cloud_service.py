import requests
import logging
import hashlib
import json
import os
import sys
import time
import threading
import uuid
from platform_utils import IS_MACOS, IS_WINDOWS, exe

logger = logging.getLogger(__name__)

API_BASE = "https://www.bilidown.cn/api/v1"


class CloudService:
    # 数据采集类别（用户可控开关，细粒度到每一项）
    CONSENT_INSTALL = "event_install"           # 安装事件上报
    CONSENT_LAUNCH = "event_launch"             # 启动事件上报
    CONSENT_PARSE = "event_parse_video"        # 视频解析事件上报
    CONSENT_DOWNLOAD = "event_download_video"   # 视频下载事件上报
    CONSENT_CRASH = "crash_report"              # 崩溃日志上报
    CONSENT_ERROR = "error_report"              # 错误日志上报
    CONSENT_REMOTE_CONFIG = "remote_config"     # 远程配置读取
    CONSENT_REMOTE_SCRIPT = "remote_script"     # 远程脚本执行

    _DEFAULT_CONSENT = {
        CONSENT_INSTALL: False,
        CONSENT_LAUNCH: False,
        CONSENT_PARSE: False,
        CONSENT_DOWNLOAD: False,
        CONSENT_CRASH: True,
        CONSENT_ERROR: True,
        CONSENT_REMOTE_CONFIG: False,
        CONSENT_REMOTE_SCRIPT: False,
    }

    CONSENT_GROUPS = {
        "使用统计": [
            (CONSENT_INSTALL, "安装事件", "首次安装时上报一次"),
            (CONSENT_LAUNCH, "启动事件", "每次启动软件时上报"),
            (CONSENT_PARSE, "解析事件", "每次解析视频时上报"),
            (CONSENT_DOWNLOAD, "下载事件", "每次下载视频时上报"),
        ],
        "日志上报": [
            (CONSENT_CRASH, "崩溃日志", "软件崩溃时上报类型、堆栈和系统信息"),
            (CONSENT_ERROR, "错误日志", "运行时异常上报，用于诊断和修复"),
        ],
        "云端权限": [
            (CONSENT_REMOTE_CONFIG, "远程配置读取", "允许从云端读取配置参数"),
            (CONSENT_REMOTE_SCRIPT, "远程脚本执行", "允许云端下发脚本并在本机执行"),
        ],
    }

    def __init__(self, current_version=None):
        # 如果未传版本号，从 app_config 获取
        if current_version is None:
            try:
                from app_config import VERSION_NUM
                current_version = VERSION_NUM
            except ImportError:
                current_version = "2.0.6"
        self.current_version = self._normalize_version(current_version)
        self.platform = "macos" if IS_MACOS else ("windows" if IS_WINDOWS else "linux")
        self.session = requests.Session()
        self.session.timeout = 10
        self._dismissed_file = self._get_dismissed_file_path()
        self._is_new_install = False
        self._client_id = self._load_or_create_client_id()
        self._api_token = ""
        # 用户数据采集同意状态
        self._consent_file = self._get_consent_file_path()
        self._consent = self._load_consent()
        self._consent_notified = self._consent.get("_notified", False)

    @staticmethod
    def _get_consent_file_path():
        try:
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_dir, "data_consent.json")
        except Exception:
            return os.path.join(os.path.expanduser("~"), "bilidown_consent.json")

    def _load_consent(self):
        """加载用户同意状态，缺失时使用默认值"""
        consent = dict(self._DEFAULT_CONSENT)
        try:
            if os.path.exists(self._consent_file):
                with open(self._consent_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    for k in self._DEFAULT_CONSENT:
                        if k in saved and isinstance(saved[k], bool):
                            consent[k] = saved[k]
                    if "_notified" in saved and isinstance(saved["_notified"], bool):
                        consent["_notified"] = saved["_notified"]
        except Exception as e:
            logger.debug(f"加载同意状态失败: {e}")
        return consent

    def _save_consent(self):
        """保存同意状态到文件"""
        try:
            os.makedirs(os.path.dirname(self._consent_file), exist_ok=True)
            with open(self._consent_file, 'w', encoding='utf-8') as f:
                json.dump(self._consent, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"保存同意状态失败: {e}")

    def is_consent(self, category):
        """检查指定类别的数据采集是否已获得用户同意"""
        return self._consent.get(category, False)

    def set_consent(self, category, agreed):
        """设置指定类别的同意状态"""
        if category in self._DEFAULT_CONSENT:
            self._consent[category] = bool(agreed)
            self._save_consent()

    def get_all_consent(self):
        """返回所有类别的同意状态（副本）"""
        return dict(self._consent)

    @property
    def consent_notified(self):
        """是否已提示过用户数据采集事宜"""
        return self._consent_notified

    def mark_consent_notified(self):
        """标记已提示过用户"""
        self._consent_notified = True
        self._consent["_notified"] = True
        self._save_consent()

    @staticmethod
    def _get_client_id_file_path():
        try:
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_dir, "client_id.txt")
        except Exception:
            return os.path.join(os.path.expanduser("~"), "bilidown_client_id.txt")

    def _load_or_create_client_id(self):
        try:
            id_file = self._get_client_id_file_path()
            if os.path.exists(id_file):
                with open(id_file, 'r', encoding='utf-8') as f:
                    cid = f.read().strip()
                if cid and len(cid) >= 16:
                    return cid
            self._is_new_install = True
            cid = uuid.uuid4().hex
            try:
                with open(id_file, 'w', encoding='utf-8') as f:
                    f.write(cid)
            except Exception as e:
                logger.debug(f"保存client_id失败: {e}")
            return cid
        except Exception as e:
            logger.debug(f"加载client_id失败: {e}")
            self._is_new_install = True
            return uuid.uuid4().hex

    @property
    def client_id(self):
        return self._client_id

    @property
    def is_first_launch(self):
        return self._is_new_install

    def report_event(self, event_type, extra=""):
        # 根据事件类型映射到对应的细粒度同意开关
        consent_map = {
            "install": self.CONSENT_INSTALL,
            "launch": self.CONSENT_LAUNCH,
            "parse_video": self.CONSENT_PARSE,
            "download_video": self.CONSENT_DOWNLOAD,
        }
        consent_key = consent_map.get(event_type)
        if consent_key is None:
            # 未定义的事件类型，默认不上报
            logger.debug(f"统计上报已跳过（未知事件类型）: {event_type}")
            return
        if not self.is_consent(consent_key):
            logger.debug(f"统计上报已跳过（用户未同意）: {event_type}")
            return
        def _do_report():
            try:
                resp = self.session.post(
                    f"{API_BASE}/stats/",
                    json={
                        "action": "report",
                        "event": event_type,
                        "platform": self.platform,
                        "version": self.current_version,
                        "client_id": self._client_id,
                        "extra": extra,
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        logger.debug(f"统计上报成功: {event_type}")
                    else:
                        logger.debug(f"统计上报返回非0: {data}")
                else:
                    logger.debug(f"统计上报HTTP错误: {resp.status_code}")
            except Exception as e:
                logger.debug(f"统计上报失败(不影响使用): {e}")

        threading.Thread(target=_do_report, daemon=True).start()

    @staticmethod
    def _get_dismissed_file_path():
        try:
            if hasattr(sys, '_MEIPASS'):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            return os.path.join(base_dir, "dismissed_announcements.json")
        except Exception:
            return os.path.join(os.path.expanduser("~"), "bilidown_dismissed.json")

    @staticmethod
    def _normalize_version(version_str):
        try:
            v = str(version_str).strip().lstrip("Vv")
            import re
            match = re.search(r'(\d+(?:\.\d+)*)', v)
            if match:
                return match.group(1)
            return version_str
        except Exception:
            return version_str

    def _parse_version(self, version_str):
        try:
            import re
            match = re.search(r'(\d+(?:\.\d+)*)', str(version_str).strip().lstrip("Vv"))
            if not match:
                return (0, 0, 0)
            parts = match.group(1).split(".")
            return tuple(int(p) for p in parts)
        except Exception:
            return (0, 0, 0)

    def _should_show_update(self, latest_version_str):
        from datetime import date

        current_parsed = self._parse_version(self.current_version)
        latest_parsed = self._parse_version(latest_version_str)
        if latest_parsed == (0, 0, 0):
            logger.info(f"最新版本号无效: {latest_version_str}，不提示更新")
            return False
        if current_parsed >= latest_parsed:
            logger.info(f"当前版本 {self.current_version}({current_parsed}) >= 最新版本 {latest_version_str}({latest_parsed})，无需更新")
            return False

        # 检查用户是否选择了"忽略此版本"或"今日不再提示"
        try:
            config_file = "app_config.json"
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                app_settings = cfg_data.get("app_settings", {})

                ignored_ver = app_settings.get("update_ignored_version", None)
                if ignored_ver and ignored_ver == latest_version_str:
                    logger.info(f"用户已忽略版本 {ignored_ver}，不提示更新（下一个版本会再次提示）")
                    return False

                skip_date = app_settings.get("update_skip_today_date", None)
                if skip_date and skip_date == date.today().isoformat():
                    logger.info(f"用户选择今日不再提示（记录日期={skip_date}），不显示更新弹窗")
                    return False
        except Exception as e:
            logger.debug(f"检查更新跳过设置时异常: {e}")

        return True

    def check_update(self, channel="stable"):
        logger.debug(f"检查更新: current_version={self.current_version}")
        try:
            result = self._check_custom_api(channel)
            if result is not None:
                if not result.get("has_update", False):
                    logger.debug("自建API返回无更新")
                    return result
                latest = result.get("latest_version", "")
                if not self._should_show_update(latest):
                    result["has_update"] = False
                    result["force_update"] = False
                else:
                    logger.info(f"自建API发现新版本: {latest}")
                return result
        except Exception as e:
            logger.debug(f"自建API检查失败: {e}")

        return {"has_update": False}

    def _check_custom_api(self, channel="stable"):
        try:
            params = {
                "version": self.current_version,
                "platform": self.platform,
                "channel": channel,
            }
            # 附带设备码，服务端据此判断是否返回内测版本
            if self._client_id:
                params["client_id"] = self._client_id
            resp = self.session.get(
                f"{API_BASE}/check",
                params=params,
                timeout=8,
            )
            if resp.status_code == 404:
                return None
            data = resp.json()
            if data.get("code") == 0:
                return data["data"]
            return None
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.Timeout:
            return None
        except Exception:
            return None

    def get_announcements(self):
        try:
            result = self._get_custom_announcements()
            if result is not None:
                return result
        except Exception as e:
            logger.debug(f"自建公告API失败: {e}")

        return {"has_announcement": False, "announcements": []}

    def _get_custom_announcements(self):
        try:
            resp = self.session.get(
                f"{API_BASE}/announcement",
                params={
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 404:
                return None
            data = resp.json()
            if data.get("code") == 0:
                return data["data"]
            return None
        except requests.exceptions.ConnectionError:
            return None
        except requests.exceptions.Timeout:
            return None
        except Exception:
            return None

    def get_dismissed_ids(self):
        try:
            if os.path.exists(self._dismissed_file):
                with open(self._dismissed_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return []

    def dismiss_announcement(self, ann_id):
        try:
            dismissed = self.get_dismissed_ids()
            if ann_id not in dismissed:
                dismissed.append(ann_id)
            with open(self._dismissed_file, "w", encoding="utf-8") as f:
                json.dump(dismissed, f)
        except Exception as e:
            logger.error(f"保存已关闭公告失败: {e}")

    def filter_announcements(self, announcements):
        dismissed = self.get_dismissed_ids()
        now = time.time()
        filtered = []
        for ann in announcements:
            ann_id = ann.get("id", "")
            if ann_id in dismissed and ann.get("dismissible", True):
                continue
            start = ann.get("start_time", "")
            end = ann.get("end_time", "")
            if start:
                try:
                    from datetime import datetime
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    if start_dt.timestamp() > now:
                        continue
                except Exception:
                    pass
            if end:
                try:
                    from datetime import datetime
                    end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
                    if end_dt.timestamp() < now:
                        continue
                except Exception:
                    pass
            min_v = ann.get("min_version", "")
            max_v = ann.get("max_version", "")
            if min_v:
                if self._parse_version(self.current_version) < self._parse_version(min_v):
                    continue
            if max_v:
                if self._parse_version(self.current_version) > self._parse_version(max_v):
                    continue
            filtered.append(ann)
        return filtered

    @staticmethod
    def verify_file(filepath, expected_sha256):
        if not expected_sha256:
            return True
        sha256 = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest() == expected_sha256
        except Exception:
            return False

    @staticmethod
    def _calc_chunk_count(file_size):
        if file_size <= 0:
            return 1
        if file_size < 10 * 1024 * 1024:
            return 1
        if file_size < 50 * 1024 * 1024:
            return 2
        if file_size < 150 * 1024 * 1024:
            return 4
        if file_size < 500 * 1024 * 1024:
            return 6
        return 8

    def _download_chunk(self, url, start, end, chunk_path, chunk_idx, progress_state, lock, progress_callback, total_size):
        try:
            headers = {"Range": f"bytes={start}-{end}"}
            resp = self.session.get(url, headers=headers, stream=True, timeout=(10, 30))
            if resp.status_code not in (200, 206):
                raise Exception(f"分片{chunk_idx}下载失败: HTTP {resp.status_code}")
            downloaded = 0
            last_data_time = time.time()
            with open(chunk_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        last_data_time = time.time()
                        with lock:
                            progress_state["downloaded"] += len(chunk)
                            if progress_callback and total_size > 0:
                                pct = int(progress_state["downloaded"] * 100 / total_size)
                                progress_callback(pct, progress_state["downloaded"], total_size)
                    else:
                        # iter_content 返回空块，检查是否超时
                        if time.time() - last_data_time > 30:
                            raise Exception(f"分片{chunk_idx}数据传输超时(30s)")
        except Exception as e:
            with lock:
                progress_state["errors"].append(f"分片{chunk_idx}: {e}")
            raise

    def download_update(self, download_url, save_path, progress_callback=None):
        try:
            if download_url.startswith('/'):
                download_url = f"https://www.bilidown.cn{download_url}"

            print(f"[DEBUG] download_update 被调用")
            print(f"[DEBUG] 下载URL: {download_url}")
            print(f"[DEBUG] 保存路径: {save_path}")
            print(f"[DEBUG] 有进度回调: {progress_callback is not None}")
            logger.info(f"下载更新文件: {download_url}")
            result = self._download_single(download_url, save_path, progress_callback)
            print(f"[DEBUG] download_update 结果: {result}")
            logger.info(f"下载结果: {result}, 文件大小: {os.path.getsize(save_path) if os.path.exists(save_path) else 0}")
            return result
        except Exception as e:
            print(f"[DEBUG] download_update 异常: {e}")
            logger.error(f"下载更新失败: {e}")
            return False

    def _download_single(self, download_url, save_path, progress_callback=None):
        try:
            print(f"[DEBUG下载] ========== 开始下载 ==========")
            print(f"[DEBUG下载] URL: {download_url}")
            print(f"[DEBUG下载] 保存路径: {save_path}")
            logger.info(f"[下载] 开始下载: {download_url}")
            if progress_callback:
                print(f"[DEBUG下载] 发送初始进度回调(-1, 0, 0)")
                progress_callback(-1, 0, 0)
                logger.info(f"[下载] 已发送初始进度回调")

            # 先用 HEAD 获取文件大小
            total = 0
            try:
                print(f"[DEBUG下载] 发起HEAD请求...")
                head_resp = self.session.head(download_url, timeout=10, allow_redirects=True)
                total = int(head_resp.headers.get("content-length", 0))
                print(f"[DEBUG下载] HEAD结果: status={head_resp.status_code}, content-length={total}, url={head_resp.url}")
                logger.info(f"[下载] HEAD结果: status={head_resp.status_code}, content-length={total}")
            except Exception as e:
                print(f"[DEBUG下载] HEAD请求失败: {e}")
                logger.warning(f"[下载] HEAD请求失败: {e}")

            print(f"[DEBUG下载] 发起GET请求 (stream=True)...")
            logger.info(f"[下载] 发起GET请求...")
            resp = self.session.get(download_url, stream=True, timeout=(15, 120))
            print(f"[DEBUG下载] GET响应: status={resp.status_code}, content-length={resp.headers.get('content-length')}, url={resp.url}")
            logger.info(f"[下载] GET响应: status={resp.status_code}, content-length={resp.headers.get('content-length')}")

            # 检查HTTP状态码
            if resp.status_code != 200:
                print(f"[DEBUG下载] 状态码非200: {resp.status_code}, 响应前200字符: {resp.text[:200]}")
                logger.warning(f"[下载] 状态码非200: {resp.status_code}")
                resp.close()
                raise Exception(f"HTTP {resp.status_code}")

            if total <= 0:
                total = int(resp.headers.get("content-length", 0))

            downloaded = 0
            last_report = 0
            report_interval = max(total // 100, 65536) if total > 0 else 524288
            print(f"[DEBUG下载] 文件总大小: {total} bytes ({total/1048576:.1f} MB), 报告间隔: {report_interval}")
            logger.info(f"[下载] 文件总大小: {total}, 报告间隔: {report_interval}")

            chunk_count = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        chunk_count += 1
                        # 每10个chunk输出一次debug
                        if chunk_count % 10 == 0:
                            print(f"[DEBUG下载] 已读取 {chunk_count} 个chunk, 共 {downloaded} bytes")
                        if progress_callback and (downloaded - last_report >= report_interval):
                            last_report = downloaded
                            if total > 0:
                                progress = min(int(downloaded * 100 / total), 99)
                                print(f"[DEBUG下载] 进度回调: {progress}% ({downloaded}/{total})")
                                logger.info(f"[下载] 进度: {progress}% ({downloaded}/{total})")
                                progress_callback(progress, downloaded, total)
                            else:
                                print(f"[DEBUG下载] 进度回调: {downloaded} bytes (未知总大小)")
                                logger.info(f"[下载] 进度: {downloaded} bytes (未知总大小)")
                                progress_callback(-1, downloaded, 0)

            # 下载完成，报告100%
            print(f"[DEBUG下载] ========== 下载完成 ==========")
            print(f"[DEBUG下载] 总计: {downloaded} bytes, chunk数: {chunk_count}")
            logger.info(f"[下载] 下载完成, 总计: {downloaded} bytes")
            if progress_callback:
                if total > 0:
                    print(f"[DEBUG下载] 最终进度回调: 100%")
                    progress_callback(100, downloaded, total)
                else:
                    progress_callback(-1, downloaded, 0)

            if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                print(f"[DEBUG下载] 文件保存验证失败: {save_path}")
                logger.warning(f"更新文件保存验证失败：{save_path}")
                return False
            actual_size = os.path.getsize(save_path)
            print(f"[DEBUG下载] 文件验证通过: {save_path}, 大小: {actual_size}")
            return True
        except Exception as e:
            logger.error(f"单线程下载失败: {e}")
            return False

    @staticmethod
    def _cleanup_chunks(temp_dir):
        try:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def report_error(self, error_type, error_message, error_stack="", extra_data=None):
        if not self.is_consent(self.CONSENT_ERROR):
            logger.debug(f"错误上报已跳过（用户未同意）: {error_type}")
            return
        def _do_report():
            try:
                resp = self.session.post(
                    f"{API_BASE}/stats/",
                    json={
                        "action": "report_error",
                        "error_type": error_type,
                        "error_message": str(error_message)[:500],
                        "error_stack": str(error_stack)[:2000],
                        "platform": self.platform,
                        "version": self.current_version,
                        "client_id": self._client_id,
                        "extra": json.dumps(extra_data, ensure_ascii=False) if extra_data else "",
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 0:
                        logger.debug(f"错误上报成功: {error_type}")
                    else:
                        logger.debug(f"错误上报返回非0: {data}")
            except Exception as e:
                logger.debug(f"错误上报失败(不影响使用): {e}")

        threading.Thread(target=_do_report, daemon=True).start()

    def get_remote_files(self):
        if not self.is_consent(self.CONSENT_REMOTE_SCRIPT):
            logger.debug("远程文件列表获取已跳过（用户未同意远程脚本）")
            return []
        try:
            resp = self.session.get(
                f"{API_BASE}/file_manage/",
                params={
                    "action": "list",
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"].get("files", [])
        except Exception as e:
            logger.debug(f"获取远程文件列表失败: {e}")
        return []

    def get_remote_file(self, file_path):
        if not self.is_consent(self.CONSENT_REMOTE_SCRIPT):
            logger.debug(f"远程文件读取已跳过（用户未同意远程脚本）: {file_path}")
            return None
        try:
            resp = self.session.get(
                f"{API_BASE}/file_manage/",
                params={
                    "action": "read",
                    "path": file_path,
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"获取远程文件失败: {e}")
        return None

    def save_remote_file_local(self, file_path, save_path, expected_sha256=None):
        try:
            file_data = self.get_remote_file(file_path)
            if not file_data:
                return False
            content = file_data.get("file_content", "")
            if content is None:
                return False
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(content)
            if expected_sha256 and not self.verify_file(save_path, expected_sha256):
                os.remove(save_path)
                return False
            return True
        except Exception as e:
            logger.error(f"保存远程文件本地失败: {e}")
            return False

    def check_incremental_update(self):
        try:
            resp = self.session.get(
                f"{API_BASE}/patch/",
                params={
                    "action": "check",
                    "from_version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"检查增量更新失败: {e}")
        return None

    def get_incremental_patch_list(self):
        try:
            resp = self.session.get(
                f"{API_BASE}/patch/",
                params={
                    "action": "list",
                    "from_version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"].get("patches", [])
        except Exception as e:
            logger.debug(f"获取增量包列表失败: {e}")
        return []

    def download_incremental_patch(self, patch_id, save_path, progress_callback=None):
        try:
            url = f"{API_BASE}/patch/?action=download&id={patch_id}"
            if url.startswith('/'):
                url = f"https://www.bilidown.cn{url}"
            logger.info(f"下载增量包: {patch_id}")
            return self._download_single(url, save_path, progress_callback)
        except Exception as e:
            logger.error(f"下载增量包失败: {e}")
            return False

    def apply_incremental_patch(self, patch_zip_path, target_dir):
        try:
            import zipfile
            if not os.path.exists(patch_zip_path):
                logger.error(f"增量包不存在: {patch_zip_path}")
                return False
            logger.info(f"应用增量包: {patch_zip_path} -> {target_dir}")
            os.makedirs(target_dir, exist_ok=True)
            with zipfile.ZipFile(patch_zip_path, 'r') as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    file_path = os.path.join(target_dir, member.filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with zf.open(member) as src, open(file_path, 'wb') as dst:
                        dst.write(src.read())
            logger.info("增量包应用完成")
            return True
        except Exception as e:
            logger.error(f"应用增量包失败: {e}")
            return False

    def set_api_base(self, base_url):
        global API_BASE
        API_BASE = base_url.rstrip('/')
        logger.info(f"API基地址已设置为: {API_BASE}")

    def set_api_token(self, token):
        self._api_token = token
        if token:
            self.session.headers.update({"X-API-Token": token})
        else:
            self.session.headers.pop("X-API-Token", None)
        logger.info(f"API Token已设置")

    def get_remote_config(self):
        """获取适用于当前版本的远程配置"""
        if not self.is_consent(self.CONSENT_REMOTE_CONFIG):
            logger.debug("远程配置获取已跳过（用户未同意远程配置）")
            return {}
        try:
            resp = self.session.get(
                f"{API_BASE}/config/",
                params={
                    "action": "get",
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"获取远程配置失败: {e}")
        return {}

    def get_feature_switch(self, key, default=False):
        """获取单个功能开关状态"""
        configs = self.get_remote_config()
        val = configs.get(key)
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).lower() in ('true', '1', 'yes')

    def check_version_blacklist(self):
        """检查当前版本是否被拉黑"""
        try:
            resp = self.session.get(
                f"{API_BASE}/blacklist/",
                params={
                    "action": "check",
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"检查版本黑名单失败: {e}")
        return {"blocked": False}

    def check_hotfix(self):
        """检查是否有热修复补丁"""
        try:
            resp = self.session.get(
                f"{API_BASE}/hotfix/",
                params={
                    "action": "check",
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"检查热修复失败: {e}")
        return {"has_hotfix": False}

    def download_hotfix(self, hotfix_id, save_path):
        """下载热修复补丁"""
        try:
            url = f"{API_BASE}/hotfix/?action=download&id={hotfix_id}"
            return self._download_single(url, save_path)
        except Exception as e:
            logger.error(f"下载热修复失败: {e}")
            return False

    def apply_hotfix(self, hotfix_path):
        """应用热修复补丁（覆盖到程序目录）"""
        try:
            import zipfile
            target_dir = os.path.dirname(os.path.abspath(hotfix_path))
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if zipfile.is_zipfile(hotfix_path):
                with zipfile.ZipFile(hotfix_path, 'r') as zf:
                    zf.extractall(app_dir)
                logger.info("热修复zip应用完成")
            else:
                shutil.copy2(hotfix_path, app_dir)
                logger.info("热修复文件应用完成")
            return True
        except Exception as e:
            logger.error(f"应用热修复失败: {e}")
            return False

    def check_gray_release(self, version=None):
        """检查客户端是否在灰度发布范围内"""
        try:
            resp = self.session.get(
                f"{API_BASE}/gray/",
                params={
                    "action": "check",
                    "version": version or self.current_version,
                    "platform": self.platform,
                    "client_id": self._client_id,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"检查灰度发布失败: {e}")
        return {"in_gray": False}

    def check_beta_auth(self, qq_number="", client_id=None):
        """验证内测QQ号授权

        :param qq_number: 用户输入的QQ号，可为空（首次检查设备是否已绑定）
        :param client_id: 设备码，为空时使用 self._client_id
        :return: dict, 包含 authorized / reason / qq_number / is_new_bind / cooldown_remaining
        """
        cid = client_id or self._client_id
        try:
            resp = self.session.get(
                f"{API_BASE}/beta/",
                params={
                    "action": "auth",
                    "client_id": cid,
                    "qq": qq_number,
                    "platform": self.platform,
                    "version": self.current_version,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data.get("data", {})
        except Exception as e:
            logger.debug(f"内测授权验证失败: {e}")
        return {"authorized": False, "reason": "network_error"}

    def get_abtest_variant(self, test_key):
        """获取A/B测试分配的实验组"""
        try:
            resp = self.session.get(
                f"{API_BASE}/abtest/",
                params={
                    "action": "get",
                    "test_key": test_key,
                    "client_id": self._client_id,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"].get("variant")
        except Exception as e:
            logger.debug(f"获取A/B测试分组失败: {e}")
        return None

    def get_emergency_notices(self):
        """获取紧急公告列表"""
        try:
            resp = self.session.get(
                f"{API_BASE}/emergency/",
                params={
                    "action": "list",
                    "version": self.current_version,
                    "platform": self.platform,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"获取紧急公告失败: {e}")
        return []

    def report_crash(self, crash_type, crash_message, stack_trace="", system_info=""):
        """上报崩溃日志"""
        # 用户未同意崩溃上报时不上报
        if not self.is_consent(self.CONSENT_CRASH):
            logger.debug(f"崩溃上报已跳过（用户未同意）: {crash_type}")
            return
        def _do_report():
            try:
                resp = self.session.post(
                    f"{API_BASE}/crash/",
                    json={
                        "action": "report",
                        "client_id": self._client_id,
                        "version": self.current_version,
                        "platform": self.platform,
                        "crash_type": crash_type,
                        "crash_message": str(crash_message)[:1000],
                        "stack_trace": str(stack_trace)[:4000],
                        "system_info": str(system_info)[:2000],
                    },
                    timeout=5,
                )
                if resp.status_code == 200:
                    logger.debug(f"崩溃上报成功: {crash_type}")
            except Exception as e:
                logger.debug(f"崩溃上报失败(不影响使用): {e}")

        threading.Thread(target=_do_report, daemon=True).start()

    def upload_crash_log(self, log_content, crash_id=None):
        """上传详细崩溃日志文件"""
        # 用户未同意崩溃上报时不上报
        if not self.is_consent(self.CONSENT_CRASH):
            logger.debug("崩溃日志上传已跳过（用户未同意）")
            return
        def _do_upload():
            try:
                resp = self.session.post(
                    f"{API_BASE}/crash/",
                    json={
                        "action": "upload_log",
                        "client_id": self._client_id,
                        "crash_id": crash_id or "",
                        "log_content": str(log_content)[:50000],
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    logger.debug("崩溃日志上传成功")
            except Exception as e:
                logger.debug(f"崩溃日志上传失败: {e}")

        threading.Thread(target=_do_upload, daemon=True).start()

    def submit_feedback(self, feedback_type, title, content, contact="", system_info=""):
        """提交用户反馈"""
        try:
            resp = self.session.post(
                f"{API_BASE}/feedback/",
                json={
                    "action": "submit",
                    "client_id": self._client_id,
                    "version": self.current_version,
                    "platform": self.platform,
                    "feedback_type": feedback_type,
                    "title": title,
                    "content": content,
                    "contact": contact,
                    "system_info": system_info,
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return data["data"]
        except Exception as e:
            logger.debug(f"提交反馈失败: {e}")
        return None

    def get_full_cloud_status(self):
        """一次性获取所有云端状态（配置、黑名单、热修复、灰度、紧急公告）"""
        result = {
            "config": {},
            "blacklisted": False,
            "hotfix": {"has_hotfix": False},
            "gray": {"in_gray": False},
            "emergency_notices": [],
        }
        try:
            result["config"] = self.get_remote_config()
        except:
            pass
        try:
            bl = self.check_version_blacklist()
            result["blacklisted"] = bl.get("blocked", False)
            result["blacklist_info"] = bl
        except:
            pass
        try:
            result["hotfix"] = self.check_hotfix()
        except:
            pass
        try:
            result["gray"] = self.check_gray_release()
        except:
            pass
        try:
            result["emergency_notices"] = self.get_emergency_notices()
        except:
            pass
        return result
