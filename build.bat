@echo off
chcp 65001 >nul
echo ========================================
echo MP4 压缩器构建脚本
echo ========================================
echo.

REM 设置 Python 路径
set PYTHON_PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
set PIP_PATH=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\Scripts\pip.exe

REM 检查 Python 是否安装
"%PYTHON_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    rem pause
    exit /b 1
)

REM 检查 FFmpeg 是否存在
if not exist "ffmpeg\bin\ffmpeg.exe" (
    echo [错误] 未找到 ffmpeg\bin\ffmpeg.exe
    echo 请确保已下载并解压 FFmpeg 到项目目录
    rem pause
    exit /b 1
)

echo [1/5] 安装 Python 依赖...
"%PYTHON_PATH%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [错误] 依赖安装失败
    rem pause
    exit /b 1
)

echo.
echo [2/5] 清理旧的构建文件...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "*.spec" del /q "*.spec"

echo.
echo [3/5] 使用 PyInstaller 构建可执行文件...
"%PYTHON_PATH%" -m PyInstaller --noconsole --onefile --name "MP4Compressor" ^
    --add-data "ffmpeg/bin;ffmpeg/bin" ^
    --add-data "tubiao.ico;." ^
    --icon=tubiao.ico ^
    main.py

if errorlevel 1 (
    echo [错误] 构建失败
    rem pause
    exit /b 1
)

echo.
echo [4/5] 复制 FFmpeg 到输出目录...
if not exist "dist\ffmpeg\bin" mkdir "dist\ffmpeg\bin"
copy "ffmpeg\bin\ffmpeg.exe" "dist\ffmpeg\bin\" >nul
copy "ffmpeg\bin\ffplay.exe" "dist\ffmpeg\bin\" >nul
copy "ffmpeg\bin\ffprobe.exe" "dist\ffmpeg\bin\" >nul

echo.
echo [5/5] 验证构建结果...
if not exist "dist\MP4Compressor.exe" (
    echo [错误] 未找到生成的可执行文件
    rem pause
    exit /b 1
)

if not exist "dist\ffmpeg\bin\ffmpeg.exe" (
    echo [错误] FFmpeg 复制失败
    rem pause
    exit /b 1
)

echo.
echo ========================================
echo 构建成功！
echo ========================================
echo 可执行文件位置: dist\MP4Compressor.exe
echo FFmpeg 位置: dist\ffmpeg\bin\
echo.
echo 你可以将整个 dist 目录复制到任何位置使用
echo ========================================
rem pause
