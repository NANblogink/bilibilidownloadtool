"""验证新构建的 APK 是否真的包含了所有必需内容。"""
import io
import os
import re
import tarfile
import zipfile

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
AND = os.path.join(ROOT, "other", "android")
APK = os.path.join(AND, "bilidownload-2.2.0-arm64-v8a_armeabi-v7a-debug.apk")
OUT = os.path.join(AND, "_apk_verify.txt")
L = []


def w(s=""):
    L.append(str(s))


fails = []


def check(name, cond, extra=""):
    w(("  PASS " if cond else "  FAIL ") + name + ((" " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


z = zipfile.ZipFile(APK)
names = z.namelist()
w(f"APK: {os.path.basename(APK)}  ({os.path.getsize(APK)/1024/1024:.1f} MB, {len(names)} entries)")
w()

w("=== 1. 架构 ===")
for abi in ("arm64-v8a", "armeabi-v7a"):
    libs = [n for n in names if n.startswith(f"lib/{abi}/")]
    check(f"{abi} 原生库", len(libs) > 0, f"{len(libs)} 个 .so")
    for key in ("libpython3", "libmain", "libSDL2.so", "libssl", "libcrypto"):
        has = any(key in n for n in libs)
        check(f"  {abi} 含 {key}", has)

w()
w("=== 2. assets/private.tar 里的应用代码 ===")
data = z.read("assets/private.tar")
t = tarfile.open(fileobj=io.BytesIO(data))
inner = t.getnames()
w(f"  private.tar 条目数: {len(inner)}")

# 关键文件
required = {
    "main.pyc": "Android 入口（编译后的 main_kivy.py）",
    "qt_compat.pyc": "Qt 兼容层（缺了无法导入桌面引擎）",
    "NotoSansSC-Regular.ttf": "中文字体（缺了乱码）",
    "NotoSansSC-Bold.ttf": "中文粗体",
    "logo_ui.png": "界面图标",
    "core/downloader.pyc": "下载引擎",
    "core/utils.pyc": "工具函数",
    "core/task_manager.pyc": "任务管理",
    "core/config.pyc": "配置",
    "core/download_history.pyc": "下载历史",
    "core/tool_manager.pyc": "工具管理",
    "core/infra/platform_utils.pyc": "平台适配",
    "core/infra/logger_config.pyc": "日志",
    "parsers/bilibili_parser.pyc": "B站解析器",
}
for rel, why in required.items():
    ok = rel in inner
    check(f"{rel}", ok, why if not ok else "")

w()
w("=== 3. 字体文件真的写进去了吗（大小校验）===")
for fname, expect in (("NotoSansSC-Regular.ttf", 788 * 1024),
                      ("NotoSansSC-Bold.ttf", 704 * 1024)):
    try:
        fh = t.extractfile(fname)
        size = len(fh.read())
        check(f"{fname} 大小合理", abs(size - expect) < 80 * 1024,
              f"{size/1024:.0f} KB (期望约 {expect/1024:.0f} KB)")
    except Exception as exc:
        check(f"{fname} 可读取", False, exc)

w()
w("=== 4. 没有 PyQt5（Android 上不可能有）===")
pyqt = [n for n in names if "PyQt5" in n] + [n for n in inner if "PyQt5" in n]
check("APK 内无 PyQt5", not pyqt, pyqt[:5])

w()
w("=== 5. 启动图标（必须是用户自己的 logo）===")
icons = sorted(n for n in names
               if "ic_launcher" in n or re.search(r"mipmap.*\.png$", n))
w(f"  找到 {len(icons)} 个图标资源:")
for n in icons[:12]:
    w("    %-46s %8d B" % (n, len(z.read(n))))
check("存在启动图标", len(icons) > 0)

# APK里同时有p4a自带图标
# 只有manifest引用的才算
# badging会写出icon=...
_mm = [n for n in icons if n.endswith("mipmap/icon.png")]
check("存在 mipmap/icon.png（用户 logo）", bool(_mm))
if _mm:
    _size = len(z.read(_mm[0]))
    check("mipmap/icon.png 是高清 logo（>100 KB，SDL 图标仅 1-7 KB）",
          _size > 100 * 1024, "%d B" % _size)

_badge = os.path.join(AND, "_aapt_badging.txt")
if os.path.isfile(_badge):
    _btxt = io.open(_badge, encoding="utf-8").read()
    _app = [ln for ln in _btxt.split("\n") if ln.startswith("application:")]
    check("manifest 的 application icon 指向 mipmap/icon",
          any("mipmap/icon" in ln for ln in _app),
          _app[0] if _app else "无 application 行")

w()
w("=== 6. AndroidManifest 关键项 ===")


def _axml_strings(data):
    """正确解析二进制 AXML 的字符串池。

    不能用 decode 直接搜：AXML 的字符串是「长度前缀 + UTF-16」，
    按纯文本 decode 会把相邻字符串粘在一起，导致漏匹配。

    注意 RES_STRING_POOL 头是 **5 个 uint32**：
        stringCount, styleCount, flags, stringsStart, stylesStart
    漏掉 stylesStart 会让偏移表与字符串数据整体错位。
    """
    import struct
    out = []
    off = 8
    while off + 8 <= len(data):
        ctype, hsize, csize = struct.unpack_from("<HHI", data, off)
        if csize == 0:
            break
        if ctype == 0x0001:            # RES_STRING_POOL_TYPE
            count, _style, flags, sstart, _st = struct.unpack_from(
                "<IIIII", data, off + 8)
            is_utf8 = bool(flags & (1 << 8))
            base = off + hsize
            offs = [struct.unpack_from("<I", data, base + i * 4)[0]
                    for i in range(count)]
            pool = off + sstart
            for o in offs:
                p = pool + o
                if is_utf8:
                    def uleb(pos):
                        val = shift = 0
                        while True:
                            b = data[pos]
                            val |= (b & 0x7F) << shift
                            pos += 1
                            if not (b & 0x80):
                                break
                            shift += 7
                        return val, pos
                    _, p = uleb(p)
                    blen, p = uleb(p)
                    out.append(data[p:p + blen].decode("utf-8",
                                                       errors="replace"))
                else:
                    slen = struct.unpack_from("<H", data, p)[0]
                    out.append(data[p + 2:p + 2 + slen * 2]
                               .decode("utf-16-le", errors="replace"))
            break
        off += csize
    return out


raw = z.read("AndroidManifest.xml")
strs = _axml_strings(raw)
blob = "\n".join(strs)
check("manifest 可解析出字符串池", len(strs) > 10, f"{len(strs)} 项")

# 竖屏锁定。
#
# screenOrientation存整数
# 字符串池查不到portrait
# ActivityInfo定义为
# 0横屏 1竖屏 2未指定
# 3behind 4sensor 5nosensor
# 6横屏传感 7竖屏传感 8反向横
# 9反向竖 10全传感 11用户
# 判据是属性存在且值为1
def _axml_orientation(data):
    import struct
    off = 8
    pool = []
    while off + 8 <= len(data):
        ctype, hsize, csize = struct.unpack_from("<HHI", data, off)
        if csize == 0:
            break
        if ctype == 0x0001:
            count, _sc, flags, sstart, _st = struct.unpack_from(
                "<IIIII", data, off + 8)
            is_utf8 = bool(flags & (1 << 8))
            base = off + hsize
            offs = [struct.unpack_from("<I", data, base + i * 4)[0]
                    for i in range(count)]
            p0 = off + sstart
            for o in offs:
                p = p0 + o
                if is_utf8:
                    def uleb(pos):
                        v = sh = 0
                        while True:
                            b = data[pos]
                            v |= (b & 0x7F) << sh
                            pos += 1
                            if not (b & 0x80):
                                break
                            sh += 7
                        return v, pos
                    _, p = uleb(p)
                    blen, p = uleb(p)
                    pool.append(data[p:p + blen].decode("utf-8",
                                                        errors="replace"))
                else:
                    slen = struct.unpack_from("<H", data, p)[0]
                    pool.append(data[p + 2:p + 2 + slen * 2]
                                .decode("utf-16-le", errors="replace"))
        elif ctype == 0x0102:            # START_ELEMENT
            # 属性从+0x24起每项20字节
            nattr = struct.unpack_from("<H", data, off + 0x1C)[0]
            for i in range(nattr):
                ao = off + 0x24 + i * 20
                ns, name_i, raw_i, _ts, data_v = struct.unpack_from(
                    "<iiiII", data, ao)
                if 0 <= name_i < len(pool) and pool[name_i] == "screenOrientation":
                    return data_v
        off += csize
    return None


orient_val = _axml_orientation(raw)
ORIENT_NAMES = {0: "landscape", 1: "portrait", 2: "unspecified",
                3: "behind", 4: "sensor", 5: "nosensor",
                6: "sensorLandscape", 7: "sensorPortrait",
                8: "reverseLandscape", 9: "reversePortrait",
                10: "fullSensor", 11: "user", 12: "fullUser",
                13: "locked"}
check("manifest 含 screenOrientation 属性", "screenOrientation" in strs)
check("screenOrientation = portrait(1)", orient_val == 1,
      "实际=%s(%s)" % (orient_val, ORIENT_NAMES.get(orient_val, "?")))
check("manifest 不含 landscape（未误设横向）",
      orient_val != 0 and "landscape" not in strs)
check("包名正确", any("cn.bilidown" in s for s in strs))

w()
w("=== 7. 权限 ===")
for perm in ("INTERNET", "ACCESS_NETWORK_STATE", "WRITE_EXTERNAL_STORAGE"):
    check(f"权限 {perm}", perm in blob)

w()
w(f"TOTAL FAILURES: {len(fails)}")
if fails:
    for f in fails:
        w("  - " + f)

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("FAILURES:", len(fails))
