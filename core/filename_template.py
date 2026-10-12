# -*- coding: utf-8 -*-
import os
import re
import time as _time

MAX_NAME_LEN = 200

FALLBACK_TEMPLATE = "{标题}"

TEMPLATE_VARS = [
    ("{标题}", "视频标题"),
    ("{集数}", "集数（1、2、10）"),
    ("{集数2}", "集数两位补零（01）"),
    ("{集数3}", "集数三位补零（001）"),
    ("{序号}", "批次序号（按序号位数设置）"),
    ("{UP主}", "UP主名"),
    ("{合集}", "合集/番剧/课程标题"),
    ("{BV号}", "BV号"),
    ("{cid}", "视频 cid"),
    ("{日期}", "日期 2026-10-01"),
    ("{时间}", "时间 19.04.52"),
    ("{类型}", "类型（普通视频/番剧/课程）"),
]

VAR_ALIASES = {
    "title": "标题",
    "ep": "集数",
    "ep2": "集数2",
    "ep3": "集数3",
    "ep4": "集数4",
    "seq": "序号",
    "author": "UP主",
    "season": "合集",
    "bvid": "BV号",
    "cid": "cid",
    "date": "日期",
    "time": "时间",
    "type": "类型",
}

PRESET_TEMPLATES = [
    ("默认（集数前缀）", "{标题}"),
    ("序号 + 标题", "{序号} {标题}"),
    ("标题 + 序号", "{标题}_{序号}"),
    ("UP主 + 标题", "[{UP主}] {标题}"),
    ("合集 + 集数 + 标题", "{合集}_{集数2}_{标题}"),
    ("集数 + UP主 + 标题", "{集数2}_{UP主}_{标题}"),
    ("日期 + 标题", "{日期}_{标题}"),
    ("原样（不加工）", "{标题}"),
]

ASSET_SETTING_KEYS = {
    "video": "filename_template",
    "audio": "filename_template_audio",
    "danmaku": "filename_template_danmaku",
    "subtitle": "filename_template_subtitle",
    "cover": "filename_template_cover",
}

ASSET_LABELS = {
    "video": "视频",
    "audio": "音频",
    "danmaku": "弹幕",
    "subtitle": "字幕",
    "cover": "封面",
}


def _read_setting_fresh(config, key, default=""):
    try:
        val = config.get_app_setting(key, default)
    except Exception:
        val = default
    if val not in (None, ""):
        return val
    try:
        import json
        import os
        path = getattr(config, "config_file", None)
        if path and os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                disk = json.load(f)
            dval = (disk.get("app_settings") or {}).get(key)
            if dval not in (None, ""):
                try:
                    config.set_app_setting(key, dval)
                except Exception:
                    pass
                return dval
    except Exception:
        pass
    return val


def get_asset_template(config, asset="video"):
    if config is None:
        return ""
    key = ASSET_SETTING_KEYS.get(asset, "filename_template")
    tpl = _read_setting_fresh(config, key)
    if tpl and str(tpl).strip():
        return str(tpl).strip()
    if asset != "video":
        base = _read_setting_fresh(config, "filename_template")
        if base and str(base).strip():
            return str(base).strip()
    return ""


def render_asset_name(config, asset, context):
    tpl = get_asset_template(config, asset)
    if not tpl:
        return None
    try:
        name = render_template(tpl, context)
    except Exception:
        return None
    return name or None

_ILLEGAL = '\\/:*?"<>|'


def illegal_filename_chars():
    """返回文件名非法字符列表"""
    return list(_ILLEGAL)


def sanitize_filename(name, replacement="_"):
    """替换 Windows 文件名非法字符，并去掉首尾空白与结尾的点。"""
    if name is None:
        return ""
    s = str(name)
    for c in _ILLEGAL:
        s = s.replace(c, replacement)
    s = "".join(ch for ch in s if ord(ch) >= 32)
    s = s.strip()
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
        "标题": str(title or "").strip(),
        "集数": _pad(ep, 0) if ep is not None else "",
        "集数2": _pad(ep, 2) if ep is not None else "",
        "集数3": _pad(ep, 3) if ep is not None else "",
        "集数4": _pad(ep, 4) if ep is not None else "",
        "序号": _pad(seq, ep_digits) if seq is not None else "",
        "UP主": str(author or "").strip(),
        "合集": str(season or "").strip(),
        "BV号": str(bvid or "").strip(),
        "cid": str(cid or "").strip(),
        "日期": _time.strftime("%Y-%m-%d", _now),
        "时间": _time.strftime("%H.%M.%S", _now),
        "类型": type_map.get(str(media_type or "").strip().lower(), ""),
    }
    for _en, _cn in VAR_ALIASES.items():
        if _cn in ctx:
            ctx[_en] = ctx[_cn]
    return ctx


def _clean_rendered(text):
    """清理渲染结果里因空变量留下的多余分隔符与空括号。"""
    s = text
    for _ in range(3):
        new = re.sub(r"[\[\(【]\s*[\]\)】]", "", s)
        if new == s:
            break
        s = new
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"[_\-]{2,}", "_", s)
    s = re.sub(r"\s*([_\-])\s*", r"\1", s)
    s = s.strip(" _-.")
    return s


def render_template(template, context, strict=False):
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
        rendered = template.format_map(table)
    except (KeyError, IndexError, ValueError):
        if strict:
            raise
        rendered = template
        for k, v in table.items():
            rendered = rendered.replace("{" + k + "}", v)
        rendered = re.sub(r"\{[^{}]*\}", "", rendered)

    rendered = _clean_rendered(rendered)
    rendered = sanitize_filename(rendered)
    if len(rendered) > MAX_NAME_LEN:
        rendered = rendered[:MAX_NAME_LEN].rstrip(" _-.")
    if not rendered:
        rendered = sanitize_filename(
            str((context or {}).get("标题") or (context or {}).get("title") or "")
        ) or "未命名"
    return rendered


def validate_template(template):
    if not template or not str(template).strip():
        return True, ""
    t = str(template)
    known = {k.strip("{}") for k, _ in TEMPLATE_VARS}
    known |= set(VAR_ALIASES.keys())
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
    used = re.findall(r"\{([^{}]*)\}", t)
    unknown = []
    for u in used:
        name = u.strip()
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
