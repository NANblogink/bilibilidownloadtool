# 作者：寒烟似雪
# QQ：2273962061
# 转载时请勿删除
import os
import time
import requests
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

class HEVCCheckThread(QThread):
    result_signal = pyqtSignal(bool)

    def run(self):
        try:
            import subprocess
            proc = subprocess.run(
                ["powershell", "Get-AppxPackage *HEVCVideoExtension*"],
                capture_output=True, text=True, timeout=10
            )
            self.result_signal.emit("HEVCVideoExtension" in proc.stdout)
        except Exception:
            self.result_signal.emit(False)

class HEVCDownloadThread(QThread):
    progress_signal = pyqtSignal(int)
    finish_signal = pyqtSignal(bool, str)

    def __init__(self, save_path, hevc_url):
        super().__init__()
        self.save_path = save_path
        self.hevc_url = hevc_url
        self.is_running = True

    def run(self):
        try:
            import subprocess
            filename = "Microsoft.HEVCVideoExtension.Appx"
            save_path = os.path.join(self.save_path, filename)

            resp = requests.get(self.hevc_url, stream=True, timeout=30)
            resp.raise_for_status()
            total_size = int(resp.headers.get('content-length', 0))
            downloaded_size = 0

            with open(save_path, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not self.is_running:
                        raise Exception("下载已取消")
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        progress = int((downloaded_size / total_size) * 100)
                        self.progress_signal.emit(progress)

            subprocess.run(["powershell", "Add-AppxPackage", save_path], check=True, timeout=60)
            self.finish_signal.emit(True, "HEVC扩展安装成功")
        except Exception as e:
            self.finish_signal.emit(False, f"HEVC处理失败：{str(e)}")

    def stop(self):
        self.is_running = False

def format_duration(seconds):
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"

def get_unique_filename(filename):
    if not os.path.exists(filename):
        return filename
    name, ext = os.path.splitext(filename)
    counter = 1
    while os.path.exists(f"{name}_{counter}{ext}"):
        counter += 1
    return f"{name}_{counter}{ext}"