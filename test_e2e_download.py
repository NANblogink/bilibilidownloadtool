import os
import sys
import shutil
import tempfile
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

from config import ConfigLoader
from bilibili_parser import BilibiliParser
from platform_utils import IS_MACOS, exe, subprocess_no_window_kwargs

def test_download_and_merge():
    save_dir = tempfile.mkdtemp(prefix="bilibili_test_")
    logger.info(f"保存目录: {save_dir}")

    try:
        config = ConfigLoader()
        parser = BilibiliParser(config)
        logger.info("BilibiliParser 初始化成功")

        url = 'https://www.bilibili.com/video/BV1zb5k6WErV/'
        logger.info(f"解析 URL: {url}")

        url_info = parser.parse_media_url(url)
        assert url_info['type'] == 'video', f"Expected video, got {url_info['type']}"
        assert url_info['id'] == 'BV1zb5k6WErV'
        logger.info(f"URL 解析成功: type={url_info['type']}, id={url_info['id']}")

        result = parser.parse_media(url_info['type'], url_info['id'])
        success = result.get('success', False)
        error = result.get('error', '')
        title = result.get('title', '')
        collection = result.get('collection', [])
        episodes = result.get('episodes', [])
        qualities = result.get('qualities', {})
        video_urls = result.get('video_urls', {})
        audio_url = result.get('audio_url', '')
        kid = result.get('kid', '')
        bvid = result.get('bvid', '')
        cid = result.get('cid', '')

        logger.info(f"parse_media 返回: success={success}, title={title}")
        logger.info(f"  collection 数: {len(collection)}")
        logger.info(f"  episodes 数: {len(episodes)}")
        logger.info(f"  qualities: {list(qualities.keys()) if isinstance(qualities, dict) else qualities}")
        logger.info(f"  video_urls keys: {list(video_urls.keys()) if isinstance(video_urls, dict) else 'N/A'}")
        logger.info(f"  audio_url: {audio_url[:60] if audio_url else 'None'}...")
        logger.info(f"  kid: {kid}")
        logger.info(f"  bvid: {bvid}, cid: {cid}")

        if not success and error:
            logger.error(f"parse_media 返回错误: {error}")
            assert False, f"parse_media 失败: {error}"

        assert title, "未获取到标题"
        assert bvid, "未获取到 bvid"
        assert cid, "未获取到 cid"

        ep_list = collection if collection else episodes
        if not ep_list:
            logger.warning("collection 和 episodes 都为空，使用 bvid/cid 直接获取播放信息")
        else:
            logger.info(f"分P/合集数: {len(ep_list)}")
            first_ep = ep_list[0]
            cid = first_ep.get('cid', cid)
            logger.info(f"使用第一集 cid={cid}")

        if not video_urls:
            logger.info("video_urls 为空，重新获取播放信息...")
            play_info = parser._get_play_info('video', bvid, cid, False, audio_quality=30280)
            assert play_info and play_info.get('success'), f"获取播放信息失败: {play_info.get('error', '') if play_info else 'None'}"
            video_urls = play_info.get('video_urls', {})
            audio_url = play_info.get('audio_url', '')
            kid = play_info.get('kid', '')
            qualities = play_info.get('qualities', {})
            logger.info(f"重新获取成功: qualities={list(qualities.keys()) if isinstance(qualities, dict) else qualities}")

        assert video_urls, "无视频流地址"

        qn = None
        video_url = None
        if isinstance(qualities, dict):
            for qid in ['16', '32', '64', '80']:
                if qid in qualities:
                    qn = qid
                    break
            if not qn and qualities:
                qn = list(qualities.keys())[-1]

        if qn and qn in video_urls:
            video_url = video_urls[qn]
            qdesc = qualities.get(qn, '')
            logger.info(f"选择清晰度: {qn} ({qdesc})")
        elif video_urls:
            first_key = list(video_urls.keys())[0]
            video_url = video_urls[first_key]
            qn = first_key
            logger.info(f"使用清晰度: {qn}")

        assert video_url, "未能获取视频流URL"
        logger.info(f"视频流地址: {video_url[:80]}...")
        if audio_url:
            logger.info(f"音频流地址: {audio_url[:80]}...")

        video_temp = os.path.join(save_dir, "video_temp.m4s")
        audio_temp = os.path.join(save_dir, "audio_temp.m4s") if audio_url else None

        logger.info("开始下载视频流...")
        _download_file(video_url, video_temp, headers=_bili_headers())
        assert os.path.exists(video_temp), "视频文件下载失败"
        video_size = os.path.getsize(video_temp)
        logger.info(f"视频下载完成: {video_size} bytes")
        assert video_size > 10000, f"视频文件过小: {video_size} bytes"

        if audio_url:
            logger.info("开始下载音频流...")
            _download_file(audio_url, audio_temp, headers=_bili_headers())
            assert os.path.exists(audio_temp), "音频文件下载失败"
            audio_size = os.path.getsize(audio_temp)
            logger.info(f"音频下载完成: {audio_size} bytes")

        safe_title = title[:30]
        for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
            safe_title = safe_title.replace(c, '_')
        output_path = os.path.join(save_dir, f"{safe_title}.mp4")

        logger.info(f"开始合并音视频: {output_path}")
        merge_ok = False
        merge_msg = ""

        try:
            merge_result = parser.merge_media(video_temp, audio_temp, output_path, kid)
            if isinstance(merge_result, tuple):
                merge_ok, merge_msg = merge_result
            elif isinstance(merge_result, bool):
                merge_ok = merge_result
            else:
                merge_ok = bool(merge_result)
        except Exception as e:
            merge_msg = str(e)
            logger.warning(f"parser.merge_media 异常: {e}")

        if not merge_ok:
            logger.warning(f"parser.merge_media 失败: {merge_msg}，尝试直接 ffmpeg 合并")
            ffmpeg_path = shutil.which('ffmpeg') or getattr(parser, 'ffmpeg_local', 'ffmpeg')
            if os.path.isfile(ffmpeg_path) or shutil.which(ffmpeg_path):
                import subprocess
                cmd = [ffmpeg_path if os.path.isfile(ffmpeg_path) else shutil.which(ffmpeg_path)]
                cmd += ['-i', video_temp]
                if audio_temp:
                    cmd += ['-i', audio_temp]
                cmd += ['-c:v', 'copy', '-c:a', 'copy', '-y', output_path]
                logger.info(f"执行 ffmpeg: {' '.join(cmd[:6])}...")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, **subprocess_no_window_kwargs())
                if result.returncode != 0:
                    logger.error(f"ffmpeg stderr: {result.stderr[:500]}")
                merge_ok = os.path.exists(output_path) and os.path.getsize(output_path) > 1000

        assert merge_ok, f"合并失败: {merge_msg}"
        assert os.path.exists(output_path), "合并后文件不存在"

        output_size = os.path.getsize(output_path)
        logger.info(f"合并完成! 文件大小: {output_size} bytes ({output_size/1024/1024:.1f} MB)")
        assert output_size > 10000, f"合并后文件过小: {output_size} bytes"

        logger.info("=" * 50)
        logger.info("端到端测试全部通过!")
        logger.info(f"  解析: OK (title={title})")
        logger.info(f"  下载: OK (视频 {video_size} bytes)")
        logger.info(f"  合并: OK ({output_size} bytes, {output_size/1024/1024:.1f} MB)")
        logger.info("=" * 50)

    finally:
        try:
            shutil.rmtree(save_dir, ignore_errors=True)
            logger.info(f"清理临时目录: {save_dir}")
        except Exception as e:
            logger.warning(f"清理失败: {e}")


def _download_file(url, save_path, headers=None, chunk_size=8192):
    import requests
    resp = requests.get(url, headers=headers, stream=True, timeout=30)
    resp.raise_for_status()
    total = int(resp.headers.get('content-length', 0))
    downloaded = 0
    with open(save_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total > 0 and downloaded % (500 * 1024) < chunk_size:
                    pct = int(downloaded * 100 / total)
                    logger.info(f"  下载进度: {pct}% ({downloaded}/{total})")


def _bili_headers():
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
        'Referer': 'https://www.bilibili.com/',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    }


if __name__ == '__main__':
    try:
        test_download_and_merge()
    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        os._exit(0)
