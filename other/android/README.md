# Android 版说明（other/android）

B站视频解析工具的 Android 移植。**界面用 Kivy 重写，业务逻辑与桌面版完全同一份代码。**

---

## 1. 为什么还需要它（`import PyQt5` 找不到）

Android 没有 PyQt5（官方根本不提供），所以 `ui.py` 那一套 Qt 界面无法移植。
但从 `ui.py` 往下，项目的业务层本来就是平台无关的：

| 模块 | 作用 | 是否复用 |
|---|---|---|
| `parsers/bilibili_parser.py` | 解析投稿/番剧/合集/课堂/直播/收藏夹 | ✅ 原样复用 |
| `core/downloader.py` | 下载引擎（并发、断点续传、合并） | ✅ 原样复用 |
| `core/task_manager.py` | 任务持久化 | ✅ 原样复用 |
| `core/tool_manager.py` | ffmpeg / mp4decrypt 管理 | ✅ 原样复用 |
| `core/download_history.py` | 下载历史 | ✅ 原样复用 |
| `core/config.py` | 配置读写 | ✅ 原样复用 |
| `core/infra/platform_utils.py` | 平台分支 | ✅ 原样复用 |
| `ui.py` | Qt 界面 | ❌ 用 `main_kivy.py` 重写 |

这样"功能与桌面版一模一样"才成立：**下载、解析、合并的行为来自同一份代码**，
不存在"Android 特供实现"和桌面版逐渐跑偏的问题。

---

## 2. 关键难点：桌面核心 `import PyQt5`

`core/downloader.py` 和 `core/utils.py` 的第一行就是：

```python
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt, QMutex, QWaitCondition
```

Android 上没有 PyQt5，直接 `import downloader` 必然 `ImportError`，
下载功能整个不可用。

**解决办法：`qt_compat.py`（Qt 兼容层）。**

它提供一个**同名的影子 `PyQt5` 包**，只实现桌面版真正用到的那几个符号：

| 符号 | 实现方式 |
|---|---|
| `pyqtSignal` | 描述符 + 每实例回调表；`emit()` 同步调用回调 |
| `QObject` | 最小基类（信号宿主） |
| `QThread` | 真实 `threading.Thread`，实现 `start/run/wait/isRunning` |
| `QMutex` | `threading.Lock` |
| `QWaitCondition` | `threading.Condition`（`wait(mutex, ms)` 语义对齐 Qt） |
| `Qt` | 常量命名空间 |

入口脚本在任何 `core` 导入**之前**调用：

```python
import qt_compat
qt_compat.install()      # 真实 PyQt5 存在时自动跳过，不干预桌面版
```

这样同一份 `downloader.py` 在 Windows（真 PyQt5）和 Android（影子包）
上都能跑，且**桌面代码零改动**。

> ⚠️ 两个必须注意的差异
>
> 1. **信号是同步调用**，不像 Qt 默认的跨线程队列投递。所以界面槽函数里
>    必须用 `Clock.schedule_once(...)` 切回 Kivy 主线程 —— `main_kivy.py`
>    里的 `_sig_*` 系列函数都遵守这一点（见 `test_android_bridge.py` 第 10 项）。
> 2. `QThread` 是普通线程，`terminate()` 只置停止标志，不能强杀。
>    桌面版本身也是靠协作标志退出的，所以行为一致。

---

## 3. 中文不乱码

Kivy 自带的 Roboto 字体**不含汉字**，不处理的话界面全是方块。

本项目随包携带微软雅黑子集：

| 文件 | 说明 |
|---|---|
| `NotoSansSC-Regular.ttf` | 由 `make_font.py` 生成 |
| `NotoSansSC-Bold.ttf` | 同上（粗体） |

> 文件名沿用 NotoSansSC 只是为了通用性，**实际内容是微软雅黑的子集**
> （从 `C:\Windows\Fonts\msyh.ttc` 提取），因为项目原本的界面字体就是
> 微软雅黑，这样 Android 与桌面版的字形最接近。

生成方式：

```bash
python make_font.py      # 需要 fontTools
```

它会扫描项目里所有 `.py` / `.kv` 用到的字符（ASCII、CJK 标点、常用符号）
加上一批手工兜底字符，做子集化，并打印缺字检查结果（应为 `missing: NONE - OK`）。

入口脚本在启动时注册：

```python
LabelBase.register(name="CN", fn_regular="NotoSansSC-Regular.ttf",
                   fn_bold="NotoSansSC-Bold.ttf")
```

---

## 4. 图标

启动图标来自项目根目录的 `logo.png`（用户自己的 logo）。

```bash
python make_icon.py      # 需要 Pillow
```

它会：

1. 读项目根目录的 `logo.png`
2. 把接近白色的背景（r,g,b > 245）抠成透明
3. 放到正方形画布上，留 8% 安全边距
4. 导出 `icon.png`（512）与各密度 `mipmap-*/icon.png`
5. 顺带导出界面用的 `logo_ui.png`

`buildozer.spec` 里：

```ini
icon.filename = %(source.dir)s/icon.png
```

标题栏也直接显示同一张图（`logo_ui.png`）。

---

## 5. 强制竖屏

```ini
android.orientation = portrait
```

界面按竖屏单列布局设计（4 个 Tab：解析 / 任务 / 历史 / 设置）。

---

## 6. 功能对照表

| 桌面版功能 | Android 版 |
|---|---|
| 输入链接解析 | ✅ 解析 Tab |
| 剪贴板自动识别 | ✅ 输入框获得焦点时 |
| 停止解析（保留已解析结果） | ✅ 解析按钮解析中变为「停止解析」 |
| 清晰度选择 | ✅ 下拉（解析后用真实返回的清晰度填充） |
| 音质选择 | ✅ 下拉（Hi-Res / 杜比 / 192K / 132K / 64K） |
| 集数范围输入 | ✅ 输入框（`1-10` 或 `3`） |
| **选择集数（勾选具体某几集）** | ✅ 「选择集数」弹窗：全选/取消全选/反选/按标题搜索 |
| 下载完整视频（画面+音频） | ✅ 主按钮 |
| 仅下载画面 / 仅下载音频 | ✅ |
| 弹幕下载（随视频 / 单独） | ✅ |
| 保存封面 | ✅ |
| 批量下载 | ✅ 多行链接 / UP主空间 / 收藏夹 |
| 批量下载画面 / 音频 / 完整视频 | ✅ 批量弹窗 |
| 下载任务列表（进度/暂停/继续/取消） | ✅ 任务 Tab |
| 清除已完成 | ✅ |
| 下载历史（搜索 / 状态过滤 / 清空） | ✅ 历史 Tab |
| 扫码登录 / 退出登录 | ✅ 设置 Tab |
| 默认清晰度、保存目录设置 | ✅ 设置 Tab |
| 外部工具检查 / 下载 | ✅ 设置 Tab |
| 设备信息（CPU/内存/建议并发） | ✅ 设置 Tab |
| 关于 | ✅ 设置 Tab |
| 系统托盘 / 悬浮球 | ❌ Android 无此概念（改用通知栏常驻） |
| 自动关机 / 打开文件夹 | ❌ 平台不支持（改为显示路径） |
| 格式转换 / 字幕 | ❌ 依赖桌面 ffmpeg 工作流，未移植 |
| 手机号验证码登录 | ❌ 仅支持扫码登录（触屏上更顺手） |
| 内置更新器 / 内测授权 | ❌ 桌面端专用流程 |

下载参数与桌面版**逐字段一致**（见 `ui.py` 的 `download_params` 构造）：

```python
{
  "url", "video_info", "qn", "save_path", "episodes",
  "resume_download", "task_id",
  "download_content_type",   # 0=有声视频 1=仅音频 2=仅视频
  "download_danmaku",
  "video_format", "audio_format", "audio_quality", "danmaku_format",
}
```

---

## 7. 性能取向（"别把电脑搞崩"）

`device_profile()` 按设备内存自动下调并发：

| 可用内存 | 建议并发 | 同时任务 |
|---|---|---|
| < 1.5 GB | 1 | 1 |
| < 2 GB | 1~2 | 1 |
| < 4 GB | 2~3 | 2 |
| ≥ 4 GB | ≤ 4 | 2 |

- 并发上限硬性 `cap=4`，绝不放任无限线程
- 不做悬浮球 / 系统托盘
- 切后台（`on_pause`）暂停解析，回前台恢复

---

---

## 7.5 二维码登录（为什么自带 qrgen）

扫码登录是核心功能，但 **APK 里既没有 `qrcode` 也没有 `PIL`/Pillow**：

* `Pillow` 在 python-for-android 上需要额外配方，且体积很大；
* `qrcode` 依赖 `Pillow`，所以也装不了。

早期版本直接 `import qrcode`，在手机上当场抛 `ImportError`，而且异常发生在渲染路径上，表现就是**一点扫码就闪退**。

现在改用自带的 `qrgen.py`（纯 Python，只用 `io` / `struct` / `zlib`），自己编码并直接写 PNG。

### 实现要点

| 项 | 说明 |
|---|---|
| 模式 | Byte，纠错等级 M |
| 版本 | 1-10（B站登录 URL 约 100 字符，只需版本 6）|
| 分块 | 支持多块交织，含版本 8+ 的异长块 |
| 版本信息 | 版本 7+ 的 18 位 BCH |
| 掩码 | 8 种全试，按规范罚分选最优 |
| 输出 | 8 位灰度 PNG（无需 Pillow）|

### 验证方式

```bash
python other/android/_qr_test.py     # 逐格对比 + 真实解码
```

该脚本会：

1. 与参考库 `qrcode` 在**全部 8 个掩码**下逐格对比（要求差异 0 格）；
2. 对比罚分函数与其 `lost_point` 是否相等；
3. 用 OpenCV 实际解码，确认真的能扫出来。

### 曾经踩过的坑

1. **版本 8 起各块长度不同**（`[38,38,39,39]`），按“每块等长”写会生成扫不出来的码；
2. **版本 7+ 必须写版本信息**，位序是行优先 `(i//3, i%3)`，写成列优先就错；
3. **格式信息两个副本位序不同**，写反会导致整体扫不出；
4. **罚分规则二**（2×2 同色方块）漏写会选错掩码。

> 小贴士：`cv2.imread()` 读不了含中文的路径，测试脚本里用 `imdecode` + `numpy.frombuffer` 绕过。

---

## 8. 构建 APK

**必须在 Linux 上**（buildozer 不支持 Windows / macOS 原生）。Windows 用 WSL。

```bash
cd other/android
./pack.sh                # debug APK
./pack.sh --release      # release（未签名）
./pack.sh --clean        # 连同 SDK 缓存一起清掉
```

`pack.sh` 会：

1. 把 `core/`、`parsers/` 与 Android 入口复制到暂存区 `.build_stage/`
   （buildozer 的 `source.dir` 不能引用自身目录之外的文件）
2. 一并复制 `qt_compat.py`、中文字体、图标
3. 改写 spec 里的 `source.include_*` 以适配暂存区布局
4. **打包前自检**关键文件是否齐全（缺了直接报错，不必等 40 分钟）
5. 运行 buildozer

产物：`dist/bilidownload-2.2.0-arm64-v8a_armeabi-v7a-debug.apk`

安装：`adb install -r dist/<文件名>.apk`

### 环境依赖

```bash
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    cmake libffi-dev libssl-dev build-essential ccache
pip install --user buildozer cython
```

---

## 9. 从零复现构建时的注意事项

1. **构建路径必须是纯 ASCII**。`buildozer.spec` 里 `source.dir = .`，
   但 p4a 的 `javac` 调用对 Windows 中文路径（本项目的
   `E:\旧桌面备份\来自：电脑桌面\...`）会报
   `Invalid filename` / `file not found`。
   所以构建时先把源码同步到 `$HOME/bili_android_build` 这类纯 ASCII 目录。
2. **主机需要 autoconf / automake / libtool**。没有 root 时可以自行编译一套，
   并把 `PATH`、`PERL5LIB`、`AC_MACRODIR`、`AUTOM4TE_CFG` 指过去。
3. **venv 里的 pip 会被装坏**。`python -m venv venv` 用 ensurepip 装 pip 25.3，
   随后 p4a 的 `pip install -U pip` 覆盖到 26.x 时不清除旧文件，导致
   `ImportError: cannot import name 'BuildDependencyInstallError'`。
   修法：`venv --without-pip`，再用 `ensurepip` 在空的 site-packages 上引导。
4. **pip 对 Android wheel 会误判**。宿主 pip 不认识
   `android_24_arm64_v8a` 平台标签，会把正常的 Android wheel 判为
   `not a supported wheel on this platform`。修法：`pip install --target ...`
   时带 `--platform <tag> --python-version X.Y`。
5. **`lookup_prebuilt()` 的探测命令必须包 `try/except`**。`pip --dry-run`
   对 PyPI 上没有 Android wheel 的包会**非 0 退出**，而 `shprint()` 强制检查
   返回码，会让整个构建中断。
6. **Gradle 需要预置**。`gradlew` 会去 `services.gradle.org` 拉发行包，
   国内常连不上。可从腾讯云镜像下载，解压到
   `~/.gradle/wrapper/dists/gradle-8.14.3-all/<hash>/`，并放好同名
   `.zip` 与 `.zip.ok` 标记文件。
7. **SDK 更新检查要跳过**。buildozer 每次构建都会调 `sdkmanager` 去
   `dl.google.com` 确认 platform-tools / build-tools 是否最新，国内会超时，
   报 `Failed to find package platform-tools` —— 即使本地早已装好。
   spec 里设 `android.skip_update = True` 即可（本机 SDK 已含
   platform-tools、platforms/android-33、build-tools/37.0.0）。
8. **p4a 缓存要软链接到 stage**。buildozer 把平台代码放在
   `<app_dir>/.buildozer/android/platform/`，而不是 `$HOME/.buildozer/`。
   若不链接，它会重新去 GitHub 克隆并失败。链接后还要把 origin 改回
   GitHub 地址，否则 buildozer 判定为"旧地址"而删掉重克隆。
9. **`ffmpeg` / `mp4decrypt` 不随包**。首次运行时按需下载
   （设置 Tab → 下载工具）。

---

## 10. 自检

不需要装 Kivy、也不需要连手机就能验证大部分正确性：

```bash
# 桌面核心能否在无 PyQt5 环境下导入（模拟 Android）
python other/android/_test_shim.py

# 界面能否真正构建出来（KV 语法 / 控件 / 中文字体 / URL 解析）
python other/android/_render_test.py

# 打包会不会漏文件
python other/android/_check_pack.py

# 官方测试套件（含 Android 接口一致性）
python other/common/tests/test_android_bridge.py
python other/common/tests/test_platform.py
python other/common/tests/test_tools.py
python other/common/tests/test_bootstrap.py
```

`_render_test.py` 会用真实的（隐藏）窗口构建一遍全部界面，
能抓出 KV 拼写错误、控件属性错误、字体缺字等问题，
**不必等 40 分钟的 APK 构建**才发现。

> 注意：这些 `_` 开头的脚本是开发期工具，**不会**被打进 APK
> （`pack.sh` 只复制白名单文件）。
