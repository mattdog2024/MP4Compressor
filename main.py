import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess
import threading
import os
import sys
import shutil
import re
import time

# 设置外观模式 - 亮色
ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

class LogWindow(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.geometry("600x400")
        self.title("运行日志")
        
        # 设置图标
        try:
            if hasattr(self.master, 'get_resource_path'):
                icon_path = self.master.get_resource_path("tubiao.ico")
                if icon_path and os.path.exists(icon_path):
                    self.after(200, lambda: self.iconbitmap(icon_path))
        except:
            pass
        
        # 增大字号，加粗，使用黑色字体
        self.textbox = ctk.CTkTextbox(self, font=("SimHei", 14, "bold"), text_color="black")
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)
    
    def log(self, message):
        self.textbox.insert("end", message + "\n")
        self.textbox.see("end")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 1. 强制设置 AppUserModelID，让任务栏图标生效
        try:
            import ctypes
            myappid = 'mp4compressor.pro.v1.0' 
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        self.title("MP4/MKV 便携压缩器 PRO - 800x450 (VBR 800k)")
        self.geometry("800x700")
        
        # 2. 设置窗口图标 (左上角 + 任务栏)
        try:
            icon_path = self.get_resource_path("tubiao.ico")
            if icon_path and os.path.exists(icon_path):
                self.iconbitmap(icon_path)
                # 额外尝试：如果是打包环境，有时需要重新设置以确保任务栏图标刷新
                self.after(200, lambda: self.iconbitmap(icon_path))
        except Exception as e:
            print(f"Set icon error: {e}")

        # 变量
        self.file_list = []
        self.is_processing = False
        self.stop_event = threading.Event()
        self.current_process = None
        self.encoder_name = "libx264" # 默认 CPU
        self.encoder_display = "CPU"
        self.log_window = None
        self.output_dir = None
        
        # 布局配置
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) 

        # 1. 顶部标题区域
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        
        self.label_title = ctk.CTkLabel(self.header_frame, text="✨ 视频压缩工具", font=ctk.CTkFont(family="SimHei", size=24, weight="bold"))
        self.label_title.pack(side="left")
        
        self.label_info = ctk.CTkLabel(self.header_frame, text="800x450 | VBR 800k | 智能GPU加速", font=ctk.CTkFont(family="SimHei", size=14), text_color="gray")
        self.label_info.pack(side="right", anchor="s", pady=5)

        # 2. 设置区域
        self.settings_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray85")) 
        self.settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure(1, weight=1)
        
        # 2.1 音量控制
        self.label_vol = ctk.CTkLabel(self.settings_frame, text="音量调整 (0%-200%):", font=ctk.CTkFont(family="SimHei", size=14))
        self.label_vol.grid(row=0, column=0, padx=15, pady=(15, 5))
        
        self.slider_vol = ctk.CTkSlider(self.settings_frame, from_=0.0, to=2.0, number_of_steps=20)
        self.slider_vol.set(1.0) 
        self.slider_vol.grid(row=0, column=1, padx=10, pady=(15, 5), sticky="ew")
        
        self.label_vol_val = ctk.CTkLabel(self.settings_frame, text="100%", width=50, font=("SimHei", 12))
        self.label_vol_val.grid(row=0, column=2, padx=15, pady=(15, 5))
        self.slider_vol.configure(command=self.update_vol_label)

        # 2.2 输出目录
        self.label_out = ctk.CTkLabel(self.settings_frame, text="输出目录:", font=ctk.CTkFont(family="SimHei", size=14))
        self.label_out.grid(row=1, column=0, padx=15, pady=(5, 15))

        self.entry_out = ctk.CTkEntry(self.settings_frame, placeholder_text="默认: 保存在原视频同级目录下", font=("SimHei", 12))
        self.entry_out.grid(row=1, column=1, padx=10, pady=(5, 15), sticky="ew")
        self.entry_out.configure(state="disabled") 

        self.btn_browse = ctk.CTkButton(self.settings_frame, text="选择...", width=80, command=self.select_output_folder, font=("SimHei", 14, "bold"), fg_color="#1f538d", text_color="white")
        self.btn_browse.grid(row=1, column=2, padx=15, pady=(5, 15))

        # 3. 文件列表区域
        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, padx=20, pady=5, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.list_frame.grid_rowconfigure(0, weight=1)

        self.file_listbox = tk.Listbox(
            self.list_frame, 
            bg="#ffffff", 
            fg="#333333", 
            selectbackground="#3B8ED0", 
            selectforeground="white",
            font=("SimHei", 12),
            borderwidth=0, 
            highlightthickness=1,
            highlightbackground="#d1d1d1"
        )
        self.file_listbox.grid(row=0, column=0, sticky="nsew")
        
        self.scrollbar = ctk.CTkScrollbar(self.list_frame, command=self.file_listbox.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.file_listbox.configure(yscrollcommand=self.scrollbar.set)

        # 4. 按钮操作区域
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        
        self.btn_add = ctk.CTkButton(self.btn_frame, text="+ 添加视频", command=self.add_files, width=120, height=35, font=("SimHei", 13))
        self.btn_add.pack(side="left", padx=(0, 10))
        
        self.btn_clear = ctk.CTkButton(self.btn_frame, text="清空", command=self.clear_files, width=80, height=35, fg_color="transparent", border_width=1, text_color="gray", font=("SimHei", 13))
        self.btn_clear.pack(side="left")

        self.btn_log = ctk.CTkButton(self.btn_frame, text="查看日志", command=self.open_log_window, width=80, height=35, fg_color="transparent", border_width=1, text_color="gray", font=("SimHei", 13))
        self.btn_log.pack(side="left", padx=10)

        self.btn_start = ctk.CTkButton(self.btn_frame, text="开始压缩", command=self.start_processing_thread, width=150, height=40, font=("SimHei", 14, "bold"), fg_color="#2CC985", hover_color="#22A56A")
        self.btn_start.pack(side="right")
        
        self.btn_stop = ctk.CTkButton(self.btn_frame, text="停止", command=self.stop_processing, width=100, height=40, font=("SimHei", 14, "bold"), fg_color="#E74C3C", hover_color="#C0392B", state="disabled")
        self.btn_stop.pack(side="right", padx=10)

        # 5. 状态与进度区域
        self.status_frame = ctk.CTkFrame(self, fg_color=("gray95", "gray20"))
        self.status_frame.grid(row=4, column=0, padx=20, pady=(10, 20), sticky="ew")
        
        self.status_label = ctk.CTkLabel(self.status_frame, text="准备就绪", font=("SimHei", 12))
        self.status_label.pack(pady=(10, 5), padx=10, anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(self.status_frame, height=12)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 15))
        self.progress_bar.set(0)

        self.after(1000, self.open_log_window)
        self.after(500, self.check_environment)

    def get_resource_path(self, relative_path):
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)

    def select_output_folder(self):
        folder = filedialog.askdirectory(title="选择保存目录")
        if folder:
            self.output_dir = folder
            self.entry_out.configure(state="normal")
            self.entry_out.delete(0, "end")
            self.entry_out.insert(0, folder)
            self.entry_out.configure(state="disabled")
            self.log_msg(f"输出目录已设置为: {folder}")

    def log_msg(self, msg):
        print(msg) 
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.log(msg)

    def open_log_window(self):
        if self.log_window is None or not self.log_window.winfo_exists():
            self.log_window = LogWindow(self)
        self.log_window.focus()

    def update_vol_label(self, value):
        self.label_vol_val.configure(text=f"{int(value * 100)}%")

    def get_ffmpeg_path(self):
        # 1. PyInstaller
        if hasattr(sys, '_MEIPASS'):
            bundled_path = os.path.join(sys._MEIPASS, "ffmpeg", "bin", "ffmpeg.exe")
            if os.path.exists(bundled_path):
                return bundled_path

        # 2. Local
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        
        possible_paths = [
            os.path.join(base_path, "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(base_path, "ffmpeg.exe"),
            "ffmpeg.exe"
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return os.path.abspath(path)
        
        # 3. System
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg
        
        return None

    def check_environment(self):
        ffmpeg = self.get_ffmpeg_path()
        if not ffmpeg:
            self.status_label.configure(text="❌ 未找到 FFmpeg", text_color="red")
            self.log_msg("错误: 无法找到 ffmpeg.exe")
            self.btn_start.configure(state="disabled")
            return
        
        self.log_msg(f"FFmpeg 路径: {ffmpeg}")
        self.status_label.configure(text="正在检测 GPU 加速...", text_color="black")
        threading.Thread(target=self.detect_best_encoder, args=(ffmpeg,), daemon=True).start()
    
    def detect_best_encoder(self, ffmpeg_path):
        self.log_msg("开始检测编码器...")
        encoders_supported = []
        try:
            res = subprocess.run([ffmpeg_path, "-hide_banner", "-encoders"], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if "h264_nvenc" in res.stdout: encoders_supported.append("h264_nvenc")
            if "h264_amf" in res.stdout: encoders_supported.append("h264_amf")
            if "h264_qsv" in res.stdout: encoders_supported.append("h264_qsv")
            self.log_msg(f"FFmpeg 支持的硬件编码器: {encoders_supported}")
        except Exception as e:
            self.log_msg(f"获取编码器列表出错: {e}")
            
        self.encoder_name = "libx264"
        self.encoder_display = "CPU (x264)"
        
        priority_list = [
            ("h264_nvenc", "NVIDIA NVENC"),
            ("h264_amf", "AMD AMF"),
            ("h264_qsv", "Intel QSV")
        ]
        
        found_gpu = False
        for enc, display_name in priority_list:
            if enc in encoders_supported:
                self.log_msg(f"正在测试硬件可用性: {enc} ...")
                success, error_msg = self.test_encoder(ffmpeg_path, enc)
                if success:
                    self.encoder_name = enc
                    self.encoder_display = display_name
                    found_gpu = True
                    self.log_msg(f"✅ 成功激活编码器: {display_name}")
                    break
                else:
                    self.log_msg(f"❌ 编码器 {enc} 不可用.\n原因: {error_msg}")
        
        if not found_gpu:
            self.log_msg("⚠️ 未检测到可用的 GPU 硬件，已回退到 CPU 编码。")

        self.after(0, lambda: self.status_label.configure(text=f"就绪 | 当前编码器: {self.encoder_display}", text_color="green" if found_gpu else "black"))

    def test_encoder(self, ffmpeg, encoder):
        try:
            # 兼容性测试: YUV420P + 192x108
            cmd = [
                ffmpeg, "-hide_banner", 
                "-f", "lavfi", "-i", "testsrc=size=192x108:rate=30:duration=1", 
                "-vf", "format=yuv420p", 
                "-c:v", encoder, 
                "-f", "null", "-"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            )
            
            if result.returncode == 0:
                return True, "OK"
            else:
                err_log = result.stderr[-800:] if result.stderr else "No output"
                return False, f"测试失败。\n[命令]: {' '.join(cmd)}\n[错误日志]:\n{err_log}"
        except Exception as e:
            return False, str(e)

    def add_files(self):
        files = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.flv"), ("所有文件", "*.*")]
        )
        if files:
            for f in files:
                if f not in self.file_list:
                    self.file_list.append(f)
                    self.file_listbox.insert(tk.END, f)
            self.log_msg(f"添加了 {len(files)} 个文件")
            self.status_label.configure(text=f"已添加 {len(files)} 个文件")

    def clear_files(self):
        self.file_list = []
        self.file_listbox.delete(0, tk.END)
        self.status_label.configure(text="列表已清空")

    def start_processing_thread(self):
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加文件")
            return
        
        self.stop_event.clear()
        self.is_processing = True
        self.btn_start.configure(state="disabled")
        self.btn_add.configure(state="disabled")
        self.btn_clear.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.open_log_window() 
        
        threading.Thread(target=self.process_queue, daemon=True).start()

    def stop_processing(self):
        if self.is_processing:
            self.log_msg("正在停止任务...")
            self.stop_event.set()
            if self.current_process:
                try:
                    self.log_msg(f"强制终止 FFmpeg 进程 (PID: {self.current_process.pid})...")
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.current_process.pid)], creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                except Exception as e:
                    self.log_msg(f"停止失败: {e}")

    def process_queue(self):
        ffmpeg = self.get_ffmpeg_path()
        total = len(self.file_list)
        success_count = 0
        
        for i, file_path in enumerate(self.file_list):
            if self.stop_event.is_set():
                break
                
            fname = os.path.basename(file_path)
            self.update_ui_text(f"🚀 正在处理 ({i+1}/{total}): {fname}", 0)
            self.log_msg(f"=== 开始处理文件: {file_path} ===")
            
            success = self.run_ffmpeg_task(ffmpeg, file_path)
            
            if success:
                success_count += 1
                self.log_msg(f"=== 文件处理成功 ===")
            else:
                self.log_msg(f"=== 文件处理失败 ===")
                if self.stop_event.is_set():
                    self.update_ui_text("⚠️ 任务已终止", 0)
                    break 
        
        self.is_processing = False
        self.after(0, lambda: self.reset_ui(success_count, total))

    def run_ffmpeg_task(self, ffmpeg, input_path):
        directory, filename = os.path.split(input_path)
        name, _ = os.path.splitext(filename)
        output_filename = f"{name}_800x450_compressed.mp4"
        
        if self.output_dir and os.path.exists(self.output_dir):
            output_path = os.path.join(self.output_dir, output_filename)
        else:
            output_path = os.path.join(directory, output_filename)
        
        duration = 0
        try:
            probe = subprocess.run(
                [ffmpeg, "-hide_banner", "-i", input_path], 
                capture_output=True, 
                encoding='utf-8', 
                errors='replace',
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            )
            if probe.stderr:
                match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", probe.stderr)
                if match:
                    h, m, s = map(float, match.groups())
                    duration = h*3600 + m*60 + s
                self.log_msg(f"视频时长: {duration} 秒")
        except Exception as e:
            self.log_msg(f"Probe Error: {e}")

        vol_factor = self.slider_vol.get()
        
        cmd = [
            ffmpeg, "-y",
            "-i", input_path,
            "-vf", "scale=800:450",
            "-c:v", self.encoder_name,
            "-b:v", "800k",
            "-maxrate", "1200k",
            "-bufsize", "1600k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-af", f"volume={vol_factor:.2f}",
            output_path
        ]
        
        if "nvenc" in self.encoder_name:
            cmd.extend(["-preset", "p4"])
        elif "libx264" in self.encoder_name:
            cmd.extend(["-preset", "medium"])
            
        self.log_msg(f"执行命令: {' '.join(cmd)}")
        
        try:
            self.current_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                encoding='utf-8',
                errors='replace',
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            )
            
            while True:
                if self.stop_event.is_set():
                    self.current_process.kill()
                    return False
                    
                line = self.current_process.stdout.readline()
                if not line:
                    break
                
                if "Error" in line or "error" in line or "Invalid" in line:
                    self.log_msg(f"[FFmpeg Error]: {line.strip()}")
                
                if "time=" in line and duration > 0:
                    t_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
                    if t_match:
                        h, m, s = map(float, t_match.groups())
                        current_time = h*3600 + m*60 + s
                        percent = min(current_time / duration, 1.0)
                        self.update_ui_text(f"⏳ 处理中 {int(percent*100)}% - {os.path.basename(input_path)}", percent)
                
            self.current_process.wait()
            ret_code = self.current_process.returncode
            self.log_msg(f"FFmpeg 退出代码: {ret_code}")
            return ret_code == 0
            
        except Exception as e:
            self.log_msg(f"执行异常: {e}")
            import traceback
            self.log_msg(traceback.format_exc())
            return False
        finally:
            self.current_process = None

    def update_ui_text(self, text, progress):
        self.after(0, lambda: self._update_ui_progress(progress, text))
        
    def _update_ui_progress(self, val, text):
        self.progress_bar.set(val)
        self.status_label.configure(text=text)

    def reset_ui(self, count, total):
        self.btn_start.configure(state="normal")
        self.btn_add.configure(state="normal")
        self.btn_clear.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        
        if self.stop_event.is_set():
            self.status_label.configure(text="任务已手动停止", text_color="red")
        else:
            if count == total and total > 0:
                self.status_label.configure(text=f"✅ 完成！成功处理 {count}/{total} 个文件", text_color="green")
                self.progress_bar.set(1)
                messagebox.showinfo("完成", f"处理完成！\n成功: {count}\n总数: {total}")
            else:
                self.status_label.configure(text=f"⚠️ 完成，但有失败 (成功: {count}/{total})", text_color="orange")
                self.progress_bar.set(0)
                messagebox.showwarning("部分失败", f"处理结束。\n成功: {count}\n总数: {total}\n请查看日志了解详情。")

if __name__ == "__main__":
    app = App()
    app.mainloop()
