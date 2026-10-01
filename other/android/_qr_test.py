# Verify qrgen.py produces valid QR codes.
# 1) structural checks (finder patterns, timing, size)
# 2) cross-check against the reference qrcode library
import io
import os
import sys

AND = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8\other\android"
sys.path.insert(0, AND)
OUT = os.path.join(AND, "_qr_test.txt")
L = []


def w(s=""):
    L.append(str(s))


fails = []


def check(name, cond, extra=""):
    w(("  PASS " if cond else "  FAIL ") + name
      + ((" " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


import qrgen  # noqa: E402

w("=== 1. 生成一个真实 B 站登录链接的二维码 ===")
# B 站登录二维码 URL 的实际形状
URL = ("https://passport.bilibili.com/h5-app/passport/login/scan"
       "?qrcode_key=abcd1234abcd1234abcd1234abcd1234")
w("  文本长度: %d 字符" % len(URL))

mat, n = qrgen.make_matrix(URL)
w("  矩阵尺寸: %dx%d" % (n, n))

check("尺寸符合 QR 规范 (4v+17)", (n - 17) % 4 == 0 and 21 <= n <= 57, n)

# 三个定位图形
def is_finder(m, r0, c0):
    for r in range(7):
        for c in range(7):
            border = r in (0, 6) or c in (0, 6)
            core = 2 <= r <= 4 and 2 <= c <= 4
            want = 1 if (border or core) else 0
            if m[r0 + r][c0 + c] != want:
                return False
    return True


check("左上定位图形", is_finder(mat, 0, 0))
check("右上定位图形", is_finder(mat, 0, n - 7))
check("左下定位图形", is_finder(mat, n - 7, 0))

# 时序图形
timing_ok = all(mat[6][i] == (1 if i % 2 == 0 else 0)
                for i in range(8, n - 8))
check("水平时序图形", timing_ok)
timing_ok2 = all(mat[i][6] == (1 if i % 2 == 0 else 0)
                 for i in range(8, n - 8))
check("垂直时序图形", timing_ok2)

check("固定暗模块", mat[n - 8][8] == 1)
check("矩阵无空值", all(v in (0, 1) for row in mat for v in row))

w()
w("=== 2. 与参考库逐格对比 ===")
try:
    import qrcode

    # 关键：必须用同一个掩码去比
    # 两个实现都合法时也可能选不同掩码
    # （评分相同时的先后顺序不同），
    # 那不是 bug。旧版本直接拿默认掩码比，
    # 会误报。
    v_ours = qrgen._pick_version(len(URL.encode("utf-8")))
    n_ours = qrgen._size(v_ours)

    all_match = True
    for mk in range(8):
        ref = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            border=0, mask_pattern=mk)
        ref.add_data(URL)
        ref.make(fit=True)
        ref_mat = ref.get_matrix()
        rn = len(ref_mat)

        ours = qrgen._build_for_mask(URL, v_ours, mk)
        diff = sum(1 for r in range(rn) for c in range(rn)
                   if bool(ref_mat[r][c]) != bool(ours[r][c]))
        check("掩码 %d 与参考库一致" % mk,
              diff == 0, "差异 %d 格" % diff)
        if diff:
            all_match = False

    check("尺寸与参考库一致", rn == n_ours,
          "ours=%d ref=%d" % (n_ours, rn))
    check("全部 8 个掩码逐格一致", all_match)

    # 评分函数也要与参考库一致，否则会选到不同掩码
    from qrcode import util as _qu
    score_match = True
    for mk in range(8):
        ref = qrcode.QRCode(
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            border=0, mask_pattern=mk)
        ref.add_data(URL)
        ref.make(fit=True)
        ref_score = _qu.lost_point(ref.get_matrix())
        our_score = qrgen._penalty(
            qrgen._build_for_mask(URL, v_ours, mk), n_ours)
        if ref_score != our_score:
            score_match = False
            w("    掩码 %d 评分不同: ours=%d ref=%d"
              % (mk, our_score, ref_score))
    check("掩码评分与参考库一致", score_match)
except ImportError:
    w("  未安装 qrcode，跳过对比")

# 真实解码器验证：能被扫出来才算真的对
try:
    import cv2

    import tempfile
    import numpy
    _dec_path = os.path.join(tempfile.gettempdir(), "dsh_qr_dec.png")
    qrgen.make_png(URL, _dec_path, scale=8, border=4)
    _det = cv2.QRCodeDetector()
    # cv2.imread 读不了中文路径，改用 imdecode 读字节
    with open(_dec_path, "rb") as _fh:
        _buf = numpy.frombuffer(_fh.read(), dtype=numpy.uint8)
    _data, _, _ = _det.detectAndDecode(
        cv2.imdecode(_buf, cv2.IMREAD_COLOR))
    check("真实解码器能读出原文", _data == URL,
          "解码结果=%r" % (_data[:40] if _data else ""))
except ImportError:
    w("  未安装 opencv，跳过解码验证")

w("=== 3. 多个长度都要能编码 ===")
for s in ["a", "BV1xx411c7mD",
          "https://b23.tv/abcdefg",
          URL,
          URL + "&extra=padding_to_make_it_longer_0123456789"]:
    try:
        m2, n2 = qrgen.make_matrix(s)
        check("编码 %d 字符 -> %dx%d" % (len(s), n2, n2), True)
    except Exception as exc:
        check("编码 %d 字符" % len(s), False, exc)

w()
w("=== 4. 生成 PNG（不依赖 Pillow）===")
out = os.path.join(AND, "_qr_test.png")
try:
    qrgen.make_png(URL, out, scale=8, border=2)
    sz = os.path.getsize(out)
    check("PNG 已生成", sz > 200, "%d B" % sz)
    with io.open(out, "rb") as fh:
        head = fh.read(8)
    check("PNG 文件头正确", head == b"\x89PNG\r\n\x1a\n", head)
except Exception as exc:
    check("PNG 生成", False, exc)

w()
w("TOTAL FAILURES: %d" % len(fails))
for f in fails:
    w("  - " + f)

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("FAILURES:", len(fails))
for line in L:
    print(line)
