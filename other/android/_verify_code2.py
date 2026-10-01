"""确认新功能真的进了 APK —— 用字符串扫描法（不依赖 host 的 Python 版本）。

背景：APK 里的 main.pyc 是 Python 3.11 编译的（magic 0x0e2b），
本机是 3.10，marshal.loads 会报 "bad marshal data"。
所以这里不解码，而是在 pyc 的原始字节里查找：
  - co_names / co_consts 里的标识符与中文字符串
  - 都是明文 UTF-8 存于 pyc 中
"""
import io
import os
import tarfile
import zipfile

AND = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8\other\android"
APK = os.path.join(AND, "bilidownload-2.2.0-arm64-v8a_armeabi-v7a-debug.apk")
OUT = os.path.join(AND, "_apk_code.txt")
L = []


def w(s=""):
    L.append(str(s))


z = zipfile.ZipFile(APK)
tar_name = next(n for n in z.namelist() if n.endswith("private.tar"))
tf = tarfile.open(fileobj=io.BytesIO(z.read(tar_name)))
members = tf.getnames()

w("=== APK 内应用代码（assets/private.tar）===")
w("  共 %d 项" % len(members))
pycs = sorted(m for m in members if m.endswith(".pyc"))
for m in pycs:
    w("    %s" % m)

raw = tf.extractfile("main.pyc").read()
w()
w("  main.pyc = %d 字节" % len(raw))
w("  magic = 0x%04x (0x0e2b = Python 3.11)" % int.from_bytes(raw[:2], "little"))

# 标识符明文在pyc
CHECKS = {
    "EpisodePicker 类（集数选择弹窗）": "EpisodePicker",
    "EpisodeRow 类（集数行）": "EpisodeRow",
    "open_episode_picker（打开集数选择）": "open_episode_picker",
    "set_episode_selection（写回选择）": "set_episode_selection",
    "toggle_parse（解析/停止切换）": "toggle_parse",
    "on_stop_parse（停止解析）": "on_stop_parse",
    "_set_parsing_ui（按钮状态切换）": "_set_parsing_ui",
    "_apply_filter（集数搜索）": "_apply_filter",
    "_set_all（全选）": "_set_all",
    "_invert（反选）": "_invert",
    "_confirm（确认选择）": "_confirm",
    "_on_toggle（单项勾选）": "_on_toggle",
    "selected_ep_indexes 属性": "selected_ep_indexes",
    "文案：停止解析": "\u505c\u6b62\u89e3\u6790",
    "文案：选择集数": "\u9009\u62e9\u96c6\u6570",
    "文案：全选": "\u5168\u9009",
    "文案：取消全选": "\u53d6\u6d88\u5168\u9009",
    "文案：反选": "\u53cd\u9009",
    "文案：确认选择": "\u786e\u8ba4\u9009\u62e9",
    "文案：下载全部": "\u4e0b\u8f7d\u5168\u90e8",
    "文案：已选": "\u5df2\u9009",
    "文案：共 N 集": "\u5171 ",
    "文案：搜索集数标题": "\u641c\u7d22\u96c6\u6570\u6807\u9898",
    "文案：解析（按钮）": "\u89e3\u6790",
}

w()
w("=== 新功能在 APK 代码中的存在性 ===")
fails = 0
for label, needle in CHECKS.items():
    ok = needle.encode("utf-8") in raw
    w("  %s %s" % ("PASS" if ok else "FAIL", label))
    if not ok:
        fails += 1

w()
w("=== 字体与图标也在包里 ===")
for name in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"):
    ok = name.encode("utf-8") in raw or any(name in m for m in members)
    w("  %s 字体 %s" % ("PASS" if ok else "FAIL", name))
    if not ok:
        fails += 1

w()
w("TOTAL FAILURES: %d" % fails)

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("FAILURES:", fails)
for line in L:
    if "FAIL" in line:
        print(line)
