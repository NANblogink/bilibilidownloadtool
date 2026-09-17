import os
import json
import sys

import _pathsetup


def _default_download_dir():
    """默认下载目录：程序所在目录下的 B站下载。

    注意：本模块位于 core/ 子目录，必须用 project_root() 取项目根，
    否则默认下载目录会落到 core/B站下载。
    （打包后该目录只读时，下载设置里可自行改到可写盘。）
    """
    try:
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = _pathsetup.project_root()
        return os.path.join(base, "B站下载")
    except Exception:
        return os.path.join(os.path.expanduser("~"), "B站下载")


def _get_app_dir():
    """返回可写的应用目录（绝对路径）。
    MSIX 沙箱安装目录只读，先尝试 exe 目录（绿色版可写），不可写则回退用户数据目录。
    使用绝对路径避免因进程工作目录(cwd)不同导致设置被读写到别处而丢失。

    注意：本模块位于 core/ 子目录，必须用 _pathsetup.project_root() 取项目根，
    否则配置会落到 core/app_config.json —— 用户原有的根目录配置会被忽略。
    """
    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            try:
                probe = os.path.join(exe_dir, '.std_internal_probe')
                with open(probe, 'w') as f:
                    f.write('ok')
                os.remove(probe)
                return exe_dir
            except Exception:
                pass
            try:
                base = os.environ.get('APPDATA') or os.path.expanduser('~\\AppData\\Roaming')
                app_dir = os.path.join(base, 'BilibiliDownloadTool')
                os.makedirs(app_dir, exist_ok=True)
                return app_dir
            except Exception:
                pass
    except Exception:
        pass
    try:
        return _pathsetup.project_root()
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


class ConfigLoader:
    def __init__(self):
        self.config_file = os.path.join(_get_app_dir(), "app_config.json")
        self.config = self._load_config()
    def _get_default_config(self):
        return {
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Cache-Control": "no-cache",
                "Origin": "https://www.bilibili.com",
                "Connection": "keep-alive",
                "Pragma": "no-cache",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-site"
            },
            "quality_map": {
                "16": "360P", "32": "480P", "64": "720P", "74": "720P60 高帧率",
                "80": "1080P", "100": "1080P 智能修复", "112": "1080P+", "116": "1080P60 高帧率",
                "120": "4K", "125": "4K 高码率", "126": "杜比视界", "127": "8K"
            },
            "api_urls": {
                "login_status_api": "https://api.bilibili.com/x/web-interface/nav?jsonp=jsonp",
                "user_info_api": "https://api.bilibili.com/x/space/wbi/acc/info?mid={mid}&jsonp=jsonp",
                "av_info_api": "https://api.bilibili.com/x/web-interface/view?aid={aid}&jsonp=jsonp",
                "cid_api": "https://api.bilibili.com/x/player/pagelist?bvid={bvid}&jsonp=jsonp",
                "video_info_api": "https://api.bilibili.com/x/web-interface/view?bvid={bvid}&jsonp=jsonp",
                "play_url_api": "https://api.bilibili.com/x/player/playurl?fnval={fnval}&cid={cid}&bvid={bvid}&fourk=1&otype=json",
                "tv_play_url_api": "https://api.bilibili.com/x/player/playurl?fnval=16&cid={cid}&bvid={bvid}&platform=tv&otype=json",
                "bangumi_section_api": "https://api.bilibili.com/pgc/web/season/section?season_id={ssid}",
                "bangumi_play_url_api": "https://api.bilibili.com/pgc/player/web/playurl?cid={cid}&bvid={bvid}&fnval={fnval}&fourk=1&otype=json",
                "danmaku_api": "https://api.bilibili.com/x/v1/dm/list.so?oid={oid}&type={type}",
                "emoji_my_panel_api": "https://api.bilibili.com/x/emote/user/panel/web",
                "emoji_all_panel_api": "https://api.bilibili.com/x/emote/setting/panel",
                "emoji_package_detail_api": "https://api.bilibili.com/x/emote/package"
            },
            "other_urls": {
                "hevc_extension_url": "https://apps.microsoft.com/store/detail/microsoft-hevc-video-extension/9NMZQFK7HTR4"
            },
            "app_settings": {
                "default_save_path": _default_download_dir(),
                "last_save_path": "",
                # 缓存/临时目录：留空表示自动选择（优先与下载目标同盘，
                # 避免把临时文件写到系统盘 C: 导致 C 盘爆满）
                "cache_dir": "",
                "max_threads": 2,
                "auto_convert_incompatible": False,
                "hevc_not_supported_ask": True,
                "add_episode_to_filename": True,
                "batch_download_first": False,
                "filename_add_author": False,
                "use_author_folder": False,
                "use_collection_folder": False,
                "collection_folder_mode": "author",
                "favorites_refresh_mode": "manual",
                "gpu_acceleration": None,
                "app_icon_mode": "default",
                "custom_icon_path": "",
                "emoji_last_save_path": "",
                "emoji_business": "reply",
                "audio_last_save_path": "",
                "show_recording_tray": True
            }
        }
    def _load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    default_config = self._get_default_config()
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                        elif isinstance(value, dict):
                            for subkey, subvalue in value.items():
                                if subkey not in config[key]:
                                    config[key][subkey] = subvalue
                    self._migrate_settings(config)
                    return config
            except Exception as e:
                print(f"加载配置文件失败：{str(e)}")
                return self._get_default_config()
        else:
            return self._get_default_config()

    @staticmethod
    def _migrate_settings(config):
        """修正历史遗留的错误默认值。

        代码分层后 core/config.py 的 __file__ 指向 core/，曾导致默认下载路径被写成
        <项目根>/core/B站下载。已存在的配置文件里这个错误值会被保留，
        这里在加载时纠正为项目根下的 B站下载（用户手动改过的路径不动）。
        """
        try:
            s = config.get("app_settings")
            if not isinstance(s, dict):
                return
            cur = (s.get("default_save_path") or "").strip()
            if not cur:
                s["default_save_path"] = _default_download_dir()
                return
            # 仅当路径恰好是"某个 core/B站下载"时才纠正，避免误改用户自定义目录
            norm = os.path.normpath(cur).replace("/", "\\").lower()
            if norm.endswith("\\core\\b站下载"):
                s["default_save_path"] = _default_download_dir()
                return

            # 历史配置里可能保存了已被删除/移动的目录（例如早期版本的
            # "V2.0.8 TO Github\B站下载"）。指向不存在的父目录会导致下载无处可存，
            # 这里回落到项目根下的 B站下载，并在日志中说明。
            parent = os.path.dirname(cur)
            if parent and not os.path.isdir(parent):
                fallback = _default_download_dir()
                print(f"下载目录已失效（{cur}），已自动改为：{fallback}")
                s["default_save_path"] = fallback
        except Exception:
            pass
    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存配置文件失败：{str(e)}")
            return False
    def get_headers(self):
        return self.config.get("headers", {})
    def get_quality_map(self):
        return {int(k): v for k, v in self.config.get("quality_map", {}).items()}
    def get_api_url(self, key):
        return self.config.get("api_urls", {}).get(key, "")
    def get_other_url(self, key):
        return self.config.get("other_urls", {}).get(key, "")
    def get_app_setting(self, key, default=None):
        return self.config.get("app_settings", {}).get(key, default)
    def set_app_setting(self, key, value):
        if "app_settings" not in self.config:
            self.config["app_settings"] = {}
        self.config["app_settings"][key] = value
        return self.save_config()
