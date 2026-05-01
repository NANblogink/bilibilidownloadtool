import sys
import os
from cx_Freeze import setup, Executable

# 项目根目录
base_path = os.path.dirname(os.path.abspath(__file__))

# 包含的文件
include_files = []

# 添加ffmpeg目录
ffmpeg_path = os.path.join(base_path, 'ffmpeg')
if os.path.exists(ffmpeg_path):
    include_files.append((ffmpeg_path, 'ffmpeg'))

# 添加bento4目录
bento4_path = os.path.join(base_path, 'bento4')
if os.path.exists(bento4_path):
    include_files.append((bento4_path, 'bento4'))

# 添加logo.ico
icon_path = os.path.join(base_path, 'logo.ico')
if not os.path.exists(icon_path):
    icon_path = None

# 排除的模块
excludes = ['matplotlib', 'pandas', 'numpy', 'scipy', 'tkinter']

# 包含的包
packages = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtWebEngine',
    'requests',
    'qrcode',
    'PIL',
    'Cryptodome',
    'aiohttp',
    'browser_cookie3',
    'brotli',
    'orjson',
    'tkinterdnd2',
]

# 基础设置
base = None
if sys.platform == "win32":
    base = "Win32GUI"  # 隐藏控制台

# 可执行文件配置
executables = [
    Executable(
        script="main.py",
        base=base,
        target_name="BilibiliDownloader_v1.8.exe",
        icon=icon_path,
    )
]

# 打包配置
setup(
    name="BilibiliDownloader",
    version="1.8",
    description="Bilibili Video Downloader",
    options={
        "build_exe": {
            "include_files": include_files,
            "excludes": excludes,
            "packages": packages,
            "optimize": 0,
            "build_exe": "dist",
        }
    },
    executables=executables,
)
