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
        'win32': 'https://github.com/nicholasgasior/bento4/releases/download/v1-6-0-641/Bento4-Win64-v1-6-0-641.zip',
        'darwin': 'https://github.com/nicholasgasior/bento4/releases/download/v1-6-0-641/Bento4-MacOSX-v1-6-0-641.zip',
        'linux': 'https://github.com/nicholasgasior/bento4/releases/download/v1-6-0-641/Bento4-Linux-x86_64-v1-6-0-641.zip',
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


def get_safe_temp_dir(base_dir, sub_dir="temp"):
    """获取ASCII安全的临时目录，用于调用C++工具(mp4decrypt/ffmpeg等)时避免中文路径问题

    多级回退策略（按优先级）：
    1. base_dir/sub_dir（如程序目录/temp）- 不含中文时直接用
    2. base_dir/sub_dir 的8.3短路径名 - 含中文时尝试转换
    3. 系统Temp目录 - 不含中文时使用
    4. 系统Temp目录的8.3短路径名 - 含中文时尝试转换
    5. %PUBLIC%/bili_temp（C:\\Users\\Public，纯ASCII且所有用户可写）
    6. 兜底：base_dir所在驱动器根的 _bili_temp（可能需要管理员权限）

    Args:
        base_dir: 基础目录（通常是程序工作目录）
        sub_dir: 子目录名（如"temp"）

    Returns:
        ASCII安全的临时目录路径
    """
    import tempfile

    # 候选目录列表，按优先级排序
    candidates = [
        os.path.join(base_dir, sub_dir),
        tempfile.gettempdir(),
    ]

    for candidate in candidates:
        try:
            os.makedirs(candidate, exist_ok=True)
        except Exception:
            continue

        # 不含中文，直接使用
        if not has_non_ascii(candidate):
            return candidate

        # 含中文，尝试转换为8.3短路径
        short = to_short_path(candidate)
        if short != candidate and not has_non_ascii(short):
            return short

    # 上述方案都失败（含中文且8.3被禁用），尝试 %PUBLIC% 目录
    # C:\Users\Public 总是纯ASCII，且所有用户都有写权限
    try:
        public_dir = os.environ.get('PUBLIC', r'C:\Users\Public')
        if not has_non_ascii(public_dir):
            public_temp = os.path.join(public_dir, 'bili_temp')
            os.makedirs(public_temp, exist_ok=True)
            if not has_non_ascii(public_temp):
                return public_temp
    except Exception:
        pass

    # 最后兜底：驱动器根的 _bili_temp（可能需要管理员权限）
    try:
        drive = os.path.splitdrive(base_dir)[0] or 'C:'
        fallback = os.path.join(drive, '_bili_temp')
        os.makedirs(fallback, exist_ok=True)
        return fallback
    except Exception:
        # 实在没办法，返回系统Temp（即使含中文）
        return tempfile.gettempdir()
