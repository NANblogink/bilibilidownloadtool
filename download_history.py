import os
import json
import time
import threading
import logging

logger = logging.getLogger(__name__)


class DownloadHistory:
    def __init__(self, history_file=None):
        if history_file is None:
            if hasattr(os.sys, '_MEIPASS'):
                base_dir = os.path.dirname(os.sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            self.history_file = os.path.join(base_dir, "download_history.json")
        else:
            self.history_file = history_file
        self._lock = threading.Lock()
        self._history = self._load()
        self._max_records = 500

    def _load(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception as e:
            logger.debug(f"加载下载历史失败: {e}")
        return []

    def _save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"保存下载历史失败: {e}")

    def add_record(self, bvid="", title="", url="", save_path="", file_path="",
                   quality="", file_size=0, status="success", error_msg=""):
        with self._lock:
            record = {
                "id": str(int(time.time() * 1000)),
                "bvid": bvid,
                "title": title[:200] if title else "",
                "url": url,
                "save_path": save_path,
                "file_path": file_path,
                "quality": quality,
                "file_size": file_size,
                "status": status,
                "error_msg": error_msg[:200] if error_msg else "",
                "timestamp": time.time(),
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            self._history.insert(0, record)
            if len(self._history) > self._max_records:
                self._history = self._history[:self._max_records]
            self._save()
            return record

    def get_records(self, keyword="", status_filter="", limit=100, offset=0):
        with self._lock:
            filtered = self._history
            if keyword:
                keyword_lower = keyword.lower()
                filtered = [r for r in filtered if
                            keyword_lower in r.get("title", "").lower() or
                            keyword_lower in r.get("bvid", "").lower() or
                            keyword_lower in r.get("url", "").lower()]
            if status_filter:
                filtered = [r for r in filtered if r.get("status") == status_filter]
            total = len(filtered)
            records = filtered[offset:offset + limit]
            return records, total

    def get_all_records(self):
        with self._lock:
            return list(self._history)

    def delete_record(self, record_id):
        with self._lock:
            self._history = [r for r in self._history if r.get("id") != record_id]
            self._save()

    def clear_records(self):
        with self._lock:
            self._history = []
            self._save()

    def get_search_history(self, limit=20):
        seen = set()
        result = []
        for r in self._history:
            title = r.get("title", "")
            bvid = r.get("bvid", "")
            key = title or bvid
            if key and key not in seen:
                seen.add(key)
                result.append({"title": title, "bvid": bvid, "url": r.get("url", "")})
                if len(result) >= limit:
                    break
        return result
