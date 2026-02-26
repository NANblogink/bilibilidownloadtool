# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
import os
import json

class ConfigLoader:
    def __init__(self):
        self.config_file = "app_config.json"
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
                "16": "360P", "32": "480P", "64": "720P", "74": "720P高码率",
                "80": "1080P", "112": "1080P+", "120": "1080P高码率",
                "125": "4K HDR", "127": "4K 杜比视界"
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
                "danmaku_api": "https://api.bilibili.com/x/v1/dm/list.so?oid={oid}&type={type}"
            },
            "other_urls": {
                "hevc_extension_url": "https://apps.microsoft.com/store/detail/microsoft-hevc-video-extension/9NMZQFK7HTR4"
            },
            "app_settings": {
                "default_save_path": os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载"),
                "last_save_path": "",
                "max_threads": 2
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
                    return config
            except Exception as e:
                print(f"加载配置文件失败：{str(e)}")
                return self._get_default_config()
        else:
            return self._get_default_config()

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