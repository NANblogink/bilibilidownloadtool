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
    """可执行文件名：Windows 补 .exe，其余平台原名。

    注意：若传入的名字已带 .exe 后缀（历史上部分调用点如此），
    在非 Windows 平台会得到错误名。这里统一做一次规范化。
    """
    if IS_WINDOWS:
        return name if name.lower().endswith('.exe') else f"{name}.exe"
    if name.lower().endswith('.exe'):
        return name[:-4]
    return name


def tool_names(name):
    """返回该工具在当前平台的候选可执行名（含兜底别名），用于查找。

    打包场景下用户可能拿到别的平台残留的文件名，因此把 .exe 变体也列为候选，
    只在"确认可执行"时才使用。
    """
    base = exe(name)
    if IS_WINDOWS:
        return [base]
    return [base, f"{name}.exe"] if not base.endswith('.exe') else [base]


# 某些Win下Crea
# 该标志报WinErr
# 故命中后本次弃用
_NO_WINDOW_USABLE = True


def note_no_window_failure(exc):
    """记录一次 CREATE_NO_WINDOW 失败；命中 WinError 50 时全局降级。

    返回 True 表示这是可降级的错误（调用方可以去掉该标志重试）。
    """
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
        # BELOW_NORMAL
        return {'creationflags': subprocess.CREATE_NO_WINDOW | 0x00004000}
    if IS_WINDOWS:
        return {'creationflags': 0x00004000}
    return {}


def run_no_window(cmd, timeout=30, text=False, **kwargs):
    """执行子进程并隐藏窗口，遇到 Windows 的 WinError 50 自动降级重试一次。

    ffprobe / powershell 这类探测型调用被这个错误打断时会静默退化成
    "检测失败"，用户看到的是编码/加密判断失灵，因此这里兜一层。
    """
    if not IS_WINDOWS:
        return subprocess.run(cmd, capture_output=True, text=text,
                              timeout=timeout, **kwargs)
    try:
        return subprocess.run(cmd, capture_output=True, text=text, timeout=timeout,
                              **subprocess_no_window_kwargs(), **kwargs)
    except OSError as e:
        if not note_no_window_failure(e):
            raise
        # 去掉该标志重试
        # 但总好过功能直接失效。
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
                # 按字节读Proxy
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
    """检测系统是否有可用的GPU（NVIDIA/AMD/Intel），返回 (has_gpu, gpu_type, gpu_name)
    gpu_type: 'nvidia', 'amd', 'intel', 或 None
    """
    if IS_WINDOWS:
        # 方法1 Get-Cim
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

        # 方法2用wmic后备
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

        # 方法3 nvidia
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
    """检测路径是否包含非ASCII字符（如中文用户名/中文安装路径）"""
    if not path:
        return False
    return any(ord(c) > 127 for c in path)


def to_short_path(path):
    """将路径转换为Windows 8.3短路径名，解决C++工具无法处理中文路径的问题

    Windows API GetShortPathNameW 可将 C:\\Users\\廖武彬\\AppData\\Local\\Temp
    转换为 C:\\Users\\LIAOWU~1\\AppData\\Local\\Temp 这种纯ASCII短路径

    优点：
    - 原生支持，无需复制文件，无需管理员权限
    - 纯ASCII，所有C++工具(mp4decrypt/ffmpeg/ffprobe)都能处理
    - 对所有已存在的文件/目录都有效

    注意：
    - 文件/目录必须存在才能调用，否则返回原路径
    - NTFS默认支持8.3短文件名，部分系统可能禁用（返回原路径由调用方兜底）
    - 网络路径不支持8.3短文件名

    Args:
        path: 待转换的路径（可能含中文）

    Returns:
        转换后的ASCII短路径；转换失败或非Windows平台返回原路径
    """
    if not IS_WINDOWS or not path:
        return path
    # 全ASCII无需转换
    if not has_non_ascii(path):
        return path
    try:
        import ctypes
        from ctypes import wintypes
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        GetShortPathNameW.restype = wintypes.DWORD

        # 先取所需缓冲区长度
        buf_size = GetShortPathNameW(path, None, 0)
        if buf_size == 0:
            return path  # 转换失败或短名禁用

        # 实际获取短路径
        buf = ctypes.create_unicode_buffer(buf_size)
        result = GetShortPathNameW(path, buf, buf_size)
        if result > 0:
            short_path = buf.value
            # 确认确为纯ASCII
            if not has_non_ascii(short_path):
                return short_path
        return path
    except Exception:
        return path


def _is_usable_dir(path):
    """目录是否存在、可写、且不依赖中文路径（供 C++ 工具使用）。"""
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
    """返回可用的 ASCII 路径（必要时转 8.3 短路径），不可用则返回 None。"""
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


# --------------------------------------------------------------------------
# 统一平台行为 API
#
# 收敛Win专有调用
# 如explorer
# 各平台等价实现
# 失败不抛返回bool
# --------------------------------------------------------------------------


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
            # 无xdg-open降级
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
    """在文件管理器中定位文件（Windows 选中 / macOS 选中 / Linux 打开所在目录）。

    select=True 表示尽量高亮该文件本身；平台不支持时退化为打开父目录。
    """
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
        # Linux开目录
        target = path if os.path.isdir(path) else os.path.dirname(path)
        return open_path(target)
    except Exception:
        return False


def open_terminal(command=None, path=None):
    """打开一个终端窗口（可选在其中执行命令）。"""
    try:
        if IS_WINDOWS:
            if command:
                # cmd /k保持窗口不关
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
        # 按可用性试常见终端
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
        # 先温和终止超时强杀
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
    """让子进程独立成组，便于后续整组终止（POSIX）。

    ffmpeg/播放器等长驻子进程需要它，否则 kill_process_tree 无法连带清理。
    """
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
            # shutdown收
            minutes = max(1, int(round(delay_seconds / 60.0)))
            subprocess.Popen(['sudo', '-n', 'shutdown', '-h', '+%d' % minutes],
                             **subprocess_no_window_kwargs())
            return True, '已安排关机（如有提示请输入密码）'
        if IS_ANDROID:
            return False, '当前平台不支持自动关机'
        # 优先systemd
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
        # POSIX
        import psutil
        proc = psutil.Process(pid) if pid else psutil.Process()
        proc.nice(10)
        return True
    except Exception:
        return False


def available_memory_bytes():
    """返回可用物理内存字节数，获取不到返回 None。

    用于在移动端/低配设备上自适应并发度，避免把机器打崩。
    """
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
    """逻辑 CPU 数，失败回退 2（保守值）。"""
    try:
        return max(1, os.cpu_count() or 2)
    except Exception:
        return 2


def recommended_concurrency(explicit=None, cap=8, floor=1):
    """按设备能力推荐并发数。

    Android / 低内存设备上主动降低并发，避免 OOM 与系统卡顿。
    """
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


# --------------------------------------------------------------------------
# 跨平台桌面通知
#
# Win走WinRT
#notify-send
# 绝不影响主流程。
# --------------------------------------------------------------------------


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
    # a为应用名u为紧急度
    args = [sender, '-a', 'B站视频下载工具']
    if urgency in ('low', 'normal', 'critical'):
        args += ['-u', urgency]
    args += [str(title or ''), str(message or '')]
    subprocess.Popen(args, **subprocess_no_window_kwargs())
    return True


def native_notify(title, message, urgency='normal', subtitle=''):
    """发送一条系统级桌面通知。返回 bool 表示是否成功发起。

    Windows 的 WinRT 实现留在 ui.py（需要保留 Toast 动作/进度条能力），
    这里只提供 POSIX 平台实现，供 ui.py 统一入口调用。
    """
    try:
        if IS_WINDOWS:
            return False  # 由_winrt接管
        if IS_MACOS:
            return _notify_macos(title, message, subtitle)
        if IS_ANDROID:
            return False  # 由Android接管
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
            #afplay为macOS
            for name in (('Basso.aiff',) if kind == 'warn' else ('Glass.aiff', 'Ping.aiff')):
                p = '/System/Library/Sounds/' + name
                if os.path.exists(p):
                    subprocess.Popen(['afplay', p], **subprocess_no_window_kwargs())
                    return True
            return False
        # 优先paplay
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
    """获取 ASCII 安全的临时目录，用于调用 C++ 工具(mp4decrypt/ffmpeg等)时避免中文路径问题。

    回退顺序（按优先级）：
    1. 用户在设置里指定的缓存目录（cache_dir）
    2. prefer_dir 所在盘符的根级 ASCII 目录（如 E:\\_bili_cache）——
       关键：优先与"下载目标盘"同盘，避免把临时文件中转到系统盘(C:)把 C 盘写满
    3. base_dir/sub_dir（程序目录下的 temp）
    4. base_dir 所在盘符的根级 ASCII 目录
    5. 系统 Temp

    注意：C++ 工具无法处理含中文的路径，而 8.3 短路径在部分系统/卷上被禁用，
    因此这里会主动构造盘符根目录下的纯 ASCII 目录作为首选回退，
    而不是直接落到系统 Temp。

    Args:
        base_dir: 基础目录（通常是程序工作目录）
        sub_dir: 程序目录下的子目录名（如 "temp"）
        cache_dir: 用户配置的缓存目录（优先使用）
        prefer_dir: 期望同盘的目录（通常是下载保存路径）

    Returns:
        ASCII 安全的临时目录路径
    """
    import tempfile

    candidates = []

    # 1. 用户配置的缓存目录
    if cache_dir:
        candidates.append(cache_dir)

    # 同盘ASCII免占C
    if prefer_dir:
        try:
            drive = os.path.splitdrive(os.path.abspath(prefer_dir))[0]
            if drive:
                candidates.append(os.path.join(drive + os.sep, "_bili_cache"))
        except Exception:
            pass

    # 程序目录下的temp
    if base_dir:
        candidates.append(os.path.join(base_dir, sub_dir))

    # 4. 程序所在盘符根目录
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

    # 5. 兜底：系统 Temp
    sys_temp = tempfile.gettempdir()
    resolved = _resolve_ascii_candidate(sys_temp)
    return resolved or sys_temp


def move_file_no_copy(src, dst, overwrite=True, logger=None):
    """把 src 移动到 dst，优先「同盘重命名」，绝不做无谓的复制+删除。

    设计目标（用户明确要求）：
        "下载到目标文件夹所在盘，然后移动到目标文件夹，只存一次，
         必须是移动不能复制再删除。"

    行为：
        1. 先尝试 os.replace / os.rename —— 同一卷上是原子操作，
           零额外磁盘写入、零额外占用，瞬间完成（这才是真正的"移动"）。
        2. 仅当重命名确实失败（源与目标跨卷 / 跨设备）时，才回退到
           shutil.move；shutil.move 在同盘时内部也是 rename，
           跨盘时才复制+删除，属于无法避免的情况。
        3. 目标已存在时，先删除再移动（避免 rename 在某些平台失败）。

    :param src: 源文件路径
    :param dst: 目标文件路径
    :param overwrite: 目标存在时是否覆盖（默认 True）
    :param logger: 可选 logger，用于记录实际采用的是移动还是回退复制
    :return: 最终文件路径（成功）
    :raises: 移动失败时抛出最后一个异常
    """
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

    # 同盘原子重命名零拷贝
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

    # 跨卷才复制
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
    """为「工具不支持中文路径」等场景准备一份可访问副本，但尽量不额外占用磁盘。

    优先硬链接（同一卷上零额外空间、瞬间完成，数据只存一份），
    失败才回退 shutil.copy2（跨卷或文件系统不支持硬链接时）。

    注意：硬链接与原文件共享同一份数据，删除其中任意一个都不会丢失数据，
    但修改其一会影响另一个。此函数仅用于「只读副本」场景
    （如交给 ffmpeg/mp4decrypt 读取），不可用于需要独立修改的副本。

    :param src: 源文件
    :param dst: 目标副本路径
    :param overwrite: 目标存在时是否覆盖
    :return: dst
    """
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

    # 硬链接同卷零空间
    try:
        os.link(src, dst)
        if logger:
            logger.debug(f"使用硬链接创建副本（零额外空间）：{dst}")
        return dst
    except OSError:
        pass

    # 2) 回退：真实复制
    shutil.copy2(src, dst)
    if logger:
        logger.debug(f"硬链接不可用，已复制副本：{dst}")
    return dst

