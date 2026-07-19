# -*- coding: utf-8 -*-
"""
B站表情包 API 封装
功能：表情包列表查询、表情包明细获取
API 文档：https://sessionhu.github.io/bilibili-API-collect/docs/emoji/list.html
"""

import logging
import requests

logger = logging.getLogger(__name__)

EMOJI_API_BASE = "https://api.bilibili.com"

PACKAGE_TYPE_MAP = {
    1: "普通",
    2: "会员专属",
    3: "购买所得",
    4: "颜文字"
}

BUSINESS_MAP = {
    "reply": "评论区",
    "dynamic": "动态"
}


class EmojiParser:
    """B站表情包API封装"""

    def __init__(self, config=None, cookies=None, csrf_token=""):
        self.config = config
        self.cookies = cookies or {}
        self.csrf_token = csrf_token
        self.session = requests.Session()

        # 浏览器请求头
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'https://www.bilibili.com',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self._headers)

        if self.cookies:
            for k, v in self.cookies.items():
                self.session.cookies.set(k, v, domain=".bilibili.com")

    def update_cookies(self, cookies, csrf_token=""):
        """更新Cookie和CSRF Token"""
        self.cookies = cookies or {}
        self.csrf_token = csrf_token
        self.session.cookies.clear()
        if self.cookies:
            for k, v in self.cookies.items():
                self.session.cookies.set(k, v, domain=".bilibili.com")
        logger.info(f"表情包API Cookie已更新，共{len(self.cookies)}个字段")

    def _get(self, url, params=None):
        """GET请求"""
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                error_msg = data.get("message", "未知错误")
                logger.warning(f"表情包API请求失败: {url} -> {error_msg}")
                return {"success": False, "error": error_msg, "code": data.get("code")}
            return {"success": True, "data": data.get("data", {})}
        except requests.exceptions.RequestException as e:
            logger.error(f"表情包API网络错误: {url} -> {str(e)}")
            return {"success": False, "error": f"网络错误: {str(e)}"}
        except Exception as e:
            logger.error(f"表情包API解析错误: {url} -> {str(e)}")
            return {"success": False, "error": f"解析错误: {str(e)}"}

    def _format_package(self, pkg):
        """格式化表情包对象，提取关键字段"""
        if not isinstance(pkg, dict):
            return None
        emote_list = []
        for emote in pkg.get("emote", []) or []:
            meta = emote.get("meta", {}) or {}
            emote_list.append({
                "id": emote.get("id"),
                "package_id": emote.get("package_id"),
                "text": emote.get("text", ""),           # 转义符，如 [微笑]
                "url": emote.get("url", ""),              # 图片URL
                "mtime": emote.get("mtime", 0),
                "type": emote.get("type", 1),
                "type_name": PACKAGE_TYPE_MAP.get(emote.get("type", 1), "未知"),
                "alias": meta.get("alias", ""),           # 简写名
                "size": meta.get("size", 1),              # 1小 2大
            })
        meta = pkg.get("meta", {}) or {}
        flags = pkg.get("flags", {}) or {}
        return {
            "id": pkg.get("id"),
            "text": pkg.get("text", ""),                  # 表情包名称
            "url": pkg.get("url", ""),                    # 表情包封面URL
            "mtime": pkg.get("mtime", 0),
            "type": pkg.get("type", 1),
            "type_name": PACKAGE_TYPE_MAP.get(pkg.get("type", 1), "未知"),
            "meta": meta,
            "flags": flags,
            "added": flags.get("added", False),           # 是否已添加
            "emote_count": len(emote_list),
            "emote": emote_list,
        }

    def get_my_emojis(self, business="reply"):
        """
        获取我的表情包列表（需登录）
        :param business: 使用场景 reply:评论区 dynamic:动态
        :return: 表情包列表
        """
        url = "https://api.bilibili.com/x/emote/user/panel/web"
        result = self._get(url, {"business": business})
        if not result["success"]:
            return result
        packages = result["data"].get("packages", []) or []
        return {
            "success": True,
            "data": [self._format_package(p) for p in packages if self._format_package(p)]
        }

    def get_all_emojis(self, business="reply"):
        """
        获取所有表情包列表（需登录）
        返回用户拥有的表情包 + 全部表情包
        :param business: 使用场景
        :return: dict {user_packages, all_packages}
        """
        url = "https://api.bilibili.com/x/emote/setting/panel"
        result = self._get(url, {"business": business})
        if not result["success"]:
            return result
        data = result["data"]
        user_packages = data.get("user_panel_packages", []) or []
        all_packages = data.get("all_packages", []) or []
        return {
            "success": True,
            "data": {
                "user_packages": [self._format_package(p) for p in user_packages if self._format_package(p)],
                "all_packages": [self._format_package(p) for p in all_packages if self._format_package(p)],
            }
        }

    def get_package_detail(self, package_ids, business="reply"):
        """
        获取指定的表情包明细（免登录）
        :param package_ids: 表情包id，可为单个int或列表，多id用逗号分隔
        :param business: 使用场景
        :return: 表情包列表
        """
        if isinstance(package_ids, (list, tuple)):
            ids_str = ",".join(str(i) for i in package_ids)
        else:
            ids_str = str(package_ids)
        url = "https://api.bilibili.com/x/emote/package"
        result = self._get(url, {"ids": ids_str, "business": business})
        if not result["success"]:
            return result
        packages = result["data"].get("packages", []) or []
        return {
            "success": True,
            "data": [self._format_package(p) for p in packages if self._format_package(p)]
        }
