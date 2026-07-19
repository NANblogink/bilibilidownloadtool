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
    dirs = []
    if hasattr(sys, "_MEIPASS"):
        dirs.append(sys._MEIPASS)
    dirs.append(os.path.dirname(os.path.abspath(__file__)))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        internal_dir = os.path.join(exe_dir, "_internal")
        if os.path.isdir(internal_dir):
            dirs.append(internal_dir)
        dirs.append(exe_dir)
    return _unique_paths(dirs)


def get_writable_app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


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
            return candidate
    return os.path.join(get_writable_app_dir(), file_name)


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
