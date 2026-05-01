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
    print("开始检查FFmpeg...")
    # 检查系统PATH中的ffmpeg
    ffmpeg_exec = shutil.which('ffmpeg')
    print(f"系统PATH中的ffmpeg: {ffmpeg_exec}")
    if ffmpeg_exec and os.path.exists(ffmpeg_exec):
        try:
            print(f"尝试执行系统ffmpeg: {ffmpeg_exec}")
            result = subprocess.run([ffmpeg_exec, '-version'], capture_output=True, text=False, timeout=10)
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
            print(f"系统ffmpeg执行返回码: {result.returncode}")
            if result.returncode == 0:
                print(f"系统ffmpeg版本: {stdout[:100]}...")
                return True, ffmpeg_exec
            else:
                print(f"系统ffmpeg执行失败: {stderr[:100]}...")
        except Exception as e:
            print(f"执行系统ffmpeg时出错: {str(e)}")
    
    # 检查本地ffmpeg
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ffmpeg_local = os.path.join(current_dir, 'ffmpeg', 'bin', 'ffmpeg.exe')
    print(f"本地ffmpeg路径: {ffmpeg_local}")
    print(f"本地ffmpeg文件是否存在: {os.path.exists(ffmpeg_local)}")
    if os.path.exists(ffmpeg_local):
        try:
            print(f"尝试执行本地ffmpeg: {ffmpeg_local}")
            result = subprocess.run([ffmpeg_local, '-version'], capture_output=True, text=False, timeout=10)
            stdout = result.stdout.decode('utf-8', errors='replace')
            stderr = result.stderr.decode('utf-8', errors='replace')
            print(f"本地ffmpeg执行返回码: {result.returncode}")
            if result.returncode == 0:
                print(f"本地ffmpeg版本: {stdout[:100]}...")
                return True, ffmpeg_local
            else:
                print(f"本地ffmpeg执行失败: {stderr[:100]}...")
        except Exception as e:
            print(f"执行本地ffmpeg时出错: {str(e)}")
    
    print("未找到可用的FFmpeg")
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
        import aiohttp
    except ImportError:
        missing.append('aiohttp')
    try:
        import Crypto
    except ImportError:
        missing.append('pycryptodome')
    try:
        import brotli
    except ImportError:
        missing.append('brotli')
    try:
        import browser_cookie3
    except ImportError:
        missing.append('browser-cookie3')
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        missing.append('PyQt5[webengine]')
    return missing

def install_dependencies():
    missing = check_dependencies()
    if not missing:
        return True
    for pkg in missing:
        try:
            install_pkg = pkg
            if pkg == 'browser-cookie3':
                install_pkg = 'browser_cookie3'
            subprocess.run([sys.executable, '-m', 'pip', 'install', install_pkg], check=True, capture_output=True, text=True)
        except Exception as e:
            print(f"安装 {pkg} 失败: {str(e)}")
            pass
    return len(check_dependencies()) == 0

def check_network():
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        response = requests.get('https://www.bilibili.com', timeout=10, verify=False, headers=headers)
        print(f"网络检查响应状态码: {response.status_code}")
        return 200 <= response.status_code < 300 or response.status_code == 412
    except Exception as e:
        print(f"网络检查失败: {str(e)}")
        try:
            response = requests.get('https://www.baidu.com', timeout=10, verify=False, headers=headers)
            print(f"备用网络检查响应状态码: {response.status_code}")
            return 200 <= response.status_code < 300 or response.status_code == 412
        except Exception as e2:
            print(f"备用网络检查也失败: {str(e2)}")
            return False

def check_write_permission():
    try:
        test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_write.txt')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return True
    except Exception:
        return False

def check_environment():
    python_ok = check_python_version()
    ffmpeg_ok, ffmpeg_path = check_ffmpeg()
    if not ffmpeg_ok:
        ffmpeg_ok, ffmpeg_path = fix_ffmpeg()
    dependencies_ok = install_dependencies()
    network_ok = check_network()
    write_ok = check_write_permission()
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
        'network': {
            'ok': network_ok
        },
        'write_permission': {
            'ok': write_ok
        },
        'all_ok': python_ok and ffmpeg_ok and dependencies_ok and network_ok and write_ok
    }

if __name__ == "__main__":
    result = check_environment()
    print('环境检查结果:')
    print(f'Python版本: {result["python"]["version"]} - {"OK" if result["python"]["ok"] else "需要Python 3.6+"}')
    print(f'FFmpeg: {result["ffmpeg"]["path"] if result["ffmpeg"]["path"] else "未找到"} - {"OK" if result["ffmpeg"]["ok"] else "需要修复"}')
    print(f'依赖包: {"全部安装" if result["dependencies"]["ok"] else "缺失: " + str(result["dependencies"]["missing"])}')
    print(f'网络连接: {"OK" if result["network"]["ok"] else "需要检查网络"}')
    print(f'写入权限: {"OK" if result["write_permission"]["ok"] else "需要检查权限"}')
    print(f'整体状态: {"就绪" if result["all_ok"] else "需要修复"}')
