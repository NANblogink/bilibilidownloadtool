# -*- coding: utf-8 -*-
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
import zipfile
import tempfile
import urllib.request

PYQT5_VER = "5.15.11"  # PyQt5 最后一个 5.15 版本，cp38-abi3 兼容 Python 3.8+

# wheel 文件名统一不区分大小写比对用
_PLATFORM_TAG = "win_amd64"

# 简单索引（simple）镜像，逐个失败重试。腾讯/清华/阿里优先（国内快），最后 PyPI 官方兜底
MIRROR_SIMPLE = [
    "https://mirrors.cloud.tencent.com/pypi/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple",
]

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
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        candidates.append(os.path.join(appdata, "BilibiliDownloadTool", "pyqt5_runtime"))
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


def _compat_ok(pyver, abi, cur):
    cur_tag = "cp%d%d" % (sys.version_info.major, sys.version_info.minor)
    if pyver == "py3" or pyver == "py2.py3":
        return True
    if pyver.startswith("cp") and pyver[2:].isdigit() and int(pyver[2:]) <= 12:
        # 兼容任何具体 cp 或 abi3；pyver 是否 ≥ 当前解释器也在范围假设内
        pass
    if pyver.startswith("cp") and pyver[2:].isdigit():
        if abi == "abi3":
            return True
        if pyver == cur_tag:
            return True
        # 高于当前解释器版本的压缩 abi 不能用于当前解释器
        if int(pyver[2:]) > int(cur_tag[2:]):
            return False
        return True
    return False


def _load_simple_entries(mirror, package):
    """抓取 simple 页并解析成 [{filename, url}]"""
    page = "%s/%s/" % (mirror.rstrip("/"), package)
    req = urllib.request.Request(page, headers={"User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BilibiliDownloadTool/2.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read().decode("utf-8", "ignore")
    from urllib.parse import urljoin
    entries = []
    for m in re.finditer(r'href="([^"]+\.whl[^"]*)"', data):
        href = m.group(1).split("#")[0]
        if _PLATFORM_TAG not in href:
            continue
        fn = href.split("/")[-1]
        url = urljoin(page, href)
        entries.append({"filename": fn, "url": url})
    return entries


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
        if want_version:
            if p["version"] == want_version:
                score += 100
            elif p["version"].startswith(want_version + "."):
                score += 90
        score += (10 if p["abi"] == "abi3" else 0)
        if pyver_cp == cur_tag:
            score += 50  # 精确 abi 最优先（pyqt5_sip 只能精确匹配当前解释器）
        if p["abi"] == "none":
            score += 5  # py3-none 纯 python（如 PyQt5_Qt5）
        # 版本越新越靠前（小的常数列作 tiebreaker）
        try:
            vparts = p["version"].split(".")
            score += sum(int(x) for x in vparts) * 0.01
        except Exception:
            pass
        return -score

    candidates.sort(key=rank)
    return candidates[0]


# ---------------------------------------------------------------- 下载与解压


def _download(url, dest, title=""):
    """流式下载到 dest，进度每增约5%再回调 _log，避免刷屏。"""
    req = urllib.request.Request(url, headers={"User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) BilibiliDownloadTool/2.1"})
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
    return dest


def _jqpath_plugins(runtime):
    """定位 Qt 平台插件目录 plugins（内含 platforms/qwindows.dll），找不到返回 None。"""
    for root, dirs, files in os.walk(runtime):
        if "qwindows.dll" in os.path.join(root, "platforms") and "plugins" in root.split(os.sep):
            return root
        if root.replace("\\", "/").endswith("/plugins") and os.path.isdir(os.path.join(root, "platforms")):
            return root
    return None


def _wheels_installed(runtime):
    """基础 PyQt5/Qt5/sip 三个 wheel 都解压就位才算完成（幂等标志）"""
    required = (
        os.path.join(runtime, "PyQt5"),
        os.path.join(runtime, "PyQt5", "QtCore.pyd"),
    )
    for p in required:
        if not os.path.exists(p):
            return False
    # 至少有 Qt 库或插件其一，说明 Qt5 打进来了
    qt_ok = os.path.isdir(os.path.join(runtime, "PyQt5", "Qt5")) or os.path.isdir(os.path.join(runtime, "Qt5"))
    try:
        lists = os.listdir(runtime)
    except Exception:
        lists = []
    sip_ok = any(d for d in lists if d.lower().startswith("pyqt5_sip"))
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
    hit = _find_in_runtime(runtime, "QtWebEngineProcess.exe",
                           "Qt5WebEngineWidgets.dll", "qtwebengine_resources.pak")
    return hit is not None


def _setup_webengine_env(runtime):
    """WebEngine 解压后设置进程/资源路径环境变量（精简包 _internal 无 PyQt5，必须指向 runtime）。"""
    proc = _find_in_runtime(runtime, "QtWebEngineProcess.exe")
    if proc:
        os.environ["QTWEBENGINEPROCESS_PATH"] = proc
    pak = _find_in_runtime(runtime, "qtwebengine_resources.pak")
    if pak:
        os.environ["QTWEBENGINE_RESOURCES_PATH"] = os.path.dirname(pak)
    else:
        # 部分发布把资源放在 Qt5/resources
        res = os.path.join(runtime, "PyQt5", "Qt5", "resources")
        if os.path.isdir(res):
            os.environ["QTWEBENGINE_RESOURCES_PATH"] = res


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


def ensure_pyqt5(log=None, console=True, runtime=None):
    """确保 PyQt5 就位。返回 True/False。
    log:     进度回调；console: 是否允许 on Windows 调出控制台显示下载进度。
    runtime: 指定解压目标目录；默认用 runtime_dir()（供安装器预下载到已安装目录）。

    基础组件（PyQt5/Qt5/sip）与 WebEngine（人机验证）可分开增量下载：
    老版本只装过基础组件、缺 WebEngine 时会自动补装，不必重下全部。
    """
    global _log
    if log:
        _log = log

    rt = runtime or runtime_dir()
    need_base = not _wheels_installed(rt)
    need_webengine = not _webengine_installed(rt)

    # 已全部就位：注入路径后直接返回
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
        # 绑定层（PyQt5/QtWebEngineWidgets.pyd 等）与 Qt 运行层（Qt5WebEngine*.dll、QtWebEngineProcess.exe、resources）
        packages.append(("PyQtWebEngine", None, False))
        packages.append(("PyQtWebEngine_Qt5", None, False))

    # simple 索引里的包名（PyPI name 用小写），镜像路径区分大小写，一律小写
    pkg_names = {
        "PyQt5": "pyqt5",
        "PyQt5_Qt5": "pyqt5-qt5",
        "PyQt5_sip": "pyqt5-sip",
        "PyQtWebEngine": "pyqtwebengine",
        "PyQtWebEngine_Qt5": "pyqtwebengine-qt5",
    }

    ok = False
    tmp = None
    for mirror in MIRROR_SIMPLE:
        _log("  使用镜像: %s" % mirror)
        try:
            tmp = tempfile.mkdtemp(prefix="pyqt5dl_")
            all_extracted = True
            for wheelname, want_ver, is_sip in packages:
                entries = _load_simple_entries(mirror, pkg_names[wheelname])
                chosen = _best_wheel(entries, name_prefix=wheelname, want_version=want_ver)
                if not chosen:
                    _log("    未找到符合当前 Python 版本的 {0} wheel".format(wheelname))
                    all_extracted = False
                    break
                _log("    下载 {0}...".format(chosen["filename"]))
                whl = os.path.join(tmp, chosen["filename"])
                _download(chosen["url"], whl, "%s-%s" % (wheelname, chosen["version"]))
                # wheel 即 zip，解压到 runtime（多个 wheel 合并进同一目录）
                with zipfile.ZipFile(whl) as zf:
                    for name in zf.namelist():
                        zf.extract(name, rt)
            if all_extracted:
                ok = True
                break
        except Exception as e:
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
        pd = _jqpath_plugins(rt)
        if pd:
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = pd
    if ok:
        _setup_webengine_env(rt)
    if ok and not is_ready(rt):
        _log("PyQt5 已解压但无法导入，尝试继续...")
    return ok and is_ready(rt)


def _alloc_console():
    """Windows 下为无控制台的 windowed 进程调出一个控制台窗口显示下载进度"""
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.AllocConsole()
        sys.stdout = os.fdopen(os.dup(ctypes.windll.kernel32.GetStdHandle(-11)), "w", encoding="utf-8")
        sys.stderr = sys.stdout
    except Exception:
        pass


def free_console():
    """下载完成后释放控制台，不留黑窗"""
    try:
        import ctypes
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


if __name__ == "__main__":
    # 自检：打印当前 Python 版本下解析出的 wheel 下载地址（不实际下载）
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