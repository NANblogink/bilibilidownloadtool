import dis
import sys
import os

_original_get_const_info = dis._get_const_info

def _patched_get_const_info(const_index, const_list):
    try:
        return _original_get_const_info(const_index, const_list)
    except IndexError:
        return const_index, repr(const_index)

dis._get_const_info = _patched_get_const_info

if __name__ == '__main__':
    import shutil

    PROJECT_DIR = r"c:\Users\22739\Desktop\B站视频解析工具V1.8\bilibilidownloadtool-master"
    EXE_NAME = "V2.0.1_installer"

    os.chdir(PROJECT_DIR)

    for f in [f'{EXE_NAME}.spec']:
        if os.path.exists(f):
            os.remove(f)

    import PyInstaller.__main__

    sys.argv = [
        'pyinstaller',
        '--noconsole',
        '--onefile',
        '--name', EXE_NAME,
        '--icon=logo.ico',
        '--add-data', 'logo.ico;.',
        '--add-data', 'logo.png;.',
        '--add-data', 'dist/V2.0.1_main.zip;.',
        '--noconfirm',
        'installer.py'
    ]

    print("=" * 50)
    print("  B站视频解析工具 V2.0.1 安装程序构建")
    print("=" * 50)

    PyInstaller.__main__.run()

    print("\n安装程序构建完成！")
    print(f"输出: {os.path.join(PROJECT_DIR, 'dist', EXE_NAME + '.exe')}")
