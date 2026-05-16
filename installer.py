#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频解析工具 V2.0.1 正式安装程序
"""

import os
import sys
import tempfile
import traceback
import webbrowser
import zipfile

import winreg
from PyQt5.QtWidgets import (
    QApplication, QWizard, QWizardPage, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox,
    QProgressBar, QMessageBox, QGroupBox, QFormLayout, QTextEdit,
    QCheckBox, QFrame, QScrollArea, QTextBrowser, QSpacerItem, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QPixmap


APP_NAME = "B站视频解析工具"
APP_VERSION = "V2.0.1"
APP_EXE = "V2.0.1_main.exe"
UNINSTALLER_EXE = "V2.0_uninstaller.exe"
REG_KEY = r"Software\BilibiliDownloadTool"
SHORTCUT_NAME = f"{APP_NAME}{APP_VERSION}"


def markdown_to_html(text):
    text = text.replace('### ', '<h3>').replace('\n### ', '</h3>\n<h3>')
    text = text.replace('## ', '<h2>').replace('\n## ', '</h2>\n<h2>')
    text = text.replace('# ', '<h1>').replace('\n# ', '</h1>\n<h1>')
    import re
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
            result.append(f'<li>{line[2:]}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)
    if in_list:
        result.append('</ul>')
    text = '\n'.join(result)
    text = text.replace('\n\n', '</p>\n<p>')
    return f'<html><body style="font-family:Microsoft YaHei;font-size:13px;color:#333;line-height:1.8"><p>{text}</p></body></html>'


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
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit("正在准备安装环境...")
            self.progress_signal.emit(0, 100)

            if self.package_path and os.path.exists(self.package_path):
                self.log_signal.emit(f"安装包就绪: {os.path.basename(self.package_path)}")
                self.extract_package(self.package_path)
            else:
                self.log_signal.emit("错误：未找到安装包！")
                self.finished_signal.emit(False, "未找到安装包")
        except Exception as e:
            error_msg = f"安装失败：{str(e)}\n{traceback.format_exc()}"
            self.log_signal.emit(error_msg)
            self.finished_signal.emit(False, str(e))

    def extract_package(self, package_path):
        try:
            self.log_signal.emit("正在解压文件，请稍候...")
            self.progress_signal.emit(5, 100)

            if not os.path.exists(self.install_path):
                os.makedirs(self.install_path)

            file_size = os.path.getsize(package_path)
            self.log_signal.emit(f"安装包大小: {file_size / 1024 / 1024:.1f} MB")

            with zipfile.ZipFile(package_path, 'r') as z:
                total_files = len(z.namelist())
                self.log_signal.emit(f"共 {total_files} 个文件待解压")
                for i, name in enumerate(z.namelist()):
                    z.extract(name, self.install_path)
                    if i % 200 == 0:
                        progress = 5 + int((i / total_files) * 50)
                        self.progress_signal.emit(progress, 100)
                        pct = int((i / total_files) * 100)
                        self.log_signal.emit(f"解压进度: {pct}% ({i}/{total_files})")

            self.log_signal.emit("文件解压完成")
            self.progress_signal.emit(55, 100)

            self.log_signal.emit("正在写入注册表...")
            self.save_install_path()
            self.progress_signal.emit(60, 100)

            exe_path = self.find_main_exe()
            if not exe_path:
                self.log_signal.emit(f"警告：未找到{APP_EXE}")
                exe_files = [f for f in os.listdir(self.install_path) if f.endswith('.exe')]
                if exe_files:
                    exe_path = os.path.join(self.install_path, exe_files[0])
                else:
                    raise Exception("未找到可执行文件")

            self.log_signal.emit(f"主程序定位: {os.path.basename(exe_path)}")
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
                    self.create_shortcut(uninstaller_path, "StartMenu", f"卸载{SHORTCUT_NAME}", description=f"卸载{SHORTCUT_NAME}")
                    self.log_signal.emit("卸载程序快捷方式已创建")

            self.progress_signal.emit(80, 100)

            self.log_signal.emit("正在配置环境变量...")
            self.add_env_paths(exe_path)
            self.progress_signal.emit(95, 100)

            self.log_signal.emit("正在完成安装...")
            self.progress_signal.emit(100, 100)

            self.log_signal.emit(f"{APP_NAME} {APP_VERSION} 安装完成！")
            self.finished_signal.emit(True, "安装成功！")

        except Exception as e:
            error_msg = f"安装失败：{str(e)}\n{traceback.format_exc()}"
            self.log_signal.emit(error_msg)
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
        for icon_name in ['logo.ico', 'logo.png']:
            icon_file = os.path.join(exe_dir, icon_name)
            if os.path.exists(icon_file):
                return icon_file
        return None

    def save_install_path(self):
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY)
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, self.install_path)
            winreg.SetValueEx(key, "Version", 0, winreg.REG_SZ, APP_VERSION)
            winreg.CloseKey(key)
            self.log_signal.emit("安装信息已写入注册表")
        except Exception as e:
            self.log_signal.emit(f"写入注册表失败：{str(e)}")

    def create_shortcut(self, target_path, location, name, icon_path=None, description=None):
        try:
            import pythoncom
            from win32com.shell import shell, shellcon

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

            shortcut_path = os.path.join(shortcut_dir, f"{name}.lnk")

            shell_obj = pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink,
                None,
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
            self.log_signal.emit(f"创建快捷方式失败：{str(e)}")

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
            self.log_signal.emit(f"添加环境变量失败：{str(e)}")


class WelcomePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle(f"欢迎使用 {APP_NAME} 安装向导")
        self.setSubTitle(f"此向导将引导您完成 {APP_NAME} {APP_VERSION} 的安装")

        layout = QVBoxLayout()

        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f9ff;
                border: 1px solid #b3e0ff;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)

        version_label = QLabel(f"📦 {APP_NAME} {APP_VERSION}")
        version_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        version_label.setStyleSheet("color: #00a1d6; border: none;")
        info_layout.addWidget(version_label)

        desc_label = QLabel(
            "一款功能强大的B站视频解析下载工具，支持多画质选择、\n"
            "批量下载、UP主主页解析、番剧下载等功能。"
        )
        desc_label.setStyleSheet("color: #555; border: none; font-size: 13px;")
        info_layout.addWidget(desc_label)

        layout.addWidget(info_frame)
        layout.addSpacing(15)

        update_label = QLabel("🆕 V2.0.1 更新内容：")
        update_label.setFont(QFont("Microsoft YaHei", 10, QFont.Bold))
        layout.addWidget(update_label)

        updates = [
            "修复 ffmpeg/ffprobe 调用错误导致视频编码检测失败",
            "修复批量下载不开始的问题（threading 变量作用域错误）",
            "修复线程设置无效（最大并发任务数硬编码问题）",
            "新增下载失败自动重新解析链接静默重试",
            "新增完全模式多线程并发解析",
            "修复悬浮窗提示背景不透明问题",
        ]
        for u in updates:
            lbl = QLabel(f"  • {u}")
            lbl.setStyleSheet("color: #666; font-size: 12px;")
            layout.addWidget(lbl)

        layout.addStretch()
        self.setLayout(layout)


class LicensePage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("许可协议")
        self.setSubTitle("请阅读并接受以下许可协议以继续安装")

        layout = QVBoxLayout()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: 1px solid #ddd; border-radius: 6px; }")

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

- **项目主页**：[https://www.bilidown.cn](https://www.bilidown.cn)
- **源代码仓库**：[https://github.com/NANblogink/bilibilidownloadtool](https://github.com/NANblogink/bilibilidownloadtool)

---

请阅读上述协议。如接受，请勾选下方选项并继续安装。
        """.format(app_name=APP_NAME, version=APP_VERSION)

        text_browser = QTextBrowser()
        text_browser.setReadOnly(True)
        text_browser.setOpenExternalLinks(True)
        html_content = markdown_to_html(license_text.strip())
        text_browser.setHtml(html_content)
        scroll.setWidget(text_browser)

        layout.addWidget(scroll)

        self.accept_check = QCheckBox("我已阅读并接受上述许可协议")
        self.accept_check.setStyleSheet("font-size: 13px; spacing: 8px;")
        self.accept_check.toggled.connect(self.completeChanged)
        layout.addWidget(self.accept_check)

        self.setLayout(layout)

    def isComplete(self):
        return self.accept_check.isChecked()


class InstallPathPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("选择安装位置")
        self.setSubTitle("请选择软件的安装目录")

        layout = QVBoxLayout()

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.path_edit = QLineEdit()
        default_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'BilibiliDownloadTool')
        self.path_edit.setText(default_path)
        self.path_edit.setMinimumHeight(32)
        self.path_edit.setStyleSheet("QLineEdit { padding: 4px 8px; border: 1px solid #ccc; border-radius: 4px; }")

        browse_button = QPushButton("浏览...")
        browse_button.setMinimumHeight(32)
        browse_button.clicked.connect(self.browse_path)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_edit, 1)
        path_layout.addWidget(browse_button)

        form_layout.addRow("安装目录：", path_widget)

        hint_label = QLabel("💡 建议安装在有充足空间的分区，约需 300-500 MB")
        hint_label.setStyleSheet("color: #888; font-size: 12px;")
        form_layout.addRow("", hint_label)

        layout.addLayout(form_layout)
        self.setLayout(layout)

    def browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择安装位置", self.path_edit.text())
        if path:
            self.path_edit.setText(path)

    def validatePage(self):
        path = self.path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "请选择安装位置！")
            return False

        try:
            if not os.path.exists(path):
                os.makedirs(path)
            test_file = os.path.join(path, "test.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"无法写入到该位置：\n{str(e)}")
            return False


class OptionsPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("附加选项")
        self.setSubTitle("选择您需要的附加任务")

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


class InstallPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("正在安装")
        self.setSubTitle(f"正在安装 {APP_NAME} {APP_VERSION}，请稍候...")

        self.install_thread = None
        self.is_installing = False

        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setMinimumHeight(28)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备安装...")
        self.status_label.setStyleSheet("color: #555; font-size: 13px;")
        layout.addWidget(self.status_label)

        layout.addSpacing(8)

        group = QGroupBox("安装日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background-color: #fafafa;")
        log_layout.addWidget(self.log_text)
        group.setLayout(log_layout)
        layout.addWidget(group)

        self.setLayout(layout)

    def initializePage(self):
        if not self.is_installing:
            self.start_install()

    def start_install(self):
        self.is_installing = True
        wizard = self.wizard()

        install_path = wizard.page(1).path_edit.text()
        create_desktop = wizard.page(2).desktop_check.isChecked()
        create_startmenu = wizard.page(2).startmenu_check.isChecked()

        self.log_text.append(f"开始安装 {APP_NAME} {APP_VERSION}...")
        self.log_text.append(f"安装目录：{install_path}")

        wizard.button(QWizard.CancelButton).setEnabled(False)
        wizard.button(QWizard.BackButton).setEnabled(False)

        is_installed, installed_path = self.is_already_installed()
        if is_installed:
            reply = QMessageBox.question(
                self,
                "检测到已有安装",
                f"检测到软件已安装在：\n{installed_path}\n\n是否覆盖安装？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.log_text.append(f"将覆盖安装到: {install_path}")
            else:
                wizard.reject()
                return

        package_path = self.get_embedded_package()
        if not package_path:
            QMessageBox.critical(self, "错误", "未找到安装包！请确认安装程序完整。")
            wizard.button(QWizard.CancelButton).setEnabled(True)
            return

        self.install_thread = InstallerThread(
            install_path,
            create_desktop,
            create_startmenu,
            package_path
        )
        self.install_thread.log_signal.connect(self.append_log)
        self.install_thread.progress_signal.connect(self.update_progress)
        self.install_thread.finished_signal.connect(self.install_finished)
        self.install_thread.start()

    def get_embedded_package(self):
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            temp_dir = sys._MEIPASS
            zip_path = os.path.join(temp_dir, "V2.0.1_main.zip")
            if os.path.exists(zip_path):
                import shutil
                temp_package = os.path.join(tempfile.gettempdir(), "V2.0.1_main_install.zip")
                shutil.copy2(zip_path, temp_package)
                return temp_package
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            for candidate in [
                os.path.join(script_dir, "dist", "V2.0.1_main.zip"),
                os.path.join(script_dir, "V2.0.1_main.zip"),
            ]:
                if os.path.exists(candidate):
                    return candidate
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
        self.status_label.setText(f"正在安装... {current}%")

    def install_finished(self, success, message):
        wizard = self.wizard()
        wizard.install_success = success
        wizard.install_message = message

        if success:
            self.log_text.append(f"\n✅ {APP_NAME} {APP_VERSION} 安装完成！")
            self.status_label.setText("安装完成！")
            self.status_label.setStyleSheet("color: #00a1d6; font-size: 13px; font-weight: bold;")
            wizard.button(QWizard.NextButton).setEnabled(True)
            wizard.next()
        else:
            self.log_text.append(f"\n❌ 安装失败：{message}")
            self.status_label.setText("安装失败")
            self.status_label.setStyleSheet("color: #e74c3c; font-size: 13px; font-weight: bold;")
            wizard.button(QWizard.CancelButton).setEnabled(True)
            QMessageBox.critical(self, "安装失败", message)


class FinishPage(QWizardPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("安装完成")
        self.setSubTitle(f"{APP_NAME} {APP_VERSION} 已成功安装！")

        layout = QVBoxLayout()

        success_frame = QFrame()
        success_frame.setStyleSheet("""
            QFrame {
                background-color: #e8f8f0;
                border: 1px solid #a3d9b1;
                border-radius: 8px;
                padding: 20px;
            }
        """)
        frame_layout = QVBoxLayout(success_frame)

        success_label = QLabel(f"🎉 {APP_NAME} {APP_VERSION} 安装成功！")
        success_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        success_label.setStyleSheet("color: #27ae60; border: none;")
        frame_layout.addWidget(success_label)

        tip_label = QLabel("您可以通过桌面快捷方式或开始菜单启动程序")
        tip_label.setStyleSheet("color: #555; border: none; font-size: 13px;")
        frame_layout.addWidget(tip_label)

        layout.addWidget(success_frame)
        layout.addSpacing(15)

        self.launch_check = QCheckBox(f"立即启动 {APP_NAME}")
        self.launch_check.setChecked(True)
        self.launch_check.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.launch_check)

        self.visit_web_check = QCheckBox("访问项目主页 (bilidown.cn)")
        self.visit_web_check.setChecked(False)
        self.visit_web_check.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.visit_web_check)

        self.visit_repo_check = QCheckBox("访问 GitHub 仓库")
        self.visit_repo_check.setChecked(False)
        self.visit_repo_check.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.visit_repo_check)

        layout.addStretch()
        self.setLayout(layout)


class InstallerWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} 安装程序")
        self.setMinimumSize(820, 620)
        self.resize(820, 620)
        self.setWizardStyle(QWizard.ModernStyle)

        self.install_success = False
        self.install_message = ""
        self.install_path = ""

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

        self.setButtonText(QWizard.BackButton, "< 上一步")
        self.setButtonText(QWizard.NextButton, "下一步 >")
        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")

        self.apply_stylesheet()

    def setLogo(self):
        logo_paths = []
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
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

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QWizard {
                background-color: #f5f5f5;
            }
            QWizard > QWidget {
                background-color: white;
                border-radius: 10px;
            }
            QLabel#title {
                color: #333333;
                font-size: 24px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #00a1d6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #008bb9;
            }
            QPushButton:pressed {
                background-color: #007aa3;
            }
            QPushButton:disabled {
                background-color: #ccc;
                color: #999;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 2px solid #00a1d6;
                background-color: white;
            }
            QCheckBox::indicator:checked {
                background-color: #00a1d6;
            }
            QGroupBox {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 15px;
                font-weight: bold;
                font-size: 13px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 10px;
                color: #00a1d6;
            }
            QProgressBar {
                border: 2px solid #e0e0e0;
                border-radius: 8px;
                text-align: center;
                background-color: #f5f5f5;
                height: 25px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: #00a1d6;
                border-radius: 6px;
            }
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #00a1d6;
            }
        """)

    def on_finish(self):
        if self.finish_page.visit_web_check.isChecked():
            try:
                webbrowser.open("https://www.bilidown.cn")
            except:
                pass

        if self.finish_page.visit_repo_check.isChecked():
            try:
                webbrowser.open("https://github.com/NANblogink/bilibilidownloadtool")
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


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    wizard = InstallerWizard()
    wizard.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
