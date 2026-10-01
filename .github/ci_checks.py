"""
CI 自检脚本，由 .github/workflows/Build.yml 调用，也可本地直接运行：

    python .github/ci_checks.py

检查项：
  1. 版本号一致性（app_config.py / version_info.json）
  2. 源码资源是否存在
  3. 关键模块是否可导入
  4. 内测开关 IS_BETA_BUILD 未残留（必须是 False）
  5. 平台工具函数行为是否正确
  6. 随包分发的离线工具是否就位

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


def check_beta_flag():
    """仓库里的 IS_BETA_BUILD 必须是 False。

    打包内测包时 other/windows/build_beta.py 会临时把它改成 True。
    如果脚本被强杀（TerminateProcess 不触发 finally），开关会残留在 True，
    之后打的「正式包」就会变成需要 QQ 授权、且更新走 beta 通道的内测包，
    而这一点从外观上完全看不出来。所以在这里兜一道。
    """
    cfg = os.path.join(ROOT, "core", "app_config.py")
    with open(cfg, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"^IS_BETA_BUILD\s*=\s*(True|False)\s*$", content, re.M)
    if not m:
        raise AssertionError("core/app_config.py 中找不到 IS_BETA_BUILD")
    if m.group(1) != "False":
        raise AssertionError(
            "IS_BETA_BUILD 为 True —— 这是内测包开关，不应出现在仓库里。"
            "若是打包内测包后被强杀导致残留，请改回 False 再提交。")

    # 顺带检查内测打包的备份标记有没有残留
    marker = os.path.join(ROOT, "build_win_beta", ".beta_flag_backup")
    if os.path.exists(marker):
        raise AssertionError("发现内测打包残留标记 %s，上次构建可能被中断" % marker)

    return "IS_BETA_BUILD=False"


def check_platform_helpers():
    from platform_utils import (exe, get_bento4_sdk_dirname, IS_WINDOWS,
                                IS_MACOS, IS_LINUX, app_data_dir,
                                illegal_filename_chars, platform_font,
                                notification_backend)

    if os.name == "nt":
        assert exe("ffmpeg") == "ffmpeg.exe", f"期望 ffmpeg.exe，实际 {exe('ffmpeg')}"
        assert exe("mp4decrypt") == "mp4decrypt.exe", f"期望 mp4decrypt.exe，实际 {exe('mp4decrypt')}"
    else:
        # 非 Windows 平台必须去掉 .exe，否则找不到工具
        assert exe("ffmpeg") == "ffmpeg", f"期望 ffmpeg，实际 {exe('ffmpeg')}"
        assert exe("mp4decrypt") == "mp4decrypt", \
            f"期望 mp4decrypt，实际 {exe('mp4decrypt')}"
        # 传入已带 .exe 的名字也要能规范化
        assert exe("ffmpeg.exe") == "ffmpeg", \
            f"exe('ffmpeg.exe') 应为 ffmpeg，实际 {exe('ffmpeg.exe')}"

    # 平台互斥：三个标志中恰好一个为真
    assert sum([bool(IS_WINDOWS), bool(IS_MACOS), bool(IS_LINUX)]) == 1, \
        f"平台标志异常: win={IS_WINDOWS} mac={IS_MACOS} linux={IS_LINUX}"

    # 数据目录必须是当前平台的合法路径，不能含 Windows 反斜杠
    adir = app_data_dir()
    if not IS_WINDOWS:
        assert "\\" not in adir, f"非 Windows 平台数据目录不应含反斜杠: {adir}"

    # 非法文件名字符必须与平台匹配
    chars = illegal_filename_chars()
    if IS_WINDOWS:
        assert '\\' in chars and ':' in chars, f"Windows 非法字符异常: {chars}"
    else:
        assert chars == ['/'] or ':' not in chars, f"非 Windows 非法字符异常: {chars}"

    font, size = platform_font()
    assert font and size, "platform_font 返回值异常"

    return (f"{'win32' if IS_WINDOWS else ('darwin' if IS_MACOS else 'linux')}"
            f" / bento4={get_bento4_sdk_dirname()} / notify={notification_backend()}")


# 随包工具：按平台选择期望的文件名。
# Windows 用 .exe；Linux/macOS 用无扩展名的二进制。
def _vendor_tool_paths():
    from platform_utils import exe as _exe
    return [
        f"ffmpeg/bin/{_exe('ffmpeg')}",
        f"ffmpeg/bin/{_exe('ffprobe')}",
        f"bento4/Bento4-SDK-1-6-0-641.x86_64-microsoft-win32/bin/{_exe('mp4decrypt')}",
        f"mpv/{_exe('mpv')}",
    ]


def check_vendor_tools():
    """随包工具检查。

    注意：仓库里默认只带 Windows 版二进制（ffmpeg.exe / mpv.exe）。
    其他平台改为运行时按需下载，因此这里只在 Windows 上强制要求，
    非 Windows 平台缺失时给出提示而不失败。
    """
    from platform_utils import IS_WINDOWS

    paths = _vendor_tool_paths()
    missing = [p for p in paths if not os.path.exists(os.path.join(ROOT, p))]

    if missing and IS_WINDOWS:
        raise AssertionError("随包分发工具缺失: " + ", ".join(missing))
    if missing:
        return (f"非 Windows 平台未随包携带二进制（{len(missing)} 项缺失，"
                f"运行时自动下载）")
    return f"{len(paths)} 项就位"


def check_platform_guard():
    """静态检查：非 Windows 平台不应存在未加守卫的 Windows 专有调用。"""
    from platform_utils import IS_WINDOWS
    if IS_WINDOWS:
        return "跳过（当前即 Windows）"

    import re
    PLATFORM_LAYER = {"platform_utils.py", "toast_winrt.py", "cert_installer.py",
                      "pyqt5_bootstrap.py", "cli.py", "build.py", "installer.py"}
    BAD = [
        (r"os\.startfile\(", "os.startfile"),
        (r"subprocess\.\w+\(\s*\[?\s*['\"]explorer['\"]", "explorer"),
        (r"['\"]taskkill['\"]", "taskkill"),
        (r"\bwinsound\b", "winsound"),
    ]
    leaks = []
    for sub in ("core", "parsers", os.path.join("core", "infra")):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for dp, dn, fn in os.walk(d):
            dn[:] = [x for x in dn if x != "__pycache__"]
            for f in fn:
                if not f.endswith(".py") or f in PLATFORM_LAYER:
                    continue
                p = os.path.join(dp, f)
                try:
                    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines):
                    if not any(re.search(pat, line) for pat, _ in BAD):
                        continue
                    if "IS_WINDOWS" in line or "sys.platform" in line:
                        continue
                    # 往上找守卫
                    indent = len(line) - len(line.lstrip())
                    guarded = False
                    for j in range(i - 1, max(-1, i - 40), -1):
                        prev = lines[j]
                        if not prev.strip():
                            continue
                        pind = len(prev) - len(prev.lstrip())
                        if pind >= indent:
                            continue
                        if ("IS_WINDOWS" in prev or "sys.platform" in prev) and \
                                prev.strip().endswith(":"):
                            guarded = True
                            break
                        if prev.strip().startswith(("def ", "class ")):
                            break
                    if not guarded:
                        leaks.append("%s:%d" % (os.path.relpath(p, ROOT), i + 1))
    if leaks:
        raise AssertionError("发现未加平台守卫的 Windows 专有调用: "
                             + ", ".join(leaks[:10]))
    return "未发现平台泄漏"


def main():
    check("版本号一致性 (app_config / version_info.json)", check_versions)
    check("源码资源存在性", check_assets)
    check("关键模块可导入", check_imports)
    check("内测开关未残留 (IS_BETA_BUILD)", check_beta_flag)
    check("平台工具函数行为", check_platform_helpers)
    check("随包分发工具就位", check_vendor_tools)
    check("平台专有调用守卫", check_platform_guard)

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
