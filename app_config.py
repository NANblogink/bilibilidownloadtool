import os
import json
import logging

logger = logging.getLogger(__name__)

APP_NAME = "B站视频解析工具"
APP_NAME_EN = "BilibiliDownloader"
APP_DESCRIPTION = "B站视频解析下载工具"
APP_VERSION = "V2.1.1"
VERSION_NUM = "2.1.1"
APP_AUTHOR = "寒烟似雪"
APP_AUTHOR_QQ = "2273962061"
APP_WEBSITE = "https://www.bilidown.cn"
APP_REPO = "https://github.com/NANblogink/bilibilidownloadtool"
BETA_QQ_GROUP = "https://jq.qq.com/?_wv=1027&k=714822491"

# 是否为内测版本（打包内测包时改为 True，正式包保持 False）
# 内测包启动时需要输入授权QQ号验证，正式包无此限制
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


def is_safe_install_path(path):
    """校验安装/卸载路径是否安全，防止误删整盘或系统关键目录。

    触发本校验的典型事故：用户在安装时把路径选成驱动器根目录（如 D:\\ 或 D:），
    该值被写入注册表 InstallPath，卸载时 shutil.rmtree("D:\\") 会递归删除整盘数据。

    返回 (is_safe: bool, reason: str)。安全时 reason 为空字符串。
    """
    if not path or not str(path).strip():
        return False, "路径为空"
    raw = str(path).strip()
    try:
        norm_path = os.path.normpath(raw)
    except Exception:
        return False, f"路径无效：{raw}"

    # 1. 拒绝驱动器根目录，如 D:\ D:/ D: C:\
    drive, tail = os.path.splitdrive(norm_path)
    if drive and (not tail or tail in (os.sep, '/', '\\')):
        return False, f"禁止使用驱动器根目录作为安装/卸载路径：{drive}"

    # 2. 路径最后一段必须存在且包含应用标识，避免误选浅层无关目录
    last_part = os.path.basename(norm_path)
    if not last_part:
        return False, f"路径无效：{norm_path}"
    app_keywords = ('bilibili', '哔哩')
    if not any(kw.lower() in last_part.lower() for kw in app_keywords):
        return False, (f"安装目录名需包含应用标识(Bilibili/哔哩)，"
                       f"当前目录名为：{last_part}")

    # 3. 拒绝系统关键目录（即使名字巧合也拒绝）
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
