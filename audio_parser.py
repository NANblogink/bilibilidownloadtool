# -*- coding: utf-8 -*-
"""
B站音频（歌曲）API 封装
功能：歌曲信息查询、TAG、歌词、创作成员、音频流URL获取、收藏/投币状态、音频榜单
API 文档：
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/info.html
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/action.html
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/musicstream_url.html
  https://sessionhu.github.io/bilibili-API-collect/docs/audio/rank.html
"""

import logging
import requests

logger = logging.getLogger(__name__)

AUDIO_WEB_BASE = "https://www.bilibili.com/audio/music-service-c/web"
AUDIO_API_BASE = "https://api.bilibili.com/audio/music-service-c"
TOPLIST_API_BASE = "https://api.bilibili.com/x/copyright-music-publicity/toplist"

QUALITY_MAP = {
    0: "流畅 128K",
    1: "标准 192K",
    2: "高品质 320K",
    3: "无损 FLAC（大会员）",
}

# 音质标识映射（返回数据中的type字段）
QUALITY_TYPE_MAP = {
    -1: "试听片段（192K）",
    0: "128K",
    1: "192K",
    2: "320K",
    3: "FLAC",
}

MEMBER_TYPE_MAP = {
    1: "歌手",
    2: "作词",
    3: "作曲",
    4: "编曲",
    5: "后期/混音",
    7: "封面制作",
    8: "音源",
    9: "调音",
    10: "演奏",
    11: "乐器",
    127: "UP主",
}

RANK_TYPE_MAP = {
    1: "热榜",
    2: "原创榜",
}

VIP_TYPE_MAP = {
    0: "无",
    1: "月会员",
    2: "年会员",
}


class AudioParser:
    """B站音频（歌曲）API封装"""

    def __init__(self, config=None, cookies=None, csrf_token=""):
        self.config = config
        self.cookies = cookies or {}
        self.csrf_token = csrf_token
        self.session = requests.Session()

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
        logger.info(f"音频API Cookie已更新，共{len(self.cookies)}个字段")

    def _get(self, url, params=None, timeout=15):
        """GET请求"""
        try:
            resp = self.session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            # 音频API的code字段：0为成功
            if data.get("code") != 0:
                error_msg = data.get("msg") or data.get("message") or "未知错误"
                logger.warning(f"音频API请求失败: {url} -> {error_msg}")
                return {"success": False, "error": error_msg, "code": data.get("code")}
            return {"success": True, "data": data.get("data")}
        except requests.exceptions.RequestException as e:
            logger.error(f"音频API网络错误: {url} -> {str(e)}")
            return {"success": False, "error": f"网络错误: {str(e)}"}
        except Exception as e:
            logger.error(f"音频API解析错误: {url} -> {str(e)}")
            return {"success": False, "error": f"解析错误: {str(e)}"}

    def _post(self, url, data=None, timeout=15):
        """POST请求（带CSRF）"""
        try:
            post_data = data or {}
            if self.csrf_token:
                post_data['csrf'] = self.csrf_token
                post_data['csrf_token'] = self.csrf_token
            resp = self.session.post(url, data=post_data, timeout=timeout)
            resp.raise_for_status()
            result = resp.json()
            if result.get("code") != 0:
                error_msg = result.get("msg") or result.get("message") or "未知错误"
                logger.warning(f"音频API POST失败: {url} -> {error_msg}")
                return {"success": False, "error": error_msg, "code": result.get("code")}
            return {"success": True, "data": result.get("data")}
        except requests.exceptions.RequestException as e:
            logger.error(f"音频API网络错误: {url} -> {str(e)}")
            return {"success": False, "error": f"网络错误: {str(e)}"}
        except Exception as e:
            logger.error(f"音频API解析错误: {url} -> {str(e)}")
            return {"success": False, "error": f"解析错误: {str(e)}"}

    @staticmethod
    def parse_auid(raw):
        """从输入中提取音频auid（支持 au123、纯数字、完整URL）"""
        if not raw:
            return ""
        raw = str(raw).strip()
        # au123
        import re
        m = re.search(r'au(\d+)', raw, re.IGNORECASE)
        if m:
            return m.group(1)
        # 完整URL中的sid参数
        m = re.search(r'[?&]sid=(\d+)', raw)
        if m:
            return m.group(1)
        # audio/数字
        m = re.search(r'audio/(\d+)', raw)
        if m:
            return m.group(1)
        # 纯数字
        if raw.isdigit():
            return raw
        return ""

    # ==================== 歌曲信息 ====================

    def get_song_info(self, sid):
        """
        查询歌曲基本信息
        https://www.bilibili.com/audio/music-service-c/web/song/info
        :param sid: 音频auid
        """
        url = f"{AUDIO_WEB_BASE}/song/info"
        result = self._get(url, {"sid": sid})
        if not result["success"]:
            return result
        d = result["data"] or {}
        statistic = d.get("statistic", {}) or {}
        vip_info = d.get("vipInfo", {}) or {}
        return {
            "success": True,
            "data": {
                "id": d.get("id"),
                "uid": d.get("uid"),
                "uname": d.get("uname", ""),
                "author": d.get("author", ""),
                "title": d.get("title", ""),
                "cover": d.get("cover", ""),
                "intro": d.get("intro", ""),
                "lyric": d.get("lyric", ""),
                "duration": d.get("duration", 0),
                "passtime": d.get("passtime", 0),
                "curtime": d.get("curtime", 0),
                "aid": d.get("aid", 0),
                "bvid": d.get("bvid", ""),
                "cid": d.get("cid", 0),
                "coin_num": d.get("coin_num", 0),
                "statistic": {
                    "play": statistic.get("play", 0),
                    "collect": statistic.get("collect", 0),
                    "comment": statistic.get("comment", 0),
                    "share": statistic.get("share", 0),
                },
                "vip_info": {
                    "type": vip_info.get("type", 0),
                    "type_name": VIP_TYPE_MAP.get(vip_info.get("type", 0), "未知"),
                    "status": vip_info.get("status", 0),
                    "due_date": vip_info.get("due_date", 0),
                },
            },
        }

    def get_song_tags(self, sid):
        """
        查询歌曲TAG
        https://www.bilibili.com/audio/music-service-c/web/tag/song
        """
        url = f"{AUDIO_WEB_BASE}/tag/song"
        result = self._get(url, {"sid": sid})
        if not result["success"]:
            return result
        tags = []
        for item in (result["data"] or []):
            if isinstance(item, dict):
                tags.append(item.get("info", ""))
            else:
                tags.append(str(item))
        return {"success": True, "data": tags}

    def get_song_members(self, sid):
        """
        查询歌曲创作成员列表
        https://www.bilibili.com/audio/music-service-c/web/member/song
        """
        url = f"{AUDIO_WEB_BASE}/member/song"
        result = self._get(url, {"sid": sid})
        if not result["success"]:
            return result
        members = []
        for group in (result["data"] or []):
            if not isinstance(group, dict):
                continue
            type_code = group.get("type", 0)
            type_name = MEMBER_TYPE_MAP.get(type_code, f"类型{type_code}")
            names = [m.get("name", "") for m in (group.get("list", []) or []) if isinstance(m, dict)]
            if names:
                members.append({
                    "type": type_code,
                    "type_name": type_name,
                    "names": names,
                })
        return {"success": True, "data": members}

    def get_song_lyric(self, sid):
        """
        获取歌曲歌词（lrc格式）
        https://www.bilibili.com/audio/music-service-c/web/song/lyric
        """
        url = f"{AUDIO_WEB_BASE}/song/lyric"
        result = self._get(url, {"sid": sid})
        if not result["success"]:
            return result
        # data为字符串或null
        lyric = result["data"] or ""
        return {"success": True, "data": lyric}

    def get_stream_url_web(self, sid, quality=2, privilege=2):
        """
        获取音频流URL（web端，仅192K，付费歌曲为30s试听片段）
        https://www.bilibili.com/audio/music-service-c/web/url
        :param sid: 音频auid
        :param quality: 固定2
        :param privilege: 固定2
        """
        url = f"{AUDIO_WEB_BASE}/url"
        params = {"sid": sid, "quality": quality, "privilege": privilege}
        result = self._get(url, params)
        if not result["success"]:
            return result
        d = result["data"] or {}
        return {
            "success": True,
            "data": {
                "sid": d.get("sid"),
                "type": d.get("type", 0),
                "type_name": QUALITY_TYPE_MAP.get(d.get("type", 0), "未知"),
                "timeout": d.get("timeout", 0),
                "size": d.get("size", 0),
                "cdns": d.get("cdns", []) or [],
                "title": d.get("title", ""),
                "cover": d.get("cover", ""),
                "is_trial": d.get("type", 0) == -1,
            },
        }

    def get_stream_url_full(self, songid, quality=2, privilege=2, mid=0, platform="web"):
        """
        获取音频流URL（可获取付费音频，需登录的大会员账号）
        https://api.bilibili.com/audio/music-service-c/url
        :param songid: 音频auid
        :param quality: 0/1/2/3
        :param privilege: 必须为2
        :param mid: 当前用户mid（可为任意值）
        :param platform: 平台标识
        """
        url = f"{AUDIO_API_BASE}/url"
        params = {
            "songid": songid,
            "quality": quality,
            "privilege": privilege,
            "mid": mid,
            "platform": platform,
        }
        result = self._get(url, params)
        if not result["success"]:
            return result
        d = result["data"] or {}
        qualities = []
        for q in (d.get("qualities") or []):
            if isinstance(q, dict):
                qualities.append({
                    "type": q.get("type", 0),
                    "type_name": QUALITY_TYPE_MAP.get(q.get("type", 0), "未知"),
                    "desc": q.get("desc", ""),
                    "size": q.get("size", 0),
                    "bps": q.get("bps", ""),
                    "tag": q.get("tag", ""),
                    "require": q.get("require", 0),
                    "requiredesc": q.get("requiredesc", ""),
                })
        return {
            "success": True,
            "data": {
                "sid": d.get("sid"),
                "type": d.get("type", 0),
                "type_name": QUALITY_TYPE_MAP.get(d.get("type", 0), "未知"),
                "timeout": d.get("timeout", 0),
                "size": d.get("size", 0),
                "cdns": d.get("cdns", []) or [],
                "title": d.get("title", ""),
                "cover": d.get("cover", ""),
                "qualities": qualities,
                "is_trial": d.get("type", 0) == -1,
            },
        }

    # ==================== 收藏 & 投币 ====================

    def get_collect_status(self, sid):
        """
        查询音频收藏状态（需登录）
        https://www.bilibili.com/audio/music-service-c/web/collections/songs-coll
        """
        url = f"{AUDIO_WEB_BASE}/collections/songs-coll"
        result = self._get(url, {"sid": sid})
        if not result["success"]:
            return result
        return {"success": True, "data": bool(result["data"])}

    def get_coin_num(self, sid):
        """
        查询音频投币数（0为未投币，上限为2，需登录）
        https://www.bilibili.com/audio/music-service-c/web/coin/audio
        """
        url = f"{AUDIO_WEB_BASE}/coin/audio"
        result = self._get(url, {"sid": sid})
        if not result["success"]:
            return result
        return {"success": True, "data": result["data"] or 0}

    def add_coin(self, sid, multiply=1):
        """
        投币音频（需登录）
        https://www.bilibili.com/audio/music-service-c/web/coin/add
        :param sid: 音频auid
        :param multiply: 投币数量（最大为2）
        """
        url = f"{AUDIO_WEB_BASE}/coin/add"
        post_data = {"sid": sid, "multiply": multiply}
        return self._post(url, post_data)

    # ==================== 音频榜单 ====================

    def get_rank_periods(self, list_type=1):
        """
        获取音频榜单每期列表
        https://api.bilibili.com/x/copyright-music-publicity/toplist/all_period
        :param list_type: 1=热榜 2=原创榜
        :return: {年份: [{ID, priod, publish_time}, ...]}
        """
        url = f"{TOPLIST_API_BASE}/all_period"
        params = {"list_type": list_type}
        if self.csrf_token:
            params["csrf"] = self.csrf_token
        result = self._get(url, params)
        if not result["success"]:
            return result
        raw_list = (result["data"] or {}).get("list", {}) or {}
        # 转换为按年份组织的列表
        periods = {}
        for year, arr in raw_list.items():
            periods[year] = [
                {
                    "id": item.get("ID"),
                    "period": item.get("priod"),
                    "publish_time": item.get("publish_time", 0),
                }
                for item in (arr or []) if isinstance(item, dict)
            ]
        return {"success": True, "data": periods}

    def get_rank_detail(self, list_id):
        """
        查询音频榜单单期信息
        https://api.bilibili.com/x/copyright-music-publicity/toplist/detail
        """
        url = f"{TOPLIST_API_BASE}/detail"
        params = {"list_id": list_id}
        if self.csrf_token:
            params["csrf"] = self.csrf_token
        result = self._get(url, params)
        if not result["success"]:
            return result
        d = result["data"] or {}
        return {
            "success": True,
            "data": {
                "listen_fid": d.get("listen_fid", 0),
                "all_fid": d.get("all_fid", 0),
                "fav_mid": d.get("fav_mid", 0),
                "cover_url": d.get("cover_url", ""),
                "is_subscribe": d.get("is_subscribe", False),
                "listen_count": d.get("listen_count", 0),
            },
        }

    def get_rank_music_list(self, list_id):
        """
        获取音频榜单单期内容
        https://api.bilibili.com/x/copyright-music-publicity/toplist/music_list
        """
        url = f"{TOPLIST_API_BASE}/music_list"
        params = {"list_id": list_id}
        if self.csrf_token:
            params["csrf"] = self.csrf_token
        result = self._get(url, params)
        if not result["success"]:
            return result
        raw_list = (result["data"] or {}).get("list", []) or []
        items = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            items.append({
                "music_id": item.get("music_id", ""),
                "music_title": item.get("music_title", ""),
                "singer": item.get("singer", ""),
                "album": item.get("album", ""),
                "mv_aid": item.get("mv_aid", 0),
                "mv_bvid": item.get("mv_bvid", ""),
                "mv_cover": item.get("mv_cover", ""),
                "heat": item.get("heat", 0),
                "rank": item.get("rank", 0),
                "can_listen": item.get("can_listen", False),
                "creation_aid": item.get("creation_aid", 0),
                "creation_bvid": item.get("creation_bvid", ""),
                "creation_title": item.get("creation_title", ""),
                "creation_nickname": item.get("creation_nickname", ""),
                "creation_duration": item.get("creation_duration", 0),
                "creation_play": item.get("creation_play", 0),
                "achievements": item.get("achievements", []) or [],
            })
        return {"success": True, "data": items}

    # ==================== 下载音频流 ====================

    def download_stream(self, stream_url, output_path, progress_callback=None,
                        cancel_check=None, referer="https://www.bilibili.com/"):
        """
        下载音频流到文件
        音频流URL要求：User-Agent不为空且不含敏感字串，Referer必须在.bilibili.com下
        :param stream_url: 音频流URL
        :param output_path: 输出文件路径
        :param progress_callback: 回调 (downloaded, total, speed_bytes_per_sec)
        :param cancel_check: 取消检查函数，返回True则停止下载
        :return: dict {success, path, error}
        """
        import time as _time
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': referer,
                'Accept': '*/*',
                'Range': 'bytes=0-',
            }
            resp = self.session.get(stream_url, stream=True, timeout=30, headers=headers)
            resp.raise_for_status()

            total = int(resp.headers.get('content-length', 0))
            # 如果是分块响应，尝试从Content-Range获取总大小
            if total == 0 and resp.headers.get('content-range'):
                try:
                    total = int(resp.headers['content-range'].split('/')[-1])
                except Exception:
                    pass

            downloaded = 0
            start_time = _time.time()
            chunk_size = 1024 * 256  # 256KB
            with open(output_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if cancel_check and cancel_check():
                        f.close()
                        try:
                            import os as _os
                            _os.remove(output_path)
                        except Exception:
                            pass
                        return {"success": False, "error": "下载已取消"}
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = _time.time() - start_time + 0.001
                        speed = downloaded / elapsed
                        if progress_callback:
                            progress_callback(downloaded, total, speed)

            if cancel_check and cancel_check():
                return {"success": False, "error": "下载已取消"}

            return {"success": True, "path": output_path,
                    "size": downloaded, "total": total}
        except Exception as e:
            logger.error(f"下载音频流失败: {str(e)}")
            return {"success": False, "error": f"下载失败: {str(e)}"}
