"""检查桌面版 DownloadManager 的接口契约，供 Kivy 端正确桥接。"""
import io
import os
import re

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
OUT = os.path.join(ROOT, "other", "android", "_api_report.txt")
L = []


def w(s=""):
    L.append(str(s))


# ---------------- downloader ----------------
p = os.path.join(ROOT, "core", "downloader.py")
src = io.open(p, encoding="utf-8").read()
w("=== core/downloader.py ===")
for m in re.finditer(r"^class (\w+)\(([^)]*)\):", src, re.M):
    w(f"  class {m.group(1)}({m.group(2)})")
w()
w("  pyqtSignal 声明:")
for m in re.finditer(r"^\s{4}(\w+)\s*=\s*pyqtSignal\(([^)]*)\)", src, re.M):
    w(f"    {m.group(1)} = pyqtSignal({m.group(2)})")
w()

i = src.find("def start_download")
seg = src[i:i + 14000]
keys = sorted(set(re.findall(r"(?:params|download_params)\.get\(\s*['\"]([a-z_0-9]+)['\"]", seg)))
w("  start_download 读取的参数字段:")
for k in keys:
    w(f"    - {k}")
w()

# save_path与ep
for pat in [r"save_path", r"episodes", r"video_info"]:
    n = len(re.findall(pat, seg))
    w(f"  '{pat}' 出现 {n} 次")
w()

# ---------------- parser ----------------
p2 = os.path.join(ROOT, "parsers", "bilibili_parser.py")
src2 = io.open(p2, encoding="utf-8").read()
w("=== parsers/bilibili_parser.py 公开方法 ===")
for m in re.finditer(r"^    def ([a-z]\w+)\(self([^)]*)\)", src2, re.M):
    name, args = m.group(1), m.group(2).strip()
    if name.startswith("_"):
        continue
    w(f"    {name}({args[:90]})")
w()

# parse_media结构
i2 = src2.find("def parse_media(")
seg2 = src2[i2:i2 + 30000]
keys2 = sorted(set(re.findall(r"result\[\s*['\"]([a-z_0-9]+)['\"]\s*\]\s*=", seg2)))
w("  parse_media 结果里出现的字段:")
for k in keys2:
    w(f"    - {k}")
w()
ret = sorted(set(re.findall(r"return\s*\{", seg2)))
w(f"  return dict 次数: {len(ret)}")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
