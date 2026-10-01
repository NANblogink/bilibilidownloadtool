"""纯 Python 的 QR 码生成器（不依赖 qrcode / Pillow）。

为什么需要它：Android 打包不了 `qrcode` 与 `PIL`（Pillow 在 p4a 上需要额外配方，体积也大），
而扫码登录是核心功能，必须有二维码，所以这里自带一个完整实现。

能力：
  * Byte 模式 + 纠错等级 M，版本 1-10
  * 支持**多分块交织**（版本 6 起会分成多个 RS 块，且版本 8 起各块长度可能不同）
  * 版本 7+ 的 18 位版本信息（BCH）
  * 自己写 PNG（灰度图，不用 Pillow）

验证：与参考库 qrcode 在全部 8 个掩码下**逐格一致**（差异 0 格），
评分函数也与其 lost_point 完全相等，并且用 OpenCV 真实解码验证可扫。

历史坑（别重踩）：
  1. 版本 8 起各块数据长度不同（[38,38,39,39]），按“每块等长”写会生成扫不出来的码
  2. 版本 7+ 必须写版本信息，且位序是行优先（i//3, i%3）
  3. 格式信息的两个副本位序不同，写反会导致扫不出来
  4. 评分规则二（2x2 同色方块）漏写会选错掩码
"""
import io
import struct
import zlib

# ---------------------------------------------------------------- GF(256)
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n):
    g = [1]
    for i in range(n):
        g2 = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            g2[j] ^= _mul(c, 1)
            g2[j + 1] ^= _mul(c, _EXP[i])
        g = g2
    return g


def _rs_encode(data, n):
    gen = _rs_generator(n)
    res = list(data) + [0] * n
    for i in range(len(data)):
        coef = res[i]
        if coef == 0:
            continue
        for j, g in enumerate(gen):
            res[i + j] ^= _mul(g, coef)
    return res[len(data):]


# ------------------------------------------------- 版本参数表（纠错等级 M）
# 版本: (各块数据码字数, 每块纠错码字数, 对齐中心)
#
# 注意：v8 起各块数据长度可能不同，如 v8=[38,38,39,39]
# 早期按等长处理，导致 v8 以后生成错码流、扫不出来
# 数值取自 QR 规范，与 qrcode 库 base.rs_blocks 一致
DATA_M = {
    1:  ([16], 10, []),
    2:  ([28], 16, [6, 18]),
    3:  ([44], 26, [6, 22]),
    4:  ([32, 32], 18, [6, 26]),
    5:  ([43, 43], 24, [6, 30]),
    6:  ([27, 27, 27, 27], 16, [6, 34]),
    7:  ([31, 31, 31, 31], 18, [6, 22, 38]),
    8:  ([38, 38, 39, 39], 22, [6, 24, 42]),
    9:  ([36, 36, 36, 37, 37], 22, [6, 26, 46]),
    10: ([43, 43, 43, 43, 44], 26, [6, 28, 50]),
}


def _total_data_codewords(v):
    return sum(DATA_M[v][0])


def _pick_version(nbytes):
    for v in sorted(DATA_M):
        cap_bits = _total_data_codewords(v) * 8
        hdr = 4 + (8 if v <= 9 else 16)
        if hdr + nbytes * 8 <= cap_bits:
            return v
    raise ValueError("文本过长，无法用本实现编码")
# ------------------------------------------------------------- 功能图形
def _size(v):
    return v * 4 + 17


def _version_bits(v):
    """版本 7 及以上需要写入 18 位版本信息（6 位版本号 + 12 位 BCH 纠错）。

    生成多项式 G(x) = x^12 + x^11 + x^10 + x^9 + x^8 + x^5 + x^2 + 1
    十六进制为 0x1F25。做法：把版本号左移 12 位后，
    用生成多项式做模 2 除法取余数。
    """
    val = v << 12
    g = 0x1F25
    # 取 g 的最高位，用于逐位对齐
    top = g.bit_length() - 1
    rem = val
    for i in range(17, top - 1, -1):
        if (rem >> i) & 1:
            rem ^= g << (i - top)
    return val | (rem & 0xFFF)


def _place_version_info(m, v):
    """写入版本信息块（仅版本 >= 7）。

    两处副本（互为转置）：
      - 右上：6 行 x 3 列，位于 (0..5, n-11..n-9)
      - 左下：3 行 x 6 列，位于 (n-11..n-9, 0..5)

    位序经与参考实现逐位比对确定（用标准值 0x085BC 反推得到）：
      右上块是 6 行 x 3 列，按**行优先**填入：
          i -> 行 = i // 3, 列 = n-11 + (i % 3)
      左下块是右上块的转置（沿主对角线镜像）：
          i -> 行 = n-11 + (i % 3), 列 = i // 3

    注意：这里不是 (i%6, i//6)。之前按列优先写，导致版本 7 以上的
    版本信息位序错误，v8 直接扫不出来（v9/v10 因为校验位凑巧能过）。
    """
    if v < 7:
        return
    n = _size(v)
    bits = _version_bits(v)

    def bit(i):
        return (bits >> i) & 1

    for i in range(18):
        b = bit(i)
        r = i // 3
        c = i % 3
        m[r][n - 11 + c] = b        # 右上
        m[n - 11 + c][r] = b        # 左下（转置）


def _place_finder(m, v):
    n = _size(v)

    def pat(r0, c0):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = r0 + r, c0 + c
                if not (0 <= rr < n and 0 <= cc < n):
                    continue
                inside = (0 <= r <= 6 and 0 <= c <= 6)
                border = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                m[rr][cc] = 1 if (inside and (border or core)) else 0

    pat(0, 0)
    pat(0, n - 7)
    pat(n - 7, 0)

    for i in range(8):
        if i < n:
            m[7][i] = 0
            m[i][7] = 0
            m[7][n - 1 - i] = 0
            m[i][n - 8] = 0
            m[n - 8][i] = 0
            m[n - 1 - i][7] = 0


def _place_timing(m, v):
    n = _size(v)
    for i in range(8, n - 8):
        bit = 1 if i % 2 == 0 else 0
        m[6][i] = bit
        m[i][6] = bit


def _place_alignment(m, v):
    n = _size(v)
    centers = DATA_M[v][2]
    for r in centers:
        for c in centers:
            if (r < 8 and c < 8) or (r < 8 and c > n - 9) \
                    or (r > n - 9 and c < 8):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    edge = max(abs(dr), abs(dc))
                    m[r + dr][c + dc] = 1 if edge != 1 else 0


def _reserve_format(m, v):
    """先把格式信息区占位（None -> 0），避免数据写进去。"""
    n = _size(v)
    for i in range(9):
        if m[8][i] is None:
            m[8][i] = 0
        if m[i][8] is None:
            m[i][8] = 0
    for i in range(8):
        m[8][n - 1 - i] = 0
        m[n - 1 - i][8] = 0


def _place_format(m, v, mask):
    """写入格式信息（15 位，含 BCH 纠错与固定掩码 0x5412）。

    位序（与 QR 规范一致，bit0 为最低位）：
      副本 1：bit0-5  -> (8,0)..(8,5)   ；bit6 -> (8,7)；bit7 -> (8,8)
              bit8    -> (7,8)         ；bit9-14 -> (14-i, 8)
      副本 2：bit0-6  -> (n-1-i, 8)
              bit7-14 -> (8, n-15+i)

    之前把两个副本的行/列写反了，导致格式信息错位——虽然结构检查能过，
    但真实扫描器读到的纠错等级与掩码是错的，扫不出来。
    """
    n = _size(v)
    data = (0b00 << 3) | mask          # 纠错等级 M = 00
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    bits = ((data << 10) | rem) ^ 0x5412

    def bit(i):
        return (bits >> i) & 1

    # 位序由与参考实现逐位比对反推得到，非照抄文档
    # 第 8 行：(8,0)=bit14 (8,1)=bit13 (8,2)=bit12
    # (8,3)=bit11 (8,4)=bit10 (8,5)=bit9 (8,7)=bit8
    # 第 8 列：(0,8)=bit0 (1,8)=bit1 (2,8)=bit2
    # (3,8)=bit3 (4,8)=bit4 (5,8)=bit5 (7,8)=bit6
    # 副本 2 顺序相同，只是沿对角镜像
    for i in range(6):
        m[8][i] = bit(14 - i)          # (8,0)..(8,5) = bit14..bit9
    m[8][7] = bit(8)
    m[8][8] = bit(7)

    # 注意：(6,8) 属垂直时序图形，不能覆盖，故跳过
    for i in range(6):
        m[i][8] = bit(i)               # (0,8)..(5,8) = bit0..bit5
    m[7][8] = bit(6)

    # 副本 2a —— 右上，沿第 8 行自右向左：位号递增
    # 实测 n=29：(8,28)=bit0 (8,27)=bit1 (8,26)=bit2
    # (8,25)=bit3 (8,24)=bit4 (8,23)=bit5 (8,22)=bit6
    for i in range(8):
        m[8][n - 1 - i] = bit(i)

    # 副本 2b —— 左下，沿第 8 列自下向上：位号递减
    # 实测：(28,8)=bit14 (27,8)=bit13 (26,8)=bit12
    # (25,8)=bit11 (24,8)=bit10 (23,8)=bit9 (22,8)=bit8
    for i in range(7):
        m[n - 1 - i][8] = bit(14 - i)
    m[n - 8][8] = 1                    # 固定暗模块


def _mask_fn(mask):
    return [
        lambda r, c: (r + c) % 2 == 0,
        lambda r, c: r % 2 == 0,
        lambda r, c: c % 3 == 0,
        lambda r, c: (r + c) % 3 == 0,
        lambda r, c: (r // 2 + c // 3) % 2 == 0,
        lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
        lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
        lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
    ][mask]


def _penalty(m, n):
    score = 0

    # 规则 1：同色连续 >=5 计分
    for line in list(m) + [list(col) for col in zip(*m)]:
        run = 1
        for i in range(1, n):
            if line[i] == line[i - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)

    # 规则 2：2x2 同色方块，每块 +3
    for r in range(n - 1):
        for c in range(n - 1):
            v = m[r][c]
            if v == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3

    # 规则 3：类定位图形 1:1:3:1:1，每次 +40
    # 规范定义 1011101 两侧各 4 个浅色模块，等价于
    # 11 格窗口内匹配 10111010000 或 00001011101
    pat1 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    pat2 = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1]
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(n - 10):
            seg = line[i:i + 11]
            if seg == pat1 or seg == pat2:
                score += 40

    # 规则 4：暗模块比例偏离 50%，每 5% 一档 10 分
    dark = sum(sum(r) for r in m)
    total = n * n
    pct = dark * 100 / total
    score += 10 * (int(abs(pct - 50)) // 5)
    return score


def _build_codewords(text, v):
    """返回最终码字序列（数据块与纠错块按规范交织）。

    版本 8 起各块的数据长度可能不同（例如 v8 = [38,38,39,39]），
    交织时「短块先取完，长块多出的那一个码字排在最后」——
    这是规范定义的行为，写错就会生成扫不出来的码。
    """
    payload = text.encode("utf-8")
    sizes, ec_len, _ = DATA_M[v]
    total_data = sum(sizes)
    blocks = len(sizes)

    bits = []

    def push(val, length):
        for i in range(length - 1, -1, -1):
            bits.append((val >> i) & 1)

    push(0b0100, 4)
    push(len(payload), 8 if v <= 9 else 16)
    for b in payload:
        push(b, 8)

    total = total_data * 8
    if len(bits) > total:
        raise ValueError("超长")
    for _ in range(min(4, total - len(bits))):
        bits.append(0)
    while len(bits) % 8:
        bits.append(0)
    pad = [0xEC, 0x11]
    i = 0
    while len(bits) < total:
        push(pad[i % 2], 8)
        i += 1

    data = [int("".join(str(b) for b in bits[i:i + 8]), 2)
            for i in range(0, total, 8)]

    # 按各块长度切分
    dblocks = []
    pos = 0
    for sz in sizes:
        dblocks.append(data[pos:pos + sz])
        pos += sz
    eblocks = [_rs_encode(db, ec_len) for db in dblocks]

    # 交织
    out = []
    max_data = max(sizes)
    for i in range(max_data):
        for db in dblocks:
            if i < len(db):
                out.append(db[i])
    for i in range(ec_len):
        for eb in eblocks:
            out.append(eb[i])
    return out


def _build_for_mask(text, v, mask):
    """按指定掩码构造完整矩阵（供 make_matrix 与测试复用）。"""
    n = _size(v)
    codewords = _build_codewords(text, v)

    # 先标出功能图形占用的格子，数据位不能写进去
    tmp = [[None] * n for _ in range(n)]
    _place_finder(tmp, v)
    _place_timing(tmp, v)
    _place_alignment(tmp, v)
    _place_version_info(tmp, v)
    _reserve_format(tmp, v)
    reserved = [[tmp[r][c] is not None for c in range(n)] for r in range(n)]

    m = [[None] * n for _ in range(n)]
    _place_finder(m, v)
    _place_timing(m, v)
    _place_alignment(m, v)
    _place_version_info(m, v)

    fn = _mask_fn(mask)
    idx = 0
    col = n - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for c in (col, col - 1):
                if reserved[r][c]:
                    continue
                bit = 0
                if idx < len(codewords) * 8:
                    bit = (codewords[idx // 8] >> (7 - idx % 8)) & 1
                idx += 1
                if fn(r, c):
                    bit ^= 1
                m[r][c] = bit
        upward = not upward
        col -= 2

    _place_format(m, v, mask)
    for r in range(n):
        for c in range(n):
            if m[r][c] is None:
                m[r][c] = 0
    return m


def make_matrix(text):
    """把文本编码成 0/1 矩阵（1=黑）。返回 (matrix, size)。"""
    v = _pick_version(len(text.encode("utf-8")))
    n = _size(v)

    best = None
    for mask in range(8):
        m = _build_for_mask(text, v, mask)
        sc = _penalty(m, n)
        if best is None or sc < best[0]:
            best = (sc, m)

    return best[1], n


def make_png(text, path, scale=8, border=2):
    """生成 PNG（自己写 PNG，不需要 Pillow）。"""
    m, n = make_matrix(text)
    side = (n + border * 2) * scale
    rows = []
    for y in range(side):
        my = y // scale - border
        row = bytearray()
        for x in range(side):
            mx = x // scale - border
            if 0 <= mx < n and 0 <= my < n and m[my][mx]:
                row.append(0)
            else:
                row.append(255)
        rows.append(bytes(row))

    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    # 用 8 位灰度 PNG（color type 0），像素 0 黑 255 白
    # 实测可被 OpenCV / zbar / 手机相机正确解码
    # 不要再附 PLTE——灰度图带调色板会触发 libpng 警告
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", side, side, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")

    with io.open(path, "wb") as fh:
        fh.write(png)
    return path
