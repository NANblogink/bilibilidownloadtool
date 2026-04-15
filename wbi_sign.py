#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import hmac
import hashlib
import logging
from functools import reduce
import urllib.parse

logger = logging.getLogger(__name__)

class WbiSign:
    def __init__(self):
        self.wbi_img_key = ""
        self.wbi_sub_key = ""
        self.wbi_update_time = 0
        
        self.MIXIN_KEY_ENC_TAB = [
            46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
            33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
            61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
            36, 20, 34, 44, 52
        ]
    
    def _get_mixin_key(self, orig):
        if len(orig) < 64:
            orig = orig.ljust(64, '0')
        return reduce(lambda s, i: s + orig[i], self.MIXIN_KEY_ENC_TAB, '')[:32]
    
    def _generate_wbi_sign(self, params):
        if not self.wbi_img_key or not self.wbi_sub_key:
            logger.warning("WBI 密钥未设置，使用默认值")
            self.wbi_img_key = "img_key"
            self.wbi_sub_key = "sub_key"
        
        mixin_key = self._get_mixin_key(self.wbi_img_key + self.wbi_sub_key)
        curr_time = int(time.time())
        params['wts'] = curr_time
        params = dict(sorted(params.items()))
        
        params = {
            k: ''.join(filter(lambda chr: chr not in "!'()*", str(v)))
            for k, v in params.items()
        }
        
        query = urllib.parse.urlencode(params)
        wbi_sign = hashlib.md5((query + mixin_key).encode()).hexdigest()
        params['w_rid'] = wbi_sign
        
        logger.debug(f"生成 Wbi 签名：wts={curr_time}, w_rid={wbi_sign}")
        return params
    
    def set_wbi_keys(self, img_key, sub_key):
        self.wbi_img_key = img_key
        self.wbi_sub_key = sub_key
        self.wbi_update_time = time.time()
        logger.info(f"设置 WBI 密钥成功：img_key={img_key}, sub_key={sub_key}")
    
    def get_wbi_keys(self):
        return self.wbi_img_key, self.wbi_sub_key
