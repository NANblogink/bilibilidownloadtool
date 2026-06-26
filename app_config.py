import os
import json
import logging

logger = logging.getLogger(__name__)

APP_NAME = "B站视频解析工具"
APP_NAME_EN = "BilibiliDownloader"
APP_DESCRIPTION = "B站视频解析下载工具"
APP_VERSION = "V2.0.7"
VERSION_NUM = "2.0.7"
APP_AUTHOR = "寒烟似雪"
APP_AUTHOR_QQ = "2273962061"
APP_WEBSITE = "https://www.bilidown.cn"
APP_REPO = "https://github.com/NANblogink/bilibilidownloadtool"

SHORTCUT_NAME = APP_NAME + APP_VERSION

CLOUD_DOWNLOAD_URLS = [
    f"https://www.bilidown.cn/api/check?type=installer&version={VERSION_NUM}",
    "https://gitee.com/api/v5/repos/nanblogink/bilibilidownloadtool/releases/latest",
    "https://api.github.com/repos/NANblogink/bilibilidownloadtool/releases/latest",
]


def load_version_info():
    import sys
    candidate_paths = []

    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        internal_dir = os.path.join(exe_dir, '_internal')
        candidate_paths.append(os.path.join(internal_dir, 'version_info.json'))
        candidate_paths.append(os.path.join(exe_dir, 'version_info.json'))

    if hasattr(sys, '_MEIPASS'):
        candidate_paths.append(os.path.join(sys._MEIPASS, 'version_info.json'))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_paths.append(os.path.join(script_dir, 'version_info.json'))
    candidate_paths.append(os.path.join(script_dir, 'config', 'version_info.json'))

    for path in candidate_paths:
        if os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if not data.get("version"):
                    continue
                data.setdefault("version", APP_VERSION)
                data.setdefault("author", APP_AUTHOR)
                data.setdefault("qq", APP_AUTHOR_QQ)
                data.setdefault("description", APP_DESCRIPTION)
                return data
            except Exception:
                continue
    return {
        "version": APP_VERSION,
        "author": APP_AUTHOR,
        "qq": APP_AUTHOR_QQ,
        "description": APP_DESCRIPTION,
    }
