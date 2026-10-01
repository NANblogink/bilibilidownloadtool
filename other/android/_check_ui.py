"""对新的 main_kivy.py 做静态与轻量运行时自检（本机无 Kivy 也能查大部分问题）。"""
import ast
import io
import os
import re
import sys

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
AND = os.path.join(ROOT, "other", "android")
MAIN = os.path.join(AND, "main_kivy.py")
OUT = os.path.join(AND, "_ui_check.txt")
L = []


def w(s=""):
    L.append(str(s))


src = io.open(MAIN, encoding="utf-8").read()
fails = []


def check(name, cond, extra=""):
    w(("  PASS " if cond else "  FAIL ") + name + ((" " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


w("=== 1. 语法 ===")
try:
    tree = ast.parse(src)
    check("main_kivy.py 语法正确", True)
except SyntaxError as exc:
    check("main_kivy.py 语法正确", False, f"line {exc.lineno}: {exc.msg}")
    io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print("written", OUT)
    sys.exit(1)

w()
w("=== 2. KV 模板 ===")
kv_blocks = [n for n in ast.walk(tree)
             if isinstance(n, ast.Assign)
             and any(getattr(t, "id", "") == "KV" for t in n.targets)]
check("找到 KV 字符串", bool(kv_blocks))
kv = kv_blocks[0].value.value
rules = re.findall(r"<([A-Za-z_]\w*)(?:@([A-Za-z_]\w*))?>:", kv)
check("KV 定义了控件规则", len(rules) >= 3, [f"{a}@{b}" if b else a for a, b in rules])
check("KV 大括号配平", kv.count("{") == kv.count("}"),
      f"{kv.count('{')} vs {kv.count('}')}")
check("KV 含 canvas 规则", "canvas.before" in kv)

w()
w("=== 3. 关键功能是否都有入口 ===")
features = {
    "解析": "def on_parse",
    "粘贴": "def on_paste",
    "清空": "def _clear_all",
    "下载完整视频": "on_download(0)",
    "仅下载画面": "on_download(2)",
    "仅下载音频": "on_download(1)",
    "保存封面": "def on_save_cover",
    "单独下载弹幕": "def on_download_danmaku",
    "打开目录": "def on_open_folder",
    "批量下载": "def open_batch",
    "任务列表": "class TaskTab",
    "任务暂停/继续": "def toggle_pause",
    "任务取消": "def cancel_task",
    "历史记录": "class HistoryTab",
    "历史搜索/过滤": "def reload",
    "设置": "class SettingsTab",
    "扫码登录": "class LoginPopup",
    "退出登录": "def logout",
    "清晰度选择": "quality_spinner",
    "音质选择": "audio_spinner",
    "集数范围": "ep_input",
    "弹幕开关": "danmaku_spinner",
    "保存目录": "save_dir",
    "工具检查": "def refresh_tools",
    "工具下载": "def download_tools",
    "设备信息": "设备信息",
    "关于": "关于",
}
for name, needle in features.items():
    check(f"功能入口 - {name}", needle in src)

w()
w("=== 4. download_params 字段与桌面版一致 ===")
required = ["url", "video_info", "qn", "save_path", "episodes",
            "resume_download", "task_id", "download_content_type",
            "download_danmaku", "video_format", "audio_format",
            "audio_quality", "danmaku_format"]
for k in required:
    check(f'params["{k}"]', f'"{k}":' in src)

w()
w("=== 5. 无 PyQt5 直接 import（必须靠 qt_compat）===")
imports = re.findall(r"^\s*(?:from|import)\s+(PyQt5\S*)", src, re.M)
check("main_kivy.py 没有直接 import PyQt5", not imports, imports)

w()
w("=== 6. 跨线程更新界面必须经过 Clock ===")
# 找出所有 def _sig_* 槽函数，确认都用了 Clock
slots = re.findall(r"def (_sig_\w+)\(self.*?\n(.*?)(?=\n    def |\nclass |\Z)",
                   src, re.S)
for fname, body in slots:
    if fname in ("_sig_task_added", "_sig_task_status"):
        continue
    ok = "Clock.schedule_once" in body
    check(f"{fname} 用 Clock 切主线程", ok)

w()
w("=== 7. 字体与图标资源 ===")
for f in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf", "icon.png",
          "logo_ui.png"):
    p = os.path.join(AND, f)
    check(f"存在 {f}", os.path.isfile(p),
          f"{os.path.getsize(p)/1024:.0f} KB" if os.path.isfile(p) else "缺失")

w()
w("=== 8. buildozer.spec 关键项 ===")
spec = io.open(os.path.join(AND, "buildozer.spec"), encoding="utf-8").read()
def _spec_val(key):
    for line in spec.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("["):
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            if k.strip() == key:
                return v.strip()
    return None

check("强制竖屏（orientation = portrait）", _spec_val("orientation") == "portrait",
      "实际=%r" % _spec_val("orientation"))
check("图标已配置", "icon.filename" in spec)
check("ttf 被打包", "ttf" in spec.split("source.include_exts")[1].split("\n")[0])
check("qt_compat 会被打包", "source.include_patterns" in spec)

w()
w("=== 9. qt_compat 是否存在且可用 ===")
qp = os.path.join(AND, "qt_compat.py")
check("qt_compat.py 存在", os.path.isfile(qp))
qsrc = io.open(qp, encoding="utf-8").read() if os.path.isfile(qp) else ""
for sym in ("QObject", "pyqtSignal", "QThread", "QMutex", "QWaitCondition"):
    check(f"qt_compat 提供 {sym}", f"class {sym}" in qsrc)

w()
w(f"TOTAL FAILURES: {len(fails)}")
if fails:
    w("  " + "\n  ".join(fails))

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("FAILURES:", len(fails))
