"""无头方式真正构建一遍 Kivy 界面，抓出 KV 语法错误与运行时异常。

这比静态检查强得多：KV 里的拼写错误、属性名错误、
窗口构建期抛异常，都能在这里暴露，而不必等 40 分钟的 APK 构建。
"""
import io
import os
import sys
import traceback

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ["KIVY_LOG_LEVEL"] = "error"
#KIVY_WINDOW
#sys.exit退出
# 改用真实但隐藏的窗口
os.environ.pop("KIVY_WINDOW", None)
os.environ["KIVY_NO_CONSOLELOG"] = "1"

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
AND = os.path.join(ROOT, "other", "android")
OUT = os.path.join(AND, "_render_report.txt")
L = []


def _flush():
    """无论在哪一步死掉，都要留下证据（只写文件，避免与 Kivy 的
    stderr 劫持冲突）。"""
    try:
        io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
    except Exception:
        pass


L.append("### render test started")
L.append("### exe=%s" % sys.executable)
_flush()


def w(s=""):
    L.append(str(s))
    try:
        io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
    except Exception:
        pass


# 让main_kivy
sys.path.insert(0, AND)
for sub in ("core", os.path.join("core", "infra"), "parsers", ""):
    p = os.path.join(ROOT, sub)
    if os.path.isdir(p):
        sys.path.insert(0, p)

w("=== 1. 导入 Kivy ===")
try:
    import kivy
    w(f"  kivy {kivy.__version__}")
except BaseException as exc:
    w(f"  !! {type(exc).__name__}: {exc}")
    _flush()
    sys.exit(1)
w("  step1 done")

w()
w("=== 2. 导入 main_kivy ===")
main_mod = None
try:
    import importlib.util as _ilu
    _spec = _ilu.find_spec("main_kivy")
    w(f"  解析到文件: {_spec.origin}")
    import main_kivy as main_mod
    w("  导入成功")
    w(f"  模块文件: {getattr(main_mod, '__file__', '?')}")
    w(f"  FONT_NAME = {main_mod.FONT_NAME!r}")
    w(f"  字体文件: {os.path.basename(main_mod._FONT_REG)} 存在={os.path.isfile(main_mod._FONT_REG)}")
except BaseException as exc:
    w(f"  !! 导入失败: {type(exc).__name__}: {exc}")
    w(traceback.format_exc()[-2500:])
    _flush()
    sys.exit(1)

w()
w("=== 3. 加载 KV 模板（这一步能抓出 KV 语法错误）===")
try:
    from kivy.lang import Builder
    Builder.load_string(main_mod.KV)
    w("  KV 加载成功")
except Exception as exc:
    w(f"  !! KV 加载失败: {type(exc).__name__}: {exc}")
    w(traceback.format_exc()[-2500:])
    io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
    print("written", OUT)
    sys.exit(1)

w()
w("=== 4. 字体是否真的注册成功 ===")
try:
    from kivy.core.text import LabelBase
    fonts = getattr(LabelBase, "_fonts", {})
    w(f"  已注册字体: {sorted(fonts.keys())}")
    w(f"  'CN' 已注册: {'CN' in fonts}")
except Exception as exc:
    w(f"  !! {exc}")

w()
w("=== 5. 构建整个界面（build()）===")
try:
    w("  创建 App 实例…")
    app = main_mod.BilibiliAndroidApp()
    w("  App 实例 OK")

    # 分步build定位
    w("  加载设置…")
    app.load_settings()
    w("  设置加载完成, save_dir=%s" % app.save_dir)

    w("  调用 build()…")
    root = app.build()
    w("  build() 成功")
    w(f"  根控件: {type(root).__name__}")
    w(f"  子控件数: {len(root.children)}")

    # 关键控件是否都存在
    for attr in ("parse_tab", "task_tab", "history_tab", "settings_tab", "tabs"):
        has = hasattr(app, attr)
        w(f"    app.{attr}: {'存在' if has else '缺失'}")
    for attr in ("url_input", "quality_spinner", "audio_spinner", "ep_input",
                 "danmaku_spinner", "path_lbl", "parse_btn"):
        has = hasattr(app.parse_tab, attr)
        w(f"    parse_tab.{attr}: {'存在' if has else '缺失'}")
except BaseException as exc:
    w(f"  !! build() 失败: {type(exc).__name__}: {exc}")
    w(traceback.format_exc()[-4000:])
    _flush()
    sys.exit(1)

w()
w("=== 6. Tab 数量与标题 ===")
try:
    tabs = [t.text for t in app.tabs.tab_list]
    w(f"  Tab: {tabs}")
except Exception as exc:
    w(f"  !! {exc}")

w()
w("=== 7. 中文渲染（真正的乱码检测）===")
try:
    from kivy.core.text import Label as CoreLabel
    from kivy.core.text import LabelBase
    sample = "B站视频解析工具 清晰度 下载 弹幕 任务 设置"
    for fname in ("CN", "Roboto"):
        try:
            cl = CoreLabel(text=sample, font_name=fname, font_size=18)
            cl.refresh()
            tex = cl.texture
            w(f"  字体 {fname}: 纹理 {tex.size if tex else None}")
            if tex is None:
                w(f"    !! {fname} 渲染失败（可能是缺字）")
        except Exception as exc:
            w(f"  字体 {fname}: 渲染报错 {type(exc).__name__}: {str(exc)[:120]}")

    # 逐字符检查缺字
    from fontTools.ttLib import TTFont
    cm = TTFont(main_mod._FONT_REG).getBestCmap()
    miss = [c for c in sample if ord(c) > 127 and ord(c) not in cm]
    w(f"  字体缺字检查: {miss if miss else '无（中文可正常显示）'}")
except Exception as exc:
    w(f"  !! {type(exc).__name__}: {exc}")

w()
w("=== 8. 解析 URL 拆分逻辑 ===")
try:
    cases = [
        ("BV1xx411c7mD", ("video", "BV1xx411c7mD")),
        ("av12345", ("video", "av12345")),
        ("ep12345", ("bangumi", "ep12345")),
        ("ss12345", ("bangumi", "ss12345")),
        ("https://www.bilibili.com/video/BV1xx411c7mD", ("video", "BV1xx411c7mD")),
        ("https://www.bilibili.com/bangumi/play/ep12345", ("bangumi", "ep12345")),
        ("https://space.bilibili.com/123456", ("space", "123456")),
        ("https://www.bilibili.com/list/123456", ("favlist", "123456")),
    ]
    ok = 0
    for url, want in cases:
        got = main_mod.ParseTab._split_url(url)
        good = got == want
        ok += good
        w(f"  {'OK ' if good else 'BAD'} {url[:44]:44s} -> {got}")
    w(f"  {ok}/{len(cases)} 通过")
except Exception as exc:
    w(f"  !! {exc}")

w()
w("=== 9. qn 映射与桌面版一致 ===")
w(f"  {main_mod.QN_MAP}")
w(f"  1080P -> {main_mod.QN_MAP.get('1080P')} (桌面版=80)")
w(f"  4K    -> {main_mod.QN_MAP.get('4K')} (桌面版=126)")

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
