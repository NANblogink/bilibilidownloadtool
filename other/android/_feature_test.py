"""功能测试：集数选择、停止解析、下载参数裁剪。

这些是新加/改动的逻辑，必须真的跑一遍，而不是只看界面能不能建出来。
"""
import io
import os
import sys

os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ["KIVY_LOG_LEVEL"] = "error"
os.environ.pop("KIVY_WINDOW", None)
os.environ["KIVY_NO_CONSOLELOG"] = "1"

ROOT = r"E:\旧桌面备份\来自：电脑桌面\B站视频解析工具V1.8"
AND = os.path.join(ROOT, "other", "android")
OUT = os.path.join(AND, "_feature_test.txt")
L = []


def w(s=""):
    L.append(str(s))


fails = []


def check(name, cond, extra=""):
    w(("  PASS " if cond else "  FAIL ") + name + ((" " + str(extra)) if extra else ""))
    if not cond:
        fails.append(name)


sys.path.insert(0, AND)
for sub in ("core", os.path.join("core", "infra"), "parsers", ""):
    p = os.path.join(ROOT, sub)
    if os.path.isdir(p):
        sys.path.insert(0, p)

import main_kivy as mk  # noqa: E402

w("=== 构建 App ===")
app = mk.BilibiliAndroidApp()
root = app.build()
pt = app.parse_tab
w("  OK")

w()
w("=== 1. 集数选择：数据流 ===")
# 造一个假的解析结果
eps = [{"title": "第%d集" % i, "cid": 1000 + i} for i in range(1, 21)]
fake = {"success": True, "title": "测试合集", "episodes": eps,
        "qualities": [{"desc": "1080P"}, {"desc": "720P"}]}

pt._show_result(fake)
check("解析后默认全选（selected_ep_indexes is None）",
      pt.selected_ep_indexes is None)
check("摘要提示出现", "20" in pt.ep_summary_lbl.text,
      repr(pt.ep_summary_lbl.text))

# 模拟用户勾选 3、5、7
pt.set_episode_selection({2, 4, 6})
check("勾选后记录正确", pt.selected_ep_indexes == {2, 4, 6},
      pt.selected_ep_indexes)
check("摘要显示已选 3 集", "3 集" in pt.ep_summary_lbl.text,
      repr(pt.ep_summary_lbl.text))

w()
w("=== 2. on_download 是否真的只下载选中的集 ===")
captured = {}


class FakeDM:
    def start_download(self, params):
        captured.update(params)


app._download_manager = FakeDM()
app.start_download = app.start_download  # 保持原方法
#start_downl
app.start_download(fake, qn=80, content_type=0)

w()
w("=== 2b. 通过 parse_tab.on_download 走完整路径 ===")
captured.clear()
#get_download假对象
app.get_download_manager = lambda: FakeDM()
pt.selected_ep_indexes = {2, 4, 6}
pt.on_download(0)
got = captured.get("episodes") or []
check("只提交选中的 3 集", len(got) == 3, "实际 %d 集" % len(got))
check("选的正是第 3/5/7 集",
      [e["title"] for e in got] == ["第3集", "第5集", "第7集"],
      [e["title"] for e in got])
check("qn 透传正确（默认自动=0，交给引擎取最高）",
      captured.get("qn") == 0, captured.get("qn"))
check("download_content_type 正确",
      captured.get("download_content_type") == 0)
check("原始 video_info 的 episodes 未被破坏（拷贝语义）",
      len(fake["episodes"]) == 20, len(fake["episodes"]))

w()
w("=== 3. 不选任何集时应拒绝 ===")
captured.clear()
pt.selected_ep_indexes = set()
pt.on_download(0)
check("空选择不启动下载", not captured, captured.get("task_id"))

w()
w("=== 4. 全选（None）应提交全部 20 集 ===")
captured.clear()
pt.selected_ep_indexes = None
pt.on_download(0)
check("提交全部 20 集", len(captured.get("episodes") or []) == 20,
      len(captured.get("episodes") or []))

w()
w("=== 5. 停止解析按钮切换 ===")
pt._set_parsing_ui(True)
check("解析中按钮文本为「停止解析」", pt.parse_btn.text == "停止解析",
      pt.parse_btn.text)
check("解析中按钮为红色", pt.parse_btn.background_color[0] > 0.9,
      pt.parse_btn.background_color)
app.parse_cancelled = False
pt.on_stop_parse()
check("点击后置位取消标志", app.parse_cancelled is True)
pt._set_parsing_ui(False)
check("结束后恢复「解析」", pt.parse_btn.text == "解析", pt.parse_btn.text)
check("结束后按钮可用", pt.parse_btn.disabled is False)

w()
w("=== 6. 集数弹窗能否构建（含勾选/全选/反选/过滤）===")
try:
    picker = mk.EpisodePicker(app, fake, pt)
    check("弹窗构建成功", True)
    check("行数与集数一致", len(picker.rows) == 20, len(picker.rows))
    picker._set_all(False)
    check("取消全选后 checked 为空", picker.checked == set())
    picker._set_all(True)
    check("全选后 checked=20", len(picker.checked) == 20)
    picker._invert()
    check("反选后为空", picker.checked == set())
    picker._on_toggle(3, True)
    check("单勾第4集", picker.checked == {3}, picker.checked)
    picker._apply_filter("第1集")
    visible = [r for r in picker.rows if not r.disabled]
    # 第1集只命中第1集
    check("过滤「第1集」只命中第 1 集",
          [r.index + 1 for r in visible] == [1],
          [r.index + 1 for r in visible])
    # 纯数字命中1与10
    picker._apply_filter("1")
    visible = [r for r in picker.rows if not r.disabled]
    check("过滤「1」命中 1,10-19 共 11 行",
          len(visible) == 11, [r.index + 1 for r in visible])
    picker._apply_filter("")
    check("清空过滤后全部可见",
          all(not r.disabled for r in picker.rows))
    picker._confirm({1, 2})
    check("确认后写回 parse_tab", pt.selected_ep_indexes == {1, 2},
          pt.selected_ep_indexes)
except Exception as exc:
    import traceback
    check("集数弹窗可用", False, str(exc))
    w(traceback.format_exc()[-1500:])

w()
w("=== 7. 单集视频应提示无需选择 ===")
single = {"success": True, "title": "单集", "episodes": [{"title": "P1"}]}
pt._show_result(single)
check("单集不显示选择提示", pt.ep_summary_lbl.text == "",
      repr(pt.ep_summary_lbl.text))

w()
w(f"TOTAL FAILURES: {len(fails)}")
for f in fails:
    w("  - " + f)

io.open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("written", OUT)
print("FAILURES:", len(fails))
