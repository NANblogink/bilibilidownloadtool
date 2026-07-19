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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
import logging
from Crypto.Cipher import PKCS1_OAEP
from Crypto.Hash import SHA1
from wbi_sign import WbiSign
from api_request import ApiRequest
from video_parser import VideoParser
import requests
from platform_utils import IS_MACOS, IS_WINDOWS, exe, subprocess_no_window_kwargs, subprocess_low_priority_kwargs, hide_file, get_bento4_sdk_dirname, has_non_ascii, to_short_path, get_safe_temp_dir

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

KID_REGEX = {
    'bilidrm_uri': re.compile(r'uri:bili://([0-9a-f]{32})', re.IGNORECASE),
    'url_param': re.compile(r'kid=([0-9a-fA-F]{32})')
}

KID_CACHE = {}
KID_CACHE_EXPIRY = 3600  # 1小时
# 多线程并发访问保护（批量下载使用ThreadPoolExecutor，多任务可能同时读写缓存）
KID_CACHE_LOCK = threading.Lock()

# DRM密钥缓存：kid -> (key, timestamp)，避免同一KID重复请求DRM API
DRM_KEY_CACHE = {}
DRM_KEY_CACHE_EXPIRY = 3600  # 1小时（DRM密钥通常有效期较长）
# 多线程并发访问保护（同上）
DRM_KEY_CACHE_LOCK = threading.Lock()


def _decode_subprocess_output(data):
    """解码子进程输出（stderr/stdout），自动处理Windows GBK编码。

    Windows上ffmpeg/mp4decrypt等工具的输出使用系统编码（GBK），
    如果用UTF-8解码会导致中文路径被丢弃，错误信息不可读。
    """
    if not data:
        return ''
    # 优先尝试GBK（Windows默认），失败则回退到UTF-8
    for encoding in ('gbk', 'utf-8'):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode('utf-8', errors='replace')


class SimpleBiliDRM:
    # DRM请求超时（秒）：公钥获取和密钥请求共用
    _REQUEST_TIMEOUT = 15

    def __init__(self):
        self._key = self.generate_random_bytes(16)
        self._iv = self.generate_random_bytes(16)
        self._public_key = None
        self.session = None
        
        self.api_url = "http://bvc-drm.bilivideo.com/bilidrm"
        self.pub_key_url = "http://bvc-drm.bilivideo.com/cer/bilidrm_pub.key"

    async def __aenter__(self):
        import aiohttp
        try:
            self.session = aiohttp.ClientSession(headers={
                'origin': 'https://www.bilibili.com',
                'referer': 'https://www.bilibili.com/',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
                'Content-Type': 'application/json'
            })
            self._public_key = await self.get_public_key()
            if not self._public_key or len(self._public_key) < 64:
                raise Exception(f"公钥获取失败或格式无效（长度={len(self._public_key) if self._public_key else 0}）")
            return self
        except Exception:
            # 初始化失败时确保session被关闭，避免资源泄漏
            if self.session and not self.session.closed:
                await self.session.close()
            raise

    async def __aexit__(self, *args):
        if self.session and not self.session.closed:
            await self.session.close()

    @staticmethod
    def generate_random_bytes(length):
        return os.urandom(length)

    async def get_public_key(self):
        import aiohttp
        try:
            async with self.session.get(self.pub_key_url, timeout=aiohttp.ClientTimeout(total=self._REQUEST_TIMEOUT)) as resp:
                if resp.status != 200:
                    raise Exception(f"获取公钥失败，HTTP状态码: {resp.status}")
                public_key = await resp.read()
                return public_key
        except asyncio.TimeoutError:
            raise Exception(f"获取公钥超时（{self._REQUEST_TIMEOUT}秒）")
        except aiohttp.ClientError as e:
            raise Exception(f"获取公钥网络错误: {str(e)}")

    def encrypt_kid(self, kid):
        aes_ecb = AES.new(self._key, AES.MODE_ECB)
        enc_kid = aes_ecb.encrypt(kid[:16])
        
        salt = bytes([0x1b, 0xf7, 0xf5, 0x3f, 0x5d, 0x5d, 0x5a, 0x1f, 0x00, 0x00, 0x00, 0x20, 0x00, 0x00, 0x00, 0x20])
        kid_bytes = salt + enc_kid + kid[16:]
        
        aes_cbc = AES.new(self._key, AES.MODE_CBC, self._iv)
        encrypted_kid = aes_cbc.encrypt(kid_bytes)
        return encrypted_kid

    def encrypt_key(self):
        if not self._public_key:
            raise Exception("公钥未初始化，无法加密密钥")
        public_key = RSA.import_key(self._public_key)
        cipher_rsa = PKCS1_OAEP.new(public_key, hashAlgo=SHA1)
        encrypted = cipher_rsa.encrypt(self._key)
        return encrypted

    @staticmethod
    def _normalize_kid(kid):
        """将KID统一转换为32字节ASCII形式

        B站DRM协议要求KID为32字节ASCII（hex字符串的字节表示）。
        此方法智能处理两种输入:
        - 32字符hex字符串 → 直接encode()为32字节
        - 16字节二进制 → 转为32字符hex字符串再encode()为32字节
        - 其它长度 → 截断或补0到32字节
        """
        if isinstance(kid, str):
            if len(kid) == 32 and all(c in '0123456789abcdefABCDEF' for c in kid):
                return kid.encode('ascii')
            kid_bytes = kid.encode('utf-8')
        elif isinstance(kid, (bytes, bytearray)):
            kid_bytes = bytes(kid)
            if len(kid_bytes) == 16:
                return kid_bytes.hex().encode('ascii')
        else:
            kid_bytes = str(kid).encode('utf-8')

        if len(kid_bytes) > 32:
            return kid_bytes[:32]
        if len(kid_bytes) < 32:
            return kid_bytes.ljust(32, b'\x00')
        return kid_bytes

    def encrypt_spc(self, kid):
        content_key_ctx = self.encrypt_kid(kid)
        sha_digest = hashlib.sha1(self._public_key).digest()
        
        timestamp = int(time.time())
        
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
        # 统一规范化KID为32字节ASCII形式（兼容hex字符串和二进制两种输入）
        kid_bytes = self._normalize_kid(kid)

        # 缓存键统一基于规范化后的kid_bytes生成
        # 这样同一KID的不同输入格式（str/bytes/带连字符UUID）都能命中同一缓存
        cache_key = kid_bytes.decode('ascii', errors='ignore').lower()
        # 防御：空cache_key会导致不同无效KID共享缓存，此时跳过缓存
        if not cache_key or not all(c in '0123456789abcdef' for c in cache_key):
            logger.warning(f"KID规范化后非合法hex，跳过缓存：{cache_key!r}")
            cache_key = None

        # 读取缓存时加锁，避免与其他线程并发写入冲突
        if cache_key is not None:
            with DRM_KEY_CACHE_LOCK:
                if cache_key in DRM_KEY_CACHE:
                    cached_key, timestamp = DRM_KEY_CACHE[cache_key]
                    if time.time() - timestamp < DRM_KEY_CACHE_EXPIRY:
                        logger.info(f"从缓存中获取DRM密钥: {cached_key}（KID={cache_key}）")
                        return cached_key
                    else:
                        del DRM_KEY_CACHE[cache_key]

        spc = self.encrypt_spc(kid_bytes)

        payload = {"spc": spc}

        try:
            import aiohttp
            try:
                async with self.session.post(self.api_url, json=payload,
                                             timeout=aiohttp.ClientTimeout(total=self._REQUEST_TIMEOUT)) as resp:
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
            except asyncio.TimeoutError:
                raise Exception(f"DRM API请求超时（{self._REQUEST_TIMEOUT}秒）")
            except aiohttp.ClientError as e:
                raise Exception(f"DRM API网络错误: {str(e)}")

            ckc = response.get("ckc")
            if not ckc:
                logger.error(f"响应中未找到ckc字段，响应内容: {response}")
                ckc = response.get("data", {}).get("ckc")
                if not ckc:
                    raise Exception(f"响应中未找到ckc字段，响应: {response}")

            ckc_bytes = base64.b64decode(ckc)

            _MIN_CKC_LEN = 52
            if len(ckc_bytes) < _MIN_CKC_LEN:
                raise Exception(f"ckc响应过短: {len(ckc_bytes)}字节（最小需要{_MIN_CKC_LEN}字节）")

            offset = 12
            offset += 4  # time_bytes
            iv = ckc_bytes[offset:offset+16]
            offset += 16
            data_len = int.from_bytes(ckc_bytes[offset:offset+4], 'big')
            offset += 4

            if data_len <= 0 or data_len > 65536:
                raise Exception(f"ckc数据长度异常: {data_len}")
            if offset + data_len > len(ckc_bytes):
                raise Exception(f"ckc数据长度{data_len}超出实际数据范围(offset={offset}, 总长={len(ckc_bytes)})")

            data = ckc_bytes[offset:offset+data_len]

            if len(data) == 0 or len(data) % 16 != 0:
                raise Exception(f"ckc数据长度{len(data)}不是16的倍数，无法CBC解密")

            aes_cbc = AES.new(self._key, AES.MODE_CBC, iv)
            decrypted = aes_cbc.decrypt(data)

            aes_ecb = AES.new(self._key, AES.MODE_ECB)
            final_key = aes_ecb.decrypt(decrypted[-16:])

            result_key = final_key.hex()
            logger.info(f"成功获取DRM密钥: {result_key}")

            # 写入密钥缓存（加锁，避免并发写入冲突）
            # 仅当cache_key合法时才缓存，避免无效KID污染缓存
            if cache_key is not None:
                with DRM_KEY_CACHE_LOCK:
                    DRM_KEY_CACHE[cache_key] = (result_key, time.time())
                    # 清理过期缓存
                    current_time = time.time()
                    expired_keys = [k for k, (_, ts) in DRM_KEY_CACHE.items()
                                  if current_time - ts >= DRM_KEY_CACHE_EXPIRY]
                    for k in expired_keys:
                        del DRM_KEY_CACHE[k]

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
        
        self.wbi_sign = WbiSign()
        self.api_request = ApiRequest(self.session)
        self.video_parser = VideoParser()

        import sys
        if getattr(sys, 'frozen', False):
            self.current_dir = os.path.dirname(sys.executable)
        elif hasattr(sys, '_MEIPASS'):
            self.current_dir = sys._MEIPASS
        else:
            self.current_dir = os.path.dirname(os.path.abspath(__file__))

        # 预计算ASCII安全的临时目录，用于C++工具(mp4decrypt/ffmpeg/ffprobe)调用时避免中文路径问题
        # 解决中文用户名/中文安装路径导致的工具崩溃和解密失败
        self.safe_temp_dir = get_safe_temp_dir(self.current_dir, "temp")
        
        if hasattr(sys, '_MEIPASS'):
            self.cookie_path = os.path.join(os.getcwd(), cookie_path)
        else:
            self.cookie_path = os.path.join(self.current_dir, cookie_path)
        
        self.tool_manager = None
        self.using_system_tools = False
        if get_tool_manager is not None:
            try:
                self.tool_manager = get_tool_manager()
                tool_status = self.tool_manager.check_tools_installed()
                if tool_status['ffmpeg_exists'] and tool_status['bento4_exists']:
                    self.ffmpeg_local = tool_status['ffmpeg_path']
                    self.bento4_dir = tool_status['bento4_path'].replace(os.sep + exe('mp4decrypt'), '')
                    self.using_system_tools = True
                    logger.info(f"使用已安装的工具: FFmpeg={self.ffmpeg_local}, Bento4={self.bento4_dir}")
                else:
                    self._setup_old_paths()
            except Exception as e:
                logger.warning(f"工具管理器初始化失败: {str(e)}, 使用旧逻辑")
                self._setup_old_paths()
        else:
            self._setup_old_paths()

        self._session_ready = threading.Event()
        self._init_session_lightweight()
        # 网络部分（获取buvid3/sid）延迟到后台执行，不阻塞启动
        threading.Thread(target=self._init_session_network, daemon=True).start()
    
    def _wait_session_ready(self, timeout=None):
        """等待session网络初始化完成（按需阻塞）"""
        if not self._session_ready.is_set():
            logger.debug("等待session网络初始化...")
            self._session_ready.wait(timeout=timeout)
    
    def _init_session_lightweight(self):
        """轻量级session初始化（无网络请求，毫秒级完成）"""
        headers = self.config.get_headers()
        self.session.headers.clear()
        self.session.headers.update(headers)
        
        self.cookies = self._load_cookies()
        logger.info(f"从文件加载的cookie：{self.cookies}")
        self.session.cookies.update(self.cookies)
        
        self.csrf_token = self.cookies.get('bili_jct', '')
        if self.csrf_token:
            self.session.headers.update({'X-CSRF-Token': self.csrf_token})
        
        self.session.verify = False
        self.session.proxies = {}  # 强制禁用代理
        self.session.trust_env = False  # 不读取系统代理（含注册表IE代理），让开梯子也能直连B站
        
        self._load_cached_wbi_keys()
        threading.Thread(target=self._update_wbi_keys).start()
        
        if 'bili_ticket' not in self.cookies:
            def _gen_ticket():
                try:
                    time.sleep(3)
                    self._generate_bili_ticket()
                except Exception as e:
                    logger.warning(f"预生成bili_ticket失败: {e}")
            threading.Thread(target=_gen_ticket, daemon=True).start()
    
    def _init_session_network(self):
        """session网络初始化（获取buvid3、sid等服务端cookie），在后台线程中执行"""
        try:
            _need_server_buvid3 = True
            for key in self.session.cookies.keys():
                val = self.session.cookies.get(key, '')
                if key == 'buvid3' and val and not val.startswith('XY'):
                    _need_server_buvid3 = False
                    break
            
            if _need_server_buvid3:
                try:
                    logger.info("_init_session: 正在从bilibili.com获取服务端签发的buvid3...")
                    _init_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
                    }
                    _init_resp = self.session.get('https://www.bilibili.com', headers=_init_headers, timeout=10, allow_redirects=True)
                    if _init_resp.cookies:
                        self.session.cookies.update(_init_resp.cookies)
                    for k, v in dict(self.session.cookies).items():
                        if 'buvid' in k.lower():
                            logger.info(f"  获取到服务端cookie: {k}={v[:30]}...")
                except Exception as e:
                    logger.warning(f"_init_session: 获取服务端buvid3失败: {e}")

            _has_sid = False
            for key in self.session.cookies.keys():
                if key == 'sid':
                    _has_sid = True
                    break
            if not _has_sid:
                try:
                    logger.info("_init_session: 正在从passport获取sid...")
                    _init_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
                    }
                    _passport_resp = self.session.get('https://passport.bilibili.com/login', headers=_init_headers, timeout=10, allow_redirects=True)
                    if _passport_resp.cookies:
                        self.session.cookies.update(_passport_resp.cookies)
                        for k, v in dict(_passport_resp.cookies).items():
                            logger.info(f"  获取到passport cookie: {k}={v[:30]}...")
                except Exception as e:
                    logger.warning(f"_init_session: 获取sid失败: {e}")
            
            logger.info(f"session cookie：{dict(self.session.cookies)}")
            
            # 同步获取WBI密钥，确保API请求时密钥已就绪
            try:
                _img_key, _ = self.wbi_sign.get_wbi_keys()
                if not _img_key or _img_key == 'img_key':
                    logger.info("WBI密钥为无效默认值，正在同步获取...")
                    if self._get_wbi_keys():
                        self._save_wbi_keys()
                        logger.info("WBI密钥同步获取成功")
            except Exception as e:
                logger.warning(f"同步获取WBI密钥失败: {e}")
        finally:
            self._session_ready.set()
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
    
    def _setup_old_paths(self):
        """使用旧的路径设置逻辑"""
        import sys
        if hasattr(sys, '_MEIPASS'):
            self.bento4_dir = os.path.join(self.current_dir, 'bento4', 'bin')
        else:
            self.bento4_dir = os.path.join(self.current_dir, 'bento4', get_bento4_sdk_dirname(), 'bin')
        
        self.ffmpeg_local = os.path.join(self.current_dir, 'ffmpeg', 'bin', exe('ffmpeg'))
        
        # 检查工具是否存在，并尝试多个可能的路径
        self._check_and_fix_paths()
    
    def _check_and_fix_paths(self):
        """检查必要工具是否存在，尝试多个可能的路径"""
        import sys
        
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None
        
        possible_bento4_paths = []
        if exe_dir:
            _internal_dir = os.path.join(exe_dir, '_internal')
            possible_bento4_paths.append(os.path.join(_internal_dir, 'bento4', get_bento4_sdk_dirname(), 'bin'))
            possible_bento4_paths.append(os.path.join(_internal_dir, 'bento4', 'bin'))
            possible_bento4_paths.append(os.path.join(exe_dir, 'bento4', get_bento4_sdk_dirname(), 'bin'))
            possible_bento4_paths.append(os.path.join(exe_dir, 'bento4', 'bin'))
        if hasattr(sys, '_MEIPASS'):
            possible_bento4_paths.append(os.path.join(sys._MEIPASS, 'bento4', 'bin'))
            possible_bento4_paths.append(os.path.join(sys._MEIPASS, 'bento4', get_bento4_sdk_dirname(), 'bin'))
        possible_bento4_paths.append(self.bento4_dir)
        possible_bento4_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', 'bin'))
        possible_bento4_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bento4', get_bento4_sdk_dirname(), 'bin'))
        possible_bento4_paths.append(os.path.join(os.getcwd(), 'bento4', 'bin'))
        possible_bento4_paths.append(os.path.join(os.getcwd(), 'bento4', get_bento4_sdk_dirname(), 'bin'))
        
        found_bento4 = False
        for path in possible_bento4_paths:
            test_path = os.path.join(path, exe('mp4decrypt'))
            if os.path.exists(test_path):
                self.bento4_dir = path
                found_bento4 = True
                logger.info(f"找到Bento4工具：{path}")
                break
        
        if not found_bento4:
            logger.warning("未找到Bento4工具，解密功能可能无法正常工作")
        
        possible_ffmpeg_paths = []
        if exe_dir:
            _internal_dir = os.path.join(exe_dir, '_internal')
            possible_ffmpeg_paths.append(os.path.join(_internal_dir, 'ffmpeg', 'bin', exe('ffmpeg')))
            possible_ffmpeg_paths.append(os.path.join(exe_dir, 'ffmpeg', 'bin', exe('ffmpeg')))
        if hasattr(sys, '_MEIPASS'):
            possible_ffmpeg_paths.append(os.path.join(sys._MEIPASS, 'ffmpeg', 'bin', exe('ffmpeg')))
        possible_ffmpeg_paths.append(self.ffmpeg_local)
        possible_ffmpeg_paths.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ffmpeg', 'bin', exe('ffmpeg')))
        possible_ffmpeg_paths.append(os.path.join(os.getcwd(), 'ffmpeg', 'bin', exe('ffmpeg')))
        
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
                'exists': os.path.exists(os.path.join(self.bento4_dir, exe('mp4decrypt'))),
                'path': os.path.join(self.bento4_dir, exe('mp4decrypt'))
            },
            'bento4_dir': {
                'exists': os.path.exists(self.bento4_dir),
                'path': self.bento4_dir
            }
        }
        return status

    def _init_session(self):
        """完整的session初始化（同步，用于登录后重初始化）"""
        self._session_ready.clear()
        self._init_session_lightweight()
        self._init_session_network()
    
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
                # 跳过无效的默认值
                if img_key and sub_key and img_key != 'img_key' and sub_key != 'sub_key':
                    self.wbi_sign.set_wbi_keys(img_key, sub_key)
                    logger.debug(f"从缓存加载Wbi密钥成功：img_key={img_key[:8]}..., sub_key={sub_key[:8]}...")
                else:
                    logger.warning(f"缓存中的WBI密钥为无效默认值，将重新获取")
        except Exception as e:
            logger.error(f"加载Wbi缓存失败：{str(e)}")
    
    def _save_wbi_keys(self):
        try:
            img_key, sub_key = self.wbi_sign.get_wbi_keys()
            # 不保存无效的默认值
            if not img_key or not sub_key or img_key == 'img_key' or sub_key == 'sub_key':
                logger.warning("WBI密钥为无效默认值，跳过保存")
                return
            cache_file = 'wbi_cache.json'
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
                # 检查是否需要更新：超过24小时、密钥为空、或密钥为无效默认值
                _img_key, _ = self.wbi_sign.get_wbi_keys()
                need_update = (
                    time.time() - self.wbi_sign.wbi_update_time > 86400
                    or not _img_key
                    or _img_key == 'img_key'  # 无效默认值
                )
                if need_update:
                    if self._get_wbi_keys():
                        self._save_wbi_keys()
            except Exception as e:
                logger.error(f"更新Wbi密钥失败：{str(e)}")
        
        threading.Thread(target=update_once, daemon=True).start()
        
        while True:
            time.sleep(3600)
            threading.Thread(target=update_once, daemon=True).start()  
    
    def _generate_wbi_sign(self, params, with_dm_params=True):
        return self.wbi_sign._generate_wbi_sign(params, with_dm_params=with_dm_params)
    
    def _generate_bili_ticket(self):
        try:
            timestamp = int(time.time())
            key = "XgwSnGZ1p"
            message = f"ts{timestamp}"
            hexsign = hmac.new(key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
            
            params = {
                "key_id": "ec02",
                "hexsign": hexsign,
                "context[ts]": str(timestamp),
                "csrf": self.csrf_token if self.csrf_token else ''
            }
            
            url = "https://api.bilibili.com/bapis/bilibili.api.ticket.v1.Ticket/GenWebTicket"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*'
            }
            
            response = self.session.post(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0:
                ticket = data.get('data', {}).get('ticket', '')
                if ticket:
                    logger.debug("生成 bili_ticket 成功")
                    self.cookies['bili_ticket'] = ticket
                    self.session.cookies.update({'bili_ticket': ticket})
                    
                    nav_data = data.get('data', {}).get('nav', {})
                    if nav_data:
                        img_url = nav_data.get('img', '')
                        sub_url = nav_data.get('sub', '')
                        if img_url and sub_url:
                            img_key = img_url.rsplit('/', 1)[-1].split('.')[0]
                            sub_key = sub_url.rsplit('/', 1)[-1].split('.')[0]
                            if hasattr(self, 'wbi_sign') and self.wbi_sign:
                                self.wbi_sign.set_wbi_keys(img_key, sub_key)
                                logger.debug(f"从bili_ticket响应更新WBI密钥: img={img_key[:8]}..., sub={sub_key[:8]}...")
                    return ticket
            
            logger.error(f"生成 bili_ticket 失败：{data.get('code')}: {data.get('message', '未知错误')}")
            return None
        except Exception as e:
            logger.error(f"生成 bili_ticket 失败：{str(e)}")
            return None
    
    def _get_v_voucher(self, url, params=None):
        return None
    
    def _handle_v_voucher(self, v_voucher):
        try:
            if not v_voucher:
                return None
            
            logger.info(f"处理 v_voucher: {v_voucher[:30]}...")
            
            register_url = "https://api.bilibili.com/x/gaia-vgate/v1/register"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            register_data = {
                'csrf': self.csrf_token if self.csrf_token else '',
                'v_voucher': v_voucher
            }
            
            resp = self.session.post(register_url, data=register_data, headers=headers, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get('code') != 0:
                logger.warning(f"v_voucher register 失败: {result.get('message', '未知错误')}")
                return None
            
            data = result.get('data', {})
            captcha_type = data.get('type', '')
            token = data.get('token', '')
            
            if captcha_type == 'geetest':
                geetest = data.get('geetest')
                if not geetest:
                    logger.warning("v_voucher geetest 数据为空，该风控无法通过 captcha 解除")
                    return None
                
                gt = geetest.get('gt', '')
                challenge = geetest.get('challenge', '')
                
                logger.info(f"v_voucher 需要极验验证，gt={gt[:16]}..., challenge={challenge[:16]}...")
                
                if hasattr(self, 'v_voucher_callback') and self.v_voucher_callback:
                    captcha_result = self.v_voucher_callback({
                        'type': 'geetest',
                        'gt': gt,
                        'challenge': challenge,
                        'token': token
                    })
                    
                    if captcha_result and isinstance(captcha_result, dict):
                        validate_val = captcha_result.get('validate', '')
                        seccode_val = captcha_result.get('seccode', '')
                        
                        if validate_val and seccode_val:
                            validate_url = "https://api.bilibili.com/x/gaia-vgate/v1/validate"
                            validate_data = {
                                'csrf': self.csrf_token if self.csrf_token else '',
                                'challenge': challenge,
                                'token': token,
                                'validate': validate_val,
                                'seccode': seccode_val
                            }
                            
                            resp2 = self.session.post(validate_url, data=validate_data, headers=headers, timeout=15)
                            resp2.raise_for_status()
                            validate_result = resp2.json()
                            
                            if validate_result.get('code') == 0:
                                grisk_id = validate_result.get('data', {}).get('grisk_id', '')
                                if grisk_id:
                                    logger.info(f"v_voucher 验证成功，获取 grisk_id: {grisk_id[:16]}...")
                                    self.cookies['x-bili-gaia-vtoken'] = grisk_id
                                    self.session.cookies.update({'x-bili-gaia-vtoken': grisk_id})
                                    return grisk_id
                            else:
                                logger.warning(f"v_voucher validate 失败: {validate_result.get('message', '未知错误')}")
                else:
                    logger.warning("v_voucher 需要极验验证，但未设置回调函数，无法自动处理")
            else:
                logger.warning(f"v_voucher 验证类型不支持: {captcha_type}")
            
            return None
        except Exception as e:
            logger.error(f"处理 v_voucher 失败：{str(e)}")
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
                            name = item.get('name', '')
                            value = item.get('value', '')
                            if self._is_valid_cookie_kv(name, value):
                                cookies[name.strip()] = value.strip()
                            elif name:  # 有key但验证失败
                                logger.warning(f"加载到无效cookie被跳过: key={str(name)[:30]}..., value长度={len(str(value))}")
                    else:
                        for item in cookie_data:
                            if isinstance(item, dict) and 'name' in item and 'value' in item:
                                name = item['name']
                                value = item['value']
                                if self._is_valid_cookie_kv(name, value):
                                    cookies[name.strip()] = value.strip()
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

            # 过滤无效的cookie键值对（防止污染数据被保存）
            cookies = {k: v for k, v in cookies.items() if self._is_valid_cookie_kv(k, v)}
            if not cookies:
                raise ValueError("没有有效的cookie可保存（所有cookie数据均未通过验证）")

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
            self._api_cache.clear()
            return True
        except Exception as e:
            print(f"Cookie保存失败：{str(e)}")
            return False

    def _is_valid_cookie_kv(self, key, value):
        """检查cookie键值对是否有效，过滤被日志等数据污染的脏数据"""
        if not isinstance(key, str) or not isinstance(value, str):
            return False
        # 键名必须是简单的英文/数字/下划线组合（B站cookie格式）
        if not key or len(key) > 100 or not re.match(r'^[a-zA-Z0-9_]+$', key):
            return False
        # 值不能包含换行、管道符等日志特征字符
        if '\n' in value or '\r' in value or '| DEBUG' in value or '| INFO' in value or '| WARNING' in value or '| ERROR' in value:
            return False
        # 值不能太长（B站单个cookie值一般不超过500字符）
        if len(value) > 1000:
            return False
        # 值不能是Python dict或list片段
        if value.startswith('{') or value.startswith('['):
            return False
        return True

    def _parse_cookie_text(self, cookie_text):
        cookie_dict = {}
        if not cookie_text.strip():
            return cookie_dict

        text = cookie_text.strip()

        # 预检：如果文本包含明显的日志污染特征，直接拒绝
        if '| DEBUG' in text or '| INFO' in text or '| WARNING' in text or '| ERROR' in text or 'Login poll response' in text:
            logger.warning(f"Cookie文本包含日志数据污染，已忽略。文本前50字符: {text[:50]}")
            return cookie_dict

        # 尝试解析 Python dict 格式: {'key': 'value', ...} 或 {"key": "value", ...}
        if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
            try:
                import ast
                parsed = ast.literal_eval(text)
                if isinstance(parsed, dict):
                    for k, v in parsed.items():
                        if self._is_valid_cookie_kv(k, v):
                            cookie_dict[k.strip()] = v.strip()
                    if cookie_dict:
                        logger.info(f"通过ast.literal_eval解析到{len(cookie_dict)}个cookie")
                        return cookie_dict
                elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                    for item in parsed:
                        if isinstance(item, dict) and 'name' in item and 'value' in item:
                            if self._is_valid_cookie_kv(item['name'], item['value']):
                                cookie_dict[item['name'].strip()] = item['value'].strip()
                    if cookie_dict:
                        logger.info(f"通过ast.literal_eval(list)解析到{len(cookie_dict)}个cookie")
                        return cookie_dict
            except Exception:
                pass

            # ast 失败，尝试用正则提取 key: value 对
            import re
            dict_pattern = re.compile(r"['\"](\w+)['\"]\s*:\s*['\"]([^'\"]*)['\"]")
            matches = dict_pattern.findall(text)
            if matches:
                for k, v in matches:
                    if self._is_valid_cookie_kv(k, v):
                        cookie_dict[k] = v
                if cookie_dict:
                    logger.info(f"通过正则提取到{len(cookie_dict)}个cookie(dict格式)")
                    return cookie_dict

        # 标准格式: key=value; key2=value2
        pairs = [pair.strip() for pair in text.split(';') if pair.strip()]
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                if self._is_valid_cookie_kv(key.strip(), value.strip()):
                    cookie_dict[key.strip()] = value.strip()
        return cookie_dict

    _api_cache = {}
    _cache_expiry = 300
    _cache_max_size = 100
    
    def _api_request(self, url, timeout=None, max_retries=None, use_wbi=False, params=None, use_cache=True, extra_headers=None, with_dm_params=True):
        try:
            # 从配置读取网络超时和重试设置（确保设置项生效）
            if timeout is None:
                timeout = self.config.get_app_setting("network_timeout", 15) if self.config else 15
                try:
                    timeout = int(timeout)
                except (ValueError, TypeError):
                    timeout = 15
            if max_retries is None:
                max_retries = self.config.get_app_setting("max_retry", 3) if self.config else 3
                try:
                    max_retries = int(max_retries)
                except (ValueError, TypeError):
                    max_retries = 3

            if not url or not isinstance(url, str):
                return False, {"error": "无效的API请求地址"}
            
            cache_key = self._generate_cache_key(url, params, use_wbi)
            
            if use_cache:
                cached_data = self._get_cached_data(cache_key)
                if cached_data:
                    return True, cached_data
            
            _BROWSER_HEADERS = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Origin': 'https://www.bilibili.com',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-site',
                'Sec-Ch-Ua': '"Not A(Brand";v="8", "Chromium";v="129", "Google Chrome";v="129"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
            }

            for retry in range(max_retries):
                try:
                    if params:
                        import urllib.parse
                        url_parts = list(urllib.parse.urlparse(url))
                        query = dict(urllib.parse.parse_qsl(url_parts[4]))
                        
                        query.pop('wts', None)
                        query.pop('w_rid', None)

                        for key, value in params.items():
                            if key not in query:
                                query[key] = value

                        if use_wbi:
                            signed_params = self._generate_wbi_sign(query, with_dm_params=with_dm_params)
                            query = signed_params

                        url_parts[4] = urllib.parse.urlencode(query, quote_via=urllib.parse.quote)
                        url = urllib.parse.urlunparse(url_parts)

                    logger.debug(f"发送API请求: {url}")

                    if not hasattr(self, 'session') or self.session is None:
                        self.session = requests.Session()
                        self.session.headers.update(_BROWSER_HEADERS)
                    else:
                        for k, v in _BROWSER_HEADERS.items():
                            if k not in self.session.headers or not self.session.headers[k]:
                                self.session.headers[k] = v
                    
                    self._enforce_request_interval()

                    # 临时应用额外请求头（如针对 space 的 Referer）
                    if extra_headers:
                        self.session.headers.update(extra_headers)

                    resp = self.session.get(url, timeout=timeout, proxies={}, allow_redirects=True, stream=False)

                    if resp.cookies:
                        self.session.cookies.update(resp.cookies)

                    if resp.status_code != 200:
                        logger.debug(f"API请求失败，状态码: {resp.status_code}, URL: {url}")
                        if resp.status_code == 412:
                            logger.warning("触发412风控（请求频率过高），等待后重试")
                            time.sleep(5 + retry * 5)
                            if retry < max_retries - 1:
                                continue
                            return False, {"error": "请求频率过高，请稍后再试"}
                        return False, {"error": f"请求错误（code={resp.status_code}）"}

                    content = resp.text.strip()
                    
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
                                if not self.cookies or 'SESSDATA' not in self.cookies:
                                    return False, {"error": "访问权限不足，请先登录"}
                                logger.warning(f"403权限不足，尝试刷新cookie后重试: {error_message}")
                                if retry < max_retries - 1:
                                    time.sleep(1 + retry)
                                    continue
                                return False, {"error": "访问权限不足，请确认登录状态"}
                            
                            elif code == -352:
                                logger.warning(f"风控校验失败(-352)：{error_message}，尝试自动处理")
                                v_voucher = data.get('data', {}).get('v_voucher', '')
                                if not v_voucher:
                                    v_voucher = resp.headers.get('x-bili-gaia-vvoucher', '')
                                if v_voucher:
                                    logger.info(f"从风控响应获取到 v_voucher: {v_voucher[:30]}...")
                                    grisk_id = self._handle_v_voucher(v_voucher)
                                    if grisk_id:
                                        if params is None:
                                            params = {}
                                        params['gaia_vtoken'] = grisk_id
                                else:
                                    self._generate_bili_ticket()
                                if retry < max_retries - 1:
                                    time.sleep(2 + retry)
                                    continue
                                return False, {"error": f"风控校验失败，请稍后再试（code=-352）"}

                            elif code == -799:
                                logger.warning(f"请求过于频繁(-799)：{error_message}")
                                wait_time = 8 * (2 ** retry) + random.randint(1, 5)
                                logger.info(f"-799重试等待{wait_time}秒...")
                                time.sleep(wait_time)
                                if retry < max_retries - 1:
                                    continue
                                return False, {"error": "请求过于频繁，请稍后再试"}

                            elif code == -509:
                                logger.warning(f"请求频率限制(-509)：{error_message}")
                                wait_time = 5 * (2 ** retry) + random.randint(1, 3)
                                logger.info(f"-509重试等待{wait_time}秒...")
                                time.sleep(wait_time)
                                if retry < max_retries - 1:
                                    continue
                                return False, {"error": "请求频率限制，请稍后再试"}

                            return False, {"error": f"API返回错误：{error_message}（code={code}）"}
                        
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
                            time.sleep(1 + retry * 0.5)
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

    _last_request_time = 0.0
    _min_request_interval = 0.3

    def _enforce_request_interval(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
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
        if len(self._api_cache) >= self._cache_max_size:
            self._clean_expired_cache()
            if len(self._api_cache) >= self._cache_max_size:
                oldest_key = min(self._api_cache, key=lambda k: self._api_cache[k]['timestamp'])
                del self._api_cache[oldest_key]
        self._api_cache[cache_key] = {
            'data': data,
            'timestamp': time.time()
        }
    
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
        _max_retry = self.config.get_app_setting("max_retry", 3) if self.config else 3
        try:
            _max_retry = int(_max_retry)
        except (ValueError, TypeError):
            _max_retry = 3
        success, result = self._api_request(api_url, timeout=10, max_retries=_max_retry, use_cache=False)
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
            
            resp = self.session.get(url, timeout=15, proxies={}, allow_redirects=True)
            
            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.debug(f"获取二维码更新会话cookies：{dict(resp.cookies)}")
            
            logger.info(f"获取二维码API响应状态码：{resp.status_code}")
            
            content = resp.text
            if not content or content.strip() == '':
                if resp.content:
                    try:
                        content = resp.content.decode('utf-8')
                    except:
                        pass
                if not content or content.strip() == '':
                    raise Exception("获取二维码失败：响应内容为空")
            
            if resp.status_code != 200:
                raise Exception(f"获取二维码失败：HTTP {resp.status_code}")
            
            try:
                data = json.loads(content)
                logger.info(f"解析后的JSON数据：{data}")
            except json.JSONDecodeError as e:
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
        except ImportError as e:
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
                self.session.headers.update(headers)
                resp = self.session.get(url, timeout=15, proxies={}, allow_redirects=True)
                
                if resp.cookies:
                    self.session.cookies.update(resp.cookies)
                    logger.debug(f"获取二维码更新会话cookies(no brotli)：{dict(resp.cookies)}")
                
                if resp.status_code != 200:
                    raise Exception(f"获取二维码失败：HTTP {resp.status_code}")
                
                try:
                    data = resp.json()
                except json.JSONDecodeError:
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
            import logging
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
            
            self.session.headers.update(headers)
            resp = self.session.get(url, timeout=10, proxies={}, allow_redirects=True)
            
            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.debug(f"轮询更新会话cookies：{dict(resp.cookies)}")
            
            if resp.status_code != 200:
                raise Exception(f"轮询登录状态失败：HTTP {resp.status_code}")
            
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
                risk_url = login_data.get('url', '')
                logger.debug(f"Risk detected: message={message}, url={risk_url}")
                return {
                    "success": False,
                    "status": message,
                    "code": code,
                    "url": risk_url,
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
            
            # B站QR登录成功时，cookie可能不在Set-Cookie中，而在crossDomain URL的查询参数里
            if not cookies and login_data.get('url'):
                try:
                    from urllib.parse import urlparse, parse_qs
                    cd_url = login_data['url']
                    parsed = urlparse(cd_url)
                    params = parse_qs(parsed.query, keep_blank_values=True)
                    if params:
                        # parse_qs 返回 list 值，取第一个
                        cookies = {k: v[0] for k, v in params.items()
                                   if k in ('DedeUserID', 'DedeUserID__ckMd5', 'SESSDATA',
                                            'bili_jct', 'sid', 'buvid3')}
                        if cookies:
                            logger.info(f"从crossDomain URL提取到cookie: {list(cookies.keys())}")
                except Exception as url_e:
                    logger.warning(f"解析crossDomain URL失败: {url_e}")
            
            if cookies:
                self.save_cookies(cookies)
                user_info = self.get_user_info()
                return {
                    "success": True,
                    "status": "登录成功",
                    "user_info": user_info
                }
            else:
                raise Exception("登录成功但未获取到cookie（resp.cookies为空且无法从crossDomain URL提取）")
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
                self.session.headers.update(headers)
                resp = self.session.get(url, timeout=10, proxies={}, allow_redirects=True)
                
                if resp.cookies:
                    self.session.cookies.update(resp.cookies)
                    logger.debug(f"轮询更新会话cookies(no brotli)：{dict(resp.cookies)}")
                
                if resp.status_code != 200:
                    raise Exception(f"轮询登录状态失败：HTTP {resp.status_code}")
                
                data = resp.json()
                code = data.get('code', 0)
                message = data.get('message', '')
                login_data = data.get('data', {})
                
                logger.debug(f"Login poll response (no brotli): code={code}, message={message}, data={login_data}")
                
                if "风险" in message or "验证" in message:
                    risk_url = login_data.get('url', '')
                    logger.debug(f"Risk detected (no brotli): message={message}, url={risk_url}")
                    return {
                        "success": False,
                        "status": message,
                        "code": code,
                        "url": risk_url,
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
                
                # B站QR登录成功时，cookie可能不在Set-Cookie中，而在crossDomain URL的查询参数里
                if not cookies and login_data.get('url'):
                    try:
                        from urllib.parse import urlparse, parse_qs
                        cd_url = login_data['url']
                        parsed = urlparse(cd_url)
                        params = parse_qs(parsed.query, keep_blank_values=True)
                        if params:
                            cookies = {k: v[0] for k, v in params.items()
                                       if k in ('DedeUserID', 'DedeUserID__ckMd5', 'SESSDATA',
                                                'bili_jct', 'sid', 'buvid3')}
                            if cookies:
                                logger.info(f"从crossDomain URL提取到cookie(no brotli): {list(cookies.keys())}")
                    except Exception as url_e:
                        logger.warning(f"解析crossDomain URL失败: {url_e}")
                
                if cookies:
                    self.save_cookies(cookies)
                    user_info = self.get_user_info()
                    return {
                        "success": True,
                        "status": "登录成功",
                        "user_info": user_info
                    }
                else:
                    raise Exception("登录成功但未获取到cookie（resp.cookies为空且无法从crossDomain URL提取）")
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

    def get_user_info(self, force_refresh=False):
        if not force_refresh and self.user_info and self.user_info['success']:
            return self.user_info

        api_url = self.config.get_api_url("login_status_api")
        if not api_url:
            return {"success": False, "msg": "配置错误：未找到用户信息API地址", "is_vip": False}

        success, result = self._api_request(api_url, use_cache=not force_refresh)
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
            session.trust_env = False

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
    
    @staticmethod
    def _format_duration(seconds):
        """将秒数转换为 MM:SS 或 HH:MM:SS"""
        try:
            seconds = int(seconds)
            if seconds < 0:
                return "00:00"
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"
        except Exception:
            return "00:00"

    def _parse_space_video_item(self, item):
        """将 Web 接口返回的单个视频对象转换为统一字典"""
        return {
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
        }

    def _parse_app_space_video_item(self, item, mid):
        """将 APP 接口返回的单个视频对象转换为统一字典"""
        return {
            "aid": item.get('param', ''),
            "bvid": item.get('bvid', ''),
            "title": item.get('title', ''),
            "pic": item.get('cover', ''),
            "description": item.get('subtitle', ''),
            "created": item.get('ctime', 0),
            "length": self._format_duration(item.get('duration', 0)),
            "play": item.get('play', 0),
            "video_review": item.get('danmaku', 0),
            "review": 0,
            "favorites": 0,
            "author": item.get('author', ''),
            "mid": mid
        }

    def _request_space_videos_web(self, mid, page, ps, use_wbi=True):
        """请求 Web 端单页空间视频，返回 (success, data/error)"""
        url = "https://api.bilibili.com/x/space/wbi/arc/search" if use_wbi else "https://api.bilibili.com/x/space/arc/search"
        params = {
            "mid": mid,
            "ps": ps,
            "pn": page,
            "tid": 0,
            "keyword": "",
            "order": "pubdate",
            "platform": "web",
            "order_avoided": "true",
            "special_type": ""
        }
        extra_headers = {'Referer': f'https://space.bilibili.com/{mid}/video'}
        return self._api_request(url, use_wbi=use_wbi, params=params, timeout=15, extra_headers=extra_headers)

    def _request_space_videos_app(self, mid, ps=30, aid=None, order="pubdate"):
        """请求 APP 端空间视频，返回 (success, data/error)"""
        url = "https://app.biliapi.com/x/v2/space/archive/cursor"
        params = {
            "vmid": mid,
            "ps": ps,
            "order": order,
            "mobi_app": "web",
            "platform": "web",
            "pn": 1,
            "pn_policy": 1,
            "c_locale": "zh_CN",
            "s_locale": "zh_CN"
        }
        if aid:
            params["aid"] = aid

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
            'Referer': f'https://space.bilibili.com/{mid}',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'https://space.bilibili.com'
        }

        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=15, proxies={})
            if resp.status_code != 200:
                return False, {"error": f"HTTP {resp.status_code}"}
            data = resp.json()
            if data.get('code') != 0:
                return False, {"error": data.get('message', f"code={data.get('code')}")}
            return True, data
        except Exception as e:
            return False, {"error": str(e)}

    def _load_space_videos_app(self, mid, ps=30, load_all=False, cancel_check=None, progress_callback=None):
        """使用 APP 接口加载空间视频"""
        all_videos = []
        total = 0
        aid = None
        has_next = True
        page = 1

        while has_next:
            if cancel_check and cancel_check():
                logger.info("用户取消加载更多视频")
                if progress_callback:
                    progress_callback("已取消加载")
                break

            if progress_callback and (load_all or page > 1):
                progress_callback(f"正在加载第 {page} 页 ({len(all_videos)}/{total if total else '?'} 个)...")

            success, data = self._request_space_videos_app(mid, ps=ps, aid=aid)
            if not success:
                logger.warning(f"APP 接口第 {page} 页加载失败：{data.get('error')}")
                break

            video_data = data.get('data', {}) or {}
            items = video_data.get('item', [])
            if not total:
                total = video_data.get('count', 0)

            for item in items:
                all_videos.append(self._parse_app_space_video_item(item, mid))

            has_next = video_data.get('has_next', False)
            if items and has_next:
                aid = items[-1].get('param')
            else:
                has_next = False

            page += 1

            if not load_all:
                break

        return all_videos, total

    def get_space_videos(self, mid, page=1, ps=30, load_all=False, cancel_check=None, progress_callback=None):
        """
        获取 UP 主空间视频列表。
        优先使用 Web WBI 接口（当前已通过 dm_img 参数修复风控），失败时回退到 APP 接口或非 WBI 接口。
        默认仅加载第一页并返回 total，load_all=True 时按需加载后续页。
        cancel_check 为可选的可调用对象，返回 True 时中断加载。
        """
        try:
            logger.info(f"获取UP主作品列表，mid: {mid}, page: {page}, load_all: {load_all}")

            # 优先使用 Web WBI 接口
            logger.info("尝试使用 Web WBI 接口获取作品列表")
            success, data = self._request_space_videos_web(mid, page, ps, use_wbi=True)
            if not success:
                logger.info(f"WBI 接口获取失败：{data.get('error')}，尝试非 WBI Web 接口")
                time.sleep(0.3)
                success, data = self._request_space_videos_web(mid, page, ps, use_wbi=False)

            # Web 接口均失败时回退到 APP 接口
            if not success:
                logger.info(f"Web 接口获取失败，回退到 APP 接口：{data.get('error')}")
                time.sleep(0.3)
                app_videos, app_total = self._load_space_videos_app(
                    mid, ps=ps, load_all=load_all,
                    cancel_check=cancel_check, progress_callback=progress_callback
                )
                if app_videos:
                    logger.info(f"APP 接口获取成功，共 {len(app_videos)} 个视频，总计 {app_total}")
                    return {
                        "success": True,
                        "videos": app_videos,
                        "page": page,
                        "ps": ps,
                        "total": app_total
                    }

            if not success:
                logger.error(f"获取作品列表失败：{data.get('error')}")
                return {"success": False, "error": data.get('error', '无法获取作品列表')}

            video_data = data.get('data', {}) or {}
            items = video_data.get('list', {}).get('vlist', []) if video_data else []
            total = (video_data.get('page', {}) or {}).get('count', 0) if video_data else 0

            all_videos = [self._parse_space_video_item(item) for item in items]
            logger.info(f"Web 接口第 {page} 页加载完成，本页 {len(all_videos)} 个，总计 {total} 个")

            if load_all and total > ps * page:
                import math
                total_pages = math.ceil(total / ps)
                if progress_callback:
                    progress_callback(f"共 {total} 个视频，开始加载全部...")

                for p in range(page + 1, total_pages + 1):
                    if cancel_check and cancel_check():
                        logger.info("用户取消加载更多视频")
                        if progress_callback:
                            progress_callback("已取消加载")
                        break

                    if progress_callback:
                        progress_callback(f"正在加载第 {p}/{total_pages} 页 ({len(all_videos)}/{total} 个)...")

                    p_success, p_data = self._request_space_videos_web(mid, p, ps, use_wbi=True)
                    if not p_success:
                        p_success, p_data = self._request_space_videos_web(mid, p, ps, use_wbi=False)

                    if p_success:
                        p_video_data = p_data.get('data', {}) or {}
                        p_items = p_video_data.get('list', {}).get('vlist', []) if p_video_data else []
                        all_videos.extend(self._parse_space_video_item(item) for item in p_items)
                        logger.info(f"已加载第 {p}/{total_pages} 页，累计 {len(all_videos)} 个视频")
                    else:
                        logger.warning(f"加载第 {p} 页失败：{p_data.get('error')}，跳过")

                if progress_callback:
                    progress_callback(f"加载完成！共 {len(all_videos)} 个视频")

            return {
                "success": True,
                "videos": all_videos,
                "page": page,
                "ps": ps,
                "total": total
            }
        except Exception as e:
            logger.error(f"获取UP主作品列表异常：{str(e)}")
            return {"success": False, "error": f"获取作品列表失败：{str(e)}"}

    def get_space_videos_page(self, mid, page=1, ps=30):
        """单独加载指定页的空间视频，供 UI 按需加载更多使用"""
        # 使用 Web WBI 接口加载指定页；APP 接口为游标分页，不适合按页加载
        success, data = self._request_space_videos_web(mid, page, ps, use_wbi=True)
        if not success:
            success, data = self._request_space_videos_web(mid, page, ps, use_wbi=False)

        if not success:
            return {"success": False, "error": data.get('error', '无法获取作品列表')}

        video_data = data.get('data', {}) or {}
        items = video_data.get('list', {}).get('vlist', []) if video_data else []
        total = (video_data.get('page', {}) or {}).get('count', 0) if video_data else 0
        return {
            "success": True,
            "videos": [self._parse_space_video_item(item) for item in items],
            "page": page,
            "ps": ps,
            "total": total
        }

    def check_hevc_support(self):
        try:
            # 优先使用程序自带的ffmpeg
            ffmpeg_exec = self.ffmpeg_local if self.ffmpeg_local and os.path.exists(self.ffmpeg_local) else shutil.which('ffmpeg')
            if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                self.hevc_supported = False
                return False

            cmd = [ffmpeg_exec, '-codecs']
            result = subprocess.run(cmd, capture_output=True, text=False, timeout=10,
                                   **subprocess_no_window_kwargs())
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
                    **subprocess_no_window_kwargs()
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

            # 中文路径适配：优先8.3短路径转换
            if has_non_ascii(video_path):
                short_path = to_short_path(video_path)
                if short_path != video_path:
                    video_path = short_path

            ffprobe_path = None
            ffmpeg_dir = os.path.dirname(self.ffmpeg_local)
            if ffmpeg_dir:
                candidate = os.path.join(ffmpeg_dir, exe('ffprobe'))
                if os.path.exists(candidate):
                    ffprobe_path = os.path.normpath(candidate)
            if not ffprobe_path:
                ffprobe_path = shutil.which('ffprobe')
                if ffprobe_path:
                    ffprobe_path = os.path.normpath(ffprobe_path)

            if not ffprobe_path:
                return {"compatible": True, "codec": "unknown", "reason": "无法检测编码"}

            cmd = [ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_streams', video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                                  **subprocess_no_window_kwargs())

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

    def _transcode_to_codec(self, input_path, output_path, target_codecid, ffmpeg_exec, progress_callback=None):
        """将视频转码到目标编码格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可与输入相同，会先写到临时文件再替换）
            target_codecid: 目标编码ID (7=H.264, 12=HEVC, 13=AV1)
            ffmpeg_exec: ffmpeg可执行文件路径
            progress_callback: 进度回调函数
        
        Returns:
            bool: 是否成功
        """
        import subprocess
        import tempfile
        import shutil

        codec_params = {
            7: {'encoder': 'libx264', 'name': 'H.264(AVC)', 'extra': []},
            12: {'encoder': 'libx265', 'name': 'H.265(HEVC)', 'extra': ['-tag:v', 'hvc1']},
            13: {'encoder': 'libaom-av1', 'name': 'AV1', 'extra': ['-cpu-used', '4', '-row-mt', '1']},
        }
        
        params = codec_params.get(target_codecid)
        if not params:
            logger.warning(f"不支持的转码目标编码: {target_codecid}")
            return False

        # 先检测源视频码率用于自适应CRF
        source_bitrate = self._get_video_bitrate(input_path, ffmpeg_exec)
        adaptive_crf = self._get_adaptive_crf(source_bitrate)
        codec_name = params['name']

        # 中文路径适配：优先8.3短路径转换输入文件，避免ffmpeg处理中文路径时崩溃
        actual_input = to_short_path(input_path) if has_non_ascii(input_path) else input_path
        if actual_input != input_path:
            logger.info(f"[转码] 输入文件使用8.3短路径：{actual_input}")

        # 写入临时文件再替换（避免覆盖源文件导致损坏）
        # 如果输出路径含中文，使用ASCII安全临时目录，转码后再移动到目标位置
        if has_non_ascii(output_path):
            temp_output = os.path.join(self.safe_temp_dir, f"transcode_{os.getpid()}_{int(time.time() * 1000) % 100000000}.mp4")
            need_move_output = True
        else:
            temp_output = output_path + '.transcoding.tmp'
            need_move_output = False
        
        cmd = [
            ffmpeg_exec,
            '-i', actual_input,
            '-c:v', params['encoder'],
            '-preset', 'medium',
            '-crf', str(adaptive_crf),
            *params['extra'],
            '-c:a', 'copy',
            '-y',
            temp_output
        ]
        
        logger.info(f"[转码] 开始转换到 {codec_name}: CRF={adaptive_crf}, 命令长度={len(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **subprocess_low_priority_kwargs()
            )

            total_duration = 0
            for line in process.stderr:
                line_str = line.decode('utf-8', errors='ignore').strip()
                if 'Duration:' in line_str:
                    parts = line_str.split()
                    for i, p in enumerate(parts):
                        if p == 'Duration:' and i + 1 < len(parts):
                            time_str = parts[i + 1]
                            h, m, s = time_str.split(':')
                            total_duration = int(h) * 3600 + int(m) * 60 + float(s)
                            break
                elif 'time=' in line_str and total_duration > 0 and progress_callback:
                    time_match = line_str.split('time=')[1].split()[0]
                    try:
                        h, m, s = time_str = time_match.split(':')
                        current_time = int(h) * 3600 + int(m) * 60 + float(s)
                        progress = min(current_time / total_duration * 100, 100)
                        progress_callback(progress)
                    except (ValueError, IndexError):
                        pass
            
            process.wait(timeout=3600)
            
            if process.returncode != 0:
                error_out = process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"[转码] 失败 (exit code={process.returncode}): {error_out[-500:]}")
                if os.path.exists(temp_output):
                    os.remove(temp_output)
                return False
            
            # 用临时文件替换输出文件
            if os.path.exists(temp_output):
                if os.path.exists(output_path):
                    os.remove(output_path)
                shutil.move(temp_output, output_path)
            
            logger.info(f"[转码] 成功转换为 {codec_name}")
            return True
            
        except Exception as e:
            logger.error(f"[转码] 异常: {e}")
            if os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except:
                    pass
            return False

    def convert_video_to_h264(self, input_path, output_path, progress_callback=None):
        try:
            import subprocess

            ffmpeg_path = self.ffmpeg_local
            if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                ffmpeg_path = os.path.normpath(ffmpeg_path)

            if not ffmpeg_path:
                return False, "未找到FFmpeg"

            if not progress_callback:
                def empty_progress(p):
                    pass
                progress_callback = empty_progress

            # 检测源视频码率，使用自适应CRF
            video_bitrate = self._get_video_bitrate(input_path, ffmpeg_path)
            adaptive_crf = self._get_adaptive_crf(video_bitrate)

            # 中文路径适配：优先8.3短路径转换，避免ffmpeg处理中文路径时崩溃
            actual_input = to_short_path(input_path) if has_non_ascii(input_path) else input_path
            if has_non_ascii(output_path):
                # 输出路径含中文，使用ASCII安全临时目录，转码后再移动到目标位置
                actual_output = os.path.join(self.safe_temp_dir, f"h264_convert_{os.getpid()}_{int(time.time() * 1000) % 100000000}.mp4")
                need_move_output = True
            else:
                actual_output = output_path
                need_move_output = False

            cmd = [
                ffmpeg_path,
                '-i', actual_input,
                '-c:v', 'libx264',
                '-preset', 'medium',
                '-crf', str(adaptive_crf),
                '-c:a', 'aac',
                '-b:a', '128k',
                '-y',
                actual_output
            ]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True,
                **subprocess_low_priority_kwargs()
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

            # 中文路径适配：转码成功后移动临时文件到目标位置
            if need_move_output and os.path.exists(actual_output) and os.path.getsize(actual_output) > 0:
                try:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    shutil.move(actual_output, output_path)
                except Exception as e:
                    logger.error(f"[H264转换] 移动临时文件失败: {e}")
                    return False, f"移动文件失败: {str(e)}"

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
        self._wait_session_ready()
        return self.video_parser.parse_media_url(url)
            
    def get_captcha(self):
        try:
            url = "https://passport.bilibili.com/x/passport-login/captcha?source=main_web"
            import logging
            logger = logging.getLogger(__name__)
            
            _has_valid_buvid3 = False
            for key in self.session.cookies.keys():
                val = self.session.cookies.get(key, '')
                if key == 'buvid3' and val and not val.startswith('XY'):
                    _has_valid_buvid3 = True
                    break
            if not _has_valid_buvid3:
                logger.info("get_captcha: session缺少服务端签发的buvid3，正在获取...")
                try:
                    _init_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
                    }
                    _init_resp = self.session.get('https://www.bilibili.com', headers=_init_headers, timeout=10, allow_redirects=True)
                    if _init_resp.cookies:
                        self.session.cookies.update(_init_resp.cookies)
                        logger.info(f"get_captcha: 从bilibili.com获取到{len(_init_resp.cookies)}个cookie")
                    
                    _pre_resp = self.session.get('https://passport.bilibili.com/login', headers=_init_headers, timeout=10, allow_redirects=True)
                    if _pre_resp.cookies:
                        self.session.cookies.update(_pre_resp.cookies)
                        logger.info(f"get_captcha: 从passport获取到{len(_pre_resp.cookies)}个cookie")
                except Exception as _e:
                    logger.warning(f"get_captcha: 初始化cookie失败: {_e}")
            
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
            status_val = data.get('status', 0)
            if "risk" in url or "verify" in url or "环境存在风险" in message or "环境存在风险" in data_message or status_val == 2:
                risk_message = data_message or message or "登录存在风险，需要验证"
                if risk_message == "OK" or not risk_message:
                    risk_message = "登录存在风险，需要验证"
                logger.info(f"Risk detected in login response: message={risk_message}, url={url}, status={status_val}")
                tmp_token = ''
                if url:
                    import re as _re
                    m = _re.search(r'tmp_token=([a-f0-9]+)', url)
                    if m:
                        tmp_token = m.group(1)
                        logger.info(f"Extracted tmp_token: {tmp_token[:20]}...")
                    else:
                        from urllib.parse import urlparse, parse_qs
                        try:
                            parsed = urlparse(url)
                            qs = parse_qs(parsed.query)
                            if 'tmp_token' in qs:
                                tmp_token = qs['tmp_token'][0]
                                logger.info(f"Extracted tmp_token from URL params: {tmp_token[:20]}...")
                        except Exception:
                            pass
                return {
                    "success": False,
                    "error": risk_message,
                    "status": risk_message,
                    "code": code,
                    "url": url,
                    "tmp_token": tmp_token,
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
            session.trust_env = False

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
                    'cid': country.get('country_id'),
                    'name': country.get('cname'),
                    'code': country.get('country_id')
                })
            
            
            for country in other_countries:
                result.append({
                    'cid': country.get('country_id'),
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
            
            _has_valid_buvid3 = False
            for key in self.session.cookies.keys():
                val = self.session.cookies.get(key, '')
                if key == 'buvid3' and val and not val.startswith('XY'):
                    _has_valid_buvid3 = True
                    break
            
            if not _has_valid_buvid3:
                logger.info("send_sms_code: session缺少服务端签发的buvid3，正在获取...")
                try:
                    _init_headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
                    }
                    _init_resp = self.session.get('https://www.bilibili.com', headers=_init_headers, timeout=10, allow_redirects=True)
                    if _init_resp.cookies:
                        self.session.cookies.update(_init_resp.cookies)
                    logger.info(f"send_sms_code: 访问bilibili.com后session有{len(self.session.cookies)}个cookie")
                    for k, v in dict(self.session.cookies).items():
                        if 'buvid' in k.lower():
                            logger.info(f"  {k}={v[:30]}...")
                except Exception as _e:
                    logger.warning(f"send_sms_code: 获取buvid3失败: {_e}")
            
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
            
            logger.info(f"发送短信验证码请求到：{url} (web端API) [V2-FIX]")
            logger.info(f"send_sms_code: session cookies = {dict(self.session.cookies)}")
            logger.info(f"send_sms_code: >>> CID={cid} <<<, tel={tel}")
            
            self.session.headers.update(headers)
            
            resp = self.session.post(url, data=data, timeout=10)
            
            logger.info(f"send_sms_code: 请求发送完毕，响应状态={resp.status_code}")
            logger.info(f"send_sms_code: 请求时发送的cookie头={resp.request.headers.get('Cookie', 'NONE')}")
            
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
            
            logger.debug("发送短信验证码成功")
            
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
            
            logger.info(f"发送短信验证码验证请求到：{url} (web端API)")
            
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
            
            code_resp = verify_data.get('code', 0)
            message = verify_data.get('message', '未知错误')
            logger.debug(f"短信验证码验证响应代码：{code_resp}，消息：{message}")
            
            data = verify_data.get('data', {})
            if not isinstance(data, dict):
                data = {}
            risk_url = data.get('url', '')
            
            if "risk" in risk_url or "verify" in risk_url or "环境存在风险" in message:
                risk_message = message or "登录存在风险，需要验证"
                logger.debug(f"Risk detected in SMS login: message={risk_message}, url={risk_url}")
                return {
                    "success": False,
                    "error": risk_message,
                    "status": risk_message,
                    "code": code_resp,
                    "url": risk_url,
                    "risk": True
                }
            
            if code_resp != 0:
                error_message = f"短信验证码验证失败：{message}（错误码：{code_resp}）"
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

    def verify_risk_sms(self, tmp_token, cid, tel, code, captcha_key):
        try:
            url = "https://passport.bilibili.com/x/passport-login/web/login/verify_sms"
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
                'tmp_token': tmp_token,
                'cid': str(cid),
                'tel': tel,
                'code': code,
                'source': 'main_web',
                'captcha_key': captcha_key
            }

            self.session.headers.update(headers)

            logger.info(f"发送风控验证请求到：{url}")
            logger.info(f"verify_risk_sms: tmp_token={tmp_token[:20]}..., cid={cid}, tel={tel}")

            resp = self.session.post(url, data=data, timeout=10)

            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.debug(f"更新会话cookies：{dict(resp.cookies)}")

            if resp.status_code != 200:
                raise Exception(f"风控验证失败：HTTP {resp.status_code}")

            content = resp.text.strip()
            logger.debug(f"风控验证响应：{content}")

            try:
                verify_data = resp.json()
            except json.JSONDecodeError:
                if content.startswith('!'):
                    start_index = content.find('{')
                    if start_index != -1:
                        content = content[start_index:]
                verify_data = json.loads(content)

            code_resp = verify_data.get('code', 0)
            message = verify_data.get('message', '未知错误')
            logger.info(f"风控验证响应代码：{code_resp}，消息：{message}")

            if code_resp != 0:
                error_message = f"风控验证失败：{message}（错误码：{code_resp}）"
                raise Exception(error_message)

            cookies = resp.cookies.get_dict()
            logger.info(f"风控验证获取到的cookie：{cookies}")

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
                    data_inner = verify_data.get('data', {})
                    url_inner = data_inner.get('url', '') if isinstance(data_inner, dict) else ''
                    if url_inner:
                        logger.info(f"从风控验证响应的 url 中提取 cookie：{url_inner}")
                        import re
                        cookie_params = re.findall(r'(DedeUserID|DedeUserID__ckMd5|SESSDATA|bili_jct)=([^&]+)', url_inner)
                        if cookie_params:
                            cookie_dict = dict(cookie_params)
                            logger.info(f"从 url 中提取到的 cookie：{cookie_dict}")
                            cookie_str = '; '.join([f'{k}={v}' for k, v in cookie_dict.items()])
                            self.save_cookies(cookie_str)

            data_inner = verify_data.get('data', {})
            sso_url = data_inner.get('url', '') if isinstance(data_inner, dict) else ''
            if sso_url:
                logger.info(f"处理风控验证 SSO 跳转：{sso_url}")
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
                "data": verify_data.get('data', {})
            }
        except Exception as e:
            logger.error(f"风控验证失败：{str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def parse_media(self, media_type, media_id, is_tv_mode=False, progress_callback=None, permission_denied_retries=1, cancel_check=None):
        self._wait_session_ready()
        logger.info(f"开始解析媒体信息: 类型={media_type}, ID={media_id}")
        try:
            if cancel_check and cancel_check():
                return {"success": False, "error": "解析已取消"}

            bvid = None
            title = ""
            cid = ""
            collection = []
            bangumi_info = None
            cheese_info = None
            # 标记充电视频（sponsor类型）：未登录时需要提示用户登录
            is_charging_content = False

            if progress_callback:
                progress_callback(10, "正在解析媒体类型...")

            if media_type == "space":
                return {
                    "success": False,
                    "error": "space类型需要在UI层通过show_space_videos处理，请使用主界面解析UP主主页链接"
                }

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
                # 标记为充电视频，未登录时需要提示用户登录
                is_charging_content = True
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

                    # 根据 video_info 字段自动识别视频类型
                    # 参考：https://sessionhu.github.io/bilibili-API-collect/docs/video/info.html
                    # 1) redirect_url 存在 → 番剧/影视视频，需跳转ep解析
                    # 2) is_upower_exclusive=True → 充电专属视频
                    redirect_url = video_info.get('redirect_url', '') if video_info else ''
                    is_upower_exclusive = bool(video_info.get('is_upower_exclusive', False)) if video_info else False
                    is_upower_play = bool(video_info.get('is_upower_play', False)) if video_info else False

                    if redirect_url and not is_charging_content:
                        # 番剧/影视：av/bv->ep 自动跳转
                        logger.info(f"检测到 redirect_url，跳转番剧/影视解析: {redirect_url}")
                        try:
                            redirect_media = self.parse_media_url(redirect_url)
                            if redirect_media.get('type') in ('bangumi', 'cheese'):
                                # 递归调用 parse_media 解析番剧/影视
                                return self.parse_media(
                                    redirect_media['type'], redirect_media['id'],
                                    is_tv_mode=is_tv_mode, progress_callback=progress_callback,
                                    permission_denied_retries=permission_denied_retries,
                                    cancel_check=cancel_check)
                        except Exception as e:
                            logger.warning(f"redirect_url 跳转失败: {e}")

                    # 标记充电专属视频（URL识别 + API字段识别）
                    if is_upower_exclusive or is_upower_play:
                        is_charging_content = True
                        logger.info(f"API字段识别为充电专属视频: is_upower_exclusive={is_upower_exclusive}, is_upower_play={is_upower_play}")


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
                        # 优先检查是否属于合集(ugc_season)或系列(series)
                        collection = self._get_collection_info(bvid)
                        logger.info(f"从API获取合集信息，共{len(collection)}集")
                        
                        # 如果合集只有1集（即只有当前视频自身），尝试查找系列
                        if len(collection) <= 1:
                            logger.info("合集信息只有1集，尝试查找视频所属系列...")
                            # 复用已获取的video_info中的mid，避免重复请求
                            _owner_mid = None
                            if video_info and video_info.get('owner'):
                                _owner_mid = video_info.get('owner', {}).get('mid')
                            series_collection = self._get_series_info(bvid, mid=_owner_mid)
                            if len(series_collection) > 1:
                                collection = series_collection
                                logger.info(f"找到系列，共{len(collection)}集")
                        
                        # 如果合集和系列都没有，使用分P信息
                        if not collection and 'pages' in video_info:
                            for page in video_info['pages']:
                                duration = page.get('duration', 0)
                                collection.append({
                                    "page": page.get('page', 0),
                                    "cid": page.get('cid', 0),
                                    "title": self._sanitize_filename(page.get('part', f"第{page.get('page')}集")),
                                    "duration": duration,
                                    "duration_str": self._format_duration(duration)
                                })
                            logger.info(f"从video_info获取分P信息，共{len(collection)}集")
                    
                    
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
            if cancel_check and cancel_check():
                return {"success": False, "error": "解析已取消"}
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
                        if cancel_check and cancel_check():
                            return {"success": False, "error": "解析已取消"}
                        if progress_callback:
                            progress = 40 + (i * 60) // total_episodes
                            progress_callback(progress, f"正在处理第{i+1}/{total_episodes}集...")
                        ep_bvid = ep.get('bvid', '')
                        ep_cid = ep.get('cid', '')
                        ep_season_id = ep.get('season_id', media_id)
                        ep_ep_id = ep.get('ep_id', '')

                        # 权限不足时按配置重试
                        ep_play_info = None
                        for retry_idx in range(permission_denied_retries + 1):
                            ep_play_info = self._get_play_info('cheese', ep_bvid, ep_cid, is_tv_mode, season_id=ep_season_id, ep_id=ep_ep_id)
                            if ep_play_info['success']:
                                break
                            if retry_idx < permission_denied_retries:
                                logger.info(f"课程第{i+1}集权限不足，第{retry_idx + 1}次重试...")
                                time.sleep(1 + retry_idx * 0.5)
                        
                        if ep_play_info and ep_play_info['success']:
                            
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
                        if cancel_check and cancel_check():
                            return {"success": False, "error": "解析已取消"}
                        if progress_callback:
                            progress = 40 + (i * 60) // total_episodes
                            progress_callback(progress, f"正在检查第{i+1}/{total_episodes}集权限...")
                        ep_bvid = ep.get('bvid', '')
                        ep_cid = ep.get('cid', '')
                        ep_id = ep.get('ep_id', '')
                        
                        # 权限不足时按配置重试
                        ep_play_info = None
                        for retry_idx in range(permission_denied_retries + 1):
                            ep_play_info = self._get_play_info('bangumi', ep_bvid, ep_cid, is_tv_mode, ep_id=ep_id)
                            if ep_play_info['success']:
                                break
                            if retry_idx < permission_denied_retries:
                                logger.info(f"番剧第{i+1}集权限不足，第{retry_idx + 1}次重试...")
                                time.sleep(1 + retry_idx * 0.5)
                        
                        if ep_play_info and ep_play_info['success']:
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
                "is_charging_content": is_charging_content,
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
                # 避免文件名中"第""集"重复：如果标题已包含"第X集"前缀则去除
                if re.match(r'^第\d+集', actual_title):
                    actual_title = re.sub(r'^第\d+集[ _\-]*', '', actual_title)
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

            data = api_data.get('data') or {}
            folders = data.get('list') or []
            logger.info(f"获取到 {len(folders)} 个收藏夹")
            
            return folders
        except Exception as e:
            error_msg = str(e)
            # 避免错误信息重复
            if not error_msg.startswith("获取用户收藏夹失败：") and not error_msg.startswith("获取用户信息失败："):
                error_msg = f"获取用户收藏夹失败：{error_msg}"
            logger.error(error_msg)
            raise

    def get_folder_content(self, media_id, page=1, page_size=20, get_all=False, progress_callback=None, page_callback=None, cancel_check=None):
        try:
            logger.info(f"开始获取收藏夹内容，media_id: {media_id}, page: {page}, page_size: {page_size}, get_all: {get_all}")

            if not self.cookies:
                raise Exception("请先登录")

            # 取消检查辅助函数
            def _cancelled():
                if cancel_check is None:
                    return False
                try:
                    return bool(cancel_check())
                except Exception:
                    return False
            
            # 注意：B站收藏夹内容接口不接受 dm_img 参数，且必须传 keyword/order/type/tid，否则返回 code=-400
            base_params = {
                'media_id': media_id,
                'ps': min(page_size, 20),
                'pn': page,
                'platform': 'web',
                'keyword': '',
                'order': 'mtime',
                'type': 0,
                'tid': 0
            }
            
            url = "https://api.bilibili.com/x/v3/fav/resource/list"
            
            if progress_callback:
                progress_callback(5, "正在获取收藏夹内容...")
            
            max_page_retries = 3
            
            def _fetch_page(params, page_num):
                for retry in range(max_page_retries):
                    if _cancelled():
                        raise Exception("已取消")
                    try:
                        logger.info(f"获取第{page_num}页收藏内容（尝试 {retry + 1}/{max_page_retries}）")
                        # 收藏夹内容接口无需 WBI 签名，且不接受 dm_img 参数
                        success, data = self._api_request(url, timeout=15, use_wbi=False, params=params, with_dm_params=False)
                        
                        if not success:
                            success, data = self._api_request(url, timeout=15, use_wbi=False, params=params, with_dm_params=False)
                            if not success:
                                error_msg = data['error']
                                if retry < max_page_retries - 1:
                                    import time as _t
                                    wait = 2 * (2 ** retry) + 1
                                    logger.warning(f"第{page_num}页请求失败，{wait}秒后重试：{error_msg}")
                                    _t.sleep(wait)
                                    continue
                                raise Exception(f"获取收藏夹内容失败：{error_msg}")
                        
                        if data.get('code') != 0:
                            error_msg = data.get('message', '未知错误')
                            if retry < max_page_retries - 1:
                                import time as _t
                                wait = 2 * (2 ** retry) + 1
                                logger.warning(f"第{page_num}页API返回错误(code={data.get('code')})，{wait}秒后重试：{error_msg}")
                                _t.sleep(wait)
                                continue
                            raise Exception(f"获取收藏夹内容失败：{error_msg}（code={data.get('code')}）")
                        
                        return data
                    except Exception as e:
                        if retry < max_page_retries - 1 and ('timeout' in str(e).lower() or 'timed out' in str(e).lower()):
                            import time as _t
                            wait = 2 * (2 ** retry) + 1
                            logger.warning(f"第{page_num}页超时，{wait}秒后重试：{e}")
                            _t.sleep(wait)
                            continue
                        raise
                raise Exception(f"获取第{page_num}页收藏夹内容失败：已重试{max_page_retries}次")
            
            def _parse_medias(medias):
                items = []
                for item in medias:
                    # 收藏夹可能包含多种类型：视频(2)、番剧(12)、课程(21)等
                    # 只要有 bvid 或 id 就当作可下载内容处理
                    bvid = item.get('bv_id') or item.get('bvid')
                    aid = item.get('id')
                    if not (bvid or aid):
                        continue
                    media_type = int(item.get('type', 2))
                    # type=2 视频, type=12 番剧, type=21 课程, 其他也尝试兼容
                    items.append({
                        'id': aid,
                        'type': 'video',
                        'title': item.get('title', '未知内容'),
                        'cover': item.get('cover'),
                        'bvid': bvid,
                        'aid': aid,
                        'up_name': (item.get('upper', {}) or {}).get('name', '未知UP主'),
                        'duration': item.get('duration', 0),
                        'fav_time': item.get('fav_time', 0)
                    })
                return items
            
            api_data = _fetch_page(base_params, page)

            result_data = api_data.get('data') or {}
            medias = result_data.get('medias') or []
            has_more = result_data.get('has_more', False)
            total_count = result_data.get('info', {}).get('media_count', 0)
            
            logger.info(f"第一页：获取到 {len(medias)} 个收藏内容，has_more={has_more}，total_count={total_count}")
            
            collection_items = _parse_medias(medias)
            
            logger.info(f"处理后收藏内容数量：{len(collection_items)}")
            
            if page_callback and collection_items:
                page_callback(collection_items, page, total_count)
            
            # 进入循环条件：get_all 且（has_more 为真，或 total_count 大于已获取数量）
            # 不单纯依赖 has_more：B 站 API 在收藏夹含失效视频或被限流时会异常返回 has_more=False，
            # 但 media_count 仍显示总数，导致只拿到第一页就提前结束
            need_more = bool(has_more) or (total_count and total_count > len(collection_items))
            if get_all and need_more:
                all_items = collection_items.copy()
                # 估算总页数（每页最多 20 个），用于进度显示和安全上限
                estimated_pages = max(1, (total_count + 19) // 20) if total_count > 0 else 10
                
                # 读取设置中的并发线程数（同下载设置 max_threads），保守限制 2~8
                try:
                    _cfg_threads = self.config.get_app_setting('max_threads', 2) if self.config else 2
                    _cfg_threads = int(_cfg_threads)
                except Exception:
                    _cfg_threads = 2
                fav_workers = max(2, min(_cfg_threads, 8))
                logger.info(f"收藏夹分页并发获取，线程数={fav_workers}，预估页数={estimated_pages}")
                
                # 用线程池并发拉取剩余页；先按预估页数派发任务，遇到 has_more=False 的页后停止派发
                from concurrent.futures import ThreadPoolExecutor, as_completed
                import threading as _threading
                
                _stop_dispatch = _threading.Event()
                _completed_count = [0]
                _counter_lock = _threading.Lock()
                _empty_page_count = [0]  # 连续空页计数（has_more=False 但未拿够时用于判断是否停止）
                
                def _fetch_one_page(pn):
                    if _cancelled():
                        raise Exception("已取消")
                    params = {
                        'media_id': media_id,
                        'ps': 20,
                        'pn': pn,
                        'platform': 'web',
                        'keyword': '',
                        'order': 'mtime',
                        'type': 0,
                        'tid': 0
                    }
                    page_data = _fetch_page(params, pn)
                    page_result = page_data.get('data') or {}
                    page_medias = page_result.get('medias') or []
                    page_has_more = page_result.get('has_more', False)
                    return pn, page_medias, page_has_more

                # 用户取消时抛出，由外层 except 捕获后正常返回已获取的内容
                _cancelled_exc = None
                with ThreadPoolExecutor(max_workers=fav_workers) as executor:
                    next_page = page + 1
                    # 派发上限：估算页数 + 1 安全余量（应对分页边界和 API 异常）
                    # 例如 total_count=64, estimated_pages=4 → 最多派发到 page 5
                    # 避免派发远超估算范围的空页，导致空页计数器误触发停止
                    max_page_cap = page + estimated_pages
                    futures = set()

                    # 先派发首批任务（每线程一个），但不超过实际需要的页数
                    initial_dispatch = min(fav_workers, max(0, max_page_cap - page))
                    for _ in range(initial_dispatch):
                        if next_page > max_page_cap:
                            break
                        futures.add(executor.submit(_fetch_one_page, next_page))
                        next_page += 1

                    while futures and not _stop_dispatch.is_set():
                        # 取消时立即停止派发，并等待在途任务完成
                        if _cancelled():
                            _stop_dispatch.set()
                            break
                        # as_completed 在 with 块结束时未取完的 future 会被取消，这里手动管理
                        done = set()
                        for fut in list(futures):
                            if fut.done():
                                done.add(fut)
                        if not done:
                            # 没有完成的任务，短暂等待避免忙轮询
                            import time as _t
                            _t.sleep(0.02)
                            continue

                        for fut in done:
                            futures.discard(fut)
                            try:
                                pn, page_medias, page_has_more = fut.result()
                            except Exception as e:
                                # 取消导致的失败，记录后跳出，不再派发
                                if _cancelled() or "已取消" in str(e):
                                    _cancelled_exc = e
                                    _stop_dispatch.set()
                                    break
                                logger.error(f"并发获取收藏夹页失败：{e}")
                                raise

                            logger.info(f"第{pn}页获取到 {len(page_medias)} 个收藏内容")
                            page_items = _parse_medias(page_medias)
                            all_items.extend(page_items)

                            if page_callback and page_items:
                                page_callback(page_items, pn, total_count)

                            with _counter_lock:
                                _completed_count[0] += 1
                            if progress_callback:
                                page_progress = min(90, int(10 + 80 * _completed_count[0] / max(estimated_pages, 1)))
                                progress_callback(page_progress, f"已获取 {len(all_items)}/{total_count} 项（完成 {_completed_count[0]} 页）...")

                            # has_more=False 时的停止策略：
                            # 1. 已拿够 total_count → 正常停止
                            # 2. 当前页为空且连续 2 次空页 → 判定无可再取，停止
                            #    - 但若仍有在途任务且未拿够 total_count，继续等待（避免因远端空页误杀未完成的有效页）
                            # 3. 否则继续派发下一页（应对 API 异常返回 has_more=False 但实际还有数据）
                            if not page_has_more:
                                if total_count and len(all_items) >= total_count:
                                    logger.info(f"已获取 {len(all_items)} 项 >= total_count={total_count}，停止派发")
                                    _stop_dispatch.set()
                                    break
                                if not page_medias:
                                    _empty_page_count[0] += 1
                                    if _empty_page_count[0] >= 2:
                                        # 仍有在途任务且未拿够，可能这些任务包含数据，继续等待
                                        if futures and (not total_count or len(all_items) < total_count):
                                            logger.info(f"连续 {_empty_page_count[0]} 次空页，但仍有 {len(futures)} 个在途任务未完成，继续等待")
                                        else:
                                            logger.info(f"连续 {_empty_page_count[0]} 次空页，停止派发（已获取 {len(all_items)}/{total_count}）")
                                            _stop_dispatch.set()
                                            break
                                    else:
                                        logger.info(f"has_more=False 且当前页空，第 {_empty_page_count[0]} 次空页，继续试探下一页")
                                else:
                                    _empty_page_count[0] = 0
                                    logger.info(f"has_more=False 但未拿够（{len(all_items)}/{total_count}），继续派发下一页")

                            # 还有更多，且未达上限，派发下一页
                            if next_page <= max_page_cap and not _stop_dispatch.is_set():
                                futures.add(executor.submit(_fetch_one_page, next_page))
                                next_page += 1

                    # 取消未开始的任务
                    for fut in futures:
                        fut.cancel()

                # 用户取消时，正常返回已获取的内容（不视为错误）
                if _cancelled_exc is not None or _cancelled():
                    logger.info(f"用户已取消获取收藏夹，返回已获取的 {len(all_items)} 项")
                    if progress_callback:
                        progress_callback(100, f"已取消，共获取 {len(all_items)} 项")
                    return {
                        'items': all_items,
                        'has_more': False,
                        'total': len(all_items)
                    }
                
                if progress_callback:
                    progress_callback(95, f"获取完成，共 {len(all_items)} 项，正在处理...")
                
                logger.info(f"处理后收藏内容总数量：{len(all_items)}")
                return {
                    'items': all_items,
                    'has_more': False,
                    'total': len(all_items)
                }
            else:
                total = result_data.get('info', {}).get('media_count', 0)
                logger.info(f"收藏夹总内容数量：{total}")
                if progress_callback:
                    progress_callback(100, "获取完成")
                return {
                    'items': collection_items,
                    'has_more': has_more,
                    'total': total
                }
        except Exception as e:
            error_msg = str(e)
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
            pages = video_data.get('pages', [])
            page_count = len(pages)
            

            if page_count > 1 and 'ugc_season' not in video_data:
                logger.info(f"视频有{page_count}个分P，优先使用分P信息")
                for page in pages:
                    duration = page.get('duration', 0)
                    collection.append({
                        "page": page.get('page', 0),
                        "cid": page.get('cid', 0),
                        "bvid": bvid,
                        "title": self._sanitize_filename(page.get('part', f"第{page.get('page')}集")),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": video_cover  
                    })
                return collection

            if 'ugc_season' in video_data:
                ugc_season = video_data['ugc_season']
                # 尝试从ugc_season中提取season_id和mid，用于获取完整合集
                season_id = ugc_season.get('id') or ugc_season.get('season_id')
                upper_mid = ugc_season.get('mid') or ugc_season.get('upper_mid') or video_data.get('owner', {}).get('mid')
                season_title = ugc_season.get('title') or ugc_season.get('name')

                # 如果能获取到season_id和mid，使用合集详情API获取完整合集（避免只返回当前章节的问题
                full_collection = None
                if season_id and upper_mid:
                    logger.info(f"检测到合集: {season_title} (season_id={season_id}, mid={upper_mid})，尝试获取完整合集列表")
                    full_collection = self._get_full_ugc_season_archives(upper_mid, season_id, video_cover, source_bvid=bvid)
                    if full_collection and len(full_collection) > 0:
                        logger.info(f"从合集详情API获取到 {len(full_collection)} 个视频")
                        collection = full_collection

                # 如果没有获取到完整合集，使用视频信息API中的sections数据
                if not collection and 'sections' in ugc_season:
                    logger.info("使用视频信息API中的ugc_season.sections数据")
                    page_idx = 1
                    for section in ugc_season['sections']:
                        if 'episodes' in section:
                            for ep in section['episodes']:

                                ep_pages = []
                                if 'page' in ep:
                                    ep_pages = [ep['page']]
                                elif 'pages' in ep and ep['pages']:
                                    ep_pages = ep['pages']
                                
                                if not ep_pages:
                                    continue
                                
                                ep_title = ep.get('title', f"第{page_idx}集")
                                ep_bvid = ep.get('bvid', bvid)

                                if len(ep_pages) == 1:
                                    page_info = ep_pages[0]
                                    duration = page_info.get('duration', 0)
                                    collection.append({
                                        "page": page_idx,
                                        "cid": page_info.get('cid', 0),
                                        "bvid": ep_bvid,
                                        "title": self._sanitize_filename(ep_title),
                                        "duration": duration,
                                        "duration_str": self._format_duration(duration),
                                        "cover": video_cover
                                    })
                                    page_idx += 1
                                else:
                                    collection.append({
                                        "page": page_idx,
                                        "cid": ep_pages[0].get('cid', 0),
                                        "bvid": ep_bvid,
                                        "title": self._sanitize_filename(ep_title),
                                        "duration": 0,
                                        "duration_str": "",
                                        "cover": video_cover
                                    })
                                    page_idx += 1

                                    for pi, page_info in enumerate(ep_pages):
                                        duration = page_info.get('duration', 0)
                                        part_name = page_info.get('part', f"P{pi+1}")
                                        collection.append({
                                            "page": page_idx,
                                            "cid": page_info.get('cid', 0),
                                            "bvid": ep_bvid,
                                            "title": self._sanitize_filename(f"  │ P{pi+1} - {part_name}"),
                                            "duration": duration,
                                            "duration_str": self._format_duration(duration),
                                            "cover": video_cover
                                        })
                                        page_idx += 1
            
            if not collection:
                for page in pages:
                    duration = page.get('duration', 0)
                    collection.append({
                        "page": page.get('page', 0),
                        "cid": page.get('cid', 0),
                        "bvid": bvid,
                        "title": self._sanitize_filename(page.get('part', f"第{page.get('page')}集")),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": video_cover  
                    })
            
            return collection
        except Exception as e:
            logger.error(f"获取合集信息失败：{str(e)}（bvid={bvid}）")
            return []

    def _get_full_ugc_season_archives(self, mid, season_id, default_cover='', source_bvid=''):
        """通过合集详情API获取完整的合集视频列表（包含所有章节、所有视频、所有分P）

        使用 seasons_archives_list API 获取所有章节视频，然后对每个章节视频
        调用视频信息API获取其完整的分P列表，构建完整的合集结构。

        Args:
            mid: UP主mid
            season_id: 合集season_id
            default_cover: 默认封面图URL
            source_bvid: 触发解析的视频bvid，用于辅助查找

        Returns:
            list: 合集视频列表，每个元素包含page, bvid, cid, title, duration等字段
        """
        # 方案1：使用 seasons_archives_list API 获取所有章节视频
        try:
            all_archives = []
            page_size = 30
            page_num = 1

            while True:
                try:
                    url = f"https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid={mid}&season_id={season_id}&page_num={page_num}&page_size={page_size}&sort=0"
                    success, data = self._api_request(url, timeout=10, use_cache=False)
                    if not success or data.get('code') != 0:
                        logger.warning(f"获取合集第{page_num}页失败: {data.get('message', '未知错误') if not success else data.get('message')}")
                        break

                    page_data = data.get('data', {})
                    archives = page_data.get('archives', [])
                    if not archives:
                        break

                    all_archives.extend(archives)

                    # 检查是否还有下一页
                    page_info = page_data.get('page', {})
                    total = page_info.get('total', 0)
                    if total == 0:
                        total = page_data.get('meta', {}).get('total', 0)

                    logger.info(f"seasons_archives_list 第{page_num}页获取到 {len(archives)} 个视频，累计 {len(all_archives)}/{total}")

                    if len(all_archives) >= total or len(archives) < page_size:
                        break

                    page_num += 1
                except Exception as e:
                    logger.warning(f"获取合集第{page_num}页异常: {e}")
                    break

            if not all_archives:
                logger.info("seasons_archives_list API未返回数据")
                return []

            logger.info(f"从seasons_archives_list获取到 {len(all_archives)} 个章节视频，开始并发获取每个视频的分P信息")

            # 并发获取每个章节视频的分P列表，避免同步请求导致解析卡死
            from concurrent.futures import ThreadPoolExecutor, as_completed
            pages_map = {}  # bvid -> pages list

            def _fetch_pages(bvid):
                return bvid, self._get_video_pages_list(bvid)

            # 限制并发数避免被风控，每个请求设置较短超时
            max_workers = min(8, len(all_archives)) if all_archives else 1
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {executor.submit(_fetch_pages, arc.get('bvid', '')): arc for arc in all_archives if arc.get('bvid')}
                    for future in as_completed(futures, timeout=30):
                        try:
                            bvid, pages = future.result(timeout=10)
                            pages_map[bvid] = pages
                        except Exception as e:
                            logger.warning(f"获取分P失败: {e}")
            except Exception as e:
                logger.warning(f"并发获取分P异常: {e}")

            # 对每个章节视频，构建合集项（含分P）
            collection = []
            page_idx = 1
            for arc in all_archives:
                arc_bvid = arc.get('bvid', '')
                arc_title = arc.get('title', f"第{page_idx}集")
                arc_cover = arc.get('pic', '') or default_cover
                arc_duration = arc.get('duration', 0)

                if not arc_bvid:
                    logger.warning(f"章节视频无bvid，跳过: {arc_title}")
                    continue

                # 从并发结果中获取分P列表
                pages = pages_map.get(arc_bvid, [])

                if not pages:
                    # 没有分P信息，将视频本身作为单项
                    collection.append({
                        "page": page_idx,
                        "cid": arc.get('cid', 0),
                        "bvid": arc_bvid,
                        "title": self._sanitize_filename(arc_title),
                        "duration": arc_duration,
                        "duration_str": self._format_duration(arc_duration),
                        "cover": arc_cover
                    })
                    page_idx += 1
                    logger.info(f"章节 '{arc_title}' 无分P，作为单项添加")
                elif len(pages) == 1:
                    # 单分P视频
                    page_info = pages[0]
                    duration = page_info.get('duration', 0) or arc_duration
                    collection.append({
                        "page": page_idx,
                        "cid": page_info.get('cid', 0) or arc.get('cid', 0),
                        "bvid": arc_bvid,
                        "title": self._sanitize_filename(arc_title),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": arc_cover
                    })
                    page_idx += 1
                    logger.info(f"章节 '{arc_title}' 单分P，共1项")
                else:
                    # 多分P视频：先添加视频本身，再添加每个分P
                    collection.append({
                        "page": page_idx,
                        "cid": pages[0].get('cid', 0) if pages else arc.get('cid', 0),
                        "bvid": arc_bvid,
                        "title": self._sanitize_filename(arc_title),
                        "duration": arc_duration,
                        "duration_str": self._format_duration(arc_duration),
                        "cover": arc_cover
                    })
                    page_idx += 1

                    for pi, page_info in enumerate(pages):
                        duration = page_info.get('duration', 0)
                        part_name = page_info.get('part', f"P{pi+1}")
                        collection.append({
                            "page": page_idx,
                            "cid": page_info.get('cid', 0),
                            "bvid": arc_bvid,
                            "title": self._sanitize_filename(f"  │ P{pi+1} - {part_name}"),
                            "duration": duration,
                            "duration_str": self._format_duration(duration),
                            "cover": arc_cover
                        })
                        page_idx += 1
                    logger.info(f"章节 '{arc_title}' 多分P，共{len(pages)+1}项")

            if collection:
                logger.info(f"构建完整合集列表，共 {len(collection)} 项（含分P）")
                return collection
        except Exception as e:
            logger.error(f"获取完整合集列表失败: {e}")

        # 方案2：fallback - 使用 _get_season_all_archives（旧逻辑）
        try:
            all_archives = self._get_season_all_archives(mid, season_id, 999)
            if all_archives:
                collection = []
                for idx, arc in enumerate(all_archives, 1):
                    duration = arc.get('duration', 0)
                    collection.append({
                        "page": idx,
                        "cid": arc.get('cid', 0),
                        "bvid": arc.get('bvid', ''),
                        "title": self._sanitize_filename(arc.get('title', f"第{idx}集")),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": arc.get('pic', '') or default_cover
                    })
                return collection
        except Exception as e:
            logger.error(f"fallback获取合集列表失败: {e}")

        return []

    def _get_video_pages_list(self, bvid):
        """获取视频的分P列表（通过视频信息API）

        Args:
            bvid: 视频bvid

        Returns:
            list: 分P列表，每个元素包含cid, page, part, duration等字段
        """
        try:
            url = self.config.get_api_url("video_info_api").format(bvid=bvid)
            import urllib.parse
            url_parts = list(urllib.parse.urlparse(url))
            query = dict(urllib.parse.parse_qsl(url_parts[4]))
            success, data = self._api_request(url, timeout=10, use_wbi=True, params=query)
            if not success or data.get('code') != 0:
                logger.warning(f"获取视频分P失败: bvid={bvid}")
                return []

            video_data = data.get('data', {})
            pages = video_data.get('pages', [])
            return pages
        except Exception as e:
            logger.warning(f"获取视频分P异常: bvid={bvid}, error={e}")
            return []

    def _get_series_info(self, bvid, mid=None):
        """获取视频所属系列(series)的完整视频列表。
        B站有两种视频组织形式：合集(ugc_season)和系列(series)。
        合集已由 _get_collection_info 处理，此方法处理系列。
        
        Args:
            bvid: 视频bvid
            mid: UP主mid（可选，如果不提供则从视频信息中获取）
        """
        try:
            # 先获取视频信息以得到mid
            if not mid:
                video_info = self._get_video_main_info(bvid)
                if not video_info:
                    logger.warning(f"无法获取视频信息以查找系列: {bvid}")
                    return []
                owner = video_info.get('owner', {})
                mid = owner.get('mid')
                if not mid:
                    logger.warning(f"无法获取UP主mid: {bvid}")
                    return []
            
            # 获取UP主的系列和合集列表
            series_url = f"https://api.bilibili.com/x/polymer/web-space/home/seasons_series?mid={mid}&page_num=1&page_size=30"
            success, data = self._api_request(series_url, timeout=5, use_cache=False)
            if not success:
                logger.warning(f"获取UP主系列列表失败: {data.get('error', '未知')}")
                return []
            
            if data.get('code') != 0:
                logger.warning(f"获取UP主系列列表API返回错误: {data.get('message', '未知')}")
                return []
            
            items_lists = data.get('data', {}).get('items_lists', {})
            
            # 遍历所有系列，找到包含当前bvid的系列
            series_list = items_lists.get('series_list', [])
            for series_item in series_list:
                meta = series_item.get('meta', {})
                series_id = meta.get('series_id')
                recent_aids = series_item.get('recent_aids', [])
                
                # 检查当前视频是否在这个系列中（先快速检查recent_aids）
                archives = series_item.get('archives', [])
                archive_bvids = [a.get('bvid', '') for a in archives]
                
                if bvid not in archive_bvids:
                    continue
                
                logger.info(f"找到视频所属系列: {meta.get('name', '未知')} (series_id={series_id}), 系列内{meta.get('total', '?')}个视频")
                
                # 如果当前返回的archives不完整，需要分页获取全部
                total = meta.get('total', 0)
                if total > len(archives):
                    archives = self._get_series_all_archives(mid, series_id, total)
                
                collection = []
                for idx, arc in enumerate(archives, 1):
                    duration = arc.get('duration', 0)
                    collection.append({
                        "page": idx,
                        "bvid": arc.get('bvid', ''),
                        "title": self._sanitize_filename(arc.get('title', f"第{idx}集")),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": arc.get('pic', '')
                    })
                
                return collection
            
            # 也检查合集列表（seasons_list）
            seasons_list = items_lists.get('seasons_list', [])
            for season_item in seasons_list:
                archives = season_item.get('archives', [])
                archive_bvids = [a.get('bvid', '') for a in archives]
                
                if bvid not in archive_bvids:
                    continue
                
                meta = season_item.get('meta', {})
                season_id = meta.get('season_id')
                logger.info(f"找到视频所属合集(通过seasons_list): {meta.get('name', '未知')} (season_id={season_id})")
                
                total = meta.get('total', 0)
                if total > len(archives):
                    archives = self._get_season_all_archives(mid, season_id, total)
                
                collection = []
                for idx, arc in enumerate(archives, 1):
                    duration = arc.get('duration', 0)
                    collection.append({
                        "page": idx,
                        "bvid": arc.get('bvid', ''),
                        "title": self._sanitize_filename(arc.get('title', f"第{idx}集")),
                        "duration": duration,
                        "duration_str": self._format_duration(duration),
                        "cover": arc.get('pic', '')
                    })
                
                return collection
            
            logger.info(f"视频 {bvid} 不属于任何系列")
            return []
            
        except Exception as e:
            logger.error(f"获取系列信息失败: {str(e)}")
            return []

    def _get_series_all_archives(self, mid, series_id, total):
        """分页获取系列的所有视频"""
        all_archives = []
        page_size = 30
        total_pages = (total + page_size - 1) // page_size
        
        for page_num in range(1, total_pages + 1):
            try:
                url = f"https://api.bilibili.com/x/series/archives?mid={mid}&series_id={series_id}&pn={page_num}&ps={page_size}"
                success, data = self._api_request(url, timeout=10, use_cache=False)
                if not success or data.get('code') != 0:
                    break
                
                archives = data.get('data', {}).get('archives', [])
                if not archives:
                    break
                all_archives.extend(archives)
            except Exception as e:
                logger.warning(f"获取系列第{page_num}页失败: {e}")
                break
        
        return all_archives

    def _get_season_all_archives(self, mid, season_id, total):
        """分页获取合集的所有视频"""
        all_archives = []
        page_size = 30
        total_pages = (total + page_size - 1) // page_size
        
        for page_num in range(1, total_pages + 1):
            try:
                url = f"https://api.bilibili.com/x/polymer/web-space/seasons_archives_list?mid={mid}&season_id={season_id}&page_num={page_num}&page_size={page_size}"
                success, data = self._api_request(url, timeout=10, use_cache=False)
                if not success or data.get('code') != 0:
                    break
                
                archives = data.get('data', {}).get('archives', [])
                if not archives:
                    break
                all_archives.extend(archives)
            except Exception as e:
                logger.warning(f"获取合集第{page_num}页失败: {e}")
                break
        
        return all_archives

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
            # 注意：Hi-Res无损音频通过dash.flac字段获取，不依赖fnval标志位
            fnval = 4048
            fnver = 0
            
            # 判断登录状态：未登录带try_look=1（试看1080P），已登录不带（获取4K等高画质）
            _is_logged_in = bool(self.cookies and self.cookies.get('SESSDATA'))
            if not _is_logged_in:
                _try_look = 1
            else:
                _try_look = 0

            if media_type == "bangumi":
                # 番剧使用正确的API
                params = {
                    'cid': cid,
                    'bvid': bvid,
                    'qn': 127,  # 请求最高画质
                    'fnval': fnval,
                    'fnver': fnver,
                    'fourk': 1,
                    'try_look': _try_look,
                    'from_client': 'BROWSER',
                    'drm_tech_type': 2,
                    'otype': 'json'
                }
                play_url = "https://api.bilibili.com/pgc/player/web/playurl"
                logger.debug(f"获取番剧播放链接：{play_url}，参数：{params}")
            elif media_type == "cheese":
                params = {
                    'qn': 127,
                    'fnval': fnval,
                    'fnver': fnver,
                    'fourk': 1,
                    'try_look': _try_look,
                    'drm_tech_type': 2,
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
                    'qn': 127,
                    'fnval': fnval,
                    'fnver': fnver,
                    'fourk': 1,
                    'try_look': _try_look,
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
                    if not success or play_data.get('code') != 0:
                        logger.info("尝试html5模式获取播放信息")
                        html5_params = {
                            'cid': cid,
                            'bvid': bvid,
                            'qn': 80,
                            'fnval': 1,
                            'fnver': 0,
                            'platform': 'html5',
                            'high_quality': 1,
                            'fourk': 1,
                            'otype': 'json'
                        }
                        success, play_data = self._api_request(play_url, timeout=15, use_wbi=False, params=html5_params)
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

            # 获取登录状态（用于判断是否需要回退html5模式）
            user_info = self.get_user_info()
            is_login = user_info.get('success', False)

            # 检查DASH模式下最高画质，如果未登录且最高画质<1080P，尝试html5模式获取1080P
            _data_src = play_data.get('data', play_data.get('result', {}))
            if not is_login and _data_src.get('dash') and _data_src.get('quality', 0) < 80:
                _max_qn = _data_src.get('quality', 0)
                logger.info(f"未登录DASH模式最高画质qn={_max_qn}，尝试html5模式获取1080P")
                html5_params2 = {
                    'cid': cid,
                    'bvid': bvid,
                    'qn': 80,
                    'fnval': 1,
                    'fnver': 0,
                    'platform': 'html5',
                    'high_quality': 1,
                    'fourk': 1,
                    'otype': 'json'
                }
                h5_ok, h5_data = self._api_request(play_url, timeout=15, use_wbi=False, params=html5_params2)
                if h5_ok and h5_data.get('code') == 0:
                    h5_src = h5_data.get('data', h5_data.get('result', {}))
                    h5_qn = h5_src.get('quality', 0)
                    if h5_qn > _max_qn:
                        logger.info(f"html5模式获取到更高画质qn={h5_qn}，使用html5数据")
                        play_data = h5_data

            qualities = []
            video_urls = {}
            audio_url = ""
            
            is_vip = user_info.get('is_vip', False)
            has_hevc = False
            quality_map = self.config.get_quality_map()
            
            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
            # 注意：使用try_look=1参数后，未登录也可获取720P(qn=64)和1080P(qn=80)
            # 因此不再将64和80列为登录必需，改为：如果API返回了该画质流就允许使用
            LOGIN_REQUIRED_QN = []  # try_look=1已解决未登录获取问题

            def is_quality_available(qn, is_login, is_vip):
                # 4K(qn=120) 不强制要求大会员：B站API已根据用户权限返回可用流
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
                if 'widevine_pssh' in first_video:
                    _pssh_val = first_video['widevine_pssh']
                    logger.debug(f"widevine_pssh: {'(空)' if not _pssh_val else _pssh_val[:80] + '...'}")

            kid = None
            audio_urls = {}
            audio_qualities = []
            if 'dash' in data_source:
                logger.debug("使用DASH格式获取链接")

                # 音频质量名称映射（支持B站API返回的所有音质ID）
                # 官方文档ID：30216=64K, 30232=132K, 30280=192K, 30250=杜比全景声, 30251=Hi-Res无损
                # 实际API可能额外返回：100008=128K, 100009=192K, 100010=320K
                _AUDIO_NAME_MAP = {
                    30251: "Hi-Res无损",
                    30250: "杜比全景声",
                    100010: "320K 高音质",
                    30280: "192K 高音质",
                    100009: "192K 标准音质",
                    30232: "132K 标准音质",
                    100008: "128K 标准音质",
                    30216: "64K 低音质",
                }

                def _pick_best_audio_url(url_list):
                    """从URL列表中选择最稳定的CDN域名（优先bilivideo.com，避免mcdn）"""
                    if not url_list:
                        return ''
                    _avoid = ['mcdn.bilivideo.cn']
                    _sorted_urls = sorted(url_list, key=lambda u: (
                        any(m in u for m in _avoid),
                        -u.count('bilivideo.com')
                    ))
                    return _sorted_urls[0].strip().strip('`')

                def _parse_audio_stream(audio_item):
                    """解析单个音频流，返回(audio_id, audio_url)或None"""
                    audio_id = audio_item.get('id', 0)
                    _candidates = []
                    if audio_item.get('baseUrl'):
                        _candidates.append(audio_item.get('baseUrl'))
                    if audio_item.get('url'):
                        _candidates.append(audio_item.get('url'))
                    if audio_item.get('backup_url') and isinstance(audio_item.get('backup_url'), list):
                        _candidates.extend(audio_item.get('backup_url'))
                    if audio_item.get('backupUrl') and isinstance(audio_item.get('backupUrl'), list):
                        _candidates.extend(audio_item.get('backupUrl'))
                    _candidates = [u for u in _candidates if u]
                    audio_url = _pick_best_audio_url(_candidates) if _candidates else ''
                    if audio_url:
                        return audio_id, audio_url
                    return None

                # 解析普通DASH音频流（dash.audio）
                _all_audio_ids = []
                if 'audio' in data_source['dash'] and data_source['dash']['audio']:
                    for audio_item in data_source['dash']['audio']:
                        _all_audio_ids.append(audio_item.get('id', 0))
                        result = _parse_audio_stream(audio_item)
                        if result:
                            audio_id, audio_url = result
                            audio_urls[audio_id] = audio_url
                            quality_name = _AUDIO_NAME_MAP.get(audio_id, f"音质({audio_id})")
                            audio_qualities.append((audio_id, quality_name))
                            logger.debug(f"获取音频链接 ID={audio_id}({quality_name}): {audio_url[:50]}...")

                # 解析Hi-Res/FLAC无损音频流（dash.flac.audio）— 独立于普通音频流
                # B站API结构：dash.flac.audio 是单个dict对象（非数组），包含id/baseUrl等字段
                _flac = data_source['dash'].get('flac')
                if isinstance(_flac, dict):
                    _flac_audio = _flac.get('audio')
                    if isinstance(_flac_audio, dict):
                        # dash.flac.audio 是单个音频对象
                        logger.info("检测到FLAC/Hi-Res无损音频流")
                        _all_audio_ids.append(_flac_audio.get('id', 0))
                        result = _parse_audio_stream(_flac_audio)
                        if result:
                            audio_id, audio_url = result
                            audio_urls[audio_id] = audio_url
                            quality_name = _AUDIO_NAME_MAP.get(audio_id, f"Hi-Res无损({audio_id})")
                            audio_qualities.append((audio_id, quality_name))
                            logger.info(f"获取Hi-Res音频链接 ID={audio_id}({quality_name}): {audio_url[:50]}...")
                    elif isinstance(_flac_audio, list):
                        # 兼容：dash.flac.audio 偶尔为数组格式
                        logger.info("检测到FLAC/Hi-Res无损音频流(数组格式)")
                        for audio_item in _flac_audio:
                            if not isinstance(audio_item, dict):
                                continue
                            _all_audio_ids.append(audio_item.get('id', 0))
                            result = _parse_audio_stream(audio_item)
                            if result:
                                audio_id, audio_url = result
                                audio_urls[audio_id] = audio_url
                                quality_name = _AUDIO_NAME_MAP.get(audio_id, f"Hi-Res无损({audio_id})")
                                audio_qualities.append((audio_id, quality_name))
                                logger.info(f"获取Hi-Res音频链接 ID={audio_id}({quality_name}): {audio_url[:50]}...")

                # 解析杜比全景声音频流（dash.dolby.audio）
                _dolby = data_source['dash'].get('dolby')
                if isinstance(_dolby, dict):
                    _dolby_audio = _dolby.get('audio')
                    if isinstance(_dolby_audio, list):
                        for audio_item in _dolby_audio:
                            if not isinstance(audio_item, dict):
                                continue
                            _all_audio_ids.append(audio_item.get('id', 0))
                            result = _parse_audio_stream(audio_item)
                            if result:
                                audio_id, audio_url = result
                                audio_urls[audio_id] = audio_url
                                quality_name = _AUDIO_NAME_MAP.get(audio_id, f"杜比({audio_id})")
                                audio_qualities.append((audio_id, quality_name))
                                logger.info(f"获取杜比音频链接 ID={audio_id}({quality_name}): {audio_url[:50]}...")
                    elif isinstance(_dolby_audio, dict):
                        _all_audio_ids.append(_dolby_audio.get('id', 0))
                        result = _parse_audio_stream(_dolby_audio)
                        if result:
                            audio_id, audio_url = result
                            audio_urls[audio_id] = audio_url
                            quality_name = _AUDIO_NAME_MAP.get(audio_id, f"杜比({audio_id})")
                            audio_qualities.append((audio_id, quality_name))
                            logger.info(f"获取杜比音频链接 ID={audio_id}({quality_name}): {audio_url[:50]}...")

                # 诊断日志：显示API返回的所有音质ID，方便排查Hi-Res获取问题
                logger.info(f"[音频诊断] API返回音频流: IDs={_all_audio_ids}, "
                           f"可用音质={[q[1] for q in audio_qualities]}, "
                           f"登录状态={'已登录' if is_login else '未登录'}, "
                           f"VIP状态={'是' if is_vip else '否'}")
                if 30251 not in [a[0] for a in audio_qualities] and 30250 not in [a[0] for a in audio_qualities]:
                    logger.debug(f"[音频诊断] 未检测到Hi-Res(30251)/杜比(30250)音频流。"
                                  f"如视频支持Hi-Res，请确认已登录大会员账号")

                # 根据用户选择的音频质量返回对应的音频URL
                if audio_qualities:
                    # 按音质优先级排序（从高到低，动态支持API返回的所有音质ID）
                    audio_quality_priority = [30251, 30250, 100010, 30280, 100009, 30232, 100008, 30216]
                    sorted_audio_qualities = sorted(audio_qualities, key=lambda x: audio_quality_priority.index(x[0]) if x[0] in audio_quality_priority else 999)

                    if audio_quality and audio_quality in audio_urls:
                        audio_url = audio_urls[audio_quality]
                        _aq_name = _AUDIO_NAME_MAP.get(audio_quality, f"音质({audio_quality})")
                        logger.info(f"使用用户选择的音频质量：{_aq_name}")
                    else:
                        # 使用最高可用的音频质量
                        highest_quality = sorted_audio_qualities[0][0]
                        _hq_name = _AUDIO_NAME_MAP.get(highest_quality, f"音质({highest_quality})")
                        audio_url = audio_urls[highest_quality]
                        logger.info(f"使用最高可用的音频质量：{_hq_name}")

                if 'video' in data_source['dash']:
                    # 编码ID映射
                    codec_id_map = {7: "AVC", 12: "HEVC", 13: "AV1"}
                    # 用于去重：同一(qn, codecid)只保留第一个
                    seen_qn_codec = set()
                    
                    for video in data_source['dash']['video']:
                        qn = video.get('id', 0)
                        codecid = video.get('codecid', 7)  # 默认AVC
                        codec_name = codec_id_map.get(codecid, f"编码{codecid}")
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

                        if not is_quality_available(qn, is_login, is_vip):
                            continue

                        
                        # 优先选择稳定 CDN 域名，避免 mcdn 镜像（移动/联通/电信CDN）不稳定
                        # mcdn 域名常出现 Read timed out / Connection refused 等问题
                        _PREFERRED_HOSTS = ['bilivideo.com']  # 官方CDN最稳定
                        _AVOID_HOSTS = ['mcdn.bilivideo.cn']   # 移动镜像CDN不稳定

                        def _pick_best_url(url_list):
                            """从URL列表中选择最稳定的CDN域名"""
                            if not url_list:
                                return ''
                            # 按优先级排序：先找 bilivideo.com（官方），最后才是 mcdn
                            _sorted_urls = sorted(url_list, key=lambda u: (
                                any(m in u for m in _AVOID_HOSTS),  # 避免mcdn排最后
                                -u.count('bilivideo.com')
                            ))
                            return _sorted_urls[0].strip().strip('`')

                        video_url = ''
                        _candidates = []
                        if video.get('baseUrl'):
                            _candidates.append(video.get('baseUrl'))
                        if video.get('url'):
                            _candidates.append(video.get('url'))
                        if video.get('backup_url') and isinstance(video.get('backup_url'), list):
                            _candidates.extend(video.get('backup_url'))
                        if video.get('backupUrl') and isinstance(video.get('backupUrl'), list):
                            _candidates.extend(video.get('backupUrl'))
                        _candidates = [u for u in _candidates if u]
                        if _candidates:
                            video_url = _pick_best_url(_candidates)
                        
                        if video_url:
                            # 按 (qn, codecid) 组合存储，避免不同编码互相覆盖
                            video_urls[(qn, codecid)] = video_url
                            # 同时保留纯qn映射（向后兼容，优先AVC > HEVC > AV1）
                            if qn not in video_urls or codecid == 7:
                                video_urls[qn] = video_url
                            
                            # 去重：同一(qn, codecid)只添加一次
                            if (qn, codecid) not in seen_qn_codec:
                                seen_qn_codec.add((qn, codecid))
                                qualities.append((qn, codecid, quality_name))
                            logger.debug(f"获取视频链接 QN={qn}: {video_url[:50]}...")
                            
                            if not kid:
                                cache_key = f"{bvid}_{cid}"
                                
                                # 检查缓存（加锁，避免并发读写冲突）
                                with KID_CACHE_LOCK:
                                    if cache_key in KID_CACHE:
                                        cached_kid, timestamp = KID_CACHE[cache_key]
                                        if time.time() - timestamp < KID_CACHE_EXPIRY:
                                            kid = cached_kid
                                            logger.info(f"从缓存中获取KID：{kid}")
                                        else:
                                            del KID_CACHE[cache_key]
                                
                                if not kid:
                                    kid = self._extract_kid_from_video_info(video, "API返回的")

                                    # 缓存KID（加锁）
                                    if kid:
                                        with KID_CACHE_LOCK:
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
                        video_urls_list = []
                        for durl_item in data_source['durl']:
                            video_urls_list.append(durl_item['url'])
                        video_url = video_urls_list
                        logger.debug(f"获取多分段视频链接，共{len(video_urls_list)}个分段")
                    else:
                        video_url = data_source['durl'][0]['url']
                        logger.debug(f"获取视频链接：{video_url[:50]}...")
                    
                    # 提取KID（DURL格式）
                    if not kid:
                        cache_key = f"{bvid}_{cid}"
                        
                        # 检查缓存（加锁，避免并发读写冲突）
                        with KID_CACHE_LOCK:
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
                                
                                # 缓存KID（加锁）
                                with KID_CACHE_LOCK:
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

            # 去重并排序
            # qualities 可能是 (qn, name) 或 (qn, codecid, name) 格式
            if qualities and len(qualities[0]) == 3:
                # 新格式：(qn, codecid, name) - 按qn降序，codecid升序（AVC优先）
                codec_priority = {7: 0, 12: 1, 13: 2}
                seen = set()
                unique_qualities = []
                for q in qualities:
                    key = (q[0], q[1])
                    if key not in seen:
                        seen.add(key)
                        unique_qualities.append(q)
                unique_qualities.sort(key=lambda x: (-x[0], codec_priority.get(x[1], 99)))
                qualities = unique_qualities
            else:
                # 旧格式：(qn, name)
                qualities = list(dict.fromkeys(qualities))
                qualities.sort(key=lambda x: x[0], reverse=True)

            # 提取可用的编码列表
            available_codecs = set()
            if qualities and len(qualities[0]) == 3:
                for q in qualities:
                    available_codecs.add(q[1])

            return {
                "success": True,
                "qualities": qualities,
                "video_urls": video_urls,
                "audio_url": audio_url,
                "audio_qualities": audio_qualities,
                "audio_urls": audio_urls,
                "is_vip": is_vip,
                "has_hevc": has_hevc,
                "kid": kid,
                "available_codecs": available_codecs
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
                        audio_urls = {}
                        audio_qualities = []
                        user_info = self.get_user_info()
                        is_login = user_info.get('success', False)
                        is_vip = user_info.get('is_vip', False)
                        has_hevc = False
                        quality_map = self.config.get_quality_map()
                        
                        VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&qn=127&fnval=112&fourk=1&otype=json"
                        else:
                            play_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&qn=127&fnval=112&fnver=0&fourk=1&from_client=BROWSER&drm_tech_type=2&otype=json"
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
                            audio_urls = {}
                            audio_qualities = []
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                                                kid = self._extract_kid_from_video_info(video, "备用链接")
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
                                play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&bvid={bvid}&qn=127&fnval=112&fourk=1&otype=json"
                            else:
                                play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&avid={bvid}&qn=127&fnval=112&fourk=1&otype=json"
                        else:
                            play_url = f"https://api.bilibili.com/pgc/player/web/playurl?cid={cid}&bvid={bvid}&qn=127&fnval=112&fnver=0&fourk=1&from_client=BROWSER&drm_tech_type=2&otype=json"
                        logger.info(f"尝试备用链接（cid+bvid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            audio_urls = {}
                            audio_qualities = []
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                                                kid = self._extract_kid_from_video_info(video, "备用链接")
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
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=127&fnval=112&fourk=1&otype=json"
                        else:
                            play_url = f"https://api.bilibili.com/pgc/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=127&fnval=112&fnver=0&fourk=1&from_client=BROWSER&drm_tech_type=2&otype=json"
                        logger.info(f"尝试备用链接（ep_id+cid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            audio_urls = {}
                            audio_qualities = []
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                                                kid = self._extract_kid_from_video_info(video, "备用链接")
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
                        
                        play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&qn=127&fnval=112&fourk=1&otype=json"
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
                            audio_urls = {}
                            audio_qualities = []
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                                                kid = self._extract_kid_from_video_info(video, "备用链接")
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
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&bvid={bvid}&qn=127&fnval=112&fourk=1&otype=json"
                            logger.info(f"尝试备用链接（cid+bvid）：{play_url}")
                        else:
                            play_url = f"https://api.bilibili.com/pugv/player/web/playurl?cid={cid}&avid={bvid[2:]}&qn=127&fnval=112&fourk=1&otype=json"
                            logger.info(f"尝试备用链接（cid+avid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            audio_urls = {}
                            audio_qualities = []
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                                                kid = self._extract_kid_from_video_info(video, "备用链接")
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
                        play_url = f"https://api.bilibili.com/pugv/player/web/playurl?ep_id={ep_id}&cid={cid}&qn=127&fnval=112&fourk=1&otype=json"
                        logger.info(f"尝试备用链接（ep_id+cid）：{play_url}")
                        
                        
                        success, data = self._api_request(play_url, timeout=15)
                        logger.info(f"备用链接API请求结果：success={success}")
                        
                        if success and data.get('code') == 0:
                            data_source = data.get('data', data.get('result', {}))
                            qualities = []
                            video_urls = {}
                            audio_url = ""
                            audio_urls = {}
                            audio_qualities = []
                            user_info = self.get_user_info()
                            is_login = user_info.get('success', False)
                            is_vip = user_info.get('is_vip', False)
                            has_hevc = False
                            quality_map = self.config.get_quality_map()
                            
                            VIP_ONLY_QN = [74, 100, 112, 116, 125, 126, 127]
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
                                                kid = self._extract_kid_from_video_info(video, "备用链接")
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

    _download_session = None

    def _get_download_session(self, headers=None):
        if self._download_session is None:
            self._download_session = requests.Session()
            self._download_session.verify = False
            self._download_session.proxies = {}
            self._download_session.trust_env = False
            self._download_session.cookies.update(self.session.cookies)
        if headers:
            self._download_session.headers.update(headers)
        return self._download_session

    def _download_segment(self, segment_url, segment_path, headers, segment_index, total_segments, progress_lock, progress_state, is_running=None):
        seg_session = requests.Session()
        seg_session.headers.update(headers)
        seg_session.cookies.update(self.session.cookies)
        seg_session.verify = False
        seg_session.proxies = {}
        seg_session.trust_env = False
        seg_session.timeout = (15, 30)

        max_retries = self.config.get_app_setting("max_retry", 3) if self.config else 3
        try:
            max_retries = int(max_retries)
        except (ValueError, TypeError):
            max_retries = 3
        retry_count = 0
        segment_response = None

        while retry_count < max_retries:
            if is_running is not None and not is_running():
                seg_session.close()
                raise Exception("下载已取消")
            try:
                segment_response = seg_session.get(segment_url, stream=True, headers=headers, timeout=(15, 30))
                logger.info(f"分段 {segment_index+1} 响应状态码：{segment_response.status_code}")
                segment_response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                # 关闭失败的response，避免连接泄漏
                if segment_response is not None:
                    try:
                        segment_response.close()
                    except Exception:
                        pass
                    segment_response = None
                retry_count += 1
                if retry_count >= max_retries:
                    seg_session.close()
                    raise
                # 指数退避：2, 4, 8 秒，给 CDN 缓冲时间
                wait = 2 ** retry_count
                logger.warning(f"分段 {segment_index+1} 请求失败，{wait}秒后重试：{str(e)}")
                time.sleep(wait)

        segment_total_size = int(segment_response.headers.get('content-length', 0))
        logger.info(f"分段 {segment_index+1} 大小：{segment_total_size}字节")

        segment_size_downloaded = 0
        segment_size_pct = 100 / total_segments

        try:
            with open(segment_path, 'wb') as f:
                chunk_size = 65536
                for chunk in segment_response.iter_content(chunk_size=chunk_size):
                    if is_running is not None and not is_running():
                        raise Exception("下载已取消")

                    if chunk:
                        f.write(chunk)
                        chunk_len = len(chunk)
                        segment_size_downloaded += chunk_len

                        with progress_lock:
                            progress_state['cumulative_size'] += chunk_len
                            segment_progress = min(100, int((segment_size_downloaded / segment_total_size) * 100)) if segment_total_size > 0 else 0
                            total_progress = min(99, int((segment_index * segment_size_pct) + (segment_progress * segment_size_pct / 100)))
                            cb = progress_state.get('callback')
                            if cb and total_progress % 5 == 0:
                                cb(total_progress, progress_state['cumulative_size'])
        finally:
            # 确保response和session在任何情况下都被关闭（正常完成、异常、取消）
            if segment_response is not None:
                try:
                    segment_response.close()
                except Exception:
                    pass
            seg_session.close()

        logger.info(f"分段 {segment_index+1} 下载完成，大小：{segment_size_downloaded/1024/1024:.2f}MB")
        return segment_path, segment_size_downloaded

    def download_file(self, url, save_path, progress_callback, file_type="video", bvid=None, is_running=None, kid=None):
        logger.info(f"开始下载{file_type}：{url[:100]}...")
        if is_running is not None and not is_running():
            logger.info("下载已被取消")
            raise Exception("下载已被取消")

        
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
        try:
            os.makedirs(temp_dir, exist_ok=True)
            hide_file(temp_dir)
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
            
            session = self._get_download_session(headers)

            # B站CDN单连接限速，通过多分片并发突破限制
            # 策略：先用Range探针获取文件大小并验证CDN支持Range，再决定是否分片
            CHUNK_THRESHOLD = 2 * 1024 * 1024   # 2MB以上就启用分片
            use_chunked = False
            total_file_size = 0
            # 根据并发任务数动态决定每任务分片数，避免总连接数过多触发 CDN 限流
            # 实际并发连接数 ≈ max_threads × 2(video+audio) × CHUNK_COUNT
            # 目标：总连接数 ≤ 16，避免 B站 CDN 限流（RemoteDisconnected/IncompleteRead）
            try:
                _mt = int(self.config.get_app_setting('max_threads', 4)) if self.config else 4
            except Exception:
                _mt = 4
            if _mt >= 3:
                CHUNK_COUNT = 1   # 多任务并发时已有 task×stream 级并发，不分片避免连接过多
            elif _mt == 2:
                CHUNK_COUNT = 2
            else:
                CHUNK_COUNT = 4   # 单任务时用4分片提升单文件速度

            if not isinstance(url, list):
                # 用Range探针获取文件大小，同时验证CDN是否支持Range请求
                try:
                    probe_headers = dict(headers)
                    probe_headers['Range'] = 'bytes=0-0'
                    probe_resp = session.get(url, headers=probe_headers, timeout=10, allow_redirects=True)
                    if probe_resp.status_code == 206:
                        # CDN支持Range请求
                        cr = probe_resp.headers.get('Content-Range', '')
                        if '/' in cr:
                            total_file_size = int(cr.split('/')[-1])
                        probe_resp.close()
                        if total_file_size >= CHUNK_THRESHOLD:
                            use_chunked = True
                            logger.info(f"CDN支持Range请求，文件大小{total_file_size/1024/1024:.1f}MB，启用分片并发下载")
                    elif probe_resp.status_code == 200:
                        # CDN不支持Range，回退到普通下载
                        total_file_size = int(probe_resp.headers.get('Content-Length', 0))
                        probe_resp.close()
                        logger.info(f"CDN不支持Range请求(status=200)，使用普通下载，文件大小{total_file_size/1024/1024:.1f}MB")
                    else:
                        probe_resp.close()
                        logger.info(f"探针请求返回{probe_resp.status_code}，使用普通下载")
                except Exception as e:
                    logger.warning(f"探针请求失败: {e}，使用普通下载")

                if use_chunked and total_file_size > 0:
                    # 文件过小时不需要分片（分片开销大于收益）
                    # CHUNK_COUNT 已根据 max_threads 动态调整，这里只在小文件时进一步降低
                    if total_file_size < 5 * 1024 * 1024:
                        CHUNK_COUNT = 1   # 小于5MB不分行
                    logger.info(f"文件大小{total_file_size/1024/1024:.1f}MB，启用{CHUNK_COUNT}分片并发下载（max_threads={_mt}）")

            if use_chunked and total_file_size > 0:
                chunk_size = total_file_size // CHUNK_COUNT
                ranges = []
                for i in range(CHUNK_COUNT):
                    start = i * chunk_size
                    end = total_file_size - 1 if i == CHUNK_COUNT - 1 else (i + 1) * chunk_size - 1
                    ranges.append((start, end))

                chunk_paths = []
                for i in range(CHUNK_COUNT):
                    chunk_filename = f"temp_{file_type}_chunk_{i}_{uuid.uuid4().hex}_{int(time.time())}.m4s"
                    chunk_filename = re.sub(r'[\x00-\x1f\x7f:/\\*?"<>|]', '', chunk_filename)
                    chunk_paths.append(os.path.join(temp_dir, chunk_filename))

                progress_lock = threading.Lock()
                progress_state = {
                    'cumulative_size': 0,
                    'chunk_progresses': [0] * CHUNK_COUNT,   # 每片进度 0-100
                    'chunk_sizes': [r[1] - r[0] + 1 for r in ranges],  # 每片字节数
                    'last_callback_overall': -1  # 上次回调的进度值，避免重复
                }
                chunk_results = [None] * CHUNK_COUNT
                chunked_failed = False

                def _download_chunk(chunk_url, chunk_path, chunk_headers, chunk_index, chunk_start, chunk_end):
                    """下载单个分片（支持断点续传和指数退避重试，覆盖请求和流式读取全阶段）"""
                    ch_session = requests.Session()
                    ch_session.headers.update(chunk_headers)
                    ch_session.cookies.update(self.session.cookies)
                    ch_session.verify = False

                    chunk_total = chunk_end - chunk_start + 1
                    chunk_downloaded = 0
                    max_retries = 5
                    for retry in range(max_retries):
                        if is_running is not None and not is_running():
                            ch_session.close()
                            raise Exception("下载已取消")
                        resp = None
                        try:
                            # 支持断点续传：从已下载位置继续
                            cur_start = chunk_start + chunk_downloaded
                            chunk_headers_copy = dict(chunk_headers)
                            chunk_headers_copy['Range'] = f'bytes={cur_start}-{chunk_end}'
                            resp = ch_session.get(chunk_url, stream=True, headers=chunk_headers_copy, timeout=(15, 120))
                            if resp.status_code != 206:
                                _sc = resp.status_code
                                resp.close()
                                resp = None
                                raise Exception(f"CDN返回{_sc}而非206，不支持Range请求")
                            resp.raise_for_status()
                            logger.info(f"分片{chunk_index}开始下载: bytes={cur_start}-{chunk_end} (已续传 {chunk_downloaded/1024/1024:.1f}MB), status=206")

                            # 流式读取也纳入重试范围：IncompleteRead/Connection broken 会在此阶段抛出
                            file_mode = 'ab' if chunk_downloaded > 0 else 'wb'
                            with open(chunk_path, file_mode) as f:
                                for chunk_data in resp.iter_content(chunk_size=1048576):
                                    if is_running is not None and not is_running():
                                        resp.close()
                                        ch_session.close()
                                        raise Exception("下载已取消")
                                    if chunk_data:
                                        f.write(chunk_data)
                                        chunk_downloaded += len(chunk_data)
                                        with progress_lock:
                                            progress_state['cumulative_size'] += len(chunk_data)
                                            chunk_pct = min(100, int(chunk_downloaded * 100 / chunk_total))
                                            progress_state['chunk_progresses'][chunk_index] = chunk_pct
                                            overall = min(99, int(progress_state['cumulative_size'] * 100 / total_file_size))
                                            if progress_callback and overall != progress_state['last_callback_overall'] and overall % 2 == 0:
                                                progress_state['last_callback_overall'] = overall
                                                try:
                                                    progress_callback(overall, progress_state['cumulative_size'], list(progress_state['chunk_progresses']))
                                                except TypeError:
                                                    progress_callback(overall, progress_state['cumulative_size'])

                            resp.close()
                            ch_session.close()
                            logger.info(f"分片{chunk_index}下载完成: {chunk_downloaded/1024/1024:.1f}MB")
                            return chunk_path, chunk_downloaded
                        except Exception as e:
                            if resp is not None:
                                try:
                                    resp.close()
                                except Exception:
                                    pass
                                resp = None
                            # 用户取消下载时直接抛出，不重试
                            if str(e) == "下载已取消":
                                ch_session.close()
                                raise
                            # 取消标志已设置时不再重试，立即抛出
                            if is_running is not None and not is_running():
                                ch_session.close()
                                raise Exception("下载已取消")
                            if retry >= max_retries - 1:
                                ch_session.close()
                                raise
                            # 指数退避：2, 4, 8, 16 秒，给 CDN 缓冲时间
                            wait = 2 ** (retry + 1)
                            logger.warning(f"分片{chunk_index}下载失败(已下载{chunk_downloaded/1024/1024:.1f}MB)，{wait}秒后重试({retry+1}/{max_retries}): {e}")
                            # 可取消的sleep：每0.5秒检查一次取消标志
                            slept = 0
                            while slept < wait:
                                if is_running is not None and not is_running():
                                    ch_session.close()
                                    raise Exception("下载已取消")
                                time.sleep(min(0.5, wait - slept))
                                slept += 0.5

                    ch_session.close()
                    raise Exception(f"分片{chunk_index}下载失败，已重试{max_retries}次")

                try:
                    max_workers = min(CHUNK_COUNT, 4)
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        futures = {}
                        for i in range(CHUNK_COUNT):
                            future = executor.submit(
                                _download_chunk, url, chunk_paths[i], headers,
                                i, ranges[i][0], ranges[i][1]
                            )
                            futures[future] = i

                        for future in as_completed(futures):
                            idx = futures[future]
                            try:
                                chunk_results[idx] = future.result()
                            except Exception as e:
                                # 用户取消属于正常流程，使用INFO级别避免误导
                                if str(e) == "下载已取消":
                                    logger.info(f"分片{idx}下载已取消")
                                else:
                                    logger.error(f"分片{idx}下载失败: {e}")
                                chunked_failed = True
                                raise

                    logger.info(f"合并{CHUNK_COUNT}个分片...")
                    _MERGE_BUF = 4 * 1024 * 1024  # 4MB缓冲区，减少系统调用次数
                    with open(temp_path, 'wb') as outfile:
                        for chunk_path, _ in chunk_results:
                            with open(chunk_path, 'rb') as infile:
                                while True:
                                    data = infile.read(_MERGE_BUF)
                                    if not data:
                                        break
                                    outfile.write(data)
                            try:
                                os.remove(chunk_path)
                            except Exception:
                                pass

                    downloaded_size = total_file_size
                    if progress_callback:
                        progress_callback(100, downloaded_size)
                except Exception as e:
                    # 用户取消下载时直接抛出，不回退到普通下载（避免取消后仍发起新请求）
                    if str(e) == "下载已取消" or (is_running is not None and not is_running()):
                        for cp in chunk_paths:
                            try:
                                if os.path.exists(cp):
                                    os.remove(cp)
                            except Exception:
                                pass
                        raise
                    # 分片下载失败，清理临时文件并回退到普通下载
                    logger.warning(f"分片下载失败: {e}，回退到普通下载")
                    chunked_failed = True
                    for cp in chunk_paths:
                        try:
                            if os.path.exists(cp):
                                os.remove(cp)
                        except Exception:
                            pass
                    # 等待 3 秒让 CDN 缓冲，避免立即再次冲击触发限流
                    time.sleep(3)
                    # 继续走下面的普通下载逻辑

                if not chunked_failed:
                    # 分片下载成功，直接返回临时文件路径
                    return temp_path
                else:
                    # 分片失败，重置标记，回退到普通下载
                    use_chunked = False

            # 检查是否是多分段下载
            if isinstance(url, list):
                logger.info(f"开始多分段并发下载，共{len(url)}个分段")
                total_segments = len(url)
                
                segment_paths = []
                for i, segment_url in enumerate(url):
                    segment_filename = f"temp_{file_type}_segment_{i}_{uuid.uuid4().hex}_{int(time.time())}.m4s"
                    segment_filename = re.sub(r'[\x00-\x1f\x7f:/\\*?"<>|]', '', segment_filename)
                    segment_path = os.path.join(temp_dir, segment_filename)
                    segment_paths.append(segment_path)
                    logger.info(f"准备下载分段 {i+1}/{total_segments}：{segment_url[:100]}...")
                
                progress_lock = threading.Lock()
                progress_state = {
                    'cumulative_size': 0,
                    'callback': progress_callback
                }
                
                max_workers = min(total_segments, 4)
                segment_results = [None] * total_segments
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {}
                    for i, segment_url in enumerate(url):
                        future = executor.submit(
                            self._download_segment,
                            segment_url, segment_paths[i], headers,
                            i, total_segments,
                            progress_lock, progress_state,
                            is_running
                        )
                        futures[future] = i
                    
                    for future in as_completed(futures):
                        idx = futures[future]
                        try:
                            seg_path, seg_size = future.result()
                            segment_results[idx] = (seg_path, seg_size)
                        except Exception as e:
                            logger.error(f"分段 {idx+1} 下载失败：{str(e)}")
                            executor.shutdown(wait=False, cancel_futures=True)
                            # 清理已下载的分段文件，避免临时文件残留
                            for sp in segment_paths:
                                try:
                                    if os.path.exists(sp):
                                        os.remove(sp)
                                except Exception:
                                    pass
                            raise
                
                cumulative_size = progress_state['cumulative_size']
                
                # 合并所有分段（按顺序）
                logger.info(f"开始合并{total_segments}个分段")
                _MERGE_BUF = 4 * 1024 * 1024  # 4MB缓冲区，减少系统调用次数
                with open(temp_path, 'wb') as outfile:
                    for seg_path, _ in segment_results:
                        with open(seg_path, 'rb') as infile:
                            while True:
                                data = infile.read(_MERGE_BUF)
                                if not data:
                                    break
                                outfile.write(data)
                        try:
                            os.remove(seg_path)
                            logger.debug(f"删除已合并的分段文件：{seg_path}")
                        except Exception as e:
                            logger.warning(f"删除分段文件失败：{str(e)}")
                
                downloaded_size = cumulative_size
                logger.info(f"分段合并完成，总大小：{downloaded_size/1024/1024:.2f}MB")
            elif not use_chunked:
                # 单个URL下载（原有逻辑，或分片下载失败后的回退）
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
                max_retries = self.config.get_app_setting("max_retry", 3) if self.config else 3
                try:
                    max_retries = int(max_retries)
                except (ValueError, TypeError):
                    max_retries = 3
                retry_count = 0
                response = None
                while retry_count < max_retries:
                    try:
                        response = session.get(url, stream=True, headers=headers, timeout=(15, 30))
                        logger.info(f"响应状态码：{response.status_code}")
                        
                        
                        if response.status_code == 416:
                            logger.info("文件已下载完成")
                            response.close()
                            if progress_callback:
                                progress_callback(100, downloaded_size)
                            return temp_path
                        
                        response.raise_for_status()
                        break
                    except requests.exceptions.RequestException as e:
                        # 关闭失败的response，避免连接泄漏（stream=True需显式close）
                        if response is not None:
                            try:
                                response.close()
                            except Exception:
                                pass
                            response = None
                        retry_count += 1
                        if retry_count >= max_retries:
                            raise
                        # 指数退避：2, 4 秒，给 CDN 缓冲时间
                        wait = 2 ** retry_count
                        logger.warning(f"请求失败，{wait}秒后重试：{str(e)}")
                        time.sleep(wait)

            
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
                    # 取消标志已设置时不再重试，立即抛出
                    if is_running is not None and not is_running():
                        raise Exception("下载已取消")
                    if download_retry_count >= max_download_retries:
                        logger.error(f"下载失败，已重试{max_download_retries}次：{str(e)}")
                        raise Exception(f"网络连接中断，下载失败：{str(e)}")

                    # 关闭异常的response，避免连接泄漏
                    if response is not None:
                        try:
                            response.close()
                        except Exception:
                            pass
                        response = None

                    # 指数退避：2, 4 秒，给 CDN 缓冲时间，避免立即再次触发限流
                    wait = 2 ** download_retry_count
                    logger.warning(f"下载中断，{wait}秒后重试：{str(e)}")
                    # 可取消的sleep：每0.5秒检查一次取消标志
                    slept = 0
                    while slept < wait:
                        if is_running is not None and not is_running():
                            raise Exception("下载已取消")
                        time.sleep(min(0.5, wait - slept))
                        slept += 0.5

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
                            response.close()
                            response = None
                            download_success = True
                            break
                        
                        response.raise_for_status()
                    except Exception as retry_e:
                        logger.error(f"断点续传请求失败：{str(retry_e)}")
                        if download_retry_count >= max_download_retries:
                            raise Exception(f"断点续传失败：{str(retry_e)}")
            # 下载完成，关闭response释放连接
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
                response = None
            if progress_callback:
                progress_callback(100, downloaded_size)
            
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
                        decrypted_path = asyncio.run(self._decrypt_with_bento4(temp_path, decrypted_path, kid))
                        # 等待文件系统稳定
                        import time
                        time.sleep(1)
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
                if os.path.isdir(save_path):
                    actual_save_path = os.path.join(save_path, os.path.basename(temp_path))
                else:
                    actual_save_path = save_path
                if os.path.exists(actual_save_path):
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            os.remove(actual_save_path)
                            break
                        except Exception as remove_e:
                            logger.warning(f"删除文件失败（尝试{attempt+1}/{max_retries}）：{str(remove_e)}")
                            if attempt < max_retries - 1:
                                time.sleep(1)
                            else:
                                raise
                shutil.move(temp_path, actual_save_path)
                logger.info(f"文件已保存到：{actual_save_path}")

                if not os.path.exists(actual_save_path) or os.path.getsize(actual_save_path) == 0:
                    from utils import verify_and_ensure_save
                    actual_path, saved = verify_and_ensure_save(actual_save_path, source_path=temp_path if os.path.exists(temp_path) else None)
                    if saved:
                        logger.info(f"文件保存验证修复成功：{actual_path}")
                        return actual_path
                    else:
                        logger.error(f"文件保存验证失败，目标路径：{actual_save_path}")

                return actual_save_path
            except Exception as e:
                logger.error(f"移动文件失败：{str(e)}")
                if os.path.exists(temp_path):
                    from utils import verify_and_ensure_save
                    actual_path, saved = verify_and_ensure_save(actual_save_path, source_path=temp_path)
                    if saved:
                        logger.info(f"移动失败后备用保存成功：{actual_path}")
                        return actual_path
                logger.warning("返回临时文件路径")
                return temp_path
        except requests.exceptions.Timeout as e:
            logger.error(f"下载超时：{str(e)}")
            raise Exception(f"下载超时：{str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求失败：{str(e)}")
            raise Exception(f"网络请求失败：{str(e)}")
        except Exception as e:
            if "取消" in str(e) or "TASK_PAUSED" in str(e):
                logger.info(f"下载中断：{str(e)}")
                raise
            logger.error(f"下载错误：{str(e)}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logger.debug(f"已清理临时文件：{temp_path}")
                except Exception as clean_e:
                    logger.warning(f"清理临时文件失败：{clean_e}")
            raise Exception(f"{file_type}下载失败：{str(e)}")

    @staticmethod
    def _extract_kid_from_video_info(video, log_prefix=""):
        """从API返回的video字典中提取KID（统一逻辑，修复elif短路bug）

        按优先级依次尝试: bilidrm_uri → uri → baseUrl → base_url → widevine_pssh
        每个字段独立检查，避免elif导致前一个字段存在但无KID时后续字段被跳过。
        """
        import base64 as _b64
        kid = None

        # 1. bilidrm_uri
        if not kid and video.get('bilidrm_uri'):
            uri = video['bilidrm_uri']
            m = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
            if m:
                kid = m.group(1)
                logger.info(f"{log_prefix}从bilidrm_uri中提取到KID：{kid}")

        # 2. uri
        if not kid and video.get('uri'):
            uri = video['uri']
            m = re.search(r'uri:bili://([0-9a-f]{32})', uri, re.IGNORECASE)
            if m:
                kid = m.group(1)
                logger.info(f"{log_prefix}从URI中提取到KID：{kid}")

        # 3. baseUrl
        if not kid and video.get('baseUrl'):
            m = re.search(r'kid=([0-9a-fA-F]{32})', video['baseUrl'])
            if m:
                kid = m.group(1)
                logger.info(f"{log_prefix}从baseUrl参数中提取到KID：{kid}")

        # 4. base_url
        if not kid and video.get('base_url'):
            m = re.search(r'kid=([0-9a-fA-F]{32})', video['base_url'])
            if m:
                kid = m.group(1)
                logger.info(f"{log_prefix}从base_url参数中提取到KID：{kid}")

        # 5. widevine_pssh
        if not kid and video.get('widevine_pssh'):
            try:
                pssh_data = _b64.b64decode(video['widevine_pssh'])
                if len(pssh_data) >= 32:
                    widevine_sid = bytes.fromhex('edef8ba979d64acea3c827dcd51d21ed')
                    sid_pos = pssh_data.find(widevine_sid)
                    if sid_pos >= 0:
                        data_size_pos = sid_pos + 16
                        if data_size_pos + 4 <= len(pssh_data):
                            data_size = int.from_bytes(pssh_data[data_size_pos:data_size_pos + 4], 'big')
                            data_start = data_size_pos + 4
                            data_end = min(data_start + data_size, len(pssh_data))
                            payload = pssh_data[data_start:data_end]
                            idx = payload.find(b'\x12\x10')
                            if idx >= 0 and idx + 2 + 16 <= len(payload):
                                extracted = payload[idx + 2:idx + 18].hex()
                                if extracted != '0' * 32:
                                    kid = extracted
                                    logger.info(f"{log_prefix}从widevine_pssh中提取到KID：{kid}")
                            else:
                                version = pssh_data[sid_pos - 4] if sid_pos >= 4 else 0
                                if version == 1 and len(payload) >= 4 + 16:
                                    kid_count = int.from_bytes(payload[:4], 'big')
                                    if kid_count > 0:
                                        extracted = payload[4:20].hex()
                                        if extracted != '0' * 32:
                                            kid = extracted
                                            logger.info(f"{log_prefix}从widevine_pssh(v1)中提取到KID：{kid}")
            except Exception as pssh_e:
                logger.warning(f"{log_prefix}从widevine_pssh提取KID失败: {pssh_e}")

        return kid

    def _extract_kid_from_binary(self, m4s_path):
        """直接从m4s二进制文件中解析tenc/pssh box提取KID

        Bento4 mp4dump/mp4info无法处理截断的文件（ERROR: cannot open input -4），
        此方法直接扫描二进制数据查找tenc box，不依赖完整的MP4文件结构，
        因此对截断的临时文件（仅含文件头部）也能正常工作。

        CENC tenc box格式（FullBox）:
          [size(4)][type='tenc'(4)][version(1)][flags(3)]
          [reserved1(1)][reserved2/crypt+skip(1~2)][is_protected(1)][per_sample_iv_size(1)][KID(16)]
        KID是box的最后一部分，可直接通过box size定位。
        """
        try:
            # 读取前2MB数据，moov box（含tenc）在fMP4中位于文件头部
            _READ_SIZE = 2 * 1024 * 1024
            with open(m4s_path, 'rb') as f:
                data = f.read(_READ_SIZE)

            if not data or len(data) < 32:
                logger.warning(f"二进制解析KID：文件过小或无法读取（{len(data) if data else 0}字节）")
                return None

            # 1. 查找 tenc box（Track Encryption Box）
            tenc_marker = b'tenc'
            pos = 0
            while True:
                pos = data.find(tenc_marker, pos)
                if pos < 0:
                    break
                # tenc marker前的4字节是box size（big-endian）
                if pos >= 4:
                    box_size = int.from_bytes(data[pos - 4:pos], 'big')
                    # tenc box大小通常为32（v0）或33（v1）字节，合理范围28~64
                    if 28 <= box_size <= 64:
                        # KID是box最后16字节
                        box_start = pos - 4
                        kid_start = box_start + box_size - 16
                        kid_end = kid_start + 16
                        if kid_end <= len(data):
                            kid_bytes = data[kid_start:kid_end]
                            # 排除全0的KID
                            if kid_bytes != b'\x00' * 16:
                                kid = kid_bytes.hex()
                                logger.info(f"从tenc box中提取到KID：{kid}（pos={pos}, box_size={box_size}）")
                                return kid
                pos += 4

            # 2. 查找 pssh box（Protection System Specific Header Box）作为降级方案
            # B站Widevine PSSH为v0：SystemID后是DataSize+Data，KID在Data的protobuf field2(0x12 0x10 + 16字节)
            widevine_sid = bytes.fromhex('edef8ba979d64acea3c827dcd51d21ed')
            pssh_marker = b'pssh'
            pos = 0
            while True:
                pos = data.find(pssh_marker, pos)
                if pos < 0:
                    break
                if pos >= 4:
                    box_size = int.from_bytes(data[pos - 4:pos], 'big')
                    # pssh box至少32字节
                    if box_size >= 32 and pos + box_size - 4 <= len(data):
                        # SystemID在version+flags之后(pos+8开始)
                        sys_id_start = pos + 8
                        sys_id_end = sys_id_start + 16
                        if sys_id_end <= len(data) and data[sys_id_start:sys_id_end] == widevine_sid:
                            # DataSize(4字节) + Data
                            if sys_id_end + 4 <= len(data):
                                data_size = int.from_bytes(data[sys_id_end:sys_id_end + 4], 'big')
                                pssh_payload_start = sys_id_end + 4
                                pssh_payload_end = min(pssh_payload_start + data_size, len(data))
                                pssh_payload = data[pssh_payload_start:pssh_payload_end]
                                # 查找protobuf pattern: 0x12 0x10 + 16字节KID
                                idx = pssh_payload.find(b'\x12\x10')
                                if idx >= 0 and idx + 2 + 16 <= len(pssh_payload):
                                    kid_bytes = pssh_payload[idx + 2:idx + 18]
                                    if kid_bytes != b'\x00' * 16:
                                        kid = kid_bytes.hex()
                                        logger.info(f"从pssh box(Widevine v0)中提取到KID：{kid}")
                                        return kid
                pos += 4

            logger.warning("二进制解析KID：未找到tenc/pssh box或KID为空")
            return None
        except Exception as e:
            logger.error(f"二进制解析KID时出错：{str(e)}")
            import traceback
            logger.debug("traceback", exc_info=True)
            return None

    def _extract_kid_from_m4s(self, m4s_path):
        import re

        # 如果路径含非ASCII字符，优先尝试8.3短路径转换，避免复制文件
        # 优化：Bento4 mp4dump/mp4info只需要文件头部即可提取KID，不需要复制整个文件
        # 对于大文件（如584MB视频），完整复制会因临时盘空间不足而失败（Errno 28）
        # 策略：1.优先8.3短路径转换（零开销）2.短路径失败时复制前1MB到ASCII安全临时目录
        original_m4s_path = m4s_path
        _temp_m4s_copied = False
        if has_non_ascii(m4s_path):
            # 优先尝试8.3短路径转换，成功则无需复制文件
            short_path = to_short_path(m4s_path)
            if short_path != m4s_path:
                m4s_path = short_path
                logger.info(f"[KID提取] 中文路径，使用8.3短路径：{short_path}")
            else:
                # 短路径转换失败，回退到复制文件头部到ASCII安全临时目录
                try:
                    _tmp_dir = self.safe_temp_dir
                    _unique_name = f"m4s_extract_{os.getpid()}_{int(time.time() * 1000) % 1000000}_{os.path.basename(m4s_path)}"
                    _tmp_path = os.path.join(_tmp_dir, _unique_name)
                    
                    # 只复制文件头部（前1MB），KID等元数据位于moov/tenc box中，通常在文件头部
                    # 对于B站DRM加密的m4s文件，moov box在文件开头，1MB足够包含完整moov
                    _HEAD_BYTES = 1024 * 1024  # 1MB
                    with open(m4s_path, 'rb') as src_f:
                        head_data = src_f.read(_HEAD_BYTES)
                    with open(_tmp_path, 'wb') as dst_f:
                        dst_f.write(head_data)
                    m4s_path = _tmp_path
                    _temp_m4s_copied = True
                    logger.info(f"[KID提取] 短路径转换失败，复制文件头部({_HEAD_BYTES//1024}KB)到临时目录：{_tmp_path}")
                except Exception as _e:
                    logger.warning(f"[KID提取] 复制到临时目录失败，使用原路径：{_e}")
        
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
            
            # 优先使用二进制解析提取KID（不依赖Bento4，对截断文件也能工作）
            logger.info("尝试通过二进制解析提取KID...")
            kid = self._extract_kid_from_binary(m4s_path)
            if kid:
                return kid

            bento4_path = os.path.join(self.bento4_dir, exe('mp4dump'))
            if os.path.exists(bento4_path):
                try:
                    absolute_path = os.path.abspath(m4s_path)
                    logger.info(f"使用绝对路径：{absolute_path}")

                    cmd = [bento4_path, absolute_path]
                    logger.info(f"执行命令：{' '.join(cmd)}")
                    
                    import subprocess
                    result = subprocess.run(cmd, capture_output=True, text=False, timeout=30,
                                          **subprocess_no_window_kwargs())
                    
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
            
            mp4info_path = os.path.join(self.bento4_dir, exe('mp4info'))
            if os.path.exists(mp4info_path):
                try:
                    absolute_path = os.path.abspath(m4s_path)
                    cmd = [mp4info_path, absolute_path]
                    logger.info(f"执行命令：{' '.join(cmd)}")
                    
                    import subprocess
                    result = subprocess.run(cmd, capture_output=True, text=False, timeout=30,
                                          **subprocess_no_window_kwargs())
                    
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
            logger.debug("traceback", exc_info=True)
            return None
        finally:
            if _temp_m4s_copied and m4s_path != original_m4s_path:
                try:
                    if os.path.exists(m4s_path):
                        os.remove(m4s_path)
                except Exception:
                    pass

    async def _decrypt_with_bento4(self, input_file, output_file, kid=None):
        """使用Bento4 mp4decrypt解密DRM保护的m4s文件
        返回: 解密后的文件路径
        异常: 解密失败时抛出异常（不再静默复制加密文件）
        """
        # 提前初始化，防止早期异常时 except 块引用未定义变量
        need_temp_copy = False
        temp_input = None
        temp_output = None
        # 使用预计算的ASCII安全临时目录，避免系统临时目录含中文用户名导致mp4decrypt无法打开文件
        temp_dir = self.safe_temp_dir
        
        try:
            if not kid:
                # 没有提供kid，尝试提取
                try:
                    kid = self._extract_kid_from_m4s(input_file)
                    logger.info(f"提取到KID：{kid}")
                except Exception as e:
                    logger.warning(f"提取KID时发生异常：{str(e)}")

                if not kid:
                    raise Exception("无法获取DRM KID，无法解密")

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
                raise Exception("多次尝试后仍然无法获取DRM密钥")

            logger.info(f"使用KID {kid} 和密钥 {key} 解密文件")
            
            if not os.path.exists(input_file):
                raise Exception(f"输入文件不存在：{input_file}")
            
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            input_file = os.path.abspath(input_file)
            output_file = os.path.abspath(output_file)
            
            base_name = os.path.basename(output_file)
            if not base_name.endswith('.mp4'):
                output_file = os.path.join(os.path.dirname(output_file), f"{os.path.splitext(base_name)[0]}.mp4")
            
            logger.info(f"输入文件绝对路径：{input_file}")
            logger.info(f"输出文件绝对路径：{output_file}")
            
            # temp_dir 已在方法开头设置为ASCII安全临时目录
            # need_temp_copy: 标记是否使用了临时输出路径（需后续复制回原位置和清理）
            # temp_input_is_copy: 标记temp_input是否为复制的副本（需清理，短路径转换的不删除）
            need_temp_copy = False
            temp_input_is_copy = False
            temp_input = input_file
            temp_output = output_file
            
            # 检查输入/输出路径是否含非ASCII字符（中文用户名/安装路径）
            input_has_non_ascii = has_non_ascii(input_file)
            output_has_non_ascii = has_non_ascii(output_file)
            
            if input_has_non_ascii or output_has_non_ascii:
                # 输入路径处理：优先8.3短路径转换，避免复制大文件
                if input_has_non_ascii:
                    short_input = to_short_path(input_file)
                    if short_input != input_file:
                        # 短路径转换成功，直接使用短路径，无需复制文件
                        temp_input = short_input
                        logger.info(f"输入文件使用8.3短路径：{short_input}")
                    else:
                        # 短路径转换失败（文件不存在或8.3被禁用），回退到复制方式
                        temp_input = os.path.join(temp_dir, f"decrypt_input_{os.getpid()}_{int(time.time() * 1000) % 100000000}_{os.path.basename(input_file)}")
                        shutil.copy2(input_file, temp_input)
                        temp_input_is_copy = True  # 标记为复制的副本，异常时需清理
                        logger.info(f"输入文件短路径转换失败，复制到临时目录：{temp_input}")
                
                # 输出路径处理：只要输入或输出含中文，输出都使用ASCII临时路径
                # ffmpeg新版本虽支持中文路径，但混合斜杠/不同locale仍可能崩溃，统一用ASCII最安全
                temp_output = os.path.join(temp_dir, f"decrypt_output_{os.getpid()}_{int(time.time() * 1000) % 100000000}.mp4")
                need_temp_copy = True  # 标记需要后续复制回原位置
                logger.info(f"输出文件使用ASCII临时路径：{temp_output}")
            
            try:
                # 优先使用程序自带的ffmpeg，避免系统PATH中的不兼容版本导致崩溃
                ffmpeg_exec = self.ffmpeg_local
                if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                    ffmpeg_exec = shutil.which('ffmpeg')
                if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                    raise Exception("未找到ffmpeg")
                # 规范化路径：shutil.which可能返回正斜杠混合的路径，统一为反斜杠
                ffmpeg_exec = os.path.normpath(ffmpeg_exec)
                
                cmd = [
                    ffmpeg_exec,
                    '-decryption_key', f'{key}',
                    '-i', temp_input,
                    '-c', 'copy',
                    '-y',
                    temp_output
                ]
                logger.info(f"使用ffmpeg执行解密命令：{' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = _decode_subprocess_output(stderr)
                    logger.error(f"ffmpeg解密失败，返回码：{process.returncode}")
                    logger.error(f"错误输出：{error_msg}")
                    logger.error(f"标准输出：{_decode_subprocess_output(stdout)}")
                    # 清理可能产生的半成品输出文件
                    if need_temp_copy and temp_output and os.path.exists(temp_output):
                        try:
                            os.remove(temp_output)
                        except Exception:
                            pass
                    raise Exception(f"ffmpeg解密失败：{error_msg}")

                # ffmpeg返回码为0不代表一定写出了输出文件，必须验证
                actual_output = temp_output if need_temp_copy else output_file
                
                # 等待文件系统刷新（某些情况下ffmpeg进程已结束但文件尚未落盘）
                await asyncio.sleep(0.5)
                
                if not os.path.exists(actual_output):
                    stderr_text = _decode_subprocess_output(stderr).strip()
                    stdout_text = _decode_subprocess_output(stdout).strip()
                    logger.error(f"ffmpeg返回成功但输出文件不存在: {actual_output}")
                    logger.error(f"ffmpeg stderr: {stderr_text[:500] if stderr_text else '(空)'}")
                    logger.error(f"ffmpeg stdout: {stdout_text[:500] if stdout_text else '(空)'}")
                    raise Exception(f"ffmpeg解密后输出文件不存在: {actual_output}")
                
                output_size = os.path.getsize(actual_output)
                if output_size < 1024:
                    logger.error(f"ffmpeg解密输出文件过小: {actual_output}, 大小={output_size}字节")
                    raise Exception(f"ffmpeg解密输出文件过小: {output_size}字节")
                
                logger.info(f"ffmpeg解密输出文件验证通过: {actual_output} ({output_size}字节)")
                
                if need_temp_copy and temp_output != output_file:
                    shutil.copy2(temp_output, output_file)
                    logger.info(f"复制解密结果到目标路径：{output_file}")
                
                logger.info(f"ffmpeg解密成功：{input_file} -> {output_file}")
                return output_file
            except Exception as ffmpeg_e:
                logger.warning(f"ffmpeg解密失败，尝试使用Bento4：{str(ffmpeg_e)}")
                
                bento4_path = os.path.join(self.bento4_dir, exe('mp4decrypt'))
                if not os.path.exists(bento4_path):
                    raise Exception(f"Bento4 mp4decrypt工具不存在：{bento4_path}")
                
                if temp_input_is_copy and os.path.exists(temp_input):
                    # temp_input是复制的副本，Bento4可直接使用，后续清理会删除
                    simple_input = temp_input
                else:
                    # temp_input是原文件或短路径（指向原文件），需复制一份给Bento4用
                    # 避免Bento4分支后续清理逻辑误删原文件
                    # 使用唯一后缀避免多任务并发时临时文件名冲突
                    _unique_suffix = f"{os.getpid()}_{int(time.time() * 1000) % 1000000}_{os.urandom(4).hex()}"
                    simple_input = os.path.join(temp_dir, f"bento4_input_{_unique_suffix}.m4s")
                    # 优先从短路径/原路径复制，确保得到ASCII安全路径的副本
                    shutil.copy2(temp_input, simple_input)
                    logger.info(f"复制文件到ASCII安全临时目录：{simple_input}")
                # simple_output 基于已有的 simple_input 名生成，确保唯一
                simple_output = os.path.splitext(simple_input)[0] + ".decrypted.mp4"
                
                # 异步执行Bento4命令
                cmd = [bento4_path, '--key', f'{kid}:{key}', simple_input, simple_output]
                logger.info(f"使用Bento4执行解密命令：{' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    error_msg = _decode_subprocess_output(stderr)
                    logger.error(f"Bento4解密失败，返回码：{process.returncode}")
                    logger.error(f"错误输出：{error_msg}")
                    logger.error(f"标准输出：{_decode_subprocess_output(stdout)}")
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

                if os.path.exists(simple_output) and os.path.getsize(simple_output) > 1024:
                    shutil.copy2(simple_output, output_file)
                    logger.info(f"复制解密后的文件到目标位置：{output_file}")
                else:
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
            logger.debug("traceback", exc_info=True)
            if need_temp_copy:
                # 只清理复制的输入副本和临时输出文件，短路径转换的输入文件不删除（指向原文件）
                files_to_clean = []
                if temp_input_is_copy and temp_input and os.path.exists(temp_input):
                    files_to_clean.append(temp_input)
                if temp_output and temp_output != output_file and os.path.exists(temp_output):
                    files_to_clean.append(temp_output)
                for tf in files_to_clean:
                    try:
                        os.remove(tf)
                    except Exception:
                        pass
            raise

    def _check_encryption(self, video_path):
        try:
            if not video_path or not os.path.exists(video_path):
                logger.error(f"加密检测：文件不存在：{video_path}")
                return False, ""

            # 中文路径适配：优先8.3短路径转换，避免ffprobe处理中文路径时崩溃
            if has_non_ascii(video_path):
                short_path = to_short_path(video_path)
                if short_path != video_path:
                    logger.info(f"加密检测：使用8.3短路径：{short_path}")
                    video_path = short_path

            file_size = os.path.getsize(video_path)
            logger.info(f"加密检测：文件大小={file_size}字节")

            if file_size < 1024:
                logger.warning("加密检测：文件过小，可能是加密文件")
                return True, "加密文件"

            try:
                # 优先使用程序自带的ffprobe（从ffmpeg_local推导），避免系统PATH中的不兼容版本导致崩溃
                ffprobe_exec = None
                if self.ffmpeg_local and os.path.exists(self.ffmpeg_local):
                    ffprobe_path = os.path.join(os.path.dirname(self.ffmpeg_local), exe('ffprobe'))
                    if os.path.exists(ffprobe_path):
                        ffprobe_exec = os.path.normpath(ffprobe_path)
                if not ffprobe_exec or not os.path.exists(ffprobe_exec):
                    ffprobe_exec = shutil.which('ffprobe')
                    if ffprobe_exec:
                        ffprobe_exec = os.path.normpath(ffprobe_exec)

                if ffprobe_exec and os.path.exists(ffprobe_exec):
                    cmd = [ffprobe_exec, '-i', video_path, '-v', 'error', '-print_format', 'json', '-show_format', '-show_streams']
                    logger.info(f"加密检测：使用ffprobe检测文件类型，命令={cmd}")
                    result = subprocess.run(cmd, capture_output=True, text=False, timeout=30,
                                          **subprocess_no_window_kwargs())
                    stdout = result.stdout.decode('utf-8', errors='replace')
                    stderr = result.stderr.decode('utf-8', errors='replace')
                    logger.info(f"加密检测：ffprobe返回码={result.returncode}")
                    logger.info(f"加密检测：ffprobe stdout={stdout}")
                    logger.info(f"加密检测：ffprobe stderr={stderr}")

                    decode_errors = ['error while decoding', 'top block unavailable',
                                     'Could not open codec', 'Decrypting not allowed']
                    has_decode_error = any(error in stderr for error in decode_errors)

                    has_encryption_error = 'Decrypt' in stderr or 'encrypted' in stderr.lower()

                    # B站课程加密m4s：文件头是合法ftyp box（DASH标准容器）但内容加密，
                    # ffprobe返回码!=0且报"Invalid data"/"error reading header"是典型加密特征
                    has_invalid_data = 'Invalid data found' in stderr or 'error reading header' in stderr

                    if result.returncode == 0 and not has_decode_error:
                        logger.info("加密检测：ffprobe检测成功，文件格式正常")
                        return False, ""
                    elif has_encryption_error:
                        logger.warning("加密检测：ffprobe输出明确加密错误，标记为加密文件")
                        return True, "加密文件"
                    elif has_decode_error:
                        logger.warning("加密检测：ffprobe解码错误，可能是加密文件")
                        return True, "加密文件"
                    elif result.returncode != 0 and has_invalid_data:
                        # ffprobe读不了文件但文件头是合法MP4，说明内容被加密（cbcs/cenc）
                        logger.warning(f"加密检测：ffprobe返回码={result.returncode}且数据无效，疑似加密文件")
                        return True, "加密文件"
                    else:
                        logger.warning(f"加密检测：ffprobe检测失败但非加密特征，继续备选检测")
            except Exception as ffprobe_e:
                logger.error(f"加密检测：ffprobe检测异常：{str(ffprobe_e)}")
                logger.warning("加密检测：ffprobe检测异常，继续使用备选检测方法")

            logger.info("加密检测：使用文件头备选检测方法")

            with open(video_path, 'rb') as f:
                header = f.read(256)
                logger.info(f"加密检测：文件头前256字节={header[:256].hex()}")

                if header.startswith(b'RDM'):
                    logger.warning("加密检测：检测到RDM加密")
                    return True, "RDM"

                if header.startswith(b'AES-'):
                    logger.warning("加密检测：检测到AES加密文件头")
                    return True, "AES"

                if header.startswith(b'Widevine') or header.startswith(b'PlayReady') or header.startswith(b'FairPlay'):
                    logger.warning("加密检测：检测到DRM系统文件头")
                    return True, "DRM"

                if header.startswith(b'ftyp') or (len(header) >= 8 and header[4:8] == b'ftyp'):
                    logger.info("加密检测：检测到MP4/m4s文件")
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

                if header.startswith(b'ID3'):
                    logger.info("加密检测：检测到MP3文件")
                    return False, ""

                if header.startswith(b'RIFF') and b'WAVE' in header[:12]:
                    logger.info("加密检测：检测到WAV文件")
                    return False, ""

                if header.startswith(b'ADIF') or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xF0) == 0xF0):
                    logger.info("加密检测：检测到AAC文件")
                    return False, ""

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
            logger.debug("traceback", exc_info=True)
            logger.warning("加密检测：检测异常，默认不标记为加密（避免误报）")
            return False, ""
            
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
            
            for idx, xml_url in enumerate(xml_urls):
                logger.info(f"尝试使用XML弹幕API：{xml_url}")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                        'Referer': 'https://www.bilibili.com',
                        'Accept-Encoding': 'gzip, deflate'
                    }
                    
                    # 第一个URL(comment.bilibili.com)不稳定时容易超时，使用较短超时快速回退到备用API
                    xml_timeout = 5 if idx == 0 else 10
                    response = self.session.get(xml_url, headers=headers, timeout=xml_timeout)
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
                    logger.debug("traceback", exc_info=True)
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
                    logger.debug("traceback", exc_info=True)
                    continue
            
            logger.info("所有API都未获取到弹幕")
            return {"data": {"danmaku": [], "count": 0}, "error": ""}
        except Exception as e:
            logger.error(f"获取弹幕失败：{str(e)}")
            import traceback
            logger.debug("traceback", exc_info=True)
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
            logger.debug("traceback", exc_info=True)
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
        try:
            import subprocess
            # 中文路径适配：优先8.3短路径转换
            if has_non_ascii(video_path):
                short_path = to_short_path(video_path)
                if short_path != video_path:
                    video_path = short_path
            ffprobe_exec = None
            ffmpeg_dir = os.path.dirname(ffmpeg_exec)
            if ffmpeg_dir:
                candidate = os.path.join(ffmpeg_dir, exe('ffprobe'))
                if os.path.exists(candidate):
                    ffprobe_exec = os.path.normpath(candidate)
            if not ffprobe_exec:
                ffprobe_exec = shutil.which('ffprobe')
                if ffprobe_exec:
                    ffprobe_exec = os.path.normpath(ffprobe_exec)
            if not ffprobe_exec or not os.path.exists(ffprobe_exec):
                logger.warning("未找到ffprobe，无法检测视频编码")
                return 'unknown'
            cmd = [
                ffprobe_exec,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                video_path
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                **subprocess_no_window_kwargs(),
                timeout=30
            )
            if result.returncode != 0:
                logger.warning(f"ffprobe检测视频编码失败，返回码：{result.returncode}")
                return 'unknown'
            import json
            output = result.stdout.decode('utf-8', errors='ignore')
            data = json.loads(output)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    codec = stream.get('codec_name', 'unknown')
                    logger.info(f"检测到视频编码: {codec} (来自文件: {os.path.basename(video_path)})")
                    return codec
            return 'unknown'
        except subprocess.TimeoutExpired:
            logger.warning("ffprobe检测视频编码超时")
            return 'unknown'
        except Exception as e:
            logger.warning(f"获取视频编码失败：{str(e)}")
            return 'unknown'

    def _get_video_bitrate(self, video_path, ffmpeg_exec):
        """使用ffprobe检测视频码率，返回码率(bps)，失败返回0"""
        try:
            import subprocess
            # 中文路径适配：优先8.3短路径转换
            if has_non_ascii(video_path):
                short_path = to_short_path(video_path)
                if short_path != video_path:
                    video_path = short_path
            ffprobe_exec = None
            ffmpeg_dir = os.path.dirname(ffmpeg_exec)
            if ffmpeg_dir:
                candidate = os.path.join(ffmpeg_dir, exe('ffprobe'))
                if os.path.exists(candidate):
                    ffprobe_exec = os.path.normpath(candidate)
            if not ffprobe_exec:
                ffprobe_exec = shutil.which('ffprobe')
                if ffprobe_exec:
                    ffprobe_exec = os.path.normpath(ffprobe_exec)
            if not ffprobe_exec or not os.path.exists(ffprobe_exec):
                logger.warning("未找到ffprobe，无法检测视频码率")
                return 0
            cmd = [
                ffprobe_exec,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_streams',
                '-show_format',
                video_path
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                **subprocess_no_window_kwargs(),
                timeout=30
            )
            if result.returncode != 0:
                return 0
            import json
            output = result.stdout.decode('utf-8', errors='ignore')
            data = json.loads(output)
            # 优先从视频流获取码率
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    bitrate = stream.get('bit_rate')
                    if bitrate and int(bitrate) > 0:
                        logger.info(f"检测到视频码率: {int(bitrate)} bps ({int(bitrate)//1000} kbps)")
                        return int(bitrate)
            # 回退到格式级别码率
            format_bitrate = data.get('format', {}).get('bit_rate')
            if format_bitrate and int(format_bitrate) > 0:
                logger.info(f"从format检测到码率: {int(format_bitrate)} bps ({int(format_bitrate)//1000} kbps)")
                return int(format_bitrate)
            return 0
        except Exception as e:
            logger.warning(f"获取视频码率失败：{str(e)}")
            return 0

    def _get_adaptive_crf(self, video_bitrate):
        """根据源视频码率自适应计算CRF值，高码率视频使用更低CRF以减少画质损失

        码率阈值与CRF映射：
        - >= 20000 kbps (4K高码率): CRF 17 (接近无损)
        - >= 10000 kbps (1080P高码率/4K): CRF 19
        - >= 6000 kbps (1080P普通): CRF 20
        - >= 3000 kbps (720P高码率): CRF 22
        - < 3000 kbps (低码率): CRF 23 (默认)
        - 未知码率: CRF 23 (默认)
        """
        kbps = video_bitrate // 1000
        if kbps >= 20000:
            crf = 17
        elif kbps >= 10000:
            crf = 19
        elif kbps >= 6000:
            crf = 20
        elif kbps >= 3000:
            crf = 22
        else:
            crf = 23
        logger.info(f"自适应CRF: 源码率={kbps}kbps, CRF={crf}")
        return crf

    def _check_gpu_codec_support(self, ffmpeg_exec, gpu_type, video_path, video_codec):
        """运行时预检：验证 GPU 硬件编解码器对当前视频编码的支持情况。

        返回三态字符串之一：
          - "full_gpu"     : GPU 支持该编码的硬件解码+编码（全 GPU 链路，最快）
          - "encode_only"  : GPU 不支持该编码的硬件解码，但 GPU 编码器可用（CPU 解码+GPU 编码）
          - "no_gpu"       : GPU 编码器也不可用（完全回退 CPU）
        """
        import subprocess as _sp

        if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
            return "no_gpu", "ffmpeg 不可用"

        # 中文路径适配：优先8.3短路径转换
        if has_non_ascii(video_path):
            short_path = to_short_path(video_path)
            if short_path != video_path:
                video_path = short_path

        hwaccel_map = {
            'nvidia': ['-hwaccel', 'cuda', '-hwaccel_device', '0',
                       '-hwaccel_output_format', 'cuda'],
            'amd':    ['-hwaccel', 'd3d11va',
                       '-hwaccel_output_format', 'd3d11'],
            'intel':  ['-hwaccel', 'qsv',
                       '-hwaccel_output_format', 'qsv'],
        }
        if gpu_type not in hwaccel_map:
            return "no_gpu", f"未知 gpu_type={gpu_type}"

        # 先测试 GPU 硬件解码是否支持该编码（AV1/HEVC 等编码在老 GPU 上可能不支持）
        if video_codec in ('av1', 'hevc', 'h265', 'unknown'):
            logger.info(f"[GPU预检] 视频编码为 {video_codec}，正在验证 {gpu_type} 硬件解码能力...")
            test_cmd = [ffmpeg_exec] + hwaccel_map[gpu_type] + [
                '-i', video_path,
                '-frames:v', '30',
                '-an',
                '-f', 'null',
                '-'
            ]
            try:
                probe = _sp.run(
                    test_cmd,
                    stdout=_sp.PIPE,
                    stderr=_sp.PIPE,
                    stdin=_sp.PIPE,
                    shell=False,
                    timeout=30,
                    **subprocess_no_window_kwargs()
                )
                if probe.returncode == 0:
                    logger.info(f"[GPU预检] {gpu_type} 支持 {video_codec} 硬件解码，将使用 GPU 全链路")
                    return "full_gpu", "支持"
                stderr_text = (probe.stderr or b'').decode('utf-8', errors='ignore').strip()
                logger.warning(
                    f"[GPU预检] {gpu_type} 不支持 {video_codec} 硬件解码（返回码={probe.returncode}），"
                    f"将使用 CPU 解码 + GPU 编码（混合模式）。ffmpeg 诊断: {stderr_text[:300]}"
                )
                return "encode_only", f"硬件解码失败: {stderr_text[:200]}"
            except _sp.TimeoutExpired:
                logger.warning(f"[GPU预检] 硬件解码测试超时，跳过 GPU 解码，使用 CPU 解码 + GPU 编码")
                return "encode_only", "预检超时"
            except Exception as ex:
                logger.warning(f"[GPU预检] 检测异常: {ex}，跳过 GPU 解码，使用 CPU 解码 + GPU 编码")
                return "encode_only", f"异常: {ex}"

        # H.264 等常见编码，大多数 GPU 硬件解码器都支持
        return "full_gpu", "默认支持"

    def merge_media(self, video_path, audio_path, output_path, kid=None, target_codecid=0, actual_codecid=0, audio_quality=None, video_process_mode='copy'):
        import os
        import shutil
        try:
            _aq_label = {0: "自动", 30251: "Hi-Res无损", 30250: "杜比全景声", 100010: "320K高音质", 30280: "192K高音质", 100009: "192K标准音质", 30232: "132K标准音质", 100008: "128K标准音质", 30216: "64K低音质"}.get(audio_quality or 0, f"音质({audio_quality})")
            logger.debug(f"开始合并音视频：视频={video_path}, 音频={audio_path}, 输出={output_path}, 音频质量设置={_aq_label}")

            # 音频质量到ffmpeg比特率参数的映射（动态支持B站API返回的所有音质ID）
            # 官方文档：30216=64K, 30232=132K, 30280=192K, 30250=杜比全景声, 30251=Hi-Res无损
            # API实际额外返回：100008=128K, 100009=192K, 100010=320K
            # 含义：(ffmpeg_bitrate参数, 显示标签)，None表示copy保持原始质量
            AUDIO_QUALITY_BITRATE = {
                30251: None,                  # Hi-Res无损 → copy（无损格式不能转码）
                30250: None,                  # 杜比全景声 → copy（特殊格式不能转码）
                100010: None,                 # 320K → copy（已是高码率）
                30280: None,                  # 192K 高音质 → copy（默认高质量）
                100009: None,                 # 192K → copy（与30280相同质量）
                30232: ('132k', '132K'),     # 132K 标准音质 → 转码到132kbps
                100008: ('128k', '128K'),     # 128K 低音质 → 转码到128kbps
                30216: ('64k', '64K'),        # 64K 低音质 → 转码到64kbps
            }

            def _get_audio_encode_args():
                """根据用户设置的音频质量返回ffmpeg音频编码参数，None表示使用copy
                audio_quality=0 表示自动模式（使用最高可用音质）→ copy保持原始质量"""
                if audio_quality is None or audio_quality == 0:
                    return None  # 未设置或自动 → copy保持原始最高音质
                bitrate_info = AUDIO_QUALITY_BITRATE.get(audio_quality)
                if bitrate_info is None:
                    return None  # 高音质/无损/自动，直接copy
                bitrate_k, label = bitrate_info
                logger.info(f"音频转码：用户设置了{label}音频质量，目标码率={bitrate_k}")
                return ['-c:a', 'aac', '-b:a', bitrate_k, '-ar', '44100', '-ac', '2']

            import time
            # 使用预计算的ASCII安全临时目录，避免系统临时目录含中文用户名导致ffmpeg无法处理
            merge_temp_dir = self.safe_temp_dir
            # 检查输出路径是否含非ASCII字符（merge_temp_dir已通过get_safe_temp_dir保证ASCII安全）
            # 注意：局部变量必须改名为 output_has_non_ascii，避免遮蔽导入的 has_non_ascii 函数
            output_has_non_ascii = has_non_ascii(output_path)
            merge_temp_output = None

            # 生成安全的临时合并文件名（纯ASCII + 时间戳避免冲突，固定.mp4扩展名）
            _safe_name = f"bili_merge_{int(time.time() * 1000) % 100000000}.mp4"
            if output_has_non_ascii:
                merge_temp_output = os.path.join(merge_temp_dir, _safe_name)
                logger.info(f"输出路径含非ASCII字符，使用安全临时路径合并：{merge_temp_output}")
            
            decrypted_video_path = video_path
            decrypted_audio_path = audio_path

            def _cleanup_decrypted_files():
                """统一清理解密产生的临时文件，避免early return路径资源泄漏"""
                if decrypted_video_path != video_path and os.path.exists(decrypted_video_path):
                    try:
                        os.remove(decrypted_video_path)
                        logger.debug(f"清理临时视频文件：{decrypted_video_path}")
                    except Exception:
                        pass
                if decrypted_audio_path != audio_path and os.path.exists(decrypted_audio_path):
                    try:
                        os.remove(decrypted_audio_path)
                        logger.debug(f"清理临时音频文件：{decrypted_audio_path}")
                    except Exception:
                        pass
                if merge_temp_output and merge_temp_output != output_path and os.path.exists(merge_temp_output):
                    try:
                        os.remove(merge_temp_output)
                    except Exception:
                        pass

            is_encrypted, encryption_type = self._check_encryption(video_path)
            if is_encrypted:
                logger.info(f"检测到视频被{encryption_type}加密，尝试解密")
                decrypted_video_path = video_path + '.decrypted'
                try:
                    actual_decrypted = asyncio.run(self._decrypt_with_bento4(video_path, decrypted_video_path, kid))
                    # _decrypt_with_bento4 可能修改输出路径（如 .decrypted -> .mp4），使用返回值
                    if actual_decrypted and actual_decrypted != decrypted_video_path:
                        decrypted_video_path = actual_decrypted
                except Exception as decrypt_err:
                    logger.error(f"视频解密失败: {decrypt_err}")
                    # 清理可能产生的无效文件
                    if os.path.exists(decrypted_video_path):
                        try:
                            os.remove(decrypted_video_path)
                        except Exception:
                            pass
                    return False, f"视频DRM解密失败（{encryption_type}）: {decrypt_err}"
                if not os.path.exists(decrypted_video_path):
                    return False, "视频解密后文件不存在"
                # 中文路径适配：对解密后的视频路径应用8.3短路径转换
                # 避免后续ffprobe验证和ffmpeg合并时处理中文路径崩溃
                # 注意：短路径指向同一文件，_cleanup_decrypted_files 仍能正确清理
                if has_non_ascii(decrypted_video_path):
                    _short_v = to_short_path(decrypted_video_path)
                    if _short_v != decrypted_video_path:
                        logger.info(f"[合并] 解密后视频使用8.3短路径：{_short_v}")
                        decrypted_video_path = _short_v
                decrypted_size = os.path.getsize(decrypted_video_path)
                if decrypted_size < 1024:
                    _cleanup_decrypted_files()
                    return False, f"视频解密后文件过小（{decrypted_size}字节），可能是密钥错误或文件损坏"
                # 验证解密后的文件是否可以被ffmpeg读取
                # 优先使用程序自带的ffmpeg
                ffmpeg_exec = self.ffmpeg_local
                if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                    ffmpeg_exec = shutil.which('ffmpeg')
                if ffmpeg_exec and os.path.exists(ffmpeg_exec):
                    ffmpeg_exec = os.path.normpath(ffmpeg_exec)
                    ffprobe_exec = os.path.join(os.path.dirname(ffmpeg_exec), exe('ffprobe'))
                    if not os.path.exists(ffprobe_exec):
                        ffprobe_exec = shutil.which('ffprobe')
                    if ffprobe_exec:
                        ffprobe_exec = os.path.normpath(ffprobe_exec)
                    if ffprobe_exec and os.path.exists(ffprobe_exec):
                        import subprocess as sp
                        try:
                            probe_result = sp.run(
                                [ffprobe_exec, '-v', 'quiet', '-print_format', 'json',
                                 '-show_streams', decrypted_video_path],
                                stdout=sp.PIPE, stderr=sp.PIPE,
                                shell=False, **subprocess_no_window_kwargs(), timeout=15
                            )
                            if probe_result.returncode != 0:
                                err_msg = probe_result.stderr.decode('utf-8', errors='ignore')[:200]
                                logger.error(f"解密后文件仍无法被ffprobe读取: {err_msg}")
                                _cleanup_decrypted_files()
                                return False, f"视频解密后文件仍然损坏（{err_msg[:80]}），请检查DRM密钥获取是否正常"
                        except Exception as ve:
                            logger.warning(f"验证解密文件时异常: {ve}")
                logger.info(f"视频解密成功并验证通过：{decrypted_video_path}")
            else:
                logger.info("视频未加密，直接使用原始文件")

            if audio_path:
                is_audio_encrypted, audio_encryption_type = self._check_encryption(audio_path)
                if is_audio_encrypted:
                    logger.info(f"检测到音频被{audio_encryption_type}加密，尝试解密")
                    decrypted_audio_path = audio_path + '.decrypted'
                    try:
                        actual_decrypted = asyncio.run(self._decrypt_with_bento4(audio_path, decrypted_audio_path, kid))
                        # _decrypt_with_bento4 可能修改输出路径（如 .decrypted -> .mp4），使用返回值
                        if actual_decrypted and actual_decrypted != decrypted_audio_path:
                            decrypted_audio_path = actual_decrypted
                    except Exception as decrypt_err:
                        logger.error(f"音频解密失败: {decrypt_err}")
                        if os.path.exists(decrypted_audio_path):
                            try:
                                os.remove(decrypted_audio_path)
                            except Exception:
                                pass
                        _cleanup_decrypted_files()
                        return False, f"音频DRM解密失败（{audio_encryption_type}）: {decrypt_err}"
                    if not os.path.exists(decrypted_audio_path):
                        _cleanup_decrypted_files()
                        return False, "音频解密后文件不存在"
                    decrypted_size = os.path.getsize(decrypted_audio_path)
                    if decrypted_size < 1024:
                        _cleanup_decrypted_files()
                        return False, f"音频解密后文件过小：{decrypted_size}字节"
            
            # 优先使用程序自带的ffmpeg，避免系统PATH中的不兼容版本导致合并失败
            ffmpeg_exec = self.ffmpeg_local
            logger.debug(f"本地ffmpeg路径：{ffmpeg_exec}")
            
            if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                ffmpeg_exec = shutil.which('ffmpeg')
                logger.debug(f"系统环境变量中的ffmpeg路径：{ffmpeg_exec}")
                if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                    logger.error(f"未找到ffmpeg！本地路径和系统PATH均不存在")
                    _cleanup_decrypted_files()
                    return False, "未找到ffmpeg！请安装并添加到系统环境变量，或放在./ffmpeg/bin目录下"

            logger.debug(f"使用的ffmpeg路径：{ffmpeg_exec}")
            
            if output_has_non_ascii:
                # 已在上面设置 merge_temp_output 为安全的ASCII文件名
                pass
            else:
                merge_temp_output = output_path
            
            video_codec = self._get_video_codec(decrypted_video_path, ffmpeg_exec)
            logger.info(f"视频编码：{video_codec}")

            # 检测源视频码率，用于自适应CRF计算
            video_bitrate = self._get_video_bitrate(decrypted_video_path, ffmpeg_exec)
            adaptive_crf = self._get_adaptive_crf(video_bitrate)

            # 检测输出格式
            output_ext = os.path.splitext(output_path)[1].lower()
            is_amv = output_ext == '.amv'

            # 需要转换编码的判断逻辑：
            # 1. DRM解密后的文件可能需要重新封装/转码
            # 2. 输出格式不支持该编码（如AMV/AVI不支持HEVC）
            # 3. 编码未知无法安全copy
            # 注意：MP4容器原生支持AV1/HEVC/H.264/AAC等常见编码，无需为了"兼容性"强制转码
            # video_output_format 设置项生效：根据输出容器格式判断是否需要转码
            need_drm_repack = encryption_type is not None  # 经过了DRM解密
            need_format_convert = is_amv
            # AVI 不支持 HEVC/AV1，需要转码为 H.264
            if output_ext == '.avi' and video_codec in ('hevc', 'av1', 'h265', 'vp9'):
                need_format_convert = True
                logger.info(f"输出格式AVI不支持{video_codec}编码，将转码为H.264")
            # FLV 不支持 HEVC/AV1/VP9
            if output_ext == '.flv' and video_codec in ('hevc', 'av1', 'h265', 'vp9'):
                need_format_convert = True
                logger.info(f"输出格式FLV不支持{video_codec}编码，将转码为H.264")
            # WMV/ASF 需要WMV编码
            if output_ext in ('.wmv', '.asf') and video_codec not in ('wmv1', 'wmv2', 'wmv3', 'msmpeg4', 'mpeg4'):
                need_format_convert = True
                logger.info(f"输出格式{output_ext}需要WMV兼容编码，将转码为H.264")
            # VOB/DVD 需要MPEG2
            if output_ext in ('.vob', '.dat') and video_codec not in ('mpeg1video', 'mpeg2video'):
                need_format_convert = True
                logger.info(f"输出格式{output_ext}需要MPEG2编码，将转码")
            # SVCD/VCD 需要MPEG1/2
            if output_ext == '.svcd' and video_codec not in ('mpeg1video', 'mpeg2video'):
                need_format_convert = True
            # MPG/MPEG 可能不支持 HEVC/AV1
            if output_ext in ('.mpg', '.mpeg') and video_codec in ('hevc', 'av1', 'h265', 'vp9'):
                need_format_convert = True
            # M2TS (Blu-ray) 支持 H.264/HEVC/AVC，但可能不支持 AV1/VP9
            if output_ext == '.m2ts' and video_codec in ('av1', 'vp9'):
                need_format_convert = True
            need_conversion = (video_codec == 'unknown') or need_format_convert

            if need_drm_repack:
                logger.info(f"检测到DRM已解密({encryption_type})，可能需要转码确保格式正确")
            if video_codec == 'unknown':
                logger.warning("无法检测视频编码，将转换为H.264以确保兼容性")

            gpu_acceleration = self.config.get_app_setting("gpu_acceleration", False) if self.config else False
            gpu_type = None
            logger.info(f"[GPU诊断] gpu_acceleration配置值={gpu_acceleration}, self.config存在={self.config is not None}")
            if gpu_acceleration:
                try:
                    from platform_utils import detect_gpu
                    _, gpu_type, _ = detect_gpu()
                    logger.info(f"[GPU诊断] detect_gpu()返回: gpu_type={gpu_type}")
                except Exception as ex:
                    logger.error(f"[GPU诊断] detect_gpu()异常: {ex}")
                    gpu_type = None

            # 构建GPU硬件转码参数（基于目标码率ABR模式，与CPU路径输出体积一致）
            def _gpu_encode_args(video_bitrate=0):
                """返回GPU加速的完整转码参数

                策略变更（v2.0.6）：不再使用CQ恒定质量模式
                改为基于原始码率的目标码率ABR模式，确保GPU/CPU输出体积一致
                - 目标码率 = 原始码率 × 1.25（最低保底800kbps）
                - GPU硬件编码器用VBR + 目标码率控制，避免CQ模式下体积膨胀
                """
                src_kbps = (video_bitrate // 1000) if video_bitrate else 0
                target_kbps = max(int(src_kbps * 1.25), 800) if src_kbps > 0 else 1000
                maxrate_kbps = int(target_kbps * 1.1)
                logger.info(f"[GPU编码] ABR目标码率模式，源={src_kbps}kbps, 目标={target_kbps}kbps, gpu_type={gpu_type}")

                if gpu_type == 'nvidia':
                    # NVIDIA NVENC: VBR + 目标码率（不用CQ，避免体积膨胀）
                    return {
                        'hwaccel': ['-hwaccel', 'cuda',
                                    '-hwaccel_device', '0',
                                    '-hwaccel_output_format', 'cuda'],
                        'encoder': [
                            '-c:v', 'h264_nvenc',
                            '-rc', 'vbr',
                            '-b:v', f'{target_kbps}k',
                            '-maxrate', f'{maxrate_kbps}k',
                            '-qmin', '22', '-qmax', '40',
                            '-preset', 'p4',
                            '-spatial_aq', '1',
                        ]
                    }
                elif gpu_type == 'amd':
                    # AMD AMF: 基于目标码率的VBR
                    return {
                        'hwaccel': ['-hwaccel', 'd3d11va',
                                    '-hwaccel_output_format', 'd3d11'],
                        'encoder': [
                            '-c:v', 'h264_amf',
                            '-rc', 'vbr_latency',
                            '-b:v', f'{target_kbps}k',
                            '-maxrate', f'{maxrate_kbps}k',
                            '-qmin', '22', '-qmax', '40',
                            '-quality', 'quality'
                        ]
                    }
                elif gpu_type == 'intel':
                    # Intel QSV: 基于目标码率的VBR
                    return {
                        'hwaccel': ['-hwaccel', 'qsv',
                                    '-hwaccel_output_format', 'qsv',
                                    '-async', '4'],
                        'encoder': [
                            '-c:v', 'h264_qsv',
                            '-rc', 'vbr',
                            '-b:v', f'{target_kbps}k',
                            '-maxrate', f'{maxrate_kbps}k',
                            '-global_quality', '25',
                            '-preset', 'medium'
                        ]
                    }
                return None

            # 判断 GPU 加速模式：
            #   "off"        : 不使用 GPU
            #   "full_gpu"   : GPU 硬件解码 + GPU 硬件编码（全 GPU，最快）
            #   "encode_only": CPU 软件解码 + GPU 硬件编码（混合模式，编码在 GPU 上）
            gpu_mode = "off"
            if gpu_acceleration and gpu_type and _gpu_encode_args(0) is not None:
                gpu_result, _gpu_diag = self._check_gpu_codec_support(
                    ffmpeg_exec, gpu_type, decrypted_video_path, video_codec
                )
                if gpu_result in ("full_gpu", "encode_only"):
                    gpu_mode = gpu_result
            logger.info(f"[GPU诊断] 最终决策: gpu_acceleration={gpu_acceleration}, gpu_type={gpu_type}, gpu_mode={gpu_mode}, _gpu_encode_args()={_gpu_encode_args()}")

            # 中文路径适配：对音频路径应用8.3短路径转换（视频路径已在解密后转换）
            if decrypted_audio_path and has_non_ascii(decrypted_audio_path):
                _short_a = to_short_path(decrypted_audio_path)
                if _short_a != decrypted_audio_path:
                    logger.info(f"[合并] 音频输入使用8.3短路径：{_short_a}")
                    decrypted_audio_path = _short_a

            # 根据是否有音频文件构建不同的命令
            # 预计算音频编码参数（根据用户设置的音频质量决定是否转码）
            _audio_args = _get_audio_encode_args() if decrypted_audio_path else None
            if _audio_args is None:
                _audio_args = ['-c:a', 'copy']  # 默认copy

            # 预计算视频编码参数
            # 策略：优先从B站API直接下载目标编码（无需转码）
            # 仅当API不提供该编码时，才用ffmpeg转码
            # 编码ID: 7=AVC/H.264, 12=HEVC/H.265, 13=AV1
            _CODEC_ENCODER_MAP = {
                7: ['-c:v', 'libx264', '-preset', 'fast', '-crf', '20'],
                12: ['-c:v', 'libx265', '-preset', 'medium', '-crf', '23'],
                13: ['-c:v', 'libaom-av1', '-crf', '35', '-cpu-used', '4'],
                14: ['-c:v', 'libvpx-vp9', '-crf', '30', '-b:v', '0', '-cpu-used', '4'],
            }
            _CODEC_NAME_MAP = {7: 'H.264/AVC', 12: 'H.265/HEVC', 13: 'AV1', 14: 'VP9'}
            need_video_transcode = (target_codecid and target_codecid > 0 and
                                    actual_codecid and actual_codecid > 0 and
                                    target_codecid != actual_codecid)
            # 根据视频处理模式决定编码策略
            # copy: 直接复制B站数据流（速度快，可变帧率）
            # re-encode: 用ffmpeg重编码（基于原始码率自适应，恒定帧率利于剪辑）
            _force_copy = (video_process_mode == 'copy')
            if _force_copy:
                # 复制数据流模式：不转码，但保留GPU加速解码（hwaccel加速读取）
                need_video_transcode = False
                need_conversion = False
                need_format_convert = False
                _audio_args = ['-c:a', 'copy']
                logger.info("复制数据流模式：音视频直接copy封装，GPU加速解码（如可用）")

            # 核心思路：B站流已是专业压缩过的，盲目低CRF只会膨胀体积
            # 正确做法：以原始码率为基准，按比例适度提升(×1.25)
            # 效果：体积仅增~25%，但获得恒定帧率和更好的编码一致性
            src_kbps = (video_bitrate // 1000) if video_bitrate else 0
            _reencode_target_kbps = max(int(src_kbps * 1.25), 800) if src_kbps > 0 else 1000
            _reencode_maxrate_kbps = int(_reencode_target_kbps * 1.1)
            _reencode_bufsize_kbps = _reencode_target_kbps * 2

            if need_video_transcode and not _force_copy:
                # API未提供目标编码，需要ffmpeg转码（使用目标码率ABR模式）
                _video_args = _CODEC_ENCODER_MAP.get(target_codecid, ['-c:v', 'libx264', '-preset', 'fast'])
                # 在编码器参数后追加码率控制参数
                _br_args = ['-b:v', f'{_reencode_target_kbps}k',
                            '-maxrate', f'{_reencode_maxrate_kbps}k',
                            '-bufsize', f'{_reencode_bufsize_kbps}k']
                # 插入到 -crf 参数之前（如果有）或追加到末尾
                _crf_idx = next((i for i, x in enumerate(_video_args) if x == '-crf'), -1)
                if _crf_idx >= 0:
                    _video_args = _video_args[:_crf_idx] + _br_args + _video_args[_crf_idx+2:]
                else:
                    _video_args = _video_args + _br_args
                src_codec = _CODEC_NAME_MAP.get(actual_codecid, str(actual_codecid))
                dst_codec = _CODEC_NAME_MAP.get(target_codecid, str(target_codecid))
                logger.info(f"视频转码：B站API未提供{dst_codec}流，从{src_codec}转码→{dst_codec}，目标码率={_reencode_target_kbps}kbps(源={src_kbps}kbps)")
            elif actual_codecid and actual_codecid > 0 and not _force_copy:
                # API提供了编码流，用户选择重编码模式 → 基于原始码率自适应重编码
                codec_label = _CODEC_NAME_MAP.get(actual_codecid, f'codecid={actual_codecid}')
                encoder_base = _CODEC_ENCODER_MAP.get(actual_codecid,
                    ['-c:v', 'libx264', '-preset', 'fast'])
                # 追加自适应码率控制（替换或追加CRF）
                _br_args = ['-b:v', f'{_reencode_target_kbps}k',
                            '-maxrate', f'{_reencode_maxrate_kbps}k',
                            '-bufsize', f'{_reencode_bufsize_kbps}k']
                _crf_idx = next((i for i, x in enumerate(encoder_base) if x == '-crf'), -1)
                if _crf_idx >= 0:
                    _video_args = encoder_base[:_crf_idx] + _br_args + encoder_base[_crf_idx+2:]
                else:
                    _video_args = encoder_base + _br_args
                logger.info(f"视频重编码：B站API提供{codec_label}流，ffmpeg重编码提升画质，"
                           f"目标码率={_reencode_target_kbps}kbps(源={src_kbps}kbps, +{_reencode_target_kbps - src_kbps if src_kbps else '?'}kbps)")
            else:
                # copy模式 或 无编码信息 → 直接复制原始流
                _video_args = ['-c:v', 'copy']
                if _force_copy:
                    logger.info(f"视频复制模式（用户选择）：保持B站原始数据流({src_kbps}kbps)，速度最快")
                else:
                    logger.info(f"视频copy模式：保持原始编码({video_codec})")

            if decrypted_audio_path:
                if not need_conversion and not is_amv:
                    # 智能合并路径：根据编码设置动态决定视频编码参数
                    _is_copy = (_video_args == ['-c:v', 'copy'])
                    _v_mode = "copy(原始编码)" if _is_copy else ("转码" if need_video_transcode else "重编码")

                    # copy模式 + GPU加速：使用hwaccel加速解码读取，但输出仍为copy
                    _hwaccel_args = []
                    if _is_copy and gpu_mode in ("full_gpu", "encode_only") and gpu_type:
                        gpu_params = _gpu_encode_args(video_bitrate)
                        if gpu_params and 'hwaccel' in gpu_params:
                            _hwaccel_args = gpu_params['hwaccel']
                            _v_mode = f"copy+GPU加速解码({gpu_type})"
                            logger.info(f"复制数据流+GPU加速解码：使用{gpu_type} hwaccel加速读取，输出直接copy")

                    logger.info(f"智能合并：视频{_v_mode}，音频{'转码' if _audio_args != ['-c:a', 'copy'] else 'copy'}")
                    cmd = [
                        ffmpeg_exec,
                    ] + _hwaccel_args + [
                        '-i', decrypted_video_path,
                        '-i', decrypted_audio_path,
                    ] + _video_args + _audio_args + [
                    ]
                    if output_ext in ('.mp4', '.mov', '.m4v', '.3gp'):
                        cmd.extend(['-movflags', '+faststart'])
                    cmd.extend([
                        '-shortest',
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ])
                    logger.info(f"[合并] 智能合并命令(视频{_v_mode})")
                elif is_amv:
                    # AMV格式特殊处理（固定编码）
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                        '-i', decrypted_audio_path,
                        '-c:v', 'amv',
                        '-c:a', 'adpcm_ima_amv',
                        '-ar', '22050',
                        '-ac', '1',
                        '-block_size', '735',
                        '-strict', '-1',
                        '-shortest',
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]
                elif gpu_mode in ("full_gpu", "encode_only") and not need_video_transcode:
                    # GPU加速：仅在不需要视频转码时使用GPU（用户选择的编码与实际一致或未指定）
                    if gpu_mode == "full_gpu":
                        logger.info(f"GPU加速已启用({gpu_type})，全GPU硬件编解码")
                        gpu_params = _gpu_encode_args(video_bitrate)
                        cmd = [
                            ffmpeg_exec,
                        ] + gpu_params['hwaccel'] + [
                            '-i', decrypted_video_path,
                            '-i', decrypted_audio_path,
                        ] + gpu_params['encoder'] + _audio_args + [
                            '-shortest',
                            '-loglevel', 'error',
                            '-y',
                            merge_temp_output
                        ]
                    else:
                        logger.info(f"GPU加速已启用({gpu_type})，混合模式(CPU解码+GPU编码)")
                        gpu_params = _gpu_encode_args(video_bitrate)
                        cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                            '-i', decrypted_audio_path,
                        ] + gpu_params['encoder'] + _audio_args + [
                            '-shortest',
                            '-loglevel', 'error',
                            '-y',
                            merge_temp_output
                        ]
                elif need_conversion or need_video_transcode:
                    # CPU转码：格式不兼容 或 用户指定了不同编码 → 使用目标编码器转码
                    if need_video_transcode:
                        logger.info(f"用户指定编码转换(目标={_CODEC_NAME_MAP.get(target_codecid,str(target_codecid))})，使用CPU转码")
                    else:
                        logger.info(f"格式不兼容({video_codec})，自动转换为H.264(自适应CRF={adaptive_crf})")
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                        '-i', decrypted_audio_path,
                    ] + _video_args + _audio_args + [
                        '-shortest',
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]
                else:
                    # CPU模式+普通copy
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                        '-i', decrypted_audio_path,
                    ] + _video_args + _audio_args + [
                        '-shortest',
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]
            else:
                if is_amv:
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                        '-c:v', 'amv',
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]
                elif not need_conversion and not is_amv and not need_video_transcode:
                    # 智能合并（无音频轨）：用预计算的编码参数
                    _is_copy = (_video_args == ['-c:v', 'copy'])

                    # copy模式 + GPU加速（无音频轨）
                    _hwaccel_args_noaudio = []
                    if _is_copy and gpu_mode in ("full_gpu", "encode_only") and gpu_type:
                        gpu_params = _gpu_encode_args(video_bitrate)
                        if gpu_params and 'hwaccel' in gpu_params:
                            _hwaccel_args_noaudio = gpu_params['hwaccel']
                            logger.info(f"复制数据流+GPU加速解码(无音频轨)：使用{gpu_type} hwaccel")

                    logger.info(f"智能合并（无音频轨）：视频{'重编码' if not _is_copy else 'copy'}")
                    cmd = [
                        ffmpeg_exec,
                    ] + _hwaccel_args_noaudio + [
                        '-i', decrypted_video_path,
                    ] + _video_args + [
                        '-movflags', '+faststart',
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]
                elif gpu_mode in ("full_gpu", "encode_only") and not need_video_transcode and not need_conversion:
                    # GPU加速：仅在不需转码时使用
                    if gpu_mode == "full_gpu":
                        logger.info(f"GPU加速已启用({gpu_type})，全GPU编解码(无音频轨)")
                        gpu_params = _gpu_encode_args(video_bitrate)
                        cmd = [
                            ffmpeg_exec,
                        ] + gpu_params['hwaccel'] + [
                            '-i', decrypted_video_path,
                        ] + gpu_params['encoder'] + [
                            '-loglevel', 'error',
                            '-y',
                            merge_temp_output
                        ]
                    else:
                        logger.info(f"GPU加速已启用({gpu_type})，混合模式(无音频轨)")
                        gpu_params = _gpu_encode_args(video_bitrate)
                        cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                        ] + gpu_params['encoder'] + [
                            '-loglevel', 'error',
                            '-y',
                            merge_temp_output
                        ]
                elif need_conversion or need_video_transcode:
                    # CPU转码：格式不兼容 或 用户指定不同编码
                    if need_video_transcode:
                        logger.info(f"用户指定编码转换(无音频轨, 目标={_CODEC_NAME_MAP.get(target_codecid,str(target_codecid))})")
                    else:
                        logger.info(f"格式不兼容({video_codec})，自动转码")
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                    ] + _video_args + [
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]
                else:
                    # 最终回退：copy模式
                    cmd = [
                        ffmpeg_exec,
                        '-i', decrypted_video_path,
                    ] + _video_args + [
                        '-loglevel', 'error',
                        '-y',
                        merge_temp_output
                    ]

            logger.debug(f"执行ffmpeg命令：{' '.join(cmd)}")
            
            try:
                # 使用低优先级运行ffmpeg，降低CPU噪音但不影响合并速度
                result = subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    shell=False,
                    **subprocess_low_priority_kwargs()
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
                        **subprocess_low_priority_kwargs()
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
                    _cleanup_decrypted_files()
                    return False, f"执行ffmpeg失败：{str(shell_e)}"
            
            if merge_temp_output and merge_temp_output != output_path and os.path.exists(merge_temp_output):
                try:
                    output_dir = os.path.dirname(output_path)
                    if output_dir:
                        os.makedirs(output_dir, exist_ok=True)
                    shutil.copy2(merge_temp_output, output_path)
                    logger.info(f"复制合并结果到目标路径：{output_path}")
                    try:
                        os.remove(merge_temp_output)
                    except Exception:
                        pass
                except Exception as copy_e:
                    logger.error(f"复制合并结果失败：{str(copy_e)}")
                    if os.path.exists(merge_temp_output):
                        try:
                            os.rename(merge_temp_output, output_path)
                        except Exception:
                            pass
            
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
            # GPU 路径失败时自动回退到 CPU 编码
            if gpu_mode != "off":
                try:
                    _gpu_err = (e.stderr or b'').decode('utf-8', errors='ignore')
                except Exception:
                    _gpu_err = str(e.stderr) if e.stderr else ''
                logger.warning(
                    f"GPU加速编码失败（{gpu_type}，模式={gpu_mode}），回退到CPU编码：返回码={e.returncode}\n"
                    f"  ffmpeg stderr（前1000字符）: {_gpu_err[:1000]}"
                )
                try:
                    # GPU失败回退到CPU编码，使用用户指定的目标编码器
                    if decrypted_audio_path:
                        fallback_cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                            '-i', decrypted_audio_path,
                        ] + _video_args + _audio_args + [
                            '-shortest',
                            '-loglevel', 'error',
                            '-y',
                            merge_temp_output
                        ]
                    else:
                        fallback_cmd = [
                            ffmpeg_exec,
                            '-i', decrypted_video_path,
                        ] + _video_args + [
                            '-loglevel', 'error',
                            '-y',
                            merge_temp_output
                        ]
                    logger.info(f"回退到CPU编码执行ffmpeg")
                    result = subprocess.run(
                        fallback_cmd,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        shell=False,
                        **subprocess_low_priority_kwargs()
                    )
                    logger.info("CPU编码回退成功")
                    if merge_temp_output and merge_temp_output != output_path and os.path.exists(merge_temp_output):
                        try:
                            output_dir = os.path.dirname(output_path)
                            if output_dir:
                                os.makedirs(output_dir, exist_ok=True)
                            shutil.copy2(merge_temp_output, output_path)
                            try:
                                os.remove(merge_temp_output)
                            except Exception:
                                pass
                        except Exception as copy_e:
                            if os.path.exists(merge_temp_output):
                                try:
                                    os.rename(merge_temp_output, output_path)
                                except Exception:
                                    pass
                    if decrypted_video_path != video_path and os.path.exists(decrypted_video_path):
                        try:
                            os.remove(decrypted_video_path)
                        except Exception:
                            pass
                    if decrypted_audio_path != audio_path and os.path.exists(decrypted_audio_path):
                        try:
                            os.remove(decrypted_audio_path)
                        except Exception:
                            pass
                    return True, "合并成功（GPU加速失败，已回退CPU编码）"
                except Exception as fallback_e:
                    logger.error(f"CPU编码回退也失败：{str(fallback_e)}")
                    _cleanup_decrypted_files()
                    return False, f"GPU和CPU编码均失败：{str(fallback_e)}"
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
        """将秒数转换为 MM:SS 或 HH:MM:SS"""
        try:
            seconds = int(duration)
            if seconds < 0:
                return "00:00"
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            secs = seconds % 60
            if hours > 0:
                return f"{hours}:{minutes:02d}:{secs:02d}"
            return f"{minutes:02d}:{secs:02d}"
        except Exception:
            return "00:00"

    def _transcode_to_codec(self, inp, outp, tc, ffmpeg_exec=None):
        """将视频转码到目标编码格式"""
        import subprocess
        if not ffmpeg_exec:
            ffmpeg_exec = self._get_ffmpeg_executable()
        CM = {7:'libx264', 12:'libx265', 13:'libaom-av1', 14:'libvpx-vp9'}
        e = CM.get(tc, 'libx264')
        c = [ffmpeg_exec, '-i', inp, '-c:v', e]
        if tc == 12:
            c += ['-preset', 'medium', '-crf', '23']
        elif tc == 13:
            c += ['-crf', '35', '-cpu-used', '4']
        else:
            c += ['-preset', 'fast', '-crf', '20']
        c += ['-c:a', 'copy', '-y', outp]
        try:
            r = subprocess.run(c, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              stdin=subprocess.PIPE, shell=False, **subprocess_low_priority_kwargs())
            if r.returncode != 0:
                err_msg = (r.stderr or b'').decode('utf-8', errors='ignore')[:200]
                return False, f"转码失败（返回码{r.returncode}）: {err_msg}"
            return True, ""
        except Exception as ex:
            return False, str(ex)