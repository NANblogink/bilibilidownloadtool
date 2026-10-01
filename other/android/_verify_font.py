import io
import os
import json
from fontTools.ttLib import TTFont

D = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8\other\android"
OUT = os.path.join(D, "_font_report.txt")

lines = []
for name in ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"):
    p = os.path.join(D, name)
    if not os.path.isfile(p):
        lines.append("MISSING " + name)
        continue
    f = TTFont(p)
    cm = f.getBestCmap()
    full = f["name"].getDebugName(4)
    samples = [
        "B站视频解析工具", "视频链接", "粘贴", "解析", "开始下载",
        "清晰度", "自动（最高）", "下载任务", "暂无任务", "设置",
        "设备信息", "CPU 核心", "可用内存", "建议并发", "同时任务",
        "登录", "退出登录", "扫码登录", "选择集数", "选择弹幕",
        "下载完整视频", "下载画面", "下载音频", "批量", "历史记录",
        "任务管理", "视频工具", "保存封面", "全选", "清空选择",
        "解析完成，可开始下载", "已加入下载队列", "解析失败",
        "已开始下载到：", "请先解析视频", "剪贴板为空", "已从剪贴板粘贴",
        "扫码登录", "密码登录", "短信登录", "Cookie 登录",
        "画质选择", "音质选择", "保存路径", "开始解析", "停止",
        "进度", "速度", "剩余时间", "已完成", "正在合并音视频",
        "番剧", "合集", "课堂", "直播", "投稿",
    ]
    miss = []
    for s in samples:
        for ch in s:
            if ord(ch) > 127 and ord(ch) not in cm:
                miss.append(ch)
    lines.append(f"{name}")
    lines.append(f"  font name : {full}")
    lines.append(f"  codepoints: {len(cm)}")
    lines.append(f"  size      : {os.path.getsize(p)/1024:.0f} KB")
    lines.append(f"  missing   : {sorted(set(miss)) if miss else 'NONE - OK'}")
    lines.append("")

io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("written to", OUT)
