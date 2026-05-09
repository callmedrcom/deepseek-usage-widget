@echo off
chcp 65001 >nul
title DeepSeek Widget — 打包工具

echo.
echo ╔══════════════════════════════════════════╗
echo ║   DeepSeek Usage Widget — 打包为 EXE     ║
echo ╚══════════════════════════════════════════╝
echo.

:: ── 检查 Python ──
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未找到 Python，请先安装 Python 3.8+
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [ OK ] Python 已就绪

:: ── 使用虚拟环境（如果存在）──
if exist "%~dp0venv\Scripts\python.exe" (
    echo [ OK ] 使用虚拟环境
    set PYTHON=%~dp0venv\Scripts\python.exe
    set PIP=%~dp0venv\Scripts\pip.exe
) else (
    echo [ .. ] 未找到虚拟环境，使用系统 Python
    set PYTHON=python
    set PIP=pip
)

:: ── 安装 PyInstaller ──
echo.
echo [ .. ] 安装 PyInstaller...
%PIP% install pyinstaller -q
if %errorlevel% neq 0 (
    echo [FAIL] PyInstaller 安装失败
    pause
    exit /b 1
)
echo [ OK ] PyInstaller 已安装

:: ── 安装 requests ──
echo.
echo [ .. ] 安装 requests...
%PIP% install requests -q
if %errorlevel% neq 0 (
    echo [FAIL] requests 安装失败
    pause
    exit /b 1
)
echo [ OK ] requests 已安装

:: ── 打包 ──
echo.
echo [ .. ] 正在打包 (需要 1-2 分钟)...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name DeepSeekWidget ^
    --clean ^
    --hidden-import requests ^
    --hidden-import json ^
    --hidden-import threading ^
    --hidden-import logging ^
    --hidden-import crypto_utils ^
    --add-data "%~dp0crypto_utils.py;." ^
    --distpath "%USERPROFILE%\Desktop" ^
    --workpath "%TEMP%\deepseek_build" ^
    --specpath "%TEMP%\deepseek_build" ^
    "%~dp0deepseek_usage_widget.py"

if %errorlevel% neq 0 (
    echo.
    echo [FAIL] 打包失败
    pause
    exit /b 1
)

:: ── 清理 ──
echo.
echo [ .. ] 清理临时文件...
rmdir /s /q "%TEMP%\deepseek_build" 2>nul

echo.
echo ╔══════════════════════════════════════════╗
echo ║  [ OK ] 打包完成！                        ║
echo ║                                          ║
echo ║  文件: 桌面\DeepSeekWidget.exe            ║
echo ╚══════════════════════════════════════════╝
echo.
echo 双击 DeepSeekWidget.exe 即可运行。
echo.

pause
