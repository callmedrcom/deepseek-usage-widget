@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title DeepSeek Widget — Build EXE

cd /d "%~dp0"

echo.
echo ==========================================
echo   DeepSeek Usage Widget — Build EXE
echo ==========================================
echo.

:: ── Check Python ──
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Python not found. Install Python 3.8+ from:
    echo        https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [ OK ] Python:
python --version

:: ── Create venv ──
if not exist "%~dp0venv" (
    echo.
    echo [ .. ] Creating virtual environment...
    python -m venv "%~dp0venv"
    if %errorlevel% neq 0 (
        echo [FAIL] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [ OK ] Virtual environment created
) else (
    echo [ OK ] Virtual environment exists
)

set PY=%~dp0venv\Scripts\python.exe

:: ── Install dependencies ──
echo.
echo [ .. ] Installing dependencies...
%PY% -m pip install requests pyinstaller -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [FAIL] Failed to install dependencies
    pause
    exit /b 1
)
echo [ OK ] Dependencies installed

:: ── Verify imports ──
echo.
echo [ .. ] Verifying package...
%PY% -c "import sys; sys.path.insert(0, r'%~dp0'); from run_widget import main; print('OK')"
if %errorlevel% neq 0 (
    echo [FAIL] Package verification failed — check for syntax errors
    pause
    exit /b 1
)
echo [ OK ] Package verified

:: ── Build ──
echo.
echo [ .. ] Building EXE (takes 1—2 minutes)...
echo.

%PY% -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name DeepSeekWidget ^
    --clean ^
    --hidden-import crypto_utils ^
    --paths "%~dp0" ^
    --distpath "%~dp0" ^
    --workpath "%~dp0build_temp" ^
    --specpath "%~dp0build_temp" ^
    "%~dp0run_widget.py"

if %errorlevel% neq 0 (
    echo.
    echo [FAIL] Build failed — see errors above
    pause
    exit /b 1
)

:: ── Cleanup ──
echo.
echo [ .. ] Cleaning up...
rmdir /s /q "%~dp0build_temp" 2>nul
del /q "%~dp0DeepSeekWidget.spec" 2>nul
echo [ OK ] Temp files removed

:: ── Result ──
if exist "%~dp0DeepSeekWidget.exe" (
    for %%F in ("%~dp0DeepSeekWidget.exe") do set /a size_mb=%%~zF / 1048576
    echo.
    echo ==========================================
    echo   Build Complete
    echo.
    echo   DeepSeekWidget.exe ^(!size_mb! MB^)
    echo   %~dp0
    echo ==========================================
    echo.
    echo Double-click DeepSeekWidget.exe to run.
) else (
    echo [WARN] EXE not found at expected path
)

echo.
pause
endlocal
