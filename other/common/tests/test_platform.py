"""platform_utils 跨平台行为测试。

验证：平台识别、可执行名规范化、路径/字体/通知等 API 在当前平台
行为正确，且容错路径不会抛异常。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import install_paths  # noqa: E402

PROJECT_ROOT = install_paths()

import platform_utils as pu  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (" " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


print("PLATFORM_NAME     :", pu.PLATFORM_NAME)
print("IS_WINDOWS        :", pu.IS_WINDOWS)
print("IS_MACOS          :", pu.IS_MACOS)
print("IS_LINUX          :", pu.IS_LINUX)
print("IS_ANDROID        :", pu.IS_ANDROID)
print("exe('ffmpeg')     :", pu.exe("ffmpeg"))
print("exe('ffmpeg.exe') :", pu.exe("ffmpeg.exe"))
print("tool_names        :", pu.tool_names("mp4decrypt"))
print("app_data_dir      :", pu.app_data_dir())
print("platform_font     :", pu.platform_font())
print("bento4 sdk dir    :", pu.get_bento4_sdk_dirname())
print("notification      :", pu.notification_backend())
print()

print("== platform flags are mutually exclusive ==")
check("exactly one platform flag",
      sum([bool(pu.IS_WINDOWS), bool(pu.IS_MACOS), bool(pu.IS_LINUX)]) == 1)

print("== exe() normalisation ==")
if pu.IS_WINDOWS:
    check("exe('ffmpeg') -> ffmpeg.exe", pu.exe("ffmpeg") == "ffmpeg.exe")
    check("exe('x.exe') stays x.exe", pu.exe("x.exe") == "x.exe")
else:
    check("exe('ffmpeg') has no .exe", pu.exe("ffmpeg") == "ffmpeg", pu.exe("ffmpeg"))
    check("exe('x.exe') strips .exe", pu.exe("x.exe") == "x", pu.exe("x.exe"))

print("== app_data_dir is platform-appropriate ==")
adir = pu.app_data_dir()
check("non-empty", bool(adir))
if not pu.IS_WINDOWS:
    check("no backslash on posix", "\\" not in adir, adir)
if pu.IS_MACOS:
    check("macOS uses Library/Application Support",
          "Library/Application Support" in adir, adir)
elif pu.IS_LINUX and not pu.IS_ANDROID:
    check("linux uses ~/.config or XDG", ".config" in adir or "XDG" in adir, adir)

print("== illegal_filename_chars matches platform ==")
chars = pu.illegal_filename_chars()
if pu.IS_WINDOWS:
    check("windows forbids backslash/colon", "\\" in chars and ":" in chars, chars)
else:
    check("posix only forbids slash", "/" in chars, chars)

print("== ascii-safe temp dir ==")
d = pu.get_safe_temp_dir(tempfile.gettempdir(), "bili_t", None, None)
check("returns a usable dir", bool(d) and os.path.isdir(d), d)

print("== notify / beep must not raise ==")
try:
    pu.native_notify("标题", "内容")
    check("native_notify tolerated", True)
except Exception as exc:
    check("native_notify tolerated", False, exc)

print("== tolerant helpers on bogus input ==")
for fn, label in (
    (lambda: pu.kill_process_tree(999999, timeout=0.2), "kill_process_tree(bogus pid)"),
    (lambda: pu.reveal_in_file_manager("/nonexistent/xyz", select=True), "reveal_in_file_manager(missing)"),
    (lambda: pu.open_path("/nonexistent/xyz"), "open_path(missing)"),
):
    try:
        fn()
        check(label, True)
    except Exception as exc:
        check(label, False, exc)

print("== concurrency recommendation is sane ==")
c = pu.recommended_concurrency()
check("1 <= concurrency <= 8", 1 <= c <= 8, c)
check("cpu_count >= 1", pu.cpu_count() >= 1)

print()
print("TOTAL FAILURES:", len(fails), fails)
sys.exit(1 if fails else 0)
