#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频解析工具 - 命令行界面
在GUI无法启动时自动降级使用，也可通过 bilibilidownloadtool 命令手动启动
"""
import sys
import os
import re
import time
import json
import shutil
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

from app_config import APP_NAME, APP_VERSION

# 全局解析器实例
_parser = None
_config = None
_fallback_reason = ""


def get_parser():
    """获取或初始化解析器"""
    global _parser
    if _parser is None:
        try:
            from bilibili_parser import BilibiliParser
            _parser = BilibiliParser()
            logger.info("解析器初始化成功")
        except Exception as e:
            logger.error(f"解析器初始化失败: {e}")
            print(f"\n  [错误] 解析器初始化失败: {e}")
            return None
    return _parser


def get_config():
    """获取或初始化配置"""
    global _config
    if _config is None:
        try:
            from config import ConfigLoader
            _config = ConfigLoader()
        except Exception:
            _config = None
    return _config


def get_save_path():
    """获取默认保存路径"""
    config = get_config()
    if config:
        path = config.get_app_setting("default_save_path", "")
        if path and os.path.isdir(os.path.dirname(path)):
            return path
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "B站下载")


def sanitize_filename(name):
    """清理文件名中的非法字符"""
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', name).strip('. ')


def _logo_to_ascii(width=90):
    """将logo.png转换为ASCII字符画（8级灰度，保留文字细节）"""
    try:
        from PIL import Image, ImageOps

        logo_path = None
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
            candidates = [
                os.path.join(base, '_internal', 'logo.png'),
                os.path.join(base, 'logo.png'),
            ]
        else:
            src_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(src_dir, 'logo.png'),
            ]

        for p in candidates:
            if os.path.exists(p):
                logo_path = p
                break

        if not logo_path:
            return None

        img = Image.open(logo_path)
        img = img.convert('L')
        # 增强对比度（拉伸直方图，让文字更清晰）
        img = ImageOps.autocontrast(img, cutoff=2)
        # 不反转！原图：深色文字+图标 / 浅色背景
        aspect = img.height / img.width
        new_width = width
        new_height = int(new_width * aspect * 0.45)  # 0.45: 字符高宽比约2:1
        img = img.resize((new_width, new_height), Image.LANCZOS)

        pixels = list(img.getdata())
        # 8级灰度字符表（从暗到亮）：
        # 密字符表示深色区域（文字/图标），空字符表示浅色区域（背景）
        shade_chars = ["@", "%", "#", "*", "+", "=", "-", " "]
        result = []
        for y in range(new_height):
            row = ""
            for x in range(new_width):
                px = pixels[y * new_width + x]
                # 0(黑)=@(最密) ~ 255(白)=空格(最疏)
                level = min(int(px / 32), 7)  # 256/8=32 每级
                row += shade_chars[level]
            result.append(row)
        # 裁掉顶部和底部连续空白行
        while result and not result[-1].strip():
            result.pop()
        while result and not result[0].strip():
            result.pop(0)
        return '\n'.join(result)
    except Exception:
        return None


def print_banner():
    """打印顶部横幅"""
    ascii_logo = _logo_to_ascii(50)
    if ascii_logo:
        print()
        for line in ascii_logo.split('\n'):
            print(f"  {line}")
    print("\n" + "=" * 60)
    print(f"  {APP_NAME} {APP_VERSION} - 命令行模式")
    if _fallback_reason:
        print(f"  [降级模式] GUI启动失败原因: {_fallback_reason}")
        print(f"  已自动降级为命令行模式")
    print("=" * 60)


def print_menu():
    """打印主菜单"""
    print("\n┌─────────────────────────────────┐")
    print("│         主 菜 单                 │")
    print("├─────────────────────────────────┤")
    print("│  1. 解析视频链接                 │")
    print("│  2. 下载视频                     │")
    print("│  3. 下载弹幕                     │")
    print("│  4. 下载封面                     │")
    print("│  5. 查看收藏夹                   │")
    print("│  6. 登录账号                     │")
    print("│  7. 设置保存路径                 │")
    print("│  0. 退出                         │")
    print("└─────────────────────────────────┘")


def is_bilibili_url(text):
    """验证是否为B站链接"""
    text = text.strip()
    if not text:
        return False
    if re.search(r'https?://', text, re.IGNORECASE):
        patterns = [
            r'https?://(?:www\.)?bilibili\.com',
            r'https?://(?:www\.)?b23\.tv',
            r'https?://space\.bilibili\.com',
            r'https?://cheese\.bilibili\.com',
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)
    standalone = [
        r'^BV1[0-9A-Za-z]{9}$',
        r'^av\d+$',
        r'^\d{10,}$',
        r'^ep\d+$',
        r'^ss\d+$',
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in standalone)


def do_parse():
    """解析视频链接"""
    url = input("\n请输入B站视频链接: ").strip()
    if not url:
        print("  [提示] 未输入链接")
        return None
    if not is_bilibili_url(url):
        print("  [错误] 不是有效的B站链接")
        return None

    parser = get_parser()
    if not parser:
        return None

    print("\n  正在解析...")
    try:
        parse_result = parser.parse_media_url(url)
        if parse_result.get("error"):
            print(f"  [错误] URL解析失败: {parse_result['error']}")
            return None

        media_type = parse_result["type"]
        media_id = parse_result["id"]
        print(f"  识别类型: {media_type}, ID: {media_id}")

        if media_type == "space":
            do_parse_space(parser, media_id)
            return None

        def progress_cb(pct, msg):
            print(f"\r  进度: {pct}% - {msg}", end="", flush=True)

        result = parser.parse_media(media_type, media_id, False, progress_cb)
        print()  # 换行

        if not result.get("success"):
            print(f"  [错误] 解析失败: {result.get('error', '未知错误')}")
            return None

        title = result.get("title", "未知标题")
        bvid = result.get("bvid", "")
        collection = result.get("collection", [])

        print(f"\n  标题: {title}")
        print(f"  BV号: {bvid}")

        if collection:
            print(f"\n  共 {len(collection)} 个分P:")
            for i, ep in enumerate(collection):
                ep_title = ep.get("title", f"第{i+1}集")
                ep_cid = ep.get("cid", "")
                ep_bvid = ep.get("bvid", bvid)
                duration = ep.get("duration", 0)
                dur_str = f"{duration//60}:{duration%60:02d}" if duration else ""
                print(f"    P{i+1}. {ep_title}  {dur_str}  (cid:{ep_cid}, bvid:{ep_bvid})")
        else:
            cid = result.get("cid", "")
            print(f"  CID: {cid}")

        return result

    except Exception as e:
        print(f"\n  [错误] 解析异常: {e}")
        return None


def do_parse_space(parser, mid):
    """解析UP主主页"""
    try:
        print(f"  正在获取UP主信息 (mid: {mid})...")
        space_info = parser.get_space_info(mid)
        if not space_info.get("success"):
            print(f"  [错误] {space_info.get('error', '获取失败')}")
            return

        name = space_info.get("name", "未知")
        sign = space_info.get("sign", "")
        fans = space_info.get("fans", 0)
        print(f"\n  UP主: {name}")
        print(f"  粉丝: {fans}")
        if sign:
            print(f"  签名: {sign}")

        print(f"\n  正在获取作品列表...")
        videos_info = parser.get_space_videos(mid, load_all=True, progress_callback=lambda msg: print(f"    {msg}"))
        if not videos_info.get("success"):
            print(f"  [错误] {videos_info.get('error', '获取失败')}")
            return

        videos = videos_info.get("videos", [])
        total = videos_info.get("total", len(videos))
        print(f"  共 {total} 个作品，已加载 {len(videos)} 个:")
        for i, v in enumerate(videos[:30]):
            vtitle = v.get("title", "未知")
            vbvid = v.get("bvid", "")
            vplay = v.get("play", 0)
            print(f"    {i+1}. {vtitle}  (BV: {vbvid}, 播放: {vplay})")
        if len(videos) > 30:
            print(f"    ... 还有 {len(videos)-30} 个作品未显示")

    except Exception as e:
        print(f"  [错误] {e}")


def do_download_video():
    """下载视频"""
    result = do_parse()
    if not result:
        return

    collection = result.get("collection", [])
    bvid = result.get("bvid", "")
    title = result.get("title", "")
    cid = result.get("cid", "")

    selected = []
    if collection:
        print(f"\n  请选择要下载的分P (输入编号，多个用逗号分隔，0=全部):")
        choice = input("  > ").strip()
        if choice == "0" or choice == "":
            selected = list(range(len(collection)))
        else:
            try:
                indices = [int(x.strip()) - 1 for x in choice.split(",")]
                selected = [i for i in indices if 0 <= i < len(collection)]
            except ValueError:
                print("  [错误] 输入格式不正确")
                return
    else:
        selected = [0]
        collection = [{"title": title, "cid": cid, "bvid": bvid}]

    if not selected:
        print("  [提示] 未选择任何分P")
        return

    print("\n  可选画质:")
    print("    1. 1080P    2. 720P    3. 480P    4. 360P")
    qn_choice = input("  选择画质 (默认1): ").strip()
    qn_map = {"1": 80, "2": 64, "3": 32, "4": 16}
    qn = qn_map.get(qn_choice, 80)

    save_path = get_save_path()
    os.makedirs(save_path, exist_ok=True)

    parser = get_parser()
    if not parser:
        return

    for idx in selected:
        ep = collection[idx]
        ep_title = ep.get("title", f"第{idx+1}集")
        ep_cid = ep.get("cid", cid)
        ep_bvid = ep.get("bvid", bvid)

        print(f"\n  正在下载: {ep_title}")

        try:
            is_bangumi = result.get("is_bangumi", False)
            is_cheese = result.get("is_cheese", False)
            if is_bangumi:
                media_type = "bangumi"
            elif is_cheese:
                media_type = "cheese"
            else:
                media_type = "video"

            play_info = parser._get_play_info(media_type, ep_bvid, ep_cid, False)
            if not play_info.get("success"):
                print(f"  [错误] 获取下载链接失败: {play_info.get('error', '未知')}")
                continue

            video_urls = play_info.get("video_urls", {})
            quality_desc = play_info.get("quality_desc", "")
            audio_url = play_info.get("audio_url", "")
            # 获取KID（付费课程/番剧DRM解密用，未提供时download_file内部会从m4s自动提取）
            ep_kid = play_info.get("kid")

            video_url = ""
            qn_str = str(qn)
            if qn_str in video_urls:
                video_url = video_urls[qn_str]
            else:
                for url in video_urls.values():
                    video_url = url
                    break

            if not video_url:
                print(f"  [错误] 未获取到视频链接")
                continue

            print(f"  画质: {quality_desc}")

            safe_title = sanitize_filename(ep_title)
            if len(collection) > 1:
                video_file = os.path.join(save_path, f"{safe_title}_P{idx+1}.mp4")
            else:
                video_file = os.path.join(save_path, f"{safe_title}.mp4")

            print(f"  下载视频流...")
            def video_progress(done, total):
                pct = int(done / total * 100) if total > 0 else 0
                mb_done = done / 1024 / 1024
                mb_total = total / 1024 / 1024
                print(f"\r  视频进度: {pct}% ({mb_done:.1f}/{mb_total:.1f}MB)", end="", flush=True)

            parser.download_file(video_url, video_file + ".video.tmp", video_progress, "video", ep_bvid, kid=ep_kid)
            print()

            if audio_url:
                print(f"  下载音频流...")
                def audio_progress(done, total):
                    pct = int(done / total * 100) if total > 0 else 0
                    mb_done = done / 1024 / 1024
                    mb_total = total / 1024 / 1024
                    print(f"\r  音频进度: {pct}% ({mb_done:.1f}/{mb_total:.1f}MB)", end="", flush=True)

                parser.download_file(audio_url, video_file + ".audio.tmp", audio_progress, "audio", ep_bvid, kid=ep_kid)
                print()

                print(f"  合并音视频...")
                if merge_video_audio(video_file + ".video.tmp", video_file + ".audio.tmp", video_file):
                    print(f"  [成功] 已保存: {video_file}")
                else:
                    # 合并失败，保留视频流
                    try:
                        shutil.move(video_file + ".video.tmp", video_file)
                        print(f"  [提示] 合并失败，仅保存视频流: {video_file}")
                    except Exception:
                        print(f"  [错误] 保存失败")
            else:
                # 无音频，直接重命名
                try:
                    shutil.move(video_file + ".video.tmp", video_file)
                    print(f"  [成功] 已保存: {video_file}")
                except Exception as e:
                    print(f"  [错误] 保存失败: {e}")

            for tmp in [video_file + ".video.tmp", video_file + ".audio.tmp"]:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass

        except Exception as e:
            print(f"\n  [错误] 下载失败: {e}")


def merge_video_audio(video_tmp, audio_tmp, output):
    """使用ffmpeg合并音视频"""
    ffmpeg_path = _find_ffmpeg()
    if not ffmpeg_path:
        print("  [警告] 未找到ffmpeg，无法合并音视频")
        return False

    import subprocess
    try:
        cmd = [
            ffmpeg_path, '-y',
            '-i', video_tmp,
            '-i', audio_tmp,
            '-c:v', 'copy', '-c:a', 'copy',
            '-movflags', '+faststart',
            output
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode == 0 and os.path.exists(output) and os.path.getsize(output) > 0:
            return True
        return False
    except Exception as e:
        logger.error(f"ffmpeg合并失败: {e}")
        return False


def _find_ffmpeg():
    """查找ffmpeg路径"""
    # 1. _internal目录
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
        for candidate in [
            os.path.join(base, '_internal', 'ffmpeg', 'bin', 'ffmpeg.exe'),
            os.path.join(base, 'ffmpeg', 'bin', 'ffmpeg.exe'),
        ]:
            if os.path.exists(candidate):
                return candidate

    # 2. 源码目录
    src_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in [
        os.path.join(src_dir, 'ffmpeg', 'bin', 'ffmpeg.exe'),
        os.path.join(src_dir, '_internal', 'ffmpeg', 'bin', 'ffmpeg.exe'),
    ]:
        if os.path.exists(candidate):
            return candidate

    # 3. PATH
    return shutil.which('ffmpeg')


def do_download_danmaku():
    """下载弹幕"""
    url = input("\n请输入B站视频链接: ").strip()
    if not url or not is_bilibili_url(url):
        print("  [错误] 不是有效的B站链接")
        return

    parser = get_parser()
    if not parser:
        return

    try:
        print("  正在解析...")
        parse_result = parser.parse_media_url(url)
        if parse_result.get("error"):
            print(f"  [错误] {parse_result['error']}")
            return

        media_type = parse_result["type"]
        media_id = parse_result["id"]

        result = parser.parse_media(media_type, media_id, False)
        if not result.get("success"):
            print(f"  [错误] 解析失败: {result.get('error')}")
            return

        title = result.get("title", "未知")
        bvid = result.get("bvid", "")
        collection = result.get("collection", [])
        cid = result.get("cid", "")

        if collection:
            print(f"\n  共 {len(collection)} 个分P:")
            for i, ep in enumerate(collection[:20]):
                print(f"    P{i+1}. {ep.get('title', '')}")
            choice = input("  选择分P编号 (0=全部): ").strip()
            if choice == "0":
                selected_eps = list(range(len(collection)))
            else:
                try:
                    selected_eps = [int(x.strip()) - 1 for x in choice.split(",")]
                except ValueError:
                    selected_eps = [0]
        else:
            selected_eps = [0]
            collection = [{"cid": cid, "title": title}]

        print("\n  弹幕格式: 1. XML  2. ASS")
        fmt_choice = input("  选择 (默认1): ").strip()
        danmaku_format = "ass" if fmt_choice == "2" else "xml"

        save_path = get_save_path()
        os.makedirs(save_path, exist_ok=True)

        for idx in selected_eps:
            if idx >= len(collection):
                continue
            ep = collection[idx]
            ep_cid = ep.get("cid", cid)
            ep_title = ep.get("title", title)

            print(f"\n  正在获取弹幕: {ep_title}")
            danmaku_result = parser.get_danmaku(ep_cid, aid=None)
            if not danmaku_result.get("success"):
                print(f"  [错误] {danmaku_result.get('error', '获取失败')}")
                continue

            danmaku_list = danmaku_result.get("danmaku", [])
            print(f"  获取到 {len(danmaku_list)} 条弹幕")

            safe_title = sanitize_filename(ep_title)
            ext = danmaku_format
            danmaku_file = os.path.join(save_path, f"{safe_title}.{ext}")

            if danmaku_format == "xml":
                _save_danmaku_xml(danmaku_list, danmaku_file)
            else:
                _save_danmaku_ass(danmaku_list, danmaku_file, ep_title)

            print(f"  [成功] 已保存: {danmaku_file}")

    except Exception as e:
        print(f"\n  [错误] {e}")


def _save_danmaku_xml(danmaku_list, filepath):
    """保存弹幕为XML格式"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<i>\n')
        f.write(f'  <chatserver>chat.bilibili.com</chatserver>\n')
        f.write(f'  <chatid>0</chatid>\n')
        f.write(f'  <mission>0</mission>\n')
        f.write(f'  <maxlimit>0</maxlimit>\n')
        f.write(f'  <state>0</state>\n')
        for d in danmaku_list:
            p_attrs = [
                str(d.get("progress", 0) / 1000),
                str(d.get("mode", 1)),
                str(d.get("fontsize", 25)),
                str(d.get("color", 16777215)),
                str(d.get("ctime", 0)),
                str(d.get("pool", 0)),
                d.get("midHash", ""),
                d.get("idStr", "0"),
            ]
            p_str = ",".join(p_attrs)
            content = d.get("content", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            f.write(f'  <d p="{p_str}">{content}</d>\n')
        f.write('</i>\n')


def _save_danmaku_ass(danmaku_list, filepath, title=""):
    """保存弹幕为ASS格式（简化版）"""
    width, height = 1920, 1080
    font_size = 36
    duration = 8.0

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('[Script Info]\n')
        f.write('Title: {}\n'.format(title))
        f.write('ScriptType: v4.00+\n')
        f.write(f'PlayResX: {width}\nPlayResY: {height}\n')
        f.write('Timer: 100.0000\n\n')
        f.write('[V4+ Styles]\n')
        f.write('Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, '
                'OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, '
                'ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, '
                'Alignment, MarginL, MarginR, MarginV, Encoding\n')
        f.write(f'Style: Danmaku,Microsoft YaHei,{font_size},&H00FFFFFF,&H00FFFFFF,'
                f'&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,0,0,0,0\n\n')
        f.write('[Events]\n')
        f.write('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')

        for i, d in enumerate(danmaku_list):
            progress = d.get("progress", 0) / 1000
            start_h = int(progress // 3600)
            start_m = int((progress % 3600) // 60)
            start_s = progress % 60
            end_time = progress + duration
            end_h = int(end_time // 3600)
            end_m = int((end_time % 3600) // 60)
            end_s = end_time % 60

            start_str = f"{start_h}:{start_m:02d}:{start_s:05.2f}"
            end_str = f"{end_h}:{end_m:02d}:{end_s:05.2f}"

            color = d.get("color", 16777215)
            hex_color = f"{color:06X}"
            # BGR to RGB
            r, g, b = hex_color[4:6], hex_color[2:4], hex_color[0:2]
            ass_color = f"&H00{b}{g}{r}"

            content = d.get("content", "").replace("\\N", "\\\\N").replace("\n", "\\N")
            mode = d.get("mode", 1)
            if mode == 4:  # 底部
                pos_y = height - 60
                f.write(f'Dialogue: 2,{start_str},{end_str},Danmaku,,0,0,0,,'
                        f'{{\\pos({width//2},{pos_y})\\c{ass_color}}}{content}\n')
            elif mode == 5:  # 顶部
                pos_y = 60
                f.write(f'Dialogue: 2,{start_str},{end_str},Danmaku,,0,0,0,,'
                        f'{{\\pos({width//2},{pos_y})\\c{ass_color}}}{content}\n')
            else:  # 滚动
                f.write(f'Dialogue: 2,{start_str},{end_str},Danmaku,,0,0,0,,'
                        f'{{\\c{ass_color}}}{content}\n')


def do_download_cover():
    """下载视频封面"""
    url = input("\n请输入B站视频链接: ").strip()
    if not url or not is_bilibili_url(url):
        print("  [错误] 不是有效的B站链接")
        return

    parser = get_parser()
    if not parser:
        return

    try:
        print("  正在解析...")
        parse_result = parser.parse_media_url(url)
        if parse_result.get("error"):
            print(f"  [错误] {parse_result['error']}")
            return

        result = parser.parse_media(parse_result["type"], parse_result["id"], False)
        if not result.get("success"):
            print(f"  [错误] 解析失败: {result.get('error')}")
            return

        title = result.get("title", "未知")
        cover_url = result.get("cover", "")
        if not cover_url:
            print("  [错误] 未获取到封面链接")
            return

        # B站封面需要加referer
        print(f"  封面链接: {cover_url[:80]}...")

        save_path = get_save_path()
        os.makedirs(save_path, exist_ok=True)

        safe_title = sanitize_filename(title)
        if '.jpg' in cover_url or '.jpeg' in cover_url:
            ext = 'jpg'
        elif '.webp' in cover_url:
            ext = 'webp'
        elif '.png' in cover_url:
            ext = 'png'
        else:
            ext = 'jpg'

        cover_file = os.path.join(save_path, f"{safe_title}_cover.{ext}")

        def cover_progress(done, total):
            pct = int(done / total * 100) if total > 0 else 0
            print(f"\r  下载进度: {pct}%", end="", flush=True)

        parser.download_file(cover_url, cover_file, cover_progress, "cover")
        print(f"\n  [成功] 已保存: {cover_file}")

    except Exception as e:
        print(f"\n  [错误] {e}")


def do_favorites():
    """查看收藏夹"""
    parser = get_parser()
    if not parser:
        return

    if not parser.cookies:
        print("\n  [提示] 请先登录 (菜单6) 才能查看收藏夹")
        return

    try:
        print("\n  正在获取收藏夹列表...")
        folders = parser.get_user_folders()
        if not folders:
            print("  [提示] 没有收藏夹")
            return

        print(f"\n  收藏夹列表:")
        for i, f in enumerate(folders):
            fname = f.get("title", "未命名")
            fcount = f.get("media_count", 0)
            fid = f.get("id", "")
            print(f"    {i+1}. {fname} ({fcount}个内容) [id:{fid}]")

        choice = input("\n  选择收藏夹编号查看内容 (0=返回): ").strip()
        try:
            idx = int(choice) - 1
        except ValueError:
            return

        if idx < 0 or idx >= len(folders):
            return

        folder = folders[idx]
        media_id = folder.get("id")
        print(f"\n  正在获取 [{folder.get('title')}] 的内容...")

        result = parser.get_folder_content(media_id, page=1, page_size=20, get_all=False)
        items = result.get("items", [])
        total = result.get("total", 0)
        if not items:
            print("  [提示] 收藏夹为空")
            return

        print(f"\n  收藏内容 (共{total}个):")
        for i, item in enumerate(items):
            ititle = item.get("title", "未知")
            iupper = item.get("up_name", "")
            iduration = item.get("duration", 0)
            dur_str = f"{iduration//60}:{iduration%60:02d}" if iduration else ""
            ibvid = item.get("bvid", "")
            print(f"    {i+1}. {ititle}  UP:{iupper}  {dur_str}  [{ibvid}]")

        dl_choice = input("\n  输入编号下载视频 (0=返回): ").strip()
        try:
            dl_idx = int(dl_choice) - 1
        except ValueError:
            return

        if 0 <= dl_idx < len(items):
            item = items[dl_idx]
            ibvid = item.get("bvid", "")
            if ibvid:
                print(f"\n  正在解析: {item.get('title')}")
                # 复用下载逻辑
                url = f"https://www.bilibili.com/video/{ibvid}"
                _download_by_url(url)

    except Exception as e:
        print(f"  [错误] {e}")


def _download_by_url(url):
    """通过URL直接下载视频（内部使用）"""
    parser = get_parser()
    if not parser:
        return

    try:
        parse_result = parser.parse_media_url(url)
        if parse_result.get("error"):
            print(f"  [错误] {parse_result['error']}")
            return

        result = parser.parse_media(parse_result["type"], parse_result["id"], False)
        if not result.get("success"):
            print(f"  [错误] 解析失败: {result.get('error')}")
            return

        title = result.get("title", "")
        bvid = result.get("bvid", "")
        cid = result.get("cid", "")

        is_bangumi = result.get("is_bangumi", False)
        is_cheese = result.get("is_cheese", False)
        if is_bangumi:
            media_type = "bangumi"
        elif is_cheese:
            media_type = "cheese"
        else:
            media_type = "video"

        play_info = parser._get_play_info(media_type, bvid, cid, False)
        if not play_info.get("success"):
            print(f"  [错误] 获取下载链接失败: {play_info.get('error')}")
            return

        video_urls = play_info.get("video_urls", {})
        audio_url = play_info.get("audio_url", "")
        ep_kid = play_info.get("kid")
        video_url = ""
        for url in video_urls.values():
            video_url = url
            break

        save_path = get_save_path()
        os.makedirs(save_path, exist_ok=True)
        safe_title = sanitize_filename(title)
        video_file = os.path.join(save_path, f"{safe_title}.mp4")

        print(f"  下载视频流...")
        def vp(done, total):
            pct = int(done / total * 100) if total > 0 else 0
            print(f"\r  视频进度: {pct}%", end="", flush=True)
        parser.download_file(video_url, video_file + ".video.tmp", vp, "video", bvid, kid=ep_kid)
        print()

        if audio_url:
            print(f"  下载音频流...")
            def ap(done, total):
                pct = int(done / total * 100) if total > 0 else 0
                print(f"\r  音频进度: {pct}%", end="", flush=True)
            parser.download_file(audio_url, video_file + ".audio.tmp", ap, "audio", bvid, kid=ep_kid)
            print()

            print(f"  合并音视频...")
            if merge_video_audio(video_file + ".video.tmp", video_file + ".audio.tmp", video_file):
                print(f"  [成功] 已保存: {video_file}")
            else:
                try:
                    shutil.move(video_file + ".video.tmp", video_file)
                    print(f"  [提示] 合并失败，仅保存视频流: {video_file}")
                except Exception:
                    print(f"  [错误] 保存失败")
        else:
            try:
                shutil.move(video_file + ".video.tmp", video_file)
                print(f"  [成功] 已保存: {video_file}")
            except Exception as e:
                print(f"  [错误] {e}")

        for tmp in [video_file + ".video.tmp", video_file + ".audio.tmp"]:
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    except Exception as e:
        print(f"\n  [错误] {e}")


def do_login():
    """登录B站账号"""
    parser = get_parser()
    if not parser:
        return

    print("\n  登录方式:")
    print("    1. 扫码登录")
    print("    2. 输入Cookie")
    choice = input("  选择: ").strip()

    if choice == "1":
        try:
            print("\n  正在获取登录二维码...")
            qrcode_result = parser.get_qrcode()
            if not qrcode_result.get("success"):
                print(f"  [错误] {qrcode_result.get('error', '获取二维码失败')}")
                return

            qrcode_url = qrcode_result.get("url", "")
            qrcode_key = qrcode_result.get("qrcode_key", "")

            if not qrcode_url:
                print("  [错误] 未获取到二维码链接")
                return

            print(f"\n  请使用B站APP扫描以下二维码登录:")
            print(f"  二维码链接: {qrcode_url}")
            print()

            try:
                import qrcode
                qr = qrcode.QRCode(border=1)
                qr.add_data(qrcode_url)
                qr.make(fit=True)
                qr.print_ascii(tty=sys.stdout)
            except ImportError:
                print("  (未安装qrcode库，无法显示二维码，请手动打开上方链接)")

            print(f"\n  等待扫码确认... (超时120秒)")
            for i in range(120):
                time.sleep(1)
                check = parser.poll_login_status(qrcode_key)
                if check.get("success"):
                    print(f"\n  [成功] 登录成功！")
                    user_info = check.get("user_info", {})
                    if user_info.get("success"):
                        print(f"  当前账号: {user_info.get('name', '未知')}")
                    return
                if check.get("expired") or check.get("code") == 86038:
                    print(f"\n  [提示] 二维码已过期，请重新获取")
                    return
                if i % 5 == 0:
                    print(f"\r  等待中... {i}s", end="", flush=True)

            print(f"\n  [提示] 登录超时")

        except Exception as e:
            print(f"\n  [错误] {e}")

    elif choice == "2":
        print("\n  请输入B站Cookie (从浏览器获取):")
        cookie = input("  Cookie: ").strip()
        if cookie:
            try:
                parser.save_cookies(cookie)
                print("  [成功] Cookie已设置")
                user_info = parser.get_user_info()
                if user_info.get("success"):
                    print(f"  当前账号: {user_info.get('name', '未知')}")
                else:
                    print("  [警告] Cookie可能无效，请检查")
            except Exception as e:
                print(f"  [错误] {e}")
    else:
        print("  [提示] 已取消")


def do_settings():
    """设置保存路径"""
    config = get_config()
    current = get_save_path()
    print(f"\n  当前保存路径: {current}")
    new_path = input("  输入新路径 (留空取消): ").strip()
    if new_path:
        try:
            os.makedirs(new_path, exist_ok=True)
            if config:
                config.set_app_setting("default_save_path", new_path)
            print(f"  [成功] 保存路径已更新: {new_path}")
        except Exception as e:
            print(f"  [错误] 路径无效: {e}")


def main(fallback_reason=""):
    """CLI主入口"""
    global _fallback_reason
    _fallback_reason = fallback_reason

    print_banner()

    while True:
        try:
            print_menu()
            choice = input("\n  请选择功能 > ").strip()

            if choice == "1":
                do_parse()
            elif choice == "2":
                do_download_video()
            elif choice == "3":
                do_download_danmaku()
            elif choice == "4":
                do_download_cover()
            elif choice == "5":
                do_favorites()
            elif choice == "6":
                do_login()
            elif choice == "7":
                do_settings()
            elif choice == "0":
                print(f"\n  感谢使用 {APP_NAME}！\n")
                break
            else:
                print("  [提示] 无效选择，请重新输入")

        except KeyboardInterrupt:
            print(f"\n\n  感谢使用 {APP_NAME}！\n")
            break
        except Exception as e:
            print(f"\n  [错误] {e}")
            logger.error(f"CLI异常: {e}", exc_info=True)


if __name__ == "__main__":
    main()
