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
            proxy_server = winreg.QueryValueEx(internet_settings, 'ProxyServer')[0]
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
