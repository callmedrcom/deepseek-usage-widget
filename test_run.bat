@echo off
chcp 65001 >nul
title DeepSeek Widget — 调试运行

cd /d "%~dp0"

:: ── 检查并创建虚拟环境 ──
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [ .. ] 首次运行，正在创建虚拟环境...
    python -m venv "%~dp0venv"
    if %errorlevel% neq 0 (
        echo [ERR] 虚拟环境创建失败，请确认 Python 已安装
        pause
        exit /b 1
    )
    call "%~dp0venv\Scripts\activate.bat"
    echo [ .. ] 正在安装 requests...
    pip install requests -q --disable-pip-version-check
    if %errorlevel% neq 0 (
        echo [ERR] requests 安装失败
        pause
        exit /b 1
    )
    echo [ OK ] 环境准备完成
) else (
    call "%~dp0venv\Scripts\activate.bat"
)

echo [ .. ] 正在启动 DeepSeek 用量悬浮窗...
echo         (悬浮窗将出现在屏幕右下角)
echo         (右键悬浮窗可打开设置、输入 API Key)
echo         (关闭此命令行窗口不会影响悬浮窗)
echo.

python "%~dp0deepseek_usage_widget.py"
pause
