#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
B站视频解析工具 卸载程序
注意: 此卸载程序仅适用于 Windows 平台
"""
import sys
import os

# 在导入PyQt5之前设置Qt平台插件路径，防止"no Qt platform plugin could be initialized"
if sys.platform == 'win32':
    try:
        _internal_dir = os.path.join(os.path.dirname(sys.executable), '_internal')
        for _search in [
            os.path.join(_internal_dir, 'PyQt5', 'Qt5', 'plugins', 'platforms'),
            os.path.join(_internal_dir, 'PyQt5', 'Qt', 'plugins', 'platforms'),
            os.path.join(_internal_dir, 'platforms'),
            os.path.join(os.path.dirname(sys.executable), 'platforms'),
        ]:
            if os.path.isdir(_search):
                os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = _search
                break
    except Exception:
        pass

if sys.platform != 'win32':
    print("此卸载程序仅适用于 Windows 平台")
    print("macOS 用户请直接删除应用目录即可")
    sys.exit(1)


import shutil
import winreg
import traceback

from PyQt5.QtWidgets import (
    QApplication, QWizard, QWizardPage, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QMessageBox, QGroupBox, QTextEdit,
    QCheckBox, QScrollArea, QTextBrowser
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

from app_config import APP_NAME, APP_VERSION, SHORTCUT_NAME, is_safe_install_path

REG_KEY = r"Software\BilibiliDownloadTool"


def markdown_to_html(text):
    """简单的Markdown转HTML函数"""
    text = text.replace('### ', '<h3>').replace('\n### ', '</h3>\n<h3>')
    text = text.replace('## ', '<h2>').replace('\n## ', '</h2>\n<h2>')
    text = text.replace('# ', '<h1>').replace('\n# ', '</h1>\n<h1>')
    text = text.replace('**', '<b>', 1).replace('**', '</b>', 1)
    text = text.replace('*', '<i>', 1).replace('*', '</i>', 1)
    import re
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
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
    
    return f'<html><body><p>{text}</p></body></html>'


class UninstallerThread(QThread):
    """卸载工作线程"""
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, install_path, remove_shortcuts, remove_env):
        super().__init__()
        self.install_path = install_path
        self.remove_shortcuts = remove_shortcuts
        self.remove_env = remove_env
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit("开始卸载...")
            self.progress_signal.emit(0, 100)

            # 步骤1：删除快捷方式
            if self.remove_shortcuts:
                self.log_signal.emit("正在删除快捷方式...")
                self.remove_shortcut("Desktop", SHORTCUT_NAME)
                self.remove_shortcut("StartMenu", SHORTCUT_NAME)
                self.log_signal.emit("快捷方式已删除")
            self.progress_signal.emit(30, 100)

            # 步骤2：移除环境变量
            if self.remove_env:
                self.log_signal.emit("正在移除环境变量...")
                self.remove_env_paths()
                self.log_signal.emit("环境变量已移除")
            self.progress_signal.emit(60, 100)

            # 步骤3：删除安装目录
            # 安全防护：校验路径，避免注册表 InstallPath 被篡改为驱动器根目录
            # （如 D:\）导致 shutil.rmtree 递归删除整盘数据
            safe, reason = is_safe_install_path(self.install_path)
            if not safe:
                err = f"拒绝删除安装目录：{reason}（路径：{self.install_path}）"
                self.log_signal.emit(err)
                self.finished_signal.emit(False, err)
                return
            self.log_signal.emit(f"正在删除安装目录: {self.install_path}")
            if os.path.exists(self.install_path):
                try:
                    shutil.rmtree(self.install_path)
                except Exception as e:
                    self.log_signal.emit(f"删除安装目录时出错：{e}")
                    self.finished_signal.emit(False, f"删除安装目录失败：{e}")
                    return
            self.log_signal.emit("安装目录已删除")
            self.progress_signal.emit(100, 100)

            self.finished_signal.emit(True, "卸载成功！")

        except Exception as e:
            error_msg = f"卸载失败：{str(e)}\n{traceback.format_exc()}"
            self.log_signal.emit(error_msg)
            self.finished_signal.emit(False, str(e))

    def remove_shortcut(self, location, name):
        """删除快捷方式"""
        try:
            if location == "Desktop":
                shortcut_path = os.path.join(os.path.expanduser('~'), 'Desktop', f"{name}.lnk")
            else:
                shortcut_path = os.path.join(
                    os.path.expanduser('~'),
                    'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs',
                    f"{name}.lnk"
                )
            
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
        except Exception as e:
            self.log_signal.emit(f"删除快捷方式失败：{str(e)}")

    def remove_env_paths(self):
        """从环境变量中移除ffmpeg和bento4路径"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
            try:
                current_path, _ = winreg.QueryValueEx(key, "Path")
            except:
                current_path = ""

            if current_path:
                paths = current_path.split(';')
                new_paths = []
                for path in paths:
                    path = path.strip()
                    if path and ("ffmpeg" not in path.lower() or "bento4" not in path.lower()):
                        new_paths.append(path)
                
                new_path_str = ';'.join(new_paths)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_path_str)
                self.log_signal.emit("环境变量更新成功")

            winreg.CloseKey(key)
        except Exception as e:
            self.log_signal.emit(f"移除环境变量失败：{str(e)}")


class ConfirmPage(QWizardPage):
    """确认卸载页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("确认卸载")
        self.setSubTitle("请确认您要卸载" + SHORTCUT_NAME)

        layout = QVBoxLayout()

        warning_label = QLabel("警告：此操作将删除软件及其相关文件！")
        warning_font = QFont("Microsoft YaHei", 12)
        warning_font.setBold(True)
        warning_label.setFont(warning_font)
        warning_label.setStyleSheet("color: #d9534f;")
        layout.addWidget(warning_label)

        layout.addSpacing(15)

        info_text = """
# 卸载选项

---

## 卸载内容

- 删除安装目录及所有文件
- 删除桌面快捷方式
- 删除开始菜单快捷方式
- 从系统环境变量中移除FFmpeg和Bento4路径

---

**注意：此操作不可撤销，请确保已备份重要数据。**
        """

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        text_browser = QTextBrowser()
        text_browser.setReadOnly(True)
        text_browser.setHtml(markdown_to_html(info_text.strip()))
        scroll.setWidget(text_browser)
        layout.addWidget(scroll)

        layout.addSpacing(15)

        self.remove_shortcuts = QCheckBox("删除桌面和开始菜单快捷方式")
        self.remove_shortcuts.setChecked(True)
        layout.addWidget(self.remove_shortcuts)

        self.remove_env = QCheckBox("从环境变量中移除FFmpeg和Bento4路径")
        self.remove_env.setChecked(True)
        layout.addWidget(self.remove_env)

        self.setLayout(layout)


class UninstallPage(QWizardPage):
    """卸载页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("正在卸载")
        self.setSubTitle("正在卸载" + SHORTCUT_NAME + "，请稍候...")

        self.uninstall_thread = None
        self.is_uninstalling = False

        layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备卸载...")
        layout.addWidget(self.status_label)

        group = QGroupBox("卸载日志")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        group.setLayout(log_layout)
        layout.addWidget(group)

        self.setLayout(layout)

    def initializePage(self):
        if not self.is_uninstalling:
            self.start_uninstall()

    def start_uninstall(self):
        self.is_uninstalling = True
        wizard = self.wizard()

        install_path = self.get_install_path()
        remove_shortcuts = wizard.page(0).remove_shortcuts.isChecked()
        remove_env = wizard.page(0).remove_env.isChecked()

        self.log_text.append("开始卸载...")
        self.log_text.append(f"安装路径：{install_path}")

        wizard.button(QWizard.CancelButton).setEnabled(False)
        wizard.button(QWizard.BackButton).setEnabled(False)

        self.uninstall_thread = UninstallerThread(install_path, remove_shortcuts, remove_env)
        self.uninstall_thread.log_signal.connect(self.append_log)
        self.uninstall_thread.progress_signal.connect(self.update_progress)
        self.uninstall_thread.finished_signal.connect(self.uninstall_finished)
        self.uninstall_thread.start()

    def get_install_path(self):
        """从注册表获取安装路径"""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                                r"Software\BilibiliDownloadTool", 0, winreg.KEY_READ)
            install_path, _ = winreg.QueryValueEx(key, "InstallPath")
            winreg.CloseKey(key)
            return install_path
        except:
            return os.path.join(os.path.expanduser('~'), 'AppData', 'Local', 'BilibiliDownloader')

    def append_log(self, msg):
        self.log_text.append(msg)
        self.log_text.moveCursor(QTextCursor.End)

    def update_progress(self, current, total):
        self.progress_bar.setValue(current)
        self.status_label.setText(f"正在卸载... {current}%")

    def uninstall_finished(self, success, message):
        wizard = self.wizard()
        wizard.uninstall_success = success
        wizard.uninstall_message = message

        if success:
            self.log_text.append("\n卸载完成！")
            wizard.button(QWizard.NextButton).setEnabled(True)
            wizard.next()
        else:
            self.log_text.append(f"\n卸载失败：{message}")
            wizard.button(QWizard.CancelButton).setEnabled(True)
            QMessageBox.critical(self, "卸载失败", message)


class FinishPage(QWizardPage):
    """完成页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("卸载完成")
        self.setSubTitle("已成功卸载" + SHORTCUT_NAME)

        layout = QVBoxLayout()

        info_label = QLabel("软件已成功卸载！")
        info_font = QFont("Microsoft YaHei", 12)
        info_label.setFont(info_font)
        layout.addWidget(info_label)

        layout.addSpacing(10)

        note_label = QLabel("如果您在使用过程中有任何问题或建议，欢迎访问我们的项目主页。")
        note_label.setStyleSheet("color: #666;")
        layout.addWidget(note_label)

        layout.addSpacing(10)

        link_label = QLabel()
        link_label.setText('<a href="https://github.com/NANblogink/bilibilidownloadtool">项目仓库</a>')
        link_label.setOpenExternalLinks(True)
        layout.addWidget(link_label)

        layout.addStretch()

        self.setLayout(layout)


class UninstallerWizard(QWizard):
    """卸载向导"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME + " " + APP_VERSION + " 卸载程序")
        self.setMinimumSize(600, 450)
        self.resize(650, 500)
        self.setWizardStyle(QWizard.ModernStyle)

        self.uninstall_success = False
        self.uninstall_message = ""

        self.confirm_page = ConfirmPage(self)
        self.addPage(self.confirm_page)

        self.uninstall_page = UninstallPage(self)
        self.addPage(self.uninstall_page)

        self.finish_page = FinishPage(self)
        self.addPage(self.finish_page)

        self.setButtonText(QWizard.BackButton, "< 上一步")
        self.setButtonText(QWizard.NextButton, "下一步 >")
        self.setButtonText(QWizard.FinishButton, "完成")
        self.setButtonText(QWizard.CancelButton, "取消")


def is_installed():
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


def main():
    # 尝试GUI模式
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # 检查是否已安装
        installed, install_path = is_installed()
        if not installed:
            QMessageBox.warning(None, "未安装", "未检测到" + SHORTCUT_NAME + "已安装！", QMessageBox.Ok)
            sys.exit(0)

        wizard = UninstallerWizard()
        wizard.show()

        sys.exit(app.exec_())
    except Exception as e:
        # GUI失败时降级到命令行模式
        print(f"GUI模式启动失败: {e}")
        print("切换到命令行卸载模式...")
        cli_uninstall()


def cli_uninstall():
    """命令行卸载模式（GUI失败时的降级方案）"""
    print("=" * 50)
    print(APP_NAME + " " + APP_VERSION + " 命令行卸载程序")
    print("=" * 50)
    
    installed, install_path = is_installed()
    if not installed:
        print("未检测到已安装的" + SHORTCUT_NAME)
        input("按回车键退出...")
        sys.exit(0)
    
    print(f"检测到安装路径: {install_path}")
    confirm = input("确认卸载？(y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消卸载")
        sys.exit(0)
    
    # 删除快捷方式
    try:
        desktop = os.path.join(os.path.expanduser('~'), 'Desktop', SHORTCUT_NAME + '.lnk')
        startmenu = os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'Microsoft', 'Windows', 'Start Menu', 'Programs', SHORTCUT_NAME + '.lnk')
        for sc in [desktop, startmenu]:
            if os.path.exists(sc):
                os.remove(sc)
                print(f"已删除: {sc}")
    except Exception as e:
        print(f"删除快捷方式失败: {e}")
    
    # 移除环境变量
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
        try:
            current_path, _ = winreg.QueryValueEx(key, "Path")
        except Exception:
            current_path = ""
        if current_path:
            paths = current_path.split(';')
            new_paths = [p for p in paths if p.strip() and "ffmpeg" not in p.lower() and "bento4" not in p.lower()]
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ';'.join(new_paths))
            print("环境变量已更新")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"移除环境变量失败: {e}")
    
    # 删除安装目录
    # 安全防护：校验路径，避免注册表 InstallPath 为驱动器根目录导致整盘被删
    safe, reason = is_safe_install_path(install_path)
    if not safe:
        print(f"!! 拒绝删除安装目录：{reason}（路径：{install_path}）")
        print("!! 卸载中止，请手动检查注册表 HKCU\\Software\\BilibiliDownloadTool\\InstallPath")
        input("按回车键退出...")
        sys.exit(1)
    if os.path.exists(install_path):
        try:
            shutil.rmtree(install_path)
            print(f"安装目录已删除: {install_path}")
        except Exception as e:
            print(f"删除安装目录失败: {e}")
    
    # 删除注册表项
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\BilibiliDownloadTool")
        print("注册表项已删除")
    except Exception:
        pass
    
    print("\n卸载完成！")
    input("按回车键退出...")


if __name__ == '__main__':
    main()
