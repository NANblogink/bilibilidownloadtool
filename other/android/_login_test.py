# 类Android复现
#无qrcode/PyQt
# 屏蔽import跑
import builtins
import io
import os
import sys
import traceback

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ["KIVY_LOG_LEVEL"] = "error"
os.environ["KIVY_NO_CONSOLELOG"] = "1"
os.environ.pop("KIVY_WINDOW", None)

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
AND = os.path.join(ROOT, "other", "android")
OUT = os.path.join(AND, "_login_crash.txt")
L = []


def w(s=""):
    L.append(str(s))


# --- 屏蔽缺失模块 ---
BLOCKED = {"qrcode", "PIL", "PyQt5", "android", "jnius"}
_real_import = builtins.__import__


def fake_import(name, *a, **k):
    top = name.split(".")[0]
    if top in BLOCKED:
        raise ImportError("No module named %r" % top)
    return _real_import(name, *a, **k)


builtins.__import__ = fake_import

sys.path.insert(0, AND)
for sub in ("core", os.path.join("core", "infra"), "parsers", ""):
    p = os.path.join(ROOT, sub)
    if os.path.isdir(p):
        sys.path.insert(0, p)

w("=== 模拟 Android 环境（无 qrcode / PyQt5 / jnius）===")
for m in sorted(BLOCKED):
    try:
        __import__(m)
        w("  !! %s 仍然可导入（模拟失败）" % m)
    except ImportError:
        w("  OK %s 已屏蔽" % m)

w()
w("=== 1. 导入 main_kivy ===")
try:
    import main_kivy as mk
    w("  OK 导入成功")
except Exception:
    w("  FAIL 导入即失败")
    w(traceback.format_exc()[-2000:])
    io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
    raise SystemExit(1)

w()
w("=== 2. 构建 App ===")
app = mk.BilibiliAndroidApp()
try:
    root = app.build()
    w("  OK build() 成功")
except Exception:
    w("  FAIL build() 失败")
    w(traceback.format_exc()[-2000:])

w()
w("=== 3. 打开扫码登录（这是用户报告闪退的地方）===")
crashes = []


def step(name, fn):
    try:
        fn()
        w("  OK   %s" % name)
        return True
    except Exception:
        w("  FAIL %s" % name)
        tb = traceback.format_exc()
        w("       " + tb.strip().split("\n")[-1])
        crashes.append((name, tb))
        return False


#3a. LoginPopup
pop_holder = {}


def _make():
    pop_holder["pop"] = mk.LoginPopup(app)


step("构造 LoginPopup", _make)
pop = pop_holder.get("pop")

if pop is not None:
    step("pop.open()", pop.open)

    # 3b. start取码
    step("pop.start()", pop.start)
    import time
    time.sleep(2.5)

    # 3c. _render_qr
    step("_render_qr（无 qrcode 模块）",
         lambda: w("       -> 返回 %r" % pop._render_qr("https://example.com")))

    # 3d. _show_qr有数
    step("_show_qr（模拟服务端返回）",
         lambda: pop._show_qr({"qrcode_key": "abc123",
                               "url": "https://www.bilibili.com/h5/login"}))

    step("_poll 一轮", lambda: pop._poll(0))
    time.sleep(1.0)
    step("_on_poll（模拟未扫码）",
         lambda: pop._on_poll({"success": False, "status": "等待扫码",
                               "code": 86101}))
    step("dismiss", pop.dismiss)

w()
w("=== 4. 通过 App 的 open_login 走完整路径 ===")
step("app.open_login()", app.open_login)
import time
time.sleep(2.5)

w()
w("=== 5. 其他会用到缺失模块的入口 ===")
step("app.open_batch()", app.open_batch)
step("app.load_settings()", app.load_settings)

w()
w("=== 崩溃摘要 ===")
if crashes:
    for name, tb in crashes:
        w("--- %s ---" % name)
        w(tb[-1200:])
else:
    w("  无崩溃")
w()
w("TOTAL CRASHES: %d" % len(crashes))

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("CRASHES:", len(crashes))
for line in L:
    if "OK " in line or "FAIL" in line or "->" in line or "TOTAL" in line:
        print(line)
