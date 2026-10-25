# -*- coding: utf-8 -*-
import os
import re
import sys
import time
import shutil
import zipfile
import tempfile

# ---------------------------------------------------------------- 常量

PY_VER = "3.10.11"
PY_TAG = "cp310"          # 校验wheel标签
PY_SHORT = "310"          # _pth里的XY

PY_URLS = {
    "win_amd64": "https://www.python.org/ftp/python/{v}/python-{v}-embed-amd64.zip",
    "win32":     "https://www.python.org/ftp/python/{v}/python-{v}-embed-win32.zip",
    "win_arm64": "https://www.python.org/ftp/python/{v}/python-{v}-embed-arm64.zip",
}

PY_MIRRORS = [
    "https://registry.npmmirror.com/-/binary/python/{v}/",
    "https://mirrors.huaweicloud.com/python/{v}/",
    "https://mirrors.tuna.tsinghua.edu.cn/python/{v}/",
]

MIRROR_SIMPLE = [
    "https://mirrors.cloud.tencent.com/pypi/simple",
    "https://pypi.tuna.tsinghua.edu.cn/simple",
    "https://mirrors.aliyun.com/pypi/simple",
    "https://pypi.org/simple",
]

_log = lambda *a: print(*a)


def set_logger(fn):
    global _log
    if fn:
        _log = fn


# ---------------------------------------------------------------- 架构判定

def _machine():
    try:
        import platform as _pf
        m = (_pf.machine() or "").lower()
    except Exception:
        m = ""
    if m in ("amd64", "x86_64", "x64", "em64t"):
        return "x86_64"
    if m in ("arm64", "aarch64", "armv8l"):
        return "arm64"
    if m in ("i386", "i486", "i586", "i686", "x86", "ia32", "win32"):
        return "x86"
    return m or "x86_64"


def _interp_bits():
    try:
        import struct
        return struct.calcsize("P") * 8
    except Exception:
        return 64


def target_arch_tag():
    if sys.platform != "win32":
        return None
    bits = _interp_bits()
    cpu = _machine()
    if bits == 32:
        return "win32"
    if cpu == "arm64":
        return "win_amd64"
    return "win_amd64"


# ---------------------------------------------------------------- 路径

def deploy_root(base=None):
    if base:
        return base
    try:
        here = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False)
                                              else __file__))
    except Exception:
        here = os.getcwd()
    cand = os.path.join(here, "runtime")
    if _writable(here):
        return cand
    la = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(la, "BilibiliDownloader", "runtime")


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".wtest")
        with open(t, "w") as f:
            f.write("x")
        os.remove(t)
        return True
    except Exception:
        return False


def python_dir(root=None):
    return os.path.join(root or deploy_root(), "python")


def site_packages_dir(root=None):
    return os.path.join(python_dir(root), "Lib", "site-packages")


def python_exe(root=None, windowed=False):
    d = python_dir(root)
    return os.path.join(d, "pythonw.exe" if windowed else "python.exe")


# ---------------------------------------------------------------- 下载

def _download(url, dest, title="", retries=3, timeout=120):
    """下载到 dest，校验 Content-Length；本地路径则直接复制。"""
    import urllib.request

    if not str(url).lower().startswith(("http://", "https://")):
        src = str(url)
        if not os.path.isfile(src):
            raise IOError("本地文件不存在: %s" % src)
        shutil.copyfile(src, dest)
        if os.path.getsize(dest) != os.path.getsize(src):
            raise IOError("复制后大小不一致: %s" % os.path.basename(src))
        return dest

    if str(url).lower().startswith("http://"):
        raise IOError("已拒绝不安全的下载地址: %s" % url)

    last = None
    for attempt in range(max(1, retries)):
        if attempt:
            _log("    重试 %d/%d ..." % (attempt + 1, retries))
            time.sleep(2 * attempt)
        try:
            req = urllib.request.Request(url, headers={"User-Agent":
                "Mozilla/5.0 BilibiliDownloadTool/2.1"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if not str(r.geturl()).lower().startswith("https://"):
                    raise IOError("下载被重定向到不安全地址")
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                lastpct = -1
                with open(dest, "wb") as f:
                    while True:
                        b = r.read(256 * 1024)
                        if not b:
                            break
                        f.write(b)
                        done += len(b)
                        if total:
                            pct = done * 100 // total
                            if pct != lastpct and (pct % 10 == 0 or pct == 100):
                                lastpct = pct
                                _log("    %s %d%% (%.1f/%.1f MB)"
                                     % (title, pct, done / 1048576.0,
                                        total / 1048576.0))
            if total and done < total:
                last = "下载不完整 %d/%d" % (done, total)
                _log("    " + last)
                continue
            if done == 0:
                last = "下载为空"
                continue
            return dest
        except Exception as e:
            last = str(e)
            _log("    下载失败: %s" % e)
    raise IOError(last or ("下载失败: %s" % title))


# ---------------------------------------------------------------- Python 部署

def _py_url(arch):
    u = PY_URLS.get(arch)
    if not u:
        return None
    return u.format(v=PY_VER)


def _alt_py_urls(arch):
    """国内镜像下载地址（优先）。"""
    name = "python-%s-embed-%s.zip" % (
        PY_VER, {"win_amd64": "amd64", "win32": "win32",
                 "win_arm64": "arm64"}.get(arch, "amd64"))
    out = []
    for m in PY_MIRRORS:
        if "{v}" in m:
            out.append(m.format(v=PY_VER) + name)
        else:
            out.append(m.rstrip("/") + "/" + PY_VER + "/" + name)
    return out


def python_ready(root=None):
    """部署的 Python 是否可用。"""
    exe = python_exe(root)
    if not os.path.isfile(exe):
        return False
    try:
        import subprocess
        r = subprocess.run(
            [exe, "-c", "import sys;print(sys.version_info[:2])"],
            capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def deploy_python(root=None, local_zip=None):
    root = root or deploy_root()
    arch = target_arch_tag()
    if not arch:
        _log("  当前平台暂不支持自动部署 Python（仅 Windows）。")
        return False

    if python_ready(root):
        _log("  Python 运行时已就位。")
        return True

    pyt = python_dir(root)
    os.makedirs(root, exist_ok=True)

    # ---- 取 zip ----
    tmpzip = None
    if local_zip and os.path.isfile(local_zip):
        _log("  使用内置 Python 运行时包: %s" % os.path.basename(local_zip))
        tmpzip = local_zip
    else:
        urls = _alt_py_urls(arch) + [_py_url(arch)]
        urls = [u for u in urls if u]
        _log("  下载 Python 运行时 (%.0f MB 左右)..." % 8)
        tmp = tempfile.mkdtemp(prefix="pydl_")
        tmpzip = os.path.join(tmp, "python.zip")
        ok = False
        for u in urls:
            try:
                _log("    来源: %s" % u)
                _download(u, tmpzip, "Python", retries=2)
                ok = True
                break
            except Exception as e:
                _log("    失败: %s" % e)
        if not ok:
            _log("  Python 运行时下载失败。")
            shutil.rmtree(tmp, ignore_errors=True)
            return False

    _log("  解压 Python 运行时...")
    stage = pyt + ".new"
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage, exist_ok=True)
    try:
        with zipfile.ZipFile(tmpzip) as z:
            bad = z.testzip()
            if bad:
                raise IOError("压缩包损坏: %s" % bad)
            z.extractall(stage)
    except Exception as e:
        _log("  解压失败: %s" % e)
        shutil.rmtree(stage, ignore_errors=True)
        return False
    finally:
        try:
            if not (local_zip and os.path.isfile(local_zip)):
                shutil.rmtree(os.path.dirname(tmpzip), ignore_errors=True)
        except Exception:
            pass

    # ---- 启用site-pkgs ----
    _fix_pth(stage)

    shutil.rmtree(pyt, ignore_errors=True)
    try:
        os.rename(stage, pyt)
    except Exception:
        shutil.move(stage, pyt)

    os.makedirs(site_packages_dir(root), exist_ok=True)
    if not python_ready(root):
        _log("  Python 运行时部署后无法运行。")
        return False
    _log("  Python 运行时已部署: %s" % pyt)
    return True


def _fix_pth(pydir):
    try:
        cands = [f for f in os.listdir(pydir) if f.endswith("._pth")]
    except Exception:
        return
    for fn in cands:
        p = os.path.join(pydir, fn)
        try:
            lines = open(p, encoding="utf-8").read().splitlines()
        except Exception:
            continue
        out = []
        has_site = False
        has_sp = False
        for ln in lines:
            s = ln.strip()
            if s in ("#import site", "# import site", "import site"):
                if not has_site:
                    out.append("import site")
                    has_site = True
                continue
            if "site-packages" in s:
                has_sp = True
            out.append(ln)
        if not has_site:
            out.append("import site")
        if not has_sp:
            out.append("Lib\\site-packages")
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n".join(out) + "\n")
        except Exception:
            pass


# ---------------------------------------------------------------- wheel 安装

def _split_wheel(fn):
    base = fn[:-4] if fn.lower().endswith(".whl") else fn
    parts = base.split("-")
    if len(parts) < 5:
        raise ValueError("bad wheel name: %s" % fn)
    return {
        "name": parts[0],
        "version": parts[1],
        "pyver": parts[-3],
        "abi": parts[-2],
        "platform": parts[-1],
    }


def _arch_ok(platform_field):
    """wheel 平台标签是否适用于目标架构。"""
    pf = (platform_field or "").lower()
    if pf == "any":
        return True
    tgt = target_arch_tag()
    if pf == tgt:
        return True
    return pf == tgt


def _pyver_ok(pyver, abi):
    """解释器/ABI 是否可用于目标 CPython。"""
    pv = (pyver or "").lower()
    ab = (abi or "").lower()
    if pv in ("py3", "py2.py3", "any"):
        return True
    if ab == "abi3":
        m = re.match(r"^cp3(\d+)$", pv)
        if not m:
            return False
        return int(m.group(1)) <= int(PY_SHORT[1:])
    return pv == PY_TAG


def _wheel_score(fn, want_name=None, want_ver=None):
    try:
        p = _split_wheel(fn)
    except Exception:
        return -1
    if want_name and p["name"].lower() != want_name.lower():
        return -1
    if not _arch_ok(p["platform"]):
        return -1
    if not _pyver_ok(p["pyver"], p["abi"]):
        return -1
    s = 0
    if p["pyver"].lower() == PY_TAG:
        s += 50
    if p["abi"] == "abi3":
        s += 10
    if p["abi"] == "none":
        s += 5
    if want_ver:
        if p["version"] == want_ver:
            s += 100
        elif p["version"].startswith(want_ver + "."):
            s += 90
    try:
        s += sum(int(x) for x in p["version"].split(".")) * 0.01
    except Exception:
        pass
    return s


REQUIRED_PACKAGES = [
    ("PyQt5", "5.15.11"),
    ("PyQt5_Qt5", "5.15.2"),
    ("PyQt5_sip", None),
    ("PyQtWebEngine", None),
    ("PyQtWebEngine_Qt5", None),
]

PKG_INDEX_NAMES = {
    "PyQt5": "pyqt5",
    "PyQt5_Qt5": "pyqt5-qt5",
    "PyQt5_sip": "pyqt5-sip",
    "PyQtWebEngine": "pyqtwebengine",
    "PyQtWebEngine_Qt5": "pyqtwebengine-qt5",
}


def local_wheel_dirs(base=None):
    """查找本地 wheel 目录。"""
    dirs = []
    roots = []
    try:
        if getattr(sys, "frozen", False):
            roots.append(os.path.dirname(os.path.abspath(sys.executable)))
    except Exception:
        pass
    try:
        roots.append(os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        pass
    if base:
        roots.append(base)
    try:
        roots.append(deploy_root(base))
    except Exception:
        pass
    seen = set()
    for r in roots:
        if not r:
            continue
        for sub in ("wheels", os.path.join("_internal", "wheels")):
            d = os.path.join(r, sub)
            k = os.path.normcase(os.path.abspath(d))
            if k in seen:
                continue
            seen.add(k)
            if os.path.isdir(d):
                dirs.append(d)
    return dirs


def _scan_local(directory, want_name):
    out = []
    try:
        names = os.listdir(directory)
    except Exception:
        return out
    for n in names:
        if not n.lower().endswith(".whl"):
            continue
        if _wheel_score(n, want_name) >= 0:
            out.append(n)
    return out


def _sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _fetch_index(prefix):
    """从镜像取 simple 索引里的 wheel 列表。"""
    import urllib.request
    from urllib.parse import urljoin
    pkg = PKG_INDEX_NAMES.get(prefix)
    if not pkg:
        return []
    for mirror in MIRROR_SIMPLE:
        page = "%s/%s/" % (mirror.rstrip("/"), pkg)
        try:
            req = urllib.request.Request(page, headers={"User-Agent":
                "Mozilla/5.0 BilibiliDownloadTool/2.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read().decode("utf-8", "ignore")
        except Exception:
            continue
        out = []
        for m in re.finditer(r'href="([^"]+\.whl[^"]*)"', data):
            raw = m.group(1)
            href, _, fragment = raw.partition("#")
            fn = href.split("/")[-1]
            sha = ""
            if fragment.strip().lower().startswith("sha256="):
                sha = fragment.split("=", 1)[1].strip().lower()
            out.append((fn, urljoin(page, href), sha))
        if out:
            return out
    return []


def _platform_plugin_names():
    """当前平台 Qt platform 插件的库文件名候选。"""
    if sys.platform == "win32":
        return ("qwindows.dll",)
    if sys.platform == "darwin":
        return ("libqcocoa.dylib", "libqcocoa.so")
    return ("libqxcb.so", "libqwayland.so", "libqeglfs.so")


def _platform_plugins_ready(sp):
    names = {n.lower() for n in _platform_plugin_names()}
    try:
        for root, _dirs, _files in os.walk(sp):
            platforms = os.path.join(root, "platforms")
            if not os.path.isdir(platforms):
                continue
            try:
                present = {f.lower() for f in os.listdir(platforms)}
            except Exception:
                continue
            if names & present:
                return True
    except Exception:
        return False
    return False


def site_packages_ready(root=None):
    """部署的 Python 是否已装好 PyQt5。"""
    exe = python_exe(root)
    if not os.path.isfile(exe):
        return False
    try:
        import subprocess
        r = subprocess.run(
            [exe, "-c",
             "import PyQt5.QtCore,PyQt5.QtGui,PyQt5.QtWidgets;print('ok')"],
            capture_output=True, text=True, timeout=60)
        if not (r.returncode == 0 and "ok" in (r.stdout or "")):
            return False
    except Exception:
        return False
    # 平台插件缺失同样无法启动界面，不能算就绪
    return _platform_plugins_ready(site_packages_dir(root))


def _install_wheel_zip(whl_path, sp):
    """把 wheel解压到 site-packages，并校验完整性。"""
    os.makedirs(sp, exist_ok=True)
    with zipfile.ZipFile(whl_path) as z:
        bad = z.testzip()
        if bad:
            raise IOError("wheel 损坏: %s" % bad)
        for info in z.infolist():
            name = info.filename
            target = os.path.normpath(os.path.join(sp, name))
            base = os.path.normcase(os.path.normpath(sp)) + os.sep
            if not os.path.normcase(target).startswith(base):
                if os.path.normcase(target) != os.path.normcase(os.path.normpath(sp)):
                    continue
            z.extract(info, sp)
            if not name.endswith("/") and info.file_size > 0:
                if not os.path.exists(target) or \
                        os.path.getsize(target) != info.file_size:
                    raise IOError("解压后不完整: %s" % name)
    return True


def install_site_packages(root=None, local_dir=None):
    root = root or deploy_root()
    if not python_ready(root):
        _log("  Python 运行时未就位，无法安装依赖。")
        return False
    if site_packages_ready(root):
        _log("  PyQt5 已就位。")
        return True

    sp = site_packages_dir(root)
    os.makedirs(sp, exist_ok=True)

    dirs = ([local_dir] if local_dir else []) + local_wheel_dirs(root)
    _log("  本地组件目录: %s" % ("; ".join(dirs) if dirs else "无"))

    tmp = tempfile.mkdtemp(prefix="wheelinst_")
    try:
        # ---- 先尽量用本地 ----
        need = list(REQUIRED_PACKAGES)
        if dirs:
            still = []
            for prefix, ver in need:
                picked = None
                best = -1
                for d in dirs:
                    for fn in _scan_local(d, prefix):
                        sc = _wheel_score(fn, prefix, ver)
                        if sc > best:
                            best = sc
                            for dd in dirs:
                                p = os.path.join(dd, fn)
                                if os.path.isfile(p):
                                    picked = p
                                    break
                if picked:
                    try:
                        _log("    安装内置 %s" % os.path.basename(picked))
                        _install_wheel_zip(picked, sp)
                    except Exception as e:
                        _log("    内置包不可用(%s)，改为联网获取" % e)
                        still.append((prefix, ver))
                else:
                    still.append((prefix, ver))
            need = still

        # ---- 剩余的走网络 ----
        if need:
            _log("  从镜像获取剩余组件: %s"
                 % ", ".join(p for p, _ in need))
            for prefix, ver in need:
                entries = _fetch_index(prefix)
                if not entries:
                    _log("    %s: 无法获取索引" % prefix)
                    return False
                best = None
                bestsc = -1
                for fn, url, sha in entries:
                    sc = _wheel_score(fn, prefix, ver)
                    if sc > bestsc:
                        bestsc = sc
                        best = (fn, url, sha)
                if not best:
                    _log("    %s: 没有匹配当前架构/版本的 wheel" % prefix)
                    return False
                fn, url, sha = best
                dst = os.path.join(tmp, fn)
                _log("    下载 %s" % fn)
                try:
                    _download(url, dst, prefix, retries=2)
                except Exception as e:
                    _log("    下载失败: %s" % e)
                    return False
                if sha and _sha256_file(dst) != sha.lower():
                    _log("    校验失败，已中止: %s" % fn)
                    return False
                try:
                    _install_wheel_zip(dst, sp)
                except Exception as e:
                    _log("    安装失败: %s" % e)
                    return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if not site_packages_ready(root):
        _log("  PyQt5 安装后仍无法导入。")
        return False
    _log("  PyQt5 安装完成。")
    return True


def ensure_environment(root=None, local_py_zip=None, local_wheel_dir=None):
    """完整流程：部署 Python + 安装 PyQt5。返回 True/False。"""
    root = root or deploy_root()
    _log("运行环境目录: %s" % root)

    if python_ready(root) and site_packages_ready(root):
        _log("运行环境已就绪，跳过部署。")
        return True

    if not python_ready(root):
        _log("[1/2] 部署 Python 运行时")
        if not deploy_python(root, local_zip=local_py_zip):
            return False
    else:
        _log("[1/2] Python 运行时已就位")

    _log("[2/2] 安装界面组件 (PyQt5)")
    if not install_site_packages(root, local_dir=local_wheel_dir):
        return False
    return True
