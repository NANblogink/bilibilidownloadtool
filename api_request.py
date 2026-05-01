#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API请求模块
"""

import time
import logging
import requests
import asyncio
from wbi_sign import WbiSign

logger = logging.getLogger(__name__)

# 条件导入：优先使用orjson，失败则使用标准json模块
try:
    import orjson
    json = orjson
    logger.debug("使用orjson库进行JSON解析")
except ImportError:
    import json
    logger.debug("orjson库导入失败，使用标准json模块")

class ApiRequest:
    def __init__(self, session=None):
        # 如果没有提供session，创建一个新的requests.Session
        if session is None:
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com'
            })
        else:
            self.session = session
        self.wbi_sign = WbiSign()
        self.cookies = {}
    
    def _api_request(self, url, timeout=15, max_retries=3, use_wbi=False, params=None):
        try:
            if not url or not isinstance(url, str):
                return False, {"error": "无效的API请求地址"}
            
            for retry in range(max_retries):
                try:
                    if params:
                        import urllib.parse
                        url_parts = list(urllib.parse.urlparse(url))
                        query = dict(urllib.parse.parse_qsl(url_parts[4]))

                        for key, value in params.items():
                            if key not in query:
                                query[key] = value

                        if use_wbi:
                            signed_params = self.wbi_sign._generate_wbi_sign(query)
                            query = signed_params

                        url_parts[4] = urllib.parse.urlencode(query)
                        url = urllib.parse.urlunparse(url_parts)
                    
                    logger.debug(f"发送API请求: {url}")
                    
                    if 'Referer' not in self.session.headers:
                        self.session.headers.update({'Referer': 'https://www.bilibili.com'})
                    logger.debug(f"请求头: {dict(self.session.headers)}")
                    
                    resp = self.session.get(url, timeout=timeout, allow_redirects=True)
                    
                    if resp.status_code != 200:
                        logger.debug(f"API请求失败，状态码: {resp.status_code}, URL: {url}")
                        logger.debug(f"响应内容: {resp.text}")
                        logger.debug(f"响应头: {dict(resp.headers)}")
                        return False, {"error": f"请求错误（code={resp.status_code}，msg={resp.text}）"}
                    
                    content = resp.text.strip()
                    
                    if content.startswith('!'):
                        start_index = content.find('{')
                        if start_index != -1:
                            content = content[start_index:]
                    
                    try:
                        data = json.loads(content)
                        
                        code = data.get('code', 0)
                        if code != 0:
                            
                            try:
                                from error_codes import ERROR_CODES
                                if code in ERROR_CODES:
                                    error_message = ERROR_CODES[code]
                                else:
                                    error_message = data.get('message', '未知错误')
                            except ImportError:
                                error_message = data.get('message', '未知错误')
                            
                            if code == -403 or code == 403:
                                return False, {"error": "访问权限不足"}
                            
                            elif code == -352:
                                logger.warning(f"风控校验失败：{error_message}")
                                
                                if retry < max_retries - 1:
                                    continue
                            return False, {"error": f"API返回错误：{error_message}（code={code}）"}
                        return True, data
                    except Exception:
                        
                        if resp.status_code == 403:
                            return False, {"error": "访问权限不足"}
                        
                        if "访问权限不足" in content:
                            return False, {"error": "访问权限不足"}
                        
                        if not content:
                            return False, {"error": "访问权限不足"}
                        
                        try:
                            resp.raise_for_status()
                        except Exception as e:
                            logger.debug(f"响应异常: {str(e)}")
                        
                        return False, {"error": "API返回的不是JSON格式数据"}
                except requests.exceptions.Timeout:
                    if retry < max_retries - 1:
                        import time
                        time.sleep(1 + retry)  
                        continue
                    return False, {"error": "API请求超时，请检查网络连接"}
                except requests.exceptions.RequestException as e:
                    error_msg = str(e)
                    if retry < max_retries - 1:
                        import time
                        time.sleep(1 + retry)  
                        continue
                    if "ProxyError" in error_msg:
                        return False, {"error": "代理错误，请检查网络设置"}
                    elif "ConnectionError" in error_msg:
                        return False, {"error": "连接错误，请检查网络连接"}
                    else:
                        return False, {"error": f"网络请求失败：{error_msg}"}
                except Exception as e:
                    if retry < max_retries - 1:
                        import time
                        time.sleep(1 + retry)  
                        continue
                    return False, {"error": f"API请求发生未知错误：{str(e)}"}
        except Exception as e:
            return False, {"error": f"API请求发生未知错误：{str(e)}"}
    
    async def _async_api_request(self, url, timeout=15, max_retries=3, use_wbi=False, params=None):
        try:
            if not url or not isinstance(url, str):
                return False, {"error": "无效的API请求地址"}
            
            for retry in range(max_retries):
                try:
                    if params:
                        import urllib.parse
                        url_parts = list(urllib.parse.urlparse(url))
                        query = dict(urllib.parse.parse_qsl(url_parts[4]))

                        for key, value in params.items():
                            if key not in query:
                                query[key] = value

                        if use_wbi:
                            signed_params = self.wbi_sign._generate_wbi_sign(query)
                            query = signed_params

                        url_parts[4] = urllib.parse.urlencode(query)
                        url = urllib.parse.urlunparse(url_parts)
                    
                    logger.debug(f"发送异步API请求: {url}")
                    
                    def sync_request():
                        if 'Referer' not in self.session.headers:
                            self.session.headers.update({'Referer': 'https://www.bilibili.com'})
                        return self.session.get(url, timeout=timeout, allow_redirects=True)
                    
                    loop = asyncio.get_event_loop()
                    resp = await loop.run_in_executor(None, sync_request)
                    
                    if resp.status_code != 200:
                        logger.debug(f"API请求失败，状态码: {resp.status_code}, URL: {url}")
                        logger.debug(f"响应内容: {resp.text}")
                        return False, {"error": f"请求错误（code={resp.status_code}，msg={resp.text}）"}
                    
                    content = resp.text.strip()
                    
                    if content.startswith('!'):
                        start_index = content.find('{')
                        if start_index != -1:
                            content = content[start_index:]
                    
                    try:
                        data = json.loads(content)
                        
                        code = data.get('code', 0)
                        if code != 0:
                            try:
                                from error_codes import ERROR_CODES
                                if code in ERROR_CODES:
                                    error_message = ERROR_CODES[code]
                                else:
                                    error_message = data.get('message', '未知错误')
                            except ImportError:
                                error_message = data.get('message', '未知错误')
                            
                            if code == -403 or code == 403:
                                return False, {"error": "访问权限不足"}
                            
                            elif code == -352:
                                logger.warning(f"风控校验失败：{error_message}")
                                if retry < max_retries - 1:
                                    continue
                            return False, {"error": f"API返回错误：{error_message}（code={code}）"}
                        return True, data
                    except Exception:
                        if resp.status_code == 403:
                            return False, {"error": "访问权限不足"}
                        
                        if "访问权限不足" in content:
                            return False, {"error": "访问权限不足"}
                        
                        if not content:
                            return False, {"error": "访问权限不足"}
                        
                        try:
                            resp.raise_for_status()
                        except Exception as e:
                            logger.debug(f"响应异常: {str(e)}")
                        
                        return False, {"error": "API返回的不是JSON格式数据"}
                except requests.exceptions.Timeout:
                    if retry < max_retries - 1:
                        import time
                        await asyncio.sleep(1 + retry)  
                        continue
                    return False, {"error": "API请求超时，请检查网络连接"}
                except requests.exceptions.RequestException as e:
                    error_msg = str(e)
                    if retry < max_retries - 1:
                        import time
                        await asyncio.sleep(1 + retry)  
                        continue
                    if "ProxyError" in error_msg:
                        return False, {"error": "代理错误，请检查网络设置"}
                    elif "ConnectionError" in error_msg:
                        return False, {"error": "连接错误，请检查网络连接"}
                    else:
                        return False, {"error": f"网络请求失败：{error_msg}"}
                except Exception as e:
                    if retry < max_retries - 1:
                        import time
                        await asyncio.sleep(1 + retry)  
                        continue
                    return False, {"error": f"API请求发生未知错误：{str(e)}"}
        except Exception as e:
            return False, {"error": f"API请求发生未知错误：{str(e)}"}
    
    def set_wbi_keys(self, img_key, sub_key):
        self.wbi_sign.set_wbi_keys(img_key, sub_key)
    
    def get_wbi_keys(self):
        return self.wbi_sign.get_wbi_keys()
    
    def close(self):
        if hasattr(self.session, 'close'):
            self.session.close()
