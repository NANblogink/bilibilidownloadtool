"""
PyQt5 运行时按需下载 / 解压 / 注入模块（精简包专用）。

精简打包不把 PyQt5 打进程序包；本模块在首次启动（或安装阶段）:
  1. 从镜像解析并下载 PyQt5 / PyQt5-Qt5 / PyQt5_sip 三个 wheel（zip 压缩）
  2. 原地解压到可写的 runtime 目录
  3. 把 runtime 目录加入 sys.path，供随后的 import PyQt5 使用
不依赖系统 python / pip，也不依赖网络之外的工具。

被 boot.py（精简包入口，不 import PyQt5）与 installer.py 复用。

注意：本模块自身不允许顶层 import PyQt5（否则会把 PyQt5 拖回打包依赖）。
"""
import os
import sys
import re
import time
import zipfile
import tempfile
import urllib.request

PYQT5_VER = "5.15.11"  # 5.15 末版，兼容 3.8+


# ---------------------------------------------------------------- 平台标签
#
#平台族ABI须匹配
# 否则导入失败
#
# 历史缺陷（本次全部修复）：
# 只看架构会选错平台族
#macosx会误选
# 不分32与64位
#64位下32whe
#WinOnARM->32
#LinuxARM归一
#
# 解析成家族架构位数
#标签逐字段比

_WIN_FAMILY = 'windows'
_MAC_FAMILY = 'macos'
_LINUX_FAMILY = 'linux'


def _machine():
    """归一化 CPU 架构名（跨平台别名 -> 统一小写标识）。"""
    try:
        import platform as _pf
        m = (_pf.machine() or '').lower()
    except Exception:
        m = ''
    return _normalize_arch(m)


def _normalize_arch(m):
    """把各种架构别名归一化。独立出来便于测试与复用。"""
    m = (m or '').lower()
    # x86 家族
    if m in ('amd64', 'x86_64', 'x64', 'em64t'):
        return 'x86_64'
    # 32 位 x86
    if m in ('i386', 'i486', 'i586', 'i686', 'x86', 'ia32', 'win32'):
        return 'x86'
    # ARM 64 位
    if m in ('arm64', 'aarch64', 'armv8l', 'arm64e'):
        return 'arm64'
    # ARM 32 位（树莓派等）
    if m.startswith('armv') or m in ('arm', 'armhf', 'armel'):
        return 'armv7'
    # 其它架构原样返回
    if m in ('riscv64', 'ppc64le', 'ppc64', 's390x', 'loongarch64', 'mips64'):
        return m
    return m or 'x86_64'


def _host_family():
    """当前运行环境所属的平台族。"""
    p = sys.platform or ''
    if p.startswith('win'):
        return _WIN_FAMILY
    if p.startswith('darwin'):
        return _MAC_FAMILY
    #freebsd
    return _LINUX_FAMILY


def _interp_bits():
    """当前解释器位数（32 / 64）。用最大整数位宽判断，比平台字符串可靠。"""
    try:
        import struct
        return struct.calcsize("P") * 8
    except Exception:
        return 64


def platform_tag():
    """返回当前平台在 wheel 文件名中使用的标签（小写，仅用于日志/展示）。"""
    fam = _host_family()
    if fam == _WIN_FAMILY:
        return _win_arch_tag()
    if fam == _MAC_FAMILY:
        #macosx_arm
        return _interp_arch()
    #manylinux_a
    return _linux_arch_tag(_interp_arch())


def _win_arch_tag(arch=None):
    """本机 Windows 解释器应使用的 wheel 架构标签。

    关键原则：**决定 wheel 的是解释器的架构，不是 CPU 的架构**。
    wheel 里的 .pyd 由 Python 进程加载，因此：
      * 32 位 Python 跑在 64 位 Windows 上 -> 只能装 win32
        （这是极常见的真实配置，早期实现会在这里全部落空）
      * 64 位 Python 跑在 ARM64 Windows 上 -> 原生是 win_arm64；
        若解释器其实是 x64 模拟进程，则应装 win_amd64。
    统一用 _interp_arch() 判定，避免各处各判一套。
    """
    ia = _interp_arch()
    if ia == 'x86_64':
        return 'win_amd64'
    if ia == 'arm64':
        return 'win_arm64'
    return 'win32'


def _interp_arch():
    """解释器自身的架构（决定它能加载哪种 wheel）。

    与 _machine()（CPU 架构）不同：32 位 Python 跑在 64 位 Windows 上时，
    这里必须返回 x86。
    """
    bits = _interp_bits()
    cpu = _machine()
    if bits == 32:
        #32位随CPU家族
        #x86与WoW64
        #ARM64:32位
        #ARMv7:32位v7
        if cpu in ('armv7', 'arm'):
            return 'armv7'
        return 'x86'
    #64位分x64
    if cpu == 'arm64':
        return 'arm64'
    if cpu in ('armv7', 'arm'):
        #64位跑32位ARM
        return 'armv7'
    return cpu if cpu not in ('x86',) else 'x86_64'


def _linux_arch_tag(arch):
    """Linux wheel 使用的架构标签。"""
    return {
        'x86_64': 'x86_64',
        'x86': 'i686',
        'arm64': 'aarch64',
        'armv7': 'armv7l',
        'riscv64': 'riscv64',
        'ppc64le': 'ppc64le',
        's390x': 's390x',
        'loongarch64': 'loongarch64',
    }.get(arch, arch)


def platform_tag_aliases():
    """平台标签的候选集合，仅用于粗筛（真正判定走 _platform_arch_ok）。"""
    fam = _host_family()
    if fam == _WIN_FAMILY:
        # 只留win家族
        return {'win', 'win32', 'win_amd64', 'win_arm64', platform_tag()}
    if fam == _MAC_FAMILY:
        return {'macosx', 'universal2', 'intel', 'fat', 'arm64', 'x86_64'}
    return {'manylinux', 'musllinux', 'linux', 'manylinux1', 'manylinux2010',
            'manylinux2014', 'linux_' + _linux_arch_tag(_interp_arch())}


def _parse_platform_field(pf):
    """把 wheel 平台标签解析成 (family, arch, bits)。

    返回 family 为 None 表示无法识别。
    """
    pf = (pf or '').lower().strip()
    if not pf:
        return (None, None, None)
    if pf == 'any':
        return ('any', 'any', None)

    # ---- Windows ----
    if 'win_amd64' in pf:
        return (_WIN_FAMILY, 'x86_64', 64)
    if 'win_arm64' in pf:
        return (_WIN_FAMILY, 'arm64', 64)
    if pf.startswith('win32') or pf == 'win32':
        return (_WIN_FAMILY, 'x86', 32)
    if pf.startswith('win'):
        return (_WIN_FAMILY, 'x86', 32)

    # ---- macOS ----
    if pf.startswith('macosx') or 'macosx' in pf:
        if 'universal2' in pf:
            #Intel+Apple
            return (_MAC_FAMILY, 'universal2', 64)
        if 'arm64' in pf:
            return (_MAC_FAMILY, 'arm64', 64)
        if 'x86_64' in pf:
            return (_MAC_FAMILY, 'x86_64', 64)
        if 'intel' in pf or 'i386' in pf or 'fat' in pf:
            #fat仅x86可用
            return (_MAC_FAMILY, 'x86_64', 64)
        return (_MAC_FAMILY, 'unknown', 64)

    # ---- Linux ----
    if ('manylinux' in pf or 'musllinux' in pf or 'linux' in pf):
        if 'aarch64' in pf:
            return (_LINUX_FAMILY, 'arm64', 64)
        if 'armv7l' in pf or 'armv6l' in pf or 'armhf' in pf:
            return (_LINUX_FAMILY, 'armv7', 32)
        if 'x86_64' in pf or 'amd64' in pf:
            return (_LINUX_FAMILY, 'x86_64', 64)
        if 'i686' in pf or 'i386' in pf:
            return (_LINUX_FAMILY, 'x86', 32)
        if 'riscv64' in pf:
            return (_LINUX_FAMILY, 'riscv64', 64)
        if 'ppc64le' in pf:
            return (_LINUX_FAMILY, 'ppc64le', 64)
        if 's390x' in pf:
            return (_LINUX_FAMILY, 's390x', 64)
        if 'loongarch64' in pf:
            return (_LINUX_FAMILY, 'loongarch64', 64)
        return (_LINUX_FAMILY, 'unknown', None)

    return (None, None, None)


def _arch_rank(platform_field):
    """返回 wheel 与本机的契合度（越大越合适，-1 表示不可用）。

    判定基准是**解释器架构**（_interp_arch），因为 wheel 里的扩展模块
    由 Python 进程加载，能否加载取决于解释器而不是 CPU。

    Windows 上的自适应降级规则：
      * 32 位 Python（无论跑在 x86 / x64 / ARM64 Windows 上）
        -> 首选 win32（唯一可行）
      * 64 位 Python on x64  -> 首选 win_amd64，win32 作 WoW64 降级
      * 64 位 Python on ARM64 -> 首选 win_arm64；上游不发布时
        降级用 win_amd64（x64 模拟），再退 win32
    """
    fam_h = _host_family()
    ia = _interp_arch()
    bits_h = _interp_bits()
    cpu_h = _machine()
    fam_w, arch_w, bits_w = _parse_platform_field(platform_field)

    if fam_w == 'any':
        return 50  #纯python都可用
    if fam_w != fam_h:
        return -1  # 平台族不符，绝不可用

    # ---- Windows ----
    if fam_h == _WIN_FAMILY:
        want = _win_arch_tag()          # 解释器应使用的标签
        if arch_w == ia and (bits_w is None or bits_w == bits_h):
            return 100                  # 完全匹配
        if arch_w == want:
            return 100
        #wheel:WoW64
        if ia == 'x86_64' and arch_w == 'x86' and bits_w == 32:
            return 40
        #ARM64可跑x64
        if ia == 'arm64' and arch_w == 'x86_64' and bits_w == 64:
            return 60
        if ia == 'arm64' and arch_w == 'x86' and bits_w == 32:
            return 30
        return -1

    # ---- macOS ----
    if fam_h == _MAC_FAMILY:
        if arch_w == 'universal2' and bits_h == 64:
            return 95                  #Intel+Apple
        if arch_w == ia and (bits_w is None or bits_w == bits_h):
            return 100
        if ia == 'x86_64' and arch_w == 'x86_64':
            return 90
        #经Rosetta2
        if ia == 'arm64' and arch_w == 'x86_64' and bits_h == 64:
            return 70
        return -1

    # ---- Linux ----
    if arch_w == ia and (bits_w is None or bits_w == bits_h):
        return 100
    #64位x86需32位
    if ia == 'x86_64' and bits_h == 64 and arch_w == 'x86' and bits_w == 32:
        return 30
    return -1


def _platform_arch_ok(platform_field):
    """wheel 是否可用（严格匹配或系统支持的降级组合）。

    严格匹配优先；没有严格匹配时允许架构降级（见 _arch_rank），
    以保证在 PyQt5 未发布对应架构 wheel 的平台上仍能装起来。
    """
    return _arch_rank(platform_field) >= 0


_PLATFORM_TAG = platform_tag()

# 解释器标签供调试
_PY_TAG = "cp%d%d" % (sys.version_info.major, sys.version_info.minor)

# 国内源优先逐个重试
MIRROR_SIMPLE = [
    "https://mirrors.cloud.tencent.com/pypi/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple",
]


def local_wheel_dirs():
    """随包内置 / 用户可放置的本地 wheel 目录（优先级最高，无需联网）。

    发布版把 wheel 直接放在程序目录下，这样**离线环境、内网、被墙**
    的机器也能安装，不会因为下不到 PyQt5 而完全无法启动。

    查找顺序（先找到先用）：
      1. <程序目录>/wheels                —— 随包附带
      2. <程序目录>/_internal/wheels      —— PyInstaller onedir 内部布局
      3. <运行库目录> 同级 wheels          —— 运行库旁边
      4. %LOCALAPPDATA%/BilibiliDownloader/wheels —— 用户手动放置
    """
    dirs = []
    try:
        here = os.path.dirname(os.path.abspath(__file__))
    except Exception:
        here = os.getcwd()

    #候选根为本目录
    # 冻结时含exe目录
    # 模块同级都能找到。
    roots = []
    try:
        if getattr(sys, "frozen", False):
            roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    except Exception:
        pass
    roots.append(here)
    p = here
    for _ in range(3):           # 向上找最多 3 层
        parent = os.path.dirname(p)
        if not parent or parent == p:
            break
        roots.append(parent)
        p = parent
    try:
        roots.append(runtime_dir())
    except Exception:
        pass

    for r in roots:
        if not r:
            continue
        dirs.append(os.path.join(r, "wheels"))
        dirs.append(os.path.join(r, "_internal", "wheels"))

    # 用户级缓存目录
    try:
        la = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        dirs.append(os.path.join(la, "BilibiliDownloader", "wheels"))
    except Exception:
        pass

    out = []
    seen = set()
    for d in dirs:
        try:
            key = os.path.normcase(os.path.abspath(d))
        except Exception:
            continue
        if key in seen:
            continue
        seen.add(key)
        if os.path.isdir(d):
            out.append(d)
    return out


def _scan_local_wheels(directory, name_prefix=None):
    """扫描本地目录里的 wheel，返回可用于本机的候选列表。"""
    entries = []
    try:
        names = os.listdir(directory)
    except Exception:
        return entries
    for n in names:
        if not n.lower().endswith(".whl"):
            continue
        if not _looks_like_candidate(n.lower()):
            continue
        try:
            p = _split_wheel(n)
        except Exception:
            continue
        if name_prefix and p["name"].lower() != name_prefix.lower():
            continue
        if not _platform_arch_ok(p["platform"]):
            continue
        entries.append({
            "filename": n,
            "url": os.path.join(directory, n),   # 本地路径当 url 用
            "local": True,
        })
    return entries

_log = lambda *a: print(*a)


def set_log_callback(cb):
    global _log
    _log = cb


def runtime_dir():
    """返回可写的 PyQt5 运行时目录。
    优先包内 _internal（onedir 的 sys._MEIPASS），绿色版若只读则回退 AppData。
    """
    base = None
    try:
        base = sys._MEIPASS
    except AttributeError:
        base = (os.path.dirname(sys.executable) if getattr(sys, "frozen", False)
                else os.path.dirname(os.path.abspath(__file__)))

    candidates = []
    if base:
        candidates.append(os.path.join(base, "pyqt5_runtime"))
    try:
        if sys.platform == 'win32':
            _appdir = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        elif sys.platform == 'darwin':
            _appdir = os.path.expanduser("~/Library/Application Support")
        else:
            _appdir = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
        candidates.append(os.path.join(_appdir, "BilibiliDownloadTool", "pyqt5_runtime"))
    except Exception:
        pass
    try:
        candidates.append(os.path.join(tempfile.gettempdir(), "pyqt5_runtime"))
    except Exception:
        pass

    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            t = os.path.join(d, ".wtest")
            with open(t, "w") as f:
                f.write("ok")
            os.remove(t)
            return d
        except Exception:
            continue
    return os.path.join(tempfile.gettempdir(), "pyqt5_runtime_%s" % os.getpid())


# ---------------------------------------------------------------- wheel 选择


def _split_wheel(filename):
    """解析 wheel 文件名的组件。返回 dict: name/version/pyver/abi/platform"""
    core = filename[:-4] if filename.endswith(".whl") else filename
    parts = core.split("-")
    plat = parts[-1]
    abi = parts[-2]
    pyver = parts[-3]
    version = parts[-4]
    name = "-".join(parts[:-4])
    return {"name": name, "version": version, "pyver": pyver, "abi": abi, "platform": plat}


def _py_tag_tuple(tag):
    """把 'cp310' / 'cp38' 解析成 (3, 10) / (3, 8)；无法解析返回 None。

    注意：不能直接比较 'cp310' 与 'cp38' 的数字部分（310 > 38 会得出
    错误结论），必须拆成 (主版本, 次版本) 元组再比较。
    """
    s = (tag or '').lower()
    if not s.startswith('cp') or not s[2:].isdigit():
        return None
    d = s[2:]
    if len(d) <= 1:
        return None
    return (int(d[0]), int(d[1:]))


def _compat_ok(pyver, abi, cur):
    """判断 wheel 的解释器/ABI 标签能否在当前解释器上使用。"""
    cur_tag = "cp%d%d" % (sys.version_info.major, sys.version_info.minor)
    pyver = (pyver or '').strip().lower()
    abi = (abi or '').strip().lower()

    #纯python都可
    if pyver in ("py3", "py2.py3", "py2.py3-none", "any"):
        return True

    cur_ver = _py_tag_tuple(cur_tag)
    want_ver = _py_tag_tuple(pyver)
    if want_ver is None:
        return False

    #abi3向前兼容
    # 目标版本不高于解释器
    if abi == "abi3":
        if cur_ver is None:
            return False
        return want_ver <= cur_ver

    #非abi3须一致
    #sip310给3.10
    return cur_ver is not None and want_ver == cur_ver


def _load_simple_entries(mirror, package):
    """抓取 simple 页并解析成 [{filename, url}]"""
    page = "%s/%s/" % (mirror.rstrip("/"), package)
    req = urllib.request.Request(page, headers={"User-Agent":
        "Mozilla/5.0 BilibiliDownloadTool/2.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode("utf-8", "ignore")
    from urllib.parse import urljoin
    entries = []
    for m in re.finditer(r'href="([^"]+\.whl[^"]*)"', data):
        href = m.group(1).split("#")[0]
        fn = href.split("/")[-1]
        low = fn.lower()
        # 先按文件名粗筛
        #判定给arch_ok
        if not _looks_like_candidate(low):
            continue
        try:
            _plat = _split_wheel(fn)["platform"]
        except Exception:
            continue
        if not _platform_arch_ok(_plat):
            continue
        url = urljoin(page, href)
        entries.append({"filename": fn, "url": url})
    return entries


def _looks_like_candidate(low):
    """廉价粗筛：判断 wheel 文件名是否可能属于本机。

    仅用于减少后续解析量，命中后仍需 _platform_arch_ok 精确判定。
    any 结尾的纯 python wheel 一律放行。
    """
    if low.endswith('-any.whl') or '-any.' in low:
        return True
    fam = _host_family()
    if fam == _WIN_FAMILY:
        return 'win' in low
    if fam == _MAC_FAMILY:
        return 'macosx' in low or 'darwin' in low
    #接受manylin
    if 'win' in low or 'macosx' in low or 'darwin' in low:
        return False
    return ('manylinux' in low or 'musllinux' in low
            or 'linux' in low)


def _best_wheel(entries, name_prefix=None, want_version=None, wants_cp310_first=True):
    """在抓到的 wheel 列表里挑最合适的（平台已过滤，这里按兼容性/版本排序）。"""
    cur_tag = "cp%d%d" % (sys.version_info.major, sys.version_info.minor)
    candidates = []
    for e in entries:
        p = _split_wheel(e["filename"])
        if name_prefix and p["name"].lower() != name_prefix.lower():
            continue
        if not _compat_ok(p["pyver"], p["abi"], cur_tag):
            continue
        item = dict(p)
        item["filename"] = e["filename"]
        item["url"] = e["url"]
        candidates.append(item)
    if not candidates:
        return None

    def rank(p):
        score = 0
        pyver_cp = ""
        if p["pyver"].startswith("cp"):
            pyver_cp = p["pyver"]
        #100降级30到60
        ar = _arch_rank(p.get("platform"))
        if ar < 0:
            score -= 10000
        else:
            score += ar * 10
        if want_version:
            if p["version"] == want_version:
                score += 100
            elif p["version"].startswith(want_version + "."):
                score += 90
        score += (10 if p["abi"] == "abi3" else 0)
        if pyver_cp == cur_tag:
            score += 50  # 精确abi最优先
        if p["abi"] == "none":
            score += 5  #py3-none纯py
        # 版本越新越靠前
        try:
            vparts = p["version"].split(".")
            score += sum(int(x) for x in vparts) * 0.01
        except Exception:
            pass
        return -score

    candidates.sort(key=rank)
    return candidates[0]


# ---------------------------------------------------------------- 下载与解压


def _download(url, dest, title="", retries=3):
    """把 wheel 取到 dest。

    支持两种来源：
      * 本地文件路径（随包内置的 wheels 目录）—— 直接复制，无需联网
      * http(s) URL —— 流式下载

    下载完成后按 Content-Length 校验字节数：镜像/网络提前断流会留下
    截断的 wheel，解压时才会失败，表象就是"库装不全"。这里当场发现
    并重试，避免把残缺文件带进解压流程。
    """
    # ---- 本地文件：离线安装路径 ----
    if not str(url).lower().startswith(("http://", "https://")):
        src = str(url)
        if not os.path.isfile(src):
            raise IOError("本地 wheel 不存在: %s" % src)
        _log("    使用内置组件: %s" % os.path.basename(src))
        try:
            import shutil
            shutil.copyfile(src, dest)
        except Exception as e:
            raise IOError("复制内置 wheel 失败: %s" % e)
        if os.path.getsize(dest) != os.path.getsize(src):
            raise IOError("复制后大小不一致: %s" % os.path.basename(src))
        return dest

    last_err = None
    for attempt in range(max(1, retries)):
        if attempt:
            _log("    下载中断，重试 %d/%d ..." % (attempt + 1, retries))
            try:
                time.sleep(2 * attempt)
            except Exception:
                pass
        try:
            req = urllib.request.Request(url, headers={"User-Agent":
                "Mozilla/5.0 BilibiliDownloadTool/2.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                chunk = 64 * 1024
                last_pct = -1
                with open(dest, "wb") as f:
                    while True:
                        b = r.read(chunk)
                        if not b:
                            break
                        f.write(b)
                        done += len(b)
                        if total:
                            pct = done * 100 // total
                            if pct != last_pct and (pct % 5 == 0 or pct == 100):
                                last_pct = pct
                                _log("%s %d%% (%d/%d MB)" % (title, pct, done // 1048576, total // 1048576))
                        elif not done % (8 * 1048576):
                            _log("%s %d MB" % (title, done // 1048576))
            # 声明长度未收够即失败
            if total and done < total:
                last_err = "下载不完整 %s: %d/%d 字节" % (title, done, total)
                _log("    " + last_err)
                continue
            if done == 0:
                last_err = "下载为空: %s" % title
                _log("    " + last_err)
                continue
            return dest
        except Exception as e:
            last_err = str(e)
            _log("    下载失败: %s" % e)
    raise IOError(last_err or ("下载失败: %s" % title))


def _remote_size(url):
    """尽力获取远端文件大小；失败返回 0（不阻断安装流程）。"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":
            "Mozilla/5.0 BilibiliDownloadTool/2.1"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def _extract_wheel(whl, rt):
    """把 wheel 解压到 rt，并在解压后校验关键文件确实落盘。

    历史实现直接 zf.extract 循环，遇到个别条目写入失败会静默跳过，
    最终 is_ready 才失败，用户看到的就是"装不全"。这里改为逐条记录，
    对 nbytes 与 mtime 做基本校验，任何条目失败都抛出以便换镜像重试。
    """
    os.makedirs(rt, exist_ok=True)
    rt_plain = os.path.normpath(rt)
    #Win超260失败
    # 安装目录深时易触发
    # 解压才用扩展前缀
    # 校验仍用原始路径
    rt_long = _win_long_path(rt_plain)
    with zipfile.ZipFile(whl) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise IOError("wheel 内文件损坏: %s" % bad)
        for info in zf.infolist():
            name = info.filename
            # 防目录穿越
            target = os.path.normpath(os.path.join(rt_plain, name))
            base = os.path.normcase(rt_plain) + os.sep
            if not os.path.normcase(target).startswith(base):
                if os.path.normcase(target) != os.path.normcase(rt_plain):
                    continue
            try:
                zf.extract(info, rt_long)
            except Exception as e:
                # 杀软占用常见需重试
                if not _extract_with_retry(zf, info, rt_long):
                    raise IOError("解压失败 %s: %s" % (name, e))
            # 须确认落盘且大小一致
            if not name.endswith('/') and info.file_size > 0:
                if not os.path.exists(target) or os.path.getsize(target) != info.file_size:
                    raise IOError("解压后文件不完整: %s" % name)
        return len(zf.infolist())


def _extract_with_retry(zf, info, rt, attempts=4):
    """解压单个条目，遇到 Windows 常见的短暂占用/WinError 时重试。"""
    import time as _t
    for i in range(max(1, attempts)):
        try:
            zf.extract(info, rt)
            return True
        except Exception:
            _t.sleep(0.3 * (i + 1))
            # 被占住先删再重试
            try:
                tgt = os.path.normpath(os.path.join(rt, info.filename))
                if os.path.isfile(tgt):
                    os.remove(tgt)
            except Exception:
                pass
    return False


def _win_long_path(p):
    """Windows 下给路径加上 \\\\?\\ 前缀以支持超过 260 字符的路径。

    非 Windows 或已是扩展路径时原样返回。失败时安全回退。
    """
    if sys.platform != 'win32':
        return p
    try:
        if not p or p.startswith('\\\\?\\'):
            return p
        ap = os.path.abspath(p)
        if ap.startswith('\\\\'):        # UNC转\?\UNC\
            return '\\\\?\\UNC\\' + ap[2:]
        return '\\\\?\\' + ap
    except Exception:
        return p


def _platform_plugin_names():
    """当前平台 Qt platform 插件的库文件名候选。"""
    if sys.platform == 'win32':
        return ('qwindows.dll',)
    if sys.platform == 'darwin':
        return ('libqcocoa.dylib', 'libqcocoa.so')
    return ('libqxcb.so', 'libqwayland.so', 'libqeglfs.so')


def _webengine_process_names():
    """QtWebEngine 主程序在当前平台的文件名候选。"""
    if sys.platform == 'win32':
        return ('QtWebEngineProcess.exe',)
    return ('QtWebEngineProcess', 'QtWebEngineProcess.app')


def _jqpath_plugins(runtime):
    """定位 Qt 平台插件目录 plugins（内含各平台的平台插件），找不到返回 None。"""
    names = _platform_plugin_names()
    for root, dirs, files in os.walk(runtime):
        platforms = os.path.join(root, "platforms")
        if os.path.isdir(platforms):
            try:
                present = os.listdir(platforms)
            except Exception:
                present = []
            if any(n in present for n in names):
                #返回plugins
                if os.path.basename(root) == "plugins":
                    return root
                for n in names:
                    if n in present:
                        return root
        if root.replace("\\", "/").endswith("/plugins") and os.path.isdir(platforms):
            return root
    return None


def _wheels_installed(runtime):
    """基础 PyQt5/Qt5/sip 三个 wheel 都解压就位才算完成（幂等标志）。

    扩展模块在各平台的扩展名不同：Windows .pyd / macOS .so / Linux .so，
    因此这里按"PyQt5 目录内存在任意 QtCore 扩展模块"来判断。
    """
    pydir = os.path.join(runtime, "PyQt5")
    if not os.path.isdir(pydir):
        return False
    try:
        entries = os.listdir(pydir)
    except Exception:
        return False
    # QtCore扩展模块
    has_qtcore = any(
        e == "QtCore.pyd" or
        e.startswith("QtCore.") and e.endswith(".so") or
        e.startswith("QtCore.so")
        for e in entries
    )
    if not has_qtcore:
        return False
    #有Qt库或插件
    qt_ok = (os.path.isdir(os.path.join(pydir, "Qt5"))
             or os.path.isdir(os.path.join(runtime, "Qt5")))
    # sip可能是目录
    #或只有dist
    try:
        rt_entries = os.listdir(runtime)
    except Exception:
        rt_entries = []
    sip_ok = any(d.lower().startswith("pyqt5_sip") for d in rt_entries)
    return qt_ok and sip_ok


def _find_in_runtime(runtime, *names):
    """在 runtime 目录下递归查找任一文件名，返回命中文件的绝对路径，找不到返回 None。"""
    lo = {n.lower() for n in names}
    for root, dirs, files in os.walk(runtime):
        for f in files:
            if f.lower() in lo:
                return os.path.join(root, f)
    return None


def _webengine_installed(runtime):
    """WebEngine（人机验证组件）是否已就位。以关键二进制 / 资源文件是否存在为准。"""
    names = list(_webengine_process_names()) + [
        "Qt5WebEngineWidgets.dll", "QtWebEngineWidgets", "qtwebengine_resources.pak",
    ]
    hit = _find_in_runtime(runtime, *names)
    if hit:
        return True
    #Versions/5
    for root, dirs, files in os.walk(runtime):
        for d in dirs:
            if d.startswith("QtWebEngineCore.framework"):
                return True
    return False


def _setup_webengine_env(runtime):
    """WebEngine 解压后设置进程/资源路径环境变量（精简包 _internal 无 PyQt5，必须指向 runtime）。"""
    proc = _find_in_runtime(runtime, *_webengine_process_names())
    if proc:
        os.environ["QTWEBENGINEPROCESS_PATH"] = proc
    pak = _find_in_runtime(runtime, "qtwebengine_resources.pak")
    if pak:
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = os.path.dirname(pak)
    else:
        #资源放Qt5下
        for cand in (os.path.join(runtime, "PyQt5", "Qt5", "resources"),
                     os.path.join(runtime, "Qt5", "resources")):
            if os.path.isdir(cand):
                os.environ["QTWEBENGINE_RESOURCES_PATH"] = cand
                break


def is_ready(runtime=None):
    """PyQt5 当前是否可用"""
    rt = runtime or runtime_dir()
    inserted = False
    if rt and rt not in sys.path:
        sys.path.insert(0, rt)
        inserted = True
    try:
        import PyQt5.QtWidgets  # noqa
        return True
    except Exception:
        return False


def deployed_runtime_dir():
    """安装程序部署好的运行时目录（若存在）。

    标准安装程序会把完整 Python 运行时 + PyQt5 部署到 <安装目录>/runtime，
    并在其中留下 deployed.json。这里检测它，目的是**复用**而不是
    再装一份 —— 两份 PyQt5 同时出现在 sys.path 会导致 Qt DLL 冲突，
    进程直接崩溃（0xC0000409 STATUS_STACK_BUFFER_OVERRUN）。
    """
    try:
        base = None
        if getattr(sys, "frozen", False):
            base = os.path.dirname(os.path.abspath(sys.executable))
        else:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if not base:
            return None
        rt = os.path.join(base, "runtime")
        sp = os.path.join(rt, "python", "Lib", "site-packages")
        if os.path.isdir(os.path.join(sp, "PyQt5")):
            return sp
    except Exception:
        pass
    return None


def register_qt_plugin_path(rt):
    """把 PyQt5 的 Qt 插件目录注册给 Qt。

    这是「This application failed to start because no Qt platform plugin
    could be initialized」的根治办法。

    为什么单设环境变量不够：
      * QT_QPA_PLATFORM_PLUGIN_PATH 只在 Qt **首次**初始化平台插件时被读取；
        如果 PyQt5 已经导入，再设环境变量不会生效。
      * PyQt5 从非标准目录（我们解压出来的 runtime/）加载时，Qt 默认
        不会去那里找插件。

    因此这里三重保险：
      1. 设环境变量（对尚未导入 PyQt5 的场景有效）；
      2. 若 QApplication 尚未创建，调用 QCoreApplication.addLibraryPath()；
      3. 预置 QT_PLUGIN_PATH，覆盖 Qt5/plugins 整体目录。

    返回实际注册的插件目录（无则 None）。
    """
    pd = _jqpath_plugins(rt)
    if not pd:
        return None

    #未导入PyQt5兜底
    try:
        os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = pd
        #Qt5/plugins
        qt_plugins_root = os.path.dirname(os.path.abspath(pd))
        if os.path.isdir(qt_plugins_root):
            os.environ["QT_PLUGIN_PATH"] = qt_plugins_root
        # 倾向用我们的插件
        os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(
            os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    except Exception:
        pass

    # 向Qt注册搜索路径
    try:
        from PyQt5.QtCore import QCoreApplication
        for p in (pd, os.path.dirname(os.path.abspath(pd))):
            if os.path.isdir(p):
                try:
                    QCoreApplication.addLibraryPath(p)
                except Exception:
                    pass
    except Exception:
        # 未就绪不算失败
        pass

    return pd


def ensure_qt_plugins(log=None):
    """在创建 QApplication 之前调用，确保平台插件可被找到。

    主程序（main.py）在构造 QApplication 前应调用本函数；
    即使 ensure_pyqt5 已经跑过，这里再注册一次也是幂等且安全的。
    """
    if log:
        try:
            log("正在注册 Qt 插件路径...")
        except Exception:
            pass

    # 先定位PyQt5目录
    cands = []
    try:
        import PyQt5  # noqa: F401
        cands.append(os.path.dirname(os.path.abspath(PyQt5.__file__)))
    except Exception:
        pass
    for d in (deployed_runtime_dir(), runtime_dir()):
        if d:
            cands.append(os.path.join(d, "PyQt5"))

    for base in cands:
        plugins = os.path.join(base, "Qt5", "plugins")
        pf = os.path.join(plugins, "platforms")
        if os.path.isdir(pf) and any(
                f.lower() == "qwindows.dll" for f in os.listdir(pf)):
            pd = register_qt_plugin_path(os.path.dirname(base)) or pf
            if log:
                try:
                    log("Qt 插件目录: %s" % (pd or pf))
                except Exception:
                    pass
            return pd or pf
    return None


def ensure_pyqt5(log=None, console=True, runtime=None):
    """确保 PyQt5 就位。返回 True/False。
    log:     进度回调；console: 是否允许 on Windows 调出控制台显示下载进度。
    runtime: 指定解压目标目录；默认用 runtime_dir()（供安装器预下载到已安装目录）。

    基础组件（PyQt5/Qt5/sip）与 WebEngine（人机验证）可分开增量下载：
    老版本只装过基础组件、缺 WebEngine 时会自动补装，不必重下全部。

    优先复用安装程序已部署的运行时，避免重复安装造成 DLL 冲突。
    """
    global _log
    if log:
        _log = log

    # 已部署则直接复用
    dep = deployed_runtime_dir()
    if dep and not runtime:
        if dep not in sys.path:
            sys.path.insert(0, dep)
        if is_ready(dep) and _wheels_installed(dep) and _webengine_installed(dep):
            _log("使用安装程序已部署的运行环境。")
            return True

    rt = runtime or runtime_dir()
    need_base = not _wheels_installed(rt)
    need_webengine = not _webengine_installed(rt)

    # 已就位则注入返回
    if rt not in sys.path:
        sys.path.insert(0, rt)
    if not need_base and not need_webengine and is_ready(rt):
        return True

    if console and sys.platform == "win32":
        _alloc_console()

    _log("正在准备 PyQt5 运行环境，请稍候...")
    packages = []
    if need_base:
        _log("  - 需要下载基础组件（PyQt5/Qt5/sip）")
        packages += [
            ("PyQt5", PYQT5_VER, False),
            ("PyQt5_Qt5", PYQT5_VER, False),
            ("PyQt5_sip", None, True),
        ]
    if need_webengine:
        _log("  - 需要下载人机验证(WebEngine)组件")
        # pyd与dll都要齐
        packages.append(("PyQtWebEngine", None, False))
        packages.append(("PyQtWebEngine_Qt5", None, False))

    # 索引包名一律小写
    pkg_names = {
        "PyQt5": "pyqt5",
        "PyQt5_Qt5": "pyqt5-qt5",
        "PyQt5_sip": "pyqt5-sip",
        "PyQtWebEngine": "pyqtwebengine",
        "PyQtWebEngine_Qt5": "pyqtwebengine-qt5",
    }

    ok = False
    tmp = None
    #记成功跨镜像用
    # 免得失败时从头重下
    done_pkgs = set()
    last_err = ""

    # 本地内置目录优先
    # 无网也能装上
    local_dirs = local_wheel_dirs()
    if local_dirs:
        _log("  发现本地组件目录: %s" % "; ".join(local_dirs))
    else:
        _log("  未发现本地组件目录，将使用在线镜像")

    for source in (["local"] + list(MIRROR_SIMPLE)):
        if len(done_pkgs) == len(packages):
            ok = True
            break
        is_local = (source == "local")
        if is_local:
            if not local_dirs:
                continue
            _log("  使用内置组件: %s" % local_dirs[0])
        else:
            _log("  使用镜像: %s" % source)
        try:
            tmp = tempfile.mkdtemp(prefix="pyqt5dl_")
            all_extracted = True
            for wheelname, want_ver, is_sip in packages:
                if wheelname in done_pkgs:
                    continue
                if is_local:
                    #挑最合适wheel
                    entries = []
                    for d in local_dirs:
                        entries += _scan_local_wheels(d, name_prefix=wheelname)
                else:
                    entries = _load_simple_entries(source, pkg_names[wheelname])
                chosen = _best_wheel(entries, name_prefix=wheelname, want_version=want_ver)
                if not chosen:
                    last_err = "未找到符合当前 Python 版本的 {0} wheel".format(wheelname)
                    _log("    " + last_err)
                    all_extracted = False
                    break
                if chosen.get("local"):
                    _log("    安装 {0}...".format(chosen["filename"]))
                else:
                    _log("    下载 {0}...".format(chosen["filename"]))
                whl = os.path.join(tmp, chosen["filename"])
                _download(chosen["url"], whl, "%s-%s" % (wheelname, chosen["version"]))
                #截断wheel失败
                # 表现为库装不全
                # 远端才需校验
                if not chosen.get("local"):
                    _expected = _remote_size(chosen["url"])
                    _actual = os.path.getsize(whl) if os.path.exists(whl) else 0
                    if _expected and _actual < _expected:
                        raise IOError(
                            "wheel 下载不完整: %s (%d/%d 字节)"
                            % (chosen["filename"], _actual, _expected))
                if not zipfile.is_zipfile(whl):
                    raise IOError("wheel 不是有效的 zip: %s" % chosen["filename"])
                #wheel即zip
                _extract_wheel(whl, rt)
                done_pkgs.add(wheelname)
                _log("    已就位: {0}".format(wheelname))
            if all_extracted:
                ok = True
                break
        except Exception as e:
            last_err = str(e)
            _log("    镜像失败: %s" % e)
        finally:
            try:
                if tmp:
                    import shutil
                    shutil.rmtree(tmp, ignore_errors=True)
            except Exception:
                pass

    if ok and rt not in sys.path:
        sys.path.insert(0, rt)
    if ok:
        register_qt_plugin_path(rt)
    if ok:
        _setup_webengine_env(rt)

    #能import为准
    # 历史实现只看解压完
    # 缺插件也报成功
    if ok:
        try:
            import importlib
            for _m in ("PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets"):
                importlib.import_module(_m)
        except Exception as _ie:
            _log("已解压但无法导入 %s: %s" % (_m, _ie))
            return False

        # 基础组件须齐全
        if not _wheels_installed(rt):
            _log("基础组件不完整（PyQt5/Qt5/sip 缺失），本次安装未完成")
            return False

        # 平台插件是弹窗前提
        if _jqpath_plugins(rt) is None:
            _log("警告：未找到 Qt 平台插件目录，界面可能无法显示")

        #WebEngine
        # 缺失只提示不阻断
        if need_webengine and not _webengine_installed(rt):
            _log("提示：人机验证组件(WebEngine)未就位，相关功能将不可用")

        return True

    # 所有镜像都失败
    #上游无本机wheel
    # 改用系统包管理器
    _log("未能通过 wheel 安装 PyQt5（最后错误：%s）" % (last_err or "未知"))
    if _try_system_pyqt5():
        if is_ready(rt):
            _log("已改用系统自带 PyQt5，继续启动。")
            return True
    _log("请手动安装 PyQt5 后重试：")
    for cmd in _system_install_hints():
        _log("    " + cmd)
    return ok and is_ready(rt)


def _system_install_hints():
    """按平台给出可复制的系统级安装命令（面向无法使用 wheel 的环境）。"""
    fam = _host_family()
    if fam == _LINUX_FAMILY:
        py = "python%d.%d" % (sys.version_info.major, sys.version_info.minor)
        return [
            "Debian/Ubuntu: sudo apt install python3-pyqt5 python3-pyqt5.qtwebengine",
            "Fedora/RHEL:   sudo dnf install python3-pyqt5",
            "Arch:          sudo pacman -S python-pyqt5",
            "或用 pip:      %s -m pip install PyQt5 PyQtWebEngine" % py,
        ]
    if fam == _MAC_FAMILY:
        return [
            "Homebrew: brew install pyqt@5",
            "或用 pip: python3 -m pip install PyQt5 PyQtWebEngine",
        ]
    return [
        "python -m pip install PyQt5 PyQtWebEngine==5.15.7",
    ]


def _try_system_pyqt5():
    """尝试使用系统已经装好的 PyQt5（不下载）。

    很多 Linux 发行版通过 apt/dnf/pacman 提供 PyQt5，直接可用；
    若系统已具备则该函数返回 True，让程序照常启动。
    """
    try:
        import importlib
        importlib.invalidate_caches()
        for m in ("PyQt5", "PyQt5.QtCore", "PyQt5.QtWidgets"):
            importlib.import_module(m)
        return True
    except Exception:
        pass
    #site-pkgs
    import glob
    cands = []
    for pat in (
        "/usr/lib/python3/dist-packages",
        "/usr/lib/python3*/site-packages",
        "/usr/local/lib/python3*/site-packages",
        "/opt/homebrew/lib/python3*/site-packages",
        "/usr/lib64/python3*/site-packages",
    ):
        cands.extend(glob.glob(pat))
    for c in cands:
        if c not in sys.path:
            sys.path.append(c)
    try:
        import importlib
        importlib.invalidate_caches()
        for m in ("PyQt5", "PyQt5.QtCore", "PyQt5.QtWidgets"):
            importlib.import_module(m)
        return True
    except Exception:
        return False


def _alloc_console():
    """Windows 下为无控制台的 windowed 进程调出一个控制台窗口显示下载进度。

    非 Windows 平台本身就是终端进程，无需（也无法）分配控制台。
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.AllocConsole()
        sys.stdout = os.fdopen(os.dup(ctypes.windll.kernel32.GetStdHandle(-11)), "w", encoding="utf-8")
        sys.stderr = sys.stdout
    except Exception:
        pass


def free_console():
    """下载完成后释放控制台，不留黑窗（仅 Windows 有意义）"""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


if __name__ == "__main__":
    #打印wheel地址
    for mirror in MIRROR_SIMPLE[:1]:
        for wheelname, pkg, want_ver in (("PyQt5", "pyqt5", PYQT5_VER),
                                         ("PyQt5_Qt5", "PyQt5-Qt5", PYQT5_VER),
                                         ("PyQt5_sip", "PyQt5-sip", None),
                                         ("PyQtWebEngine", "PyQtWebEngine", None),
                                         ("PyQtWebEngine_Qt5", "PyQtWebEngine-Qt5", None)):
            try:
                ents = _load_simple_entries(mirror, pkg.lower())
                c = _best_wheel(ents, name_prefix=wheelname,
                                want_version=want_ver)
                print(wheelname, "->", c["filename"] if c else "NONE")
            except Exception as e:
                print(wheelname, "ERR", e)