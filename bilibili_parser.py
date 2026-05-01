import os
import re
import json
import time
import shutil
import subprocess
import logging
import random
import base64
import asyncio
import hashlib
import hmac
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
import logging
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA1
from wbi_sign import WbiSign
from api_request import ApiRequest
from video_parser import VideoParser
import requests

# 导入工具管理器
try:
    from tool_manager import get_tool_manager
except ImportError:
    get_tool_manager = None

logger = logging.getLogger(__name__)

# 条件导入：优先使用orjson进行字符串解析，始终使用标准json进行文件操作
import json as std_json
try:
    import orjson
    json = orjson
    logger.debug("使用orjson库进行JSON解析")
except ImportError:
    import json
    logger.debug("orjson库导入失败，使用标准json模块")

# 预编译正则表达式
KID_REGEX = {
    'bilidrm_uri': re.compile(r'uri:bili://([0-9a-f]{32})', re.IGNORECASE),
    'url_param': re.compile(r'kid=([0-9a-fA-F]{32})')
}

# KID缓存
KID_CACHE = {}
KID_CACHE_EXPIRY = 3600  # 1小时

class SimpleBiliDRM:
    def __init__(self):
        self._key = self.generate_random_bytes(16)
        self._iv = self.generate_random_bytes(16)
        self._public_key = None
        self.session = None
        
        self.api_url = "http://bvc-drm.bilivideo.com/bilidrm"
        self.pub_key_url = "http://bvc-drm.bilivideo.com/cer/bilidrm_pub.key"

    async def __aenter__(self):
        # 使用aiohttp的异步客户端
        import aiohttp
        self.session = aiohttp.ClientSession(headers={
            'origin': 'https://www.bilibili.com',
            'referer': 'https://www.bilibili.com/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Content-Type': 'application/json'
        })
        self._public_key = await self.get_public_key()
        return self

    async def __aexit__(self, *args):
        await self.session.close()

    @staticmethod
    def generate_random_bytes(length):
        return bytes(random.randint(0, 255) for _ in range(length))

    async def get_public_key(self):
        async with self.session.get(self.pub_key_url) as resp:
            public_key = await resp.read()
            return public_key

    def encrypt_kid(self, kid):
        aes_ecb = AES.new(self._key, AES.MODE_ECB)
        enc_kid = aes_ecb.encrypt(kid[:16])
        
        salt = bytes([0x1b, 0xf7, 0xf5, 0x3f, 0x5d, 0x5d, 0x5a, 0x1f, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x20])
        kid_bytes = salt + enc_kid + kid[16:]
        
        aes_cbc = AES.new(self._key, AES.MODE_CBC, self._iv)
        encrypted_kid = aes_cbc.encrypt(kid_bytes)
        return encrypted_kid

    def encrypt_key(self):
        public_key = RSA.import_key(self._public_key)
        cipher_rsa = PKCS1_OAEP.new(public_key, hashAlgo=SHA1)
        encrypted = cipher_rsa.encrypt(self._key)
        return encrypted

    def encrypt_spc(self, kid):
        content_key_ctx = self.encrypt_kid(kid)
        sha_digest = hashlib.sha1(self._public_key).digest()
        
        timestamp = int(asyncio.get_event_loop().time())
        
        spc_data = (
            b'bilibili' +
            bytes([0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]) +
            timestamp.to_bytes(4, 'big') +
            self._iv +
            self.encrypt_key() +
            sha_digest +
            len(content_key_ctx).to_bytes(4, 'big') +
            content_key_ctx
        )
        
        spc_b64 = base64.b64encode(spc_data).decode()
        return spc_b64

    async def get_key(self, kid):
        if isinstance(kid, str):
            kid_bytes = kid.encode()
        else:
            kid_bytes = kid
        
        if len(kid_bytes) != 32:
            kid_bytes = kid_bytes[:32] if len(kid_bytes) > 32 else kid_bytes.ljust(32, b'\x00')
        
        spc = self.encrypt_spc(kid_bytes)
        
        payload = {"spc": spc}
        
        try:
            async with self.session.post(self.api_url, json=payload) as resp:
                response_text = await resp.text()
                logger.debug(f"DRM API响应: {response_text}")
                
                if resp.status != 200:
                    logger.error(f"DRM API请求失败，状态码: {resp.status}")
                    raise Exception(f"DRM API请求失败，状态码: {resp.status}")
                
                try:
                    response = json.loads(response_text)
                except Exception as e:
                    logger.error(f"解析DRM API响应失败: {str(e)}")
                    raise Exception(f"解析DRM API响应失败: {str(e)}")
            
            ckc = response.get("ckc")
            if not ckc:
                logger.error(f"响应中未找到ckc字段，响应内容: {response}")
                # 尝试使用不同的字段名
                ckc = response.get("data", {}).get("ckc")
                if not ckc:
                    raise Exception(f"响应中未找到ckc字段，响应: {response}")
            
            ckc_bytes = base64.b64decode(ckc)
            
            offset = 12
            time_bytes = ckc_bytes[offset:offset+4]
            offset += 4
            iv = ckc_bytes[offset:offset+16]
            offset += 16
            data_len_bytes = ckc_bytes[offset:offset+4]
            data_len = int.from_bytes(data_len_bytes, 'big')
            offset += 4
            data = ckc_bytes[offset:offset+data_len]
            
            aes_cbc = AES.new(self._key, AES.MODE_CBC, iv)
            decrypted = aes_cbc.decrypt(data)
            
            aes_ecb = AES.new(self._key, AES.MODE_ECB)
            final_key = aes_ecb.decrypt(decrypted[-16:])
            
            result_key = final_key.hex()
            logger.info(f"成功获取DRM密钥: {result_key}")
            return result_key
        except Exception as e:
            logger.error(f"获取DRM密钥失败: {str(e)}")
            raise


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None



from error_codes import ERROR_CODES


requests.packages.urllib3.disable_warnings()

class BilibiliParser:
    def __init__(self, config, cookie_path="cookie.txt"):
        self.config = config
        self.cookies = {}
        self.csrf_token = ""
        self.session = requests.Session()
        self.user_info = None
        self.hevc_supported = False
        
        # 初始化模块
        self.wbi_sign = WbiSign()
        self.api_request = ApiRequest(self.session)
        self.video_parser = VideoParser()

        import sys
        if hasattr(sys, '_MEIPASS'):
            self.current_dir = sys._MEIPASS
        else:
            self.current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 设置cookie路径
        if hasattr(sys, '_MEIPASS'):
            self.cookie_path = os.path.join(os.getcwd(), cookie_path)
        else:
            self.cookie_path = os.path.join(self.current_dir, cookie_path)
        
        # 尝试使用工具管理器
        self.tool_manager = None
        self.using_system_tools = False
        if get_tool_manager is not None:
            try:
                self.tool_manager = get_tool_manager()
                # 检查工具是否已安装
                tool_status = self.tool_manager.check_tools_installed()
                if tool_status['ffmpeg_exists'] and tool_status['bento4_exists']:
                    # 使用已安装的工具
                    self.ffmpeg_local = tool_status['ffmpeg_path']
                    self.bento4_dir = tool_status['bento4_path'].replace(os.sep + 'mp4decrypt.exe', '')
                    self.using_system_tools = True
                    logger.info(f"使用已安装的工具: FFmpeg={self.ffmpeg_local}, Bento4={self.bento4_dir}")
                else:
                    # 工具未安装，使用旧逻辑
                    self._setup_old_paths()
            except Exception as e:
                logger.warning(f"工具管理器初始化失败: {str(e)}, 使用旧逻辑")
                self._setup_old_paths()
        else:
            # 工具管理器不可用，使用旧逻辑
            self._setup_old_paths()
        
        self._init_session()
    
    def _setup_old_paths(self):
        """使用旧的路径设置逻辑"""
        import sys
        if hasattr(sys, '_MEIPASS'):
            self.bento4_dir = os.path.join(self.current_dir, 'bento4', 'bin')
        else:
            self.bento4_dir = os.path.join(self.current_dir, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin')
        
        self.ffmpeg_local = os.path.join(self.current_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')
        
        # 检查工具是否存在，并尝试多个可能的路径
        self._check_and_fix_paths()
    
    def _check_and_fix_paths(self):
        """检查必要工具是否存在，尝试多个可能的路径"""
        import sys
        
        # 可能的bento4路径列表
        possible_bento4_paths = []
        if hasattr(sys, '_MEIPASS'):
            possible_bento4_paths.append(os.path.join(sys._MEIPASS, 'bento4', 'bin'))
            possible_bento4_paths.append(os.path.join(sys._MEIPASS, 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin'))
            possible_bento4_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', 'bin'))
            possible_bento4_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin'))
            possible_bento4_paths.append(os.path.join(os.getcwd(), 'bento4', 'bin'))
            possible_bento4_paths.append(os.path.join(os.getcwd(), 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin'))
        else:
            possible_bento4_paths.append(self.bento4_dir)
            possible_bento4_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', 'bin'))
            possible_bento4_paths.append(os.path.join(os.getcwd(), 'bento4', 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32', 'bin'))
            possible_bento4_paths.append(os.path.join(os.getcwd(), 'bento4', 'bin'))
        
        # 寻找包含mp4decrypt.exe的路径
        found_bento4 = False
        for path in possible_bento4_paths:
            test_path = os.path.join(path, 'mp4decrypt.exe')
            if os.path.exists(test_path):
                self.bento4_dir = path
                found_bento4 = True
                logger.info(f"找到Bento4工具：{path}")
                break
        
        if not found_bento4:
            logger.warning("未找到Bento4工具，解密功能可能无法正常工作")
        
        # 可能的ffmpeg路径列表
        possible_ffmpeg_paths = []
        if hasattr(sys, '_MEIPASS'):
            possible_ffmpeg_paths.append(os.path.join(sys._MEIPASS, 'ffmpeg', 'bin', 'ffmpeg.exe'))
            possible_ffmpeg_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe'))
            possible_ffmpeg_paths.append(os.path.join(os.getcwd(), 'ffmpeg', 'bin', 'ffmpeg.exe'))
        else:
            possible_ffmpeg_paths.append(self.ffmpeg_local)
            possible_ffmpeg_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', 'ffmpeg.exe'))
            possible_ffmpeg_paths.append(os.path.join(os.getcwd(), 'ffmpeg', 'bin', 'ffmpeg.exe'))
        
        # 寻找ffmpeg.exe
        found_ffmpeg = False
        for path in possible_ffmpeg_paths:
            if os.path.exists(path):
                self.ffmpeg_local = path
                found_ffmpeg = True
                logger.info(f"找到FFmpeg工具：{path}")
                break
        
        if not found_ffmpeg:
            logger.warning("未找到FFmpeg工具，视频处理功能可能无法正常工作")
    
    def check_tools_exist(self):
        """检查所有必要工具是否存在，返回状态字典"""
        status = {
            'ffmpeg': {
                'exists': os.path.exists(self.ffmpeg_local),
                'path': self.ffmpeg_local
            },
            'mp4decrypt': {
                'exists': os.path.exists(os.path.join(self.bento4_dir, 'mp4decrypt.exe')),
                'path': os.path.join(self.bento4_dir, 'mp4decrypt.exe')
            },
            'bento4_dir': {
                'exists': os.path.exists(self.bento4_dir),
                'path': self.bento4_dir
            }
        }
        return status

    def _init_session(self):
        import threading
        headers = self.config.get_headers()
        self.session.headers.clear()
        self.session.headers.update(headers)

        self.cookies = self._load_cookies()
        logger.info(f"从文件加载的cookie：{self.cookies}")
        self.session.cookies.update(self.cookies)
        logger.info(f"session cookie：{dict(self.session.cookies)}")
        self.csrf_token = self.cookies.get('bili_jct', '')

        if self.csrf_token:
            self.session.headers.update({'X-CSRF-Token': self.csrf_token})

        self.session.verify = False
        self.session.proxies = {}  # 强制禁用代理
        
        
        if self.cookies:
            def verify_cookie_in_thread():
                try:
                    success, msg = self.verify_cookie()
                    if not success:
                        logger.warning(f"Cookie有效性检查：{msg}")
                    else:
                        logger.debug(f"Cookie有效性检查：{msg}")
                except Exception as e:
                    logger.error(f"Cookie有效性检查失败：{str(e)}")
            
            thread = threading.Thread(target=verify_cookie_in_thread)
            thread.daemon = True
            thread.start()
        
        
        self._load_cached_wbi_keys()
        threading.Thread(target=self._update_wbi_keys).start()
    
    def _get_wbi_keys(self):
        try:
            url = "https://api.bilibili.com/x/web-interface/nav"
            success, data = self._api_request(url, timeout=10, use_wbi=False)
            if not success:
                logger.warning(f"获取 Wbi 密钥失败：{data['error']}，使用缓存密钥")
                # 即使获取失败，也返回True，使用缓存的密钥
                img_key, sub_key = self.wbi_sign.get_wbi_keys()
                return img_key and sub_key
            
            wbi_data = data.get('data', {}).get('wbi_img', {})
            img_url = wbi_data.get('img_url', '')
            sub_url = wbi_data.get('sub_url', '')
            
            if not img_url or not sub_url:
                logger.warning("获取 Wbi 密钥失败：未找到密钥信息，使用缓存密钥")
                # 即使获取失败，也返回True，使用缓存的密钥
                img_key, sub_key = self.wbi_sign.get_wbi_keys()
                return img_key and sub_key
            
            
            img_key = img_url.split('/')[-1].split('.')[0]
            sub_key = sub_url.split('/')[-1].split('.')[0]
            self.wbi_sign.set_wbi_keys(img_key, sub_key)
            logger.debug(f"获取 Wbi 密钥成功：img_key={img_key}, sub_key={sub_key}")
            self._save_wbi_keys()
            return True
        except Exception as e:
            logger.error(f"获取 Wbi 密钥失败：{str(e)}，使用缓存密钥")
            # 即使获取失败，也返回True，使用缓存的密钥
            img_key, sub_key = self.wbi_sign.get_wbi_keys()
            return img_key and sub_key
    
    def _load_cached_wbi_keys(self):
        try:
            cache_file = 'wbi_cache.json'
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = std_json.load(f)
                img_key = cache_data.get('wbi_img_key', '')
                sub_key = cache_data.get('wbi_sub_key', '')
                self.wbi_sign.set_wbi_keys(img_key, sub_key)
                logger.debug(f"从缓存加载Wbi密钥成功：img_key={img_key}, sub_key={sub_key}")
        except Exception as e:
            logger.error(f"加载Wbi缓存失败：{str(e)}")
    
    def _save_wbi_keys(self):
        try:
            cache_file = 'wbi_cache.json'
            img_key, sub_key = self.wbi_sign.get_wbi_keys()
            cache_data = {
                'wbi_img_key': img_key,
                'wbi_sub_key': sub_key,
                'wbi_update_time': time.time()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                std_json.dump(cache_data, f, ensure_ascii=False, indent=2)
            logger.debug("Wbi密钥保存到缓存成功")
        except Exception as e:
            logger.error(f"保存Wbi缓存失败：{str(e)}")
    
    def _update_wbi_keys(self):
        import threading
        
        def update_once():
            try:
                if time.time() - self.wbi_sign.wbi_update_time > 86400 or not self.wbi_sign.wbi_img_key:
                    if self._get_wbi_keys():
                        self._save_wbi_keys()
            except Exception as e:
                logger.error(f"更新Wbi密钥失败：{str(e)}")
        
        threading.Thread(target=update_once, daemon=True).start()
        
        while True:
            time.sleep(3600)
            threading.Thread(target=update_once, daemon=True).start()  
    
    def _generate_wbi_sign(self, params):
        return self.wbi_sign._generate_wbi_sign(params)
    
    def _generate_bili_ticket(self):
        try:
            
            timestamp = int(time.time())
            key = "XgwSnGZ1p"
            message = f"ts{timestamp}"
            hexsign = hmac.new(key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
            
            
            params = {
                "key_id": "ec02",
                "hexsign": hexsign,
                "context[ts]": timestamp
            }
            
            # 只有当csrf_token不为空时才添加csrf参数
            if self.csrf_token:
                params["csrf"] = self.csrf_token
            
            
            url = "https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json'
            }
            
            response = self.session.post(url, json=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                ticket = data.get('data', {}).get('ticket', '')
                if ticket:
                    logger.debug("生成 bili_ticket 成功")
                    
                    self.cookies['bili_ticket'] = ticket
                    self.session.cookies.update({'bili_ticket': ticket})
                    return ticket
            
            logger.error(f"生成 bili_ticket 失败：{data.get('message', '未知错误')}")
            return None
        except Exception as e:
            logger.error(f"生成 bili_ticket 失败：{str(e)}")
            return None
    
    def _get_v_voucher(self, url, params=None):
        try:
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json'
            }
            
            
            voucher_url = "https://api.bilibili.com/x/frontend/finger/spi"
            voucher_params = {
                "buvid3": self.cookies.get('buvid3', ''),
                "buvid4": self.cookies.get('buvid4', ''),
                "timestamp": int(time.time())
            }
            
            response = self.session.post(voucher_url, json=voucher_params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                v_voucher = data.get('data', {}).get('v_voucher', '')
                if v_voucher:
                    logger.debug("获取 v_voucher 成功")
                    
                    self.cookies['v_voucher'] = v_voucher
                    self.session.cookies.update({'v_voucher': v_voucher})
                    return v_voucher
            
            logger.error(f"获取 v_voucher 失败：{data.get('message', '未知错误')}")
            return None
        except Exception as e:
            logger.error(f"获取 v_voucher 失败：{str(e)}")
            return None

    def _load_cookies(self):
        cookies = {}

        if os.path.exists(self.cookie_path):
            try:
                with open(self.cookie_path, 'r', encoding='utf-8') as f:
                    cookie_data = std_json.load(f)

                if isinstance(cookie_data, list):
                    if len(cookie_data) > 0 and 'name' in cookie_data[0] and 'value' in cookie_data[0]:
                        for item in cookie_data:
                            cookies[item['name'].strip()] = item['value'].strip()
                    else:
                        for item in cookie_data:
                            if isinstance(item, dict) and 'name' in item and 'value' in item:
                                cookies[item['name'].strip()] = item['value'].strip()
                if cookies:
                    return cookies
            except Exception as e:
                print(f"本地Cookie加载失败：{str(e)}")

        return cookies


    def save_cookies(self, cookies):
        try:
            if isinstance(cookies, str):
                try:
                    cookies = json.loads(cookies.strip())
                except Exception:
                    cookies = self._parse_cookie_text(cookies)

            if isinstance(cookies, list) and len(cookies) > 0 and isinstance(cookies[0], dict):
                cookie_dict = {}
                for item in cookies:
                    if 'name' in item and 'value' in item:
                        cookie_dict[item['name'].strip()] = item['value'].strip()
                cookies = cookie_dict

            if not isinstance(cookies, dict):
                raise ValueError("Cookie格式不支持")

            cookie_list = [{'name': k, 'value': v} for k, v in cookies.items()]
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                std_json.dump(cookie_list, f, ensure_ascii=False, indent=2)

            self.cookies = cookies
            self.session.cookies.clear()
            self.session.cookies.update(cookies)
            self.csrf_token = cookies.get('bili_jct', '')
            if self.csrf_token:
                self.session.headers.update({'X-CSRF-Token': self.csrf_token})

            self.user_info = None
            return True
        except Exception as e:
            print(f"Cookie保存失败：{str(e)}")
            return False

    def _parse_cookie_text(self, cookie_text):
        cookie_dict = {}
        if not cookie_text.strip():
            return cookie_dict
        pairs = [pair.strip() for pair in cookie_text.split(';') if pair.strip()]
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                cookie_dict[key.strip()] = value.strip()
        return cookie_dict

    # API请求缓存
    _api_cache = {}
    _cache_expiry = 300  # 缓存有效期（秒）
    
    def _api_request(self, url, timeout=15, max_retries=3, use_wbi=False, params=None, use_cache=True):
        try:
            if not url or not isinstance(url, str):
                return False, {"error": "无效的API请求地址"}
            
            # 生成缓存键
            cache_key = self._generate_cache_key(url, params, use_wbi)
            
            # 检查缓存
            if use_cache:
                cached_data = self._get_cached_data(cache_key)
                if cached_data:
                    return True, cached_data
            
            for retry in range(max_retries):
                try:
                    # 构建URL
                    if params:
                        import urllib.parse
                        url_parts = list(urllib.parse.urlparse(url))
                        query = dict(urllib.parse.parse_qsl(url_parts[4]))

                        for key, value in params.items():
                            if key not in query:
                                query[key] = value

                        if use_wbi:
                            signed_params = self._generate_wbi_sign(query)
                            query = signed_params

                        url_parts[4] = urllib.parse.urlencode(query, safe='/:?=&')
                        url = urllib.parse.urlunparse(url_parts)

                    logger.debug(f"发送API请求: {url}")

                    # 确保会话已初始化
                    if not hasattr(self, 'session') or self.session is None:
                        self.session = requests.Session()
                        self.session.headers.update({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                            'Referer': 'https://www.bilibili.com',
                            'Accept': 'application/json, text/plain, */*'
                        })
                    elif 'Referer' not in self.session.headers:
                        self.session.headers.update({'Referer': 'https://www.bilibili.com'})
                    
                    # 发送请求
                    resp = self.session.get(url, timeout=timeout, proxies={}, allow_redirects=True, stream=False)

                    if resp.status_code != 200:
                        logger.debug(f"API请求失败，状态码: {resp.status_code}, URL: {url}")
                        logger.debug(f"响应内容: {resp.text[:200]}...")  # 限制日志长度
                        return False, {"error": f"请求错误（code={resp.status_code}）"}

                    content = resp.text.strip()
                    
                    # 处理特殊响应格式
                    if content.startswith('!'):
                        start_index = content.find('{')
                        if start_index != -1:
                            content = content[start_index:]
                    
                    try:
                        data = json.loads(content)
                        
                        code = data.get('code', 0)
                        if code != 0:
                            if code in ERROR_CODES:
                                error_message = ERROR_CODES[code]
                            else:
                                error_message = data.get('message', '未知错误')
                            
                            if code == -403 or code == 403:
                                return False, {"error": "访问权限不足"}
                            
                            elif code == -352:
                                logger.warning(f"风控校验失败：{error_message}")
                                self._generate_bili_ticket()
                                if 'v_voucher' not in self.cookies:
                                    self._get_v_voucher(url, params)
                                if retry < max_retries - 1:
                                    continue
                            return False, {"error": f"API返回错误：{error_message}（code={code}）"}
                        
                        # 缓存成功的响应
                        self._cache_api_response(cache_key, data)
                        return True, data
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON解析错误: {str(e)}")
                        if resp.status_code == 403:
                            return False, {"error": "访问权限不足"}
                        if "访问权限不足" in content:
                            return False, {"error": "访问权限不足"}
                        if not content:
                            return False, {"error": "访问权限不足"}
                        return False, {"error": "API返回的不是JSON格式数据"}
                except Exception as e:
                    error_msg = str(e)
                    if "Timeout" in error_msg:
                        if retry < max_retries - 1:
                            time.sleep(1 + retry * 0.5)  # 指数退避
                            continue
                        return False, {"error": "API请求超时，请检查网络连接"}
                    elif "RequestException" in error_msg:
                        if retry < max_retries - 1:
                            time.sleep(1 + retry * 0.5)
                            continue
                        if "ProxyError" in error_msg:
                            return False, {"error": "代理错误，请检查网络设置"}
                        elif "ConnectionError" in error_msg:
                            return False, {"error": "连接错误，请检查网络连接"}
                        else:
                            return False, {"error": f"网络请求失败：{error_msg}"}
                    else:
                        if retry < max_retries - 1:
                            time.sleep(1 + retry * 0.5)
                            continue
                        return False, {"error": f"API请求发生未知错误：{str(e)}"}
        except Exception as e:
            return False, {"error": f"API请求发生未知错误：{str(e)}"}
    
    def _generate_cache_key(self, url, params, use_wbi):
        import hashlib
        key_parts = [url]
        if params:
            sorted_params = sorted(params.items())
            key_parts.extend([f"{k}={v}" for k, v in sorted_params])
        if use_wbi:
            key_parts.append("wbi=True")
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
    
    def _get_cached_data(self, cache_key):
        if cache_key in self._api_cache:
            cached = self._api_cache[cache_key]
            if time.time() - cached['timestamp'] < self._cache_expiry:
                logger.debug(f"使用缓存的API响应: {cache_key}")
                return cached['data']
            else:
                del self._api_cache[cache_key]  # 缓存过期
        return None
    
    def _cache_api_response(self, cache_key, data):
        self._api_cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
        # 清理过期缓存
        self._clean_expired_cache()
    
    def _clean_expired_cache(self):
        current_time = time.time()
        expired_keys = [key for key, cached in self._api_cache.items() 
                      if current_time - cached['timestamp'] >= self._cache_expiry]
        for key in expired_keys:
            del self._api_cache[key]
        if expired_keys:
            logger.debug(f"清理了 {len(expired_keys)} 个过期缓存")

    def verify_cookie(self):
        if not self.cookies:
            return False, "未加载任何Cookie"

        required_cookies = ['SESSDATA']
        missing = [ck for ck in required_cookies if ck not in self.cookies]
        if missing:
            return False, f"缺少关键Cookie：{','.join(missing)}（登录必需）"

        api_url = self.config.get_api_url("login_status_api")
        if not api_url:
            return False, "配置错误：未找到用户信息API地址"

        # 调用_api_request时禁用缓存，确保每次都是最新的验证
        success, result = self._api_request(api_url, timeout=10, max_retries=1, use_cache=False)
        if not success:
            return False, f"API请求失败：{result['error']}"

        code = result.get('code', -1)
        if code != 0:
            msg = result.get('message', '未知错误')
            return False, f"API返回错误：{msg}（code={code}）"

        data = result.get('data', {})
        is_login = data.get('isLogin', False)
        if not is_login:
            return False, "Cookie失效或未登录"

        uname = data.get('uname', '未知用户')
        mid = data.get('mid', '未知ID')
        vip_status = data.get('vipStatus', 0)
        vip_text = "会员" if vip_status == 1 else "普通用户"
        return True, f"登录成功！用户：{uname}（ID：{mid}）| {vip_text}"

    def get_qrcode(self):
        try:
            url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
            import requests
            import logging
            import brotli
            logger = logging.getLogger(__name__)
            
            # 优化请求头，确保兼容性
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache'
            }
            
            # 使用会话对象，保持cookie一致性
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False
            session.proxies = {}  # 强制禁用代理
            
            logger.info(f"发送请求到：{url}")
            
            # 增加超时时间，确保网络较慢时也能获取二维码
            resp = session.get(url, timeout=15, proxies={}, allow_redirects=True)
            
            logger.info(f"获取二维码API响应状态码：{resp.status_code}")
            
            # 处理响应内容
            content = resp.text
            if not content or content.strip() == '':
                # 尝试使用content属性
                if resp.content:
                    try:
                        content = resp.content.decode('utf-8')
                    except:
                        pass
                if not content or content.strip() == '':
                    raise Exception("获取二维码失败：响应内容为空")
            
            if resp.status_code != 200:
                raise Exception(f"获取二维码失败：HTTP {resp.status_code}")
            
            # 解析JSON响应
            try:
                data = json.loads(content)
                logger.info(f"解析后的JSON数据：{data}")
            except json.JSONDecodeError as e:
                # 清理响应内容，处理可能的前缀
                content = content.strip()
                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]
                try:
                    data = json.loads(content)
                    logger.info(f"清理后解析的JSON数据：{data}")
                except json.JSONDecodeError as e:
                    raise Exception(f"获取二维码失败：JSON解析错误：{str(e)}")
            
            # 检查响应码
            code = data.get('code', 0)
            if code != 0:
                message = data.get('message', '未知错误')
                raise Exception(f"获取二维码失败：{message}（code={code}）")
            
            # 获取二维码信息
            qrcode_data = data.get('data', {})
            qrcode_url = qrcode_data.get('url', '')
            qrcode_key = qrcode_data.get('qrcode_key', '')
            
            if not qrcode_url or not qrcode_key:
                raise Exception("获取二维码信息失败")
            
            return {
                "success": True,
                "url": qrcode_url,
                "qrcode_key": qrcode_key
            }
        except ImportError as e:
            # 处理缺少brotli库的情况
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"缺少brotli库：{str(e)}")
            
            url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache'
            }
            
            try:
                session = requests.Session()
                session.headers.update(headers)
                session.verify = False
                session.proxies = {}  # 强制禁用代理
                
                resp = session.get(url, timeout=15, proxies={}, allow_redirects=True)
                
                if resp.status_code != 200:
                    raise Exception(f"获取二维码失败：HTTP {resp.status_code}")
                
                # 尝试不同的解析方式
                try:
                    data = resp.json()
                except json.JSONDecodeError:
                    # 尝试手动解析
                    content = resp.text.strip()
                    if content.startswith('!'):
                        start_index = content.find('{')
                        if start_index != -1:
                            content = content[start_index:]
                    data = json.loads(content)
                
                code = data.get('code', 0)
                if code != 0:
                    message = data.get('message', '未知错误')
                    raise Exception(f"获取二维码失败：{message}（code={code}）")
                
                qrcode_data = data.get('data', {})
                qrcode_url = qrcode_data.get('url', '')
                qrcode_key = qrcode_data.get('qrcode_key', '')
                
                if not qrcode_url or not qrcode_key:
                    raise Exception("获取二维码信息失败")
                
                return {
                    "success": True,
                    "url": qrcode_url,
                    "qrcode_key": qrcode_key
                }
            except Exception as e:
                logger.error(f"获取二维码失败：{str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        except Exception as e:
            import traceback
            logger.error(f"获取二维码失败：{str(e)}")
            logger.error(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }

    def poll_login_status(self, qrcode_key):
        try:
            url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}"
            import requests
            import logging
            import brotli
            logger = logging.getLogger(__name__)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            }
            
            
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False
            session.proxies = {}  # 强制禁用代理
            resp = session.get(url, timeout=10, proxies={}, allow_redirects=True)
            
            
            if resp.status_code != 200:
                raise Exception(f"轮询登录状态失败：HTTP {resp.status_code}")
            
            
            content_encoding = resp.headers.get('Content-Encoding', '')
            if 'br' in content_encoding:
                try:
                    
                    content = brotli.decompress(resp.content)
                    content = content.decode('utf-8')
                except Exception as e:
                    logger.error(f"解压缩失败：{str(e)}")
                    raise Exception(f"轮询登录状态失败：解压缩响应内容失败")
            else:
                content = resp.text
            
            
            if not content or content.strip() == '':
                raise Exception("轮询登录状态失败：响应内容为空")
            
            
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                
                content = content.strip()
                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]
                try:
                    data = json.loads(content)
                except json.JSONDecodeError as e:
                    raise Exception(f"轮询登录状态失败：JSON解析错误：{str(e)}")
            
            
            code = data.get('code', 0)
            message = data.get('message', '')
            login_data = data.get('data', {})
            
            
            logger.debug(f"Login poll response: code={code}, message={message}, data={login_data}")
            
            
            if "风险" in message or "验证" in message:
                url = login_data.get('url', '')
                logger.debug(f"Risk detected: message={message}, url={url}")
                return {
                    "success": False,
                    "status": message,
                    "code": code,
                    "url": url,
                    "risk": True
                }
            
            
            login_code = login_data.get('code', code)
            login_message = login_data.get('message', message)
            
            
            if login_code in ERROR_CODES:
                return {
                    "success": False,
                    "status": ERROR_CODES[login_code],
                    "code": login_code
                }
            elif login_code != 0:
                return {
                    "success": False,
                    "status": login_message or "未知状态",
                    "code": login_code
                }
            
            
            cookies = {}
            
            for cookie in resp.cookies:
                cookies[cookie.name] = cookie.value
            
            if cookies:
                
                self.save_cookies(cookies)
                
                user_info = self.get_user_info()
                return {
                    "success": True,
                    "status": "登录成功",
                    "user_info": user_info
                }
            else:
                raise Exception("登录成功但未获取到cookie")
        except ImportError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"缺少brotli库：{str(e)}")
            
            url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            }
            
            try:
                session = requests.Session()
                session.headers.update(headers)
                session.verify = False
                session.proxies = {}  # 强制禁用代理
                resp = session.get(url, timeout=10, proxies={}, allow_redirects=True)
                
                if resp.status_code != 200:
                    raise Exception(f"轮询登录状态失败：HTTP {resp.status_code}")
                
                data = resp.json()
                code = data.get('code', 0)
                message = data.get('message', '')
                login_data = data.get('data', {})
                
                
                logger.debug(f"Login poll response (no brotli): code={code}, message={message}, data={login_data}")
                
                
                if "风险" in message or "验证" in message:
                    url = login_data.get('url', '')
                    logger.debug(f"Risk detected (no brotli): message={message}, url={url}")
                    return {
                        "success": False,
                        "status": message,
                        "code": code,
                        "url": url,
                        "risk": True
                    }
                
                
                login_code = login_data.get('code', code)
                login_message = login_data.get('message', message)
                
                
                if login_code in ERROR_CODES:
                    return {
                        "success": False,
                        "status": ERROR_CODES[login_code],
                        "code": login_code
                    }
                elif login_code != 0:
                    return {
                        "success": False,
                        "status": login_message or "未知状态",
                        "code": login_code
                    }
                
                
                cookies = {}
                for cookie in resp.cookies:
                    cookies[cookie.name] = cookie.value
                
                if cookies:
                    self.save_cookies(cookies)
                    user_info = self.get_user_info()
                    return {
                        "success": True,
                        "status": "登录成功",
                        "user_info": user_info
                    }
                else:
                    raise Exception("登录成功但未获取到cookie")
            except Exception as e:
                logger.error(f"轮询登录状态失败：{str(e)}")
                return {
                    "success": False,
                    "error": str(e)
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def get_user_info(self):
        if self.user_info and self.user_info['success']:
            return self.user_info

        api_url = self.config.get_api_url("login_status_api")
        if not api_url:
            return {"success": False, "msg": "配置错误：未找到用户信息API地址", "is_vip": False}

        success, result = self._api_request(api_url)
        if not success:
            return {"success": False, "msg": f"获取用户信息失败：{result['error']}", "is_vip": False}

        code = result.get('code', -1)
        if code != 0:
            msg = result.get('message', '未知错误')
            return {"success": False, "msg": f"API返回错误：{msg}（code={code}）", "is_vip": False}

        data = result.get('data', {})
        is_login = data.get('isLogin', False)
        if not is_login:
            return {"success": False, "msg": "未登录或Cookie失效", "is_vip": False}

        self.user_info = {
            "success": True,
            "uname": data.get('uname', '未知用户'),
            "mid": str(data.get('mid', '未知ID')),
            "is_vip": data.get('vipStatus', 0) == 1,
            "vip_type": data.get('vipType', 0),
            "level": data.get('level_info', {}).get('current_level', 0),
            "face": data.get('face', ''),
            "msg": f"登录用户：{data.get('uname', '未知用户')} | 等级{data.get('level_info', {}).get('current_level', 0)} | {'会员' if data.get('vipStatus') == 1 else '普通用户'}"
        }
        return self.user_info
    
    def get_user_detail(self):
        try:
            # 先获取用户基本信息，获取mid
            user_info = self.get_user_info()
            if not user_info.get("success"):
                return {"success": False, "error": "未登录或Cookie失效"}
            
            mid = user_info.get("mid", "")
            if not mid:
                return {"success": False, "error": "获取用户ID失败"}
            
            # 构建基本用户信息
            basic_user_detail = {
                "success": True,
                "mid": user_info.get("mid", ""),
                "name": user_info.get("uname", "未知用户"),
                "sex": "保密",
                "face": user_info.get("face", ""),
                "sign": "无签名",
                "level": user_info.get("level", 0),
                "coins": 0,
                "vip": {"status": 1 if user_info.get("is_vip") else 0, "type": user_info.get("vip_type", 0)},
                "is_senior_member": 0,
                "jointime": 0
            }
            
            url = f"https://api.bilibili.com/x/space/acc/info"
            params = {
                "mid": mid
            }
            
            # 确保session包含cookie
            logger.info(f"当前session cookie: {dict(self.session.cookies)}")
            
            # 不使用Wbi签名，直接请求
            logger.info(f"尝试获取用户详细信息，URL: {url}, params: {params}")
            success, result = self._api_request(url, use_wbi=False, params=params)
            logger.info(f"API请求结果 - success: {success}, result: {result}")
            
            if not success:
                # 如果API调用失败，使用基本信息
                logger.debug(f"获取用户详细信息失败：{result.get('error', '未知错误')}，使用基本信息")
                return basic_user_detail
            
            code = result.get('code', -1)
            if code != 0:
                # 如果API返回错误，使用基本信息
                msg = result.get('message', '未知错误')
                logger.debug(f"API返回错误：{msg}（code={code}），使用基本信息")
                return basic_user_detail
            
            data = result.get('data', {})
            
            # 构建返回数据，包含更多字段
            user_detail = {
                "success": True,
                "mid": data.get('mid', user_info.get("mid", "")),
                "name": data.get('name', user_info.get("uname", "未知用户")),
                "sex": data.get('sex', '保密'),
                "face": data.get('face', user_info.get("face", "")),
                "sign": data.get('sign', '无签名'),
                "level": data.get('level', user_info.get("level", 0)),
                "coins": data.get('coins', 0),
                "vip": data.get('vip', {"status": 1 if user_info.get("is_vip") else 0, "type": user_info.get("vip_type", 0)}),
                "is_senior_member": data.get('is_senior_member', 0),
                "jointime": data.get('jointime', 0)
            }
            
            # 打印获取到的用户详细信息，便于调试
            logger.debug(f"获取到的用户详细信息：{user_detail}")
            
            return user_detail
        except Exception as e:
            # 如果发生异常，使用基本信息
            logger.debug(f"获取用户详细信息失败：{str(e)}，使用基本信息")
            # 确保user_info变量已定义
            if 'user_info' not in locals():
                user_info = self.get_user_info()
            return {
                "success": True,
                "mid": user_info.get("mid", ""),
                "name": user_info.get("uname", "未知用户"),
                "sex": "保密",
                "face": user_info.get("face", ""),
                "sign": "无签名",
                "level": user_info.get("level", 0),
                "coins": 0,
                "vip": {"status": 1 if user_info.get("is_vip") else 0, "type": user_info.get("vip_type", 0)},
                "is_senior_member": 0,
                "jointime": 0
            }
    
    def get_space_info(self, mid):
        try:
            url = f"https://api.bilibili.com/x/web-interface/card"
            params = {
                "mid": mid
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': f'https://space.bilibili.com/{mid}',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False
            session.proxies = {}
            
            logger.info(f"尝试获取UP主信息，URL: {url}, params: {params}")
            response = session.get(url, params=params, timeout=15, allow_redirects=True)
            logger.info(f"API响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"API响应: {data}")
                    if data.get('code') == 0:
                        card_data = data.get('data', {}).get('card', {})
                        if card_data:
                            logger.info(f"获取UP主信息成功: {card_data.get('name')}")
                            # 获取等级信息
                            level_info = card_data.get('level_info', {})
                            current_level = level_info.get('current_level', 0)
                            return {
                                "success": True,
                                "mid": mid,
                                "name": card_data.get('name', ''),
                                "face": card_data.get('face', ''),
                                "sign": card_data.get('sign', ''),
                                "level": current_level,
                                "sex": card_data.get('sex', ''),
                                "birthday": card_data.get('birthday', ''),
                                "coins": card_data.get('coins', 0),
                                "fans_badge": card_data.get('fans_badge', False),
                                "official": card_data.get('official', {})
                            }
                except Exception as json_e:
                    logger.error(f"解析JSON失败: {str(json_e)}")
            
            logger.info("尝试使用备用API端点")
            url2 = f"https://api.bilibili.com/x/relation/stat"
            params2 = {
                "vmid": mid
            }
            
            response2 = session.get(url2, params=params2, timeout=15, allow_redirects=True)
            logger.info(f"备用API响应状态码: {response2.status_code}")
            
            if response2.status_code == 200:
                try:
                    data2 = response2.json()
                    logger.info(f"备用API响应: {data2}")
                    if data2.get('code') == 0:
                        # 即使只能获取部分信息，也返回成功
                        return {
                            "success": True,
                            "mid": mid,
                            "name": f"UP主{mid}",
                            "face": "",
                            "sign": "",
                            "level": 0,
                            "sex": "",
                            "birthday": "",
                            "coins": 0,
                            "fans_badge": False,
                            "official": {}
                        }
                except Exception as json_e2:
                    logger.error(f"解析备用API JSON失败: {str(json_e2)}")
            
            logger.info("所有API都失败，返回固定信息")
            return {
                "success": True,
                "mid": mid,
                "name": f"UP主{mid}",
                "face": "",
                "sign": "",
                "level": 0,
                "sex": "",
                "birthday": "",
                "coins": 0,
                "fans_badge": False,
                "official": {}
            }
        except Exception as e:
            logger.error(f"获取UP主空间信息异常：{str(e)}")
            return {
                "success": True,
                "mid": mid,
                "name": f"UP主{mid}",
                "face": "",
                "sign": "",
                "level": 0,
                "sex": "",
                "birthday": "",
                "coins": 0,
                "fans_badge": False,
                "official": {}
            }
    
    def get_space_videos(self, mid, page=1, ps=25):
        try:
            url = f"https://api.bilibili.com/x/space/wbi/arc/search"
            params = {
                "mid": mid,
                "order": "pubdate",
                "ps": ps,
                "pn": page,
                "index": 1,
                "order_avoided": True,
                "platform": "web",
                "web_location": "333.1387",
                "dm_img_list": [],
                "dm_img_str": "V2ViR0wgMS4wIChPcGVuR0wgRVMgMi4wIENocm9taXVtKQ",
                "dm_cover_img_str": "QU5HTEUgKEludGVsLCBJbnRlbChSKSBVSEQgR3JhcGhpY3MgKDB4MDAwMDQ2QTMpIERpcmVjdDNEMTEgdnNfNV8wIHBzXzVfMCwgRDNEMTEpR29vZ2xlIEluYy4gKEludGVsKQ",
                "dm_img_inter": "{\"ds\":[],\"wh\":[3254,2663,106],\"of\":[154,308,154]}"
            }
            
            # 直接使用当前会话的 API 请求方法，确保包含正确的 WBI 签名
            logger.info(f"尝试使用 WBI API 获取作品列表，mid: {mid}")
            success, data = self._api_request(url, use_wbi=True, params=params)
            
            if success:
                video_data = data.get('data', {})
                if video_data:
                    items = video_data.get('list', {}).get('vlist', [])
                    videos = []
                    
                    for item in items:
                        videos.append({
                            "aid": item.get('aid', ''),
                            "bvid": item.get('bvid', ''),
                            "title": item.get('title', ''),
                            "pic": item.get('pic', ''),
                            "description": item.get('description', ''),
                            "created": item.get('created', 0),
                            "length": item.get('length', ''),
                            "play": item.get('play', 0),
                            "video_review": item.get('video_review', 0),
                            "review": item.get('review', 0),
                            "favorites": item.get('favorites', 0),
                            "author": item.get('author', ''),
                            "mid": item.get('mid', '')
                        })
                    
                    logger.info(f"获取作品列表成功，共 {len(videos)} 个视频")
                    return {
                        "success": True,
                        "videos": videos,
                        "page": page,
                        "ps": ps,
                        "total": video_data.get('page', {}).get('count', 0)
                    }
            
            logger.info("尝试使用备用 API 端点")
            url2 = f"https://api.bilibili.com/x/space/arc/search"
            params2 = {
                "mid": mid,
                "ps": ps,
                "pn": page,
                "order": "pubdate"
            }
            
            # 使用正确的请求头和 cookies
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': f'https://space.bilibili.com/{mid}',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False
            session.proxies = {}
            
            # 复制当前会话的 cookies
            if hasattr(self, 'session'):
                session.cookies.update(self.session.cookies)
                logger.info(f"复制了 {len(session.cookies)} 个 cookies")
            
            response = session.get(url2, params=params2, timeout=15, allow_redirects=True)
            logger.info(f"备用 API 响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(f"备用 API 响应: {data}")
                    if data.get('code') == 0:
                        video_data = data.get('data', {})
                        if video_data:
                            items = video_data.get('list', {}).get('vlist', [])
                            videos = []
                            
                            for item in items:
                                videos.append({
                                    "aid": item.get('aid', ''),
                                    "bvid": item.get('bvid', ''),
                                    "title": item.get('title', ''),
                                    "pic": item.get('pic', ''),
                                    "description": item.get('description', ''),
                                    "created": item.get('created', 0),
                                    "length": item.get('length', ''),
                                    "play": item.get('play', 0),
                                    "video_review": item.get('video_review', 0),
                                    "review": item.get('review', 0),
                                    "favorites": item.get('favorites', 0),
                                    "author": item.get('author', ''),
                                    "mid": item.get('mid', '')
                                })
                            
                            logger.info(f"备用 API 获取作品列表成功，共 {len(videos)} 个视频")
                            return {
                                "success": True,
                                "videos": videos,
                                "page": page,
                                "ps": ps,
                                "total": video_data.get('page', {}).get('count', 0)
                            }
                except Exception as json_e:
                    logger.error(f"解析 JSON 失败: {str(json_e)}")
            
            logger.info("尝试使用网页抓取方式获取作品列表")
            space_url = f"https://space.bilibili.com/{mid}/video"
            # 添加更多的请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': f'https://space.bilibili.com/{mid}',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Upgrade-Insecure-Requests': '1'
            }
            session.headers.update(headers)
            response = session.get(space_url, timeout=15, allow_redirects=True)
            logger.info(f"网页响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    content = response.text
                    # 保存网页内容到文件，以便调试
                    with open('space_page.html', 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info("网页内容已保存到 space_page.html")
                    
                    import re
                    # 查找包含视频信息的脚本标签
                    logger.info("查找包含视频信息的脚本标签")
                    script_match = re.search(r'<script>window\.__INITIAL_STATE__=(.*?)</script>', content, re.DOTALL)
                    if script_match:
                        logger.info("找到 __INITIAL_STATE__ 脚本标签")
                        script_content = script_match.group(1)
                        # 尝试不同的方式提取视频列表
                        # 方式1：查找videoList或类似的键
                        logger.info("尝试查找 videoList")
                        video_list_match = re.search(r'videoList\s*:\s*\{[^}]*?list\s*:\s*\[(.*?)\]', script_content, re.DOTALL)
                        if not video_list_match:
                            # 方式2：查找更通用的列表结构
                            logger.info("尝试查找通用列表结构")
                            video_list_match = re.search(r'list\s*:\s*\[(.*?)\]', script_content, re.DOTALL)
                        
                        if video_list_match:
                            logger.info("找到视频列表")
                            videos_str = video_list_match.group(1)
                            # 提取视频信息
                            video_pattern = re.compile(r'\{[^}]*?(?:bvid|aid)[^}]*?\}', re.DOTALL)
                            video_matches = video_pattern.findall(videos_str)
                            logger.info(f"找到 {len(video_matches)} 个视频匹配")
                            
                            if video_matches:
                                videos = []
                                for video_str in video_matches:
                                    try:
                                        # 提取关键信息
                                        bvid_match = re.search(r'bvid\s*:\s*["\']([^"\']+)["\']', video_str)
                                        aid_match = re.search(r'aid\s*:\s*(\d+)', video_str)
                                        title_match = re.search(r'title\s*:\s*["\']([^"\']+)["\']', video_str)
                                        pic_match = re.search(r'pic\s*:\s*["\']([^"\']+)["\']', video_str)
                                        length_match = re.search(r'duration\s*:\s*["\']([^"\']+)["\']|length\s*:\s*["\']([^"\']+)["\']', video_str)
                                        created_match = re.search(r'pubdate\s*:\s*(\d+)', video_str)
                                        
                                        if (bvid_match or aid_match) and title_match:
                                            video = {
                                                "aid": aid_match.group(1) if aid_match else "",
                                                "bvid": bvid_match.group(1) if bvid_match else "",
                                                "title": title_match.group(1),
                                                "pic": pic_match.group(1) if pic_match else "",
                                                "description": "",
                                                "created": int(created_match.group(1)) if created_match else int(time.time()),
                                                "length": length_match.group(1) if length_match and length_match.group(1) else (length_match.group(2) if length_match else "00:00"),
                                                "play": 0,
                                                "video_review": 0,
                                                "review": 0,
                                                "favorites": 0,
                                                "author": f"UP主{mid}",
                                                "mid": mid
                                            }
                                            videos.append(video)
                                    except Exception as e:
                                        continue
                                
                                if videos:
                                    logger.info(f"网页抓取获取作品列表成功，共 {len(videos)} 个视频")
                                    return {
                                        "success": True,
                                        "videos": videos,
                                        "page": page,
                                        "ps": ps,
                                        "total": len(videos)
                                    }
                    
                    # 尝试使用更简单的方式，直接查找视频卡片
                    logger.info("尝试使用简单方式抓取视频列表")
                    video_card_pattern = re.compile(r'<a[^>]+href="/video/(BV[0-9A-Za-z]+)[^>]*>', re.DOTALL)
                    video_matches = video_card_pattern.findall(content)
                    logger.info(f"找到 {len(video_matches)} 个视频链接")
                    
                    if video_matches:
                        videos = []
                        for bvid in video_matches:
                            # 尝试从链接中提取标题
                            title_pattern = re.compile(rf'<a[^>]+href="/video/{bvid}[^>]+title="([^"]+)"[^>]*>', re.DOTALL)
                            title_match = title_pattern.search(content)
                            title = title_match.group(1) if title_match else f"视频 {bvid}"
                            
                            video = {
                                "aid": "",
                                "bvid": bvid,
                                "title": title,
                                "pic": "",
                                "description": "",
                                "created": int(time.time()),
                                "length": "00:00",
                                "play": 0,
                                "video_review": 0,
                                "review": 0,
                                "favorites": 0,
                                "author": f"UP主{mid}",
                                "mid": mid
                            }
                            videos.append(video)
                        
                        if videos:
                            logger.info(f"简单方式抓取获取作品列表成功，共 {len(videos)} 个视频")
                            return {
                                "success": True,
                                "videos": videos,
                                "page": page,
                                "ps": ps,
                                "total": len(videos)
                            }
                except Exception as html_e:
                    logger.error(f"解析 HTML 失败: {str(html_e)}")
            
            # 所有方法都失败，尝试使用B站的移动端API获取视频列表
            logger.info("尝试使用B站移动端API获取作品列表")
            try:
                # 使用B站的移动端API获取视频列表
                api_url = f"https://api.bilibili.com/x/space/arc/search"
                params = {
                    "mid": mid,
                    "ps": ps,
                    "pn": page,
                    "order": "pubdate"
                }
                
                # 使用移动端User-Agent
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                    'Referer': f'https://m.bilibili.com/space/{mid}',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'Origin': 'https://m.bilibili.com'
                }
                
                # 添加一些常见的cookies
                session.cookies.set('buvid3', '7B0F6C90-7F6A-4B1D-8B8F-7B0F6C907F6A12345infoc', domain='.bilibili.com')
                session.cookies.set('bili_jct', '1234567890abcdef1234567890abcdef', domain='.bilibili.com')
                session.cookies.set('DedeUserID', '123456789', domain='.bilibili.com')
                session.cookies.set('DedeUserID__ckMd5', '1234567890abcdef', domain='.bilibili.com')
                session.cookies.set('sid', '1234567890abcdef', domain='.bilibili.com')
                
                response = session.get(api_url, params=params, headers=headers, timeout=15)
                logger.info(f"移动端API响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"移动端API响应: {data}")
                        if data.get('code') == 0:
                            video_data = data.get('data', {})
                            if video_data:
                                items = video_data.get('list', {}).get('vlist', [])
                                videos = []
                                
                                for item in items:
                                    videos.append({
                                        "aid": item.get('aid', ''),
                                        "bvid": item.get('bvid', ''),
                                        "title": item.get('title', ''),
                                        "pic": item.get('pic', ''),
                                        "description": item.get('description', ''),
                                        "created": item.get('created', 0),
                                        "length": item.get('length', ''),
                                        "play": item.get('play', 0),
                                        "video_review": item.get('video_review', 0),
                                        "review": item.get('review', 0),
                                        "favorites": item.get('favorites', 0),
                                        "author": item.get('author', ''),
                                        "mid": item.get('mid', '')
                                    })
                                
                                if videos:
                                    logger.info(f"移动端API获取作品列表成功，共 {len(videos)} 个视频")
                                    return {
                                        "success": True,
                                        "videos": videos,
                                        "page": page,
                                        "ps": ps,
                                        "total": video_data.get('page', {}).get('count', 0)
                                    }
                    except Exception as json_e:
                        logger.error(f"解析 JSON 失败: {str(json_e)}")
            except Exception as e:
                logger.error(f"使用移动端API获取作品列表失败: {str(e)}")
            
            # 所有方法都失败，尝试使用B站的公开API获取视频列表
            logger.info("尝试使用B站公开API获取作品列表")
            try:
                # 使用B站的公开API获取视频列表
                api_url = f"https://api.bilibili.com/x/archive/stat"
                params = {
                    "aid": "1"
                }
                
                # 使用更完整的请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                    'Referer': f'https://space.bilibili.com/{mid}',
                    'Accept': 'application/json, text/plain, */*',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache'
                }
                
                response = session.get(api_url, params=params, headers=headers, timeout=15)
                logger.info(f"公开API响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    # 如果公开API可以访问，说明网络连接正常，但是获取作品列表失败
                    # 可能是因为UP主没有作品，或者API限制
                    logger.info("网络连接正常，但无法获取作品列表")
                    return {
                        "success": True,
                        "videos": [],
                        "page": page,
                        "ps": ps,
                        "total": 0
                    }
            except Exception as e:
                logger.error(f"使用公开API获取作品列表失败: {str(e)}")
            
            # 所有方法都失败，返回错误
            logger.error("所有方法都失败，无法获取作品列表")
            return {
                "success": False,
                "error": "无法获取作品列表，请检查网络连接或稍后重试"
            }
        except Exception as e:
            logger.error(f"获取UP主作品列表异常：{str(e)}")
            return {
                "success": False,
                "error": f"获取作品列表失败：{str(e)}"
            }

    def check_hevc_support(self):
        try:
            ffmpeg_exec = shutil.which('ffmpeg') if shutil.which('ffmpeg') else self.ffmpeg_local
            if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                self.hevc_supported = False
                return False

            cmd = [ffmpeg_exec, '-codecs']
            result = subprocess.run(cmd, capture_output=True, text=False, timeout=10,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
            output = result.stdout.decode('utf-8', errors='replace')
            self.hevc_supported = 'hevc' in output.lower() and 'decoder' in output.lower()
            return self.hevc_supported
        except Exception as e:
            print(f"HEVC支持检测失败：{str(e)}")
            self.hevc_supported = False
            return False

    def install_hevc(self, progress_callback=None):
        try:
            import os
            import subprocess

            script_dir = os.path.dirname(os.path.abspath(__file__))
            hevc_appx = os.path.join(script_dir, "hevc安装.Appx")

            if not os.path.exists(hevc_appx):
                return False, f"未找到HEVC安装文件：{hevc_appx}"

            if not progress_callback:
                def empty_progress(p):
                    pass
                progress_callback = empty_progress

            progress_callback(10)

            try:
                result = subprocess.run(
                    ["powershell", "-Command", f"Add-AppxPackage -Path '{hevc_appx}'"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )

                progress_callback(100)

                if result.returncode == 0:
                    return True, "HEVC扩展安装成功"
                else:
                    error_msg = result.stderr if result.stderr else result.stdout
                    if "已安装" in error_msg or "already installed" in error_msg.lower():
                        return True, "HEVC扩展已安装"
                    return False, f"安装失败：{error_msg}"
            except subprocess.TimeoutExpired:
                return False, "HEVC扩展安装超时"
            except Exception as e:
                return False, f"安装异常：{str(e)}"

        except Exception as e:
            print(f"HEVC扩展安装失败：{str(e)}")
            return False, str(e)

    def check_video_codec_compatible(self, video_path):
        try:
            import json
            import subprocess

            ffprobe_path = self.ffmpeg_local.replace('ffmpeg.exe', 'ffprobe.exe')
            if not os.path.exists(ffprobe_path):
                ffprobe_path = shutil.which('ffprobe')

            if not ffprobe_path:
                return {"compatible": True, "codec": "unknown", "reason": "无法检测编码"}

            cmd = [ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                  creationflags=subprocess.CREATE_NO_WINDOW)

            if result.returncode != 0:
                return {"compatible": True, "codec": "unknown", "reason": "检测失败"}

            data = json.loads(result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    codec_name = stream.get('codec_name', '')
                    codec_long_name = stream.get('codec_long_name', '')

                    incompatible_codecs = ['av1', 'hevc', 'h265']
                    if codec_name in incompatible_codecs:
                        return {
                            "compatible": False,
                            "codec": codec_name,
                            "reason": f"当前视频使用{codec_long_name}编码，部分播放器可能无法直接播放"
                        }
                    return {"compatible": True, "codec": codec_name, "reason": ""}

            return {"compatible": True, "codec": "unknown", "reason": ""}
        except Exception as e:
            print(f"视频兼容性检测失败：{str(e)}")
            return {"compatible": True, "codec": "unknown", "reason": str(e)}

    def convert_video_to_h264(self, input_path, output_path, progress_callback=None):
        try:
            import subprocess

            ffmpeg_path = self.ffmpeg_local
            if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                ffmpeg_path = shutil.which('ffmpeg')

            if not ffmpeg_path:
                return False, "未找到FFmpeg"

            if not progress_callback:
                def empty_progress(p):
                    pass
                progress_callback = empty_progress

            cmd = [
                ffmpeg_path,
                '-i', input_path,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                output_path
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for line in process.stdout:
                try:
                    decoded_line = line.decode('utf-8', errors='replace')
                    if 'frame=' in decoded_line:
                        import re
                        match = re.search(r'frame=\s*(\d+)', decoded_line)
                        if match:
                            frame_num = int(match.group(1))
                            progress = min(int(frame_num / 100), 99)
                            progress_callback(progress)
                except Exception:
                    pass

            process.wait()

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                progress_callback(100)
                return True, "转换成功"
            else:
                return False, "转换失败"

        except Exception as e:
            print(f"视频转换失败：{str(e)}")
            return False, str(e)

    def av2bv(self, aid):
        return self.video_parser.av2bv(aid)

    def bv2av(self, bvid):
        return self.video_parser.bv2av(bvid)

    def parse_media_url(self, url):
        return self.video_parser.parse_media_url(url)
            
    def get_captcha(self):
        try:
            url = "https://passport.bilibili.com/x/passport-login/captcha?source=main_web"
            import logging
            logger = logging.getLogger(__name__)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache'
            }
            
            
            self.session.headers.update(headers)
            
            logger.info(f"发送请求到：{url}")
            resp = self.session.get(url, timeout=10)
            
            
            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.debug(f"更新会话cookies：{dict(resp.cookies)}")
            
            if resp.status_code != 200:
                raise Exception(f"获取验证码失败：HTTP {resp.status_code}")
            
            data = resp.json()
            code = data.get('code', 0)
            if code != 0:
                message = data.get('message', '未知错误')
                raise Exception(f"获取验证码失败：{message}")
            
            captcha_data = data.get('data', {})
            token = captcha_data.get('token', '')
            geetest = captcha_data.get('geetest', {})
            gt = geetest.get('gt', '')
            challenge = geetest.get('challenge', '')
            
            if not token or not gt or not challenge:
                raise Exception("获取验证码参数失败")
            
            return {
                "success": True,
                "token": token,
                "gt": gt,
                "challenge": challenge
            }
        except Exception as e:
            logger.error(f"获取验证码失败：{str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def get_login_key(self):
        try:
            url = "https://passport.bilibili.com/x/passport-login/web/key"
            import logging
            logger = logging.getLogger(__name__)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache'
            }
            
            
            self.session.headers.update(headers)
            
            logger.info(f"发送请求到：{url}")
            resp = self.session.get(url, timeout=10)
            
            if resp.status_code != 200:
                raise Exception(f"获取登录公钥失败：HTTP {resp.status_code}")
            
            data = resp.json()
            code = data.get('code', 0)
            if code != 0:
                message = data.get('message', '未知错误')
                raise Exception(f"获取登录公钥失败：{message}")
            
            key_data = data.get('data', {})
            hash = key_data.get('hash', '')
            key = key_data.get('key', '')
            
            if not hash or not key:
                raise Exception("获取登录公钥和盐失败")
            
            return {
                "success": True,
                "hash": hash,
                "key": key
            }
        except Exception as e:
            logger.error(f"获取登录公钥失败：{str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def login_with_password(self, username, password, token, challenge, validate):
        try:
            
            key_result = self.get_login_key()
            if not key_result.get("success"):
                return key_result
            
            hash = key_result.get("hash")
            public_key = key_result.get("key")
            
            
            import rsa
            import base64
            
            
            password_str = hash + password
            password_bytes = password_str.encode('utf-8')
            
            
            public_key_obj = rsa.PublicKey.load_pkcs1_openssl_pem(public_key.encode('utf-8'))
            
            
            encrypted_password = rsa.encrypt(password_bytes, public_key_obj)
            encrypted_password_base64 = base64.b64encode(encrypted_password).decode('utf-8')
            
            
            url = "https://passport.bilibili.com/x/passport-login/web/login"
            import logging
            logger = logging.getLogger(__name__)
            
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'username': username,
                'password': encrypted_password_base64,
                'keep': 0,
                'source': 'main_web',
                'token': token,
                'challenge': challenge,
                'validate': validate,
                'seccode': f"{validate}|jordan"
            }
            
            
            self.session.headers.update(headers)
            
            logger.info(f"发送登录请求到：{url}")
            logger.info(f"登录参数：{data}")
            
            resp = self.session.post(url, data=data, timeout=10)
            
            if resp.status_code != 200:
                raise Exception(f"登录失败：HTTP {resp.status_code}")
            
            
            try:
                login_data = resp.json()
            except json.JSONDecodeError:
                
                content = resp.text.strip()
                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]
                login_data = json.loads(content)
            except Exception as e:
                logger.error(f"解析登录响应失败：{str(e)}")
                return {
                    "success": False,
                    "error": f"解析登录响应失败：{str(e)}"
                }
            
            
            if not isinstance(login_data, dict):
                logger.error(f"登录响应格式错误：{login_data}")
                return {
                    "success": False,
                    "error": "登录响应格式错误"
                }
            
            code = login_data.get('code', 0)
            message = login_data.get('message', '')
            data = login_data.get('data', {})
            
            if not isinstance(data, dict):
                data = {}
            url = data.get('url', '')
            
            
            logger.info(f"Login response: code={code}, message={message}, data={data}")
            logger.info(f"完整登录响应：{login_data}")
            
            
            data_data = data.get('data', {})
            data_message = data_data.get('message', '') if isinstance(data_data, dict) else ''
            if "risk" in url or "verify" in url or "环境存在风险" in message or "环境存在风险" in data_message:
                
                risk_message = data_message or message or "登录存在风险，需要验证"
                
                if risk_message == "OK" or not risk_message:
                    risk_message = "登录存在风险，需要验证"
                logger.debug(f"Risk detected in login response: message={risk_message}, url={url}")
                return {
                    "success": False,
                    "error": risk_message,
                    "status": risk_message,
                    "code": code,
                    "url": url,
                    "risk": True
                }
            
            if code != 0:
                logger.error(f"登录失败：code={code}, message={message}")
                
                if message == "OK" or not message:
                    
                    if code in ERROR_CODES:
                        error_message = f"登录失败：{ERROR_CODES[code]}（错误码：{code}）"
                    else:
                        error_message = f"登录失败（错误码：{code}）"
                else:
                    error_message = f"登录失败：{message}"
                return {
                    "success": False,
                    "error": error_message,
                    "code": code
                }
            
            
            cookies = resp.cookies.get_dict()
            logger.info(f"获取到的cookie：{cookies}")
            
            
            if cookies:
                cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
                self.save_cookies(cookie_str)
            else:
                
                session_cookies = self.session.cookies.get_dict()
                if session_cookies:
                    logger.info(f"从会话中获取到的cookie：{session_cookies}")
                    cookie_str = '; '.join([f'{k}={v}' for k, v in session_cookies.items()])
                    self.save_cookies(cookie_str)
                else:
                    
                    data = login_data.get('data', {})
                    url = data.get('url', '')
                    if url:
                        logger.info(f"从登录响应的 url 中提取 cookie：{url}")
                        
                        import re
                        cookie_params = re.findall(r'(DedeUserID|DedeUserID__ckMd5|SESSDATA|bili_jct)=([^&]+)', url)
                        if cookie_params:
                            cookie_dict = dict(cookie_params)
                            logger.info(f"从 url 中提取到的 cookie：{cookie_dict}")
                            cookie_str = '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])
                            self.save_cookies(cookie_str)
            
            
            data = login_data.get('data', {})
            sso_url = data.get('url', '')
            if sso_url:
                logger.info(f"处理 SSO 登录跳转：{sso_url}")
                
                try:
                    sso_resp = self.session.get(sso_url, timeout=10, allow_redirects=True)
                    logger.info(f"SSO 跳转响应状态码：{sso_resp.status_code}")
                    
                    sso_cookies = sso_resp.cookies.get_dict()
                    if sso_cookies:
                        logger.info(f"从 SSO 跳转中获取到的 cookie：{sso_cookies}")
                        cookie_str = '; '.join([f'{k}={v}' for k, v in sso_cookies.items()])
                        self.save_cookies(cookie_str)
                except Exception as e:
                    logger.warning(f"SSO 跳转处理失败：{str(e)}")
            
            
            self._init_session()
            
            
            user_info = self.get_user_info()
            
            return {
                "success": True,
                "user_info": user_info,
                "data": login_data.get('data', {})
            }
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"账号密码登录失败：{str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def get_country_list(self):
        try:
            url = "https://passport.bilibili.com/web/generic/country/list"
            import requests
            import logging
            logger = logging.getLogger(__name__)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            session.verify = False
            session.proxies = {}  # 强制禁用代理
            
            resp = session.get(url, timeout=10, proxies={})
            if resp.status_code != 200:
                raise Exception(f"获取国际冠字码失败：HTTP {resp.status_code}")
            
            data = resp.json()
            code = data.get('code', 0)
            if code != 0:
                message = data.get('message', '未知错误')
                raise Exception(f"获取国际冠字码失败：{message}")
            
            
            result = []
            country_data = data.get('data', {})
            
            
            common_countries = country_data.get('common', [])
            other_countries = country_data.get('others', [])
            
            
            for country in common_countries:
                result.append({
                    'cid': country.get('id'),
                    'name': country.get('cname'),
                    'code': country.get('country_id')
                })
            
            
            for country in other_countries:
                result.append({
                    'cid': country.get('id'),
                    'name': country.get('cname'),
                    'code': country.get('country_id')
                })
            
            return result
        except Exception as e:
            logger.error(f"获取国际冠字码失败：{str(e)}")
            return []
    
    def send_sms_code(self, cid, tel, token, challenge, validate):
        try:
            url = "https://passport.bilibili.com/x/passport-login/web/sms/send"
            import logging
            logger = logging.getLogger(__name__)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'cid': cid,
                'tel': tel,
                'source': 'main_web',
                'token': token,
                'challenge': challenge,
                'validate': validate,
                'seccode': f"{validate}|jordan"
            }
            
            
            logger.debug(f"发送短信验证码参数：{data}")
            
            
            self.session.headers.update(headers)
            
            logger.info(f"发送短信验证码请求到：{url}")
            logger.info(f"请求参数：{data}")
            
            resp = self.session.post(url, data=data, timeout=10)
            
            
            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.debug(f"更新会话cookies：{dict(resp.cookies)}")
            
            if resp.status_code != 200:
                raise Exception(f"发送短信验证码失败：HTTP {resp.status_code}")
            
            
            content = resp.text.strip()
            logger.debug(f"发送短信验证码响应：{content}")
            
            
            try:
                sms_data = resp.json()
            except json.JSONDecodeError:
                
                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]
                sms_data = json.loads(content)
            
            code = sms_data.get('code', 0)
            message = sms_data.get('message', '未知错误')
            logger.debug(f"发送短信验证码响应代码：{code}，消息：{message}")
            
            if code != 0:
                
                if message == "OK" or not message:
                    
                    if code in ERROR_CODES:
                        error_message = f"发送短信验证码失败：{ERROR_CODES[code]}（错误码：{code}）"
                    else:
                        error_message = f"发送短信验证码失败（错误码：{code}）"
                else:
                    error_message = f"发送短信验证码失败：{message}"
                raise Exception(error_message)
            
            
            logger.debug("发送短信验证码成功，返回结果：{\"success\": True, \"data\": " + str(sms_data.get('data', {})) + "}")
            
            return {
                "success": True,
                "data": sms_data.get('data', {})
            }
        except Exception as e:
            logger.error(f"发送短信验证码失败：{str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def login_with_sms(self, cid, tel, code, captcha_key):
        try:
            url = "https://passport.bilibili.com/x/passport-login/web/login/sms"
            import logging
            logger = logging.getLogger(__name__)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            data = {
                'cid': str(cid),  
                'tel': tel,
                'code': code,
                'source': 'main_web',
                'captcha_key': captcha_key,
                'go_url': 'https://www.bilibili.com',
                'keep': True
            }
            
            
            self.session.headers.update(headers)
            
            logger.info(f"发送短信验证码验证请求到：{url}")
            logger.info(f"请求参数：{data}")
            
            resp = self.session.post(url, data=data, timeout=10)
            
            
            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.debug(f"更新会话cookies：{dict(resp.cookies)}")
            
            if resp.status_code != 200:
                raise Exception(f"短信验证码验证失败：HTTP {resp.status_code}")
            
            
            content = resp.text.strip()
            logger.debug(f"短信验证码验证响应：{content}")
            
            
            try:
                verify_data = resp.json()
            except json.JSONDecodeError:
                
                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]
                verify_data = json.loads(content)
            
            code = verify_data.get('code', 0)
            message = verify_data.get('message', '未知错误')
            logger.debug(f"短信验证码验证响应代码：{code}，消息：{message}")
            
            if code != 0:
                
                error_message = f"短信验证码验证失败：{message}（错误码：{code}）"
                raise Exception(error_message)
            
            
            cookies = resp.cookies.get_dict()
            logger.info(f"获取到的cookie：{cookies}")
            
            
            if cookies:
                cookie_str = '; '.join([f'{k}={v}' for k, v in cookies.items()])
                self.save_cookies(cookie_str)
            else:
                
                session_cookies = self.session.cookies.get_dict()
                if session_cookies:
                    logger.info(f"从会话中获取到的cookie：{session_cookies}")
                    cookie_str = '; '.join([f'{k}={v}' for k, v in session_cookies.items()])
                    self.save_cookies(cookie_str)
            
            
            self._init_session()
            
            
            user_info = self.get_user_info()
            
            return {
                "success": True,
                "user_info": user_info,
                "data": verify_data.get('data', {})
            }
        except Exception as e:
            logger.error(f"短信登录失败：{str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def parse_media(self, media_type, media_id, is_tv_mode=False, progress_callback=None):
        logger.info(f"开始解析媒体信息: 类型={media_type}, ID={media_id}")
        try:
            bvid = None
            title = ""
            cid = ""
            collection = []
            bangumi_info = None
            cheese_info = None

            if progress_callback:
                progress_callback(10, "正在解析媒体类型...")

            if media_type == "av":
                try:
                    av_data = self._get_av_info(media_id)
                    logger.info(f"获取AV数据成功")
                    
                    is_bangumi = False
                    
                    if 'season_id' in av_data and av_data['season_id'] > 0:
                        
                        is_bangumi = True
                        logger.info(f"发现season_id: {av_data['season_id']}")
                    elif 'is_chargeable_season' in av_data and av_data['is_chargeable_season']:
                        
                        is_bangumi = True
                        logger.info(f"发现is_chargeable_season: {av_data['is_chargeable_season']}")
                    elif 'redirect_url' in av_data and 'bangumi' in av_data['redirect_url']:
                        
                        is_bangumi = True
                        logger.info(f"发现redirect_url: {av_data['redirect_url']}")
                    
                    logger.info(f"是否为番剧: {is_bangumi}")
                    
                    if is_bangumi:
                        
                        media_type = "bangumi"
                        logger.info("转换为番剧处理")
                        
                        
                        if 'redirect_url' in av_data and 'bangumi' in av_data['redirect_url']:
                            redirect_url = av_data['redirect_url']
                            logger.info(f"发现番剧重定向链接: {redirect_url}")
                            
                            redirect_parse = self.parse_media_url(redirect_url)
                            logger.info(f"重定向链接解析结果: {redirect_parse}")
                            if redirect_parse['type'] == 'bangumi' and redirect_parse['id']:
                                bangumi_id = redirect_parse['id']
                                logger.info(f"获取到的番剧ID: {bangumi_id}")
                                try:
                                    
                                    logger.info(f"尝试获取番剧信息，ID: {bangumi_id}")
                                    if progress_callback:
                                        progress_callback(20, "正在获取番剧信息...")
                                    bangumi_full_info = self._get_bangumi_full_info(bangumi_id)
                                    logger.info(f"番剧信息获取成功")
                                    bangumi_info = bangumi_full_info
                                    season_title = bangumi_full_info['season_title']
                                    first_ep = bangumi_full_info['episodes'][0]
                                    bvid = first_ep['bvid']
                                    cid = first_ep['cid']
                                    first_ep_title = first_ep.get('ep_title', f"第1集")
                                    title = self._sanitize_filename(f"{season_title}_{first_ep_title}")
                                    logger.info(f"番剧信息获取成功: {season_title}")
                                    
                                    media_id = bangumi_id
                                    
                                    pass
                                except Exception as e:
                                    logger.error(f"使用重定向链接获取番剧信息失败: {str(e)}")
                                    
                                    media_type = "video"
                                    bvid = av_data['bvid']
                                    cid = av_data['cid']
                                    title = self._sanitize_filename(av_data['title'])
                                    collection = self._get_collection_info(bvid)
                                    logger.info(f"回退为普通视频处理: {title}")
                        else:
                            
                            season_id = av_data.get('season_id', '')
                            if not season_id:
                                
                                season_id = av_data.get('season', {}).get('season_id', '')
                            if season_id:
                                try:
                                    
                                    if progress_callback:
                                        progress_callback(20, "正在获取番剧信息...")
                                    bangumi_full_info = self._get_bangumi_full_info(season_id)
                                    bangumi_info = bangumi_full_info
                                    season_title = bangumi_full_info['season_title']
                                    first_ep = bangumi_full_info['episodes'][0]
                                    bvid = first_ep['bvid']
                                    cid = first_ep['cid']
                                    first_ep_title = first_ep.get('ep_title', f"第1集")
                                    title = self._sanitize_filename(f"{season_title}_{first_ep_title}")
                                    logger.info(f"使用season_id获取番剧信息成功: {season_title}")
                                except Exception as e:
                                    logger.error(f"使用season_id获取番剧信息失败: {str(e)}")
                                    
                                    media_type = "video"
                                    bvid = av_data['bvid']
                                    cid = av_data['cid']
                                    title = self._sanitize_filename(av_data['title'])
                                    collection = self._get_collection_info(bvid)
                                    logger.info(f"回退为普通视频处理: {title}")
                            else:
                                
                                media_type = "video"
                                bvid = av_data['bvid']
                                cid = av_data['cid']
                                title = self._sanitize_filename(av_data['title'])
                                collection = self._get_collection_info(bvid)
                    else:
                        
                        media_type = "video"
                        bvid = av_data['bvid']
                        cid = av_data['cid']
                        title = self._sanitize_filename(av_data['title'])
                        
                        collection = self._get_collection_info(bvid)
                except Exception as e:
                    logger.error(f"AV信息获取失败: {str(e)}")
                    if not self.cookies:
                        logger.info("未登录，可能需要登录才能访问此视频")
                        return {
                            "success": False,
                            "error": "视频可能需要登录才能访问，请先登录"
                        }
                    logger.info("尝试使用课程API解析此AV号...")
                    try:
                        if progress_callback:
                            progress_callback(15, "尝试使用课程API解析...")
                        cheese_info = self._get_cheese_full_info(media_id)
                        if cheese_info and cheese_info.get('success', True):
                            logger.info("使用课程API解析成功！")
                            media_type = "cheese"
                            season_title = cheese_info['season_title']
                            first_ep = cheese_info['episodes'][0]
                            bvid = first_ep['bvid']
                            cid = first_ep['cid']
                            first_ep_title = first_ep.get('ep_title', f"第1集")
                            title = self._sanitize_filename(f"{season_title}_{first_ep_title}")
                            collection = cheese_info['episodes']
                        else:
                            logger.error("课程API解析也失败")
                            logger.info("尝试使用其他API端点...")
                            api_endpoints = [
                                ("https://api.bilibili.com/x/web-interface/view", {"aid": media_id}),
                                ("https://api.bilibili.com/x/web-interface/view/detail", {"aid": media_id}),
                                ("https://api.bilibili.com/x/web-interface/view?jsonp=jsonp", {"aid": media_id}),
                                ("https://api.bilibili.com/x/player/pagelist", {"aid": media_id})
                            ]
                            
                            success = False
                            for url, params in api_endpoints:
                                try:
                                    logger.info(f"尝试API: {url} with params: {params}")
                                    success, api_data = self._api_request(url, params=params)
                                    if success and api_data.get('code') == 0:
                                        data = api_data.get('data', {})
                                        if 'View' in data:
                                            view = data['View']
                                        elif 'list' in data:
                                            view = data
                                        else:
                                            view = data
                                        
                                        if view and (view.get('bvid') or view.get('title')):
                                            logger.info(f"使用{url} API解析成功！")
                                            media_type = "video"
                                            bvid = view.get('bvid', media_id)
                                            cid = view.get('cid', 0)
                                            title = self._sanitize_filename(view.get('title', '未知视频'))
                                            collection = self._get_collection_info(bvid)
                                            success = True
                                            break
                                except Exception as e3:
                                    logger.error(f"API {url} 解析失败: {str(e3)}")
                            
                            if not success:
                                return {
                                    "success": False,
                                    "error": "视频不存在或已被删除（或需要登录）"
                                }
                    except Exception as e2:
                        logger.error(f"课程API解析失败: {str(e2)}")
                        return {
                            "success": False,
                            "error": "视频不存在或已被删除（或需要登录）"
                        }

            elif media_type == "sponsor":
                
                media_type = "video"
                bvid = media_id
                cid = self._get_cid(media_type, bvid)
                video_info = self._get_video_main_info(bvid)
                title = self._sanitize_filename(video_info['title'])
                collection = self._get_collection_info(bvid)
                logger.info(f"充电视频处理: {title}")

            if media_type == "video":
                if not bvid:
                    bvid = media_id
                if not cid:
                    cid = self._get_cid(media_type, bvid)
                if not title or not collection:
                    video_info = self._get_video_main_info(bvid)
                    if not title:
                        title = self._sanitize_filename(video_info['title'])
                    
                    
                    is_interact = False
                    interact_info = None
                    if 'interaction' in video_info:
                        is_interact = True
                        interact_info = video_info['interaction']
                        logger.info("检测到互动视频")
                    
                    elif 'is_stein_gate' in video_info and video_info['is_stein_gate']:
                        is_interact = True
                        interact_info = {"is_stein_gate": True}
                        logger.info("通过is_stein_gate字段检测到互动视频")
                    
                    elif 'stein_guide_cid' in video_info and video_info['stein_guide_cid']:
                        is_interact = True
                        interact_info = {"stein_guide_cid": video_info['stein_guide_cid']}
                        logger.info(f"通过stein_guide_cid字段检测到互动视频：{video_info['stein_guide_cid']}")
                    
                    if not collection:
                        if 'pages' in video_info:
                            for page in video_info['pages']:
                                duration = page.get('duration', 0)
                                collection.append({
                                    "page": page.get('page', 0),
                                    "cid": page.get('cid', 0),
                                    "title": self._sanitize_filename(page.get('part', f"第{page.get('page')}集")),
                                    "duration": duration,
                                    "duration_str": self._format_duration(duration)
                                })
                            logger.info(f"从video_info获取合集信息，共{len(collection)}集")
                        else:
                            collection = self._get_collection_info(bvid)
                            logger.info(f"从API获取合集信息，共{len(collection)}集")
                    
                    
                    if is_interact and interact_info:
                        graph_version = interact_info.get('graph_version')
                        if graph_version:
                            try:
                                interact_data = self._get_interact_video_info(bvid, graph_version)
                                logger.info("获取到互动视频信息")
                                
                                if 'story_list' in interact_data:
                                    interact_modules = []
                                    for module in interact_data['story_list']:
                                        interact_modules.append({
                                            "module_id": module.get('node_id', ''),
                                            "edge_id": module.get('edge_id', ''),
                                            "title": module.get('title', ''),
                                            "cid": module.get('cid', ''),
                                            "cover": module.get('cover', '')
                                        })
                                    
                                    collection.extend(interact_modules)
                                    logger.info(f"添加互动视频模块，共{len(interact_modules)}个")
                            except Exception as e:
                                logger.error(f"获取互动视频模块信息失败：{str(e)}")
                logger.info(f"视频信息处理完成: {title}")

            elif media_type == "bangumi":
                if progress_callback:
                    progress_callback(20, "正在获取番剧信息...")
                bangumi_full_info = self._get_bangumi_full_info(media_id)
                bangumi_info = bangumi_full_info
                season_title = bangumi_full_info['season_title']
                first_ep = bangumi_full_info['episodes'][0]
                bvid = first_ep['bvid']
                cid = first_ep['cid']
                first_ep_title = first_ep.get('ep_title', f"第1集")
                title = self._sanitize_filename(f"{season_title}_{first_ep_title}")
                logger.info(f"番剧信息处理完成: {season_title}")

            elif media_type == "cheese":
                if progress_callback:
                    progress_callback(20, "正在获取课程信息...")
                cheese_full_info = self._get_cheese_full_info(media_id)
                cheese_info = cheese_full_info
                season_title = cheese_full_info['season_title']
                first_ep = cheese_full_info['episodes'][0]
                bvid = first_ep['bvid']
                cid = first_ep['cid']
                season_id = first_ep.get('season_id', media_id)
                ep_id = first_ep.get('ep_id', '')
                first_ep_title = first_ep.get('ep_title', f"第1集")
                title = self._sanitize_filename(f"{season_title}_{first_ep_title}")
                logger.info(f"课程信息处理完成: {season_title}")

            
            if progress_callback:
                progress_callback(40, "正在获取播放信息...")
            if media_type == "cheese":
                play_info = self._get_play_info(media_type, bvid, cid, is_tv_mode, season_id=season_id, ep_id=ep_id)
            elif media_type == "bangumi":
                
                ep_id = first_ep.get('ep_id', '')
                play_info = self._get_play_info(media_type, bvid, cid, is_tv_mode, ep_id=ep_id)
            else:
                play_info = self._get_play_info(media_type, bvid, cid, is_tv_mode)
            if not play_info['success']:
                raise Exception(play_info['error'])
            logger.info("播放信息获取成功")

            
            if media_type == "cheese" and cheese_info:
                episodes = cheese_info.get('episodes', [])
                collection = episodes  
                logger.info(f"课程集数: {len(collection)}")
                
                total_episodes = len(episodes)
                for i, ep in enumerate(episodes):
                    try:
                        if progress_callback:
                            progress = 40 + (i * 60) // total_episodes
                            progress_callback(progress, f"正在处理第{i+1}/{total_episodes}集...")
                        ep_bvid = ep.get('bvid', '')
                        ep_cid = ep.get('cid', '')
                        ep_season_id = ep.get('season_id', media_id)
                        ep_ep_id = ep.get('ep_id', '')
                        ep_play_info = self._get_play_info('cheese', ep_bvid, ep_cid, is_tv_mode, season_id=ep_season_id, ep_id=ep_ep_id)
                        if ep_play_info['success']:
                            
                            episodes[i]['video_urls'] = ep_play_info['video_urls']
                            episodes[i]['audio_url'] = ep_play_info['audio_url']
                            episodes[i]['kid'] = ep_play_info.get('kid')
                            episodes[i]['permission_denied'] = False
                        else:
                            episodes[i]['permission_denied'] = True
                            episodes[i]['title'] = f"{ep.get('ep_title', '')}（权限不足）"
                    except Exception as e:
                        logger.warning(f"获取第{i+1}集播放信息失败：{str(e)}")
                        episodes[i]['permission_denied'] = True
            elif media_type == "bangumi" and bangumi_info:
                episodes = bangumi_info.get('episodes', [])
                collection = episodes  
                logger.info(f"番剧集数: {len(collection)}")
                
                # 检查用户是否为会员
                user_info = self.get_user_info()
                is_vip = user_info.get('is_vip', False)
                logger.info(f"用户会员状态: {is_vip}")
                
                # 为每集单独检查权限
                total_episodes = len(episodes)
                for i, ep in enumerate(episodes):
                    try:
                        if progress_callback:
                            progress = 40 + (i * 60) // total_episodes
                            progress_callback(progress, f"正在检查第{i+1}/{total_episodes}集权限...")
                        ep_bvid = ep.get('bvid', '')
                        ep_cid = ep.get('cid', '')
                        ep_id = ep.get('ep_id', '')
                        ep_play_info = self._get_play_info('bangumi', ep_bvid, ep_cid, is_tv_mode, ep_id=ep_id)
                        if ep_play_info['success']:
                            episodes[i]['permission_denied'] = False
                            episodes[i]['video_urls'] = ep_play_info.get('video_urls', {})
                            episodes[i]['audio_url'] = ep_play_info.get('audio_url', '')
                            episodes[i]['kid'] = ep_play_info.get('kid')
                        else:
                            episodes[i]['permission_denied'] = True
                            episodes[i]['title'] = f"{ep.get('ep_title', '')}（权限不足）"
                    except Exception as e:
                        logger.warning(f"检查第{i+1}集权限失败：{str(e)}")
                        episodes[i]['permission_denied'] = True
                        episodes[i]['title'] = f"{ep.get('ep_title', '')}（权限检查失败）"
            elif media_type == "video" and collection:
                
                
                logger.info(f"视频合集数: {len(collection)}")
                for i, ep in enumerate(collection):
                    collection[i]['permission_denied'] = False

            
            pic = None
            if media_type == "video" and 'video_info' in locals():
                pic = video_info.get('pic', '')
            elif media_type == "bangumi" and bangumi_info:
                pic = bangumi_info.get('cover', '')
            elif media_type == "cheese" and cheese_info:
                pic = cheese_info.get('cover', '')
            
            
            total_duration = 0
            
            if collection:
                for i, ep in enumerate(collection):
                    
                    if not ep.get('cover'):
                        if media_type == "video" and 'video_info' in locals():
                            
                            collection[i]['cover'] = video_info.get('pic', '')
                        elif media_type == "bangumi" and bangumi_info:
                            
                            collection[i]['cover'] = bangumi_info.get('cover', '')
                        elif media_type == "cheese" and cheese_info:
                            
                            collection[i]['cover'] = cheese_info.get('cover', '')
                    
                    if ep.get('duration'):
                        total_duration += int(ep.get('duration'))
            
            
            if media_type == "bangumi" and bangumi_info:
                episodes = bangumi_info.get('episodes', [])
                for i, ep in enumerate(episodes):
                    if not ep.get('cover'):
                        episodes[i]['cover'] = bangumi_info.get('cover', '')
                    
                    if ep.get('duration'):
                        total_duration += int(ep.get('duration'))
            
            
            if media_type == "cheese" and cheese_info:
                episodes = cheese_info.get('episodes', [])
                for i, ep in enumerate(episodes):
                    if not ep.get('cover'):
                        episodes[i]['cover'] = cheese_info.get('cover', '')
                    
                    if ep.get('duration'):
                        total_duration += int(ep.get('duration'))
            
            
            estimated_size_mb = 0
            if total_duration > 0:
                
                estimated_size_mb = int(total_duration * 0.375)
                if estimated_size_mb >= 1024:
                    estimated_size_gb = estimated_size_mb / 1024
                    estimated_size_str = f"{estimated_size_gb:.1f} GB"
                else:
                    estimated_size_str = f"{estimated_size_mb} MB"
            else:
                estimated_size_str = "未知"

            logger.info(f"媒体信息解析成功: {title}，总时长: {total_duration}秒，预估大小: {estimated_size_str}")
            
            return {
                "success": True,
                "type": media_type,
                "title": title,
                "bvid": bvid,
                "cid": cid,
                "pic": pic,
                "qualities": play_info['qualities'],
                "video_urls": play_info['video_urls'],
                "audio_url": play_info['audio_url'],
                "audio_qualities": play_info.get('audio_qualities', []),
                "is_tv_mode": is_tv_mode,
                "is_vip": play_info['is_vip'],
                "has_hevc": play_info['has_hevc'],
                "collection": collection,
                "episodes": collection,  
                "is_collection": len(collection) > 1,
                "bangumi_info": bangumi_info,
                "cheese_info": cheese_info,
                "is_bangumi": media_type == "bangumi",
                "is_cheese": media_type == "cheese",
                "is_interact": is_interact if 'is_interact' in locals() else False,
                "interact_info": interact_info if 'interact_info' in locals() else None,
                "total_duration": total_duration,
                "estimated_size": estimated_size_str,
                "estimated_size_mb": estimated_size_mb,
                "kid": play_info.get('kid')
            }
        except Exception as e:
            logger.error(f"解析媒体信息失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_av_info(self, aid):
        try:
            url = self.config.get_api_url("av_info_api").format(aid=aid)
            success, data = self._api_request(url, timeout=10)
            if not success:
                raise Exception(f"av号信息获取失败：{data['error']}")
            if data.get('code') != 0:
                raise Exception(f"av号信息获取失败：{data.get('message', '未知错误')}")
            
            if 'data' in data:
                return data['data']
            elif 'result' in data:
                return data['result']
            else:
                raise Exception(f"API返回格式错误，未找到data或result字段：{data}")
        except Exception as e:
            raise Exception(f"av信息获取失败：{str(e)}（aid={aid}）")

    def _get_bangumi_full_info(self, media_id):
        try:
            
            is_ep_id = media_id.startswith('ep')
            id_value = media_id[2:] if is_ep_id else media_id
            
            if is_ep_id:
                url = "https://api.bilibili.com/pgc/view/web/season"
                params = {"ep_id": id_value}
                logger.debug(f"使用ep_id获取番剧信息：{url}?ep_id={id_value}")
            else:
                url = "https://api.bilibili.com/pgc/view/web/season"
                params = {"season_id": id_value}
                logger.debug(f"使用season_id获取番剧信息：{url}?season_id={id_value}")
                
            success, api_data = self._api_request(url, timeout=15, use_wbi=True, params=params)
            if not success:
                logger.info("尝试不使用WBI签名获取番剧信息")
                success, api_data = self._api_request(url, timeout=15, use_wbi=False, params=params)
                if not success:
                    raise Exception(f"番剧API请求失败：{api_data['error']}")

            if api_data.get('code') != 0:
                raise Exception(f"番剧API错误：{api_data.get('message', '未知错误')}")

            
            logger.debug(f"API返回数据结构：{list(api_data.keys())}")
            
            
            data = api_data.get('data', {})
            result = api_data.get('result', data)
            
            logger.debug(f"result数据结构：{list(result.keys()) if result else '空'}")
            
            episodes = []
            
            if 'main_section' in result and 'episodes' in result['main_section']:
                episodes = result['main_section']['episodes']
                logger.debug(f"从main_section获取剧集数量：{len(episodes)}")
            elif not episodes and 'sections' in result:
                for section in result['sections']:
                    if 'episodes' in section and section['episodes']:
                        episodes = section['episodes']
                        logger.debug(f"从sections获取剧集数量：{len(episodes)}")
                        break
            elif not episodes and 'episodes' in result:
                episodes = result['episodes']
                logger.debug(f"从result直接获取剧集数量：{len(episodes)}")
            elif not episodes and 'ep' in result:
                
                episodes = [result['ep']]
                logger.debug(f"从ep字段获取剧集数量：{len(episodes)}")

            if not episodes:
                logger.error(f"API未返回剧集数据，result: {json.dumps(result).decode('utf-8')[:1000]}...")
                
                return {
                    "success": True,
                    "season_title": result.get('title', '未知番剧'),
                    "season_id": id_value,
                    "total_episodes": 0,
                    "episodes": [],
                    "cover": result.get('cover', ''),
                    "desc": result.get('desc', ''),
                    "publish_time": result.get('publish_time', 0),
                    "rating": result.get('rating', {}),
                    "stat": result.get('stat', {})
                }

            season_title = '未知番剧'
            if 'main_section' in result:
                season_title = result['main_section'].get('title', season_title)
            if season_title == '未知番剧':
                season_title = result.get('title', season_title)
            season_title = self._sanitize_filename(season_title)
            season_id = id_value
            
            season_cover = result.get('cover', '')

            bangumi_episodes = []
            for idx, ep in enumerate(episodes, 1):
                logger.info(f"剧集{idx}信息字段：{list(ep.keys())}")
                logger.info(f"剧集{idx}信息：{json.dumps(ep).decode('utf-8')[:500]}")
                ep_type = ep.get('type_name', '')
                ep_num = ep.get('ep', idx)
                
                if ep_type in ['SP', 'OVA', '剧场版']:
                    ep_index = f"{ep_type}{ep_num}"
                else:
                    ep_index = f"第{ep_num}集"

                title_candidates = [
                    ep.get('long_title', ''),
                    ep.get('sub_title', ''),
                    ep.get('title', ''),
                    f"第{ep_num}集"
                ]
                actual_title = next((t for t in title_candidates if t), f"第{ep_num}集")
                actual_title = actual_title.replace("正片", "")
                actual_title = actual_title.replace("_", " ")
                actual_title = actual_title.strip()
                if not actual_title:
                    actual_title = f"第{ep_num}集"

                
                ep_id = ep.get('id', '')
                if not ep_id:
                    ep_id = ep.get('ep_id', '')
                if not ep_id:
                    ep_id = ep.get('ep', '')

                bvid = ep.get('bvid', '')
                if not bvid:
                    bvid = ep.get('aid', '')
                
                
                
                
                bangumi_episodes.append({
                    "ep_id": ep_id,
                    "bvid": bvid,
                    "cid": ep.get('cid', ''),
                    "ep_index": ep_index,
                    "ep_title": self._sanitize_filename(actual_title),
                    "duration": ep.get('duration', 0),
                    "duration_str": self._format_duration(ep.get('duration', 0)),
                    "aid": ep.get('aid', ''),
                    "cover": ep.get('cover', season_cover),  
                    "share_url": ep.get('share_url', ''),
                    "status": ep.get('status', 0)
                })

            return {
                "success": True,
                "season_title": season_title,
                "season_id": season_id,
                "total_episodes": len(bangumi_episodes),
                "episodes": bangumi_episodes,
                "cover": result.get('cover', ''),
                "desc": result.get('desc', ''),
                "publish_time": result.get('publish_time', 0),
                "rating": result.get('rating', {}),
                "stat": result.get('stat', {})
            }
        except Exception as e:
            print(f"获取番剧信息失败：{str(e)}")
            raise Exception(f"番剧信息获取失败：{str(e)}")

    def _get_cheese_full_info(self, media_id):
        try:
            logger.info(f"开始获取课程信息，media_id: {media_id}")
            
            # 处理ep开头的ID
            is_ep_id = media_id.startswith('ep')
            id_value = media_id[2:] if is_ep_id else media_id
            
            original_headers = self.session.headers.copy()
            
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/cheese/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            })
            
            logger.info("发送课程API请求...")
            
            cheese_api_url = "https://api.bilibili.com/cheese/api/subject/info"
            if is_ep_id:
                params = {'ep_id': id_value}
            else:
                params = {'season_id': id_value}
            
            logger.info(f"尝试cheese专用API: {cheese_api_url} with params: {params}")
            success, api_data = self._api_request(cheese_api_url, timeout=15, use_wbi=True, params=params)
            
            if not success:
                logger.info("尝试不使用WBI签名获取课程信息")
                success, api_data = self._api_request(cheese_api_url, timeout=15, use_wbi=False, params=params)
                
            if success and api_data.get('code') == 0:
                data = api_data.get('data', {})
                logger.info("cheese API请求成功")
                
                # 构建课程信息
                season_title = data.get('title', '未知课程')
                season_title = self._sanitize_filename(season_title)
                season_id = data.get('season_id', media_id)
                cover = data.get('cover', '')
                desc = data.get('desc', '')
                
                # 获取剧集信息
                episodes = data.get('episodes', [])
                logger.info(f"获取到的剧集数量：{len(episodes)}")
                
                cheese_episodes = []
                for idx, ep in enumerate(episodes, 1):
                    ep_num = ep.get('index', idx)
                    ep_index = f"第{ep_num}集"

                    title = ep.get('title', f"第{ep_num}集")
                    title = title.strip()
                    if not title:
                        title = f"第{ep_num}集"

                    status = ep.get('status', 1)  
                    is_paid = status != 1

                    cheese_episodes.append({
                        "ep_id": ep.get('id', ''),
                        "season_id": season_id,
                        "bvid": str(ep.get('aid', '')),  
                        "cid": ep.get('cid', ''),
                        "ep_index": ep_index,
                        "ep_title": self._sanitize_filename(title),
                        "duration": ep.get('duration', 0),
                        "duration_str": self._format_duration(ep.get('duration', 0)),
                        "status": status,
                        "kid": ep.get('kid', None)
                    })
                
                self.session.headers = original_headers
                
                return {
                    "success": True,
                    "season_title": season_title,
                    "season_id": season_id,
                    "total_episodes": len(cheese_episodes),
                    "episodes": cheese_episodes,
                    "cover": cover,
                    "desc": desc,
                    "share_url": f"https://www.bilibili.com/cheese/play/ss{season_id}"
                }
            
            logger.info("尝试使用番剧API获取课程信息")
            url = "https://api.bilibili.com/pugv/view/web/season"
            if is_ep_id:
                params = {'ep_id': id_value}
            else:
                params = {'season_id': id_value}
            
            original_headers = self.session.headers.copy()
            self.session.headers.update({'Referer': 'https://www.bilibili.com'})
            
            success, api_data = self._api_request(url, timeout=15, use_wbi=True, params=params)
            
            if not success:
                logger.info("尝试不使用WBI签名获取课程信息")
                success, api_data = self._api_request(url, timeout=15, use_wbi=False, params=params)
                if not success:
                    logger.error(f"API请求失败：{api_data['error']}")
                    logger.info("尝试使用其他API端点...")
                    api_endpoints = [
                        ("https://api.bilibili.com/cheese/api/subject/info", {"season_id": id_value}),
                        ("https://api.bilibili.com/cheese/api/playurl", {"season_id": id_value, "cid": "1"})
                    ]
                    
                    for api_url, api_params in api_endpoints:
                        try:
                            logger.info(f"尝试API: {api_url} with params: {api_params}")
                            success, api_data = self._api_request(api_url, params=api_params)
                            if success and api_data.get('code') == 0:
                                data = api_data.get('data', {})
                                
                                season_title = data.get('title', '未知课程')
                                season_title = self._sanitize_filename(season_title)
                                season_id = data.get('season_id', media_id)
                                cover = data.get('cover', '')
                                desc = data.get('desc', '')
                                
                                episodes = data.get('episodes', [])
                                logger.info(f"获取到的剧集数量：{len(episodes)}")
                                
                                cheese_episodes = []
                                for idx, ep in enumerate(episodes, 1):
                                    ep_num = ep.get('index', idx)
                                    ep_index = f"第{ep_num}集"

                                    title = ep.get('title', f"第{ep_num}集")
                                    title = title.strip()
                                    if not title:
                                        title = f"第{ep_num}集"

                                    status = ep.get('status', 1)  
                                    is_paid = status != 1

                                    cheese_episodes.append({
                                        "ep_id": ep.get('id', ''),
                                        "season_id": season_id,
                                        "bvid": str(ep.get('aid', '')),  
                                        "cid": ep.get('cid', ''),
                                        "ep_index": ep_index,
                                        "ep_title": self._sanitize_filename(title),
                                        "duration": ep.get('duration', 0),
                                        "duration_str": self._format_duration(ep.get('duration', 0)),
                                        "status": status,
                                        "kid": ep.get('kid', None)
                                    })
                                
                                self.session.headers = original_headers
                                
                                return {
                                    "success": True,
                                    "season_title": season_title,
                                    "season_id": season_id,
                                    "total_episodes": len(cheese_episodes),
                                    "episodes": cheese_episodes,
                                    "cover": cover,
                                    "desc": desc,
                                    "share_url": f"https://www.bilibili.com/cheese/play/ss{season_id}"
                                }
                        except Exception as e:
                            logger.error(f"API {api_url} 解析失败: {str(e)}")
                            continue
                    
                    # 所有API都失败
                    raise Exception(f"课程API请求失败：{api_data['error']}")

            # 恢复原始headers
            self.session.headers = original_headers

            if api_data.get('code') != 0:
                error_msg = api_data.get('message', '未知错误')
                logger.error(f"API错误信息：{error_msg}")
                raise Exception(f"课程API错误：{error_msg}")

            data = api_data.get('data', {})
            logger.debug(f"data 包含的键：{list(data.keys())}")
            
            episodes = data.get('episodes', [])
            logger.info(f"获取到的剧集数量：{len(episodes)}")
            
            if not episodes:
                logger.error(f"API未返回剧集数据，data: {json.dumps(data).decode('utf-8')[:500]}...")
                raise Exception("API未返回剧集数据")

            season_title = data.get('title', '未知课程')
            season_title = self._sanitize_filename(season_title)
            season_id = data.get('season_id', media_id)
            logger.info(f"课程标题：{season_title}")
            logger.info(f"课程season_id：{season_id}")

            cheese_episodes = []
            for idx, ep in enumerate(episodes, 1):
                ep_num = ep.get('index', idx)
                ep_index = f"第{ep_num}集"

                title = ep.get('title', f"第{ep_num}集")
                title = title.strip()
                if not title:
                    title = f"第{ep_num}集"

                status = ep.get('status', 1)  
                is_paid = status != 1

                cheese_episodes.append({
                "ep_id": ep.get('id', ''),
                "season_id": season_id,
                "bvid": str(ep.get('aid', '')),  
                "cid": ep.get('cid', ''),
                "ep_index": ep_index,
                "ep_title": self._sanitize_filename(title),
                "duration": ep.get('duration', 0),
                "duration_str": self._format_duration(ep.get('duration', 0)),
                "status": status,
                "kid": None
            })

            return {
                "success": True,
                "season_title": season_title,
                "season_id": season_id,
                "total_episodes": len(cheese_episodes),
                "episodes": cheese_episodes,
                "cover": data.get('cover', ''),
                "desc": data.get('desc', ''),
                "share_url": data.get('share_url', '')
            }
        except Exception as e:
            logger.error(f"获取课程信息失败：{str(e)}")
            raise Exception(f"课程信息获取失败：{str(e)}")

    def get_user_folders(self):
        try:
            logger.info("开始获取用户收藏夹列表...")
            
            if not self.cookies:
                raise Exception("请先登录")
            
            user_info = self.get_user_info()
            if not user_info.get('success'):
                error_msg = user_info.get('msg', '未知错误')
                logger.error(f"获取用户信息失败：{error_msg}")
                raise Exception(f"获取用户信息失败：{error_msg}")
            mid = user_info.get('mid')
            if not mid:
                raise Exception("无法获取用户ID，请重新登录")
            
            try:
                up_mid = int(mid)
            except ValueError:
                raise Exception("用户ID格式错误")
            
            url = "https://api.bilibili.com/x/v3/fav/folder/created/list-all"
            params = {
                'up_mid': up_mid,
                'platform': 'web'
            }
            
            success, api_data = self._api_request(url, timeout=15, use_wbi=True, params=params)
            
            if not success:
                logger.info("尝试不使用WBI签名获取收藏夹列表")
                success, api_data = self._api_request(url, timeout=15, use_wbi=False, params=params)
                if not success:
                    error_msg = api_data['error']
                    logger.error(f"API请求失败：{error_msg}")
                    raise Exception(f"获取收藏夹列表失败：{error_msg}")

            if api_data.get('code') != 0:
                error_msg = api_data.get('message', '未知错误')
                logger.error(f"API错误信息：{error_msg}")
                raise Exception(f"获取收藏夹列表失败：{error_msg}")

            data = api_data.get('data', {})
            folders = data.get('list', [])
            logger.info(f"获取到 {len(folders)} 个收藏夹")
            
            return folders
        except Exception as e:
            error_msg = str(e)
            # 避免错误信息重复
            if not error_msg.startswith("获取用户收藏夹失败：") and not error_msg.startswith("获取用户信息失败："):
                error_msg = f"获取用户收藏夹失败：{error_msg}"
            logger.error(error_msg)
            raise

    def get_folder_content(self, media_id, page=1, page_size=20, get_all=False):
        try:
            logger.info(f"开始获取收藏夹内容，media_id: {media_id}, page: {page}, page_size: {page_size}, get_all: {get_all}")
            
            if not self.cookies:
                raise Exception("请先登录")
            
            # 构建API参数，严格按照B站API文档
            base_params = {
                'media_id': media_id,
                'ps': min(page_size, 20),  # API限制ps最大为20
                'pn': page,
                'platform': 'web'
            }
            
            # 使用B站API文档指定的URL
            url = "https://api.bilibili.com/x/v3/fav/resource/list"
            
            # 先尝试使用WBI签名
            logger.info("尝试使用WBI签名获取收藏夹内容")
            success, api_data = self._api_request(url, timeout=15, use_wbi=True, params=base_params)
            
            if not success:
                # 如果失败，尝试不使用WBI签名
                logger.info("尝试不使用WBI签名获取收藏夹内容")
                success, api_data = self._api_request(url, timeout=15, use_wbi=False, params=base_params)
                if not success:
                    error_msg = api_data['error']
                    logger.error(f"API请求失败：{error_msg}")
                    raise Exception(f"获取收藏夹内容失败：{error_msg}")
            
            logger.info(f"解析后的响应数据：{api_data}")
            
            # 检查响应码
            code = api_data.get('code', 0)
            if code != 0:
                error_msg = api_data.get('message', '未知错误')
                raise Exception(f"获取收藏夹内容失败：{error_msg}（code={code}）")
            
            # 处理数据
            result_data = api_data.get('data', {})
            medias = result_data.get('medias', [])
            has_more = result_data.get('has_more', False)
            
            logger.info(f"获取到 {len(medias)} 个收藏内容")
            
            collection_items = []
            for item in medias:
                # 根据API文档，类型为2的是视频稿件
                if item.get('type') == 2:
                    collection_items.append({
                        'id': item.get('id'),
                        'type': 'video',
                        'title': item.get('title', '未知内容'),
                        'cover': item.get('cover'),
                        'bvid': item.get('bv_id') or item.get('bvid'),
                        'aid': item.get('id'),  # 视频ID就是aid
                        'up_name': item.get('upper', {}).get('name', '未知UP主'),
                        'duration': item.get('duration', 0),
                        'fav_time': item.get('fav_time', 0)
                    })
            
            logger.info(f"处理后收藏内容数量：{len(collection_items)}")
            for item in collection_items[:5]:  # 只打印前5个，避免日志过多
                logger.info(f"收藏内容：{item['title']} - BV号：{item['bvid']}")
            if len(collection_items) > 5:
                logger.info(f"... 还有 {len(collection_items) - 5} 个收藏内容")
            
            # 如果需要获取所有内容
            if get_all and has_more:
                all_items = collection_items.copy()
                current_page = page + 1
                
                while True:
                    params = {
                        'media_id': media_id,
                        'ps': 20,  # API限制最大为20
                        'pn': current_page,
                        'platform': 'web'
                    }
                    
                    logger.info(f"获取第{current_page}页收藏内容")
                    # 使用_api_request方法
                    success, data = self._api_request(url, timeout=15, use_wbi=True, params=params)
                    
                    if not success:
                        # 尝试不使用WBI签名
                        success, data = self._api_request(url, timeout=15, use_wbi=False, params=params)
                        if not success:
                            error_msg = data['error']
                            raise Exception(f"获取收藏夹内容失败：{error_msg}")
                    
                    if data.get('code') != 0:
                        error_msg = data.get('message', '未知错误')
                        raise Exception(f"获取收藏夹内容失败：{error_msg}（code={data.get('code')}）")
                    
                    page_data = data.get('data', {})
                    page_medias = page_data.get('medias', [])
                    has_more = page_data.get('has_more', False)
                    
                    logger.info(f"第{current_page}页获取到 {len(page_medias)} 个收藏内容")
                    
                    for item in page_medias:
                        if item.get('type') == 2:  # 只处理视频稿件
                            all_items.append({
                                'id': item.get('id'),
                                'type': 'video',
                                'title': item.get('title', '未知内容'),
                                'cover': item.get('cover'),
                                'bvid': item.get('bv_id') or item.get('bvid'),
                                'aid': item.get('id'),
                                'up_name': item.get('upper', {}).get('name', '未知UP主'),
                                'duration': item.get('duration', 0),
                                'fav_time': item.get('fav_time', 0)
                            })
                    
                    if not has_more:
                        break
                    
                    current_page += 1
                    # 避免请求过快被封
                    import time
                    time.sleep(0.5)
                
                logger.info(f"处理后收藏内容总数量：{len(all_items)}")
                return {
                    'items': all_items,
                    'has_more': False,
                    'total': len(all_items)
                }
            else:
                # 从API响应中获取真实的收藏夹内容数量
                total = result_data.get('info', {}).get('media_count', 0)
                logger.info(f"收藏夹总内容数量：{total}")
                return {
                    'items': collection_items,
                    'has_more': has_more,
                    'total': total
                }
        except Exception as e:
            error_msg = str(e)
            # 避免错误信息重复
            if not error_msg.startswith("获取收藏夹内容失败："):
                error_msg = f"获取收藏夹内容失败：{error_msg}"
            logger.error(error_msg)
            raise

    def _get_cid(self, media_type, media_id, page=1):
        try:
            if media_type == "video":
                
                url = self.config.get_api_url("cid_api").format(bvid=media_id)
                
                import urllib.parse
                url_parts = list(urllib.parse.urlparse(url))
                query = dict(urllib.parse.parse_qsl(url_parts[4]))
                success, data = self._api_request(url, timeout=10, use_wbi=True, params=query)
                if success and data.get('code') == 0:
                    
                    if 'data' in data:
                        pages_data = data['data']
                    elif 'result' in data:
                        pages_data = data['result']
                    else:
                        raise Exception(f"API返回格式错误，未找到data或result字段：{data}")
                    
                    if isinstance(pages_data, list):
                        if len(pages_data) >= page:
                            return str(pages_data[page - 1]['cid'])
                        else:
                            raise Exception(f"未找到第{page}集的CID")
                
                
                logger.warning("CID API失败，尝试使用视频信息API获取CID")
                video_info_url = self.config.get_api_url("video_info_api").format(bvid=media_id)
                
                url_parts = list(urllib.parse.urlparse(video_info_url))
                query = dict(urllib.parse.parse_qsl(url_parts[4]))
                success, data = self._api_request(video_info_url, timeout=10, use_wbi=True, params=query)
                if not success:
                    raise Exception(f"视频信息API获取失败：{data['error']}")
                
                if data.get('code') != 0:
                    raise Exception(f"视频信息API返回错误：{data.get('message', '未知错误')}")
                
                
                if 'data' in data:
                    video_data = data['data']
                elif 'result' in data:
                    video_data = data['result']
                else:
                    raise Exception(f"API返回格式错误，未找到data或result字段：{data}")
                
                
                if 'cid' in video_data:
                    return str(video_data['cid'])
                
                
                if 'pages' in video_data and isinstance(video_data['pages'], list):
                    if len(video_data['pages']) >= page:
                        return str(video_data['pages'][page - 1]['cid'])
                    else:
                        raise Exception(f"未找到第{page}集的CID")
                
                raise Exception("API未返回CID数据")
            elif media_type == "bangumi":
                bangumi_info = self._get_bangumi_full_info(media_id)
                if bangumi_info['episodes']:
                    return str(bangumi_info['episodes'][0]['cid'])
                raise Exception("未找到番剧CID")
            elif media_type == "cheese":
                # 对于课程视频，根据media_id类型使用不同的API
                # 尝试直接使用视频API获取CID
                try:
                    # 检查media_id是否为AV号
                    if media_id.startswith('av'):
                        aid = media_id[2:]
                        url = f"https://api.bilibili.com/x/player/pagelist?aid={aid}&jsonp=jsonp"
                    else:
                        # 尝试使用BV号
                        bvid = media_id
                        url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&jsonp=jsonp"
                    success, data = self._api_request(url, timeout=10, use_wbi=True)
                    if success and data.get('code') == 0:
                        pages = data.get('data', [])
                        if pages:
                            return str(pages[0]['cid'])
                except Exception as e:
                    logger.warning(f"直接获取CID失败：{str(e)}")
                # 尝试使用课程API
                cheese_info = self._get_cheese_full_info(media_id)
                if cheese_info['episodes']:
                    cid = cheese_info['episodes'][0]['cid']
                    if cid:
                        return str(cid)
                # 尝试使用视频信息API
                try:
                    # 检查media_id是否为AV号
                    if media_id.startswith('av'):
                        aid = media_id[2:]
                        url = f"https://api.bilibili.com/x/web-interface/view?aid={aid}&jsonp=jsonp"
                    else:
                        # 尝试使用BV号
                        bvid = media_id
                        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}&jsonp=jsonp"
                    success, data = self._api_request(url, timeout=10, use_wbi=True)
                    if success and data.get('code') == 0:
                        video_data = data.get('data', {})
                        if 'cid' in video_data:
                            return str(video_data['cid'])
                        elif 'pages' in video_data and video_data['pages']:
                            return str(video_data['pages'][0]['cid'])
                except Exception as e:
                    logger.warning(f"视频信息API获取CID失败：{str(e)}")
                raise Exception("未找到课程CID")
            else:
                raise Exception(f"不支持的媒体类型：{media_type}")
        except Exception as e:
            raise Exception(f"CID获取失败：{str(e)}（类型={media_type}, ID={media_id}）")

    def _get_collection_info(self, bvid):
        try:
            url = self.config.get_api_url("video_info_api").format(bvid=bvid)
            
            import urllib.parse
            url_parts = list(urllib.parse.urlparse(url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            success, data = self._api_request(url, timeout=10, use_wbi=True, params=query)
            if not success:
                raise Exception(f"获取合集信息失败：{data['error']}")
            if data.get('code') != 0:
                raise Exception(f"获取合集信息失败：{data.get('message', '未知错误')}")

            
            if 'data' in data:
                video_data = data['data']
            elif 'result' in data:
                video_data = data['result']
            else:
                raise Exception(f"API返回格式错误，未找到data或result字段：{data}")

            collection = []
            
            video_cover = video_data.get('pic', '')
            
            
            if 'ugc_season' in video_data:
                ugc_season = video_data['ugc_season']
                if 'sections' in ugc_season:
                    for section in ugc_season['sections']:
                        if 'episodes' in section:
                            for idx, ep in enumerate(section['episodes'], 1):
                                
                                page_info = None
                                if 'page' in ep:
                                    page_info = ep['page']
                                elif 'pages' in ep and ep['pages']:
                                    page_info = ep['pages'][0]
                                
                                if page_info:
                                    duration = page_info.get('duration', 0)
                                    collection.append({
                                        "page": idx,
                                        "cid": page_info.get('cid', 0),
                                        "bvid": ep.get('bvid', bvid),
                                        "title": self._sanitize_filename(ep.get('title', f"第{idx}集")),
                                        "duration": duration,
                                        "duration_str": self._format_duration(duration),
                                        "cover": video_cover  
                                    })
                            
                            break
            
            
            if not collection:
                pages = video_data.get('pages', [])
                for page in pages:
                    duration = page.get('duration', 0)
                    collection.append({
                        "page": page.get('page', 0),
                        "cid": page.get('cid', 0),
                        "title": self._sanitize_filename(page.get('part', f"第{page.get('page')}集")),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": video_cover  
                    })
            
            return collection
        except Exception as e:
            print(f"获取合集信息失败：{str(e)}（bvid={bvid}）")
            return []

    def _get_video_main_info(self, bvid):
        try:
            url = self.config.get_api_url("video_info_api").format(bvid=bvid)
            
            import urllib.parse
            url_parts = list(urllib.parse.urlparse(url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            success, data = self._api_request(url, timeout=10, use_wbi=True, params=query)
            if not success:
                raise Exception(f"视频信息获取失败：{data['error']}")
            if data.get('code') != 0:
                raise Exception(f"视频信息获取失败：{data.get('message', '未知错误')}")
            
            
            if 'data' in data:
                video_data = data['data']
            elif 'result' in data:
                video_data = data['result']
            else:
                raise Exception(f"API返回格式错误，未找到data或result字段：{data}")
            
            
            if 'View' in video_data:
                
                view_data = video_data['View']
                
                video_data.update(view_data)
            
            return video_data
        except Exception as e:
            raise Exception(f"视频主信息获取失败：{str(e)}（bvid={bvid}）")

    def _get_subtitle_info(self, bvid):
        try:
            url = self.config.get_api_url("video_info_api").format(bvid=bvid)
            
            import urllib.parse
            url_parts = list(urllib.parse.urlparse(url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            success, data = self._api_request(url, timeout=10, use_wbi=True, params=query)
            if not success:
                return {}
            if data.get('code') != 0:
                return {}
            
            if 'data' in data:
                video_data = data['data']
            elif 'result' in data:
                video_data = data['result']
            else:
                return {}
            
            if 'View' in video_data:
                view_data = video_data['View']
                video_data.update(view_data)
            
            subtitle_info = video_data.get('subtitle', {})
            logger.info(f"字幕信息完整数据：{subtitle_info}")
            
            if subtitle_info:
                subtitle_list = subtitle_info.get('list', [])
                logger.info(f"字幕列表完整数据：{subtitle_list}")
                if subtitle_list:
                    # 使用第一个字幕的id
                    first_subtitle = subtitle_list[0]
                    logger.info(f"第一个字幕完整数据：{first_subtitle}")
                    logger.info(f"第一个字幕所有字段：{list(first_subtitle.keys())}")
                    
                    # 检查字幕对象中是否有ai_subtitle字段或者其他字段包含完整的字幕ID
                    # 根据字幕api.txt，字幕ID应该是一个长十六进制字符串
                    subtitle_id = None
                    subtitle_url_from_list = None
                    
                    # 先检查是否有直接的subtitle_url字段
                    if 'subtitle_url' in first_subtitle and first_subtitle.get('subtitle_url'):
                        subtitle_url_from_list = first_subtitle.get('subtitle_url')
                        logger.info(f"找到字幕URL字段：{subtitle_url_from_list}")
                    
                    # 尝试查找可能包含字幕ID的字段
                    if 'ai_subtitle' in first_subtitle:
                        subtitle_id = first_subtitle.get('ai_subtitle')
                    elif 'id_str' in first_subtitle:
                        subtitle_id = first_subtitle.get('id_str')
                    elif 'oid' in first_subtitle:
                        subtitle_id = first_subtitle.get('oid')
                    elif 'id' in first_subtitle:
                        # 尝试使用id字段，但可能需要进一步处理
                        subtitle_id_num = first_subtitle.get('id')
                        if subtitle_id_num:
                            # 先尝试直接使用id的字符串形式
                            subtitle_id = str(subtitle_id_num)
                    
                    # 如果有直接的字幕URL，尝试从中提取字幕ID
                    if subtitle_url_from_list:
                        # 从URL中提取字幕ID
                        import re
                        match = re.search(r'/bfs/ai_subtitle/prod/([^/?]+)', subtitle_url_from_list)
                        if match:
                            subtitle_id = match.group(1)
                            logger.info(f"从URL中提取到字幕ID：{subtitle_id}")
                    
                    if subtitle_id:
                        logger.info(f"找到字幕ID：{subtitle_id}")
                        subtitle_url = f"https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/{subtitle_id}"
                        logger.info(f"字幕URL：{subtitle_url}")
                        return {
                            "subtitle_id": subtitle_id,
                            "subtitle_url": subtitle_url
                        }
            
            return {}
        except Exception as e:
            logger.error(f"获取字幕信息失败：{str(e)}（bvid={bvid}）")
            import traceback
            traceback.print_exc()
            return {}
            
    def _get_interact_video_info(self, bvid, graph_version, edge_id=0):
        try:
            url = f"https://api.bilibili.com/x/stein/edgeinfo_v2?bvid={bvid}&graph_version={graph_version}&edge_id={edge_id}"
            logger.debug(f"获取互动视频信息URL：{url}")
            success, data = self._api_request(url, timeout=15)
            if not success:
                raise Exception(f"互动视频API请求失败：{data['error']}")

            if data.get('code') != 0:
                raise Exception(f"互动视频API错误：{data.get('message', '未知错误')}")

            return data.get('data', {})
        except Exception as e:
            raise Exception(f"获取互动视频信息失败：{str(e)}")
            
    def force_get_interact_video_info(self, bvid):
        try:
            
            default_graph_versions = [1, 100, 1000, 5000, 10000, 155446, 200000, 250000, 300000, 350000, 400000, 450000, 500000]  
            
            for graph_version in default_graph_versions:
                try:
                    url = f"https://api.bilibili.com/x/stein/edgeinfo_v2?bvid={bvid}&graph_version={graph_version}&edge_id=0"
                    logger.debug(f"尝试获取互动视频信息：{url}")
                    success, data = self._api_request(url, timeout=15)
                    
                    if success and data.get('code') == 0:
                        interact_data = data.get('data', {})
                        if interact_data:
                            logger.debug(f"成功获取互动视频信息：{interact_data}")
                            return interact_data
                except Exception as e:
                    logger.debug(f"尝试graph_version={graph_version}失败：{str(e)}")
                    continue
            
            
            try:
                url = f"https://api.bilibili.com/x/stein/edgeinfo_v2?bvid={bvid}&edge_id=0"
                logger.debug(f"尝试获取互动视频信息（不指定graph_version）：{url}")
                success, data = self._api_request(url, timeout=15)
                
                if success and data.get('code') == 0:
                    interact_data = data.get('data', {})
                    if interact_data:
                        logger.debug(f"成功获取互动视频信息：{interact_data}")
                        return interact_data
            except Exception as e:
                logger.debug(f"尝试不指定graph_version失败：{str(e)}")
            
            return {}
        except Exception as e:
            logger.error(f"强制获取互动视频信息失败：{str(e)}")
            return {}

    def _get_play_info(self, media_type, bvid, cid, is_tv_mode, season_id=None, ep_id=None, audio_quality=None):
        try:
            # 如果cid为空，尝试获取cid
            if not cid:
                try:
                    cid = self._get_cid(media_type, bvid)
                    logger.info(f"自动获取CID成功：{cid}")
                except Exception as e:
                    logger.warning(f"获取CID失败：{str(e)}")
            
            
            
            
            # 使用fnval=4048获取最多画质选项（支持DASH、HEVC、4K等）
            fnval = 4048
            fnver = 0
            
            if media_type == "bangumi":
                # 番剧使用正确的API
                params = {
                    'cid': cid,
                    'bvid': bvid,
                    'qn': 112,  # 请求1080p+画质
                    'fnval': fnval,
                    'fnver': fnver,
                    'from_client': 'BROWSER',
                    'drm_tech_type': 2,
                    'otype': 'json'
                }
                play_url = "https://api.bilibili.com/pgc/player/web/playurl"
                logger.debug(f"获取番剧播放链接：{play_url}，参数：{params}")
            elif media_type == "cheese":
                params = {
                    'qn': 112,
                    'fnval': fnval,
                    'fnver': fnver,
                    'otype': 'json'
                }
                
                if cid:
                    params['cid'] = cid
                if ep_id:
                    params['ep_id'] = ep_id
                if bvid:
                    if bvid.startswith('av'):
                        params['avid'] = bvid[2:]
                    else:
                        params['bvid'] = bvid
                
                play_url = "https://api.bilibili.com/pugv/player/web/playurl"
                logger.debug(f"获取课程播放链接：{play_url}，参数：{params}")
            elif is_tv_mode:
                play_url = self.config.get_api_url("tv_play_url_api").format(cid=cid, bvid=bvid)
                logger.debug(f"获取TV模式播放链接：{play_url}")
            else:
                params = {
                    'cid': cid,
                    'bvid': bvid,
                    'qn': 112,
                    'fnval': fnval,
                    'fnver': fnver,
                    'otype': 'json'
                }
                play_url = "https://api.bilibili.com/x/player/playurl"
                logger.debug(f"获取普通视频播放链接：{play_url}，参数：{params}")

            if media_type == "bangumi":
                success, play_data = self._api_request(play_url, timeout=15, use_wbi=False, params=params)
                if not success or play_data.get('code') != 0:
                    logger.info("尝试使用WBI签名获取番剧播放信息")
                    success, play_data = self._api_request(play_url, timeout=15, use_wbi=True, params=params)
            elif media_type == "cheese":
                if season_id:
                    params['season_id'] = season_id
                params = {k: v for k, v in params.items() if v}
                success, play_data = self._api_request(play_url, timeout=15, use_wbi=False, params=params)
                if not success or play_data.get('code') != 0:
                    logger.info("尝试使用WBI签名获取课程播放信息")
                    success, play_data = self._api_request(play_url, timeout=15, use_wbi=True, params=params)
                if not success or play_data.get('code') != 0:
                    logger.info("尝试使用课程备用API")
                    cheese_api_url = "https://api.bilibili.com/pugv/player/web/playurl"
                    cheese_params = params.copy()
                    cheese_params['fourk'] = 1
                    success, play_data = self._api_request(cheese_api_url, timeout=15, use_wbi=True, params=cheese_params)
            elif is_tv_mode:
                success, play_data = self._api_request(play_url, timeout=15, use_wbi=False)
            else:
                success, play_data = self._api_request(play_url, timeout=15, use_wbi=True, params=params)
                if not success or play_data.get('code') != 0:
                    logger.info("尝试不使用WBI签名获取播放信息")
                    success, play_data = self._api_request(play_url, timeout=15, use_wbi=False, params=params)
            if not success:
                if "访问权限不足" in play_data['error']:
                    raise Exception("访问权限不足")
                elif "啥都木有" in play_data['error'] or "404" in play_data['error']:
                    raise Exception("视频不存在或已被删除")
                raise Exception(f"获取播放链接失败：{play_data['error']}")

            if play_data.get('code') != 0:
                error_msg = play_data.get('message', '权限不足')
                if play_data.get('code') == 403:
                    error_msg += "（可能是Cookie失效或无对应画质权限）"
                elif play_data.get('code') == -404 or "啥都木有" in error_msg:
                    error_msg = "视频不存在或已被删除"
                raise Exception(error_msg)

            qualities = []
            video_urls = {}
            audio_url = ""
            
            user_info = self.get_user_info()
            is_login = user_info.get('success', False)
            is_vip = user_info.get('is_vip', False)
            has_hevc = False
            quality_map = self.config.get_quality_map()
            
            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
            LOGIN_REQUIRED_QN = [64, 80]
            
            def is_quality_available(qn, is_login, is_vip):
                if qn in VIP_ONLY_QN:
                    return is_vip
                if qn in LOGIN_REQUIRED_QN:
                    return is_login
                return True

            data_source = play_data.get('data', play_data.get('result', {}))
            logger.debug(f"API返回数据结构：{list(data_source.keys())}")
            if 'dash' in data_source and 'video' in data_source['dash'] and data_source['dash']['video']:
                first_video = data_source['dash']['video'][0]
                logger.debug(f"第一个视频对象的键：{list(first_video.keys())}")
                if 'bilidrm_uri' in first_video:
                    logger.debug(f"bilidrm_uri: {first_video['bilidrm_uri']}")
                if 'uri' in first_video:
                    logger.debug(f"uri: {first_video['uri']}")
                if 'baseUrl' in first_video:
                    logger.debug(f"baseUrl前100字符：{first_video['baseUrl'][:100]}...")

            kid = None
            audio_urls = {}
            audio_qualities = []
            if 'dash' in data_source:
                logger.debug("使用DASH格式获取链接")
                if 'audio' in data_source['dash'] and data_source['dash']['audio']:
                    
                    for audio_item in data_source['dash']['audio']:
                        audio_id = audio_item.get('id', 0)
                        audio_url = ''
                        if audio_item.get('baseUrl'):
                            audio_url = audio_item.get('baseUrl').strip().strip('`')
                        elif audio_item.get('url'):
                            audio_url = audio_item.get('url').strip().strip('`')
                        elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                            audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                        
                        if audio_url:
                            audio_urls[audio_id] = audio_url
                            # 音频质量名称映射
                            if audio_id == 30216:
                                quality_name = "低音质 (64K)"
                            elif audio_id == 30232:
                                quality_name = "标准音质 (132K)"
                            elif audio_id == 30280:
                                quality_name = "高音质 (192K)"
                            elif audio_id == 30250:
                                quality_name = "杜比全景声"
                            elif audio_id == 30251:
                                quality_name = "Hi-Res无损"
                            elif audio_id == 100010:
                                quality_name = "高音质 (320K)"
                            elif audio_id == 100009:
                                quality_name = "标准音质 (192K)"
                            elif audio_id == 100008:
                                quality_name = "低音质 (128K)"
                            else:
                                quality_name = f"未知音质 ({audio_id})"
                            audio_qualities.append((audio_id, quality_name))
                            logger.debug(f"获取音频链接 ID={audio_id}: {audio_url[:50]}...")
                    
                    # 根据用户选择的音频质量返回对应的音频URL
                    if audio_qualities:
                        # 按音质优先级排序（从高到低）
                        audio_quality_priority = [30251, 30250, 100010, 30280, 100009, 30232, 100008, 30216]
                        sorted_audio_qualities = sorted(audio_qualities, key=lambda x: audio_quality_priority.index(x[0]) if x[0] in audio_quality_priority else 999)
                        
                        if audio_quality and audio_quality in audio_urls:
                            audio_url = audio_urls[audio_quality]
                            logger.info(f"使用用户选择的音频质量：{audio_quality}")
                        else:
                            # 使用最高可用的音频质量
                            highest_quality = sorted_audio_qualities[0][0]
                            audio_url = audio_urls[highest_quality]
                            logger.info(f"使用最高可用的音频质量：{highest_quality}")

                if 'video' in data_source['dash']:
                    for video in data_source['dash']['video']:
                        qn = video.get('id', 0)
                        quality_name = quality_map.get(qn, f"未知画质({qn})")

                        
                        if media_type == "bangumi" or media_type == "cheese":
                            
                            if qn == 74:
                                quality_name = "720P60 高帧率"
                            elif qn == 100:
                                quality_name = "智能修复"
                            elif qn == 116:
                                quality_name = "1080P60 高帧率"
                            elif qn == 126:
                                quality_name = "杜比视界"

                        if qn in [125, 127]:
                            has_hevc = True
                            quality_name += " (HEVC)"

                        if not is_quality_available(qn, is_login, is_vip):
                            continue

                        
                        video_url = ''
                        if video.get('baseUrl'):
                            video_url = video.get('baseUrl').strip().strip('`')
                        elif video.get('url'):
                            video_url = video.get('url').strip().strip('`')
                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                            video_url = video.get('backup_url')[0].strip().strip('`')
                        
                        if video_url:
                            video_urls[qn] = video_url
                            qualities.append((qn, quality_name))
                            logger.debug(f"获取视频链接 QN={qn}: {video_url[:50]}...")
                            
                            if not kid:
                                # 生成缓存键
                                cache_key = f"{bvid}_{cid}"
                                
                                # 检查缓存
                                if cache_key in KID_CACHE:
                                    cached_kid, timestamp = KID_CACHE[cache_key]
                                    if time.time() - timestamp < KID_CACHE_EXPIRY:
                                        kid = cached_kid
                                        logger.info(f"从缓存中获取KID：{kid}")
                                    else:
                                        del KID_CACHE[cache_key]
                                
                                if not kid:
                                    if 'bilidrm_uri' in video:
                                        uri = video['bilidrm_uri']
                                        kid_match = KID_REGEX['bilidrm_uri'].search(uri)
                                        if kid_match:
                                            kid = kid_match.group(1)
                                            logger.info(f"从API返回的bilidrm_uri中提取到KID：{kid}")
                                    elif 'uri' in video:
                                        uri = video['uri']
                                        kid_match = KID_REGEX['bilidrm_uri'].search(uri)
                                        if kid_match:
                                            kid = kid_match.group(1)
                                            logger.info(f"从API返回的URI中提取到KID：{kid}")
                                    elif 'baseUrl' in video:
                                        base_url = video['baseUrl']
                                        kid_match = KID_REGEX['url_param'].search(base_url)
                                        if kid_match:
                                            kid = kid_match.group(1)
                                            logger.info(f"从URL参数中提取到KID：{kid}")
                                    elif 'base_url' in video:
                                        base_url = video['base_url']
                                        kid_match = KID_REGEX['url_param'].search(base_url)
                                        if kid_match:
                                            kid = kid_match.group(1)
                                            logger.info(f"从base_url参数中提取到KID：{kid}")
                                    
                                    # 缓存KID
                                    if kid:
                                        KID_CACHE[cache_key] = (kid, time.time())
                                        # 清理过期缓存
                                        current_time = time.time()
                                        expired_keys = [k for k, (_, ts) in KID_CACHE.items() 
                                                      if current_time - ts >= KID_CACHE_EXPIRY]
                                        for k in expired_keys:
                                            del KID_CACHE[k]

            elif 'durl' in data_source:
                logger.debug("使用DURL格式获取链接")
                current_qn = data_source.get('quality', 0)
                accept_quality = data_source.get('accept_quality', [current_qn])
                
                if data_source['durl']:
                    # 检查是否有多个分段
                    if len(data_source['durl']) > 1:
                        # 多分段下载
                        video_urls_list = []
                        for durl_item in data_source['durl']:
                            video_urls_list.append(durl_item['url'])
                        video_url = video_urls_list
                        logger.debug(f"获取多分段视频链接，共{len(video_urls_list)}个分段")
                    else:
                        # 单分段下载
                        video_url = data_source['durl'][0]['url']
                        logger.debug(f"获取视频链接：{video_url[:50]}...")
                    
                    # 提取KID（DURL格式）
                    if not kid:
                        # 生成缓存键
                        cache_key = f"{bvid}_{cid}"
                        
                        # 检查缓存
                        if cache_key in KID_CACHE:
                            cached_kid, timestamp = KID_CACHE[cache_key]
                            if time.time() - timestamp < KID_CACHE_EXPIRY:
                                kid = cached_kid
                                logger.info(f"从缓存中获取KID：{kid}")
                            else:
                                del KID_CACHE[cache_key]
                        
                        if not kid:
                            # 从DURL链接中提取KID（使用第一个分段的URL）
                            first_url = video_url[0] if isinstance(video_url, list) else video_url
                            kid_match = KID_REGEX['url_param'].search(first_url)
                            if kid_match:
                                kid = kid_match.group(1)
                                logger.info(f"从DURL链接中提取到KID：{kid}")
                                
                                # 缓存KID
                                KID_CACHE[cache_key] = (kid, time.time())
                                # 清理过期缓存
                                current_time = time.time()
                                expired_keys = [k for k, (_, ts) in KID_CACHE.items() 
                                              if current_time - ts >= KID_CACHE_EXPIRY]
                                for k in expired_keys:
                                    del KID_CACHE[k]
                    
                    for qn in accept_quality:
                        qn = int(qn)
                        quality_name = quality_map.get(qn, f"未知画质({qn})")

                        
                        if media_type == "bangumi" or media_type == "cheese":
                            
                            if qn == 74:
                                quality_name = "720P60 高帧率"
                            elif qn == 100:
                                quality_name = "智能修复"
                            elif qn == 116:
                                quality_name = "1080P60 高帧率"
                            elif qn == 126:
                                quality_name = "杜比视界"

                        if qn in [125, 127]:
                            has_hevc = True
                            quality_name += " (HEVC)"

                        if not is_quality_available(qn, is_login, is_vip):
                            continue

                        video_urls[qn] = video_url
                        qualities.append((qn, quality_name))

            else:
                logger.error("API返回数据中未找到dash或durl字段")
                raise Exception("API返回格式错误，未找到播放链接数据")

            if not video_urls:
                logger.error("未获取到任何视频链接")
                raise Exception("未获取到视频播放链接")

            qualities = list(dict.fromkeys(qualities))
            qualities.sort(key=lambda x: x[0], reverse=True)

            return {
                "success": True,
                "qualities": qualities,
                "video_urls": video_urls,
                "audio_url": audio_url,
                "audio_qualities": audio_qualities,
                "audio_urls": audio_urls,
                "is_vip": is_vip,
                "has_hevc": has_hevc,
                "kid": kid
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"获取播放信息失败：{error_msg}")
            
            # 尝试将cheese视频当作普通视频处理
            if media_type == "cheese" and bvid and cid:
                logger.info("尝试将cheese视频当作普通视频处理（异常处理中）")
                try:
                    normal_play_url = "https://api.bilibili.com/x/player/playurl"
                    simple_params = {
                        'cid': cid,
                        'bvid': bvid,
                        'fnval': 80,
                        'otype': 'json'
                    }
                    success, play_data = self._api_request(normal_play_url, timeout=15, use_wbi=False, params=simple_params)
                    if success and play_data.get('code') == 0:
                        logger.info("成功将cheese视频当作普通视频处理")
                        data_source = play_data.get('data', play_data.get('result', {}))
                        qualities = []
                        video_urls = {}
                        audio_url = ""
                        user_info = self.get_user_info()
                        is_login = user_info.get('success', False)
                        is_vip = user_info.get('is_vip', False)
                        has_hevc = False
                        quality_map = self.config.get_quality_map()
                        
                        VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                        LOGIN_REQUIRED_QN = [64, 80]
                        
                        def is_quality_available(qn, is_login, is_vip):
                            if qn in VIP_ONLY_QN:
                                return is_vip
                            if qn in LOGIN_REQUIRED_QN:
                                return is_login
                            return True
                        
                        kid = None
                        if 'dash' in data_source:
                            if data_source['dash'].get('video'):
                                for video in data_source['dash']['video']:
                                    qn = video.get('id', 0)
                                    quality_name = quality_map.get(qn, f"未知画质({qn})")
                                    if qn in [125, 127]:
                                        has_hevc = True
                                        quality_name += " (HEVC)"
                                    if not is_quality_available(qn, is_login, is_vip):
                                        continue
                                    video_url = ''
                                    if video.get('baseUrl'):
                                        video_url = video.get('baseUrl').strip().strip('`')
                                    elif video.get('url'):
                                        video_url = video.get('url').strip().strip('`')
                                    elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                        video_url = video.get('backup_url')[0].strip().strip('`')
                                    if video_url:
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            if data_source['dash'].get('audio'):
                                audio_item = data_source['dash']['audio'][0]
                                if audio_item.get('baseUrl'):
                                    audio_url = audio_item.get('baseUrl').strip().strip('`')
                                elif audio_item.get('url'):
                                    audio_url = audio_item.get('url').strip().strip('`')
                                elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                    audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                        elif 'durl' in data_source:
                            if data_source['durl']:
                                video_url = data_source['durl'][0]['url']
                                current_qn = data_source.get('quality', 0)
                                accept_quality = data_source.get('accept_quality', [current_qn])
                                for qn in accept_quality:
                                    qn = int(qn)
                                    quality_name = quality_map.get(qn, f"未知画质({qn})")
                                    if qn in [125, 127]:
                                        has_hevc = True
                                        quality_name += " (HEVC)"
                                    if not is_quality_available(qn, is_login, is_vip):
                                        continue
                                    video_urls[qn] = video_url
                                    qualities.append((qn, quality_name))
                        
                        if video_urls:
                            qualities = list(dict.fromkeys(qualities))
                            qualities.sort(key=lambda x: x[0], reverse=True)
                            return {
                                "success": True,
                                "qualities": qualities,
                                "video_urls": video_urls,
                                "audio_url": audio_url,
                                "audio_qualities": audio_qualities,
                                "audio_urls": audio_urls,
                                "is_vip": is_vip,
                                "has_hevc": has_hevc,
                                "kid": kid
                            }
                except Exception as e2:
                    logger.warning(f"将cheese视频当作普通视频处理失败：{str(e2)}")
            
            if "任务信息不存在" in error_msg and (media_type == "bangumi" or media_type == "cheese"):
                
                try:
                    if ep_id:
                        
                        if media_type == "cheese":
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&qn=80&fnval=112&fourk=1&otype=json"
                        else:
                            play_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&qn=80&fnval=112&fnver=0&fourk=1&from_client=BROWSER&drm_tech_type=2&otype=json"
                        logger.info(f"尝试备用链接（仅ep_id）：{play_url}")
                        
                        
                        if 'Referer' not in self.session.headers:
                            self.session.headers.update({'Referer': 'https://www.bilibili.com'})
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                            LOGIN_REQUIRED_QN = [64, 80]
                            
                            def is_quality_available(qn, is_login, is_vip):
                                if qn in VIP_ONLY_QN:
                                    return is_vip
                                if qn in LOGIN_REQUIRED_QN:
                                    return is_login
                                return True
                            
                            kid = None
                            if 'dash' in data_source:
                                if data_source['dash'].get('video'):
                                    for video in data_source['dash']['video']:
                                        qn = video.get('id', 0)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_url = ''
                                        if video.get('baseUrl'):
                                            video_url = video.get('baseUrl').strip().strip('`')
                                        elif video.get('url'):
                                            video_url = video.get('url').strip().strip('`')
                                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                            video_url = video.get('backup_url')[0].strip().strip('`')
                                        if video_url:
                                            video_urls[qn] = video_url
                                            qualities.append((qn, quality_name))
                                            
                                            if not kid:
                                                import re
                                                if 'bilidrm_uri' in video:
                                                        uri = video['bilidrm_uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的bilidrm_uri中提取到KID：{kid}")
                                                elif 'uri' in video:
                                                        uri = video['uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的URI中提取到KID：{kid}")
                                                elif 'baseUrl' in video:
                                                    base_url = video['baseUrl']
                                                    kid_match = re.search(r'kid=([0-9a-fA-F]{32})', base_url)
                                                    if kid_match:
                                                        kid = kid_match.group(1)
                                                        logger.info(f"从备用链接URL参数中提取到KID：{kid}")
                                if data_source['dash'].get('audio'):
                                    audio_item = data_source['dash']['audio'][0]
                                    if audio_item.get('baseUrl'):
                                        audio_url = audio_item.get('baseUrl').strip().strip('`')
                                    elif audio_item.get('url'):
                                        audio_url = audio_item.get('url').strip().strip('`')
                                    elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                        audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                            elif 'durl' in data_source:
                                if data_source['durl']:
                                    video_url = data_source['durl'][0]['url']
                                    current_qn = data_source.get('quality', 0)
                                    accept_quality = data_source.get('accept_quality', [current_qn])
                                    for qn in accept_quality:
                                        qn = int(qn)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            
                            if video_urls:
                                qualities = list(dict.fromkeys(qualities))
                                qualities.sort(key=lambda x: x[0], reverse=True)
                                logger.info(f"备用链接获取成功：视频URL数量={len(video_urls)}, 音频URL长度={len(audio_url)}")
                                return {
                                    "success": True,
                                    "qualities": qualities,
                                    "video_urls": video_urls,
                                    "audio_url": audio_url,
                                    "audio_qualities": audio_qualities,
                                    "audio_urls": audio_urls,
                                    "is_vip": is_vip,
                                    "has_hevc": has_hevc,
                                    "kid": kid
                                }
                    
                    
                    if bvid and cid:
                        if media_type == "cheese":
                            if bvid.startswith('BV'):
                                play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&bvid={bvid}&qn=80&fnval=112&fourk=1&otype=json"
                            else:
                                play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&avid={bvid}&qn=80&fnval=112&fourk=1&otype=json"
                        else:
                            play_url = f"https://api.bilibili.com/pgc/player/web/playurl?cid={cid}&bvid={bvid}&qn=80&fnval=112&fnver=0&fourk=1&from_client=BROWSER&drm_tech_type=2&otype=json"
                        logger.info(f"尝试备用链接（cid+bvid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                            LOGIN_REQUIRED_QN = [64, 80]
                            
                            def is_quality_available(qn, is_login, is_vip):
                                if qn in VIP_ONLY_QN:
                                    return is_vip
                                if qn in LOGIN_REQUIRED_QN:
                                    return is_login
                                return True
                            
                            kid = None
                            if 'dash' in data_source:
                                if data_source['dash'].get('video'):
                                    for video in data_source['dash']['video']:
                                        qn = video.get('id', 0)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_url = ''
                                        if video.get('baseUrl'):
                                            video_url = video.get('baseUrl').strip().strip('`')
                                        elif video.get('url'):
                                            video_url = video.get('url').strip().strip('`')
                                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                            video_url = video.get('backup_url')[0].strip().strip('`')
                                        if video_url:
                                            video_urls[qn] = video_url
                                            qualities.append((qn, quality_name))
                                            
                                            if not kid:
                                                import re
                                                if 'bilidrm_uri' in video:
                                                        uri = video['bilidrm_uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的bilidrm_uri中提取到KID：{kid}")
                                                elif 'uri' in video:
                                                        uri = video['uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的URI中提取到KID：{kid}")
                                                elif 'baseUrl' in video:
                                                    base_url = video['baseUrl']
                                                    kid_match = re.search(r'kid=([0-9a-fA-F]{32})', base_url)
                                                    if kid_match:
                                                        kid = kid_match.group(1)
                                                        logger.info(f"从备用链接URL参数中提取到KID：{kid}")
                                if data_source['dash'].get('audio'):
                                    audio_item = data_source['dash']['audio'][0]
                                    if audio_item.get('baseUrl'):
                                        audio_url = audio_item.get('baseUrl').strip().strip('`')
                                    elif audio_item.get('url'):
                                        audio_url = audio_item.get('url').strip().strip('`')
                                    elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                        audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                            elif 'durl' in data_source:
                                if data_source['durl']:
                                    video_url = data_source['durl'][0]['url']
                                    current_qn = data_source.get('quality', 0)
                                    accept_quality = data_source.get('accept_quality', [current_qn])
                                    for qn in accept_quality:
                                        qn = int(qn)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            
                            if video_urls:
                                qualities = list(dict.fromkeys(qualities))
                                qualities.sort(key=lambda x: x[0], reverse=True)
                                logger.info(f"备用链接获取成功：视频URL数量={len(video_urls)}, 音频URL长度={len(audio_url)}")
                                return {
                                    "success": True,
                                    "qualities": qualities,
                                    "video_urls": video_urls,
                                    "audio_url": audio_url,
                                    "audio_qualities": audio_qualities,
                                    "audio_urls": audio_urls,
                                    "is_vip": is_vip,
                                    "has_hevc": has_hevc,
                                    "kid": kid
                                }
                    
                    
                    if ep_id and cid:
                        if media_type == "cheese":
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=80&fnval=112&fourk=1&otype=json"
                        else:
                            play_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=80&fnval=112&fnver=0&fourk=1&from_client=BROWSER&drm_tech_type=2&otype=json"
                        logger.info(f"尝试备用链接（ep_id+cid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                            LOGIN_REQUIRED_QN = [64, 80]
                            
                            def is_quality_available(qn, is_login, is_vip):
                                if qn in VIP_ONLY_QN:
                                    return is_vip
                                if qn in LOGIN_REQUIRED_QN:
                                    return is_login
                                return True
                            
                            kid = None
                            if 'dash' in data_source:
                                if data_source['dash'].get('video'):
                                    for video in data_source['dash']['video']:
                                        qn = video.get('id', 0)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_url = ''
                                        if video.get('baseUrl'):
                                            video_url = video.get('baseUrl').strip().strip('`')
                                        elif video.get('url'):
                                            video_url = video.get('url').strip().strip('`')
                                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                            video_url = video.get('backup_url')[0].strip().strip('`')
                                        if video_url:
                                            video_urls[qn] = video_url
                                            qualities.append((qn, quality_name))
                                            
                                            if not kid:
                                                import re
                                                if 'bilidrm_uri' in video:
                                                        uri = video['bilidrm_uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的bilidrm_uri中提取到KID：{kid}")
                                                elif 'uri' in video:
                                                        uri = video['uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的URI中提取到KID：{kid}")
                                                elif 'baseUrl' in video:
                                                    base_url = video['baseUrl']
                                                    kid_match = re.search(r'kid=([0-9a-fA-F]{32})', base_url)
                                                    if kid_match:
                                                        kid = kid_match.group(1)
                                                        logger.info(f"从备用链接URL参数中提取到KID：{kid}")
                                if data_source['dash'].get('audio'):
                                    audio_item = data_source['dash']['audio'][0]
                                    if audio_item.get('baseUrl'):
                                        audio_url = audio_item.get('baseUrl').strip().strip('`')
                                    elif audio_item.get('url'):
                                        audio_url = audio_item.get('url').strip().strip('`')
                                    elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                        audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                            elif 'durl' in data_source:
                                if data_source['durl']:
                                    video_url = data_source['durl'][0]['url']
                                    current_qn = data_source.get('quality', 0)
                                    accept_quality = data_source.get('accept_quality', [current_qn])
                                    for qn in accept_quality:
                                        qn = int(qn)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            
                            if video_urls:
                                qualities = list(dict.fromkeys(qualities))
                                qualities.sort(key=lambda x: x[0], reverse=True)
                                logger.info(f"备用链接获取成功：视频URL数量={len(video_urls)}, 音频URL长度={len(audio_url)}")
                                return {
                                    "success": True,
                                    "qualities": qualities,
                                    "video_urls": video_urls,
                                    "audio_url": audio_url,
                                    "audio_qualities": audio_qualities,
                                    "audio_urls": audio_urls,
                                    "is_vip": is_vip,
                                    "has_hevc": has_hevc,
                                    "kid": kid
                                }
                except Exception as backup_e:
                    logger.error(f"备用链接尝试失败：{str(backup_e)}")
            
            elif media_type == "cheese":
                
                try:
                    if ep_id:
                        
                        play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&qn=80&fnval=112&fourk=1&otype=json"
                        logger.info(f"尝试备用链接（仅ep_id）：{play_url}")
                        
                        
                        if 'Referer' not in self.session.headers:
                            self.session.headers.update({'Referer': 'https://www.bilibili.com'})
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                            LOGIN_REQUIRED_QN = [64, 80]
                            
                            def is_quality_available(qn, is_login, is_vip):
                                if qn in VIP_ONLY_QN:
                                    return is_vip
                                if qn in LOGIN_REQUIRED_QN:
                                    return is_login
                                return True
                            
                            kid = None
                            if 'dash' in data_source:
                                if data_source['dash'].get('video'):
                                    for video in data_source['dash']['video']:
                                        qn = video.get('id', 0)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_url = ''
                                        if video.get('baseUrl'):
                                            video_url = video.get('baseUrl').strip().strip('`')
                                        elif video.get('url'):
                                            video_url = video.get('url').strip().strip('`')
                                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                            video_url = video.get('backup_url')[0].strip().strip('`')
                                        if video_url:
                                            video_urls[qn] = video_url
                                            qualities.append((qn, quality_name))
                                            
                                            if not kid:
                                                import re
                                                if 'bilidrm_uri' in video:
                                                        uri = video['bilidrm_uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的bilidrm_uri中提取到KID：{kid}")
                                                elif 'uri' in video:
                                                        uri = video['uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的URI中提取到KID：{kid}")
                                                elif 'baseUrl' in video:
                                                    base_url = video['baseUrl']
                                                    kid_match = re.search(r'kid=([0-9a-fA-F]{32})', base_url)
                                                    if kid_match:
                                                        kid = kid_match.group(1)
                                                        logger.info(f"从备用链接URL参数中提取到KID：{kid}")
                                if data_source['dash'].get('audio'):
                                    audio_item = data_source['dash']['audio'][0]
                                    if audio_item.get('baseUrl'):
                                        audio_url = audio_item.get('baseUrl').strip().strip('`')
                                    elif audio_item.get('url'):
                                        audio_url = audio_item.get('url').strip().strip('`')
                                    elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                        audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                            elif 'durl' in data_source:
                                if data_source['durl']:
                                    video_url = data_source['durl'][0]['url']
                                    current_qn = data_source.get('quality', 0)
                                    accept_quality = data_source.get('accept_quality', [current_qn])
                                    for qn in accept_quality:
                                        qn = int(qn)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            
                            if video_urls:
                                qualities = list(dict.fromkeys(qualities))
                                qualities.sort(key=lambda x: x[0], reverse=True)
                                logger.info(f"备用链接获取成功：视频URL数量={len(video_urls)}, 音频URL长度={len(audio_url)}")
                                return {
                                    "success": True,
                                    "qualities": qualities,
                                    "video_urls": video_urls,
                                    "audio_url": audio_url,
                                    "audio_qualities": audio_qualities,
                                    "audio_urls": audio_urls,
                                    "is_vip": is_vip,
                                    "has_hevc": has_hevc,
                                    "kid": kid
                                }
                    
                    
                    if bvid and cid:
                        if not bvid.startswith('av'):
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&bvid={bvid}&qn=80&fnval=112&fourk=1&otype=json"
                            logger.info(f"尝试备用链接（cid+bvid）：{play_url}")
                        else:
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&avid={bvid[2:]}&qn=80&fnval=112&fourk=1&otype=json"
                            logger.info(f"尝试备用链接（cid+avid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                            LOGIN_REQUIRED_QN = [64, 80]
                            
                            def is_quality_available(qn, is_login, is_vip):
                                if qn in VIP_ONLY_QN:
                                    return is_vip
                                if qn in LOGIN_REQUIRED_QN:
                                    return is_login
                                return True
                            
                            kid = None
                            if 'dash' in data_source:
                                if data_source['dash'].get('video'):
                                    for video in data_source['dash']['video']:
                                        qn = video.get('id', 0)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_url = ''
                                        if video.get('baseUrl'):
                                            video_url = video.get('baseUrl').strip().strip('`')
                                        elif video.get('url'):
                                            video_url = video.get('url').strip().strip('`')
                                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                            video_url = video.get('backup_url')[0].strip().strip('`')
                                        if video_url:
                                            video_urls[qn] = video_url
                                            qualities.append((qn, quality_name))
                                            
                                            if not kid:
                                                import re
                                                if 'bilidrm_uri' in video:
                                                        uri = video['bilidrm_uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的bilidrm_uri中提取到KID：{kid}")
                                                elif 'uri' in video:
                                                        uri = video['uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的URI中提取到KID：{kid}")
                                                elif 'baseUrl' in video:
                                                    base_url = video['baseUrl']
                                                    kid_match = re.search(r'kid=([0-9a-fA-F]{32})', base_url)
                                                    if kid_match:
                                                        kid = kid_match.group(1)
                                                        logger.info(f"从备用链接URL参数中提取到KID：{kid}")
                                if data_source['dash'].get('audio'):
                                    audio_item = data_source['dash']['audio'][0]
                                    if audio_item.get('baseUrl'):
                                        audio_url = audio_item.get('baseUrl').strip().strip('`')
                                    elif audio_item.get('url'):
                                        audio_url = audio_item.get('url').strip().strip('`')
                                    elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                        audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                            elif 'durl' in data_source:
                                if data_source['durl']:
                                    video_url = data_source['durl'][0]['url']
                                    current_qn = data_source.get('quality', 0)
                                    accept_quality = data_source.get('accept_quality', [current_qn])
                                    for qn in accept_quality:
                                        qn = int(qn)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            
                            if video_urls:
                                qualities = list(dict.fromkeys(qualities))
                                qualities.sort(key=lambda x: x[0], reverse=True)
                                logger.info(f"备用链接获取成功：视频URL数量={len(video_urls)}, 音频URL长度={len(audio_url)}")
                                return {
                                    "success": True,
                                    "qualities": qualities,
                                    "video_urls": video_urls,
                                    "audio_url": audio_url,
                                    "audio_qualities": audio_qualities,
                                    "audio_urls": audio_urls,
                                    "is_vip": is_vip,
                                    "has_hevc": has_hevc,
                                    "kid": kid
                                }
                    
                    
                    if ep_id and cid:
                        play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=80&fnval=112&fourk=1&otype=json"
                        logger.info(f"尝试备用链接（ep_id+cid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 120, 125, 126, 127]
                            LOGIN_REQUIRED_QN = [64, 80]
                            
                            def is_quality_available(qn, is_login, is_vip):
                                if qn in VIP_ONLY_QN:
                                    return is_vip
                                if qn in LOGIN_REQUIRED_QN:
                                    return is_login
                                return True
                            
                            kid = None
                            if 'dash' in data_source:
                                if data_source['dash'].get('video'):
                                    for video in data_source['dash']['video']:
                                        qn = video.get('id', 0)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_url = ''
                                        if video.get('baseUrl'):
                                            video_url = video.get('baseUrl').strip().strip('`')
                                        elif video.get('url'):
                                            video_url = video.get('url').strip().strip('`')
                                        elif video.get('backup_url') and isinstance(video.get('backup_url'), list) and len(video.get('backup_url')) > 0:
                                            video_url = video.get('backup_url')[0].strip().strip('`')
                                        if video_url:
                                            video_urls[qn] = video_url
                                            qualities.append((qn, quality_name))
                                            
                                            if not kid:
                                                import re
                                                if 'bilidrm_uri' in video:
                                                        uri = video['bilidrm_uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的bilidrm_uri中提取到KID：{kid}")
                                                elif 'uri' in video:
                                                        uri = video['uri']
                                                        kid_match = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
                                                        if kid_match:
                                                            kid = kid_match.group(1)
                                                            logger.info(f"从备用链接API返回的URI中提取到KID：{kid}")
                                                elif 'baseUrl' in video:
                                                    base_url = video['baseUrl']
                                                    kid_match = re.search(r'kid=([0-9a-fA-F]{32})', base_url)
                                                    if kid_match:
                                                        kid = kid_match.group(1)
                                                        logger.info(f"从备用链接URL参数中提取到KID：{kid}")
                                if data_source['dash'].get('audio'):
                                    audio_item = data_source['dash']['audio'][0]
                                    if audio_item.get('baseUrl'):
                                        audio_url = audio_item.get('baseUrl').strip().strip('`')
                                    elif audio_item.get('url'):
                                        audio_url = audio_item.get('url').strip().strip('`')
                                    elif audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list) and len(audio_item.get('backup_url')) > 0:
                                        audio_url = audio_item.get('backup_url')[0].strip().strip('`')
                            elif 'durl' in data_source:
                                if data_source['durl']:
                                    video_url = data_source['durl'][0]['url']
                                    current_qn = data_source.get('quality', 0)
                                    accept_quality = data_source.get('accept_quality', [current_qn])
                                    for qn in accept_quality:
                                        qn = int(qn)
                                        quality_name = quality_map.get(qn, f"未知画质({qn})")
                                        if qn == 74:
                                            quality_name = "720P60 高帧率"
                                        elif qn == 100:
                                            quality_name = "智能修复"
                                        elif qn == 116:
                                            quality_name = "1080P60 高帧率"
                                        elif qn == 126:
                                            quality_name = "杜比视界"
                                        if qn in [125, 127]:
                                            has_hevc = True
                                            quality_name += " (HEVC)"
                                        if not is_quality_available(qn, is_login, is_vip):
                                            continue
                                        video_urls[qn] = video_url
                                        qualities.append((qn, quality_name))
                            
                            if video_urls:
                                qualities = list(dict.fromkeys(qualities))
                                qualities.sort(key=lambda x: x[0], reverse=True)
                                logger.info(f"备用链接获取成功：视频URL数量={len(video_urls)}, 音频URL长度={len(audio_url)}")
                                return {
                                    "success": True,
                                    "qualities": qualities,
                                    "video_urls": video_urls,
                                    "audio_url": audio_url,
                                    "audio_qualities": audio_qualities,
                                    "audio_urls": audio_urls,
                                    "is_vip": is_vip,
                                    "has_hevc": has_hevc,
                                    "kid": kid
                                }
                except Exception as backup_e:
                    logger.error(f"备用链接尝试失败：{str(backup_e)}")
            
            return {"success": False, "error": error_msg}

    def get_single_episode_info(self, media_type, media_id, page=1, is_tv_mode=False):
        try:
            bvid = media_id if media_type == "video" else None
            cid = None

            if media_type == "video":
                if not bvid:
                    raise Exception("视频ID（BV号）为空")
                collection = self._get_collection_info(bvid)
                
                ep_info = next((item for item in collection if item['page'] == page), None)
                if not ep_info:
                    raise Exception(f"未找到第{page}集")
                
                ep_title = ep_info['title']
                
                if 'bvid' in ep_info and ep_info['bvid'] != bvid:
                    bvid = ep_info['bvid']
                    cid = ep_info.get('cid', '')
                elif not cid:
                    cid = self._get_cid(media_type, bvid, page)
                
                main_title = self._get_video_main_info(bvid)['title']
                full_title = f"{main_title}_{ep_title}"

            elif media_type == "bangumi":
                return {"success": False, "error": "番剧单集信息请通过get_bangumi_episode_playinfo获取"}
            elif media_type == "cheese":
                return {"success": False, "error": "课程单集信息请通过parse_media获取"}
            else:
                return {"success": False, "error": f"不支持的媒体类型：{media_type}"}

            play_info = self._get_play_info(media_type, bvid, cid, is_tv_mode)
            if not play_info['success']:
                raise Exception(play_info['error'])

            return {
                "success": True,
                "type": media_type,
                "title": self._sanitize_filename(full_title),
                "bvid": bvid,
                "cid": cid,
                "page": page,
                "qualities": play_info['qualities'],
                "video_urls": play_info['video_urls'],
                "audio_url": play_info['audio_url'],
                "is_tv_mode": is_tv_mode,
                "is_vip": play_info['is_vip'],
                "has_hevc": play_info['has_hevc'],
                "kid": play_info.get('kid')
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "page": page
            }

    def get_bangumi_episode_playinfo(self, bvid, cid, quality=80, ep_id=None):
        try:
            
            play_url = self.config.get_api_url("bangumi_play_url_api").format(cid=cid, bvid=bvid, fnval=112)
            success, data = self._api_request(play_url, timeout=15)
            if not success:
                if "访问权限不足" in data['error']:
                    raise Exception("访问权限不足")
                raise Exception(f"获取番剧播放链接失败：{data['error']}")

            if data.get('code') != 0:
                error_msg = data.get('message', '权限不足')
                if data.get('code') == 403:
                    error_msg += "（可能是会员专享集或Cookie失效）"
                raise Exception(error_msg)

            data_source = data.get('data', data.get('result', {}))

            video_url = ""
            audio_url = ""
            if 'dash' in data_source:
                if data_source['dash'].get('video'):
                    selected_video = None
                    for video in data_source['dash']['video']:
                        if video.get('id') == quality:
                            selected_video = video
                            break
                    if not selected_video:
                        selected_video = data_source['dash']['video'][0]
                    video_url = selected_video['baseUrl']
                if data_source['dash'].get('audio'):
                    audio_url = data_source['dash']['audio'][0]['baseUrl']
            elif 'durl' in data_source:
                video_url = data_source['durl'][0]['url']

            if not video_url:
                raise Exception("未获取到视频播放链接")

            return {
                "success": True,
                "video_url": video_url,
                "audio_url": audio_url
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"番剧单集播放链接获取失败：{str(e)}（bvid={bvid}, cid={cid}）"
            }
    def decrypt_file(self, input_path, output_path, key):
        logger.info(f"开始解密文件：{input_path}")
        try:
            with open(input_path, 'rb') as f:
                encrypted_data = f.read()
            
            key_bytes = bytes.fromhex(key)
            cipher = AES.new(key_bytes, AES.MODE_ECB)
            
            decrypted_data = cipher.decrypt(encrypted_data)
            
            padding_length = decrypted_data[-1]
            if padding_length > 0:
                decrypted_data = decrypted_data[:-padding_length]
            
            with open(output_path, 'wb') as f:
                f.write(decrypted_data)
            
            logger.info(f"文件解密成功：{output_path}")
            return True
        except Exception as e:
            logger.error(f"文件解密失败：{str(e)}")
            return False

    async def download_file(self, url, save_path, progress_callback, file_type="video", bvid=None, is_running=None, kid=None):
        logger.info(f"开始下载{file_type}：{url[:100]}...")
        if is_running is not None and not is_running():
            logger.info("下载已被取消")
            raise Exception("下载已被取消")

        
        # 确保保存目录存在
        save_dir = os.path.dirname(save_path)
        try:
            os.makedirs(save_dir, exist_ok=True)
            logger.debug(f"保存目录：{save_dir}")
        except Exception as e:
            logger.error(f"创建保存目录失败：{str(e)}")
            raise Exception(f"创建保存目录失败：{str(e)}")

        
        # 使用工作目录下的temp文件夹作为临时目录
        work_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(work_dir, "temp")
        # 确保临时目录存在
        try:
            os.makedirs(temp_dir, exist_ok=True)
            # 设置文件夹为隐藏属性（Windows）
            if os.name == 'nt':
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(temp_dir, 0x02)
            logger.debug(f"临时目录：{temp_dir}")
        except Exception as e:
            logger.error(f"创建临时目录失败：{str(e)}")
            raise Exception(f"创建临时目录失败：{str(e)}")

        import uuid
        import time
        temp_filename = f"temp_{file_type}_{uuid.uuid4().hex}_{int(time.time())}.m4s"
        # 清理文件名中的非法字符
        import re
        temp_filename = re.sub(r'[\x00-\x1f\x7f:/\\*?"<>|]', '', temp_filename)
        temp_path = os.path.join(temp_dir, temp_filename)
        temp_path = os.path.normpath(temp_path)
        downloaded_size = 0
        logger.debug(f"临时文件：{temp_path}")

        
        try:
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': f'https://www.bilibili.com/video/{bvid}/' if bvid else 'https://www.bilibili.com/',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Origin': 'https://www.bilibili.com',
                'Pragma': 'no-cache',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site'
            }
            
            session = requests.Session()
            session.headers.update(headers)
            session.cookies.update(self.session.cookies)
            session.verify = False
            session.proxies = {}
            session.timeout = (15, 30)  

            # 检查是否是多分段下载
            if isinstance(url, list):
                logger.info(f"开始多分段下载，共{len(url)}个分段")
                total_segments = len(url)
                segment_size = 100 / total_segments
                cumulative_size = 0
                
                # 为每个分段创建临时文件
                segment_files = []
                
                for i, segment_url in enumerate(url):
                    if is_running is not None and not is_running():
                        logger.info("下载已被取消")
                        raise Exception("下载已被取消")
                    
                    segment_filename = f"temp_{file_type}_segment_{i}_{uuid.uuid4().hex}_{int(time.time())}.m4s"
                    segment_filename = re.sub(r'[\x00-\x1f\x7f:/\\*?"<>|]', '', segment_filename)
                    segment_path = os.path.join(temp_dir, segment_filename)
                    segment_files.append(segment_path)
                    
                    logger.info(f"下载分段 {i+1}/{total_segments}：{segment_url[:100]}...")
                    
                    # 下载单个分段
                    segment_size_downloaded = 0
                    max_retries = 3
                    retry_count = 0
                    segment_response = None
                    
                    while retry_count < max_retries:
                        try:
                            segment_response = session.get(segment_url, stream=True, headers=headers, timeout=(15, 30))
                            logger.info(f"分段 {i+1} 响应状态码：{segment_response.status_code}")
                            segment_response.raise_for_status()
                            break
                        except requests.exceptions.RequestException as e:
                            retry_count += 1
                            if retry_count >= max_retries:
                                raise
                            logger.warning(f"分段 {i+1} 请求失败，{retry_count}秒后重试：{str(e)}")
                            time.sleep(retry_count)
                    
                    segment_total_size = int(segment_response.headers.get('content-length', 0))
                    logger.info(f"分段 {i+1} 大小：{segment_total_size}字节")
                    
                    # 写入分段文件
                    with open(segment_path, 'wb') as f:
                        chunk_size = 65536  # 64KB
                        chunk_count = 0
                        start_time = time.time()
                        
                        for chunk in segment_response.iter_content(chunk_size=chunk_size):
                            if is_running is not None and not is_running():
                                logger.info("下载已被取消")
                                raise Exception("下载已取消")
                            
                            if chunk:
                                f.write(chunk)
                                chunk_len = len(chunk)
                                segment_size_downloaded += chunk_len
                                cumulative_size += chunk_len
                                
                                # 计算总进度
                                segment_progress = min(100, int((segment_size_downloaded / segment_total_size) * 100))
                                total_progress = min(99, int((i * segment_size) + (segment_progress * segment_size / 100)))
                                
                                if progress_callback and total_progress % 5 == 0:
                                    progress_callback(total_progress, cumulative_size)
                    
                    # 关闭分段响应
                    if segment_response:
                        segment_response.close()
                    
                    logger.info(f"分段 {i+1} 下载完成，大小：{segment_size_downloaded/1024/1024:.2f}MB")
                
                # 合并所有分段
                logger.info(f"开始合并{len(segment_files)}个分段")
                with open(temp_path, 'wb') as outfile:
                    for segment_file in segment_files:
                        with open(segment_file, 'rb') as infile:
                            outfile.write(infile.read())
                        # 删除已合并的分段文件
                        try:
                            os.remove(segment_file)
                            logger.debug(f"删除已合并的分段文件：{segment_file}")
                        except Exception as e:
                            logger.warning(f"删除分段文件失败：{str(e)}")
                
                downloaded_size = cumulative_size
                logger.info(f"分段合并完成，总大小：{downloaded_size/1024/1024:.2f}MB")
            else:
                # 单个URL下载（原有逻辑）
                if os.path.exists(temp_path):
                    downloaded_size = os.path.getsize(temp_path)
                    logger.info(f"续传：已下载{downloaded_size}字节")
                    headers['Range'] = f'bytes={downloaded_size}-'
                    mode = 'ab'
                else:
                    downloaded_size = 0
                    mode = 'wb'
                
                logger.debug(f"请求头：{headers}")

                
                logger.info(f"发送请求，URL：{url[:100]}...")
                max_retries = 3
                retry_count = 0
                response = None
                while retry_count < max_retries:
                    try:
                        response = session.get(url, stream=True, headers=headers, timeout=(15, 30))
                        logger.info(f"响应状态码：{response.status_code}")
                        
                        
                        if response.status_code == 416:
                            logger.info("文件已下载完成")
                            if progress_callback:
                                progress_callback(100, downloaded_size)
                            return temp_path
                        
                        response.raise_for_status()
                        break
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        if retry_count >= max_retries:
                            raise
                        logger.warning(f"请求失败，{retry_count}秒后重试：{str(e)}")
                        time.sleep(retry_count)

            
            total_size = int(response.headers.get('content-length', 0))
            if 'content-range' in response.headers:
                total_size = int(response.headers['content-range'].split('/')[-1])
            logger.info(f"文件大小：{total_size}字节")

            
            logger.debug(f"打开文件，模式：{mode}")
            
            # 添加断点续传支持
            max_download_retries = 3
            download_retry_count = 0
            download_success = False
            
            while download_retry_count < max_download_retries and not download_success:
                try:
                    # 使用二进制模式
                    with open(temp_path, mode) as f:
                        logger.debug("开始读取数据...")
                        # 优化：根据文件大小动态调整chunk_size
                        if total_size > 100 * 1024 * 1024:  # 大于100MB
                            chunk_size = 262144  # 256KB
                        elif total_size > 10 * 1024 * 1024:  # 大于10MB
                            chunk_size = 131072  # 128KB
                        else:
                            chunk_size = 65536  # 64KB
                        
                        chunk_count = 0
                        start_time = time.time()
                        last_progress_update = time.time()
                        last_progress_value = -1
                        bytes_processed = 0
                        speed_check_interval = 50  # 每处理50个chunk检查一次速度
                        
                        for chunk in response.iter_content(chunk_size=chunk_size):
                            if is_running is not None and not is_running():
                                logger.info("下载已被取消")
                                raise Exception("下载已取消")
                            
                            if chunk:
                                # 优化：使用缓冲区写入
                                f.write(chunk)
                                chunk_len = len(chunk)
                                downloaded_size += chunk_len
                                chunk_count += 1
                                bytes_processed += chunk_len
                                
                                current_time = time.time()
                                # 优化：减少进度更新频率
                                if chunk_count % 5 == 0 or current_time - last_progress_update >= 0.5:
                                    if total_size > 0:
                                        progress = min(99, int((downloaded_size / total_size) * 100))
                                    else:
                                        progress = min(99, int(chunk_count / 100))
                                    
                                    if progress != last_progress_value or current_time - last_progress_update >= 1.0:
                                        if progress_callback:
                                            progress_callback(progress, downloaded_size)
                                        last_progress_value = progress
                                        last_progress_update = current_time
                                        
                                # 优化：定期记录下载速度
                                if chunk_count % speed_check_interval == 0:
                                    elapsed_time = current_time - start_time
                                    if elapsed_time > 0:
                                        speed = bytes_processed / elapsed_time / 1024  # KB/s
                                        logger.debug(f"下载速度：{speed:.2f} KB/s，进度：{progress}%")
                                        bytes_processed = 0
                    
                    download_success = True
                    total_time = time.time() - start_time
                    if total_time > 0:
                        average_speed = downloaded_size / total_time / 1024 / 1024  # MB/s
                        logger.info(f"下载完成，总大小：{downloaded_size/1024/1024:.2f}MB，耗时：{total_time:.2f}秒，平均速度：{average_speed:.2f}MB/s")
                    else:
                        logger.info(f"下载完成，总大小：{downloaded_size/1024/1024:.2f}MB")
                    
                except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as e:
                    download_retry_count += 1
                    if download_retry_count >= max_download_retries:
                        logger.error(f"下载失败，已重试{max_download_retries}次：{str(e)}")
                        raise Exception(f"网络连接中断，下载失败：{str(e)}")
                    
                    logger.warning(f"下载中断，{download_retry_count}秒后重试：{str(e)}")
                    time.sleep(download_retry_count)
                    
                    # 更新已下载大小
                    if os.path.exists(temp_path):
                        downloaded_size = os.path.getsize(temp_path)
                        logger.info(f"已下载{downloaded_size}字节，尝试断点续传")
                    
                    # 重新发送请求，使用Range头进行断点续传
                    headers['Range'] = f'bytes={downloaded_size}-'
                    mode = 'ab'
                    
                    try:
                        response = session.get(url, stream=True, headers=headers, timeout=(15, 30))
                        logger.info(f"断点续传响应状态码：{response.status_code}")
                        
                        if response.status_code == 416:
                            logger.info("文件已下载完成")
                            download_success = True
                            break
                        
                        response.raise_for_status()
                    except Exception as retry_e:
                        logger.error(f"断点续传请求失败：{str(retry_e)}")
                        if download_retry_count >= max_download_retries:
                            raise Exception(f"断点续传失败：{str(retry_e)}")
            if progress_callback:
                progress_callback(100, downloaded_size)
            
            import gc
            gc.collect()
            
            logger.info("等待文件完全释放...")
            time.sleep(2)
            
            if file_type in ["video", "audio"]:
                is_encrypted, encryption_type = self._check_encryption(temp_path)
                if is_encrypted:
                    logger.info(f"检测到{file_type}被{encryption_type}加密，尝试解密")
                    try:
                        max_attempts = 5
                        for attempt in range(max_attempts):
                            try:
                                with open(temp_path, 'rb') as f:
                                    logger.info(f"文件可以正常打开（解密前尝试{attempt+1}/{max_attempts}）")
                                break
                            except Exception as e:
                                logger.error(f"文件被占用：{str(e)}")
                                if attempt < max_attempts - 1:
                                    logger.info(f"等待{3*(attempt+1)}秒后重试...")
                                    time.sleep(3*(attempt+1))
                                else:
                                    logger.error(f"文件仍然被占用，尝试{max_attempts}次后失败")
                                    raise Exception("文件被占用，无法解密")
                        
                        decrypted_path = temp_path + ".decrypted"
                        decrypted_path = await self._decrypt_with_bento4(temp_path, decrypted_path, kid)
                        # 等待文件系统稳定
                        import time
                        time.sleep(1)
                        # 检查解密后的文件是否存在
                        if not os.path.exists(decrypted_path):
                            raise Exception("解密后文件不存在")
                        # 再次检查文件存在性，防止竞态条件
                        if not os.path.exists(decrypted_path):
                            raise Exception("解密后文件不存在（竞态条件）")
                        decrypted_size = os.path.getsize(decrypted_path)
                        if decrypted_size < 1024:
                            raise Exception(f"解密后文件过小：{decrypted_size}字节")
                        logger.info("等待解密后文件释放...")
                        time.sleep(2)
                        
                        for attempt in range(max_attempts):
                            try:
                                with open(temp_path, 'rb') as f:
                                    pass
                                with open(decrypted_path, 'rb') as f:
                                    pass
                                logger.info(f"文件可以正常打开（替换前尝试{attempt+1}/{max_attempts}）")
                                break
                            except Exception as e:
                                logger.error(f"文件被占用：{str(e)}")
                                if attempt < max_attempts - 1:
                                    logger.info(f"等待{2*(attempt+1)}秒后重试...")
                                    time.sleep(2*(attempt+1))
                                else:
                                    logger.error(f"文件仍然被占用，尝试{max_attempts}次后失败")
                                    raise Exception("文件被占用，无法替换")
                        
                        os.remove(temp_path)
                        os.rename(decrypted_path, temp_path)
                        logger.info(f"{file_type}解密成功")
                    except Exception as decrypt_e:
                        logger.error(f"解密失败：{str(decrypt_e)}")
                        if os.path.exists(temp_path):
                            try:
                                os.remove(temp_path)
                                logger.debug(f"已清理加密的临时文件：{temp_path}")
                            except Exception as clean_e:
                                logger.warning(f"清理临时文件失败：{clean_e}")
                        if os.path.exists(decrypted_path):
                            try:
                                os.remove(decrypted_path)
                                logger.debug(f"已清理解密失败的临时文件：{decrypted_path}")
                            except Exception as clean_e:
                                logger.warning(f"清理临时文件失败：{clean_e}")
                        raise Exception(f"流媒体已加密，解密失败：{str(decrypt_e)}")
            
            # 将临时文件移动到最终保存路径
            import shutil
            try:
                # 确保目标文件不存在
                if os.path.exists(save_path):
                    # 尝试删除文件，最多重试3次
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            os.remove(save_path)
                            break
                        except Exception as remove_e:
                            logger.warning(f"删除文件失败（尝试{attempt+1}/{max_retries}）：{str(remove_e)}")
                            if attempt < max_retries - 1:
                                time.sleep(1)
                            else:
                                raise
                # 移动文件
                shutil.move(temp_path, save_path)
                logger.info(f"文件已保存到：{save_path}")
                return save_path
            except Exception as e:
                logger.error(f"移动文件失败：{str(e)}")
                # 尝试直接返回临时文件路径
                logger.warning("返回临时文件路径")
                return temp_path
        except requests.exceptions.Timeout as e:
            logger.error(f"下载超时：{str(e)}")
            raise Exception(f"下载超时：{str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败：{str(e)}")
            raise Exception(f"网络请求失败：{str(e)}")
        except Exception as e:
            logger.error(f"下载错误：{str(e)}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"已清理临时文件：{temp_path}")
                except Exception as clean_e:
                    logger.warning(f"清理临时文件失败：{clean_e}")
            raise Exception(f"{file_type}下载失败：{str(e)}")

    def _extract_kid_from_m4s(self, m4s_path):
        import re
        
        try:
            if not os.path.exists(m4s_path):
                logger.error(f"M4S文件不存在：{m4s_path}")
                return None
            
            file_size = os.path.getsize(m4s_path)
            logger.info(f"M4S文件大小：{file_size}字节")
            
            if file_size < 1024:
                logger.warning("文件过小，可能不是有效的M4S文件")
                return None
            
            logger.info("等待文件释放...")
            time.sleep(2)
            
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    with open(m4s_path, 'rb') as f:
                        logger.info(f"文件可以正常打开（尝试{attempt+1}/{max_attempts}")
                    break
                except Exception as e:
                    logger.error(f"文件被占用：{str(e)}")
                    if attempt < max_attempts - 1:
                        logger.info(f"等待{2*(attempt+1)}秒后重试...")
                        time.sleep(2*(attempt+1))
                    else:
                        logger.error(f"文件仍然被占用，尝试{max_attempts}次后失败")
                        return None
            
            bento4_path = os.path.join(self.bento4_dir, 'mp4dump.exe')
            if os.path.exists(bento4_path):
                try:
                    absolute_path = os.path.abspath(m4s_path)
                    logger.info(f"使用绝对路径：{absolute_path}")
                    
                    cmd = [bento4_path, absolute_path]
                    logger.info(f"执行命令：{' '.join(cmd)}")
                    
                    import subprocess
                    result = subprocess.run(cmd, capture_output=True, text=False, timeout=30,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    if result.returncode == 0:
                        output = result.stdout.decode('utf-8', errors='replace')
                        kid_match = re.search(r'default_KID\s*=\s*\[(.*?)\]', output)
                        if not kid_match:
                            kid_match = re.search(r'KID\s*=\s*\[(.*?)\]', result.stdout)
                        if not kid_match:
                            kid_match = re.search(r'[Kk][Ii][Dd]\s*[:=]\s*\[(.*?)\]', result.stdout)
                        if not kid_match:
                            kid_match = re.search(r'uri:bili://([0-9a-fA-F]{32})', result.stdout)
                        if not kid_match:
                            kid_match = re.search(r'([0-9a-fA-F]{32})', result.stdout)
                        
                        if kid_match:
                            if len(kid_match.groups()) > 0:
                                kid_hex = kid_match.group(1)
                                kid = ''.join(kid_hex.split())
                                if len(kid) == 32 and all(c in '0123456789abcdefABCDEF' for c in kid):
                                    logger.info(f"从mp4dump输出中提取到KID：{kid}")
                                    return kid
                                else:
                                    logger.error(f"提取到的KID格式不正确：{kid}")
                            else:
                                kid = kid_match.group(0)
                                if len(kid) == 32 and all(c in '0123456789abcdefABCDEF' for c in kid):
                                    logger.info(f"从mp4dump输出中提取到KID：{kid}")
                                    return kid
                    else:
                        logger.warning(f"mp4dump返回错误：{result.stderr}")
                except Exception as e:
                    logger.warning(f"执行mp4dump时出错：{str(e)}")
            else:
                logger.warning("Bento4 mp4dump工具不存在")
            
            logger.info("尝试直接从文件内容中提取KID...")
            try:
                with open(m4s_path, 'rb') as f:
                    file_content = f.read(102400)
                    content_str = file_content.decode('utf-8', errors='ignore')
                    
                    kid_match = re.search(r'uri:bili://([0-9a-fA-F]{32})', content_str)
                    if not kid_match:
                        kid_match = re.search(r'([0-9a-fA-F]{32})', content_str)
                    
                    if kid_match:
                        kid = kid_match.group(1) if kid_match.groups() else kid_match.group(0)
                        if len(kid) == 32 and all(c in '0123456789abcdefABCDEF' for c in kid):
                            logger.info(f"从文件内容中提取到KID：{kid}")
                            return kid
                        else:
                            logger.error(f"提取到的KID格式不正确：{kid}")
            except Exception as e:
                logger.error(f"直接读取文件时出错：{str(e)}")
            
            mp4info_path = os.path.join(self.bento4_dir, 'mp4info.exe')
            if os.path.exists(mp4info_path):
                try:
                    absolute_path = os.path.abspath(m4s_path)
                    cmd = [mp4info_path, absolute_path]
                    logger.info(f"执行命令：{' '.join(cmd)}")
                    
                    import subprocess
                    result = subprocess.run(cmd, capture_output=True, text=False, timeout=30,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                    
                    if result.returncode == 0:
                        output = result.stdout.decode('utf-8', errors='replace')
                        kid_match = re.search(r'default_KID\s*=\s*\[(.*?)\]', output)
                        if not kid_match:
                            kid_match = re.search(r'KID\s*=\s*\[(.*?)\]', output)
                        if not kid_match:
                            kid_match = re.search(r'uri:bili://([0-9a-fA-F]{32})', output)
                        if not kid_match:
                            kid_match = re.search(r'([0-9a-fA-F]{32})', output)
                        
                        if kid_match:
                            kid = kid_match.group(1) if kid_match.groups() else kid_match.group(0)
                            if len(kid) == 32 and all(c in '0123456789abcdefABCDEF' for c in kid):
                                logger.info(f"从mp4info输出中提取到KID：{kid}")
                                return kid
                except Exception as e:
                    logger.warning(f"执行mp4info时出错：{str(e)}")
            
            logger.error("所有方法都无法提取KID")
            return None
        except Exception as e:
            logger.error(f"提取KID时出错：{str(e)}")
            import traceback
            traceback.print_exc()
            return None

    async def _decrypt_with_bento4(self, input_file, output_file, kid=None):
        try:
            if not kid:
                # 没有提供kid，尝试提取
                try:
                    kid = self._extract_kid_from_m4s(input_file)
                    logger.info(f"提取到KID：{kid}")
                except Exception as e:
                    logger.warning(f"提取KID时发生异常：{str(e)}")
                
                if not kid:
                    # 未提供kid且提取失败，直接复制文件，尝试直接合并
                    logger.info("未提供KID且提取失败，直接复制文件尝试合并")
                    shutil.copy2(input_file, output_file)
                    return output_file
            
            # 尝试获取DRM密钥
            key = None
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    async with SimpleBiliDRM() as drm:
                        key = await drm.get_key(kid)
                        if key:
                            break
                except Exception as e:
                    logger.warning(f"获取DRM密钥失败，尝试重试 ({retry_count+1}/{max_retries})：{str(e)}")
                    retry_count += 1
                    await asyncio.sleep(2)
            
            if not key:
                logger.error("多次尝试后仍然无法获取DRM密钥")
                # 尝试直接复制文件，可能是未加密的视频
                logger.info("尝试直接复制文件，可能是未加密的视频")
                shutil.copy2(input_file, output_file)
                return output_file
            
            logger.info(f"使用KID {kid} 和密钥 {key} 解密文件")
            
            if not os.path.exists(input_file):
                raise Exception(f"输入文件不存在：{input_file}")
            
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            input_file = os.path.abspath(input_file)
            output_file = os.path.abspath(output_file)
            
            # 确保输出文件有正确的扩展名
            base_name = os.path.basename(output_file)
            if not base_name.endswith('.mp4'):
                output_file = os.path.join(os.path.dirname(output_file), f"{os.path.splitext(base_name)[0]}.mp4")
            
            logger.info(f"输入文件绝对路径：{input_file}")
            logger.info(f"输出文件绝对路径：{output_file}")
            
            try:
                ffmpeg_exec = shutil.which('ffmpeg')
                if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                    ffmpeg_exec = self.ffmpeg_local
                    if not os.path.exists(ffmpeg_exec):
                        raise Exception("未找到ffmpeg")
                
                cmd = [
                    ffmpeg_exec,
                    '-decryption_key', f'{key}',
                    '-i', input_file,
                    '-c', 'copy',
                    '-y',
                    output_file
                ]
                logger.info(f"使用ffmpeg执行解密命令：{' '.join(cmd)}")
                
                # 异步执行ffmpeg命令
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    logger.error(f"ffmpeg解密失败，返回码：{process.returncode}")
                    logger.error(f"错误输出：{error_msg}")
                    logger.error(f"标准输出：{stdout.decode('utf-8', errors='ignore')}")
                    raise Exception(f"ffmpeg解密失败：{error_msg}")
                
                logger.info(f"ffmpeg解密成功：{input_file} -> {output_file}")
                return output_file
            except Exception as ffmpeg_e:
                logger.warning(f"ffmpeg解密失败，尝试使用Bento4：{str(ffmpeg_e)}")
                
                bento4_path = os.path.join(self.bento4_dir, 'mp4decrypt.exe')
                if not os.path.exists(bento4_path):
                    raise Exception(f"Bento4 mp4decrypt工具不存在：{bento4_path}")
                
                # 使用系统临时目录作为临时目录（避免中文路径问题）
                import tempfile
                temp_dir = tempfile.gettempdir()
                simple_input = os.path.join(temp_dir, f"input_{os.path.basename(input_file)}")
                simple_output = os.path.join(temp_dir, f"output_{os.path.basename(input_file)}.decrypted")
                
                shutil.copy2(input_file, simple_input)
                logger.info(f"复制文件到系统临时目录：{simple_input}")
                
                # 异步执行Bento4命令
                cmd = [bento4_path, '--key', f'{kid}:{key}', simple_input, simple_output]
                logger.info(f"使用Bento4执行解密命令：{' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                # 检查Bento4命令返回码
                if process.returncode != 0:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    logger.error(f"Bento4解密失败，返回码：{process.returncode}")
                    logger.error(f"错误输出：{error_msg}")
                    logger.error(f"标准输出：{stdout.decode('utf-8', errors='ignore')}")
                    # 清理临时文件
                    if os.path.exists(simple_input):
                        try:
                            os.remove(simple_input)
                        except Exception as e:
                            logger.warning(f"清理临时输入文件失败：{e}")
                    if os.path.exists(simple_output):
                        try:
                            os.remove(simple_output)
                        except Exception as e:
                            logger.warning(f"清理临时输出文件失败：{e}")
                    raise Exception(f"Bento4解密失败：{error_msg}")
                
                # 等待文件操作完成
                await asyncio.sleep(1.0)  # 增加等待时间
                
                # 检查解密后的文件
                if os.path.exists(simple_output) and os.path.getsize(simple_output) > 1024:
                    shutil.copy2(simple_output, output_file)
                    logger.info(f"复制解密后的文件到目标位置：{output_file}")
                else:
                    # 清理临时文件
                    if os.path.exists(simple_input):
                        try:
                            os.remove(simple_input)
                        except Exception as e:
                            logger.warning(f"清理临时输入文件失败：{e}")
                    if os.path.exists(simple_output):
                        try:
                            os.remove(simple_output)
                        except Exception as e:
                            logger.warning(f"清理临时输出文件失败：{e}")
                    raise Exception("解密后文件不存在或文件过小")
                
                # 清理临时文件
                if os.path.exists(simple_input):
                    try:
                        os.remove(simple_input)
                    except Exception as e:
                        logger.warning(f"清理临时输入文件失败：{e}")
                if os.path.exists(simple_output):
                    try:
                        os.remove(simple_output)
                    except Exception as e:
                        logger.warning(f"清理临时输出文件失败：{e}")
                
                logger.info(f"Bento4解密成功：{input_file} -> {output_file}")
                return output_file
        except Exception as e:
            logger.error(f"解密时出错：{str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def _check_encryption(self, video_path):
        try:
            if not video_path or not os.path.exists(video_path):
                logger.error(f"加密检测：文件不存在：{video_path}")
                return False, ""
            
            file_size = os.path.getsize(video_path)
            logger.info(f"加密检测：文件大小={file_size}字节")
            
            if file_size < 1024:
                logger.warning("加密检测：文件过小，可能是加密文件")
                return True, "加密文件"
            
            try:
                ffprobe_exec = shutil.which('ffprobe')
                if not ffprobe_exec or not os.path.exists(ffprobe_exec):
                    if os.path.exists(self.ffmpeg_local):
                        ffprobe_path = os.path.join(os.path.dirname(self.ffmpeg_local), 'ffprobe.exe')
                        if os.path.exists(ffprobe_path):
                            ffprobe_exec = ffprobe_path
                
                if ffprobe_exec and os.path.exists(ffprobe_exec):
                    cmd = [ffprobe_exec, '-i', video_path, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams']
                    logger.info(f"加密检测：使用ffprobe检测文件类型，命令={cmd}")
                    result = subprocess.run(cmd, capture_output=True, text=False, timeout=30,
                                          creationflags=subprocess.CREATE_NO_WINDOW)
                    stdout = result.stdout.decode('utf-8', errors='replace')
                    stderr = result.stderr.decode('utf-8', errors='replace')
                    logger.info(f"加密检测：ffprobe返回码={result.returncode}")
                    logger.info(f"加密检测：ffprobe stdout={stdout}")
                    logger.info(f"加密检测：ffprobe stderr={stderr}")
                    
                    decode_errors = ['error while decoding', 'Invalid data found', 'top block unavailable', 'bytestream', 'Could not find codec parameters', 'Could not open codec', 'Error opening input file']
                    has_decode_error = any(error in stderr for error in decode_errors)
                    
                    if result.returncode == 0 and not has_decode_error:
                        logger.info("加密检测：ffprobe检测成功，文件格式正常")
                        return False, ""
                    else:
                        logger.warning(f"加密检测：ffprobe检测失败，这是加密/损坏文件！")
                        logger.warning("加密检测：ffprobe检测失败，标记为加密文件")
                        return True, "加密文件"
            except Exception as ffprobe_e:
                logger.error(f"加密检测：ffprobe检测异常：{str(ffprobe_e)}")
                logger.warning("加密检测：ffprobe检测异常，标记为加密文件")
                return True, "加密文件"
            
            logger.warning("加密检测：无法找到ffprobe，使用备选检测方法")
            
            with open(video_path, 'rb') as f:
                header = f.read(256)
                logger.info(f"加密检测：文件头前256字节={header[:256].hex()}")
                
                if header.startswith(b'RDM'):
                    logger.warning("加密检测：检测到RDM加密")
                    return True, "RDM"
                
                if header.startswith(b'AES-') or b'AES' in header[:128]:
                    logger.warning("加密检测：检测到AES加密")
                    return True, "AES"
                
                if b'DRM' in header[:128] or b'Widevine' in header[:256] or b'PlayReady' in header[:256] or b'FairPlay' in header[:256]:
                    logger.warning("加密检测：检测到DRM加密")
                    return True, "DRM"
                
                if header.startswith(b'ftyp'):
                    logger.info("加密检测：检测到标准MP4文件")
                    return False, ""
                
                if header[0:1] == b'\x47':
                    logger.info("加密检测：检测到MPEG-TS文件")
                    return False, ""
                
                if header.startswith(b'FLV'):
                    logger.info("加密检测：检测到FLV文件")
                    return False, ""
                
                if header.startswith(b'\x1a\x45\xdf\xa3'):
                    logger.info("加密检测：检测到MKV/WebM文件")
                    return False, ""
                
                if header.startswith(b'ftyp') or (len(header) >= 8 and header[4:8] == b'ftyp'):
                    logger.info("加密检测：检测到m4s/MP4文件")
                    return False, ""
                
                if header.startswith(b'ID3'):
                    logger.info("加密检测：检测到MP3文件")
                    return False, ""
                
                if header.startswith(b'RIFF') and b'WAVE' in header[:12]:
                    logger.info("加密检测：检测到WAV文件")
                    return False, ""
                
                if header.startswith(b'ADIF') or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xF0) == 0xF0):
                    logger.info("加密检测：检测到AAC文件")
                    return False, ""
                
                try:
                    f.seek(0)
                    more_data = f.read(4096)
                    logger.info(f"加密检测：文件前4096字节分析：{more_data[:512].hex()}")
                    more_data_lower = more_data.lower()
                    if b'encrypted' in more_data_lower:
                        logger.warning("加密检测：检测到'encrypted'关键词")
                        return True, "加密文件"
                    if b'encryption' in more_data_lower:
                        logger.warning("加密检测：检测到'encryption'关键词")
                        return True, "加密文件"
                    if b'key' in more_data_lower:
                        logger.warning("加密检测：检测到'key'关键词")
                        return True, "加密文件"
                    if b'crypt' in more_data_lower:
                        logger.warning("加密检测：检测到'crypt'关键词")
                        return True, "加密文件"
                    if b'drm' in more_data_lower:
                        logger.warning("加密检测：检测到'DRM'关键词")
                        return True, "DRM"
                    if b'aes' in more_data_lower:
                        logger.warning("加密检测：检测到'AES'关键词")
                        return True, "AES"
                except Exception as read_e:
                    logger.error(f"加密检测：读取文件更多内容失败：{str(read_e)}")
                
                ext = os.path.splitext(video_path)[1].lower()
                logger.info(f"加密检测：文件扩展名={ext}")
                encrypted_exts = ['.enc', '.drm', '.protected', '.secure', '.encrypted']
                if ext in encrypted_exts:
                    logger.warning(f"加密检测：检测到加密文件扩展名{ext}")
                    return True, "加密文件"
                
                media_exts = ['.mp4', '.ts', '.flv', '.mkv', '.webm', '.m4s', '.mp3', '.wav', '.aac']
                if ext in media_exts:
                    logger.info(f"加密检测：检测到媒体文件扩展名{ext}")
                    return False, ""
                
                logger.warning(f"加密检测：检测到未知文件格式，但默认不标记为加密")
                return False, ""
        except Exception as e:
            logger.error(f"加密检测：检测失败：{str(e)}")
            import traceback
            traceback.print_exc()
            logger.warning("加密检测：检测异常，安全起见标记为加密文件")
            return True, "加密文件"
            
    def get_danmaku(self, cid, aid=None):
        import logging
        import gzip
        import xml.etree.ElementTree as ET
        import requests
        logger = logging.getLogger(__name__)
        
        try:
            xml_urls = [
                f"https://comment.bilibili.com/{cid}.xml",
                f"https://api.bilibili.com/x/v1/dm/list.so?oid={cid}"
            ]
            
            for xml_url in xml_urls:
                logger.info(f"尝试使用XML弹幕API：{xml_url}")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Referer': 'https://www.bilibili.com',
                        'Accept-Encoding': 'gzip, deflate'
                    }
                    
                    response = self.session.get(xml_url, headers=headers, timeout=10)
                    logger.info(f"XML API响应状态码：{response.status_code}")
                    logger.info(f"XML API响应头：{dict(response.headers)}")
                    
                    if response.status_code != 200:
                        logger.warning(f"XML API请求失败，状态码：{response.status_code}")
                        logger.warning(f"响应内容：{response.text[:200]}")
                        continue
                    
                    content = response.content
                    logger.info(f"响应内容长度：{len(content)}")
                    
                    if response.headers.get('Content-Encoding') == 'gzip':
                        logger.info("处理gzip压缩响应")
                        try:
                            content = gzip.decompress(content)
                            logger.info(f"解压后内容长度：{len(content)}")
                        except Exception as e:
                            logger.error(f"解压gzip响应失败：{str(e)}")
                            continue
                    
                    try:
                        xml_content = content.decode('utf-8')
                        logger.info(f"XML内容前200字符：{xml_content[:200]}")
                        
                        root = ET.fromstring(xml_content)
                        danmaku_list = []
                        
                        logger.info(f"XML根标签：{root.tag}")
                        logger.info(f"XML子标签数量：{len(root)}")
                        
                        for d in root.findall('.//d'):
                            p = d.get('p')
                            if p:
                                parts = p.split(',')
                                if len(parts) >= 8:
                                    try:
                                        danmaku = {
                                            "id": int(parts[7]),
                                            "progress": int(float(parts[0]) * 1000),
                                            "mode": int(parts[1]),
                                            "fontsize": int(parts[2]),
                                            "color": int(parts[3]),
                                            "midHash": parts[6],
                                            "content": d.text or "",
                                            "ctime": int(parts[4]),
                                            "weight": 1,
                                            "pool": int(parts[5]),
                                            "idStr": parts[7],
                                            "attr": 0
                                        }
                                        danmaku_list.append(danmaku)
                                    except (ValueError, IndexError) as e:
                                        logger.error(f"解析弹幕数据失败：{str(e)}")
                                        continue
                        
                        if danmaku_list:
                            logger.info(f"XML API获取到{len(danmaku_list)}条弹幕")
                            return {"data": {"danmaku": danmaku_list, "count": len(danmaku_list)}, "error": ""}
                        else:
                            logger.warning("XML API未获取到弹幕")
                    except Exception as e:
                        logger.error(f"解析XML失败：{str(e)}")
                        try:
                            logger.error(f"错误时的XML内容：{content[:500].decode('utf-8', errors='replace')}")
                        except:
                            pass
                        continue
                except Exception as e:
                    logger.error(f"XML API请求失败：{str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            proto_urls = [
                {"url": "https://api.bilibili.com/x/v2/dm/web/seg.so", "params": {"type": 1, "oid": cid, "segment_index": 1}},
                {"url": "https://api.bilibili.com/x/v2/dm/list/seg.so", "params": {"type": 1, "oid": cid, "segment_index": 1}},
                {"url": "https://api.bilibili.com/x/v2/dm/wbi/web/seg.so", "params": {"type": 1, "oid": cid, "segment_index": 1}}
            ]
            
            if aid:
                proto_urls.append({"url": "https://api.bilibili.com/x/v2/dm/web/seg.so", "params": {"type": 1, "oid": cid, "pid": aid, "segment_index": 1}})
            
            for config in proto_urls:
                url = config["url"]
                params = config["params"]
                logger.info(f"尝试使用Protobuf弹幕API：{url}，参数：{params}")
                
                try:
                    if 'Referer' not in self.session.headers:
                        self.session.headers.update({'Referer': 'https://www.bilibili.com'})
                    
                    response = self.session.get(url, params=params, timeout=10)
                    logger.info(f"Protobuf API响应状态码：{response.status_code}")
                    
                    if response.status_code != 200:
                        logger.warning(f"Protobuf API请求失败，状态码：{response.status_code}")
                        continue
                    
                    content = response.content
                    if not content:
                        logger.warning("空响应")
                        continue
                    
                    segment_danmaku = self._parse_danmaku_proto(content)
                    if segment_danmaku:
                        logger.info(f"Protobuf API获取到{len(segment_danmaku)}条弹幕")
                        return {"data": {"danmaku": segment_danmaku, "count": len(segment_danmaku)}, "error": ""}
                    else:
                        logger.warning("Protobuf API未解析到弹幕")
                except Exception as e:
                    logger.error(f"Protobuf API请求失败：{str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            logger.info("所有API都未获取到弹幕")
            return {"data": {"danmaku": [], "count": 0}, "error": ""}
        except Exception as e:
            logger.error(f"获取弹幕失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return {"data": {}, "error": str(e)}
            
    def get_subtitle(self, subtitle_id):
        import logging
        import json
        import requests
        import time
        import random
        import string
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"开始获取字幕，subtitle_id: {subtitle_id}")
            
            # 生成auth_key
            timestamp = int(time.time())
            random_str1 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
            random_str2 = ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))
            auth_key = f"{timestamp}-{random_str1}-0-{random_str2}"
            
            subtitle_url = f"https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/{subtitle_id}?auth_key={auth_key}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com',
                'Origin': 'https://www.bilibili.com',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            logger.info(f"字幕API请求URL：{subtitle_url}")
            logger.info(f"字幕API请求头：{headers}")
            
            # 使用self.session来保持cookies（登录态）
            response = self.session.get(subtitle_url, headers=headers, timeout=15)
            logger.info(f"字幕API响应状态码：{response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"获取字幕失败，状态码：{response.status_code}")
                return {"data": {}, "error": f"HTTP {response.status_code}"}
            
            content = response.text.strip()
            logger.info(f"字幕API响应内容长度：{len(content)}")
            
            try:
                data = json.loads(content)
                
                subtitle_info = {
                    "font_size": data.get("font_size", 0.4),
                    "font_color": data.get("font_color", "#FFFFFF"),
                    "background_alpha": data.get("background_alpha", 0.5),
                    "background_color": data.get("background_color", "#9C27B0"),
                    "stroke": data.get("Stroke", "none"),
                    "lang": data.get("lang", "zh"),
                    "type": data.get("type", "AIsubtitle"),
                    "version": data.get("version", "v1.7.0.4"),
                    "body": data.get("body", [])
                }
                
                logger.info(f"字幕获取成功，共 {len(subtitle_info['body'])} 条")
                return {"data": subtitle_info, "error": ""}
                
            except json.JSONDecodeError as e:
                logger.error(f"解析字幕JSON失败：{str(e)}")
                return {"data": {}, "error": f"JSON解析失败：{str(e)}"}
                
        except requests.exceptions.Timeout:
            logger.error("获取字幕请求超时")
            return {"data": {}, "error": "请求超时"}
        except Exception as e:
            logger.error(f"获取字幕失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return {"data": {}, "error": str(e)}
            
    def _get_danmaku_info(self, cid, aid=None):
        import logging
        import json
        logger = logging.getLogger(__name__)
        
        try:
            url = "https://api.bilibili.com/x/v2/dm/web/view"
            params = {
                "type": 1,
                "oid": cid
            }
            if aid:
                params["pid"] = aid
            
            if 'Referer' not in self.session.headers:
                self.session.headers.update({'Referer': 'https://www.bilibili.com'})
            
            response = self.session.get(url, params=params, timeout=10)
            logger.info(f"弹幕API响应状态码：{response.status_code}")
            logger.info(f"弹幕API响应头：{dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"获取弹幕元数据失败：HTTP {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            content = response.text.strip()
            logger.info(f"弹幕API响应内容长度：{len(content)}")
            logger.info(f"弹幕API响应内容前200字符：{content[:200]}")
            
            try:
                data = json.loads(content)
                code = data.get('code', 0)
                if code != 0:
                    error_message = data.get('message', '未知错误')
                    logger.error(f"获取弹幕元数据失败：{error_message}（code={code}）")
                    return {"success": False, "error": error_message}
                
                danmaku_data = data.get("data", {})
                count = danmaku_data.get("count", 0)
                
                logger.info(f"获取弹幕元数据成功，弹幕总数：{count}")
                return {"success": True, "count": count, "data": danmaku_data}
            except json.JSONDecodeError:
                logger.error(f"获取弹幕元数据失败：API返回的不是JSON格式数据")
                logger.error(f"响应内容：{content[:500]}")
                
                try:
                    url2 = "https://api.bilibili.com/x/v2/dm/preview"
                    params2 = {
                        "aid": aid or "0",
                        "cid": cid,
                        "page": 1
                    }
                    response2 = self.session.get(url2, params=params2, timeout=10)
                    if response2.status_code == 200:
                        content2 = response2.text.strip()
                        data2 = json.loads(content2)
                        if data2.get('code') == 0:
                            danmaku_data2 = data2.get("data", {})
                            count2 = danmaku_data2.get("count", 0)
                            logger.info(f"使用备用API获取弹幕元数据成功，弹幕总数：{count2}")
                            return {"success": True, "count": count2, "data": danmaku_data2}
                except Exception as e2:
                    logger.error(f"备用API也失败：{str(e2)}")
                
                return {"success": False, "error": "API返回的不是JSON格式数据"}
        except Exception as e:
            logger.error(f"获取弹幕元数据失败：{str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
            
    def _get_danmaku_segment(self, cid, segment_index, aid=None):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            url = "https://api.bilibili.com/x/v2/dm/web/seg.so"
            params = {
                "type": 1,
                "oid": cid,
                "segment_index": segment_index
            }
            if aid:
                params["pid"] = aid
            
            if 'Referer' not in self.session.headers:
                self.session.headers.update({'Referer': 'https://www.bilibili.com'})
            
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                return {"success": False, "error": f"HTTP {response.status_code}"}
            
            content = response.content
            if not content:
                return {"success": False, "error": "空响应"}
            
            danmaku_list = self._parse_danmaku_proto(content)
            return {"success": True, "danmaku": danmaku_list}
        except Exception as e:
            logger.error(f"获取弹幕分段失败：{str(e)}")
            return {"success": False, "error": str(e)}
            
    def _parse_danmaku_proto(self, data):
        import logging
        import struct
        logger = logging.getLogger(__name__)
        
        try:
            try:
                from bilibili.community.service.dm.v1.dm_pb2 import DmSegMobileReply
                danmaku_seg = DmSegMobileReply()
                danmaku_seg.ParseFromString(data)
                
                danmaku_list = []
                for elem in danmaku_seg.elems:
                    danmaku = {
                        "id": elem.id,
                        "progress": elem.progress,
                        "mode": elem.mode,
                        "fontsize": elem.fontsize,
                        "color": elem.color,
                        "midHash": elem.midHash,
                        "content": elem.content,
                        "ctime": elem.ctime,
                        "weight": elem.weight,
                        "pool": elem.pool,
                        "idStr": elem.idStr,
                        "attr": elem.attr
                    }
                    danmaku_list.append(danmaku)
                
                return danmaku_list
            except ImportError:
                logger.warning("未找到编译的protobuf文件，使用简单解析方式")
                
                danmaku_list = []
                offset = 0
                data_len = len(data)
                
                while offset < data_len:
                    try:
                        if offset + 4 > data_len:
                            break
                        msg_len = struct.unpack('<I', data[offset:offset+4])[0]
                        offset += 4
                        
                        if offset + 1 > data_len:
                            break
                        msg_type = data[offset]
                        offset += 1
                        
                        if msg_type == 1:
                            danmaku = {
                                "id": 0,
                                "progress": 0,
                                "mode": 1,
                                "fontsize": 25,
                                "color": 16777215,
                                "midHash": "unknown",
                                "content": "",
                                "ctime": 0,
                                "weight": 1,
                                "pool": 0,
                                "idStr": "",
                                "attr": 0
                            }
                            
                            pos = offset
                            while pos < offset + msg_len:
                                if pos + 2 > data_len:
                                    break
                                field_type = (data[pos] >> 3) & 0x7
                                field_num = data[pos] & 0x7
                                pos += 1
                                
                                if field_type == 2:
                                    if pos + 4 > data_len:
                                        break
                                    str_len = struct.unpack('<I', data[pos:pos+4])[0]
                                    pos += 4
                                    if pos + str_len <= data_len:
                                        if field_num == 8:
                                            danmaku["content"] = data[pos:pos+str_len].decode('utf-8', errors='replace')
                                        elif field_num == 5:
                                            danmaku["midHash"] = data[pos:pos+str_len].decode('utf-8', errors='replace')
                                    pos += str_len
                                elif field_type == 0:
                                    varint = 0
                                    shift = 0
                                    while pos < data_len:
                                        byte = data[pos]
                                        varint |= (byte & 0x7f) << shift
                                        shift += 7
                                        pos += 1
                                        if not (byte & 0x80):
                                            break
                                    if field_num == 1:
                                        danmaku["id"] = varint
                                    elif field_num == 2:
                                        danmaku["progress"] = varint
                                    elif field_num == 3:
                                        danmaku["mode"] = varint
                                    elif field_num == 4:
                                        danmaku["fontsize"] = varint
                                    elif field_num == 6:
                                        danmaku["color"] = varint
                                    elif field_num == 7:
                                        danmaku["ctime"] = varint
                                    elif field_num == 9:
                                        danmaku["weight"] = varint
                                    elif field_num == 10:
                                        danmaku["pool"] = varint
                                    elif field_num == 12:
                                        danmaku["attr"] = varint
                                elif field_type == 1:
                                    pos += 8
                                elif field_type == 5:
                                    pos += 4
                        
                        offset += msg_len
                    except Exception as e:
                        logger.error(f"解析弹幕片段失败：{str(e)}")
                        offset += 1
                
                danmaku_list = [d for d in danmaku_list if d["content"]]
                logger.info(f"简单解析获取到{len(danmaku_list)}条弹幕")
                return danmaku_list
        except Exception as e:
            logger.error(f"解析弹幕protobuf失败：{str(e)}")
            return []
            
    def convert_danmaku_format(self, danmaku_list, format_type="XML"):
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            if format_type == "XML":
                return self._convert_to_xml(danmaku_list)
            elif format_type == "ASS":
                return self._convert_to_ass(danmaku_list)
            elif format_type == "JSON":
                import json
                return json.dumps(danmaku_list).decode('utf-8')
            else:
                logger.error(f"不支持的弹幕格式：{format_type}")
                return ""
        except Exception as e:
            logger.error(f"转换弹幕格式失败：{str(e)}")
            return ""
            
    def _convert_to_xml(self, danmaku_list):
        import time
        xml_header = '<?xml version="1.0" encoding="UTF-8"?><i>\n'
        xml_footer = '</i>'
        
        xml_content = xml_header
        for danmaku in danmaku_list:
            time_str = self._format_danmaku_time(danmaku['progress'])
            mode = danmaku['mode']
            fontsize = danmaku['fontsize']
            color = danmaku['color']
            ctime = danmaku['ctime']
            mid_hash = danmaku['midHash']
            content = danmaku['content'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            danmaku_id = danmaku['id']
            
            xml_line = f'  <d p="{time_str},{mode},{fontsize},{color},{ctime},{mid_hash},0,{danmaku_id}">{content}</d>\n'
            xml_content += xml_line
        
        xml_content += xml_footer
        return xml_content
        
    def _convert_to_ass(self, danmaku_list):
        ass_header = '''[Script Info]
; Script generated by Bilibili Downloader
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes
Collisions: Normal

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,SimHei,25,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
        
        ass_content = ass_header
        layer = 0
        for danmaku in danmaku_list:
            start_time = self._format_ass_time(danmaku['progress'])
            end_time = self._format_ass_time(danmaku['progress'] + 8000)
            mode = danmaku['mode']
            alignment = 2
            if mode == 4:
                alignment = 8
            elif mode == 5:
                alignment = 4
            color = danmaku['color']
            content = danmaku['content'].replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}')
            
            ass_line = f'Dialogue: {layer},{start_time},{end_time},Default,,0,0,0,,{{\\c&H{color:06X}&}}{{\\a{alignment}}}{content}\n'
            ass_content += ass_line
        
        return ass_content
        
    def _format_danmaku_time(self, ms):
        seconds = ms / 1000
        return f"{seconds:.2f}"
        
    def _format_ass_time(self, ms):
        seconds = ms / 1000
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:.2f}"

    def _get_video_codec(self, video_path, ffmpeg_exec):
        """获取视频文件的编码格式"""
        try:
            import subprocess
            cmd = [
                ffmpeg_exec,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                video_path
            ]
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            import json
            output = result.stdout.decode('utf-8', errors='ignore')
            data = json.loads(output)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return stream.get('codec_name', 'unknown')
            return 'unknown'
        except Exception as e:
            logger.warning(f"获取视频编码失败：{str(e)}")
            return 'unknown'
    
    async def merge_media(self, video_path, audio_path, output_path, kid=None):
        import os
        try:
            logger.debug(f"开始合并音视频：视频={video_path}, 音频={audio_path}, 输出={output_path}")
            
            decrypted_video_path = video_path
            decrypted_audio_path = audio_path
            
            is_encrypted, encryption_type = self._check_encryption(video_path)
            if is_encrypted:
                logger.info(f"检测到视频被{encryption_type}加密，尝试解密")
                decrypted_video_path = video_path + '.decrypted'
                await self._decrypt_with_bento4(video_path, decrypted_video_path, kid)
                if not os.path.exists(decrypted_video_path):
                    return False, "视频解密后文件不存在"
                decrypted_size = os.path.getsize(decrypted_video_path)
                if decrypted_size < 1024:
                    return False, f"视频解密后文件过小：{decrypted_size}字节"
                logger.info(f"视频解密成功：{decrypted_video_path}")
            else:
                logger.info("视频未加密，直接使用原始文件")
            
            if audio_path:
                is_audio_encrypted, audio_encryption_type = self._check_encryption(audio_path)
                if is_audio_encrypted:
                    logger.info(f"检测到音频被{audio_encryption_type}加密，尝试解密")
                    decrypted_audio_path = audio_path + '.decrypted'
                    await self._decrypt_with_bento4(audio_path, decrypted_audio_path, kid)
                    if not os.path.exists(decrypted_audio_path):
                        return False, "音频解密后文件不存在"
                    decrypted_size = os.path.getsize(decrypted_audio_path)
                    if decrypted_size < 1024:
                        return False, f"音频解密后文件过小：{decrypted_size}字节"
                    logger.info(f"音频解密成功：{decrypted_audio_path}")
            
            ffmpeg_exec = shutil.which('ffmpeg')
            logger.debug(f"系统环境变量中的ffmpeg路径：{ffmpeg_exec}")
            
            if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                ffmpeg_exec = self.ffmpeg_local
                logger.debug(f"本地ffmpeg路径：{ffmpeg_exec}")
                if not os.path.exists(ffmpeg_exec):
                    logger.error(f"未找到ffmpeg！本地路径不存在：{ffmpeg_exec}")
                    return False, "未找到ffmpeg！请安装并添加到系统环境变量，或放在./ffmpeg/bin目录下"

            logger.debug(f"使用的ffmpeg路径：{ffmpeg_exec}")
            
            # 检测视频编码
            video_codec = self._get_video_codec(decrypted_video_path, ffmpeg_exec)
            logger.info(f"视频编码：{video_codec}")
            
            # 检测输出格式
            output_ext = os.path.splitext(output_path)[1].lower()
            is_amv = output_ext == '.amv'
            
            # 需要转换编码的情况：AV1或HEVC
            need_conversion = video_codec in ['av1', 'hevc', 'h265']
            
            # 根据是否有音频文件构建不同的命令
            if decrypted_audio_path:
                if is_amv:
                    # AMV格式需要使用amv编码器和adpcm_ima_amv音频编码
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                        '-i', decrypted_audio_path,
                        '-c:v', 'amv',
                        '-c:a', 'adpcm_ima_amv',  # AMV需要使用adpcm_ima_amv音频编码
                        '-ar', '22050',  # AMV需要22050Hz采样率
                        '-ac', '1',  # AMV只支持单声道音频
                        '-block_size', '735',  # AMV需要特定的音频块大小（根据FFmpeg推荐）
                        '-strict', '-1',  # 允许实验性功能
                        '-shortest',
                        '-loglevel', 'error',
                        '-y',
                        output_path
                    ]
                else:
                    if need_conversion:
                        # 需要转换编码为H.264，确保Windows播放器支持
                        logger.info("检测到不支持的视频编码，自动转换为H.264")
                        cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                            '-i', decrypted_audio_path,
                            '-c:v', 'libx264',
                            '-preset', 'medium',
                            '-crf', '23',
                            '-c:a', 'copy',
                            '-shortest',
                            '-loglevel', 'error',
                            '-y',
                            output_path
                        ]
                    else:
                        # 其他格式可以直接复制编码
                        cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                            '-i', decrypted_audio_path,
                            '-c:v', 'copy',
                            '-c:a', 'copy',
                            '-shortest',
                            '-loglevel', 'error',
                            '-y',
                            output_path
                        ]
            else:
                if is_amv:
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                        '-c:v', 'amv',
                        '-loglevel', 'error',
                        '-y',
                        output_path
                    ]
                else:
                    if need_conversion:
                        # 需要转换编码为H.264，确保Windows播放器支持
                        logger.info("检测到不支持的视频编码，自动转换为H.264")
                        cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                            '-c:v', 'libx264',
                            '-preset', 'medium',
                            '-crf', '23',
                            '-loglevel', 'error',
                            '-y',
                            output_path
                        ]
                    else:
                        cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                            '-c:v', 'copy',
                            '-loglevel', 'error',
                            '-y',
                            output_path
                        ]

            logger.debug(f"执行ffmpeg命令：{' '.join(cmd)}")
            
            try:
                # 使用bytes模式而不是text模式，避免编码错误
                result = subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    shell=False,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                logger.debug(f"ffmpeg执行成功，返回码：{result.returncode}")
                # 尝试解码输出，忽略错误
                try:
                    stdout = result.stdout.decode('utf-8', errors='ignore')
                    stderr = result.stderr.decode('utf-8', errors='ignore')
                    if stdout:
                        logger.debug(f"ffmpeg stdout：{stdout}")
                    if stderr:
                        logger.debug(f"ffmpeg stderr：{stderr}")
                except Exception as decode_e:
                    logger.warning(f"解码输出时发生错误：{str(decode_e)}")
            except OSError as e:
                logger.error(f"执行ffmpeg时发生系统错误：{str(e)}")
                logger.error(f"命令：{' '.join(cmd)}")
                logger.error(f"当前工作目录：{os.getcwd()}")
                logger.error(f"ffmpeg路径是否存在：{os.path.exists(ffmpeg_exec)}")
                logger.error(f"ffmpeg是否可执行：{os.access(ffmpeg_exec, os.X_OK)}")
                logger.error(f"视频文件是否存在：{os.path.exists(decrypted_video_path)}")
                logger.error(f"音频文件是否存在：{os.path.exists(decrypted_audio_path)}")
                
                try:
                    logger.info("尝试使用shell=True执行ffmpeg命令")
                    cmd_str = ' '.join(cmd)
                    logger.debug(f"执行命令：{cmd_str}")
                    # 使用bytes模式而不是text模式，避免编码错误
                    result = subprocess.run(
                        cmd_str,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        shell=True,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    logger.debug(f"ffmpeg执行成功，返回码：{result.returncode}")
                    # 尝试解码输出，忽略错误
                    try:
                        stdout = result.stdout.decode('utf-8', errors='ignore')
                        stderr = result.stderr.decode('utf-8', errors='ignore')
                        if stdout:
                            logger.debug(f"ffmpeg stdout：{stdout}")
                        if stderr:
                            logger.debug(f"ffmpeg stderr：{stderr}")
                    except Exception as decode_e:
                        logger.warning(f"解码输出时发生错误：{str(decode_e)}")
                except Exception as shell_e:
                    logger.error(f"使用shell=True执行也失败：{str(shell_e)}")
                    return False, f"执行ffmpeg失败：{str(shell_e)}"
            
            if decrypted_video_path != video_path and os.path.exists(decrypted_video_path):
                try:
                    os.remove(decrypted_video_path)
                    logger.debug(f"清理临时视频文件：{decrypted_video_path}")
                except Exception as e:
                    logger.warning(f"清理临时视频文件失败：{str(e)}")
            
            if decrypted_audio_path != audio_path and os.path.exists(decrypted_audio_path):
                try:
                    os.remove(decrypted_audio_path)
                    logger.debug(f"清理临时音频文件：{decrypted_audio_path}")
                except Exception as e:
                    logger.warning(f"清理临时音频文件失败：{str(e)}")
            
            temp_files_to_clean = []
            if decrypted_video_path != video_path:
                temp_files_to_clean.append(decrypted_video_path)
            if decrypted_audio_path != audio_path:
                temp_files_to_clean.append(decrypted_audio_path)
            
            for temp_file in temp_files_to_clean:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.debug(f"清理临时文件成功：{temp_file}")
                    except Exception as e:
                        logger.warning(f"清理临时文件失败：{temp_file} - {str(e)}")

            logger.debug(f"音视频合并完成：{output_path}")
            return True, ""
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg执行失败：返回码={e.returncode}, 标准错误={e.stderr}, 标准输出={e.stdout}")
            return False, f"ffmpeg执行失败：{e.stderr}"
        except Exception as e:
            logger.error(f"音视频合并失败：{str(e)}", exc_info=True)
            return False, f"音视频合并失败：{str(e)}"



    @staticmethod
    def _sanitize_filename(filename):
        invalid_chars = r'[\/:*?"<>|]'
        return re.sub(invalid_chars, '_', filename).strip()

    @staticmethod
    def _format_duration(duration):
        
        if duration > 1000:
            seconds = duration // 1000
        else:
            seconds = duration
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"