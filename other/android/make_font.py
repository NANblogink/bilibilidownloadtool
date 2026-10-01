"""从 Windows 的微软雅黑（msyh.ttc）抽取一个精简子集字体，用于 Android APK。

桌面版用的就是 Microsoft YaHei，这里保持一致可以确保字形完全对齐。
但完整 msyh.ttc 有 19 MB，直接打进 APK 会明显变大，因此用 fonttools 做子集化：
  * 保留 ASCII / 常用符号
  * 保留源码里实际出现过的所有汉字
这样体积通常只有几十~几百 KB，且不会出现乱码。
"""
import io
import os
import re
import sys

SRC = r"C:\Windows\Fonts\msyh.ttc"
# 同时抽取一份粗体，供标题使用
SRC_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
PROJECT = os.path.normpath(os.path.join(OUT_DIR, "..", ".."))

print("=== 收集源码中出现的所有字符 ===")
chars = set()
scanned = 0
for root, dirs, files in os.walk(PROJECT):
    dirs[:] = [d for d in dirs if d not in (
        ".git", "__pycache__", "build", "dist", "build_dist", "build_dist_beta",
        "build_parts", "build_parts_beta", "dist_beta", "_整理", ".build_stage",
        "node_modules", ".venv", "other")]
    for fn in files:
        if not fn.endswith((".py", ".kv")):
            continue
        fp = os.path.join(root, fn)
        try:
            text = io.open(fp, encoding="utf-8", errors="ignore").read()
            chars.update(text)
            scanned += 1
        except Exception:
            pass

print(f"  扫描 {scanned} 个文件，收集到 {len(chars)} 个不同字符")

# 必须保留的基础字符集
base = set(
    "".join(chr(c) for c in range(0x20, 0x7F)) +          # ASCII
    "　、。！？；：“”‘’（）【】《》〈〉—…·×÷±≤≥≠∞°℃"      # 中文标点
    "①②③④⑤⑥⑦⑧⑨⑩←→↑↓■□●○◆◇★☆✓✗✔✘⚠"        # 常用符号
    "０１２３４５６７８９"
)
chars |= base
# 补充常用汉字，避免运行时动态拼接的字符串缺字
chars |= set("零一二三四五六七八九十百千万亿年月日时分秒周星期"
             "大小多少高低长短宽窄深浅轻重快慢新旧好坏对错"
             "上下左右前后内外中间东西南北中"
             "有无是非能否可否要不要对不对行不行"
             "正在等待完成失败成功错误异常重试取消确认"
             "下载上传解析播放暂停继续停止开始结束关闭打开"
             "视频音频画面弹幕封面标题作者时长清晰度画质"
             "登录退出账号密码二维码短信验证手机号"
             "设置任务历史批量选择全选清空删除添加修改保存"
             "路径目录文件大小进度速度剩余已用总计共计"
             "网络连接超时服务器请求响应数据格式版本更新"
             "登录未登录已登录会员普通用户大会员"
             # B站内容形态与界面高频词
             "投稿番剧合集课堂直播专栏频道分区排行追番"
             "字幕音轨码率帧率分辨率编码解码转码封装"
             "缓存断点续传合并切片下载中已完成队列排队"
             "收藏点赞投币分享关注粉丝动态评论回复"
             "工具栏拖拽长按滑动点击双击返回上一页"
             "权限存储相机通知后台前台服务电池省电"
             "错误提示请稍候正在加载刷新重载初始化"
             "建议推荐自定义默认自动手动高级基础")
print(f"  加上基础与常用集后共 {len(chars)} 个字符")

if not os.path.isfile(SRC):
    print(f"  !! 找不到 {SRC}")
    sys.exit(1)

try:
    from fontTools import subset
    from fontTools.ttLib import TTFont, TTCollection
except ImportError:
    print("  !! 需要 fonttools：pip install fonttools")
    sys.exit(1)


def build(src_path, out_name, label):
    print(f"\n=== 生成 {label} ===")
    if not os.path.isfile(src_path):
        print(f"  跳过（不存在）：{src_path}")
        return None

    # .ttc 是字体集合，取第一个（Regular）或按名称挑
    try:
        coll = TTCollection(src_path, lazy=False)
        font = coll.fonts[0]
        if len(coll.fonts) > 1:
            names = []
            for f in coll.fonts:
                try:
                    nm = f["name"].getDebugName(4)
                except Exception:
                    nm = "?"
                names.append(nm)
            print(f"  ttc 内含 {len(coll.fonts)} 个字体：{names}")
            # 优先选名字里带 Regular / 不含 Bold 的
            for f in coll.fonts:
                try:
                    nm = (f["name"].getDebugName(4) or "")
                except Exception:
                    nm = ""
                if "Regular" in nm or "regular" in nm:
                    font = f
                    print(f"  选用：{nm}")
                    break
    except Exception:
        font = TTFont(src_path, lazy=False)

    # 检查 cmap 覆盖率
    cmap = font.getBestCmap()
    have = sum(1 for c in chars if ord(c) in cmap)
    print(f"  源字体含 {len(cmap)} 个码位，覆盖我们需要的 {have}/{len(chars)}")

    opts = subset.Options()
    opts.set(layout_features="*", name_IDs="*", name_legacy=True,
             name_languages="*", notdef_outline=True, recalc_bounds=True,
             drop_tables=[], glyph_names=False, hinting=True, legacy_kern=True)
    subsetter = subset.Subsetter(options=opts)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)

    out_path = os.path.join(OUT_DIR, out_name)
    font.save(out_path)
    sz = os.path.getsize(out_path)
    print(f"  已生成 {out_name}  ({sz/1024:.0f} KB)")
    return out_path


r1 = build(SRC, "NotoSansSC-Regular.ttf", "常规体（msyh.ttc）")
r2 = build(SRC_BOLD, "NotoSansSC-Bold.ttf", "粗体（msyhbd.ttc）")

print("\n=== 校验生成结果 ===")
for p in (r1, r2):
    if not p or not os.path.isfile(p):
        continue
    f = TTFont(p)
    cm = f.getBestCmap()
    test = "B站视频解析工具下载解析中请稍候清晰度弹幕任务设置"
    miss = [c for c in test if ord(c) not in cm]
    print(f"  {os.path.basename(p)}: 码位数={len(cm)} 缺字={miss or '无'}")
