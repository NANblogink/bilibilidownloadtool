import os
import json
import logging

import _pathsetup

logger = logging.getLogger(__name__)

APP_NAME = "B站视频解析工具"
APP_NAME_EN = "BilibiliDownloader"
APP_DESCRIPTION = "B站视频解析下载工具"
APP_VERSION = "V2.2.4"
VERSION_NUM = "2.2.4"
APP_AUTHOR = "寒烟似雪"
APP_AUTHOR_QQ = "2273962061"
APP_WEBSITE = "https://www.bilidown.cn"
APP_REPO = "https://github.com/NANblogink/bilibilidownloadtool"
BETA_QQ_GROUP = "https://jq.qq.com/?_wv=1027&k=714822491"

IS_BETA_BUILD = False

SHORTCUT_NAME = APP_NAME + APP_VERSION

CLOUD_DOWNLOAD_URLS = [
    f"https://www.bilidown.cn/api/v1/check?type=installer&version={VERSION_NUM}",
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

    root_dir = _pathsetup.project_root()
    candidate_paths.append(os.path.join(root_dir, 'version_info.json'))
    candidate_paths.append(os.path.join(root_dir, 'config', 'version_info.json'))
    candidate_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'version_info.json'))

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


def is_safe_install_path(path):
    if not path or not str(path).strip():
        return False, "路径为空"
    raw = str(path).strip()
    try:
        norm_path = os.path.normpath(raw)
    except Exception:
        return False, f"路径无效：{raw}"

    drive, tail = os.path.splitdrive(norm_path)
    if drive and (not tail or tail in (os.sep, '/', '\\')):
        return False, f"禁止使用驱动器根目录作为安装/卸载路径：{drive}"

    # 末段须含应用标识
    last_part = os.path.basename(norm_path)
    if not last_part:
        return False, f"路径无效：{norm_path}"
    app_keywords = ('bilibili', '哔哩')
    if not any(kw.lower() in last_part.lower() for kw in app_keywords):
        return False, (f"安装目录名需包含应用标识(Bilibili/哔哩)，"
                       f"当前目录名为：{last_part}")

    win_dir = os.environ.get('SystemRoot', r'C:\Windows')
    pf = os.environ.get('ProgramFiles', r'C:\Program Files')
    pf86 = os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')
    home = os.path.expanduser('~')
    dangerous = {
        os.path.normpath(p).lower() for p in (
            win_dir, pf, pf86, home,
            os.path.join(win_dir, 'System32'),
            os.path.join(win_dir, 'SysWOW64'),
        ) if p
    }
    if norm_path.lower() in dangerous:
        return False, f"禁止使用系统关键目录：{norm_path}"

    return True, ""
