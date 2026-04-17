# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 直接指定所有需要的文件
added_files = [
    ('ffmpeg/bin', 'ffmpeg/bin'),
    ('bento4/Bento4-SDK-1-6-0-641.x86_64-microsoft-win32/bin', 'bento4/bin'),
    ('logo.ico', '.'),
    ('logo.png', '.')
]

# 分析主文件
a = Analysis(['main.py'],
             pathex=['.'],
             binaries=[],
             datas=added_files,
             hiddenimports=[
                 'PyQt5.QtCore',
                 'PyQt5.QtGui',
                 'PyQt5.QtWidgets',
                 'PyQt5.QtNetwork',
                 'PyQt5.QtWebEngineWidgets',
                 'PyQt5.QtWebEngineCore',
                 'PyQt5.QtWebChannel',
                 'requests',
                 'aiohttp',
                 'orjson',
                 'cachetools',
                 'dateutil',
                 'Crypto',
                 'json',
                 'threading',
                 'time',
                 'os',
                 'sys'
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

# 创建PYZ文件
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# 创建可执行文件，完全禁用压缩
executable = EXE(pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='B站视频解析工具V1.9修复版',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon='logo.ico'
    )
