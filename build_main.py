import os
import shutil
import subprocess
import sys
import zipfile

APP_NAME = "B站视频解析工具"
APP_VERSION = "2.0.1"
EXE_NAME = f"V{APP_VERSION}_main"
PROJECT_DIR = r"c:\Users\22739\Desktop\B站视频解析工具V1.8\bilibilidownloadtool-master"

def clean_pycache():
    paths_to_clean = []
    for path in sys.path:
        if os.path.isdir(path) and 'site-packages' in path:
            paths_to_clean.append(path)
    
    for base_path in paths_to_clean:
        print(f"清理 {base_path} 中的 __pycache__ ...")
        for root, dirs, files in os.walk(base_path):
            for d in dirs:
                if d == '__pycache__':
                    cache_dir = os.path.join(root, d)
                    try:
                        shutil.rmtree(cache_dir)
                    except Exception as e:
                        print(f"  无法删除 {cache_dir}: {e}")
            for f in files:
                if f.endswith('.pyc'):
                    pyc_file = os.path.join(root, f)
                    try:
                        os.remove(pyc_file)
                    except Exception as e:
                        print(f"  无法删除 {pyc_file}: {e}")
    print("字节码缓存清理完成")

def run_pyinstaller():
    os.chdir(PROJECT_DIR)
    
    for d in ['dist', 'build']:
        if os.path.exists(d):
            shutil.rmtree(d)
    
    spec_file = f'{EXE_NAME}.spec'
    if os.path.exists(spec_file):
        os.remove(spec_file)
    
    cmd = [
        sys.executable, '-B', '-m', 'PyInstaller',
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
    
    print(f"运行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    return result.returncode

def create_zip():
    dist_dir = os.path.join(PROJECT_DIR, 'dist', EXE_NAME)
    if not os.path.exists(dist_dir):
        print(f"错误：找不到 {dist_dir}")
        return False
    
    zip_path = os.path.join(PROJECT_DIR, 'dist', f'{EXE_NAME}.zip')
    print(f"正在创建 {zip_path} ...")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dist_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, os.path.dirname(dist_dir))
                zf.write(file_path, arcname)
    
    zip_size = os.path.getsize(zip_path) / 1048576
    print(f"ZIP创建完成：{zip_path} ({zip_size:.1f} MB)")
    return True

def main():
    clean_pycache()
    
    print("\n" + "=" * 50)
    print(f"  {APP_NAME} V{APP_VERSION} 构建脚本")
    print("=" * 50 + "\n")
    
    print("[1/3] PyInstaller 打包...")
    ret = run_pyinstaller()
    if ret != 0:
        print(f"打包失败！退出码: {ret}")
        sys.exit(ret)
    
    print("\n[2/3] 创建ZIP更新包...")
    if not create_zip():
        print("ZIP创建失败！")
        sys.exit(1)
    
    print("\n[3/3] 构建完成！")
    print(f"\n输出文件：")
    print(f"  程序目录: {os.path.join(PROJECT_DIR, 'dist', EXE_NAME)}")
    print(f"  更新包:   {os.path.join(PROJECT_DIR, 'dist', f'{EXE_NAME}.zip')}")
    print(f"\n下一步：")
    print(f"  1. 将 {EXE_NAME}.zip 上传到服务器或对象存储")
    print(f"  2. 通过管理API更新 download_url 指向该zip文件")
    print(f"  3. 运行 build_installer_patched.py 构建安装程序（可选）")

if __name__ == '__main__':
    main()
