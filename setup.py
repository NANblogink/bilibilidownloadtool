import sys
import os
from cx_Freeze import setup, Executable

base_path = os.path.dirname(os.path.abspath(__file__))

include_files = []

ffmpeg_path = os.path.join(base_path, 'ffmpeg')
if os.path.exists(ffmpeg_path):
    include_files.append((ffmpeg_path, 'ffmpeg'))

bento4_path = os.path.join(base_path, 'bento4')
if os.path.exists(bento4_path):
    include_files.append((bento4_path, 'bento4'))

icon_path = None
if sys.platform == 'win32':
    icon_path = os.path.join(base_path, 'logo.ico')
    if not os.path.exists(icon_path):
        icon_path = None
elif sys.platform == 'darwin':
    icon_path = os.path.join(base_path, 'logo.icns')
    if not os.path.exists(icon_path):
        icon_path = None

excludes = ['matplotlib', 'pandas', 'numpy', 'scipy']

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
]

if sys.platform == 'win32':
    packages.append('tkinterdnd2')

base = None
if sys.platform == "win32":
    base = "Win32GUI"

if sys.platform == 'darwin':
    target_name = "BilibiliDownloader"
elif sys.platform == 'win32':
    target_name = "BilibiliDownloader_v1.8.exe"
else:
    target_name = "BilibiliDownloader"

executables = [
    Executable(
        script="main.py",
        base=base,
        target_name=target_name,
        icon=icon_path,
    )
]

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
