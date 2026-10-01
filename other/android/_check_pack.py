"""模拟 p4a 的 source 收集过程，确认关键文件真的会被打进 APK。

p4a 依据 buildozer.spec 的 source.dir / include_exts / include_patterns
决定拷贝哪些文件。这里按同样的规则复算一遍，避免"改完 spec 却漏了文件"
导致 APK 启动即崩。
"""
import fnmatch
import io
import os
import shutil
import tempfile

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
ANDROID = os.path.join(ROOT, "other", "android")
OUT = os.path.join(ANDROID, "_pack_report.txt")
L = []


def w(s=""):
    L.append(str(s))


spec_path = os.path.join(ANDROID, "buildozer.spec")
spec = {}
for line in io.open(spec_path, encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("["):
        continue
    if "=" in line:
        k, v = line.split("=", 1)
        spec[k.strip()] = v.strip()

src_dir = os.path.abspath(os.path.join(ANDROID, spec.get("source.dir", ".")))
exts = [e.strip() for e in spec.get("source.include_exts", "").split(",") if e.strip()]
pats = [p.strip() for p in spec.get("source.include_patterns", "").split(",") if p.strip()]

w("=== source 收集模拟 ===")
w(f"  source.dir       = {src_dir}")
w(f"  include_exts     = {exts}")
w(f"  include_patterns = {pats}")
w()

collected = set()

# 1) 按扩展名过滤
for dirpath, dirnames, filenames in os.walk(src_dir):
    # 跳过构建产物
    dirnames[:] = [d for d in dirnames
                   if d not in (".buildozer", "bin", "__pycache__",
                                ".build_stage", ".git")]
    for fn in filenames:
        ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
        if ext in exts:
            full = os.path.join(dirpath, fn)
            collected.add(os.path.relpath(full, src_dir).replace("\\", "/"))

#2) include_patterns
for pat in pats:
    base = os.path.normpath(os.path.join(src_dir, os.path.dirname(pat)))
    name = os.path.basename(pat)
    if os.path.isdir(base):
        for fn in os.listdir(base):
            if fnmatch.fnmatch(fn, name):
                full = os.path.join(base, fn)
                if os.path.isfile(full):
                    collected.add(os.path.relpath(full, src_dir).replace("\\", "/"))

w("=== 收集到的文件 ===")
for f in sorted(collected):
    p = os.path.join(src_dir, f)
    size = os.path.getsize(p) if os.path.isfile(p) else 0
    w(f"  {f}   ({size/1024:.0f} KB)")

w()
w("=== 必需文件是否都在 ===")
required = {
    "main_kivy.py": "Android 入口",
    "qt_compat.py": "Qt 兼容层（缺了就无法导入桌面引擎）",
    "NotoSansSC-Regular.ttf": "中文字体（缺了乱码）",
    "NotoSansSC-Bold.ttf": "中文粗体",
    "icon.png": "启动图标源图",
    "logo_ui.png": "标题栏图标",
    "core/downloader.py": "下载引擎",
    "core/task_manager.py": "任务管理",
    "core/tool_manager.py": "工具管理",
    "core/config.py": "配置",
    "core/download_history.py": "下载历史",
    "core/utils.py": "工具函数",
    "core/infra/platform_utils.py": "平台适配",
    "core/infra/logger_config.py": "日志",
    "parsers/bilibili_parser.py": "B站解析器",
    "_pathsetup.py": "路径初始化",
}
missing = []
for rel, why in required.items():
    ok = rel in collected
    w(f"  {'OK  ' if ok else 'MISS'} {rel:34s} {why}")
    if not ok:
        missing.append(rel)

w()
w("=== 结论 ===")
if missing:
    w(f"  缺失 {len(missing)} 个必需文件：{missing}")
    w("  → 必须修正 buildozer.spec，否则 APK 会出问题。")
else:
    w("  全部必需文件都会被收集进 APK。")
w(f"  总文件数：{len(collected)}")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("MISSING:", len(missing))
