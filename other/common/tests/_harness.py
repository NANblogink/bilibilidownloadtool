"""跨平台测试公共工具：定位项目根目录。

这些测试原本是为了在一台具体机器上用 WSL 验证而写的，路径写死成
/mnt/e/...。放进 CI 后必须能自己找到项目根，因此这里做统一的向上探测。
"""
import os
import sys


def _looks_like_project(path):
    return (path and os.path.isfile(os.path.join(path, "main.py"))
            and os.path.isdir(os.path.join(path, "core")))


def find_project_root():
    # 1) 本文件位于 other/common/tests/，向上三级即项目根
    here = os.path.dirname(os.path.abspath(__file__))
    cand = os.path.abspath(os.path.join(here, "..", "..", ".."))
    if _looks_like_project(cand):
        return cand

    # 2) 从 cwd 向上找
    cur = os.path.abspath(os.getcwd())
    for _ in range(8):
        if _looks_like_project(cur):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    # 3) 环境变量兜底
    env = os.environ.get("BILI_PROJECT_ROOT")
    if _looks_like_project(env):
        return env

    raise RuntimeError("找不到项目根目录（main.py + core/ 同时存在）")


PROJECT_ROOT = find_project_root()


def install_paths():
    """把 core / core/infra / parsers 挂到 sys.path，并返回项目根。"""
    for sub in ("core", os.path.join("core", "infra"), "parsers"):
        p = os.path.join(PROJECT_ROOT, sub)
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    if PROJECT_ROOT not in sys.path:
        sys.path.insert(0, PROJECT_ROOT)
    return PROJECT_ROOT
