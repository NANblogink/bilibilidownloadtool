"""用用户自己的 logo.png 生成 Android 各密度启动图标。

Android 启动图标（mipmap）规格：
    mdpi     48x48
    hdpi     72x72
    xhdpi    96x96
    xxhdpi   144x144
    xxxhdpi  192x192

另外 buildozer/p4a 只认单个 icon.png（会自己缩放到各密度），但我们这里
直接生成 p4a 需要的 icon.png，并额外导出各密度供检查。
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(PROJECT, "logo.png")
OUT_ICON = os.path.join(HERE, "icon.png")

DENSITIES = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}

print("=== 读取源 logo ===")
if not os.path.isfile(SRC):
    raise SystemExit(f"找不到 {SRC}")
src = Image.open(SRC).convert("RGBA")
print(f"  {SRC}: {src.size} {src.mode}")

# 源图白底 + 蓝色电视图标
# 1) 裁掉留白占满画布
# 2) 透明或白底皆可
# 保留比例居中留8%边距
W, H = src.size
side = max(W, H)
canvas = Image.new("RGBA", (side, side), (255, 255, 255, 0))
canvas.paste(src, ((side - W) // 2, (side - H) // 2), src)

# 去掉纯白背景 → 透明
datas = canvas.getdata()
new_data = []
for r, g, b, a in datas:
    # 近纯白像素设为透明
    if r > 245 and g > 245 and b > 245:
        new_data.append((r, g, b, 0))
    else:
        new_data.append((r, g, b, a))
canvas.putdata(new_data)

print("\n=== 导出各密度 ===")
for name, px in DENSITIES.items():
    # 留 8% 安全边距
    inner = int(px * 0.92)
    img = canvas.resize((inner, inner), Image.LANCZOS)
    tile = Image.new("RGBA", (px, px), (255, 255, 255, 0))
    off = (px - inner) // 2
    tile.paste(img, (off, off), img)
    d = os.path.join(HERE, "mipmap-" + name)
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, "icon.png")
    tile.save(fp)
    print(f"  {name:8s} {px:3d}x{px:<3d} -> {os.path.relpath(fp, HERE)}")

# p4a主图标512
main = canvas.resize((512, 512), Image.LANCZOS)
main.save(OUT_ICON)
print(f"\n=== 主图标 ===")
print(f"  {os.path.relpath(OUT_ICON, HERE)}  {os.path.getsize(OUT_ICON)/1024:.0f} KB  {main.size}")

# 另生成标题栏小图标
ui_icon = canvas.resize((128, 128), Image.LANCZOS)
ui_path = os.path.join(HERE, "logo_ui.png")
ui_icon.save(ui_path)
print(f"  {os.path.relpath(ui_path, HERE)}  {os.path.getsize(ui_path)/1024:.0f} KB  {ui_icon.size}")
