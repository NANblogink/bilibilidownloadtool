#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频编码检测与转换工具

功能：
1. 支持拖入视频文件进行编码信息检测
2. 支持自由转换视频编码格式
3. 检测视频的编码、分辨率、时长等信息
4. 支持将AV1/HEVC等编码转换为H.264，确保Windows播放器支持
"""

import os
import sys
import json
import subprocess
from tkinter import Tk, Label, Button, Entry, Text, Frame, filedialog
from tkinter import ttk
from tkinterdnd2 import TkinterDnD, DND_FILES

class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("视频编码检测与转换工具")
        self.root.geometry("900x600")
        self.root.minsize(900, 600)
        
        # 设置FFmpeg路径
        self.ffmpeg_path = self._get_ffmpeg_path()
        
        # 创建界面
        self.create_widgets()
        
    def _get_ffmpeg_path(self):
        """获取FFmpeg路径"""
        # 先尝试系统环境变量中的FFmpeg
        import shutil
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg and os.path.exists(ffmpeg):
            return ffmpeg
        
        # 尝试本地FFmpeg
        import sys
        if hasattr(sys, '_MEIPASS'):
            # EXE模式
            local_ffmpeg = os.path.join(sys._MEIPASS, 'ffmpeg', 'bin', 'ffmpeg.exe')
        else:
            # 开发模式
            local_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', 'ffmpeg.exe')
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg
        
        return None
    
    def create_widgets(self):
        """创建界面组件"""
        # 顶部标题
        title_frame = Frame(self.root)
        title_frame.pack(pady=20)
        
        title_label = Label(title_frame, text="视频编码检测与转换工具", font=("微软雅黑", 16, "bold"))
        title_label.pack()
        
        # 拖放区域
        drop_frame = Frame(self.root, bd=2, relief="groove", bg="#f0f0f0")
        drop_frame.pack(padx=20, pady=10, fill="x")
        
        drop_label = Label(drop_frame, text="请拖放视频文件到此处", font=("微软雅黑", 12), bg="#f0f0f0")
        drop_label.pack(pady=40)
        
        # 绑定拖放事件
        drop_frame.drop_target_register(DND_FILES)
        drop_frame.dnd_bind('<<Drop>>', self.on_drop)
        
        # 文件路径输入
        input_frame = Frame(self.root)
        input_frame.pack(padx=20, pady=10, fill="x")
        
        Label(input_frame, text="视频文件:", font=("微软雅黑", 10)).pack(side="left")
        self.file_entry = Entry(input_frame, width=60, font=("微软雅黑", 10))
        self.file_entry.pack(side="left", fill="x", expand=True, padx=10)
        
        browse_btn = Button(input_frame, text="浏览", command=self.browse_file, font=("微软雅黑", 10))
        browse_btn.pack(side="right")
        
        # 检测按钮
        detect_btn = Button(self.root, text="检测视频信息", command=self.detect_video, font=("微软雅黑", 10))
        detect_btn.pack(pady=10)
        
        # 左右分栏布局
        main_frame = Frame(self.root)
        main_frame.pack(padx=20, pady=10, fill="both", expand=True)
        
        # 左侧：视频信息
        left_frame = Frame(main_frame, bd=2, relief="groove")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        Label(left_frame, text="视频信息:", font=("微软雅黑", 10)).pack(anchor="w", padx=10, pady=5)
        
        self.info_text = Text(left_frame, font=("微软雅黑", 10), wrap="word")
        self.info_text.pack(fill="both", expand=True, padx=10, pady=5)
        
        # 右侧：转换设置
        right_frame = Frame(main_frame, bd=2, relief="groove", width=400)
        right_frame.pack(side="right", fill="both", expand=False)
        
        Label(right_frame, text="转换设置:", font=("微软雅黑", 10)).pack(anchor="w", padx=10, pady=10)
        
        # 目标编码
        codec_frame = Frame(right_frame)
        codec_frame.pack(padx=10, pady=10, fill="x")
        
        Label(codec_frame, text="目标编码:", font=("微软雅黑", 10)).pack(side="left")
        
        self.codec_var = ttk.Combobox(codec_frame, values=[
            "H.264 (libx264)", 
            "H.265 (libx265)", 
            "AV1 (libaom-av1)",
            "MPEG-4 (mpeg4)",
            "VP8 (libvpx)",
            "VP9 (libvpx-vp9)"
        ], font=("微软雅黑", 10), width=25)
        self.codec_var.current(0)  # 默认选择H.264
        self.codec_var.pack(side="left", padx=10, fill="x", expand=True)
        
        # 转换质量
        quality_frame = Frame(right_frame)
        quality_frame.pack(padx=10, pady=10, fill="x")
        
        Label(quality_frame, text="转换质量:", font=("微软雅黑", 10)).pack(side="left")
        
        self.quality_var = ttk.Combobox(quality_frame, values=[
            "低质量 (快速) - crf 30",
            "中质量 (平衡) - crf 23",
            "高质量 (慢速) - crf 18"
        ], font=("微软雅黑", 10), width=25)
        self.quality_var.current(1)  # 默认选择中质量
        self.quality_var.pack(side="left", padx=10, fill="x", expand=True)
        
        # 输出路径
        output_frame = Frame(right_frame)
        output_frame.pack(padx=10, pady=10, fill="x")
        
        Label(output_frame, text="输出路径:", font=("微软雅黑", 10)).pack(side="left")
        self.output_entry = Entry(output_frame, font=("微软雅黑", 10))
        self.output_entry.pack(side="left", fill="x", expand=True, padx=10)
        
        output_btn = Button(output_frame, text="浏览", command=self.browse_output, font=("微软雅黑", 10))
        output_btn.pack(side="right")
        
        # 转换按钮
        convert_btn = Button(right_frame, text="开始转换", command=self.convert_video, font=("微软雅黑", 10), bg="#4CAF50", fg="white")
        convert_btn.pack(pady=20)
        
        # 状态信息
        self.status_label = Label(right_frame, text="就绪", font=("微软雅黑", 10), fg="#666666")
        self.status_label.pack(pady=10)
    
    def browse_file(self):
        """浏览文件"""
        file_path = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.wmv *.mov")])
        if file_path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, file_path)
            # 自动填充输出路径
            output_path = os.path.splitext(file_path)[0] + "_converted.mp4"
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, output_path)
    
    def browse_output(self):
        """浏览输出路径"""
        output_path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("MP4文件", "*.mp4")])
        if output_path:
            self.output_entry.delete(0, "end")
            self.output_entry.insert(0, output_path)
    
    def on_drop(self, event):
        """处理拖放事件"""
        file_path = event.data
        # 处理Windows路径格式
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        # 处理空格转义
        file_path = file_path.replace('\\ ', ' ')
        
        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, file_path)
        
        # 自动填充输出路径
        output_path = os.path.splitext(file_path)[0] + "_converted.mp4"
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, output_path)
        
        # 自动检测视频信息
        self.detect_video()
    
    def detect_video(self):
        """检测视频信息"""
        file_path = self.file_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            self.status_label.config(text="请选择有效的视频文件", fg="#ff0000")
            return
        
        if not self.ffmpeg_path:
            self.status_label.config(text="未找到FFmpeg，请确保FFmpeg已安装并添加到环境变量", fg="#ff0000")
            return
        
        self.status_label.config(text="正在检测视频信息...", fg="#0066cc")
        self.root.update()
        
        try:
            # 使用ffprobe获取视频信息
            cmd = [
                self.ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe'),
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False
            )
            
            output = result.stdout.decode('utf-8', errors='ignore')
            data = json.loads(output)
            
            # 解析视频信息
            info = []
            info.append(f"文件路径: {file_path}")
            info.append(f"文件大小: {self._format_size(os.path.getsize(file_path))}")
            
            # 格式信息
            format_info = data.get('format', {})
            info.append(f"格式: {format_info.get('format_name', '未知')}")
            info.append(f"时长: {self._format_duration(float(format_info.get('duration', 0)))}")
            info.append(f"比特率: {self._format_bitrate(int(format_info.get('bit_rate', 0)))}")
            
            # 流信息
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    info.append("\n视频流:")
                    info.append(f"  编码: {stream.get('codec_name', '未知')} ({stream.get('codec_long_name', '')})")
                    info.append(f"  分辨率: {stream.get('width', '未知')}x{stream.get('height', '未知')}")
                    info.append(f"  帧率: {eval(stream.get('r_frame_rate', '0/1')):.2f} fps")
                    info.append(f"  比特率: {self._format_bitrate(int(stream.get('bit_rate', 0)))}")
                elif stream.get('codec_type') == 'audio':
                    info.append("\n音频流:")
                    info.append(f"  编码: {stream.get('codec_name', '未知')} ({stream.get('codec_long_name', '')})")
                    info.append(f"  采样率: {stream.get('sample_rate', '未知')} Hz")
                    info.append(f"  声道数: {stream.get('channels', '未知')}")
                    info.append(f"  比特率: {self._format_bitrate(int(stream.get('bit_rate', 0)))}")
            
            # 检查是否需要转换
            video_codec = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_codec = stream.get('codec_name', 'unknown')
                    break
            
            if video_codec in ['av1', 'hevc', 'h265']:
                info.append("\n⚠️  检测到Windows播放器可能不支持的编码格式，建议转换为H.264")
            
            # 显示信息
            self.info_text.delete(1.0, "end")
            self.info_text.insert(1.0, "\n".join(info))
            
            self.status_label.config(text="检测完成", fg="#009900")
            
        except Exception as e:
            self.status_label.config(text=f"检测失败: {str(e)}", fg="#ff0000")
            self.info_text.delete(1.0, "end")
            self.info_text.insert(1.0, f"检测失败: {str(e)}")
    
    def convert_video(self):
        """转换视频编码"""
        file_path = self.file_entry.get().strip()
        output_path = self.output_entry.get().strip()
        
        if not file_path or not os.path.exists(file_path):
            self.status_label.config(text="请选择有效的视频文件", fg="#ff0000")
            return
        
        if not output_path:
            self.status_label.config(text="请设置输出路径", fg="#ff0000")
            return
        
        if not self.ffmpeg_path:
            self.status_label.config(text="未找到FFmpeg，请确保FFmpeg已安装并添加到环境变量", fg="#ff0000")
            return
        
        # 获取目标编码
        codec_map = {
            "H.264 (libx264)": "libx264",
            "H.265 (libx265)": "libx265",
            "AV1 (libaom-av1)": "libaom-av1",
            "MPEG-4 (mpeg4)": "mpeg4",
            "VP8 (libvpx)": "libvpx",
            "VP9 (libvpx-vp9)": "libvpx-vp9"
        }
        target_codec = codec_map.get(self.codec_var.get())
        
        # 获取转换质量
        quality_map = {
            "低质量 (快速) - crf 30": "30",
            "中质量 (平衡) - crf 23": "23",
            "高质量 (慢速) - crf 18": "18"
        }
        crf_value = quality_map.get(self.quality_var.get(), "23")
        
        # 启动转换线程
        import threading
        convert_thread = threading.Thread(
            target=self._convert_video_thread,
            args=(file_path, output_path, target_codec, crf_value)
        )
        convert_thread.daemon = True
        convert_thread.start()
    
    def _convert_video_thread(self, file_path, output_path, target_codec, crf_value):
        """转换视频的线程函数"""
        def update_status(text, fg):
            self.status_label.config(text=text, fg=fg)
            self.root.update()
        
        update_status("正在转换视频...", "#0066cc")
        print(f"[转换线程] 开始转换: {file_path}")
        print(f"[转换线程] 输出路径: {output_path}")
        print(f"[转换线程] 目标编码: {target_codec}, CRF: {crf_value}")
        
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', file_path,
                '-c:v', target_codec,
                '-preset', 'medium',
                '-crf', crf_value,
                '-c:a', 'copy',
                '-y',
                output_path
            ]
            
            print(f"[转换线程] 执行命令: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=True
            )
            
            # 使用gbk编码读取输出
            for line in process.stdout:
                try:
                    decoded_line = line.decode('utf-8', errors='replace').strip()
                    print(f"[FFmpeg] {decoded_line}")
                except Exception:
                    pass
            
            process.wait()
            print(f"[转换线程] FFmpeg进程结束，返回码: {process.returncode}")
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                def on_success():
                    update_status("转换完成", "#009900")
                    self.file_entry.delete(0, "end")
                    self.file_entry.insert(0, output_path)
                    self.detect_video()
                
                self.root.after(0, on_success)
            else:
                def on_error():
                    update_status("转换失败：输出文件不存在或为空", "#ff0000")
                
                self.root.after(0, on_error)
                
        except Exception as e:
            error_msg = str(e)
            print(f"[转换线程] 异常: {error_msg}")
            def on_exception():
                update_status(f"转换失败: {error_msg}", "#ff0000")
            
            self.root.after(0, on_exception)
    
    def _format_size(self, size):
        """格式化文件大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def _format_duration(self, duration):
        """格式化时长"""
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def _format_bitrate(self, bitrate):
        """格式化比特率"""
        if bitrate < 1024:
            return f"{bitrate} bps"
        elif bitrate < 1024 * 1024:
            return f"{bitrate / 1024:.2f} Kbps"
        else:
            return f"{bitrate / (1024 * 1024):.2f} Mbps"

if __name__ == "__main__":
    # 检查tkinterdnd2是否安装
    try:
        from tkinterdnd2 import TkinterDnD
    except ImportError:
        print("请安装tkinterdnd2库: pip install tkinterdnd2")
        sys.exit(1)
    
    root = TkinterDnD.Tk()
    app = VideoConverter(root)
    root.mainloop()
