# MP4/MKV 便携压缩器

一个简单易用的视频压缩工具，可将 MP4、MKV 等视频文件压缩为 800x450 分辨率的 MP4 格式。

## 功能特点

- ✅ 支持多种视频格式（MP4, MKV, AVI, MOV, FLV）
- ✅ 批量处理多个文件
- ✅ 自动压缩为 800x450 分辨率
- ✅ 使用 H.264 编码，高压缩比
- ✅ 便携式设计，无需安装
- ✅ 友好的图形界面

## 系统要求

- Windows 11 或 Windows 10
- 无需安装 Python（使用打包版本）

## 使用方法

### 方式一：使用打包好的可执行文件（推荐）

1. 运行 `dist\MP4Compressor.exe`
2. 点击"添加文件"按钮选择要压缩的视频
3. 点击"开始压缩"按钮
4. 压缩完成后，文件会保存在原视频所在目录，文件名格式为：`原文件名_800x450_compressed.mp4`

### 方式二：从源代码运行

1. 确保已安装 Python 3.8+
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 运行程序：
   ```bash
   python main.py
   ```

## 构建可执行文件

如果你想自己构建可执行文件：

1. 确保 FFmpeg 已下载并解压到 `ffmpeg/bin/` 目录
2. 运行构建脚本：
   ```bash
   build.bat
   ```
3. 构建完成后，可执行文件位于 `dist` 目录

## 技术规格

- **输出格式**: MP4
- **视频编码**: H.264 (libx264)
- **分辨率**: 800x450
- **质量参数**: CRF 28（较高压缩率）
- **音频编码**: AAC, 128kbps
- **编码预设**: medium

## 文件结构

```
mp4压缩器/
├── main.py                    # 主程序
├── build.bat                  # 构建脚本
├── requirements.txt           # Python 依赖
├── ffmpeg/                    # FFmpeg 目录
│   └── bin/
│       ├── ffmpeg.exe
│       ├── ffplay.exe
│       └── ffprobe.exe
└── dist/                      # 构建输出（运行 build.bat 后生成）
    ├── MP4Compressor.exe
    └── ffmpeg/
        └── bin/
            └── ffmpeg.exe
```

## 常见问题

### Q: 提示"未检测到 FFmpeg"怎么办？
A: 确保 `ffmpeg/bin/ffmpeg.exe` 文件存在。如果使用打包版本，确保 `dist/ffmpeg/bin/ffmpeg.exe` 存在。

### Q: 压缩后的视频质量如何？
A: 使用 CRF 28 参数，在保持较好质量的同时实现高压缩率。如需调整质量，可修改 `main.py` 中的 CRF 值（数值越小质量越好，文件越大）。

### Q: 可以修改输出分辨率吗？
A: 可以。修改 `main.py` 第 151 行的 `scale=800:450` 参数。

### Q: 支持保持原始宽高比吗？
A: 当前版本强制缩放到 800x450。如需保持宽高比，可将缩放参数改为：
   ```python
   "-vf", "scale=800:450:force_original_aspect_ratio=decrease,pad=800:450:(ow-iw)/2:(oh-ih)/2"
   ```

## 开发信息

- **GUI 框架**: CustomTkinter
- **视频处理**: FFmpeg 8.0.1
- **打包工具**: PyInstaller

## 许可证

本项目使用 FFmpeg，遵循 GPL 许可证。

## 更新日志

### v1.0.0
- 初始版本
- 支持 MP4/MKV 批量压缩
- 图形界面
- 便携式打包
