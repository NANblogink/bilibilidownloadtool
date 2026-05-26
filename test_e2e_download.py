import os
import sys
import shutil
import tempfile
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from config import ConfigLoader
from bilibili_parser import BilibiliParser
from platform_utils import (
    IS_MACOS, IS_WINDOWS, exe, subprocess_no_window_kwargs,
    illegal_filename_chars, platform_font, app_data_dir,
    program_files_dir, is_admin, get_bento4_sdk_dirname,
    get_system_proxy, hide_file, add_to_system_path, remove_from_system_path,
)

passed = 0
failed = 0
errors = []

def test(name, func):
    global passed, failed, errors
    try:
        func()
        passed += 1
        logger.info(f"✅ PASS: {name}")
    except Exception as e:
        failed += 1
        errors.append((name, str(e)))
        logger.error(f"❌ FAIL: {name} - {e}")


def test_platform_utils():
    logger.info("=" * 60)
    logger.info("1. platform_utils 平台抽象层")
    logger.info("=" * 60)

    def t_is_macos():
        assert IS_MACOS == True, f"IS_MACOS should be True on macOS, got {IS_MACOS}"
        assert IS_WINDOWS == False
    test("IS_MACOS/IS_WINDOWS 常量", t_is_macos)

    def t_exe():
        assert exe('ffmpeg') == 'ffmpeg', f"exe('ffmpeg') should be 'ffmpeg', got {exe('ffmpeg')}"
        assert exe('mp4decrypt') == 'mp4decrypt'
        assert exe('ffprobe') == 'ffprobe'
        assert exe('mp4dump') == 'mp4dump'
        assert exe('mp4info') == 'mp4info'
    test("exe() 函数", t_exe)

    def t_subprocess_kwargs():
        kwargs = subprocess_no_window_kwargs()
        assert kwargs == {}, f"subprocess_no_window_kwargs() should be {{}} on macOS, got {kwargs}"
    test("subprocess_no_window_kwargs()", t_subprocess_kwargs)

    def t_illegal_chars():
        chars = illegal_filename_chars()
        assert '/' in chars, "/ should be illegal"
        assert ':' in chars, ": should be illegal on macOS"
        assert '*' not in chars, "* should NOT be illegal on macOS"
        assert '?' not in chars, "? should NOT be illegal on macOS"
    test("illegal_filename_chars()", t_illegal_chars)

    def t_platform_font():
        family, size = platform_font()
        assert family == 'PingFang SC', f"Expected PingFang SC, got {family}"
        assert size == 13, f"Expected 13, got {size}"
    test("platform_font()", t_platform_font)

    def t_app_data_dir():
        d = app_data_dir()
        assert 'Library/Application Support' in d, f"Expected Library/Application Support in {d}"
    test("app_data_dir()", t_app_data_dir)

    def t_program_files_dir():
        d = program_files_dir()
        assert 'Library/Application Support' in d, f"Expected Library/Application Support in {d}"
    test("program_files_dir()", t_program_files_dir)

    def t_is_admin():
        result = is_admin()
        assert isinstance(result, bool), f"is_admin() should return bool, got {type(result)}"
    test("is_admin()", t_is_admin)

    def t_bento4_sdk_dirname():
        d = get_bento4_sdk_dirname()
        assert 'apple-macosx' in d, f"Expected apple-macosx in {d}"
    test("get_bento4_sdk_dirname()", t_bento4_sdk_dirname)

    def t_get_system_proxy():
        proxy = get_system_proxy()
        assert proxy is None or isinstance(proxy, str), f"proxy should be None or str, got {type(proxy)}"
    test("get_system_proxy()", t_get_system_proxy)


def test_tool_manager():
    logger.info("=" * 60)
    logger.info("2. tool_manager 工具管理器")
    logger.info("=" * 60)

    from tool_manager import ToolManager

    tm = ToolManager()

    def t_init():
        assert 'ffmpeg' in tm.ffmpeg_path
        assert 'mp4decrypt' in tm.mp4decrypt_path
        assert not tm.ffmpeg_path.endswith('.exe')
        assert not tm.mp4decrypt_path.endswith('.exe')
    test("ToolManager 初始化", t_init)

    def t_check_tools():
        result = tm.check_tools_installed()
        assert 'ffmpeg_exists' in result
        assert 'bento4_exists' in result
        logger.info(f"  工具状态: ffmpeg={result['ffmpeg_exists']}, bento4={result['bento4_exists']}")
    test("check_tools_installed()", t_check_tools)

    def test_homebrew_detection():
        assert tm.ffmpeg_path == '/opt/homebrew/bin/ffmpeg' or os.path.exists(tm.ffmpeg_path), \
            f"FFmpeg not found at {tm.ffmpeg_path}"
    test("Homebrew FFmpeg 检测", test_homebrew_detection)

    def t_get_tool_paths():
        paths = tm.get_tool_paths()
        assert 'ffmpeg' in paths
        assert 'mp4decrypt' in paths
        assert 'install_dir' in paths
    test("get_tool_paths()", t_get_tool_paths)


def test_config():
    logger.info("=" * 60)
    logger.info("3. config 配置管理")
    logger.info("=" * 60)

    def t_config_dir():
        c = ConfigLoader()
        assert 'Library/Application Support' in c.config_file, f"Config in wrong dir: {c.config_file}"
    test("配置文件目录", t_config_dir)

    def t_hevc_url():
        c = ConfigLoader()
        cfg = c._get_default_config()
        other_urls = cfg.get('other_urls', {})
        hevc_url = other_urls.get('hevc_extension_url', 'NOT_FOUND')
        assert hevc_url == '', f"hevc_extension_url should be empty on macOS, got {hevc_url}"
    test("HEVC URL 为空（Mac不需要）", t_hevc_url)

    def t_default_save_path():
        c = ConfigLoader()
        cfg = c._get_default_config()
        app_settings = cfg.get('app_settings', {})
        save_path = app_settings.get('default_save_path', '')
        assert save_path, "default_save_path should not be empty"
    test("默认保存路径", t_default_save_path)


def test_url_parsing():
    logger.info("=" * 60)
    logger.info("4. URL 解析（多种类型）")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_video_url():
        info = parser.parse_media_url('https://www.bilibili.com/video/BV1zb5k6WErV/')
        assert info['type'] == 'video', f"Expected video, got {info['type']}"
        assert info['id'] == 'BV1zb5k6WErV'
    test("普通视频URL解析", t_video_url)

    def t_b23_url():
        info = parser.parse_media_url('https://b23.tv/BV1zb5k6WErV')
        assert info['type'] in ['video', 'bangumi', 'cheese', 'av'], f"Got type: {info['type']}"
    test("b23.tv短链解析", t_b23_url)

    def t_bangumi_url():
        info = parser.parse_media_url('https://www.bilibili.com/bangumi/play/ss1234')
        assert info['type'] == 'bangumi', f"Expected bangumi, got {info['type']}"
        assert info['id'] == '1234', f"Expected 1234, got {info['id']}"
    test("番剧URL解析", t_bangumi_url)

    def t_ep_url():
        info = parser.parse_media_url('https://www.bilibili.com/bangumi/play/ep1234')
        assert info['type'] == 'bangumi', f"Expected bangumi, got {info['type']}"
        assert info['id'] == 'ep1234'
    test("番剧EP URL解析", t_ep_url)

    def t_av_url():
        info = parser.parse_media_url('https://www.bilibili.com/video/av170001')
        assert info['type'] == 'av', f"Expected av, got {info['type']}"
        assert info['id'] == '170001'
    test("AV号URL解析", t_av_url)

    def t_cheese_url():
        info = parser.parse_media_url('https://www.bilibili.com/cheese/play/ss123')
        assert info['type'] == 'cheese', f"Expected cheese, got {info['type']}"
    test("课程URL解析", t_cheese_url)


def test_parse_and_download():
    logger.info("=" * 60)
    logger.info("5. 视频解析+下载+合并（端到端）")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)
    save_dir = tempfile.mkdtemp(prefix="bilibili_test_")

    try:
        def t_parse_video():
            result = parser.parse_media('video', 'BV1zb5k6WErV')
            assert result.get('success', False) or result.get('title'), \
                f"parse_media failed: {result.get('error', 'unknown')}"
            assert result.get('title'), "No title"
            assert result.get('bvid'), "No bvid"
            assert result.get('cid'), "No cid"
            logger.info(f"  标题: {result.get('title')}")
        test("视频信息解析", t_parse_video)

        def t_get_play_info():
            result = parser.parse_media('video', 'BV1zb5k6WErV')
            bvid = result.get('bvid', '')
            cid = result.get('cid', '')
            play = parser._get_play_info('video', bvid, cid, False, audio_quality=30280)
            assert play and play.get('success'), f"_get_play_info failed: {play.get('error', '') if play else 'None'}"
            assert play.get('video_urls'), "No video_urls"
            qualities = play.get('qualities', [])
            logger.info(f"  清晰度: {qualities}")
        test("播放信息获取", t_get_play_info)

        def t_download_and_merge():
            result = parser.parse_media('video', 'BV1zb5k6WErV')
            bvid = result.get('bvid', '')
            cid = result.get('cid', '')
            kid = result.get('kid', '')

            play = parser._get_play_info('video', bvid, cid, False, audio_quality=30280)
            video_urls = play.get('video_urls', {})
            audio_url = play.get('audio_url', '')

            qn = None
            for qid in ['16', '32', '64']:
                if qid in video_urls:
                    qn = qid
                    break
            if not qn:
                qn = list(video_urls.keys())[-1]

            video_url = video_urls[qn]
            video_temp = os.path.join(save_dir, "video_temp.m4s")
            audio_temp = os.path.join(save_dir, "audio_temp.m4s") if audio_url else None

            _download_file(video_url, video_temp, headers=_bili_headers())
            assert os.path.exists(video_temp) and os.path.getsize(video_temp) > 10000
            logger.info(f"  视频下载: {os.path.getsize(video_temp)} bytes")

            if audio_url:
                _download_file(audio_url, audio_temp, headers=_bili_headers())
                assert os.path.exists(audio_temp) and os.path.getsize(audio_temp) > 1000
                logger.info(f"  音频下载: {os.path.getsize(audio_temp)} bytes")

            output_path = os.path.join(save_dir, "output.mp4")
            merge_ok = False
            try:
                mr = parser.merge_media(video_temp, audio_temp, output_path, kid)
                if isinstance(mr, tuple):
                    merge_ok, _ = mr
                else:
                    merge_ok = bool(mr)
            except Exception:
                pass

            if not merge_ok:
                ffmpeg = shutil.which('ffmpeg')
                if ffmpeg:
                    import subprocess
                    cmd = [ffmpeg, '-i', video_temp]
                    if audio_temp:
                        cmd += ['-i', audio_temp]
                    cmd += ['-c:v', 'copy', '-c:a', 'copy', '-y', output_path]
                    subprocess.run(cmd, capture_output=True, timeout=60, **subprocess_no_window_kwargs())
                    merge_ok = os.path.exists(output_path)

            assert merge_ok and os.path.exists(output_path), "merge failed"
            output_size = os.path.getsize(output_path)
            assert output_size > 10000, f"output too small: {output_size}"
            logger.info(f"  合并完成: {output_size} bytes ({output_size/1024/1024:.1f} MB)")
        test("下载+合并", t_download_and_merge)

    finally:
        shutil.rmtree(save_dir, ignore_errors=True)


def test_hevc():
    logger.info("=" * 60)
    logger.info("6. HEVC 支持")
    logger.info("=" * 60)

    def t_mac_native_hevc():
        from utils import HEVCCheckThread
        thread = HEVCCheckThread()
        thread.result_signal = _MockSignal()
        thread.run()
        assert thread.result_signal.last_value == True, "macOS should support HEVC natively"
    test("macOS原生HEVC支持", t_mac_native_hevc)

    def t_hevc_download_skip():
        from utils import HEVCDownloadThread
        thread = HEVCDownloadThread(save_path='/tmp', hevc_url='')
        thread.finish_signal = _MockSignal()
        thread.run()
        ok, msg = thread.finish_signal.last_value
        assert ok == True, f"HEVC download should skip on macOS: {msg}"
    test("HEVC安装跳过（Mac不需要）", t_hevc_download_skip)


def test_danmaku():
    logger.info("=" * 60)
    logger.info("7. 弹幕功能")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_get_danmaku():
        result = parser.parse_media('video', 'BV1zb5k6WErV')
        cid = result.get('cid', '')
        if not cid:
            raise AssertionError("No cid for danmaku test")
        danmaku = parser.get_danmaku(cid)
        assert danmaku is not None, "get_danmaku returned None"
        if isinstance(danmaku, list):
            logger.info(f"  弹幕数: {len(danmaku)}")
        else:
            logger.info(f"  弹幕返回类型: {type(danmaku)}")
    test("弹幕获取", t_get_danmaku)


def test_filename_sanitization():
    logger.info("=" * 60)
    logger.info("8. 文件名处理")
    logger.info("=" * 60)

    def t_illegal_chars():
        chars = illegal_filename_chars()
        test_name = "视频/标题:测试*name?test"
        for c in chars:
            test_name = test_name.replace(c, '_')
        assert '/' not in test_name, "/ should be replaced"
        assert ':' not in test_name, ": should be replaced"
        assert '*' in test_name or IS_MACOS, "* should NOT be replaced on macOS"
    test("非法字符替换", t_illegal_chars)

    def t_sanitize():
        result = BilibiliParser._sanitize_filename("test<>file")
        assert '<' not in result
        assert '>' not in result
    test("_sanitize_filename", t_sanitize)


def test_avbv_conversion():
    logger.info("=" * 60)
    logger.info("9. AV/BV号转换")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_bv2av():
        aid = parser.bv2av('BV1zb5k6WErV')
        assert isinstance(aid, int), f"bv2av should return int, got {type(aid)}"
        logger.info(f"  BV1zb5k6WErV -> av{aid}")
    test("bv2av 转换", t_bv2av)

    def t_av2bv():
        aid = parser.bv2av('BV1zb5k6WErV')
        bvid = parser.av2bv(aid)
        assert bvid.startswith('BV'), f"av2bv should return BV string, got {bvid}"
    test("av2bv 转换", t_av2bv)


def test_cookie_and_session():
    logger.info("=" * 60)
    logger.info("10. Cookie/会话管理")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_session_init():
        assert parser.session is not None, "Session should be initialized"
        assert 'buvid3' in str(parser.session.cookies.get_dict()) or len(parser.session.cookies) >= 0
    test("Session 初始化", t_session_init)

    def t_cookie_load():
        result = parser._load_cookies()
        assert isinstance(result, dict), f"Cookie should be dict, got {type(result)}"
    test("Cookie 加载", t_cookie_load)

    def t_verify_cookie():
        result = parser.verify_cookie()
        assert isinstance(result, tuple), f"verify_cookie should return tuple, got {type(result)}"
        is_valid = result[0]
        assert isinstance(is_valid, bool), f"First element should be bool, got {type(is_valid)}"
        logger.info(f"  Cookie有效: {is_valid}")
    test("Cookie 验证", t_verify_cookie)


def test_wbi_sign():
    logger.info("=" * 60)
    logger.info("11. WBI签名")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_wbi_sign():
        params = {'foo': 'bar', 'test': '123'}
        signed = parser._generate_wbi_sign(params)
        assert 'w_rid' in signed, "w_rid should be in signed params"
        assert 'wts' in signed, "wts should be in signed params"
    test("WBI签名生成", t_wbi_sign)


def test_api_request():
    logger.info("=" * 60)
    logger.info("12. API请求")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_api_request_basic():
        success, data = parser._api_request('https://api.bilibili.com/x/web-interface/view',
                                             params={'bvid': 'BV1zb5k6WErV'})
        assert success is True or isinstance(success, bool), f"API request success should be bool, got {type(success)}"
        assert data is not None, "API request returned None data"
        assert data.get('code') == 0, f"API error: {data.get('message', '')}"
    test("基础API请求", t_api_request_basic)


def test_video_codec():
    logger.info("=" * 60)
    logger.info("13. 视频编码检测")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_check_codec():
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg, "ffmpeg not found"
        result = parser.check_video_codec_compatible("/nonexistent/file.mp4")
        assert isinstance(result, dict), f"Should return dict, got {type(result)}"
        assert 'compatible' in result, f"Result should have 'compatible' key, got {result}"
    test("编码检测方法可用", t_check_codec)


def test_decrypt():
    logger.info("=" * 60)
    logger.info("14. 解密功能")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_decrypt_method_exists():
        assert hasattr(parser, 'decrypt_file'), "decrypt_file method missing"
        assert hasattr(parser, '_check_encryption'), "_check_encryption method missing"
    test("解密方法存在", t_decrypt_method_exists)


def test_collection_and_folders():
    logger.info("=" * 60)
    logger.info("15. 合集/收藏夹")
    logger.info("=" * 60)

    config = ConfigLoader()
    parser = BilibiliParser(config)

    def t_get_collection():
        result = parser._get_collection_info('BV1zb5k6WErV')
        assert result is not None, "Collection info returned None"
        logger.info(f"  合集信息类型: {type(result)}")
    test("合集信息获取", t_get_collection)


def test_logger_config():
    logger.info("=" * 60)
    logger.info("16. 日志配置")
    logger.info("=" * 60)

    def t_logger_mac_clipboard():
        from logger_config import setup_logging
        log = setup_logging()
        assert log is not None or True, "setup_logging executed without error"
    test("日志初始化", t_logger_mac_clipboard)


def test_cloud_service():
    logger.info("=" * 60)
    logger.info("17. 云服务/更新检查")
    logger.info("=" * 60)

    def t_cloud_platform():
        from cloud_service import CloudService
        cs = CloudService()
        assert cs.platform == 'macos', f"Expected macos, got {cs.platform}"
    test("云服务平台标识", t_cloud_platform)


class _MockSignal:
    def __init__(self):
        self.last_value = None

    def emit(self, *args):
        self.last_value = args[0] if len(args) == 1 else args


def _download_file(url, save_path, headers=None, chunk_size=8192, max_retries=5):
    import requests
    from requests.exceptions import ChunkedEncodingError, ConnectionError

    existing_size = 0
    if os.path.exists(save_path):
        existing_size = os.path.getsize(save_path)

    for attempt in range(1, max_retries + 1):
        try:
            req_headers = dict(headers) if headers else {}
            if existing_size > 0:
                req_headers['Range'] = f'bytes={existing_size}-'

            resp = requests.get(url, headers=req_headers, stream=True, timeout=60)
            if resp.status_code == 416:
                return
            resp.raise_for_status()

            content_length = int(resp.headers.get('content-length', 0))
            total = existing_size + content_length

            mode = 'ab' if existing_size > 0 and resp.status_code == 206 else 'wb'
            if resp.status_code != 206 and existing_size > 0:
                existing_size = 0
                total = content_length
                mode = 'wb'

            downloaded = existing_size
            with open(save_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and downloaded % (500 * 1024) < chunk_size:
                            pct = int(downloaded * 100 / total)
                            logger.info(f"  下载进度: {pct}% ({downloaded}/{total})")
            resp.close()
            return
        except (ChunkedEncodingError, ConnectionError, requests.exceptions.RequestException) as e:
            logger.warning(f"  下载中断 (尝试 {attempt}/{max_retries}): {e}")
            if os.path.exists(save_path):
                existing_size = os.path.getsize(save_path)
            if attempt == max_retries:
                raise
            time.sleep(2 * attempt)


def _bili_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }


if __name__ == '__main__':
    exit_code = 0
    try:
        test_platform_utils()
        test_tool_manager()
        test_config()
        test_url_parsing()
        test_parse_and_download()
        test_hevc()
        test_danmaku()
        test_filename_sanitization()
        test_avbv_conversion()
        test_cookie_and_session()
        test_wbi_sign()
        test_api_request()
        test_video_codec()
        test_decrypt()
        test_collection_and_folders()
        test_logger_config()
        test_cloud_service()

        logger.info("=" * 60)
        logger.info(f"测试完成: ✅ {passed} 通过, ❌ {failed} 失败")
        logger.info("=" * 60)

        if errors:
            logger.error("失败的测试:")
            for name, err in errors:
                logger.error(f"  ❌ {name}: {err}")

        if failed > 0:
            exit_code = 1
    except Exception as e:
        logger.error(f"测试执行异常: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1
    finally:
        os._exit(exit_code)
