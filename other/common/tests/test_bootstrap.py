"""pyqt5_bootstrap 平台标签与 wheel 选择测试。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import install_paths  # noqa: E402

PROJECT_ROOT = install_paths()

import pyqt5_bootstrap as pb  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (" " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


print("platform_tag        :", pb.platform_tag())
print("platform_tag_aliases:", sorted(pb.platform_tag_aliases()))
print("_PLATFORM_TAG       :", pb._PLATFORM_TAG)
print("_PY_TAG             :", pb._PY_TAG)
print("runtime_dir         :", pb.runtime_dir())
print("plugin names        :", pb._platform_plugin_names())
print("webengine names     :", pb._webengine_process_names())
print()

print("== platform tag matches this host ==")
if sys.platform.startswith("linux"):
    check("linux tag is linux-ish",
          pb.platform_tag() in ("x86_64", "aarch64", "i686"), pb.platform_tag())
check("tag is not win_amd64 on posix",
      pb.platform_tag() != "win_amd64" or sys.platform == "win32")

print("== wheel filtering accepts this platform's wheels ==")
# 模拟PyQt5索引
entries = [
    {"filename": "PyQt5-5.15.11-cp38-abi3-manylinux_2_17_x86_64.whl",
     "url": "https://example.invalid/a.whl"},
    {"filename": "PyQt5-5.15.11-cp38-abi3-win_amd64.whl",
     "url": "https://example.invalid/b.whl"},
    {"filename": "PyQt5-5.15.11-cp38-abi3-macosx_11_0_arm64.whl",
     "url": "https://example.invalid/c.whl"},
]
aliases = pb.platform_tag_aliases()
picked = [e["filename"] for e in entries
          if any(a in e["filename"].lower() for a in aliases)]
print("  would accept:", picked)
if sys.platform.startswith("linux"):
    check("accepts manylinux wheel",
          any("manylinux" in p for p in picked), picked)
    check("rejects win_amd64 wheel",
          not any("win_amd64" in p for p in picked), picked)

print("== 架构筛选：64 位机器优先选 win_amd64 ==")
# 精简版装不全根因回归
# 旧实现子串匹配别名
# 64位误下32wh
check("win_amd64 accepted", pb._platform_arch_ok("win_amd64") is True)
check("win_amd64 ranks above win32",
      pb._arch_rank("win_amd64") > pb._arch_rank("win32"))
check("win32 only usable as downgrade",
      0 <= pb._arch_rank("win32") < pb._arch_rank("win_amd64"))
check("win_arm64 rejected on x86_64 host",
      pb._platform_arch_ok("win_arm64") is False)
check("pure-python 'any' accepted", pb._platform_arch_ok("any") is True)
check("empty platform rejected", pb._platform_arch_ok("") is False)

# 用真实解析器再验一次
_w = pb._split_wheel("PyQt5_sip-12.17.2-cp310-cp310-win32.whl")
check("win32 wheel parses as 32-bit x86",
      pb._parse_platform_field(_w["platform"]) == ("windows", "x86", 32), _w)
check("win32 wheel ranks below win_amd64",
      pb._arch_rank(_w["platform"]) < pb._arch_rank("win_amd64"))

print("== 解释器/ABI 兼容判断 ==")
_cur = "cp%d%d" % (sys.version_info.major, sys.version_info.minor)
# abi3 向后兼容
check("abi3 for older cp is usable", pb._compat_ok("cp38", "abi3", _cur) is True)
# 非abi3须精确匹配
check("non-abi3 exact match usable",
      pb._compat_ok(_cur, _cur, _cur) is True)
check("non-abi3 wrong minor rejected",
      pb._compat_ok("cp39" if _cur != "cp39" else "cp38", "cp39", _cur) is False)
check("py3 pure-python usable", pb._compat_ok("py3", "none", _cur) is True)
# 别把cp310比数字
check("cp310 vs cp38 handled by tuple compare",
      pb._compat_ok("cp38", "abi3", "cp310") is True)

print("== wheel 解压完整性 ==")
import zipfile as _zip
_rt = tempfile.mkdtemp(prefix="pyqt5_extract_")
_good = os.path.join(_rt, "g.whl")
with _zip.ZipFile(_good, "w") as _z:
    _z.writestr("PyQt5/QtCore.pyd", b"Z" * 2048)
_target = os.path.join(_rt, "out")
pb._extract_wheel(_good, _target)
check("extracts declared bytes",
      os.path.getsize(os.path.join(_target, "PyQt5", "QtCore.pyd")) == 2048)
_trunc = os.path.join(_rt, "t.whl")
_raw = open(_good, "rb").read()
open(_trunc, "wb").write(_raw[: len(_raw) // 2])
_try = {"raised": False}
try:
    pb._extract_wheel(_trunc, os.path.join(_rt, "out2"))
except Exception:
    _try["raised"] = True
check("truncated wheel is rejected", _try["raised"] is True)

print("== _wheels_installed detects a fake linux runtime ==")
import tempfile
rt = tempfile.mkdtemp(prefix="pyqt5_rt_")
os.makedirs(os.path.join(rt, "PyQt5", "Qt5"), exist_ok=True)
#linux风格QtCore
open(os.path.join(rt, "PyQt5", "QtCore.cpython-314-x86_64-linux-gnu.so"), "w").close()
os.makedirs(os.path.join(rt, "PyQt5_sip-12.19.0.dist-info"), exist_ok=True)
check("detects linux-style runtime", pb._wheels_installed(rt) is True)

print("== _wheels_installed rejects empty runtime ==")
rt2 = tempfile.mkdtemp(prefix="pyqt5_rt_empty_")
check("rejects empty runtime", pb._wheels_installed(rt2) is False)

print("== Windows 全环境矩阵（重点） ==")
# 覆盖架构 x 位数全组合
_o_fam, _o_arch, _o_bits = pb._host_family, pb._machine, pb._interp_bits


def _win(cpu, bits, platform_field):
    pb._host_family = lambda: 'windows'
    pb._machine = lambda: pb._normalize_arch(cpu)
    pb._interp_bits = lambda: bits
    return pb._arch_rank(platform_field)


try:
    # 1) x64加64位Py
    check("x64/64bit -> win_amd64 exact",
          _win("AMD64", 64, "win_amd64") == 100)
    check("x64/64bit -> win32 WoW64 fallback",
          0 <= _win("AMD64", 64, "win32") < 100)
    check("x64/64bit -> win_arm64 rejected",
          _win("AMD64", 64, "win_arm64") < 0)
    check("x64/64bit interpreter arch is x86_64",
          (pb._host_family(), pb._interp_arch()) == ('windows', 'x86_64'))

    # 2) x64加32位Py
    check("x64/32bit -> win32 exact (NOT win_amd64)",
          _win("AMD64", 32, "win32") == 100)
    check("x64/32bit -> win_amd64 rejected",
          _win("AMD64", 32, "win_amd64") < 0)
    check("x64/32bit interpreter arch is x86",
          pb._interp_arch() == 'x86')

    # 3) ARM64原生64
    check("arm64/64bit -> win_arm64 exact",
          _win("ARM64", 64, "win_arm64") == 100)
    check("arm64/64bit -> win_amd64 emulation fallback",
          0 < _win("ARM64", 64, "win_amd64") < 100)
    check("arm64/64bit -> win32 lower fallback",
          0 < _win("ARM64", 64, "win32")
          < _win("ARM64", 64, "win_amd64"))

    # 4) ARM64加32位
    check("arm64/32bit -> win32 exact",
          _win("ARM64", 32, "win32") == 100)
    check("arm64/32bit -> win_amd64 rejected",
          _win("ARM64", 32, "win_amd64") < 0)
    check("arm64/32bit -> win_arm64 rejected",
          _win("ARM64", 32, "win_arm64") < 0)

    # 5) 纯32位Win
    check("x86/32bit -> win32 exact",
          _win("x86", 32, "win32") == 100)
    check("x86/32bit -> win_amd64 rejected",
          _win("x86", 32, "win_amd64") < 0)

    # 6) 每组合都要有可用项
    for cpu, bits in (("AMD64", 64), ("AMD64", 32), ("ARM64", 64),
                      ("ARM64", 32), ("x86", 32)):
        usable = [w for w in ("win_amd64", "win32", "win_arm64")
                  if _win(cpu, bits, w) >= 0]
        check("win %s/%dbit has a usable wheel" % (cpu, bits),
              len(usable) > 0)
finally:
    pb._host_family, pb._machine, pb._interp_bits = _o_fam, _o_arch, _o_bits

print("== 跨平台自适应：各系统/架构下应选中的 wheel ==")
# 替换归一化模拟平台


def _sim(fam, arch, bits, platform_field):
    pb._host_family = lambda: fam
    pb._machine = lambda: pb._normalize_arch(arch)
    pb._interp_bits = lambda: bits
    return pb._arch_rank(platform_field)


try:
    # --- Windows ---
    check("win x64 -> win_amd64 exact",
          _sim("windows", "x86_64", 64, "win_amd64") == 100)
    check("win x64 -> win32 downgraded (WoW64)",
          0 <= _sim("windows", "x86_64", 64, "win32") < 100)
    check("win x64 -> win_arm64 rejected",
          _sim("windows", "x86_64", 64, "win_arm64") < 0)
    check("win 32bit -> win32 exact",
          _sim("windows", "x86", 32, "win32") == 100)
    check("win 32bit -> win_amd64 rejected",
          _sim("windows", "x86", 32, "win_amd64") < 0)
    #无win_arm64降x64
    check("win arm64 -> win_amd64 via emulation",
          0 <= _sim("windows", "arm64", 64, "win_amd64") < 100)
    check("win arm64 -> win_arm64 exact",
          _sim("windows", "arm64", 64, "win_arm64") == 100)

    # --- macOS ---
    check("mac arm64 -> arm64 exact",
          _sim("macos", "arm64", 64, "macosx_11_0_arm64") == 100)
    check("mac arm64 -> universal2 usable",
          _sim("macos", "arm64", 64, "macosx_11_0_universal2") > 0)
    # Rosetta降级低
    check("mac arm64 -> x86_64 demoted via Rosetta",
          0 < _sim("macos", "arm64", 64, "macosx_11_0_x86_64") < 100)
    check("mac x86_64 -> x86_64 exact",
          _sim("macos", "x86_64", 64, "macosx_10_13_x86_64") == 100)
    #Intel不跑arm64
    check("mac x86_64 -> arm64 rejected",
          _sim("macos", "x86_64", 64, "macosx_11_0_arm64") < 0)
    check("mac x86_64 -> legacy intel usable",
          _sim("macos", "x86_64", 64, "macosx_10_6_intel") > 0)

    # --- Linux ---
    check("linux x64 -> manylinux x86_64 exact",
          _sim("linux", "x86_64", 64, "manylinux_2_17_x86_64") == 100)
    check("linux x64 -> win32 rejected",
          _sim("linux", "x86_64", 64, "win32") < 0)
    check("linux arm64 -> aarch64 exact",
          _sim("linux", "arm64", 64, "manylinux_2_17_aarch64") == 100)
    check("linux arm64 -> x86_64 rejected",
          _sim("linux", "arm64", 64, "manylinux_2_17_x86_64") < 0)
    check("linux armv7 -> armv7l exact",
          _sim("linux", "armv7", 32, "manylinux_2_17_armv7l") == 100)

    # --- 绝不允许跨平台族误选 ---
    for host in (("windows", "x86_64", 64), ("macos", "arm64", 64),
                 ("linux", "x86_64", 64)):
        for foreign in ("win32", "win_amd64", "macosx_11_0_arm64",
                        "manylinux_2_17_x86_64", "manylinux_2_17_aarch64"):
            r = _sim(host[0], host[1], host[2], foreign)
            fw = pb._parse_platform_field(foreign)[0]
            if fw != host[0]:
                check("no cross-family leak %s on %s" % (foreign, host[0]),
                      r < 0)
finally:
    pb._host_family, pb._machine, pb._interp_bits = _o_fam, _o_arch, _o_bits

print("== 平台标签解析 ==")
check("parse win_amd64", pb._parse_platform_field("win_amd64")
      == ("windows", "x86_64", 64))
check("parse win32", pb._parse_platform_field("win32")
      == ("windows", "x86", 32))
check("parse universal2", pb._parse_platform_field("macosx_10_9_universal2")
      == ("macos", "universal2", 64))
check("parse any", pb._parse_platform_field("any")[0] == "any")
check("parse garbage -> None", pb._parse_platform_field("zzz-unknown")[0] is None)

print("== 架构名归一化 ==")
for raw, want in (("AMD64", "x86_64"), ("x86_64", "x86_64"),
                  ("ARM64", "arm64"), ("aarch64", "arm64"),
                  ("armv7l", "armv7"), ("i686", "x86"),
                  ("riscv64", "riscv64")):
    check("normalize %-10s -> %s" % (raw, want),
          pb._normalize_arch(raw) == want)

print()
print("TOTAL FAILURES:", len(fails), fails)
sys.exit(1 if fails else 0)
