# 跨平台适配（Linux / macOS / Android）

本目录存放 Windows 之外三个平台的启动器、打包配置与文档。

> 桌面版（Windows）的代码是**唯一主干**。Linux / macOS 复用同一套源码，
> 只在 `core/infra/platform_utils.py` 里按平台分支；
> Android 因 PyQt5 不支持该平台，界面层用 Kivy 重写，业务层与桌面版同源。

---

## 目录结构

```
other/
├── README.md                  本文件
├── common/                    三平台共用
│   ├── requirements.txt       Python 依赖（PyQt5 系）
│   ├── doctor.py              环境自检脚本（排查"跑不起来"）
│   ├── check_threads.py       非守护线程静态检查（防退出挂起）
│   └── tests/                 跨平台行为测试
├── linux/
│   ├── run.sh                 启动器
│   ├── install.sh             安装到 ~/.local 或 /opt
│   ├── build.sh               PyInstaller 打包
│   ├── pack.sh                生成 tar.gz 分发包（推荐）
│   ├── BilibiliDownloader.spec  打包配置（Linux/macOS 共用）
│   └── bilibili-downloader.desktop  桌面菜单项
├── macos/
│   ├── run.sh                 启动器（自动建 venv）
│   ├── build.sh               生成 .app
│   ├── pack.sh                生成 .dmg + .zip（推荐）
│   └── BilibiliDownloader.spec  复用 linux 的 spec
└── android/
    ├── main_kivy.py           Kivy 界面入口
    ├── buildozer.spec         APK 打包配置
    └── pack.sh                生成 APK（仅在 Linux 上可用）
```

---

## 打包安装包

> Windows 安装包请用仓库根目录下你自己的 `setup.iss`（Inno Setup），
> 本节只讲 Linux / macOS / Android 三个平台。

### Linux —— 生成 tar.gz 分发包

在 Linux 上（或 WSL）：

```bash
cd other/linux
./pack.sh
```

产物在 `dist/`：

| 文件 | 说明 |
|---|---|
| `dist/BilibiliDownloader/` | 绿色版目录，可直接运行 |
| `dist/BilibiliDownloader-linux-x86_64.tar.gz` | 分发包（约 226MB）|

用户拿到后的用法：

```bash
tar -xzf BilibiliDownloader-linux-x86_64.tar.gz
cd BilibiliDownloader
./BilibiliDownloader        # 或 ./run.sh
```

包内已附 `启动说明.txt`（含缺库时的安装命令）与 `install.sh`（装桌面菜单项）。

`pack.sh` 会在打包后自动做一次 offscreen 启动自检，
确认无导入错误才出包；并用快照复制避免 `tar: file changed as we read it`。

### macOS —— 生成 .dmg / .zip

**必须在 macOS 上运行**（PyInstaller 不能跨平台出 `.app`）：

```bash
cd other/macos
./pack.sh                 # .app + .dmg + .zip
./pack.sh --no-dmg        # 只要 .app + .zip
./pack.sh --arch arm64    # 指定架构（默认当前机器架构）
```

产物：

| 文件 | 说明 |
|---|---|
| `dist/B站视频解析工具.app` | 应用包 |
| `dist/B站视频解析工具-2.2.0-macOS-arm64.dmg` | 分发镜像 |
| `dist/B站视频解析工具-2.2.0-macOS-arm64.zip` | 备用（用 `ditto` 保留了权限位）|

未签名，首次打开需右键 → 打开，或 `xattr -cr "B站视频解析工具.app"`。
包内 `Contents/Resources/启动说明.txt` 已写明这些步骤。

### Android —— 生成 APK

> **详细说明见 [`other/android/README.md`](android/README.md)**：界面为什么重写、
> `qt_compat.py` 兼容层如何让桌面引擎在无 PyQt5 环境运行、中文字体与图标怎么生成、
> 强制竖屏的配置项、功能对照表、以及从零复现构建的全部坑位。

**必须在 Linux 上运行**（buildozer 不支持 Windows/macOS 原生）：

```bash
cd other/android
./pack.sh                 # debug APK
./pack.sh --release       # release APK（未签名）
```

产物：`dist/bilidownload-2.2.0-*.apk`

安装到设备：`adb install -r dist/<文件名>.apk`

#### 已构建好的 APK

`other/android/bilidownload-2.2.0-arm64-v8a_armeabi-v7a-debug.apk`
（约 48 MB，内含 `arm64-v8a` + `armeabi-v7a` 双架构）：

| 项目 | 值 |
|---|---|
| 包名 | `cn.bilidown.bilidownload` |
| 版本 | 2.2.0 |
| minSdk / targetSdk | 24 / 33 |
| ABI | arm64-v8a, armeabi-v7a |
| Python | 3.14 |
| SHA256 | `9e1e2c8777b1f00711b4b61472e7dc94a333e42fc089e9d25eb33bda85ec5d62` |

```bash
adb install -r other/android/bilidownload-2.2.0-arm64-v8a_armeabi-v7a-debug.apk
```

> 这是 **debug** 包（debug 签名，可直接侧载）。要上架需自行配置 release
> 签名，见 `buildozer.spec` 中 `[app]` 段的 `android.release_*` 注释。

#### 从零复现构建时的注意事项

本项目在 buildozer 上踩到的坑（按遇到顺序），复现卡住时可对照排查：

1. **构建路径必须是纯 ASCII**。p4a 内部有 `javac` 调用，中文路径会被
   WSL 的编码转换毁掉（`Invalid filename` / `file not found`）。
   必须先把源码复制到 `$HOME/xxx` 这类纯 ASCII 目录再构建。
2. **主机需要 autoconf / automake / libtool**。没有 root 时可以
   `./configure --prefix=$HOME/hosttools/root` 自行编译一套，并把
   `PATH`、`PERL5LIB`、`AC_MACRODIR`、`AUTOM4TE_CFG` 指过去；
   `aclocal` / `automake` / `libtoolize` 的脚本 shebang 与内置
   `@prefix@` 路径都要改写成实际安装路径。
3. **venv 里的 pip 会被装坏**。`python -m venv venv` 用 ensurepip
   装 pip 25.3，随后 p4a 的 `pip install -U pip` 覆盖到 26.x 时
   不清除旧文件，导致
   `ImportError: cannot import name 'BuildDependencyInstallError'`。
   修法：用 `venv --without-pip` 建环境，再用 `ensurepip` 在空的
   site-packages 上引导。
4. **p4a 用宿主 pip 校验 Android wheel 会误判**。wheel 标签是
   `android_24_arm64_v8a`，宿主 pip 只认本机标签，会报
   `not a supported wheel on this platform`。修法：给最终的
   `pip install --target` 补上 `--platform <tag> --python-version X.Y`。
5. **p4a 的 PyPI 预编译探测会中断构建**。`lookup_prebuilt()` 里的
   `pip --dry-run` 对 PyPI 上没有 Android wheel 的包（如
   `pycryptodome`）会非 0 退出，而 `shprint()` 强制 `_bg=True`，
   异常在后台线程抛出、绕过了外层 `try/except`。修法：该探测改为
   直接调 pip 并接收任意退出码。
6. **Gradle 需要预置**：国内常连不上官方源，需要提前下好 Gradle。
   下载 `https://mirrors.cloud.tencent.com/gradle/gradle-8.14.3-all.zip`
   解压到 `~/.gradle/wrapper/dists/gradle-8.14.3-all/<hash>/`，并放好同名 `.zip` 与 `.zip.ok` 标记文件。
7. **`ffmpeg` 等外部工具不随包**。Android 端与 Linux/macOS 一样，
   首次运行时按需下载（见下文「随包二进制」）。

> **重要**：buildozer 的 `source.dir` 不能引用自身目录之外的文件，
> 所以 `pack.sh` 会先把 `core/`、`parsers/` 与 Android 入口
> **复制到一个临时暂存区**（`.build_stage/`），在那里跑 buildozer。
> 暂存区用完即删，不污染源码树。
>
> 首次构建会自动下载 Android SDK/NDK（数 GB），耗时可能 30 分钟以上。

依赖（Ubuntu/Debian）：

```bash
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    cmake libffi-dev libssl-dev build-essential ccache
pip install --user buildozer cython
```

### 用 GitHub Actions 自动出包

三个平台的打包任务已配置在 `.github/workflows/MultiPlatform.yml`：

- 在 GitHub 上手动触发（Actions → Multi-Platform CI → Run workflow）
- 或推一个 tag，例如 `git tag v2.2.0 && git push --tags`

三个平台并行打包，产物自动上传为 Artifacts：
`linux-tarball` / `macos-dmg` / `macos-zip` / `android-apk`。

---

## 快速开始

### Linux

```bash
cd other/linux
./run.sh --debug          # 直接运行（前台看日志）
./install.sh              # 安装到 ~/.local（无需 root）
./install.sh --system --with-deps   # 装到 /opt 并装系统 Qt 依赖
```

首次运行缺依赖时，`run.sh` 会自动读取 `other/common/requirements.txt` 安装。

### macOS

```bash
cd other/macos
./run.sh --debug          # 直接运行（首次自动建 .venv 并装依赖）
./build.sh                # 生成 dist/B站视频解析工具.app
./build.sh --dmg          # 再生成 .dmg
```

未签名的 `.app` 首次打开需**右键 → 打开**；若提示"已损坏"：

```bash
xattr -cr "dist/B站视频解析工具.app"
```

### Android

Android 必须用 Linux 主机打包（buildozer 不支持 Windows）。

```bash
# 在 Linux 上（或 WSL，需 sudo）
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    cmake libffi-dev libssl-dev
pip install --user buildozer cython

cd other/android
buildozer -v android debug     # 产物在 bin/*.apk
```

---

## 平台差异说明

### 功能一致性

| 功能 | Windows | Linux | macOS | Android |
|---|---|---|---|---|
| 链接解析（投稿/番剧/合集/课堂/直播） | ✅ | ✅ | ✅ | ✅ |
| 清晰度选择 / DASH 解析 | ✅ | ✅ | ✅ | ✅ |
| 并发下载 / 断点续传 | ✅ | ✅ | ✅ | ✅ |
| 音视频合并（ffmpeg） | ✅ | ✅ | ✅ | ✅ |
| GPU 硬编（NVENC/AMF/QSV） | ✅ | ✅ | ✅ | — |
| DRM 解密（mp4decrypt） | ✅ | ✅ | ✅ | ✅ |
| 登录（密码/二维码/短信/Cookie） | ✅ | ✅ | ✅ | ✅ |
| 内嵌播放器（mpv） | ✅ | ✅ | ✅ | — |
| 系统托盘 | ✅ | ✅ | ✅ | — |
| 桌面通知 | ✅ WinRT | ✅ notify-send | ✅ 通知中心 | ✅ 通知栏 |
| 下载完成后关机 | ✅ | ✅ | ✅ | — |
| 自动更新 | ✅ | ✅ | ✅ | — |

「—」表示该平台本身没有对应概念（如手机没有"关机"和"托盘"），
程序会自动隐藏或降级，不会报错。

### 界面一致性

- **Linux / macOS**：与 Windows **完全一致** —— 同一份 `ui.py`（PyQt5），
  仅字体与文件管理器调用按平台切换。
- **Android**：PyQt5 **没有** Android 版本，无法原样移植。
  Android 端用 Kivy 重写界面，**信息架构、配色（主色 #00a1d6）、
  操作流程**与桌面版对齐，但受限于两套渲染框架，不是像素级一致。

---

## 打包说明

### 随包二进制（ffmpeg / mp4decrypt / mpv）

仓库里默认**只带 Windows 版**（`ffmpeg.exe` 等），因为：

- Linux/macOS 的 ffmpeg 二进制体积大（各约 100MB+），不适合进 git
- 各平台/架构（x86_64 / arm64）需要的版本不同

因此 Linux / macOS 上改为**首次运行时按需下载**：

1. 程序内「设置 → 工具」→ 一键下载对应平台版本
2. 或手动放置：
   ```
   ffmpeg/bin/ffmpeg         ffmpeg/bin/ffprobe
   bento4/bin/mp4decrypt
   ```
3. 或直接用系统的：`sudo apt install ffmpeg` / `brew install ffmpeg`

`tool_manager.py` 已按平台选择正确的下载源与解压方式
（Windows/macOS 用 `.zip`，Linux 用 `.tar.xz`）。

---

## 环境自检

任何平台跑不起来时，先执行：

```bash
python other/common/doctor.py
```

它会逐项检查 Python 版本、依赖、平台识别、Qt 插件、
外部工具、平台 API、以及源码里是否残留未加保护的 Windows 调用，
并给出具体的修复命令。

---

## 常见问题

### Linux: `could not load the Qt platform plugin "xcb"`

缺 Qt 运行库：

```bash
# Debian / Ubuntu
sudo apt install -y libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
  libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 \
  libxcb-xkb1 libxkbcommon-x11-0 libgl1 libegl1

# Fedora
sudo dnf install -y xcb-util-wm xcb-util-image xcb-util-keysyms \
  xcb-util-renderutil libxkbcommon-x11 mesa-libGL
```

### Linux: 关闭窗口后进程不退出

这是**非守护线程**导致的，本项目已修复并用
`python other/common/check_threads.py` 做静态防护。
若你改动了线程代码，请跑一遍这个脚本。

### Linux: 没有声音提示 / 没有通知

```bash
sudo apt install -y libnotify-bin
```

### macOS: 提示"无法打开，因为来自身份不明的开发者"

右键 → 打开；或 `xattr -cr <app>`。这是未签名应用的正常提示，
不影响功能。

### Android: 提示缺少 NDK / SDK

buildozer 首次运行会自动下载（需要数 GB 空间与较长时间）。
建议先前置设置：

```bash
export ANDROID_HOME=$HOME/.buildozer/android/platform/android-sdk
```

### 代理相关问题

B站是国内站点，程序已自动清除代理环境变量并设置 `NO_PROXY=*`。
若你的环境必须走代理才能上网，请自行修改 `main.py` 顶部的清理逻辑。

---

## 验证状态

本适配经过以下验证（截至提交时）：

| 项目 | Windows | Linux(WSL) | macOS | Android |
|---|---|---|---|---|
| 全量语法编译 | ✅ | ✅ | CI | ✅(静态) |
| 模块导入 | ✅ | ✅ | CI | ✅(静态) |
| 主窗口构建 + 事件循环 | ✅ | ✅ | CI | — |
| PyInstaller 打包并运行 | ✅ | ✅ | CI | — |
| 平台 API 测试 | ✅ | ✅ | CI | ✅ |
| 非守护线程检查 | ✅ | ✅ | CI | ✅ |

- **macOS**：通过 `.github/workflows/MultiPlatform.yml` 在 GitHub 的
  macOS runner 上验证（本机为 Windows，无法本地跑）。
- **Android**：本机无法安装 Kivy（从源码编译会打满 CPU），
  因此用 `other/common/tests/test_android_bridge.py` 校验
  Android 层与桌面核心的**接口契约**（符号是否存在、
  `download_params` 的键是否与 `DownloadManager.start_download()`
  实际读取的一致、有无 PyQt5 混入）。
  **真机运行需自行验证**。
