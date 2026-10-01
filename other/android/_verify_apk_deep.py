# Deep-verify the freshly built APK:
#   1. qrgen.pyc is present inside assets/private.tar
#   2. no qrcode/PIL references (they must be absent)
#   3. orientation=portrait and our own icon
#   4. main.pyc / qt_compat.pyc present
import io
import os
import re
import struct
import sys
import tarfile
import zipfile

AND = (r"E:\旧桌面备份\来自：电脑桌面"
       r"\B站视频解析工具V1.8\other\android")
APK = os.path.join(
    AND, "bilidownload-2.2.0-arm64-v8a_armeabi-v7a-debug.apk")

fails = []


def check(name, ok, detail=""):
    print("  %s %s%s" % ("PASS" if ok else "FAIL", name,
                         ("  " + detail) if detail else ""))
    if not ok:
        fails.append(name)


print("=== 1. APK 基本信息 ===")
size = os.path.getsize(APK)
check("APK 存在", os.path.isfile(APK))
check("APK 体积合理", size > 20 * 1024 * 1024,
      "%.1f MB" % (size / 1048576.0))

zf = zipfile.ZipFile(APK)

print()
print("=== 2. assets/private.tar 内容 ===")
tar_names = []
if "assets/private.tar" in zf.namelist():
    data = zf.read("assets/private.tar")
    tf = tarfile.open(fileobj=io.BytesIO(data))
    tar_names = tf.getnames()
    print("  共 %d 个条目" % len(tar_names))
else:
    check("assets/private.tar 存在", False)

for want in ("main.pyc", "qt_compat.pyc", "qrgen.pyc"):
    hit = any(n.endswith(want) for n in tar_names)
    check("包含 %s" % want, hit)

print()
print("  应用代码文件:")
for n in sorted(tar_names):
    if n.endswith((".pyc", ".py", ".ttf", ".png")):
        print("     %s" % n)

print()
print("=== 3. 确认没有 qrcode / PIL（Android 上不可用）===")
bad = [n for n in tar_names
       if re.search(r"(^|/)(qrcode|PIL|Pillow)", n)]
check("未打包 qrcode/PIL", not bad, str(bad[:3]))

print()
print("=== 4. 中文字体 ===")
fonts = [n for n in tar_names if n.endswith(".ttf")]
check("包含中文字体", any("NotoSansSC" in n for n in fonts), str(fonts))

print()
print("=== 5. 图标资源 ===")
icons = [n for n in zf.namelist()
         if "mipmap" in n and n.endswith(".png")]
check("包含 mipmap 图标", len(icons) >= 1,
      "%d 个: %s" % (len(icons), [os.path.basename(i) for i in icons[:3]]))

print()
print("=== 6. 清单：竖屏 + 图标 ===")
# 注意：AndroidManifest.xml 是**二进制 AXML**，
# 直接 decode utf-8/utf-16 找字符串会误判。
# 这里复用 _verify_apk.py 里已验证过的 AXML 解析器。
sys.path.insert(0, AND)
import _verify_apk as va

raw = zf.read("AndroidManifest.xml")

# screenOrientation 属性的数值：
#   1 = SCREEN_ORIENTATION_PORTRAIT（竖屏锁定）
#   0 = LANDSCAPE, -1 = UNSPECIFIED
SCREEN_ORIENTATION = {0: "landscape", 1: "portrait", -1: "unspecified"}
orient_val = va._axml_orientation(raw)
orient = SCREEN_ORIENTATION.get(orient_val, "unknown(%r)" % orient_val)
check("screenOrientation=竖屏", orient == "portrait",
      "数值 %r -> %s" % (orient_val, orient))

strings = va._axml_strings(raw)
check("清单含包名", "cn.bilidown.bilidownload" in strings)
check("清单含 PythonActivity",
      "org.kivy.android.PythonActivity" in strings)

# 图标：aapt2 读到的是 icon='res/mipmap/icon.png'，
# 而 AXML 字符串池里只有资源名（如 'icon'）。
# 两者都查一下，避免因为解析层级不同误判。
has_icon_name = "icon" in strings
icon_res = [n for n in zf.namelist() if "mipmap" in n and n.endswith(".png")]
check("清单引用 icon 资源", has_icon_name)
check("mipmap 图标资源存在", len(icon_res) >= 1, str(icon_res))

print("=== 7. native 库 ===")
libs = [n for n in zf.namelist() if n.startswith("lib/")]
abi = sorted(set(n.split("/")[1] for n in libs if len(n.split("/")) > 2))
check("包含 arm64-v8a", "arm64-v8a" in abi, str(abi))
check("包含 armeabi-v7a", "armeabi-v7a" in abi)

# 有没有 SDL2_ttf 相关
ttf_lib = [n for n in libs if "SDL2_ttf" in n]
check("SDL2_ttf native 库存在", len(ttf_lib) > 0, str(ttf_lib[:2]))

print()
print("FAILURES: %d %s" % (len(fails), fails if fails else ""))
