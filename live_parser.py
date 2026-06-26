# -*- coding: utf-8 -*-
"""
B站直播 API 封装
功能：直播间信息查询、直播流获取、直播录制、回放下载
"""

import os
import time
import logging
import requests
import threading

logger = logging.getLogger(__name__)

# 直播状态映射
LIVE_STATUS_MAP = {
    0: "未开播",
    1: "直播中",
    2: "轮播中"
}

# 画质映射
QUALITY_MAP = {
    80: "流畅",
    150: "高清",
    250: "超清",
    400: "蓝光",
    10000: "原画",
    20000: "4K",
    25000: "默认",
    30000: "杜比"
}

# 直播API基础URL
LIVE_API_BASE = "https://api.live.bilibili.com"


class LiveParser:
    """B站直播API封装"""

    def __init__(self, config=None, cookies=None, csrf_token=""):
        self.config = config
        self.cookies = cookies or {}
        self.csrf_token = csrf_token
        self.session = requests.Session()

        # 浏览器请求头
        self._headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': 'https://live.bilibili.com/',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'https://live.bilibili.com',
            'Connection': 'keep-alive',
        }
        self.session.headers.update(self._headers)

        # 更新cookie
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
        logger.info(f"直播API Cookie已更新，共{len(self.cookies)}个字段")

    def _get(self, endpoint, params=None):
        """GET请求"""
        url = f"{LIVE_API_BASE}{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                error_msg = data.get("message", "未知错误")
                logger.warning(f"直播API请求失败: {endpoint} -> {error_msg}")
                return {"success": False, "error": error_msg, "code": data.get("code")}
            return {"success": True, "data": data.get("data", {})}
        except requests.exceptions.RequestException as e:
            logger.error(f"直播API网络错误: {endpoint} -> {str(e)}")
            return {"success": False, "error": f"网络错误: {str(e)}"}
        except Exception as e:
            logger.error(f"直播API解析错误: {endpoint} -> {str(e)}")
            return {"success": False, "error": f"解析错误: {str(e)}"}

    def _post(self, endpoint, data=None):
        """POST请求"""
        url = f"{LIVE_API_BASE}{endpoint}"
        try:
            post_data = data or {}
            if self.csrf_token:
                post_data['csrf'] = self.csrf_token
                post_data['csrf_token'] = self.csrf_token
            resp = self.session.post(url, data=post_data, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                error_msg = result.get("message", "未知错误")
                logger.warning(f"直播API POST失败: {endpoint} -> {error_msg}")
                return {"success": False, "error": error_msg, "code": result.get("code")}
            return {"success": True, "data": result.get("data", {})}
        except requests.exceptions.RequestException as e:
            logger.error(f"直播API网络错误: {endpoint} -> {str(e)}")
            return {"success": False, "error": f"网络错误: {str(e)}"}
        except Exception as e:
            logger.error(f"直播API解析错误: {endpoint} -> {str(e)}")
            return {"success": False, "error": f"解析错误: {str(e)}"}

    # ==================== 直播间信息 ====================

    def get_room_info(self, room_id):
        """
        获取直播间信息
        :param room_id: 房间号（短号或长号）
        :return: 直播间详细信息
        """
        result = self._get("/room/v1/Room/get_info", {"room_id": room_id})
        if not result["success"]:
            return result
        data = result["data"]
        return {
            "success": True,
            "data": {
                "uid": data.get("uid"),
                "room_id": data.get("room_id"),
                "short_id": data.get("short_id"),
                "title": data.get("title", ""),
                "live_status": data.get("live_status", 0),
                "live_status_text": LIVE_STATUS_MAP.get(data.get("live_status", 0), "未知"),
                "live_time": data.get("live_time", ""),
                "online": data.get("online", 0),
                "attention": data.get("attention", 0),
                "description": data.get("description", ""),
                "user_cover": data.get("user_cover", ""),
                "keyframe": data.get("keyframe", ""),
                "area_name": data.get("area_name", ""),
                "parent_area_name": data.get("parent_area_name", ""),
                "tags": data.get("tags", ""),
                "is_portrait": data.get("is_portrait", False),
            }
        }

    def room_init(self, room_id):
        """
        房间初始化（短号转长号）
        :param room_id: 短号
        :return: 真实房间ID、主播UID等
        """
        result = self._get("/room/v1/Room/room_init", {"id": room_id})
        if not result["success"]:
            return result
        data = result["data"]
        return {
            "success": True,
            "data": {
                "room_id": data.get("room_id"),
                "short_id": data.get("short_id"),
                "uid": data.get("uid"),
                "live_status": data.get("live_status", 0),
                "live_status_text": LIVE_STATUS_MAP.get(data.get("live_status", 0), "未知"),
                "is_hidden": data.get("is_hidden", False),
                "is_locked": data.get("is_locked", False),
                "encrypted": data.get("encrypted", False),
                "pwd_verified": data.get("pwd_verified", False),
                "live_time": data.get("live_time", 0),
                "is_sp": data.get("is_sp", 0),
            }
        }

    def get_master_info(self, uid):
        """
        获取主播信息
        :param uid: 主播mid
        """
        result = self._get("/live_user/v1/Master/info", {"uid": uid})
        if not result["success"]:
            return result
        data = result["data"]
        info = data.get("info", {})
        return {
            "success": True,
            "data": {
                "uid": info.get("uid"),
                "uname": info.get("uname", ""),
                "face": info.get("face", ""),
                "gender": info.get("gender", ""),
                "follower_num": data.get("follower_num", 0),
                "room_id": data.get("room_id", 0),
                "medal_name": data.get("medal_name", ""),
                "room_news": data.get("room_news", {}),
            }
        }

    def get_room_base_info(self, room_ids):
        """
        批量获取直播间基本信息
        :param room_ids: 房间ID列表
        """
        if isinstance(room_ids, (list, tuple)):
            room_ids_str = ",".join(str(r) for r in room_ids)
        else:
            room_ids_str = str(room_ids)
        result = self._get("/xlive/web-room/v1/index/getRoomBaseInfo", {
            "req_biz": "web_room_componet",
            "room_ids": room_ids_str
        })
        return result

    # ==================== 直播流 ====================

    def get_live_stream_url(self, room_id, platform="web", qn=None):
        """
        获取直播流地址
        :param room_id: 真实房间号（长号）
        :param platform: web=http-flv, h5=hls(m3u8)
        :param qn: 画质代码，None=自动最高
        :return: 直播流URL列表
        """
        params = {
            "cid": room_id,
            "platform": platform,
        }
        if qn:
            params["qn"] = qn

        result = self._get("/room/v1/Room/playUrl", params)
        if not result["success"]:
            return result
        data = result["data"]
        durl = data.get("durl", [])
        quality_desc = data.get("quality_description", [])
        return {
            "success": True,
            "data": {
                "current_quality": data.get("current_quality"),
                "current_qn": data.get("current_qn"),
                "accept_quality": data.get("accept_quality", []),
                "quality_description": quality_desc,
                "stream_urls": [
                    {
                        "url": d.get("url", ""),
                        "order": d.get("order", 0),
                    }
                    for d in durl
                ],
            }
        }

    def get_best_live_stream(self, room_id, prefer_hls=True):
        """
        获取最佳直播流（自动选最高画质）
        :param room_id: 真实房间号
        :param prefer_hls: True=优先HLS(m3u8), False=FLV
        :return: 直播流URL
        """
        platform = "h5" if prefer_hls else "web"
        result = self.get_live_stream_url(room_id, platform=platform)
        if not result["success"]:
            return result
        urls = result["data"]["stream_urls"]
        if not urls:
            return {"success": False, "error": "未获取到直播流地址，可能未开播"}
        # 取第一个URL（通常是最佳线路）
        return {
            "success": True,
            "data": {
                "url": urls[0]["url"],
                "platform": platform,
                "current_qn": result["data"]["current_qn"],
                "quality_description": result["data"]["quality_description"],
            }
        }

    # ==================== 直播回放 ====================

    def get_replay_list(self, page=1, page_size=30):
        """
        获取自己的直播回放列表（仅14天内）
        :param page: 页码
        :param page_size: 每页数量（最大30）
        """
        result = self._get("/xlive/app-blink/v1/anchorVideo/AnchorGetReplayList", {
            "page": page,
            "page_size": page_size
        })
        if not result["success"]:
            return result
        data = result["data"]
        replay_list = data.get("replay_info") or []
        return {
            "success": True,
            "data": {
                "replay_list": [
                    {
                        "replay_id": r.get("replay_id"),
                        "room_id": r.get("room_id"),
                        "live_key": r.get("live_key", ""),
                        "start_time": r.get("start_time", 0),
                        "end_time": r.get("end_time", 0),
                        "title": r.get("live_info", {}).get("title", ""),
                        "cover": r.get("live_info", {}).get("cover", ""),
                        "live_time": r.get("live_info", {}).get("live_time", ""),
                        "duration": r.get("video_info", {}).get("duration", 0),
                        "replay_status": r.get("video_info", {}).get("replay_status", 0),
                        "download_url": r.get("video_info", {}).get("download_url", ""),
                    }
                    for r in replay_list
                ],
                "pagination": data.get("pagination", {}),
            }
        }

    def _format_replay_list(self, data):
        """统一格式化回放列表响应"""
        replay_list = data.get("replay_info") or []
        return {
            "success": True,
            "data": {
                "replay_list": [
                    {
                        "replay_id": r.get("replay_id"),
                        "room_id": r.get("room_id"),
                        "live_key": r.get("live_key", ""),
                        "start_time": r.get("start_time", 0),
                        "end_time": r.get("end_time", 0),
                        "title": r.get("live_info", {}).get("title", ""),
                        "cover": r.get("live_info", {}).get("cover", ""),
                        "live_time": r.get("live_info", {}).get("live_time", ""),
                        "duration": r.get("video_info", {}).get("duration", 0),
                        "replay_status": r.get("video_info", {}).get("replay_status", 0),
                        "download_url": r.get("video_info", {}).get("download_url", ""),
                    }
                    for r in replay_list
                ],
                "pagination": data.get("pagination", {}),
            }
        }

    def get_other_replay_list(self, live_uid, time_range=3, page=1, page_size=30):
        """
        获取某位主播的回放列表（需要授权）
        :param live_uid: 主播UID
        :param time_range: 1=近3天, 2=近7天, 3=近14天
        """
        # 优先尝试 app-blink 端点（对登录态要求更宽松）
        result = self._get("/xlive/app-blink/v1/anchorVideo/AnchorGetReplayList", {
            "live_uid": live_uid,
            "time_range": time_range,
            "page": page,
            "page_size": page_size
        })
        if result["success"]:
            logger.info(f"获取他人回放成功(app-blink): uid={live_uid}")
            return self._format_replay_list(result["data"])

        # 失败时回退到 web-room 端点
        logger.warning(f"app-blink 获取他人回放失败，回退 web-room: {result.get('error')}")
        result = self._get("/xlive/web-room/v1/videoService/GetOtherSliceList", {
            "live_uid": live_uid,
            "time_range": time_range,
            "page": page,
            "page_size": page_size
        })
        if not result["success"]:
            return result
        return self._format_replay_list(result["data"])

    def request_replay_download(self, record_id=None, live_key=None):
        """
        请求整场直播回放下载链接（未生成时会触发生成）
        :param record_id: 回放ID
        :param live_key: 直播场次key
        :return: 下载链接或生成状态
        """
        post_data = {}
        if record_id:
            post_data["record_id"] = record_id
        elif live_key:
            post_data["live_key"] = live_key
        else:
            return {"success": False, "error": "必须提供record_id或live_key"}

        result = self._post("/xlive/app-blink/v1/anchorVideo/AnchorVideoDownload", post_data)
        if not result["success"]:
            return result
        data = result["data"]
        record = data.get("record", {})
        status = record.get("status", 0)
        # status: 30=合成中, 2=已完成
        download_url = data.get("download_url", "")
        download_url_list = data.get("download_url_list", [])

        return {
            "success": True,
            "data": {
                "status": status,
                "is_ready": status == 2,
                "is_processing": status == 30,
                "download_url": download_url,
                "download_url_list": download_url_list,
                "estimated_time": record.get("estimated_time", 0),
                "current_time": record.get("current_time", 0),
                "toast": record.get("toast", ""),
            }
        }

    def get_slice_stream(self, live_key, start_time, end_time):
        """
        获取切片视频流
        :param live_key: 直播场次key
        :param start_time: 开始时间戳（秒）
        :param end_time: 结束时间戳（秒）
        :return: 切片视频流列表
        """
        result = self._get("/xlive/app-blink/v1/anchorVideo/GetSliceStream", {
            "live_key": live_key,
            "start_time": start_time,
            "end_time": end_time,
        })
        if not result["success"]:
            return result
        data = result["data"]
        stream_list = data.get("list") or []
        return {
            "success": True,
            "data": {
                "stream_list": [
                    {
                        "start_time": s.get("start_time", 0),
                        "end_time": s.get("end_time", 0),
                        "stream_url": s.get("stream", ""),
                        "type": s.get("type", 0),
                    }
                    for s in stream_list
                ],
                "ban_list": data.get("ban_list") or [],
            }
        }

    def get_live_session_data(self, live_key, start_tm, end_tm):
        """
        获取直播会话数据（弹幕统计、高光时刻等）
        :param live_key: 直播场次key
        :param start_tm: 开始时间 yyyy-MM-dd HH:MM:SS
        :param end_tm: 结束时间 yyyy-MM-dd HH:MM:SS
        """
        result = self._get("/xlive/app-blink/v1/anchorVideo/GetLiveSessionData", {
            "live_key": live_key,
            "start_tm": start_tm,
            "end_tm": end_tm,
        })
        if not result["success"]:
            return result
        data = result["data"]
        return {
            "success": True,
            "data": {
                "session_data": data.get("session_data", []),
                "max_danmaku": data.get("max_danmaku", 0),
                "max_pcu": data.get("max_pcu", 0),
                "high_light_data": data.get("high_light_data", []),
                "ass_url": data.get("ass_url", ""),
            }
        }

    # ==================== 直播管理 ====================

    def start_live(self, room_id, area_v2, platform="pc"):
        """
        开始直播（获取推流地址）
        :param room_id: 自己的直播间ID
        :param area_v2: 直播分区ID
        :param platform: pc/pc_link/android_link
        """
        post_data = {
            "room_id": room_id,
            "area_v2": area_v2,
            "platform": platform,
        }
        result = self._post("/room/v1/Room/startLive", post_data)
        if not result["success"]:
            return result
        data = result["data"]
        rtmp = data.get("rtmp", {})
        return {
            "success": True,
            "data": {
                "status": data.get("status", ""),
                "change": data.get("change", 0),
                "live_key": data.get("live_key", ""),
                "rtmp_addr": rtmp.get("addr", ""),
                "rtmp_code": rtmp.get("code", ""),
                "provider": rtmp.get("provider", ""),
            }
        }

    def stop_live(self, room_id, platform="pc_link"):
        """
        关闭直播
        :param room_id: 自己的直播间ID
        :param platform: pc_link/android_link
        """
        post_data = {
            "room_id": room_id,
            "platform": platform,
        }
        result = self._post("/room/v1/Room/stopLive", post_data)
        return result

    def update_room_info(self, room_id, title=None, area_id=None):
        """
        更新直播间信息
        :param room_id: 自己的直播间ID
        :param title: 新标题（最多40字符）
        :param area_id: 分区ID
        """
        post_data = {"room_id": room_id}
        if title:
            post_data["title"] = title[:40]
        if area_id:
            post_data["area_id"] = area_id
        result = self._post("/room/v1/Room/update", post_data)
        return result
