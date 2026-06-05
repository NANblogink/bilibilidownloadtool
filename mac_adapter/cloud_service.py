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
GITHUB_API = "https://api.github.com/repos/NANblogink/bilibilidownloadtool/releases/latest"


class CloudService:
    def __init__(self, current_version="2.0.3"):
        self.current_version = self._normalize_version(current_version)
        self.platform = "macos" if IS_MACOS else ("windows" if IS_WINDOWS else "linux")
        self.session = requests.Session()
        self.session.timeout = 10
        self._dismissed_file = self._get_dismissed_file_path()
        self._is_new_install = False
        self._client_id = self._load_or_create_client_id()

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
        current_parsed = self._parse_version(self.current_version)
        latest_parsed = self._parse_version(latest_version_str)
        if latest_parsed == (0, 0, 0):
            logger.info(f"最新版本号无效: {latest_version_str}，不提示更新")
            return False
        if current_parsed >= latest_parsed:
            logger.info(f"当前版本 {self.current_version}({current_parsed}) >= 最新版本 {latest_version_str}({latest_parsed})，无需更新")
            return False
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
            logger.debug(f"自建API检查失败，回退到GitHub: {e}")

        try:
            result = self._check_github_api()
            if result.get("has_update", False):
                latest = result.get("latest_version", "")
                if not self._should_show_update(latest):
                    result["has_update"] = False
                    result["force_update"] = False
                else:
                    logger.info(f"GitHub API发现新版本: {latest}")
            return result
        except Exception as e:
            logger.error(f"GitHub API检查也失败: {e}")
            return {"has_update": False}

    def _check_custom_api(self, channel="stable"):
        try:
            resp = self.session.get(
                f"{API_BASE}/check",
                params={
                    "version": self.current_version,
                    "platform": self.platform,
                    "channel": channel,
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

    def _check_github_api(self):
        try:
            headers = {"Accept": "application/vnd.github.v3+json"}
            resp = self.session.get(GITHUB_API, headers=headers, timeout=10)
            if resp.status_code != 200:
                return {"has_update": False}

            release = resp.json()
            tag = release.get("tag_name", "")
            latest_version = tag.lstrip("Vv")

            if not self._parse_version(latest_version) or self._parse_version(latest_version) == (0, 0, 0):
                import re
                for asset in release.get("assets", []):
                    name = asset.get("name", "")
                    match = re.search(r'V?(\d+\.\d+(?:\.\d+)?)', name, re.I)
                    if match:
                        latest_version = match.group(1)
                        break
                if not latest_version or self._parse_version(latest_version) == (0, 0, 0):
                    match = re.search(r'V?(\d+\.\d+(?:\.\d+)?)', release.get("name", ""), re.I)
                    if match:
                        latest_version = match.group(1)

            current = self._parse_version(self.current_version)
            latest = self._parse_version(latest_version)

            has_update = latest > current and latest != (0, 0, 0)

            download_url = ""
            file_size = 0
            for asset in release.get("assets", []):
                name = asset.get("name", "").lower()
                if IS_WINDOWS:
                    is_main = name.endswith(".exe") and "installer" not in name and "uninstall" not in name
                elif IS_MACOS:
                    is_main = name.endswith(".dmg") and "installer" not in name and "uninstall" not in name
                else:
                    is_main = "installer" not in name and "uninstall" not in name and not name.endswith('.py')
                if is_main:
                    download_url = asset.get("browser_download_url", "")
                    file_size = asset.get("size", 0)
                    break

            if not download_url:
                download_url = release.get("html_url", "")

            release_notes = release.get("body", "")

            return {
                "has_update": has_update,
                "latest_version": latest_version,
                "min_supported_version": "",
                "force_update": False,
                "release_notes": release_notes,
                "download_url": download_url,
                "file_size": file_size,
                "sha256": "",
                "release_date": release.get("published_at", "")[:10] if release.get("published_at") else "",
                "source": "github",
            }
        except Exception as e:
            logger.error(f"GitHub API检查失败: {e}")
            return {"has_update": False}

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
            resp = self.session.get(url, headers=headers, stream=True, timeout=60)
            if resp.status_code not in (200, 206):
                raise Exception(f"分片{chunk_idx}下载失败: HTTP {resp.status_code}")
            downloaded = 0
            with open(chunk_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        with lock:
                            progress_state["downloaded"] += len(chunk)
                            if progress_callback and total_size > 0:
                                pct = int(progress_state["downloaded"] * 100 / total_size)
                                progress_callback(pct, progress_state["downloaded"], total_size)
        except Exception as e:
            with lock:
                progress_state["errors"].append(f"分片{chunk_idx}: {e}")
            raise

    def download_update(self, download_url, save_path, progress_callback=None):
        try:
            if download_url.startswith('/'):
                download_url = f"https://www.bilidown.cn{download_url}"

            head_resp = self.session.head(download_url, timeout=10, allow_redirects=True)
            total_size = int(head_resp.headers.get("content-length", 0))
            accept_ranges = head_resp.headers.get("accept-ranges", "").lower()
            supports_range = accept_ranges == "bytes" and total_size > 0

            chunk_count = self._calc_chunk_count(total_size) if supports_range else 1

            if chunk_count <= 1 or not supports_range:
                logger.info(f"使用单线程下载 (supports_range={supports_range}, total={total_size})")
                return self._download_single(download_url, save_path, progress_callback)

            logger.info(f"使用{chunk_count}线程分片下载 (total={total_size / 1048576:.1f}MB)")
            chunk_size = total_size // chunk_count
            temp_dir = os.path.join(os.path.dirname(save_path), "_chunks")
            os.makedirs(temp_dir, exist_ok=True)

            progress_state = {"downloaded": 0, "errors": []}
            lock = threading.Lock()
            threads = []

            for i in range(chunk_count):
                start = i * chunk_size
                if i == chunk_count - 1:
                    end = total_size - 1
                else:
                    end = start + chunk_size - 1
                chunk_path = os.path.join(temp_dir, f"chunk_{i}")
                t = threading.Thread(
                    target=self._download_chunk,
                    args=(download_url, start, end, chunk_path, i, progress_state, lock, progress_callback, total_size),
                    daemon=True,
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join(timeout=600)

            if progress_state["errors"]:
                logger.error(f"分片下载出错: {progress_state['errors']}")
                self._cleanup_chunks(temp_dir)
                return False

            with open(save_path, "wb") as out_f:
                for i in range(chunk_count):
                    chunk_path = os.path.join(temp_dir, f"chunk_{i}")
                    if not os.path.exists(chunk_path):
                        self._cleanup_chunks(temp_dir)
                        return False
                    with open(chunk_path, "rb") as cf:
                        while True:
                            data = cf.read(65536)
                            if not data:
                                break
                            out_f.write(data)

            self._cleanup_chunks(temp_dir)

            if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                logger.warning(f"更新文件保存验证失败：{save_path}")
                return False
            actual_size = os.path.getsize(save_path)
            if total_size > 0 and actual_size != total_size:
                logger.warning(f"更新文件大小不匹配: 期望{total_size}, 实际{actual_size}")
            return True
        except Exception as e:
            logger.error(f"下载更新失败: {e}")
            return False

    def _download_single(self, download_url, save_path, progress_callback=None):
        try:
            resp = self.session.get(download_url, stream=True, timeout=30)
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total > 0:
                            progress = int(downloaded * 100 / total)
                            progress_callback(progress, downloaded, total)
            if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                logger.warning(f"更新文件保存验证失败：{save_path}")
                return False
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
