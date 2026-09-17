"""
模块搜索路径注入层 —— 必须在任何业务模块 import 之前被导入。

背景
----
本项目把业务模块按职责分到了子目录：

    core/            核心业务（配置、任务、下载、工具、云端…）
    core/infra/      基础设施（网络、签名、日志、平台、错误码）
    parsers/         B站解析 + 功能界面（音视频/直播/表情/字幕/播放器/托盘/通知）
    build/           打包与安装（build / build_msix / installer / uninstaller / cli）

但模块之间的 import 一律保持**扁平写法**（如 `from tool_manager import ToolManager`），
因此这里把上述目录加入 sys.path，使这些模块名仍可作为顶层模块被导入。

这样做的原因（都是实测确认的硬约束）：
  1. `boot.py` 用 `runpy.run_module("main")` 启动，`main.py` 必须在仓库根
  2. `ui.py` 与 `main.py` 相互 import，形成真实循环依赖，`ui.py` 也留在根
  3. PyInstaller 打包时按目录结构还原，本模块用 `__file__` 推导，打包后同样有效

维护提示
--------
新增子目录时，把它加进下面的 _SUBDIRS 即可，无需改动任何 import 语句。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))

# 需要加入 sys.path 的子目录（相对仓库根）
_SUBDIRS = (
    "core",
    os.path.join("core", "infra"),
    "parsers",
    "build",
)


def install():
    """把子目录加入 sys.path（幂等）。返回实际加入的目录列表。"""
    added = []
    for sub in _SUBDIRS:
        path = os.path.normpath(os.path.join(_HERE, sub))
        if os.path.isdir(path) and path not in sys.path:
            # 插到末尾：第三方库优先，避免与标准库/依赖同名冲突
            sys.path.append(path)
            added.append(path)
    return added


def project_root():
    """返回项目根目录（即本文件所在目录）。

    模块归类到 core/ parsers/ build/ 等子目录后，`os.path.dirname(__file__)`
    指向各自子目录而非项目根。凡需定位 ffmpeg/ mpv/ bento4/ version_info 等
    根目录资源的代码，都应改用本函数。
    """
    return _HERE


# 导入本模块即生效
install()
