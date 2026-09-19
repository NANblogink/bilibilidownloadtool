"""
CI 自检脚本，由 .github/workflows/Build.yml 调用，也可本地直接运行：

    python .github/ci_checks.py

检查项：
  1. 版本号一致性（app_config.py / version_info.json）
  2. 源码资源是否存在
  3. 关键模块是否可导入
  4. 平台工具函数行为是否正确
  5. 随包分发的离线工具是否就位

version_info.win、setup.iss、upx_tool/ 仅打包时使用，不入库；若本地存在
则一并校验版本号，缺失时跳过。

退出码 0 表示全部通过。
"""
import json
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import _pathsetup  # noqa: E402

failures = []
notes = []


def check(name, fn):
    try:
        detail = fn()
    except Exception as exc:
        failures.append(f"[FAIL] {name}: {exc}")
    else:
        notes.append(f"[ OK ] {name}{(' -> ' + detail) if detail else ''}")


def check_versions():
    with open(os.path.join(ROOT, "core", "app_config.py"), encoding="utf-8") as fh:
        app_cfg = fh.read()

    m_ver = re.search(r'APP_VERSION\s*=\s*"V([0-9.]+)"', app_cfg)
    m_num = re.search(r'VERSION_NUM\s*=\s*"([0-9.]+)"', app_cfg)
    if not (m_ver and m_num):
        raise AssertionError("app_config.py 中未找到 APP_VERSION / VERSION_NUM")
    app_version, app_num = m_ver.group(1), m_num.group(1)
    if app_version != app_num:
        raise AssertionError(f"APP_VERSION({app_version}) != VERSION_NUM({app_num})")

    with open(os.path.join(ROOT, "version_info.json"), encoding="utf-8") as fh:
        json_version = json.load(fh)["version"]

    versions = {app_version, json_version}
    win_path = os.path.join(ROOT, "version_info.win")
    if os.path.isfile(win_path):
        with open(win_path, encoding="utf-8") as fh:
            win = fh.read()
        m_win = re.search(r"filevers=\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", win)
        if not m_win:
            raise AssertionError("version_info.win 中未找到 filevers")
        versions.add(".".join(m_win.group(1, 2, 3)))

    if len(versions) != 1:
        raise AssertionError("版本号不一致：%s" % sorted(versions))
    return f"V{app_version}"


REQUIRED_ASSETS = [
    "main.py",
    "boot.py",
    "ui.py",
    "_pathsetup.py",
    "core/downloader.py",
    "core/app_config.py",
    "core/tool_manager.py",
    "core/icon_manager.py",
    "parsers/bilibili_parser.py",
    "core/cli.py",
    "version_info.json",
    "README.md",
    "CHANGELOG.md",
    "logo.ico",
    "logo.png",
    "warning_icon.png",
    "assets/icons",
    "assets/images",
    "assets/badges/version.svg",
]


def check_assets():
    missing = [p for p in REQUIRED_ASSETS if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        raise AssertionError("缺少必需资源: " + ", ".join(missing))
    return f"{len(REQUIRED_ASSETS)} 项齐全"


def check_imports():
    import app_config  # noqa: F401
    import platform_utils  # noqa: F401
    import error_codes  # noqa: F401
    import logger_config  # noqa: F401

    return f"APP_VERSION={app_config.APP_VERSION}"


def check_platform_helpers():
    from platform_utils import exe, get_bento4_sdk_dirname

    if os.name == "nt":
        assert exe("ffmpeg") == "ffmpeg.exe", f"期望 ffmpeg.exe，实际 {exe('ffmpeg')}"
        assert exe("mp4decrypt") == "mp4decrypt.exe", f"期望 mp4decrypt.exe，实际 {exe('mp4decrypt')}"
    return f"bento4 sdk dir = {get_bento4_sdk_dirname()}"


VENDOR_TOOLS = [
    "ffmpeg/bin/ffmpeg.exe",
    "ffmpeg/bin/ffprobe.exe",
    "bento4/Bento4-SDK-1-6-0-641.x86_64-microsoft-win32/bin/mp4decrypt.exe",
    "mpv/mpv.exe",
]


def check_vendor_tools():
    missing = [p for p in VENDOR_TOOLS if not os.path.exists(os.path.join(ROOT, p))]
    if missing:
        raise AssertionError("随包分发工具缺失: " + ", ".join(missing))
    return f"{len(VENDOR_TOOLS)} 项就位"


def main():
    check("版本号一致性 (app_config / version_info.json)", check_versions)
    check("源码资源存在性", check_assets)
    check("关键模块可导入", check_imports)
    check("平台工具函数行为", check_platform_helpers)
    check("随包分发工具就位", check_vendor_tools)

    print("=" * 68)
    for line in notes:
        print(line)
    for line in failures:
        print(line)
    print("=" * 68)

    if failures:
        print(f"\n自检失败：{len(failures)} 项")
        return 1
    print(f"\n自检全部通过：{len(notes)} 项")
    return 0


if __name__ == "__main__":
    sys.exit(main())
