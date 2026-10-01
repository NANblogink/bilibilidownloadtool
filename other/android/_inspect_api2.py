"""弄清桌面版解析结果的真实数据结构，以及核心模块对 PyQt 的依赖程度。"""
import io
import os
import re

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
OUT = os.path.join(ROOT, "other", "android", "_api_report2.txt")
L = []


def w(s=""):
    L.append(str(s))


#1) 调parse_media
ui = io.open(os.path.join(ROOT, "ui.py"), encoding="utf-8").read()
w("=== ui.py 中 parse_media 的调用方式 ===")
for m in re.finditer(r"parse_media\(", ui):
    s = max(0, m.start() - 200)
    seg = ui[s:m.start() + 420]
    ln = ui[:m.start()].count("\n") + 1
    w(f"--- L{ln} ---")
    w(seg.strip()[-560:])
    w()
    if len([x for x in L if x.startswith("--- L")]) >= 4:
        break

#2) current_vid
w("=== ui.py 中 current_video_info 的字段访问 ===")
fields = sorted(set(re.findall(r"current_video_info(?:\.get\(\s*['\"]([a-z_0-9]+)['\"]|\[\s*['\"]([a-z_0-9]+)['\"]\s*\])", ui)))
flat = sorted({a or b for a, b in fields})
for f in flat:
    w(f"    - {f}")
w()

# 3) video_info
w("=== ui.py 中 video_info 的字段 ===")
f2 = sorted(set(re.findall(r"video_info\.get\(\s*['\"]([a-z_0-9]+)['\"]", ui)))
for f in f2:
    w(f"    - {f}")
w()

# 4) 对PyQt5依赖
w("=== 核心模块的 PyQt5 依赖 ===")
for rel in ["core/downloader.py", "core/task_manager.py", "core/tool_manager.py",
            "core/config.py", "parsers/bilibili_parser.py",
            "core/download_history.py", "core/utils.py"]:
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        w(f"  {rel}: <不存在>")
        continue
    s = io.open(p, encoding="utf-8", errors="ignore").read()
    hits = sorted(set(re.findall(r"from PyQt5[^\n]*|import PyQt5[^\n]*", s)))
    w(f"  {rel}:")
    if hits:
        for h in hits[:6]:
            w(f"      {h.strip()}")
    else:
        w("      (无 PyQt5 依赖)")
w()

# 5) download_h
p = os.path.join(ROOT, "core", "download_history.py")
if os.path.isfile(p):
    s = io.open(p, encoding="utf-8").read()
    w("=== core/download_history.py 公开方法 ===")
    for m in re.finditer(r"^    def ([a-z]\w+)\(self([^)]*)\)", s, re.M):
        w(f"    {m.group(1)}({m.group(2).strip()[:80]})")
    w()

#6) task_manager
p = os.path.join(ROOT, "core", "task_manager.py")
if os.path.isfile(p):
    s = io.open(p, encoding="utf-8").read()
    w("=== core/task_manager.py 公开方法 ===")
    for m in re.finditer(r"^    def ([a-z]\w+)\(self([^)]*)\)", s, re.M):
        w(f"    {m.group(1)}({m.group(2).strip()[:80]})")
    w()

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
