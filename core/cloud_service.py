import requests
import logging
import hashlib
import json
import os
import re
import sys
import time
import threading
import uuid
from platform_utils import IS_MACOS, IS_WINDOWS, exe

logger = logging.getLogger(__name__)

API_BASE = "https://www.bilidown.cn/api/v1"

class CloudService:
    def __init__(self, current_version=None):
        if current_version is None:
            try:
                from app_config import VERSION_NUM
                current_version = VERSION_NUM
            except ImportError:
                current_version = "2.0.6"
        self.current_version = self._normalize_version(current_version)
        self.platform = "macos" if IS_MACOS else ("windows" if IS_WINDOWS else "linux")
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.timeout = 10
        self._dismissed_file = self._get_dismissed_file_path()
        self._is_new_install = False
        self._client_id = self._load_or_create_client_id()
        self._api_token = ""

    @staticmethod
    def _get_client_id_file_paths():
        paths = []
        seen = set()

        def _add(p):
            if not p:
                return
            try:
                norm = os.path.normcase(os.path.abspath(p))
            except Exception:
                return
            if norm not in seen:
                seen.add(norm)
                paths.append(p)

        for base in (os.environ.get('LOCALAPPDATA'), os.environ.get('APPDATA')):
            if base:
                _add(os.path.join(base, 'BilibiliDownloadTool', 'client_id.txt'))
        try:
            _add(os.path.join(os.path.expanduser('~'), '.bilidown', 'client_id.txt'))
        except Exception:
            pass

        try:
            from logger_config import get_app_dir
            _add(os.path.join(get_app_dir(), 'client_id.txt'))
        except Exception:
            pass

        try:
            _add(os.path.join(os.path.expanduser("~"), "bilidown_client_id.txt"))
        except Exception:
            pass
        return paths

    @staticmethod
    def _get_client_id_file_path():
        """主路径：优先用户数据目录。"""
        return CloudService._get_client_id_file_paths()[0]

    @staticmethod
    def _read_client_id_from(path):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    cid = f.read().strip()
                if cid and len(cid) >= 16:
                    return cid
        except Exception:
            pass
        return ""

    @staticmethod
    def _write_client_id_to(path, cid):
        try:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(cid)
            try:
                os.replace(tmp, path)
            except Exception:
                os.remove(tmp)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(cid)
            return True
        except Exception as e:
            logger.debug(f"保存client_id失败({path}): {e}")
            return False

    @staticmethod
    def _machine_identity():
        import platform
        import hashlib
        parts = []
        try:
            parts.append(platform.node() or '')
        except Exception:
            pass
        try:
            parts.append(platform.machine() or '')
        except Exception:
            pass
        if IS_WINDOWS:
            try:
                import subprocess
                try:
                    from platform_utils import subprocess_no_window_kwargs as _snwk
                except Exception:
                    def _snwk():
                        return {}
                out = subprocess.run(
                    ['reg', 'query',
                     r'HKLM\SOFTWARE\Microsoft\Cryptography',
                     '/v', 'MachineGuid'],
                    capture_output=True, text=True, timeout=5,
                    **_snwk()
                )
                for line in (out.stdout or '').splitlines():
                    if 'MachineGuid' in line:
                        parts.append(line.split()[-1].strip())
                        break
            except Exception:
                pass
        try:
            import uuid as _uuid
            mac = _uuid.getnode()
            if mac:
                parts.append('%012x' % mac)
        except Exception:
            pass
        seed = '|'.join(p for p in parts if p)
        if not seed:
            return ""
        return hashlib.sha256(('bilidown-device:' + seed).encode('utf-8')).hexdigest()

    def _load_or_create_client_id(self):
        try:
            paths = self._get_client_id_file_paths()

            for p in paths:
                cid = self._read_client_id_from(p)
                if cid:
                    for other in paths:
                        if other != p and not self._read_client_id_from(other):
                            self._write_client_id_to(other, cid)
                    self._is_new_install = False
                    return cid

            cid = None
            machine_id = self._machine_identity()
            if machine_id and len(machine_id) >= 16:
                cid = machine_id
                logger.info("未发现历史设备码，已按本机特征生成稳定设备码")
            else:
                cid = uuid.uuid4().hex

            for p in paths:
                self._write_client_id_to(p, cid)

            self._is_new_install = machine_id == ""
            return cid
        except Exception as e:
            logger.debug(f"加载client_id失败: {e}")
            self._is_new_install = True
            try:
                _m = self._machine_identity()
                if _m:
                    return _m
            except Exception:
                pass
            return uuid.uuid4().hex

    @property
    def client_id(self):
        return self._client_id

    @property
    def is_first_launch(self):
        return self._is_new_install

    @staticmethod
    def _get_dismissed_file_path():
        try:
            from logger_config import get_app_dir
            base_dir = get_app_dir()
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
            # 正式版更新检查只需版本/平台/通道，不上传设备标识。
            if channel == "beta" and self._client_id:
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

            logger.debug(f"[DEBUG] download_update 被调用")
            logger.debug(f"[DEBUG] 下载URL: {download_url}")
            logger.debug(f"[DEBUG] 保存路径: {save_path}")
            logger.debug(f"[DEBUG] 有进度回调: {progress_callback is not None}")
            logger.info(f"下载更新文件: {download_url}")
            result = self._download_single(download_url, save_path, progress_callback)
            logger.debug(f"[DEBUG] download_update 结果: {result}")
            logger.info(f"下载结果: {result}, 文件大小: {os.path.getsize(save_path) if os.path.exists(save_path) else 0}")
            return result
        except Exception as e:
            logger.debug(f"[DEBUG] download_update 异常: {e}")
            logger.error(f"下载更新失败: {e}")
            return False

    def _download_single(self, download_url, save_path, progress_callback=None):
        try:
            logger.debug(f"[DEBUG下载] ========== 开始下载 ==========")
            logger.debug(f"[DEBUG下载] URL: {download_url}")
            logger.debug(f"[DEBUG下载] 保存路径: {save_path}")
            logger.info(f"[下载] 开始下载: {download_url}")
            if progress_callback:
                logger.debug(f"[DEBUG下载] 发送初始进度回调(-1, 0, 0)")
                progress_callback(-1, 0, 0)
                logger.info(f"[下载] 已发送初始进度回调")

            total = 0
            try:
                logger.debug(f"[DEBUG下载] 发起HEAD请求...")
                head_resp = self.session.head(download_url, timeout=10, allow_redirects=True)
                total = int(head_resp.headers.get("content-length", 0))
                logger.debug(f"[DEBUG下载] HEAD结果: status={head_resp.status_code}, content-length={total}, url={head_resp.url}")
                logger.info(f"[下载] HEAD结果: status={head_resp.status_code}, content-length={total}")
            except Exception as e:
                logger.debug(f"[DEBUG下载] HEAD请求失败: {e}")
                logger.warning(f"[下载] HEAD请求失败: {e}")

            logger.debug(f"[DEBUG下载] 发起GET请求 (stream=True)...")
            logger.info(f"[下载] 发起GET请求...")
            resp = self.session.get(download_url, stream=True, timeout=(15, 120))
            logger.debug(f"[DEBUG下载] GET响应: status={resp.status_code}, content-length={resp.headers.get('content-length')}, url={resp.url}")
            logger.info(f"[下载] GET响应: status={resp.status_code}, content-length={resp.headers.get('content-length')}")

            if resp.status_code != 200:
                logger.debug(f"[DEBUG下载] 状态码非200: {resp.status_code}, 响应前200字符: {resp.text[:200]}")
                logger.warning(f"[下载] 状态码非200: {resp.status_code}")
                resp.close()
                raise Exception(f"HTTP {resp.status_code}")

            if total <= 0:
                total = int(resp.headers.get("content-length", 0))

            downloaded = 0
            last_report = 0
            report_interval = max(total // 100, 65536) if total > 0 else 524288
            logger.debug(f"[DEBUG下载] 文件总大小: {total} bytes ({total/1048576:.1f} MB), 报告间隔: {report_interval}")
            logger.info(f"[下载] 文件总大小: {total}, 报告间隔: {report_interval}")

            chunk_count = 0
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        chunk_count += 1
                        if chunk_count % 10 == 0:
                            logger.debug(f"[DEBUG下载] 已读取 {chunk_count} 个chunk, 共 {downloaded} bytes")
                        if progress_callback and (downloaded - last_report >= report_interval):
                            last_report = downloaded
                            if total > 0:
                                progress = min(int(downloaded * 100 / total), 99)
                                logger.debug(f"[DEBUG下载] 进度回调: {progress}% ({downloaded}/{total})")
                                logger.info(f"[下载] 进度: {progress}% ({downloaded}/{total})")
                                progress_callback(progress, downloaded, total)
                            else:
                                logger.debug(f"[DEBUG下载] 进度回调: {downloaded} bytes (未知总大小)")
                                logger.info(f"[下载] 进度: {downloaded} bytes (未知总大小)")
                                progress_callback(-1, downloaded, 0)

            logger.debug(f"[DEBUG下载] ========== 下载完成 ==========")
            logger.debug(f"[DEBUG下载] 总计: {downloaded} bytes, chunk数: {chunk_count}")
            logger.info(f"[下载] 下载完成, 总计: {downloaded} bytes")

            if total > 0 and downloaded < total:
                pct = downloaded * 100.0 / total
                logger.debug(f"[DEBUG下载] 文件下载不完整: 已下载 {downloaded}/{total} bytes ({pct:.1f}%)")
                logger.error(f"[下载] 文件下载不完整：已下载 {downloaded}/{total} bytes ({pct:.1f}%)，文件已截断，丢弃损坏文件")
                try:
                    if os.path.exists(save_path):
                        os.remove(save_path)
                except Exception:
                    pass
                return False

            if progress_callback:
                if total > 0:
                    logger.debug(f"[DEBUG下载] 最终进度回调: 100%")
                    progress_callback(100, downloaded, total)
                else:
                    progress_callback(-1, downloaded, 0)

            if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                logger.debug(f"[DEBUG下载] 文件保存验证失败: {save_path}")
                logger.warning(f"更新文件保存验证失败：{save_path}")
                return False
            actual_size = os.path.getsize(save_path)
            logger.debug(f"[DEBUG下载] 文件验证通过: {save_path}, 大小: {actual_size}")
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
        """应用热修复补丁"""
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

    def submit_feedback(self, feedback_type, title, content, contact="", system_info=""):
        """提交用户反馈"""
        try:
            resp = self.session.post(
                f"{API_BASE}/feedback/",
                json={
                    "action": "submit",
                    "feedback_type": feedback_type,
                    "title": title,
                    "content": content,
                    "contact": contact,
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
        """一次性获取所有云端状态"""
        result = {
            "blacklisted": False,
            "hotfix": {"has_hotfix": False},
            "gray": {"in_gray": False},
            "emergency_notices": [],
        }
        try:
            bl = self.check_version_blacklist()
            result["blacklisted"] = bl.get("blocked", False)
            result["blacklist_info"] = bl
        except Exception:
            pass
        try:
            result["hotfix"] = self.check_hotfix()
        except Exception:
            pass
        try:
            result["emergency_notices"] = self.get_emergency_notices()
        except Exception:
            pass
        return result
