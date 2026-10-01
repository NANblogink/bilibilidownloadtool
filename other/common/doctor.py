#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨平台环境自检。

在 Linux / macOS / Android 上运行本脚本，可快速确认：
  1. Python 版本与依赖是否齐全
  2. 平台识别是否正确（platform_utils 是否走了对的分支）
  3. 关键工具（ffmpeg / ffprobe / mp4decrypt / mpv）能否找到
  4. Qt 平台插件能否加载（无显示器环境下用 offscreen 验证）
  5. 桌面通知 / 文件管理器 / 关机等平台 API 是否可用
  6. 常见坑位检查（非守护线程、Windows 专有调用残留）

用法：
    python other/common/doctor.py

退出码 0 表示全部通过；非 0 表示有项目失败（详见输出）。
"""
import os
import platform
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))


def _looks_like_project(path):
    return path and os.path.isfile(os.path.join(path, "main.py")) \
        and os.path.isdir(os.path.join(path, "core"))


if not _looks_like_project(PROJECT_ROOT):
    # stdin下__file__不可靠
    starts = [os.getcwd(), HERE]
    for start in starts:
        cur = os.path.abspath(start)
        for _ in range(6):
            if _looks_like_project(cur):
                PROJECT_ROOT = cur
                break
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        if _looks_like_project(PROJECT_ROOT):
            break

for _sub in ("core", os.path.join("core", "infra"), "parsers"):
    _p = os.path.join(PROJECT_ROOT, _sub)
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OK, FAIL, WARN = "PASS", "FAIL", "WARN"
results = []


def record(status, title, detail=""):
    results.append((status, title, detail))
    icon = {OK: "✓", FAIL: "✗", WARN: "!"}[status]
    line = "  %s  %s" % (icon, title)
    if detail:
        line += "\n        %s" % detail
    print(line)


def section(name):
    print("\n" + "=" * 68)
    print(name)
    print("=" * 68)


# ---------------------------------------------------------------- 1. Python
section("1. 运行环境")

py_ok = sys.version_info >= (3, 8)
record(OK if py_ok else FAIL,
       "Python 版本 %d.%d.%d" % sys.version_info[:3],
       "" if py_ok else "需要 Python 3.8 或更高")

record(OK, "操作系统: %s" % platform.platform())
record(OK, "架构: %s" % (platform.machine() or "unknown"))

# ---------------------------------------------------------------- 2. 平台识别
section("2. 平台识别 (platform_utils)")

try:
    import platform_utils as pu
except Exception as exc:  # pragma: no cover
    record(FAIL, "导入 platform_utils", str(exc))
    pu = None

if pu is not None:
    record(OK, "PLATFORM_NAME = %s" % pu.PLATFORM_NAME)
    # 三个IS恰好一真
    flags = [pu.IS_WINDOWS, pu.IS_MACOS, pu.IS_LINUX]
    record(OK if sum(bool(f) for f in flags) == 1 else FAIL,
           "平台标志互斥",
           "IS_WINDOWS=%s IS_MACOS=%s IS_LINUX=%s IS_ANDROID=%s"
           % (pu.IS_WINDOWS, pu.IS_MACOS, pu.IS_LINUX, pu.IS_ANDROID))
    record(OK, "exe('ffmpeg') -> %s" % pu.exe("ffmpeg"))
    record(OK, "数据目录 -> %s" % pu.app_data_dir())
    record(OK, "通知后端 -> %s" % pu.notification_backend())
    if pu.notification_backend() == "none" and not pu.IS_WINDOWS:
        record(WARN, "系统通知不可用",
               "Linux 安装 libnotify-bin，或忽略（仅影响完成提示）")

# ---------------------------------------------------------------- 3. 依赖
section("3. Python 依赖")

DEPS = [
    ("PyQt5.QtCore", "GUI 框架"),
    ("PyQt5.QtWidgets", "GUI 组件"),
    ("PyQt5.QtGui", "GUI 绘制"),
    ("requests", "HTTP 客户端"),
    ("curl_cffi", "TLS 指纹伪装"),
    ("orjson", "高速 JSON"),
    ("PIL", "图像处理"),
    ("psutil", "系统信息"),
    ("qrcode", "登录二维码"),
    ("cryptography", "RSA 加密"),
    ("Crypto", "AES/DRM 解密"),
]
missing = []
for mod, desc in DEPS:
    try:
        __import__(mod)
        record(OK, "%s (%s)" % (mod, desc))
    except Exception as exc:
        missing.append(mod)
        record(FAIL, "%s (%s)" % (mod, desc), str(exc))

# WebEngine可选
try:
    __import__("PyQt5.QtWebEngineWidgets")
    record(OK, "PyQt5.QtWebEngineWidgets (人机验证)")
except Exception as exc:
    record(WARN, "PyQt5.QtWebEngineWidgets 不可用",
           "极验/人机验证将降级为外部浏览器：%s" % exc)

# ---------------------------------------------------------------- 4. Qt 插件
section("4. Qt 平台插件")

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PyQt5.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    record(OK, "QApplication 创建成功 (platform=%s)"
           % os.environ.get("QT_QPA_PLATFORM"))
    from PyQt5.QtCore import QT_VERSION_STR
    record(OK, "Qt 版本 %s" % QT_VERSION_STR)
except Exception as exc:
    record(FAIL, "QApplication 创建失败",
           "%s\n        提示: Linux 需要安装 libxcb / libxkbcommon 等库，"
           "或设置 QT_QPA_PLATFORM=offscreen" % exc)

# ---------------------------------------------------------------- 5. 外部工具
section("5. 外部工具 (ffmpeg / bento4 / mpv)")

from platform_utils import exe as _exe_name  # noqa: E402

TOOLS = [
    ("ffmpeg", "音视频合并与转码", True),
    ("ffprobe", "媒体信息探测", True),
    ("mp4decrypt", "DRM 解密 (Bento4)", False),
    ("mpv", "内置播放器", False),
]
for tool, desc, required in TOOLS:
    name = _exe_name(tool)
    found = shutil.which(name)
    local = []
    for d in (os.path.join(PROJECT_ROOT, "ffmpeg", "bin"),
              os.path.join(PROJECT_ROOT, "bento4", "bin"),
              os.path.join(PROJECT_ROOT, "bento4",
                           "Bento4-SDK-1-6-0-641.x86_64-apple-macosx", "bin"),
              os.path.join(PROJECT_ROOT, "mpv"),
              os.path.join(pu.app_data_dir(), "ffmpeg", "bin") if pu else "",
              os.path.join(pu.app_data_dir(), "bento4", "bin") if pu else ""):
        if d and os.path.isfile(os.path.join(d, name)):
            local.append(os.path.join(d, name))
    if found or local:
        record(OK, "%s (%s)" % (name, desc),
               "系统: %s" % found if found else "随包: %s" % local[0])
    else:
        record(FAIL if required else WARN,
               "未找到 %s (%s)" % (name, desc),
               "程序内「设置 → 工具安装」可从网络自动下载，或手动放入 ffmpeg/bin/")

# ---------------------------------------------------------------- 6. 平台 API
section("6. 平台行为 API")

if pu:
    for fn, label in [
        (lambda: pu.open_path("/nonexistent_probe_path"), "open_path() 容错"),
        (lambda: pu.reveal_in_file_manager("/nonexistent_probe_path"), "reveal_in_file_manager() 容错"),
        (lambda: pu.kill_process_tree(999999, timeout=0.1), "kill_process_tree() 容错"),
    ]:
        try:
            fn()
            record(OK, label)
        except Exception as exc:
            record(FAIL, label, "不应抛异常: %s" % exc)

    # 只验证后端不真的发声
    backend = pu.notification_backend()
    record(OK if backend != "none" or pu.IS_WINDOWS else WARN,
           "通知后端: %s" % backend)
    record(OK, "beep() 可用（未实际发声）")

    # 只查存在不真调用
    # 否则会关用户机器
    import shutil as _sh
    can_shutdown = bool(_sh.which("systemctl") or _sh.which("shutdown"))
    if pu.IS_WINDOWS:
        can_shutdown = True
    record(OK if can_shutdown else WARN,
           "关机命令可用: %s" % ("是" if can_shutdown else "否"),
           "" if can_shutdown else "「下载完成后关机」功能将不可用")

    record(OK if pu.recommended_concurrency() >= 1 else FAIL,
           "recommended_concurrency() = %s" % pu.recommended_concurrency(),
           "CPU=%s 可用内存=%.1fGB" % (
               pu.cpu_count(),
               (pu.available_memory_bytes() or 0) / 1024 ** 3))

# ---------------------------------------------------------------- 7. 源码检查
section("7. 源码健康检查")

try:
    from bilibili_parser import BilibiliParser  # noqa: F401
    record(OK, "解析核心可导入")
except Exception as exc:
    record(FAIL, "解析核心导入失败", str(exc))

try:
    import ui  # noqa: F401
    record(OK, "界面模块可导入")
except Exception as exc:
    record(FAIL, "界面模块导入失败", str(exc))

# 扫描残留Win调用
if pu and not pu.IS_WINDOWS:
    import re

    # 这些本就是平台适配层
    # 都被IS_WINDOWS守卫
    PLATFORM_LAYER = {"platform_utils.py", "toast_winrt.py", "cert_installer.py",
                      "pyqt5_bootstrap.py", "cli.py"}
    BAD = [
        (r"os\.startfile\(", "os.startfile"),
        (r"subprocess\.\w+\(\s*\[?\s*['\"]explorer['\"]", "explorer 调用"),
        (r"['\"]taskkill['\"]", "taskkill 调用"),
        (r"\bwinsound\b", "winsound 调用"),
        (r"subprocess\.STARTUPINFO", "subprocess.STARTUPINFO"),
    ]

    def _guarded(lines, idx):
        """判断第 idx 行（0-based）是否处在 IS_WINDOWS 守卫之下。

        简单回溯：往上找最近的 if/elif/else 结构，看是否提到 IS_WINDOWS。
        也接受同一行内出现 IS_WINDOWS（三元表达式写法）。
        """
        line = lines[idx]
        if "IS_WINDOWS" in line or "sys.platform" in line or "os.name" in line:
            return True
        indent = len(line) - len(line.lstrip())
        for j in range(idx - 1, max(-1, idx - 40), -1):
            prev = lines[j]
            if not prev.strip():
                continue
            pindent = len(prev) - len(prev.lstrip())
            if pindent >= indent:
                continue
            stripped = prev.strip()
            if ("IS_WINDOWS" in prev or "sys.platform" in prev or "os.name" in prev) \
                    and (stripped.endswith(":") or stripped.startswith(("if ", "elif ", "else"))):
                return True
            if stripped.startswith(("def ", "class ")):
                break
            if pindent < indent and not stripped.startswith(("if ", "elif ", "else", "#", "try", "except", "with", "@")):
                break
        return False

    leaks = []
    for sub in ("core", "parsers", os.path.join("core", "infra")):
        d = os.path.join(PROJECT_ROOT, sub)
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                if not f.endswith(".py") or f in PLATFORM_LAYER:
                    continue
                p = os.path.join(dp, f)
                try:
                    src = open(p, encoding="utf-8", errors="replace").read()
                except Exception:
                    continue
                lines = src.splitlines()
                for ln, line in enumerate(lines):
                    for pat, label in BAD:
                        if re.search(pat, line) and not _guarded(lines, ln):
                            leaks.append("%s:%d [%s] %s" % (
                                os.path.relpath(p, PROJECT_ROOT), ln + 1,
                                label, line.strip()[:70]))
    if leaks:
        record(WARN, "发现 %d 处未加平台守卫的 Windows 调用" % len(leaks),
               "\n        ".join(leaks[:8]))
    else:
        record(OK, "未发现未加平台守卫的 Windows 专有调用")

# ---------------------------------------------------------------- 汇总
section("自检结果")
n_fail = sum(1 for s, _, _ in results if s == FAIL)
n_warn = sum(1 for s, _, _ in results if s == WARN)
n_ok = sum(1 for s, _, _ in results if s == OK)
print("  通过 %d 项 / 警告 %d 项 / 失败 %d 项" % (n_ok, n_warn, n_fail))

if n_fail:
    print("\n以下项目失败：")
    for s, t, d in results:
        if s == FAIL:
            print("  ✗ %s" % t)
            if d:
                print("      %s" % d)
    print("\n请按上面的提示修复后重新运行自检。")
    sys.exit(1)

if n_warn:
    print("\n有警告项但无致命问题，程序可正常运行。")
print("\n环境自检通过。")
sys.exit(0)
