@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title DeepSeek Widget — 一键部署 ^& 打包

cd /d "%~dp0"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║   DeepSeek Usage Widget — 部署 ^& 打包       ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ── 检查 Python ──
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] 未找到 Python，请先安装 Python 3.8+
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)
python --version
echo.

:: ── 创建虚拟环境 ──
if not exist "%~dp0venv" (
    echo [ .. ] 正在创建虚拟环境...
    python -m venv "%~dp0venv"
    if %errorlevel% neq 0 (
        echo [FAIL] 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo [ OK ] 虚拟环境已创建
) else (
    echo [ OK ] 虚拟环境已存在，跳过创建
)

:: ── 激活并安装依赖 ──
set VENV_PYTHON=%~dp0venv\Scripts\python.exe
set VENV_PIP=%~dp0venv\Scripts\pip.exe

echo.
echo [ .. ] 安装依赖...
%VENV_PIP% install requests pyinstaller -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [FAIL] 依赖安装失败
    pause
    exit /b 1
)
echo [ OK ] 依赖已安装

:: ── 语法检查 ──
echo.
echo [ .. ] 语法检查...
%VENV_PYTHON% -c "import ast; ast.parse(open('deepseek_usage_widget.py', encoding='utf-8').read()); print('OK')"
if %errorlevel% neq 0 (
    echo [FAIL] 代码存在语法错误
    pause
    exit /b 1
)
echo [ OK ] 语法检查通过

:: ── 打包 ──
echo.
echo [ .. ] 正在打包为 EXE（约 1-2 分钟）...
echo.

%VENV_PYTHON% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name DeepSeekWidget ^
    --clean ^
    --hidden-import requests ^
    --hidden-import json ^
    --hidden-import threading ^
    --hidden-import tkinter ^
    --hidden-import tkinter.font ^
    --hidden-import logging ^
    --hidden-import crypto_utils ^
    --add-data "%~dp0crypto_utils.py;." ^
    --distpath "%~dp0" ^
    --workpath "%~dp0build_temp" ^
    --specpath "%~dp0build_temp" ^
    "%~dp0deepseek_usage_widget.py"

if %errorlevel% neq 0 (
    echo.
    echo [FAIL] 打包失败，请检查上方错误信息
    pause
    exit /b 1
)

:: ── 清理临时文件 ──
echo.
echo [ .. ] 清理临时文件...
rmdir /s /q "%~dp0build_temp" 2>nul
del /q "%~dp0DeepSeekWidget.spec" 2>nul

:: ── 结果 ──
if exist "%~dp0DeepSeekWidget.exe" (
    for %%F in ("%~dp0DeepSeekWidget.exe") do set fsize=%%~zF
    set /a fsize_mb=!fsize! / 1048576
    echo.
    echo ╔══════════════════════════════════════════════╗
    echo ║  [DONE] 打包完成                              ║
    echo ║                                              ║
    echo ║  DeepSeekWidget.exe (!fsize_mb! MB)          ║
    echo ║  %~dp0                                      ║
    echo ╚══════════════════════════════════════════════╝
    echo.
    echo 双击 DeepSeekWidget.exe 即可运行。
) else (
    echo [WARN] 未找到生成的 EXE
)

echo.
pause
endlocal
