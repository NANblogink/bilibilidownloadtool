import os
import shutil
import zipfile

base = r"c:\Users\22739\Desktop\B站视频解析工具V1.8\bilibilidownloadtool-master"
dist_main = os.path.join(base, "dist", "V2.0.1_main")

shutil.copytree(os.path.join(base, "ffmpeg"), os.path.join(dist_main, "ffmpeg"), dirs_exist_ok=True)
print("ffmpeg copied")

shutil.copytree(os.path.join(base, "bento4"), os.path.join(dist_main, "bento4"), dirs_exist_ok=True)
print("bento4 copied")

shutil.copy2(os.path.join(base, "dist", "V2.0_uninstaller.exe"), os.path.join(dist_main, "V2.0_uninstaller.exe"))
print("uninstaller copied")

for f in ["logo.ico", "logo.png"]:
    src = os.path.join(base, f)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(dist_main, f))
        print(f"{f} copied")

zip_path = os.path.join(base, "dist", "V2.0.1_main.zip")
if os.path.exists(zip_path):
    os.remove(zip_path)

print("Creating zip...")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(dist_main):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, os.path.dirname(dist_main))
            zf.write(file_path, arcname)

zip_size = os.path.getsize(zip_path)
print(f"Zip created: {zip_size / 1024 / 1024:.1f} MB")
