@echo off
setlocal enabledelayedexpansion
title DeepSeek Widget — Build EXE

cd /d "%~dp0"

echo.
echo ==========================================
echo   DeepSeek Usage Widget - Build EXE
echo ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [FAIL] Python not found. Install Python 3.8+ from:
    echo        https://www.python.org/downloads/
    goto end
)
echo [ OK ] Python:
python --version

:: Create venv
if not exist "%~dp0venv" (
    echo.
    echo [ .. ] Creating virtual environment...
    python -m venv "%~dp0venv"
    if %errorlevel% neq 0 (
        echo [FAIL] Failed to create virtual environment
        goto end
    )
    echo [ OK ] Virtual environment created
) else (
    echo [ OK ] Virtual environment exists
)

set PY=%~dp0venv\Scripts\python.exe

:: Install dependencies
echo.
echo [ .. ] Installing dependencies...
%PY% -m pip install requests pyinstaller -q --disable-pip-version-check
if %errorlevel% neq 0 (
    echo [FAIL] Failed to install dependencies
    goto end
)
echo [ OK ] Dependencies installed

:: Verify package
echo.
echo [ .. ] Verifying package...
set "PROJ_DIR=%~dp0"
%PY% -c "import sys; sys.path.insert(0, r'%PROJ_DIR:\=/%'.rstrip('/')); from run_widget import main; print('OK')"
if %errorlevel% neq 0 (
    echo [FAIL] Package verification failed - check for syntax errors
    goto end
)
echo [ OK ] Package verified

:: Build
echo.
echo [ .. ] Building EXE (1-2 minutes)...
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
    echo [FAIL] Build failed - see errors above
    goto end
)

:: Cleanup
echo.
echo [ .. ] Cleaning up...
rmdir /s /q "%~dp0build_temp" 2>nul
del /q "%~dp0DeepSeekWidget.spec" 2>nul
echo [ OK ] Temp files removed

:: Result
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

:end
echo.
pause
endlocal
