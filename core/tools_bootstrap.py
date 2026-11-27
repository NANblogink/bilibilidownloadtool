# -*- coding: utf-8 -*-
import os
import shutil
import sys
import tarfile

_TOOL_DIRS = ("ffmpeg", "mpv", "bento4")
_REQUIRED = (
    ("ffmpeg", "bin", "ffmpeg.exe"),
    ("ffmpeg", "bin", "ffprobe.exe"),
    ("mpv", "mpv.exe"),
    ("bento4", "bin", "mp4decrypt.exe"),
)


def app_root():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        internal = os.path.join(base, "_internal")
        return internal if os.path.isdir(internal) else base
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ready(root):
    return all(os.path.isfile(os.path.join(root, *parts)) for parts in _REQUIRED)


def ensure_tools():
    root = app_root()
    if _ready(root):
        return root

    archive = os.path.join(root, "tools.tar.xz")
    if not os.path.isfile(archive):
        print("[tools] 未找到 tools.tar.xz，沿用现有工具目录")
        return root

    print("[tools] 首次运行，解压运行组件...")
    temp_dir = os.path.join(root, ".tools_tmp")
    shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(temp_dir, exist_ok=True)
    try:
        with tarfile.open(archive, "r:xz") as tar:
            for member in tar.getmembers():
                name = member.name.replace("\\", "/")
                if not name.startswith(_TOOL_DIRS) or ".." in name.split("/"):
                    raise RuntimeError("tools.tar.xz 路径异常: %s" % member.name)
            tar.extractall(temp_dir)
        for name in _TOOL_DIRS:
            src = os.path.join(temp_dir, name)
            dst = os.path.join(root, name)
            if os.path.isdir(src):
                shutil.rmtree(dst, ignore_errors=True)
                shutil.move(src, dst)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    if not _ready(root):
        raise RuntimeError("运行组件解压不完整，请检查 tools.tar.xz")
    print("[tools] 运行组件就绪")
    return root
