#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频编码检测与转换工具（跨平台版本）

功能：
1. 支持拖入视频文件进行编码信息检测
2. 支持自由转换视频编码格式
3. 检测视频的编码、分辨率、时长等信息
4. 支持将AV1/HEVC等编码转换为H.264
"""

import os
import sys
import json
import subprocess
from tkinter import Tk, Label, Button, Entry, Text, Frame, filedialog
from tkinter import ttk

IS_WINDOWS = sys.platform == 'win32'
IS_MACOS = sys.platform == 'darwin'


def _exe(name):
    if IS_WINDOWS:
        return name + '.exe'
    return name


def _setup_dnd(root, widget, callback):
    """跨平台拖放支持"""
    if IS_WINDOWS:
        try:
            from tkinterdnd2 import DND_FILES
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', callback)
            return True
        except ImportError:
            pass
    elif IS_MACOS:
        try:
            from tkdnd import TkDND
            TkDND(root).bind_target(widget, '<<Drop>>', callback)
            return True
        except ImportError:
            pass
    return False


class VideoConverter:
    def __init__(self, root):
        self.root = root
        self.root.title("视频编码检测与转换工具")
        self.root.geometry("900x600")
        self.root.minsize(900, 600)

        self.ffmpeg_path = self._get_ffmpeg_path()

        self.create_widgets()

    def _get_ffmpeg_path(self):
        """获取FFmpeg路径"""
        import shutil
        ffmpeg = shutil.which('ffmpeg')
        if ffmpeg and os.path.exists(ffmpeg):
            return ffmpeg

        if hasattr(sys, '_MEIPASS'):
            local_ffmpeg = os.path.join(sys._MEIPASS, 'ffmpeg', 'bin', _exe('ffmpeg'))
        else:
            local_ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg', 'bin', _exe('ffmpeg'))
        if os.path.exists(local_ffmpeg):
            return local_ffmpeg

        try:
            from tool_manager import get_tool_manager
            tool_manager = get_tool_manager()
            tool_paths = tool_manager.get_tool_paths()
            if os.path.exists(tool_paths['ffmpeg']):
                return tool_paths['ffmpeg']
        except ImportError:
            pass

        return None

    def _get_font(self):
        """获取跨平台字体"""
        if IS_MACOS:
            return ("PingFang SC", 10)
        elif IS_WINDOWS:
            return ("微软雅黑", 10)
        else:
            return ("Noto Sans CJK SC", 10)

    def create_widgets(self):
        """创建界面组件"""
        font = self._get_font()
        font_bold = (font[0], 16, "bold") if IS_MACOS else (font[0], 16, "bold")

        title_frame = Frame(self.root)
        title_frame.pack(pady=20)

        title_label = Label(title_frame, text="视频编码检测与转换工具", font=font_bold)
        title_label.pack()

        drop_frame = Frame(self.root, bd=2, relief="groove", bg="#f0f0f0")
        drop_frame.pack(padx=20, pady=10, fill="x")

        drop_label = Label(drop_frame, text="请拖放视频文件到此处，或点击下方浏览按钮", font=font, bg="#f0f0f0")
        drop_label.pack(pady=40)

        dnd_ok = _setup_dnd(self.root, drop_frame, self.on_drop)
        if not dnd_ok:
            drop_label.config(text="请点击下方浏览按钮选择视频文件")

        input_frame = Frame(self.root)
        input_frame.pack(padx=20, pady=10, fill="x")

        Label(input_frame, text="视频文件:", font=font).pack(side="left")
        self.file_entry = Entry(input_frame, width=60, font=font)
        self.file_entry.pack(side="left", fill="x", expand=True, padx=10)

        browse_btn = Button(input_frame, text="浏览", command=self.browse_file, font=font)
        browse_btn.pack(side="right")

        detect_btn = Button(self.root, text="检测视频信息", command=self.detect_video, font=font)
        detect_btn.pack(pady=10)

        main_frame = Frame(self.root)
        main_frame.pack(padx=20, pady=10, fill="both", expand=True)

        left_frame = Frame(main_frame, bd=2, relief="groove")
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        Label(left_frame, text="视频信息:", font=font).pack(anchor="w", padx=10, pady=5)

        self.info_text = Text(left_frame, font=font, wrap="word")
        self.info_text.pack(fill="both", expand=True, padx=10, pady=5)

        right_frame = Frame(main_frame, bd=2, relief="groove", width=400)
        right_frame.pack(side="right", fill="both", expand=False)

        Label(right_frame, text="转换设置:", font=font).pack(anchor="w", padx=10, pady=10)

        codec_frame = Frame(right_frame)
        codec_frame.pack(padx=10, pady=10, fill="x")

        Label(codec_frame, text="目标编码:", font=font).pack(side="left")

        self.codec_var = ttk.Combobox(codec_frame, values=[
            "H.264 (libx264)",
            "H.265 (libx265)",
            "AV1 (libaom-av1)",
            "MPEG-4 (mpeg4)",
            "VP8 (libvpx)",
            "VP9 (libvpx-vp9)"
        ], font=font, width=25)
        self.codec_var.current(0)
        self.codec_var.pack(side="left", padx=10, fill="x", expand=True)

        quality_frame = Frame(right_frame)
        quality_frame.pack(padx=10, pady=10, fill="x")

        Label(quality_frame, text="转换质量:", font=font).pack(side="left")

        self.quality_var = ttk.Combobox(quality_frame, values=[
            "低质量 (快速) - crf 30",
            "中质量 (平衡) - crf 23",
            "高质量 (慢速) - crf 18"
        ], font=font, width=25)
        self.quality_var.current(1)
        self.quality_var.pack(side="left", padx=10, fill="x", expand=True)

        output_frame = Frame(right_frame)
        output_frame.pack(padx=10, pady=10, fill="x")

        Label(output_frame, text="输出路径:", font=font).pack(side="left")
        self.output_entry = Entry(output_frame, font=font)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=10)

        output_btn = Button(output_frame, text="浏览", command=self.browse_output, font=font)
        output_btn.pack(side="right")

        convert_btn = Button(right_frame, text="开始转换", command=self.convert_video, font=font, bg="#4CAF50", fg="white")
        convert_btn.pack(pady=20)

        self.status_label = Label(right_frame, text="就绪", font=font, fg="#666666")
        self.status_label.pack(pady=10)

    def browse_file(self):
        """浏览文件"""
        file_path = filedialog.askopenfilename(filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.wmv *.mov *.flv *.webm")])
        if file_path:
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, file_path)
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
        if IS_WINDOWS:
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]
            file_path = file_path.replace('\\ ', ' ')
        elif IS_MACOS:
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]

        self.file_entry.delete(0, "end")
        self.file_entry.insert(0, file_path)

        output_path = os.path.splitext(file_path)[0] + "_converted.mp4"
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, output_path)

        self.detect_video()

    def detect_video(self):
        """检测视频信息"""
        file_path = self.file_entry.get().strip()
        if not file_path or not os.path.exists(file_path):
            self.status_label.config(text="请选择有效的视频文件", fg="#ff0000")
            return

        if not self.ffmpeg_path:
            self.status_label.config(text="未找到FFmpeg，请确保FFmpeg已安装", fg="#ff0000")
            return

        self.status_label.config(text="正在检测视频信息...", fg="#0066cc")
        self.root.update()

        try:
            ffprobe_path = None
            ffmpeg_dir = os.path.dirname(self.ffmpeg_path)
            if ffmpeg_dir:
                candidate = os.path.join(ffmpeg_dir, _exe('ffprobe'))
                if os.path.exists(candidate):
                    ffprobe_path = candidate
            if not ffprobe_path:
                import shutil as _shutil
                ffprobe_path = _shutil.which('ffprobe')
            if not ffprobe_path:
                self.status_label.config(text="未找到ffprobe，无法检测视频信息", fg="#ff0000")
                return
            cmd = [
                ffprobe_path,
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

            info = []
            info.append(f"文件路径: {file_path}")
            info.append(f"文件大小: {self._format_size(os.path.getsize(file_path))}")

            format_info = data.get('format', {})
            info.append(f"格式: {format_info.get('format_name', '未知')}")
            info.append(f"时长: {self._format_duration(float(format_info.get('duration', 0)))}")
            info.append(f"比特率: {self._format_bitrate(int(format_info.get('bit_rate', 0)))}")

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

            video_codec = None
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    video_codec = stream.get('codec_name', 'unknown')
                    break

            if video_codec in ['av1', 'hevc', 'h265']:
                info.append("\n⚠️  检测到可能不兼容的编码格式，建议转换为H.264")

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
            self.status_label.config(text="未找到FFmpeg，请确保FFmpeg已安装", fg="#ff0000")
            return

        codec_map = {
            "H.264 (libx264)": "libx264",
            "H.265 (libx265)": "libx265",
            "AV1 (libaom-av1)": "libaom-av1",
            "MPEG-4 (mpeg4)": "mpeg4",
            "VP8 (libvpx)": "libvpx",
            "VP9 (libvpx-vp9)": "libvpx-vp9"
        }
        target_codec = codec_map.get(self.codec_var.get())

        quality_map = {
            "低质量 (快速) - crf 30": "30",
            "中质量 (平衡) - crf 23": "23",
            "高质量 (慢速) - crf 18": "18"
        }
        crf_value = quality_map.get(self.quality_var.get(), "23")

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
                shell=IS_WINDOWS
            )

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
    if IS_WINDOWS:
        try:
            from tkinterdnd2 import TkinterDnD
            root = TkinterDnD.Tk()
        except ImportError:
            print("tkinterdnd2未安装，拖放功能不可用")
            root = Tk()
    else:
        root = Tk()
    app = VideoConverter(root)
    root.mainloop()
