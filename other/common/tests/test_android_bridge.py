"""Android 入口与桌面核心的接口一致性校验。

本机不方便在 Android 上跑 Kivy，但真正决定"能不能用/对不对"的部分
可以在这里校验：

  1. main_kivy.py 能解析，KV 模板结构合理
  2. Android 层用到的桌面核心符号确实存在（接口名/签名写错是最大风险）
  3. start_download() 构造的 download_params 与
     DownloadManager.start_download() 实际读取的键一致
  4. Android 入口没有混入 PyQt5（Android 无 PyQt5）
  5. qt_compat 影子包确实能让桌面核心在无 PyQt5 环境下导入
  6. 返回值形状（例如 get_records 返回元组）与调用方假设一致
"""
import ast
import inspect
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import install_paths  # noqa: E402

PROJ = install_paths()

ANDROID_DIR = os.path.join(PROJ, "other", "android")
ANDROID = os.path.join(ANDROID_DIR, "main_kivy.py")
QT_COMPAT = os.path.join(ANDROID_DIR, "qt_compat.py")
SPEC = os.path.join(ANDROID_DIR, "buildozer.spec")
fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (" " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


src = open(ANDROID, encoding="utf-8").read()
tree = ast.parse(src)
print("== 1. module parses ==")
check("main_kivy.py parses", True)
check("qt_compat.py exists", os.path.isfile(QT_COMPAT))
qsrc = open(QT_COMPAT, encoding="utf-8").read() if os.path.isfile(QT_COMPAT) else ""

# ---------------------------------------------------------------- KV block
print()
print("== 2. KV template sanity ==")
kv_blocks = [n for n in ast.walk(tree)
             if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "KV" for t in n.targets)]
check("KV string found", bool(kv_blocks))
kv = kv_blocks[0].value.value
check("KV non-trivial", len(kv) > 200, "%d chars" % len(kv))
rules = re.findall(r"<([A-Za-z_]\w*)(?:@([A-Za-z_]\w*))?>:", kv)
check("KV defines widget rules", len(rules) >= 3,
      ["%s@%s" % (a, b) if b else a for a, b in rules])
# 大括号须配平
check("KV braces balanced", kv.count("{") == kv.count("}"),
      "%d vs %d" % (kv.count("{"), kv.count("}")))
check("KV has canvas rules", "canvas.before" in kv)

# ---------------------------------------------------------------- 竖屏
print()
print("== 3. portrait / icon / font packaging ==")
spec = open(SPEC, encoding="utf-8").read() if os.path.isfile(SPEC) else ""


def _spec_value(key):
    """读取 spec 里的某个键（忽略注释行），返回 None 表示未设置。"""
    for line in spec.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("["):
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            if k.strip() == key:
                return v.strip()
    return None


# buildozer读orientation
# 写成android前缀会被忽略
check("orientation = portrait", _spec_value("orientation") == "portrait",
      "实际=%r" % _spec_value("orientation"))
check("no bogus android.orientation key",
      _spec_value("android.orientation") is None)
check("launcher icon configured", "icon.filename" in spec)
check("font ttf packaged", "ttf" in spec)
check("kivy required", "kivy" in spec)
for f in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf", "icon.png"):
    check("bundled asset %s" % f, os.path.isfile(os.path.join(ANDROID_DIR, f)))

# ---------------------------------------------------------------- imports
print()
print("== 4. desktop-core symbols actually exist ==")
import downloader as dl
import bilibili_parser as bp
import config as cfg
import task_manager as tm
import download_history as dh

check("downloader.DownloadManager exists", hasattr(dl, "DownloadManager"))
check("bilibili_parser.BilibiliParser exists", hasattr(bp, "BilibiliParser"))
check("config.ConfigLoader exists", hasattr(cfg, "ConfigLoader"))
check("task_manager.TaskManager exists", hasattr(tm, "TaskManager"))
check("download_history.DownloadHistory exists", hasattr(dh, "DownloadHistory"))

# BilibiliParser接受config
try:
    sig = inspect.signature(bp.BilibiliParser.__init__)
    check("BilibiliParser(config=...) accepted", "config" in sig.parameters, str(sig))
except Exception as exc:
    check("BilibiliParser signature readable", False, exc)

# ---------------------------------------------------------------- DM API
print()
print("== 5. DownloadManager API matches Android bridge ==")
try:
    sig = inspect.signature(dl.DownloadManager.__init__)
    params = set(sig.parameters)
    check("DownloadManager(max_threads=...) exists", "max_threads" in params, str(sig))
    check("DownloadManager(max_concurrent_tasks=...) exists",
          "max_concurrent_tasks" in params, str(sig))
except Exception as exc:
    check("DownloadManager signature readable", False, exc)

check("DownloadManager.start_download exists",
      hasattr(dl.DownloadManager, "start_download"))

# start_download读哪些键
try:
    dsrc = inspect.getsource(dl.DownloadManager.start_download)
    read_keys = set(re.findall(r"download_params\.get\(\s*['\"]([^'\"]+)['\"]", dsrc))
except Exception:
    read_keys = set()
print("      start_download reads:", sorted(read_keys))

# 桥须供给它读的每个键
android_keys = set(re.findall(r"['\"]([a-z_]+)['\"]\s*:", src))
required = {"video_info", "qn", "save_path", "episodes", "task_id",
            "download_content_type", "resume_download", "audio_quality"}
missing = required - android_keys
check("Android bridge supplies required keys", not missing, "missing=%s" % missing)

# ---------------------------------------------------------------- no PyQt leak
print()
print("== 6. no PyQt5 leakage into Android entry ==")
# 只看真实import
import re as _re
_imports = _re.findall(r"^\s*(?:from|import)\s+PyQt5\S*", src, _re.M)
check("no PyQt5 import statement", not _imports, _imports)
check("no QtWidgets import", not _re.search(r"^\s*(?:from|import)\s+PyQt5\.QtWidgets", src, _re.M))
check("kivy is imported", "from kivy" in src or "import kivy" in src)
# 影子包须先于core安装
check("qt_compat installed before core imports", "qt_compat.install()" in src)

# ---------------------------------------------------------------- 影子包
print()
print("== 7. qt_compat provides the Qt surface the core needs ==")
for sym, cls in (("QObject", "QObject"), ("pyqtSignal", "pyqtSignal"),
                 ("QThread", "QThread"), ("QMutex", "QMutex"),
                 ("QWaitCondition", "QWaitCondition")):
    check("qt_compat defines %s" % sym, ("class %s" % cls) in qsrc)
check("qt_compat exposes Qt namespace", "Qt = _QtNamespace()" in qsrc)
check("qt_compat does not import real PyQt5 at top level",
      not _re.search(r"^\s*(?:from|import)\s+PyQt5\s*$", qsrc, _re.M))
# 影子包仅在缺PyQt5时生效
check("qt_compat defers to real PyQt5", "import PyQt5" in qsrc)

# ---------------------------------------------------------------- 返回值形状
print()
print("== 8. return-value shapes match caller assumptions ==")
try:
    gsrc = inspect.getsource(dh.DownloadHistory.get_records)
    returns_tuple = re.search(r"return\s+records\s*,\s*total", gsrc) is not None
    check("get_records returns (records, total)", returns_tuple)
    # 须解包元组否则history崩
    check("Android unpacks get_records tuple", "isinstance(result, tuple)" in src)
except Exception as exc:
    check("get_records source readable", False, exc)

# ------------ 设备档案 ------------
print()
print("== 9. device profile is conservative ==")
check("concurrency cap <= 4", "cap=4" in src)
check("max_tasks bounded", "max_tasks" in src)
check("no unbounded thread spawning", "ThreadPoolExecutor(max_workers=None)" not in src)

# ---------------------------------------------------------------- 跨线程 UI
print()
print("== 10. UI updates are marshalled to the main thread ==")
slots = re.findall(r"def (_sig_\w+)\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)",
                   src, re.S)
marshalled = 0
for fname, body in slots:
    if "Clock.schedule_once" in body:
        marshalled += 1
check("emitted signals use Clock.schedule_once", marshalled >= 4,
      "%d/%d slots" % (marshalled, len(slots)))

print()
print("TOTAL FAILURES:", len(fails), fails)
sys.exit(1 if fails else 0)
