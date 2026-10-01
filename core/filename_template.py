# -*- coding: utf-8 -*-
"""文件名模板引擎。

提供统一的文件名模板渲染，替代原先散落在下载器里的多分支硬编码逻辑。

模板变量（不区分大小写，用 {变量} 引用）：
    {title}      视频标题（合集/分P标题，已按 raw_title 规则清洗）
    {ep}         集数序号，不带前导零（1、2、10）
    {ep2}        集数序号，两位补零（01、02、10）
    {ep3}        集数序号，三位补零（001、002、010）
    {ep4}        集数序号，四位补零
    {seq}        批次序号，按「文件名序号位数」设置补零（默认两位）
    {author}     UP主名
    {season}     合集 / 番剧 / 课程标题
    {bvid}       视频 BV 号（课程无 BV 号时为空）
    {cid}        视频 cid
    {date}       当前日期 YYYY-MM-DD
    {time}       当前时间 HH.MM.SS（用点号，避免冒号在文件名非法）
    {type}       媒体类型：普通视频 / 番剧 / 课程 / 互动视频

空变量处理：
    {a}-{b} 这种写法在某一段为空时会留下多余分隔符，因此渲染后统一
    清理连续分隔符、首尾分隔符。可用 {a?}{b} 形式显式控制。

非法字符：
    渲染结果中的 Windows 非法字符会被替换为下划线。
"""
import os
import re
import time as _time

# 模板中最多允许的长度，防止极端模板产生超长文件名
MAX_NAME_LEN = 200

# 未渲染成功时的兜底模板
FALLBACK_TEMPLATE = "{title}"

# 变量说明，供设置界面展示
TEMPLATE_VARS = [
    ("{title}", "视频标题"),
    ("{ep}", "集数（1、2、10）"),
    ("{ep2}", "集数两位补零（01）"),
    ("{ep3}", "集数三位补零（001）"),
    ("{seq}", "批次序号（按序号位数设置）"),
    ("{author}", "UP主名"),
    ("{season}", "合集/番剧/课程标题"),
    ("{bvid}", "BV号"),
    ("{cid}", "cid"),
    ("{date}", "日期 2026-10-01"),
    ("{time}", "时间 19.04.52"),
    ("{type}", "类型（普通视频/番剧/课程）"),
]

# 预设模板，设置界面下拉可直接选
PRESET_TEMPLATES = [
    ("默认（集数前缀）", "{title}"),
    ("序号 + 标题", "{seq} {title}"),
    ("标题 + 序号", "{title}_{seq}"),
    ("UP主 + 标题", "[{author}] {title}"),
    ("合集 + 集数 + 标题", "{season}_{ep2}_{title}"),
    ("集数 + UP主 + 标题", "{ep2}_{author}_{title}"),
    ("日期 + 标题", "{date}_{title}"),
    ("原样（不加工）", "{title}"),
]

_ILLEGAL = '\\/:*?"<>|'


def illegal_filename_chars():
    """返回文件名非法字符列表（保留原接口，供既有代码调用）"""
    return list(_ILLEGAL)


def sanitize_filename(name, replacement="_"):
    """替换 Windows 文件名非法字符，并去掉首尾空白与结尾的点。"""
    if name is None:
        return ""
    s = str(name)
    for c in _ILLEGAL:
        s = s.replace(c, replacement)
    # 控制字符
    s = "".join(ch for ch in s if ord(ch) >= 32)
    s = s.strip()
    # Windows 不允许文件名以点或空格结尾
    s = s.rstrip(" .")
    return s


def _pad(number, digits):
    """把数字补零到指定宽度；digits<=0 时不补零。"""
    try:
        n = int(number)
    except (TypeError, ValueError):
        return ""
    if n < 0:
        n = 0
    try:
        d = int(digits)
    except (TypeError, ValueError):
        d = 0
    if d <= 0:
        return str(n)
    d = max(1, min(d, 6))
    return f"{n:0{d}d}"


def build_context(title="", ep=None, seq=None, seq_digits=2, author="",
                  season="", bvid="", cid="", media_type=""):
    """构造模板变量字典。

    title/author/season 等会做基础清洗；数值类变量同时提供补零版本。
    """
    _now = _time.localtime()
    type_map = {
        "video": "普通视频",
        "bangumi": "番剧",
        "cheese": "课程",
        "interact": "互动视频",
    }
    ep_digits = 2
    if seq_digits is not None:
        try:
            ep_digits = int(seq_digits)
        except (TypeError, ValueError):
            ep_digits = 2
    ctx = {
        "title": str(title or "").strip(),
        "ep": _pad(ep, 0) if ep is not None else "",
        "ep2": _pad(ep, 2) if ep is not None else "",
        "ep3": _pad(ep, 3) if ep is not None else "",
        "ep4": _pad(ep, 4) if ep is not None else "",
        "seq": _pad(seq, ep_digits) if seq is not None else "",
        "author": str(author or "").strip(),
        "season": str(season or "").strip(),
        "bvid": str(bvid or "").strip(),
        "cid": str(cid or "").strip(),
        "date": _time.strftime("%Y-%m-%d", _now),
        "time": _time.strftime("%H.%M.%S", _now),
        "type": type_map.get(str(media_type or "").strip().lower(), ""),
    }
    return ctx


def _clean_rendered(text):
    """清理渲染结果里因空变量留下的多余分隔符与空括号。"""
    s = text
    # 去掉空括号（含中英文括号与方括号），避免出现 [] () 【】
    for _ in range(3):
        new = re.sub(r"[\[\(【]\s*[\]\)】]", "", s)
        if new == s:
            break
        s = new
    # 折叠连续空格
    s = re.sub(r"[ \t]{2,}", " ", s)
    # 折叠连续的下划线/连字符分隔
    s = re.sub(r"[_\-]{2,}", "_", s)
    # 去掉分隔符两侧多余空格
    s = re.sub(r"\s*([_\-])\s*", r"\1", s)
    # 去掉首尾的分隔符与空白
    s = s.strip(" _-.")
    return s


def render_template(template, context, strict=False):
    """渲染模板。

    template: 形如 "{seq} {title}" 的字符串
    context:  build_context 的返回值，或普通 dict
    strict:   True 时未定义变量会抛错（用于设置界面的即时校验）；
              默认 False，未定义变量渲染为空串，保证下载流程不中断。
    返回：清洗并替换非法字符后的文件名（不含扩展名）。
    """
    if not template or not str(template).strip():
        template = FALLBACK_TEMPLATE
    template = str(template)

    class _SafeDict(dict):
        def __missing__(self, key):
            if strict:
                raise KeyError(key)
            return ""

    table = _SafeDict()
    for k, v in (context or {}).items():
        table[str(k)] = "" if v is None else str(v)

    try:
        # 用 format_map 支持 {var}，并容忍未知变量
        rendered = template.format_map(table)
    except (KeyError, IndexError, ValueError):
        if strict:
            raise
        # 模板语法有误时退化为逐个替换，尽量保留可用部分
        rendered = template
        for k, v in table.items():
            rendered = rendered.replace("{" + k + "}", v)
        rendered = re.sub(r"\{[^{}]*\}", "", rendered)

    rendered = _clean_rendered(rendered)
    rendered = sanitize_filename(rendered)
    if len(rendered) > MAX_NAME_LEN:
        rendered = rendered[:MAX_NAME_LEN].rstrip(" _-.")
    if not rendered:
        # 全部变量为空时给一个可用兜底
        rendered = sanitize_filename(str((context or {}).get("title") or "")) or "未命名"
    return rendered


def validate_template(template):
    """校验模板，返回 (是否合法, 错误信息)。

    用于设置界面在用户保存时给出即时反馈。
    """
    if not template or not str(template).strip():
        return True, ""  # 空模板按默认处理
    t = str(template)
    known = {k.strip("{}") for k, _ in TEMPLATE_VARS}
    # 检查花括号是否配对
    depth = 0
    for ch in t:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth < 0:
            return False, "花括号不匹配：出现了多余的 }"
    if depth != 0:
        return False, "花括号不匹配：缺少 }"
    # 检查未知变量
    used = re.findall(r"\{([^{}]*)\}", t)
    unknown = []
    for u in used:
        name = u.strip()
        # 允许 {var:格式} 与 {var!r} 之类，取主名
        name = re.split(r"[!:.]", name)[0].strip()
        if name and name not in known:
            unknown.append(u)
    if unknown:
        return False, "未知变量：" + "、".join("{%s}" % u for u in unknown)
    return True, ""


def preview(template, context=None):
    """生成预览文件名，供设置界面调用。"""
    if context is None:
        context = build_context(
            title="示例视频标题", ep=1, seq=1, seq_digits=2,
            author="示例UP主", season="示例合集", bvid="BV1xx411c7mD",
            cid="12345678", media_type="video",
        )
    try:
        name = render_template(template, context)
        return name + ".mp4"
    except Exception as e:
        return "（模板无效：%s）" % e
