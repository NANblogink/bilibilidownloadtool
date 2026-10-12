import os
import sys
import shutil
import subprocess

IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')
IS_ANDROID = (sys.platform.startswith('linux')
              and ('ANDROID_ARGUMENT' in os.environ
                   or 'ANDROID_ROOT' in os.environ
                   or 'ANDROID_STORAGE' in os.environ
                   or os.path.exists('/system/build.prop')))

PLATFORM_NAME = 'windows' if IS_WINDOWS else ('macos' if IS_MACOS else
                                              ('android' if IS_ANDROID else 'linux'))


def exe(name):
    if IS_WINDOWS:
        return name if name.lower().endswith('.exe') else f"{name}.exe"
    if name.lower().endswith('.exe'):
        return name[:-4]
    return name


def tool_names(name):
    base = exe(name)
    if IS_WINDOWS:
        return [base]
    return [base, f"{name}.exe"] if not base.endswith('.exe') else [base]


_NO_WINDOW_USABLE = True


def note_no_window_failure(exc):
    global _NO_WINDOW_USABLE
    if not IS_WINDOWS:
        return False
    if getattr(exc, 'winerror', None) == 50:
        if _NO_WINDOW_USABLE:
            _NO_WINDOW_USABLE = False
        return True
    return False


def subprocess_no_window_kwargs():
    if IS_WINDOWS and _NO_WINDOW_USABLE:
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def subprocess_low_priority_kwargs():
    """返回低优先级子进程的创建参数，用于ffmpeg等CPU密集型任务，降低CPU噪音但不降速"""
    if IS_WINDOWS and _NO_WINDOW_USABLE:
        return {'creationflags': subprocess.CREATE_NO_WINDOW | 0x00004000}
    if IS_WINDOWS:
        return {'creationflags': 0x00004000}
    return {}


def run_no_window(cmd, timeout=30, text=False, **kwargs):
    if not IS_WINDOWS:
        return subprocess.run(cmd, capture_output=True, text=text,
                              timeout=timeout, **kwargs)
    try:
        return subprocess.run(cmd, capture_output=True, text=text, timeout=timeout,
                              **subprocess_no_window_kwargs(), **kwargs)
    except OSError as e:
        if not note_no_window_failure(e):
            raise
        return subprocess.run(cmd, capture_output=True, text=text,
                              timeout=timeout, **kwargs)


def app_data_dir(app_name="BilibiliDownloadTool"):
    if IS_MACOS:
        return os.path.expanduser(f"~/Library/Application Support/{app_name}")
    elif IS_WINDOWS:
        return os.path.join(os.environ.get('APPDATA', os.path.expanduser('~\\AppData\\Roaming')), app_name)
    else:
        return os.path.expanduser(f"~/.config/{app_name}")


def program_files_dir(app_name="BilibiliDownloadTool"):
    if IS_MACOS:
        return os.path.expanduser(f"~/Library/Application Support/{app_name}")
    elif IS_WINDOWS:
        return os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files'), app_name)
    else:
        return os.path.expanduser(f"/opt/{app_name}")


def is_admin():
    if IS_WINDOWS:
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False
    else:
        return os.geteuid() == 0


def hide_file(path):
    if IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(path, 0x02)
        except Exception:
            pass


def illegal_filename_chars():
    if IS_WINDOWS:
        return ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
    elif IS_MACOS:
        return ['/', ':']
    return ['/']


def platform_font():
    if IS_MACOS:
        return "PingFang SC", 13
    elif IS_WINDOWS:
        return "Microsoft YaHei", 9
    return "Noto Sans CJK SC", 10


def get_bento4_sdk_dirname():
    if IS_WINDOWS:
        return 'Bento4-SDK-1-6-0-641.x86_64-microsoft-win32'
    elif IS_MACOS:
        return 'Bento4-SDK-1-6-0-641.x86_64-apple-macosx'
    return 'Bento4-SDK-1-6-0-641'


CDN_URLS = {
    'ffmpeg': {
        'win32': 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip',
        'darwin': 'https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip',
        'linux': 'https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz',
    },
    'bento4': {
        'win32': 'https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-microsoft-win32.zip',
        'darwin': 'https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-apple-macosx.zip',
        'linux': 'https://www.bok.net/Bento4/binaries/Bento4-SDK-1-6-0-641.x86_64-unknown-linux.zip',
    }
}


def get_cdn_url(tool_name):
    platform_key = 'win32' if IS_WINDOWS else ('darwin' if IS_MACOS else 'linux')
    urls = CDN_URLS.get(tool_name, {})
    return urls.get(platform_key, urls.get('win32', ''))


def add_to_system_path(paths, user_only=True):
    if IS_WINDOWS:
        try:
            import winreg
            if user_only:
                root_key = winreg.HKEY_CURRENT_USER
                sub_key = r'Environment'
            else:
                root_key = winreg.HKEY_LOCAL_MACHINE
                sub_key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'

            key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_ALL_ACCESS)
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
            paths_updated = False
            for path in paths:
                if path not in current_path:
                    current_path = f"{current_path};{path}" if current_path else path
                    paths_updated = True
            if paths_updated:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, current_path)
                winreg.CloseKey(key)
                _broadcast_env_change_windows()
                return True, '环境变量更新成功'
            winreg.CloseKey(key)
            return True, '环境变量已包含工具路径'
        except Exception as e:
            return False, f'更新环境变量失败: {str(e)}'
    elif IS_MACOS:
        shell_rc_files = [
            os.path.expanduser('~/.zshrc'),
            os.path.expanduser('~/.bash_profile'),
            os.path.expanduser('~/.bashrc'),
        ]
        marker = '# BilibiliDownloadTool PATH'
        path_exports = ':'.join(paths)
        export_line = f'export PATH="$PATH:{path_exports}" {marker}'

        updated = False
        for rc_file in shell_rc_files:
            if os.path.exists(rc_file):
                with open(rc_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                if marker not in content:
                    with open(rc_file, 'a', encoding='utf-8') as f:
                        f.write(f'\n{export_line}\n')
                    updated = True
                break
        else:
            rc_file = shell_rc_files[0]
            with open(rc_file, 'a', encoding='utf-8') as f:
                f.write(f'\n{export_line}\n')
            updated = True

        if updated:
            return True, '环境变量已添加，请重新打开终端生效'
        return True, '环境变量已存在'
    else:
        return False, '当前平台不支持自动添加环境变量'


def remove_from_system_path(paths, user_only=True):
    if IS_WINDOWS:
        try:
            import winreg
            if user_only:
                root_key = winreg.HKEY_CURRENT_USER
                sub_key = r'Environment'
            else:
                root_key = winreg.HKEY_LOCAL_MACHINE
                sub_key = r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'

            key = winreg.OpenKey(root_key, sub_key, 0, winreg.KEY_ALL_ACCESS)
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
            paths_updated = False
            for path in paths:
                if path in current_path:
                    current_path = current_path.replace(path, '')
                    current_path = current_path.replace(';;', ';')
                    if current_path.startswith(';'):
                        current_path = current_path[1:]
                    if current_path.endswith(';'):
                        current_path = current_path[:-1]
                    paths_updated = True
            if paths_updated:
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, current_path)
                winreg.CloseKey(key)
                _broadcast_env_change_windows()
                return True, '环境变量更新成功'
            winreg.CloseKey(key)
            return True, '环境变量中没有工具路径'
        except Exception as e:
            return False, f'移除环境变量失败: {str(e)}'
    elif IS_MACOS:
        marker = '# BilibiliDownloadTool PATH'
        shell_rc_files = [
            os.path.expanduser('~/.zshrc'),
            os.path.expanduser('~/.bash_profile'),
            os.path.expanduser('~/.bashrc'),
        ]
        for rc_file in shell_rc_files:
            if os.path.exists(rc_file):
                with open(rc_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                new_lines = [line for line in lines if marker not in line]
                if len(new_lines) != len(lines):
                    with open(rc_file, 'w', encoding='utf-8') as f:
                        f.writelines(new_lines)
                    return True, '环境变量已移除'
        return True, '未找到环境变量配置'
    else:
        return False, '当前平台不支持自动移除环境变量'


def _broadcast_env_change_windows():
    if not IS_WINDOWS:
        return
    try:
        import win32gui
        import win32con
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x1A
        win32gui.SendMessageTimeout(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0,
            'Environment', win32con.SMTO_ABORTIFHUNG, 5000
        )
    except ImportError:
        pass
    except Exception:
        pass


def get_system_proxy():
    if IS_WINDOWS:
        try:
            import winreg
            internet_settings = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Internet Settings',
                0, winreg.KEY_READ
            )
            proxy_enable = winreg.QueryValueEx(internet_settings, 'ProxyEnable')[0]
            try:
                proxy_server = winreg.QueryValueEx(internet_settings, 'ProxyServer')[0]
            except (UnicodeDecodeError, Exception):
                try:
                    proxy_server_raw = winreg.QueryValueEx(internet_settings, 'ProxyServer')
                    proxy_server = str(proxy_server_raw[0]) if proxy_server_raw else ''
                except Exception:
                    proxy_server = ''
            winreg.CloseKey(internet_settings)
            if proxy_enable and proxy_server:
                return proxy_server
        except Exception:
            pass
    elif IS_MACOS:
        try:
            result = subprocess.run(
                ['networksetup', '-getwebproxy', 'Wi-Fi'],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            enabled = False
            server = ''
            port = ''
            for line in lines:
                if 'Enabled' in line and 'Yes' in line:
                    enabled = True
                elif 'Server' in line:
                    server = line.split(':')[-1].strip()
                elif 'Port' in line:
                    port = line.split(':')[-1].strip()
            if enabled and server:
                return f"{server}:{port}"
        except Exception:
            pass
    return None


def detect_gpu():
    if IS_WINDOWS:
        try:
            result = run_no_window(
                ['powershell', '-NoProfile', '-Command',
                 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'],
                timeout=10, text=True
            )
            output = result.stdout.strip()
            if output:
                for line in output.split('\n'):
                    line = line.strip()
                    low = line.lower()
                    if not line or low == 'name':
                        continue
                    if 'nvidia' in low:
                        return True, 'nvidia', line
                    elif 'amd' in low or 'radeon' in low:
                        return True, 'amd', line
                    elif 'intel' in low and ('uhd' in low or 'iris' in low or 'arc' in low):
                        return True, 'intel', line
        except Exception as e:
            try:
                import logging
                logging.getLogger(__name__).debug(f"PowerShell GPU检测失败: {e}")
            except Exception:
                pass

        try:
            result = subprocess.run(
                ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip().strip('\r')
                low = line.lower()
                if not line or low == 'name':
                    continue
                if 'nvidia' in low:
                    return True, 'nvidia', line
                elif 'amd' in low or 'radeon' in low:
                    return True, 'amd', line
                elif 'intel' in low and ('uhd' in low or 'iris' in low or 'arc' in low):
                    return True, 'intel', line
        except Exception:
            pass

        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip().split('\n')[0].strip()
                return True, 'nvidia', gpu_name
        except Exception:
            pass

    return False, None, None


def has_non_ascii(path):
    """检测路径是否包含非ASCII字符"""
    if not path:
        return False
    return any(ord(c) > 127 for c in path)


def to_short_path(path):
    if not IS_WINDOWS or not path:
        return path
    if not has_non_ascii(path):
        return path
    try:
        import ctypes
        from ctypes import wintypes
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        GetShortPathNameW.restype = wintypes.DWORD

        buf_size = GetShortPathNameW(path, None, 0)
        if buf_size == 0:
            return path

        buf = ctypes.create_unicode_buffer(buf_size)
        result = GetShortPathNameW(path, buf, buf_size)
        if result > 0:
            short_path = buf.value
            if not has_non_ascii(short_path):
                return short_path
        return path
    except Exception:
        return path


def _is_usable_dir(path):
    """目录是否存在、可写、且不依赖中文路径。"""
    if not path:
        return False
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".bili_write_probe")
        with open(probe, "w") as fh:
            fh.write("ok")
        os.remove(probe)
    except Exception:
        return False
    if not has_non_ascii(path):
        return True
    short = to_short_path(path)
    return short != path and not has_non_ascii(short)


def _resolve_ascii_candidate(path):
    """返回可用的 ASCII 路径，不可用则返回 None。"""
    if not path:
        return None
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        return None
    if not has_non_ascii(path):
        return path
    short = to_short_path(path)
    if short != path and not has_non_ascii(short):
        return short
    return None




def open_path(path):
    """用系统默认程序打开文件或目录。"""
    if not path:
        return False
    path = os.path.normpath(path)
    try:
        if IS_WINDOWS:
            os.startfile(path)  # noqa: S606 - Windows 专用
        elif IS_MACOS:
            subprocess.Popen(['open', path], **subprocess_no_window_kwargs())
        elif IS_ANDROID:
            return False
        else:
            opener = shutil.which('xdg-open')
            if not opener:
                return False
            subprocess.Popen([opener, path], **subprocess_no_window_kwargs())
        return True
    except Exception:
        return False


def reveal_in_file_manager(path, select=False):
    if not path:
        return False
    path = os.path.normpath(path)
    try:
        if IS_WINDOWS:
            if select and os.path.isfile(path):
                subprocess.Popen(['explorer', '/select,', path],
                                 **subprocess_no_window_kwargs())
            else:
                target = path if os.path.isdir(path) else os.path.dirname(path)
                subprocess.Popen(['explorer', target],
                                 **subprocess_no_window_kwargs())
            return True
        if IS_MACOS:
            if select:
                subprocess.Popen(['open', '-R', path], **subprocess_no_window_kwargs())
            else:
                subprocess.Popen(['open', path if os.path.isdir(path) else os.path.dirname(path)],
                                 **subprocess_no_window_kwargs())
            return True
        target = path if os.path.isdir(path) else os.path.dirname(path)
        return open_path(target)
    except Exception:
        return False


def open_terminal(command=None, path=None):
    """打开一个终端窗口。"""
    try:
        if IS_WINDOWS:
            if command:
                subprocess.Popen(['cmd', '/k', command],
                                 cwd=path, **subprocess_no_window_kwargs())
            else:
                subprocess.Popen(['cmd'], cwd=path, **subprocess_no_window_kwargs())
            return True
        if IS_MACOS:
            if path:
                subprocess.Popen(['open', '-a', 'Terminal', path])
            else:
                subprocess.Popen(['open', '-a', 'Terminal'])
            return True
        if IS_ANDROID:
            return False
        for term in ('x-terminal-emulator', 'gnome-terminal', 'konsole',
                     'xfce4-terminal', 'xterm'):
            exe_path = shutil.which(term)
            if not exe_path:
                continue
            if command:
                if term in ('gnome-terminal', 'xfce4-terminal'):
                    args = [exe_path, '--', 'bash', '-c', command + '; exec bash']
                elif term == 'konsole':
                    args = [exe_path, '-e', 'bash', '-c', command + '; exec bash']
                else:
                    args = [exe_path, '-e', 'bash', '-c', command + '; exec bash']
            else:
                args = [exe_path]
            subprocess.Popen(args, cwd=path, **subprocess_no_window_kwargs())
            return True
        return False
    except Exception:
        return False


def kill_process_tree(pid, timeout=5):
    """强制结束进程及其子进程。返回 bool。"""
    if not pid:
        return False
    try:
        if IS_WINDOWS:
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(pid)],
                            **subprocess_no_window_kwargs())
            return True
        import signal
        try:
            pgid = os.getpgid(pid)
        except Exception:
            pgid = None
        try:
            if pgid is not None:
                os.killpg(pgid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return True
        except Exception:
            pass

        import time as _time
        deadline = _time.time() + max(0.0, float(timeout))
        while _time.time() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return True
            _time.sleep(0.05)
        try:
            if pgid is not None:
                os.killpg(pgid, signal.SIGKILL)
            else:
                os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        return True
    except Exception:
        return False


def popen_new_session_kwargs():
    if IS_WINDOWS:
        return {'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0)}
    return {'start_new_session': True}


def shutdown_system(delay_seconds=60, reason=""):
    """安排系统关机。各平台使用各自的命令。返回 (ok, message)。"""
    try:
        if IS_WINDOWS:
            args = ['shutdown', '/s', '/t', str(int(delay_seconds))]
            if reason:
                args += ['/c', reason]
            subprocess.Popen(args, **subprocess_no_window_kwargs())
            return True, '已安排关机'
        if IS_MACOS:
            minutes = max(1, int(round(delay_seconds / 60.0)))
            subprocess.Popen(['sudo', '-n', 'shutdown', '-h', '+%d' % minutes],
                             **subprocess_no_window_kwargs())
            return True, '已安排关机（如有提示请输入密码）'
        if IS_ANDROID:
            return False, '当前平台不支持自动关机'
        if shutil.which('systemctl'):
            subprocess.Popen(['systemctl', 'poweroff'],
                             **subprocess_no_window_kwargs())
            return True, '已安排关机'
        if shutil.which('shutdown'):
            subprocess.Popen(['shutdown', '-h', '+%d' % max(1, int(round(delay_seconds / 60.0)))],
                             **subprocess_no_window_kwargs())
            return True, '已安排关机'
        return False, '未找到可用的关机命令'
    except Exception as e:
        return False, f'安排关机失败: {e}'


def set_process_priority_low(pid=None):
    """把当前进程或指定进程降到低优先级。返回 bool。"""
    try:
        if IS_WINDOWS:
            import ctypes
            handle = None
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            kernel32 = ctypes.windll.kernel32
            if pid:
                handle = kernel32.OpenProcess(0x0200 | 0x0400, False, int(pid))
            else:
                handle = kernel32.GetCurrentProcess()
            if not handle:
                return False
            try:
                return bool(kernel32.SetPriorityClass(handle, BELOW_NORMAL_PRIORITY_CLASS))
            finally:
                if pid and handle:
                    kernel32.CloseHandle(handle)
        import psutil
        proc = psutil.Process(pid) if pid else psutil.Process()
        proc.nice(10)
        return True
    except Exception:
        return False


def available_memory_bytes():
    try:
        import psutil
        return int(psutil.virtual_memory().available)
    except Exception:
        pass
    try:
        if IS_LINUX or IS_ANDROID:
            with open('/proc/meminfo') as fh:
                for line in fh:
                    if line.startswith('MemAvailable:'):
                        return int(line.split()[1]) * 1024
    except Exception:
        pass
    return None


def cpu_count():
    """逻辑 CPU 数，失败回退 2。"""
    try:
        return max(1, os.cpu_count() or 2)
    except Exception:
        return 2


def recommended_concurrency(explicit=None, cap=8, floor=1):
    if explicit:
        try:
            return max(floor, min(int(explicit), cap))
        except Exception:
            pass
    n = cpu_count()
    mem = available_memory_bytes()
    if mem is not None:
        gb = mem / float(1024 ** 3)
        if gb < 1.0:
            n = min(n, 2)
        elif gb < 2.0:
            n = min(n, 3)
        elif gb < 4.0:
            n = min(n, 4)
    if IS_ANDROID:
        n = min(n, 3)
    return max(floor, min(n, cap))




def _notify_macos(title, message, subtitle=""):
    def _esc(s):
        return str(s).replace('\\', '\\\\').replace('"', '\\"')
    parts = ['display notification "%s"' % _esc(message)]
    if title:
        parts.append('with title "%s"' % _esc(title))
    if subtitle:
        parts.append('subtitle "%s"' % _esc(subtitle))
    script = ' '.join(parts)
    subprocess.Popen(['osascript', '-e', script], **subprocess_no_window_kwargs())
    return True


def _notify_linux(title, message, urgency='normal'):
    sender = shutil.which('notify-send')
    if not sender:
        return False
    args = [sender, '-a', 'B站视频下载工具']
    if urgency in ('low', 'normal', 'critical'):
        args += ['-u', urgency]
    args += [str(title or ''), str(message or '')]
    subprocess.Popen(args, **subprocess_no_window_kwargs())
    return True


def native_notify(title, message, urgency='normal', subtitle=''):
    try:
        if IS_WINDOWS:
            return False
        if IS_MACOS:
            return _notify_macos(title, message, subtitle)
        if IS_ANDROID:
            return False
        return _notify_linux(title, message, urgency)
    except Exception:
        return False


def notification_backend():
    """返回当前平台可用的通知后端名，便于界面显示与自查。"""
    if IS_WINDOWS:
        try:
            import winsdk  # noqa: F401
            return 'winrt'
        except Exception:
            return 'none'
    if IS_MACOS:
        return 'osascript' if shutil.which('osascript') else 'none'
    if IS_ANDROID:
        return 'android'
    return 'notify-send' if shutil.which('notify-send') else 'none'


def beep(kind='info'):
    """播放一声系统提示音。各平台实现不同，失败静默返回 False。"""
    try:
        if IS_WINDOWS:
            import winsound
            tone = winsound.MB_ICONEXCLAMATION if kind == 'warn' else winsound.MB_OK
            winsound.MessageBeep(tone)
            return True
        if IS_MACOS:
            for name in (('Basso.aiff',) if kind == 'warn' else ('Glass.aiff', 'Ping.aiff')):
                p = '/System/Library/Sounds/' + name
                if os.path.exists(p):
                    subprocess.Popen(['afplay', p], **subprocess_no_window_kwargs())
                    return True
            return False
        for cmd in (['canberra-gtk-play', '-i', 'complete'],
                    ['paplay', '/usr/share/sounds/freedesktop/stereo/complete.oga']):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, **subprocess_no_window_kwargs())
                return True
        sys.stdout.write('\a')
        sys.stdout.flush()
        return True
    except Exception:
        return False




def get_safe_temp_dir(base_dir, sub_dir="temp", cache_dir=None, prefer_dir=None):
    import tempfile

    candidates = []

    if cache_dir:
        candidates.append(cache_dir)

    if prefer_dir:
        try:
            drive = os.path.splitdrive(os.path.abspath(prefer_dir))[0]
            if drive:
                candidates.append(os.path.join(drive + os.sep, "_bili_cache"))
        except Exception:
            pass

    if base_dir:
        candidates.append(os.path.join(base_dir, sub_dir))

    if base_dir:
        try:
            drive = os.path.splitdrive(os.path.abspath(base_dir))[0]
            if drive:
                candidates.append(os.path.join(drive + os.sep, "_bili_cache"))
        except Exception:
            pass

    for candidate in candidates:
        resolved = _resolve_ascii_candidate(candidate)
        if resolved and _is_usable_dir(resolved):
            return resolved

    sys_temp = tempfile.gettempdir()
    resolved = _resolve_ascii_candidate(sys_temp)
    return resolved or sys_temp


def move_file_no_copy(src, dst, overwrite=True, logger=None):
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)

    if src == dst:
        return dst

    dst_dir = os.path.dirname(dst)
    if dst_dir:
        os.makedirs(dst_dir, exist_ok=True)

    if os.path.exists(dst):
        if overwrite:
            try:
                os.remove(dst)
            except Exception as _e:
                if logger:
                    logger.warning(f"覆盖前删除目标文件失败：{dst} - {_e}")
        else:
            raise FileExistsError(f"目标文件已存在：{dst}")

    try:
        os.replace(src, dst)
        if logger:
            logger.debug(f"同盘重命名完成（零拷贝）：{src} -> {dst}")
        return dst
    except OSError as e:
        _rename_err = e

    try:
        os.rename(src, dst)
        if logger:
            logger.debug(f"同盘重命名完成（零拷贝）：{src} -> {dst}")
        return dst
    except OSError as e:
        _rename_err = e

    same_volume = False
    try:
        same_volume = os.path.splitdrive(src)[0].lower() == os.path.splitdrive(dst)[0].lower()
    except Exception:
        pass
    if same_volume and logger:
        logger.warning(f"同盘重命名失败（{_rename_err}），回退 shutil.move：{src} -> {dst}")
    elif logger:
        logger.info(f"源与目标跨盘，回退 shutil.move（不可避免的一次搬运）：{src} -> {dst}")

    shutil.move(src, dst)
    return dst


def link_or_copy(src, dst, overwrite=True, logger=None):
    src = os.path.abspath(src)
    dst = os.path.abspath(dst)

    dst_dir = os.path.dirname(dst)
    if dst_dir:
        os.makedirs(dst_dir, exist_ok=True)

    if os.path.exists(dst):
        if overwrite:
            try:
                os.remove(dst)
            except Exception:
                pass
        else:
            return dst

    try:
        os.link(src, dst)
        if logger:
            logger.debug(f"使用硬链接创建副本（零额外空间）：{dst}")
        return dst
    except OSError:
        pass

    shutil.copy2(src, dst)
    if logger:
        logger.debug(f"硬链接不可用，已复制副本：{dst}")
    return dst

