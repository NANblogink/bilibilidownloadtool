
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
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
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

            subprocess.run(["powershell", "Add-AppxPackage", save_path], check=True, timeout=60,
                          creationflags=subprocess.CREATE_NO_WINDOW)
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

def generate_qrcode(url):
    try:
        import qrcode
        import io
        from PyQt5.QtGui import QImage, QPainter, QColor
        from PyQt5.QtCore import Qt, QBuffer, QIODevice
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        qr.add_data(url)
        qr.make(fit=True)
        
        # 获取QR矩阵
        matrix = qr.get_matrix()
        box_size = 10
        border = 4
        
        # 计算尺寸
        qr_size = len(matrix)
        width = (qr_size + border * 2) * box_size
        height = width
        
        # 创建PyQt5图像
        image = QImage(width, height, QImage.Format_RGB32)
        image.fill(QColor(255, 255, 255))  # 白色背景
        
        painter = QPainter(image)
        painter.setBrush(QColor(0, 0, 0))  # 黑色前景
        painter.setPen(Qt.NoPen)
        
        # 绘制二维码
        for y in range(qr_size):
            for x in range(qr_size):
                if matrix[y][x]:
                    painter.drawRect(
                        (x + border) * box_size,
                        (y + border) * box_size,
                        box_size,
                        box_size
                    )
        
        painter.end()
        
        # 保存到buffer
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        
        # 转换为BytesIO
        bytesio = io.BytesIO(buffer.data())
        bytesio.seek(0)
        
        return bytesio
    except ImportError as e:
        raise Exception(f"缺少必要的库：{str(e)}，请安装 qrcode")
    except Exception as e:
        raise Exception(f"生成二维码失败：{str(e)}")

class LoginPollThread(QThread):
    status_signal = pyqtSignal(dict)
    
    def __init__(self, parser, qrcode_key):
        super().__init__()
        self.parser = parser
        self.qrcode_key = qrcode_key
        self.is_running = True
    
    def run(self):
        start_time = time.time()
        timeout = 180  
        
        while self.is_running:
            
            if time.time() - start_time > timeout:
                self.status_signal.emit({"success": False, "status": "二维码已超时", "code": 86038})
                break
            
            
            result = self.parser.poll_login_status(self.qrcode_key)
            self.status_signal.emit(result)
            
            
            if result.get("success") or result.get("code") == 86038:
                break
            
            
            time.sleep(1)
    
    def stop(self):
        self.is_running = False