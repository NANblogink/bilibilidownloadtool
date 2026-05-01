#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频解析工具 V1.9 正式安装程序
"""

import os
import sys
import tempfile
import traceback
import webbrowser
import zipfile

import py7zr
import winreg
from PyQt5.QtWidgets import (
    QApplication, QWizard, QWizardPage, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFileDialog, QCheckBox,
    QProgressBar, QMessageBox, QGroupBox, QFormLayout, QTextEdit,
    QRadioButton, QButtonGroup, QFrame, QScrollArea, QTextBrowser
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

def markdown_to_html(text):
    """简单的Markdown转HTML函数"""
    # 标题
    text = text.replace('### ', '<h3>').replace('\n### ', '</h3>\n<h3>')
    text = text.replace('## ', '<h2>').replace('\n## ', '</h2>\n<h2>')
    text = text.replace('# ', '<h1>').replace('\n# ', '</h1>\n<h1>')
    
    # 粗体和斜体
    text = text.replace('**', '<b>', 1).replace('**', '</b>', 1)
    text = text.replace('*', '<i>', 1).replace('*', '</i>', 1)
    
    # 链接 [text](url)
    import re
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    # 水平线
    text = text.replace('---', '<hr>')
    
    # 列表
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
    
    # 段落
    text = text.replace('\n\n', '</p>\n<p>')
    
    return f'<html><body><p>{text}</p></body></html>'


class InstallerThread(QThread):
    """安装工作线程"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)  # 当前, 总
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, install_path, create_desktop, create_startmenu, local_package=None):
        super().__init__()
        self.install_path = install_path
        self.create_desktop = create_desktop
        self.create_startmenu = create_startmenu
        self.local_package = local_package
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit("正在准备安装...")
            self.progress_signal.emit(0, 100)

            # 优先使用本地安装包
            if self.local_package and os.path.exists(self.local_package):
                self.log_signal.emit(f"使用本地安装包: {self.local_package}")
                self.extract_package(self.local_package)
            else:
                self.log_signal.emit("错误：未找到本地安装包！")
                self.finished_signal.emit(False, "未找到本地安装包")
                return
                
        except Exception as e:
            error_msg = f"安装失败：{str(e)}\n{traceback.format_exc()}"
            self.log_signal.emit(error_msg)
            self.finished_signal.emit(False, str(e))

    def extract_package(self, package_path):
        """解压安装包"""
        try:
            self.log_signal.emit("正在解压安装包...")
            self.progress_signal.emit(10, 100)
            
            if not os.path.exists(self.install_path):
                os.makedirs(self.install_path)
            
            file_size = os.path.getsize(package_path)
            self.log_signal.emit(f"安装包大小: {file_size / 1024 / 1024:.2f} MB")
            
            # 根据文件扩展名选择解压方式
            if package_path.endswith('.zip'):
                with zipfile.ZipFile(package_path, 'r') as z:
                    total_files = len(z.namelist())
                    for i, name in enumerate(z.namelist()):
                        z.extract(name, self.install_path)
                        if i % 100 == 0:
                            progress = 10 + int((i / total_files) * 40)
                            self.progress_signal.emit(progress, 100)
                            self.log_signal.emit(f"解压进度: {int((i / total_files) * 100)}%")
            elif package_path.endswith('.7z'):
                with py7zr.SevenZipFile(package_path, mode='r') as z:
                    total_files = len(z.getnames())
                    for i, name in enumerate(z.getnames()):
                        if i % 100 == 0:
                            progress = 10 + int((i / total_files) * 40)
                            self.progress_signal.emit(progress, 100)
                            self.log_signal.emit(f"解压进度: {int((i / total_files) * 100)}%")
                    z.extractall(self.install_path)
            else:
                raise Exception(f"不支持的压缩包格式: {package_path}")
            
            self.log_signal.emit("解压完成！")
            self.progress_signal.emit(50, 100)
            
            # 步骤3：记录安装路径到注册表
            self.save_install_path()
            self.progress_signal.emit(60, 100)
            
            # 步骤4：查找主程序
            exe_path = self.find_main_exe()
            if not exe_path:
                self.log_signal.emit("警告：未找到V1.9_main.exe，使用目录下第一个exe文件")
                exe_files = [f for f in os.listdir(self.install_path) if f.endswith('.exe')]
                if exe_files:
                    exe_path = os.path.join(self.install_path, exe_files[0])
                else:
                    raise Exception("未找到可执行文件")
            
            self.log_signal.emit(f"主程序：{exe_path}")
            self.progress_signal.emit(70, 100)
            
            # 步骤5：创建快捷方式
            if self.create_desktop:
                self.create_shortcut(exe_path, "Desktop", "B站视频解析工具V1.9")
                self.log_signal.emit("桌面快捷方式已创建")
            
            if self.create_startmenu:
                self.create_shortcut(exe_path, "StartMenu", "B站视频解析工具V1.9")
                self.log_signal.emit("开始菜单快捷方式已创建")
            
            self.progress_signal.emit(85, 100)
            # 步骤6：添加环境变量
            self.add_env_paths(exe_path)
            self.progress_signal.emit(100, 100)
            
            self.log_signal.emit("安装完成！")
            self.finished_signal.emit(True, "安装成功！")
            
        except Exception as e:
            error_msg = f"安装失败：{str(e)}\n{traceback.format_exc()}"
            self.log_signal.emit(error_msg)
            self.finished_signal.emit(False, str(e))

    def find_main_exe(self):
        """查找V1.9_main.exe"""
        for root, dirs, files in os.walk(self.install_path):
            if "V1.9_main.exe" in files:
                return os.path.join(root, "V1.9_main.exe")
        return None

    def save_install_path(self):
        """保存安装路径到注册表"""
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\BilibiliDownloadTool")
            winreg.SetValueEx(key, "InstallPath", 0, winreg.REG_SZ, self.install_path)
            winreg.CloseKey(key)
            self.log_signal.emit("安装路径已记录")
        except Exception as e:
            self.log_signal.emit(f"记录安装路径失败：{str(e)}")

    def create_shortcut(self, target_path, location, name):
        """创建快捷方式"""
        try:
            import pythoncom
            from win32com.shell import shell, shellcon

            if location == "Desktop":
                desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
            else:  # StartMenu
                start_menu_path = os.path.join(
                    os.path.expanduser('~'),
                    'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs'
                )
                if not os.path.exists(start_menu_path):
                    os.makedirs(start_menu_path)
                desktop_path = start_menu_path

            shortcut_path = os.path.join(desktop_path, f"{name}.lnk")

            shell_obj = pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink,
                None,
                pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IShellLink
            )
            shell_obj.SetPath(target_path)
            shell_obj.SetWorkingDirectory(os.path.dirname(target_path))

            persistant_file = shell_obj.QueryInterface(pythoncom.IID_IPersistFile)
            persistant_file.Save(shortcut_path, 0)
        except Exception as e:
            self.log_signal.emit(f"创建快捷方式失败：{str(e)}")

    def add_env_paths(self, exe_path):
        """添加ffmpeg、bento4和主程序目录到环境变量"""
        ffmpeg_path = None
        bento4_path = None
        main_program_path = os.path.dirname(exe_path)

        # 查找文件夹
        for root, dirs, files in os.walk(self.install_path):
            for d in dirs:
                if d.lower() == "ffmpeg":
                    ffmpeg_path = os.path.join(root, d, "bin")
                if d.lower() == "bento4":
                    bento4_path = os.path.join(root, d, "bin")

        # 添加到用户环境变量
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
                self.log_signal.emit("环境变量已更新！")
                self.log_signal.emit("现在可以通过 win+r 或 cmd 输入 bilidown 启动程序")

            winreg.CloseKey(key)

        except Exception as e:
            self.log_signal.emit(f"添加环境变量失败：{str(e)}")


class LicensePage(QWizardPage):
    """协议页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("许可协议")
        self.setSubTitle("请阅读并接受以下许可协议以继续安装。")

        layout = QVBoxLayout()

        # 协议文本
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        license_text = """
# 许可协议

---

## 版权声明

本软件（B站视频解析工具V1.9）版权归原作者所有。

## 使用许可

- 您可以免费使用、复制和分发本软件。
- 本软件仅供学习和个人使用，不得用于商业用途。
- 使用本软件产生的任何后果由使用者自行承担。
- 请遵守B站的相关服务条款。

## 免责声明

本软件按**现状**提供，不提供任何明示或暗示的保证，包括但不限于对适销性、特定用途的适用性和非侵权性的保证。在任何情况下，作者不对因使用或无法使用本软件而产生的任何索赔、损害或其他责任承担责任。

## 项目信息

- **项目主页**：[https://www.bilidown.cn](https://www.bilidown.cn)
- **源代码仓库**：[https://github.com/NANblogink/bilibilidownloadtool](https://github.com/NANblogink/bilibilidownloadtool)

---

请阅读上述协议。如接受，请点击"接受"并继续安装。
        """

        text_browser = QTextBrowser()
        text_browser.setReadOnly(True)
        text_browser.setOpenExternalLinks(True)
        html_content = markdown_to_html(license_text.strip())
        text_browser.setHtml(html_content)
        scroll.setWidget(text_browser)

        layout.addWidget(scroll)

        # 接受协议复选框
        self.accept_check = QCheckBox("我已阅读并接受上述许可协议")
        self.accept_check.toggled.connect(self.completeChanged)
        layout.addWidget(self.accept_check)

        self.setLayout(layout)

    def isComplete(self):
        return self.accept_check.isChecked()


class InstallPathPage(QWizardPage):
    """安装路径页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("选择安装位置")
        self.setSubTitle("请选择软件的安装位置。")

        layout = QVBoxLayout()

        # 路径选择
        form_layout = QFormLayout()

        self.path_edit = QLineEdit()
        default_path = os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'BilibiliDownloader')
        self.path_edit.setText(default_path)
        self.path_edit.setMinimumHeight(30)

        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_path)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_button)

        form_layout.addRow("安装位置：", path_widget)

        # 空间提示
        hint_label = QLabel("提示：建议选择有足够空间的分区安装，约需要500MB-1GB空间。")
        hint_label.setStyleSheet("color: #666;")
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
            QMessageBox.critical(self, "错误", f"无法写入到该位置：{str(e)}")
            return False


class OptionsPage(QWizardPage):
    """选项页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("选择附加任务")
        self.setSubTitle("请选择您想要执行的附加任务。")

        layout = QVBoxLayout()

        # 快捷方式选项
        group = QGroupBox("快捷方式")
        group_layout = QVBoxLayout()

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
    """安装页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("正在安装")
        self.setSubTitle("正在安装B站视频解析工具V1.9，请稍候...")

        self.install_thread = None
        self.is_installing = False

        layout = QVBoxLayout()

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("准备安装...")
        layout.addWidget(self.status_label)

        # 日志
        group = QGroupBox("安装日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
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

        # 获取参数
        install_path = wizard.page(1).path_edit.text()
        create_desktop = wizard.page(2).desktop_check.isChecked()
        create_startmenu = wizard.page(2).startmenu_check.isChecked()

        self.log_text.append("开始安装...")
        self.log_text.append(f"安装位置：{install_path}")

        # 禁用按钮
        wizard.button(QWizard.CancelButton).setEnabled(False)
        wizard.button(QWizard.BackButton).setEnabled(False)

        # 检查是否已安装
        is_installed, installed_path = self.is_already_installed()
        overwrite = False
        
        if is_installed:
            reply = QMessageBox.question(
                self,
                "确认覆盖安装",
                f"检测到软件已安装在:\n{installed_path}\n\n是否覆盖安装？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                overwrite = True
                self.log_text.append(f"检测到已安装，将覆盖安装到: {install_path}")
            else:
                wizard.reject()
                return

        # 获取本地安装包路径
        local_package = self.get_local_package()
        if not local_package:
            QMessageBox.critical(self, "错误", "未找到本地安装包！请确保1.9.zip文件与安装程序在同一目录下。")
            wizard.button(QWizard.CancelButton).setEnabled(True)
            return

        # 启动线程
        self.install_thread = InstallerThread(
            install_path,
            create_desktop,
            create_startmenu,
            local_package
        )
        self.install_thread.log_signal.connect(self.append_log)
        self.install_thread.progress_signal.connect(self.update_progress)
        self.install_thread.finished_signal.connect(self.install_finished)
        self.install_thread.start()
    
    def get_local_package(self):
        """获取本地安装包路径"""
        # 获取安装程序所在目录
        if getattr(sys, 'frozen', False):
            # 打包后的环境 - 从临时目录获取资源
            if hasattr(sys, '_MEIPASS'):
                temp_dir = sys._MEIPASS
                zip_path = os.path.join(temp_dir, "1.9.zip")
                if os.path.exists(zip_path):
                    # 复制到临时目录
                    import shutil
                    temp_package = os.path.join(tempfile.gettempdir(), "1.9.zip")
                    if not os.path.exists(temp_package) or os.path.getsize(temp_package) < 100 * 1024 * 1024:
                        shutil.copy(zip_path, temp_package)
                    return temp_package
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 查找1.9.zip
        zip_path = os.path.join(app_dir, "1.9.zip")
        if os.path.exists(zip_path):
            return zip_path
        
        # 查找其他可能的压缩包
        for f in os.listdir(app_dir):
            if f.endswith('.zip') or f.endswith('.7z'):
                return os.path.join(app_dir, f)
        
        return None
    
    def is_already_installed(self):
        """检查软件是否已安装"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\BilibiliDownloadTool", 0, winreg.KEY_READ)
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
            self.log_text.append("\n安装完成！")
            wizard.button(QWizard.NextButton).setEnabled(True)
            wizard.next()
        else:
            self.log_text.append(f"\n安装失败：{message}")
            wizard.button(QWizard.CancelButton).setEnabled(True)
            QMessageBox.critical(self, "安装失败", message)


class FinishPage(QWizardPage):
    """完成页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("安装完成")
        self.setSubTitle("已成功安装B站视频解析工具V1.9！")

        layout = QVBoxLayout()

        # 完成信息
        info_label = QLabel("恭喜您，软件已成功安装！")
        info_font = QFont("Microsoft YaHei", 12)
        info_label.setFont(info_font)
        layout.addWidget(info_label)

        layout.addSpacing(15)

        # 选项
        self.visit_web_check = QCheckBox("访问网页版 (https://www.bilidown.cn)")
        self.visit_web_check.setChecked(True)
        layout.addWidget(self.visit_web_check)

        self.visit_repo_check = QCheckBox("访问GitHub仓库 (https://github.com/NANblogink/bilibilidownloadtool)")
        self.visit_repo_check.setChecked(False)
        layout.addWidget(self.visit_repo_check)

        self.launch_check = QCheckBox("启动 B站视频解析工具V1.9")
        self.launch_check.setChecked(True)
        layout.addWidget(self.launch_check)

        layout.addStretch()

        self.setLayout(layout)


class InstallerWizard(QWizard):
    """安装向导"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("B站视频解析工具 V1.9 安装程序")
        self.setMinimumSize(800, 600)
        self.resize(800, 600)
        self.setWizardStyle(QWizard.ModernStyle)

        self.install_success = False
        self.install_message = ""
        self.install_path = ""

        # 设置logo
        self.setLogo()

        # 添加页面
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

        # 连接按钮
        self.button(QWizard.FinishButton).clicked.connect(self.on_finish)

        # 自定义按钮文本
        self.setButtonText(QWizard.BackButton, "< 上一步")
        self.setButtonText(QWizard.NextButton, "下一步 >")
        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")

        # 应用样式
        self.apply_stylesheet()

    def setLogo(self):
        """设置窗口logo"""
        logo_paths = []
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            logo_paths.append(os.path.join(sys._MEIPASS, "logo.ico"))
            logo_paths.append(os.path.join(sys._MEIPASS, "logo.png"))
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logo_paths.append(os.path.join(script_dir, "logo.ico"))
            logo_paths.append(os.path.join(script_dir, "logo.png"))
            logo_paths.append(os.path.join(script_dir, "dist", "logo.ico"))
            logo_paths.append(os.path.join(script_dir, "dist", "logo.png"))

        for path in logo_paths:
            if os.path.exists(path):
                try:
                    from PyQt5.QtGui import QIcon, QPixmap
                    self.setWindowIcon(QIcon(path))
                    self.logo_path = path
                    break
                except:
                    pass

    def apply_stylesheet(self):
        """应用美化样式"""
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
            QPushButton[objectName="cancel"] {
                background-color: #999999;
            }
            QPushButton[objectName="cancel"]:hover {
                background-color: #777777;
            }
            QCheckBox {
                spacing: 8px;
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
            }
            QProgressBar::chunk {
                background-color: #00a1d6;
                border-radius: 6px;
            }
        """)

    def on_finish(self):
        """点击完成按钮"""
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
        """启动主程序"""
        install_path = self.path_page.path_edit.text()
        exe_path = None
        
        # 查找V1.9_main.exe
        for root, dirs, files in os.walk(install_path):
            if "V1.9_main.exe" in files:
                exe_path = os.path.join(root, "V1.9_main.exe")
                break
        
        if not exe_path:
            # 查找第一个exe文件
            for root, dirs, files in os.walk(install_path):
                for f in files:
                    if f.endswith('.exe'):
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
