# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
import os
import re
import json
import time
import requests
import shutil
import subprocess

try:
    import browser_cookie3
except ImportError:
    browser_cookie3 = None



requests.packages.urllib3.disable_warnings()


class BilibiliParser:
    def __init__(self, config, cookie_path="cookie.txt"):
        self.config = config
        self.cookie_path = cookie_path
        self.cookies = {}
        self.csrf_token = ""
        self.session = requests.Session()
        self.user_info = None
        self.hevc_supported = False
        self.is_running = True

        import sys
        if hasattr(sys, '_MEIPASS'):
            self.current_dir = sys._MEIPASS
        else:
            self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.ffmpeg_local = os.path.join(self.current_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')
        self._init_session()

    def _init_session(self):
        headers = self.config.get_headers()
        self.session.headers.clear()
        self.session.headers.update(headers)

        self.cookies = self._load_cookies()
        self.session.cookies.update(self.cookies)
        self.csrf_token = self.cookies.get('bili_jct', '')

        if self.csrf_token:
            self.session.headers.update({'X-CSRF-Token': self.csrf_token})

        self.session.verify = False

    def _load_cookies(self):
        cookies = {}

        if os.path.exists(self.cookie_path):
            try:
                with open(self.cookie_path, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)

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

        if browser_cookie3:
            try:
                browser_cookies = browser_cookie3.load(domain_name='bilibili.com')
                for cookie in browser_cookies:
                    cookies[cookie.name] = cookie.value
                if cookies:
                    self.save_cookies(cookies)
            except Exception as e:
                print(f"浏览器Cookie获取失败：{str(e)}")
        else:
            print("browser_cookie3模块未安装，跳过浏览器Cookie获取")

        return cookies


    def save_cookies(self, cookies):
        try:
            if isinstance(cookies, str):
                try:
                    cookies = json.loads(cookies.strip())
                except json.JSONDecodeError:
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
                json.dump(cookie_list, f, ensure_ascii=False, indent=2)

            self.cookies = cookies
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

    def _api_request(self, url, timeout=15):
        try:
            session_no_proxy = requests.Session()
            session_no_proxy.headers.update(self.session.headers)
            session_no_proxy.cookies.update(self.session.cookies)
            session_no_proxy.verify = False
            
            resp = session_no_proxy.get(url, timeout=timeout, proxies={})
            resp.raise_for_status()
            data = resp.json()
            return True, data
        except requests.exceptions.Timeout:
            return False, {"error": "API请求超时，请检查网络连接"}
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if "ProxyError" in error_msg:
                return False, {"error": "代理错误，请检查网络设置"}
            elif "ConnectionError" in error_msg:
                return False, {"error": "连接错误，请检查网络连接"}
            else:
                return False, {"error": f"网络请求失败：{error_msg}"}
        except json.JSONDecodeError:
            return False, {"error": "API响应格式错误"}

    def verify_cookie(self):
        if not self.cookies:
            return False, "未加载任何Cookie"

        required_cookies = ['SESSDATA', 'buvid3']
        missing = [ck for ck in required_cookies if ck not in self.cookies]
        if missing:
            return False, f"缺少关键Cookie：{','.join(missing)}（登录必需）"

        api_url = self.config.get_api_url("login_status_api")
        if not api_url:
            return False, "配置错误：未找到用户信息API地址"

        success, result = self._api_request(api_url)
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

    def check_hevc_support(self):
        try:
            ffmpeg_exec = shutil.which('ffmpeg') if shutil.which('ffmpeg') else self.ffmpeg_local
            if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                self.hevc_supported = False
                return False

            cmd = [ffmpeg_exec, '-codecs']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.hevc_supported = 'hevc' in result.stdout.lower() and 'decoder' in result.stdout.lower()
            return self.hevc_supported
        except Exception as e:
            print(f"HEVC支持检测失败：{str(e)}")
            self.hevc_supported = False
            return False

    def install_hevc(self, progress_callback):
        try:
            hevc_url = self.config.get_other_url("hevc_extension_url")
            if not hevc_url:
                raise Exception("未找到HEVC扩展下载地址")

            import webbrowser
            webbrowser.open(hevc_url)
            progress_callback(100)
            return True, "已打开Microsoft Store HEVC扩展下载页面，请手动安装"
        except Exception as e:
            print(f"HEVC扩展安装失败：{str(e)}")
            return False, str(e)

    def parse_media_url(self, url):
        bv_match = re.search(r'(BV[0-9A-Za-z]{10})', url)
        if bv_match:
            return {"type": "video", "id": bv_match.group(1), "error": ""}

        ss_match = re.search(r'ss(\d+)', url, re.IGNORECASE)
        if ss_match:
            return {"type": "bangumi", "id": ss_match.group(1), "error": ""}

        av_match = re.search(r'av(\d+)', url, re.IGNORECASE)
        if av_match:
            return {"type": "av", "id": av_match.group(1), "error": ""}

        return {"type": None, "id": None, "error": "未识别的链接格式（支持BV/ss/av号）"}

    def parse_media(self, media_type, media_id, is_tv_mode=False):
        try:
            self.reset_running_status()
            
            bvid = None
            title = ""
            cid = ""
            collection = []
            bangumi_info = None

            if media_type == "av":
                av_data = self._get_av_info(media_id)
                season_id = av_data.get('season_id')
                if season_id:
                    media_type = "bangumi"
                    media_id = str(season_id)
                else:
                    media_type = "video"
                    bvid = av_data['bvid']
                    cid = av_data['cid']
                    title = self._sanitize_filename(av_data['title'])
                    collection = self._get_collection_info(bvid)

            if media_type == "video":
                if not bvid:
                    bvid = media_id
                if not cid:
                    cid = self._get_cid(media_type, bvid)
                video_info = self._get_video_main_info(bvid)
                title = self._sanitize_filename(video_info['title'])
                collection = self._get_collection_info(bvid)

            elif media_type == "bangumi":
                bangumi_full_info = self._get_bangumi_full_info(media_id)
                bangumi_info = bangumi_full_info
                season_title = bangumi_full_info['season_title']
                first_ep = bangumi_full_info['episodes'][0]
                bvid = first_ep['bvid']
                cid = first_ep['cid']
                first_ep_title = first_ep.get('ep_title', f"第1集")
                title = self._sanitize_filename(f"{season_title}_{first_ep_title}")

            play_info = self._get_play_info(media_type, bvid, cid, is_tv_mode)
            if not play_info['success']:
                raise Exception(play_info['error'])

            return {
                "success": True,
                "type": media_type,
                "title": title,
                "bvid": bvid,
                "cid": cid,
                "qualities": play_info['qualities'],
                "video_urls": play_info['video_urls'],
                "audio_url": play_info['audio_url'],
                "is_tv_mode": is_tv_mode,
                "is_vip": play_info['is_vip'],
                "has_hevc": play_info['has_hevc'],
                "collection": collection,
                "is_collection": len(collection) > 1,
                "bangumi_info": bangumi_info,
                "is_bangumi": media_type == "bangumi"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _get_av_info(self, aid):
        try:
            url = self.config.get_api_url("av_info_api").format(aid=aid)
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') != 0:
                raise Exception(f"av号信息获取失败：{data.get('message', '未知错误')}")
            return data['data']
        except Exception as e:
            raise Exception(f"av信息获取失败：{str(e)}（aid={aid}）")

    def _get_bangumi_full_info(self, ssid):
        try:
            url = self.config.get_api_url("bangumi_section_api").format(ssid=ssid)
            print(f"获取番剧信息：{url}")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Accept': 'application/json, text/plain, */*',
                'Cache-Control': 'no-cache'
            }
            params = {
                'season_id': ssid,
                'platform': 'web'
            }
            resp = self.session.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            api_data = resp.json()

            print(f"API返回码：{api_data.get('code')}")
            if api_data.get('code') != 0:
                raise Exception(f"番剧API错误：{api_data.get('message', '未知错误')}")

            result = api_data.get('result', {})
            print(f"result 包含的键：{list(result.keys())}")
            
            episodes = []
            if 'main_section' in result:
                print(f"main_section 存在")
                main_section = result['main_section']
                if 'episodes' in main_section:
                    episodes = main_section['episodes']
                    print(f"main_section.episodes 长度：{len(episodes)}")
                    if episodes:
                        print(f"第一个剧集信息：{list(episodes[0].keys())}")
            
            if not episodes and 'sections' in result:
                print(f"sections 长度：{len(result['sections'])}")
                for i, section in enumerate(result['sections']):
                    print(f"Section {i} 标题：{section.get('title')}")
                    print(f"Section {i} 类型：{section.get('type')}")
                    if 'episodes' in section:
                        print(f"Section {i} 剧集数：{len(section['episodes'])}")
                        if section['episodes']:
                            episodes = section['episodes']
                            break

            if not episodes:
                print(f"完整result字段：{json.dumps(result, ensure_ascii=False)[:500]}...")
                raise Exception("API未返回剧集数据")

            season_title = '未知番剧'
            if 'main_section' in result:
                season_title = result['main_section'].get('title', season_title)
            if season_title == '未知番剧':
                season_title = result.get('title', season_title)
            season_title = self._sanitize_filename(season_title)
            season_id = ssid

            bangumi_episodes = []
            for idx, ep in enumerate(episodes, 1):
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

                bvid = ep.get('bvid', '')
                if not bvid:
                    bvid = f"ep{ep.get('id', '')}"

                bangumi_episodes.append({
                    "ep_id": ep.get('id', ''),
                    "bvid": bvid,
                    "cid": ep.get('cid', ''),
                    "ep_index": ep_index,
                    "ep_title": self._sanitize_filename(actual_title),
                    "duration": ep.get('duration', 0),
                    "duration_str": self._format_duration(ep.get('duration', 0))
                })

            return {
                "success": True,
                "season_title": season_title,
                "season_id": season_id,
                "total_episodes": len(bangumi_episodes),
                "episodes": bangumi_episodes
            }
        except Exception as e:
            print(f"获取番剧信息失败：{str(e)}")
            raise Exception(f"番剧信息获取失败：{str(e)}")

    def _get_cid(self, media_type, media_id, page=1):
        try:
            if media_type == "video":
                url = self.config.get_api_url("cid_api").format(bvid=media_id)
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get('code') != 0:
                    raise Exception(f"视频CID获取失败：{data.get('message', '未知错误')}")
                if len(data['data']) >= page:
                    return str(data['data'][page - 1]['cid'])
                else:
                    raise Exception(f"未找到第{page}集的CID")
            elif media_type == "bangumi":
                bangumi_info = self._get_bangumi_full_info(media_id)
                if bangumi_info['episodes']:
                    return str(bangumi_info['episodes'][0]['cid'])
                raise Exception("未找到番剧CID")
            else:
                raise Exception(f"不支持的媒体类型：{media_type}")
        except Exception as e:
            raise Exception(f"CID获取失败：{str(e)}（类型={media_type}, ID={media_id}）")

    def _get_collection_info(self, bvid):
        try:
            url = self.config.get_api_url("video_info_api").format(bvid=bvid)
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') != 0:
                raise Exception(f"获取合集信息失败：{data.get('message', '未知错误')}")

            pages = data['data'].get('pages', [])
            collection = []
            for page in pages:
                duration = page.get('duration', 0)
                collection.append({
                    "page": page.get('page', 0),
                    "cid": page.get('cid', 0),
                    "title": self._sanitize_filename(page.get('part', f"第{page.get('page')}集")),
                    "duration": duration,
                    "duration_str": self._format_duration(duration)
                })
            return collection
        except Exception as e:
            print(f"获取合集信息失败：{str(e)}（bvid={bvid}）")
            return []

    def _get_video_main_info(self, bvid):
        try:
            url = self.config.get_api_url("video_info_api").format(bvid=bvid)
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') != 0:
                raise Exception(f"视频信息获取失败：{data.get('message', '未知错误')}")
            return data['data']
        except Exception as e:
            raise Exception(f"视频主信息获取失败：{str(e)}（bvid={bvid}）")

    def _get_play_info(self, media_type, bvid, cid, is_tv_mode):
        try:
            if media_type == "bangumi":
                play_url = self.config.get_api_url("bangumi_play_url_api").format(cid=cid, bvid=bvid, fnval=80)
                print(f"获取番剧播放链接：{play_url}")
            elif is_tv_mode:
                play_url = self.config.get_api_url("tv_play_url_api").format(cid=cid, bvid=bvid)
            else:
                play_url = self.config.get_api_url("play_url_api").format(cid=cid, bvid=bvid, fnval=80)

            resp = self.session.get(play_url, timeout=15)
            resp.raise_for_status()
            play_data = resp.json()

            print(f"播放链接API返回码：{play_data.get('code')}")
            if play_data.get('code') != 0:
                error_msg = play_data.get('message', '权限不足')
                if play_data.get('code') == 403:
                    error_msg += "（可能是Cookie失效或无对应画质权限）"
                print(f"播放链接API错误：{error_msg}")
                if media_type == "bangumi":
                    return {
                        "success": True,
                        "qualities": [(80, "1080P")],
                        "video_urls": {80: ""},
                        "audio_url": "",
                        "is_vip": False,
                        "has_hevc": False
                    }
                raise Exception(error_msg)

            qualities = []
            video_urls = {}
            audio_url = ""
            is_vip = self.user_info.get('is_vip', False) if self.user_info else False
            has_hevc = False
            quality_map = self.config.get_quality_map()

            data_source = play_data.get('data', play_data.get('result', {}))

            if 'dash' in data_source:
                if 'audio' in data_source['dash']:
                    audio_url = data_source['dash']['audio'][0]['baseUrl']

                for video in data_source['dash']['video']:
                    qn = video.get('id', 0)
                    quality_name = quality_map.get(qn, f"未知画质({qn})")

                    if qn in [125, 127]:
                        has_hevc = True
                        quality_name += " (HEVC)"

                    if qn in [112, 120, 125, 127] and not is_vip:
                        continue

                    video_urls[qn] = video['baseUrl']
                    qualities.append((qn, quality_name))

            elif 'durl' in data_source:
                for durl in data_source['durl']:
                    qn = durl.get('quality', 0)
                    quality_name = quality_map.get(qn, f"未知画质({qn})")

                    if qn in [125, 127]:
                        has_hevc = True
                        quality_name += " (HEVC)"

                    if qn in [112, 120, 125, 127] and not is_vip:
                        continue

                    video_urls[qn] = durl['url']
                    qualities.append((qn, quality_name))

            qualities = list(dict.fromkeys(qualities))
            qualities.sort(key=lambda x: x[0], reverse=True)

            return {
                "success": True,
                "qualities": qualities,
                "video_urls": video_urls,
                "audio_url": audio_url,
                "is_vip": is_vip,
                "has_hevc": has_hevc
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_single_episode_info(self, media_type, media_id, page=1, is_tv_mode=False):
        try:
            bvid = media_id if media_type == "video" else None
            cid = self._get_cid(media_type, media_id, page) if media_type == "video" else None

            if media_type == "video":
                if not bvid:
                    raise Exception("视频ID（BV号）为空")
                collection = self._get_collection_info(bvid)
                ep_title = next((item['title'] for item in collection if item['page'] == page), f"第{page}集")
                main_title = self._get_video_main_info(bvid)['title']
                full_title = f"{main_title}_{ep_title}"

            elif media_type == "bangumi":
                return {"success": False, "error": "番剧单集信息请通过get_bangumi_episode_playinfo获取"}
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
                "has_hevc": play_info['has_hevc']
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "page": page
            }

    def get_bangumi_episode_playinfo(self, bvid, cid, quality=80):
        try:
            play_url = self.config.get_api_url("bangumi_play_url_api").format(cid=cid, bvid=bvid, fnval=80)
            resp = self.session.get(play_url, timeout=15)
            resp.raise_for_status()
            data = resp.json()

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

    def download_file(self, url, save_dir, progress_callback, file_type="video", bvid=None):
        if not self.is_running:
            raise Exception("下载已被取消")

        os.makedirs(save_dir, exist_ok=True)

        temp_filename = f"temp_{file_type}_{hash(url)}_{int(time.time())}.m4s"
        temp_path = os.path.join(save_dir, temp_filename)
        downloaded_size = 0

        try:
            download_headers = self.config.get_headers().copy()
            if bvid:
                download_headers['Referer'] = f"https://www.bilibili.com/video/{bvid}/"

            if os.path.exists(temp_path):
                downloaded_size = os.path.getsize(temp_path)
                headers = download_headers.copy()
                headers['Range'] = f'bytes={downloaded_size}-'
                resp = self.session.get(url, stream=True, timeout=30, headers=headers)

                if resp.status_code == 416:
                    progress_callback(100, downloaded_size)
                    return temp_path
            else:
                resp = self.session.get(url, stream=True, timeout=30, headers=download_headers)

            resp.raise_for_status()
            total_size = int(resp.headers.get('content-length', 0))
            if 'content-range' in resp.headers:
                total_size = int(resp.headers['content-range'].split('/')[-1])

            mode = 'ab' if downloaded_size > 0 else 'wb'
            with open(temp_path, mode) as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not self.is_running:
                        raise Exception("下载已取消")
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = int((downloaded_size / total_size) * 100) if total_size > 0 else 0
                        progress_callback(progress, downloaded_size)

            return temp_path
        except Exception as e:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as clean_e:
                    print(f"清理临时文件失败：{clean_e}")
            raise Exception(f"{file_type}下载失败：{str(e)}")

    def merge_media(self, video_path, audio_path, output_path):
        from logger_config import logger
        try:
            logger.debug(f"开始合并音视频：视频={video_path}, 音频={audio_path}, 输出={output_path}")
            
            ffmpeg_exec = shutil.which('ffmpeg')
            logger.debug(f"系统环境变量中的ffmpeg路径：{ffmpeg_exec}")
            
            if not ffmpeg_exec or not os.path.exists(ffmpeg_exec):
                ffmpeg_exec = self.ffmpeg_local
                logger.debug(f"本地ffmpeg路径：{ffmpeg_exec}")
                if not os.path.exists(ffmpeg_exec):
                    logger.error(f"未找到ffmpeg！本地路径不存在：{ffmpeg_exec}")
                    raise Exception("未找到ffmpeg！请安装并添加到系统环境变量，或放在./ffmpeg/bin目录下")

            logger.debug(f"使用的ffmpeg路径：{ffmpeg_exec}")
            
            cmd = [
                ffmpeg_exec,
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-loglevel', 'error',
                '-y',
                output_path
            ]

            logger.debug(f"执行ffmpeg命令：{' '.join(cmd)}")
            
            try:
                result = subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='ignore',
                    shell=False
                )
                logger.debug(f"ffmpeg执行成功，返回码：{result.returncode}")
            except OSError as e:
                logger.error(f"执行ffmpeg时发生系统错误：{str(e)}")
                logger.error(f"命令：{' '.join(cmd)}")
                logger.error(f"当前工作目录：{os.getcwd()}")
                logger.error(f"ffmpeg路径是否存在：{os.path.exists(ffmpeg_exec)}")
                logger.error(f"ffmpeg是否可执行：{os.access(ffmpeg_exec, os.X_OK)}")
                logger.error(f"视频文件是否存在：{os.path.exists(video_path)}")
                logger.error(f"音频文件是否存在：{os.path.exists(audio_path)}")
                
                try:
                    logger.info("尝试使用shell=True执行ffmpeg命令")
                    cmd_str = ' '.join(cmd)
                    logger.debug(f"执行命令：{cmd_str}")
                    result = subprocess.run(
                        cmd_str,
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.PIPE,
                        text=True,
                        encoding='utf-8',
                        errors='ignore',
                        shell=True
                    )
                    logger.debug(f"ffmpeg执行成功，返回码：{result.returncode}")
                except Exception as shell_e:
                    logger.error(f"使用shell=True执行也失败：{str(shell_e)}")
                    raise
            
            for temp_file in [video_path, audio_path]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                        logger.debug(f"清理临时文件成功：{temp_file}")
                    except Exception as e:
                        logger.warning(f"清理临时文件失败：{temp_file} - {str(e)}")

            logger.debug(f"音视频合并完成：{output_path}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg执行失败：返回码={e.returncode}, 标准错误={e.stderr}, 标准输出={e.stdout}")
            raise Exception(f"ffmpeg执行失败：{e.stderr}")
        except Exception as e:
            logger.error(f"音视频合并失败：{str(e)}", exc_info=True)
            raise Exception(f"音视频合并失败：{str(e)}")

    def stop_download(self):
        self.is_running = False

    def reset_running_status(self):
        self.is_running = True

    @staticmethod
    def _sanitize_filename(filename):
        invalid_chars = r'[\/:*?"<>|]'
        return re.sub(invalid_chars, '_', filename).strip()

    @staticmethod
    def _format_duration(seconds):
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"