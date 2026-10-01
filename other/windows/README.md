# Windows 打包脚本

原 `build.py` 在项目重构时被归档到 `_整理/`，根目录一度没有可用的 Windows 打包脚本。
这里补齐完整流水线（各步骤与历史行为一致，已在 V2.2.1 实测通过）。

## 环境要求

- Python 3.10（`D:\Python3.10`），已装 PyInstaller + 全部运行依赖
  （PyQt5 / requests / curl_cffi / qrcode / Pillow / psutil / cryptography / pywin32 / browser-cookie3 / pycryptodome / orjson）
- `version_info.win` 必须存在（不入库，打包时用）
- 工具源：`ffmpeg/bin/`、`mpv/`、`bento4/*/bin/`、`upx_tool/upx.exe`

## 完整流水线

```bash
# 0) 版本一致性自检（必做，改过版本号后尤其重要）
python .github/ci_checks.py

# 1) 主程序（完整版，含 PyQt5）
python -m PyInstaller BilibiliDownloader.spec --noconfirm \
    --distpath=dist_win --workpath=build_win

# 2) 卸载程序
python -m PyInstaller uninstaller.spec --noconfirm \
    --distpath=dist_win --workpath=build_win_un

# 3) 证书安装器
python -m PyInstaller cert_installer.spec --noconfirm \
    --distpath=output --workpath=build_win_cert

# 4) 精简版（剥离 PyQt5，供云端/绿色版；入口 boot.py）
python other/windows/build_lean.py

# 5) 组装 + 打完整包 zip（含 ffmpeg/mpv/bento4）
python other/windows/build_main.py --no-upx

# 6) 打云端精简包 zip
python other/windows/build_main.py --lean

# 7) 安装程序（在线版 / 内嵌版）
python -m PyInstaller 2.2.1_installer.spec --noconfirm \
    --distpath=output --workpath=build_win_inst
python -m PyInstaller 2.2.1_installer_embedded.spec --noconfirm \
    --distpath=output --workpath=build_win_inst_emb
```

> 第 1、7 步的 spec 文件名带版本号（`2.2.1_installer.spec`），升版本时要同步改名。

## 产物（`output/`）

| 文件 | 说明 |
|---|---|
| `BilibiliDownloader_<ver>.zip` | 云端精简包：无 PyQt5 / ffmpeg / bento4，仅 mpv；首次启动由 `pyqt5_bootstrap` 补装 |
| `BilibiliDownloader_<ver>_full.zip` | 完整包：含 ffmpeg / mpv / bento4 |
| `<ver>_installer.exe` | 在线安装程序，从云端下载 |
| `<ver>_installer_embedded.exe` | 内嵌安装程序，包体已含完整包 zip |
| `cert_installer.exe` | 证书安装器 |

## 注意

- **UPX**：`--no-upx` 是推荐做法。ffmpeg/ffprobe 单个约 100MB，UPX -9 压缩极慢；
  不加 `--no-upx` 会走压缩流程（耗时可能 10 分钟以上）。
- **证书**：`BilibiliDownloader_dev.cer` 由 `sign_exes.ps1` 生成，缺失时脚本会跳过（不影响打包）。
- **压缩包内容**：打 zip 时会排除 `cookie.txt`、`app_config.json`、`client_id.txt`、
  `download_history.json`、`data_consent.json` 等运行时状态，避免把用户凭据打进发布包。
- **精简包校验**：`build_main.py --lean` 会主动确认 `_internal` 下没有 PyQt5 / ffmpeg / bento4，
  发现残留会直接移除。
- `dist/` 被 `other/linux/build.sh` 占用（Linux 构建），Windows 完整版请用 `dist_win/`。

---

## 内测包（beta 通道）

一条命令跑完全流程：

```bash
python other/windows/build_beta.py                 # 完整（含 321MB 内嵌安装器）
python other/windows/build_beta.py --skip-embedded # 跳过内嵌安装器
python other/windows/build_beta.py --only main     # 只跑某一步，调试用
```

脚本会自动把 `core/app_config.py` 的 `IS_BETA_BUILD` 置为 `True`，**结束后（含异常/中断）
无条件还原**，不会把内测开关提交进仓库。

产物全部落在 `*_beta` 目录，**不覆盖正式包**：

| 文件 | 说明 |
|---|---|
| `dist_beta/BilibiliDownloader/` | 完整程序目录 |
| `dist_beta/_lean/BilibiliDownloader/` | 精简程序目录 |
| `output_beta/BilibiliDownloader_<ver>_full.zip` | 完整包 |
| `output_beta/BilibiliDownloader_<ver>.zip` | 精简包 |
| `output_beta/<ver>_installer.exe` | 在线安装器 |
| `output_beta/<ver>_installer_embedded.exe` | 内嵌安装器 |
| `output_beta/cert_installer.exe` | 证书安装器 |

### 内测包与正式包的差异

**只有 `IS_BETA_BUILD` 这一个开关**，它控制两件事：

1. 启动时弹 `BetaAuthDialog` 要求输入授权 QQ，校验通过才继续（`ui.py:_check_beta_auth`）
2. 更新检查用 `channel="beta"` 而非 `"stable"`（`ui.py:_check_cloud_info`）

### 服务端注册（不做这一步，内测用户收不到更新）

`app_version` 表的 `version` 列是**单列 UNIQUE**，且版本号被正则限死为纯 `x.y.z`。
所以「同一版本号既是 stable 又是 beta」在数据库层面做不到，必须二选一：

- 内测号取**更高**的版本号（如正式 2.2.1 + 内测 2.2.2）→ 两通道共存，互不影响
- 或者内测先占用 2.2.1，验证通过后把该行 `channel` 从 `beta` 改成 `stable`

注册字段：

| 字段 | 值 |
|---|---|
| version | 内测版本号（纯 x.y.z） |
| channel | `beta` |
| platform | `windows` |
| **download_url** | 指向 `BilibiliDownloader_<ver>_full.zip` |
| file_size / sha256 / release_notes | 按需 |

> **`download_url` 必须指向 full.zip，不能填 installer.exe。**
> 因为安装器会用 `type=installer&version=<ver>` 反过来查这个字段，
> 拿到后按 zip 解包（`installer.py:extract_package`）。填 exe 会导致安装器解包失败。

让用户进入 beta 通道有**两条独立路径**：

1. **客户端侧**：装内测包（`IS_BETA_BUILD=True`），无条件请求 beta 通道 —— 但启动需 QQ 授权
2. **服务端侧**：把设备 `client_id` 加进 `beta_tester` 表（后台 `beta_testers.php`），
   `/check` 会自动把该设备切到 beta 通道 —— **正式包也能收到内测更新**

授权 QQ 名单在后台 `beta_auth.php` 维护（支持单个添加 / 批量添加 / 解绑设备）。

### ⚠️ 已知坑：COLLECT 被批量删除保护拦下

**重复构建到同一个 distpath 时，PyInstaller 的 COLLECT 会先删掉同名输出目录。**
目录里文件较多（2500+）时会触发沙箱的批量删除保护：

```
INFO: Removing dir ...\dist_beta\BilibiliDownloader
[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED] {"count":2514,"threshold":50,...}
```

删除被拒 → COLLECT 中断 → **distpath 里留着的是上一次的旧产物，而构建过程返回 0**。

判据：`workpath/<name>/COLLECT-00.toc` 不存在就是没跑完。

`build_beta.py` 已内置规避：调 PyInstaller 前先 `move_aside()` 把旧目录**改名让开**
（rename 不受删除限制），并在构建后断言产物目录存在。
手动敲 PyInstaller 命令时若遇到这个现象，同样先手动改名，或先清空 distpath。

> 首次在全新目录构建不会触发，所以这个问题往往在「第二次构建」才暴露，
> 极易误判为「代码改动没生效」。


