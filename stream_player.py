# -*- coding: utf-8 -*-
"""
流媒体播放器工具（独立弹窗）
方案：ffplay + SetParent 嵌入 + 持续尺寸校正
- ffplay 启动后通过 Win32 API 嵌入到 Qt 容器中
- 定时器持续校正窗口尺寸确保填满容器
- 支持B站直播m3u8、央视频等HLS/FLV流
"""

import os
import sys
import time
import json
import logging
import subprocess
import threading
import re
import urllib.parse
from datetime import datetime

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QProgressBar, QFileDialog, QMessageBox, QDialog, QFrame, QSizePolicy,
    QSystemTrayIcon, QMenu, QTextEdit, QAction
)

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except Exception as e:
    HAS_WEBENGINE = False
    print(f"[stream_player] WebEngine import failed: {e}", file=sys.stderr)

try:
    from platform_utils import IS_WINDOWS, exe, subprocess_no_window_kwargs, subprocess_low_priority_kwargs
except ImportError:
    IS_WINDOWS = True
    def exe(n): return n + ('.exe' if os.name == 'nt' else '')
    def subprocess_no_window_kwargs(): return {}
    def subprocess_low_priority_kwargs(): return {}

logger = logging.getLogger(__name__)

try:
    from ui import scale, scale_style
except ImportError:
    def scale(v): return int(v)
    def scale_style(s): return re.sub(r'(\d+)px', lambda m: str(int(m.group(1))) + 'px', s)

try:
    from live_tab import LiveRecordThread
except ImportError:
    LiveRecordThread = None


def _find_ffmpeg():
    if getattr(sys, 'frozen', False) or hasattr(sys, '_MEIPASS'):
        base = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else sys._MEIPASS
        for d in [os.path.join(base, '_internal', 'ffmpeg'), os.path.join(base, 'ffmpeg'),
                  os.path.join(base, '_internal', 'ffmpeg', 'bin'), os.path.join(base, 'ffmpeg', 'bin'),
                  os.path.join(base, '_internal')]:
            p = os.path.join(d, exe('ffmpeg'))
            if os.path.exists(p): return p
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for d in [os.path.join(script_dir, 'ffmpeg'), os.path.join(script_dir, 'ffmpeg', 'bin'), script_dir]:
        p = os.path.join(d, exe('ffmpeg'))
        if os.path.exists(p): return p
    import shutil
    return shutil.which('ffmpeg')


def _detect_stream_format(url):
    lower = url.lower()
    if '.m3u8' in lower or 'm3u8' in url: return 'HLS'
    if '.mp4' in lower: return 'MP4'
    return 'FLV'


_JS_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_cache')


def _get_js_content(name, cdn_url):
    """下载/读取缓存JS库"""
    cache_path = os.path.join(_JS_CACHE_DIR, name)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            pass
    try:
        os.makedirs(_JS_CACHE_DIR, exist_ok=True)
        import requests
        resp = requests.get(cdn_url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200 and len(resp.content) > 1000:
            content = resp.text
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"{name} 缓存成功 ({len(content)} bytes)")
            return content
    except Exception as e:
        logger.warning(f"{name} 下载失败: {e}")
    return None


_codec_probe_done = False

def _probe_stream_codec(url):
    """用 ffprobe 探测首个 ts 片段的编码格式"""
    global _codec_probe_done
    if _codec_probe_done:
        return
    _codec_probe_done = True
    try:
        import subprocess
        import shutil
        ffprobe = shutil.which('ffprobe')
        if not ffprobe:
            ffmpeg_path = shutil.which('ffmpeg')
            if ffmpeg_path:
                ffprobe = os.path.join(os.path.dirname(ffmpeg_path), 'ffprobe.exe')
                if not os.path.exists(ffprobe):
                    ffprobe = None
        if not ffprobe:
            logger.warning('[StreamProxy] 未找到 ffprobe，无法探测编码')
            return
        cmd = [ffprobe, '-v', 'error',
               '-show_entries', 'stream=codec_name,width,height,pix_fmt,sample_rate,channels',
               '-of', 'default=noprint_wrappers=1', url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15,
                           **subprocess_no_window_kwargs())
        logger.info(f'[StreamProxy] ffprobe 流信息:\n{r.stdout}')
        if r.stderr:
            logger.info(f'[StreamProxy] ffprobe stderr:\n{r.stderr}')
    except Exception as e:
        logger.warning(f'[StreamProxy] ffprobe 探测失败: {e}')

class _ProxyServer(threading.Thread):
    """
    HTTP代理：
    - /           返回播放器HTML页面
    - /proxy?url= 代理转发任意URL（加CORS头）
    - /stream     返回当前设置的流URL（fMP4管道流，用于下载）
    - /hls        ffmpeg 实时转码为标准 m3u8+ts，供 hls.js 播放
    - /hls/*.ts   ts 分片文件
    """

    def __init__(self):
        super().__init__(daemon=True)
        self.httpd = None
        self.port = None
        self._stream_url = ""
        self._html = ""
        self._running = True
        self._transcode = [False]
        self._hls_dir = None
        self._hls_proc = None
        self._hls_url = ""

    def set_stream_url(self, url):
        self._stream_url = url

    def set_html(self, html):
        self._html = html

    def enable_transcode(self):
        self._transcode[0] = True

    def start_hls(self, url):
        import tempfile
        self.stop_hls()
        self._hls_dir = tempfile.mkdtemp(prefix='stream_hls_')
        self._hls_url = url
        logger.info(f"[StreamProxy/HLS] 启动转码: {url[:80]}... → {self._hls_dir}")
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            logger.error("[StreamProxy/HLS] ffmpeg 未找到")
            return
        cmd = [
            ffmpeg_path, '-y',
            '-fflags', '+genpts+discardcorrupt',
            '-reconnect', '1', '-reconnect_streamed', '1',
            '-reconnect_delay_max', '30',
            '-i', url,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
            '-vf', 'scale=min(1280\\,iw):-2',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2',
            '-f', 'hls',
            '-hls_time', '2',
            '-hls_list_size', '5',
            '-hls_flags', 'delete+append_list+temp_file',
            '-hls_segment_type', 'mpegts',
            '-hls_segment_filename', os.path.join(self._hls_dir, 'segment_%03d.ts'),
            os.path.join(self._hls_dir, 'index.m3u8'),
        ]
        logger.info(f"[StreamProxy/HLS] ffmpeg: {' '.join(cmd[:15])} ...")
        import subprocess
        self._hls_proc = subprocess.Popen(
            cmd,
            stderr=subprocess.PIPE,
            bufsize=8192,
            **subprocess_low_priority_kwargs()
        )
        def _log_stderr():
            try:
                for line in iter(self._hls_proc.stderr.readline, b''):
                    if not line:
                        break
                    s = line.decode('utf-8', errors='replace').strip()
                    if s:
                        logger.info(f'[StreamProxy/HLS/ffmpeg] {s}')
            except Exception:
                pass
        threading.Thread(target=_log_stderr, daemon=True).start()
        if self.httpd:
            try:
                self.httpd.RequestHandlerClass.set_hls_dir(self._hls_dir)
            except Exception:
                pass

    def stop_hls(self):
        if self._hls_proc:
            try:
                self._hls_proc.terminate()
                self._hls_proc.wait(timeout=3)
            except Exception:
                try:
                    self._hls_proc.kill()
                except Exception:
                    pass
            self._hls_proc = None
        if self._hls_dir and os.path.isdir(self._hls_dir):
            try:
                import shutil
                shutil.rmtree(self._hls_dir, ignore_errors=True)
            except Exception:
                pass
            self._hls_dir = None
        self._hls_url = ""

    def run(self):
        import http.server
        import requests

        stream_url_ref = [self._stream_url]
        html_ref = [self._html]
        running_ref = [True]
        transcode_ref = self._transcode
        hls_dir_ref = [None]
        hls_url_ref = [""]
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://live.bilibili.com/',
            'Origin': 'https://live.bilibili.com',
        })

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def _client_disconnected(self, e):
                if isinstance(e, ConnectionResetError):
                    return True
                msg = str(e).lower()
                for code in ('10053', '10054', '10055', 'broken pipe', 'an existing connection was forcibly closed'):
                    if code in msg:
                        return True
                return False

            def do_GET(self):
                path = self.path.split('?')[0]
                try:
                    if path == '/':
                        self._serve_page(html_ref[0])
                    elif path == '/proxy':
                        query = urllib.parse.parse_qs(self.path.split('?', 1)[1]) if '?' in self.path else {}
                        url = query.get('url', [''])[0]
                        self._proxy(url)
                    elif path == '/stream':
                        self._serve_stream(stream_url_ref[0], transcode_ref[0])
                    elif path == '/hls' or path.startswith('/hls/'):
                        self._serve_hls(path)
                    elif path == '/log':
                        self._serve_log()
                    elif path == '/favicon.ico':
                        self.send_response(204)
                        self.end_headers()
                    else:
                        self.send_error(404)
                except Exception as e:
                    if not self._client_disconnected(e):
                        logger.warning(f"代理错误 {path}: {e}")
                    try:
                        self.send_response(500)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(str(e).encode())
                    except Exception:
                        pass

            def _serve_page(self, html):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(html.encode('utf-8'))

            def _serve_log(self):
                try:
                    query = urllib.parse.parse_qs(self.path.split('?', 1)[1]) if '?' in self.path else {}
                    msg = query.get('msg', [''])[0]
                    if not msg:
                        length = int(self.headers.get('Content-Length', 0))
                        if length > 0 and length < 8192:
                            msg = self.rfile.read(length).decode('utf-8', errors='replace')
                    if msg:
                        logger.info(f'[JS] {msg}')
                except Exception:
                    pass
                self.send_response(204)
                self.end_headers()

            def _serve_stream(self, url):
                if not url:
                    self.send_error(400, "missing url")
                    return
                try:
                    ffmpeg_path = _find_ffmpeg()
                    if not ffmpeg_path or not os.path.exists(ffmpeg_path):
                        self.send_error(500, "ffmpeg not found")
                        return
                    if transcode_ref[0]:
                        cmd = [
                            ffmpeg_path, '-y',
                            '-fflags', '+genpts+discardcorrupt',
                            '-reconnect', '1', '-reconnect_streamed', '1',
                            '-reconnect_delay_max', '30',
                            '-i', url,
                            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency',
                            '-c:a', 'aac', '-b:a', '128k',
                            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                            '-f', 'mp4',
                            'pipe:1'
                        ]
                    else:
                        cmd = [
                            ffmpeg_path, '-y',
                            '-fflags', '+genpts+discardcorrupt',
                            '-reconnect', '1', '-reconnect_streamed', '1', '-reconnect_delay_max', '30',
                            '-i', url,
                            '-c', 'copy',
                            '-bsf:a', 'aac_adtstoasc',
                            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
                            '-f', 'mp4',
                            'pipe:1'
                        ]
                    logger.info(f"[StreamProxy] ffmpeg cmd: {' '.join(cmd[:14])} ...")
                    import subprocess
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=8192,
                        **subprocess_low_priority_kwargs()
                    )
                    import queue
                    out_q = queue.Queue(maxsize=200)
                    def read_stdout():
                        try:
                            while True:
                                chunk = proc.stdout.read(32768)
                                if not chunk:
                                    break
                                try:
                                    out_q.put(chunk, timeout=1)
                                except queue.Full:
                                    break
                        except Exception:
                            pass
                    def read_stderr():
                        try:
                            for line in iter(proc.stderr.readline, b''):
                                if not line:
                                    break
                                s = line.decode('utf-8', errors='replace').strip()
                                if s:
                                    logger.info(f'[StreamProxy/ffmpeg] {s}')
                        except Exception:
                            pass
                    threading.Thread(target=read_stdout, daemon=True).start()
                    threading.Thread(target=read_stderr, daemon=True).start()

                    first_chunk = None
                    for _ in range(80):
                        if proc.poll() is not None:
                            break
                        try:
                            first_chunk = out_q.get(timeout=0.1)
                            break
                        except queue.Empty:
                            continue
                    if first_chunk is None and proc.poll() is not None:
                        logger.warning(f'[StreamProxy] ffmpeg 提前退出(ret={proc.returncode})')
                        self.send_error(502, 'ffmpeg failed')
                        return
                    if first_chunk is None:
                        logger.warning('[StreamProxy] ffmpeg 8秒内无输出')
                        self.send_error(502, 'ffmpeg timeout')
                        proc.terminate()
                        return

                    self.send_response(200)
                    self.send_header('Content-Type', 'video/mp4')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(first_chunk)
                    self.wfile.flush()
                    total = len(first_chunk)

                    while running_ref[0] and proc.poll() is None:
                        try:
                            chunk = out_q.get(timeout=1)
                            self.wfile.write(chunk)
                            self.wfile.flush()
                            total += len(chunk)
                        except queue.Empty:
                            continue
                        except Exception as e:
                            if not self._client_disconnected(e):
                                logger.warning(f'[StreamProxy] 传输中断: {e}')
                            break
                    logger.info(f'[StreamProxy] 流完成: {total} bytes')
                    try:
                        proc.terminate()
                        proc.wait(timeout=2)
                    except Exception:
                        pass
                except Exception as e:
                    if not self._client_disconnected(e):
                        logger.warning(f"m3u8代理失败: {e}")
                    try:
                        self.send_response(502)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(str(e).encode())
                    except Exception:
                        pass

            def _serve_hls(self, path):
                hls_dir = hls_dir_ref[0]
                if not hls_dir or not os.path.isdir(hls_dir):
                    self.send_error(503, "HLS not started")
                    return
                if path == '/hls':
                    m3u8_path = os.path.join(hls_dir, 'index.m3u8')
                    if not os.path.exists(m3u8_path):
                        for _ in range(20):
                            time.sleep(0.25)
                            if os.path.exists(m3u8_path):
                                break
                        else:
                            self.send_error(504, "HLS not ready")
                            return
                    try:
                        with open(m3u8_path, 'rb') as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/vnd.apple.mpegurl; charset=utf-8')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        self.wfile.write(data)
                    except Exception as e:
                        logger.warning(f"[StreamProxy/HLS] m3u8 读取失败: {e}")
                        self.send_error(500, str(e))
                else:
                    filename = path.split('/', 2)[-1] if len(path.split('/')) > 2 else ''
                    if not filename or '..' in filename:
                        self.send_error(400, "bad request")
                        return
                    filepath = os.path.join(hls_dir, filename)
                    if not os.path.exists(filepath):
                        self.send_error(404, "segment not found")
                        return
                    try:
                        with open(filepath, 'rb') as f:
                            data = f.read()
                        self.send_response(200)
                        self.send_header('Content-Type', 'video/mp2t')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        self.wfile.write(data)
                    except Exception as e:
                        logger.warning(f"[StreamProxy/HLS] ts 读取失败({filename}): {e}")
                        self.send_error(500, str(e))

            def _proxy(self, url):
                if not url:
                    self.send_error(400, "missing url")
                    return
                try:
                    logger.info(f"[StreamProxy] 代理请求: {url[:120]}...")
                    with session.get(url, timeout=15, stream=True) as r:
                        r.raise_for_status()
                        ct = r.headers.get('Content-Type', 'application/octet-stream')
                        cl = r.headers.get('Content-Length')
                        logger.info(f"[StreamProxy] 代理响应: CT={ct}, CL={cl}")
                        self.send_response(200)
                        self.send_header('Content-Type', ct)
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        total = 0
                        first = True
                        for chunk in r.iter_content(chunk_size=32768):
                            if not chunk:
                                continue
                            if not running_ref[0]:
                                break
                            if first:
                                first = False
                                logger.info(f"[StreamProxy] 首包hex={chunk[:16].hex()}")
                            self.wfile.write(chunk)
                            self.wfile.flush()
                            total += len(chunk)
                        logger.info(f"[StreamProxy] 代理完成: {total} bytes")
                except Exception as e:
                    if not self._client_disconnected(e):
                        logger.warning(f"代理请求失败: {e}")
                    try:
                        self.send_response(502)
                        self.send_header('Content-Type', 'text/plain')
                        self.end_headers()
                        self.wfile.write(str(e).encode())
                    except Exception:
                        pass

        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.port = self.httpd.server_address[1]
        Handler.set_stream = lambda u: stream_url_ref.__setitem__(0, u)
        Handler.set_html = lambda h: html_ref.__setitem__(0, h)
        Handler.stop_server = lambda: running_ref.__setitem__(0, False)
        Handler.set_hls_dir = lambda d: hls_dir_ref.__setitem__(0, d)
        logger.info(f"[StreamProxy] 启动于 127.0.0.1:{self.port}")
        self.httpd.serve_forever()

    def update_url(self, url):
        self._stream_url = url
        if self.httpd:
            self.httpd.RequestHandlerClass.set_stream(url)

    def stop(self):
        self._running = False
        self.stop_hls()
        if self.httpd:
            try:
                self.httpd.shutdown()
            except Exception:
                pass


def _build_player_html(hls_js_code):
    css = """*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;background:#000;overflow:hidden;font-family:sans-serif}
#wrap{display:flex;flex-direction:column;width:100%;height:100%}
video{flex:1;width:100%;background:#000}
#bar{display:flex;align-items:center;padding:6px 12px;background:#222;color:#ccc;font-size:12px;gap:12px}
#bar span{white-space:nowrap}"""

    html = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stream Player</title>
<style>""" + css + """</style></head>
<body>
<div id="wrap">
<video id="v" controls autoplay muted playsinline src="/stream"></video>
<div id="bar">
<span id="st">Loading...</span>
<span id="fmt">fMP4</span>
<span id="dbg" style="color:#888;display:none"></span>
<span id="err" style="color:#ff4444;display:none"></span>
</div></div>
<script>
var v=document.getElementById('v'),st=document.getElementById('st'),
    fmt=document.getElementById('fmt'),dbg=document.getElementById('dbg'),
    err=document.getElementById('err');
function sendToServer(m){
 try{var img=new Image();img.src='/log?msg='+encodeURIComponent(String(m).substring(0,512));}catch(e){}
}
function log(m){var s=String(m);dbg.textContent=s;dbg.style.display='inline';console.log(s);sendToServer(s);}
function showErr(m){err.textContent=m;err.style.display='inline';st.textContent='Error';log('ERROR: '+m);}
function describeVideoError(){
 var c=v.error?v.error.code:-1;
 var msgs=['','MEDIA_ERR_ABORTED','MEDIA_ERR_NETWORK','MEDIA_ERR_DECODE','MEDIA_ERR_SRC_NOT_SUPPORTED'];
 return 'VideoError code='+c+' '+(msgs[c]||'');
}
log('UA='+navigator.userAgent);
v.addEventListener('loadstart',function(){st.textContent='Loading...';});
v.addEventListener('loadedmetadata',function(){st.textContent='Ready';try{v.play();}catch(e){}});
v.addEventListener('playing',function(){st.textContent='Playing';});
v.addEventListener('waiting',function(){st.textContent='Buffering...';});
v.addEventListener('canplay',function(){st.textContent='Can play';});
v.addEventListener('error',function(){showErr(describeVideoError());});
v.addEventListener('stalled',function(){log('stalled');});
setTimeout(function(){try{v.play();}catch(e){}},500);
</script></body></html>"""
    return html


class StreamDownloadThread(QThread):
    progress_updated = pyqtSignal(int, str)
    download_finished = pyqtSignal(bool, str)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, output_path, format_type="hls"):
        super().__init__()
        self.url = url
        self.output_path = output_path
        self.format_type = format_type
        self._stop_flag = False

    def run(self):
        ffmpeg_path = _find_ffmpeg()
        if not ffmpeg_path or not os.path.exists(ffmpeg_path):
            self.error_occurred.emit("未找到 ffmpeg"); return
        try:
            cmd = [ffmpeg_path, '-y']
            if self.format_type == "hls":
                cmd += ['-protocol_whitelist', 'concat,file,http,https,tcp,tls,crypto', '-i', self.url]
            else:
                cmd += ['-i', self.url]
            cmd += ['-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-movflags', '+faststart', self.output_path]
            self.progress_updated.emit(0, "连接中...")
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **subprocess_low_priority_kwargs())
            t0 = time.time(); total_dur = 0
            for line in iter(self.process.stdout.readline, b''):
                if self._stop_flag: break
                lt = line.decode('utf-8', errors='ignore').strip()
                if not lt: continue
                dm = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', lt)
                if dm: total_dur = int(dm.group(1))*3600+int(dm.group(2))*60+float(dm.group(3))
                tm = re.search(r'time=(\d+):(\d+):(\d+\.\d+)', lt)
                if tm:
                    cur = int(tm.group(1))*3600+int(tm.group(2))*60+float(tm.group(3))
                    if total_dur > 0:
                        pct = min(int(cur*100/total_dur), 99)
                        sp = re.search(r'speed=\s*([\d.]+)', lt)
                        self.progress_updated.emit(pct, f"{pct}% {sp.group(1)+'x' if sp else ''}")
                    else:
                        m, s = divmod(int(cur), 60)
                        self.progress_updated.emit(-1, f"录制 {m:02d}:{s:02d}")
            if self._stop_flag:
                if self.process.poll() is None: self.process.terminate()
                self.download_finished.emit(True, f"已停止 ({int(time.time()-t0)}s)")
            else:
                ret = self.process.wait()
                self.download_finished.emit(ret == 0, f"{'完成' if ret==0 else f'异常({ret})'} ({int(time.time()-t0)}s)")
        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self): self._stop_flag = True


class StreamPlayerDialog(QDialog):
    """ffplay 嵌入式流媒体播放器"""

    _dl_progress_sig = pyqtSignal(int, str)
    _dl_done_sig = pyqtSignal(bool, str)
    _dl_err_sig = pyqtSignal(str)
    _record_status_sig = pyqtSignal(str)

    def __init__(self, config=None, parent=None, initial_url=""):
        super().__init__(parent)
        self.config = config
        self.parent_window = parent
        self.download_thread = None
        self._current_url = initial_url
        self._player_proc = None
        self._player_type = ''
        self._container = None
        self._resize_timer = None
        self._embed_try = 0
        self._stream_info = {}  # 存储从mpv日志解析的流数据
        self._lua_script_path = None  # Lua脚本临时文件路径

        self._setup_win()
        self._init_ui()

        self._dl_progress_sig.connect(self._on_dl_progress)
        self._dl_done_sig.connect(self._on_dl_done)
        self._dl_err_sig.connect(self._on_dl_err)
        self._record_status_sig.connect(self._on_record_status)

        if initial_url:
            self.url_input.setText(initial_url)
            QTimer.singleShot(500, lambda: self._do_play())

    def _setup_win(self):
        self.setWindowTitle("流媒体播放器")
        self.setMinimumSize(scale(850), scale(600))
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setWindowModality(Qt.NonModal)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 工具栏
        toolbar = QFrame()
        toolbar.setStyleSheet(scale_style("QFrame{background:white;border-radius:4px;padding:2px}"))
        tl = QHBoxLayout(toolbar); tl.setSpacing(6); tl.setContentsMargins(8, 4, 8, 4)
        tl.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入流媒体地址（支持B站直播m3u8等）")
        self.url_input.returnPressed.connect(self._do_play)
        tl.addWidget(self.url_input, stretch=1)

        self.play_btn = QPushButton("播放")
        self.play_btn.setStyleSheet(scale_style("padding:5px 18px;background:#00a1d6;color:white;border:none;border-radius:4px;font-weight:bold;"))
        self.play_btn.clicked.connect(self._do_play)
        tl.addWidget(self.play_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setStyleSheet(scale_style("padding:5px 14px;background:#dc3545;color:white;border:none;border-radius:4px;"))
        self.stop_btn.clicked.connect(self._stop_play)
        tl.addWidget(self.stop_btn)

        self.ext_btn = QPushButton("外部播放")
        self.ext_btn.setStyleSheet(scale_style("padding:5px 14px;background:#6c757d;color:white;border:none;border-radius:4px;"))
        self.ext_btn.clicked.connect(self._open_external)
        tl.addWidget(self.ext_btn)

        self.dl_video_btn = QPushButton("下载画面")
        self.dl_video_btn.setStyleSheet(scale_style("padding:5px 14px;background:#17a2b8;color:white;border:none;border-radius:4px;"))
        self.dl_video_btn.clicked.connect(lambda: self._do_download(2))
        tl.addWidget(self.dl_video_btn)

        self.dl_audio_btn = QPushButton("下载音频")
        self.dl_audio_btn.setStyleSheet(scale_style("padding:5px 14px;background:#fd7e14;color:white;border:none;border-radius:4px;"))
        self.dl_audio_btn.clicked.connect(lambda: self._do_download(1))
        tl.addWidget(self.dl_audio_btn)

        self.dl_btn = QPushButton("下载完整视频")
        self.dl_btn.setStyleSheet(scale_style("padding:5px 14px;background:#28a745;color:white;border:none;border-radius:4px;"))
        self.dl_btn.clicked.connect(lambda: self._do_download(0))
        tl.addWidget(self.dl_btn)
        main_layout.addWidget(toolbar)

        # 播放容器（黑色背景，mpv 嵌入到这里）
        self._player_frame = QFrame()
        self._player_frame.setStyleSheet(scale_style("QFrame{background:#000;border-radius:4px;}"))
        pl = QVBoxLayout(self._player_frame); pl.setContentsMargins(0, 0, 0, 0)
        self._container = QWidget()
        self._container.setStyleSheet("background:#000;")
        self._container.setContextMenuPolicy(Qt.CustomContextMenu)
        self._container.customContextMenuRequested.connect(self._show_stream_info_menu)
        pl.addWidget(self._container, stretch=1)
        self._player_frame.setMinimumSize(scale(400), scale(280))
        main_layout.addWidget(self._player_frame, stretch=1)

        # 状态栏
        sb = QHBoxLayout()
        self.status_label = QLabel("就绪 (mpv 内嵌)")
        self.status_label.setStyleSheet("font-size:12px;color:#666;")
        sb.addWidget(self.status_label)
        sb.addStretch()
        self.format_label = QLabel("-")
        self.format_label.setStyleSheet("font-size:11px;color:#999;")
        sb.addWidget(self.format_label)
        self.dl_bar = QProgressBar()
        self.dl_bar.setRange(0, 100); self.dl_bar.setValue(0)
        self.dl_bar.setMaximumWidth(scale(180)); self.dl_bar.setMaximumHeight(scale(16)); self.dl_bar.hide()
        sb.addWidget(self.dl_bar)
        main_layout.addLayout(sb)

        if self._current_url:
            self.url_input.setText(self._current_url)

    def _do_play(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入URL"); return
        self._current_url = url
        self.show(); self.raise_(); self.activateWindow()
        QTimer.singleShot(600, lambda: self._start_player(url))

    def _start_player(self, url):
        """优先 mpv（--wid 原生嵌入），回退 ffplay（外部窗口）"""
        self._stop_play()
        self._stream_info = {}  # 重置流数据

        fmt = _detect_stream_format(url)
        self.format_label.setText(fmt)

        # 确保容器背景为黑色（避免透明背景导致嵌入异常）
        if self._container:
            self._container.setStyleSheet("background:#000;")

        # 强制 layout 完成，确保容器可见且有尺寸
        from PyQt5.QtWidgets import QApplication
        for _ in range(6):
            QApplication.processEvents()
            self.repaint()
            QApplication.processEvents()

        # 1) 尝试 mpv
        mpv_exe = self._find_mpv()
        if mpv_exe and os.path.exists(mpv_exe):
            logger.info(f"使用 mpv 播放: {mpv_exe}")
            self._play_mpv(url, mpv_exe)
            return

        # 2) 回退 ffplay
        logger.info("未找到 mpv，回退 ffplay")
        self._play_ffplay_fallback(url)

    # 用于外部设置刷新URL的回调（live_tab 调用 set_url_refresher）
    _url_refresher = None

    def set_url_refresher(self, callback):
        """设置刷新直播流URL的回调函数。callback() 返回最新URL或None"""
        self._url_refresher = callback

    def _get_fresh_url(self):
        """获取最新的直播流URL（优先用回调刷新）"""
        if self._url_refresher:
            try:
                fresh = self._url_refresher()
                if fresh:
                    logger.info(f"[播放] 刷新到新URL: {fresh[:80]}")
                    return fresh
            except Exception as e:
                logger.warning(f"[播放] 刷新URL失败: {e}")
        return self._current_url

    def _find_mpv(self):
        """查找 mpv.exe"""
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for d in [os.path.join(script_dir, 'mpv'),
                  os.path.join(script_dir, 'ffmpeg')]:
            p = os.path.join(d, exe('mpv'))
            if os.path.exists(p): return p
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
            for d in [base, os.path.join(base, '_internal'), os.path.join(base, 'mpv')]:
                p = os.path.join(d, exe('mpv'))
                if os.path.exists(p): return p
        import shutil
        return shutil.which('mpv') or shutil.which(exe('mpv'))

    def _play_mpv(self, url, mpv_exe, retry_count=0):
        """mpv --wid 嵌入播放（自动刷新URL + 失败重试）"""
        play_url = self._get_fresh_url() if retry_count > 0 else url

        # 验证容器是否就绪
        if not self._container or not self._container.isVisible():
            logger.warning("[mpv] 容器未就绪，延迟启动")
            QTimer.singleShot(200, lambda: self._play_mpv(url, mpv_exe, retry_count))
            return

        # 确保容器有有效尺寸
        sz = self._container.size()
        if sz.width() <= 10 or sz.height() <= 10:
            logger.warning(f"[mpv] 容器尺寸太小({sz.width()}x{sz.height()})，延迟启动")
            QTimer.singleShot(200, lambda: self._play_mpv(url, mpv_exe, retry_count))
            return

        wid = int(self._container.winId())
        # 用 --wid=value 格式（Windows上更可靠）
        # --force-window=yes 确保有窗口但不抢焦点

        # 创建 Lua 脚本用于获取详细流数据
        if self._lua_script_path and os.path.exists(self._lua_script_path):
            try:
                os.unlink(self._lua_script_path)
            except Exception:
                pass
        self._lua_script_path = self._create_stream_info_script()

        cmd = [
            mpv_exe,
            f'--wid={wid}',
            '--force-window=yes',
            '--no-border', '--no-config',
            '--keepaspect-window=no',
            '--loop=no',
            '--volume=50',
            '--ytdl=no',
            '--gpu-api=auto',
            '--hwdec=auto',
            f'--scripts={self._lua_script_path}',
            '--referrer=https://live.bilibili.com/',
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            play_url,
        ]
        logger.info(f"[mpv] 启动(重试{retry_count}): --wid={wid} container={sz.width()}x{sz.height()} url={play_url[:80]}")
        try:
            self._player_proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                **subprocess_no_window_kwargs()
            )
            self._player_type = 'mpv'
            self.status_label.setText("正在连接...")

            def _log_mpv():
                lines = []
                try:
                    for line in iter(self._player_proc.stdout.readline, b''):
                        if not line: break
                        s = line.decode('utf-8', errors='replace').rstrip()
                        lines.append(s)
                        if s:
                            logger.info(f"[mpv] {s}")
                            self._parse_mpv_line(s)
                except Exception as e:
                    logger.warning(f"[mpv] 日志读取异常: {e}")
                ret = self._player_proc.poll() if self._player_proc else -1
                last = '\n'.join(lines[-15:]) if lines else '(无输出)'
                logger.warning(f"[mpv] 已退出! code={ret} 最后输出:\n{last}")

                # 如果是URL过期(404)且还有重试次数，自动重试
                if retry_count < 2 and ret != 0:
                    any_404 = any('404' in l for l in lines[-10:])
                    any_failed = any('loading failed' in l or 'Failed to open' in l for l in lines[-10:])
                    if any_404 or any_failed:
                        logger.warning(f"[mpv] URL可能过期，自动重试 ({retry_count+1}/2)")
                        self._player_proc = None
                        QTimer.singleShot(1000, lambda: self._play_mpv(url, mpv_exe, retry_count+1))
                        return

                # 重试耗尽或非网络错误，回退 ffplay
                if ret != 0 and retry_count >= 2:
                    logger.error("[mpv] 多次失败，回退 ffplay")
                    self.status_label.setText("mpv 播放失败，尝试外部播放...")
                    QTimer.singleShot(500, lambda: self._play_ffplay_fallback(play_url))

            threading.Thread(target=_log_mpv, daemon=True).start()

            def _check_alive():
                proc = getattr(self, '_player_proc', None)
                if not proc: return
                if proc.poll() is not None:
                    # mpv 快速退出，日志线程会处理重试逻辑
                    pass
                else:
                    self.status_label.setText("正在播放 (mpv)")
                    self._monitor_player()
            QTimer.singleShot(2000, _check_alive)

        except Exception as e:
            logger.error(f"[mpv] 失败: {e}")
            self.status_label.setText(f"mpv 启动失败，回退 ffplay...")
            QTimer.singleShot(500, lambda: self._play_ffplay_fallback(self._get_fresh_url()))

    def _play_ffplay_fallback(self, url):
        """ffplay 外部窗口回退"""
        ffmpeg_dir = os.path.dirname(_find_ffmpeg()) if _find_ffmpeg() else ''
        ffplay_exe = os.path.join(ffmpeg_dir, exe('ffplay')) if ffmpeg_dir else exe('ffplay')
        if not os.path.exists(ffplay_exe):
            import shutil
            ffplay_exe = shutil.which('ffplay') or 'ffplay'
        if not os.path.exists(ffplay_exe):
            QMessageBox.warning(self, "提示", "未找到 ffplay"); return

        cmd = [
            ffplay_exe,
            '-allowed_extensions', 'ALL',
            '-noborder', '-autoexit', '-volume', '50',
            '-i', url,
        ]
        logger.info(f"[ffplay] 外部: {url[:80]}")
        try:
            self._player_proc = subprocess.Popen(cmd, **subprocess_no_window_kwargs())
            self._player_type = 'ffplay'
            self.status_label.setText("正在播放 (ffplay 外部)")
            self._monitor_player()
        except Exception as e:
            self.status_label.setText(f"启动失败: {e}")

    def _monitor_player(self):
        proc = getattr(self, '_player_proc', None)
        if not proc:
            return
        if proc.poll() is not None:
            pname = getattr(self, '_player_type', 'player')
            self.status_label.setText(f"{pname} 已退出")
            self._player_proc = None
        else:
            QTimer.singleShot(1000, self._monitor_player)

    def _stop_play(self):
        """停止播放：先温和终止，避免强制 kill 破坏窗口状态"""
        if getattr(self, '_resize_timer', None):
            self._resize_timer.stop()
        self._ffplay_hwnd = None
        proc = getattr(self, '_player_proc', None)
        if proc:
            pid = proc.pid
            try:
                # 先温和终止
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    # 2秒后不退出再强制终止
                    if IS_WINDOWS:
                        subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
                    else:
                        proc.kill()
                        proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            self._player_proc = None
        # 清理 Lua 脚本临时文件
        if self._lua_script_path and os.path.exists(self._lua_script_path):
            try:
                os.unlink(self._lua_script_path)
            except Exception:
                pass
            self._lua_script_path = None
        self.status_label.setText("已停止")

    def _create_stream_info_script(self):
        """创建 mpv Lua 脚本，用于输出详细的 track 数据和实时码率"""
        script = r"""
local utils = require 'mp.utils'

-- 文件加载后输出所有 track 详情
mp.register_event('file-loaded', function()
    local tracks = mp.get_property_native('track-list', {})
    for i, t in ipairs(tracks) do
        mp.msg.info('STREAM_TRACK:' .. utils.format_json(t))
    end
    -- 输出额外属性
    local extra = {
        media_title = mp.get_property('media-title', ''),
        container_fps = mp.get_property('container-fps', ''),
        path = mp.get_property('path', ''),
        demuxer = mp.get_property('demuxer-lavf-demuxer', ''),
        protocol = mp.get_property('protocol', ''),
        seekable = mp.get_property('seekable', ''),
        duration = mp.get_property('duration', ''),
    }
    mp.msg.info('STREAM_EXTRA:' .. utils.format_json(extra))
end)

-- 每3秒输出实时数据
mp.add_periodic_timer(3, function()
    local cache_state = mp.get_property_native('demuxer-cache-state', {})
    local live = {
        vbitrate = mp.get_property('packet-video-bitrate', ''),
        abitrate = mp.get_property('packet-audio-bitrate', ''),
        cache_duration = mp.get_property('demuxer-cache-duration', ''),
        cache_speed = mp.get_property('demuxer-cache-speed', ''),
        dropped = mp.get_property('drop-frame-count', ''),
        fps = mp.get_property('estimated-vf-fps', ''),
        eof = mp.get_property('demux-eof', ''),
        buffering = mp.get_property('cache-buffering-state', ''),
        video_format = mp.get_property('video-format', ''),
        video_colorspace = mp.get_property('video-params/colorspace', ''),
        video_primaries = mp.get_property('video-params/primaries', ''),
        video_levels = mp.get_property('video-params/output-levels', ''),
        hwdec_current = mp.get_property('hwdec-current', ''),
        cache_size = cache_state and cache_state['cache-size'] or '',
        cache_used = cache_state and cache_state['fw-bytes'] or '',
        cache_filling = cache_state and cache_state['filling'] or '',
        underrun = cache_state and cache_state['underrun'] or '',
    }
    mp.msg.info('STREAM_LIVE:' .. utils.format_json(live))
end)
"""
        import tempfile
        fd, path = tempfile.mkstemp(suffix='.lua', prefix='mpv_stream_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(script)
        return path

    def _parse_mpv_line(self, line):
        """从 mpv 日志行中解析流数据"""

        # 1) Lua 脚本输出的 TRACK 数据（JSON格式，最详细）
        if 'STREAM_TRACK:' in line:
            try:
                json_str = line.split('STREAM_TRACK:', 1)[1].strip()
                data = json.loads(json_str)
                track_type = data.get('type', '')
                if track_type == 'video':
                    self._stream_info['video_codec'] = data.get('codec', '')
                    self._stream_info['video_width'] = data.get('demux-w', data.get('width', 0))
                    self._stream_info['video_height'] = data.get('demux-h', data.get('height', 0))
                    self._stream_info['video_fps'] = data.get('demux-fps', data.get('fps', ''))
                    self._stream_info['video_bitrate'] = data.get('demux-bitrate', 0)
                    self._stream_info['video_lang'] = data.get('lang', '')
                    self._stream_info['video_title'] = data.get('title', '')
                    # 额外视频属性
                    if data.get('demux-bitrate'):
                        self._stream_info['video_bitrate'] = data['demux-bitrate']
                    if data.get('codec-profile'):
                        self._stream_info['video_profile'] = data['codec-profile']
                    if data.get('codec-level'):
                        self._stream_info['video_level'] = data['codec-level']
                    if data.get('pixel-format'):
                        self._stream_info['video_pixel_format'] = data['pixel-format']
                    if data.get('color-primaries'):
                        self._stream_info['video_color_primaries'] = data['color-primaries']
                    if data.get('transfer-characteristics'):
                        self._stream_info['video_transfer'] = data['transfer-characteristics']
                elif track_type == 'audio':
                    self._stream_info['audio_codec'] = data.get('codec', '')
                    self._stream_info['audio_sample_rate'] = data.get('demux-samplerate', 0)
                    self._stream_info['audio_channels'] = data.get('demux-channel-count', 0)
                    self._stream_info['audio_bitrate'] = data.get('demux-bitrate', 0)
                    self._stream_info['audio_lang'] = data.get('lang', '')
                    self._stream_info['audio_title'] = data.get('title', '')
                    if data.get('codec-profile'):
                        self._stream_info['audio_profile'] = data['codec-profile']
            except Exception as e:
                logger.debug(f"解析 STREAM_TRACK 失败: {e}")
            return

        # 2) Lua 脚本输出的 EXTRA 数据
        if 'STREAM_EXTRA:' in line:
            try:
                json_str = line.split('STREAM_EXTRA:', 1)[1].strip()
                data = json.loads(json_str)
                for k in ('media_title', 'container_fps', 'path', 'demuxer',
                          'protocol', 'seekable', 'duration'):
                    if data.get(k) is not None and data[k] != '':
                        self._stream_info[f'extra_{k}'] = data[k]
            except Exception as e:
                logger.debug(f"解析 STREAM_EXTRA 失败: {e}")
            return

        # 3) Lua 脚本输出的实时数据
        if 'STREAM_LIVE:' in line:
            try:
                json_str = line.split('STREAM_LIVE:', 1)[1].strip()
                data = json.loads(json_str)
                for k in ('vbitrate', 'abitrate', 'cache_duration', 'cache_speed',
                          'dropped', 'fps', 'eof', 'buffering', 'video_format',
                          'video_colorspace', 'video_primaries', 'video_levels',
                          'hwdec_current', 'cache_size', 'cache_used',
                          'cache_filling', 'underrun'):
                    if data.get(k) is not None and data[k] != '':
                        self._stream_info[f'live_{k}'] = data[k]
            except Exception as e:
                logger.debug(f"解析 STREAM_LIVE 失败: {e}")
            return

        # 4) 常规日志解析（作为补充）

        # AO: [wasapi] 48000Hz stereo 2ch floatp
        m = re.match(r'AO:\s+\[(\w+)\]\s+(\d+)Hz\s+(\w+)\s+(\d+)ch', line)
        if m:
            self._stream_info['ao_driver'] = m.group(1)
            self._stream_info['ao_sample_rate'] = int(m.group(2))
            self._stream_info['ao_channels_label'] = m.group(3)
            self._stream_info['ao_channels_num'] = int(m.group(4))
            return

        # VO: [gpu] 1920x1080 gpu
        m = re.match(r'VO:\s+\[(\w+)\]\s+(\d+)x(\d+)', line)
        if m:
            self._stream_info['vo_driver'] = m.group(1)
            self._stream_info['vo_width'] = int(m.group(2))
            self._stream_info['vo_height'] = int(m.group(3))
            return

        # HTTP Host header
        m = re.match(r'.*Host:\s+(.*)', line, re.IGNORECASE)
        if m and 'stream_host' not in self._stream_info:
            self._stream_info['stream_host'] = m.group(1).strip()

        # content-type
        m = re.match(r'.*[Cc]ontent-[Tt]ype:\s+(.*)', line)
        if m and 'mime_type' not in self._stream_info:
            self._stream_info['mime_type'] = m.group(1).strip()

        # Server header (encoder info)
        m = re.match(r'.*[Ss]erver:\s+(.*)', line)
        if m and 'server' not in self._stream_info:
            self._stream_info['server'] = m.group(1).strip()

        # cache / buffer
        m = re.match(r'.*[Cc]ache:\s+(.*)', line)
        if m:
            self._stream_info['cache'] = m.group(1).strip()

    def _show_stream_info_menu(self, pos):
        """右键菜单：显示视频流数据"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #555; padding: 4px; }
            QMenu::item { padding: 6px 24px; }
            QMenu::item:selected { background-color: #3d6fa5; }
            QMenu::separator { height: 1px; background: #555; margin: 4px 0; }
        """)

        info_action = menu.addAction("查看流数据信息")
        menu.addSeparator()
        copy_action = menu.addAction("复制流数据到剪贴板")

        action = menu.exec_(self._container.mapToGlobal(pos))

        if action == info_action:
            self._show_stream_info_dialog()
        elif action == copy_action:
            self._copy_stream_info()

    def _build_stream_info_text(self):
        """构建流数据信息文本（全中文标签，显示所有可用数据）"""
        info = self._stream_info
        lines = []

        def _fmt_bitrate(bps):
            """格式化码率"""
            if not bps:
                return ''
            try:
                v = float(bps)
                if v >= 1_000_000:
                    return f"{v / 1_000_000:.2f} Mbps"
                elif v >= 1000:
                    return f"{v / 1000:.0f} Kbps"
                else:
                    return f"{v:.0f} bps"
            except Exception:
                return str(bps)

        def _fmt_bytes(b):
            """格式化字节数"""
            if not b:
                return ''
            try:
                v = float(b)
                if v >= 1024 * 1024:
                    return f"{v / 1024 / 1024:.1f} MB"
                elif v >= 1024:
                    return f"{v / 1024:.0f} KB"
                else:
                    return f"{v:.0f} B"
            except Exception:
                return str(b)

        def _extract_url_param(url, param):
            """从URL中提取指定参数值"""
            try:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(url)
                qs = parse_qs(parsed.query)
                vals = qs.get(param, [])
                return vals[0] if vals else None
            except Exception:
                return None

        def _short_title(title):
            """截断媒体标题，只保留文件名部分"""
            if not title:
                return ''
            # 如果是URL，只取路径部分（去掉查询参数）
            if '?' in title:
                title = title.split('?', 1)[0]
            if '/' in title:
                title = title.rsplit('/', 1)[-1]
            if len(title) > 60:
                title = title[:57] + '...'
            return title

        current_url = self._current_url or ''

        lines.append("══════ 基础信息 ══════")

        if 'mime_type' in info:
            lines.append(f"  媒体类型: {info['mime_type']}")
        else:
            if '.m3u8' in current_url:
                lines.append("  媒体类型: application/vnd.apple.mpegurl (HLS)")
            elif 'flv' in current_url.lower():
                lines.append("  媒体类型: video/x-flv")
            else:
                lines.append("  媒体类型: (未获取)")

        if self._player_type == 'mpv':
            lines.append("  播放器内核: mpv (内嵌)")
        elif self._player_type == 'ffplay':
            lines.append("  播放器内核: ffplay (外部)")
        else:
            lines.append("  播放器内核: (未知)")

        protocol = info.get('extra_protocol')
        if protocol:
            proto_map = {'hls': 'HLS', 'http': 'HTTP', 'https': 'HTTPS', 'rtmp': 'RTMP'}
            lines.append(f"  传输协议: {proto_map.get(protocol, protocol)}")

        demuxer = info.get('extra_demuxer')
        if demuxer:
            lines.append(f"  解复用器: {demuxer}")

        media_title = info.get('extra_media_title') or info.get('media_title')
        if media_title:
            short = _short_title(media_title)
            if short:
                lines.append(f"  流名称: {short}")

        qn = _extract_url_param(current_url, 'qn')
        qn_map = {'80': '流畅', '150': '高清', '250': '超清',
                  '400': '蓝光', '10000': '原画', '20000': '4K', '30000': '杜比'}
        if qn:
            qn_desc = qn_map.get(str(qn), '')
            qn_text = f"  实际画质: {qn_desc} (qn={qn})" if qn_desc else f"  实际画质: qn={qn}"
            lines.append(qn_text)

        suffix = _extract_url_param(current_url, 'suffix')
        if suffix:
            lines.append(f"  流标识码率: {suffix}Kbps")

        origin_bitrate = _extract_url_param(current_url, 'origin_bitrate')
        if origin_bitrate:
            fb = _fmt_bitrate(float(origin_bitrate) * 1000)  # URL中的单位是Kbps
            if fb:
                lines.append(f"  源流码率: {fb}")

        cdn = _extract_url_param(current_url, 'cdn')
        if cdn:
            lines.append(f"  CDN节点: {cdn}")

        if info.get('server'):
            lines.append(f"  服务器: {info['server']}")

        if info.get('stream_host'):
            lines.append(f"  流服务器: {info['stream_host']}")
        else:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(current_url)
                if parsed.hostname:
                    lines.append(f"  流服务器: {parsed.hostname}")
            except Exception:
                pass

        lines.append("")
        lines.append("══════ 视频信息 ══════")

        vcodec = info.get('video_codec')
        vprofile = info.get('video_profile')
        vlevel = info.get('video_level')
        if vcodec:
            codec_str = vcodec
            if vprofile:
                codec_str += f" ({vprofile})"
            if vlevel:
                try:
                    codec_str += f" Level {float(vlevel):.1f}"
                except Exception:
                    codec_str += f" Level {vlevel}"
            lines.append(f"  视频编码: {codec_str}")

        vw = info.get('video_width')
        vh = info.get('video_height')
        if vw and vh:
            lines.append(f"  视频分辨率: {vw}x{vh}")

        vfps = info.get('video_fps') or info.get('extra_container_fps')
        if vfps:
            try:
                lines.append(f"  视频帧率: {float(vfps):.2f} FPS")
            except Exception:
                lines.append(f"  视频帧率: {vfps} FPS")

        vbitrate = info.get('video_bitrate')
        if vbitrate:
            fb = _fmt_bitrate(vbitrate)
            if fb:
                lines.append(f"  视频码率: {fb}")

        pix_fmt = info.get('video_pixel_format')
        if pix_fmt:
            lines.append(f"  像素格式: {pix_fmt}")

        colorspace = info.get('live_video_colorspace') or info.get('video_color_primaries')
        if colorspace:
            lines.append(f"  色彩空间: {colorspace}")
        transfer = info.get('video_transfer')
        if transfer:
            lines.append(f"  传输特性: {transfer}")
        primaries = info.get('video_color_primaries')
        if primaries and primaries != colorspace:
            lines.append(f"  色域: {primaries}")
        levels = info.get('live_video_levels')
        if levels:
            lines.append(f"  亮度范围: {levels}")

        hwdec = info.get('live_hwdec_current')
        if hwdec:
            lines.append(f"  硬件解码: {hwdec}")

        vo = info.get('vo_driver')
        if vo:
            vo_w = info.get('vo_width')
            vo_h = info.get('vo_height')
            vo_str = vo
            if vo_w and vo_h:
                vo_str += f" ({vo_w}x{vo_h})"
            lines.append(f"  视频输出驱动: {vo_str}")

        if not any(info.get(k) for k in ('video_codec', 'video_width', 'video_height', 'video_fps', 'video_bitrate', 'vo_driver')):
            lines.append("  (暂未获取视频数据)")

        lines.append("")
        lines.append("══════ 音频信息 ══════")

        acodec = info.get('audio_codec')
        aprofile = info.get('audio_profile')
        if acodec:
            codec_str = acodec
            if aprofile:
                codec_str += f" ({aprofile})"
            lines.append(f"  音频编码: {codec_str}")

        asr = info.get('audio_sample_rate')
        if asr:
            sr_str = f"{asr // 1000}KHz" if asr >= 1000 else f"{asr}Hz"
            lines.append(f"  采样率: {sr_str}")

        ach = info.get('audio_channels')
        ach_label = info.get('ao_channels_label')
        ach_num = info.get('ao_channels_num')
        if ach:
            ch_map = {'1': '单声道', '2': '立体声', '6': '5.1环绕声', '8': '7.1环绕声'}
            ch_str = ch_map.get(str(ach), f"{ach}声道")
            lines.append(f"  声道数: {ch_str} ({ach}ch)")
        elif ach_num:
            ch_map = {'1': '单声道', '2': '立体声', '6': '5.1环绕声', '8': '7.1环绕声'}
            ch_str = ch_map.get(str(ach_num), f"{ach_num}声道")
            label = f" ({ach_label})" if ach_label else ""
            lines.append(f"  声道数: {ch_str} ({ach_num}ch){label}")

        abitrate = info.get('audio_bitrate')
        if abitrate:
            fb = _fmt_bitrate(abitrate)
            if fb:
                lines.append(f"  音频码率: {fb}")

        ao = info.get('ao_driver')
        if ao:
            ao_parts = [ao]
            ao_sr = info.get('ao_sample_rate')
            if ao_sr:
                ao_parts.append(f"{ao_sr // 1000}KHz" if ao_sr >= 1000 else f"{ao_sr}Hz")
            if ach_label:
                ao_parts.append(ach_label)
            if ach_num:
                ao_parts.append(f"{ach_num}ch")
            lines.append(f"  音频输出驱动: {' '.join(ao_parts)}")

        if not any(info.get(k) for k in ('audio_codec', 'audio_sample_rate', 'audio_channels', 'audio_bitrate', 'ao_driver')):
            lines.append("  (暂未获取音频数据)")

        lines.append("")
        lines.append("══════ 实时流数据 ══════")

        has_live_data = False

        lvb = info.get('live_vbitrate')
        if lvb:
            fb = _fmt_bitrate(lvb)
            if fb:
                lines.append(f"  实时视频码率: {fb}")
                has_live_data = True

        lab = info.get('live_abitrate')
        if lab:
            fb = _fmt_bitrate(lab)
            if fb:
                lines.append(f"  实时音频码率: {fb}")
                has_live_data = True

        lfps = info.get('live_fps')
        if lfps:
            try:
                lines.append(f"  实时帧率: {float(lfps):.2f} FPS")
                has_live_data = True
            except Exception:
                pass

        cache_dur = info.get('live_cache_duration')
        cache_spd = info.get('live_cache_speed')
        cache_size = info.get('live_cache_size')
        cache_used = info.get('live_cache_used')
        cache_parts = []
        if cache_dur:
            try:
                cache_parts.append(f"{float(cache_dur):.1f}秒")
                has_live_data = True
            except Exception:
                cache_parts.append(f"{cache_dur}")
        if cache_spd:
            fb = _fmt_bitrate(cache_spd)
            if fb:
                cache_parts.append(fb)
        size_parts = []
        if cache_used:
            s = _fmt_bytes(cache_used)
            if s:
                size_parts.append(f"已用{s}")
        if cache_size:
            s = _fmt_bytes(cache_size)
            if s:
                size_parts.append(f"总{s}")
        if size_parts:
            cache_parts.append(' '.join(size_parts))
        if cache_parts:
            lines.append(f"  缓冲: {'/'.join(cache_parts)}")

        if info.get('live_cache_filling'):
            lines.append("  缓存状态: 正在填充...")
        if info.get('live_underrun'):
            lines.append("  缓存状态: 缓存欠载!")

        dropped = info.get('live_dropped')
        if dropped:
            try:
                d = int(float(dropped))
                if d > 0:
                    lines.append(f"  丢帧数: {d}")
                    has_live_data = True
            except Exception:
                pass

        if not has_live_data:
            lines.append("  (播放开始后将自动获取实时数据)")

        if info.get('bitrate') or info.get('demux_info'):
            lines.append("")
            lines.append("══════ 下载信息 ══════")
            if 'bitrate' in info:
                fb = _fmt_bitrate(info['bitrate'])
                if fb:
                    lines.append(f"  下载码率: {fb}")
            if 'demux_info' in info:
                lines.append(f"  解复用信息: {info['demux_info']}")

        return '\n'.join(lines)

    def _show_stream_info_dialog(self):
        """弹窗显示流数据"""
        text = self._build_stream_info_text()
        dlg = QDialog(self)
        dlg.setWindowTitle("视频流数据")
        dlg.setMinimumSize(scale(450), scale(350))
        dlg.setStyleSheet("QDialog { background-color: #1e1e1e; }")

        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        title_label = QLabel("当前视频流数据")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #00a1d6; padding-bottom: 4px;")
        layout.addWidget(title_label)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(text)
        text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #555;
                border-radius: 4px; font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px; padding: 8px;
            }
        """)
        layout.addWidget(text_edit, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        copy_btn = QPushButton("复制")
        copy_btn.setStyleSheet("padding: 6px 20px; background-color: #00a1d6; color: white; border: none; border-radius: 4px; font-size: 12px;")
        copy_btn.clicked.connect(lambda: self._copy_to_clipboard(text))
        btn_layout.addWidget(copy_btn)

        close_btn = QPushButton("关闭")
        close_btn.setStyleSheet("padding: 6px 20px; background-color: #6c757d; color: white; border: none; border-radius: 4px; font-size: 12px;")
        close_btn.clicked.connect(dlg.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        dlg.exec_()

    def _copy_stream_info(self):
        """复制流数据到剪贴板"""
        text = self._build_stream_info_text()
        self._copy_to_clipboard(text)

    @staticmethod
    def _copy_to_clipboard(text):
        from PyQt5.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def play_url(self, url):
        self.url_input.setText(url)
        self.show(); self.raise_(); self.activateWindow()
        self._current_url = url
        QTimer.singleShot(500, lambda: self._start_player(url))

    def _open_external(self, url=None):
        target = url or self._current_url or self.url_input.text().strip()
        if not target:
            QMessageBox.warning(self, "提示", "请输入URL"); return
        try:
            if IS_WINDOWS: os.startfile(target)
            elif sys.platform == 'darwin': subprocess.Popen(['open', target])
            else: subprocess.Popen(['xdg-open', target])
            self.status_label.setText("已在外部打开")
        except Exception as e:
            self.status_label.setText(f"打开失败: {e}")

    def _set_download_buttons_enabled(self, enabled):
        for btn_name in ('dl_btn', 'dl_video_btn', 'dl_audio_btn'):
            btn = getattr(self, btn_name, None)
            if btn:
                btn.setEnabled(enabled)

    def _do_download(self, content_type=0):
        """开始后台持续录制/下载（接入录播工具托盘）"""
        url = self.url_input.text().strip()
        if not url: QMessageBox.warning(self, "提示", "请输入URL"); return
        if not LiveRecordThread:
            QMessageBox.warning(self, "提示", "录制模块未加载"); return

        d = os.path.join(os.getcwd(), "流媒体下载"); os.makedirs(d, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        is_hls = ".m3u8" in url.lower()
        if content_type == 1:
            ext = "m4a"
            file_filter = "音频 (*.m4a *.mp3);;所有 (*)"
        elif content_type == 2:
            ext = "mp4" if is_hls else "ts"
            file_filter = "视频 (*.mp4 *.ts);;所有 (*)"
        else:
            ext = "mp4" if is_hls else "flv"
            file_filter = "视频 (*.mp4 *.flv);;所有 (*)"
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存", os.path.join(d, f"stream_{ts}.{ext}"),
            file_filter)
        if not save_path: return

        fmt = "hls" if is_hls else "direct"
        self._set_download_buttons_enabled(False); self.dl_bar.show(); self.dl_bar.setValue(0)

        # 使用 LiveRecordThread（支持URL刷新、暂停、持续录制）
        self.download_thread = LiveRecordThread(
            stream_url=url,
            output_path=save_path,
            format_type=fmt,
            content_type=content_type,
            duration=0,  # 0 = 持续到手动停止
            url_refresher=self._url_refresher,
            room_id="stream"
        )
        self.download_thread.status_changed.connect(self._record_status_sig.emit)
        self.download_thread.progress_updated.connect(self._on_record_progress)
        self.download_thread.record_finished.connect(self._dl_done_sig.emit)
        self.download_thread.error_occurred.connect(self._dl_err_sig.emit)
        self.download_thread.start()

        # 注册到主窗口的录播工具托盘
        self._register_to_recording_tray(save_path)

    def _register_to_recording_tray(self, save_path):
        """将播放器中的下载/录制注册到主窗口的录播工具托盘"""
        parent = self.parent_window
        tray = getattr(parent, 'recording_tray', None) if parent else None
        url = self.url_input.text().strip()
        title = f"播放器直播流"
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.path:
                title = os.path.basename(parsed.path).split('?')[0][:30] or title
        except Exception:
            pass

        if tray:
            self._recording_session_id = tray.add_session(
                room_id="stream", title=title, output_path=save_path)
            tray.notify(
                "录播工具",
                f"正在录制「{title}」\n点击托盘图标可查看状态和控制",
                QSystemTrayIcon.Information)
            self.status_label.setText("录制中（后台持续录制）")
        else:
            QMessageBox.information(
                self, "提示",
                "录制已在后台开始进行！\n\n关闭播放器窗口不影响录制，"
                "可通过系统托盘的「录播工具」图标控制。")

    def _on_record_progress(self, seconds, time_str):
        self._dl_progress_sig.emit(-1, f"录制 {time_str}")

    def _on_record_status(self, msg):
        self.status_label.setText(msg)

    def _on_dl_progress(self, pct, msg):
        if pct >= 0: self.dl_bar.setValue(pct)
        else: self.dl_bar.setRange(0, 0)
        self.status_label.setText(msg)

    def _on_dl_done(self, ok, msg):
        self._set_download_buttons_enabled(True); self.dl_bar.setRange(0, 100)
        if ok: self.dl_bar.setValue(100)
        self.status_label.setText(msg)
        self._cleanup_tray_session()
        QTimer.singleShot(3000, lambda: self.dl_bar.hide())

    def _on_dl_err(self, msg):
        self._set_download_buttons_enabled(True); self.dl_bar.setRange(0, 100); self.dl_bar.setValue(0)
        self.status_label.setText(f"错误: {msg}")
        self._cleanup_tray_session()
        QTimer.singleShot(3000, lambda: self.dl_bar.hide())

    def _cleanup_tray_session(self):
        sid = getattr(self, '_recording_session_id', None)
        if not sid: return
        parent = self.parent_window
        tray = getattr(parent, 'recording_tray', None) if parent else None
        if tray:
            tray.remove_session(sid)
        self._recording_session_id = None

    def handle_tray_stop(self, session_id):
        """托盘请求停止录制"""
        if getattr(self, '_recording_session_id', None) == session_id:
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.stop()
            self._cleanup_tray_session()
            self.dl_btn.setEnabled(True)
            self.dl_bar.setRange(0, 100)

    def handle_tray_pause(self, session_id):
        """托盘请求暂停录制"""
        if getattr(self, '_recording_session_id', None) == session_id:
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.pause()
            parent = self.parent_window
            tray = getattr(parent, 'recording_tray', None) if parent else None
            if tray:
                tray.pause_session(session_id)

    def handle_tray_resume(self, session_id):
        """托盘请求继续录制"""
        if getattr(self, '_recording_session_id', None) == session_id:
            if self.download_thread and self.download_thread.isRunning():
                self.download_thread.resume()
            parent = self.parent_window
            tray = getattr(parent, 'recording_tray', None) if parent else None
            if tray:
                tray.resume_session(session_id)

    def closeEvent(self, event):
        self._stop_play()
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop()
        event.accept()

    def cleanup(self):
        self._stop_play()
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.stop(); self.download_thread.wait(3000)
        self._cleanup_tray_session()
