"""补齐写 Kivy 界面所需的接口细节。"""
import io
import os
import re

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
OUT = os.path.join(ROOT, "other", "android", "_api_report3.txt")
L = []


def w(s=""):
    L.append(str(s))


ui = io.open(os.path.join(ROOT, "ui.py"), encoding="utf-8").read()
par = io.open(os.path.join(ROOT, "parsers", "bilibili_parser.py"),
              encoding="utf-8").read()

# 1) 下载按钮组装参数
w("=== ui.py: start_download / download_params 组装处 ===")
for m in re.finditer(r"download_params\s*=\s*\{", ui):
    s = m.start()
    seg = ui[s:s + 1800]
    ln = ui[:s].count("\n") + 1
    w(f"--- L{ln} ---")
    w(seg[:1500])
    w()
    break

# 2) qn / 清晰度相关
w("=== 清晰度 (qn) 相关取值 ===")
for m in re.finditer(r"\bqn\b\s*=\s*([^,\n\)]{1,40})", ui):
    ln = ui[:m.start()].count("\n") + 1
    w(f"  L{ln}: {m.group(0).strip()[:70]}")
w()
qs = sorted(set(re.findall(r"quality_desc['\"]?\s*[:=]\s*['\"]([^'\"]+)['\"]", par)))
w("  parser 中的 quality_desc 取值样本:")
for q in qs[:15]:
    w(f"    - {q}")
w()

# 3) parse_media
w("=== parser: parse_media 返回字典的键 ===")
i = par.find("def parse_media(")
seg = par[i:i + 40000]
# 找result与return
for m in re.finditer(r"(['\"])(success|title|episodes|qualities|audio_qualities|owner|pic|bvid|is_bangumi|is_cheese|collection|bangumi_info|cheese_info|duration)\1\s*:", seg):
    ln = par[:i + m.start()].count("\n") + 1
    w(f"    L{ln}: {m.group(0)}")
w()

# 4) episodes字
w("=== parser: episodes 每项字段 ===")
keys = sorted(set(re.findall(r"episode(?:s)?\[[^\]]*\]\[\s*['\"]([a-z_0-9]+)['\"]\s*\]", par)))
for k in keys:
    w(f"    - {k}")
w()
keys2 = sorted(set(re.findall(r"\{\s*['\"]index['\"]", par)))
w(f"  episode dict 出现 {len(keys2)} 次（含 index 字段）")
w()

# 5) 登录二维码与轮询
w("=== parser: get_qrcode 返回字段 ===")
i = par.find("def get_qrcode")
seg = par[i:i + 3000]
for m in re.finditer(r"return\s*\{([^}]{0,300})\}", seg, re.S):
    w("  " + " ".join(m.group(1).split())[:280])
w()

w("=== parser: poll_login_status 返回字段 ===")
i = par.find("def poll_login_status")
seg = par[i:i + 4000]
for m in re.finditer(r"return\s*\{([^}]{0,400})\}", seg, re.S):
    w("  " + " ".join(m.group(1).split())[:350])
w()

# 6) 保存目录 / 配置项
w("=== config 里与下载相关的键 ===")
cfg = io.open(os.path.join(ROOT, "core", "config.py"), encoding="utf-8").read()
for m in re.finditer(r"get_app_setting\(\s*['\"]([a-z_0-9]+)['\"]", cfg + ui):
    pass
keys3 = sorted(set(re.findall(r"get_app_setting\(\s*['\"]([a-z_0-9]+)['\"]", ui)))
w("  ui.py 读取的设置项（前 40）:")
for k in keys3[:40]:
    w(f"    - {k}")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
