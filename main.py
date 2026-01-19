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
import uuid
import tempfile
import concurrent.futures
import math

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
        self.file_subtitles = {}  # {video_path: subtitle_path}
        self.is_processing = False
        self.stop_event = threading.Event()
        self.current_process = None
        self.encoder_name = "libx264" # 默认 CPU
        self.encoder_display = "CPU"
        self.log_window = None
        self.output_dir = None
        self.active_processes = set()
        self.active_processes_lock = threading.Lock()
        self.total_files_count = 0
        self.finished_files_count = 0
        self.failed_files_count = 0
        
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
        
        self.slider_vol = ctk.CTkSlider(self.settings_frame, from_=0.0, to=2.0, number_of_steps=200)
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

        # 2.3 并行数量
        self.label_threads = ctk.CTkLabel(self.settings_frame, text="并行任务数:", font=ctk.CTkFont(family="SimHei", size=14))
        self.label_threads.grid(row=2, column=0, padx=15, pady=(5, 15))
        
        self.slider_threads = ctk.CTkSlider(self.settings_frame, from_=1, to=5, number_of_steps=4)
        self.slider_threads.set(3) # 默认3个，比较科学
        self.slider_threads.grid(row=2, column=1, padx=10, pady=(5, 15), sticky="ew")
        
        self.label_threads_val = ctk.CTkLabel(self.settings_frame, text="3", width=50, font=("SimHei", 12))
        self.label_threads_val.grid(row=2, column=2, padx=15, pady=(5, 15))
        self.slider_threads.configure(command=self.update_threads_label)

        # 2.4 高级选项 (跳过片头/片尾 + 去黑边)
        self.frame_advanced = ctk.CTkFrame(self.settings_frame, fg_color="transparent")
        self.frame_advanced.grid(row=3, column=0, columnspan=3, padx=15, pady=(5, 15), sticky="ew")
        
        # 跳过片头
        self.label_skip_start = ctk.CTkLabel(self.frame_advanced, text="跳过片头(秒):", font=("SimHei", 13))
        self.label_skip_start.pack(side="left", padx=(0, 5))
        self.entry_skip_start = ctk.CTkEntry(self.frame_advanced, width=60, font=("SimHei", 12))
        self.entry_skip_start.pack(side="left", padx=(0, 15))
        self.entry_skip_start.insert(0, "0")

        # 跳过片尾
        self.label_skip_end = ctk.CTkLabel(self.frame_advanced, text="跳过片尾(秒):", font=("SimHei", 13))
        self.label_skip_end.pack(side="left", padx=(0, 5))
        self.entry_skip_end = ctk.CTkEntry(self.frame_advanced, width=60, font=("SimHei", 12))
        self.entry_skip_end.pack(side="left", padx=(0, 15))
        self.entry_skip_end.insert(0, "0")

        # 去黑边
        self.var_crop = ctk.BooleanVar(value=False)
        self.check_crop = ctk.CTkCheckBox(self.frame_advanced, text="去除黑边 (自动裁剪)", variable=self.var_crop, font=("SimHei", 13))
        self.check_crop.pack(side="left", padx=(0, 5))

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
        
        self.btn_set_sub = ctk.CTkButton(self.btn_frame, text="设置字幕", command=self.set_subtitle, width=100, height=35, font=("SimHei", 13), fg_color="#E67E22", hover_color="#D35400")
        self.btn_set_sub.pack(side="left", padx=(0, 10))

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
            self.after(0, lambda: self.log_window.log(msg))

    def update_threads_label(self, value):
        self.label_threads_val.configure(text=f"{int(value)}")

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
            self.refresh_file_list()
            self.log_msg(f"添加了 {len(files)} 个文件")
            self.status_label.configure(text=f"已添加 {len(files)} 个文件")

    def refresh_file_list(self):
        self.file_listbox.delete(0, tk.END)
        for f in self.file_list:
            display_text = f
            if f in self.file_subtitles:
                sub_name = os.path.basename(self.file_subtitles[f])
                display_text += f"   [字幕: {sub_name}]"
            self.file_listbox.insert(tk.END, display_text)

    def clear_files(self):
        self.file_list = []
        self.file_subtitles = {}
        self.file_listbox.delete(0, tk.END)
        self.status_label.configure(text="列表已清空")

    def set_subtitle(self):
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先在列表中选择一个视频文件")
            return
        
        index = selection[0]
        video_path = self.file_list[index]
        
        # 简单的 MKV 检查 (可选，目前允许所有格式尝试加载字幕)
        # ext = os.path.splitext(video_path)[1].lower()
        # if ext != '.mkv':
        #     if not messagebox.askyesno("提示", "该功能主要是为 MKV 设计的，确认要为非 MKV 文件添加字幕吗？"):
        #         return

        sub_file = filedialog.askopenfilename(
            title="选择字幕文件",
            filetypes=[("字幕文件", "*.srt *.ass *.ssa"), ("所有文件", "*.*")]
        )
        
        if sub_file:
            self.file_subtitles[video_path] = sub_file
            self.refresh_file_list()
            self.log_msg(f"为 {os.path.basename(video_path)} 设置了字幕: {os.path.basename(sub_file)}")

    def start_processing_thread(self):
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加文件")
            return
        
        self.stop_event.clear()
        self.is_processing = True
        self.btn_start.configure(state="disabled")
        self.btn_add.configure(state="disabled")
        self.btn_clear.configure(state="disabled")
        self.btn_set_sub.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.open_log_window() 
        
        # 收集所有 UI 设置参数 (必须在主线程获取)
        settings = {
            "skip_start": self.entry_skip_start.get(),
            "skip_end": self.entry_skip_end.get(),
            "crop": self.var_crop.get(),
            "volume": round(self.slider_vol.get(), 2),
            "threads": self.slider_threads.get(),
            "output_dir": self.output_dir
        }

        threading.Thread(target=self.process_queue, args=(settings,), daemon=True).start()

    def stop_processing(self):
        if self.is_processing:
            self.log_msg("正在停止所有任务...")
            self.stop_event.set()
            
            with self.active_processes_lock:
                for proc in self.active_processes:
                    try:
                        self.log_msg(f"强制终止 FFmpeg 进程 (PID: {proc.pid})...")
                        subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)], creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
                    except Exception as e:
                        self.log_msg(f"停止失败: {e}")

    def process_queue(self, settings):
        ffmpeg = self.get_ffmpeg_path()
        self.total_files_count = len(self.file_list)
        self.finished_files_count = 0
        self.failed_files_count = 0
        
        # 初始化每个文件的进度 (0.0 - 1.0)
        self.file_progress_map = {f: 0.0 for f in self.file_list}
        self.file_progress_lock = threading.Lock()
        
        max_workers = int(settings["threads"])
        vol_debug = settings["volume"]
        self.log_msg(f"启动配置: 线程={max_workers}, 音量={int(round(vol_debug*100))}%, 裁剪={settings['crop']}, 跳过={settings['skip_start']}s/{settings['skip_end']}s")

        # 使用 ThreadPoolExecutor 进行并行处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.run_ffmpeg_task, ffmpeg, f, settings): f for f in self.file_list}
            
            for future in concurrent.futures.as_completed(futures):
                if self.stop_event.is_set():
                    break
                
                # 这里的 result 是 run_ffmpeg_task 的返回值 (True/False)
                # 但因为我们在 task 内部处理了异常和日志，这里主要是为了确保任务完成
                pass

        self.is_processing = False
        self.after(0, lambda: self.reset_ui(self.finished_files_count, self.total_files_count))

    def check_loudness(self, ffmpeg, file_path):
        try:
            self.log_msg(f"正在分析输出文件音量...")
            cmd = [
                ffmpeg, "-hide_banner",
                "-i", file_path,
                "-af", "volumedetect",
                "-vn", "-sn", "-dn",
                "-f", "null", "-"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, errors="replace", creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            
            # [Parsed_volumedetect_0 @ ...] mean_volume: -29.1 dB
            import re
            match = re.search(r"mean_volume:\s+([-\d.]+)\s+dB", res.stderr)
            if match:
                vol = float(match.group(1))
                self.log_msg(f"🔍 验证: 输出文件平均音量为 {vol} dB")
                if vol > -15.0: # 一般正常音量在 -10 到 -20 之间，如果压缩了90%应该远低于 -15
                    self.log_msg("⚠️ 警告: 音量似乎仍然很大，请检查播放器是否开启了'音量规格化'或'响度平衡'功能。")
            else:
                self.log_msg("验证音量失败: 无法解析结果")
        except Exception as e:
            self.log_msg(f"验证音量出错: {e}")

    def detect_crop(self, ffmpeg, input_path, start_time=0):
        """
        使用 cropdetect 滤镜检测视频的有效区域。
        仅检测几帧以加快速度。
        """
        try:
            # 跳过片头后再检测，避免片头黑屏影响结果
            ss_arg = str(start_time + 10) # 往后推一点，确保有画面
            
            # 如果视频很短，可能 10秒后都没了，那就在 1/3 处检测
            # 这里简单处理，如果出错或没检测到，就返回 None
            
            cmd = [
                ffmpeg, "-hide_banner",
                "-ss", ss_arg,
                "-i", input_path,
                "-vf", "cropdetect=24:16:0", # limit=24, round=16, reset=0
                "-vframes", "10",
                "-f", "null", "-"
            ]
            
            res = subprocess.run(
                cmd, capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            ) # 不要 check=True，因为 -ss 可能超出范围导致错误，我们需要手动处理
            
            # 解析输出寻找 crop=w:h:x:y
            # [Parsed_cropdetect_0 @ ...] x1:0 x2:1919 y1:140 y2:939 w:1920 h:800 x:0 y:140 pts:130 t:5.416667 crop=1920:800:0:140
            matches = re.findall(r"crop=(\d+:\d+:\d+:\d+)", res.stderr)
            if matches:
                # 统计出现次数最多的 crop 参数（简单的众数）
                from collections import Counter
                most_common = Counter(matches).most_common(1)
                if most_common:
                    return most_common[0][0]
            
            # 备用尝试：如果 offset 10秒 失败（可能视频短），尝试从头开始
            if start_time == 0: # 避免无限递归
                return self.detect_crop(ffmpeg, input_path, 0)
                
            return None
        except Exception as e:
            self.log_msg(f"自动裁剪检测失败: {e}")
            return None

    def run_ffmpeg_task(self, ffmpeg, input_path, settings):
        directory, filename = os.path.split(input_path)
        name, _ = os.path.splitext(filename)
        output_filename = f"{name}_800x450_compressed.mp4"
        
        output_dir = settings["output_dir"]
        if output_dir and os.path.exists(output_dir):
            output_path = os.path.join(output_dir, output_filename)
        else:
            output_path = os.path.join(directory, output_filename)
        
        # 获取用户设置
        try:
            skip_start = float(settings["skip_start"])
        except:
            skip_start = 0.0
            
        try:
            skip_end = float(settings["skip_end"])
        except:
            skip_end = 0.0
            
        do_crop = settings["crop"]

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
                self.log_msg(f"[{filename}] 视频总时长: {duration} 秒")
        except Exception as e:
            self.log_msg(f"Probe Error: {e}")

        # 计算实际编码的时长和起始点
        if skip_start >= duration:
            self.log_msg(f"⚠️ 跳过片头 ({skip_start}s) 超过视频时长，跳过此文件。")
            return False
            
        actual_duration = duration - skip_start - skip_end
        if actual_duration <= 0:
             self.log_msg(f"⚠️ 设置的裁剪后时长无效 (总:{duration} - 头:{skip_start} - 尾:{skip_end} <= 0)。")
             return False

        vol_factor = settings["volume"]
        
        # 视频滤镜链构建
        filters = []
        
        # 1. 自动裁剪
        if do_crop:
            self.log_msg("正在分析黑边区域...")
            # 尽量在用户希望的开始时间点附近检测，比较准确
            crop_arg = self.detect_crop(ffmpeg, input_path, start_time=skip_start) 
            if crop_arg:
                self.log_msg(f"检测到有效区域: {crop_arg}")
                filters.append(f"crop={crop_arg}")
            else:
                self.log_msg("未检测到明显的黑边，跳过裁剪。")

        # 2. 缩放
        filters.append("scale=800:450")
        
        vf_chain = ",".join(filters)
        
        temp_sub_path = None

        # 检查是否有字幕
        if input_path in self.file_subtitles:
            original_sub = self.file_subtitles[input_path]
            try:
                # 创建临时字幕文件以避免特殊字符 (空格, 括号, 引号等) 导致的 FFmpeg 路径错误
                ext = os.path.splitext(original_sub)[1]
                temp_filename = f"safe_sub_{uuid.uuid4().hex}{ext}"
                temp_dir = tempfile.gettempdir()
                temp_sub_path = os.path.join(temp_dir, temp_filename)
                
                shutil.copy2(original_sub, temp_sub_path)
                self.log_msg(f"创建临时字幕文件: {temp_sub_path}")
                
                # FFmpeg filter 路径转义: 
                # 1. backslash -> forward slash
                # 2. escape colon (:) which is a filter delimiter, with \:
                safe_sub_path = temp_sub_path.replace('\\', '/').replace(':', '\\:')
                
                # 使用 force_style 设置字体
                vf_chain += f",subtitles='{safe_sub_path}':force_style='FontName=SimHei'"
                self.log_msg(f"检测到外挂字幕，已处理并在压缩中烧录。")
            except Exception as e:
                self.log_msg(f"处理字幕文件失败: {e}")
                temp_sub_path = None # 防止后续清理出错

        cmd = [
            ffmpeg, "-y"
        ]
        
        # 添加跳过片头 (必须放在 -i 之前以利用 input seeking 提高速度，但在某些复杂编码下可能有关键帧对其问题)
        # 为了精确剪辑，input seeking 结合 output duration 通常较好，或者放在 -i 之后 output seeking (更精确但慢)
        # 这里为了速度和通用性，我们放在 -i 之前，但注意 FFmpeg 的机制
        if skip_start > 0:
            cmd.extend(["-ss", str(skip_start)])
            
        cmd.extend(["-i", input_path])

        # 设置处理时长 (注意：如果在 -i 之前用了 -ss，这里的 -t 是指“读取输入流的时长”，即我们需要截取的片段长度)
        # 如果 skip_end > 0，我们需要截取 duration - skip_start - skip_end
        if skip_end > 0:
             cmd.extend(["-t", str(actual_duration)])
             
        # 构建音频滤镜
        audio_filters = []
        # volume 滤镜 (当不为 1.0 时或为了确保设置生效，我们总是应用，除非是 0需要特殊处理?)
        # FFmpeg volume=0.0 Silence, volume=1.0 Normal.
        audio_filters.append(f"volume={vol_factor:.2f}")

        cmd.extend([
            "-vf", vf_chain
        ])

        if audio_filters:
            cmd.extend(["-af", ",".join(audio_filters)])

        cmd.extend([
            "-c:v", self.encoder_name,

            "-b:v", "800k",
            "-maxrate", "1200k",
            "-bufsize", "1600k",
            "-c:a", "aac",
            "-b:a", "128k",
            output_path
        ])
        
        if "nvenc" in self.encoder_name:
            cmd.extend(["-preset", "p4"])
        elif "libx264" in self.encoder_name:
            cmd.extend(["-preset", "medium"])
            
        db_val = 0
        if vol_factor > 0:
            db_val = 20 * math.log10(vol_factor)
        elif vol_factor == 0:
            db_val = -999
            
        self.log_msg(f"[{name}] 音量设置: {vol_factor:.2f} ({(vol_factor*100):.0f}%) -> {db_val:.1f}dB")
        self.log_msg(f"执行命令: {' '.join(cmd)}")
        
        start_time = time.time()
        
        proc = None
        try:
            proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                encoding='utf-8',
                errors='replace',
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            )
            
            with self.active_processes_lock:
                self.active_processes.add(proc)
            
            while True:
                if self.stop_event.is_set():
                    proc.kill()
                    return False
                    
                line = proc.stdout.readline()
                if not line:
                    break
                
                if "Error" in line or "error" in line or "Invalid" in line:
                    self.log_msg(f"[{os.path.basename(input_path)}] Error: {line.strip()}")
                
                if "time=" in line and duration > 0:
                    t_match = re.search(r"time=(\d{2}):(\d{2}):(\d{2}\.\d{2})", line)
                    if t_match:
                        h, m, s = map(float, t_match.groups())
                        current_time = h*3600 + m*60 + s
                        percent = min(current_time / duration, 1.0)
                        
                        # 更新当前文件的进度
                        with self.file_progress_lock:
                            self.file_progress_map[input_path] = percent
                        
                        # 触发 UI 总进度更新
                        self.after(0, self.update_composite_progress)
                
            proc.wait()
            ret_code = proc.returncode
            
            if ret_code == 0:
                with self.active_processes_lock:
                    self.finished_files_count += 1
                with self.file_progress_lock:
                    self.file_progress_map[input_path] = 1.0
                self.log_msg(f"✅ 文件成功: {os.path.basename(input_path)}")
                
                # 验证音量
                if vol_factor < 0.99: # 只有在调整音量时才检查
                    self.check_loudness(ffmpeg, output_path)
            else:
                with self.active_processes_lock:
                    self.failed_files_count += 1
                self.log_msg(f"❌ 文件失败: {os.path.basename(input_path)}")

            # 更新总进度 UI
            progress_val = (self.finished_files_count + self.failed_files_count) / self.total_files_count
            status_text = f"处理中... 完成 {self.finished_files_count}/{self.total_files_count} (失败: {self.failed_files_count})"
            self.update_ui_text(status_text, progress_val)
                
            return ret_code == 0
            
        except Exception as e:
            self.log_msg(f"执行异常 [{os.path.basename(input_path)}]: {e}")
            self.failed_files_count += 1
            return False
        finally:
            if proc:
                with self.active_processes_lock:
                    if proc in self.active_processes:
                        self.active_processes.remove(proc)
             # 清理临时字幕文件
            if temp_sub_path and os.path.exists(temp_sub_path):
                try:
                    os.remove(temp_sub_path)
                    self.log_msg("已清理临时字幕文件")
                except Exception as e:
                    self.log_msg(f"清理临时文件失败 (不影响结果): {e}")

    def update_composite_progress(self):
        """
        计算所有文件的平均进度并更新 UI。
        总进度 = (所有文件进度之和) / 文件总数
        """
        if not self.is_processing and self.finished_files_count + self.failed_files_count == self.total_files_count:
            return # 避免结束后的多余刷新

        with self.file_progress_lock:
            total_sum = sum(self.file_progress_map.values())
        
        if self.total_files_count > 0:
            avg_progress = total_sum / self.total_files_count
        else:
            avg_progress = 0
            
        progress_percent = int(avg_progress * 100)
        
        # 构建状态文本
        if self.total_files_count == 1:
            # 单文件模式：显示详细百分比
            status_text = f"🚀 正在处理... {progress_percent}%"
        else:
            # 多文件模式：显示完成数量和总进度
            status_text = f"🚀 并行处理中... 总进度 {progress_percent}% (完成 {self.finished_files_count}/{self.total_files_count})"
            
        self.progress_bar.set(avg_progress)
        self.status_label.configure(text=status_text)

    def update_ui_text(self, text, progress):
        self.after(0, lambda: self._update_ui_progress(progress, text))
        
    def _update_ui_progress(self, val, text):
        # 仅用于非计算进度的直接状态设置
        self.progress_bar.set(val)
        self.status_label.configure(text=text)

    def reset_ui(self, count, total):
        self.btn_start.configure(state="normal")
        self.btn_add.configure(state="normal")
        self.btn_clear.configure(state="normal")
        self.btn_set_sub.configure(state="normal")
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
