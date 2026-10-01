import os
import sys
import shutil


BUILTIN_ICON_OPTIONS = {
    "default": {
        "label": "默认",
        "author": "寒烟似雪",
        "qq": "",
        "file_name": "logo.ico",
    },
    "alt": {
        "label": "新奇",
        "author": "群友",
        "qq": "",
        "file_name": "logo_alt_kaisui.ico",
    },
}


def _unique_paths(paths):
    result = []
    seen = set()
    for path in paths:
        if not path:
            continue
        norm = os.path.normcase(os.path.normpath(path))
        if norm in seen:
            continue
        seen.add(norm)
        result.append(path)
    return result


def get_runtime_search_dirs():
    """返回图标搜索目录（按优先级）。

    图标资源按类型归入 assets/ 子目录：
      assets/icons/    内置图标（logo.ico / logo_alt_kaisui.ico）
      assets/images/   图片资源（二维码等）
    同时根目录也保留 logo.ico / logo.png（打包脚本按根目录定位并随 _internal 分发），
    因此把根与 assets 子目录都纳入搜索以兼容两种位置。
    """
    roots = []
    if hasattr(sys, "_MEIPASS"):
        roots.append(sys._MEIPASS)
    # 本文件位于 core/，其上级即仓库根
    roots.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.isdir(internal_dir):
            roots.append(internal_dir)
        roots.append(exe_dir)

    dirs = []
    for root in roots:
        dirs.append(root)
        dirs.append(os.path.join(root, "assets", "icons"))
        dirs.append(os.path.join(root, "assets", "images"))
    return _unique_paths(dirs)


def get_writable_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    # 本文件位于 core/，其上级即仓库根
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))



def normalize_icon_mode(mode):
    mode = (mode or "default").strip().lower()
    aliases = {
        "builtin_default": "default",
        "builtin_alt": "alt",
        "custom_upload": "custom",
    }
    return aliases.get(mode, mode if mode in {"default", "alt", "custom"} else "default")


def resolve_builtin_icon_path(icon_key="default"):
    icon_key = "default" if icon_key not in BUILTIN_ICON_OPTIONS else icon_key
    file_name = BUILTIN_ICON_OPTIONS[icon_key]["file_name"]
    for base_dir in get_runtime_search_dirs():
        candidate = os.path.join(base_dir, file_name)
        if os.path.exists(candidate):
            # 防御：历史版本的 logo.ico 实际是「PNG 改名」，Windows 任务栏
            # 按 ICO 解析会得到空白图标。这里校验魔数，遇到假 ICO 就跳过，
            # 继续寻找后续候选（真 ICO / PNG 兜底），避免任务栏空白。
            if file_name.lower().endswith(".ico") and not _is_real_ico(candidate):
                continue
            return candidate
    # 没有可用的真 ICO 时返回空串，让调用方继续尝试其它图标源
    # （例如 alt 图标 logo_alt_kaisui.ico 就是真正的 ICO），
    # 而不是退回一个会被任务栏渲染成空白的假 ICO。
    return ""


def _is_real_ico(path):
    """校验文件是否为真正的 ICO（魔数 00 00 01 00）。

    历史缺陷：仓库里的 logo.ico 实际是 PNG 改扩展名，Qt 能正常显示，
    但 Windows 任务栏/资源管理器按 ICO 解析会显示空白。此函数用于识别。
    """
    try:
        with open(path, "rb") as f:
            head = f.read(4)
        return head == b"\x00\x00\x01\x00"
    except Exception:
        return False


def get_effective_icon_mode(config=None):
    mode = "default"
    if config is not None:
        try:
            mode = normalize_icon_mode(config.get_app_setting("app_icon_mode", "default"))
            if mode == "custom":
                custom_icon_path = config.get_app_setting("custom_icon_path", "")
                if custom_icon_path and os.path.exists(custom_icon_path):
                    return "custom"
                return "default"
        except Exception:
            return "default"
    return mode if mode in {"default", "alt", "custom"} else "default"


def get_effective_icon_path(config=None):
    icon_mode = get_effective_icon_mode(config)
    if icon_mode == "custom" and config is not None:
        try:
            custom_icon_path = config.get_app_setting("custom_icon_path", "")
            if custom_icon_path and os.path.exists(custom_icon_path):
                return custom_icon_path
        except Exception:
            pass

    for builtin_key in [icon_mode, "default", "alt"]:
        if builtin_key in BUILTIN_ICON_OPTIONS:
            candidate = resolve_builtin_icon_path(builtin_key)
            if os.path.exists(candidate):
                return candidate
    return ""


def get_icon_credit(config=None):
    icon_mode = get_effective_icon_mode(config)
    if icon_mode == "custom":
        return {
            "mode": "custom",
            "label": "自定义上传图标",
            "author": "用户自定义",
            "qq": "",
        }

    meta = BUILTIN_ICON_OPTIONS.get(icon_mode, BUILTIN_ICON_OPTIONS["default"]).copy()
    meta["mode"] = icon_mode
    return meta


def ensure_custom_icon_file(source_path):
    if not source_path:
        raise ValueError("未提供图标文件路径")
    if not os.path.exists(source_path):
        raise FileNotFoundError(source_path)

    ext = os.path.splitext(source_path)[1].lower() or ".ico"
    target_dir = os.path.join(get_writable_app_dir(), "custom_icons")
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, f"custom_icon{ext}")
    if os.path.normcase(os.path.abspath(source_path)) == os.path.normcase(os.path.abspath(target_path)):
        return target_path
    shutil.copy2(source_path, target_path)
    return target_path
