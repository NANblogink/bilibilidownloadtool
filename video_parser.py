#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频解析模块
"""

import re
import logging
from wbi_sign import WbiSign

logger = logging.getLogger(__name__)

class VideoParser:
    def __init__(self):
        self.wbi_sign = WbiSign()
    
    def parse_media_url(self, url):
        logger.info(f"开始解析链接: {url}")

        # 检查 UP 主主页 URL
        space_match = re.search(r'space\.bilibili\.com/(\d+)', url, re.IGNORECASE)
        if space_match:
            mid = space_match.group(1)
            logger.info(f"解析成功: 类型=space, ID={mid}")
            return {"type": "space", "id": mid, "error": ""}

        if 'cheese' in url:
            cheese_match = re.search(r'cheese/play/ss(\d+)', url, re.IGNORECASE)
            if cheese_match:
                cheese_id = cheese_match.group(1)
                logger.info(f"解析成功: 类型=cheese, ID={cheese_id}")
                return {"type": "cheese", "id": cheese_id, "error": ""}

            cheese_ep_match = re.search(r'cheese/play/ep(\d+)', url, re.IGNORECASE)
            if cheese_ep_match:
                ep_id = cheese_ep_match.group(1)
                logger.info(f"解析成功: 类型=cheese, ID=ep{ep_id}")
                return {"type": "cheese", "id": f"ep{ep_id}", "error": ""}

        final_url = url
        try:
            import requests
            response = requests.get(url, allow_redirects=True, timeout=3)
            final_url = response.url
            logger.info(f"重定向后的链接: {final_url}")
        except Exception as e:
            logger.info(f"获取重定向链接失败: {str(e)}")

        # 检查重定向后的 UP 主主页 URL
        space_match = re.search(r'space\.bilibili\.com/(\d+)', final_url, re.IGNORECASE)
        if space_match:
            mid = space_match.group(1)
            logger.info(f"解析成功: 类型=space, ID={mid}")
            return {"type": "space", "id": mid, "error": ""}

        if 'cheese' in final_url:
            cheese_match = re.search(r'cheese/play/ss(\d+)', final_url, re.IGNORECASE)
            if cheese_match:
                cheese_id = cheese_match.group(1)
                logger.info(f"解析成功: 类型=cheese, ID={cheese_id}")
                return {"type": "cheese", "id": cheese_id, "error": ""}

            cheese_ep_match = re.search(r'cheese/play/ep(\d+)', final_url, re.IGNORECASE)
            if cheese_ep_match:
                ep_id = cheese_ep_match.group(1)
                logger.info(f"解析成功: 类型=cheese, ID=ep{ep_id}")
                return {"type": "cheese", "id": f"ep{ep_id}", "error": ""}

        av_match = re.search(r'av(\d+)', final_url, re.IGNORECASE)
        if av_match:
            av_id = av_match.group(1)
            logger.info(f"解析成功: 类型=av, ID={av_id}")
            return {"type": "av", "id": av_id, "error": ""}

        bv_match = re.search(r'(BV1[0-9A-Za-z]{9})', final_url)
        if bv_match:
            bvid = bv_match.group(1)

            if '充电' in final_url or 'sponsor' in final_url:
                logger.info(f"解析成功: 类型=sponsor, ID={bvid}")
                return {"type": "sponsor", "id": bvid, "error": ""}
            logger.info(f"解析成功: 类型=video, ID={bvid}")
            return {"type": "video", "id": bvid, "error": ""}

        ep_match = re.search(r'ep(\d+)', final_url, re.IGNORECASE)
        if ep_match:
            ep_id = ep_match.group(1)
            logger.info(f"解析成功: 类型=bangumi, ID=ep{ep_id}")
            return {"type": "bangumi", "id": f"ep{ep_id}", "error": ""}

        ss_match = re.search(r'ss(\d+)', final_url, re.IGNORECASE)
        if ss_match:
            ss_id = ss_match.group(1)
            logger.info(f"解析成功: 类型=bangumi, ID={ss_id}")
            return {"type": "bangumi", "id": ss_id, "error": ""}

        logger.info("解析失败: 无法解析链接类型")
        return {"type": "", "id": "", "error": "无法解析链接类型"}
    
    def av2bv(self, aid):
        XOR_CODE = 23442827791579
        MASK_CODE = 2251799813685247
        MAX_AID = 1 << 51
        ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
        ENCODE_MAP = 8, 7, 0, 5, 1, 3, 2, 4, 6
        DECODE_MAP = tuple(reversed(ENCODE_MAP))

        BASE = len(ALPHABET)
        PREFIX = "BV1"
        PREFIX_LEN = len(PREFIX)
        CODE_LEN = len(ENCODE_MAP)

        if isinstance(aid, str):
            aid = int(aid)

        bvid = [""] * 9
        tmp = (MAX_AID | aid) ^ XOR_CODE
        for i in range(CODE_LEN):
            bvid[ENCODE_MAP[i]] = ALPHABET[tmp % BASE]
            tmp //= BASE
        return PREFIX + "".join(bvid)

    def bv2av(self, bvid):
        XOR_CODE = 23442827791579
        MASK_CODE = 2251799813685247
        MAX_AID = 1 << 51
        ALPHABET = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"
        ENCODE_MAP = 8, 7, 0, 5, 1, 3, 2, 4, 6
        DECODE_MAP = tuple(reversed(ENCODE_MAP))

        BASE = len(ALPHABET)
        PREFIX = "BV1"
        PREFIX_LEN = len(PREFIX)
        CODE_LEN = len(ENCODE_MAP)

        assert bvid[:3] == PREFIX

        bvid = bvid[3:]
        tmp = 0
        for i in range(CODE_LEN):
            idx = ALPHABET.index(bvid[DECODE_MAP[i]])
            tmp = tmp * BASE + idx
        return (tmp & MASK_CODE) ^ XOR_CODE
