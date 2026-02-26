import os
import sys
import subprocess
import shutil
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def add_to_path(path):
    if not os.path.exists(path):
        return False
    if is_admin():
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment', 0, winreg.KEY_ALL_ACCESS)
            current_path, _ = winreg.QueryValueEx(key, 'PATH')
            if path not in current_path:
                new_path = current_path + ';' + path
                winreg.SetValueEx(key, 'PATH', 0, winreg.REG_EXPAND_SZ, new_path)
                winreg.CloseKey(key)
                return True
            return False
        except Exception:
            return False
    else:
        return False

def check_ffmpeg():
    ffmpeg_exec = shutil.which('ffmpeg')
    if ffmpeg_exec and os.path.exists(ffmpeg_exec):
        try:
            result = subprocess.run([ffmpeg_exec, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True, ffmpeg_exec
        except Exception:
            pass
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_local = os.path.join(current_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')
    if os.path.exists(ffmpeg_local):
        try:
            result = subprocess.run([ffmpeg_local, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return True, ffmpeg_local
        except Exception:
            pass
    return False, None

def fix_ffmpeg():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_bin_path = os.path.join(current_dir, 'ffmpeg', 'bin')
    if os.path.exists(os.path.join(ffmpeg_bin_path, 'ffmpeg.exe')):
        add_to_path(ffmpeg_bin_path)
        return check_ffmpeg()
    return False, None

def check_python_version():
    version = sys.version_info
    return version.major >= 3 and version.minor >= 6

def check_dependencies():
    missing = []
    try:
        import requests
    except ImportError:
        missing.append('requests')
    try:
        from PyQt5.QtWidgets import QApplication
    except ImportError:
        missing.append('PyQt5')
    try:
        import browser_cookie3
    except ImportError:
        missing.append('browser_cookie3')
    return missing

def install_dependencies():
    missing = check_dependencies()
    if not missing:
        return True
    for pkg in missing:
        try:
            subprocess.run([sys.executable, '-m', 'pip', 'install', pkg], check=True, capture_output=True, text=True)
        except Exception:
            pass
    return len(check_dependencies()) == 0

def check_environment():
    python_ok = check_python_version()
    ffmpeg_ok, ffmpeg_path = check_ffmpeg()
    if not ffmpeg_ok:
        ffmpeg_ok, ffmpeg_path = fix_ffmpeg()
    dependencies_ok = install_dependencies()
    return {
        'python': {
            'ok': python_ok,
            'version': f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}'
        },
        'ffmpeg': {
            'ok': ffmpeg_ok,
            'path': ffmpeg_path
        },
        'dependencies': {
            'ok': dependencies_ok,
            'missing': check_dependencies()
        },
        'all_ok': python_ok and ffmpeg_ok and dependencies_ok
    }

if __name__ == "__main__":
    result = check_environment()
    print('环境检查结果:')
    print(f'Python版本: {result["python"]["version"]} - {"OK" if result["python"]["ok"] else "需要Python 3.6+"}')
    print(f'FFmpeg: {result["ffmpeg"]["path"] if result["ffmpeg"]["path"] else "未找到"} - {"OK" if result["ffmpeg"]["ok"] else "需要修复"}')
    print(f'依赖包: {"全部安装" if result["dependencies"]["ok"] else "缺失: " + str(result["dependencies"]["missing"])}')
    print(f'整体状态: {"就绪" if result["all_ok"] else "需要修复"}')
