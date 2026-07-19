#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频解析工具 安装程序
注意: 此安装程序仅适用于 Windows 平台
macOS 用户请直接运行 python main.py 或使用 Homebrew 安装依赖
"""
import sys
if sys.platform != 'win32':
    print("此安装程序仅适用于 Windows 平台")
    print("macOS 用户请直接运行: python main.py")
    print("建议先安装依赖: brew install ffmpeg bento4")
    sys.exit(1)

import os
import sys
import tempfile
import shutil
import traceback
import webbrowser
import zipfile
import requests
import threading

import winreg
from PyQt5.QtWidgets import (
    QApplication, QWizard, QWizardPage, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox,
    QProgressBar, QMessageBox, QGroupBox, QFormLayout, QTextEdit,
    QScrollArea, QTextBrowser
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor, QIcon

from app_config import (
    APP_NAME, APP_NAME_EN, APP_VERSION, VERSION_NUM,
    APP_DESCRIPTION, APP_WEBSITE, APP_REPO,
    SHORTCUT_NAME, CLOUD_DOWNLOAD_URLS, is_safe_install_path
)

APP_EXE = APP_NAME_EN + ".exe"
UNINSTALLER_EXE = "uninstaller.exe"
REG_KEY = r"Software\BilibiliDownloadTool"


def markdown_to_html(text):
    import re
    text = re.sub(r'### (.+)', r'<h3>\1</h3>', text)
    text = re.sub(r'## (.+)', r'<h2>\1</h2>', text)
    text = re.sub(r'# (.+)', r'<h1>\1</h1>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" style="color:#00a1d6">\1</a>', text)
    text = text.replace('---', '<hr>')
    lines = text.split('\n')
    result = []
    in_list = False
    for line in lines:
        if line.startswith('- '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append('<li>' + line[2:] + '</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')
    text = '\n'.join(result)
    text = text.replace('\n\n', '</p>\n<p>')
    return '<html><body style="font-family:Microsoft YaHei;font-size:13px;color:#333;line-height:1.6"><p>' + text + '</p></body></html>'


class InstallerThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, install_path, create_desktop, create_startmenu, package_path=None):
        super().__init__()
        self.install_path = install_path
        self.create_desktop = create_desktop
        self.create_startmenu = create_startmenu
        self.package_path = package_path
        self._cancelled = False

    def cancel(self):
        """请求取消安装"""
        self._cancelled = True

    def run(self):
        try:
            self.log_signal.emit("正在准备安装...")
            self.progress_signal.emit(0, 100)
            if self.package_path and os.path.exists(self.package_path):
                # 有内嵌包，直接使用（离线模式）
                self.log_signal.emit("使用本地安装包...")
                self.extract_package(self.package_path)
            else:
                # 无内嵌包，从云端下载
                self.log_signal.emit("本地未找到安装包，将从云端下载...")
                zip_path = self.download_from_cloud()
                if zip_path:
                    self.extract_package(zip_path)
                    # 下载的临时文件，安装后清理
                    try:
                        os.remove(zip_path)
                    except Exception:
                        pass
                else:
                    self.finished_signal.emit(False, "无法获取安装包：云端下载失败且本地无安装包")
        except Exception as e:
            self.log_signal.emit("安装失败：" + str(e))
            self.finished_signal.emit(False, str(e))

    def download_from_cloud(self):
        """从云端下载安装包，返回本地zip路径，失败返回None"""
        import requests as req

        session = req.Session()
        session.headers.update({
            'User-Agent': f'BilibiliDownloader-Installer/{APP_VERSION}'
        })

        for url in CLOUD_DOWNLOAD_URLS:
            try:
                self.log_signal.emit(f"正在从云端获取下载链接...")
                self.progress_signal.emit(2, 100)

                # 解析实际下载URL
                actual_url = self._resolve_download_url(session, url)
                if not actual_url:
                    continue

                self.log_signal.emit(f"正在下载安装包: {actual_url[:80]}...")
                self.progress_signal.emit(5, 100)

                # HEAD请求获取文件大小
                total_size = 0
                try:
                    head_resp = session.head(actual_url, timeout=(10, 15), allow_redirects=True)
                    if head_resp.status_code == 200:
                        total_size = int(head_resp.headers.get('content-length', 0))
                except Exception:
                    pass

                if total_size > 0:
                    self.log_signal.emit(f"安装包大小: {total_size / 1024 / 1024:.1f} MB")

                resp = session.get(actual_url, stream=True, timeout=(10, 30), allow_redirects=True)
                resp.raise_for_status()

                if total_size <= 0:
                    total_size = int(resp.headers.get('content-length', 0))

                temp_dir = tempfile.gettempdir()
                zip_path = os.path.join(temp_dir, f"BilibiliDownloader_{APP_VERSION}.zip")
                downloaded = 0
                chunk_size = 65536
                last_progress = 5

                with open(zip_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=chunk_size):
                        if self._cancelled:
                            f.close()
                            try:
                                os.remove(zip_path)
                            except Exception:
                                pass
                            self.log_signal.emit("下载已取消")
                            return None
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                pct = int(5 + 45 * downloaded / total_size)
                                if pct != last_progress and pct <= 50:
                                    last_progress = pct
                                    self.progress_signal.emit(pct, 100)
                                if downloaded % (5 * 1024 * 1024) < chunk_size:
                                    self.log_signal.emit(
                                        f"下载进度: {downloaded / 1024 / 1024:.1f}/{total_size / 1024 / 1024:.1f} MB"
                                    )

                # 验证下载文件
                file_size = os.path.getsize(zip_path)
                if file_size < 1024 * 1024:
                    self.log_signal.emit(f"下载文件过小({file_size}字节)，可能不是有效安装包")
                    try:
                        os.remove(zip_path)
                    except Exception:
                        pass
                    continue

                # 验证是否为有效zip
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zf:
                        file_count = len(zf.namelist())
                        if file_count < 10:
                            raise Exception("zip文件内容过少")
                        self.log_signal.emit(f"下载完成，验证通过（{file_count} 个文件）")
                except Exception as ze:
                    self.log_signal.emit(f"下载文件不是有效的zip: {ze}")
                    try:
                        os.remove(zip_path)
                    except Exception:
                        pass
                    continue

                return zip_path

            except req.exceptions.Timeout:
                self.log_signal.emit(f"下载超时，尝试下一个源...")
                continue
            except req.exceptions.ConnectionError:
                self.log_signal.emit(f"连接失败，尝试下一个源...")
                continue
            except Exception as e:
                self.log_signal.emit(f"下载失败: {e}")
                continue

        return None

    def _resolve_download_url(self, session, url):
        try:
            if 'bilidown.cn' in url:
                # 自建API check接口：获取安装包下载链接
                self.log_signal.emit("正在查询自建API获取下载地址...")
                resp = session.get(url, timeout=(10, 30))
                if resp.status_code == 200:
                    data = resp.json()
                    # 打印实际返回内容便于诊断（截断避免过长）
                    raw_preview = str(data)[:500]
                    self.log_signal.emit(f"API原始响应: {raw_preview}")
                    # 兼容多种 code 格式（整数0 / 字符串"0" / True 等）
                    code_val = data.get('code')
                    if code_val in (0, '0', '0000', True, 'true', 'success', 'ok'):
                        d = data.get('data', {})
                        dl_url = d.get('download_url') or d.get('url')
                        if isinstance(dl_url, dict):
                            dl_url = dl_url.get('url') or dl_url.get('download_url') or dl_url.get('data')
                        if dl_url:
                            if isinstance(dl_url, str) and not dl_url.startswith('http'):
                                dl_url = 'https://www.bilidown.cn' + dl_url
                            file_size = d.get('file_size', 0)
                            size_str = f"{file_size / 1024 / 1024:.0f} MB" if file_size > 0 else "未知"
                            self.log_signal.emit(f"API返回下载地址 (大小: {size_str})")
                            return dl_url
                    else:
                        self.log_signal.emit(f"API返回 code={code_val} (期望 0)，尝试从响应中直接提取 URL...")
                        # 兜底：尝试直接从整个响应中找到 URL
                        import re as _re
                        text = str(data)
                        urls_found = _re.findall(r"https?://[^\s\x22\x27]+\.(?:zip|exe|7z|rar)[^\s\x22\x27]*", text)
                        for u in urls_found:
                            self.log_signal.emit(f"兜底提取到 URL: {u[:100]}")
                            return u
                self.log_signal.emit(f"自建API请求失败: HTTP {resp.status_code}, body={resp.text[:300] if hasattr(resp,'text') else ''}")
                return None

            else:
                return url

        except Exception as e:
            self.log_signal.emit(f"解析下载链接失败: {e}")
            return None

    def extract_package(self, package_path):
        try:
            self.log_signal.emit("正在解压文件...")
            self.progress_signal.emit(5, 100)
            if not os.path.exists(self.install_path):
                os.makedirs(self.install_path)

            # 覆盖安装：先备份用户数据
            is_overwrite = os.path.isdir(self.install_path) and any(
                os.path.exists(os.path.join(self.install_path, f))
                for f in PRESERVE_FILES + PRESERVE_DIRS
            )
            temp_backup = None
            if is_overwrite:
                temp_backup = tempfile.mkdtemp(prefix='bdt_backup_')
                self.log_signal.emit("检测到覆盖安装，正在备份用户数据...")
                for fname in PRESERVE_FILES:
                    src = os.path.join(self.install_path, fname)
                    if os.path.isfile(src):
                        shutil.copy2(src, os.path.join(temp_backup, fname))
                        self.log_signal.emit(f"  备份: {fname}")
                for dname in PRESERVE_DIRS:
                    src = os.path.join(self.install_path, dname)
                    if os.path.isdir(src):
                        dst = os.path.join(temp_backup, dname)
                        shutil.copytree(src, dst)
                        self.log_signal.emit(f"  备份目录: {dname}/")

            # 清空安装目录（保留的用户数据已备份）
            if is_overwrite:
                self.log_signal.emit("正在清理旧版本文件...")
                for item in os.listdir(self.install_path):
                    item_path = os.path.join(self.install_path, item)
                    # 跳过保留的文件/目录（它们会被新文件覆盖，之后从备份恢复）
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception as e:
                        self.log_signal.emit(f"  清理跳过: {item} ({e})")

            file_size = os.path.getsize(package_path)
            self.log_signal.emit("安装包大小: %.1f MB" % (file_size / 1024 / 1024))
            with zipfile.ZipFile(package_path, 'r') as z:
                total_files = len(z.namelist())
                self.log_signal.emit("共 %d 个文件" % total_files)
                for i, name in enumerate(z.namelist()):
                    target = os.path.join(self.install_path, name)
                    # 跳过保留文件（不解压覆盖，后面从备份恢复）
                    basename = os.path.basename(name)
                    skip = False
                    for pf in PRESERVE_FILES:
                        if name.endswith(pf) or basename == pf:
                            skip = True
                            break
                    for pd in PRESERVE_DIRS:
                        if name.startswith(pd + '/') or name.startswith(pd + '\\') or name == pd:
                            skip = True
                            break
                    if not skip:
                        z.extract(name, self.install_path)
                    if self._cancelled:
                        self.log_signal.emit("安装已被取消")
                        self.finished_signal.emit(False, "用户取消安装")
                        return
                    if i % 200 == 0:
                        progress = 5 + int((i / total_files) * 50)
                        self.progress_signal.emit(progress, 100)
                        self.log_signal.emit("解压: %d/%d" % (i, total_files))

            # 恢复用户数据备份
            if temp_backup and os.path.isdir(temp_backup):
                self.log_signal.emit("正在恢复用户数据...")
                for fname in PRESERVE_FILES:
                    src = os.path.join(temp_backup, fname)
                    if os.path.isfile(src):
                        dst = os.path.join(self.install_path, fname)
                        shutil.copy2(src, dst)
                        self.log_signal.emit(f"  恢复: {fname}")
                for dname in PRESERVE_DIRS:
                    src = os.path.join(temp_backup, dname)
                    if os.path.isdir(src):
                        dst = os.path.join(self.install_path, dname)
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                        self.log_signal.emit(f"  恢复目录: {dname}/")
                # 清理临时备份
                try:
                    shutil.rmtree(temp_backup)
                except Exception:
                    pass

            self.log_signal.emit("解压完成")
            self.progress_signal.emit(55, 100)
            self.save_install_path()
            self.progress_signal.emit(60, 100)
            exe_path = self.find_main_exe()
            if not exe_path:
                exe_files = [f for f in os.listdir(self.install_path) if f.endswith('.exe')]
                if exe_files:
                    exe_path = os.path.join(self.install_path, exe_files[0])
                else:
                    raise Exception("未找到可执行文件")
            self.log_signal.emit("主程序: " + os.path.basename(exe_path))
            self.progress_signal.emit(65, 100)
            icon_path = self.find_icon(exe_path)
            if self.create_desktop:
                self.create_shortcut(exe_path, "Desktop", SHORTCUT_NAME, icon_path=icon_path, description=APP_NAME)
                self.log_signal.emit("桌面快捷方式已创建")
            if self.create_startmenu:
                self.create_shortcut(exe_path, "StartMenu", SHORTCUT_NAME, icon_path=icon_path, description=APP_NAME)
                self.log_signal.emit("开始菜单快捷方式已创建")
                uninstaller_path = self.find_uninstaller_exe()
                if uninstaller_path:
                    self.create_shortcut(uninstaller_path, "StartMenu", "卸载" + SHORTCUT_NAME, description="卸载" + SHORTCUT_NAME)
                    self.log_signal.emit("卸载快捷方式已创建")
            self.progress_signal.emit(80, 100)
            self.add_env_paths(exe_path)
            self.progress_signal.emit(90, 100)
            # 自动安装开发者证书到系统（方便后续版本更新不再报"未知发行者"）
            try:
                self._install_dev_cert(exe_path)
            except Exception as cert_e:
                self.log_signal.emit(f"证书自动安装跳过: {cert_e}")
            self.progress_signal.emit(100, 100)
            self.log_signal.emit(APP_NAME + " " + APP_VERSION + " 安装完成")
            self.finished_signal.emit(True, "安装成功")
        except Exception as e:
            self.log_signal.emit("安装失败：" + str(e))
            self.finished_signal.emit(False, str(e))

    def find_main_exe(self):
        for root, dirs, files in os.walk(self.install_path):
            if APP_EXE in files:
                return os.path.join(root, APP_EXE)
        return None

    def find_uninstaller_exe(self):
        for root, dirs, files in os.walk(self.install_path):
            if UNINSTALLER_EXE in files:
                return os.path.join(root, UNINSTALLER_EXE)
        return None

    def find_icon(self, exe_path):
        exe_dir = os.path.dirname(exe_path)
        internal_dir = os.path.join(exe_dir, "_internal")
        search_dirs = [exe_dir, internal_dir]
        for search_dir in search_dirs:
            for icon_name in ['logo.ico', 'logo.png']:
                icon_file = os.path.join(search_dir, icon_name)
                if os.path.exists(icon_file):
                    return icon_file
        return None

    def save_install_path(self):
        try:
            # 写入注册表前再次校验，防止任何路径绕过到达这里
            safe, reason = is_safe_install_path(self.install_path)
            if not safe:
                self.log_signal.emit(f"拒绝写入注册表，路径不安全：{reason}")
                return
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, self.install_path)
            winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, APP_VERSION)
            winreg.CloseKey(key)
            self.log_signal.emit("注册表已写入")
        except Exception as e:
            self.log_signal.emit("写入注册表失败：" + str(e))

    def create_shortcut(self, target_path, location, name, icon_path=None, description=None):
        try:
            import pythoncom
            from win32com.shell import shell
            if location == "Desktop":
                shortcut_dir = os.path.join(os.path.expanduser('~'), 'Desktop')
            elif location == "StartMenu":
                program_group = os.path.join(
                    os.path.expanduser('~'),
                    'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs',
                    SHORTCUT_NAME
                )
                if not os.path.exists(program_group):
                    os.makedirs(program_group)
                shortcut_dir = program_group
            else:
                shortcut_dir = location
                if not os.path.exists(shortcut_dir):
                    os.makedirs(shortcut_dir)
            shortcut_path = os.path.join(shortcut_dir, name + ".lnk")
            shell_obj = pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink, None,
                pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IShellLink
            )
            shell_obj.SetPath(target_path)
            shell_obj.SetWorkingDirectory(os.path.dirname(target_path))
            if icon_path and os.path.exists(icon_path):
                shell_obj.SetIconLocation(icon_path, 0)
            if description:
                shell_obj.SetDescription(description)
            persistant_file = shell_obj.QueryInterface(pythoncom.IID_IPersistFile)
            persistant_file.Save(shortcut_path, 0)
        except Exception as e:
            self.log_signal.emit("创建快捷方式失败：" + str(e))

    def add_env_paths(self, exe_path):
        ffmpeg_path = None
        bento4_path = None
        main_program_path = os.path.dirname(exe_path)
        for root, dirs, files in os.walk(self.install_path):
            for d in dirs:
                if d.lower() == "ffmpeg":
                    ffmpeg_path = os.path.join(root, d, "bin")
                if d.lower() == "bento4":
                    bento4_path = os.path.join(root, d, "bin")
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
            try:
                current_path, _ = winreg.QueryValueEx(key, "Path")
            except:
                current_path = ""
            paths_to_add = []
            if ffmpeg_path and ffmpeg_path not in current_path:
                paths_to_add.append(ffmpeg_path)
            if bento4_path and bento4_path not in current_path:
                paths_to_add.append(bento4_path)
            if main_program_path and main_program_path not in current_path:
                paths_to_add.append(main_program_path)
            if paths_to_add:
                if current_path and not current_path.endswith(";"):
                    current_path += ";"
                current_path += ";".join(paths_to_add)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, current_path)
                self.log_signal.emit("环境变量已更新")
            winreg.CloseKey(key)
        except Exception as e:
            self.log_signal.emit("添加环境变量失败：" + str(e))

    def _install_dev_cert(self, exe_path):
        """安装开发者证书到系统（受信任根 + 受信任发布者）

        在解压后的安装目录中查找 BilibiliDownloader_dev.cer，
        静默调用 certutil 安装到 LocalMachine 的 Root 和 TrustedPublisher。
        需要管理员权限（已在 main() 入口完成 UAC 提权）。
        """
        if sys.platform != 'win32':
            return

        # 在安装目录中查找证书文件
        cer_path = None
        for root, dirs, files in os.walk(self.install_path):
            for f in files:
                if f == "BilibiliDownloader_dev.cer":
                    cer_path = os.path.join(root, f)
                    break
            if cer_path:
                break

        if not cer_path:
            self.log_signal.emit("未找到证书文件，跳过证书安装")
            return

        # 检查管理员权限
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                self.log_signal.emit("非管理员权限，跳过证书安装")
                return
        except Exception:
            return

        # 调用 certutil 安装证书
        try:
            import subprocess
            # 受信任根证书颁发机构
            r1 = subprocess.run(
                ["certutil", "-addstore", "-f", "Root", cer_path],
                capture_output=True, text=True, timeout=30,
                creationflags=0x08000000,
            )
            # 受信任发布者
            r2 = subprocess.run(
                ["certutil", "-addstore", "-f", "TrustedPublisher", cer_path],
                capture_output=True, text=True, timeout=30,
                creationflags=0x08000000,
            )
            if r1.returncode == 0 and r2.returncode == 0:
                self.log_signal.emit("开发者证书已安装到系统（后续版本更新不再报'未知发行者'）")
            elif r1.returncode == 0:
                self.log_signal.emit("根证书安装成功，受信任发布者安装失败")
            elif r2.returncode == 0:
                self.log_signal.emit("受信任发布者安装成功，根证书安装失败")
            else:
                self.log_signal.emit(f"证书安装失败: {(r1.stderr + r2.stderr).strip()[:100]}")
        except Exception as e:
            self.log_signal.emit(f"证书安装异常: {e}")


# 需要保留的用户数据（覆盖安装时不删除不解压）
PRESERVE_FILES = [
    'cookie.txt',
    'download_history.json',
]
PRESERVE_DIRS = [
    'log',
]


class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("欢迎使用 " + APP_NAME + " 安装向导")

    def initializePage(self):
        # 欢迎页重置按钮文本
        self.wizard().button(QWizard.NextButton).setText("下一步 >")
        self.wizard().button(QWizard.BackButton).setVisible(False)
        self.setSubTitle("此向导将引导您完成 " + APP_NAME + " " + APP_VERSION + " 的安装")
        layout = QVBoxLayout()
        name_label = QLabel(APP_NAME + " " + APP_VERSION)
        name_label.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        name_label.setStyleSheet("color: #00a1d6;")
        layout.addWidget(name_label)
        desc_label = QLabel(
            "B站视频解析下载工具，支持多画质选择、批量下载、\n"
            "UP主主页解析、番剧下载等功能。"
        )
        desc_label.setStyleSheet("color: #555; font-size: 13px; margin-top: 8px;")
        layout.addWidget(desc_label)
        layout.addSpacing(10)
        # 更新日志用 QTextBrowser 渲染 Markdown
        self.update_browser = QTextBrowser()
        self.update_browser.setReadOnly(True)
        self.update_browser.setOpenExternalLinks(True)
        self.update_browser.setMaximumHeight(220)
        layout.addWidget(self.update_browser)

        # 先显示默认内容（兜底），然后异步从云端获取
        default_md = f"### {APP_VERSION} 更新内容：\n\n正在从云端获取更新日志..."
        self.update_browser.setHtml(markdown_to_html(default_md.strip()))

        # 异步从云端API获取当前版本的更新日志
        threading.Thread(target=self._fetch_update_content, daemon=True).start()

        layout.addStretch()
        self.setLayout(layout)

    def _fetch_update_content(self):
        """从云端API获取当前版本的更新日志

        注意：必须用低版本号请求（如0.0.1），否则云端判断'已是最新版'
        会返回 {has_update: false} 而不带 changelog/release_notes 字段
        """
        try:
            resp = requests.get(
                "https://www.bilidown.cn/api/v1/check",
                # 用低版本号请求，确保云端返回完整信息含changelog
                params={"version": "0.0.1", "platform": "windows", "channel": "stable"},
                timeout=8
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") in (0, '0', '0000', True, 'true', 'success', 'ok'):
                    info = data.get("data", {})
                    # 尝试多个可能的字段名
                    changelog = (
                        info.get("release_notes")
                        or info.get("changelog")
                        or info.get("update_log")
                        or info.get("change_log")
                        or info.get("notes")
                        or ""
                    )
                    if changelog:
                        self._set_update_html(changelog.strip())
                        return
        except Exception as e:
            pass

        # 兜底：云端未返回时显示提示
        fallback_md = f"### {APP_VERSION}\n\n正在从云端获取更新日志...\n\n如长时间无响应，请检查网络连接后重试。"
        self._set_update_html(fallback_md.strip())

    def _set_update_html(self, md_text):
        """线程安全地设置更新日志HTML"""
        try:
            html = markdown_to_html(md_text)
            # 通过QMetaObject.invokeMethod在主线程更新UI
            from PyQt5.QtCore import QMetaObject, Qt, Q_ARG
            QMetaObject.invokeMethod(
                self.update_browser, "setHtml",
                Qt.QueuedConnection, Q_ARG(str, html)
            )
        except Exception:
            pass


class LicensePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("许可协议")

    def initializePage(self):
        # 许可协议页重置按钮文本
        self.wizard().button(QWizard.NextButton).setText("下一步 >")
        self.setSubTitle("请阅读并接受许可协议以继续安装")
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        license_text = """
# 许可协议

---

## 版权声明

本软件（{app_name} {version}）版权归原作者所有。

## 使用许可

- 您可以免费使用、复制和分发本软件
- 本软件仅供学习和个人使用，不得用于商业用途
- 使用本软件产生的任何后果由使用者自行承担
- 请遵守B站的相关服务条款

## 免责声明

本软件按**现状**提供，不提供任何明示或暗示的保证，包括但不限于对适销性、特定用途的适用性和非侵权性的保证。在任何情况下，作者不对因使用或无法使用本软件而产生的任何索赔、损害或其他责任承担责任。

## 项目信息

- **项目主页**：[{website}]({website})
- **源代码仓库**：[{repo}]({repo})

---

请阅读上述协议，勾选下方选项后继续安装。
        """.format(app_name=APP_NAME, version=APP_VERSION, website=APP_WEBSITE, repo=APP_REPO)
        text_browser = QTextBrowser()
        text_browser.setReadOnly(True)
        text_browser.setOpenExternalLinks(True)
        text_browser.setHtml(markdown_to_html(license_text.strip()))
        scroll.setWidget(text_browser)
        layout.addWidget(scroll)
        self.accept_check = QCheckBox("我已阅读并接受上述许可协议")
        self.accept_check.toggled.connect(self.completeChanged)
        layout.addWidget(self.accept_check)
        self.setLayout(layout)

    def isComplete(self):
        return self.accept_check.isChecked()


class InstallPathPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("选择安装位置")

    def initializePage(self):
        # 安装路径页重置按钮文本
        self.wizard().button(QWizard.NextButton).setText("下一步 >")
        self.setSubTitle("选择软件的安装目录")
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        self.path_edit = QLineEdit()
        default_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'BilibiliDownloadTool')
        self.path_edit.setText(default_path)
        self.path_edit.setMinimumHeight(30)
        browse_button = QPushButton("浏览...")
        browse_button.setMinimumHeight(30)
        browse_button.clicked.connect(self.browse_path)
        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(browse_button)
        form_layout.addRow("安装目录：", path_widget)
        hint_label = QLabel("建议安装在有充足空间的分区，约需 300-500 MB")
        hint_label.setStyleSheet("color: #888; font-size: 12px;")
        form_layout.addRow("", hint_label)
        layout.addLayout(form_layout)
        self.setLayout(layout)

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择安装位置", self.path_edit.text())
        if path:
            # 强制在所选路径下追加 BilibiliDownloadTool 子文件夹，
            # 防止意外安装到根目录（用户仍可手动编辑路径）
            base_name = os.path.basename(os.path.normpath(path))
            if base_name.lower() != 'bilibilidownloadtool':
                path = os.path.join(path, 'BilibiliDownloadTool')
            self.path_edit.setText(path)

    def validatePage(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "请选择安装位置")
            return False
        # 安全防护：拒绝驱动器根目录(如 D:\)、系统目录等危险路径，
        # 避免卸载时 shutil.rmtree 递归删除整盘数据
        safe, reason = is_safe_install_path(path)
        if not safe:
            QMessageBox.critical(self, "路径不安全", reason)
            return False
        try:
            if not os.path.exists(path):
                os.makedirs(path)
            fd, test_file = tempfile.mkstemp(dir=path, suffix='.tmp')
            os.close(fd)
            os.remove(test_file)
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", "无法写入到该位置：\n" + str(e))
            return False


class OptionsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("附加选项")
        self.setSubTitle("选择需要的附加任务")
        layout = QVBoxLayout()
        group = QGroupBox("快捷方式")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        self.desktop_check = QCheckBox("创建桌面快捷方式")
        self.desktop_check.setChecked(True)
        group_layout.addWidget(self.desktop_check)
        self.startmenu_check = QCheckBox("添加到开始菜单")
        self.startmenu_check.setChecked(True)
        group_layout.addWidget(self.startmenu_check)
        group.setLayout(group_layout)
        layout.addWidget(group)
        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        # 选项页的"下一步"改为"安装"
        self.wizard().button(QWizard.NextButton).setText("安装")


class InstallPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("正在安装")
        self.setSubTitle("正在安装 " + APP_NAME + " " + APP_VERSION + "，请稍候...")
        self.install_thread = None
        self.is_installing = False
        layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.status_label = QLabel("准备安装...")
        layout.addWidget(self.status_label)
        layout.addSpacing(8)
        group = QGroupBox("安装日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas; font-size: 12px; background-color: #fafafa;")
        log_layout.addWidget(self.log_text)
        group.setLayout(log_layout)
        layout.addWidget(group)
        self.setLayout(layout)

    def initializePage(self):
        # 按钮状态由 InstallerWizard._on_page_changed 统一管理
        if not self.is_installing:
            self.start_install()

    def start_install(self):
        self.is_installing = True
        wizard = self.wizard()
        install_path = wizard.path_page.path_edit.text().strip()
        create_desktop = wizard.options_page.desktop_check.isChecked()
        create_startmenu = wizard.options_page.startmenu_check.isChecked()
        self.log_text.append("开始安装 " + APP_NAME + " " + APP_VERSION)
        self.log_text.append("安装目录：" + install_path)
        # 记录安装前状态，用于取消时回滚
        self._pre_install_path = install_path
        self._pre_install_existed = os.path.isdir(install_path)
        self._pre_install_files = set(os.listdir(install_path)) if self._pre_install_existed else set()
        # 安装过程中只留取消按钮
        wizard.button(QWizard.CancelButton).setEnabled(True)
        wizard.button(QWizard.CancelButton).setVisible(True)
        wizard.button(QWizard.BackButton).setVisible(False)
        wizard.button(QWizard.NextButton).setVisible(False)
        wizard.button(QWizard.FinishButton).setVisible(False)

        # 只有当目标安装路径下已有程序文件时才提示覆盖（不管注册表）
        target_has_files = os.path.isdir(install_path) and any(
            os.path.exists(os.path.join(install_path, f))
            for f in [APP_EXE, UNINSTALLER_EXE, 'logo.ico'] + PRESERVE_FILES
        )
        if target_has_files:
            reply = QMessageBox.question(
                self, "检测到已有安装",
                "目标目录已存在文件：\n" + install_path +
                "\n\n是否覆盖安装？\n（Cookie、下载历史、日志等个人数据将被保留）",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.log_text.append("将覆盖安装到: " + install_path)
            else:
                wizard.reject()
                return
        else:
            # 用户选了新路径或空目录，直接安装
            _, old_path = self.is_already_installed()
            if old_path and old_path != install_path:
                self.log_text.append(f"检测到旧版本在: {old_path}（将安装到新路径）")
        package_path = self.get_embedded_package()
        if not package_path:
            self.log_text.append("本地未找到安装包，将尝试从云端下载...")
        self.install_thread = InstallerThread(install_path, create_desktop, create_startmenu, package_path)
        self.install_thread.log_signal.connect(self.append_log)
        self.install_thread.progress_signal.connect(self.update_progress)
        self.install_thread.finished_signal.connect(self.install_finished)
        self.install_thread.start()

    def get_embedded_package(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            if hasattr(sys, '_MEIPASS'):
                meipass_dir = sys._MEIPASS
                for candidate in os.listdir(meipass_dir):
                    if candidate.endswith('.zip') and 'BilibiliDownloader' in candidate:
                        path = os.path.join(meipass_dir, candidate)
                        if os.path.isfile(path):
                            return path
                zip_name = "BilibiliDownloader.zip"
                if os.path.exists(os.path.join(meipass_dir, zip_name)):
                    return os.path.join(meipass_dir, zip_name)
            for candidate in os.listdir(base_dir):
                if candidate.endswith('.zip') and 'BilibiliDownloader' in candidate:
                    path = os.path.join(base_dir, candidate)
                    if os.path.isfile(path):
                        return path
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            dist_dir = os.path.join(script_dir, "dist")
            output_dir = os.path.join(script_dir, "output")
            for search_dir in [output_dir, dist_dir, script_dir]:
                if not os.path.isdir(search_dir):
                    continue
                for f in os.listdir(search_dir):
                    if f.endswith('.zip') and 'BilibiliDownloader' in f:
                        path = os.path.join(search_dir, f)
                        if os.path.isfile(path):
                            return path
        return None

    def is_already_installed(self):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            if os.path.exists(install_path):
                return True, install_path
        except:
            pass
        return False, ""

    def append_log(self, msg):
        self.log_text.append(msg)
        self.log_text.moveCursor(QTextCursor.End)

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.status_label.setText("正在安装... %d%%" % current)

    def install_finished(self, success, message):
        wizard = self.wizard()
        wizard.install_success = success
        wizard.install_message = message
        if success:
            self.is_installing = False
            self.log_text.append("\n安装完成")
            self.status_label.setText("安装完成")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            # 安装成功后自动跳到最后一页
            wizard.button(QWizard.CancelButton).setVisible(False)
            wizard.button(QWizard.BackButton).setVisible(False)
            wizard.button(QWizard.NextButton).setVisible(False)
            wizard.button(QWizard.FinishButton).setVisible(True)
            wizard.button(QWizard.FinishButton).setEnabled(True)
            wizard.button(QWizard.FinishButton).setFocus()
            wizard.next()
        else:
            self.log_text.append("\n安装失败：" + message)
            self.status_label.setText("安装失败")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            wizard.button(QWizard.CancelButton).setEnabled(True)
            wizard.button(QWizard.BackButton).setVisible(True)
            wizard.button(QWizard.NextButton).setVisible(True)
            QMessageBox.critical(self, "安装失败", message)


class FinishPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("安装完成")
        self.setSubTitle(APP_NAME + " " + APP_VERSION + " 已成功安装")
        layout = QVBoxLayout()
        success_label = QLabel(APP_NAME + " " + APP_VERSION + " 安装成功")
        success_label.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        success_label.setStyleSheet("color: #27ae60;")
        layout.addWidget(success_label)
        tip_label = QLabel("您可以通过桌面快捷方式或开始菜单启动程序")
        tip_label.setStyleSheet("color: #555; font-size: 13px; margin-top: 4px;")
        layout.addWidget(tip_label)
        layout.addSpacing(20)
        self.launch_check = QCheckBox("立即启动 " + APP_NAME)
        self.launch_check.setChecked(True)
        layout.addWidget(self.launch_check)
        self.visit_web_check = QCheckBox("访问项目主页 (bilidown.cn)")
        self.visit_web_check.setChecked(False)
        layout.addWidget(self.visit_web_check)
        self.visit_repo_check = QCheckBox("访问 GitHub 仓库")
        self.visit_repo_check.setChecked(False)
        layout.addWidget(self.visit_repo_check)
        layout.addStretch()
        self.setLayout(layout)

    def initializePage(self):
        # 完成页只显示"完成"按钮，隐藏其他导航
        wizard = self.wizard()
        wizard.button(QWizard.BackButton).setVisible(False)
        wizard.button(QWizard.BackButton).setEnabled(False)
        wizard.button(QWizard.NextButton).setVisible(False)
        wizard.button(QWizard.NextButton).setEnabled(False)
        wizard.button(QWizard.CancelButton).setVisible(False)
        wizard.button(QWizard.CancelButton).setEnabled(False)
        wizard.button(QWizard.FinishButton).setVisible(True)
        wizard.button(QWizard.FinishButton).setEnabled(True)
        wizard.button(QWizard.FinishButton).setFocus()


class InstallerWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME + " " + APP_VERSION + " 安装程序")
        self.setMinimumSize(750, 550)
        self.resize(750, 550)
        self.setWizardStyle(QWizard.ModernStyle)
        self.install_success = False
        self.install_message = ""
        self.install_path = ""
        self._is_rolling_back = False
        self.setLogo()
        self.welcome_page = WelcomePage(self)
        self.addPage(self.welcome_page)
        self.license_page = LicensePage(self)
        self.addPage(self.license_page)
        self.path_page = InstallPathPage(self)
        self.addPage(self.path_page)
        self.options_page = OptionsPage(self)
        self.addPage(self.options_page)
        self.install_page = InstallPage(self)
        self.addPage(self.install_page)
        self.finish_page = FinishPage(self)
        self.addPage(self.finish_page)
        self.button(QWizard.FinishButton).clicked.connect(self.on_finish)

        # 按 addPage 顺序固定索引（0=welcome, 1=license, 2=path, 3=options, 4=install, 5=finish）
        self._page_ids = {
            'welcome':  0,
            'license':  1,
            'path':     2,
            'options':  3,
            'install':  4,
            'finish':   5,
        }

        # 页面切换时统一管理按钮状态
        self.currentIdChanged.connect(self._on_page_changed)

        # 给按钮设置 objectName，方便 QSS ID 选择器样式
        self.button(QWizard.BackButton).setObjectName("backButton")
        self.button(QWizard.NextButton).setObjectName("nextButton")
        self.button(QWizard.CancelButton).setObjectName("cancelButton")
        self.button(QWizard.FinishButton).setObjectName("nextButton")

        self.apply_stylesheet()

    def _on_page_changed(self, page_id):
        """页面切换后统一设置按钮状态，覆盖 ModernStyle 的默认行为"""
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._setup_buttons_for_page(page_id))

    def _setup_buttons_for_page(self, page_id):
        if not hasattr(self, '_page_ids') or not self._page_ids:
            return

        btn_back = self.button(QWizard.BackButton)
        btn_next = self.button(QWizard.NextButton)
        btn_cancel = self.button(QWizard.CancelButton)
        btn_finish = self.button(QWizard.FinishButton)

        pid = self._page_ids

        if page_id == pid['welcome']:
            btn_back.setVisible(False)
            btn_next.setVisible(True); btn_next.setText("下一步 >")
            btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("取消")
            btn_finish.setVisible(False)

        elif page_id == pid['license']:
            btn_back.setVisible(True); btn_back.setText("< 上一步"); btn_back.setEnabled(True)
            btn_next.setVisible(True); btn_next.setText("下一步 >")
            btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("取消")
            btn_finish.setVisible(False)

        elif page_id == pid['path']:
            btn_back.setVisible(True); btn_back.setText("< 上一步"); btn_back.setEnabled(True)
            btn_next.setVisible(True); btn_next.setText("下一步 >")
            btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("取消")
            btn_finish.setVisible(False)

        elif page_id == pid['options']:
            btn_back.setVisible(True); btn_back.setText("< 上一步"); btn_back.setEnabled(True)
            btn_next.setVisible(True); btn_next.setText("安装"); btn_next.setEnabled(True)
            btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("取消")
            btn_finish.setVisible(False)

        elif page_id == pid['install']:
            if self.install_page.is_installing or self._is_rolling_back:
                btn_back.setVisible(False)
                btn_next.setVisible(False)
                btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("取消")
                btn_finish.setVisible(False)
            else:
                pass

        elif page_id == pid['finish']:
            btn_back.setVisible(False); btn_back.setEnabled(False)
            btn_next.setVisible(False); btn_next.setEnabled(False)
            btn_cancel.setVisible(False); btn_cancel.setEnabled(False)
            btn_finish.setVisible(True); btn_finish.setEnabled(True); btn_finish.setText("完成")

    def setLogo(self):
        logo_paths = []
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            logo_paths.append(os.path.join(exe_dir, "logo.ico"))
            logo_paths.append(os.path.join(exe_dir, "logo.png"))
            internal_dir = os.path.join(exe_dir, "_internal")
            if os.path.isdir(internal_dir):
                logo_paths.append(os.path.join(internal_dir, "logo.ico"))
                logo_paths.append(os.path.join(internal_dir, "logo.png"))
            if hasattr(sys, '_MEIPASS'):
                logo_paths.append(os.path.join(sys._MEIPASS, "logo.ico"))
                logo_paths.append(os.path.join(sys._MEIPASS, "logo.png"))
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logo_paths.append(os.path.join(script_dir, "logo.ico"))
            logo_paths.append(os.path.join(script_dir, "logo.png"))
        for path in logo_paths:
            if os.path.exists(path):
                try:
                    self.setWindowIcon(QIcon(path))
                    self.logo_path = path
                    break
                except:
                    pass

    def reject(self):
        install_page = self.install_page
        if install_page.is_installing:
            reply = QMessageBox.warning(
                self, "确认取消",
                "安装尚未完成，取消将回滚已安装的文件。\n确定要取消安装吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._rollback_install()
        elif self._is_rolling_back:
            pass
        else:
            super().reject()

    def _rollback_install(self):
        from PyQt5.QtCore import QEventLoop, QTimer
        install_page = self.install_page
        self._is_rolling_back = True

        if install_page.install_thread and install_page.install_thread.isRunning():
            install_page.install_thread.cancel()
            waited = 0
            while install_page.install_thread.isRunning() and waited < 10000:
                install_page.install_thread.wait(500)
                waited += 500
                loop = QEventLoop()
                QTimer.singleShot(50, loop.quit)
                loop.exec_()
            if install_page.install_thread.isRunning():
                install_page.log_text.append("提示：下载线程仍在运行，将在网络超时后自动停止")

        install_page.is_installing = False

        install_page.status_label.setText("正在回滚...")
        install_page.status_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        install_page.log_text.append("\n=== 用户取消安装，开始回滚 ===")

        self._setup_buttons_for_page(4)

        current_val = install_page.progress_bar.value()
        for v in range(current_val, -1, -1):
            install_page.progress_bar.setValue(v)
            install_page.status_label.setText(f"正在回滚... {max(v, 0)}%")
            loop = QEventLoop()
            QTimer.singleShot(20, loop.quit)
            loop.exec_()

        install_path = getattr(install_page, '_pre_install_path', None)
        if not install_path or not os.path.isdir(install_path):
            install_page.log_text.append("回滚完成：无需清理")
            install_page.status_label.setText("回滚完成：用户取消安装")
            install_page.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            install_page.progress_bar.setValue(0)
            self._is_rolling_back = False

            btn_back = self.button(QWizard.BackButton)
            btn_next = self.button(QWizard.NextButton)
            btn_cancel = self.button(QWizard.CancelButton)
            btn_finish = self.button(QWizard.FinishButton)
            btn_back.setVisible(False)
            btn_next.setVisible(False)
            btn_finish.setVisible(False)
            btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("退出")
            return

        pre_existed = getattr(install_page, '_pre_install_existed', False)
        pre_files = getattr(install_page, '_pre_install_files', set())
        try:
            # 回滚前的安全防护：校验路径，避免误删整盘
            safe, reason = is_safe_install_path(install_path)
            if not safe:
                install_page.log_text.append(f"回滚中止，路径不安全：{reason}")
                install_page.log_text.append("请手动清理安装目录")
            elif not pre_existed:
                shutil.rmtree(install_path, ignore_errors=True)
                install_page.log_text.append("回滚完成：已删除安装目录")
            else:
                current_files = set(os.listdir(install_path))
                new_files = current_files - pre_files
                for f in new_files:
                    fpath = os.path.join(install_path, f)
                    try:
                        if os.path.isdir(fpath):
                            shutil.rmtree(fpath, ignore_errors=True)
                        else:
                            os.remove(fpath)
                    except Exception:
                        pass
                install_page.log_text.append(f"回滚完成：已清理 {len(new_files)} 个新增文件")
        except Exception as e:
            install_page.log_text.append(f"回滚时出错：{e}")

        install_page.status_label.setText("回滚完成：用户取消安装")
        install_page.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        install_page.progress_bar.setValue(0)
        self._is_rolling_back = False

        btn_back = self.button(QWizard.BackButton)
        btn_next = self.button(QWizard.NextButton)
        btn_cancel = self.button(QWizard.CancelButton)
        btn_finish = self.button(QWizard.FinishButton)
        btn_back.setVisible(False)
        btn_next.setVisible(False)
        btn_finish.setVisible(False)
        btn_cancel.setVisible(True); btn_cancel.setEnabled(True); btn_cancel.setText("退出")

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWizard {
                background-color: #f8f9fa;
            }
            QWizardPage {
                background-color: #f8f9fa;
            }
            QLabel {
                color: #333;
                font-family: "Microsoft YaHei", "微软雅黑", Arial;
            }
            QPushButton {
                background-color: #00a1d6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 22px;
                font-size: 13px;
                font-family: "Microsoft YaHei", "微软雅黑", Arial;
                min-width: 88px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #00b5e5;
            }
            QPushButton:pressed {
                background-color: #0091c2;
            }
            QPushButton:disabled {
                background-color: #d0d7de;
                color: #99a2ad;
            }
            QPushButton#nextButton {
                background-color: #00a1d6;
            }
            QPushButton#nextButton:hover {
                background-color: #00b5e5;
            }
            QPushButton#backButton {
                background-color: #fff;
                color: #555;
                border: 1px solid #d9d9d9;
            }
            QPushButton#backButton:hover {
                background-color: #f5f7fa;
                border-color: #b3d4ff;
                color: #00a1d6;
            }
            QPushButton#backButton:disabled {
                background-color: #f5f5f5;
                color: #bbb;
                border-color: #e0e0e0;
            }
            QPushButton#cancelButton {
                background-color: #fff;
                color: #666;
                border: 1px solid #d9d9d9;
            }
            QPushButton#cancelButton:hover {
                background-color: #fff5f5;
                border-color: #ff7875;
                color: #ff4d4f;
            }
            QGroupBox {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                margin-top: 16px;
                padding-top: 14px;
                padding-left: 12px;
                padding-right: 12px;
                padding-bottom: 10px;
                font-weight: bold;
                background-color: #fff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: #00a1d6;
                font-size: 13px;
                left: 12px;
            }
            QProgressBar {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                text-align: center;
                background-color: #f3f4f6;
                height: 24px;
                color: #666;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c6ff, stop:1 #00a1d6);
                border-radius: 5px;
            }
            QLineEdit {
                border: 1px solid #d9d9d9;
                border-radius: 6px;
                padding: 6px 10px;
                background-color: #fff;
                selection-background-color: #00a1d6;
            }
            QLineEdit:focus {
                border: 1px solid #00a1d6;
            }
            QCheckBox {
                spacing: 8px;
                color: #444;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #d9d9d9;
                border-radius: 3px;
                background-color: #fff;
            }
            QCheckBox::indicator:hover {
                border-color: #00a1d6;
            }
            QCheckBox::indicator:checked {
                background-color: #00a1d6;
                border: 1px solid #00a1d6;
                image: none;
            }
            QTextEdit, QTextBrowser {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background-color: #fafbfc;
                padding: 6px;
                color: #444;
            }
            QTextBrowser {
                background-color: #fff;
            }
            QScrollBar:vertical {
                border: none;
                background-color: #f3f4f6;
                width: 10px;
                margin: 0;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #c8ccd1;
                min-height: 40px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #a8acb1;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def on_finish(self):
        if self.finish_page.visit_web_check.isChecked():
            try:
                webbrowser.open(APP_WEBSITE)
            except:
                pass
        if self.finish_page.visit_repo_check.isChecked():
            try:
                webbrowser.open(APP_REPO)
            except:
                pass
        if self.finish_page.launch_check.isChecked():
            try:
                self.launch_program()
            except:
                pass

    def launch_program(self):
        install_path = self.path_page.path_edit.text()
        exe_path = None
        for root, dirs, files in os.walk(install_path):
            if APP_EXE in files:
                exe_path = os.path.join(root, APP_EXE)
                break
        if not exe_path:
            for root, dirs, files in os.walk(install_path):
                for f in files:
                    if f.endswith('.exe') and 'uninstall' not in f.lower():
                        exe_path = os.path.join(root, f)
                        break
                if exe_path:
                    break
        if exe_path:
            import subprocess
            subprocess.Popen([exe_path], cwd=os.path.dirname(exe_path), creationflags=subprocess.CREATE_NO_WINDOW)


def build_zip(source_dir, output_zip=None):
    """打包安装zip，自动排除用户数据文件（cookie/日志/历史等）

    用法: python installer.py --build-zip dist/BilibiliDownloader
         python installer.py --build-zip dist/BilibiliDownloader output/BilibiliDownloader.zip
    """
    if output_zip is None:
        output_zip = os.path.join(os.path.dirname(source_dir), 'BilibiliDownloader.zip')

    # 排除列表
    exclude_files = set(PRESERVE_FILES)
    exclude_dirs = set(PRESERVE_DIRS)
    # 额外排除不需要打包的文件
    exclude_files.update([
        # uninstaller.exe 已包含在安装包中
        'uninstaller.py',
        'installer.py',
        'cli.py',
        '*.pyc', '__pycache__',
    ])

    def should_exclude(arcname):
        basename = os.path.basename(arcname)
        if basename in exclude_files:
            return True
        for d in exclude_dirs:
            if arcname.startswith(d + '/') or arcname.startswith(d + '\\'):
                return True
        # 排除 __pycache__
        parts = arcname.replace('\\', '/').split('/')
        if '__pycache__' in parts:
            return True
        return False

    print(f"正在打包: {source_dir}")
    print(f"输出: {output_zip}")
    print(f"排除文件: {exclude_files}")
    print(f"排除目录: {exclude_dirs}")

    count = 0
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            # 跳过排除目录（不遍历进去）
            dirs[:] = [d for d in dirs if d not in exclude_dirs and d != '__pycache__']
            for f in files:
                fpath = os.path.join(root, f)
                arcname = os.path.relpath(fpath, source_dir)
                if should_exclude(arcname):
                    print(f"  跳过: {arcname}")
                    continue
                zf.write(fpath, arcname)
                count += 1

    zip_size = os.path.getsize(output_zip)
    print(f"\n打包完成! 共 {count} 个文件, 大小: {zip_size / 1024 / 1024:.1f} MB")
    print(f"路径: {os.path.abspath(output_zip)}")
    return output_zip


def main():
    # 支持 --build-zip 命令行参数直接打包
    if len(sys.argv) >= 3 and sys.argv[1] == '--build-zip':
        source = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else None
        build_zip(source, output)
        return

    # Windows: 启动时自动申请管理员权限（用于安装到ProgramFiles、
    # 写注册表、添加环境变量、安装开发者证书等）
    if sys.platform == 'win32':
        try:
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
                sys.exit(0)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    wizard = InstallerWizard()
    wizard.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
