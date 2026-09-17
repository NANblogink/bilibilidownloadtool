import os
import sys
import subprocess

IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'
IS_LINUX = sys.platform.startswith('linux')


def exe(name):
    if IS_WINDOWS:
        return f"{name}.exe"
    return name


def subprocess_no_window_kwargs():
    if IS_WINDOWS:
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def subprocess_low_priority_kwargs():
    """返回低优先级子进程的创建参数，用于ffmpeg等CPU密集型任务，降低CPU噪音但不降速"""
    if IS_WINDOWS:
        # BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
        return {'creationflags': subprocess.CREATE_NO_WINDOW | 0x00004000}
    return {}


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
                # ProxyServer可能包含非UTF-8字符，尝试用原始字节读取
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
        # 方法1: 优先用PowerShell Get-CimInstance（wmic在新版Windows可能弃用）
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
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

        # 方法2: 尝试wmic作为后备
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

        # 方法3: 用nvidia-smi专门检测NVIDIA GPU（最可靠）
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
    # 路径不含非ASCII字符，无需转换
    if not has_non_ascii(path):
        return path
    try:
        import ctypes
        from ctypes import wintypes
        GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
        GetShortPathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
        GetShortPathNameW.restype = wintypes.DWORD

        # 首次调用获取所需缓冲区长度
        buf_size = GetShortPathNameW(path, None, 0)
        if buf_size == 0:
            return path  # 转换失败（文件不存在或8.3短文件名被禁用）

        # 实际获取短路径
        buf = ctypes.create_unicode_buffer(buf_size)
        result = GetShortPathNameW(path, buf, buf_size)
        if result > 0:
            short_path = buf.value
            # 确认转换后路径确实为纯ASCII（罕见情况下仍含非ASCII）
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

    # 2. 与下载目标同盘的 ASCII 目录（避免占用 C 盘）
    if prefer_dir:
        try:
            drive = os.path.splitdrive(os.path.abspath(prefer_dir))[0]
            if drive:
                candidates.append(os.path.join(drive + os.sep, "_bili_cache"))
        except Exception:
            pass

    # 3. 程序目录下的 temp
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

