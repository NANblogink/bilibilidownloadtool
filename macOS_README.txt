# B站视频解析工具 macOS 适配版

## macOS 使用说明

### 环境要求
- macOS 10.14+ (Mojave 或更高版本)
- Python 3.7+
- FFmpeg
- Bento4 (mp4decrypt)

### 快速安装

#### 1. 安装 Homebrew（如未安装）
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

#### 2. 安装 Python3 和依赖
```bash
brew install python3
pip3 install PyQt5 requests aiohttp pycryptodome brotli orjson qrcode Pillow browser-cookie3 PyQtWebEngine
```

#### 3. 安装 FFmpeg 和 Bento4
```bash
brew install ffmpeg
brew install bento4
```

#### 4. 启动程序
```bash
chmod +x start_mac.sh
./start_mac.sh
```

或者直接运行：
```bash
python3 main.py
```

### 使用本地 FFmpeg/Bento4

如果你不想使用 Homebrew 安装，也可以手动放置二进制文件：

```
bilibilidownloadtool-mac/
├── ffmpeg/
│   └── bin/
│       ├── ffmpeg          # macOS 版 ffmpeg 二进制文件
│       ├── ffprobe         # macOS 版 ffprobe 二进制文件
│       └── ffplay          # 可选
├── bento4/
│   └── bin/
│       ├── mp4decrypt      # macOS 版 mp4decrypt 二进制文件
│       ├── mp4dump
│       └── mp4info
├── main.py
└── ...
```

注意：macOS 二进制文件需要具有执行权限：
```bash
chmod +x ffmpeg/bin/ffmpeg
chmod +x ffmpeg/bin/ffprobe
chmod +x bento4/bin/mp4decrypt
```

### macOS 适配说明

本版本已做以下跨平台适配：

1. **工具路径检测**：自动检测系统 PATH 中的 ffmpeg/mp4decrypt，优先使用 Homebrew 安装的版本
2. **字体适配**：macOS 使用 PingFang SC 字体替代 Microsoft YaHei
3. **配置路径**：配置文件存储在 `~/Library/Application Support/BilibiliDownloadTool/`
4. **数据路径**：工具文件存储在 `~/Library/Application Support/BilibiliDownloadTool/`
5. **权限管理**：macOS 使用 osascript 请求管理员权限
6. **环境变量**：PATH 配置写入 ~/.zshrc 或 ~/.bash_profile
7. **代理检测**：支持 macOS 系统代理设置检测
8. **热更新**：支持 macOS 的 bash 更新脚本
9. **文件权限**：自动为二进制文件设置执行权限

### 已知限制

- `installer.py` 和 `uninstaller.py` 仅适用于 Windows，macOS 不需要
- HEVC 扩展安装功能仅适用于 Windows，macOS 原生支持 HEVC
- `tkinterdnd2` 拖放功能在 macOS 上可能不可用，视频转换工具仍可通过浏览按钮选择文件
- `browser_cookie3` 在 macOS 上可能需要额外权限访问浏览器 Cookie

### 打包为 macOS 应用

使用 PyInstaller 打包：
```bash
pip3 install pyinstaller
pyinstaller --name "BilibiliDownloader" \
    --windowed \
    --onedir \
    --icon logo.icns \
    --add-data "ffmpeg:ffmpeg" \
    --add-data "bento4:bento4" \
    main.py
```

### 下载路径

默认下载路径为 `~/BilibiliDownloads`，可在设置中修改。
