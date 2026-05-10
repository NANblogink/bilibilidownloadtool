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
    import zipfile

    PROJECT_DIR = r"c:\Users\22739\Desktop\B站视频解析工具V1.8\bilibilidownloadtool-master"
    EXE_NAME = "V2.0.0_main"

    os.chdir(PROJECT_DIR)

    for d in ['dist', 'build']:
        if os.path.exists(d):
            shutil.rmtree(d)

    for f in [f'{EXE_NAME}.spec']:
        if os.path.exists(f):
            os.remove(f)

    import PyInstaller.__main__

    sys.argv = [
        'pyinstaller',
        '--noconsole',
        '--onedir',
        '--name', EXE_NAME,
        '--icon=logo.ico',
        '--add-data', 'logo.ico;.',
        '--add-data', 'logo.png;.',
        '--add-data', 'version_info.json;.',
        '--add-data', 'cookie.txt;.',
        '--add-data', 'wbi_cache.json;.',
        '--add-data', 'hevc安装.Appx;.',
        '--add-data', 'ffmpeg;ffmpeg',
        '--add-data', 'bento4;bento4',
        '--noconfirm',
        'main.py'
    ]

    print("=" * 50)
    print("  B站视频解析工具 V2.0.0 构建脚本 (patched)")
    print("=" * 50)
    print("\n[1/3] PyInstaller 打包...")

    PyInstaller.__main__.run()

    dist_dir = os.path.join(PROJECT_DIR, 'dist', EXE_NAME)
    if not os.path.exists(dist_dir):
        print("错误：打包输出目录不存在！")
        sys.exit(1)

    print("\n[1.5/3] 删除mypyc编译扩展（与PyInstaller不兼容）...")
    removed = 0
    for root, dirs, files in os.walk(dist_dir):
        for file in files:
            if '__mypyc' in file and file.endswith('.pyd'):
                file_path = os.path.join(root, file)
                os.remove(file_path)
                removed += 1
    print(f"  已删除 {removed} 个mypyc文件")

    print("\n[2/3] 创建ZIP更新包...")
    zip_path = os.path.join(PROJECT_DIR, 'dist', f'{EXE_NAME}.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(dist_dir))
                zf.write(file_path, arcname)

    zip_size = os.path.getsize(zip_path) / 1048576
    print(f"ZIP创建完成：{zip_path} ({zip_size:.1f} MB)")

    print("\n[3/3] 构建完成！")
    print(f"\n输出文件：")
    print(f"  程序目录: {dist_dir}")
    print(f"  更新包:   {zip_path}")
