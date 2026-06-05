# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import shutil

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('logo.png', '.'),
        ('logo.ico', '.'),
        ('version_info.json', '.'),
        ('ffmpeg', 'ffmpeg'),
        ('bento4', 'bento4'),
    ],
    hiddenimports=[
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngine',
        'PyQt5.QtNetwork',
        'PyQt5.sip',
        'requests',
        'qrcode',
        'qrcode.image.pil',
        'PIL',
        'PIL.Image', 'PIL.ImageOps', 'PIL.ImageDraw', 'PIL.ImageFont',
        'Cryptodome',
        'Cryptodome.Cipher',
        'Cryptodome.Cipher.AES',
        'Cryptodome.Util',
        'Cryptodome.Util.Padding',
        'aiohttp',
        'brotli',
        'brotli.asgi',
        'orjson',
        'browser_cookie3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'pandas', 'numpy', 'scipy',
        'tkinterdnd2', 'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# GUI主程序 (console=False)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BilibiliDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon='logo.ico',
)

# CLI命令行工具 (console=True，可通过 bilibilidownloadtool 命令启动)
cli_exe = EXE(
    pyz,
    a.scripts + [('bilibilidownloadtool.py', 'cli.py', 'PYSOURCE')],
    [],
    exclude_binaries=True,
    name='bilibilidownloadtool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon='logo.ico',
)

coll = COLLECT(
    exe,
    cli_exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='BilibiliDownloader',
)

app = BUNDLE(
    coll,
    name='BilibiliDownloader.app',
    icon='logo.ico',
    bundle_identifier='com.bilibili.downloader',
    info_plist={
        'CFBundleName': 'BilibiliDownloader',
        'CFBundleDisplayName': 'B站视频解析下载工具',
        'CFBundleVersion': '2.0.3',
        'CFBundleShortVersionString': '2.0.3',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '10.15',
        'NSAppleEventsUsageDescription': '需要访问浏览器以获取Cookie',
        'com.apple.security.cs.allow-jit': True,
        'com.apple.security.cs.allow-unsigned-executable-memory': True,
        'com.apple.security.cs.disable-library-validation': True,
    },
)
