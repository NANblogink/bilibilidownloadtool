import requests
import logging
import hashlib
import json
import os
import sys
import time
import threading
from platform_utils import IS_MACOS, IS_WINDOWS, exe

logger = logging.getLogger(__name__)

API_BASE = "https://www.bilidown.cn/api/v1"
GITHUB_API = "https://api.github.com/repos/NANblogink/bilibilidownloadtool/releases/latest"


class CloudService:
    def __init__(self, current_version="2.0.2"):
        self.current_version = current_version
        self.platform = "macos" if IS_MACOS else ("windows" if IS_WINDOWS else "linux")
        self.session = requests.Session()
        self.session.timeout = 10
        self._dismissed_file = self._get_dismissed_file_path()

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

    def _parse_version(self, version_str):
        try:
            parts = version_str.strip().lstrip("Vv").split(".")
            return tuple(int(p) for p in parts if p.isdigit())
        except Exception:
            return (0, 0, 0)

    def check_update(self, channel="stable"):
        try:
            result = self._check_custom_api(channel)
            if result is not None:
                if not result.get("has_update", False):
                    return result
                latest = result.get("latest_version", "")
                if latest and self._parse_version(self.current_version) >= self._parse_version(latest):
                    result["has_update"] = False
                return result
        except Exception as e:
            logger.debug(f"自建API检查失败，回退到GitHub: {e}")

        try:
            result = self._check_github_api()
            if result.get("has_update", False):
                latest = result.get("latest_version", "")
                if latest and self._parse_version(self.current_version) >= self._parse_version(latest):
                    result["has_update"] = False
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

            has_update = latest > current

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

    def download_update(self, download_url, save_path, progress_callback=None):
        try:
            if download_url.startswith('/'):
                download_url = f"https://www.bilidown.cn{download_url}"
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
            return True
        except Exception as e:
            logger.error(f"下载更新失败: {e}")
            return False
