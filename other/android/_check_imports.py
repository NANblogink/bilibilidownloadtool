"""验证：在没有 PyQt5 的环境下，桌面核心模块能否被导入。

Android 上没有 PyQt5。如果 core/downloader.py 顶层 import PyQt5，
那么 Kivy 端一旦 get_download_manager() 就会抛 ImportError，
"功能与桌面版一样" 根本无从谈起。

本脚本模拟"没有 PyQt5"的情形（用一个假的 meta_path finder 屏蔽 PyQt5），
逐个 import 核心模块，找出所有会炸的地方。
"""
import importlib
import io
import os
import sys

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
OUT = os.path.join(ROOT, "other", "android", "_import_report.txt")
L = []


def w(s=""):
    L.append(str(s))


class BlockPyQt5:
    """让 import PyQt5 一律失败，模拟 Android 环境。"""

    def find_module(self, name, path=None):
        if name == "PyQt5" or name.startswith("PyQt5."):
            return self
        return None

    def find_spec(self, name, path=None, target=None):
        if name == "PyQt5" or name.startswith("PyQt5."):
            raise ImportError(f"No module named '{name}' (blocked: simulating Android)")
        return None


for sub in ("core", os.path.join("core", "infra"), "parsers", ""):
    p = os.path.join(ROOT, sub)
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# 先引入_pathsetup
os.environ.setdefault("BILIDOWN_NO_QT", "1")

# 屏蔽 PyQt5
for i, f in enumerate(sys.meta_path):
    if getattr(f, "__name__", "") == "BlockPyQt5":
        break
else:
    sys.meta_path.insert(0, BlockPyQt5())

w("=== 模拟 Android（无 PyQt5）逐个导入核心模块 ===")
modules = [
    "platform_utils", "logger_config", "config", "task_manager",
    "tool_manager", "download_history", "bilibili_parser",
    "utils", "downloader",
]
results = {}
for m in modules:
    try:
        importlib.import_module(m)
        results[m] = "OK"
        w(f"  OK    {m}")
    except Exception as exc:
        results[m] = f"{type(exc).__name__}: {exc}"
        w(f"  FAIL  {m}: {type(exc).__name__}: {str(exc)[:160]}")

w()
w("=== 结论 ===")
bad = [m for m, r in results.items() if r != "OK"]
if bad:
    w(f"  以下模块在无 PyQt5 环境下无法导入：{bad}")
    w("  → Kivy 端不能直接用它们，需要一层不依赖 Qt 的适配/替身。")
else:
    w("  全部可导入。")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
